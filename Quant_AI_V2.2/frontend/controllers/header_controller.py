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

    def _format_top_ticker(self, bal=None, eq=None, pnl=None, pnl_pct=0.0, max_dd=0.0, latency=None, is_algo_active=False, is_dark=None):
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

        return (
            f'<span style="color:{lbl_col}; font-size:9.5px; font-family:Consolas, monospace;">'
            f'BALANCE: <b style="color:{val_col};">{bal_txt}</b>&nbsp;&nbsp;<span style="color:{sep_col};">|</span>&nbsp;&nbsp;'
            f'EQUITY: <b style="color:{val_col};">{eq_txt}</b>&nbsp;&nbsp;<span style="color:{sep_col};">|</span>&nbsp;&nbsp;'
            f'NET P&L: <b style="color:{pnl_color};">{pnl_txt}</b>'
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
            sub_title = None
            try:
                s_info = mt5.symbol_info(clean_sym)
                if s_info and getattr(s_info, "description", None):
                    sub_title = s_info.description.strip()
            except Exception:
                pass

            if not sub_title:
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
            badge_text = "Wyckoff · Momentum Pro v2.2"
        elif "ema" in strat_lower:
            badge_text = "EMA · Dual Cross Benchmark"
        elif "ict" in strat_lower:
            badge_text = "ICT / SMC · Confluence Pro v4.2"
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
            bg = "#0a0c10" if is_dark else "#f1f5f9"
            border = "#1e222d" if is_dark else "#cbd5e1"
            self.header_container.setStyleSheet(
                f"QFrame#topHeaderContainer {{ background-color: {bg}; border-bottom: 1px solid {border}; }}"
            )

        # 2. Bottom Tab Bar (Height: 30px)
        if hasattr(self, "bottom_bar") and self.bottom_bar:
            bg = "#090d16" if is_dark else "#ffffff"
            border = "#1e222d" if is_dark else "#cbd5e1"
            self.bottom_bar.setFixedHeight(30)
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

        # 10. Bottom Session Indicator (merged into right-side telemetry cluster)
        if hasattr(self, "lbl_bottom_mid") and self.lbl_bottom_mid:
            self.lbl_bottom_mid.setVisible(False)
        if hasattr(self, "sep_bottom_nav") and self.sep_bottom_nav:
            self.sep_bottom_nav.setVisible(False)

        # 11. Consolidated Bottom Telemetry: FULL-ALGO | ● MT5: 1.2ms | 0% LOSS
        if hasattr(self, "lbl_bot_status") and self.lbl_bot_status:
            self.lbl_bot_status.setFixedHeight(30)
            self.lbl_bot_status.setText(self._format_bottom_telemetry(is_dark))

        # 12. Bottom Audit Log Button (Ctrl+L trigger)
        if hasattr(self, "btn_bottom_audit") and self.btn_bottom_audit:
            if is_dark:
                self.btn_bottom_audit.setStyleSheet(
                    "QPushButton#btnBottomAudit { background-color: #0d121f; color: #94a3b8; border: 1px solid #1e293b; "
                    "font-family: 'Segoe UI', sans-serif; font-size: 11px; font-weight: 600; border-radius: 2px; padding: 0 8px; min-height: 22px; max-height: 22px; } "
                    "QPushButton#btnBottomAudit:hover { background-color: #1e293b; color: #38bdf8; border-color: #38bdf8; }"
                )
            else:
                self.btn_bottom_audit.setStyleSheet(
                    "QPushButton#btnBottomAudit { background-color: #ffffff; color: #475569; border: 1px solid #cbd5e1; "
                    "font-family: 'Segoe UI', sans-serif; font-size: 11px; font-weight: 600; border-radius: 2px; padding: 0 8px; min-height: 22px; max-height: 22px; } "
                    "QPushButton#btnBottomAudit:hover { background-color: #f1f5f9; color: #0284c7; border-color: #0284c7; }"
                )

        # 13. Sync Bottom Navigation Tab Buttons Styling
        if hasattr(self, "_update_nav_buttons_style"):
            self._update_nav_buttons_style(is_dark)



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
            btn_tf.setFixedSize(28, 20)
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

        # 3. Dynamic Strategy & Indicator Badge
        btn_ind = QPushButton()
        btn_ind.setObjectName("btnTopIndicator")
        btn_ind.setFixedHeight(24)
        btn_ind.setCursor(Qt.PointingHandCursor)
        btn_ind.setToolTip("Configure Quantitative Strategy or Indicator Stack")
        ind_bg = "transparent"
        ind_col = "#94a3b8" if is_dark else "#334155"
        hover_bg = "#1e293b" if is_dark else "#ffffff"
        hover_col = "#f8fafc" if is_dark else "#0f172a"
        hover_border = "#475569" if is_dark else "#cbd5e1"
        btn_ind.setStyleSheet(
            f"QPushButton#btnTopIndicator {{ background-color: {ind_bg}; color: {ind_col}; border: 1px solid transparent; "
            f"border-radius: 3px; padding: 0 8px; font-family: Consolas, monospace; font-size: 9px; font-weight: bold; "
            f"min-height: 24px; max-height: 24px; }} "
            f"QPushButton#btnTopIndicator:hover {{ color: {hover_col}; border: 1px solid {hover_border}; background-color: {hover_bg}; }} "
            f"QPushButton#btnTopIndicator:pressed {{ background-color: {'#0f172a' if is_dark else '#e2e8f0'}; }}"
        )
        self.btn_top_ind = btn_ind
        self.window.btn_top_ind = btn_ind
        self.window.update_strategy_badge = self.update_strategy_badge
        self.update_strategy_badge()
        btn_ind.clicked.connect(self._show_strategy_and_indicators_menu)
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
                screen = self.window.screen()
                if screen:
                    avail = screen.availableGeometry()
                    self.window.setMaximumSize(avail.width(), avail.height())
                    self.window.setGeometry(avail)
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

        # BOTTOM BAR (30px): 3 Workspaces on Left, Consolidated Telemetry on Right
        bottom_bar = QFrame()
        bottom_bar.setObjectName("bottomTabBar")
        bottom_bar.setFixedHeight(30)
        bg = "#090d16" if is_dark else "#ffffff"
        border = "#1e222d" if is_dark else "#cbd5e1"
        bottom_bar.setStyleSheet(f"QFrame#bottomTabBar {{ background-color: {bg}; border-top: 1px solid {border}; }}")
        self.bottom_bar = bottom_bar

        b_layout = QHBoxLayout(bottom_bar)
        b_layout.setContentsMargins(10, 0, 10, 0)
        b_layout.setSpacing(2)

        # 3 Core Workspaces on Left: Terminal · Performance · Backtest (MT5 Toolbox / VS style)
        self.nav_buttons = []
        tabs_spec = [
            ("btnNavTerminal", "Terminal", self.window.tab2, "Terminal"),
            ("btnNavStats", "Performance", self.window.tab3, "Performance"),
            ("btnNavBacktest", "Backtest", self.window.tab_5, "Backtest"),
        ]

        for obj_name, label_text, target_tab, full_title in tabs_spec:
            btn = QPushButton(label_text)
            btn.setObjectName(obj_name)
            btn.setFixedHeight(30)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setCheckable(True)
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

        # Clickable Journal Pill (Ctrl+L)
        btn_audit = QPushButton("JOURNAL")
        btn_audit.setObjectName("btnBottomAudit")
        btn_audit.setFixedHeight(22)
        btn_audit.setCursor(Qt.PointingHandCursor)
        btn_audit.setToolTip("System Journal (Ctrl+L)")
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
        master_layout.addWidget(header_container, 0)
        master_layout.addWidget(self.window.mainSplitter, 1)
        master_layout.addWidget(bottom_bar, 0)
        self.window.setCentralWidget(master)
        if hasattr(self.window, "mainSplitter"):
            total_w = max(400, self.window.mainSplitter.width() or 1440)
            sidebar_w = 260
            self.window.mainSplitter.setSizes([sidebar_w, max(100, total_w - sidebar_w)])

# Backward compatibility alias
HeaderController = WorkspaceHeaderController
