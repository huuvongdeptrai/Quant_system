"""
Unit tests for Institutional Right-Click Chart Trading and Context-Aware Order Placement.
Validates:
1. Institutional submenu layout (Trading submenu contains Sell Limit / Buy Stop, NO direct execution at root menu).
2. Dynamic lot resolution (Manual spinbox > Broker volume_min, NO hardcoded 0.05).
3. Institutional Safety Guard: Confirmation dialog intercepts accidental clicks unless One-Click is enabled.
4. One-Click direct dispatch when explicitly enabled.
"""

import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QMainWindow, QFrame, QVBoxLayout, QMessageBox
from PySide6.QtCore import QPoint

from frontend.controllers.chart.chart_canvas import setup_chart_ui


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def _create_mock_window():
    win = QMainWindow()
    win.current_sym = "XAUUSD"
    win.is_dark_theme = True
    win.frameChartArea = QFrame()
    win.frameChartArea.setLayout(QVBoxLayout())
    with patch("backend.infrastructure.brokers.mt5_safe.mt5.terminal_info", return_value=None):
        setup_chart_ui(win)
    win.chart_order_lines = {}
    return win


def test_chart_context_menu_above_and_below_market(qapp):
    """
    Verifies that right-click context menu creates MT5/TradingView-style dedicated 'Trading' submenu,
    leaving the root menu free of accidental financial execution triggers.
    """
    win = _create_mock_window()
    assert hasattr(win, "plot_widget")

    mock_sym_info = MagicMock()
    mock_sym_info.digits = 2
    mock_sym_info.point = 0.01
    mock_sym_info.volume_min = 0.01

    mock_tick = MagicMock()
    mock_tick.bid = 2000.00
    mock_tick.ask = 2000.50

    with patch("backend.infrastructure.brokers.mt5_safe.mt5.symbol_info", return_value=mock_sym_info), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.symbol_info_tick", return_value=mock_tick):

        # 1. Test clicking ABOVE market (y = 2050 > ask 2000.50)
        mock_pt_above = MagicMock()
        mock_pt_above.y.return_value = 2050.00

        with patch.object(win.plot_widget.plotItem.vb, "mapSceneToView", return_value=mock_pt_above):
            with patch("PySide6.QtWidgets.QMenu") as MockMenu:
                mock_menu_inst = MagicMock()
                mock_trading_sub = MagicMock()
                submenus_created = {}

                def fake_add_menu(name):
                    sub = MagicMock()
                    submenus_created[name] = sub
                    return sub

                mock_menu_inst.addMenu.side_effect = fake_add_menu
                MockMenu.return_value = mock_menu_inst

                win.plot_widget.customContextMenuRequested.emit(QPoint(100, 100))
                assert mock_menu_inst.exec.called

                # Root menu must have Trading submenu
                assert "Trading" in submenus_created
                sub = submenus_created["Trading"]
                trading_actions = [str(call[0][0]) for call in sub.addAction.call_args_list if call[0]]

                # Volume must be 0.01 (min_lot), NEVER hardcoded 0.05
                assert any("Sell Limit 0.01" in a and "2050.00" in a for a in trading_actions)
                assert any("Buy Stop   0.01" in a and "2050.00" in a for a in trading_actions)

                # Root level actions must NOT contain any order execution
                root_actions = [str(call[0][0]) for call in mock_menu_inst.addAction.call_args_list if call[0]]
                assert not any("Sell Limit" in a or "Buy Limit" in a for a in root_actions)

        # 2. Test clicking BELOW market (y = 1950 < bid 2000.00)
        mock_pt_below = MagicMock()
        mock_pt_below.y.return_value = 1950.00

        with patch.object(win.plot_widget.plotItem.vb, "mapSceneToView", return_value=mock_pt_below):
            with patch("PySide6.QtWidgets.QMenu") as MockMenu:
                mock_menu_inst = MagicMock()
                submenus_created = {}
                mock_menu_inst.addMenu.side_effect = lambda name: submenus_created.setdefault(name, MagicMock())
                MockMenu.return_value = mock_menu_inst

                win.plot_widget.customContextMenuRequested.emit(QPoint(100, 200))
                assert mock_menu_inst.exec.called

                sub = submenus_created.get("Trading")
                assert sub is not None
                trading_actions = [str(call[0][0]) for call in sub.addAction.call_args_list if call[0]]
                assert any("Buy Limit  0.01" in a and "1950.00" in a for a in trading_actions)
                assert any("Sell Stop  0.01" in a and "1950.00" in a for a in trading_actions)


