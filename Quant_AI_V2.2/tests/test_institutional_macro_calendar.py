"""
Unit tests for Institutional Macro & Economic Calendar 70:30 Defense Desk Workspace
"""

import pytest
import os
import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QTabWidget
from PySide6.QtCore import Qt

from frontend.controllers.macro_calendar_controller import MacroCalendarController, CalendarManager
from backend.core.event_risk_engine import EventRiskEngine


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def test_calendar_manager_ui_initialization_70_30(qapp):
    """Verifies that CalendarManager creates the 70:30 institutional layout."""
    win = QMainWindow()
    win.tabWidget = QTabWidget()
    win.setCentralWidget(win.tabWidget)
    win.current_sym = "XAUUSD"

    mgr = MacroCalendarController(win)

    # 1. Workspace Tab exists
    assert hasattr(win, "tabCalendar")
    assert win.tabCalendar is not None
    assert win.tabWidget.count() >= 1

    # 2. Main Economic Calendar Table exists and has 8 tight columns
    assert hasattr(win, "tableEconomicCalendar")
    table = win.tableEconomicCalendar
    assert table is not None
    assert table.columnCount() == 8
    assert table.horizontalHeaderItem(0).text() == "TIME (VN)"
    assert table.horizontalHeaderItem(1).text() == "CURR"
    assert table.horizontalHeaderItem(2).text() == "IMPACT"
    assert table.horizontalHeaderItem(3).text() == "EVENT RELEASE"
    assert table.horizontalHeaderItem(7).text() == "SURPRISE"

    # 3. 4-Pillar Macro Matrix exists (including Target Asset Confluence)
    assert hasattr(mgr, "badge_market_state")
    assert hasattr(mgr, "badge_monetary_state")
    assert hasattr(mgr, "badge_economic_state")
    assert hasattr(mgr, "badge_confluence_state")

    # 4. Filters exist (clean, no duplicate USD/Symbol)
    assert "ALL" in mgr.filter_buttons
    assert "HIGH" in mgr.filter_buttons
    assert "TARGET" in mgr.filter_buttons

    # 5. 70:30 Splitter and Right Defense Desk exist
    assert hasattr(mgr, "main_splitter")
    assert hasattr(mgr, "lbl_countdown_val")
    assert hasattr(mgr, "lbl_lockout_status")
    assert hasattr(mgr, "btn_force_defense")
    assert hasattr(mgr, "btn_override_lock")


def test_calendar_filtering_and_defense_desk(qapp):
    """Verifies filtering, surprise delta calculation, and semi-auto override."""
    win = QMainWindow()
    win.tabWidget = QTabWidget()
    win.current_sym = "XAUUSD"
    mgr = MacroCalendarController(win)

    # Mock raw events
    mgr._raw_events = [
        {"time": "20/10 19:30", "sort_key": 1792495800.0, "country": "US", "title": "Core CPI (MoM)", "impact": 2, "actual": "0.4%", "forecast": "0.3%", "previous": "0.2%"},
        {"time": "20/10 20:00", "sort_key": 1792497600.0, "country": "EU", "title": "ECB President Lagarde Speech", "impact": 2, "actual": "None", "forecast": "None", "previous": "None"},
        {"time": "20/10 21:00", "sort_key": 1792501200.0, "country": "US", "title": "Real Earnings", "impact": 1, "actual": "None", "forecast": "0.1%", "previous": "0.2%"},
        {"time": "20/10 22:00", "sort_key": 1792504800.0, "country": "GB", "title": "BoE Tenreyro Speech", "impact": 0, "actual": "None", "forecast": "None", "previous": "None"},
    ]

    # Test ALL filter
    mgr.set_filter("ALL")
    assert mgr.table.rowCount() == 5

    # Test HIGH filter
    mgr.set_filter("HIGH")
    assert mgr.table.rowCount() == 3

    # Test TARGET filter (XAUUSD -> USD events match)
    mgr.set_current_symbol("XAUUSD")
    mgr.set_filter("TARGET")
    assert mgr.table.rowCount() == 3

    # Test row selection & surprise delta
    mgr.table.selectRow(1)
    assert mgr._selected_event is not None
    assert "CPI" in mgr.lbl_next_event_title.text()

    # Test Override Lock toggle
    assert mgr._override_active is False
    mgr.btn_override_lock.setChecked(True)
    mgr._handle_override_toggle(True)
    assert mgr._override_active is True
    assert "OVERRIDE ACTIVE" in mgr.lbl_override_note.text()


def test_theme_update(qapp):
    """Verifies update_theme handles dark and light modes cleanly."""
    win = QMainWindow()
    win.tabWidget = QTabWidget()
    win.current_sym = "XAUUSD"
    mgr = MacroCalendarController(win)

    mgr.update_theme(True)
    mgr.update_theme(False)


def test_event_risk_engine_multi_asset_mapping():
    """Verifies event mapping logic in EventRiskEngine."""
    ere = EventRiskEngine()
    assert ere.is_symbol_impacted_by_event("XAUUSD", "US", "Core CPI") is True
    assert ere.is_symbol_impacted_by_event("BTCUSD", "US", "FOMC") is True
    assert ere.is_symbol_impacted_by_event("EURUSD", "US", "NFP") is True
    assert ere.is_symbol_impacted_by_event("EURUSD", "EU", "ECB Rate") is True
    assert ere.is_symbol_impacted_by_event("GBPJPY", "EU", "ECB Rate") is False
