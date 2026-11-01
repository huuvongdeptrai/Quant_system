"""
Unit Tests for Phase 1: Order Ownership, Magic Number Isolation, and Guard Conflict Resolution.
Covers:
- SC-01: PositionGuard skips manual trades (magic=0 or 'manual' comment), preserving user's manual SL.
- SC-02: CircuitBreakerGuard excludes manual losing deals from the automated bot losing streak.
- SC-06: ExecutionManager.close_all_positions(symbol, bot_only=True) protects discretionary positions.
- SC-10: Manual order routing assigns magic=0 and isolates discretionary execution.
"""

from unittest.mock import MagicMock, patch
import pytest

from backend.core.position_guard import PositionGuard
from backend.core.circuit_breaker_guard import CircuitBreakerGuard
from backend.infrastructure.brokers.execution_manager import ExecutionManager


class DummyPosition:
    def __init__(self, ticket, symbol, p_type, price_open, price_current, sl, tp, magic=999999, comment="VECTRA"):
        self.ticket = ticket
        self.symbol = symbol
        self.type = p_type  # 0 = BUY, 1 = SELL
        self.price_open = price_open
        self.price_current = price_current
        self.sl = sl
        self.tp = tp
        self.volume = 0.1
        self.magic = magic
        self.comment = comment


class DummyDeal:
    def __init__(self, ticket, entry, profit, commission, swap, magic=999999, comment="VECTRA"):
        self.ticket = ticket
        self.position_id = ticket
        self.entry = entry  # 1 = EXIT
        self.profit = profit
        self.commission = commission
        self.swap = swap
        self.fee = 0.0
        self.time = ticket
        self.price = 2650.0
        self.magic = magic
        self.comment = comment


# ============================================================================
# SC-01 TESTS: PositionGuard Trailing Stop Isolation
# ============================================================================

def test_position_guard_skips_manual_position():
    """SC-01: PositionGuard must NOT modify SL for manual positions (magic=0 or comment containing 'manual')."""
    mock_exec = MagicMock()
    mock_db = MagicMock()
    guard = PositionGuard(
        execution_manager=mock_exec,
        db_manager=mock_db,
        enable_trailing_stop=True,
        trailing_pips=10,
        breakeven_pips=5,
        bot_magic=999999,
    )

    # Position 1: Bot position (magic=999999, comment="VECTRA")
    bot_pos = DummyPosition(
        ticket=1001, symbol="XAUUSD", p_type=0, price_open=2650.0, price_current=2670.0, sl=2640.0, tp=2700.0, magic=999999, comment="VECTRA"
    )
    # Position 2: User manual position (magic=0, comment="VECTRA_Manual")
    manual_pos = DummyPosition(
        ticket=1002, symbol="XAUUSD", p_type=0, price_open=2650.0, price_current=2670.0, sl=2645.0, tp=2700.0, magic=0, comment="VECTRA_Manual"
    )

    mock_info = MagicMock()
    mock_info.point = 0.01

    with patch("backend.core.position_guard.mt5.positions_get", return_value=[bot_pos, manual_pos]), \
         patch("backend.core.position_guard.mt5.symbol_info", return_value=mock_info), \
         patch("backend.core.position_guard.mt5.order_send") as mock_order_send:

        mock_res = MagicMock()
        mock_res.retcode = 10009  # TRADE_RETCODE_DONE
        mock_order_send.return_value = mock_res

        guard._apply_trailing_for_symbol("XAUUSD")

        # Verify that order_send was called ONLY for ticket 1001 (bot_pos), NOT for 1002 (manual_pos)
        assert mock_order_send.called
        tickets_trailed = [call.args[0]["position"] for call in mock_order_send.call_args_list]
        assert 1001 in tickets_trailed
        assert 1002 not in tickets_trailed


# ============================================================================
# SC-02 TESTS: CircuitBreakerGuard Losing Streak Isolation
# ============================================================================

