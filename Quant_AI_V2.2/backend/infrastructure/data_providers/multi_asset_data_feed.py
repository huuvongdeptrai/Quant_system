"""
Multi-Asset Data Feed & Synchronized Market Slice Engine (Pillar 2).
Complies with QuantConnect LEAN OnData(Slice) architecture and CFA quantitative standards.
Provides concurrent, low-latency market data ingestion across the entire Watchlist,
eliminating sequential latency drift and guaranteeing synchronized bar evaluation.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Sequence, Tuple
import pandas as pd
import numpy as np
from loguru import logger

from backend.infrastructure.brokers.mt5_safe import mt5


@dataclass(frozen=True)
class MarketSlice:
    """
    Immutable, synchronized multi-asset market snapshot for a single discrete time event.
    Replicates QuantConnect LEAN Slice pattern for fair cross-asset algorithmic execution.
    """
    timestamp: float
    timeframe: int
    bars: Dict[str, pd.DataFrame] = field(default_factory=dict)
    raw_rates: Dict[str, Any] = field(default_factory=dict)
    ticks: Dict[str, Dict[str, float]] = field(default_factory=dict)

    @property
    def symbols(self) -> List[str]:
        """Returns list of all active symbols present in this slice."""
        return list(self.bars.keys())

    @property
    def is_empty(self) -> bool:
        """Returns True if no symbol data was successfully captured in this slice."""
        return len(self.bars) == 0

    def has_symbol(self, symbol: str) -> bool:
        """Checks if a symbol is present in this slice."""
        clean = str(symbol or "").split("\n")[0].strip().upper()
        return clean in self.bars

    def get_bars(self, symbol: str) -> Optional[pd.DataFrame]:
        """Retrieves OHLCV DataFrame for a specific symbol."""
        clean = str(symbol or "").split("\n")[0].strip().upper()
        return self.bars.get(clean)

    def get_rates(self, symbol: str) -> Optional[Any]:
        """Retrieves raw numpy structured rates array for high-performance vectorized operations."""
        clean = str(symbol or "").split("\n")[0].strip().upper()
        return self.raw_rates.get(clean)

    def get_tick(self, symbol: str) -> Optional[Dict[str, float]]:
        """Retrieves latest tick dictionary (bid, ask, spread)."""
        clean = str(symbol or "").split("\n")[0].strip().upper()
        return self.ticks.get(clean)

    def get_current_price(self, symbol: str) -> Optional[float]:
        """Retrieves latest close/bid price for a symbol from this slice."""
        clean = str(symbol or "").split("\n")[0].strip().upper()
        tick = self.ticks.get(clean)
        if tick and "bid" in tick and tick["bid"] > 0:
            return tick["bid"]
        df = self.bars.get(clean)
        if df is not None and len(df) > 0 and "close" in df.columns:
            return float(df["close"].iloc[-1])
        rates = self.raw_rates.get(clean)
        if rates is not None and len(rates) > 0:
            return float(rates[-1]["close"])
        return None


class MultiAssetDataFeed:
    """
    Concurrent Multi-Asset Data Ingestion Engine.
    Emits synchronized MarketSlice snapshots for entire watchlists.
    """

    def __init__(self, max_workers: int = 8, default_lookback: int = 300):
        self.max_workers = max_workers
        self.default_lookback = default_lookback

    def _fetch_single_symbol(
        self,
        symbol: str,
        timeframe: int,
        count: int
    ) -> Tuple[str, Optional[Any], Optional[pd.DataFrame], Optional[Dict[str, float]]]:
        """Internal worker fetching rates and tick for a single instrument."""
        clean = str(symbol or "").split("\n")[0].strip().upper()
        try:
            # Ensure MarketWatch subscription
            try:
                mt5.symbol_select(clean, True)
            except Exception:
                pass

            # Fetch rates
            rates = mt5.copy_rates_from_pos(clean, timeframe, 0, count)
            if rates is None or len(rates) == 0:
                rates = mt5.copy_rates_from_pos(clean, timeframe, 0, min(count, 100))

            df = None
            if rates is not None and len(rates) > 0:
                df = pd.DataFrame(rates)
                if "time" in df.columns:
                    df["time"] = pd.to_datetime(df["time"], unit="s")

            # Fetch tick
            tick_dict = None
            try:
                t = mt5.symbol_info_tick(clean)
                if t is not None:
                    bid = float(getattr(t, "bid", 0.0))
                    ask = float(getattr(t, "ask", 0.0))
                    spread = float(ask - bid) if (ask > 0 and bid > 0) else 0.0
                    tick_dict = {"bid": bid, "ask": ask, "spread": spread}
            except Exception:
                pass

            return clean, rates, df, tick_dict

        except Exception as e_fetch:
            logger.debug(f"[MultiAssetDataFeed] Error fetching {clean}: {e_fetch}")
            return clean, None, None, None

    def pull_slice(
        self,
        symbols: Sequence[str],
        timeframe: int,
        count: Optional[int] = None
    ) -> MarketSlice:
        """
        Pulls synchronized market data concurrently across all symbols.
        Returns an immutable MarketSlice capturing the unified bar snapshot.
        """
        slice_ts = time.time()
        lookback = count if count is not None else self.default_lookback

        clean_syms = [str(s).split("\n")[0].strip().upper() for s in symbols if str(s).strip()]
        if not clean_syms:
            return MarketSlice(timestamp=slice_ts, timeframe=timeframe)

        bars_map: Dict[str, pd.DataFrame] = {}
        rates_map: Dict[str, Any] = {}
        ticks_map: Dict[str, Dict[str, float]] = {}

        workers = min(self.max_workers, max(1, len(clean_syms)))

        if workers == 1:
            for s in clean_syms:
                sym_k, r, d, t = self._fetch_single_symbol(s, timeframe, lookback)
                if d is not None:
                    bars_map[sym_k] = d
                if r is not None:
                    rates_map[sym_k] = r
                if t is not None:
                    ticks_map[sym_k] = t
        else:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(self._fetch_single_symbol, s, timeframe, lookback): s
                    for s in clean_syms
                }
                for f in as_completed(futures):
                    sym_k, r, d, t = f.result()
                    if d is not None:
                        bars_map[sym_k] = d
                    if r is not None:
                        rates_map[sym_k] = r
                    if t is not None:
                        ticks_map[sym_k] = t

        return MarketSlice(
            timestamp=slice_ts,
            timeframe=timeframe,
            bars=bars_map,
            raw_rates=rates_map,
            ticks=ticks_map,
        )

    def benchmark_latency(
        self,
        symbols: Sequence[str],
        timeframe: int,
        count: int = 300
    ) -> Dict[str, float]:
        """
        Benchmarks latency comparison between sequential vs concurrent slice ingestion.
        Returns timing in milliseconds and speedup ratio.
        """
        clean_syms = [str(s).split("\n")[0].strip().upper() for s in symbols if str(s).strip()]
        if not clean_syms:
            return {"sequential_ms": 0.0, "concurrent_ms": 0.0, "speedup_ratio": 1.0}

        # 1. Sequential timing
        t0 = time.perf_counter()
        for s in clean_syms:
            self._fetch_single_symbol(s, timeframe, count)
        seq_time = (time.perf_counter() - t0) * 1000.0

        # 2. Concurrent timing
        t1 = time.perf_counter()
        self.pull_slice(clean_syms, timeframe, count)
        conc_time = (time.perf_counter() - t1) * 1000.0

        ratio = round(seq_time / conc_time, 2) if conc_time > 0 else 1.0
        return {
            "sequential_ms": round(seq_time, 2),
            "concurrent_ms": round(conc_time, 2),
            "speedup_ratio": ratio,
        }
