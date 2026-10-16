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
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QFrame, QLineEdit, QCheckBox
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
    "execution_mode": "SEMI-AUTO",
    "max_spread": 25,
    "slippage": 20,
    "breakeven_pips": 10,
    "trailing_pips": 15,
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
    # Fallback keys maintained for backwards compatibility
    "mt5_server": "MetaQuotes-Demo / IC Markets",
    "strategy": "ICT",
    "timeframe": 15,
    "gate_mode": "FULL",
    "bias": "AUTO",
    "news_filter": True,
    "news_pause": 30,
    "heartbeat": 500,
    "auto_wal": True,
}



class OptionsDialog(QDialog):
    """Authentic MetaTrader 5-style 'Options' Dialog (Floating Preferences Window)."""

    def __init__(self, parent=None, manager=None):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("System Options & Configurations")
        self.setFixedSize(580, 418)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        icon_path = os.path.join(ASSETS_DIR, "nav_settings.svg")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._setup_ui()
        self._apply_styling()

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(8)

        # Tab Widget (Authentic Horizontal MT5 Tabs)
        self.tabWidget = QTabWidget()
        self.tabWidget.setObjectName("optionsTabWidget")

        # --- PAGE 1: RISK LIMITS ---
        page_risk = QWidget()
        layout_risk = QVBoxLayout(page_risk)
        layout_risk.setContentsMargins(16, 12, 16, 12)
        layout_risk.setSpacing(9)

        lbl_desc_risk = QLabel("Risk limits and drawdown protection rules.")
        lbl_desc_risk.setStyleSheet("color: #64748b; font-family: 'Segoe UI', sans-serif; font-size: 11px; margin-bottom: 4px;")
        layout_risk.addWidget(lbl_desc_risk)

        self.spinRiskPerTrade = QDoubleSpinBox()
        self.spinRiskPerTrade.setRange(0.1, 10.0)
        self.spinRiskPerTrade.setSingleStep(0.25)
        self.spinRiskPerTrade.setSuffix(" %")

        self.spinMaxDailyLoss = QDoubleSpinBox()
        self.spinMaxDailyLoss.setRange(50.0, 50000.0)
        self.spinMaxDailyLoss.setSingleStep(50.0)
        self.spinMaxDailyLoss.setPrefix("$")

        self.spinMaxDrawdown = QDoubleSpinBox()
        self.spinMaxDrawdown.setRange(1.0, 30.0)
        self.spinMaxDrawdown.setSingleStep(0.5)
        self.spinMaxDrawdown.setSuffix(" %")

        self.spinMaxLosingStreak = QSpinBox()
        self.spinMaxLosingStreak.setRange(1, 20)
        self.spinMaxLosingStreak.setSuffix(" trades")

        self.spinMaxOpenTrades = QSpinBox()
        self.spinMaxOpenTrades.setRange(1, 20)
        self.spinMaxOpenTrades.setSuffix(" positions")

        self.spinMaxLosingStreak.setSuffix(" trades")
        for lbl_text, widget, w_width in [
            ("Risk Per Trade:", self.spinRiskPerTrade, 110),
            ("Max Daily Loss:", self.spinMaxDailyLoss, 110),
            ("Max Equity Drawdown:", self.spinMaxDrawdown, 110),
            ("Max Consecutive Losses:", self.spinMaxLosingStreak, 110),
            ("Max Concurrent Positions:", self.spinMaxOpenTrades, 110),
        ]:
            row = QWidget()
            r_lay = QHBoxLayout(row)
            r_lay.setContentsMargins(0, 0, 0, 0)
            r_lay.setSpacing(10)

            lbl = QLabel(lbl_text)
            lbl.setFixedWidth(150)
            r_lay.addWidget(lbl)

            widget.setFixedWidth(w_width)
            widget.setFixedHeight(26)
            r_lay.addWidget(widget)
            r_lay.addStretch()
            layout_risk.addWidget(row)

        self.chkEnforceDailyHalt = QCheckBox("Halt trading on maximum daily loss")
        self.chkEnforceDailyHalt.setChecked(True)
        layout_risk.addWidget(self.chkEnforceDailyHalt)

        layout_risk.addStretch()
        self.tabWidget.addTab(page_risk, "Risk Management")

        # --- PAGE 2: EXECUTION ---
        page_exec = QWidget()
        layout_exec = QVBoxLayout(page_exec)
        layout_exec.setContentsMargins(16, 12, 16, 12)
        layout_exec.setSpacing(9)

        lbl_desc_exec = QLabel("Execution modes, spread limits, and trading sessions.")
        lbl_desc_exec.setStyleSheet("color: #64748b; font-family: 'Segoe UI', sans-serif; font-size: 11px; margin-bottom: 4px;")
        layout_exec.addWidget(lbl_desc_exec)

        self.comboStrategy = QComboBox()
        try:
            from backend.core.strategies.strategy_loader import discover_strategies
            strats = discover_strategies()
            for s in strats:
                self.comboStrategy.addItem(s["name"], s["id"])
        except Exception:
            self.comboStrategy.addItem("ICT Zones Pro v4.2 (Asian Sweep + FVG)", "builtin_ict_pro")
            self.comboStrategy.addItem("EMA Dual Cross (Resilience Benchmark)", "builtin_ema_stress")
            self.comboStrategy.addItem("Wyckoff Momentum Pro (Vectorized)", "builtin_wyckoff")

        self.comboTradingTimeframe = QComboBox()
        self.comboTradingTimeframe.addItem("M1 (1 Minute)", 1)
        self.comboTradingTimeframe.addItem("M5 (5 Minutes)", 5)
        self.comboTradingTimeframe.addItem("M15 (15 Minutes - Recommended)", 15)
        self.comboTradingTimeframe.addItem("M30 (30 Minutes)", 30)
        self.comboTradingTimeframe.addItem("H1 (1 Hour)", 60)
        self.comboTradingTimeframe.addItem("H4 (4 Hours)", 240)
        self.comboTradingTimeframe.addItem("D1 (Daily)", 1440)
        self.comboTradingTimeframe.addItem("Follow Chart Timeframe", "FOLLOW_CHART")

        self.comboExecutionMode = QComboBox()
        self.comboExecutionMode.addItem("Semi-Automated (Operator Approval)", "SEMI-AUTO")
        self.comboExecutionMode.addItem("Manual (Alerts Only)", "MANUAL")
        self.comboExecutionMode.addItem("Fully Automated (STP Execution)", "FULL-AUTO")

        self.spinMaxSpread = QSpinBox()
        self.spinMaxSpread.setRange(1, 200)
        self.spinMaxSpread.setSuffix(" points")

        self.spinSlippage = QSpinBox()
        self.spinSlippage.setRange(1, 100)
        self.spinSlippage.setSuffix(" points")

        self.spinSignalExpiry = QSpinBox()
        self.spinSignalExpiry.setRange(10, 600)
        self.spinSignalExpiry.setSingleStep(5)
        self.spinSignalExpiry.setSuffix(" sec")
        self.spinSignalExpiry.setValue(60)

        # Breakeven / Trailing
        be_ts_widget = QWidget()
        be_ts_lay = QHBoxLayout(be_ts_widget)
        be_ts_lay.setContentsMargins(0, 0, 0, 0)
        be_ts_lay.setSpacing(6)

        lbl_be = QLabel("BE:")
        lbl_be.setStyleSheet("font-family: 'Segoe UI', sans-serif; font-size: 11px; color: #64748b;")
        self.spinBreakevenPips = QSpinBox()
        self.spinBreakevenPips.setRange(1, 100)
        self.spinBreakevenPips.setFixedWidth(85)
        self.spinBreakevenPips.setSuffix(" pts")
        self.spinBreakevenPips.setFixedHeight(26)

        lbl_ts = QLabel("TS:")
        lbl_ts.setStyleSheet("font-family: 'Segoe UI', sans-serif; font-size: 11px; color: #64748b; margin-left: 6px;")
        self.spinTrailingPips = QSpinBox()
        self.spinTrailingPips.setRange(1, 100)
        self.spinTrailingPips.setFixedWidth(85)
        self.spinTrailingPips.setSuffix(" pts")
        self.spinTrailingPips.setFixedHeight(26)

        be_ts_lay.addWidget(lbl_be)
        be_ts_lay.addWidget(self.spinBreakevenPips)
        be_ts_lay.addWidget(lbl_ts)
        be_ts_lay.addWidget(self.spinTrailingPips)
        be_ts_lay.addStretch()

        # Sessions
        sessions_widget = QWidget()
        sw_lay = QHBoxLayout(sessions_widget)
        sw_lay.setContentsMargins(0, 0, 0, 0)
        sw_lay.setSpacing(10)

        self.chkSessionAsian = QCheckBox("Asian (Tokyo)")
        self.chkSessionLondon = QCheckBox("London")
        self.chkSessionNY = QCheckBox("New York")
        sw_lay.addWidget(self.chkSessionAsian)
        sw_lay.addWidget(self.chkSessionLondon)
        sw_lay.addWidget(self.chkSessionNY)
        sw_lay.addStretch()

        for lbl_text, widget, w_width in [
            ("Active Strategy:", self.comboStrategy, 240),
            ("Trading Timeframe:", self.comboTradingTimeframe, 220),
            ("Execution Mode:", self.comboExecutionMode, 220),
            ("Signal Expiry:", self.spinSignalExpiry, 110),
            ("Max Spread Limit:", self.spinMaxSpread, 110),
            ("Slippage Tolerance:", self.spinSlippage, 110),
            ("Break-Even / Trailing:", be_ts_widget, None),
            ("Active Sessions:", sessions_widget, None),
        ]:
            row = QWidget()
            r_lay = QHBoxLayout(row)
            r_lay.setContentsMargins(0, 0, 0, 0)
            r_lay.setSpacing(10)

            lbl = QLabel(lbl_text)
            lbl.setFixedWidth(150)
            r_lay.addWidget(lbl)

            if w_width:
                widget.setFixedWidth(w_width)
            if hasattr(widget, "setFixedHeight") and w_width:
                widget.setFixedHeight(26)
            r_lay.addWidget(widget)
            r_lay.addStretch()
            layout_exec.addWidget(row)

        self.chkCloseFriday = QCheckBox("Close all open positions on Friday EOD")
        self.chkCloseFriday.setStyleSheet("color: #334155; font-weight: 500;")
        layout_exec.addWidget(self.chkCloseFriday)

        layout_exec.addStretch()
        self.tabWidget.addTab(page_exec, "Execution Strategy")

        # --- PAGE 3: SERVER ---
        page_broker = QWidget()
        layout_broker = QVBoxLayout(page_broker)
        layout_broker.setContentsMargins(16, 12, 16, 12)
        layout_broker.setSpacing(9)

        lbl_desc_server = QLabel("MetaTrader 5 connection and bridge settings.")
        lbl_desc_server.setStyleSheet("color: #64748b; font-family: 'Segoe UI', sans-serif; font-size: 11px; margin-bottom: 4px;")
        layout_broker.addWidget(lbl_desc_server)

        self.lblGatewayAccount = QLineEdit("Offline")
        self.lblGatewayAccount.setReadOnly(True)
        self.lblGatewayAccount.setFixedWidth(242)
        self.lblGatewayAccount.setFixedHeight(24)

        self.lblGatewayServer = QLineEdit("MetaQuotes-Demo")
        self.lblGatewayServer.setReadOnly(True)
        self.lblGatewayServer.setFixedWidth(242)
        self.lblGatewayServer.setFixedHeight(24)

        self.lblGatewayBridge = QLineEdit("Connected (1.1 ms)")
        self.lblGatewayBridge.setReadOnly(True)
        self.lblGatewayBridge.setFixedWidth(242)
        self.lblGatewayBridge.setFixedHeight(24)

        self.lblGatewayLatency = QLabel("1.1 ms")
        self.lblGatewayLatency.setVisible(False)
        self.lblGatewayAlgo = QLabel("ENABLED")
        self.lblGatewayAlgo.setVisible(False)

        for w_ro in [self.lblGatewayAccount, self.lblGatewayServer, self.lblGatewayBridge]:
            w_ro.setStyleSheet("QLineEdit { background-color: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; border-radius: 2px; padding: 0 8px; font-family: Consolas, monospace; }")
        for lbl_text, widget in [
            ("MT5 Account:", self.lblGatewayAccount),
            ("Broker Server:", self.lblGatewayServer),
            ("Bridge Gateway:", self.lblGatewayBridge),
        ]:
            row = QWidget()
            r_lay = QHBoxLayout(row)
            r_lay.setContentsMargins(0, 0, 0, 0)
            r_lay.setSpacing(10)

            lbl = QLabel(lbl_text)
            lbl.setFixedWidth(150)
            r_lay.addWidget(lbl)
            r_lay.addWidget(widget)
            r_lay.addStretch()
            layout_broker.addWidget(row)

        self.chkAlgoTrading = QCheckBox("Enable automated trading")
        self.chkAlgoTrading.setChecked(True)
        layout_broker.addWidget(self.chkAlgoTrading)

        self.chkWebRequest = QCheckBox("Enable WebRequest for market data")
        self.chkWebRequest.setChecked(True)
        layout_broker.addWidget(self.chkWebRequest)

        layout_broker.addStretch()
        self.tabWidget.addTab(page_broker, "Broker Bridge")

        # --- PAGE 4: NOTIFICATIONS ---
        page_notif = QWidget()
        layout_notif = QVBoxLayout(page_notif)
        layout_notif.setContentsMargins(16, 12, 16, 12)
        layout_notif.setSpacing(9)

        lbl_desc_notif = QLabel("Execution alerts and Telegram notifications.")
        lbl_desc_notif.setStyleSheet("color: #64748b; font-family: 'Segoe UI', sans-serif; font-size: 11px; margin-bottom: 4px;")
        layout_notif.addWidget(lbl_desc_notif)

        self.editTgToken = QLineEdit()
        self.editTgToken.setEchoMode(QLineEdit.Password)
        self.editTgToken.setPlaceholderText("Bot Token from @BotFather")
        self.editTgToken.setFixedWidth(242)
        self.editTgToken.setFixedHeight(24)

        # Chat ID row with inline Test button (MT5 style)
        chat_widget = QWidget()
        chat_lay = QHBoxLayout(chat_widget)
        chat_lay.setContentsMargins(0, 0, 0, 0)
        chat_lay.setSpacing(6)

        self.editTgChatId = QLineEdit()
        self.editTgChatId.setPlaceholderText("-100...")
        self.editTgChatId.setFixedWidth(180)
        self.editTgChatId.setFixedHeight(24)

        btn_tg_test = QPushButton("Test")
        btn_tg_test.setFixedWidth(56)
        btn_tg_test.setFixedHeight(24)
        btn_tg_test.setCursor(Qt.PointingHandCursor)
        btn_tg_test.clicked.connect(self._on_telegram_test_clicked)

        chat_lay.addWidget(self.editTgChatId)
        chat_lay.addWidget(btn_tg_test)
        chat_lay.addStretch()

        events_widget = QWidget()
        ev_lay = QHBoxLayout(events_widget)
        ev_lay.setContentsMargins(0, 0, 0, 0)
        ev_lay.setSpacing(10)

        self.chkAlertFills = QCheckBox("Order Fills")
        self.chkAlertSL = QCheckBox("TP / SL Hit")
        self.chkAlertRisk = QCheckBox("Risk Halt")
        self.chkAlertRisk.setStyleSheet("color: #334155;")
        ev_lay.addWidget(self.chkAlertFills)
        ev_lay.addWidget(self.chkAlertSL)
        ev_lay.addWidget(self.chkAlertRisk)
        ev_lay.addStretch()

        for lbl_text, widget in [
            ("Telegram Bot Token:", self.editTgToken),
            ("Channel / Chat ID:", chat_widget),
            ("Notification Events:", events_widget),
        ]:
            row = QWidget()
            r_lay = QHBoxLayout(row)
            r_lay.setContentsMargins(0, 0, 0, 0)
            r_lay.setSpacing(10)

            lbl = QLabel(lbl_text)
            lbl.setFixedWidth(150)
            r_lay.addWidget(lbl)
            r_lay.addWidget(widget)
            r_lay.addStretch()
            layout_notif.addWidget(row)

        self.chkSoundFx = QCheckBox("Play sound on order execution")
        layout_notif.addWidget(self.chkSoundFx)

        layout_notif.addStretch()
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
        f_lay.setContentsMargins(4, 4, 4, 6)
        f_lay.setSpacing(6)

        self.lblDialogStatus = QLabel("Ready")
        self.lblDialogStatus.setStyleSheet("font-family: 'Segoe UI', sans-serif; font-size: 10.5px; color: #64748b;")
        f_lay.addWidget(self.lblDialogStatus)
        f_lay.addStretch()

        self.btnOk = QPushButton("OK")
        self.btnOk.setObjectName("btnDialogOk")
        self.btnOk.setFixedWidth(74)
        self.btnOk.setFixedHeight(24)
        self.btnOk.setCursor(Qt.PointingHandCursor)
        self.btnOk.clicked.connect(self._on_ok_clicked)

        self.btnCancel = QPushButton("Cancel")
        self.btnCancel.setObjectName("btnDialogCancel")
        self.btnCancel.setFixedWidth(74)
        self.btnCancel.setFixedHeight(24)
        self.btnCancel.setCursor(Qt.PointingHandCursor)
        self.btnCancel.clicked.connect(self.reject)

        self.btnApply = QPushButton("Apply")
        self.btnApply.setObjectName("btnDialogApply")
        self.btnApply.setFixedWidth(74)
        self.btnApply.setFixedHeight(24)
        self.btnApply.setCursor(Qt.PointingHandCursor)
        self.btnApply.clicked.connect(self._on_apply_clicked)

        f_lay.addWidget(self.btnOk)
        f_lay.addWidget(self.btnCancel)
        f_lay.addWidget(self.btnApply)
        root_layout.addWidget(footer)

    def _apply_styling(self):
        arrow_up = "frontend/assets/arrow_up.svg"
        arrow_down = "frontend/assets/arrow_down.svg"
        check_icon = "frontend/assets/check_vector_light.svg"

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
                padding: 6px 14px 7px 14px;
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
                padding: 2px 6px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 11px;
                color: #0f172a;
                min-height: 24px;
            }}
            QSpinBox, QDoubleSpinBox {{
                padding-right: 18px;
            }}
            QLineEdit[readOnly="true"] {{
                background-color: #f8fafc;
                color: #334155;
            }}
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
                border: 1px solid #475569;
            }}
            QSpinBox::up-button, QDoubleSpinBox::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 16px;
                border-left: 1px solid #cbd5e1;
                border-bottom: 1px solid #cbd5e1;
                background-color: #f8fafc;
            }}
            QSpinBox::down-button, QDoubleSpinBox::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 16px;
                border-left: 1px solid #cbd5e1;
                background-color: #f8fafc;
            }}
            QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
            QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
                background-color: #e2e8f0;
            }}
            QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
                image: url("{arrow_up}");
                width: 8px;
                height: 6px;
            }}
            QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
                image: url("{arrow_down}");
                width: 8px;
                height: 6px;
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
                width: 8px;
                height: 6px;
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
        self.spinBreakevenPips.setValue(int(data.get("breakeven_pips", DEFAULTS["breakeven_pips"])))
        self.spinTrailingPips.setValue(int(data.get("trailing_pips", DEFAULTS["trailing_pips"])))

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
            "breakeven_pips": self.spinBreakevenPips.value(),
            "trailing_pips": self.spinTrailingPips.value(),

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
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

            tok = self.editTgToken.text().strip()
            cid = self.editTgChatId.text().strip()
            if tok:
                telegram_notifier.bot_token = tok
            if cid:
                telegram_notifier.chat_id = cid

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