def test_circuit_breaker_ignores_manual_losing_deals():
    """SC-02: Losing deals from manual trades (magic=0 or comment='manual') must NOT trip bot losing streak."""
    mock_db = MagicMock()
    cb_guard = CircuitBreakerGuard(
        db_manager=mock_db,
        max_losing_streak=3,
        bot_magic=999999,
    )

    # 3 manual losing deals
    manual_deal1 = DummyDeal(ticket=1, entry=1, profit=-50.0, commission=-2.0, swap=0.0, magic=0, comment="VECTRA_Manual")
    manual_deal2 = DummyDeal(ticket=2, entry=1, profit=-30.0, commission=-2.0, swap=0.0, magic=0, comment="VECTRA_Manual")
    manual_deal3 = DummyDeal(ticket=3, entry=1, profit=-40.0, commission=-2.0, swap=0.0, magic=0, comment="VECTRA_Manual")

    # 1 bot winning deal
    bot_deal1 = DummyDeal(ticket=4, entry=1, profit=100.0, commission=-2.0, swap=0.0, magic=999999, comment="VECTRA")

    with patch("backend.core.circuit_breaker_guard.mt5.positions_get", return_value=()), patch("backend.core.circuit_breaker_guard.mt5.history_deals_get", side_effect=position_history([manual_deal1, manual_deal2, manual_deal3, bot_deal1])):
        triggered, streak = cb_guard.check_losing_streak()
        # Even though there are 3 consecutive manual losses, the bot has 0 losses!
        assert not triggered
        assert streak == 0


def test_circuit_breaker_triggers_only_on_bot_losing_deals():
    """SC-02: When bot deals reach max_losing_streak, it triggers properly."""
    mock_db = MagicMock()
    cb_guard = CircuitBreakerGuard(
        db_manager=mock_db,
        max_losing_streak=3,
        bot_magic=999999,
    )

    # 3 bot losing deals
    b1 = DummyDeal(ticket=1, entry=1, profit=-50.0, commission=-2.0, swap=0.0, magic=999999, comment="VECTRA")
    b2 = DummyDeal(ticket=2, entry=1, profit=-30.0, commission=-2.0, swap=0.0, magic=999999, comment="VECTRA")
    b3 = DummyDeal(ticket=3, entry=1, profit=-40.0, commission=-2.0, swap=0.0, magic=999999, comment="VECTRA")

    with patch("backend.core.circuit_breaker_guard.mt5.positions_get", return_value=()), patch("backend.core.circuit_breaker_guard.mt5.history_deals_get", side_effect=position_history([b1, b2, b3])):
        triggered, streak = cb_guard.check_losing_streak()
        assert triggered
        assert streak == 3


# ============================================================================
# SC-06 TESTS: ExecutionManager Close All Scoping
# ============================================================================

def test_close_all_positions_bot_only_protects_manual_positions():
    """SC-06: close_all_positions with bot_only=True must not close manual positions."""
    exec_mgr = ExecutionManager(magic_number=999999)

    bot_pos = DummyPosition(ticket=2001, symbol="EURUSD", p_type=0, price_open=1.0800, price_current=1.0850, sl=1.0750, tp=1.0900, magic=999999, comment="VECTRA")
    manual_pos = DummyPosition(ticket=2002, symbol="EURUSD", p_type=0, price_open=1.0810, price_current=1.0850, sl=1.0750, tp=1.0900, magic=0, comment="VECTRA_Manual")

    mock_info = MagicMock()
    mock_info.digits = 5
    mock_info.filling_mode = 1

    mock_tick = MagicMock()
    mock_tick.bid = 1.0850
    mock_tick.ask = 1.0852

    mock_res = MagicMock()
    mock_res.retcode = 10009  # TRADE_RETCODE_DONE

    with patch("backend.infrastructure.brokers.execution_manager.mt5.positions_get", return_value=[bot_pos, manual_pos]), \
         patch("backend.infrastructure.brokers.execution_manager.mt5.symbol_info", return_value=mock_info), \
         patch("backend.infrastructure.brokers.execution_manager.mt5.symbol_info_tick", return_value=mock_tick), \
         patch("backend.infrastructure.brokers.execution_manager.mt5.order_send", return_value=mock_res) as mock_send:

        # 1. bot_only=True (default)
        res = exec_mgr.close_all_positions("EURUSD", bot_only=True)
        assert len(res) == 1
        assert "2001" in res[0]
        # Verify order_send was called only once for ticket 2001
        assert mock_send.call_count == 1
        assert mock_send.call_args[0][0]["position"] == 2001

    # 2. bot_only=False (full liquidation on symbol)
    with patch("backend.infrastructure.brokers.execution_manager.mt5.positions_get", return_value=[bot_pos, manual_pos]), \
         patch("backend.infrastructure.brokers.execution_manager.mt5.symbol_info", return_value=mock_info), \
         patch("backend.infrastructure.brokers.execution_manager.mt5.symbol_info_tick", return_value=mock_tick), \
         patch("backend.infrastructure.brokers.execution_manager.mt5.order_send", return_value=mock_res) as mock_send:

        res = exec_mgr.close_all_positions("EURUSD", bot_only=False)
        assert len(res) == 2
        assert mock_send.call_count == 2


