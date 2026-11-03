"""
Test Suite: Calendar Event Risk Targeting & Multi-Asset News Isolation
=======================================================================
Verifies:
1. An upcoming AU event (RBA Rate Decision) does NOT block Gold (XAUUSD) trading.
2. News events far away (> 15m) do NOT arm T-15M lockout.
3. Tab Calendar right desk accurately badges foreign domestic events as UNEXPOSED for XAUUSD.
4. MacroContextBus.check_pre_trade_news_compliance evaluates ground truth without false stale locks.
5. All-day general political/holiday events (e.g. Midterm Elections) do not trigger execution blackouts.
"""

import time
import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from backend.infrastructure.data_providers.macro.calendar_engine import CalendarEngine
from backend.core.event_risk_engine import EventRiskEngine
from backend.core.macro_context_bus import MacroContextBus, SymbolMacroProfile
from frontend.controllers.macro_calendar_controller import MacroCalendarController
from frontend.controllers.chart.trading_plan_panel import evaluate_manual_compliance


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


@pytest.fixture
def calendar_ctrl(qapp):
    win = QMainWindow()
    win.tabWidget = QTabWidget()
    win.setCentralWidget(win.tabWidget)
    win.current_sym = "XAUUSD"
    ctrl = MacroCalendarController(win)
    return ctrl


def test_au_event_does_not_impact_gold():
    """Confirms that EventRiskEngine strictly isolates AUD events from XAUUSD."""
    ere = EventRiskEngine()
    assert ere.is_symbol_impacted_by_event("XAUUSD", "AU", "RBA Interest Rate Decision") is False
    assert ere.is_symbol_impacted_by_event("XAUUSD", "AU", "RBA Rate Statement") is False
    assert ere.is_symbol_impacted_by_event("XAUUSD", "US", "Core CPI MoM") is True
    assert ere.is_symbol_impacted_by_event("AUDUSD", "AU", "RBA Interest Rate Decision") is True


def test_far_away_news_does_not_block_trading():
    """Events occurring hours in advance must NOT block trading."""
    now_ts = time.time()
    ere = EventRiskEngine(pause_window_mins=30)
    ere._calendar_valid = True
    ere._news_events_ts = now_ts

    # Event 3 hours in the future
    ere._news_events_cache = [
        {"impact": 2, "country": "US", "sort_key": now_ts + 10800, "title": "FOMC Statement"}
    ]

    blocked, reason = ere.check_news_impact_for_symbol("XAUUSD")
    assert blocked is False
    assert reason == ""


def test_macro_context_bus_no_false_stale_lock():
    """MacroContextBus must NOT freeze trading when profile timestamp is uninitialized or > 120s."""
    bus = MacroContextBus.get_instance()
    bus.set_manual_override(False)

    # Set an uninitialized or aged profile
    prof = SymbolMacroProfile(
        symbol="XAUUSD",
        asset_class="COMMODITY_PRECIOUS",
        directional_bias="BULLISH",
        macro_regime="RECESSION",
        news_blackout=False,
        event_risk_level="LOW",
        next_event_title="",
        seconds_to_event=999999.0,
        manual_override_lock=False,
        force_defense_active=False,
        timestamp=0.0,  # Aged timestamp
    )
    bus.set_profile(prof)

    with patch.object(bus._event_risk_engine, "check_news_impact_for_symbol", return_value=(False, "")):
        cleared, status, msg = bus.check_pre_trade_news_compliance("XAUUSD")
        assert cleared is True
        assert status == "PASS"
        assert "Clear" in msg


def test_manual_compliance_evaluation_unlocked_for_gold():
    """Card M1 manual compliance must pass for XAUUSD when only foreign AU news is on the calendar."""
    win = QMainWindow()
    win.current_sym = "XAUUSD"

    bus = MacroContextBus.get_instance()
    bus.set_manual_override(False)

    # Direct real-time check returns clear for Gold
    with patch.object(bus._event_risk_engine, "check_news_impact_for_symbol", return_value=(False, "")):
        passed, checks, block_reason = evaluate_manual_compliance(win, "XAUUSD")
        assert checks["news"]["passed"] is True
        assert "NEWS BLACKOUT LOCK" not in block_reason


def test_calendar_desk_foreign_event_unexposed_display(calendar_ctrl):
    """Right desk Section 1 & 4 must clearly show UNEXPOSED (XAUUSD CLEAR) when viewing an AU event."""
    ctrl = calendar_ctrl
    ctrl.set_current_symbol("XAUUSD")

    au_event = {
        "country": "AU",
        "title": "RBA Interest Rate Decision",
        "impact": 2,
        "actual": "None",
        "forecast": "4.85",
        "previous": "4.6",
        "sort_key": time.time() + 7200,  # 2 hours away
    }
    ctrl._selected_event = au_event
    ctrl._update_defense_desk_display(au_event)

    # Badge must show UNEXPOSED
    assert "UNEXPOSED" in ctrl.badge_target_relevance.text()
    assert "XAUUSD" in ctrl.badge_target_relevance.text()

    # Status must show CLEAR
    assert "CLEAR" in ctrl.lbl_lockout_status.text()
    assert "ORDERS LOCKED" not in ctrl.lbl_lockout_status.text()

    # Action protocol must explicitly state UNEXPOSED
    assert "UNEXPOSED" in ctrl.lbl_qa_asset_impact.text()

    # Watchlist exposure must not say T-15M LOCK for event 2 hours away
    assert "T-15M LOCK ARMED" not in ctrl.lbl_qa_watchlist_impact.text()


def test_elections_demoted_from_spike_impact():
    """All-day events (elections, bank holidays) must be demoted so they don't trigger spike execution blackouts."""
    ce = CalendarEngine()
    assert ce.classify_impact(1, "US Midterm Elections", "US") == 0
    assert ce.classify_impact(1, "General Election", "NZ") == 0
    assert ce.classify_impact(1, "Bank Holiday", "GB") == 0
    # Core macroeconomic data must remain High Impact (Tier 2)
    assert ce.classify_impact(1, "CPI MoM", "US") == 2
    assert ce.classify_impact(1, "Non Farm Payrolls", "US") == 2
    assert ce.classify_impact(1, "Fed Interest Rate Decision", "US") == 2
