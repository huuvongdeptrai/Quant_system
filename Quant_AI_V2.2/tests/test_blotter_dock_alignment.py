# -*- coding: utf-8 -*-
"""
Unit tests for Bottom Trade Blotter Dock Alignment, Collapse States, and Tab Sync.
Validates:
1. Filters & Export CSV buttons auto-hide when dock is collapsed.
2. Active tab removes 3-sided box border and applies clean flat underline in collapsed state.
3. Live counts sync for both POSITIONS and PENDING ORDERS in dock header.
4. Dock toggle chevron icons and uniform button heights.
5. Real-time lot typing synchronization in Trading Plan copilot.
"""

import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QMainWindow, QFrame, QVBoxLayout, QHBoxLayout, QTableWidget
from PySide6.QtCore import Qt

from frontend.controllers.blotter.positions_table_view import PositionsTableView
from frontend.controllers.chart.trading_plan_panel import setup_trading_plan_cards


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def _create_mock_blotter_window():
    win = QMainWindow()
    win.current_sym = "XAUUSD"
    win.is_dark_theme = False

    # Execution frame structure matching quant_ai.ui (itemAt(0) is QHBoxLayout)
    win.frameExecutions = QFrame()
    exec_vbox = QVBoxLayout(win.frameExecutions)
    header_layout = QHBoxLayout()
    exec_vbox.addLayout(header_layout)

    win.tableExecutions = QTableWidget()
    exec_vbox.addWidget(win.tableExecutions)

    mock_controller = MagicMock()
    mock_controller.is_dark_theme = False
    mock_controller.window = win
    mock_controller.active_blotter_mode = "active"
    mock_controller._apply_flatten_btn_style = lambda: None

    view = PositionsTableView(win, mock_controller)
    view.setup_ui()
    return win, view


def test_blotter_collapsed_state_hides_filters_and_export(qapp):
    """Verifies that FILTERS and EXPORT CSV hide when collapsed and restore when expanded."""
    win, view = _create_mock_blotter_window()

    # Initial state: expanded
    assert win.is_dock_collapsed is False
    assert view.btn_blotter_filters.isHidden() is False
    assert view.btn_blotter_export.isHidden() is False

    # Click toggle dock to collapse
    win.btnDockToggle.click()
    assert win.is_dock_collapsed is True
    assert view.btn_blotter_filters.isHidden() is True
    assert view.btn_blotter_export.isHidden() is True
    assert win.tableExecutions.isHidden() is True
    assert win.frameExecutions.height() <= 28

    # Click toggle dock to expand
    win.btnDockToggle.click()
    assert win.is_dock_collapsed is False
    assert view.btn_blotter_filters.isHidden() is False
    assert view.btn_blotter_export.isHidden() is False
    assert win.tableExecutions.isHidden() is False


def test_blotter_collapsed_tab_styling(qapp):
    """Verifies that active tab uses flat underline when collapsed, avoiding broken 3-sided box."""
    win, view = _create_mock_blotter_window()

    # When collapsed, active tab style must NOT have border-top 2px box
    win.btnDockToggle.click()
    assert win.is_dock_collapsed is True
    active_tab = view.blotter_buttons["active"]
    qss = active_tab.styleSheet()
    assert "border-bottom: 2px solid" in qss
    assert "border-top: 2px solid" not in qss


def test_blotter_synchronizes_pending_orders_count(qapp):
    """Verifies that both POSITIONS and PENDING ORDERS show live counts in dock header."""
    win, view = _create_mock_blotter_window()

    mock_pos = [
        MagicMock(ticket=101, volume=0.5, price_open=4100.0, price_current=4105.0, profit=250.0, time=1700000000, symbol="XAUUSD", comment="ICT", type=0, sl=4090.0, tp=4120.0),
        MagicMock(ticket=102, volume=1.0, price_open=4110.0, price_current=4105.0, profit=-500.0, time=1700000000, symbol="XAUUSD", comment="ICT", type=1, sl=4130.0, tp=4080.0),
    ]
    mock_orders = [MagicMock(ticket=201), MagicMock(ticket=202), MagicMock(ticket=203)]

    with patch("backend.infrastructure.brokers.mt5_safe.mt5.terminal_info", return_value=MagicMock(connected=True)), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.positions_get", return_value=mock_pos), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.orders_get", return_value=mock_orders), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.symbol_info", return_value=MagicMock(digits=2)):

        view.render("active")

        assert "POSITIONS (2)" in view.blotter_buttons["active"].text()
        assert "PENDING ORDERS (3)" in view.blotter_buttons["pending"].text()


def test_blotter_button_height_uniformity(qapp):
    """Verifies that dock toggle, flatten, export, and filters buttons share uniform 20px height."""
    win, view = _create_mock_blotter_window()

    assert view.btn_blotter_filters.maximumHeight() == 20
    assert view.btn_blotter_export.maximumHeight() == 20
    assert view.btn_blotter_flatten.maximumHeight() == 20
    assert win.btnDockToggle.maximumHeight() == 20


def test_trading_plan_lot_realtime_text_sync(qapp):
    """Verifies that typing lot size in spinManualLot immediately updates execution button."""
    win = QMainWindow()
    win.current_sym = "XAUUSD"
    win.is_dark_theme = False
    win.frameAIArea = QFrame()
    win.layoutAIArea = QVBoxLayout(win.frameAIArea)
    setup_trading_plan_cards(win, is_dark=False)

    win.spinManualLot.setValue(6.00)
    assert "6.00 LOTS" in win.btnManualExecute.text()

    # User types '0.6' into lineEdit without pressing Enter
    win.spinManualLot.lineEdit().setText("0.6 LOTS")
    win.spinManualLot.lineEdit().textEdited.emit("0.6 LOTS")

    # Real-time textEdited must have parsed 0.60 and updated button
    assert "0.60 LOTS" in win.btnManualExecute.text()


def test_blotter_in_place_row_updates_prevents_widget_churn(qapp):
    """Verifies that consecutive quote updates on active positions update cells in-place without destroying widgets."""
    win, view = _create_mock_blotter_window()
    tbl = win.tableExecutions

    p1 = MagicMock(
        time=1700000000,
        ticket=99901,
        symbol="XAUUSD",
        type=0,  # BUY
        volume=1.0,
        price_open=2000.0,
        price_current=2005.0,
        profit=500.0,
        comment="TestStrategy",
        sl=1990.0,
        tp=2020.0
    )
    mock_info = MagicMock(digits=2)

    with patch("backend.infrastructure.brokers.mt5_safe.mt5.terminal_info", return_value=MagicMock(connected=True)), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.positions_get", return_value=[p1]), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.orders_get", return_value=[]), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.symbol_info", return_value=mock_info):

        # Initial full render
        view.render("active")
        assert tbl.rowCount() == 1
        assert tbl.item(0, 7).text() == "2005.00"
        assert tbl.item(0, 8).text() == "+$500.00"

        # Capture initial action widget reference in column 9
        initial_action_widget = tbl.cellWidget(0, 9)
        assert initial_action_widget is not None

        # Next quote tick: price rises to 2008.0, profit rises to 800.0
        p1.price_current = 2008.0
        p1.profit = 800.0

        view.render("active")

        # In-place update must NOT destroy or replace cellWidget
        second_action_widget = tbl.cellWidget(0, 9)
        assert second_action_widget is initial_action_widget, "Action cell widget must be preserved in-place"
        assert tbl.item(0, 7).text() == "2008.00"
        assert tbl.item(0, 8).text() == "+$800.00"
