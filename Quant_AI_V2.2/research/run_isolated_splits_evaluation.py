# -*- coding: utf-8 -*-
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import lightgbm as lgb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
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

# Vectorized features
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
        adx14[idx] = (adx14[idx - 1] * 13 + dx[idx]) / 14.0

log_hl = np.log(np.maximum(highs, 1e-9) / np.maximum(lows, 1e-9))
log_co = np.log(np.maximum(closes, 1e-9) / np.maximum(opens, 1e-9))
gk_vol = 0.5 * (log_hl ** 2) - (2.0 * np.log(2.0) - 1.0) * (log_co ** 2)

body = closes - opens
candle_range = highs - lows
safe_range = np.where(candle_range > 1e-9, candle_range, 1e-9)
cvd_proxy_ratio = (body / safe_range) * volumes

typical_price = (highs + lows + closes) / 3.0
pv = typical_price * volumes
cum_pv = np.cumsum(pv)
cum_vol = np.cumsum(volumes)
safe_cum_vol = np.where(cum_vol > 1e-9, cum_vol, 1e-9)
vwap = cum_pv / safe_cum_vol
roll_std_vwap = pd.Series(closes - vwap).rolling(50, min_periods=1).std().fillna(1.0).to_numpy()
safe_std = np.where(roll_std_vwap > 1e-9, roll_std_vwap, 1e-9)
vwap_zscore = (closes - vwap) / safe_std

roll_high_30 = pd.Series(highs).rolling(30, min_periods=1).max().to_numpy()
roll_low_30 = pd.Series(lows).rolling(30, min_periods=1).min().to_numpy()
safe_atr = np.where(atr14 > 1e-9, atr14, 1e-9)
upper_wick_ratio = np.maximum(0.0, highs - np.maximum(opens, closes)) / safe_range
lower_wick_ratio = np.maximum(0.0, np.minimum(opens, closes) - lows) / safe_range
hours = df["time"].dt.hour.to_numpy()
days_of_week = df["time"].dt.dayofweek.to_numpy()

# Run dynamic strategy backtest
strat_cfg = {"vol_mult": 1.10, "adx_threshold": 16.0, "min_headroom_atr": 0.4, "session_filter": False}

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

strat = VersionedWyckoff(6, 21)
tester = EventDrivenBacktester(strategy=strat, initial_balance=100000.0, risk_per_trade_pct=1.0, commission_per_lot=7.0, slippage_pts=20.0, max_lot_cap=10.0)
report = tester.run(df, symbol=symbol)
raw_trades = report.trade_records

time_str_to_idx = {t.strftime("%Y-%m-%d %H:%M"): i for i, t in enumerate(df["time"])}
samples = []
for tr in raw_trades:
    entry_str = str(tr.get("signal_time",tr["entry_time"]))
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
    samples.append({
        "trade_id": tr["trade_id"],
        "entry_time": tr["entry_time"],
        "exit_time": tr["exit_time"],
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
        "hour": hours[idx],
        "dow": days_of_week[idx],
        "year": str(tr["entry_time"])[:4],
    })

from backend.core.meta_features import build_meta_features
trades_by_time={str(t["entry_time"]):t for t in raw_trades}
for sample in samples:
    trade=trades_by_time[str(sample["entry_time"])]
    feature_time=str(trade.get('signal_time',trade['entry_time']))
    feature_idx=time_str_to_idx.get(feature_time)
    if feature_idx is None:
        raise ValueError('Missing signal timestamp for feature extraction')
    sample.update(build_meta_features(df.iloc[max(0,feature_idx-299):feature_idx+1],trade['side']))

dataset_df = pd.DataFrame(samples)
feature_cols = ["is_buy", "vol_ratio", "adx", "gk_vol", "cvd_proxy", "vwap_zscore", "ema_spread", "headroom", "wick_ratio", "hour", "dow"]

# Walk forward
years_list = ["2022", "2023", "2024", "2025", "2026"]
oos_predictions = []

for step_idx in range(1, len(years_list)):
    train_years = years_list[:step_idx]
    test_year = years_list[step_idx]
    train_df = dataset_df[dataset_df["year"].isin(train_years)]
    train_df = train_df[pd.to_datetime(train_df["exit_time"]) < pd.Timestamp(f"{test_year}-01-01")]
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
            "entry_time": row["entry_time"],
            "outcome": row["outcome"],
            "pnl": row["pnl"],
            "pred_prob": float(preds[i]),
        })

oos_df = pd.DataFrame(oos_predictions)

def calc_stats(sub_df, name):
    print(f"\n=======================================================")
    print(f"   STATS FOR: {name} ({len(sub_df)} trades)")
    print(f"=======================================================")
    print(f"{'Thresh':<7} | {'Trades':<6} | {'Wins':<4} | {'Losses':<6} | {'Winrate':<7} | {'Net Profit':<12} | {'MaxDD':<7} | {'PF':<5} | {'J (Return/DD)':<12}")
    print("-" * 80)
    for thresh in [0.0, 0.32, 0.34, 0.36, 0.38, 0.40, 0.42]:
        f = sub_df[sub_df["pred_prob"] >= thresh] if thresh > 0.0 else sub_df
        tot = len(f)
        if tot == 0:
            continue
        wins = int((f["outcome"] == 1).sum())
        losses = tot - wins
        wr = (wins / tot) * 100.0
        bal = 100000.0
        curv = [bal]
        for p in f["pnl"]:
            bal += p
            curv.append(bal)
        c_arr = np.array(curv)
        pk = np.maximum.accumulate(c_arr)
        dd = np.where(pk > 0, (pk - c_arr) / pk, 0.0)
        mdd = np.max(dd) * 100.0
        net = bal - 100000.0
        ret_pct = (net / 100000.0) * 100.0
        gp = f[f["pnl"] > 0]["pnl"].sum()
        gl = abs(f[f["pnl"] < 0]["pnl"].sum())
        pf = (gp / gl) if gl > 0 else (99.0 if gp > 0 else 0.0)
        j_val = (ret_pct / mdd) if mdd > 0 else 0.0
        print(f"{thresh:<7} | {tot:<6} | {wins:<4} | {losses:<6} | {wr:6.2f}% | ${net:10,.2f} | {mdd:6.2f}% | {pf:4.2f} | {j_val:6.2f}")

# 1. Validation Set (2023 - 2024)
val_df = oos_df[oos_df["year"].isin(["2023", "2024"])]
calc_stats(val_df, "TAP XAC THUC (VALIDATION SET 2023-2024)")

# 2. Test Set (2025 - 2026)
test_df = oos_df[oos_df["year"].isin(["2025", "2026"])]
calc_stats(test_df, "TAP KIEM THU DOC LAP (PURE HOLDOUT TEST SET 2025-2026)")

# Date ranges
print("\n--- EXACT DATE RANGES ---")
print("Dataset min date:", df["time"].min(), "max date:", df["time"].max())
t22 = dataset_df[dataset_df["year"] == "2022"]["entry_time"]
t23_24 = dataset_df[dataset_df["year"].isin(["2023", "2024"])]["entry_time"]
t25_26 = dataset_df[dataset_df["year"].isin(["2025", "2026"])]["entry_time"]
print(f"2022 Train Trades: {len(t22)} trades | from {t22.min()} to {t22.max()}")
print(f"2023-2024 Validation Trades: {len(t23_24)} trades | from {t23_24.min()} to {t23_24.max()}")
print(f"2025-2026 Holdout Trades: {len(t25_26)} trades | from {t25_26.min()} to {t25_26.max()}")
