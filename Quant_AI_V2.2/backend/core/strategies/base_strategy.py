# -*- coding: utf-8 -*-
"""
Quant AI V2.2 - Institutional Strategy Contract & Data Transfer Objects (DTO)
Core Strategy Pattern implementation following Open-Closed Principle (OCP).
All quantitative strategies must inherit from BaseStrategy and emit StrategySignal DTOs.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional
import pandas as pd


class ChecklistStatus(str, Enum):
    """Execution compliance status for each checklist condition."""
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    NEUTRAL = "NEUTRAL"


@dataclass
class ChecklistItem:
    """Represents a self-describing criterion row in the Trading Plan."""
    key: str
    value: str
    status: ChecklistStatus = ChecklistStatus.PENDING

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "status": self.status.value if isinstance(self.status, ChecklistStatus) else str(self.status),
        }

    def __getitem__(self, item):
        return self.to_dict()[item]

    def get(self, item, default=None):
        return self.to_dict().get(item, default)

    def __contains__(self, key: str) -> bool:
        return key in self.to_dict()

    def __iter__(self):
        return iter(self.to_dict())

    def items(self):
        return self.to_dict().items()

    def keys(self):
        return self.to_dict().keys()

    def values(self):
        return self.to_dict().values()


@dataclass
class StrategySignal:
    """Standardized quantitative signal emitted by any strategy algorithm."""
    strategy_id: str
    strategy_name: str
    action: str  # "BUY", "SELL", "HOLD"
    signal: str = ""
    entry_price: Optional[float] = None
    sl: Optional[float] = None
    tp1: Optional[float] = None
    tp2: Optional[float] = None
    confidence: float = 0.0
    score: float = 0.0
    checklist: List[ChecklistItem] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.signal:
            self.signal = self.action

    def to_dict(self) -> Dict[str, Any]:
        """Provides full backwards compatibility with legacy dictionary consumers."""
        strat_key = self.metadata.get("strategy") if isinstance(self.metadata, dict) else None
        return {
            "strategy": strat_key or self.strategy_id,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "action": self.action,
            "signal": self.signal,
            "entry_price": self.entry_price,
            "sl": self.sl,
            "tp1": self.tp1,
            "tp2": self.tp2,
            "confidence": self.confidence,
            "score": self.score,
            "checklist": [c.to_dict() if hasattr(c, "to_dict") else c for c in self.checklist],
            "metadata": self.metadata,
        }

    def __getitem__(self, item):
        return self.to_dict()[item]

    def get(self, item, default=None):
        return self.to_dict().get(item, default)

    def __contains__(self, key: str) -> bool:
        return key in self.to_dict()

    def __iter__(self):
        return iter(self.to_dict())

    def items(self):
        return self.to_dict().items()

    def keys(self):
        return self.to_dict().keys()

    def values(self):
        return self.to_dict().values()


class BaseStrategy(ABC):
    """
    Abstract Base Class defining the contract for all quantitative trading models.
    Decouples strategies completely from chart visualization and execution routing.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.strategy_id = getattr(self, "strategy_id", self.__class__.__name__)
        self.name = getattr(self, "name", self.__class__.__name__)

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Returns strategy metadata, parameters, and description."""
        pass

    @abstractmethod
    def get_default_checklist(self) -> List[ChecklistItem]:
        """Returns baseline schema checklist items displayed in standby mode."""
        pass

    def get_active_checklist(self, action: str = "BUY") -> List[ChecklistItem]:
        """Returns schema checklist items when an active order setup is triggered."""
        defaults = self.get_default_checklist()
        for item in defaults:
            item.status = ChecklistStatus.PASSED
        return defaults

    @abstractmethod
    def analyze(
        self, df: pd.DataFrame, macro_context: Dict[str, Any] = None
    ) -> StrategySignal:
        """
        Executes strategy logic on OHLCV bars and returns a typed StrategySignal.
        Must not raise unhandled exceptions on incomplete or edge-case market data.
        """
        pass


__all__ = [
    "ChecklistStatus",
    "ChecklistItem",
    "StrategySignal",
    "BaseStrategy",
]
