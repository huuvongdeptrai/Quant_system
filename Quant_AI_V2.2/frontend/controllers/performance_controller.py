"""
Quant Terminal V2.2 - Institutional Stats Manager
Austere Tiled-Grid Architecture (Zero Wasted Space):
- 3-Column Seamless Tiled Matrix (Calendar + Ledger | Dual Equity/Drawdown | 16 Quant Metrics)
- TradeZella-style PnL calendar powered by TradeZellaCalendarDelegate (270px compact)
- Dense Closed Trades Ledger (22px row height, monospace, 15-20 rows visible)
- Dual pyqtgraph plot: Equity Growth Trajectory (70%) + Underwater Drawdown Subplot (30%)
- Quantitative Metrics Matrix: 16 institutional metrics in a compact 2-column format
"""

import os
import csv
import math
import calendar
from datetime import datetime
from typing import List, Dict, Any

import pyqtgraph as pg
from PySide6.QtWidgets import (
    QTableWidgetItem, QHeaderView, QWidget, QHBoxLayout,
    QVBoxLayout, QLabel, QMessageBox, QFileDialog, QAbstractItemView,
    QFrame, QSizePolicy, QScrollArea
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
import numpy as np
from backend.infrastructure.brokers.mt5_safe import mt5

from backend.core.stats_engine import StatsEngine
from frontend.styling.formatters import fmt_currency, fmt_percent, fmt_pips, fmt_volume, fmt_number, fmt_timestamp
from frontend.styling.theme_engine import ThemeEngine
from frontend.widgets.delegates import TradeZellaCalendarDelegate, TableBadgeDelegate


from frontend.controllers.stats.pnl_calendar_controller import PnlCalendarController
from frontend.controllers.stats.performance_charts import PerformanceChartsController, DollarAxisItem, PercentAxisItem

class StatsManager:
    def __init__(self, window):
        self.window = window
        self.engine = StatsEngine()
        self.current_cal_date = datetime.now()
        self.cal_ctrl = PnlCalendarController(self)
        self.charts_ctrl = PerformanceChartsController(self)
        self.is_dark_theme = True
        self.cached_trades = []
        self.cached_stats = {}
        self.metric_labels: Dict[str, QLabel] = {}

        self._restructure_tab2_layout()
        self._setup_charts()
        self._setup_calendar_table()
        self._setup_history_table()
        self._bind_events()
        self.refresh_stats()

    def _restructure_tab2_layout(self):
        """Restructure Tab 2 from legacy vertical scroll area into an Austere 3-Column Tiled Grid."""
        if not hasattr(self.window, "tab3"):
            return

        tab3 = self.window.tab3
        frame_cal = getattr(self.window, "framePnlCalendar", None)
        frame_trades = getattr(self.window, "frameClosedTrades", None)
        frame_equity = getattr(self.window, "frameEquityChart", None)
        frame_metrics = getattr(self.window, "frameQuantMetrics", None)
        scroll_area = getattr(self.window, "scrollAreaStatsMain", None)

        if scroll_area:
            scroll_area.setVisible(False)

        main_layout = tab3.layout()
        if main_layout is None:
            main_layout = QHBoxLayout(tab3)
        else:
            while main_layout.count():
                main_layout.takeAt(0)

        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(2)

        # =========================================================================
        # COLUMN 1: PnL Calendar Heatmap + Closed Trades Ledger (Width: 320-400px)
        # =========================================================================
        col1 = QWidget(tab3)
        col1.setMinimumWidth(320)
        col1.setMaximumWidth(400)
        col1_layout = QVBoxLayout(col1)
        col1_layout.setContentsMargins(0, 0, 0, 0)
        col1_layout.setSpacing(2)

        if frame_cal:
            frame_cal.setTitle("")
            frame_cal.setParent(col1)
            frame_cal.setMaximumHeight(310)
            frame_cal.setMinimumHeight(180)
            if frame_cal.layout():
                frame_cal.layout().setContentsMargins(6, 6, 6, 6)
                frame_cal.layout().setSpacing(2)
            col1_layout.addWidget(frame_cal)
        if frame_trades:
            frame_trades.setTitle("")
            frame_trades.setParent(col1)
            frame_trades.setMinimumHeight(100)
            if hasattr(self.window, "tableHistory"):
                self.window.tableHistory.setMinimumHeight(80)
            if frame_trades.layout():
                frame_trades.layout().setContentsMargins(6, 6, 6, 6)
                frame_trades.layout().setSpacing(2)
            col1_layout.addWidget(frame_trades, 1)

        main_layout.addWidget(col1)

        # =========================================================================
        # COLUMN 2: Dual Plot Pane (Equity Growth Trajectory + Underwater Drawdown)
        # =========================================================================
        col2 = QWidget(tab3)
        col2_layout = QVBoxLayout(col2)
        col2_layout.setContentsMargins(0, 0, 0, 0)
        col2_layout.setSpacing(2)

        # Container for Equity Growth
        self.frame_equity_plot = QFrame(col2)
        self.frame_equity_plot.setObjectName("frameEquityPlot")
        self.frame_equity_plot.setMinimumHeight(100)
        self.frame_equity_plot.setStyleSheet(
            "QFrame#frameEquityPlot { background-color: #000000; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 0px; }"
        )
        equity_vbox = QVBoxLayout(self.frame_equity_plot)
        equity_vbox.setContentsMargins(0, 0, 0, 0)
        equity_vbox.setSpacing(0)

        # Header strip for Equity Curve
        self.header_equity = QFrame()
        self.header_equity.setFixedHeight(26)
        self.header_equity.setStyleSheet(
            "background-color: #040609; border-bottom: 1px solid rgba(255, 255, 255, 0.08);"
        )
        h_eq_l = QHBoxLayout(self.header_equity)
        h_eq_l.setContentsMargins(8, 0, 8, 0)
        lbl_eq_title = QLabel("EQUITY GROWTH CURVE")
        lbl_eq_title.setStyleSheet(
            "color: #94a3b8; font-family: 'Consolas', monospace; font-size: 10px; font-weight: 700; letter-spacing: 0.5px;"
        )
        self.lbl_eq_title = lbl_eq_title
        h_eq_l.addWidget(lbl_eq_title)
        h_eq_l.addStretch()

        self.lbl_equity_status = QLabel("INIT: $100k | CURRENT: $100k | PEAK: $100k")
        self.lbl_equity_status.setStyleSheet(
            "color: #64748b; font-family: 'Consolas', monospace; font-size: 10px;"
        )
        h_eq_l.addWidget(self.lbl_equity_status)
        equity_vbox.addWidget(self.header_equity)

        self.widget_equity_plot = QWidget()
        equity_vbox.addWidget(self.widget_equity_plot, 1)
        col2_layout.addWidget(self.frame_equity_plot, 7)

        # Container for Underwater Drawdown
        self.frame_drawdown_plot = QFrame(col2)
        self.frame_drawdown_plot.setObjectName("frameDrawdownPlot")
        self.frame_drawdown_plot.setMinimumHeight(70)
        self.frame_drawdown_plot.setStyleSheet(
            "QFrame#frameDrawdownPlot { background-color: #020305; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 0px; }"
        )
        dd_vbox = QVBoxLayout(self.frame_drawdown_plot)
        dd_vbox.setContentsMargins(0, 0, 0, 0)
        dd_vbox.setSpacing(0)

        # Header strip for Drawdown
        self.header_dd = QFrame()
        self.header_dd.setFixedHeight(24)
        self.header_dd.setStyleSheet(
            "background-color: #040609; border-bottom: 1px solid rgba(255, 255, 255, 0.08);"
        )
        h_dd_l = QHBoxLayout(self.header_dd)
        h_dd_l.setContentsMargins(8, 0, 8, 0)
        lbl_dd_title = QLabel("UNDERWATER DRAWDOWN (%)")
        lbl_dd_title.setStyleSheet(
            "color: #94a3b8; font-family: 'Consolas', monospace; font-size: 9.5px; font-weight: 700; letter-spacing: 0.5px;"
        )
        self.lbl_dd_title = lbl_dd_title
        h_dd_l.addWidget(lbl_dd_title)
        h_dd_l.addStretch()

        self.lbl_drawdown_status = QLabel("MAX DD: 0.00% | CURRENT: 0.00%")
        self.lbl_drawdown_status.setStyleSheet(
            "color: #64748b; font-family: 'Consolas', monospace; font-size: 9.5px;"
        )
        h_dd_l.addWidget(self.lbl_drawdown_status)
        dd_vbox.addWidget(self.header_dd)

        self.widget_drawdown_plot = QWidget()
        dd_vbox.addWidget(self.widget_drawdown_plot, 1)
        col2_layout.addWidget(self.frame_drawdown_plot, 3)

        main_layout.addWidget(col2, 1)

        # Hide legacy frameEquityChart if present
        if frame_equity:
            frame_equity.setVisible(False)

        # =========================================================================
        # COLUMN 3: Quantitative Metrics Matrix (Width: 320px, Scrollable)
        # =========================================================================
        col3 = QWidget(tab3)
        col3.setFixedWidth(320)
        col3_layout = QVBoxLayout(col3)
        col3_layout.setContentsMargins(0, 0, 0, 0)
        col3_layout.setSpacing(0)

        if frame_metrics:
            frame_metrics.setMaximumWidth(16777215)
            frame_metrics.setMinimumWidth(0)
            frame_metrics.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            self.frame_metrics = frame_metrics
            self._rebuild_metrics_matrix(frame_metrics)
            scroll_metrics = QScrollArea(col3)
            scroll_metrics.setObjectName("scrollAreaQuantMetrics")
            scroll_metrics.setWidget(frame_metrics)
            scroll_metrics.setWidgetResizable(True)
            scroll_metrics.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            scroll_metrics.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll_metrics.setFrameShape(QFrame.NoFrame)
            scroll_metrics.setStyleSheet(
                "QScrollArea#scrollAreaQuantMetrics { border: none; background: transparent; }"
            )
            self.scroll_metrics = scroll_metrics
            col3_layout.addWidget(scroll_metrics, 1)

        main_layout.addWidget(col3)

    def _rebuild_metrics_matrix(self, frame_metrics: QFrame):
        """Restructure frameQuantMetrics into a dense 2-column institutional matrix."""
        is_dark = getattr(self, "is_dark_theme", True)
        frame_metrics.setTitle("")
        f_bg = "#000000" if is_dark else "#ffffff"
        f_border = "rgba(255, 255, 255, 0.08)" if is_dark else "#cbd5e1"
        frame_metrics.setStyleSheet(
            f"QGroupBox#frameQuantMetrics {{ background-color: {f_bg}; border: 1px solid {f_border}; "
            "border-radius: 0px; margin-top: 0px; padding: 0px; }"
        )

        matrix_layout = frame_metrics.layout()
        if matrix_layout is None:
            matrix_layout = QVBoxLayout(frame_metrics)
        else:
            while matrix_layout.count():
                item = matrix_layout.takeAt(0)
                w = item.widget()
                if w:
                    w.setParent(None)
                    w.deleteLater()

        matrix_layout.setContentsMargins(0, 0, 0, 0)
        matrix_layout.setSpacing(0)

        # Top Matrix Header
        hdr = QFrame()
        hdr.setFixedHeight(26)
        hdr_bg = "#040609" if is_dark else "#f8fafc"
        hdr_border = "rgba(255, 255, 255, 0.08)" if is_dark else "#cbd5e1"
        hdr.setStyleSheet(f"background-color: {hdr_bg}; border-bottom: 1px solid {hdr_border};")
        hdr_l = QHBoxLayout(hdr)
        hdr_l.setContentsMargins(8, 0, 8, 0)
        lbl_h = QLabel("CORE PERFORMANCE METRICS")
        lbl_h_col = "#94a3b8" if is_dark else "#0f172a"
        lbl_h.setStyleSheet(f"color: {lbl_h_col}; font-family: 'Consolas', monospace; font-size: 10px; font-weight: 700; letter-spacing: 0.5px;")
        hdr_l.addWidget(lbl_h)
        hdr_l.addStretch()
        self.lbl_matrix_sample = QLabel("SAMPLE: 0 TRADES")
        lbl_sample_col = "#64748b" if is_dark else "#475569"
        self.lbl_matrix_sample.setStyleSheet(f"color: {lbl_sample_col}; font-family: 'Consolas', monospace; font-size: 9.5px;")
        hdr_l.addWidget(self.lbl_matrix_sample)
        matrix_layout.addWidget(hdr)

        def add_section_header(title: str):
            sec = QFrame()
            sec.setFixedHeight(20)
            sec_bg = "#030508" if is_dark else "#f1f5f9"
            sec_border = "rgba(255, 255, 255, 0.04)" if is_dark else "#e2e8f0"
            sec.setStyleSheet(f"background-color: {sec_bg}; border-bottom: 1px solid {sec_border};")
            sl = QHBoxLayout(sec)
            sl.setContentsMargins(8, 0, 8, 0)
            lbl = QLabel(title)
            lbl_sec_col = "#475569" if is_dark else "#334155"
            lbl.setStyleSheet(f"color: {lbl_sec_col}; font-family: 'Consolas', monospace; font-size: 9px; font-weight: 700;")
            sl.addWidget(lbl)
            matrix_layout.addWidget(sec)

        def add_metric_row(key: str, label_text: str, default_val: str, text_color: str = "#f8fafc", is_highlight: bool = False) -> QLabel:
            row = QFrame()
            row.setFixedHeight(24)
            bg = ("background-color: rgba(34, 197, 94, 0.08);" if is_dark else "background-color: rgba(21, 128, 61, 0.08);") if is_highlight else "background-color: transparent;"
            row_border = "rgba(255, 255, 255, 0.03)" if is_dark else "rgba(0, 0, 0, 0.05)"
            row.setStyleSheet(f"{bg} border-bottom: 1px solid {row_border};")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(10, 0, 14, 0)

            lbl_title = QLabel(label_text)
            title_col = "#64748b" if is_dark else "#475569"
            lbl_title.setStyleSheet(f"color: {title_col}; font-family: 'Consolas', monospace; font-size: 10px; font-weight: 600;")
            rl.addWidget(lbl_title)
            rl.addStretch()

            lbl_val = QLabel(default_val)
            lbl_val.setObjectName(key)
            font_size = "11px" if is_highlight else "10.5px"
            val_col = text_color
            if not is_dark:
                if text_color in ("#f8fafc", "#ffffff"):
                    val_col = "#0f172a"
                elif text_color in ("#22c55e", "#10b981", "#4ade80"):
                    val_col = "#15803d"
                elif text_color in ("#ef4444", "#f87171"):
                    val_col = "#b91c1c"
                elif text_color in ("#cbd5e1", "#94a3b8"):
                    val_col = "#334155"
            lbl_val.setStyleSheet(
                f"color: {val_col}; font-family: 'Consolas', monospace; font-size: {font_size}; font-weight: 700;"
            )
            rl.addWidget(lbl_val)
            matrix_layout.addWidget(row)
            self.metric_labels[key] = lbl_val
            return lbl_val

        # PHẦN 1: HIỆU QUẢ THEO RỦI RO
        add_section_header("RISK-ADJUSTED PERFORMANCE")
        self.valSharpe = add_metric_row("valSharpe", "SHARPE RATIO", "--", "#334155")
        self.valSortino = add_metric_row("valSortino", "SORTINO RATIO", "--", "#334155")
        self.valCalmar = add_metric_row("valCalmar", "CALMAR RATIO", "--", "#334155")
        self.valProfitFactor = add_metric_row("valProfitFactor", "PROFIT FACTOR", "--", "#334155")
        self.valRR = add_metric_row("valRR", "WIN / LOSS RATIO", "--", "#334155")

        # PHẦN 2: VỐN VÀ QUẢN TRỊ RỦI RO
        add_section_header("CAPITAL & RISK METRICS")
        self.valMaxDD = add_metric_row("valMaxDD", "MAX DRAWDOWN", "0.00%", "#334155")
        self.valMaxDDDuration = add_metric_row("valMaxDDDuration", "DD DURATION", "0 bars", "#334155")
        self.valRecoveryFactor = add_metric_row("valRecoveryFactor", "RECOVERY FACTOR", "--", "#334155")
        self.valMarginUtil = add_metric_row("valMarginUtil", "MARGIN LEVEL", "0.0%", "#334155")

        # PHẦN 3: HIỆU NĂNG GIAO DỊCH
        add_section_header("TRADING PERFORMANCE")
        self.valWinRate = add_metric_row("valWinRate", "WIN RATE", "0.00%", "#334155")
        self.valTotalTrades = add_metric_row("valTotalTrades", "TOTAL TRADES", "0", "#334155")
        self.valAvgWin = add_metric_row("valAvgWin", "AVG WINNING TRADE", "$0.00", "#334155")
        self.valAvgLoss = add_metric_row("valAvgLoss", "AVG LOSING TRADE", "$0.00", "#334155")
        self.valExpectancy = add_metric_row("valExpectancy", "EXPECTANCY", "$0.00 / trade", "#334155")
        self.valConsecWins = add_metric_row("valConsecWins", "MAX WIN STREAK", "0", "#334155")
        self.valConsecLoss = add_metric_row("valConsecLoss", "MAX LOSS STREAK", "0", "#334155")
        self.valLargestWin = add_metric_row("valLargestWin", "LARGEST WIN", "$0.00", "#334155")
        self.valLargestLoss = add_metric_row("valLargestLoss", "LARGEST LOSS", "$0.00", "#334155")

        # PHẦN 4: TỔNG KẾT TÀI CHÍNH
        add_section_header("FINANCIAL SUMMARY")
        self.valGrossProfit = add_metric_row("valGrossProfit", "GROSS PROFIT", "$0.00", "#334155")
        self.valGrossLoss = add_metric_row("valGrossLoss", "GROSS LOSS", "$0.00", "#334155")
        self.valNetProfit = add_metric_row("valNetProfit", "NET PROFIT", "$0.00", "#334155", is_highlight=True)

        # PHẦN 5: HIỆU SUẤT THEO CHIỀU LỆNH & PHIÊN
        add_section_header("DIRECTION & SESSION BREAKDOWN")
        self.valLongTrades = add_metric_row("valLongTrades", "LONG TRADES", "0 (0.0%)", "#334155")
        self.valShortTrades = add_metric_row("valShortTrades", "SHORT TRADES", "0 (0.0%)", "#334155")
        self.valAsianSession = add_metric_row("valAsianSession", "ASIAN SESSION", "$0.00", "#334155")
        self.valLondonSession = add_metric_row("valLondonSession", "LONDON SESSION", "$0.00", "#334155")
        self.valNYSession = add_metric_row("valNYSession", "NEW YORK SESSION", "$0.00", "#334155")

        matrix_layout.addStretch()

        # Wire legacy attributes onto self.window for backward compatibility
        self.window.valSharpe = self.valSharpe
        self.window.valSortino = self.valSortino
        self.window.valMaxDD = self.valMaxDD
        self.window.valRR = self.valRR
        self.window.valWinRate = self.valWinRate
        self.window.valNetProfit = self.valNetProfit
        self.window.valTotalTrades = self.valTotalTrades

    def _bind_events(self):
        if hasattr(self.window, "btnCalPrev"):
            self.window.btnCalPrev.clicked.connect(self._prev_month)
        if hasattr(self.window, "btnCalNext"):
            self.window.btnCalNext.clicked.connect(self._next_month)
        if hasattr(self.window, "btnCalToday"):
            self.window.btnCalToday.clicked.connect(self._go_today)
        for attr in ("btnExportCsv", "btnExportTrades"):
            if hasattr(self.window, attr):
                getattr(self.window, attr).clicked.connect(self.export_csv)
        if hasattr(self.window, "btnRefreshStats"):
            self.window.btnRefreshStats.clicked.connect(self.refresh_stats)
        if hasattr(self.window, "searchStats"):
            self.window.searchStats.textChanged.connect(self._filter_history_table)
        if hasattr(self.window, "comboLogFilter"):
            self.window.comboLogFilter.currentIndexChanged.connect(self._filter_history_table)

    def _setup_history_table(self):
        if not hasattr(self.window, "tableHistory"):
            return
        ht = self.window.tableHistory
        ht.setColumnCount(5)
        ht.setHorizontalHeaderLabels([
            "TICKET", "SYMBOL", "SIDE", "PIPS", "NET P&L"
        ])
        ht.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        hh = ht.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        ht.setColumnWidth(0, 58)  # TICKET
        hh.setSectionResizeMode(1, QHeaderView.Fixed)
        ht.setColumnWidth(1, 62)  # SYMBOL
        hh.setSectionResizeMode(2, QHeaderView.Fixed)
        ht.setColumnWidth(2, 48)  # SIDE
        hh.setSectionResizeMode(3, QHeaderView.Fixed)
        ht.setColumnWidth(3, 58)  # PIPS
        hh.setSectionResizeMode(4, QHeaderView.Stretch)  # NET P&L
        ht.verticalHeader().setVisible(False)
        ht.verticalHeader().setDefaultSectionSize(22)
        ht.setEditTriggers(QAbstractItemView.NoEditTriggers)
        ht.setSelectionMode(QAbstractItemView.NoSelection)
        ht.setStyleSheet(
            "QTableWidget#tableHistory::item { padding: 0px 2px; } "
            "QHeaderView::section { font-family: 'Consolas', monospace; font-size: 8.5px; font-weight: 700; padding: 2px 2px; }"
        )

        # High-performance vector badge delegate (Columns 2, 3, 4: SIDE, PIPS, NET P&L)
        self.badge_delegate = TableBadgeDelegate(ht, self.is_dark_theme)
        ht.setItemDelegateForColumn(2, self.badge_delegate)
        ht.setItemDelegateForColumn(3, self.badge_delegate)
        ht.setItemDelegateForColumn(4, self.badge_delegate)

        # Empty diagnostic state overlay
        self.layout_history_vp = QVBoxLayout(ht.viewport())
        self.layout_history_vp.setContentsMargins(0, 0, 0, 0)
        self.lbl_history_empty = QLabel("No closed deals recorded in this period", ht.viewport())
        self.lbl_history_empty.setAlignment(Qt.AlignCenter)
        self.lbl_history_empty.setStyleSheet(
            "color: #64748b; font-family: 'Segoe UI', sans-serif; font-size: 11px; font-weight: 500; background: transparent;"
        )
        self.lbl_history_empty.setVisible(False)
        self.layout_history_vp.addWidget(self.lbl_history_empty)

        # Cài đặt kích thước chuẩn và nhãn tiếng Việt
        if hasattr(self.window, "searchStats"):
            self.window.searchStats.setFixedHeight(24)
            self.window.searchStats.setMinimumWidth(100)
            self.window.searchStats.setPlaceholderText("Filter ticket...")
        if hasattr(self.window, "comboLogFilter"):
            self.window.comboLogFilter.setFixedHeight(24)
            self.window.comboLogFilter.clear()
            self.window.comboLogFilter.addItems(["Time (Newest)", "Profit (Highest)"])
        if hasattr(self.window, "btnExportTrades"):
            self.window.btnExportTrades.setFixedHeight(24)
            self.window.btnExportTrades.setText("EXPORT CSV")
        if hasattr(self.window, "btnCalToday"):
            self.window.btnCalToday.setText("TODAY")

    def _setup_calendar_table(self):
        return self.cal_ctrl.setup_calendar_table()

    def _setup_charts(self):
        def build_plot(parent_widget, custom_y_axis=None):
            layout = QVBoxLayout(parent_widget)
            layout.setContentsMargins(0, 0, 0, 0)

            plot_item = pg.PlotItem(axisItems={"left": custom_y_axis} if custom_y_axis else None)
            plot_item.setContentsMargins(0, 2, 6, 8)
            pw = pg.PlotWidget(plotItem=plot_item, background="#000000")
            pw.showGrid(x=False, y=True, alpha=0.08)
            pw.getPlotItem().hideButtons()
            pw.setMenuEnabled(False)
            pw.setMouseEnabled(x=False, y=False)
            pw.getPlotItem().setMouseEnabled(x=False, y=False)

            for axis_name in ("left", "bottom"):
                ax = pw.getAxis(axis_name)
                ax.setPen(pg.mkPen(color="#161d31"))
                ax.setTextPen(pg.mkPen(color="#64748b"))
                ax.setStyle(tickLength=-4)
                ax.setTickFont(QFont("Consolas", 8))

            if custom_y_axis:
                pw.getAxis("left").setWidth(48)

            layout.addWidget(pw)
            return pw

        # 1. Equity Growth Trajectory Plot
        self.pw_equity = build_plot(self.widget_equity_plot, custom_y_axis=DollarAxisItem(orientation="left"))
        self.pw_equity.setYRange(96000, 104000, padding=0)
        self.pw_hourly_pnl = self.pw_equity  # Backward compatibility alias
        self.charts_ctrl.pw_equity = self.pw_equity

        # 2. Underwater Drawdown Subplot
        self.pw_drawdown = build_plot(self.widget_drawdown_plot, custom_y_axis=PercentAxisItem(orientation="left"))
        self.pw_drawdown.setYRange(-4.0, 0.0, padding=0)
        self.pw_drawdown.setXLink(self.pw_equity)
        self.charts_ctrl.pw_drawdown = self.pw_drawdown

    def update_theme(self, is_dark: bool):
        """Called when user switches Dark/Light mode."""
        self.is_dark_theme = is_dark

        # Update Equity & Drawdown plot headers and frames
        if hasattr(self, "header_equity") and self.header_equity:
            h_bg = "#040609" if is_dark else "#f8fafc"
            h_border = "rgba(255, 255, 255, 0.08)" if is_dark else "#cbd5e1"
            self.header_equity.setStyleSheet(f"background-color: {h_bg}; border-bottom: 1px solid {h_border};")
        if hasattr(self, "lbl_eq_title") and self.lbl_eq_title:
            t_col = "#94a3b8" if is_dark else "#0f172a"
            self.lbl_eq_title.setStyleSheet(f"color: {t_col}; font-family: 'Consolas', monospace; font-size: 10px; font-weight: 700; letter-spacing: 0.5px;")
        if hasattr(self, "frame_equity_plot") and self.frame_equity_plot:
            f_bg = "#020305" if is_dark else "#ffffff"
            f_border = "rgba(255, 255, 255, 0.08)" if is_dark else "#cbd5e1"
            self.frame_equity_plot.setStyleSheet(f"QFrame#frameEquityPlot {{ background-color: {f_bg}; border: 1px solid {f_border}; border-radius: 0px; }}")

        if hasattr(self, "header_dd") and self.header_dd:
            h_bg = "#040609" if is_dark else "#f8fafc"
            h_border = "rgba(255, 255, 255, 0.08)" if is_dark else "#cbd5e1"
            self.header_dd.setStyleSheet(f"background-color: {h_bg}; border-bottom: 1px solid {h_border};")
        if hasattr(self, "lbl_dd_title") and self.lbl_dd_title:
            t_col = "#94a3b8" if is_dark else "#0f172a"
            self.lbl_dd_title.setStyleSheet(f"color: {t_col}; font-family: 'Consolas', monospace; font-size: 9.5px; font-weight: 700; letter-spacing: 0.5px;")
        if hasattr(self, "frame_drawdown_plot") and self.frame_drawdown_plot:
            f_bg = "#020305" if is_dark else "#ffffff"
            f_border = "rgba(255, 255, 255, 0.08)" if is_dark else "#cbd5e1"
            self.frame_drawdown_plot.setStyleSheet(f"QFrame#frameDrawdownPlot {{ background-color: {f_bg}; border: 1px solid {f_border}; border-radius: 0px; }}")

        if hasattr(self, "badge_delegate"):
            self.badge_delegate.set_dark_theme(is_dark)

        for pw in [
            getattr(self, "pw_equity", None),
            getattr(self, "pw_drawdown", None),
        ]:
            if pw is not None:
                ThemeEngine.sync_pyqtgraph_plot(pw, is_dark)

        # Rebuild metrics matrix with current theme colors
        if hasattr(self, "frame_metrics") and self.frame_metrics:
            self._rebuild_metrics_matrix(self.frame_metrics)

        if self.cached_stats:
            self._update_kpi(self.cached_stats)
        self._update_calendar(self.cached_trades)
        self._update_charts(self.cached_trades)
        if hasattr(self.window, "tableHistory"):
            self.window.tableHistory.viewport().update()

    def refresh(self):
        """Alias for refresh_stats to support tab switching calls."""
        self.refresh_stats()

    def refresh_stats(self):
        stats = self.engine.get_account_statistics()
        trades = self.engine.get_full_history()

        self.cached_trades = trades or []
        self.cached_stats = stats or {}

        self._update_kpi(self.cached_stats)
        self._update_history_table(self.cached_trades)
        self._update_calendar(self.cached_trades)
        self._update_charts(self.cached_trades)

    def _update_kpi(self, stats):
        trades = self.cached_trades or []
        total_trades = len(trades)
        tokens = ThemeEngine.get_tokens(self.is_dark_theme)

        acc = mt5.account_info() if mt5.terminal_info() else None
        margin_util = (acc.margin / acc.equity * 100.0) if (acc and acc.equity > 0) else 0.0

        if total_trades == 0:
            if hasattr(self, "valSharpe"):
                self.valSharpe.setText("--")
            if hasattr(self, "valSortino"):
                self.valSortino.setText("--")
            if hasattr(self, "valCalmar"):
                self.valCalmar.setText("--")
            if hasattr(self, "valProfitFactor"):
                self.valProfitFactor.setText("--")
            if hasattr(self, "valRR"):
                self.valRR.setText("--")

            if hasattr(self, "valMaxDD"):
                self.valMaxDD.setText("0.00%")
            if hasattr(self, "valMaxDDDuration"):
                self.valMaxDDDuration.setText("0 bars")
            if hasattr(self, "valRecoveryFactor"):
                self.valRecoveryFactor.setText("--")
            if hasattr(self, "valMarginUtil"):
                self.valMarginUtil.setText(f"{margin_util:.1f}%")

            if hasattr(self, "valWinRate"):
                self.valWinRate.setText("0.00%")
            if hasattr(self, "valTotalTrades"):
                self.valTotalTrades.setText("0")
            if hasattr(self, "valAvgWin"):
                self.valAvgWin.setText("$0.00")
            if hasattr(self, "valAvgLoss"):
                self.valAvgLoss.setText("$0.00")
            if hasattr(self, "valExpectancy"):
                self.valExpectancy.setText("$0.00 / trade")
            if hasattr(self, "valConsecWins"):
                self.valConsecWins.setText("0")
            if hasattr(self, "valConsecLoss"):
                self.valConsecLoss.setText("0")

            neutral_col = "#94a3b8" if self.is_dark_theme else "#334155"
            neutral_style = f"color: {neutral_col}; font-family: 'Consolas', monospace; font-size: 10.5px; font-weight: 700;"

            if hasattr(self, "valGrossProfit"):
                self.valGrossProfit.setText("$0.00")
            if hasattr(self, "valGrossLoss"):
                self.valGrossLoss.setText("$0.00")
            if hasattr(self, "valNetProfit"):
                self.valNetProfit.setText("$0.00")
            if hasattr(self, "valLongTrades"):
                self.valLongTrades.setText("0 (0.0%)")
            if hasattr(self, "valShortTrades"):
                self.valShortTrades.setText("0 (0.0%)")
            if hasattr(self, "valAsianSession"):
                self.valAsianSession.setText("$0.00")
            if hasattr(self, "valLondonSession"):
                self.valLondonSession.setText("$0.00")
            if hasattr(self, "valNYSession"):
                self.valNYSession.setText("$0.00")

            for lbl_attr in [
                "valMaxDD", "valWinRate", "valAvgWin", "valAvgLoss",
                "valGrossProfit", "valGrossLoss", "valNetProfit",
                "valLongTrades", "valShortTrades", "valAsianSession",
                "valLondonSession", "valNYSession"
            ]:
                lbl_w = getattr(self, lbl_attr, None)
                if lbl_w:
                    lbl_w.setStyleSheet(neutral_style)

            if hasattr(self, "lbl_matrix_sample"):
                self.lbl_matrix_sample.setText("SAMPLE: 0 TRADES")
            return

        wins = [t for t in trades if t.get("pnl", 0.0) > 0]
        losses = [t for t in trades if t.get("pnl", 0.0) < 0]

        gross_profit = sum(t.get("pnl", 0.0) for t in wins)
        gross_loss = abs(sum(t.get("pnl", 0.0) for t in losses))
        net_profit = sum(t.get("pnl", 0.0) for t in trades)

        win_rate = (len(wins) / total_trades * 100.0)
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (99.9 if gross_profit > 0 else 0.0)
        avg_win = (gross_profit / len(wins)) if wins else 0.0
        avg_loss = (gross_loss / len(losses)) if losses else 0.0
        payoff_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0
        expectancy = ((win_rate / 100.0) * avg_win) - (((100.0 - win_rate) / 100.0) * avg_loss)

        # Max consecutive wins and losses
        max_c_win = 0
        curr_c_win = 0
        max_c_loss = 0
        curr_c_loss = 0
        for t in trades:
            p = t.get("pnl", 0.0)
            if p > 0:
                curr_c_win += 1
                curr_c_loss = 0
                max_c_win = max(max_c_win, curr_c_win)
            elif p < 0:
                curr_c_loss += 1
                curr_c_win = 0
                max_c_loss = max(max_c_loss, curr_c_loss)

        pnl_series = [t.get("pnl", 0.0) for t in trades]
        if len(pnl_series) >= 2:
            std_pnl = float(np.std(pnl_series))
            mean_pnl = float(np.mean(pnl_series))
            sharpe = (mean_pnl / std_pnl * np.sqrt(252)) if std_pnl > 0 else 0.0
            pnl_arr = np.array(pnl_series)
            downside_diff = np.minimum(0.0, pnl_arr)
            downside_dev = float(np.sqrt(np.mean(downside_diff ** 2)))
            sortino = (mean_pnl / downside_dev * np.sqrt(252)) if downside_dev > 0 else 0.0
        else:
            sharpe = 0.0
            sortino = 0.0

        curve = [100000.0]
        for p in pnl_series:
            curve.append(curve[-1] + p)
        peak = curve[0]
        max_dd = 0.0
        for val in curve:
            if val > peak:
                peak = val
            dd_pct = ((val - peak) / peak * 100.0) if peak > 0 else 0.0
            if abs(dd_pct) > max_dd:
                max_dd = abs(dd_pct)

        calmar = (net_profit / 100000.0 * 100.0 / max_dd) if max_dd > 0 else 0.0
        recovery = (net_profit / (100000.0 * (max_dd / 100.0))) if max_dd > 0 else 0.0

        if hasattr(self, "valSharpe"):
            self.valSharpe.setText(f"{sharpe:.2f}")
        if hasattr(self, "valSortino"):
            self.valSortino.setText(f"{sortino:.2f}")
        if hasattr(self, "valCalmar"):
            self.valCalmar.setText(f"{calmar:.2f}")
        if hasattr(self, "valProfitFactor"):
            self.valProfitFactor.setText(f"{profit_factor:.2f}")
        if hasattr(self, "valRR"):
            self.valRR.setText(f"{payoff_ratio:.2f}")

        if hasattr(self, "valMaxDD"):
            self.valMaxDD.setText(fmt_percent(max_dd))
        if hasattr(self, "valMaxDDDuration"):
            self.valMaxDDDuration.setText(f"{min(total_trades, 30)} bars")
        if hasattr(self, "valRecoveryFactor"):
            self.valRecoveryFactor.setText(f"{recovery:.2f}")
        if hasattr(self, "valMarginUtil"):
            self.valMarginUtil.setText(f"{margin_util:.1f}%")

        if hasattr(self, "valWinRate"):
            self.valWinRate.setText(fmt_percent(win_rate))
        if hasattr(self, "valTotalTrades"):
            self.valTotalTrades.setText(fmt_number(total_trades))
        if hasattr(self, "valAvgWin"):
            self.valAvgWin.setText(fmt_currency(avg_win, sign=True))
        if hasattr(self, "valAvgLoss"):
            self.valAvgLoss.setText(fmt_currency(-avg_loss, sign=True))
        if hasattr(self, "valExpectancy"):
            self.valExpectancy.setText(f"{'+' if expectancy >= 0 else '-'}${abs(expectancy):.2f} / trade")
        if hasattr(self, "valConsecWins"):
            self.valConsecWins.setText(str(max_c_win))
        if hasattr(self, "valConsecLoss"):
            self.valConsecLoss.setText(str(max_c_loss))

        if hasattr(self, "valGrossProfit"):
            self.valGrossProfit.setText(fmt_currency(gross_profit, sign=True))
        if hasattr(self, "valGrossLoss"):
            self.valGrossLoss.setText(fmt_currency(-gross_loss, sign=True))
        if hasattr(self, "valNetProfit"):
            self.valNetProfit.setText(fmt_currency(net_profit, sign=True))
            color = tokens.pnl_profit if net_profit >= 0 else tokens.pnl_loss
            self.valNetProfit.setStyleSheet(
                f"color: {color}; font-family: 'Consolas', monospace; font-size: 11.5px; font-weight: 700;"
            )

        if hasattr(self, "lbl_matrix_sample"):
            self.lbl_matrix_sample.setText(f"SAMPLE: {total_trades} TRADES")

    def _update_history_table(self, trades):
        self._filter_history_table()

    def _filter_history_table(self):
        if not hasattr(self.window, "tableHistory"):
            return
        trades = self.cached_trades or []
        query = ""
        if hasattr(self.window, "searchStats"):
            query = self.window.searchStats.text().strip().lower()

        sort_mode = 0
        if hasattr(self.window, "comboLogFilter"):
            sort_mode = self.window.comboLogFilter.currentIndex()

        filtered = []
        for t in trades:
            if query:
                ticket_str = str(t.get("ticket", "")).lower()
                sym_str = str(t.get("symbol", "")).lower()
                type_str = str(t.get("type", "")).lower()
                if query not in ticket_str and query not in sym_str and query not in type_str:
                    continue
            filtered.append(t)

        if sort_mode == 1:
            filtered.sort(key=lambda x: x.get("pnl", 0.0), reverse=True)
        else:
            filtered.sort(key=lambda x: x.get("timestamp", 0), reverse=True)

        ht = self.window.tableHistory
        ht.setRowCount(0)

        if len(filtered) == 0:
            if hasattr(self, "lbl_history_empty"):
                m = getattr(self, "current_cal_month", 10)
                y = getattr(self, "current_cal_year", 2026)
                self.lbl_history_empty.setText(f"No closed trades recorded in {calendar.month_name[m]} {y}")
                self.lbl_history_empty.setVisible(True)
        else:
            if hasattr(self, "lbl_history_empty"):
                self.lbl_history_empty.setVisible(False)
            for t in filtered:
                is_buy = str(t.get("type", "")).upper() == "BUY" or t.get("is_buy", False)
                self._add_history_row(
                    t["ticket"],
                    is_buy,
                    t.get("close_time", ""),
                    f"{t.get('volume', 0.5):.2f}",
                    t.get("symbol", "XAUUSD"),
                    t.get("pnl", 0.0),
                    t.get("pips", 0.0),
                    t.get("duration", "30m"),
                )

    def _add_history_row(self, ticket, is_buy, time_str, vol, sym, pnl, pips, duration):
        ht = self.window.tableHistory
        row = ht.rowCount()
        ht.insertRow(row)
        ht.setRowHeight(row, 22)

        # Định dạng thời gian hiển thị gọn gàng: "15/10 14:15"
        display_time = str(time_str).replace("\n", " ").strip()
        if "thg" in display_time:
            # Phân giải "15 thg 10 2026 14:15:00" -> "15/10 14:15"
            parts = display_time.split()
            if len(parts) >= 5:
                display_time = f"{parts[0]}/{parts[2]} {parts[4][:5]}"
        elif len(display_time) >= 16 and display_time.startswith("20"):
            display_time = f"{display_time[8:10]}/{display_time[5:7]} {display_time[11:16]}"
        ticket_str = str(ticket)
        if len(ticket_str) > 6:
            ticket_str = ticket_str[-6:]

        pips_str = f"{fmt_pips(pips, sign=True, include_unit=False)} p"
        col_data = [
            (ticket_str, Qt.AlignCenter),
            (sym, Qt.AlignCenter),
            ("BUY" if is_buy else "SELL", Qt.AlignCenter),
            (pips_str, Qt.AlignCenter),
            (fmt_currency(pnl, sign=True), Qt.AlignCenter),
        ]

        for col, (text, align) in enumerate(col_data):
            item = QTableWidgetItem(text)
            item.setTextAlignment(align)
            ht.setItem(row, col, item)

    def _prev_month(self):
        return self.cal_ctrl.prev_month()

    def _next_month(self):
        return self.cal_ctrl.next_month()

    def _go_today(self):
        return self.cal_ctrl.go_today()

    def _update_calendar(self, trades):
        return self.cal_ctrl.update_calendar(trades)

    def _update_charts(self, trades):
        return self.charts_ctrl.update_charts(trades)

    def export_csv(self):
        trades = self.cached_trades or self.engine.get_full_history()
        if not trades:
            QMessageBox.warning(self.window, "Export Data", "No trade history available to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self.window, "Save Trade History", "Trade_History.csv", "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Ticket", "Type", "Close Time", "Volume", "Symbol", "Net P&L", "Pips", "Duration"])
                for t in trades:
                    writer.writerow([
                        t.get("ticket", ""),
                        t.get("type", ""),
                        t.get("close_time", ""),
                        t.get("volume", ""),
                        t.get("symbol", ""),
                        t.get("pnl", ""),
                        t.get("pips", ""),
                        t.get("duration", "")
                    ])
            QMessageBox.information(self.window, "Export Success", f"Successfully exported {len(trades)} trades to CSV file.")
        except Exception as e:
            QMessageBox.critical(self.window, "Error", f"Failed to save CSV file: {str(e)}")

# Backward compatibility alias
PerformanceController = StatsManager
