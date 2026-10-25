# -*- coding: utf-8 -*-
"""
2-YEAR COMPREHENSIVE STATISTICAL BACKTEST (50,000 M15 BARS OF XAUUSD)
Compares:
1. Ban Hien Tai (Strict / Sieu khat khe)
2. Ban Can Bang (Balanced Day-Trader)
3. Ban Nang Dong (Dynamic / Toi uu Dong tien)
"""

import sys
import time
from pathlib import Path
import pandas as pd
import json

# Fix windows console unicode printing
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(r"Kho_Do_An\Quant_AI_V2.2")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.infrastructure.brokers.mt5_safe import mt5
from backend.backtest.backtest_ict_pro import EventDrivenBacktester
from backend.core.strategies.wyckoff_vectorized import WyckoffMomentumStrategy

if not mt5.initialize():
    print("MT5 Init Failed")
    sys.exit(1)

symbol = "XAUUSD"
bars_count = 50000

print(f"Fetching {bars_count:,} M15 bars for {symbol} from MT5...")
rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, bars_count)
df = pd.DataFrame(rates)
df["time"] = pd.to_datetime(df["time"], unit="s")

from_dt = df["time"].iloc[0]
to_dt = df["time"].iloc[-1]
years = (to_dt - from_dt).days / 365.25

print(f"Data Loaded: {len(df):,} bars")
print(f"Time Range: {from_dt} -> {to_dt} ({years:.2f} years)")
print("=" * 70)

configs = [
    {
        "id": "STRICT",
        "name": "1. Ban Hien Tai (Strict - Sieu khat khe)",
        "vol_mult": 1.25,
        "adx_threshold": 20.0,
        "min_headroom_atr": 1.0,
        "start_hr": 7,
        "end_hr": 17,
    },
    {
        "id": "BALANCED",
        "name": "2. Ban Can Bang (Balanced - Chuan Quy)",
        "vol_mult": 1.15,
        "adx_threshold": 18.0,
        "min_headroom_atr": 0.6,
        "start_hr": 6,
        "end_hr": 20,
    },
    {
        "id": "DYNAMIC",
        "name": "3. Ban Nang Dong (Dynamic - Toi uu Von)",
        "vol_mult": 1.10,
        "adx_threshold": 16.0,
        "min_headroom_atr": 0.4,
        "start_hr": 6,
        "end_hr": 21,
    },
]

results = []

for cfg in configs:
    t_start = time.perf_counter()
    strat_cfg = {
        "vol_mult": cfg["vol_mult"],
        "adx_threshold": cfg["adx_threshold"],
        "min_headroom_atr": cfg["min_headroom_atr"],
        "session_filter": False,
    }

    class VersionedWyckoff(WyckoffMomentumStrategy):
        def __init__(self, s_hr, e_hr):
            super().__init__(strat_cfg)
            self.s_hr = s_hr
            self.e_hr = e_hr

        def analyze(self, window_df, macro_context=None):
            if "time" in window_df.columns:
                t = pd.to_datetime(window_df["time"].iloc[-1])
                if not (self.s_hr <= t.hour <= self.e_hr):
                    res = super().analyze(window_df, macro_context)
                    res.action = "HOLD"
                    res.signal = "HOLD"
                    return res
            return super().analyze(window_df, macro_context)

    strat_inst = VersionedWyckoff(cfg["start_hr"], cfg["end_hr"])
    tester = EventDrivenBacktester(
        strategy=strat_inst,
        initial_balance=100000.0,
        risk_per_trade_pct=1.0,
        commission_per_lot=7.0,
        slippage_pts=20.0,
        max_lot_cap=10.0,
    )

    report = tester.run(df, symbol=symbol)
    elapsed = time.perf_counter() - t_start

    total_months = max(1.0, years * 12.0)
    trades_per_month = report.total_trades / total_months
    trades_per_week = trades_per_month / 4.33

    stat = {
        "config_name": cfg["name"],
        "total_trades": report.total_trades,
        "trades_per_month": round(trades_per_month, 1),
        "trades_per_week": round(trades_per_week, 1),
        "wins": report.win_trades,
        "losses": report.loss_trades,
        "winrate_pct": round(report.win_rate_pct, 2),
        "initial_balance": report.initial_balance,
        "final_equity": round(report.final_equity, 2),
        "net_profit_usd": round(report.total_net_profit, 2),
        "total_return_pct": round(report.total_return_pct, 2),
        "cagr_pct": round(((report.final_equity / report.initial_balance) ** (1.0 / years) - 1.0) * 100.0, 2),
        "profit_factor": round(report.profit_factor, 2),
        "max_drawdown_pct": round(report.max_drawdown_pct, 2),
        "sharpe_ratio": round(report.sharpe_ratio, 2),
        "sortino_ratio": round(report.sortino_ratio, 2),
        "expectancy_usd": round(report.mathematical_expectancy, 2),
        "exec_time_sec": round(elapsed, 1),
    }
    results.append(stat)

    print(f"\n>>> {cfg['name']}")
    print(f"  Execution Time        : {stat['exec_time_sec']}s")
    print(f"  Total Trades          : {stat['total_trades']} ({stat['trades_per_month']} trades/month, ~{stat['trades_per_week']} trades/week)")
    print(f"  Win / Loss            : {stat['wins']} Wins / {stat['losses']} Losses")
    print(f"  Win Rate              : {stat['winrate_pct']}%")
    print(f"  Final Equity          : ${stat['final_equity']:,.2f} USD")
    print(f"  Total Net Profit      : ${stat['net_profit_usd']:,.2f} USD ({stat['total_return_pct']}%)")
    print(f"  Annual Return (CAGR)  : {stat['cagr_pct']}% / year")
    print(f"  Profit Factor         : {stat['profit_factor']}")
    print(f"  Max Drawdown          : {stat['max_drawdown_pct']}%")
    print(f"  Sharpe Ratio          : {stat['sharpe_ratio']}")
    print(f"  Expectancy            : ${stat['expectancy_usd']} / trade")

with open(r"Kho_Do_An\Quant_AI_V2.2\research\benchmark_2year_results.json", "w", encoding="utf-8") as f_out:
    json.dump({"period_years": years, "bars": len(df), "from": str(from_dt), "to": str(to_dt), "results": results}, f_out, indent=2)

print("\nSaved benchmark results to research/benchmark_2year_results.json")
