# BÁO CÁO KIỂM TOÁN VI CẤU TRÚC KHỚP LỆNH THỰC TẾ (FILLED DEALS AUDIT)
**Đồ án Tốt nghiệp:** Hệ thống Giao dịch Định lượng Quant AI V2.2 (VECTRA)  
**Thời gian kiểm toán:** 2026-10-26 21:26:57  
**Môi trường:** MetaTrader 5 Build 4000+ kết nối `EGlobalTrade-Demo` (Login `316070`)  

---

## 1. Kết quả Đo lường Độ trễ Xác thực Lệnh (20 Chu kỳ order_check)
- **Độ trễ trung bình:** **0.10 ms**
- **Độ trễ phân vị 95 (P95):** **0.17 ms**
- **Độ trễ lớn nhất:** **0.74 ms**
- **Đánh giá:** Nhanh hơn chuẩn định chế (< 500 ms) **4851.1 lần**.

---

## 2. Bảng Đối soát Độ trượt giá Thực tế của 100% Lệnh ĐÃ KHỚP (Filled Deals)
*Ghi chú học thuật: Theo nguyên lý Vi cấu trúc thị trường, trượt giá (Slippage) chỉ tồn tại khi lệnh được thực thi khớp lệnh ($P_{filled} - P_{requested}$). Các lệnh chờ bị hủy không phát sinh giao dịch tiền tệ nên không có trượt giá.*

| Deal Ticket | Order Ticket | Thời gian khớp (UTC) | Hướng lệnh | Khối lượng | Giá yêu cầu | Giá khớp thực | Độ trượt giá (Points) | Lãi/Lỗ ghi nhận | Nguồn phát lệnh |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `203173408` | `283087717` | 2026-10-19 14:53:09 | **BUY** | 0.28 lot | 4184.020 | 4184.093 | **7.3** | $0.00 | `FULL_AUTO_XAUUSD` |
| `203802763` | `283797557` | 2026-10-20 14:19:30 | **BUY** | 2.0 lot | 4135.800 | 4135.822 | **2.2** | $0.00 | `VECTRA_Manual` |
| `204625903` | `284779386` | 2026-10-21 22:00:31 | **BUY** | 0.05 lot | 4133.500 | 4133.595 | **9.5** | $21.45 | `Quant_Close_Single` |
| `204718207` | `284886853` | 2026-10-22 00:33:06 | **SELL** | 3.3 lot | 4139.644 | 4139.644 | **0.0** | $0.00 | `VECTRA_ChartOrder` |
| `204723683` | `284893490` | 2026-10-22 00:44:59 | **BUY** | 3.3 lot | 4131.380 | 4131.391 | **1.1** | $2,723.49 | `Quant_Close_Single` |
| `205309018` | `285611718` | 2026-10-22 22:00:01 | **BUY** | 0.62 lot | 4086.730 | 4086.745 | **1.5** | $0.00 | `FULL_AUTO_XAUUSD` |

- **Tỷ lệ thực thi lệnh thị trường (Fill Rate):** **100.0%** (Tất cả 6 vị thế đều được khớp trọn vẹn).
- **Độ trượt giá trung bình (Average Slippage):** **3.60 points** (tương đương $0.0360 USD).
- **Độ trượt giá cực đại (Max Slippage):** **9.5 points** (Tuyệt đối tuân thủ chuẩn $< 10.0$ points).
