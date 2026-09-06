# Khung Hệ Thống Phân Tích & Giao Dịch AI (Quant AI Terminal)

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-green)
![Architecture](https://img.shields.io/badge/Architecture-Hybrid%20AI-orange)

## 📌 Giới Thiệu
Đây là một hệ thống Giao dịch Định lượng (Quant Trading System) cấp độ tổ chức, được thiết kế với kiến trúc **Hybrid AI** độc đáo. Hệ thống không chỉ dựa vào các chỉ báo kỹ thuật thuần túy mà kết hợp sức mạnh của Mô hình Ngôn ngữ Lớn (LLM - Gemini 1.5 / Local Llama 3B) để đọc hiểu bối cảnh kinh tế vĩ mô, từ đó cấp phép cho các thuật toán kỹ thuật (ICT) hoạt động.

## 🏗 Kiến Trúc Hệ Thống (5 Lõi)

Hệ thống được chia thành 5 lõi (Cores) hoạt động độc lập và bất đồng bộ, đảm bảo tính ổn định và khả năng mở rộng cao:

1. **Core 1: Data Engine (MT5 & News API)**
   - Kết nối trực tiếp với MetaTrader 5 để lấy dữ liệu Tick/Bar theo thời gian thực (Zero-latency).
   - Tự động cào (scrape) lịch kinh tế từ ForexFactory và phân loại các sự kiện High-Impact.
2. **Core 2: Macro Brain (Trí Tuệ Vĩ Mô AI)**
   - Sử dụng **Gemini 1.5** hoặc **Local Llama 3B** để phân tích bối cảnh vĩ mô (DXY, US10Y, VIX).
   - Tự động đánh giá các số liệu kinh tế (Ví dụ: ISM PMI, NFP) so với kỳ vọng (Forecast) để đưa ra "Thiên kiến" (Bias) dài hạn.
   - **Tính năng đặc biệt:** Hỗ trợ cơ chế *Semi-Auto Input* cho phép người dùng mớm dữ liệu Actual để vượt qua các tường lửa chống Bot (Cloudflare).
3. **Core 3: Technical Strategy (Chiến lược Kỹ thuật - ICT)**
   - Triển khai thuật toán **ICT (Inner Circle Trader)** để dò tìm các vùng thanh khoản (Liquidity Voids, FVG, Order Blocks).
   - Core 3 chỉ được phép kích hoạt lệnh khi hướng giao dịch đồng thuận với Bias Vĩ mô từ Core 2.
4. **Core 4: Risk Manager (Quản trị Rủi ro Tự động)**
   - Tính toán khối lượng vào lệnh (Position Sizing) động dựa trên ATR và phần trăm rủi ro tài khoản.
   - Kiểm soát Drawdown tối đa trong ngày (Max Daily Drawdown) và chặn đứng hệ thống nếu chạm ngưỡng rủi ro.
5. **Core 5: Execution Manager (Thực thi Lệnh)**
   - Giao tiếp với MT5 để đẩy lệnh (Market/Limit) với mức trượt giá (Slippage) được kiểm soát nghiêm ngặt.
   - Quản lý vòng đời của lệnh, tự động dời Stoploss (Trailing) dựa trên cấu trúc giá.

## 🚀 Điểm Nhấn Công Nghệ (Dành cho báo cáo/Demo)
- **Kiến trúc Bất đồng bộ (Threading & Watchdogs):** Giao diện UI (Streamlit) và Lõi phân tích (Backend) chạy trên 2 luồng độc lập. UI không bao giờ bị đơ (freeze) kể cả khi AI đang tốn thời gian phân tích suy luận.
- **Dự phòng AI (LLM Fallback):** Hệ thống có khả năng chuyển đổi mượt mà giữa Cloud AI (Gemini) và Offline AI (Llama 3B chạy cục bộ) để đảm bảo quyền riêng tư dữ liệu và tính liên tục.
- **Giao diện Dashboard Tối giản & Thông minh:** Bảng điều khiển Streamlit được tinh chỉnh CSS cấp thấp, mang lại trải nghiệm chuyên nghiệp (Quant Terminal) và tự động dọn dẹp các trường nhập liệu thừa thãi.
