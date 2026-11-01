import sys
from pathlib import Path

def main():
    path = Path("Kho_Do_An/Quant_AI_V2.2/research/build_ch4_perfect.py")
    lines = open(path, "r", encoding="utf-8").readlines()
    
    new_lines = []
    for line in lines:
        # Point 1.2: 4.27 năm theo lịch
        if "Thực hiện kiểm thử trên toàn bộ 99.999 nến M15 được truy xuất và sử dụng trong thực nghiệm (tương đương 4.27 năm liên tục" in line:
            line = line.replace(
                "Thực hiện kiểm thử trên toàn bộ 99.999 nến M15 được truy xuất và sử dụng trong thực nghiệm (tương đương 4.27 năm liên tục từ 18/07/2022 03:15 UTC đến 23/10/2026 22:45 UTC).",
                "Thực nghiệm sử dụng 99.999 nến M15 được truy xuất và đưa vào mô phỏng, trải dài trong khoảng thời gian từ 18/07/2022 03:15 UTC đến 23/10/2026 22:45 UTC, tương đương khoảng 4.27 năm theo lịch."
            )
        if "(từ 18/07/2022 03:15 UTC đến 23/10/2026 22:45 UTC, tương đương 4.27 năm liên tục)" in line:
            line = line.replace(
                "(từ 18/07/2022 03:15 UTC đến 23/10/2026 22:45 UTC, tương đương 4.27 năm liên tục)",
                "(trải dài trong khoảng thời gian từ 18/07/2022 03:15 UTC đến 23/10/2026 22:45 UTC, tương đương khoảng 4.27 năm theo lịch)"
            )
        if "*Bảng 4.4: Hiệu năng của chiến lược tất định thuần túy qua các cấu hình chiến lược (4.27 năm lịch sử)*" in line:
            line = line.replace(
                "*Bảng 4.4: Hiệu năng của chiến lược tất định thuần túy qua các cấu hình chiến lược (4.27 năm lịch sử)*",
                "*Bảng 4.4: Hiệu năng của chiến lược tất định thuần túy qua các cấu hình chiến lược (khoảng 4.27 năm theo lịch)*"
            )
        if "qua 4.27 năm), phân tích chi tiết" in line:
            line = line.replace(
                "qua 4.27 năm), phân tích chi tiết",
                "trải dài qua khoảng 4.27 năm theo lịch), phân tích chi tiết"
            )

        # Point 1.3: Table 4.2 memory units and notes
        if "| **Bộ nhớ vật lý tiến trình** | Resident Set Size qua `psutil` |" in line:
            line = "| **Bộ nhớ vật lý tiến trình** | Resident Set Size qua `psutil` | $< 200$ MB | **101.79 MiB** (khoảng $106.73$ MB) | **Đạt chuẩn thiết kế** (Chiếm $53.4\\%$ hạn mức) |\n"
        elif "| **Bộ nhớ Heap Python tính toán** | Đỉnh cấp phát qua `tracemalloc` |" in line:
            line = "| **Bộ nhớ Heap Python tính toán** | Đỉnh cấp phát qua `tracemalloc` | $< 10$ MB | **108.45 KiB** ($0.1059$ MiB) | **Tối ưu vượt chuẩn ngân sách Heap** |\n"
        elif "| **Biến thiên bộ nhớ sau 1,000 chu kỳ** | Chênh lệch snapshot `tracemalloc` |" in line:
            line = "| **Biến thiên bộ nhớ sau 1,000 chu kỳ** | Chênh lệch snapshot `tracemalloc` | $< 5.0$ MB | **0.64 KiB** ($656$ bytes) | **Duy trì ổn định trong phạm vi thử nghiệm** |\n"
        
        # After GUI FPS row in Table 4.2, add note
        if "| **Tốc độ khung hình giao diện GUI** | Đo qua `QElapsedTimer` khi cập nhật nến |" in line:
            new_lines.append(line)
            new_lines.append("\n")
            new_lines.append("*Ghi chú:* Các đại lượng bộ nhớ được đo theo chuẩn nhị phân ($1\\text{ KiB} = 1{,}024\\text{ bytes}$, $1\\text{ MiB} = 1{,}048{,}576\\text{ bytes}$). Cụ thể, đỉnh heap $108.45\\text{ KiB} / 1{,}024 = 0.1059\\text{ MiB}$ (tương đương khoảng $0.111\\text{ MB}$ theo hệ thập phân); $101.79\\text{ MiB}$ Resident Set Size tương đương khoảng $106.73\\text{ MB}$ theo hệ thập phân.\n")
            continue

        # Text below Table 4.2
        if "Kết quả đo đạc từ thư viện `psutil` xác nhận tổng lượng bộ nhớ vật lý thực tế" in line:
            line = "Kết quả đo đạc từ thư viện `psutil` xác nhận tổng lượng bộ nhớ vật lý thực tế của toàn bộ tiến trình VECTRA khi nạp đầy đủ runtime Python, giao diện đồ họa PySide6, động cơ LightGBM và các mô-đun kết nối MetaTrader 5 chỉ chiếm **101.79 MiB** (khoảng $106.73$ MB), hoàn toàn nằm trong hạn mức trần 200 MB đặt ra cho các máy trạm cá nhân phổ thông. \n"
        if "Xét riêng trong phạm vi động cơ tính toán tín hiệu, công cụ `tracemalloc` ghi nhận dung lượng heap" in line:
            line = "Xét riêng trong phạm vi động cơ tính toán tín hiệu, công cụ `tracemalloc` ghi nhận dung lượng heap cấp phát cho mảng nến và ma trận đặc trưng vi cấu trúc chỉ tiêu tốn cực đại **108.45 KiB** (tương đương $0.1059$ MiB, khoảng $0.111$ MB). Sau 1,000 chu kỳ liên tục bổ sung nến mới và cập nhật tại chỗ mảng dữ liệu, mức chênh lệch bộ nhớ Python được theo dõi giữa snapshot chu kỳ 1 và chu kỳ 1,000 chỉ ghi nhận ở mức **0.64 KiB** (khoảng $656$ bytes, mức dao động nhỏ phát sinh từ các đối tượng tạm thời của bộ thu gom rác Python). Đồ thị tiêu thụ bộ nhớ duy trì ổn định nằm ngang xuyên suốt quá trình thử nghiệm với cửa sổ cố định $K = 150$ nến. Về mặt cấu trúc thuật toán, việc duy trì mảng đệm vòng cố định kích thước $K$ bảo đảm tính chất giới hạn không gian lưu trữ hằng số $O(1)$ theo thời gian vận hành; kết quả thực nghiệm trong phạm vi kiểm thử cho thấy mức tiêu thụ bộ nhớ ổn định, không làm phát sinh xu hướng tích lũy rò rỉ bộ nhớ.\n"

        # Figure 4.1 caption
        if "*Hình 4.1: Kết quả đo lường thực nghiệm hiệu năng hệ thống: (a) Biến thiên độ trễ qua 1.000 chu kỳ; (b) Bóc tách tỷ trọng thời gian 5 tầng xử lý; (c) Kiểm soát bộ nhớ RAM hằng số" in line:
            line = "*Hình 4.1: Kết quả đo lường thực nghiệm hiệu năng hệ thống: (a) Biến thiên độ trễ qua 1.000 chu kỳ; (b) Bóc tách tỷ trọng thời gian 5 tầng xử lý; (c) Mức sử dụng bộ nhớ RAM duy trì ổn định trong thử nghiệm với cửa sổ cố định $K = 150$*\n"

        # Point 1.1: 740 tín hiệu trong chuỗi Walk-Forward tổng hợp
        if "Cả hai phép đo đều sử dụng chung cấu hình chiến lược Năng động và cùng bao quát 740 tín hiệu ngoài mẫu trong giai đoạn 2023–2026:" in line:
            line = "Khi đối chiếu riêng giai đoạn 2023–2026, hai báo cáo cùng bao quát 740 tín hiệu trong chuỗi Walk-Forward tổng hợp, gồm tập xác thực giai đoạn 2023–2024 và tập kiểm thử độc lập giai đoạn 2025–2026 (mốc thời gian 26/10/2026 xuất hiện trong một số nhật ký nội bộ chỉ là thời điểm thực hiện lần chạy benchmark kiểm tra trên hệ thống, không phải là mốc kết thúc của chuỗi dữ liệu nến):\n"

        # Point 1.4: PnL reconciliation caution note
        if "dù số lượng giao dịch và kết quả thắng/thua được ghi nhận là giống nhau. Nguyên nhân cụ thể của sai khác PnL cần được xác nhận bằng phép chạy đối chứng" in line:
            line = line.replace(
                "dù số lượng giao dịch và kết quả thắng/thua được ghi nhận là giống nhau. Nguyên nhân cụ thể của sai khác PnL cần được xác nhận bằng phép chạy đối chứng trên dữ liệu đã cố định và cùng bộ tham số.",
                "dù số lượng giao dịch và kết quả thắng/thua được ghi nhận là giống nhau. Mức độ tương đồng của chuỗi tín hiệu và kết quả thắng/thua được xác nhận thông qua đối chiếu nhật ký giao dịch của hai lần chạy; phần chênh lệch P&L danh nghĩa được ghi nhận riêng và chưa được quy hoàn toàn cho một nguyên nhân duy nhất. Nguyên nhân cụ thể của sai khác PnL cần được xác nhận bằng phép chạy đối chứng trên dữ liệu đã cố định và cùng bộ tham số."
            )

        new_lines.append(line)

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print("Updated build_ch4_perfect.py successfully")

if __name__ == "__main__":
    main()
