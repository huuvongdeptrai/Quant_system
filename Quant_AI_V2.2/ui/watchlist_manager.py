from PySide6.QtCore import Qt
import os, json
from infrastructure.brokers.mt5_safe import mt5
from PySide6.QtWidgets import (
    QTreeWidgetItem,
    QHeaderView,
    QDialog,
    QVBoxLayout,
    QLineEdit,
    QTreeWidget,
    QMenu,
    QMessageBox,
)
from PySide6.QtGui import QColor
from PySide6.QtCore import QObject
from core.event_bus import event_bus


class SymbolSearchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Thêm Mã (Phân theo Danh mục)")
        self.setFixedSize(450, 550)
        self.setProperty("class", "symbol_search_dialog")

        layout = QVBoxLayout(self)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Tìm kiếm mã...")
        self.search_box.textChanged.connect(self.filter_symbols)
        layout.addWidget(self.search_box)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemDoubleClicked.connect(self.on_select)
        layout.addWidget(self.tree)

        self.selected_symbol = None
        self.selected_category = None
        self.load_symbols()

    def load_symbols(self):
        if not mt5.terminal_info():
            return
        symbols = mt5.symbols_get()
        if not symbols:
            return

        cats = {}
        for s in symbols:
            path = s.path.split("\\")
            cat = path[0] if len(path) > 0 else "Khác"
            if cat not in cats:
                cats[cat] = []
            cats[cat].append(s.name)

        for cat, syms in cats.items():
            cat_item = QTreeWidgetItem([cat])
            for sym in syms:
                child = QTreeWidgetItem([sym])
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
        if item.childCount() == 0:  # Is a symbol
            self.selected_symbol = item.text(0)
            self.selected_category = item.parent().text(0)
            self.accept()


class WatchlistManager(QObject):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.tree = self.window.treeWatchlist
        self.tree.setProperty("class", "watchlist_tree")
        self.setup_ui()
        self.last_account = None
        self.data_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "watchlist.json"
        )
        self.load_watchlist()

    def setup_ui(self):
        self.tree.setColumnCount(4)
        self.tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tree.setIndentation(12)  # Reduce left spacing
        self.tree.setHeaderLabels(["Mã", "Giá", "Pips", "%"])

        self.tree.headerItem().setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
        self.tree.headerItem().setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter)
        self.tree.headerItem().setTextAlignment(3, Qt.AlignRight | Qt.AlignVCenter)
        self.tree.header().setMinimumSectionSize(40)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.Fixed)
        self.tree.header().setSectionResizeMode(2, QHeaderView.Fixed)
        self.tree.header().setSectionResizeMode(3, QHeaderView.Fixed)
        self.tree.setColumnWidth(1, 55)
        self.tree.setColumnWidth(2, 52)
        self.tree.setColumnWidth(3, 42)

        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        event_bus.market_tick.connect(self.on_tick)

        if hasattr(self.window, "btnOpenSearch"):
            self.window.btnOpenSearch.clicked.connect(self.open_search_modal)

    def check_account_changed(self):
        acc = mt5.account_info()
        if not acc:
            return
        if self.last_account != acc.login:
            self.last_account = acc.login

    def save_watchlist(self):
        symbols = self.get_all_symbols()
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(symbols, f)

    def load_watchlist(self):
        if not os.path.exists(self.data_file):
            self.add_symbol_to_tree("XAUUSD", "COMMODITIES")
            return
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                symbols = json.load(f)
            for sym in symbols:
                info = mt5.symbol_info(sym)
                cat = "Khác"
                if info:
                    path = info.path.split("\\")
                    cat = path[0] if len(path) > 0 else "Khác"
                self.add_symbol_to_tree(sym, cat)
        except Exception:
            self.add_symbol_to_tree("XAUUSD", "COMMODITIES")

    def open_search_modal(self):
        dialog = SymbolSearchDialog(self.window)
        if dialog.exec() == QDialog.Accepted and dialog.selected_symbol:
            self.add_symbol_to_tree(dialog.selected_symbol, dialog.selected_category)

    def add_symbol_to_tree(self, sym, cat_name):
        if sym in self.get_all_symbols():
            return

        cat_item = None
        for i in range(self.tree.topLevelItemCount()):
            if self.tree.topLevelItem(i).text(0) == cat_name:
                cat_item = self.tree.topLevelItem(i)
                break
        if not cat_item:
            cat_item = QTreeWidgetItem([cat_name])
            self.tree.addTopLevelItem(cat_item)
            cat_item.setExpanded(True)

        child = QTreeWidgetItem([sym, "-", "-", "-"])

        child.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
        child.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter)
        child.setTextAlignment(3, Qt.AlignRight | Qt.AlignVCenter)
        cat_item.addChild(child)
        self.save_watchlist()

    def _show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item or item.childCount() > 0:
            return
        menu = QMenu(self.tree)
        menu.setProperty("class", "context_menu")
        act_del = menu.addAction("Xóa " + item.text(0))
        action = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if action == act_del:
            parent = item.parent()
            parent.removeChild(item)
            if parent.childCount() == 0:
                self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(parent))
            self.save_watchlist()

    def get_all_symbols(self):
        if not self.tree:
            return []
        symbols = []
        for i in range(self.tree.topLevelItemCount()):
            cat = self.tree.topLevelItem(i)
            for j in range(cat.childCount()):
                symbols.append(cat.child(j).text(0))
        return symbols

    def on_tick(self, sym, bid, ask):
        if not self.tree:
            return
        self.check_account_changed()

        for i in range(self.tree.topLevelItemCount()):
            cat = self.tree.topLevelItem(i)
            for j in range(cat.childCount()):
                item = cat.child(j)
                if item.text(0) != sym:
                    continue
                info = mt5.symbol_info(sym)
                if not info:
                    return
                item.setText(1, f"{bid:.{info.digits}f}")

                rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_D1, 1, 1)
                if rates is not None and len(rates) > 0:
                    y_close = rates[0]["close"]
                    if y_close > 0:
                        change_pts = bid - y_close
                        pct_change = (change_pts / y_close) * 100
                        prefix = "+" if change_pts > 0 else ""
                        item.setText(2, f"{prefix}{change_pts:.{info.digits}f}")
                        item.setText(3, f"{prefix}{pct_change:.2f}%")
                        col = (
                            QColor("#3FB950")
                            if change_pts > 0
                            else (
                                QColor("#F23645")
                                if change_pts < 0
                                else QColor("#8B949E")
                            )
                        )
                        item.setForeground(2, col)
                        item.setForeground(3, col)
                return
