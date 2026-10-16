"""
Workspace Header Controller for Quant_AI V2.2
"""

import os
import sys
from datetime import datetime, timedelta
from loguru import logger
from PySide6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QFrame, QTableWidgetItem, QCheckBox, QGraphicsDropShadowEffect,
    QSizePolicy, QComboBox, QMessageBox, QHeaderView, QMenu
)
from PySide6.QtGui import QFont, QIcon, QColor, QCursor, QKeySequence, QShortcut, QMouseEvent
from PySide6.QtCore import Qt, QTimer, QFile, QIODevice, QObject, QThread, QSize, QPoint
from backend.infrastructure.brokers.mt5_safe import mt5
from frontend.widgets.bot_power_button import AlgoControlPill


class WorkspaceHeaderController:
    """Manages the top workspace ribbon, telemetry ticker, and frameless window controls."""

    def __init__(self, terminal):
        self.terminal = terminal
        self.window = terminal.window

    def __getattr__(self, name):
        return getattr(self.terminal, name)

    def __setattr__(self, name, value):
        if name in ("terminal", "window"):
            super().__setattr__(name, value)
        else:
            super().__setattr__(name, value)
            if hasattr(self, "terminal"):
                setattr(self.terminal, name, value)

    def _format_top_ticker(self, bal=100000.0, eq=100000.0, pnl=0.0, pnl_pct=0.0, max_dd=0.0, latency=1.2, is_algo_active=False, is_dark=None):
        if is_dark is None:
            is_dark = getattr(self, "is_dark_theme", False)
        if pnl < 0:
            pnl_txt = f"-${abs(pnl):,.2f}"
            pnl_color = "#ef4444" if is_dark else "#b91c1c"
        else:
            pnl_txt = f"+${pnl:,.2f}"
            pnl_color = "#10b981" if is_dark else "#15803d"

        lbl_col = "#71717a" if is_dark else "#64748b"
        val_col = "#ffffff" if is_dark else "#0f172a"
        sep_col = "#262626" if is_dark else "#cbd5e1"
        lat_col = "#10b981" if is_dark else "#15803d"

        return (
            f'<span style="color:{lbl_col}; font-size:9.5px; font-family:Consolas, monospace;">'
            f'BALANCE: <b style="color:{val_col};">${bal:,.2f}</b>&nbsp;&nbsp;<span style="color:{sep_col};">|</span>&nbsp;&nbsp;'
            f'EQUITY: <b style="color:{val_col};">${eq:,.2f}</b>&nbsp;&nbsp;<span style="color:{sep_col};">|</span>&nbsp;&nbsp;'
            f'NET P&L: <b style="color:{pnl_color};">{pnl_txt}</b>'
            f'</span>'
        )

    def _update_tf_button_styles(self, is_dark=None):
        if is_dark is None:
            is_dark = getattr(self, "is_dark_theme", False)
        if not hasattr(self, "tf_buttons") or not self.tf_buttons:
            return
        active_tf = getattr(self, "active_timeframe", "H1")
        for tf_name, btn_tf in self.tf_buttons.items():
            is_active = (tf_name == active_tf)
            if is_active:
                if is_dark:
                    btn_tf.setStyleSheet(
                        "QPushButton { background-color: #064e3b; color: #34d399; border: 1px solid #059669; "
                        "font-family: Consolas, monospace; font-size: 9px; font-weight: bold; border-radius: 2px; padding: 0px; margin: 0px; }"
                    )
                else:
                    btn_tf.setStyleSheet(
                        "QPushButton { background-color: #0f172a; color: #ffffff; border: 1px solid #0f172a; "
                        "font-family: Consolas, monospace; font-size: 9px; font-weight: bold; border-radius: 2px; padding: 0px; margin: 0px; }"
                    )
            else:
                if is_dark:
                    btn_tf.setStyleSheet(
                        "QPushButton { background-color: transparent; color: #94a3b8; border: 1px solid transparent; "
                        "font-family: Consolas, monospace; font-size: 9px; font-weight: 600; border-radius: 2px; padding: 0px; margin: 0px; } "
                        "QPushButton:hover { color: #ffffff; background-color: #141721; border-color: #272d3b; }"
                    )
                else:
                    btn_tf.setStyleSheet(
                        "QPushButton { background-color: transparent; color: #64748b; border: 1px solid transparent; "
                        "font-family: Consolas, monospace; font-size: 9px; font-weight: 600; border-radius: 2px; padding: 0px; margin: 0px; } "
                        "QPushButton:hover { color: #0f172a; background-color: #e2e8f0; border-color: #cbd5e1; }"
                    )

    def _refresh_top_ticker(self):
        if hasattr(self, "lbl_top_sym"):
            raw_sym = getattr(self.window, "current_sym", "XAUUSD") if hasattr(self, "window") and getattr(self.window, "current_sym", None) else "XAUUSD"
            clean_sym = raw_sym.split("\n")[0].strip()
            is_dark = getattr(self, "is_dark_theme", False)
            sym_color = "#ffffff" if is_dark else "#0f172a"
            sub_color = "#94a3b8" if is_dark else "#64748b"
            subtitles = {
                "XAUUSD": "Spot Gold",
                "XAGUSD": "Spot Silver",
                "BTCUSD": "Bitcoin",
                "ETHUSD": "Ethereum",
                "EURUSD": "Euro / Dollar",
                "GBPUSD": "Cable / Dollar",
                "USDJPY": "Dollar / Yen",
                "US30": "Dow Jones",
                "NAS100": "Nasdaq Tech",
            }
            sub_title = subtitles.get(clean_sym, "Spot Asset")
            self.lbl_top_sym.setText(
                f'<b style="color:{sym_color}; font-family:Consolas, monospace; font-size:11.5px; font-weight:700;">{clean_sym}</b>&nbsp;&nbsp;'
                f'<span style="color:{sub_color}; font-size:9.5px; font-family:\'Segoe UI\', sans-serif; font-weight:500;">{sub_title}</span>'
            )
        is_running = False
        if hasattr(self.terminal, "bot_thread") and self.terminal.bot_thread and self.terminal.bot_thread.isRunning():
            is_running = True
        elif hasattr(self.terminal, "bot_worker") and self.terminal.bot_worker and getattr(self.terminal.bot_worker, "is_running", False):
            is_running = True
        elif hasattr(self.terminal, "btn_bot_power"):
            is_running = self.terminal.btn_bot_power.is_running()
        elif hasattr(self.terminal, "nav") and hasattr(self.terminal.nav, "btn_bot_power"):
            is_running = self.terminal.nav.btn_bot_power.is_running()

        if hasattr(self, "lbl_algo_status"):
            self.lbl_algo_status.setText("ALGO: ACTIVE" if is_running else "ALGO: STANDBY")
        if hasattr(self, "btn_algo_toggle") and self.btn_algo_toggle:
            if hasattr(self.btn_algo_toggle, "set_running"):
                self.btn_algo_toggle.set_running(is_running)
            else:
                self.btn_algo_toggle.setText("ALGO: ACTIVE" if is_running else "ALGO: STANDBY")
        acc = mt5.account_info() if mt5.terminal_info() else None
        if acc:
            pnl = acc.equity - acc.balance
            pnl_pct = (pnl / acc.balance * 100) if acc.balance > 0 else 0.0
            if hasattr(self, "lbl_top_ticker"):
                self.lbl_top_ticker.setText(
                    self._format_top_ticker(
                        bal=acc.balance,
                        eq=acc.equity,
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        is_algo_active=is_running,
                    )
                )
        else:
            if hasattr(self, "lbl_top_ticker"):
                self.lbl_top_ticker.setText(self._format_top_ticker(is_algo_active=is_running))

    def set_execution_mode(self, mode):
        """Set algorithm dispatch mode (configured in Settings tab) and update telemetry."""
        self.execution_mode = mode
        if hasattr(self.window, "lblAISubtitle") and self.window.lblAISubtitle:
            if mode == "MANUAL":
                self.window.lblAISubtitle.setText("Manual Execution Gate (Alerts Only)")
            elif mode == "FULL-AUTO":
                self.window.lblAISubtitle.setText("Autonomous STP Gate (Full-Auto)")
            else:
                self.window.lblAISubtitle.setText("Semi-Automated Execution Gate")
        self._update_title_and_bottom_bar_theme(getattr(self, "is_dark_theme", False))

    def _update_panel_toggle_styles(self, is_dark=None):
        if is_dark is None:
            is_dark = getattr(self, "is_dark_theme", False)
        if hasattr(self.window, "btn_edge_wl") and self.window.btn_edge_wl:
            if is_dark:
                self.window.btn_edge_wl.setStyleSheet(
                    "QPushButton#btnEdgeWatchlist { background-color: #0d121f; color: #94a3b8; border: 1px solid #1e293b; "
                    "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0 6px; min-height: 18px; max-height: 18px; } "
                    "QPushButton#btnEdgeWatchlist:hover { background-color: #1e293b; color: #ffffff; border-color: #475569; }"
                )
            else:
                self.window.btn_edge_wl.setStyleSheet(
                    "QPushButton#btnEdgeWatchlist { background-color: #ffffff; color: #475569; border: 1px solid #cbd5e1; "
                    "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0 6px; min-height: 18px; max-height: 18px; } "
                    "QPushButton#btnEdgeWatchlist:hover { background-color: #f1f5f9; color: #0f172a; border-color: #94a3b8; }"
                )
        if hasattr(self.window, "btn_edge_plan") and self.window.btn_edge_plan:
            if is_dark:
                self.window.btn_edge_plan.setStyleSheet(
                    "QPushButton#btnEdgeTradingPlan { background-color: #0d121f; color: #94a3b8; border: 1px solid #1e293b; "
                    "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0 6px; min-height: 18px; max-height: 18px; } "
                    "QPushButton#btnEdgeTradingPlan:hover { background-color: #1e293b; color: #ffffff; border-color: #475569; }"
                )
            else:
                self.window.btn_edge_plan.setStyleSheet(
                    "QPushButton#btnEdgeTradingPlan { background-color: #ffffff; color: #475569; border: 1px solid #cbd5e1; "
                    "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0 6px; min-height: 18px; max-height: 18px; } "
                    "QPushButton#btnEdgeTradingPlan:hover { background-color: #f1f5f9; color: #0f172a; border-color: #94a3b8; }"
                )

    def _update_mode_buttons(self, is_dark=None):
        if is_dark is None:
            is_dark = getattr(self, "is_dark_theme", False)
        m = getattr(self, "execution_mode", "SEMI-AUTO")
        if is_dark:
            act_style = (
                "QPushButton { background-color: #1e293b; color: #ffffff; border: 1px solid #475569; "
                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0 6px; }"
            )
            inact_style = (
                "QPushButton { background-color: transparent; color: #94a3b8; border: 1px solid transparent; "
                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: 600; border-radius: 2px; padding: 0 6px; } "
                "QPushButton:hover { color: #ffffff; background-color: #141721; border-color: #272d3b; }"
            )
        else:
            act_style = (
                "QPushButton { background-color: #ffffff; color: #0f172a; border: 1px solid #0f172a; "
                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0 6px; }"
            )
            inact_style = (
                "QPushButton { background-color: transparent; color: #64748b; border: 1px solid transparent; "
                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: 600; border-radius: 2px; padding: 0 6px; } "
                "QPushButton:hover { color: #0f172a; background-color: #e2e8f0; border-color: #cbd5e1; }"
            )
        if hasattr(self, "btn_mode_manual"):
            self.btn_mode_manual.setStyleSheet(act_style if m == "MANUAL" else inact_style)
        if hasattr(self, "btn_mode_semi"):
            self.btn_mode_semi.setStyleSheet(act_style if m == "SEMI-AUTO" else inact_style)
        if hasattr(self, "btn_mode_full"):
            self.btn_mode_full.setStyleSheet(act_style if m == "FULL-AUTO" else inact_style)

    def _update_title_and_bottom_bar_theme(self, is_dark):
        """Dynamic Light & Dark Theme synchronization for Top Title Bar and Bottom Toolbox Bar."""
        # 1. Top Header Container
        if hasattr(self, "header_container") and self.header_container:
            bg = "#0a0c10" if is_dark else "#f1f5f9"
            border = "#1e222d" if is_dark else "#cbd5e1"
            self.header_container.setStyleSheet(
                f"QFrame#topHeaderContainer {{ background-color: {bg}; border-bottom: 1px solid {border}; }}"
            )

        # 2. Bottom Tab Bar
        if hasattr(self, "bottom_bar") and self.bottom_bar:
            bg = "#0a0c10" if is_dark else "#f1f5f9"
            border = "#1e222d" if is_dark else "#cbd5e1"
            self.bottom_bar.setStyleSheet(
                f"QFrame#bottomTabBar {{ background-color: {bg}; border-top: 1px solid {border}; }}"
            )

        # 3. Top Symbol & Subtitle (Single baseline)
        self._refresh_top_ticker()

        # 4. Discrete Timeframe Buttons
        self._update_tf_button_styles(is_dark)

        # 5. IND Badge Button & Algo Control Pill (MT5 Flat resting state + Hover border)
        if hasattr(self, "btn_top_ind") and self.btn_top_ind:
            if is_dark:
                self.btn_top_ind.setStyleSheet(
                    "QPushButton { background-color: transparent; color: #94a3b8; border: 1px solid transparent; "
                    "font-family: Consolas, monospace; font-size: 9px; font-weight: bold; border-radius: 3px; padding: 0 8px; min-height: 24px; max-height: 24px; } "
                    "QPushButton:hover { background-color: #1e293b; color: #f8fafc; border: 1px solid #475569; } "
                    "QPushButton:pressed { background-color: #0f172a; border: 1px solid #334155; }"
                )
            else:
                self.btn_top_ind.setStyleSheet(
                    "QPushButton { background-color: transparent; color: #334155; border: 1px solid transparent; "
                    "font-family: Consolas, monospace; font-size: 9px; font-weight: bold; border-radius: 3px; padding: 0 8px; min-height: 24px; max-height: 24px; } "
                    "QPushButton:hover { background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; } "
                    "QPushButton:pressed { background-color: #e2e8f0; border: 1px solid #94a3b8; }"
                )

        if hasattr(self, "btn_algo_toggle") and self.btn_algo_toggle:
            if hasattr(self.btn_algo_toggle, "set_dark_theme"):
                self.btn_algo_toggle.set_dark_theme(is_dark)

        # 6. Central Telemetry (Account info only: BAL, EQ, PnL) - Flat institutional header
        if hasattr(self, "lbl_top_ticker") and self.lbl_top_ticker:
            self.lbl_top_ticker.setMinimumWidth(230)
            self.lbl_top_ticker.setStyleSheet(
                "background: transparent; border: none; padding: 0 4px; font-family: Consolas, monospace; font-size: 9.5px;"
            )
            is_running = self.btn_bot_power.is_running() if hasattr(self, "btn_bot_power") else False
            self.lbl_top_ticker.setText(self._format_top_ticker(is_algo_active=is_running, is_dark=is_dark))

        # 6b. Top Hairline Separators
        if hasattr(self, "top_separators") and self.top_separators:
            sep_col = "#272d3b" if is_dark else "#cbd5e1"
            for sep in self.top_separators:
                sep.setStyleSheet(f"background-color: {sep_col};")

        # 7. Mode Selector Buttons
        self._update_mode_buttons(is_dark)

        # 7b. Panel Toggle Buttons (Watchlist & Ticket)
        self._update_panel_toggle_styles(is_dark)

        # 8. EMERGENCY HALT Button
        if hasattr(self, "btn_emergency_top") and self.btn_emergency_top:
            if is_dark:
                self.btn_emergency_top.setStyleSheet(
                    "QPushButton#btnEmergencyTop { background-color: #2b0b0b; color: #fca5a5; border: 1px solid #7f1d1d; "
                    "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0 6px; } "
                    "QPushButton#btnEmergencyTop:hover { background-color: #450a0a; color: #ffffff; border-color: #991b1b; }"
                )
            else:
                self.btn_emergency_top.setStyleSheet(
                    "QPushButton#btnEmergencyTop { background-color: #ffffff; color: #dc2626; border: 1px solid #cbd5e1; "
                    "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0 6px; } "
                    "QPushButton#btnEmergencyTop:hover { background-color: #fef2f2; color: #991b1b; border-color: #94a3b8; }"
                )

        # 9. Window Controls
        hover_bg = "#1e222d" if is_dark else "#e2e8f0"
        btn_style = (
            f"QPushButton {{ background: transparent; border: none; border-radius: 0px; padding: 0; }} "
            f"QPushButton:hover {{ background-color: {hover_bg}; }}"
        )
        if hasattr(self, "btn_win_min") and self.btn_win_min:
            self.btn_win_min.setStyleSheet(btn_style)
        if hasattr(self, "btn_win_max") and self.btn_win_max:
            self.btn_win_max.setStyleSheet(btn_style)
        if hasattr(self, "btn_win_close") and self.btn_win_close:
            self.btn_win_close.setStyleSheet(
                "QPushButton#btnWinClose { background: transparent; border: none; border-radius: 0px; padding: 0; } "
                "QPushButton#btnWinClose:hover { background-color: #ef4444; }"
            )

        # 10. Bottom Session Indicator (Clean institutional wording)
        if hasattr(self, "lbl_bottom_mid") and self.lbl_bottom_mid:
            text_color = "#64748b" if is_dark else "#475569"
            mode = getattr(self, "execution_mode", "SEMI-ALGO")
            if mode == "SEMI-AUTO":
                mode = "SEMI-ALGO"
            elif mode == "FULL-AUTO":
                mode = "FULL-ALGO"
            elif mode == "MANUAL":
                mode = "MANUAL"
            self.lbl_bottom_mid.setText(
                f'<span style="color:{text_color}; font-family:Consolas, monospace; font-size:9px; padding-left: 8px;">'
                f'CME RTH SESSION &nbsp;·&nbsp; {mode}'
                '</span>'
            )

        if hasattr(self, "sep_bottom_nav") and self.sep_bottom_nav:
            self.sep_bottom_nav.setStyleSheet("background-color: #272d3b;" if is_dark else "background-color: #cbd5e1;")

        # 11. Bottom Telemetry & Status Strip (Concise, zero dev-internals)
        if hasattr(self, "lbl_bot_status") and self.lbl_bot_status:
            text_color = "#71717a" if is_dark else "#475569"
            green_color = "#10b981" if is_dark else "#15803d"
            sep_col = "#272d3b" if is_dark else "#cbd5e1"
            self.lbl_bot_status.setText(
                f'<span style="color:{text_color}; font-family:Consolas, monospace; font-size:9px;">'
                f'MT5: <b style="color:{green_color};">CONNECTED</b> &nbsp;&nbsp;'
                f'<span style="color:{sep_col};">|</span>&nbsp;&nbsp; '
                f'<b style="color:{green_color};">1.2ms</b> &nbsp;&nbsp;'
                f'<span style="color:{sep_col};">|</span>&nbsp;&nbsp; '
                f'<b style="color:{green_color};">0% LOSS</b>'
                '</span>'
            )



    def _setup_custom_title_bar(self):
        """Create institutional MT5-Style Workspace Layout matching blueprint:
        Top Bar (32px): Unified header with Symbol + Subtitle, Discrete TF buttons (M1-D1), IND badge,
                        Financial Telemetry Ribbon (BAL, EQ, PnL, DD, LATENCY, UTC), Mode selector (SEMI-AUTO active),
                        EMERGENCY HALT, and vector window controls (min, max, close).
        Bottom Bar (28px): MT5 Toolbox-style navigation tabs (TERMINAL, STATS, BACKTEST, SETTINGS, LOGS) + CME telemetry.
        """
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
        if not os.path.exists(assets_dir):
            assets_dir = os.path.join(os.path.dirname(__file__), "assets")

        header_container = QFrame()
        header_container.setObjectName("topHeaderContainer")
        header_container.setFixedHeight(32)
        header_container.setStyleSheet("QFrame#topHeaderContainer { background-color: #0a0c10; border-bottom: 1px solid #1e222d; }")
        self.header_container = header_container

        h_layout = QHBoxLayout(header_container)
        h_layout.setContentsMargins(10, 0, 10, 0)
        h_layout.setSpacing(8)
        h_layout.setAlignment(Qt.AlignVCenter)

        is_dark = getattr(self, "is_dark_theme", False)
        sep_col = "#272d3b" if is_dark else "#cbd5e1"

        # Chart Context Bar (Asset + Timeframe + Strategy): Strictly scoped to Tab 1 (Terminal)
        self.chart_context_bar = QWidget()
        self.chart_context_bar.setFixedHeight(24)
        ctx_layout = QHBoxLayout(self.chart_context_bar)
        ctx_layout.setContentsMargins(0, 0, 0, 0)
        ctx_layout.setSpacing(8)
        ctx_layout.setAlignment(Qt.AlignVCenter)

        # 1. Symbol Display: Active Asset
        self.lbl_top_sym = QLabel()
        self.lbl_top_sym.setObjectName("lblTopSymbol")
        self.lbl_top_sym.setFixedHeight(22)
        ctx_layout.addWidget(self.lbl_top_sym)
        self._refresh_top_ticker()

        # Separator 1: Between Symbol and Timeframes
        sep1 = QFrame()
        sep1.setFixedWidth(1)
        sep1.setFixedHeight(14)
        sep1.setStyleSheet(f"background-color: {sep_col};")
        ctx_layout.addWidget(sep1)

        # 2. Timeframe Discrete Buttons Strip (M1, M5, M15, H1, H4, D1 with 3px gap)
        tf_bar = QWidget()
        tf_bar.setFixedHeight(22)
        tf_layout = QHBoxLayout(tf_bar)
        tf_layout.setContentsMargins(0, 0, 0, 0)
        tf_layout.setSpacing(3)

        self.tf_buttons = {}
        tf_map = {
            "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
            "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4, "D1": mt5.TIMEFRAME_D1
        }

        self.active_timeframe = "H1"
        def _on_tf_click(tf_k):
            self.active_timeframe = tf_k
            self._update_tf_button_styles()
            if hasattr(self.window, "change_timeframe"):
                self.window.change_timeframe(tf_map.get(tf_k, mt5.TIMEFRAME_H1), tf_k)

        for tf_name in ["M1", "M5", "M15", "H1", "H4", "D1"]:
            btn_tf = QPushButton(tf_name)
            btn_tf.setObjectName(f"btnTopTf_{tf_name}")
            btn_tf.setFixedSize(26, 20)
            btn_tf.setCursor(Qt.PointingHandCursor)
            btn_tf.clicked.connect(lambda chk=False, k=tf_name: _on_tf_click(k))
            tf_layout.addWidget(btn_tf)
            self.tf_buttons[tf_name] = btn_tf

        self._update_tf_button_styles(is_dark)
        self.window.update_tf_styles = self._update_tf_button_styles
        ctx_layout.addWidget(tf_bar)

        # Separator 2: Between Timeframes and Indicator
        sep2 = QFrame()
        sep2.setFixedWidth(1)
        sep2.setFixedHeight(14)
        sep2.setStyleSheet(f"background-color: {sep_col};")
        ctx_layout.addWidget(sep2)

        # 3. Indicator Badge (ICT / SMC · Confluence Pro v4.2)
        btn_ind = QPushButton()
        btn_ind.setObjectName("btnTopIndicator")
        btn_ind.setFixedHeight(20)
        btn_ind.setCursor(Qt.PointingHandCursor)
        btn_ind.setToolTip("Configure Algorithmic Indicator Stack")
        btn_ind.setText("ICT / SMC · Confluence Pro v4.2")
        ind_bg = "transparent"
        ind_col = "#94a3b8" if is_dark else "#334155"
        hover_bg = "#1e293b" if is_dark else "#ffffff"
        hover_col = "#f8fafc" if is_dark else "#0f172a"
        hover_border = "#475569" if is_dark else "#cbd5e1"
        btn_ind.setFixedHeight(24)
        btn_ind.setStyleSheet(
            f"QPushButton#btnTopIndicator {{ background-color: {ind_bg}; color: {ind_col}; border: 1px solid transparent; "
            f"border-radius: 3px; padding: 0 8px; font-family: Consolas, monospace; font-size: 9px; font-weight: bold; "
            f"min-height: 24px; max-height: 24px; }} "
            f"QPushButton#btnTopIndicator:hover {{ color: {hover_col}; border: 1px solid {hover_border}; background-color: {hover_bg}; }} "
            f"QPushButton#btnTopIndicator:pressed {{ background-color: {'#0f172a' if is_dark else '#e2e8f0'}; }}"
        )
        if hasattr(self.window, "open_indicators"):
            btn_ind.clicked.connect(self.window.open_indicators)
        ctx_layout.addWidget(btn_ind)

        # Separator 3: Between Indicator Badge and ALGO Control Pill
        sep_algo = QFrame()
        sep_algo.setFixedWidth(1)
        sep_algo.setFixedHeight(14)
        sep_algo.setStyleSheet(f"background-color: {sep_col};")
        ctx_layout.addWidget(sep_algo)

        # 4. Institutional Flat ALGO State & Control Pill (24px)
        btn_algo = AlgoControlPill(is_running=False, is_dark=is_dark)
        btn_algo.setObjectName("btnAlgoTrading")
        btn_algo.clicked.connect(lambda: self.terminal._toggle_bot())
        self.btn_algo_toggle = btn_algo
        self.window.btn_algo_toggle = btn_algo
        ctx_layout.addWidget(btn_algo)

        h_layout.addWidget(self.chart_context_bar)

        # Dedicated Non-Terminal Workspace Branding (Shown on Stats, Backtest, Logs)
        self.lbl_header_app_title = QLabel("QUANT AI TERMINAL v2.2")
        self.lbl_header_app_title.setObjectName("lblHeaderAppTitle")
        self.lbl_header_app_title.setStyleSheet(
            f"color: {'#94a3b8' if is_dark else '#475569'}; font-family: 'Consolas', monospace; font-size: 10px; font-weight: 700; letter-spacing: 0.5px;"
        )
        self.lbl_header_app_title.setVisible(False)
        h_layout.addWidget(self.lbl_header_app_title)

        # Maintain legacy objects for compatibility
        self.combo_top_tf = QComboBox()
        self.combo_top_tf.setVisible(False)
        self.window.combo_top_tf = self.combo_top_tf
        self.btn_top_ind = btn_ind

        # Maintain legacy stubs for compatibility (Panels fold via Edge Tabs on chart ribbon)
        self.btn_top_wl = None
        self.window.btn_top_wl = None
        self.btn_top_ticket = None
        self.window.btn_top_ticket = None
        self.window._update_panel_toggle_styles = self._update_panel_toggle_styles

        # 4. SINGLE UNIFIED CENTER DRAGGING STRETCH
        # Creates clean, balanced symmetry between left chart controls and right account telemetry
        h_layout.addStretch(1)

        # Global HotKey F5 to toggle Algo Bot
        self.shortcut_f5 = QShortcut(QKeySequence("F5"), self.window)
        self.shortcut_f5.activated.connect(lambda: self.terminal._toggle_bot())

        # 5. Right-docked Account Telemetry (BAL | EQ | PnL - Account Capital Only)
        self.lbl_top_ticker = QLabel()
        self.lbl_top_ticker.setObjectName("lblTopTicker")
        self.lbl_top_ticker.setTextFormat(Qt.RichText)
        self.lbl_top_ticker.setFixedHeight(22)
        self.lbl_top_ticker.setMinimumWidth(230)
        self.lbl_top_ticker.setAlignment(Qt.AlignCenter)
        self.lbl_top_ticker.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.lbl_top_ticker.setStyleSheet(
            "background: transparent; border: none; padding: 0 4px; font-family: Consolas, monospace; font-size: 9.5px;"
        )
        self.lbl_top_ticker.setText(self._format_top_ticker(is_dark=is_dark))
        h_layout.addWidget(self.lbl_top_ticker)

        self.top_separators = [sep1, sep2, sep_algo]

        # 6. Execution Mode State (Configured centrally in Tab 4 Settings)
        self.execution_mode = "SEMI-AUTO"

        # 7. Top Bar Action / Emergency state (Flatten moved to Blotter toolbar per institutional spec)
        self.btn_emergency_top = None

        self.lbl_algo_status = QLabel()
        self.lbl_algo_status.setVisible(False)

        # 8. Windows System Control Bar (Standard Integrated Windows Titlebar Controls)
        win_controls = QWidget()
        win_controls.setFixedHeight(32)
        win_layout = QHBoxLayout(win_controls)
        win_layout.setContentsMargins(0, 0, 0, 0)
        win_layout.setSpacing(0)

        hover_bg = "#1e222d" if is_dark else "#e2e8f0"
        btn_style = (
            f"QPushButton {{ background: transparent; border: none; border-radius: 0px; padding: 0; }} "
            f"QPushButton:hover {{ background-color: {hover_bg}; }}"
        )

        btn_min = QPushButton()
        btn_min.setObjectName("btnWinMinimize")
        btn_min.setFixedSize(36, 32)
        btn_min.setCursor(Qt.ArrowCursor)
        min_svg = os.path.join(assets_dir, "win_min.svg")
        if os.path.exists(min_svg):
            btn_min.setIcon(QIcon(min_svg))
            btn_min.setIconSize(QSize(10, 10))
        btn_min.setStyleSheet(btn_style)
        btn_min.clicked.connect(lambda: self.window.showMinimized())
        self.btn_win_min = btn_min
        win_layout.addWidget(btn_min)

        self._is_maximized = False
        btn_max = QPushButton()
        btn_max.setObjectName("btnWinMaximize")
        btn_max.setFixedSize(36, 32)
        btn_max.setCursor(Qt.ArrowCursor)
        max_svg = os.path.join(assets_dir, "win_max.svg")
        if os.path.exists(max_svg):
            btn_max.setIcon(QIcon(max_svg))
            btn_max.setIconSize(QSize(10, 10))
        btn_max.setStyleSheet(btn_style)

        def toggle_maximize():
            if self._is_maximized:
                self.window.showNormal()
                self._is_maximized = False
            else:
                self.window.showMaximized()
                self._is_maximized = True
        btn_max.clicked.connect(toggle_maximize)
        self.btn_win_max = btn_max
        win_layout.addWidget(btn_max)

        btn_close = QPushButton()
        btn_close.setObjectName("btnWinClose")
        btn_close.setFixedSize(40, 32)
        btn_close.setCursor(Qt.ArrowCursor)
        close_svg = os.path.join(assets_dir, "win_close.svg")
        if os.path.exists(close_svg):
            btn_close.setIcon(QIcon(close_svg))
            btn_close.setIconSize(QSize(10, 10))
        btn_close.setStyleSheet(
            "QPushButton#btnWinClose { background: transparent; border: none; border-radius: 0px; padding: 0; } "
            "QPushButton#btnWinClose:hover { background-color: #ef4444; }"
        )
        btn_close.clicked.connect(lambda: self.window.close())
        self.btn_win_close = btn_close
        win_layout.addWidget(btn_close)

        h_layout.addWidget(win_controls)

        # Window drag handlers
        def mouse_press(event):
            if event.button() == Qt.LeftButton:
                self._drag_pos = event.globalPosition().toPoint() - self.window.frameGeometry().topLeft()
                event.accept()

        def mouse_move(event):
            if event.buttons() == Qt.LeftButton and hasattr(self, "_drag_pos") and self._drag_pos is not None:
                self.window.move(event.globalPosition().toPoint() - self._drag_pos)
                event.accept()

        def mouse_release(event):
            self._drag_pos = None

        header_container.mousePressEvent = mouse_press
        header_container.mouseMoveEvent = mouse_move
        header_container.mouseReleaseEvent = mouse_release

        # BOTTOM BAR (28px): MT5 Toolbox Navigation Tabs + CME Telemetry
        bottom_bar = QFrame()
        bottom_bar.setObjectName("bottomTabBar")
        bottom_bar.setFixedHeight(28)
        bottom_bar.setStyleSheet("QFrame#bottomTabBar { background-color: #0a0c10; border-top: 1px solid #1e222d; }")
        self.bottom_bar = bottom_bar

        b_layout = QHBoxLayout(bottom_bar)
        b_layout.setContentsMargins(8, 0, 8, 0)
        b_layout.setSpacing(4)

        # 4 Core Workspaces (MT5 Toolbox Bottom Navigation)
        self.nav_buttons = []
        tabs_spec = [
            ("btnNavTerminal", "LIVE TERMINAL", self.window.tab2, "LIVE TRADING TERMINAL"),
            ("btnNavStats", "PERFORMANCE", self.window.tab3, "PERFORMANCE ANALYTICS"),
            ("btnNavBacktest", "BACKTEST", self.window.tab_5, "STRATEGY BACKTESTING WORKBENCH"),
            ("btnNavLogs", "SYSTEM LOGS", self.window.tab4, "SYSTEM AUDIT & EXECUTION LOGS"),
        ]

        for obj_name, label_text, target_tab, full_title in tabs_spec:
            btn = QPushButton(label_text)
            btn.setObjectName(obj_name)
            btn.setFixedHeight(22)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setCheckable(True)
            btn.setStyleSheet(
                "QPushButton { background-color: transparent; color: #94a3b8; border: 1px solid transparent; "
                "font-family: Consolas, monospace; font-size: 9px; font-weight: 600; padding: 0 12px; } "
                "QPushButton:hover { color: #ffffff; background-color: #141721; }"
            )
            def _make_nav_handler(target_tab, btn_obj, tab_title):
                def _handler(checked=False):
                    self._switch_nav_tab(target_tab, btn_obj, tab_title)
                return _handler

            btn.clicked.connect(_make_nav_handler(target_tab, btn, full_title))
            b_layout.addWidget(btn)
            self.nav_buttons.append((btn, target_tab, full_title))
            setattr(self, obj_name, btn)

        if hasattr(self.terminal, "nav"):
            self.terminal.nav.nav_buttons = self.nav_buttons

        # Settings / Options Modal Overlay Trigger (MT5 Ctrl+O Architecture)
        btn_settings = QPushButton("OPTIONS")
        btn_settings.setObjectName("btnNavSettings")
        btn_settings.setFixedHeight(22)
        btn_settings.setCursor(Qt.PointingHandCursor)
        btn_settings.setToolTip("System Options & Risk Settings (Ctrl+O)")
        btn_settings.setStyleSheet(
            "QPushButton { background-color: transparent; color: #94a3b8; border: 1px solid transparent; "
            "font-family: Consolas, monospace; font-size: 9px; font-weight: 600; padding: 0 12px; } "
            "QPushButton:hover { color: #ffffff; background-color: #141721; }"
        )
        def _open_options(checked=False):
            if hasattr(self, "settings") and hasattr(self.settings, "open_options_dialog"):
                self.settings.open_options_dialog()
        btn_settings.clicked.connect(_open_options)
        b_layout.addWidget(btn_settings)
        setattr(self, "btnNavSettings", btn_settings)

        # Hairline separator between nav tabs and session indicator
        sep_bottom_nav = QFrame()
        sep_bottom_nav.setFrameShape(QFrame.VLine)
        sep_bottom_nav.setFixedWidth(1)
        sep_bottom_nav.setFixedHeight(14)
        sep_bottom_nav.setStyleSheet("background-color: #272d3b;" if is_dark else "background-color: #cbd5e1;")
        self.sep_bottom_nav = sep_bottom_nav
        b_layout.addWidget(sep_bottom_nav)

        # Middle session indicator (Clean institutional wording)
        lbl_bottom_mid = QLabel(
            '<span style="color:#64748b; font-family:Consolas, monospace; font-size:9px; padding-left: 8px;">'
            'SESSION CME RTH &nbsp;·&nbsp; SEMI-ALGO'
            '</span>'
        )
        self.lbl_bottom_mid = lbl_bottom_mid
        b_layout.addWidget(lbl_bottom_mid)
        b_layout.addStretch()

        # Telemetry & Status strip on bottom right (Concise, zero dev-internals)
        lbl_bot_status = QLabel(
            '<span style="color:#71717a; font-family:Consolas, monospace; font-size:9px;">'
            'MT5: <b style="color:#15803d;">CONNECTED</b> &nbsp;&nbsp;'
            '<span style="color:#cbd5e1;">|</span>&nbsp;&nbsp; '
            '<b style="color:#15803d;">1.2ms</b> &nbsp;&nbsp;'
            '<span style="color:#cbd5e1;">|</span>&nbsp;&nbsp; '
            '<b style="color:#15803d;">0% LOSS</b>'
            '</span>'
        )
        lbl_bot_status.setFixedHeight(24)
        lbl_bot_status.setAlignment(Qt.AlignVCenter)
        self.lbl_bot_status = lbl_bot_status
        b_layout.addWidget(lbl_bot_status)

        # Mount top and bottom bars spanning 100% full width across window
        header_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        bottom_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if hasattr(self.window, "mainSplitter"):
            self.window.mainSplitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.window.mainSplitter.setChildrenCollapsible(True)
        if hasattr(self.window, "tabWidget"):
            self.window.tabWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        master = QWidget()
        master.setObjectName("centralwidget")
        master.setMinimumWidth(0)
        master_layout = QVBoxLayout(master)
        master_layout.setContentsMargins(0, 0, 0, 0)
        master_layout.setSpacing(0)
        master_layout.addWidget(header_container, 0)
        master_layout.addWidget(self.window.mainSplitter, 1)
        master_layout.addWidget(bottom_bar, 0)
        self.window.setCentralWidget(master)
        if hasattr(self.window, "mainSplitter"):
            self.window.mainSplitter.setSizes([285, 1155])

# Backward compatibility alias
HeaderController = WorkspaceHeaderController
