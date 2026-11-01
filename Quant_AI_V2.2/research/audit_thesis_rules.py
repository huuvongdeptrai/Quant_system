# -*- coding: utf-8 -*-
import sys
import re
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

thesis_dir = Path("Kho_Do_An/Quant_AI_V2.2/docs/thesis")
files = sorted(list(thesis_dir.glob("*.md")))

first_person = ["tôi", "em", "nhóm tác giả", "chúng em", "chúng tôi"]
slang = ["cắn sl", "hít tp", "quét râu", "rút chân", "nhồi lệnh", "gồng lỗ", "cháy tài khoản"]
ai_cliches = ["bức tranh đa chiều", "dệt nên", "đi sâu vào", "mảnh ghép hoàn hảo", "chứng minh vị thế", "bất khả chiến bại", "thần thánh", "siêu việt", "bóc trần", "sự bất lực"]
emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)

print(f"Auditing {len(files)} files in {thesis_dir}...\n")

issues_found = 0

for f in files:
    text = f.read_text(encoding="utf-8")
    lines = text.splitlines()
    file_issues = 0
    
    # 1. First person pronouns
    for fp in first_person:
        # Match standalone word
        matches = [(i+1, l.strip()) for i, l in enumerate(lines) if re.search(r"(?<!\w)" + fp + r"(?!\w)", l, re.I)]
        # Filter false positives: e.g. "tối ưu" contains "tôi"? No, regex has word boundary!
        # In Vietnamese, regex \b or (?<!\w) might treat accented letters differently.
        real_matches = []
        for line_num, line in matches:
            words = re.findall(r"[\w\u00C0-\u1EF9]+", line.lower())
            if fp in words or (len(fp.split()) > 1 and fp in line.lower()):
                real_matches.append((line_num, line))
        if real_matches:
            print(f"[{f.name}] First-person pronoun '{fp}' found on {len(real_matches)} lines:")
            for l_num, l_text in real_matches[:5]:
                print(f"   Line {l_num}: {l_text[:100]}")
            file_issues += len(real_matches)

    # 2. Trader slang
    for sl in slang:
        matches = [(i+1, l.strip()) for i, l in enumerate(lines) if sl in l.lower()]
        if matches:
            print(f"[{f.name}] Trader slang '{sl}' found on {len(matches)} lines:")
            for l_num, l_text in matches[:5]:
                print(f"   Line {l_num}: {l_text[:100]}")
            file_issues += len(matches)

    # 3. AI cliches
    for cl in ai_cliches:
        matches = [(i+1, l.strip()) for i, l in enumerate(lines) if cl in l.lower()]
        if matches:
            print(f"[{f.name}] AI cliche '{cl}' found on {len(matches)} lines:")
            for l_num, l_text in matches[:5]:
                print(f"   Line {l_num}: {l_text[:100]}")
            file_issues += len(matches)

    # 4. Emojis
    emojis = [(i+1, emoji_pattern.findall(l)) for i, l in enumerate(lines) if emoji_pattern.search(l)]
    if emojis:
        print(f"[{f.name}] Emojis found on {len(emojis)} lines:")
        for l_num, em_list in emojis[:5]:
            print(f"   Line {l_num}: {em_list}")
        file_issues += len(emojis)

    # 5. Heading audit (Rule 9: No numbers, no sensational words in headings)
    headings = [(i+1, l.strip()) for i, l in enumerate(lines) if l.strip().startswith("#")]
    for h_num, h_text in headings:
        # Check if heading contains sensational words or percentage results
        if re.search(r"\b\d+[\.,]\d+%", h_text):
            print(f"[{f.name}] Heading with percentage result: Line {h_num}: {h_text}")
            file_issues += 1
        for bad_w in ["bất lực", "thần thánh", "siêu việt", "bóc trần", "hoàn hảo"]:
            if bad_w in h_text.lower():
                print(f"[{f.name}] Heading with sensational word '{bad_w}': Line {h_num}: {h_text}")
                file_issues += 1

    if file_issues == 0:
        print(f"[PASS] {f.name}: 0 violations of tone, slang, AI cliches, emojis, or sensational headings.")
    else:
        issues_found += file_issues
    print()

print(f"Audit completed. Total issues flagged: {issues_found}")
