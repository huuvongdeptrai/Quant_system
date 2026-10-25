# -*- coding: utf-8 -*-
import sys
from pathlib import Path
import pandas as pd
import json

PROJECT_ROOT = Path(r"Kho_Do_An\Quant_AI_V2.2")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.infrastructure.brokers.mt5_safe import mt5
from backend.backtest.backtest_ict_pro import EventDrivenBacktester

if not mt5.initialize():
    print("MT5 Initialization failed")
    sys.exit(1)

symbol = "XAUUSD"
bars_to_fetch = 3000
rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, bars_to_fetch)
df = pd.DataFrame(rates)
df["time"] = pd.to_datetime(df["time"], unit="s")

print(f"=== HEAD-TO-HEAD EVENT-DRIVEN BENCHMARK: {symbol} M15 ===")
print(f"Sample Period: {df['time'].iloc[0]} to {df['time'].iloc[-1]} ({len(df)} bars)")

# 1. Run Wyckoff Momentum Pro
bt_wyckoff = EventDrivenBacktester(strategy="wyckoff", initial_balance=100000.0, risk_per_trade_pct=1.0)
rep_w = bt_wyckoff.run(df, symbol=symbol)

# 2. Run ICT Zones Pro
bt_ict = EventDrivenBacktester(strategy="ict", initial_balance=100000.0, risk_per_trade_pct=1.0)
rep_i = bt_ict.run(df, symbol=symbol)

summary = {
    "symbol": symbol,
    "bars": len(df),
    "from_date": str(df['time'].iloc[0]),
    "to_date": str(df['time'].iloc[-1]),
    "wyckoff": {
        "trades": rep_w.total_trades,
        "wins": rep_w.win_trades,
        "losses": rep_w.loss_trades,
        "winrate": round(rep_w.win_rate_pct, 2),
        "net_profit": round(rep_w.total_net_profit, 2),
        "return_pct": round(rep_w.total_return_pct, 2),
        "profit_factor": round(rep_w.profit_factor, 2),
        "max_dd_pct": round(rep_w.max_drawdown_pct, 2),
        "sharpe": round(rep_w.sharpe_ratio, 2),
        "expectancy": round(rep_w.mathematical_expectancy, 2),
    },
    "ict": {
        "trades": rep_i.total_trades,
        "wins": rep_i.win_trades,
        "losses": rep_i.loss_trades,
        "winrate": round(rep_i.win_rate_pct, 2),
        "net_profit": round(rep_i.total_net_profit, 2),
        "return_pct": round(rep_i.total_return_pct, 2),
        "profit_factor": round(rep_i.profit_factor, 2),
        "max_dd_pct": round(rep_i.max_drawdown_pct, 2),
        "sharpe": round(rep_i.sharpe_ratio, 2),
        "expectancy": round(rep_i.mathematical_expectancy, 2),
    }
}

print(json.dumps(summary, indent=2))
