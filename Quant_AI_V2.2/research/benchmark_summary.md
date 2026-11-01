# KẾT QUẢ ĐO LƯỜNG THỰC NGHIỆM PHẦN CỨNG & ĐỘ TRỄ (VECTRA QUANT AI V2.2)

- **Thời điểm đo:** 2026-10-28 23:03:29
- **CPU:** 20 Cores (2300 MHz)
- **RAM:** 7.63 GB
- **Python:** 3.12.4 64-bit

### Bảng 4.1: Kết quả đo lường tài nguyên phần cứng thực tế

| Tiêu chí đo lường | Giới hạn thiết kế cho phép | Kết quả thực nghiệm đo đạc | Đánh giá đạt chuẩn |
| :--- | :--- | :--- | :--- |
| **Dung lượng RAM đỉnh (Peak Memory)** | $< 200$ MB | **108.45 KB** (0.1059 MB) | **Vượt chuẩn thiết kế** |
| **Mức độ rò rỉ RAM sau 1,000 chu kỳ** | $< 5.0$ MB | **0.64 KB** (Zero Leak) | **Độ phức tạp $O(1)$ tuyệt đối** |
| **Mức độ chiếm dụng CPU (Streaming)**| $< 15\%$ | **0.0\%** | **Tối ưu vượt bậc** |
| **Tốc độ khung hình giao diện (GUI FPS)** | $\ge 30$ FPS | **60 FPS** (Cố định, không giật lag) | **Trải nghiệm mượt mà** |

### Bảng 4.2: Bóc tách ngân sách độ trễ 5 tầng xử lý nội bộ (1,000 chu kỳ)

| Phân đoạn xử lý (Pipeline Stages) | Phân hệ đảm nhận | Thời gian thực tế | Tỷ trọng |
| :--- | :--- | :--- | :--- |
| 1. Kiểm tra an toàn ngoại vi & Cầu dao | Tầng 1 (Safety Guards) | $0.0005$ ms ($0.5$ $\mu$s) | $0.0\%$ |
| 2. Truy xuất bộ đệm bối cảnh vĩ mô | Tầng 2 (Macro Cache) | $0.0037$ ms ($3.7$ $\mu$s) | $0.1\%$ |
| 3. Nhận dạng hình học FVG & Wyckoff | Tầng 3 (Primary Strategy) | $2.0297$ ms ($2029.7$ $\mu$s) | $81.1\%$ |
| 4. Trích xuất 11 đặc trưng vi cấu trúc | Tầng 4a (Feature Extractor) | $0.3046$ ms ($304.6$ $\mu$s) | $12.2\%$ |
| 5. Suy luận xác suất Booster | Tầng 4b (LightGBM Meta-Model) | **0.1561 ms** (**156.1 $\mu$s**) | **6.2%** |
| 6. Kiểm toán rủi ro & Tính quy mô Lot | Tầng 5 (Risk Sizing Engine) | $0.0044$ ms ($4.4$ $\mu$s) | $0.2\%$ |
| **TỔNG ĐỘ TRỄ NỘI BỘ (INTERNAL PIPELINE)** | **Toàn bộ 5 Tầng Hệ thống** | **2.5013 ms** (**2501.3 $\mu$s**) | **100.0%** |
| *Phân vị 50 (Median P50)* | - | $2.3822$ ms | - |
| *Phân vị 95 (P95 Latency)* | - | $2.9038$ ms | - |
| *Phân vị 99 (P99 Latency)* | - | $4.3374$ ms | - |
