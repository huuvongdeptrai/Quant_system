"""
Dual Equity Growth and Drawdown Charts Controller for Tab 2 (Performance)
"""

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QVBoxLayout
from backend.infrastructure.brokers.mt5_safe import mt5


class DollarAxisItem(pg.AxisItem):
    """Custom Y-Axis formatting numbers as authentic currency ($96k, $100k, $104k)."""
    def tickStrings(self, values, scale, spacing):
        strings = []
        for v in values:
            if abs(v) >= 1_000_000:
                s = f"${v/1_000_000:.1f}M"
            elif abs(v) >= 1_000:
                s = f"${v/1000:.0f}k" if (v % 1000 == 0) else f"${v:,.0f}"
            else:
                s = f"${v:.0f}"
            strings.append(s)
        return strings


class PercentAxisItem(pg.AxisItem):
    """Custom Y-Axis formatting numbers as percentage (-4.0% to 0.0%)."""
    def tickStrings(self, values, scale, spacing):
        return [f"{v:.1f}%" for v in values]


class PerformanceChartsController:
    """Manages Equity Growth and Underwater Drawdown curves in Tab 2."""

    def __init__(self, manager):
        self.mgr = manager
        self.window = manager.window
        self.pw_equity = None
        self.pw_drawdown = None

    def setup_charts(self):
        def build_plot(parent_widget, custom_y_axis=None):
            layout = QVBoxLayout(parent_widget)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            plot_item = pg.PlotItem(axisItems={"left": custom_y_axis} if custom_y_axis else None)
            pw = pg.PlotWidget(plotItem=plot_item)
            pw.setBackground("#0d1117")
            pw.showGrid(x=True, y=True, alpha=0.15)
            pw.setMenuEnabled(False)
            layout.addWidget(pw)
            return pw

        if hasattr(self.window, "chartEquity"):
            self.pw_equity = build_plot(self.window.chartEquity, DollarAxisItem(orientation="left"))
            self.mgr.pw_equity = self.pw_equity

        if hasattr(self.window, "chartDrawdown"):
            self.pw_drawdown = build_plot(self.window.chartDrawdown, PercentAxisItem(orientation="left"))
            self.mgr.pw_drawdown = self.pw_drawdown

    def update_charts(self, trades):
        trades = trades or []
        acc = mt5.account_info() if mt5.terminal_info() else None
        current_balance = acc.balance if acc else 100000.0

        if not trades:
            curve = [current_balance, current_balance]
            x_data = [0, 20]
            dd_curve = [0.0, 0.0]
            ath = current_balance
            curr = current_balance
            max_dd_val = 0.0
            curr_dd = 0.0
        else:
            trades_sorted = sorted(trades, key=lambda x: x.get("timestamp", 0))
            total_realized_pnl = sum(t.get("pnl", 0.0) for t in trades)
            initial_balance = current_balance - total_realized_pnl if current_balance > total_realized_pnl else 100000.0
            cum_pnl = initial_balance
            curve = [initial_balance]
            for t in trades_sorted:
                cum_pnl += t.get("pnl", 0.0)
                curve.append(cum_pnl)
            x_data = list(range(len(curve)))

            dd_curve = []
            peak = curve[0]
            for val in curve:
                if val > peak:
                    peak = val
                dd_pct = ((val - peak) / peak) * 100.0 if peak > 0 else 0.0
                dd_curve.append(dd_pct)

            ath = max(curve)
            curr = curve[-1]
            max_dd_val = min(dd_curve) if dd_curve else 0.0
            curr_dd = dd_curve[-1] if dd_curve else 0.0

        # 1. Update Equity Growth Plot
        pw = self.pw_equity or getattr(self.mgr, "pw_equity", None)
        if pw:
            self.pw_equity = pw
            pw.clear()
            if not trades:
                pw.setYRange(96000, 104000, padding=0)
                curve_item = pg.PlotDataItem(
                    x_data,
                    curve,
                    pen=pg.mkPen("#94a3b8", width=1.5, style=Qt.DashLine),
                )
                pw.addItem(curve_item)
            else:
                if min(curve) == max(curve):
                    pw.setYRange(curve[0] - 4000, curve[0] + 4000, padding=0)
                else:
                    pw.enableAutoRange(axis=pg.ViewBox.YAxis)
                pen_color = "#15803d" if curve[-1] >= curve[0] else "#b91c1c"
                curve_item = pg.PlotDataItem(
                    x_data,
                    curve,
                    pen=pg.mkPen(pen_color, width=2.0),
                )
                pw.addItem(curve_item)
                fill_color = QColor(21, 128, 61, 25) if curve[-1] >= curve[0] else QColor(185, 28, 28, 25)
                fill = pg.FillBetweenItem(
                    curve1=curve_item,
                    curve2=pg.PlotDataItem(x_data, [min(curve)] * len(x_data)),
                    brush=pg.mkBrush(fill_color),
                )
                pw.addItem(fill)

            if hasattr(self.window, "lblStatsEquityATH"):
                self.window.lblStatsEquityATH.setText(f"${ath:,.2f}")
            if hasattr(self.window, "lblStatsEquityCurrent"):
                color = "#15803d" if curr >= (curve[0] if curve else 0) else "#b91c1c"
                self.window.lblStatsEquityCurrent.setText(f"${curr:,.2f}")
                self.window.lblStatsEquityCurrent.setStyleSheet(f"color: {color};")

        # 2. Update Underwater Drawdown Plot
        pw_dd = self.pw_drawdown or getattr(self.mgr, "pw_drawdown", None)
        if pw_dd:
            self.pw_drawdown = pw_dd
            pw_dd.clear()
            if not trades:
                pw_dd.setYRange(-4.0, 0.0, padding=0)
                dd_item = pg.PlotDataItem(
                    x_data,
                    dd_curve,
                    pen=pg.mkPen("#64748b", width=1.2, style=Qt.DashLine),
                )
                pw_dd.addItem(dd_item)
            else:
                min_dd = min(dd_curve) if dd_curve else 0.0
                bottom_y = min(-4.0, min_dd * 1.15)
                pw_dd.setYRange(bottom_y, 0.0, padding=0)
                dd_item = pg.PlotDataItem(
                    x_data,
                    dd_curve,
                    pen=pg.mkPen("#f43f5e", width=1.8),
                )
                pw_dd.addItem(dd_item)
                zero_baseline = pg.PlotDataItem(x_data, [0.0] * len(x_data))
                fill_dd = pg.FillBetweenItem(
                    curve1=zero_baseline,
                    curve2=dd_item,
                    brush=pg.mkBrush(244, 63, 94, 35),
                )
                pw_dd.addItem(fill_dd)

            if hasattr(self.window, "lblStatsMaxDD"):
                self.window.lblStatsMaxDD.setText(f"{max_dd_val:.2f}%")
            if hasattr(self.window, "lblStatsCurrentDD"):
                self.window.lblStatsCurrentDD.setText(f"{curr_dd:.2f}%")
