# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

p = Path("Kho_Do_An/Quant_AI_V2.2/docs/thesis/chuong_4_thuc_nghiem.md")
txt = p.read_text(encoding="utf-8")

old = "(vượt trội hoàn toàn so với các ngưỡng còn lại vốn có chỉ số âm hoặc tiệm cận 0)"
new = "(vượt trội so với các ngưỡng còn lại vốn có chỉ số âm hoặc tiệm cận 0)"
if old in txt:
    txt = txt.replace(old, new)
    print("Replaced J(P) claim.")
p.write_text(txt, encoding="utf-8")
