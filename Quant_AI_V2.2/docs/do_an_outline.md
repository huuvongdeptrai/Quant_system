TÓM TẮT ĐỒ ÁN 

Tóm tắt tiếng Việt: Nghiên cứu này trình bày quá trình xây dựng hệ thống giao dịch tự động tích hợp trí tuệ nhân tạo. Quá trình phát triển tập trung vào việc áp dụng phương pháp Smart Money Concepts (SMC) cùng với khả năng xử lý ngôn ngữ tự nhiên từ mô hình Qwen 2.5 chạy cục bộ. Hệ thống kết nối với MetaTrader 5 để lấy dữ liệu giá, nhận diện cấu trúc thị trường và phân tích tin tức kinh tế nhằm đưa ra quyết định giao dịch. Ngoài ra, phần mềm bao gồm cơ chế quản lý rủi ro tự động, thiết kế đa luồng để giữ độ trễ thấp và tích hợp môi trường giả lập Backtest hỗ trợ kiểm thử chiến lược trên dữ liệu lịch sử.

English Abstract: This study presents the development of an automated trading system integrated with artificial intelligence. The process focuses on applying Smart Money Concepts (SMC) alongside natural language processing capabilities from a local Qwen 2.5 model. The system connects to MetaTrader 5 to fetch price data, identify market structures, and analyze economic news for executing trades. Additionally, the software includes an automated risk management mechanism, a multi-threaded design to maintain low latency, and an integrated simulation environment to support strategy testing on historical data.

---

MỤC LỤC

LỜI CAM ĐOAN	2
TÓM TẮT ĐỒ ÁN	3
MỤC LỤC	5
DANH MỤC HÌNH ẢNH, BẢNG BIỂU	6
DANH MỤC TỪ VIẾT TẮT	6

CHƯƠNG 1: MỞ ĐẦU	7
1.1. Đặt vấn đề và tính cấp thiết	7
1.2. Mục tiêu nghiên cứu	7
1.3. Đối tượng và phạm vi	7
1.4. Phương pháp nghiên cứu	7

CHƯƠNG 2: CƠ SỞ LÝ THUYẾT VÀ CÔNG NGHỆ	8
2.1. Tổng quan giao dịch định lượng	8
2.2. Công nghệ và mô hình sử dụng	8
2.2.1. Python và giao diện PySide6	8
2.2.2. Giao thức MetaTrader 5 API	8
2.2.3. Mô hình trí tuệ nhân tạo Qwen 2.5	8

CHƯƠNG 3: PHÂN TÍCH VÀ THIẾT KẾ	8
3.1. Khảo sát hiện trạng và yêu cầu	8
3.2. Thiết kế kiến trúc	8
3.2.1. Sơ đồ Use Case	8
3.2.2. Xử lý đa luồng và cơ chế EventBus	8
3.2.3. Mô hình Vectorized và Event-Driven	8
3.3. Tổ chức mã nguồn Single Responsibility	8

CHƯƠNG 4: TRIỂN KHAI VÀ THỰC NGHIỆM	9
4.1. Giao diện và chức năng chính	9
4.1.1. Màn hình giao dịch và danh mục	9
4.1.2. Biểu đồ nến và công cụ Crosshair	9
4.1.3. Bảng báo cáo từ AI	9
4.1.4. Môi trường kiểm thử chiến lược	9
4.2. Thử nghiệm và đánh giá kết quả	9
4.2.1. Tốc độ xử lý của mô hình ngôn ngữ	9
4.2.2. Thuật toán tính toán khối lượng lệnh	9
4.2.3. Độ trễ cập nhật tin tức vĩ mô	9
4.2.4. Hiệu năng động cơ Backtest	9

CHƯƠNG 5: KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN	10
5.1. Kết quả đạt được	10
5.2. Hạn chế của hệ thống	10
5.3. Hướng phát triển	10

TÀI LIỆU THAM KHẢO	11
PHỤ LỤC	11
