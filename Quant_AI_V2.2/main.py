import sys
import os

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
for _p in [
    ROOT_DIR,
    os.path.join(ROOT_DIR, "backend"),
    os.path.join(ROOT_DIR, "frontend"),
]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from datetime import datetime, timedelta
import json
from loguru import logger
from backend.infrastructure.security.crypto_vault import decrypt_secret
from backend.infrastructure.brokers.mt5_safe import mt5
from backend.infrastructure.brokers.execution_manager import ExecutionManager

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QTableWidgetItem,
    QCheckBox,
    QGraphicsDropShadowEffect,
    QSizePolicy,
    QComboBox,
    QMessageBox,
    QHeaderView,
)

from PySide6.QtGui import QFont, QIcon, QColor, QCursor, QKeySequence, QShortcut

from PySide6.QtCore import Qt, QTimer, QFile, QIODevice, QObject, QThread, QSize, QPoint

from PySide6.QtUiTools import QUiLoader

from frontend.widgets.modify_order_dialog import ModifyOrderDialog

from frontend.controllers.chart_controller import setup_chart_ui, update_chart_theme
from frontend.controllers.blotter_controller import BlotterController
from frontend.controllers.navigation_controller import NavigationController
from frontend.controllers.header_controller import HeaderController, WorkspaceHeaderController
from frontend.controllers.watchlist_controller import WatchlistController
from frontend.controllers.logs_controller import LogsController
from frontend.controllers.account_controller import AccountController
from frontend.controllers.performance_controller import PerformanceController
from frontend.controllers.macro_calendar_controller import MacroCalendarController
from frontend.controllers.backtest_controller import setup_backtest_tab
from frontend.controllers.settings_controller import SettingsManager

from frontend.widgets.gauge_widget import GaugeWidget
from frontend.widgets.theme_toggle import ThemeToggleSwitch
from frontend.widgets.bot_power_button import BotPowerButton
from backend.core.event_bus import event_bus
from backend.core.bot_worker import BotWorker
from backend.infrastructure.notifications.telegram_notifier import telegram_notifier

_TXT_CONNECTED = "CONNECTED: {}"

_TXT_DISCONNECTED = "MT5 DISCONNECTED"

_TXT_START = "BOT: STANDBY"

_TXT_STOP = "BOT: ACTIVE"


