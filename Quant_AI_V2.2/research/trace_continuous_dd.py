import sys
from pathlib import Path
import json
import numpy as np
import pandas as pd

# Let's inspect the continuous curve of oos_df
df = pd.read_parquet("Kho_Do_An/Quant_AI_V2.2/research/oos_df_canonical.parquet")

for thresh in [0.0, 0.38]:
    f = df[df["pred_prob"] >= thresh] if thresh > 0.0 else df
    f = f.sort_values("entry_time").reset_index(drop=True)
    bal = 100000.0
    curve = [bal]
    times = [f["entry_time"].iloc[0]]
    for _, r in f.iterrows():
        bal += r["pnl"]
        curve.append(bal)
        times.append(r["entry_time"])
    
    c_arr = np.array(curve)
    pk = np.maximum.accumulate(c_arr)
    dd = np.where(pk > 0, (pk - c_arr) / pk, 0.0)
    max_idx = np.argmax(dd)
    print(f"\n==========================================")
    print(f"CONTINUOUS CURVE STATS FOR P >= {thresh} ({len(f)} trades)")
    print(f"==========================================")
    print(f"Final Balance: ${bal:,.2f} | Net: ${bal-100000:,.2f}")
    print(f"Max Continuous DD: {np.max(dd)*100:.2f}% at trade {max_idx} ({times[max_idx]})")
    print(f"Peak before Max DD: ${pk[max_idx]:,.2f}, Valley at Max DD: ${c_arr[max_idx]:,.2f}")
    
    # Yearly max DD along this CONTINUOUS curve:
    # Notice: at each point in year Y, peak is relative to max so far on continuous curve
    for yr in ["2023", "2024", "2025", "2026"]:
        yr_mask = [False] + list(f["year"] == yr)
        yr_dd = dd[yr_mask]
        print(f"   Year {yr}: trades {(f['year']==yr).sum()}, Net PnL ${f[f['year']==yr]['pnl'].sum():,.2f}, Max DD in continuous curve: {np.max(yr_dd)*100:.2f}%")

    # Now let's calculate what happens if each period is isolated with Initial Capital = 100,000 USD:
    print("\n--- ISOLATED SUB-PERIODS (RESET CAPITAL = $100,000) ---")
    val_sub = f[f["year"].isin(["2023", "2024"])]
    test_sub = f[f["year"].isin(["2025", "2026"])]
    for name, sub in [("Validation 2023-2024", val_sub), ("Holdout Test 2025-2026", test_sub)]:
        b = 100000.0
        c = [b]
        for p in sub["pnl"]:
            b += p
            c.append(b)
        ca = np.array(c)
        pka = np.maximum.accumulate(ca)
        dda = np.where(pka > 0, (pka - ca) / pka, 0.0)
        print(f"   {name}: trades {len(sub)}, Net ${b-100000:,.2f}, Max DD (Isolated): {np.max(dda)*100:.2f}%")
