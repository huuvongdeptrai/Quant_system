import json
import sys

with open(r"Kho_Do_An/Quant_AI_V2.2/research/strict_walk_forward_oos_results.json", "r", encoding="utf-8") as f:
    d = json.load(f)["results"]

print(f"{'Thresh':<7} | {'Val Trades':<10} | {'Val Wins':<8} | {'Val PnL':<12} | {'Test Trades':<11} | {'Test Wins':<9} | {'Test PnL':<12} | {'Tot Trades':<10} | {'Tot Wins':<8} | {'Tot PnL':<12}")
print("-" * 115)

for t in ["0.0", "0.32", "0.34", "0.36", "0.38", "0.4", "0.42"]:
    val_t = d[t]["yearly"]["2023"]["trades"] + d[t]["yearly"]["2024"]["trades"]
    val_w = d[t]["yearly"]["2023"]["wins"] + d[t]["yearly"]["2024"]["wins"]
    val_pnl = d[t]["yearly"]["2023"]["pnl"] + d[t]["yearly"]["2024"]["pnl"]
    
    test_t = d[t]["yearly"]["2025"]["trades"] + d[t]["yearly"]["2026"]["trades"]
    test_w = d[t]["yearly"]["2025"]["wins"] + d[t]["yearly"]["2026"]["wins"]
    test_pnl = d[t]["yearly"]["2025"]["pnl"] + d[t]["yearly"]["2026"]["pnl"]
    
    tot_t = d[t]["total_trades"]
    tot_w = d[t]["wins"]
    tot_pnl = d[t]["net_profit_usd"]
    
    print(f"{t:<7} | {val_t:<10} | {val_w:<8} | ${val_pnl:<11,.2f} | {test_t:<11} | {test_w:<9} | ${test_pnl:<11,.2f} | {tot_t:<10} | {tot_w:<8} | ${tot_pnl:<11,.2f}")
