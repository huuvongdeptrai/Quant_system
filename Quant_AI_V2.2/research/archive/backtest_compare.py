# =============================================================================
# BACKTEST COMPARISON ENGINE
# ICT Zones Pro v1 (Baseline) vs v2 (Challenger)
# Chạy: python research/backtest_compare.py
# =============================================================================
import sys
import os
import glob
import warnings
import json
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

# --- Tìm Project Root ---
_search = os.path.join(os.path.expanduser("~"), "OneDrive", "*",
                       "Quant_System", "Quant_AI")
_candidates = glob.glob(_search)
PROJECT_ROOT = Path(_candidates[0]) if _candidates else Path(__file__).resolve().parent.parent

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "research"))


# ======================== 1. LẤY DỮ LIỆU ========================
def fetch_data(symbol="XAUUSD", timeframe="M30", count=2600) -> pd.DataFrame:
    print(f"\n[DATA] Fetching {count} bars of {symbol} {timeframe} from MT5...")
    try:
        from core.core1_data.mt5_engine import MT5DataEngine
        engine = MT5DataEngine()
        df = engine.fetch_ohlcv(symbol, timeframe, count)
        if df is not None and not df.empty:
            df = df.reset_index()
            print(f"[DATA] MT5 OK: {len(df)} bars")
            return df
        raise ValueError("MT5 returned empty data")
    except Exception as e:
        print(f"[DATA] MT5 failed ({e}). Falling back to yfinance...")
        try:
            import yfinance as yf
            gold = yf.download("GC=F", period="60d", interval="30m", progress=False)
            gold = gold.reset_index()
            gold.columns = ['_'.join([str(x).lower() for x in (c if isinstance(c, tuple) else (c,)) if x]).strip('_') for c in gold.columns]
            gold = gold.reset_index()
            for col in list(gold.columns):
                if col in ['datetime', 'date', 'index', 'level_0']:
                    gold = gold.rename(columns={col: 'time'})
                    break
            for col in list(gold.columns):
                if 'open' in col: gold = gold.rename(columns={col: 'open'})
                elif 'high' in col: gold = gold.rename(columns={col: 'high'})
                elif 'low' in col and 'close' not in col: gold = gold.rename(columns={col: 'low'})
                elif 'close' in col: gold = gold.rename(columns={col: 'close'})
                elif 'volume' in col: gold = gold.rename(columns={col: 'volume'})
            keep = [c for c in ['time','open','high','low','close','volume'] if c in gold.columns]
            gold = gold[keep].dropna()
            gold = gold.tail(count).reset_index(drop=True)
            print(f"[DATA] yfinance OK: {len(gold)} bars")
            return gold
        except Exception as e2:
            print(f"[DATA] yfinance also failed: {e2}")
            return pd.DataFrame()


# ======================== 2. SIMULATION ENGINE ========================
MACRO_CONTEXT = {
    "bias": "NEUTRAL",
    "confidence": 0.5,
    "volatility_risk": "LOW",
    "summary": "Backtest fixed macro context"
}

FIXED_LOT   = 0.1    # Lot cố định mỗi lệnh
POINT_VALUE = 1.0    # 1 point XAUUSD = $1 per 0.01 lot => $10/lot


