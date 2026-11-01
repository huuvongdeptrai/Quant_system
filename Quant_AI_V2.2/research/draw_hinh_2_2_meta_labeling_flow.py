# -*- coding: utf-8 -*-
"""
GENERATE FIGURE 2.2: TWO-TIER META-LABELING DECISION FLOW (MARCOS LÓPEZ DE PRADO)
Outputs:
1. docs/thesis/images/hinh_2_2_meta_labeling_flow.png (300 DPI Academic Print White)
2. docs/thesis/images/hinh_2_2_meta_labeling_flow_dark.png (300 DPI Institutional Dark)
"""

import sys
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, ArrowStyle

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def draw_diagram(dark=False):
    bg_color = "#090d16" if dark else "#ffffff"
    card_bg = "#101524" if dark else "#f8fafc"
    text_color = "#f1f5f9" if dark else "#0f172a"
    subtext_color = "#94a3b8" if dark else "#475569"
    border_color = "#1e293b" if dark else "#cbd5e1"
    
    # Accent colors
    c_blue = "#0284c7" if not dark else "#38bdf8"
    c_green = "#16a34a" if not dark else "#4ade80"
    c_purple = "#7c3aed" if not dark else "#a78bfa"
    c_red = "#dc2626" if not dark else "#f87171"
    c_amber = "#d97706" if not dark else "#fbbf24"

    fig, ax = plt.subplots(figsize=(12, 7.5), dpi=300)
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    # Title
    ax.text(50, 96, "HÌNH 2.2: SƠ ĐỒ LUỒNG QUYẾT ĐỊNH HAI TẦNG CỦA KIẾN TRÚC HỌC MÁY META-LABELING",
            ha="center", va="center", fontsize=12, fontweight="bold", color=text_color)
    ax.text(50, 92.5, "Phương pháp luận Marcos López de Prado (Advances in Financial Machine Learning, 2018)",
            ha="center", va="center", fontsize=10, style="italic", color=subtext_color)

    def draw_box(x, y, w, h, title, subtitle, items, border_c, bg_c=card_bg, title_c=text_color):
        box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.5,rounding_size=1.5",
                             ec=border_c, fc=bg_c, lw=1.5)
        ax.add_patch(box)
        ax.text(x + w/2, y + h - 3, title, ha="center", va="center", fontsize=9.5, fontweight="bold", color=title_c)
        if subtitle:
            ax.text(x + w/2, y + h - 6.5, subtitle, ha="center", va="center", fontsize=8.5, style="italic", color=subtext_color)
        
        curr_y = y + h - (10.5 if subtitle else 7.5)
        for item in items:
            ax.text(x + 2.5, curr_y, item, ha="left", va="center", fontsize=8.2, color=text_color)
            curr_y -= 4.0

    # 1. INPUT
    draw_box(3, 62, 22, 24, "DỮ LIỆU ĐẦU VÀO", "Market & Microstructure", [
        "- Chuỗi nến M15 OHLCV",
        "- Khối lượng Tick Volume (V)",
        "- Chênh lệch giá mua/bán (Spread)",
        "- 11 Đặc trưng vi cấu trúc Xt"
    ], c_blue, card_bg, c_blue)

    # 2. TIER 1: PRIMARY MODEL
    draw_box(32, 62, 30, 24, "TẦNG 1: MÔ HÌNH SƠ CẤP", "(Primary Heuristic / Rule-based Model)", [
        "- Nhận diện FVG & Wyckoff VSA",
        "- Mục tiêu: Tối đa hóa Recall (High Recall)",
        "- Quyết định hướng: y_primary in {-1, 0, +1}",
        "- Chấp nhận phát sinh nhiều tín hiệu giả"
    ], c_blue, card_bg, c_blue)

    # 3. TRIPLE BARRIER METHOD
    draw_box(69, 62, 28, 24, "PHƯƠNG PHÁP GÁN NHÃN", "(Triple-Barrier Method [Prado, 2018])", [
        "- Rào trên (TP): +2.5 ATR",
        "- Rào dưới (SL): -1.0 ATR",
        "- Rào thời gian: H = 20 nến",
        "- Gán nhãn học máy: z in {0, 1}"
    ], c_amber, card_bg, c_amber)

    # 4. TIER 2: SECONDARY META-MODEL
    draw_box(32, 16, 30, 36, "TẦNG 2: MÔ HÌNH HỌC MÁY THỨ CẤP", "(Meta-Model / Binary LightGBM Classifier)", [
        "- Không can thiệp vào hướng vào lệnh",
        "- Dự báo xác suất thành công:",
        "    P(z = 1 | Xt, y_primary)",
        "- Không gian 11 đặc trưng vi cấu trúc:",
        "    * Biến động Garman-Klass (gk_vol)",
        "    * Dòng tiền tích lũy (cvd_proxy)",
        "    * Độ lệch chuẩn Session VWAP",
        "    * Khoảng trống cản cứng (headroom)",
        "- Mục tiêu: Tối ưu độ chính xác (Precision)"
    ], c_purple, card_bg, c_purple)

    # 5. DECISION GATE & BET SIZING
    draw_box(69, 16, 28, 36, "CỔNG ĐỊNH CỠ VỊ THẾ & DUYỆT", "(Bet Sizing & Decision Gate)", [
        "- Ngưỡng phê duyệt: P >= 0.38",
        "- Điều kiện định cỡ vị thế:",
        "    * Nếu P < 0.38: Size = 0 (Hủy)",
        "    * Nếu P >= 0.38: Size = 1% Vốn",
        "- Kiểm định ngoài mẫu chặt chẽ:",
        "    * Purging & Embargoing",
        "    * Expanding Walk-Forward OOS",
        "- Nén Max Drawdown: 39.4% -> 7.46%"
    ], c_green, card_bg, c_green)

    # Arrows
    def draw_arrow(x1, y1, x2, y2, label="", color=subtext_color, style="->", lw=1.5):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle=style, color=color, lw=lw, shrinkA=3, shrinkB=3))
        if label:
            mx, my = (x1 + x2)/2, (y1 + y2)/2
            ax.text(mx, my + 1.8, label, ha="center", va="center", fontsize=8, fontweight="bold",
                    color=color, bbox=dict(boxstyle="round,pad=0.2", fc=bg_color, ec="none", alpha=0.85))

    draw_arrow(25, 74, 32, 74, "Dữ liệu nến", c_blue)
    draw_arrow(62, 74, 69, 74, "Tín hiệu sơ cấp", c_amber)
    draw_arrow(83, 62, 83, 52, "Nhãn huấn luyện z in {0,1}", c_amber)
    draw_arrow(83, 52, 62, 40, "", c_amber)

    draw_arrow(14, 62, 14, 34, "11 Đặc trưng Xt", c_purple)
    draw_arrow(14, 34, 32, 34, "", c_purple)

    draw_arrow(62, 30, 69, 30, "Xác suất P", c_purple)

    # Out results
    draw_box(69, 2, 13, 8, "LỌC BỎ TÍN HIỆU", "", ["P < 0.38: Bẫy giá"], c_red, "#fef2f2" if not dark else "#450a0a", c_red)
    draw_box(84, 2, 13, 8, "VÀO LỆNH AN TOÀN", "", ["P >= 0.38: Khớp lệnh"], c_green, "#f0fdf4" if not dark else "#052e16", c_green)

    draw_arrow(75.5, 16, 75.5, 10, "Từ chối", c_red)
    draw_arrow(90.5, 16, 90.5, 10, "Chấp thuận", c_green)

    plt.tight_layout()
    out_name = "hinh_2_2_meta_labeling_flow_dark.png" if dark else "hinh_2_2_meta_labeling_flow.png"
    out_path = PROJECT_ROOT / "docs" / "thesis" / "images" / out_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out_path), dpi=300, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    print(f"[V] Exported: {out_path}")
    return out_path

draw_diagram(dark=False)
draw_diagram(dark=True)
print("Figure 2.2 diagrams generated successfully!")
