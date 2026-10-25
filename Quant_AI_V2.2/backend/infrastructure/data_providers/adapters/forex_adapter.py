# -*- coding: utf-8 -*-
"""
Forex Context Adapter (Relative Currency Strength & Economic Surprise Engine).
Calculates Directional Macro Bias based on:
1. DXY Inversion Vector (USD-denominated pairs)
2. Base vs Quote Currency Economic Surprise Momentum (Actual vs Forecast differential from CalendarEngine)
3. Central Bank Interest Rate Differentials (Fallback/Structural)
"""
import re
import time
from typing import Dict, Any, Tuple, Optional
from loguru import logger

from backend.infrastructure.data_providers.adapters.base_adapter import BaseContextAdapter
from backend.infrastructure.data_providers.macro.macro_regime import MacroRegimeEngine
from backend.infrastructure.data_providers.macro.calendar_engine import CalendarEngine
from backend.infrastructure.data_providers.macro.fred_client import FREDClient

# Benchmark Policy Rates of G10 Central Banks (Annualized %)
CENTRAL_BANK_BENCHMARK_RATES = {
    "USD": 5.33,  # Fed Funds Effective Target
    "EUR": 3.65,  # ECB Main Refinancing Rate (Deposit 3.25%)
    "GBP": 5.00,  # Bank of England Official Bank Rate
    "JPY": 0.25,  # Bank of Japan Policy Rate
    "AUD": 4.35,  # Reserve Bank of Australia Cash Rate
    "CAD": 3.75,  # Bank of Canada Policy Rate
    "CHF": 1.00,  # Swiss National Bank Policy Rate
    "NZD": 4.75,  # Reserve Bank of New Zealand Official Cash Rate
}


CURRENCY_COUNTRY_MAP = {
    "USD": "US",
    "EUR": "EU",
    "GBP": "GB",
    "JPY": "JP",
    "AUD": "AU",
    "CAD": "CA",
    "CHF": "CH",
    "NZD": "NZ",
}


def parse_numeric_metric(val_str: Any) -> Optional[float]:
    """Parses strings like '3.2%', '150K', '-0.4M' into normalized float."""
    if val_str is None:
        return None
    s = str(val_str).strip()
    if not s or s in ["--", "N/A", "None"]:
        return None

    is_pct = "%" in s
    mult = 1.0
    if "K" in s.upper():
        mult = 1e3
    elif "M" in s.upper():
        mult = 1e6
    elif "B" in s.upper():
        mult = 1e9

    clean = re.sub(r"[^0-9.-]", "", s)
    try:
        val = float(clean) * mult
        return val / 100.0 if is_pct else val
    except (ValueError, TypeError):
        return None


