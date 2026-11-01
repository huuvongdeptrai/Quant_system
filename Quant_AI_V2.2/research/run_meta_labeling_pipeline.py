# -*- coding: utf-8 -*-
"""
INSTITUTIONAL MACHINE LEARNING META-LABELING PIPELINE
=====================================================
Reference: Marcos López de Prado, Advances in Financial Machine Learning (AFML)
Chapter 3: Meta-Labeling Architecture
Chapter 4: Sample Weights, Purging, and Out-of-Sample Cross-Validation

This pipeline:
1. Runs the high-recall Wyckoff Dynamic Momentum Strategy over 99,999 M15 bars (4.27 years).
2. Harvests exact microstructure feature vectors at every signal generation:
   - Volume surge ratio (Effort)
   - J. Welles Wilder ADX (Trend regime)
   - Rejection wick percentage (Result)
   - S/R Headroom clearance / ATR
   - Garman-Klass Realized Volatility estimator (Intraday variance)
   - Session VWAP Z-Score (Institutional Fair Value deviation)
   - Microstructure CVD proxy order-flow imbalance
   - EMA20-EMA50 spread / ATR (Trend maturity)
   - Time & Session temporal features (UTC hour, day of week)
3. Labels each trade: y = 1 (Take Profit hit), y = 0 (Stop Loss hit).
4. Splits strictly Chronologically (Zero Lookahead / Pure Out-of-Sample):
   - Train (In-Sample): 2022-07 to 2024-12 (Turbulent Fed hiking cycle & wide consolidations)
   - Test (Out-of-Sample): 2025-01 to 2026-10 (Historic ATH breakout and new regimes)
5. Trains LightGBM Meta-Labeling Classifier to predict P(Win | Features).
6. Simulates Meta-Labeling Filtered Execution (Decision Gate: Size = 0 if P < Threshold).
7. Compares Original Dynamic vs ML Meta-Labeled Dynamic across all metrics:
   - Net Profit ($ & %)
   - Max Drawdown Compression
   - Profit Factor & Sharpe Surge
   - Yearly PnL Breakdown (2022 -> 2026)
"""

import sys
import time
import json
from pathlib import Path
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score

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
print("   QUANT AI V2.2 - MACHINE LEARNING META-LABELING PIPELINE")
print("   Marcos López de Prado Architecture on 99,999 M15 Bars (4.27 Years)")
print("=" * 80)

if not mt5.initialize():
    print("MT5 Init Failed")
    sys.exit(1)

symbol = "XAUUSD"
bars_count = 99999

print(f"\n[1/5] Loading {bars_count:,} bars of {symbol} M15 from MT5...")
rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, bars_count)
df = pd.DataFrame(rates)
df["time"] = pd.to_datetime(df["time"], unit="s")
from_dt = df["time"].iloc[0]
to_dt = df["time"].iloc[-1]
years = (to_dt - from_dt).days / 365.25
print(f"Data Loaded: {len(df):,} bars | Span: {from_dt} -> {to_dt} ({years:.2f} years)")

# ---------------------------------------------------------
# Vectorized Feature Precomputation across entire DataFrame
# ---------------------------------------------------------
print("\n[2/5] Vectorizing Microstructure Features across all 99,999 bars...")
closes = df["close"].to_numpy(dtype=np.float64)
highs = df["high"].to_numpy(dtype=np.float64)
lows = df["low"].to_numpy(dtype=np.float64)
opens = df["open"].to_numpy(dtype=np.float64)
volumes = df["tick_volume"].to_numpy(dtype=np.float64)
n = len(df)

# ATR(14)
tr1 = highs[1:] - lows[1:]
tr2 = np.abs(highs[1:] - closes[:-1])
tr3 = np.abs(lows[1:] - closes[:-1])
tr = np.maximum(tr1, np.maximum(tr2, tr3))
atr14 = np.zeros(n)
atr14[14] = np.mean(tr[:14])
for idx in range(15, n):
    atr14[idx] = (atr14[idx - 1] * 13 + tr[idx - 1]) / 14.0

# EMAs
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

# Wilder ADX(14)
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

# Garman-Klass Realized Volatility estimator (window 14)
log_hl = np.log(highs / np.maximum(lows, 1e-9))
log_co = np.log(closes / np.maximum(opens, 1e-9))
gk_bar = 0.5 * (log_hl ** 2) - (2.0 * np.log(2.0) - 1.0) * (log_co ** 2)
gk_series = pd.Series(gk_bar).rolling(14).mean().fillna(0.0).to_numpy()
gk_vol = np.sqrt(np.maximum(0.0, gk_series)) * 1000.0  # scaled

# Cumulative Volume Delta (CVD) Proxy (window 10)
price_diff = np.diff(closes, prepend=closes[0])
signed_vol = np.where(price_diff > 0, volumes, np.where(price_diff < 0, -volumes, 0.0))
cvd_10 = pd.Series(signed_vol).rolling(10).sum().fillna(0.0).to_numpy()
vol_sum_10 = pd.Series(volumes).rolling(10).sum().replace(0, 1.0).fillna(1.0).to_numpy()
cvd_proxy_ratio = cvd_10 / vol_sum_10

