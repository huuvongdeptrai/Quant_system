from pathlib import Path
import json
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pandas as pd
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve()
while (
    PROJECT_ROOT.parent != PROJECT_ROOT
    and not (PROJECT_ROOT / "frontend" / "quant_ai.ui").exists()
    and not (PROJECT_ROOT / "quant_ai.ui").exists()
    and not (PROJECT_ROOT / "config").exists()
):
    PROJECT_ROOT = PROJECT_ROOT.parent


class FVG:
    def __init__(self, top: float, btm: float, is_bull: bool, start_idx: int):
        self.top = top
        self.btm = btm
        self.is_bull = is_bull
        self.start_idx = start_idx
        self.is_mitigated = False


class OrderBlock:
    def __init__(
        self,
        top: float,
        btm: float,
        is_bull: bool,
        base_score: float,
        start_idx: int,
        has_fvg: bool = False,
    ):
        self.top = top
        self.btm = btm
        self.is_bull = is_bull
        self.base_score = base_score
        self.start_idx = start_idx
        self.has_fvg = has_fvg
        self.max_disp = 0.0
        self.touch_count = 0
        self.is_mitigated = False
        self.is_touching = False

    def current_score(self) -> float:
        disp_score = min(30.0, self.max_disp * 10.0)
        return min(100.0, self.base_score + disp_score)

    def is_hpz(self, threshold: float = 70.0) -> bool:
        return self.current_score() >= threshold


