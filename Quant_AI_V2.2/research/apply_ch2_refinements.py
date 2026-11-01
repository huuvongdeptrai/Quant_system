# -*- coding: utf-8 -*-
"""
Script to apply Chapter 2 refinements requested in academic review turn 11:
1. Section 2.1: SMA lag vs trading signal lag; tone down opening and conclusion.
2. Section 2.2.1: FVG ATR threshold alpha*ATR_14 formula from codebase (alpha=0.15); designate FVG as representative geometric feature.
3. Section 2.2.2: R_eff epsilon=10^-5 numerical regularization; tone down absorption claim to representative tick activity feature.
4. Section 2.3: Macro synchronization based on actually available data, account for timezone/holidays; distinguish ICE/Cboe benchmark indices from broker quotes on MT5; unify VIX rule to binary VIX >= 20.0 (Risk-Off) and VIX < 20.0 (Risk-On) matching codebase. Add FRED citation [25] for DGS10 alongside [24] DFII10.
5. Section 2.4.2: Triple-Barrier formula with direction variable s_t in {-1, +1} for both Buy and Sell: P_TP = P_entry + s_t*Delta_P_TP and P_SL = P_entry - s_t*Delta_P_SL. Detail pessimistic rule (z=0 on simultaneous hit) and embargoing buffer h_embargo = 5 bars matching Chapter 4.
6. References: Format [22], [23], [24] per IEEE and add [25] for DGS10.
"""
import re
import sys

