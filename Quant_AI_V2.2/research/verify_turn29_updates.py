import sys
from pathlib import Path

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    content = open("Kho_Do_An/Quant_AI_V2.2/docs/thesis/chuong_4_thuc_nghiem.md", "r", encoding="utf-8").read()

    checks = [
        ("Point 1.1: Walk-Forward reconciliation phrase", "Khi đối chiếu riêng giai đoạn 2023–2026, hai báo cáo cùng bao quát 740 tín hiệu trong chuỗi Walk-Forward tổng hợp, gồm tập xác thực giai đoạn 2023–2024 và tập kiểm thử độc lập giai đoạn 2025–2026" in content),
        ("Point 1.2: Calendar time span in Sec 4.1", "Thực nghiệm sử dụng 99.999 nến M15 được truy xuất và đưa vào mô phỏng, trải dài trong khoảng thời gian từ 18/07/2022 03:15 UTC đến 23/10/2026 22:45 UTC, tương đương khoảng 4.27 năm theo lịch." in content),
        ("Point 1.2: Calendar time span in Sec 4.4.1", "(trải dài trong khoảng thời gian từ 18/07/2022 03:15 UTC đến 23/10/2026 22:45 UTC, tương đương khoảng 4.27 năm theo lịch)" in content),
        ("Point 1.2: Table 4.4 caption", "*Bảng 4.4: Hiệu năng của chiến lược tất định thuần túy qua các cấu hình chiến lược (khoảng 4.27 năm theo lịch)*" in content),
        ("Point 1.3: Table 4.2 101.79 MiB", "101.79 MiB" in content),
        ("Point 1.3: Table 4.2 108.45 KiB", "108.45 KiB" in content),
        ("Point 1.3: Table 4.2 binary note", "*Ghi chú:* Các đại lượng bộ nhớ được đo theo chuẩn nhị phân" in content),
        ("Point 1.3: Fig 4.1 caption stable RAM", "Mức sử dụng bộ nhớ RAM duy trì ổn định trong thử nghiệm với cửa sổ cố định $K = 150$" in content),
        ("Point 1.4: PnL trade log reconciliation caution", "Mức độ tương đồng của chuỗi tín hiệu và kết quả thắng/thua được xác nhận thông qua đối chiếu nhật ký giao dịch của hai lần chạy; phần chênh lệch P&L danh nghĩa được ghi nhận riêng và chưa được quy hoàn toàn cho một nguyên nhân duy nhất." in content)
    ]

    all_ok = True
    for name, passed in checks:
        status = "[OK]" if passed else "[FAIL]"
        print(f"{status} {name}")
        if not passed:
            all_ok = False

    if all_ok:
        print("\nALL 9 REVIEWS PASSED WITH 100% ACCURACY!")
    else:
        print("\nSOME CHECKS FAILED!")
        sys.exit(1)

if __name__ == "__main__":
    main()
