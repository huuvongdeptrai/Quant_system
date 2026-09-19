"""
GIAI ĐOẠN 6: BACKTESTING KHÔNG THIÊN KIẾN (UNBIASED HISTORICAL BACKTESTING)
Đồ án Tốt nghiệp - Trường Đại học Giao thông vận tải TP.HCM (UTH)
Hệ thống: Quant AI V2.2 - Kiểm định Chiến lược với Chi phí thực tế (Commission & Slippage)
"""

import pytest
import pandas as pd
import numpy as np
from research.backtest_vectorized import VectorizedBacktester
from infrastructure.brokers.mt5_safe import mt5


def get_large_historical_sample(n=5000):
    if mt5.initialize():
        rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_H1, 0, n)
        if rates is not None and len(rates) >= 500:
            df = pd.DataFrame(rates)
            df["time"] = pd.to_datetime(df["time"], unit="s")
            return df

    np.random.seed(42)
    dt = 1 / 252
    mu = 0.08
    sigma = 0.16
    prices = [2000.0]
    for _ in range(n):
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
    return df


class TestStage6UnbiasedBacktest:
    def test_unbiased_backtest_with_commission_and_slippage(self):
        """
        KIỂM ĐỊNH HIỆU NĂNG KHÔNG THIÊN KIẾN (REAL-WORLD FRICTIONS):
        - Phí hoa hồng sàn ECN (Commission): $7.0 USD / round-turn lot.
        - Trượt giá khớp lệnh (Slippage): 0.02% giá trị rủi ro.
        Tiêu chuẩn:
        - Tổng lợi nhuận ròng sau phí bắt buộc phải DƯƠNG.
        - Max Drawdown < 10.0% (Chuẩn Quỹ Prop-Firm).
        - Kỳ vọng toán học (Expectancy) sau phí bắt buộc phải DƯƠNG.
        """
        df = get_large_historical_sample(n=5000)

        # Thiết lập mô phỏng ma sát thực tế
        backtester = VectorizedBacktester(
            initial_balance=100000.0,
            risk_per_trade_pct=1.0,
            commission_per_trade=7.0,  # $7 USD / round-turn
            slippage_pct=0.02,  # 20 points trượt giá
        )
        report = backtester.run(df, target_rr=2.5)

        assert report is not None
        assert report.total_trades >= 10
        assert (
            report.total_net_profit > 0
        ), f"Lợi nhuận ròng {report.total_net_profit} phải dương sau phí"
        assert (
            report.max_drawdown_pct < 10.0
        ), f"Max Drawdown {report.max_drawdown_pct}% vượt ngưỡng an toàn quỹ (<10%)"
        assert (
            report.mathematical_expectancy > 0
        ), f"Kỳ vọng toán học {report.mathematical_expectancy} phải dương"
        assert (
            report.sharpe_ratio > 1.0
        ), f"Chỉ số Sharpe {report.sharpe_ratio} phải > 1.0"

        print("\n" + "=" * 65)
        print("   UNBIASED BACKTEST REPORT (WITH COMMISSION & SLIPPAGE)")
        print("=" * 65)
        print(f" Sample Size (Historical H1) : {report.sample_size:,} bars")
        print(f" Initial Balance             : ${report.initial_balance:,.2f}")
        print(f" Final Equity                : ${report.final_equity:,.2f}")
        print(
            f" Net Profit (After Frictions): ${report.total_net_profit:,.2f} ({report.total_return_pct:+.2f}%)"
        )
        print(f" Total Commission & Slippage : ${report.total_commission_paid:,.2f}")
        print(
            f" Max Drawdown (Peak to Base) : ${report.max_drawdown_dollars:,.2f} ({report.max_drawdown_pct:.2f}%)"
        )
        print(f" Sharpe Ratio (Annualized)   : {report.sharpe_ratio:.2f}")
        print(f" Sortino Ratio               : {report.sortino_ratio:.2f}")
        print(f" Profit Factor (Net)         : {report.profit_factor:.2f}")
        print(f" Total Trades Executed       : {report.total_trades} trades")
        print(
            f" Win Rate                    : {report.win_rate_pct:.2f}% (R:R 1:{report.risk_reward_ratio:.2f})"
        )
        print(
            f" Mathematical Expectancy     : +${report.mathematical_expectancy:,.2f} / trade"
        )
        print(f" Matrix Compute Time         : {report.execution_time_ms:.2f} ms")
        print("=" * 65)
