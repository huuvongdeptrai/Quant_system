import json
import sys
import pandas as pd

# Let's inspect max_limit_4year_results.json
p1 = 'Kho_Do_An/Quant_AI_V2.2/research/max_limit_4year_results.json'
with open(p1, 'r', encoding='utf-8') as f:
    d1 = json.load(f)

print("Historical data range in max_limit_4year_results.json:")
print("From:", d1.get("from"))
print("To:", d1.get("to"))
