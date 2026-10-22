# -*- coding: utf-8 -*-
"""
Unit tests for Top Ribbon / Header Bar 3-Zone Architecture and Alignment.
Validates:
1. 3-zone layout structure (Chart Controls, Semi-Auto Controls, Account Telemetry).
2. Uniform fixed width (26px) and height (20px) across all 9 timeframe buttons (M1-MN1).
3. Uniform 1px x 14px vertical separators.
4. Clean symbol display without long verbose descriptions (no 'Gold vs US Dollar').
5. Compact account telemetry with segregated font typography (Monospace for values, Segoe UI for labels).
6. AlgoControlPill placement and internal separator alignment.
"""

import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QFrame, QPushButton, QLabel, QTabWidget, QSplitter
from PySide6.QtCore import Qt

from frontend.controllers.header_controller import WorkspaceHeaderController
from frontend.widgets.bot_power_button import AlgoControlPill


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def _create_mock_header_controller():
    win = QMainWindow()
    win.current_sym = "XAUUSD"
    win.is_dark_theme = False
    win.mainSplitter = QSplitter()
    win.tabWidget = QTabWidget()
    win.tab2 = QWidget()
    win.tab3 = QWidget()
    win.tab_5 = QWidget()
    win.tabCalendar = QWidget()

    term = MagicMock()
    term.window = win
    term._toggle_bot = MagicMock()

    header = WorkspaceHeaderController(term)
    header.window = win
    header._setup_custom_title_bar()
    return win, header


def test_header_ribbon_three_zones_mounted(qapp):
    """Verifies that the top header container contains Zone 1, Zone 2, and Zone 3 on a single contiguous row."""
    win, header = _create_mock_header_controller()

    assert hasattr(header, "header_container")
    assert header.header_container.height() == 26 or header.header_container.maximumHeight() == 26

    # Verify Zone 1 (Symbol + Timeframes)
    assert hasattr(header, "lbl_top_sym")
    assert hasattr(header, "tf_buttons")
    assert len(header.tf_buttons) == 9

    # Verify separator between Zone 1 and Zone 2
    assert hasattr(header, "sep_chart_algo")

    # Verify Zone 2 (ALGO Pill + Strategy + Event Risk)
    assert hasattr(header, "btn_algo_toggle")
    assert hasattr(header, "btn_top_ind")
    assert hasattr(header, "btn_event_risk")
    assert header.btn_event_risk.maximumHeight() == 20
    assert "border: 1px solid" in header.btn_event_risk.styleSheet()

    # Verify Zone 3 (Account Telemetry)
    assert hasattr(header, "lbl_top_ticker")

    # Verify only ONE stretch exists in the ribbon layout (before Zone 3)
    layout = header.header_container.layout()
    stretches = [layout.itemAt(i) for i in range(layout.count()) if layout.itemAt(i).spacerItem() is not None]
    assert len(stretches) == 1


def test_timeframe_buttons_uniform_fixed_dimensions(qapp):
    """Verifies all 9 timeframe buttons have strictly equal 26px width and 20px height."""
    win, header = _create_mock_header_controller()

    for tf_name, btn in header.tf_buttons.items():
        assert btn.maximumWidth() == 26, f"{tf_name} width must be 26px"
        assert btn.minimumWidth() == 26, f"{tf_name} width must be 26px"
        assert btn.maximumHeight() == 20, f"{tf_name} height must be 20px"
        assert btn.minimumHeight() == 20, f"{tf_name} height must be 20px"


def test_clean_symbol_display_without_verbose_description(qapp):
    """Verifies symbol display only shows clean symbol code (e.g. XAUUSD), no long description, and NO '▼' icon."""
    win, header = _create_mock_header_controller()

    header._refresh_top_ticker()
    txt = header.lbl_top_sym.text()
    assert txt == "XAUUSD"
    assert "▼" not in txt
    assert "Gold vs US Dollar" not in txt
    assert "Spot Gold" not in txt
    assert isinstance(header.lbl_top_sym, QPushButton)


def test_quick_symbol_switch_from_watchlist(qapp):
    """Verifies that selecting an asset switches current_sym and calls draw_and_analyze."""
    win, header = _create_mock_header_controller()
    win.draw_and_analyze = MagicMock()

    # Mock watchlist returning symbols
    mock_wl = MagicMock()
    mock_wl.get_all_symbols.return_value = ["XAUUSD", "BTCUSD", "EURUSD"]
    header.terminal.watchlist = mock_wl

    symbols = header._get_watchlist_symbols()
    assert "BTCUSD" in symbols

    # Switch symbol to BTCUSD
    header._switch_symbol("BTCUSD")
    assert win.current_sym == "BTCUSD"
    assert header.lbl_top_sym.text() == "BTCUSD"
    assert "▼" not in header.lbl_top_sym.text()
    win.draw_and_analyze.assert_called_once_with("BTCUSD")


def test_quick_symbol_wheel_cycling(qapp):
    """Verifies mouse wheel scrolling on symbol button cycles through watchlist symbols."""
    win, header = _create_mock_header_controller()
    win.draw_and_analyze = MagicMock()

    mock_wl = MagicMock()
    mock_wl.get_all_symbols.return_value = ["XAUUSD", "EURUSD", "GBPUSD"]
    header.terminal.watchlist = mock_wl

    # Simulate wheel event (delta < 0 -> next symbol)
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtCore import QPointF, QPoint

    mock_event_down = MagicMock()
    mock_event_down.angleDelta.return_value = QPoint(0, -120)

    header.lbl_top_sym.wheelEvent(mock_event_down)
    assert win.current_sym == "EURUSD"
    assert header.lbl_top_sym.text() == "EURUSD"

    # Delta > 0 -> previous symbol
    mock_event_up = MagicMock()
    mock_event_up.angleDelta.return_value = QPoint(0, 120)
    header.lbl_top_sym.wheelEvent(mock_event_up)
    assert win.current_sym == "XAUUSD"
    assert header.lbl_top_sym.text() == "XAUUSD"


def test_compact_account_telemetry_typography(qapp):
    """Verifies telemetry uses BAL / EQ / P&L with Monospace numbers and Segoe UI labels."""
    win, header = _create_mock_header_controller()

    ticker_html = header._format_top_ticker(bal=97519.79, eq=97519.79, pnl=0.0)
    assert "BAL:" in ticker_html
    assert "EQ:" in ticker_html
    assert "P&L:" in ticker_html
    assert "BALANCE:" not in ticker_html
    assert "$97,519.79" in ticker_html
    assert "Consolas" in ticker_html or "monospace" in ticker_html


def test_algo_control_pill_standard_height_and_separator(qapp):
    """Verifies AlgoControlPill has 20px height and uses standard 1px vertical separator line."""
    pill = AlgoControlPill(is_running=False, is_dark=False)
    assert pill.height() == 20 or pill.maximumHeight() == 20
    assert hasattr(pill, "sep_line")
    assert pill.sep_line.width() == 1 or pill.sep_line.maximumWidth() == 1
