import pandas as pd
import numpy as np

def generate_signals(df):
    """
    Chiến lược ICT (Smart Money Concept) - Phiên bản Backtest
    
    Đây là phiên bản Vectorized tốc độ cao của lõi ICT, chuyên biệt cho Backtest.
    Hệ thống sẽ quét hàng nghìn nến trong chưa tới 1 giây.
    
    Logic cốt lõi:
    1. Tìm Fair Value Gap (FVG)
    2. Xác định cấu trúc thị trường (Market Structure Shift - MSS)
    3. Phát tín hiệu khi giá thoái lui về FVG hợp lệ.
    """
    df['signal'] = 0
    if len(df) < 50:
        return df
        
    df = df.copy()
    
    # 1. TÌM FVG (Fair Value Gap)
    # FVG Bullish: Low nến 3 > High nến 1 VÀ Nến 2 tăng mạnh
    # FVG Bearish: High nến 3 < Low nến 1 VÀ Nến 2 giảm mạnh
    df['fvg_bull'] = (df['low'] > df['high'].shift(2)) & (df['close'].shift(1) > df['open'].shift(1))
    df['fvg_bear'] = (df['high'] < df['low'].shift(2)) & (df['close'].shift(1) < df['open'].shift(1))
    
    # 2. XÁC ĐỊNH ĐỈNH ĐÁY VÀ CẤU TRÚC THỊ TRƯỜNG (MSS)
    # Fractal 5 nến
    df['fractal_high'] = (df['high'] > df['high'].shift(1)) & (df['high'] > df['high'].shift(-1)) & (df['high'] > df['high'].shift(2)) & (df['high'] > df['high'].shift(-2))
    df['fractal_low'] = (df['low'] < df['low'].shift(1)) & (df['low'] < df['low'].shift(-1)) & (df['low'] < df['low'].shift(2)) & (df['low'] < df['low'].shift(-2))
    
    df['last_swing_high'] = df['high'].where(df['fractal_high']).ffill()
    df['last_swing_low'] = df['low'].where(df['fractal_low']).ffill()
    
    # Xác nhận phá vỡ cấu trúc (MSS)
    df['mss_bull'] = (df['close'] > df['last_swing_high'].shift(1)) & (df['close'].shift(1) <= df['last_swing_high'].shift(2))
    df['mss_bear'] = (df['close'] < df['last_swing_low'].shift(1)) & (df['close'].shift(1) >= df['last_swing_low'].shift(2))
    
    # 3. KẾT HỢP FVG VÀ MSS ĐỂ TẠO TÍN HIỆU
    # Quét theo mảng numpy để tối đa hóa tốc độ
    signals = np.zeros(len(df))
    fvg_bull_arr = df['fvg_bull'].values
    fvg_bear_arr = df['fvg_bear'].values
    mss_bull_arr = df['mss_bull'].values
    mss_bear_arr = df['mss_bear'].values
    
    lows = df['low'].values
    highs = df['high'].values
    
    # Giới hạn tìm kiếm FVG trong 20 nến gần nhất
    lookback = 20
    
    for i in range(lookback, len(df)):
        # Kiểm tra BUY Setup
        if mss_bull_arr[i-1] or mss_bull_arr[i-2] or mss_bull_arr[i-3]:
            # Nếu có phá vỡ cấu trúc tăng gần đây, tìm FVG tăng ở dưới giá hiện tại
            recent_fvgs = np.where(fvg_bull_arr[i-lookback:i])[0]
            if len(recent_fvgs) > 0:
                # Nếu giá thoái lui chạm vào cây nến có FVG
                fvg_idx = (i - lookback) + recent_fvgs[-1]
                fvg_top = highs[fvg_idx]  # Cạnh trên của FVG (High của nến 1)
                
                if lows[i] <= fvg_top:
                    signals[i] = 1  # Bắt lệnh BUY
                    
        # Kiểm tra SELL Setup
        if mss_bear_arr[i-1] or mss_bear_arr[i-2] or mss_bear_arr[i-3]:
            # Nếu có phá vỡ cấu trúc giảm gần đây, tìm FVG giảm ở trên giá hiện tại
            recent_fvgs = np.where(fvg_bear_arr[i-lookback:i])[0]
            if len(recent_fvgs) > 0:
                fvg_idx = (i - lookback) + recent_fvgs[-1]
                fvg_bottom = lows[fvg_idx]  # Cạnh dưới của FVG (Low của nến 1)
                
                if highs[i] >= fvg_bottom:
                    signals[i] = -1 # Bắt lệnh SELL
                    
    df['signal'] = signals
    return df
