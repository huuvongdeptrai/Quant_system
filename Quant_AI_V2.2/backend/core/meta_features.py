"""Causal shared feature contract for training and live Meta-Labeling."""
from datetime import datetime, timezone
import numpy as np
import pandas as pd

FEATURE_COLUMNS = ['is_buy','vol_ratio','adx','gk_vol','cvd_proxy','vwap_zscore','ema_spread','headroom','wick_ratio','hour','dow']
FEATURE_VERSION = 'vectra-meta-v2'

def build_meta_features(rates,signal):
    if signal not in ('BUY','SELL') or rates is None or len(rates)<100:
        raise ValueError('At least 100 completed bars and a valid direction are required')
    rates=rates[-300:] if not isinstance(rates,pd.DataFrame) else rates.tail(300).copy()
    if isinstance(rates, pd.DataFrame):
        df = rates
    else:
        df = pd.DataFrame(rates)
    if "time" in df.columns and not pd.api.types.is_datetime64_any_dtype(df["time"]):
        df["time"] = pd.to_datetime(df["time"], unit="s")

    closes = df["close"].to_numpy(dtype=np.float64)
    highs = df["high"].to_numpy(dtype=np.float64)
    lows = df["low"].to_numpy(dtype=np.float64)
    opens = df["open"].to_numpy(dtype=np.float64)
    volumes = df["tick_volume"].to_numpy(dtype=np.float64) if "tick_volume" in df.columns else np.ones(len(closes)) * 1000.0

    n_bars = len(closes)
    tr1 = highs[1:] - lows[1:]
    tr2 = np.abs(highs[1:] - closes[:-1])
    tr3 = np.abs(lows[1:] - closes[:-1])
    tr = np.maximum(tr1, np.maximum(tr2, tr3))
    atr = np.zeros(n_bars)
    atr[14] = np.mean(tr[:14])
    for i in range(15, n_bars):
        atr[i] = (atr[i - 1] * 13 + tr[i - 1]) / 14.0
    curr_atr = atr[-1] if atr[-1] > 1e-4 else 1.0

    def calc_ema(arr, period):
        res = np.zeros(len(arr))
        alpha = 2.0 / (period + 1.0)
        res[period - 1] = np.mean(arr[:period])
        for i in range(period, len(arr)):
            res[i] = (arr[i] - res[i - 1]) * alpha + res[i - 1]
        return res

    ema20 = calc_ema(closes, 20)[-1]
    ema50 = calc_ema(closes, 50)[-1]
    vol_ma20 = calc_ema(volumes, 20)[-1]

    up_move = highs[1:] - highs[:-1]
    down_move = lows[:-1] - lows[1:]
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr_smooth = np.zeros(n_bars)
    p_dm_smooth = np.zeros(n_bars)
    m_dm_smooth = np.zeros(n_bars)
    tr_smooth[14] = np.sum(tr[:14])
    p_dm_smooth[14] = np.sum(plus_dm[:14])
    m_dm_smooth[14] = np.sum(minus_dm[:14])
    for idx in range(15, n_bars):
        tr_smooth[idx] = tr_smooth[idx - 1] - (tr_smooth[idx - 1] / 14.0) + tr[idx - 1]
        p_dm_smooth[idx] = p_dm_smooth[idx - 1] - (p_dm_smooth[idx - 1] / 14.0) + plus_dm[idx - 1]
        m_dm_smooth[idx] = m_dm_smooth[idx - 1] - (m_dm_smooth[idx - 1] / 14.0) + minus_dm[idx - 1]
    safe_tr = np.where(tr_smooth > 1e-9, tr_smooth, 1e-9)
    plus_di = 100.0 * (p_dm_smooth / safe_tr)
    minus_di = 100.0 * (m_dm_smooth / safe_tr)
    di_sum = plus_di + minus_di
    safe_di_sum = np.where(di_sum > 1e-9, di_sum, 1e-9)
    dx = 100.0 * np.abs(plus_di - minus_di) / safe_di_sum
    adx14 = np.zeros(n_bars)
    if n_bars >= 28:
        adx14[27] = np.mean(dx[14:28])
        for idx in range(28, n_bars):
            adx14[idx] = (adx14[idx - 1] * 13.0 + dx[idx]) / 14.0
    curr_adx = float(adx14[-1])

    log_hl = np.log(highs[-14:] / np.maximum(lows[-14:], 1e-9))
    log_co = np.log(closes[-14:] / np.maximum(opens[-14:], 1e-9))
    gk_bar = 0.5 * (log_hl ** 2) - (2.0 * np.log(2.0) - 1.0) * (log_co ** 2)
    gk_vol = float(np.sqrt(max(0.0, np.mean(gk_bar))) * 1000.0)

    p_diff = np.diff(closes[-11:])
    s_vol = np.where(p_diff > 0, volumes[-10:], np.where(p_diff < 0, -volumes[-10:], 0.0))
    cvd_proxy = float(np.sum(s_vol) / max(1.0, np.sum(volumes[-10:])))

    w_len = min(96, n_bars)
    pv_sub = closes[-w_len:] * volumes[-w_len:]
    vwap = np.sum(pv_sub) / max(1.0, np.sum(volumes[-w_len:]))
    vwap_z = float((closes[-1] - vwap) / curr_atr)

    look_sr = min(30, n_bars - 1)
    high_30 = float(np.max(highs[-look_sr - 1 : -1]))
    low_30 = float(np.min(lows[-look_sr - 1 : -1]))
    is_buy = 1 if signal == "BUY" else 0
    if is_buy:
        headroom = float((high_30 - closes[-1]) / curr_atr)
        c_rng = max(1e-4, highs[-1] - lows[-1])
        wick_ratio = float((highs[-1] - max(closes[-1], opens[-1])) / c_rng)
    else:
        headroom = float((closes[-1] - low_30) / curr_atr)
        c_rng = max(1e-4, highs[-1] - lows[-1])
        wick_ratio = float((min(closes[-1], opens[-1]) - lows[-1]) / c_rng)

    vol_ratio = float(volumes[-1] / max(1.0, vol_ma20))
    ema_spread = float(abs(ema20 - ema50) / curr_atr)

    last_time = df["time"].iloc[-1] if "time" in df.columns else datetime.now(timezone.utc)
    hour_val = int(getattr(last_time, "hour", 12))
    dow_val = int(getattr(last_time, "weekday", lambda: 2)()) if callable(getattr(last_time, "weekday", None)) else int(getattr(last_time, "dayofweek", 2))

    feat_dict = {
        "is_buy": is_buy,
        "vol_ratio": round(vol_ratio, 3),
        "adx": round(curr_adx, 2),
        "gk_vol": round(gk_vol, 4),
        "cvd_proxy": round(cvd_proxy, 3),
        "vwap_zscore": round(vwap_z, 3),
        "ema_spread": round(ema_spread, 3),
        "headroom": round(headroom, 3),
        "wick_ratio": round(wick_ratio, 3),
        "hour": hour_val,
        "dow": dow_val,
    }

    return feat_dict
