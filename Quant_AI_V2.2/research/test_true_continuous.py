import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = Path("Kho_Do_An/Quant_AI_V2.2").resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.infrastructure.brokers.mt5_safe import mt5
from backend.backtest.backtest_ict_pro import EventDrivenBacktester
from backend.core.strategies.wyckoff_vectorized import WyckoffMomentumStrategy

if not mt5.initialize():
    print("MT5 Failed")
    sys.exit(1)

symbol = "XAUUSD"
bars_count = 99999
rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, bars_count)
mt5.shutdown()

df = pd.DataFrame(rates)
df["time"] = pd.to_datetime(df["time"], unit="s")

dynamic_cfg = {
    "vol_mult": 1.10,
    "adx_threshold": 16.0,
    "min_headroom_atr": 0.4,
    "session_filter": False,
}

class VersionedWyckoff(WyckoffMomentumStrategy):
    def __init__(self, s_hr=6, e_hr=21):
        super().__init__(dynamic_cfg)
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

# 1. Full 4-year continuous backtest starting 2022
strat1 = VersionedWyckoff(6, 21)
tester1 = EventDrivenBacktester(
    strategy=strat1,
    initial_balance=100000.0,
    risk_per_trade_pct=1.0,
    commission_per_lot=7.0,
    slippage_pts=20.0,
    max_lot_cap=10.0,
)
report1 = tester1.run(df, symbol=symbol)
trades1 = pd.DataFrame(report1.trade_records)
trades1["year"] = trades1["entry_time"].str[:4]

print("=== Run 1: Continuous 2022-2026 (Initial $100,000 on 2022) ===")
for y, g in trades1.groupby("year"):
    print(f"Year {y}: trades={len(g)}, wins={(g['outcome']=='TP').sum()}, pnl={g['pnl'].sum():.2f}")

val_trades_1 = trades1[trades1["year"].isin(["2023", "2024"])]
print(f"2023-2024 PnL in Continuous Run: {val_trades_1['pnl'].sum():.2f}")
test_trades_1 = trades1[trades1["year"].isin(["2025", "2026"])]
print(f"2025-2026 PnL in Continuous Run: {test_trades_1['pnl'].sum():.2f}")
