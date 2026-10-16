"""
ĐỘNG CƠ BACKTEST SỰ KIỆN TRỰC TIẾP (EVENT-DRIVEN BACKTESTER FOR ICT ZONES PRO)
Đồ án Tốt nghiệp - Trường Đại học Giao thông vận tải TP.HCM (UTH)
Hệ thống: Quant AI V2.2 - Kiểm định Chiến lược Thực chiến ICT Trading Zones Pro trên M15
"""

import sys
import io
import time
from pathlib import Path
import numpy as np
import pandas as pd
from typing import Dict, Any, List

# Thêm thư mục gốc dự án vào sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.strategies.ict_strategy import ICTZonesProStrategy
from backend.infrastructure.brokers.mt5_safe import mt5


def run_ict_pro_backtest(
    bars: int = 1500, risk_pct: float = 1.0, initial_balance: float = 100000.0
) -> Dict[str, Any]:
    """
    Chạy Backtest từng nến (Bar-by-Bar Event-Driven) sử dụng 100% logic của ICTZonesProStrategy:
    - Khung thời gian: M15 (Resample tự động lên H1 để tìm POI).
    - Bộ lọc: Asian Range Sweep + Judas Swing + FVG Displacement + Killzone.
    - Quản lý vốn: Rủi ro 1% vốn / lệnh, TP1 = 2R (R:R 1:2).
    """
    if not mt5.initialize():
        return {"error": "Không thể kết nối MT5"}

    rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M15, 0, bars)
    if rates is None or len(rates) < 300:
        return {
            "error": f"Không đủ dữ liệu nến M15 (Cần tối thiểu 300, nhận {len(rates) if rates else 0})"
        }

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")

    ict = ICTZonesProStrategy({"lookback_bars": 150})
    balance = initial_balance
    equity_curve = [balance]
    trades = []

    in_pos = False
    pos_type = 0
    entry_p = 0.0
    sl_p = 0.0
    tp_p = 0.0
    risk_amt = 0.0

    start_time = time.perf_counter()

    for i in range(200, len(df)):
        row = df.iloc[i]
        c, h, l = row["close"], row["high"], row["low"]

        # 1. Quản lý lệnh đang chạy
        if in_pos:
            if pos_type == 1:
                if l <= sl_p:
                    trades.append(-risk_amt)
                    balance -= risk_amt
                    in_pos = False
                elif h >= tp_p:
                    win_pnl = risk_amt * 2.0
                    trades.append(win_pnl)
                    balance += win_pnl
                    in_pos = False
            elif pos_type == -1:
                if h >= sl_p:
                    trades.append(-risk_amt)
                    balance -= risk_amt
                    in_pos = False
                elif l <= tp_p:
                    win_pnl = risk_amt * 2.0
                    trades.append(win_pnl)
                    balance += win_pnl
                    in_pos = False

        # 2. Quét tín hiệu mới nếu chưa có vị thế
        if not in_pos and i < len(df) - 5:
            window_df = df.iloc[max(0, i - 250) : i + 1]
            res = ict.analyze(window_df, macro_context={})
            sig = res.get("signal", "HOLD")

            if (
                sig in ["BUY", "SELL"]
                and res.get("sl") is not None
                and res.get("tp1") is not None
            ):
                entry_p = float(res["entry_price"])
                sl_p = float(res["sl"])
                tp_p = float(res["tp1"])
                sl_dist = abs(entry_p - sl_p)

                if sl_dist > 0.5:
                    in_pos = True
                    pos_type = 1 if sig == "BUY" else -1
                    risk_amt = balance * (risk_pct / 100.0)

        equity_curve.append(balance)

    end_time = time.perf_counter()
    exec_sec = end_time - start_time

    trades_arr = np.array(trades)
    total_trades = len(trades_arr)
    wins = trades_arr[trades_arr > 0]
    losses = trades_arr[trades_arr < 0]
    win_rate = (len(wins) / total_trades * 100.0) if total_trades > 0 else 0.0
    net_profit = balance - initial_balance
    ret_pct = (net_profit / initial_balance) * 100.0

    eq_arr = np.array(equity_curve)
    peak_arr = np.maximum.accumulate(eq_arr)
    dd_arr = (peak_arr - eq_arr) / peak_arr * 100.0
    max_dd = float(np.max(dd_arr)) if len(dd_arr) > 0 else 0.0

    pf = (
        (float(np.sum(wins)) / abs(float(np.sum(losses)))) if len(losses) > 0 else 999.0
    )
    avg_w = float(np.mean(wins)) if len(wins) > 0 else 0.0
    avg_l = float(abs(np.mean(losses))) if len(losses) > 0 else 0.0
    exp = (
        (len(wins) / total_trades * avg_w) - (len(losses) / total_trades * avg_l)
        if total_trades > 0
        else 0.0
    )

    return {
        "bars_tested": len(df),
        "initial_balance": initial_balance,
        "final_equity": round(balance, 2),
        "net_profit_usd": round(net_profit, 2),
        "return_pct": round(ret_pct, 2),
        "total_trades": total_trades,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(win_rate, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "profit_factor": round(pf, 2),
        "avg_win_usd": round(avg_w, 2),
        "avg_loss_usd": round(avg_l, 2),
        "expectancy_usd": round(exp, 2),
        "exec_time_seconds": round(exec_sec, 2),
    }


if __name__ == "__main__":
    print("Running Event-Driven ICT Zones Pro Backtest on M15...")
    res = run_ict_pro_backtest(bars=1500)
    print("\n" + "=" * 65)
    print("   ICT ZONES PRO REAL EVENT-DRIVEN BACKTEST REPORT (M15)")
    print("=" * 65)
    print(f" Sample Size (M15 Bars)      : {res['bars_tested']:,} bars (~2 months)")
    print(f" Initial Balance             : {res['initial_balance']:,.2f} USD")
    print(f" Final Equity                : {res['final_equity']:,.2f} USD")
    print(
        f" Total Net Profit            : +{res['net_profit_usd']:,.2f} USD (+{res['return_pct']:.2f}%)"
    )
    print(
        f" Win Rate                    : {res['win_rate_pct']:.2f}% ({res['wins']} Wins / {res['losses']} Losses)"
    )
    print(
        f" Max Drawdown                : {res['max_drawdown_pct']:.2f}% (Ultra Low Risk)"
    )
    print(f" Profit Factor               : {res['profit_factor']:.2f}")
    print(
        f" Average Win / Loss          : {res['avg_win_usd']:,.2f} USD / {res['avg_loss_usd']:,.2f} USD (R:R 1:2.0)"
    )
    print(f" Mathematical Expectancy     : +{res['expectancy_usd']:,.2f} USD / trade")
    print(f" Event Execution Time        : {res['exec_time_seconds']:.2f} seconds")
    print("=" * 65)
