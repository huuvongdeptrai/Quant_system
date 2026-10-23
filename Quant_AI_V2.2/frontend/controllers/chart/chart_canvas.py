"""
Interactive Candlestick Chart Viewport, Volume Profile, and Drawing Tools Engine
"""

import os
import time
import json
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import pyqtgraph as pg

from PySide6 import QtCore, QtGui
from PySide6.QtCore import Qt, QTimer, QSize, QPointF, QPoint, QEvent, QObject
from PySide6.QtGui import (
    QColor, QFont, QIcon, QPainter, QPicture, QCursor,
    QKeySequence, QShortcut, QPixmap, QPen, QBrush, QAction
)
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QFrame, QLabel, QHBoxLayout, QVBoxLayout, QPushButton,
    QWidget, QGraphicsRectItem, QMenu, QMessageBox, QTableWidgetItem,
    QCheckBox
)
from loguru import logger

from backend.infrastructure.brokers.mt5_safe import mt5
from backend.infrastructure.brokers.execution_manager import ExecutionManager
from backend.core.event_bus import event_bus
from backend.core.strategies.strategy_loader import discover_strategies

from frontend.controllers.chart.candlestick_items import TimeAxisItem, CandlestickItem
from frontend.controllers.chart.indicator_dialog import (
    IndicatorDialog, _compute_indicators, _refresh_indicators,
    _get_or_create_curve, _get_or_create_hline, _hide_curve
)
from frontend.controllers.chart.ai_panel_controller import (
    AISignals, AIAnalyzerThread, _build_analysis_panel, _force_reanalyze,
    _update_panel_with_result, _run_analysis, _show_error
)
from frontend.controllers.chart.trading_plan_panel import (
    update_order_proposal_html, update_ai_reasoning,
    apply_playbook_cards_theme, setup_trading_plan_cards,
    start_signal_expiry_countdown
)
from frontend.controllers.chart.drawing_engine import ChartDrawingEngine


class CompactRibbonLabel(QLabel):
    """QLabel subclass that allows shrinking below text length to prevent horizontal window expansion."""
    def minimumSizeHint(self):
        return QSize(40, super().minimumSizeHint().height())


def _compute_market_profile_va(rates, lookback: int = 100, num_bins: int = 60, va_pct: float = 0.70, return_tpoc: bool = False):
    """
    Computes Volume Profile Point of Control (vPOC), 70% Value Area (VAH & VAL),
    and Time Point of Control (tPOC) according to J. Peter Steidlmayer's
    authentic Market Profile Theory (CBOT, 1985).
    Optionally returns tPOC (Time Point of Control / highest TPO count).
    """
    if rates is None or len(rates) == 0:
        if return_tpoc:
            return 0.0, 0.0, 0.0, 0.0
        return 0.0, 0.0, 0.0

    subset = rates[-lookback:] if len(rates) >= lookback else rates
    lows = [float(r["low"]) for r in subset]
    highs = [float(r["high"]) for r in subset]
    closes = [float(r["close"]) for r in subset]
    vols = [float(r["tick_volume"]) if "tick_volume" in r.dtype.names else 1.0 for r in subset]

    p_min = min(lows)
    p_max = max(highs)
    if p_max <= p_min:
        mean_p = float(np.mean(closes))
        if return_tpoc:
            return mean_p, mean_p, mean_p, mean_p
        return mean_p, mean_p, mean_p

    bins = np.linspace(p_min, p_max, num_bins + 1)
    bin_centers = 0.5 * (bins[:-1] + bins[1:])
    vol_profile = np.zeros(num_bins)
    tpo_profile = np.zeros(num_bins)

    for l, h, c, v in zip(lows, highs, closes, vols):
        if v <= 0:
            v = 1.0
        mask = (bin_centers >= l) & (bin_centers <= h)
        cnt = np.count_nonzero(mask)
        if cnt > 0:
            vol_profile[mask] += v / cnt
            tpo_profile[mask] += 1.0  # Steidlmayer TPO: price bracket presence
        else:
            idx = int(np.argmin(np.abs(bin_centers - c)))
            vol_profile[idx] += v
            tpo_profile[idx] += 1.0

    tot_vol = np.sum(vol_profile)
    if tot_vol <= 0:
        mean_p = float(np.mean(closes))
        if return_tpoc:
            return mean_p, mean_p, mean_p, mean_p
        return mean_p, mean_p, mean_p

    poc_idx = int(np.argmax(vol_profile))
    vpoc = float(bin_centers[poc_idx])

    tpoc_idx = int(np.argmax(tpo_profile))
    tpoc = float(bin_centers[tpoc_idx])

    # 70% Value Area Expansion (CBOT Market Profile Standard)
    target_vol = tot_vol * va_pct
    accum_vol = vol_profile[poc_idx]
    up_idx = poc_idx
    dn_idx = poc_idx

    while accum_vol < target_vol and (up_idx < num_bins - 1 or dn_idx > 0):
        v_up = vol_profile[up_idx + 1] if up_idx < num_bins - 1 else 0.0
        v_dn = vol_profile[dn_idx - 1] if dn_idx > 0 else 0.0

        if v_up >= v_dn and up_idx < num_bins - 1:
            up_idx += 1
            accum_vol += v_up
        elif dn_idx > 0:
            dn_idx -= 1
            accum_vol += v_dn
        elif up_idx < num_bins - 1:
            up_idx += 1
            accum_vol += v_up
        else:
            break

    vah = float(bin_centers[up_idx])
    val = float(bin_centers[dn_idx])
    if return_tpoc:
        return vpoc, vah, val, tpoc
    return vpoc, vah, val


