import sys
from pathlib import Path
import numpy as np
import pandas as pd
import json

PROJECT_ROOT = Path("Kho_Do_An/Quant_AI_V2.2").resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Let's check how run_expanding_walk_forward.py evaluates drawdown
# We can re-run the loop in run_expanding_walk_forward or extract trades.
