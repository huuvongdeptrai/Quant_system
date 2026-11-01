import sys
import pandas as pd
import json

sys.stdout.reconfigure(encoding='utf-8')

# 1. Read df_oos
df_oos = pd.read_parquet('Kho_Do_An/Quant_AI_V2.2/research/oos_df_canonical.parquet')
print("=== oos_df_canonical.parquet ===")
for y, g in df_oos.groupby('year'):
    print(f"Year {y}: trades={len(g)}, sum_pnl={g['pnl'].sum():.2f}")

# 2. Read strict_walk_forward_oos_results.json
with open('Kho_Do_An/Quant_AI_V2.2/research/strict_walk_forward_oos_results.json', 'r', encoding='utf-8') as f:
    d_strict = json.load(f)

print("\n=== strict_walk_forward_oos_results.json (thresh 0.0) ===")
res_0 = d_strict['results']['0.0']['yearly']
for y, s in res_0.items():
    print(f"Year {y}: trades={s['trades']}, wins={s['wins']}, pnl={s['pnl']}")

# 3. Read max_limit_4year_results.json
with open('Kho_Do_An/Quant_AI_V2.2/research/max_limit_4year_results.json', 'r', encoding='utf-8') as f:
    d_max = json.load(f)

for r in d_max['results']:
    if 'Dynamic' in r['config_name']:
        print(f"\n=== max_limit_4year_results.json ({r['config_name']}) ===")
        for y, s in r['yearly_breakdown'].items():
            print(f"Year {y}: trades={s['trades']}, wins={s['wins']}, pnl={s['pnl']}")
