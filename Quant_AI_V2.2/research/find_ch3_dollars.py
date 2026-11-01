with open('Kho_Do_An/Quant_AI_V2.2/docs/thesis/chuong_3_thiet_ke_he_thong.md', 'r', encoding='utf-8') as f:
    text = f.read()

import re
matches = [m.start() for m in re.finditer(r'\\\$', text)]
print('Matches for backslash dollar in ch3:', len(matches))
for m in matches:
    print(repr(text[max(0, m-50):min(len(text), m+50)]))
