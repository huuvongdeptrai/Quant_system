import os, sys
sys.stdout.reconfigure(encoding='utf-8')

docs_dir = r'Kho_Do_An/Quant_AI_V2.2/docs/thesis'
for f in os.listdir(docs_dir):
    if f.endswith('.md'):
        p = os.path.join(docs_dir, f)
        with open(p, 'r', encoding='utf-8') as fp:
            content = fp.read()
        if r'\$' in content:
            print(f'Contains backslash dollar: {f}')
