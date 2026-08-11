import sys
import os
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Any

# Ensure project root (QUANT_AI_WYCKOFF) is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from app.ui_utils import CUSTOM_CSS, MOCK_LOGS, MACRO_ROWS_MOCK, colorize_logs, compute_stats
from app.ui_charts import render_candlestick_chart

# ─── Đường dẫn file dữ liệu ───────────────────────────────────────────────────
CONFIG_PATH: str = str(PROJECT_ROOT / "config" / "config.json")
LOGS_PATH:   str = str(PROJECT_ROOT / "data" / "trade_logs.csv")
MACRO_CACHE_PATH: str = str(PROJECT_ROOT / "data" / "macro_cache.json")

# ─── Schema mặc định ────────────────────────────────────────────────────────
DEFAULT_CONFIG: dict[str, Any] = {
    "system":   {"bot_active": False, "api_key": ""},
    "risk":     {"risk_percent": 1.0, "atr_multiplier": 1.5},
    "strategy": {"timeframe": "H4", "llm_model": "gpt-4o"},
}

DEFAULT_COLUMNS: list[str] = [
    "ticket", "timestamp", "symbol", "action", "lot", "price", "sl", "tp", "profit", "strategy", "status", "notes"
]

def initialize_files() -> None:
    # Đảm bảo thư mục tồn tại
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(LOGS_PATH), exist_ok=True)
    
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
    if not os.path.exists(LOGS_PATH):
        pd.DataFrame(columns=DEFAULT_COLUMNS).to_csv(LOGS_PATH, index=False)

def load_config() -> dict[str, Any]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Merge defaults for missing keys (compatibility with older config schema)
    for k, v in DEFAULT_CONFIG.items():
        if k not in data or not isinstance(data[k], dict):
            data[k] = v
        else:
            for sub_k, sub_v in v.items():
                if sub_k not in data[k]:
                    data[k][sub_k] = sub_v
    return data

def save_config(cfg: dict[str, Any]) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4)

def load_logs() -> pd.DataFrame:
    try:
        return pd.read_csv(LOGS_PATH)
    except Exception:
        return pd.DataFrame(columns=DEFAULT_COLUMNS)

# ─── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="XAU/USD QUANT TERMINAL",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
initialize_files()
config: dict[str, Any] = load_config()
bot_active: bool = config["system"].get("bot_active", False)

# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
# 1. Ép CSS ẩn thanh cuộn Sidebar
st.sidebar.markdown("""
    <style>
    [data-testid="stSidebar"] {
        overflow-x: hidden !important;
    }
    [data-testid="stSidebar"] ::-webkit-scrollbar {
        width: 0px;
        background: transparent;
        display: none;
    }
    </style>
""", unsafe_allow_html=True)

# 2. Header tinh gọn, không hardcode XAU/USD, không màu mè
st.sidebar.markdown("## QUANT TERMINAL")
st.sidebar.markdown("<div style='box-sizing: border-box; width: 100%; color:#9CA3AF; font-size:12px; margin-bottom:15px; font-family:monospace;'>v1.0 — INSTITUTIONAL</div>", unsafe_allow_html=True)
st.sidebar.markdown("---")

# 3. System Status
st.sidebar.caption("SYSTEM STATUS")
is_active = config.get("system", {}).get("bot_active", False)

if is_active:
    st.sidebar.markdown('<div style="box-sizing: border-box; width: 100%; color:#10B981; border: 1px solid #10B981; padding: 4px; border-radius: 4px; text-align: center; font-weight: bold; font-family: monospace; margin-bottom: 10px; font-size: 13px;">[ ACTIVE ]</div>', unsafe_allow_html=True)
else:
    st.sidebar.markdown('<div style="box-sizing: border-box; width: 100%; color:#F59E0B; border: 1px solid #F59E0B; padding: 4px; border-radius: 4px; text-align: center; font-weight: bold; font-family: monospace; margin-bottom: 10px; font-size: 13px;">[ PAUSED ]</div>', unsafe_allow_html=True)

