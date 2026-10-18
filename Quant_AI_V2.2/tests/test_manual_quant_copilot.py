import pytest
import os
import json
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout

from frontend.controllers.chart.trading_plan_panel import (
    calculate_manual_quant_lot,
    evaluate_manual_compliance,
    _recalculate_manual_lot_and_rr,
    sync_manual_copilot_quotes,
    execute_manual_quant_order,
    setup_trading_plan_cards,
    apply_playbook_cards_theme,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestManualQuantLotMath:
    def test_calculate_manual_quant_lot_xauusd(self):
        # Balance = $10,000, 1.0% risk = $100. SL = 2.50 ($2.50 move on Gold)
        # Lot = $100 / (2.50 * 100) = 0.40 lots
        lot, risk_dlr = calculate_manual_quant_lot("XAUUSD", sl_points=2.50, risk_pct=1.0, balance=10000.0)
        assert risk_dlr == 100.0
        assert lot == 0.40

    def test_calculate_manual_quant_lot_btcusd(self):
        # Balance = $10,000, 1.0% risk = $100. SL = 500.0 points
        # Lot = $100 / 500.0 = 0.20 lots
        lot, risk_dlr = calculate_manual_quant_lot("BTCUSD", sl_points=500.0, risk_pct=1.0, balance=10000.0)
        assert risk_dlr == 100.0
        assert lot == 0.20

    def test_calculate_manual_quant_lot_forex(self):
        # Balance = $10,000, 1.0% risk = $100. SL = 0.0020 (20 pips on EURUSD)
        # Lot = $100 / (0.0020 * 100,000) = 0.50 lots
        lot, risk_dlr = calculate_manual_quant_lot("EURUSD", sl_points=0.0020, risk_pct=1.0, balance=10000.0)
        assert risk_dlr == 100.0
        assert lot == 0.50

    def test_calculate_manual_quant_lot_zero_or_negative_sl(self):
        # Zero division guard
        lot, risk_dlr = calculate_manual_quant_lot("XAUUSD", sl_points=0.0, risk_pct=1.0, balance=10000.0)
        assert lot == 0.01
        assert risk_dlr == 100.0

        lot, risk_dlr = calculate_manual_quant_lot("XAUUSD", sl_points=-5.0, risk_pct=1.0, balance=10000.0)
        assert lot == 0.01

    def test_calculate_manual_quant_lot_different_risk_pcts(self):
        # 0.5% risk on $10,000 = $50
        lot_05, risk_05 = calculate_manual_quant_lot("XAUUSD", sl_points=2.0, risk_pct=0.5, balance=10000.0)
        assert risk_05 == 50.0
        assert lot_05 == 0.25

        # 2.0% risk on $10,000 = $200
        lot_20, risk_20 = calculate_manual_quant_lot("XAUUSD", sl_points=2.0, risk_pct=2.0, balance=10000.0)
        assert risk_20 == 200.0
        assert lot_20 == 1.00


class TestManualComplianceGatekeeper:
    def test_compliance_normal_conditions(self):
        mock_win = MagicMock()
        mock_win.current_sym = "XAUUSD"
        passed, checks, reason = evaluate_manual_compliance(mock_win, "XAUUSD")
        assert passed is True
        assert reason == ""
        assert checks["drawdown"]["passed"] is True
        assert checks["spread"]["passed"] is True

    @patch("backend.infrastructure.brokers.mt5_safe.mt5.terminal_info")
    @patch("backend.infrastructure.brokers.mt5_safe.mt5.account_info")
    def test_compliance_daily_loss_breach_blocks(self, mock_acc, mock_term):
        mock_term.return_value = MagicMock()
        mock_acc_obj = MagicMock()
        mock_acc_obj.balance = 10000.0
        mock_acc_obj.equity = 4500.0  # Floating loss $5,500 > max limit $5,000
        mock_acc.return_value = mock_acc_obj

        mock_win = MagicMock()
        mock_win.current_sym = "XAUUSD"
        passed, checks, reason = evaluate_manual_compliance(mock_win, "XAUUSD")
        assert passed is False
        assert "DAILY LOSS" in reason
        assert checks["drawdown"]["passed"] is False

    @patch("backend.infrastructure.brokers.mt5_safe.mt5.terminal_info")
    @patch("backend.infrastructure.brokers.mt5_safe.mt5.positions_get")
    def test_compliance_max_trades_breach_blocks(self, mock_pos, mock_term):
        mock_term.return_value = MagicMock()
        # 3 open positions >= max_open_trades (3)
        mock_pos.return_value = [MagicMock(), MagicMock(), MagicMock()]

        mock_win = MagicMock()
        mock_win.current_sym = "XAUUSD"
        passed, checks, reason = evaluate_manual_compliance(mock_win, "XAUUSD")
        assert passed is False
        assert "MAX TRADES" in reason
        assert checks["max_trades"]["passed"] is False

    @patch("backend.infrastructure.brokers.mt5_safe.mt5.terminal_info")
    @patch("backend.infrastructure.brokers.mt5_safe.mt5.symbol_info")
    def test_compliance_spread_widening_blocks(self, mock_sym_info, mock_term):
        mock_term.return_value = MagicMock()
        mock_info_obj = MagicMock()
        mock_info_obj.spread = 120  # Spread 120 > normal allowance 45 for Gold
        mock_sym_info.return_value = mock_info_obj

        mock_win = MagicMock()
        mock_win.current_sym = "XAUUSD"
        passed, checks, reason = evaluate_manual_compliance(mock_win, "XAUUSD")
        assert passed is False
        assert "SPREAD" in reason
        assert checks["spread"]["passed"] is False


class TestManualCopilotUI:
    def test_ui_construction_and_mode_switching(self, qapp):
        win = QWidget()
        win.current_sym = "XAUUSD"
        win.is_dark_theme = True
        win.layoutAIArea = QVBoxLayout(win)

        setup_trading_plan_cards(win, is_dark=True)
        win.show()

        # Check switcher and containers
        assert hasattr(win, "framePlanModeSwitcher")
        assert hasattr(win, "containerPlanAI")
        assert hasattr(win, "containerPlanManual")
        assert not win.containerPlanAI.isHidden()
        assert win.containerPlanManual.isHidden()

        # Switch to Manual Mode
        assert win.btnPlanModeManual.text() == "MANUAL ORDER"
        assert win.lblManualGateTitle.text() == "PRE-TRADE CHECK"
        win.btnPlanModeManual.click()
        assert win._plan_mode == "manual"
        assert win.containerPlanAI.isHidden()
        assert not win.containerPlanManual.isHidden()

        # Switch back to AI Mode
        win.btnPlanModeAI.click()
        assert win._plan_mode == "ai"
        assert not win.containerPlanAI.isHidden()
        assert win.containerPlanManual.isHidden()
        win.close()

    def test_spinbox_and_lot_recalculation(self, qapp):
        win = QWidget()
        win.current_sym = "XAUUSD"
        win.is_dark_theme = True
        win.layoutAIArea = QVBoxLayout(win)
        setup_trading_plan_cards(win, is_dark=True)

        win.btnPlanModeManual.click()
        win._last_manual_entry = 2650.0
        win.lblManualAskPrice.setText("2650.00")
        win._manual_direction = "BUY"
        win._manual_risk_pct = 1.0

        # Set SL = 2645.0 (5.0 pts distance -> on Gold: $100 / (5.0 * 100) = 0.20 lots)
        # Set TP = 2660.0 (10.0 pts distance -> R:R 1:2.0)
        win.spinManualSL.setValue(2645.0)
        win.spinManualTP.setValue(2660.0)

        assert "0.20" in win.lblManualLotVal.text()
        assert "2.0R" in win.lblManualLotSummary.text() or "1:2.0" in win.lblManualLotSummary.text()
        assert "-$100.00 (1.0%)" in win.lblManualRiskPart.text()
        assert "+$200.00 (2.0R)" in win.lblManualRewardPart.text()
        assert win.btnManualExecute.isEnabled() is True
        assert "BUY 0.20 LOTS" in win.btnManualExecute.text()

        # Test user editing lot directly to 0.19
        win.spinManualLot.setValue(0.19)
        assert "-$95.00 (0.9%)" in win.lblManualRiskPart.text()
        assert "BUY 0.19 LOTS" in win.btnManualExecute.text()

    def test_stepper_and_preset_buttons(self, qapp):
        win = QWidget()
        win.current_sym = "XAUUSD"
        win.is_dark_theme = True
        win.layoutAIArea = QVBoxLayout(win)
        setup_trading_plan_cards(win, is_dark=True)

        win.btnPlanModeManual.click()
        win._last_manual_entry = 2650.0
        win.lblManualAskPrice.setText("2650.00")
        win.spinManualSL.setValue(2645.0)
        win.spinManualTP.setValue(2660.0)

        # Step SL up (+)
        win.btnSLPlus.click()
        assert win.spinManualSL.value() == 2646.0

        # Step SL down (-)
        win.btnSLMinus.click()
        assert win.spinManualSL.value() == 2645.0

        # Preset R:R 3.0R (from 2650 with SL 2645, dist=5 -> TP should be 2650 + 15 = 2665.0)
        win.btnPresetRR30.click()
        assert win.spinManualTP.value() == 2665.0
        assert "3.0R" in win.lblManualLotSummary.text() or "1:3.0" in win.lblManualLotSummary.text()

    def test_buy_order_pips_calculation_fix(self, qapp):
        """User reported bug: BUY MARKET @ 2650.50, SL 2645.00, TP 2660.00.
        SL distance must be -55.0 pips (not -52.5 pips).
        TP distance must be +95.0 pips (not +97.5 pips)."""
        win = QWidget()
        win.current_sym = "XAUUSD"
        win.layoutAIArea = QVBoxLayout(win)
        setup_trading_plan_cards(win, is_dark=False)

        win.btnPlanModeManual.click()
        win._manual_direction = "BUY"
        win.lblManualAskPrice.setText("2650.50")
        win.lblManualBidPrice.setText("2650.25")
        win.spinManualSL.setValue(2645.00)
        win.spinManualTP.setValue(2660.00)

        assert "-55.0 pips" in win.lblManualSLPips.text()
        assert "+95.0 pips" in win.lblManualTPPips.text()
        assert "BUY" in win.btnManualExecute.text()
        assert "2650.50" in win.btnManualExecute.text()

    def test_theme_toggle_light_and_dark(self, qapp):
        win = QWidget()
        win.current_sym = "XAUUSD"
        win.layoutAIArea = QVBoxLayout(win)
        setup_trading_plan_cards(win, is_dark=False)

        # Test applying dark theme
        apply_playbook_cards_theme(win, is_dark=True)
        # Test applying light theme
        apply_playbook_cards_theme(win, is_dark=False)

    @patch("backend.infrastructure.brokers.mt5_safe.mt5.terminal_info")
    @patch("backend.infrastructure.brokers.execution_manager.ExecutionManager.execute_market_order")
    def test_custom_lot_preservation_and_execution(self, mock_exec, mock_term, qapp):
        """Verify that user-edited lot is preserved during recalculate/tick and passed to broker."""
        mock_term.return_value = MagicMock()
        mock_exec.return_value = {"status": "success", "ticket": 123456}

        win = QWidget()
        win.current_sym = "XAUUSD"
        win.layoutAIArea = QVBoxLayout(win)
        setup_trading_plan_cards(win, is_dark=False)

        win.btnPlanModeManual.click()
        win._manual_direction = "BUY"
        win.lblManualAskPrice.setText("2650.50")
        win.lblManualBidPrice.setText("2650.25")
        win.spinManualSL.setValue(2645.00)
        win.spinManualTP.setValue(2660.00)

        # User edits lot to 0.20
        win.spinManualLot.setValue(0.20)
        assert win._user_custom_lot is True
        assert "BUY 0.20 LOTS" in win.btnManualExecute.text()

        # Simulate a market tick arriving
        sync_manual_copilot_quotes(win)
        # Custom lot should still be 0.20, NOT overwritten
        assert win.spinManualLot.value() == 0.20
        assert "BUY 0.20 LOTS" in win.btnManualExecute.text()

        # Execute order
        execute_manual_quant_order(win)
        mock_exec.assert_called_once()
        _, kwargs = mock_exec.call_args
        assert kwargs["volume"] == 0.20
        assert kwargs["is_buy"] is True
        assert kwargs["symbol"] == "XAUUSD"

        # Now click 2.0% risk button -> resets custom lot
        win.btnRisk20.click()
        assert win._user_custom_lot is False
        assert win._manual_risk_pct == 2.0
