import sys, re

sys.stdout.reconfigure(encoding='utf-8')
with open('Kho_Do_An/Quant_AI_V2.2/docs/thesis/chuong_4_thuc_nghiem.md', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, l in enumerate(lines, 1):
    if l.startswith('#') or l.startswith('*Bảng') or l.startswith('![Hình') or l.startswith('*Hình'):
        print(f"L{i}: {l.strip()}")