def run_simulation(strategy_class, df: pd.DataFrame, label: str) -> dict:
    print(f"\n[SIM] Running: {label} on {len(df)} bars...")

    try:
        strategy = strategy_class()
    except Exception as e:
        return {"label": label, "total": 0, "error": str(e)}

    trades    = []
    balance   = 10000.0
    equity    = [balance]
    open_pos  = None
    START_BAR = 300

    for i in range(START_BAR, len(df)):
        row    = df.iloc[i]
        window = df.iloc[: i + 1].copy()

        # --- Quản lý lệnh đang mở ---
        if open_pos is not None:
            pos    = open_pos
            closed = False
            pnl    = 0.0

            if pos["type"] == "BUY":
                if row["low"] <= pos["sl"]:
                    pnl = (pos["sl"] - pos["entry"]) * FIXED_LOT * 100
                    pos.update({"exit": pos["sl"], "reason": "SL"})
                    closed = True
                elif not pos.get("tp1_hit") and pos["tp1"] and row["high"] >= pos["tp1"]:
                    partial = (pos["tp1"] - pos["entry"]) * (FIXED_LOT * 0.5) * 100
                    balance += partial
                    pos.update({"tp1_hit": True, "sl": pos["entry"], "locked": partial})
                elif pos["tp2"] and row["high"] >= pos["tp2"]:
                    pnl = (pos["tp2"] - pos["entry"]) * FIXED_LOT * 100 + pos.get("locked", 0)
                    pos.update({"exit": pos["tp2"], "reason": "TP2"})
                    closed = True

            elif pos["type"] == "SELL":
                if row["high"] >= pos["sl"]:
                    pnl = (pos["entry"] - pos["sl"]) * FIXED_LOT * 100
                    pos.update({"exit": pos["sl"], "reason": "SL"})
                    closed = True
                elif not pos.get("tp1_hit") and pos["tp1"] and row["low"] <= pos["tp1"]:
                    partial = (pos["entry"] - pos["tp1"]) * (FIXED_LOT * 0.5) * 100
                    balance += partial
                    pos.update({"tp1_hit": True, "sl": pos["entry"], "locked": partial})
                elif pos["tp2"] and row["low"] <= pos["tp2"]:
                    pnl = (pos["entry"] - pos["tp2"]) * FIXED_LOT * 100 + pos.get("locked", 0)
                    pos.update({"exit": pos["tp2"], "reason": "TP2"})
                    closed = True

            if closed:
                balance      += pnl
                pos["pnl"]    = round(pnl, 2)
                pos["bal"]    = round(balance, 2)
                trades.append(pos)
                open_pos = None

            equity.append(balance)
            continue

        # --- Phân tích tín hiệu ---
        try:
            result = strategy.analyze(window, MACRO_CONTEXT)
        except Exception:
            equity.append(balance)
            continue

        signal = result.get("signal", "WAIT")
        if signal in ("BUY", "SELL"):
            entry = result.get("entry_price", row["close"])
            sl    = result.get("sl")
            tp1   = result.get("tp1")
            tp2   = result.get("tp2")
            if sl is None or tp2 is None:
                equity.append(balance)
                continue
            open_pos = {
                "type":    signal,
                "entry":   entry,
                "sl":      sl,
                "tp1":     tp1,
                "tp2":     tp2,
                "time":    str(row.get("time", i)),
                "score":   result.get("score", 0),
                "tp1_hit": False,
                "locked":  0.0,
            }

        equity.append(balance)

    # --- Tính Metrics ---
    if not trades:
        return {"label": label, "total": 0, "equity_curve": equity,
                "error": "No trades generated"}

    wins   = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]

    total_profit  = sum(t["pnl"] for t in wins)
    total_loss    = abs(sum(t["pnl"] for t in losses)) or 0.0001
    profit_factor = round(total_profit / total_loss, 3)

    eq_arr  = np.array(equity)
    peak    = np.maximum.accumulate(eq_arr)
    dd      = (peak - eq_arr) / (peak + 1e-9)
    max_dd  = round(float(np.max(dd)) * 100, 2)

    rr_list = []
    for t in trades:
        risk = abs(t["entry"] - t["sl"])
        if risk > 0 and t["tp2"]:
            rr_list.append(abs(t["entry"] - t["tp2"]) / risk)

    metrics = {
        "label":         label,
        "total":         len(trades),
        "wins":          len(wins),
        "losses":        len(losses),
        "winrate":       round(len(wins) / len(trades) * 100, 2),
        "net_pnl":       round(sum(t["pnl"] for t in trades), 2),
        "profit_factor": profit_factor,
        "max_drawdown":  max_dd,
        "avg_rr":        round(sum(rr_list) / len(rr_list), 2) if rr_list else 0,
        "avg_score":     round(sum(t["score"] for t in trades) / len(trades), 2),
        "equity_curve":  [round(e, 2) for e in equity],
        "trades":        trades,
    }
    print(f"[SIM] {label} done: {len(trades)} trades | WR={metrics['winrate']}% | PF={profit_factor}")
    return metrics


