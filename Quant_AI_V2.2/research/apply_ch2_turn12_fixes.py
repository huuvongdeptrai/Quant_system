# -*- coding: utf-8 -*-
"""
Script to apply Chapter 2 final academic refinements (Turn 12):
1. Triple-Barrier parameters: unify with Chapter 4 and Figure 2.3:
   - Delta P_SL = 1.0 * ATR_14(t)
   - Delta P_TP = 2.5 * ATR_14(t) (Target RR = 2.5)
   - Vertical Barrier H = 20 M15 bars expiration rule: closed and assigned defensive label z = 0.
2. Section 2.2.1 FVG: present middle candle direction (Close_t-1 > Close_t-2) as design choice of VECTRA evaluated empirically, not universal fact.
3. Section 2.2.2 R_eff: detail epsilon numerical guard (10^-4 / 10^-5 relative to tick size of XAUUSD), zero-range candle handling, and representative tick activity phrasing.
4. Section 2.3.2 DXY & VIX: qualify broker quote on MT5 as proxy, note correspondence with benchmark indices requires verification for direct comparison.
5. Section 2.2.1 BVC [18] & Lee-Ready [19]: clarify [18] JFE 2016 theoretical role, and [19] reference principle without asserting full tick/quote data execution.
6. Section 2.5: update closing latency sentence regarding HFT microsecond vs M15 unblocked processing.
"""
import re
import sys