def setup_chart_ui(window):
    chart_layout = window.frameChartArea.layout()

    while chart_layout.count():
        item = chart_layout.takeAt(0)
        w = item.widget()
        if w:
            w.deleteLater()

    chart_layout.setContentsMargins(0, 0, 0, 0)
    chart_layout.setSpacing(0)

    assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets")
    if not os.path.exists(assets_dir):
        assets_dir = os.path.join(os.path.dirname(__file__), "assets")
    window.current_tf = mt5.TIMEFRAME_H1
    window.current_tf_str = "H1"
    window.current_sym = None
    window.chart_data_list = []
    window.tf_buttons = {}
    window.active_indicators = {"ema": False, "donchian": False}
    window.lbl_chart_title = QLabel("")  # Maintained as internal object for telemetry compatibility
    window._rates_cache = {}  # Session memory cache for offline resilience
    window._poc_visible = True
    window._va_visible = True
    window._vpoc_visible = True
    window._tpoc_visible = True
    window._vah_visible = True
    window._val_visible = True
    window._va_fill_visible = True
    window._last_vah = None
    window._last_val = None

    def toggle_vpoc(visible: bool = None):
        if visible is None:
            visible = not getattr(window, "_vpoc_visible", True)
        window._vpoc_visible = bool(visible)
        if hasattr(window, "line_vpoc") and window.line_vpoc:
            poc_vis = getattr(window, "_poc_visible", True)
            window.line_vpoc.setVisible(bool(visible) and poc_vis)
        return window._vpoc_visible

    def toggle_tpoc(visible: bool = None):
        if visible is None:
            visible = not getattr(window, "_tpoc_visible", True)
        window._tpoc_visible = bool(visible)
        if hasattr(window, "line_tpoc") and window.line_tpoc:
            poc_vis = getattr(window, "_poc_visible", True)
            window.line_tpoc.setVisible(bool(visible) and poc_vis)
        return window._tpoc_visible

    def toggle_vah(visible: bool = None):
        if visible is None:
            visible = not getattr(window, "_vah_visible", True)
        window._vah_visible = bool(visible)
        if hasattr(window, "line_vah") and window.line_vah:
            va_vis = getattr(window, "_va_visible", True)
            window.line_vah.setVisible(bool(visible) and va_vis)
        return window._vah_visible

    def toggle_val(visible: bool = None):
        if visible is None:
            visible = not getattr(window, "_val_visible", True)
        window._val_visible = bool(visible)
        if hasattr(window, "line_val") and window.line_val:
            va_vis = getattr(window, "_va_visible", True)
            window.line_val.setVisible(bool(visible) and va_vis)
        return window._val_visible

    def toggle_va_fill(visible: bool = None):
        if visible is None:
            visible = not getattr(window, "_va_fill_visible", True)
        window._va_fill_visible = bool(visible)
        if hasattr(window, "va_region") and window.va_region:
            va_vis = getattr(window, "_va_visible", True)
            window.va_region.setVisible(bool(visible) and va_vis)
        return window._va_fill_visible

    window.toggle_vpoc = toggle_vpoc
    window.toggle_tpoc = toggle_tpoc
    window.toggle_vah = toggle_vah
    window.toggle_val = toggle_val
    window.toggle_va_fill = toggle_va_fill

    def _open_indicators():
        def _refresh():
            if hasattr(window, "current_sym") and window.current_sym:
                draw_and_analyze(window.current_sym)
        dlg = IndicatorDialog(window, window.active_indicators, on_change=_refresh)
        dlg.exec()

    window.open_indicators = _open_indicators

    # Configure Floating Trading Plan Overlay:
    # 1. Expand chartSplitter to 100% full width (candlestick chart never squeezed)
    if hasattr(window, "chartSplitter") and window.chartSplitter:
        window.chartSplitter.setSizes([1440, 0])

    # 2. Re-parent frameAIArea as a direct floating child over frameChartArea
    if hasattr(window, "frameAIArea") and window.frameAIArea:
        window.frameAIArea.setParent(window.frameChartArea)
        window.frameAIArea.setObjectName("floatingTradingPlan")
        window.frameAIArea.setMinimumSize(310, 0)
        window.frameAIArea.setMaximumSize(360, 560)

    def _reposition_trading_plan():
        if not hasattr(window, "frameAIArea") or not window.frameAIArea:
            return
        if not hasattr(window, "frameChartArea") or not window.frameChartArea:
            return
        w = 325
        c_w = window.frameChartArea.width()
        c_h = window.frameChartArea.height()
        x = max(10, c_w - w - 85)
        ribbon_h = window.frameChartRibbon.height() if hasattr(window, "frameChartRibbon") and window.frameChartRibbon else 24
        y = ribbon_h + 8
        # Dynamic auto-fit height: shrink tightly to active tab content (zero dead white void)
        mode = getattr(window, "_plan_mode", "ai")
        target_h = 401 if mode == "ai" else 495
        h = min(target_h, max(200, c_h - y - 25))
        window.frameAIArea.setGeometry(x, y, w, h)
        window.frameAIArea.raise_()

    window._reposition_trading_plan = _reposition_trading_plan

    class ChartAreaOverlayFilter(QObject):
        def __init__(self, callback, parent=None):
            super().__init__(parent)
            self.callback = callback

        def eventFilter(self, watched, event):
            if event.type() in (QEvent.Resize, QEvent.Show):
                self.callback()
            return super().eventFilter(watched, event)

    if hasattr(window, "frameChartArea") and window.frameChartArea:
        overlay_filter = ChartAreaOverlayFilter(_reposition_trading_plan, window.frameChartArea)
        window.frameChartArea.installEventFilter(overlay_filter)
        window._chart_area_overlay_filter = overlay_filter

    def _close_ai_drawer():
        if hasattr(window, "frameAIArea") and window.frameAIArea:
            window.frameAIArea.setVisible(False)
        if hasattr(window, "btn_edge_plan") and window.btn_edge_plan:
            window.btn_edge_plan.setVisible(True)
        # Institutional UX: If user is drafting an unsubmitted manual order, hide preview draft lines
        # when collapsing the drawer to prevent phantom order confusion. Real broker positions and
        # MT5 pending orders are NEVER cleared and remain visible for continuous monitoring.
        is_live = getattr(window, "is_live_position", False)
        is_pending = getattr(window, "is_pending_order", False)
        if getattr(window, "_plan_mode", "ai") == "manual" and not is_live and not is_pending:
            try:
                from frontend.controllers.chart.trading_plan_panel import clear_manual_chart_lines
                clear_manual_chart_lines(window)
            except Exception:
                pass
    def _open_ai_drawer():
        if hasattr(window, "frameAIArea") and window.frameAIArea:
            window.frameAIArea.setVisible(True)
            _reposition_trading_plan()
        if hasattr(window, "btn_edge_plan") and window.btn_edge_plan:
            window.btn_edge_plan.setVisible(False)
        # Restore preview lines if drawer is reopened
        try:
            if getattr(window, "_plan_mode", "ai") == "manual":
                if getattr(window, "_show_manual_preview", True):
                    from frontend.controllers.chart.trading_plan_panel import _recalculate_manual_lot_and_rr
                    _recalculate_manual_lot_and_rr(window)
            else:
                try:
                    from frontend.controllers.chart.trading_plan_panel import sync_live_position_to_ai_plan
                    sync_live_position_to_ai_plan(window)
                except Exception:
                    pass
                clean_curr = getattr(window, "current_sym", "").split("\n")[0].strip()
                sig = getattr(window, "active_signals_by_symbol", {}).get(clean_curr, {})
                if not sig and hasattr(window, "active_signal_data") and isinstance(window.active_signal_data, dict):
                    if window.active_signal_data.get("sym", "").upper() == clean_curr.upper():
                        sig = window.active_signal_data
                from frontend.controllers.chart.trading_plan_panel import update_order_proposal_html
                if sig and sig.get("has_signal"):
                    update_order_proposal_html(
                        window, sym=clean_curr, entry=sig.get("entry"),
                        sl=sig.get("sl"), tp=sig.get("tp"), has_signal=True,
                        signal_type=sig.get("signal_type", "BUY"),
                        is_live_position=sig.get("is_live_position", False),
                        live_ticket=sig.get("live_ticket", None),
                        live_volume=sig.get("live_volume", None),
                        live_profit=sig.get("live_profit", 0.0),
                        model_name=sig.get("model_name", None),
                        grade=sig.get("grade", None),
                        status=sig.get("status", "LIVE POSITION IN MARKET"),
                        checklist=sig.get("checklist", None),
                    )
                else:
                    update_order_proposal_html(
                        window, sym=clean_curr, has_signal=False,
                        model_name=sig.get("model_name", None) if sig else None,
                        checklist=sig.get("checklist", None) if sig else None,
                    )
        except Exception:
            pass

    window._close_ai_drawer = _close_ai_drawer
    window._open_ai_drawer = _open_ai_drawer

    if hasattr(window, "btnAIClose") and window.btnAIClose:
        close_svg = os.path.join(assets_dir, "close_hairline.svg")
        if os.path.exists(close_svg):
            window.btnAIClose.setIcon(QIcon(close_svg))
            window.btnAIClose.setIconSize(QSize(11, 11))
            window.btnAIClose.setText("")
        window.btnAIClose.setCursor(Qt.PointingHandCursor)
        window.btnAIClose.setToolTip("Collapse Trading Plan Drawer")
        if not getattr(window.btnAIClose, "_ai_close_connected", False):
            window.btnAIClose.clicked.connect(_close_ai_drawer)
            window.btnAIClose._ai_close_connected = True

    # Configure Signal Approval Ticket inside frameAIArea
    if hasattr(window, "lblAIGateTitle"):
        window.lblAIGateTitle.setText("TRADING PLAN")
    if hasattr(window, "lblAISubtitle"):
        window.lblAISubtitle.setText("")

    # Construct institutional TradeZella-style 3-card Playbook inside frameAIArea
    setup_trading_plan_cards(window, is_dark=getattr(window, "is_dark_theme", False))

    # Default to closed Trading Plan so chart canvas and right price axis are 100% visible
    _close_ai_drawer()

    is_d_init = getattr(window, "is_dark_theme", False)
    bg_init = "#000000" if is_d_init else "#ffffff"
    axis_init = "#1c2438" if is_d_init else "#cbd5e1"
    text_init = "#64748b" if is_d_init else "#475569"

    window.time_axis = TimeAxisItem(orientation="bottom")

    window.plot_widget = pg.PlotWidget(
        background=bg_init, axisItems={"bottom": window.time_axis}
    )

    window.plot_widget.setMouseEnabled(x=True, y=False)

    window.plot_widget.showGrid(x=True, y=True, alpha=0.06)
    window.plot_widget.getPlotItem().hideButtons()

    window.plot_widget.showAxis("right")
    window.plot_widget.hideAxis("left")
    window.plot_widget.getAxis("right").setPen(pg.mkPen(color=axis_init))
    window.plot_widget.getAxis("bottom").setPen(pg.mkPen(color=axis_init))
    window.plot_widget.getAxis("right").setTextPen(pg.mkPen(color=text_init))
    window.plot_widget.getAxis("bottom").setTextPen(pg.mkPen(color=text_init))
    window.plot_widget.getAxis("right").setWidth(55)

    # Sub-Pane PlotWidget for Oscillators (RSI, MACD, CVD)
    osc_bg_init = "#000000" if is_d_init else "#f8fafc"
    window.osc_plot_widget = pg.PlotWidget(background=osc_bg_init)
    window.osc_plot_widget.setMouseEnabled(x=True, y=False)
    window.osc_plot_widget.showGrid(x=True, y=True, alpha=0.06)
    window.osc_plot_widget.getPlotItem().hideButtons()
    window.osc_plot_widget.showAxis("right")
    window.osc_plot_widget.hideAxis("left")
    window.osc_plot_widget.hideAxis("bottom")
    window.osc_plot_widget.getAxis("right").setPen(pg.mkPen(color=axis_init))
    window.osc_plot_widget.getAxis("right").setTextPen(pg.mkPen(color=text_init))
    window.osc_plot_widget.getAxis("right").setWidth(55)
    window.osc_plot_widget.setMaximumHeight(130)
    window.osc_plot_widget.setMinimumHeight(85)
    window.osc_plot_widget.setXLink(window.plot_widget)
    window.osc_plot_widget.setVisible(False)

    # Chart Sub-Header Ribbon (height: 24px)
    ribbon = QFrame()
    ribbon.setObjectName("frameChartRibbon")
    ribbon.setFixedHeight(24)
    ribbon.setStyleSheet("QFrame#frameChartRibbon { background-color: #050608; border-bottom: 1px solid #1c1c1c; }")
    ribbon_layout = QHBoxLayout(ribbon)
    ribbon_layout.setContentsMargins(6, 0, 6, 0)
    ribbon_layout.setSpacing(6)
    ribbon_layout.setAlignment(Qt.AlignVCenter)

    # Edge Tab: Watchlist restore button (appears when Watchlist is folded)
    btn_edge_wl = QPushButton(" WATCHLIST")
    btn_edge_wl.setObjectName("btnEdgeWatchlist")
    btn_edge_wl.setFixedHeight(18)
    btn_edge_wl.setCursor(Qt.PointingHandCursor)
    btn_edge_wl.setToolTip("Toggle Watchlist Panel")
    chevron_right_svg = os.path.join(assets_dir, "chevron_right_pro.svg")
    if os.path.exists(chevron_right_svg):
        btn_edge_wl.setIcon(QIcon(chevron_right_svg))
        btn_edge_wl.setIconSize(QSize(10, 10))
    btn_edge_wl.setStyleSheet(
        "QPushButton#btnEdgeWatchlist { background-color: transparent; color: #475569; border: 1px solid transparent; "
        "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0 6px; min-height: 18px; max-height: 18px; } "
        "QPushButton#btnEdgeWatchlist:hover { background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; }"
    )
    def _expand_wl_from_ribbon():
        if hasattr(window, "sidebar") and hasattr(window, "mainSplitter"):
            window.sidebar.setVisible(True)
            window.watchlist_collapsed = False
            total_w = max(400, window.mainSplitter.width())
            sidebar_w = 260
            window.mainSplitter.setSizes([sidebar_w, max(100, total_w - sidebar_w)])
        btn_edge_wl.setVisible(False)

    btn_edge_wl.clicked.connect(_expand_wl_from_ribbon)
    btn_edge_wl.setVisible(False)
    window.btn_edge_wl = btn_edge_wl
    ribbon_layout.addWidget(btn_edge_wl)

    lbl_ribbon_left = CompactRibbonLabel(
        '<span style="font-family:Consolas, monospace; font-size:9px; color:#71717a;">'
        'SESSION: <b style="color:#ffffff;">--</b> &nbsp;|&nbsp; '
        'vPOC: <b style="color:#ffffff;">--</b> &nbsp;|&nbsp; '
        'VAH: <b style="color:#ffffff;">--</b> &nbsp;|&nbsp; '
        'VAL: <b style="color:#ffffff;">--</b> &nbsp;|&nbsp; '
        'tPOC: <b style="color:#ffffff;">--</b> &nbsp;|&nbsp; '
        'Δ: <b style="color:#ffffff;">--</b>'
        '</span>'
    )
    lbl_ribbon_left.setMinimumWidth(0)
    lbl_ribbon_left.setToolTip("Steidlmayer Market Profile: 70% Value Area (VAH/VAL), Volume POC, Time POC & Order Flow Delta")
    ribbon_layout.addWidget(lbl_ribbon_left)

    lbl_chart_ohlc = CompactRibbonLabel(
        '<span style="font-family:Consolas, monospace; font-size:9px; color:#64748b;">'
        'O: <b style="color:#f8fafc;">--</b> &nbsp;'
        'H: <b style="color:#f8fafc;">--</b> &nbsp;'
        'L: <b style="color:#f8fafc;">--</b> &nbsp;'
        'C: <b style="color:#f8fafc;">--</b> &nbsp;'
        '<b style="color:#22c55e;">+0.00%</b>'
        '</span>'
    )
    lbl_chart_ohlc.setMinimumWidth(0)
    window.lbl_chart_ohlc = lbl_chart_ohlc
    ribbon_layout.addWidget(lbl_chart_ohlc)

    lbl_chart_studies = CompactRibbonLabel("")
    lbl_chart_studies.setObjectName("lblChartStudies")
    lbl_chart_studies.setMinimumWidth(0)
    lbl_chart_studies.setVisible(False)
    lbl_chart_studies.setToolTip("Active Studies & Quantitative Indicators (TradingView / Bloomberg Terminal style)")
    window.lbl_chart_studies = lbl_chart_studies
    ribbon_layout.addWidget(lbl_chart_studies)

    ribbon_layout.addStretch()

    lbl_zoom = QLabel('<span style="color:#71717a; font-family:Consolas, monospace; font-size:8.5px;">100%</span>')
    ribbon_layout.addWidget(lbl_zoom)

    # Institutional Auto-Scale button
    btn_autoscale = QPushButton("AUTO FIT")
    btn_autoscale.setObjectName("btnChartAutoScale")
    btn_autoscale.setFixedHeight(18)
    btn_autoscale.setCursor(Qt.PointingHandCursor)
    btn_autoscale.setToolTip("Reset Chart Scale (Auto Range)")
    btn_autoscale.clicked.connect(lambda: window.plot_widget.enableAutoRange())
    window.btnChartAutoScale = btn_autoscale
    ribbon_layout.addWidget(btn_autoscale)

    from backend.core.timezone_manager import timezone_manager, SUPPORTED_TIMEZONES
    from PySide6.QtWidgets import QMenu
    from PySide6.QtCore import QPoint

    btn_tz = QPushButton(f"{timezone_manager.short_label} ▾")
    btn_tz.setObjectName("btnChartTimezone")
    btn_tz.setFixedHeight(18)
    btn_tz.setCursor(Qt.PointingHandCursor)
    btn_tz.setToolTip("Chart & Calendar Display Timezone (Click to change)")
    btn_tz.setStyleSheet(
        "QPushButton#btnChartTimezone { background-color: transparent; color: #94a3b8; "
        "border: 1px solid rgba(255, 255, 255, 0.08); font-family: Consolas, monospace; "
        "font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0 5px; min-height: 18px; max-height: 18px; } "
        "QPushButton#btnChartTimezone:hover { background-color: #1e293b; color: #f8fafc; border: 1px solid #334155; }"
    )

    def _open_tz_menu():
        menu = QMenu(btn_tz)
        is_d = getattr(window, "is_dark_theme", False)
        m_bg = "#101524" if is_d else "#ffffff"
        m_bdr = "#1e293b" if is_d else "#cbd5e1"
        m_txt = "#94a3b8" if is_d else "#475569"
        m_hvr = "#1e293b" if is_d else "#f1f5f9"
        m_htxt = "#f8fafc" if is_d else "#0f172a"
        menu.setStyleSheet(f"""
            QMenu {{ background-color: {m_bg}; border: 1px solid {m_bdr}; border-radius: 2px; padding: 2px; }}
            QMenu::item {{ color: {m_txt}; font-family: Consolas, monospace; font-size: 9.5px; padding: 4px 16px 4px 10px; }}
            QMenu::item:selected {{ background-color: {m_hvr}; color: {m_htxt}; }}
        """)
        for k, v in SUPPORTED_TIMEZONES.items():
            prefix = "✓ " if k == timezone_manager.active_key else "   "
            act = menu.addAction(f"{prefix}{v['menu_text']}")
            def _make_handler(tz_k):
                return lambda: _apply_tz(tz_k)
            act.triggered.connect(_make_handler(k))
        menu.exec_(btn_tz.mapToGlobal(QPoint(0, btn_tz.height())))

    def _apply_tz(tz_k):
        timezone_manager.set_active_timezone(tz_k)
        btn_tz.setText(f"{timezone_manager.short_label} ▾")
        if hasattr(window, "plot_widget"):
            b_axis = window.plot_widget.getAxis("bottom")
            if hasattr(b_axis, "picture"):
                b_axis.picture = None
            window.plot_widget.update()

    btn_tz.clicked.connect(_open_tz_menu)
    ribbon_layout.addWidget(btn_tz)
    window.btn_chart_tz = btn_tz

    # Edge Tab: Trading Plan restore button (appears when Trading Plan is folded)
    btn_edge_plan = QPushButton(" TRADING PLAN")
    btn_edge_plan.setObjectName("btnEdgeTradingPlan")
    btn_edge_plan.setFixedHeight(18)
    btn_edge_plan.setCursor(Qt.PointingHandCursor)
    btn_edge_plan.setToolTip("Toggle Trading Plan Drawer")
    chevron_left_svg = os.path.join(assets_dir, "chevron_left.svg")
    if os.path.exists(chevron_left_svg):
        btn_edge_plan.setIcon(QIcon(chevron_left_svg))
        btn_edge_plan.setIconSize(QSize(10, 10))
    btn_edge_plan.setStyleSheet(
        "QPushButton#btnEdgeTradingPlan { background-color: transparent; color: #94a3b8; border: 1px solid transparent; "
        "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0 6px; min-height: 18px; max-height: 18px; } "
        "QPushButton#btnEdgeTradingPlan:hover { background-color: #1e293b; color: #f8fafc; border: 1px solid #334155; }"
    )
    btn_edge_plan.clicked.connect(_open_ai_drawer)
    btn_edge_plan.setVisible(False)
    window.btn_edge_plan = btn_edge_plan
    ribbon_layout.addWidget(btn_edge_plan)

    window.frameChartRibbon = ribbon
    window.lbl_ribbon_left = lbl_ribbon_left
    window.lbl_chart_zoom = lbl_zoom
    window.lbl_chart_live_badge = btn_tz

    # Vertical Drawing Toolbar (width: 26px) - Institutional Interactive Chart Controls
    toolbar_draw = QFrame()
    toolbar_draw.setObjectName("toolbarChartDrawing")
    toolbar_draw.setFixedWidth(26)
    is_d_init = getattr(window, "is_dark_theme", False)
    tb_bg_init = "#050608" if is_d_init else "#f8fafc"
    tb_bdr_init = "#1c1c1c" if is_d_init else "#e2e8f0"
    toolbar_draw.setStyleSheet(f"QFrame#toolbarChartDrawing {{ background-color: {tb_bg_init}; border-right: 1px solid {tb_bdr_init}; border-bottom: 1px solid {tb_bdr_init}; }}")
    tb_layout = QVBoxLayout(toolbar_draw)
    tb_layout.setContentsMargins(2, 4, 2, 4)
    tb_layout.setSpacing(4)
    tb_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

    def _get_tool_btn_style(is_dark, is_active=False, is_accent=False):
        if is_active:
            bg = "#1e293b" if is_dark else "#e2e8f0"
            border = "1px solid #475569" if is_dark else "1px solid #94a3b8"
            return f"QPushButton {{ background-color: {bg}; border: {border}; border-radius: 2px; min-width: 20px; max-width: 20px; min-height: 20px; max-height: 20px; padding: 0px; margin: 0px; }}"
        else:
            hover_bg = "#18181b" if is_dark else "#f1f5f9"
            return f"QPushButton {{ background: transparent; border: 1px solid transparent; border-radius: 2px; min-width: 20px; max-width: 20px; min-height: 20px; max-height: 20px; padding: 0px; margin: 0px; }} QPushButton:hover {{ background-color: {hover_bg}; }}"

    drawing_engine = ChartDrawingEngine(window)
    window.drawing_engine = drawing_engine

    # 1. Crosshair Toggle Button
    btn_crosshair = QPushButton()
    btn_crosshair.setObjectName("btnToolCrosshair")
    btn_crosshair.setFixedSize(22, 22)
    btn_crosshair.setCheckable(True)
    btn_crosshair.setChecked(True)
    btn_crosshair.setCursor(Qt.PointingHandCursor)
    btn_crosshair.setToolTip("Crosshair Mode & Coordinates (C)")
    ic_ch = os.path.join(assets_dir, "tool_crosshair.svg")
    if os.path.exists(ic_ch):
        btn_crosshair.setIcon(QIcon(ic_ch))
        btn_crosshair.setIconSize(QSize(12, 12))
    btn_crosshair.setStyleSheet(_get_tool_btn_style(is_d_init, is_active=True, is_accent=False))
    btn_crosshair.clicked.connect(lambda: drawing_engine.set_mode(ChartDrawingEngine.MODE_CROSSHAIR))
    tb_layout.addWidget(btn_crosshair)

    # 2. Trendline Drawing Tool Button
    btn_poc = QPushButton()
    btn_poc.setObjectName("btnToolPOC")
    btn_poc.setFixedSize(22, 22)
    btn_poc.setCheckable(True)
    btn_poc.setChecked(False)
    btn_poc.setCursor(Qt.PointingHandCursor)
    btn_poc.setToolTip("Draw Trendline (Click & Drag) | Double-Click to Toggle POC")
    ic_poc = os.path.join(assets_dir, "tool_trendline.svg")
    if os.path.exists(ic_poc):
        btn_poc.setIcon(QIcon(ic_poc))
        btn_poc.setIconSize(QSize(12, 12))
    btn_poc.setStyleSheet(_get_tool_btn_style(is_d_init, is_active=False, is_accent=False))
    btn_poc.clicked.connect(lambda: drawing_engine.set_mode(ChartDrawingEngine.MODE_TRENDLINE))
    tb_layout.addWidget(btn_poc)

    # 3. FVG / Zone Box Drawing Tool Button
    btn_fvg = QPushButton()
    btn_fvg.setObjectName("btnToolFVG")
    btn_fvg.setFixedSize(22, 22)
    btn_fvg.setCheckable(True)
    btn_fvg.setChecked(False)
    btn_fvg.setCursor(Qt.PointingHandCursor)
    btn_fvg.setToolTip("Draw Zone Box (Click & Drag) | Double-Click to Toggle FVG")
    ic_fvg = os.path.join(assets_dir, "tool_rect.svg")
    if os.path.exists(ic_fvg):
        btn_fvg.setIcon(QIcon(ic_fvg))
        btn_fvg.setIconSize(QSize(12, 12))
    btn_fvg.setStyleSheet(_get_tool_btn_style(is_d_init, is_active=False, is_accent=False))
    btn_fvg.clicked.connect(lambda: drawing_engine.set_mode(ChartDrawingEngine.MODE_RECTANGLE))
    tb_layout.addWidget(btn_fvg)

    # 4. Market Profile Levels Tool Drawer & Button (TradingView / Exocharts Style)
    class ModernSwitch(QWidget):
        """Sleek iOS / TradingView style pill toggle switch."""
        def __init__(self, checked=True, is_dark=False, on_toggle=None, parent=None):
            super().__init__(parent)
            self.setFixedSize(28, 16)
            self.setCursor(Qt.PointingHandCursor)
            self._checked = bool(checked)
            self._is_dark = bool(is_dark)
            self._on_toggle = on_toggle

        def isChecked(self):
            return self._checked

        def setChecked(self, val):
            if self._checked != bool(val):
                self._checked = bool(val)
                self.update()
                if self._on_toggle:
                    self._on_toggle(self._checked)

        def mousePressEvent(self, event):
            if event.button() == Qt.LeftButton:
                self.setChecked(not self._checked)
                event.accept()

        def paintEvent(self, event):
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            if self._checked:
                track_color = QColor("#0284c7" if not self._is_dark else "#38bdf8")
            else:
                track_color = QColor("#cbd5e1" if not self._is_dark else "#334155")
            p.setBrush(QBrush(track_color))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(0, 0, 28, 16, 8, 8)

            thumb_color = QColor("#ffffff" if not self._is_dark else "#0f172a")
            p.setBrush(QBrush(thumb_color))
            thumb_x = 14 if self._checked else 2
            p.drawEllipse(thumb_x, 2, 12, 12)
            p.end()

    class ProfileLevelRow(QFrame):
        """
        Interactive level row with tick box on the left, color badge, title, and subtitle.
        Provides 100% design consistency with the Studies & Indicators dialog.
        """
        def __init__(self, key, code_name, desc, color_hex, checked=True, shape="line", is_dark=False, on_change=None, parent=None):
            super().__init__(parent)
            self.key = key
            self.color_hex = color_hex
            self._is_dark = is_dark
            self._shape = shape
            self._on_change = on_change
            self.setFixedHeight(34)
            self.setCursor(Qt.PointingHandCursor)
            self.setObjectName(f"row_{key}")

            bg_hover = "#f1f5f9" if not is_dark else "#161d31"
            self.setStyleSheet(f"""
                QFrame#{self.objectName()} {{
                    background-color: transparent;
                    border: 1px solid transparent;
                    border-radius: 2px;
                }}
                QFrame#{self.objectName()}:hover {{
                    background-color: {bg_hover};
                }}
            """)

            layout = QHBoxLayout(self)
            layout.setContentsMargins(6, 2, 8, 2)
            layout.setSpacing(8)
            layout.setAlignment(Qt.AlignVCenter)

            # 1. Tick box (Checkbox on LEFT, matching indicator_dialog.py design)
            self.cb = QCheckBox()
            self.cb.setObjectName("profileRowCheckbox")
            self.cb.setFixedSize(16, 16)
            self.cb.setCursor(Qt.PointingHandCursor)
            self.cb.setChecked(checked)

            ic_check_clean = os.path.join(assets_dir, "check_icon.svg").replace("\\", "/")
            if not is_dark:
                cb_style = f"""
                    QCheckBox#profileRowCheckbox {{
                        spacing: 0px;
                    }}
                    QCheckBox#profileRowCheckbox::indicator {{
                        width: 15px;
                        height: 15px;
                        border-radius: 3px;
                        border: 1px solid #cbd5e1;
                        background-color: #f8fafc;
                    }}
                    QCheckBox#profileRowCheckbox::indicator:hover {{
                        border-color: #0f172a;
                    }}
                    QCheckBox#profileRowCheckbox::indicator:checked {{
                        background-color: #0f172a;
                        border: 1px solid #0f172a;
                        image: url("{ic_check_clean}");
                    }}
                """
            else:
                cb_style = f"""
                    QCheckBox#profileRowCheckbox {{
                        spacing: 0px;
                    }}
                    QCheckBox#profileRowCheckbox::indicator {{
                        width: 15px;
                        height: 15px;
                        border-radius: 3px;
                        border: 1px solid #334155;
                        background-color: #161b26;
                    }}
                    QCheckBox#profileRowCheckbox::indicator:hover {{
                        border-color: #38bdf8;
                    }}
                    QCheckBox#profileRowCheckbox::indicator:checked {{
                        background-color: #0284c7;
                        border: 1px solid #38bdf8;
                        image: url("{ic_check_clean}");
                    }}
                """
            self.cb.setStyleSheet(cb_style)
            self.cb.toggled.connect(self._on_cb_toggled)
            layout.addWidget(self.cb)

            # 2. Color swatch badge
            self.lbl_badge = QLabel()
            self.lbl_badge.setFixedSize(16, 16)
            self.lbl_badge.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            self._draw_badge(checked)
            layout.addWidget(self.lbl_badge)

            # 3. Title + Description
            title_box = QVBoxLayout()
            title_box.setContentsMargins(0, 0, 0, 0)
            title_box.setSpacing(1)

            c_text = "#0f172a" if not is_dark else "#f8fafc"
            c_sub = "#64748b" if not is_dark else "#94a3b8"

            self.lbl_code = QLabel(code_name)
            self.lbl_code.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            self.lbl_code.setStyleSheet(f"color: {c_text}; font-weight: 700; font-size: 11px; font-family: 'Segoe UI', Consolas;")

            self.lbl_desc = QLabel(desc)
            self.lbl_desc.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            self.lbl_desc.setStyleSheet(f"color: {c_sub}; font-size: 9px; font-family: 'Segoe UI', sans-serif;")

            title_box.addWidget(self.lbl_code)
            title_box.addWidget(self.lbl_desc)
            layout.addLayout(title_box, stretch=1)

        def _draw_badge(self, checked):
            pm = QPixmap(16, 16)
            pm.fill(Qt.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.Antialiasing)

            color = QColor(self.color_hex)
            if not checked:
                color.setAlpha(60)

            if self._shape == "line":
                pen = QPen(color, 2.5)
                pen.setCapStyle(Qt.RoundCap)
                p.setPen(pen)
                p.drawLine(1, 8, 15, 8)
            elif self._shape == "rect":
                col = QColor(self.color_hex)
                col.setAlpha(90 if checked else 30)
                p.setBrush(QBrush(col))
                p.setPen(QPen(color, 1.0))
                p.drawRoundedRect(1, 4, 14, 8, 2, 2)
            p.end()
            self.lbl_badge.setPixmap(pm)

        def _on_cb_toggled(self, val):
            self._draw_badge(val)
            if self._on_change:
                self._on_change(val)

        def mousePressEvent(self, event):
            if event.button() == Qt.LeftButton:
                if not self.cb.geometry().contains(event.pos()):
                    self.cb.setChecked(not self.cb.isChecked())
                event.accept()
            else:
                super().mousePressEvent(event)

        def setChecked(self, val):
            self.cb.setChecked(val)

        def isChecked(self):
            return self.cb.isChecked()

        @property
        def switch(self):
            return self.cb

    class MarketProfileDrawer(QWidget):
        """
        World-class TradingView / Exocharts style Market Profile Tool Drawer.
        Floating tool palette with drop shadow, color badges, and iOS switches.
        """
        def __init__(self, parent=None, is_dark=False, on_close=None):
            super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.is_dark = is_dark
            self.on_close = on_close
            self.setFixedWidth(256)

            main_layout = QVBoxLayout(self)
            main_layout.setContentsMargins(10, 10, 10, 10)

            self.card = QFrame()
            self.card.setObjectName("drawerCard")
            bg_card = "#ffffff" if not is_dark else "#0c0e17"
            border_card = "#e2e8f0" if not is_dark else "#272d3b"

            self.card.setStyleSheet(f"""
                QFrame#drawerCard {{
                    background-color: {bg_card};
                    border: 1px solid {border_card};
                    border-radius: 2px;
                }}
            """)

            card_layout = QVBoxLayout(self.card)
            card_layout.setContentsMargins(10, 10, 10, 10)
            card_layout.setSpacing(4)

            # Header
            hdr_layout = QHBoxLayout()
            hdr_layout.setContentsMargins(2, 0, 2, 4)

            lbl_title = QLabel("MARKET PROFILE LEVELS")
            lbl_title.setStyleSheet(f"color: {'#64748b' if not is_dark else '#94a3b8'}; font-weight: 700; font-size: 9.5px; letter-spacing: 0.8px; font-family: 'Segoe UI', sans-serif;")
            hdr_layout.addWidget(lbl_title, stretch=1)

            btn_close = QPushButton("×")
            btn_close.setFixedSize(18, 18)
            btn_close.setCursor(Qt.PointingHandCursor)
            btn_close.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    color: {'#94a3b8' if not is_dark else '#64748b'};
                    font-size: 14px;
                    font-weight: 700;
                    border-radius: 2px;
                }}
                QPushButton:hover {{
                    background-color: {'#f1f5f9' if not is_dark else '#1e293b'};
                    color: {'#0f172a' if not is_dark else '#f8fafc'};
                }}
            """)
            btn_close.clicked.connect(self.close)
            hdr_layout.addWidget(btn_close)

            card_layout.addLayout(hdr_layout)

            div1 = QFrame()
            div1.setFixedHeight(1)
            div1.setStyleSheet(f"background-color: {'#f1f5f9' if not is_dark else '#1e293b'};")
            card_layout.addWidget(div1)
            card_layout.addSpacing(2)

            # Rows
            c_vpoc = "#10b981"
            c_tpoc = "#f43f5e"
            c_va = "#0284c7" if not is_dark else "#38bdf8"

            self.rows = {}

            self.rows["vpoc"] = ProfileLevelRow("vpoc", "vPOC", "Volume Point of Control", c_vpoc, getattr(window, "_vpoc_visible", True), "line", is_dark, toggle_vpoc, self)
            card_layout.addWidget(self.rows["vpoc"])

            self.rows["tpoc"] = ProfileLevelRow("tpoc", "tPOC", "Time Point of Control (CBOT)", c_tpoc, getattr(window, "_tpoc_visible", True), "line", is_dark, toggle_tpoc, self)
            card_layout.addWidget(self.rows["tpoc"])

            self.rows["vah"] = ProfileLevelRow("vah", "VAH", "Value Area High (70%)", c_va, getattr(window, "_vah_visible", True), "line", is_dark, toggle_vah, self)
            card_layout.addWidget(self.rows["vah"])

            self.rows["val"] = ProfileLevelRow("val", "VAL", "Value Area Low (70%)", c_va, getattr(window, "_val_visible", True), "line", is_dark, toggle_val, self)
            card_layout.addWidget(self.rows["val"])

            self.rows["va_fill"] = ProfileLevelRow("va_fill", "Value Area Fill", "70% Shaded Liquidity Zone", c_va, getattr(window, "_va_fill_visible", True), "rect", is_dark, toggle_va_fill, self)
            card_layout.addWidget(self.rows["va_fill"])

            card_layout.addSpacing(4)
            div2 = QFrame()
            div2.setFixedHeight(1)
            div2.setStyleSheet(f"background-color: {'#f1f5f9' if not is_dark else '#1e293b'};")
            card_layout.addWidget(div2)
            card_layout.addSpacing(2)

            # Footer actions
            ftr_layout = QHBoxLayout()
            ftr_layout.setContentsMargins(2, 2, 2, 0)

            btn_show_all = QPushButton("Show All")
            btn_show_all.setCursor(Qt.PointingHandCursor)
            btn_show_all.setStyleSheet(f"""
                QPushButton {{
                    background-color: {'#f1f5f9' if not is_dark else '#161d31'};
                    border: 1px solid {'#e2e8f0' if not is_dark else '#272d3b'};
                    border-radius: 4px;
                    color: {'#0f172a' if not is_dark else '#e2e8f0'};
                    font-size: 10px;
                    font-weight: 600;
                    padding: 4px 8px;
                }}
                QPushButton:hover {{
                    background-color: {'#e2e8f0' if not is_dark else '#1e293b'};
                    color: {'#0284c7' if not is_dark else '#38bdf8'};
                }}
            """)
            btn_show_all.clicked.connect(self._show_all)
            ftr_layout.addWidget(btn_show_all)

            btn_hide_all = QPushButton("Hide All")
            btn_hide_all.setCursor(Qt.PointingHandCursor)
            btn_hide_all.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: 1px solid {'#e2e8f0' if not is_dark else '#272d3b'};
                    border-radius: 4px;
                    color: {'#64748b' if not is_dark else '#94a3b8'};
                    font-size: 10px;
                    font-weight: 600;
                    padding: 4px 8px;
                }}
                QPushButton:hover {{
                    background-color: {'#f1f5f9' if not is_dark else '#161d31'};
                    color: {'#ef4444' if not is_dark else '#f87171'};
                    border-color: {'#fca5a5' if not is_dark else '#7f1d1d'};
                }}
            """)
            btn_hide_all.clicked.connect(self._hide_all)
            ftr_layout.addWidget(btn_hide_all)

            card_layout.addLayout(ftr_layout)
            main_layout.addWidget(self.card)

        def _show_all(self):
            for r in self.rows.values():
                r.setChecked(True)

        def _hide_all(self):
            for r in self.rows.values():
                r.setChecked(False)

        def hideEvent(self, event):
            super().hideEvent(event)
            if self.on_close:
                self.on_close()

    class ProfileToolButton(QPushButton):
        """
        Custom toolbar button with authentic TradingView-style expand caret (icon mở ▶).
        """
        def __init__(self, is_dark=False, parent=None):
            super().__init__(parent)
            self.setFixedSize(22, 22)
            self.setCursor(Qt.PointingHandCursor)
            self._is_dark = is_dark
            self.setCheckable(True)

        def paintEvent(self, event):
            super().paintEvent(event)
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)

            # If no icon file found, draw fallback vector profile levels directly
            if self.icon().isNull():
                p.setPen(QPen(QColor("#71717a"), 1.2, Qt.SolidLine, Qt.RoundCap))
                p.drawLine(3, 4, 11, 4)
                p.setPen(QPen(QColor("#10b981"), 1.6, Qt.SolidLine, Qt.RoundCap))
                p.drawLine(3, 7, 14, 7)
                p.setPen(QPen(QColor("#f43f5e"), 1.4, Qt.SolidLine, Qt.RoundCap))
                p.drawLine(3, 10, 12, 10)
                p.setPen(QPen(QColor("#71717a"), 1.2, Qt.SolidLine, Qt.RoundCap))
                p.drawLine(3, 13, 9, 13)

            caret_col = QColor("#0284c7" if self.isChecked() else ("#94a3b8" if self._is_dark else "#71717a"))
            p.setBrush(QBrush(caret_col))
            p.setPen(Qt.NoPen)
            w, h = self.width(), self.height()
            # Crisp 4x4 right-facing expand triangle in bottom-right corner (icon mở TradingView)
            p.drawPolygon([QPoint(w - 5, h - 6), QPoint(w - 1, h - 3.5), QPoint(w - 5, h - 1)])
            p.end()

    def _show_profile_levels_menu(trigger_btn):
        is_dark = getattr(window, "is_dark_theme", False)
        
        # Close existing drawer if already open
        if hasattr(window, "_profile_drawer") and window._profile_drawer:
            try:
                window._profile_drawer.close()
            except Exception:
                pass
            window._profile_drawer = None

        trigger_btn.setChecked(True)

        def _on_drawer_closed():
            trigger_btn.setChecked(False)

        drawer = MarketProfileDrawer(parent=window, is_dark=is_dark, on_close=_on_drawer_closed)
        window._profile_drawer = drawer

        # Position cleanly to the right of the toolbar button
        btn_rect = trigger_btn.rect()
        pos = trigger_btn.mapToGlobal(btn_rect.topRight())
        drawer.move(pos.x() + 4, pos.y() - 14)
        drawer.show()

    btn_profile = ProfileToolButton(is_dark=is_d_init)
    btn_profile.setObjectName("btnToolProfile")
    btn_profile.setToolTip("Market Profile Levels (vPOC, tPOC, VAH, VAL)")
    ic_candidates = [
        os.path.join(assets_dir, "tool_profile.svg"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets", "tool_profile.svg"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets", "tool_profile.svg"),
        os.path.join(os.path.dirname(__file__), "assets", "tool_profile.svg"),
    ]
    for ic_p in ic_candidates:
        if os.path.exists(ic_p):
            btn_profile.setIcon(QIcon(ic_p))
            btn_profile.setIconSize(QSize(13, 13))
            break
    btn_profile.setStyleSheet(_get_tool_btn_style(is_d_init, is_active=False, is_accent=False))
    btn_profile.clicked.connect(lambda: _show_profile_levels_menu(btn_profile))
    tb_layout.addWidget(btn_profile)

    # 5. Ruler / Measurement Tool Button
    btn_ruler = QPushButton()
    btn_ruler.setObjectName("btnToolRuler")
    btn_ruler.setFixedSize(22, 22)
    btn_ruler.setCheckable(True)
    btn_ruler.setChecked(False)
    btn_ruler.setCursor(Qt.PointingHandCursor)
    btn_ruler.setToolTip("Ruler (Click & Drag to measure Pips, %, Bars)")
    ic_ruler = os.path.join(assets_dir, "tool_ruler.svg")
    if os.path.exists(ic_ruler):
        btn_ruler.setIcon(QIcon(ic_ruler))
        btn_ruler.setIconSize(QSize(12, 12))
    btn_ruler.setStyleSheet(_get_tool_btn_style(is_d_init, is_active=False, is_accent=True))
    btn_ruler.clicked.connect(lambda: drawing_engine.set_mode(ChartDrawingEngine.MODE_RULER))
    tb_layout.addWidget(btn_ruler)

    # 5. Clear All Drawings Button
    btn_clear = QPushButton()
    btn_clear.setObjectName("btnToolClear")
    btn_clear.setFixedSize(22, 22)
    btn_clear.setCursor(Qt.PointingHandCursor)
    btn_clear.setToolTip("Clear All Drawn Lines & Zones (Del)")
    ic_clear = os.path.join(assets_dir, "icon_reset.svg")
    if os.path.exists(ic_clear):
        btn_clear.setIcon(QIcon(ic_clear))
        btn_clear.setIconSize(QSize(11, 11))
    btn_clear.setStyleSheet(_get_tool_btn_style(is_d_init, is_active=False))
    btn_clear.clicked.connect(drawing_engine.clear_user_drawings)
    tb_layout.addWidget(btn_clear)

    # 6. Chart Settings Button
    btn_gear = QPushButton()
    btn_gear.setObjectName("btnToolGear")
    btn_gear.setFixedSize(22, 22)
    btn_gear.setCursor(Qt.PointingHandCursor)
    btn_gear.setToolTip("Chart Settings & System Options")
    ic_gear = os.path.join(assets_dir, "tool_gear.svg")
    if os.path.exists(ic_gear):
        btn_gear.setIcon(QIcon(ic_gear))
        btn_gear.setIconSize(QSize(12, 12))
    btn_gear.setStyleSheet(_get_tool_btn_style(is_d_init, is_active=False))

    def _open_chart_settings():
        if hasattr(window, "settings_mgr") and window.settings_mgr:
            window.settings_mgr.open_options_dialog()
        elif hasattr(window, "btnNavSettings"):
            window.btnNavSettings.click()

    btn_gear.clicked.connect(_open_chart_settings)
    tb_layout.addWidget(btn_gear)

    tb_layout.addStretch()
    window.toolbarChartDrawing = toolbar_draw
    window.btnToolCrosshair = btn_crosshair
    window.btnToolPOC = btn_poc
    window.btnToolFVG = btn_fvg
    window.btnToolRuler = btn_ruler
    window.btnToolGear = btn_gear
    window.btnToolClear = btn_clear
    window.btnToolProfile = btn_profile
    window.show_profile_levels_menu = _show_profile_levels_menu
    window._get_tool_btn_style = _get_tool_btn_style

    drawing_engine.set_toolbar_buttons(btn_crosshair, btn_poc, btn_fvg, btn_ruler, btn_gear, btn_clear, btn_profile=btn_profile)

    # Vertical container for main candlestick plot + collapsible oscillator sub-pane
    plots_container = QWidget()
    plots_layout = QVBoxLayout(plots_container)
    plots_layout.setContentsMargins(0, 0, 0, 0)
    plots_layout.setSpacing(2)
    plots_layout.addWidget(window.plot_widget, stretch=4)
    plots_layout.addWidget(window.osc_plot_widget, stretch=1)
    window.plots_container = plots_container

    # Horizontal row containing vertical toolbar and plots container
    chart_canvas_row = QWidget()
    canvas_row_layout = QHBoxLayout(chart_canvas_row)
    canvas_row_layout.setContentsMargins(0, 0, 0, 0)
    canvas_row_layout.setSpacing(0)
    canvas_row_layout.addWidget(toolbar_draw)
    canvas_row_layout.addWidget(plots_container)

    # 1. Dải cảnh báo dữ liệu ngoại tuyến (Kịch bản A - Có dữ liệu đệm cũ)
    offline_banner = QFrame()
    offline_banner.setObjectName("chartOfflineBanner")
    offline_banner.setFixedHeight(26)
    offline_banner.setStyleSheet(
        "QFrame#chartOfflineBanner { background-color: #fef3c7; border-bottom: 1px solid #fcd34d; }"
    )
    b_layout = QHBoxLayout(offline_banner)
    b_layout.setContentsMargins(10, 0, 10, 0)
    b_layout.setSpacing(8)

    tag_offline = QLabel("OFFLINE")
    tag_offline.setStyleSheet(
        "background-color: #fde68a; color: #92400e; font-family: 'Segoe UI'; font-size: 8.5px; "
        "font-weight: 700; border-radius: 2px; padding: 1px 5px;"
    )
    b_layout.addWidget(tag_offline)

    lbl_offline_msg = QLabel("MetaTrader 5 Disconnected. Displaying cached session data.")
    lbl_offline_msg.setStyleSheet("color: #78350f; font-family: 'Segoe UI'; font-size: 9.5px; font-weight: 600;")
    b_layout.addWidget(lbl_offline_msg)
    b_layout.addStretch()

    btn_offline_retry = QPushButton("RELOAD (F5)")
    btn_offline_retry.setFixedHeight(18)
    btn_offline_retry.setCursor(Qt.PointingHandCursor)
    btn_offline_retry.setStyleSheet(
        "QPushButton { background-color: #d97706; color: #ffffff; border: none; border-radius: 2px; "
        "font-family: 'Segoe UI'; font-size: 8.5px; font-weight: 700; padding: 0 8px; } "
        "QPushButton:hover { background-color: #b45309; }"
    )
    b_layout.addWidget(btn_offline_retry)
    offline_banner.setVisible(False)
    window.offline_banner = offline_banner
    window.lbl_offline_msg = lbl_offline_msg
    window.btn_offline_retry = btn_offline_retry

    chart_layout.addWidget(ribbon)
    chart_layout.addWidget(offline_banner)
    chart_layout.addWidget(chart_canvas_row)

    # 2. Thẻ chẩn đoán rỗng trung tâm (Kịch bản B - Khởi động lạnh, chưa có dữ liệu đệm)
    card_empty = QFrame(window.plot_widget)
    card_empty.setObjectName("chartEmptyStateCard")
    card_empty.setFixedWidth(520)
    card_empty.setStyleSheet(
        "QFrame#chartEmptyStateCard { "
        "background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 2px; }"
    )
    c_layout = QVBoxLayout(card_empty)
    c_layout.setContentsMargins(22, 18, 22, 18)
    c_layout.setSpacing(9)

    lbl_empty_title = QLabel("METATRADER 5 DISCONNECTED")
    lbl_empty_title.setStyleSheet("color: #b45309; font-family: 'Segoe UI'; font-size: 13px; font-weight: 700;")
    c_layout.addWidget(lbl_empty_title)

    lbl_empty_sub = QLabel("No live candle feed received for symbol")
    lbl_empty_sub.setStyleSheet("color: #475569; font-family: 'Segoe UI'; font-size: 11px;")
    c_layout.addWidget(lbl_empty_sub)

    sep_empty = QFrame()
    sep_empty.setFrameShape(QFrame.HLine)
    sep_empty.setStyleSheet("color: #e2e8f0;")
    c_layout.addWidget(sep_empty)

    sec1_lbl = QLabel("Possible Causes:")
    sec1_lbl.setStyleSheet("color: #334155; font-family: 'Segoe UI'; font-size: 10px; font-weight: 700;")
    c_layout.addWidget(sec1_lbl)

    for bullet in [
        "• MetaTrader 5 terminal is not running on this host.",
        "• Trading account is not logged into broker server.",
        "• Automated Algo Trading is disabled in MT5 (Ctrl+E).",
    ]:
        lb = QLabel(bullet)
        lb.setStyleSheet("color: #64748b; font-family: 'Segoe UI'; font-size: 10px; padding-left: 4px;")
        c_layout.addWidget(lb)

    sec2_lbl = QLabel("Recommended Actions:")
    sec2_lbl.setStyleSheet("color: #334155; font-family: 'Segoe UI'; font-size: 10px; font-weight: 700; margin-top: 4px;")
    c_layout.addWidget(sec2_lbl)

    for step in [
        "1. Launch MT5 and verify account server connection.",
        "2. Click button below or press F5 to reload feeds.",
    ]:
        ls = QLabel(step)
        ls.setStyleSheet("color: #64748b; font-family: 'Segoe UI'; font-size: 10px; padding-left: 4px;")
        c_layout.addWidget(ls)

    btn_row_layout = QHBoxLayout()
    btn_row_layout.setSpacing(8)
    btn_row_layout.setContentsMargins(0, 8, 0, 0)

    btn_empty_retry = QPushButton("RECONNECT (F5)")
    btn_empty_retry.setFixedHeight(26)
    btn_empty_retry.setCursor(Qt.PointingHandCursor)
    btn_empty_retry.setStyleSheet(
        "QPushButton { background-color: #0f172a; color: #ffffff; border: 1px solid #0f172a; "
        "border-radius: 2px; padding: 0 16px; font-family: 'Segoe UI'; font-size: 10px; font-weight: 700; } "
        "QPushButton:hover { background-color: #334155; }"
    )
    btn_row_layout.addWidget(btn_empty_retry)

    btn_empty_settings = QPushButton("OPEN SETTINGS")
    btn_empty_settings.setFixedHeight(26)
    btn_empty_settings.setCursor(Qt.PointingHandCursor)
    btn_empty_settings.setStyleSheet(
        "QPushButton { background-color: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; "
        "border-radius: 2px; padding: 0 14px; font-family: 'Segoe UI'; font-size: 10px; font-weight: 700; } "
        "QPushButton:hover { background-color: #e2e8f0; color: #0f172a; }"
    )
    btn_row_layout.addWidget(btn_empty_settings)
    btn_row_layout.addStretch()
    c_layout.addLayout(btn_row_layout)

    card_empty.adjustSize()
    card_empty.setVisible(False)
    window.empty_state_card = card_empty
    window.lbl_empty_sub = lbl_empty_sub
    window.btn_empty_retry = btn_empty_retry
    window.btn_empty_settings = btn_empty_settings

    btn_empty_retry.clicked.connect(lambda: window.draw_and_analyze(getattr(window, "current_sym", "XAUUSD")))
    btn_offline_retry.clicked.connect(lambda: window.draw_and_analyze(getattr(window, "current_sym", "XAUUSD")))

    def _open_options_dialog_action():
        qt = getattr(window, "quant_terminal", None)
        settings_mgr = (
            getattr(qt, "settings", None)
            or getattr(window, "settings_mgr", None)
        )
        if settings_mgr and hasattr(settings_mgr, "open_options_dialog"):
            settings_mgr.open_options_dialog()
        else:
            from frontend.widgets.options_dialog import OptionsDialog
            dlg = OptionsDialog(window)
            dlg.load_data()
            dlg.show()
            dlg.raise_()
            dlg.activateWindow()
    btn_empty_settings.clicked.connect(_open_options_dialog_action)

    # Quản lý định vị căn giữa thẻ rỗng tự động khi biểu đồ co giãn
    class ChartOverlayPositionFilter(QtCore.QObject):
        def __init__(self, target_widget, overlay_widget):
            super().__init__(target_widget)
            self.target_widget = target_widget
            self.overlay_widget = overlay_widget
            self.target_widget.installEventFilter(self)

        def eventFilter(self, obj, event):
            if obj == self.target_widget and event.type() in (QtCore.QEvent.Resize, QtCore.QEvent.Show):
                self.reposition()
            return super().eventFilter(obj, event)

        def reposition(self):
            if hasattr(self, "overlay_widget") and self.overlay_widget:
                w = self.overlay_widget.width()
                h = self.overlay_widget.height()
                x = max(10, (self.target_widget.width() - w) // 2)
                y = max(10, (self.target_widget.height() - h) // 2)
                self.overlay_widget.move(x, y)

    window._chart_overlay_filter = ChartOverlayPositionFilter(window.plot_widget, card_empty)

    # Phím tắt toàn cục Ctrl+F5 làm mới biểu đồ và quét lại kết nối MT5 (tránh xung đột với F5 Algo Bot)
    if not hasattr(window, "act_ref") or not window.act_ref:
        shortcut_f5 = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+F5"), window)
        shortcut_f5.activated.connect(lambda: window.draw_and_analyze(getattr(window, "current_sym", "XAUUSD")))
        window.shortcut_f5 = shortcut_f5
    else:
        window.shortcut_f5 = getattr(window, "act_ref", None)

    # Phím tắt toàn cục Esc: Hủy các đường vẽ lệnh nháp và thu gọn Trading Plan drawer
    shortcut_esc = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Escape), window)
    def _on_escape_pressed():
        from frontend.controllers.chart.trading_plan_panel import clear_manual_chart_lines
        clear_manual_chart_lines(window)
        if hasattr(window, "btn_close_plan") and hasattr(window, "frameAIArea") and window.frameAIArea.isVisible():
            window.btn_close_plan.click()
    shortcut_esc.activated.connect(_on_escape_pressed)
    window.shortcut_esc = shortcut_esc

    # Add Crosshair lines
    window.vLine = pg.InfiniteLine(
        angle=90, movable=False, pen=pg.mkPen("#475569", style=QtCore.Qt.DashLine)
    )

    window.hLine = pg.InfiniteLine(
        angle=0, movable=False, pen=pg.mkPen("#475569", style=QtCore.Qt.DashLine),
        label="",
        labelOpts={
            "color": "#f8fafc",
            "position": 0.99,
            "anchors": [(1, 0.5), (1, 0.5)],
            "fill": (15, 23, 42, 230),
            "border": "#475569",
            "movable": False,
        }
    )
    if hasattr(window.hLine, "label") and window.hLine.label:
        window.hLine.label.setFont(pg.Qt.QtGui.QFont("Consolas", 8))

    window.plot_widget.addItem(window.vLine, ignoreBounds=True)
    window.plot_widget.addItem(window.hLine, ignoreBounds=True)

    # Crosshair text label (kept hidden; cursor price is pinned to the right Y-axis on hLine)
    window.crosshair_label = pg.TextItem(
        color="#E5E7EB", anchor=(0, 1), fill=pg.mkBrush(0, 0, 0, 150)
    )
    window.crosshair_label.setZValue(10)  # ensure it's on top
    window.crosshair_label.setVisible(False)
    window.plot_widget.addItem(window.crosshair_label, ignoreBounds=True)

    # Current price line - 1px dashed institutional silver
    window.current_price_line = pg.InfiniteLine(
        angle=0, movable=False, pen=pg.mkPen("#cbd5e1", width=1.0, style=QtCore.Qt.DashLine)
    )
    window.plot_widget.addItem(window.current_price_line, ignoreBounds=True)

    # Institutional Signal Threads: 1px tPOC (#f43f5e) and 1px vPOC (#10b981)
    # Positioned cleanly at right margin (position: 0.98, border: None) so price candlesticks are 100% unobstructed
    lbl_font = pg.Qt.QtGui.QFont("Consolas", 8)

    window.line_tpoc = pg.InfiniteLine(
        angle=0, movable=False,
        pen=pg.mkPen(color="#f43f5e", width=1.0, style=QtCore.Qt.SolidLine),
        label="tPOC",
        labelOpts={
            "color": "#f43f5e", "position": 0.98, "anchors": [(1, 1), (1, 1)],
            "fill": (254, 226, 226, 160) if not is_d_init else (127, 29, 29, 160), "border": None
        }
    )
    if hasattr(window.line_tpoc, "label") and window.line_tpoc.label:
        window.line_tpoc.label.setFont(lbl_font)

    window.line_vpoc = pg.InfiniteLine(
        angle=0, movable=False,
        pen=pg.mkPen(color="#10b981", width=1.0, style=QtCore.Qt.SolidLine),
        label="vPOC",
        labelOpts={
            "color": "#10b981", "position": 0.98, "anchors": [(1, 1), (1, 1)],
            "fill": (220, 252, 231, 160) if not is_d_init else (6, 78, 59, 160), "border": None
        }
    )
    if hasattr(window.line_vpoc, "label") and window.line_vpoc.label:
        window.line_vpoc.label.setFont(lbl_font)

    window.plot_widget.addItem(window.line_tpoc, ignoreBounds=True)
    window.plot_widget.addItem(window.line_vpoc, ignoreBounds=True)

    # Market Profile 70% Value Area Overlay (J. Peter Steidlmayer, CBOT 1985)
    va_brush_init = pg.mkBrush(color=(56, 189, 248, 18))
    window.va_region = pg.LinearRegionItem(
        values=[0, 0], orientation=pg.LinearRegionItem.Horizontal,
        brush=va_brush_init, movable=False
    )
    window.va_region.setZValue(-10)
    for l_reg in window.va_region.lines:
        l_reg.setPen(pg.mkPen(color=(0, 0, 0, 0)))

    c_va_pen = "#38bdf8" if is_d_init else "#0284c7"
    va_fill = (56, 189, 248, 120) if is_d_init else (224, 242, 254, 160)
    window.line_vah = pg.InfiniteLine(
        angle=0, movable=False,
        pen=pg.mkPen(color=c_va_pen, width=1.0, style=QtCore.Qt.DashLine),
        label="VAH (70%)",
        labelOpts={
            "color": c_va_pen, "position": 0.98, "anchors": [(1, 1), (1, 1)],
            "fill": va_fill, "border": None
        }
    )
    if hasattr(window.line_vah, "label") and window.line_vah.label:
        window.line_vah.label.setFont(lbl_font)

    window.line_val = pg.InfiniteLine(
        angle=0, movable=False,
        pen=pg.mkPen(color=c_va_pen, width=1.0, style=QtCore.Qt.DashLine),
        label="VAL (70%)",
        labelOpts={
            "color": c_va_pen, "position": 0.98, "anchors": [(1, 1), (1, 1)],
            "fill": va_fill, "border": None
        }
    )
    if hasattr(window.line_val, "label") and window.line_val.label:
        window.line_val.label.setFont(lbl_font)

    window.plot_widget.addItem(window.va_region, ignoreBounds=True)
    window.plot_widget.addItem(window.line_vah, ignoreBounds=True)
    window.plot_widget.addItem(window.line_val, ignoreBounds=True)

    # Negative-Space Session Metadata Text Item
    window.session_meta_label = pg.TextItem(
        html='<div style="font-family: Consolas, monospace; font-size: 10px; color: #71717a; line-height: 1.3;">'
             '<b>SESSION:</b> <span style="color:#94a3b8;">CME RTH</span> &middot; '
             '<b>TPO:</b> <span style="color:#94a3b8;">370</span> &middot; '
             '<b>VOL:</b> <span style="color:#94a3b8;">2,392k</span> &middot; '
             '<b>Δ:</b> <span style="color:#22c55e;">+14.2k</span><br>'
             '<b>ALGO BIAS:</b> <span style="color:#22c55e; font-weight:bold;">VALUE REJECTION &rarr; LONG</span> '
             '(CONF: <span style="color:#22c55e;">89%</span>)'
             '</div>',
        anchor=(0, 0),
        fill=pg.mkBrush(0, 0, 0, 160)
    )
    window.session_meta_label.setZValue(12)
    # Session metadata is now cleanly presented in the dedicated frameChartRibbon ribbon
    # window.plot_widget.addItem(window.session_meta_label, ignoreBounds=True)

    # On-Chart Trade Management (Interactive Order Lines)
    window.order_proposal_active = False
    window.line_order_entry = pg.InfiniteLine(
        angle=0, movable=False, pos=0.0,
        pen=pg.mkPen(color="#22c55e", width=1.2, style=QtCore.Qt.DashLine),
        label="BUY ORDER: --",
        labelOpts={
            "color": "#f8fafc", "position": 0.92,
            "fill": (15, 23, 42, 235), "border": "#22c55e", "movable": False
        }
    )
    if hasattr(window.line_order_entry, "label") and window.line_order_entry.label:
        window.line_order_entry.label.setFont(pg.Qt.QtGui.QFont("Consolas", 8))

    window.line_order_sl = pg.InfiniteLine(
        angle=0, movable=True, pos=0.0,
        pen=pg.mkPen(color="#ef4444", width=1.0, style=QtCore.Qt.DashLine),
        label="STOP LOSS: --",
        labelOpts={
            "color": "#f8fafc", "position": 0.84,
            "fill": (15, 23, 42, 235), "border": "#ef4444", "movable": False
        }
    )
    if hasattr(window.line_order_sl, "label") and window.line_order_sl.label:
        window.line_order_sl.label.setFont(pg.Qt.QtGui.QFont("Consolas", 8))

    window.line_order_tp = pg.InfiniteLine(
        angle=0, movable=True, pos=0.0,
        pen=pg.mkPen(color="#22c55e", width=1.0, style=QtCore.Qt.DashLine),
        label="TAKE PROFIT: --",
        labelOpts={
            "color": "#f8fafc", "position": 0.76,
            "fill": (15, 23, 42, 235), "border": "#22c55e", "movable": False
        }
    )
    if hasattr(window.line_order_tp, "label") and window.line_order_tp.label:
        window.line_order_tp.label.setFont(pg.Qt.QtGui.QFont("Consolas", 8))

    def _sync_order_metrics():
        if getattr(window, "_plan_mode", "ai") == "manual":
            sym = getattr(window, "current_sym", "XAUUSD").split("\n")[0].strip()
            info = mt5.symbol_info(sym)
            dig = info.digits if info else 2
            sl_p = window.line_order_sl.value()
            tp_p = window.line_order_tp.value()
            order_type_str = getattr(window, "_manual_order_type", "MARKET")
            if order_type_str != "MARKET" and hasattr(window, "line_order_entry") and window.line_order_entry:
                entry_line_p = window.line_order_entry.value()
                if hasattr(window, "spinManualPendingPrice") and window.spinManualPendingPrice:
                    window.spinManualPendingPrice.blockSignals(True)
                    window.spinManualPendingPrice.setValue(round(entry_line_p, dig))
                    window.spinManualPendingPrice.blockSignals(False)
            if hasattr(window, "spinManualSL") and window.spinManualSL:
                window.spinManualSL.blockSignals(True)
                window.spinManualSL.setValue(round(sl_p, dig))
                window.spinManualSL.blockSignals(False)
            if hasattr(window, "spinManualTP") and window.spinManualTP:
                window.spinManualTP.blockSignals(True)
                window.spinManualTP.setValue(round(tp_p, dig))
                window.spinManualTP.blockSignals(False)
            from frontend.controllers.chart.trading_plan_panel import _recalculate_manual_lot_and_rr
            _recalculate_manual_lot_and_rr(window)
            return

        if not getattr(window, "order_proposal_active", False):
            return
        entry_p = window.line_order_entry.value()
        sl_p = window.line_order_sl.value()
        tp_p = window.line_order_tp.value()
        sl_pts = abs(entry_p - sl_p)
        tp_pts = abs(tp_p - entry_p)
        sym = getattr(window, "current_sym", "XAUUSD").split("\n")[0].strip()
        info = mt5.symbol_info(sym)
        dig = info.digits if info else (2 if entry_p > 10 else 5)

        from frontend.controllers.chart.trading_plan_panel import get_symbol_multiplier, calculate_manual_quant_lot
        mult = get_symbol_multiplier(sym, info)

        acc = mt5.account_info() if mt5.terminal_info() is not None else None
        balance = float(acc.balance) if acc and acc.balance > 0 else 10000.0

        is_live = getattr(window, "is_live_position", False)
        is_pending = getattr(window, "is_pending_order", False)
        calc_lot = getattr(window, "active_signal_data", {}).get("lot")
        if not calc_lot or calc_lot <= 0:
            if is_live or is_pending:
                calc_lot = getattr(window, "live_volume", 0.10) or 0.10
            else:
                calc_lot, _ = calculate_manual_quant_lot(sym, sl_pts, balance=balance)

        risk_dlr = round(sl_pts * calc_lot * mult, 2)
        reward_dlr = round(tp_pts * calc_lot * mult, 2)
        risk_pct = round((risk_dlr / balance) * 100.0, 1) if balance > 0 else 1.0
        rr_ratio = round(tp_pts / sl_pts, 1) if sl_pts > 0.00001 else 2.0

        if is_live:
            window.line_order_sl.label.setFormat(f"LIVE SL: {sl_p:.{dig}f}")
            window.line_order_tp.label.setFormat(f"LIVE TP: {tp_p:.{dig}f}")
        else:
            window.line_order_sl.label.setFormat(f"STOP LOSS: {sl_p:.{dig}f} (-${risk_dlr:.2f} | -{risk_pct:.1f}%)")
            window.line_order_tp.label.setFormat(f"TAKE PROFIT: {tp_p:.{dig}f} (+${reward_dlr:.2f} | +{rr_ratio:.1f}R)")

        is_waiting = hasattr(window, "btnApproveOrder") and window.btnApproveOrder.isEnabled()
        update_order_proposal_html(
            window,
            sym=sym,
            has_signal=True,
            signal_type="BUY" if tp_p >= entry_p else "SELL",
            entry=entry_p, sl=sl_p, tp=tp_p,
            risk_dlr=risk_dlr, risk_pct=risk_pct,
            reward_dlr=reward_dlr, rr_ratio=rr_ratio,
            status="UPDATE SL/TP IN MT5" if is_live else ("WAITING OPERATOR APPROVAL" if is_waiting else "EXECUTED & FILLED"),
            digits=dig,
            is_live_position=is_live,
            live_ticket=getattr(window, "live_ticket", None),
            is_pending_order=is_pending,
            pending_ticket=getattr(window, "pending_ticket", None),
        )
        if is_live and hasattr(window, "btnApproveOrder") and window.btnApproveOrder:
            window.btnApproveOrder.setText("UPDATE SL/TP IN MT5")
            window.btnApproveOrder.setEnabled(True)

    window.line_order_entry.sigPositionChanged.connect(lambda: _sync_order_metrics())
    window.line_order_sl.sigPositionChanged.connect(lambda: _sync_order_metrics())
    window.line_order_tp.sigPositionChanged.connect(lambda: _sync_order_metrics())

    def _on_entry_drag_finished(*args):
        if getattr(window, "is_pending_order", False) and getattr(window, "pending_ticket", None):
            tkt = window.pending_ticket
            new_p = window.line_order_entry.value()
            raw_sym = getattr(window, "current_sym", "XAUUSD") or "XAUUSD"
            sym = raw_sym.split("\n")[0].strip()
            sym_info = mt5.symbol_info(sym)
            digits = sym_info.digits if sym_info else (2 if new_p > 10 else 5)
            new_p = round(float(new_p), digits)

            cur_sl = window.line_order_sl.value() if (hasattr(window, "line_order_sl") and window.line_order_sl.isVisible()) else 0.0
            cur_tp = window.line_order_tp.value() if (hasattr(window, "line_order_tp") and window.line_order_tp.isVisible()) else 0.0

            exec_mgr = None
            if hasattr(window, "quant_terminal") and hasattr(window.quant_terminal, "exec_mgr"):
                exec_mgr = window.quant_terminal.exec_mgr
            if not exec_mgr:
                from backend.infrastructure.brokers.execution_manager import ExecutionManager
                exec_mgr = ExecutionManager(slippage=20)

            res = exec_mgr.modify_pending_order(int(tkt), price=new_p, sl=cur_sl, tp=cur_tp)
            from backend.core.event_bus import event_bus
            if res and res.get("status") == "success":
                window.pending_price = new_p
                event_bus.log_event.emit("", "SUCCESS", f"Đã cập nhật giá lệnh chờ #{tkt} sang {new_p:.{digits}f} trên sàn MT5", "#22c55e")
                if hasattr(window, "refresh_active_orders"):
                    window.refresh_active_orders()
            else:
                err = res.get("msg", "Error") if res else "Unknown"
                event_bus.log_event.emit("", "ERROR", f"Không thể sửa giá lệnh chờ #{tkt}: {err}", "#ef4444")
                if hasattr(window, "pending_price") and window.pending_price:
                    window.line_order_entry.setValue(window.pending_price)

    def _on_sl_drag_finished(*args):
        is_live = getattr(window, "is_live_position", False)
        is_pending = getattr(window, "is_pending_order", False)
        if not is_live and not is_pending:
            return

        new_sl = window.line_order_sl.value()
        raw_sym = getattr(window, "current_sym", "XAUUSD") or "XAUUSD"
        sym = raw_sym.split("\n")[0].strip()
        sym_info = mt5.symbol_info(sym)
        digits = sym_info.digits if sym_info else (2 if new_sl > 10 else 5)
        new_sl = round(float(new_sl), digits)

        exec_mgr = None
        if hasattr(window, "quant_terminal") and hasattr(window.quant_terminal, "exec_mgr"):
            exec_mgr = window.quant_terminal.exec_mgr
        if not exec_mgr:
            from backend.infrastructure.brokers.execution_manager import ExecutionManager
            exec_mgr = ExecutionManager(slippage=20)

        from backend.core.event_bus import event_bus
        if is_live and getattr(window, "live_ticket", None):
            tkt = window.live_ticket
            cur_tp = 0.0
            pos_list = mt5.positions_get(ticket=int(tkt))
            if pos_list and len(pos_list) > 0:
                cur_tp = float(pos_list[0].tp)
            elif (int(tkt), "TP") in getattr(window, "chart_order_lines", {}):
                cur_tp = float(window.chart_order_lines[(int(tkt), "TP")].value())
            elif hasattr(window, "line_order_tp") and window.line_order_tp.isVisible():
                cur_tp = float(window.line_order_tp.value())

            res = exec_mgr.modify_position(int(tkt), sl=new_sl, tp=cur_tp)
            if res and res.get("status") == "success":
                event_bus.log_event.emit("", "SUCCESS", f"Đã cập nhật Stop Loss vị thế #{tkt} sang {new_sl:.{digits}f}", "#22c55e")
                if hasattr(window, "refresh_active_orders"):
                    window.refresh_active_orders()
            else:
                err = res.get("msg", "Error") if res else "Unknown"
                event_bus.log_event.emit("", "ERROR", f"Lỗi cập nhật SL vị thế #{tkt}: {err}", "#ef4444")
        elif is_pending and getattr(window, "pending_ticket", None):
            tkt = window.pending_ticket
            cur_price = window.line_order_entry.value()
            cur_tp = 0.0
            ord_list = mt5.orders_get(ticket=int(tkt))
            if ord_list and len(ord_list) > 0:
                cur_tp = float(ord_list[0].tp)
            elif (int(tkt), "TP") in getattr(window, "chart_order_lines", {}):
                cur_tp = float(window.chart_order_lines[(int(tkt), "TP")].value())
            elif hasattr(window, "line_order_tp") and window.line_order_tp.isVisible():
                cur_tp = float(window.line_order_tp.value())

            res = exec_mgr.modify_pending_order(int(tkt), price=cur_price, sl=new_sl, tp=cur_tp)
            if res and res.get("status") == "success":
                event_bus.log_event.emit("", "SUCCESS", f"Đã cập nhật Stop Loss lệnh chờ #{tkt} sang {new_sl:.{digits}f}", "#22c55e")
                if hasattr(window, "refresh_active_orders"):
                    window.refresh_active_orders()
            else:
                err = res.get("msg", "Error") if res else "Unknown"
                event_bus.log_event.emit("", "ERROR", f"Lỗi cập nhật SL lệnh chờ #{tkt}: {err}", "#ef4444")

    def _on_tp_drag_finished(*args):
        is_live = getattr(window, "is_live_position", False)
        is_pending = getattr(window, "is_pending_order", False)
        if not is_live and not is_pending:
            return

        new_tp = window.line_order_tp.value()
        raw_sym = getattr(window, "current_sym", "XAUUSD") or "XAUUSD"
        sym = raw_sym.split("\n")[0].strip()
        sym_info = mt5.symbol_info(sym)
        digits = sym_info.digits if sym_info else (2 if new_tp > 10 else 5)
        new_tp = round(float(new_tp), digits)

        exec_mgr = None
        if hasattr(window, "quant_terminal") and hasattr(window.quant_terminal, "exec_mgr"):
            exec_mgr = window.quant_terminal.exec_mgr
        if not exec_mgr:
            from backend.infrastructure.brokers.execution_manager import ExecutionManager
            exec_mgr = ExecutionManager(slippage=20)

        from backend.core.event_bus import event_bus
        if is_live and getattr(window, "live_ticket", None):
            tkt = window.live_ticket
            cur_sl = 0.0
            pos_list = mt5.positions_get(ticket=int(tkt))
            if pos_list and len(pos_list) > 0:
                cur_sl = float(pos_list[0].sl)
            elif (int(tkt), "SL") in getattr(window, "chart_order_lines", {}):
                cur_sl = float(window.chart_order_lines[(int(tkt), "SL")].value())
            elif hasattr(window, "line_order_sl") and window.line_order_sl.isVisible():
                cur_sl = float(window.line_order_sl.value())

            res = exec_mgr.modify_position(int(tkt), sl=cur_sl, tp=new_tp)
            if res and res.get("status") == "success":
                event_bus.log_event.emit("", "SUCCESS", f"Đã cập nhật Take Profit vị thế #{tkt} sang {new_tp:.{digits}f}", "#22c55e")
                if hasattr(window, "refresh_active_orders"):
                    window.refresh_active_orders()
            else:
                err = res.get("msg", "Error") if res else "Unknown"
                event_bus.log_event.emit("", "ERROR", f"Lỗi cập nhật TP vị thế #{tkt}: {err}", "#ef4444")
        elif is_pending and getattr(window, "pending_ticket", None):
            tkt = window.pending_ticket
            cur_price = window.line_order_entry.value()
            cur_sl = 0.0
            ord_list = mt5.orders_get(ticket=int(tkt))
            if ord_list and len(ord_list) > 0:
                cur_sl = float(ord_list[0].sl)
            elif (int(tkt), "SL") in getattr(window, "chart_order_lines", {}):
                cur_sl = float(window.chart_order_lines[(int(tkt), "SL")].value())
            elif hasattr(window, "line_order_sl") and window.line_order_sl.isVisible():
                cur_sl = float(window.line_order_sl.value())

            res = exec_mgr.modify_pending_order(int(tkt), price=cur_price, sl=cur_sl, tp=new_tp)
            if res and res.get("status") == "success":
                event_bus.log_event.emit("", "SUCCESS", f"Đã cập nhật Take Profit lệnh chờ #{tkt} sang {new_tp:.{digits}f}", "#22c55e")
                if hasattr(window, "refresh_active_orders"):
                    window.refresh_active_orders()
            else:
                err = res.get("msg", "Error") if res else "Unknown"
                event_bus.log_event.emit("", "ERROR", f"Lỗi cập nhật TP lệnh chờ #{tkt}: {err}", "#ef4444")

    window.line_order_entry.sigPositionChangeFinished.connect(_on_entry_drag_finished)
    window.line_order_sl.sigPositionChangeFinished.connect(_on_sl_drag_finished)
    window.line_order_tp.sigPositionChangeFinished.connect(_on_tp_drag_finished)

    # -------------------------------------------------------------------------
    # MULTI-ORDER ON-CHART VISUALIZER & SYNCHRONIZER (MT5 / TradingView Standard)
    # -------------------------------------------------------------------------
    window.chart_order_lines = {}

    def _on_chart_order_line_dragged(target_line):
        tkt = getattr(target_line, "order_ticket", None)
        l_type = getattr(target_line, "order_type", None)
        is_pos = getattr(target_line, "is_position", False)
        sym = getattr(target_line, "order_symbol", getattr(window, "current_sym", "XAUUSD")).split("\n")[0].strip()

        if not tkt or not l_type:
            return

        new_val = target_line.value()
        sym_info = mt5.symbol_info(sym)
        digits = sym_info.digits if sym_info else (2 if new_val > 10 else 5)
        new_val = round(float(new_val), digits)

        exec_mgr = None
        if hasattr(window, "quant_terminal") and hasattr(window.quant_terminal, "exec_mgr"):
            exec_mgr = window.quant_terminal.exec_mgr
        if not exec_mgr:
            from backend.infrastructure.brokers.execution_manager import ExecutionManager
            exec_mgr = ExecutionManager(slippage=20)

        from backend.core.event_bus import event_bus

        if is_pos:
            pos_list = mt5.positions_get(ticket=int(tkt))
            if not pos_list or len(pos_list) == 0:
                sync_chart_orders(window)
                return
            p_obj = pos_list[0]
            cur_sl = float(p_obj.sl)
            cur_tp = float(p_obj.tp)

            if l_type == "SL":
                res = exec_mgr.modify_position(int(tkt), sl=new_val, tp=cur_tp)
                if res and res.get("status") == "success":
                    event_bus.log_event.emit("", "SUCCESS", f"Đã cập nhật Stop Loss vị thế #{tkt} sang {new_val:.{digits}f}", "#22c55e")
                else:
                    err = res.get("msg", "Error") if res else "Unknown"
                    event_bus.log_event.emit("", "ERROR", f"Lỗi cập nhật SL vị thế #{tkt}: {err}", "#ef4444")
            elif l_type == "TP":
                res = exec_mgr.modify_position(int(tkt), sl=cur_sl, tp=new_val)
                if res and res.get("status") == "success":
                    event_bus.log_event.emit("", "SUCCESS", f"Đã cập nhật Take Profit vị thế #{tkt} sang {new_val:.{digits}f}", "#22c55e")
                else:
                    err = res.get("msg", "Error") if res else "Unknown"
                    event_bus.log_event.emit("", "ERROR", f"Lỗi cập nhật TP vị thế #{tkt}: {err}", "#ef4444")
        else:
            ord_list = mt5.orders_get(ticket=int(tkt))
            if not ord_list or len(ord_list) == 0:
                sync_chart_orders(window)
                return
            o_obj = ord_list[0]
            cur_p = float(o_obj.price_open)
            cur_sl = float(o_obj.sl)
            cur_tp = float(o_obj.tp)

            if l_type == "ENTRY":
                res = exec_mgr.modify_pending_order(int(tkt), price=new_val, sl=cur_sl, tp=cur_tp)
                if res and res.get("status") == "success":
                    event_bus.log_event.emit("", "SUCCESS", f"Đã cập nhật giá lệnh chờ #{tkt} sang {new_val:.{digits}f} trên sàn MT5", "#22c55e")
                else:
                    err = res.get("msg", "Error") if res else "Unknown"
                    event_bus.log_event.emit("", "ERROR", f"Không thể sửa giá lệnh chờ #{tkt}: {err}", "#ef4444")
            elif l_type == "SL":
                res = exec_mgr.modify_pending_order(int(tkt), price=cur_p, sl=new_val, tp=cur_tp)
                if res and res.get("status") == "success":
                    event_bus.log_event.emit("", "SUCCESS", f"Đã cập nhật Stop Loss lệnh chờ #{tkt} sang {new_val:.{digits}f}", "#22c55e")
                else:
                    err = res.get("msg", "Error") if res else "Unknown"
                    event_bus.log_event.emit("", "ERROR", f"Lỗi cập nhật SL lệnh chờ #{tkt}: {err}", "#ef4444")
            elif l_type == "TP":
                res = exec_mgr.modify_pending_order(int(tkt), price=cur_p, sl=cur_sl, tp=new_val)
                if res and res.get("status") == "success":
                    event_bus.log_event.emit("", "SUCCESS", f"Đã cập nhật Take Profit lệnh chờ #{tkt} sang {new_val:.{digits}f}", "#22c55e")
                else:
                    err = res.get("msg", "Error") if res else "Unknown"
                    event_bus.log_event.emit("", "ERROR", f"Lỗi cập nhật TP lệnh chờ #{tkt}: {err}", "#ef4444")

        sync_chart_orders(window)

    def sync_chart_orders(win=window):
        """
        Real-time synchronization of all MT5 active positions and pending orders for current symbol onto chart canvas.
        Institutes standard MT5 / TradingView multi-order visualizer with drag-and-drop modification and order context menu.
        """
        if not hasattr(win, "plot_widget") or not win.plot_widget:
            return

        clean_sym = getattr(win, "current_sym", "").split("\n")[0].strip()
        if not clean_sym:
            return

        if not hasattr(win, "chart_order_lines"):
            win.chart_order_lines = {}

        if mt5.terminal_info() is None:
            for k, l_obj in list(win.chart_order_lines.items()):
                try:
                    win.plot_widget.removeItem(l_obj)
                except Exception:
                    pass
            win.chart_order_lines.clear()
            return

        info = mt5.symbol_info(clean_sym)
        digits = info.digits if info else (2 if "JPY" in clean_sym or "XAU" in clean_sym else 5)

        is_dark = getattr(win, "is_dark_theme", True)
        bull_color = "#22c55e" if is_dark else "#15803d"
        bear_color = "#ef4444" if is_dark else "#dc2626"

        base_sym = clean_sym.split(".")[0].split("+")[0].upper()

        pos_raw = mt5.positions_get(symbol=clean_sym)
        if pos_raw is None or len(pos_raw) == 0:
            all_p = mt5.positions_get() or []
            positions = [p for p in all_p if getattr(p, "symbol", "").split(".")[0].split("+")[0].upper() == base_sym]
        else:
            positions = list(pos_raw)

        ord_raw = mt5.orders_get(symbol=clean_sym)
        if ord_raw is None or len(ord_raw) == 0:
            all_o = mt5.orders_get() or []
            pending_orders = [o for o in all_o if getattr(o, "symbol", "").split(".")[0].split("+")[0].upper() == base_sym]
        else:
            pending_orders = list(ord_raw)

        active_keys = set()

        if positions:
            win.is_live_position = True
            win.live_ticket = positions[0].ticket
        elif not getattr(win, "is_pending_order", False):
            win.is_live_position = False

        if pending_orders:
            win.is_pending_order = True
            win.pending_ticket = pending_orders[0].ticket
        elif not getattr(win, "is_live_position", False):
            win.is_pending_order = False

        def _upsert_line(key, price, color, style, label_str, movable, tkt, l_type, is_pos, action_str, vol, pos_ratio, border_color=None, entry_p=None):
            active_keys.add(key)
            border_c = border_color or color
            ref_entry = entry_p if entry_p is not None else price
            if key in win.chart_order_lines:
                line = win.chart_order_lines[key]
                line.order_ticket = tkt
                line.order_type = l_type
                line.is_position = is_pos
                line.order_action = action_str
                line.order_vol = vol
                line.order_symbol = clean_sym
                line.order_entry_price = ref_entry
                if not getattr(line, "is_dragging", False):
                    line.setValue(price)
                    line.setPen(pg.mkPen(color=color, width=1.2, style=style))
                    line.setMovable(movable)
                    if hasattr(line, "label") and line.label:
                        line.label.setFormat(label_str)
                        line.label.setColor("#f8fafc")
                        line.label.fill = pg.mkBrush(15, 23, 42, 235)
                        line.label.border = pg.mkPen(color=border_c, width=1.0)
                        line.label.setPosition(pos_ratio)
                        line.label.setFont(pg.Qt.QtGui.QFont("Consolas", 8))
                    if line not in win.plot_widget.items():
                        win.plot_widget.addItem(line, ignoreBounds=True)
            else:
                line = pg.InfiniteLine(
                    angle=0,
                    movable=movable,
                    pos=price,
                    pen=pg.mkPen(color=color, width=1.2, style=style),
                    label=label_str,
                    labelOpts={
                        "color": "#f8fafc",
                        "position": pos_ratio,
                        "fill": (15, 23, 42, 235),
                        "border": border_c,
                        "movable": False
                    }
                )
                if hasattr(line, "label") and line.label:
                    line.label.setFont(pg.Qt.QtGui.QFont("Consolas", 8))
                line.order_ticket = tkt
                line.order_type = l_type
                line.is_position = is_pos
                line.order_action = action_str
                line.order_vol = vol
                line.order_symbol = clean_sym
                line.order_entry_price = ref_entry
                line.is_dragging = False

                def _on_drag_change(*args, l_ref=line):
                    l_ref.is_dragging = True
                    try:
                        cur_v = float(l_ref.value())
                        ref_e = getattr(l_ref, "order_entry_price", cur_v)
                        t_type = getattr(l_ref, "order_type", "")
                        v_lots = getattr(l_ref, "order_vol", 0.01)
                        s_tkt = str(getattr(l_ref, "order_ticket", ""))[-4:]
                        act = getattr(l_ref, "order_action", "buy").lower()
                        is_b = ("buy" in act)

                        sym_info_loc = mt5.symbol_info(clean_sym)
                        dig_loc = sym_info_loc.digits if sym_info_loc else digits
                        pt_loc = sym_info_loc.point if sym_info_loc and sym_info_loc.point > 0 else 0.01
                        pip_unit_loc = pt_loc * 10.0 if ("JPY" in clean_sym or "XAU" in clean_sym or dig_loc in (3, 5)) else pt_loc

                        from frontend.controllers.chart.trading_plan_panel import get_symbol_multiplier
                        mult_loc = get_symbol_multiplier(clean_sym, sym_info_loc)

                        if t_type in ("SL", "TP"):
                            pips_diff = (cur_v - ref_e) / pip_unit_loc if is_b else (ref_e - cur_v) / pip_unit_loc
                            dlr_pnl = ((cur_v - ref_e) if is_b else (ref_e - cur_v)) * mult_loc * v_lots
                            sign_pnl = f"+${dlr_pnl:,.2f}" if dlr_pnl >= 0 else f"-${abs(dlr_pnl):,.2f}"
                            hud_text = f"{t_type} #{s_tkt} | {sign_pnl} ({pips_diff:+.1f} pips) @ {cur_v:.{dig_loc}f}"
                            if hasattr(l_ref, "label") and l_ref.label:
                                l_ref.label.setFormat(hud_text)
                                l_ref.label.setColor("#38bdf8" if dlr_pnl >= 0 else "#f87171")
                        elif t_type == "ENTRY":
                            diff_pts = (cur_v - ref_e) / pt_loc if pt_loc > 0 else 0.0
                            hud_text = f"ENTRY #{s_tkt} | {cur_v:.{dig_loc}f} ({diff_pts:+.0f} pts)"
                            if hasattr(l_ref, "label") and l_ref.label:
                                l_ref.label.setFormat(hud_text)
                                l_ref.label.setColor("#38bdf8")
                    except Exception as e_drag:
                        logger.debug(f"[ChartCanvas] Drag HUD calculation error: {e_drag}")

                def _on_drag_finish(*args, l_ref=line):
                    l_ref.is_dragging = False
                    _on_chart_order_line_dragged(l_ref)

                line.sigPositionChanged.connect(_on_drag_change)
                line.sigPositionChangeFinished.connect(_on_drag_finish)

                win.plot_widget.addItem(line, ignoreBounds=True)
                win.chart_order_lines[key] = line

        # 1. Process Live Positions (Solid Line, Pinned to Right Margin)
        for p in positions:
            tkt = int(p.ticket)
            vol = float(p.volume)
            open_p = float(p.price_open)
            sl = float(p.sl)
            tp = float(p.tp)
            is_buy = (p.type == 0)

            # Live Trailing Stop Engine Execution
            if hasattr(win, "_active_trailing_stops") and tkt in win._active_trailing_stops:
                try:
                    pts_trail = win._active_trailing_stops[tkt]
                    pt_val = info.point if info and info.point > 0 else 0.01
                    trail_dist = pts_trail * pt_val
                    cur_market_p = float(getattr(p, "price_current", open_p))
                    if is_buy:
                        target_sl = round(cur_market_p - trail_dist, digits)
                        if target_sl > open_p and (sl <= 0.00001 or target_sl > sl + (5 * pt_val)):
                            exec_mgr = getattr(getattr(win, "quant_terminal", None), "exec_mgr", None)
                            if not exec_mgr:
                                from backend.infrastructure.brokers.execution_manager import ExecutionManager
                                exec_mgr = ExecutionManager(slippage=20)
                            res_tr = exec_mgr.modify_position(tkt, sl=target_sl, tp=tp)
                            if res_tr and res_tr.get("status") == "success":
                                sl = target_sl
                    else:
                        target_sl = round(cur_market_p + trail_dist, digits)
                        if target_sl < open_p and (sl <= 0.00001 or target_sl < sl - (5 * pt_val)):
                            exec_mgr = getattr(getattr(win, "quant_terminal", None), "exec_mgr", None)
                            if not exec_mgr:
                                from backend.infrastructure.brokers.execution_manager import ExecutionManager
                                exec_mgr = ExecutionManager(slippage=20)
                            res_tr = exec_mgr.modify_position(tkt, sl=target_sl, tp=tp)
                            if res_tr and res_tr.get("status") == "success":
                                sl = target_sl
                except Exception as e_tr:
                    logger.debug(f"[ChartCanvas] Trailing Stop update error: {e_tr}")

            act_name = "buy" if is_buy else "sell"
            dir_c = bull_color if is_buy else bear_color
            short_tkt = str(tkt)[-4:]

            # Position Entry Line (solid, not movable)
            _upsert_line(
                key=(tkt, "ENTRY"),
                price=open_p,
                color=dir_c,
                style=QtCore.Qt.SolidLine,
                label_str=f"POS #{short_tkt} | {act_name.upper()} {vol:.2f}L @ {open_p:.{digits}f}",
                movable=False,
                tkt=tkt,
                l_type="ENTRY",
                is_pos=True,
                action_str=act_name,
                vol=vol,
                pos_ratio=0.92,
                border_color=dir_c,
                entry_p=open_p
            )

            # Position SL Line (dashed, movable)
            if sl > 0:
                _upsert_line(
                    key=(tkt, "SL"),
                    price=sl,
                    color=bear_color,
                    style=QtCore.Qt.DashLine,
                    label_str=f"SL #{short_tkt} | {sl:.{digits}f}",
                    movable=True,
                    tkt=tkt,
                    l_type="SL",
                    is_pos=True,
                    action_str=act_name,
                    vol=vol,
                    pos_ratio=0.84,
                    border_color=bear_color,
                    entry_p=open_p
                )

            # Position TP Line (dashed, movable)
            if tp > 0:
                _upsert_line(
                    key=(tkt, "TP"),
                    price=tp,
                    color=bull_color,
                    style=QtCore.Qt.DashLine,
                    label_str=f"TP #{short_tkt} | {tp:.{digits}f}",
                    movable=True,
                    tkt=tkt,
                    l_type="TP",
                    is_pos=True,
                    action_str=act_name,
                    vol=vol,
                    pos_ratio=0.76,
                    border_color=bull_color,
                    entry_p=open_p
                )

        # 2. Process Pending Orders (Uniform DashLine, Pinned to Right Margin)
        for o in pending_orders:
            tkt = int(o.ticket)
            vol = float(o.volume_initial or o.volume_current)
            open_p = float(o.price_open)
            sl = float(o.sl)
            tp = float(o.tp)
            ord_type = o.type
            if ord_type == mt5.ORDER_TYPE_BUY_LIMIT:
                act_name = "buy limit"
                dir_c = bull_color
            elif ord_type == mt5.ORDER_TYPE_SELL_LIMIT:
                act_name = "sell limit"
                dir_c = bear_color
            elif ord_type == mt5.ORDER_TYPE_BUY_STOP:
                act_name = "buy stop"
                dir_c = bull_color
            else:
                act_name = "sell stop"
                dir_c = bear_color
            short_tkt = str(tkt)[-4:]

            # Pending Entry Line (Uniform DashLine for all pending orders, movable=True)
            _upsert_line(
                key=(tkt, "ENTRY"),
                price=open_p,
                color=dir_c,
                style=QtCore.Qt.DashLine,
                label_str=f"{act_name.upper()} | {vol:.2f}L @ {open_p:.{digits}f} (#{short_tkt})",
                movable=True,
                tkt=tkt,
                l_type="ENTRY",
                is_pos=False,
                action_str=act_name,
                vol=vol,
                pos_ratio=0.92,
                border_color=dir_c,
                entry_p=open_p
            )

            # Pending SL Line (dashed, movable)
            if sl > 0:
                _upsert_line(
                    key=(tkt, "SL"),
                    price=sl,
                    color=bear_color,
                    style=QtCore.Qt.DashLine,
                    label_str=f"SL (#{short_tkt}) | {sl:.{digits}f}",
                    movable=True,
                    tkt=tkt,
                    l_type="SL",
                    is_pos=False,
                    action_str=act_name,
                    vol=vol,
                    pos_ratio=0.84,
                    border_color=bear_color,
                    entry_p=open_p
                )

            # Pending TP Line (dashed, movable)
            if tp > 0:
                _upsert_line(
                    key=(tkt, "TP"),
                    price=tp,
                    color=bull_color,
                    style=QtCore.Qt.DashLine,
                    label_str=f"TP (#{short_tkt}) | {tp:.{digits}f}",
                    movable=True,
                    tkt=tkt,
                    l_type="TP",
                    is_pos=False,
                    action_str=act_name,
                    vol=vol,
                    pos_ratio=0.76,
                    border_color=bull_color,
                    entry_p=open_p
                )

        # 3. Clean up lines whose orders are no longer active in MT5
        for key in list(win.chart_order_lines.keys()):
            if key not in active_keys:
                l_obj = win.chart_order_lines.pop(key)
                try:
                    win.plot_widget.removeItem(l_obj)
                except Exception:
                    pass

    window.sync_chart_orders = lambda: sync_chart_orders(window)
    window.refresh_active_orders = lambda: sync_chart_orders(window)


    def _on_approve():
        if not getattr(window, "order_proposal_active", False):
            return

        # Neu la vi the dang chay tren MT5 -> Cap nhat SL/TP vao MT5
        if getattr(window, "is_live_position", False) and getattr(window, "live_ticket", None):
            ticket = window.live_ticket
            new_sl = window.line_order_sl.value()
            new_tp = window.line_order_tp.value()
            exec_mgr = None
            if hasattr(window, "quant_terminal") and hasattr(window.quant_terminal, "exec_mgr"):
                exec_mgr = window.quant_terminal.exec_mgr
            if not exec_mgr:
                from backend.infrastructure.brokers.execution_manager import ExecutionManager
                exec_mgr = ExecutionManager(slippage=20)
            res = exec_mgr.modify_position(ticket, new_sl, new_tp)
            from backend.core.event_bus import event_bus
            if res and res.get("status") == "success":
                window.btnApproveOrder.setText("SL/TP UPDATED")
                window.btnApproveOrder.setEnabled(False)
                event_bus.log_event.emit("", "SUCCESS", f"Live position #{ticket} SL/TP updated: SL={new_sl:.2f}, TP={new_tp:.2f}", "#10b981")
            else:
                window.btnApproveOrder.setText("UPDATE FAILED")
                event_bus.log_event.emit("", "ERROR", f"Failed to modify #{ticket}: {res.get('msg', 'Error')}", "#ef4444")
            return

        entry_p = window.line_order_entry.value()
        sl_p = window.line_order_sl.value()
        tp_p = window.line_order_tp.value()
        sl_pts = abs(entry_p - sl_p)
        tp_pts = abs(tp_p - entry_p)
        sym = getattr(window, "current_sym", "XAUUSD").split("\n")[0].strip()
        info = mt5.symbol_info(sym)
        dig = info.digits if info else (2 if entry_p > 10 else 5)

        from frontend.controllers.chart.trading_plan_panel import get_symbol_multiplier, calculate_manual_quant_lot
        mult = get_symbol_multiplier(sym, info)

        acc = mt5.account_info() if mt5.terminal_info() is not None else None
        balance = float(acc.balance) if acc and acc.balance > 0 else 10000.0

        # Determine direction
        is_buy = True
        if hasattr(window, "lblOrderTypeBadge") and "SELL" in window.lblOrderTypeBadge.text().upper():
            is_buy = False
        elif tp_p < entry_p:
            is_buy = False

        # Validate stop loss orientation before MT5 submission
        if is_buy and sl_p >= entry_p:
            from backend.core.event_bus import event_bus
            event_bus.log_event.emit("", "ERROR", f"Cannot approve BUY order: Stop Loss ({sl_p:.{dig}f}) must be below Entry ({entry_p:.{dig}f}).", "#ef4444")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(window, "Invalid Stop Loss", f"Stop Loss ({sl_p:.{dig}f}) must be below Entry price ({entry_p:.{dig}f}) for a BUY order.")
            return
        elif not is_buy and sl_p <= entry_p:
            from backend.core.event_bus import event_bus
            event_bus.log_event.emit("", "ERROR", f"Cannot approve SELL order: Stop Loss ({sl_p:.{dig}f}) must be above Entry ({entry_p:.{dig}f}).", "#ef4444")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(window, "Invalid Stop Loss", f"Stop Loss ({sl_p:.{dig}f}) must be above Entry price ({entry_p:.{dig}f}) for a SELL order.")
            return

        # Calculate lot size from active_signal_data or dynamic risk math
        lot_size = getattr(window, "active_signal_data", {}).get("lot")
        if not lot_size or lot_size <= 0:
            if hasattr(window, "lblSizeVal") and window.lblSizeVal:
                try:
                    lot_size = float(window.lblSizeVal.text().split()[0])
                except Exception:
                    pass
        if not lot_size or lot_size <= 0:
            lot_size, _ = calculate_manual_quant_lot(sym, sl_pts, balance=balance)

        # Execute on MT5 via ExecutionManager
        exec_mgr = None
        if hasattr(window, "quant_terminal") and hasattr(window.quant_terminal, "exec_mgr"):
            exec_mgr = window.quant_terminal.exec_mgr
        if not exec_mgr:
            from backend.infrastructure.brokers.execution_manager import ExecutionManager
            exec_mgr = ExecutionManager(slippage=20)

        order_res = None
        if mt5.terminal_info() is not None:
            order_res = exec_mgr.execute_market_order(
                symbol=sym,
                is_buy=is_buy,
                volume=lot_size,
                sl_price=sl_p,
                tp_price=tp_p,
                comment="ICT_Strategy"
            )

        from backend.core.event_bus import event_bus
        side_str = "BUY" if is_buy else "SELL"
        if order_res and order_res.get("status") == "success":
            ticket = order_res.get("ticket", "OK")
            window.btnApproveOrder.setText(f"FILLED #{ticket}")
            window.btnApproveOrder.setEnabled(False)
            if hasattr(window, "lblSignalExpiry"):
                window.lblSignalExpiry.setText(f"STATUS: FILLED #{ticket}")
                window.lblSignalExpiry.setStyleSheet("color: #10b981; font-family: 'Consolas', monospace; font-size: 9.5px; font-weight: bold;")
            event_bus.log_event.emit("", "SUCCESS", f"Order filled: {side_str} {lot_size:.2f} lots {sym} #{ticket}", "#10b981")
            window.order_proposal_active = False
            for l_name in ("line_order_entry", "line_order_sl", "line_order_tp"):
                if hasattr(window, l_name):
                    l_obj = getattr(window, l_name)
                    if l_obj is not None:
                        try:
                            l_obj.setVisible(False)
                        except Exception as err:
                            logger.debug(f"[ChartCanvas] Line hide error: {err}")
                        try:
                            window.plot_widget.removeItem(l_obj)
                        except Exception as err:
                            logger.debug(f"[ChartCanvas] Line remove error: {err}")
            # Refresh live blotter in terminal
            if hasattr(window, "quant_terminal") and hasattr(window.quant_terminal, "blotter_buttons"):
                qt = window.quant_terminal
                if "active" in qt.blotter_buttons:
                    qt.blotter_buttons["active"].click()
        elif order_res and order_res.get("status") == "error":
            err_msg = order_res.get("msg", "Rejected")
            ret_code = order_res.get("retcode", 0)
            window.btnApproveOrder.setText("RETRY APPROVAL")
            window.btnApproveOrder.setEnabled(True)
            if hasattr(window, "lblSignalExpiry"):
                window.lblSignalExpiry.setText(f"REJECTED: {err_msg[:24]}")
                window.lblSignalExpiry.setStyleSheet("color: #ef4444; font-family: 'Consolas', monospace; font-size: 9.5px; font-weight: bold;")
            event_bus.log_event.emit("", "ERROR", f"MT5 execution error: {err_msg}", "#ef4444")

            if ret_code == 10027 or "autotrading" in err_msg.lower() or "algo trading" in err_msg.lower():
                from PySide6.QtWidgets import QMessageBox
                msg_box = QMessageBox(window)
                msg_box.setWindowTitle("MT5: Algo Trading Disabled")
                msg_box.setIcon(QMessageBox.Warning)
                msg_box.setText(
                    "<b>MetaTrader 5 Algo Trading is disabled!</b><br><br>"
                    "To route orders into MT5 successfully, please:<br>"
                    "1. Open the <b>MetaTrader 5</b> application window.<br>"
                    "2. Press <b>Ctrl + E</b> (or toggle the <b>Algo Trading</b> button on MT5 toolbar to green).<br><br>"
                    "Then click <b>'RETRY APPROVAL'</b> in the terminal to resubmit."
                )
                msg_box.exec()
        else:
            # Paper trading / MT5 disconnected
            window.btnApproveOrder.setText("SIMULATED")
            window.btnApproveOrder.setEnabled(False)
            if hasattr(window, "lblSignalExpiry"):
                window.lblSignalExpiry.setText("STATUS: SIMULATED")
                window.lblSignalExpiry.setStyleSheet("color: #10b981; font-family: 'Consolas', monospace; font-size: 9.5px; font-weight: bold;")
            event_bus.log_event.emit("", "SUCCESS", f"Simulated execution: {side_str} {lot_size:.2f} lots {sym} @ {entry_p:.{dig}f}", "#10b981")
            window.order_proposal_active = False
            for l_name in ("line_order_entry", "line_order_sl", "line_order_tp"):
                if hasattr(window, l_name):
                    l_obj = getattr(window, l_name)
                    if l_obj is not None:
                        try:
                            l_obj.setVisible(False)
                        except Exception as err:
                            logger.debug(f"[ChartCanvas] Line hide error: {err}")
                        try:
                            window.plot_widget.removeItem(l_obj)
                        except Exception as err:
                            logger.debug(f"[ChartCanvas] Line remove error: {err}")

    def _on_modify():
        ticket = getattr(window, "live_ticket", None) or getattr(window, "pending_ticket", None)
        is_pos = getattr(window, "is_live_position", False)
        is_pend = getattr(window, "is_pending_order", False)

        # For live positions or pending orders, switch to MANUAL ORDER copilot prefilled
        if is_pos or is_pend:
            from frontend.controllers.chart.trading_plan_panel import populate_manual_order_for_modification
            if ticket:
                if is_pos:
                    p_pos = mt5.positions_get(ticket=int(ticket))
                    if p_pos and len(p_pos) > 0:
                        ps = p_pos[0]
                        act = "BUY" if ps.type == 0 else "SELL"
                        populate_manual_order_for_modification(
                            window, ticket, act, float(ps.volume), float(ps.price_open),
                            sl=float(ps.sl), tp=float(ps.tp), is_position=True
                        )
                        return
                else:
                    p_ord = mt5.orders_get(ticket=int(ticket))
                    if p_ord and len(p_ord) > 0:
                        po = p_ord[0]
                        act = "BUY LIMIT" if po.type == mt5.ORDER_TYPE_BUY_LIMIT else (
                            "SELL LIMIT" if po.type == mt5.ORDER_TYPE_SELL_LIMIT else (
                                "BUY STOP" if po.type == mt5.ORDER_TYPE_BUY_STOP else "SELL STOP"
                            )
                        )
                        populate_manual_order_for_modification(
                            window, ticket, act, float(po.volume_initial or po.volume_current), float(po.price_open),
                            sl=float(po.sl), tp=float(po.tp), is_position=False
                        )
                        return
            if hasattr(window, "_switch_plan_mode"):
                window._switch_plan_mode("manual")
            elif hasattr(window, "btnPlanModeManual"):
                window.btnPlanModeManual.click()
            return

        # Draft unapproved AI proposal adjustment
        if hasattr(window, "line_order_entry"):
            window.line_order_entry.setMovable(True)
        if hasattr(window, "line_order_sl"):
            window.line_order_sl.setMovable(True)
        if hasattr(window, "line_order_tp"):
            window.line_order_tp.setMovable(True)
        if hasattr(window, "lblSignalExpiry"):
            window.lblSignalExpiry.setText("DRAG SL/TP LINES TO ADJUST")
            window.lblSignalExpiry.setStyleSheet("color: #0284c7; font-family: 'Consolas', monospace; font-size: 9.5px; font-weight: bold;")
        if hasattr(window, "btnApproveOrder"):
            window.btnApproveOrder.setText("APPROVE ORDER (MODIFIED)")
            window.btnApproveOrder.setEnabled(True)

    def _on_discard():
        if getattr(window, "is_live_position", False) and getattr(window, "live_ticket", None):
            ticket = window.live_ticket
            from PySide6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                window,
                "Close Position",
                f"Close active MT5 position #{ticket} immediately?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                exec_mgr = None
                if hasattr(window, "quant_terminal") and hasattr(window.quant_terminal, "exec_mgr"):
                    exec_mgr = window.quant_terminal.exec_mgr
                if not exec_mgr:
                    from backend.infrastructure.brokers.execution_manager import ExecutionManager
                    exec_mgr = ExecutionManager(slippage=20)
                res = exec_mgr.close_position(ticket)
                from backend.core.event_bus import event_bus
                if res and res.get("status") == "success":
                    event_bus.log_event.emit("", "SUCCESS", f"Closed MT5 position #{ticket}", "#10b981")
                    window.is_live_position = False
                    window.live_ticket = None
                    clean_sym = getattr(window, "current_sym", "XAUUSD").split("\n")[0].strip()
                    from frontend.controllers.chart.ai_panel_controller import _run_analysis
                    _run_analysis(window, clean_sym, force=True)
                else:
                    event_bus.log_event.emit("", "ERROR", f"Failed to close #{ticket}: {res.get('msg', 'Error')}", "#ef4444")
            return

        if getattr(window, "is_pending_order", False) and getattr(window, "pending_ticket", None):
            ticket = window.pending_ticket
            from PySide6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                window,
                "Cancel Pending Order",
                f"Cancel pending MT5 order #{ticket} immediately?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                exec_mgr = None
                if hasattr(window, "quant_terminal") and hasattr(window.quant_terminal, "exec_mgr"):
                    exec_mgr = window.quant_terminal.exec_mgr
                if not exec_mgr:
                    from backend.infrastructure.brokers.execution_manager import ExecutionManager
                    exec_mgr = ExecutionManager(slippage=20)
                res = exec_mgr.cancel_pending_order(ticket)
                from backend.core.event_bus import event_bus
                if res and res.get("status") == "success":
                    event_bus.log_event.emit("", "SUCCESS", f"Cancelled MT5 pending order #{ticket}", "#10b981")
                    window.is_pending_order = False
                    window.pending_ticket = None
                    clean_sym = getattr(window, "current_sym", "XAUUSD").split("\n")[0].strip()
                    from frontend.controllers.chart.ai_panel_controller import _run_analysis
                    _run_analysis(window, clean_sym, force=True)
                else:
                    event_bus.log_event.emit("", "ERROR", f"Failed to cancel #{ticket}: {res.get('msg', 'Error')}", "#ef4444")
            return

        window.order_proposal_active = False
        for l_name in ("line_order_entry", "line_order_sl", "line_order_tp"):
            if hasattr(window, l_name):
                l_obj = getattr(window, l_name)
                if l_obj is not None:
                    try:
                        l_obj.setVisible(False)
                    except Exception as err:
                        logger.debug(f"[ChartCanvas] Line hide error: {err}")
                    try:
                        window.plot_widget.removeItem(l_obj)
                    except Exception as err:
                        logger.debug(f"[ChartCanvas] Line remove error: {err}")
        if hasattr(window, "_active_proposal_sig") and window._active_proposal_sig:
            if not hasattr(window, "_discarded_signals"):
                window._discarded_signals = set()
            window._discarded_signals.add(window._active_proposal_sig)

        if hasattr(window, "btnApproveOrder"):
            window.btnApproveOrder.setEnabled(False)
            window.btnApproveOrder.setText("DISCARDED")
        if hasattr(window, "btnDiscardOrder"):
            window.btnDiscardOrder.setText("STANDBY")
            window.btnDiscardOrder.setEnabled(False)
        if hasattr(window, "lblSignalExpiry"):
            window.lblSignalExpiry.setText("STATUS: SCANNING MARKET")
            window.lblSignalExpiry.setStyleSheet("color: #71717a; font-family: 'Consolas', monospace; font-size: 9.5px;")
        if hasattr(window, "barSignalExpiry"):
            window.barSignalExpiry.setValue(0)
        if hasattr(window, "_signal_expiry_timer") and window._signal_expiry_timer:
            window._signal_expiry_timer.stop()
        from backend.core.event_bus import event_bus
        event_bus.log_event.emit("", "WARN", "Order proposal cancelled by user.", "#64748b")

    if hasattr(window, "btnApproveOrder"):
        window.btnApproveOrder.clicked.connect(_on_approve)
    if hasattr(window, "btnDiscardOrder"):
        window.btnDiscardOrder.clicked.connect(_on_discard)
    if hasattr(window, "btnModifyOrder"):
        window.btnModifyOrder.clicked.connect(_on_modify)

    def mouseMoved(evt):

        pos = evt

        if window.plot_widget.sceneBoundingRect().contains(pos):

            mousePoint = window.plot_widget.plotItem.vb.mapSceneToView(pos)

            x = mousePoint.x()

            y = mousePoint.y()

            if hasattr(window, "chart_data_list") and window.chart_data_list:

                idx = int(round(x))

                if 0 <= idx < len(window.chart_data_list):

                    t_val = window.time_axis.timestamps[idx]

                    dt_str = timezone_manager.format_mt5_ts(t_val)

                    data = window.chart_data_list[idx]

                    o, c, l, h = data[1], data[2], data[3], data[4]
                    fmt = ".5f" if o < 10 else (".2f" if o > 500 else ".3f")
                    chg_pct = ((c - o) / o) * 100.0 if o > 0 else 0.0
                    chg_clr = "#22c55e" if chg_pct >= 0 else "#ef4444"
                    sign = "+" if chg_pct >= 0 else ""

                    if hasattr(window, "lbl_chart_ohlc") and window.lbl_chart_ohlc:
                        is_d = getattr(window, "is_dark_theme", False)
                        txt_val = "#f8fafc" if is_d else "#0f172a"
                        txt_lbl = "#64748b" if is_d else "#94a3b8"
                        window.lbl_chart_ohlc.setText(
                            f'<span style="font-family:Consolas, monospace; font-size:9.5px; color:{txt_lbl};">'
                            f'{dt_str} &nbsp;&nbsp;'
                            f'O: <b style="color:{txt_val};">{o:{fmt}}</b> &nbsp;&nbsp;'
                            f'H: <b style="color:{txt_val};">{h:{fmt}}</b> &nbsp;&nbsp;'
                            f'L: <b style="color:{txt_val};">{l:{fmt}}</b> &nbsp;&nbsp;'
                            f'C: <b style="color:{txt_val};">{c:{fmt}}</b> &nbsp;&nbsp;'
                            f'<b style="color:{chg_clr};">{sign}{chg_pct:.2f}%</b>'
                            f'</span>'
                        )

                    vb = window.plot_widget.getViewBox()
                    y_min, y_max = vb.viewRange()[1]
                    y_span = y_max - y_min
                    if y_span > 0:
                        y_margin = y_span * 0.045
                        label_y = max(y_min + y_margin, min(y, y_max - y_margin))
                    else:
                        label_y = y

                    # Crosshair price pinned to Y-axis on the right margin (never floating mid-canvas)
                    if hasattr(window, "hLine") and hasattr(window.hLine, "label") and window.hLine.label:
                        window.hLine.label.setFormat(f"{y:{fmt}}")
                    window.crosshair_label.setVisible(False)

            is_cross_mode = True
            if hasattr(window, "drawing_engine") and window.drawing_engine:
                is_cross_mode = (window.drawing_engine.mode == ChartDrawingEngine.MODE_CROSSHAIR)

            if getattr(window, "_crosshair_enabled", True) and is_cross_mode:
                window.vLine.setPos(x)
                window.hLine.setPos(y)
                window.vLine.setVisible(True)
                window.hLine.setVisible(True)
            else:
                window.vLine.setVisible(False)
                window.hLine.setVisible(False)
            window.crosshair_label.setVisible(False)

    window.plot_widget.scene().sigMouseMoved.connect(mouseMoved)

    # Interactive canvas click dismissal for draft preview order lines
    def _on_chart_scene_clicked(ev):
        try:
            from pyqtgraph.Qt import QtCore
            if ev.button() != QtCore.Qt.MouseButton.LeftButton:
                return
            if getattr(window, "_plan_mode", "ai") != "manual":
                return
            if not getattr(window, "_show_manual_preview", True):
                return
            if getattr(window, "is_live_position", False) or getattr(window, "is_pending_order", False):
                return

            for l_attr in ("line_order_entry", "line_order_sl", "line_order_tp"):
                if hasattr(window, l_attr):
                    l_obj = getattr(window, l_attr)
                    if l_obj and hasattr(l_obj, "label") and l_obj.label and l_obj.label.isVisible():
                        rect = l_obj.label.sceneBoundingRect()
                        if rect.contains(ev.scenePos()):
                            window._show_manual_preview = False
                            from frontend.controllers.chart.trading_plan_panel import clear_manual_chart_lines
                            clear_manual_chart_lines(window)
                            if hasattr(window, "btnManualClearPreview") and window.btnManualClearPreview:
                                window.btnManualClearPreview.setText("SHOW PREVIEW")
                            ev.accept()
                            return
        except Exception:
            pass

    window.plot_widget.scene().sigMouseClicked.connect(_on_chart_scene_clicked)

    # Live chart update

    def on_market_tick(sym, bid, ask):

        clean_curr = getattr(window, "current_sym", "").split("\n")[0].strip()
        if not clean_curr or sym != clean_curr:

            return

        window.current_price_line.setPos(bid)

        if getattr(window, "_plan_mode", "ai") == "manual":
            try:
                from frontend.controllers.chart.trading_plan_panel import sync_manual_copilot_quotes
                sync_manual_copilot_quotes(window)
            except Exception:
                pass
        else:
            try:
                from frontend.controllers.chart.trading_plan_panel import sync_live_position_to_ai_plan
                sync_live_position_to_ai_plan(window)
            except Exception:
                pass

        rates = mt5.copy_rates_from_pos(sym, window.current_tf, 0, 1)

        if (
            rates is not None
            and len(rates) > 0
            and hasattr(window, "chart_data_list")
            and window.chart_data_list
        ):

            r = rates[0]

            last_idx = window.chart_data_list[-1][0]

            last_time = window.time_axis.timestamps[-1]

            changed = False

            if r["time"] == last_time:
                window.chart_data_list[-1] = (
                    last_idx,
                    r["open"],
                    r["close"],
                    r["low"],
                    r["high"],
                )
                if hasattr(window, "candlesticks"):
                    if hasattr(window.candlesticks, "update_live_bar"):
                        window.candlesticks.update_live_bar(r["open"], r["close"], r["low"], r["high"])
                    else:
                        window.candlesticks.data = window.chart_data_list
                        window.candlesticks.generatePicture()
                        window.candlesticks.update()

            elif r["time"] > last_time:
                new_idx = last_idx + 1
                new_bar = (new_idx, r["open"], r["close"], r["low"], r["high"])
                window.chart_data_list.append(new_bar)
                window.time_axis.timestamps.append(r["time"])
                if hasattr(window, "candlesticks"):
                    window.candlesticks.data = window.chart_data_list
                    window.candlesticks.generatePicture()
                    window.candlesticks.update()

                # On-Bar-Close Event Trigger (QuantConnect LEAN & Sierra Chart standard)
                # When previous candle confirms closed, automatically re-evaluate quantitative strategy
                clean_sym = getattr(window, "current_sym", "").split("\n")[0].strip()
                last_analyzed = getattr(window, "_last_analyzed_bar_time", 0)
                if clean_sym and r["time"] != last_analyzed:
                    window._last_analyzed_bar_time = r["time"]
                    from frontend.controllers.chart.ai_panel_controller import _run_analysis
                    _run_analysis(window, clean_sym, force=False)

    from backend.core.event_bus import event_bus

    event_bus.market_tick.connect(on_market_tick)

    # Xay dung panel phan tich moi (thay QTextEdit cu)

    _build_analysis_panel(window)

    def update_y_range():

        if not window.chart_data_list:

            return

        view_range = window.plot_widget.viewRange()[0]

        x_min = max(0, int(view_range[0]))

        x_max = min(len(window.chart_data_list) - 1, int(view_range[1]))

        if x_min < x_max:

            visible_data = window.chart_data_list[x_min : x_max + 1]

            if not visible_data:

                return

            y_min = min(d[3] for d in visible_data)

            y_max = max(d[4] for d in visible_data)

            margin = (y_max - y_min) * 0.1

            if margin == 0:

                margin = y_max * 0.001

            window.plot_widget.setYRange(y_min - margin, y_max + margin, padding=0)
            if hasattr(window, "session_meta_label") and window.session_meta_label:
                window.session_meta_label.setPos(x_min + 2, y_max + margin * 0.3)

    window.plot_widget.sigXRangeChanged.connect(update_y_range)

    def _show_chart_context_menu(pos):
        from PySide6.QtWidgets import QMenu, QFileDialog
        from PySide6.QtGui import QImage, QPainter
        is_dark = getattr(window, "is_dark_theme", True)

        menu = QMenu(window.plot_widget)

        if is_dark:
            menu_style = (
                "QMenu { background-color: #0c0e17; color: #f8fafc; border: 1px solid #1e293b; "
                "border-radius: 2px; padding: 3px; font-family: Consolas, monospace; font-size: 11px; } "
                "QMenu::item { padding: 5px 22px 5px 12px; border-radius: 2px; color: #cbd5e1 !important; background-color: transparent; } "
                "QMenu::item:selected { background-color: #1e293b; color: #38bdf8 !important; } "
                "QMenu::item:disabled { color: #64748b !important; } "
                "QMenu::separator { height: 1px; background-color: #1e293b; margin: 3px 4px; }"
            )
        else:
            menu_style = (
                "QMenu { background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; "
                "border-radius: 2px; padding: 3px; font-family: Consolas, monospace; font-size: 11px; } "
                "QMenu::item { padding: 5px 22px 5px 12px; border-radius: 2px; color: #1e293b !important; background-color: transparent; } "
                "QMenu::item:selected { background-color: #f1f5f9; color: #0284c7 !important; } "
                "QMenu::item:disabled { color: #94a3b8 !important; } "
                "QMenu::separator { height: 1px; background-color: #e2e8f0; margin: 3px 4px; }"
            )

        menu.setStyleSheet(menu_style)

        # -------------------------------------------------------------
        # 1. Order-Line Hit Test: MT5-style Modify / Delete Context Menu
        # -------------------------------------------------------------
        try:
            vb = window.plot_widget.plotItem.vb
            from PySide6.QtCore import QPointF

            def _extract_y(pt):
                if pt is None:
                    return 0.0
                if hasattr(pt, "y"):
                    return float(pt.y() if callable(pt.y) else pt.y)
                if hasattr(pt, "boundingRect"):
                    return float(pt.boundingRect().center().y())
                return 0.0

            scene_pos = window.plot_widget.mapToScene(pos.x(), pos.y()) if hasattr(pos, "x") else pos
            scene_y = _extract_y(scene_pos)

            # Detect if user right-clicked directly on or near ANY active Order Line
            hit_order_line = None
            hit_line_type = None
            hit_ticket = None
            hit_is_pos = False
            hit_vol = 0.01
            hit_action = "order"

            # 1. Check dynamic broker order lines
            for (tkt, l_type), l_obj in getattr(window, "chart_order_lines", {}).items():
                if l_obj and l_obj.isVisible():
                    try:
                        line_scene_pt = vb.mapViewToScene(QPointF(0, float(l_obj.value())))
                        line_scene_y = _extract_y(line_scene_pt)
                        if abs(scene_y - line_scene_y) <= 14:
                            hit_order_line = l_obj
                            hit_line_type = l_type
                            hit_ticket = getattr(l_obj, "order_ticket", tkt)
                            hit_is_pos = getattr(l_obj, "is_position", False)
                            hit_vol = getattr(l_obj, "order_vol", 0.01)
                            hit_action = getattr(l_obj, "order_action", "order")
                            break
                    except Exception:
                        pass

            # 2. Fallback check for single order proposal lines (line_order_entry, line_order_sl, line_order_tp)
            if hit_order_line is None:
                for l_type, l_name in [("ENTRY", "line_order_entry"), ("SL", "line_order_sl"), ("TP", "line_order_tp")]:
                    if hasattr(window, l_name):
                        l_obj = getattr(window, l_name)
                        if l_obj and l_obj.isVisible():
                            try:
                                line_scene_pt = vb.mapViewToScene(QPointF(0, float(l_obj.value())))
                                line_scene_y = _extract_y(line_scene_pt)
                                if abs(scene_y - line_scene_y) <= 14:
                                    hit_order_line = l_obj
                                    hit_line_type = l_type
                                    is_pend = getattr(window, "is_pending_order", False)
                                    hit_is_pos = getattr(window, "is_live_position", False)
                                    hit_ticket = getattr(window, "pending_ticket" if is_pend else "live_ticket", None)
                                    break
                            except Exception:
                                pass

            is_pending = not hit_is_pos
            is_live = hit_is_pos
            if hit_order_line is not None and (hit_ticket or is_pending or is_live):
                tkt = hit_ticket or getattr(window, "pending_ticket" if is_pending else "live_ticket", None)
                raw_sym = getattr(window, "current_sym", "XAUUSD") or "XAUUSD"
                sym = raw_sym.split("\n")[0].strip()
                sym_info = mt5.symbol_info(sym)
                digits = sym_info.digits if sym_info else 2

                ord_type_name = hit_action
                ord_vol = hit_vol
                ord_price = float(hit_order_line.value())

                if is_pending and tkt and ord_type_name == "order":
                    p_orders = mt5.orders_get(ticket=int(tkt))
                    if p_orders and len(p_orders) > 0:
                        po = p_orders[0]
                        ord_type_name = "sell limit" if po.type == mt5.ORDER_TYPE_SELL_LIMIT else (
                            "buy limit" if po.type == mt5.ORDER_TYPE_BUY_LIMIT else (
                                "buy stop" if po.type == mt5.ORDER_TYPE_BUY_STOP else "sell stop"
                            )
                        )
                        ord_vol = float(po.volume_current or po.volume_initial)
                        ord_price = float(po.price_open)
                elif is_live and tkt and ord_type_name == "order":
                    p_pos = mt5.positions_get(ticket=int(tkt))
                    if p_pos and len(p_pos) > 0:
                        ps = p_pos[0]
                        ord_type_name = "buy" if ps.type == 0 else "sell"
                        ord_vol = float(ps.volume)
                        ord_price = float(ps.price_open)

                order_menu = QMenu(window.plot_widget)
                order_menu.setStyleSheet(menu_style)

                # 1. Modify Item (Opens Trading Plan drawer prefilled in MANUAL ORDER mode)
                modify_label = f"Modify #{tkt} {ord_type_name} {ord_vol:<5.2f}    {ord_price:.{digits}f}"
                act_modify = order_menu.addAction(modify_label)
                def _do_modify_order():
                    from frontend.controllers.chart.trading_plan_panel import populate_manual_order_for_modification
                    mod_sl = 0.0
                    mod_tp = 0.0
                    if is_pending:
                        p_orders = mt5.orders_get(ticket=int(tkt))
                        if p_orders and len(p_orders) > 0:
                            mod_sl = float(p_orders[0].sl)
                            mod_tp = float(p_orders[0].tp)
                    else:
                        p_pos = mt5.positions_get(ticket=int(tkt))
                        if p_pos and len(p_pos) > 0:
                            mod_sl = float(p_pos[0].sl)
                            mod_tp = float(p_pos[0].tp)
                    populate_manual_order_for_modification(
                        window=window,
                        ticket=tkt,
                        order_type_str=ord_type_name,
                        volume=ord_vol,
                        price=ord_price,
                        sl=mod_sl,
                        tp=mod_tp,
                        is_position=is_live
                    )
                act_modify.triggered.connect(_do_modify_order)

                # 2. Delete / Close Item (Identical to MT5 Image 2)
                if is_pending:
                    delete_label = f"Delete #{tkt} {ord_type_name} {ord_vol:<5.2f}    {ord_price:.{digits}f}"
                else:
                    delete_label = f"Close  #{tkt} {ord_type_name} {ord_vol:<5.2f}    {ord_price:.{digits}f}"
                act_delete = order_menu.addAction(delete_label)

                def _do_delete_or_close():
                    exec_mgr = None
                    if hasattr(window, "quant_terminal") and hasattr(window.quant_terminal, "exec_mgr"):
                        exec_mgr = window.quant_terminal.exec_mgr
                    if not exec_mgr:
                        from backend.infrastructure.brokers.execution_manager import ExecutionManager
                        exec_mgr = ExecutionManager(slippage=20)

                    from backend.core.event_bus import event_bus
                    if is_pending:
                        res = exec_mgr.cancel_pending_order(int(tkt))
                        if res and res.get("status") == "success":
                            event_bus.log_event.emit("", "SUCCESS", f"Đã hủy lệnh chờ #{tkt} trên sàn MT5", "#22c55e")
                            window.is_pending_order = False
                            window.pending_ticket = None
                            if hasattr(window, "chart_order_lines"):
                                for lt in ("ENTRY", "SL", "TP"):
                                    l_rem = window.chart_order_lines.pop((int(tkt), lt), None)
                                    if l_rem and hasattr(window, "plot_widget") and window.plot_widget:
                                        try:
                                            window.plot_widget.removeItem(l_rem)
                                        except Exception:
                                            pass
                            from frontend.controllers.chart.trading_plan_panel import clear_manual_chart_lines
                            clear_manual_chart_lines(window)
                        else:
                            err_m = res.get("msg", "Error") if res else "Unknown"
                            event_bus.log_event.emit("", "ERROR", f"Lỗi hủy lệnh #{tkt}: {err_m}", "#ef4444")
                    else:
                        res = exec_mgr.close_position(int(tkt))
                        if res and res.get("status") == "success":
                            event_bus.log_event.emit("", "SUCCESS", f"Đã đóng vị thế #{tkt} trên sàn MT5", "#22c55e")
                            window.is_live_position = False
                            window.live_ticket = None
                            if hasattr(window, "chart_order_lines"):
                                for lt in ("ENTRY", "SL", "TP"):
                                    l_rem = window.chart_order_lines.pop((int(tkt), lt), None)
                                    if l_rem and hasattr(window, "plot_widget") and window.plot_widget:
                                        try:
                                            window.plot_widget.removeItem(l_rem)
                                        except Exception:
                                            pass
                            from frontend.controllers.chart.trading_plan_panel import clear_manual_chart_lines
                            clear_manual_chart_lines(window)
                        else:
                            err_m = res.get("msg", "Error") if res else "Unknown"
                            event_bus.log_event.emit("", "ERROR", f"Lỗi đóng vị thế #{tkt}: {err_m}", "#ef4444")
                act_delete.triggered.connect(_do_delete_or_close)

                order_menu.addSeparator()

                # 3. Trailing Stop Submenu (MT5 Standard)
                m_trailing = order_menu.addMenu("Trailing Stop")
                m_trailing.setStyleSheet(menu_style)
                act_none = m_trailing.addAction("None")
                def _cancel_trail():
                    if hasattr(window, "_active_trailing_stops") and int(tkt) in window._active_trailing_stops:
                        del window._active_trailing_stops[int(tkt)]
                    from backend.core.event_bus import event_bus
                    event_bus.log_event.emit("", "INFO", f"Đã hủy Trailing Stop cho #{tkt}", "#64748b")
                act_none.triggered.connect(_cancel_trail)

                for pts in [15, 20, 30, 50, 100]:
                    act_p = m_trailing.addAction(f"{pts} Points")
                    def _set_trail(p=pts):
                        if not hasattr(window, "_active_trailing_stops"):
                            window._active_trailing_stops = {}
                        window._active_trailing_stops[int(tkt)] = p
                        from backend.core.event_bus import event_bus
                        event_bus.log_event.emit("", "SUCCESS", f"Đã kích hoạt Trailing Stop {p} points cho #{tkt}", "#38bdf8")
                    act_p.triggered.connect(_set_trail)

                if is_live:
                    order_menu.addSeparator()
                    act_be = order_menu.addAction("Move SL to Breakeven")
                    def _do_be():
                        exec_mgr = None
                        if hasattr(window, "quant_terminal") and hasattr(window.quant_terminal, "exec_mgr"):
                            exec_mgr = window.quant_terminal.exec_mgr
                        if not exec_mgr:
                            from backend.infrastructure.brokers.execution_manager import ExecutionManager
                            exec_mgr = ExecutionManager(slippage=20)

                        # Query existing position details from MT5 or cache to preserve take profit
                        cur_tp = 0.0
                        pos_list = mt5.positions_get(ticket=int(tkt))
                        if pos_list and len(pos_list) > 0:
                            cur_tp = float(pos_list[0].tp)
                        elif hasattr(window, "chart_order_lines") and (int(tkt), "TP") in window.chart_order_lines:
                            cur_tp = float(window.chart_order_lines[(int(tkt), "TP")].value())
                        elif hasattr(window, "line_order_tp") and window.line_order_tp.isVisible():
                            cur_tp = float(window.line_order_tp.value())

                        res = exec_mgr.modify_position(int(tkt), sl=ord_price, tp=cur_tp)
                        from backend.core.event_bus import event_bus
                        if res and res.get("status") == "success":
                            event_bus.log_event.emit("", "SUCCESS", f"Đã dời SL vị thế #{tkt} về hòa vốn {ord_price:.{digits}f}", "#22c55e")
                            if hasattr(window, "chart_order_lines") and (int(tkt), "SL") in window.chart_order_lines:
                                window.chart_order_lines[(int(tkt), "SL")].setValue(ord_price)
                            if hasattr(window, "line_order_sl") and window.line_order_sl:
                                window.line_order_sl.setValue(ord_price)
                            if hasattr(window, "refresh_active_orders"):
                                window.refresh_active_orders()
                        else:
                            err_m = res.get("msg", "Error") if res else "Unknown"
                            event_bus.log_event.emit("", "ERROR", f"Không thể dời SL về hòa vốn: {err_m}", "#ef4444")
                    act_be.triggered.connect(_do_be)

                order_menu.exec(window.plot_widget.mapToGlobal(pos))
                return

            view_point = vb.mapSceneToView(scene_pos)
            click_p_raw = _extract_y(view_point)

            raw_sym = getattr(window, "current_sym", "XAUUSD") or "XAUUSD"
            sym = raw_sym.split("\n")[0].strip()
            sym_info = mt5.symbol_info(sym)
            digits = sym_info.digits if sym_info else (2 if click_p_raw > 10 else 5)
            click_p = round(click_p_raw, digits)

            tick = mt5.symbol_info_tick(sym)
            cur_bid = tick.bid if tick else click_p
            cur_ask = tick.ask if tick else click_p

            # Resolve lot size: Manual spinbox > Broker volume_min (institutional standard, no cross-contamination)
            min_lot = float(sym_info.volume_min) if (sym_info and hasattr(sym_info, "volume_min") and sym_info.volume_min) else 0.01
            lot = None
            if hasattr(window, "spinManualLot") and window.spinManualLot and window.spinManualLot.value() > 0:
                lot = float(window.spinManualLot.value())
            elif hasattr(window, "lblManualLotVal") and window.lblManualLotVal:
                try:
                    lot = float(window.lblManualLotVal.text().split()[0])
                except Exception:
                    pass

            if lot is None or lot <= 0:
                lot = min_lot
            lot = round(float(lot), 2)

            is_above = click_p >= cur_ask
            primary_type = "SELL_LIMIT" if is_above else "BUY_LIMIT"
            primary_label = f"Sell Limit {lot:<5.2f}    {click_p:.{digits}f}" if is_above else f"Buy Limit  {lot:<5.2f}    {click_p:.{digits}f}"
            secondary_type = "BUY_STOP" if is_above else "SELL_STOP"
            secondary_label = f"Buy Stop   {lot:<5.2f}    {click_p:.{digits}f}" if is_above else f"Sell Stop  {lot:<5.2f}    {click_p:.{digits}f}"

            def _do_execute_pending(order_type_str: str, target_price: float):
                try:
                    # Institutional Safety Guard: Confirmation dialog before dispatching real broker orders
                    one_click = getattr(window, "one_click_trading_enabled", False)
                    if not one_click:
                        from PySide6.QtWidgets import QMessageBox
                        reply = QMessageBox.question(
                            window,
                            "Xác nhận đặt lệnh MT5",
                            f"Bạn có chắc chắn muốn gửi lệnh sau lên MT5?\n\n"
                            f"• Loại lệnh: {order_type_str}\n"
                            f"• Cặp tiền: {sym}\n"
                            f"• Khối lượng: {lot:.2f} lot\n"
                            f"• Giá đặt: {target_price:.{digits}f}\n\n"
                            f"Bấm 'Yes' để gửi lệnh lên sàn, hoặc 'No' để hủy bỏ.",
                            QMessageBox.Yes | QMessageBox.No,
                            QMessageBox.No,
                        )
                        if reply != QMessageBox.Yes:
                            return

                    from backend.infrastructure.brokers.execution_manager import ExecutionManager
                    exec_mgr = None
                    if hasattr(window, "quant_terminal") and hasattr(window.quant_terminal, "exec_mgr"):
                        exec_mgr = window.quant_terminal.exec_mgr
                    if not exec_mgr:
                        exec_mgr = ExecutionManager(slippage=20)

                    res = exec_mgr.execute_pending_order(
                        symbol=sym,
                        order_type=order_type_str,
                        price=target_price,
                        volume=lot,
                        sl_price=0.0,
                        tp_price=0.0,
                        comment="VECTRA_ChartOrder",
                    )

                    from backend.core.event_bus import event_bus
                    if res.get("status") == "success":
                        tkt = res.get("ticket")
                        msg = f"Đã đặt {order_type_str} {lot} {sym} @ {target_price} (Ticket #{tkt})"
                        logger.info(f"[ChartTrading] {msg}")
                        event_bus.log_event.emit("", "SUCCESS", msg, "#22c55e")
                        window.is_pending_order = True
                        window.pending_ticket = tkt
                        window.pending_order_type = order_type_str
                        window.pending_price = target_price
                        if hasattr(window, "refresh_active_orders"):
                            window.refresh_active_orders()
                    else:
                        err_msg = res.get("msg", "Lỗi gửi lệnh MT5")
                        logger.error(f"[ChartTrading] {err_msg}")
                        event_bus.log_event.emit("", "ERROR", f"Không thể đặt {order_type_str}: {err_msg}", "#ef4444")
                except Exception as e:
                    logger.error(f"[ChartTrading] Exception while executing pending order: {e}")

            # Trading Submenu (Institutional Standard: MT5 & TradingView place all trade actions in a dedicated submenu)
            m_trading = menu.addMenu("Trading")
            m_trading.setStyleSheet(menu_style)

            act_sub1 = m_trading.addAction(primary_label)
            act_sub1.triggered.connect(lambda chk=False, t=primary_type, p=click_p: _do_execute_pending(t, p))

            act_sub2 = m_trading.addAction(secondary_label)
            act_sub2.triggered.connect(lambda chk=False, t=secondary_type, p=click_p: _do_execute_pending(t, p))

            act_alert = m_trading.addAction(f"Alert                    {click_p:.{digits}f}")
            def _do_set_alert(target_p):
                from backend.core.event_bus import event_bus
                event_bus.log_event.emit("", "INFO", f"Đã tạo cảnh báo giá {sym} @ {target_p}", "#38bdf8")
            act_alert.triggered.connect(lambda chk=False, p=click_p: _do_set_alert(p))

            m_trading.addSeparator()
            act_new_order = m_trading.addAction("New Order Ticket...     F9")
            def _do_open_new_order_ticket(target_p):
                _open_ai_drawer()
                if hasattr(window, "_switch_plan_mode"):
                    window._switch_plan_mode("manual")
                elif hasattr(window, "btnPlanModeManual") and window.btnPlanModeManual:
                    window.btnPlanModeManual.click()
                if hasattr(window, "spinManualPendingPrice") and window.spinManualPendingPrice:
                    window.spinManualPendingPrice.setValue(target_p)
            act_new_order.triggered.connect(lambda chk=False, p=click_p: _do_open_new_order_ticket(p))

            menu.addSeparator()
        except Exception as e:
            logger.debug(f"[ChartCanvas] Price mapping in context menu: {e}")
        tf_menu = menu.addMenu("Timeframes")
        tf_menu.setStyleSheet(menu_style)
        tfs = [
            ("M1", mt5.TIMEFRAME_M1), ("M5", mt5.TIMEFRAME_M5), ("M15", mt5.TIMEFRAME_M15),
            ("M30", mt5.TIMEFRAME_M30), ("H1", mt5.TIMEFRAME_H1), ("H4", mt5.TIMEFRAME_H4),
            ("D1", mt5.TIMEFRAME_D1),
        ]
        for tf_n, tf_v in tfs:
            prefix = "✓  " if tf_n == window.current_tf_str else "    "
            act = tf_menu.addAction(f"{prefix}{tf_n}")
            act.triggered.connect(lambda chk=False, v=tf_v, n=tf_n: change_timeframe(v, n))

        # Chart Modes (Alt+2 Candlestick, Alt+1 Bars, Alt+3 Line)
        m_mode = menu.addMenu("Chart Mode")
        m_mode.setStyleSheet(menu_style)
        cur_m = getattr(window, "chart_mode", "candlestick")
        act_c = m_mode.addAction(f"{'✓  ' if cur_m == 'candlestick' else '    '}Candlesticks (Alt+2)")
        act_c.triggered.connect(lambda: set_chart_mode("candlestick") if "set_chart_mode" in globals() else None)
        act_b = m_mode.addAction(f"{'✓  ' if cur_m == 'bar' else '    '}Bar Chart (Alt+1)")
        act_b.triggered.connect(lambda: set_chart_mode("bar") if "set_chart_mode" in globals() else None)
        act_l = m_mode.addAction(f"{'✓  ' if cur_m == 'line' else '    '}Line Chart (Alt+3)")
        act_l.triggered.connect(lambda: set_chart_mode("line") if "set_chart_mode" in globals() else None)

        act_ind = menu.addAction("Indicators...")
        act_ind.triggered.connect(lambda: _open_indicators() if hasattr(window, "open_indicators") else None)

        menu.addSeparator()
        act_reset = menu.addAction("Auto Fit (Reset Scale)")
        def _do_reset():
            if hasattr(window, "chart_data_list") and window.chart_data_list:
                tot = len(window.chart_data_list)
                vb = min(120, tot)
                window.plot_widget.setXRange(tot - vb, tot + 5)
                update_y_range()
        act_reset.triggered.connect(_do_reset)

        act_export = menu.addAction("Export Chart Image...")
        def _do_export():
            try:
                raw_sym = getattr(window, "current_sym", "CHART") or "CHART"
                clean_sym = raw_sym.split("\n")[0].strip()
                tf_k = getattr(window, "current_tf_str", "H1")
                default_name = f"{clean_sym}_{tf_k}_chart.png"
                file_path, _ = QFileDialog.getSaveFileName(
                    window, "Export Chart Image", default_name, "PNG Images (*.png);;All Files (*)"
                )
                if file_path:
                    img = QImage(window.plot_widget.size(), QImage.Format_ARGB32)
                    img.fill(QtCore.Qt.transparent)
                    painter = QPainter(img)
                    window.plot_widget.render(painter)
                    painter.end()
                    img.save(file_path)
                    from backend.core.event_bus import event_bus
                    event_bus.log_event.emit("", "SUCCESS", f"Chart exported to {file_path}", "#10b981")
            except Exception as e:
                logger.error(f"[ChartCanvas] Failed to export chart image: {e}")
        act_export.triggered.connect(_do_export)

        menu.exec(window.plot_widget.mapToGlobal(pos))

    # Vô hiệu hóa context menu mặc định của pyqtgraph để ngăn 2 menu đè lên nhau
    if hasattr(window.plot_widget, "plotItem") and hasattr(window.plot_widget.plotItem, "vb"):
        window.plot_widget.plotItem.vb.setMenuEnabled(False)
    if hasattr(window.plot_widget, "getViewBox"):
        vb = window.plot_widget.getViewBox()
        if vb is not None:
            vb.setMenuEnabled(False)

    window.plot_widget.setContextMenuPolicy(Qt.CustomContextMenu)
    window.plot_widget.customContextMenuRequested.connect(_show_chart_context_menu)

    def change_timeframe(val, name_str):
        window.current_tf = val
        window.current_tf_str = name_str
        if hasattr(window, "update_tf_styles"):
            try:
                window.update_tf_styles()
            except Exception as err:
                logger.debug(f"[ChartCanvas] update_tf_styles error: {err}")
        if hasattr(window, "quant_terminal"):
            qt = window.quant_terminal
            if hasattr(qt, "combo_top_tf"):
                qt.combo_top_tf.blockSignals(True)
                qt.combo_top_tf.setCurrentText(name_str)
                qt.combo_top_tf.blockSignals(False)
            if hasattr(qt, "lbl_top_ticker"):
                qt.lbl_top_ticker.setText(qt._format_top_ticker())
        if window.current_sym:
            draw_and_analyze(window.current_sym)

    window.change_timeframe = change_timeframe

    def draw_and_analyze(sym):
        clean_sym = sym.split("\n")[0].strip()
        sym = clean_sym
        window.current_sym = sym

        # Reset active live ticket and re-anchor signal data strictly to target symbol
        window.is_live_position = False
        window.live_ticket = None
        if not hasattr(window, "active_signals_by_symbol"):
            window.active_signals_by_symbol = {}
        window.active_signal_data = window.active_signals_by_symbol.get(clean_sym, {})

        rates = None
        if mt5.terminal_info() is None:
            mt5.initialize()

        if mt5.terminal_info() is not None:
            mt5.symbol_select(sym, True)
            rates = mt5.copy_rates_from_pos(sym, window.current_tf, 0, 5000)
            if rates is None or len(rates) == 0:
                rates = mt5.copy_rates_from_pos(sym, window.current_tf, 0, 1000)

        # Quản lý cơ chế đệm dữ liệu ngoại tuyến (Scenario A & B)
        is_cached_fallback = False
        cached_info_str = ""

        if rates is not None and len(rates) > 0:
            if not hasattr(window, "_rates_cache"):
                window._rates_cache = {}
            # SC-12: Enforce LRU eviction cap (max 10 symbol frames) to prevent memory leak
            if len(window._rates_cache) >= 10 and (sym, window.current_tf) not in window._rates_cache:
                oldest_key = next(iter(window._rates_cache))
                del window._rates_cache[oldest_key]
            c_str = time.strftime("%H:%M:%S")
            window._rates_cache[(sym, window.current_tf)] = (rates, time.time(), c_str)
            if hasattr(window, "offline_banner") and window.offline_banner:
                window.offline_banner.setVisible(False)
            if hasattr(window, "empty_state_card") and window.empty_state_card:
                window.empty_state_card.setVisible(False)
        else:
            # Kiểm tra xem mã này đã từng có nến trong phiên chưa
            cached_data = getattr(window, "_rates_cache", {}).get((sym, window.current_tf))
            if cached_data is not None:
                rates, _, cached_info_str = cached_data
                is_cached_fallback = True
                if hasattr(window, "empty_state_card") and window.empty_state_card:
                    window.empty_state_card.setVisible(False)
                if hasattr(window, "offline_banner") and window.offline_banner:
                    if hasattr(window, "lbl_offline_msg"):
                        window.lbl_offline_msg.setText(
                            f"MetaTrader 5 disconnected. Showing cached market feed for {sym} ({cached_info_str})."
                        )
                    window.offline_banner.setVisible(True)

        if rates is None or len(rates) == 0:
            # Kịch bản B: Khởi động lạnh hoặc mã chưa từng có nến (Hiển thị Thẻ chẩn đoán rỗng)
            window.chart_data_list = []
            window.plot_widget.clear()
            window._ind_curves = {}

            if hasattr(window, "offline_banner") and window.offline_banner:
                window.offline_banner.setVisible(False)

            # Gỡ bỏ toàn bộ đường lệnh ảo cũ khi không có dữ liệu
            for line_name in ("line_order_entry", "line_order_sl", "line_order_tp"):
                if hasattr(window, line_name):
                    l_obj = getattr(window, line_name)
                    if l_obj is not None:
                        try:
                            window.plot_widget.removeItem(l_obj)
                        except Exception as err:
                            logger.debug(f"[ChartCanvas] Empty state removeItem error: {err}")
            window.order_proposal_active = False

            txt_lbl = "#94a3b8"
            txt_warn = "#d97706"
            empty_ohlc = (
                f'<span style="font-family:Consolas, monospace; font-size:9.5px; color:{txt_lbl};">'
                f'O: <b style="color:{txt_lbl};">--</b> &nbsp;&nbsp;'
                f'H: <b style="color:{txt_lbl};">--</b> &nbsp;&nbsp;'
                f'L: <b style="color:{txt_lbl};">--</b> &nbsp;&nbsp;'
                f'C: <b style="color:{txt_lbl};">--</b> &nbsp;&nbsp;'
                f'<b style="color:{txt_warn};">NO MT5 DATA FEED</b>'
                f'</span>'
            )
            if hasattr(window, "lbl_chart_title") and window.lbl_chart_title:
                window.lbl_chart_title.setText(empty_ohlc)
            if hasattr(window, "lbl_chart_ohlc") and window.lbl_chart_ohlc:
                window.lbl_chart_ohlc.setText(empty_ohlc)

            if hasattr(window, "lbl_ribbon_left") and window.lbl_ribbon_left:
                c_lbl = "#475569"
                window.lbl_ribbon_left.setText(
                    f'<span style="color:{c_lbl}; font-family:Consolas, monospace; font-size:8.5px;">'
                    f'SESSION: <b>--</b> &nbsp;|&nbsp; '
                    f'vPOC: <b>--</b> &nbsp;|&nbsp; '
                    f'VAH: <b>--</b> &nbsp;|&nbsp; '
                    f'VAL: <b>--</b> &nbsp;|&nbsp; '
                    f'tPOC: <b>--</b> &nbsp;|&nbsp; '
                    f'DELTA: <b>--</b>'
                    f'</span>'
                )

            # Hiển thị Thẻ chẩn đoán rỗng trung tâm phẳng
            if hasattr(window, "empty_state_card") and window.empty_state_card:
                if hasattr(window, "lbl_empty_sub"):
                    window.lbl_empty_sub.setText(f"No candlestick feed received from MT5 for {sym}")
                window.empty_state_card.setVisible(True)
                if hasattr(window, "_chart_overlay_filter"):
                    window._chart_overlay_filter.reposition()

            update_order_proposal_html(
                window,
                sym=sym,
                has_signal=False,
                model_name="Awaiting MT5 Feed",
                digits=2,
            )

            if hasattr(window, "ai_lbl_status") and window.ai_lbl_status:
                window.ai_lbl_status.setText("Awaiting MT5 feed...")
            if hasattr(window, "lbl_ai_action") and window.lbl_ai_action:
                window.lbl_ai_action.setText("AWAITING FEED")
            if hasattr(window, "lbl_ai_conf") and window.lbl_ai_conf:
                window.lbl_ai_conf.setText("--%")
            if hasattr(window, "lbl_ai_reason") and window.lbl_ai_reason:
                window.lbl_ai_reason.setText("No real-time market data received from MetaTrader 5.")

            if hasattr(window, "lbl_ribbon_left") and window.lbl_ribbon_left:
                c_lbl = "#71717a" if getattr(window, "is_dark_theme", False) else "#475569"
                c_val = "#ffffff" if getattr(window, "is_dark_theme", False) else "#0f172a"
                window.lbl_ribbon_left.setText(
                    f'<span style="color:{c_lbl}; font-family:Consolas, monospace; font-size:8.5px;">'
                    f'SESSION: <b style="color:{c_val};">--</b> &nbsp;|&nbsp; '
                    f'vPOC: <b style="color:{c_val};">--</b> &nbsp;|&nbsp; '
                    f'VAH: <b style="color:{c_val};">--</b> &nbsp;|&nbsp; '
                    f'VAL: <b style="color:{c_val};">--</b> &nbsp;|&nbsp; '
                    f'tPOC: <b style="color:{c_val};">--</b> &nbsp;|&nbsp; '
                    f'DELTA: <b style="color:{c_val};">--</b>'
                    f'</span>'
                )

            if hasattr(window, "quant_terminal") and hasattr(window.quant_terminal, "watchlist"):
                window.quant_terminal.watchlist.set_active_symbol(sym)

            return

        window.chart_data_list = []
        timestamps = []
        for i in range(len(rates)):
            r = rates[i]
            window.chart_data_list.append(
                (i, r["open"], r["close"], r["low"], r["high"])
            )
            timestamps.append(r["time"])

        window.time_axis.update_timestamps(timestamps)
        window.plot_widget.clear()
        window._ind_curves = {}

        sym_info = mt5.symbol_info(sym)
        last_r = rates[-1]
        cur_p = float(last_r["close"])
        digits = sym_info.digits if sym_info else (2 if cur_p > 10 else 5)
        diff = last_r["close"] - rates[0]["open"]
        diff_pct = (diff / rates[0]["open"]) * 100
        sign = "+" if diff >= 0 else ""
        pnl_col = "#22c55e" if diff >= 0 else "#ef4444"
        window.lbl_chart_title.setText(
            f'<span style="font-family: Consolas, monospace; font-size: 10px; color: #94a3b8;">'
            f'O: <b style="color:#f8fafc;">{last_r["open"]:.{digits}f}</b> &nbsp;'
            f'H: <b style="color:#f8fafc;">{last_r["high"]:.{digits}f}</b> &nbsp;'
            f'L: <b style="color:#f8fafc;">{last_r["low"]:.{digits}f}</b> &nbsp;'
            f'C: <b style="color:#f8fafc;">{last_r["close"]:.{digits}f}</b> &nbsp;'
            f'<b style="color:{pnl_col};">{sign}{diff:.{digits}f} ({sign}{diff_pct:.2f}%)</b>'
            f'</span>'
        )

        is_d = getattr(window, "is_dark_theme", False)
        txt_val = "#f8fafc" if is_d else "#0f172a"
        txt_lbl = "#64748b" if is_d else "#94a3b8"
        diff_str = f"{sign}{diff_pct:.2f}%" if not is_cached_fallback else f"{sign}{diff_pct:.2f}% (CACHED {cached_info_str})"
        diff_col = pnl_col if not is_cached_fallback else "#d97706"

        if hasattr(window, "lbl_chart_ohlc") and window.lbl_chart_ohlc:
            window.lbl_chart_ohlc.setText(
                f'<span style="font-family:Consolas, monospace; font-size:9.5px; color:{txt_lbl};">'
                f'O: <b style="color:{txt_val};">{last_r["open"]:.{digits}f}</b> &nbsp;&nbsp;'
                f'H: <b style="color:{txt_val};">{last_r["high"]:.{digits}f}</b> &nbsp;&nbsp;'
                f'L: <b style="color:{txt_val};">{last_r["low"]:.{digits}f}</b> &nbsp;&nbsp;'
                f'C: <b style="color:{txt_val};">{last_r["close"]:.{digits}f}</b> &nbsp;&nbsp;'
                f'<b style="color:{diff_col};">{diff_str}</b>'
                f'</span>'
            )

        # SC-12: Explicitly clear and detach previous CandlestickItem to free QPicture buffer
        if hasattr(window, "candlesticks") and window.candlesticks is not None:
            try:
                window.plot_widget.removeItem(window.candlesticks)
            except Exception:
                pass
            window.candlesticks = None

        is_d = getattr(window, "is_dark_theme", False)
        window.candlesticks = CandlestickItem(window.chart_data_list, is_dark=is_d)
        window.plot_widget.addItem(window.candlesticks)

        # Tự động nhận diện và vẽ Fair Value Gap (FVG) chuẩn mực thể chế & LuxAlgo
        try:
            from frontend.controllers.chart.fvg_engine import update_chart_fvgs
            update_chart_fvgs(window)
        except Exception as e_fvg:
            logger.debug(f"[FVG] Error updating chart FVGs: {e_fvg}")

        # Thêm lại crosshair, live price line, tPOC, vPOC do hàm clear() đã xóa mất
        if hasattr(window, "vLine"):
            window.plot_widget.addItem(window.vLine, ignoreBounds=True)

        if hasattr(window, "hLine"):
            window.plot_widget.addItem(window.hLine, ignoreBounds=True)

        if hasattr(window, "crosshair_label"):
            window.plot_widget.addItem(window.crosshair_label, ignoreBounds=True)

        if hasattr(window, "current_price_line"):
            window.current_price_line.setPos(cur_p)
            window.plot_widget.addItem(window.current_price_line, ignoreBounds=True)

        # -------------------------------------------------------------
        # Market Profile / Volume Profile (J. Peter Steidlmayer, CBOT 1985)
        # Point of Control (vPOC, tPOC) & 70% Value Area (VAH, VAL)
        # -------------------------------------------------------------
        vpoc_val, vah_val, val_val, tpoc_val = _compute_market_profile_va(
            rates, lookback=100, num_bins=60, va_pct=0.70, return_tpoc=True
        )

        poc_vis = getattr(window, "_poc_visible", True)
        vpoc_vis = getattr(window, "_vpoc_visible", poc_vis) and poc_vis
        tpoc_vis = getattr(window, "_tpoc_visible", poc_vis) and poc_vis
        if hasattr(window, "line_vpoc"):
            window.line_vpoc.setValue(vpoc_val)
            window.line_vpoc.setVisible(vpoc_vis)
        if hasattr(window, "line_tpoc"):
            window.line_tpoc.setValue(tpoc_val)
            window.line_tpoc.setVisible(tpoc_vis)

        va_vis = getattr(window, "_va_visible", True)
        vah_vis = getattr(window, "_vah_visible", va_vis) and va_vis
        val_vis = getattr(window, "_val_visible", va_vis) and va_vis
        va_fill_vis = getattr(window, "_va_fill_visible", va_vis) and va_vis
        if hasattr(window, "line_vah"):
            window.line_vah.setValue(vah_val)
            window.line_vah.setVisible(vah_vis)
        if hasattr(window, "line_val"):
            window.line_val.setValue(val_val)
            window.line_val.setVisible(val_vis)
        if hasattr(window, "va_region"):
            window.va_region.setRegion([val_val, vah_val])
            window.va_region.setVisible(va_fill_vis)

        # Restore user drawings and annotations from DrawingEngine
        if hasattr(window, "drawing_engine") and window.drawing_engine:
            window.drawing_engine.re_add_to_plot()

        from datetime import datetime, timezone
        utc_hour = datetime.now(timezone.utc).hour
        if 0 <= utc_hour < 8:
            session_name = "ASIAN SESSION"
        elif 8 <= utc_hour < 13:
            session_name = "LONDON SESSION"
        elif 13 <= utc_hour < 16:
            session_name = "LONDON / NY OVERLAP (RTH)"
        elif 16 <= utc_hour < 21:
            session_name = "NEW YORK CME (RTH)"
        else:
            session_name = "PACIFIC / SYDNEY"

        up_vol = sum(float(r["tick_volume"]) for r in rates[-30:] if r["close"] >= r["open"])
        down_vol = sum(float(r["tick_volume"]) for r in rates[-30:] if r["close"] < r["open"])
        delta_val = up_vol - down_vol
        delta_k = delta_val / 1000.0
        sign_d = "+" if delta_k >= 0 else ""
        delta_desc = "Absorption" if abs(delta_k) > 5 else "Balanced"
        delta_str = f"{sign_d}{delta_k:.1f}k ({delta_desc})"

        is_d = getattr(window, "is_dark_theme", False)
        delta_color = "#10b981" if delta_val >= 0 else "#ef4444"

        window._last_vpoc = vpoc_val
        window._last_vah = vah_val
        window._last_val = val_val
        window._last_tpoc = tpoc_val
        window._last_session = session_name
        window._last_delta_str = delta_str
        window._last_delta_color = delta_color
        window._last_digits = digits

        if hasattr(window, "lbl_ribbon_left") and window.lbl_ribbon_left:
            c_lbl = "#71717a" if is_d else "#475569"
            c_val = "#ffffff" if is_d else "#0f172a"
            c_va = "#38bdf8" if is_d else "#0284c7"
            c_vpoc = "#22c55e" if is_d else "#15803d"
            c_tpoc = "#f43f5e" if is_d else "#b91c1c"
            sess_prefix = f'SESSION: <b style="color:{c_val};">{session_name}</b> &nbsp;|&nbsp; ' if not is_cached_fallback else f'<b style="color:#d97706;">OFFLINE CACHE ({cached_info_str})</b> &nbsp;|&nbsp; '
            window.lbl_ribbon_left.setText(
                f'<span style="color:{c_lbl}; font-family:Consolas, monospace; font-size:8.5px;">'
                f'{sess_prefix}'
                f'vPOC: <b style="color:{c_vpoc};">{vpoc_val:,.{digits}f}</b> &nbsp;|&nbsp; '
                f'VAH: <b style="color:{c_va};">{vah_val:,.{digits}f}</b> &nbsp;|&nbsp; '
                f'VAL: <b style="color:{c_va};">{val_val:,.{digits}f}</b> &nbsp;|&nbsp; '
                f'tPOC: <b style="color:{c_tpoc};">{tpoc_val:,.{digits}f}</b> &nbsp;|&nbsp; '
                f'Δ: <b style="color:{delta_color};">{delta_str}</b>'
                f'</span>'
            )

        # Gỡ bỏ toàn bộ đường lệnh ảo cũ khi tải lại biểu đồ hoặc chuyển mã
        for line_name in ("line_order_entry", "line_order_sl", "line_order_tp"):
            if hasattr(window, line_name):
                l_obj = getattr(window, line_name)
                if l_obj is not None:
                    try:
                        window.plot_widget.removeItem(l_obj)
                    except Exception as err:
                        logger.debug(f"[ChartCanvas] Re-render removeItem error: {err}")
        window.order_proposal_active = False
        window.is_live_position = False
        window.live_ticket = None

        strat_display_name = "ICT Zones Pro v4.2"
        try:
            strat_saved = getattr(window, "active_strategy_id", None)
            if not strat_saved and hasattr(window, "comboStrategy") and window.comboStrategy:
                try:
                    import shiboken6
                    if shiboken6.isValid(window.comboStrategy):
                        strat_saved = window.comboStrategy.currentData()
                except Exception:
                    pass
            if not strat_saved:
                with open("config/settings.json", "r", encoding="utf-8") as f_cfg:
                    cfg_s = json.load(f_cfg)
                    strat_saved = cfg_s.get("strategy", "builtin_ict_pro")

            from backend.core.strategies import get_strategy_instance
            strat_inst = get_strategy_instance(strat_saved)
            strat_display_name = getattr(strat_inst, "name", "Quant Strategy")
            if hasattr(window, "update_strategy_badge"):
                window.update_strategy_badge(strat_saved)
        except Exception:
            strat_display_name = "ICT Zones Pro v4.2"

        update_order_proposal_html(
            window,
            sym=sym,
            has_signal=False,
            model_name=strat_display_name,
            digits=digits,
        )

        try:
            from frontend.controllers.chart.trading_plan_panel import sync_live_position_to_ai_plan
            sync_live_position_to_ai_plan(window)
        except Exception:
            pass

        try:
            if hasattr(window, "sync_chart_orders"):
                window.sync_chart_orders()
        except Exception as e:
            logger.debug(f"[ChartCanvas] sync_chart_orders in draw_and_analyze error: {e}")

        total_candles = len(window.chart_data_list)

        window.plot_widget.setLimits(xMin=-20, xMax=total_candles + 20)

        view_bars = min(120, total_candles)

        window.plot_widget.setXRange(total_candles - view_bars, total_candles + 5)

        update_y_range()

        if hasattr(window, "quant_terminal"):
            if hasattr(window.quant_terminal, "_refresh_top_ticker"):
                window.quant_terminal._refresh_top_ticker()
            elif hasattr(window.quant_terminal, "lbl_top_ticker"):
                window.quant_terminal.lbl_top_ticker.setText(window.quant_terminal._format_top_ticker())
            if hasattr(window.quant_terminal, "update_sidebar_alert"):
                window.quant_terminal.update_sidebar_alert(clean_sym)
            if hasattr(window.quant_terminal, "macro_calendar") and hasattr(window.quant_terminal.macro_calendar, "set_current_symbol"):
                window.quant_terminal.macro_calendar.set_current_symbol(clean_sym)

        # --- DRAW INDICATORS (setData pattern) ---

        df = pd.DataFrame(rates)

        _refresh_indicators(window, df)

        # -----------------------

        if is_cached_fallback:
            if hasattr(window, "ai_lbl_status") and window.ai_lbl_status:
                window.ai_lbl_status.setText("Analysis Paused")
            if hasattr(window, "lbl_ai_action") and window.lbl_ai_action:
                window.lbl_ai_action.setText("SIGNALS LOCKED")
            if hasattr(window, "lbl_ai_conf") and window.lbl_ai_conf:
                window.lbl_ai_conf.setText("--%")
            if hasattr(window, "lbl_ai_reason") and window.lbl_ai_reason:
                window.lbl_ai_reason.setText("MT5 real-time data disconnected. Signal locked for capital preservation.")
        else:
            _run_analysis(window, sym)
        if hasattr(window, "quant_terminal") and hasattr(window.quant_terminal, "watchlist"):
            window.quant_terminal.watchlist.set_active_symbol(sym)

    def on_watchlist_click(item, column=0):
        if item.childCount() > 0:
            return  # clicked on category header
        sym = item.text(0).split("\n")[0].strip()
        if sym:
            draw_and_analyze(sym)

    def on_watchlist_changed(curr, prev):
        if curr and curr.childCount() == 0:
            sym = curr.text(0).split("\n")[0].strip()
            if sym and sym != getattr(window, "current_sym", ""):
                draw_and_analyze(sym)

    if hasattr(window, "treeWatchlist"):
        window.treeWatchlist.itemClicked.connect(on_watchlist_click)
        window.treeWatchlist.currentItemChanged.connect(on_watchlist_changed)

    window.draw_and_analyze = draw_and_analyze
    # Auto-load default active pair XAUUSD
    draw_and_analyze("XAUUSD")


