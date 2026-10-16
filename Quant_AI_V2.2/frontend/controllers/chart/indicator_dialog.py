"""
Technical Indicator Selection Dialog and Calculation Engine
"""

import os
import json
import numpy as np
import pandas as pd
import pyqtgraph as pg
from datetime import datetime
from PySide6 import QtCore, QtGui
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QCheckBox, QFrame
)
from backend.infrastructure.brokers.mt5_safe import mt5

INDICATOR_CATALOG = {
    "Xu huong": [
        {"id": "ema", "available": True},
        {"id": "ma200", "available": True},
    ],
    "Cau truc gia": [
        {"id": "donchian", "available": True},
        {"id": "pivot", "available": True},
    ],
    "Dao dong": [
        {"id": "rsi", "available": False},
        {"id": "macd", "available": False},
    ],
    "Khoi luong": [
        {"id": "volume", "available": False},
    ],
}

INDICATOR_LABELS = {
    "Xu huong": "Xu hướng",
    "Cau truc gia": "Cấu trúc giá",
    "Dao dong": "Dao động",
    "Khoi luong": "Khối lượng",
    "ema": "Đường Trung bình EMA (10, 50)",
    "ma200": "Đường MA 200",
    "donchian": "Vùng Hỗ trợ / Kháng cự (Donchian 100)",
    "pivot": "Pivot Points (Classic)",
    "rsi": "RSI (14) (Sắp ra mắt)",
    "macd": "MACD (Sắp ra mắt)",
    "volume": "Volume (Sắp ra mắt)",
}

class IndicatorDialog(QDialog):

    def __init__(self, parent=None, active_indicators=None, on_change=None):

        super().__init__(parent)

        self.setWindowTitle("STUDIES & INDICATORS")

        self.resize(560, 400)

        self.on_change = on_change

        self.active_indicators = active_indicators or {}

        self._checkboxes = {}

        self._current_cat = list(INDICATOR_CATALOG.keys())[0]

        self.setStyleSheet("""







            QDialog { background-color: #1E222D; }







            QLineEdit { background-color: #131722; color: #D1D4DC; border: 1px solid #2B3139; border-radius: 4px; padding: 7px 10px; font-size: 13px; margin: 10px 10px 6px 10px; }







            QListWidget { background-color: transparent; border: none; outline: none; color: #8B949E; font-size: 13px; }







            QListWidget::item { padding: 10px 14px; border-radius: 4px; }







            QListWidget::item:selected { background-color: #2B3139; color: #FFFFFF; }







            QListWidget::item:hover { background-color: #21262D; color: #C9D1D9; }







            QCheckBox { color: #D1D4DC; font-size: 13px; padding: 8px 4px; spacing: 8px; }







            QCheckBox:hover { color: #FFFFFF; }







            QCheckBox:disabled { color: #484F58; }







            QCheckBox::indicator { width: 16px; height: 16px; border-radius: 3px; border: 1px solid #444C56; background: #161B22; image: none; }







            QCheckBox::indicator:hover { border: 1px solid #58A6FF; }







            QCheckBox::indicator:checked { background: #1F6FEB; border: 1px solid #1F6FEB; image: url(frontend/assets/check_icon.svg); }







            QCheckBox::indicator:disabled { background: #21262D; border: 1px solid #30363D; image: none; }







        """)

        main = QVBoxLayout(self)

        main.setContentsMargins(0, 0, 0, 0)

        main.setSpacing(0)

        self.search_bar = QLineEdit()

        self.search_bar.setPlaceholderText("Search indicators...")

        main.addWidget(self.search_bar)

        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet("background:#21262D;")

        main.addWidget(div)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self.sidebar = QListWidget()

        self.sidebar.setFixedWidth(160)

        for k in INDICATOR_CATALOG:
            self.sidebar.addItem(INDICATOR_LABELS.get(k, k))

        self.sidebar.setCurrentRow(0)

        self.sidebar.currentRowChanged.connect(self._switch_cat)

        row.addWidget(self.sidebar)

        vsep = QFrame()
        vsep.setFixedWidth(1)
        vsep.setStyleSheet("background:#21262D;")

        row.addWidget(vsep)

        self.right_panel = QWidget()
        self.right_panel.setStyleSheet("background:transparent;")

        self.right_layout = QVBoxLayout(self.right_panel)

        self.right_layout.setContentsMargins(14, 8, 14, 14)
        self.right_layout.setSpacing(0)

        row.addWidget(self.right_panel)

        main.addLayout(row)

        self.search_bar.textChanged.connect(self._on_search)

        self._render(self._current_cat)

    def _clear(self):

        while self.right_layout.count():

            item = self.right_layout.takeAt(0)

            if item.widget():
                item.widget().deleteLater()

    def _render(self, cat, filt=""):

        self._clear()

        hdr = QLabel(INDICATOR_LABELS.get(cat, cat).upper())

        hdr.setStyleSheet(
            "color:#6E7681;font-size:10px;font-weight:bold;padding:8px 4px 4px 0;"
        )

        self.right_layout.addWidget(hdr)

        found = False

        for ind in INDICATOR_CATALOG.get(cat, []):

            label = INDICATOR_LABELS.get(ind["id"], ind["id"])

            if filt and filt.lower() not in label.lower():
                continue

            found = True

            cb = QCheckBox(label)

            cb.setEnabled(ind["available"])

            cb.setChecked(self.active_indicators.get(ind["id"], False))

            if ind["available"]:

                iid = ind["id"]

                cb.toggled.connect(lambda chk, i=iid: self._toggle(i, chk))

            self.right_layout.addWidget(cb)

            self._checkboxes[ind["id"]] = cb

        if not found:

            lbl = QLabel("No indicators found.")

            lbl.setStyleSheet("color:#484F58;font-size:12px;padding:10px 0;")

            self.right_layout.addWidget(lbl)

        self.right_layout.addStretch()

    def _switch_cat(self, row):

        keys = list(INDICATOR_CATALOG.keys())

        if 0 <= row < len(keys):

            self._current_cat = keys[row]

            self._render(self._current_cat, self.search_bar.text())

    def _on_search(self, text):

        self._render(self._current_cat, text)

    def _toggle(self, ind_id, checked):

        self.active_indicators[ind_id] = checked

        if self.on_change:
            self.on_change()


