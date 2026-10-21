"""
Unit tests for Institutional Right-Click Chart Trading and Context-Aware Order Placement.
Validates that right-clicking above market suggests Sell Limit / Buy Stop,
and below market suggests Buy Limit / Sell Stop with One-Click Execution (Option A).
"""

import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QMainWindow, QFrame, QVBoxLayout
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
    Verifies that right-click context menu creates MT5-style context-aware
    trading actions (Sell Limit above ask, Buy Limit below bid).
    """
    win = _create_mock_window()
    assert hasattr(win, "plot_widget")

    mock_sym_info = MagicMock()
    mock_sym_info.digits = 2
    mock_sym_info.point = 0.01

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
                MockMenu.return_value = mock_menu_inst

                win.plot_widget.customContextMenuRequested.emit(QPoint(100, 100))
                assert mock_menu_inst.exec.called
                # Verify addAction was called with Sell Limit
                actions_added = [call[0][0] for call in mock_menu_inst.addAction.call_args_list if call[0]]
                assert any("Sell Limit" in str(a) and "2050.00" in str(a) for a in actions_added)

        # 2. Test clicking BELOW market (y = 1950 < bid 2000.00)
        mock_pt_below = MagicMock()
        mock_pt_below.y.return_value = 1950.00

        with patch.object(win.plot_widget.plotItem.vb, "mapSceneToView", return_value=mock_pt_below):
            with patch("PySide6.QtWidgets.QMenu") as MockMenu:
                mock_menu_inst = MagicMock()
                MockMenu.return_value = mock_menu_inst

                win.plot_widget.customContextMenuRequested.emit(QPoint(100, 200))
                assert mock_menu_inst.exec.called
                actions_added = [call[0][0] for call in mock_menu_inst.addAction.call_args_list if call[0]]
                assert any("Buy Limit" in str(a) and "1950.00" in str(a) for a in actions_added)


def test_chart_one_click_execution_dispatch(qapp):
    """
    Verifies that triggering the top action calls ExecutionManager.execute_pending_order
    with exact price, lot, and symbol (Option A One-Click Trading).
    """
    win = _create_mock_window()

    mock_exec_mgr = MagicMock()
    mock_exec_mgr.execute_pending_order.return_value = {
        "status": "success",
        "ticket": 888123,
        "msg": "OK"
    }

    mock_pt = MagicMock()
    mock_pt.y.return_value = 2050.00

    mock_sym_info = MagicMock()
    mock_sym_info.digits = 2
    mock_sym_info.point = 0.01

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

            mock_menu_inst.addAction.side_effect = fake_add_action
            mock_submenu = MagicMock()
            mock_submenu.addAction.side_effect = fake_add_action
            mock_menu_inst.addMenu.return_value = mock_submenu
            MockMenu.return_value = mock_menu_inst

            win.plot_widget.customContextMenuRequested.emit(QPoint(100, 100))

            # The first action added is the top Sell Limit action
            top_action = actions_list[0]
            assert "Sell Limit" in top_action.text()
            assert "2050.00" in top_action.text()

            # Trigger its connected handler
            # In chart_canvas: act_primary.triggered.connect(lambda chk=False, t=primary_type, p=click_p: _do_execute_pending(t, p))
            connect_call = top_action.triggered.connect.call_args[0][0]
            connect_call()

            assert mock_exec_mgr.execute_pending_order.called
            call_kwargs = mock_exec_mgr.execute_pending_order.call_args[1]
            assert call_kwargs["symbol"] == "XAUUSD"
            assert call_kwargs["order_type"] == "SELL_LIMIT"
            assert call_kwargs["price"] == 2050.00
