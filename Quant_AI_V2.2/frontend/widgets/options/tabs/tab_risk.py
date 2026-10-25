"""
Tab 1: Risk Limits & Safeguards Configuration Widget.
Responsible for user configuration of position sizing risks, maximum daily drawdown,
and consecutive loss circuit breakers.
Compact MT5-style institutional layout.
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
        layout_main.setContentsMargins(8, 8, 8, 8)
        layout_main.setSpacing(8)

        # 1. Position & Drawdown Limits
        grp_pos = QGroupBox("Position Limits")
        lay_pos = QVBoxLayout(grp_pos)
        lay_pos.setContentsMargins(8, 10, 8, 8)
        lay_pos.setSpacing(6)

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
        self.spinMaxOpenTrades.setSuffix(" trades")

        lay_pos.addWidget(self._create_row("Risk / Trade:", self.spinRiskPerTrade))
        lay_pos.addWidget(self._create_row("Max Drawdown:", self.spinMaxDrawdown))
        lay_pos.addWidget(self._create_row("Max Trades:", self.spinMaxOpenTrades))

        # 2. Daily Loss & Circuit Breaker
        grp_daily = QGroupBox("Daily Protection")
        lay_daily = QVBoxLayout(grp_daily)
        lay_daily.setContentsMargins(8, 10, 8, 8)
        lay_daily.setSpacing(6)

        self.spinMaxDailyLoss = QDoubleSpinBox()
        self.spinMaxDailyLoss.setRange(50.0, 50000.0)
        self.spinMaxDailyLoss.setSingleStep(50.0)
        self.spinMaxDailyLoss.setPrefix("$ ")

        self.spinMaxLosingStreak = QSpinBox()
        self.spinMaxLosingStreak.setRange(1, 20)
        self.spinMaxLosingStreak.setSuffix(" losses")

        self.chkEnforceDailyHalt = QCheckBox("Stop trading on breach")
        self.chkEnforceDailyHalt.setChecked(True)

        lay_daily.addWidget(self._create_row("Daily Loss Limit:", self.spinMaxDailyLoss))
        lay_daily.addWidget(self._create_row("Max Loss Streak:", self.spinMaxLosingStreak))
        lay_daily.addWidget(self._create_row("Auto Halt:", self.chkEnforceDailyHalt))

        layout_main.addWidget(grp_pos)
        layout_main.addWidget(grp_daily)
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
