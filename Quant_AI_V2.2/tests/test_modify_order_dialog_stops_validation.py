"""
Unit Tests for ModifyOrderDialog Stop Loss & Take Profit Client-Side Validation
Quant AI V2.2 - Institutional Verification
"""

import pytest
from PySide6.QtWidgets import QApplication
from frontend.widgets.modify_order_dialog import ModifyOrderDialog


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


class TestModifyOrderDialogValidation:
    """Client-side validation preventing MT5 error 10016 (INVALID_STOPS)."""

    def test_buy_stops_validation(self, qapp):
        """BUY order: SL must be < current_price, TP must be > current_price."""
        dlg = ModifyOrderDialog(
            ticket=1001,
            symbol="EURUSD",
            order_type="BUY",
            volume=1.0,
            open_price=1.0850,
            current_price=1.0860,
            current_sl=1.0800,
            current_tp=1.0950,
            digits=4,
            is_dark=True
        )
        dlg.show()

        # Initial valid state
        assert dlg.btn_modify.isEnabled() is True
        assert dlg.lbl_error.isVisible() is False

        # Inverted SL (SL >= current price)
        dlg.spin_sl.setValue(1.0870)
        assert dlg.btn_modify.isEnabled() is False
        assert dlg.lbl_error.isVisible() is True
        assert "below current price" in dlg.lbl_error.text()

        # Fix SL, invert TP (TP <= current price)
        dlg.spin_sl.setValue(1.0820)
        dlg.spin_tp.setValue(1.0855)
        assert dlg.btn_modify.isEnabled() is False
        assert dlg.lbl_error.isVisible() is True
        assert "above current price" in dlg.lbl_error.text()

        # Setting SL=0 and TP=0 (removing stops) is valid
        dlg.spin_sl.setValue(0.0)
        dlg.spin_tp.setValue(0.0)
        assert dlg.btn_modify.isEnabled() is True
        assert dlg.lbl_error.isVisible() is False
        dlg.close()

    def test_sell_stops_validation(self, qapp):
        """SELL order: SL must be > current_price, TP must be < current_price."""
        dlg = ModifyOrderDialog(
            ticket=1002,
            symbol="EURUSD",
            order_type="SELL",
            volume=1.0,
            open_price=1.0850,
            current_price=1.0840,
            current_sl=1.0900,
            current_tp=1.0750,
            digits=4,
            is_dark=False
        )
        dlg.show()

        # Initial valid state
        assert dlg.btn_modify.isEnabled() is True
        assert dlg.lbl_error.isVisible() is False

        # Inverted SL (SL <= current price)
        dlg.spin_sl.setValue(1.0830)
        assert dlg.btn_modify.isEnabled() is False
        assert dlg.lbl_error.isVisible() is True
        assert "above current price" in dlg.lbl_error.text()

        # Fix SL, invert TP (TP >= current price)
        dlg.spin_sl.setValue(1.0920)
        dlg.spin_tp.setValue(1.0850)
        assert dlg.btn_modify.isEnabled() is False
        assert dlg.lbl_error.isVisible() is True
        assert "below current price" in dlg.lbl_error.text()

        # Valid stops restored
        dlg.spin_tp.setValue(1.0800)
        assert dlg.btn_modify.isEnabled() is True
        assert dlg.lbl_error.isVisible() is False
        dlg.close()
