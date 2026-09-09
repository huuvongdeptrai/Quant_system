import pandas as pd
import numpy as np

def generate_signals(df):
    """
    Chiến lược ICT (Smart Money Concept) - Phiên bản Backtest
    Dựa trên 2 khái niệm cốt lõi:
    1. Fair Value Gap (FVG)
    2. Phá vỡ cấu trúc (Market Structure Shift - MSS)
    """
    df['signal'] = 0
    
    if len(df) < 20:
        return df
        
    # 1. Tìm Fair Value Gap (FVG)
    # FVG Bullish: Low(i) > High(i-2)
    # FVG Bearish: High(i) < Low(i-2)
    df['fvg_bull'] = (df['low'] > df['high'].shift(2)) & (df['close'].shift(1) > df['open'].shift(1))
    df['fvg_bear'] = (df['high'] < df['low'].shift(2)) & (df['close'].shift(1) < df['open'].shift(1))
    
    # 2. Market Structure Shift (MSS - Phá vỡ cấu trúc)
    # Xác định đỉnh/đáy ngắn hạn (Fractal)
    df['fractal_high'] = (df['high'] > df['high'].shift(1)) & (df['high'] > df['high'].shift(-1))
    df['fractal_low'] = (df['low'] < df['low'].shift(1)) & (df['low'] < df['low'].shift(-1))
    
    # Kéo dài mức giá của đỉnh/đáy gần nhất (Điểm xoay cấu trúc)
    df['last_high'] = df['high'].where(df['fractal_high']).ffill()
    df['last_low'] = df['low'].where(df['fractal_low']).ffill()
    
    # Đột phá cấu trúc
    # MSS Bullish: Giá đóng cửa vượt qua đỉnh gần nhất
    df['mss_bull'] = df['close'] > df['last_high'].shift(1)
    
    # MSS Bearish: Giá đóng cửa phá xuống đáy gần nhất
    df['mss_bear'] = df['close'] < df['last_low'].shift(1)
    
    # 3. Kết hợp Logic (Signal)
    # BUY: Đã có MSS Bullish gần đây VÀ giá thoái lui về chạm FVG Bullish
    for i in range(3, len(df)):
        # Kiểm tra xem có FVG trước đó không
        recent_fvg_bull = df['fvg_bull'].iloc[i-3:i].any()
        recent_mss_bull = df['mss_bull'].iloc[i-5:i].any()
        
        if recent_fvg_bull and recent_mss_bull:
            df.iloc[i, df.columns.get_loc('signal')] = 1
            
        recent_fvg_bear = df['fvg_bear'].iloc[i-3:i].any()
        recent_mss_bear = df['mss_bear'].iloc[i-5:i].any()
        
        if recent_fvg_bear and recent_mss_bear:
            df.iloc[i, df.columns.get_loc('signal')] = -1
            
    return df
