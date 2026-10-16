from PySide6.QtCore import Qt
import os, json
from backend.infrastructure.brokers.mt5_safe import mt5
from PySide6.QtWidgets import (
    QTreeWidgetItem,
    QHeaderView,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QTreeWidget,
    QMenu,
    QMessageBox,
    QStyledItemDelegate,
    QStyle,
)
from PySide6.QtGui import QColor, QIcon, QFont, QPainter, QBrush
from PySide6.QtCore import QObject, QSize, QTimer
from backend.core.event_bus import event_bus


class SymbolSearchDialog(QDialog):
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

        # Bottom Button Bar
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
                "QDialog { background-color: #ffffff; border: 1px solid #94a3b8; border-radius: 2px; } "
                "QLineEdit { background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 2px; padding: 0 8px; font-family: 'Segoe UI'; font-size: 11px; } "
                "QLineEdit:focus { border: 1px solid #475569; } "
                "QTreeWidget { background-color: #ffffff; color: #0f172a; border: 1px solid #e2e8f0; border-radius: 2px; font-family: 'Segoe UI'; font-size: 11px; padding: 2px; outline: none; } "
                "QTreeWidget::item { padding: 4px 6px; border-bottom: 1px solid #f1f5f9; border-radius: 1px; } "
                "QTreeWidget::item:hover { background-color: #f8fafc; } "
                "QTreeWidget::item:selected { background-color: #e2e8f0; color: #0f172a; font-weight: bold; } "
                "QPushButton { border-radius: 2px; font-family: 'Segoe UI'; font-size: 11px; font-weight: 600; }"
            )
            self.btn_cancel.setStyleSheet(
                "QPushButton { background-color: #f8fafc; color: #334155; border: 1px solid #cbd5e1; height: 28px; } "
                "QPushButton:hover { background-color: #f1f5f9; color: #0f172a; border-color: #94a3b8; }"
            )
            self.btn_add.setStyleSheet(
                "QPushButton { background-color: #0f172a; color: #ffffff; border: 1px solid #0f172a; font-weight: bold; height: 28px; } "
                "QPushButton:hover { background-color: #1e293b; border-color: #1e293b; }"
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
            self.on_select(items[0])

    def load_symbols(self):
        def map_cat_name(raw):
            r = raw.strip()
            cat_map = {
                "Indices": "INDICES", "Indices Cash": "INDICES", "INDICES": "INDICES", "INDICES CASH": "INDICES",
                "Commodities": "COMMODITIES", "CommoditiesCash": "COMMODITIES", "COMMODITIES": "COMMODITIES", "COMMODITIESCASH": "COMMODITIES",
                "Energies": "ENERGIES", "Oil and Gas": "ENERGIES", "ENERGIES": "ENERGIES",
                "Forex": "FOREX", "Forex Majors": "FOREX", "Forex Minors": "FOREX", "FOREX": "FOREX",
                "Crypto": "CRYPTO", "Crypto Perpetual": "CRYPTO", "Crypto Perpetuals": "CRYPTO", "CRYPTO": "CRYPTO",
                "Metals": "METALS", "METALS": "METALS",
                "Stocks": "STOCKS", "STOCKS": "STOCKS",
                "Internal": "INTERNAL", "INTERNAL": "INTERNAL"
            }
            if r in cat_map:
                return cat_map[r]
            rl = r.lower()
            if "indic" in rl: return "INDICES"
            if "commodit" in rl: return "COMMODITIES"
            if "oil" in rl or "gas" in rl or "energ" in rl: return "ENERGIES"
            if "forex" in rl or "fx" in rl: return "FOREX"
            if "crypto" in rl: return "CRYPTO"
            if "metal" in rl: return "METALS"
            if "stock" in rl or "share" in rl: return "STOCKS"
            if "internal" in rl: return "INTERNAL"
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
        if item.childCount() == 0:  # Is a symbol
            self.selected_symbol = item.text(0)
            self.selected_category = item.parent().text(0) if item.parent() else "OTHER"
            self.accept()



class WatchlistDelegate(QStyledItemDelegate):
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
                from PySide6.QtGui import QFontMetrics
                fm = QFontMetrics(sub_font)
                avail_w = max(10, rect.width() - 8)
                elided_sub = fm.elidedText(sub, Qt.ElideRight, avail_w)
                painter.drawText(x, rect.top() + 27, elided_sub)

        elif col in (1, 2, 3):
            pad_r = -8 if col == 1 else -4
            rect = option.rect.adjusted(0, 0, pad_r, 0)
            painter.setFont(QFont("Consolas", 9, QFont.Bold if col == 1 else QFont.Normal))
            fg = index.data(Qt.ForegroundRole)
            if fg and isinstance(fg, (QColor, QBrush)):
                painter.setPen(fg if isinstance(fg, QColor) else fg.color())
            else:
                default_color = QColor("#cbd5e1" if is_dark else "#0f172a") if col == 1 else QColor("#94a3b8" if is_dark else "#64748b")
                painter.setPen(default_color)
            painter.drawText(rect, Qt.AlignRight | Qt.AlignVCenter, item_text)

        painter.restore()


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
        self.refresh_all_status_icons()
        self.timer_status = QTimer(self)
        self.timer_status.timeout.connect(self.refresh_all_status_icons)
        self.timer_status.start(2000)

    def setup_ui(self):
        if hasattr(self.window, "sidebar"):
            self.window.sidebar.setMinimumWidth(280)
            self.window.sidebar.setMaximumWidth(340)
            if self.window.sidebar.layout():
                self.window.sidebar.layout().setContentsMargins(4, 4, 4, 4)
        if hasattr(self.window, "watchlistTitle"):
            self.window.watchlistTitle.setText("WATCHLIST")
        self.tree.setItemDelegate(WatchlistDelegate(self.tree))
        self.tree.setIconSize(QSize(0, 0))
        self.tree.setColumnCount(4)
        self.tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tree.setIndentation(4)
        self.tree.setHeaderLabels(["SYMBOL", "BID", "PIPS", "%CHG"])

        self.tree.headerItem().setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
        self.tree.headerItem().setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter)
        self.tree.headerItem().setTextAlignment(3, Qt.AlignRight | Qt.AlignVCenter)
        self.tree.header().setMinimumSectionSize(30)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Interactive)
        self.tree.header().setSectionResizeMode(1, QHeaderView.Interactive)
        self.tree.header().setSectionResizeMode(2, QHeaderView.Interactive)
        self.tree.header().setSectionResizeMode(3, QHeaderView.Interactive)
        self.tree.header().setStretchLastSection(True)
        self.tree.setColumnWidth(0, 82)
        self.tree.setColumnWidth(1, 70)
        self.tree.setColumnWidth(2, 58)
        self.tree.setColumnWidth(3, 56)

        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        event_bus.market_tick.connect(self.on_tick)

        assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
        if hasattr(self.window, "btnOpenSearch"):
            search_svg = os.path.join(assets_dir, "icon_search.svg")
            if os.path.exists(search_svg):
                self.window.btnOpenSearch.setIcon(QIcon(search_svg))
                self.window.btnOpenSearch.setText("")
                self.window.btnOpenSearch.setToolTip("Add Symbol to Watchlist")
            self.window.btnOpenSearch.clicked.connect(self.open_search_modal)
        if hasattr(self.window, "btnOpenLogin"):
            try:
                plus_svg = os.path.join(assets_dir, "icon_plus.svg")
                if os.path.exists(plus_svg):
                    self.window.btnOpenLogin.setIcon(QIcon(plus_svg))
                    self.window.btnOpenLogin.setText("")
                    self.window.btnOpenLogin.setToolTip("Add Market Symbol")
                self.window.btnOpenLogin.clicked.connect(self.open_search_modal)
            except RuntimeError:
                pass

        if hasattr(self.window, "btnCollapseWatchlist"):
            chevron_left_svg = os.path.join(assets_dir, "chevron_left.svg")
            if os.path.exists(chevron_left_svg):
                self.window.btnCollapseWatchlist.setIcon(QIcon(chevron_left_svg))
                self.window.btnCollapseWatchlist.setIconSize(QSize(12, 12))
                self.window.btnCollapseWatchlist.setText("")
                self.window.btnCollapseWatchlist.setToolTip("Toggle Watchlist Panel")
            self.window.btnCollapseWatchlist.setCursor(Qt.PointingHandCursor)
            self.window.btnCollapseWatchlist.setStyleSheet(
                "QPushButton#btnCollapseWatchlist { background: transparent; border: none; padding: 2px; } "
                "QPushButton#btnCollapseWatchlist:hover { background-color: rgba(255, 255, 255, 0.08); border-radius: 2px; }"
            )
            def _collapse():
                if hasattr(self.window, "sidebar") and hasattr(self.window, "mainSplitter"):
                    self.window.sidebar.setVisible(False)
                    self.window.watchlist_collapsed = True
                    self.window.mainSplitter.setSizes([0, 1440])
                    if hasattr(self.window, "btn_edge_wl") and self.window.btn_edge_wl:
                        self.window.btn_edge_wl.setVisible(True)
                    if hasattr(self.window, "btn_top_wl") and self.window.btn_top_wl:
                        self.window.btn_top_wl.setChecked(False)
            self.window.btnCollapseWatchlist.clicked.connect(_collapse)


    def check_account_changed(self):
        acc = mt5.account_info()
        if not acc:
            return
        if self.last_account != acc.login:
            self.last_account = acc.login

    def _sync_bot_symbols(self):
        """Đồng bộ danh sách mã theo dõi vào BotWorker ngay lập tức nếu bot đang chạy."""
        try:
            terminal = getattr(self.window, "quant_terminal", None)
            if terminal and hasattr(terminal, "bot_worker") and terminal.bot_worker:
                all_syms = self.get_all_symbols()
                if all_syms:
                    terminal.bot_worker.symbols = all_syms
        except Exception:
            pass

    def save_watchlist(self):
        symbols = self.get_all_symbols()
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(symbols, f)
        self._sync_bot_symbols()

    def load_watchlist(self):
        default_pairs = [
            ("XAUUSD", "COMMODITIES"),
            ("XAGUSD", "COMMODITIES"),
            ("BTCUSD", "CRYPTO"),
            ("ETHUSD", "CRYPTO"),
            ("EURUSD", "FOREX"),
            ("GBPUSD", "FOREX"),
            ("USDJPY", "FOREX"),
            ("US30", "INDICES"),
            ("NAS100", "INDICES"),
        ]
        cat_map = {
            "COMMODITIES": "COMMODITIES",
            "CRYPTO PERPETUALS": "CRYPTO",
            "FOREX MAJORS": "FOREX",
            "INDICES": "INDICES",
            "Indices": "INDICES",
            "Commodities": "COMMODITIES",
            "Energies": "ENERGIES",
            "Forex": "FOREX",
            "Crypto": "CRYPTO",
            "Metals": "METALS",
        }
        if not os.path.exists(self.data_file):
            for sym, cat in default_pairs:
                self.add_symbol_to_tree(sym, cat)
            return
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                symbols = json.load(f)
            if not symbols or symbols == ["XAUUSD"]:
                symbols = [p[0] for p in default_pairs]
            for sym in symbols:
                cat = "FOREX"
                if "XAU" in sym or "XAG" in sym or "OIL" in sym:
                    cat = "COMMODITIES"
                elif "BTC" in sym or "ETH" in sym or "SOL" in sym:
                    cat = "CRYPTO"
                elif "US30" in sym or "NAS" in sym or "SPX" in sym:
                    cat = "INDICES"
                info = mt5.symbol_info(sym)
                if info and info.path:
                    path = info.path.split("\\")
                    if len(path) > 0 and path[0]:
                        raw = path[0]
                        cat = cat_map.get(raw, raw)
                self.add_symbol_to_tree(sym, cat)
        except Exception:
            for sym, cat in default_pairs:
                self.add_symbol_to_tree(sym, cat)

    def open_search_modal(self):
        dialog = SymbolSearchDialog(self.window)
        if dialog.exec() == QDialog.Accepted and dialog.selected_symbol:
            self.add_symbol_to_tree(dialog.selected_symbol, dialog.selected_category)

    def add_symbol_to_tree(self, sym, cat_name):
        clean_sym = sym.split("\n")[0].strip()
        if clean_sym in self.get_all_symbols():
            return
        sym = clean_sym

        cat_map = {
            "COMMODITIES": "COMMODITIES",
            "CRYPTO PERPETUALS": "CRYPTO",
            "FOREX MAJORS": "FOREX",
            "INDICES": "INDICES",
            "Indices": "INDICES",
            "Commodities": "COMMODITIES",
            "Energies": "ENERGIES",
            "Forex": "FOREX",
            "Crypto": "CRYPTO",
            "Metals": "METALS",
        }
        cat_name = cat_map.get(cat_name, cat_name)

        cat_item = None
        for i in range(self.tree.topLevelItemCount()):
            if self.tree.topLevelItem(i).text(0) == cat_name:
                cat_item = self.tree.topLevelItem(i)
                break
        if not cat_item:
            cat_item = QTreeWidgetItem([cat_name])
            self.tree.addTopLevelItem(cat_item)
            cat_item.setFirstColumnSpanned(True)
            cat_item.setExpanded(True)

        subtitles = {
            "XAUUSD": "Gold Spot",
            "XAGUSD": "Silver Spot",
            "BTCUSD": "Bitcoin",
            "ETHUSD": "Ethereum",
            "EURUSD": "Euro / USD",
            "GBPUSD": "Pound / USD",
            "USDJPY": "USD / JPY",
            "US30": "Dow Jones",
            "NAS100": "Nasdaq 100",
        }
        default_prices = {
            "XAUUSD": ("2,680.27", "+35.2", "+1.13%"),
            "XAGUSD": ("31.845", "+12.1", "+0.84%"),
            "BTCUSD": ("63,458.0", "+1,720", "+2.78%"),
            "ETHUSD": ("2,642.10", "+88.4", "+3.12%"),
            "EURUSD": ("1.08450", "-54.2", "-0.13%"),
            "GBPUSD": ("1.29800", "+33.5", "+0.22%"),
            "USDJPY": ("144.250", "-18.0", "-0.12%"),
            "US30": ("42,120.0", "+85.0", "+0.20%"),
            "NAS100": ("20,185.4", "+108.2", "+0.54%"),
        }
        sub = subtitles.get(sym, "")
        sym_display = f"{sym}\n{sub}" if sub else sym
        if sym in default_prices:
            p, diff, pct = default_prices[sym]
            child = QTreeWidgetItem([sym_display, p, diff, pct])
        else:
            child = QTreeWidgetItem([sym_display, "-", "-", "-"])

        child.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
        child.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter)
        child.setTextAlignment(3, Qt.AlignRight | Qt.AlignVCenter)

        self.update_item_status(child, sym)

        is_dark = getattr(self.window, "is_dark_theme", True)
        green = QColor("#10b981" if is_dark else "#16a34a")
        red = QColor("#ef4444" if is_dark else "#dc2626")
        if child.text(2).startswith("+"):
            child.setForeground(2, green)
            child.setForeground(3, green)
        elif child.text(2).startswith("-"):
            child.setForeground(2, red)
            child.setForeground(3, red)

        cat_item.addChild(child)
        self.save_watchlist()

    def update_item_status(self, item, sym: str):
        """
        Cập nhật chấm trạng thái theo đúng quy tắc thực tế:
        - Chấm xanh (status_active.svg): Chỉ hiện khi mã đang có lệnh/vị thế chạy (open positions).
        - Chấm vàng (status_pending.svg): Chỉ hiện khi mã có lệnh chờ (pending orders).
        - Chấm xám (status_idle.svg): Không có lệnh nào.
        """
        clean_sym = sym.split("\n")[0].strip().upper()
        state = "IDLE"
        try:
            if mt5.terminal_info() is not None:
                positions = mt5.positions_get(symbol=clean_sym)
                if positions and len(positions) > 0:
                    state = "ACTIVE"
                else:
                    orders = mt5.orders_get(symbol=clean_sym)
                    if orders and len(orders) > 0:
                        state = "PENDING"
        except Exception:
            state = "IDLE"

        assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
        if not os.path.exists(assets_dir):
            assets_dir = os.path.join(os.path.dirname(__file__), "assets")
        if state == "ACTIVE":
            icon_file = os.path.join(assets_dir, "status_active.svg")
            item.setToolTip(0, f"{clean_sym}: Active position open")
        elif state == "PENDING":
            icon_file = os.path.join(assets_dir, "status_pending.svg")
            item.setToolTip(0, f"{clean_sym}: Pending order active")
        else:
            icon_file = os.path.join(assets_dir, "status_idle.svg")
            item.setToolTip(0, f"{clean_sym}: No open orders")

        # Zero dot icon per institutional standard
        pass

    def refresh_all_status_icons(self):
        """Quét toàn bộ MT5 và cập nhật chấm xanh (lệnh chạy), chấm vàng (lệnh chờ), chấm xám (không có lệnh)."""
        if not self.tree:
            return
        active_syms = set()
        pending_syms = set()
        try:
            if mt5.terminal_info() is not None:
                pos = mt5.positions_get()
                if pos:
                    for p in pos:
                        active_syms.add(p.symbol.upper())
                ords = mt5.orders_get()
                if ords:
                    for o in ords:
                        pending_syms.add(o.symbol.upper())
        except Exception:
            pass

        assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
        if not os.path.exists(assets_dir):
            assets_dir = os.path.join(os.path.dirname(__file__), "assets")
        icon_active = os.path.join(assets_dir, "status_active.svg")
        icon_pending = os.path.join(assets_dir, "status_pending.svg")
        icon_idle = os.path.join(assets_dir, "status_idle.svg")

        for i in range(self.tree.topLevelItemCount()):
            cat = self.tree.topLevelItem(i)
            for j in range(cat.childCount()):
                item = cat.child(j)
                sym = item.text(0).split("\n")[0].strip().upper()
                if sym in active_syms:
                    if os.path.exists(icon_active):
                        pass
                    item.setToolTip(0, f"{sym}: Active position open")
                elif sym in pending_syms:
                    if os.path.exists(icon_pending):
                        pass
                    item.setToolTip(0, f"{sym}: Pending order active")
                else:
                    if os.path.exists(icon_idle):
                        pass
                    item.setToolTip(0, f"{sym}: Flat (No orders)")

    def update_theme(self, is_dark: bool):
        self.is_dark = is_dark
        if not self.tree:
            return
        if hasattr(self.tree, "itemDelegate") and hasattr(self.tree.itemDelegate(), "set_dark"):
            self.tree.itemDelegate().set_dark(is_dark)
            self.tree.viewport().update()
        sym_color = QColor("#f8fafc" if is_dark else "#0f172a")
        price_color = QColor("#cbd5e1" if is_dark else "#334155")
        cat_color = QColor("#94a3b8" if is_dark else "#64748b")
        green = QColor("#10b981" if is_dark else "#16a34a")
        red = QColor("#ef4444" if is_dark else "#dc2626")

        for i in range(self.tree.topLevelItemCount()):
            cat = self.tree.topLevelItem(i)
            cat.setFirstColumnSpanned(True)
            cat.setForeground(0, cat_color)
            for j in range(cat.childCount()):
                child = cat.child(j)
                child.setForeground(0, sym_color)
                child.setForeground(1, price_color)
                diff = child.text(2)
                if diff.startswith("+"):
                    child.setForeground(2, green)
                    child.setForeground(3, green)
                elif diff.startswith("-"):
                    child.setForeground(2, red)
                    child.setForeground(3, red)

        if hasattr(self, "active_sym") and self.active_sym:
            self.set_active_symbol(self.active_sym)

    def set_active_symbol(self, active_sym: str):
        """Maintain persistent institutional visual active indicator on the selected symbol."""
        if not self.tree or not active_sym:
            return
        clean_target = str(active_sym).split("\n")[0].strip().upper()
        self.active_sym = clean_target
        is_dark = getattr(self, "is_dark", getattr(self.window, "is_dark_theme", True))
        active_bg = QColor("#1e293b" if is_dark else "#e2e8f0")
        active_fg = QColor("#ffffff" if is_dark else "#0f172a")
        sym_fg = QColor("#f8fafc" if is_dark else "#0f172a")

        for i in range(self.tree.topLevelItemCount()):
            cat = self.tree.topLevelItem(i)
            for j in range(cat.childCount()):
                child = cat.child(j)
                sym = child.text(0).split("\n")[0].strip().upper()
                if sym == clean_target:
                    for c in range(self.tree.columnCount()):
                        child.setBackground(c, active_bg)
                    child.setForeground(0, active_fg)
                    f = child.font(0)
                    f.setBold(True)
                    child.setFont(0, f)
                else:
                    for c in range(self.tree.columnCount()):
                        child.setBackground(c, QColor(0, 0, 0, 0))
                    child.setForeground(0, sym_fg)
                    f = child.font(0)
                    f.setBold(False)
                    child.setFont(0, f)

    def _show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item or item.childCount() > 0:
            return

        clean_sym = item.text(0).split("\n")[0].strip()
        menu = QMenu(self.tree)
        menu.setProperty("class", "context_menu")

        is_dark = getattr(self.window, "is_dark_theme", False)
        if is_dark:
            menu.setStyleSheet(
                "QMenu { background-color: #0c0e14; color: #f8fafc; border: 1px solid #272d3b; border-radius: 4px; padding: 4px; font-family: 'Segoe UI', sans-serif; font-size: 11px; } "
                "QMenu::item { padding: 6px 18px 6px 12px; border-radius: 3px; } "
                "QMenu::item:selected { background-color: #1e293b; color: #ffffff; } "
                "QMenu::separator { height: 1px; background-color: #272d3b; margin: 3px 6px; }"
            )
        else:
            menu.setStyleSheet(
                "QMenu { background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px; font-family: 'Segoe UI', sans-serif; font-size: 11px; } "
                "QMenu::item { padding: 6px 18px 6px 12px; border-radius: 3px; } "
                "QMenu::item:selected { background-color: #f1f5f9; color: #0284c7; } "
                "QMenu::separator { height: 1px; background-color: #e2e8f0; margin: 3px 6px; }"
            )

        act_open = menu.addAction(f"Open {clean_sym} Chart")
        menu.addSeparator()
        act_del = menu.addAction(f"Remove {clean_sym} from Watchlist")

        action = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if action == act_open:
            if hasattr(self.window, "draw_and_analyze"):
                self.window.draw_and_analyze(clean_sym)
        elif action == act_del:
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
                sym_raw = cat.child(j).text(0)
                symbols.append(sym_raw.split("\n")[0].strip())
        return symbols

    def on_tick(self, sym, bid, ask):
        if not self.tree:
            return
        self.check_account_changed()

        for i in range(self.tree.topLevelItemCount()):
            cat = self.tree.topLevelItem(i)
            for j in range(cat.childCount()):
                item = cat.child(j)
                item_sym = item.text(0).split("\n")[0].strip()
                if item_sym != sym:
                    continue
                info = mt5.symbol_info(sym)
                if not info:
                    continue
                item.setText(1, f"{bid:.{info.digits}f}")

                rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_D1, 1, 1)
                if rates is not None and len(rates) > 0:
                    y_close = rates[0]["close"]
                    if y_close > 0:
                        change_pts = bid - y_close
                        pct_change = (change_pts / y_close) * 100
                        prefix = "+" if change_pts > 0 else ("-" if change_pts < 0 else "")
                        sym_u = sym.upper()
                        abs_diff = abs(change_pts)
                        if "JPY" in sym_u:
                            pips_val = abs_diff * 100.0
                        elif "XAU" in sym_u or "GOLD" in sym_u:
                            pips_val = abs_diff * 10.0
                        elif "XAG" in sym_u or "SILVER" in sym_u:
                            pips_val = abs_diff * 100.0
                        elif any(c in sym_u for c in ["BTC", "ETH", "SOL", "BNB", "US30", "NAS100", "SPX500", "GER"]):
                            pips_val = abs_diff
                        elif info.digits in (4, 5):
                            pips_val = abs_diff * 10000.0
                        elif info.digits == 3:
                            pips_val = abs_diff * 100.0
                        elif info.digits == 2:
                            pips_val = abs_diff * 10.0
                        else:
                            pips_val = abs_diff * 10000.0 if abs_diff < 1.0 else abs_diff

                        if pips_val >= 1000:
                            pips_text = f"{prefix}{pips_val:,.0f}"
                        else:
                            pips_text = f"{prefix}{pips_val:.1f}"

                        item.setText(2, pips_text)
                        item.setText(3, f"{prefix}{abs(pct_change):.2f}%")
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

# Backward compatibility alias
WatchlistController = WatchlistManager
