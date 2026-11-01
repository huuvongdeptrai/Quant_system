# -*- coding: utf-8 -*-
"""
GENERATE FIGURE 2.2: WYCKOFF ACCUMULATION PHASES & EFFORT VS RESULT PRINCIPLE
Outputs:
1. docs/thesis/images/hinh_2_2_wyckoff_schematic.png (300 DPI Academic Print White)
2. docs/thesis/images/hinh_2_2_wyckoff_schematic_dark.png (300 DPI Institutional Dark)
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "docs" / "thesis" / "images"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def draw_wyckoff_diagram(dark_mode=False):
    fig, (ax_price, ax_vol) = plt.subplots(2, 1, figsize=(11, 7.0), dpi=300,
                                           gridspec_kw={"height_ratios": [3.2, 1.2], "hspace": 0.08})
    
    # Palette
    if dark_mode:
        bg_fig = "#070a12"
        bg_ax = "#090d16"
        text_primary = "#f8fafc"
        text_secondary = "#94a3b8"
        border_color = "#1e293b"
        grid_color = "#151c2e"
        price_line = "#38bdf8"
        spring_color = "#ef4444"
        markup_color = "#22c55e"
        vol_normal = "#475569"
        vol_spike = "#f59e0b"
        range_bg = "rgba(59, 130, 246, 0.06)"
    else:
        bg_fig = "#ffffff"
        bg_ax = "#fafafa"
        text_primary = "#0f172a"
        text_secondary = "#475569"
        border_color = "#cbd5e1"
        grid_color = "#f1f5f9"
        price_line = "#0284c7"
        spring_color = "#dc2626"
        markup_color = "#16a34a"
        vol_normal = "#94a3b8"
        vol_spike = "#d97706"
        range_bg = "#f0f9ff"

    fig.patch.set_facecolor(bg_fig)
    for ax in (ax_price, ax_vol):
        ax.set_facecolor(bg_ax)

    # 1. Price Curve Construction (Phases A, B, C, D, E)
    # Phase A: Downtrend -> SC (10) -> AR (25) -> ST (35)
    # Phase B: Range fluctuation (35 -> 70)
    # Phase C: Spring (75) dipping below support
    # Phase D: SOS (85) -> LPS (95)
    # Phase E: Markup (100 -> 120)
    t = np.linspace(0, 120, 300)
    
    # Piecewise price trajectory
    pts_x = [0,  8, 15, 23, 30, 40, 50, 60, 68, 75, 82, 90, 98, 108, 120]
    pts_y = [118, 92, 88, 104, 91, 102, 90, 100, 92, 83, 102, 109, 101, 116, 128]
    # Interpolate smooth trajectory
    from scipy.interpolate import make_interp_spline
    spl = make_interp_spline(pts_x, pts_y, k=3)
    t_smooth = np.linspace(0, 120, 400)
    y_smooth = spl(t_smooth)

    # Trading Range Support & Resistance lines
    tr_res = 104.0
    tr_sup = 89.0
    ax_price.axhline(tr_res, color=border_color, linestyle="--", linewidth=1.2)
    ax_price.axhline(tr_sup, color=border_color, linestyle="--", linewidth=1.2)
    
    # Plot trading range background
    ax_price.axhspan(tr_sup, tr_res, color="#3b82f6", alpha=0.04, zorder=0)

    # Plot Price Curve
    ax_price.plot(t_smooth, y_smooth, color=price_line, linewidth=2.2, zorder=3)

    # Labels for Support & Resistance
    ax_price.text(1, tr_res + 1.0, "Ngưỡng kháng cự tích lũy (Resistance / TR High)", fontsize=8.5, color=text_secondary, fontweight="bold")
    ax_price.text(1, tr_sup - 2.5, "Ngưỡng hỗ trợ tích lũy (Support / TR Low)", fontsize=8.5, color=text_secondary, fontweight="bold")

    # Phase Delimiters
    phases = [
        (0, 32, "Pha A\nChặn đà giảm", "Dừng xu hướng giảm\n(SC, AR, ST)"),
        (32, 70, "Pha B\nXây dựng nguyên nhân", "Hấp thụ cung cầu\ntrong biên độ"),
        (70, 82, "Pha C\nThanh lọc (Spring)", "Kiểm định bẫy bán lẻ\n(Bẫy phá vỡ giả)"),
        (82, 102, "Pha D\nXung lực bứt phá", "Xác nhận tăng trưởng\n(SOS & LPS)"),
        (102, 120, "Pha E\nĐẩy giá (Markup)", "Xu hướng tăng giá\nđịnh chế bền vững")
    ]

    for x_start, x_end, p_title, p_desc in phases:
        if x_start > 0:
            ax_price.axvline(x_start, color=border_color, linestyle=":", linewidth=1.0)
            ax_vol.axvline(x_start, color=border_color, linestyle=":", linewidth=1.0)
        ax_price.text((x_start + x_end)/2, 125.0, p_title, ha="center", va="top",
                      fontsize=9.0, fontweight="bold", color=text_primary)

    # Wyckoff Milestones Callouts
    milestones = [
        (15, 88, "SC (Selling Climax)", -10, text_secondary),
        (23, 104, "AR (Automatic Rally)", 8, text_secondary),
        (30, 91, "ST (Secondary Test)", -10, text_secondary),
        (75, 83, "SPRING / SHAKEOUT\n(Bẫy giảm vi cấu trúc)", -18, spring_color),
        (90, 109, "SOS (Sign of Strength)", 8, markup_color),
        (98, 101, "LPS (Last Point Support)", -10, markup_color)
    ]

    for mx, my, mlabel, offset_y, mcol in milestones:
        ax_price.plot(mx, my, "o", color=mcol, markersize=5, zorder=4)
        ax_price.annotate(mlabel, xy=(mx, my), xytext=(mx, my + offset_y),
                          ha="center", fontsize=8.2, fontweight="bold", color=mcol,
                          arrowprops=dict(arrowstyle="->", color=mcol, lw=1.0))

    # 2. Volume Profile & Effort vs Result in Lower Pane
    vol_x = np.linspace(2, 118, 40)
    vol_y = np.random.uniform(20, 45, 40)
    # SC volume spike at x=15
    vol_y[np.argmin(np.abs(vol_x - 15))] = 95.0
    # Spring absorption spike at x=75
    idx_spring = np.argmin(np.abs(vol_x - 75))
    vol_y[idx_spring] = 85.0
    # SOS breakout spike at x=90
    idx_sos = np.argmin(np.abs(vol_x - 90))
    vol_y[idx_sos] = 90.0

    bar_colors = [vol_spike if y > 70 else vol_normal for y in vol_y]
    ax_vol.bar(vol_x, vol_y, width=2.0, color=bar_colors, alpha=0.85, zorder=2)
    
    # Effort vs Result annotation at Spring (x=75)
    ax_vol.annotate("HẤP THỤ THANH KHOẢN (EFFORT > RESULT)\n" +
                    r"Khối lượng đột biến ($R_{\mathrm{eff}} > \mu_R + 2\sigma_R$) nhưng thân nến hẹp",
                    xy=(75, 85), xytext=(55, 65),
                    arrowprops=dict(arrowstyle="->", color=spring_color, lw=1.2),
                    fontsize=8.2, fontweight="bold", color=text_primary,
                    bbox=dict(boxstyle="square,pad=0.3", facecolor=bg_ax, edgecolor=spring_color, alpha=0.9))

    # Styling Axes
    ax_price.set_xlim(0, 122)
    ax_price.set_ylim(60, 132)
    ax_price.set_ylabel("Mức giá (Price Axis)", fontsize=9.5, fontweight="bold", color=text_primary)
    ax_price.set_xticks([])
    ax_price.set_yticks([])

    ax_vol.set_xlim(0, 122)
    ax_vol.set_ylim(0, 110)
    ax_vol.set_ylabel("Khối lượng\n(Volume)", fontsize=9.0, fontweight="bold", color=text_primary)
    ax_vol.set_xlabel("Thời gian và Trình tự các Pha Tích lũy (Time / Sequence)", fontsize=9.5, fontweight="bold", color=text_primary)
    ax_vol.set_xticks([])
    ax_vol.set_yticks([])

    for ax in (ax_price, ax_vol):
        for spine in ax.spines.values():
            spine.set_color(border_color)
            spine.set_linewidth(1.0)

    # Title & Subtitle
    title_text = "HÌNH 2.2: SƠ ĐỒ CẤU TRÚC PHA VÀ NGUYÊN LÝ NỖ LỰC - KẾT QUẢ THEO PHƯƠNG PHÁP WYCKOFF"
    sub_text = "Quá trình tích lũy 5 pha (A - E) kết hợp nhận diện điểm bẫy thanh khoản (Spring) qua tỷ số Nỗ lực / Kết quả"
    fig.text(0.5, 0.96, title_text, ha="center", fontsize=11.5, fontweight="bold", color=text_primary)
    fig.text(0.5, 0.925, sub_text, ha="center", fontsize=9.5, color=text_secondary)

    plt.tight_layout(rect=[0.02, 0.03, 0.98, 0.91])
    
    filename = "hinh_2_2_wyckoff_schematic_dark.png" if dark_mode else "hinh_2_2_wyckoff_schematic.png"
    out_path = OUTPUT_DIR / filename
    plt.savefig(out_path, dpi=300, facecolor=bg_fig, edgecolor="none")
    plt.close()
    print(f"Generated: {out_path}")

if __name__ == "__main__":
    draw_wyckoff_diagram(dark_mode=False)
    draw_wyckoff_diagram(dark_mode=True)
