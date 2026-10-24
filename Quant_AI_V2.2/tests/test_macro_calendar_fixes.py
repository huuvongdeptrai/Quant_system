"""
Unit tests verifying the 7 display, formatting, and language fixes for Macro Calendar & Header.
"""

import datetime
from unittest.mock import MagicMock
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QMenuBar, QFrame, QLabel

from frontend.controllers.macro_calendar_controller import MacroCalendarController
from frontend.controllers.header_controller import HeaderController


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def test_macro_matrix_institutional_english_strings(qapp):
    """Bug 1: Verifies all Macro Matrix cards output institutional English without Vietnamese diacritics."""
    win = QMainWindow()
    win.tabWidget = QTabWidget()
    win.setCentralWidget(win.tabWidget)
    win.current_sym = "XAUUSD"
    ctrl = MacroCalendarController(win)

    # 1. Economic Card Cycles
    ctrl._apply_macro_report({"Economic": {"state": "RECESSION"}})
    eco_txt = ctrl.lbl_economic_metrics.text()
    assert "PMI Contraction & Labor Softening" in eco_txt
    assert "Thu hẹp" not in eco_txt

    ctrl._apply_macro_report({"Economic": {"state": "GROWTH"}})
    assert "PMI Expansion & Robust Employment" in ctrl.lbl_economic_metrics.text()

    ctrl._apply_macro_report({"Economic": {"state": "STAGFLATION"}})
    assert "High Inflation & Slowing Growth" in ctrl.lbl_economic_metrics.text()

    ctrl._apply_macro_report({"Economic": {"state": "RECOVERY"}})
    assert "PMI Stabilizing & Labor Rebound" in ctrl.lbl_economic_metrics.text()

    # 2. Confluence Card Bias
    # Bullish scenario (gold_score >= 1.0)
    ctrl._calculate_target_asset_bias(is_risk_off=True, mon_badge="DOVISH", eco_badge="RECESSION", dxy_trend="DOWN")
    conf_txt = ctrl.lbl_confluence_metrics.text()
    assert "LONG BIAS (XAUUSD)" in conf_txt
    assert "Falling Real Yields & Haven Demand" in conf_txt
    assert "ƯU TIÊN MUA" not in conf_txt

    # Bearish scenario (gold_score <= -1.0)
    ctrl._calculate_target_asset_bias(is_risk_off=False, mon_badge="HAWKISH", eco_badge="GROWTH", dxy_trend="UP")
    conf_txt = ctrl.lbl_confluence_metrics.text()
    assert "SHORT BIAS (XAUUSD)" in conf_txt
    assert "Rising DXY & Monetary Tightening" in conf_txt
    assert "ÁP LỰC BÁN" not in conf_txt

    # Neutral scenario
    ctrl._calculate_target_asset_bias(is_risk_off=None, mon_badge="NEUTRAL", eco_badge="RECOVERY", dxy_trend="NEUTRAL")
    conf_txt = ctrl.lbl_confluence_metrics.text()
    assert "NEUTRAL (XAUUSD)" in conf_txt
    assert "Balanced Supply & Consolidation" in conf_txt


def test_timer_humanized_past_format(qapp):
    """Bug 2: Verifies timer replaces redundant 'T + ...M AGO' with humanized M / H / D past strings."""
    win = QMainWindow()
    win.tabWidget = QTabWidget()
    win.setCentralWidget(win.tabWidget)
    ctrl = MacroCalendarController(win)

    now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()

    # Case A: 45 minutes ago
    ctrl._selected_event = {
        "sort_key": now_ts - 2700,
        "impact": 2,
        "title": "Unemployment Claims",
        "country": "US"
    }
    ctrl._on_clock_tick()
    t_val = ctrl.lbl_countdown_val.text()
    assert t_val == "45M AGO"
    assert "T +" not in t_val

    # Case B: 3 hours 15 minutes ago
    ctrl._selected_event = {
        "sort_key": now_ts - (3 * 3600 + 15 * 60),
        "impact": 2,
        "title": "CPI",
        "country": "US"
    }
    ctrl._on_clock_tick()
    t_val = ctrl.lbl_countdown_val.text()
    assert t_val == "3H 15M AGO"
    assert "T +" not in t_val

    # Case C: 4 days 16 hours ago (reproducing the 6751M overflow condition)
    ctrl._selected_event = {
        "sort_key": now_ts - (4 * 86400 + 16 * 3600),
        "impact": 2,
        "title": "Housing Starts",
        "country": "US"
    }
    ctrl._on_clock_tick()
    t_val = ctrl.lbl_countdown_val.text()
    assert t_val == "4D 16H AGO"
    assert "6751" not in t_val
    assert "T +" not in t_val