class ICTZonesProStrategy:
    """
    Chiến lược giao dịch ICT Trading Zones Pro (Bản chuẩn hóa hội tụ OB + FVG & Structural SL).
    Đã khắc phục hoàn toàn các điểm nghẽn:
    - Nghịch lý triệt tiêu FVG khi giá retest Order Block
    - Đè bẹp SL cấu trúc
    - Lỗi múi giờ Killzone trên nến MT5
    - Lỗi dìm điểm Volume do Min-Max scaling
    - Tối ưu hóa I/O và hiệu năng đa khung thời gian H1
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.ob_length = self.config.get("ob_length", 5)
        self.hpz_threshold = self.config.get("hpz_threshold", 70.0)
        self.momentum_period = self.config.get("momentum_period", 50)
        self.fvg_threshold_per = self.config.get("fvg_threshold_per", 0.05)
        self.min_confluence = max(2, int(self.config.get("min_confluence", 2)))
        self.require_pa = self.config.get("require_pa", True)
        self.lookback_bars = self.config.get("lookback_bars", 300)
        self.sweep_len = self.config.get("sweep_len", 20)
        self.sweep_memory = self.config.get("sweep_memory", 12)
        self.persist_state = self.config.get("persist_state", False)
        self.save_state = self.config.get("save_state", False)

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # 1. Chỉ báo ATR 14
        df["prev_close"] = df["close"].shift(1)
        df["tr"] = np.maximum(
            df["high"] - df["low"],
            np.maximum(
                (df["high"] - df["prev_close"]).abs(),
                (df["low"] - df["prev_close"]).abs(),
            ),
        )
        df["atr"] = df["tr"].rolling(window=14, min_periods=1).mean()

        # 2. Momentum Z-Score
        df["price_change"] = df["close"].diff()
        df["avg_change"] = df["price_change"].rolling(self.momentum_period).mean()
        df["std_change"] = df["price_change"].rolling(self.momentum_period).std()
        df["momentum_z"] = np.where(
            df["std_change"] > 0,
            (df["price_change"] - df["avg_change"]) / df["std_change"],
            0.0,
        )

        # 3. Xếp hạng phần trăm Volume theo Gaussian Z-Score (Miễn nhiễm với nến giật tin tức)
        vol_ma = df["tick_volume"].rolling(20, min_periods=5).mean()
        vol_std = df["tick_volume"].rolling(20, min_periods=5).std().replace(0, 1.0)
        vol_z = (df["tick_volume"] - vol_ma) / vol_std
        df["vol_pct_rank"] = np.clip((vol_z + 2.0) / 4.0 * 100.0, 0.0, 100.0)

        # 4. Xu hướng cấu trúc SMA20 & SMA50
        df["sma20"] = df["close"].rolling(20).mean()
        df["sma50"] = df["close"].rolling(50).mean()
        df["bias"] = np.where(
            df["sma20"] > df["sma50"],
            1,
            np.where(df["sma20"] < df["sma50"], -1, 0),
        )

        # 5. Đỉnh / Đáy thanh khoản cục bộ
        df["prev_sw_high"] = df["high"].rolling(self.sweep_len).max().shift(1)
        df["prev_sw_low"] = df["low"].rolling(self.sweep_len).min().shift(1)

        return df

    def analyze(
        self, df: pd.DataFrame, macro_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        macro_context = macro_context or {}
        if len(df) < max(self.momentum_period, 100) + 10:
            return {"action": "HOLD", "signal": "HOLD", "confidence": 0.0}

        df = self._calculate_indicators(df)

        # --- 1. TÍNH TOÁN ASIAN RANGE AN TOÀN ---
        has_asian_range = False
        asian_high = np.nan
        asian_low = np.nan
        try:
            if "time" in df.columns and pd.api.types.is_datetime64_any_dtype(df["time"]):
                asia_bars = df[(df["time"].dt.hour >= 1) & (df["time"].dt.hour < 7)]
                if not asia_bars.empty:
                    last_asia_date = asia_bars["time"].dt.date.iloc[-1]
                    current_asia = asia_bars[asia_bars["time"].dt.date == last_asia_date]
                    if not current_asia.empty:
                        asian_high = float(current_asia["high"].max())
                        asian_low = float(current_asia["low"].min())
                        has_asian_range = True
        except Exception as err:
            logger.debug(f"[ICTStrategy] Asian range calculation skipped: {err}")

        # --- 2. MTFA: LẤY ORDER BLOCK TỪ KHUNG H1 (TỐI ƯU HÓA HIỆU NĂNG) ---
        active_h1_obs = []
        try:
            if "time" in df.columns and pd.api.types.is_datetime64_any_dtype(df["time"]):
                df_h1_input = df.iloc[-600:] if len(df) > 600 else df
                df_h1 = (
                    df_h1_input.set_index("time")
                    .resample("1h")
                    .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
                    .dropna()
                    .reset_index()
                )

                h1_obs_temp = []
                for j in range(3, len(df_h1) - 1):
                    piv_idx = j - 1
                    piv = df_h1.iloc[piv_idx]
                    prev_c = df_h1.iloc[piv_idx - 1]
                    next_c = df_h1.iloc[j]

                    is_swing_low = piv["low"] <= prev_c["low"] and next_c["close"] > piv["high"]
                    is_swing_high = piv["high"] >= prev_c["high"] and next_c["close"] < piv["low"]

                    if is_swing_low:
                        h1_obs_temp.append({
                            "type": "BULL",
                            "top": max(piv["open"], piv["close"]),
                            "btm": piv["low"],
                            "broken": False,
                            "confirm_idx": j,
                        })
                    if is_swing_high:
                        h1_obs_temp.append({
                            "type": "BEAR",
                            "top": piv["high"],
                            "btm": min(piv["open"], piv["close"]),
                            "broken": False,
                            "confirm_idx": j,
                        })

                for h_ob in h1_obs_temp:
                    for j in range(h_ob["confirm_idx"] + 1, len(df_h1)):
                        curr_c = df_h1.iloc[j]
                        if h_ob["type"] == "BULL" and curr_c["close"] < h_ob["btm"]:
                            h_ob["broken"] = True
                            break
                        if h_ob["type"] == "BEAR" and curr_c["close"] > h_ob["top"]:
                            h_ob["broken"] = True
                            break
                active_h1_obs = [ob for ob in h1_obs_temp if not ob["broken"]][-3:]
        except Exception as err:
            logger.debug(f"[ICTStrategy] H1 MTFA calculation skipped: {err}")

        # --- 3. QUÉT CẤU TRÚC FVG, SWEEP & ORDER BLOCK ---
        active_fvgs: List[FVG] = []
        ifvg_boxes: List[FVG] = []
        active_obs: List[OrderBlock] = []

        last_bull_sweep_idx = -999
        last_bear_sweep_idx = -999

        start_idx = max(0, len(df) - self.lookback_bars)

        for i in range(start_idx, len(df)):
            if i < self.ob_length + 2:
                continue

            row = df.iloc[i]
            prev_row = df.iloc[i - 1]
            prev2_row = df.iloc[i - 2]
            atr_i = row["atr"] if (not pd.isna(row["atr"]) and row["atr"] > 0) else 1.0

            # 3.1 Quét thanh khoản
            if row["low"] < row["prev_sw_low"] and row["close"] > row["prev_sw_low"]:
                last_bull_sweep_idx = i
            if row["high"] > row["prev_sw_high"] and row["close"] < row["prev_sw_high"]:
                last_bear_sweep_idx = i

            # 3.2 Phát hiện FVG Imbalance
            thresh = self.fvg_threshold_per / 100.0
            bull_gap = row["low"] - prev2_row["high"]
            bear_gap = prev2_row["low"] - row["high"]

            is_bull_fvg = (
                bull_gap > max(prev2_row["high"] * thresh, atr_i * 0.15)
                and prev_row["close"] > prev2_row["high"]
            )
            is_bear_fvg = (
                bear_gap > max(row["high"] * thresh, atr_i * 0.15)
                and prev_row["close"] < prev2_row["low"]
            )

            if is_bull_fvg:
                active_fvgs.insert(
                    0, FVG(top=row["low"], btm=prev2_row["high"], is_bull=True, start_idx=i - 2)
                )
            if is_bear_fvg:
                active_fvgs.insert(
                    0, FVG(top=prev2_row["low"], btm=row["high"], is_bull=False, start_idx=i - 2)
                )

            # Cập nhật trạng thái lấp đầy FVG
            fvgs_to_keep = []
            for f in active_fvgs:
                is_broken = (row["close"] < f.btm) if f.is_bull else (row["close"] > f.top)
                if is_broken:
                    ifvg_boxes.insert(0, f)
                    if len(ifvg_boxes) > 5:
                        ifvg_boxes.pop()
                else:
                    fvgs_to_keep.append(f)
            active_fvgs = fvgs_to_keep[:30]

            # 3.3 Phát hiện Order Block chuẩn Pivot
            piv_idx = i - self.ob_length
            piv_high = df["high"].iloc[piv_idx]
            piv_low = df["low"].iloc[piv_idx]
            subseq_high = df["high"].iloc[piv_idx + 1 : i + 1].max()
            subseq_low = df["low"].iloc[piv_idx + 1 : i + 1].min()
            prev_window_low = df["low"].iloc[max(0, piv_idx - self.ob_length) : piv_idx].min()
            prev_window_high = df["high"].iloc[max(0, piv_idx - self.ob_length) : piv_idx].max()

            is_swing_low_ob = (
                piv_low <= prev_window_low
                and piv_low <= subseq_low
                and row["close"] > piv_high + atr_i * 0.25
            )
            is_swing_high_ob = (
                piv_high >= prev_window_high
                and piv_high >= subseq_high
                and row["close"] < piv_low - atr_i * 0.25
            )

            # Kiểm tra xem có FVG sinh ra ngay sau OB hay không (Đặc tính vĩnh viễn của OB)
            has_ob_fvg = is_bull_fvg or is_bear_fvg

            mZ = float(df["momentum_z"].iloc[i - 1])
            vP = float(df["vol_pct_rank"].iloc[piv_idx])
            base_score = min(75.0, abs(mZ) * 10.0 + vP * 0.45)

            if is_swing_low_ob and (not active_obs or active_obs[0].start_idx != piv_idx):
                active_obs.insert(
                    0, OrderBlock(piv_high, piv_low, True, base_score, piv_idx, has_fvg=has_ob_fvg)
                )
            elif is_swing_high_ob and (not active_obs or active_obs[0].start_idx != piv_idx):
                active_obs.insert(
                    0, OrderBlock(piv_high, piv_low, False, base_score, piv_idx, has_fvg=has_ob_fvg)
                )

            # 3.4 Cập nhật trạng thái Order Block
            obs_to_keep = []
            clearance = atr_i * 0.5
            for ob in active_obs:
                if ob.is_bull:
                    mitigated = row["close"] < ob.btm
                    if not mitigated:
                        in_zone = row["low"] <= ob.top and row["close"] >= ob.btm
                        if in_zone:
                            if not ob.is_touching and i > ob.start_idx + self.ob_length:
                                ob.touch_count += 1
                                ob.is_touching = True
                        elif row["low"] > ob.top + clearance:
                            ob.is_touching = False

                        cur_disp = max(0.0, row["high"] - ob.top) / atr_i
                        ob.max_disp = max(ob.max_disp, cur_disp)
                        obs_to_keep.append(ob)
                else:
                    mitigated = row["close"] > ob.top
                    if not mitigated:
                        in_zone = row["high"] >= ob.btm and row["close"] <= ob.top
                        if in_zone:
                            if not ob.is_touching and i > ob.start_idx + self.ob_length:
                                ob.touch_count += 1
                                ob.is_touching = True
                        elif row["high"] < ob.btm - clearance:
                            ob.is_touching = False

                        cur_disp = max(0.0, ob.btm - row["low"]) / atr_i
                        ob.max_disp = max(ob.max_disp, cur_disp)
                        obs_to_keep.append(ob)

            bull_obs = [ob for ob in obs_to_keep if ob.is_bull][:3]
            bear_obs = [ob for ob in obs_to_keep if not ob.is_bull][:3]
            active_obs = bull_obs + bear_obs

        # === 4. ĐÁNH GIÁ HỘI TỤ & TẠO TÍN HIỆU ===
        last_idx = len(df) - 1
        curr = df.iloc[last_idx]
        prev = df.iloc[last_idx - 1]
        atr = float(curr["atr"]) if (not pd.isna(curr["atr"]) and curr["atr"] > 0) else 1.0

        # Khung giờ Killzone chuẩn sàn MT5 (EET: 09:00 - 21:00 bao quát cả London và NY Session)
        broker_hour = int(curr["time"].hour) if "time" in curr and hasattr(curr["time"], "hour") else 12
        in_killzone = (9 <= broker_hour <= 21)
        require_pa_now = self.require_pa or (broker_hour >= 15)

        def check_pa(is_bull: bool) -> bool:
            candle_range = max(curr["high"] - curr["low"], 1e-9)
            w_top = curr["high"] - max(curr["close"], curr["open"])
            w_btm = min(curr["close"], curr["open"]) - curr["low"]

            if is_bull:
                strong_bull_close = (
                    curr["close"] > curr["open"]
                    and (curr["close"] - curr["low"]) / candle_range >= 0.50
                )
                pinbar_rejection = (w_btm / candle_range >= 0.40) and (curr["close"] >= prev["low"])
                return strong_bull_close or pinbar_rejection
            else:
                strong_bear_close = (
                    curr["close"] < curr["open"]
                    and (curr["high"] - curr["close"]) / candle_range >= 0.50
                )
                pinbar_rejection = (w_top / candle_range >= 0.40) and (curr["close"] <= prev["high"])
                return strong_bear_close or pinbar_rejection

        def has_ifvg_overlap(z_top: float, z_btm: float) -> bool:
            for ifvg in ifvg_boxes:
                if z_btm <= ifvg.top and z_top >= ifvg.btm:
                    return True
            return False

        def calc_confluence(is_long: bool) -> Tuple[int, float, float]:
            score = 0
            in_ob = False
            price = float(curr["close"])
            z_top = price
            z_btm = price

            for ob in active_obs:
                if ob.is_bull != is_long:
                    continue

                if is_long:
                    interacts = curr["low"] <= ob.top and curr["close"] >= ob.btm
                    swept = curr["low"] < ob.btm and curr["close"] > ob.btm
                else:
                    interacts = curr["high"] >= ob.btm and curr["close"] <= ob.top
                    swept = curr["high"] > ob.top and curr["close"] < ob.top

                if not interacts:
                    continue

                is_valid_sweep = swept and check_pa(is_long)
                if ob.touch_count >= 3 and not is_valid_sweep:
                    continue

                in_ob = True
                z_top = ob.top
                z_btm = ob.btm

                # 1. Điểm chất lượng Order Block
                score += 2 if ob.is_hpz(self.hpz_threshold) else 1
                if is_valid_sweep:
                    score += 1

                # 2. Điểm cộng Displacement FVG (Khắc phục lỗi triệt tiêu)
                if ob.has_fvg:
                    score += 1

                # 3. Điểm cộng Judas Swing (Quét qua biên độ phiên Á)
                if has_asian_range:
                    if is_long and (ob.btm <= asian_low or curr["low"] <= asian_low):
                        score += 1
                    elif not is_long and (ob.top >= asian_high or curr["high"] >= asian_high):
                        score += 1

                # 4. Điểm cộng đồng thuận vùng H1 POI
                for h_ob in active_h1_obs:
                    if is_long and h_ob["type"] == "BULL":
                        if ob.btm <= h_ob["top"] + atr * 0.5 and ob.top >= h_ob["btm"] - atr * 0.5:
                            score += 1
                            break
                    elif not is_long and h_ob["type"] == "BEAR":
                        if ob.top >= h_ob["btm"] - atr * 0.5 and ob.btm <= h_ob["top"] + atr * 0.5:
                            score += 1
                            break

                break

            # Không chạm vào Order Block hợp lệ thì không mở lệnh
            if not in_ob:
                return 0, z_top, z_btm

            bias = int(curr["bias"])
            if (is_long and bias == 1) or (not is_long and bias == -1):
                score += 1

            recent_bull_sweep = (last_idx - last_bull_sweep_idx) <= self.sweep_memory
            recent_bear_sweep = (last_idx - last_bear_sweep_idx) <= self.sweep_memory
            if (is_long and recent_bull_sweep) or (not is_long and recent_bear_sweep):
                score += 1

            if has_ifvg_overlap(z_top, z_btm):
                score -= 1

            if require_pa_now and not check_pa(is_long):
                return 0, z_top, z_btm

            return max(0, score), z_top, z_btm

        # Ghi trạng thái ra file chỉ khi được yêu cầu tường minh
        if getattr(self, "persist_state", False) or getattr(self, "save_state", False):
            try:
                state_file = PROJECT_ROOT / "data" / "strategy_state.json"
                state_file.parent.mkdir(parents=True, exist_ok=True)
                serialized_obs = [
                    {
                        "top": ob.top,
                        "btm": ob.btm,
                        "is_bull": ob.is_bull,
                        "score": ob.current_score(),
                        "start_idx": ob.start_idx,
                    }
                    for ob in active_obs
                ]
                with open(state_file, "w") as f:
                    json.dump(
                        {"strategy": "ICT_Zones_Pro", "active_obs": serialized_obs},
                        f,
                        indent=4,
                    )
            except Exception as e:
                logger.warning(f"Lỗi lưu state: {e}")

        l_score, l_top, l_btm = calc_confluence(is_long=True)
        s_score, s_top, s_btm = calc_confluence(is_long=False)

        action = "HOLD"
        confidence = 0.0
        entry = float(curr["close"])
        sl = None
        tp1 = None
        tp2 = None

        volatility = macro_context.get("volatility_risk", "LOW")
        macro_bias = macro_context.get("bias", "NEUTRAL")

        if volatility == "HIGH":
            min_conf = self.min_confluence + 2
        elif volatility == "MEDIUM":
            min_conf = self.min_confluence + 1
        else:
            min_conf = self.min_confluence

        # Tính toán Lệnh BUY (Cắt lỗ theo Cấu trúc thực tế)
        if l_score >= min_conf and l_score > s_score and in_killzone:
            if macro_bias != "BEARISH":
                structural_low = min(l_btm, float(curr["low"]), float(prev["low"]))
                sl_candidate = structural_low - atr * 0.6
                risk_candidate = entry - sl_candidate

                # Bộ lọc chống đuổi giá: Không vào lệnh nếu giá đã chạy quá 3.0 ATR so với cấu trúc
                if atr * 0.8 <= risk_candidate <= atr * 3.0:
                    sl = sl_candidate
                    risk = risk_candidate
                    action = "BUY"
                    confidence = round(min(1.0, l_score / 6.0), 2)
                    rr = 2.0
                    tp1 = entry + risk * rr
                    tp2 = entry + risk * (rr * 2.0)

        # Tính toán Lệnh SELL (Cắt lỗ theo Cấu trúc thực tế)
        elif s_score >= min_conf and s_score > l_score and in_killzone:
            if macro_bias != "BULLISH":
                structural_high = max(s_top, float(curr["high"]), float(prev["high"]))
                sl_candidate = structural_high + atr * 0.6
                risk_candidate = sl_candidate - entry

                # Bộ lọc chống đuổi giá
                if atr * 0.8 <= risk_candidate <= atr * 3.0:
                    sl = sl_candidate
                    risk = risk_candidate
                    action = "SELL"
                    confidence = round(min(1.0, s_score / 6.0), 2)
                    rr = 2.0
                    tp1 = entry - risk * rr
                    tp2 = entry - risk * (rr * 2.0)

        return {
            "strategy": "ICT_Zones_Pro",
            "action": action,
            "signal": action,
            "entry_price": entry,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "confidence": confidence,
            "score": max(l_score, s_score),
            "metadata": {
                "active_fvgs": len(active_fvgs),
                "active_obs": len(active_obs),
                "bias": int(curr["bias"]),
            },
        }
