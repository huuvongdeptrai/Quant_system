# -*- coding: utf-8 -*-
"""
FRED (Federal Reserve Economic Data) Official Client.
St. Louis Fed Institutional Macro API Integration for Precious Metals & FX:
- 10-Year TIPS Real Yield (DFII10) - Primary Valuation Vector for Gold
- 2-Year Treasury Constant Maturity (DGS2) - Core Sovereign Vector for FX
- 10-Year Treasury Constant Maturity (DGS10) - Benchmark Long Yield
- 10-Year Breakeven Inflation Rate (T10YIE) - Market Expected Inflation

Complies with institutional Pre-Trade compliance and multi-tier network fallback.
"""
import os
import time
import requests
from typing import Dict, Any, Optional
from loguru import logger

# Cache TTL: 3600 seconds (1 hour) since FRED daily series update after market close
_FRED_CACHE: Dict[str, Any] = {
    "data": {},
    "timestamp": 0.0,
}
FRED_CACHE_TTL = 3600.0


class FREDClient:
    """Institutional St. Louis Fed API Client with local caching and graceful fallback."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("FRED_API_KEY", "").strip()
        self.base_url = "https://api.stlouisfed.org/fred/series/observations"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "QuantAI/2.2 Institutional Macro Desk"})

    @property
    def is_configured(self) -> bool:
        """Returns True if a valid FRED API key is loaded."""
        return bool(self.api_key and len(self.api_key) >= 16)

    def fetch_latest_observation(self, series_id: str) -> Optional[float]:
        """
        Fetches the latest non-empty observation for a FRED economic series.
        Example series: 'DFII10' (10Y Real Yield), 'DGS2' (2Y US), 'DGS10' (10Y US).
        """
        now = time.time()
        cached_entry = _FRED_CACHE["data"].get(series_id)
        if cached_entry and (now - cached_entry.get("timestamp", 0.0) < FRED_CACHE_TTL):
            return cached_entry.get("value")

        if not self.is_configured:
            return None

        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 5,
        }

        try:
            res = self.session.get(self.base_url, params=params, timeout=3.5)
            if res.status_code == 200:
                payload = res.json()
                observations = payload.get("observations", [])
                for obs in observations:
                    val_str = obs.get("value", "").strip()
                    if val_str and val_str != ".":
                        val = float(val_str)
                        _FRED_CACHE["data"][series_id] = {
                            "value": val,
                            "date": obs.get("date"),
                            "timestamp": now,
                        }
                        return val
        except Exception as err:
            logger.debug(f"[FREDClient] Error querying {series_id}: {err}")

        return None

    def get_real_yield_10y(self) -> Optional[float]:
        """10-Year Treasury Inflation-Indexed Security (TIPS) Constant Maturity Rate (DFII10)."""
        return self.fetch_latest_observation("DFII10")

    def get_us_2y_yield(self) -> Optional[float]:
        """2-Year Treasury Constant Maturity Rate (DGS2)."""
        return self.fetch_latest_observation("DGS2")

    def get_us_10y_yield(self) -> Optional[float]:
        """10-Year Treasury Constant Maturity Rate (DGS10)."""
        return self.fetch_latest_observation("DGS10")

    def get_breakeven_inflation(self) -> Optional[float]:
        """10-Year Breakeven Inflation Rate (T10YIE)."""
        return self.fetch_latest_observation("T10YIE")