def test_weekend_standby_desk(qapp):
    """Bug 2 & Fallback: Verifies weekend standby state when all releases for the week have passed."""
    win = QMainWindow()
    win.tabWidget = QTabWidget()
    win.setCentralWidget(win.tabWidget)
    ctrl = MacroCalendarController(win)

    ctrl._set_weekend_standby_desk()
    assert ctrl.lbl_next_event_title.text() == "WEEKEND STANDBY · ALL RELEASES CONCLUDED"
    assert "MONDAY MARKET REOPEN" in ctrl.lbl_next_event_time.text()
    assert ctrl.lbl_countdown_val.text() == "STANDBY"
    assert "NO UPCOMING RELEASES" in ctrl.lbl_lockout_status.text()
    assert "NONE · ALL ASSETS CLEAR" in ctrl.lbl_qa_watchlist_impact.text()


def test_sticky_date_ribbon_and_alternating_colors(qapp):
    """Bug 3 & Bug 7: Verifies sticky date header ribbon and alternating table rows."""
    win = QMainWindow()
    win.tabWidget = QTabWidget()
    win.setCentralWidget(win.tabWidget)
    ctrl = MacroCalendarController(win)

    # 1. Sticky ribbon exists and is pinned above table
    assert hasattr(ctrl, "lbl_sticky_date")
    assert ctrl.lbl_sticky_date is not None
    assert "ACTIVE VIEW" in ctrl.lbl_sticky_date.text()

    # 2. Alternating row colors enabled on calendar table
    assert ctrl.table.alternatingRowColors() is True

    # 3. Dynamic scroll updates sticky ribbon date
    ctrl._raw_events = [
        {"time": "22/10 19:30", "sort_key": 1792450000.0, "country": "US", "title": "Jobless Claims", "impact": 2},
        {"time": "23/10 20:00", "sort_key": 1792536400.0, "country": "US", "title": "Flash PMI", "impact": 2},
    ]
    ctrl.load_calendar()
    ctrl._on_table_scroll(0)
    assert ctrl.lbl_sticky_date.text() != ""
    assert "ACTIVE VIEW" in ctrl.lbl_sticky_date.text()


def test_quant_action_card_badges_and_asset_labels(qapp):
    """Bug 4 & Bug 5: Verifies tag badges, removal of Python None, and clean ticker without (GOLD)."""
    win = QMainWindow()
    win.tabWidget = QTabWidget()
    win.setCentralWidget(win.tabWidget)
    ctrl = MacroCalendarController(win)

    # Mock active watchlist symbols
    ctrl._get_watchlist_symbols = MagicMock(return_value=["XAUUSD", "EURUSD", "GBPUSD"])

    # 1. Affected assets in defense desk should not contain "(GOLD)"
    desk_assets = ctrl.lbl_desk_assets.text()
    assert "(GOLD)" not in desk_assets

    # 2. Quant action card formats watchlist as clean badges
    event = {
        "country": "US",
        "title": "Non-Farm Employment Change",
        "impact": 2,
        "actual": "250K",
        "forecast": "180K",
        "surprise": 70.0,
    }
    ctrl._update_quant_action_card(event)

    wl_text = ctrl.lbl_qa_watchlist_impact.text()
    assert "• WATCHLIST EXPOSURE:" in wl_text
    assert "[XAUUSD]" in wl_text
    assert "· T-15M LOCK" in wl_text
    assert "None" not in wl_text
    assert "Cặp an toàn (0): None" not in wl_text


def test_header_view_menu_focus_policy(qapp):
    """Bug 6: Verifies QMenuBar focus policy is Qt.NoFocus to prevent persistent focus borders."""
    win = QMainWindow()
    win.menuBar = QMenuBar()
    hdr = HeaderController(win)
    if hasattr(hdr, "native_mb") and hdr.native_mb:
        assert hdr.native_mb.focusPolicy() == Qt.NoFocus


def test_dotted_leader_line_in_event_column(qapp):
    """Bug 7: Verifies Column 3 creates a dotted leader line spanning dead space."""
    win = QMainWindow()
    win.tabWidget = QTabWidget()
    win.setCentralWidget(win.tabWidget)
    ctrl = MacroCalendarController(win)

    ctrl._raw_events = [
        {"time": "22/10 19:30", "sort_key": 1792450000.0, "country": "US", "title": "Jobless Claims", "impact": 2},
    ]
    ctrl.load_calendar()

    # Row 0 is Date separator, Row 1 is Event
    cell_widget = ctrl.table.cellWidget(1, 3)
    assert cell_widget is not None
    # Cell widget layout contains label and dotted line frame (not QLabel)
    dotted_frames = [f for f in cell_widget.findChildren(QFrame) if not isinstance(f, QLabel) and "dotted" in f.styleSheet().lower()]
    assert len(dotted_frames) >= 1
