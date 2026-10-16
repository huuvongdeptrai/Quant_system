"""
Tab 1: Risk Limits & Safeguards Configuration Widget.
Responsible for user configuration of position sizing risks, maximum daily drawdown,
and consecutive loss circuit breakers.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, QSpinBox,
    QCheckBox, QGroupBox
)
from typing import Dict, Any


class RiskSettingsTab(QWidget):
    """UI tab component for capital preservation and risk parameters."""

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
        layout_main.setContentsMargins(14, 12, 14, 12)
        layout_main.setSpacing(10)

        lbl_desc = QLabel("Account risk limits, daily loss threshold, and maximum drawdown safeguards.")
        lbl_desc.setStyleSheet("color: #64748b; font-family: 'Segoe UI', sans-serif; font-size: 11px;")
        layout_main.addWidget(lbl_desc)

        cols = QWidget()
        cols_lay = QHBoxLayout(cols)
        cols_lay.setContentsMargins(0, 0, 0, 0)
        cols_lay.setSpacing(14)

        # Left Column: Position & Drawdown
        grp_pos = QGroupBox("POSITION && DRAWDOWN LIMITS")
        lay_pos = QVBoxLayout(grp_pos)
        lay_pos.setContentsMargins(10, 14, 10, 10)
        lay_pos.setSpacing(8)

        self.spinRiskPerTrade = QDoubleSpinBox()
        self.spinRiskPerTrade.setRange(0.1, 10.0)
        self.spinRiskPerTrade.setSingleStep(0.25)
        self.spinRiskPerTrade.setSuffix(" %")

        self.spinMaxDrawdown = QDoubleSpinBox()
        self.spinMaxDrawdown.setRange(1.0, 30.0)
        self.spinMaxDrawdown.setSingleStep(0.5)
        self.spinMaxDrawdown.setSuffix(" %")

        self.spinMaxOpenTrades = QSpinBox()
        self.spinMaxOpenTrades.setRange(1, 20)
        self.spinMaxOpenTrades.setSuffix(" positions")

        lay_pos.addWidget(self._create_row("Risk Per Trade:", self.spinRiskPerTrade))
        lay_pos.addWidget(self._create_row("Max Equity DD:", self.spinMaxDrawdown))
        lay_pos.addWidget(self._create_row("Max Positions:", self.spinMaxOpenTrades))

        # Right Column: Daily Loss & Circuit Breaker
        grp_daily = QGroupBox("DAILY PROTECTION && CIRCUIT BREAKER")
        lay_daily = QVBoxLayout(grp_daily)
        lay_daily.setContentsMargins(10, 14, 10, 10)
        lay_daily.setSpacing(8)

        self.spinMaxDailyLoss = QDoubleSpinBox()
        self.spinMaxDailyLoss.setRange(50.0, 50000.0)
        self.spinMaxDailyLoss.setSingleStep(50.0)
        self.spinMaxDailyLoss.setPrefix("$ ")

        self.spinMaxLosingStreak = QSpinBox()
        self.spinMaxLosingStreak.setRange(1, 20)
        self.spinMaxLosingStreak.setSuffix(" trades")

        self.chkEnforceDailyHalt = QCheckBox("Halt trading on breach")
        self.chkEnforceDailyHalt.setChecked(True)

        lay_daily.addWidget(self._create_row("Max Daily Loss:", self.spinMaxDailyLoss))
        lay_daily.addWidget(self._create_row("Max Loss Streak:", self.spinMaxLosingStreak))
        lay_daily.addWidget(self._create_row("Daily Loss Action:", self.chkEnforceDailyHalt))

        cols_lay.addWidget(grp_pos)
        cols_lay.addWidget(grp_daily)
        layout_main.addWidget(cols)
        layout_main.addStretch()

    def load_values(self, data: Dict[str, Any], defaults: Dict[str, Any]) -> None:
        """Populates risk control widgets from settings dictionary."""
        self.spinRiskPerTrade.setValue(float(data.get("risk_per_trade", defaults["risk_per_trade"])))
        self.spinMaxDailyLoss.setValue(float(data.get("max_daily_loss", defaults["max_daily_loss"])))
        self.spinMaxDrawdown.setValue(float(data.get("max_drawdown", defaults["max_drawdown"])))
        self.spinMaxLosingStreak.setValue(int(data.get("max_losing_streak", defaults["max_losing_streak"])))
        self.spinMaxOpenTrades.setValue(int(data.get("max_open_trades", defaults["max_open_trades"])))

    def get_values(self) -> Dict[str, Any]:
        """Extracts current risk settings into a key-value dictionary."""
        return {
            "risk_per_trade": self.spinRiskPerTrade.value(),
            "max_daily_loss": self.spinMaxDailyLoss.value(),
            "max_drawdown": self.spinMaxDrawdown.value(),
            "max_losing_streak": self.spinMaxLosingStreak.value(),
            "max_open_trades": self.spinMaxOpenTrades.value(),
        }
