# -*- coding: utf-8 -*-
"""
Clean unnecessary parenthetical English terms in Chapter 3.
Preserves:
- Math expressions like $f(X_t)$, $O(1)$, $P(z=1)$
- Markdown image links ![...](...)
- Citations [12], [14]
- Functional parameters / code blocks
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

p = Path("Kho_Do_An/Quant_AI_V2.2/docs/thesis/chuong_3_thiet_ke_he_thong.md")
txt = p.read_text(encoding="utf-8")

replacements = [
    # Section 3.1
    ("tiêu chuẩn phần mềm định chế (Institutional Software Standards)", "tiêu chuẩn phần mềm định chế"),
    ("### 3.1.1. Yêu cầu chức năng (Functional Requirements)", "### 3.1.1. Yêu cầu chức năng"),
    ("thông qua liên tiến trình (IPC)", "thông qua liên tiến trình IPC"),
    ("thanh khoản (Fair Value Gaps)", "thanh khoản Fair Value Gap"),
    ("khung hình cao (60 FPS)", "khung hình cao 60 FPS"),
    ("quy mô vị thế động (Position Sizing)", "quy mô vị thế động"),
    ("### 3.1.2. Tiêu chuẩn phi chức năng (Non-Functional Requirements & Latency Budget)", "### 3.1.2. Tiêu chuẩn phi chức năng và ngân sách độ trễ"),
    ("- **Phân định ngân sách độ trễ (Latency Budget & Breakdown):**", "- **Phân định ngân sách độ trễ:**"),
    ("*Độ trễ đường ống nội bộ (Internal Pipeline Latency):*", "*Độ trễ đường ống nội bộ:*"),
    ("*Độ trễ tiền kiểm định cấu trúc lệnh (Pre-trade Validation Latency):*", "*Độ trễ tiền kiểm định cấu trúc lệnh:*"),
    ("*Độ trễ mạng khứ hồi (Network Round-Trip Time - RTT):*", "*Độ trễ mạng khứ hồi RTT:*"),
    ("*Độ trễ khớp lệnh tại sàn (Broker Execution Latency):*", "*Độ trễ khớp lệnh tại sàn:*"),
    ("phản hồi xác nhận (ACK)", "phản hồi xác nhận"),
    ("- **Ngân sách bộ nhớ RAM (Memory Budget):**", "- **Ngân sách bộ nhớ RAM:**"),
    ("- **Tính toàn vẹn dữ liệu (Data Integrity):**", "- **Tính toàn vẹn dữ liệu:**"),
    ("dữ liệu tương lai (Lookahead Bias).", "dữ liệu tương lai."),
    ("- **Khả năng chịu lỗi và tự phục hồi (Fault Tolerance):**", "- **Khả năng chịu lỗi và tự phục hồi:**"),
    ("giãn mức chênh lệch giá (Spread Spikes),", "giãn mức chênh lệch giá,"),

    # Section 3.2
    ("ngăn xếp công nghệ (Technology Stack) hiện đại,", "ngăn xếp công nghệ hiện đại,"),
    ("xây dựng nguyên bản (native) cho Windows.", "xây dựng nguyên bản cho Windows."),
    ("kênh truyền thông liên tiến trình trực tiếp (Inter-Process Communication - IPC) qua vùng nhớ chia sẻ (Shared Memory)", "kênh truyền thông liên tiến trình trực tiếp IPC qua vùng nhớ chia sẻ"),
    ("xác suất Meta-Labeling (LightGBM):", "xác suất Meta-Labeling với LightGBM:"),
    ("thuật toán phân loại nhị phân LightGBM (Light Gradient Boosting Machine) do Ke et al.", "thuật toán cây quyết định tăng cường độ dốc LightGBM [12] do Ke et al."),
    ("mạng nơ-ron sâu (Deep Neural Networks),", "mạng nơ-ron sâu,"),
    ("thuật toán chia thùng dựa trên biểu đồ tần suất (Histogram-based)", "thuật toán chia thùng dựa trên biểu đồ tần suất"),
    ("dữ liệu dạng bảng (Tabular Data)", "dữ liệu dạng bảng"),
    ("mô hình kiến trúc hướng sự kiện (Event-Driven),", "mô hình kiến trúc hướng sự kiện,"),
    ("luồng giao diện đồ họa (GUI Thread)", "luồng giao diện đồ họa"),
    ("luồng tính toán định lượng (Worker Threads).", "luồng tính toán định lượng."),
    ("kỹ thuật vẽ lại vi sai (Incremental Repainting)", "kỹ thuật vẽ lại vi sai"),
    ("tranh chấp khóa tệp (Locking Contention) [13].", "tranh chấp khóa tệp [13]."),
    ("phục hồi trạng thái (State Recovery)", "phục hồi trạng thái"),
    ("tiến trình ghi (Risk Engine, Trade Logger)", "tiến trình quản trị rủi ro và ghi nhật ký lệnh"),

    # Section 3.3
    ("Cơ chế Điều phối Kép (Dual-Dispatch Architecture)", "Cơ chế Điều phối Kép"),
    ("### 3.3.1. Luồng Giao dịch Thuật toán Tự hành (Autonomous Algorithmic Stream)", "### 3.3.1. Luồng Giao dịch Thuật toán Tự hành"),
    ("### 3.3.2. Luồng Hỗ trợ Giao dịch Thủ công Thông minh (Smart Semi-Automated Stream)", "### 3.3.2. Luồng Hỗ trợ Giao dịch Thủ công Thông minh"),
    ("lệnh (Fat-finger Error) từ phía con người.", "lệnh do thao tác từ con người."),
    ("SQLite Write-Ahead Logging (WAL) để các", "SQLite WAL để các"),

    # Section 3.4
    ("thuật toán Cửa sổ trượt (Sliding Window Algorithm)", "thuật toán Cửa sổ trượt"),
    ("(In-place Rolling View)", "(cập nhật lăn tại chỗ)"),
    ("**Thuật toán Phục hồi Trạng thái (State Recovery Algorithm)**", "**Thuật toán Phục hồi Trạng thái**"),
    ("kiểm tra kết nối (Heartbeat Ping)", "kiểm tra kết nối định kỳ"),
    ("cầu dao ngắt mạch khẩn cấp (Circuit Breakers)", "cầu dao ngắt mạch khẩn cấp"),
    ("sụt giảm vốn ngày (Daily Drawdown Breaker):", "sụt giảm vốn ngày:"),
    ("chuỗi thua lỗ liên tiếp (Max Consecutive Losses):", "chuỗi thua lỗ liên tiếp:"),
    ("giao dịch trả thù (Revenge Trading).", "giao dịch trả thù."),
    ("độ giãn Spread (Spread Spike Breaker):", "độ giãn Spread:"),
    ("tin tức đỏ (High-Impact News Blackout):", "tin tức đỏ:"),

    # Section 3.5
    ("chỉ thị hệ thống (System Prompt)", "chỉ thị hệ thống"),
    ("trung lập (`NEUTRAL`),", "trung lập `NEUTRAL`,"),
    ("Lịch Kinh tế & Vĩ mô (Macro Calendar).", "Lịch Kinh tế & Vĩ mô."),
    ("Vĩ mô 4 trụ cột (Macro Bias Quad-Pillars):", "Vĩ mô 4 trụ cột:"),
    ("khẩu vị rủi ro toàn cầu (Risk-On / Risk-Off trích xuất từ chỉ số biến động VIX),", "khẩu vị rủi ro toàn cầu Risk-On hoặc Risk-Off từ biến động VIX,"),
    ("chính sách tiền tệ (Monetary Policy Bias từ chênh lệch lợi suất US10Y),", "chính sách tiền tệ từ chênh lệch lợi suất US10Y,"),
    ("thiên kiến hướng đi (Macro Bias)", "thiên kiến hướng đi"),
    ("hệ thống nhãn phẳng (Flat Badges)", "hệ thống nhãn phẳng"),
    ("Độ lệch chuẩn (Z-Score Deviation Table):", "Độ lệch chuẩn:"),
    ("Phòng vệ Sự kiện Bán tự động (Event Defense & News Guard Protocol):", "Phòng vệ Sự kiện Bán tự động:"),
    ("thời gian thực (Countdown Timer)", "thời gian thực"),
    ("phòng vệ tin tức (News Guard):", "phòng vệ tin tức:"),
    ("hòa vốn (Breakeven).", "hòa vốn."),
    ("ghi đè an toàn (Manual Override Switch)", "ghi đè an toàn"),

    # Section 3.6
    ("phi tập trung (OTC)", "phi tập trung OTC"),
    ("sổ lệnh tập trung cấp độ 2 (Level 2 Order Book),", "sổ lệnh tập trung Level 2,"),
    ("thanh nến (Bulk Volume Classification)", "thanh nến BVC"),
    ("giá đóng cửa (Session VWAP)", "giá đóng cửa Session VWAP"),

    # Section 3.7
    ("Kiểm toán Vĩ mô (Macro Audit):", "Kiểm toán Vĩ mô:"),
    ("theo quy ước cắm-rút (Convention-Based Plug-and-Play):", "theo quy ước cắm-rút:"),
    ("suy thoái mềm (Seamless Fallback):", "suy thoái mềm:"),

    # Section 3.8
    ("tỷ lệ cố định (Fixed Fractional Risk Model)", "tỷ lệ cố định"),
    ("khả dụng (Free Margin Check):", "khả dụng:"),

    # Section 3.9
    ("thiết kế phẳng định chế (Institutional Flat Design).", "thiết kế phẳng định chế."),
    ("vẽ vi sai hai lớp (Incremental Dual-Layer Painting)", "vẽ vi sai hai lớp"),
    ("đa tài sản (Multi-Asset Watchlist):", "đa tài sản:"),
    ("vĩ mô (Macro Bias Badge)", "vĩ mô"),
    ("thời gian thực (Trade Blotter Dock):", "thời gian thực:"),
    ("hai bước (Armed Flatten All / Kill-Switch)", "hai bước"),
    ("bán tự động (Semi-Automated / Copilot Trading),", "bán tự động,"),
    ("bảng điều khiển trượt (Sliding Drawer)", "bảng điều khiển trượt"),
    ("tín hiệu tự động (Auto Signals Review):", "tín hiệu tự động:"),
    ("thực thi (Full-Auto)", "thực thi tự động"),
    ("có trợ lực (Assisted Manual Order):", "có trợ lực:"),
    ("trước giao dịch (Pre-trade 4-Point Safety Checklist)", "trước giao dịch"),

    # Section 3.10
    ("Tab Backtest):", "Tab Backtest):"),
    ("đường cong vốn (Equity Curve)", "đường cong vốn"),
    ("sụt giảm tài khoản (Underwater Drawdown)", "đường chìm sụt giảm tài khoản"),
    ("Tab Performance Dashboard):", "Tab Performance Dashboard):"),
    ("hiệu suất (Performance Attribution),", "hiệu suất,"),
    ("Giao dịch (Monthly Trading Journal & PnL Heatmap Calendar):", "Giao dịch:"),
    ("Kiểm toán CSV (Trade History Blotter & CSV Exporter):", "Kiểm toán CSV:"),
    ("Mã vé lệnh (Ticket ID),", "Mã vé lệnh,"),
    ("Cặp tài sản (Symbol),", "Cặp tài sản,"),
    ("Chiều lệnh (Side),", "Chiều lệnh,"),
    ("chạy (Pips),", "chạy tính theo pips,"),
    ("Lợi nhuận ròng (Net PnL).", "Lợi nhuận ròng."),
    ("Đường chìm Sụt giảm Kép (Dual Equity Growth & Underwater Drawdown Canvas):", "Đường chìm Sụt giảm Kép:"),
    ("Đường cong Vốn (Equity Growth Curve):", "Đường cong Vốn:"),
    ("Đường chìm Sụt giảm (Underwater Drawdown %):", "Đường chìm Sụt giảm:"),
    ("Rủi ro Định chế (Institutional Core Performance Metrics Panel):", "Rủi ro Định chế:"),
    ("theo rủi ro (Risk-Adjusted Performance):", "theo rủi ro:"),
    ("Tỷ số Sharpe (Sharpe Ratio),", "Tỷ số Sharpe,"),
    ("Tỷ số Sortino (đo lường độ lệch chuẩn của phần rủi ro giảm giá Downside Deviation),", "Tỷ số Sortino (đo lường độ lệch chuẩn của phần rủi ro giảm giá),"),
    ("Tỷ số Calmar (tỷ lệ Lợi nhuận ròng trên Max Drawdown),", "Tỷ số Calmar,"),
    ("Hệ số Lãi/Lỗ (Profit Factor),", "Hệ số Lãi/Lỗ Profit Factor,"),
    ("Rủi ro Sụt giảm (Capital & Risk Metrics):", "Rủi ro Sụt giảm:"),
    ("Mức sụt giảm tối đa (Max Drawdown),", "Mức sụt giảm tối đa,"),
    ("chịu sụt giảm (DD Duration),", "chịu sụt giảm,"),
    ("hồi vốn (Recovery Factor),", "hồi vốn,"),
    ("ký quỹ (Margin Level).", "ký quỹ."),
    ("Giao dịch (Trading Performance):", "Giao dịch:"),
    ("Tỷ lệ thắng (Win Rate),", "Tỷ lệ thắng,"),
    ("giao dịch (Total Trades),", "giao dịch,"),
    ("lệnh thắng (Avg Winning Trade),", "lệnh thắng,"),
    ("lệnh thua (Avg Losing Trade),", "lệnh thua,"),
    ("mỗi giao dịch (Expectancy),", "mỗi giao dịch,"),
    ("thắng/thua dài nhất (Max Win/Loss Streak).", "thắng/thua dài nhất."),
    ("Tài chính (Financial Summary):", "Tài chính:"),
    ("Lãi gộp (Gross Profit),", "Lãi gộp,"),
    ("Lỗ gộp (Gross Loss),", "Lỗ gộp,"),
    ("ròng thực tế (Net Profit).", "ròng thực tế."),
    ("Giao dịch (Direction & Session Breakdown):", "Giao dịch:"),
    ("vị thế Mua/Bán (Long/Short)", "vị thế Mua và Bán"),
    ("thanh khoản (Asian Session, London Session, New York Session).", "thanh khoản bao gồm phiên Á, phiên Âu và phiên Mỹ.")
]

count = 0
for old, new in replacements:
    if old in txt:
        txt = txt.replace(old, new)
        count += 1
    else:
        print(f"NOT FOUND: {old[:40]}")

p.write_text(txt, encoding="utf-8")
print(f"Cleaned {count} items in Chapter 3!")
