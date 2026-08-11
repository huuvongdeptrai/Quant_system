import pandas as pd
from typing import Any

# ─── CSS toàn cục ────────────────────────────────────────────────────────────
CUSTOM_CSS: str = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&display=swap');

/* ── Reset & base ── */
html, body, [class*="css"] {
    font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace !important;
    background-color: #161A25 !important;
    color: #F9FAFB !important;
}

/* ── Streamlit Overrides ── */
#MainMenu {visibility: hidden;}
/* header {visibility: hidden;} */
footer {visibility: hidden;}
[data-testid="stSidebarCollapseButton"] { display: none !important; }

/* ── App background ── */
.stApp, .stMain, section.main {
    background-color: #161A25 !important;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background-color: #212636 !important;
    border-right: 1px solid #374151 !important;
    overflow-x: hidden !important;
}
section[data-testid="stSidebar"] * {
    font-family: 'JetBrains Mono', monospace !important;
}

/* ── Tabs: remove white background, style active/inactive ── */
.stTabs [data-baseweb="tab-list"] {
    background-color: #212636 !important;
    border-bottom: 1px solid #374151 !important;
    gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background-color: transparent !important;
    color: #9CA3AF !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 11px !important;
    letter-spacing: 0.15em !important;
    border: none !important;
    border-right: 1px solid #374151 !important;
    border-bottom: 2px solid transparent !important;
    padding: 10px 22px !important;
    transition: color 0.15s !important;
}
.stTabs [data-baseweb="tab"]:hover {
    color: #F9FAFB !important;
    background-color: transparent !important;
}
.stTabs [aria-selected="true"] {
    color: #F9FAFB !important;
    font-weight: 600 !important;
    border-bottom: 2px solid #10B981 !important;
    background-color: #161A25 !important;
}
.stTabs [data-baseweb="tab-panel"] {
    background-color: #161A25 !important;
    padding-top: 24px !important;
}

/* ── Metric cards ── */
[data-testid="stMetric"] {
    background-color: #1C2133 !important;
    border: 1px solid #374151 !important;
    border-radius: 4px !important;
    padding: 16px 20px !important;
}
[data-testid="stMetricLabel"] {
    font-size: 9px !important;
    letter-spacing: 0.18em !important;
    color: #4B5563 !important;
    text-transform: uppercase !important;
}
[data-testid="stMetricValue"] {
    font-size: 24px !important;
    font-weight: 600 !important;
    color: #F9FAFB !important;
    letter-spacing: -0.02em !important;
}
[data-testid="stMetricDelta"] { font-size: 10px !important; }

/* ── Form inputs ── */
.stTextInput input,
.stNumberInput input,
.stSelectbox select,
.stTextInput textarea {
    background-color: #212636 !important;
    border: 1px solid #374151 !important;
    border-radius: 4px !important;
    color: #F9FAFB !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 12px !important;
    font-weight: 600 !important;
}
.stTextInput input:focus,
.stNumberInput input:focus {
    border-color: #10B981 !important;
    box-shadow: 0 0 0 1px #10B981 !important;
}

/* ── Labels ── */
label, .stSelectbox label, .stTextInput label, .stNumberInput label {
    font-size: 9px !important;
    letter-spacing: 0.15em !important;
    color: #9CA3AF !important;
    font-family: 'JetBrains Mono', monospace !important;
}

/* ── Buttons (Removed to use native Streamlit sizing) ── */

/* ── Success / warning messages ── */
.stSuccess {
    background-color: #064E3B !important;
    border: 1px solid #10B981 !important;
    border-radius: 4px !important;
    color: #10B981 !important;
}
.stWarning {
    background-color: #451A03 !important;
    border: 1px solid #F59E0B !important;
    border-radius: 4px !important;
    color: #F59E0B !important;
}

/* ── Dataframe ── */
.stDataFrame, iframe[title="st.dataframe"] {
    border: 1px solid #374151 !important;
    border-radius: 4px !important;
}

