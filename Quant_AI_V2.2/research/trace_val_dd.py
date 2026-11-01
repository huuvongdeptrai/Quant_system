import pandas as pd
import numpy as np

df = pd.read_parquet("Kho_Do_An/Quant_AI_V2.2/research/oos_canonical_reproduced.parquet")

def trace_dd(f, name=""):
    bal = 100000.0
    curve = [bal]
    for p in f["pnl"]:
        bal += p
        curve.append(bal)
    c_arr = np.array(curve)
    pk = np.maximum.accumulate(c_arr)
    dd = np.where(pk > 0, (pk - c_arr) / pk, 0.0)
    max_idx = np.argmax(dd)
    max_dd = np.max(dd) * 100.0
    return max_dd, pk[max_idx], c_arr[max_idx], max_idx

print("=== THRESHOLD 0.38 TRACE ===")
f = df[df["pred_prob"] >= 0.38]
print(f"Total trades: {len(f)}")
val_f = f[f["year"].isin(["2023", "2024"])]
test_f = f[f["year"].isin(["2025", "2026"])]

mdd_full, pk_f, vl_f, idx_f = trace_dd(f, "Full")
print(f"Full 2023-2026: MaxDD = {mdd_full:.2f}%, Peak = ${pk_f:,.2f}, Valley = ${vl_f:,.2f}, Trade = {idx_f}")

mdd_val, pk_v, vl_v, idx_v = trace_dd(val_f, "Validation 2023-2024")
print(f"Validation 2023-2024 (Isolated): MaxDD = {mdd_val:.2f}%, Peak = ${pk_v:,.2f}, Valley = ${vl_v:,.2f}, Trade = {idx_v}")

mdd_test, pk_t, vl_t, idx_t = trace_dd(test_f, "Test 2025-2026")
print(f"Test 2025-2026 (Isolated): MaxDD = {mdd_test:.2f}%, Peak = ${pk_t:,.2f}, Valley = ${vl_t:,.2f}, Trade = {idx_t}")
