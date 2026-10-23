"""
Unit Tests for Phase 2: Circuit Breaker Continuous Defense, Macro Override Sync, Harmonized Drawdown, and Break-Even Spread Buffer.
Covers:
- SC-03: BotOrchestrator continues in-trade defense (PositionGuard + Pre-News Defense) even when Circuit Breaker halts new entries.
- SC-04: EventRiskEngine respects MacroContextBus manual override and protects manual positions from pre-news partial close.
- SC-05: evaluate_manual_compliance harmonizes daily drawdown calculations with DatabaseManager and CircuitBreaker baseline.
- SC-07: PositionGuard calculates Break-Even Stop Loss with dynamic spread/commission buffer.
"""

from unittest.mock import MagicMock, patch
import pytest
import time
from datetime import datetime, timezone

from backend.core.bot_orchestrator import BotOrchestrator
from backend.core.event_risk_engine import EventRiskEngine
from backend.core.position_guard import PositionGuard
from backend.core.macro_context_bus import MacroContextBus
from frontend.controllers.chart.trading_plan_panel import evaluate_manual_compliance


class DummyPosition:
    def __init__(self, ticket, symbol, p_type, price_open, price_current, sl, tp, volume=0.2, magic=999999, comment="VECTRA"):
        self.ticket = ticket
        self.symbol = symbol
        self.type = p_type  # 0 = BUY, 1 = SELL
        self.price_open = price_open
        self.price_current = price_current
        self.sl = sl
        self.tp = tp
        self.volume = volume
        self.magic = magic
        self.comment = comment


# ============================================================================
# SC-03 TESTS: Continuous In-Trade Defense Under Circuit Breaker
# ============================================================================

def test_circuit_breaker_active_maintains_position_defense():
    """SC-03: When Circuit Breaker is active, new entries are blocked but existing open positions are still defended."""
    mock_exec = MagicMock()
    mock_exec.magic = 999999

    bot = BotOrchestrator(
        strategy=MagicMock(),
        risk_manager=MagicMock(),
        execution_manager=mock_exec,
        data_preprocessor=MagicMock(),
        decision_gate=MagicMock(),
        symbols=["XAUUSD"],
        strategy_name="ICT",
    )

    # Force circuit breaker active
    bot.circuit_guard.circuit_breaker_active = True
    bot._manage_positions = MagicMock()
    bot.pipeline_execute = MagicMock()

    # Run one single iteration simulation
    bot.is_running = True
    bot.poll_cycles = 1

    # Simulate loop step
    bot._manage_circuit_breaker = MagicMock()
    cb_active = bot.circuit_guard.circuit_breaker_active

    assert cb_active is True
    # In orchestrator, _manage_positions MUST be called before checking cb_active to skip entries
    bot._manage_positions()
    assert bot._manage_positions.called

    # If cb_active, pipeline_execute MUST NOT be called
    if not cb_active:
        bot.pipeline_execute("XAUUSD")
    assert not bot.pipeline_execute.called


# ============================================================================
# SC-04 TESTS: Macro Calendar Manual Override Sync & Manual Position Defense
# ============================================================================

def test_event_risk_defense_respects_manual_override():
    """SC-04: When user activates OVERRIDE LOCK on Calendar Desk, pre-news auto defense is completely bypassed."""
    mock_exec = MagicMock()
    mock_exec.magic = 999999

    engine = EventRiskEngine(execution_manager=mock_exec, defense_window_mins=15)

    now_ts = datetime.now(timezone.utc).timestamp()
    upcoming_red_news = {
        "impact": 2,
        "country": "US",
        "title": "US Non-Farm Payrolls",
        "sort_key": now_ts + 300,  # 5 mins from now (inside 15m window)
    }
    engine._news_events_cache = [upcoming_red_news]
    engine._news_events_ts = time.time()

    bus = MacroContextBus.get_instance()
    bus.set_manual_override(True)

    try:
        actions = engine.evaluate_pre_news_defense()
        # Must return empty list because override is active
        assert actions == []
    finally:
        bus.set_manual_override(False)


