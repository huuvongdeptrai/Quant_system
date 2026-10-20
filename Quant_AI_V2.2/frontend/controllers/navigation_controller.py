"""
Navigation Controller for Quant_AI V2.2
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
from frontend.widgets.bot_power_button import BotPowerButton

class NavigationController:
    """Manages workspace navigation rail, tab routing, and overlay controls."""

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

    def _setup_navigation_rail(self):
        """Setup internal micro toggles, connection dot, and algo engine power button.
        The left rail itself is eliminated from layout to achieve x = 0 pure canvas.
        """
        self.nav_rail = QFrame()
        self.nav_rail.setObjectName("leftSidebar")
        self.nav_rail.setVisible(False)

        self.nav_buttons = []

        # Middle Zone: Monospace micro shortcuts (CPL, VA, POC, CPR, Δ)
        self.micro_toggles = {}
        toggles_info = [
            ("CPL", "Candle Profile / Bars", self._toggle_candles),
            ("VA", "Value Area 70% Overlay", self._toggle_value_area),
            ("POC", "Point of Control (tPOC/vPOC)", self._toggle_poc),
            ("CPR", "Central Pivot Range", self._toggle_cpr),
            ("Δ", "Cumulative Delta Kim", self._toggle_delta),
        ]
        for key, name, callback in toggles_info:
            t_btn = QPushButton(key)
            t_btn.setFixedHeight(18)
            t_btn.setCheckable(True)
            t_btn.setChecked(True)
            t_btn.setObjectName(f"btnMicroToggle_{key}")
            t_btn.setProperty("class", "micro_toggle")
            t_btn.setToolTip(f"TOGGLE: {name}")
            t_btn.setStyleSheet(
                "QPushButton { background-color: #0c0c0c; color: #888888; border: 1px solid #1c1c1c; "
                "font-family: 'Consolas', monospace; font-size: 8.5px; font-weight: bold; padding: 0 4px; } "
                "QPushButton:checked { background-color: #1a1a1a; color: #ffffff; border-color: #333333; } "
                "QPushButton:hover { color: #cccccc; }"
            )
            t_btn.clicked.connect(callback)
            self.micro_toggles[key] = t_btn

        # Bottom Zone: Connection Dot + Engine Power Button
        self.dot_mt5 = QFrame()
        self.dot_mt5.setObjectName("dotMT5")
        self.dot_mt5.setFixedSize(6, 6)
        self.dot_mt5.setStyleSheet("background-color: #ef4444; border-radius: 3px;")
        self.dot_mt5.setToolTip("FEED: DISCONNECTED")

        # Bot Engine Power Button - 20x20
        self.btn_bot_power = BotPowerButton(is_running=False)
        self.btn_bot_power.setObjectName("btnBotPower")
        self.btn_bot_power.setFixedSize(20, 20)
        self.btn_bot_power.power_toggled.connect(self._on_bot_power_toggled)

        # Hide native tabBar; tabs are hosted in bottom navigation bar
        self.window.tabWidget.tabBar().setVisible(False)

        # Remove orphaned legacy Settings tab (tab1) from tabWidget
        # Settings is purely an MT5 modal dialog overlay (OptionsDialog via Ctrl+O / SETTINGS button)
        if hasattr(self.window, "tab1"):
            idx_tab1 = self.window.tabWidget.indexOf(self.window.tab1)
            if idx_tab1 != -1:
                self.window.tabWidget.removeTab(idx_tab1)

        # Remove Tab 4 (System Audit Logs) from main tabWidget
        # Logs are displayed in floating modal System Audit Dialog via Ctrl+L or Telemetry button
        if hasattr(self.window, "tab4"):
            idx_tab4 = self.window.tabWidget.indexOf(self.window.tab4)
            if idx_tab4 != -1:
                self.window.tabWidget.removeTab(idx_tab4)
            self.window.tab4.setVisible(True)


    def _toggle_candles(self, checked):
        if hasattr(self.window, "candlesticks") and self.window.candlesticks:
            self.window.candlesticks.setVisible(checked)

    def _toggle_value_area(self, checked):
        if hasattr(self.window, "drawing_engine") and hasattr(self.window.drawing_engine, "toggle_value_area"):
            self.window.drawing_engine.toggle_value_area(checked)
        else:
            self.window._va_visible = checked
            for it_name in ("line_vah", "line_val", "va_region"):
                if hasattr(self.window, it_name):
                    it = getattr(self.window, it_name)
                    if it:
                        it.setVisible(checked)
        if hasattr(self.window, "va_rects"):
            for r in self.window.va_rects:
                r.setVisible(checked)

    def _toggle_poc(self, checked):
        if hasattr(self.window, "drawing_engine") and hasattr(self.window.drawing_engine, "toggle_poc"):
            self.window.drawing_engine.toggle_poc(checked)
        else:
            self.window._poc_visible = checked
            if hasattr(self.window, "line_tpoc") and self.window.line_tpoc:
                self.window.line_tpoc.setVisible(checked)
            if hasattr(self.window, "line_vpoc") and self.window.line_vpoc:
                self.window.line_vpoc.setVisible(checked)

    def _toggle_cpr(self, checked):
        if hasattr(self.window, "cpr_lines"):
            for l in self.window.cpr_lines:
                l.setVisible(checked)

    def _toggle_delta(self, checked):
        if hasattr(self.window, "delta_items"):
            for it in self.window.delta_items:
                it.setVisible(checked)

    def _get_nav_btn_styles(self, is_dark):
        """Unified institutional styling for bottom workspace tab buttons (MT5 Toolbox / VS Code style):
        12px font, Title Case, generous horizontal padding (0 18px), 30px comfortable height,
        and clean top hairline active indicator with subtle background tint.
        """
        if is_dark:
            act_style = (
                "QPushButton { background-color: #0f172a; color: #38bdf8; font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif; "
                "font-size: 12px; font-weight: 600; letter-spacing: 0.2px; border: none; border-top: 2px solid #38bdf8; padding: 0 18px; "
                "min-height: 30px; max-height: 30px; border-radius: 0px; }"
            )
            inact_style = (
                "QPushButton { background-color: transparent; color: #94a3b8; font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif; "
                "font-size: 12px; font-weight: 500; letter-spacing: 0.2px; border: none; border-top: 2px solid transparent; padding: 0 18px; "
                "min-height: 30px; max-height: 30px; border-radius: 0px; } "
                "QPushButton:hover { color: #f8fafc; border-top: 2px solid #475569; background-color: #121827; }"
            )
        else:
            act_style = (
                "QPushButton { background-color: #f8fafc; color: #0284c7; font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif; "
                "font-size: 12px; font-weight: 600; letter-spacing: 0.2px; border: none; border-top: 2px solid #0284c7; padding: 0 18px; "
                "min-height: 30px; max-height: 30px; border-radius: 0px; }"
            )
            inact_style = (
                "QPushButton { background-color: transparent; color: #64748b; font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif; "
                "font-size: 12px; font-weight: 500; letter-spacing: 0.2px; border: none; border-top: 2px solid transparent; padding: 0 18px; "
                "min-height: 30px; max-height: 30px; border-radius: 0px; } "
                "QPushButton:hover { color: #0f172a; border-top: 2px solid #cbd5e1; background-color: #f1f5f9; }"
            )
        return act_style, inact_style

    def _switch_nav_tab(self, target_tab, active_btn=None, tab_name=""):
        self.window.tabWidget.setCurrentWidget(target_tab)

        is_dark = getattr(self, "is_dark_theme", False)
        act_style, inact_style = self._get_nav_btn_styles(is_dark)

        buttons = getattr(self, "nav_buttons", [])
        if not buttons and hasattr(self, "terminal") and hasattr(self.terminal, "header"):
            buttons = getattr(self.terminal.header, "nav_buttons", [])

        for btn, tab, _ in buttons:
            is_active = (btn == active_btn) or (active_btn is None and tab == target_tab)
            btn.setChecked(is_active)
            btn.setStyleSheet(act_style if is_active else inact_style)

        if hasattr(self, "lbl_tab_title") and tab_name:
            self.lbl_tab_title.setText(tab_name)

        is_terminal = (target_tab == getattr(self.window, "tab2", None))

        # Pure Institutional Separation: Hide timeframe/strategy controls outside Terminal tab
        if hasattr(self, "chart_context_bar") and self.chart_context_bar:
            self.chart_context_bar.setVisible(is_terminal)
        if hasattr(self, "lbl_header_app_title") and self.lbl_header_app_title:
            self.lbl_header_app_title.setVisible(not is_terminal)
            if tab_name:
                self.lbl_header_app_title.setText(f"VECTRA · {tab_name.upper()}")

        if target_tab == getattr(self.window, "tab3", None):
            if hasattr(self, "stats") and self.stats:
                self.stats.refresh()
        elif target_tab == getattr(self.window, "tab_5", None):
            if hasattr(self.window, "backtest_controller") and hasattr(self.window.backtest_controller, "set_symbol"):
                curr_sym = getattr(self.window, "current_sym", None)
                if curr_sym:
                    self.window.backtest_controller.set_symbol(curr_sym)
        elif target_tab == getattr(self.window, "tabCalendar", None):
            cal_mgr = getattr(self.window, "calendar_mgr", None) or getattr(self.terminal, "calendar", None)
            if cal_mgr:
                curr_sym = getattr(self.window, "current_sym", None)
                if curr_sym and hasattr(cal_mgr, "set_current_symbol"):
                    cal_mgr.set_current_symbol(curr_sym)
                if hasattr(cal_mgr, "load_calendar"):
                    cal_mgr.load_calendar()

        # Dedicated Viewport: Only show Watchlist on Tab 1 (Terminal), unless manually collapsed
        if hasattr(self.window, "sidebar"):
            is_user_collapsed = getattr(self.window, "watchlist_collapsed", False)
            show_sidebar = is_terminal and not is_user_collapsed
            self.window.sidebar.setVisible(show_sidebar)
            # Maintain exact splitter proportions within current window bounds (prevents window widening)
            if show_sidebar and hasattr(self.window, "mainSplitter"):
                total_w = self.window.mainSplitter.width()
                sidebar_w = 280
                self.window.mainSplitter.setSizes([sidebar_w, max(100, total_w - sidebar_w)])

    def _update_nav_buttons_style(self, is_dark):
        """MT5 Toolbox bottom tab bar styling: elevated top hairline border on active tab."""
        act_style, inact_style = self._get_nav_btn_styles(is_dark)

        buttons = getattr(self, "nav_buttons", [])
        if not buttons and hasattr(self, "terminal") and hasattr(self.terminal, "header"):
            buttons = getattr(self.terminal.header, "nav_buttons", [])
        for btn, tab, _ in buttons:
            is_active = btn.isChecked() or (tab == self.window.tabWidget.currentWidget())
            btn.setStyleSheet(act_style if is_active else inact_style)

        if hasattr(self, "btnNavSettings") and self.btnNavSettings:
            self.btnNavSettings.setVisible(False)


