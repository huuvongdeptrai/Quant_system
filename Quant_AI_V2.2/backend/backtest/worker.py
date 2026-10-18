"""
Re-export wrapper for BacktestWorker.
Preserves backward compatibility while pointing to the single source of truth.
Single Source of Truth: backend.backtest.backtest_engine
"""

from .backtest_engine import (
    BacktestWorker,
    get_symbol_multiplier,
)

__all__ = [
    "BacktestWorker",
    "get_symbol_multiplier",
]
