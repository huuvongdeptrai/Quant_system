"""
Tab 4: Telegram Notifications & Event Subscriptions Configuration Widget.
Responsible for Telegram bot API credentials, test message dispatching,
and event alerting filters (fills, SL/TP hits, circuit breaker halts).
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QGroupBox
)
from PySide6.QtCore import Qt
from typing import Dict, Any, Callable, Optional, Tuple
from loguru import logger

from backend.infrastructure.notifications.telegram_notifier import telegram_notifier


class NotificationSettingsTab(QWidget):
    """UI tab component for Telegram alerts and event subscription routing."""

    def __init__(self, parent=None, on_test_callback: Optional[Callable[[], None]] = None):
        super().__init__(parent)
        self.on_test_callback = on_test_callback
        self._setup_ui()

    def _create_row(self, label_text: str, widget: QWidget, label_width: int = 125) -> QWidget:
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
        layout_main = QVBoxLayout(self)
        layout_main.setContentsMargins(14, 12, 14, 12)
        layout_main.setSpacing(10)

        lbl_desc = QLabel("Telegram bot alerts, execution event broadcasting, and audio notifications.")
        lbl_desc.setStyleSheet("color: #64748b; font-family: 'Segoe UI', sans-serif; font-size: 11px;")
        layout_main.addWidget(lbl_desc)

        cols = QWidget()
        cols_lay = QHBoxLayout(cols)
        cols_lay.setContentsMargins(0, 0, 0, 0)
        cols_lay.setSpacing(14)

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

        self.btnTgTest = QPushButton("Test Telegram Bot")
        self.btnTgTest.setCursor(Qt.PointingHandCursor)
        if self.on_test_callback:
            self.btnTgTest.clicked.connect(self.on_test_callback)

        lay_tg.addWidget(self._create_row("Telegram Token:", self.editTgToken))
        lay_tg.addWidget(self._create_row("Channel / Chat ID:", self.editTgChatId))
        lay_tg.addWidget(self._create_row("Message Format:", ro_fmt))
        lay_tg.addWidget(self._create_row("Connection Test:", self.btnTgTest))

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

        cols_lay.addWidget(grp_tg)
        cols_lay.addWidget(grp_alerts)
        layout_main.addWidget(cols)
        layout_main.addStretch()

    def load_values(self, data: Dict[str, Any], defaults: Dict[str, Any], fallback_token: str = "", fallback_chat: str = "") -> None:
        """Populates notification control widgets from settings dictionary."""
        tg_token = data.get("telegram_bot_token", "") or fallback_token
        tg_chat_id = data.get("telegram_chat_id", "") or fallback_chat

        self.editTgToken.setText(str(tg_token))
        self.editTgChatId.setText(str(tg_chat_id))

        self.chkAlertFills.setChecked(bool(data.get("alert_fills", defaults["alert_fills"])))
        self.chkAlertSL.setChecked(bool(data.get("alert_sl_tp", defaults["alert_sl_tp"])))
        self.chkAlertRisk.setChecked(bool(data.get("alert_risk_halt", defaults["alert_risk_halt"])))
        self.chkSoundFx.setChecked(bool(data.get("audio_sound_fx", defaults["audio_sound_fx"])))

    def get_values(self) -> Dict[str, Any]:
        """Extracts current notification settings."""
        return {
            "telegram_bot_token": self.editTgToken.text().strip(),
            "telegram_chat_id": self.editTgChatId.text().strip(),
            "alert_fills": self.chkAlertFills.isChecked(),
            "alert_sl_tp": self.chkAlertSL.isChecked(),
            "alert_risk_halt": self.chkAlertRisk.isChecked(),
            "audio_sound_fx": self.chkSoundFx.isChecked(),
        }

    def test_telegram_dispatch(self) -> Tuple[bool, str]:
        """Dispatches a test notification and updates status."""
        tok = self.editTgToken.text().strip()
        cid = self.editTgChatId.text().strip()
        if not cid:
            return False, "Missing Chat ID"

        if tok:
            telegram_notifier.bot_token = tok
        telegram_notifier.chat_id = cid

        try:
            telegram_notifier.send_message("🔔 <b>[Quant System]</b> Test notification dispatched from Options.")
            return True, f"Telegram test sent to {cid}"
        except Exception as e:
            logger.debug(f"[NotificationSettingsTab] Telegram test error: {e}")
            return False, f"Telegram Error: {e}"
