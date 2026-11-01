import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

with open(r"c:\Users\vong2\OneDrive\Tài liệu\Quant_System\Kho_Do_An\Quant_AI_V2.2\research\strict_walk_forward_oos_results.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print("=========================================================================================")
print("   BẢNG 1: KHẢO SÁT ĐỘ NHẠY TRÊN TẬP XÁC THỰC (VALIDATION SET 2023 - 2024)")
print("=========================================================================================")
print(f"{'Ngưỡng P':<10} | {'Số lệnh':<8} | {'Thắng':<6} | {'Thua':<6} | {'Winrate':<8} | {'PnL (USD)':<14} | {'Ghi chú'}")
print("-" * 85)

for thresh in ["0.0", "0.32", "0.34", "0.36", "0.38", "0.4", "0.42"]:
    res = data["results"][thresh]
    y23 = res["yearly"]["2023"]
    y24 = res["yearly"]["2024"]
    
    t_val = y23["trades"] + y24["trades"]
    w_val = y23["wins"] + y24["wins"]
    l_val = t_val - w_val
    wr_val = (w_val / t_val * 100.0) if t_val > 0 else 0.0
    pnl_val = y23["pnl"] + y24["pnl"]
    
    note = ""
    if thresh == "0.0":
        note = "Baseline chiến lược cơ sở (thua lỗ nặng)"
    elif thresh == "0.38":
        note = "Đạt lợi nhuận dương cao nhất trong pha giằng co"
        
    print(f"{thresh:<10} | {t_val:<8} | {w_val:<6} | {l_val:<6} | {wr_val:6.2f}% | ${pnl_val:12,.2f} | {note}")

print("\n=========================================================================================")
print("   BẢNG 2: ĐỐI CHỨNG A/B TRÊN TẬP KIỂM THỬ ĐỘC LẬP (PURE HOLDOUT TEST SET 2025 - 2026)")
print("=========================================================================================")
print(f"{'Phương án':<30} | {'Số lệnh':<8} | {'Thắng':<6} | {'Thua':<6} | {'Winrate':<8} | {'Lợi nhuận ròng':<16} | {'Nhận xét đánh đổi'}")
print("-" * 100)

for thresh in ["0.0", "0.38"]:
    res = data["results"][thresh]
    y25 = res["yearly"]["2025"]
    y26 = res["yearly"]["2026"]
    
    t_test = y25["trades"] + y26["trades"]
    w_test = y25["wins"] + y26["wins"]
    l_test = t_test - w_test
    wr_test = (w_test / t_test * 100.0) if t_test > 0 else 0.0
    pnl_test = y25["pnl"] + y26["pnl"]
    
    name = "Chiến lược cơ sở (P = 0.00)" if thresh == "0.0" else "Sau lọc Meta-Labeling (P >= 0.38)"
    tradeoff = "Bắt trọn mọi đợt sóng nhưng chịu rủi ro cao" if thresh == "0.0" else "Sàng lọc 79.3% lệnh, giảm lợi nhuận để bảo toàn vốn"
    print(f"{name:<30} | {t_test:<8} | {w_test:<6} | {l_test:<6} | {wr_test:6.2f}% | ${pnl_test:14,.2f} | {tradeoff}")
