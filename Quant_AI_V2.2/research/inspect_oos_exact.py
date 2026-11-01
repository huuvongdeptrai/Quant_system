import json
import sys
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

# 1. Inspect strict_walk_forward_oos_results.json
p2 = 'Kho_Do_An/Quant_AI_V2.2/research/strict_walk_forward_oos_results.json'
with open(p2, 'r', encoding='utf-8') as f:
    d2 = json.load(f)

print("=== strict_walk_forward_oos_results.json results ===")
for thresh, res in d2['results'].items():
    print(f"Threshold {thresh}:")
    print(f"  Trades: {res.get('trades')} | Wins: {res.get('wins')} | Losses: {res.get('losses')}")
    print(f"  Net Profit: {res.get('net_profit')} | Return Pct: {res.get('return_pct')}% | Max DD: {res.get('max_drawdown_pct')}% | Sharpe: {res.get('sharpe')}")
    yb = res.get('yearly', {})
    for y, s in yb.items():
        print(f"    {y}: pnl={s.get('pnl')} trades={s.get('trades')} winrate={s.get('winrate')}")

# 2. Inspect oos_df_canonical.parquet
p3 = 'Kho_Do_An/Quant_AI_V2.2/research/oos_df_canonical.parquet'
df = pd.read_parquet(p3)
print("\n=== oos_df_canonical breakdown by year ===")
for yr, grp in df.groupby('year'):
    wins = (grp['outcome'] == 1).sum()
    losses = (grp['outcome'] == 0).sum()
    print(f"Year {yr}: PnL sum={grp['pnl'].sum():.2f} | Trades={len(grp)} | Wins={wins} | Losses={losses} | Winrate={wins/len(grp)*100:.2f}%")

# Also check 2023-2024 vs 2025-2026
df_val = df[df['year'].isin([2023, 2024])]
wins_val = (df_val['outcome'] == 1).sum()
losses_val = (df_val['outcome'] == 0).sum()
print(f"\nVal (2023-2024): PnL sum={df_val['pnl'].sum():.2f} | Trades={len(df_val)} | Wins={wins_val} | Losses={losses_val}")

df_test = df[df['year'].isin([2025, 2026])]
wins_test = (df_test['outcome'] == 1).sum()
losses_test = (df_test['outcome'] == 0).sum()
print(f"Test (2025-2026): PnL sum={df_test['pnl'].sum():.2f} | Trades={len(df_test)} | Wins={wins_test} | Losses={losses_test}")
