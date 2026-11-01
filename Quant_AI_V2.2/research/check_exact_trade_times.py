import json
import sys
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

# Check oos_df_canonical.parquet
p3 = 'Kho_Do_An/Quant_AI_V2.2/research/oos_df_canonical.parquet'
df = pd.read_parquet(p3)

print("First trade in oos_df:", df.iloc[0]['entry_time'], "Year:", df.iloc[0]['year'])
print("Last trade in oos_df:", df.iloc[-1]['entry_time'], "Year:", df.iloc[-1]['year'])

df_2022 = df[df['year'] == '2022']
print("2022 trades in oos_df:", len(df_2022))

df_2023_2024 = df[df['year'].isin(['2023', '2024'])]
print("2023-2024 trades in oos_df:", len(df_2023_2024))
print("  First 2023:", df_2023_2024.iloc[0]['entry_time'])
print("  Last 2024:", df_2023_2024.iloc[-1]['entry_time'])

df_2025_2026 = df[df['year'].isin(['2025', '2026'])]
print("2025-2026 trades in oos_df:", len(df_2025_2026))
print("  First 2025:", df_2025_2026.iloc[0]['entry_time'])
print("  Last 2026:", df_2025_2026.iloc[-1]['entry_time'])
