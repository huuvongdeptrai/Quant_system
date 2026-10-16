"""BotPowerButton - Custom PySide6 vector-painted Power Button widget.

Replaces problematic Unicode glyphs with pixel-perfect vector QPainter geometry.
Provides immediate visual feedback, states (OFF / ON), hover effects, and custom signals.
"""

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget, QFrame, QHBoxLayout, QLabel


class BotPowerButton(QWidget):
    """Circular bot power button with institutional styling and vector power icon."""

    power_toggled = Signal(bool)  # True = RUNNING, False = STOPPED

    def __init__(self, is_running=False, parent=None):
        super().__init__(parent)
        self._is_running = is_running
        self._is_hovered = False
        self.is_dark = False
        self.setFixedSize(20, 20)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._update_tooltip()

    def set_dark_theme(self, is_dark: bool):
        """Update button styling for current theme."""
        self.is_dark = is_dark
        self.update()

    def _update_tooltip(self):
        if self._is_running:
            self.setToolTip("ALGO ENGINE: ACTIVE (Click to Halt)")
        else:
            self.setToolTip("ALGO ENGINE: STANDBY (Click to Arm)")

    def is_running(self):
        return self._is_running

    def set_running(self, val, emit_signal=True):
        if self._is_running != val:
            self._is_running = val
            self._update_tooltip()
            self.update()
            if emit_signal:
                self.power_toggled.emit(self._is_running)

    def enterEvent(self, event):
        self._is_hovered = True
        self.update()

    def leaveEvent(self, event):
        self._is_hovered = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.set_running(not self._is_running, emit_signal=True)
            event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        cx = w / 2.0
        cy = h / 2.0
        r_dim = min(w, h)

        # Background circular card
        if self._is_running:
            if self.is_dark:
                bg_color = QColor("#064e3b") if not self._is_hovered else QColor("#065f46")
                border_color = QColor("#272d3b")
                icon_color = QColor("#16a34a")
            else:
                bg_color = QColor("#dcfce7") if not self._is_hovered else QColor("#bbf7d0")
                border_color = QColor("#cbd5e1")
                icon_color = QColor("#15803d")
        else:
            if self.is_dark:
                bg_color = QColor("#0a0e17") if not self._is_hovered else QColor("#161d2d")
                border_color = (
                    QColor(255, 255, 255, 30)
                    if not self._is_hovered
                    else QColor(255, 255, 255, 60)
                )
                icon_color = QColor("#64748b") if not self._is_hovered else QColor("#94a3b8")
            else:
                bg_color = QColor("#ffffff") if not self._is_hovered else QColor("#f1f5f9")
                border_color = (
                    QColor("#cbd5e1")
                    if not self._is_hovered
                    else QColor("#94a3b8")
                )
                icon_color = QColor("#475569") if not self._is_hovered else QColor("#0f172a")

        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, 1.0))
        painter.drawEllipse(QRectF(1.0, 1.0, w - 2.0, h - 2.0))

        # Vector Power Symbol (circle with top gap + vertical bar)
        icon_stroke = max(1.1, r_dim * 0.08)
        icon_pen = QPen(icon_color, icon_stroke, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(icon_pen)
        painter.setBrush(Qt.NoBrush)

        arc_r = r_dim * 0.24
        arc_rect = QRectF(cx - arc_r, cy - arc_r, arc_r * 2.0, arc_r * 2.0)
        # Top gap of 60 deg centered at 90 deg: span from 120 deg to 60 deg (300 deg total).
        painter.drawArc(arc_rect, int(120 * 16), int(300 * 16))

        # Vertical bar from center upwards through gap
        painter.drawLine(QPointF(cx, cy - r_dim * 0.28), QPointF(cx, cy - r_dim * 0.04))

        painter.end()


class AlgoControlPill(QFrame):
    """Institutional Flat Algo State & Control Pill (24px height).

    Placed directly beside the Strategy Badge.
    Standby: White #ffffff bg, #cbd5e1 border, '○ STANDBY' (#64748b) | '▶ RUN' (#15803d)
    Active:  Neutral pale bg, #cbd5e1 border, '● ACTIVE' (#15803d) | '■ HALT' (#b91c1c)
    """

    clicked = Signal()

    def __init__(self, is_running=False, is_dark=False, parent=None):
        super().__init__(parent)
        self._is_running = is_running
        self.is_dark = is_dark
        self._is_hovered = False
        self.setFixedHeight(24)
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)

        self.lbl_status = QLabel()
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.lbl_sep = QLabel("|")
        self.lbl_sep.setAlignment(Qt.AlignCenter)
        self.lbl_sep.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.lbl_action = QLabel()
        self.lbl_action.setAlignment(Qt.AlignCenter)
        self.lbl_action.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        layout.addWidget(self.lbl_status)
        layout.addWidget(self.lbl_sep)
        layout.addWidget(self.lbl_action)

        self._update_style()

    def is_running(self):
        return self._is_running

    def set_running(self, val: bool, emit_signal: bool = False):
        if self._is_running != val:
            self._is_running = val
            self._update_style()
            if emit_signal:
                self.clicked.emit()

    def set_dark_theme(self, is_dark: bool):
        self.is_dark = is_dark
        self._update_style()

    def setText(self, text):
        """Backward compatibility noop."""
        pass

    def _update_style(self):
        # MT5 Standard Toolbar behavior:
        # Resting state: flat & borderless (seamless with toolbar, color contrast)
        # Hover state: clean 1px border box appears
        if self._is_running:
            self.setToolTip("ALGO ENGINE: ACTIVE (Click to Halt | HotKey: F5)")
            self.lbl_status.setText("● ACTIVE")
            self.lbl_action.setText("■ HALT")
            if self.is_dark:
                bg = "#064e3b" if not self._is_hovered else "#065f46"
                border = "transparent" if not self._is_hovered else "#059669"
                status_col = "#4ade80"
                action_col = "#f87171"
                sep_col = "rgba(255, 255, 255, 0.2)"
            else:
                bg = "#f0fdf4" if not self._is_hovered else "#dcfce7"
                border = "transparent" if not self._is_hovered else "#86efac"
                status_col = "#15803d"
                action_col = "#b91c1c"
                sep_col = "#86efac"
        else:
            self.setToolTip("ALGO ENGINE: STANDBY (Click to Run | HotKey: F5)")
            self.lbl_status.setText("○ STANDBY")
            self.lbl_action.setText("▶ RUN")
            if self.is_dark:
                bg = "transparent" if not self._is_hovered else "#161d2d"
                border = "transparent" if not self._is_hovered else "#475569"
                status_col = "#94a3b8" if not self._is_hovered else "#cbd5e1"
                action_col = "#22c55e" if not self._is_hovered else "#4ade80"
                sep_col = "rgba(255, 255, 255, 0.15)"
            else:
                bg = "transparent" if not self._is_hovered else "#ffffff"
                border = "transparent" if not self._is_hovered else "#cbd5e1"
                status_col = "#64748b" if not self._is_hovered else "#334155"
                action_col = "#15803d" if not self._is_hovered else "#166534"
                sep_col = "#cbd5e1"

        self.setStyleSheet(
            f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 3px; }}"
        )
        self.lbl_status.setStyleSheet(
            f"color: {status_col}; border: none; background: transparent; font-family: Consolas, monospace; font-size: 9px; font-weight: 700;"
        )
        self.lbl_sep.setStyleSheet(
            f"color: {sep_col}; border: none; background: transparent; font-family: Consolas, monospace; font-size: 9px;"
        )
        self.lbl_action.setStyleSheet(
            f"color: {action_col}; border: none; background: transparent; font-family: Consolas, monospace; font-size: 9px; font-weight: 800;"
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            event.accept()

    def enterEvent(self, event):
        self._is_hovered = True
        self._update_style()

    def leaveEvent(self, event):
        self._is_hovered = False
        self._update_style()
