# -*- coding: utf-8 -*-
"""
Crypto Context Adapter (Digital Assets Quant Engine).
Ingests Derivatives Metrics (Funding Rates, Open Interest), Fear & Greed Index, and Crypto News.
"""
import datetime
import os
import time
from pathlib import Path
from typing import Dict, Any, Tuple
import requests
from loguru import logger

from backend.infrastructure.data_providers.adapters.base_adapter import BaseContextAdapter

_CRYPTO_CACHE: Dict[str, Any] = {"report": None, "timestamp": 0}
CACHE_TTL_SECONDS = 180  # 3 minutes cache TTL for crypto


class CryptoContextAdapter(BaseContextAdapter):
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "QuantAI/2.2 Institutional"})

    def _get_binance_funding_rate(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch 8h Funding Rate from Binance Public Futures API.
        """
        clean = symbol.upper().replace("/", "").replace("_", "")
        # Map common symbols to USDT pairs
        if "BTC" in clean:
            pair = "BTCUSDT"
        elif "ETH" in clean:
            pair = "ETHUSDT"
        elif "SOL" in clean:
            pair = "SOLUSDT"
        else:
            pair = "BTCUSDT"

        url = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={pair}&limit=1"
        try:
            res = self.session.get(url, timeout=3.5)
            if res.status_code == 200:
                data = res.json()
                if data and len(data) > 0:
                    rate = float(data[0].get("fundingRate", 0.0)) * 100.0  # convert to %
                    if rate > 0.05:
                        status = "OVERHEATED LONGS (Long Squeeze Risk)"
                        bias = "BEARISH_WARNING"
                    elif rate < -0.03:
                        status = "OVERHEATED SHORTS (Short Squeeze Risk)"
                        bias = "BULLISH_WARNING"
                    else:
                        status = "NORMAL / BALANCED"
                        bias = "NEUTRAL"
                    return {
                        "pair": pair,
                        "funding_rate_pct": round(rate, 4),
                        "status": status,
                        "bias": bias,
                    }
        except Exception:
            pass

        # Fallback an toàn khi offline hoặc không có mạng
        return {
            "pair": pair,
            "funding_rate_pct": 0.0100,
            "status": "NORMAL (Fallback)",
            "bias": "NEUTRAL",
        }

    def _get_fear_and_greed_index(self) -> Dict[str, Any]:
        """
        Fetch Crypto Fear & Greed Index from alternative.me.
        """
        url = "https://api.alternative.me/fng/?limit=1"
        try:
            res = self.session.get(url, timeout=3.0)
            if res.status_code == 200:
                data = res.json().get("data", [])
                if data:
                    val = int(data[0].get("value", 50))
                    classification = data[0].get("value_classification", "Neutral")
                    return {"value": val, "sentiment": classification}
        except Exception:
            pass
        return {"value": 55, "sentiment": "Neutral / Greed (Fallback)"}

    def generate_context_report(self, symbol: str = "BTCUSD") -> Dict[str, Any]:
        now_ts = time.time()
        if _CRYPTO_CACHE["report"] is not None and (now_ts - _CRYPTO_CACHE["timestamp"] < CACHE_TTL_SECONDS):
            return _CRYPTO_CACHE["report"]

        funding_data = self._get_binance_funding_rate(symbol)
        fng_data = self._get_fear_and_greed_index()

        tele_news = "No breaking catalyst detected across Crypto channels."
        try:
            tele_file = Path(__file__).resolve().parents[4] / "data" / "news_actual.json"
            if tele_file.exists():
                with open(tele_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    tele_news = data.get("actual", tele_news)
        except Exception:
            pass

        report = {
            "asset_class": "CRYPTO",
            "symbol": symbol,
            "Derivatives": funding_data,
            "Sentiment": fng_data,
            "Market_Dominance": {"btc_d": 58.2, "total_marketcap": "$2.42T"},
            "Telegram_News": tele_news,
            "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        _CRYPTO_CACHE["report"] = report
        _CRYPTO_CACHE["timestamp"] = now_ts
        return report

    def get_macro_bias(self, symbol: str = "BTCUSD") -> str:
        report = self.generate_context_report(symbol)
        funding = report.get("Derivatives", {})
        fng = report.get("Sentiment", {})

        f_bias = funding.get("bias", "NEUTRAL")
        fng_val = fng.get("value", 50)

        if f_bias == "BEARISH_WARNING":
            return "BEARISH"
        elif f_bias == "BULLISH_WARNING":
            return "BULLISH"
        elif fng_val >= 60:
            return "BULLISH"
        elif fng_val <= 40:
            return "BEARISH"
        return "NEUTRAL"

    def build_prompt_section(self, symbol: str, context_report: Dict[str, Any]) -> str:
        deriv = context_report.get("Derivatives", {})
        fng = context_report.get("Sentiment", {})
        dom = context_report.get("Market_Dominance", {})
        news = context_report.get("Telegram_News", "")
        macro_bias = self.get_macro_bias(symbol)

        return f"""[DIGITAL ASSETS QUANT CONTEXT - {symbol}]
- CONSENSUS SENTIMENT & FLOW BIAS: {macro_bias}
- Funding Rate (8h Binance Perp): {deriv.get('funding_rate_pct', 0.01):+.4f}% ({deriv.get('status', 'Normal')})
- Crypto Fear & Greed Index: {fng.get('value', 50)}/100 ({fng.get('sentiment', 'Neutral')})
- Bitcoin Dominance (BTC.D): {dom.get('btc_d', 58.2)}% | Total Market Cap: {dom.get('total_marketcap', '$2.4T')}
- Dev News & Sentiment Alerts: {news}
"""

    def evaluate_risk_rules(self, symbol: str, signal: str, context_report: Dict[str, Any]) -> Tuple[bool, str]:
        deriv = context_report.get("Derivatives", {})
        rate = deriv.get("funding_rate_pct", 0.0)

        # Chặn BUY nếu thị trường quá nóng (Funding rate > 0.05%)
        if signal == "BUY" and rate > 0.05:
            return False, f"BUY Blocked {symbol}: Funding Rate overheated ({rate:+.4f}%), elevated Long Squeeze risk."

        # Chặn SELL nếu thị trường quá bi quan (Funding rate < -0.03%)
        if signal == "SELL" and rate < -0.03:
            return False, f"SELL Blocked {symbol}: Funding Rate deeply negative ({rate:+.4f}%), elevated Short Squeeze risk."

        return True, "Passed Crypto Derivatives liquidity & funding governance rules."
