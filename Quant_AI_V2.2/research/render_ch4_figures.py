import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')
import matplotlib.pyplot as plt
import numpy as np

# Set font family
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Segoe UI']
plt.rcParams['axes.edgecolor'] = '#94a3b8'
plt.rcParams['axes.linewidth'] = 0.8

# =========================================================================
# 1. HÌNH 4.3: HIỆU QUẢ NÉN SỤT GIẢM VÀ TỶ LỆ THẮNG NGOÀI MẪU (THEO BẢNG 4.7)
# =========================================================================
thresholds = ["0.00 (Gốc)", "0.30", "0.32", "0.34", "0.36", "0.38 (Chọn)", "0.40", "0.42"]
drawdowns = [39.45, 24.36, 17.65, 13.91, 11.63, 7.46, 8.87, 8.87]
winrates = [32.97, 35.51, 36.43, 37.24, 33.33, 35.82, 38.20, 41.07]
trades_cnt = [740, 352, 280, 239, 177, 134, 89, 56]

fig, ax1 = plt.subplots(figsize=(9.2, 5.0), dpi=300)

# Trục 1: Max Drawdown (%)
color_dd = "#dc2626"
ax1.set_xlabel("Ngưỡng xác suất phê duyệt của Mô hình AI Meta-Labeling (P*)", fontsize=10.5, fontweight="bold", labelpad=8)
ax1.set_ylabel("Mức sụt giảm tối đa (% Max Drawdown)", color=color_dd, fontsize=10.5, fontweight="bold")
line1 = ax1.plot(thresholds, drawdowns, color=color_dd, marker="s", linewidth=2.5, markersize=8, label="Mức sụt giảm tối đa (% Max DD)")
ax1.tick_params(axis="y", labelcolor=color_dd)
ax1.set_ylim(0, 46)
ax1.grid(True, linestyle="--", alpha=0.35, color="#cbd5e1")

# Đường trần rủi ro mục tiêu 10%
ax1.axhline(y=10.0, color="#f59e0b", linestyle=":", linewidth=1.8, label="Trần an toàn vốn mục tiêu (10.0%)")
ax1.annotate("Trần an toàn 10%", xy=(0.5, 10.5), fontsize=8.5, color="#d97706", fontweight="bold")

# Điểm tối ưu 0.38
ax1.annotate("Điểm cân bằng vận hành\nMax DD = 7.46% (Nén 81.1%)", 
             xy=(5, 7.46), xytext=(4.2, 16.0),
             arrowprops=dict(facecolor="#1e293b", shrink=0.08, width=1.2, headwidth=6),
             fontsize=8.5, fontweight="bold", color="#1e293b",
             bbox=dict(boxstyle="round,pad=0.4", fc="#fef08a", ec="#ca8a04", lw=1))

for i, txt in enumerate(drawdowns):
    if i != 5: # skip annotate at 5 to avoid clash
        ax1.annotate(f"{txt:.2f}%", (thresholds[i], drawdowns[i] + 1.2), ha="center", fontsize=8, fontweight="bold", color=color_dd)

# Trục 2: Winrate (%)
ax2 = ax1.twinx()
color_wr = "#16a34a"
ax2.set_ylabel("Tỷ lệ thắng thực tế ngoài mẫu (% Winrate)", color=color_wr, fontsize=10.5, fontweight="bold")
line2 = ax2.plot(thresholds, winrates, color=color_wr, marker="o", linewidth=2.5, markersize=8, linestyle="--", label="Tỷ lệ thắng (% Winrate)")
ax2.tick_params(axis="y", labelcolor=color_wr)
ax2.set_ylim(28, 45)

for i, txt in enumerate(winrates):
    ax2.annotate(f"{txt:.1f}%", (thresholds[i], winrates[i] + 0.6), ha="center", fontsize=8, fontweight="bold", color=color_wr)

plt.title("Hiệu quả Nén Sụt giảm (Drawdown Compression) và Tỷ lệ thắng theo Ngưỡng Phê duyệt P\n(Toàn chu kỳ Walk-Forward 2023 - 2026, 740 tín hiệu sơ cấp)", 
          fontsize=11, fontweight="bold", pad=12)

lines = line1 + [plt.Line2D([0], [0], color="#f59e0b", linestyle=":", lw=1.8)] + line2
labels = ["Mức sụt giảm tối đa (% Max DD)", "Trần rủi ro mục tiêu (10%)", "Tỷ lệ thắng (% Winrate)"]
ax1.legend(lines, labels, loc="upper right", fontsize=8.5, framealpha=0.95, facecolor="#ffffff", edgecolor="#cbd5e1")

