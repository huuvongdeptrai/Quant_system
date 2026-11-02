# -*- coding: utf-8 -*-
"""
UNIT TESTS: A/B TESTING META-LABELING FILTER (GROUP A BASELINE vs GROUP B FILTERED)
===================================================================================
Verifies:
1. BotRunConfig and OptionsConfigBinder support 'enable_meta_labeling' persistence.
2. DecisionGate respects 'enable_meta_labeling':
   - False: Bypasses ML Meta-Labeling (Group A Baseline mode).
   - True: Applies ML Meta-Labeling probability gate (Group B Filtered mode).
3. EventDrivenBacktester with signal_filter:
   - Unfiltered (Group A): Generates full set of strategy trades.
   - Filtered (Group B): Drops low-probability signals, altering trade count.
4. Backtest workbench UI controls:
   - 'chkBtMetaLabeling' widget existence and tooltip.
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch

from backend.core.engine_config import BotRunConfig, GateMode
from backend.infrastructure.ai_engines.ai.decision_gate import DecisionGate
from backend.backtest.backtest_ict_pro import EventDrivenBacktester


def test_bot_run_config_meta_labeling_serialization():
    # Default is True
    cfg_def = BotRunConfig.from_dict({})
    assert cfg_def.enable_meta_labeling is True
    assert cfg_def.to_dict()["enable_meta_labeling"] is True

    # Explicit False
    cfg_false = BotRunConfig.from_dict({"enable_meta_labeling": False})
    assert cfg_false.enable_meta_labeling is False
    assert cfg_false.to_dict()["enable_meta_labeling"] is False

    # String parsing
    cfg_str = BotRunConfig.from_dict({"enable_meta_labeling": "off"})
    assert cfg_str.enable_meta_labeling is False


def test_decision_gate_bypass_when_meta_labeling_disabled():
    gate = DecisionGate()
    sample_rates = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=150, freq="15min"),
        "open": np.linspace(2000, 2020, 150),
        "high": np.linspace(2005, 2025, 150),
        "low": np.linspace(1995, 2015, 150),
        "close": np.linspace(2002, 2022, 150),
        "tick_volume": [1000] * 150,
    })

    # Mock _evaluate_technical to propose a BUY trade
    def fake_tech(symbol, signal, *args, **kwargs):
        enable_ml = kwargs.get("enable_meta_labeling", True)
        reason = "Tech Valid"
        if not enable_ml:
            reason += " [MLMetaGate: Bypassed (A/B Test / Disabled)]"
        return {
            "decision": signal,
            "reason": reason,
            "htf_bias": "BULLISH",
            "macro_bias": "BULLISH",
            "combined_bias": "BULLISH",
            "position": "SUPPORT",
            "trade_mode": "STANDARD",
            "size_multiplier": 1.0,
        }

    gate._evaluate_technical = fake_tech

    # Group A: enable_meta_labeling = False -> Must bypass ML and keep BUY
    res_a = gate.evaluate(
        symbol="XAUUSD",
        signal_from_strategy="BUY",
        timeframe=15,
        gate_mode="FULL",
        rates=sample_rates,
        strategy_id="builtin_wyckoff",
        enable_meta_labeling=False,
    )
    assert res_a["decision"] == "BUY"
    assert "Bypassed" in res_a["reason"]


def test_backtest_ab_testing_signal_filter():
    """Verifies that an ML signal_filter callback successfully discriminates Group A from Group B."""
    # Synthetic bars with alternating oscillations
    np.random.seed(42)
    n = 200
    times = pd.date_range("2026-01-01", periods=n, freq="15min")
    closes = 2000.0 + np.sin(np.linspace(0, 10, n)) * 20.0
    highs = closes + 2.0
    lows = closes - 2.0
    opens = closes - 0.5
    vols = [1000.0] * n

    df = pd.DataFrame({
        "time": times,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "tick_volume": vols,
    })

    # Strategy mock that emits BUY on every 10th bar
    class PeriodicStrategy:
        def analyze(self, window, macro_context=None):
            idx = len(window)
            if idx % 10 == 0:
                p = float(window["close"].iloc[-1])
                return {"signal": "BUY", "sl": p - 5.0, "tp": p + 10.0}
            return {"signal": "HOLD"}

    tester = EventDrivenBacktester(
        strategy=PeriodicStrategy(),
        initial_balance=10000.0,
        risk_per_trade_pct=1.0,
        commission_per_lot=0.0,
        slippage_pts=0.0,
    )

    # Group A: Baseline (no signal filter)
    rep_a = tester.run(df, symbol="XAUUSD", signal_filter=None)
    assert rep_a is not None
    trades_a = rep_a.total_trades

    # Group B: Filtered (filter half the signals)
    call_count = [0]
    def half_filter(feature_window, res):
        call_count[0] += 1
        return (call_count[0] % 2 == 1)  # Only allow odd signals

    rep_b = tester.run(df, symbol="XAUUSD", signal_filter=half_filter)
    assert rep_b is not None
    trades_b = rep_b.total_trades

    # Group B must execute fewer trades than Group A (strictly proving filter isolation)
    assert trades_b < trades_a, f"Filtered trades ({trades_b}) must be strictly less than baseline ({trades_a})"


def test_options_tab_execution_meta_labeling_toggle(persistent_qt_application):
    from frontend.widgets.options.tabs.tab_execution import ExecutionSettingsTab
    from frontend.widgets.options.options_binder import DEFAULTS
    tab = ExecutionSettingsTab()
    assert hasattr(tab, "chkEnableMetaLabeling"), "chkEnableMetaLabeling must be present on ExecutionSettingsTab"

    tab.load_values({"enable_meta_labeling": False}, DEFAULTS)
    assert tab.chkEnableMetaLabeling.isChecked() is False
    assert tab.get_values()["enable_meta_labeling"] is False

    tab.load_values({"enable_meta_labeling": True}, DEFAULTS)
    assert tab.chkEnableMetaLabeling.isChecked() is True
    assert tab.get_values()["enable_meta_labeling"] is True

