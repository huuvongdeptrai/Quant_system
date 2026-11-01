import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

df_canon = pd.read_parquet('Kho_Do_An/Quant_AI_V2.2/research/oos_df_canonical.parquet')
print("Columns:", list(df_canon.columns))
print(df_canon.head(10))

for yr, g in df_canon.groupby("year"):
    print(f"Year {yr}: sum_pnl={g['pnl'].sum():.2f}")
