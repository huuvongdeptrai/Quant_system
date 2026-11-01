import json
import sys
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

# 1. max_limit_4year_results.json
p1 = 'Kho_Do_An/Quant_AI_V2.2/research/max_limit_4year_results.json'
with open(p1, 'r', encoding='utf-8') as f:
    d1 = json.load(f)

print("=== max_limit_4year_results.json ===")
print("From:", d1.get("from"), "To:", d1.get("to"), "Total bars:", d1.get("total_bars"))
for r in d1['results']:
    print(f"\nConfig: {r.get('config_name')}")
    print(f"Total Net Profit: {r.get('net_profit_usd')} | Trades: {r.get('total_trades')}")
    yb = r.get('yearly_breakdown', {})
    for y in sorted(yb.keys()):
        s = yb[y]
        print(f"  {y}: pnl={s.get('pnl')} trades={s.get('trades')} wins={s.get('wins')} losses={s.get('losses')}")

# 2. strict_walk_forward_oos_results.json
p2 = 'Kho_Do_An/Quant_AI_V2.2/research/strict_walk_forward_oos_results.json'
try:
    with open(p2, 'r', encoding='utf-8') as f:
        d2 = json.load(f)
    print("\n=== strict_walk_forward_oos_results.json ===")
    print("Keys:", list(d2.keys()))
    if isinstance(d2, dict):
        for k, v in d2.items():
            if isinstance(v, dict):
                print(f"Key {k}: {list(v.keys())[:10]}")
            elif isinstance(v, list):
                print(f"Key {k} (list len {len(v)}): {v[:2]}")
            else:
                print(f"Key {k}: {v}")
except Exception as e:
    print("p2 error:", e)

# 3. oos_df_canonical.parquet
p3 = 'Kho_Do_An/Quant_AI_V2.2/research/oos_df_canonical.parquet'
try:
    df = pd.read_parquet(p3)
    print("\n=== oos_df_canonical.parquet ===")
    print(f"Shape: {df.shape}")
    print("Columns:", list(df.columns))
    print("Min entry_time:", df['entry_time'].min(), "Max entry_time:", df['entry_time'].max())
    print("Total trades:", len(df))
    print("Total pnl sum:", df['pnl'].sum())
except Exception as e:
    print("p3 error:", e)
