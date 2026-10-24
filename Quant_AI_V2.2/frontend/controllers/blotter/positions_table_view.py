"""
Positions Table View - Institutional MT5-Style Trade Blotter Renderer.
Handles table layouts, dock controls, header tabs, and row rendering for
active positions, history deals, and pending orders.
"""

import os
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)
from backend.infrastructure.brokers.mt5_safe import mt5


class PositionsTableView:
    """Renders and manages the tableExecutions dock component."""

    def __init__(self, window, controller):
        self.window = window
        self.controller = controller
        self.blotter_buttons = {}
        self.lbl_blotter_empty = None
        self.lbl_dock_summary = None
        self.btn_blotter_filters = None
        self.btn_blotter_export = None
        self.btn_blotter_flatten = None
        self._last_mode = None
        self._last_active_tickets = None
        self._last_theme = None

    def setup_ui(self):
        """Setup institutional MT5-style Trade Blotter layout, dock header tabs, and toggle button."""
        if not hasattr(self.window, "tableExecutions"):
            return

        tbl = self.window.tableExecutions
        tbl.verticalHeader().setDefaultSectionSize(28)
        tbl.verticalHeader().setVisible(False)
        tbl.setShowGrid(False)

        # Empty state indicator for trade blotter
        if not hasattr(self, "lbl_blotter_empty") or self.lbl_blotter_empty is None:
            self.layout_blotter_vp = QVBoxLayout(tbl.viewport())
            self.layout_blotter_vp.setContentsMargins(0, 0, 0, 0)
            self.lbl_blotter_empty = QLabel("No open positions", tbl.viewport())
            self.lbl_blotter_empty.setAlignment(Qt.AlignCenter)
            self.lbl_blotter_empty.setStyleSheet(
                "color: #64748b; font-family: 'Segoe UI', sans-serif; font-size: 11px; font-weight: 500; background: transparent;"
            )
            self.lbl_blotter_empty.setVisible(False)
            self.layout_blotter_vp.addWidget(self.lbl_blotter_empty)

        assets_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "assets"
        )
        if not os.path.exists(assets_dir):
            assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")

        if hasattr(self.window, "frameExecutions"):
            self.window.frameExecutions.setFixedHeight(155)
            for _lbl_name in ["lblExecutionsFilters", "lblExecutionsTitle", "badgeExecutionsCount"]:
                if hasattr(self.window, _lbl_name):
                    getattr(self.window, _lbl_name).setVisible(False)

            # Reconstruct dock header layout inside frameExecutions
            exec_layout = self.window.frameExecutions.layout()
            if exec_layout:
                exec_layout.setContentsMargins(0, 0, 0, 0)
                exec_layout.setSpacing(0)
            if exec_layout and exec_layout.itemAt(0) and exec_layout.itemAt(0).layout():
                header_layout = exec_layout.itemAt(0).layout()
                while header_layout.count():
                    item = header_layout.takeAt(0)
                    w = item.widget()
                    if w:
                        w.deleteLater()

                # Left margin 26px precisely aligns with the 26px width of toolbarChartDrawing
                header_layout.setContentsMargins(26, 0, 6, 0)
                header_layout.setSpacing(6)
                header_layout.setAlignment(Qt.AlignVCenter)

                # Real Trade Blotter Tabs
                blotter_tabs = [
                    ("POSITIONS (0)", "active"),
                    ("ORDERS / DEALS", "history"),
                    ("PENDING ORDERS (0)", "pending"),
                ]
                self.blotter_buttons = {}

                # Institutional summary badge in dock header (dynamically updated)
                self.lbl_dock_summary = QLabel()
                self.lbl_dock_summary.setFixedHeight(20)
                self.lbl_dock_summary.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                self.lbl_dock_summary.setStyleSheet(
                    "color:#64748b; font-family:Consolas, monospace; font-size:9px; padding-left: 14px; margin: 0px;"
                )

                for t_label, t_mode in blotter_tabs:
                    btn_t = QPushButton(t_label)
                    btn_t.setFixedHeight(20)
                    btn_t.setCursor(Qt.PointingHandCursor)
                    btn_t.clicked.connect(lambda checked=False, m=t_mode: self.render(m))
                    header_layout.addWidget(btn_t, 0, Qt.AlignVCenter)
                    self.blotter_buttons[t_mode] = btn_t

                header_layout.addWidget(self.lbl_dock_summary, 0, Qt.AlignVCenter)
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
                    "font-family: Consolas, monospace; font-size: 8.5px; font-weight: 600; border-radius: 2px; padding: 0 8px; margin: 0px; } "
                    "QPushButton:hover { color: #ffffff; background-color: #141721; border-color: #3b4252; }"
                )
                self.btn_blotter_filters = btn_filters
                header_layout.addWidget(btn_filters, 0, Qt.AlignVCenter)

                btn_export = QPushButton("EXPORT CSV")
                btn_export.setFixedHeight(20)
                btn_export.setCursor(Qt.PointingHandCursor)
                export_icon = os.path.join(assets_dir, "icon_export.svg")
                if os.path.exists(export_icon):
                    btn_export.setIcon(QIcon(export_icon))
                    btn_export.setIconSize(QSize(11, 11))
                btn_export.setStyleSheet(
                    "QPushButton { background-color: transparent; color: #94a3b8; border: 1px solid #272d3b; "
                    "font-family: Consolas, monospace; font-size: 8.5px; font-weight: 600; border-radius: 2px; padding: 0 8px; margin: 0px; } "
                    "QPushButton:hover { color: #ffffff; background-color: #141721; border-color: #3b4252; }"
                )
                self.btn_blotter_export = btn_export
                header_layout.addWidget(btn_export, 0, Qt.AlignVCenter)

                btn_flatten = QPushButton("FLATTEN ALL")
                btn_flatten.setFixedHeight(20)
                btn_flatten.setCursor(Qt.PointingHandCursor)
                btn_flatten.setToolTip("Close all open positions and pause algorithms")
                btn_flatten.clicked.connect(self.controller._handle_kill_switch)
                self.btn_blotter_flatten = btn_flatten
                self.controller.btn_blotter_flatten = btn_flatten
                header_layout.addWidget(btn_flatten, 0, Qt.AlignVCenter)

                # Dock collapse/expand toggle
                btn_dock = QPushButton()
                btn_dock.setObjectName("btnDockToggle")
                btn_dock.setCursor(Qt.PointingHandCursor)
                btn_dock.setFixedSize(20, 20)
                btn_dock.setToolTip("Collapse / Expand Trade Blotter dock")
                is_dark = getattr(self.controller, "is_dark_theme", False)
                if is_dark:
                    btn_dock.setStyleSheet(
                        "QPushButton#btnDockToggle { background-color: transparent; border: 1px solid #272d3b; border-radius: 2px; padding: 0px; margin: 0px; min-height: 18px; max-height: 18px; min-width: 18px; max-width: 18px; } "
                        "QPushButton#btnDockToggle:hover { background-color: #1e293b; border-color: #475569; }"
                    )
                else:
                    btn_dock.setStyleSheet(
                        "QPushButton#btnDockToggle { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 2px; padding: 0px; margin: 0px; min-height: 18px; max-height: 18px; min-width: 18px; max-width: 18px; } "
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
                        self.window.frameExecutions.setMinimumHeight(26)
                        self.window.frameExecutions.setFixedHeight(26)
                        if self.btn_blotter_filters:
                            self.btn_blotter_filters.hide()
                        if self.btn_blotter_export:
                            self.btn_blotter_export.hide()
                        if os.path.exists(expand_svg):
                            btn_dock.setIcon(QIcon(expand_svg))
                    else:
                        self.window.tableExecutions.setVisible(True)
                        self.window.frameExecutions.setMinimumHeight(155)
                        self.window.frameExecutions.setFixedHeight(155)
                        if self.btn_blotter_filters:
                            self.btn_blotter_filters.show()
                        if self.btn_blotter_export:
                            self.btn_blotter_export.show()
                        if os.path.exists(collapse_svg):
                            btn_dock.setIcon(QIcon(collapse_svg))
                    self._update_tab_styles()

                btn_dock.clicked.connect(_toggle_dock)
                self.window.btnDockToggle = btn_dock
                header_layout.addWidget(btn_dock, 0, Qt.AlignVCenter)

                # Initial render of active positions
                self.render("active")

        # Reparent frameExecutions to tab_live layout so it spans 100% full width below chartSplitter
        tab_live = getattr(self.window, "tab2", None) or (
            self.window.tabWidget.widget(1) if hasattr(self.window, "tabWidget") else None
        )
        if hasattr(self.window, "layoutChartAndExec") and hasattr(self.window, "frameExecutions") and tab_live:
            self.window.layoutChartAndExec.removeWidget(self.window.frameExecutions)
            tab_live.layout().addWidget(self.window.frameExecutions)

    def _update_tab_styles(self, mode: Optional[str] = None):
        """Update tab button styles reflecting both active mode and dock collapsed/expanded state."""
        if mode is None:
            mode = getattr(self.controller, "active_blotter_mode", "active")
        is_dark = getattr(self.controller, "is_dark_theme", False)
        is_collapsed = getattr(self.window, "is_dock_collapsed", False)

        for m_key, b_obj in self.blotter_buttons.items():
            if m_key == mode:
                if is_collapsed:
                    # Clean flat underline accent when collapsed (no broken 3-sided box)
                    accent_c = "#38bdf8" if is_dark else "#0284c7"
                    text_c = "#ffffff" if is_dark else "#0f172a"
                    b_obj.setStyleSheet(
                        f"QPushButton {{ background-color: transparent; color: {text_c}; border: none; "
                        f"border-bottom: 2px solid {accent_c}; font-family: Consolas, monospace; "
                        "font-size: 9px; font-weight: bold; padding: 0 10px; margin: 0px; min-height: 20px; max-height: 20px; }"
                    )
                else:
                    # Connected tab border when expanded into table below
                    if is_dark:
                        b_obj.setStyleSheet(
                            "QPushButton { background-color: #12151d; color: #ffffff; border: 1px solid #272d3b; "
                            "border-top: 2px solid #f8fafc; border-bottom: none; font-family: Consolas, monospace; "
                            "font-size: 9px; font-weight: bold; padding: 0 12px; border-top-left-radius: 2px; border-top-right-radius: 2px; "
                            "margin: 0px; min-height: 20px; max-height: 20px; }"
                        )
                    else:
                        b_obj.setStyleSheet(
                            "QPushButton { background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; "
                            "border-top: 2px solid #0f172a; border-bottom: none; font-family: Consolas, monospace; "
                            "font-size: 9px; font-weight: bold; padding: 0 12px; border-top-left-radius: 2px; border-top-right-radius: 2px; "
                            "margin: 0px; min-height: 20px; max-height: 20px; }"
                        )
            else:
                color_inactive = "#94a3b8" if is_dark else "#64748b"
                hover_bg = "#141721" if is_dark else "#e2e8f0"
                hover_color = "#ffffff" if is_dark else "#0f172a"
                b_obj.setStyleSheet(
                    f"QPushButton {{ background-color: transparent; color: {color_inactive}; border: none; "
                    "font-family: Consolas, monospace; font-size: 9px; font-weight: 600; padding: 0 8px; margin: 0px; "
                    "min-height: 20px; max-height: 20px; } "
                    f"QPushButton:hover {{ color: {hover_color}; background-color: {hover_bg}; }}"
                )

    def render(self, mode: Optional[str] = None):
        """Render active positions, history deals, or pending orders based on mode."""
        if not hasattr(self.window, "tableExecutions"):
            return

        tbl = self.window.tableExecutions
        if mode is None:
            mode = getattr(self.controller, "active_blotter_mode", "active")
        self.controller.active_blotter_mode = mode
        if hasattr(self.controller, "terminal"):
            try:
                self.controller.terminal.active_blotter_mode = mode
            except Exception:
                pass
        is_dark = getattr(self.controller, "is_dark_theme", False)
        is_live = mt5.terminal_info() is not None
        is_dock_col = getattr(self.window, "is_dock_collapsed", False)

        # Tab button styles reflecting mode & collapsed/expanded state
        self._update_tab_styles(mode)

        # Always synchronize live counts for POSITIONS and PENDING ORDERS
        try:
            cur_pos = mt5.positions_get() if is_live else None
            n_pos = len(cur_pos) if cur_pos else 0
            if hasattr(self, "blotter_buttons") and "active" in self.blotter_buttons:
                self.blotter_buttons["active"].setText(f"POSITIONS ({n_pos})")

            cur_orders = mt5.orders_get() if is_live else None
            n_orders = len(cur_orders) if cur_orders else 0
            if hasattr(self, "blotter_buttons") and "pending" in self.blotter_buttons:
                self.blotter_buttons["pending"].setText(f"PENDING ORDERS ({n_orders})")
        except Exception as e_cnt:
            logger.debug(f"[Blotter] Live tab counts error: {e_cnt}")

        # Update FILTERS & EXPORT CSV buttons style & visibility (hidden when dock is collapsed)
        if hasattr(self, "btn_blotter_filters") and self.btn_blotter_filters:
            self.btn_blotter_filters.setVisible(not is_dock_col)
            if is_dark:
                self.btn_blotter_filters.setStyleSheet(
                    "QPushButton { background-color: transparent; color: #94a3b8; border: 1px solid #272d3b; "
                    "font-family: Consolas, monospace; font-size: 8.5px; font-weight: 600; border-radius: 2px; padding: 0 8px; margin: 0px; } "
                    "QPushButton:hover { color: #ffffff; background-color: #141721; border-color: #3b4252; }"
                )
            else:
                self.btn_blotter_filters.setStyleSheet(
                    "QPushButton { background-color: #ffffff; color: #475569; border: 1px solid #cbd5e1; "
                    "font-family: Consolas, monospace; font-size: 8.5px; font-weight: 600; border-radius: 2px; padding: 0 8px; margin: 0px; } "
                    "QPushButton:hover { color: #0f172a; background-color: #e2e8f0; border-color: #94a3b8; }"
                )
        if hasattr(self, "btn_blotter_export") and self.btn_blotter_export:
            self.btn_blotter_export.setVisible(not is_dock_col)
            if is_dark:
                self.btn_blotter_export.setStyleSheet(
                    "QPushButton { background-color: transparent; color: #94a3b8; border: 1px solid #272d3b; "
                    "font-family: Consolas, monospace; font-size: 8.5px; font-weight: 600; border-radius: 2px; padding: 0 8px; margin: 0px; } "
                    "QPushButton:hover { color: #ffffff; background-color: #141721; border-color: #3b4252; }"
                )
            else:
                self.btn_blotter_export.setStyleSheet(
                    "QPushButton { background-color: #ffffff; color: #475569; border: 1px solid #cbd5e1; "
                    "font-family: Consolas, monospace; font-size: 8.5px; font-weight: 600; border-radius: 2px; padding: 0 8px; margin: 0px; } "
                    "QPushButton:hover { color: #0f172a; background-color: #e2e8f0; border-color: #94a3b8; }"
                )

        self.controller._apply_flatten_btn_style()

        mono_font = QFont("Consolas", 9)
        clr_sym = QColor("#ffffff" if is_dark else "#0f172a")
        clr_strat = QColor("#cbd5e1" if is_dark else "#334155")
        clr_buy = QColor("#10b981" if is_dark else "#15803d")
        clr_pnl_pos = QColor("#10b981" if is_dark else "#15803d")
        clr_pnl_neg = QColor("#ef4444" if is_dark else "#b91c1c")
        clr_comm = QColor("#94a3b8" if is_dark else "#64748b")
        clr_def = QColor("#cbd5e1" if is_dark else "#334155")

        if mode == "active":
            pos_records = []
            total_exposure = 0.0
            total_unrealized = 0.0

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
                pos_records = getattr(self.controller, "_demo_positions", []) or []
                for p in pos_records:
                    total_exposure += p.get("volume", 0.0)
                    total_unrealized += p.get("pnl_val", 0.0)

            current_tickets = [p["ticket"] for p in pos_records]
            can_in_place_update = (
                getattr(self, "_last_mode", None) == "active"
                and getattr(self, "_last_theme", None) == is_dark
                and getattr(self, "_last_active_tickets", None) == current_tickets
                and tbl.rowCount() == len(pos_records)
                and tbl.columnCount() == 10
            )

            if can_in_place_update:
                for row, p in enumerate(pos_records):
                    item_curr = tbl.item(row, 7)
                    if item_curr:
                        item_curr.setText(p["current"])
                    item_pnl = tbl.item(row, 8)
                    if item_pnl:
                        item_pnl.setText(p["pnl_str"])
                        item_pnl.setForeground(clr_pnl_pos if p["pnl_val"] >= 0 else clr_pnl_neg)

                if hasattr(self, "blotter_buttons") and "active" in self.blotter_buttons:
                    self.blotter_buttons["active"].setText(f"POSITIONS ({len(pos_records)})")

                if hasattr(self, "lbl_blotter_empty") and self.lbl_blotter_empty:
                    self.lbl_blotter_empty.setVisible(len(pos_records) == 0)

                exp_col = "#f8fafc" if is_dark else "#0f172a"
                pnl_col = "#10b981" if is_dark else "#15803d" if total_unrealized >= 0 else ("#ef4444" if is_dark else "#b91c1c")
                pnl_fmt = f"+${total_unrealized:,.2f}" if total_unrealized >= 0 else f"-${abs(total_unrealized):,.2f}"
                if self.lbl_dock_summary:
                    self.lbl_dock_summary.setText(
                        f'EXPOSURE: <b style="color:{exp_col};">{total_exposure:.2f} LOTS</b> &nbsp;·&nbsp; '
                        f'UNREALIZED P&L: <b style="color:{pnl_col};">{pnl_fmt}</b>'
                    )
                return

            self._last_mode = "active"
            self._last_theme = is_dark
            self._last_active_tickets = current_tickets
            tbl.clear()

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

                # Column 9: ACTIONS ([MODIFY], [CLOSE])
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
                        "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0px 4px; margin: 0px; min-height: 20px; } "
                        "QPushButton#btnRowModify:hover { background-color: #1e293b; color: #ffffff; border-color: #475569; }"
                    )
                else:
                    btn_mod.setStyleSheet(
                        "QPushButton#btnRowModify { background-color: #ffffff; border: 1px solid #cbd5e1; color: #334155; "
                        "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0px 4px; margin: 0px; min-height: 20px; } "
                        "QPushButton#btnRowModify:hover { background-color: #f1f5f9; color: #0f172a; border-color: #94a3b8; }"
                    )
                btn_mod.clicked.connect(lambda chk=False, pinfo=p: self.controller._modify_single_position(pinfo))

                btn_cls = QPushButton("CLOSE")
                btn_cls.setObjectName("btnRowClose")
                btn_cls.setFixedSize(48, 20)
                btn_cls.setCursor(Qt.PointingHandCursor)
                if is_dark:
                    btn_cls.setStyleSheet(
                        "QPushButton#btnRowClose { background-color: #2a0d10; border: 1px solid #272d3b; color: #dc2626; "
                        "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0px 4px; margin: 0px; min-height: 20px; } "
                        "QPushButton#btnRowClose:hover { background-color: #450a0a; color: #ffffff; border-color: #475569; }"
                    )
                else:
                    btn_cls.setStyleSheet(
                        "QPushButton#btnRowClose { background-color: #ffffff; border: 1px solid #cbd5e1; color: #dc2626; "
                        "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0px 4px; margin: 0px; min-height: 20px; } "
                        "QPushButton#btnRowClose:hover { background-color: #fef2f2; color: #b91c1c; border-color: #94a3b8; }"
                    )
                btn_cls.clicked.connect(lambda chk=False, t=p["ticket"]: self.controller._close_single_position(t))

                act_layout.addWidget(btn_mod)
                act_layout.addWidget(btn_cls)
                tbl.setCellWidget(row, 9, act_widget)

            if hasattr(self, "blotter_buttons") and "active" in self.blotter_buttons:
                self.blotter_buttons["active"].setText(f"POSITIONS ({len(pos_records)})")

            if hasattr(self, "lbl_blotter_empty") and self.lbl_blotter_empty:
                if len(pos_records) == 0:
                    self.lbl_blotter_empty.setText("No open positions")
                    self.lbl_blotter_empty.setVisible(True)
                else:
                    self.lbl_blotter_empty.setVisible(False)

            exp_col = "#f8fafc" if is_dark else "#0f172a"
            pnl_col = "#10b981" if is_dark else "#15803d" if total_unrealized >= 0 else ("#ef4444" if is_dark else "#b91c1c")
            pnl_fmt = f"+${total_unrealized:,.2f}" if total_unrealized >= 0 else f"-${abs(total_unrealized):,.2f}"
            if self.lbl_dock_summary:
                self.lbl_dock_summary.setText(
                    f'EXPOSURE: <b style="color:{exp_col};">{total_exposure:.2f} LOTS</b> &nbsp;·&nbsp; '
                    f'UNREALIZED P&L: <b style="color:{pnl_col};">{pnl_fmt}</b>'
                )

        elif mode == "history":
            self._last_mode = "history"
            self._last_theme = is_dark
            self._last_active_tickets = None
            tbl.clear()
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

            if hasattr(self, "lbl_blotter_empty") and self.lbl_blotter_empty:
                if len(history_trades) == 0:
                    self.lbl_blotter_empty.setText("No orders in history")
                    self.lbl_blotter_empty.setVisible(True)
                else:
                    self.lbl_blotter_empty.setVisible(False)

            vol_col = "#f8fafc" if is_dark else "#0f172a"
            grn_col = "#10b981" if is_dark else "#15803d" if total_hist_pnl >= 0 else ("#ef4444" if is_dark else "#b91c1c")
            pnl_fmt = f"+${total_hist_pnl:,.2f}" if total_hist_pnl >= 0 else f"-${abs(total_hist_pnl):,.2f}"
            if self.lbl_dock_summary:
                self.lbl_dock_summary.setText(
                    f'CLOSED DEALS: <b style="color:{grn_col};">{len(history_trades)}</b> &nbsp;·&nbsp; '
                    f'TOTAL VOLUME: <b style="color:{vol_col};">{total_hist_vol:.2f} LOTS</b> &nbsp;·&nbsp; '
                    f'REALIZED P&L: <b style="color:{grn_col};">{pnl_fmt}</b>'
                )

        elif mode == "pending":
            self._last_mode = "pending"
            self._last_theme = is_dark
            self._last_active_tickets = None
            tbl.clear()
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
                        type_str = "BUY LIMIT" if o.type == mt5.ORDER_TYPE_BUY_LIMIT else (
                            "SELL LIMIT" if o.type == mt5.ORDER_TYPE_SELL_LIMIT else (
                                "BUY STOP" if o.type == mt5.ORDER_TYPE_BUY_STOP else "SELL STOP"
                            )
                        )
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

            if hasattr(self, "lbl_blotter_empty") and self.lbl_blotter_empty:
                if len(pending_records) == 0:
                    self.lbl_blotter_empty.setText("No pending orders")
                    self.lbl_blotter_empty.setVisible(True)
                else:
                    self.lbl_blotter_empty.setVisible(False)

            sub_col = "#94a3b8" if is_dark else "#64748b"
            grn_col = "#10b981" if is_dark else "#15803d"
            if self.lbl_dock_summary:
                self.lbl_dock_summary.setText(
                    f'PENDING ORDERS: <b style="color:{sub_col};">{len(pending_records)}</b> &nbsp;·&nbsp; '
                    f'ORDER ROUTING: <b style="color:{grn_col};">ONLINE</b>'
                )

        if hasattr(self.controller, "watchlist_mgr") and hasattr(self.controller.watchlist_mgr, "refresh_all_status_icons"):
            self.controller.watchlist_mgr.refresh_all_status_icons()
