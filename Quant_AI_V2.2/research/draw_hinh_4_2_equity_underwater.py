# -*- coding: utf-8 -*-
"""
VECTRA QUANT SYSTEM - GENERATE FIGURE 4.2: EQUITY CURVE & UNDERWATER DRAWDOWN
Continuous 99,999 M15 bars (4.27 years: 2022-07-18 to 2026-10-23)
Outputs:
1. docs/thesis/images/hinh_4_2_equity_curve_underwater_drawdown.png (Academic Print 300 DPI)
2. docs/thesis/images/hinh_4_2_equity_curve_underwater_drawdown_dark.png (Dark Mode 300 DPI)
"""

import sys
import time
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

cache_file = PROJECT_ROOT / "research" / "equity_curves_4year_cache.npz"

configs = [
    {
        "id": "STRICT",
        "name": "Nghiêm ngặt (Strict)",
        "color": "#0284c7",
        "vol_mult": 1.25,
        "adx_threshold": 20.0,
        "min_headroom_atr": 1.0,
        "start_hr": 7,
        "end_hr": 17,
    },
    {
        "id": "BALANCED",
        "name": "Cân bằng (Balanced)",
        "color": "#16a34a",
        "vol_mult": 1.15,
        "adx_threshold": 18.0,
        "min_headroom_atr": 0.6,
        "start_hr": 6,
        "end_hr": 20,
    },
    {
        "id": "DYNAMIC",
        "name": "Năng động (Dynamic)",
        "color": "#d97706",
        "vol_mult": 1.10,
        "adx_threshold": 16.0,
        "min_headroom_atr": 0.4,
        "start_hr": 6,
        "end_hr": 21,
    },
]

curves = {}

if cache_file.exists():
    print(f"Loading cached curves from {cache_file}...")
    npz = np.load(cache_file, allow_pickle=True)
    time_plot = pd.to_datetime(npz["timestamps"])
    for cfg in configs:
        cid = cfg["id"]
        eq = npz[f"{cid}_equity"]
        dd = npz[f"{cid}_drawdown"]
        final_eq = float(npz[f"{cid}_final_eq"])
        ret_pct = float(npz[f"{cid}_ret_pct"])
        max_dd = float(npz[f"{cid}_max_dd"])
        trades = int(npz[f"{cid}_trades"])
        curves[cid] = {
            "cfg": cfg,
            "equity": eq,
            "drawdown": dd,
            "final_equity": final_eq,
            "total_return_pct": ret_pct,
            "max_drawdown_pct": max_dd,
            "total_trades": trades,
        }
    print("Cache loaded successfully in < 0.1s!")
