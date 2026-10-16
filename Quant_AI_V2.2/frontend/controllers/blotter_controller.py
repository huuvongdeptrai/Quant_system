"""
Trade Blotter Controller for Quant_AI V2.2
Manages active positions, pending orders, trade history, and execution actions (Close, Modify, Flatten, Kill Switch).
"""

import os
import time
from datetime import datetime
from loguru import logger
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from backend.infrastructure.brokers.mt5_safe import mt5


class BlotterController:
    """Institutional Trade Blotter managing Executions Table, Orders, Positions, and Kill Switch."""

    def __init__(self, terminal):
        self.terminal = terminal
        self.window = terminal.window
        self.flatten_countdown = 0
        self.flatten_timer = None
        self.active_blotter_mode = "active"

    def __getattr__(self, name):
        return getattr(self.terminal, name)

    def __setattr__(self, name, value):
        if name in ("terminal", "window", "flatten_countdown", "flatten_timer", "active_blotter_mode"):
            super().__setattr__(name, value)
        else:
            super().__setattr__(name, value)
            if hasattr(self, "terminal"):
                setattr(self.terminal, name, value)

    def _setup_executions_table(self):
        """Setup institutional MT5-style Trade Blotter with active positions, history, and realistic order logic."""
        if not hasattr(self.window, "tableExecutions"):
            return

        tbl = self.window.tableExecutions
        tbl.verticalHeader().setDefaultSectionSize(28)
        tbl.verticalHeader().setVisible(False)
        tbl.setShowGrid(False)

        # Empty state indicator for trade blotter
        if not hasattr(self, "lbl_blotter_empty"):
            self.layout_blotter_vp = QVBoxLayout(tbl.viewport())
            self.layout_blotter_vp.setContentsMargins(0, 0, 0, 0)
            self.lbl_blotter_empty = QLabel("No open positions", tbl.viewport())
            self.lbl_blotter_empty.setAlignment(Qt.AlignCenter)
            self.lbl_blotter_empty.setStyleSheet(
                "color: #64748b; font-family: 'Segoe UI', sans-serif; font-size: 11px; font-weight: 500; background: transparent;"
            )
            self.lbl_blotter_empty.setVisible(False)
            self.layout_blotter_vp.addWidget(self.lbl_blotter_empty)

        assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
        if not os.path.exists(assets_dir):
            assets_dir = os.path.join(os.path.dirname(__file__), "assets")

        if hasattr(self.window, "frameExecutions"):
            self.window.frameExecutions.setFixedHeight(155)
            for _lbl_name in ["lblExecutionsFilters", "lblExecutionsTitle", "badgeExecutionsCount"]:
                if hasattr(self.window, _lbl_name):
                    getattr(self.window, _lbl_name).setVisible(False)

            # Reconstruct dock header layout inside frameExecutions
            exec_layout = self.window.frameExecutions.layout()
            if exec_layout:
                exec_layout.setContentsMargins(6, 4, 6, 4)
                exec_layout.setSpacing(2)
            if exec_layout and exec_layout.itemAt(0) and exec_layout.itemAt(0).layout():
                header_layout = exec_layout.itemAt(0).layout()
                while header_layout.count():
                    item = header_layout.takeAt(0)
                    w = item.widget()
                    if w:
                        w.deleteLater()

                header_layout.setContentsMargins(6, 2, 6, 2)
                header_layout.setSpacing(6)
                header_layout.setAlignment(Qt.AlignVCenter)

                # Real Trade Blotter Tabs (Eliminates redundant TERMINAL, BACKTEST, LOGS)
                blotter_tabs = [
                    ("POSITIONS", "active"),
                    ("ORDERS / DEALS", "history"),
                    ("PENDING ORDERS", "pending"),
                ]
                self.blotter_buttons = {}

                # Institutional summary badge in dock header (dynamically updated)
                self.lbl_dock_summary = QLabel()
                self.lbl_dock_summary.setStyleSheet("color:#64748b; font-family:Consolas, monospace; font-size:9px; padding-left: 14px;")

                def _render_blotter(mode=None):
                    if mode is None:
                        mode = getattr(self, "active_blotter_mode", "active")
                    self.active_blotter_mode = mode
                    is_dark = getattr(self, "is_dark_theme", False)
                    is_live = mt5.terminal_info() is not None

                    for m_key, b_obj in self.blotter_buttons.items():
                        if m_key == mode:
                            if is_dark:
                                b_obj.setStyleSheet(
                                    "QPushButton { background-color: #12151d; color: #ffffff; border: 1px solid #272d3b; "
                                    "border-top: 2px solid #f8fafc; border-bottom: none; font-family: Consolas, monospace; "
                                    "font-size: 9px; font-weight: bold; padding: 0 12px; border-top-left-radius: 2px; border-top-right-radius: 2px; }"
                                )
                            else:
                                b_obj.setStyleSheet(
                                    "QPushButton { background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; "
                                    "border-top: 2px solid #0f172a; border-bottom: none; font-family: Consolas, monospace; "
                                    "font-size: 9px; font-weight: bold; padding: 0 12px; border-top-left-radius: 2px; border-top-right-radius: 2px; }"
                                )
                        else:
                            if is_dark:
                                b_obj.setStyleSheet(
                                    "QPushButton { background-color: transparent; color: #94a3b8; border: 1px solid transparent; "
                                    "font-family: Consolas, monospace; font-size: 9px; font-weight: 600; padding: 0 10px; } "
                                    "QPushButton:hover { color: #ffffff; background-color: #141721; }"
                                )
                            else:
                                b_obj.setStyleSheet(
                                    "QPushButton { background-color: transparent; color: #64748b; border: 1px solid transparent; "
                                    "font-family: Consolas, monospace; font-size: 9px; font-weight: 600; padding: 0 10px; } "
                                    "QPushButton:hover { color: #0f172a; background-color: #e2e8f0; }"
                                )

                    # Update FILTERS & EXPORT CSV buttons style
                    if hasattr(self, "btn_blotter_filters") and self.btn_blotter_filters:
                        if is_dark:
                            self.btn_blotter_filters.setStyleSheet(
                                "QPushButton { background-color: transparent; color: #94a3b8; border: 1px solid #272d3b; "
                                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: 600; border-radius: 2px; padding: 0 8px; } "
                                "QPushButton:hover { color: #ffffff; background-color: #141721; border-color: #3b4252; }"
                            )
                        else:
                            self.btn_blotter_filters.setStyleSheet(
                                "QPushButton { background-color: #ffffff; color: #475569; border: 1px solid #cbd5e1; "
                                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: 600; border-radius: 2px; padding: 0 8px; } "
                                "QPushButton:hover { color: #0f172a; background-color: #e2e8f0; border-color: #94a3b8; }"
                            )
                    if hasattr(self, "btn_blotter_export") and self.btn_blotter_export:
                        if is_dark:
                            self.btn_blotter_export.setStyleSheet(
                                "QPushButton { background-color: transparent; color: #94a3b8; border: 1px solid #272d3b; "
                                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: 600; border-radius: 2px; padding: 0 8px; } "
                                "QPushButton:hover { color: #ffffff; background-color: #141721; border-color: #3b4252; }"
                            )
                        else:
                            self.btn_blotter_export.setStyleSheet(
                                "QPushButton { background-color: #ffffff; color: #475569; border: 1px solid #cbd5e1; "
                                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: 600; border-radius: 2px; padding: 0 8px; } "
                                "QPushButton:hover { color: #0f172a; background-color: #e2e8f0; border-color: #94a3b8; }"
                            )
                    if hasattr(self, "btn_blotter_flatten") and self.btn_blotter_flatten:
                        if is_dark:
                            self.btn_blotter_flatten.setStyleSheet(
                                "QPushButton { background-color: #991b1b; color: #ffffff; border: 1px solid #7f1d1d; "
                                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0 8px; } "
                                "QPushButton:hover { background-color: #b91c1c; border-color: #991b1b; }"
                            )
                        else:
                            self.btn_blotter_flatten.setStyleSheet(
                                "QPushButton { background-color: #dc2626; color: #ffffff; border: 1px solid #cbd5e1; "
                                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0 8px; } "
                                "QPushButton:hover { background-color: #b91c1c; border-color: #94a3b8; }"
                            )

                    if hasattr(self.window, "btnDockToggle") and self.window.btnDockToggle:
                        if is_dark:
                            self.window.btnDockToggle.setStyleSheet(
                                "QPushButton#btnDockToggle { background-color: transparent; border: 1px solid #272d3b; border-radius: 2px; padding: 0px; margin: 0px; min-height: 20px; max-height: 20px; min-width: 20px; max-width: 20px; } "
                                "QPushButton#btnDockToggle:hover { background-color: #1e293b; border-color: #475569; }"
                            )
                        else:
                            self.window.btnDockToggle.setStyleSheet(
                                "QPushButton#btnDockToggle { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 2px; padding: 0px; margin: 0px; min-height: 20px; max-height: 20px; min-width: 20px; max-width: 20px; } "
                                "QPushButton#btnDockToggle:hover { background-color: #f1f5f9; border-color: #94a3b8; }"
                            )

                    tbl.clear()
                    mono_font = QFont("Consolas", 9)

                    clr_sym = QColor("#ffffff" if is_dark else "#0f172a")
                    clr_strat = QColor("#cbd5e1" if is_dark else "#334155")
                    clr_buy = QColor("#10b981" if is_dark else "#15803d")
                    clr_pnl_pos = QColor("#10b981" if is_dark else "#15803d")
                    clr_pnl_neg = QColor("#ef4444" if is_dark else "#b91c1c")
                    clr_comm = QColor("#94a3b8" if is_dark else "#64748b")
                    clr_def = QColor("#cbd5e1" if is_dark else "#334155")

                    if mode == "active":
                        headers = ["TIME", "TICKET", "SYMBOL", "STRATEGY", "SIDE", "VOLUME", "ENTRY", "CURRENT", "PROFIT", "ACTION"]
                        tbl.setColumnCount(len(headers))
                        for col_idx, h_text in enumerate(headers):
                            item = QTableWidgetItem(h_text)
                            if col_idx in (5, 6, 7, 8):
                                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                            else:
                                item.setTextAlignment(Qt.AlignCenter)
                            tbl.setHorizontalHeaderItem(col_idx, item)

                        tbl.setColumnWidth(0, 95)
                        tbl.setColumnWidth(1, 90)
                        tbl.setColumnWidth(2, 85)
                        tbl.setColumnWidth(3, 210)
                        tbl.setColumnWidth(4, 70)
                        tbl.setColumnWidth(5, 90)
                        tbl.setColumnWidth(6, 110)
                        tbl.setColumnWidth(7, 110)
                        tbl.setColumnWidth(8, 120)
                        tbl.setColumnWidth(9, 130)
                        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
                        tbl.horizontalHeader().setStretchLastSection(True)

                        pos_records = []
                        total_exposure = 0.0
                        total_unrealized = 0.0

                        is_live = mt5.terminal_info() is not None
                        if is_live:
                            mt5_pos = mt5.positions_get()
                            if mt5_pos:
                                for p in mt5_pos:
                                    t_str = datetime.fromtimestamp(p.time).strftime("%H:%M:%S") if hasattr(p, "time") else "--:--:--"
                                    side_str = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
                                    info_sym = mt5.symbol_info(p.symbol)
                                    dig = info_sym.digits if info_sym else 2
                                    pos_records.append({
                                        "time": t_str,
                                        "ticket": p.ticket,
                                        "symbol": p.symbol,
                                        "strategy": p.comment if p.comment else "Algo Strategy",
                                        "side": side_str,
                                        "lots": f"{p.volume:.2f}",
                                        "entry": f"{p.price_open:.{dig}f}",
                                        "current": f"{p.price_current:.{dig}f}",
                                        "pnl_val": p.profit,
                                        "pnl_str": f"+${p.profit:.2f}" if p.profit >= 0 else f"-${abs(p.profit):.2f}",
                                        "sl": p.sl,
                                        "tp": p.tp,
                                        "open_price": p.price_open,
                                        "current_price": p.price_current,
                                        "volume": p.volume,
                                        "digits": dig,
                                    })
                                    total_exposure += p.volume
                                    total_unrealized += p.profit
                        else:
                            pos_records = getattr(self, "_demo_positions", []) or []
                            for p in pos_records:
                                total_exposure += p.get("volume", 0.0)
                                total_unrealized += p.get("pnl_val", 0.0)

                        tbl.setRowCount(len(pos_records))
                        for row, p in enumerate(pos_records):
                            row_cells = [
                                p["time"],
                                f"#{p['ticket']}",
                                p["symbol"],
                                p["strategy"],
                                p["side"],
                                p["lots"],
                                p["entry"],
                                p["current"],
                                p["pnl_str"],
                            ]
                            for col, text in enumerate(row_cells):
                                item = QTableWidgetItem(text)
                                item.setFont(mono_font)
                                if col in (5, 6, 7, 8):
                                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                                else:
                                    item.setTextAlignment(Qt.AlignCenter)

                                if col == 2:
                                    item.setForeground(clr_sym)
                                elif col == 3:
                                    item.setForeground(clr_strat)
                                elif col == 4:
                                    item.setForeground(clr_buy if p["side"] == "BUY" else clr_pnl_neg)
                                elif col == 8:
                                    item.setForeground(clr_pnl_pos if p["pnl_val"] >= 0 else clr_pnl_neg)
                                else:
                                    item.setForeground(clr_def)
                                tbl.setItem(row, col, item)

                            # Column 9: ACTIONS ([MODIFY], [CLOSE]) rendered ONLY for active positions!
                            act_widget = QWidget()
                            act_layout = QHBoxLayout(act_widget)
                            act_layout.setContentsMargins(0, 0, 0, 0)
                            act_layout.setSpacing(6)
                            act_layout.setAlignment(Qt.AlignCenter)

                            btn_mod = QPushButton("MODIFY")
                            btn_mod.setObjectName("btnRowModify")
                            btn_mod.setFixedSize(48, 20)
                            btn_mod.setCursor(Qt.PointingHandCursor)
                            if is_dark:
                                btn_mod.setStyleSheet(
                                    "QPushButton#btnRowModify { background-color: #141721; border: 1px solid #334155; color: #cbd5e1; "
                                    "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0px 4px !important; margin: 0px !important; min-height: 20px !important; } "
                                    "QPushButton#btnRowModify:hover { background-color: #1e293b; color: #ffffff; border-color: #475569; }"
                                )
                            else:
                                btn_mod.setStyleSheet(
                                    "QPushButton#btnRowModify { background-color: #ffffff; border: 1px solid #cbd5e1; color: #334155; "
                                    "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0px 4px !important; margin: 0px !important; min-height: 20px !important; } "
                                    "QPushButton#btnRowModify:hover { background-color: #f1f5f9; color: #0f172a; border-color: #94a3b8; }"
                                )
                            btn_mod.clicked.connect(lambda chk=False, pinfo=p: self._modify_single_position(pinfo))

                            btn_cls = QPushButton("CLOSE")
                            btn_cls.setObjectName("btnRowClose")
                            btn_cls.setFixedSize(48, 20)
                            btn_cls.setCursor(Qt.PointingHandCursor)
                            if is_dark:
                                btn_cls.setStyleSheet(
                                    "QPushButton#btnRowClose { background-color: #2a0d10; border: 1px solid #272d3b; color: #dc2626; "
                                    "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0px 4px !important; margin: 0px !important; min-height: 20px !important; } "
                                    "QPushButton#btnRowClose:hover { background-color: #450a0a; color: #ffffff; border-color: #475569; }"
                                )
                            else:
                                btn_cls.setStyleSheet(
                                    "QPushButton#btnRowClose { background-color: #ffffff; border: 1px solid #cbd5e1; color: #dc2626; "
                                    "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0px 4px !important; margin: 0px !important; min-height: 20px !important; } "
                                    "QPushButton#btnRowClose:hover { background-color: #fef2f2; color: #b91c1c; border-color: #94a3b8; }"
                                )
                            btn_cls.clicked.connect(lambda chk=False, t=p["ticket"]: self._close_single_position(t))

                            act_layout.addWidget(btn_mod)
                            act_layout.addWidget(btn_cls)
                            tbl.setCellWidget(row, 9, act_widget)

                        if hasattr(self, "blotter_buttons") and "active" in self.blotter_buttons:
                            self.blotter_buttons["active"].setText(f"POSITIONS ({len(pos_records)})")

                        if hasattr(self, "lbl_blotter_empty"):
                            if len(pos_records) == 0:
                                self.lbl_blotter_empty.setText("No open positions")
                                self.lbl_blotter_empty.setVisible(True)
                            else:
                                self.lbl_blotter_empty.setVisible(False)

                        exp_col = "#f8fafc" if is_dark else "#0f172a"
                        pnl_col = "#10b981" if is_dark else "#15803d" if total_unrealized >= 0 else ("#ef4444" if is_dark else "#b91c1c")
                        pnl_fmt = f"+${total_unrealized:,.2f}" if total_unrealized >= 0 else f"-${abs(total_unrealized):,.2f}"
                        self.lbl_dock_summary.setText(
                            f'EXPOSURE: <b style="color:{exp_col};">{total_exposure:.2f} LOTS</b> &nbsp;·&nbsp; '
                            f'UNREALIZED P&L: <b style="color:{pnl_col};">{pnl_fmt}</b>'
                        )

                    elif mode == "history":
                        headers = ["TIME", "TICKET", "SYMBOL", "STRATEGY", "SIDE", "VOLUME", "CLOSE PRICE", "COMMISSION", "PROFIT", "STATUS"]
                        tbl.setColumnCount(len(headers))
                        for col_idx, h_text in enumerate(headers):
                            item = QTableWidgetItem(h_text)
                            if col_idx in (5, 6, 7, 8):
                                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                            else:
                                item.setTextAlignment(Qt.AlignCenter)
                            tbl.setHorizontalHeaderItem(col_idx, item)

                        tbl.setColumnWidth(0, 95)
                        tbl.setColumnWidth(1, 90)
                        tbl.setColumnWidth(2, 85)
                        tbl.setColumnWidth(3, 210)
                        tbl.setColumnWidth(4, 70)
                        tbl.setColumnWidth(5, 90)
                        tbl.setColumnWidth(6, 110)
                        tbl.setColumnWidth(7, 105)
                        tbl.setColumnWidth(8, 120)
                        tbl.setColumnWidth(9, 130)
                        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
                        tbl.horizontalHeader().setStretchLastSection(True)

                        history_trades = []
                        total_hist_vol = 0.0
                        total_hist_pnl = 0.0
                        if is_live:
                            from_date = datetime.now() - timedelta(days=30)
                            deals = mt5.history_deals_get(from_date, datetime.now())
                            if deals:
                                for d in deals:
                                    if d.entry in (1, 2) or (d.symbol and d.profit != 0):
                                        t_str = datetime.fromtimestamp(d.time).strftime("%H:%M:%S") if hasattr(d, "time") else "--:--:--"
                                        side_str = "BUY" if d.type == 0 else "SELL"
                                        info_s = mt5.symbol_info(d.symbol)
                                        dig = info_s.digits if info_s else 2
                                        pnl_str = f"+${d.profit:.2f}" if d.profit >= 0 else f"-${abs(d.profit):.2f}"
                                        comm_str = f"-${abs(d.commission):.2f}" if d.commission != 0 else "$0.00"
                                        strat_str = d.comment if d.comment else "Manual/Algo"
                                        history_trades.append((
                                             t_str, f"#{d.ticket}", d.symbol, strat_str, side_str,
                                             f"{d.volume:.2f}", f"{d.price:.{dig}f}", comm_str, pnl_str, "FILLED"
                                        ))
                                        total_hist_vol += d.volume
                                        total_hist_pnl += d.profit

                        tbl.setRowCount(len(history_trades))
                        for row, data in enumerate(history_trades):
                            for col, text in enumerate(data):
                                item = QTableWidgetItem(text)
                                item.setFont(mono_font)
                                if col in (5, 6, 7, 8):
                                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                                else:
                                    item.setTextAlignment(Qt.AlignCenter)

                                if col == 2:
                                    item.setForeground(clr_sym)
                                elif col == 3:
                                    item.setForeground(clr_strat)
                                elif col == 4:
                                    item.setForeground(clr_buy if data[4] == "BUY" else clr_pnl_neg)
                                elif col == 7:
                                    item.setForeground(clr_comm)
                                elif col == 8:
                                    if text.startswith("+"):
                                        item.setForeground(clr_pnl_pos)
                                    elif text.startswith("-"):
                                        item.setForeground(clr_pnl_neg)
                                    else:
                                        item.setForeground(clr_def)
                                elif col == 9:
                                    item.setForeground(clr_buy)
                                else:
                                    item.setForeground(clr_def)
                                tbl.setItem(row, col, item)

                        if hasattr(self, "blotter_buttons") and "history" in self.blotter_buttons:
                            self.blotter_buttons["history"].setText(f"ORDERS / DEALS ({len(history_trades)})")

                        if hasattr(self, "lbl_blotter_empty"):
                            if len(history_trades) == 0:
                                self.lbl_blotter_empty.setText("No orders in history")
                                self.lbl_blotter_empty.setVisible(True)
                            else:
                                self.lbl_blotter_empty.setVisible(False)

                        vol_col = "#f8fafc" if is_dark else "#0f172a"
                        grn_col = "#10b981" if is_dark else "#15803d" if total_hist_pnl >= 0 else ("#ef4444" if is_dark else "#b91c1c")
                        pnl_fmt = f"+${total_hist_pnl:,.2f}" if total_hist_pnl >= 0 else f"-${abs(total_hist_pnl):,.2f}"
                        self.lbl_dock_summary.setText(
                            f'CLOSED DEALS: <b style="color:{grn_col};">{len(history_trades)}</b> &nbsp;·&nbsp; '
                            f'TOTAL VOLUME: <b style="color:{vol_col};">{total_hist_vol:.2f} LOTS</b> &nbsp;·&nbsp; '
                            f'REALIZED P&L: <b style="color:{grn_col};">{pnl_fmt}</b>'
                        )

                    elif mode == "pending":
                        headers = ["TIME", "TICKET", "SYMBOL", "STRATEGY", "ORDER TYPE", "VOLUME", "PRICE", "SL", "TP", "STATUS"]
                        tbl.setColumnCount(len(headers))
                        for col_idx, h_text in enumerate(headers):
                            item = QTableWidgetItem(h_text)
                            tbl.setHorizontalHeaderItem(col_idx, item)

                        tbl.setColumnWidth(0, 95)
                        tbl.setColumnWidth(1, 90)
                        tbl.setColumnWidth(2, 85)
                        tbl.setColumnWidth(3, 190)
                        tbl.setColumnWidth(4, 100)
                        tbl.setColumnWidth(5, 85)
                        tbl.setColumnWidth(6, 105)
                        tbl.setColumnWidth(7, 105)
                        tbl.setColumnWidth(8, 105)
                        tbl.setColumnWidth(9, 120)
                        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
                        tbl.horizontalHeader().setStretchLastSection(True)

                        pending_records = []
                        if is_live:
                            orders = mt5.orders_get()
                            if orders:
                                for o in orders:
                                    t_str = datetime.fromtimestamp(o.time_setup).strftime("%H:%M:%S") if hasattr(o, "time_setup") else "--:--:--"
                                    info_s = mt5.symbol_info(o.symbol)
                                    dig = info_s.digits if info_s else 2
                                    type_str = "BUY LIMIT" if o.type == mt5.ORDER_TYPE_BUY_LIMIT else ("SELL LIMIT" if o.type == mt5.ORDER_TYPE_SELL_LIMIT else ("BUY STOP" if o.type == mt5.ORDER_TYPE_BUY_STOP else "SELL STOP"))
                                    pending_records.append((
                                        t_str, f"#{o.ticket}", o.symbol, o.comment or "Operator/AI", type_str,
                                        f"{o.volume_initial:.2f}", f"{o.price_open:.{dig}f}", f"{o.sl:.{dig}f}", f"{o.tp:.{dig}f}", "PENDING"
                                    ))

                        tbl.setRowCount(len(pending_records))
                        for row, data in enumerate(pending_records):
                            for col, text in enumerate(data):
                                item = QTableWidgetItem(text)
                                item.setFont(mono_font)
                                item.setTextAlignment(Qt.AlignCenter)
                                if col == 2:
                                    item.setForeground(clr_sym)
                                elif col == 4:
                                    item.setForeground(clr_buy if "BUY" in text else clr_pnl_neg)
                                else:
                                    item.setForeground(clr_def)
                                tbl.setItem(row, col, item)

                        if hasattr(self, "blotter_buttons") and "pending" in self.blotter_buttons:
                            self.blotter_buttons["pending"].setText(f"PENDING ORDERS ({len(pending_records)})")

                        if hasattr(self, "lbl_blotter_empty"):
                            if len(pending_records) == 0:
                                self.lbl_blotter_empty.setText("No pending orders")
                                self.lbl_blotter_empty.setVisible(True)
                            else:
                                self.lbl_blotter_empty.setVisible(False)

                        sub_col = "#94a3b8" if is_dark else "#64748b"
                        grn_col = "#10b981" if is_dark else "#15803d"
                        self.lbl_dock_summary.setText(
                            f'PENDING ORDERS: <b style="color:{sub_col};">{len(pending_records)}</b> &nbsp;·&nbsp; '
                            f'ORDER ROUTING: <b style="color:{grn_col};">ONLINE</b>'
                        )

                    if hasattr(self, "watchlist_mgr") and hasattr(self.watchlist_mgr, "refresh_all_status_icons"):
                        self.watchlist_mgr.refresh_all_status_icons()

                self._render_blotter = _render_blotter

                for t_label, t_mode in blotter_tabs:
                    btn_t = QPushButton(t_label)
                    btn_t.setFixedHeight(22)
                    btn_t.setCursor(Qt.PointingHandCursor)
                    btn_t.clicked.connect(lambda checked=False, m=t_mode: _render_blotter(m))
                    header_layout.addWidget(btn_t)
                    self.blotter_buttons[t_mode] = btn_t

                header_layout.addWidget(self.lbl_dock_summary)
                header_layout.addStretch()

                # Right action buttons: FILTERS & EXPORT CSV
                btn_filters = QPushButton("FILTERS")
                btn_filters.setFixedHeight(20)
                btn_filters.setCursor(Qt.PointingHandCursor)
                filter_icon = os.path.join(assets_dir, "icon_filter.svg")
                if os.path.exists(filter_icon):
                    btn_filters.setIcon(QIcon(filter_icon))
                    btn_filters.setIconSize(QSize(11, 11))
                btn_filters.setStyleSheet(
                    "QPushButton { background-color: transparent; color: #94a3b8; border: 1px solid #272d3b; "
                    "font-family: Consolas, monospace; font-size: 8.5px; font-weight: 600; border-radius: 2px; padding: 0 8px; } "
                    "QPushButton:hover { color: #ffffff; background-color: #141721; border-color: #3b4252; }"
                )
                self.btn_blotter_filters = btn_filters
                header_layout.addWidget(btn_filters)

                btn_export = QPushButton("EXPORT CSV")
                btn_export.setFixedHeight(20)
                btn_export.setCursor(Qt.PointingHandCursor)
                export_icon = os.path.join(assets_dir, "icon_export.svg")
                if os.path.exists(export_icon):
                    btn_export.setIcon(QIcon(export_icon))
                    btn_export.setIconSize(QSize(11, 11))
                btn_export.setStyleSheet(
                    "QPushButton { background-color: transparent; color: #94a3b8; border: 1px solid #272d3b; "
                    "font-family: Consolas, monospace; font-size: 8.5px; font-weight: 600; border-radius: 2px; padding: 0 8px; } "
                    "QPushButton:hover { color: #ffffff; background-color: #141721; border-color: #3b4252; }"
                )
                self.btn_blotter_export = btn_export
                header_layout.addWidget(btn_export)

                btn_flatten = QPushButton("FLATTEN ALL")
                btn_flatten.setFixedHeight(20)
                btn_flatten.setCursor(Qt.PointingHandCursor)
                btn_flatten.setToolTip("Close all open positions and pause algorithms")
                btn_flatten.clicked.connect(self._handle_kill_switch)
                self.btn_blotter_flatten = btn_flatten
                header_layout.addWidget(btn_flatten, 0, Qt.AlignVCenter)

                # Dock collapse/expand toggle (height 20px, strictly aligned with btn_flatten)
                btn_dock = QPushButton()
                btn_dock.setObjectName("btnDockToggle")
                btn_dock.setCursor(Qt.PointingHandCursor)
                btn_dock.setFixedSize(20, 20)
                btn_dock.setToolTip("Collapse / Expand Trade Blotter dock")
                is_dark = getattr(self, "is_dark_theme", False)
                if is_dark:
                    btn_dock.setStyleSheet(
                        "QPushButton#btnDockToggle { background-color: transparent; border: 1px solid #272d3b; border-radius: 2px; padding: 0px; margin: 0px; min-height: 20px; max-height: 20px; min-width: 20px; max-width: 20px; } "
                        "QPushButton#btnDockToggle:hover { background-color: #1e293b; border-color: #475569; }"
                    )
                else:
                    btn_dock.setStyleSheet(
                        "QPushButton#btnDockToggle { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 2px; padding: 0px; margin: 0px; min-height: 20px; max-height: 20px; min-width: 20px; max-width: 20px; } "
                        "QPushButton#btnDockToggle:hover { background-color: #f1f5f9; border-color: #94a3b8; }"
                    )
                collapse_svg = os.path.join(assets_dir, "dock_collapse.svg")
                expand_svg = os.path.join(assets_dir, "dock_expand.svg")
                if os.path.exists(collapse_svg):
                    btn_dock.setIcon(QIcon(collapse_svg))
                    btn_dock.setIconSize(QSize(10, 10))
                self.window.is_dock_collapsed = False
                def _toggle_dock():
                    self.window.is_dock_collapsed = not getattr(self.window, "is_dock_collapsed", False)
                    if self.window.is_dock_collapsed:
                        self.window.tableExecutions.setVisible(False)
                        self.window.frameExecutions.setMinimumHeight(28)
                        self.window.frameExecutions.setFixedHeight(28)
                        if os.path.exists(expand_svg):
                            btn_dock.setIcon(QIcon(expand_svg))
                    else:
                        self.window.tableExecutions.setVisible(True)
                        self.window.frameExecutions.setMinimumHeight(155)
                        self.window.frameExecutions.setFixedHeight(155)
                        if os.path.exists(collapse_svg):
                            btn_dock.setIcon(QIcon(collapse_svg))
                btn_dock.clicked.connect(_toggle_dock)
                self.window.btnDockToggle = btn_dock
                header_layout.addWidget(btn_dock, 0, Qt.AlignVCenter)

                # Initial render of active positions
                _render_blotter("active")

        # Reparent frameExecutions to tab_live layout so it spans 100% full width below chartSplitter
        tab_live = getattr(self.window, "tab2", None) or self.window.tabWidget.widget(1)
        if hasattr(self.window, "layoutChartAndExec") and hasattr(self.window, "frameExecutions") and tab_live:
            self.window.layoutChartAndExec.removeWidget(self.window.frameExecutions)
            tab_live.layout().addWidget(self.window.frameExecutions)
    def _close_single_position(self, ticket: int):
        """Institutional position liquidation at market price."""
        is_live = mt5.terminal_info() is not None
        if is_live:
            res = self.exec_mgr.close_position(ticket)
            if res.get("status") == "success":
                lat = res.get("latency_ms", 0.0)
                event_bus.log_event.emit(
                    "",
                    "INFO",
                    f"LIQUIDATED POSITION #{ticket} | LATENCY: {lat:.1f}ms",
                    "#10b981",
                )
                telegram_notifier.send_message(
                    f"<b>[TRADE LIQUIDATION]</b>\nPosition #{ticket} closed successfully.\nExecution latency: {lat:.1f}ms"
                )
            else:
                err_msg = res.get("msg", "Unknown error")
                event_bus.log_event.emit(
                    "",
                    "ERROR",
                    f"FAILED TO CLOSE #{ticket}: {err_msg}",
                    "#ef4444",
                )
        else:
            # Simulated demo closure
            if hasattr(self, "_demo_positions") and self._demo_positions:
                self._demo_positions = [p for p in self._demo_positions if p["ticket"] != ticket]
            event_bus.log_event.emit(
                "",
                "INFO",
                f"[SIMULATION] LIQUIDATED POSITION #{ticket}",
                "#10b981",
            )

        if hasattr(self, "_render_blotter"):
            self._render_blotter("active")

    def _modify_single_position(self, pos_info: dict):
        """Open institutional ModifyOrderDialog and execute TRADE_ACTION_SLTP."""
        ticket = pos_info.get("ticket", 0)
        sym = pos_info.get("symbol", "XAUUSD")
        order_type = pos_info.get("side", "BUY")
        vol = float(pos_info.get("volume", pos_info.get("lots", 0.1)))
        open_p = float(pos_info.get("open_price", pos_info.get("entry", 0.0)))
        cur_p = float(pos_info.get("current_price", pos_info.get("current", 0.0)))
        sl = float(pos_info.get("sl", 0.0))
        tp = float(pos_info.get("tp", 0.0))
        digits = int(pos_info.get("digits", 2))
        is_dark = getattr(self, "is_dark_theme", False)

        dlg = ModifyOrderDialog(
            ticket=ticket,
            symbol=sym,
            order_type=order_type,
            volume=vol,
            open_price=open_p,
            current_price=cur_p,
            current_sl=sl,
            current_tp=tp,
            digits=digits,
            is_dark=is_dark,
            parent=self.window,
        )
        if dlg.exec():
            new_sl, new_tp = dlg.get_values()
            is_live = mt5.terminal_info() is not None
            if is_live:
                res = self.exec_mgr.modify_position(ticket, new_sl, new_tp)
                if res.get("status") == "success":
                    event_bus.log_event.emit(
                        "",
                        "INFO",
                        f"MODIFIED ORDER #{ticket} | SL: {new_sl} | TP: {new_tp}",
                        "#10b981",
                    )
                else:
                    event_bus.log_event.emit(
                        "",
                        "ERROR",
                        f"FAILED TO MODIFY #{ticket}: {res.get('msg', 'Error')}",
                        "#ef4444",
                    )
            else:
                if hasattr(self, "_demo_positions") and self._demo_positions:
                    for p in self._demo_positions:
                        if p["ticket"] == ticket:
                            p["sl"] = new_sl
                            p["tp"] = new_tp
                event_bus.log_event.emit(
                    "",
                    "INFO",
                    f"[SIMULATION] MODIFIED #{ticket} | SL: {new_sl} | TP: {new_tp}",
                    "#10b981",
                )
            if hasattr(self, "_render_blotter"):
                self._render_blotter("active")

    def _apply_flatten_btn_style(self):
        if not hasattr(self, "btn_blotter_flatten") or not self.btn_blotter_flatten:
            return
        is_dark = getattr(self, "is_dark_theme", False)
        if is_dark:
            self.btn_blotter_flatten.setStyleSheet(
                "QPushButton { background-color: #991b1b; color: #ffffff; border: 1px solid #7f1d1d; "
                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0 8px; } "
                "QPushButton:hover { background-color: #b91c1c; border-color: #991b1b; }"
            )
        else:
            self.btn_blotter_flatten.setStyleSheet(
                "QPushButton { background-color: #dc2626; color: #ffffff; border: 1px solid #cbd5e1; "
                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0 8px; } "
                "QPushButton:hover { background-color: #b91c1c; border-color: #94a3b8; }"
            )

    def _disarm_flatten_button(self):
        self._flatten_armed = False
        if hasattr(self, "_flatten_timer") and self._flatten_timer and self._flatten_timer.isActive():
            self._flatten_timer.stop()
        if hasattr(self, "btn_blotter_flatten") and self.btn_blotter_flatten:
            self.btn_blotter_flatten.setText("FLATTEN ALL")
            self._apply_flatten_btn_style()

    def _on_flatten_timer_tick(self):
        self._flatten_countdown -= 1
        btn = getattr(self, "btn_blotter_flatten", None)
        if not btn:
            return
        if self._flatten_countdown > 0:
            btn.setText(f"CONFIRM FLATTEN ({self._flatten_countdown}s)")
        else:
            self._disarm_flatten_button()

    def _handle_kill_switch(self):
        """Emergency Kill-Switch / Flatten All: 2-step armed click confirmation to prevent accidental liquidation."""
        btn = getattr(self, "btn_blotter_flatten", None)
        if not btn:
            return

        is_armed = getattr(self, "_flatten_armed", False)
        if not is_armed:
            self._flatten_armed = True
            self._flatten_countdown = 3
            btn.setText("CONFIRM FLATTEN (3s)")
            btn.setStyleSheet(
                "QPushButton { background-color: #b91c1c; color: #ffffff; border: 1px solid #475569; "
                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0 6px; } "
                "QPushButton:hover { background-color: #dc2626; border-color: #991b1b; }"
            )
            if not hasattr(self, "_flatten_timer") or self._flatten_timer is None:
                from PySide6.QtCore import QTimer
                self._flatten_timer = QTimer(self.window)
                self._flatten_timer.setInterval(1000)
                self._flatten_timer.timeout.connect(self._on_flatten_timer_tick)
            self._flatten_timer.start()
            return

        self._disarm_flatten_button()
        btn.setText("LIQUIDATING...")
        btn.setEnabled(False)

        # 1. Panic close all open positions and pending orders on MT5 broker
        results = []
        if mt5.terminal_info() is not None:
            results = self.exec_mgr.panic_kill_switch_all()
        else:
            if hasattr(self, "_demo_positions"):
                self._demo_positions = []

        # 2. Halt bot worker and thread
        if self.bot_worker:
            self.bot_worker.stop()

        if self.bot_thread and self.bot_thread.isRunning():
            self.bot_thread.quit()
            self.bot_thread.wait(500)

        self.btnStart.setText(_TXT_START)
        self.btnStart.setProperty("running", "false")
        if hasattr(self, "btn_bot_power"):
            if hasattr(self.btn_bot_power, "set_running"):
                self.btn_bot_power.set_running(False, emit_signal=False)
            else:
                self.btn_bot_power.setProperty("running", "false")

        self.btnStart.style().unpolish(self.btnStart)
        self.btnStart.style().polish(self.btnStart)

        # 3. Log and Telegram Alert
        detail_msg = f" Liquidated {len(results)} orders." if results else " All active trading halted."
        event_bus.log_event.emit(
            "",
            "ERROR",
            f"EMERGENCY KILL-SWITCH EXECUTED!{detail_msg}",
            "#ef4444",
        )

        telegram_notifier.send_message(
            f"<b>[EMERGENCY KILL-SWITCH]</b>\nFlatten all positions triggered from Terminal!{detail_msg}\nStatus: HALTED"
        )

        # 4. Refresh blotter immediately
        if hasattr(self, "_render_blotter"):
            self._render_blotter("active")

