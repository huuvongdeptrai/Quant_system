"""
Re-export wrapper for VectorizedBacktester.
Preserves backward compatibility while pointing to the single source of truth.
Single Source of Truth: backend.backtest.backtest_vectorized
"""

from .backtest_vectorized import (
    VectorizedBacktester,
    BacktestReport,
    get_symbol_multiplier,
)

__all__ = [
    "VectorizedBacktester",
    "BacktestReport",
    "get_symbol_multiplier",
]
