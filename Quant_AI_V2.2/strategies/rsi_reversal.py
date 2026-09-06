import pandas as pd
import numpy as np

def generate_signals(df):
    """
    Chiến lược Bắt Đảo chiều với Chỉ báo RSI (RSI Reversal)
    - Mua (1): RSI rơi xuống vùng Quá Bán (Oversold < 30) và bắt đầu ngóc đầu lên.
    - Bán (-1): RSI vượt lên vùng Quá Mua (Overbought > 70) và bắt đầu cắm đầu xuống.
    """
    df['signal'] = 0
    
    rsi_period = 14
    oversold = 30
    overbought = 70
    
    if len(df) <= rsi_period:
        return df
        
    # Tính toán RSI thủ công bằng Pandas
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)
    
    avg_gain = gain.rolling(window=rsi_period, min_periods=rsi_period).mean()
    avg_loss = loss.rolling(window=rsi_period, min_periods=rsi_period).mean()
    
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Logic Tín hiệu Đảo chiều
    for i in range(1, len(df)):
        rsi_current = df['RSI'].iloc[i]
        rsi_prev = df['RSI'].iloc[i-1]
        
        # Nếu RSI hôm qua < 30 (quá bán) và RSI hôm nay lớn hơn RSI hôm qua -> Có dấu hiệu hồi phục -> MUA
        if rsi_prev < oversold and rsi_current > rsi_prev:
            df.iloc[i, df.columns.get_loc('signal')] = 1
            
        # Nếu RSI hôm qua > 70 (quá mua) và RSI hôm nay nhỏ hơn RSI hôm qua -> Có dấu hiệu suy yếu -> BÁN
        elif rsi_prev > overbought and rsi_current < rsi_prev:
            df.iloc[i, df.columns.get_loc('signal')] = -1
            
    return df
