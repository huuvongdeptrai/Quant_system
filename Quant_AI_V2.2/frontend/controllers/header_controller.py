"""
Workspace Header Controller for Quant_AI V2.2
"""

import os
import sys
from datetime import datetime, timedelta
from loguru import logger
from PySide6.QtWidgets import (
    QMenuBar, QMenu,
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QFrame, QTableWidgetItem, QCheckBox, QGraphicsDropShadowEffect,
    QSizePolicy, QComboBox, QMessageBox, QHeaderView, QMenu
)
from PySide6.QtGui import QFont, QIcon, QColor, QCursor, QKeySequence, QShortcut, QMouseEvent, QAction
from PySide6.QtCore import Qt, QTimer, QFile, QIODevice, QObject, QThread, QSize, QPoint
from backend.infrastructure.brokers.mt5_safe import mt5
from frontend.widgets.bot_power_button import AlgoControlPill


class WorkspaceHeaderController:

    @staticmethod
    def _create_v_separator(is_dark=False):
        """Unified institutional 1px x 14px vertical separator."""
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Plain)
        sep.setFixedWidth(1)
        sep.setFixedHeight(14)
        col = "#272d3b" if is_dark else "#cbd5e1"
        sep.setStyleSheet(f"background-color: {col}; border: none; margin: 0px;")
        return sep

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

    def _format_top_ticker(self, bal=None, eq=None, pnl=None, pnl_pct=0.0, max_dd=0.0, latency=None, is_algo_active=False, is_dark=None, acct=None):
        if is_dark is None:
            is_dark = getattr(self, "is_dark_theme", False)

        lbl_col = "#71717a" if is_dark else "#64748b"
        val_col = "#ffffff" if is_dark else "#0f172a"
        sep_col = "#262626" if is_dark else "#cbd5e1"

        if bal is None or eq is None:
            bal_txt = "--"
            eq_txt = "--"
            pnl_txt = "--"
            pnl_color = lbl_col
        else:
            bal_txt = f"${bal:,.2f}"
            eq_txt = f"${eq:,.2f}"
            if pnl is not None and pnl < 0:
                pnl_txt = f"-${abs(pnl):,.2f}"
                pnl_color = "#ef4444" if is_dark else "#b91c1c"
            elif pnl is not None:
                pnl_txt = f"+${pnl:,.2f}"
                pnl_color = "#10b981" if is_dark else "#15803d"
            else:
                pnl_txt = "--"
                pnl_color = lbl_col

        acct_prefix = ""
        if acct:
            if str(acct).upper() == "OFFLINE":
                acct_val_col = "#ef4444" if is_dark else "#dc2626"
                acct_prefix = (
                    f'<b style="color:{acct_val_col}; font-family:Consolas, monospace; font-size:10px; font-weight:700;">[OFFLINE]</b>&nbsp;&nbsp;'
                    f'<span style="color:{sep_col}; font-family:Consolas, monospace; font-weight:300;">|</span>&nbsp;&nbsp;'
                )
            else:
                acct_str = f"#{acct}" if not str(acct).startswith("#") else str(acct)
                acct_val_col = "#38bdf8" if is_dark else "#0284c7"
                acct_prefix = (
                    f'<span style="color:{lbl_col}; font-size:10px; font-family:Consolas, monospace; font-weight:600;">ACCT:</span> '
                    f'<b style="color:{acct_val_col}; font-family:Consolas, monospace; font-size:10px; font-weight:700;">{acct_str}</b>&nbsp;&nbsp;'
                    f'<span style="color:{sep_col}; font-family:Consolas, monospace; font-weight:300;">|</span>&nbsp;&nbsp;'
                )

        return (
            f'<span style="color:{lbl_col}; font-size:10px; font-family:Consolas, monospace; font-weight:600;">'
            f'{acct_prefix}'
            f'BAL: <b style="color:{val_col}; font-family:Consolas, monospace; font-size:10px; font-weight:700;">{bal_txt}</b>&nbsp;&nbsp;'
            f'<span style="color:{sep_col}; font-family:Consolas, monospace; font-weight:300;">|</span>&nbsp;&nbsp;'
            f'EQ: <b style="color:{val_col}; font-family:Consolas, monospace; font-size:10px; font-weight:700;">{eq_txt}</b>&nbsp;&nbsp;'
            f'<span style="color:{sep_col}; font-family:Consolas, monospace; font-weight:300;">|</span>&nbsp;&nbsp;'
            f'P&L: <b style="color:{pnl_color}; font-family:Consolas, monospace; font-size:10px; font-weight:700;">{pnl_txt}</b>'
            f'</span>'
        )

    def _format_bottom_telemetry(self, is_dark=None):
        """Consolidated institutional bottom telemetry cluster:
        FULL-ALGO | ● MT5: 234.0ms | 0% LOSS
        Reflects genuine live MT5 broker ping latency and real-time loss tracking.
        """
        if is_dark is None:
            is_dark = getattr(self, "is_dark_theme", False)

        mode = getattr(self, "execution_mode", "FULL-ALGO")
        if mode in ("FULL-AUTO", "FULL-ALGO"):
            mode_str = "FULL-ALGO"
        elif mode in ("SEMI-AUTO", "SEMI-ALGO"):
            mode_str = "SEMI-ALGO"
        elif mode == "MANUAL":
            mode_str = "MANUAL"
        else:
            mode_str = mode

        # Measure genuine MT5 broker server ping & connection state
        is_connected = False
        latency_ms = 0.0
        try:
            import time
            t0 = time.perf_counter()
            t_info = mt5.terminal_info()
            ipc_elapsed = (time.perf_counter() - t0) * 1000.0
            if t_info and getattr(t_info, "connected", False):
                is_connected = True
                if hasattr(t_info, "ping_last") and t_info.ping_last > 0:
                    latency_ms = t_info.ping_last / 1000.0
                else:
                    latency_ms = max(0.1, ipc_elapsed)
                self.broker_latency_ms = latency_ms
                self.is_broker_connected = True
            elif t_info:
                self.is_broker_connected = False
            else:
                self.is_broker_connected = False
        except Exception:
            self.is_broker_connected = False

        if not is_connected and hasattr(self, "broker_latency_ms"):
            val = getattr(self, "broker_latency_ms", 0.0)
            if isinstance(val, (int, float)):
                latency_ms = val

        latency_str = f"{latency_ms:.1f}ms" if (isinstance(latency_ms, (int, float)) and latency_ms > 0) else "--"

        # Check daily loss or drawdown
        loss_pct = 0.0
        try:
            acc = mt5.account_info() if mt5.terminal_info() else None
            if acc and acc.balance > 0:
                pnl = acc.equity - acc.balance
                if pnl < 0:
                    loss_pct = abs(pnl) / acc.balance * 100.0
        except Exception:
            val = getattr(self, "current_daily_loss_pct", 0.0)
            loss_pct = val if isinstance(val, (int, float)) else 0.0

        loss_str = f"{loss_pct:.0f}% LOSS" if loss_pct == int(loss_pct) else f"{loss_pct:.1f}% LOSS"

        if is_dark:
            txt_col = "#94a3b8"
            mode_col = "#38bdf8"
            sep_col = "#334155"
            green_col = "#10b981"
            amber_col = "#f59e0b"
            red_col = "#ef4444"
        else:
            txt_col = "#64748b"
            mode_col = "#0284c7"
            sep_col = "#cbd5e1"
            green_col = "#15803d"
            amber_col = "#d97706"
            red_col = "#dc2626"

        dot_col = green_col if is_connected else red_col
        mt5_val = latency_str if is_connected else "OFFLINE"
        if is_connected:
            mt5_val_col = green_col if latency_ms < 300.0 else (amber_col if latency_ms < 500.0 else red_col)
        else:
            mt5_val_col = red_col

        loss_col = green_col if loss_pct <= 0.0 else red_col
        sep = f'&nbsp;&nbsp;<span style="color:{sep_col}; font-weight:300;">|</span>&nbsp;&nbsp;'

        return (
            f'<span style="font-family:\'Segoe UI\', -apple-system, sans-serif; font-size:11px;">'
            f'<span style="color:{dot_col};">●</span> <span style="color:{txt_col}; font-weight:500;">MT5:</span> <b style="color:{mt5_val_col}; font-weight:600;">{mt5_val}</b>'
            f'{sep}'
            f'<b style="color:{loss_col}; font-weight:600;">{loss_str}</b>'
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
                        "font-family: Consolas, monospace; font-size: 10px; font-weight: bold; border-radius: 2px; padding: 0px; margin: 0px; }"
                    )
                else:
                    btn_tf.setStyleSheet(
                        "QPushButton { background-color: #0f172a; color: #ffffff; border: 1px solid #0f172a; "
                        "font-family: Consolas, monospace; font-size: 10px; font-weight: bold; border-radius: 2px; padding: 0px; margin: 0px; }"
                    )
            else:
                if is_dark:
                    btn_tf.setStyleSheet(
                        "QPushButton { background-color: transparent; color: #94a3b8; border: 1px solid transparent; "
                        "font-family: Consolas, monospace; font-size: 10px; font-weight: 600; border-radius: 2px; padding: 0px; margin: 0px; } "
                        "QPushButton:hover { color: #ffffff; background-color: #141721; border-color: #272d3b; }"
                    )
                else:
                    btn_tf.setStyleSheet(
                        "QPushButton { background-color: transparent; color: #64748b; border: 1px solid transparent; "
                        "font-family: Consolas, monospace; font-size: 10px; font-weight: 600; border-radius: 2px; padding: 0px; margin: 0px; } "
                        "QPushButton:hover { color: #0f172a; background-color: #e2e8f0; border-color: #cbd5e1; }"
                    )

    def _update_top_symbol_style(self, is_dark=None):
        """Institutional styling for top ribbon active symbol button."""
        if is_dark is None:
            is_dark = getattr(self, "is_dark_theme", False)
        if not hasattr(self, "lbl_top_sym") or not self.lbl_top_sym:
            return
        if is_dark:
            self.lbl_top_sym.setStyleSheet(
                "QPushButton#lblTopSymbol { "
                "  background-color: transparent; "
                "  color: #f8fafc; "
                "  border: 1px solid transparent; "
                "  border-radius: 2px; "
                "  padding: 0 4px; "
                "  font-family: Consolas, monospace; "
                "  font-size: 11px; "
                "  font-weight: 700; "
                "  text-align: center; "
                "  min-height: 20px; "
                "  max-height: 20px; "
                "} "
                "QPushButton#lblTopSymbol:hover { "
                "  background-color: #141721; "
                "  border: 1px solid #272d3b; "
                "  color: #38bdf8; "
                "} "
                "QPushButton#lblTopSymbol:pressed { "
                "  background-color: #0c1a2e; "
                "  border: 1px solid #0284c7; "
                "}"
            )
        else:
            self.lbl_top_sym.setStyleSheet(
                "QPushButton#lblTopSymbol { "
                "  background-color: transparent; "
                "  color: #0f172a; "
                "  border: 1px solid transparent; "
                "  border-radius: 2px; "
                "  padding: 0 4px; "
                "  font-family: Consolas, monospace; "
                "  font-size: 11px; "
                "  font-weight: 700; "
                "  text-align: center; "
                "  min-height: 20px; "
                "  max-height: 20px; "
                "} "
                "QPushButton#lblTopSymbol:hover { "
                "  background-color: #e2e8f0; "
                "  border: 1px solid #cbd5e1; "
                "  color: #0284c7; "
                "} "
                "QPushButton#lblTopSymbol:pressed { "
                "  background-color: #cbd5e1; "
                "  border: 1px solid #94a3b8; "
                "}"
            )

    def _get_watchlist_symbols(self):
        """Returns list of distinct asset symbols currently configured in Watchlist."""
        symbols = []
        wl = getattr(self.terminal, "watchlist", None) or getattr(self, "watchlist", None)
        if wl and hasattr(wl, "get_all_symbols"):
            try:
                symbols = wl.get_all_symbols()
            except Exception:
                symbols = []
        if not symbols and hasattr(self.window, "treeWatchlist") and self.window.treeWatchlist:
            try:
                tree = self.window.treeWatchlist
                for i in range(tree.topLevelItemCount()):
                    cat = tree.topLevelItem(i)
                    for j in range(cat.childCount()):
                        raw = cat.child(j).text(0)
                        clean = raw.split("\n")[0].strip()
                        if clean and clean not in symbols:
                            symbols.append(clean)
            except Exception:
                pass
        if not symbols:
            symbols = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "BTCUSD", "US500"]
        return symbols

    def _switch_symbol(self, sym):
        """Switches active workspace asset, synchronizing Watchlist tree and Chart viewport."""
        clean_sym = sym.split("\n")[0].strip()
        if hasattr(self, "window"):
            self.window.current_sym = clean_sym
        self._refresh_top_ticker()

        if hasattr(self.window, "treeWatchlist") and self.window.treeWatchlist:
            tree = self.window.treeWatchlist
            for i in range(tree.topLevelItemCount()):
                cat = tree.topLevelItem(i)
                for j in range(cat.childCount()):
                    item = cat.child(j)
                    if item.text(0).split("\n")[0].strip() == clean_sym:
                        tree.setCurrentItem(item)
                        break

        if hasattr(self.window, "draw_and_analyze"):
            self.window.draw_and_analyze(clean_sym)

    def _show_symbol_quick_picker(self):
        """Displays an institutional flat popup menu listing all assets currently in the Watchlist."""
        if not hasattr(self, "lbl_top_sym") or not self.lbl_top_sym:
            return

        is_dark = getattr(self, "is_dark_theme", False)
        menu = QMenu(self.lbl_top_sym)
        menu.setObjectName("menuTopSymbolPicker")

        bg_col = "#070a12" if is_dark else "#ffffff"
        text_col = "#f8fafc" if is_dark else "#0f172a"
        border_col = "#1e293b" if is_dark else "#cbd5e1"
        hover_bg = "#161d31" if is_dark else "#f1f5f9"
        active_col = "#38bdf8" if is_dark else "#0284c7"
        sep_col = "#1e293b" if is_dark else "#e2e8f0"

        menu.setStyleSheet(
            f"QMenu#menuTopSymbolPicker {{ "
            f"  background-color: {bg_col}; "
            f"  border: 1px solid {border_col}; "
            f"  border-radius: 3px; "
            f"  padding: 4px; "
            f"}} "
            f"QMenu#menuTopSymbolPicker::item {{ "
            f"  color: {text_col}; "
            f"  font-family: Consolas, monospace; "
            f"  font-size: 10px; "
            f"  font-weight: 600; "
            f"  padding: 5px 16px 5px 10px; "
            f"  border-radius: 2px; "
            f"}} "
            f"QMenu#menuTopSymbolPicker::item:selected {{ "
            f"  background-color: {hover_bg}; "
            f"  color: {active_col}; "
            f"}} "
            f"QMenu#menuTopSymbolPicker::separator {{ "
            f"  height: 1px; "
            f"  background-color: {sep_col}; "
            f"  margin: 3px 6px; "
            f"}}"
        )

        symbols = self._get_watchlist_symbols()
        curr_sym = getattr(self.window, "current_sym", "XAUUSD").split("\n")[0].strip()

        for sym in symbols:
            is_active = (sym == curr_sym)
            label = f"✓  {sym}" if is_active else f"    {sym}"
            action = menu.addAction(label)
            if is_active:
                f = action.font()
                f.setBold(True)
                action.setFont(f)
            action.triggered.connect(lambda chk=False, s=sym: self._switch_symbol(s))

        menu.addSeparator()
        act_manage = menu.addAction("  ⚙ Manage Watchlist...")
        def _open_watchlist():
            if hasattr(self.window, "sidebar"):
                self.window.sidebar.setVisible(True)
                self.window.watchlist_collapsed = False
                if hasattr(self.window, "mainSplitter"):
                    total_w = max(400, self.window.mainSplitter.width() or 1440)
                    sidebar_w = 260
                    self.window.mainSplitter.setSizes([sidebar_w, max(100, total_w - sidebar_w)])
            if hasattr(self.terminal, "watchlist") and hasattr(self.terminal.watchlist, "open_search_modal"):
                self.terminal.watchlist.open_search_modal()
        act_manage.triggered.connect(_open_watchlist)

        pos = self.lbl_top_sym.mapToGlobal(QPoint(0, self.lbl_top_sym.height() + 2))
        menu.exec(pos)

    def _refresh_top_ticker(self):
        if hasattr(self, "lbl_top_sym"):
            raw_sym = getattr(self.window, "current_sym", "XAUUSD") if hasattr(self, "window") and getattr(self.window, "current_sym", None) else "XAUUSD"
            clean_sym = raw_sym.split("\n")[0].strip()
            is_dark = getattr(self, "is_dark_theme", False)
            sub_title = None
            try:
                s_info = mt5.symbol_info(clean_sym)
                if s_info and getattr(s_info, "description", None):
                    sub_title = s_info.description.strip()
            except Exception:
                pass

            self.lbl_top_sym.setText(clean_sym)
            self._update_top_symbol_style(is_dark)
            tooltip_txt = f"Active Asset: {clean_sym}"
            if sub_title:
                tooltip_txt += f" ({sub_title})"
            tooltip_txt += "\nClick to switch asset from Watchlist\nScroll mouse wheel to quickly cycle"
            self.lbl_top_sym.setToolTip(tooltip_txt)

            if hasattr(self, "_update_event_risk_badge"):
                self._update_event_risk_badge(clean_sym)
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
                        acct=str(acc.login),
                    )
                )
        else:
            if hasattr(self, "lbl_top_ticker"):
                self.lbl_top_ticker.setText(self._format_top_ticker(is_algo_active=is_running, acct="OFFLINE"))

        if hasattr(self, "lbl_bot_status") and self.lbl_bot_status:
            self.lbl_bot_status.setText(self._format_bottom_telemetry(getattr(self, "is_dark_theme", False)))

    def update_strategy_badge(self, strat_id_or_name=None):
        """
        Dynamically updates btnTopIndicator text and tooltip to match active quantitative strategy.
        Complies with polymorphic BaseStrategy contract (ICT, Wyckoff, EMA, or Custom).
        """
        if not hasattr(self, "btn_top_ind") or not self.btn_top_ind:
            return

        strat_id = strat_id_or_name
        if not strat_id:
            strat_id = getattr(self.window, "active_strategy_id", None)
        if not strat_id and hasattr(self.window, "comboStrategy") and self.window.comboStrategy:
            try:
                import shiboken6
                if shiboken6.isValid(self.window.comboStrategy):
                    strat_id = self.window.comboStrategy.currentData()
            except Exception:
                pass
        if not strat_id:
            try:
                import json
                with open("config/settings.json", "r", encoding="utf-8") as f_cfg:
                    cfg_d = json.load(f_cfg)
                    strat_id = cfg_d.get("strategy", "builtin_ict_pro")
            except Exception:
                strat_id = "builtin_ict_pro"

        strat_id_str = str(strat_id or "builtin_ict_pro").strip()
        strat_lower = strat_id_str.lower()

        if "wyckoff" in strat_lower:
            badge_text = "Wyckoff · v2.2"
        elif "ema" in strat_lower:
            badge_text = "EMA Cross · Dual"
        elif "ict" in strat_lower:
            badge_text = "Confluence v4.2"
        else:
            try:
                from backend.core.strategies.strategy_loader import discover_strategies
                for s in discover_strategies():
                    if s["id"] == strat_id_str or s["name"].lower() == strat_lower:
                        badge_text = s["name"]
                        break
                else:
                    badge_text = strat_id_str
            except Exception:
                badge_text = strat_id_str

        self.btn_top_ind.setText(badge_text)
        self.btn_top_ind.setToolTip(f"Active Strategy: {badge_text}\nClick to switch strategy or configure indicators")
        self.window.active_strategy_id = strat_id_str
        self.window.current_strategy_name = badge_text

    def _show_strategy_and_indicators_menu(self):
        """Pops up a clean context menu on btnTopIndicator allowing one-click strategy switching."""
        if not hasattr(self, "btn_top_ind") or not self.btn_top_ind:
            return
        menu = QMenu(self.window)
        is_dark = getattr(self, "is_dark_theme", False)

        menu_bg = "#0d121f" if is_dark else "#ffffff"
        menu_border = "#1e293b" if is_dark else "#cbd5e1"
        menu_text = "#e2e8f0" if is_dark else "#0f172a"
        menu_hover = "#1e293b" if is_dark else "#f1f5f9"

        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {menu_bg};
                color: {menu_text};
                border: 1px solid {menu_border};
                border-radius: 4px;
                padding: 4px 0px;
                font-family: 'Segoe UI', -apple-system, sans-serif;
                font-size: 11px;
            }}
            QMenu::item {{
                padding: 6px 20px 6px 12px;
                margin: 1px 4px;
                border-radius: 3px;
            }}
            QMenu::item:selected {{
                background-color: {menu_hover};
                color: {menu_text};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {menu_border};
                margin: 4px 0px;
            }}
        """)

        act_title = menu.addAction("QUANTITATIVE STRATEGY")
        act_title.setEnabled(False)

        assets_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets"
        )
        icon_check = QIcon(os.path.join(assets_dir, "check_vector_emerald.svg" if not is_dark else "check_vector_light.svg"))
        icon_import = QIcon(os.path.join(assets_dir, "icon_import.svg"))
        icon_folder = QIcon(os.path.join(assets_dir, "icon_folder.svg"))
        icon_gear = QIcon(os.path.join(assets_dir, "tool_gear.svg"))

        from backend.core.strategies.strategy_loader import discover_strategies
        strats = discover_strategies()
        curr_strat = getattr(self.window, "active_strategy_id", "builtin_ict_pro").lower()

        for s in strats:
            s_id = s["id"]
            s_name = s["name"]
            is_active = (s_id.lower() == curr_strat) or (s_name.lower() in curr_strat) or (curr_strat in s_id.lower())
            if is_active:
                action = menu.addAction(icon_check, s_name)
            else:
                action = menu.addAction(s_name)

            def make_handler(target_id=s_id, target_name=s_name):
                return lambda: self._apply_strategy_switch(target_id, target_name)

            action.triggered.connect(make_handler())

        menu.addSeparator()
        act_import = menu.addAction(icon_import, "Import Strategy Script (.py)...")
        act_import.triggered.connect(self._open_import_strategy_file)

        act_folder = menu.addAction(icon_folder, "Open Strategies Folder...")
        act_folder.triggered.connect(self._open_strategies_folder)

        act_mgr = menu.addAction(icon_gear, "Strategy Manager...")
        act_mgr.triggered.connect(self._open_strategy_manager_dialog)

        menu.addSeparator()
        act_ind = menu.addAction(icon_gear, "Indicator Settings (Market Profile, Oscillators)...")
        if hasattr(self.window, "open_indicators"):
            act_ind.triggered.connect(self.window.open_indicators)

        menu.exec(self.btn_top_ind.mapToGlobal(QPoint(0, self.btn_top_ind.height() + 2)))

    def _open_import_strategy_file(self):
        from frontend.widgets.strategy_manager_dialog import StrategyManagerDialog
        dlg = StrategyManagerDialog(self.window)
        dlg.strategy_activated.connect(self._apply_strategy_switch)
        dlg._on_import_clicked()

    def _open_strategies_folder(self):
        from backend.core.strategies.strategy_loader import get_strategies_dir
        strat_dir = get_strategies_dir()
        try:
            if sys.platform == "win32":
                os.startfile(str(strat_dir))
            else:
                import subprocess
                subprocess.Popen(["xdg-open", str(strat_dir)])
        except Exception as e:
            logger.warning(f"Failed to open strategies folder: {e}")

    def _open_strategy_manager_dialog(self):
        from frontend.widgets.strategy_manager_dialog import StrategyManagerDialog
        dlg = StrategyManagerDialog(self.window)
        dlg.strategy_activated.connect(self._apply_strategy_switch)
        dlg.exec()

    def _apply_strategy_switch(self, strat_id, strat_name):
        """Centralized switch of active trading strategy."""
        self.window.active_strategy_id = strat_id
        self.update_strategy_badge(strat_id)

        # 1. Persist to settings.json
        try:
            import json, os
            cfg_p = "config/settings.json"
            cfg = {}
            if os.path.exists(cfg_p):
                with open(cfg_p, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            cfg["strategy"] = strat_id
            with open(cfg_p, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4)
        except Exception as e:
            logger.debug(f"[HeaderController] Failed to save strategy: {e}")

        # 2. Sync Settings Tab comboStrategy if present
        if hasattr(self.window, "comboStrategy") and self.window.comboStrategy:
            try:
                import shiboken6
                if shiboken6.isValid(self.window.comboStrategy):
                    for i in range(self.window.comboStrategy.count()):
                        if self.window.comboStrategy.itemData(i) == strat_id:
                            self.window.comboStrategy.blockSignals(True)
                            self.window.comboStrategy.setCurrentIndex(i)
                            self.window.comboStrategy.blockSignals(False)
                            break
            except Exception:
                pass

        # 3. Hot-reload into live BotWorker if running
        try:
            qt = getattr(self.window, "quant_terminal", None)
            bot = getattr(qt, "bot_worker", None) if qt else None
            if bot:
                from backend.core.strategies import get_strategy_instance
                bot.ict = get_strategy_instance(strat_id)
                bot.strategy_name = strat_name
        except Exception as e:
            logger.debug(f"[HeaderController] Hot reload bot error: {e}")

        # 4. Trigger immediate chart canvas and AI Trading Plan re-analysis
        if hasattr(self.window, "draw_and_analyze") and hasattr(self.window, "current_sym") and self.window.current_sym:
            self.window.draw_and_analyze(self.window.current_sym)

        logger.info(f"[HeaderController] Active strategy switched to: {strat_name} ({strat_id})")

    def set_execution_mode(self, mode):
        """Set algorithm dispatch mode (configured in Settings tab) and update telemetry."""
        self.execution_mode = mode
        if hasattr(self.window, "lblAISubtitle") and self.window.lblAISubtitle:
            if mode == "MANUAL":
                self.window.lblAISubtitle.setText("Manual Alerts")
            elif mode == "FULL-AUTO":
                self.window.lblAISubtitle.setText("Autonomous STP")
            else:
                self.window.lblAISubtitle.setText("Semi-Automated")
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
            bg = "#0a0c10" if is_dark else "#ffffff"
            border = "#1e222d" if is_dark else "#cbd5e1"
            self.header_container.setStyleSheet(
                f"QFrame#topHeaderContainer {{ background-color: {bg}; border-bottom: 1px solid {border}; }}"
            )

        # 1b. Top Menu Bar (Height: 26px)
        if hasattr(self, "menu_bar") and self.menu_bar:
            bg_menu = "#060910" if is_dark else "#f8fafc"
            border_menu = "#1e222d" if is_dark else "#cbd5e1"
            self.menu_bar.setStyleSheet(
                f"QFrame#topMenuBar {{ background-color: {bg_menu}; border-bottom: 1px solid {border_menu}; }}"
            )
            if hasattr(self, "_apply_native_menu_bar_theme"):
                self._apply_native_menu_bar_theme(is_dark)
            style_m = self._create_mt5_menu_style(is_dark)
            for m in (getattr(self, "menu_file", None), getattr(self, "menu_view", None),
                      getattr(self, "menu_insert", None), getattr(self, "menu_charts", None),
                      getattr(self, "menu_tools", None), getattr(self, "menu_window", None),
                      getattr(self, "menu_help", None)):
                if m:
                    m.setStyleSheet(style_m)

        # 2. Bottom Status Bar (Height: 22px)
        if hasattr(self, "bottom_bar") and self.bottom_bar:
            bg = "#090d16" if is_dark else "#f8fafc"
            border = "#1e222d" if is_dark else "#e2e8f0"
            self.bottom_bar.setFixedHeight(22)
            self.bottom_bar.setStyleSheet(
                f"QFrame#bottomTabBar {{ background-color: {bg}; border-top: 1px solid {border}; }}"
            )

        # 3. Top Symbol & Subtitle (Single baseline)
        self._refresh_top_ticker()

        # 4. Discrete Timeframe Buttons
        self._update_tf_button_styles(is_dark)

        # 5. IND Badge Button & Algo Control Pill (MT5 Flat resting state + Hover border)
        if hasattr(self, "btn_top_ind") and self.btn_top_ind:
            ind_col = "#38bdf8" if is_dark else "#0284c7"
            border_col = "transparent"
            hover_bg = "#141721" if is_dark else "#f1f5f9"
            hover_col = "#38bdf8" if is_dark else "#0f172a"
            hover_border = "#272d3b" if is_dark else "#cbd5e1"
            self.btn_top_ind.setStyleSheet(
                f"QPushButton#btnTopIndicator {{ background-color: transparent; color: {ind_col}; border: 1px solid {border_col}; "
                f"border-radius: 2px; padding: 0 6px; margin: 0px; font-family: Consolas, monospace; font-size: 10px; font-weight: 600; "
                f"}} "
                f"QPushButton#btnTopIndicator:hover {{ color: {hover_col}; border: 1px solid {hover_border}; background-color: {hover_bg}; }} "
                f"QPushButton#btnTopIndicator:pressed {{ background-color: {'#0c1a2e' if is_dark else '#e2e8f0'}; }}"
            )

        if hasattr(self, "btn_algo_toggle") and self.btn_algo_toggle:
            if hasattr(self.btn_algo_toggle, "set_dark_theme"):
                self.btn_algo_toggle.set_dark_theme(is_dark)

        # 6. Central Telemetry (Account info only: BAL, EQ, PnL) - Flat institutional header
        if hasattr(self, "lbl_top_ticker") and self.lbl_top_ticker:
            self.lbl_top_ticker.setMinimumWidth(330)
            self.lbl_top_ticker.setStyleSheet(
                "background: transparent; border: none; padding: 0 4px; font-family: Consolas, monospace; font-size: 10px;"
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

        # 10. Bottom Session Indicator (merged into right-side telemetry cluster)
        if hasattr(self, "lbl_bottom_mid") and self.lbl_bottom_mid:
            self.lbl_bottom_mid.setVisible(False)
        if hasattr(self, "sep_bottom_nav") and self.sep_bottom_nav:
            self.sep_bottom_nav.setVisible(False)

        # 11. Consolidated Bottom Telemetry: FULL-ALGO | ● MT5: 1.2ms | 0% LOSS
        if hasattr(self, "lbl_bot_status") and self.lbl_bot_status:
            self.lbl_bot_status.setFixedHeight(30)
            self.lbl_bot_status.setText(self._format_bottom_telemetry(is_dark))

        # 12. Bottom Audit Log Button (Ctrl+L trigger) - Flat Typography (No Box Outline)
        if hasattr(self, "btn_bottom_audit") and self.btn_bottom_audit:
            if is_dark:
                self.btn_bottom_audit.setStyleSheet(
                    "QPushButton#btnBottomAudit { background: transparent; color: #94a3b8; border: none; "
                    "font-family: 'Segoe UI', sans-serif; font-size: 11px; font-weight: 600; padding: 0 4px; min-height: 22px; max-height: 22px; } "
                    "QPushButton#btnBottomAudit:hover { background: transparent; color: #38bdf8; }"
                )
            else:
                self.btn_bottom_audit.setStyleSheet(
                    "QPushButton#btnBottomAudit { background: transparent; color: #64748b; border: none; "
                    "font-family: 'Segoe UI', sans-serif; font-size: 11px; font-weight: 600; padding: 0 4px; min-height: 22px; max-height: 22px; } "
                    "QPushButton#btnBottomAudit:hover { background: transparent; color: #0284c7; }"
                )
        if hasattr(self, "sep_bottom_audit") and self.sep_bottom_audit:
            self.sep_bottom_audit.setStyleSheet(f"background-color: {'#334155' if is_dark else '#cbd5e1'};")

        # Sync Event Risk Badge to theme
        if hasattr(self, "_update_event_risk_badge"):
            self._update_event_risk_badge()

        # 13. Sync Bottom Navigation Tab Buttons Styling
        if hasattr(self, "_update_nav_buttons_style"):
            self._update_nav_buttons_style(is_dark)



    def _create_mt5_menu_style(self, is_dark):
        menu_bg = "#0d121f" if is_dark else "#ffffff"
        menu_border = "#1e293b" if is_dark else "#cbd5e1"
        menu_text = "#e2e8f0" if is_dark else "#0f172a"
        menu_hover = "#1e293b" if is_dark else "#f1f5f9"
        return f"""
            QMenu {{
                background-color: {menu_bg};
                color: {menu_text};
                border: 1px solid {menu_border};
                border-radius: 2px;
                padding: 4px 0px;
                font-family: 'Segoe UI', -apple-system, sans-serif;
                font-size: 11px;
            }}
            QMenu::item {{
                padding: 5px 28px 5px 22px;
                margin: 1px 4px;
                border-radius: 2px;
            }}
            QMenu::item:selected {{
                background-color: {menu_hover};
                color: {menu_text};
            }}
            QMenu::indicator {{
                width: 14px;
                height: 14px;
                margin-left: 4px;
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {menu_border};
                margin: 4px 0px;
            }}
        """

    def _apply_native_menu_bar_theme(self, is_dark: bool = False):
        if not hasattr(self, "native_menu_bar") or not self.native_menu_bar:
            return
        if is_dark:
            self.native_menu_bar.setStyleSheet("""
                QMenuBar#nativeMenuBar {
                    background-color: transparent;
                    color: #94a3b8;
                    font-family: 'Segoe UI', -apple-system, sans-serif;
                    font-size: 11px;
                    font-weight: 500;
                    border: none;
                    outline: none;
                }
                QMenuBar#nativeMenuBar::item {
                    background: transparent;
                    color: #94a3b8;
                    padding: 3px 8px;
                    border-radius: 2px;
                    border: none;
                    outline: none;
                }
                QMenuBar#nativeMenuBar::item:focus {
                    background: transparent;
                    border: none;
                    outline: none;
                }
                QMenuBar#nativeMenuBar::item:selected {
                    background-color: #1e293b;
                    color: #ffffff;
                    border: none;
                    outline: none;
                }
                QMenuBar#nativeMenuBar::item:pressed {
                    background-color: #0284c7;
                    color: #ffffff;
                    border: none;
                    outline: none;
                }
            """)
        else:
            self.native_menu_bar.setStyleSheet("""
                QMenuBar#nativeMenuBar {
                    background-color: transparent;
                    color: #334155;
                    font-family: 'Segoe UI', -apple-system, sans-serif;
                    font-size: 11px;
                    font-weight: 500;
                    border: none;
                    outline: none;
                }
                QMenuBar#nativeMenuBar::item {
                    background: transparent;
                    color: #334155;
                    padding: 3px 8px;
                    border-radius: 2px;
                    border: none;
                    outline: none;
                }
                QMenuBar#nativeMenuBar::item:focus {
                    background: transparent;
                    border: none;
                    outline: none;
                }
                QMenuBar#nativeMenuBar::item:selected {
                    background-color: #e2e8f0;
                    color: #0f172a;
                    border: none;
                    outline: none;
                }
                QMenuBar#nativeMenuBar::item:pressed {
                    background-color: #cbd5e1;
                    color: #0f172a;
                    border: none;
                    outline: none;
                }
            """)

    # -------------------------------------------------------------
    # ACTION HANDLERS & HELPERS FOR MT5 TOP MENUS
    # -------------------------------------------------------------
    def _on_select_symbol(self):
        """Ctrl+N: Opens SymbolSearchDialog and switches chart symbol."""
        try:
            from frontend.controllers.watchlist.symbol_search_dialog import SymbolSearchDialog
            dlg = SymbolSearchDialog(self.window)
            if dlg.exec() and dlg.selected_symbol:
                sym = dlg.selected_symbol
                cat = getattr(dlg, "selected_category", "OTHER")
                if hasattr(self.terminal, "watchlist") and self.terminal.watchlist:
                    self.terminal.watchlist.add_symbol_to_tree(sym, cat)
                if hasattr(self.window, "draw_and_analyze"):
                    self.window.draw_and_analyze(sym)
                if hasattr(self, "_refresh_top_ticker"):
                    self._refresh_top_ticker()
        except Exception as e:
            logger.warning(f"Error selecting symbol from menu: {e}")

    def _on_save_chart_picture(self):
        """Ctrl+S: Captures high-res chart picture to PNG/JPG."""
        try:
            from PySide6.QtWidgets import QFileDialog, QMessageBox
            curr_sym = getattr(self.window, "current_sym", "XAUUSD")
            clean_sym = curr_sym.split("\n")[0].strip()
            fn = f"vectra_chart_{clean_sym}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            save_path, _ = QFileDialog.getSaveFileName(
                self.window, "Save Chart As Picture", fn, "PNG Image (*.png);;JPEG Image (*.jpg)"
            )
            if save_path:
                plot_w = getattr(self.window, "plot_widget", None) or getattr(self.window, "frameChartArea", None)
                if plot_w:
                    pix = plot_w.grab()
                    pix.save(save_path)
                    QMessageBox.information(self.window, "Chart Saved", f"Chart snapshot saved to:\n{save_path}")
        except Exception as e:
            logger.warning(f"Error saving chart picture: {e}")

    def _on_open_data_folder(self):
        """Opens system data / database directory in Windows Explorer."""
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            data_dir = os.path.join(base_dir, "backend", "database")
            if not os.path.exists(data_dir):
                data_dir = base_dir
            if sys.platform == "win32":
                os.startfile(data_dir)
            else:
                import subprocess
                subprocess.Popen(["xdg-open", data_dir])
        except Exception as e:
            logger.warning(f"Failed to open data folder: {e}")

    def _on_export_blotter_csv(self):
        """Exports open positions and deals to a clean CSV file."""
        try:
            from PySide6.QtWidgets import QFileDialog, QMessageBox
            import csv
            fn = f"blotter_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            save_path, _ = QFileDialog.getSaveFileName(self.window, "Export Blotter to CSV", fn, "CSV Files (*.csv)")
            if not save_path:
                return
            positions = mt5.positions_get() if mt5.terminal_info() else []
            with open(save_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Ticket", "Time", "Symbol", "Side", "Volume (Lots)", "Open Price", "Current Price", "SL", "TP", "Profit ($)", "Comment"])
                if positions:
                    for p in positions:
                        t_str = datetime.fromtimestamp(p.time).strftime("%Y-%m-%d %H:%M:%S") if hasattr(p, "time") else ""
                        side = "BUY" if p.type == 0 else "SELL"
                        w.writerow([p.ticket, t_str, p.symbol, side, p.volume, p.price_open, p.price_current, p.sl, p.tp, f"{p.profit:.2f}", getattr(p, "comment", "")])
            QMessageBox.information(self.window, "Export Completed", f"Blotter exported successfully to:\n{save_path}")
        except Exception as e:
            logger.warning(f"Error exporting blotter CSV: {e}")

    def _toggle_watchlist(self):
        """Ctrl+M: Toggles Market Watch / Watchlist sidebar."""
        if hasattr(self.window, "sidebar"):
            is_vis = self.window.sidebar.isVisible()
            if is_vis:
                self.window.sidebar.setVisible(False)
                self.window.watchlist_collapsed = True
                if hasattr(self.window, "btn_edge_wl") and self.window.btn_edge_wl:
                    self.window.btn_edge_wl.setVisible(True)
            else:
                self.window.sidebar.setVisible(True)
                self.window.watchlist_collapsed = False
                if hasattr(self.window, "btn_edge_wl") and self.window.btn_edge_wl:
                    self.window.btn_edge_wl.setVisible(False)
                if hasattr(self.window, "mainSplitter"):
                    total_w = max(400, self.window.mainSplitter.width() or 1440)
                    self.window.mainSplitter.setSizes([260, max(100, total_w - 260)])

    def _toggle_trading_plan(self):
        """Ctrl+T: Toggles Toolbox / Trading Plan panel."""
        if hasattr(self.window, "frameAIArea"):
            if self.window.frameAIArea.isVisible():
                if hasattr(self.window, "btn_close_plan") and self.window.btn_close_plan:
                    self.window.btn_close_plan.click()
                else:
                    self.window.frameAIArea.setVisible(False)
                    if hasattr(self.window, "btn_edge_plan") and self.window.btn_edge_plan:
                        self.window.btn_edge_plan.setVisible(True)
            else:
                if hasattr(self.window, "btn_edge_plan") and self.window.btn_edge_plan:
                    self.window.btn_edge_plan.click()
                else:
                    self.window.frameAIArea.setVisible(True)

    def _open_new_order_ticket(self):
        """F9: Opens New Order Ticket directly in Manual Quant Copilot mode."""
        if hasattr(self.window, "frameAIArea"):
            if not self.window.frameAIArea.isVisible():
                if hasattr(self.window, "btn_edge_plan") and self.window.btn_edge_plan:
                    self.window.btn_edge_plan.click()
                else:
                    self.window.frameAIArea.setVisible(True)
        if hasattr(self.window, "_switch_plan_mode"):
            self.window._switch_plan_mode("manual")
        elif hasattr(self.window, "btnPlanModeManual") and self.window.btnPlanModeManual:
            self.window.btnPlanModeManual.click()

    def _toggle_blotter_dock(self):
        """Ctrl+B: Toggles Trade Blotter dock collapse / expand."""
        if hasattr(self.window, "btnDockToggle") and self.window.btnDockToggle:
            self.window.btnDockToggle.click()
        elif hasattr(self.window, "frameExecutions"):
            vis = self.window.frameExecutions.isVisible()
            self.window.frameExecutions.setVisible(not vis)

    def _toggle_color_theme(self):
        """Toggles between Dark Institutional and Light Institutional theme."""
        if hasattr(self.terminal, "_on_toggle_theme"):
            self.terminal._on_toggle_theme()
        elif hasattr(self.terminal, "toggle_theme"):
            self.terminal.toggle_theme()

    def _toggle_volume_profile(self):
        """Toggles Volume Profile (VPOC, VAH, VAL, VA fill) visibility on chart."""
        if hasattr(self.window, "line_vpoc") and self.window.line_vpoc:
            target_vis = not self.window.line_vpoc.isVisible()
            for fn in ("toggle_vpoc", "toggle_tpoc", "toggle_vah", "toggle_val", "toggle_va_fill"):
                if hasattr(self.window, fn):
                    try:
                        getattr(self.window, fn)(target_vis)
                    except Exception:
                        pass

    def _set_drawing_tool(self, mode_str):
        """Sets active drawing tool mode (crosshair, trendline, rectangle, ruler)."""
        de = getattr(self.window, "drawing_engine", None)
        if de:
            from frontend.controllers.chart.drawing_engine import ChartDrawingEngine
            mode_map = {
                "crosshair": ChartDrawingEngine.MODE_CROSSHAIR,
                "trendline": ChartDrawingEngine.MODE_TRENDLINE,
                "rectangle": ChartDrawingEngine.MODE_RECTANGLE,
                "ruler": ChartDrawingEngine.MODE_RULER,
            }
            if mode_str in mode_map:
                de.set_mode(mode_map[mode_str])

    def _clear_all_drawings(self):
        """Clears all user drawings on the active chart."""
        de = getattr(self.window, "drawing_engine", None)
        if de and hasattr(de, "clear_user_drawings"):
            de.clear_user_drawings()

    def _set_chart_type(self, mode_str):
        """Alt+1..3: Switches chart rendering type (candlestick, bar, line)."""
        cs = getattr(self.window, "candlesticks", None)
        if cs and hasattr(cs, "set_chart_mode"):
            cs.set_chart_mode(mode_str)

    def _zoom_in_chart(self):
        """+ / =: Zooms in chart horizontal axis."""
        pw = getattr(self.window, "plot_widget", None)
        if pw:
            pw.getViewBox().scaleBy((0.8, 1.0))

    def _zoom_out_chart(self):
        """-: Zooms out chart horizontal axis."""
        pw = getattr(self.window, "plot_widget", None)
        if pw:
            pw.getViewBox().scaleBy((1.25, 1.0))

    def _auto_fit_chart(self):
        """Ctrl+0: Auto-fits chart range to current price and bar history."""
        pw = getattr(self.window, "plot_widget", None)
        if pw:
            pw.autoRange()

    def _toggle_grid(self):
        """Ctrl+G: Toggles background grid visibility."""
        pw = getattr(self.window, "plot_widget", None)
        if pw:
            self._grid_enabled = not getattr(self, "_grid_enabled", True)
            pw.showGrid(x=self._grid_enabled, y=self._grid_enabled, alpha=0.12)
            if hasattr(self, "_act_grid") and self._act_grid:
                self._act_grid.setChecked(self._grid_enabled)

    def _refresh_chart_data(self):
        """Ctrl+F5: Refreshes candlestick feed and Market Profile from MT5."""
        if hasattr(self.window, "draw_and_analyze"):
            sym = getattr(self.window, "current_sym", "XAUUSD")
            self.window.draw_and_analyze(sym)

    def _trigger_kill_switch(self):
        """Ctrl+Shift+K: Activates emergency kill switch / liquidation."""
        if hasattr(self.terminal, "blotter") and hasattr(self.terminal.blotter, "_handle_kill_switch"):
            self.terminal.blotter._handle_kill_switch()
        elif hasattr(self.window, "btnEmergencyKill"):
            self.window.btnEmergencyKill.click()

    def _run_in_background(self):
        """Ctrl+Shift+B: Minimizes dashboard to system tray and enters background headless execution."""
        term = getattr(self, "terminal", None) or getattr(self.window, "quant_terminal", None)
        if term and hasattr(term, "tray_manager") and term.tray_manager:
            term.tray_manager.minimize_to_tray()
        else:
            self.window.hide()

    def _export_vps_profile(self):
        """Ctrl+Shift+E: Exports active configuration into a deployable JSON profile for headless VPS execution."""
        import os
        import json
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from backend.core.engine_config import BotRunConfig

        term = getattr(self, "terminal", None) or getattr(self.window, "quant_terminal", None)
        default_dir = os.path.join(os.getcwd(), "config")
        os.makedirs(default_dir, exist_ok=True)
        default_path = os.path.join(default_dir, "vps_profile.json")

        file_path, _ = QFileDialog.getSaveFileName(
            self.window,
            "Export VPS Config",
            default_path,
            "JSON Configuration (*.json)",
        )
        if not file_path:
            return

        cfg_dict = {}
        if term and hasattr(term, "_build_active_bot_config"):
            bot_cfg = term._build_active_bot_config()
            cfg_dict = bot_cfg.to_dict()
        else:
            try:
                with open("config/settings.json", "r", encoding="utf-8") as f:
                    cfg_dict = json.load(f)
            except Exception:
                cfg_dict = BotRunConfig().to_dict()

        try:
            with open(file_path, "w", encoding="utf-8") as f_out:
                json.dump(cfg_dict, f_out, indent=2)

            QMessageBox.information(
                self.window,
                "VPS Profile Exported",
                f"Configuration exported successfully to:\n{file_path}\n\n"
                f"To run 24/7 on your VPS without GUI, execute:\n"
                f"python run_headless.py --config {os.path.basename(file_path)}",
            )
        except Exception as e:
            QMessageBox.critical(
                self.window,
                "Export Error",
                f"Failed to export VPS profile: {e}",
            )

    def _reset_default_layout(self):
        """Window -> Default Layout: Restores institutional 3-pane proportions."""
        if hasattr(self.window, "sidebar"):
            self.window.sidebar.setVisible(True)
            self.window.watchlist_collapsed = False
        if hasattr(self.window, "btn_edge_wl") and self.window.btn_edge_wl:
            self.window.btn_edge_wl.setVisible(False)
        if hasattr(self.window, "mainSplitter"):
            total_w = max(400, self.window.mainSplitter.width() or 1440)
            self.window.mainSplitter.setSizes([260, max(100, total_w - 260)])
        if hasattr(self.window, "frameAIArea"):
            self.window.frameAIArea.setVisible(True)
        if hasattr(self.window, "btn_edge_plan") and self.window.btn_edge_plan:
            self.window.btn_edge_plan.setVisible(False)
        if getattr(self.window, "is_dock_collapsed", False):
            if hasattr(self.window, "btnDockToggle") and self.window.btnDockToggle:
                self.window.btnDockToggle.click()
        self._focus_chart_active = False

    def _toggle_focus_chart(self):
        """Shift+F11: Focus Chart Mode collapses sidebars to give 100% canvas to chart."""
        self._focus_chart_active = not getattr(self, "_focus_chart_active", False)
        if self._focus_chart_active:
            if hasattr(self.window, "sidebar"):
                self.window.sidebar.setVisible(False)
            if hasattr(self.window, "btn_edge_wl") and self.window.btn_edge_wl:
                self.window.btn_edge_wl.setVisible(True)
            if hasattr(self.window, "frameAIArea"):
                self.window.frameAIArea.setVisible(False)
            if hasattr(self.window, "btn_edge_plan") and self.window.btn_edge_plan:
                self.window.btn_edge_plan.setVisible(True)
            if not getattr(self.window, "is_dock_collapsed", False):
                if hasattr(self.window, "btnDockToggle") and self.window.btnDockToggle:
                    self.window.btnDockToggle.click()
        else:
            self._reset_default_layout()

    def _show_shortcuts_cheat_sheet(self):
        """Displays a clean institutional dialog summarizing all global hotkeys."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView
        dlg = QDialog(self.window)
        dlg.setWindowTitle("VECTRA Keyboard Shortcuts")
        dlg.setFixedSize(520, 500)
        is_dark = getattr(self, "is_dark_theme", False)

        bg = "#0c0e14" if is_dark else "#ffffff"
        text_col = "#f8fafc" if is_dark else "#0f172a"
        border_col = "#272d3b" if is_dark else "#cbd5e1"

        dlg.setStyleSheet(f"""
            QDialog {{ background-color: {bg}; border: 1px solid {border_col}; }}
            QTableWidget {{ background-color: {'#080b11' if is_dark else '#f8fafc'}; color: {text_col}; border: 1px solid {border_col}; gridline-color: {border_col}; font-family: 'Segoe UI', sans-serif; font-size: 11px; }}
            QHeaderView::section {{ background-color: {'#161d2d' if is_dark else '#e2e8f0'}; color: {text_col}; font-weight: bold; border: 1px solid {border_col}; padding: 4px; }}
        """)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        lbl = QLabel("VECTRA QUANTITATIVE TERMINAL - SHORTCUT CHEAT SHEET")
        lbl.setStyleSheet(f"color: {'#38bdf8' if is_dark else '#0284c7'}; font-weight: bold; font-family: Consolas, monospace; font-size: 11px;")
        layout.addWidget(lbl)

        table = QTableWidget(16, 2)
        table.setHorizontalHeaderLabels(["HOTKEY", "ACTION"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)

        shortcuts = [
            ("F1", "Terminal"),
            ("F2", "Reports"),
            ("Ctrl+R", "Strategy Tester"),
            ("F3", "Calendar"),
            ("F9", "New Order"),
            ("Ctrl+M", "Market Watch"),
            ("Ctrl+T", "Toolbox"),
            ("Ctrl+B", "Trade"),
            ("Ctrl+N", "New Chart..."),
            ("Ctrl+S", "Save As Picture..."),
            ("Ctrl+L", "Journal"),
            ("Ctrl+O", "Options"),
            ("Alt+1 / 2 / 3", "Bar Chart / Candlesticks / Line Chart"),
            ("Ctrl+0 / + / -", "Auto Range / Zoom In / Zoom Out"),
            ("Ctrl+G", "Grid"),
            ("Shift+F11 / F11", "Maximize Chart / Full Screen"),
        ]

        for row, (key, desc) in enumerate(shortcuts):
            item_k = QTableWidgetItem(key)
            item_k.setTextAlignment(Qt.AlignCenter)
            item_k.setFont(QFont("Consolas", 10, QFont.Bold))
            item_d = QTableWidgetItem(desc)
            table.setItem(row, 0, item_k)
            table.setItem(row, 1, item_d)

        layout.addWidget(table)
        dlg.exec()

    def _show_diagnostics_dialog(self):
        """Displays MT5 IPC diagnostics and telemetry summary."""
        from PySide6.QtWidgets import QMessageBox
        term = mt5.terminal_info()
        acc = mt5.account_info() if term else None

        if term and getattr(term, "connected", False):
            ping = getattr(self, "broker_latency_ms", 0.0)
            msg = (
                f"MT5 Terminal: CONNECTED (Build {getattr(term, 'build', 'N/A')})\n"
                f"Broker Server: {getattr(acc, 'server', 'N/A')}\n"
                f"Trading Account: #{getattr(acc, 'login', 'N/A')} ({getattr(acc, 'name', 'User')})\n"
                f"Company: {getattr(acc, 'company', 'N/A')}\n"
                f"Server Ping Latency: {ping:.1f}ms\n"
                f"Currency / Leverage: {getattr(acc, 'currency', 'USD')} (1:{getattr(acc, 'leverage', 100)})\n"
                f"Trade Allowed: {getattr(term, 'trade_allowed', True)}\n"
                f"Headless Mode: Active in Background"
            )
            QMessageBox.information(self.window, "MT5 IPC Diagnostics", msg)
        else:
            QMessageBox.warning(self.window, "MT5 IPC Diagnostics", "MT5 Terminal is currently OFFLINE.\nCheck if MT5 is running or credentials are correct.")

    def _trigger_journal(self):
        btn = getattr(self, "btn_bottom_audit", None)
        if btn:
            btn.click()

    def _trigger_options(self):
        btn = getattr(self, "btnNavSettings", None)
        if btn:
            btn.click()

    # -------------------------------------------------------------
    # 7 AUTHENTIC MT5 MENUS IMPLEMENTATION
    # -------------------------------------------------------------
    def _show_file_menu(self):
        if not hasattr(self, "btn_menu_file") or not self.btn_menu_file:
            return
        menu = QMenu(self.window)
        menu.setStyleSheet(self._create_mt5_menu_style(getattr(self, "is_dark_theme", False)))

        act_sym = menu.addAction("New Chart...")
        act_sym.setShortcut(QKeySequence("Ctrl+N"))
        act_sym.triggered.connect(self._on_select_symbol)

        act_save = menu.addAction("Save As Picture...")
        act_save.setShortcut(QKeySequence("Ctrl+S"))
        act_save.triggered.connect(self._on_save_chart_picture)

        act_data = menu.addAction("Open Data Folder")
        act_data.triggered.connect(self._on_open_data_folder)

        act_export = menu.addAction("Export Data...")
        act_export.triggered.connect(self._on_export_blotter_csv)

        menu.addSeparator()

        act_opt = menu.addAction("Login to Trade Account")
        act_opt.triggered.connect(self._trigger_options)

        act_exit = menu.addAction("Exit")
        act_exit.setShortcut(QKeySequence("Alt+F4"))
        act_exit.triggered.connect(self.window.close)

        menu.exec(self.btn_menu_file.mapToGlobal(QPoint(0, self.btn_menu_file.height())))

    def _show_view_menu(self):
        if not hasattr(self, "btn_menu_view") or not self.btn_menu_view:
            return
        menu = QMenu(self.window)
        menu.setStyleSheet(self._create_mt5_menu_style(getattr(self, "is_dark_theme", False)))

        curr_w = self.window.tabWidget.currentWidget() if hasattr(self.window, "tabWidget") else None

        act_term = menu.addAction("✓ Terminal" if curr_w == getattr(self.window, "tab2", None) else "Terminal")
        act_term.setShortcut(QKeySequence("F1"))
        act_term.triggered.connect(lambda: self._switch_nav_tab(self.window.tab2, getattr(self, "btnNavTerminal", None), "Terminal"))

        act_stats = menu.addAction("✓ Reports" if curr_w == getattr(self.window, "tab3", None) else "Reports")
        act_stats.setShortcut(QKeySequence("F2"))
        act_stats.triggered.connect(lambda: self._switch_nav_tab(self.window.tab3, getattr(self, "btnNavStats", None), "Performance"))

        act_bt = menu.addAction("✓ Strategy Tester" if curr_w == getattr(self.window, "tab_5", None) else "Strategy Tester")
        act_bt.setShortcut(QKeySequence("Ctrl+R"))
        act_bt.triggered.connect(lambda: self._switch_nav_tab(self.window.tab_5, getattr(self, "btnNavBacktest", None), "Backtest"))

        cal_tab = getattr(self.window, "tabCalendar", None)
        if cal_tab:
            act_cal = menu.addAction("✓ Calendar" if curr_w == cal_tab else "Calendar")
            act_cal.setShortcut(QKeySequence("F3"))
            act_cal.triggered.connect(lambda: self._switch_nav_tab(cal_tab, getattr(self, "btnNavCalendar", None), "Calendar"))

        menu.addSeparator()

        is_wl_open = getattr(self.window, "sidebar", None) and self.window.sidebar.isVisible()
        act_wl = menu.addAction("✓ Market Watch" if is_wl_open else "Market Watch")
        act_wl.setShortcut(QKeySequence("Ctrl+M"))
        act_wl.triggered.connect(self._toggle_watchlist)

        is_plan_open = getattr(self.window, "frameAIArea", None) and self.window.frameAIArea.isVisible()
        act_plan = menu.addAction("✓ Toolbox" if is_plan_open else "Toolbox")
        act_plan.setShortcut(QKeySequence("Ctrl+T"))
        act_plan.triggered.connect(self._toggle_trading_plan)

        is_dock_open = not getattr(self.window, "is_dock_collapsed", False)
        act_blotter = menu.addAction("✓ Trade" if is_dock_open else "Trade")
        act_blotter.setShortcut(QKeySequence("Ctrl+B"))
        act_blotter.triggered.connect(self._toggle_blotter_dock)

        menu.addSeparator()

        act_journal = menu.addAction("Journal")
        act_journal.setShortcut(QKeySequence("Ctrl+L"))
        act_journal.triggered.connect(self._trigger_journal)

        is_dark = getattr(self, "is_dark_theme", False)
        sub_theme = menu.addMenu("Theme")
        sub_theme.setStyleSheet(self._create_mt5_menu_style(is_dark))
        act_dark = sub_theme.addAction("✓ Dark" if is_dark else "Dark")
        act_dark.triggered.connect(lambda: self._toggle_color_theme() if not getattr(self, "is_dark_theme", False) else None)
        act_light = sub_theme.addAction("✓ Light" if not is_dark else "Light")
        act_light.triggered.connect(lambda: self._toggle_color_theme() if getattr(self, "is_dark_theme", False) else None)

        menu.addSeparator()

        act_fs = menu.addAction("Full Screen")
        act_fs.setShortcut(QKeySequence("F11"))
        def _toggle_fs():
            if self.window.isFullScreen():
                self.window.showNormal()
            else:
                self.window.showFullScreen()
        act_fs.triggered.connect(_toggle_fs)

        menu.exec(self.btn_menu_view.mapToGlobal(QPoint(0, self.btn_menu_view.height())))

    def _show_insert_menu(self):
        if not hasattr(self, "btn_menu_insert") or not self.btn_menu_insert:
            return
        menu = QMenu(self.window)
        is_dark = getattr(self, "is_dark_theme", False)
        menu.setStyleSheet(self._create_mt5_menu_style(is_dark))

        # Submenu: Indicators
        sub_ind = menu.addMenu("Indicators")
        sub_ind.setStyleSheet(self._create_mt5_menu_style(is_dark))

        act_cfg_ind = sub_ind.addAction("Settings...")
        act_cfg_ind.triggered.connect(self._show_strategy_and_indicators_menu)
        sub_ind.addSeparator()

        is_vpoc_vis = hasattr(self.window, "line_vpoc") and self.window.line_vpoc and self.window.line_vpoc.isVisible()
        act_vpoc = sub_ind.addAction("✓ Volume Profile" if is_vpoc_vis else "Volume Profile")
        act_vpoc.triggered.connect(self._toggle_volume_profile)

        act_fvg = sub_ind.addAction("Fair Value Gaps")
        act_fvg.triggered.connect(lambda: self._set_drawing_tool("rectangle"))

        # Submenu: Objects
        sub_draw = menu.addMenu("Objects")
        sub_draw.setStyleSheet(self._create_mt5_menu_style(is_dark))

        act_cross = sub_draw.addAction("Crosshair")
        act_cross.setShortcut(QKeySequence("Ctrl+1"))
        act_cross.triggered.connect(lambda: self._set_drawing_tool("crosshair"))

        act_trend = sub_draw.addAction("Trendline")
        act_trend.setShortcut(QKeySequence("Alt+T"))
        act_trend.triggered.connect(lambda: self._set_drawing_tool("trendline"))

        act_rect = sub_draw.addAction("Rectangle")
        act_rect.setShortcut(QKeySequence("Alt+R"))
        act_rect.triggered.connect(lambda: self._set_drawing_tool("rectangle"))

        act_ruler = sub_draw.addAction("Ruler")
        act_ruler.setShortcut(QKeySequence("Shift+M"))
        act_ruler.triggered.connect(lambda: self._set_drawing_tool("ruler"))

        sub_draw.addSeparator()
        act_clear_draw = sub_draw.addAction("Delete All")
        act_clear_draw.triggered.connect(self._clear_all_drawings)

        menu.exec(self.btn_menu_insert.mapToGlobal(QPoint(0, self.btn_menu_insert.height())))

    def _show_charts_menu(self):
        if not hasattr(self, "btn_menu_charts") or not self.btn_menu_charts:
            return
        menu = QMenu(self.window)
        is_dark = getattr(self, "is_dark_theme", False)
        menu.setStyleSheet(self._create_mt5_menu_style(is_dark))

        curr_mode = "candlestick"
        if hasattr(self.window, "candlesticks") and self.window.candlesticks:
            curr_mode = getattr(self.window.candlesticks, "chart_mode", "candlestick")

        act_bar = menu.addAction("✓ Bar Chart" if curr_mode == "bar" else "Bar Chart")
        act_bar.setShortcut(QKeySequence("Alt+1"))
        act_bar.triggered.connect(lambda: self._set_chart_type("bar"))

        act_candle = menu.addAction("✓ Candlesticks" if curr_mode == "candlestick" else "Candlesticks")
        act_candle.setShortcut(QKeySequence("Alt+2"))
        act_candle.triggered.connect(lambda: self._set_chart_type("candlestick"))

        act_line = menu.addAction("✓ Line Chart" if curr_mode == "line" else "Line Chart")
        act_line.setShortcut(QKeySequence("Alt+3"))
        act_line.triggered.connect(lambda: self._set_chart_type("line"))

        menu.addSeparator()

        sub_tf = menu.addMenu("Timeframes")
        sub_tf.setStyleSheet(self._create_mt5_menu_style(is_dark))
        tf_list = ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN1"]
        curr_tf = getattr(self.window, "current_tf_str", "H1")
        for tf in tf_list:
            act_tf = sub_tf.addAction(f"✓ {tf}" if tf == curr_tf else tf)
            def _make_tf_fn(target_tf=tf):
                return lambda: self._on_tf_click(target_tf) if hasattr(self, "_on_tf_click") else None
            act_tf.triggered.connect(_make_tf_fn())

        menu.addSeparator()

        act_zin = menu.addAction("Zoom In")
        act_zin.setShortcut(QKeySequence("+"))
        act_zin.triggered.connect(self._zoom_in_chart)

        act_zout = menu.addAction("Zoom Out")
        act_zout.setShortcut(QKeySequence("-"))
        act_zout.triggered.connect(self._zoom_out_chart)

        act_fit = menu.addAction("Auto Range")
        act_fit.setShortcut(QKeySequence("Ctrl+0"))
        act_fit.triggered.connect(self._auto_fit_chart)

        is_grid = getattr(self, "_grid_enabled", True)
        act_grid = menu.addAction("✓ Grid" if is_grid else "Grid")
        act_grid.setShortcut(QKeySequence("Ctrl+G"))
        act_grid.triggered.connect(self._toggle_grid)

        act_ref = menu.addAction("Refresh")
        act_ref.setShortcut(QKeySequence("Ctrl+F5"))
        act_ref.triggered.connect(self._refresh_chart_data)

        menu.exec(self.btn_menu_charts.mapToGlobal(QPoint(0, self.btn_menu_charts.height())))

    def _show_tools_menu(self):
        if not hasattr(self, "btn_menu_tools") or not self.btn_menu_tools:
            return
        menu = QMenu(self.window)
        menu.setStyleSheet(self._create_mt5_menu_style(getattr(self, "is_dark_theme", False)))

        act_order = menu.addAction("New Order")
        act_order.setShortcut(QKeySequence("F9"))
        act_order.triggered.connect(self._open_new_order_ticket)

        act_strat = menu.addAction("Strategy Manager...")
        act_strat.setShortcut(QKeySequence("Ctrl+Shift+S"))
        act_strat.triggered.connect(self._open_strategy_manager_dialog)

        act_bt = menu.addAction("Strategy Tester")
        act_bt.setShortcut(QKeySequence("Ctrl+R"))
        act_bt.triggered.connect(lambda: self._switch_nav_tab(self.window.tab_5, getattr(self, "btnNavBacktest", None), "Backtest"))

        act_kill = menu.addAction("Close All Positions")
        act_kill.setShortcut(QKeySequence("Ctrl+Shift+K"))
        act_kill.triggered.connect(self._trigger_kill_switch)

        menu.addSeparator()

        act_tray = menu.addAction("Minimize to Tray")
        act_tray.setShortcut(QKeySequence("Ctrl+Shift+B"))
        act_tray.triggered.connect(self._run_in_background)

        act_vps = menu.addAction("Export VPS Config...")
        act_vps.setShortcut(QKeySequence("Ctrl+Shift+E"))
        act_vps.triggered.connect(self._export_vps_profile)

        menu.addSeparator()

        act_journal = menu.addAction("Journal")
        act_journal.setShortcut(QKeySequence("Ctrl+L"))
        act_journal.triggered.connect(self._trigger_journal)

        cal_tab = getattr(self.window, "tabCalendar", None)
        if cal_tab:
            act_cal = menu.addAction("Economic Calendar")
            act_cal.setShortcut(QKeySequence("F3"))
            act_cal.triggered.connect(lambda: self._switch_nav_tab(cal_tab, getattr(self, "btnNavCalendar", None), "Calendar"))

        def _toggle_mt5_win():
            if mt5.is_mt5_window_visible():
                mt5.hide_mt5_window()
            else:
                mt5.show_mt5_window()

        act_mt5 = menu.addAction("Show/Hide MT5 Window")
        act_mt5.triggered.connect(_toggle_mt5_win)

        act_opt = menu.addAction("Options")
        act_opt.setShortcut(QKeySequence("Ctrl+O"))
        act_opt.triggered.connect(self._trigger_options)

        menu.exec(self.btn_menu_tools.mapToGlobal(QPoint(0, self.btn_menu_tools.height())))

    def _show_window_menu(self):
        if not hasattr(self, "btn_menu_window") or not self.btn_menu_window:
            return
        menu = QMenu(self.window)
        menu.setStyleSheet(self._create_mt5_menu_style(getattr(self, "is_dark_theme", False)))

        act_layout = menu.addAction("Default Layout")
        act_layout.triggered.connect(self._reset_default_layout)

        is_focus = getattr(self, "_focus_chart_active", False)
        act_focus = menu.addAction("✓ Maximize Chart" if is_focus else "Maximize Chart")
        act_focus.setShortcut(QKeySequence("Shift+F11"))
        act_focus.triggered.connect(self._toggle_focus_chart)

        menu.addSeparator()

        act_full = menu.addAction("Full Screen")
        act_full.setShortcut(QKeySequence("F11"))
        def _toggle_fs():
            if self.window.isFullScreen():
                self.window.showNormal()
            else:
                self.window.showFullScreen()
        act_full.triggered.connect(_toggle_fs)

        menu.exec(self.btn_menu_window.mapToGlobal(QPoint(0, self.btn_menu_window.height())))

    def _show_help_menu(self):
        if not hasattr(self, "btn_menu_help") or not self.btn_menu_help:
            return
        menu = QMenu(self.window)
        menu.setStyleSheet(self._create_mt5_menu_style(getattr(self, "is_dark_theme", False)))

        act_cheat = menu.addAction("Help Topics")
        act_cheat.setShortcut(QKeySequence("F1"))
        act_cheat.triggered.connect(self._show_shortcuts_cheat_sheet)

        act_diag = menu.addAction("Connection Diagnostics")
        act_diag.triggered.connect(self._show_diagnostics_dialog)

        menu.addSeparator()

        act_about = menu.addAction("About...")
        def _on_about():
            QMessageBox.information(
                self.window,
                "About VECTRA",
                "VECTRA Quantitative Trading OS v2.2\nArchitecture: MetaTrader 5 / Institutional ECN\nStrategy: ICT Zones Pro v4.2 / Market Profile vPOC\nBuilt for professional prop & multi-asset desks."
            )
        act_about.triggered.connect(_on_about)

        menu.exec(self.btn_menu_help.mapToGlobal(QPoint(0, self.btn_menu_help.height())))

    def _setup_native_mt5_menus(self, native_mb, is_dark):
        """Constructs genuine MT5 Dropdown Menus with unified canonical QActions for 100% working global shortcuts."""
        style_menu = self._create_mt5_menu_style(is_dark)

        # Helper to create canonical action wired to window (Single Source of Truth, Zero Ambiguity)
        def _reg_action(parent_menu, text, shortcut=None, handler=None, checkable=False):
            act = QAction(text, self.window)
            act.setShortcutContext(Qt.WindowShortcut)
            act.activated = act.triggered
            if checkable:
                act.setCheckable(True)
            if shortcut:
                if isinstance(shortcut, (list, tuple)):
                    act.setShortcuts([QKeySequence(s) for s in shortcut])
                else:
                    act.setShortcut(QKeySequence(shortcut))
            if handler:
                act.triggered.connect(handler)
            self.window.addAction(act)
            if parent_menu:
                parent_menu.addAction(act)
            return act

        # -------------------------------------------------------------
        # 1. FILE MENU
        # -------------------------------------------------------------
        m_file = native_mb.addMenu("&File")
        m_file.setStyleSheet(style_menu)
        self.menu_file = m_file

        act_sym = _reg_action(m_file, "New Chart...", "Ctrl+N", self._on_select_symbol)
        act_save = _reg_action(m_file, "Save As Picture...", "Ctrl+S", self._on_save_chart_picture)
        act_data = _reg_action(m_file, "Open Data Folder", None, self._on_open_data_folder)
        act_export = _reg_action(m_file, "Export Data...", None, self._on_export_blotter_csv)

        m_file.addSeparator()

        act_login = _reg_action(m_file, "Login to Trade Account", None, self._trigger_options)
        act_exit = _reg_action(m_file, "Exit", "Alt+F4", self.window.close)

        # -------------------------------------------------------------
        # SHARED CANONICAL ACTIONS (Cross-menu without shortcut collisions)
        # -------------------------------------------------------------
        act_bt = _reg_action(
            None, "Strategy Tester", "Ctrl+R",
            lambda: self._switch_nav_tab(self.window.tab_5, getattr(self, "btnNavBacktest", None), "Backtest"),
            checkable=True
        )

        act_cal = _reg_action(
            None, "Economic Calendar", "F3",
            lambda: self._switch_nav_tab(getattr(self.window, "tabCalendar", None), getattr(self, "btnNavCalendar", None), "Calendar"),
            checkable=True
        )

        act_journal = _reg_action(None, "Journal", "Ctrl+L", self._trigger_journal)

        def _toggle_fs():
            if self.window.isFullScreen():
                self.window.showNormal()
            else:
                self.window.showFullScreen()
        act_fs = _reg_action(None, "Full Screen", "F11", _toggle_fs)

        # -------------------------------------------------------------
        # 2. VIEW MENU
        # -------------------------------------------------------------
        m_view = native_mb.addMenu("&View")
        m_view.setStyleSheet(style_menu)
        self.menu_view = m_view

        act_term = _reg_action(
            m_view, "Terminal", "F1",
            lambda: self._switch_nav_tab(self.window.tab2, getattr(self, "btnNavTerminal", None), "Terminal"),
            checkable=True
        )
        act_stats = _reg_action(
            m_view, "Reports", "F2",
            lambda: self._switch_nav_tab(self.window.tab3, getattr(self, "btnNavStats", None), "Performance"),
            checkable=True
        )
        m_view.addAction(act_bt)
        m_view.addAction(act_cal)

        m_view.addSeparator()

        act_wl = _reg_action(m_view, "Market Watch", "Ctrl+M", self._toggle_watchlist, checkable=True)
        act_plan = _reg_action(m_view, "Toolbox", "Ctrl+T", self._toggle_trading_plan, checkable=True)
        act_blotter = _reg_action(m_view, "Trade", "Ctrl+B", self._toggle_blotter_dock, checkable=True)

        m_view.addSeparator()
        m_view.addAction(act_journal)

        sub_theme = m_view.addMenu("Theme")
        sub_theme.setStyleSheet(style_menu)
        is_d = getattr(self, "is_dark_theme", False)
        act_dark = sub_theme.addAction("Dark")
        act_dark.setCheckable(True)
        act_dark.setChecked(is_d)
        act_dark.triggered.connect(lambda: self._toggle_color_theme() if not getattr(self, "is_dark_theme", False) else None)
        act_light = sub_theme.addAction("Light")
        act_light.setCheckable(True)
        act_light.setChecked(not is_d)
        act_light.triggered.connect(lambda: self._toggle_color_theme() if getattr(self, "is_dark_theme", False) else None)

        m_view.addSeparator()
        m_view.addAction(act_fs)

        def _sync_view_states():
            curr_w = self.window.tabWidget.currentWidget() if hasattr(self.window, "tabWidget") else None
            act_term.setChecked(curr_w == getattr(self.window, "tab2", None))
            act_stats.setChecked(curr_w == getattr(self.window, "tab3", None))
            act_bt.setChecked(curr_w == getattr(self.window, "tab_5", None))
            cal_tab = getattr(self.window, "tabCalendar", None)
            act_cal.setChecked(bool(cal_tab and curr_w == cal_tab))
            is_wl_open = getattr(self.window, "sidebar", None) and self.window.sidebar.isVisible()
            act_wl.setChecked(bool(is_wl_open))
            is_plan_open = getattr(self.window, "frameAIArea", None) and self.window.frameAIArea.isVisible()
            act_plan.setChecked(bool(is_plan_open))
            is_dock_open = not getattr(self.window, "is_dock_collapsed", False)
            act_blotter.setChecked(bool(is_dock_open))
            is_cur_d = getattr(self, "is_dark_theme", False)
            act_dark.setChecked(is_cur_d)
            act_light.setChecked(not is_cur_d)

        m_view.aboutToShow.connect(_sync_view_states)
        _sync_view_states()

        # -------------------------------------------------------------
        # 3. INSERT MENU
        # -------------------------------------------------------------
        m_insert = native_mb.addMenu("&Insert")
        m_insert.setStyleSheet(style_menu)
        self.menu_insert = m_insert

        sub_ind = m_insert.addMenu("Indicators")
        sub_ind.setStyleSheet(style_menu)
        act_cfg_ind = _reg_action(sub_ind, "Settings...", None, self._show_strategy_and_indicators_menu)
        sub_ind.addSeparator()
        act_vpoc = _reg_action(sub_ind, "Volume Profile", None, self._toggle_volume_profile)
        act_fvg = _reg_action(sub_ind, "Fair Value Gaps", None, lambda: self._set_drawing_tool("rectangle"))

        sub_draw = m_insert.addMenu("Objects")
        sub_draw.setStyleSheet(style_menu)
        act_cross = _reg_action(sub_draw, "Crosshair", "Ctrl+1", lambda: self._set_drawing_tool("crosshair"))
        act_trend = _reg_action(sub_draw, "Trendline", "Alt+T", lambda: self._set_drawing_tool("trendline"))
        act_rect = _reg_action(sub_draw, "Rectangle", "Alt+R", lambda: self._set_drawing_tool("rectangle"))
        act_ruler = _reg_action(sub_draw, "Ruler", "Shift+M", lambda: self._set_drawing_tool("ruler"))
        sub_draw.addSeparator()
        act_clear_draw = _reg_action(sub_draw, "Delete All", None, self._clear_all_drawings)

        # -------------------------------------------------------------
        # 4. CHARTS MENU
        # -------------------------------------------------------------
        m_charts = native_mb.addMenu("&Charts")
        m_charts.setStyleSheet(style_menu)
        self.menu_charts = m_charts

        act_bar = _reg_action(m_charts, "Bar Chart", "Alt+1", lambda: self._set_chart_type("bar"), checkable=True)
        act_candle = _reg_action(m_charts, "Candlesticks", "Alt+2", lambda: self._set_chart_type("candlestick"), checkable=True)
        act_line = _reg_action(m_charts, "Line Chart", "Alt+3", lambda: self._set_chart_type("line"), checkable=True)

        m_charts.addSeparator()

        sub_tf = m_charts.addMenu("Timeframes")
        sub_tf.setStyleSheet(style_menu)
        tf_list = ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN1"]
        self._tf_actions = {}
        for tf in tf_list:
            act_tf = sub_tf.addAction(tf)
            act_tf.setCheckable(True)
            def _make_tf_fn(target_tf=tf):
                return lambda: self._on_tf_click(target_tf) if hasattr(self, "_on_tf_click") else None
            act_tf.triggered.connect(_make_tf_fn())
            self._tf_actions[tf] = act_tf

        m_charts.addSeparator()

        act_zin = _reg_action(m_charts, "Zoom In", ["+", "="], self._zoom_in_chart)
        act_zout = _reg_action(m_charts, "Zoom Out", "-", self._zoom_out_chart)
        act_fit = _reg_action(m_charts, "Auto Range", "Ctrl+0", self._auto_fit_chart)
        act_grid = _reg_action(m_charts, "Grid", "Ctrl+G", self._toggle_grid, checkable=True)
        self._act_grid = act_grid
        act_ref = _reg_action(m_charts, "Refresh", "Ctrl+F5", self._refresh_chart_data)

        def _sync_charts_states():
            curr_mode = "candlestick"
            if hasattr(self.window, "candlesticks") and self.window.candlesticks:
                curr_mode = getattr(self.window.candlesticks, "chart_mode", "candlestick")
            act_bar.setChecked(curr_mode == "bar")
            act_candle.setChecked(curr_mode == "candlestick")
            act_line.setChecked(curr_mode == "line")

            curr_tf = getattr(self, "active_timeframe", "H1")
            for tf, act_tf in self._tf_actions.items():
                act_tf.setChecked(tf == curr_tf)

            act_grid.setChecked(getattr(self, "_grid_enabled", True))

        m_charts.aboutToShow.connect(_sync_charts_states)
        _sync_charts_states()

        # -------------------------------------------------------------
        # 5. TOOLS MENU
        # -------------------------------------------------------------
        m_tools = native_mb.addMenu("&Tools")
        m_tools.setStyleSheet(style_menu)
        self.menu_tools = m_tools

        act_order = _reg_action(m_tools, "New Order", "F9", self._open_new_order_ticket)
        act_strat = _reg_action(m_tools, "Strategy Manager...", "Ctrl+Shift+S", self._open_strategy_manager_dialog)
        m_tools.addAction(act_bt)
        act_kill = _reg_action(m_tools, "Close All Positions", "Ctrl+Shift+K", self._trigger_kill_switch)

        m_tools.addSeparator()
        act_tray = _reg_action(m_tools, "Minimize to Tray", "Ctrl+Shift+B", self._run_in_background)
        act_vps = _reg_action(m_tools, "Export VPS Config...", "Ctrl+Shift+E", self._export_vps_profile)

        m_tools.addSeparator()
        m_tools.addAction(act_journal)
        m_tools.addAction(act_cal)
        def _toggle_mt5_window():
            if mt5.is_mt5_window_visible():
                mt5.hide_mt5_window()
            else:
                mt5.show_mt5_window()

        act_mt5_win = _reg_action(m_tools, "Show/Hide MT5 Window", None, _toggle_mt5_window)
        act_opt = _reg_action(m_tools, "Options", "Ctrl+O", self._trigger_options)

        # -------------------------------------------------------------
        # 6. WINDOW MENU
        # -------------------------------------------------------------
        m_window = native_mb.addMenu("&Window")
        m_window.setStyleSheet(style_menu)
        self.menu_window = m_window

        act_layout = _reg_action(m_window, "Default Layout", None, self._reset_default_layout)
        act_focus = _reg_action(m_window, "Maximize Chart", "Shift+F11", self._toggle_focus_chart)
        m_window.addSeparator()
        m_window.addAction(act_fs)

        # -------------------------------------------------------------
        # 7. HELP MENU
        # -------------------------------------------------------------
        m_help = native_mb.addMenu("&Help")
        m_help.setStyleSheet(style_menu)
        self.menu_help = m_help

        act_cheat = _reg_action(m_help, "Help Topics", "Ctrl+/", self._show_shortcuts_cheat_sheet)
        act_diag = _reg_action(m_help, "Connection Diagnostics", None, self._show_diagnostics_dialog)
        m_help.addSeparator()
        def _on_about():
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self.window,
                "About VECTRA",
                "VECTRA Quantitative Trading OS v2.2\nArchitecture: MetaTrader 5 / Institutional ECN\nStrategy: ICT Zones Pro v4.2 / Market Profile vPOC\nBuilt for professional prop & multi-asset desks."
            )
        act_about = _reg_action(m_help, "About...", None, _on_about)

        # Bot Algo Toggle (F5)
        act_f5 = _reg_action(None, "Toggle Algo Bot", "F5", lambda: self.terminal._toggle_bot() if hasattr(self.terminal, "_toggle_bot") else None)

        # Expose all canonical actions to controller instance for backward compatibility
        self.act_term = act_term
        self.act_stats = act_stats
        self.act_bt = act_bt
        self.act_cal = act_cal
        self.act_wl = act_wl
        self.act_plan = act_plan
        self.act_blotter = act_blotter
        self.act_journal = act_journal
        self.act_fs = act_fs
        self.act_sym = act_sym
        self.act_save = act_save
        self.act_order = act_order
        self.act_strat = act_strat
        self.act_kill = act_kill
        self.act_opt = act_opt
        self.act_bar = act_bar
        self.act_candle = act_candle
        self.act_line = act_line
        self.act_zin = act_zin
        self.act_zout = act_zout
        self.act_fit = act_fit
        self.act_grid = act_grid
        self.act_ref = act_ref
        self.act_cross = act_cross
        self.act_trend = act_trend
        self.act_rect = act_rect
        self.act_ruler = act_ruler
        self.act_focus = act_focus
        self.act_cheat = act_cheat
        self.act_f5 = act_f5

        # Canonical aliases for legacy shortcut references (preserving 100% backward compatibility)
        self.shortcut_f1 = act_term
        self.shortcut_f2 = act_stats
        self.shortcut_ctrl_r = act_bt
        self.shortcut_f3 = act_cal
        self.shortcut_f5 = act_f5
        self.shortcut_f9 = act_order
        self.shortcut_ctrl_l = act_journal
        self.shortcut_ctrl_o = act_opt
        self.shortcut_ctrl_m = act_wl
        self.shortcut_ctrl_t = act_plan
        self.shortcut_ctrl_b = act_blotter
        self.shortcut_ctrl_n = act_sym
        self.shortcut_ctrl_s = act_save
        self.shortcut_ctrl_shift_s = act_strat
        self.shortcut_ctrl_shift_k = act_kill
        self.shortcut_alt_1 = act_bar
        self.shortcut_alt_2 = act_candle
        self.shortcut_alt_3 = act_line
        self.shortcut_ctrl_0 = act_fit
        self.shortcut_ctrl_g = act_grid
        self.shortcut_ctrl_slash = act_cheat
        self.shortcut_shift_f11 = act_focus
        self.shortcut_f11 = act_fs

        # Maintain aliases for legacy compatibility
        self.btnMenuFile = self.menu_file
        self.btn_menu_file = self.menu_file
        self.btnMenuView = self.menu_view
        self.btn_menu_view = self.menu_view
        self.btnMenuInsert = self.menu_insert
        self.btn_menu_insert = self.menu_insert
        self.btnMenuCharts = self.menu_charts
        self.btn_menu_charts = self.menu_charts
        self.btnMenuTools = self.menu_tools
        self.btn_menu_tools = self.menu_tools
        self.btnMenuWindow = self.menu_window
        self.btn_menu_window = self.menu_window
        self.btnMenuHelp = self.menu_help
        self.btn_menu_help = self.menu_help

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

        is_dark = getattr(self, "is_dark_theme", False)

        # 0. TOP MENU BAR (26px) - Authentic MT5 Menu Bar
        menu_bar = QFrame()
        menu_bar.setObjectName("topMenuBar")
        menu_bar.setFixedHeight(26)
        bg_m = "#060910" if is_dark else "#f8fafc"
        border_m = "#1e222d" if is_dark else "#cbd5e1"
        menu_bar.setStyleSheet(f"QFrame#topMenuBar {{ background-color: {bg_m}; border-bottom: 1px solid {border_m}; }}")
        self.menu_bar = menu_bar

        m_layout = QHBoxLayout(menu_bar)
        m_layout.setContentsMargins(6, 0, 6, 0)
        m_layout.setSpacing(1)

        # Native QMenuBar matching MT5 Desktop exactly
        native_mb = QMenuBar()
        native_mb.setObjectName("nativeMenuBar")
        native_mb.setFocusPolicy(Qt.NoFocus)
        self.native_menu_bar = native_mb
        self._apply_native_menu_bar_theme(is_dark)

        # Build 7 Authentic Menus on native_mb
        self._setup_native_mt5_menus(native_mb, is_dark)
        m_layout.addWidget(native_mb)

        m_layout.addStretch()

        header_container = QFrame()
        header_container.setObjectName("topHeaderContainer")
        header_container.setFixedHeight(26)
        header_container.setStyleSheet(f"QFrame#topHeaderContainer {{ background-color: {'#0a0c10' if is_dark else '#ffffff'}; border-bottom: 1px solid {'#1e222d' if is_dark else '#cbd5e1'}; }}")
        self.header_container = header_container

        h_layout = QHBoxLayout(header_container)
        h_layout.setContentsMargins(10, 0, 10, 0)
        h_layout.setSpacing(8)
        h_layout.setAlignment(Qt.AlignVCenter)

        is_dark = getattr(self, "is_dark_theme", False)
        sep_col = "#272d3b" if is_dark else "#cbd5e1"

        # =========================================================================
        # 3-ZONE INSTITUTIONAL RIBBON ARCHITECTURE (SINGLE UNBROKEN ROW)
        # Zone 1 (Left):   Chart Controls (Symbol Dropdown + M1..MN1 Fixed Strip)
        # Zone 2 (Center): Semi-Auto Controls (ALGO Pill + Strategy Badge + Event Risk)
        # Zone 3 (Right):  Account Telemetry (BAL | EQ | P&L) + Window Controls
        # =========================================================================

        # --- ZONE 1: CHART CONTROLS ---
        zone_chart = QWidget()
        zone_chart.setFixedHeight(22)
        z1_layout = QHBoxLayout(zone_chart)
        z1_layout.setContentsMargins(0, 0, 0, 0)
        z1_layout.setSpacing(6)
        z1_layout.setAlignment(Qt.AlignVCenter)

        # 1. Symbol Button: Clean Symbol Only (No 'Gold vs US Dollar' clutter, no '▼' icon)
        # Interactive institutional quick asset picker connecting directly to Watchlist
        self.lbl_top_sym = QPushButton()
        self.lbl_top_sym.setObjectName("lblTopSymbol")
        self.lbl_top_sym.setFixedHeight(20)
        self.lbl_top_sym.setCursor(Qt.PointingHandCursor)
        self.lbl_top_sym.clicked.connect(self._show_symbol_quick_picker)

        # Fast wheel cycling through watchlist symbols
        def _on_sym_wheel(event):
            symbols = self._get_watchlist_symbols()
            if not symbols:
                return
            curr = getattr(self.window, "current_sym", "XAUUSD").split("\n")[0].strip()
            try:
                idx = symbols.index(curr)
            except ValueError:
                idx = 0
            delta = event.angleDelta().y()
            if delta > 0:
                new_idx = (idx - 1) % len(symbols)
            else:
                new_idx = (idx + 1) % len(symbols)
            new_sym = symbols[new_idx]
            if new_sym != curr:
                self._switch_symbol(new_sym)

        self.lbl_top_sym.wheelEvent = _on_sym_wheel
        z1_layout.addWidget(self.lbl_top_sym, 0, Qt.AlignVCenter)
        self._refresh_top_ticker()

        # Separator 1: Between Symbol and Timeframes
        sep1 = self._create_v_separator(is_dark)
        z1_layout.addWidget(sep1, 0, Qt.AlignVCenter)

        # 2. Timeframe Discrete Buttons Strip (Fixed 26px x 20px uniform dimensions)
        tf_bar = QWidget()
        tf_bar.setFixedHeight(20)
        tf_layout = QHBoxLayout(tf_bar)
        tf_layout.setContentsMargins(0, 0, 0, 0)
        tf_layout.setSpacing(2)
        tf_layout.setAlignment(Qt.AlignVCenter)

        self.tf_buttons = {}
        tf_map = {
            "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1, "W1": getattr(mt5, "TIMEFRAME_W1", 32769),
            "MN1": getattr(mt5, "TIMEFRAME_MN1", 49153)
        }

        self.active_timeframe = "H1"
        def _on_tf_click(tf_k):
            self.active_timeframe = tf_k
            self._update_tf_button_styles()
            if hasattr(self.window, "change_timeframe"):
                self.window.change_timeframe(tf_map.get(tf_k, mt5.TIMEFRAME_H1), tf_k)

        for tf_name in ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN1"]:
            btn_tf = QPushButton(tf_name)
            btn_tf.setObjectName(f"btnTopTf_{tf_name}")
            btn_tf.setFixedSize(26, 20)
            btn_tf.setCursor(Qt.PointingHandCursor)
            btn_tf.clicked.connect(lambda chk=False, k=tf_name: _on_tf_click(k))
            tf_layout.addWidget(btn_tf, 0, Qt.AlignVCenter)
            self.tf_buttons[tf_name] = btn_tf

        self._update_tf_button_styles(is_dark)
        self.window.update_tf_styles = self._update_tf_button_styles
        z1_layout.addWidget(tf_bar, 0, Qt.AlignVCenter)

        self.chart_context_bar = zone_chart
        h_layout.addWidget(zone_chart, 0, Qt.AlignVCenter)

        # Separator: Zone 1 (MN1) -> Zone 2 (Algo Control Pill)
        sep_chart_algo = self._create_v_separator(is_dark)
        self.sep_chart_algo = sep_chart_algo
        h_layout.addWidget(sep_chart_algo, 0, Qt.AlignVCenter)

        # --- ZONE 2: SEMI-AUTO SYSTEM CONTROLS (DIRECTLY ADJACENT, ZERO BLACK HOLE GAP) ---
        zone_algo = QWidget()
        zone_algo.setFixedHeight(22)
        z2_layout = QHBoxLayout(zone_algo)
        z2_layout.setContentsMargins(0, 0, 0, 0)
        z2_layout.setSpacing(6)
        z2_layout.setAlignment(Qt.AlignVCenter)

        # 1. ALGO State & Control Pill (Placed FIRST for maximum operational visibility)
        btn_algo = AlgoControlPill(is_running=False, is_dark=is_dark)
        btn_algo.setObjectName("btnAlgoTrading")
        btn_algo.setFixedHeight(20)
        btn_algo.clicked.connect(lambda: self.terminal._toggle_bot())
        self.btn_algo_toggle = btn_algo
        self.window.btn_algo_toggle = btn_algo
        z2_layout.addWidget(btn_algo, 0, Qt.AlignVCenter)

        # Separator: ALGO Pill -> Strategy Badge
        sep_algo_strat = self._create_v_separator(is_dark)
        z2_layout.addWidget(sep_algo_strat, 0, Qt.AlignVCenter)

        # 2. Dynamic Strategy Badge (Clean Segoe UI typography, 20px uniform height)
        btn_ind = QPushButton()
        btn_ind.setObjectName("btnTopIndicator")
        btn_ind.setFixedHeight(20)
        btn_ind.setCursor(Qt.PointingHandCursor)
        btn_ind.setToolTip("Configure Quantitative Strategy or Indicator Stack")
        ind_col = "#38bdf8" if is_dark else "#0284c7"
        border_col = "transparent"
        hover_bg = "#141721" if is_dark else "#f1f5f9"
        hover_col = "#38bdf8" if is_dark else "#0f172a"
        hover_border = "#272d3b" if is_dark else "#cbd5e1"
        btn_ind.setStyleSheet(
            f"QPushButton#btnTopIndicator {{ background-color: transparent; color: {ind_col}; border: 1px solid {border_col}; "
            f"border-radius: 2px; padding: 0 6px; margin: 0px; font-family: Consolas, monospace; font-size: 10px; font-weight: 600; "
            f"}} "
            f"QPushButton#btnTopIndicator:hover {{ color: {hover_col}; border: 1px solid {hover_border}; background-color: {hover_bg}; }} "
            f"QPushButton#btnTopIndicator:pressed {{ background-color: {'#0c1a2e' if is_dark else '#e2e8f0'}; }}"
        )
        self.btn_top_ind = btn_ind
        self.window.btn_top_ind = btn_ind
        self.window.update_strategy_badge = self.update_strategy_badge
        self.update_strategy_badge()
        btn_ind.clicked.connect(self._show_strategy_and_indicators_menu)
        z2_layout.addWidget(btn_ind, 0, Qt.AlignVCenter)

        # Separator: Strategy Badge -> Event Risk Badge
        sep_strat_event = self._create_v_separator(is_dark)
        z2_layout.addWidget(sep_strat_event, 0, Qt.AlignVCenter)

        # 3. Live Event Risk Badge (Flat Ghost Label when CLEAR, Red Alert Box when IMPACT)
        btn_event_risk = QPushButton("EVENT: CLEAR")
        btn_event_risk.setObjectName("btnEventRiskBadge")
        btn_event_risk.setFixedHeight(20)
        btn_event_risk.setCursor(Qt.PointingHandCursor)
        if is_dark:
            event_bg = "transparent"
            event_col = "#4ade80"
            event_border = "transparent"
            event_h_bg = "#064e3b"
            event_h_col = "#6ee7b7"
            event_h_border = "#059669"
        else:
            event_bg = "transparent"
            event_col = "#15803d"
            event_border = "transparent"
            event_h_bg = "#f0fdf4"
            event_h_col = "#166534"
            event_h_border = "#bbf7d0"

        btn_event_risk.setStyleSheet(
            f"QPushButton#btnEventRiskBadge {{ "
            f"  background-color: {event_bg}; "
            f"  color: {event_col}; "
            f"  border: 1px solid {event_border}; "
            f"  border-radius: 2px; "
            f"  padding: 0 6px; "
            f"  margin: 0px; "
            f"  font-family: Consolas, monospace; "
            f"  font-size: 10px; "
            f"  font-weight: 700; "
            f"}} "
            f"QPushButton#btnEventRiskBadge:hover {{ "
            f"  background-color: {event_h_bg}; "
            f"  color: {event_h_col}; "
            f"  border: 1px solid {event_h_border}; "
            f"}}"
        )
        def _jump_to_calendar(chk=False):
            if hasattr(self.terminal, "nav") and hasattr(self.window, "tabCalendar"):
                btn_cal = getattr(self, "btnNavCalendar", None)
                self.terminal.nav._switch_nav_tab(self.window.tabCalendar, btn_cal, "Calendar")
        btn_event_risk.clicked.connect(_jump_to_calendar)
        self.btn_event_risk = btn_event_risk
        self.window.btn_event_risk = btn_event_risk
        z2_layout.addWidget(btn_event_risk, 0, Qt.AlignVCenter)

        self.zone_algo = zone_algo
        h_layout.addWidget(zone_algo, 0, Qt.AlignVCenter)

        # Synchronize visibility of both Zone 1 & 2 when navigating away from Terminal
        orig_set_visible = zone_chart.setVisible
        def _chart_ctx_set_visible(v):
            orig_set_visible(v)
            if hasattr(self, "zone_algo") and self.zone_algo:
                self.zone_algo.setVisible(v)
            if hasattr(self, "sep_chart_algo") and self.sep_chart_algo:
                self.sep_chart_algo.setVisible(v)
        zone_chart.setVisible = _chart_ctx_set_visible

        # Dedicated Non-Terminal Workspace Branding (Shown on Stats, Backtest, Logs)
        self.lbl_header_app_title = QLabel("VECTRA TERMINAL v2.2")
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

        self.btn_top_wl = None
        self.window.btn_top_wl = None
        self.btn_top_ticket = None
        self.window.btn_top_ticket = None
        self.window._update_panel_toggle_styles = self._update_panel_toggle_styles

        # SINGLE UNIFIED STRETCH: Anchors all operational tools together on left, pushing Account Telemetry to right
        h_layout.addStretch(1)

        # --- ZONE 3: RIGHT-DOCKED ACCOUNT TELEMETRY ---
        zone_acct = QWidget()
        zone_acct.setFixedHeight(22)
        z3_layout = QHBoxLayout(zone_acct)
        z3_layout.setContentsMargins(0, 0, 0, 0)
        z3_layout.setSpacing(6)
        z3_layout.setAlignment(Qt.AlignVCenter)

        self.lbl_top_ticker = QLabel()
        self.lbl_top_ticker.setObjectName("lblTopTicker")
        self.lbl_top_ticker.setTextFormat(Qt.RichText)
        self.lbl_top_ticker.setFixedHeight(20)
        self.lbl_top_ticker.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        self.lbl_top_ticker.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.lbl_top_ticker.setStyleSheet(
            "background: transparent; border: none; padding: 0 4px; margin: 0px;"
        )
        self.lbl_top_ticker.setText(self._format_top_ticker(is_dark=is_dark))
        z3_layout.addWidget(self.lbl_top_ticker, 0, Qt.AlignVCenter)
        h_layout.addWidget(zone_acct, 0, Qt.AlignVCenter)

        self.top_separators = [sep1, sep_chart_algo, sep_algo_strat, sep_strat_event]

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

        self._is_maximized = self.window.isMaximized()
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
            if self.window.isMaximized():
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

        m_layout.addWidget(win_controls)

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
        menu_bar.mousePressEvent = mouse_press
        menu_bar.mouseMoveEvent = mouse_move
        menu_bar.mouseReleaseEvent = mouse_release

        # BOTTOM BAR (22px): Clean Status Bar - old bulky tabs removed, telemetry kept
        bottom_bar = QFrame()
        bottom_bar.setObjectName("bottomTabBar")
        bottom_bar.setFixedHeight(22)
        bg = "#090d16" if is_dark else "#f8fafc"
        border = "#1e222d" if is_dark else "#e2e8f0"
        bottom_bar.setStyleSheet(f"QFrame#bottomTabBar {{ background-color: {bg}; border-top: 1px solid {border}; }}")
        self.bottom_bar = bottom_bar

        b_layout = QHBoxLayout(bottom_bar)
        b_layout.setContentsMargins(10, 0, 10, 0)
        b_layout.setSpacing(4)

        # Tab buttons retained in memory for full compatibility, but hidden from bottom bar
        self.nav_buttons = []
        tabs_spec = [
            ("btnNavTerminal", "Terminal", self.window.tab2, "Terminal"),
            ("btnNavStats", "Performance", self.window.tab3, "Performance"),
            ("btnNavBacktest", "Backtest", self.window.tab_5, "Backtest"),
            ("btnNavCalendar", "Calendar", getattr(self.window, "tabCalendar", None), "Calendar"),
        ]

        for obj_name, label_text, target_tab, full_title in tabs_spec:
            btn = QPushButton(label_text)
            btn.setObjectName(obj_name)
            btn.setFixedHeight(22)
            btn.setVisible(False)
            def _make_nav_handler(target_tab, btn_obj, tab_title):
                def _handler(checked=False):
                    self._switch_nav_tab(target_tab, btn_obj, tab_title)
                return _handler

            btn.clicked.connect(_make_nav_handler(target_tab, btn, full_title))
            self.nav_buttons.append((btn, target_tab, full_title))
            setattr(self, obj_name, btn)

        lbl_status_tip = QLabel("For Help, press F1")
        lbl_status_tip.setObjectName("lblStatusTip")
        lbl_status_tip.setStyleSheet(f"color: {'#64748b' if is_dark else '#94a3b8'}; font-size: 10px; font-family: 'Segoe UI', sans-serif;")
        b_layout.addWidget(lbl_status_tip)

        if hasattr(self.terminal, "nav"):
            self.terminal.nav.nav_buttons = self.nav_buttons

        # Compatibility handle for Settings/Options trigger without polluting bottom tabs bar
        btn_settings = QPushButton("OPTIONS")
        btn_settings.setObjectName("btnNavSettings")
        btn_settings.setVisible(False)
        def _open_options(checked=False):
            settings_mgr = (
                getattr(self, "settings", None)
                or getattr(self.terminal, "settings", None)
                or getattr(self.window, "settings_mgr", None)
            )
            if settings_mgr and hasattr(settings_mgr, "open_options_dialog"):
                settings_mgr.open_options_dialog()
            else:
                from frontend.widgets.options_dialog import OptionsDialog
                dlg = OptionsDialog(self.window)
                dlg.load_data()
                dlg.show()
                dlg.raise_()
                dlg.activateWindow()
        btn_settings.clicked.connect(_open_options)
        setattr(self, "btnNavSettings", btn_settings)

        self.sep_bottom_nav = None
        self.lbl_bottom_mid = None

        # Spacer pushes all telemetry to the far right
        b_layout.addStretch()

        # Flat Journal text trigger (Ctrl+L) - No Box Border
        btn_audit = QPushButton("JOURNAL")
        btn_audit.setObjectName("btnBottomAudit")
        btn_audit.setFixedHeight(22)
        btn_audit.setCursor(Qt.PointingHandCursor)
        btn_audit.setToolTip("System Journal (Ctrl+L)")
        audit_col = "#94a3b8" if is_dark else "#64748b"
        audit_h_col = "#38bdf8" if is_dark else "#0284c7"
        btn_audit.setStyleSheet(
            f"QPushButton#btnBottomAudit {{ background: transparent; color: {audit_col}; border: none; "
            f"font-family: 'Segoe UI', sans-serif; font-size: 11px; font-weight: 600; padding: 0 4px; min-height: 22px; max-height: 22px; }} "
            f"QPushButton#btnBottomAudit:hover {{ background: transparent; color: {audit_h_col}; }}"
        )
        def _open_audit_journal(checked=False):
            logs_mgr = (
                getattr(self, "logs", None)
                or getattr(self.terminal, "logs", None)
                or getattr(self.window, "logs", None)
            )
            if logs_mgr and hasattr(logs_mgr, "toggle_audit_dialog"):
                logs_mgr.toggle_audit_dialog()
            elif logs_mgr and hasattr(logs_mgr, "open_audit_dialog"):
                logs_mgr.open_audit_dialog()
            else:
                from frontend.widgets.audit_log_dialog import AuditLogDialog
                log_w = getattr(self.window, "tab4", None)
                if log_w:
                    log_w.setVisible(True)
                    log_w.show()
                dlg = AuditLogDialog(
                    parent=self.window,
                    log_widget=log_w,
                    log_manager=logs_mgr,
                    is_dark=getattr(self, "is_dark_theme", False)
                )
                dlg.open_dialog()
        btn_audit.clicked.connect(_open_audit_journal)
        self.btn_bottom_audit = btn_audit
        b_layout.addWidget(btn_audit)

        b_layout.addSpacing(4)
        sep_bot_audit = QFrame()
        sep_bot_audit.setFixedWidth(1)
        sep_bot_audit.setFixedHeight(12)
        sep_bot_audit.setStyleSheet(f"background-color: {'#334155' if is_dark else '#cbd5e1'};")
        self.sep_bottom_audit = sep_bot_audit
        b_layout.addWidget(sep_bot_audit)
        b_layout.addSpacing(4)

        # Right: Consolidated status strip: FULL-ALGO | ● MT5: 1.2ms | 0% LOSS
        lbl_bot_status = QLabel()
        lbl_bot_status.setObjectName("lblBottomTelemetry")
        lbl_bot_status.setFixedHeight(30)
        lbl_bot_status.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        lbl_bot_status.setText(self._format_bottom_telemetry(is_dark))
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
        master_layout.addWidget(menu_bar, 0)
        master_layout.addWidget(header_container, 0)
        master_layout.addWidget(self.window.mainSplitter, 1)
        master_layout.addWidget(bottom_bar, 0)
        self.window.setCentralWidget(master)
        if hasattr(self.window, "mainSplitter"):
            total_w = max(400, self.window.mainSplitter.width() or 1440)
            sidebar_w = 260
            self.window.mainSplitter.setSizes([sidebar_w, max(100, total_w - sidebar_w)])


    def _update_event_risk_badge(self, symbol=None):
        """Updates live event risk ticker badge for active asset using flat color contrast (no box border)."""
        if not hasattr(self, "btn_event_risk") or not self.btn_event_risk:
            return

        is_dark = getattr(self, "is_dark_theme", False)

        if not symbol:
            symbol = getattr(self.window, "current_sym", "XAUUSD")
        clean_sym = symbol.split("\n")[0].split(".")[0].strip().upper()

        ere = getattr(self.window, "_event_risk_engine", None)
        if not ere:
            try:
                from backend.core.event_risk_engine import EventRiskEngine
                ere = EventRiskEngine()
                self.window._event_risk_engine = ere
            except Exception:
                return

        try:
            is_impacted, news_title = ere.check_news_impact_for_symbol(clean_sym)
            if is_impacted:
                self.btn_event_risk.setText(f"EVENT: {news_title[:12].upper()}")
                if is_dark:
                    bg_col = "#450a0a"
                    text_col = "#f87171"
                    border_col = "#991b1b"
                    hover_bg = "#5b1010"
                    hover_col = "#fca5a5"
                    hover_border = "#dc2626"
                else:
                    bg_col = "#fee2e2"
                    text_col = "#b91c1c"
                    border_col = "#fca5a5"
                    hover_bg = "#fecaca"
                    hover_col = "#991b1b"
                    hover_border = "#ef4444"
                self.btn_event_risk.setToolTip(f"High-impact news event active: {news_title}\nTrading pause active. Click to view Macro Calendar.")
            else:
                self.btn_event_risk.setText("EVENT: CLEAR")
                if is_dark:
                    bg_col = "transparent"
                    text_col = "#4ade80"
                    border_col = "transparent"
                    hover_bg = "#064e3b"
                    hover_col = "#6ee7b7"
                    hover_border = "#059669"
                else:
                    bg_col = "transparent"
                    text_col = "#15803d"
                    border_col = "transparent"
                    hover_bg = "#f0fdf4"
                    hover_col = "#166534"
                    hover_border = "#bbf7d0"
                self.btn_event_risk.setToolTip(f"No active news blackout for {clean_sym}.\nClick to view Macro Calendar.")

            self.btn_event_risk.setStyleSheet(
                f"QPushButton#btnEventRiskBadge {{ "
                f"  background-color: {bg_col}; "
                f"  color: {text_col}; "
                f"  border: 1px solid {border_col}; "
                f"  border-radius: 2px; "
                f"  padding: 0 6px; "
                f"  margin: 0px; "
                f"  font-family: Consolas, monospace; "
                f"  font-size: 10px; "
                f"  font-weight: 700; "
                f"}} "
                f"QPushButton#btnEventRiskBadge:hover {{ "
                f"  background-color: {hover_bg}; "
                f"  color: {hover_col}; "
                f"  border: 1px solid {hover_border}; "
                f"}}"
            )
        except Exception:
            pass


# Backward compatibility alias
HeaderController = WorkspaceHeaderController
