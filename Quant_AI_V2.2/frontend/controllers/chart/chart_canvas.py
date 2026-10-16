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
from PySide6.QtCore import Qt, QTimer, QSize, QPointF, QEvent, QObject
from PySide6.QtGui import (
    QColor, QFont, QIcon, QPainter, QPicture, QCursor,
    QKeySequence, QShortcut
)
from PySide6.QtWidgets import (
    QFrame, QLabel, QHBoxLayout, QVBoxLayout, QPushButton,
    QWidget, QGraphicsRectItem, QMenu, QMessageBox, QTableWidgetItem
)

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

def setup_chart_ui(window):
    chart_layout = window.frameChartArea.layout()

    while chart_layout.count():
        item = chart_layout.takeAt(0)
        w = item.widget()
        if w:
            w.deleteLater()

    chart_layout.setContentsMargins(0, 0, 0, 0)
    chart_layout.setSpacing(0)

    assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend", "assets")
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
        window.frameAIArea.setMinimumSize(275, 0)
        window.frameAIArea.setMaximumSize(310, 500)

    def _reposition_trading_plan():
        if not hasattr(window, "frameAIArea") or not window.frameAIArea:
            return
        if not hasattr(window, "frameChartArea") or not window.frameChartArea:
            return
        w = 285
        c_w = window.frameChartArea.width()
        c_h = window.frameChartArea.height()
        x = max(10, c_w - w - 10)
        ribbon_h = window.frameChartRibbon.height() if hasattr(window, "frameChartRibbon") and window.frameChartRibbon else 24
        y = ribbon_h + 8
        h = min(365, max(200, c_h - y - 10))
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

    def _open_ai_drawer():
        if hasattr(window, "frameAIArea") and window.frameAIArea:
            window.frameAIArea.setVisible(True)
            _reposition_trading_plan()
        if hasattr(window, "btn_edge_plan") and window.btn_edge_plan:
            window.btn_edge_plan.setVisible(False)

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

    window.time_axis = TimeAxisItem(orientation="bottom")

    window.plot_widget = pg.PlotWidget(
        background="#000000", axisItems={"bottom": window.time_axis}
    )

    window.plot_widget.setMouseEnabled(x=True, y=False)

    window.plot_widget.showGrid(x=True, y=True, alpha=0.06)
    window.plot_widget.getPlotItem().hideButtons()

    window.plot_widget.showAxis("right")
    window.plot_widget.hideAxis("left")
    window.plot_widget.getAxis("right").setPen(pg.mkPen(color="#1c2438"))
    window.plot_widget.getAxis("bottom").setPen(pg.mkPen(color="#1c2438"))
    window.plot_widget.getAxis("right").setTextPen(pg.mkPen(color="#64748b"))
    window.plot_widget.getAxis("bottom").setTextPen(pg.mkPen(color="#64748b"))
    window.plot_widget.getAxis("right").setWidth(55)

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
            window.mainSplitter.setSizes([260, 1180])
        btn_edge_wl.setVisible(False)

    btn_edge_wl.clicked.connect(_expand_wl_from_ribbon)
    btn_edge_wl.setVisible(False)
    window.btn_edge_wl = btn_edge_wl
    ribbon_layout.addWidget(btn_edge_wl)

    lbl_ribbon_left = QLabel(
        '<span style="font-family:Consolas, monospace; font-size:9px; color:#71717a;">'
        'SESSION: <b style="color:#ffffff;">ASIAN</b> &nbsp;|&nbsp; '
        'vPOC: <b style="color:#22c55e;">2,679.7</b> &nbsp;|&nbsp; '
        'tPOC: <b style="color:#ef4444;">2,685.7</b> &nbsp;|&nbsp; '
        'DELTA: <b style="color:#22c55e;">+14.2k</b>'
        '</span>'
    )
    ribbon_layout.addWidget(lbl_ribbon_left)

    lbl_chart_ohlc = QLabel(
        '<span style="font-family:Consolas, monospace; font-size:9px; color:#64748b;">'
        'O: <b style="color:#f8fafc;">--</b> &nbsp;'
        'H: <b style="color:#f8fafc;">--</b> &nbsp;'
        'L: <b style="color:#f8fafc;">--</b> &nbsp;'
        'C: <b style="color:#f8fafc;">--</b> &nbsp;'
        '<b style="color:#22c55e;">+0.00%</b>'
        '</span>'
    )
    window.lbl_chart_ohlc = lbl_chart_ohlc
    ribbon_layout.addWidget(lbl_chart_ohlc)
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

    lbl_live_badge = QLabel('<span style="color:#22c55e; font-family:Consolas, monospace; font-size:8.5px; font-weight:bold;">LIVE (UTC)</span>')
    ribbon_layout.addWidget(lbl_live_badge)

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
    window.lbl_chart_live_badge = lbl_live_badge

    # Vertical Drawing Toolbar (width: 26px) - Institutional Interactive Chart Controls
    toolbar_draw = QFrame()
    toolbar_draw.setObjectName("toolbarChartDrawing")
    toolbar_draw.setFixedWidth(26)
    is_d_init = getattr(window, "is_dark_theme", False)
    tb_bg_init = "#050608" if is_d_init else "#f8fafc"
    tb_bdr_init = "#1c1c1c" if is_d_init else "#e2e8f0"
    toolbar_draw.setStyleSheet(f"QFrame#toolbarChartDrawing {{ background-color: {tb_bg_init}; border-right: 1px solid {tb_bdr_init}; }}")
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

    # 4. Ruler / Measurement Tool Button
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
    window._get_tool_btn_style = _get_tool_btn_style

    drawing_engine.set_toolbar_buttons(btn_crosshair, btn_poc, btn_fvg, btn_ruler, btn_gear, btn_clear)

    # Horizontal row containing vertical toolbar and plot widget
    chart_canvas_row = QWidget()
    canvas_row_layout = QHBoxLayout(chart_canvas_row)
    canvas_row_layout.setContentsMargins(0, 0, 0, 0)
    canvas_row_layout.setSpacing(0)
    canvas_row_layout.addWidget(toolbar_draw)
    canvas_row_layout.addWidget(window.plot_widget)

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
        if hasattr(window, "quant_terminal") and hasattr(window.quant_terminal, "settings"):
            window.quant_terminal.settings.open_options_dialog()
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

    # Phím tắt toàn cục F5 làm mới biểu đồ và quét lại kết nối MT5
    shortcut_f5 = QtGui.QShortcut(QtGui.QKeySequence("F5"), window)
    shortcut_f5.activated.connect(lambda: window.draw_and_analyze(getattr(window, "current_sym", "XAUUSD")))
    window.shortcut_f5 = shortcut_f5

    # Add Crosshair lines
    window.vLine = pg.InfiniteLine(
        angle=90, movable=False, pen=pg.mkPen("#475569", style=QtCore.Qt.DashLine)
    )

    window.hLine = pg.InfiniteLine(
        angle=0, movable=False, pen=pg.mkPen("#475569", style=QtCore.Qt.DashLine)
    )

    window.plot_widget.addItem(window.vLine, ignoreBounds=True)
    window.plot_widget.addItem(window.hLine, ignoreBounds=True)

    # Crosshair text label
    window.crosshair_label = pg.TextItem(
        color="#E5E7EB", anchor=(0, 1), fill=pg.mkBrush(0, 0, 0, 150)
    )
    window.crosshair_label.setZValue(10)  # ensure it's on top
    window.plot_widget.addItem(window.crosshair_label, ignoreBounds=True)

    # Current price line - 1px dashed institutional silver
    window.current_price_line = pg.InfiniteLine(
        angle=0, movable=False, pen=pg.mkPen("#cbd5e1", width=1.0, style=QtCore.Qt.DashLine)
    )
    window.plot_widget.addItem(window.current_price_line, ignoreBounds=True)

    # Institutional Signal Threads: 1px tPOC (#ef4444) and 1px vPOC (#10b981)
    window.line_tpoc = pg.InfiniteLine(
        angle=0, movable=False,
        pen=pg.mkPen(color="#ef4444", width=1.0, style=QtCore.Qt.SolidLine),
        label="tPOC",
        labelOpts={"color": "#b91c1c", "position": 0.98, "fill": "#fee2e2", "border": "#b91c1c"}
    )
    window.line_vpoc = pg.InfiniteLine(
        angle=0, movable=False,
        pen=pg.mkPen(color="#22c55e", width=1.0, style=QtCore.Qt.SolidLine),
        label="vPOC",
        labelOpts={"color": "#15803d", "position": 0.98, "fill": "#dcfce7", "border": "#15803d"}
    )
    window.plot_widget.addItem(window.line_tpoc, ignoreBounds=True)
    window.plot_widget.addItem(window.line_vpoc, ignoreBounds=True)

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
        pen=pg.mkPen(color="#22c55e", width=1.5),
        label="BUY ORDER: --",
        labelOpts={"color": "#22c55e", "position": 0.25, "fill": (0, 0, 0, 180)}
    )
    window.line_order_sl = pg.InfiniteLine(
        angle=0, movable=True, pos=0.0,
        pen=pg.mkPen(color="#ef4444", width=1.5),
        label="STOP LOSS: --",
        labelOpts={"color": "#ef4444", "position": 0.25, "fill": (0, 0, 0, 180)}
    )
    window.line_order_tp = pg.InfiniteLine(
        angle=0, movable=True, pos=0.0,
        pen=pg.mkPen(color="#22c55e", width=1.5),
        label="TAKE PROFIT: --",
        labelOpts={"color": "#22c55e", "position": 0.25, "fill": (0, 0, 0, 180)}
    )

    def _sync_order_metrics():
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
        if "BTC" in sym:
            risk_dlr = sl_pts * 0.50
            reward_dlr = tp_pts * 0.50
        elif "XAU" in sym:
            risk_dlr = sl_pts * 50.0
            reward_dlr = tp_pts * 50.0
        elif "JPY" in sym:
            risk_dlr = sl_pts * 1000 * 0.50 * 0.07
            reward_dlr = tp_pts * 1000 * 0.50 * 0.07
        else:
            risk_dlr = sl_pts * 50000.0
            reward_dlr = tp_pts * 50000.0
        risk_pct = (risk_dlr / 100000.0) * 100.0
        rr_ratio = (tp_pts / sl_pts) if sl_pts > 0.00001 else 1.0

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
            status="WAITING OPERATOR APPROVAL" if is_waiting else "EXECUTED & FILLED",
            digits=dig,
        )

    window.line_order_sl.sigPositionChanged.connect(lambda: _sync_order_metrics())
    window.line_order_tp.sigPositionChanged.connect(lambda: _sync_order_metrics())

    def _on_approve():
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
        if "BTC" in sym:
            risk_dlr = sl_pts * 0.50
            reward_dlr = tp_pts * 0.50
        elif "XAU" in sym:
            risk_dlr = sl_pts * 50.0
            reward_dlr = tp_pts * 50.0
        elif "JPY" in sym:
            risk_dlr = sl_pts * 1000 * 0.50 * 0.07
            reward_dlr = tp_pts * 1000 * 0.50 * 0.07
        else:
            risk_dlr = sl_pts * 50000.0
            reward_dlr = tp_pts * 50000.0
        risk_pct = (risk_dlr / 100000.0) * 100.0
        rr_ratio = (tp_pts / sl_pts) if sl_pts > 0.00001 else 1.0

        # Determine direction
        is_buy = True
        if hasattr(window, "lblOrderTypeBadge") and "SELL" in window.lblOrderTypeBadge.text().upper():
            is_buy = False
        elif tp_p < entry_p:
            is_buy = False

        # Calculate lot size
        lot_size = 0.05 if "BTC" in sym else (0.10 if "XAU" in sym else 0.50)
        if hasattr(window, "lblSizeVal") and window.lblSizeVal:
            try:
                lot_size = float(window.lblSizeVal.text().split()[0])
            except Exception:
                pass

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
                    try:
                        window.plot_widget.removeItem(getattr(window, l_name))
                    except Exception:
                        pass
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

    def _on_modify():
        if hasattr(window, "line_order_entry"):
            window.line_order_entry.setMovable(True)
        if hasattr(window, "line_order_sl"):
            window.line_order_sl.setMovable(True)
        if hasattr(window, "line_order_tp"):
            window.line_order_tp.setMovable(True)
        if hasattr(window, "lblSignalExpiry"):
            window.lblSignalExpiry.setText("DRAG SL / TP LINES ON CHART TO ADJUST")
            window.lblSignalExpiry.setStyleSheet("color: #0284c7; font-family: 'Consolas', monospace; font-size: 9.5px; font-weight: bold;")
        if hasattr(window, "btnApproveOrder"):
            window.btnApproveOrder.setText("APPROVE ORDER (MODIFIED)")
            window.btnApproveOrder.setEnabled(True)

    def _on_discard():
        window.order_proposal_active = False
        if hasattr(window, "line_order_entry"):
            try: window.plot_widget.removeItem(window.line_order_entry)
            except Exception: pass
        if hasattr(window, "line_order_sl"):
            try: window.plot_widget.removeItem(window.line_order_sl)
            except Exception: pass
        if hasattr(window, "line_order_tp"):
            try: window.plot_widget.removeItem(window.line_order_tp)
            except Exception: pass
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

                    dt_str = datetime.fromtimestamp(t_val).strftime("%d/%m %H:%M")

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

                    window.crosshair_label.setText(f"{y:{fmt}}")
                    if x > len(window.chart_data_list) - 30:
                        window.crosshair_label.setAnchor((1, 1))
                    else:
                        window.crosshair_label.setAnchor((0, 1))
                    window.crosshair_label.setPos(x, label_y)

            is_cross_mode = True
            if hasattr(window, "drawing_engine") and window.drawing_engine:
                is_cross_mode = (window.drawing_engine.mode == ChartDrawingEngine.MODE_CROSSHAIR)

            if getattr(window, "_crosshair_enabled", True) and is_cross_mode:
                window.vLine.setPos(x)
                window.hLine.setPos(y)
                window.vLine.setVisible(True)
                window.hLine.setVisible(True)
                window.crosshair_label.setVisible(True)
            else:
                window.vLine.setVisible(False)
                window.hLine.setVisible(False)
                window.crosshair_label.setVisible(False)

    window.plot_widget.scene().sigMouseMoved.connect(mouseMoved)

    # Live chart update

    def on_market_tick(sym, bid, ask):

        clean_curr = getattr(window, "current_sym", "").split("\n")[0].strip()
        if not clean_curr or sym != clean_curr:

            return

        window.current_price_line.setPos(bid)

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

                changed = True

            elif r["time"] > last_time:

                new_idx = last_idx + 1

                window.chart_data_list.append(
                    (new_idx, r["open"], r["close"], r["low"], r["high"])
                )

                window.time_axis.timestamps.append(r["time"])

                changed = True

            if changed and hasattr(window, "candlesticks"):

                window.candlesticks.data = window.chart_data_list

                window.candlesticks.generatePicture()

                window.candlesticks.update()

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
        from PySide6.QtWidgets import QMenu
        menu = QMenu(window.plot_widget)
        menu.setStyleSheet(
            "QMenu { background-color: #0c0c0c; color: #cbd5e1; border: 1px solid #1c1c1c; "
            "font-family: 'Consolas', monospace; font-size: 11px; padding: 4px; } "
            "QMenu::item { padding: 4px 14px; } "
            "QMenu::item:selected { background-color: #262626; color: #ffffff; border-radius: 2px; }"
        )

        tf_menu = menu.addMenu("TIMEFRAME")
        tfs = [
            ("M1", mt5.TIMEFRAME_M1), ("M5", mt5.TIMEFRAME_M5), ("M15", mt5.TIMEFRAME_M15),
            ("M30", mt5.TIMEFRAME_M30), ("H1", mt5.TIMEFRAME_H1), ("H4", mt5.TIMEFRAME_H4),
            ("D1", mt5.TIMEFRAME_D1),
        ]
        for tf_n, tf_v in tfs:
            prefix = "[x] " if tf_n == window.current_tf_str else "    "
            act = tf_menu.addAction(f"{prefix}{tf_n}")
            act.triggered.connect(lambda chk=False, v=tf_v, n=tf_n: change_timeframe(v, n))

        menu.addSeparator()
        act_ind = menu.addAction("INDICATORS...")
        act_ind.triggered.connect(lambda: _open_indicators() if hasattr(window, "open_indicators") else None)
        menu.exec(window.plot_widget.mapToGlobal(pos))

    window.plot_widget.setContextMenuPolicy(Qt.CustomContextMenu)
    window.plot_widget.customContextMenuRequested.connect(_show_chart_context_menu)

    def change_timeframe(val, name_str):
        window.current_tf = val
        window.current_tf_str = name_str
        if hasattr(window, "update_tf_styles"):
            try:
                window.update_tf_styles()
            except Exception:
                pass
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
                        except Exception:
                            pass
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

        is_d = getattr(window, "is_dark_theme", False)
        window.candlesticks = CandlestickItem(window.chart_data_list, is_dark=is_d)
        window.plot_widget.addItem(window.candlesticks)

        # Tự động nhận diện và vẽ các dải kênh FVG (Fair Value Gap)
        if hasattr(window, "drawing_engine") and window.drawing_engine:
            window.drawing_engine.fvg_items.clear()
        if len(window.chart_data_list) >= 15:
            total_n = len(window.chart_data_list)
            fvg_zones = []
            fvg_threshold = cur_p * 0.0003
            for i in range(5, total_n - 5):
                t_cur, _, _, l_cur, h_cur = window.chart_data_list[i]
                t_prev2, _, _, l_prev2, h_prev2 = window.chart_data_list[i - 2]
                if l_cur > h_prev2 and (l_cur - h_prev2) > fvg_threshold:
                    fvg_zones.append(('bull', t_prev2, h_prev2, l_cur, l_cur - h_prev2))
                elif h_cur < l_prev2 and (l_prev2 - h_cur) > fvg_threshold:
                    fvg_zones.append(('bear', t_prev2, l_prev2, h_cur, l_prev2 - h_cur))

            fvg_zones.sort(key=lambda z: z[4], reverse=True)
            fvg_vis = getattr(window, "_fvg_visible", True)
            for z_type, t_start, y1, y2, _ in fvg_zones[:3]:
                top_y = max(y1, y2)
                bot_y = min(y1, y2)
                box_width = (total_n - t_start + 12)
                fvg_item = QGraphicsRectItem(t_start, bot_y, box_width, top_y - bot_y)
                fvg_item.setBrush(pg.mkBrush(217, 119, 6, 40))
                fvg_item.setPen(pg.mkPen(color=pg.mkColor(217, 119, 6, 140), width=1, style=QtCore.Qt.SolidLine))
                fvg_item.setVisible(fvg_vis)
                window.plot_widget.addItem(fvg_item)

                fvg_text = "FVG (Bullish Liquidity)" if z_type == 'bull' else "FVG (Session Premium Supply)"
                fvg_lbl = pg.TextItem(text=fvg_text, color=(245, 158, 11, 220), anchor=(0, 0.5))
                fvg_lbl.setFont(QFont("Consolas", 9, QFont.Bold))
                fvg_lbl.setPos(t_start + 1, (top_y + bot_y) / 2)
                fvg_lbl.setVisible(fvg_vis)
                window.plot_widget.addItem(fvg_lbl)

                if hasattr(window, "drawing_engine") and window.drawing_engine:
                    window.drawing_engine.fvg_items.extend([fvg_item, fvg_lbl])

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

        # Calculate and update tPOC and vPOC
        close_prices = [float(r["close"]) for r in rates[-100:]]
        vols = [float(r["tick_volume"]) for r in rates[-100:]]
        if close_prices:
            tot_vol = max(1.0, sum(vols))
            vpoc_val = sum(p * v for p, v in zip(close_prices, vols)) / tot_vol
            tpoc_val = float(np.median(close_prices))
            poc_vis = getattr(window, "_poc_visible", True)
            if hasattr(window, "line_vpoc"):
                window.line_vpoc.setValue(vpoc_val)
                window.line_vpoc.setVisible(poc_vis)
            if hasattr(window, "line_tpoc"):
                window.line_tpoc.setValue(tpoc_val)
                window.line_tpoc.setVisible(poc_vis)

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
            window._last_tpoc = tpoc_val
            window._last_session = session_name
            window._last_delta_str = delta_str
            window._last_delta_color = delta_color
            window._last_digits = digits

            if hasattr(window, "lbl_ribbon_left") and window.lbl_ribbon_left:
                c_lbl = "#71717a" if is_d else "#475569"
                c_val = "#ffffff" if is_d else "#0f172a"
                sess_prefix = f'SESSION: <b style="color:{c_val};">{session_name}</b> &nbsp;|&nbsp; ' if not is_cached_fallback else f'<b style="color:#d97706;">OFFLINE CACHE ({cached_info_str})</b> &nbsp;|&nbsp; '
                window.lbl_ribbon_left.setText(
                    f'<span style="color:{c_lbl}; font-family:Consolas, monospace; font-size:8.5px;">'
                    f'{sess_prefix}'
                    f'vPOC: <b style="color:{c_val};">{vpoc_val:,.{digits}f}</b> &nbsp;|&nbsp; '
                    f'tPOC: <b style="color:{c_val};">{tpoc_val:,.{digits}f}</b> &nbsp;|&nbsp; '
                    f'DELTA: <b style="color:{delta_color};">{delta_str}</b>'
                    f'</span>'
                )

        # Gỡ bỏ toàn bộ đường lệnh ảo cũ khi tải lại biểu đồ hoặc chuyển mã
        for line_name in ("line_order_entry", "line_order_sl", "line_order_tp"):
            if hasattr(window, line_name):
                l_obj = getattr(window, line_name)
                if l_obj is not None:
                    try:
                        window.plot_widget.removeItem(l_obj)
                    except Exception:
                        pass
        window.order_proposal_active = False

        strat_display_name = "Quant Strategy"
        try:
            from backend.core.strategies.strategy_loader import discover_strategies
            with open("config/settings.json", "r", encoding="utf-8") as f_cfg:
                cfg_s = json.load(f_cfg)
                strat_saved = cfg_s.get("strategy", "builtin_ict_pro")
                for s in discover_strategies():
                    if s["id"] == strat_saved or s["name"].lower() == str(strat_saved).lower():
                        strat_display_name = s["name"].split("(")[0].strip()
                        break
                else:
                    if "ema" in strat_saved.lower():
                        strat_display_name = "EMA Dual Cross"
                    elif "wyckoff" in strat_saved.lower():
                        strat_display_name = "Wyckoff Momentum Pro"
                    else:
                        strat_display_name = "ICT Zones Pro v4.2"
        except Exception:
            strat_display_name = "ICT Zones Pro v4.2"

        update_order_proposal_html(
            window,
            sym=sym,
            has_signal=False,
            model_name=strat_display_name,
            digits=digits,
        )

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
        vpoc_val = getattr(window, "_last_vpoc", 2680.0)
        tpoc_val = getattr(window, "_last_tpoc", 2680.0)
        session_name = getattr(window, "_last_session", "LONDON SESSION")
        delta_str = getattr(window, "_last_delta_str", "+14.2k (Absorption)")
        delta_color = getattr(window, "_last_delta_color", "#15803d")
        digits = getattr(window, "_last_digits", 2)

        c_lbl = "#71717a" if is_dark else "#475569"
        c_val = "#ffffff" if is_dark else "#0f172a"
        session_text = (
            f'<span style="color:{c_lbl}; font-family:Consolas, monospace; font-size:8.5px;">'
            f'SESSION: <b style="color:{c_val};">{session_name}</b> &nbsp;|&nbsp; '
            f'vPOC: <b style="color:{c_val};">{vpoc_val:,.{digits}f}</b> &nbsp;|&nbsp; '
            f'tPOC: <b style="color:{c_val};">{tpoc_val:,.{digits}f}</b> &nbsp;|&nbsp; '
            f'DELTA: <b style="color:{delta_color};">{delta_str}</b>'
            f'</span>'
        )
        window.lbl_ribbon_left.setText(session_text)

    if hasattr(window, "lbl_chart_zoom") and window.lbl_chart_zoom:
        zoom_color = "#71717a" if is_dark else "#64748b"
        window.lbl_chart_zoom.setText(f'<span style="color:{zoom_color}; font-family:Consolas, monospace; font-size:8.5px;">100%</span>')

    if hasattr(window, "toolbarChartDrawing") and window.toolbarChartDrawing:
        tb_bg = "#050608" if is_dark else "#f8fafc"
        tb_border = "#1c1c1c" if is_dark else "#e2e8f0"
        window.toolbarChartDrawing.setStyleSheet(f"QFrame#toolbarChartDrawing {{ background-color: {tb_bg}; border-right: 1px solid {tb_border}; }}")
        if hasattr(window, "drawing_engine") and window.drawing_engine:
            window.drawing_engine._update_button_styles()

    # Order proposal interactive lines on chart
    fill_rgba = (0, 0, 0, 180) if is_dark else (241, 245, 249, 230)
    bull_color = "#22c55e" if is_dark else "#15803D"
    bear_color = "#ef4444" if is_dark else "#B91C1C"
    if hasattr(window, "line_order_entry") and window.line_order_entry:
        window.line_order_entry.setPen(pg.mkPen(color=bull_color, width=1.5))
        if hasattr(window.line_order_entry, "label") and window.line_order_entry.label:
            window.line_order_entry.label.setColor(bull_color)
            window.line_order_entry.label.fill = pg.mkBrush(*fill_rgba)
    if hasattr(window, "line_order_sl") and window.line_order_sl:
        window.line_order_sl.setPen(pg.mkPen(color=bear_color, width=1.5))
        if hasattr(window.line_order_sl, "label") and window.line_order_sl.label:
            window.line_order_sl.label.setColor(bear_color)
            window.line_order_sl.label.fill = pg.mkBrush(*fill_rgba)
    if hasattr(window, "line_order_tp") and window.line_order_tp:
        window.line_order_tp.setPen(pg.mkPen(color=bull_color, width=1.5))
        if hasattr(window.line_order_tp, "label") and window.line_order_tp.label:
            window.line_order_tp.label.setColor(bull_color)
            window.line_order_tp.label.fill = pg.mkBrush(*fill_rgba)

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
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend", "assets")
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