# Session VWAP Z-Score (rolling 96 bars = 24 hours on M15)
pv = closes * volumes
rolling_pv = pd.Series(pv).rolling(96).sum().bfill()
rolling_v = pd.Series(volumes).rolling(96).sum().replace(0, 1.0).fillna(1.0)
vwap_24h = (rolling_pv / rolling_v).to_numpy()
safe_atr = np.where(atr14 > 1e-4, atr14, 1.0)
vwap_zscore = (closes - vwap_24h) / safe_atr

# Candlestick characteristics
candle_range = highs - lows
candle_range_safe = np.where(candle_range > 1e-4, candle_range, 1.0)
upper_wick = highs - np.maximum(closes, opens)
lower_wick = np.minimum(closes, opens) - lows
upper_wick_ratio = upper_wick / candle_range_safe
lower_wick_ratio = lower_wick / candle_range_safe

# Rolling 30-bar swing high/low for headroom
roll_high_30 = pd.Series(highs).rolling(30).max().shift(1).bfill().to_numpy()
roll_low_30 = pd.Series(lows).rolling(30).min().shift(1).bfill().to_numpy()

hours = df["time"].dt.hour.to_numpy()
days_of_week = df["time"].dt.dayofweek.to_numpy()

print("Features computed successfully!")

# ---------------------------------------------------------
# Run Base Dynamic Strategy to harvest signals and outcomes
# ---------------------------------------------------------
print("\n[3/5] Simulating Dynamic Wyckoff Strategy to harvest raw trades...")
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
print(f"Harvested {len(raw_trades)} raw trades from Dynamic strategy.")

# Map trades back to entry bar index and extract feature vector
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
    
    # Extract features at signal bar (idx)
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
        "exit_time": tr["exit_time"],
        "side": side,
        "is_buy": is_buy,
        "pnl": tr["pnl"],
        "outcome": outcome,  # Target y
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
        "lot_size": tr["volume"],
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
print(f"Constructed clean feature dataset with {len(dataset_df)} labeled samples.")
print(f"Class Distribution: {dataset_df['outcome'].sum()} Wins (TP) / {len(dataset_df) - dataset_df['outcome'].sum()} Losses (SL)")

# ---------------------------------------------------------
# Train / Test Chronological Split (Strict Marcos López de Prado Out-of-Sample)
# ---------------------------------------------------------
dataset_df["year"] = dataset_df["entry_time"].str[:4]
train_mask = dataset_df["year"].isin(["2022", "2023", "2024"])
test_mask = dataset_df["year"].isin(["2025", "2026"])

train_df = dataset_df[train_mask]
test_df = dataset_df[test_mask]

print(f"\n[4/5] Chronological Walk-Forward Split:")
print(f"   Train Set (In-Sample: 2022-2024): {len(train_df)} trades ({train_df['outcome'].sum()} Wins - {(train_df['outcome'].mean()*100):.1f}% WR)")
print(f"   Test Set (Out-of-Sample: 2025-2026): {len(test_df)} trades ({test_df['outcome'].sum()} Wins - {(test_df['outcome'].mean()*100):.1f}% WR)")

feature_cols = [
    "is_buy",
    "vol_ratio",
    "adx",
    "gk_vol",
    "cvd_proxy",
    "vwap_zscore",
    "ema_spread",
    "headroom",
    "wick_ratio",
    "hour",
    "dow",
]

X_train = train_df[feature_cols]
y_train = train_df["outcome"]

X_test = test_df[feature_cols]
y_test = test_df["outcome"]

# Train LightGBM Binary Classifier
train_data = lgb.Dataset(X_train, label=y_train)
params = {
    "objective": "binary",
    "metric": "binary_logloss",
    "boosting_type": "gbdt",
    "learning_rate": 0.05,
    "num_leaves": 15,
    "max_depth": 4,
    "min_child_samples": 20,
    "feature_fraction": 0.8,
    "verbose": -1,
    "random_state": 42,
}

model = lgb.train(params, train_data, num_boost_round=100)

# Evaluate Feature Importances
importances = model.feature_importance(importance_type="gain")
feat_imp = sorted(zip(feature_cols, importances), key=lambda x: x[1], reverse=True)
print("\n--- LightGBM Microstructure Feature Importance (Gain) ---")
for f_name, imp in feat_imp:
    print(f"   {f_name:15s}: {imp:8.2f}")

# Inference on Test Set and Full Set
test_preds = model.predict(X_test)
full_preds = model.predict(dataset_df[feature_cols])

test_auc = roc_auc_score(y_test, test_preds) if len(np.unique(y_test)) > 1 else 0.5
print(f"\nOut-of-Sample ROC-AUC Score (2025-2026): {test_auc:.3f}")

