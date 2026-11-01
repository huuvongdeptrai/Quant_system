import sys
import pandas as pd
import json

sys.stdout.reconfigure(encoding='utf-8')

# Let's inspect run_canonical_splits_breakdown or run_expanding_walk_forward
# Where did the trade records come from?
# In both scripts, tester.run(df) is called.
# Why would tester.run(df) produce -15,925.76 in run_max_limit_4year_benchmark,
# but -16,047.16 in run_expanding_walk_forward?

# Let's check the date of rates in run_max_limit vs run_expanding:
# Let's inspect max_limit_4year_results.json
with open('Kho_Do_An/Quant_AI_V2.2/research/max_limit_4year_results.json', 'r', encoding='utf-8') as f:
    d_max = json.load(f)

print("d_max from:", d_max.get("from"), "to:", d_max.get("to"))

# In run_expanding_walk_forward.py, line 44:
# rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, bars_count)
# What was df['time'].iloc[0] and df['time'].iloc[-1]?