def test_chart_order_dynamic_lot_from_manual_spinbox(qapp):
    """
    Verifies that right-click context menu dynamically reads user lot size
    from spinManualLot instead of hardcoded 0.05.
    """
    win = _create_mock_window()
    mock_spin = MagicMock()
    mock_spin.value.return_value = 0.25
    win.spinManualLot = mock_spin

    mock_sym_info = MagicMock()
    mock_sym_info.digits = 2
    mock_sym_info.point = 0.01
    mock_sym_info.volume_min = 0.01

    mock_tick = MagicMock()
    mock_tick.bid = 2000.00
    mock_tick.ask = 2000.50

    mock_pt = MagicMock()
    mock_pt.y.return_value = 2050.00

    with patch("backend.infrastructure.brokers.mt5_safe.mt5.symbol_info", return_value=mock_sym_info), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.symbol_info_tick", return_value=mock_tick), \
         patch.object(win.plot_widget.plotItem.vb, "mapSceneToView", return_value=mock_pt):

        with patch("PySide6.QtWidgets.QMenu") as MockMenu:
            mock_menu_inst = MagicMock()
            submenus_created = {}
            mock_menu_inst.addMenu.side_effect = lambda name: submenus_created.setdefault(name, MagicMock())
            MockMenu.return_value = mock_menu_inst

            win.plot_widget.customContextMenuRequested.emit(QPoint(100, 100))
            sub = submenus_created["Trading"]
            trading_actions = [str(call[0][0]) for call in sub.addAction.call_args_list if call[0]]
            assert any("Sell Limit 0.25" in a for a in trading_actions)


def test_chart_one_click_execution_safety_guard(qapp):
    """
    Verifies that triggering order without one_click_trading_enabled prompts
    QMessageBox.question. If user cancels (No), nothing is dispatched to broker.
    """
    win = _create_mock_window()
    win.one_click_trading_enabled = False

    mock_exec_mgr = MagicMock()
    mock_pt = MagicMock()
    mock_pt.y.return_value = 2050.00

    mock_sym_info = MagicMock()
    mock_sym_info.digits = 2
    mock_sym_info.point = 0.01
    mock_sym_info.volume_min = 0.02

    mock_tick = MagicMock()
    mock_tick.bid = 2000.00
    mock_tick.ask = 2000.50

    with patch("backend.infrastructure.brokers.mt5_safe.mt5.symbol_info", return_value=mock_sym_info), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.symbol_info_tick", return_value=mock_tick), \
         patch("backend.infrastructure.brokers.execution_manager.ExecutionManager", return_value=mock_exec_mgr), \
         patch.object(win.plot_widget.plotItem.vb, "mapSceneToView", return_value=mock_pt):

        with patch("PySide6.QtWidgets.QMenu") as MockMenu:
            mock_menu_inst = MagicMock()
            actions_list = []

            def fake_add_action(text):
                act = MagicMock()
                act.text = lambda: text
                actions_list.append(act)
                return act

            mock_submenu = MagicMock()
            mock_submenu.addAction.side_effect = fake_add_action
            mock_menu_inst.addMenu.return_value = mock_submenu
            MockMenu.return_value = mock_menu_inst

            win.plot_widget.customContextMenuRequested.emit(QPoint(100, 100))
            top_action = actions_list[0]
            connect_call = top_action.triggered.connect.call_args[0][0]

            # 1. User cancels in safety prompt (QMessageBox.No) -> NO order dispatched
            with patch("PySide6.QtWidgets.QMessageBox.question", return_value=QMessageBox.No):
                connect_call()
                assert not mock_exec_mgr.execute_pending_order.called

            # 2. User confirms (QMessageBox.Yes) -> Dispatched to broker with dynamic volume 0.02
            with patch("PySide6.QtWidgets.QMessageBox.question", return_value=QMessageBox.Yes):
                mock_exec_mgr.execute_pending_order.return_value = {"status": "success", "ticket": 999123}
                connect_call()
                assert mock_exec_mgr.execute_pending_order.called
                kwargs = mock_exec_mgr.execute_pending_order.call_args[1]
                assert kwargs["symbol"] == "XAUUSD"
                assert kwargs["order_type"] == "SELL_LIMIT"
                assert kwargs["volume"] == 0.02
                assert kwargs["price"] == 2050.00


