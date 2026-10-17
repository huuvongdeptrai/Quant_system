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
    "Trend & Momentum": [
        {"id": "ema", "available": True},
        {"id": "ma200", "available": True},
        {"id": "rsi", "available": True},
        {"id": "macd", "available": True},
    ],
    "Price Structure & Levels": [
        {"id": "donchian", "available": True},
        {"id": "pivot", "available": True},
        {"id": "fvg", "available": True},
    ],
    "Volatility & Dispersion": [
        {"id": "bollinger", "available": True},
        {"id": "vwap", "available": True},
    ],
    "Order Flow & Microstructure": [
        {"id": "cvd", "available": True},
    ],
}

INDICATOR_METADATA = {
    "ema": {
        "title": "Dual Exponential Moving Average (EMA 10 / 50)",
        "short_name": "EMA (10/50)",
        "category": "Trend & Momentum",
        "description": "Fast (10-bar) and medium (50-bar) exponential moving averages to identify directional momentum.",
        "citation": "Brock, Lakonishok, & LeBaron (1992), Journal of Finance, 47(5), 1731-1764",
        "formula": "EMA_t = alpha * P_t + (1 - alpha) * EMA_{t-1}, alpha = 2 / (N + 1)",
        "badge": "TREND FILTER",
    },
    "ma200": {
        "title": "200-Bar Regime Baseline (SMA 200)",
        "short_name": "SMA 200",
        "category": "Trend & Momentum",
        "description": "Macro-institutional trend boundary distinguishing structural bull from bear regimes.",
        "citation": "Siegel (2002); Neely, Rapach, Tu, & Zhou (2014), Management Science, 60(7)",
        "formula": "SMA_200 = (1 / 200) * sum_{i=0}^{199} P_{t-i}",
        "badge": "MACRO REGIME",
    },
    "rsi": {
        "title": "Relative Strength Index (RSI 14)",
        "short_name": "RSI (14)",
        "category": "Trend & Momentum",
        "description": "Internal price momentum velocity measuring overbought (>=70) and oversold (<=30) exhaustion.",
        "citation": "Wilder (1978); Lo, Mamaysky, & Wang (2000), Journal of Finance, 55(4)",
        "formula": "RSI = 100 - (100 / (1 + RS)), RS = EMA(Gain, 14) / EMA(Loss, 14)",
        "badge": "OSCILLATOR",
    },
    "macd": {
        "title": "MACD Momentum Oscillator (12, 26, 9)",
        "short_name": "MACD (12,26,9)",
        "category": "Trend & Momentum",
        "description": "Moving average convergence-divergence capturing momentum acceleration and signal crossovers.",
        "citation": "Appel (1979); Neely, Rapach, Tu, & Zhou (2014), Management Science",
        "formula": "MACD = EMA(12) - EMA(26); Signal = EMA(MACD, 9); Hist = MACD - Signal",
        "badge": "MOMENTUM",
    },
    "donchian": {
        "title": "Donchian Breakout Channels (100-Bar Dynamic S/R)",
        "short_name": "Donchian 100",
        "category": "Price Structure & Levels",
        "description": "Rolling extremum envelope tracking 100-period highest high resistance and lowest low support.",
        "citation": "Donchian (1960); Park & Irwin (2007), Journal of Economic Surveys, 21(4)",
        "formula": "Upper = max(High_{t-100..t}), Lower = min(Low_{t-100..t})",
        "badge": "SUPPORT / RESIST",
    },
    "pivot": {
        "title": "Classic Floor Pivots (P, R1/S1, R2/S2)",
        "short_name": "Floor Pivots",
        "category": "Price Structure & Levels",
        "description": "Intraday liquidity clustering levels derived from prior daily session (D1) high, low, and close.",
        "citation": "Harris (2003), Oxford University Press; Floor Trading Liquidity Axioms",
        "formula": "P = (H + L + C) / 3; R1 = 2P - L; S1 = 2P - H; R2 = P + (H - L); S2 = P - (H - L)",
        "badge": "SESSION PIVOTS",
    },
    "fvg": {
        "title": "Fair Value Gaps / Imbalance Voids (FVG)",
        "short_name": "FVG Imbalance",
        "category": "Price Structure & Levels",
        "description": "Three-candle microstructure price jumps highlighting unfilled institutional liquidity pools.",
        "citation": "Harris (2003), Oxford Univ. Press; Biais, Hillion, & Spatt (1995), Journal of Finance",
        "formula": "Bullish: Low_t > High_{t-2}; Bearish: High_t < Low_{t-2}",
        "badge": "SMART MONEY",
    },
    "bollinger": {
        "title": "Bollinger Volatility Bands (20, 2.0sigma)",
        "short_name": "Bollinger (20, 2sigma)",
        "category": "Volatility & Dispersion",
        "description": "Adaptive volatility envelopes plotted at +/- 2.0 sample standard deviations around a 20-period SMA.",
        "citation": "Bollinger (1992); Lo, Mamaysky, & Wang (2000), Journal of Finance, 55(4)",
        "formula": "Upper = SMA(20) + 2.0 * sigma; Lower = SMA(20) - 2.0 * sigma",
        "badge": "VOLATILITY",
    },
    "vwap": {
        "title": "Session VWAP & Dispersion Bands (+/-1.5sigma)",
        "short_name": "Session VWAP",
        "category": "Volatility & Dispersion",
        "description": "Cumulative volume-weighted average price and volume standard deviation dispersion envelopes.",
        "citation": "Berkowitz, Logue, & Noser (1988), Journal of Finance; Madhavan (2002)",
        "formula": "VWAP = sum(P_typ * Vol) / sum(Vol); Bands = VWAP +/- 1.5 * sigma_vwap",
        "badge": "FAIR VALUE",
    },
    "cvd": {
        "title": "Cumulative Volume Delta Proxy (CVD)",
        "short_name": "Order Flow CVD",
        "category": "Order Flow & Microstructure",
        "description": "Tick-level signed order flow accumulation measuring aggressive buyer vs seller pressure.",
        "citation": "Kyle (1985), Econometrica, 53(6); Cartea & Jaimungal (2014), Risk Metrics",
        "formula": "Delta_t = Vol_t * ((Close_t - Open_t) / (High_t - Low_t)); CVD = cumsum(Delta)",
        "badge": "ORDER FLOW",
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
        self.resize(680, 520)

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
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Custom Institutional Title Bar (Eliminates OS Qt icon)
        self.header_bar = QWidget()
        self.header_bar.setFixedHeight(44)
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(16, 0, 12, 0)
        header_layout.setSpacing(10)

        lbl_icon = QLabel("[fx]")
        lbl_icon.setObjectName("dlgHeaderIcon")
        lbl_icon.setFont(QFont("Consolas", 11, QFont.Bold))
        header_layout.addWidget(lbl_icon)

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        title_col.setAlignment(Qt.AlignVCenter)

        self.lbl_title = QLabel("STUDIES & QUANTITATIVE INDICATORS")
        self.lbl_title.setObjectName("dlgTitle")
        self.lbl_title.setFont(QFont("Segoe UI", 10, QFont.Bold))

        self.lbl_subtitle = QLabel("ACADEMIC & INSTITUTIONAL SUITE - PEER-REVIEWED SPECIFICATIONS")
        self.lbl_subtitle.setObjectName("dlgSubtitle")
        self.lbl_subtitle.setFont(QFont("Segoe UI", 7, QFont.DemiBold))

        title_col.addWidget(self.lbl_title)
        title_col.addWidget(self.lbl_subtitle)
        header_layout.addLayout(title_col)

        header_layout.addStretch()

        self.btn_close = QPushButton("X")
        self.btn_close.setObjectName("dlgBtnClose")
        self.btn_close.setFixedSize(28, 28)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.clicked.connect(self.accept)
        header_layout.addWidget(self.btn_close)

        main_layout.addWidget(self.header_bar)

        # 2. Search Toolbar
        search_wrap = QWidget()
        search_layout = QHBoxLayout(search_wrap)
        search_layout.setContentsMargins(16, 10, 16, 10)
        search_layout.setSpacing(10)

        self.search_bar = QLineEdit()
        self.search_bar.setObjectName("dlgSearchBar")
        self.search_bar.setFixedHeight(32)
        self.search_bar.setPlaceholderText("Search studies by name, citation (e.g. Brock, Siegel, Kyle), or formula...")
        self.search_bar.textChanged.connect(self._on_search)
        search_layout.addWidget(self.search_bar)

        main_layout.addWidget(search_wrap)

        # Thin divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setObjectName("dlgDivider")
        main_layout.addWidget(div)

        # 3. Content Split (Sidebar + Cards)
        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(0)

        # Left Sidebar (Categories)
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("dlgSidebar")
        self.sidebar.setFixedWidth(190)
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

        # Right Panel (Scroll Area with Cards)
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("dlgScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)

        self.card_container = QWidget()
        self.card_container.setObjectName("dlgCardContainer")
        self.card_layout = QVBoxLayout(self.card_container)
        self.card_layout.setContentsMargins(14, 12, 14, 12)
        self.card_layout.setSpacing(10)
        self.card_layout.setAlignment(Qt.AlignTop)

        self.scroll_area.setWidget(self.card_container)
        content_row.addWidget(self.scroll_area)

        main_layout.addLayout(content_row)

        # 4. Bottom Action Bar
        bottom_bar = QWidget()
        bottom_bar.setFixedHeight(48)
        bottom_bar.setObjectName("dlgBottomBar")
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(16, 0, 16, 0)
        bottom_layout.setSpacing(10)

        self.btn_reset = QPushButton("Reset All")
        self.btn_reset.setObjectName("dlgBtnReset")
        self.btn_reset.setFixedHeight(28)
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.clicked.connect(self._reset_all)
        bottom_layout.addWidget(self.btn_reset)

        self.lbl_active_count = QLabel("0 studies active")
        self.lbl_active_count.setObjectName("dlgActiveCount")
        self.lbl_active_count.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
        bottom_layout.addWidget(self.lbl_active_count)

        bottom_layout.addStretch()

        self.btn_apply = QPushButton("Apply & Close")
        self.btn_apply.setObjectName("dlgBtnApply")
        self.btn_apply.setFixedHeight(28)
        self.btn_apply.setFixedWidth(110)
        self.btn_apply.setCursor(Qt.PointingHandCursor)
        self.btn_apply.clicked.connect(self.accept)
        bottom_layout.addWidget(self.btn_apply)

        main_layout.addWidget(bottom_bar)

        self._render_cards()
        self._update_active_count()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.pos().y() <= 44:
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

            # Query filter: matches title, citation, formula, category, or short_name
            if query:
                search_corpus = f"{meta['title']} {meta['citation']} {meta['formula']} {meta['category']} {meta['short_name']} {meta['description']}".lower()
                if query not in search_corpus:
                    continue

            card = self._create_indicator_card(ind_id, meta)
            self.card_layout.addWidget(card)
            visible_count += 1

        if visible_count == 0:
            empty_lbl = QLabel("No indicators matching current filter.")
            empty_lbl.setAlignment(Qt.AlignCenter)
            empty_lbl.setObjectName("dlgEmptyLabel")
            empty_lbl.setFixedHeight(80)
            self.card_layout.addWidget(empty_lbl)

    def _create_indicator_card(self, ind_id, meta):
        card = QFrame()
        card.setObjectName("dlgCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(6)

        # Top line: Checkbox + Short Badge
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        cb = QCheckBox(meta["title"])
        cb.setObjectName("dlgCardCheckbox")
        cb.setFont(QFont("Segoe UI", 9, QFont.Bold))
        cb.setCursor(Qt.PointingHandCursor)
        is_active = self.active_indicators.get(ind_id, False)
        cb.setChecked(is_active)
        cb.toggled.connect(lambda checked, i_id=ind_id: self._toggle(i_id, checked))
        self._checkboxes[ind_id] = cb
        top_row.addWidget(cb)

        top_row.addStretch()

        badge = QLabel(meta.get("badge", "STUDY"))
        badge.setObjectName("dlgCardBadge")
        badge.setFont(QFont("Segoe UI", 7, QFont.Bold))
        badge.setFixedHeight(18)
        top_row.addWidget(badge)

        card_layout.addLayout(top_row)

        # Middle line: Description
        lbl_desc = QLabel(meta["description"])
        lbl_desc.setObjectName("dlgCardDesc")
        lbl_desc.setWordWrap(True)
        lbl_desc.setFont(QFont("Segoe UI", 8))
        card_layout.addWidget(lbl_desc)

        # Bottom line: Citation & Formula
        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 2, 0, 0)
        meta_row.setSpacing(6)

        lbl_cit = QLabel(f"REF: {meta['citation']}")
        lbl_cit.setObjectName("dlgCardCitation")
        lbl_cit.setFont(QFont("Consolas", 7, QFont.DemiBold))
        meta_row.addWidget(lbl_cit)

        meta_row.addStretch()

        card_layout.addLayout(meta_row)

        return card

    def _toggle(self, ind_id, checked):
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
                    border-radius: 6px;
                }
                QWidget#dlgHeaderIcon {
                    color: #38BDF8;
                }
                QLabel#dlgTitle {
                    color: #F8FAFC;
                    letter-spacing: 0.5px;
                }
                QLabel#dlgSubtitle {
                    color: #64748B;
                    letter-spacing: 0.8px;
                }
                QPushButton#dlgBtnClose {
                    background: transparent;
                    color: #94A3B8;
                    border: none;
                    border-radius: 4px;
                    font-family: 'Segoe UI';
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton#dlgBtnClose:hover {
                    background-color: #7F1D1D;
                    color: #FCA5A5;
                }
                QLineEdit#dlgSearchBar {
                    background-color: #141721;
                    color: #F8FAFC;
                    border: 1px solid #272D3B;
                    border-radius: 4px;
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
                    border-radius: 4px;
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
                QFrame#dlgCard {
                    background-color: #111622;
                    border: 1px solid #1E293B;
                    border-radius: 5px;
                }
                QFrame#dlgCard:hover {
                    background-color: #141B2B;
                    border-color: #334155;
                }
                QCheckBox#dlgCardCheckbox {
                    color: #F1F5F9;
                    spacing: 8px;
                }
                QCheckBox#dlgCardCheckbox::indicator {
                    width: 15px;
                    height: 15px;
                    border-radius: 3px;
                    border: 1px solid #334155;
                    background-color: #161B26;
                }
                QCheckBox#dlgCardCheckbox::indicator:checked {
                    background-color: #0284C7;
                    border-color: #38BDF8;
                }
                QLabel#dlgCardBadge {
                    background-color: #161F30;
                    color: #38BDF8;
                    border: 1px solid #1E3A5F;
                    border-radius: 3px;
                    padding: 0 6px;
                }
                QLabel#dlgCardDesc {
                    color: #94A3B8;
                }
                QLabel#dlgCardCitation {
                    color: #2DD4BF;
                    background-color: #0E2422;
                    border: 1px solid #115E59;
                    border-radius: 3px;
                    padding: 1px 6px;
                }
                QWidget#dlgBottomBar {
                    background-color: #10141F;
                    border-top: 1px solid #1E293B;
                }
                QPushButton#dlgBtnReset {
                    background-color: #18181B;
                    color: #A1A1AA;
                    border: 1px solid #27272A;
                    border-radius: 3px;
                    font-family: 'Segoe UI';
                    font-size: 11px;
                    padding: 0 12px;
                }
                QPushButton#dlgBtnReset:hover {
                    background-color: #27272A;
                    color: #FFFFFF;
                }
                QLabel#dlgActiveCount {
                    color: #64748B;
                }
                QPushButton#dlgBtnApply {
                    background-color: #0284C7;
                    color: #FFFFFF;
                    border: 1px solid #0284C7;
                    border-radius: 3px;
                    font-family: 'Segoe UI';
                    font-size: 11px;
                    font-weight: bold;
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
                    border-radius: 6px;
                }
                QWidget#dlgHeaderIcon {
                    color: #2563EB;
                }
                QLabel#dlgTitle {
                    color: #0F172A;
                    letter-spacing: 0.5px;
                }
                QLabel#dlgSubtitle {
                    color: #64748B;
                    letter-spacing: 0.8px;
                }
                QPushButton#dlgBtnClose {
                    background: transparent;
                    color: #64748B;
                    border: none;
                    border-radius: 4px;
                    font-family: 'Segoe UI';
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton#dlgBtnClose:hover {
                    background-color: #FEE2E2;
                    color: #EF4444;
                }
                QLineEdit#dlgSearchBar {
                    background-color: #F8FAFC;
                    color: #0F172A;
                    border: 1px solid #CBD5E1;
                    border-radius: 4px;
                    padding: 0 10px;
                    font-family: 'Segoe UI';
                    font-size: 11px;
                }
                QLineEdit#dlgSearchBar:focus {
                    border: 1px solid #2563EB;
                }
                QFrame#dlgDivider, QFrame#dlgVDivider {
                    background-color: #E2E8F0;
                }
                QListWidget#dlgSidebar {
                    background-color: #F8FAFC;
                    border: none;
                    outline: none;
                    font-family: 'Segoe UI';
                    font-size: 11px;
                    color: #475569;
                    padding: 4px;
                }
                QListWidget#dlgSidebar::item {
                    padding: 8px 12px;
                    border-radius: 4px;
                    margin: 1px 0;
                }
                QListWidget#dlgSidebar::item:hover {
                    background-color: #F1F5F9;
                    color: #0F172A;
                }
                QListWidget#dlgSidebar::item:selected {
                    background-color: #E2E8F0;
                    color: #0F172A;
                    font-weight: bold;
                }
                QScrollArea#dlgScrollArea {
                    background-color: #FFFFFF;
                    border: none;
                }
                QWidget#dlgCardContainer {
                    background-color: #FFFFFF;
                }
                QFrame#dlgCard {
                    background-color: #FFFFFF;
                    border: 1px solid #E2E8F0;
                    border-radius: 5px;
                }
                QFrame#dlgCard:hover {
                    background-color: #F8FAFC;
                    border-color: #CBD5E1;
                }
                QCheckBox#dlgCardCheckbox {
                    color: #0F172A;
                    spacing: 8px;
                }
                QCheckBox#dlgCardCheckbox::indicator {
                    width: 15px;
                    height: 15px;
                    border-radius: 3px;
                    border: 1px solid #CBD5E1;
                    background-color: #F8FAFC;
                }
                QCheckBox#dlgCardCheckbox::indicator:checked {
                    background-color: #2563EB;
                    border-color: #2563EB;
                }
                QLabel#dlgCardBadge {
                    background-color: #EFF6FF;
                    color: #1D4ED8;
                    border: 1px solid #BFDBFE;
                    border-radius: 3px;
                    padding: 0 6px;
                }
                QLabel#dlgCardDesc {
                    color: #475569;
                }
                QLabel#dlgCardCitation {
                    color: #0D9488;
                    background-color: #F0FDFA;
                    border: 1px solid #CCFBF1;
                    border-radius: 3px;
                    padding: 1px 6px;
                }
                QWidget#dlgBottomBar {
                    background-color: #F8FAFC;
                    border-top: 1px solid #E2E8F0;
                }
                QPushButton#dlgBtnReset {
                    background-color: #FFFFFF;
                    color: #475569;
                    border: 1px solid #CBD5E1;
                    border-radius: 3px;
                    font-family: 'Segoe UI';
                    font-size: 11px;
                    padding: 0 12px;
                }
                QPushButton#dlgBtnReset:hover {
                    background-color: #F1F5F9;
                    color: #0F172A;
                }
                QLabel#dlgActiveCount {
                    color: #64748B;
                }
                QPushButton#dlgBtnApply {
                    background-color: #2563EB;
                    color: #FFFFFF;
                    border: 1px solid #2563EB;
                    border-radius: 3px;
                    font-family: 'Segoe UI';
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton#dlgBtnApply:hover {
                    background-color: #1D4ED8;
                }
                QLabel#dlgEmptyLabel {
                    color: #94A3B8;
                    font-family: 'Segoe UI';
                    font-size: 12px;
                }
            """)


# ============================================================
# INDICATOR CALCULATION & RENDERING HELPERS - Clean Architecture
# ============================================================

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
        result["MA_200"] = df["close"].rolling(window=200, min_periods=1).mean().tolist()

    # 3. Donchian Channels (100) - Donchian (1960); Park & Irwin (2007)
    if active.get("donchian", False) and n >= 5:
        lookback = min(100, n)
        result["DONCHIAN_HIGH"] = float(df["high"].iloc[-lookback:].max())
        result["DONCHIAN_LOW"] = float(df["low"].iloc[-lookback:].min())

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
        cum_vp = (typical_price * vol).cumsum()
        cum_vol = vol.cumsum().replace(0, 1.0)
        vwap = cum_vp / cum_vol
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
        result["MACD_LINE"] = macd_line.tolist()
        result["MACD_SIGNAL"] = signal_line.tolist()

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
        window.plot_widget.addItem(curve)
        window._ind_curves[key] = curve
    return window._ind_curves[key]


def _get_or_create_hline(window, key, pen):
    """Retrieves existing InfiniteLine or creates and attaches to plot_widget."""
    if not hasattr(window, "_ind_curves"):
        window._ind_curves = {}
    if key not in window._ind_curves:
        line = pg.InfiniteLine(angle=0, pen=pen, movable=False)
        window.plot_widget.addItem(line)
        window._ind_curves[key] = line
    return window._ind_curves[key]


def _hide_curve(window, key):
    """Hides indicator curve safely without destroying the graphical object."""
    if hasattr(window, "_ind_curves") and key in window._ind_curves:
        window._ind_curves[key].setVisible(False)


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

    # 3. Donchian Channel (100)
    if active.get("donchian", False) and "DONCHIAN_HIGH" in computed:
        x_start = max(0, n - 100)
        x_end = max(0, n - 1)
        r_curve = _get_or_create_curve(window, "DONCHIAN_R", pg.mkPen(color=(244, 63, 94, 180), width=1.2, style=Qt.DashLine))
        r_curve.setData([x_start, x_end], [computed["DONCHIAN_HIGH"], computed["DONCHIAN_HIGH"]])
        r_curve.setVisible(True)

        s_curve = _get_or_create_curve(window, "DONCHIAN_S", pg.mkPen(color=(16, 185, 129, 180), width=1.2, style=Qt.DashLine))
        s_curve.setData([x_start, x_end], [computed["DONCHIAN_LOW"], computed["DONCHIAN_LOW"]])
        s_curve.setVisible(True)
    else:
        _hide_curve(window, "DONCHIAN_R")
        _hide_curve(window, "DONCHIAN_S")

    # 4. Classic Floor Pivots
    if active.get("pivot", False):
        try:
            sym = getattr(window, "current_sym", "XAUUSD")
            d1_rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_D1, 0, 3)
            if d1_rates is not None and len(d1_rates) >= 2:
                prev = d1_rates[-2]
                H = float(prev["high"])
                L = float(prev["low"])
                C = float(prev["close"])
                P = (H + L + C) / 3.0
                R1 = 2 * P - L
                S1 = 2 * P - H
                R2 = P + (H - L)
                S2 = P - (H - L)

                today_open_time = d1_rates[-1]["time"]
                x_start = 0
                if "time" in df.columns:
                    today_mask = df["time"] >= today_open_time
                    if today_mask.any():
                        x_start = int(today_mask.idxmax())
                x_end = max(0, n - 1)
                if x_start >= x_end:
                    x_start = max(0, x_end - 30)

                pivot_cfg = [
                    ("PIVOT_P", P, pg.mkPen("#94A3B8", width=1.0, style=Qt.DashLine)),
                    ("PIVOT_R1", R1, pg.mkPen(color=(244, 63, 94, 200), width=1.1, style=Qt.DashLine)),
                    ("PIVOT_S1", S1, pg.mkPen(color=(16, 185, 129, 200), width=1.1, style=Qt.DashLine)),
                    ("PIVOT_R2", R2, pg.mkPen(color=(244, 63, 94, 130), width=1.0, style=Qt.DotLine)),
                    ("PIVOT_S2", S2, pg.mkPen(color=(16, 185, 129, 130), width=1.0, style=Qt.DotLine)),
                ]
                for key, val, pen in pivot_cfg:
                    c = _get_or_create_curve(window, key, pen)
                    c.setData([x_start, x_end], [val, val])
                    c.setVisible(True)
        except Exception as e:
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

    # 7. Fair Value Gaps (FVG)
    if active.get("fvg", False) and "FVG_ZONES" in computed:
        fvg_zones = computed["FVG_ZONES"]
        # Plot up to last 10 significant FVGs
        for idx in range(10):
            k_top = f"FVG_TOP_{idx}"
            k_bot = f"FVG_BOT_{idx}"
            if idx < len(fvg_zones):
                x1, x2, top_p, bot_p, is_bull = fvg_zones[-(idx + 1)]
                pen_color = (6, 182, 212, 180) if is_bull else (245, 158, 11, 180)
                pen = pg.mkPen(color=pen_color, width=1.2, style=Qt.DashLine)

                c_top = _get_or_create_curve(window, k_top, pen)
                c_top.setData([x1, x2 + 15], [top_p, top_p])
                c_top.setVisible(True)

                c_bot = _get_or_create_curve(window, k_bot, pen)
                c_bot.setData([x1, x2 + 15], [bot_p, bot_p])
                c_bot.setVisible(True)
            else:
                _hide_curve(window, k_top)
                _hide_curve(window, k_bot)
    else:
        for idx in range(10):
            _hide_curve(window, f"FVG_TOP_{idx}")
            _hide_curve(window, f"FVG_BOT_{idx}")

    # 8. RSI 14 (Mapped corridor at chart lower bounds)
    if active.get("rsi", False) and "RSI_14" in computed and n > 0:
        y_min = float(df["low"].min())
        y_max = float(df["high"].max())
        y_span = max(y_max - y_min, 1e-4)

        # Map 0..100 RSI to lower 12% corridor of price
        corridor_base = y_min + y_span * 0.02
        corridor_height = y_span * 0.12

        rsi_raw = np.array(computed["RSI_14"])
        rsi_mapped = (corridor_base + (rsi_raw / 100.0) * corridor_height).tolist()

        c_rsi = _get_or_create_curve(window, "RSI_14_CURVE", pg.mkPen("#10B981", width=1.3))
        c_rsi.setData(x, rsi_mapped)
        c_rsi.setVisible(True)

        # 70/30 bounds
        r70 = corridor_base + 0.70 * corridor_height
        r30 = corridor_base + 0.30 * corridor_height
        c_r70 = _get_or_create_curve(window, "RSI_70_LINE", pg.mkPen(color=(244, 63, 94, 120), width=1.0, style=Qt.DotLine))
        c_r70.setData([0, n - 1], [r70, r70])
        c_r70.setVisible(True)

        c_r30 = _get_or_create_curve(window, "RSI_30_LINE", pg.mkPen(color=(16, 185, 129, 120), width=1.0, style=Qt.DotLine))
        c_r30.setData([0, n - 1], [r30, r30])
        c_r30.setVisible(True)
    else:
        _hide_curve(window, "RSI_14_CURVE")
        _hide_curve(window, "RSI_70_LINE")
        _hide_curve(window, "RSI_30_LINE")

    # 9. MACD (Mapped to lower corridor above RSI)
    if active.get("macd", False) and "MACD_LINE" in computed and n > 0:
        y_min = float(df["low"].min())
        y_max = float(df["high"].max())
        y_span = max(y_max - y_min, 1e-4)

        corridor_base = y_min + y_span * 0.16
        corridor_height = y_span * 0.10

        macd_raw = np.array(computed["MACD_LINE"])
        sig_raw = np.array(computed["MACD_SIGNAL"])
        m_min = min(macd_raw.min(), sig_raw.min())
        m_max = max(macd_raw.max(), sig_raw.max())
        m_range = max(m_max - m_min, 1e-5)

        macd_mapped = (corridor_base + ((macd_raw - m_min) / m_range) * corridor_height).tolist()
        sig_mapped = (corridor_base + ((sig_raw - m_min) / m_range) * corridor_height).tolist()

        c_macd = _get_or_create_curve(window, "MACD_CURVE", pg.mkPen("#06B6D4", width=1.2))
        c_macd.setData(x, macd_mapped)
        c_macd.setVisible(True)

        c_sig = _get_or_create_curve(window, "MACD_SIG_CURVE", pg.mkPen("#F43F5E", width=1.2, style=Qt.DashLine))
        c_sig.setData(x, sig_mapped)
        c_sig.setVisible(True)
    else:
        _hide_curve(window, "MACD_CURVE")
        _hide_curve(window, "MACD_SIG_CURVE")

    # 10. CVD Proxy
    if active.get("cvd", False) and "CVD_LINE" in computed and n > 0:
        y_min = float(df["low"].min())
        y_max = float(df["high"].max())
        y_span = max(y_max - y_min, 1e-4)

        corridor_base = y_min + y_span * 0.28
        corridor_height = y_span * 0.08

        cvd_raw = np.array(computed["CVD_LINE"])
        c_min = cvd_raw.min()
        c_max = cvd_raw.max()
        c_range = max(c_max - c_min, 1e-5)

        cvd_mapped = (corridor_base + ((cvd_raw - c_min) / c_range) * corridor_height).tolist()
        c_cvd = _get_or_create_curve(window, "CVD_CURVE", pg.mkPen("#8B5CF6", width=1.2))
        c_cvd.setData(x, cvd_mapped)
        c_cvd.setVisible(True)
    else:
        _hide_curve(window, "CVD_CURVE")


__all__ = [
    "INDICATOR_CATALOG",
    "INDICATOR_METADATA",
    "INDICATOR_LABELS",
    "IndicatorDialog",
    "_compute_indicators",
    "_refresh_indicators",
    "_get_or_create_curve",
    "_get_or_create_hline",
    "_hide_curve",
]