else:
    from backend.infrastructure.brokers.mt5_safe import mt5
    from backend.backtest.backtest_ict_pro import EventDrivenBacktester
    from backend.core.strategies.wyckoff_vectorized import WyckoffMomentumStrategy

    print("=" * 80)
    print("   GENERATING FIGURE 4.2: 4-YEAR CONTINUOUS EQUITY & UNDERWATER DRAWDOWN")
    print("=" * 80)

    if not mt5.initialize():
        print("[!] MT5 Init Failed")
        sys.exit(1)

    symbol = "XAUUSD"
    bars_count = 99999

    print(f"Loading {bars_count:,} M15 bars from MT5...")
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, bars_count)
    mt5.shutdown()

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    time_index = df["time"]

    print(f"Data Loaded: {len(df):,} bars from {time_index.iloc[0]} to {time_index.iloc[-1]}")

    save_dict = {}

    for cfg in configs:
        print(f"\nRunning backtest for: {cfg['name']}...")
        strat_cfg = {
            "vol_mult": cfg["vol_mult"],
            "adx_threshold": cfg["adx_threshold"],
            "min_headroom_atr": cfg["min_headroom_atr"],
            "session_filter": False,
        }

        class VersionedWyckoff(WyckoffMomentumStrategy):
            def __init__(self, s_hr, e_hr):
                super().__init__(strat_cfg)
                self.s_hr = s_hr
                self.e_hr = e_hr

            def analyze(self, window_df, macro_context=None):
                if "time" in window_df.columns:
                    t = pd.to_datetime(window_df["time"].iloc[-1])
                    if not (self.s_hr <= t.hour <= self.e_hr):
                        res = super().analyze(window_df, macro_context)
                        res.action = "HOLD"
                        res.signal = "HOLD"
                        return res
                return super().analyze(window_df, macro_context)

        strat_inst = VersionedWyckoff(cfg["start_hr"], cfg["end_hr"])
        tester = EventDrivenBacktester(
            strategy=strat_inst,
            initial_balance=100000.0,
            risk_per_trade_pct=1.0,
            commission_per_lot=7.0,
            slippage_pts=20.0,
            max_lot_cap=10.0,
        )

        t0 = time.perf_counter()
        report = tester.run(df, symbol=symbol)
        elapsed = time.perf_counter() - t0
        print(f"Done in {elapsed:.1f}s. Trades: {report.total_trades}, Net: ${report.total_net_profit:,.2f}, MaxDD: {report.max_drawdown_pct:.2f}%")

        eq = np.array(report.equity_curve[1:], dtype=np.float64)  # 99,799 points
        peak = np.maximum.accumulate(eq)
        dd_pct = ((eq - peak) / peak) * 100.0

        curves[cfg["id"]] = {
            "cfg": cfg,
            "equity": eq,
            "drawdown": dd_pct,
            "final_equity": report.final_equity,
            "total_return_pct": report.total_return_pct,
            "max_drawdown_pct": report.max_drawdown_pct,
            "total_trades": report.total_trades,
        }

        cid = cfg["id"]
        save_dict[f"{cid}_equity"] = eq
        save_dict[f"{cid}_drawdown"] = dd_pct
        save_dict[f"{cid}_final_eq"] = report.final_equity
        save_dict[f"{cid}_ret_pct"] = report.total_return_pct
        save_dict[f"{cid}_max_dd"] = report.max_drawdown_pct
        save_dict[f"{cid}_trades"] = report.total_trades

    # Match time array length with equity series
    n_pts = len(eq)
    time_plot = time_index.iloc[-n_pts:].reset_index(drop=True)
    save_dict["timestamps"] = time_plot.astype(str).to_numpy()

    np.savez_compressed(cache_file, **save_dict)
    print(f"\n[V] Successfully cached backtest equity series to: {cache_file.name}")