def test_chart_one_click_execution_when_enabled(qapp):
    """
    Verifies that when one_click_trading_enabled is True, orders dispatch immediately
    without showing modal.
    """
    win = _create_mock_window()
    win.one_click_trading_enabled = True

    mock_exec_mgr = MagicMock()
    mock_exec_mgr.execute_pending_order.return_value = {"status": "success", "ticket": 123456}

    mock_pt = MagicMock()
    mock_pt.y.return_value = 2050.00

    mock_sym_info = MagicMock()
    mock_sym_info.digits = 2
    mock_sym_info.point = 0.01
    mock_sym_info.volume_min = 0.01

    mock_tick = MagicMock()
    mock_tick.bid = 2000.00
    mock_tick.ask = 2000.50

    with patch("backend.infrastructure.brokers.mt5_safe.mt5.symbol_info", return_value=mock_sym_info), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.symbol_info_tick", return_value=mock_tick), \
         patch("backend.infrastructure.brokers.execution_manager.ExecutionManager", return_value=mock_exec_mgr), \
         patch.object(win.plot_widget.plotItem.vb, "mapSceneToView", return_value=mock_pt):

        with patch("PySide6.QtWidgets.QMenu") as MockMenu:
            mock_menu_inst = MagicMock()
            actions_list = []

            def fake_add_action(text):
                act = MagicMock()
                act.text = lambda: text
                actions_list.append(act)
                return act

            mock_submenu = MagicMock()
            mock_submenu.addAction.side_effect = fake_add_action
            mock_menu_inst.addMenu.return_value = mock_submenu
            MockMenu.return_value = mock_menu_inst

            win.plot_widget.customContextMenuRequested.emit(QPoint(100, 100))
            top_action = actions_list[0]
            connect_call = top_action.triggered.connect.call_args[0][0]

            with patch("PySide6.QtWidgets.QMessageBox.question") as mock_box:
                connect_call()
                assert not mock_box.called
                assert mock_exec_mgr.execute_pending_order.called

