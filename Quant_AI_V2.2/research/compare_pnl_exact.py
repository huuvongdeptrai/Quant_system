import json
import sys
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

# Compare 2023-2024 and 2025-2026 PnL:
# In max_limit_4year_results.json:
# 2023: -15,925.76 USD
# 2024: -11,270.96 USD
# Sum 2023-2024: -27,196.72 USD
# 2025: +40,300.08 USD
# 2026: +54,502.91 USD
# Sum 2025-2026: +94,802.99 USD
# Total 2023-2026: +67,606.27 USD

# In strict_walk_forward_oos_results.json (and Tables 4.5, 4.6, 4.7):
# 2023: -16,047.16 USD
# 2024: -11,383.16 USD
# Sum 2023-2024: -27,430.32 USD
# 2025: +40,899.87 USD
# 2026: +55,281.98 USD
# Sum 2025-2026: +96,181.85 USD
# Total 2023-2026: +68,751.53 USD

print("Comparison of Yearly PnL:")
print("2023: max_limit = -15,925.76 | walk_forward = -16,047.16 | diff =", -16047.16 - (-15925.76))
print("2024: max_limit = -11,270.96 | walk_forward = -11,383.16 | diff =", -11383.16 - (-11270.96))
print("2025: max_limit = +40,300.08 | walk_forward = +40,899.87 | diff =", 40899.87 - 40300.08)
print("2026: max_limit = +54,502.91 | walk_forward = +55,281.98 | diff =", 55281.98 - 54502.91)
print("Total 2023-2024: max_limit = -27,196.72 | walk_forward = -27,430.32")
print("Total 2025-2026: max_limit = +94,802.99 | walk_forward = +96,181.85")
print("Total 2023-2026: max_limit = +67,606.27 | walk_forward = +68,751.53")
print("Total 2022-2026: max_limit = +53,810.41 (with 2022: -13,795.74)")
