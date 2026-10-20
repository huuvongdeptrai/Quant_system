"""
Macro Calendar Controller & Institutional Event Risk Intelligence Panel
========================================================================
Institutional Macro Workspace for VECTRA Quant System (PySide6 / Qt6)
Conforms strictly to DESIGN.md:
- Pitch-Black / Institutional Flat UI (border-radius: 0px to 3px)
- Strict Monospace & Tabular figures (Consolas, text-align: right)
- Tri-Pillar Macro Matrix: Market Risk (VIX/DXY), Monetary Stance (US10Y), Economic Growth (NFP/PMI)
- Pure Financial English terminology (No emojis, no radial gauges)
- Real-time TradingView Economic Calendar Feed & Event Risk Diagnostic Drawer
"""

import os
import datetime
from loguru import logger
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QCursor

from backend.infrastructure.data_providers.macro.calendar_engine import CalendarEngine
from backend.infrastructure.data_providers.macro.macro_regime import MacroRegimeEngine
from backend.core.event_risk_engine import COUNTRY_CURRENCY_MAP, USD_DEPENDENT_ASSETS

# Flat Country Color Badges (No Emoji flags, pure institutional text badges)
COUNTRY_COLORS = {
    "US": "#1e3a8a",
    "EU": "#14532d",
    "GB": "#7f1d1d",
    "JP": "#831843",
    "AU": "#0c4a6e",
    "CA": "#7c2d12",
    "CH": "#701a75",
    "NZ": "#134e4a",
    "CN": "#991b1b",
    "DE": "#1e293b",
}

WEEKDAYS_EN = [
    "MONDAY",
    "TUESDAY",
    "WEDNESDAY",
    "THURSDAY",
    "FRIDAY",
    "SATURDAY",
    "SUNDAY",
]


