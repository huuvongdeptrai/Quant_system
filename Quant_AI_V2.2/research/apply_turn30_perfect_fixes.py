import sys
from pathlib import Path

def main():
    path = Path("Kho_Do_An/Quant_AI_V2.2/research/build_ch4_perfect.py")
    lines = open(path, "r", encoding="utf-8").readlines()
    
    new_lines = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]

        # 1. Scope of cost assumptions in Sec 4.1
        if "toàn bộ các kiểm định đều áp dụng phí hoa hồng sàn $7.0$ USD/lot hai chiều Round-Trip" in line:
            line = line.replace(
                "toàn bộ các kiểm định đều áp dụng phí hoa hồng sàn $7.0$ USD/lot hai chiều Round-Trip",
                "toàn bộ các mô phỏng chiến lược lịch sử trong nghiên cứu áp dụng phí hoa hồng sàn $7.00$ USD/lot hai chiều Round-Trip"
            )
        # and in Sec 4.4.1
        if "Toàn bộ các kiểm định đều áp dụng kịch bản chi phí ma sát định chế với hoa hồng $7.0$ USD/lot" in line:
            line = line.replace(
                "Toàn bộ các kiểm định đều áp dụng kịch bản chi phí ma sát định chế với hoa hồng $7.0$ USD/lot",
                "Toàn bộ các mô phỏng chiến lược lịch sử áp dụng kịch bản chi phí ma sát định chế với hoa hồng $7.00$ USD/lot"
            )

        # 2. Table 4.2 heap row and note, and paragraph below
        if "| **Bộ nhớ Heap Python tính toán** | Đỉnh cấp phát qua `tracemalloc` |" in line:
            line = line.replace(
                "| **Bộ nhớ Heap Python tính toán** | Đỉnh cấp phát qua `tracemalloc` |",
                "| **Bộ nhớ Heap Python tính toán** | Đỉnh cấp phát heap qua `tracemalloc` |"
            )
        if "*Ghi chú:* Các đại lượng bộ nhớ được đo theo chuẩn nhị phân" in line:
            line = "*Ghi chú:* Các đại lượng bộ nhớ được đo theo chuẩn nhị phân ($1\\text{ KiB} = 1{,}024\\text{ bytes}$, $1\\text{ MiB} = 1{,}048{,}576\\text{ bytes}$). Cụ thể, đỉnh heap $108.45\\text{ KiB} / 1{,}024 = 0.1059\\text{ MiB}$ (tương đương khoảng $0.111\\text{ MB}$ theo hệ thập phân) phản ánh đỉnh bộ nhớ heap Python trong phạm vi được `tracemalloc` theo dõi; $101.79\\text{ MiB}$ Resident Set Size (khoảng $106.73\\text{ MB}$) phản ánh bộ nhớ vật lý của toàn bộ tiến trình.\n"
        if "Xét riêng trong phạm vi động cơ tính toán tín hiệu, công cụ `tracemalloc`" in line:
            line = "Xét riêng trong phạm vi đo lường của công cụ `tracemalloc`, đỉnh bộ nhớ heap Python cấp phát được theo dõi trong quá trình nạp nến và tính toán ma trận đặc trưng chỉ tiêu tốn cực đại **108.45 KiB** (tương đương $0.1059$ MiB, khoảng $0.111$ MB theo hệ thập phân). Sau 1,000 chu kỳ liên tục bổ sung nến mới và cập nhật tại chỗ mảng dữ liệu, mức chênh lệch bộ nhớ Python được theo dõi giữa snapshot chu kỳ 1 và chu kỳ 1,000 chỉ ghi nhận ở mức **0.64 KiB** (khoảng $656$ bytes, mức dao động nhỏ phát sinh từ các đối tượng tạm thời của bộ thu gom rác Python). Đồ thị tiêu thụ bộ nhớ duy trì ổn định nằm ngang xuyên suốt quá trình thử nghiệm với cửa sổ cố định $K = 150$ nến. Về mặt lý thuyết cấu trúc dữ liệu, bộ đệm có độ phức tạp không gian $O(K)$ theo kích thước cửa sổ trượt, và bị chặn theo thời gian vận hành khi $K = 150$ cố định trong cấu trúc mảng đệm vòng (ring buffer); kết quả thực nghiệm trong phạm vi kiểm thử xác nhận mức tiêu thụ bộ nhớ ổn định, không làm phát sinh xu hướng tích lũy rò rỉ bộ nhớ.\n"

        # 3. Table 4.3 Latency breakdown rows
        if "| **TỔNG ĐỘ TRỄ ĐƯỜNG ỐNG NỘI BỘ** | **Toàn bộ 5 Tầng Hệ thống** | **2.4017 ms**" in line:
            new_lines.append("| **Tổng sáu phân đoạn thành phần** | **Tích lũy các tầng xử lý** | **2.3991 ms** (**2399.1 $\\mu$s**) | **100.0%** |\n")
            new_lines.append("| **Đo độc lập toàn trình đầu-cuối** | **Toàn bộ đường ống (End-to-End)** | **2.4017 ms** (**2401.7 $\\mu$s**) | **-** |\n")
            i += 1
            continue

        if "| *Phân vị 50 (P50)* |" in line:
            line = "| *Phân vị 50 (P50 toàn trình)* | - | $2.3454$ ms | - |\n"
        elif "| *Phân vị 95 (P95)* |" in line:
            line = "| *Phân vị 95 (P95 toàn trình)* | - | $2.6276$ ms | - |\n"
        elif "| *Phân vị 99 (P99)* |" in line:
            line = "| *Phân vị 99 (P99 toàn trình)* | - | $2.8096$ ms | - |\n"

        # 4. Gold Market 2025-2026 in Sec 4.4.2
        if "- **Giai đoạn 2025 - 2026 (đến 23/10/2026 14:00 UTC):** Bùng nổ lợi nhuận đạt **+$94,803 USD**" in line:
            line = "- **Giai đoạn 2025 - 2026 (đến 23/10/2026 14:00 UTC):** Chiến lược ghi nhận lợi nhuận ròng **+$94,803 USD** với 300 giao dịch (gồm **+$40,300 USD** trong năm 2025 với 163 lệnh, tỷ lệ thắng $39.26\\%$; và **+$54,503 USD** trong năm 2026 với 137 lệnh, tỷ lệ thắng $38.69\\%$). Đây là giai đoạn chiến lược đạt kết quả tốt nhất trong mẫu nghiên cứu. Tuy nhiên, kết quả này không đồng nghĩa giá Vàng tăng liên tục trong toàn giai đoạn: thị trường đã lập các mức cao kỷ lục trong năm 2025 và đầu năm 2026, sau đó trải qua nhịp điều chỉnh. Vì vậy, kết quả cần được diễn giải là hiệu quả quan sát được của cấu hình chiến lược trên chuỗi dữ liệu đã kiểm thử, không phải bằng chứng rằng lợi nhuận đến từ một xu hướng tăng liên tục. Tín hiệu giao dịch cuối cùng xuất hiện lúc 14:00 UTC ngày 23/10/2026; các thanh nến còn lại đến 22:45 UTC ngày 23/10/2026 phục vụ rào chắn thời gian đóng lệnh.\n"

        # 5. PnL reconciliation note in Sec 4.4.2
        if "Mức độ tương đồng của chuỗi tín hiệu và kết quả thắng/thua được xác nhận thông qua đối chiếu nhật ký giao dịch" in line:
            line = "2. *Độ lệch nhỏ về PnL danh nghĩa:* Hai phép đo sử dụng cùng phạm vi thời gian và cùng số lượng 99.999 nến lịch sử được truy xuất, nhưng được thực hiện trên các phiên bản dữ liệu hoặc điều kiện tính toán khác nhau. Do đó, kết quả PnL giữa hai báo cáo có chênh lệch nhỏ ($233.60$ USD cho giai đoạn 2023–2024, tương ứng -$27,196.72$ USD ở Mục 4.4.2 so với -$27,430.32$ USD ở Bảng 4.5; và $1,145.26$ USD trên toàn chu kỳ 2023–2026, tương ứng $67,606.27$ USD so với $68,751.53$ USD, độ lệch khoảng $1.7\\%$, chính xác $1.67\\%$; riêng giai đoạn 2025–2026 ghi nhận chênh lệch $1,378.85$ USD giữa +$94,803.00$ USD và +$96,181.85$ USD) dù số lượng giao dịch và kết quả thắng/thua được ghi nhận là giống nhau. Mức độ tương đồng của chuỗi tín hiệu và kết quả thắng/thua được xác nhận thông qua đối chiếu nhật ký giao dịch của hai lần chạy; phần chênh lệch P&L danh nghĩa được ghi nhận riêng và chưa được quy hoàn toàn cho một nguyên nhân duy nhất. Việc cùng số lượng giao dịch và kết quả thắng/thua không hàm ý rằng toàn bộ các điều kiện tính toán còn lại (như khối lượng lot, giá khớp lệnh, mức trượt giá chi tiết của từng lệnh) đều hoàn toàn đồng nhất; nguyên nhân cụ thể của sai khác PnL cần được xác nhận bằng phép chạy đối chứng bổ sung trên dữ liệu đã cố định và cùng bộ tham số.\n"

        # 6. Section 4.5 Heading & Intro
        if "## 4.5. Đánh giá hiệu quả Meta-Labeling trên dữ liệu ngoài mẫu" in line:
            line = "## 4.5. Đánh giá Meta-Labeling theo quy trình Walk-Forward: tập xác thực và kiểm thử độc lập\n"
        if "giữa việc xác định siêu tham số và kiểm chứng độc lập." in line:
            line = line.replace(
                "giữa việc xác định siêu tham số và kiểm chứng độc lập.",
                "giữa việc xác định siêu tham số trên tập xác thực và kiểm chứng độc lập trên tập kiểm thử."
            )
        if "xác định ngưỡng xác suất vận hành tối ưu $P^*$" in line:
            line = line.replace(
                "xác định ngưỡng xác suất vận hành tối ưu $P^*$",
                "xác định ngưỡng xác suất vận hành được lựa chọn $P^*$"
            )

        # 7. Section 4.5.2 Threshold selection & Multi-criteria formulation
        if "Nhằm mục tiêu xác lập một quy tắc ra quyết định khách quan trước khi bước vào giai đoạn kiểm thử ngoài mẫu, nghiên cứu định nghĩa hàm mục tiêu Calmar Proxy quy ước:" in line:
            line = "Nhằm mục tiêu khảo sát độ nhạy và xác lập một quy tắc ra quyết định khách quan trước khi bước vào giai đoạn kiểm thử ngoài mẫu, nghiên cứu theo dõi hàm mục tiêu Calmar Proxy quy ước:\n"
            new_lines.append(line)
            new_lines.append("\n")
            new_lines.append("$$J(P) = \\frac{\\text{Net Profit}(P) / \\text{Initial Capital}}{\\text{Max Drawdown}(P)}$$\n")
            new_lines.append("\n")
            new_lines.append("Quy tắc xác lập ngưỡng vận hành trong nghiên cứu được tiếp cận theo bài toán cân bằng thực nghiệm đa tiêu chí kết hợp ràng buộc quy mô mẫu:\n")
            new_lines.append("1. *Ưu tiên an toàn vốn và lợi nhuận dương:* $\\text{Net Profit}(P) > 0$ và $\\text{Max Drawdown}(P) \\le 15.0\\%$.\n")
            new_lines.append("2. *Ràng buộc quy mô mẫu vận hành:* Duy trì số lượng giao dịch tối thiểu ($N(P) \\ge 60$ lệnh trong 2 năm, tương đương bình quân tối thiểu $2.5 - 3$ lệnh/tháng) nhằm tránh hiện tượng thiếu hụt mẫu thống kê và nguy cơ sụp đổ tần suất giao dịch trong môi trường thực tế.\n")
            new_lines.append("3. *Chỉ số hiệu quả rủi ro:* Đạt mức $J(P) > 0$ ổn định.\n")
            # Skip the next line which had the old formula since we appended it
            if i + 2 < n and "$$J(P) = " in lines[i+2]:
                i += 3
                continue
            i += 1
            continue

        if "Mặc dù ngưỡng $P = 0.40$ đạt chỉ số $J(P) = +0.16$" in line:
            line = "Xét thuần túy về giá trị đơn mục tiêu của hàm $J(P)$, ngưỡng $P = 0.40$ đạt điểm số cao nhất ($J(P) = +0.16$ với lợi nhuận $+2,298.67$ USD và Profit Factor 1.15). Tuy nhiên, tại ngưỡng này, số lượng mẫu lệnh bị thu hẹp chỉ còn $44$ giao dịch trong suốt 2 năm (trung bình chưa tới 2 lệnh/tháng), tiềm ẩn nguy cơ nhạy cảm quá mức với chi phí giao dịch và làm suy giảm tính đại diện thống kê của mẫu quan sát. Do đó, ngưỡng **$P^* = 0.38$** được xác lập theo tiêu chí cân bằng vận hành: mức ngưỡng này thỏa mãn đồng thời mục tiêu kiểm soát sụt giảm vốn (Max Drawdown giảm từ $38.64\\%$ xuống $14.12\\%$, tức giảm $63.5\\%$ biên độ rủi ro), ghi nhận lợi nhuận ròng dương (+$1,892.95$ USD, $J(P) = +0.13$), đồng thời bảo toàn được $72$ giao dịch trên tập xác thực (nhiều hơn $63.6\\%$ về quy mô mẫu so với ngưỡng $P \\ge 0.40$). Đây là lựa chọn theo tiêu chí cân bằng vận hành thực tế của nghiên cứu, không phải điểm cực trị toán học của hàm $J(P)$ đơn lẻ khi không có ràng buộc mẫu, và không thay thế cho kết luận về ý nghĩa thống kê nếu chưa có kiểm định tương ứng.\n"

        # 8. Sec 4.5.3 Drawdown claim scope
        if "đạt được mục tiêu thiết kế an toàn vốn của đề tài ($< 5.0\\%$)." in line:
            line = line.replace(
                "đạt được mục tiêu thiết kế an toàn vốn của đề tài ($< 5.0\\%$).",
                "đạt ngưỡng an toàn thiết kế ($< 5.0\\%$) trong phạm vi mẫu kiểm thử độc lập 2025–2026. Mặc dù đây là kết quả tích cực trên mẫu quan sát gồm 62 giao dịch sau lọc, kết quả này chưa đủ để bảo đảm mức sụt giảm luôn duy trì dưới $5.0\\%$ trong mọi điều kiện thị trường tương lai hoặc khi vận hành bằng tiền thật."
            )
        if "để nén mức sụt giảm tối đa xuống dưới ngưỡng an toàn thiết kế ($< 5.0\\%$)" in line:
            line = line.replace(
                "để nén mức sụt giảm tối đa xuống dưới ngưỡng an toàn thiết kế ($< 5.0\\%$)",
                "để nén mức sụt giảm tối đa trong mẫu kiểm thử xuống dưới ngưỡng an toàn thiết kế ($< 5.0\\%$)"
            )

        # 9. Sec 4.6 Demo execution: Separate Requote from Margin/Lot
        if "Đồng thời, trong mẫu sáu vị thế quan sát được, không ghi nhận trường hợp lệnh thị trường nào bị từ chối báo giá lại Requote." in line:
            p1 = "Đồng thời, trong mẫu sáu vị thế quan sát được trong điều kiện thanh khoản bình thường, hệ thống không ghi nhận trường hợp lệnh thị trường nào bị máy chủ sàn từ chối báo giá lại Requote. Cần lưu ý rằng việc không quan sát thấy Requote trong phạm vi sáu vị thế thử nghiệm chỉ mang tính chất kiểm chứng tính khả thi kỹ thuật trong điều kiện đo lường cụ thể, không phải bằng chứng chứng minh hệ thống có thể loại trừ hoàn toàn rủi ro Requote khi thị trường biến động dữ dội hoặc thiếu hụt thanh khoản.\n"
            p2 = "\nBên cạnh đó, về mặt quản trị ký quỹ, thuật toán định cỡ rủi ro Tầng 5 tính toán quy mô Lot động dựa trên lượng tiền ký quỹ khả dụng thực tế (`margin_free`) và kiểm tra điều kiện tài khoản trước khi gửi lệnh, giúp loại trừ nguy cơ phát sinh mã lỗi từ chối ký quỹ từ máy chủ sàn (`TRADE_RETCODE_NO_MONEY` - mã số 10019) trong các bài thử nghiệm. Dù vậy, quy mô mẫu sáu vị thế mang tính chất kiểm chứng nguyên lý vận hành của đường ống thực thi, chưa đủ để khái quát hóa thành tỷ lệ thành công tuyệt đối trong mọi điều kiện giao dịch bằng tiền thật.\n"
            new_lines.append(p1)
            new_lines.append(p2)
            i += 1
            continue

        new_lines.append(line)
        i += 1

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print("Updated build_ch4_perfect.py with Turn 30 fixes successfully")

if __name__ == "__main__":
    main()
