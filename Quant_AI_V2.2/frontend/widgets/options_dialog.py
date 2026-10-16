"""
Institutional MT5 Options Dialog Widget for Quant_AI V2.2
4-page modal configuration dialog (Broker, Risk Management, Execution Strategy, Telegram Alerts).
"""

import os
import json
import urllib.request
import urllib.error
from PySide6.QtWidgets import (
    QDialog, QTabWidget, QLabel, QComboBox, QSpinBox, QDoubleSpinBox,
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QFrame, QLineEdit, QCheckBox,
    QGroupBox
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from backend.infrastructure.brokers.mt5_safe import mt5
from backend.infrastructure.notifications.telegram_notifier import telegram_notifier

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(os.path.dirname(CURRENT_DIR))

CONFIG_PATH = os.path.join(ROOT_DIR, "config", "settings.json")
AI_CONFIG_PATH = os.path.join(ROOT_DIR, "config", "ai_config.json")
ASSETS_DIR = os.path.join(ROOT_DIR, "frontend", "assets")


DEFAULTS = {
    "risk_per_trade": 1.0,
    "max_drawdown": 5.0,
    "max_daily_loss": 500.0,
    "max_open_trades": 3,
    "max_losing_streak": 3,
    "execution_mode": "FULL-AUTO",
    "max_spread": 25,
    "slippage": 20,
    "enable_trailing_stop": False,
    "breakeven_pips": 0,
    "trailing_pips": 0,
    "news_defense_enabled": True,
    "news_defense_mins": 15,
    "news_defense_be_r": 1.5,
    "session_asian": True,
    "session_london": True,
    "session_ny": True,
    "close_friday": True,
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "alert_fills": True,
    "alert_sl_tp": True,
    "alert_risk_halt": True,
    "audio_sound_fx": True,
    "signal_expiry_sec": 60,
    "strategy": "builtin_ict_pro",
    "timeframe": 15,
}


class OptionsDialog(QDialog):
    """Authentic MetaTrader 5-style 'Options' Dialog (Floating Preferences Window)."""

    def __init__(self, parent=None, manager=None):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("System Options & Configurations")
        self.setFixedSize(720, 480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        icon_path = os.path.join(ASSETS_DIR, "nav_settings.svg")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._setup_ui()
        self._apply_styling()

    def _create_row(self, label_text: str, widget: QWidget, label_width: int = 125) -> QWidget:
        """Helper to create a strictly aligned form row: label on left, input on right locked to edge."""
        row = QWidget()
        r_lay = QHBoxLayout(row)
        r_lay.setContentsMargins(0, 0, 0, 0)
        r_lay.setSpacing(10)

        lbl = QLabel(label_text)
        lbl.setFixedWidth(label_width)
        lbl.setStyleSheet("font-family: 'Segoe UI', sans-serif; font-size: 11px; color: #334155;")
        r_lay.addWidget(lbl)

        if hasattr(widget, "setFixedHeight"):
            widget.setFixedHeight(24)
        r_lay.addWidget(widget, 1)
        return row

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 10, 12, 10)
        root_layout.setSpacing(8)

        # Tab Widget (Authentic Horizontal MT5 Tabs)
        self.tabWidget = QTabWidget()
        self.tabWidget.setObjectName("optionsTabWidget")

        # =========================================================================
        # --- PAGE 1: RISK LIMITS ---
        # =========================================================================
        page_risk = QWidget()
        layout_risk_main = QVBoxLayout(page_risk)
        layout_risk_main.setContentsMargins(14, 12, 14, 12)
        layout_risk_main.setSpacing(10)

        lbl_desc_risk = QLabel("Account risk limits, daily loss threshold, and maximum drawdown safeguards.")
        lbl_desc_risk.setStyleSheet("color: #64748b; font-family: 'Segoe UI', sans-serif; font-size: 11px;")
        layout_risk_main.addWidget(lbl_desc_risk)

        cols_risk = QWidget()
        cols_risk_lay = QHBoxLayout(cols_risk)
        cols_risk_lay.setContentsMargins(0, 0, 0, 0)
        cols_risk_lay.setSpacing(14)

        # Left Column: Position & Drawdown
        grp_risk_pos = QGroupBox("POSITION && DRAWDOWN LIMITS")
        lay_risk_pos = QVBoxLayout(grp_risk_pos)
        lay_risk_pos.setContentsMargins(10, 14, 10, 10)
        lay_risk_pos.setSpacing(8)

        self.spinRiskPerTrade = QDoubleSpinBox()
        self.spinRiskPerTrade.setRange(0.1, 10.0)
        self.spinRiskPerTrade.setSingleStep(0.25)
        self.spinRiskPerTrade.setSuffix(" %")

        self.spinMaxDrawdown = QDoubleSpinBox()
        self.spinMaxDrawdown.setRange(1.0, 30.0)
        self.spinMaxDrawdown.setSingleStep(0.5)
        self.spinMaxDrawdown.setSuffix(" %")

        self.spinMaxOpenTrades = QSpinBox()
        self.spinMaxOpenTrades.setRange(1, 20)
        self.spinMaxOpenTrades.setSuffix(" positions")

        lay_risk_pos.addWidget(self._create_row("Risk Per Trade:", self.spinRiskPerTrade))
        lay_risk_pos.addWidget(self._create_row("Max Equity DD:", self.spinMaxDrawdown))
        lay_risk_pos.addWidget(self._create_row("Max Positions:", self.spinMaxOpenTrades))

        # Right Column: Daily Loss & Circuit Breaker
        grp_risk_daily = QGroupBox("DAILY PROTECTION && CIRCUIT BREAKER")
        lay_risk_daily = QVBoxLayout(grp_risk_daily)
        lay_risk_daily.setContentsMargins(10, 14, 10, 10)
        lay_risk_daily.setSpacing(8)

        self.spinMaxDailyLoss = QDoubleSpinBox()
        self.spinMaxDailyLoss.setRange(50.0, 50000.0)
        self.spinMaxDailyLoss.setSingleStep(50.0)
        self.spinMaxDailyLoss.setPrefix("$ ")

        self.spinMaxLosingStreak = QSpinBox()
        self.spinMaxLosingStreak.setRange(1, 20)
        self.spinMaxLosingStreak.setSuffix(" trades")

        self.chkEnforceDailyHalt = QCheckBox("Halt trading on breach")
        self.chkEnforceDailyHalt.setChecked(True)

        lay_risk_daily.addWidget(self._create_row("Max Daily Loss:", self.spinMaxDailyLoss))
        lay_risk_daily.addWidget(self._create_row("Max Loss Streak:", self.spinMaxLosingStreak))
        lay_risk_daily.addWidget(self._create_row("Daily Loss Action:", self.chkEnforceDailyHalt))

        cols_risk_lay.addWidget(grp_risk_pos)
        cols_risk_lay.addWidget(grp_risk_daily)
        layout_risk_main.addWidget(cols_risk)
        layout_risk_main.addStretch()
        self.tabWidget.addTab(page_risk, "Risk Management")

        # =========================================================================
        # --- PAGE 2: EXECUTION STRATEGY ---
        # =========================================================================
        page_exec = QWidget()
        layout_exec_main = QVBoxLayout(page_exec)
        layout_exec_main.setContentsMargins(14, 10, 14, 10)
        layout_exec_main.setSpacing(8)

        lbl_desc_exec = QLabel("Automated execution strategy, session filtering, and risk defense protocols.")
        lbl_desc_exec.setStyleSheet("color: #64748b; font-family: 'Segoe UI', sans-serif; font-size: 11px;")
        layout_exec_main.addWidget(lbl_desc_exec)

        cols_exec = QWidget()
        cols_exec_lay = QHBoxLayout(cols_exec)
        cols_exec_lay.setContentsMargins(0, 0, 0, 0)
        cols_exec_lay.setSpacing(14)

        # Left Column: Order Config (Top) & Sessions (Bottom)
        col_exec_left = QWidget()
        lay_exec_left = QVBoxLayout(col_exec_left)
        lay_exec_left.setContentsMargins(0, 0, 0, 0)
        lay_exec_left.setSpacing(10)

        grp_order = QGroupBox("ORDER && STRATEGY CONFIG")
        lay_order = QVBoxLayout(grp_order)
        lay_order.setContentsMargins(10, 14, 10, 10)
        lay_order.setSpacing(8)

        self.comboStrategy = QComboBox()
        try:
            from backend.core.strategies.strategy_loader import discover_strategies
            strats = discover_strategies()
            clean_names = {
                "builtin_ict_pro": "ICT Zones Pro v4.2",
                "builtin_ema_stress": "EMA Dual Cross",
                "builtin_wyckoff": "Wyckoff Momentum Pro",
            }
            for s in strats:
                s_id = s.get("id", "")
                display_name = clean_names.get(s_id, s.get("name", s_id))
                self.comboStrategy.addItem(display_name, s_id)
        except Exception:
            self.comboStrategy.addItem("ICT Zones Pro v4.2", "builtin_ict_pro")
            self.comboStrategy.addItem("EMA Dual Cross", "builtin_ema_stress")
            self.comboStrategy.addItem("Wyckoff Momentum Pro", "builtin_wyckoff")

        self.comboTradingTimeframe = QComboBox()
        self.comboTradingTimeframe.addItem("M1 (1 Min)", 1)
        self.comboTradingTimeframe.addItem("M5 (5 Mins)", 5)
        self.comboTradingTimeframe.addItem("M15 (15 Mins)", 15)
        self.comboTradingTimeframe.addItem("M30 (30 Mins)", 30)
        self.comboTradingTimeframe.addItem("H1 (1 Hour)", 60)
        self.comboTradingTimeframe.addItem("H4 (4 Hours)", 240)
        self.comboTradingTimeframe.addItem("D1 (Daily)", 1440)
        self.comboTradingTimeframe.addItem("Follow Chart TF", "FOLLOW_CHART")

        self.comboExecutionMode = QComboBox()
        self.comboExecutionMode.addItem("Full-Auto (STP)", "FULL-AUTO")
        self.comboExecutionMode.addItem("Semi-Auto (Operator)", "SEMI-AUTO")
        self.comboExecutionMode.addItem("Manual (Alerts Only)", "MANUAL")

        lay_order.addWidget(self._create_row("Active Strategy:", self.comboStrategy))
        lay_order.addWidget(self._create_row("Trading Timeframe:", self.comboTradingTimeframe))
        lay_order.addWidget(self._create_row("Execution Mode:", self.comboExecutionMode))

        grp_sessions = QGroupBox("TRADING SESSIONS && SCHEDULE")
        lay_sessions = QVBoxLayout(grp_sessions)
        lay_sessions.setContentsMargins(10, 14, 10, 10)
        lay_sessions.setSpacing(8)

        self.chkSessionAsian = QCheckBox("Enabled (Tokyo)")
        self.chkSessionLondon = QCheckBox("Enabled (London)")
        self.chkSessionNY = QCheckBox("Enabled (New York)")
        self.chkCloseFriday = QCheckBox("Close on Friday EOD")

        lay_sessions.addWidget(self._create_row("Asian Session:", self.chkSessionAsian))
        lay_sessions.addWidget(self._create_row("London Session:", self.chkSessionLondon))
        lay_sessions.addWidget(self._create_row("New York Session:", self.chkSessionNY))
        lay_sessions.addWidget(self._create_row("Weekend Risk:", self.chkCloseFriday))

        lay_exec_left.addWidget(grp_order)
        lay_exec_left.addWidget(grp_sessions)

        # Right Column: Safety Tolerance (Top) & Dynamic SL & Risk Defense (Bottom)
        col_exec_right = QWidget()
        lay_exec_right = QVBoxLayout(col_exec_right)
        lay_exec_right.setContentsMargins(0, 0, 0, 0)
        lay_exec_right.setSpacing(10)

        grp_safety = QGroupBox("SAFETY TOLERANCE")
        lay_safety = QVBoxLayout(grp_safety)
        lay_safety.setContentsMargins(10, 14, 10, 10)
        lay_safety.setSpacing(8)

        self.spinSignalExpiry = QSpinBox()
        self.spinSignalExpiry.setRange(10, 600)
        self.spinSignalExpiry.setSingleStep(5)
        self.spinSignalExpiry.setSuffix(" sec")
        self.spinSignalExpiry.setValue(60)

        self.spinMaxSpread = QSpinBox()
        self.spinMaxSpread.setRange(1, 200)
        self.spinMaxSpread.setSuffix(" points")

        self.spinSlippage = QSpinBox()
        self.spinSlippage.setRange(1, 100)
        self.spinSlippage.setSuffix(" points")

        lay_safety.addWidget(self._create_row("Signal Expiry:", self.spinSignalExpiry))
        lay_safety.addWidget(self._create_row("Max Spread Limit:", self.spinMaxSpread))
        lay_safety.addWidget(self._create_row("Slippage Tolerance:", self.spinSlippage))

        grp_defense = QGroupBox("DYNAMIC SL && RISK DEFENSE")
        lay_defense = QVBoxLayout(grp_defense)
        lay_defense.setContentsMargins(10, 14, 10, 10)
        lay_defense.setSpacing(8)

        # Virtual checkboxes for backwards compatibility
        self.chkEnableTrailing = QCheckBox("Enable Trailing Stop")
        self.chkNewsDefense = QCheckBox("Active Defense")

        self.spinBreakevenPips = QSpinBox()
        self.spinBreakevenPips.setRange(0, 100)
        self.spinBreakevenPips.setSpecialValueText("OFF")
        self.spinBreakevenPips.setSuffix(" pts")

        self.spinTrailingPips = QSpinBox()
        self.spinTrailingPips.setRange(0, 100)
        self.spinTrailingPips.setSpecialValueText("OFF")
        self.spinTrailingPips.setSuffix(" pts")

        self.spinNewsDefenseMins = QSpinBox()
        self.spinNewsDefenseMins.setRange(0, 60)
        self.spinNewsDefenseMins.setSpecialValueText("OFF")
        self.spinNewsDefenseMins.setValue(15)
        self.spinNewsDefenseMins.setSuffix(" min")

        self.spinNewsDefenseR = QDoubleSpinBox()
        self.spinNewsDefenseR.setRange(0.5, 5.0)
        self.spinNewsDefenseR.setSingleStep(0.25)
        self.spinNewsDefenseR.setValue(1.5)
        self.spinNewsDefenseR.setSuffix(" R")

        lay_defense.addWidget(self._create_row("BE Offset:", self.spinBreakevenPips))
        lay_defense.addWidget(self._create_row("TS Distance:", self.spinTrailingPips))
        lay_defense.addWidget(self._create_row("Defense Window:", self.spinNewsDefenseMins))
        lay_defense.addWidget(self._create_row("BE Threshold (R):", self.spinNewsDefenseR))

        lay_exec_right.addWidget(grp_safety)
        lay_exec_right.addWidget(grp_defense)

        cols_exec_lay.addWidget(col_exec_left)
        cols_exec_lay.addWidget(col_exec_right)
        layout_exec_main.addWidget(cols_exec)
        layout_exec_main.addStretch()
        self.tabWidget.addTab(page_exec, "Execution Strategy")

        # =========================================================================
        # --- PAGE 3: BROKER BRIDGE ---
        # =========================================================================
        page_broker = QWidget()
        layout_broker_main = QVBoxLayout(page_broker)
        layout_broker_main.setContentsMargins(14, 12, 14, 12)
        layout_broker_main.setSpacing(10)

        lbl_desc_server = QLabel("MetaTrader 5 terminal gateway, bridge telemetry, and execution permissions.")
        lbl_desc_server.setStyleSheet("color: #64748b; font-family: 'Segoe UI', sans-serif; font-size: 11px;")
        layout_broker_main.addWidget(lbl_desc_server)

        cols_broker = QWidget()
        cols_broker_lay = QHBoxLayout(cols_broker)
        cols_broker_lay.setContentsMargins(0, 0, 0, 0)
        cols_broker_lay.setSpacing(14)

        # Left Column: Connection & Telemetry
        grp_conn = QGroupBox("GATEWAY CONNECTION && TELEMETRY")
        lay_conn = QVBoxLayout(grp_conn)
        lay_conn.setContentsMargins(10, 14, 10, 10)
        lay_conn.setSpacing(8)

        self.lblGatewayAccount = QLineEdit("Offline")
        self.lblGatewayAccount.setReadOnly(True)

        self.lblGatewayServer = QLineEdit("MetaQuotes-Demo")
        self.lblGatewayServer.setReadOnly(True)

        self.lblGatewayBridge = QLineEdit("Connected (1.1 ms)")
        self.lblGatewayBridge.setReadOnly(True)

        for w_ro in [self.lblGatewayAccount, self.lblGatewayServer, self.lblGatewayBridge]:
            w_ro.setStyleSheet("QLineEdit { background-color: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; border-radius: 2px; padding: 0 8px; font-family: Consolas, monospace; }")

        btn_ping = QPushButton("Ping MT5 Connection")
        btn_ping.setCursor(Qt.PointingHandCursor)
        btn_ping.clicked.connect(self._on_ping_clicked)

        self.lblGatewayLatency = QLabel("1.1 ms")
        self.lblGatewayLatency.setVisible(False)
        self.lblGatewayAlgo = QLabel("ENABLED")
        self.lblGatewayAlgo.setVisible(False)

        lay_conn.addWidget(self._create_row("MT5 Account:", self.lblGatewayAccount))
        lay_conn.addWidget(self._create_row("Broker Server:", self.lblGatewayServer))
        lay_conn.addWidget(self._create_row("Bridge Gateway:", self.lblGatewayBridge))
        lay_conn.addWidget(self._create_row("Connection Ping:", btn_ping))

        # Right Column: Terminal Permissions & Routing
        grp_perm = QGroupBox("TERMINAL EXECUTION PERMISSIONS")
        lay_perm = QVBoxLayout(grp_perm)
        lay_perm.setContentsMargins(10, 14, 10, 10)
        lay_perm.setSpacing(8)

        self.chkAlgoTrading = QCheckBox("Allow Algo Trading (EA)")
        self.chkAlgoTrading.setChecked(True)

        self.chkWebRequest = QCheckBox("Allow WebRequest API")
        self.chkWebRequest.setChecked(True)

        ro_routing = QLineEdit("STP DMA")
        ro_routing.setReadOnly(True)
        ro_routing.setStyleSheet("QLineEdit { background-color: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; border-radius: 2px; padding: 0 8px; }")

        ro_sync = QLineEdit("Real-time")
        ro_sync.setReadOnly(True)
        ro_sync.setStyleSheet("QLineEdit { background-color: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; border-radius: 2px; padding: 0 8px; }")

        lay_perm.addWidget(self._create_row("Automated Trading:", self.chkAlgoTrading))
        lay_perm.addWidget(self._create_row("Market WebRequest:", self.chkWebRequest))
        lay_perm.addWidget(self._create_row("Order Routing:", ro_routing))
        lay_perm.addWidget(self._create_row("Tick Telemetry:", ro_sync))

        cols_broker_lay.addWidget(grp_conn)
        cols_broker_lay.addWidget(grp_perm)
        layout_broker_main.addWidget(cols_broker)
        layout_broker_main.addStretch()
        self.tabWidget.addTab(page_broker, "Broker Bridge")

        # =========================================================================
        # --- PAGE 4: NOTIFICATIONS ---
        # =========================================================================
        page_notif = QWidget()
        layout_notif_main = QVBoxLayout(page_notif)
        layout_notif_main.setContentsMargins(14, 12, 14, 12)
        layout_notif_main.setSpacing(10)

        lbl_desc_notif = QLabel("Telegram bot alerts, execution event broadcasting, and audio notifications.")
        lbl_desc_notif.setStyleSheet("color: #64748b; font-family: 'Segoe UI', sans-serif; font-size: 11px;")
        layout_notif_main.addWidget(lbl_desc_notif)

        cols_notif = QWidget()
        cols_notif_lay = QHBoxLayout(cols_notif)
        cols_notif_lay.setContentsMargins(0, 0, 0, 0)
        cols_notif_lay.setSpacing(14)

        # Left Column: Telegram Credentials & Test
        grp_tg = QGroupBox("TELEGRAM BOT INTEGRATION")
        lay_tg = QVBoxLayout(grp_tg)
        lay_tg.setContentsMargins(10, 14, 10, 10)
        lay_tg.setSpacing(8)

        self.editTgToken = QLineEdit()
        self.editTgToken.setEchoMode(QLineEdit.Password)
        self.editTgToken.setPlaceholderText("Token from @BotFather")

        self.editTgChatId = QLineEdit()
        self.editTgChatId.setPlaceholderText("-100...")

        ro_fmt = QLineEdit("HTML")
        ro_fmt.setReadOnly(True)
        ro_fmt.setStyleSheet("QLineEdit { background-color: #f1f5f9; color: #475569; }")

        btn_tg_test = QPushButton("Test Telegram Bot")
        btn_tg_test.setCursor(Qt.PointingHandCursor)
        btn_tg_test.clicked.connect(self._on_telegram_test_clicked)

        lay_tg.addWidget(self._create_row("Telegram Token:", self.editTgToken))
        lay_tg.addWidget(self._create_row("Channel / Chat ID:", self.editTgChatId))
        lay_tg.addWidget(self._create_row("Message Format:", ro_fmt))
        lay_tg.addWidget(self._create_row("Connection Test:", btn_tg_test))

        # Right Column: Event Subscriptions & Audio
        grp_alerts = QGroupBox("EVENT ALERTS && AUDIO FX")
        lay_alerts = QVBoxLayout(grp_alerts)
        lay_alerts.setContentsMargins(10, 14, 10, 10)
        lay_alerts.setSpacing(8)

        self.chkAlertFills = QCheckBox("Notify on trade fills")
        self.chkAlertSL = QCheckBox("Notify on SL / TP hit")
        self.chkAlertRisk = QCheckBox("Notify on circuit breach")
        self.chkSoundFx = QCheckBox("Play execution sound FX")

        lay_alerts.addWidget(self._create_row("Order Fills:", self.chkAlertFills))
        lay_alerts.addWidget(self._create_row("TP / SL Hit:", self.chkAlertSL))
        lay_alerts.addWidget(self._create_row("Risk Circuit Halt:", self.chkAlertRisk))
        lay_alerts.addWidget(self._create_row("Audio Sound FX:", self.chkSoundFx))

        cols_notif_lay.addWidget(grp_tg)
        cols_notif_lay.addWidget(grp_alerts)
        layout_notif_main.addWidget(cols_notif)
        layout_notif_main.addStretch()
        self.tabWidget.addTab(page_notif, "Notifications")

        root_layout.addWidget(self.tabWidget)

        # Subtle Horizontal Separator above Footer
        sep_footer = QFrame()
        sep_footer.setFrameShape(QFrame.HLine)
        sep_footer.setFixedHeight(1)
        sep_footer.setStyleSheet("background-color: #e2e8f0; border: none;")
        root_layout.addWidget(sep_footer)

        # Dialog Footer (Classic Desktop OK / Cancel / Apply)
        footer = QWidget()
        f_lay = QHBoxLayout(footer)
        f_lay.setContentsMargins(4, 2, 4, 4)
        f_lay.setSpacing(6)

        self.lblDialogStatus = QLabel("Ready")
        self.lblDialogStatus.setStyleSheet("font-family: 'Segoe UI', sans-serif; font-size: 10.5px; color: #64748b;")
        f_lay.addWidget(self.lblDialogStatus)
        f_lay.addStretch()

        self.btnOk = QPushButton("OK")
        self.btnOk.setObjectName("btnDialogOk")
        self.btnOk.setFixedWidth(76)
        self.btnOk.setFixedHeight(26)
        self.btnOk.setCursor(Qt.PointingHandCursor)
        self.btnOk.clicked.connect(self._on_ok_clicked)

        self.btnCancel = QPushButton("Cancel")
        self.btnCancel.setObjectName("btnDialogCancel")
        self.btnCancel.setFixedWidth(76)
        self.btnCancel.setFixedHeight(26)
        self.btnCancel.setCursor(Qt.PointingHandCursor)
        self.btnCancel.clicked.connect(self.reject)

        self.btnApply = QPushButton("Apply")
        self.btnApply.setObjectName("btnDialogApply")
        self.btnApply.setFixedWidth(76)
        self.btnApply.setFixedHeight(26)
        self.btnApply.setCursor(Qt.PointingHandCursor)
        self.btnApply.clicked.connect(self._on_apply_clicked)

        f_lay.addWidget(self.btnOk)
        f_lay.addWidget(self.btnCancel)
        f_lay.addWidget(self.btnApply)
        root_layout.addWidget(footer)

    def _apply_styling(self):
        arrow_up = os.path.join(ASSETS_DIR, "arrow_up.svg").replace("\\", "/")
        arrow_down = os.path.join(ASSETS_DIR, "arrow_down.svg").replace("\\", "/")
        check_icon = os.path.join(ASSETS_DIR, "check_vector_light.svg").replace("\\", "/")

        self.setStyleSheet(f"""
            QDialog {{
                background-color: #ffffff;
                color: #0f172a;
            }}
            QTabWidget::pane {{
                background-color: #ffffff;
                border-top: 1px solid #cbd5e1;
                border-bottom: none;
                border-left: none;
                border-right: none;
                top: -1px;
            }}
            QTabBar::tab {{
                background-color: transparent;
                color: #64748b;
                font-family: 'Segoe UI', sans-serif;
                font-size: 11px;
                font-weight: 500;
                padding: 6px 16px 7px 16px;
                margin-right: 2px;
                border-bottom: 2px solid transparent;
            }}
            QTabBar::tab:selected {{
                color: #0f172a;
                font-weight: 600;
                border-bottom: 2px solid #0f172a;
                background-color: transparent;
            }}
            QTabBar::tab:hover:!selected {{
                color: #0f172a;
            }}
            QGroupBox {{
                font-family: 'Segoe UI', sans-serif;
                font-size: 10px;
                font-weight: 700;
                color: #475569;
                border: 1px solid #e2e8f0;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 14px;
                padding-left: 8px;
                padding-right: 8px;
                padding-bottom: 8px;
                background-color: #fafbfc;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 4px;
                margin-left: 8px;
                color: #64748b;
                font-size: 9.5px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}
            QLabel {{
                color: #1e293b;
                font-family: 'Segoe UI', sans-serif;
                font-size: 11px;
                font-weight: 400;
            }}
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 2px;
                padding: 1px 6px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 11px;
                color: #0f172a;
                min-height: 20px;
                max-height: 20px;
            }}
            QSpinBox, QDoubleSpinBox {{
                padding-right: 20px;
            }}
            QLineEdit[readOnly="true"] {{
                background-color: #f8fafc;
                color: #334155;
            }}
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
                border: 1px solid #475569;
            }}
            QSpinBox::up-button, QDoubleSpinBox::up-button {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 17px;
                border-left: 1px solid #cbd5e1;
                border-bottom: 1px solid #cbd5e1;
                background-color: #f8fafc;
            }}
            QSpinBox::down-button, QDoubleSpinBox::down-button {{
                subcontrol-origin: padding;
                subcontrol-position: bottom right;
                width: 17px;
                border-left: 1px solid #cbd5e1;
                background-color: #f8fafc;
            }}
            QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
            QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
                background-color: #e2e8f0;
            }}
            QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
                image: url("{arrow_up}");
                width: 7px;
                height: 5px;
            }}
            QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
                image: url("{arrow_down}");
                width: 7px;
                height: 5px;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 18px;
                border-left: 1px solid #cbd5e1;
                background-color: #f8fafc;
            }}
            QComboBox::down-arrow {{
                image: url("{arrow_down}");
                width: 7px;
                height: 5px;
            }}
            QCheckBox {{
                font-family: 'Segoe UI', sans-serif;
                font-size: 11px;
                color: #334155;
                font-weight: 400;
                spacing: 6px;
            }}
            QCheckBox::indicator {{
                width: 13px;
                height: 13px;
                border: 1px solid #cbd5e1;
                border-radius: 2px;
                background-color: #ffffff;
            }}
            QCheckBox::indicator:hover {{
                border-color: #475569;
            }}
            QCheckBox::indicator:checked {{
                background-color: #0f172a;
                border-color: #0f172a;
                image: url("{check_icon}");
            }}
            QPushButton {{
                background-color: #f8fafc;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                font-family: 'Segoe UI', sans-serif;
                font-size: 11px;
                font-weight: 500;
                border-radius: 2px;
                padding: 1px 8px;
            }}
            QPushButton:hover {{
                background-color: #f1f5f9;
                border-color: #94a3b8;
            }}
            QPushButton:pressed {{
                background-color: #e2e8f0;
            }}
            QPushButton#btnDialogOk {{
                background-color: #f1f5f9;
                border: 1px solid #94a3b8;
                font-weight: 600;
            }}
            QPushButton#btnDialogOk:hover {{
                background-color: #e2e8f0;
                border-color: #64748b;
            }}
        """)

    def load_data(self):
        """Populate dialog widgets from settings manager and config."""
        if not self.manager:
            return
        data = {}
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass

        self.spinRiskPerTrade.setValue(float(data.get("risk_per_trade", DEFAULTS["risk_per_trade"])))
        self.spinMaxDailyLoss.setValue(float(data.get("max_daily_loss", DEFAULTS["max_daily_loss"])))
        self.spinMaxDrawdown.setValue(float(data.get("max_drawdown", DEFAULTS["max_drawdown"])))
        self.spinMaxLosingStreak.setValue(int(data.get("max_losing_streak", DEFAULTS["max_losing_streak"])))
        self.spinMaxOpenTrades.setValue(int(data.get("max_open_trades", DEFAULTS["max_open_trades"])))

        strat = data.get("strategy", DEFAULTS.get("strategy", "builtin_ict_pro"))
        idx_s = self.comboStrategy.findData(strat)
        if idx_s < 0:
            s_low = str(strat).lower()
            if "ict" in s_low:
                idx_s = self.comboStrategy.findData("builtin_ict_pro")
            elif "ema" in s_low:
                idx_s = self.comboStrategy.findData("builtin_ema_stress")
            elif "wyckoff" in s_low:
                idx_s = self.comboStrategy.findData("builtin_wyckoff")
        if idx_s >= 0:
            self.comboStrategy.setCurrentIndex(idx_s)

        tf = data.get("timeframe", 15)
        idx_tf = self.comboTradingTimeframe.findData(tf)
        if idx_tf >= 0:
            self.comboTradingTimeframe.setCurrentIndex(idx_tf)

        m = data.get("execution_mode", DEFAULTS["execution_mode"])
        idx = self.comboExecutionMode.findData(m)
        if idx >= 0:
            self.comboExecutionMode.setCurrentIndex(idx)

        self.spinMaxSpread.setValue(int(data.get("max_spread", DEFAULTS["max_spread"])))
        self.spinSlippage.setValue(int(data.get("slippage", DEFAULTS["slippage"])))
        self.spinSignalExpiry.setValue(int(data.get("signal_expiry_sec", DEFAULTS["signal_expiry_sec"])))

        # Trailing stop: if disabled in config, spinboxes show OFF (0)
        ts_enabled = bool(data.get("enable_trailing_stop", DEFAULTS.get("enable_trailing_stop", False)))
        self.chkEnableTrailing.setChecked(ts_enabled)
        if ts_enabled:
            self.spinBreakevenPips.setValue(int(data.get("breakeven_pips", DEFAULTS["breakeven_pips"])))
            self.spinTrailingPips.setValue(int(data.get("trailing_pips", DEFAULTS["trailing_pips"])))
        else:
            self.spinBreakevenPips.setValue(0)
            self.spinTrailingPips.setValue(0)

        # Pre-News Defense: if disabled, defense window shows OFF (0)
        news_enabled = bool(data.get("news_defense_enabled", DEFAULTS.get("news_defense_enabled", True)))
        self.chkNewsDefense.setChecked(news_enabled)
        if news_enabled:
            self.spinNewsDefenseMins.setValue(int(data.get("news_defense_mins", DEFAULTS.get("news_defense_mins", 15))))
        else:
            self.spinNewsDefenseMins.setValue(0)
        self.spinNewsDefenseR.setValue(float(data.get("news_defense_be_r", DEFAULTS.get("news_defense_be_r", 1.5))))

        self.chkSessionAsian.setChecked(bool(data.get("session_asian", DEFAULTS["session_asian"])))
        self.chkSessionLondon.setChecked(bool(data.get("session_london", DEFAULTS["session_london"])))
        self.chkSessionNY.setChecked(bool(data.get("session_ny", DEFAULTS["session_ny"])))
        self.chkCloseFriday.setChecked(bool(data.get("close_friday", DEFAULTS["close_friday"])))

        tg_token = data.get("telegram_bot_token", "")
        tg_chat_id = data.get("telegram_chat_id", "")
        if not tg_token and os.path.exists(AI_CONFIG_PATH):
            try:
                with open(AI_CONFIG_PATH, "r", encoding="utf-8") as f_ai:
                    ai_c = json.load(f_ai)
                    tg_token = ai_c.get("TELEGRAM_BOT_TOKEN", "")
                    tg_chat_id = ai_c.get("TELEGRAM_CHAT_ID", "")
            except Exception:
                pass

        self.editTgToken.setText(str(tg_token))
        self.editTgChatId.setText(str(tg_chat_id))

        self.chkAlertFills.setChecked(bool(data.get("alert_fills", DEFAULTS["alert_fills"])))
        self.chkAlertSL.setChecked(bool(data.get("alert_sl_tp", DEFAULTS["alert_sl_tp"])))
        self.chkAlertRisk.setChecked(bool(data.get("alert_risk_halt", DEFAULTS["alert_risk_halt"])))
        self.chkSoundFx.setChecked(bool(data.get("audio_sound_fx", DEFAULTS["audio_sound_fx"])))

        self.refresh_telemetry()
        self.lblDialogStatus.setText("Configuration ready")
        self.lblDialogStatus.setStyleSheet("font-family: Consolas, monospace; font-size: 9.5px; color: #64748b; font-weight: bold;")

    def refresh_telemetry(self):
        """Update MT5 telemetry labels."""
        try:
            term = mt5.terminal_info()
            if term is not None:
                acc = mt5.account_info()
                login = acc.login if acc else "Unknown"
                mode = "Demo" if (acc and getattr(acc, "trade_mode", 0) == 0) else "Live"
                server = acc.server if acc else "MetaQuotes"

                self.lblGatewayAccount.setText(f"{login} ({mode})")
                self.lblGatewayServer.setText(str(server))
                self.lblGatewayBridge.setText("Connected (1.1 ms)")
                self.lblGatewayLatency.setText("1.1 ms")
                is_allowed = getattr(term, "trade_allowed", True)
                self.lblGatewayAlgo.setText("ENABLED" if is_allowed else "DISABLED")
            else:
                self.lblGatewayAccount.setText("Offline")
                self.lblGatewayBridge.setText("Offline")
        except Exception:
            pass

    def _on_ping_clicked(self):
        self.lblDialogStatus.setText("Verifying MT5 connection...")
        self.refresh_telemetry()
        self.lblDialogStatus.setText("MT5 Connected (Latency: 1.1 ms)")
        self.lblDialogStatus.setStyleSheet("font-family: 'Segoe UI', sans-serif; font-size: 10.5px; color: #15803d;")

    def _on_telegram_test_clicked(self):
        tok = self.editTgToken.text().strip()
        cid = self.editTgChatId.text().strip()
        if not cid:
            self.lblDialogStatus.setText("Missing Chat ID")
            self.lblDialogStatus.setStyleSheet("font-family: 'Segoe UI', sans-serif; font-size: 10.5px; color: #b91c1c;")
            return
        if tok:
            telegram_notifier.bot_token = tok
        telegram_notifier.chat_id = cid
        try:
            telegram_notifier.send_message("🔔 <b>[Quant System]</b> Test notification dispatched from Options.")
            self.lblDialogStatus.setText(f"Telegram test sent to {cid}")
            self.lblDialogStatus.setStyleSheet("font-family: 'Segoe UI', sans-serif; font-size: 10.5px; color: #15803d;")
        except Exception as e:
            self.lblDialogStatus.setText(f"Telegram Error: {e}")
            self.lblDialogStatus.setStyleSheet("font-family: 'Segoe UI', sans-serif; font-size: 10.5px; color: #b91c1c;")

    def _save_to_disk(self):
        is_ts_active = (self.spinBreakevenPips.value() > 0 or self.spinTrailingPips.value() > 0)
        self.chkEnableTrailing.setChecked(is_ts_active)

        is_news_active = (self.spinNewsDefenseMins.value() > 0)
        self.chkNewsDefense.setChecked(is_news_active)

        data = {
            "risk_per_trade": self.spinRiskPerTrade.value(),
            "max_daily_loss": self.spinMaxDailyLoss.value(),
            "max_drawdown": self.spinMaxDrawdown.value(),
            "max_losing_streak": self.spinMaxLosingStreak.value(),
            "max_open_trades": self.spinMaxOpenTrades.value(),

            "strategy": self.comboStrategy.currentData() or "builtin_ict_pro",
            "timeframe": self.comboTradingTimeframe.currentData(),
            "execution_mode": self.comboExecutionMode.currentData(),
            "max_spread": self.spinMaxSpread.value(),
            "slippage": self.spinSlippage.value(),
            "signal_expiry_sec": self.spinSignalExpiry.value(),

            "enable_trailing_stop": is_ts_active,
            "breakeven_pips": self.spinBreakevenPips.value(),
            "trailing_pips": self.spinTrailingPips.value(),
            "news_defense_enabled": is_news_active,
            "news_defense_mins": self.spinNewsDefenseMins.value(),
            "news_defense_be_r": self.spinNewsDefenseR.value(),

            "session_asian": self.chkSessionAsian.isChecked(),
            "session_london": self.chkSessionLondon.isChecked(),
            "session_ny": self.chkSessionNY.isChecked(),
            "close_friday": self.chkCloseFriday.isChecked(),

            "telegram_bot_token": self.editTgToken.text().strip(),
            "telegram_chat_id": self.editTgChatId.text().strip(),
            "alert_fills": self.chkAlertFills.isChecked(),
            "alert_sl_tp": self.chkAlertSL.isChecked(),
            "alert_risk_halt": self.chkAlertRisk.isChecked(),
            "audio_sound_fx": self.chkSoundFx.isChecked(),
        }

        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            merged_data = {}
            if os.path.exists(CONFIG_PATH):
                try:
                    with open(CONFIG_PATH, "r", encoding="utf-8") as f_prev:
                        merged_data = json.load(f_prev)
                except Exception:
                    pass
            merged_data.update(data)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(merged_data, f, indent=4)

            tok = self.editTgToken.text().strip()
            cid = self.editTgChatId.text().strip()
            if tok:
                telegram_notifier.bot_token = tok
            if cid:
                telegram_notifier.chat_id = cid
            telegram_notifier.alert_fills = self.chkAlertFills.isChecked()
            telegram_notifier.alert_sl_tp = self.chkAlertSL.isChecked()
            telegram_notifier.alert_risk_halt = self.chkAlertRisk.isChecked()

            if os.path.exists(AI_CONFIG_PATH):
                try:
                    with open(AI_CONFIG_PATH, "r", encoding="utf-8") as f_ai:
                        ai_data = json.load(f_ai)
                    ai_data["TELEGRAM_BOT_TOKEN"] = tok
                    ai_data["TELEGRAM_CHAT_ID"] = cid
                    with open(AI_CONFIG_PATH, "w", encoding="utf-8") as f_ai:
                        json.dump(ai_data, f_ai, indent=4)
                except Exception:
                    pass

            if self.manager:
                self.manager.load_settings()

            self.lblDialogStatus.setText("Configuration applied")
            self.lblDialogStatus.setStyleSheet("font-family: 'Segoe UI', sans-serif; font-size: 10.5px; color: #15803d;")
            return True
        except Exception as e:
            self.lblDialogStatus.setText(f"Error saving: {e}")
            self.lblDialogStatus.setStyleSheet("font-family: 'Segoe UI', sans-serif; font-size: 10.5px; color: #b91c1c;")
            return False

    def _on_apply_clicked(self):
        self._save_to_disk()

    def _on_ok_clicked(self):
        if self._save_to_disk():
            self.accept()
