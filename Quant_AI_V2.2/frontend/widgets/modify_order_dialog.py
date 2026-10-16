"""ModifyOrderDialog - Institutional PySide6 Dialog for modifying Stop Loss and Take Profit.

Follows MetaTrader 5 and cTrader standard design:
- Segoe UI labels and buttons
- Consolas monospace prices
- Pure flat geometry (radius 2px - 4px)
- Strict light & dark theme compatibility
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QDoubleSpinBox,
    QPushButton,
    QFrame,
)


class ModifyOrderDialog(QDialog):
    """Institutional Order Modification Dialog for MT5 positions."""

    def __init__(
        self,
        ticket: int,
        symbol: str,
        order_type: str,
        volume: float,
        open_price: float,
        current_price: float,
        current_sl: float = 0.0,
        current_tp: float = 0.0,
        digits: int = 2,
        is_dark: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.ticket = ticket
        self.symbol = symbol
        self.order_type = order_type.upper()
        self.volume = volume
        self.open_price = open_price
        self.current_price = current_price
        self.digits = digits
        self.is_dark = is_dark

        self.setWindowTitle(f"Order #{ticket} - Modify")
        self.setFixedSize(360, 260)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._setup_ui(current_sl, current_tp)
        self._apply_styling()

    def _setup_ui(self, current_sl: float, current_tp: float):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        # Header bar
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        lbl_title = QLabel(f"POSITION #{self.ticket}")
        lbl_title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        header_layout.addWidget(lbl_title)

        lbl_sym = QLabel(f"{self.symbol} · {self.order_type} {self.volume:.2f}L")
        lbl_sym.setFont(QFont("Consolas", 9, QFont.Bold))
        header_layout.addWidget(lbl_sym)
        header_layout.addStretch()

        main_layout.addLayout(header_layout)

        # Telemetry Card
        card = QFrame()
        card.setObjectName("cardOrderInfo")
        card_layout = QGridLayout(card)
        card_layout.setContentsMargins(10, 8, 10, 8)
        card_layout.setHorizontalSpacing(12)
        card_layout.setVerticalSpacing(4)

        lbl_open_tag = QLabel("Open Price:")
        lbl_open_tag.setFont(QFont("Segoe UI", 9))
        self.lbl_open_val = QLabel(f"{self.open_price:.{self.digits}f}")
        self.lbl_open_val.setFont(QFont("Consolas", 9, QFont.Bold))

        lbl_cur_tag = QLabel("Current Price:")
        lbl_cur_tag.setFont(QFont("Segoe UI", 9))
        self.lbl_cur_val = QLabel(f"{self.current_price:.{self.digits}f}")
        self.lbl_cur_val.setFont(QFont("Consolas", 9, QFont.Bold))

        card_layout.addWidget(lbl_open_tag, 0, 0)
        card_layout.addWidget(self.lbl_open_val, 0, 1)
        card_layout.addWidget(lbl_cur_tag, 1, 0)
        card_layout.addWidget(self.lbl_cur_val, 1, 1)

        main_layout.addWidget(card)

        # Parameter Form (SL & TP)
        form_frame = QFrame()
        form_layout = QGridLayout(form_frame)
        form_layout.setContentsMargins(0, 4, 0, 4)
        form_layout.setHorizontalSpacing(12)
        form_layout.setVerticalSpacing(8)

        lbl_sl = QLabel("Stop Loss (SL):")
        lbl_sl.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        self.spin_sl = QDoubleSpinBox()
        self.spin_sl.setDecimals(self.digits)
        self.spin_sl.setRange(0.0, 999999.0)
        self.spin_sl.setSingleStep(0.1 if self.digits <= 2 else 0.01)
        self.spin_sl.setValue(current_sl)
        self.spin_sl.setFont(QFont("Consolas", 9))
        self.spin_sl.setFixedHeight(26)

        lbl_tp = QLabel("Take Profit (TP):")
        lbl_tp.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        self.spin_tp = QDoubleSpinBox()
        self.spin_tp.setDecimals(self.digits)
        self.spin_tp.setRange(0.0, 999999.0)
        self.spin_tp.setSingleStep(0.1 if self.digits <= 2 else 0.01)
        self.spin_tp.setValue(current_tp)
        self.spin_tp.setFont(QFont("Consolas", 9))
        self.spin_tp.setFixedHeight(26)

        form_layout.addWidget(lbl_sl, 0, 0)
        form_layout.addWidget(self.spin_sl, 0, 1)
        form_layout.addWidget(lbl_tp, 1, 0)
        form_layout.addWidget(self.spin_tp, 1, 1)

        main_layout.addWidget(form_frame)
        main_layout.addStretch()

        # Bottom Button Bar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFont(QFont("Segoe UI", 9))
        self.btn_cancel.setFixedSize(76, 26)
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_modify = QPushButton("Modify")
        self.btn_modify.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.btn_modify.setFixedSize(86, 26)
        self.btn_modify.setCursor(Qt.PointingHandCursor)
        self.btn_modify.clicked.connect(self.accept)

        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_modify)

        main_layout.addLayout(btn_layout)

    def _apply_styling(self):
        if self.is_dark:
            self.setStyleSheet(
                """
                QDialog {
                    background-color: #0b0e17;
                    color: #f8fafc;
                }
                QLabel {
                    color: #94a3b8;
                }
                QFrame#cardOrderInfo {
                    background-color: #121520;
                    border: 1px solid #1e2433;
                    border-radius: 3px;
                }
                QDoubleSpinBox {
                    background-color: #121520;
                    color: #f8fafc;
                    border: 1px solid #272d3b;
                    border-radius: 2px;
                    padding: 2px 6px;
                }
                QDoubleSpinBox:focus {
                    border-color: #475569;
                }
                QPushButton {
                    background-color: #161b26;
                    color: #cbd5e1;
                    border: 1px solid #272d3b;
                    border-radius: 2px;
                }
                QPushButton:hover {
                    background-color: #1e2433;
                    color: #ffffff;
                }
                QPushButton#btnModify {
                    background-color: #047857;
                    color: #ffffff;
                    border: 1px solid #272d3b;
                }
                QPushButton#btnModify:hover {
                    background-color: #059669;
                }
                """
            )
        else:
            self.setStyleSheet(
                """
                QDialog {
                    background-color: #ffffff;
                    color: #0f172a;
                }
                QLabel {
                    color: #475569;
                }
                QFrame#cardOrderInfo {
                    background-color: #f8fafc;
                    border: 1px solid #e2e8f0;
                    border-radius: 3px;
                }
                QDoubleSpinBox {
                    background-color: #ffffff;
                    color: #0f172a;
                    border: 1px solid #cbd5e1;
                    border-radius: 2px;
                    padding: 2px 6px;
                }
                QDoubleSpinBox:focus {
                    border-color: #0f172a;
                }
                QPushButton {
                    background-color: #ffffff;
                    color: #334155;
                    border: 1px solid #cbd5e1;
                    border-radius: 2px;
                }
                QPushButton:hover {
                    background-color: #f1f5f9;
                    color: #0f172a;
                    border-color: #94a3b8;
                }
                """
            )

        # Side-specific coloring for type and open prices
        if self.order_type == "BUY":
            self.lbl_open_val.setStyleSheet("color: #15803d;" if not self.is_dark else "color: #10b981;")
        else:
            self.lbl_open_val.setStyleSheet("color: #b91c1c;" if not self.is_dark else "color: #ef4444;")

        self.btn_modify.setObjectName("btnModify")

    def get_values(self) -> tuple[float, float]:
        """Returns tuple of (StopLoss, TakeProfit)."""
        return self.spin_sl.value(), self.spin_tp.value()
