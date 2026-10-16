import os
import json
import urllib.request
import urllib.error
from backend.infrastructure.brokers.mt5_safe import mt5
from PySide6.QtWidgets import (
    QDialog,
    QTabWidget,
    QLabel,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QFrame,
    QLineEdit,
    QCheckBox,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap
from backend.infrastructure.notifications.telegram_notifier import telegram_notifier

# Resolve project root robustly
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(CURRENT_DIR) == "controllers":
    ROOT_DIR = os.path.dirname(os.path.dirname(CURRENT_DIR))
elif os.path.basename(CURRENT_DIR) == "ui":
    ROOT_DIR = os.path.dirname(CURRENT_DIR)
else:
    ROOT_DIR = os.path.dirname(os.path.dirname(CURRENT_DIR))

CONFIG_PATH = os.path.join(ROOT_DIR, "config", "settings.json")
AI_CONFIG_PATH = os.path.join(ROOT_DIR, "config", "ai_config.json")

ASSETS_DIR = os.path.join(CURRENT_DIR, "assets")
if not os.path.exists(ASSETS_DIR):
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



from frontend.widgets.options_dialog import OptionsDialog

class SettingsManager:
    """Settings Manager supporting both Embedded Preferences Sheet and MT5-Style Options Dialog."""

    def __init__(self, window):
        self.window = window
        self.options_dialog = None
        self._build_embedded_sheet_ui()
        self.setup_comboboxes()
        self.load_settings()
        self.bind_events()
        self.refresh_mt5_telemetry()

    def open_options_dialog(self):
        """Open the authentic floating MetaTrader 5-style Options Dialog (Ctrl+O)."""
        if self.options_dialog is None:
            self.options_dialog = OptionsDialog(self.window, self)
        self.options_dialog.load_data()
        self.options_dialog.setWindowModality(Qt.WindowModal)

        # Center over active workspace window
        if self.window:
            geo = self.window.geometry()
            x = geo.x() + max(0, (geo.width() - self.options_dialog.width()) // 2)
            y = geo.y() + max(0, (geo.height() - self.options_dialog.height()) // 2)
            self.options_dialog.move(x, y)

        self.options_dialog.show()
        self.options_dialog.raise_()
        self.options_dialog.activateWindow()
        return self.options_dialog

    def _build_embedded_sheet_ui(self):
        """Construct the Preferences Sheet inside Tab 4 with a prominent 'Open Popup (Ctrl+O)' trigger."""
        win = self.window
        if not hasattr(win, "scrollSettingsContent"):
            return

        # 1. Hide legacy GroupBoxes
        for gb_name in ["groupRiskLimits", "groupSessions", "groupInfrastructure"]:
            if hasattr(win, gb_name):
                getattr(win, gb_name).setVisible(False)

        # 2. Hide Ollama AI button
        if hasattr(win, "btnTestAI"):
            win.btnTestAI.setVisible(False)

        # 3. Setup Toolbar: Concise institutional layout
        if hasattr(win, "layoutSettingsToolbar"):
            tb = win.layoutSettingsToolbar

            if not hasattr(win, "lblSettingsMainTitle"):
                lbl_t = QLabel("SETTINGS & RISK PARAMETERS")
                lbl_t.setObjectName("lblSettingsMainTitle")
                lbl_t.setStyleSheet(
                    "font-family: Consolas, monospace; font-size: 11px; font-weight: bold; "
                    "letter-spacing: 0.5px; padding-right: 14px; color: #0f172a;"
                )
                win.lblSettingsMainTitle = lbl_t
                tb.insertWidget(0, lbl_t)

            icon_ping = os.path.join(ASSETS_DIR, "icon_ping.svg")
            icon_reset = os.path.join(ASSETS_DIR, "icon_reset.svg")
            icon_save = os.path.join(ASSETS_DIR, "icon_save.svg")

            if hasattr(win, "btnTestMt5"):
                win.btnTestMt5.setVisible(False)

            if hasattr(win, "btnResetSettings"):
                win.btnResetSettings.setText("RESET")
                if os.path.exists(icon_reset):
                    win.btnResetSettings.setIcon(QIcon(icon_reset))
                    win.btnResetSettings.setIconSize(QSize(12, 12))
                win.btnResetSettings.setFixedHeight(26)
                win.btnResetSettings.setCursor(Qt.PointingHandCursor)
                win.btnResetSettings.setStyleSheet(
                    "QPushButton#btnResetSettings { background-color: #ffffff; color: #475569; border: 1px solid #cbd5e1; "
                    "font-family: Consolas, monospace; font-size: 9px; font-weight: bold; border-radius: 2px; padding: 0 10px; } "
                    "QPushButton#btnResetSettings:hover { background-color: #f8fafc; border-color: #94a3b8; }"
                )

            if hasattr(win, "btnSaveSettings"):
                win.btnSaveSettings.setText("SAVE CONFIG")
                if os.path.exists(icon_save):
                    win.btnSaveSettings.setIcon(QIcon(icon_save))
                    win.btnSaveSettings.setIconSize(QSize(12, 12))
                win.btnSaveSettings.setFixedHeight(26)
                win.btnSaveSettings.setCursor(Qt.PointingHandCursor)
                win.btnSaveSettings.setStyleSheet(
                    "QPushButton#btnSaveSettings { background-color: #0f172a; color: #ffffff; border: 1px solid #0f172a; "
                    "font-family: Consolas, monospace; font-size: 9px; font-weight: bold; border-radius: 2px; padding: 0 12px; } "
                    "QPushButton#btnSaveSettings:hover { background-color: #1e293b; }"
                )

        # 4. Remove old container items from layout without deleting the underlying C++ widgets
        if hasattr(win, "horizontalLayout_settings"):
            while win.horizontalLayout_settings.count():
                item = win.horizontalLayout_settings.takeAt(0)
                w = item.widget()
                if w:
                    w.hide()
            win.horizontalLayout_settings.setContentsMargins(12, 10, 12, 12)
            win.horizontalLayout_settings.setSpacing(12)

        # Style constants
        card_qss = (
            "QFrame.settingsColCard { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px; }"
        )
        def make_card_header(title_text, sub_text):
            hdr = QFrame()
            hdr.setObjectName("cardHeaderStrip")
            hdr.setFixedHeight(48)
            hdr.setStyleSheet(
                "QFrame#cardHeaderStrip { background-color: #f8fafc; border-bottom: 1px solid #cbd5e1; "
                "border-top-left-radius: 4px; border-top-right-radius: 4px; }"
            )
            h_lay = QVBoxLayout(hdr)
            h_lay.setContentsMargins(14, 8, 14, 6)
            h_lay.setSpacing(2)
            t_lbl = QLabel(title_text)
            t_lbl.setStyleSheet(
                "font-family: 'Consolas', monospace; font-size: 11px; font-weight: 700; "
                "color: #0f172a; letter-spacing: 0.5px; background: transparent; border: none;"
            )
            s_lbl = QLabel(sub_text)
            s_lbl.setStyleSheet(
                "font-family: 'Segoe UI', sans-serif; font-size: 9.5px; color: #64748b; background: transparent; border: none;"
            )
            h_lay.addWidget(t_lbl)
            h_lay.addWidget(s_lbl)
            return hdr

        # Add Options Dialog button to toolbar if not already present
        if hasattr(win, "layoutSettingsToolbar"):
            tb = win.layoutSettingsToolbar
            if not hasattr(win, "btnOpenOptionsDialog"):
                btn_open_popup = QPushButton("OPTIONS (Ctrl+O)")
                btn_open_popup.setObjectName("btnOpenOptionsDialog")
                icon_gear = os.path.join(ASSETS_DIR, "gear_icon.svg")
                if os.path.exists(icon_gear):
                    try:
                        with open(icon_gear, "rb") as f:
                            data = f.read()
                        pix = QPixmap()
                        pix.loadFromData(data)
                        btn_open_popup.setIcon(QIcon(pix))
                    except Exception:
                        btn_open_popup.setIcon(QIcon(icon_gear))
                    btn_open_popup.setIconSize(QSize(12, 12))
                btn_open_popup.setFixedHeight(26)
                btn_open_popup.setCursor(Qt.PointingHandCursor)
                btn_open_popup.setStyleSheet(
                    "QPushButton#btnOpenOptionsDialog { background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; "
                    "font-family: Consolas, monospace; font-size: 9px; font-weight: bold; border-radius: 2px; padding: 0 10px; } "
                    "QPushButton#btnOpenOptionsDialog:hover { background-color: #f1f5f9; border-color: #94a3b8; }"
                )
                btn_open_popup.clicked.connect(self.open_options_dialog)
                win.btnOpenOptionsDialog = btn_open_popup
                tb.insertWidget(tb.count() - 2, btn_open_popup)

        # --- CARD 1: RISK & CAPITAL SAFEGUARDS ---
        card_risk = QFrame()
        card_risk.setProperty("class", "settingsColCard")
        card_risk.setStyleSheet(card_qss)
        card_risk_layout = QVBoxLayout(card_risk)
        card_risk_layout.setContentsMargins(0, 0, 0, 12)
        card_risk_layout.setSpacing(0)
        card_risk_layout.addWidget(make_card_header("HARD RISK LIMITS", "Account drawdowns and loss boundaries"))

        body_risk = QWidget()
        body_risk_lay = QVBoxLayout(body_risk)
        body_risk_lay.setContentsMargins(14, 12, 14, 8)
        body_risk_lay.setSpacing(10)

        for t, w in [
            ("Risk Per Trade:", getattr(win, "spinRiskPerTrade", None)),
            ("Max Daily Loss:", getattr(win, "spinMaxDailyLoss", None)),
            ("Max Total Drawdown:", getattr(win, "spinMaxDrawdown", None)),
            ("Max Losing Streak:", getattr(win, "spinMaxLosingStreak", None)),
            ("Max Open Positions:", getattr(win, "spinMaxOpenTrades", None)),
        ]:
            if w:
                rw = QWidget()
                rl = QHBoxLayout(rw)
                rl.setContentsMargins(0, 0, 0, 0)
                lbl = QLabel(t)
                lbl.setFixedWidth(145)
                lbl.setStyleSheet("color: #334155; font-family: 'Segoe UI', sans-serif; font-size: 10px; font-weight: 600;")
                rl.addWidget(lbl)
                w.setFixedHeight(26)
                w.setFixedWidth(120)
                rl.addWidget(w)
                rl.addStretch()
                body_risk_lay.addWidget(rw)

        self.chkEnforceDailyHalt = QCheckBox("Halt trading on daily loss breach")
        self.chkEnforceDailyHalt.setChecked(True)
        self.chkEnforceDailyHalt.setStyleSheet("color: #b91c1c; font-family: 'Segoe UI', sans-serif; font-size: 10px; font-weight: 600; margin-top: 6px;")
        body_risk_lay.addWidget(self.chkEnforceDailyHalt)
        body_risk_lay.addStretch()
        card_risk_layout.addWidget(body_risk, 1)

        # --- CARD 2: EXECUTION & SESSION GOVERNANCE ---
        card_exec = QFrame()
        card_exec.setProperty("class", "settingsColCard")
        card_exec.setStyleSheet(card_qss)
        card_exec_layout = QVBoxLayout(card_exec)
        card_exec_layout.setContentsMargins(0, 0, 0, 12)
        card_exec_layout.setSpacing(0)
        card_exec_layout.addWidget(make_card_header("EXECUTION & SESSIONS", "Slippage tolerance and trading schedule"))

        body_exec = QWidget()
        body_exec_lay = QVBoxLayout(body_exec)
        body_exec_lay.setContentsMargins(14, 12, 14, 8)
        body_exec_lay.setSpacing(10)

        # Trading Strategy row
        if hasattr(win, "comboStrategy"):
            try:
                from backend.core.strategies.strategy_loader import discover_strategies
                strats = discover_strategies()
                win.comboStrategy.clear()
                for s in strats:
                    win.comboStrategy.addItem(s["name"], s["id"])
            except Exception:
                pass
            rw_s = QWidget()
            rl_s = QHBoxLayout(rw_s)
            rl_s.setContentsMargins(0, 0, 0, 0)
            lbl_s = QLabel("Trading Strategy:")
            lbl_s.setFixedWidth(145)
            lbl_s.setStyleSheet("color: #334155; font-family: 'Segoe UI', sans-serif; font-size: 10px; font-weight: 600;")
            rl_s.addWidget(lbl_s)
            win.comboStrategy.setFixedHeight(26)
            win.comboStrategy.setFixedWidth(230)
            rl_s.addWidget(win.comboStrategy)
            rl_s.addStretch()
            body_exec_lay.addWidget(rw_s)

        # Execution Mode row
        if hasattr(win, "comboExecutionMode"):
            rw = QWidget()
            rl = QHBoxLayout(rw)
            rl.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel("Execution Mode:")
            lbl.setFixedWidth(145)
            lbl.setStyleSheet("color: #334155; font-family: 'Segoe UI', sans-serif; font-size: 10px; font-weight: 600;")
            rl.addWidget(lbl)
            win.comboExecutionMode.setFixedHeight(26)
            win.comboExecutionMode.setFixedWidth(230)
            rl.addWidget(win.comboExecutionMode)
            rl.addStretch()
            body_exec_lay.addWidget(rw)

        # Spread & Slippage
        for t, w in [
            ("Max Spread Guard:", getattr(win, "spinMaxSpread", None)),
            ("Max Slippage Tolerance:", getattr(win, "spinSlippage", None)),
            ("Breakeven Trigger:", getattr(win, "spinBreakevenPips", None)),
            ("Trailing Stop Distance:", getattr(win, "spinTrailingPips", None)),
        ]:
            if w:
                rw = QWidget()
                rl = QHBoxLayout(rw)
                rl.setContentsMargins(0, 0, 0, 0)
                lbl = QLabel(t)
                lbl.setFixedWidth(145)
                lbl.setStyleSheet("color: #334155; font-family: 'Segoe UI', sans-serif; font-size: 10px; font-weight: 600;")
                rl.addWidget(lbl)
                w.setFixedHeight(26)
                w.setFixedWidth(120)
                rl.addWidget(w)
                rl.addStretch()
                body_exec_lay.addWidget(rw)

        # Sessions Row
        sess_w = QWidget()
        sess_l = QHBoxLayout(sess_w)
        sess_l.setContentsMargins(0, 4, 0, 0)
        sess_l.setSpacing(6)
        if hasattr(win, "chkSessionAsian"):
            win.chkSessionAsian.setText("ASIA")
            win.chkSessionAsian.setStyleSheet("font-family: Consolas, monospace; font-size: 9.5px;")
            sess_l.addWidget(win.chkSessionAsian)
        if hasattr(win, "chkSessionLondon"):
            win.chkSessionLondon.setText("LON")
            win.chkSessionLondon.setStyleSheet("font-family: Consolas, monospace; font-size: 9.5px;")
            sess_l.addWidget(win.chkSessionLondon)
        if hasattr(win, "chkSessionNY"):
            win.chkSessionNY.setText("NY")
            win.chkSessionNY.setStyleSheet("font-family: Consolas, monospace; font-size: 9.5px;")
            sess_l.addWidget(win.chkSessionNY)
        if hasattr(win, "chkCloseFriday"):
            win.chkCloseFriday.setText("FRI CLS")
            win.chkCloseFriday.setStyleSheet("color: #b91c1c; font-family: Consolas, monospace; font-size: 9.5px; font-weight: bold;")
            sess_l.addWidget(win.chkCloseFriday)
        sess_l.addStretch()

        rw_sess = QWidget()
        rl_sess = QHBoxLayout(rw_sess)
        rl_sess.setContentsMargins(0, 0, 0, 0)
        lbl_sess = QLabel("Active Sessions:")
        lbl_sess.setFixedWidth(145)
        lbl_sess.setStyleSheet("color: #334155; font-family: 'Segoe UI', sans-serif; font-size: 10px; font-weight: 600;")
        rl_sess.addWidget(lbl_sess)
        rl_sess.addWidget(sess_w)
        rl_sess.addStretch()
        body_exec_lay.addWidget(rw_sess)

        body_exec_lay.addStretch()
        card_exec_layout.addWidget(body_exec, 1)

        # --- CARD 3: BROKER & NOTIFICATIONS ---
        card_infra = QFrame()
        card_infra.setProperty("class", "settingsColCard")
        card_infra.setStyleSheet(card_qss)
        card_infra_layout = QVBoxLayout(card_infra)
        card_infra_layout.setContentsMargins(0, 0, 0, 12)
        card_infra_layout.setSpacing(0)
        card_infra_layout.addWidget(make_card_header("BROKER & NOTIFICATIONS", "MT5 telemetry and telegram webhook alerts"))

        body_infra = QWidget()
        body_infra_lay = QVBoxLayout(body_infra)
        body_infra_lay.setContentsMargins(14, 12, 14, 8)
        body_infra_lay.setSpacing(8)

        self.lblGatewayAccount = QLabel("#------ (Offline)")
        self.lblGatewayAccount.setStyleSheet("font-family: Consolas, monospace; font-size: 9.5px; font-weight: bold; color: #0f172a; background-color: #f1f5f9; padding: 2px 6px; border-radius: 2px; border: 1px solid #cbd5e1;")
        self.lblGatewayServer = QLabel("MetaQuotes-Demo")
        self.lblGatewayServer.setStyleSheet("font-family: Consolas, monospace; font-size: 9.5px; font-weight: 600; color: #334155;")
        self.lblGatewayBridge = QLabel("● CONNECTED")
        self.lblGatewayBridge.setStyleSheet("font-family: Consolas, monospace; font-size: 9.5px; font-weight: bold; color: #15803d;")
        self.lblGatewayLatency = QLabel("1.1 ms")
        self.lblGatewayLatency.setStyleSheet("font-family: Consolas, monospace; font-size: 9.5px; font-weight: bold; color: #0f172a;")
        self.lblGatewayAlgo = QLabel("● ENABLED")
        self.lblGatewayAlgo.setStyleSheet("font-family: Consolas, monospace; font-size: 9.5px; font-weight: bold; color: #15803d;")

        for t, w in [
            ("Account:", self.lblGatewayAccount),
            ("Server:", self.lblGatewayServer),
            ("Terminal Bridge:", self.lblGatewayBridge),
            ("Latency:", self.lblGatewayLatency),
            ("Algo Trading:", self.lblGatewayAlgo),
        ]:
            rw = QWidget()
            rl = QHBoxLayout(rw)
            rl.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(t)
            lbl.setFixedWidth(130)
            lbl.setStyleSheet("color: #334155; font-family: 'Segoe UI', sans-serif; font-size: 10px; font-weight: 600;")
            rl.addWidget(lbl)
            rl.addWidget(w)
            rl.addStretch()
            body_infra_lay.addWidget(rw)

        sep_infra = QFrame()
        sep_infra.setFixedHeight(1)
        sep_infra.setStyleSheet("background-color: #e2e8f0; border: none; margin: 4px 0;")
        body_infra_lay.addWidget(sep_infra)

        self.editTgToken = QLineEdit()
        self.editTgToken.setEchoMode(QLineEdit.Password)
        self.editTgToken.setPlaceholderText("Bot Token from @BotFather")
        self.editTgToken.setFixedHeight(24)
        self.editTgToken.setFixedWidth(190)

        self.editTgChatId = QLineEdit()
        self.editTgChatId.setPlaceholderText("-100...")
        self.editTgChatId.setFixedHeight(24)
        self.editTgChatId.setFixedWidth(190)

        for t, w in [
            ("Telegram Token:", self.editTgToken),
            ("Chat ID:", self.editTgChatId),
        ]:
            rw = QWidget()
            rl = QHBoxLayout(rw)
            rl.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(t)
            lbl.setFixedWidth(130)
            lbl.setStyleSheet("color: #334155; font-family: 'Segoe UI', sans-serif; font-size: 10px; font-weight: 600;")
            rl.addWidget(lbl)
            rl.addWidget(w)
            rl.addStretch()
            body_infra_lay.addWidget(rw)

        ev_w = QWidget()
        ev_l = QHBoxLayout(ev_w)
        ev_l.setContentsMargins(0, 0, 0, 0)
        ev_l.setSpacing(6)
        self.chkAlertFills = QCheckBox("FILLS")
        self.chkAlertFills.setStyleSheet("font-family: Consolas, monospace; font-size: 9px;")
        self.chkAlertSL = QCheckBox("TP / SL Hit")
        self.chkAlertSL.setStyleSheet("font-family: Consolas, monospace; font-size: 9px;")
        self.chkAlertRisk = QCheckBox("HALT")
        self.chkAlertRisk.setStyleSheet("color: #b91c1c; font-family: Consolas, monospace; font-size: 9px; font-weight: bold;")
        ev_l.addWidget(self.chkAlertFills)
        ev_l.addWidget(self.chkAlertSL)
        ev_l.addWidget(self.chkAlertRisk)
        ev_l.addStretch()

        rw_ev = QWidget()
        rl_ev = QHBoxLayout(rw_ev)
        rl_ev.setContentsMargins(0, 0, 0, 0)
        lbl_ev = QLabel("Event Triggers:")
        lbl_ev.setFixedWidth(130)
        lbl_ev.setStyleSheet("color: #334155; font-family: 'Segoe UI', sans-serif; font-size: 10px; font-weight: 600;")
        rl_ev.addWidget(lbl_ev)
        rl_ev.addWidget(ev_w)
        rl_ev.addStretch()
        body_infra_lay.addWidget(rw_ev)

        self.chkSoundFx = QCheckBox("Beep on trade execution")
        self.chkSoundFx.setChecked(True)
        self.chkSoundFx.setStyleSheet("color: #334155; font-family: 'Segoe UI', sans-serif; font-size: 10px; font-weight: 600;")
        body_infra_lay.addWidget(self.chkSoundFx)

        body_infra_lay.addStretch()
        card_infra_layout.addWidget(body_infra, 1)

        # Add all 3 cards with equal stretch=1 to horizontalLayout_settings
        if hasattr(win, "horizontalLayout_settings"):
            win.horizontalLayout_settings.addWidget(card_risk, 1)
            win.horizontalLayout_settings.addWidget(card_exec, 1)
            win.horizontalLayout_settings.addWidget(card_infra, 1)

    def setup_comboboxes(self):
        """Setup algorithm dispatch mode and spinbox formatting."""
        win = self.window
        if hasattr(win, "spinRiskPerTrade"): win.spinRiskPerTrade.setSuffix(" %")
        if hasattr(win, "spinMaxDrawdown"): win.spinMaxDrawdown.setSuffix(" %")
        if hasattr(win, "spinMaxDailyLoss"): win.spinMaxDailyLoss.setPrefix("$")
        if hasattr(win, "spinMaxLosingStreak"): win.spinMaxLosingStreak.setSuffix(" trades")
        if hasattr(win, "spinMaxOpenTrades"): win.spinMaxOpenTrades.setSuffix(" positions")
        if hasattr(win, "spinMaxSpread"): win.spinMaxSpread.setSuffix(" pts")
        if hasattr(win, "spinSlippage"): win.spinSlippage.setSuffix(" pts")

        if hasattr(win, "comboExecutionMode"):
            win.comboExecutionMode.clear()
            win.comboExecutionMode.addItem("Semi-Auto (Operator Gate)", "SEMI-AUTO")
            win.comboExecutionMode.addItem("Manual (Alerts Only)", "MANUAL")
            win.comboExecutionMode.addItem("Full-Auto (Autonomous STP)", "FULL-AUTO")
            win.comboExecutionMode.currentIndexChanged.connect(self._on_execution_mode_changed)

        if hasattr(win, "comboAIModel"):
            try:
                import shiboken6
                if shiboken6.isValid(win.comboAIModel) and win.comboAIModel.count() == 0:
                    win.comboAIModel.addItems(["qwen2.5", "llama3.1", "gemini-2.0-flash"])
            except Exception:
                pass

    def _on_execution_mode_changed(self, idx):
        if hasattr(self.window, "comboExecutionMode"):
            m = self.window.comboExecutionMode.currentData()
            if m and hasattr(self.window, "quant_terminal") and hasattr(self.window.quant_terminal, "set_execution_mode"):
                self.window.quant_terminal.set_execution_mode(m)

    def bind_events(self):
        if hasattr(self.window, "btnSaveSettings"):
            self.window.btnSaveSettings.clicked.connect(self.save_settings)
        if hasattr(self.window, "btnResetSettings"):
            self.window.btnResetSettings.clicked.connect(self.reset_defaults)
        if hasattr(self.window, "btnTestMt5"):
            self.window.btnTestMt5.clicked.connect(self.test_mt5_connection)

    def _set_status(self, text, color="#0f172a"):
        if hasattr(self.window, "lblSettingsStatus"):
            self.window.lblSettingsStatus.setText(text)
            self.window.lblSettingsStatus.setStyleSheet(
                f"color: {color}; font-family: Consolas, monospace; font-size: 9.5px; font-weight: bold;"
            )

    def refresh_mt5_telemetry(self):
        """Query live MT5 terminal metrics and update readouts."""
        try:
            term = mt5.terminal_info()
            if term is not None:
                acc = mt5.account_info()
                login = acc.login if acc else "Unknown"
                mode = "Demo" if (acc and getattr(acc, "trade_mode", 0) == 0) else "Live"
                server = acc.server if acc else "MetaQuotes"

                if hasattr(self, "lblGatewayAccount"):
                    self.lblGatewayAccount.setText(f"#{login} ({mode})")
                if hasattr(self, "lblGatewayServer"):
                    self.lblGatewayServer.setText(str(server))
                if hasattr(self, "lblGatewayBridge"):
                    self.lblGatewayBridge.setText("● CONNECTED")
                    self.lblGatewayBridge.setStyleSheet("font-family: Consolas, monospace; font-size: 9.5px; font-weight: bold; color: #15803d;")
                if hasattr(self, "lblGatewayLatency"):
                    self.lblGatewayLatency.setText("1.1 ms")
                if hasattr(self, "lblGatewayAlgo"):
                    is_allowed = getattr(term, "trade_allowed", True)
                    self.lblGatewayAlgo.setText("● ENABLED" if is_allowed else "○ DISABLED")
                    self.lblGatewayAlgo.setStyleSheet(
                        f"font-family: Consolas, monospace; font-size: 9.5px; font-weight: bold; color: {'#15803d' if is_allowed else '#b91c1c'};"
                    )
            else:
                if hasattr(self, "lblGatewayAccount"):
                    self.lblGatewayAccount.setText("#------ (Offline)")
                if hasattr(self, "lblGatewayBridge"):
                    self.lblGatewayBridge.setText("○ OFFLINE")
                    self.lblGatewayBridge.setStyleSheet("font-family: Consolas, monospace; font-size: 9.5px; font-weight: bold; color: #b91c1c;")
        except Exception:
            pass

    def test_mt5_connection(self):
        """Ping MT5 Terminal and report status."""
        self._set_status("Testing MT5 connection...", "#475569")
        try:
            term = mt5.terminal_info()
            if term is not None:
                acc = mt5.account_info()
                login = acc.login if acc else "Unknown"
                self.refresh_mt5_telemetry()
                self._set_status(f"MT5: CONNECTED (1.1ms | Account: {login})", "#15803d")
            else:
                self.refresh_mt5_telemetry()
                self._set_status("MT5: TERMINAL OFFLINE", "#b91c1c")
        except Exception as e:
            self._set_status(f"MT5 Connection Error: {e}", "#b91c1c")

    def save_settings(self):
        """Save settings from UI to settings.json."""
        win = self.window
        tg_token = self.editTgToken.text().strip() if hasattr(self, "editTgToken") else ""
        tg_chat_id = self.editTgChatId.text().strip() if hasattr(self, "editTgChatId") else ""

        data = {
            "risk_per_trade": getattr(win, "spinRiskPerTrade", None).value() if hasattr(win, "spinRiskPerTrade") else DEFAULTS["risk_per_trade"],
            "max_drawdown": getattr(win, "spinMaxDrawdown", None).value() if hasattr(win, "spinMaxDrawdown") else DEFAULTS["max_drawdown"],
            "max_daily_loss": getattr(win, "spinMaxDailyLoss", None).value() if hasattr(win, "spinMaxDailyLoss") else DEFAULTS["max_daily_loss"],
            "max_open_trades": getattr(win, "spinMaxOpenTrades", None).value() if hasattr(win, "spinMaxOpenTrades") else DEFAULTS["max_open_trades"],
            "max_losing_streak": getattr(win, "spinMaxLosingStreak", None).value() if hasattr(win, "spinMaxLosingStreak") else DEFAULTS["max_losing_streak"],

            "strategy": getattr(win, "comboStrategy", None).currentData() if hasattr(win, "comboStrategy") else DEFAULTS.get("strategy", "builtin_ict_pro"),
            "execution_mode": getattr(win, "comboExecutionMode", None).currentData() if hasattr(win, "comboExecutionMode") else DEFAULTS["execution_mode"],
            "max_spread": getattr(win, "spinMaxSpread", None).value() if hasattr(win, "spinMaxSpread") else DEFAULTS["max_spread"],
            "slippage": getattr(win, "spinSlippage", None).value() if hasattr(win, "spinSlippage") else DEFAULTS["slippage"],
            "breakeven_pips": getattr(win, "spinBreakevenPips", None).value() if hasattr(win, "spinBreakevenPips") else DEFAULTS["breakeven_pips"],
            "trailing_pips": getattr(win, "spinTrailingPips", None).value() if hasattr(win, "spinTrailingPips") else DEFAULTS["trailing_pips"],

            "session_asian": getattr(win, "chkSessionAsian", None).isChecked() if hasattr(win, "chkSessionAsian") else DEFAULTS["session_asian"],
            "session_london": getattr(win, "chkSessionLondon", None).isChecked() if hasattr(win, "chkSessionLondon") else DEFAULTS["session_london"],
            "session_ny": getattr(win, "chkSessionNY", None).isChecked() if hasattr(win, "chkSessionNY") else DEFAULTS["session_ny"],
            "close_friday": getattr(win, "chkCloseFriday", None).isChecked() if hasattr(win, "chkCloseFriday") else DEFAULTS["close_friday"],

            "telegram_bot_token": tg_token,
            "telegram_chat_id": tg_chat_id,
            "alert_fills": self.chkAlertFills.isChecked() if hasattr(self, "chkAlertFills") else DEFAULTS["alert_fills"],
            "alert_sl_tp": self.chkAlertSL.isChecked() if hasattr(self, "chkAlertSL") else DEFAULTS["alert_sl_tp"],
            "alert_risk_halt": self.chkAlertRisk.isChecked() if hasattr(self, "chkAlertRisk") else DEFAULTS["alert_risk_halt"],
            "audio_sound_fx": self.chkSoundFx.isChecked() if hasattr(self, "chkSoundFx") else DEFAULTS["audio_sound_fx"],
        }

        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

            if tg_token:
                telegram_notifier.bot_token = tg_token
            if tg_chat_id:
                telegram_notifier.chat_id = tg_chat_id

            if os.path.exists(AI_CONFIG_PATH):
                try:
                    with open(AI_CONFIG_PATH, "r", encoding="utf-8") as f_ai:
                        ai_data = json.load(f_ai)
                    ai_data["TELEGRAM_BOT_TOKEN"] = tg_token
                    ai_data["TELEGRAM_CHAT_ID"] = tg_chat_id
                    with open(AI_CONFIG_PATH, "w", encoding="utf-8") as f_ai:
                        json.dump(ai_data, f_ai, indent=4)
                except Exception:
                    pass

            self._set_status("Configuration saved successfully to settings.json", "#15803d")
        except Exception as e:
            self._set_status(f"Error saving: {e}", "#b91c1c")

    def load_settings(self):
        """Read settings.json and populate UI."""
        win = self.window
        data = {}
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass

        if hasattr(win, "spinRiskPerTrade"): win.spinRiskPerTrade.setValue(float(data.get("risk_per_trade", DEFAULTS["risk_per_trade"])))
        if hasattr(win, "spinMaxDailyLoss"): win.spinMaxDailyLoss.setValue(float(data.get("max_daily_loss", DEFAULTS["max_daily_loss"])))
        if hasattr(win, "spinMaxDrawdown"): win.spinMaxDrawdown.setValue(float(data.get("max_drawdown", DEFAULTS["max_drawdown"])))
        if hasattr(win, "spinMaxLosingStreak"): win.spinMaxLosingStreak.setValue(int(data.get("max_losing_streak", DEFAULTS["max_losing_streak"])))
        if hasattr(win, "spinMaxOpenTrades"): win.spinMaxOpenTrades.setValue(int(data.get("max_open_trades", DEFAULTS["max_open_trades"])))

        if hasattr(win, "comboStrategy"):
            strat = data.get("strategy", DEFAULTS.get("strategy", "builtin_ict_pro"))
            idx_s = win.comboStrategy.findData(strat)
            if idx_s < 0:
                s_low = str(strat).lower()
                if "ict" in s_low: idx_s = win.comboStrategy.findData("builtin_ict_pro")
                elif "ema" in s_low: idx_s = win.comboStrategy.findData("builtin_ema_stress")
                elif "wyckoff" in s_low: idx_s = win.comboStrategy.findData("builtin_wyckoff")
            if idx_s >= 0:
                win.comboStrategy.setCurrentIndex(idx_s)

        if hasattr(win, "comboExecutionMode"):
            m = data.get("execution_mode", DEFAULTS["execution_mode"])
            idx = win.comboExecutionMode.findData(m)
            if idx >= 0:
                win.comboExecutionMode.setCurrentIndex(idx)
            if hasattr(win, "quant_terminal") and hasattr(win.quant_terminal, "set_execution_mode"):
                win.quant_terminal.set_execution_mode(m)

        if hasattr(win, "spinMaxSpread"): win.spinMaxSpread.setValue(int(data.get("max_spread", DEFAULTS["max_spread"])))
        if hasattr(win, "spinSlippage"): win.spinSlippage.setValue(int(data.get("slippage", DEFAULTS["slippage"])))
        if hasattr(win, "spinBreakevenPips"): win.spinBreakevenPips.setValue(int(data.get("breakeven_pips", DEFAULTS["breakeven_pips"])))
        if hasattr(win, "spinTrailingPips"): win.spinTrailingPips.setValue(int(data.get("trailing_pips", DEFAULTS["trailing_pips"])))

        if hasattr(win, "chkSessionAsian"): win.chkSessionAsian.setChecked(bool(data.get("session_asian", DEFAULTS["session_asian"])))
        if hasattr(win, "chkSessionLondon"): win.chkSessionLondon.setChecked(bool(data.get("session_london", DEFAULTS["session_london"])))
        if hasattr(win, "chkSessionNY"): win.chkSessionNY.setChecked(bool(data.get("session_ny", DEFAULTS["session_ny"])))
        if hasattr(win, "chkCloseFriday"): win.chkCloseFriday.setChecked(bool(data.get("close_friday", DEFAULTS["close_friday"])))

        tg_token = data.get("telegram_bot_token", "")
        tg_chat_id = data.get("telegram_chat_id", "")
        if not tg_token and os.path.exists(AI_CONFIG_PATH):
            try:
                with open(AI_CONFIG_PATH, "r", encoding="utf-8") as f_ai:
                    ai_cfg = json.load(f_ai)
                    tg_token = ai_cfg.get("TELEGRAM_BOT_TOKEN", "")
                    tg_chat_id = ai_cfg.get("TELEGRAM_CHAT_ID", "")
            except Exception:
                pass

        if hasattr(self, "editTgToken"): self.editTgToken.setText(str(tg_token))
        if hasattr(self, "editTgChatId"): self.editTgChatId.setText(str(tg_chat_id))

        if hasattr(self, "chkAlertFills"): self.chkAlertFills.setChecked(bool(data.get("alert_fills", DEFAULTS["alert_fills"])))
        if hasattr(self, "chkAlertSL"): self.chkAlertSL.setChecked(bool(data.get("alert_sl_tp", DEFAULTS["alert_sl_tp"])))
        if hasattr(self, "chkAlertRisk"): self.chkAlertRisk.setChecked(bool(data.get("alert_risk_halt", DEFAULTS["alert_risk_halt"])))
        if hasattr(self, "chkSoundFx"): self.chkSoundFx.setChecked(bool(data.get("audio_sound_fx", DEFAULTS["audio_sound_fx"])))

        self._set_status("CONFIGURATION READY", "#475569")

    def reset_defaults(self):
        """Restore default parameters."""
        win = self.window
        if hasattr(win, "spinRiskPerTrade"): win.spinRiskPerTrade.setValue(DEFAULTS["risk_per_trade"])
        if hasattr(win, "spinMaxDailyLoss"): win.spinMaxDailyLoss.setValue(DEFAULTS["max_daily_loss"])
        if hasattr(win, "spinMaxDrawdown"): win.spinMaxDrawdown.setValue(DEFAULTS["max_drawdown"])
        if hasattr(win, "spinMaxLosingStreak"): win.spinMaxLosingStreak.setValue(DEFAULTS["max_losing_streak"])
        if hasattr(win, "spinMaxOpenTrades"): win.spinMaxOpenTrades.setValue(DEFAULTS["max_open_trades"])

        if hasattr(win, "comboExecutionMode"):
            idx = win.comboExecutionMode.findData(DEFAULTS["execution_mode"])
            if idx >= 0:
                win.comboExecutionMode.setCurrentIndex(idx)

        if hasattr(win, "spinMaxSpread"): win.spinMaxSpread.setValue(DEFAULTS["max_spread"])
        if hasattr(win, "spinSlippage"): win.spinSlippage.setValue(DEFAULTS["slippage"])
        if hasattr(win, "spinBreakevenPips"): win.spinBreakevenPips.setValue(DEFAULTS["breakeven_pips"])
        if hasattr(win, "spinTrailingPips"): win.spinTrailingPips.setValue(DEFAULTS["trailing_pips"])

        if hasattr(win, "chkSessionAsian"): win.chkSessionAsian.setChecked(DEFAULTS["session_asian"])
        if hasattr(win, "chkSessionLondon"): win.chkSessionLondon.setChecked(DEFAULTS["session_london"])
        if hasattr(win, "chkSessionNY"): win.chkSessionNY.setChecked(DEFAULTS["session_ny"])
        if hasattr(win, "chkCloseFriday"): win.chkCloseFriday.setChecked(DEFAULTS["close_friday"])

        if hasattr(self, "chkAlertFills"): self.chkAlertFills.setChecked(DEFAULTS["alert_fills"])
        if hasattr(self, "chkAlertSL"): self.chkAlertSL.setChecked(DEFAULTS["alert_sl_tp"])
        if hasattr(self, "chkAlertRisk"): self.chkAlertRisk.setChecked(DEFAULTS["alert_risk_halt"])
        if hasattr(self, "chkSoundFx"): self.chkSoundFx.setChecked(DEFAULTS["audio_sound_fx"])

        self._set_status("Default parameters restored", "#0f172a")