/* ── Dividers ── */
hr { border-color: #374151 !important; }

/* ── Scrollbars ── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: #161A25; }
::-webkit-scrollbar-thumb { background: #374151; border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: #4B5563; }
</style>
"""

# ─── Mock Data ────────────────────────────────────────────────────────────────
MOCK_LOGS: str = """\
[2025-07-24 09:38:00] [BOOT]     XAU/USD QUANT TERMINAL — PROCESS INITIALIZED
[2025-07-24 09:38:01] [BOOT]     Loading config.json — risk: 1.0% | ATR: 1.5x | TF: H4
[2025-07-24 09:38:02] [FETCH]    MT5 bridge connection — endpoint: localhost:5000 — OK
[2025-07-24 09:38:03] [FETCH]    OHLCV retrieved — symbol: XAUUSD | bars: 500 | TF: H4
[2025-07-24 09:38:03] [FETCH]    Spot price: 2381.50 | Spread: 0.35 | Session: LONDON
[2025-07-24 09:38:04] [WYCKOFF]  Phase detector running — window: 120 bars
[2025-07-24 09:38:04] [WYCKOFF]  Detected: ACCUMULATION — Spring confirmed at 2361.20
[2025-07-24 09:38:04] [WYCKOFF]  Volume climax: YES | Effort vs Result: BULLISH
[2025-07-24 09:38:05] [LLM]      Dispatching macro context to gpt-4o — tokens: 1,204
[2025-07-24 09:38:06] [LLM]      Response received — bias: BULLISH | confidence: 0.87
[2025-07-24 09:38:06] [LLM]      DXY: BEARISH | Real yields: DECLINING | Risk: ON
[2025-07-24 09:38:07] [EXEC]     ORDER PLACED — BUY 0.10 XAUUSD @ 2381.50
[2025-07-24 09:38:07] [EXEC]     SL: 2371.20 | TP: 2405.00 | Ticket: #100042
[2025-07-24 09:38:08] [FETCH]    Trade #100042 confirmed by broker — latency: 18ms
[2025-07-24 09:38:08] [LLM]      Position monitor active — unrealized PnL: +$47.30
[2025-07-24 09:38:09] [BOOT]     Cycle complete — sleeping 240s
[2025-07-24 09:42:09] [BOOT]     Scheduler wake — resuming execution cycle
[2025-07-24 09:42:10] [FETCH]    Spot price: 2389.20 | Δ: +7.70 pts
[2025-07-24 09:42:10] [WYCKOFF]  Phase unchanged: ACCUMULATION | LPS holding
[2025-07-24 09:42:11] [LLM]      No new entry signal — conditions not met
[2025-07-24 09:42:11] [BOOT]     Cycle complete — sleeping 240s\
"""

MACRO_ROWS_MOCK: list[tuple[str, str, str]] = [
    ("MACRO STATE",    "BULLISH",       "#10B981"),
    ("CONFIDENCE",     "0.87",          "#F9FAFB"),
    ("DXY BIAS",       "BEARISH",       "#EF4444"),
    ("REAL YIELDS",    "DECLINING",     "#F9FAFB"),
    ("RISK SENTIMENT", "RISK-ON",       "#10B981"),
    ("FED POSTURE",    "DOVISH PIVOT",  "#F59E0B"),
    ("GEOPOLITICAL",   "ELEVATED",      "#F59E0B"),
    ("COT NET LONG",   "+187,432",      "#F9FAFB"),
    ("MACRO SIGNAL",   "LONG BIAS",     "#10B981"),
]

# ─── Helper Functions ─────────────────────────────────────────────────────────
def compute_stats(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {"total": 0, "winrate": "--", "net_pnl": 0.0, "avg_rr": "--"}

    total:   int   = len(df)
    pnl_col: pd.Series = pd.to_numeric(df.get("PnL", df.get("profit", 0)), errors="coerce").fillna(0)
    wins:    int   = int((pnl_col > 0).sum())
    net_pnl: float = float(pnl_col.sum())
    winrate: str   = f"{wins / total * 100:.1f}%" if total > 0 else "--"

    try:
        price  = pd.to_numeric(df.get("Price", df.get("price")), errors="coerce")
        sl     = pd.to_numeric(df.get("SL", df.get("sl")),    errors="coerce")
        tp     = pd.to_numeric(df.get("TP", df.get("tp")),    errors="coerce")
        risk   = (price - sl).abs()
        reward = (tp    - price).abs()
        rr     = reward / risk.replace(0, float("nan"))
        avg_rr: str = f"{rr.mean():.2f}R" if not rr.isna().all() else "--"
    except Exception:
        avg_rr = "--"

    return {"total": total, "winrate": winrate, "net_pnl": net_pnl, "avg_rr": avg_rr}

TAG_COLORS: dict[str, str] = {
    "[BOOT]":    "#F9FAFB",
    "[FETCH]":   "#3B82F6",
    "[WYCKOFF]": "#A78BFA",
    "[LLM]":     "#9CA3AF",
    "[EXEC]":    "#10B981",
    "[SIGNAL]":  "#F59E0B",
    "[RISK]":    "#F59E0B",
    "[MONITOR]": "#9CA3AF",
    "[SLEEP]":   "#4B5563",
    "[WAKE]":    "#F9FAFB",
}

def colorize_logs(raw: str) -> str:
    """Bọc mỗi dòng log trong HTML span với màu tương ứng theo tag."""
    lines: list[str] = raw.split("\n")
    html_lines: list[str] = []

    for line in lines:
        color: str = "#9CA3AF"
        for tag, tag_color in TAG_COLORS.items():
            if tag in line:
                color = tag_color
                break
        safe_line: str = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html_lines.append(
            f'<span style="color:{color};font-weight:{"600" if color != "#9CA3AF" else "400"};">'
            f'{safe_line}</span>'
        )

    return "\n".join(html_lines)
