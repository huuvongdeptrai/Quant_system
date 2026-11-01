import sys
import pandas as pd
import json

sys.stdout.reconfigure(encoding='utf-8')

# Let's inspect where strict_walk_forward_oos_results got its trades
# In run_expanding_walk_forward.py, line 44:
# rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, bars_count)
# In run_max_limit_4year_benchmark.py, line 39:
# rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, bars_count)

# Did run_max_limit_4year_benchmark save trade_records?
# Let's check max_limit_4year_results.json
with open('Kho_Do_An/Quant_AI_V2.2/research/max_limit_4year_results.json', 'r', encoding='utf-8') as f:
    d_max = json.load(f)

print("d_max keys:", list(d_max.keys()))
for r in d_max['results']:
    print("Result config:", r['config_name'], "keys:", list(r.keys()))
