"""
Unit tests for MultiAssetDataFeed and MarketSlice Engine (Pillar 2).
Validates QuantConnect LEAN OnData(Slice) synchronization pattern,
concurrent watchlist ingestion, and latency benchmarks.
"""

import time
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np

from backend.infrastructure.brokers.mt5_safe import mt5
from backend.infrastructure.data_providers.multi_asset_data_feed import (
    MultiAssetDataFeed,
    MarketSlice,
)
from backend.core.bot_orchestrator import BotOrchestrator


def test_market_slice_properties():
    """Verifies that MarketSlice provides immutable, typed accessor methods."""
    ts = time.time()
    df_xau = pd.DataFrame({
        "time": pd.date_range("2026-10-25", periods=5, freq="15min"),
        "open": [2730.0, 2731.0, 2732.0, 2733.0, 2734.0],
        "high": [2735.0, 2736.0, 2737.0, 2738.0, 2739.0],
        "low": [2728.0, 2729.0, 2730.0, 2731.0, 2732.0],
        "close": [2734.0, 2735.0, 2736.0, 2737.0, 2738.5],
    })
    raw_rates_xau = np.array([(1, 2730.0, 2735.0, 2728.0, 2738.5, 100, 10, 0)],
                             dtype=[('time', '<i8'), ('open', '<f8'), ('high', '<f8'), ('low', '<f8'), ('close', '<f8'), ('tick_volume', '<u8'), ('spread', '<i4'), ('real_volume', '<u8')])

    tick_xau = {"bid": 2738.5, "ask": 2738.8, "spread": 0.3}

    m_slice = MarketSlice(
        timestamp=ts,
        timeframe=15,
        bars={"XAUUSD": df_xau},
        raw_rates={"XAUUSD": raw_rates_xau},
        ticks={"XAUUSD": tick_xau},
    )

    assert m_slice.timestamp == ts
    assert m_slice.timeframe == 15
    assert m_slice.symbols == ["XAUUSD"]
    assert m_slice.is_empty is False
    assert m_slice.has_symbol("XAUUSD") is True
    assert m_slice.has_symbol("BTCUSD") is False

    assert m_slice.get_bars("XAUUSD") is df_xau
    assert m_slice.get_current_price("XAUUSD") == 2738.5
    assert m_slice.get_tick("XAUUSD") == tick_xau


def test_multi_asset_data_feed_pull_slice_concurrent():
    """Verifies that MultiAssetDataFeed concurrently aggregates rates for multiple symbols."""
    feed = MultiAssetDataFeed(max_workers=4, default_lookback=50)

    # Mock MT5 copy_rates_from_pos
    def mock_copy_rates(sym, tf, start, count):
        base = 2700.0 if "XAU" in sym else 67000.0
        return np.array([
            (int(time.time()), base, base + 10.0, base - 5.0, base + 2.0, 50, 10, 0)
        ], dtype=[('time', '<i8'), ('open', '<f8'), ('high', '<f8'), ('low', '<f8'), ('close', '<f8'), ('tick_volume', '<u8'), ('spread', '<i4'), ('real_volume', '<u8')])

    with patch("backend.infrastructure.data_providers.multi_asset_data_feed.mt5.copy_rates_from_pos", side_effect=mock_copy_rates), \
         patch("backend.infrastructure.data_providers.multi_asset_data_feed.mt5.symbol_select", return_value=True):
        m_slice = feed.pull_slice(["XAUUSD", "BTCUSD"], timeframe=15, count=50)

    assert m_slice.is_empty is False
    assert set(m_slice.symbols) == {"XAUUSD", "BTCUSD"}
    assert m_slice.has_symbol("XAUUSD") is True
    assert m_slice.has_symbol("BTCUSD") is True
    assert len(m_slice.get_bars("XAUUSD")) == 1
    assert len(m_slice.get_bars("BTCUSD")) == 1


def test_data_feed_latency_benchmark():
    """Verifies that benchmark_latency executes and returns timing metrics dictionary."""
    feed = MultiAssetDataFeed(max_workers=4)

    def mock_copy_rates(sym, tf, start, count):
        time.sleep(0.005)  # simulate small network latency
        return np.array([(1, 100.0, 105.0, 95.0, 102.0, 10, 2, 0)],
                        dtype=[('time', '<i8'), ('open', '<f8'), ('high', '<f8'), ('low', '<f8'), ('close', '<f8'), ('tick_volume', '<u8'), ('spread', '<i4'), ('real_volume', '<u8')])

    with patch("backend.infrastructure.data_providers.multi_asset_data_feed.mt5.copy_rates_from_pos", side_effect=mock_copy_rates), \
         patch("backend.infrastructure.data_providers.multi_asset_data_feed.mt5.symbol_select", return_value=True):
        metrics = feed.benchmark_latency(["XAUUSD", "BTCUSD", "ETHUSD", "EURUSD"], timeframe=15)

    assert "sequential_ms" in metrics
    assert "concurrent_ms" in metrics
    assert "speedup_ratio" in metrics
    assert metrics["sequential_ms"] >= 0.0
    assert metrics["concurrent_ms"] >= 0.0


def test_bot_orchestrator_pipeline_execute_uses_market_slice():
    """
    Verifies that BotOrchestrator uses pre-fetched rates from MarketSlice
    without making redundant MT5 copy_rates calls.
    """
    raw_rates_btc = np.array([(1, 67000.0, 67500.0, 66800.0, 67200.0, 50, 10, 0)],
                             dtype=[('time', '<i8'), ('open', '<f8'), ('high', '<f8'), ('low', '<f8'), ('close', '<f8'), ('tick_volume', '<u8'), ('spread', '<i4'), ('real_volume', '<u8')])

    m_slice = MarketSlice(
        timestamp=time.time(),
        timeframe=15,
        bars={"BTCUSD": pd.DataFrame({"time": [pd.Timestamp.now()], "open": [67000.0], "high": [67500.0], "low": [66800.0], "close": [67200.0]})},
        raw_rates={"BTCUSD": raw_rates_btc},
    )

    orch = BotOrchestrator(
        strategy=MagicMock(),
        risk_manager=MagicMock(),
        execution_manager=MagicMock(),
        data_preprocessor=MagicMock(),
        decision_gate=MagicMock(),
        symbols=["BTCUSD"],
    )

    # Mock state_recovery and session filter to allow execution
    orch.state_recovery.can_open_new_trade = MagicMock(return_value=True)
    orch.circuit_guard.circuit_breaker_active = False
    orch._check_session_allowed = MagicMock(return_value=(True, "CRYPTO_24_7"))
    orch.news_filter_enabled = False
    orch.prep.process_technical_data = MagicMock(return_value=None)  # exit early after rates check

    with patch("backend.core.bot_orchestrator.mt5.copy_rates_from_pos") as mock_copy:
        orch.pipeline_execute("BTCUSD", market_slice=m_slice)
        # MUST NOT call copy_rates_from_pos because rates were in m_slice!
        mock_copy.assert_not_called()
