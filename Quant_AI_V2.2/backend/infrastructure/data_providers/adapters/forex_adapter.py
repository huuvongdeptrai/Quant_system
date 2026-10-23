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
        Computes directional bias (BULLISH, BEARISH, NEUTRAL) for any Forex pair.
        """
        base_curr, quote_curr = self.parse_currency_pair(symbol)
        
        # 1. DXY Vector Component
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

        # 2. Economic Surprise Component from Calendar
        try:
            events = self.calendar_engine.fetch_events()
        except Exception:
            events = []

        base_surprise = self._calculate_surprise_momentum(base_curr, events)
        quote_surprise = self._calculate_surprise_momentum(quote_curr, events)

        net_surprise = base_surprise - quote_surprise
        total_score = (usd_component * 1.0) + (net_surprise * 0.5)

        if total_score >= 0.75:
            return "BULLISH"
        elif total_score <= -0.75:
            return "BEARISH"
        return "NEUTRAL"

    def generate_context_report(self, symbol: str) -> Dict[str, Any]:
        """Generates structured multi-currency macro context report."""
        base_curr, quote_curr = self.parse_currency_pair(symbol)
        bias = self.get_macro_bias(symbol)
        dxy_bias = self._get_dxy_trend()

        return {
            "symbol": symbol,
            "asset_class": "FOREX",
            "base_currency": base_curr,
            "quote_currency": quote_curr,
            "directional_bias": bias,
            "dxy_trend": dxy_bias,
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
