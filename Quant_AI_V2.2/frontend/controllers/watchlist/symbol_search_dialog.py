"""
Symbol Search Modal Dialog for Quant AI Terminal.
Allows filtering, browsing, and adding assets from MT5 market catalog into the user's Watchlist.
"""

import os
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QTreeWidget, QTreeWidgetItem
)
from PySide6.QtGui import QColor, QFont
from backend.infrastructure.brokers.mt5_safe import mt5


class SymbolSearchDialog(QDialog):
    """Modal dialog for searching and adding broker symbols into the active Watchlist."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Market Symbol")
        self.setFixedSize(480, 540)
        self.setProperty("class", "symbol_search_dialog")

        is_dark = False
        if parent is not None:
            is_dark = getattr(parent, "is_dark_theme", False)
            if not is_dark and hasattr(parent, "quant_terminal"):
                is_dark = getattr(parent.quant_terminal, "is_dark_theme", False)
        self.is_dark = is_dark

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search symbol (e.g. BTC, XAU, EUR)...")
        self.search_box.textChanged.connect(self.filter_symbols)
        self.search_box.setFixedHeight(28)
        layout.addWidget(self.search_box)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemDoubleClicked.connect(self.on_select)
        self.tree.itemSelectionChanged.connect(self._on_tree_selection_changed)
        layout.addWidget(self.tree)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedHeight(28)
        self.btn_cancel.setFixedWidth(80)
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_add = QPushButton("Add Symbol")
        self.btn_add.setFixedHeight(28)
        self.btn_add.setFixedWidth(100)
        self.btn_add.setCursor(Qt.PointingHandCursor)
        self.btn_add.clicked.connect(self._on_btn_add_click)
        btn_layout.addWidget(self.btn_add)

        layout.addLayout(btn_layout)

        self._apply_dialog_theme()
        self.selected_symbol = None
        self.selected_category = None
        self.load_symbols()

    def _apply_dialog_theme(self):
        if self.is_dark:
            self.setStyleSheet(
                "QDialog { background-color: #0c0e14; border: 1px solid #272d3b; border-radius: 2px; } "
                "QLineEdit { background-color: #141721; color: #f8fafc; border: 1px solid #272d3b; border-radius: 2px; padding: 0 8px; font-family: 'Segoe UI'; font-size: 11px; } "
                "QLineEdit:focus { border-color: #475569; } "
                "QTreeWidget { background-color: #080b11; color: #f8fafc; border: 1px solid #1c2230; border-radius: 2px; font-family: 'Segoe UI'; font-size: 11px; padding: 2px; outline: none; } "
                "QTreeWidget::item { padding: 4px 6px; border-bottom: 1px solid rgba(255, 255, 255, 0.03); border-radius: 1px; } "
                "QTreeWidget::item:hover { background-color: #161d2d; } "
                "QTreeWidget::item:selected { background-color: #1e293b; color: #f8fafc; font-weight: bold; } "
                "QPushButton { border-radius: 2px; font-family: 'Segoe UI'; font-size: 11px; font-weight: 600; }"
            )
            self.btn_cancel.setStyleSheet(
                "QPushButton { background-color: #18181b; color: #a1a1aa; border: 1px solid #27272a; height: 28px; } "
                "QPushButton:hover { background-color: #27272a; color: #ffffff; }"
            )
            self.btn_add.setStyleSheet(
                "QPushButton { background-color: #1e293b; color: #ffffff; border: 1px solid #475569; font-weight: bold; height: 28px; } "
                "QPushButton:hover { background-color: #334155; }"
            )
        else:
            self.setStyleSheet(
                "QDialog { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 2px; } "
                "QLineEdit { background-color: #f8fafc; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 2px; padding: 0 8px; font-family: 'Segoe UI'; font-size: 11px; } "
                "QTreeWidget { background-color: #ffffff; color: #0f172a; border: 1px solid #e2e8f0; font-family: 'Segoe UI'; font-size: 11px; } "
                "QPushButton { border-radius: 2px; font-family: 'Segoe UI'; font-size: 11px; font-weight: 600; }"
            )

    def _on_tree_selection_changed(self):
        items = self.tree.selectedItems()
        if items and items[0].childCount() == 0:
            self.btn_add.setEnabled(True)
        else:
            self.btn_add.setEnabled(False)

    def _on_btn_add_click(self):
        items = self.tree.selectedItems()
        if items and items[0].childCount() == 0:
            self.selected_symbol = items[0].text(0)
            self.selected_category = items[0].parent().text(0) if items[0].parent() else "OTHER"
            self.accept()

    def load_symbols(self):
        def map_cat_name(raw: str) -> str:
            r = raw.upper().strip()
            rl = r.lower()
            if "crypto" in rl or "btc" in rl: return "CRYPTO"
            if "gold" in rl or "silver" in rl or "xau" in rl: return "COMMODITIES"
            if "index" in rl or "indices" in rl: return "INDICES"
            if "oil" in rl or "gas" in rl: return "ENERGIES"
            if "forex" in rl or "fx" in rl: return "FOREX"
            if "metal" in rl: return "METALS"
            if "stock" in rl or "share" in rl: return "STOCKS"
            return r

        symbols = None
        try:
            if mt5.terminal_info():
                symbols = mt5.symbols_get()
        except Exception:
            pass

        cats = {}
        if symbols:
            for s in symbols:
                path = s.path.split("\\")
                raw_cat = path[0] if len(path) > 0 else "OTHER"
                cat = map_cat_name(raw_cat)
                if cat not in cats:
                    cats[cat] = []
                cats[cat].append(s.name)
        else:
            cats = {
                "COMMODITIES": ["XAUUSD", "XAGUSD", "USOIL", "UKOIL"],
                "CRYPTO": ["BTCUSD", "ETHUSD", "SOLUSD", "BNBUSD"],
                "FOREX": ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"],
                "INDICES": ["US30", "NAS100", "SPX500", "GER40"]
            }

        cat_color = QColor("#94a3b8" if self.is_dark else "#475569")
        sym_color = QColor("#f8fafc" if self.is_dark else "#0f172a")
        bold_font = QFont("Segoe UI", 10, QFont.Bold)
        sym_font = QFont("Consolas", 10)

        for cat, syms in cats.items():
            cat_item = QTreeWidgetItem([cat])
            cat_item.setFont(0, bold_font)
            cat_item.setForeground(0, cat_color)
            for sym in syms:
                child = QTreeWidgetItem([sym])
                child.setFont(0, sym_font)
                child.setForeground(0, sym_color)
                cat_item.addChild(child)
            self.tree.addTopLevelItem(cat_item)

    def filter_symbols(self):
        query = self.search_box.text().lower()
        for i in range(self.tree.topLevelItemCount()):
            cat = self.tree.topLevelItem(i)
            cat_match = False
            for j in range(cat.childCount()):
                child = cat.child(j)
                if query in child.text(0).lower():
                    child.setHidden(False)
                    cat_match = True
                else:
                    child.setHidden(True)
            cat.setHidden(not cat_match)
            if query and cat_match:
                cat.setExpanded(True)

    def on_select(self, item, column=0):
        if item.childCount() == 0:
            self.selected_symbol = item.text(0)
            self.selected_category = item.parent().text(0) if item.parent() else "OTHER"
            self.accept()
