"""
Watchlist Custom Item Delegate.
Renders monospace financial quotes, sub-labels, badge styling, and price changes.
"""

from PySide6.QtCore import Qt, QSize, QRect
from PySide6.QtWidgets import QStyledItemDelegate, QStyle
from PySide6.QtGui import QColor, QFont, QPainter, QBrush, QFontMetrics


class WatchlistDelegate(QStyledItemDelegate):
    """Custom table/tree cell painter for financial symbols and market quotes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_dark = True

    def set_dark(self, is_dark: bool):
        self.is_dark = is_dark

    def sizeHint(self, option, index):
        if index.parent().isValid():
            return QSize(option.rect.width(), 34)
        return QSize(option.rect.width(), 24)

    def paint(self, painter, option, index):
        if not index.parent().isValid():
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        is_dark = self.is_dark
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, QColor("#12151d" if is_dark else "#e2e8f0"))
        elif option.state & QStyle.State_MouseOver:
            painter.fillRect(option.rect, QColor("#0d1017" if is_dark else "#f1f5f9"))

        col = index.column()
        item_text = index.data(Qt.DisplayRole) or ""

        if col == 0:
            rect = option.rect
            x = rect.left() + 6
            parts = item_text.split("\n")
            sym = parts[0]
            sub = parts[1] if len(parts) > 1 else ""

            painter.setFont(QFont("Consolas", 10, QFont.Bold))
            painter.setPen(QColor("#f8fafc" if is_dark else "#0f172a"))
            painter.drawText(x, rect.top() + 15, sym)

            if sub:
                sub_font = QFont("Segoe UI", 8)
                painter.setFont(sub_font)
                painter.setPen(QColor("#94a3b8" if is_dark else "#64748b"))
                fm = QFontMetrics(sub_font)
                avail_w = max(10, rect.width() - 8)
                elided_sub = fm.elidedText(sub, Qt.ElideRight, avail_w)
                painter.drawText(x, rect.top() + 27, elided_sub)

        elif col in (1, 2, 3):
            # Uniform right alignment padding (-4px) perfectly matching QHeaderView section padding
            rect = option.rect.adjusted(0, 0, -4, 0)
            painter.setFont(QFont("Consolas", 9, QFont.Bold if col == 1 else QFont.Normal))
            fg = index.data(Qt.ForegroundRole)
            if fg and isinstance(fg, (QColor, QBrush)):
                painter.setPen(fg if isinstance(fg, QColor) else fg.color())
            else:
                default_color = (
                    QColor("#cbd5e1" if is_dark else "#0f172a")
                    if col == 1
                    else QColor("#94a3b8" if is_dark else "#64748b")
                )
                painter.setPen(default_color)
            painter.drawText(rect, Qt.AlignRight | Qt.AlignVCenter, item_text)

        elif col == 4:
            # Institutional Micro-Badge Container (Flat, 2px radius, subtle tint)
            rect = option.rect
            badge_text = item_text or "NEUT"
            fg = index.data(Qt.ForegroundRole)
            color_obj = fg if isinstance(fg, QColor) else (fg.color() if isinstance(fg, QBrush) else QColor("#64748b"))

            badge_w = 42
            badge_h = 18
            bx = rect.left() + (rect.width() - badge_w) // 2
            by = rect.top() + (rect.height() - badge_h) // 2
            box_rect = QRect(bx, by, badge_w, badge_h)

            bg_col = QColor(color_obj)
            bg_col.setAlpha(26 if is_dark else 22)
            border_col = QColor(color_obj)
            border_col.setAlpha(70 if is_dark else 65)

            painter.setBrush(QBrush(bg_col))
            painter.setPen(border_col)
            painter.drawRoundedRect(box_rect, 2, 2)

            painter.setFont(QFont("Consolas", 8, QFont.Bold))
            painter.setPen(color_obj)
            painter.drawText(box_rect, Qt.AlignCenter, badge_text)

        # Subtle row bottom divider line
        divider_color = QColor(255, 255, 255, 12 if is_dark else 18)
        painter.setPen(divider_color)
        painter.drawLine(option.rect.left(), option.rect.bottom(), option.rect.right(), option.rect.bottom())

        painter.restore()
