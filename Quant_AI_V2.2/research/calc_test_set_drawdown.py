import json
import numpy as np

with open(r"c:\Users\vong2\OneDrive\Tài liệu\Quant_System\Kho_Do_An\Quant_AI_V2.2\research\strict_walk_forward_oos_results.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Let's inspect run_expanding_walk_forward.py to see how oos_df was generated
# or let's inspect the trades
