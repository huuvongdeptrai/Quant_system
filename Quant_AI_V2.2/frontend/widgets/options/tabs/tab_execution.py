"""
Tab 2: Execution Strategy & Trade Parameters Configuration Widget.
Responsible for user configuration of strategy selection, timeframe, trading sessions,
slippage tolerance, trailing stops, and pre-news defense.
Compact MT5-style institutional layout with sleek sub-tab segmented navigation.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSpinBox,
    QDoubleSpinBox, QCheckBox, QGroupBox, QTabWidget
)
from typing import Dict, Any
from loguru import logger


class ExecutionSettingsTab(QWidget):
    """UI tab component for strategy selection, sessions, and execution defense."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _create_row(self, label_text: str, widget: QWidget, label_width: int = 120) -> QWidget:
        row = QWidget()
        r_lay = QHBoxLayout(row)
        r_lay.setContentsMargins(0, 0, 0, 0)
        r_lay.setSpacing(10)

        lbl = QLabel(label_text)
        lbl.setFixedWidth(label_width)
        lbl.setStyleSheet("font-family: 'Segoe UI', sans-serif; font-size: 11px; color: #334155;")
        r_lay.addWidget(lbl)

        if hasattr(widget, "setFixedHeight"):
            widget.setFixedHeight(23)
        r_lay.addWidget(widget, 1)
        return row

    def _setup_ui(self):
        layout_main = QVBoxLayout(self)
        layout_main.setContentsMargins(4, 4, 4, 4)
        layout_main.setSpacing(4)

        # Sub-Tab Navigation Bar (MT5 Sub-Tabs Pattern)
        self.subTabWidget = QTabWidget()
        self.subTabWidget.setObjectName("executionSubTabWidget")

        # ----------------------------------------------------------------------
        # Sub-Tab 1: Strategy & Mode
        # ----------------------------------------------------------------------
        tab_strat = QWidget()
        lay_strat = QVBoxLayout(tab_strat)
        lay_strat.setContentsMargins(8, 10, 8, 8)
        lay_strat.setSpacing(8)

        self.comboStrategy = QComboBox()
        try:
            from backend.core.strategies.strategy_loader import discover_strategies
            strats = discover_strategies()
            clean_names = {
                "builtin_ict_pro": "ICT Zones Pro v4.2",
                "builtin_ema_stress": "EMA Dual Cross",
                "builtin_wyckoff": "Wyckoff Momentum Pro",
            }
            for s in strats:
                s_id = s.get("id", "")
                display_name = clean_names.get(s_id, s.get("name", s_id))
                self.comboStrategy.addItem(display_name, s_id)
        except (ImportError, AttributeError) as err:
            logger.debug(f"[ExecutionSettingsTab] Strategy loader fallback: {err}")
            self.comboStrategy.addItem("ICT Zones Pro v4.2", "builtin_ict_pro")
            self.comboStrategy.addItem("EMA Dual Cross", "builtin_ema_stress")
            self.comboStrategy.addItem("Wyckoff Momentum Pro", "builtin_wyckoff")

        self.comboTradingTimeframe = QComboBox()
        self.comboTradingTimeframe.addItem("M1 (1 Min)", 1)
        self.comboTradingTimeframe.addItem("M5 (5 Mins)", 5)
        self.comboTradingTimeframe.addItem("M15 (15 Mins)", 15)
        self.comboTradingTimeframe.addItem("M30 (30 Mins)", 30)
        self.comboTradingTimeframe.addItem("H1 (1 Hour)", 60)
        self.comboTradingTimeframe.addItem("H4 (4 Hours)", 240)
        self.comboTradingTimeframe.addItem("D1 (Daily)", 1440)
        self.comboTradingTimeframe.addItem("W1 (Weekly)", 10080)
        self.comboTradingTimeframe.addItem("MN1 (Monthly)", 43200)
        self.comboTradingTimeframe.addItem("Chart TF", "FOLLOW_CHART")

        self.comboExecutionMode = QComboBox()
        self.comboExecutionMode.addItem("Full Auto", "FULL-AUTO")
        self.comboExecutionMode.addItem("Semi Auto", "SEMI-AUTO")
        self.comboExecutionMode.addItem("Manual (Alerts)", "MANUAL")

        self.spinSignalExpiry = QSpinBox()
        self.spinSignalExpiry.setRange(10, 600)
        self.spinSignalExpiry.setSingleStep(5)
        self.spinSignalExpiry.setSuffix(" sec")
        self.spinSignalExpiry.setValue(60)

        lay_strat.addWidget(self._create_row("Strategy:", self.comboStrategy))
        lay_strat.addWidget(self._create_row("Timeframe:", self.comboTradingTimeframe))
        lay_strat.addWidget(self._create_row("Mode:", self.comboExecutionMode))
        lay_strat.addWidget(self._create_row("Signal Expiry:", self.spinSignalExpiry))
        lay_strat.addStretch()

        # ----------------------------------------------------------------------
        # Sub-Tab 2: Trading Sessions
        # ----------------------------------------------------------------------
        tab_sess = QWidget()
        lay_sess = QVBoxLayout(tab_sess)
        lay_sess.setContentsMargins(8, 10, 8, 8)
        lay_sess.setSpacing(8)

        self.chkSessionAsian = QCheckBox("Active")
        self.chkSessionLondon = QCheckBox("Active")
        self.chkSessionNY = QCheckBox("Active")
        self.chkCloseFriday = QCheckBox("Close before weekend")

        lay_sess.addWidget(self._create_row("Tokyo (Asia):", self.chkSessionAsian))
        lay_sess.addWidget(self._create_row("London:", self.chkSessionLondon))
        lay_sess.addWidget(self._create_row("New York:", self.chkSessionNY))
        lay_sess.addWidget(self._create_row("Friday Close:", self.chkCloseFriday))
        lay_sess.addStretch()

        # ----------------------------------------------------------------------
        # Sub-Tab 3: Protection & Defense
        # ----------------------------------------------------------------------
        tab_def = QWidget()
        lay_def = QVBoxLayout(tab_def)
        lay_def.setContentsMargins(8, 10, 8, 8)
        lay_def.setSpacing(6)

        self.spinMaxSpread = QSpinBox()
        self.spinMaxSpread.setRange(1, 200)
        self.spinMaxSpread.setSuffix(" pts")

        self.spinSlippage = QSpinBox()
        self.spinSlippage.setRange(1, 100)
        self.spinSlippage.setSuffix(" pts")

        self.spinBreakevenPips = QSpinBox()
        self.spinBreakevenPips.setRange(0, 100)
        self.spinBreakevenPips.setSpecialValueText("OFF")
        self.spinBreakevenPips.setSuffix(" pts")

        self.spinTrailingPips = QSpinBox()
        self.spinTrailingPips.setRange(0, 100)
        self.spinTrailingPips.setSpecialValueText("OFF")
        self.spinTrailingPips.setSuffix(" pts")

        self.spinNewsDefenseMins = QSpinBox()
        self.spinNewsDefenseMins.setRange(0, 60)
        self.spinNewsDefenseMins.setSpecialValueText("OFF")
        self.spinNewsDefenseMins.setValue(15)
        self.spinNewsDefenseMins.setSuffix(" min")

        self.spinNewsDefenseR = QDoubleSpinBox()
        self.spinNewsDefenseR.setRange(0.5, 5.0)
        self.spinNewsDefenseR.setSingleStep(0.25)
        self.spinNewsDefenseR.setValue(1.5)
        self.spinNewsDefenseR.setSuffix(" R")

        # Hidden proxies for legacy compatibility
        self.chkEnableTrailing = QCheckBox("Enable Trailing Stop")
        self.chkNewsDefense = QCheckBox("Active Defense")

        lay_def.addWidget(self._create_row("Max Spread:", self.spinMaxSpread))
        lay_def.addWidget(self._create_row("Max Slippage:", self.spinSlippage))
        lay_def.addWidget(self._create_row("Breakeven:", self.spinBreakevenPips))
        lay_def.addWidget(self._create_row("Trailing Stop:", self.spinTrailingPips))
        lay_def.addWidget(self._create_row("News Defense:", self.spinNewsDefenseMins))
        lay_def.addWidget(self._create_row("BE Target (R):", self.spinNewsDefenseR))
        lay_def.addStretch()

        self.subTabWidget.addTab(tab_strat, "Strategy")
        self.subTabWidget.addTab(tab_sess, "Sessions")
        self.subTabWidget.addTab(tab_def, "Defense")

        layout_main.addWidget(self.subTabWidget)

    def load_values(self, data: Dict[str, Any], defaults: Dict[str, Any]) -> None:
        """Populates execution controls from settings dictionary."""
        strat = data.get("strategy", defaults.get("strategy", "builtin_ict_pro"))
        idx_s = self.comboStrategy.findData(strat)
        if idx_s < 0:
            s_low = str(strat).lower()
            if "ict" in s_low:
                idx_s = self.comboStrategy.findData("builtin_ict_pro")
            elif "ema" in s_low:
                idx_s = self.comboStrategy.findData("builtin_ema_stress")
            elif "wyckoff" in s_low:
                idx_s = self.comboStrategy.findData("builtin_wyckoff")
        if idx_s >= 0:
            self.comboStrategy.setCurrentIndex(idx_s)

        tf = data.get("timeframe", 15)
        idx_tf = self.comboTradingTimeframe.findData(tf)
        if idx_tf >= 0:
            self.comboTradingTimeframe.setCurrentIndex(idx_tf)

        m = data.get("execution_mode", defaults["execution_mode"])
        idx = self.comboExecutionMode.findData(m)
        if idx >= 0:
            self.comboExecutionMode.setCurrentIndex(idx)

        self.spinMaxSpread.setValue(int(data.get("max_spread", defaults["max_spread"])))
        self.spinSlippage.setValue(int(data.get("slippage", defaults["slippage"])))
        self.spinSignalExpiry.setValue(int(data.get("signal_expiry_sec", defaults["signal_expiry_sec"])))

        ts_enabled = bool(data.get("enable_trailing_stop", defaults.get("enable_trailing_stop", False)))
        self.chkEnableTrailing.setChecked(ts_enabled)
        if ts_enabled:
            self.spinBreakevenPips.setValue(int(data.get("breakeven_pips", defaults["breakeven_pips"])))
            self.spinTrailingPips.setValue(int(data.get("trailing_pips", defaults["trailing_pips"])))
        else:
            self.spinBreakevenPips.setValue(0)
            self.spinTrailingPips.setValue(0)

        news_enabled = bool(data.get("news_defense_enabled", defaults.get("news_defense_enabled", True)))
        self.chkNewsDefense.setChecked(news_enabled)
        if news_enabled:
            self.spinNewsDefenseMins.setValue(int(data.get("news_defense_mins", defaults.get("news_defense_mins", 15))))
        else:
            self.spinNewsDefenseMins.setValue(0)
        self.spinNewsDefenseR.setValue(float(data.get("news_defense_be_r", defaults.get("news_defense_be_r", 1.5))))

        self.chkSessionAsian.setChecked(bool(data.get("session_asian", defaults["session_asian"])))
        self.chkSessionLondon.setChecked(bool(data.get("session_london", defaults["session_london"])))
        self.chkSessionNY.setChecked(bool(data.get("session_ny", defaults["session_ny"])))
        self.chkCloseFriday.setChecked(bool(data.get("close_friday", defaults["close_friday"])))

    def get_values(self) -> Dict[str, Any]:
        """Extracts current execution and session settings."""
        is_ts_active = (self.spinBreakevenPips.value() > 0 or self.spinTrailingPips.value() > 0)
        is_news_active = (self.spinNewsDefenseMins.value() > 0)

        return {
            "strategy": self.comboStrategy.currentData() or "builtin_ict_pro",
            "timeframe": self.comboTradingTimeframe.currentData(),
            "execution_mode": self.comboExecutionMode.currentData(),
            "max_spread": self.spinMaxSpread.value(),
            "slippage": self.spinSlippage.value(),
            "signal_expiry_sec": self.spinSignalExpiry.value(),
            "enable_trailing_stop": is_ts_active,
            "breakeven_pips": self.spinBreakevenPips.value(),
            "trailing_pips": self.spinTrailingPips.value(),
            "news_defense_enabled": is_news_active,
            "news_defense_mins": self.spinNewsDefenseMins.value(),
            "news_defense_be_r": self.spinNewsDefenseR.value(),
            "session_asian": self.chkSessionAsian.isChecked(),
            "session_london": self.chkSessionLondon.isChecked(),
            "session_ny": self.chkSessionNY.isChecked(),
            "close_friday": self.chkCloseFriday.isChecked(),
        }
