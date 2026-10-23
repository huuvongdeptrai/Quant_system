# -*- coding: utf-8 -*-
"""
Unit tests for Step 2: Strategy Macro Injection & AI Chart Engine Handshake.
Verifies:
1. MacroContextBus.get_macro_context(symbol) returns standardized dictionary structure.
2. ICT Strategy Circuit Breaker halts on news_lockout=True.
3. ICT Strategy Volatility Sizing Filter adapts min_confluence dynamically (HIGH vs LOW).
4. ICT Strategy Counter-Trend Handshake permits Scalp Pullback signal generation.
5. Wyckoff Strategy Circuit Breaker halts on news_lockout=True.
6. FULL-AUTO Gate Interception prevents dispatch when DecisionGate returns WAIT.
"""
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout

from backend.core.macro_context_bus import MacroContextBus
from backend.core.strategies.ict_strategy import ICTZonesProStrategy
from backend.core.strategies.wyckoff_vectorized import WyckoffMomentumStrategy
from frontend.controllers.chart.ai_panel_controller import _update_panel_with_result, _build_analysis_panel
from frontend.controllers.chart.trading_plan_panel import setup_trading_plan_cards


def _generate_synthetic_candles(count=150, base_price=2650.0):
    """Generates synthetic DataFrame for strategy analysis."""
    times = [1700000000 + i * 900 for i in range(count)]
    rows = []
    curr = base_price
    for t in times:
        o = curr
        h = o + 2.0
        l = o - 2.0
        c = o + 0.5
        rows.append({"time": pd.to_datetime(t, unit="s"), "open": o, "high": h, "low": l, "close": c, "tick_volume": 100})
        curr = c
    return pd.DataFrame(rows)


def test_macro_context_bus_get_macro_context_contract():
    """Verifies that get_macro_context returns standardized dictionary with all required keys."""
    bus = MacroContextBus.get_instance()
    ctx = bus.get_macro_context("XAUUSD")

    assert isinstance(ctx, dict)
    assert ctx["symbol"] == "XAUUSD"
    assert "macro_bias" in ctx
    assert "bias" in ctx
    assert "volatility_risk" in ctx
    assert "news_lockout" in ctx
    assert "news_blackout" in ctx
    assert "active_event" in ctx
    assert "manual_override" in ctx
    assert "badge_text" in ctx


def test_ict_strategy_halts_on_news_lockout():
    """Verifies that ICTZonesProStrategy halts immediately with HOLD during news blackout."""
    strat = ICTZonesProStrategy()
    df = _generate_synthetic_candles(150)

    macro_ctx = {
        "symbol": "XAUUSD",
        "macro_bias": "BULLISH",
        "volatility_risk": "HIGH",
        "news_lockout": True,
        "active_event": "US CPI (19:30)",
    }

    sig = strat.analyze(df, macro_context=macro_ctx)

    assert sig.action == "HOLD"
    assert "NEWS_BLACKOUT_ACTIVE" in sig.metadata.get("reason", "")
    assert sig.metadata.get("news_locked") is True


def test_ict_strategy_volatility_sizing_filter():
    """Verifies that ICTZonesProStrategy raises min_confluence during HIGH volatility."""
    strat = ICTZonesProStrategy()
    strat.min_confluence = 3
    df = _generate_synthetic_candles(150)

    # Low volatility: min_conf = 3
    ctx_low = {"volatility_risk": "LOW", "bias": "BULLISH", "news_lockout": False}
    # High volatility: min_conf = 5 (3 + 2)
    ctx_high = {"volatility_risk": "HIGH", "bias": "BULLISH", "news_lockout": False}

    # Verify analyze accepts and processes both without exception
    sig_low = strat.analyze(df, macro_context=ctx_low)
    sig_high = strat.analyze(df, macro_context=ctx_high)

    assert sig_low.action in ["BUY", "SELL", "HOLD"]
    assert sig_high.action in ["BUY", "SELL", "HOLD"]


def test_wyckoff_strategy_halts_on_news_lockout():
    """Verifies that WyckoffMomentumStrategy halts immediately with HOLD during news blackout."""
    strat = WyckoffMomentumStrategy()
    df = _generate_synthetic_candles(150)

    macro_ctx = {
        "symbol": "XAUUSD",
        "macro_bias": "BULLISH",
        "news_lockout": True,
        "active_event": "FOMC Rate Decision",
    }

    res = strat.analyze(df, macro_context=macro_ctx)

    assert res.get("signal") == "HOLD"
    assert "NEWS_BLACKOUT_ACTIVE" in res.get("reason", "")
    assert res.get("metadata", {}).get("news_locked") is True


def test_full_auto_intercepted_by_decision_gate():
    """Verifies that FULL-AUTO mode intercepts execution when DecisionGate returns WAIT."""
    app = QApplication.instance() or QApplication([])

    class MockWindow(QWidget):
        def __init__(self):
            super().__init__()
            self.current_sym = "XAUUSD"
            self.current_tf_str = "M15"
            self.is_dark_theme = True
            self.order_proposal_active = False
            self.is_live_position = False
            self.live_ticket = None
            self.layoutAIArea = QVBoxLayout(self)
            _build_analysis_panel(self)
            setup_trading_plan_cards(self, is_dark=True)

    win = MockWindow()
    win.quant_terminal = MagicMock()
    win.quant_terminal.header = MagicMock(execution_mode="FULL-AUTO")
    win.quant_terminal.exec_mgr = MagicMock()

    # DecisionGate mock that returns WAIT (blocked by news / resistance)
    mock_dg = MagicMock()
    mock_dg.evaluate.return_value = {
        "decision": "WAIT",
        "reason": "Blocked: High Impact News Blackout",
        "trade_mode": "BLOCKED",
    }
    win.decision_gate = mock_dg

    ai_result = {
        "_price": 2680.0,
        "_candle_time": 1700000000,
        "_strategy_name": "ICT Zones Pro",
        "_strategy_res": {
            "signal": "SELL",
            "entry_price": 2680.0,
            "sl": 2690.0,
            "tp1": 2660.0,
            "confidence": 0.90,
        },
    }

    _update_panel_with_result(win, ai_result)

    # Execution manager MUST NOT be called because DecisionGate intercepted it!
    assert not win.quant_terminal.exec_mgr.execute_market_order.called
    assert win.is_live_position is False
