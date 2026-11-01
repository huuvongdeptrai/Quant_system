import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("Kho_Do_An/Quant_AI_V2.2/docs/thesis/chuong_4_thuc_nghiem.md", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if line.strip().startswith("|") and ("---" in line or "Bảng 4." in lines[max(0, i-2)] or "Bảng 4." in lines[max(0, i-3)]):
        parts = [p.strip() for p in line.strip().split("|")[1:-1]]
        print(f"Line {i+1}: num_cols={len(parts)} | {line.strip()[:60]}...")
