import sys
from pathlib import Path
import json
import numpy as np
import pandas as pd

# Let's inspect run_canonical_splits_breakdown.py test_df
# In task-61477 or task-61489:
# For Test Set (2025-2026) at 300 trades:
# Thresh 0.0: Trades 300, Wins 117, Losses 183, Winrate 39.00%, Net Profit $97,475.77, MaxDD 9.95%, PF 1.48
# Thresh 0.38: Trades 59 or 62.
# Let's check the exact PnL list for 2025 and 2026 from the canonical run.
