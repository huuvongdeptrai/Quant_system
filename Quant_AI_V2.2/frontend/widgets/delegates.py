"""
Quant Terminal V2.2 - High-Performance Vector Item Delegates
Custom QStyledItemDelegate implementations using direct QPainter vector drawing.
Replaces brittle QWidget nesting (setCellWidget anti-pattern) with 100% deterministic,
leak-free rendering that repaints cleanly on Dark/Light theme changes in sub-milliseconds.
"""

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush
from PySide6.QtWidgets import QStyledItemDelegate, QStyle

from frontend.styling.formatters import fmt_currency, fmt_pips
from frontend.styling.theme_engine import ThemeEngine


class TradeZellaCalendarDelegate(QStyledItemDelegate):
    """
    Renders TradeZella-style calendar day cards directly via QPainter.
    Expected data structure in index.data(Qt.UserRole):
    {
        "day": int,
        "pnl": float,
        "count": int,
        "is_today": bool,
        "is_dark": bool
    }
    """

    def paint(self, painter: QPainter, option, index):
        data = index.data(Qt.UserRole)
        if not data or not isinstance(data, dict):
            super().paint(painter, option, index)
            return

        day = data.get("day", 0) or 0
        pnl_raw = data.get("pnl")
        pnl = float(pnl_raw) if pnl_raw is not None else 0.0
        count = data.get("trades") or data.get("count") or 0
        is_today = bool(data.get("is_today", False))
        is_dark = bool(data.get("is_dark", False))

        tokens = ThemeEngine.get_tokens(is_dark)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        rect = QRectF(option.rect)

        # Collapsed 1px grid border per Institutional Standard
        is_cur_month = data.get("is_current_month", True)
        is_other = bool(data.get("is_other", not is_cur_month))
        grid_border = QColor("#262626" if is_dark else "#e2e8f0")
        painter.setPen(QPen(grid_border, 1.0))

        if is_other or day == 0:
            # Subtle cell for adjacent month days
            painter.setBrush(QColor("#0a0a0a" if is_dark else "#f8fafc"))
            painter.drawRect(rect)
            if day > 0:
                painter.setFont(QFont("Segoe UI", 9, QFont.Normal))
                painter.setPen(QColor("#334155" if is_dark else "#cbd5e1"))
                day_rect = QRectF(rect.x() + 4, rect.y() + 2, 20, 14)
                painter.drawText(day_rect, Qt.AlignLeft | Qt.AlignVCenter, str(day))
            painter.restore()
            return

        has_trades = count > 0 or (pnl_raw is not None and abs(pnl) > 0.001)
        is_profit = pnl >= 0

        if not has_trades:
            bg_color = QColor("#121212" if is_dark else "#ffffff")
        elif is_profit:
            bg_color = QColor(34, 197, 94, 25 if is_dark else 20)
        else:
            bg_color = QColor(239, 68, 68, 25 if is_dark else 20)

        painter.setBrush(bg_color)
        painter.drawRect(rect)

        # Day number in top-left (bold neutral for today, no colored borders)
        day_color = QColor("#f8fafc" if is_dark else "#0f172a") if is_today else QColor("#64748b")
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold if is_today else QFont.Normal))
        painter.setPen(day_color)
        day_rect = QRectF(rect.x() + 4, rect.y() + 2, 20, 14)
        painter.drawText(day_rect, Qt.AlignLeft | Qt.AlignVCenter, str(day))

        # Trade count indicator
        if has_trades and count > 0:
            painter.setFont(QFont("Consolas", 8))
            painter.setPen(QColor("#94a3b8" if is_dark else "#64748b"))
            count_rect = QRectF(rect.right() - 24, rect.y() + 2, 20, 14)
            painter.drawText(count_rect, Qt.AlignRight | Qt.AlignVCenter, f"{count}L")

        # Center PnL text (Matte institutional tones, strictly zero neon)
        if has_trades:
            pnl_text = fmt_currency(pnl, decimals=0, sign=True)
            painter.setFont(QFont("Consolas", 9, QFont.Bold))
            pnl_fg = QColor("#16a34a" if is_dark else "#15803d") if is_profit else QColor("#dc2626" if is_dark else "#b91c1c")
            painter.setPen(pnl_fg)
            center_rect = QRectF(rect.x(), rect.y() + 14, rect.width(), rect.height() - 16)
            painter.drawText(center_rect, Qt.AlignCenter, pnl_text)

        painter.restore()