class QuantTerminal(QObject):

    def __init__(self, with_overlay: bool = False):

        super().__init__()

        # 0. Ensure MT5 connection is active on main GUI thread
        if not mt5.initialize():
            logger.info("[QuantTerminal] Calling mt5.initialize() on main Qt GUI thread...")
            for custom_path in [
                r"C:\Program Files\LiteFinance MT5 Terminal\terminal64.exe",
                r"C:\Program Files\MetaTrader 5\terminal64.exe",
                r"C:\Program Files (x86)\MetaTrader 5\terminal64.exe",
            ]:
                if os.path.exists(custom_path):
                    if mt5.initialize(path=custom_path):
                        break

        term = mt5.terminal_info()
        acc_info = mt5.account_info()
        if term and getattr(term, "connected", False) and acc_info:
            logger.info(f"[QuantTerminal] Active MT5 session verified: #{acc_info.login} ({acc_info.server})")
        else:
            try:
                root_d = os.path.dirname(os.path.abspath(__file__))
                cfg_p = os.path.join(root_d, "config", "ai_config.json")
                if os.path.exists(cfg_p):
                    with open(cfg_p, "r", encoding="utf-8") as f:
                        cfg_data = json.load(f)
                    srv = cfg_data.get("MT5_SERVER")
                    acc_num = cfg_data.get("MT5_ACCOUNT")
                    pwd_enc = cfg_data.get("MT5_PASSWORD")
                    pwd_dec = decrypt_secret(pwd_enc) if pwd_enc else None
                    if srv and acc_num and pwd_dec:
                        mt5.login(int(acc_num), password=pwd_dec, server=srv)
            except Exception as e:
                logger.warning(f"[QuantTerminal] Auto-login fallback: {e}")

        self._load_ui()
        self.window.quant_terminal = self

        # Initialize modular controllers
        from frontend.controllers.blotter_controller import BlotterController
        from frontend.controllers.navigation_controller import NavigationController
        from frontend.controllers.header_controller import HeaderController

        self.blotter = BlotterController(self)
        self.nav = NavigationController(self)
        self.header = HeaderController(self)


        self._setup_navigation_rail()

        self._setup_corner_widget()

        self.settings = SettingsManager(self.window)
        self.window.settings_mgr = self.settings

        self.watchlist = WatchlistController(self.window)

        self.logs = LogsController(self.window)

        self.account = AccountController(self.window)

        self.stats = PerformanceController(self.window)

        self.calendar = MacroCalendarController(self.window)

        setup_chart_ui(self.window)
        if hasattr(self, "lbl_top_ticker"):
            self.lbl_top_ticker.setText(self._format_top_ticker())

        setup_backtest_tab(self.window)

        self.exec_mgr = ExecutionManager(slippage=20)
        self._demo_positions = None

        self._setup_executions_table()

        if hasattr(self.window, "btnEmergencyKill"):
            self.window.btnEmergencyKill.clicked.connect(self._handle_kill_switch)

        if hasattr(self.window, "frameAIArea"):
            self.window.frameAIArea.setVisible(True)
        if hasattr(self.window, "btn_edge_plan") and self.window.btn_edge_plan:
            self.window.btn_edge_plan.setVisible(False)
        if hasattr(self.window, "chartSplitter"):
            self.window.chartSplitter.setSizes([1150, 290])

        self.window.tabWidget.currentChanged.connect(self._on_tab_changed)

        self.bot_thread = None

        self.bot_worker = None

        self._tick_timer = QTimer()

        self._tick_timer.timeout.connect(self._on_tick)

        self._tick_timer.start(1000)

        telegram_notifier.start_listening(event_bus)

        event_bus.remote_command.connect(self._handle_remote_command)

        # Global shortcut Ctrl+O for authentic MT5 Options Dialog
        if hasattr(self, "settings") and hasattr(self.settings, "open_options_dialog"):
            self.shortcut_options = QShortcut(QKeySequence("Ctrl+O"), self.window)
            self.shortcut_options.activated.connect(self.settings.open_options_dialog)

        # Global shortcut Ctrl+L for authentic System Audit & Journal Dialog
        if hasattr(self, "logs") and hasattr(self.logs, "toggle_audit_dialog"):
            self.shortcut_logs = QShortcut(QKeySequence("Ctrl+L"), self.window)
            self.shortcut_logs.activated.connect(self.logs.toggle_audit_dialog)

        # Initialize directly in institutional Light Theme per user preference
        self._on_theme_changed(False)

        # Ensure default active workspace at launch is always TERMINAL (tab2)
        if hasattr(self, "btnNavTerminal"):
            self._switch_nav_tab(self.window.tab2, self.btnNavTerminal, "TERMINAL")
        elif hasattr(self.window, "tab2"):
            self.window.tabWidget.setCurrentWidget(self.window.tab2)

        # Clean Fade-Out Overlay (Cách 2) initialized seamlessly before showMaximized
        if with_overlay:
            from frontend.widgets.splash_screen import FadeOverlayWidget
            self.overlay = FadeOverlayWidget(self.window)
            self.overlay.show()
            self.overlay.raise_()
        else:
            self.overlay = None

        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            self.window.setMaximumSize(avail.width(), avail.height())
            self.window.setGeometry(avail)
        self.window.showMaximized()


    # =========================================================================
    # MODULAR DELEGATES: TRADE BLOTTER (frontend.controllers.blotter_controller)
    # =========================================================================
    def _setup_executions_table(self):
        return self.blotter._setup_executions_table()

    def _render_blotter(self, mode=None):
        return self.blotter._render_blotter(mode)

    def _close_single_position(self, ticket: int):
        return self.blotter._close_single_position(ticket)

    def _modify_single_position(self, pos_info: dict):
        return self.blotter._modify_single_position(pos_info)

    def _apply_flatten_btn_style(self):
        return self.blotter._apply_flatten_btn_style()

    def _disarm_flatten_button(self):
        return self.blotter._disarm_flatten_button()

    def _on_flatten_timer_tick(self):
        return self.blotter._on_flatten_timer_tick()

    def _handle_kill_switch(self):
        return self.blotter._handle_kill_switch()

    # =========================================================================
    # MODULAR DELEGATES: NAVIGATION RAIL (frontend.controllers.navigation_controller)
    # =========================================================================
    def _setup_navigation_rail(self):
        return self.nav._setup_navigation_rail()

    def _toggle_candles(self, checked):
        return self.nav._toggle_candles(checked)

    def _toggle_value_area(self, checked):
        return self.nav._toggle_value_area(checked)

    def _toggle_poc(self, checked):
        return self.nav._toggle_poc(checked)

    def _toggle_cpr(self, checked):
        return self.nav._toggle_cpr(checked)

    def _toggle_delta(self, checked):
        return self.nav._toggle_delta(checked)

    def _switch_nav_tab(self, target_tab, active_btn=None, tab_name=""):
        return self.nav._switch_nav_tab(target_tab, active_btn, tab_name)

    def _update_nav_buttons_style(self, is_dark):
        return self.nav._update_nav_buttons_style(is_dark)

    # =========================================================================
    # MODULAR DELEGATES: WORKSPACE HEADER (frontend.controllers.workspace_header)
    # =========================================================================
    def _setup_custom_title_bar(self):
        return self.header._setup_custom_title_bar()

    def _format_top_ticker(self, *args, **kwargs):
        return self.header._format_top_ticker(*args, **kwargs)

    def _refresh_top_ticker(self):
        return self.header._refresh_top_ticker()

    def set_execution_mode(self, mode):
        return self.header.set_execution_mode(mode)

    def _update_panel_toggle_styles(self, is_dark=None):
        return self.header._update_panel_toggle_styles(is_dark)

    def _update_mode_buttons(self, is_dark=None):
        return self.header._update_mode_buttons(is_dark)

    def _update_title_and_bottom_bar_theme(self, is_dark):
        return self.header._update_title_and_bottom_bar_theme(is_dark)

    def _update_tf_button_styles(self, is_dark=None):
        return self.header._update_tf_button_styles(is_dark)

    def _load_ui(self):

        ui_path = os.path.join(ROOT_DIR, "frontend", "quant_ai.ui")
        if not os.path.exists(ui_path):
            ui_path = os.path.join(ROOT_DIR, "quant_ai.ui")
        ui_file = QFile(ui_path)

        ui_file.open(QIODevice.OpenModeFlag.ReadOnly)

        self.window = QUiLoader().load(ui_file, None)

        ui_file.close()

        # Load Global QSS Theme (Default: Institutional Light Theme)
        qss_path = os.path.join(ROOT_DIR, "frontend", "styling", "style_light.qss")
        if not os.path.exists(qss_path):
            qss_path = os.path.join(ROOT_DIR, "ui", "style_light.qss")

        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                self.window.setStyleSheet(f.read())

        # Frameless window with blue glow border
        self.window.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.window.setAttribute(Qt.WA_TranslucentBackground)

        self.window.closeEvent = self.closeEvent

        # Live Alerts card will be configured in _setup_sidebar_alerts

        # Show institutional watchlist sidebar by default (width: 260px)
        if hasattr(self.window, "sidebar"):
            self.window.sidebar.setMinimumWidth(240)
            self.window.sidebar.setMaximumWidth(320)
            self.window.sidebar.setVisible(True)
            if self.window.sidebar.layout():
                self.window.sidebar.layout().setContentsMargins(2, 2, 2, 2)
        if hasattr(self.window, "mainSplitter"):
            self.window.mainSplitter.setStretchFactor(0, 0)
            self.window.mainSplitter.setStretchFactor(1, 1)
            total_w = max(400, self.window.mainSplitter.width() or 1440)
            sidebar_w = 260
            self.window.mainSplitter.setSizes([sidebar_w, max(100, total_w - sidebar_w)])
        if hasattr(self.window, "chartSplitter"):
            self.window.chartSplitter.setSizes([900, 340])

        # Initialize Macro & Economic Calendar tab workspace
        if not hasattr(self.window, "tabCalendar"):
            self.window.tabCalendar = QWidget()
            self.window.tabCalendar.setObjectName("tabCalendar")
            if hasattr(self.window, "tabWidget"):
                self.window.tabWidget.addTab(self.window.tabCalendar, "CALENDAR")

        # Pure Flat Architecture (Zero Drop Shadow / Glow per Institutional Specification)
        if self.window.centralWidget():
            self.window.centralWidget().setGraphicsEffect(None)

        # Track drag position for frameless window
        self._drag_pos = None

    def _setup_sidebar_alerts(self, is_dark=None):
        """Setup QUANT LIVE ALERTS card inside frameSidebarAccount with clean spacing and WCAG AA contrast."""
        if not hasattr(self.window, "frameSidebarAccount"):
            return
        if is_dark is None:
            is_dark = getattr(self, "is_dark_theme", False)

        frame = self.window.frameSidebarAccount
        frame.setVisible(True)
        frame.setFixedHeight(96)
        card_bg = "#0a0c10" if is_dark else "#ffffff"
        card_border = "#1e222d" if is_dark else "#e2e8f0"
        title_color = "#94a3b8" if is_dark else "#64748b"
        time_color = "#94a3b8" if is_dark else "#64748b"
        desc_color = "#cbd5e1" if is_dark else "#334155"

        frame.setStyleSheet(
            f"QFrame#frameSidebarAccount {{ background-color: {card_bg}; border: 1px solid {card_border}; border-radius: 4px; margin: 2px; }}"
        )

        # Hide any previous UI children so they never render
        for child in frame.findChildren(QWidget):
            child.setVisible(False)

        # Remove existing items from layout cleanly without destroying C++ objects
        if frame.layout():
            while frame.layout().count():
                frame.layout().takeAt(0)
            layout = frame.layout()
        else:
            layout = QVBoxLayout(frame)

        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # Header row: QUANT LIVE ALERTS [ 1 PENDING ]
        row_header = QWidget()
        row_header.setVisible(True)
        row_h_box = QHBoxLayout(row_header)
        row_h_box.setContentsMargins(0, 0, 0, 0)
        row_h_box.setSpacing(4)

        lbl_title = QLabel("QUANT LIVE ALERTS")
        lbl_title.setStyleSheet(f"color: {title_color}; font-family: 'Segoe UI', sans-serif; font-size: 9.5px; font-weight: bold; letter-spacing: 0.5px;")

        self.sidebar_alert_badge = QLabel("ACTIVE")
        self.sidebar_alert_badge.setStyleSheet("background-color: #064e3b; color: #4ade80; border: 1px solid #16a34a; font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; padding: 1px 6px; border-radius: 2px;")

        row_h_box.addWidget(lbl_title)
        row_h_box.addStretch()
        row_h_box.addWidget(self.sidebar_alert_badge)
        layout.addWidget(row_header)

        # Alert row
        row_alert = QWidget()
        row_alert.setVisible(True)
        row_a_box = QHBoxLayout(row_alert)
        row_a_box.setContentsMargins(0, 0, 0, 0)
        row_a_box.setSpacing(4)

        raw_sym = getattr(self.window, "current_sym", "XAUUSD") if hasattr(self, "window") and getattr(self.window, "current_sym", None) else "XAUUSD"
        clean_sym = raw_sym.split("\n")[0].strip()

        self.sidebar_alert_type = QLabel(f"[{clean_sym}] M15 STRUCTURE")
        self.sidebar_alert_type.setStyleSheet("color: #f59e0b; font-family: 'Segoe UI', sans-serif; font-size: 9.5px; font-weight: bold; letter-spacing: 0.3px;")

        self.sidebar_alert_time = QLabel(datetime.now().strftime("%H:%M:%S"))
        self.sidebar_alert_time.setStyleSheet(f"color: {time_color}; font-family: Consolas, monospace; font-size: 9px;")

        row_a_box.addWidget(self.sidebar_alert_type)
        row_a_box.addStretch()
        row_a_box.addWidget(self.sidebar_alert_time)
        layout.addWidget(row_alert)

        self.sidebar_alert_desc = QLabel(f"{clean_sym} market regime scanned. Real-time liquidity & FVG order flow active.")
        self.sidebar_alert_desc.setVisible(True)
        self.sidebar_alert_desc.setWordWrap(True)
        self.sidebar_alert_desc.setStyleSheet(f"color: {desc_color}; font-family: 'Segoe UI', sans-serif; font-size: 9px; line-height: 1.25;")
        layout.addWidget(self.sidebar_alert_desc)

    def update_sidebar_alert(self, sym=None, alert_type=None, desc=None):
        """Dynamically update sidebar alert card when active symbol changes or signals occur."""
        if not hasattr(self, "sidebar_alert_type") or not self.sidebar_alert_type:
            return
        clean_sym = (sym or getattr(self.window, "current_sym", "XAUUSD")).split("\n")[0].strip()
        time_str = datetime.now().strftime("%H:%M:%S")
        if hasattr(self, "sidebar_alert_time") and self.sidebar_alert_time:
            self.sidebar_alert_time.setText(time_str)
        if alert_type:
            self.sidebar_alert_type.setText(alert_type)
        else:
            self.sidebar_alert_type.setText(f"[{clean_sym}] M15 STRUCTURE")
        if desc:
            self.sidebar_alert_desc.setText(desc)
        else:
            self.sidebar_alert_desc.setText(f"{clean_sym} market regime scanned. Real-time liquidity & FVG order flow active.")
    def _setup_corner_widget(self):
        self.lbl_tab_title = QLabel()
        self.lbl_status = QLabel(_TXT_DISCONNECTED)
        self.lbl_status.setStyleSheet(
            "color: #ef4444; font-weight: 600; font-size: 11px; margin-right: 15px;"
        )
        # Keep dummy btnStart for backward compatibility
        self.btnStart = QPushButton()
        self.btnStart.setVisible(False)

        # Hide bulky legacy pills to prioritize pure auction chart canvas
        for pill_name in ["pillMT5", "pillMemory", "pillMacro", "pillNews"]:
            if hasattr(self.window, pill_name):
                getattr(self.window, pill_name).setVisible(False)
        if hasattr(self.window, "layoutPipelinePills"):
            self.window.layoutPipelinePills.setContentsMargins(0, 0, 0, 0)
            self.window.layoutPipelinePills.setSpacing(0)

        # Hide redundant KPI cards from Tab 1 (already tracked in Top Command Strip & Tab 2)
        for kpi_name in ["cardSharpe", "cardProfitFactor", "cardMaxDD", "cardWinRate", "cardNetPnL"]:
            if hasattr(self.window, kpi_name):
                getattr(self.window, kpi_name).setVisible(False)
        if hasattr(self.window, "layoutKPICards"):
            self.window.layoutKPICards.setContentsMargins(0, 0, 0, 0)
            self.window.layoutKPICards.setSpacing(0)

        # Maximize chart canvas area by tightening Tab 1 margins (Tiled Grid: 0px margins, 1px spacing)
        if hasattr(self.window, "layoutTab2"):
            self.window.layoutTab2.setContentsMargins(0, 0, 0, 0)
            self.window.layoutTab2.setSpacing(1)

        # Custom 24px title bar for frameless window
        self._setup_custom_title_bar()

        # Setup austere macro telemetry strip
        self._setup_gauge_widgets()

        # Add EMERGENCY KILL-SWITCH label
        self._setup_emergency_label()
        self._setup_sidebar_alerts()

    def _on_theme_changed(self, is_dark=False):
        """Set application stylesheet and components permanently to Light Theme."""
        is_dark = False
        self.is_dark_theme = False
        theme_file = "style_light.qss"
        qss_path = os.path.join(ROOT_DIR, "frontend", "styling", theme_file)
        if not os.path.exists(qss_path):
            qss_path = os.path.join(ROOT_DIR, "ui", "style.qss" if is_dark else "style_light.qss")

        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                self.window.setStyleSheet(f.read())

        # Update Tab 1 Macro Telemetry Strip
        if hasattr(self, "lbl_macro_telemetry") and self.lbl_macro_telemetry:
            macro_bg = "#03050a" if is_dark else "#f1f5f9"
            macro_border = "rgba(255, 255, 255, 0.08)" if is_dark else "rgba(0, 0, 0, 0.1)"
            self.lbl_macro_telemetry.setStyleSheet(
                f"background-color: {macro_bg}; border: 1px solid {macro_border}; "
                "border-radius: 2px; padding: 4px 8px; min-height: 22px;"
            )

        # Update Tab 1 Chart components (plot widget, axes, OHLC header, TF buttons, AI reasoning)
        update_chart_theme(self.window, is_dark)
        if hasattr(self, "settings") and hasattr(self.settings, "_update_category_nav_styles"):
            self.settings._update_category_nav_styles(is_dark)

        # Update Navigation Rail Bot Power Button
        if hasattr(self, "btn_bot_power") and hasattr(self.btn_bot_power, "set_dark_theme"):
            self.btn_bot_power.set_dark_theme(is_dark)

        # Update Tab 1 Watchlist items theme
        if hasattr(self, "watchlist") and hasattr(self.watchlist, "update_theme"):
            self.watchlist.update_theme(is_dark)
            self._setup_sidebar_alerts(is_dark)

        # Update Tab 2 (Stats)
        if hasattr(self, "stats") and hasattr(self.stats, "update_theme"):
            self.stats.update_theme(is_dark)

        # Update Tab 3 (Backtest)
        if hasattr(self.window, "backtest_controller") and hasattr(self.window.backtest_controller, "update_theme"):
            self.window.backtest_controller.update_theme(is_dark)

        # Update Tab 5 (Logs)
        if hasattr(self, "logs") and hasattr(self.logs, "update_theme"):
            self.logs.update_theme(is_dark)

        # Update Tab Calendar
        if hasattr(self, "calendar") and hasattr(self.calendar, "update_theme"):
            self.calendar.update_theme(is_dark)

        # Update Top Navigation Tab buttons
        self._update_nav_buttons_style(is_dark)

        # Update Top Custom Title Bar and Bottom Toolbox Bar
        self._update_title_and_bottom_bar_theme(is_dark)

        # Re-render Trade Blotter Table
        if hasattr(self, "_render_blotter"):
            self._render_blotter(getattr(self, "active_blotter_mode", "active"))

    def _setup_gauge_widgets(self):
        """Eliminate redundant gauge widgets and redundant macro strip from Signal Approval Ticket column."""
        try:
            if hasattr(self.window, "cardDXY"):
                self.window.cardDXY.setVisible(False)
            if hasattr(self.window, "cardUS10Y"):
                self.window.cardUS10Y.setVisible(False)
            if hasattr(self.window, "lbl_macro_telemetry"):
                self.window.lbl_macro_telemetry.setVisible(False)
        except Exception as err:
            logger.debug(f"[QuantTerminal] Gauge widget hiding error: {err}")

    def _setup_emergency_label(self):
        """Configure panel collapse controls."""
        if hasattr(self.window, "btnEmergencyKill"):
            self.window.btnEmergencyKill.setVisible(False)
        if hasattr(self.window, "btnCollapseWatchlist"):
            self.window.btnCollapseWatchlist.setVisible(True)

    def _on_tick(self):
        is_running = self.btn_bot_power.is_running() if hasattr(self, "btn_bot_power") else False

        term = mt5.terminal_info()
        acc = mt5.account_info() if term is not None else None
        is_connected = term is not None and getattr(term, "connected", False) and acc is not None

        if not is_connected:
            self.lbl_status.setText(_TXT_DISCONNECTED)
            self.lbl_status.setStyleSheet(
                "color: #ef4444; font-weight: 600; font-size: 11px; margin-right: 15px;"
            )
            if hasattr(self, "dot_mt5"):
                self.dot_mt5.setStyleSheet("background-color: #ef4444; border-radius: 3px;")
                self.dot_mt5.setToolTip("FEED: DISCONNECTED")
            if hasattr(self, "lbl_top_ticker"):
                self.lbl_top_ticker.setText(
                    self._format_top_ticker(bal=100000.0, eq=100000.0, pnl=0.0, pnl_pct=0.0, latency=0.0, is_algo_active=is_running)
                )

            if hasattr(self.window, "labelStatus"):
                delattr(self.window, "labelStatus")
            return

        if acc:
            self.lbl_status.setText(_TXT_CONNECTED.format(acc.login))
            self.lbl_status.setStyleSheet(
                "color: #22c55e; font-weight: 600; font-size: 11px; margin-right: 15px;"
            )
            if hasattr(self, "dot_mt5"):
                self.dot_mt5.setStyleSheet("background-color: #10b981; border-radius: 3px;")
                self.dot_mt5.setToolTip(f"FEED: CONNECTED ({acc.login})")

            pnl = acc.equity - acc.balance
            pnl_pct = (pnl / acc.balance * 100) if acc.balance > 0 else 0.0
            if hasattr(self, "lbl_top_ticker"):
                self.lbl_top_ticker.setText(
                    self._format_top_ticker(
                        bal=acc.balance,
                        eq=acc.equity,
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        latency=1.2,
                        is_algo_active=is_running,
                    )
                )

            if hasattr(self.window, "labelStatus"):
                self.window.labelStatus.setText(f"CONNECTED: {acc.login}")
                self.window.labelStatus.setStyleSheet(
                    "color: #22c55e; font-weight: 600; font-size: 11px;"
                )

            if hasattr(self.window, "valBalance"):
                self.window.valBalance.setText(f"${acc.balance:,.2f}")
                self.window.valEquity.setText(f"${acc.equity:,.2f}")

            if hasattr(self.window, "valMargin"):
                margin_pct = (acc.margin / acc.equity * 100) if acc.equity > 0 else 0
                self.window.valMargin.setText(f"{margin_pct:.2f}%")

            # Real-time synchronization of Trade Blotter positions with MT5
            # Tự động nạp nến thực khi MT5 vừa kết nối lại thành công nếu biểu đồ đang rỗng hoặc ở chế độ ngoại tuyến
            needs_auto_reload = False
            if hasattr(self.window, "empty_state_card") and self.window.empty_state_card and self.window.empty_state_card.isVisible():
                needs_auto_reload = True
            if hasattr(self.window, "offline_banner") and self.window.offline_banner and self.window.offline_banner.isVisible():
                needs_auto_reload = True
            if hasattr(self.window, "chart_data_list") and len(self.window.chart_data_list) == 0:
                needs_auto_reload = True

            if needs_auto_reload and hasattr(self.window, "draw_and_analyze"):
                sym = getattr(self.window, "current_sym", "XAUUSD")
                self.window.draw_and_analyze(sym)

            current_blotter_mode = "active"
            if hasattr(self, "blotter") and hasattr(self.blotter, "active_blotter_mode"):
                current_blotter_mode = self.blotter.active_blotter_mode
            elif hasattr(self, "active_blotter_mode"):
                current_blotter_mode = self.active_blotter_mode

            if current_blotter_mode == "active":
                if hasattr(self, "_render_blotter"):
                    self._render_blotter("active")

        active_sym = getattr(self.window, "current_sym", "").split("\n")[0].strip() if hasattr(self, "window") else ""
        all_syms = self.watchlist.get_all_symbols()
        sorted_syms = sorted(all_syms, key=lambda s: 0 if s == active_sym else 1)
        for sym in sorted_syms:
            tick = mt5.symbol_info_tick(sym)
            if tick:
                event_bus.market_tick.emit(sym, tick.bid, tick.ask)

        if hasattr(self, "bot_worker") and self.bot_worker:
            if hasattr(self.bot_worker, "wake_up"):
                self.bot_worker.wake_up()

    def _handle_remote_command(self, cmd):

        if cmd == "STOP" and self.bot_thread and self.bot_thread.isRunning():

            self._toggle_bot()

        elif cmd == "START" and (
            self.bot_thread is None or not self.bot_thread.isRunning()
        ):

            self._toggle_bot()

    def _on_bot_power_toggled(self, is_running):
        """Handle user clicking the custom vector BotPowerButton."""
        self._toggle_bot()

    def _toggle_bot(self):
        try:
            self._do_toggle_bot()
        except Exception as e:
            logger.error(f"[QuantTerminal] Exception in _toggle_bot: {e}")
            import traceback
            logger.error(traceback.format_exc())
            event_bus.log_event.emit(
                "", "ERROR", f"Bot Toggle Error: {e}", "#F23645"
            )
            if hasattr(self, "header") and hasattr(self.header, "btn_algo_toggle") and self.header.btn_algo_toggle:
                self.header.btn_algo_toggle.set_running(False)

    def _do_toggle_bot(self):
        if mt5.terminal_info() is None:
            if hasattr(self, "btn_bot_power"):
                new_state = self.btn_bot_power.is_running()
                if new_state:
                    event_bus.log_event.emit(
                        "",
                        "WARN",
                        "[PAPER TRADING] MT5 disconnected. Running in Standby Paper Trading mode.",
                        "#F59E0B",
                    )
                    self.btnStart.setProperty("running", "true")
                    self.btnStart.setText("BOT: SIMULATION")
                else:
                    event_bus.log_event.emit(
                        "", "INFO", "Bot algorithm stopped.", "#64748b"
                    )
                    self.btnStart.setProperty("running", "false")
                    self.btnStart.setText(_TXT_START)
            else:
                event_bus.log_event.emit(
                    "", "ERROR", "MT5 Not Connected!", "#F23645"
                )
            return

        if self.bot_thread is None or not self.bot_thread.isRunning():

            # Resolve trading timeframe from settings.json or active chart
            TF_MAP = {
                1: mt5.TIMEFRAME_M1,
                5: mt5.TIMEFRAME_M5,
                15: mt5.TIMEFRAME_M15,
                30: mt5.TIMEFRAME_M30,
                60: mt5.TIMEFRAME_H1,
                240: mt5.TIMEFRAME_H4,
                1440: mt5.TIMEFRAME_D1,
                10080: getattr(mt5, "TIMEFRAME_W1", 32769),
                43200: getattr(mt5, "TIMEFRAME_MN1", 49153),
            }
            TF_NAMES = {
                mt5.TIMEFRAME_M1: "M1",
                mt5.TIMEFRAME_M5: "M5",
                mt5.TIMEFRAME_M15: "M15",
                mt5.TIMEFRAME_M30: "M30",
                mt5.TIMEFRAME_H1: "H1",
                mt5.TIMEFRAME_H4: "H4",
                mt5.TIMEFRAME_D1: "D1",
                getattr(mt5, "TIMEFRAME_W1", 32769): "W1",
                getattr(mt5, "TIMEFRAME_MN1", 49153): "MN1",
            }
            tf_setting = 15
            cfg_d = {}
            try:
                with open("config/settings.json", "r", encoding="utf-8") as f_cfg:
                    cfg_d = json.load(f_cfg)
                    tf_setting = cfg_d.get("timeframe", 15)
            except Exception:
                tf_setting = 15

            if tf_setting == "FOLLOW_CHART":
                tf = getattr(self.window, "current_tf", mt5.TIMEFRAME_M15)
                tf_name = getattr(self.window, "current_tf_str", "M15")
            else:
                try:
                    tf_val = int(tf_setting)
                    tf = TF_MAP.get(tf_val, mt5.TIMEFRAME_M15)
                except Exception:
                    tf = mt5.TIMEFRAME_M15
                tf_name = TF_NAMES.get(tf, "M15")

            self._active_bot_tf_str = tf_name

            strategy = None
            if hasattr(self.window, "comboStrategy") and self.window.comboStrategy.currentData():
                strategy = self.window.comboStrategy.currentData()
            if not strategy:
                try:
                    with open("config/settings.json", "r", encoding="utf-8") as f_cfg:
                        cfg_d = json.load(f_cfg)
                        strategy = cfg_d.get("strategy", "builtin_ict_pro")
                except Exception:
                    strategy = "builtin_ict_pro"

            try:
                import shiboken6
                ai_model = (
                    self.window.comboAIModel.currentText()
                    if hasattr(self.window, "comboAIModel")
                    and self.window.comboAIModel is not None
                    and shiboken6.isValid(self.window.comboAIModel)
                    and self.window.comboAIModel.count() > 0
                    else "qwen2.5"
                )
            except Exception:
                ai_model = "qwen2.5"

            gate_mode = (
                self.window.comboGateMode.currentData()
                if hasattr(self.window, "comboGateMode")
                else "FULL"
            )

            news_filter = (
                self.window.chkNewsFilter.isChecked()
                if hasattr(self.window, "chkNewsFilter")
                else True
            )

            news_pause_mins = (
                self.window.spinNewsPause.value()
                if hasattr(self.window, "spinNewsPause")
                else 30
            )

            slippage = (
                self.window.spinSlippage.value()
                if hasattr(self.window, "spinSlippage")
                else 20
            )

            # Khởi tạo các thành phần cốt lõi và tiêm (inject) vào BotWorker

            from backend.core.risk_manager import RiskManager

            from backend.infrastructure.brokers.execution_manager import ExecutionManager

            from backend.core.preprocessor import DataPreprocessor

            from backend.core.strategies.ict_strategy import ICTZonesProStrategy

            from backend.core.strategies.ema_stress_test import EMAStressTestStrategy

            from backend.infrastructure.ai_engines.ai.decision_gate import DecisionGate

            from backend.core.bot_worker import DEFAULT_LOOKBACK_BARS

            risk_mgr = RiskManager(default_risk_pct=1.0)

            exec_mgr = ExecutionManager(slippage=slippage)

            prep = DataPreprocessor()

            active_strat = None
            try:
                from backend.core.strategies.strategy_loader import discover_strategies, load_strategy_instance
                for s in discover_strategies():
                    if s["id"] == strategy or s["name"].lower() == str(strategy).lower():
                        active_strat = load_strategy_instance(s["file_path"], s["class_name"])
                        break
            except Exception as e_load:
                logger.debug(f"[Main] Dynamic strategy load error: {e_load}")

            if active_strat is None:
                strat_str = str(strategy).lower()
                if "ema" in strat_str:
                    active_strat = EMAStressTestStrategy(
                        config={"fast_period": 10, "slow_period": 50}
                    )
                elif "wyckoff" in strat_str:
                    from backend.core.strategies.wyckoff_vectorized import WyckoffMomentumStrategy
                    active_strat = WyckoffMomentumStrategy()
                else:
                    active_strat = ICTZonesProStrategy(
                        config={"lookback_bars": DEFAULT_LOOKBACK_BARS}
                    )

            gate = DecisionGate()

            # Get UI Values

            r_risk = (
                self.window.spinRiskPerTrade.value()
                if hasattr(self.window, "spinRiskPerTrade")
                else float(cfg_d.get("risk_per_trade", 1.0))
            )

            r_max_daily_loss = (
                self.window.spinMaxDailyLoss.value()
                if hasattr(self.window, "spinMaxDailyLoss")
                else float(cfg_d.get("max_daily_loss", 500.0))
            )

            r_maxdd = (
                self.window.spinMaxDrawdown.value()
                if hasattr(self.window, "spinMaxDrawdown")
                else float(cfg_d.get("max_drawdown", 5.0))
            )

            r_maxloss = (
                self.window.spinMaxLosingStreak.value()
                if hasattr(self.window, "spinMaxLosingStreak")
                else int(cfg_d.get("max_losing_streak", 3))
            )

            r_max_open_trades = (
                self.window.spinMaxOpenTrades.value()
                if hasattr(self.window, "spinMaxOpenTrades")
                else int(cfg_d.get("max_open_trades", 3))
            )

            close_friday = (
                self.window.chkCloseFriday.isChecked()
                if hasattr(self.window, "chkCloseFriday")
                else bool(cfg_d.get("close_friday", True))
            )

            max_spread = (
                self.window.spinMaxSpread.value()
                if hasattr(self.window, "spinMaxSpread")
                else int(cfg_d.get("max_spread", 25))
            )

            enable_ts = (
                self.window.chkEnableTrailing.isChecked()
                if hasattr(self.window, "chkEnableTrailing")
                else bool(cfg_d.get("enable_trailing_stop", False))
            )

            r_trail = (
                self.window.spinTrailingPips.value()
                if hasattr(self.window, "spinTrailingPips")
                else int(cfg_d.get("trailing_pips", 0))
            )

            r_be = (
                self.window.spinBreakevenPips.value()
                if hasattr(self.window, "spinBreakevenPips")
                else int(cfg_d.get("breakeven_pips", 0))
            )

            news_defense_enabled = (
                self.window.chkNewsDefense.isChecked()
                if hasattr(self.window, "chkNewsDefense")
                else bool(cfg_d.get("news_defense_enabled", True))
            )

            news_defense_mins = (
                self.window.spinNewsDefenseMins.value()
                if hasattr(self.window, "spinNewsDefenseMins")
                else int(cfg_d.get("news_defense_mins", 15))
            )

            news_defense_be_r = (
                self.window.spinNewsDefenseR.value()
                if hasattr(self.window, "spinNewsDefenseR")
                else float(cfg_d.get("news_defense_be_r", 1.5))
            )

            # Sessions

            allowed_sessions = []

            if (
                hasattr(self.window, "chkSessionAsian")
                and self.window.chkSessionAsian.isChecked()
            ):
                allowed_sessions.append("ASIAN")

            if (
                hasattr(self.window, "chkSessionLondon")
                and self.window.chkSessionLondon.isChecked()
            ):
                allowed_sessions.append("LONDON")

            if (
                hasattr(self.window, "chkSessionNY")
                and self.window.chkSessionNY.isChecked()
            ):
                allowed_sessions.append("NY")

            active_symbols = self.watchlist.get_all_symbols() if self.watchlist else []

            self.bot_worker = BotWorker(
                strategy=active_strat,
                risk_manager=risk_mgr,
                execution_manager=exec_mgr,
                data_preprocessor=prep,
                decision_gate=gate,
                symbols=active_symbols,
                timeframe=tf,
                strategy_name=strategy,
                ai_model_name=ai_model,
                gate_mode=gate_mode,
                news_filter_enabled=news_filter,
                news_pause_mins=news_pause_mins,
                slippage=slippage,
                risk_per_trade=r_risk,
                max_daily_loss=r_max_daily_loss,
                max_drawdown=r_maxdd,
                max_losing_streak=r_maxloss,
                max_open_trades=r_max_open_trades,
                max_spread=max_spread,
                close_friday=close_friday,
                enable_trailing_stop=enable_ts,
                trailing_pips=r_trail,
                breakeven_pips=r_be,
                news_defense_enabled=news_defense_enabled,
                defense_window_mins=news_defense_mins,
                news_defense_be_r=news_defense_be_r,
                allowed_sessions=allowed_sessions,
            )
            self.bot_worker.symbols_provider = lambda: self.watchlist.get_all_symbols() if self.watchlist else []

            self.bot_worker.signals.log_msg.connect(event_bus.log_event.emit)

            if hasattr(self.window, "comboBias"):

                self.bot_worker.trade_mode = self.window.comboBias.currentData()

            self.bot_thread = QThread()

            self.bot_worker.moveToThread(self.bot_thread)

            self.bot_thread.started.connect(self.bot_worker.start_working)

            self.bot_thread.start()

            strat_name = (
                self.window.comboStrategy.currentText()
                if hasattr(self.window, "comboStrategy")
                else "ICT"
            )
            tf_name = getattr(self, "_active_bot_tf_str", "M15")
            self.btnStart.setText(f"{chr(9679)}  BOT: ACTIVE ({strat_name} {tf_name})")
            self.btnStart.setToolTip("Bot is running! Click to PAUSE bot")
            if hasattr(self, "btn_bot_power"):
                if hasattr(self.btn_bot_power, "set_running"):
                    self.btn_bot_power.set_running(True, emit_signal=False)
                else:
                    self.btn_bot_power.setProperty("running", "true")
            if hasattr(self, "header") and hasattr(self.header, "btn_algo_toggle") and self.header.btn_algo_toggle:
                if hasattr(self.header.btn_algo_toggle, "set_running"):
                    self.header.btn_algo_toggle.set_running(True)
            self.btnStart.style().unpolish(self.btnStart)
            self.btnStart.style().polish(self.btnStart)
            if hasattr(self, "header") and hasattr(self.header, "_refresh_top_ticker"):
                self.header._refresh_top_ticker()

            # --- GỬI THÔNG BÁO TELEGRAM CHI TIẾT ---

            tf_name = (
                self.window.comboTimeframe.currentText()
                if hasattr(self.window, "comboTimeframe")
                else "M15"
            )

            strat_name = (
                self.window.comboStrategy.currentText()
                if hasattr(self.window, "comboStrategy")
                else "ICT"
            )

            try:
                import shiboken6
                ai_name = (
                    self.window.comboAIModel.currentText()
                    if hasattr(self.window, "comboAIModel")
                    and self.window.comboAIModel is not None
                    and shiboken6.isValid(self.window.comboAIModel)
                    and self.window.comboAIModel.count() > 0
                    else "qwen2.5"
                )
            except Exception:
                ai_name = "qwen2.5"

            gate_mode_display = (
                self.window.comboGateMode.currentText()
                if hasattr(self.window, "comboGateMode")
                else "Day du"
            )

            syms_display = ", ".join(active_symbols) if active_symbols else "None (0 symbols in watchlist)"
            msg = (
                f"<b>[SYSTEM INITIALIZED]</b>\n"
                f"Trading engine activated successfully!\n\n"
                f"<b>Active Configuration:</b>\n"
                f"- Watchlist: {syms_display}\n"
                f"- Timeframe: {tf_name}\n"
                f"- Strategy: {strat_name}\n"
                f"- Decision Gate: {gate_mode_display}\n"
                f"- AI Engine: {ai_name}\n"
                f"- Risk Per Trade: {r_risk:.1f}%\n\n"
                f"<i>Awaiting real market signals...</i>"
            )

            telegram_notifier.send_message(msg)

        else:

            if self.bot_worker:

                self.bot_worker.stop()

            if self.bot_thread:

                self.bot_thread.quit()

                self.bot_thread.wait()

            self.bot_thread = None

            self.bot_worker = None

            telegram_notifier.send_message(
                "<b>[SYSTEM PAUSED]</b>\nTrading bot paused safely."
            )

            self._active_bot_tf_str = ""
            self.btnStart.setText(_TXT_START)
            self.btnStart.setToolTip("Click to START automated trading bot")
            self.btnStart.setProperty("running", "false")
        if hasattr(self, "btn_bot_power"):
            if hasattr(self.btn_bot_power, "set_running"):
                self.btn_bot_power.set_running(False, emit_signal=False)
            else:
                self.btn_bot_power.setProperty("running", "false")
        if hasattr(self, "header") and hasattr(self.header, "btn_algo_toggle") and self.header.btn_algo_toggle:
            if hasattr(self.header.btn_algo_toggle, "set_running"):
                self.header.btn_algo_toggle.set_running(False)
            self.btnStart.style().unpolish(self.btnStart)
            self.btnStart.style().polish(self.btnStart)
        if hasattr(self, "header") and hasattr(self.header, "_refresh_top_ticker"):
            self.header._refresh_top_ticker()

    def _on_tab_changed(self, index):

        if index == 2:

            self.stats.refresh()

    def closeEvent(self, event):
        if self._tick_timer.isActive():
            self._tick_timer.stop()
        if self.bot_thread and self.bot_thread.isRunning():
            if self.bot_worker:
                self.bot_worker.stop()
            if self.bot_thread:
                self.bot_thread.quit()
                self.bot_thread.wait(1000)
        # Cho phep cac luong AI hoan tat truoc khi giai phong de tranh warning
        if hasattr(self.window, "_active_ai_threads") and self.window._active_ai_threads:
            for t in list(self.window._active_ai_threads):
                if t and t.isRunning():
                    if hasattr(t, "stop"):
                        t.stop()
                    t.quit()
                    t.wait(500)
        elif (
            hasattr(self.window, "ai_thread")
            and self.window.ai_thread
            and self.window.ai_thread.isRunning()
        ):
            if hasattr(self.window.ai_thread, "stop"):
                self.window.ai_thread.stop()
            self.window.ai_thread.quit()
            self.window.ai_thread.wait(500)
        if event:
            event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    from frontend.widgets.splash_screen import InitWorker

    terminal = QuantTerminal(with_overlay=True)

    worker = InitWorker()
    if terminal.overlay:
        worker.progress.connect(terminal.overlay.update_progress)
        worker.init_done.connect(lambda: terminal.overlay.fade_out_and_destroy(350))
    worker.start()

    sys.exit(app.exec())
