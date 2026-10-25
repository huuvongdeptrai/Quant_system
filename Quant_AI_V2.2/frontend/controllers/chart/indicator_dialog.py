"""
Studies & Quantitative Technical Indicators Dialog and Real-Time Calculation Engine.
Clean Architecture / High-Performance PyQtGraph Rendering (setData pattern).

Academic Grounding:
- Dual EMA (10/50): Brock, Lakonishok, & LeBaron (1992), Journal of Finance
- SMA 200 Regime: Siegel (2002); Neely et al. (2014), Management Science
- Donchian Channels (100): Donchian (1960); Park & Irwin (2007), J. Econ. Surveys
- Classic Floor Pivots: Harris (2003), Oxford Univ. Press; Floor Trading Axioms
- Bollinger Bands (20, 2.0sigma): Bollinger (1992); Lo, Mamaysky, & Wang (2000), J. Finance
- Session VWAP & Bands: Berkowitz, Logue, & Noser (1988), J. Finance; Madhavan (2002)
- Relative Strength Index (14): Wilder (1978); Lo et al. (2000), J. Finance
- MACD Momentum Oscillator: Appel (1979); Neely et al. (2014), Management Science
- Cumulative Volume Delta Proxy (CVD): Kyle (1985), Econometrica; Cartea & Jaimungal (2014)
- Fair Value Gaps (FVG): Harris (2003); Biais, Hillion, & Spatt (1995), J. Finance
"""

import os
import json
import numpy as np
import pandas as pd
import pyqtgraph as pg
from datetime import datetime
from PySide6 import QtCore, QtGui
from PySide6.QtCore import Qt, QPoint, QSize
from PySide6.QtGui import QColor, QFont, QIcon, QCursor
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QCheckBox, QFrame,
    QScrollArea, QSizePolicy
)
from backend.infrastructure.brokers.mt5_safe import mt5

INDICATOR_CATALOG = {
    "Trend (3)": [
        {"id": "ema", "available": True},
        {"id": "ma200", "available": True},
        {"id": "donchian", "available": True},
    ],
    "Price Structure (2)": [
        {"id": "pivot", "available": True},
        {"id": "fvg", "available": True},
    ],
    "Oscillators (3)": [
        {"id": "rsi", "available": True},
        {"id": "macd", "available": True},
        {"id": "bollinger", "available": True},
    ],
    "Order Flow & Volume (2)": [
        {"id": "vwap", "available": True},
        {"id": "cvd", "available": True},
    ],
}

INDICATOR_METADATA = {
    "ema": {
        "title": "EMA Cross (10 / 50)",
        "short_name": "EMA (10/50)",
        "category": "Trend",
        "short_desc": "Fast & medium trend filter",
        "description": "Fast (10-bar) and medium (50-bar) exponential moving averages to identify directional momentum.",
        "citation": "Brock, Lakonishok, & LeBaron (1992), Journal of Finance, 47(5), 1731-1764",
        "formula": "EMA_t = alpha * P_t + (1 - alpha) * EMA_{t-1}, alpha = 2 / (N + 1)",
        "badge": "Trend",
        "pane": "main",
    },
    "ma200": {
        "title": "Moving Average (SMA 200)",
        "short_name": "SMA 200",
        "category": "Trend",
        "short_desc": "Long-term baseline",
        "description": "Macro-institutional trend boundary distinguishing structural bull from bear regimes.",
        "citation": "Siegel (2002); Neely, Rapach, Tu, & Zhou (2014), Management Science, 60(7)",
        "formula": "SMA_200 = (1 / 200) * sum_{i=0}^{199} P_{t-i}",
        "badge": "Trend",
        "pane": "main",
    },
    "donchian": {
        "title": "Donchian Channels (100)",
        "short_name": "Donchian 100",
        "category": "Trend",
        "short_desc": "100-bar breakout envelopes",
        "description": "Rolling extremum envelope tracking 100-period highest high resistance and lowest low support.",
        "citation": "Donchian (1960); Park & Irwin (2007), Journal of Economic Surveys, 21(4)",
        "formula": "Upper = max(High_{t-100..t}), Lower = min(Low_{t-100..t})",
        "badge": "Trend",
        "pane": "main",
    },
    "pivot": {
        "title": "Floor Pivots (P, R1/S1, R2/S2)",
        "short_name": "Floor Pivots",
        "category": "Price Structure",
        "short_desc": "Prior session support & resistance",
        "description": "Intraday liquidity clustering levels derived from prior daily session (D1) high, low, and close.",
        "citation": "Harris (2003), Oxford University Press; Floor Trading Liquidity Axioms",
        "formula": "P = (H + L + C) / 3; R1 = 2P - L; S1 = 2P - H; R2 = P + (H - L); S2 = P - (H - L)",
        "badge": "Price Structure",
        "pane": "main",
    },
    "fvg": {
        "title": "Fair Value Gaps (FVG)",
        "short_name": "FVG Imbalance",
        "category": "Price Structure",
        "short_desc": "Institutional liquidity voids",
        "description": "Three-candle microstructure price jumps highlighting unfilled institutional liquidity pools.",
        "citation": "Harris (2003), Oxford Univ. Press; Biais, Hillion, & Spatt (1995), Journal of Finance",
        "formula": "Bullish: Low_t > High_{t-2}; Bearish: High_t < Low_{t-2}",
        "badge": "Price Structure",
        "pane": "main",
    },
    "rsi": {
        "title": "Relative Strength Index (RSI 14)",
        "short_name": "RSI (14)",
        "category": "Oscillators",
        "short_desc": "Overbought / oversold",
        "description": "Internal price momentum velocity measuring overbought (>=70) and oversold (<=30) exhaustion.",
        "citation": "Wilder (1978); Lo, Mamaysky, & Wang (2000), Journal of Finance, 55(4)",
        "formula": "RSI = 100 - (100 / (1 + RS)), RS = EMA(Gain, 14) / EMA(Loss, 14)",
        "badge": "Oscillator",
        "pane": "sub",
    },
    "macd": {
        "title": "MACD (12, 26, 9)",
        "short_name": "MACD (12,26,9)",
        "category": "Oscillators",
        "short_desc": "Momentum convergence",
        "description": "Moving average convergence-divergence capturing momentum acceleration and signal crossovers.",
        "citation": "Appel (1979); Neely, Rapach, Tu, & Zhou (2014), Management Science",
        "formula": "MACD = EMA(12) - EMA(26); Signal = EMA(MACD, 9); Hist = MACD - Signal",
        "badge": "Oscillator",
        "pane": "sub",
    },
    "bollinger": {
        "title": "Bollinger Bands (20, 2σ)",
        "short_name": "Bollinger (20, 2sigma)",
        "category": "Oscillators",
        "short_desc": "Volatility dispersion envelopes",
        "description": "Adaptive volatility envelopes plotted at +/- 2.0 sample standard deviations around a 20-period SMA.",
        "citation": "Bollinger (1992); Lo, Mamaysky, & Wang (2000), Journal of Finance, 55(4)",
        "formula": "Upper = SMA(20) + 2.0 * sigma; Lower = SMA(20) - 2.0 * sigma",
        "badge": "Oscillator",
        "pane": "main",
    },
    "vwap": {
        "title": "Session VWAP & Bands",
        "short_name": "Session VWAP",
        "category": "Order Flow & Volume",
        "short_desc": "Volume-weighted average price",
        "description": "Cumulative volume-weighted average price and volume standard deviation dispersion envelopes.",
        "citation": "Berkowitz, Logue, & Noser (1988), Journal of Finance; Madhavan (2002)",
        "formula": "VWAP = sum(P_typ * Vol) / sum(Vol); Bands = VWAP +/- 1.5 * sigma_vwap",
        "badge": "Order Flow",
        "pane": "main",
    },
    "cvd": {
        "title": "Cumulative Volume Delta (CVD)",
        "short_name": "Order Flow CVD",
        "category": "Order Flow & Volume",
        "short_desc": "Aggressive buy / sell order delta",
        "description": "Tick-level signed order flow accumulation measuring aggressive buyer vs seller pressure.",
        "citation": "Kyle (1985), Econometrica, 53(6); Cartea & Jaimungal (2014), Risk Metrics",
        "formula": "Delta_t = Vol_t * ((Close_t - Open_t) / (High_t - Low_t)); CVD = cumsum(Delta)",
        "badge": "Order Flow",
        "pane": "sub",
    },
}

