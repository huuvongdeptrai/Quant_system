# -*- coding: utf-8 -*-
import sys
import os
import glob
import re

sys.stdout.reconfigure(encoding='utf-8')

thesis_dir = r'Kho_Do_An\Quant_AI_V2.2\docs\thesis'
all_files = sorted(glob.glob(os.path.join(thesis_dir, '*.md')))

# Check occurrences of pattern: Vietnamese word followed by (English word)
# e.g. "cắt lỗ (Stop Loss)" or "vùng mất cân bằng (Imbalance)"
paren_pattern = re.compile(r'([A-Za-zÀ-ỹ]+)\s+\(([A-Za-z0-9_\s\-\.\/]+)\)')

for fpath in all_files:
    fname = os.path.basename(fpath)
    if fname in ['danh_muc_tu_viet_tat.md', 'tai_lieu_tham_khao_phu_luc.md', 'muc_luc_chinh_thuc.md']:
        continue
    with open(fpath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    count = 0
    samples = []
    for i, line in enumerate(lines, 1):
        # find matches
        matches = paren_pattern.findall(line)
        for vn, en in matches:
            # exclude abbreviations like (API), (USD), (M15), (CPU), (RAM), (SQLite), (WAL), (JSON), (HTTP), (IPC), (GUI)
            # exclude citations like (2018), or formula references like (3.1)
            if re.match(r'^\d+$', en) or re.match(r'^[A-Z0-9]{2,5}$', en):
                continue
            if en in ['USD', 'points', 'ms', 'lot', 'oz', 'bars', 'TickSize', 'RiskMoney', 'P^*', 'XAUUSD']:
                continue
            count += 1
            if len(samples) < 5:
                samples.append((i, f"{vn} ({en})"))
    print(f"{fname}: {count} occurrences of explanatory parentheses")
    for ln, smp in samples:
        print(f"   L{ln}: {smp}")
