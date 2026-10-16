"""
Tab 2: Execution Strategy & Trade Parameters Configuration Widget.
Responsible for user configuration of strategy selection, timeframe, trading sessions,
slippage tolerance, trailing stops, and pre-news defense.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSpinBox,
    QDoubleSpinBox, QCheckBox, QGroupBox
)
from typing import Dict, Any
from loguru import logger


class ExecutionSettingsTab(QWidget):
    """UI tab component for strategy selection, sessions, and execution defense."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _create_row(self, label_text: str, widget: QWidget, label_width: int = 125) -> QWidget:
        row = QWidget()
        r_lay = QHBoxLayout(row)
        r_lay.setContentsMargins(0, 0, 0, 0)
        r_lay.setSpacing(10)

        lbl = QLabel(label_text)
        lbl.setFixedWidth(label_width)
        lbl.setStyleSheet("font-family: 'Segoe UI', sans-serif; font-size: 11px; color: #334155;")
        r_lay.addWidget(lbl)

        if hasattr(widget, "setFixedHeight"):
            widget.setFixedHeight(24)
        r_lay.addWidget(widget, 1)
        return row

    def _setup_ui(self):
        layout_main = QVBoxLayout(self)
        layout_main.setContentsMargins(14, 10, 14, 10)
        layout_main.setSpacing(8)

        lbl_desc = QLabel("Automated execution strategy, session filtering, and risk defense protocols.")
        lbl_desc.setStyleSheet("color: #64748b; font-family: 'Segoe UI', sans-serif; font-size: 11px;")
        layout_main.addWidget(lbl_desc)

        cols = QWidget()
        cols_lay = QHBoxLayout(cols)
        cols_lay.setContentsMargins(0, 0, 0, 0)
        cols_lay.setSpacing(14)

        # Left Column: Order Config & Sessions
        col_left = QWidget()
        lay_left = QVBoxLayout(col_left)
        lay_left.setContentsMargins(0, 0, 0, 0)
        lay_left.setSpacing(10)

        grp_order = QGroupBox("ORDER && STRATEGY CONFIG")
        lay_order = QVBoxLayout(grp_order)
        lay_order.setContentsMargins(10, 14, 10, 10)
        lay_order.setSpacing(8)

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
        self.comboTradingTimeframe.addItem("Follow Chart TF", "FOLLOW_CHART")

        self.comboExecutionMode = QComboBox()
        self.comboExecutionMode.addItem("Full-Auto (STP)", "FULL-AUTO")
        self.comboExecutionMode.addItem("Semi-Auto (Operator)", "SEMI-AUTO")
        self.comboExecutionMode.addItem("Manual (Alerts Only)", "MANUAL")

        lay_order.addWidget(self._create_row("Active Strategy:", self.comboStrategy))
        lay_order.addWidget(self._create_row("Trading Timeframe:", self.comboTradingTimeframe))
        lay_order.addWidget(self._create_row("Execution Mode:", self.comboExecutionMode))

        grp_sessions = QGroupBox("TRADING SESSIONS && SCHEDULE")
        lay_sessions = QVBoxLayout(grp_sessions)
        lay_sessions.setContentsMargins(10, 14, 10, 10)
        lay_sessions.setSpacing(8)

        self.chkSessionAsian = QCheckBox("Enabled (Tokyo)")
        self.chkSessionLondon = QCheckBox("Enabled (London)")
        self.chkSessionNY = QCheckBox("Enabled (New York)")
        self.chkCloseFriday = QCheckBox("Close on Friday EOD")

        lay_sessions.addWidget(self._create_row("Asian Session:", self.chkSessionAsian))
        lay_sessions.addWidget(self._create_row("London Session:", self.chkSessionLondon))
        lay_sessions.addWidget(self._create_row("New York Session:", self.chkSessionNY))
        lay_sessions.addWidget(self._create_row("Weekend Risk:", self.chkCloseFriday))

        lay_left.addWidget(grp_order)
        lay_left.addWidget(grp_sessions)

        # Right Column: Safety Tolerance & Dynamic Defense
        col_right = QWidget()
        lay_right = QVBoxLayout(col_right)
        lay_right.setContentsMargins(0, 0, 0, 0)
        lay_right.setSpacing(10)

        grp_safety = QGroupBox("SAFETY TOLERANCE")
        lay_safety = QVBoxLayout(grp_safety)
        lay_safety.setContentsMargins(10, 14, 10, 10)
        lay_safety.setSpacing(8)

        self.spinSignalExpiry = QSpinBox()
        self.spinSignalExpiry.setRange(10, 600)
        self.spinSignalExpiry.setSingleStep(5)
        self.spinSignalExpiry.setSuffix(" sec")
        self.spinSignalExpiry.setValue(60)

        self.spinMaxSpread = QSpinBox()
        self.spinMaxSpread.setRange(1, 200)
        self.spinMaxSpread.setSuffix(" points")

        self.spinSlippage = QSpinBox()
        self.spinSlippage.setRange(1, 100)
        self.spinSlippage.setSuffix(" points")

        lay_safety.addWidget(self._create_row("Signal Expiry:", self.spinSignalExpiry))
        lay_safety.addWidget(self._create_row("Max Spread Limit:", self.spinMaxSpread))
        lay_safety.addWidget(self._create_row("Slippage Tolerance:", self.spinSlippage))

        grp_defense = QGroupBox("DYNAMIC SL && RISK DEFENSE")
        lay_defense = QVBoxLayout(grp_defense)
        lay_defense.setContentsMargins(10, 14, 10, 10)
        lay_defense.setSpacing(8)

        self.chkEnableTrailing = QCheckBox("Enable Trailing Stop")
        self.chkNewsDefense = QCheckBox("Active Defense")

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

        lay_defense.addWidget(self._create_row("BE Offset:", self.spinBreakevenPips))
        lay_defense.addWidget(self._create_row("TS Distance:", self.spinTrailingPips))
        lay_defense.addWidget(self._create_row("Defense Window:", self.spinNewsDefenseMins))
        lay_defense.addWidget(self._create_row("BE Threshold (R):", self.spinNewsDefenseR))

        lay_right.addWidget(grp_safety)
        lay_right.addWidget(grp_defense)

        cols_lay.addWidget(col_left)
        cols_lay.addWidget(col_right)
        layout_main.addWidget(cols)
        layout_main.addStretch()

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
