"""SwitchWidget - Custom PySide6 switch toggle widget for Auto-Execution Bot control.

Option B chosen by user: Label 'Tự động giao dịch: TẮT / BẬT' with smooth pill switch.
"""

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget


class SwitchButton(QWidget):
    """The interactive pill switch button itself."""

    toggled = Signal(bool)

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self._checked = checked
        self.setFixedSize(40, 22)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def isChecked(self):
        return self._checked

    def setChecked(self, val):
        if self._checked != val:
            self._checked = val
            self.update()
            self.toggled.emit(self._checked)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setChecked(not self._checked)
            event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        r = h / 2.0

        track_rect = QRectF(1, 1, w - 2, h - 2)
        if self._checked:
            track_brush = QBrush(QColor("#16a34a"))  # Emerald green when ON
            track_pen = Qt.NoPen
        else:
            track_brush = QBrush(QColor("#1e293b"))  # Slate dark when OFF
            track_pen = QPen(QColor("#334155"), 1)

        painter.setBrush(track_brush)
        painter.setPen(track_pen)
        painter.drawRoundedRect(track_rect, r, r)

        # Knob
        knob_d = h - 4
        knob_y = 2
        if self._checked:
            knob_x = w - knob_d - 2
            knob_color = QColor("#ffffff")
        else:
            knob_x = 2
            knob_color = QColor("#94a3b8")

        painter.setBrush(QBrush(knob_color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(knob_x, knob_y, knob_d, knob_d))
        painter.end()


class AutoTradeControlWidget(QWidget):
    """Container card with title, status label and the switch button."""

    state_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cardAutoTrade")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(1)
        text_layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_title = QLabel("Automated Trading")
        self.lbl_title.setStyleSheet(
            "color: #f8fafc; font-size: 11px; font-weight: 700; font-family: 'Segoe UI';"
        )
        text_layout.addWidget(self.lbl_title)

        self.lbl_sub = QLabel("Mode: OFF (STANDBY)")
        self.lbl_sub.setStyleSheet(
            "color: #64748b; font-size: 9.5px; font-family: 'Consolas', monospace;"
        )
        text_layout.addWidget(self.lbl_sub)

        layout.addLayout(text_layout)
        layout.addStretch()

        self.switch_btn = SwitchButton(checked=False)
        self.switch_btn.toggled.connect(self._on_toggled)
        layout.addWidget(self.switch_btn)

        self.setStyleSheet("""
            QWidget#cardAutoTrade {
                background-color: #080b11;
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 8px;
            }
        """)

    def set_running(self, running, strat_name=""):
        self.switch_btn.setChecked(running)
        self._update_text(running, strat_name)

    def _on_toggled(self, val):
        self._update_text(val)
        self.state_changed.emit(val)

    def _update_text(self, running, strat_name=""):
        if running:
            strat_info = f" ({strat_name})" if strat_name else ""
            self.lbl_sub.setText(f"Mode: ACTIVE{strat_info}")
            self.lbl_sub.setStyleSheet(
                "color: #22c55e; font-size: 9.5px; font-weight: bold; font-family: 'Consolas', monospace;"
            )
        else:
            self.lbl_sub.setText("Mode: OFF (STANDBY)")
            self.lbl_sub.setStyleSheet(
                "color: #64748b; font-size: 9.5px; font-family: 'Consolas', monospace;"
            )
