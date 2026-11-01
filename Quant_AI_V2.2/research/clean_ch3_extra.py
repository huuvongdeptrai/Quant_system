# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

p = Path("Kho_Do_An/Quant_AI_V2.2/docs/thesis/chuong_3_thiet_ke_he_thong.md")
txt = p.read_text(encoding="utf-8")

reps = [
    ("(Deep Neural Networks)", ""),
    ("(Histogram-based)", ""),
    ("(Worker Threads)", ""),
    ("(Locking Contention) [13]", "[13]"),
    ("(State Recovery)", ""),
    ("(Direction & Session Breakdown):", ":"),
    ("### 3.10.1. Kiểm thử chiến lược trên dữ liệu lịch sử (Tab Backtest)", "### 3.10.1. Kiểm thử chiến lược trên dữ liệu lịch sử"),
    ("### 3.10.2. Phân tích hiệu suất và nhật ký định lượng (Tab Performance Dashboard)", "### 3.10.2. Phân tích hiệu suất và nhật ký định lượng"),
    ("(Tab Backtest)", ""),
    ("(Pre-trade Safety Drawer)", ""),
    ("(Tab Performance Dashboard)", ""),
    ("(Trade History Blotter & CSV Exporter)", ""),
    ("(Monthly Trading Journal & PnL Heatmap Calendar)", ""),
    ("thông qua liên tiến trình (IPC)", "thông qua liên tiến trình IPC"),
    ("khung hình cao (60 FPS)", "khung hình cao 60 FPS"),
]

for old, new in reps:
    if old in txt:
        txt = txt.replace(old, new)
        print(f"Replaced: {old}")

p.write_text(txt, encoding="utf-8")
print("Done Ch3 extra clean.")
