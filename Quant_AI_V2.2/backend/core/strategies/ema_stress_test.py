# -*- coding: utf-8 -*-
"""
EMA Stress Test Strategy for system resilience & benchmark load testing.
"""

from typing import Dict, Any
import pandas as pd


class EMAStressTestStrategy:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.name = "EMA_Stress_Test"

    def analyze(self, df: pd.DataFrame, macro_context: Dict = None) -> Dict:
        if df is None or len(df) < 50:
            return {
                "strategy": self.name,
                "signal": "HOLD",
                "confidence": 0.0
            }

        close = df["close"]
        ema10 = close.ewm(span=10).mean()
        ema50 = close.ewm(span=50).mean()

        curr_10, curr_50 = ema10.iloc[-1], ema50.iloc[-1]
        prev_10, prev_50 = ema10.iloc[-2], ema50.iloc[-2]

        action = "HOLD"
        if curr_10 > curr_50 and prev_10 <= prev_50:
            action = "BUY"
        elif curr_10 < curr_50 and prev_10 >= prev_50:
            action = "SELL"

        return {
            "strategy": self.name,
            "signal": action,
            "entry_price": float(close.iloc[-1]),
            "confidence": 0.85 if action != "HOLD" else 0.0
        }


__all__ = ["EMAStressTestStrategy"]
