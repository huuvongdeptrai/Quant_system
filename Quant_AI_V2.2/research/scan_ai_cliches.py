# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

thesis_dir = Path("Kho_Do_An/Quant_AI_V2.2/docs/thesis")
words = ["bức tranh", "đi sâu", "dệt", "mảnh ghép", "vị thế", "khá tốt", "rất tốt", "có vẻ"]

for f in sorted(thesis_dir.glob("*.md")):
    lines = f.read_text(encoding="utf-8").splitlines()
    for idx, l in enumerate(lines, 1):
        for w in words:
            if w in l.lower():
                # Filter legitimate finance uses of "vị thế" (position: vị thế mua, đóng vị thế)
                if w == "vị thế" and any(k in l.lower() for k in ["mở vị thế", "đóng vị thế", "vị thế mua", "vị thế bán", "quản lý vị thế", "sáu vị thế", "các vị thế", "quy mô vị thế", "giữ vị thế", "vị thế đang mở"]):
                    continue
                print(f"[{f.name}] L{idx}: found '{w}' -> {l.strip()[:100]}")
