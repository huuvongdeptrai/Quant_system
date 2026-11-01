# -*- coding: utf-8 -*-
"""
Clean unnecessary parenthetical English terms in Chapter 4.
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

p = Path("Kho_Do_An/Quant_AI_V2.2/docs/thesis/chuong_4_thuc_nghiem.md")
txt = p.read_text(encoding="utf-8")

replacements = [
    # 4.1 & 4.2
    ("thực tế bi quan (Pessimistic Execution).", "thực tế bi quan."),
    ("bài kiểm thử tự động (Unit & Integration Tests)", "bài kiểm thử tự động"),
    ("kịch bản ngoại lệ sống còn (Edge Cases)", "kịch bản ngoại lệ sống còn"),
    ("Kịch bản ngoại lệ (Edge Cases)", "Kịch bản ngoại lệ"),
    ("từ chối lệnh (Rejection)", "từ chối lệnh"),
    ("thay đổi (Requote)", "thay đổi"),
    ("Stress Test phần cứng (Hardware Stress Test)", "Kiểm thử phần cứng"),
    ("mức tiêu thụ RAM đỉnh (Peak Memory) của", "mức tiêu thụ RAM đỉnh của"),
    ("liên tục (Streaming)", "liên tục"),
    ("giao diện (GUI FPS)", "giao diện"),
    ("thuật toán Cửa sổ trượt bộ nhớ tĩnh (In-place Rolling Window)", "thuật toán cửa sổ trượt bộ nhớ tĩnh"),
    ("vẽ nến vi sai hai lớp (Incremental Dual-Layer Painting)", "vẽ nến vi sai hai lớp"),
    ("ngân sách độ trễ (Latency Budget)", "ngân sách độ trễ"),
    
    # Table 4.3
    ("Tầng 1 (Safety Guards)", "Tầng 1 - Cầu dao an toàn"),
    ("Tầng 2 (Macro Cache)", "Tầng 2 - Bộ đệm vĩ mô"),
    ("Tầng 3 (Primary Strategy)", "Tầng 3 - Nhận diện hình học Wyckoff"),
    ("Tầng 4a (Feature Extractor)", "Tầng 4a - Trích xuất đặc trưng"),
    ("Tầng 4b (LightGBM Meta-Model)", "Tầng 4b - Suy luận LightGBM"),
    ("Tầng 5 (Risk Sizing Engine)", "Tầng 5 - Định cỡ rủi ro"),
    ("Phân vị 50 (Median P50)", "Phân vị 50 (P50)"),
    ("Phân vị 95 (P95 Latency)", "Phân vị 95 (P95)"),
    ("Phân vị 99 (P99 Latency)", "Phân vị 99 (P99)"),
    ("đường ống nội bộ (Internal Pipeline Latency)", "đường ống nội bộ"),
    ("máy chủ sàn (Broker Fill ACK)", "máy chủ sàn"),
    
    # 4.4
    ("đối chứng khách quan (Benchmark),", "đối chứng khách quan,"),
    ("Hồ sơ rủi ro (Risk Profile)", "Hồ sơ rủi ro"),
    ("Tỷ lệ thắng (Winrate)", "Tỷ lệ thắng"),
    ("Lợi nhuận ròng (Net Profit)", "Lợi nhuận ròng"),
    ("Mức sụt giảm tối đa (Max Drawdown)", "Mức sụt giảm tối đa"),
    ("Hệ số Lợi/Lỗ (Profit Factor)", "Hệ số Lợi/Lỗ"),
    ("**Nghiêm ngặt (Strict)**", "**Nghiêm ngặt**"),
    ("**Cân bằng (Balanced)**", "**Cân bằng**"),
    ("**Năng động (Dynamic)**", "**Năng động**"),
    ("chế độ thị trường (Regime Shift),", "chế độ thị trường,"),
    ("Biểu đồ đường cong vốn (Equity Curve) và Đường chìm sụt giảm (Underwater Drawdown)", "Biểu đồ đường cong vốn và đường chìm sụt giảm"),
    ("bẫy phá vỡ giả (Chop/Range-bound)", "bẫy phá vỡ giả khi thị trường đi ngang giằng co"),

    # 4.5
    ("chọn lọc (Selection Bias)", "chọn lọc"),
    ("ngoài mẫu (Data Snooping),", "ngoài mẫu,"),
    ("tái huấn luyện mở rộng (Expanding Walk-Forward):", "tái huấn luyện mở rộng:"),
    ("Phương pháp Ba rào chắn (Triple-Barrier Method):", "Phương pháp Ba rào chắn:"),
    ("Thanh lọc mẫu chồng lấn (Purging):", "Thanh lọc mẫu chồng lấn:"),
    ("Vùng đệm cách ly (Embargoing):", "Vùng đệm cách ly:"),
    ("hệ đặc trưng (Causality):", "hệ đặc trưng:"),
    ("chế độ thị trường (Market Regime)", "chế độ thị trường"),
    ("thích ứng động (Dynamic Thresholding)", "thích ứng động"),
    ("nén sụt giảm tài khoản (Drawdown Compression)", "nén sụt giảm tài khoản"),

    # 4.6
    ("trực tiếp (Live Forward Testing)", "trực tiếp"),
    ("liên tiến trình (IPC)", "liên tiến trình IPC"),
    ("gói tin (Network Round-Trip Time - RTT)", "gói tin RTT"),
    ("trước giao dịch (Pre-trade Risk & Order Validation),", "trước giao dịch,"),
    ("xử lý (Thread Blocking)", "xử lý"),
    ("vi cấu trúc (Execution Slippage),", "vi cấu trúc,"),
    ("thử nghiệm (Demo Forward Paper Trading)", "thử nghiệm")
]

count = 0
for old, new in replacements:
    if old in txt:
        txt = txt.replace(old, new)
        count += 1
    else:
        print(f"NOT FOUND: {old[:40]}")

p.write_text(txt, encoding="utf-8")
print(f"Cleaned {count} items in Chapter 4!")