plt.tight_layout()
p_4_3_docs = "Kho_Do_An/Quant_AI_V2.2/docs/thesis/images/hinh_4_3_meta_labeling_breakthrough.png"
p_4_3_res = "Kho_Do_An/Quant_AI_V2.2/research/hinh_4_3_meta_labeling_breakthrough.png"
p_4_3_art = r"C:\Users\vong2\.gemini\antigravity\brain\812099d0-d223-4c93-b8df-d681e60c7043\hinh_4_3_meta_labeling_breakthrough.png"

fig.savefig(p_4_3_docs)
fig.savefig(p_4_3_res)
fig.savefig(p_4_3_art)
plt.close(fig)
print("Regenerated Hinh 4.3 successfully!")

# =========================================================================
# 2. HÌNH 4.4: XẾP HẠNG 11 ĐẶC TRƯNG VI CẤU TRÚC THEO CHỈ SỐ SPLIT GAIN
# =========================================================================
with open('Kho_Do_An/Quant_AI_V2.2/research/meta_labeling_results.json', 'r', encoding='utf-8') as f:
    data_meta = json.load(f)

feat_data = data_meta.get("feature_importances", [])
valid_feats = [(f, g) for f, g in feat_data if g > 0]
valid_feats.sort(key=lambda x: x[1], reverse=True)

f_names = [x[0] for x in valid_feats]
f_gains = [x[1] for x in valid_feats]
tot_gain = sum(f_gains)

f_labels = {
    "ema_spread": "Phân kỳ Xu hướng (EMA Spread)",
    "cvd_proxy": "Dòng tiền Tích lũy (CVD Proxy)",
    "gk_vol": "Biến động Garman-Klass (GK Vol)",
    "headroom": "Khoảng trống Cản cứng (Headroom)",
    "adx": "Cường độ Động lượng (ADX 14)",
    "vol_ratio": "Đột biến Khối lượng (Vol Ratio)",
    "vwap_zscore": "Độ lệch Giá trị Hợp lý (VWAP Z-Score)",
    "wick_ratio": "Tỷ lệ Bóng nến Đảo chiều (Wick Ratio)",
    "hour": "Mùa vụ Khung giờ UTC (Hour)",
    "dow": "Mùa vụ Ngày trong tuần (Day of Week)"
}
display_names = [f_labels.get(fn, fn) for fn in f_names]

fig, ax = plt.subplots(figsize=(9.2, 5.2), dpi=300)
y_pos = np.arange(len(display_names))
colors = plt.cm.Blues(np.linspace(0.85, 0.40, len(display_names)))

bars = ax.barh(y_pos, f_gains, color=colors, edgecolor="#1e293b", linewidth=0.8)
ax.set_yticks(y_pos)
ax.set_yticklabels(display_names, fontsize=9, fontweight="bold", color="#0f172a")
ax.invert_yaxis()
ax.set_xlabel("Độ đóng góp thông tin phân tách (Total Split Gain)", fontsize=10.5, fontweight="bold", labelpad=8)
ax.set_title("Xếp hạng Mức độ Quan trọng của 10 Đặc trưng Vi cấu trúc trong Mô hình LightGBM\n(Chỉ số Split Gain - Tổng độ lợi phân tách nhánh cây)", 
             fontsize=11, fontweight="bold", pad=12)
ax.grid(axis="x", linestyle="--", alpha=0.35, color="#cbd5e1")
ax.set_xlim(0, 360)

for bar, gain in zip(bars, f_gains):
    w = bar.get_width()
    pct = (gain / tot_gain) * 100
    ax.annotate(f"{w:.1f} ({pct:.1f}%)", xy=(w, bar.get_y() + bar.get_height() / 2),
                xytext=(6, 0), textcoords="offset points", ha="left", va="center", 
                fontsize=8.5, fontweight="bold", color="#1e293b")

plt.tight_layout()
p_4_4_docs = "Kho_Do_An/Quant_AI_V2.2/docs/thesis/images/hinh_4_4_feature_importance.png"
p_4_4_res = "Kho_Do_An/Quant_AI_V2.2/research/hinh_4_4_feature_importance.png"
p_4_4_art = r"C:\Users\vong2\.gemini\antigravity\brain\812099d0-d223-4c93-b8df-d681e60c7043\hinh_4_4_feature_importance.png"

fig.savefig(p_4_4_docs)
fig.savefig(p_4_4_res)
fig.savefig(p_4_4_art)
plt.close(fig)
print("Regenerated Hinh 4.4 successfully!")
