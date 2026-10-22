# -*- coding: utf-8 -*-
"""
Custom User Strategy Example: ICT Fair Value Gap (FVG) Sniper
Quant AI V2.2 Template
"""

import pandas as pd
from typing import Dict, Any

class CustomICTFVGStrategy:
    """ICT FVG Breakout & Retest Model."""
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.name = "Custom ICT FVG Sniper"
        self.rr_ratio = self.config.get("rr_ratio", 2.5)

    def analyze(self, df: pd.DataFrame, macro_context: Dict = None) -> Dict[str, Any]:
        """
        Input: OHLCV DataFrame
        Output: Signal dict with 'strategy', 'signal' ('BUY'/'SELL'/'HOLD'), 'confidence', 'sl_price', 'tp_price'
        """
        if df is None or len(df) < 30:
            return {"strategy": self.name, "signal": "HOLD", "confidence": 0.0}

        close = df["close"].iloc[-1]
        c_prev = df["close"].iloc[-2]
        c_prev2 = df["close"].iloc[-3]
        high_prev2 = df["high"].iloc[-3]
        low_prev = df["low"].iloc[-1]

        signal = "HOLD"
        confidence = 0.0

        # Bullish FVG condition: low[-1] > high[-3]
        if low_prev > high_prev2 and c_prev > high_prev2:
            signal = "BUY"
            confidence = 0.82
            sl = float(df["low"].iloc[-3])
            tp = float(close + (close - sl) * self.rr_ratio)
            return {
                "strategy": self.name,
                "signal": signal,
                "entry_price": float(close),
                "confidence": confidence,
                "sl_price": sl,
                "tp_price": tp,
            }

        return {"strategy": self.name, "signal": "HOLD", "confidence": 0.0}
