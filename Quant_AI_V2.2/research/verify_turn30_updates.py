import sys
from pathlib import Path

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    content = open("Kho_Do_An/Quant_AI_V2.2/docs/thesis/chuong_4_thuc_nghiem.md", "r", encoding="utf-8").read()

    checks = [
        ("Table 4.3 component sum row", "| **Tổng sáu phân đoạn thành phần** | **Tích lũy các tầng xử lý** | **2.3991 ms**" in content),
        ("Table 4.3 end-to-end row", "| **Đo độc lập toàn trình đầu-cuối** | **Toàn bộ đường ống (End-to-End)** | **2.4017 ms**" in content),
        ("Table 4.3 P50/P95/P99 clarified", "| *Phân vị 50 (P50 toàn trình)* |" in content),
        ("Gold 2025-2026 description nuanced", "thị trường đã lập các mức cao kỷ lục trong năm 2025 và đầu năm 2026, sau đó trải qua nhịp điều chỉnh" in content),
        ("Section 4.5 title updated", "## 4.5. Đánh giá Meta-Labeling theo quy trình Walk-Forward: tập xác thực và kiểm thử độc lập" in content),
        ("Section 4.5.2 multi-criteria text", "Quy tắc xác lập ngưỡng vận hành trong nghiên cứu được tiếp cận theo bài toán cân bằng thực nghiệm đa tiêu chí kết hợp ràng buộc quy mô mẫu:" in content),
        ("Section 4.5.2 unconstrained J(P) vs 0.38", "Xét thuần túy về giá trị đơn mục tiêu của hàm $J(P)$, ngưỡng $P = 0.40$ đạt điểm số cao nhất" in content),
        ("Section 4.5.2 sample size tradeoff", "nhiều hơn $63.6\\%$ về quy mô mẫu so với ngưỡng $P \\ge 0.40$" in content),
        ("Historical simulation cost scope Sec 4.1", "toàn bộ các mô phỏng chiến lược lịch sử trong nghiên cứu áp dụng phí hoa hồng sàn $7.00$ USD/lot" in content),
        ("Historical simulation cost scope Sec 4.4.1", "Toàn bộ các mô phỏng chiến lược lịch sử áp dụng kịch bản chi phí ma sát định chế với hoa hồng $7.00$ USD/lot" in content),
        ("tracemalloc scope in Table 4.2", "Đỉnh cấp phát heap qua `tracemalloc`" in content),
        ("tracemalloc scope in Table 4.2 note", "phản ánh đỉnh bộ nhớ heap Python trong phạm vi được `tracemalloc` theo dõi" in content),
        ("Space complexity O(K) bounded", "bộ đệm có độ phức tạp không gian $O(K)$ theo kích thước cửa sổ trượt, và bị chặn theo thời gian vận hành khi $K = 150$ cố định" in content),
        ("PnL reconciliation non-identity caveat", "Việc cùng số lượng giao dịch và kết quả thắng/thua không hàm ý rằng toàn bộ các điều kiện tính toán còn lại (như khối lượng lot, giá khớp lệnh, mức trượt giá chi tiết của từng lệnh) đều hoàn toàn đồng nhất" in content),
        ("Demo execution separate Requote", "Cần lưu ý rằng việc không quan sát thấy Requote trong phạm vi sáu vị thế thử nghiệm chỉ mang tính chất kiểm chứng tính khả thi kỹ thuật trong điều kiện đo lường cụ thể" in content),
        ("Demo execution separate Margin", "thuật toán định cỡ rủi ro Tầng 5 tính toán quy mô Lot động dựa trên lượng tiền ký quỹ khả dụng thực tế (`margin_free`)" in content),
        ("Drawdown scope bounded to 2025-2026 test sample", "đạt ngưỡng an toàn thiết kế ($< 5.0\\%$) trong phạm vi mẫu kiểm thử độc lập 2025–2026. Mặc dù đây là kết quả tích cực trên mẫu quan sát gồm 62 giao dịch sau lọc, kết quả này chưa đủ để bảo đảm mức sụt giảm luôn duy trì dưới $5.0\\%$ trong mọi điều kiện thị trường tương lai" in content)
    ]

    all_ok = True
    for name, passed in checks:
        status = "[OK]" if passed else "[FAIL]"
        print(f"{status} {name}")
        if not passed:
            all_ok = False

    if all_ok:
        print(f"\nALL {len(checks)} TURN 30 AUDIT CHECKS PASSED WITH 100% SUCCESS!")
    else:
        print("\nSOME CHECKS FAILED!")
        sys.exit(1)

if __name__ == "__main__":
    main()