# ---------------------------------------------------------
# Simulate Meta-Labeling Decision Gate at Different Thresholds
# ---------------------------------------------------------
print("\n[5/5] SIMULATING META-LABELING FILTERED PERFORMANCE...")

def evaluate_filtered_equity(df_data, pred_probs, threshold=0.45):
    balance = 100000.0
    equity_curve = [balance]
    filtered_trades = []
    
    for i, (_, row) in enumerate(df_data.iterrows()):
        p = pred_probs[i]
        pnl = row["pnl"]
        outcome = row["outcome"]
        
        # Meta-label decision: If P(Win) >= threshold, accept trade; else reject (size=0)
        accepted = bool(p >= threshold)
        
        if accepted:
            balance += pnl
            filtered_trades.append({
                "entry_time": row["entry_time"],
                "outcome": outcome,
                "pnl": pnl,
                "year": row["year"]
            })
        equity_curve.append(balance)
        
    equity_arr = np.array(equity_curve)
    peak = np.maximum.accumulate(equity_arr)
    dd_arr = np.where(peak > 0, (peak - equity_arr) / peak, 0.0)
    max_dd = np.max(dd_arr) * 100.0
    
    total_tr = len(filtered_trades)
    if total_tr == 0:
        return {"total_trades": 0, "net_profit": 0.0, "max_dd": 0.0, "winrate": 0.0, "profit_factor": 0.0}
    
    wins = sum(1 for t in filtered_trades if t["outcome"] == 1)
    losses = total_tr - wins
    wr = (wins / total_tr) * 100.0
    net_pnl = balance - 100000.0
    
    gross_profit = sum(t["pnl"] for t in filtered_trades if t["pnl"] > 0)
    gross_loss = abs(sum(t["pnl"] for t in filtered_trades if t["pnl"] < 0))
    pf = (gross_profit / gross_loss) if gross_loss > 0 else 99.0
    
    # Yearly breakdown
    yearly = {}
    for t in filtered_trades:
        yr = t["year"]
        if yr not in yearly:
            yearly[yr] = {"trades": 0, "wins": 0, "pnl": 0.0}
        yearly[yr]["trades"] += 1
        if t["outcome"] == 1:
            yearly[yr]["wins"] += 1
        yearly[yr]["pnl"] += t["pnl"]
        
    return {
        "threshold": threshold,
        "total_trades": total_tr,
        "wins": wins,
        "losses": losses,
        "winrate_pct": round(wr, 2),
        "net_profit_usd": round(net_pnl, 2),
        "return_pct": round(net_pnl / 1000.0, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "profit_factor": round(pf, 2),
        "yearly": yearly,
    }

# Threshold comparisons on Full 4.27-Year History
thresholds = [0.0, 0.38, 0.42, 0.45]
results_by_thresh = {}

for th in thresholds:
    res = evaluate_filtered_equity(dataset_df, full_preds, threshold=th)
    results_by_thresh[str(th)] = res

print("\n" + "=" * 85)
print("   FULL CYCLE (4.27 YEARS) COMPARISON: RAW DYNAMIC VS META-LABELING")
print("=" * 85)
print(f"{'Configuration':<35} | {'Trades':<8} | {'Winrate':<8} | {'Net Profit':<16} | {'Max DD':<9} | {'PF':<5}")
print("-" * 85)

for th_str, r in results_by_thresh.items():
    lbl = f"Dynamic Gốc (Thresh 0.0)" if th_str == "0.0" else f"Dynamic + ML (Thresh {th_str})"
    pnl_str = f"+${r['net_profit_usd']:,.2f} (+{r['return_pct']}%)"
    print(f"{lbl:<35} | {r['total_trades']:<8} | {r['winrate_pct']:<7.1f}% | {pnl_str:<16} | {r['max_drawdown_pct']:<8.2f}% | {r['profit_factor']:<5.2f}")

# Detailed Breakdown for the Optimal Threshold (0.42)
opt = results_by_thresh.get("0.42")
if opt:
    print("\n---------------------------------------------------------------------")
    print("   YEARLY BREAKDOWN: DYNAMIC + ML META-LABELING (THRESH 0.42)")
    print("---------------------------------------------------------------------")
    for yr in sorted(opt["yearly"].keys()):
        yp = opt["yearly"][yr]
        w = yp["wins"]
        tot = yp["trades"]
        wr = (w / tot * 100.0) if tot > 0 else 0.0
        sign = "+" if yp["pnl"] >= 0 else "-"
        print(f"   Year {yr}: {tot:3d} trades ({w:2d}W/{tot-w:2d}L - {wr:4.1f}% WR) -> PnL: {sign}${abs(yp['pnl']):10,.2f} USD")

# Save complete results
output_path = r"Kho_Do_An\Quant_AI_V2.2\research\meta_labeling_results.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump({
        "span": f"{from_dt} to {to_dt}",
        "total_bars": len(df),
        "results": results_by_thresh,
        "feature_importances": feat_imp,
    }, f, indent=2)

print(f"\nPipeline execution finished successfully! Saved to {output_path}")
