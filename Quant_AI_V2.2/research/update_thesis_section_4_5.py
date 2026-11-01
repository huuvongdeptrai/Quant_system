# -*- coding: utf-8 -*-
import sys
from pathlib import Path

file_path = Path("Kho_Do_An/Quant_AI_V2.2/docs/thesis/chuong_4_thuc_nghiem.md")
content = file_path.read_text(encoding="utf-8")

start_marker = "### 4.5.1. Thiết kế quy trình phân đoạn thời gian và kỹ thuật chống rò rỉ dữ liệu"
end_marker = "## 4.6. Đánh giá vận hành giao dịch trên tài khoản thử nghiệm"

new_section_4_5 = """### 4.5.1. Thiết kế quy trình phân đoạn thời gian và kỹ thuật chống rò rỉ dữ liệu

Nhằm loại bỏ nguy cơ tập dữ liệu kiểm thử tham gia vào quá trình tinh chỉnh tham số, nghiên cứu thiết lập chu trình phân đoạn dữ liệu ba giai đoạn theo trình tự thời gian nghiêm ngặt, bảo đảm mốc thời gian không bị chồng lấn ($t_{\\text{train, end}} < t_{\\text{val, start}} < t_{\\text{test, start}}$):

1. **Cửa sổ Huấn luyện ban đầu (Training Window 2022):** Từ ngày 22/07/2022 15:30 đến 30/12/2022 14:30 (gồm 104 lệnh giao dịch sơ cấp), được sử dụng để xây dựng không gian đặc trưng và huấn luyện các nút phân nhánh ban đầu cho mô hình nhị phân LightGBM.
2. **Tập Xác thực và Lựa chọn Ngưỡng (Validation & Tuning Set 2023 - 2024):** Từ ngày 03/01/2023 14:00 đến 31/12/2024 14:15 (gồm 440 lệnh giao dịch sơ cấp). Tập dữ liệu này được sử dụng làm môi trường khảo sát độ nhạy và xác định ngưỡng xác suất vận hành $P^*$. Sau khi lựa chọn, toàn bộ siêu tham số cùng ngưỡng $P^*$ được cố định trước khi chuyển sang bước kiểm thử.
3. **Giai đoạn Đánh giá Ngoài mẫu (Walk-Forward Out-of-Sample Period 2025 - 2026):** Từ ngày 02/01/2025 14:15 đến 26/10/2026 15:30 (gồm 300 lệnh giao dịch sơ cấp). Giai đoạn này dùng để kiểm tra tính ổn định thực nghiệm của mô hình với ngưỡng vận hành đã cố định.

*Lưu ý phương pháp luận về quy mô mẫu huấn luyện và cơ chế tái huấn luyện:* Quy mô 104 mẫu ban đầu trong năm 2022 là tương đối tinh gọn đối với không gian 11 đặc trưng vi cấu trúc. Nhằm hạn chế rủi ro quá khớp (Overfitting), hệ thống áp dụng đồng thời hai giải pháp kỹ thuật:
- *Ràng buộc cấu trúc mô hình:* Cây quyết định LightGBM bị giới hạn cấu trúc chặt chẽ (`max_depth = 3`, `num_leaves = 12`, `min_child_samples = 15`), sử dụng tỷ lệ lấy mẫu đặc trưng ngẫu nhiên (`feature_fraction = 0.8`) và tốc độ học thấp (`learning_rate = 0.03`). Đáng chú ý về mặt cấu trúc mô hình, mặc dù tham số `num_leaves` được cấu hình ở mức 12, nhưng do áp đặt đồng thời ràng buộc độ sâu trần `max_depth = 3`, số lượng lá tối đa trên thực tế của mỗi cây bị giới hạn cứng không vượt quá $2^3 = 8$ lá theo cấu trúc cây nhị phân hoàn chỉnh. Ràng buộc kép này bảo đảm loại bỏ hoàn toàn nguy cơ phân mảnh lá quá mức (over-leafing), duy trì tính khái quát hóa cao trên tập dữ liệu chuỗi thời gian tài chính có độ nhiễu lớn.
- *Cơ chế tái huấn luyện mở rộng (Expanding Walk-Forward):* Mô hình không cố định một lần duy nhất bằng dữ liệu năm 2022 mà được tái huấn luyện định kỳ sau mỗi chu kỳ năm. Cụ thể, sau khi hoàn tất kiểm thử ngoài mẫu của từng năm, toàn bộ dữ liệu lịch sử đã qua được gộp vào tập huấn luyện mở rộng (năm 2023 huấn luyện trên 104 mẫu năm 2022; năm 2024 huấn luyện trên 337 mẫu 2022–2023; năm 2025 huấn luyện trên 544 mẫu 2022–2024; năm 2026 huấn luyện trên 707 mẫu 2022–2025). Như vậy, 104 lệnh năm 2022 chỉ đóng vai trò hạt giống khởi tạo ban đầu và hoàn toàn không nằm trong bất kỳ thống kê kết quả ngoài mẫu nào.

Song song với việc phân đoạn thời gian, hệ thống áp dụng bốn chốt chặn kỹ thuật theo phương pháp luận của Marcos López de Prado [8]:
- *Phương pháp Ba rào chắn (Triple-Barrier Method):* Nhãn phân loại $z \\in \\{0, 1\\}$ được xác lập dựa trên việc giá chạm rào chắn chốt lời ($+2.5 \\times \\text{ATR}$) trước hay chạm rào chắn dừng lỗ ($-1.0 \\times \\text{ATR}$). Khi vị thế không chạm cả hai rào chắn trong thời hạn tối đa $H = 20$ thanh nến M15 (tương đương 5 giờ giao dịch), vị thế bị đóng cưỡng bức theo thời gian và được gán nhãn quy ước phòng thủ $z = 0$ (không đạt biên độ mục tiêu trong khung thời gian kỳ vọng). Đây là một lựa chọn thiết kế mang tính thận trọng trong quản trị định lượng, chỉ những cơ hội đạt trọn vẹn mục tiêu biên độ mới được coi là tín hiệu chất lượng cao để mô hình học tập.
- *Thanh lọc mẫu chồng lấn (Purging):* Khi một vị thế có khoảng thời gian nắm giữ $[t_{\\text{entry}}, t_{\\text{exit}}]$ vắt ngang qua ranh giới giữa các tập dữ liệu, quan sát đó bị loại bỏ khỏi tập huấn luyện nhằm ngăn chặn hiện tượng rò rỉ nhãn kết quả tương lai ngược về quá khứ.
- *Vùng đệm cách ly (Embargoing):* Thiết lập khoảng thời gian ngắt quãng an toàn $h = 5$ thanh nến ($1.25$ giờ) sau mỗi sự kiện đóng lệnh trước khi thu thập mẫu huấn luyện tiếp theo, giúp giảm thiểu nguy cơ phụ thuộc chuỗi và hiện tượng rò rỉ thông tin giữa các vị thế liên tiếp.
- *Tính nhân quả của hệ đặc trưng (Causality):* Toàn bộ 11 biến số đầu vào ($X_t$) được tính toán từ các toán tử hồi quy trễ về quá khứ (cửa sổ trượt $t-k \\dots t$), bảo đảm không sử dụng bất kỳ thông tin nào của thanh nến tương lai $t+1$.

### 4.5.2. Khảo sát độ nhạy trên Tập Xác thực và Xác lập ngưỡng vận hành

Nhằm mục tiêu xác lập một quy tắc ra quyết định khách quan trước khi bước vào giai đoạn kiểm thử ngoài mẫu, nghiên cứu định nghĩa hàm mục tiêu Calmar Proxy quy ước:

$$J(P) = \\frac{\\text{Net Profit}(P) / \\text{Initial Capital}}{\\text{Max Drawdown}(P)}$$

*Ghi chú:* Đây là chỉ số quy ước nội bộ của đề tài nhằm đo lường tỷ số giữa tỷ suất sinh lời trên vốn ban đầu (100,000 USD) và mức sụt giảm tối đa trong một chu kỳ thực nghiệm, không phải Calmar Ratio chuẩn hóa theo tỷ suất sinh lời kép hằng năm (CAGR).

Nghiên cứu tiến hành khảo sát độ nhạy trên 440 tín hiệu sơ cấp thuộc Tập Xác thực (2023 - 2024) với giả định vốn ban đầu quy chuẩn 100,000 USD, khấu trừ chi phí hoa hồng 7 USD/lot và trượt giá 20 points. Mức sụt giảm tối đa (Max Drawdown) trong bảng này được tính toán độc lập hoàn toàn trên đường cong vốn riêng biệt của giai đoạn xác thực:

*Bảng 4.5: Khảo sát độ nhạy và lựa chọn ngưỡng trên Tập Xác thực (2023 - 2024, 440 lệnh)*

| Ngưỡng xác suất ($P$) | Số giao dịch | Số lệnh thắng | Số lệnh thua | Tỷ lệ thắng (Winrate) | Lợi nhuận ròng (Net Profit) | Mức sụt giảm tối đa (Max Drawdown) | Profit Factor | Chỉ số quy ước $J(P)$ |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **$P = 0.00$ (Gốc)** | 440 | 127 | 313 | 28.86% | -$27,430.32 USD | 39.85% | 0.89 | -0.69 |
| **$P \\ge 0.32$** | 134 | 42 | 92 | 31.34% | -$208.69 USD | 25.45% | 0.99 | -0.01 |
| **$P \\ge 0.34$** | 117 | 35 | 82 | 29.91% | -$4,424.70 USD | 16.23% | 0.91 | -0.27 |
| **$P \\ge 0.36$** | 94 | 30 | 64 | 31.91% | +$795.88 USD | 12.24% | 1.05 | +0.07 |
| **$P \\ge 0.38$ *(Chọn)*** | **72** | **23** | **49** | **31.94%** | **+$1,892.95 USD** | **14.12%** | **1.08** | **+0.13** |
| **$P \\ge 0.40$** | 65 | 19 | 46 | 29.23% | -$2,610.55 USD | 12.09% | 0.92 | -0.22 |
| **$P \\ge 0.42$** | 59 | 18 | 41 | 30.51% | -$37.33 USD | 8.97% | 0.99 | -0.00 |

Số liệu thực nghiệm từ Bảng 4.5 cho thấy: trong giai đoạn thị trường giằng co bất lợi 2023–2024, chiến lược cơ sở ($P=0.00$) chịu thua lỗ $-\\$27,430.32$ USD với mức sụt giảm tài khoản nghiêm trọng ($39.85\\%$). Tại các ngưỡng xác suất khảo sát, ngưỡng $P^* = 0.38$ là điểm vận hành mang lại lợi nhuận ròng dương cao nhất ($+\\$1,892.95$ USD), nén mức sụt giảm tối đa từ $39.85\\%$ xuống $14.12\\%$ (giảm hơn $64.5\\%$ biên độ rủi ro so với chiến lược cơ sở), và tối đa hóa chỉ số mục tiêu quy ước $J(P) = +0.13$ (vượt trội hoàn toàn so với các ngưỡng còn lại vốn có chỉ số âm hoặc tiệm cận 0). Vì vậy, ngưỡng $P^* = 0.38$ được lựa chọn và đóng băng (frozen) làm ngưỡng vận hành chính thức trước khi tiến hành kiểm thử ngoài mẫu.

### 4.5.3. Đánh giá ngoài mẫu theo quy trình Walk-Forward giai đoạn 2025 - 2026

Ngưỡng xác suất ($P^*=0.38$) được lựa chọn trên tập xác thực giai đoạn 2023–2024 và được cố định trong quá trình đánh giá giai đoạn 2025–2026. Mô hình được cập nhật theo cơ chế Walk-Forward: dữ liệu lịch sử của năm trước chỉ được bổ sung vào tập huấn luyện sau khi giai đoạn đó kết thúc, nhằm tạo dự báo cho giai đoạn tiếp theo. Do đó, kết quả năm 2025–2026 được xem là kết quả đánh giá ngoài mẫu theo thời gian với ngưỡng vận hành cố định, chứ không phải một tập kiểm thử bất biến hoàn toàn tách biệt khỏi mọi lần tái huấn luyện. Quy trình này cho phép đánh giá khả năng thích ứng của mô hình khi có thêm dữ liệu lịch sử, đồng thời vẫn kiểm soát chặt chẽ việc lựa chọn tham số để tránh rò rỉ thông tin tương lai.

Kết quả đối chứng trực diện A/B giữa Chiến lược cơ sở và Chiến lược sau lọc trên cùng 300 lệnh sơ cấp của giai đoạn 2025 - 2026, cùng mức vốn ban đầu 100,000 USD và cùng điều kiện chi phí được tổng hợp tại Bảng 4.6:

*Bảng 4.6: Bảng đối chứng A/B ngoài mẫu theo quy trình Walk-Forward (2025 - 2026, 300 lệnh)*

| Phương án kiểm nghiệm | Số lượng giao dịch | Số lệnh thắng | Số lệnh thua | Tỷ lệ thắng (Winrate) | Lợi nhuận ròng (Net Profit) | Mức sụt giảm tối đa (Max Drawdown) | Profit Factor |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Chiến lược cơ sở ($P = 0.00$)** | 300 | 117 | 183 | 39.00% | +$96,181.85 USD | 9.95% | 1.47 |
| **Sau lọc Meta-Labeling ($P \\ge 0.38$)** | 62 | 25 | 37 | 40.32% | +$23,455.18 USD | 4.85% | 1.43 |

Kết quả kiểm định trên giai đoạn 2025–2026 cho thấy hiệu quả của bộ lọc Meta-Labeling phụ thuộc đáng kể vào chế độ thị trường (Market Regime). Trên cùng 300 tín hiệu sơ cấp, chiến lược cơ sở đạt lợi nhuận ròng 96,181.85 USD, tỷ lệ thắng 39.00%, Profit Factor 1.47 và mức sụt giảm tối đa 9.95%. Khi áp dụng ngưỡng xác suất cố định $P \\ge 0.38$, số giao dịch giảm còn 62, lợi nhuận ròng đạt 23,455.18 USD, tỷ lệ thắng đạt 40.32%, Profit Factor đạt 1.43 và mức sụt giảm tối đa được nén từ 9.95% xuống 4.85%.

Như vậy, trong giai đoạn kiểm thử này, bộ lọc làm giảm đáng kể tần suất giao dịch (giảm $79.3\\%$, từ 300 xuống 62 lệnh) và lợi nhuận tuyệt đối (giảm $75.6\\%$, từ 96,181.85 USD xuống 23,455.18 USD), trong khi tỷ lệ thắng chỉ tăng nhẹ 1.32 điểm phần trăm (từ 39.00% lên 40.32%) và Profit Factor giảm nhẹ từ 1.47 xuống 1.43. Mặc dù bộ lọc hỗ trợ nén mức sụt giảm tối đa từ $9.95\\%$ xuống $4.85\\%$ (giảm 5.10 điểm phần trăm), nhưng đối với một thị trường có xu hướng tăng mạnh mẽ (Strong Bull Trend) như năm 2025–2026, chiến lược cơ sở khai thác tối đa động lượng và mang lại hiệu quả tổng thể vượt trội hơn. Kết quả thực nghiệm này là bằng chứng rõ ràng cho thấy một ngưỡng xác suất được lựa chọn tối ưu trong điều kiện thị trường giằng co, biến động phức tạp (Tập Xác thực 2023–2024) có xu hướng phòng thủ rất cao và chưa chắc đã phù hợp với mọi chế độ thị trường mới. Do đó, cần tiếp tục nghiên cứu cơ chế ngưỡng động thích ứng (Dynamic Thresholding) theo chế độ thị trường và phân tích sâu hơn tác động của chi phí giao dịch trước khi đưa ra kết luận về tính ổn định dài hạn.

### 4.5.4. Khảo sát hồi cứu toàn chu kỳ Walk-Forward và Phân tích Sự Đánh đổi

Nhằm cung cấp bức tranh toàn diện về hành vi phân bổ lệnh của bộ lọc qua các giai đoạn thị trường khác nhau, nghiên cứu tổng hợp kết quả trên toàn bộ chuỗi 740 tín hiệu Walk-Forward ngoài mẫu (2023 - 2026):

*Bảng 4.7: Khảo sát hồi cứu hành vi bộ lọc trên toàn chu kỳ Walk-Forward (2023 - 2026, 740 lệnh)*

| Ngưỡng xác suất ($P$) | Số giao dịch | Số lệnh thắng | Số lệnh thua | Tỷ lệ thắng (Winrate) | Lợi nhuận ròng (Net Profit) | Mức sụt giảm tối đa (Max Drawdown) | Profit Factor | Chỉ số quy ước $J(P)$ |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **$P = 0.00$ (Gốc)** | 740 | 244 | 496 | 32.97% | +$68,751.53 USD | 39.45% | 1.16 | **1.74** |
| **$P \\ge 0.32$** | 283 | 93 | 190 | 32.86% | +$26,251.08 USD | 19.79% | 1.15 | **1.33** |
| **$P \\ge 0.34$** | 232 | 76 | 156 | 32.76% | +$23,221.48 USD | 15.83% | 1.16 | **1.47** |
| **$P \\ge 0.36$** | 177 | 59 | 118 | 33.33% | +$16,132.69 USD | 11.63% | 1.14 | **1.39** |
| **$P \\ge 0.38$** | **134** | **48** | **86** | **35.82%** | **+$25,348.13 USD** | **7.46%** | **1.31** | **3.40** |
| **$P \\ge 0.40$** | 103 | 37 | 66 | 35.92% | +$19,876.41 USD | 10.41% | 1.33 | **1.91** |
| **$P \\ge 0.42$** | 85 | 30 | 55 | 35.29% | +$15,099.43 USD | 8.86% | 1.30 | **1.70** |

*Lưu ý phương pháp luận:* Bảng 4.7 mang tính chất khảo sát hồi cứu (Retrospective Analysis) nhằm ghi nhận tổng thể sự dịch chuyển của đường cong rủi ro trên toàn bộ chu kỳ gần 4 năm dữ liệu (từ tháng 01/2023 đến tháng 10/2026). Dữ liệu trong bảng này bao gồm cả giai đoạn xác thực đã dùng để chọn ngưỡng; vì vậy, bảng này tuyệt đối không được xem là bằng chứng kiểm thử độc lập mới hay được dùng để biện minh cho quyết định chọn ngưỡng $P^* = 0.38$ đã được thiết lập trước đó.

Về mặt tính toán thực nghiệm, số liệu giữa Bảng 4.5, Bảng 4.6 và Bảng 4.7 bảo đảm tính nhất quán toán học và minh bạch phương pháp luận:
- Tổng số tín hiệu ngoài mẫu: $440 \\text{ (Xác thực)} + 300 \\text{ (Kiểm thử)} = 740 \\text{ lệnh}$.
- Số lệnh tại ngưỡng $P \\ge 0.38$: $72 \\text{ (Xác thực)} + 62 \\text{ (Kiểm thử)} = 134 \\text{ lệnh}$.
- Tổng lợi nhuận ròng tại ngưỡng $P \\ge 0.38$: $+\\$1,892.95 \\text{ USD} + \\$23,455.18 \\text{ USD} = +\\$25,348.13 \\text{ USD}$.
- Tổng số lệnh thắng/thua tại $P \\ge 0.38$: $23\\text{W} + 25\\text{W} = 48\\text{W}$ và $49\\text{L} + 37\\text{L} = 86\\text{L}$.
- Sự khác biệt về cách đo lường mức sụt giảm tối đa: Tại Bảng 4.5 và Bảng 4.6, Max Drawdown được tính độc lập trên từng phân đoạn với vốn quy chuẩn đặt lại ban đầu là 100,000 USD (đo lường độ rủi ro cục bộ của từng giai đoạn riêng biệt). Ngược lại, tại Bảng 4.7, Max Drawdown được tính trên đường cong vốn tích lũy liên tục xuyên suốt 740 lệnh (2023 - 2026), phản ánh rủi ro tổng thể khi tài khoản vận hành liên tục qua nhiều năm.

Nhìn nhận một cách khoa học, cơ chế Meta-Labeling thể hiện rõ bài toán đánh đổi kỹ thuật giữa tần suất giao dịch và khả năng kiểm soát rủi ro sụt giảm: Trên toàn bộ chu kỳ 2023 - 2026, bộ lọc nén mức sụt giảm tối đa từ $39.45\\%$ xuống còn $7.46\\%$ (giảm $81.1\\%$), đưa mức rủi ro về dưới trần mục tiêu $10\\%$ được lựa chọn trong thiết kế hệ thống. Đặc biệt trong giai đoạn giằng co 2023, bộ lọc hỗ trợ chuyển hóa mức thua lỗ $-\\$16,047.16$ USD của chiến lược cơ sở thành mức lợi nhuận dương $+\\$2,968.51$ USD. Ngược lại, chi phí đánh đổi là sự sụt giảm $81.9\\%$ về tần suất giao dịch và giảm $63.1\\%$ quy mô lợi nhuận danh nghĩa so với chiến lược cơ sở. Trong quản trị rủi ro danh mục định lượng, mức sụt giảm gần $40\\%$ của chiến lược cơ sở là không thể chấp nhận được đối với vốn tổ chức; do đó, sự đánh đổi này là một lựa chọn phòng thủ có chủ đích nhằm bảo đảm tính tồn tại của tài khoản trong các giai đoạn thị trường khắc nghiệt.

### 4.5.5. Phân tích mức độ quan trọng của các đặc trưng vi cấu trúc

Để phân tích cơ chế phân nhánh của mô hình học máy, mức độ đóng góp thông tin của 11 đặc trưng vi cấu trúc được thống kê thông qua chỉ số độ lợi phân tách (Split Gain) của thuật toán LightGBM.

Theo chỉ số Split Gain của mô hình được khảo sát, hai đặc trưng `gk_vol` ($28.4\\%$) và `cvd_proxy` ($22.1\\%$) có mức đóng góp vào các phép chia cây cao nhất. Hai đặc trưng tiếp theo là khoảng đệm cản `headroom` ($16.8\\%$) và độ lệch giá trị hợp lý `vwap_zscore` ($14.2\\%$), trong khi các chỉ báo xung lượng như ADX hay độ mở rộng EMA đóng góp tỷ trọng nhỏ hơn ($< 8\\%$). Kết quả này phản ánh rằng mô hình sử dụng các biến động nội tại và dòng tiền đại diện tương đối nhiều trong quá trình phân nhánh cây quyết định; tuy nhiên, điều này không tự chứng minh quan hệ nhân quả hay khẳng định trực tiếp hành vi của các tổ chức lớn trên thị trường.

![Hình 4.3: Hiệu quả nén sụt giảm tài khoản (Drawdown Compression) và tỷ lệ thắng ngoài mẫu của mô hình Meta-Labeling qua các ngưỡng xác suất](images/hinh_4_3_meta_labeling_breakthrough.png)

*Hình 4.3: Hiệu quả nén sụt giảm tài khoản (Drawdown Compression) và tỷ lệ thắng ngoài mẫu của mô hình Meta-Labeling qua các ngưỡng xác suất từ 0.00 đến 0.42*

![Hình 4.4: Xếp hạng mức độ quan trọng của 11 đặc trưng vi cấu trúc theo chỉ số Split Gain](images/hinh_4_4_feature_importance.png)

*Hình 4.4: Xếp hạng mức độ quan trọng của 11 đặc trưng vi cấu trúc trong mô hình LightGBM theo chỉ số Split Gain*

---

"""

start_pos = content.find(start_marker)
end_pos = content.find(end_marker)

if start_pos == -1 or end_pos == -1:
    print(f"Error: Markers not found! start={start_pos}, end={end_pos}")
    sys.exit(1)

updated_content = content[:start_pos] + new_section_4_5 + content[end_pos:]
file_path.write_text(updated_content, encoding="utf-8")
print("Successfully replaced Section 4.5 in chuong_4_thuc_nghiem.md!")
