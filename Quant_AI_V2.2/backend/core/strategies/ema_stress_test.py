# -*- coding: utf-8 -*-
"""
EMA Stress Test Strategy for system resilience & benchmark load testing.
"""

from typing import Dict, Any, List
import pandas as pd
from backend.core.strategies.base_strategy import (
    BaseStrategy,
    StrategySignal,
    ChecklistItem,
    ChecklistStatus,
)


class EMAStressTestStrategy(BaseStrategy):
    """
    EMA Dual Cross Strategy for system resilience & benchmark load testing.
    Standardized to BaseStrategy quantitative contract.
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.strategy_id = "builtin_ema_stress"
        self.name = "EMA Dual Cross"

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "id": self.strategy_id,
            "name": "EMA Dual Cross (Resilience Benchmark)",
            "description": "Fast EMA10 / Slow EMA50 crossover with dynamic risk sizing.",
            "author": "Quant AI Core",
            "version": "1.0",
            "checklist_schema": [
                {"key": "Trend Structure", "description": "Higher timeframe EMA slope direction"},
                {"key": "EMA Crossover", "description": "Fast EMA10 crossing Slow EMA50 trigger"},
                {"key": "Risk / Reward", "description": "Target Risk-to-Reward ratio compliance"},
            ],
        }

    def get_default_checklist(self) -> List[ChecklistItem]:
        return [
            ChecklistItem(key="Trend Structure", value="Awaiting Trend Direction", status=ChecklistStatus.PENDING),
            ChecklistItem(key="EMA Crossover", value="Awaiting EMA Crossover", status=ChecklistStatus.PENDING),
            ChecklistItem(key="Risk / Reward", value="Monitoring Volatility", status=ChecklistStatus.PENDING),
        ]

    def analyze(
        self, df: pd.DataFrame, macro_context: Dict = None
    ) -> StrategySignal:
        if df is None or len(df) < 50:
            default_chk = self.get_default_checklist()
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_name=self.name,
                action="HOLD",
                signal="HOLD",
                confidence=0.0,
                checklist=default_chk,
                metadata={"strategy": "EMA_Stress_Test", "checklist": [c.value for c in default_chk]},
            )

        close = df["close"]
        ema10 = close.ewm(span=10).mean()
        ema50 = close.ewm(span=50).mean()

        curr_10, curr_50 = float(ema10.iloc[-1]), float(ema50.iloc[-1])
        prev_10, prev_50 = float(ema10.iloc[-2]), float(ema50.iloc[-2])

        action = "HOLD"
        entry_price = float(close.iloc[-1])
        sl = None
        tp = None

        if curr_10 > curr_50 and prev_10 <= prev_50:
            action = "BUY"
            sl = entry_price * 0.99
            tp = entry_price * 1.02
            chk1 = "Trend Confirmed"
            chk2 = "EMA Cross Confirmed"
            chk3 = "Target RR Active"
            s1 = s2 = s3 = ChecklistStatus.PASSED
        elif curr_10 < curr_50 and prev_10 >= prev_50:
            action = "SELL"
            sl = entry_price * 1.01
            tp = entry_price * 0.98
            chk1 = "Trend Confirmed"
            chk2 = "EMA Cross Confirmed"
            chk3 = "Target RR Active"
            s1 = s2 = s3 = ChecklistStatus.PASSED
        else:
            chk1 = "Trend Confirmed" if curr_10 > curr_50 else "Awaiting Trend Direction"
            chk2 = "Awaiting EMA Crossover"
            chk3 = "Monitoring Volatility"
            s1 = ChecklistStatus.NEUTRAL if curr_10 > curr_50 else ChecklistStatus.PENDING
            s2 = ChecklistStatus.PENDING
            s3 = ChecklistStatus.PENDING

        checklist_items = [
            ChecklistItem(key="Trend Structure", value=chk1, status=s1),
            ChecklistItem(key="EMA Crossover", value=chk2, status=s2),
            ChecklistItem(key="Risk / Reward", value=chk3, status=s3),
        ]

        return StrategySignal(
            strategy_id=self.strategy_id,
            strategy_name=self.name,
            action=action,
            signal=action,
            entry_price=entry_price if action != "HOLD" else None,
            sl=sl,
            tp1=tp,
            confidence=0.85 if action != "HOLD" else 0.0,
            score=75.0 if action != "HOLD" else 30.0,
            checklist=checklist_items,
            metadata={"strategy": "EMA_Stress_Test", "checklist": [c.value for c in checklist_items]},
        )


__all__ = ["EMAStressTestStrategy"]