btn_label = "HALT SYSTEM" if is_active else "INITIALIZE SYSTEM"
if st.sidebar.button(btn_label, use_container_width=True):
    config["system"]["bot_active"] = not is_active
    save_config(config)
    st.rerun()
    
st.sidebar.caption("MODE: STATELESS SCHEDULER")
st.sidebar.markdown("---")

# 4. Session Info
st.sidebar.caption("SESSION INFO")

c1, c2 = st.sidebar.columns([1, 1])
with c1:
    st.markdown("<div style='box-sizing: border-box; width: 100%; color:#9CA3AF; font-size:11px; font-family:monospace; line-height:2;'>UTC TIME<br>DATE<br>TIMEFRAME<br>MODEL<br>RISK<br>LAST SYNC</div>", unsafe_allow_html=True)
with c2:
    risk_pct = config.get("risk", {}).get("risk_percent", 1.0)
    atr_mult = config.get("risk", {}).get("atr_multiplier", 1.5)
    tf = config.get("strategy", {}).get("timeframe", "H4")
    model = config.get("strategy", {}).get("llm_model", "gpt-4o")
    
    st.markdown(f"<div style='box-sizing: border-box; width: 100%; color:#F9FAFB; font-size:11px; font-family:monospace; text-align:right; line-height:2;'>{datetime.utcnow().strftime('%H:%M:%S')}<br>{datetime.utcnow().strftime('%Y-%m-%d')}<br>{tf}<br>{model}<br>{risk_pct}% | {atr_mult}x<br>{datetime.utcnow().strftime('%H:%M:%S')}</div>", unsafe_allow_html=True)



# ─── HEADER BAR ───────────────────────────────────────────────────────────────
col1, col2 = st.columns([3, 1])
with col1:
    st.markdown("### XAU/USD QUANT TERMINAL")
with col2:
    st.markdown('''
        <div style="text-align:right; margin-top: 10px;">
            <div id="live-price" style="font-size:24px; font-weight:700; color:#F9FAFB; font-family:monospace;">2,381.50</div>
            <div style="font-size:12px; color:#10B981; font-weight:600;">+7.30 (+0.31%) &nbsp;&bull;&nbsp; MOCK PRICE</div>
        </div>
    ''', unsafe_allow_html=True)
st.markdown("<hr style='margin-top:5px; margin-bottom: 10px; border-color:#374151;'>", unsafe_allow_html=True)

# ─── TABS ─────────────────────────────────────────────────────────────────────
tab_cfg, tab_radar, tab_stats, tab_logs = st.tabs([
    "  CONFIGURATION  ",
    "  LIVE RADAR  ",
    "  QUANT STATS  ",
    "  SYSTEM LOGS  ",
])

