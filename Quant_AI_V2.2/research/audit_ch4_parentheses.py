import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("Kho_Do_An/Quant_AI_V2.2/docs/thesis/chuong_4_thuc_nghiem.md", "r", encoding="utf-8") as f:
    text = f.read()

# Find all parentheses
parens = re.findall(r'\(([^)]+)\)', text)
print(f"Total parentheses in Chapter 4: {len(parens)}")

suspicious = []
# English translation pattern: word in Vietnamese followed by (English ...)
# e.g. "ngoài mẫu (Out-of-Sample)"
for p in parens:
    # Ignore purely numeric or formulas or citations
    if re.match(r'^[\d\s.,$+\-*\/=<>%\\_a-zA-Z0-9^~:;!?#]+$', p):
        # check if it looks like an English explanation
        words = p.split()
        if len(words) >= 2 and any(w.lower() in ["out-of-sample", "walk-forward", "in-sample", "drawdown", "equity", "profit", "slippage", "overfitting", "stop", "loss", "take"] for w in words):
            # check if it is part of a label or explanation
            suspicious.append(p)

print(f"Suspicious English explanatory parentheses: {len(suspicious)}")
for s in suspicious:
    print("  ->", s)
