"""
Macro Calendar Controller & Institutional Event Risk Defense Desk
===================================================================
Institutional Macro Workspace for VECTRA Quant System (PySide6 / Qt6)
Conforms strictly to DESIGN.md:
- Pitch-Black / Institutional Flat UI (border-radius: 0px to 3px)
- Strict Monospace & Tabular figures (Consolas, text-align: right)
- 4-Pillar Macro Matrix: Market Risk, Monetary Policy, Growth Cycle, Target Asset Macro Confluence
- 70:30 Golden Ratio Splitter: High-Density Calendar (Left) + Compact Semi-Auto Defense Desk (Right)
- Accurate UTC Epoch Countdown (Zero timezone drift)
- IMPACT column preserves HIGH/MED/LOW with muted alpha for past events
- Prioritizes Target Asset (XAUUSD) for upcoming event defense
- Guaranteed viewport containment (Bottom navigation tab bar remains permanently pinned)
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
from backend.core.event_risk_engine import EventRiskEngine, COUNTRY_CURRENCY_MAP, USD_DEPENDENT_ASSETS

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
        self.risk_engine = EventRiskEngine()
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

        # Synchronize with Central Timezone Manager
        from backend.core.timezone_manager import timezone_manager
        timezone_manager.add_listener(self._on_timezone_changed)

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
        tab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

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

        self.root_layout.setContentsMargins(6, 4, 6, 4)
        self.root_layout.setSpacing(4)

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
        self.cards_frame.setFixedHeight(48)
        self.cards_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        h_lay = QHBoxLayout(self.cards_frame)
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(5)

        # Helper to create compact card
        def _make_card(title_text):
            card = QFrame()
            card.setStyleSheet(
                f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 2px; padding: 2px 6px; }}"
            )
            lay = QVBoxLayout(card)
            lay.setContentsMargins(2, 2, 2, 2)
            lay.setSpacing(1)

            top = QHBoxLayout()
            lbl_title = QLabel(title_text)
            lbl_title.setStyleSheet(f"color: {fg_muted}; font-size: 8.5px; font-weight: 700; letter-spacing: 0.5px; border: none;")
            badge = QLabel("CALCULATING")
            badge.setStyleSheet("font-family: Consolas; font-size: 8.5px; font-weight: 700; padding: 1px 4px; border-radius: 2px; border: none;")
            top.addWidget(lbl_title)
            top.addStretch()
            top.addWidget(badge)
            lay.addLayout(top)

            lbl_metrics = QLabel("--")
            lbl_metrics.setStyleSheet("font-family: Consolas; font-size: 10.5px; font-weight: bold; border: none;")
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

        # Card 4: Target Asset Macro Confluence
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
        self.frame_ctrl.setFixedHeight(26)
        self.frame_ctrl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.frame_ctrl.setStyleSheet(
            f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 2px; padding: 1px 6px; }}"
        )
        c_lay = QHBoxLayout(self.frame_ctrl)
        c_lay.setContentsMargins(4, 0, 4, 0)
        c_lay.setSpacing(5)

        # Filter buttons
        lbl_flt = QLabel("FILTER:")
        lbl_flt.setStyleSheet(f"color: {fg_muted}; font-size: 9px; font-weight: bold; border: none;")
        c_lay.addWidget(lbl_flt)

        self.filter_buttons = {}
        filters_spec = [
            ("ALL", "ALL RELEASES"),
            ("HIGH", "HIGH IMPACT (TIER 2)"),
            ("TARGET", f"ACTIVE: {self._current_symbol}"),
        ]

        for key, text in filters_spec:
            btn = QPushButton(text)
            btn.setFixedHeight(18)
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
        sep1.setFixedHeight(12)
        sep1.setStyleSheet(f"background-color: {border}; border: none;")
        c_lay.addWidget(sep1)

        # Wire Alert Status (Compact, non-intrusive)
        self.lbl_wire_tag = QLabel("WIRE:")
        self.lbl_wire_tag.setStyleSheet("color: #22c55e; font-family: Consolas; font-size: 9px; font-weight: bold; border: none;")
        c_lay.addWidget(self.lbl_wire_tag)

        self.lbl_wire_text = QLabel("NORMAL · NO BREAKING INTEL")
        self.lbl_wire_text.setStyleSheet(f"color: {fg_muted}; font-size: 9.5px; font-family: 'Segoe UI', sans-serif; border: none;")
        c_lay.addWidget(self.lbl_wire_text, stretch=1)

        # Sync indicator & subtle refresh
        self.lbl_sync_status = QLabel("SYNCED: LIVE")
        self.lbl_sync_status.setStyleSheet(f"color: {fg_muted}; font-family: Consolas; font-size: 9px; border: none;")
        c_lay.addWidget(self.lbl_sync_status)

        self.btn_refresh = QPushButton("↻")
        self.btn_refresh.setFixedSize(18, 18)
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setToolTip("Refresh Economic Calendar & Intermarket Feed")
        self.btn_refresh.setStyleSheet(
            "QPushButton { background-color: transparent; color: #0284c7; font-family: Consolas; font-size: 12px; font-weight: bold; border: none; } "
            "QPushButton:hover { background-color: rgba(2, 132, 199, 0.15); border-radius: 2px; }"
        )
        self.btn_refresh.clicked.connect(self.refresh_calendar)
        c_lay.addWidget(self.btn_refresh)

        self.root_layout.addWidget(self.frame_ctrl)

    def _setup_main_splitter(self):
        """Constructs 70:30 horizontal split: Economic Calendar on Left + Compact Defense Desk on Right."""
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setObjectName("calendarSplitter")
        self.main_splitter.setHandleWidth(4)
        self.main_splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # --- LEFT PANE (70%): High-Density Calendar Table ---
        self.left_container = QWidget()
        self.left_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        l_lay = QVBoxLayout(self.left_container)
        l_lay.setContentsMargins(0, 0, 0, 0)
        l_lay.setSpacing(0)

        self.table = QTableWidget()
        self.table.setObjectName("tableEconomicCalendar")
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "TIME (VN)",
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
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed)
        hdr.setSectionResizeMode(2, QHeaderView.Fixed)
        hdr.setSectionResizeMode(3, QHeaderView.Stretch)
        hdr.setSectionResizeMode(4, QHeaderView.Fixed)
        hdr.setSectionResizeMode(5, QHeaderView.Fixed)
        hdr.setSectionResizeMode(6, QHeaderView.Fixed)
        hdr.setSectionResizeMode(7, QHeaderView.Fixed)

        self.table.setColumnWidth(0, 80)
        self.table.setColumnWidth(1, 52)
        self.table.setColumnWidth(2, 70)
        self.table.setColumnWidth(4, 75)
        self.table.setColumnWidth(5, 75)
        self.table.setColumnWidth(6, 75)
        self.table.setColumnWidth(7, 85)

        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        l_lay.addWidget(self.table)
        self.main_splitter.addWidget(self.left_container)

        # --- RIGHT PANE (30%): Compact Event Risk & Semi-Auto Defense Desk ---
        self.right_container = QWidget()
        self.right_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self._setup_defense_desk_ui()
        self.main_splitter.addWidget(self.right_container)

        # 70:30 Split Proportions
        self.main_splitter.setStretchFactor(0, 7)
        self.main_splitter.setStretchFactor(1, 3)
        self.main_splitter.setSizes([950, 380])

        self.root_layout.addWidget(self.main_splitter, stretch=1)

    def _setup_defense_desk_ui(self):
        """Constructs right-hand semi-auto defense desk and countdown monitor with strict vertical budget."""
        is_d = getattr(self.window, "is_dark_theme", False)
        bg = "#101524" if is_d else "#ffffff"
        border = "rgba(255, 255, 255, 0.08)" if is_d else "#e2e8f0"
        fg_muted = "#94a3b8" if is_d else "#64748b"

        r_lay = QVBoxLayout(self.right_container)
        r_lay.setContentsMargins(0, 0, 0, 0)
        r_lay.setSpacing(4)

        # Section 1: Upcoming Event Countdown Card (~105px)
        self.frame_countdown = QFrame()
        self.frame_countdown.setStyleSheet(
            f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 2px; padding: 6px; }}"
        )
        c_lay = QVBoxLayout(self.frame_countdown)
        c_lay.setContentsMargins(4, 4, 4, 4)
        c_lay.setSpacing(2)

        top_c_row = QHBoxLayout()
        lbl_c_tag = QLabel("NEXT HIGH-IMPACT RELEASE")
        lbl_c_tag.setStyleSheet("color: #0284c7; font-family: Consolas; font-size: 9px; font-weight: bold; border: none;")
        self.badge_target_relevance = QLabel("TARGET: DIRECT (XAUUSD)")
        self.badge_target_relevance.setStyleSheet(
            "background-color: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3); "
            "font-family: Consolas; font-size: 8.5px; font-weight: bold; padding: 1px 4px; border-radius: 2px; border: none;"
        )
        top_c_row.addWidget(lbl_c_tag)
        top_c_row.addStretch()
        top_c_row.addWidget(self.badge_target_relevance)
        c_lay.addLayout(top_c_row)

        self.lbl_next_event_title = QLabel("US · CORE CPI MOM")
        self.lbl_next_event_title.setStyleSheet("font-size: 11.5px; font-weight: bold; border: none;")
        c_lay.addWidget(self.lbl_next_event_title)

        self.lbl_next_event_time = QLabel("SCHEDULED: 19:30 VN (UTC+7)")
        self.lbl_next_event_time.setStyleSheet(f"color: {fg_muted}; font-family: Consolas; font-size: 9.5px; border: none;")
        c_lay.addWidget(self.lbl_next_event_time)

        # Huge Monospace Countdown
        self.lbl_countdown_val = QLabel("T - 00:00:00")
        self.lbl_countdown_val.setStyleSheet(
            "color: #ef4444; font-family: 'Consolas', monospace; font-size: 20px; font-weight: 900; letter-spacing: 1px; border: none; margin: 2px 0;"
        )
        c_lay.addWidget(self.lbl_countdown_val)

        self.lbl_lockout_status = QLabel("STATUS: MONITORING · WINDOW CLEAR")
        self.lbl_lockout_status.setStyleSheet(
            "color: #22c55e; font-family: Consolas; font-size: 9.5px; font-weight: bold; border: none;"
        )
        c_lay.addWidget(self.lbl_lockout_status)
        r_lay.addWidget(self.frame_countdown)

        # Section 2: Quantitative Defense Protocol (~110px)
        self.frame_protocol = QFrame()
        self.frame_protocol.setStyleSheet(
            f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 2px; padding: 6px; }}"
        )
        p_lay = QVBoxLayout(self.frame_protocol)
        p_lay.setContentsMargins(4, 4, 4, 4)
        p_lay.setSpacing(2)

        lbl_p_tag = QLabel("DEFENSE PROTOCOL (T-15M SHIELD)")
        lbl_p_tag.setStyleSheet(f"color: {fg_muted}; font-size: 9px; font-weight: 700; letter-spacing: 0.5px; border: none;")
        p_lay.addWidget(lbl_p_tag)

        self.lbl_desk_assets = QLabel("AFFECTED ASSETS: USD PAIRS, XAUUSD, US30")
        self.lbl_desk_assets.setStyleSheet("font-family: Consolas; font-size: 9.5px; font-weight: bold; border: none;")
        p_lay.addWidget(self.lbl_desk_assets)

        self.lbl_desk_rule1 = QLabel("• PnL >= +1.5R: Auto-Trail SL to Breakeven (+buffer)")
        self.lbl_desk_rule1.setStyleSheet("color: #22c55e; font-family: Consolas; font-size: 9px; font-weight: 600; border: none;")
        self.lbl_desk_rule2 = QLabel("• PnL +0.5R to +1.5R: Partial Close 50% & Lock BE")
        self.lbl_desk_rule2.setStyleSheet("color: #f59e0b; font-family: Consolas; font-size: 9px; font-weight: 600; border: none;")
        self.lbl_desk_rule3 = QLabel("• Negative PnL: Maintain original SL discipline")
        self.lbl_desk_rule3.setStyleSheet(f"color: {fg_muted}; font-family: Consolas; font-size: 9px; border: none;")
        p_lay.addWidget(self.lbl_desk_rule1)
        p_lay.addWidget(self.lbl_desk_rule2)
        p_lay.addWidget(self.lbl_desk_rule3)

        r_lay.addWidget(self.frame_protocol)

        # Section 3: Semi-Auto Execution Controls (~75px)
        self.frame_actions = QFrame()
        self.frame_actions.setStyleSheet(
            f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 2px; padding: 6px; }}"
        )
        a_lay = QVBoxLayout(self.frame_actions)
        a_lay.setContentsMargins(4, 4, 4, 4)
        a_lay.setSpacing(4)

        lbl_a_tag = QLabel("SEMI-AUTO RISK OVERRIDE")
        lbl_a_tag.setStyleSheet(f"color: {fg_muted}; font-size: 8.5px; font-weight: 700; letter-spacing: 0.5px; border: none;")
        a_lay.addWidget(lbl_a_tag)

        # 2 Buttons arranged side-by-side to save height
        btns_row = QHBoxLayout()
        btns_row.setSpacing(4)

        # Button 1: Force Defense Now
        self.btn_force_defense = QPushButton("FORCE DEFENSE")
        self.btn_force_defense.setFixedHeight(24)
        self.btn_force_defense.setCursor(Qt.PointingHandCursor)
        self.btn_force_defense.setToolTip("Immediately trail profitable orders to Breakeven and lock 50% volume ahead of schedule.")
        self.btn_force_defense.setStyleSheet(
            "QPushButton { background-color: transparent; color: #f59e0b; border: 1px solid #f59e0b; "
            "font-family: Consolas; font-size: 9.5px; font-weight: bold; border-radius: 2px; padding: 0 4px; } "
            "QPushButton:hover { background-color: rgba(245, 158, 11, 0.15); }"
        )
        self.btn_force_defense.clicked.connect(self._handle_force_defense)
        btns_row.addWidget(self.btn_force_defense)

        # Button 2: Override Lock
        self.btn_override_lock = QPushButton("OVERRIDE LOCK")
        self.btn_override_lock.setFixedHeight(24)
        self.btn_override_lock.setCursor(Qt.PointingHandCursor)
        self.btn_override_lock.setCheckable(True)
        self.btn_override_lock.setToolTip("Override automated news blackout lockout if manual entry is strictly required.")
        self.btn_override_lock.setStyleSheet(
            "QPushButton { background-color: transparent; color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.3); "
            "font-family: Consolas; font-size: 9.5px; font-weight: bold; border-radius: 2px; padding: 0 4px; } "
            "QPushButton:checked { background-color: #ef4444; color: #ffffff; border-color: #ef4444; } "
            "QPushButton:hover:!checked { background-color: rgba(148, 163, 184, 0.1); }"
        )
        self.btn_override_lock.clicked.connect(self._handle_override_toggle)
        btns_row.addWidget(self.btn_override_lock)
        a_lay.addLayout(btns_row)

        self.lbl_override_note = QLabel("RULE: ±15M BLACKOUT ENFORCED BY DEFAULT")
        self.lbl_override_note.setStyleSheet(f"color: {fg_muted}; font-family: Consolas; font-size: 8.5px; border: none; text-align: center;")
        self.lbl_override_note.setAlignment(Qt.AlignCenter)
        a_lay.addWidget(self.lbl_override_note)

        r_lay.addWidget(self.frame_actions)

        # Section 4: Quantitative Event Assessment & Action Desk (Fills empty area cleanly)
        self.frame_quant_action = QFrame()
        self.frame_quant_action.setStyleSheet(
            f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 2px; padding: 6px; }}"
        )
        qa_lay = QVBoxLayout(self.frame_quant_action)
        qa_lay.setContentsMargins(4, 4, 4, 4)
        qa_lay.setSpacing(3)

        top_qa = QHBoxLayout()
        lbl_qa_tag = QLabel("QUANT EVENT IMPACT & ACTIONS")
        lbl_qa_tag.setStyleSheet(f"color: {fg_muted}; font-size: 8.5px; font-weight: 700; letter-spacing: 0.5px; border: none;")
        self.lbl_qa_badge = QLabel("AI EVALUATION")
        self.lbl_qa_badge.setStyleSheet(
            "background-color: rgba(2, 132, 199, 0.15); color: #0284c7; "
            "font-family: Consolas; font-size: 8px; font-weight: bold; padding: 1px 4px; border-radius: 2px; border: none;"
        )
        top_qa.addWidget(lbl_qa_tag)
        top_qa.addStretch()
        top_qa.addWidget(self.lbl_qa_badge)
        qa_lay.addLayout(top_qa)

        self.lbl_qa_event_name = QLabel("EVENT: Select any row in calendar")
        self.lbl_qa_event_name.setStyleSheet("font-size: 10px; font-weight: bold; border: none;")
        qa_lay.addWidget(self.lbl_qa_event_name)

        self.lbl_qa_surprise = QLabel("DEVIATION: --")
        self.lbl_qa_surprise.setStyleSheet("font-family: Consolas; font-size: 9px; color: #64748b; border: none;")
        qa_lay.addWidget(self.lbl_qa_surprise)

        self.lbl_qa_ai_insight = QLabel("• AI Assessment: Click any event row to inspect macro deviation and liquidity shock.")
        self.lbl_qa_ai_insight.setStyleSheet("font-size: 9.5px; color: #94a3b8; border: none;")
        self.lbl_qa_ai_insight.setWordWrap(True)
        qa_lay.addWidget(self.lbl_qa_ai_insight)

        self.lbl_qa_asset_impact = QLabel("• Target Impact: Standing by for economic releases.")
        self.lbl_qa_asset_impact.setStyleSheet("font-size: 9.5px; color: #22c55e; font-weight: 600; border: none;")
        self.lbl_qa_asset_impact.setWordWrap(True)
        qa_lay.addWidget(self.lbl_qa_asset_impact)

        r_lay.addWidget(self.frame_quant_action)
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
            self.filter_buttons["TARGET"].setText(f"ACTIVE: {self._current_symbol}")
        if hasattr(self, "card_confluence"):
            self.card_confluence.findChild(QLabel).setText(f"4. TARGET BIAS ({self._current_symbol})")
        if self._current_filter == "TARGET":
            self.load_calendar()
        self._calculate_target_asset_bias()
        self._auto_select_next_event()

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
                    f"font-size: 9px; font-weight: bold; border-radius: 2px; padding: 0 6px; border: none; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: {inact_bg}; color: {inact_fg}; font-family: Consolas; "
                    f"font-size: 9px; font-weight: 500; border-radius: 2px; padding: 0 6px; border: 1px solid {border_col}; }} "
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
            f"font-family: Consolas; font-size: 8.5px; font-weight: 700; padding: 1px 4px; border-radius: 2px; "
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
            f"font-family: Consolas; font-size: 8.5px; font-weight: 700; padding: 1px 4px; border-radius: 2px; "
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
            f"font-family: Consolas; font-size: 8.5px; font-weight: 700; padding: 1px 4px; border-radius: 2px; "
            f"background-color: {eco_bg}; color: #ffffff;"
        )
        # Clarify economic cycle drivers with clear economic terms
        if eco_badge == "RECESSION":
            clear_eco = "PMI Thu hẹp & Thất nghiệp gia tăng"
        elif eco_badge == "GROWTH":
            clear_eco = "PMI Mở rộng & Thị trường lao động vững"
        elif eco_badge == "STAGFLATION":
            clear_eco = "Lạm phát cao & Tăng trưởng suy giảm"
        else:
            clear_eco = "PMI Ổn định & Tuyển dụng hồi phục"
        self.lbl_economic_metrics.setText(f"CYCLE: {eco_badge}  ·  {clear_eco}")

        # 4. Target Asset Confluence Calculation
        self._calculate_target_asset_bias(is_risk_off, mon_badge, eco_badge, dxy_trend)

        # Telegram Wire Intel Strip
        wire_msg = str(report.get("Telegram_News", ""))
        if wire_msg and "không có" not in wire_msg.lower() and "no data" not in wire_msg.lower() and "no emergency" not in wire_msg.lower():
            self.lbl_wire_tag.setText("WIRE ALERT:")
            self.lbl_wire_tag.setStyleSheet("color: #f59e0b; font-family: Consolas; font-size: 9px; font-weight: bold; border: none;")
            self.lbl_wire_text.setText(wire_msg)
            self.lbl_wire_text.setStyleSheet("color: #f59e0b; font-size: 9.5px; font-weight: bold; border: none;")
        else:
            self.lbl_wire_tag.setText("WIRE:")
            self.lbl_wire_tag.setStyleSheet("color: #22c55e; font-family: Consolas; font-size: 9px; font-weight: bold; border: none;")
            self.lbl_wire_text.setText("NORMAL · NO BREAKING INTEL")
            is_d = getattr(self.window, "is_dark_theme", False)
            self.lbl_wire_text.setStyleSheet(f"color: {'#94a3b8' if is_d else '#64748b'}; font-size: 9.5px; border: none;")

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
            desc_text = f"ƯU TIÊN MUA ({sym})  ·  Lãi suất thực giảm & Cầu trú ẩn hỗ trợ"
        elif gold_score <= -1.0:
            bias_text = "BEARISH"
            bias_bg = "#ef4444"
            desc_text = f"ÁP LỰC BÁN ({sym})  ·  DXY tăng mạnh & Lãi suất thắt chặt"
        else:
            bias_text = "NEUTRAL"
            bias_bg = "#0284c7"
            desc_text = f"TRUNG LẬP ({sym})  ·  Cung cầu cân bằng, thị trường tích lũy"

        if hasattr(self, "badge_confluence_state"):
            self.badge_confluence_state.setText(bias_text)
            self.badge_confluence_state.setStyleSheet(
                f"font-family: Consolas; font-size: 8.5px; font-weight: 700; padding: 1px 4px; border-radius: 2px; "
                f"background-color: {bias_bg}; color: #ffffff;"
            )
            self.lbl_confluence_metrics.setText(desc_text)

    def load_calendar(self):
        """Populates the 70% left table with accurate epoch comparison and preserved IMPACT badges."""
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
                title = e.get("title", "")
                if self.risk_engine.is_symbol_impacted_by_event(curr, cntry, title):
                    filtered.append(e)
            events = filtered

        # Standard UTC epoch timestamp in seconds
        now_utc_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
        current_date = None
        today = datetime.date.today()
        today_row = -1

        is_d = getattr(self.window, "is_dark_theme", False)

        for e in events:
            sort_key = e.get("sort_key", 0.0)
            try:
                # Convert UTC epoch to local date for section headers
                dt_local = datetime.datetime.fromtimestamp(sort_key, tz=datetime.timezone.utc).astimezone()
                event_date = dt_local.date()
            except Exception:
                event_date = today

            if event_date != current_date:
                current_date = event_date
                if event_date == today:
                    today_row = t.rowCount()
                self._insert_date_separator(t.rowCount(), event_date)

            row = t.rowCount()
            t.insertRow(row)
            t.setRowHeight(row, 24)

            # ACCURATE PAST CHECK: Event is in the past if sort_key was > 60 seconds ago in UTC epoch
            is_past = (sort_key < (now_utc_ts - 60))

            text_alpha = "#64748b" if is_past else ("#f8fafc" if is_d else "#0f172a")

            # Col 0: Synchronized Timezone Event Time
            from backend.core.timezone_manager import timezone_manager
            sort_key = e.get("sort_key", 0.0)
            if sort_key > 0:
                time_str = timezone_manager.format_utc_ts(sort_key, "%H:%M")
            else:
                time_str = e.get("time", "").split(" ")[-1]
            cell_w = self._cell(time_str, color=text_alpha, bold=True, font="Consolas")
            cell_w.setProperty("sort_key", sort_key)
            t.setCellWidget(row, 0, cell_w)

            # Col 1: CURR
            t.setCellWidget(row, 1, self._country_badge(e.get("country", "US"), is_past=is_past))

            # Col 2: IMPACT (PRESERVES HIGH / MED / LOW with dimmed colors for past)
            t.setCellWidget(row, 2, self._impact_badge(e.get("impact", 0), is_past=is_past))

            # Col 3: EVENT RELEASE
            lbl_title = QLabel(f" {e.get('title', '')}")
            lbl_title.setStyleSheet(f"font-size: 10.5px; font-weight: {'400' if is_past else '500'}; color: {text_alpha};")
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
                        act_col = "#22c55e" if not is_past else "#15803d"
                        surprise_col = "#22c55e" if not is_past else "#15803d"
                        surprise_text = f"{sign}{diff:.1f} ▲"
                    elif diff < -0.0001:
                        act_col = "#ef4444" if not is_past else "#b91c1c"
                        surprise_col = "#ef4444" if not is_past else "#b91c1c"
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
        """Prioritizes the next upcoming Tier-2 event for the active target asset (XAUUSD)."""
        t = self.table
        now_utc_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
        curr_sym = self._current_symbol.upper()

        best_target_row = -1
        min_target_gap = float("inf")
        best_any_row = -1
        min_any_gap = float("inf")

        for r in range(t.rowCount()):
            item = t.item(r, 0)
            if not item:
                continue
            e = item.data(Qt.UserRole)
            if not e:
                continue

            sort_key = e.get("sort_key", 0.0)
            impact = e.get("impact", 0)
            cntry = e.get("country", "")
            title = e.get("title", "")

            # Future events only
            if sort_key >= (now_utc_ts - 60):
                gap = sort_key - now_utc_ts
                if impact == 2:
                    # Check if event impacts target asset directly (e.g. US -> XAUUSD)
                    if self.risk_engine.is_symbol_impacted_by_event(curr_sym, cntry, title):
                        if gap < min_target_gap:
                            min_target_gap = gap
                            best_target_row = r
                    if gap < min_any_gap:
                        min_any_gap = gap
                        best_any_row = r

        if best_target_row != -1:
            t.selectRow(best_target_row)
        elif best_any_row != -1:
            t.selectRow(best_any_row)
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
        """Refreshes the right desk with selected event details and target asset relevance."""
        cntry = event.get("country", "US")
        title = event.get("title", "")
        time_str = event.get("time", "")
        impact = event.get("impact", 0)

        self.lbl_next_event_title.setText(f"{cntry} · {title.upper()}")
        from backend.core.timezone_manager import timezone_manager
        sort_key = event.get("sort_key", 0.0)
        self._last_next_event_utc = sort_key
        if sort_key > 0:
            time_str = timezone_manager.format_utc_ts(sort_key, "%H:%M")
        else:
            time_str = event.get("time", "")
        self.lbl_next_event_time.setText(f"SCHEDULED: {time_str} ({timezone_manager.short_label})")

        # Target relevance badge
        curr_sym = self._current_symbol.upper()
        is_direct = self.risk_engine.is_symbol_impacted_by_event(curr_sym, cntry, title)
        if is_direct:
            self.badge_target_relevance.setText(f"TARGET: DIRECT ({curr_sym})")
            self.badge_target_relevance.setStyleSheet(
                "background-color: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3); "
                "font-family: Consolas; font-size: 8.5px; font-weight: bold; padding: 1px 4px; border-radius: 2px; border: none;"
            )
        else:
            self.badge_target_relevance.setText(f"TARGET: INDIRECT ({cntry})")
            self.badge_target_relevance.setStyleSheet(
                "background-color: rgba(148, 163, 184, 0.15); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.3); "
                "font-family: Consolas; font-size: 8.5px; font-weight: bold; padding: 1px 4px; border-radius: 2px; border: none;"
            )

        # Affected Assets mapping
        affected = []
        cur = COUNTRY_CURRENCY_MAP.get(cntry, cntry)
        if cur:
            affected.append(f"{cur} PAIRS")
        if cntry.upper() == "US":
            affected.extend(["XAUUSD (GOLD)", "US30", "NAS100", "BTCUSD"])

        self.lbl_desk_assets.setText("AFFECTED ASSETS: " + (", ".join(affected) if affected else f"{cntry} DOMESTIC"))

        # Update quantitative assessment card for clicked event
        self._update_quant_action_card(event)

        # Update countdown immediately
        self._on_clock_tick()

    def _update_quant_action_card(self, event: dict):
        """Populates Section 4 with clear quantitative assessment and target symbol impact."""
        if not hasattr(self, "lbl_qa_event_name") or not event:
            return

        cntry = event.get("country", "US")
        title = event.get("title", "Event")
        actual = str(event.get("actual", "")).strip()
        forecast = str(event.get("forecast", "")).strip()
        prev = str(event.get("previous", "")).strip()
        surprise = event.get("surprise", 0.0)
        curr_sym = self._current_symbol.upper()

        self.lbl_qa_event_name.setText(f"EVENT: {cntry} · {title.upper()}")

        # When event has actual data released
        if actual and actual != "--" and actual != "None":
            surp_str = f"ACTUAL: {actual}  |  FORECAST: {forecast or '--'}  |  SURPRISE: {surprise:+.2f}"
            self.lbl_qa_surprise.setText(surp_str)

            title_l = title.lower()
            if cntry.upper() == "US":
                if "claims" in title_l or "unemploy" in title_l:
                    is_usd_positive = (surprise < 0)
                elif "cpi" in title_l or "ppi" in title_l or "inflation" in title_l:
                    is_usd_positive = (surprise > 0)
                elif "pmi" in title_l or "gdp" in title_l or "retail" in title_l:
                    is_usd_positive = (surprise > 0)
                else:
                    is_usd_positive = (surprise > 0)

                if is_usd_positive:
                    eval_msg = "• Đánh giá AI: Số liệu khả quan hơn kỳ vọng -> Củng cố sức mạnh đồng USD."
                    impact_msg = f"• Tác động {curr_sym}: Áp lực điều chỉnh giảm ngắn hạn. Không nhồi lệnh Mua khi chưa tạo đáy nến mới."
                    color = "#ef4444"
                elif surprise != 0:
                    eval_msg = "• Đánh giá AI: Số liệu thấp hơn dự báo -> USD chịu áp lực giảm, dòng vốn ưu tiên tài sản trú ẩn."
                    impact_msg = f"• Tác động {curr_sym}: Hỗ trợ đà tăng (Bullish). Ưu tiên setup Mua theo xu hướng."
                    color = "#22c55e"
                else:
                    eval_msg = "• Đánh giá AI: Số liệu sát kỳ vọng thị trường -> Không gây sốc thanh khoản."
                    impact_msg = f"• Tác động {curr_sym}: Biến động kỹ thuật bình thường, tuân thủ cấu trúc biểu đồ M15."
                    color = "#0284c7"
            else:
                eval_msg = f"• Đánh giá AI: Dữ liệu kinh tế {cntry} {'tích cực' if surprise > 0 else 'tiêu cực'} so với dự báo."
                impact_msg = f"• Tác động {curr_sym}: Tác động gián tiếp qua tỷ giá chéo, duy trì kiểm soát rủi ro thông thường."
                color = "#0284c7"
        else:
            # Upcoming scheduled release
            self.lbl_qa_surprise.setText(f"DỰ BÁO: {forecast or 'Chưa có'}  |  KỲ TRƯỚC: {prev or '--'}")
            eval_msg = "• Đánh giá AI: Sự kiện đang được giám sát chặt chẽ trong cửa sổ rủi ro."
            impact_msg = f"• Kịch bản {curr_sym}: Tự động kích hoạt khiên T-15M khi đồng hồ đếm ngược bước vào 15 phút trước giờ tin."
            color = "#f59e0b"

        self.lbl_qa_ai_insight.setText(eval_msg)
        self.lbl_qa_asset_impact.setText(impact_msg)
        self.lbl_qa_asset_impact.setStyleSheet(f"font-size: 9.5px; color: {color}; font-weight: 600; border: none;")

    def _on_clock_tick(self):
        """1-second timer tick for countdown and active defense monitoring (Pure UTC epoch)."""
        if not hasattr(self, "lbl_countdown_val"):
            return

        event = getattr(self, "_selected_event", None)
        if not event:
            return

        sort_key = event.get("sort_key", 0.0)
        # Standard UTC timestamp
        now_utc_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
        diff_sec = int(sort_key - now_utc_ts)

        impact = event.get("impact", 0)

        if diff_sec > 0:
            hrs = diff_sec // 3600
            mins = (diff_sec % 3600) // 60
            secs = diff_sec % 60
            self.lbl_countdown_val.setText(f"T - {hrs:02d}:{mins:02d}:{secs:02d}")

            # Within T-15m defense window
            if diff_sec <= 900 and impact == 2:
                if self._override_active:
                    self.lbl_countdown_val.setStyleSheet("color: #f59e0b; font-family: Consolas; font-size: 20px; font-weight: 900; border: none;")
                    self.lbl_lockout_status.setText("STATUS: OVERRIDE ACTIVE (TRADING ALLOWED)")
                    self.lbl_lockout_status.setStyleSheet("color: #f59e0b; font-family: Consolas; font-size: 9.5px; font-weight: bold; border: none;")
                else:
                    self.lbl_countdown_val.setStyleSheet("color: #ef4444; font-family: Consolas; font-size: 20px; font-weight: 900; border: none;")
                    self.lbl_lockout_status.setText("STATUS: T-15M DEFENSE ARMED (ORDERS LOCKED)")
                    self.lbl_lockout_status.setStyleSheet("color: #ef4444; font-family: Consolas; font-size: 9.5px; font-weight: bold; border: none;")
            else:
                self.lbl_countdown_val.setStyleSheet("color: #22c55e; font-family: Consolas; font-size: 20px; font-weight: 900; border: none;")
                self.lbl_lockout_status.setText("STATUS: MONITORING · WINDOW CLEAR")
                self.lbl_lockout_status.setStyleSheet("color: #22c55e; font-family: Consolas; font-size: 9.5px; font-weight: bold; border: none;")
        else:
            abs_past = abs(diff_sec)
            mins_past = abs_past // 60
            self.lbl_countdown_val.setText(f"T + {mins_past:02d}M AGO")
            self.lbl_countdown_val.setStyleSheet("color: #64748b; font-family: Consolas; font-size: 20px; font-weight: 900; border: none;")
            if abs_past <= 900 and impact == 2 and not self._override_active:
                self.lbl_lockout_status.setText("STATUS: POST-NEWS SPREAD RECOVERY")
                self.lbl_lockout_status.setStyleSheet("color: #f59e0b; font-family: Consolas; font-size: 9.5px; font-weight: bold; border: none;")
            else:
                self.lbl_lockout_status.setText("STATUS: RELEASED · SPREAD NORMALIZED")
                self.lbl_lockout_status.setStyleSheet("color: #22c55e; font-family: Consolas; font-size: 9.5px; font-weight: bold; border: none;")

    def _handle_force_defense(self):
        """Immediately triggers pre-news active position defense via MacroContextBus."""
        try:
            from backend.core.macro_context_bus import MacroContextBus
            results = MacroContextBus.get_instance().trigger_force_defense()
            self.lbl_lockout_status.setText(f"DEFENSE TRIGGERED: {len(results)} POSITIONS SECURED")
            self.lbl_lockout_status.setStyleSheet("color: #f59e0b; font-family: Consolas; font-size: 9.5px; font-weight: bold; border: none;")
        except Exception as e:
            logger.warning(f"[MacroCalendar] Force defense trigger error: {e}")

    def _handle_override_toggle(self, checked):
        """Toggles semi-auto manual lockout override."""
        self._override_active = checked
        try:
            from backend.core.macro_context_bus import MacroContextBus
            MacroContextBus.get_instance().set_manual_override(checked)
        except Exception as e:
            logger.debug(f"[MacroCalendar] Bus override error: {e}")

        if checked:
            self.lbl_override_note.setText("OVERRIDE ACTIVE: MANUAL TRADING UNLOCKED")
            self.lbl_override_note.setStyleSheet("color: #ef4444; font-family: Consolas; font-size: 8.5px; font-weight: bold; border: none;")
        else:
            self.lbl_override_note.setText("RULE: ±15M BLACKOUT ENFORCED BY DEFAULT")
            is_d = getattr(self.window, "is_dark_theme", False)
            self.lbl_override_note.setStyleSheet(f"color: {'#94a3b8' if is_d else '#64748b'}; font-family: Consolas; font-size: 8.5px; border: none;")
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
        lay.setContentsMargins(6, 0, 6, 0)
        lay.setSpacing(4)
        lay.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        thu = WEEKDAYS_EN[date_obj.weekday()]
        date_str = date_obj.strftime("%d/%m/%Y")
        lbl_date = QLabel(f"{thu}  ·  {date_str}")
        lbl_date.setStyleSheet("font-family: Consolas; font-size: 10px; font-weight: bold; color: #38bdf8;")
        lay.addWidget(lbl_date)

        if is_today:
            lbl_badge = QLabel("TODAY")
            lbl_badge.setStyleSheet(
                "background-color: #22c55e; color: #ffffff; border-radius: 2px; padding: 1px 4px; "
                "font-family: Consolas; font-size: 8.5px; font-weight: bold;"
            )
            lay.addWidget(lbl_badge)

        t.setCellWidget(row, 0, w)
        t.setRowHeight(row, 22)

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
            col = "#334155"
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(1, 1, 1, 1)
        lbl = QLabel(country.upper())
        opacity = "color: #94a3b8;" if is_past else "color: #ffffff;"
        lbl.setStyleSheet(
            f"background-color: {col}; {opacity} font-family: Consolas; font-size: 9px; "
            "font-weight: bold; border-radius: 2px; padding: 1px 3px;"
        )
        lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(lbl, alignment=Qt.AlignCenter)
        return w

    def _impact_badge(self, impact: int, is_past: bool = False):
        """Preserves HIGH/MED/LOW impact rating, only changes alpha/color intensity for past events."""
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(1, 1, 1, 1)

        if impact == 2:
            lbl_text = "HIGH"
            bg_col = "#7f1d1d" if is_past else "#ef4444"
            fg_col = "#fca5a5" if is_past else "#ffffff"
        elif impact == 1:
            lbl_text = "MED"
            bg_col = "#78350f" if is_past else "#f59e0b"
            fg_col = "#fcd34d" if is_past else "#000000"
        else:
            lbl_text = "LOW"
            bg_col = "#1e293b" if is_past else "#334155"
            fg_col = "#64748b" if is_past else "#94a3b8"

        lbl = QLabel(lbl_text)
        lbl.setStyleSheet(
            f"background-color: {bg_col}; color: {fg_col}; font-family: Consolas; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 1px 4px;"
        )
        lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(lbl, alignment=Qt.AlignCenter)
        return w

    def _cell(self, text, color=None, bold=False, font="Segoe UI", align=Qt.AlignCenter):
        val = str(text) if text not in ("None", "none", "", None) else "-"
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(3, 0, 3, 0)
        lbl = QLabel(val)

        is_d = getattr(self.window, "is_dark_theme", False)
        if not color:
            color = "#f8fafc" if is_d else "#0f172a"

        weight = "bold" if bold else "normal"
        lbl.setStyleSheet(f"color: {color}; font-family: '{font}', monospace; font-size: 10px; font-weight: {weight}; border: none;")
        lbl.setAlignment(align | Qt.AlignVCenter)
        lay.addWidget(lbl)
        return w

    def update_theme(self, is_dark: bool):
        """Applies theme colors to the entire workspace without breaking layout containment."""
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
                    f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 2px; padding: 2px 6px; }}"
                )

        if hasattr(self, "frame_countdown") and self.frame_countdown:
            self.frame_countdown.setStyleSheet(f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 2px; padding: 6px; }}")
        if hasattr(self, "frame_protocol") and self.frame_protocol:
            self.frame_protocol.setStyleSheet(f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 2px; padding: 6px; }}")
        if hasattr(self, "frame_actions") and self.frame_actions:
            self.frame_actions.setStyleSheet(f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 2px; padding: 6px; }}")
        if hasattr(self, "frame_quant_action") and self.frame_quant_action:
            self.frame_quant_action.setStyleSheet(f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 2px; padding: 6px; }}")

    def _on_timezone_changed(self, tz_key: str):
        """Synchronizes calendar column header and row time cells when global timezone changes."""
        try:
            from backend.core.timezone_manager import timezone_manager
            if hasattr(self, "table") and self.table:
                # Update Column 0 Header
                header_item = self.table.horizontalHeaderItem(0)
                if header_item:
                    header_item.setText(timezone_manager.cal_header)

                # Update all rendered rows in Column 0
                for r in range(self.table.rowCount()):
                    w = self.table.cellWidget(r, 0)
                    if w:
                        sk = w.property("sort_key")
                        if sk and sk > 0:
                            lbl = w.findChild(QLabel)
                            if lbl:
                                lbl.setText(timezone_manager.format_utc_ts(sk, "%H:%M"))
                            elif isinstance(w, QLabel):
                                w.setText(timezone_manager.format_utc_ts(sk, "%H:%M"))

            # Update Scheduled Next Event Label
            if hasattr(self, "lbl_next_event_time") and hasattr(self, "_last_next_event_utc") and self._last_next_event_utc > 0:
                time_str = timezone_manager.format_utc_ts(self._last_next_event_utc, "%H:%M")
                tz_lbl = timezone_manager.short_label
                self.lbl_next_event_time.setText(f"SCHEDULED: {time_str} ({tz_lbl})")
        except Exception as e:
            logger.debug(f"[MacroCalendar] _on_timezone_changed error: {e}")


# Backward compatibility alias
MacroCalendarController = CalendarManager
