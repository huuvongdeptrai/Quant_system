"""
Generate Publication-Quality Architecture Diagram of the DUAL-STREAM PIPELINE
(Luồng Tự Hành + Luồng Thủ Công Thông Minh) for the Graduation Thesis (VECTRA).
Outputs:
1. docs/thesis/images/hinh_3_1_kien_truc_dieu_phoi_kep.png (Academic Print Edition)
2. docs/thesis/images/hinh_3_1_kien_truc_dieu_phoi_kep_dark.png (Institutional Dark Edition)
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from pathlib import Path

OUTPUT_DIR = Path("Kho_Do_An/Quant_AI_V2.2/docs/thesis/images")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def draw_dual_stream(dark_mode=False, output_path=None):
    # Figure size: 18x20 inches for extreme clarity and detail
    fig, ax = plt.subplots(figsize=(19, 21), dpi=300)

    # Color Palette
    if dark_mode:
        bg_color = "#070a13"
        box_bg = "#0d1322"
        box_border = "#1e293b"
        header_bg = "#151e32"
        text_primary = "#f1f5f9"
        text_secondary = "#94a3b8"
        accent_blue = "#38bdf8"
        accent_purple = "#a855f7"
        accent_green = "#22c55e"
        accent_red = "#ef4444"
        reject_bg = "#1a1219"
        reject_border = "#7f1d1d"
        success_bg = "#0f2019"
        success_border = "#166534"
        manual_bg = "#161329"
        manual_border = "#6b21a8"
    else:
        bg_color = "#ffffff"
        box_bg = "#f8fafc"
        box_border = "#cbd5e1"
        header_bg = "#e2e8f0"
        text_primary = "#0f172a"
        text_secondary = "#334155"
        accent_blue = "#0284c7"
        accent_purple = "#7e22ce"
        accent_green = "#16a34a"
        accent_red = "#dc2626"
        reject_bg = "#fef2f2"
        reject_border = "#fca5a5"
        success_bg = "#f0fdf4"
        success_border = "#86efac"
        manual_bg = "#faf5ff"
        manual_border = "#d8b4fe"

    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    font_family = "Segoe UI"

    # =========================================================================
    # TOP HEADER: TỔNG QUAN KIẾN TRÚC ĐIỀU PHỐI KÉP (DUAL-DISPATCH ARCHITECTURE)
    # =========================================================================
    top_box = patches.FancyBboxPatch(
        (4, 93.5), 92, 5.2,
        boxstyle="round,pad=0.2,rounding_size=0.5",
        edgecolor=accent_blue, facecolor=box_bg, linewidth=2
    )
    ax.add_patch(top_box)
    ax.text(50, 96.6, "KIẾN TRÚC PHÂN TẦNG PHÒNG VỆ 5 LỚP KẾT HỢP CƠ CHẾ ĐIỀU PHỐI KÉP (DUAL-DISPATCH)",
            ha='center', va='center', fontsize=13, fontweight='bold',
            color=accent_blue, fontfamily=font_family)
    ax.text(50, 94.6, "Phân tách độc lập 2 luồng: Thuật toán Tự hành (Auto) & Hỗ trợ Thủ công Thông minh (Semi-Auto) — Chung lõi Quản trị Rủi ro Tầng 5",
            ha='center', va='center', fontsize=9.2,
            color=text_secondary, fontfamily=font_family)

    # =========================================================================
    # CỘT TRÁI: LUỒNG 1 - GIAO DỊCH THUẬT TOÁN TỰ HÀNH (AUTONOMOUS STREAM)
    # Width: 46%, X: 4 to 50
    # =========================================================================

    # Ingress Banner Left
    in_left = patches.FancyBboxPatch(
        (4, 85.5), 45, 5.5,
        boxstyle="round,pad=0.2,rounding_size=0.4",
        edgecolor=accent_blue, facecolor=box_bg, linewidth=1.8
    )
    ax.add_patch(in_left)
    ax.text(26.5, 89.0, "LUỒNG 1: GIAO DỊCH THUẬT TOÁN TỰ HÀNH",
            ha='center', va='center', fontsize=10.5, fontweight='bold',
            color=accent_blue, fontfamily=font_family)
    ax.text(26.5, 87.0, "Dòng dữ liệu giá thời gian thực từ MetaTrader 5 (Tick Stream, M15 OHLCV)",
            ha='center', va='center', fontsize=8.2,
            color=text_secondary, fontfamily=font_family)

    # Connecting Arrow
    ax.annotate("", xy=(26.5, 80.5), xytext=(26.5, 85.5),
                arrowprops=dict(arrowstyle="-|>", color=accent_blue, lw=1.8, mutation_scale=12))

    # TẦNG 1 (Cột trái)
    t1_box = patches.FancyBboxPatch(
        (4, 71.5), 33, 9.0,
        boxstyle="round,pad=0.2,rounding_size=0.4",
        edgecolor=box_border, facecolor=box_bg, linewidth=1.4
    )
    ax.add_patch(t1_box)
    t1_hbar = patches.FancyBboxPatch(
        (4, 78.0), 33, 2.5,
        boxstyle="round,pad=0.2,rounding_size=0.4",
        edgecolor=box_border, facecolor=header_bg, linewidth=1.0
    )
    ax.add_patch(t1_hbar)
    ax.text(5.5, 79.2, "TẦNG 1: AN TOÀN NGOẠI VI (AUTO)", fontsize=8.5, fontweight='bold', color=accent_blue, fontfamily=font_family, va='center')
    t1_items = [
        "Kiểm tra nhịp tim mạng (Heartbeat < 15s)",
        "Độ giãn Spread vi mô (Spread < 35 points)",
        "Cầu dao sụt giảm vốn ngày (Daily DD < 5%)",
        "Số chuỗi lệnh thua tối đa (Max Losses <= 3)"
    ]
    for idx, it in enumerate(t1_items):
        ax.plot(5.5, 76.5 - idx * 1.5, marker='s', markersize=3, color=accent_blue)
        ax.text(7.0, 76.5 - idx * 1.5, it, fontsize=7.6, color=text_secondary, fontfamily=font_family, va='center')

    # T1 Rejection
    t1_rej = patches.FancyBboxPatch(
        (38.5, 72.0), 10.5, 6.0,
        boxstyle="round,pad=0.2,rounding_size=0.3",
        edgecolor=reject_border, facecolor=reject_bg, linewidth=1.2
    )
    ax.add_patch(t1_rej)
    ax.text(43.75, 75.8, "NGẮT CẦU DAO", fontsize=7.5, fontweight='bold', color=accent_red, fontfamily=font_family, ha='center')
    ax.text(43.75, 73.8, "Dừng tự động\nBắn Telegram", fontsize=7.0, color=text_secondary, fontfamily=font_family, ha='center')
    ax.annotate("", xy=(38.5, 75.0), xytext=(37.0, 75.0),
                arrowprops=dict(arrowstyle="-|>", color=accent_red, lw=1.2, mutation_scale=10))

    # Arrow T1 -> T2
    ax.annotate("", xy=(20.5, 66.5), xytext=(20.5, 71.5),
                arrowprops=dict(arrowstyle="-|>", color=accent_green, lw=1.8, mutation_scale=12))
    ax.text(21.5, 69.0, "An toàn vốn đạt chuẩn", fontsize=7.5, fontweight='bold', color=accent_green, fontfamily=font_family, va='center')

    # TẦNG 2 (Cột trái)
    t2_box = patches.FancyBboxPatch(
        (4, 57.5), 33, 9.0,
        boxstyle="round,pad=0.2,rounding_size=0.4",
        edgecolor=box_border, facecolor=box_bg, linewidth=1.4
    )
    ax.add_patch(t2_box)
    t2_hbar = patches.FancyBboxPatch(
        (4, 64.0), 33, 2.5,
        boxstyle="round,pad=0.2,rounding_size=0.4",
        edgecolor=box_border, facecolor=header_bg, linewidth=1.0
    )
    ax.add_patch(t2_hbar)
    ax.text(5.5, 65.2, "TẦNG 2: MÀNG LỌC VĨ MÔ & TIN TỨC", fontsize=8.5, fontweight='bold', color=accent_blue, fontfamily=font_family, va='center')
    t2_items = [
        "Đồng bộ lịch kinh tế ForexFactory JSON",
        "News Blackout Window (Đóng băng ±30m)",
        "Phân tích sắc thái LLM Qwen 2.5 JSON Schema",
        "Ma trận rủi ro liên thị trường (US10Y, DXY, VIX)"
    ]
    for idx, it in enumerate(t2_items):
        ax.plot(5.5, 62.5 - idx * 1.5, marker='s', markersize=3, color=accent_blue)
        ax.text(7.0, 62.5 - idx * 1.5, it, fontsize=7.6, color=text_secondary, fontfamily=font_family, va='center')

    # T2 Rejection
    t2_rej = patches.FancyBboxPatch(
        (38.5, 58.0), 10.5, 6.0,
        boxstyle="round,pad=0.2,rounding_size=0.3",
        edgecolor=reject_border, facecolor=reject_bg, linewidth=1.2
    )
    ax.add_patch(t2_rej)
    ax.text(43.75, 61.8, "ĐÓNG BĂNG", fontsize=7.5, fontweight='bold', color=accent_red, fontfamily=font_family, ha='center')
    ax.text(43.75, 59.8, "Tạm hoãn lệnh\nTránh bão giá", fontsize=7.0, color=text_secondary, fontfamily=font_family, ha='center')
    ax.annotate("", xy=(38.5, 61.0), xytext=(37.0, 61.0),
                arrowprops=dict(arrowstyle="-|>", color=accent_red, lw=1.2, mutation_scale=10))

    # Arrow T2 -> T3
    ax.annotate("", xy=(20.5, 52.5), xytext=(20.5, 57.5),
                arrowprops=dict(arrowstyle="-|>", color=accent_green, lw=1.8, mutation_scale=12))
    ax.text(21.5, 55.0, "Vĩ mô an toàn", fontsize=7.5, fontweight='bold', color=accent_green, fontfamily=font_family, va='center')

    # TẦNG 3 (Cột trái)
    t3_box = patches.FancyBboxPatch(
        (4, 43.5), 33, 9.0,
        boxstyle="round,pad=0.2,rounding_size=0.4",
        edgecolor=box_border, facecolor=box_bg, linewidth=1.4
    )
    ax.add_patch(t3_box)
    t3_hbar = patches.FancyBboxPatch(
        (4, 50.0), 33, 2.5,
        boxstyle="round,pad=0.2,rounding_size=0.4",
        edgecolor=box_border, facecolor=header_bg, linewidth=1.0
    )
    ax.add_patch(t3_hbar)
    ax.text(5.5, 51.2, "TẦNG 3: CHIẾN LƯỢC TẤT ĐỊNH SƠ CẤP", fontsize=8.5, fontweight='bold', color=accent_blue, fontfamily=font_family, va='center')
    t3_items = [
        "Nhận dạng hình học vùng Imbalance (FVG)",
        "Tương quan Nỗ lực & Kết quả Wyckoff (VSA)",
        "Xác định tỷ số Reff và bộ lọc bóng nến",
        "Phát sinh tín hiệu sơ cấp: y in {-1, +1} & Stop Loss"
    ]
    for idx, it in enumerate(t3_items):
        ax.plot(5.5, 48.5 - idx * 1.5, marker='s', markersize=3, color=accent_blue)
        ax.text(7.0, 48.5 - idx * 1.5, it, fontsize=7.6, color=text_secondary, fontfamily=font_family, va='center')

    # T3 Rejection
    t3_rej = patches.FancyBboxPatch(
        (38.5, 44.0), 10.5, 6.0,
        boxstyle="round,pad=0.2,rounding_size=0.3",
        edgecolor=reject_border, facecolor=reject_bg, linewidth=1.2
    )
    ax.add_patch(t3_rej)
    ax.text(43.75, 47.8, "CHỜ NẾN MỚI", fontsize=7.5, fontweight='bold', color=accent_red, fontfamily=font_family, ha='center')
    ax.text(43.75, 45.8, "Không có cấu trúc\nTiếp tục quét", fontsize=7.0, color=text_secondary, fontfamily=font_family, ha='center')
    ax.annotate("", xy=(38.5, 47.0), xytext=(37.0, 47.0),
                arrowprops=dict(arrowstyle="-|>", color=accent_red, lw=1.2, mutation_scale=10))

    # Arrow T3 -> T4
    ax.annotate("", xy=(20.5, 38.5), xytext=(20.5, 43.5),
                arrowprops=dict(arrowstyle="-|>", color=accent_green, lw=1.8, mutation_scale=12))
    ax.text(21.5, 41.0, "Tín hiệu sơ cấp y in {-1, +1}", fontsize=7.5, fontweight='bold', color=accent_green, fontfamily=font_family, va='center')

    # TẦNG 4 (Cột trái)
    t4_box = patches.FancyBboxPatch(
        (4, 29.5), 33, 9.0,
        boxstyle="round,pad=0.2,rounding_size=0.4",
        edgecolor=box_border, facecolor=box_bg, linewidth=1.4
    )
    ax.add_patch(t4_box)
    t4_hbar = patches.FancyBboxPatch(
        (4, 36.0), 33, 2.5,
        boxstyle="round,pad=0.2,rounding_size=0.4",
        edgecolor=box_border, facecolor=header_bg, linewidth=1.0
    )
    ax.add_patch(t4_hbar)
    ax.text(5.5, 37.2, "TẦNG 4: CỔNG QUYẾT ĐỊNH AI (LIGHTGBM)", fontsize=8.5, fontweight='bold', color=accent_blue, fontfamily=font_family, va='center')
    t4_items = [
        "Nạp động mô hình {strategy}_meta.lgb qua UTF-8",
        "Trích xuất véc-tơ 11 đặc trưng vi cấu trúc (Xt)",
        "Ước lượng xác suất thành công P(z=1 | Xt)",
        "Bộ lọc ngưỡng tối ưu P >= 0.38 (Nén 81.9% bẫy giả)"
    ]
    for idx, it in enumerate(t4_items):
        ax.plot(5.5, 34.5 - idx * 1.5, marker='s', markersize=3, color=accent_blue)
        ax.text(7.0, 34.5 - idx * 1.5, it, fontsize=7.6, color=text_secondary, fontfamily=font_family, va='center')

    # T4 Rejection
    t4_rej = patches.FancyBboxPatch(
        (38.5, 30.0), 10.5, 6.0,
        boxstyle="round,pad=0.2,rounding_size=0.3",
        edgecolor=reject_border, facecolor=reject_bg, linewidth=1.2
    )
    ax.add_patch(t4_rej)
    ax.text(43.75, 33.8, "LỌC BỎ TÍN HIỆU", fontsize=7.5, fontweight='bold', color=accent_red, fontfamily=font_family, ha='center')
    ax.text(43.75, 31.8, "Xác suất P < 0.38\nChặn bẫy phá vỡ", fontsize=7.0, color=text_secondary, fontfamily=font_family, ha='center')
    ax.annotate("", xy=(38.5, 33.0), xytext=(37.0, 33.0),
                arrowprops=dict(arrowstyle="-|>", color=accent_red, lw=1.2, mutation_scale=10))

    # Arrow T4 -> Tầng 5 Convergence
    ax.annotate("", xy=(26.5, 23.5), xytext=(20.5, 29.5),
                arrowprops=dict(arrowstyle="-|>", color=accent_green, lw=2.2, mutation_scale=14))
    ax.text(12.0, 25.5, "Phê duyệt lệnh: P >= 0.38", fontsize=8.0, fontweight='bold', color=accent_green, fontfamily=font_family)

    # =========================================================================
    # CỘT PHẢI: LUỒNG 2 - HỖ TRỢ GIAO DỊCH THỦ CÔNG THÔNG MINH (MANUAL STREAM)
    # Width: 45%, X: 51 to 96
    # =========================================================================

    # Ingress Banner Right
    in_right = patches.FancyBboxPatch(
        (51, 85.5), 45, 5.5,
        boxstyle="round,pad=0.2,rounding_size=0.4",
        edgecolor=accent_purple, facecolor=manual_bg, linewidth=1.8
    )
    ax.add_patch(in_right)
    ax.text(73.5, 89.0, "LUỒNG 2: HỖ TRỢ GIAO DỊCH THỦ CÔNG THÔNG MINH",
            ha='center', va='center', fontsize=10.5, fontweight='bold',
            color=accent_purple, fontfamily=font_family)
    ax.text(73.5, 87.0, "Nhà giao dịch tương tác qua PySide6 GUI: Xem Chart, Macro Calendar & Bấm Buy/Sell",
            ha='center', va='center', fontsize=8.0,
            color=text_secondary, fontfamily=font_family)

    # Step 1: User Action on Chart
    u_box = patches.FancyBboxPatch(
        (51, 71.5), 45, 10.5,
        boxstyle="round,pad=0.2,rounding_size=0.4",
        edgecolor=manual_border, facecolor=manual_bg, linewidth=1.4
    )
    ax.add_patch(u_box)
    u_hbar = patches.FancyBboxPatch(
        (51, 79.5), 45, 2.5,
        boxstyle="round,pad=0.2,rounding_size=0.4",
        edgecolor=manual_border, facecolor=header_bg, linewidth=1.0
    )
    ax.add_patch(u_hbar)
    ax.text(53.0, 80.7, "BƯỚC 1: PHÁT LỆNH THỦ CÔNG TỪ BIỂU ĐỒ (CHART TRADING WIDGET)",
            fontsize=8.5, fontweight='bold', color=accent_purple, fontfamily=font_family, va='center')
    u_items = [
        "Người dùng quan sát mô hình nến và khuyến nghị xu hướng từ Tab Macro Calendar",
        "Kéo thả trực tiếp vạch mức giá Vào lệnh (Entry) và Dừng lỗ (Stop Loss) trên biểu đồ",
        "Bấm nút [BUY] hoặc [SELL] trên bảng Chart Trading Widget của trạm giao dịch",
        "Lệnh KHÔNG gửi thẳng lên sàn: Hệ thống cưỡng bức chuyển hướng vào chốt kiểm duyệt an toàn"
    ]
    for idx, it in enumerate(u_items):
        ax.plot(53.0, 77.8 - idx * 1.7, marker='o', markersize=3.2, color=accent_purple)
        ax.text(54.5, 77.8 - idx * 1.7, it, fontsize=7.6, color=text_secondary, fontfamily=font_family, va='center')

    # Arrow Down to Step 2
    ax.annotate("", xy=(73.5, 65.5), xytext=(73.5, 71.5),
                arrowprops=dict(arrowstyle="-|>", color=accent_purple, lw=1.8, mutation_scale=12))

    # Step 2: Pre-trade Safety Interception (Tầng 1 Guard for Manual)
    s_box = patches.FancyBboxPatch(
        (51, 51.5), 33, 13.5,
        boxstyle="round,pad=0.2,rounding_size=0.4",
        edgecolor=manual_border, facecolor=manual_bg, linewidth=1.4
    )
    ax.add_patch(s_box)
    s_hbar = patches.FancyBboxPatch(
        (51, 62.5), 33, 2.5,
        boxstyle="round,pad=0.2,rounding_size=0.4",
        edgecolor=manual_border, facecolor=header_bg, linewidth=1.0
    )
    ax.add_patch(s_hbar)
    ax.text(52.5, 63.7, "BƯỚC 2: CHỐT KIỂM DUYỆT NGOẠI VI (TẦNG 1 SAFETY)",
            fontsize=8.5, fontweight='bold', color=accent_purple, fontfamily=font_family, va='center')
    s_items = [
        "Kiểm tra kỷ luật: Ngăn chặn hoàn toàn tâm lý 'giao dịch trả thù' (Revenge Trading)",
        "Tự động KHÓA nút phát lệnh nếu tài khoản chạm trần Daily Drawdown Limit (>= 5%)",
        "Tự động KHÓA tính năng đặt lệnh nếu Spread thị trường giãn nở quá mức (> 35 points)",
        "Kiểm tra trạng thái kết nối mạng MT5 (Ngăn chặn lệnh mồ côi khi đứt đường truyền)",
        "Nếu vi phạm: Lập tức từ chối lệnh, rung chuông cảnh báo và hiển thị lý do vi phạm trên UI"
    ]
    for idx, it in enumerate(s_items):
        ax.plot(52.5, 60.5 - idx * 1.7, marker='o', markersize=3.2, color=accent_purple)
        ax.text(54.0, 60.5 - idx * 1.7, it, fontsize=7.4, color=text_secondary, fontfamily=font_family, va='center')

    # Manual Rejection Box
    m_rej = patches.FancyBboxPatch(
        (85.5, 53.5), 10.5, 8.5,
        boxstyle="round,pad=0.2,rounding_size=0.3",
        edgecolor=reject_border, facecolor=reject_bg, linewidth=1.2
    )
    ax.add_patch(m_rej)
    ax.text(90.75, 59.5, "KHÓA LỆNH", fontsize=8.0, fontweight='bold', color=accent_red, fontfamily=font_family, ha='center')
    ax.text(90.75, 56.5, "Từ chối phát lệnh\nBảo vệ kỷ luật vốn\nChống giao dịch trả thù", fontsize=6.8, color=text_secondary, fontfamily=font_family, ha='center')
    ax.annotate("", xy=(85.5, 58.0), xytext=(84.0, 58.0),
                arrowprops=dict(arrowstyle="-|>", color=accent_red, lw=1.2, mutation_scale=10))

    # Arrow Down to Step 3
    ax.annotate("", xy=(73.5, 45.5), xytext=(73.5, 51.5),
                arrowprops=dict(arrowstyle="-|>", color=accent_green, lw=1.8, mutation_scale=12))
    ax.text(74.5, 48.5, "Thỏa mãn kiểm duyệt an toàn", fontsize=7.5, fontweight='bold', color=accent_green, fontfamily=font_family, va='center')

    # Step 3: Auto Risk Sizing for Manual
    size_box = patches.FancyBboxPatch(
        (51, 29.5), 45, 15.5,
        boxstyle="round,pad=0.2,rounding_size=0.4",
        edgecolor=manual_border, facecolor=manual_bg, linewidth=1.4
    )
    ax.add_patch(size_box)
    size_hbar = patches.FancyBboxPatch(
        (51, 42.5), 45, 2.5,
        boxstyle="round,pad=0.2,rounding_size=0.4",
        edgecolor=manual_border, facecolor=header_bg, linewidth=1.0
    )
    ax.add_patch(size_hbar)
    ax.text(53.0, 43.7, "BƯỚC 3: PHÂN HỆ ĐỊNH CỠ RỦI RO TỰ ĐỘNG (AUTO-RISK SIZING)",
            fontsize=8.5, fontweight='bold', color=accent_purple, fontfamily=font_family, va='center')
    size_items = [
        "Người dùng KHÔNG cần tính nhẩm số Lot: Thuật toán tự động đọc vạch Stop Loss trên Chart",
        "Đo lường chính xác khoảng cách giá dừng lỗ: ΔP = |Entry - StopLoss|",
        "Tính toán số Lot chuẩn xác theo đúng ngân sách rủi ro 1.0% vốn: Lot = (Equity * 1%) / (ΔP * PointValue)",
        "Loại trừ 100% rủi ro do con người gõ nhầm số thập phân (Fat-finger Error / Nhầm 0.1 thành 1.0 lot)",
        "Tự động chuẩn hóa khối lượng theo giới hạn sàn: Min Lot, Max Lot và Bước nhảy (Lot Step)",
        "Kiểm tra tiền ký quỹ khả dụng (margin_free): Loại trừ mã lỗi thiếu tiền (RET_NO_MONEY) từ broker"
    ]
    for idx, it in enumerate(size_items):
        ax.plot(53.0, 40.5 - idx * 1.8, marker='o', markersize=3.2, color=accent_purple)
        ax.text(54.5, 40.5 - idx * 1.8, it, fontsize=7.5, color=text_secondary, fontfamily=font_family, va='center')

    # Arrow from Step 3 down to Convergence
    ax.annotate("", xy=(73.5, 23.5), xytext=(73.5, 29.5),
                arrowprops=dict(arrowstyle="-|>", color=accent_green, lw=2.2, mutation_scale=14))
    ax.text(74.5, 26.5, "Chuẩn hóa Lot rủi ro 1.0% an toàn", fontsize=8.0, fontweight='bold', color=accent_green, fontfamily=font_family, va='center')

    # =========================================================================
    # BOTTOM: ĐỘNG CƠ QUẢN TRỊ RỦI RO & THỰC THI TẬP TRUNG (TẦNG 5 CONVERGENCE)
    # Width: 92%, X: 4 to 96, Y: 4 to 22
    # =========================================================================
    t5_box = patches.FancyBboxPatch(
        (4, 3.5), 92, 19.0,
        boxstyle="round,pad=0.2,rounding_size=0.5",
        edgecolor=accent_green, facecolor=box_bg, linewidth=2.0
    )
    ax.add_patch(t5_box)

    t5_hbar = patches.FancyBboxPatch(
        (4, 19.5), 92, 3.0,
        boxstyle="round,pad=0.2,rounding_size=0.5",
        edgecolor=accent_green, facecolor=header_bg, linewidth=1.2
    )
    ax.add_patch(t5_hbar)

    ax.text(50, 21.0, "TẦNG 5: ĐỘNG CƠ QUẢN TRỊ RỦI RO & THỰC THI TẬP TRUNG (SHARED RISK & EXECUTION ENGINE)",
            ha='center', va='center', fontsize=11.0, fontweight='bold',
            color=accent_green, fontfamily=font_family)

    # Internal sub-blocks in Tier 5
    # Left Sub-block: IPC Order Transmission
    ipc_box = patches.FancyBboxPatch(
        (6, 5.0), 42, 13.5,
        boxstyle="round,pad=0.2,rounding_size=0.3",
        edgecolor=box_border, facecolor=bg_color, linewidth=1.2
    )
    ax.add_patch(ipc_box)
    ax.text(27, 16.5, "1. GIAO TIẾP THỰC THI SÀN (MT5 IPC GATEWAY)",
            ha='center', va='center', fontsize=8.8, fontweight='bold',
            color=accent_blue, fontfamily=font_family)
    ipc_items = [
        "Tiếp nhận lệnh từ cả 2 nguồn: Auto (Tầng 4) & Manual (Bước 3)",
        "Đóng gói cấu trúc lệnh chuẩn MqlTradeRequest nguyên tử",
        "Gửi lệnh trực tiếp qua MT5 Python IPC (order_send) trong 0.10 ms",
        "Đối soát phản hồi từ Broker: Fill Rate 100%, Slippage trung bình 3.60 pts",
        "Bảo đảm khớp lệnh đúng giá kế hoạch, không requote hay từ chối"
    ]
    for idx, it in enumerate(ipc_items):
        ax.plot(7.5, 14.5 - idx * 2.0, marker='s', markersize=3, color=accent_blue)
        ax.text(9.0, 14.5 - idx * 2.0, it, fontsize=7.5, color=text_secondary, fontfamily=font_family, va='center')

    # Right Sub-block: Persistence & Monitoring
    db_box = patches.FancyBboxPatch(
        (52, 5.0), 42, 13.5,
        boxstyle="round,pad=0.2,rounding_size=0.3",
        edgecolor=box_border, facecolor=bg_color, linewidth=1.2
    )
    ax.add_patch(db_box)
    ax.text(73, 16.5, "2. BỀN VỮNG TRẠNG THÁI & GIÁM SÁT RỦI RO (SQLITE WAL)",
            ha='center', va='center', fontsize=8.8, fontweight='bold',
            color=accent_green, fontfamily=font_family)
    db_items = [
        "Lưu tức thời Deal Ticket, Entry, SL/TP vào cơ sở dữ liệu SQLite WAL",
        "Kích hoạt cơ chế Phục hồi trạng thái (State Recovery) sau sự cố sập nguồn",
        "Giám sát vị thế thời gian thực độc lập cho cả lệnh Auto và lệnh Manual",
        "Tự động kích hoạt Trailing Stop / Break-Even dời dừng lỗ bảo toàn vốn",
        "Gửi thông báo xác nhận mở/đóng vị thế bất đồng bộ qua Webhook Telegram"
    ]
    for idx, it in enumerate(db_items):
        ax.plot(53.5, 14.5 - idx * 2.0, marker='s', markersize=3, color=accent_green)
        ax.text(55.0, 14.5 - idx * 2.0, it, fontsize=7.5, color=text_secondary, fontfamily=font_family, va='center')

    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=300, facecolor=bg_color, bbox_inches='tight')
        print(f"Saved: {output_path}")
    plt.close()


if __name__ == "__main__":
    p_white = OUTPUT_DIR / "hinh_3_1_kien_truc_dieu_phoi_kep.png"
    p_dark = OUTPUT_DIR / "hinh_3_1_kien_truc_dieu_phoi_kep_dark.png"

    draw_dual_stream(dark_mode=False, output_path=p_white)
    draw_dual_stream(dark_mode=True, output_path=p_dark)