class LogLevelPillDelegate(QStyledItemDelegate):
    """
    Renders rounded pill badges for the Log Level column in Tab 5.
    Avoids crude full-cell square coloring or nested widgets.
    """

    def __init__(self, parent=None, is_dark=True):
        super().__init__(parent)
        self.is_dark = is_dark

    def set_dark_theme(self, is_dark: bool):
        self.is_dark = is_dark

    def paint(self, painter: QPainter, option, index):
        level_text = index.data(Qt.DisplayRole)
        if not level_text:
            super().paint(painter, option, index)
            return

        lvl = str(level_text).strip().upper()
        bg, fg = ThemeEngine.get_level_badge_colors(lvl, self.is_dark)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        # Draw centered rounded pill
        rect = option.rect
        pill_w = min(rect.width() - 8, 88)
        pill_h = 18
        pill_x = rect.x() + (rect.width() - pill_w) // 2
        pill_y = rect.y() + (rect.height() - pill_h) // 2
        pill_rect = QRectF(pill_x, pill_y, pill_w, pill_h)

        painter.setBrush(bg)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(pill_rect, 2, 2)

        # Text
        painter.setFont(QFont("Consolas", 9, QFont.Bold))
        painter.setPen(fg)
        painter.drawText(pill_rect, Qt.AlignCenter, lvl)

        painter.restore()


class TableBadgeDelegate(QStyledItemDelegate):
    """
    Renders clean pill badges for table columns such as Type (BUY/SELL), PnL, Pips.
    """

    def __init__(self, parent=None, is_dark=True):
        super().__init__(parent)
        self.is_dark = is_dark

    def set_dark_theme(self, is_dark: bool):
        self.is_dark = is_dark

    def paint(self, painter: QPainter, option, index):
        text = index.data(Qt.DisplayRole)
        if not text:
            super().paint(painter, option, index)
            return

        str_val = str(text).strip()
        tokens = ThemeEngine.get_tokens(self.is_dark)

        # Detect badge type
        is_buy = str_val.upper() in ("BUY", "LONG")
        is_sell = str_val.upper() in ("SELL", "SHORT")
        has_dollar = "$" in str_val or "pips" in str_val or str_val.endswith(" p") or "%" in str_val

        if is_buy:
            bg, fg = ThemeEngine.get_pnl_badge_colors(is_profit=True, is_dark=self.is_dark)
        elif is_sell:
            bg, fg = ThemeEngine.get_pnl_badge_colors(is_profit=False, is_dark=self.is_dark)
        elif has_dollar:
            is_neg = "-" in str_val
            bg, fg = ThemeEngine.get_pnl_badge_colors(is_profit=not is_neg, is_dark=self.is_dark)
        else:
            # Standard cell rendering
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        rect = option.rect
        pill_w = min(rect.width() - 4, 98.0)
        pill_h = 18
        pill_x = rect.x() + (rect.width() - pill_w) / 2
        pill_y = rect.y() + (rect.height() - pill_h) / 2
        pill_rect = QRectF(pill_x, pill_y, pill_w, pill_h)

        painter.setBrush(bg)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(pill_rect, 2, 2)

        # Adaptive font size to avoid any text clipping in narrow cells
        font_sz = 9
        if len(str_val) * 7.5 > pill_w:
            font_sz = 8
        if len(str_val) * 6.5 > pill_w:
            font_sz = 7
        painter.setFont(QFont("Consolas", font_sz, QFont.Bold))
        painter.setPen(fg)
        painter.drawText(pill_rect, Qt.AlignCenter, str_val)

        painter.restore()