# ============================================================


# INDICATOR HELPERS - Clean Architecture / Single Responsibility


# ============================================================


def _compute_indicators(df, active):
    """







    Tinh toan tat ca chi bao can thiet.







    Chi tinh nhung chi bao dang duoc bat -> Tiet kiem CPU.







    """

    result = {}

    n = len(df)

    x = list(range(n))

    result["x"] = x

    if active.get("ema", False):

        result["EMA_10"] = df["close"].ewm(span=10, adjust=False).mean().tolist()

        result["EMA_50"] = df["close"].ewm(span=50, adjust=False).mean().tolist()

    if active.get("ma200", False):

        result["MA_200"] = (
            df["close"].rolling(window=200, min_periods=1).mean().tolist()
        )

    if active.get("donchian", False) and n >= 100:

        result["DONCHIAN_HIGH"] = df["high"].iloc[-100:].max()

        result["DONCHIAN_LOW"] = df["low"].iloc[-100:].min()

    if active.get("pivot", False):

        try:

            from backend.infrastructure.brokers.mt5_safe import mt5

            sym = getattr(df, "_sym", None)

        except Exception:

            sym = None

        result["_pivot_raw"] = True  # Signal to fetch D1 later

    return result


def _get_or_create_curve(window, key, pen, **kwargs):
    """







    Lay curve da ton tai hoac tao moi va addItem vao plot_widget.







    Day la trai tim cua setData pattern.







    """

    if not hasattr(window, "_ind_curves"):

        window._ind_curves = {}

    if key not in window._ind_curves:

        curve = pg.PlotCurveItem(pen=pen, **kwargs)

        window.plot_widget.addItem(curve)

        window._ind_curves[key] = curve

    return window._ind_curves[key]


def _get_or_create_hline(window, key, pen):
    """Lay InfiniteLine da ton tai hoac tao moi."""

    if not hasattr(window, "_ind_curves"):

        window._ind_curves = {}

    if key not in window._ind_curves:

        line = pg.InfiniteLine(angle=0, pen=pen, movable=False)

        window.plot_widget.addItem(line)

        window._ind_curves[key] = line

    return window._ind_curves[key]


def _hide_curve(window, key):
    """An duong ke neu chi bao tuong ung bi tat."""

    if hasattr(window, "_ind_curves") and key in window._ind_curves:

        window._ind_curves[key].setVisible(False)


