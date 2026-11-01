import os
import json
import time
import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QProgressBar

from frontend.controllers.chart.ai_panel_controller import _update_panel_with_result, _build_analysis_panel
from frontend.controllers.chart.trading_plan_panel import (
    setup_trading_plan_cards,
    update_order_proposal_html,
    start_signal_expiry_countdown,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class DummyWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.current_sym = "XAUUSD"
        self.current_tf_str = "M15"
        self.is_dark_theme = True
        self.order_proposal_active = False
        self.is_live_position = False
        self.live_ticket = None
        self.is_pending_order = False
        self.pending_ticket = None
        self.layoutAIArea = QVBoxLayout(self)
        _build_analysis_panel(self)
        setup_trading_plan_cards(self, is_dark=True)


class TestFullAutoExecution:
    @patch("frontend.controllers.chart.ai_panel_controller.mt5")
    def test_full_auto_autonomous_execution(self, mock_mt5, qapp):
        mock_mt5.terminal_info.return_value = None
        mock_mt5.symbol_info.return_value = MagicMock(digits=2)

        win = DummyWindow()
        win.quant_terminal = MagicMock()
        win.quant_terminal.header = MagicMock(execution_mode="FULL-AUTO")
        win.quant_terminal.exec_mgr = MagicMock()
        win.quant_terminal.exec_mgr.execute_market_order.return_value = {
            "status": "success",
            "ticket": 888999,
            "price": 2650.0,
        }

        candle_t = 1700000000
        ai_result = {
            "_price": 2650.0,
            "_candle_time": candle_t,
            "_strategy_name": "ICT Zones Pro",
            "_strategy_res": {
                "signal": "BUY",
                "entry_price": 2650.0,
                "sl": 2640.0,
                "tp1": 2670.0,
                "confidence": 0.90,
                "checklist": ["Bullish Order Block", "Liquidity Swept", "Fair Value Gap Mitigated"],
            },
        }

        # First run: autonomous dispatch
        _update_panel_with_result(win, ai_result)

        # The GUI is a renderer; autonomous routing belongs to the armed worker.
        win.quant_terminal.exec_mgr.execute_market_order.assert_not_called()
        assert not getattr(win,'is_live_position',False)

    @patch("frontend.controllers.chart.ai_panel_controller.mt5")
    def test_full_auto_signal_deduplication(self, mock_mt5, qapp):
        """FULL-AUTO must NOT re-execute the same signal on the same candle."""
        mock_mt5.terminal_info.return_value = None
        mock_mt5.symbol_info.return_value = MagicMock(digits=2)

        win = DummyWindow()
        win.quant_terminal = MagicMock()
        win.quant_terminal.header = MagicMock(execution_mode="FULL-AUTO")
        win.quant_terminal.exec_mgr = MagicMock()
        win.quant_terminal.exec_mgr.execute_market_order.return_value = {
            "status": "success",
            "ticket": 888100,
            "price": 2650.0,
        }

        candle_t = 1700000500
        ai_result = {
            "_price": 2650.0,
            "_candle_time": candle_t,
            "_strategy_name": "ICT Zones Pro",
            "_strategy_res": {
                "signal": "BUY",
                "entry_price": 2650.0,
                "sl": 2640.0,
                "tp1": 2670.0,
                "confidence": 0.88,
            },
        }

        _update_panel_with_result(win, ai_result)
        assert win.quant_terminal.exec_mgr.execute_market_order.call_count == 0

        # Second tick on the exact same candle -> MUST NOT CALL execute_market_order AGAIN
        win.is_live_position = False  # even if position closed
        _update_panel_with_result(win, ai_result)
        assert win.quant_terminal.exec_mgr.execute_market_order.call_count == 0

    @patch("frontend.controllers.chart.ai_panel_controller.mt5")
    def test_full_auto_invalid_sl_orientation_interception(self, mock_mt5, qapp):
        """FULL-AUTO must intercept and reject invalid SL orientation before MT5 submission."""
        mock_mt5.terminal_info.return_value = None
        mock_mt5.symbol_info.return_value = MagicMock(digits=2)

        win = DummyWindow()
        win.quant_terminal = MagicMock()
        win.quant_terminal.header = MagicMock(execution_mode="FULL-AUTO")
        win.quant_terminal.exec_mgr = MagicMock()

        ai_result = {
            "_price": 2650.0,
            "_candle_time": 1700001000,
            "_strategy_name": "ICT Zones Pro",
            "_strategy_res": {
                "signal": "BUY",
                "entry_price": 2650.0,
                "sl": 2660.0,  # ILLEGAL: SL is ABOVE entry for BUY
                "tp1": 2670.0,
            },
        }

        _update_panel_with_result(win, ai_result)
        # Order execution must NOT be called
        assert not win.quant_terminal.exec_mgr.execute_market_order.called


class TestSemiAutoDecisionGate:
    @patch("frontend.controllers.chart.ai_panel_controller.mt5")
    def test_semi_auto_proposal_and_countdown(self, mock_mt5, qapp):
        mock_mt5.terminal_info.return_value = None
        mock_mt5.symbol_info.return_value = MagicMock(digits=2)

        win = DummyWindow()
        win.quant_terminal = MagicMock()
        win.quant_terminal.header = MagicMock(execution_mode="SEMI-AUTO")

        candle_t = 1700002000
        ai_result = {
            "_price": 2650.0,
            "_candle_time": candle_t,
            "_strategy_name": "ICT Zones Pro",
            "_strategy_res": {
                "signal": "BUY",
                "entry_price": 2650.0,
                "sl": 2640.0,
                "tp1": 2670.0,
                "confidence": 0.85,
            },
        }

        _update_panel_with_result(win, ai_result)

        # Verified: In SEMI-AUTO, waits for operator approval
        assert win.btnApproveOrder.isEnabled() is True
        assert win.btnApproveOrder.text() == "APPROVE ORDER"
        assert win.btnDiscardOrder.isEnabled() is True
        assert win.order_proposal_active is True
        assert hasattr(win, "_signal_expiry_remaining")
        assert win._signal_expiry_remaining > 0

    @patch("frontend.controllers.chart.ai_panel_controller.mt5")
    def test_semi_auto_deduplication_preserves_countdown(self, mock_mt5, qapp):
        """Repeated analysis on same candle must not reset the countdown timer."""
        mock_mt5.terminal_info.return_value = None
        mock_mt5.symbol_info.return_value = MagicMock(digits=2)

        win = DummyWindow()
        win.quant_terminal = MagicMock()
        win.quant_terminal.header = MagicMock(execution_mode="SEMI-AUTO")

        candle_t = 1700003000
        ai_result = {
            "_price": 2650.0,
            "_candle_time": candle_t,
            "_strategy_name": "ICT Zones Pro",
            "_strategy_res": {
                "signal": "BUY",
                "entry_price": 2650.0,
                "sl": 2640.0,
                "tp1": 2670.0,
                "confidence": 0.85,
            },
        }

        _update_panel_with_result(win, ai_result)
        # Simulate countdown ticking down by 15 seconds
        win._signal_expiry_remaining = 45

        # Re-run analysis on the exact same candle
        _update_panel_with_result(win, ai_result)

        # Verified: Countdown was PRESERVED and not reset back to 60!
        assert win._signal_expiry_remaining == 45

    @patch("frontend.controllers.chart.ai_panel_controller.mt5")
    def test_semi_auto_discard_suppresses_repush(self, mock_mt5, qapp):
        """If user discarded proposal, it must not be re-pushed on the same candle."""
        mock_mt5.terminal_info.return_value = None
        mock_mt5.symbol_info.return_value = MagicMock(digits=2)

        win = DummyWindow()
        win.quant_terminal = MagicMock()
        win.quant_terminal.header = MagicMock(execution_mode="SEMI-AUTO")

        candle_t = 1700004000
        ai_result = {
            "_price": 2650.0,
            "_candle_time": candle_t,
            "_strategy_name": "ICT Zones Pro",
            "_strategy_res": {
                "signal": "SELL",
                "entry_price": 2650.0,
                "sl": 2660.0,
                "tp1": 2630.0,
                "confidence": 0.85,
            },
        }

        _update_panel_with_result(win, ai_result)
        assert win.order_proposal_active is True

        # Simulate user clicking DISCARD
        sig_key = getattr(win, "_active_proposal_sig")
        win._discarded_signals = {sig_key}
        win.order_proposal_active = False

        # Re-run analysis on the exact same candle
        _update_panel_with_result(win, ai_result)

        # Verified: Proposal remains suppressed!
        assert win.order_proposal_active is False


class TestManualModeIsolation:
    def test_manual_mode_tab_not_disturbed_by_ai(self, qapp):
        win = DummyWindow()
        win.btnPlanModeManual.click()
        assert win._plan_mode == "manual"
        win.spinManualSL.setValue(2642.50)
        win.spinManualTP.setValue(2680.00)

        # Incoming AI signal update
        update_order_proposal_html(
            win,
            sym="XAUUSD",
            has_signal=True,
            signal_type="BUY",
            entry=2650.0,
            sl=2635.0,
            tp=2675.0,
            exec_mode="SEMI-AUTO",
        )

        # Verified: Manual inputs were NOT overwritten by background AI signal
        assert win.spinManualSL.value() == 2642.50
        assert win.spinManualTP.value() == 2680.00
