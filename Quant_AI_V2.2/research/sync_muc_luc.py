# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

p = Path("Kho_Do_An/Quant_AI_V2.2/docs/thesis/muc_luc_chinh_thuc.md")

content = """# MỤC LỤC CHÍNH THỨC ĐỒ ÁN TỐT NGHIỆP

**ĐỀ TÀI: XÂY DỰNG NỀN TẢNG GIAO DỊCH ĐỊNH LƯỢNG ĐA TẦNG TỰ HÀNH TÍCH HỢP HỌC MÁY META-LABELING VÀ MÔ HÌNH NGÔN NGỮ LỚN CỤC BỘ**

---

### PHẦN MỞ ĐẦU CHUNG
- **LỜI CAM ĐOAN**
- **TÓM TẮT ĐỒ ÁN (TIẾNG VIỆT & ENGLISH ABSTRACT)**
- **MỤC LỤC**
- **DANH MỤC TỪ VIẾT TẮT**
- **DANH MỤC BẢNG BIỂU**
- **DANH MỤC HÌNH VẼ VÀ ĐỒ THỊ**

---

### CHƯƠNG 1: MỞ ĐẦU

- **1.1. Bối cảnh nghiên cứu và vấn đề đặt ra**
  - 1.1.1. Vấn đề độ trễ của các bộ lọc kỹ thuật truyền thống
  - 1.1.2. Độ trễ xử lý dữ liệu và thực thi trong giao dịch thuật toán
  - 1.1.3. Hạn chế của hệ luật tĩnh trước sự thay đổi chế độ thị trường
- **1.2. Mục tiêu nghiên cứu**
  - 1.2.1. Mục tiêu tổng quát
  - 1.2.2. Các mục tiêu cụ thể
- **1.3. Đối tượng và Phạm vi nghiên cứu**
  - 1.3.1. Đối tượng nghiên cứu
  - 1.3.2. Phạm vi nghiên cứu
- **1.4. Phương pháp nghiên cứu**
- **1.5. Đóng góp dự kiến và kết cấu báo cáo**
  - 1.5.1. Đóng góp dự kiến của đồ án
  - 1.5.2. Kết cấu báo cáo đồ án

---

### CHƯƠNG 2: CƠ SỞ LÝ THUYẾT VÀ PHƯƠNG PHÁP ĐỀ XUẤT

- **2.1. Bộ lọc kỹ thuật và vấn đề độ trễ pha**
- **2.2. Cấu trúc vi mô thị trường và hành vi giá**
  - 2.2.1. Cấu trúc vi mô thị trường và phân tích dữ liệu giá, khối lượng
  - 2.2.2. Nguyên lý Nỗ lực và Kết quả theo lý thuyết Wyckoff
- **2.3. Phân tích vĩ mô và liên thị trường**
  - 2.3.1. Cơ chế truyền dẫn Lợi suất Danh nghĩa, Lợi suất Thực và Vàng
  - 2.3.2. Vai trò của DXY, Tâm lý Rủi ro VIX và Hạ tầng Thu thập Dữ liệu Liên thị trường
- **2.4. Mô hình Meta-Labeling trong giao dịch định lượng**
  - 2.4.1. Vai trò của luật tất định, mô hình học máy và mô hình ngôn ngữ lớn
  - 2.4.2. Nguyên lý phân tách vai trò giữa mô hình cơ sở và Meta-Labeling
- **2.5. Nguyên lý kiến trúc phần mềm hướng sự kiện**

---

### CHƯƠNG 3: THIẾT KẾ VÀ XÂY DỰNG HỆ THỐNG GIAO DỊCH ĐỊNH LƯỢNG

- **3.1. Phân tích yêu cầu và tiêu chí hiệu năng hệ thống**
  - 3.1.1. Yêu cầu chức năng
  - 3.1.2. Tiêu chuẩn phi chức năng và ngân sách độ trễ
- **3.2. Lựa chọn công nghệ và môi trường triển khai**
  - 3.2.1. Ngôn ngữ lập trình và Môi trường thực thi
  - 3.2.2. Giao thức kết nối và Thu thập dữ liệu vi cấu trúc
  - 3.2.3. Động cơ Học máy và Nền tảng Mô hình Ngôn ngữ Lớn cục bộ
  - 3.2.4. Khung Giao diện Đồ họa và Động cơ Đồ thị thời gian thực
  - 3.2.5. Hệ thống Lưu trữ Trạng thái và Cơ chế Bền vững Dữ liệu
- **3.3. Kiến trúc tổng thể và quy trình luồng dữ liệu**
  - 3.3.1. Luồng Giao dịch Thuật toán Tự hành
  - 3.3.2. Luồng Hỗ trợ Giao dịch Thủ công Thông minh
- **3.4. Phân hệ kết nối, quản lý trạng thái và phục hồi khi có lỗi**
  - 3.4.1. Quản lý dữ liệu chuỗi thời gian bằng cửa sổ trượt
  - 3.4.2. Lưu trữ với SQLite WAL và phục hồi trạng thái
  - 3.4.3. Giám sát tiến trình và tái thiết lập kết nối
- **3.5. Phân hệ phân tích vĩ mô tích hợp mô hình ngôn ngữ lớn**
  - 3.5.1. Quy trình xử lý bất đồng bộ tin tức kinh tế và cấu trúc chỉ thị phân tích
  - 3.5.2. Cơ chế ràng buộc cú pháp JSON và kiểm thực lược đồ nghiệp vụ
  - 3.5.3. Trực quan hóa bối cảnh vĩ mô và phân hệ phòng vệ sự kiện kinh tế Tab Macro Calendar
- **3.6. Xây dựng đặc trưng từ dữ liệu vi cấu trúc**
  - 3.6.1. Ước lượng biến động Garman-Klass và đặc trưng khối lượng đại diện
  - 3.6.2. Chuẩn hóa độ lệch so với giá trị hợp lý và vùng cản
- **3.7. Phân hệ cổng quyết định giao dịch**
  - 3.7.1. Kết hợp tín hiệu vĩ mô và vi cấu trúc
  - 3.7.2. Chuẩn hóa biên độ dao động và cơ chế nạp mô hình
- **3.8. Phân hệ quản trị rủi ro và mô phỏng thực thi lệnh**
- **3.9. Giao diện điều khiển và luồng tương tác người dùng**

---

### CHƯƠNG 4: THỰC NGHIỆM VÀ ĐÁNH GIÁ HỆ THỐNG

- **4.1. Môi trường, dữ liệu và phương pháp thực nghiệm**
- **4.2. Kiểm thử chức năng và khả năng chịu lỗi**
- **4.3. Đánh giá hiệu năng xử lý và sử dụng tài nguyên**
  - 4.3.1. Mức tiêu thụ bộ nhớ và quản lý cửa sổ trượt
  - 4.3.2. Đo lường độ trễ xử lý và phản hồi của hệ thống
- **4.4. Đánh giá chiến lược cơ sở sau chi phí giao dịch**
  - 4.4.1. Đánh giá chiến lược trên dữ liệu lịch sử bằng xử lý vector hóa
  - 4.4.2. Phân tích mức sụt giảm tài khoản theo các giai đoạn thị trường
- **4.5. Đánh giá Meta-Labeling theo quy trình Walk-Forward: tập xác thực và kiểm thử độc lập**
  - 4.5.1. Thiết kế quy trình phân đoạn thời gian và kỹ thuật chống rò rỉ dữ liệu
  - 4.5.2. Khảo sát độ nhạy trên Tập Xác thực và Xác lập ngưỡng vận hành
  - 4.5.3. Đánh giá ngoài mẫu độc lập theo quy trình Walk-Forward giai đoạn 2025 - 2026
  - 4.5.4. Khảo sát hồi cứu toàn chu kỳ Walk-Forward và Phân tích Sự Đánh đổi
  - 4.5.5. Phân tích mức độ quan trọng của các đặc trưng vi cấu trúc
- **4.6. Đánh giá vận hành giao dịch trên tài khoản thử nghiệm**

---

### CHƯƠNG 5: KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN

- **5.1. Tổng kết kết quả nghiên cứu**
- **5.2. Đóng góp khoa học và kỹ thuật phần mềm của đồ án**
  - 5.2.1. Đóng góp về mặt Khoa học Tài chính Định lượng
  - 5.2.2. Đóng góp về mặt Kỹ nghệ Phần mềm và Kiến trúc Hệ thống
- **5.3. Các hạn chế kỹ thuật hiện tại**
- **5.4. Hướng mở rộng nghiên cứu trong tương lai**

---

### DANH MỤC BẢNG BIỂU
- **Bảng 2.1:** Cơ chế kinh tế và quy tắc vận hành liên thị trường của nền tảng VECTRA
- **Bảng 3.1:** Môi trường thử nghiệm và kết quả đo lường độ trễ, tài nguyên hệ thống VECTRA
- **Bảng 3.2:** Bảng tổng hợp ngăn xếp công nghệ và môi trường triển khai hệ thống VECTRA
- **Bảng 3.3:** Phân định các mã định danh MetaTrader 5 và vai trò lưu trữ trong cơ sở dữ liệu nội bộ
- **Bảng 3.4:** Bảng quy tắc ánh xạ trường `bias_direction` sang trạng thái xu hướng vĩ mô `macro_bias`
- **Bảng 3.5:** Bảng đặc tả toán học và thông số vận hành của 11 đặc trưng vi cấu trúc
- **Bảng 4.1:** Kết quả kiểm thử 5 kịch bản ngoại lệ sống còn của hệ thống
- **Bảng 4.2:** Kết quả đo lường tài nguyên phần cứng thực tế của hệ thống
- **Bảng 4.3:** Bóc tách ngân sách độ trễ chi tiết trong đường ống xử lý nội bộ (1,000 chu kỳ)
- **Bảng 4.4:** Hiệu năng của chiến lược tất định thuần túy qua các cấu hình chiến lược (khoảng 4.27 năm theo lịch)
- **Bảng 4.5:** Khảo sát độ nhạy và lựa chọn ngưỡng trên Tập Xác thực (2023 - 2024, 440 lệnh)
- **Bảng 4.6:** Bảng đối chứng A/B ngoài mẫu theo quy trình Walk-Forward (2025 - 2026, 300 lệnh)
- **Bảng 4.7:** Khảo sát hồi cứu tổng hợp hành vi bộ lọc trên toàn chu kỳ Walk-Forward (2023 - 2026, 740 lệnh)
- **Bảng 4.8:** Phân rã chi tiết hiệu quả bộ lọc Meta-Labeling theo từng năm trong chuỗi Walk-Forward (Ngưỡng $P^* = 0.38$)

---

### DANH MỤC HÌNH VẼ VÀ ĐỒ THỊ
- **Hình 2.1:** Sơ đồ hình học vi cấu trúc của Khoảng cách giá Fair Value Gap và cơ chế kiểm định lại
- **Hình 2.2:** Sơ đồ cấu trúc pha và nguyên lý Nỗ lực - Kết quả theo phương pháp Wyckoff kết hợp nhận diện điểm bẫy thanh khoản Spring
- **Hình 2.3:** Sơ đồ luồng quyết định hai tầng của Kiến trúc Học máy Meta-Labeling theo phương pháp luận Marcos López de Prado
- **Hình 3.1:** Sơ đồ kiến trúc phân tầng phòng vệ kết hợp Cơ chế Điều phối Kép giữa Luồng Tự hành và Luồng Thủ công Thông minh
- **Hình 3.2:** Giao diện trực quan hóa bối cảnh vĩ mô và bảng điều phối phòng vệ sự kiện kinh tế Tab Macro Calendar hiển thị dữ liệu của Tầng 2 trong kiến trúc hệ thống
- **Hình 3.3:** Giao diện trạm điều khiển trung tâm Main Trading Terminal tích hợp biểu đồ nến vi sai với mục tiêu thiết kế 60 FPS, bảng theo dõi đa tài sản và bảng quản lý vị thế Blotter Dock
- **Hình 3.4:** Giao diện phân hệ kiểm thử lịch sử Tab Backtest và cổng kiểm duyệt an toàn 4 điểm Pre-trade Safety trong trạm giao dịch VECTRA
- **Hình 3.5:** Giao diện Phân hệ Phân tích Hiệu suất và Nhật ký Định lượng Tab Performance Dashboard với Lịch PnL Heatmap, Đồ thị vốn kép Equity/Drawdown và Bảng chỉ số rủi ro Sharpe/Sortino
- **Hình 4.1:** Kết quả đo lường thực nghiệm hiệu năng hệ thống: (a) Biến thiên độ trễ qua 1.000 chu kỳ; (b) Bóc tách tỷ trọng thời gian 5 tầng xử lý; (c) Mức sử dụng bộ nhớ RAM duy trì ổn định trong thử nghiệm với cửa sổ cố định $K = 150$
- **Hình 4.2:** Biểu đồ đường cong vốn và đường chìm sụt giảm của chiến lược tất định qua 99.999 nến M15 XAUUSD (2022 - 2026)
- **Hình 4.3:** Hiệu quả nén sụt giảm tài khoản và tỷ lệ thắng ngoài mẫu của mô hình Meta-Labeling qua các ngưỡng xác suất từ 0.00 đến 0.42
- **Hình 4.4:** Xếp hạng mức độ quan trọng của 11 đặc trưng vi cấu trúc trong mô hình LightGBM theo chỉ số Split Gain
- **Hình 4.5:** Kết quả kiểm toán thực nghiệm vận hành thời gian thực trên tài khoản Demo MetaTrader 5: (a) Phân phối độ trễ xác thực lệnh nội bộ; (b) Thống kê độ trượt giá thực tế Slippage của các lệnh đã khớp trên máy chủ MetaTrader 5

---

### TÀI LIỆU THAM KHẢO (IEEE Standard)
### PHỤ LỤC
- **Phụ lục A:** Đặc tả thông số kỹ thuật môi trường và Thư viện triển khai
- **Phụ lục B:** Cấu trúc phân cấp mã nguồn nền tảng phần mềm
- **Phụ lục C:** Cấu trúc Chỉ thị và Khuôn mẫu JSON Phân tích Vĩ mô
- **Phụ lục D:** Đặc tả 11 Chiều Véc-tơ Đặc trưng Vi cấu trúc của Bộ lọc ML
"""

p.write_text(content, encoding="utf-8")
print("Successfully synced muc_luc_chinh_thuc.md!")
