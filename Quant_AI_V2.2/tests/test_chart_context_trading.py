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
    setup_chart_ui(win)
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
