import json

with open(r"c:\Users\vong2\OneDrive\Tài liệu\Quant_System\Kho_Do_An\Quant_AI_V2.2\research\strict_walk_forward_oos_results.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for thresh in ["0.0", "0.32", "0.34", "0.36", "0.38", "0.4", "0.42"]:
    tdata = data["results"][thresh]
    print(f"Thresh {thresh:>4}: total={tdata['total_trades']:<4} wins={tdata['wins']:<3} losses={tdata['losses']:<3} wr={tdata['winrate_pct']:.2f}% net=${tdata['net_profit_usd']:<10.2f} maxdd={tdata['max_drawdown_pct']:.2f}% pf={tdata['profit_factor']:.2f}")

print("\n--- Yearly breakdown for P=0.0 ---")
for yr, yd in data["results"]["0.0"]["yearly"].items():
    print(f"{yr}: trades={yd['trades']}, wins={yd['wins']}, losses={yd['trades']-yd['wins']}, wr={yd['winrate']}%, pnl=${yd['pnl']:,.2f}")

print("\n--- Yearly breakdown for P=0.38 ---")
for yr, yd in data["results"]["0.38"]["yearly"].items():
    print(f"{yr}: trades={yd['trades']}, wins={yd['wins']}, losses={yd['trades']-yd['wins']}, wr={yd['winrate']}%, pnl=${yd['pnl']:,.2f}")
