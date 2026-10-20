"""
Macro Calendar Controller & Institutional Event Risk Defense Desk
===================================================================
Institutional Macro Workspace for VECTRA Quant System (PySide6 / Qt6)
Conforms strictly to DESIGN.md:
- Pitch-Black / Institutional Flat UI (border-radius: 0px to 3px)
- Strict Monospace & Tabular figures (Consolas, text-align: right)
- 4-Pillar Macro Matrix: Market Risk, Monetary Policy, Growth Cycle, Target Asset Macro Confluence
- 70:30 Golden Ratio Splitter: High-Density Calendar (Left) + Semi-Auto Defense Desk (Right)
- Real-time 1s Countdown Timer to upcoming tier-2 news release
- Pure Financial English terminology (Zero verbose fluff, zero emojis)
"""

import os
import time
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
    QSplitter,
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
    """Manages the 70:30 Macro & Economic Calendar Defense Desk Workspace."""

    def __init__(self, window):
        self.window = window
        self.engine = CalendarEngine()
        self.regime_engine = MacroRegimeEngine()
        self._raw_events = []
        self._current_filter = "ALL"
        self._current_symbol = getattr(window, "current_sym", "XAUUSD")
        self._selected_event = None
        self._override_active = False

        # Setup tabCalendar workspace
        self._setup_workspace_ui()

        # Connect window reference for cross-tab queries
        setattr(self.window, "calendar_mgr", self)
        setattr(self.window, "tableEconomicCalendar", self.table)

        # 1-second Countdown & Real-time Telemetry Timer
        self._clock_timer = QTimer(self.window)
        self._clock_timer.timeout.connect(self._on_clock_tick)
        self._clock_timer.start(1000)

        # Initial fetch & load
        self.refresh_calendar()

    def _setup_workspace_ui(self):
        """Constructs the 70:30 split institutional layout on window.tabCalendar."""
        if not hasattr(self.window, "tabCalendar") or self.window.tabCalendar is None:
            self.window.tabCalendar = QWidget()
            self.window.tabCalendar.setObjectName("tabCalendar")
            if hasattr(self.window, "tabWidget"):
                self.window.tabWidget.addTab(self.window.tabCalendar, "CALENDAR")

        tab = self.window.tabCalendar
        is_d = getattr(self.window, "is_dark_theme", False)
        tab_bg = "#070a12" if is_d else "#f8fafc"
        tab.setAutoFillBackground(True)
        tab.setStyleSheet(f"QWidget#tabCalendar {{ background-color: {tab_bg}; }}")

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

        self.root_layout.setContentsMargins(8, 6, 8, 6)
        self.root_layout.setSpacing(6)

        # 1. ROW 1: 4-Pillar Macro Matrix (Clean, no verbose description fluff)
        self._setup_macro_matrix_row()

        # 2. ROW 2: Compact Controls & Wire Intel Action Strip
        self._setup_controls_wire_row()

        # 3. ROW 3: 70:30 Main Splitter (Calendar Left + Defense Desk Right)
        self._setup_main_splitter()

    def _setup_macro_matrix_row(self):
        """Builds 4 austere macro cards: Market, Monetary, Growth, Target Asset Confluence."""
        is_d = getattr(self.window, "is_dark_theme", False)
        bg = "#101524" if is_d else "#ffffff"
        border = "rgba(255, 255, 255, 0.08)" if is_d else "#e2e8f0"
        fg_muted = "#94a3b8" if is_d else "#64748b"

        self.cards_frame = QFrame()
        self.cards_frame.setFixedHeight(54)
        h_lay = QHBoxLayout(self.cards_frame)
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(6)

        # Helper to create compact card
        def _make_card(title_text):
            card = QFrame()
            card.setStyleSheet(
                f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 2px; padding: 4px 8px; }}"
            )
            lay = QVBoxLayout(card)
            lay.setContentsMargins(2, 2, 2, 2)
            lay.setSpacing(2)

            top = QHBoxLayout()
            lbl_title = QLabel(title_text)
            lbl_title.setStyleSheet(f"color: {fg_muted}; font-size: 9px; font-weight: 700; letter-spacing: 0.5px; border: none;")
            badge = QLabel("CALCULATING")
            badge.setStyleSheet("font-family: Consolas; font-size: 9px; font-weight: 700; padding: 1px 5px; border-radius: 2px; border: none;")
            top.addWidget(lbl_title)
            top.addStretch()
            top.addWidget(badge)
            lay.addLayout(top)

            lbl_metrics = QLabel("--")
            lbl_metrics.setStyleSheet("font-family: Consolas; font-size: 11px; font-weight: bold; border: none;")
            lay.addWidget(lbl_metrics)
            return card, badge, lbl_metrics

        # Card 1: Market Risk Regime
        self.card_market, self.badge_market_state, self.lbl_market_metrics = _make_card("1. MARKET RISK REGIME")
        h_lay.addWidget(self.card_market)

        # Card 2: Monetary Stance
        self.card_monetary, self.badge_monetary_state, self.lbl_monetary_metrics = _make_card("2. MONETARY STANCE")
        h_lay.addWidget(self.card_monetary)

        # Card 3: Growth Cycle
        self.card_economic, self.badge_economic_state, self.lbl_economic_metrics = _make_card("3. ECONOMIC GROWTH")
        h_lay.addWidget(self.card_economic)

        # Card 4: Target Asset Macro Confluence (Synthesizes net bias for main trading asset)
        self.card_confluence, self.badge_confluence_state, self.lbl_confluence_metrics = _make_card(f"4. TARGET BIAS ({self._current_symbol})")
        h_lay.addWidget(self.card_confluence)

        self.root_layout.addWidget(self.cards_frame)

    def _setup_controls_wire_row(self):
        """Unified compact row merging filters, wire alert status, and sync indicator."""
        is_d = getattr(self.window, "is_dark_theme", False)
        bg = "#070a12" if is_d else "#f1f5f9"
        border = "rgba(255, 255, 255, 0.08)" if is_d else "#cbd5e1"
        fg_muted = "#94a3b8" if is_d else "#64748b"

        self.frame_ctrl = QFrame()
        self.frame_ctrl.setFixedHeight(28)
        self.frame_ctrl.setStyleSheet(
            f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 2px; padding: 2px 6px; }}"
        )
        c_lay = QHBoxLayout(self.frame_ctrl)
        c_lay.setContentsMargins(4, 0, 4, 0)
        c_lay.setSpacing(6)

        # Filter buttons
        lbl_flt = QLabel("FILTER:")
        lbl_flt.setStyleSheet(f"color: {fg_muted}; font-size: 9.5px; font-weight: bold; border: none;")
        c_lay.addWidget(lbl_flt)

        self.filter_buttons = {}
        filters_spec = [
            ("ALL", "ALL RELEASES"),
            ("HIGH", "HIGH IMPACT (TIER 2)"),
            ("TARGET", f"TARGET: {self._current_symbol}"),
        ]

        for key, text in filters_spec:
            btn = QPushButton(text)
            btn.setFixedHeight(20)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setCheckable(True)
            def _make_flt_handler(k):
                return lambda: self.set_filter(k)
            btn.clicked.connect(_make_flt_handler(key))
            c_lay.addWidget(btn)
            self.filter_buttons[key] = btn

        self.filter_buttons["ALL"].setChecked(True)

        sep1 = QFrame()
        sep1.setFixedWidth(1)
        sep1.setFixedHeight(14)
        sep1.setStyleSheet(f"background-color: {border}; border: none;")
        c_lay.addWidget(sep1)

        # Wire Alert Status (Compact, non-intrusive)
        self.lbl_wire_tag = QLabel("WIRE:")
        self.lbl_wire_tag.setStyleSheet("color: #22c55e; font-family: Consolas; font-size: 9.5px; font-weight: bold; border: none;")
        c_lay.addWidget(self.lbl_wire_tag)

        self.lbl_wire_text = QLabel("NORMAL · NO BREAKING INTEL")
        self.lbl_wire_text.setStyleSheet(f"color: {fg_muted}; font-size: 10px; font-family: 'Segoe UI', sans-serif; border: none;")
        c_lay.addWidget(self.lbl_wire_text, stretch=1)

        # Sync indicator & subtle refresh
        self.lbl_sync_status = QLabel("SYNCED: LIVE")
        self.lbl_sync_status.setStyleSheet(f"color: {fg_muted}; font-family: Consolas; font-size: 9.5px; border: none;")
        c_lay.addWidget(self.lbl_sync_status)

        self.btn_refresh = QPushButton("↻")
        self.btn_refresh.setFixedSize(20, 20)
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setToolTip("Refresh Economic Calendar & Intermarket Feed")
        self.btn_refresh.setStyleSheet(
            "QPushButton { background-color: transparent; color: #0284c7; font-family: Consolas; font-size: 13px; font-weight: bold; border: none; } "
            "QPushButton:hover { background-color: rgba(2, 132, 199, 0.15); border-radius: 2px; }"
        )
        self.btn_refresh.clicked.connect(self.refresh_calendar)
        c_lay.addWidget(self.btn_refresh)

        self.root_layout.addWidget(self.frame_ctrl)

    def _setup_main_splitter(self):
        """Constructs 70:30 horizontal split: Economic Calendar on Left + Defense Desk on Right."""
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setObjectName("calendarSplitter")
        self.main_splitter.setHandleWidth(4)

        # --- LEFT PANE (70%): High-Density Calendar Table ---
        self.left_container = QWidget()
        l_lay = QVBoxLayout(self.left_container)
        l_lay.setContentsMargins(0, 0, 0, 0)
        l_lay.setSpacing(0)

        self.table = QTableWidget()
        self.table.setObjectName("tableEconomicCalendar")
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "TIME (UTC+7)",
            "CURR",
            "IMPACT",
            "EVENT RELEASE",
            "ACTUAL",
            "FORECAST",
            "PREVIOUS",
            "SURPRISE",
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
        hdr.setSectionResizeMode(7, QHeaderView.Fixed)

        self.table.setColumnWidth(0, 78)
        self.table.setColumnWidth(1, 55)
        self.table.setColumnWidth(2, 72)
        self.table.setColumnWidth(4, 75)
        self.table.setColumnWidth(5, 75)
        self.table.setColumnWidth(6, 75)
        self.table.setColumnWidth(7, 85)

        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        l_lay.addWidget(self.table)
        self.main_splitter.addWidget(self.left_container)

        # --- RIGHT PANE (30%): Event Risk & Semi-Auto Defense Desk ---
        self.right_container = QWidget()
        self._setup_defense_desk_ui()
        self.main_splitter.addWidget(self.right_container)

        # 70:30 Split Proportions
        self.main_splitter.setStretchFactor(0, 7)
        self.main_splitter.setStretchFactor(1, 3)
        self.main_splitter.setSizes([950, 380])

        self.root_layout.addWidget(self.main_splitter, stretch=1)

    def _setup_defense_desk_ui(self):
        """Constructs right-hand semi-auto defense desk and countdown monitor."""
        is_d = getattr(self.window, "is_dark_theme", False)
        bg = "#101524" if is_d else "#ffffff"
        border = "rgba(255, 255, 255, 0.08)" if is_d else "#e2e8f0"
        fg_muted = "#94a3b8" if is_d else "#64748b"

        r_lay = QVBoxLayout(self.right_container)
        r_lay.setContentsMargins(0, 0, 0, 0)
        r_lay.setSpacing(6)

        # Section 1: Upcoming Event Countdown Card
        self.frame_countdown = QFrame()
        self.frame_countdown.setStyleSheet(
            f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 2px; padding: 8px; }}"
        )
        c_lay = QVBoxLayout(self.frame_countdown)
        c_lay.setContentsMargins(6, 6, 6, 6)
        c_lay.setSpacing(4)

        lbl_c_tag = QLabel("NEXT HIGH-IMPACT RELEASE")
        lbl_c_tag.setStyleSheet("color: #0284c7; font-family: Consolas; font-size: 9.5px; font-weight: bold; border: none;")
        c_lay.addWidget(lbl_c_tag)

        self.lbl_next_event_title = QLabel("US · CORE CPI MOM")
        self.lbl_next_event_title.setStyleSheet("font-size: 12px; font-weight: bold; border: none;")
        c_lay.addWidget(self.lbl_next_event_title)

        self.lbl_next_event_time = QLabel("SCHEDULED: 19:30 VN (UTC+7)")
        self.lbl_next_event_time.setStyleSheet(f"color: {fg_muted}; font-family: Consolas; font-size: 10px; border: none;")
        c_lay.addWidget(self.lbl_next_event_time)

        # Huge Monospace Countdown
        self.lbl_countdown_val = QLabel("T - 00:00:00")
        self.lbl_countdown_val.setStyleSheet(
            "color: #ef4444; font-family: 'Consolas', monospace; font-size: 22px; font-weight: 900; letter-spacing: 1px; border: none; margin: 4px 0;"
        )
        c_lay.addWidget(self.lbl_countdown_val)

        self.lbl_lockout_status = QLabel("STATUS: MONITORING · WINDOW CLEAR")
        self.lbl_lockout_status.setStyleSheet(
            "color: #22c55e; font-family: Consolas; font-size: 10.5px; font-weight: bold; border: none;"
        )
        c_lay.addWidget(self.lbl_lockout_status)
        r_lay.addWidget(self.frame_countdown)

        # Section 2: Quantitative Defense Protocol (T-15m Execution Rules)
        self.frame_protocol = QFrame()
        self.frame_protocol.setStyleSheet(
            f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 2px; padding: 8px; }}"
        )
        p_lay = QVBoxLayout(self.frame_protocol)
        p_lay.setContentsMargins(6, 6, 6, 6)
        p_lay.setSpacing(4)

        lbl_p_tag = QLabel("QUANTITATIVE DEFENSE PROTOCOL")
        lbl_p_tag.setStyleSheet(f"color: {fg_muted}; font-size: 9.5px; font-weight: 700; letter-spacing: 0.5px; border: none;")
        p_lay.addWidget(lbl_p_tag)

        lbl_assets_hdr = QLabel("AFFECTED ASSETS:")
        lbl_assets_hdr.setStyleSheet(f"color: {fg_muted}; font-size: 9px; font-weight: bold; border: none;")
        self.lbl_desk_assets = QLabel("USD PAIRS, XAUUSD (GOLD), US30, NAS100")
        self.lbl_desk_assets.setStyleSheet("font-family: Consolas; font-size: 10px; font-weight: bold; border: none;")
        p_lay.addWidget(lbl_assets_hdr)
        p_lay.addWidget(self.lbl_desk_assets)

        lbl_rules_hdr = QLabel("PRE-NEWS POSITION ACTIONS (T-15M):")
        lbl_rules_hdr.setStyleSheet(f"color: {fg_muted}; font-size: 9px; font-weight: bold; border: none; margin-top: 4px;")
        p_lay.addWidget(lbl_rules_hdr)

        self.lbl_desk_rule1 = QLabel("• Profit >= 1.5R: Auto-Trailed SL to Breakeven (+buffer)")
        self.lbl_desk_rule1.setStyleSheet("color: #22c55e; font-family: Consolas; font-size: 9.5px; font-weight: 600; border: none;")
        self.lbl_desk_rule2 = QLabel("• Profit 0.5R - 1.5R: Partial Close 50% & Lock BE")
        self.lbl_desk_rule2.setStyleSheet("color: #f59e0b; font-family: Consolas; font-size: 9.5px; font-weight: 600; border: none;")
        self.lbl_desk_rule3 = QLabel("• Negative PnL: Maintain original SL discipline")
        self.lbl_desk_rule3.setStyleSheet(f"color: {fg_muted}; font-family: Consolas; font-size: 9.5px; border: none;")
        p_lay.addWidget(self.lbl_desk_rule1)
        p_lay.addWidget(self.lbl_desk_rule2)
        p_lay.addWidget(self.lbl_desk_rule3)

        r_lay.addWidget(self.frame_protocol)

        # Section 3: Semi-Auto Execution Controls (Human Override)
        self.frame_actions = QFrame()
        self.frame_actions.setStyleSheet(
            f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 2px; padding: 8px; }}"
        )
        a_lay = QVBoxLayout(self.frame_actions)
        a_lay.setContentsMargins(6, 6, 6, 6)
        a_lay.setSpacing(6)

        lbl_a_tag = QLabel("SEMI-AUTO RISK CONTROLS")
        lbl_a_tag.setStyleSheet(f"color: {fg_muted}; font-size: 9.5px; font-weight: 700; letter-spacing: 0.5px; border: none;")
        a_lay.addWidget(lbl_a_tag)

        # Button 1: Force Defense Now
        self.btn_force_defense = QPushButton("FORCE ARM DEFENSE NOW")
        self.btn_force_defense.setFixedHeight(26)
        self.btn_force_defense.setCursor(Qt.PointingHandCursor)
        self.btn_force_defense.setToolTip("Immediately trail profitable orders to Breakeven and lock 50% volume ahead of schedule.")
        self.btn_force_defense.setStyleSheet(
            "QPushButton { background-color: transparent; color: #f59e0b; border: 1px solid #f59e0b; "
            "font-family: Consolas; font-size: 10px; font-weight: bold; border-radius: 2px; } "
            "QPushButton:hover { background-color: rgba(245, 158, 11, 0.15); }"
        )
        self.btn_force_defense.clicked.connect(self._handle_force_defense)
        a_lay.addWidget(self.btn_force_defense)

        # Button 2: Override Lock
        self.btn_override_lock = QPushButton("OVERRIDE LOCK (ALLOW TRADING)")
        self.btn_override_lock.setFixedHeight(26)
        self.btn_override_lock.setCursor(Qt.PointingHandCursor)
        self.btn_override_lock.setCheckable(True)
        self.btn_override_lock.setToolTip("Override automated news blackout lockout if manual entry is strictly required.")
        self.btn_override_lock.setStyleSheet(
            "QPushButton { background-color: transparent; color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.3); "
            "font-family: Consolas; font-size: 10px; font-weight: bold; border-radius: 2px; } "
            "QPushButton:checked { background-color: #ef4444; color: #ffffff; border-color: #ef4444; } "
            "QPushButton:hover:!checked { background-color: rgba(148, 163, 184, 0.1); }"
        )
        self.btn_override_lock.clicked.connect(self._handle_override_toggle)
        a_lay.addWidget(self.btn_override_lock)

        self.lbl_override_note = QLabel("RULE: ±15M BLACKOUT ENFORCED BY DEFAULT")
        self.lbl_override_note.setStyleSheet(f"color: {fg_muted}; font-family: Consolas; font-size: 9px; border: none; text-align: center;")
        self.lbl_override_note.setAlignment(Qt.AlignCenter)
        a_lay.addWidget(self.lbl_override_note)

        r_lay.addWidget(self.frame_actions)
        r_lay.addStretch(1)

    def set_filter(self, filter_key):
        """Applies active filter mode (ALL, HIGH, TARGET)."""
        self._current_filter = filter_key
        is_d = getattr(self.window, "is_dark_theme", False)
        self._update_filter_button_styles(is_d)
        self.load_calendar()

    def set_current_symbol(self, sym: str):
        """Updates current symbol context when user switches instrument."""
        if not sym:
            return
        self._current_symbol = sym.upper().split(".")[0].split("\n")[0].strip()
        if "TARGET" in self.filter_buttons:
            self.filter_buttons["TARGET"].setText(f"TARGET: {self._current_symbol}")
        if hasattr(self, "card_confluence"):
            self.card_confluence.findChild(QLabel).setText(f"4. TARGET BIAS ({self._current_symbol})")
        if self._current_filter == "TARGET":
            self.load_calendar()
        self._calculate_target_asset_bias()

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
                    "font-size: 9.5px; font-weight: bold; border-radius: 2px; padding: 0 8px; border: none; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: {inact_bg}; color: {inact_fg}; font-family: Consolas; "
                    f"font-size: 9.5px; font-weight: 500; border-radius: 2px; padding: 0 8px; border: 1px solid {border_col}; }} "
                    f"QPushButton:hover {{ background-color: {'#161d31' if is_dark else '#e2e8f0'}; color: {'#f8fafc' if is_dark else '#0f172a'}; }}"
                )

    def refresh_calendar(self):
        """Fetches calendar events and macro regime telemetry."""
        try:
            self._raw_events = self.engine.fetch_events()
            self.lbl_sync_status.setText(f"SYNCED: {datetime.datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            logger.warning(f"[MacroCalendar] Calendar fetch error: {e}")
            self._raw_events = []

        try:
            report = self.regime_engine.generate_macro_report()
            self._apply_macro_report(report)
        except Exception as e:
            logger.warning(f"[MacroCalendar] Macro report error: {e}")

        self.load_calendar()
        self._auto_select_next_event()

    def _apply_macro_report(self, report: dict):
        """Renders the 4-pillar macro matrix in clean financial English."""
        # 1. Market Risk Regime
        m_state = report.get("Market", {})
        raw_m = str(m_state.get("state", "UNKNOWN")).upper()
        vix = float(m_state.get("vix", 0))
        dxy = float(m_state.get("dxy", 0))
        dxy_trend = str(m_state.get("dxy_trend", "--")).upper()

        is_risk_off = ("OFF" in raw_m or vix >= 20.0)
        market_badge = "RISK-OFF" if is_risk_off else "RISK-ON"
        self.badge_market_state.setText(market_badge)
        self.badge_market_state.setStyleSheet(
            f"font-family: Consolas; font-size: 9px; font-weight: 700; padding: 1px 5px; border-radius: 2px; "
            f"background-color: {'#ef4444' if is_risk_off else '#22c55e'}; color: #ffffff;"
        )
        self.lbl_market_metrics.setText(f"VIX: {vix:.2f}  ·  DXY: {dxy:.2f} {dxy_trend}")

        # 2. Monetary Policy Stance
        mon_state = report.get("Monetary", {})
        raw_mon = str(mon_state.get("state", "UNKNOWN")).upper()
        us10y = float(mon_state.get("us10y", 0))
        d5 = float(mon_state.get("delta_5d", 0))
        sign = "+" if d5 >= 0 else ""

        if "HAWK" in raw_mon:
            mon_badge = "HAWKISH"
            mon_bg = "#ef4444"
        elif "DOV" in raw_mon:
            mon_badge = "DOVISH"
            mon_bg = "#22c55e"
        else:
            mon_badge = "NEUTRAL"
            mon_bg = "#0284c7"

        self.badge_monetary_state.setText(mon_badge)
        self.badge_monetary_state.setStyleSheet(
            f"font-family: Consolas; font-size: 9px; font-weight: 700; padding: 1px 5px; border-radius: 2px; "
            f"background-color: {mon_bg}; color: #ffffff;"
        )
        self.lbl_monetary_metrics.setText(f"US10Y: {us10y:.3f}%  ·  5D: {sign}{d5:.3f}%")

        # 3. Economic Growth Cycle
        eco_state = report.get("Economic", {})
        raw_eco = str(eco_state.get("state", "UNKNOWN")).upper()
        if "GROWTH" in raw_eco:
            eco_badge = "GROWTH"
            eco_bg = "#22c55e"
        elif "RECESSION" in raw_eco:
            eco_badge = "RECESSION"
            eco_bg = "#ef4444"
        else:
            eco_badge = "RECOVERY"
            eco_bg = "#0284c7"

        self.badge_economic_state.setText(eco_badge)
        self.badge_economic_state.setStyleSheet(
            f"font-family: Consolas; font-size: 9px; font-weight: 700; padding: 1px 5px; border-radius: 2px; "
            f"background-color: {eco_bg}; color: #ffffff;"
        )
        score_part = eco_state.get('reason', '')
        if ' - ' in score_part:
            score_part = score_part.split(' - ')[-1]
        self.lbl_economic_metrics.setText(f"CYCLE: {eco_badge}  ·  {score_part}")

        # 4. Target Asset Confluence Calculation
        self._calculate_target_asset_bias(is_risk_off, mon_badge, eco_badge, dxy_trend)

        # Telegram Wire Intel Strip
        wire_msg = str(report.get("Telegram_News", ""))
        if wire_msg and "không có" not in wire_msg.lower() and "no data" not in wire_msg.lower():
            self.lbl_wire_tag.setText("WIRE ALERT:")
            self.lbl_wire_tag.setStyleSheet("color: #f59e0b; font-family: Consolas; font-size: 9.5px; font-weight: bold; border: none;")
            self.lbl_wire_text.setText(wire_msg)
            self.lbl_wire_text.setStyleSheet("color: #f59e0b; font-size: 10px; font-weight: bold; border: none;")
        else:
            self.lbl_wire_tag.setText("WIRE:")
            self.lbl_wire_tag.setStyleSheet("color: #22c55e; font-family: Consolas; font-size: 9.5px; font-weight: bold; border: none;")
            self.lbl_wire_text.setText("NORMAL · NO BREAKING INTEL")
            is_d = getattr(self.window, "is_dark_theme", False)
            self.lbl_wire_text.setStyleSheet(f"color: {'#94a3b8' if is_d else '#64748b'}; font-size: 10px; border: none;")

    def _calculate_target_asset_bias(self, is_risk_off=None, mon_badge="NEUTRAL", eco_badge="RECOVERY", dxy_trend="DOWN"):
        """Synthesizes net macro bias for target symbol (e.g. XAUUSD)."""
        sym = self._current_symbol.upper()
        gold_score = 0

        # Safe haven / Risk appetite
        if is_risk_off is not None:
            gold_score += (1 if is_risk_off else -0.5)

        # Real yields (US10Y)
        if mon_badge == "DOVISH":
            gold_score += 1
        elif mon_badge == "HAWKISH":
            gold_score -= 1

        # Recession supports Gold
        if eco_badge == "RECESSION":
            gold_score += 0.5
        elif eco_badge == "GROWTH":
            gold_score -= 0.5

        # DXY trend
        if "DOWN" in dxy_trend:
            gold_score += 1
        elif "UP" in dxy_trend:
            gold_score -= 1

        if gold_score >= 1.0:
            bias_text = "BULLISH"
            bias_bg = "#22c55e"
            desc_text = "CONFLUENCE: FAVOR LONG (REAL YIELDS & SAFE HAVEN)"
        elif gold_score <= -1.0:
            bias_text = "BEARISH"
            bias_bg = "#ef4444"
            desc_text = "PRESSURE: FAVOR SHORT (DXY FIRM & TIGHT YIELDS)"
        else:
            bias_text = "NEUTRAL"
            bias_bg = "#0284c7"
            desc_text = "BALANCED FORCES: RANGE-BOUND EXPANSION"

        if hasattr(self, "badge_confluence_state"):
            self.badge_confluence_state.setText(bias_text)
            self.badge_confluence_state.setStyleSheet(
                f"font-family: Consolas; font-size: 9px; font-weight: 700; padding: 1px 5px; border-radius: 2px; "
                f"background-color: {bias_bg}; color: #ffffff;"
            )
            self.lbl_confluence_metrics.setText(desc_text)

    def load_calendar(self):
        """Populates the 70% left table with past events dimmed and surprise delta."""
        t = self.table
        t.setRowCount(0)
        events = list(self._raw_events)

        # Apply active filter
        if self._current_filter == "HIGH":
            events = [e for e in events if e.get("impact", 0) == 2]
        elif self._current_filter == "TARGET":
            curr = self._current_symbol.upper()
            filtered = []
            for e in events:
                cntry = e.get("country", "").upper()
                mapped_cur = COUNTRY_CURRENCY_MAP.get(cntry, cntry)
                if mapped_cur and mapped_cur in curr:
                    filtered.append(e)
                elif cntry == "US":
                    for dep in USD_DEPENDENT_ASSETS:
                        if curr.startswith(dep) or dep in curr:
                            filtered.append(e)
                            break
            events = filtered

        now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
        current_date = None
        today = datetime.date.today()
        today_row = -1

        is_d = getattr(self.window, "is_dark_theme", False)

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
            t.setRowHeight(row, 26)

            # Check if event has already passed (past release)
            # sort_key was converted with +7h in calendar_engine
            # Compare with UTC+7 timestamp
            now_vn_ts = now_ts + (7 * 3600)
            is_past = (sort_key < (now_vn_ts - 300))

            text_alpha = "#64748b" if is_past else ("#f8fafc" if is_d else "#0f172a")

            # Col 0: TIME (UTC+7)
            time_str = e.get("time", "").split(" ")[-1]
            t.setCellWidget(row, 0, self._cell(time_str, color=text_alpha, bold=True, font="Consolas"))

            # Col 1: CURRENCY
            t.setCellWidget(row, 1, self._country_badge(e.get("country", "US"), is_past=is_past))

            # Col 2: IMPACT
            t.setCellWidget(row, 2, self._impact_badge(e.get("impact", 0), is_past=is_past))

            # Col 3: EVENT RELEASE
            lbl_title = QLabel(f" {e.get('title', '')}")
            lbl_title.setStyleSheet(f"font-size: 11px; font-weight: {'400' if is_past else '500'}; color: {text_alpha};")
            lbl_title.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            t.setCellWidget(row, 3, lbl_title)

            # Col 4, 5, 6: Actual, Forecast, Previous
            actual = str(e.get("actual", "-")) if e.get("actual") not in ("None", "", None) else "-"
            forecast = str(e.get("forecast", "-")) if e.get("forecast") not in ("None", "", None) else "-"
            previous = str(e.get("previous", "-")) if e.get("previous") not in ("None", "", None) else "-"

            # Col 7: Surprise Delta calculation & directional color
            act_col = text_alpha
            surprise_text = "--"
            surprise_col = text_alpha

            if actual != "-" and forecast != "-":
                try:
                    act_num = float(actual.replace("%", "").replace("K", "").replace("M", "").replace("B", ""))
                    fc_num = float(forecast.replace("%", "").replace("K", "").replace("M", "").replace("B", ""))
                    diff = act_num - fc_num
                    sign = "+" if diff > 0 else ""
                    if diff > 0.0001:
                        act_col = "#22c55e"
                        surprise_col = "#22c55e"
                        surprise_text = f"{sign}{diff:.1f} ▲"
                    elif diff < -0.0001:
                        act_col = "#ef4444"
                        surprise_col = "#ef4444"
                        surprise_text = f"{diff:.1f} ▼"
                    else:
                        surprise_text = "0.0 ="
                except Exception:
                    pass

            t.setCellWidget(row, 4, self._cell(actual, color=act_col, bold=True, font="Consolas", align=Qt.AlignRight))
            t.setCellWidget(row, 5, self._cell(forecast, color=text_alpha, font="Consolas", align=Qt.AlignRight))
            t.setCellWidget(row, 6, self._cell(previous, color=text_alpha, font="Consolas", align=Qt.AlignRight))
            t.setCellWidget(row, 7, self._cell(surprise_text, color=surprise_col, bold=True, font="Consolas", align=Qt.AlignRight))

            # Store event dict on row item 0
            item = QTableWidgetItem()
            item.setData(Qt.UserRole, e)
            t.setItem(row, 0, item)

        if today_row != -1:
            item = t.item(today_row, 0)
            if item:
                t.scrollToItem(item, QAbstractItemView.PositionAtTop)

    def _auto_select_next_event(self):
        """Automatically selects the next upcoming high-impact event by default."""
        t = self.table
        now_vn_ts = datetime.datetime.now(datetime.timezone.utc).timestamp() + (7 * 3600)

        best_row = -1
        min_future_gap = float("inf")

        for r in range(t.rowCount()):
            item = t.item(r, 0)
            if not item:
                continue
            e = item.data(Qt.UserRole)
            if not e:
                continue

            sort_key = e.get("sort_key", 0.0)
            impact = e.get("impact", 0)

            # Prioritize future high impact events
            if sort_key >= (now_vn_ts - 60):
                gap = sort_key - now_vn_ts
                if impact == 2 and gap < min_future_gap:
                    min_future_gap = gap
                    best_row = r

        if best_row != -1:
            t.selectRow(best_row)
        elif t.rowCount() > 1:
            t.selectRow(1)

    def _on_table_selection_changed(self):
        """Updates right-hand defense desk when an event row is clicked."""
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

        self._selected_event = event
        self._update_defense_desk_display(event)

    def _update_defense_desk_display(self, event: dict):
        """Refreshes the right desk with selected event details."""
        cntry = event.get("country", "US")
        title = event.get("title", "")
        time_str = event.get("time", "")
        impact = event.get("impact", 0)

        self.lbl_next_event_title.setText(f"{cntry} · {title.upper()}")
        self.lbl_next_event_time.setText(f"SCHEDULED: {time_str} VN (UTC+7)")

        # Affected Assets mapping
        affected = []
        cur = COUNTRY_CURRENCY_MAP.get(cntry, cntry)
        if cur:
            affected.append(f"{cur} FX PAIRS")
        if cntry.upper() == "US":
            affected.extend(["XAUUSD (GOLD)", "US30", "NAS100", "BTCUSD"])

        self.lbl_desk_assets.setText(", ".join(affected) if affected else f"{cntry} DOMESTIC ASSETS")

        # Update countdown immediately
        self._on_clock_tick()

    def _on_clock_tick(self):
        """1-second timer tick for countdown and active defense monitoring."""
        if not hasattr(self, "lbl_countdown_val"):
            return

        event = getattr(self, "_selected_event", None)
        if not event:
            return

        sort_key = event.get("sort_key", 0.0)
        now_vn_ts = datetime.datetime.now(datetime.timezone.utc).timestamp() + (7 * 3600)
        diff_sec = int(sort_key - now_vn_ts)

        impact = event.get("impact", 0)

        if diff_sec > 0:
            hrs = diff_sec // 3600
            mins = (diff_sec % 3600) // 60
            secs = diff_sec % 60
            self.lbl_countdown_val.setText(f"T - {hrs:02d}:{mins:02d}:{secs:02d}")

            # Within T-15m defense window
            if diff_sec <= 900 and impact == 2:
                if self._override_active:
                    self.lbl_countdown_val.setStyleSheet("color: #f59e0b; font-family: Consolas; font-size: 22px; font-weight: 900; border: none;")
                    self.lbl_lockout_status.setText("STATUS: OVERRIDE ACTIVE (TRADING ALLOWED)")
                    self.lbl_lockout_status.setStyleSheet("color: #f59e0b; font-family: Consolas; font-size: 10px; font-weight: bold; border: none;")
                else:
                    self.lbl_countdown_val.setStyleSheet("color: #ef4444; font-family: Consolas; font-size: 22px; font-weight: 900; border: none;")
                    self.lbl_lockout_status.setText("STATUS: T-15M DEFENSE ARMED (ORDERS LOCKED)")
                    self.lbl_lockout_status.setStyleSheet("color: #ef4444; font-family: Consolas; font-size: 10px; font-weight: bold; border: none;")
            else:
                self.lbl_countdown_val.setStyleSheet("color: #22c55e; font-family: Consolas; font-size: 22px; font-weight: 900; border: none;")
                self.lbl_lockout_status.setText("STATUS: MONITORING · WINDOW CLEAR")
                self.lbl_lockout_status.setStyleSheet("color: #22c55e; font-family: Consolas; font-size: 10px; font-weight: bold; border: none;")
        else:
            abs_past = abs(diff_sec)
            mins_past = abs_past // 60
            self.lbl_countdown_val.setText(f"T + {mins_past:02d}M AGO")
            self.lbl_countdown_val.setStyleSheet("color: #64748b; font-family: Consolas; font-size: 22px; font-weight: 900; border: none;")
            if abs_past <= 900 and impact == 2 and not self._override_active:
                self.lbl_lockout_status.setText("STATUS: POST-NEWS SPREAD RECOVERY")
                self.lbl_lockout_status.setStyleSheet("color: #f59e0b; font-family: Consolas; font-size: 10px; font-weight: bold; border: none;")
            else:
                self.lbl_lockout_status.setText("STATUS: RELEASED · SPREAD NORMALIZED")
                self.lbl_lockout_status.setStyleSheet("color: #22c55e; font-family: Consolas; font-size: 10px; font-weight: bold; border: none;")

    def _handle_force_defense(self):
        """Immediately triggers pre-news active position defense via EventRiskEngine."""
        try:
            from backend.core.event_risk_engine import EventRiskEngine
            ere = getattr(self.window, "_event_risk_engine", None) or EventRiskEngine()
            results = ere.evaluate_pre_news_defense()
            self.lbl_lockout_status.setText(f"DEFENSE TRIGGERED: {len(results)} POSITIONS SECURED")
            self.lbl_lockout_status.setStyleSheet("color: #f59e0b; font-family: Consolas; font-size: 10px; font-weight: bold; border: none;")
        except Exception as e:
            logger.warning(f"[MacroCalendar] Force defense trigger error: {e}")

    def _handle_override_toggle(self, checked):
        """Toggles semi-auto manual lockout override."""
        self._override_active = checked
        if checked:
            self.lbl_override_note.setText("OVERRIDE ACTIVE: MANUAL TRADING UNLOCKED")
            self.lbl_override_note.setStyleSheet("color: #ef4444; font-family: Consolas; font-size: 9px; font-weight: bold; border: none;")
        else:
            self.lbl_override_note.setText("RULE: ±15M BLACKOUT ENFORCED BY DEFAULT")
            is_d = getattr(self.window, "is_dark_theme", False)
            self.lbl_override_note.setStyleSheet(f"color: {'#94a3b8' if is_d else '#64748b'}; font-family: Consolas; font-size: 9px; border: none;")
        self._on_clock_tick()

    def _insert_date_separator(self, row, date_obj):
        """Renders an institutional date bar across all columns."""
        t = self.table
        t.insertRow(row)
        t.setSpan(row, 0, 1, t.columnCount())

        today = datetime.date.today()
        is_today = (date_obj == today)

        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.setSpacing(6)
        lay.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        thu = WEEKDAYS_EN[date_obj.weekday()]
        date_str = date_obj.strftime("%d/%m/%Y")
        lbl_date = QLabel(f"{thu}  ·  {date_str}")
        lbl_date.setStyleSheet("font-family: Consolas; font-size: 10.5px; font-weight: bold; color: #38bdf8;")
        lay.addWidget(lbl_date)

        if is_today:
            lbl_badge = QLabel("TODAY")
            lbl_badge.setStyleSheet(
                "background-color: #22c55e; color: #ffffff; border-radius: 2px; padding: 1px 5px; "
                "font-family: Consolas; font-size: 9px; font-weight: bold;"
            )
            lay.addWidget(lbl_badge)

        t.setCellWidget(row, 0, w)
        t.setRowHeight(row, 24)

        is_d = getattr(self.window, "is_dark_theme", False)
        bg = "#161d31" if is_d else "#e2e8f0"
        for col in range(t.columnCount()):
            item = QTableWidgetItem()
            item.setBackground(QColor(bg))
            item.setFlags(Qt.NoItemFlags)
            t.setItem(row, col, item)

    def _country_badge(self, country: str, is_past: bool = False):
        col = COUNTRY_COLORS.get(country.upper(), "#334155")
        if is_past:
            col = "#475569"
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(2, 2, 2, 2)
        lbl = QLabel(country.upper())
        lbl.setStyleSheet(
            f"background-color: {col}; color: #ffffff; font-family: Consolas; font-size: 9.5px; "
            "font-weight: bold; border-radius: 2px; padding: 1px 4px;"
        )
        lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(lbl, alignment=Qt.AlignCenter)
        return w

    def _impact_badge(self, impact: int, is_past: bool = False):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(2, 2, 2, 2)

        if is_past:
            lbl = QLabel("PAST")
            lbl.setStyleSheet("background-color: #334155; color: #64748b; font-family: Consolas; font-size: 9px; font-weight: 500; border-radius: 2px; padding: 1px 4px;")
        elif impact == 2:
            lbl = QLabel("HIGH")
            lbl.setStyleSheet("background-color: #ef4444; color: #ffffff; font-family: Consolas; font-size: 9px; font-weight: bold; border-radius: 2px; padding: 1px 4px;")
        elif impact == 1:
            lbl = QLabel("MED")
            lbl.setStyleSheet("background-color: #f59e0b; color: #000000; font-family: Consolas; font-size: 9px; font-weight: bold; border-radius: 2px; padding: 1px 4px;")
        else:
            lbl = QLabel("LOW")
            lbl.setStyleSheet("background-color: #334155; color: #94a3b8; font-family: Consolas; font-size: 9px; font-weight: 500; border-radius: 2px; padding: 1px 4px;")

        lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(lbl, alignment=Qt.AlignCenter)
        return w

    def _cell(self, text, color=None, bold=False, font="Segoe UI", align=Qt.AlignCenter):
        val = str(text) if text not in ("None", "none", "", None) else "-"
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(4, 0, 4, 0)
        lbl = QLabel(val)

        is_d = getattr(self.window, "is_dark_theme", False)
        if not color:
            color = "#f8fafc" if is_d else "#0f172a"

        weight = "bold" if bold else "normal"
        lbl.setStyleSheet(f"color: {color}; font-family: '{font}', monospace; font-size: 10.5px; font-weight: {weight}; border: none;")
        lbl.setAlignment(align | Qt.AlignVCenter)
        lay.addWidget(lbl)
        return w

    def update_theme(self, is_dark: bool):
        """Applies theme colors to the entire workspace."""
        if hasattr(self.window, "tabCalendar") and self.window.tabCalendar:
            tab_bg = "#070a12" if is_dark else "#f8fafc"
            self.window.tabCalendar.setAutoFillBackground(True)
            self.window.tabCalendar.setStyleSheet(f"QWidget#tabCalendar {{ background-color: {tab_bg}; }}")

        self._update_filter_button_styles(is_dark)
        bg = "#101524" if is_dark else "#ffffff"
        border = "rgba(255, 255, 255, 0.08)" if is_dark else "#e2e8f0"

        for card in [self.card_market, self.card_monetary, self.card_economic, self.card_confluence]:
            if card:
                card.setStyleSheet(
                    f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 2px; padding: 4px 8px; }}"
                )

        if hasattr(self, "frame_countdown") and self.frame_countdown:
            self.frame_countdown.setStyleSheet(f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 2px; padding: 8px; }}")
        if hasattr(self, "frame_protocol") and self.frame_protocol:
            self.frame_protocol.setStyleSheet(f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 2px; padding: 8px; }}")
        if hasattr(self, "frame_actions") and self.frame_actions:
            self.frame_actions.setStyleSheet(f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 2px; padding: 8px; }}")


# Backward compatibility alias
MacroCalendarController = CalendarManager
