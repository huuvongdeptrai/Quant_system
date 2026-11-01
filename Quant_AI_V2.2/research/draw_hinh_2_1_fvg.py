# -*- coding: utf-8 -*-
"""
GENERATE FIGURE 2.1: MICROSTRUCTURE FAIR VALUE GAP (FVG) GEOMETRY & RE-TEST
Outputs:
1. docs/thesis/images/hinh_2_1_fvg_imbalance.png (300 DPI Academic Print White)
2. docs/thesis/images/hinh_2_1_fvg_imbalance_dark.png (300 DPI Institutional Dark)
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "docs" / "thesis" / "images"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def draw_fvg_diagram(dark_mode=False):
    fig, ax = plt.subplots(figsize=(10, 6.2), dpi=300)
    
    # Palette
    if dark_mode:
        bg_fig = "#070a12"
        bg_ax = "#090d16"
        text_primary = "#f8fafc"
        text_secondary = "#94a3b8"
        border_color = "rgba(255, 255, 255, 0.08)"
        grid_color = "#1e293b"
        green_candle = "#22c55e"
        red_candle = "#ef4444"
        fvg_color = "#3b82f6"
        fvg_alpha = 0.22
        line_color = "#60a5fa"
        retest_line = "#e2e8f0"
    else:
        bg_fig = "#ffffff"
        bg_ax = "#fafafa"
        text_primary = "#0f172a"
        text_secondary = "#475569"
        border_color = "#cbd5e1"
        grid_color = "#f1f5f9"
        green_candle = "#16a34a"
        red_candle = "#dc2626"
        fvg_color = "#2563eb"
        fvg_alpha = 0.16
        line_color = "#1d4ed8"
        retest_line = "#334155"

    fig.patch.set_facecolor(bg_fig)
    ax.set_facecolor(bg_ax)

    # Candlestick coordinates: (x, open, high, low, close, color)
    candles = [
        # Candle 1: t-1 (Small bullish candle)
        (1.0, 100.0, 104.0, 98.0, 103.0, green_candle),
        # Candle 2: t (Large displacement candle)
        (2.2, 103.5, 122.0, 102.5, 120.0, green_candle),
        # Candle 3: t+1 (Small indecision candle)
        (3.4, 120.5, 123.0, 112.0, 121.5, green_candle),
        # Candle 4: t+2 (Pullback 1)
        (4.6, 121.5, 122.0, 114.0, 115.0, red_candle),
        # Candle 5: t+3 (Re-test candle dipping into FVG zone)
        (5.8, 115.0, 116.0, 106.0, 112.0, red_candle),
        # Candle 6: t+4 (Strong bounce away from FVG)
        (7.0, 112.0, 125.0, 111.0, 124.0, green_candle),
    ]

    width = 0.45

    for x, o, h, l, c, col in candles:
        # Wick
        ax.plot([x, x], [l, h], color=col, linewidth=1.8, zorder=2)
        # Body
        body_bottom = min(o, c)
        body_height = abs(c - o)
        rect = patches.Rectangle((x - width/2, body_bottom), width, body_height,
                                 facecolor=col, edgecolor=col, linewidth=1.2, zorder=3)
        ax.add_patch(rect)

    # Key FVG Boundaries
    # Candle 1 high: 104.0
    p_high_t_minus_1 = 104.0
    # Candle 3 low: 112.0
    p_low_t_plus_1 = 112.0
    gap_size = p_low_t_plus_1 - p_high_t_minus_1 # 8.0 points

    # Draw FVG Box from x=1.0 to x=6.5
    fvg_box = patches.Rectangle((1.0, p_high_t_minus_1), 5.3, gap_size,
                                facecolor=fvg_color, alpha=fvg_alpha,
                                edgecolor=line_color, linestyle="--", linewidth=1.5, zorder=1)
    ax.add_patch(fvg_box)

    # Dashed Boundary Lines
    ax.axhline(p_high_t_minus_1, xmin=0.1, xmax=0.65, color=line_color, linestyle=":", linewidth=1.2)
    ax.axhline(p_low_t_plus_1, xmin=0.35, xmax=0.65, color=line_color, linestyle=":", linewidth=1.2)

    # Annotations
    # Candle labels
    ax.text(1.0, 95.0, "Nến t - 1\n(Nến chuẩn)", ha="center", va="top", fontsize=9.5, fontweight="bold", color=text_secondary)
    ax.text(2.2, 95.0, "Nến t\n(Bứt phá mạnh)", ha="center", va="top", fontsize=9.5, fontweight="bold", color=green_candle)
    ax.text(3.4, 95.0, "Nến t + 1\n(Xác nhận)", ha="center", va="top", fontsize=9.5, fontweight="bold", color=text_secondary)
    ax.text(5.8, 95.0, "Nến t + 3\n(Kiểm định FVG)", ha="center", va="top", fontsize=9.5, fontweight="bold", color=retest_line)

    # Boundary callouts
    ax.annotate(r"$P_{\mathrm{low}}(t+1) = 112.0$", xy=(3.4, p_low_t_plus_1), xytext=(3.8, 114.5),
                arrowprops=dict(arrowstyle="->", color=line_color, lw=1.2),
                fontsize=9.5, fontweight="bold", color=text_primary)
    
    ax.annotate(r"$P_{\mathrm{high}}(t-1) = 104.0$", xy=(1.0, p_high_t_minus_1), xytext=(0.3, 106.0),
                arrowprops=dict(arrowstyle="->", color=line_color, lw=1.2),
                fontsize=9.5, fontweight="bold", color=text_primary)

    # FVG Box Label
    ax.text(2.6, 108.0, "VÙNG MẤT CÂN BẰNG THANH KHOẢN (FAIR VALUE GAP)\n" +
            r"$\mathrm{Gap}_{\mathrm{bullish}}(t) = P_{\mathrm{low}}(t+1) - P_{\mathrm{high}}(t-1) > \epsilon$",
            ha="center", va="center", fontsize=9.0, fontweight="bold", color=line_color,
            bbox=dict(boxstyle="square,pad=0.4", facecolor=bg_ax, edgecolor=line_color, alpha=0.9))

    # Re-test and bounce annotation
    ax.annotate("Pha hồi quy kiểm định thanh khoản (Re-test)\nKhối lượng bán bị hấp thụ, giá bật tăng tiếp",
                xy=(5.8, 106.0), xytext=(5.0, 100.0),
                arrowprops=dict(arrowstyle="->", color=green_candle, lw=1.5),
                fontsize=9.0, fontweight="bold", color=text_primary)

    # Title & Subtitle
    title_text = "HÌNH 2.1: SƠ ĐỒ HÌNH HỌC VI CẤU TRÚC KHOẢNG TRỐNG THANH KHOẢN (FAIR VALUE GAP)"
    sub_text = "Mô hình xác thực 3 nến liên tiếp và cơ chế hồi quy kiểm định (Re-test) của dòng tiền định chế"
    fig.text(0.5, 0.95, title_text, ha="center", fontsize=11.5, fontweight="bold", color=text_primary)
    fig.text(0.5, 0.91, sub_text, ha="center", fontsize=9.5, color=text_secondary)

    ax.set_xlim(0.0, 8.0)
    ax.set_ylim(92.0, 130.0)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color(border_color if not dark_mode else "#1e293b")
        spine.set_linewidth(1.0)

    plt.tight_layout(rect=[0.02, 0.03, 0.98, 0.89])
    
    filename = "hinh_2_1_fvg_imbalance_dark.png" if dark_mode else "hinh_2_1_fvg_imbalance.png"
    out_path = OUTPUT_DIR / filename
    plt.savefig(out_path, dpi=300, facecolor=bg_fig, edgecolor="none")
    plt.close()
    print(f"Generated: {out_path}")

if __name__ == "__main__":
    draw_fvg_diagram(dark_mode=False)
    draw_fvg_diagram(dark_mode=True)
