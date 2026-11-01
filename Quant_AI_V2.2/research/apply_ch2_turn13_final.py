# -*- coding: utf-8 -*-
"""
Script to apply Chapter 2 final academic refinements (Turn 13):
1. Section 2.2.1: EMH and Limit Order Book logic adjustment.
2. Section 2.2.1: FVG diagram middle candle note and caption ('Khoảng cách giá Fair Value Gap').
3. Section 2.2.2: R_eff epsilon numerical guard, zero-range candle handling, and representative tick activity phrasing.
4. Section 2.4.2: Triple-Barrier - Clarify VECTRA design convention for z=0 expiration vs general method variations.
5. Section 2.5: MarketDataEvent: differentiate tick update events vs bar close events.
6. Synchronize Table of Contents (muc_luc_chinh_thuc.md) for Hình 2.1 caption.
"""
import re
import sys

def main():
    ch2_path = "docs/thesis/chuong_2_co_so_ly_thuyet.md"
    ml_path = "docs/thesis/muc_luc_chinh_thuc.md"

    with open(ch2_path, "r", encoding="utf-8") as f:
        ch2 = f.read()

    with open(ml_path, "r", encoding="utf-8") as f:
        ml = f.read()

    # --- 1. Section 2.2.1: EMH and Limit Order Book logic ---
    target_emh = (
        "Cấu trúc vi mô thị trường tài chính là phân ngành kinh tế học tài chính nghiên cứu các cơ chế trao đổi, khớp lệnh và hình thành giá trong điều kiện ma sát thực tế [6]. Khác với các giả định lý tưởng của Thuyết thị trường hiệu quả EMH, các giao dịch trên thị trường tài chính diễn ra thông qua tương tác giữa các lệnh giới hạn và lệnh thị trường trong sổ lệnh [7]."
    )
    repl_emh = (
        "Cấu trúc vi mô thị trường tài chính là phân ngành kinh tế học tài chính nghiên cứu các cơ chế trao đổi, khớp lệnh và hình thành giá trong điều kiện ma sát thực tế [6]. Lý thuyết cấu trúc vi mô thị trường bổ sung góc nhìn về cơ chế hình thành giá bằng cách nghiên cứu tương tác giữa các lệnh giới hạn, lệnh thị trường và những ma sát trong quá trình giao dịch [6], [7]. Trong khi đó, Giả thuyết thị trường hiệu quả EMH tập trung vào mức độ thông tin được phản ánh trong giá tài sản. Hai cách tiếp cận này có thể được sử dụng bổ trợ cho nhau khi phân tích hành vi giá trong thị trường tài chính."
    )
    assert target_emh in ch2, "target_emh not found"
    ch2 = ch2.replace(target_emh, repl_emh)

    # --- 2. Section 2.2.1: FVG diagram middle candle & caption ---
    target_fvg_diag = (
        "(Nến t-1 nằm giữa có biên độ dao động mạnh tạo khoảng hở giữa nến t-2 và nến t)"
    )
    repl_fvg_diag = (
        "(Nến t-1 nằm giữa hai nến biên và đáp ứng điều kiện xác nhận hướng được quy định trong mô hình)"
    )
    assert target_fvg_diag in ch2, "target_fvg_diag not found"
    ch2 = ch2.replace(target_fvg_diag, repl_fvg_diag)

    target_fvg_cap1 = "![Hình 2.1: Sơ đồ hình học vi cấu trúc của Khoảng trống thanh khoản Fair Value Gap và cơ chế tái kiểm định](images/hinh_2_1_fvg_imbalance.png)"
    repl_fvg_cap1 = "![Hình 2.1: Sơ đồ hình học vi cấu trúc của Khoảng cách giá Fair Value Gap và cơ chế kiểm định lại](images/hinh_2_1_fvg_imbalance.png)"
    assert target_fvg_cap1 in ch2, "target_fvg_cap1 not found"
    ch2 = ch2.replace(target_fvg_cap1, repl_fvg_cap1)

    target_fvg_cap2 = "*Hình 2.1: Sơ đồ hình học vi cấu trúc của Khoảng trống thanh khoản Fair Value Gap và cơ chế tái kiểm định của dòng tiền*"
    repl_fvg_cap2 = "*Hình 2.1: Sơ đồ hình học vi cấu trúc của Khoảng cách giá Fair Value Gap và cơ chế kiểm định lại*"
    assert target_fvg_cap2 in ch2, "target_fvg_cap2 not found"
    ch2 = ch2.replace(target_fvg_cap2, repl_fvg_cap2)

    # Update muc_luc_chinh_thuc.md
    target_ml_fig21 = "- **Hình 2.1:** Sơ đồ hình học vi cấu trúc của Khoảng trống thanh khoản Fair Value Gap và cơ chế tái kiểm định"
    repl_ml_fig21 = "- **Hình 2.1:** Sơ đồ hình học vi cấu trúc của Khoảng cách giá Fair Value Gap và cơ chế kiểm định lại"
    if target_ml_fig21 in ml:
        ml = ml.replace(target_ml_fig21, repl_ml_fig21)
        with open(ml_path, "w", encoding="utf-8") as f:
            f.write(ml)
        print("Updated muc_luc_chinh_thuc.md successfully.")

    # --- 3. Section 2.2.2: R_eff numerical protection and phrasing ---
    target_reff = (
        "1. **Tỷ số hoạt động tick trên biên độ giá:**\n"
        "   Đo lường mức độ tương quan giữa tần suất biến động giá và biên độ nến tại thời điểm $t$:\n\n"
        "   $$R_{\\text{eff}}(t) = \\frac{V_t}{\\max(High_t - Low_t, \\epsilon)}$$\n\n"
        "   Trong đó $V_t$ là khối lượng nhịp nhảy giá Tick Volume tại thanh nến thứ $t$, $High_t - Low_t$ là biên độ giá của nến, và $\\epsilon = 10^{-4}$ là hằng số bảo vệ mẫu số được lựa chọn phù hợp với đơn vị giá và bước giá thực tế của XAUUSD trên MetaTrader 5 (bước giá $0{,}01$) nhằm tránh phép chia cho giá trị bằng không hoặc quá nhỏ khi xuất hiện nến doji ($High_t = Low_t$). Các trường hợp nến có biên độ bằng 0 được xử lý theo quy tắc số học này để hạn chế giá trị ngoại lệ đột biến. Chỉ số $R_{\\text{eff}}$ được sử dụng như một đặc trưng đại diện cho hoạt động tick tương đối so với biên độ giá; trạng thái này có thể gợi ý sự không tương xứng giữa mức độ hoạt động thị trường và mức dịch chuyển giá, nhưng không phải phép đo trực tiếp khối lượng giao dịch thực hay hành vi hấp thụ của các tổ chức lớn."
    )
    repl_reff = (
        "1. **Tỷ số hoạt động tick trên biên độ giá:**\n"
        "   Đo lường mức độ tương quan giữa tần suất biến động giá và biên độ nến tại thời điểm $t$:\n\n"
        "   $$R_{\\text{eff}}(t) = \\frac{V_t}{\\max(High_t - Low_t, \\epsilon)}$$\n\n"
        "   Trong đó, $V_t$ là khối lượng nhịp nhảy giá Tick Volume của nến thứ $t$, còn $High_t - Low_t$ là biên độ giá. Hằng số $\\epsilon$ được sử dụng để tránh phép chia cho 0 khi tính toán. Tuy nhiên, đối với các nến có biên độ bằng 0, việc sử dụng mẫu số rất nhỏ có thể tạo ra giá trị $R_{\\text{eff}}$ bất thường. Do đó, hệ thống cần có quy tắc xử lý riêng cho các trường hợp này, chẳng hạn sử dụng bước giá tối thiểu làm giới hạn mẫu số hoặc loại các mẫu không phù hợp khỏi phép tính. Chỉ số $R_{\\text{eff}}$ được sử dụng như một đặc trưng đại diện cho hoạt động tick tương đối so với biên độ giá, không phải phép đo trực tiếp khối lượng giao dịch thực hay hành vi hấp thụ của các tổ chức lớn."
    )
    assert target_reff in ch2, "target_reff not found"
    ch2 = ch2.replace(target_reff, repl_reff)

    # --- 4. Section 2.4.2: Triple-Barrier VECTRA design convention ---
    target_tb_h = (
        "   - **Rào chắn thời gian (Vertical Barrier):** Giới hạn thời gian nắm giữ tối đa $H = 20$ thanh nến M15 (tương đương 20 nến giao dịch liên tục trên sàn, tức 5 giờ giao dịch thực tế, không tính thời gian thị trường đóng cửa cuối tuần). Khi vị thế vượt quá thời hạn $H = 20$ nến mà chưa chạm cả rào chắn TP lẫn SL, vị thế bị đóng cưỡng bức theo thời gian và được gán nhãn quy ước phòng thủ $z = 0$ (không đạt biên độ mục tiêu trong khung thời gian kỳ vọng)."
    )
    repl_tb_h = (
        "   - **Rào chắn thời gian (Vertical Barrier):** Giới hạn thời gian nắm giữ tối đa $H = 20$ thanh nến M15 (tương đương 20 nến giao dịch liên tục trên sàn, tức 5 giờ giao dịch thực tế, không tính thời gian thị trường đóng cửa cuối tuần). Khi vị thế vượt quá thời hạn $H = 20$ nến mà chưa chạm cả rào chắn TP lẫn SL, hệ thống áp dụng quy ước gán nhãn riêng của VECTRA: đóng vị thế theo thời gian và ấn định nhãn quy ước phòng thủ $z = 0$ (coi như không đạt biên độ mục tiêu trong khung thời gian kỳ vọng). Đây là một lựa chọn thiết kế mang tính thận trọng trong quản trị định lượng của đồ án nhằm chỉ coi những cơ hội đạt trọn vẹn mục tiêu biên độ mới là tín hiệu chất lượng cao ($z = 1$), phân biệt với các biến thể khác của phương pháp Ba rào chắn có thể gán nhãn theo dấu của tỷ suất sinh lợi tại thời điểm hết hạn [8]."
    )
    assert target_tb_h in ch2, "target_tb_h not found"
    ch2 = ch2.replace(target_tb_h, repl_tb_h)

    # --- 5. Section 2.5: MarketDataEvent tick vs candle close distinction ---
    target_mde = (
        "- `MarketDataEvent`: Phát sinh khi hệ thống tiếp nhận một thanh nến mới đóng cửa hoặc một nhịp tick giá cập nhật từ MetaTrader 5."
    )
    repl_mde = (
        "- `MarketDataEvent`: Phát sinh khi hệ thống phát hiện dữ liệu thị trường mới từ MetaTrader 5, bao gồm hai dạng sự kiện với mục đích chuyên biệt: (1) Sự kiện nhịp tick cập nhật phục vụ theo dõi giá tức thời, kiểm tra trạng thái lệnh và kích hoạt cơ chế bảo vệ rủi ro; (2) Sự kiện thanh nến đóng cửa phục vụ việc tính toán các đặc trưng kỹ thuật $OHLC$ và xác nhận hoàn tất mẫu hình FVG theo đúng thời điểm đã định nghĩa."
    )
    assert target_mde in ch2, "target_mde not found"
    ch2 = ch2.replace(target_mde, repl_mde)

    with open(ch2_path, "w", encoding="utf-8") as f:
        f.write(ch2)
    print("Chapter 2 updated with all Turn 13 refinements successfully.")

if __name__ == "__main__":
    main()