def update_chart_theme(window, is_dark: bool = False):
    is_dark = False
    window.is_dark_theme = False
    """Synchronize all Tab 1 chart elements, buttons, axes, labels, and AI reasoning with current theme."""
    window.is_dark_theme = is_dark

    # Synchronize candlesticks
    if hasattr(window, "candlesticks") and window.candlesticks:
        window.candlesticks.set_theme(is_dark)

    # Playbook 3-card Trading Plan theme synchronization
    if hasattr(window, "cardSetupModel"):
        apply_playbook_cards_theme(window, is_dark)

    # Chart ribbon theme synchronization
    if hasattr(window, "frameChartRibbon") and window.frameChartRibbon:
        ribbon_bg = "#050608" if is_dark else "#f8fafc"
        ribbon_border = "#1c1c1c" if is_dark else "#e2e8f0"
        window.frameChartRibbon.setStyleSheet(f"QFrame#frameChartRibbon {{ background-color: {ribbon_bg}; border-bottom: 1px solid {ribbon_border}; }}")

    if hasattr(window, "btn_edge_wl") and window.btn_edge_wl:
        if is_dark:
            window.btn_edge_wl.setStyleSheet(
                "QPushButton#btnEdgeWatchlist { background-color: transparent; color: #94a3b8; border: 1px solid transparent; "
                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0 6px; min-height: 18px; max-height: 18px; } "
                "QPushButton#btnEdgeWatchlist:hover { background-color: #1e293b; color: #ffffff; border: 1px solid #475569; }"
            )
        else:
            window.btn_edge_wl.setStyleSheet(
                "QPushButton#btnEdgeWatchlist { background-color: transparent; color: #475569; border: 1px solid transparent; "
                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0 6px; min-height: 18px; max-height: 18px; } "
                "QPushButton#btnEdgeWatchlist:hover { background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; }"
            )

    if hasattr(window, "btn_edge_plan") and window.btn_edge_plan:
        if is_dark:
            window.btn_edge_plan.setStyleSheet(
                "QPushButton#btnEdgeTradingPlan { background-color: transparent; color: #94a3b8; border: 1px solid transparent; "
                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0 6px; min-height: 18px; max-height: 18px; } "
                "QPushButton#btnEdgeTradingPlan:hover { background-color: #1e293b; color: #f8fafc; border: 1px solid #334155; }"
            )
        else:
            window.btn_edge_plan.setStyleSheet(
                "QPushButton#btnEdgeTradingPlan { background-color: transparent; color: #475569; border: 1px solid transparent; "
                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0 6px; min-height: 18px; max-height: 18px; } "
                "QPushButton#btnEdgeTradingPlan:hover { background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; }"
            )

    if hasattr(window, "btnChartAutoScale") and window.btnChartAutoScale:
        if is_dark:
            window.btnChartAutoScale.setStyleSheet(
                "QPushButton#btnChartAutoScale { background-color: transparent; color: #94a3b8; border: 1px solid transparent; "
                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0 6px; min-height: 18px; max-height: 18px; } "
                "QPushButton#btnChartAutoScale:hover { background-color: #1e293b; color: #ffffff; border: 1px solid #475569; }"
            )
        else:
            window.btnChartAutoScale.setStyleSheet(
                "QPushButton#btnChartAutoScale { background-color: transparent; color: #64748b; border: 1px solid transparent; "
                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0 6px; min-height: 18px; max-height: 18px; } "
                "QPushButton#btnChartAutoScale:hover { background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; }"
            )

    if hasattr(window, "lbl_ribbon_left") and window.lbl_ribbon_left:
        vpoc_val = getattr(window, "_last_vpoc", None)
        vah_val = getattr(window, "_last_vah", None)
        val_val = getattr(window, "_last_val", None)
        tpoc_val = getattr(window, "_last_tpoc", None)
        session_name = getattr(window, "_last_session", "--")
        delta_str = getattr(window, "_last_delta_str", "--")
        delta_color = getattr(window, "_last_delta_color", "#15803d" if not is_dark else "#22c55e")
        digits = getattr(window, "_last_digits", 2)

        c_lbl = "#71717a" if is_dark else "#475569"
        c_val = "#ffffff" if is_dark else "#0f172a"
        c_va = "#38bdf8" if is_dark else "#0284c7"
        c_vpoc = "#22c55e" if is_dark else "#15803d"
        c_tpoc = "#f43f5e" if is_dark else "#b91c1c"
        vpoc_str = f"{vpoc_val:,.{digits}f}" if vpoc_val is not None else "--"
        vah_str = f"{vah_val:,.{digits}f}" if vah_val is not None else "--"
        val_str = f"{val_val:,.{digits}f}" if val_val is not None else "--"
        tpoc_str = f"{tpoc_val:,.{digits}f}" if tpoc_val is not None else "--"
        session_text = (
            f'<span style="color:{c_lbl}; font-family:Consolas, monospace; font-size:8.5px;">'
            f'SESSION: <b style="color:{c_val};">{session_name}</b> &nbsp;|&nbsp; '
            f'vPOC: <b style="color:{c_vpoc};">{vpoc_str}</b> &nbsp;|&nbsp; '
            f'VAH: <b style="color:{c_va};">{vah_str}</b> &nbsp;|&nbsp; '
            f'VAL: <b style="color:{c_va};">{val_str}</b> &nbsp;|&nbsp; '
            f'tPOC: <b style="color:{c_tpoc};">{tpoc_str}</b> &nbsp;|&nbsp; '
            f'Δ: <b style="color:{delta_color};">{delta_str}</b>'
            f'</span>'
        )
        window.lbl_ribbon_left.setText(session_text)

    # Market Profile VAH / VAL / Value Area Region theme sync
    if hasattr(window, "line_vah") and window.line_vah:
        c_va = "#38bdf8" if is_dark else "#0284c7"
        va_fill = (56, 189, 248, 120) if is_dark else (224, 242, 254, 160)
        window.line_vah.setPen(pg.mkPen(color=c_va, width=1.0, style=QtCore.Qt.DashLine))
        if hasattr(window.line_vah, "label") and window.line_vah.label:
            window.line_vah.label.setColor(c_va)
            window.line_vah.label.fill = pg.mkBrush(*va_fill)
    if hasattr(window, "line_val") and window.line_val:
        c_va = "#38bdf8" if is_dark else "#0284c7"
        va_fill = (56, 189, 248, 120) if is_dark else (224, 242, 254, 160)
        window.line_val.setPen(pg.mkPen(color=c_va, width=1.0, style=QtCore.Qt.DashLine))
        if hasattr(window.line_val, "label") and window.line_val.label:
            window.line_val.label.setColor(c_va)
            window.line_val.label.fill = pg.mkBrush(*va_fill)
    if hasattr(window, "line_vpoc") and window.line_vpoc:
        c_vpoc_pen = "#10b981"
        vpoc_fill = (6, 78, 59, 160) if is_dark else (220, 252, 231, 160)
        if hasattr(window.line_vpoc, "label") and window.line_vpoc.label:
            window.line_vpoc.label.setColor(c_vpoc_pen)
            window.line_vpoc.label.fill = pg.mkBrush(*vpoc_fill)
    if hasattr(window, "line_tpoc") and window.line_tpoc:
        c_tpoc_pen = "#f43f5e"
        tpoc_fill = (127, 29, 29, 160) if is_dark else (254, 226, 226, 160)
        if hasattr(window.line_tpoc, "label") and window.line_tpoc.label:
            window.line_tpoc.label.setColor(c_tpoc_pen)
            window.line_tpoc.label.fill = pg.mkBrush(*tpoc_fill)
    if hasattr(window, "va_region") and window.va_region:
        va_brush_color = (56, 189, 248, 16) if is_dark else (2, 132, 199, 14)
        window.va_region.setBrush(pg.mkBrush(color=va_brush_color))

    # Oscillator Sub-Pane Theme Sync
    if hasattr(window, "osc_plot_widget") and window.osc_plot_widget:
        osc_bg = "#000000" if is_dark else "#f8fafc"
        window.osc_plot_widget.setBackground(osc_bg)
        osc_axis_color = "#1c2438" if is_dark else "#cbd5e1"
        osc_text_color = "#64748b" if is_dark else "#475569"
        osc_right = window.osc_plot_widget.getAxis("right")
        if osc_right:
            osc_right.setPen(pg.mkPen(color=osc_axis_color))
            osc_right.setTextPen(pg.mkPen(color=osc_text_color))
            osc_right.setWidth(55)

    if hasattr(window, "lbl_chart_zoom") and window.lbl_chart_zoom:
        zoom_color = "#71717a" if is_dark else "#64748b"
        window.lbl_chart_zoom.setText(f'<span style="color:{zoom_color}; font-family:Consolas, monospace; font-size:8.5px;">100%</span>')

    if hasattr(window, "toolbarChartDrawing") and window.toolbarChartDrawing:
        tb_bg = "#050608" if is_dark else "#f8fafc"
        tb_border = "#1c1c1c" if is_dark else "#e2e8f0"
        window.toolbarChartDrawing.setStyleSheet(f"QFrame#toolbarChartDrawing {{ background-color: {tb_bg}; border-right: 1px solid {tb_border}; border-bottom: 1px solid {tb_border}; }}")
        if hasattr(window, "btnToolProfile") and window.btnToolProfile:
            window.btnToolProfile._is_dark = is_dark
            if hasattr(window, "_get_tool_btn_style"):
                window.btnToolProfile.setStyleSheet(window._get_tool_btn_style(is_dark, is_active=False))
            window.btnToolProfile.update()
        if hasattr(window, "drawing_engine") and window.drawing_engine:
            window.drawing_engine._update_button_styles()

    # Order proposal interactive lines on chart (Unified institutional styling)
    bull_color = "#22c55e" if is_dark else "#15803D"
    bear_color = "#ef4444" if is_dark else "#B91C1C"
    is_live = getattr(window, "is_live_position", False)
    line_style = QtCore.Qt.SolidLine if is_live else QtCore.Qt.DashLine
    line_w = 1.2

    if hasattr(window, "line_order_entry") and window.line_order_entry:
        window.line_order_entry.setPen(pg.mkPen(color=bull_color, width=line_w, style=line_style))
        if hasattr(window.line_order_entry, "label") and window.line_order_entry.label:
            window.line_order_entry.label.setColor("#f8fafc")
            window.line_order_entry.label.fill = pg.mkBrush(15, 23, 42, 235)
            window.line_order_entry.label.border = pg.mkPen(color=bull_color, width=1.0)
    if hasattr(window, "line_order_sl") and window.line_order_sl:
        window.line_order_sl.setPen(pg.mkPen(color=bear_color, width=1.0, style=QtCore.Qt.DashLine))
        if hasattr(window.line_order_sl, "label") and window.line_order_sl.label:
            window.line_order_sl.label.setColor("#f8fafc")
            window.line_order_sl.label.fill = pg.mkBrush(15, 23, 42, 235)
            window.line_order_sl.label.border = pg.mkPen(color=bear_color, width=1.0)
    if hasattr(window, "line_order_tp") and window.line_order_tp:
        window.line_order_tp.setPen(pg.mkPen(color=bull_color, width=1.0, style=QtCore.Qt.DashLine))
        if hasattr(window.line_order_tp, "label") and window.line_order_tp.label:
            window.line_order_tp.label.setColor("#f8fafc")
            window.line_order_tp.label.fill = pg.mkBrush(15, 23, 42, 235)
            window.line_order_tp.label.border = pg.mkPen(color=bull_color, width=1.0)

    # Synchronize all MT5 broker order lines with active theme colors
    if hasattr(window, "sync_chart_orders"):
        try:
            window.sync_chart_orders()
        except Exception:
            pass

    # 1. Plot widget background & axes
    if hasattr(window, "plot_widget") and window.plot_widget:
        bg_color = "#000000" if is_dark else "#ffffff"
        window.plot_widget.setBackground(bg_color)
        axis_color = "#1c2438" if is_dark else "#cbd5e1"
        text_color = "#64748b" if is_dark else "#475569"

        right_axis = window.plot_widget.getAxis("right")
        if right_axis:
            right_axis.setPen(pg.mkPen(color=axis_color))
            right_axis.setTextPen(pg.mkPen(color=text_color))
            right_axis.setWidth(55)

        bottom_axis = window.plot_widget.getAxis("bottom")
        if bottom_axis:
            bottom_axis.setPen(pg.mkPen(color=axis_color))
            bottom_axis.setTextPen(pg.mkPen(color=text_color))

    # 2. Crosshair text item
    if hasattr(window, "crosshair_label") and window.crosshair_label:
        ch_text_color = "#E5E7EB" if is_dark else "#0f172a"
        ch_brush = pg.mkBrush(0, 0, 0, 150) if is_dark else pg.mkBrush(241, 245, 249, 200)
        window.crosshair_label.setColor(ch_text_color)
        window.crosshair_label.fill = ch_brush

    # 3. Chart Title / OHLC Header
    if hasattr(window, "lbl_chart_title") and window.lbl_chart_title:
        title_color = "#f8fafc" if is_dark else "#0f172a"
        window.lbl_chart_title.setStyleSheet(
            f"color: {title_color}; font-size: 10px; font-weight: 600; font-family: 'Consolas', monospace; padding: 0 4px;"
        )

    # 4. Timeframe buttons
    if hasattr(window, "update_tf_styles"):
        window.update_tf_styles(is_dark)

    # 5. Chart TF Separator
    if hasattr(window, "chart_tf_sep") and window.chart_tf_sep:
        sep_color = "#30363D" if is_dark else "#e2e8f0"
        window.chart_tf_sep.setStyleSheet(f"QFrame {{ color: {sep_color}; }}")

    # 6. Indicators button
    if hasattr(window, "btn_indicators") and window.btn_indicators:
        if is_dark:
            window.btn_indicators.setStyleSheet(
                "QPushButton { background-color: transparent; color: #D1D4DC; border: none; font-weight: bold; padding: 6px 12px; } QPushButton:hover { background-color: #2B3139; border-radius: 4px; }"
            )
        else:
            window.btn_indicators.setStyleSheet(
                "QPushButton { background-color: transparent; color: #334155; border: none; font-weight: bold; padding: 6px 12px; } QPushButton:hover { background-color: #e2e8f0; border-radius: 4px; }"
            )

    # 7. AI Reasoning Card
    update_ai_reasoning(window, is_dark)

    # 8. Watchlist toggle button
    if hasattr(window, "btn_toggle_watchlist") and window.btn_toggle_watchlist:
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets")
        if not os.path.exists(assets_dir):
            assets_dir = os.path.join(os.path.dirname(__file__), "assets")
        icon_name = "sidebar_toggle_dark.svg" if is_dark else "sidebar_toggle_light.svg"
        window.btn_toggle_watchlist.setIcon(QIcon(os.path.join(assets_dir, icon_name)))
        window.btn_toggle_watchlist.setIconSize(QSize(16, 16))
        if is_dark:
            window.btn_toggle_watchlist.setStyleSheet(
                "QPushButton { background-color: #101524; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 4px; } QPushButton:hover { background-color: #161d31; border-color: #71717a; }"
            )
        else:
            window.btn_toggle_watchlist.setStyleSheet(
                "QPushButton { background-color: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 4px; } QPushButton:hover { background-color: #e2e8f0; border-color: #71717a; }"
            )

