import sys
from pathlib import Path
import json
import numpy as np

with open(r"Kho_Do_An/Quant_AI_V2.2/research/strict_walk_forward_oos_results.json", "r", encoding="utf-8") as f:
    d = json.load(f)["results"]

print("--- CANONICAL JSON BREAKDOWN ---")
for t in ["0.0", "0.32", "0.34", "0.36", "0.38", "0.4", "0.42"]:
    v_tr = d[t]["yearly"]["2023"]["trades"] + d[t]["yearly"]["2024"]["trades"]
    v_w = d[t]["yearly"]["2023"]["wins"] + d[t]["yearly"]["2024"]["wins"]
    v_pnl = d[t]["yearly"]["2023"]["pnl"] + d[t]["yearly"]["2024"]["pnl"]
    
    te_tr = d[t]["yearly"]["2025"]["trades"] + d[t]["yearly"]["2026"]["trades"]
    te_w = d[t]["yearly"]["2025"]["wins"] + d[t]["yearly"]["2026"]["wins"]
    te_pnl = d[t]["yearly"]["2025"]["pnl"] + d[t]["yearly"]["2026"]["pnl"]
    
    tot_tr = d[t]["total_trades"]
    tot_w = d[t]["wins"]
    tot_pnl = d[t]["net_profit_usd"]
    tot_dd = d[t]["max_drawdown_pct"]
    tot_pf = d[t]["profit_factor"]
    
    print(f"Thresh {t:<4} | Val: {v_tr:3d} tr, {v_w:2d}W ({v_w/v_tr*100:5.2f}%), ${v_pnl:9.2f} | Test: {te_tr:3d} tr, {te_w:2d}W ({te_w/te_tr*100:5.2f}%), ${te_pnl:9.2f} | Tot: {tot_tr:3d} tr, {tot_w:2d}W, ${tot_pnl:9.2f}, DD {tot_dd:5.2f}%, PF {tot_pf:4.2f}")
