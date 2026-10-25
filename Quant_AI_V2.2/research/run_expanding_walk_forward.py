# -*- coding: utf-8 -*-
"""
STRICT EXPANDING-WINDOW OUT-OF-SAMPLE WALK-FORWARD VALIDATION
============================================================
Every single test prediction is 100% OUT-OF-SAMPLE:
- Train 2022 -> Predict 2023 strictly OOS
- Train 2022..2023 -> Predict 2024 strictly OOS
- Train 2022..2024 -> Predict 2025 strictly OOS
- Train 2022..2025 -> Predict 2026 strictly OOS
ZERO in-sample evaluation. Pure Institutional Proof per Marcos López de Prado.
"""

import sys
import json
from pathlib import Path
import numpy as np
import pandas as pd
import lightgbm as lgb

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

print("=" * 80)
print("   STRICT OUT-OF-SAMPLE EXPANDING WALK-FORWARD VALIDATION")
print("   Marcos López de Prado: Zero In-Sample Leakage")
print("=" * 80)

if not mt5.initialize():
    print("MT5 Init Failed")
    sys.exit(1)

symbol = "XAUUSD"
bars_count = 99999
rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, bars_count)
df = pd.DataFrame(rates)
df["time"] = pd.to_datetime(df["time"], unit="s")

# Compute vectorized features
closes = df["close"].to_numpy(dtype=np.float64)
highs = df["high"].to_numpy(dtype=np.float64)
lows = df["low"].to_numpy(dtype=np.float64)
opens = df["open"].to_numpy(dtype=np.float64)
volumes = df["tick_volume"].to_numpy(dtype=np.float64)
n = len(df)

tr1 = highs[1:] - lows[1:]
tr2 = np.abs(highs[1:] - closes[:-1])
tr3 = np.abs(lows[1:] - closes[:-1])
tr = np.maximum(tr1, np.maximum(tr2, tr3))
atr14 = np.zeros(n)
atr14[14] = np.mean(tr[:14])
for idx in range(15, n):
    atr14[idx] = (atr14[idx - 1] * 13 + tr[idx - 1]) / 14.0

def calc_ema(arr, period):
    res = np.zeros(len(arr))
    alpha = 2.0 / (period + 1.0)
    res[period - 1] = np.mean(arr[:period])
    for i in range(period, len(arr)):
        res[i] = (arr[i] - res[i - 1]) * alpha + res[i - 1]
    return res

ema20 = calc_ema(closes, 20)
ema50 = calc_ema(closes, 50)
vol_ma20 = calc_ema(volumes, 20)

# Wilder ADX
up_move = highs[1:] - highs[:-1]
down_move = lows[:-1] - lows[1:]
plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
tr_smooth = np.zeros(n)
p_dm_smooth = np.zeros(n)
m_dm_smooth = np.zeros(n)
tr_smooth[14] = np.sum(tr[:14])
p_dm_smooth[14] = np.sum(plus_dm[:14])
m_dm_smooth[14] = np.sum(minus_dm[:14])
for idx in range(15, n):
    tr_smooth[idx] = tr_smooth[idx - 1] - (tr_smooth[idx - 1] / 14.0) + tr[idx - 1]
    p_dm_smooth[idx] = p_dm_smooth[idx - 1] - (p_dm_smooth[idx - 1] / 14.0) + plus_dm[idx - 1]
    m_dm_smooth[idx] = m_dm_smooth[idx - 1] - (m_dm_smooth[idx - 1] / 14.0) + minus_dm[idx - 1]

safe_tr = np.where(tr_smooth > 1e-9, tr_smooth, 1e-9)
plus_di = 100.0 * (p_dm_smooth / safe_tr)
minus_di = 100.0 * (m_dm_smooth / safe_tr)
di_sum = plus_di + minus_di
safe_di_sum = np.where(di_sum > 1e-9, di_sum, 1e-9)
dx = 100.0 * np.abs(plus_di - minus_di) / safe_di_sum
adx14 = np.zeros(n)
if n >= 28:
    adx14[27] = np.mean(dx[14:28])
    for idx in range(28, n):
        adx14[idx] = (adx14[idx - 1] * 13.0 + dx[idx]) / 14.0

