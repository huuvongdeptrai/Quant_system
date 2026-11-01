import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

files = [
    "Kho_Do_An/Quant_AI_V2.2/docs/thesis/chuong_3_thiet_ke_he_thong.md",
    "Kho_Do_An/Quant_AI_V2.2/docs/thesis/chuong_4_thuc_nghiem.md",
    "Kho_Do_An/Quant_AI_V2.2/docs/thesis/tai_lieu_tham_khao_phu_luc.md"
]

for fp in files:
    if os.path.exists(fp):
        with open(fp, "r", encoding="utf-8") as f:
            lines = f.readlines()
        print(f"=== {os.path.basename(fp)} ===")
        for idx, line in enumerate(lines, 1):
            if "0.38" in line or "0.36" in line:
                print(f"  L{idx}: {line.strip()[:110]}")
