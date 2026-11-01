import json
import sys
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

# 1. max_limit_4year_results.json
with open('Kho_Do_An/Quant_AI_V2.2/research/max_limit_4year_results.json', 'r', encoding='utf-8') as f:
    d_max = json.load(f)

print("=== max_limit_4year_results.json ===")
print("from:", d_max.get("from"))
print("to:", d_max.get("to"))
print("total_bars:", d_max.get("total_bars"))
print("years:", d_max.get("years"))

# 2. strict_walk_forward_oos_results.json
with open('Kho_Do_An/Quant_AI_V2.2/research/strict_walk_forward_oos_results.json', 'r', encoding='utf-8') as f:
    d_strict = json.load(f)

print("\n=== strict_walk_forward_oos_results.json ===")
print("description:", d_strict.get("description"))
print("total_bars:", d_strict.get("total_bars"))

# 3. oos_df_canonical.parquet
try:
    df_canon = pd.read_parquet('Kho_Do_An/Quant_AI_V2.2/research/oos_df_canonical.parquet')
    print("\n=== oos_df_canonical.parquet ===")
    print("len:", len(df_canon))
    print("min entry_time:", df_canon['entry_time'].min())
    print("max entry_time:", df_canon['entry_time'].max())
    print("sum pnl:", df_canon['pnl'].sum())
except Exception as e:
    print("oos_df_canonical error:", e)

# 4. oos_canonical_reproduced.parquet
try:
    df_reprod = pd.read_parquet('Kho_Do_An/Quant_AI_V2.2/research/oos_canonical_reproduced.parquet')
    print("\n=== oos_canonical_reproduced.parquet ===")
    print("len:", len(df_reprod))
    print("min entry_time:", df_reprod['entry_time'].min())
    print("max entry_time:", df_reprod['entry_time'].max())
    print("sum pnl:", df_reprod['pnl'].sum())
except Exception as e:
    print("oos_canonical_reproduced error:", e)