# Microstructure features
log_hl = np.log(highs / np.maximum(lows, 1e-9))
log_co = np.log(closes / np.maximum(opens, 1e-9))
gk_bar = 0.5 * (log_hl ** 2) - (2.0 * np.log(2.0) - 1.0) * (log_co ** 2)
gk_series = pd.Series(gk_bar).rolling(14).mean().fillna(0.0).to_numpy()
gk_vol = np.sqrt(np.maximum(0.0, gk_series)) * 1000.0

price_diff = np.diff(closes, prepend=closes[0])
signed_vol = np.where(price_diff > 0, volumes, np.where(price_diff < 0, -volumes, 0.0))
cvd_10 = pd.Series(signed_vol).rolling(10).sum().fillna(0.0).to_numpy()
vol_sum_10 = pd.Series(volumes).rolling(10).sum().replace(0, 1.0).fillna(1.0).to_numpy()
cvd_proxy_ratio = cvd_10 / vol_sum_10

pv = closes * volumes
rolling_pv = pd.Series(pv).rolling(96).sum().bfill()
rolling_v = pd.Series(volumes).rolling(96).sum().replace(0, 1.0).fillna(1.0)
vwap_24h = (rolling_pv / rolling_v).to_numpy()
safe_atr = np.where(atr14 > 1e-4, atr14, 1.0)
vwap_zscore = (closes - vwap_24h) / safe_atr

candle_range = highs - lows
candle_range_safe = np.where(candle_range > 1e-4, candle_range, 1.0)
upper_wick = highs - np.maximum(closes, opens)
lower_wick = np.minimum(closes, opens) - lows
upper_wick_ratio = upper_wick / candle_range_safe
lower_wick_ratio = lower_wick / candle_range_safe

roll_high_30 = pd.Series(highs).rolling(30).max().shift(1).bfill().to_numpy()
roll_low_30 = pd.Series(lows).rolling(30).min().shift(1).bfill().to_numpy()
hours = df["time"].dt.hour.to_numpy()
days_of_week = df["time"].dt.dayofweek.to_numpy()

# Harvest trades from Dynamic
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

strat = VersionedWyckoff(6, 21)
tester = EventDrivenBacktester(
    strategy=strat,
    initial_balance=100000.0,
    risk_per_trade_pct=1.0,
    commission_per_lot=7.0,
    slippage_pts=20.0,
    max_lot_cap=10.0,
)

report = tester.run(df, symbol=symbol)
raw_trades = report.trade_records

time_str_to_idx = {t.strftime("%Y-%m-%d %H:%M"): i for i, t in enumerate(df["time"])}
samples = []
for tr in raw_trades:
    entry_str = str(tr["entry_time"])
    idx = time_str_to_idx.get(entry_str)
    if idx is None:
        continue
    side = tr["side"]
    is_buy = 1 if side == "BUY" else 0
    outcome = 1 if tr["outcome"] == "TP" else 0
    v_ratio = volumes[idx] / max(1.0, vol_ma20[idx])
    adx_val = adx14[idx]
    gk_val = gk_vol[idx]
    cvd_val = cvd_proxy_ratio[idx]
    vwap_z = vwap_zscore[idx]
    ema_spread = abs(ema20[idx] - ema50[idx]) / safe_atr[idx]
    if is_buy:
        headroom = (roll_high_30[idx] - closes[idx]) / safe_atr[idx]
        wick = upper_wick_ratio[idx]
    else:
        headroom = (closes[idx] - roll_low_30[idx]) / safe_atr[idx]
        wick = lower_wick_ratio[idx]
    hr = hours[idx]
    dow = days_of_week[idx]
    samples.append({
        "trade_id": tr["trade_id"],
        "entry_time": tr["entry_time"],
        "pnl": tr["pnl"],
        "outcome": outcome,
        "is_buy": is_buy,
        "vol_ratio": round(v_ratio, 3),
        "adx": round(adx_val, 2),
        "gk_vol": round(gk_val, 4),
        "cvd_proxy": round(cvd_val, 3),
        "vwap_zscore": round(vwap_z, 3),
        "ema_spread": round(ema_spread, 3),
        "headroom": round(headroom, 3),
        "wick_ratio": round(wick, 3),
        "hour": hr,
        "dow": dow,
        "year": str(tr["entry_time"])[:4],
    })

