import json
import sys
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

# Check baseline drawdown in max_limit_4year_results.json or run a check
# In Section 4.4.2, the 47.97% max drawdown of Dynamic:
# Let's see: In 2022: -13,796; 2023: -15,926; 2024: -11,271
# Initial balance was 100,000. Balance went down from 100k to ~59k at the end of 2024!
# (100k - 59k) / 100k = ~41%, and intra-year drawdown reached 47.97% in late 2024!
# Then in 2025 it started going up!
print("User suggestion: 'trên toàn kỳ kiểm thử, Max Drawdown đạt 47.97%, trong khi chiến lược ghi nhận kết quả âm ở các giai đoạn 2022–2024'.")
