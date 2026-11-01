import pandas as pd
import numpy as np

df = pd.read_parquet("Kho_Do_An/Quant_AI_V2.2/research/oos_df_canonical.parquet")

def calc_stats(sub_df, initial_bal=100000.0):
    total = len(sub_df)
    if total == 0:
        return {"trades": 0, "wins": 0, "losses": 0, "wr": 0, "net": 0, "mdd": 0, "pf": 0}
    wins = (sub_df["outcome"] == 1).sum()
    wr = wins / total * 100.0
    bal = initial_bal
    curve = [bal]
    for p in sub_df["pnl"]:
        bal += p
        curve.append(bal)
    c_arr = np.array(curve)
    pk = np.maximum.accumulate(c_arr)
    dd = np.where(pk > 0, (pk - c_arr) / pk, 0.0)
    mdd = np.max(dd) * 100.0
    net = bal - initial_bal
    gp = sub_df[sub_df["pnl"] > 0]["pnl"].sum()
    gl = abs(sub_df[sub_df["pnl"] < 0]["pnl"].sum())
    pf = (gp / gl) if gl > 0 else 99.0
    return {
        "trades": total,
        "wins": int(wins),
        "losses": int(total - wins),
        "wr": round(wr, 2),
        "net": round(net, 2),
        "mdd": round(mdd, 2),
        "pf": round(pf, 2)
    }

val_df = df[df["year"].isin(["2023", "2024"])]
test_df = df[df["year"].isin(["2025", "2026"])]

print("=== VALIDATION SET (2023-2024, ISOLATED STARTING CAPITAL = $100,000) ===")
for th in [0.0, 0.32, 0.34, 0.36, 0.38, 0.40, 0.42]:
    sub = val_df[val_df["pred_prob"] >= th] if th > 0 else val_df
    st = calc_stats(sub)
    j_score = (st["net"] / 100000.0) / (st["mdd"] / 100.0) if st["mdd"] > 0 else 0
    print(f"P >= {th:4.2f}: trades={st['trades']:3d}, wins={st['wins']:2d}, losses={st['losses']:2d}, wr={st['wr']:5.2f}%, net={st['net']:10.2f}, mdd={st['mdd']:5.2f}%, pf={st['pf']:4.2f}, J={j_score:+.2f}")

print("\n=== HOLDOUT TEST SET (2025-2026, ISOLATED STARTING CAPITAL = $100,000) ===")
for th in [0.0, 0.38]:
    sub = test_df[test_df["pred_prob"] >= th] if th > 0 else test_df
    st = calc_stats(sub)
    print(f"P >= {th:4.2f}: trades={st['trades']:3d}, wins={st['wins']:2d}, losses={st['losses']:2d}, wr={st['wr']:5.2f}%, net={st['net']:10.2f}, mdd={st['mdd']:5.2f}%, pf={st['pf']:4.2f}")

print("\n=== FULL CONTINUOUS CURVE (2023-2026, STARTING CAPITAL = $100,000) ===")
for th in [0.0, 0.32, 0.34, 0.36, 0.38, 0.40, 0.42]:
    sub = df[df["pred_prob"] >= th] if th > 0 else df
    st = calc_stats(sub)
    j_score = (st["net"] / 100000.0) / (st["mdd"] / 100.0) if st["mdd"] > 0 else 0
    print(f"P >= {th:4.2f}: trades={st['trades']:3d}, wins={st['wins']:2d}, losses={st['losses']:2d}, wr={st['wr']:5.2f}%, net={st['net']:10.2f}, mdd={st['mdd']:5.2f}%, pf={st['pf']:4.2f}, J={j_score:+.2f}")
