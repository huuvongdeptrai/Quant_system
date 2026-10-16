"""
GIAI ĐOẠN 2: TEST HIỆU NĂNG QUÁ KHỨ (BACKTESTING ON LARGE SAMPLE SIZE)
Đồ án Tốt nghiệp - Trường Đại học Giao thông vận tải TP.HCM (UTH)
Hệ thống: Quant AI V2.2 - Kiểm định chỉ số Quỹ Prop-Firm & Tính toán Ma trận
"""

import sys
import io
import pytest
import pandas as pd
import numpy as np
from research.backtest_vectorized import VectorizedBacktester
from backend.infrastructure.brokers.mt5_safe import mt5


def get_or_create_historical_data(n=5000):
    """Lấy dữ liệu thực từ MT5 XAUUSD hoặc sinh mẫu hình ngẫu nhiên nếu MT5 offline."""
    try:
        import psutil
        is_running = any("terminal" in p.name().lower() or "metatrader" in p.name().lower() for p in psutil.process_iter(["name"]))
    except Exception:
        is_running = False

    if is_running and mt5.initialize():
        rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_H1, 0, n)
        if rates is not None and len(rates) >= 500:
            df = pd.DataFrame(rates)
            df["time"] = pd.to_datetime(df["time"], unit="s")
            return df

    np.random.seed(42)
    dt = 1 / 252
    mu = 0.12
    sigma = 0.14
    prices = [2000.0]
    for _ in range(n):
        ret = np.random.normal((mu - 0.5 * sigma**2) * dt, sigma * np.sqrt(dt))
        prices.append(prices[-1] * np.exp(ret))

    highs = [p * (1 + abs(np.random.normal(0, 0.002))) for p in prices]
    lows = [p * (1 - abs(np.random.normal(0, 0.002))) for p in prices]
    vols = [1000.0 * (1.0 + abs(np.random.normal(0, 0.4))) for _ in prices]
    df = pd.DataFrame({"close": prices, "high": highs, "low": lows, "tick_volume": vols})
    return df


class TestStage2Backtest:
    def test_backtest_performance_metrics(self):
        df = get_or_create_historical_data(n=5000)
        backtester = VectorizedBacktester(
            initial_balance=100000.0, risk_per_trade_pct=1.0
        )
        report = backtester.run(df, target_rr=2.5)

        assert report is not None, "Bao cao Backtest khong duoc rong"
        assert (
            report.total_trades >= 10
        ), "Can toi thieu 10 lenh de danh gia mau thong ke"

        # 1. Tốc độ thực thi cho máy 8GB RAM (< 200 ms cho 5000 nến)
        assert (
            report.execution_time_ms < 200.0
        ), f"Execution time {report.execution_time_ms} ms qua cham"

        # 2. Tiêu chuẩn Quỹ Prop-Firm: Max Drawdown < 10%
        assert (
            report.max_drawdown_pct < 10.0
        ), f"Max Drawdown {report.max_drawdown_pct}% vuot 10%"

        # 3. Kỳ vọng toán học (Expectancy) bắt buộc phải DƯƠNG
        assert (
            report.mathematical_expectancy > 0
        ), f"Expectancy {report.mathematical_expectancy} phai duong"

        # 4. Tỷ lệ Sharpe Ratio > 1.0
        assert report.sharpe_ratio > 1.0, f"Sharpe {report.sharpe_ratio} phai > 1.0"

        # In kết quả chuẩn định dạng ASCII an toàn cho console Windows
        print("\n" + "=" * 65)
        print("   QUANTITATIVE BACKTEST REPORT (VECTORIZED MATRIX - 8GB RAM)")
        print("=" * 65)
        print(f" Sample Size (Candles)       : {report.sample_size:,} bars")
        print(f" Initial Balance             : ${report.initial_balance:,.2f}")
        print(f" Final Equity                : ${report.final_equity:,.2f}")
        print(
            f" Total Net Profit            : ${report.total_net_profit:,.2f} ({report.total_return_pct:+.2f}%)"
        )
        print(
            f" Max Drawdown (Peak to Trough): ${report.max_drawdown_dollars:,.2f} ({report.max_drawdown_pct:.2f}%)"
        )
        print(f" Sharpe Ratio (Annualized)   : {report.sharpe_ratio:.2f}")
        print(f" Sortino Ratio (Downside)    : {report.sortino_ratio:.2f}")
        print(f" Profit Factor               : {report.profit_factor:.2f}")
        print(f" Total Trades Executed       : {report.total_trades}")
        print(
            f" Win / Loss Count            : {report.win_trades} Wins / {report.loss_trades} Losses"
        )
        print(f" Win Rate                    : {report.win_rate_pct:.2f}%")
        print(
            f" Average Win / Average Loss  : ${report.avg_win:,.2f} / ${report.avg_loss:,.2f}"
        )
        print(f" Realized Risk:Reward Ratio  : 1:{report.risk_reward_ratio:.2f}")
        print(
            f" Mathematical Expectancy     : ${report.mathematical_expectancy:,.2f} / trade"
        )
        print(f" Matrix Execution Time       : {report.execution_time_ms:.2f} ms")
        print("=" * 65)
