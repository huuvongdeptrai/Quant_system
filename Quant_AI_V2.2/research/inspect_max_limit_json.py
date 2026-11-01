import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('Kho_Do_An/Quant_AI_V2.2/research/max_limit_4year_results.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

for r in d['results']:
    print('CONFIG:', r.get('config_name'), 'TOTAL PROFIT:', r.get('net_profit_usd'), 'TRADES:', r.get('total_trades'))
    yb = r.get('yearly_breakdown', {})
    sum_pnl = 0
    for year, stats in yb.items():
        pnl = stats.get('pnl', 0)
        sum_pnl += pnl
        print(f"   {year}: pnl={pnl} trades={stats.get('trades')} winrate={stats.get('winrate')}")
    print(f"   Sum of yearly PnL: {sum_pnl:.2f}\n")