# ======================== 3. BÁO CÁO HTML ========================
def render_html(r1: dict, r2: dict, symbol: str, tf: str, out_path: str):
    def badge(v1, v2, hib=True):
        if hib:
            return "&#x25B2;" if v2 > v1 else "&#x25BC;" if v2 < v1 else "="
        else:
            return "&#x25B2;" if v2 < v1 else "&#x25BC;" if v2 > v1 else "="

    def color(v1, v2, hib=True):
        better = (v2 > v1 if hib else v2 < v1)
        return "#3FB950" if better else "#F85149" if v1 != v2 else "#8B949E"

    rows = [
        ("Total Trades",     r1.get("total", 0),         r2.get("total", 0),         True),
        ("Win Rate (%)",     r1.get("winrate", 0),       r2.get("winrate", 0),       True),
        ("Profit Factor",    r1.get("profit_factor", 0), r2.get("profit_factor", 0), True),
        ("Net PnL (USD)",    r1.get("net_pnl", 0),       r2.get("net_pnl", 0),       True),
        ("Max Drawdown (%)", r1.get("max_drawdown", 0),  r2.get("max_drawdown", 0),  False),
        ("Avg RR",           r1.get("avg_rr", 0),        r2.get("avg_rr", 0),        True),
        ("Avg Score",        r1.get("avg_score", 0),     r2.get("avg_score", 0),     True),
    ]

    table_html = ""
    for name, v1, v2, hib in rows:
        c = color(v1, v2, hib)
        b = badge(v1, v2, hib)
        table_html += (
            f'<tr><td>{name}</td><td>{v1}</td>'
            f'<td style="color:{c}">{v2} {b}</td></tr>'
        )

    eq1   = r1.get("equity_curve", [10000])
    eq2   = r2.get("equity_curve", [10000])
    max_l = max(len(eq1), len(eq2))
    eq1  += [eq1[-1]] * (max_l - len(eq1))
    eq2  += [eq2[-1]] * (max_l - len(eq2))

    lbl1 = r1.get("label", "v1")
    lbl2 = r2.get("label", "v2")
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<title>Backtest Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0D1117; color: #C9D1D9; font-family: 'Courier New', monospace; padding: 32px; }}
  h1 {{ color: #58A6FF; font-size: 22px; margin-bottom: 6px; }}
  .meta {{ color: #8B949E; font-size: 13px; margin-bottom: 28px; }}
  h2 {{ color: #8B949E; font-size: 14px; letter-spacing: 2px; text-transform: uppercase;
        border-bottom: 1px solid #30363D; padding-bottom: 8px; margin: 28px 0 16px; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th {{ background: #161B22; color: #58A6FF; padding: 12px 16px; text-align: left;
        font-size: 12px; letter-spacing: 1px; text-transform: uppercase; }}
  td {{ padding: 11px 16px; border-bottom: 1px solid #21262D; font-size: 14px; }}
  tr:hover td {{ background: #161B22; }}
  .chart-wrap {{ background: #161B22; border: 1px solid #30363D; border-radius: 8px;
                 padding: 20px; margin-top: 8px; }}
  canvas {{ max-height: 380px; }}
</style>
</head>
<body>
<h1>&#x1F4CA; Backtest Report — ICT Zones Pro</h1>
<div class="meta">Symbol: <b>{symbol}</b> | Timeframe: <b>{tf}</b> | Generated: <b>{ts}</b></div>
<h2>So Sanh Metrics</h2>
<table>
  <tr><th>Chi So</th><th>{lbl1}</th><th>{lbl2}</th></tr>
  {table_html}
</table>
<h2>Equity Curve</h2>
<div class="chart-wrap">
  <canvas id="eqChart"></canvas>
</div>
<script>
  new Chart(document.getElementById("eqChart").getContext("2d"), {{
    type: "line",
    data: {{
      labels: Array.from({{length: {max_l}}}, (_, i) => i),
      datasets: [
        {{label: "{lbl1}", data: {eq1}, borderColor: "#58A6FF",
          fill: false, tension: 0.1, pointRadius: 0, borderWidth: 1.5}},
        {{label: "{lbl2}", data: {eq2}, borderColor: "#3FB950",
          fill: false, tension: 0.1, pointRadius: 0, borderWidth: 1.5}}
      ]
    }},
    options: {{
      responsive: true,
      plugins: {{legend: {{labels: {{color: "#C9D1D9", font: {{family: "Courier New"}}}}}}}},
      scales: {{
        x: {{ticks: {{color: "#8B949E", maxTicksLimit: 10}}, grid: {{color: "#21262D"}}}},
        y: {{ticks: {{color: "#8B949E"}}, grid: {{color: "#21262D"}}}}
      }}
    }}
  }});
</script>
</body>
</html>"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n[REPORT] Saved to: {out_path}")


# ======================== 4. MAIN ========================
if __name__ == "__main__":
    SYMBOL    = "XAUUSD"
    TIMEFRAME = "M30"
    COUNT     = 2600

    df = fetch_data(SYMBOL, TIMEFRAME, COUNT)
    if df.empty:
        print("[ERROR] No data available. Aborting.")
        sys.exit(1)

    # Load 2 phiên bản chiến lược
    for path in [str(PROJECT_ROOT), str(PROJECT_ROOT / "research")]:
        if path not in sys.path:
            sys.path.insert(0, path)

    try:
        from ict_v1_baseline import ICTZonesProStrategyV1
        print("[OK] Loaded ICT v1 Baseline")
    except Exception as e:
        print(f"[ERROR] Cannot load ict_v1_baseline: {e}")
        sys.exit(1)

    try:
        from ict_v2_challenger import ICTZonesProStrategyV2
        print("[OK] Loaded ICT v2 Challenger")
    except Exception as e:
        print(f"[ERROR] Cannot load ict_v2_challenger: {e}")
        sys.exit(1)

    # Chạy simulation tuần tự (2 phiên bản độc lập)
    r1 = run_simulation(ICTZonesProStrategyV1, df.copy(), "ICT v1 — Baseline")
    r2 = run_simulation(ICTZonesProStrategyV2, df.copy(), "ICT v2 — Challenger")

    # In kết quả tóm tắt ra terminal
    print("\n" + "=" * 60)
    print("  BACKTEST RESULTS SUMMARY")
    print("=" * 60)
    keys = ["total", "winrate", "profit_factor", "net_pnl", "max_drawdown", "avg_rr", "avg_score"]
    for k in keys:
        v1 = r1.get(k, "N/A")
        v2 = r2.get(k, "N/A")
        diff = ""
        if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
            delta = v2 - v1
            diff = f"  (Delta: {'+' if delta >= 0 else ''}{delta:.2f})"
        print(f"  {k:<20} V1={str(v1):<12} V2={str(v2)}{diff}")

    # Xuất báo cáo HTML
    out = str(PROJECT_ROOT / "research" / "backtest_report.html")
    render_html(r1, r2, SYMBOL, TIMEFRAME, out)
    print(f"\n[DONE] Open in browser: {out}")
