# -*- coding: utf-8 -*-
"""
Equity Index Context Adapter (US30, NAS100, SPX500 Quant Engine).
Ingests Volatility (VIX Regime), Monetary Policy Stance, and Yield Pressures.
Leaves modular hooks for Earnings Season and Market Breadth.
"""
import time
from typing import Dict, Any, Tuple
from loguru import logger

from backend.infrastructure.data_providers.adapters.base_adapter import BaseContextAdapter
from backend.infrastructure.data_providers.macro.macro_regime import MacroRegimeEngine


class EquityIndexAdapter(BaseContextAdapter):
    """Institutional Equity Indices Context Adapter."""

    def __init__(self):
        self.macro_engine = MacroRegimeEngine()
        self.VIX_RISK_OFF_THRESHOLD = 22.0
        self.VIX_RISK_ON_THRESHOLD = 18.0

    def get_macro_bias(self, symbol: str) -> str:
        """
        Determines Equity Index bias based on VIX Volatility Regime & Fed Stance.
        """
        try:
            regime = self.macro_engine.get_current_regime()
            bias = regime.get("bias", "NEUTRAL").upper()
            vix = float(regime.get("vix", 20.0))

            if vix >= self.VIX_RISK_OFF_THRESHOLD:
                return "BEARISH"
            elif vix <= self.VIX_RISK_ON_THRESHOLD and bias in ["BULLISH", "NEUTRAL"]:
                return "BULLISH"
            return bias
        except Exception as e:
            logger.debug(f"[EquityIndexAdapter] get_macro_bias fallback: {e}")
            return "NEUTRAL"

    def generate_context_report(self, symbol: str) -> Dict[str, Any]:
        """Generates equity index context report."""
        try:
            regime = self.macro_engine.get_current_regime()
        except Exception:
            regime = {}

        bias = self.get_macro_bias(symbol)
        return {
            "symbol": symbol,
            "asset_class": "EQUITY_INDEX",
            "directional_bias": bias,
            "vix": regime.get("vix", 20.0),
            "fed_rate": regime.get("fed_rate", 5.25),
            "timestamp": time.time(),
        }

    def build_prompt_section(self, symbol: str, context_report: Dict[str, Any]) -> str:
        """Builds prompt section for LLM."""
        bias = context_report.get("directional_bias", "NEUTRAL")
        vix = context_report.get("vix", 20.0)
        return (
            f"[EQUITY INDEX CONTEXT: {symbol}]\n"
            f"- Directional Bias: {bias}\n"
            f"- Market Volatility (VIX): {vix:.2f}\n"
        )

    def evaluate_risk_rules(self, symbol: str, signal: str, context_report: Dict[str, Any]) -> Tuple[bool, str]:
        """Equity index risk filters (e.g. Extreme VIX shock blocks new long positions)."""
        vix = float(context_report.get("vix", 20.0))
        if vix >= 30.0 and signal == "BUY":
            return False, f"VIX Market Panic ({vix:.1f} >= 30.0) - Long positions blocked"
        return True, "Equity risk clearance OK"
