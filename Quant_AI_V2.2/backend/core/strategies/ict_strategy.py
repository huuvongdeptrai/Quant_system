# -*- coding: utf-8 -*-
"""
ICT Zones Pro Strategy (Trading Zones Pro v4.2)
Quant AI V2.2 - Institutional Strategy Engine
Restored from canonical ICT strategy core.
"""

import sys
from pathlib import Path
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

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.strategies.base_strategy import (
    BaseStrategy,
    StrategySignal,
    ChecklistItem,
    ChecklistStatus,
)


class FVG:
    def __init__(self, top: float, btm: float, is_bull: bool, start_idx: int):
        self.top = top
        self.btm = btm
        self.is_bull = is_bull
        self.start_idx = start_idx
        self.is_mitigated = False


class OrderBlock:
    def __init__(
        self, top: float, btm: float, is_bull: bool, base_score: float, start_idx: int
    ):
        self.top = top
        self.btm = btm
        self.is_bull = is_bull
        self.base_score = base_score
        self.start_idx = start_idx
        self.max_disp = 0.0
        self.touch_count = 0
        self.is_mitigated = False
        self.is_touching = False

    def current_score(self) -> float:
        disp_score = min(30.0, self.max_disp * 10.0)
        return min(100.0, self.base_score + disp_score)

    def is_hpz(self, threshold: float = 80.0) -> bool:
        return self.current_score() >= threshold