dataset_df = pd.DataFrame(samples)
feature_cols = [
    "is_buy", "vol_ratio", "adx", "gk_vol", "cvd_proxy",
    "vwap_zscore", "ema_spread", "headroom", "wick_ratio", "hour", "dow"
]

# STRICT EXPANDING WALK-FORWARD
years_list = ["2022", "2023", "2024", "2025", "2026"]
oos_predictions = []

for step_idx in range(1, len(years_list)):
    train_years = years_list[:step_idx]
    test_year = years_list[step_idx]
    
    train_df = dataset_df[dataset_df["year"].isin(train_years)]
    test_df = dataset_df[dataset_df["year"] == test_year]
    
    X_tr = train_df[feature_cols]
    y_tr = train_df["outcome"]
    X_te = test_df[feature_cols]
    
    train_data = lgb.Dataset(X_tr, label=y_tr)
    params = {
        "objective": "binary",
        "metric": "binary_logloss",
        "boosting_type": "gbdt",
        "learning_rate": 0.03,
        "num_leaves": 12,
        "max_depth": 3,
        "min_child_samples": 15,
        "feature_fraction": 0.8,
        "verbose": -1,
        "random_state": 42,
    }
    m = lgb.train(params, train_data, num_boost_round=80)
    preds = m.predict(X_te)
    
    for i, (_, row) in enumerate(test_df.iterrows()):
        oos_predictions.append({
            "trade_id": row["trade_id"],
            "year": test_year,
            "outcome": row["outcome"],
            "pnl": row["pnl"],
            "pred_prob": float(preds[i]),
        })

oos_df = pd.DataFrame(oos_predictions)
print(f"Generated {len(oos_df)} PURE OUT-OF-SAMPLE walk-forward trade predictions (2023-2026).")

# Compare Unfiltered vs Filtered OOS
for thresh in [0.0, 0.32, 0.34, 0.36]:
    filtered = oos_df[oos_df["pred_prob"] >= thresh] if thresh > 0.0 else oos_df
    balance = 100000.0
    curve = [balance]
    for _, r in filtered.iterrows():
        balance += r["pnl"]
        curve.append(balance)
    c_arr = np.array(curve)
    peak = np.maximum.accumulate(c_arr)
    dd_arr = np.where(peak > 0, (peak - c_arr) / peak, 0.0)
    max_dd = np.max(dd_arr) * 100.0
    
    wins = (filtered["outcome"] == 1).sum()
    total = len(filtered)
    wr = (wins / total * 100.0) if total > 0 else 0.0
    net = balance - 100000.0
    gp = filtered[filtered["pnl"] > 0]["pnl"].sum()
    gl = abs(filtered[filtered["pnl"] < 0]["pnl"].sum())
    pf = (gp / gl) if gl > 0 else 99.0
    
    lbl = "Dynamic Goc (Khong ML)" if thresh == 0.0 else f"Dynamic + ML OOS (Thresh {thresh})"
    print(f"\n[{lbl}]")
    print(f"   Trades: {total:3d} | Winrate: {wr:4.1f}% | Net Profit: +${net:10,.2f} USD (+{net/1000.0:.1f}%) | Max DD: {max_dd:5.2f}% | PF: {pf:4.2f}")
    
    # Yearly
    for yr in ["2023", "2024", "2025", "2026"]:
        yr_f = filtered[filtered["year"] == yr]
        yr_w = (yr_f["outcome"] == 1).sum()
        yr_t = len(yr_f)
        yr_pnl = yr_f["pnl"].sum()
        sign = "+" if yr_pnl >= 0 else "-"
        yr_wr = (yr_w / yr_t * 100.0) if yr_t > 0 else 0.0
        print(f"      Year {yr}: {yr_t:3d} trades ({yr_w:2d}W/{yr_t-yr_w:2d}L - {yr_wr:4.1f}% WR) -> PnL: {sign}${abs(yr_pnl):9,.2f} USD")
