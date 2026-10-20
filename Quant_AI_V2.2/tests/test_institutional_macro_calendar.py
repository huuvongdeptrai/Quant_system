"""
Unit tests for Institutional Macro & Economic Calendar Workspace & Event Risk Intelligence
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


def test_calendar_manager_ui_initialization(qapp):
    """Verifies that CalendarManager creates and mounts tabCalendar with all institutional panels."""
    win = QMainWindow()
    win.tabWidget = QTabWidget()
    win.setCentralWidget(win.tabWidget)
    win.current_sym = "XAUUSD"

    mgr = MacroCalendarController(win)

    # 1. Workspace Tab exists
    assert hasattr(win, "tabCalendar")
    assert win.tabCalendar is not None
    assert win.tabWidget.count() >= 1

    # 2. Main Economic Calendar Table exists and configured
    assert hasattr(win, "tableEconomicCalendar")
    table = win.tableEconomicCalendar
    assert table is not None
    assert table.columnCount() == 7
    assert table.horizontalHeaderItem(0).text() == "TIME (VN)"
    assert table.horizontalHeaderItem(1).text() == "CURRENCY"
    assert table.horizontalHeaderItem(2).text() == "IMPACT"
    assert table.horizontalHeaderItem(3).text() == "EVENT RELEASE"

    # 3. Macro Regime Tri-Pillar Matrix components exist
    assert hasattr(mgr, "badge_market_state")
    assert hasattr(mgr, "badge_monetary_state")
    assert hasattr(mgr, "badge_economic_state")
    assert hasattr(mgr, "lbl_wire_text")

    # 4. Filters exist
    assert "ALL" in mgr.filter_buttons
    assert "HIGH" in mgr.filter_buttons
    assert "USD" in mgr.filter_buttons
    assert "CURRENT" in mgr.filter_buttons

    # 5. Diagnostic Drawer exists
    assert hasattr(mgr, "lbl_drawer_title")
    assert hasattr(mgr, "lbl_drawer_assets")
    assert hasattr(mgr, "lbl_drawer_defense")
    assert hasattr(mgr, "lbl_drawer_status")


def test_calendar_filtering_and_drawer(qapp):
    """Verifies filter switching and diagnostic drawer updates."""
    win = QMainWindow()
    win.tabWidget = QTabWidget()
    win.current_sym = "EURUSD"
    mgr = MacroCalendarController(win)

    # Mock raw events
    mgr._raw_events = [
        {"time": "20/10 19:30", "sort_key": 1792450000.0, "country": "US", "title": "Core CPI (MoM)", "impact": 2, "actual": "0.3%", "forecast": "0.3%", "previous": "0.2%"},
        {"time": "20/10 20:00", "sort_key": 1792451800.0, "country": "EU", "title": "ECB President Lagarde Speech", "impact": 2, "actual": "None", "forecast": "None", "previous": "None"},
        {"time": "20/10 21:00", "sort_key": 1792455400.0, "country": "US", "title": "Real Earnings", "impact": 1, "actual": "None", "forecast": "0.1%", "previous": "0.2%"},
        {"time": "20/10 22:00", "sort_key": 1792459000.0, "country": "GB", "title": "BoE Tenreyro Speech", "impact": 0, "actual": "None", "forecast": "None", "previous": "None"},
    ]

    # Test ALL filter
    mgr.set_filter("ALL")
    # Table should have date separator + 4 rows = 5 rows
    assert mgr.table.rowCount() == 5

    # Test HIGH filter
    mgr.set_filter("HIGH")
    # Date separator + 2 high impact events = 3 rows
    assert mgr.table.rowCount() == 3

    # Test USD filter
    mgr.set_filter("USD")
    # Date separator + 2 USD events = 3 rows
    assert mgr.table.rowCount() == 3

    # Test CURRENT filter (EURUSD -> should match EU and US)
    mgr.set_current_symbol("EURUSD")
    mgr.set_filter("CURRENT")
    # Date separator + 3 events (2 US + 1 EU) = 4 rows
    assert mgr.table.rowCount() == 4

    # Test selection update on Diagnostic Drawer
    mgr.table.selectRow(1)
    assert "CPI" in mgr.lbl_drawer_title.text() or "ECB" in mgr.lbl_drawer_title.text()
    assert mgr.lbl_drawer_status.text() == "BLACKOUT WINDOW ±15M ARMED"


def test_theme_update(qapp):
    """Verifies update_theme handles both dark and light modes without exception."""
    win = QMainWindow()
    win.tabWidget = QTabWidget()
    win.current_sym = "XAUUSD"
    mgr = MacroCalendarController(win)

    # Dark mode
    mgr.update_theme(True)
    # Light mode
    mgr.update_theme(False)


def test_event_risk_engine_multi_asset_mapping():
    """Verifies event mapping logic in EventRiskEngine."""
    ere = EventRiskEngine()
    # US event affects USD and USD-dependent assets (Gold, US30, BTC)
    assert ere.is_symbol_impacted_by_event("XAUUSD", "US", "Core CPI") is True
    assert ere.is_symbol_impacted_by_event("BTCUSD", "US", "FOMC") is True
    assert ere.is_symbol_impacted_by_event("EURUSD", "US", "NFP") is True

    # EU event affects EUR but NOT GBP or USD-only
    assert ere.is_symbol_impacted_by_event("EURUSD", "EU", "ECB Rate") is True
    assert ere.is_symbol_impacted_by_event("GBPJPY", "EU", "ECB Rate") is False
