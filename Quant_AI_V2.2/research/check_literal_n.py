# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

fpath = r'Kho_Do_An\Quant_AI_V2.2\docs\thesis\chuong_3_thiet_ke_he_thong.md'
with open(fpath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines, 1):
    if r'\n' in line:
        # Check if it's LaTeX like \nu or \nabla vs literal \n
        # Count actual literal \n (backslash followed by n)
        # Note: in markdown, \nabla, \nu, \neq, \neg, \norm might exist!
        pass

# Let's distinguish between LaTeX commands starting with \n (like \nabla, \neq, \nu, \not, \newline, \null)
# and actual escaped literal newline '\n' (i.e. '\n' followed by space or text that is meant to be a newline).
import re
latex_cmds = ['nabla', 'neq', 'nu', 'neg', 'norm', 'newline', 'not', 'notin', 'ni', 'natural', 'nearrow', 'nwarrow']

literal_newlines = []
for i, line in enumerate(lines, 1):
    # find all \n[a-zA-Z0-9_]*
    matches = re.finditer(r'\\n([a-zA-Z]*)', line)
    for m in matches:
        suffix = m.group(1)
        if suffix not in latex_cmds:
            literal_newlines.append((i, m.group(0), line[:100]))

print(f"Total non-LaTeX \\n matches: {len(literal_newlines)}")
for ln, token, text in literal_newlines[:20]:
    print(f"Line {ln}: {token} | {text.strip()}")
