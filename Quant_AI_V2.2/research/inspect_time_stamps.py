import pandas as pd
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

# 1. max_limit_4year_results.json
with open('Kho_Do_An/Quant_AI_V2.2/research/max_limit_4year_results.json', 'r', encoding='utf-8') as f:
    d_max = json.load(f)
print("max_limit From:", d_max['from'], "To:", d_max['to'])

# 2. oos_df_canonical.parquet
df_oos = pd.read_parquet('Kho_Do_An/Quant_AI_V2.2/research/oos_df_canonical.parquet')
print("oos_df_canonical min entry:", df_oos['entry_time'].min(), "max entry:", df_oos['entry_time'].max())

# Let's check strict_walk_forward_oos_results.json
with open('Kho_Do_An/Quant_AI_V2.2/research/strict_walk_forward_oos_results.json', 'r', encoding='utf-8') as f:
    d_strict = json.load(f)
print("strict_walk_forward description:", d_strict['description'])
