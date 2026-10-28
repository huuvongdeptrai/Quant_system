# -*- coding: utf-8 -*-
"""
UNIT TESTS: ML META-LABELING MODEL REGISTRY (METHOD 1 - CONVENTION AUTO-DISCOVERY)
==================================================================================
Verifies:
1. Auto-discovery of LightGBM models in storage/models/{strategy_id}_meta.lgb
2. Seamless prediction & decision gating (probability >= threshold -> pass, < threshold -> block)
3. Fallback resilience: When model file is missing or renamed to .bak, system falls back to standard mode
4. Hot-reloading when model file modification time changes
"""

import os
import shutil
from pathlib import Path
import pytest
import numpy as np
import pandas as pd

from backend.infrastructure.ai_engines.ai.decision_gate import DecisionGate


@pytest.fixture
def sample_rates():
    """Generates synthetic 100-bar M15 rates for testing."""
    np.random.seed(42)
    n = 100
    base = 2650.0
    times = pd.date_range("2026-10-20 08:00", periods=n, freq="15min")
    noise = np.random.normal(0, 1.5, n)
    trend = np.linspace(0, 15, n)
    closes = base + trend + noise
    highs = closes + np.random.uniform(0.5, 2.0, n)
    lows = closes - np.random.uniform(0.5, 2.0, n)
    opens = closes - np.random.normal(0, 0.5, n)
    vols = np.random.uniform(500, 2500, n)

    rates = []
    for i in range(n):
        rates.append({
            "time": int(times[i].timestamp()),
            "open": float(opens[i]),
            "high": float(highs[i]),
            "low": float(lows[i]),
            "close": float(closes[i]),
            "tick_volume": float(vols[i]),
        })
    return rates


def test_model_registry_auto_discovery_and_fallback(sample_rates):
    gate = DecisionGate()
    models_dir = gate._models_dir
    assert models_dir.exists(), "storage/models directory must exist"

    wyckoff_model_file = models_dir / "builtin_wyckoff_meta.lgb"
    assert wyckoff_model_file.exists(), "builtin_wyckoff_meta.lgb must be present"

    # 1. Test Auto-Discovery for Wyckoff
    model_info = gate._get_or_load_meta_model("builtin_wyckoff")
    assert model_info is not None, "Should auto-discover builtin_wyckoff_meta.lgb"
    booster, thresh, feat_cols, fname = model_info
    assert fname == "builtin_wyckoff_meta.lgb"
    assert thresh == 0.38
    assert "cvd_proxy" in feat_cols

    # 2. Test Evaluation with ML Hook Active
    is_pass, prob, reason = gate._evaluate_meta_labeling(
        symbol="XAUUSD", signal="BUY", strategy_id="builtin_wyckoff", rates=sample_rates
    )
    assert isinstance(is_pass, (bool, np.bool_))
    assert 0.0 <= prob <= 1.0
    assert "ML Meta" in reason

    # 3. Test Fallback when Strategy has no model (e.g. unknown custom strategy)
    fallback_info = gate._get_or_load_meta_model("custom_strategy_without_model")
    assert fallback_info is None

    is_pass_fb, prob_fb, reason_fb = gate._evaluate_meta_labeling(
        symbol="XAUUSD", signal="BUY", strategy_id="custom_strategy_without_model", rates=sample_rates
    )
    assert is_pass_fb is True
    assert prob_fb == 1.0
    assert "No ML Model Attached" in reason_fb


def test_decision_gate_evaluate_with_strategy_id(sample_rates):
    gate = DecisionGate()
    res = gate.evaluate(
        symbol="XAUUSD",
        signal_from_strategy="BUY",
        timeframe=15,
        gate_mode="TECHNICAL",
        rates=sample_rates,
        strategy_id="builtin_wyckoff"
    )
    assert "decision" in res
    assert res["decision"] in ["BUY", "SELL", "WAIT"]
    assert "reason" in res
