import os, json
import MetaTrader5 as mt5
from PySide6.QtWidgets import QTreeWidgetItem, QHeaderView, QDialog, QVBoxLayout, QLineEdit, QTreeWidget, QMenu
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt
from core.event_bus import event_bus


class SymbolSearchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Th\u00eam M\u00e3 (Ph\u00e2n theo Danh m\u1ee5c)')
        self.setFixedSize(450, 550)
        self.setStyleSheet(
            'QDialog { background-color: #0D1117; } '
            'QLineEdit { background-color: #010409; border: 1px solid #30363D; '
            'color: white; padding: 10px; border-radius: 6px; font-size: 13px; } '
            'QTreeWidget { background-color: #0D1117; color: white; border: none; '
            'font-size: 13px; font-weight: bold; outline: none; } '
            'QTreeWidget::item { padding: 10px; border-bottom: 1px solid #21262D; } '
            'QTreeWidget::item:hover { background-color: #161B22; } '
        )

        layout = QVBoxLayout(self)
        self.search_box = QLineEdit()
        # Bo icon kinh lup theo yeu cau cua nguoi dung
        self.search_box.setPlaceholderText('T\u00ecm m\u00e3 (VD: XAUUSD, AAPL)...')
        layout.addWidget(self.search_box)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(15)
        layout.addWidget(self.tree)

        self.all_symbols_data = []
        self.selected_symbol = None
        self.load_symbols()

        self.search_box.textChanged.connect(self.filter_symbols)
        self.tree.itemDoubleClicked.connect(self.on_select)

    def load_symbols(self):
        if mt5.terminal_info() is not None:
            syms = mt5.symbols_get()
            if syms:
                for s in syms:
                    path_parts = s.path.replace('/', os.sep).split(os.sep)
                    cat = path_parts[0].upper() if path_parts else 'OTHER'
                    self.all_symbols_data.append({'name': s.name, 'category': cat, 'desc': s.description})
                self.filter_symbols('')
        else:
            QTreeWidgetItem(self.tree, ['Ch\u01b0a k\u1ebft n\u1ed1i MT5! H\u00e3y k\u1ebft n\u1ed1i tr\u01b0\u1edbc.'])

    def filter_symbols(self, text):
        self.tree.clear()
        text = text.upper()
        grouped = {}
        for s in self.all_symbols_data:
            if text in s['name'].upper() or text in s['desc'].upper():
                cat = s['category']
                if cat not in grouped:
                    grouped[cat] = []
                grouped[cat].append(s)

        for cat in sorted(grouped.keys()):
            cat_item = QTreeWidgetItem(self.tree, ['\U0001f4c2 ' + cat])
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemIsSelectable)
            for s in grouped[cat]:
                child = QTreeWidgetItem(cat_item, [s['name'] + '   (' + s['desc'] + ')'])
                child.setData(0, Qt.UserRole, s['name'])
            if text:
                cat_item.setExpanded(True)

    def on_select(self, item, column):
        sym = item.data(0, Qt.UserRole)
        if sym:
            self.selected_symbol = sym
            self.accept()


