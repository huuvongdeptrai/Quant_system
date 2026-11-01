# -*- coding: utf-8 -*-
import sys
import re
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

thesis_dir = Path("Kho_Do_An/Quant_AI_V2.2/docs/thesis")
files = sorted(list(thesis_dir.glob("*.md")))

# Whitelist of legitimate parenthetical expressions
whitelist = [
    "ieee standard", "crd", "sqlite wal", "wal", "pnl", "utc", "gmt", "xauusd",
    "dxy", "vix", "us10y", "us02y", "dfii10", "tips", "fed", "fomc", "adx", "atr",
    "rsi", "ema", "vwap", "cvd", "poc", "vah", "val", "fvg", "ob", "bos", "choch",
    "eqh", "eql", "ict", "smc", "mt5", "ipc", "dll", "gui", "qss", "fps", "cpu", "ram",
    "rss", "kib", "mib", "gb", "ms", "us", "ns", "api", "rest", "json", "wal", "csv",
    "parquet", "llm", "lgbm", "sl", "tp", "rr", "dd", "pf", "wr", "auc", "roc",
    "wf", "oos", "is", "pr", "k=150", "p=0.00", "p=0.38", "p=0.40", "p=0.42", "p=0.30",
    "p=0.32", "p=0.34", "p=0.36", "p50", "p95", "p99", "j(p)", "m15", "h1", "h4", "d1"
]

def is_whitelisted(s):
    s_clean = s.strip().lower()
    if s_clean in whitelist:
        return True
    # Single letter or math variable: (x), (y), (t), (p), (a), (b), (c), (d), (1), (2), (i)
    if len(s_clean) <= 3:
        return True
    # Mathematical expression with =, +, -, *, /, <, >
    if any(c in s_clean for c in ["=", "+", "-", "*", "/", "<", ">", "\\", "$"]):
        return True
    # Citations or numbers: e.g. (2018), (2001)
    if re.match(r"^\d{4}$", s_clean):
        return True
    # Split designations: e.g. Split 1, Split 2
    if "split" in s_clean:
        return True
    return False

print("Scanning for suspicious English explanatory parentheses across thesis files...\n")

total_suspicious = 0

for f in files:
    if f.name in ["danh_muc_tu_viet_tat.md", "tai_lieu_tham_khao_phu_luc.md"]:
        # Acronym table and Bibliography naturally have English terms
        continue
    text = f.read_text(encoding="utf-8")
    lines = text.splitlines()
    
    suspicious_in_file = []
    for line_idx, line in enumerate(lines, 1):
        # find all parenthetical phrases: (...)
        # ignore markdown links: [...](...)
        line_no_links = re.sub(r"\[.*?\]\(.*?\)", "", line)
        line_no_images = re.sub(r"!\[.*?\]\(.*?\)", "", line_no_links)
        line_no_math = re.sub(r"\$.*?\$", "", line_no_images)
        
        matches = re.findall(r"\(([^)]+)\)", line_no_math)
        for m in matches:
            m_strip = m.strip()
            # check if it looks like English text (contains only ASCII letters and spaces, at least 4 chars)
            if re.match(r"^[A-Za-z\s/&–-]{4,}$", m_strip) and not is_whitelisted(m_strip):
                # Check if it's an explanatory translation of Vietnamese word right before
                suspicious_in_file.append((line_idx, m_strip, line.strip()[:100]))

    if suspicious_in_file:
        print(f"[{f.name}] Found {len(suspicious_in_file)} potentially suspicious parenthetical English terms:")
        for l_num, term, context in suspicious_in_file[:10]:
            print(f"   Line {l_num}: ({term}) in: {context}")
        total_suspicious += len(suspicious_in_file)
    else:
        print(f"[CLEAN] {f.name}: 0 suspicious English explanatory parentheses.")

print(f"\nTotal suspicious parentheses found: {total_suspicious}")
