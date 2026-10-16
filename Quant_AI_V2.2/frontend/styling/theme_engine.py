"""
Quant Terminal V2.2 - Design Token & Theme Synchronization Engine
Dedicated to Institutional Pure Light Theme (TradingView / Bloomberg Light).
"""

from dataclasses import dataclass
from typing import Dict, Any
import os
import pyqtgraph as pg
from PySide6.QtGui import QColor, QFont


@dataclass(frozen=True)
class ThemeTokens:
    is_dark: bool

    # Surfaces & Canvas
    bg_canvas: str
    bg_surface: str
    bg_card: str
    bg_card_hover: str
    bg_input: str

    # Borders
    border_subtle: str
    border_strong: str

    # Typography
    text_primary: str
    text_secondary: str
    text_muted: str

    # Semantic Status & Financial Accents
    accent_primary: str      # Slate/Dark Charcoal
    accent_secondary: str    # Blue
    pnl_profit: str          # Green
    pnl_profit_bg: str       # Translucent green
    pnl_loss: str            # Red
    pnl_loss_bg: str         # Translucent red
    warning: str             # Amber
    warning_bg: str          # Translucent amber
    info: str                # Blue
    info_bg: str             # Translucent blue
    purple: str              # Purple/Violet
    purple_bg: str           # Translucent purple


LIGHT_TOKENS = ThemeTokens(
    is_dark=False,
    bg_canvas="#f1f5f9",
    bg_surface="#ffffff",
    bg_card="#ffffff",
    bg_card_hover="#f8fafc",
    bg_input="#f8fafc",
    border_subtle="rgba(0, 0, 0, 0.08)",
    border_strong="rgba(0, 0, 0, 0.16)",
    text_primary="#0f172a",
    text_secondary="#334155",
    text_muted="#64748b",
    accent_primary="#27272a",
    accent_secondary="#0369a1",
    pnl_profit="#16a34a",
    pnl_profit_bg="rgba(22, 163, 74, 0.12)",
    pnl_loss="#dc2626",
    pnl_loss_bg="rgba(220, 38, 38, 0.12)",
    warning="#d97706",
    warning_bg="rgba(217, 119, 6, 0.12)",
    info="#2563eb",
    info_bg="rgba(37, 99, 235, 0.12)",
    purple="#9333ea",
    purple_bg="rgba(147, 51, 234, 0.12)",
)

# Dark theme removed per user directive. Alias to LIGHT_TOKENS for compatibility.
DARK_TOKENS = LIGHT_TOKENS


class ThemeEngine:
    """Central manager for application-wide theme state and graph synchronization (Locked to Light Theme)."""

    @staticmethod
    def get_tokens(is_dark: bool = False) -> ThemeTokens:
        return LIGHT_TOKENS

    @staticmethod
    def sync_pyqtgraph_plot(plot_widget: pg.PlotWidget, is_dark: bool = False):
        """Uniformly synchronizes a pyqtgraph PlotWidget to Light theme."""
        if not plot_widget:
            return

        tokens = LIGHT_TOKENS
        plot_widget.setBackground(tokens.bg_surface)

        text_color = tokens.text_muted
        axis_pen = pg.mkPen(color="#cbd5e1", width=1)
        grid_alpha = 35

        for axis_name in ["left", "bottom", "right", "top"]:
            ax = plot_widget.getAxis(axis_name)
            if ax:
                ax.setPen(axis_pen)
                ax.setTextPen(text_color)
                ax.setTickFont(QFont("Consolas", 8))

        plot_widget.showGrid(x=True, y=True, alpha=grid_alpha / 100.0)

    @staticmethod
    def get_pnl_badge_colors(is_profit: bool, is_dark: bool = False) -> tuple[QColor, QColor]:
        """Returns (background_QColor, text_QColor) for PnL and trade badges in Light Theme."""
        if is_profit:
            bg = QColor(22, 163, 74, 35)
            fg = QColor("#059669")
        else:
            bg = QColor(220, 38, 38, 35)
            fg = QColor("#b91c1c")
        return bg, fg

    @staticmethod
    def get_level_badge_colors(level: str, is_dark: bool = False) -> tuple[QColor, QColor]:
        """Returns (background_QColor, text_QColor) for log pills in Light Theme."""
        lvl = level.upper().strip()
        tokens = LIGHT_TOKENS

        if "EXEC" in lvl or "TRADE" in lvl:
            bg = QColor(22, 163, 74, 30)
            fg = QColor(tokens.pnl_profit)
        elif "WARN" in lvl:
            bg = QColor(217, 119, 6, 30)
            fg = QColor(tokens.warning)
        elif "ERR" in lvl or "CRIT" in lvl:
            bg = QColor(220, 38, 38, 30)
            fg = QColor(tokens.pnl_loss)
        elif "RECOV" in lvl or "SYS" in lvl:
            bg = QColor(147, 51, 234, 30)
            fg = QColor(tokens.purple)
        else:  # INFO / default
            bg = QColor(37, 99, 235, 30)
            fg = QColor(tokens.info)

        return bg, fg
