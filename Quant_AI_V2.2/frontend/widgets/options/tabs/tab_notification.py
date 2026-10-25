"""
Tab 4: Telegram Notifications & Event Subscriptions Configuration Widget.
Responsible for Telegram bot API credentials, test message dispatching,
and event alerting filters (fills, SL/TP hits, circuit breaker halts).
Compact MT5-style institutional layout.
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

    def _create_row(self, label_text: str, widget: QWidget, label_width: int = 120) -> QWidget:
        row = QWidget()
        r_lay = QHBoxLayout(row)
        r_lay.setContentsMargins(0, 0, 0, 0)
        r_lay.setSpacing(10)

        lbl = QLabel(label_text)
        lbl.setFixedWidth(label_width)
        lbl.setStyleSheet("font-family: 'Segoe UI', sans-serif; font-size: 11px; color: #334155;")
        r_lay.addWidget(lbl)

        if hasattr(widget, "setFixedHeight"):
            widget.setFixedHeight(23)
        r_lay.addWidget(widget, 1)
        return row

    def _setup_ui(self):
        layout_main = QVBoxLayout(self)
        layout_main.setContentsMargins(8, 8, 8, 8)
        layout_main.setSpacing(8)

        # 1. Telegram Bot Integration
        grp_tg = QGroupBox("Telegram Bot")
        lay_tg = QVBoxLayout(grp_tg)
        lay_tg.setContentsMargins(8, 10, 8, 8)
        lay_tg.setSpacing(6)

        self.editTgToken = QLineEdit()
        self.editTgToken.setEchoMode(QLineEdit.Password)
        self.editTgToken.setPlaceholderText("Paste BotFather API Token")

        self.editTgChatId = QLineEdit()
        self.editTgChatId.setPlaceholderText("Target Chat / Channel ID")

        self.btnTest = QPushButton("Send Test")
        self.btnTest.setCursor(Qt.PointingHandCursor)
        if self.on_test_callback:
            self.btnTest.clicked.connect(self.on_test_callback)

        lay_tg.addWidget(self._create_row("Bot Token:", self.editTgToken))
        lay_tg.addWidget(self._create_row("Chat ID:", self.editTgChatId))
        lay_tg.addWidget(self._create_row("Test Bot:", self.btnTest))

        # 2. Event Alert Subscriptions
        grp_sub = QGroupBox("Alert Events")
        lay_sub = QVBoxLayout(grp_sub)
        lay_sub.setContentsMargins(8, 10, 8, 8)
        lay_sub.setSpacing(6)

        self.chkAlertFills = QCheckBox("Notify on order fill")
        self.chkAlertSL = QCheckBox("Notify on SL / TP hit")
        self.chkAlertRisk = QCheckBox("Notify on risk halt")
        self.chkSoundFx = QCheckBox("Play sound on triggers")

        lay_sub.addWidget(self._create_row("Order Fills:", self.chkAlertFills))
        lay_sub.addWidget(self._create_row("SL / TP Hits:", self.chkAlertSL))
        lay_sub.addWidget(self._create_row("Risk Halts:", self.chkAlertRisk))
        lay_sub.addWidget(self._create_row("Audio Alerts:", self.chkSoundFx))

        layout_main.addWidget(grp_tg)
        layout_main.addWidget(grp_sub)
        layout_main.addStretch()

    def load_values(self, data: Dict[str, Any], defaults: Dict[str, Any], fallback_token: str = "", fallback_chat: str = "") -> None:
        """Populates notification controls from settings dictionary."""
        tok = data.get("telegram_bot_token", fallback_token)
        cid = data.get("telegram_chat_id", fallback_chat)
        self.editTgToken.setText(tok)
        self.editTgChatId.setText(cid)

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
        """Sends test verification payload to Telegram endpoint."""
        token = self.editTgToken.text().strip()
        chat_id = self.editTgChatId.text().strip()
        if not token or not chat_id:
            return False, "Error: Bot Token and Chat ID cannot be empty."

        telegram_notifier.bot_token = token
        telegram_notifier.chat_id = chat_id
        success = telegram_notifier.send_message(
            "<b>[VECTRA] System Options Telemetry Test</b>\n"
            "Status: Gateway Online\n"
            "Configuration: Dispatched successfully.",
            category="info"
        )
        if success:
            return True, "Telegram alert sent successfully!"
        return False, "Failed to send Telegram alert. Verify API credentials."