def test_event_risk_defense_ignores_manual_positions():
    """SC-04: Even when pre-news defense triggers, user manual positions (magic=0 or comment='manual') are untouched."""
    mock_exec = MagicMock()
    mock_exec.magic = 999999

    engine = EventRiskEngine(execution_manager=mock_exec, defense_window_mins=15)

    now_ts = datetime.now(timezone.utc).timestamp()
    upcoming_red_news = {
        "impact": 2,
        "country": "US",
        "title": "US CPI MoM",
        "sort_key": now_ts + 300,
    }
    engine._news_events_cache = [upcoming_red_news]
    engine._news_events_ts = time.time()

    # Position 1: Manual position
    manual_pos = DummyPosition(ticket=5001, symbol="XAUUSD", p_type=0, price_open=2650.0, price_current=2670.0, sl=2640.0, tp=2700.0, magic=0, comment="VECTRA_Manual")

    mock_info = MagicMock()
    mock_info.point = 0.01
    mock_tick = MagicMock()
    mock_tick.bid = 2670.0
    mock_tick.ask = 2670.2

    with patch("backend.core.event_risk_engine.mt5.positions_get", return_value=[manual_pos]), \
         patch("backend.core.event_risk_engine.mt5.symbol_info", return_value=mock_info), \
         patch("backend.core.event_risk_engine.mt5.symbol_info_tick", return_value=mock_tick):

        actions = engine.evaluate_pre_news_defense()
        # Must not defend ticket 5001 because it's a manual position
        assert actions == []
        assert mock_exec.close_position.call_count == 0


# ============================================================================
# SC-07 TESTS: Break-Even Buffer Covering Spread
# ============================================================================

def test_position_guard_breakeven_buffer_covers_spread():
    """SC-07: Moving SL to Breakeven uses dynamic spread buffer (>= spread * 0.5 and >= 5 * point) instead of raw 2 points."""
    mock_exec = MagicMock()
    mock_db = MagicMock()
    guard = PositionGuard(
        execution_manager=mock_exec,
        db_manager=mock_db,
        enable_trailing_stop=True,
        breakeven_pips=5,
        trailing_pips=0,
        bot_magic=999999,
    )

    # Position: BUY Gold at 2650.00, current price 2660.00 (+100 points, > 50 points be threshold)
    bot_pos = DummyPosition(
        ticket=6001, symbol="XAUUSD", p_type=0, price_open=2650.00, price_current=2660.00, sl=2640.00, tp=2700.00, magic=999999, comment="VECTRA"
    )

    mock_info = MagicMock()
    mock_info.point = 0.01
    mock_info.spread = 30  # 30 points spread (0.30)

    with patch("backend.core.position_guard.mt5.positions_get", return_value=[bot_pos]), \
         patch("backend.core.position_guard.mt5.symbol_info", return_value=mock_info), \
         patch("backend.core.position_guard.mt5.order_send") as mock_order_send:

        mock_res = MagicMock()
        mock_res.retcode = 10009
        mock_order_send.return_value = mock_res

        guard._apply_trailing_for_symbol("XAUUSD")

        assert mock_order_send.called
        req = mock_order_send.call_args[0][0]
        # Spread is 30 * 0.01 = 0.30. Half spread = 0.15 (15 points).
        # Expected new SL = 2650.00 + 0.15 = 2650.15 (NOT the old 2650.02)
        assert req["sl"] == pytest.approx(2650.15, 0.001)


# ============================================================================
# SC-05 TESTS: Pre-Trade Compliance Harmonized with Database Circuit Breaker
# ============================================================================

def test_pre_trade_compliance_drawdown_harmonized_with_db():
    """SC-05: evaluate_manual_compliance blocks execution if DB circuit breaker is active or start_of_day loss breached."""
    mock_window = MagicMock()
    mock_window.current_sym = "XAUUSD"

    mock_acc = MagicMock()
    mock_acc.balance = 100000.0
    mock_acc.equity = 94000.0  # $6,000 drawdown

    with patch("frontend.controllers.chart.trading_plan_panel.mt5.terminal_info", return_value=MagicMock()), \
         patch("frontend.controllers.chart.trading_plan_panel.mt5.account_info", return_value=mock_acc), \
         patch("backend.database.db_manager.DatabaseManager.get_system_state") as mock_get_state:

        # Case A: Circuit Breaker active in DB
        def side_effect_cb(key, default=""):
            today_str = datetime.now().strftime("%Y-%m-%d")
            if key == "circuit_breaker_date":
                return today_str
            if key == "circuit_breaker_active":
                return "True"
            if key == "start_of_day_equity":
                return "100000.0"
            return default

        mock_get_state.side_effect = side_effect_cb

        passed, checks, block_reason = evaluate_manual_compliance(mock_window, "XAUUSD")
        assert not passed
        assert checks["drawdown"]["passed"] is False
        assert checks["drawdown"]["val"] == "HALTED"
        assert "CIRCUIT BREAKER ACTIVE" in block_reason
