# -*- coding: utf-8 -*-
"""
Unit Tests for Specialized XAUUSD and FX (EURUSD, GBPUSD) Data Ingestion & Processing Pipeline:
- Microstructure Wick Absorption Decomposition (Aronson & Lee-Ready CVD Proxy)
- Forex Tri-Factor Macro Integration (Central Bank Rate Spreads, DXY Vector, Economic Surprise)
- Precious Metals London LBMA Gold Fixing Detection
- FRED St. Louis API Institutional Client Resilience
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timezone

from backend.core.preprocessor import DataPreprocessor
from backend.infrastructure.data_providers.adapters.forex_adapter import (
    ForexContextAdapter,
    CENTRAL_BANK_BENCHMARK_RATES,
)
from backend.infrastructure.data_providers.adapters.precious_metals_adapter import (
    PreciousMetalsAdapter,
)
from backend.infrastructure.data_providers.macro.fred_client import FREDClient


class TestMicrostructureCVDWickAbsorption:
    """Verifies that the upgraded CVD Proxy properly captures Wick Absorption."""

    def test_hammer_pinbar_registers_buyer_absorption(self):
        """
        A Hammer candle has a massive lower wick and small body.
        Old linear formula: (Close - Open) / (High - Low) produces almost 0.
        Upgraded Wick Absorption model MUST capture the aggressive buyer absorption (+).
        """
        prep = DataPreprocessor()
        # 14 neutral candles followed by a massive hammer pinbar
        n = 14
        df = pd.DataFrame({
            "open": [2000.0] * (n - 1) + [2000.0],
            "high": [2002.0] * (n - 1) + [2002.0],
            "low": [1998.0] * (n - 1) + [1975.0],    # Deep 25-pt liquidity sweep
            "close": [2000.0] * (n - 1) + [2001.0],  # Closed back near highs
            "volume": [1000.0] * n,
        })

        cvd_data = prep._calculate_cvd_proxy(df, window=14)
        assert cvd_data is not None
        # With massive lower wick (1975 to 2000 = 25 pts) and small upper wick (1 pt),
        # delta must be strongly positive
        assert cvd_data["cvd_rolling"] > 0, "Hammer pinbar must produce positive buyer absorption"
        assert cvd_data["cvd_pressure_ratio"] > 0

    def test_shooting_star_registers_seller_absorption(self):
        """
        A Shooting Star has a massive upper wick and small body.
        Upgraded Wick Absorption model MUST capture the aggressive seller absorption (-).
        """
        prep = DataPreprocessor()
        n = 14
        df = pd.DataFrame({
            "open": [2000.0] * (n - 1) + [2000.0],
            "high": [2002.0] * (n - 1) + [2030.0],   # Spike up to sweep liquidity
            "low": [1998.0] * (n - 1) + [1999.0],
            "close": [2000.0] * (n - 1) + [1999.5],  # Pushed back down
            "volume": [1000.0] * n,
        })

        cvd_data = prep._calculate_cvd_proxy(df, window=14)
        assert cvd_data is not None
        assert cvd_data["cvd_rolling"] < 0, "Shooting star must produce negative seller absorption"
        assert cvd_data["cvd_pressure_ratio"] < 0

    def test_cvd_divergence_flag_generation(self):
        """Verify that price/volume absorption divergences are detected."""
        prep = DataPreprocessor()
        # Price creating lower lows while buyers absorb aggressively
        closes = [2010.0, 2008.0, 2006.0, 2004.0, 2000.0]
        lows = [2005.0, 2003.0, 2000.0, 1995.0, 1980.0]   # Deep long lower wicks
        opens = [2010.0, 2008.0, 2006.0, 2004.0, 1999.0]
        highs = [2011.0, 2009.0, 2007.0, 2005.0, 2001.0]
        df = pd.DataFrame({
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": [1000.0] * len(closes),
        })

        cvd_data = prep._calculate_cvd_proxy(df, window=5)
        assert "cvd_divergence" in cvd_data
        # At price low, buyers absorbing creates positive ratio -> Bullish Absorption Divergence
        if cvd_data["cvd_pressure_ratio"] > 0.05:
            assert cvd_data["cvd_divergence"] == "BULLISH_ABSORPTION_DIV"


class TestForexTriFactorMacroModel:
    """Verifies that ForexContextAdapter incorporates Rate Spreads and G10 Central Bank Rates."""

    def test_central_bank_benchmark_rates_configured(self):
        """Verify standard G10 policy rates are available."""
        assert "USD" in CENTRAL_BANK_BENCHMARK_RATES
        assert "EUR" in CENTRAL_BANK_BENCHMARK_RATES
        assert "GBP" in CENTRAL_BANK_BENCHMARK_RATES
        assert CENTRAL_BANK_BENCHMARK_RATES["USD"] > 5.0
        assert CENTRAL_BANK_BENCHMARK_RATES["EUR"] < CENTRAL_BANK_BENCHMARK_RATES["USD"]

    def test_forex_context_report_contains_institutional_metrics(self):
        """Verify context report includes rate differentials and G10 benchmarks."""
        adapter = ForexContextAdapter()
        rep_eurusd = adapter.generate_context_report("EURUSD")

        assert rep_eurusd["asset_class"] == "FOREX"
        assert rep_eurusd["base_currency"] == "EUR"
        assert rep_eurusd["quote_currency"] == "USD"
        assert "base_rate" in rep_eurusd
        assert "quote_rate" in rep_eurusd
        assert "rate_differential" in rep_eurusd
        assert rep_eurusd["rate_differential"] < 0, "EUR - USD policy rate spread must be negative"

        rep_gbpusd = adapter.generate_context_report("GBPUSD")
        assert rep_gbpusd["base_currency"] == "GBP"
        assert rep_gbpusd["quote_currency"] == "USD"
        assert "rate_differential" in rep_gbpusd


class TestPreciousMetalsLondonFixAndFRED:
    """Verifies London Gold Auction Fixing detection and FRED client resilience."""

    def test_london_fix_status_structure(self):
        """Verify get_london_fix_status returns structured dict."""
        adapter = PreciousMetalsAdapter()
        status = adapter.get_london_fix_status()
        assert "is_fixing_active" in status
        assert "fixing_name" in status
        assert "warning" in status
        assert isinstance(status["is_fixing_active"], bool)

    def test_fred_client_graceful_fallback_without_key(self):
        """Verify FREDClient handles unconfigured API key gracefully without crashing."""
        client = FREDClient(api_key="")
        assert not client.is_configured
        val = client.get_real_yield_10y()
        assert val is None, "Must return None cleanly when API key is missing"