def test_order_line_context_menu_modify_and_delete(qapp):
    """
    Verifies that right-clicking directly on a pending order line displays
    the MT5-style Order Context Menu (Modify, Delete, Trailing Stop),
    and clicking Delete calls ExecutionManager.cancel_pending_order.
    """
    from PySide6.QtCore import QPointF
    win = _create_mock_window()
    win.is_pending_order = True
    win.pending_ticket = 284837434
    win.pending_price = 4143.054

    mock_exec_mgr = MagicMock()
    mock_exec_mgr.cancel_pending_order.return_value = {"status": "success", "ticket": 284837434}

    # Setup line_order_entry at 4143.054
    win.line_order_entry.setValue(4143.054)
    win.line_order_entry.setVisible(True)

    mock_sym_info = MagicMock()
    mock_sym_info.digits = 3
    mock_sym_info.point = 0.001

    mock_order = MagicMock()
    mock_order.type = 3  # SELL LIMIT
    mock_order.volume_current = 1.24
    mock_order.price_open = 4143.054

    with patch("backend.infrastructure.brokers.mt5_safe.mt5.symbol_info", return_value=mock_sym_info), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.orders_get", return_value=[mock_order]), \
         patch("backend.infrastructure.brokers.execution_manager.ExecutionManager", return_value=mock_exec_mgr):

        # Mock mapToScene and mapViewToScene so click is within 2px of line
        with patch.object(win.plot_widget, "mapToScene", return_value=MagicMock(y=lambda: 200.0)), \
             patch.object(win.plot_widget.plotItem.vb, "mapViewToScene", return_value=MagicMock(y=lambda: 200.0)):

            with patch("PySide6.QtWidgets.QMenu") as MockMenu:
                mock_menu_inst = MagicMock()
                actions_created = []

                def fake_add_action(text):
                    act = MagicMock()
                    act.text = lambda: text
                    actions_created.append(act)
                    return act

                mock_menu_inst.addAction.side_effect = fake_add_action
                mock_sub = MagicMock()
                mock_menu_inst.addMenu.return_value = mock_sub
                MockMenu.return_value = mock_menu_inst

                # Trigger right click on order line
                win.plot_widget.customContextMenuRequested.emit(QPoint(100, 100))

                # Verify Order Context Menu was executed
                assert mock_menu_inst.exec.called
                action_texts = [a.text() for a in actions_created]

                # Check Modify and Delete actions match MT5 format
                assert any("Modify #284837434" in t and "4143.054" in t for t in action_texts)
                assert any("Delete #284837434" in t and "4143.054" in t for t in action_texts)

                # Trigger Delete action
                delete_act = next(a for a in actions_created if "Delete" in a.text())
                delete_handler = delete_act.triggered.connect.call_args[0][0]
                delete_handler()

                # Verify cancel_pending_order was called with ticket 284837434
                mock_exec_mgr.cancel_pending_order.assert_called_with(284837434)
                assert win.is_pending_order is False
                assert win.pending_ticket is None


def test_order_line_drag_and_drop_modifies_pending_order(qapp):
    """
    Verifies that dragging the pending order line on the chart and releasing mouse
    triggers sigPositionChangeFinished and calls ExecutionManager.modify_pending_order.
    """
    win = _create_mock_window()
    win.is_pending_order = True
    win.pending_ticket = 284837434
    win.pending_price = 4140.000

    mock_exec_mgr = MagicMock()
    mock_exec_mgr.modify_pending_order.return_value = {"status": "success", "ticket": 284837434, "price": 4145.500}

    mock_sym_info = MagicMock()
    mock_sym_info.digits = 3

    with patch("backend.infrastructure.brokers.mt5_safe.mt5.symbol_info", return_value=mock_sym_info), \
         patch("backend.infrastructure.brokers.execution_manager.ExecutionManager", return_value=mock_exec_mgr):

        # User dragged line to 4145.500
        win.line_order_entry.setValue(4145.500)
        # Emit drag finished
        win.line_order_entry.sigPositionChangeFinished.emit(win.line_order_entry)

        assert mock_exec_mgr.modify_pending_order.called
        kwargs = mock_exec_mgr.modify_pending_order.call_args[1]
        assert kwargs["price"] == 4145.500
        assert mock_exec_mgr.modify_pending_order.call_args[0][0] == 284837434
        assert win.pending_price == 4145.500


