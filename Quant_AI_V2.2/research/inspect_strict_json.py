import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('Kho_Do_An/Quant_AI_V2.2/research/strict_walk_forward_oos_results.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

print("Description:", d.get("description"))
print("Total bars:", d.get("total_bars"))

for th, stats in d['results'].items():
    print(f"\n--- Threshold {th} ---")
    print(f"Total trades: {stats['total_trades']}, Wins: {stats['wins']}, WR: {stats['winrate_pct']}%")
    print(f"Net profit: {stats['net_profit_usd']}, MaxDD: {stats['max_drawdown_pct']}%, PF: {stats['profit_factor']}")
    yb = stats.get('yearly', {})
    for y, ys in yb.items():
        print(f"   Year {y}: trades={ys['trades']}, wins={ys['wins']}, wr={ys['winrate']}%, pnl={ys['pnl']}")
