import pandas as pd
import numpy as np
import pytz
from datetime import datetime

class DataPreprocessor:
    def __init__(self):
        pass

    def process_technical_data(self, rates_data, broker_timezone="Europe/Kyiv"):
        # 1. Chuyển đổi Data thô sang DataFrame (Kế thừa V1)
        df = pd.DataFrame(rates_data)
        if len(df) < 50:
            return None
            
        df['close'] = df['close'].astype(float)
        
        # CHUẨN HOÁ MÚI GIỜ (KẾ THỪA V1)
        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'], unit='s')
            try:
                # Đưa về múi giờ Broker rồi ép sang UTC chuẩn Quốc tế
                broker_tz = pytz.timezone(broker_timezone)
                df['time'] = df['time'].dt.tz_localize(broker_tz).dt.tz_convert(pytz.UTC)
                current_time_utc = df.iloc[-1]['time'].strftime('%Y-%m-%d %H:%M:%S UTC')
            except Exception:
                current_time_utc = "Không xác định"
        else:
            current_time_utc = "Không xác định"
            
        if 'tick_volume' in df.columns:
            df.rename(columns={'tick_volume': 'volume'}, inplace=True)
        
        # 2. Làm sạch dữ liệu (Xử lý NaN)
        df.ffill(inplace=True)
        
        # 3. Trích xuất đặc trưng (Feature Extraction)
        df['EMA20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['EMA50'] = df['close'].ewm(span=50, adjust=False).mean()
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # 4. Gắn nhãn dữ liệu (Categorical Labeling) - Tối ưu cho AI
        current = df.iloc[-1]
        
        # Nhãn RSI
        rsi = current['RSI']
        if rsi > 70:
            rsi_label = "QUÁ MUA (Khả năng đảo chiều giảm)"
        elif rsi < 30:
            rsi_label = "QUÁ BÁN (Khả năng bật tăng)"
        else:
            rsi_label = "TRUNG TÍNH"
            
        # Nhãn Trend
        trend_label = "TĂNG (Uptrend)" if current['EMA20'] > current['EMA50'] else "GIẢM (Downtrend)"
        
        # Phân tích Cấu trúc thị trường (Market Structure) 50 nến
        recent_50 = df.tail(50)
        resistance = recent_50['high'].max()
        support = recent_50['low'].min()
        
        # Tính toán Độ biến động (Volatility - Biên độ nến)
        recent_10 = df.tail(10)
        volatility = recent_10['high'].max() - recent_10['low'].min()
        
        return {
            'current_time_utc': current_time_utc,
            'current_price': current['close'],
            'rsi_value': round(rsi, 1),
            'rsi_label': rsi_label,
            'trend': trend_label,
            'resistance': resistance,
            'support': support,
            'volatility': round(volatility, 4)
        }