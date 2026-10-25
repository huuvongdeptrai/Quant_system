# -*- coding: utf-8 -*-
"""
Verification suite for the upgraded institutional Wyckoff Momentum Pro Strategy.
Tests:
1. Choppy market / Low ADX suppression (Sideways immunity).
2. Wyckoff Effort vs Result rejection wick filter.
3. S/R Headroom Clearance to prevent buying into ceilings / selling into floors.
4. Clean pullback retest execution when all 4 quantitative criteria align.
"""

import numpy as np
import pandas as pd
import pytest
from backend.core.strategies.wyckoff_vectorized import WyckoffMomentumStrategy
from backend.core.strategies.base_strategy import ChecklistStatus


def test_wyckoff_choppy_market_filter():
    """Verify that when ADX is low in a flat choppy range, the strategy suppresses entries."""
    strat = WyckoffMomentumStrategy()
    n = 80
    # Create flat oscillating series (choppy, low directional movement)
    t = np.arange(n)
    closes = 2650.0 + 1.5 * np.sin(t * 0.8)
    highs = closes + 1.0
    lows = closes - 1.0
    vols = np.full(n, 1000.0)
    vols[-1] = 2000.0  # Even with high volume, chop should prevent entry

    df = pd.DataFrame({"close": closes, "high": highs, "low": lows, "tick_volume": vols})
    sig = strat.analyze(df)

    assert sig.action == "HOLD"
    # Metadata should show low ADX or chop detection
    assert "adx" in sig.metadata
    assert sig.metadata["adx"] < 25.0


def test_wyckoff_effort_vs_result_wick_rejection():
    """Verify that a high-volume candle with a heavy upper rejection wick is NOT bought."""
    strat = WyckoffMomentumStrategy()
    n = 80
    closes = [2600.0 + i * 0.8 for i in range(n)]
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]
    opens = [c - 0.5 for c in closes]
    vols = [1000.0] * n

    # On the last candle, price shoots up but gets violently slammed down (Upper Wick = 65% of range)
    highs[-1] = closes[-1] + 6.0
    opens[-1] = closes[-1] - 0.5
    lows[-1] = closes[-1] - 1.0
    vols[-1] = 2500.0  # High volume effort

    df = pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "tick_volume": vols,
    })
    sig = strat.analyze(df)

    # Must be HOLD due to Wyckoff Effort vs Result failure
    assert sig.action == "HOLD"
    chk_vals = [c.value for c in sig.checklist]
    assert any("Effort" in v or "Wick" in v or "Normal" in v for v in chk_vals)


def test_wyckoff_sr_headroom_choked_filter():
    """Verify that when an obstacle (recent ceiling) is within < 1.0 ATR, BUY is suppressed."""
    strat = WyckoffMomentumStrategy()
    n = 80
    closes = [2600.0 + i * 0.5 for i in range(n)]
    highs = [c + 1.5 for c in closes]
    lows = [c - 1.5 for c in closes]
    vols = [1000.0] * n

    # Place a massive peak 15 bars ago at 2650.0
    highs[-15] = 2650.0  # Massive ceiling
    closes[-1] = 2649.5  # Current price is 0.5 points below ceiling (< 1.0 ATR)
    highs[-1] = 2649.8
    lows[-1] = 2647.0
    vols[-1] = 2000.0

    df = pd.DataFrame({
        "open": closes,
        "high": highs,
        "low": lows,
        "close": closes,
        "tick_volume": vols,
    })
    sig = strat.analyze(df)

    # Choked headroom should prevent BUY
    assert sig.action == "HOLD"
    assert sig.metadata["has_headroom"] is False


def test_wyckoff_clean_breakout_execution():
    """Verify that when all 4 quantitative criteria align, BUY is cleanly executed."""
    strat = WyckoffMomentumStrategy()
    n = 80
    closes = [2600.0 + i * 0.5 for i in range(n)]
    ema20 = strat._calc_ema(np.array(closes), 20)

    # Pullback testing EMA20 at n-2, then strong thrust above EMA20 at n-1
    closes[-2] = ema20[-3] - 0.2
    closes[-1] = ema20[-2] + 2.0

    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]
    opens = [c - 0.5 for c in closes]
    vols = [1000.0] * n
    vols[-1] = 2500.0  # High volume expansion

    df = pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "tick_volume": vols,
    })
    sig = strat.analyze(df)

    assert sig.action == "BUY"
    assert sig.confidence >= 0.75
    assert sig.sl is not None
    assert sig.tp1 is not None
    assert sig.tp1 > sig.entry_price > sig.sl
    assert len(sig.checklist) == 3
    for chk in sig.checklist:
        assert chk.status == ChecklistStatus.PASSED
