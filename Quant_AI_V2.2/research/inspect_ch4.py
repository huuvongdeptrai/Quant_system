# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'Kho_Do_An\Quant_AI_V2.2\docs\thesis\chuong_4_thuc_nghiem.md', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i in range(215, 225):
    print(f'{i+1}: {lines[i]}', end='')
