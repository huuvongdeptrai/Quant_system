# PHIÊN BẢN CHALLENGER - Áp dụng 5 bản vá cải tiến - Dùng để backtest so sánh
import pandas as pd
import numpy as np
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from system.interfaces import IStrategy

class FVG:
    def __init__(self, top: float, btm: float, is_bull: bool, start_idx: int):
        self.top = top
        self.btm = btm
        self.is_bull = is_bull
        self.start_idx = start_idx
        self.is_mitigated = False

class OrderBlock:
    def __init__(self, top: float, btm: float, is_bull: bool, base_score: float, start_idx: int):
        self.top = top
        self.btm = btm
        self.is_bull = is_bull
        self.base_score = base_score
        self.start_idx = start_idx
        self.max_disp = 0.0
        self.touch_count = 0
        self.is_mitigated = False
        
    def current_score(self) -> float:
        disp_score = min(30.0, self.max_disp * 10.0)
        return min(100.0, self.base_score + disp_score)
        
    def is_hpz(self, threshold: float = 80.0) -> bool:
        return self.current_score() >= threshold

class ICTZonesProStrategyV2(IStrategy):
    """
    Chiến lược giao dịch ICT Trading Zones Pro
    
    Đầu vào:
    - config: Giá trị dict, cấu hình tham số chiến lược.

    Đầu ra:
    - Giá trị None, khởi tạo đối tượng chiến lược.
    """
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.ob_length = self.config.get("ob_length", 5)
        self.hpz_threshold = self.config.get("hpz_threshold", 80.0)
        self.momentum_period = self.config.get("momentum_period", 50)
        self.fvg_threshold_per = self.config.get("fvg_threshold_per", 0.1)
        self.min_confluence = self.config.get("min_confluence", 1)
        self.require_pa = self.config.get("require_pa", True)
        self.lookback_bars = self.config.get("lookback_bars", 300) # Khôi phục trạng thái từ 300 nến
        self.sweep_len = self.config.get("sweep_len", 20)
        self.sweep_memory = self.config.get("sweep_memory", 10)
        
    def get_min_confluence(self, macro_context: dict) -> int:
        """Ngưỡng Confluence động theo mức rủi ro vĩ mô."""
        vol = macro_context.get('volatility_risk', 'LOW')
        if vol == 'HIGH':
            return 4
        elif vol == 'MEDIUM':
            return 3
        return 2

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # Chỉ báo ATR 14
        df['prev_close'] = df['close'].shift(1)
        df['tr'] = np.maximum(df['high'] - df['low'], 
                   np.maximum(abs(df['high'] - df['prev_close']), abs(df['low'] - df['prev_close'])))
        df['atr'] = df['tr'].rolling(window=14).mean()
        
        # Momentum Z-Score
        df['price_change'] = df['close'].diff()
        df['avg_change'] = df['price_change'].rolling(self.momentum_period).mean()
        df['std_change'] = df['price_change'].rolling(self.momentum_period).std()
        df['momentum_z'] = np.where(df['std_change'] != 0, (df['price_change'] - df['avg_change']) / df['std_change'], 0)
        
        # Xếp hạng phần trăm Volume
        def rolling_pct_rank(x):
            return pd.Series(x).rank(pct=True).iloc[-1] * 100 if len(x) > 0 else 0
            
        df['vol_pct_rank'] = df['volume'].rolling(100).apply(rolling_pct_rank, raw=True)
        
        # Xu hướng SMA
        df['sma20'] = df['close'].rolling(20).mean()
        df['sma50'] = df['close'].rolling(50).mean()
        df['bias'] = np.where(df['sma20'] > df['sma50'], 1, np.where(df['sma20'] < df['sma50'], -1, 0))
        
        # Quét đỉnh đáy
        df['prev_sw_high'] = df['high'].rolling(self.sweep_len).max().shift(1)
        df['prev_sw_low'] = df['low'].rolling(self.sweep_len).min().shift(1)
        
        return df

    def analyze(self, df: pd.DataFrame, macro_context: Dict[str, Any]) -> Dict[str, Any]:
        if len(df) < max(self.momentum_period, 100) + 10:
            return {"action": "HOLD", "confidence": 0}
            
        df = self._calculate_indicators(df)
        
        active_fvgs: List[FVG] = []
        ifvg_boxes: List[FVG] = []
        active_obs: List[OrderBlock] = []
        
        last_bull_sweep_idx = -999
        last_bear_sweep_idx = -999
        
        os_state = 0  
        start_idx = max(0, len(df) - self.lookback_bars)
        
        for i in range(start_idx, len(df)):
            if i < self.ob_length + 2:
                continue
                
            row = df.iloc[i]
            prev_row = df.iloc[i-1]
            prev2_row = df.iloc[i-2]
            
            # 1. Phát hiện quét thanh khoản
            if row['low'] < row['prev_sw_low'] and row['close'] > row['prev_sw_low']:
                last_bull_sweep_idx = i
            if row['high'] > row['prev_sw_high'] and row['close'] < row['prev_sw_high']:
                last_bear_sweep_idx = i
                
            # 2. Phát hiện vùng FVG
            thresh = self.fvg_threshold_per / 100
            
            is_bull_fvg = (row['low'] > prev2_row['high']) and (prev_row['close'] > prev2_row['high']) and \
                          ((row['low'] - prev2_row['high']) / prev2_row['high'] > thresh)
                          
            is_bear_fvg = (row['high'] < prev2_row['low']) and (prev_row['close'] < prev2_row['low']) and \
                          ((prev2_row['low'] - row['high']) / row['high'] > thresh)
                          
            if is_bull_fvg:
                active_fvgs.insert(0, FVG(top=row['low'], btm=prev2_row['high'], is_bull=True, start_idx=i-2))
            if is_bear_fvg:
                active_fvgs.insert(0, FVG(top=prev2_row['low'], btm=row['high'], is_bull=False, start_idx=i-2))
                
            # Cập nhật trạng thái FVG
            fvgs_to_keep = []
            for f in active_fvgs:
                is_broken = (row['low'] < f.btm) if f.is_bull else (row['high'] > f.top)
                if is_broken:
                    ifvg_boxes.insert(0, f)
                    if len(ifvg_boxes) > 5:
                        ifvg_boxes.pop()
                else:
                    fvgs_to_keep.append(f)
            active_fvgs = fvgs_to_keep[:50]
            
            # 3. Phát hiện Order Block
            high_oblen = df['high'].iloc[i-self.ob_length]
            low_oblen = df['low'].iloc[i-self.ob_length]
            upper = df['high'].iloc[i-self.ob_length+1:i+1].max() 
            lower = df['low'].iloc[i-self.ob_length+1:i+1].min()
            
            if high_oblen > upper:
                os_state = 0
            elif low_oblen < lower:
                os_state = 1
                
            # Đỉnh Volume
            vol_window = df['volume'].iloc[i-self.ob_length*2 : i+1].values
            if len(vol_window) == self.ob_length*2 + 1:
                mid_vol = vol_window[self.ob_length]
                is_phv = True
                for v in vol_window:
                    if v > mid_vol:
                        is_phv = False
                        break
                
                if is_phv:
                    mZ = df['momentum_z'].iloc[i-self.ob_length]
                    vP = df['vol_pct_rank'].iloc[i-self.ob_length]
                    base_score = min(70.0, abs(mZ) * 7.0 + vP * 0.35)
                    
                    if os_state == 1: # Bull Order Block
                        ob_top = df['open'].iloc[i-self.ob_length]
                        ob_btm = df['low'].iloc[i-self.ob_length]
                        active_obs.insert(0, OrderBlock(ob_top, ob_btm, True, base_score, i-self.ob_length))
                    elif os_state == 0: # Bear Order Block
                        ob_top = df['high'].iloc[i-self.ob_length]
                        ob_btm = df['open'].iloc[i-self.ob_length]
                        active_obs.insert(0, OrderBlock(ob_top, ob_btm, False, base_score, i-self.ob_length))
                        
            # Dọn dẹp và cập nhật Order Block
            obs_to_keep = []
            for ob in active_obs:
                if ob.is_bull:
                    mitigated = row['close'] < ob.btm
                    if not mitigated:
                        in_zone = row['low'] <= ob.top and row['close'] >= ob.btm
                        if in_zone and not (prev_row['low'] <= ob.top and prev_row['close'] >= ob.btm):
                            ob.touch_count += 1
                        
                        atr_val = row['atr'] if not pd.isna(row['atr']) and row['atr'] > 0 else 1.0
                        cur_disp = max(0.0, row['high'] - ob.top) / atr_val
                        ob.max_disp = max(ob.max_disp, cur_disp)
                        obs_to_keep.append(ob)
                else:
                    mitigated = row['close'] > ob.top
                    if not mitigated:
                        in_zone = row['high'] >= ob.btm and row['close'] <= ob.top
                        if in_zone and not (prev_row['high'] >= ob.btm and prev_row['close'] <= ob.top):
                            ob.touch_count += 1
                            
                        atr_val = row['atr'] if not pd.isna(row['atr']) and row['atr'] > 0 else 1.0
                        cur_disp = max(0.0, ob.btm - row['low']) / atr_val
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
        def check_pa(is_bull: bool) -> int:
            body = abs(curr['close'] - curr['open'])
            wTop = curr['high'] - max(curr['close'], curr['open'])
            wBtm = min(curr['close'], curr['open']) - curr['low']
            
            if is_bull:
                is_strong_pinbar = wBtm > body * 2.0 and wTop < body
                is_medium_pinbar = wBtm > body * 1.5 and wTop < body * 1.5
                is_engulf = (prev['close'] < prev['open']) and (curr['close'] > prev['open']) and (curr['open'] < prev['close'])
            else:
                is_strong_pinbar = wTop > body * 2.0 and wBtm < body
                is_medium_pinbar = wTop > body * 1.5 and wBtm < body * 1.5
                is_engulf = (prev['close'] > prev['open']) and (curr['close'] < prev['open']) and (curr['open'] > prev['close'])
                
            if is_strong_pinbar or is_engulf:
                return 2
            if is_medium_pinbar:
                return 1
            return 0

        def has_ifvg_overlap(zTop: float, zBtm: float) -> bool:
            for ifvg in ifvg_boxes:
                if zBtm <= ifvg.top and zTop >= ifvg.btm:
                    return True
            return False

        def calc_confluence(is_long: bool) -> Tuple[int, float, float]:
            score = 0
            in_fvg = False
            in_ob = False
            zTop = curr['close']
            zBtm = curr['close']
            price = curr['close']
            
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
                    if ob.btm <= price <= ob.top:
                        if ob.touch_count >= 3:
                            ob.is_mitigated = True
                            continue  # Bỏ qua hoàn toàn, không tính điểm
                        else:
                            ob_add = 2 if ob.is_hpz(self.hpz_threshold) else 1
                            score += (ob_add - 1) if ob.touch_count == 2 else ob_add
                            in_ob = True
                            zTop = max(zTop, ob.top)
                            zBtm = min(zBtm, ob.btm)
                        break
                        
            if not in_fvg and not in_ob:
                return 0, zTop, zBtm
                
            bias = curr['bias']
            if (is_long and bias == 1) or (not is_long and bias == -1):
                score += 1
                
            recent_bull_sweep = (last_idx - last_bull_sweep_idx) <= self.sweep_memory
            recent_bear_sweep = (last_idx - last_bear_sweep_idx) <= self.sweep_memory
            
            if (is_long and recent_bull_sweep) or (not is_long and recent_bear_sweep):
                score += 1
                
            if has_ifvg_overlap(zTop, zBtm):
                score -= 1  # Bị iFVG chặn
            else:
                score += 1  # Vùng sạch, không có iFVG
                
            # PA cộng điểm thay vì chặn cứng
            pa_result = check_pa(is_long)  # check_pa now returns int: 2=strong, 1=medium, 0=none
            score += pa_result
                
            return max(0, score), zTop, zBtm

        import json
        state_file = PROJECT_ROOT / "data" / "strategy_state.json"
        
        # Tải Order Block cũ
        prev_obs = []
        if state_file.exists():
            try:
                with open(state_file, "r") as f:
                    old_state = json.load(f)
                    prev_obs = old_state.get("active_obs", [])
            except:
                pass
                
        # Ghi nhận Order Block hiện tại
        serialized_obs = []
        for ob in active_obs:
            serialized_obs.append({
                "top": ob.top,
                "btm": ob.btm,
                "is_bull": ob.is_bull,
                "score": ob.current_score(),
                "start_idx": ob.start_idx
            })
            
        # Thông báo Order Block mới
        # [BACKTEST MODE] Telegram da tat
            
        # Lưu trạng thái mới
        try:
            with open(state_file, "w") as f:
                json.dump({"strategy": "ICT_v2_Challenger", "active_obs": serialized_obs}, f, indent=4)
        except:
            pass
            
        l_score, l_top, l_btm = calc_confluence(is_long=True)
        s_score, s_top, s_btm = calc_confluence(is_long=False)
        
        action = "HOLD"
        confidence = 0.0
        entry = curr['close']
        sl = None
        tp1 = None
        tp2 = None
        
        atr = curr['atr'] if not pd.isna(curr['atr']) else (curr['high'] - curr['low'])
        
        min_confluence = self.get_min_confluence(macro_context)
        
        if l_score >= min_confluence:
            action = "BUY"
            confidence = min(1.0, l_score / 6.0)
            sl = l_btm - atr * 0.2
            risk = entry - sl
            if risk <= 0:
                risk = 0.0001
            tp1 = entry + risk * 1.0
            tp2 = entry + risk * 2.0
            
        elif s_score >= min_confluence:
            action = "SELL"
            confidence = min(1.0, s_score / 6.0)
            sl = s_top + atr * 0.2
            risk = sl - entry
            if risk <= 0:
                risk = 0.0001
            tp1 = entry - risk * 1.0
            tp2 = entry - risk * 2.0

        return {
            "strategy": "ICT_v2_Challenger",
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
                "bias": curr['bias']
            }
        }
