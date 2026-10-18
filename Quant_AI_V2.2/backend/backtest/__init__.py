"""
Backend Backtesting Package - High-performance vectorized and event-driven backtesting engines.
Centralized Quantitative Subsystem: Single Source of Truth for Backtesting.
"""

from .backtest_vectorized import (
    VectorizedBacktester,
    BacktestReport,
    get_symbol_multiplier,
)
from .backtest_ict_pro import (
    EventDrivenBacktester,
    ICTProBacktester,
    run_ict_pro_backtest,
)
from .backtest_engine import (
    BacktestWorker,
)

__all__ = [
    "VectorizedBacktester",
    "EventDrivenBacktester",
    "ICTProBacktester",
    "run_ict_pro_backtest",
    "BacktestWorker",
    "BacktestReport",
    "get_symbol_multiplier",
]
