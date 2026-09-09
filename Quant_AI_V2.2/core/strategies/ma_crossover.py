import pandas as pd
import numpy as np

def generate_signals(df):
    """
    Chiến lược Cắt chéo 2 đường Trung bình động (Moving Average Crossover)
    - Mua (1): Đường MA Ngắn hạn (Fast) cắt lên MA Dài hạn (Slow).
    - Bán (-1): Đường MA Ngắn hạn cắt xuống MA Dài hạn.
    - Đứng ngoài (0): Không có tín hiệu.
    """
    # Khởi tạo cột tín hiệu ban đầu bằng 0
    df['signal'] = 0
    
    # Thông số chiến lược (Bạn có thể tinh chỉnh)
    fast_period = 10
    slow_period = 20
    
    # Đảm bảo có đủ dữ liệu để tính toán
    if len(df) < slow_period:
        return df
        
    # Tính toán các đường MA (Simple Moving Average)
    df['MA_Fast'] = df['close'].rolling(window=fast_period).mean()
    df['MA_Slow'] = df['close'].rolling(window=slow_period).mean()
    
    # Logic Cắt chéo (Crossover Logic)
    # df['MA_Fast'] > df['MA_Slow'] trả về True/False.
    # .astype(int) chuyển True->1, False->0
    # .diff() tính sự chênh lệch so với nến trước đó để tìm ra ĐIỂM CẮT.
    crossover = (df['MA_Fast'] > df['MA_Slow']).astype(int).diff()
    
    # Ghi nhận tín hiệu
    # diff() == 1: Mới chuyển từ False sang True -> Cắt lên -> BUY
    df.loc[crossover == 1, 'signal'] = 1
    
    # diff() == -1: Mới chuyển từ True sang False -> Cắt xuống -> SELL
    df.loc[crossover == -1, 'signal'] = -1
    
    return df