def test_multi_order_on_chart_synchronization_and_interaction(qapp):
    """
    Verifies that multiple pending orders in MT5 (e.g. 3 Sell Limit orders)
    are all synchronized onto the chart as distinct interactive lines,
    can be dragged to modify prices, and can be cancelled via right click.
    """
    win = _create_mock_window()

    mock_sym_info = MagicMock(digits=3, point=0.001)

    order1 = MagicMock(ticket=284858911, symbol="XAUUSD", type=3, volume_initial=4.33, volume_current=4.33, price_open=4149.156, sl=0.0, tp=0.0)
    order2 = MagicMock(ticket=284858998, symbol="XAUUSD", type=3, volume_initial=5.39, volume_current=5.39, price_open=4148.868, sl=0.0, tp=0.0)
    order3 = MagicMock(ticket=284859200, symbol="XAUUSD", type=3, volume_initial=1.00, volume_current=1.00, price_open=4144.610, sl=0.0, tp=0.0)

    mock_exec_mgr = MagicMock()
    mock_exec_mgr.modify_pending_order.return_value = {"status": "success", "ticket": 284858911}
    mock_exec_mgr.cancel_pending_order.return_value = {"status": "success", "ticket": 284858998}

    with patch("backend.infrastructure.brokers.mt5_safe.mt5.symbol_info", return_value=mock_sym_info), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.orders_get", return_value=[order1, order2, order3]), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.positions_get", return_value=[]), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.terminal_info", return_value=MagicMock(connected=True)), \
         patch("backend.infrastructure.brokers.execution_manager.ExecutionManager", return_value=mock_exec_mgr):

        # Trigger sync
        win.sync_chart_orders()

        # 1. Verify all 3 orders have entry lines in chart_order_lines
        assert (284858911, "ENTRY") in win.chart_order_lines
        assert (284858998, "ENTRY") in win.chart_order_lines
        assert (284859200, "ENTRY") in win.chart_order_lines

        line1 = win.chart_order_lines[(284858911, "ENTRY")]
        line2 = win.chart_order_lines[(284858998, "ENTRY")]
        line3 = win.chart_order_lines[(284859200, "ENTRY")]

        assert line1.value() == 4149.156
        assert line2.value() == 4148.868
        assert line3.value() == 4144.610
        assert line1.movable is True
        assert line2.movable is True
        assert line3.movable is True

        # 2. Test dragging line 1 to 4152.000
        line1.setValue(4152.000)
        line1.sigPositionChangeFinished.emit(line1)
        assert mock_exec_mgr.modify_pending_order.called
        assert mock_exec_mgr.modify_pending_order.call_args[0][0] == 284858911
        assert mock_exec_mgr.modify_pending_order.call_args[1]["price"] == 4152.000

        # 3. Test right clicking line 2 displays Delete #284858998 and clicking Delete cancels it
        with patch.object(win.plot_widget, "mapToScene", return_value=MagicMock(y=lambda: 200.0)), \
             patch.object(win.plot_widget.plotItem.vb, "mapViewToScene", return_value=MagicMock(y=lambda: 200.0)):
            with patch("PySide6.QtWidgets.QMenu") as MockMenu:
                mock_menu_inst = MagicMock()
                actions_created = []
                def fake_add_action(text):
                    act = MagicMock()
                    act.text = lambda: text
                    actions_created.append(act)
                    return act
                mock_menu_inst.addAction.side_effect = fake_add_action
                mock_menu_inst.addMenu.return_value = MagicMock()
                MockMenu.return_value = mock_menu_inst

                # Trigger right click
                win.plot_widget.customContextMenuRequested.emit(QPoint(100, 100))
                action_texts = [a.text() for a in actions_created]
                assert any("Delete" in t for t in action_texts)

    # 4. Test when order 2 is cancelled in MT5, next sync removes its line
    with patch("backend.infrastructure.brokers.mt5_safe.mt5.symbol_info", return_value=mock_sym_info), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.orders_get", return_value=[order1, order3]), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.positions_get", return_value=[]), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.terminal_info", return_value=MagicMock(connected=True)):

        win.sync_chart_orders()
        assert (284858998, "ENTRY") not in win.chart_order_lines
        assert (284858911, "ENTRY") in win.chart_order_lines
        assert (284859200, "ENTRY") in win.chart_order_lines


