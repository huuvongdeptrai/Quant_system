"""ThemeToggleSwitch - Custom PySide6 widget for Sun / Moon theme toggling.

Pixel-perfect implementation of the institutional toggle switch matching media_1790000264879.png:
- Clean monochrome palette (no bright orange/yellow emojis or text).
- Dark mode: Solid black track, silver crescent moon on the left, smooth solid white knob on the right.
- Light mode: Soft light gray track, smooth solid white knob on the left, subtle etched sun on the right.
- Full interactive mouse events and smooth hover states.
"""

import math
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


class ThemeToggleSwitch(QWidget):
    """Clean institutional pill switch toggle between Dark (Moon) and Light (Sun) modes."""

    theme_changed = Signal(bool)  # True = Dark, False = Light

    def __init__(self, is_dark=True, parent=None):
        super().__init__(parent)
        self._is_dark = is_dark
        self._is_hovered = False
        self.setFixedSize(54, 26)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._update_tooltip()

    def _update_tooltip(self):
        if self._is_dark:
            self.setToolTip("Theme: DARK — Click to switch to Light Mode")
        else:
            self.setToolTip("Theme: LIGHT — Click to switch to Dark Mode")

    def is_dark(self):
        return self._is_dark

    def set_dark(self, val):
        if self._is_dark != val:
            self._is_dark = val
            self._update_tooltip()
            self.update()
            self.theme_changed.emit(self._is_dark)

    def enterEvent(self, event):
        self._is_hovered = True
        self.update()

    def leaveEvent(self, event):
        self._is_hovered = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.set_dark(not self._is_dark)
            event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        r = h / 2.0
        knob_d = h - 6.0
        knob_y = 3.0

        if self._is_dark:
            # Track: Deep Matte Black/Navy
            track_bg = QColor("#090d16") if not self._is_hovered else QColor("#0e1524")
            track_border = QColor("#1e293b") if not self._is_hovered else QColor("#334155")
            painter.setBrush(QBrush(track_bg))
            painter.setPen(QPen(track_border, 1.2))
            painter.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), r, r)

            # Left side: Crisp White/Silver Crescent Moon etched on track
            moon_cx = 14.0
            moon_cy = h / 2.0
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor("#f8fafc")))
            outer = QPainterPath()
            outer.addEllipse(QPointF(moon_cx, moon_cy), 5.5, 5.5)
            cutter = QPainterPath()
            cutter.addEllipse(QPointF(moon_cx + 2.5, moon_cy - 1.5), 4.8, 4.8)
            moon = outer.subtracted(cutter)
            painter.drawPath(moon)

            # Right side: Solid White Knob (Smooth iOS thumb)
            knob_x = w - knob_d - 3.0
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.setPen(QPen(QColor("#cbd5e1"), 0.8))
            painter.drawEllipse(QRectF(knob_x, knob_y, knob_d, knob_d))

        else:
            # Light Mode: Soft matte light gray track
            track_bg = QColor("#e2e8f0") if not self._is_hovered else QColor("#cbd5e1")
            track_border = QColor("#cbd5e1") if not self._is_hovered else QColor("#94a3b8")
            painter.setBrush(QBrush(track_bg))
            painter.setPen(QPen(track_border, 1.2))
            painter.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), r, r)

            # Left side: Solid White Knob (Smooth iOS thumb)
            knob_x = 3.0
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.setPen(QPen(QColor("#94a3b8"), 0.8))
            painter.drawEllipse(QRectF(knob_x, knob_y, knob_d, knob_d))

            # Right side: Etched Subtle Sun (Monochrome / Matte Slate Gray)
            sun_cx = w - 14.0
            sun_cy = h / 2.0
            painter.setPen(QPen(QColor("#94a3b8"), 1.3))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(sun_cx, sun_cy), 3.2, 3.2)
            for i in range(8):
                angle = i * (math.pi / 4.0)
                p1 = QPointF(
                    sun_cx + 4.5 * math.cos(angle),
                    sun_cy + 4.5 * math.sin(angle),
                )
                p2 = QPointF(
                    sun_cx + 6.5 * math.cos(angle),
                    sun_cy + 6.5 * math.sin(angle),
                )
                painter.drawLine(p1, p2)

        painter.end()
