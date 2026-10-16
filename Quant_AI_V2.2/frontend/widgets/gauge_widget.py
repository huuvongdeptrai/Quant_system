"""GaugeWidget - Semicircular gauge for fintech dashboard (DXY, US10Y indicators)."""
import math
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QConicalGradient, QBrush
from PySide6.QtCore import Qt, QRectF, QPointF


class GaugeWidget(QWidget):
    """A semicircular speedometer-style gauge widget.

    Draws a 180-degree arc with red-yellow-green gradient,
    a needle pointing to the current value, title text above,
    and value text below.
    """

    def __init__(
        self,
        title="DXY",
        value=4.9,
        suffix="%",
        min_val=0,
        max_val=10,
        parent=None,
    ):
        super().__init__(parent)
        self.title = title
        self._value = value
        self.suffix = suffix
        self.min_val = min_val
        self.max_val = max_val
        self._custom_text = None
        self.is_dark = True
        self.setMinimumSize(120, 90)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def set_dark_theme(self, is_dark: bool):
        """Update gauge theme mode (Dark/Light) and repaint."""
        self.is_dark = is_dark
        self.update()

    def setValue(self, value):
        """Update the gauge value and trigger repaint."""
        self._value = value
        self.update()

    @property
    def value(self):
        return self._value

    def setRange(self, min_val, max_val):
        """Set the minimum and maximum range."""
        self.min_val = min_val
        self.max_val = max_val
        self.update()

    def setValueText(self, text):
        """Override the displayed value text (e.g. '+0.23%')."""
        self._custom_text = text
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        # Layout constants
        title_area_h = 18
        value_area_h = 22
        arc_margin_x = 16
        arc_top = title_area_h + 4
        arc_diameter = min(w - 2 * arc_margin_x, (h - title_area_h - value_area_h) * 2)
        if arc_diameter < 30:
            arc_diameter = 30

        arc_rect = QRectF(
            (w - arc_diameter) / 2,
            arc_top,
            arc_diameter,
            arc_diameter,
        )
        center_x = arc_rect.center().x()
        center_y = arc_rect.center().y()

        # --- Draw arc with gradient ---
        gradient = QConicalGradient(QPointF(center_x, center_y), 180)
        # At 180 deg (left) = red, at 90 deg (top center) = yellow, at 0 deg (right) = green
        gradient.setColorAt(0.0, QColor("#ef4444"))   # left = red
        gradient.setColorAt(0.25, QColor("#f59e0b"))  # quarter = amber
        gradient.setColorAt(0.5, QColor("#22c55e"))   # right = green
        gradient.setColorAt(0.75, QColor("#22c55e"))  # fill rest green
        gradient.setColorAt(1.0, QColor("#ef4444"))   # wrap back

        arc_pen = QPen(QBrush(gradient), 7, Qt.SolidLine, Qt.FlatCap)
        painter.setPen(arc_pen)
        # drawArc uses 1/16th degree units; 180*16 start, -180*16 span (clockwise)
        painter.drawArc(arc_rect, 180 * 16, -180 * 16)

        # --- Draw needle ---
        val_range = self.max_val - self.min_val
        if val_range <= 0:
            val_range = 1
        clamped = max(self.min_val, min(self._value, self.max_val))
        val_pct = (clamped - self.min_val) / val_range

        # Angle: 180 deg (left/red) to 0 deg (right/green)
        angle_deg = 180.0 - (val_pct * 180.0)
        angle_rad = math.radians(angle_deg)

        radius = arc_diameter / 2 - 6
        needle_end_x = center_x + radius * math.cos(angle_rad)
        needle_end_y = center_y - radius * math.sin(angle_rad)

        # Needle line
        needle_color = QColor("#f8fafc" if self.is_dark else "#0f172a")
        needle_pen = QPen(needle_color, 2, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(needle_pen)
        painter.drawLine(
            QPointF(center_x, center_y),
            QPointF(needle_end_x, needle_end_y),
        )

        # Center dot
        painter.setPen(Qt.NoPen)
        painter.setBrush(needle_color)
        painter.drawEllipse(QPointF(center_x, center_y), 3, 3)

        # --- Title text (top center) ---
        title_font = QFont("Segoe UI", 9)
        title_font.setWeight(QFont.Bold)
        painter.setFont(title_font)
        painter.setPen(QColor("#64748b" if self.is_dark else "#475569"))
        painter.drawText(
            QRectF(0, 2, w, title_area_h),
            Qt.AlignHCenter | Qt.AlignTop,
            self.title,
        )

        # --- Three-dot menu icon (top right) ---
        painter.setPen(QColor("#475569" if self.is_dark else "#94a3b8"))
        dot_font = QFont("Segoe UI", 10)
        painter.setFont(dot_font)
        painter.drawText(QRectF(w - 20, 0, 18, title_area_h), Qt.AlignCenter, chr(8942))

        # --- Value text (below arc center) ---
        val_font = QFont("Consolas", 13)
        val_font.setWeight(QFont.Bold)
        painter.setFont(val_font)

        if val_pct > 0.6:
            val_color = QColor("#22c55e" if self.is_dark else "#16a34a")
        elif val_pct > 0.3:
            val_color = QColor("#f59e0b" if self.is_dark else "#d97706")
        else:
            val_color = QColor("#ef4444" if self.is_dark else "#dc2626")

        painter.setPen(val_color)

        if self._custom_text:
            display_text = self._custom_text
        else:
            display_text = f"{self._value}{self.suffix}"

        val_rect = QRectF(0, center_y + 4, w, value_area_h)
        painter.drawText(val_rect, Qt.AlignHCenter | Qt.AlignTop, display_text)

        painter.end()
