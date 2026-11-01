import sys
sys.stdout.reconfigure(encoding='utf-8')
with open('Kho_Do_An/Quant_AI_V2.2/docs/thesis/chuong_4_thuc_nghiem.md', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print('Line 194:', lines[193].encode('ascii', 'backslashreplace').decode('ascii'))
print('Line 270:', lines[269].encode('ascii', 'backslashreplace').decode('ascii'))
