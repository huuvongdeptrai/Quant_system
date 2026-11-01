"""
Generate Publication-Quality Architecture Diagram of the 5-Stage Decoupled Pipeline
for the Graduation Thesis (VECTRA Quant AI V2.2).
Outputs:
1. docs/thesis/images/hinh_3_1_pipeline_5_tang.png (Academic Print Edition)
2. docs/thesis/images/hinh_3_1_pipeline_5_tang_dark.png (Institutional Dark Edition)
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from pathlib import Path

# Paths
OUTPUT_DIR = Path("Kho_Do_An/Quant_AI_V2.2/docs/thesis/images")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def draw_pipeline(dark_mode=False, output_path=None):
    fig, ax = plt.subplots(figsize=(15, 19), dpi=300)
    
    # Color palette
    if dark_mode:
        bg_color = "#070a13"
        box_bg = "#0d1322"
        box_border = "#1e293b"
        header_bg = "#151e32"
        text_primary = "#f1f5f9"
        text_secondary = "#94a3b8"
        accent_blue = "#38bdf8"
        accent_green = "#22c55e"
        accent_red = "#ef4444"
        reject_bg = "#1a1219"
        reject_border = "#7f1d1d"
        success_bg = "#0f2019"
        success_border = "#166534"
        arrow_color = "#64748b"
        card_shadow = None
    else:
        bg_color = "#ffffff"
        box_bg = "#f8fafc"
        box_border = "#cbd5e1"
        header_bg = "#e2e8f0"
        text_primary = "#0f172a"
        text_secondary = "#334155"
        accent_blue = "#0284c7"
        accent_green = "#16a34a"
        accent_red = "#dc2626"
        reject_bg = "#fef2f2"
        reject_border = "#fca5a5"
        success_bg = "#f0fdf4"
        success_border = "#86efac"
        arrow_color = "#475569"
        card_shadow = None

    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    font_family = "Segoe UI"

    # Title Banner at Top
    title_box = patches.FancyBboxPatch(
        (8, 93), 84, 5.5,
        boxstyle="round,pad=0.2,rounding_size=0.5",
        edgecolor=accent_blue, facecolor=box_bg, linewidth=2
    )
    ax.add_patch(title_box)
    ax.text(50, 96.5, "LUỒNG DỮ LIỆU GIÁ THỜI GIAN THỰC (MT5 DATA STREAM)",
            ha='center', va='center', fontsize=13, fontweight='bold',
            color=accent_blue, fontfamily=font_family)
    ax.text(50, 94.2, "Dòng nhịp đập Tick Stream  •  Nến M15 OHLCV  •  Độ giãn Spread vi mô  •  Ký quỹ khả dụng",
            ha='center', va='center', fontsize=9.5,
            color=text_secondary, fontfamily=font_family)

    # Connecting Arrow from Stream to Tier 1
    ax.annotate("", xy=(40, 87.5), xytext=(40, 93),
                arrowprops=dict(arrowstyle="-|>", color=accent_blue, lw=2.2, mutation_scale=15))
    ax.text(41.5, 90.2, "Tiếp nhận nhịp giá mới", fontsize=8.5, color=accent_blue,
            fontweight='bold', fontfamily=font_family, va='center')

    # Data for the 5 Tiers
    tiers = [
        {
            "tier_num": "TẦNG 1",
            "name": "BỘ BẢO VỆ AN TOÀN NGOẠI VI (SAFETY GUARDS & CIRCUIT BREAKERS)",
            "y": 77,
            "items": [
                "Kiểm tra nhịp tim kết nối máy chủ MT5 (Heartbeat Monitor < 15 giây)",
                "Kiểm tra độ giãn Spread vi mô (Spread Threshold < 35 points / 0.35 USD)",
                "Kiểm tra cầu dao sụt giảm vốn trong ngày (Daily Drawdown Limit < 5.0%)",
                "Kiểm tra chuỗi vị thế thua lỗ liên tiếp (Max Consecutive Losses <= 3 vị thế)"
            ],
            "pass_cond": "Đạt chuẩn an toàn vốn & hạ tầng (Safety Passed)",
            "reject_title": "NGẮT CẦU DAO",
            "reject_text": "Dừng phát lệnh tức thì\nBắn cảnh báo Telegram",
            "reject_reason": "Vi phạm an toàn"
        },
        {
            "tier_num": "TẦNG 2",
            "name": "MÀNG LỌC VĨ MÔ & PHÒNG VỆ TIN TỨC (MACRO NEWS DEFENSE)",
            "y": 59,
            "items": [
                "Đồng bộ lịch kinh tế vĩ mô định kỳ (ForexFactory JSON Calendar API)",
                "Cầu dao đóng băng giao dịch trước/sau tin tức đỏ (High-Impact News Blackout ±30m)",
                "Trích xuất sắc thái vĩ mô bằng LLM Qwen 2.5 cục bộ qua định dạng JSON Schema",
                "Xác định chế độ rủi ro liên thị trường: US10Y (Lợi suất Mỹ), DXY (USD), VIX (Nỗi sợ)"
            ],
            "pass_cond": "Bối cảnh vĩ mô an toàn (Macro Cleared)",
            "reject_title": "ĐÓNG BĂNG LỆNH",
            "reject_text": "Tạm hoãn giải ngân vị thế\nTránh bão giá phi cấu trúc",
            "reject_reason": "Bão tin tức đỏ"
        },
        {
            "tier_num": "TẦNG 3",
            "name": "ĐỘNG CƠ CHIẾN LƯỢC TẤT ĐỊNH SƠ CẤP (PRIMARY STRATEGY ENGINE)",
            "y": 41,
            "items": [
                "Nhận dạng hình học vùng mất cân bằng thanh khoản (Fair Value Gap - FVG)",
                "Phân tích tương quan nỗ lực & kết quả Wyckoff (Effort vs. Result Volume Absorption)",
                "Xác định tỷ số Nỗ lực / Kết quả Reff và bộ lọc bóng nến từ chối giá (Wick Rejection)",
                "Phát sinh tín hiệu sơ cấp: Hướng lệnh y in {-1, +1} và Điểm dừng lỗ hình học SL"
            ],
            "pass_cond": "Phát hiện tín hiệu sơ cấp y in {-1, +1}",
            "reject_title": "CHỜ NẾN MỚI",
            "reject_text": "Không xuất hiện FVG/Wyckoff\nTiếp tục chu trình quét nến",
            "reject_reason": "Không có cấu trúc"
        },
        {
            "tier_num": "TẦNG 4",
            "name": "CỔNG QUYẾT ĐỊNH THÔNG MINH & MODEL REGISTRY (AI DECISION GATE)",
            "y": 23,
            "items": [
                "Tự động nạp mô hình LightGBM Meta-Labeling: {strategy_id}_meta.lgb qua chuỗi UTF-8",
                "Trích xuất véc-tơ 11 đặc trưng vi cấu trúc (Garman-Klass, CVD Proxy, Headroom, VWAP Z-score...)",
                "Ước lượng xác suất thành công nhị phân của tín hiệu: P(z=1 | Xt)",
                "Kiểm định ngưỡng xác suất tin cậy tối ưu: P(z=1 | Xt) >= 0.38 (Loại bỏ 81.9% bẫy giá)"
            ],
            "pass_cond": "Xác nhận phê duyệt lệnh: P >= 0.38",
            "reject_title": "LỌC BỎ TÍN HIỆU",
            "reject_text": "Xác suất P < 0.38 (Bẫy giá)\nHủy tín hiệu, bảo toàn vốn",
            "reject_reason": "P < 0.38 (Lọc bẫy)"
        },
        {
            "tier_num": "TẦNG 5",
            "name": "PHÂN HỆ QUẢN TRỊ RỦI RO & THỰC THI (DYNAMIC RISK ENGINE & EXECUTION)",
            "y": 5,
            "items": [
                "Định cỡ quy mô vị thế theo tỷ lệ rủi ro cố định danh mục (Fixed Fractional Sizing 1.0% vốn)",
                "Chuẩn hóa bước nhảy khối lượng sàn (Min Lot, Max Lot, Lot Step) và kiểm tra margin_free",
                "Truyền lệnh thực thi nguyên tử qua giao tiếp liên tiến trình MetaTrader 5 Python IPC",
                "Đồng bộ trạng thái mở vị thế vào SQLite WAL Database và gửi thông báo qua Webhook Telegram"
            ],
            "pass_cond": None,
            "reject_title": "VỊ THẾ ĐÃ KHỚP",
            "reject_text": "Deal Ticket lưu SQLite WAL\nGiám sát rủi ro tự động",
            "reject_reason": "Khớp lệnh thành công"
        }
    ]

    tier_width = 63
    tier_height = 10.5
    tier_x = 8

    reject_width = 20
    reject_height = 7.5
    reject_x = 74

    for i, t in enumerate(tiers):
        y = t["y"]

        # Main Tier Box
        box = patches.FancyBboxPatch(
            (tier_x, y), tier_width, tier_height,
            boxstyle="round,pad=0.2,rounding_size=0.4",
            edgecolor=box_border, facecolor=box_bg, linewidth=1.5
        )
        ax.add_patch(box)

        # Header Box of Tier
        hbar = patches.FancyBboxPatch(
            (tier_x, y + tier_height - 2.6), tier_width, 2.6,
            boxstyle="round,pad=0.2,rounding_size=0.4",
            edgecolor=box_border, facecolor=header_bg, linewidth=1.2
        )
        ax.add_patch(hbar)

        # Header Text
        ax.text(tier_x + 1.5, y + tier_height - 1.3, t["tier_num"] + ":",
                fontsize=10, fontweight='bold', color=accent_blue,
                fontfamily=font_family, va='center')
        ax.text(tier_x + 10.5, y + tier_height - 1.3, t["name"],
                fontsize=9.2, fontweight='bold', color=text_primary,
                fontfamily=font_family, va='center')

        # Bullet Items
        for j, item in enumerate(t["items"]):
            item_y = y + tier_height - 3.8 - (j * 1.65)
            # Bullet dot
            ax.plot(tier_x + 2.0, item_y, marker='s', markersize=3.5, color=accent_blue)
            ax.text(tier_x + 3.8, item_y, item,
                    fontsize=8.5, color=text_secondary,
                    fontfamily=font_family, va='center')

        # Rejection / Exit Box on the Right
        is_tier_5 = (i == len(tiers) - 1)
        r_box_color = success_bg if is_tier_5 else reject_bg
        r_border_color = success_border if is_tier_5 else reject_border
        r_accent_color = accent_green if is_tier_5 else accent_red

        r_y = y + 1.5
        r_box = patches.FancyBboxPatch(
            (reject_x, r_y), reject_width, reject_height,
            boxstyle="round,pad=0.2,rounding_size=0.4",
            edgecolor=r_border_color, facecolor=r_box_color, linewidth=1.4
        )
        ax.add_patch(r_box)

        # Rejection Title
        ax.text(reject_x + reject_width / 2, r_y + reject_height - 1.8, t["reject_title"],
                fontsize=9, fontweight='bold', color=r_accent_color,
                fontfamily=font_family, ha='center', va='center')
        
        # Rejection Body
        ax.text(reject_x + reject_width / 2, r_y + reject_height / 2 - 0.8, t["reject_text"],
                fontsize=8, color=text_secondary,
                fontfamily=font_family, ha='center', va='center')

        # Arrow from Main Box to Reject Box
        ax.annotate("", xy=(reject_x, r_y + reject_height / 2),
                    xytext=(tier_x + tier_width, r_y + reject_height / 2),
                    arrowprops=dict(arrowstyle="-|>", color=r_accent_color, lw=1.6, mutation_scale=12))
        ax.text((tier_x + tier_width + reject_x) / 2, r_y + reject_height / 2 + 1.0,
                t["reject_reason"], fontsize=7.5, color=r_accent_color,
                fontweight='bold', fontfamily=font_family, ha='center', va='bottom')

        # Downward Arrow to Next Tier
        if t["pass_cond"] is not None:
            next_y = tiers[i + 1]["y"] + tier_height
            curr_bottom = y
            mid_arrow_y = (curr_bottom + next_y) / 2

            ax.annotate("", xy=(40, next_y), xytext=(40, curr_bottom),
                        arrowprops=dict(arrowstyle="-|>", color=accent_green, lw=2.0, mutation_scale=14))
            ax.text(41.5, mid_arrow_y, t["pass_cond"],
                    fontsize=8.5, fontweight='bold', color=accent_green,
                    fontfamily=font_family, va='center')

    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=300, facecolor=bg_color, bbox_inches='tight')
        print(f"Saved: {output_path}")
    plt.close()


if __name__ == "__main__":
    white_img = OUTPUT_DIR / "hinh_3_1_pipeline_5_tang.png"
    dark_img = OUTPUT_DIR / "hinh_3_1_pipeline_5_tang_dark.png"

    draw_pipeline(dark_mode=False, output_path=white_img)
    draw_pipeline(dark_mode=True, output_path=dark_img)