class ICTZonesProStrategy(BaseStrategy):
    """
    Chiến lược giao dịch ICT Trading Zones Pro
    
    Đầu vào:
    - config: Giá trị dict, cấu hình tham số chiến lược.

    Đầu ra:
    - Giá trị None, khởi tạo đối tượng chiến lược.
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.strategy_id = "builtin_ict_pro"
        self.name = "ICT Zones Pro v4.2"
        self.ob_length = self.config.get("ob_length", 5)
        self.hpz_threshold = self.config.get("hpz_threshold", 80.0)
        self.momentum_period = self.config.get("momentum_period", 50)
        self.fvg_threshold_per = self.config.get("fvg_threshold_per", 0.1)
        self.min_confluence = self.config.get("min_confluence", 1)
        self.require_pa = self.config.get("require_pa", True)
        self.lookback_bars = self.config.get("lookback_bars", 300)  # Khôi phục trạng thái từ 300 nến
        self.sweep_len = self.config.get("sweep_len", 20)
        self.sweep_memory = self.config.get("sweep_memory", 10)
        self.save_state = self.config.get("save_state", False)

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "id": self.strategy_id,
            "name": self.name,
            "description": "Asian High/Low sweep, Judas swing, Fair Value Gap and Killzone filter.",
            "author": "Quant AI Core",
            "version": "4.2",
            "checklist_schema": [
                {"key": "Trend Structure", "description": "Higher Timeframe market bias"},
                {"key": "Liquidity Sweep", "description": "Asian session range sweep"},
                {"key": "Order Blocks & FVG", "description": "Unmitigated institutional imbalance"},
            ],
        }

    def get_default_checklist(self) -> List[ChecklistItem]:
        return [
            ChecklistItem(key="Trend Structure", value="Awaiting Clear Trend", status=ChecklistStatus.PENDING),
            ChecklistItem(key="Liquidity Sweep", value="Awaiting Asian Sweep", status=ChecklistStatus.PENDING),
            ChecklistItem(key="Order Blocks & FVG", value="Awaiting Mitigation", status=ChecklistStatus.PENDING),
        ]

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # Chỉ báo ATR 14
        df["prev_close"] = df["close"].shift(1)
        df["tr"] = np.maximum(
            df["high"] - df["low"],
            np.maximum(
                (df["high"] - df["prev_close"]).abs(),
                (df["low"] - df["prev_close"]).abs(),
            ),
        )
        df["atr"] = df["tr"].rolling(window=14).mean()

        # Momentum Z-Score
        df["price_change"] = df["close"].diff()
        df["avg_change"] = df["price_change"].rolling(self.momentum_period).mean()
        df["std_change"] = df["price_change"].rolling(self.momentum_period).std()
        df["momentum_z"] = np.where(
            df["std_change"] != 0,
            (df["price_change"] - df["avg_change"]) / df["std_change"],
            0.0,
        )

        # Xếp hạng phần trăm Volume
        vol_col = "tick_volume" if "tick_volume" in df.columns else ("volume" if "volume" in df.columns else None)
        if vol_col:
            def fast_pct_rank(x):
                return (np.count_nonzero(x <= x[-1]) / len(x)) * 100.0 if len(x) > 0 else 50.0

            df["vol_pct_rank"] = df[vol_col].rolling(100).apply(fast_pct_rank, raw=True)
        else:
            df["vol_pct_rank"] = 50.0

        # Xu hướng SMA
        df["sma20"] = df["close"].rolling(20).mean()
        df["sma50"] = df["close"].rolling(50).mean()
        df["bias"] = np.where(
            df["sma20"] > df["sma50"], 1, np.where(df["sma20"] < df["sma50"], -1, 0)
        )

        # Quét đỉnh đáy
        df["prev_sw_high"] = df["high"].rolling(self.sweep_len).max().shift(1)
        df["prev_sw_low"] = df["low"].rolling(self.sweep_len).min().shift(1)

        return df

    def analyze(self, df: pd.DataFrame, macro_context: Dict[str, Any] = None) -> StrategySignal:
        macro_context = macro_context or {}
        if len(df) < max(self.momentum_period, 100) + 10:
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_name=self.name,
                action="HOLD",
                signal="HOLD",
                entry_price=float(df["close"].iloc[-1]) if len(df) > 0 and "close" in df.columns else 0.0,
                confidence=0.0,
                checklist=self.get_default_checklist(),
                metadata={"strategy": "ICT_Zones_Pro", "active_fvgs": 0, "active_obs": 0, "bias": 0},
            )

        df = self._calculate_indicators(df)

        # --- TÍNH TOÁN ASIAN RANGE ---
        asian_high = float("inf")
        asian_low = -float("inf")
        try:
            if "time" in df.columns:
                time_s = df["time"]
                if not pd.api.types.is_datetime64_any_dtype(time_s):
                    time_s = pd.to_datetime(time_s)
                asia_mask = (time_s.dt.hour >= 1) & (time_s.dt.hour < 7)
                asia_bars = df[asia_mask]
                if not asia_bars.empty:
                    asia_dates = time_s[asia_mask].dt.date
                    last_asia_date = asia_dates.iloc[-1]
                    current_asia = asia_bars[asia_dates == last_asia_date]
                    asian_high = float(current_asia["high"].max())
                    asian_low = float(current_asia["low"].min())
        except Exception as err:
            logger.debug(f"[ICTStrategy] Asian range calculation skipped: {err}")

        # --- MTFA: LẤY ORDER BLOCK TỪ KHUNG LỚN (H1 POI) ---
        active_h1_obs = []
        try:
            if "time" in df.columns:
                df_h1_input = df.iloc[-2000:] if len(df) > 2000 else df
                df_h1_time = df_h1_input.copy()
                if not pd.api.types.is_datetime64_any_dtype(df_h1_time["time"]):
                    df_h1_time["time"] = pd.to_datetime(df_h1_time["time"])
                df_h1 = (
                    df_h1_time.set_index("time")
                    .resample("1h")
                    .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
                    .dropna()
                    .reset_index()
                )

                h1_len = len(df_h1)
                h1_open = df_h1["open"].to_numpy(dtype=float)
                h1_high = df_h1["high"].to_numpy(dtype=float)
                h1_low = df_h1["low"].to_numpy(dtype=float)
                h1_close = df_h1["close"].to_numpy(dtype=float)

                h1_obs_temp = []
                for j in range(5, h1_len - 1):
                    p_idx = j - 5
                    p_low = h1_low[p_idx]
                    p_high = h1_high[p_idx]
                    p_open = h1_open[p_idx]
                    p_close = h1_close[p_idx]

                    is_sl = True
                    is_sh = True
                    for k in range(1, 6):
                        if k != 5:
                            if h1_low[j - k] < p_low:
                                is_sl = False
                            if h1_high[j - k] > p_high:
                                is_sh = False

                    if is_sl and p_close < p_open:
                        h1_obs_temp.append({
                            "type": "BULL",
                            "top": p_open,
                            "btm": p_low,
                            "broken": False,
                            "start_idx": p_idx,
                        })
                    if is_sh and p_close > p_open:
                        h1_obs_temp.append({
                            "type": "BEAR",
                            "top": p_high,
                            "btm": p_open,
                            "broken": False,
                            "start_idx": p_idx,
                        })

                for h_ob in h1_obs_temp:
                    s_idx = h_ob["start_idx"] + 1
                    ob_type = h_ob["type"]
                    ob_btm = h_ob["btm"]
                    ob_top = h_ob["top"]
                    for j in range(s_idx, h1_len):
                        c_val = h1_close[j]
                        if ob_type == "BULL" and c_val < ob_btm:
                            h_ob["broken"] = True
                            break
                        if ob_type == "BEAR" and c_val > ob_top:
                            h_ob["broken"] = True
                            break
                active_h1_obs = [ob for ob in h1_obs_temp if not ob["broken"]]
        except Exception as err:
            logger.debug(f"[ICTStrategy] H1 MTFA calculation skipped: {err}")

        n_bars = len(df)
        c_arr = df["close"].to_numpy(dtype=float)
        h_arr = df["high"].to_numpy(dtype=float)
        l_arr = df["low"].to_numpy(dtype=float)
        o_arr = df["open"].to_numpy(dtype=float) if "open" in df.columns else c_arr
        atr_arr = df["atr"].to_numpy(dtype=float)
        mZ_arr = df["momentum_z"].to_numpy(dtype=float)
        vP_arr = df["vol_pct_rank"].to_numpy(dtype=float)
        sw_low_arr = df["prev_sw_low"].to_numpy(dtype=float)
        sw_high_arr = df["prev_sw_high"].to_numpy(dtype=float)

        vol_col = "tick_volume" if "tick_volume" in df.columns else ("volume" if "volume" in df.columns else None)
        vol_arr = df[vol_col].to_numpy(dtype=float) if vol_col else None

        active_fvgs: List[FVG] = []
        ifvg_boxes: List[FVG] = []
        active_obs: List[OrderBlock] = []

        last_bull_sweep_idx = -999
        last_bear_sweep_idx = -999

        os_state = 0
        start_idx = max(0, n_bars - self.lookback_bars)

        for i in range(start_idx, n_bars):
            if i < self.ob_length + 2:
                continue

            c_i = c_arr[i]
            h_i = h_arr[i]
            l_i = l_arr[i]
            prev_c = c_arr[i - 1]
            prev2_h = h_arr[i - 2]
            prev2_l = l_arr[i - 2]

            # 1. Phát hiện quét thanh khoản
            if l_i < sw_low_arr[i] and c_i > sw_low_arr[i]:
                last_bull_sweep_idx = i
            if h_i > sw_high_arr[i] and c_i < sw_high_arr[i]:
                last_bear_sweep_idx = i

            # 2. Phát hiện vùng FVG
            thresh = self.fvg_threshold_per / 100

            is_bull_fvg = (
                (l_i > prev2_h)
                and (prev_c > prev2_h)
                and ((l_i - prev2_h) / prev2_h > thresh)
            )

            is_bear_fvg = (
                (h_i < prev2_l)
                and (prev_c < prev2_l)
                and ((prev2_l - h_i) / h_i > thresh)
            )

            if is_bull_fvg:
                active_fvgs.insert(0, FVG(top=l_i, btm=prev2_h, is_bull=True, start_idx=i - 2))
            if is_bear_fvg:
                active_fvgs.insert(0, FVG(top=prev2_l, btm=h_i, is_bull=False, start_idx=i - 2))

            # Cập nhật trạng thái FVG
            fvgs_to_keep = []
            for f in active_fvgs:
                is_broken = (l_i < f.btm) if f.is_bull else (h_i > f.top)
                if is_broken:
                    ifvg_boxes.insert(0, f)
                    if len(ifvg_boxes) > 5:
                        ifvg_boxes.pop()
                else:
                    fvgs_to_keep.append(f)
            active_fvgs = fvgs_to_keep[:50]

            # 3. Phát hiện Order Block
            high_oblen = h_arr[i - self.ob_length]
            low_oblen = l_arr[i - self.ob_length]
            upper = np.max(h_arr[i - self.ob_length + 1 : i + 1])
            lower = np.min(l_arr[i - self.ob_length + 1 : i + 1])

            if high_oblen > upper:
                os_state = 0
            elif low_oblen < lower:
                os_state = 1

            # Đỉnh Volume
            if vol_arr is not None:
                vol_start = i - self.ob_length * 2
                if vol_start >= 0:
                    vol_window = vol_arr[vol_start : i + 1]
                    if len(vol_window) == self.ob_length * 2 + 1:
                        mid_vol = vol_window[self.ob_length]
                        is_phv = True
                        for v in vol_window:
                            if v > mid_vol:
                                is_phv = False
                                break

                        if is_phv:
                            mZ = mZ_arr[i - self.ob_length]
                            vP = vP_arr[i - self.ob_length]
                            base_score = min(70.0, abs(mZ) * 7.0 + vP * 0.35)

                            if os_state == 1:  # Bull Order Block
                                active_obs.insert(0, OrderBlock(high_oblen, low_oblen, True, base_score, i - self.ob_length))
                            elif os_state == 0:  # Bear Order Block
                                active_obs.insert(0, OrderBlock(high_oblen, low_oblen, False, base_score, i - self.ob_length))

            # Dọn dẹp và cập nhật Order Block
            obs_to_keep = []
            atr_val = atr_arr[i] if not np.isnan(atr_arr[i]) and atr_arr[i] > 0 else 1.0
            clearance = atr_val * 0.5  # Giá phải rời khỏi OB ít nhất 0.5 ATR mới reset chạm

            for ob in active_obs:
                if ob.is_bull:
                    mitigated = c_i < ob.btm
                    if not mitigated:
                        in_zone = l_i <= ob.top and c_i >= ob.btm
                        if in_zone:
                            if not ob.is_touching:
                                ob.touch_count += 1
                                ob.is_touching = True
                        else:
                            if l_i > ob.top + clearance:
                                ob.is_touching = False

                        cur_disp = max(0.0, h_i - ob.top) / atr_val
                        ob.max_disp = max(ob.max_disp, cur_disp)
                        obs_to_keep.append(ob)
                else:
                    mitigated = c_i > ob.top
                    if not mitigated:
                        in_zone = h_i >= ob.btm and c_i <= ob.top
                        if in_zone:
                            if not ob.is_touching:
                                ob.touch_count += 1
                                ob.is_touching = True
                        else:
                            if h_i < ob.btm - clearance:
                                ob.is_touching = False

                        cur_disp = max(0.0, ob.btm - l_i) / atr_val
                        ob.max_disp = max(ob.max_disp, cur_disp)
                        obs_to_keep.append(ob)

            bull_obs = [ob for ob in obs_to_keep if ob.is_bull][:3]
            bear_obs = [ob for ob in obs_to_keep if not ob.is_bull][:3]
            active_obs = bull_obs + bear_obs

        # === TẠO TÍN HIỆU ===
        last_idx = len(df) - 1
        curr = df.iloc[last_idx]
        prev = df.iloc[last_idx - 1]

        # Mẫu hình giá
        def check_pa(is_bull: bool) -> bool:
            # Soft PA (Xác nhận mềm)
            body = abs(curr["close"] - curr["open"])
            wTop = curr["high"] - max(curr["close"], curr["open"])
            wBtm = min(curr["close"], curr["open"]) - curr["low"]

            if is_bull:
                # Nến xanh HOẶC râu dưới dài hơn thân (rút chân)
                is_bullish = curr["close"] > curr["open"]
                has_tail = wBtm >= body
                return is_bullish or has_tail
            else:
                # Nến đỏ HOẶC râu trên dài hơn thân (rút chân)
                is_bearish = curr["close"] < curr["open"]
                has_tail = wTop >= body
                return is_bearish or has_tail

        def has_ifvg_overlap(zTop: float, zBtm: float) -> bool:
            for ifvg in ifvg_boxes:
                if zBtm <= ifvg.top and zTop >= ifvg.btm:
                    return True
            return False

        def calc_confluence(is_long: bool) -> Tuple[int, float, float]:
            score = 0
            in_fvg = False
            in_ob = False
            zTop = curr["close"]
            zBtm = curr["close"]
            price = curr["close"]

            for f in active_fvgs:
                if (is_long and f.is_bull) or (not is_long and not f.is_bull):
                    if f.btm <= price <= f.top:
                        score += 1
                        in_fvg = True
                        zTop = f.top
                        zBtm = f.btm
                        break

            for ob in active_obs:
                if (is_long and ob.is_bull) or (not is_long and not ob.is_bull):
                    # BỘ LỌC 1: Bắt buộc có FVG (Displacement) - BẬT LẠI
                    has_fvg = False
                    for f in active_fvgs:
                        if f.is_bull == ob.is_bull:
                            if is_long and f.btm <= ob.top * 1.002:
                                has_fvg = True
                                break
                            elif not is_long and f.top >= ob.btm * 0.998:
                                has_fvg = True
                                break
                    if not has_fvg:
                        continue

                    # BỘ LỌC 2: Judas Swing (Bắt buộc quét thanh khoản phiên Á)
                    if is_long and ob.btm >= asian_low:
                        continue
                    if not is_long and ob.top <= asian_high:
                        continue

                    # BỘ LỌC 3: MTFA (Nằm trong H1 POI)
                    in_h1_poi = False
                    for h_ob in active_h1_obs:
                        if is_long and h_ob["type"] == "BULL":
                            if ob.btm <= h_ob["top"] and ob.btm >= h_ob["btm"] * 0.999:
                                in_h1_poi = True
                                break
                        elif not is_long and h_ob["type"] == "BEAR":
                            if ob.top >= h_ob["btm"] and ob.top <= h_ob["top"] * 1.001:
                                in_h1_poi = True
                                break
                    if not in_h1_poi:
                        continue

                    if is_long:
                        interacts = curr["low"] <= ob.top and curr["close"] >= ob.btm
                        swept = curr["low"] < ob.btm
                    else:
                        interacts = curr["high"] >= ob.btm and curr["close"] <= ob.top
                        swept = curr["high"] > ob.top

                    if interacts:
                        # Nếu cắn qua OB (Sweep) nhưng đóng nến hợp lệ và có PA => Vô hiệu hóa phạt touch_count
                        is_valid_sweep = swept and (not self.require_pa or check_pa(is_long))

                        if ob.touch_count >= 3 and not is_valid_sweep:
                            score = 0
                            in_ob = True
                        else:
                            ob_add = 2 if ob.is_hpz(self.hpz_threshold) else 1
                            if is_valid_sweep:
                                ob_add += 1  # Thưởng 1 điểm vì đây là cú Quét thanh khoản (Liquidity Sweep) mười mươi!

                            score += (ob_add - 1) if (ob.touch_count == 2 and not is_valid_sweep) else ob_add
                            in_ob = True
                            zTop = max(zTop, ob.top)
                            zBtm = min(zBtm, ob.btm)
                        break

            if not in_fvg and not in_ob:
                return 0, zTop, zBtm

            bias = curr["bias"]
            if (is_long and bias == 1) or (not is_long and bias == -1):
                score += 1

            recent_bull_sweep = (last_idx - last_bull_sweep_idx) <= self.sweep_memory
            recent_bear_sweep = (last_idx - last_bear_sweep_idx) <= self.sweep_memory

            if (is_long and recent_bull_sweep) or (not is_long and recent_bear_sweep):
                score += 1

            if has_ifvg_overlap(zTop, zBtm):
                score -= 1
            else:
                score += 1

            if self.require_pa and not check_pa(is_long):
                score = 0

            return max(0, score), zTop, zBtm

        if getattr(self, "save_state", True):
            import json
            state_file = PROJECT_ROOT / "data" / "strategy_state.json"

            # Tải Order Block cũ
            prev_obs = []
            if state_file.exists():
                try:
                    with open(state_file, "r") as f:
                        old_state = json.load(f)
                        prev_obs = old_state.get("active_obs", [])
                except Exception as e:
                    logger.warning(f"Lỗi đọc state cũ: {e}")

            # Ghi nhận Order Block hiện tại
            serialized_obs = []
            for ob in active_obs:
                serialized_obs.append({
                    "top": float(ob.top),
                    "btm": float(ob.btm),
                    "is_bull": ob.is_bull,
                    "score": float(ob.current_score()),
                    "start_idx": int(ob.start_idx),
                })

            # Lưu trạng thái mới
            try:
                state_file.parent.mkdir(parents=True, exist_ok=True)
                with open(state_file, "w") as f:
                    json.dump({"strategy": "ICT_Zones_Pro", "active_obs": serialized_obs}, f, indent=4)
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

        atr = float(curr["atr"]) if not pd.isna(curr["atr"]) and curr["atr"] > 0 else 1.0

        # Killzone Filter (14:00 - 23:00 VN => 07:00 - 15:59 UTC)
        in_killzone = False
        utc_hour = None
        if "time" in curr:
            time_val = curr["time"]
            utc_hour = getattr(time_val, "hour", None)
            if utc_hour is None:
                try:
                    utc_hour = pd.to_datetime(time_val).hour
                except Exception:
                    utc_hour = None
            if utc_hour is not None and 7 <= utc_hour <= 15:
                in_killzone = True

        # Phiên Mỹ (Bắt đầu từ 13:00 UTC): Yêu cầu nến râu dài để chống Stop Hunt
        if in_killzone and utc_hour is not None and utc_hour >= 13:
            # Tăng độ khó PA ở phiên Mỹ
            self.require_pa = True

        volatility = macro_context.get("volatility_risk") or macro_context.get("volatility", "LOW")
        macro_bias = macro_context.get("bias") or macro_context.get("macro_bias", "NEUTRAL")

        if volatility == "HIGH":
            min_conf = self.min_confluence + 2
        elif volatility == "MEDIUM":
            min_conf = self.min_confluence + 1
        else:
            min_conf = self.min_confluence

        if l_score >= min_conf and in_killzone:
            if macro_bias != "BEARISH":  # CORE 2 CHẶN LỆNH BUY NẾU VĨ MÔ LÀ BEARISH
                # Structural SL (Mép dưới OB - 0.5 ATR)
                sl = float(l_btm - atr * 0.5)
                risk = entry - sl
                if risk <= 0:
                    risk = 0.0001

                action = "BUY"
                confidence = float(min(1.0, l_score / 6.0))
                rr = 2.0
                tp1 = float(entry + risk * rr)
                tp2 = float(entry + risk * (rr * 2.0))

        elif s_score >= min_conf and in_killzone:
            if macro_bias != "BULLISH":  # CORE 2 CHẶN LỆNH SELL NẾU VĨ MÔ LÀ BULLISH
                # Structural SL (Mép trên OB + 0.5 ATR)
                sl = float(s_top + atr * 0.5)
                risk = sl - entry
                if risk <= 0:
                    risk = 0.0001

                action = "SELL"
                confidence = float(min(1.0, s_score / 6.0))
                rr = 2.0
                tp1 = float(entry - risk * rr)
                tp2 = float(entry - risk * (rr * 2.0))

        # Construct dynamic self-describing checklist
        chk1_val = (
            "Bullish Structure Confirmed" if action == "BUY"
            else ("Bearish Structure Confirmed" if action == "SELL"
            else ("Bullish Bias Confirmed" if curr["bias"] > 0
            else ("Bearish Bias Confirmed" if curr["bias"] < 0
            else "Awaiting Clear Trend")))
        )
        chk1_status = (
            ChecklistStatus.PASSED if action in ("BUY", "SELL")
            else (ChecklistStatus.NEUTRAL if curr["bias"] != 0 else ChecklistStatus.PENDING)
        )

        chk2_val = (
            "Asian Low Swept & Absorbed" if action == "BUY"
            else ("Asian High Swept & Absorbed" if action == "SELL"
            else "Awaiting Asian Sweep")
        )
        chk2_status = ChecklistStatus.PASSED if action in ("BUY", "SELL") else ChecklistStatus.PENDING

        chk3_val = (
            "OB Retest + FVG Confluence" if action in ("BUY", "SELL")
            else "Awaiting Mitigation"
        )
        chk3_status = ChecklistStatus.PASSED if action in ("BUY", "SELL") else ChecklistStatus.PENDING

        checklist = [
            ChecklistItem(key="Trend Structure", value=chk1_val, status=chk1_status),
            ChecklistItem(key="Liquidity Sweep", value=chk2_val, status=chk2_status),
            ChecklistItem(key="Order Blocks & FVG", value=chk3_val, status=chk3_status),
        ]

        return StrategySignal(
            strategy_id=self.strategy_id,
            strategy_name=self.name,
            action=action,
            signal=action,
            entry_price=entry,
            sl=sl,
            tp1=tp1,
            tp2=tp2,
            confidence=confidence,
            score=float(max(l_score, s_score)),
            checklist=checklist,
            metadata={
                "strategy": "ICT_Zones_Pro",
                "active_fvgs": len(active_fvgs),
                "active_obs": len(active_obs),
                "bias": int(curr["bias"]),
                "checklist": [c.value for c in checklist],
            },
        )