def _refresh_indicators(window, df):
    """







    Ham dieu phoi chinh: Quyet dinh ve gi va an gi.







    Su dung setData() thay vi clear() + addItem() -> Hieu nang ~80% tot hon.







    """

    active = getattr(window, "active_indicators", {})

    computed = _compute_indicators(df, active)

    x = computed.get("x", [])

    # --- EMA 10 ---

    if active.get("ema", False) and "EMA_10" in computed:

        c = _get_or_create_curve(window, "EMA_10", pg.mkPen("#F59E0B", width=1.2))

        c.setData(x, computed["EMA_10"])

        c.setVisible(True)

    else:

        _hide_curve(window, "EMA_10")

    # --- EMA 50 ---

    if active.get("ema", False) and "EMA_50" in computed:

        c = _get_or_create_curve(window, "EMA_50", pg.mkPen("#3B82F6", width=1.5))

        c.setData(x, computed["EMA_50"])

        c.setVisible(True)

    else:

        _hide_curve(window, "EMA_50")

    # --- MA 200 ---

    if active.get("ma200", False) and "MA_200" in computed:

        c = _get_or_create_curve(
            window, "MA_200", pg.mkPen("#A78BFA", width=1.2, style=Qt.DashLine)
        )

        c.setData(x, computed["MA_200"])

        c.setVisible(True)

    else:

        _hide_curve(window, "MA_200")

    # --- DONCHIAN S/R ---

    # Dung PlotCurveItem voi x gioi han trong 100 nen gan nhat

    if active.get("donchian", False) and "DONCHIAN_HIGH" in computed:

        total = len(x)

        x_start = max(0, total - 100)

        x_end = total - 1

        r_curve = _get_or_create_curve(
            window,
            "DONCHIAN_R",
            pg.mkPen(color=(242, 54, 69, 160), width=1, style=Qt.DashLine),
        )

        r_curve.setData(
            [x_start, x_end], [computed["DONCHIAN_HIGH"], computed["DONCHIAN_HIGH"]]
        )

        r_curve.setVisible(True)

        s_curve = _get_or_create_curve(
            window,
            "DONCHIAN_S",
            pg.mkPen(color=(16, 185, 129, 160), width=1, style=Qt.DashLine),
        )

        s_curve.setData(
            [x_start, x_end], [computed["DONCHIAN_LOW"], computed["DONCHIAN_LOW"]]
        )

        s_curve.setVisible(True)

    else:

        _hide_curve(window, "DONCHIAN_R")

        _hide_curve(window, "DONCHIAN_S")

    # --- PIVOT POINTS (Classic) ---

    # Su dung PlotCurveItem thay vi InfiniteLine de tranh duong ke vo tan

    if active.get("pivot", False):

        try:

            from backend.infrastructure.brokers.mt5_safe import mt5

            import datetime

            sym = getattr(window, "current_sym", "XAUUSD")

            d1_rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_D1, 0, 3)

            if d1_rates is not None and len(d1_rates) >= 2:

                prev = d1_rates[-2]  # Phien hom qua

                H = prev["high"]

                L = prev["low"]

                C = prev["close"]

                P = (H + L + C) / 3.0

                R1 = 2 * P - L

                S1 = 2 * P - H

                R2 = P + (H - L)

                S2 = P - (H - L)

                # Tim x_start: Chi so nen dau tien cua phien hom nay (D1 hien tai)

                today_open_time = d1_rates[-1]["time"]

                total = len(df)

                x_start = 0

                if "time" in df.columns:

                    today_mask = df["time"] >= today_open_time

                    if today_mask.any():

                        x_start = int(today_mask.idxmax())

                x_end = total - 1

                # Neu khong co nen hom nay (ngoai gio), ve tu nen cuoi cung tro ve

                if x_start >= x_end:

                    x_start = max(0, x_end - 30)

                pivot_cfg = [
                    ("PIVOT_P", P, pg.mkPen("#D1D4DC", width=1, style=Qt.DashLine)),
                    (
                        "PIVOT_R1",
                        R1,
                        pg.mkPen(color=(242, 54, 69, 200), width=1, style=Qt.DashLine),
                    ),
                    (
                        "PIVOT_S1",
                        S1,
                        pg.mkPen(color=(16, 185, 129, 200), width=1, style=Qt.DashLine),
                    ),
                    (
                        "PIVOT_R2",
                        R2,
                        pg.mkPen(color=(242, 54, 69, 120), width=1, style=Qt.DotLine),
                    ),
                    (
                        "PIVOT_S2",
                        S2,
                        pg.mkPen(color=(16, 185, 129, 120), width=1, style=Qt.DotLine),
                    ),
                ]

                for key, val, pen in pivot_cfg:

                    c = _get_or_create_curve(window, key, pen)

                    c.setData([x_start, x_end], [val, val])

                    c.setVisible(True)

        except Exception as e:

            print(f"[Pivot] Error: {e}")

    else:

        for key in ["PIVOT_P", "PIVOT_R1", "PIVOT_S1", "PIVOT_R2", "PIVOT_S2"]:
            _hide_curve(window, key)


