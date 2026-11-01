# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

fpath = r'Kho_Do_An\Quant_AI_V2.2\docs\thesis\chuong_3_thiet_ke_he_thong.md'
with open(fpath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

bad_lines = [47, 65, 166, 242, 247, 257, 274, 365, 372, 402, 452]
for ln in bad_lines:
    line = lines[ln-1]
    print(f"=== Line {ln} (len {len(line)}) ===")
    print(line[:200] + ("..." if len(line) > 200 else ""))
