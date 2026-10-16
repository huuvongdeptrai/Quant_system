# 📈 THƯ MỤC CHIẾN LƯỢC ĐỊNH LƯỢNG (STRATEGIES)
**Hệ thống:** Quant AI V2.2  
**Đường dẫn:** `strategies/` (ngay tại thư mục gốc của dự án)

Toàn bộ các chiến lược giao dịch và kiểm thử (Backtest) đã được quy tụ về **duy nhất 1 thư mục này** để bạn dễ dàng quản lý, đọc code, chỉnh sửa và thêm chiến lược mới mà không cần tìm kiếm trong các thư mục con lồng nhau.

---

## 📂 Danh sách các file chiến lược hiện có

| Tên File | Tên Chiến Lược | Mô Tả Thuật Toán |
| :--- | :--- | :--- |
| **`ict_strategy.py`** | **ICT Zones Pro v4.2** | Quét thanh khoản phiên Á (Asian High/Low Sweep), bẫy giá Judas Swing, khối lệnh Order Block và vùng mất cân bằng FVG. |
| **`wyckoff_vectorized.py`** | **Wyckoff Momentum Pro** | Tính toán ma trận NumPy siêu tốc (xử lý 10.000 nến < 0.1s), dải biến động ATR Envelope và bùng nổ khối lượng Wyckoff. |
| **`ema_stress_test.py`** | **EMA Dual Cross** | Giao cắt đường EMA10 và EMA50, dùng làm chuẩn đo lường và kiểm thử khả năng chịu tải (Stress Test) của hệ thống. |
| **`custom_ict_fvg.py`** | **Custom ICT FVG Sniper** | File mẫu chiến lược FVG đơn giản để bạn tham khảo hoặc sao chép khi tự viết chiến lược mới. |
| **`strategy_loader.py`** | **Bộ nạp chiến lược tự động** | Tự động quét toàn bộ file `.py` trong thư mục này và nạp lên giao diện Backtest. |

---

## 🚀 Cách tạo thêm chiến lược mới của bạn

Bạn chỉ cần tạo một file Python mới (ví dụ `my_rsi_strategy.py`) và đặt trực tiếp vào thư mục `strategies/` này.

Mẫu code tối giản chuẩn hệ thống:
```python
# -*- coding: utf-8 -*-
import pandas as pd

class MyRSIStrategy:
    def __init__(self, config=None):
        self.config = config or {}
        self.name = "My RSI Strategy"

    def analyze(self, df: pd.DataFrame, macro_context=None):
        """
        Nhận vào: DataFrame dữ liệu nến OHLCV
        Trả về: Dict tín hiệu gồm BUY, SELL hoặc HOLD
        """
        if df is None or len(df) < 30:
            return {"strategy": self.name, "signal": "HOLD", "confidence": 0.0}

        close = df["close"].iloc[-1]
        
        # Viết logic tính toán của bạn ở đây...
        
        return {
            "strategy": self.name,
            "signal": "BUY",        # hoặc "SELL", "HOLD"
            "entry_price": float(close),
            "confidence": 0.85,
            "sl_price": float(close * 0.99),
            "tp_price": float(close * 1.02)
        }
```

> **Lưu ý:** Khi bạn lưu file xong, hệ thống sẽ **tự động quét và hiển thị** chiến lược của bạn trong menu thả xuống **Strategy** ở Tab Backtest!