# ─── TAB 1: CONFIGURATION ─────────────────────────────────────────────────────
with tab_cfg:

    with st.form("config_form"):
        col_risk, col_strategy = st.columns(2, gap="large")
        with col_risk:
            st.markdown('<div style="font-size:9px;letter-spacing:.2em;color:#10B981;margin-bottom:14px;">RISK MANAGEMENT</div>', unsafe_allow_html=True)
            risk_pct = st.number_input("RISK PER TRADE (%)", min_value=0.1, max_value=10.0, step=0.1, value=float(config["risk"]["risk_percent"]), format="%.2f")
            atr_mult = st.number_input("ATR STOP-LOSS MULTIPLIER", min_value=0.5, max_value=10.0, step=0.1, value=float(config["risk"]["atr_multiplier"]), format="%.2f")
        with col_strategy:
            st.markdown('<div style="font-size:9px;letter-spacing:.2em;color:#3B82F6;margin-bottom:14px;">STRATEGY PARAMETERS</div>', unsafe_allow_html=True)
            tf_opts = ["M15", "M30", "H1", "H4", "D1", "W1"]
            tf_idx = tf_opts.index(config["strategy"]["timeframe"]) if config["strategy"]["timeframe"] in tf_opts else 3
            timeframe = st.selectbox("WYCKOFF ANALYSIS TIMEFRAME", tf_opts, index=tf_idx)
            model_opts = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "claude-opus-4-8", "claude-sonnet-4-6", "gemini-1.5-pro"]
            m_idx = model_opts.index(config["strategy"]["llm_model"]) if config["strategy"]["llm_model"] in model_opts else 0
            llm_model = st.selectbox("LLM INFERENCE MODEL", model_opts, index=m_idx)
        
        st.markdown('<div style="font-size:9px;letter-spacing:.2em;color:#F59E0B;margin-top:20px;margin-bottom:14px;">BROKER API CREDENTIAL</div>', unsafe_allow_html=True)
        api_key = st.text_input("API KEY (MASKED)", value=config["system"]["api_key"], type="password", placeholder="Enter broker or data provider API key...")
        st.markdown('<div style="font-size:8px;color:#4B5563;margin-top:-8px;letter-spacing:.08em;">STORED LOCALLY IN config/config.json — NEVER TRANSMITTED BY THIS UI</div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.form_submit_button("SAVE CONFIGURATION"):
            config["system"]["api_key"] = api_key
            config["risk"]["risk_percent"] = risk_pct
            config["risk"]["atr_multiplier"] = atr_mult
            config["strategy"]["timeframe"] = timeframe
            config["strategy"]["llm_model"] = llm_model
            save_config(config)
            st.success(f"CONFIG SAVED — {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")

# ─── TAB 2: LIVE RADAR ────────────────────────────────────────────────────────
with tab_radar:

    col_macro, col_tech = st.columns([1, 2], gap="large")

    with col_macro:
        st.markdown('<div style="font-size:9px;letter-spacing:.18em;color:#4B5563;margin-bottom:12px;">MACRO BRAIN — LLM CONTEXT OUTPUT</div>', unsafe_allow_html=True)
        rows_html: list[str] = []
        
        # Load from cache if exists
        macro_cache = {}
        if os.path.exists(MACRO_CACHE_PATH):
            with open(MACRO_CACHE_PATH, "r", encoding="utf-8") as f:
                macro_cache = json.load(f)
                
        # If macro cache is empty, fallback to mock, otherwise display cache nicely
        if macro_cache and "bias" in macro_cache:
            bias = str(macro_cache.get("bias", "NEUTRAL")).upper()
            color = "#10B981" if bias == "BULLISH" else "#EF4444" if bias == "BEARISH" else "#F59E0B"
            rows_html.append(f'<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #1C2133;"><span style="color:#9CA3AF;font-size:10px;">BIAS</span><span style="color:{color};font-size:11px;font-weight:600;">{bias}</span></div>')
            rows_html.append(f'<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #1C2133;"><span style="color:#9CA3AF;font-size:10px;">CONFIDENCE</span><span style="color:#F9FAFB;font-size:11px;font-weight:600;">{macro_cache.get("confidence", "N/A")}</span></div>')
            summary = macro_cache.get("summary", "")
            if summary:
                rows_html.append(f'<div style="margin-top: 10px; color:#9CA3AF; font-size:10px;">{summary}</div>')
        else:
            for label, value, color in MACRO_ROWS_MOCK:
                rows_html.append(f'<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #1C2133;"><span style="color:#9CA3AF;font-size:10px;">{label}</span><span style="color:{color};font-size:11px;font-weight:600;">{value}</span></div>')

        st.markdown(
            f'<div style="background:#1C2133;border:1px solid #374151;border-left:3px solid #00BCD4;border-radius:4px;padding:16px 18px;line-height:2.1;">'
            + "".join(rows_html)
            + "</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div style="background:#1C2133;border:1px solid #374151;border-left:3px solid #10B981;border-radius:4px;padding:16px 18px;margin-top:14px;">'
            '<div style="font-size:9px;letter-spacing:.18em;color:#4B5563;margin-bottom:10px;">ACTIVE SIGNAL</div>'
            '<div style="color:#10B981;font-size:16px;font-weight:700;letter-spacing:.08em;">BUY XAUUSD</div>'
            '<div style="color:#9CA3AF;font-size:10px;margin-top:8px;line-height:2;">'
            "ENTRY &nbsp; 2381.50<br>SL &nbsp;&nbsp;&nbsp;&nbsp; 2371.20<br>TP &nbsp;&nbsp;&nbsp;&nbsp; 2405.00"
            "</div>"
            '<div style="color:#4B5563;font-size:9px;margin-top:8px;letter-spacing:.08em;">WYCKOFF: LPS RETEST — ACCUMULATION</div></div>',
            unsafe_allow_html=True,
        )

    with col_tech:
        st.markdown(f'<div style="font-size:9px;letter-spacing:.18em;color:#4B5563;margin-bottom:12px;">TECHNICAL BRAIN — WYCKOFF SCHEMATIC (XAUUSD {config["strategy"]["timeframe"]})</div>', unsafe_allow_html=True)
        # Replacing placeholder with the actual Plotly Chart from app/ui_charts.py
        fig = render_candlestick_chart()
        st.plotly_chart(fig, use_container_width=True)

# ─── TAB 3: QUANT STATS ───────────────────────────────────────────────────────
with tab_stats:

    logs_df: pd.DataFrame = load_logs()
    stats: dict[str, Any] = compute_stats(logs_df)
    mc1, mc2, mc3, mc4 = st.columns(4, gap="small")
    pnl_val: float = stats["net_pnl"]
    pnl_delta: str = f"+${pnl_val:.2f}" if pnl_val >= 0 else f"-${abs(pnl_val):.2f}"
    pnl_color: str = "normal" if pnl_val >= 0 else "inverse"

    def render_card(title, value, badge_html=""):
        return f'''
        <div style="background-color: #212636; border: 1px solid #374151; border-radius: 4px; padding: 16px; height: 130px; display: flex; flex-direction: column; justify-content: space-between; margin-bottom: 10px;">
            <div style="color: #9CA3AF; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">{title}</div>
            <div style="color: #F9FAFB; font-size: 28px; font-weight: 700; font-family: monospace; line-height: 1.2;">{value}</div>
            <div style="height: 24px; display: flex; align-items: center;">{badge_html}</div>
        </div>
        '''

    badge_total = '<span style="background: #374151; color: #9CA3AF; padding: 2px 8px; border-radius: 12px; font-size: 11px;">ALL TIME</span>'
    
    pnl_bg = "#064E3B" if pnl_val >= 0 else "#451A03"
    pnl_text = "#10B981" if pnl_val >= 0 else "#EF4444"
    badge_pnl = f'<span style="background: {pnl_bg}; color: {pnl_text}; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{pnl_delta}</span>'

    with mc1: st.markdown(render_card("TOTAL TRADES", str(stats["total"]), badge_total), unsafe_allow_html=True)
    with mc2: st.markdown(render_card("WIN RATE", str(stats["winrate"])), unsafe_allow_html=True)
    with mc3: st.markdown(render_card("NET PNL (USD)", f"${pnl_val:.2f}", badge_pnl), unsafe_allow_html=True)
    with mc4: st.markdown(render_card("AVG RISK:REWARD", str(stats["avg_rr"])), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div style="font-size:9px;letter-spacing:.15em;color:#4B5563;margin-bottom:10px;">EXECUTION LOG</div>', unsafe_allow_html=True)

    if logs_df.empty:
        st.markdown('<div style="background:#1C2133;border:1px solid #374151;border-radius:4px;padding:24px;font-size:11px;color:#4B5563;letter-spacing:.1em;">NO TRADE RECORDS FOUND IN data/trade_logs.csv<br>Records will appear here after the execution engine logs its first trade.</div>', unsafe_allow_html=True)
    else:
        st.dataframe(logs_df, use_container_width=True, hide_index=True)

# ─── TAB 4: SYSTEM LOGS ───────────────────────────────────────────────────────
with tab_logs:

    colored_logs: str = colorize_logs(MOCK_LOGS)
    st.markdown(
        f'<div style="background:#0D1117;border:1px solid #374151;border-left:3px solid #3B82F6;border-radius:4px;padding:20px 24px;max-height:480px;overflow-y:auto;overflow-x:auto;white-space:pre;font-family:\'JetBrains Mono\',monospace;font-size:11px;line-height:1.9;">'
        f"<pre style='margin:0;background:transparent;'>{colored_logs}</pre></div>",
        unsafe_allow_html=True,
    )
