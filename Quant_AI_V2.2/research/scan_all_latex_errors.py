import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

thesis_dir = r'Kho_Do_An/Quant_AI_V2.2/docs/thesis'
md_files = glob.glob(os.path.join(thesis_dir, '*.md'))

def check_latex_in_file(fpath):
    fname = os.path.basename(fpath)
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    errors = []

    # 1. Check display math $$ ... $$
    # Can be single-line or multi-line
    display_matches = list(re.finditer(r'\$\$(.*?)\$\$', content, re.DOTALL))
    for m in display_matches:
        math_str = m.group(1)
        start_pos = m.start()
        line_no = content[:start_pos].count('\n') + 1

        # Check for unescaped & inside \text{...}
        text_blocks = re.findall(r'\\text\{([^{}]*)\}', math_str)
        for tb in text_blocks:
            if '&' in tb and not re.search(r'\\&', tb):
                errors.append((line_no, f"Unescaped '&' inside \\text{{{tb}}} in display math"))

        # Check for unescaped % inside math (not \%)
        # Find % that is not preceded by \
        unescaped_pct = re.findall(r'(?<!\\)%', math_str)
        if unescaped_pct:
            # check if it's inside a comment? LaTeX math doesn't use % comments in markdown usually
            errors.append((line_no, f"Unescaped '%' in math block: {math_str.strip()[:60]}..."))

        # Check matched braces in math_str
        open_b = math_str.count('{')
        close_b = math_str.count('}')
        if open_b != close_b:
            errors.append((line_no, f"Mismatched braces: {open_b} '{{' vs {close_b} '}}'"))

        # Check \\command
        double_bs = re.findall(r'\\\\([a-zA-Z]+)', math_str)
        if double_bs:
            errors.append((line_no, f"Double backslash command: \\\\{double_bs[0]}"))

    # 2. Check inline math $ ... $
    # Be careful not to match display math or code blocks
    # First remove code blocks
    no_code = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
    no_code_and_display = re.sub(r'\$\$.*?\$\$', '', no_code, flags=re.DOTALL)

    inline_matches = list(re.finditer(r'(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)', no_code_and_display))
    for m in inline_matches:
        math_str = m.group(1)
        start_pos = m.start()
        line_no = content[:start_pos].count('\n') + 1

        # Check for unescaped & inside \text{...}
        text_blocks = re.findall(r'\\text\{([^{}]*)\}', math_str)
        for tb in text_blocks:
            if '&' in tb and not re.search(r'\\&', tb):
                errors.append((line_no, f"Unescaped '&' inside \\text{{{tb}}} in inline math"))

        # Check matched braces
        open_b = math_str.count('{')
        close_b = math_str.count('}')
        if open_b != close_b:
            errors.append((line_no, f"Mismatched braces in inline math: {math_str}"))

        # Check \\command
        double_bs = re.findall(r'\\\\([a-zA-Z]+)', math_str)
        if double_bs:
            errors.append((line_no, f"Double backslash command in inline math: \\\\{double_bs[0]}"))

    return fname, errors

total_errors = 0
for fpath in md_files:
    fname, errors = check_latex_in_file(fpath)
    if errors:
        print(f"\n=== {fname} ({len(errors)} issues) ===")
        for line_no, err in errors:
            print(f"  Line {line_no}: {err}")
            total_errors += 1
    else:
        print(f"=== {fname}: PERFECT (0 issues) ===")

print(f"\nTotal issues found across all thesis files: {total_errors}")
