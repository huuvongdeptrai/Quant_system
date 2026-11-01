# -*- coding: utf-8 -*-
import sys
import os
import glob
import re

sys.stdout.reconfigure(encoding='utf-8')

thesis_dir = r'Kho_Do_An\Quant_AI_V2.2\docs\thesis'
all_files = sorted(glob.glob(os.path.join(thesis_dir, '*.md')))

print("=== DEEP AUDIT FOR ALL 10 WRITING RULES & GEMINI.md ===")

# 1. Check citations in tai_lieu_tham_khao_phu_luc.md vs chapters
tltk_path = os.path.join(thesis_dir, 'tai_lieu_tham_khao_phu_luc.md')
with open(tltk_path, 'r', encoding='utf-8') as f:
    tltk_content = f.read()

# find defined references [1] to [N]
defined_refs = set(re.findall(r'\[(\d+)\]', tltk_content))
print(f"Total defined references in Bibliography: {len(defined_refs)} -> {sorted([int(x) for x in defined_refs])}")

# Scan each chapter for cited references
cited_refs = set()
for fpath in all_files:
    fname = os.path.basename(fpath)
    if fname == 'tai_lieu_tham_khao_phu_luc.md':
        continue
    with open(fpath, 'r', encoding='utf-8') as f:
        text = f.read()
    refs = re.findall(r'\[(\d+)\]', text)
    cited_refs.update(refs)
    print(f"File {fname}: cites {len(refs)} references -> {sorted(set([int(x) for x in refs]))}")

missing_defs = cited_refs - defined_refs
if missing_defs:
    print(f"WARNING: Cited references missing from bibliography: {missing_defs}")
else:
    print("ALL cited references [X] are properly defined in Bibliography! (100% match)")

# 2. Check for classic author names without citations nearby
classic_authors = [
    ('Ehlers', r'Ehlers(?!.*?\[\d+\])'),
    ('Kyle', r'Kyle(?!.*?\[\d+\])'),
    ('Cont', r'Cont(?!.*?\[\d+\])'),
    ('López de Prado', r'López de Prado(?!.*?\[\d+\])'),
    ('Garman', r'Garman(?!.*?\[\d+\])'),
    ('Pardo', r'Pardo(?!.*?\[\d+\])')
]

print("\n--- Checking Author Mentions vs Citations ---")
for fpath in all_files:
    fname = os.path.basename(fpath)
    if fname in ['tai_lieu_tham_khao_phu_luc.md', 'danh_muc_tu_viet_tat.md', 'muc_luc_chinh_thuc.md']:
        continue
    with open(fpath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for i, line in enumerate(lines, 1):
        for author, _ in classic_authors:
            if author in line and '[' not in line:
                # check if next line or previous line has citation
                prev_line = lines[i-2] if i > 1 else ""
                next_line = lines[i] if i < len(lines) else ""
                if '[' not in prev_line and '[' not in next_line:
                    print(f"{fname}:{i} Author '{author}' mentioned without citation nearby: {line.strip()[:100]}")

# 3. Check Headings for Sensationalism / Metric Numbers (Rule 9)
print("\n--- Checking Headings for Rule 9 Compliance ---")
for fpath in all_files:
    fname = os.path.basename(fpath)
    if fname in ['muc_luc_chinh_thuc.md', 'tai_lieu_tham_khao_phu_luc.md']:
        continue
    with open(fpath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for i, line in enumerate(lines, 1):
        line_clean = line.strip()
        if line_clean.startswith('#'):
            # check if heading contains numbers like % or specific backtest outcomes
            if re.search(r'\b\d+(\.\d+)?%', line_clean):
                print(f"{fname}:{i} [HEADING WITH %]: {line_clean[:100]}")
            for sens in ['bất lực', 'thần thánh', 'siêu việt', 'bóc trần', 'hoàn hảo', 'bất khả chiến bại']:
                if sens in line_clean.lower():
                    print(f"{fname}:{i} [SENSATIONAL HEADING]: {line_clean[:100]}")

# 4. Check for Platform vs Case Study (Rule 2)
print("\n--- Checking Platform vs Case Study (Rule 2) ---")
# Check if Wyckoff or ICT is claimed as the main system instead of benchmark case study
for fpath in all_files:
    fname = os.path.basename(fpath)
    with open(fpath, 'r', encoding='utf-8') as f:
        text = f.read()
    # Check mentions of Wyckoff
    wyckoff_count = len(re.findall(r'Wyckoff', text, re.IGNORECASE))
    vectra_count = len(re.findall(r'VECTRA', text, re.IGNORECASE))
    print(f"{fname}: VECTRA mentions = {vectra_count}, Wyckoff mentions = {wyckoff_count}")

# 5. Check Emojis & Prohibited Characters
print("\n--- Checking Emojis across all thesis files ---")
emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]|[\u2600-\u27ff]|[\u2300-\u23ff]')
for fpath in all_files:
    fname = os.path.basename(fpath)
    with open(fpath, 'r', encoding='utf-8') as f:
        text = f.read()
    emojis = [c for c in emoji_pattern.findall(text) if ord(c) > 0x27bf or c in ['🚀', '📈', '💰', '🔥', '❌', '🟢', '⚙️', '🔹', '🛑']]
    if emojis:
        print(f"{fname}: Found emojis: {set(emojis)}")
    else:
        print(f"{fname}: 0 emojis found")

print("\n--- Deep audit completed ---")
