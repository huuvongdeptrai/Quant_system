with open('Kho_Do_An/Quant_AI_V2.2/docs/thesis/chuong_4_thuc_nghiem.md', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace the two remaining -$27,430.32 and +$2,968.51
text = text.replace(r'$-\$27,430.32$ USD', '-$27,430.32 USD')
text = text.replace(r'$+\$2,968.51$ USD', '+$2,968.51 USD')

with open('Kho_Do_An/Quant_AI_V2.2/docs/thesis/chuong_4_thuc_nghiem.md', 'w', encoding='utf-8') as f:
    f.write(text)

print('Replaced remaining 2 items')
