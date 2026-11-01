import json
import sys
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

# 1. Load strict_walk_forward_oos_results.json
p = 'Kho_Do_An/Quant_AI_V2.2/research/strict_walk_forward_oos_results.json'
with open(p, 'r', encoding='utf-8') as f:
    d = json.load(f)

print("=== strict_walk_forward_oos_results.json ===")
for th, v in d['results'].items():
    print(f"Thresh {th}: max_dd={v.get('max_drawdown_pct')}% | return={v.get('return_pct')}% | pnl_sum={v.get('net_profit')}")

# 2. Check oos_df_canonical.parquet
p3 = 'Kho_Do_An/Quant_AI_V2.2/research/oos_df_canonical.parquet'
df = pd.read_parquet(p3)
print("\n=== Calculating Max Drawdown from oos_df_canonical ===")
initial_cap = 100000.0

for th in [0.0, 0.32, 0.34, 0.36, 0.38, 0.40, 0.42]:
    sub = df[df['pred_prob'] >= th] if th > 0 else df
    # Let's compute equity curve by cumsum of PnL:
    # Method A: equity = 100000 + cumsum(pnl)
    eq_a = initial_cap + sub['pnl'].cumsum()
    peak_a = np.maximum.accumulate(np.insert(eq_a.values, 0, initial_cap))
    eq_arr_a = np.insert(eq_a.values, 0, initial_cap)
    dd_a = (peak_a - eq_arr_a) / peak_a * 100.0
    max_dd_a = np.max(dd_a)

    print(f"Thresh {th}: Trades={len(sub)} | Net PnL={sub['pnl'].sum():,.2f} | Max DD (Cumsum on $100k)={max_dd_a:.2f}%")
