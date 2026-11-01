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

# Filter df to 2023-2024 plus 250 bars warmup before 2023
idx_2023 = df[df["time"] >= "2023-01-01"].index[0]
warmup_start = max(0, idx_2023 - 250)
df_val = df.iloc[warmup_start:].copy()
df_val_23_24 = df_val[df_val["time"] <= "2024-12-31 23:59:59"].copy()

print(f"Running ISOLATED 2023-2024 backtest from $100,000...")
strat = VersionedWyckoff(6, 21)
tester = EventDrivenBacktester(
    strategy=strat,
    initial_balance=100000.0,
    risk_per_trade_pct=1.0,
    commission_per_lot=7.0,
    slippage_pts=20.0,
    max_lot_cap=10.0,
)
report = tester.run(df_val_23_24, symbol=symbol)
trades = pd.DataFrame(report.trade_records)
trades["year"] = trades["entry_time"].str[:4]
trades_23_24 = trades[trades["year"].isin(["2023", "2024"])]

print("=== Isolated 2023-2024 Backtest Result ===")
print("Total trades:", len(trades_23_24))
print("Wins:", (trades_23_24["outcome"] == "TP").sum())
print("Total PnL:", trades_23_24["pnl"].sum())
for y, g in trades_23_24.groupby("year"):
    print(f"Year {y}: trades={len(g)}, wins={(g['outcome']=='TP').sum()}, pnl={g['pnl'].sum():.2f}")
