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


    def _toggle_candles(self, checked):
        if hasattr(self.window, "candlesticks") and self.window.candlesticks:
            self.window.candlesticks.setVisible(checked)

    def _toggle_value_area(self, checked):
        if hasattr(self.window, "va_rects"):
            for r in self.window.va_rects:
                r.setVisible(checked)

    def _toggle_poc(self, checked):
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

    def _switch_nav_tab(self, target_tab, active_btn=None, tab_name=""):
        self.window.tabWidget.setCurrentWidget(target_tab)

        is_dark = getattr(self, "is_dark_theme", False)
        act_style = (
            "QPushButton { background-color: #141414; color: #ffffff; font-family: 'Segoe UI', -apple-system, sans-serif; "
            "font-size: 10px; font-weight: 700; border: none; border-bottom: 2px solid #ffffff; padding: 0 14px; "
            "min-height: 27px; max-height: 27px; }"
            if is_dark else
            "QPushButton { background-color: #e2e8f0; color: #0f172a; font-family: 'Segoe UI', -apple-system, sans-serif; "
            "font-size: 10px; font-weight: 700; border: none; border-bottom: 2px solid #0f172a; padding: 0 14px; "
            "min-height: 27px; max-height: 27px; }"
        )
        inact_style = (
            "QPushButton { background-color: transparent; color: #777777; font-family: 'Segoe UI', -apple-system, sans-serif; "
            "font-size: 10px; font-weight: 600; border: none; border-bottom: 2px solid transparent; padding: 0 14px; "
            "min-height: 27px; max-height: 27px; } "
            "QPushButton:hover { color: #cccccc; background-color: #111111; }"
            if is_dark else
            "QPushButton { background-color: transparent; color: #64748b; font-family: 'Segoe UI', -apple-system, sans-serif; "
            "font-size: 10px; font-weight: 600; border: none; border-bottom: 2px solid transparent; padding: 0 14px; "
            "min-height: 27px; max-height: 27px; } "
            "QPushButton:hover { color: #1e293b; background-color: #f1f5f9; }"
        )

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
                self.lbl_header_app_title.setText(f"QUANT AI TERMINAL v2.2 · {tab_name.upper()}")

        if target_tab == getattr(self.window, "tab3", None):
            if hasattr(self, "stats") and self.stats:
                self.stats.refresh()

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
        act_style = (
            "QPushButton { background-color: #141414; color: #ffffff; font-family: 'Consolas', 'Segoe UI', monospace; "
            "font-size: 10px; font-weight: 700; letter-spacing: 0.5px; border: 1px solid #262626; border-top: 2px solid #ffffff; "
            "border-bottom: none; border-top-left-radius: 2px; border-top-right-radius: 2px; padding: 0 14px; "
            "min-height: 24px; max-height: 24px; }"
            if is_dark else
            "QPushButton { background-color: #ffffff; color: #0f172a; font-family: 'Consolas', 'Segoe UI', monospace; "
            "font-size: 10px; font-weight: 700; letter-spacing: 0.5px; border: 1px solid #cbd5e1; border-top: 2px solid #0f172a; "
            "border-bottom: none; border-top-left-radius: 2px; border-top-right-radius: 2px; padding: 0 14px; "
            "min-height: 24px; max-height: 24px; }"
        )
        inact_style = (
            "QPushButton { background-color: transparent; color: #71717a; font-family: 'Consolas', 'Segoe UI', monospace; "
            "font-size: 10px; font-weight: 600; letter-spacing: 0.5px; border: 1px solid transparent; border-bottom: none; padding: 0 14px; "
            "min-height: 24px; max-height: 24px; } "
            "QPushButton:hover { color: #ffffff; background-color: #111111; border-color: #1c1c1c; }"
            if is_dark else
            "QPushButton { background-color: transparent; color: #64748b; font-family: 'Consolas', 'Segoe UI', monospace; "
            "font-size: 10px; font-weight: 600; letter-spacing: 0.5px; border: 1px solid transparent; border-bottom: none; padding: 0 14px; "
            "min-height: 24px; max-height: 24px; } "
            "QPushButton:hover { color: #0f172a; background-color: #f1f5f9; border-color: #e2e8f0; }"
        )
        buttons = getattr(self, "nav_buttons", [])
        if not buttons and hasattr(self, "terminal") and hasattr(self.terminal, "header"):
            buttons = getattr(self.terminal.header, "nav_buttons", [])
        for btn, tab, _ in buttons:
            is_active = btn.isChecked() or (tab == self.window.tabWidget.currentWidget())
            btn.setStyleSheet(act_style if is_active else inact_style)

        if hasattr(self, "btnNavSettings") and self.btnNavSettings:
            btn_opt_style = (
                "QPushButton { background-color: transparent; color: #94a3b8; font-family: 'Consolas', 'Segoe UI', monospace; "
                "font-size: 10px; font-weight: 600; letter-spacing: 0.5px; border: 1px solid transparent; border-bottom: none; padding: 0 10px; "
                "min-height: 24px; max-height: 24px; } "
                "QPushButton:hover { color: #ffffff; background-color: #111111; border-color: #1c1c1c; }"
                if is_dark else
                "QPushButton { background-color: transparent; color: #64748b; font-family: 'Consolas', 'Segoe UI', monospace; "
                "font-size: 10px; font-weight: 600; letter-spacing: 0.5px; border: 1px solid transparent; border-bottom: none; padding: 0 10px; "
                "min-height: 24px; max-height: 24px; } "
                "QPushButton:hover { color: #0f172a; background-color: #f1f5f9; border-color: #e2e8f0; }"
            )
            self.btnNavSettings.setStyleSheet(btn_opt_style)