class WatchlistManager:
    def __init__(self, window):
        self.window = window
        self.tree = self.window.treeWatchlist if hasattr(self.window, 'treeWatchlist') else None
        self.wl_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'watchlist.json')
        self._last_account = None

        if self.tree:
            self.setup_ui()
            self.load_watchlist()
            event_bus.market_tick.connect(self.on_tick)

            if hasattr(self.window, 'btnOpenSearch'):
                self.window.btnOpenSearch.clicked.connect(self.open_search_modal)
            if hasattr(self.window, 'btnDelSymbol'):
                self.window.btnDelSymbol.clicked.connect(self.del_symbol)
            # Chuot phai de xoa
            self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
            self.tree.customContextMenuRequested.connect(self._show_context_menu)

    def setup_ui(self):
        self.tree.setIndentation(12)
        self.tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Col 0 (Ma): co dinh vua du, col 1 (Gia): stretch lay phan con lai
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(3, QHeaderView.ResizeToContents)

    def check_account_changed(self):
        """
        Goi tu tick timer. Khi tai khoan MT5 thay doi, re-resolve
        category cho tat ca symbol (xoa UNKNOWN neu da co info).
        """
        acc = mt5.account_info()
        if acc is None:
            self._last_account = None
            return

        if acc.login != self._last_account:
            self._last_account = acc.login
            # Re-resolve: lay lai tat ca symbol hien tai va dung lai cay
            current_symbols = self.get_all_symbols()
            self.tree.clear()
            for sym in current_symbols:
                self.add_symbol_to_tree(sym)

    def save_watchlist(self):
        symbols = self.get_all_symbols()
        os.makedirs(os.path.dirname(self.wl_file), exist_ok=True)
        with open(self.wl_file, 'w', encoding='utf-8') as f:
            json.dump({'symbols': symbols}, f, indent=4)

    def load_watchlist(self):
        self.tree.clear()
        if os.path.exists(self.wl_file):
            try:
                with open(self.wl_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for sym in data.get('symbols', []):
                    self.add_symbol_to_tree(sym)
            except Exception:
                pass

    def open_search_modal(self):
        dlg = SymbolSearchDialog(self.window)
        if dlg.exec():
            sym = dlg.selected_symbol
            if sym:
                self.add_symbol_to_tree(sym)
                self.save_watchlist()

    def del_symbol(self):
        sel = self.tree.selectedItems()
        if not sel:
            return
        item = sel[0]
        parent = item.parent()
        if parent:
            parent.removeChild(item)
            if parent.childCount() == 0:
                self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(parent))
            self.save_watchlist()

    def add_symbol_to_tree(self, sym):
        try:
            if mt5.terminal_info() is not None:
                mt5.symbol_select(sym, True)
            info = mt5.symbol_info(sym)
            cat = info.path.replace('/', os.sep).split(os.sep)[0].upper() if (info and info.path) else 'UNKNOWN'
        except Exception:
            cat = 'UNKNOWN'

        # Tim cat_item hien co
        cat_item = None
        for i in range(self.tree.topLevelItemCount()):
            if self.tree.topLevelItem(i).text(0) == cat:
                cat_item = self.tree.topLevelItem(i)
                break

        if not cat_item:
            cat_item = QTreeWidgetItem(self.tree, [cat, '', '', ''])
            cat_item.setForeground(0, QColor('#8B949E'))
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemIsSelectable)
            cat_item.setExpanded(True)

        # Tranh them trung
        for i in range(cat_item.childCount()):
            if cat_item.child(i).text(0) == sym:
                return

        item = QTreeWidgetItem(cat_item, [sym, '---', '---', '---'])
        item.setForeground(0, QColor('#E5E7EB'))
        item.setForeground(1, QColor('#8B949E'))

    def _show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None or item.parent() is None:
            return  # Chi hien menu tren symbol, khong hien tren category
        menu = QMenu(self.tree)
        menu.setStyleSheet(
            'QMenu { background:#161B22; color:#E5E7EB; border:1px solid #30363D; }'
            'QMenu::item:selected { background:#21262D; }'
        )
        act_del = menu.addAction('\u274c  X\u00f3a ' + item.text(0))
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
        # Kiem tra doi account truoc khi xu ly tick
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
                item.setText(1, f'{bid:.{info.digits}f}')

                rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_D1, 1, 1)
                if rates is not None and len(rates) > 0:
                    y_close = rates[0]['close']
                    if y_close > 0:
                        change_pts = bid - y_close
                        pct_change = (change_pts / y_close) * 100
                        prefix = '+' if change_pts > 0 else ''
                        item.setText(2, f'{prefix}{change_pts:.{info.digits}f}')
                        item.setText(3, f'{prefix}{pct_change:.2f}%')
                        col = (QColor('#3FB950') if change_pts > 0
                               else QColor('#F23645') if change_pts < 0
                               else QColor('#8B949E'))
                        item.setForeground(2, col)
                        item.setForeground(3, col)
                return
