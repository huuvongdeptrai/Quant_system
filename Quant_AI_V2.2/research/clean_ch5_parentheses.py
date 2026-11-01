# -*- coding: utf-8 -*-
"""
Clean unnecessary parenthetical English terms in Chapter 5.
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

p = Path("Kho_Do_An/Quant_AI_V2.2/docs/thesis/chuong_5_ket_luan.md")
txt = p.read_text(encoding="utf-8")

replacements = [
    ("**Nền tảng giao dịch định lượng đa tầng tự hành (VECTRA - Multi-Tier Autonomous Quantitative Trading Platform)**", "**Nền tảng giao dịch định lượng đa tầng tự hành VECTRA**"),
    ("đường ống 5 tầng phân ly (5-Stage Decoupled Pipeline)", "đường ống 5 tầng phân ly"),
    ("theo mô hình Hướng sự kiện (Event-Driven Architecture).", "theo mô hình hướng sự kiện."),
    ("thuật toán Cửa sổ trượt tại chỗ (In-place Rolling Window)", "thuật toán cửa sổ trượt tại chỗ"),
    ("Cây quyết định tăng cường độ dốc (LightGBM Booster)", "Cây quyết định tăng cường độ dốc LightGBM"),
    ("lực tự phục hồi (Resilience Engineering):", "lực tự phục hồi:"),
    ("kiểm thử đơn vị và tích hợp (Unit & Integration Tests)", "kiểm thử đơn vị và tích hợp"),
    ("kết nối mạng (Heartbeat Timeout),", "kết nối mạng,"),
    ("suy thoái an toàn (Fail-fast)", "suy thoái an toàn"),
    ("ngoài mẫu mở rộng (Expanding Walk-Forward OOS)", "ngoài mẫu mở rộng"),
    ("thời gian thực (Forward Paper Trading):", "thời gian thực:"),
    ("### 5.2.1. Đóng góp về mặt Khoa học Tài chính Định lượng (Quantitative Finance Methodology)", "### 5.2.1. Đóng góp về mặt Khoa học Tài chính Định lượng"),
    ("tỷ số Tín hiệu trên Nhiễu (Signal-to-Noise Ratio)", "tỷ số Tín hiệu trên Nhiễu"),
    ("hiện tượng quá khớp (Overfitting)", "hiện tượng quá khớp"),
    ("đặc trưng vi cấu trúc (Microstructure Features) phi tuyến tính,", "đặc trưng vi cấu trúc phi tuyến tính,"),
    ("khoản khả dụng (Headroom).", "khoản khả dụng Headroom."),
    ("độ quan trọng của đặc trưng (Feature Importance)", "độ quan trọng của đặc trưng"),
    ("### 5.2.2. Đóng góp về mặt Kỹ nghệ Phần mềm và Kiến trúc Hệ thống (Software Architecture & Engineering)", "### 5.2.2. Đóng góp về mặt Kỹ nghệ Phần mềm và Kiến trúc Hệ thống"),
    ("trạm giao dịch định chế độc lập (Institutional Desktop Trading Station)", "trạm giao dịch định chế độc lập"),
    ("Cổng thực thi thụ động (Execution Gateway),", "Cổng thực thi thụ động,"),
    ("cơ chế vi sai hai lớp (Incremental Dual-Layer Painting),", "cơ chế vi sai hai lớp,"),
    ("khung kiểm thử phòng vệ (Resilience Engineering Protocol)", "khung kiểm thử phòng vệ"),
    ("liên tiến trình (IPC Shared Memory)", "liên tiến trình IPC"),
    ("thời gian khứ hồi gói tin qua mạng internet (Network RTT dao động từ", "thời gian khứ hồi gói tin qua mạng Internet (dao động từ"),
    ("thanh khoản cấp 1 (Tier-1 Prime Broker).", "thanh khoản cấp 1."),
    ("thị trường phi tập trung (Over-The-Counter),", "thị trường phi tập trung OTC,"),
    ("Vàng giao ngay (Forex/CFD)", "Vàng giao ngay Forex và CFD"),
    ("thực tế (Real Traded Volume).", "thực tế."),
    ("ước lượng đại diện (Proxy Estimator)", "ước lượng đại diện"),
    ("sổ lệnh giới hạn (Limit Order Book Level 2/3)", "sổ lệnh giới hạn Level 2 và 3"),
    ("sở giao dịch tương lai tập trung (CME/COMEX).", "sở giao dịch tương lai tập trung."),
    ("thời gian thực (Dynamic Covariance Matrix)", "thời gian thực"),
    ("nguyên lý Kelly phân đoạn (Fractional Kelly Criterion).", "nguyên lý Kelly phân đoạn."),
    ("danh mục chéo (Cross-Sectional Portfolio),", "danh mục chéo,"),
    ("Phân cấp (Hierarchical Risk Parity - HRP)", "Phân cấp HRP"),
    ("lý thuyết Đồ thị mạng (Graph Theory)", "lý thuyết Đồ thị mạng"),
    ("Học máy Tăng cường Sâu (Deep RL)", "Học máy Tăng cường Sâu"),
    ("dời dừng lỗ (Trailing Stop)", "dời dừng lỗ"),
    ("mô hình ngôn ngữ lớn cục bộ (Edge LLM)", "mô hình ngôn ngữ lớn cục bộ"),
    ("ngữ nghĩa (Sentiment Scoring)", "ngữ nghĩa")
]

count = 0
for old, new in replacements:
    if old in txt:
        txt = txt.replace(old, new)
        count += 1
    else:
        print(f"NOT FOUND: {old[:40]}")

p.write_text(txt, encoding="utf-8")
print(f"Cleaned {count} items in Chapter 5!")
