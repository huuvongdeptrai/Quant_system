"""
Tests for System-Level Market Structure & Trend Engine.
Verifies pure deterministic mathematical detection of:
- Fractal Swings (Swing Highs & Lows)
- Market Structure Geometry (Higher Highs/Lows, Lower Highs/Lows, Contraction, Expansion)
- Break of Structure (BOS) / Market Structure Shift (MSS)
- Adaptive lookback on variable candle buffers
- DataPreprocessor, AnalysisEngine, and DecisionGate integration without touching strategies
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import MagicMock, patch

from backend.core.market_structure import (
    MarketStructureEngine,
    MarketStructureResult,
    SwingPoint,
)
from backend.core.preprocessor import DataPreprocessor
from backend.infrastructure.ai_engines.ai.decision_gate import DecisionGate


class TestMarketStructureEngine:
    """Test suite for MarketStructureEngine core calculations."""

    def test_swing_detection_basic(self):
        """Verify swing high and low detection on known pivot sequence."""
        # V-shape sequence: peaks at index 3, trough at index 7
        highs = np.array([10, 12, 14, 18, 14, 12, 11, 8, 11, 13, 16, 12, 10], dtype=float)
        lows = highs - 1.0
        closes = highs - 0.5
        opens = closes.copy()

        df = pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes})
        sh_points, sl_points = MarketStructureEngine.detect_swings(df, order=2)

        sh_indices = [p.index for p in sh_points]
        sl_indices = [p.index for p in sl_points]

        assert 3 in sh_indices, f"Index 3 (18.0) should be a swing high, got {sh_indices}"
        assert 7 in sl_indices, f"Index 7 (7.0) should be a swing low, got {sl_indices}"

    def test_uptrend_higher_highs_higher_lows(self):
        """Verify detection of Bullish market structure with HH + HL."""
        n = 80
        t = np.linspace(100, 140, n)
        # Add sinusoidal swings on top of upward slope
        swings = np.sin(np.linspace(0, 8 * np.pi, n)) * 2.5
        highs = t + 2.0 + swings
        lows = t - 2.0 + swings
        closes = (highs + lows) / 2.0
        opens = closes.copy()

        df = pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes})
        res = MarketStructureEngine.analyze_market_structure(df, ema_period=50)

        assert res.trend == "BULLISH"
        assert "Bullish" in res.structure_label
        assert res.ema_position in ("ABOVE_EMA", "AT_EMA")
        assert res.confidence >= 0.75

    def test_downtrend_lower_highs_lower_lows(self):
        """Verify detection of Bearish market structure with LH + LL."""
        n = 80
        t = np.linspace(140, 100, n)
        swings = np.sin(np.linspace(0, 8 * np.pi, n)) * 2.5
        highs = t + 2.0 + swings
        lows = t - 2.0 + swings
        closes = (highs + lows) / 2.0
        opens = closes.copy()

        df = pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes})
        res = MarketStructureEngine.analyze_market_structure(df, ema_period=50)

        assert res.trend == "BEARISH"
        assert "Bearish" in res.structure_label
        assert res.ema_position in ("BELOW_EMA", "AT_EMA")
        assert res.confidence >= 0.75

    def test_bullish_break_of_structure(self):
        """Verify BOS detection when price breaks above previous swing high."""
        # 30 bars ranging between 100-110, then a strong breakout to 118
        highs = np.array([100, 102, 105, 108, 106, 103, 101, 102, 104, 107, 105, 102, 103, 106, 118], dtype=float)
        lows = highs - 2.0
        closes = highs - 0.2
        opens = lows + 0.2

        df = pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes})
        res = MarketStructureEngine.analyze_market_structure(df, current_price=117.8)

        assert res.bos_detected is True
        assert res.bos_direction == "BULLISH_BOS"
        assert res.trend == "BULLISH"
        assert "BOS" in res.structure_label or "Bullish" in res.structure_label

    def test_bearish_break_of_structure(self):
        """Verify BOS detection when price breaks below previous swing low."""
        highs = np.array([118, 116, 113, 111, 114, 117, 115, 112, 111, 113, 115, 113, 111, 109, 98], dtype=float)
        lows = highs - 2.0
        closes = lows + 0.2
        opens = highs - 0.2

        df = pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes})
        res = MarketStructureEngine.analyze_market_structure(df, current_price=98.2)

        assert res.bos_detected is True
        assert res.bos_direction == "BEARISH_BOS"
        assert res.trend == "BEARISH"
        assert "BOS" in res.structure_label or "Bearish" in res.structure_label

    def test_adaptive_lookback_small_sample(self):
        """Verify engine does not crash or fail when bar count is small (15-25 bars)."""
        small_bars = [
            {"open": 2000.0 + i, "high": 2002.0 + i, "low": 1999.0 + i, "close": 2001.0 + i}
            for i in range(18)
        ]
        res = MarketStructureEngine.analyze_market_structure(small_bars)
        assert res.trend in ("BULLISH", "BEARISH", "SIDEWAYS")
        assert res.current_price > 0
        assert res.ema_anchor > 0

    def test_empty_or_zero_data_fallback(self):
        """Verify graceful fallback on empty input."""
        res = MarketStructureEngine.analyze_market_structure([], current_price=2750.0)
        assert res.trend == "SIDEWAYS"
        assert res.current_price == 2750.0
        assert res.structure_label == "Insufficient Data"


class TestDataPreprocessorIntegration:
    """Test DataPreprocessor interaction with MarketStructureEngine."""

    def test_preprocessor_emits_market_structure(self):
        prep = DataPreprocessor()
        rates = [
            {"time": 1700000000 + i * 900, "open": 2700.0 + i * 0.5, "high": 2702.0 + i * 0.5, "low": 2699.0 + i * 0.5, "close": 2701.0 + i * 0.5, "tick_volume": 150}
            for i in range(60)
        ]
        res = prep.process_technical_data(rates)
        assert res is not None

        # 8 Legacy keys check
        for k in ["current_time_utc", "current_price", "rsi_value", "rsi_label", "trend", "resistance", "support", "volatility"]:
            assert k in res, f"Missing legacy key: {k}"

        # New System Market Structure keys
        assert "market_structure" in res
        assert "structure_label" in res
        assert "math_trend" in res
        assert "bos_detected" in res
        assert res["math_trend"] in ("Bullish", "Bearish", "Sideways")

    def test_preprocessor_resilience_small_buffer(self):
        """Ensure preprocessor works on 25 bars without returning None."""
        prep = DataPreprocessor()
        rates = [
            {"time": 1700000000 + i * 900, "open": 2700.0 + i, "high": 2702.0 + i, "low": 2699.0 + i, "close": 2701.0 + i, "tick_volume": 150}
            for i in range(25)
        ]
        res = prep.process_technical_data(rates)
        assert res is not None
        assert res["trend"] in ("TĂNG (Uptrend)", "GIẢM (Downtrend)", "ĐI NGANG (Sideways)")

    def test_preprocessor_detect_fractal_swings_and_structure(self):
        """Ensure public methods detect_fractal_swings and detect_market_structure work."""
        prep = DataPreprocessor()
        rates = [
            {"time": 1700000000 + i * 900, "open": 2700.0 + i, "high": 2702.0 + i, "low": 2699.0 + i, "close": 2701.0 + i, "tick_volume": 150}
            for i in range(40)
        ]
        shs, sls = prep.detect_fractal_swings(rates, order=2)
        assert isinstance(shs, list)
        assert isinstance(sls, list)

        struct = prep.detect_market_structure(rates)
        assert isinstance(struct, MarketStructureResult)
        assert struct.trend in ("BULLISH", "BEARISH", "SIDEWAYS")


class TestDecisionGateAdaptiveLookback:
    """Test DecisionGate _get_htf_bias with adaptive lookback."""

    def test_decision_gate_htf_bias_low_bar_count(self):
        gate = DecisionGate()
        # Create 35 bars of D1 and H4 (less than the former 65-bar hard threshold)
        d1_rates = [
            {"time": 1700000000 + i * 86400, "open": 2700.0 + i * 2, "high": 2705.0 + i * 2, "low": 2698.0 + i * 2, "close": 2704.0 + i * 2}
            for i in range(35)
        ]
        h4_rates = [
            {"time": 1700000000 + i * 14400, "open": 2700.0 + i, "high": 2703.0 + i, "low": 2698.0 + i, "close": 2702.0 + i}
            for i in range(35)
        ]
        bias = gate._get_htf_bias("XAUUSD", d1_rates=d1_rates, h4_rates=h4_rates)
        assert bias in ("BULLISH", "BEARISH", "NEUTRAL")
        assert bias == "BULLISH"
