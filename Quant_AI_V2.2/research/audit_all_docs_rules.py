# -*- coding: utf-8 -*-
import os
import glob
import re
import sys

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

thesis_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'docs', 'thesis')
files = sorted(glob.glob(os.path.join(thesis_dir, '*.md')))

# Rule 1: Pronouns & Trader slang & Subjective adjectives
pronoun_patterns = [
    r'\btôi\b', r'\bem\b', r'\bchúng tôi\b', r'\bchúng em\b', 
    r'\bnhóm em\b', r'\bnhóm tôi\b', r'\bnhóm chúng tôi\b'
]
slang_patterns = [
    'cắn sl', 'hít tp', 'quét râu', 'rút chân', 'nhồi lệnh', 'gồng lỗ', 'gồng lãi'
]
subjective_patterns = [
    'có vẻ', 'khá mượt', 'rất tốt', 'rất nhanh', 'cực kỳ tốt', 'siêu việt', 'thần thánh'
]

# Rule 8: AI Cliches & Glorification
cliche_patterns = [
    'bức tranh', 'dệt nên', 'đi sâu vào', 'mảnh ghép hoàn hảo', 'chứng minh vị thế',
    'chiếc cầu nối', 'đóng vai trò như một chiếc cầu nối', 'vô cùng hoàn hảo', 
    'bất khả chiến bại', 'hoàn hảo'
]

# Rule 9: Sensational Headings
sensational_heading_words = [
    '%', 'sự bất lực', 'bóc trần', 'thần thánh', 'siêu việt', 'vượt trội hoàn toàn', 'bất khả chiến bại'
]

# Emojis (GEMINI.md & DESIGN.md)
emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]|[\u2600-\u27ff]|[\u2300-\u23ff]')

print(f"Auditing {len(files)} thesis files in: {thesis_dir}\n")

findings = []

for fpath in files:
    fname = os.path.basename(fpath)
    with open(fpath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    file_findings = []
    
    for i, line in enumerate(lines, 1):
        line_clean = line.strip()
        lower = line_clean.lower()
        
        # Rule 1: Pronouns
        for p in pronoun_patterns:
            m = re.search(p, lower)
            if m:
                # Exclude if it's "xem xét", "điểm", etc. (handled by word boundary \b)
                # Note: "em" might match "hệ thống", but \bem\b won't. Wait, in Vietnamese, "em" is a word.
                # Let's inspect context
                file_findings.append((i, "RULE_1_PRONOUN", f"Found pronoun '{m.group(0)}'", line_clean))
        
        # Rule 1: Slang
        for s in slang_patterns:
            if s in lower:
                file_findings.append((i, "RULE_1_SLANG", f"Found trader slang '{s}'", line_clean))
                
        # Rule 1: Subjective words
        for sub in subjective_patterns:
            if sub in lower:
                file_findings.append((i, "RULE_1_SUBJECTIVE", f"Found subjective wording '{sub}'", line_clean))
                
        # Rule 8: AI Cliches
        for c in cliche_patterns:
            if c in lower:
                file_findings.append((i, "RULE_8_CLICHE", f"Found AI cliché/glorification '{c}'", line_clean))
                
        # Rule 9: Sensational Headings
        if line_clean.startswith('#'):
            for sh in sensational_heading_words:
                if sh in lower:
                    file_findings.append((i, "RULE_9_HEADING", f"Found sensational/metric in heading '{sh}'", line_clean))
                    
        # Emojis
        emojis = emoji_pattern.findall(line_clean)
        if emojis:
            # Filter out standard math symbols if any got caught (like arrows or bullet points)
            bad_emojis = [e for e in emojis if ord(e) > 0x27bf or e in ['🚀', '📈', '💰', '🔥', '❌', '🟢', '⚙️', '🔹', '🛑']]
            if bad_emojis:
                file_findings.append((i, "GEMINI_EMOJI", f"Found emoji '{bad_emojis}'", line_clean))

    if file_findings:
        print(f"=== {fname} ({len(file_findings)} findings) ===")
        for f in file_findings:
            print(f"  Line {f[0]} [{f[1]}]: {f[2]}")
            print(f"    Excerpt: {f[3][:120]}")
    else:
        print(f"=== {fname}: PERFECT (0 automated violations) ===")

print("\nAudit completed.")
