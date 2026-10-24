"""
Unit tests verifying Weekend Session Filtering, Spread Warning Throttling, and Thread Teardown Safety.
"""

from unittest.mock import MagicMock, patch
import pytest

from backend.core.session_filter import SessionFilter
from backend.core.bot_orchestrator import BotOrchestrator
from frontend.controllers.chart.ai_panel_controller import AIAnalyzerThread
from frontend.widgets.splash_screen import InitWorker


def test_weekend_session_filter_blocks_forex_and_gold():
    """Verifies that non-crypto assets (XAUUSD, EURUSD, US30) are blocked on weekends."""
    sf = SessionFilter(allowed_sessions=["ASIAN", "LONDON", "NY"], close_friday=True)

    with patch("backend.core.session_filter.datetime") as mock_dt:
        # Case A: Saturday at 13:45 UTC (reproducing user scenario)
        sat = MagicMock()
        sat.weekday.return_value = 5  # Saturday
        sat.hour = 13
        mock_dt.now.return_value = sat

        allowed, reason = sf.is_session_allowed(symbol="XAUUSD")
        assert allowed is False
        assert reason == "WEEKEND_CLOSED"

        # Case B: Sunday at 15:00 UTC (still closed before Sydney session open)
        sun_early = MagicMock()
        sun_early.weekday.return_value = 6  # Sunday
        sun_early.hour = 15
        mock_dt.now.return_value = sun_early

        allowed_sun, reason_sun = sf.is_session_allowed(symbol="XAUUSD")
        assert allowed_sun is False
        assert reason_sun == "WEEKEND_CLOSED"

        # Case C: Sunday at 22:30 UTC (Sydney opens -> Asian session active)
        sun_open = MagicMock()
        sun_open.weekday.return_value = 6  # Sunday
        sun_open.hour = 22
        mock_dt.now.return_value = sun_open

        allowed_open, reason_open = sf.is_session_allowed(symbol="XAUUSD")
        assert allowed_open is True
        assert reason_open == "ASIAN"

        # Case D: Friday at 21:30 UTC -> FRIDAY_EOD
        fri_eod = MagicMock()
        fri_eod.weekday.return_value = 4  # Friday
        fri_eod.hour = 21
        mock_dt.now.return_value = fri_eod

        allowed_fri, reason_fri = sf.is_session_allowed(symbol="XAUUSD")
        assert allowed_fri is False
        assert reason_fri == "FRIDAY_EOD"


def test_crypto_24_7_exempt_from_weekend_closure():
    """Verifies that Crypto assets (BTCUSD) trade 24/7 and are completely exempt from weekend closure."""
    sf = SessionFilter(allowed_sessions=["LONDON"], close_friday=True)

    with patch("backend.core.session_filter.datetime") as mock_dt:
        sat = MagicMock()
        sat.weekday.return_value = 5  # Saturday
        sat.hour = 14
        mock_dt.now.return_value = sat

        allowed_btc, reason_btc = sf.is_session_allowed(symbol="BTCUSD")
        assert allowed_btc is True
        assert reason_btc == "CRYPTO_24_7"


def test_spread_warning_throttling():
    """Verifies that SPREAD EXPANDED warnings are throttled to at most once every 60s per asset."""
    bot = BotOrchestrator(
        strategy=MagicMock(),
        risk_manager=MagicMock(),
        execution_manager=MagicMock(),
        data_preprocessor=MagicMock(),
        decision_gate=MagicMock(),
        symbols=["XAUUSD"],
    )
    bot.trade_mode = "BUY_SELL"

    logged_warnings = []
    bot.log = lambda level, msg, color="#8B949E": logged_warnings.append(msg) if level == "WARNING" else None

    # Mock state recovery, circuit guard, session allowed
    bot.state_recovery.can_open_new_trade = MagicMock(return_value=True)
    bot.circuit_guard.circuit_breaker_active = False
    bot._check_session_allowed = MagicMock(return_value=(True, "LONDON"))

    # Mock spread expanded (spread_ok = False)
    bot.event_risk.check_news_impact_for_symbol = MagicMock(return_value=(False, ""))
    bot.event_risk.check_spread_normalization = MagicMock(return_value=(False, 150, 25))

    # First call: should log warning
    bot.pipeline_execute("XAUUSD")
    assert len(logged_warnings) == 1
    assert "SPREAD EXPANDED [XAUUSD]" in logged_warnings[0]

    # Subsequent call immediately after (e.g. 1 second later): MUST be throttled
    bot.pipeline_execute("XAUUSD")
    bot.pipeline_execute("XAUUSD")
    assert len(logged_warnings) == 1  # Still 1, 0 spam

    # Simulate spread normalizing: clears throttle timestamp
    bot.event_risk.check_spread_normalization = MagicMock(return_value=(True, 15, 25))
    with patch("backend.infrastructure.brokers.mt5_safe.mt5.copy_rates_from_pos", return_value=None):
        bot.pipeline_execute("XAUUSD")
    assert "XAUUSD" not in bot._last_spread_warning_ts


def test_bot_orchestrator_stop_wakes_worker():
    """Verifies that calling stop() sets is_running False and triggers immediate wake-up event."""
    bot = BotOrchestrator(
        strategy=MagicMock(),
        risk_manager=MagicMock(),
        execution_manager=MagicMock(),
        data_preprocessor=MagicMock(),
        decision_gate=MagicMock(),
        symbols=["XAUUSD"],
    )

    bot.is_running = True
    assert bot._wake_event.is_set() is False

    with patch("backend.infrastructure.notifications.telegram_notifier.telegram_notifier.send_message"):
        bot.stop()

    assert bot.is_running is False
    assert bot._wake_event.is_set() is True


def test_thread_object_names_assigned():
    """Verifies that QThread subclasses have explicit objectName set for transparent debugging."""
    ai_t = AIAnalyzerThread(sym="XAUUSD")
    assert ai_t.objectName() == "AIAnalyzerThread_XAUUSD"

    init_w = InitWorker()
    assert init_w.objectName() == "InitWorkerThread"
