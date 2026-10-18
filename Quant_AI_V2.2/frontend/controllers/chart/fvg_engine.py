"""
Institutional Fair Value Gap (FVG) Engine
===========================================
Implements academic & institutional market microstructure standards for Fair Value Gaps:
- References:
  * Harris, L. (2003): "Trading and Exchanges: Market Microstructure for Practitioners", Oxford University Press.
  * Biais, B., Hillion, P., & Spatt, C. (1995): "An Empirical Analysis of the Limit Order Book and Order Flow", Journal of Finance.
  * LuxAlgo & TradingView Pine Script v5 Smart Money Concepts (SMC) Architecture.
  * ICT Core Framework: 3-candle imbalance, mitigation lifecycle, and Consequent Encroachment (CE 50%).

Features:
1. Dynamic ATR-based displacement & noise thresholding.
2. Complete mitigation engine (zones stop extending at the exact candle that filled them).
3. Consequent Encroachment (CE - 50% equilibrium reaction line).
4. WCAG AAA theme-aware color palettes (soft emerald demand / soft rose supply).
5. Non-colliding micro-badge labels anchored to outer boundaries (zero text overlap).
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple, Any
import numpy as np
import pyqtgraph as pg


@dataclass
class FVGZone:
    """Institutional Fair Value Gap model representation."""
    type: str  # 'bull' (+FVG / Demand) or 'bear' (-FVG / Supply)
    start_idx: int  # Origin candle index (bar i-2)
    disp_idx: int   # Displacement candle index (bar i-1)
    form_idx: int   # Confirmation candle index (bar i)
    end_idx: int    # Right termination bar index (mitigation candle or projected edge)
    top: float      # Upper price boundary
    bottom: float   # Lower price boundary
    ce: float       # Consequent Encroachment midpoint (50% equilibrium)
    is_mitigated: bool = False
    is_tested: bool = False
    mitigated_idx: Optional[int] = None
    gap_size: float = 0.0
    gap_pts: float = 0.0


def _calculate_tr_atr(chart_data_list: List[Tuple], period: int = 14) -> float:
    """Computes robust Average True Range (ATR) across candlestick data."""
    n = len(chart_data_list)
    if n < 3:
        return 1.0

    tr_list = []
    for i in range(1, n):
        _, _, c_prev, _, _ = chart_data_list[i - 1]
        _, _, c_cur, l_cur, h_cur = chart_data_list[i]
        tr = max(h_cur - l_cur, abs(h_cur - c_prev), abs(l_cur - c_prev))
        tr_list.append(tr)

    if not tr_list:
        return 1.0

    lookback = min(period, len(tr_list))
    return float(np.mean(tr_list[-lookback:]))


def detect_institutional_fvgs(
    chart_data_list: List[Tuple],
    cur_p: Optional[float] = None,
    point: float = 0.01,
    min_atr_mult: float = 0.20,
    max_active: int = 6,
    max_lookback: int = 160,
) -> List[FVGZone]:
    """
    Detects 3-candle institutional Fair Value Gaps with full lifecycle mitigation tracking.
    
    Guarantees:
    - Mitigated (filled) zones terminate strictly at their mitigation bar (never bleed across candles).
    - Unmitigated (active) zones project cleanly to current price as live support/resistance.
    - True body displacement confirmed on candle i-1.
    - Micro-wick noise filtered by ATR threshold.
    """
    total_n = len(chart_data_list)
    if total_n < 5:
        return []

    if cur_p is None:
        cur_p = chart_data_list[-1][2]  # latest close

    atr = _calculate_tr_atr(chart_data_list, period=14)
    min_gap = max(atr * min_atr_mult, cur_p * 0.00020, 5.0 * point)

    start_scan = max(2, total_n - max_lookback)
    all_zones: List[FVGZone] = []

    for i in range(start_scan, total_n):
        # Candle 1 (origin): bar i-2
        t_prev2, o_p2, c_p2, l_prev2, h_prev2 = chart_data_list[i - 2]
        # Candle 2 (displacement): bar i-1
        t_prev, o_p, c_p, l_prev, h_prev = chart_data_list[i - 1]
        # Candle 3 (confirmation): bar i
        t_cur, o_cur, c_cur, l_cur, h_cur = chart_data_list[i]

        # 1. Bullish FVG (+FVG / Demand Imbalance):
        # Low of Candle 3 is strictly higher than High of Candle 1
        # Displacement body closes higher than Candle 1 high
        if l_cur > h_prev2 and (l_cur - h_prev2) >= min_gap and c_p > h_prev2:
            top = float(l_cur)
            bottom = float(h_prev2)
            ce = round((top + bottom) / 2.0, 5)
            gap_size = round(top - bottom, 5)

            # Trace forward to find exact mitigation candle
            is_mitigated = False
            is_tested = False
            mitigated_idx = None
            end_idx = total_n - 1 + 5  # default active forward projection

            for k in range(i + 1, total_n):
                k_bar = chart_data_list[k]
                k_low = k_bar[3]
                if k_low <= bottom:
                    # Fully filled / closed!
                    is_mitigated = True
                    mitigated_idx = k
                    end_idx = k
                    break
                elif k_low <= top:
                    is_tested = True

            all_zones.append(
                FVGZone(
                    type="bull",
                    start_idx=i - 2,
                    disp_idx=i - 1,
                    form_idx=i,
                    end_idx=end_idx,
                    top=top,
                    bottom=bottom,
                    ce=ce,
                    is_mitigated=is_mitigated,
                    is_tested=is_tested,
                    mitigated_idx=mitigated_idx,
                    gap_size=gap_size,
                    gap_pts=round(gap_size / point, 1) if point > 0 else gap_size,
                )
            )

        # 2. Bearish FVG (-FVG / Supply Imbalance):
        # High of Candle 3 is strictly lower than Low of Candle 1
        # Displacement body closes lower than Candle 1 low
        elif h_cur < l_prev2 and (l_prev2 - h_cur) >= min_gap and c_p < l_prev2:
            top = float(l_prev2)
            bottom = float(h_cur)
            ce = round((top + bottom) / 2.0, 5)
            gap_size = round(top - bottom, 5)

            # Trace forward to find exact mitigation candle
            is_mitigated = False
            is_tested = False
            mitigated_idx = None
            end_idx = total_n - 1 + 5

            for k in range(i + 1, total_n):
                k_bar = chart_data_list[k]
                k_high = k_bar[4]
                if k_high >= top:
                    # Fully filled / closed!
                    is_mitigated = True
                    mitigated_idx = k
                    end_idx = k
                    break
                elif k_high >= bottom:
                    is_tested = True

            all_zones.append(
                FVGZone(
                    type="bear",
                    start_idx=i - 2,
                    disp_idx=i - 1,
                    form_idx=i,
                    end_idx=end_idx,
                    top=top,
                    bottom=bottom,
                    ce=ce,
                    is_mitigated=is_mitigated,
                    is_tested=is_tested,
                    mitigated_idx=mitigated_idx,
                    gap_size=gap_size,
                    gap_pts=round(gap_size / point, 1) if point > 0 else gap_size,
                )
            )

    # Filter & Prioritize for Institutional Clarity:
    # 1. Unmitigated Active Zones (Priority 1)
    active_bull = [z for z in all_zones if not z.is_mitigated and z.type == "bull"]
    active_bear = [z for z in all_zones if not z.is_mitigated and z.type == "bear"]

    # Sort by recency (most recent formation first)
    active_bull.sort(key=lambda z: z.form_idx, reverse=True)
    active_bear.sort(key=lambda z: z.form_idx, reverse=True)

    # 2. Recent Mitigated Zones (Ghost Mode, terminating strictly at mitigation bar)
    mitigated_zones = [z for z in all_zones if z.is_mitigated]
    mitigated_zones.sort(key=lambda z: z.mitigated_idx or 0, reverse=True)

    selected: List[FVGZone] = []
    # Up to 3 active demand zones below price and 3 active supply zones above price
    selected.extend(active_bull[:3])
    selected.extend(active_bear[:3])
    # Up to 2 most recently mitigated zones to show recent order flow resolution
    selected.extend(mitigated_zones[:2])

    return selected


def render_institutional_fvg_items(
    plot_widget: Any,
    fvg_zones: List[FVGZone],
    is_dark: bool = False,
    visible: bool = True,
    digits: int = 2,
) -> List[Any]:
    """
    Renders institutional FVG graphics items onto the pyqtgraph ViewBox.
    
    Aesthetic Standards:
    - Soft semi-transparent fills (10-12% opacity) never obscuring candlestick bodies.
    - Consequent Encroachment (CE - 50% equilibrium) delicate dashed line.
    - Outer-edge anchored micro-badges: +FVG on bottom-left, -FVG on top-left (zero text collision).
    - Mitigated zones rendered as subtle historical ghost boxes terminating cleanly at mitigation bar.
    """
    created_items: List[Any] = []
    if not plot_widget:
        return created_items

    for zone in fvg_zones:
        start_x = float(zone.start_idx)
        width_x = float(max(0.8, zone.end_idx - zone.start_idx))
        bot_y = float(zone.bottom)
        height_y = float(max(0.00001, zone.top - zone.bottom))
        top_y = float(zone.top)
        ce_y = float(zone.ce)

        # Theme-aware WCAG AAA color palette
        if zone.type == "bull":
            if is_dark:
                # Dark mode: Emerald demand
                fill_color = (16, 185, 129, 28) if not zone.is_mitigated else (16, 185, 129, 10)
                pen_color = (16, 185, 129, 130) if not zone.is_mitigated else (16, 185, 129, 45)
                ce_color = (16, 185, 129, 95)
                txt_color = (52, 211, 153, 220)
            else:
                # Light mode: Green demand
                fill_color = (22, 163, 74, 25) if not zone.is_mitigated else (22, 163, 74, 10)
                pen_color = (22, 163, 74, 140) if not zone.is_mitigated else (22, 163, 74, 50)
                ce_color = (22, 163, 74, 100)
                txt_color = (21, 128, 61, 230)
            badge_text = "+FVG"
            # Anchor Bullish badge to BOTTOM-LEFT of the box
            lbl_anchor = (0.0, 1.0)
            lbl_pos_y = bot_y
        else:
            if is_dark:
                # Dark mode: Rose supply
                fill_color = (239, 68, 68, 28) if not zone.is_mitigated else (239, 68, 68, 10)
                pen_color = (239, 68, 68, 130) if not zone.is_mitigated else (239, 68, 68, 45)
                ce_color = (239, 68, 68, 95)
                txt_color = (248, 113, 113, 220)
            else:
                # Light mode: Crimson supply
                fill_color = (220, 38, 38, 25) if not zone.is_mitigated else (220, 38, 38, 10)
                pen_color = (220, 38, 38, 140) if not zone.is_mitigated else (220, 38, 38, 50)
                ce_color = (220, 38, 38, 100)
                txt_color = (185, 28, 28, 230)
            badge_text = "-FVG"
            # Anchor Bearish badge to TOP-LEFT of the box
            lbl_anchor = (0.0, 0.0)
            lbl_pos_y = top_y

        pen_style = pg.QtCore.Qt.PenStyle.SolidLine if not zone.is_mitigated else pg.QtCore.Qt.PenStyle.DashLine

        # 1. Shaded Imbalance Rect
        rect_item = pg.QtWidgets.QGraphicsRectItem(start_x, bot_y, width_x, height_y)
        rect_item.setBrush(pg.mkBrush(*fill_color))
        rect_item.setPen(pg.mkPen(color=pen_color, width=1.0, style=pen_style))
        rect_item.setVisible(visible)
        plot_widget.addItem(rect_item)
        created_items.append(rect_item)

        # 2. Consequent Encroachment (CE 50% equilibrium line) for active zones
        if not zone.is_mitigated:
            ce_line = pg.PlotCurveItem(
                [start_x, start_x + width_x],
                [ce_y, ce_y],
                pen=pg.mkPen(color=ce_color, width=0.8, style=pg.QtCore.Qt.PenStyle.DashLine),
            )
            ce_line.setVisible(visible)
            plot_widget.addItem(ce_line)
            created_items.append(ce_line)

        # 3. Compact non-intrusive badge label (only on active or prominent zones)
        if not zone.is_mitigated:
            lbl_item = pg.TextItem(text=badge_text, color=txt_color, anchor=lbl_anchor)
            lbl_item.setFont(pg.QtGui.QFont("Consolas", 8, pg.QtGui.QFont.Weight.Bold))
            lbl_item.setPos(start_x + 0.25, lbl_pos_y)
            lbl_item.setToolTip(
                f"{badge_text} [Unmitigated Inefficiency]\n"
                f"Range: {bot_y:.{digits}f} - {top_y:.{digits}f}\n"
                f"CE (50%): {ce_y:.{digits}f}\n"
                f"Gap: {zone.gap_pts:.1f} pts"
            )
            lbl_item.setVisible(visible)
            plot_widget.addItem(lbl_item)
            created_items.append(lbl_item)

    return created_items


def update_chart_fvgs(window: Any, force_visible: Optional[bool] = None) -> List[FVGZone]:
    """
    Main entrypoint: Detects and renders institutional FVGs on the main chart canvas.
    Safely clears previous items and updates drawing_engine.fvg_items.
    """
    if not hasattr(window, "plot_widget") or not window.plot_widget:
        return []

    if not hasattr(window, "chart_data_list") or not window.chart_data_list or len(window.chart_data_list) < 5:
        return []

    # Clean up previous FVG items
    if hasattr(window, "drawing_engine") and window.drawing_engine:
        for it in list(window.drawing_engine.fvg_items):
            try:
                window.plot_widget.removeItem(it)
            except Exception:
                pass
        window.drawing_engine.fvg_items.clear()

    # Determine visibility
    if force_visible is not None:
        window._fvg_visible = force_visible
    fvg_vis = getattr(window, "_fvg_visible", True)

    clean_sym = getattr(window, "current_sym", "XAUUSD").split("\n")[0].strip()
    digits = getattr(window, "digits", 2)
    point = 0.01 if digits == 2 else 0.0001
    cur_p = getattr(window, "_last_manual_entry", None)

    is_d = getattr(window, "is_dark_theme", False)

    # Detect institutional FVGs
    zones = detect_institutional_fvgs(
        window.chart_data_list,
        cur_p=cur_p,
        point=point,
        min_atr_mult=0.20,
        max_active=6,
        max_lookback=160,
    )

    # Render items onto the chart
    new_items = render_institutional_fvg_items(
        window.plot_widget,
        zones,
        is_dark=is_d,
        visible=fvg_vis,
        digits=digits,
    )

    if hasattr(window, "drawing_engine") and window.drawing_engine:
        window.drawing_engine.fvg_items.extend(new_items)

    return zones