class ForexContextAdapter(BaseContextAdapter):
    """Institutional Multi-Currency Forex Context Engine."""

    def __init__(self):
        self.macro_engine = MacroRegimeEngine()
        self.calendar_engine = CalendarEngine()
        self.fred_client = FREDClient()

    @staticmethod
    def parse_currency_pair(symbol: str) -> Tuple[str, str]:
        """Decomposes symbol like 'EURUSD', 'GBPUSD' into ('EUR', 'USD')."""
        s = symbol.upper().replace("/", "").replace("_", "").replace(".", "").strip()
        if len(s) >= 6:
            base = s[:3]
            quote = s[3:6]
            return base, quote
        return "EUR", "USD"

    def _get_dxy_trend(self) -> str:
        """Extracts DXY trend / US Macro bias."""
        try:
            regime = self.macro_engine.get_current_regime()
            bias = regime.get("bias", "NEUTRAL").upper()
            return bias
        except Exception:
            return "NEUTRAL"

    def _calculate_surprise_momentum(self, currency: str, events: list) -> float:
        """
        Calculates net economic surprise score for a given currency based on recent releases.
        Positive surprise (+): Economy beating forecasts -> Currency Bullish.
        Negative surprise (-): Economy missing forecasts -> Currency Bearish.
        """
        country = CURRENCY_COUNTRY_MAP.get(currency)
        if not country or not events:
            return 0.0

        score = 0.0
        now_ts = time.time()
        lookback_sec = 86400 * 3  # Past 3 days lookback for fresh releases

        for e in events:
            if e.get("country") != country:
                continue

            event_ts = e.get("sort_key", 0)
            if not (0 < (now_ts - event_ts) <= lookback_sec):
                continue

            act = parse_numeric_metric(e.get("actual"))
            fc = parse_numeric_metric(e.get("forecast"))
            if act is not None and fc is not None:
                diff = act - fc
                imp_weight = 1.0 if e.get("impact", 0) >= 2 else (0.5 if e.get("impact", 0) == 1 else 0.2)
                
                title_u = e.get("title", "").upper()
                if any(k in title_u for k in ["UNEMPLOYMENT", "JOBLESS", "CLAIMS"]):
                    diff = -diff

                if abs(diff) > 1e-6:
                    score += (1.0 if diff > 0 else -1.0) * imp_weight

        return max(-3.0, min(3.0, score))

    def get_macro_bias(self, symbol: str) -> str:
        """
        Computes directional bias (BULLISH, BEARISH, NEUTRAL) for any Forex pair using
        Tri-Factor Macro Integration:
        1. US Dollar Index (DXY) Structural Vector
        2. Central Bank Benchmark Rate & Sovereign Yield Differential
        3. Economic Surprise Momentum from Economic Releases (CESI Proxy)
        """
        base_curr, quote_curr = self.parse_currency_pair(symbol)
        
        # 1. DXY Vector Component (-1.0 to +1.0)
        dxy_trend = self._get_dxy_trend()
        usd_component = 0.0
        if quote_curr == "USD":
            if dxy_trend == "BULLISH":
                usd_component = -1.0
            elif dxy_trend == "BEARISH":
                usd_component = 1.0
        elif base_curr == "USD":
            if dxy_trend == "BULLISH":
                usd_component = 1.0
            elif dxy_trend == "BEARISH":
                usd_component = -1.0

        # 2. Policy Rate & Sovereign Yield Differential Component
        base_rate = CENTRAL_BANK_BENCHMARK_RATES.get(base_curr, 5.0)
        quote_rate = CENTRAL_BANK_BENCHMARK_RATES.get(quote_curr, 5.0)
        rate_diff = base_rate - quote_rate
        # Rate carry component normalized (-1.0 to +1.0 for +-1.5% spread)
        rate_component = max(-1.0, min(1.0, rate_diff / 1.5))

        # 3. Economic Surprise Component from Calendar
        try:
            events = self.calendar_engine.fetch_events()
        except Exception:
            events = []

        base_surprise = self._calculate_surprise_momentum(base_curr, events)
        quote_surprise = self._calculate_surprise_momentum(quote_curr, events)
        net_surprise = base_surprise - quote_surprise
        surprise_component = max(-1.0, min(1.0, net_surprise / 2.0))

        # Tri-Factor Macro Score (USD Vector 40%, Rate Spread 35%, Surprise 25%)
        total_score = (usd_component * 0.40) + (rate_component * 0.35) + (surprise_component * 0.25)

        if total_score >= 0.25:
            return "BULLISH"
        elif total_score <= -0.25:
            return "BEARISH"
        return "NEUTRAL"

    def generate_context_report(self, symbol: str) -> Dict[str, Any]:
        """Generates structured multi-currency macro context report."""
        base_curr, quote_curr = self.parse_currency_pair(symbol)
        bias = self.get_macro_bias(symbol)
        dxy_bias = self._get_dxy_trend()
        base_rate = CENTRAL_BANK_BENCHMARK_RATES.get(base_curr, 5.0)
        quote_rate = CENTRAL_BANK_BENCHMARK_RATES.get(quote_curr, 5.0)
        rate_diff = base_rate - quote_rate
        us_2y = self.fred_client.get_us_2y_yield() if self.fred_client else None

        return {
            "symbol": symbol,
            "asset_class": "FOREX",
            "base_currency": base_curr,
            "quote_currency": quote_curr,
            "directional_bias": bias,
            "dxy_trend": dxy_bias,
            "base_rate": base_rate,
            "quote_rate": quote_rate,
            "rate_differential": round(rate_diff, 2),
            "us_2y_yield": us_2y,
            "timestamp": time.time(),
        }

    def build_prompt_section(self, symbol: str, context_report: Dict[str, Any]) -> str:
        """Builds prompt string for LLM strategies."""
        base = context_report.get("base_currency", "EUR")
        quote = context_report.get("quote_currency", "USD")
        bias = context_report.get("directional_bias", "NEUTRAL")
        dxy = context_report.get("dxy_trend", "NEUTRAL")
        return (
            f"[FOREX MACRO CONTEXT: {symbol}]\n"
            f"- Currency Pair: {base}/{quote}\n"
            f"- Directional Macro Bias: {bias}\n"
            f"- US Dollar (DXY) Structural Stance: {dxy}\n"
        )

    def evaluate_risk_rules(self, symbol: str, signal: str, context_report: Dict[str, Any]) -> Tuple[bool, str]:
        """Asset-specific risk rules for Forex pairs."""
        bias = context_report.get("directional_bias", "NEUTRAL")
        if bias != "NEUTRAL" and signal != "HOLD":
            if (bias == "BULLISH" and signal == "SELL") or (bias == "BEARISH" and signal == "BUY"):
                return True, f"Counter-trend to Macro {bias} (Allowed with scaled risk)"
        return True, "Forex macro risk clearance OK"
