import json
import sys
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

# Compare max_limit_4year_results vs strict_walk_forward_oos_results
with open('Kho_Do_An/Quant_AI_V2.2/research/max_limit_4year_results.json', 'r', encoding='utf-8') as f:
    d_max = json.load(f)

with open('Kho_Do_An/Quant_AI_V2.2/research/strict_walk_forward_oos_results.json', 'r', encoding='utf-8') as f:
    d_strict = json.load(f)

# Find dynamic config in max
dyn = None
for r in d_max['results']:
    if 'Dynamic' in r['config_name']:
        dyn = r
        break

print("=== Section 4.4.2 Dynamic Baseline (max_limit_4year_results.json) ===")
print("Total Trades:", dyn['total_trades'])
print("Total Net Profit:", dyn['net_profit_usd'])
for yr, s in dyn['yearly_breakdown'].items():
    print(f"  {yr}: trades={s['trades']}, wins={s['wins']}, losses={s['losses']}, pnl={s['pnl']}")

print("\n=== Section 4.5 Walk-Forward Baseline P=0.0 (strict_walk_forward_oos_results.json) ===")
s0 = d_strict['results']['0.0']
print("Total Trades:", s0['total_trades'])
print("Total Net Profit:", s0['net_profit_usd'])
for yr, s in s0['yearly'].items():
    print(f"  {yr}: trades={s['trades']}, wins={s['wins']}, losses={s['trades']-s['wins']}, pnl={s['pnl']}")

print("\n=== Section 4.5 Walk-Forward Filtered P>=0.38 ===")
s38 = d_strict['results']['0.38']
print("Total Trades:", s38['total_trades'])
print("Total Net Profit:", s38['net_profit_usd'])
for yr, s in s38['yearly'].items():
    print(f"  {yr}: trades={s['trades']}, wins={s['wins']}, losses={s['trades']-s['wins']}, pnl={s['pnl']}")