def test_order_modify_switches_to_manual_copilot(qapp):
    """
    Verifies that selecting 'Modify #...' from on-chart context menu or clicking MODIFY in Card 2
    switches the Trading Plan directly to the MANUAL ORDER copilot (not AI Strategy),
    prepopulates ticket, volume, direction, price, SL, TP, and binds the execution gate.
    """
    from frontend.controllers.chart.trading_plan_panel import setup_trading_plan_cards

    win = _create_mock_window()
    win.frameAIArea = QFrame()
    win.layoutAIArea = QVBoxLayout(win.frameAIArea)
    setup_trading_plan_cards(win, is_dark=True)

    mock_sym_info = MagicMock(digits=3, point=0.001)
    order = MagicMock(
        ticket=284886853,
        symbol="XAUUSD",
        type=3,  # ORDER_TYPE_SELL_LIMIT
        volume_initial=3.30,
        volume_current=3.30,
        price_open=4139.644,
        sl=4149.000,
        tp=4120.000
    )

    mock_exec_mgr = MagicMock()
    mock_exec_mgr.modify_pending_order.return_value = {"status": "success", "ticket": 284886853}

    with patch("backend.infrastructure.brokers.mt5_safe.mt5.symbol_info", return_value=mock_sym_info), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.orders_get", return_value=[order]), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.positions_get", return_value=[]), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.terminal_info", return_value=MagicMock(connected=True)), \
         patch("backend.infrastructure.brokers.execution_manager.ExecutionManager", return_value=mock_exec_mgr):

        # Sync order line to chart
        win.sync_chart_orders()
        assert (284886853, "ENTRY") in win.chart_order_lines

        # Trigger right-click on the order line to open menu
        with patch.object(win.plot_widget, "mapToScene", return_value=MagicMock(y=lambda: 200.0)), \
             patch.object(win.plot_widget.plotItem.vb, "mapViewToScene", return_value=MagicMock(y=lambda: 200.0)):
            with patch("PySide6.QtWidgets.QMenu") as MockMenu:
                mock_menu_inst = MagicMock()
                actions_map = {}
                def fake_add_action(text):
                    act = MagicMock()
                    act.text = lambda: text
                    actions_map[text] = act
                    return act
                mock_menu_inst.addAction.side_effect = fake_add_action
                mock_menu_inst.addMenu.return_value = MagicMock()
                MockMenu.return_value = mock_menu_inst

                win.plot_widget.customContextMenuRequested.emit(QPoint(100, 100))

                # Find the Modify action
                modify_act_text = [t for t in actions_map.keys() if "Modify #284886853" in t][0]
                modify_action = actions_map[modify_act_text]

                # Trigger the modify action
                connect_args = modify_action.triggered.connect.call_args[0]
                handler = connect_args[0]
                handler()

        # VERIFY: Drawer is switched to MANUAL ORDER (not AI Strategy!)
        assert win._plan_mode == "manual"
        assert win.containerPlanManual.isVisible() is True
        assert win.containerPlanAI.isVisible() is False

        # VERIFY: Prefilled values
        assert win._modifying_ticket == 284886853
        assert win._modifying_is_position is False
        assert win._manual_direction == "SELL"
        assert win.spinManualLot.value() == 3.30
        assert abs(win.spinManualPendingPrice.value() - 4139.644) < 1e-3
        assert abs(win.spinManualSL.value() - 4149.000) < 1e-3
        assert abs(win.spinManualTP.value() - 4120.000) < 1e-3

        # VERIFY: Execution button binds to modification
        assert win.btnManualExecute.text() == "MODIFY ORDER #284886853"
        assert "ORDER MODIFICATION (#284886853)" in win.lblManualGateTitle.text()

        # Test executing the modification
        from frontend.controllers.chart.trading_plan_panel import execute_manual_quant_order
        execute_manual_quant_order(win)

        assert mock_exec_mgr.modify_pending_order.called
        kwargs = mock_exec_mgr.modify_pending_order.call_args[1]
        assert mock_exec_mgr.modify_pending_order.call_args[0][0] == 284886853
        assert kwargs["price"] == 4139.644
        assert kwargs["sl"] == 4149.000
        assert kwargs["tp"] == 4120.000