def main():
    ch2_path = "docs/thesis/chuong_2_co_so_ly_thuyet.md"

    with open(ch2_path, "r", encoding="utf-8") as f:
        ch2 = f.read()

    # --- 1. Section 2.2.1: BVC [18] & Lee-Ready [19] clarification ---
    target_bvc = (
        "Nghiên cứu của Easley, López de Prado và O’Hara (2016) về phân loại khối lượng gộp BVC [18] cùng quy tắc suy luận hướng lệnh Tick Test của Lee và Ready (1991) [19] cung cấp cơ sở lý luận về việc trích xuất thông tin từ dữ liệu giá và khối lượng. Tuy nhiên, khối lượng Tick Volume từ MT5 không phản ánh toàn bộ khối lượng giao dịch thật của thị trường; do đó, biến `cvd_proxy` được xây dựng như một đặc trưng dòng tiền đại diện do đồ án đề xuất, có tham khảo các nguyên lý phân loại hướng giao dịch."
    )
    repl_bvc = (
        "Nghiên cứu của Easley, López de Prado và O’Hara (2016) về phân loại khối lượng gộp BVC [18] cùng quy tắc suy luận hướng lệnh Tick Test của Lee và Ready (1991) [19] cung cấp cơ sở lý luận tham khảo về việc trích xuất thông tin từ dữ liệu giá và khối lượng. Tuy nhiên, do nền tảng bán lẻ MetaTrader 5 không cung cấp dữ liệu khớp lệnh từng giao dịch (trade-by-trade) hay báo giá đa tầng (quote-by-quote), biến `cvd_proxy` được xây dựng như một đặc trưng dòng tiền đại diện do đồ án đề xuất, dựa trên nguyên lý tương quan giữa biến động giá và Tick Volume, không phải là sự áp dụng nguyên vẹn của thuật toán Lee–Ready trên dữ liệu giao dịch thực tế."
    )
    assert target_bvc in ch2, "target_bvc not found"
    ch2 = ch2.replace(target_bvc, repl_bvc)

    # --- 2. Section 2.2.1: FVG middle candle condition & geometric definition ---
    target_fvg_nature = (
        "*Bản chất đặc trưng hình học đại diện:* FVG được xác định nhất quán là một đặc trưng hình học đại diện trích xuất từ dữ liệu $OHLC$ của nhà môi giới. Việc xuất hiện FVG không được xem là bằng chứng trực tiếp về sự thiếu hụt thanh khoản mỏng trên toàn thị trường hay dấu vết khớp lệnh của các định chế tài chính lớn, mà là một giả thuyết hình học cần được kiểm định hiệu quả thực tế thông qua mô hình học máy thứ cấp."
    )
    repl_fvg_nature = (
        "*Bản chất đặc trưng hình học đại diện và tiêu chí nhận diện:* Trong phạm vi đồ án, FVG được định nghĩa theo điều kiện hình học giữa giá cao nhất của nến thứ nhất và giá thấp nhất của nến thứ ba đối với chiều tăng; chiều giảm được xác định theo điều kiện đối xứng. Ngoài điều kiện khoảng cách giá tối thiểu $\\epsilon_{\\text{threshold}} = \\alpha \\cdot \\text{ATR}_{14}(t)$ với $\\alpha = 0{,}15$, hệ thống sử dụng quan hệ giữa giá đóng cửa của nến giữa và nến thứ nhất như một tiêu chí xác nhận hướng. Đây là quy tắc nhận diện do đồ án lựa chọn và được đánh giá bằng thực nghiệm, không phải bằng chứng trực tiếp về sự thiếu hụt thanh khoản trên toàn thị trường hay dấu vết khớp lệnh của các tổ chức lớn."
    )
    assert target_fvg_nature in ch2, "target_fvg_nature not found"
    ch2 = ch2.replace(target_fvg_nature, repl_fvg_nature)

    # --- 3. Section 2.2.2: R_eff numerical protection and phrasing ---
    target_reff = (
        "1. **Tỷ số hoạt động tick trên biên độ giá:**\n"
        "   Đo lường mức độ tương quan giữa tần suất biến động giá và biên độ nến tại thời điểm $t$:\n\n"
        "   $$R_{\\text{eff}}(t) = \\frac{V_t}{\\max(High_t - Low_t, \\epsilon)}$$\n\n"
        "   Trong đó $V_t$ là khối lượng nhịp nhảy giá Tick Volume tại thanh nến thứ $t$, $High_t - Low_t$ là biên độ giá, và $\\epsilon = 10^{-5}$ là hằng số điều chuẩn số học nhỏ hơn bước giá tối thiểu của XAUUSD trên MetaTrader 5 nhằm bảo vệ giải thuật tránh lỗi chia cho 0 khi nến doji xuất hiện ($High_t = Low_t$). Một giá trị $R_{\\text{eff}}(t)$ tăng cao cho thấy hoạt động tick tương đối lớn so với biên độ giá của nến. Trong phạm vi đồ án, trạng thái này được xem là một đặc trưng đại diện có thể gợi ý sự không tương xứng giữa mức độ hoạt động thị trường và mức dịch chuyển giá; tuy nhiên, nó không phải bằng chứng trực tiếp về khối lượng lệnh đối ứng hoặc hành vi hấp thụ của các tổ chức lớn."
    )
    repl_reff = (
        "1. **Tỷ số hoạt động tick trên biên độ giá:**\n"
        "   Đo lường mức độ tương quan giữa tần suất biến động giá và biên độ nến tại thời điểm $t$:\n\n"
        "   $$R_{\\text{eff}}(t) = \\frac{V_t}{\\max(High_t - Low_t, \\epsilon)}$$\n\n"
        "   Trong đó $V_t$ là khối lượng nhịp nhảy giá Tick Volume tại thanh nến thứ $t$, $High_t - Low_t$ là biên độ giá của nến, và $\\epsilon = 10^{-4}$ là hằng số bảo vệ mẫu số được lựa chọn phù hợp với đơn vị giá và bước giá thực tế của XAUUSD trên MetaTrader 5 (bước giá $0{,}01$) nhằm tránh phép chia cho giá trị bằng không hoặc quá nhỏ khi xuất hiện nến doji ($High_t = Low_t$). Các trường hợp nến có biên độ bằng 0 được xử lý theo quy tắc số học này để hạn chế giá trị ngoại lệ đột biến. Chỉ số $R_{\\text{eff}}$ được sử dụng như một đặc trưng đại diện cho hoạt động tick tương đối so với biên độ giá; trạng thái này có thể gợi ý sự không tương xứng giữa mức độ hoạt động thị trường và mức dịch chuyển giá, nhưng không phải phép đo trực tiếp khối lượng giao dịch thực hay hành vi hấp thụ của các tổ chức lớn."
    )
    assert target_reff in ch2, "target_reff not found"
    ch2 = ch2.replace(target_reff, repl_reff)

    # --- 4. Section 2.3.2: DXY & VIX broker quote qualification ---
    target_dxy_vix = (
        "1. **Chỉ số Sức mạnh Đồng USD (DXY):**\n"
        "   Trong lý thuyết kinh tế, DXY được đo lường thông qua chuỗi hợp đồng tương lai USDX của Intercontinental Exchange (ICE) [23] hoặc chỉ số tham chiếu USDX tính trên mức trung bình nhân gia quyền của đồng USD so với rổ 6 đồng tiền chủ chốt (EUR, JPY, GBP, CAD, SEK, CHF). Do Vàng được định giá bằng USD ($USD/oz$), sự biến động của đồng USD tạo ra hiệu ứng mẫu số định giá, thường tạo áp lực biến động ngược chiều lên giá vàng. Khi thu thập dữ liệu giao dịch trực tiếp từ thiết bị đầu cuối MetaTrader 5, hệ thống tiếp nhận chuỗi báo giá `USDX` do nhà môi giới cung cấp và xem đây là một biến đại diện phái sinh bám sát chỉ số ICE.\n\n"
        "2. **Chỉ số Biến động Cboe (VIX):**\n"
        "   VIX đo lường mức độ biến động kỳ vọng trong 30 ngày của thị trường chứng khoán Hoa Kỳ thông qua giá quyền chọn chỉ số S&P 500 theo phương pháp luận chính thức của Cboe [22]. VIX không trực tiếp đo lường nỗi sợ hãi của toàn bộ thị trường và giá trị VIX tăng cao không đảm bảo giá vàng sẽ luôn tăng, nhưng cung cấp một chỉ báo hữu ích về trạng thái bất ổn tài chính. Tương tự như DXY, khi vận hành qua cổng kết nối MetaTrader 5, hệ thống tiếp nhận báo giá sản phẩm CFD theo mã `VIX` từ nhà môi giới như một biến đại diện phản ánh biến động."
    )
    repl_dxy_vix = (
        "1. **Chỉ số Sức mạnh Đồng USD (DXY):**\n"
        "   Trong lý thuyết kinh tế, DXY được đo lường thông qua chuỗi hợp đồng tương lai USDX của Intercontinental Exchange (ICE) [23] hoặc chỉ số tham chiếu USDX tính trên mức trung bình nhân gia quyền của đồng USD so với rổ 6 đồng tiền chủ chốt (EUR, JPY, GBP, CAD, SEK, CHF). Do Vàng được định giá bằng USD ($USD/oz$), sự biến động của đồng USD tạo ra hiệu ứng mẫu số định giá, thường tạo áp lực biến động ngược chiều lên giá vàng. Khi thu thập dữ liệu từ MetaTrader 5, hệ thống sử dụng chuỗi báo giá `USDX` do nhà môi giới cung cấp làm biến đại diện cho sức mạnh đồng USD. Chuỗi này được sử dụng theo đặc tính dữ liệu của nguồn cung cấp; mức độ tương ứng với chỉ số tham chiếu chính thức cần được xác minh nếu được dùng cho các phân tích định lượng so sánh trực tiếp.\n\n"
        "2. **Chỉ số Biến động Cboe (VIX):**\n"
        "   VIX đo lường mức độ biến động kỳ vọng trong 30 ngày của thị trường chứng khoán Hoa Kỳ thông qua giá quyền chọn chỉ số S&P 500 theo phương pháp luận chính thức của Cboe [22]. VIX không trực tiếp đo lường nỗi sợ hãi của toàn bộ thị trường và giá trị VIX tăng cao không đảm bảo giá vàng sẽ luôn tăng. Khi thu thập dữ liệu từ MetaTrader 5, hệ thống sử dụng sản phẩm CFD theo mã `VIX` do nhà môi giới cung cấp làm biến đại diện cho trạng thái biến động kỳ vọng. Mức độ tương ứng giữa báo giá CFD của nhà môi giới và chỉ số VIX cơ sở của Cboe cần được lưu ý khi diễn giải các trạng thái rủi ro."
    )
    assert target_dxy_vix in ch2, "target_dxy_vix not found"
    ch2 = ch2.replace(target_dxy_vix, repl_dxy_vix)

    # --- 5. Section 2.4.2: Triple-Barrier parameters & Expiration rule ---
    target_tb_params = (
        "   Công thức này đảm bảo đảo chiều đối xứng: khi $s_t = +1$ (Mua), $P_{\\text{TP}} > P_{\\text{entry}}$ và $P_{\\text{SL}} < P_{\\text{entry}}$; khi $s_t = -1$ (Bán), $P_{\\text{TP}} < P_{\\text{entry}}$ và $P_{\\text{SL}} > P_{\\text{entry}}$. Trong mô hình thực nghiệm của VECTRA, khoảng dừng lỗ được ấn định $\\Delta P_{\\text{SL}} = 1{,}5 \\cdot \\text{ATR}_{14}(t)$ và khoảng chốt lời mục tiêu được xác định theo tỷ số rủi ro/lợi nhuận: $\\Delta P_{\\text{TP}} = 1{,}5 \\cdot \\Delta P_{\\text{SL}}$.\n"
        "   - **Rào chắn thời gian (Vertical Barrier):** Giới hạn thời gian nắm giữ tối đa $H = 20$ thanh nến M15 (tương đương 20 nến giao dịch liên tục trên sàn, tức 5 giờ giao dịch thực tế, không tính thời gian thị trường đóng cửa cuối tuần), hoàn toàn thống nhất với mã nguồn kiểm thử và kết quả thực nghiệm tại Chương 4.\n"
        "   - *Quy tắc thực thi bi quan:* Trong trường hợp giá dao động cực đoan khiến cả hai rào chắn TP và SL cùng bị xuyên thủng trong phạm vi một thanh nến, thuật toán luôn ấn định nhãn bi quan $z = 0$ (coi như chạm SL trước) nhằm loại bỏ triệt để kết quả lợi nhuận ảo."
    )
    repl_tb_params = (
        "   Công thức này đảm bảo đảo chiều đối xứng: khi $s_t = +1$ (Mua), $P_{\\text{TP}} > P_{\\text{entry}}$ và $P_{\\text{SL}} < P_{\\text{entry}}$; khi $s_t = -1$ (Bán), $P_{\\text{TP}} < P_{\\text{entry}}$ và $P_{\\text{SL}} > P_{\\text{entry}}$. Trong quy trình gán nhãn thực nghiệm của mô hình Meta-Labeling (nhất quán với Mục 4.5 và Hình 2.3), khoảng dừng lỗ được ấn định $\\Delta P_{\\text{SL}} = 1{,}0 \\cdot \\text{ATR}_{14}(t)$ và khoảng chốt lời mục tiêu được thiết lập $\\Delta P_{\\text{TP}} = 2{,}5 \\cdot \\text{ATR}_{14}(t)$ (tương ứng tỷ số lợi nhuận trên rủi ro mục tiêu là $2{,}5$).\n"
        "   - **Rào chắn thời gian (Vertical Barrier):** Giới hạn thời gian nắm giữ tối đa $H = 20$ thanh nến M15 (tương đương 20 nến giao dịch liên tục trên sàn, tức 5 giờ giao dịch thực tế, không tính thời gian thị trường đóng cửa cuối tuần). Khi vị thế vượt quá thời hạn $H = 20$ nến mà chưa chạm cả rào chắn TP lẫn SL, vị thế bị đóng cưỡng bức theo thời gian và được gán nhãn quy ước phòng thủ $z = 0$ (không đạt biên độ mục tiêu trong khung thời gian kỳ vọng).\n"
        "   - *Quy tắc thực thi bi quan:* Trong trường hợp giá dao động cực đoan khiến cả hai rào chắn TP và SL cùng bị xuyên thủng trong phạm vi một thanh nến, thuật toán luôn ấn định nhãn bi quan $z = 0$ (coi như chạm SL trước) nhằm loại bỏ triệt để kết quả lợi nhuận ảo."
    )
    assert target_tb_params in ch2, "target_tb_params not found"
    ch2 = ch2.replace(target_tb_params, repl_tb_params)

    # --- 6. Section 2.5: Event-Driven architecture latency closing sentence ---
    target_eda_end = (
        "Khác với môi trường giao dịch tần suất siêu cao HFT đòi hỏi hạ tầng vi mô ở cấp độ micro-giây [20], mục tiêu kiến trúc của VECTRA là bảo đảm tính phân tách không chặn giữa phân hệ AI và luồng thị trường, duy trì độ trễ xử lý nội bộ ở mức mili-giây thấp để không bỏ lỡ các nhịp nến M15. Khả năng duy trì độ trễ này được kiểm tra bằng các kịch bản đo lường thực nghiệm riêng biệt, thay vì chỉ suy luận thuần túy từ sơ đồ thiết kế."
    )
    repl_eda_end = (
        "Khác với các môi trường giao dịch tần suất siêu cao HFT có mức độ cạnh tranh ở thang thời gian micro-giây [20], nền tảng VECTRA tập trung vào khả năng phân tách không chặn giữa phân hệ AI và luồng xử lý thị trường. Mục tiêu thiết kế là duy trì độ trễ nội bộ thấp, bảo đảm việc phân tích và kiểm tra rủi ro không gây trì hoãn không cần thiết đối với quá trình xử lý tín hiệu. Hiệu quả này được đánh giá bằng các phép đo thực nghiệm riêng biệt."
    )
    assert target_eda_end in ch2, "target_eda_end not found"
    ch2 = ch2.replace(target_eda_end, repl_eda_end)

    with open(ch2_path, "w", encoding="utf-8") as f:
        f.write(ch2)
    print("Chapter 2 updated with all Turn 12 refinements.")

if __name__ == "__main__":
    main()