def main():
    ch2_path = "docs/thesis/chuong_2_co_so_ly_thuyet.md"
    ref_path = "docs/thesis/tai_lieu_tham_khao_phu_luc.md"

    with open(ch2_path, "r", encoding="utf-8") as f:
        ch2 = f.read()

    with open(ref_path, "r", encoding="utf-8") as f:
        refs = f.read()

    # --- 1. Section 2.1 Refinements ---
    # Replace opening and conclusion
    target_sec21_open = (
        "Các chỉ báo kỹ thuật truyền thống phần lớn hoạt động như các bộ lọc thông thấp nhằm làm mượt chuỗi thời gian giá và giảm bớt các dao động ngắn hạn [4]. Bộ lọc phổ biến nhất là đường trung bình động giản đơn SMA chu kỳ $k$:"
    )
    repl_sec21_open = (
        "Một số chỉ báo kỹ thuật phổ biến, đặc biệt là các đường trung bình động và bộ lọc làm mịn chuỗi giá, có thể được phân tích dưới góc nhìn xử lý tín hiệu thông thấp [4]. Các phép biến đổi này làm giảm một phần dao động ngắn hạn, nhưng có thể khiến tín hiệu phản ứng chậm trước những thay đổi nhanh của giá. Bộ lọc phổ biến nhất là đường trung bình động giản đơn SMA chu kỳ $k$:"
    )
    assert target_sec21_open in ch2, "Target sec21_open not found"
    ch2 = ch2.replace(target_sec21_open, repl_sec21_open)

    target_sec21_end = (
        "Do đó, nền tảng nghiên cứu này đề xuất từ bỏ việc phụ thuộc vào các chỉ báo trễ tuyến tính, chuyển dịch sang các đặc trưng đại diện về giá và hoạt động tick nhằm ghi nhận biến động giá kịp thời hơn."
    )
    repl_sec21_end = (
        "Do đó, nền tảng nghiên cứu này đề xuất giảm sự phụ thuộc vào các chỉ báo làm mịn đơn lẻ, đồng thời bổ sung các đặc trưng đại diện từ $OHLC$ và Tick Volume nhằm ghi nhận biến động giá kịp thời hơn."
    )
    assert target_sec21_end in ch2, "Target sec21_end not found"
    ch2 = ch2.replace(target_sec21_end, repl_sec21_end)

    # --- 2. Section 2.2.1 FVG Refinements ---
    target_fvg = (
        "Trong phạm vi đồ án, **Fair Value Gap (FVG)** được sử dụng như một đặc trưng hình học nhằm nhận diện khoảng cách giá bất thường giữa các nến liên tiếp. Mẫu hình FVG tăng giá được định nghĩa qua một chuỗi ba cây nến liên tiếp $(t-2, t-1, t)$ thỏa mãn:\n\n"
        "$$\\text{Gap}_{\\text{bullish}}(t) = P_{\\text{low}}(t) - P_{\\text{high}}(t-2) > \\epsilon_{\\text{threshold}}$$\n\n"
        "Trong đó $P_{\\text{low}}(t)$ là mức giá thấp nhất của cây nến thứ ba, $P_{\\text{high}}(t-2)$ là mức giá cao nhất của cây nến thứ nhất, và $\\epsilon_{\\text{threshold}}$ là ngưỡng biến động vi mô tối thiểu (được chuẩn hóa theo biến động thực tế ATR). \n\n"
        "*Nguyên tắc đóng dấu thời gian và loại trừ rò rỉ dữ liệu tương lai:* Mẫu hình FVG là một cấu trúc trải dài qua ba cây nến. Do đó, mẫu hình chỉ được xác nhận hoàn tất khi cây nến thứ ba đóng cửa tại thời điểm $t$. Toàn bộ đặc trưng và tín hiệu của mô hình chỉ được tính toán và đóng dấu thời gian tại thời điểm $t$ khi dữ liệu nến thứ ba đã hoàn toàn sẵn có trong lịch sử, loại trừ nguy cơ rò rỉ dữ liệu tương lai. Việc xuất hiện FVG không được xem là bằng chứng trực tiếp về sự thiếu hụt thanh khoản trên toàn thị trường hay hoạt động của một nhóm nhà giao dịch tổ chức cụ thể, mà là một giả thuyết hình học cần được kiểm chứng hiệu quả qua thực nghiệm."
    )

    repl_fvg = (
        "Trong phạm vi đồ án, **Fair Value Gap (FVG)** được sử dụng như một đặc trưng hình học đại diện nhằm nhận diện khoảng cách giá bất thường giữa các nến liên tiếp trên biểu đồ. Mẫu hình FVG được xác định thông qua một chuỗi ba cây nến liên tiếp $(t-2, t-1, t)$ đối với cả hai chiều thị trường:\n\n"
        "- Chiều tăng giá (Bullish FVG):\n"
        "$$\\text{Gap}_{\\text{bullish}}(t) = P_{\\text{low}}(t) - P_{\\text{high}}(t-2) > \\epsilon_{\\text{threshold}}$$\n"
        "đi kèm điều kiện xác nhận nến gia tốc ở giữa: $P_{\\text{close}}(t-1) > P_{\\text{close}}(t-2)$.\n\n"
        "- Chiều giảm giá (Bearish FVG):\n"
        "$$\\text{Gap}_{\\text{bearish}}(t) = P_{\\text{low}}(t-2) - P_{\\text{high}}(t) > \\epsilon_{\\text{threshold}}$$\n"
        "đi kèm điều kiện xác nhận nến gia tốc ở giữa: $P_{\\text{close}}(t-1) < P_{\\text{close}}(t-2)$.\n\n"
        "Trong đó $P_{\\text{low}}(t)$ và $P_{\\text{high}}(t)$ lần lượt là giá thấp nhất và cao nhất của thanh nến thứ $t$. Ngưỡng biến động tối thiểu $\\epsilon_{\\text{threshold}}$ được chuẩn hóa động theo biên độ dao động thực tế trung bình ATR của 14 nến:\n\n"
        "$$\\epsilon_{\\text{threshold}} = \\alpha \\cdot \\text{ATR}_{14}(t)$$\n\n"
        "Trong mã nguồn mô hình thực nghiệm của hệ thống VECTRA, hệ số tỷ lệ được ấn định ở mức $\\alpha = 0{,}15$.\n\n"
        "*Nguyên tắc đóng dấu thời gian và loại trừ rò rỉ dữ liệu tương lai:* Mẫu hình FVG là một cấu trúc trải dài qua ba cây nến liên tiếp. Do đó, mẫu hình chỉ được xác nhận hoàn tất khi cây nến thứ ba đóng cửa tại thời điểm $t$. Toàn bộ véc-tơ đặc trưng và tín hiệu chỉ được tính toán và đóng dấu thời gian tại thời điểm $t$ khi dữ liệu nến thứ ba đã hoàn toàn sẵn có trong lịch sử, loại trừ nguy cơ rò rỉ dữ liệu tương lai.\n\n"
        "*Bản chất đặc trưng hình học đại diện:* FVG được xác định nhất quán là một đặc trưng hình học đại diện trích xuất từ dữ liệu $OHLC$ của nhà môi giới. Việc xuất hiện FVG không được xem là bằng chứng trực tiếp về sự thiếu hụt thanh khoản mỏng trên toàn thị trường hay dấu vết khớp lệnh của các định chế tài chính lớn, mà là một giả thuyết hình học cần được kiểm định hiệu quả thực tế thông qua mô hình học máy thứ cấp."
    )
    assert target_fvg in ch2, "Target FVG not found"
    ch2 = ch2.replace(target_fvg, repl_fvg)

    # --- 3. Section 2.2.2 Wyckoff R_eff Refinements ---
    target_reff = (
        "1. **Tỷ số hoạt động tick trên biên độ giá:**\n"
        "   Đo lường mức độ tương quan giữa tần suất biến động giá và biên độ nến tại thời điểm $t$:\n\n"
        "   $$R_{\\text{eff}}(t) = \\frac{V_t}{\\max(High_t - Low_t, \\epsilon)}$$\n\n"
        "   Trong đó $V_t$ là khối lượng nhịp nhảy giá Tick Volume tại thanh nến thứ $t$, $High_t - Low_t$ là biên độ giá, và $\\epsilon = 10^{-5}$ là hằng số bảo vệ tránh chia cho 0. Một giá trị $R_{\\text{eff}}(t)$ tăng cao đột biến biểu thị tần suất nhảy giá lớn nhưng biên độ di chuyển bị kìm hãm, gợi ý khả năng có sự hấp thụ biến động."
    )

    repl_reff = (
        "1. **Tỷ số hoạt động tick trên biên độ giá:**\n"
        "   Đo lường mức độ tương quan giữa tần suất biến động giá và biên độ nến tại thời điểm $t$:\n\n"
        "   $$R_{\\text{eff}}(t) = \\frac{V_t}{\\max(High_t - Low_t, \\epsilon)}$$\n\n"
        "   Trong đó $V_t$ là khối lượng nhịp nhảy giá Tick Volume tại thanh nến thứ $t$, $High_t - Low_t$ là biên độ giá, và $\\epsilon = 10^{-5}$ là hằng số điều chuẩn số học nhỏ hơn bước giá tối thiểu của XAUUSD trên MetaTrader 5 nhằm bảo vệ giải thuật tránh lỗi chia cho 0 khi nến doji xuất hiện ($High_t = Low_t$). Một giá trị $R_{\\text{eff}}(t)$ tăng cao cho thấy hoạt động tick tương đối lớn so với biên độ giá của nến. Trong phạm vi đồ án, trạng thái này được xem là một đặc trưng đại diện có thể gợi ý sự không tương xứng giữa mức độ hoạt động thị trường và mức dịch chuyển giá; tuy nhiên, nó không phải bằng chứng trực tiếp về khối lượng lệnh đối ứng hoặc hành vi hấp thụ của các tổ chức lớn."
    )
    assert target_reff in ch2, "Target reff not found"
    ch2 = ch2.replace(target_reff, repl_reff)

    # --- 4. Section 2.3 Macro Synchronization, DXY, VIX, Table 2.1 Refinements ---
    target_fisher = (
        "Trong đó $y_{\\text{nominal}}$ là lợi suất danh nghĩa của Trái phiếu Kho bạc Hoa Kỳ kỳ hạn 10 năm US10Y, và $\\pi_{\\text{breakeven}}$ là tỷ lệ lạm phát hòa vốn kỳ vọng 10 năm. Cần lưu ý rằng lợi suất thực quan sát trực tiếp từ trái phiếu chống lạm phát TIPS (DFII10 trên FRED [24]) có thể khác biệt nhất định so với phép tính xấp xỉ qua lạm phát hòa vốn, do lạm phát hòa vốn còn bao hàm phần bù rủi ro lạm phát và phần bù thanh khoản."
    )
    repl_fisher = (
        "Trong đó $y_{\\text{nominal}}$ là lợi suất danh nghĩa của Trái phiếu Kho bạc Hoa Kỳ kỳ hạn 10 năm US10Y (chuỗi DGS10 trên FRED [25]), và $\\pi_{\\text{breakeven}}$ là tỷ lệ lạm phát hòa vốn kỳ vọng 10 năm. Cần lưu ý rằng lợi suất thực quan sát trực tiếp từ trái phiếu chống lạm phát TIPS (chuỗi DFII10 trên FRED [24]) có thể khác biệt nhất định so với phép tính xấp xỉ qua lạm phát hòa vốn, do lạm phát hòa vốn còn bao hàm phần bù rủi ro lạm phát và phần bù thanh khoản."
    )
    assert target_fisher in ch2, "Target fisher not found"
    ch2 = ch2.replace(target_fisher, repl_fisher)

    target_sync = (
        "Trong đó $X_i$ là tỷ suất sinh lợi logarit theo ngày của Vàng ($\\Delta \\ln P_{\\text{Gold}, t}$), và $Y_i$ là mức biến động theo ngày của lợi suất thực ($\\Delta r_{\\text{real}, t}$). Do dữ liệu vĩ mô có tần suất ngày trong khi dữ liệu giao dịch là nến M15, quy trình đồng bộ dữ liệu của đồ án chỉ sử dụng các giá trị vĩ mô đã được công bố và chốt phiên của ngày $T-1$ cho các quyết định trong ngày $T$, ngăn ngừa hoàn toàn nguy cơ đưa thông tin chưa công bố vào tín hiệu giao dịch."
    )
    repl_sync = (
        "Trong đó $X_i$ là tỷ suất sinh lợi logarit theo ngày của Vàng ($\\Delta \\ln P_{\\text{Gold}, t}$), và $Y_i$ là mức biến động theo ngày của lợi suất thực ($\\Delta r_{\\text{real}, t}$). Do dữ liệu vĩ mô có tần suất ngày trong khi dữ liệu giao dịch sử dụng nến M15, nghiên cứu đồng bộ dữ liệu theo thời điểm thông tin thực sự có sẵn. Tại mỗi thời điểm ra quyết định, hệ thống chỉ sử dụng giá trị vĩ mô gần nhất đã được công bố và có thể truy cập tại thời điểm đó. Với các chuỗi dữ liệu ngày, việc ghép dữ liệu phải xét đến ngày nghỉ, múi giờ và thời điểm công bố, nhằm hạn chế nguy cơ sử dụng thông tin chưa sẵn có trong quá khứ. Đây là quy ước đồng bộ dữ liệu của nền tảng, giúp kiểm soát nguy cơ rò rỉ dữ liệu khi kết hợp các chuỗi thời gian có tần suất thu thập khác nhau."
    )
    assert target_sync in ch2, "Target sync not found"
    ch2 = ch2.replace(target_sync, repl_sync)

    target_dxy_vix = (
        "1. **Chỉ số Sức mạnh Đồng USD (DXY):**\n"
        "   Được đo lường thông qua hợp đồng tương lai USDX của Intercontinental Exchange (ICE) [23], tính toán dựa trên mức trung bình nhân gia quyền của đồng USD so với rổ 6 đồng tiền chủ chốt (EUR, JPY, GBP, CAD, SEK, CHF). Do Vàng được định giá bằng USD ($USD/oz$), sự biến động của đồng USD tạo ra hiệu ứng mẫu số định giá, thường tạo áp lực biến động ngược chiều lên giá vàng.\n\n"
        "2. **Chỉ số Biến động Cboe (VIX):**\n"
        "   VIX đo lường mức độ biến động kỳ vọng trong 30 ngày của thị trường chứng khoán Hoa Kỳ thông qua giá quyền chọn chỉ số S&P 500 theo phương pháp luận chính thức của Cboe [22]. VIX không trực tiếp đo lường nỗi sợ hãi của toàn bộ thị trường hay bảo đảm vàng sẽ tăng cùng VIX, nhưng cung cấp một chỉ báo hữu ích về trạng thái bất ổn tài chính.\n\n"
        "*Quy tắc vận hành của hệ thống VECTRA:*\n"
        "Nhằm bảo vệ tài khoản trước các biến động cực đoan, hệ thống thiết lập các ngưỡng vận hành thực nghiệm:\n"
        "- **Chế độ bình ổn (Risk-On):** Khi $VIX \\le 20.0$, thị trường duy trì trạng thái ổn định, hệ thống cho phép thực thi đầy đủ các vị thế kỹ thuật theo tỷ lệ rủi ro chuẩn.\n"
        "- **Chế độ phòng vệ (Risk-Off):** Khi $VIX > 22.5$, thị trường bước vào trạng thái rủi ro biến động cao. Hệ thống tự động kích hoạt chế độ phòng vệ: giảm $50\\%$ quy mô vị thế Mua hoặc tạm dừng mở vị thế mới để tránh các đợt quét biến động mạnh. Các ngưỡng này là quy tắc thiết kế riêng của VECTRA, không phải quy chuẩn cố định của Cboe hay định luật kinh tế phổ quát.\n\n"
        "Bảng 2.1 tổng hợp cơ chế kinh tế và quy tắc tích hợp các biến số vĩ mô trong nền tảng:\n\n"
        "*Bảng 2.1: Cơ chế kinh tế và quy tắc vận hành liên thị trường của nền tảng VECTRA*\n\n"
        "| Biến số vĩ mô | Ký hiệu / Đơn vị | Ý nghĩa lý thuyết kinh tế | Cơ chế tác động kỳ vọng lên Vàng | Quy tắc vận hành của hệ thống VECTRA | Nguồn dữ liệu chính thức |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
        "| **Lợi suất thực 10Y** | TIPS (`DFII10`) / $\%$ | Chi phí cơ hội thực nắm giữ vàng theo phương trình Fisher | Lợi suất thực tăng $\\rightarrow$ Tăng chi phí cơ hội, tạo áp lực giảm giá | TIPS tăng mạnh liên tục $\\rightarrow$ Giới hạn quy mô vị thế Mua | Federal Reserve / FRED [24] |\n"
        "| **Lợi suất danh nghĩa 10Y**| US10Y (`DGS10`) / $\%$ | Lợi suất phi rủi ro tham chiếu của tài sản định chế | Tác động qua kênh kỳ vọng lãi suất và lạm phát | Theo dõi độ dốc đường cong lợi suất | Federal Reserve / FRED |\n"
        "| **Sức mạnh Đồng USD** | DXY (`USDX`) / Điểm | Sức mạnh tương đối của USD so với rổ 6 ngoại tệ | Hiệu ứng mẫu số định giá ($USD/oz$) | DXY tăng mạnh $\\rightarrow$ Giảm quy mô vị thế Mua | Intercontinental Exchange [23] / MT5 |\n"
        "| **Biến động kỳ vọng S&P 500** | VIX / Điểm | Biến động ngụ ý 30 ngày từ quyền chọn S&P 500 | Phản ánh tâm lý bất ổn tài chính | $VIX > 22.5$ $\\rightarrow$ Kích hoạt chế độ phòng vệ Risk-Off | Cboe Global Markets [22] / MT5 |"
    )

    repl_dxy_vix = (
        "1. **Chỉ số Sức mạnh Đồng USD (DXY):**\n"
        "   Trong lý thuyết kinh tế, DXY được đo lường thông qua chuỗi hợp đồng tương lai USDX của Intercontinental Exchange (ICE) [23] hoặc chỉ số tham chiếu USDX tính trên mức trung bình nhân gia quyền của đồng USD so với rổ 6 đồng tiền chủ chốt (EUR, JPY, GBP, CAD, SEK, CHF). Do Vàng được định giá bằng USD ($USD/oz$), sự biến động của đồng USD tạo ra hiệu ứng mẫu số định giá, thường tạo áp lực biến động ngược chiều lên giá vàng. Khi thu thập dữ liệu giao dịch trực tiếp từ thiết bị đầu cuối MetaTrader 5, hệ thống tiếp nhận chuỗi báo giá `USDX` do nhà môi giới cung cấp và xem đây là một biến đại diện phái sinh bám sát chỉ số ICE.\n\n"
        "2. **Chỉ số Biến động Cboe (VIX):**\n"
        "   VIX đo lường mức độ biến động kỳ vọng trong 30 ngày của thị trường chứng khoán Hoa Kỳ thông qua giá quyền chọn chỉ số S&P 500 theo phương pháp luận chính thức của Cboe [22]. VIX không trực tiếp đo lường nỗi sợ hãi của toàn bộ thị trường và giá trị VIX tăng cao không đảm bảo giá vàng sẽ luôn tăng, nhưng cung cấp một chỉ báo hữu ích về trạng thái bất ổn tài chính. Tương tự như DXY, khi vận hành qua cổng kết nối MetaTrader 5, hệ thống tiếp nhận báo giá sản phẩm CFD theo mã `VIX` từ nhà môi giới như một biến đại diện phản ánh biến động.\n\n"
        "*Quy tắc vận hành của hệ thống VECTRA:*\n"
        "Căn cứ trực tiếp theo mã nguồn lớp `MacroRegimeEngine` trong hệ thống (ngưỡng chuyển trạng thái `VIX_RISK_OFF_THRESHOLD = 20.0`):\n"
        "- **Chế độ bình ổn (Risk-On):** Khi $VIX < 20.0$, thị trường duy trì trạng thái ổn định, hệ thống cho phép thực thi đầy đủ các vị thế kỹ thuật theo tỷ lệ rủi ro chuẩn.\n"
        "- **Chế độ phòng vệ (Risk-Off):** Khi $VIX \\ge 20.0$, thị trường bước vào trạng thái rủi ro biến động cao. Phân hệ vĩ mô chuyển trạng thái sang Risk-Off, truyền thông điệp cảnh báo sang Cổng quyết định AI Decision Gate để thắt chặt điều kiện phê duyệt tín hiệu Mua hoặc kích hoạt cơ chế giảm quy mô vị thế nhằm hạn chế rủi ro trước các đợt quét biến động mạnh. Quy tắc này được xây dựng trên ngưỡng nhị phân $20.0$ của hệ thống VECTRA, không tồn tại vùng trung gian mơ hồ.\n\n"
        "Bảng 2.1 tổng hợp cơ chế kinh tế và quy tắc tích hợp các biến số vĩ mô trong nền tảng:\n\n"
        "*Bảng 2.1: Cơ chế kinh tế và quy tắc vận hành liên thị trường của nền tảng VECTRA*\n\n"
        "| Biến số vĩ mô | Ký hiệu / Đơn vị | Ý nghĩa lý thuyết kinh tế | Cơ chế tác động kỳ vọng lên Vàng | Quy tắc vận hành của hệ thống VECTRA | Nguồn dữ liệu tham chiếu |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
        "| **Lợi suất thực 10Y** | TIPS (`DFII10`) / $\%$ | Chi phí cơ hội thực nắm giữ vàng theo phương trình Fisher | Lợi suất thực tăng $\\rightarrow$ Tăng chi phí cơ hội, tạo áp lực giảm giá | TIPS tăng mạnh liên tục $\\rightarrow$ Giới hạn quy mô vị thế Mua | Board of Governors / FRED [24] |\n"
        "| **Lợi suất danh nghĩa 10Y**| US10Y (`DGS10`) / $\%$ | Lợi suất phi rủi ro tham chiếu của tài sản định chế | Tác động qua kênh kỳ vọng lãi suất và lạm phát | Theo dõi độ dốc đường cong lợi suất | Board of Governors / FRED [25] |\n"
        "| **Sức mạnh Đồng USD** | DXY (`USDX`) / Điểm | Sức mạnh tương đối của USD so với rổ 6 ngoại tệ | Hiệu ứng mẫu số định giá ($USD/oz$) | DXY tăng mạnh $\\rightarrow$ Giảm quy mô vị thế Mua | ICE [23] / Báo giá môi giới MT5 |\n"
        "| **Biến động kỳ vọng S&P 500** | VIX / Điểm | Biến động ngụ ý 30 ngày từ quyền chọn S&P 500 | Phản ánh tâm lý bất ổn tài chính | $VIX \\ge 20.0$ $\\rightarrow$ Kích hoạt chế độ phòng vệ Risk-Off | Cboe [22] / Báo giá môi giới MT5 |"
    )
    assert target_dxy_vix in ch2, "Target dxy_vix not found"
    ch2 = ch2.replace(target_dxy_vix, repl_dxy_vix)

    # --- 5. Section 2.4.2 Triple-Barrier Buy & Sell, Embargoing Refinements ---
    target_tb = (
        "1. **Mô hình Sơ cấp:**\n"
        "   Được thiết kế để đạt độ nhạy cao, tạo ra chuỗi tín hiệu định hướng:\n\n"
        "   $$y_{\\text{primary}} \\in \\{-1, 0, 1\\}$$\n\n"
        "2. **Mô hình Thứ cấp:**\n"
        "   Mô hình học máy không tham gia quyết định hướng lệnh (không quyết định Buy hay Sell). Nhiệm vụ của nó là trả lời câu hỏi nhị phân: *\"Nếu tuân theo tín hiệu của Mô hình sơ cấp tại thời điểm hiện tại, xác suất lệnh đó đạt mức lợi nhuận mục tiêu trước khi chạm mức dừng lỗ là bao nhiêu?\"*\n\n"
        "   $$z_{\\text{meta}} \\in \\{0, 1\\}$$\n\n"
        "   Trong đó, nhãn mục tiêu $z$ được xác định dựa trên phương pháp Ba rào chắn (Triple-Barrier Method) [8]:\n"
        "   - Rào chắn chốt lời: $P_{\\text{entry}} + \\Delta P_{\\text{TP}}$.\n"
        "   - Rào chắn dừng lỗ: $P_{\\text{entry}} - \\Delta P_{\\text{SL}}$.\n"
        "   - **Rào chắn thời gian:** Giới hạn tối đa $H = 20$ thanh nến M15 (tương đương 5 giờ giao dịch), hoàn toàn thống nhất với quy trình thực nghiệm ở Chương 4.\n"
        "   - *Quy tắc thực thi bi quan:* Trong trường hợp giá dao động mạnh khiến cả rào chắn TP và SL cùng bị kích hoạt trong cùng một thanh nến, thuật toán luôn ấn định nhãn $z = 0$ (coi như chạm SL trước) nhằm loại bỏ kết quả lợi nhuận ảo.\n"
        "   - *Kỹ thuật Purging & Embargoing:* Các quan sát có khoảng thời gian mở lệnh vắt ngang qua ranh giới giữa tập huấn luyện và kiểm định được loại bỏ để ngăn ngừa rò rỉ thông tin tương lai [8]."
    )

    repl_tb = (
        "1. **Mô hình Sơ cấp:**\n"
        "   Được thiết kế để đạt độ nhạy cao, tạo ra chuỗi tín hiệu định hướng vị thế:\n\n"
        "   $$y_{\\text{primary}} \\in \\{-1, 0, 1\\}$$\n\n"
        "   Trong đó $+1$ đại diện cho tín hiệu Mua (Buy), $-1$ đại diện cho tín hiệu Bán (Sell), và $0$ là trạng thái giữ tiền mặt (Neutral).\n\n"
        "2. **Mô hình Thứ cấp:**\n"
        "   Mô hình học máy không tham gia quyết định hướng lệnh. Nhiệm vụ của nó là trả lời câu hỏi nhị phân: *\"Nếu tuân theo tín hiệu của Mô hình sơ cấp tại thời điểm hiện tại, xác suất lệnh đó đạt mức lợi nhuận mục tiêu trước khi chạm mức dừng lỗ là bao nhiêu?\"*\n\n"
        "   $$z_{\\text{meta}} \\in \\{0, 1\\}$$\n\n"
        "   Để định nghĩa chính xác các rào chắn giá cho cả hai chiều giao dịch, gọi $s_t \\in \\{-1, +1\\}$ là biến chỉ báo hướng của tín hiệu sơ cấp được chấp thuận ($s_t = +1$ đối với lệnh Mua và $s_t = -1$ đối với lệnh Bán). Khi đó, các mức rào chắn theo khoảng cách giá dương $\\Delta P_{\\text{TP}} > 0$ và $\\Delta P_{\\text{SL}} > 0$ được xác định tổng quát dựa trên phương pháp Ba rào chắn (Triple-Barrier Method) [8]:\n"
        "   - **Rào chắn chốt lời (Upper/Lower Take-Profit Barrier):**\n"
        "     $$P_{\\text{TP}} = P_{\\text{entry}} + s_t \\Delta P_{\\text{TP}}$$\n"
        "   - **Rào chắn dừng lỗ (Stop-Loss Barrier):**\n"
        "     $$P_{\\text{SL}} = P_{\\text{entry}} - s_t \\Delta P_{\\text{SL}}$$\n"
        "   Công thức này đảm bảo đảo chiều đối xứng: khi $s_t = +1$ (Mua), $P_{\\text{TP}} > P_{\\text{entry}}$ và $P_{\\text{SL}} < P_{\\text{entry}}$; khi $s_t = -1$ (Bán), $P_{\\text{TP}} < P_{\\text{entry}}$ và $P_{\\text{SL}} > P_{\\text{entry}}$. Trong mô hình thực nghiệm của VECTRA, khoảng dừng lỗ được ấn định $\\Delta P_{\\text{SL}} = 1{,}5 \\cdot \\text{ATR}_{14}(t)$ và khoảng chốt lời mục tiêu được xác định theo tỷ số rủi ro/lợi nhuận: $\\Delta P_{\\text{TP}} = 1{,}5 \\cdot \\Delta P_{\\text{SL}}$.\n"
        "   - **Rào chắn thời gian (Vertical Barrier):** Giới hạn thời gian nắm giữ tối đa $H = 20$ thanh nến M15 (tương đương 20 nến giao dịch liên tục trên sàn, tức 5 giờ giao dịch thực tế, không tính thời gian thị trường đóng cửa cuối tuần), hoàn toàn thống nhất với mã nguồn kiểm thử và kết quả thực nghiệm tại Chương 4.\n"
        "   - *Quy tắc thực thi bi quan:* Trong trường hợp giá dao động cực đoan khiến cả hai rào chắn TP và SL cùng bị xuyên thủng trong phạm vi một thanh nến, thuật toán luôn ấn định nhãn bi quan $z = 0$ (coi như chạm SL trước) nhằm loại bỏ triệt để kết quả lợi nhuận ảo.\n"
        "   - *Kỹ thuật Purging & Embargoing:* Kỹ thuật thanh lọc mẫu (Purging) loại bỏ các quan sát có khoảng thời gian mở vị thế vắt ngang qua ranh giới giữa tập huấn luyện và kiểm định. Đồng thời, kỹ thuật cách ly an toàn (Embargoing) thiết lập một vùng đệm ngắt quãng $h_{\\text{embargo}} = 5$ thanh nến (tương đương 1,25 giờ giao dịch) sau mỗi sự kiện đóng lệnh trước khi thu thập mẫu huấn luyện tiếp theo (như được cụ thể hóa trong quy trình thực nghiệm ở Mục 4.5), ngăn ngừa hiện tượng rò rỉ thông tin tương lai và giảm thiểu tương quan chuỗi giữa các giao dịch kế tiếp [8]."
    )
    assert target_tb in ch2, "Target tb not found"
    ch2 = ch2.replace(target_tb, repl_tb)

    # --- 6. References Update ---
    target_refs_22_24 = (
        "[22] Cboe Exchange, Inc., \"Cboe Volatility Index (VIX) White Paper: Methodology and Calculation,\" Chicago, IL, USA: Cboe Global Markets, 2019. [Online]. Available: https://www.cboe.com/micro/vix/vixwhite.pdf.\n\n"
        "[23] Intercontinental Exchange (ICE), \"U.S. Dollar Index (USDX) Contracts Specification & Methodology,\" ICE Futures U.S., 2023. [Online]. Available: https://www.theice.com/products/194/US-Dollar-Index-Futures.\n\n"
        "[24] Federal Reserve Bank of St. Louis, \"10-Year Treasury Inflation-Indexed Security, Constant Maturity (DFII10),\" *Federal Reserve Economic Data (FRED)*, 2024. [Online]. Available: https://fred.stlouisfed.org/series/DFII10."
    )

    repl_refs_22_25 = (
        "[22] Cboe Global Markets, \"Volatility Index Methodology: Cboe Volatility Index,\" 2019. [Online]. Available: https://cdn.cboe.com/resources/indices/Volatility_Index_Methodology_Cboe_Volatility_Index.pdf. [Accessed: Oct. 27, 2026].\n\n"
        "[23] Intercontinental Exchange, \"U.S. Dollar Index Futures,\" 2023. [Online]. Available: https://www.ice.com/products/194/US-Dollar-Index-USDX-Futures. [Accessed: Oct. 27, 2026].\n\n"
        "[24] Board of Governors of the Federal Reserve System, \"Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity, Quoted on an Investment Basis, Inflation-Indexed (DFII10),\" FRED, Federal Reserve Bank of St. Louis, 2024. [Online]. Available: https://fred.stlouisfed.org/series/DFII10. [Accessed: Oct. 27, 2026].\n\n"
        "[25] Board of Governors of the Federal Reserve System, \"Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity, Quoted on an Investment Basis (DGS10),\" FRED, Federal Reserve Bank of St. Louis, 2024. [Online]. Available: https://fred.stlouisfed.org/series/DGS10. [Accessed: Oct. 27, 2026]."
    )
    assert target_refs_22_24 in refs, "Target refs 22-24 not found"
    refs = refs.replace(target_refs_22_24, repl_refs_22_25)

    with open(ch2_path, "w", encoding="utf-8") as f:
        f.write(ch2)
    print("Updated Chapter 2 successfully.")

    with open(ref_path, "w", encoding="utf-8") as f:
        f.write(refs)
    print("Updated Bibliography successfully.")

if __name__ == "__main__":
    main()
