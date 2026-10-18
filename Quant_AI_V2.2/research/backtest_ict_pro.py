"""
ĐỘNG CƠ BACKTEST SỰ KIỆN TRỰC TIẾP (EVENT-DRIVEN BACKTESTER FOR ICT ZONES PRO)
=============================================================================
Đồ án Tốt nghiệp - Trường Đại học Giao thông vận tải TP.HCM (UTH)
Hệ thống: Quant AI V2.2 - Kiểm định Chiến lược Thực chiến ICT Trading Zones Pro
"""

import sys
from pathlib import Path

# Thêm thư mục gốc dự án vào sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.backtest.backtest_ict_pro import (
    ICTProBacktester,
    run_ict_pro_backtest,
    BacktestReport,
    get_symbol_multiplier,
)

if __name__ == "__main__":
    print("Running Event-Driven ICT Zones Pro Backtest on M15...")
    res = run_ict_pro_backtest(bars=1500)
    if "error" in res:
        print(f"Error: {res['error']}")
    else:
        print("\n" + "=" * 65)
        print("   ICT ZONES PRO REAL EVENT-DRIVEN BACKTEST REPORT (M15)")
        print("=" * 65)
        print(f" Sample Size (M15 Bars)      : {res['bars_tested']:,} bars (~2 months)")
        print(f" Initial Balance             : {res['initial_balance']:,.2f} USD")
        print(f" Final Equity                : {res['final_equity']:,.2f} USD")
        sign = "+" if res['net_profit_usd'] >= 0 else "-"
        print(
            f" Total Net Profit            : {sign}${abs(res['net_profit_usd']):,.2f} USD ({sign}{abs(res['return_pct']):.2f}%)"
        )
        print(
            f" Win Rate                    : {res['win_rate_pct']:.2f}% ({res['wins']} Wins / {res['losses']} Losses)"
        )
        print(f" Total Trades                : {res['total_trades']} trades")
        print(f" Profit Factor               : {res['profit_factor']:.2f}")
        print(f" Sharpe Ratio                : {res['sharpe_ratio']:.2f}")
        print(f" Max Drawdown                : {res['max_drawdown_pct']:.2f}%")
        print(
            f" Average Win / Loss          : ${res['avg_win_usd']:,.2f} / ${res['avg_loss_usd']:,.2f}"
        )
        print(f" Total Commission & Friction : ${res['total_commission_paid']:,.2f}")
        print(f" Mathematical Expectancy     : ${res['expectancy_usd']:,.2f} / trade")
        print(f" Event Execution Time        : {res['exec_time_seconds']:.2f} seconds")
        print("=" * 65)