# ============================================================================
# SC-10 TESTS: Manual Order Execution Routing
# ============================================================================

def test_manual_order_execution_assigns_magic_zero():
    """SC-10: execute_market_order with comment containing 'manual' or magic=0 assigns magic=0."""
    exec_mgr = ExecutionManager(magic_number=999999)

    mock_terminal = MagicMock()
    mock_terminal.trade_allowed = True

    mock_info = MagicMock()
    mock_info.digits = 2
    mock_info.point = 0.01
    mock_info.filling_mode = 1
    mock_info.trade_stops_level = 0

    mock_tick = MagicMock()
    mock_tick.ask = 2650.0
    mock_tick.bid = 2649.5

    mock_res = MagicMock()
    mock_res.retcode = 10009
    mock_res.order = 3001
    mock_res.price = 2650.0

    with patch("backend.infrastructure.brokers.execution_manager.mt5.terminal_info", return_value=mock_terminal), \
         patch("backend.infrastructure.brokers.execution_manager.mt5.symbol_select", return_value=True), \
         patch("backend.infrastructure.brokers.execution_manager.mt5.symbol_info", return_value=mock_info), \
         patch("backend.infrastructure.brokers.execution_manager.mt5.symbol_info_tick", return_value=mock_tick), \
         patch("backend.infrastructure.brokers.execution_manager.mt5.order_send", return_value=mock_res) as mock_send:

        # Case A: Explicit magic=0
        exec_mgr._execute_market_order_raw(
            symbol="XAUUSD",
            is_buy=True,
            volume=0.1,
            sl_price=2640.0,
            tp_price=2670.0,
            comment="VECTRA_Manual",
            magic=0
        )
        assert mock_send.call_args[0][0]["magic"] == 0

        # Case B: comment contains 'manual' without explicit magic
        exec_mgr._execute_market_order_raw(
            symbol="XAUUSD",
            is_buy=True,
            volume=0.1,
            sl_price=2640.0,
            tp_price=2670.0,
            comment="VECTRA_Manual"
        )
        assert mock_send.call_args[0][0]["magic"] == 0

        # Case C: Automated bot order uses exec_mgr.magic (999999)
        exec_mgr._execute_market_order_raw(
            symbol="XAUUSD",
            is_buy=True,
            volume=0.1,
            sl_price=2640.0,
            tp_price=2670.0,
            comment="ICT_Strategy"
        )
        assert mock_send.call_args[0][0]["magic"] == 999999


def position_history(exits):
    def get(*args, **kwargs):
        if "position" not in kwargs:
            return exits
        d = next(d for d in exits if d.position_id == kwargs["position"])
        opening = DummyDeal(d.ticket, 0, 0, -1, 0, magic=d.magic, comment=d.comment)
        return [opening, d]
    return get
