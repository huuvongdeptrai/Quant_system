"""
Re-export wrapper for EventDrivenBacktester and ICTProBacktester.
Preserves backward compatibility while pointing to the single source of truth.
Single Source of Truth: backend.backtest.backtest_ict_pro
"""

from .backtest_ict_pro import (
    EventDrivenBacktester,
    ICTProBacktester,
    run_ict_pro_backtest,
    BacktestReport,
    get_symbol_multiplier,
)

__all__ = [
    "EventDrivenBacktester",
    "ICTProBacktester",
    "run_ict_pro_backtest",
    "BacktestReport",
    "get_symbol_multiplier",
]