class CalendarManager:
    """Manages the dedicated Macro & Economic Calendar Workspace."""

    def __init__(self, window):
        self.window = window
        self.engine = CalendarEngine()
        self.regime_engine = MacroRegimeEngine()
        self._raw_events = []
        self._current_filter = "ALL"
        self._current_symbol = getattr(window, "current_sym", "XAUUSD")

        # Setup tabCalendar workspace if not already present
        self._setup_workspace_ui()

        # Connect window reference for cross-tab queries
        setattr(self.window, "calendar_mgr", self)
        setattr(self.window, "tableEconomicCalendar", self.table)

        # Initial fetch & load
        self.refresh_calendar()

    def _setup_workspace_ui(self):
        """Constructs the complete institutional layout on window.tabCalendar."""
        if not hasattr(self.window, "tabCalendar") or self.window.tabCalendar is None:
            self.window.tabCalendar = QWidget()
            self.window.tabCalendar.setObjectName("tabCalendar")
            if hasattr(self.window, "tabWidget"):
                self.window.tabWidget.addTab(self.window.tabCalendar, "CALENDAR")

        tab = self.window.tabCalendar
        existing_layout = tab.layout()
        if existing_layout:
            while existing_layout.count():
                item = existing_layout.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()
            self.root_layout = existing_layout
        else:
            self.root_layout = QVBoxLayout(tab)

        self.root_layout.setContentsMargins(10, 8, 10, 8)
        self.root_layout.setSpacing(8)

        # 1. TOP ZONE: Macro Regime Tri-Pillar Matrix
        self._setup_macro_regime_strip()

        # 2. MIDDLE ZONE: Wire Intel Breaking News Feed
        self._setup_wire_intel_strip()

        # 3. CONTROLS ZONE: Filters & Timezone Indicator
        self._setup_controls_bar()

        # 4. MAIN ZONE: Economic Calendar Table
        self._setup_calendar_table()

        # 5. BOTTOM ZONE: Event Risk Diagnostic Drawer
        self._setup_diagnostic_drawer()

    def _setup_macro_regime_strip(self):
        """Builds the 3-pillar macro cards: Market Risk, Monetary Policy, Economic Growth."""
        is_d = getattr(self.window, "is_dark_theme", False)
        bg = "#101524" if is_d else "#ffffff"
        border = "rgba(255, 255, 255, 0.08)" if is_d else "#e2e8f0"
        fg_muted = "#94a3b8" if is_d else "#64748b"

        self.macro_cards_frame = QFrame()
        self.macro_cards_frame.setObjectName("macroRegimeCards")
        h_lay = QHBoxLayout(self.macro_cards_frame)
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(8)

        # Card 1: Market Risk Regime (VIX / DXY)
        self.card_market = QFrame()
        self.card_market.setStyleSheet(
            f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 2px; padding: 6px; }}"
        )
        c1_lay = QVBoxLayout(self.card_market)
        c1_lay.setContentsMargins(4, 4, 4, 4)
        c1_lay.setSpacing(2)

        c1_top = QHBoxLayout()
        lbl_c1_title = QLabel("1. MARKET RISK REGIME")
        lbl_c1_title.setStyleSheet(f"color: {fg_muted}; font-size: 9.5px; font-weight: 700; letter-spacing: 0.5px; border: none;")
        self.badge_market_state = QLabel("CALCULATING...")
        self.badge_market_state.setStyleSheet("font-family: Consolas; font-size: 9.5px; font-weight: 700; padding: 1px 4px; border-radius: 2px; border: none;")
        c1_top.addWidget(lbl_c1_title)
        c1_top.addStretch()
        c1_top.addWidget(self.badge_market_state)
        c1_lay.addLayout(c1_top)

        self.lbl_market_metrics = QLabel("VIX: --  ·  DXY: --")
        self.lbl_market_metrics.setStyleSheet("font-family: Consolas; font-size: 11px; font-weight: bold; border: none;")
        c1_lay.addWidget(self.lbl_market_metrics)

        self.lbl_market_desc = QLabel("Loading live macro indicators from intermarket feed...")
        self.lbl_market_desc.setStyleSheet(f"color: {fg_muted}; font-size: 10px; border: none;")
        c1_lay.addWidget(self.lbl_market_desc)
        h_lay.addWidget(self.card_market)

        # Card 2: Monetary Policy Stance (US10Y)
        self.card_monetary = QFrame()
        self.card_monetary.setStyleSheet(
            f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 2px; padding: 6px; }}"
        )
        c2_lay = QVBoxLayout(self.card_monetary)
        c2_lay.setContentsMargins(4, 4, 4, 4)
        c2_lay.setSpacing(2)

        c2_top = QHBoxLayout()
        lbl_c2_title = QLabel("2. MONETARY POLICY STANCE")
        lbl_c2_title.setStyleSheet(f"color: {fg_muted}; font-size: 9.5px; font-weight: 700; letter-spacing: 0.5px; border: none;")
        self.badge_monetary_state = QLabel("CALCULATING...")
        self.badge_monetary_state.setStyleSheet("font-family: Consolas; font-size: 9.5px; font-weight: 700; padding: 1px 4px; border-radius: 2px; border: none;")
        c2_top.addWidget(lbl_c2_title)
        c2_top.addStretch()
        c2_top.addWidget(self.badge_monetary_state)
        c2_lay.addLayout(c2_top)

        self.lbl_monetary_metrics = QLabel("US10Y: --  ·  5D DELTA: --")
        self.lbl_monetary_metrics.setStyleSheet("font-family: Consolas; font-size: 11px; font-weight: bold; border: none;")
        c2_lay.addWidget(self.lbl_monetary_metrics)

        self.lbl_monetary_desc = QLabel("Treasury yields trajectory and central bank bias...")
        self.lbl_monetary_desc.setStyleSheet(f"color: {fg_muted}; font-size: 10px; border: none;")
        c2_lay.addWidget(self.lbl_monetary_desc)
        h_lay.addWidget(self.card_monetary)

        # Card 3: Economic Growth Stance (NFP / PMI / Unemp)
        self.card_economic = QFrame()
        self.card_economic.setStyleSheet(
            f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 2px; padding: 6px; }}"
        )
        c3_lay = QVBoxLayout(self.card_economic)
        c3_lay.setContentsMargins(4, 4, 4, 4)
        c3_lay.setSpacing(2)

        c3_top = QHBoxLayout()
        lbl_c3_title = QLabel("3. ECONOMIC GROWTH CYCLE")
        lbl_c3_title.setStyleSheet(f"color: {fg_muted}; font-size: 9.5px; font-weight: 700; letter-spacing: 0.5px; border: none;")
        self.badge_economic_state = QLabel("CALCULATING...")
        self.badge_economic_state.setStyleSheet("font-family: Consolas; font-size: 9.5px; font-weight: 700; padding: 1px 4px; border-radius: 2px; border: none;")
        c3_top.addWidget(lbl_c3_title)
        c3_top.addStretch()
        c3_top.addWidget(self.badge_economic_state)
        c3_lay.addLayout(c3_top)

        self.lbl_economic_metrics = QLabel("CYCLE: --  ·  SCORE: --")
        self.lbl_economic_metrics.setStyleSheet("font-family: Consolas; font-size: 11px; font-weight: bold; border: none;")
        c3_lay.addWidget(self.lbl_economic_metrics)

        self.lbl_economic_desc = QLabel("Employment, manufacturing PMI, and macro health scoring...")
        self.lbl_economic_desc.setStyleSheet(f"color: {fg_muted}; font-size: 10px; border: none;")
        c3_lay.addWidget(self.lbl_economic_desc)
        h_lay.addWidget(self.card_economic)

        self.root_layout.addWidget(self.macro_cards_frame)

    def _setup_wire_intel_strip(self):
        """Constructs breaking news marquee ticker."""
        is_d = getattr(self.window, "is_dark_theme", False)
        bg = "#070a12" if is_d else "#f1f5f9"
        border = "rgba(255, 255, 255, 0.08)" if is_d else "#cbd5e1"

        self.frame_wire = QFrame()
        self.frame_wire.setFixedHeight(28)
        self.frame_wire.setStyleSheet(
            f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 2px; padding: 2px 8px; }}"
        )
        w_lay = QHBoxLayout(self.frame_wire)
        w_lay.setContentsMargins(6, 0, 6, 0)
        w_lay.setSpacing(8)

        lbl_tag = QLabel("WIRE INTEL")
        lbl_tag.setStyleSheet("color: #d97706; font-family: Consolas; font-size: 10px; font-weight: bold; border: none;")
        w_lay.addWidget(lbl_tag)

        self.lbl_wire_text = QLabel("No emergency breaking macro alerts reported in the last 4 hours.")
        self.lbl_wire_text.setStyleSheet("font-size: 11px; border: none;")
        w_lay.addWidget(self.lbl_wire_text, stretch=1)

        self.lbl_wire_status = QLabel("FEED: ACTIVE")
        self.lbl_wire_status.setStyleSheet("color: #22c55e; font-family: Consolas; font-size: 9.5px; font-weight: bold; border: none;")
        w_lay.addWidget(self.lbl_wire_status)

        self.root_layout.addWidget(self.frame_wire)

    def _setup_controls_bar(self):
        """Constructs filter buttons bar and timezone indicator."""
        is_d = getattr(self.window, "is_dark_theme", False)
        fg_muted = "#94a3b8" if is_d else "#64748b"

        ctrl_frame = QFrame()
        ctrl_lay = QHBoxLayout(ctrl_frame)
        ctrl_lay.setContentsMargins(0, 0, 0, 0)
        ctrl_lay.setSpacing(6)

        lbl_flt = QLabel("FILTER:")
        lbl_flt.setStyleSheet(f"color: {fg_muted}; font-size: 10px; font-weight: bold;")
        ctrl_lay.addWidget(lbl_flt)

        self.filter_buttons = {}
        filters_spec = [
            ("ALL", "ALL RELEASES"),
            ("HIGH", "HIGH IMPACT ONLY (TIER 2)"),
            ("USD", "USD / GOLD DIRECT"),
            ("CURRENT", f"SYMBOL: {self._current_symbol}"),
        ]

        for key, text in filters_spec:
            btn = QPushButton(text)
            btn.setFixedHeight(24)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setCheckable(True)
            def _make_flt_handler(k):
                return lambda: self.set_filter(k)
            btn.clicked.connect(_make_flt_handler(key))
            ctrl_lay.addWidget(btn)
            self.filter_buttons[key] = btn

        self.filter_buttons["ALL"].setChecked(True)

        ctrl_lay.addStretch(1)

        # Timezone label
        lbl_tz = QLabel("TIMEZONE: UTC+7 (HANOI / HO CHI MINH)")
        lbl_tz.setStyleSheet(f"color: {fg_muted}; font-family: Consolas; font-size: 10px; font-weight: 600;")
        ctrl_lay.addWidget(lbl_tz)

        # Refresh button
        self.btn_refresh = QPushButton("REFRESH FEED")
        self.btn_refresh.setFixedHeight(24)
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setStyleSheet(
            "QPushButton { background-color: #0284c7; color: #ffffff; font-family: Consolas; font-size: 10.5px; font-weight: bold; border-radius: 2px; padding: 0 10px; } "
            "QPushButton:hover { background-color: #0369a1; }"
        )
        self.btn_refresh.clicked.connect(self.refresh_calendar)
        ctrl_lay.addWidget(self.btn_refresh)

        self.root_layout.addWidget(ctrl_frame)

    def _setup_calendar_table(self):
        """Constructs the high-density economic calendar table."""
        self.table = QTableWidget()
        self.table.setObjectName("tableEconomicCalendar")
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "TIME (VN)",
            "CURRENCY",
            "IMPACT",
            "EVENT RELEASE",
            "ACTUAL",
            "FORECAST",
            "PREVIOUS",
        ])

        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed)
        hdr.setSectionResizeMode(2, QHeaderView.Fixed)
        hdr.setSectionResizeMode(3, QHeaderView.Stretch)
        hdr.setSectionResizeMode(4, QHeaderView.Fixed)
        hdr.setSectionResizeMode(5, QHeaderView.Fixed)
        hdr.setSectionResizeMode(6, QHeaderView.Fixed)

        self.table.setColumnWidth(0, 85)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(4, 95)
        self.table.setColumnWidth(5, 95)
        self.table.setColumnWidth(6, 95)

        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        self.root_layout.addWidget(self.table, stretch=1)

    def _setup_diagnostic_drawer(self):
        """Constructs bottom event risk inspection card."""
        is_d = getattr(self.window, "is_dark_theme", False)
        bg = "#101524" if is_d else "#ffffff"
        border = "rgba(255, 255, 255, 0.08)" if is_d else "#e2e8f0"
        fg_muted = "#94a3b8" if is_d else "#64748b"

        self.drawer_frame = QFrame()
        self.drawer_frame.setObjectName("eventRiskDrawer")
        self.drawer_frame.setStyleSheet(
            f"QFrame#eventRiskDrawer {{ background-color: {bg}; border: 1px solid {border}; border-radius: 2px; padding: 6px; }}"
        )
        d_lay = QVBoxLayout(self.drawer_frame)
        d_lay.setContentsMargins(6, 6, 6, 6)
        d_lay.setSpacing(4)

        top_row = QHBoxLayout()
        self.lbl_drawer_tag = QLabel("EVENT RISK DIAGNOSTICS")
        self.lbl_drawer_tag.setStyleSheet("color: #0284c7; font-family: Consolas; font-size: 10px; font-weight: bold; border: none;")
        self.lbl_drawer_title = QLabel("Select an event release above to inspect quantitative defense parameters.")
        self.lbl_drawer_title.setStyleSheet("font-size: 11px; font-weight: bold; border: none;")
        self.lbl_drawer_time = QLabel("")
        self.lbl_drawer_time.setStyleSheet("font-family: Consolas; font-size: 11px; font-weight: bold; border: none;")

        top_row.addWidget(self.lbl_drawer_tag)
        top_row.addWidget(self.lbl_drawer_title, stretch=1)
        top_row.addWidget(self.lbl_drawer_time)
        d_lay.addLayout(top_row)

        cols_row = QHBoxLayout()
        cols_row.setSpacing(12)

        # Col 1: Asset Mapping
        c1 = QVBoxLayout()
        lbl_c1 = QLabel("AFFECTED SYMBOLS (AUTO-MAPPING):")
        lbl_c1.setStyleSheet(f"color: {fg_muted}; font-size: 9.5px; font-weight: bold; border: none;")
        self.lbl_drawer_assets = QLabel("None selected")
        self.lbl_drawer_assets.setStyleSheet("font-family: Consolas; font-size: 11px; font-weight: 600; border: none;")
        c1.addWidget(lbl_c1)
        c1.addWidget(self.lbl_drawer_assets)
        cols_row.addLayout(c1, stretch=1)

        # Col 2: Defense Mechanism
        c2 = QVBoxLayout()
        lbl_c2 = QLabel("ACTIVE DEFENSE MECHANISM (EVENTRISKENGINE):")
        lbl_c2.setStyleSheet(f"color: {fg_muted}; font-size: 9.5px; font-weight: bold; border: none;")
        self.lbl_drawer_defense = QLabel("T-15m: Lãi >= 1.5R dời BE · Lãi 0.5-1.5R chốt 50% & BE")
        self.lbl_drawer_defense.setStyleSheet("font-family: Consolas; font-size: 11px; font-weight: 600; border: none;")
        c2.addWidget(lbl_c2)
        c2.addWidget(self.lbl_drawer_defense)
        cols_row.addLayout(c2, stretch=2)

        # Col 3: Order Execution Lock Status
        c3 = QVBoxLayout()
        lbl_c3 = QLabel("EXECUTION LOCKOUT STATUS:")
        lbl_c3.setStyleSheet(f"color: {fg_muted}; font-size: 9.5px; font-weight: bold; border: none;")
        self.lbl_drawer_status = QLabel("CLEAR")
        self.lbl_drawer_status.setStyleSheet("color: #22c55e; font-family: Consolas; font-size: 11px; font-weight: bold; border: none;")
        c3.addWidget(lbl_c3)
        c3.addWidget(self.lbl_drawer_status)
        cols_row.addLayout(c3, stretch=1)

        d_lay.addLayout(cols_row)
        self.root_layout.addWidget(self.drawer_frame)

    def set_filter(self, filter_key):
        """Applies active filter mode (ALL, HIGH, USD, CURRENT)."""
        self._current_filter = filter_key
        is_d = getattr(self.window, "is_dark_theme", False)
        self._update_filter_button_styles(is_d)
        self.load_calendar()

    def set_current_symbol(self, sym: str):
        """Updates current symbol context when user selects a different instrument."""
        if not sym:
            return
        self._current_symbol = sym.upper().split(".")[0]
        if "CURRENT" in self.filter_buttons:
            self.filter_buttons["CURRENT"].setText(f"SYMBOL: {self._current_symbol}")
        if self._current_filter == "CURRENT":
            self.load_calendar()

    def _update_filter_button_styles(self, is_dark):
        """Styles filter buttons according to active state and theme."""
        act_bg = "#0284c7"
        act_fg = "#ffffff"
        inact_bg = "#101524" if is_dark else "#f1f5f9"
        inact_fg = "#94a3b8" if is_dark else "#475569"
        border_col = "rgba(255, 255, 255, 0.08)" if is_dark else "#cbd5e1"

        for k, btn in self.filter_buttons.items():
            is_active = (k == self._current_filter)
            btn.setChecked(is_active)
            if is_active:
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: {act_bg}; color: {act_fg}; font-family: Consolas; "
                    "font-size: 10px; font-weight: bold; border-radius: 2px; padding: 0 8px; border: none; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: {inact_bg}; color: {inact_fg}; font-family: Consolas; "
                    f"font-size: 10px; font-weight: 500; border-radius: 2px; padding: 0 8px; border: 1px solid {border_col}; }} "
                    f"QPushButton:hover {{ background-color: {'#161d31' if is_dark else '#e2e8f0'}; color: {'#f8fafc' if is_dark else '#0f172a'}; }}"
                )

    def refresh_calendar(self):
        """Fetches calendar events and macro regime telemetry."""
        try:
            self._raw_events = self.engine.fetch_events()
        except Exception as e:
            logger.warning(f"[MacroCalendar] Calendar fetch error: {e}")
            self._raw_events = []

        try:
            report = self.regime_engine.generate_macro_report()
            self._apply_macro_report(report)
        except Exception as e:
            logger.warning(f"[MacroCalendar] Macro report error: {e}")

        self.load_calendar()

    def _apply_macro_report(self, report: dict):
        """Renders the tri-pillar macro report onto KPI cards."""
        m_state = report.get("Market", {})
        m_name = m_state.get("state", "UNKNOWN").upper()
        vix = m_state.get("vix", 0)
        dxy = m_state.get("dxy", 0)
        dxy_trend = m_state.get("dxy_trend", "--")
        
        is_risk_off = ("OFF" in m_name)
        self.badge_market_state.setText(m_name)
        self.badge_market_state.setStyleSheet(
            f"font-family: Consolas; font-size: 9.5px; font-weight: 700; padding: 1px 4px; border-radius: 2px; "
            f"background-color: {'#ef4444' if is_risk_off else '#22c55e'}; color: #ffffff;"
        )
        self.lbl_market_metrics.setText(f"VIX: {vix:.2f}  ·  DXY: {dxy:.2f} {dxy_trend}")
        self.lbl_market_desc.setText(m_state.get("reason", "Intermarket liquidity posture"))

        # Monetary
        mon_state = report.get("Monetary", {})
        mon_name = mon_state.get("state", "UNKNOWN")
        us10y = mon_state.get("us10y", 0)
        d5 = mon_state.get("delta_5d", 0)
        sign = "+" if d5 >= 0 else ""

        is_hawk = ("Hawkish" in mon_name)
        self.badge_monetary_state.setText(mon_name[:15].upper())
        self.badge_monetary_state.setStyleSheet(
            f"font-family: Consolas; font-size: 9.5px; font-weight: 700; padding: 1px 4px; border-radius: 2px; "
            f"background-color: {'#ef4444' if is_hawk else '#0284c7'}; color: #ffffff;"
        )
        self.lbl_monetary_metrics.setText(f"US10Y: {us10y:.3f}%  ·  5D: {sign}{d5:.3f}%")
        self.lbl_monetary_desc.setText(mon_state.get("reason", "Bond yields and discount rates"))

        # Economic
        eco_state = report.get("Economic", {})
        eco_name = eco_state.get("state", "UNKNOWN")
        is_rec = ("Recession" in eco_name)
        self.badge_economic_state.setText(eco_name[:15].upper())
        self.badge_economic_state.setStyleSheet(
            f"font-family: Consolas; font-size: 9.5px; font-weight: 700; padding: 1px 4px; border-radius: 2px; "
            f"background-color: {'#ef4444' if is_rec else '#22c55e'}; color: #ffffff;"
        )
        self.lbl_economic_metrics.setText(f"CYCLE: {eco_name.split(' ')[0]}  ·  {eco_state.get('reason', '')}")
        self.lbl_economic_desc.setText("Scoring across NFP, PMI, and unemployment indices")

        # Telegram
        wire_msg = report.get("Telegram_News", "")
        if wire_msg:
            self.lbl_wire_text.setText(wire_msg)

    def load_calendar(self):
        """Filters and populates the table."""
        t = self.table
        t.setRowCount(0)
        events = list(self._raw_events)

        # Apply active filter
        if self._current_filter == "HIGH":
            events = [e for e in events if e.get("impact", 0) == 2]
        elif self._current_filter == "USD":
            events = [e for e in events if e.get("country", "").upper() == "US"]
        elif self._current_filter == "CURRENT":
            # Match current symbol dependencies
            curr = self._current_symbol.upper()
            filtered = []
            for e in events:
                cntry = e.get("country", "").upper()
                title = e.get("title", "")
                mapped_cur = COUNTRY_CURRENCY_MAP.get(cntry, cntry)
                if mapped_cur and mapped_cur in curr:
                    filtered.append(e)
                elif cntry == "US":
                    for dep in USD_DEPENDENT_ASSETS:
                        if curr.startswith(dep) or dep in curr:
                            filtered.append(e)
                            break
            events = filtered

        current_date = None
        today = datetime.date.today()
        today_row = -1

        for e in events:
            sort_key = e.get("sort_key", 0.0)
            try:
                event_date = datetime.date.fromtimestamp(sort_key)
            except Exception:
                event_date = today

            if event_date != current_date:
                current_date = event_date
                if event_date == today:
                    today_row = t.rowCount()
                self._insert_date_separator(t.rowCount(), event_date)

            row = t.rowCount()
            t.insertRow(row)
            t.setRowHeight(row, 28)

            # Col 0: TIME (VN)
            time_str = e.get("time", "").split(" ")[-1]
            t.setCellWidget(row, 0, self._cell(time_str, bold=True, font="Consolas"))

            # Col 1: CURRENCY BADGE
            t.setCellWidget(row, 1, self._country_badge(e.get("country", "US")))

            # Col 2: IMPACT
            t.setCellWidget(row, 2, self._impact_badge(e.get("impact", 0)))

            # Col 3: EVENT RELEASE
            lbl_title = QLabel(f" {e.get('title', '')}")
            lbl_title.setStyleSheet("font-size: 11px; font-weight: 500;")
            lbl_title.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            t.setCellWidget(row, 3, lbl_title)

            # Actual vs Forecast
            actual = str(e.get("actual", "-")) if e.get("actual") not in ("None", "", None) else "-"
            forecast = str(e.get("forecast", "-")) if e.get("forecast") not in ("None", "", None) else "-"
            previous = str(e.get("previous", "-")) if e.get("previous") not in ("None", "", None) else "-"

            act_col = "#94a3b8"
            if actual != "-" and forecast != "-":
                try:
                    act_col = "#22c55e" if float(actual.replace("%", "")) >= float(forecast.replace("%", "")) else "#ef4444"
                except Exception:
                    pass

            t.setCellWidget(row, 4, self._cell(actual, color=act_col, bold=True, font="Consolas", align=Qt.AlignRight))
            t.setCellWidget(row, 5, self._cell(forecast, font="Consolas", align=Qt.AlignRight))
            t.setCellWidget(row, 6, self._cell(previous, font="Consolas", align=Qt.AlignRight))

            # Store event dict on row item 0
            item = QTableWidgetItem()
            item.setData(Qt.UserRole, e)
            t.setItem(row, 0, item)

        if today_row != -1:
            item = t.item(today_row, 0)
            if item:
                t.scrollToItem(item, QAbstractItemView.PositionAtTop)

    def _insert_date_separator(self, row, date_obj):
        """Renders an institutional date bar across all columns."""
        t = self.table
        t.insertRow(row)
        t.setSpan(row, 0, 1, t.columnCount())

        today = datetime.date.today()
        is_today = (date_obj == today)

        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(8)
        lay.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        thu = WEEKDAYS_EN[date_obj.weekday()]
        date_str = date_obj.strftime("%d/%m/%Y")
        lbl_date = QLabel(f"{thu}  ·  {date_str}")
        lbl_date.setStyleSheet("font-family: Consolas; font-size: 11px; font-weight: bold; color: #38bdf8;")
        lay.addWidget(lbl_date)

        if is_today:
            lbl_badge = QLabel("TODAY")
            lbl_badge.setStyleSheet(
                "background-color: #22c55e; color: #ffffff; border-radius: 2px; padding: 1px 6px; "
                "font-family: Consolas; font-size: 9.5px; font-weight: bold;"
            )
            lay.addWidget(lbl_badge)

        t.setCellWidget(row, 0, w)
        t.setRowHeight(row, 26)

        # Background color for date separator
        is_d = getattr(self.window, "is_dark_theme", False)
        bg = "#161d31" if is_d else "#e2e8f0"
        for col in range(t.columnCount()):
            item = QTableWidgetItem()
            item.setBackground(QColor(bg))
            item.setFlags(Qt.NoItemFlags)
            t.setItem(row, col, item)

    def _country_badge(self, country: str):
        col = COUNTRY_COLORS.get(country.upper(), "#334155")
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(4, 2, 4, 2)
        lbl = QLabel(country.upper())
        lbl.setStyleSheet(
            f"background-color: {col}; color: #ffffff; font-family: Consolas; font-size: 10px; "
            "font-weight: bold; border-radius: 2px; padding: 1px 6px;"
        )
        lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(lbl, alignment=Qt.AlignCenter)
        return w

    def _impact_badge(self, impact: int):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(4, 2, 4, 2)

        if impact == 2:
            lbl = QLabel("HIGH")
            lbl.setStyleSheet("background-color: #ef4444; color: #ffffff; font-family: Consolas; font-size: 9.5px; font-weight: bold; border-radius: 2px; padding: 1px 6px;")
        elif impact == 1:
            lbl = QLabel("MED")
            lbl.setStyleSheet("background-color: #f59e0b; color: #000000; font-family: Consolas; font-size: 9.5px; font-weight: bold; border-radius: 2px; padding: 1px 6px;")
        else:
            lbl = QLabel("LOW")
            lbl.setStyleSheet("background-color: #334155; color: #94a3b8; font-family: Consolas; font-size: 9.5px; font-weight: 500; border-radius: 2px; padding: 1px 6px;")

        lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(lbl, alignment=Qt.AlignCenter)
        return w

    def _cell(self, text, color=None, bold=False, font="Segoe UI", align=Qt.AlignCenter):
        val = str(text) if text not in ("None", "none", "", None) else "-"
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(6, 0, 6, 0)
        lbl = QLabel(val)

        is_d = getattr(self.window, "is_dark_theme", False)
        if not color:
            color = "#f8fafc" if is_d else "#0f172a"

        weight = "bold" if bold else "normal"
        lbl.setStyleSheet(f"color: {color}; font-family: '{font}', monospace; font-size: 11px; font-weight: {weight}; border: none;")
        lbl.setAlignment(align | Qt.AlignVCenter)
        lay.addWidget(lbl)
        return w

    def _on_table_selection_changed(self):
        """Updates diagnostic drawer when an event row is clicked."""
        selected_rows = self.table.selectedItems()
        if not selected_rows:
            return

        row = selected_rows[0].row()
        item = self.table.item(row, 0)
        if not item:
            return

        event = item.data(Qt.UserRole)
        if not event:
            return

        cntry = event.get("country", "US")
        title = event.get("title", "")
        time_str = event.get("time", "")
        impact = event.get("impact", 0)

        self.lbl_drawer_title.setText(f"{cntry} · {title}")
        self.lbl_drawer_time.setText(f"SCHEDULED: {time_str} VN (UTC+7)")

        # Determine impacted assets
        affected = []
        cur = COUNTRY_CURRENCY_MAP.get(cntry, cntry)
        if cur:
            affected.append(f"{cur} FX PAIRS")
        if cntry.upper() == "US":
            affected.extend(["XAUUSD (GOLD)", "XAGUSD", "US30", "NAS100", "BTCUSD"])

        self.lbl_drawer_assets.setText(", ".join(affected) if affected else f"{cntry} DOMESTIC")

        # Defense status
        if impact == 2:
            self.lbl_drawer_defense.setText("T-15m: Lãi >= 1.5R Auto-BE · Lãi 0.5-1.5R Chốt 50% & Lock BE")
            self.lbl_drawer_status.setText("BLACKOUT WINDOW ±15M ARMED")
            self.lbl_drawer_status.setStyleSheet("color: #ef4444; font-family: Consolas; font-size: 11px; font-weight: bold; border: none;")
        else:
            self.lbl_drawer_defense.setText("Minor Impact: No automated trade halt or position modification required")
            self.lbl_drawer_status.setText("CLEAR")
            self.lbl_drawer_status.setStyleSheet("color: #22c55e; font-family: Consolas; font-size: 11px; font-weight: bold; border: none;")

    def update_theme(self, is_dark: bool):
        """Applies theme colors to the entire workspace."""
        self._update_filter_button_styles(is_dark)
        bg = "#101524" if is_dark else "#ffffff"
        border = "rgba(255, 255, 255, 0.08)" if is_dark else "#e2e8f0"

        for card in [self.card_market, self.card_monetary, self.card_economic]:
            card.setStyleSheet(
                f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 2px; padding: 6px; }}"
            )

        if hasattr(self, "drawer_frame"):
            self.drawer_frame.setStyleSheet(
                f"QFrame#eventRiskDrawer {{ background-color: {bg}; border: 1px solid {border}; border-radius: 2px; padding: 6px; }}"
            )


# Backward compatibility alias
MacroCalendarController = CalendarManager