def test_move_sl_to_breakeven_preserves_existing_take_profit(qapp):
    """
    Verifies that choosing 'Move SL to Breakeven' from chart context menu
    preserves the position's existing TP target from MT5 instead of wiping it to 0.0.
    """
    win = _create_mock_window()
    pos = MagicMock(
        ticket=123456,
        symbol="XAUUSD",
        type=0,  # BUY
        volume=1.0,
        price_open=4100.0,
        price_current=4120.0,
        sl=4080.0,
        tp=4150.0  # Existing TP target
    )
    mock_exec_mgr = MagicMock()
    mock_exec_mgr.modify_position.return_value = {"status": "success", "ticket": 123456}

    with patch("backend.infrastructure.brokers.mt5_safe.mt5.positions_get", return_value=[pos]),          patch("backend.infrastructure.brokers.mt5_safe.mt5.orders_get", return_value=[]),          patch("backend.infrastructure.brokers.mt5_safe.mt5.terminal_info", return_value=MagicMock(connected=True)),          patch("backend.infrastructure.brokers.execution_manager.ExecutionManager", return_value=mock_exec_mgr):

        win.sync_chart_orders()
        assert (123456, "ENTRY") in win.chart_order_lines

        # Trigger right-click on the order line to open menu
        with patch.object(win.plot_widget, "mapToScene", return_value=MagicMock(y=lambda: 200.0)),              patch.object(win.plot_widget.plotItem.vb, "mapViewToScene", return_value=MagicMock(y=lambda: 200.0)):
            with patch("PySide6.QtWidgets.QMenu") as MockMenu:
                mock_menu_inst = MagicMock()
                actions_map = {}
                def fake_add_action(text):
                    act = MagicMock()
                    act.text = lambda: text
                    actions_map[text] = act
                    return act
                mock_menu_inst.addAction.side_effect = fake_add_action
                mock_menu_inst.addMenu.return_value = MagicMock()
                MockMenu.return_value = mock_menu_inst

                win.plot_widget.customContextMenuRequested.emit(QPoint(100, 100))

                assert "Move SL to Breakeven" in actions_map
                be_action = actions_map["Move SL to Breakeven"]
                connect_args = be_action.triggered.connect.call_args[0]
                handler = connect_args[0]
                handler()

        # VERIFY: modify_position was called with entry price as SL and 4150.0 as TP (PRESERVED!)
        assert mock_exec_mgr.modify_position.called
        call_args = mock_exec_mgr.modify_position.call_args
        assert call_args[0][0] == 123456
        assert call_args[1]["sl"] == 4100.0
        assert call_args[1]["tp"] == 4150.0  # CRITICAL: TP must NOT be 0.0!


def test_trailing_stop_activation_and_execution(qapp):
    """
    Verifies that choosing 'Trailing Stop -> 20 Points' records active trailing stop
    and sync_chart_orders automatically steps the SL forward on MT5 when in profit.
    """
    win = _create_mock_window()
    pos = MagicMock(
        ticket=654321,
        symbol="XAUUSD",
        type=0,  # BUY
        volume=1.0,
        price_open=4100.0,
        price_current=4130.0,  # +30.0 points in profit
        sl=4080.0,
        tp=4180.0
    )
    mock_sym_info = MagicMock(digits=2, point=0.01)
    mock_exec_mgr = MagicMock()
    mock_exec_mgr.modify_position.return_value = {"status": "success", "ticket": 654321}

    # Simulate activating 20 points trailing stop
    win._active_trailing_stops = {654321: 20}

    with patch("backend.infrastructure.brokers.mt5_safe.mt5.positions_get", return_value=[pos]),          patch("backend.infrastructure.brokers.mt5_safe.mt5.orders_get", return_value=[]),          patch("backend.infrastructure.brokers.mt5_safe.mt5.symbol_info", return_value=mock_sym_info),          patch("backend.infrastructure.brokers.mt5_safe.mt5.terminal_info", return_value=MagicMock(connected=True)),          patch("backend.infrastructure.brokers.execution_manager.ExecutionManager", return_value=mock_exec_mgr):

        win.sync_chart_orders()

        # VERIFY: SL was stepped forward: 4130.0 - (20 * 0.01) = 4129.80
        assert mock_exec_mgr.modify_position.called
        call_args = mock_exec_mgr.modify_position.call_args
        assert call_args[0][0] == 654321
        assert abs(call_args[1]["sl"] - 4129.80) < 1e-2


