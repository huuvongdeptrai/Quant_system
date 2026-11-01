# -*- coding: utf-8 -*-
"""
Verification script for all citations [1] to [25] and audit of parentheses in Chapter 2.
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

thesis_dir = "docs/thesis"
bib_path = os.path.join(thesis_dir, "tai_lieu_tham_khao_phu_luc.md")

with open(bib_path, "r", encoding="utf-8") as f:
    bib_text = f.read()

# Find all [N] defined in bibliography
bib_citations = set(int(m.group(1)) for m in re.finditer(r'^\[(\d+)\]', bib_text, re.MULTILINE))
print(f"Citations defined in bibliography: {sorted(list(bib_citations))}")
print(f"Total defined: {len(bib_citations)}")

# Now find all citations in other thesis markdown files
files = [
    "chuong_1_tong_quan.md",
    "chuong_2_co_so_ly_thuyet.md",
    "chuong_3_thiet_ke_he_thong.md",
    "chuong_4_thuc_nghiem.md",
    "chuong_5_ket_luan.md",
    "danh_muc_tu_viet_tat.md",
    "muc_luc_chinh_thuc.md",
    "tom_tat_va_abstract.md",
]

citation_counts = {i: 0 for i in bib_citations}
undefined_citations = set()

for fname in files:
    fpath = os.path.join(thesis_dir, fname)
    if not os.path.exists(fpath):
        continue
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    matches = re.finditer(r'\[(\d+)\]', content)
    for m in matches:
        num = int(m.group(1))
        if num in citation_counts:
            citation_counts[num] += 1
        else:
            undefined_citations.add((fname, num))

print("\n--- Citation Occurrence Counts Across Thesis ---")
for num in sorted(list(citation_counts.keys())):
    cnt = citation_counts[num]
    status = "OK (>=2)" if cnt >= 2 else "WARNING (<2)" if cnt == 1 else "ZERO (Dangling)"
    print(f"[{num:2d}]: {cnt:2d} times -> {status}")

if undefined_citations:
    print(f"\nUNDEFINED CITATIONS FOUND: {undefined_citations}")
else:
    print("\nZero undefined citations found!")

# Check Chapter 2 for redundant parentheses
ch2_path = os.path.join(thesis_dir, "chuong_2_co_so_ly_thuyet.md")
with open(ch2_path, "r", encoding="utf-8") as f:
    ch2_text = f.read()

# Find all parentheses in ch2
print("\n--- Chapter 2 Parentheses Audit ---")
parens = re.findall(r'\([A-Za-z0-9\s,._\-\/\\\'\"\$\=\<\>\+\:\;\%\&]*\)', ch2_text)
print(f"Total parenthetical items in Chapter 2: {len(parens)}")
# Sample some
suspicious = []
for p in parens:
    # check if it looks like an English explanation e.g. (Fair Value Gap), (Take-Profit), etc.
    if re.search(r'\b(tương đương|nghĩa là|hay là|tức là|hoặc)\b', p, re.IGNORECASE):
        suspicious.append(p)
print(f"Suspicious explanatory parentheses: {len(suspicious)}")
for s in suspicious:
    print("  Suspicious:", s)

print("\nAudit completed.")
