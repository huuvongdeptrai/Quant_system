"""
Research Entry Point: Vectorized Backtester.
Re-exports from the unified backend backtesting package: backend.backtest
Preserves single source of truth across the terminal and research scripts.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.backtest import (
    VectorizedBacktester,
    BacktestReport,
    get_symbol_multiplier,
)
from backend.core.strategies.wyckoff_vectorized import WyckoffMomentumStrategy

__all__ = [
    "VectorizedBacktester",
    "WyckoffMomentumStrategy",
    "BacktestReport",
    "get_symbol_multiplier",
]

if __name__ == "__main__":
    from backend.infrastructure.brokers.mt5_safe import mt5

    print("Running Vectorized NumPy Backtest on XAUUSD H1 (5,000 bars)...")
    df = None
    if mt5.initialize():
        rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_H1, 0, 5000)
        if rates is not None and len(rates) >= 500:
            df = pd.DataFrame(rates)
            df["time"] = pd.to_datetime(df["time"], unit="s")

    if df is None:
        np.random.seed(42)
        dt = 1 / 252
        mu = 0.08
        sigma = 0.16
        prices = [2000.0]
        for _ in range(5000):
            ret = np.random.normal((mu - 0.5 * sigma**2) * dt, sigma * np.sqrt(dt))
            prices.append(prices[-1] * np.exp(ret))
        highs = [p * (1 + abs(np.random.normal(0, 0.003))) for p in prices]
        lows = [p * (1 - abs(np.random.normal(0, 0.003))) for p in prices]
        df = pd.DataFrame(
            {
                "close": prices,
                "high": highs,
                "low": lows,
                "tick_volume": np.ones(len(prices)) * 1200,
            }
        )

    bt = VectorizedBacktester(
        initial_balance=100000.0,
        risk_per_trade_pct=1.0,
        commission_per_trade=7.0,
        slippage_pct=0.0002,
    )
    rep = bt.run(df, target_rr=2.5)

    print("\n" + "=" * 65)
    print("   VECTORIZED NUMPY BACKTEST REPORT (UNBIASED H1)")
    print("=" * 65)
    print(f" Sample Size (H1 Bars)       : {rep.sample_size:,} bars (~1 year)")
    print(f" Initial Balance             : {rep.initial_balance:,.2f} USD")
    print(f" Final Equity                : {rep.final_equity:,.2f} USD")
    print(
        f" Total Net Profit            : +{rep.total_net_profit:,.2f} USD (+{rep.total_return_pct:.2f}%)"
    )
    print(
        f" Win Rate                    : {rep.win_rate_pct:.2f}% ({rep.win_trades} Wins / {rep.loss_trades} Losses)"
    )
    print(
        f" Max Drawdown                : {rep.max_drawdown_pct:.2f}% ({rep.max_drawdown_dollars:,.2f} USD)"
    )
    print(f" Sharpe Ratio                : {rep.sharpe_ratio:.2f}")
    print(f" Profit Factor               : {rep.profit_factor:.2f}")
    print(
        f" Average Win / Loss          : {rep.avg_win:,.2f} USD / {rep.avg_loss:,.2f} USD (R:R {rep.risk_reward_ratio:.2f})"
    )
    print(
        f" Mathematical Expectancy     : +{rep.mathematical_expectancy:,.2f} USD / trade"
    )
    print(f" Total Commission Paid       : {rep.total_commission_paid:,.2f} USD")
    print(f" Execution Time (Pure Matrix): {rep.execution_time_ms:.2f} ms")
    print("=" * 65)