# -------------------------------------------------------------
# PLOT FUNCTION FOR BOTH LIGHT AND DARK THEMES
# -------------------------------------------------------------
def make_plot(dark=False):
    theme_bg = "#090d16" if dark else "#ffffff"
    card_bg = "#101524" if dark else "#f8fafc"
    text_color = "#f1f5f9" if dark else "#0f172a"
    subtext_color = "#94a3b8" if dark else "#475569"
    border_color = "#1e293b" if dark else "#cbd5e1"

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11.5, 7.5), dpi=300, sharex=True, gridspec_kw={"height_ratios": [2.2, 1.2]})
    fig.patch.set_facecolor(theme_bg)

    for ax in (ax1, ax2):
        ax.set_facecolor(card_bg)
        for spine in ax.spines.values():
            spine.set_color(border_color)
            spine.set_linewidth(1.0)
        ax.tick_params(colors=subtext_color, labelsize=9)
        ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.6, color="#cbd5e1" if not dark else "#334155")

    # PANEL 1: EQUITY CURVE
    ax1.set_title("HÌNH 4.2: ĐƯỜNG CONG VỐN (EQUITY CURVE) VÀ ĐƯỜNG CHÌM SỤT GIẢM (UNDERWATER DRAWDOWN)\n"
                  "Chiến lược Tất định Vi cấu trúc qua 99.999 nến M15 XAUUSD (2022 - 2026, Vốn: $100,000 USD)",
                  fontsize=11.5, fontweight="bold", color=text_color, pad=12)

    ax1.axhline(100000.0, color=subtext_color, linestyle=":", linewidth=1.1, alpha=0.8, label="Vốn gốc ban đầu ($100,000 USD)")

    for cfg_id in ["STRICT", "BALANCED", "DYNAMIC"]:
        cdata = curves[cfg_id]
        cfg = cdata["cfg"]
        final_eq = cdata["final_equity"]
        ret_pct = cdata["total_return_pct"]
        max_dd = cdata["max_drawdown_pct"]
        lbl = f"{cfg['name']}: Cuối kỳ ${final_eq:,.0f} (+{ret_pct:.1f}%, Max DD: {max_dd:.1f}%)"
        ax1.plot(time_plot, cdata["equity"], label=lbl, color=cfg["color"], linewidth=1.8, alpha=0.95)

    ax1.set_ylabel("Giá trị Vốn (USD)", fontsize=10, fontweight="bold", color=text_color)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${x:,.0f}"))
    ax1.legend(loc="upper left", fontsize=9, framealpha=0.92, facecolor=card_bg, edgecolor=border_color, labelcolor=text_color)

    # Event annotations
    events = [
        ("2023-03-10", 87000, "Khủng hoảng SVB &\nFed neo lãi suất 5.5%\n(Chop/Sụt giảm sâu)"),
        ("2024-03-01", 102000, "Vàng phá vỡ đỉnh cũ\n$2,075 USD/oz"),
        ("2025-06-01", 135000, "Fed hạ lãi suất &\nSiêu sóng tăng ATH"),
    ]
    for date_str, y_pos, text in events:
        dt = pd.to_datetime(date_str)
        if dt >= time_plot.iloc[0] and dt <= time_plot.iloc[-1]:
            ax1.axvline(dt, color="#ef4444" if "Fed" in text else "#3b82f6", linestyle="--", linewidth=0.9, alpha=0.7)
            ax1.annotate(text, xy=(dt, y_pos), xytext=(10, 10), textcoords="offset points",
                         fontsize=8, fontweight="bold", color=text_color,
                         bbox=dict(boxstyle="square,pad=0.3", fc=theme_bg, ec=border_color, lw=0.8, alpha=0.85),
                         arrowprops=dict(arrowstyle="->", color="#ef4444" if "Fed" in text else "#3b82f6", lw=0.8))

    # PANEL 2: UNDERWATER DRAWDOWN
    ax2.set_ylabel("Mức sụt giảm (% DD)", fontsize=10, fontweight="bold", color=text_color)
    ax2.set_xlabel("Thời gian giao dịch (Năm 2022 - 2026)", fontsize=10, fontweight="bold", color=text_color)
    ax2.axhline(0, color=border_color, linewidth=1.0)
    ax2.axhline(-20.0, color="#dc2626", linestyle=":", linewidth=1.2, label="Ngưỡng cảnh báo rủi ro Quỹ (-20%)")

    # Shaded red danger zone
    ax2.axhspan(-60.0, -20.0, color="#fca5a5" if not dark else "#7f1d1d", alpha=0.15)

    for cfg_id in ["STRICT", "BALANCED", "DYNAMIC"]:
        cdata = curves[cfg_id]
        cfg = cdata["cfg"]
        max_dd = cdata["max_drawdown_pct"]
        ax2.plot(time_plot, cdata["drawdown"], label=f"{cfg['name']} (Max -{max_dd:.1f}%)", color=cfg["color"], linewidth=1.4, alpha=0.9)

    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"{x:.0f}%"))
    ax2.set_ylim(-55, 3)
    ax2.legend(loc="lower left", fontsize=8.5, framealpha=0.92, facecolor=card_bg, edgecolor=border_color, labelcolor=text_color)

    # Format x-axis dates
    ax2.xaxis.set_major_locator(mdates.YearLocator())
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax2.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=[4, 7, 10]))

    plt.tight_layout()
    out_name = "hinh_4_2_equity_curve_underwater_drawdown_dark.png" if dark else "hinh_4_2_equity_curve_underwater_drawdown.png"
    out_path = PROJECT_ROOT / "docs" / "thesis" / "images" / out_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out_path), dpi=300, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    print(f"[V] Exported 300 DPI chart: {out_path}")
    return out_path

p_light = make_plot(dark=False)
p_dark = make_plot(dark=True)
print("\nAll publication charts successfully generated!")