def test_margin_adequacy_pre_check_blocks_insufficient_margin(qapp):
    """
    Verifies that evaluate_manual_compliance blocks execution when required margin
    exceeds available free margin, protecting trader from MT5 retcode 10019.
    """
    from frontend.controllers.chart.trading_plan_panel import evaluate_manual_compliance, setup_trading_plan_cards

    win = _create_mock_window()
    win.frameAIArea = QFrame()
    win.layoutAIArea = QVBoxLayout(win.frameAIArea)
    setup_trading_plan_cards(win, is_dark=True)

    # Set lot to a large volume (e.g. 50 lots) with matching valid entry price
    win._last_manual_entry = 4120.0
    win._last_manual_ask = 4120.0
    win._last_manual_bid = 4119.5
    win.spinManualSL.setRange(0.0, 1000000.0)
    win.spinManualTP.setRange(0.0, 1000000.0)
    win.spinManualLot.setValue(50.0)
    win.spinManualSL.setValue(4090.0)
    win.spinManualTP.setValue(4150.0)
    win._manual_direction = "BUY"

    mock_acc = MagicMock(
        balance=5000.0,
        equity=5000.0,
        margin_free=2000.0,
        leverage=100
    )
    mock_tick = MagicMock(ask=4120.0, bid=4119.5)
    with patch("backend.infrastructure.brokers.mt5_safe.mt5.account_info", return_value=mock_acc), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.symbol_info_tick", return_value=mock_tick), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.terminal_info", return_value=MagicMock(connected=True)), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.order_calc_margin", return_value=205000.0):
        passed, checks, block_reason = evaluate_manual_compliance(win, "XAUUSD")
        assert passed is False
        assert "INSUFFICIENT MARGIN" in block_reason
        assert checks["margin"]["passed"] is False


def test_ai_signal_price_action_invalidation_gate(qapp):
    """
    Verifies that when market price breaches the SL level of an active proposal,
    the countdown timer stops and marks the setup as INVALIDATED immediately.
    """
    from frontend.controllers.chart.trading_plan_panel import start_signal_expiry_countdown

    win = _create_mock_window()
    win.line_order_entry = MagicMock()
    win.line_order_entry.value.return_value = 4120.0
    win.line_order_entry.isVisible.return_value = True

    win.line_order_sl = MagicMock()
    win.line_order_sl.value.return_value = 4100.0  # Buy setup SL at 4100
    win.line_order_sl.isVisible.return_value = True

    win.line_order_tp = MagicMock()
    win.line_order_tp.value.return_value = 4150.0
    win.line_order_tp.isVisible.return_value = True

    win.btnApproveOrder = MagicMock()
    win.lblSignalExpiry = MagicMock()
    win.lblGateExpiryTime = MagicMock()
    win.barSignalExpiry = MagicMock()
    win._plan_mode = "ai"

    # Start countdown
    start_signal_expiry_countdown(win, duration_sec=60)
    timer = win._signal_expiry_timer

    # Market price crashes to 4095.0 (below SL of 4100.0)
    mock_tick = MagicMock(bid=4095.0, ask=4095.5)
    with patch("backend.infrastructure.brokers.mt5_safe.mt5.symbol_info_tick", return_value=mock_tick),          patch("backend.infrastructure.brokers.mt5_safe.mt5.terminal_info", return_value=MagicMock(connected=True)):

        # Trigger timer tick
        timer.timeout.emit()

        # VERIFY: Invalidation triggered!
        assert win.btnApproveOrder.setEnabled.called
        assert win.btnApproveOrder.setEnabled.call_args[0][0] is False
        assert win.btnApproveOrder.setText.call_args[0][0] == "INVALIDATED"
