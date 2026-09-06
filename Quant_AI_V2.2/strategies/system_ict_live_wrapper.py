import pandas as pd
import numpy as np
from core.ict_strategy import ICTZonesProStrategy

def generate_signals(df):
    """
    Backtest ĐẦY ĐỦ LOGIC (Event-Driven) bằng Core Engine Live.
    
    Bao gồm toàn bộ 100% logic: 
    - Order Blocks (OB) với các tham số HPZ, quét thanh khoản (Liquidity Sweep)
    - Momentum Z-Score, Volume Percentile
    - Multi-Timeframe Analysis (MTFA) quét OB từ khung H1
    - Asian Range (Dải giá phiên Á)
    
    Để đảm bảo logic y hệt như lúc Bot chạy live, đoạn code này sẽ 
    giả lập đưa từng cây nến vào cỗ máy phân tích.
    
    Thời gian chạy ước tính: Khoảng 2 - 5 phút (tùy số lượng nến).
    """
    engine = ICTZonesProStrategy()
    signals = np.zeros(len(df))
    sls = np.zeros(len(df))
    tps = np.zeros(len(df))
    
    # --- TỐI ƯU HÓA SIÊU TỐC ---
    print("Đang tiền xử lý toàn bộ Ma trận Chỉ báo (ATR, Z-Score, Volume)...")
    df_calc = engine._calculate_indicators(df)
    engine._calculate_indicators = lambda x: x
    
    start_idx = 110
    print(f"Bắt đầu giả lập Live Trading cho {len(df) - start_idx} nến. Vui lòng đợi...")
    
    for i in range(start_idx, len(df)):
        current_window = df_calc.iloc[:i]
        res = engine.analyze(current_window, macro_context={})
        action = res.get('signal', 'HOLD')
        
        if action == 'BUY':
            signals[i] = 1
            sls[i] = res.get('sl', 0)
            tps[i] = res.get('tp1', 0)
        elif action == 'SELL':
            signals[i] = -1
            sls[i] = res.get('sl', 0)
            tps[i] = res.get('tp1', 0)
            
        if i % 500 == 0:
            print(f"Đã xử lý {i}/{len(df)} nến...")
            
    df['signal'] = signals
    df['sl'] = sls
    df['tp'] = tps
    
    print("Hoàn tất Backtest toàn bộ Logic!")
    return df