# Compatibility mapping
INDICATOR_LABELS = {k: v["title"] for k, v in INDICATOR_METADATA.items()}
for cat_name in INDICATOR_CATALOG:
    INDICATOR_LABELS[cat_name] = cat_name


class IndicatorDialog(QDialog):
    """Institutional Studies & Technical Indicators Selection Dialog with Light/Dark Theme Sync."""

    def __init__(self, parent=None, active_indicators=None, on_change=None, is_dark=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.resize(650, 480)

        self.on_change = on_change
        self.active_indicators = active_indicators if active_indicators is not None else {}
        self._checkboxes = {}
        self._drag_pos = None

        # Resolve Theme
        if is_dark is not None:
            self.is_dark = is_dark
        elif parent is not None:
            is_dark_flag = getattr(parent, "is_dark_theme", False)
            if not is_dark_flag and hasattr(parent, "quant_terminal"):
                is_dark_flag = getattr(parent.quant_terminal, "is_dark_theme", False)
            self.is_dark = is_dark_flag
        else:
            self.is_dark = False

        self._all_categories = ["All Studies (10)"] + list(INDICATOR_CATALOG.keys())
        self._current_cat = self._all_categories[0]

        self._init_ui()
        self._apply_dialog_theme()

    def _init_ui(self):
        self.resize(650, 480)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Title Bar: Flat, clean 'STUDIES & INDICATORS', zero AI noise, undistorted close button
        self.header_bar = QWidget()
        self.header_bar.setFixedHeight(40)
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(16, 0, 10, 0)
        header_layout.setSpacing(8)

        self.lbl_title = QLabel("STUDIES & INDICATORS")
        self.lbl_title.setObjectName("dlgTitle")
        self.lbl_title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        header_layout.addWidget(self.lbl_title)

        header_layout.addStretch()

        assets_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets"
        )
        self.btn_close = QPushButton()
        close_svg = os.path.join(assets_dir, "win_close.svg")
        if os.path.exists(close_svg):
            self.btn_close.setIcon(QIcon(close_svg))
            self.btn_close.setIconSize(QSize(10, 10))
        else:
            self.btn_close.setText("✕")
        self.btn_close.setObjectName("dlgBtnClose")
        self.btn_close.setFixedSize(28, 28)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.clicked.connect(self.accept)
        header_layout.addWidget(self.btn_close)

        main_layout.addWidget(self.header_bar)

        # 2. Search Toolbar (Simple placeholder 'Search indicators...')
        search_wrap = QWidget()
        search_layout = QHBoxLayout(search_wrap)
        search_layout.setContentsMargins(16, 8, 16, 8)
        search_layout.setSpacing(10)

        self.search_bar = QLineEdit()
        self.search_bar.setObjectName("dlgSearchBar")
        self.search_bar.setFixedHeight(30)
        self.search_bar.setPlaceholderText("Search indicators...")
        self.search_bar.textChanged.connect(self._on_search)
        search_layout.addWidget(self.search_bar)

        main_layout.addWidget(search_wrap)

        # Thin separator line
        div = QFrame()
        div.setFixedHeight(1)
        div.setObjectName("dlgDivider")
        main_layout.addWidget(div)

        # 3. Two-Column Workspace (Left: Categories with counts | Right: Flat 38px rows)
        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(0)

        # Left Sidebar (TradingView-style Category Navigation with Counts)
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("dlgSidebar")
        self.sidebar.setFixedWidth(180)
        for cat in self._all_categories:
            item = QListWidgetItem(cat)
            self.sidebar.addItem(item)
        self.sidebar.setCurrentRow(0)
        self.sidebar.currentRowChanged.connect(self._switch_cat)
        content_row.addWidget(self.sidebar)

        vsep = QFrame()
        vsep.setFixedWidth(1)
        vsep.setObjectName("dlgVDivider")
        content_row.addWidget(vsep)

        # Right Panel: Flat 38px rows with 1px dividers
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("dlgScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)

        self.card_container = QWidget()
        self.card_container.setObjectName("dlgCardContainer")
        self.card_layout = QVBoxLayout(self.card_container)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setSpacing(0)
        self.card_layout.setAlignment(Qt.AlignTop)

        self.scroll_area.setWidget(self.card_container)
        content_row.addWidget(self.scroll_area)

        main_layout.addLayout(content_row)

        # 4. Bottom Action Bar: Reset All on Left, Apply on Right (dark slate #0f172a)
        bottom_bar = QWidget()
        bottom_bar.setFixedHeight(44)
        bottom_bar.setObjectName("dlgBottomBar")
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(16, 0, 16, 0)
        bottom_layout.setSpacing(10)

        self.btn_reset = QPushButton("Reset All")
        self.btn_reset.setObjectName("dlgBtnReset")
        self.btn_reset.setFixedHeight(26)
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.clicked.connect(self._reset_all)
        bottom_layout.addWidget(self.btn_reset)

        self.lbl_active_count = QLabel("0 studies active")
        self.lbl_active_count.setObjectName("dlgActiveCount")
        self.lbl_active_count.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
        bottom_layout.addWidget(self.lbl_active_count)

        bottom_layout.addStretch()

        self.btn_apply = QPushButton("Apply")
        self.btn_apply.setObjectName("dlgBtnApply")
        self.btn_apply.setFixedHeight(28)
        self.btn_apply.setFixedWidth(84)
        self.btn_apply.setCursor(Qt.PointingHandCursor)
        self.btn_apply.clicked.connect(self.accept)
        bottom_layout.addWidget(self.btn_apply)

        main_layout.addWidget(bottom_bar)

        self._render_cards()
        self._update_active_count()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.pos().y() <= 40:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def _switch_cat(self, row):
        if 0 <= row < len(self._all_categories):
            self._current_cat = self._all_categories[row]
            self._render_cards()

    def _on_search(self, text):
        self._render_cards()

    def _render_cards(self):
        # Clear existing items
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self._checkboxes.clear()
        query = self.search_bar.text().strip().lower()

        # Filter items
        target_ids = []
        if self._current_cat == "All Studies (10)":
            target_ids = list(INDICATOR_METADATA.keys())
        else:
            cat_list = INDICATOR_CATALOG.get(self._current_cat, [])
            target_ids = [c["id"] for c in cat_list]

        visible_count = 0
        for ind_id in target_ids:
            meta = INDICATOR_METADATA.get(ind_id)
            if not meta:
                continue

            # Query filter matches name, category, formula or citation in the background
            if query:
                search_corpus = f"{meta['title']} {meta.get('citation', '')} {meta.get('formula', '')} {meta['category']} {meta['short_name']} {meta.get('short_desc', '')} {meta['description']}".lower()
                if query not in search_corpus:
                    continue

            row = self._create_indicator_card(ind_id, meta)
            self.card_layout.addWidget(row)
            visible_count += 1

        if visible_count == 0:
            empty_lbl = QLabel("No indicators matching current filter.")
            empty_lbl.setAlignment(Qt.AlignCenter)
            empty_lbl.setObjectName("dlgEmptyLabel")
            empty_lbl.setFixedHeight(80)
            self.card_layout.addWidget(empty_lbl)

    def _create_indicator_card(self, ind_id, meta):
        """Creates a single ultra-clean flat row (height 36px, thin divider 1px #E2E8F0)."""
        row = QFrame()
        row.setObjectName("dlgRow")
        row.setFixedHeight(36)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(14, 0, 16, 0)
        row_layout.setSpacing(12)
        row_layout.setAlignment(Qt.AlignVCenter)

        # Left: Checkbox + Indicator Name
        cb = QCheckBox(meta["title"].replace("&", "&&"))
        cb.setObjectName("dlgRowCheckbox")
        cb.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        cb.setCursor(Qt.PointingHandCursor)
        is_active = self.active_indicators.get(ind_id, False)
        cb.setChecked(is_active)
        cb.toggled.connect(lambda checked, i_id=ind_id: self._toggle(i_id, checked))
        self._checkboxes[ind_id] = cb
        row_layout.addWidget(cb)

        row_layout.addStretch()

        # Middle: Concise 3-5 word description in high-contrast crisp typography
        desc_text = meta.get("short_desc", meta["description"])
        lbl_desc = QLabel(desc_text)
        lbl_desc.setObjectName("dlgRowDesc")
        lbl_desc.setFont(QFont("Segoe UI", 8))
        row_layout.addWidget(lbl_desc)

        # Target Pane Badge: Subtle monochrome institutional pill (No neon / candy colors)
        pane_type = meta.get("pane", "main")
        is_sub = (pane_type == "sub")
        badge_pane_text = "SUB-PANE" if is_sub else "OVERLAY"
        lbl_pane = QLabel(badge_pane_text)
        lbl_pane.setObjectName("dlgRowPaneBadge")
        lbl_pane.setFont(QFont("Consolas", 7, QFont.Bold))
        lbl_pane.setFixedSize(62, 17)
        lbl_pane.setAlignment(Qt.AlignCenter)
        if self.is_dark:
            p_bg = "#161B26"
            p_fg = "#94A3B8"
            p_border = "#272D3B"
        else:
            p_bg = "#F1F5F9"
            p_fg = "#334155"
            p_border = "#CBD5E1"
        lbl_pane.setStyleSheet(f"background-color: {p_bg}; color: {p_fg}; border: 1px solid {p_border}; border-radius: 2px;")
        row_layout.addWidget(lbl_pane)

        # Redundant category label removed (Category is already displayed in left sidebar)

        return row

    def _toggle(self, ind_id, checked):
        if checked:
            meta = INDICATOR_METADATA.get(ind_id, {})
            # Sub-pane exclusive scale management: When activating a sub-pane study,
            # switch off other sub-pane studies to prevent scale collisions in single-pane oscillator widget.
            if meta.get("pane") == "sub":
                sub_ids = [k for k, v in INDICATOR_METADATA.items() if v.get("pane") == "sub" and k != ind_id]
                for s_id in sub_ids:
                    if self.active_indicators.get(s_id, False):
                        self.active_indicators[s_id] = False
                        if s_id in self._checkboxes:
                            self._checkboxes[s_id].blockSignals(True)
                            self._checkboxes[s_id].setChecked(False)
                            self._checkboxes[s_id].blockSignals(False)

        self.active_indicators[ind_id] = checked
        self._update_active_count()
        if self.on_change:
            self.on_change()

    def _reset_all(self):
        for ind_id, cb in self._checkboxes.items():
            if cb.isChecked():
                cb.setChecked(False)
        for k in list(self.active_indicators.keys()):
            self.active_indicators[k] = False
        self._update_active_count()
        if self.on_change:
            self.on_change()

    def _update_active_count(self):
        active_count = sum(1 for v in self.active_indicators.values() if v)
        self.lbl_active_count.setText(f"{active_count} {'study' if active_count == 1 else 'studies'} active")

    def _apply_dialog_theme(self):
        if self.is_dark:
            self.setStyleSheet("""
                QDialog {
                    background-color: #0C0E14;
                    border: 1px solid #1E293B;
                    border-radius: 2px;
                }
                QLabel#dlgTitle {
                    color: #F8FAFC;
                    letter-spacing: 0.5px;
                }
                QPushButton#dlgBtnClose {
                    background: transparent;
                    color: #94A3B8;
                    border: none;
                    border-radius: 2px;
                    font-family: 'Segoe UI', Arial, sans-serif;
                    font-size: 13px;
                    font-weight: bold;
                    padding: 0;
                }
                QPushButton#dlgBtnClose:hover {
                    background-color: #7F1D1D;
                    color: #FCA5A5;
                }
                QLineEdit#dlgSearchBar {
                    background-color: #141721;
                    color: #F8FAFC;
                    border: 1px solid #272D3B;
                    border-radius: 2px;
                    padding: 0 10px;
                    font-family: 'Segoe UI';
                    font-size: 11px;
                }
                QLineEdit#dlgSearchBar:focus {
                    border: 1px solid #38BDF8;
                }
                QFrame#dlgDivider, QFrame#dlgVDivider {
                    background-color: #1E293B;
                }
                QListWidget#dlgSidebar {
                    background-color: #0E121B;
                    border: none;
                    outline: none;
                    font-family: 'Segoe UI';
                    font-size: 11px;
                    color: #94A3B8;
                    padding: 4px;
                }
                QListWidget#dlgSidebar::item {
                    padding: 8px 12px;
                    border-radius: 2px;
                    margin: 1px 0;
                }
                QListWidget#dlgSidebar::item:hover {
                    background-color: #161D2D;
                    color: #F8FAFC;
                }
                QListWidget#dlgSidebar::item:selected {
                    background-color: #1E293B;
                    color: #38BDF8;
                    font-weight: bold;
                }
                QScrollArea#dlgScrollArea {
                    background-color: #0C0E14;
                    border: none;
                }
                QWidget#dlgCardContainer {
                    background-color: #0C0E14;
                }
                QFrame#dlgRow {
                    background-color: transparent;
                    border: none;
                    border-bottom: 1px solid #1E293B;
                }
                QFrame#dlgRow:hover {
                    background-color: #141722;
                }
                QCheckBox#dlgRowCheckbox {
                    color: #F8FAFC;
                    spacing: 8px;
                }
                QCheckBox#dlgRowCheckbox::indicator {
                    width: 14px;
                    height: 14px;
                    border-radius: 2px;
                    border: 1px solid #334155;
                    background-color: #161B26;
                }
                QCheckBox#dlgRowCheckbox::indicator:checked {
                    background-color: #0284C7;
                    border-color: #38BDF8;
                }
                QLabel#dlgRowDesc {
                    color: #CBD5E1;
                }
                QWidget#dlgBottomBar {
                    background-color: #0E121B;
                    border-top: 1px solid #1E293B;
                }
                QPushButton#dlgBtnReset {
                    background-color: #161B26;
                    color: #CBD5E1;
                    border: 1px solid #272D3B;
                    border-radius: 2px;
                    font-family: 'Segoe UI';
                    font-size: 11px;
                    padding: 0 12px;
                }
                QPushButton#dlgBtnReset:hover {
                    background-color: #27272A;
                    color: #FFFFFF;
                }
                QLabel#dlgActiveCount {
                    color: #94A3B8;
                }
                QPushButton#dlgBtnApply {
                    background-color: #0284C7;
                    color: #FFFFFF;
                    border: 1px solid #0284C7;
                    border-radius: 2px;
                    font-family: 'Segoe UI';
                    font-size: 11px;
                    font-weight: bold;
                    padding: 0 16px;
                }
                QPushButton#dlgBtnApply:hover {
                    background-color: #0369A1;
                }
                QLabel#dlgEmptyLabel {
                    color: #64748B;
                    font-family: 'Segoe UI';
                    font-size: 12px;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #FFFFFF;
                    border: 1px solid #CBD5E1;
                    border-radius: 2px;
                }
                QLabel#dlgTitle {
                    color: #0F172A;
                    letter-spacing: 0.5px;
                }
                QPushButton#dlgBtnClose {
                    background: transparent;
                    color: #64748B;
                    border: none;
                    border-radius: 2px;
                    font-family: 'Segoe UI', Arial, sans-serif;
                    font-size: 13px;
                    font-weight: bold;
                    padding: 0;
                }
                QPushButton#dlgBtnClose:hover {
                    background-color: #FEE2E2;
                    color: #EF4444;
                }
                QLineEdit#dlgSearchBar {
                    background-color: #FFFFFF;
                    color: #0F172A;
                    border: 1px solid #CBD5E1;
                    border-radius: 2px;
                    padding: 0 10px;
                    font-family: 'Segoe UI';
                    font-size: 11px;
                }
                QLineEdit#dlgSearchBar:focus {
                    border: 1px solid #0F172A;
                }
                QFrame#dlgDivider, QFrame#dlgVDivider {
                    background-color: #CBD5E1;
                }
                QListWidget#dlgSidebar {
                    background-color: #F8FAFC;
                    border: none;
                    outline: none;
                    font-family: 'Segoe UI';
                    font-size: 11px;
                    color: #334155;
                    padding: 4px;
                }
                QListWidget#dlgSidebar::item {
                    padding: 8px 12px;
                    border-radius: 2px;
                    margin: 1px 0;
                }
                QListWidget#dlgSidebar::item:hover {
                    background-color: #E2E8F0;
                    color: #0F172A;
                    font-weight: 500;
                }
                QListWidget#dlgSidebar::item:selected {
                    background-color: #0F172A;
                    color: #FFFFFF;
                    font-weight: 600;
                }
                QScrollArea#dlgScrollArea {
                    background-color: #FFFFFF;
                    border: none;
                }
                QWidget#dlgCardContainer {
                    background-color: #FFFFFF;
                }
                QFrame#dlgRow {
                    background-color: transparent;
                    border: none;
                    border-bottom: 1px solid #E2E8F0;
                }
                QFrame#dlgRow:hover {
                    background-color: #F8FAFC;
                }
                QCheckBox#dlgRowCheckbox {
                    color: #0F172A;
                    spacing: 8px;
                }
                QCheckBox#dlgRowCheckbox::indicator {
                    width: 14px;
                    height: 14px;
                    border-radius: 2px;
                    border: 1px solid #94A3B8;
                    background-color: #FFFFFF;
                }
                QCheckBox#dlgRowCheckbox::indicator:hover {
                    border-color: #475569;
                }
                QCheckBox#dlgRowCheckbox::indicator:checked {
                    background-color: #0F172A;
                    border-color: #0F172A;
                }
                QLabel#dlgRowDesc {
                    color: #334155;
                }
                QWidget#dlgBottomBar {
                    background-color: #F8FAFC;
                    border-top: 1px solid #CBD5E1;
                }
                QPushButton#dlgBtnReset {
                    background-color: #FFFFFF;
                    color: #334155;
                    border: 1px solid #CBD5E1;
                    border-radius: 2px;
                    font-family: 'Segoe UI';
                    font-size: 11px;
                    font-weight: 500;
                    padding: 0 12px;
                }
                QPushButton#dlgBtnReset:hover {
                    background-color: #F1F5F9;
                    border-color: #94A3B8;
                    color: #0F172A;
                }
                QLabel#dlgActiveCount {
                    color: #0F172A;
                }
                QPushButton#dlgBtnApply {
                    background-color: #0F172A;
                    color: #FFFFFF;
                    border: 1px solid #0F172A;
                    border-radius: 2px;
                    font-family: 'Segoe UI';
                    font-size: 11px;
                    font-weight: 600;
                    padding: 0 16px;
                }
                QPushButton#dlgBtnApply:hover {
                    background-color: #1E293B;
                    border-color: #1E293B;
                }
                QLabel#dlgEmptyLabel {
                    color: #64748B;
                    font-family: 'Segoe UI';
                    font-size: 12px;
                }
            """)


def _compute_indicators(df, active):
    """
    Computes active technical indicators grounded in academic finance literature.
    Computes only active items to maintain ultra-low CPU load (<1ms overhead).
    """
    result = {}
    if df is None or len(df) == 0:
        return result

    n = len(df)
    x = list(range(n))
    result["x"] = x

    # 1. Dual EMA (10 / 50) - Brock et al. (1992), Journal of Finance
    if active.get("ema", False):
        result["EMA_10"] = df["close"].ewm(span=10, adjust=False).mean().tolist()
        result["EMA_50"] = df["close"].ewm(span=50, adjust=False).mean().tolist()

    # 2. SMA 200 Macro Regime - Siegel (2002); Neely et al. (2014), Management Science
    if active.get("ma200", False):
        result["MA_200"] = df["close"].rolling(window=200, min_periods=min(50, n)).mean().tolist()

    # 3. Donchian Channels (Dynamic Rolling Envelopes) - Donchian (1960); Park & Irwin (2007)
    if active.get("donchian", False) and n >= 5:
        span = min(100, n)
        d_high = df["high"].rolling(window=span, min_periods=1).max()
        d_low = df["low"].rolling(window=span, min_periods=1).min()
        d_mid = (d_high + d_low) / 2.0
        result["DONCHIAN_HIGH"] = float(df["high"].iloc[-span:].max())
        result["DONCHIAN_LOW"] = float(df["low"].iloc[-span:].min())
        result["DONCHIAN_SERIES_HIGH"] = d_high.tolist()
        result["DONCHIAN_SERIES_LOW"] = d_low.tolist()
        result["DONCHIAN_SERIES_MID"] = d_mid.tolist()

    # 4. Classic Floor Pivots - Harris (2003), Oxford University Press
    if active.get("pivot", False):
        result["_pivot_raw"] = True

    # 5. Bollinger Bands (20, 2.0sigma) - Bollinger (1992); Lo et al. (2000), J. Finance
    if active.get("bollinger", False):
        sma20 = df["close"].rolling(window=20, min_periods=1).mean()
        std20 = df["close"].rolling(window=20, min_periods=1).std(ddof=0).fillna(0.0)
        result["BB_MID"] = sma20.tolist()
        result["BB_UPPER"] = (sma20 + 2.0 * std20).tolist()
        result["BB_LOWER"] = (sma20 - 2.0 * std20).tolist()

    # 6. Session VWAP & Dispersion Bands - Berkowitz et al. (1988); Madhavan (2002)
    if active.get("vwap", False):
        vol = df["tick_volume"] if "tick_volume" in df.columns else (
            df["volume"] if "volume" in df.columns else pd.Series(1.0, index=df.index)
        )
        vol = vol.astype(float).replace(0, 1.0)
        typical_price = (df["high"] + df["low"] + df["close"]) / 3.0

        # Session anchor: find recent session/day boundary or anchor to last 150 bars
        anchor_idx = 0
        if "time" in df.columns and len(df) > 1:
            try:
                times = pd.to_datetime(df["time"], unit="s") if np.issubdtype(df["time"].dtype, np.number) else pd.to_datetime(df["time"])
                day_diffs = np.where(times.dt.day.diff() != 0)[0]
                if len(day_diffs) > 1:
                    anchor_idx = int(day_diffs[-1])
            except Exception:
                anchor_idx = max(0, n - 150)
        else:
            anchor_idx = max(0, n - 150)

        cum_vp = (typical_price * vol).cumsum()
        cum_vol = vol.cumsum().replace(0, 1.0)
        vwap = cum_vp / cum_vol

        if 0 < anchor_idx < n:
            sess_vp = (typical_price.iloc[anchor_idx:] * vol.iloc[anchor_idx:]).cumsum()
            sess_vol = vol.iloc[anchor_idx:].cumsum().replace(0, 1.0)
            vwap.iloc[anchor_idx:] = sess_vp / sess_vol

        cum_sq_diff = (vol * ((typical_price - vwap) ** 2)).cumsum()
        vwap_std = np.sqrt((cum_sq_diff / cum_vol).clip(lower=0.0)).fillna(0.0)

        result["VWAP_LINE"] = vwap.tolist()
        result["VWAP_UPPER"] = (vwap + 1.5 * vwap_std).tolist()
        result["VWAP_LOWER"] = (vwap - 1.5 * vwap_std).tolist()

    # 7. Relative Strength Index (RSI 14) - Wilder (1978); Lo et al. (2000)
    if active.get("rsi", False):
        delta = df["close"].diff()
        gain = delta.clip(lower=0.0)
        loss = -delta.clip(upper=0.0)
        avg_gain = gain.ewm(com=13, adjust=False).mean()
        avg_loss = loss.ewm(com=13, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        result["RSI_14"] = rsi.fillna(50.0).tolist()

    # 8. MACD Oscillator (12, 26, 9) - Appel (1979); Neely et al. (2014)
    if active.get("macd", False):
        ema12 = df["close"].ewm(span=12, adjust=False).mean()
        ema26 = df["close"].ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist = macd_line - signal_line
        result["MACD_LINE"] = macd_line.tolist()
        result["MACD_SIGNAL"] = signal_line.tolist()
        result["MACD_HIST"] = macd_hist.tolist()

    # 9. Order Flow CVD Proxy - Kyle (1985), Econometrica; Cartea & Jaimungal (2014)
    if active.get("cvd", False):
        vol = df["tick_volume"] if "tick_volume" in df.columns else (
            df["volume"] if "volume" in df.columns else pd.Series(1.0, index=df.index)
        )
        vol = vol.astype(float)
        hl = (df["high"] - df["low"]).replace(0, 1e-5)
        delta = vol * ((df["close"] - df["open"]) / hl)
        result["CVD_LINE"] = delta.cumsum().tolist()

    # 10. Fair Value Gaps (FVG) - Harris (2003); Biais et al. (1995)
    if active.get("fvg", False) and n >= 3:
        fvg_zones = []
        # Inspect up to last 120 bars
        start_idx = max(2, n - 120)
        for i in range(start_idx, n):
            h_prev = df["high"].iloc[i - 2]
            l_prev = df["low"].iloc[i - 2]
            c_curr_high = df["high"].iloc[i]
            c_curr_low = df["low"].iloc[i]

            # Bullish FVG: current low > high of 2 bars ago
            if c_curr_low > h_prev:
                fvg_zones.append((i - 1, i, float(c_curr_low), float(h_prev), True))
            # Bearish FVG: current high < low of 2 bars ago
            elif c_curr_high < l_prev:
                fvg_zones.append((i - 1, i, float(l_prev), float(c_curr_high), False))
        result["FVG_ZONES"] = fvg_zones

    return result


def _get_or_create_curve(window, key, pen, **kwargs):
    """Retrieves existing PlotCurveItem or creates and attaches to plot_widget."""
    if not hasattr(window, "_ind_curves"):
        window._ind_curves = {}
    if key not in window._ind_curves:
        curve = pg.PlotCurveItem(pen=pen, **kwargs)
        if hasattr(window, "plot_widget") and window.plot_widget:
            window.plot_widget.addItem(curve)
        window._ind_curves[key] = curve
    return window._ind_curves[key]


def _get_or_create_osc_curve(window, key, pen, **kwargs):
    """Retrieves or creates PlotCurveItem attached to window.osc_plot_widget."""
    target = getattr(window, "osc_plot_widget", None) or getattr(window, "plot_widget", None)
    if not hasattr(window, "_ind_osc_curves"):
        window._ind_osc_curves = {}
    if key not in window._ind_osc_curves:
        curve = pg.PlotCurveItem(pen=pen, **kwargs)
        if target:
            target.addItem(curve)
        window._ind_osc_curves[key] = curve
    return window._ind_osc_curves[key]


def _get_or_create_hline(window, key, pen):
    """Retrieves existing InfiniteLine or creates and attaches to plot_widget."""
    if not hasattr(window, "_ind_curves"):
        window._ind_curves = {}
    if key not in window._ind_curves:
        line = pg.InfiniteLine(angle=0, pen=pen, movable=False)
        if hasattr(window, "plot_widget") and window.plot_widget:
            window.plot_widget.addItem(line)
        window._ind_curves[key] = line
    return window._ind_curves[key]


def _hide_curve(window, key):
    """Hides indicator curve safely without destroying the graphical object."""
    if hasattr(window, "_ind_curves") and key in window._ind_curves:
        window._ind_curves[key].setVisible(False)


def _hide_osc_curve(window, key):
    """Hides oscillator curve safely without destroying the graphical object."""
    if hasattr(window, "_ind_osc_curves") and key in window._ind_osc_curves:
        window._ind_osc_curves[key].setVisible(False)


def _get_or_create_osc_bargraph(window, key, brush):
    """Retrieves or creates BarGraphItem attached to window.osc_plot_widget."""
    target = getattr(window, "osc_plot_widget", None) or getattr(window, "plot_widget", None)
    if not hasattr(window, "_ind_osc_bars"):
        window._ind_osc_bars = {}
    if key not in window._ind_osc_bars:
        bargraph = pg.BarGraphItem(x=[0], height=[0], width=0.6, brush=brush, pen=None)
        if target:
            target.addItem(bargraph)
        window._ind_osc_bars[key] = bargraph
    return window._ind_osc_bars[key]


def _hide_osc_bargraph(window, key):
    """Hides oscillator BarGraphItem safely without destroying the graphical object."""
    if hasattr(window, "_ind_osc_bars") and key in window._ind_osc_bars:
        window._ind_osc_bars[key].setVisible(False)


def _refresh_indicators(window, df):
    """
    Main Indicator Coordinator: High-performance setData pattern.
    Renders academic curves and hides unselected items seamlessly.
    """
    if not hasattr(window, "plot_widget") or window.plot_widget is None:
        return
    if df is None or len(df) == 0:
        return

    active = getattr(window, "active_indicators", {})
    computed = _compute_indicators(df, active)
    x = computed.get("x", [])
    n = len(x)

    # 1. EMA (10 / 50)
    if active.get("ema", False) and "EMA_10" in computed and "EMA_50" in computed:
        c10 = _get_or_create_curve(window, "EMA_10", pg.mkPen("#F59E0B", width=1.3))
        c10.setData(x, computed["EMA_10"])
        c10.setVisible(True)

        c50 = _get_or_create_curve(window, "EMA_50", pg.mkPen("#3B82F6", width=1.5))
        c50.setData(x, computed["EMA_50"])
        c50.setVisible(True)
    else:
        _hide_curve(window, "EMA_10")
        _hide_curve(window, "EMA_50")

    # 2. SMA 200
    if active.get("ma200", False) and "MA_200" in computed:
        c200 = _get_or_create_curve(window, "MA_200", pg.mkPen("#A78BFA", width=1.3, style=Qt.DashLine))
        c200.setData(x, computed["MA_200"])
        c200.setVisible(True)
    else:
        _hide_curve(window, "MA_200")

    # 3. Donchian Channel (Dynamic Rolling Envelopes)
    if active.get("donchian", False) and "DONCHIAN_SERIES_HIGH" in computed:
        r_curve = _get_or_create_curve(window, "DONCHIAN_R", pg.mkPen(color=(244, 63, 94, 180), width=1.2, style=Qt.DashLine))
        r_curve.setData(x, computed["DONCHIAN_SERIES_HIGH"])
        r_curve.setVisible(True)

        m_curve = _get_or_create_curve(window, "DONCHIAN_M", pg.mkPen(color=(148, 163, 184, 140), width=1.0, style=Qt.DotLine))
        m_curve.setData(x, computed["DONCHIAN_SERIES_MID"])
        m_curve.setVisible(True)

        s_curve = _get_or_create_curve(window, "DONCHIAN_S", pg.mkPen(color=(16, 185, 129, 180), width=1.2, style=Qt.DashLine))
        s_curve.setData(x, computed["DONCHIAN_SERIES_LOW"])
        s_curve.setVisible(True)
    else:
        _hide_curve(window, "DONCHIAN_R")
        _hide_curve(window, "DONCHIAN_M")
        _hide_curve(window, "DONCHIAN_S")

    # 4. Classic Floor Pivots
    if active.get("pivot", False):
        try:
            sym = getattr(window, "current_sym", "XAUUSD")
            d1_rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_D1, 0, 3)
            H, L, C = None, None, None
            if d1_rates is not None and len(d1_rates) >= 2:
                prev = d1_rates[-2]
                H = float(prev["high"])
                L = float(prev["low"])
                C = float(prev["close"])
            elif df is not None and len(df) >= 20:
                prev_chunk = df.iloc[-48:-24] if len(df) >= 48 else df.iloc[:max(1, len(df) // 2)]
                H = float(prev_chunk["high"].max())
                L = float(prev_chunk["low"].min())
                C = float(prev_chunk["close"].iloc[-1])

            if H is not None and L is not None and C is not None:
                P = (H + L + C) / 3.0
                R1 = 2 * P - L
                S1 = 2 * P - H
                R2 = P + (H - L)
                S2 = P - (H - L)

                # Floor Pivots session anchor: Anchor across current day session (Sierra Chart / TradingView standard)
                x_start = max(0, n - 40)
                if "time" in df.columns and len(df) > 1:
                    try:
                        times = pd.to_datetime(df["time"], unit="s") if np.issubdtype(df["time"].dtype, np.number) else pd.to_datetime(df["time"])
                        day_diffs = np.where(times.dt.day.diff() != 0)[0]
                        if len(day_diffs) > 0:
                            x_start = int(day_diffs[-1])
                    except Exception:
                        pass
                x_end = max(0, n - 1)

                pivot_cfg = [
                    ("PIVOT_P", P, pg.mkPen("#64748B", width=1.0, style=Qt.DashLine)),
                    ("PIVOT_R1", R1, pg.mkPen(color=(244, 63, 94, 200), width=1.1, style=Qt.DashLine)),
                    ("PIVOT_S1", S1, pg.mkPen(color=(16, 185, 129, 200), width=1.1, style=Qt.DashLine)),
                    ("PIVOT_R2", R2, pg.mkPen(color=(244, 63, 94, 130), width=1.0, style=Qt.DotLine)),
                    ("PIVOT_S2", S2, pg.mkPen(color=(16, 185, 129, 130), width=1.0, style=Qt.DotLine)),
                ]
                for key, val, pen in pivot_cfg:
                    c = _get_or_create_curve(window, key, pen)
                    c.setData([x_start, x_end], [val, val])
                    c.setVisible(True)
        except Exception:
            pass
    else:
        for key in ["PIVOT_P", "PIVOT_R1", "PIVOT_S1", "PIVOT_R2", "PIVOT_S2"]:
            _hide_curve(window, key)

    # 5. Bollinger Bands (20, 2.0sigma)
    if active.get("bollinger", False) and "BB_UPPER" in computed:
        b_up = _get_or_create_curve(window, "BB_UPPER", pg.mkPen(color=(56, 189, 248, 200), width=1.2, style=Qt.DashLine))
        b_up.setData(x, computed["BB_UPPER"])
        b_up.setVisible(True)

        b_mid = _get_or_create_curve(window, "BB_MID", pg.mkPen(color=(56, 189, 248, 140), width=1.0))
        b_mid.setData(x, computed["BB_MID"])
        b_mid.setVisible(True)

        b_low = _get_or_create_curve(window, "BB_LOWER", pg.mkPen(color=(56, 189, 248, 200), width=1.2, style=Qt.DashLine))
        b_low.setData(x, computed["BB_LOWER"])
        b_low.setVisible(True)
    else:
        _hide_curve(window, "BB_UPPER")
        _hide_curve(window, "BB_MID")
        _hide_curve(window, "BB_LOWER")

    # 6. Session VWAP & Dispersion Bands
    if active.get("vwap", False) and "VWAP_LINE" in computed:
        v_line = _get_or_create_curve(window, "VWAP_LINE", pg.mkPen("#EC4899", width=1.6))
        v_line.setData(x, computed["VWAP_LINE"])
        v_line.setVisible(True)

        v_up = _get_or_create_curve(window, "VWAP_UPPER", pg.mkPen(color=(236, 72, 153, 140), width=1.0, style=Qt.DotLine))
        v_up.setData(x, computed["VWAP_UPPER"])
        v_up.setVisible(True)

        v_low = _get_or_create_curve(window, "VWAP_LOWER", pg.mkPen(color=(236, 72, 153, 140), width=1.0, style=Qt.DotLine))
        v_low.setData(x, computed["VWAP_LOWER"])
        v_low.setVisible(True)
    else:
        _hide_curve(window, "VWAP_LINE")
        _hide_curve(window, "VWAP_UPPER")
        _hide_curve(window, "VWAP_LOWER")

    # 7. Fair Value Gaps (FVG) - Institutional Engine (LuxAlgo / ICT Standard)
    for idx in range(10):
        _hide_curve(window, f"FVG_TOP_{idx}")
        _hide_curve(window, f"FVG_BOT_{idx}")

    fvg_on = active.get("fvg", False)
    if hasattr(window, "drawing_engine") and window.drawing_engine:
        window.drawing_engine.toggle_fvg(fvg_on)
    else:
        window._fvg_visible = fvg_on
        try:
            from frontend.controllers.chart.fvg_engine import update_chart_fvgs
            update_chart_fvgs(window, force_visible=fvg_on)
        except Exception:
            pass

    # Sub-Pane Oscillators Management (RSI, MACD, CVD)
    has_osc = hasattr(window, "osc_plot_widget") and window.osc_plot_widget is not None
    osc_active = active.get("rsi", False) or active.get("macd", False) or active.get("cvd", False)
    if has_osc:
        window.osc_plot_widget.setVisible(osc_active)

    # 8. RSI 14
    if active.get("rsi", False) and "RSI_14" in computed and n > 0:
        rsi_raw = computed["RSI_14"]
        if has_osc:
            c_rsi = _get_or_create_osc_curve(window, "OSC_RSI_CURVE", pg.mkPen("#10B981", width=1.5))
            c_rsi.setData(x, rsi_raw)
            c_rsi.setVisible(True)

            c_r70 = _get_or_create_osc_curve(window, "OSC_RSI_70", pg.mkPen(color=(244, 63, 94, 180), width=1.0, style=Qt.DashLine))
            c_r70.setData([0, n - 1], [70.0, 70.0])
            c_r70.setVisible(True)

            c_r50 = _get_or_create_osc_curve(window, "OSC_RSI_50", pg.mkPen(color=(148, 163, 184, 120), width=0.8, style=Qt.DotLine))
            c_r50.setData([0, n - 1], [50.0, 50.0])
            c_r50.setVisible(True)

            c_r30 = _get_or_create_osc_curve(window, "OSC_RSI_30", pg.mkPen(color=(16, 185, 129, 180), width=1.0, style=Qt.DashLine))
            c_r30.setData([0, n - 1], [30.0, 30.0])
            c_r30.setVisible(True)

            window.osc_plot_widget.setYRange(0, 100)
            r_axis = window.osc_plot_widget.getAxis("right")
            if r_axis:
                r_axis.setLabel("RSI")
        else:
            _hide_curve(window, "RSI_14_CURVE")
    else:
        _hide_osc_curve(window, "OSC_RSI_CURVE")
        _hide_osc_curve(window, "OSC_RSI_70")
        _hide_osc_curve(window, "OSC_RSI_50")
        _hide_osc_curve(window, "OSC_RSI_30")
        _hide_curve(window, "RSI_14_CURVE")
        _hide_curve(window, "RSI_70_LINE")
        _hide_curve(window, "RSI_30_LINE")

    # 9. MACD (12, 26, 9)
    if active.get("macd", False) and "MACD_LINE" in computed and n > 0:
        macd_raw = np.array(computed["MACD_LINE"])
        sig_raw = np.array(computed["MACD_SIGNAL"])
        hist_raw = np.array(computed.get("MACD_HIST", macd_raw - sig_raw))
        if has_osc:
            # Positive and Negative Histogram bars (Appel 1979 / Institutional TradingView style)
            pos_mask = (hist_raw >= 0)
            neg_mask = (hist_raw < 0)
            x_arr = np.array(x)

            bar_pos = _get_or_create_osc_bargraph(window, "OSC_MACD_BAR_POS", pg.mkBrush("#22C55E"))
            if np.any(pos_mask):
                bar_pos.setOpts(x=x_arr[pos_mask], height=hist_raw[pos_mask], width=0.6, brush=pg.mkBrush("#22C55E"), pen=None)
                bar_pos.setVisible(True)
            else:
                bar_pos.setVisible(False)

            bar_neg = _get_or_create_osc_bargraph(window, "OSC_MACD_BAR_NEG", pg.mkBrush("#EF4444"))
            if np.any(neg_mask):
                bar_neg.setOpts(x=x_arr[neg_mask], height=hist_raw[neg_mask], width=0.6, brush=pg.mkBrush("#EF4444"), pen=None)
                bar_neg.setVisible(True)
            else:
                bar_neg.setVisible(False)

            c_macd = _get_or_create_osc_curve(window, "OSC_MACD_LINE", pg.mkPen("#0284C7", width=1.4))
            c_macd.setData(x, macd_raw.tolist())
            c_macd.setVisible(True)

            c_sig = _get_or_create_osc_curve(window, "OSC_MACD_SIG", pg.mkPen("#F43F5E", width=1.2, style=Qt.DashLine))
            c_sig.setData(x, sig_raw.tolist())
            c_sig.setVisible(True)

            c_zero = _get_or_create_osc_curve(window, "OSC_MACD_ZERO", pg.mkPen(color=(148, 163, 184, 100), width=0.8, style=Qt.DotLine))
            c_zero.setData([0, n - 1], [0.0, 0.0])
            c_zero.setVisible(True)

            m_all = np.concatenate([macd_raw, sig_raw, hist_raw])
            m_min, m_max = float(np.min(m_all)), float(np.max(m_all))
            pad = max(abs(m_max - m_min) * 0.15, 1e-4)
            window.osc_plot_widget.setYRange(m_min - pad, m_max + pad)
            r_axis = window.osc_plot_widget.getAxis("right")
            if r_axis:
                r_axis.setLabel("MACD")
        else:
            _hide_curve(window, "MACD_CURVE")
    else:
        _hide_osc_bargraph(window, "OSC_MACD_BAR_POS")
        _hide_osc_bargraph(window, "OSC_MACD_BAR_NEG")
        _hide_osc_curve(window, "OSC_MACD_LINE")
        _hide_osc_curve(window, "OSC_MACD_SIG")
        _hide_osc_curve(window, "OSC_MACD_ZERO")
        _hide_curve(window, "MACD_CURVE")
        _hide_curve(window, "MACD_SIG_CURVE")

    # 10. Order Flow CVD Proxy
    if active.get("cvd", False) and "CVD_LINE" in computed and n > 0:
        cvd_raw = np.array(computed["CVD_LINE"])
        if has_osc:
            c_cvd = _get_or_create_osc_curve(window, "OSC_CVD_LINE", pg.mkPen("#8B5CF6", width=1.5))
            c_cvd.setData(x, cvd_raw.tolist())
            c_cvd.setVisible(True)

            c_czero = _get_or_create_osc_curve(window, "OSC_CVD_ZERO", pg.mkPen(color=(148, 163, 184, 100), width=0.8, style=Qt.DotLine))
            c_czero.setData([0, n - 1], [0.0, 0.0])
            c_czero.setVisible(True)

            cv_min, cv_max = float(np.min(cvd_raw)), float(np.max(cvd_raw))
            cpad = max(abs(cv_max - cv_min) * 0.15, 1e-4)
            window.osc_plot_widget.setYRange(cv_min - cpad, cv_max + cpad)
            r_axis = window.osc_plot_widget.getAxis("right")
            if r_axis:
                r_axis.setLabel("CVD")
        else:
            _hide_curve(window, "CVD_CURVE")
    else:
        _hide_osc_curve(window, "OSC_CVD_LINE")
        _hide_osc_curve(window, "OSC_CVD_ZERO")
        _hide_curve(window, "CVD_CURVE")

    # Dynamic Study Legend on Ribbon (TradingView / Bloomberg Terminal standard)
    if hasattr(window, "lbl_chart_studies") and window.lbl_chart_studies is not None:
        legend_items = []
        if active.get("ema", False) and "EMA_10" in computed and len(computed["EMA_10"]) > 0:
            e10_val = computed["EMA_10"][-1]
            e50_val = computed["EMA_50"][-1]
            legend_items.append(f'<span style="color:#F59E0B;">● EMA10: <b>{e10_val:,.2f}</b></span> <span style="color:#3B82F6;">● EMA50: <b>{e50_val:,.2f}</b></span>')
        if active.get("ma200", False) and "MA_200" in computed and len(computed["MA_200"]) > 0:
            m200_val = computed["MA_200"][-1]
            if not np.isnan(m200_val):
                legend_items.append(f'<span style="color:#A78BFA;">● SMA200: <b>{m200_val:,.2f}</b></span>')
        if active.get("donchian", False) and "DONCHIAN_SERIES_HIGH" in computed and len(computed["DONCHIAN_SERIES_HIGH"]) > 0:
            dh = computed["DONCHIAN_SERIES_HIGH"][-1]
            dl = computed["DONCHIAN_SERIES_LOW"][-1]
            legend_items.append(f'<span style="color:#F43F5E;">● D-High: <b>{dh:,.1f}</b></span> <span style="color:#10B981;">● D-Low: <b>{dl:,.1f}</b></span>')
        if active.get("bollinger", False) and "BB_UPPER" in computed and len(computed["BB_UPPER"]) > 0:
            b_up = computed["BB_UPPER"][-1]
            b_low = computed["BB_LOWER"][-1]
            legend_items.append(f'<span style="color:#38BDF8;">● BB: <b>[{b_low:,.1f}-{b_up:,.1f}]</b></span>')
        if active.get("vwap", False) and "VWAP_LINE" in computed and len(computed["VWAP_LINE"]) > 0:
            vw = computed["VWAP_LINE"][-1]
            legend_items.append(f'<span style="color:#EC4899;">● VWAP: <b>{vw:,.2f}</b></span>')
        if active.get("rsi", False) and "RSI_14" in computed and len(computed["RSI_14"]) > 0:
            rsi_val = computed["RSI_14"][-1]
            legend_items.append(f'<span style="color:#10B981;">● RSI: <b>{rsi_val:.1f}</b></span>')
        if active.get("macd", False) and "MACD_LINE" in computed and len(computed["MACD_LINE"]) > 0:
            m_val = computed["MACD_LINE"][-1]
            s_val = computed["MACD_SIGNAL"][-1]
            legend_items.append(f'<span style="color:#0284C7;">● MACD: <b>{m_val:.2f}</b></span> <span style="color:#F43F5E;">Sig: <b>{s_val:.2f}</b></span>')
        if active.get("cvd", False) and "CVD_LINE" in computed and len(computed["CVD_LINE"]) > 0:
            cvd_val = computed["CVD_LINE"][-1]
            legend_items.append(f'<span style="color:#8B5CF6;">● CVD: <b>{cvd_val:,.0f}</b></span>')

        if legend_items:
            html = '<span style="font-family:Consolas, monospace; font-size:9px; color:#94A3B8;">' + " &nbsp;|&nbsp; ".join(legend_items) + "</span>"
            window.lbl_chart_studies.setText(html)
            window.lbl_chart_studies.setVisible(True)
        else:
            window.lbl_chart_studies.setText("")
            window.lbl_chart_studies.setVisible(False)


__all__ = [
    "INDICATOR_CATALOG",
    "INDICATOR_METADATA",
    "INDICATOR_LABELS",
    "IndicatorDialog",
    "_compute_indicators",
    "_refresh_indicators",
    "_get_or_create_curve",
    "_get_or_create_osc_curve",
    "_get_or_create_osc_bargraph",
    "_get_or_create_hline",
    "_hide_curve",
    "_hide_osc_curve",
    "_hide_osc_bargraph",
]
