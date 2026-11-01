# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

fpath = r'Kho_Do_An\Quant_AI_V2.2\docs\thesis\chuong_3_thiet_ke_he_thong.md'
with open(fpath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines in Chapter 3: {len(lines)}")
bad_lines = []
for i, line in enumerate(lines, 1):
    # check if literal '\n' exists (not inside a single quote or code block where it might be regex or code)
    if r'\n' in line:
        bad_lines.append(i)

print(f"Lines containing literal \\n: {bad_lines}")
