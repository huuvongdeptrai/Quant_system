# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

content = """# CHƯƠNG 2: CƠ SỞ LÝ THUYẾT VÀ PHƯƠNG PHÁP ĐỀ XUẤT

## 2.1. Bộ lọc kỹ thuật và vấn đề độ trễ pha

Các chỉ báo kỹ thuật truyền thống phần lớn hoạt động như các bộ lọc thông thấp nhằm làm mượt chuỗi thời gian giá và loại bỏ nhiễu ngắn hạn [4]. Bộ lọc phổ biến nhất là đường trung bình động giản đơn SMA chu kỳ $k$:

$$\\text{SMA}_k(t) = \\frac{1}{k} \\sum_{i=0}^{k-1} P_{t-i}$$

Theo lý thuyết xử lý tín hiệu số của John F. Ehlers (2001), một bộ lọc trung bình trượt đối xứng với $k$ phần tử luôn gây ra một độ trễ pha cố hữu được xác định bằng công thức toán học [4]:

$$\\tau_{\\text{lag}} = \\frac{k - 1}{2}$$

Đơn vị tính là chu kỳ nến.

Ví dụ, một đường SMA chu kỳ $k = 21$ nến sẽ tạo ra độ trễ pha lên tới $10$ thanh nến. Trong thị trường có độ biến động cao như Vàng giao ngay XAUUSD, độ trễ 10 nến M15 tương đương $150$ phút. Khi tín hiệu giao cắt xuất hiện thì xung lực giá thực tế phần lớn đã suy kiệt hoặc chuẩn bị bước vào pha đảo chiều hồi quy [2], [4]. Hiện tượng trễ pha này chính là nguyên nhân gốc rễ dẫn đến việc các hệ thống giao dịch bán lẻ dựa trên chỉ báo kỹ thuật trễ liên tục bị dính bẫy thanh khoản và gánh chịu tỷ lệ sụt giảm vốn nghiêm trọng.

Do đó, nền tảng nghiên cứu này đề xuất từ bỏ việc phụ thuộc vào các chỉ báo trễ tuyến tính, chuyển dịch sang phương pháp trích xuất các đặc trưng đại diện vi cấu trúc từ dữ liệu giá và khối lượng biến động Tick Volume tức thời của thị trường.

---

## 2.2. Cấu trúc vi mô thị trường và hành vi giá

### 2.2.1. Cấu trúc vi mô thị trường và phân tích dữ liệu giá, khối lượng

Cấu trúc vi mô thị trường tài chính là phân ngành kinh tế học tài chính nghiên cứu các cơ chế trao đổi, khớp lệnh và hình thành giá trong điều kiện ma sát thực tế [6]. Khác với các giả định lý tưởng của Thuyết thị trường hiệu quả EMH, các giao dịch trên thị trường ngoại hối và kim loại quý như tỷ giá XAUUSD diễn ra thông qua sổ lệnh giới hạn LOB [7]. 

Cần lưu ý rằng đối với môi trường giao dịch ngoại hối bán lẻ phi tập trung OTC qua cổng MetaTrader 5, người tham gia không thể tiếp cận trực tiếp toàn bộ độ sâu sổ lệnh Level 2/3 hay khối lượng giao dịch thực tế. Do đó, nghiên cứu này phân định rõ giữa hai cấp độ dữ liệu:
- **Dữ liệu quan sát trực tiếp:** Bao gồm chuỗi giá Mở cửa, Cao nhất, Thấp nhất, Đóng cửa $OHLC$ và khối lượng nhịp nhảy giá Tick Volume.
- **Đặc trưng suy luận đại diện:** Các chỉ số mất cân bằng thanh khoản và áp lực mua bán được lượng hóa gián tiếp từ sự tương quan giữa biên độ nến và tần suất biến động tick. Để xấp xỉ áp lực dòng lệnh trong điều kiện không có sổ lệnh tập trung, các phương pháp phân loại khối lượng gộp BVC của Easley, López de Prado và O'Hara [18] cùng quy tắc suy luận hướng lệnh Tick Test của Lee và Ready [19] được ứng dụng để xây dựng các biến đại diện dòng tiền tích lũy.

Khi một áp lực mua hoặc bán chủ động quy mô lớn xuất hiện, nó sẽ nhanh chóng hấp thụ các lệnh chờ đối ứng tại các bước giá lân cận, tạo ra sự dịch chuyển giá tức thời có biên độ rộng [6], [7]. Hiện tượng này để lại trên đồ thị nến một vùng mất cân bằng thanh khoản Fair Value Gap (FVG). Theo định nghĩa hình học, vùng mất cân bằng thanh khoản tăng giá tại cây nến thứ $t$ được định lượng hóa khi thỏa mãn điều kiện cách biệt giữa nến trước và nến sau:

$$\\text{Gap}_{\\text{bullish}}(t) = P_{\\text{low}}(t+1) - P_{\\text{high}}(t-1) > \\epsilon_{\\text{threshold}}$$

Trong đó $P_{\\text{low}}(t+1)$ là mức giá thấp nhất của cây nến liền sau, $P_{\\text{high}}(t-1)$ là mức giá cao nhất của cây nến liền trước, và $\\epsilon_{\\text{threshold}}$ là ngưỡng biến động vi mô tối thiểu (được chuẩn hóa theo biến động thực tế) nhằm loại bỏ nhiễu của sàn giao dịch. Khi điều kiện này được kích hoạt, khoảng giá giữa $P_{\\text{high}}(t-1)$ và $P_{\\text{low}}(t+1)$ biểu thị một vùng giá có thanh khoản mỏng. Về phương diện thống kê vi cấu trúc, dòng tiền thường có xu hướng hồi quy kiểm định lại vùng giá này trước khi tiếp tục vận động theo xu hướng chính [6].

![Hình 2.1: Sơ đồ hình học vi cấu trúc của Khoảng trống thanh khoản (Fair Value Gap) và cơ chế tái kiểm định](images/hinh_2_1_fvg_imbalance.png)

*Hình 2.1: Sơ đồ hình học vi cấu trúc của Khoảng trống thanh khoản (Fair Value Gap) và cơ chế tái kiểm định của dòng tiền định chế*

### 2.2.2. Nguyên lý Nỗ lực và Kết quả theo lý thuyết Wyckoff

Phương pháp phân tích khối lượng chênh lệch giá VSA, có nguồn gốc từ các nghiên cứu kinh điển của Richard D. Wyckoff, cung cấp một khung lý thuyết vững chắc để phân tích hành vi tích lũy và phân phối thông qua mối tương quan giữa khối lượng và biên độ giá [9]. Quy luật cốt lõi trong lý thuyết Wyckoff là quy luật Nỗ lực và Kết quả:
- **Nỗ lực:** Được đo lường thông qua Khối lượng giao dịch $Volume$ hoặc Tick Volume trong chu kỳ nến, đại diện cho cường độ hoạt động giao dịch.
- **Kết quả:** Được đo lường thông qua Biên độ dao động của thân nến ($\\Delta P = |Close - Open|$ hoặc $Spread = High - Low$).

Trong một phiên giao dịch thông thường, nỗ lực lớn sẽ đi kèm với kết quả tương xứng: khối lượng gia tăng đi kèm với biên độ nến thân dài phá vỡ các ngưỡng cản kỹ thuật. Ngược lại, hiện tượng phân kỳ bất thường xảy ra khi một cây nến có khối lượng giao dịch đột biến nhưng thân nến lại hẹp và giá đóng cửa bị từ chối. Điều này phản ánh rằng nỗ lực đẩy giá đã bị hấp thụ bởi một khối lượng lệnh đối ứng thụ động được đặt chặn sẵn từ phía bên kia của thị trường [9].

Để lượng hóa hiện tượng này một cách khách quan, hệ thống xác định Tỷ số Nỗ lực trên Kết quả ($R_{\\text{eff}}$):

$$R_{\\text{eff}}(t) = \\frac{V_t}{\\max(High_t - Low_t, \\epsilon)}$$

Trạng thái hấp thụ thanh khoản bất thường tại cây nến $t$ được xác nhận khi:

$$R_{\\text{eff}}(t) > \\mu_{R}(k) + 2 \\cdot \\sigma_{R}(k) \\quad \\land \\quad \\frac{|Close_t - P_{\\text{extreme}}|}{High_t - Low_t} \\le \\theta_{\\text{wick}}$$

Trong đó $\\mu_{R}(k)$ và $\\sigma_{R}(k)$ lần lượt là giá trị kỳ vọng và độ lệch chuẩn của tỷ số nỗ lực trong cửa sổ trượt $k = 20$ nến; $P_{\\text{extreme}}$ là mức giá cực đại của xu hướng và $\\theta_{\\text{wick}}$ là ngưỡng tỷ lệ bóng nến từ chối giá. Việc số hóa các điều kiện này thành các biểu thức logic toán học giúp hệ thống nhận diện các mẫu hình giá có tính lặp lại trong phiên một cách tự động và nhất quán.

![Hình 2.2: Sơ đồ cấu trúc pha và nguyên lý Nỗ lực - Kết quả theo phương pháp Wyckoff](images/hinh_2_2_wyckoff_schematic.png)

*Hình 2.2: Sơ đồ cấu trúc pha và nguyên lý Nỗ lực - Kết quả theo phương pháp Wyckoff kết hợp nhận diện điểm bẫy thanh khoản (Spring)*

---

## 2.3. Phân tích vĩ mô và liên thị trường

### 2.3.1. Cơ chế truyền dẫn Lợi suất Danh nghĩa, Lợi suất Thực và Vàng

Theo lý thuyết kinh tế tài chính và định giá tài sản định chế, Vàng là một tài sản thực phi lợi tức [3]. Khác với trái phiếu chi trả coupon cố định hoặc cổ phiếu chi trả cổ tức, việc nắm giữ vàng không tạo ra dòng tiền định kỳ. Do đó, chi phí cơ hội thực sự của việc nắm giữ vàng không chỉ đơn thuần phụ thuộc vào Lợi suất danh nghĩa của Trái phiếu Kho bạc Hoa Kỳ kỳ hạn 10 năm ($y_{\\text{US10Y}}$), mà chịu sự chi phối quyết định bởi **Lợi suất thực (Real Yield)** theo phương trình Fisher:

$$r_{\\text{real}} \\approx y_{\\text{nominal}} - \\pi_{\\text{breakeven}}$$

Trong đó:
- $y_{\\text{nominal}}$ là lợi suất danh nghĩa của Trái phiếu Chính phủ Mỹ kỳ hạn 10 năm US10Y.
- $\\pi_{\\text{breakeven}}$ là tỷ lệ lạm phát kỳ vọng hòa vốn 10 năm, được xác định bằng chênh lệch lợi suất giữa Trái phiếu Kho bạc Mỹ thông thường và Trái phiếu Kho bạc Bảo vệ Lạm phát TIPS.

Khi Lợi suất thực ($r_{\\text{real}}$) tăng cao, chi phí cơ hội thực tế của việc nắm giữ tài sản không sinh lời như Vàng tăng mạnh. Lúc này, dòng vốn từ các quỹ đầu tư định chế toàn cầu có xu hướng tái cơ cấu danh mục từ Vàng sang trái phiếu TIPS để hưởng mức lợi tức thực dương an toàn, tạo áp lực giảm giá mạnh lên tỷ giá XAUUSD. Ngược lại, khi lợi suất thực suy giảm về vùng âm hoặc kỳ vọng lạm phát tăng nhanh hơn tốc độ tăng lãi suất danh nghĩa, chi phí cơ hội nắm giữ vàng tiệm cận 0 hoặc mang giá trị dương, thúc đẩy dòng vốn đổ mạnh vào tích lũy vàng như một công cụ bảo toàn sức mua [3].

Thực chứng trên chuỗi dữ liệu lịch sử giai đoạn 2022 – 2026 cho thấy:
- Hệ số tương quan Pearson giữa chuỗi tỷ suất sinh lợi logarit của XAUUSD và biến động Lợi suất thực 10-Year TIPS đạt mức **tương quan nghịch sâu** ($r \\approx -0.72$ đến $-0.85$). Đây là mối quan hệ định giá cấu trúc vững chắc nhất chi phối xu hướng trung và dài hạn của vàng.
- Trong khi đó, tương quan giữa XAUUSD và Lợi suất danh nghĩa US10Y lỏng lẻo hơn ($r \\approx -0.35$ đến $-0.50$). Thậm chí trong năm 2022, khi lạm phát toàn cầu bùng nổ vượt 8%, vàng và lợi suất danh nghĩa đã xuất hiện các pha phân kỳ dương tạm thời do kỳ vọng lạm phát $\\pi_{\\text{breakeven}}$ tăng nhanh hơn tốc độ điều chỉnh chính sách của Fed.

Mức độ gắn kết tương quan tuyến tính được lượng hóa thông qua công thức Pearson ($r$):

$$r(XAU, Y) = \\frac{\\sum_{i=1}^{N} (r_{\\text{Gold}, i} - \\bar{r}_{\\text{Gold}}) (\\Delta Y_i - \\overline{\\Delta Y})}{\\sqrt{\\sum_{i=1}^{N} (r_{\\text{Gold}, i} - \\bar{r}_{\\text{Gold}})^2} \\sqrt{\\sum_{i=1}^{N} (\\Delta Y_i - \\overline{\\Delta Y})^2}}$$

Hệ thống tính toán chỉ số tương quan động lăn theo cửa sổ trượt 30 ngày để kịp thời nhận diện các giai đoạn phân kỳ hoặc đứt gãy tương quan vĩ mô.

### 2.3.2. Vai trò của DXY, Tâm lý Rủi ro VIX và Hạ tầng Thu thập Dữ liệu Liên thị trường

Bên cạnh lợi suất trái phiếu, hai biến số vĩ mô then chốt khác chi phối dòng tiền luân chuyển toàn cầu là Chỉ số Sức mạnh Đồng Đô la Mỹ DXY và Chỉ số Biến động Kỳ vọng Cboe VIX [3], [5]:

- **Chỉ số DXY:** Đo lường sức mạnh tương đối của đồng USD so với rổ 6 ngoại tệ chủ chốt. Do Vàng quốc tế được định giá tiêu chuẩn bằng USD ($USD/oz$), mối quan hệ giữa Vàng và DXY phần lớn thời gian mang tính nghịch biến với hệ số tương quan Pearson lịch sử dao động từ $r \\approx -0.45$ đến $-0.60$. Khi DXY tăng giá mạnh, Vàng trở nên đắt đỏ hơn đối với các nhà đầu tư nắm giữ các đồng tiền khác, làm suy giảm sức mua vật chất và dòng vốn đầu tư quốc tế.
- **Chỉ số biến động VIX:** Đo lường mức độ biến động ngụ ý kỳ hạn 30 ngày của thị trường quyền chọn chỉ số S&P 500 do Chicago Board Options Exchange công bố. VIX được xem là thước đo nỗi sợ hãi của thị trường tài chính toàn cầu. Trong điều kiện bình thường ($VIX \\le 20.0$), dòng vốn duy trì khẩu vị chấp nhận rủi ro Risk-On và tương quan giữa Vàng và VIX thường ở mức thấp ($r \\approx 0.05$). Tuy nhiên, khi các cú sốc địa chính trị, chiến tranh hoặc khủng hoảng ngân hàng nổ ra đẩy $VIX > 22.5$ (ngưỡng chuyển dịch chế độ rủi ro cao Risk-Off), tâm lý thị trường hoảng loạn sẽ kích hoạt làn sóng tìm kiếm tài sản trú ẩn an toàn, đẩy tương quan tức thời giữa Vàng và VIX tăng vọt lên mức dương mạnh ($r \\approx +0.45$ đến $+0.65$). Cần lưu ý rằng trong các cuộc khủng hoảng thanh lý hoảng loạn, vàng có thể chịu áp lực bán tháo ngắn hạn để bù đắp yêu cầu ký quỹ cho thị trường chứng khoán trước khi phục hồi đà tăng.

**Hạ tầng trích xuất và đối soát dữ liệu liên thị trường:**
Nhằm bảo đảm tính liên tục và độ chuẩn xác của dữ liệu vĩ mô, hệ thống tích hợp cơ chế trích xuất đa nguồn:
1. Luồng dữ liệu giá thời gian thực từ máy chủ MetaTrader 5 thông qua các mã hợp đồng CFD tương ứng (`US10Y`, `USDX`, `VIX`) với tần số cập nhật theo nhịp tick.
2. Tiểu trình `MacroAnalysisWorker` đồng bộ dữ liệu kinh tế vĩ mô bổ trợ bao gồm Lợi suất TIPS và Lịch tin tức kinh tế từ API Investing.com và Cboe DataFeed, lưu trữ vào bộ đệm Macro Cache ở Tầng 2 nhằm cung cấp đầu vào chuẩn hóa cho mô hình Qwen 2.5 [16].

*Bảng 2.1: Tổng hợp hệ số tương quan thực nghiệm và cơ chế tác động liên thị trường lên XAUUSD*

| Biến số vĩ mô | Ký hiệu | Hệ số tương quan Pearson ($r$) | Cơ chế tác động kinh tế | Ngưỡng cảnh báo / Quy tắc hệ thống | Nguồn dữ liệu |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Lợi suất thực 10 năm** | TIPS Real Yield | **$-0.72$ đến $-0.85$** | Chi phí cơ hội thực sự của việc nắm giữ tài sản phi lợi tức | Lợi suất thực đảo chiều tăng $\\rightarrow$ Đình chỉ vị thế Mua | Investing.com / FRED |
| **Lợi suất danh nghĩa** | US10Y | **$-0.35$ đến $-0.50$** | Chi phí cơ hội danh nghĩa; tương quan lỏng khi lạm phát cao | Lợi suất danh nghĩa bứt phá đỉnh $\\rightarrow$ Cảnh báo rủi ro | MetaTrader 5 CFD (`US10Y`) |
| **Sức mạnh Đồng USD** | DXY | **$-0.45$ đến $-0.60$** | Hiệu ứng mẫu số định giá bằng USD ($USD/oz$) | DXY tăng mạnh $\\rightarrow$ Giảm quy mô vị thế Mua | MetaTrader 5 CFD (`USDX`) |
| **Chỉ số Sợ hãi Cboe** | VIX | **$+0.45$ đến $+0.65$** *(khi Risk-Off)* | Dòng tiền tìm kiếm nơi trú ẩn an toàn | $VIX > 22.5$ $\\rightarrow$ Kích hoạt chế độ phòng vệ Risk-Off | MetaTrader 5 / Cboe (`VIX`) |

---

## 2.4. Mô hình Meta-Labeling trong giao dịch định lượng

### 2.4.1. Vai trò của luật tất định, mô hình học máy và mô hình ngôn ngữ lớn

Kiến trúc định lượng của hệ thống phân định rõ trách nhiệm giữa các mô hình tính toán nhằm kiểm soát hiện tượng quá khớp [8]:
1. **Giải thuật tất định:** Vận hành như mô hình sơ cấp, phụ trách quét cơ hội vào lệnh dựa trên quy tắc hình học cấu trúc giá và khối lượng Wyckoff và FVG. Giải thuật này xử lý với tốc độ nano/micro-giây, độc lập hoàn toàn với độ trễ suy luận AI.
2. **Mô hình Ngôn ngữ Lớn cục bộ Qwen 2.5 [16]:** Đảm nhiệm phân tích bối cảnh vĩ mô phi cấu trúc, chuyển hóa phát biểu của ngân hàng trung ương và lịch kinh tế thành véc-tơ tâm lý có cấu trúc qua lược đồ JSON Schema.
3. **Mô hình Học máy dạng Cây LightGBM Booster [12]:** Thực thi chức năng Cổng quyết định xác suất nhị phân, đánh giá độ tin cậy của tín hiệu dựa trên 11 đặc trưng vi cấu trúc tức thời trước khi chuyển tiếp cho tầng quản trị rủi ro.

### 2.4.2. Nguyên lý phân tách vai trò giữa mô hình cơ sở và Meta-Labeling

Phương pháp luận Gán nhãn Bổ trợ Meta-Labeling do Marcos López de Prado [8] đề xuất nhằm giải quyết nhược điểm cố hữu của các mô hình học máy khi áp dụng trực tiếp vào chuỗi thời gian tài chính:

1. **Mô hình Sơ cấp:**
   Được thiết kế để đạt độ nhạy cao, chấp nhận phát sinh nhiều tín hiệu giả mạo nhằm không bỏ sót các cơ hội bứt phá tiềm năng:
   
   $$y_{\\text{primary}} \\in \\{-1, 0, 1\\}$$

2. **Mô hình Thứ cấp:**
   Mô hình học máy không tham gia quyết định hướng lệnh (không quyết định Buy hay Sell). Nhiệm vụ của nó là trả lời câu hỏi nhị phân: *"Nếu tuân theo tín hiệu của Mô hình sơ cấp tại thời điểm hiện tại, xác suất lệnh đó đạt mức lợi nhuận mục tiêu trước khi chạm mức dừng lỗ là bao nhiêu?"*

   $$z_{\\text{meta}} \\in \\{0, 1\\}$$

   Trong đó, nhãn mục tiêu $z$ được xác định dựa trên phương pháp Ba rào chắn [8]:
   - Rào chắn chốt lời: $P_{\\text{entry}} + \\Delta P_{\\text{TP}}$.
   - Rào chắn dừng lỗ: $P_{\\text{entry}} - \\Delta P_{\\text{SL}}$.
   - Rào chắn thời gian: Giới hạn tối đa $T_{\\text{barrier}} = 40$ thanh nến (tương đương 10 giờ giao dịch trên khung M15).
   - *Quy tắc thực thi bi quan:* Trong trường hợp giá dao động mạnh khiến cả rào chắn TP và SL cùng bị kích hoạt trong cùng một thanh nến, thuật toán luôn ấn định nhãn $z = 0$ (coi như chạm SL trước) nhằm loại bỏ kết quả lợi nhuận ảo.
   - *Kỹ thuật Purging & Embargoing:* Các quan sát có khoảng thời gian mở lệnh vắt ngang qua ranh giới giữa tập huấn luyện và kiểm định được loại bỏ để ngăn ngừa rò rỉ thông tin tương lai [8].

Mô hình Meta-Model tính toán hàm xác suất điều kiện:

$$P(z = 1 \\mid X_t) = \\sigma(f(X_t))$$

Trong đó $X_t$ là véc-tơ đặc trưng vi cấu trúc tại thời điểm phát sinh tín hiệu sơ cấp. Cổng quyết định thông minh AI Decision Gate chỉ phê duyệt thực thi lệnh nếu xác suất $P(z=1 \\mid X_t)$ vượt qua một ngưỡng tin cậy tối ưu $P_{\\text{threshold}}$:

$$\\text{Action}(t) = \\begin{cases} 
\\text{EXECUTE}(y_{\\text{primary}}), & \\text{if } P(z = 1 \\mid X_t) \\ge P_{\\text{threshold}} \\\\ 
\\text{DISCARD}, & \\text{if } P(z = 1 \\mid X_t) < P_{\\text{threshold}} 
\\end{cases}$$

Ưu điểm toán học quan trọng của Meta-Labeling là: nó biến bài toán lọc tín hiệu thành một bài toán tối ưu hóa độ chính xác mà không làm suy giảm tỷ lệ lợi nhuận trên rủi ro đã được thiết lập bởi giải thuật sơ cấp [8].

![Hình 2.3: Sơ đồ luồng quyết định hai tầng của Kiến trúc Học máy Meta-Labeling theo phương pháp luận Marcos López de Prado](images/hinh_2_3_meta_labeling_flow.png)

*Hình 2.3: Sơ đồ luồng quyết định hai tầng của Kiến trúc Học máy Meta-Labeling theo phương pháp luận Marcos López de Prado*

---

## 2.5. Nguyên lý kiến trúc phần mềm hướng sự kiện

Để đáp ứng yêu cầu xử lý luồng dữ liệu thời gian thực mà không làm nghẽn giao diện đồ họa, nền tảng giao dịch được thiết kế theo mẫu kiến trúc hướng sự kiện EDA.

Theo mô hình hướng sự kiện, trạng thái thị trường được biểu diễn dưới dạng các đối tượng sự kiện bất biến:
- `MarketDataEvent`: Phát sinh mỗi khi máy chủ MetaTrader 5 đẩy về một thanh nến mới hoặc một nhịp tick giá.
- `MacroSignalEvent`: Phát sinh khi tiểu trình phân tích LLM hoàn tất quá trình trích xuất chỉ số vĩ mô.
- `OrderSignalEvent`: Phát sinh từ lõi định lượng khi các điều kiện hình học và khối lượng được thỏa mãn.
- `ExecutionEvent`: Phát sinh khi lệnh giao dịch được máy chủ sàn xác nhận khớp thành công hoặc bị từ chối.

Các sự kiện được đưa vào Hàng đợi sự kiện ưu tiên. Bộ điều phối tín hiệu Bot Orchestrator lắng nghe và định tuyến sự kiện tới các phân hệ chuyên trách mà không tạo ra bất kỳ sự phụ thuộc liên kết chặt chẽ nào. Nhờ đó, việc một tác vụ phân tích vĩ mô cần tới vài giây để suy luận trên GPU/CPU không làm ảnh hưởng đến độ trễ milli-giây của phân hệ giám sát rủi ro và thực thi lệnh.
"""

Path("Kho_Do_An/Quant_AI_V2.2/docs/thesis/chuong_2_co_so_ly_thuyet.md").write_text(content, encoding="utf-8")
print("Cleaned chuong_2_co_so_ly_thuyet.md!")
