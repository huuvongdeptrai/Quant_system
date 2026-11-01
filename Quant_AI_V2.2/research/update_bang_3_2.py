import sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'Kho_Do_An/Quant_AI_V2.2/docs/thesis/chuong_3_thiet_ke_he_thong.md', 'r', encoding='utf-8') as f:
    content = f.read()

target = """| **Kết nối Broker & Thực thi**| MetaTrader 5 Python API [14] | 5.0.45 | Cầu nối IPC nhận dữ liệu tick/nến và truyền lệnh giao dịch |
| **Bộ lọc Học máy AI** | LightGBM [12] | 4.3.0 | Mô hình phân loại nhị phân xác thực tín hiệu Meta-Labeling |
| **Mô hình Ngôn ngữ Lớn** | Ollama Engine [26] & Qwen 2.5 [16] | 7B-Instruct (Q4) | Phân tích bất đồng bộ tin tức qua JSON mode kết hợp kiểm thực schema nghiệp vụ trong Python [26] |
| **Khung Giao diện Người dùng**| PySide6 (Qt for Python) [11] | 6.7.2 | Điều phối cửa sổ, bảng điều khiển, Signal/Slot luồng |
| **Đồ họa Đồ thị Thời gian thực**| PyQtGraph | 0.13.7 | Kết xuất biểu đồ nến vi sai và vùng thanh khoản động |
| **Cơ sở dữ liệu Trạng thái** | SQLite Engine [13] | Chế độ WAL | Lưu trữ nhật ký lệnh, bền vững trạng thái và phục hồi lỗi |
| **Truy xuất Dữ liệu Vĩ mô** | FRED API [24], [25], [27], Cboe VIX [22], ICE DX Futures [23], MT5 Broker Feed, Requests | REST / MT5 Feed | Nạp US10Y (DGS10 [25], DFII10 [24]), biến động VIX (VIXCLS [27], Cboe [22]), CFD proxy Dollar Index (chuẩn tham chiếu ICE DX [23]) và lịch kinh tế với bộ đệm phân cấp TTL 900s - 3600s |"""

replacement = """| **Kết nối Broker & Thực thi**| MetaTrader 5 Python API [14] | 5.0.5735 | Cầu nối IPC nhận dữ liệu tick/nến và truyền lệnh tới Terminal Build 4410 |
| **Bộ lọc Học máy AI** | LightGBM [12] | 4.5.0 | Mô hình phân loại nhị phân xác thực tín hiệu Meta-Labeling (tương thích $\\ge 4.3.0$) |
| **Máy chủ LLM Cục bộ** | Ollama Engine [26] | 0.3.14 (dải $\\ge 0.3.0$) | Quản lý tiến trình suy luận LLM ngoại tuyến qua REST API tại `localhost:11434` |
| **Mô hình Ngôn ngữ Lớn** | Qwen 2.5 [16] | 7B-Instruct (Q4_K_M) | Bóc tách sắc thái tin tức vĩ mô theo lược đồ JSON Schema có cấu trúc |
| **Khung Giao diện Người dùng**| PySide6 (Qt for Python) [11] | 6.7.2 | Điều phối cửa sổ, bảng điều khiển, Signal/Slot luồng |
| **Đồ họa Đồ thị Thời gian thực**| PyQtGraph | 0.13.7 | Kết xuất biểu đồ nến vi sai và vùng thanh khoản động |
| **Cơ sở dữ liệu Trạng thái** | SQLite Engine [13] | 3.45.3 | Lưu trữ nhật ký lệnh, bền vững trạng thái (cấu hình `WAL`, `synchronous=NORMAL`) |
| **Truy xuất Dữ liệu Vĩ mô** | FRED API [24], [25], Yahoo Finance API, TradingView API, MT5 Feed | REST / yfinance / MT5 | Nạp US10Y (DGS10 [25], DFII10 [24]), biến động VIX (`^VIX`), Dollar Index (`DX-Y.NYB`) và lịch kinh tế |"""

content_norm = content.replace('\r\n', '\n')
target_norm = target.replace('\r\n', '\n')
replacement_norm = replacement.replace('\r\n', '\n')

if target_norm in content_norm:
    new_content = content_norm.replace(target_norm, replacement_norm)
    with open(r'Kho_Do_An/Quant_AI_V2.2/docs/thesis/chuong_3_thiet_ke_he_thong.md', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Replaced Bang 3.2 in chuong_3_thiet_ke_he_thong.md successfully!")
else:
    print("Target not found in content!")
