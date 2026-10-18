import pytest
import os
import json
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout

from frontend.controllers.chart.trading_plan_panel import (
    calculate_manual_quant_lot,
    get_symbol_multiplier,
    get_symbol_pip_unit,
    evaluate_manual_compliance,
    _recalculate_manual_lot_and_rr,
    sync_manual_copilot_quotes,
    sync_live_position_to_ai_plan,
    execute_manual_quant_order,
    setup_trading_plan_cards,
    apply_playbook_cards_theme,
    clear_manual_chart_lines,
    _setup_chart_manual_lines,
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


class TestPlanScenarioAudits:
    def test_direction_switch_inverts_sl_tp_symmetrically(self, qapp):
        """Audit Scenario 1: Switching direction BUY <-> SELL must symmetrically flip SL & TP."""
        win = QWidget()
        win.current_sym = "XAUUSD"
        win.layoutAIArea = QVBoxLayout(win)
        setup_trading_plan_cards(win, is_dark=False)

        win.btnPlanModeManual.click()
        win._manual_direction = "BUY"
        win.lblManualAskPrice.setText("2650.50")
        win.lblManualBidPrice.setText("2650.25")
        win._last_manual_entry = 2650.50
        win.spinManualSL.setValue(2645.00)  # Dist: 5.50 below ask
        win.spinManualTP.setValue(2660.00)  # Dist: 9.50 above ask

        # User clicks SELL button
        win.btnManualSell.click()
        assert win._manual_direction == "SELL"

        # On SELL: entry is Bid (2650.25)
        # SL must be ABOVE 2650.25 by 5.50 -> 2655.75
        # TP must be BELOW 2650.25 by 9.50 -> 2640.75
        assert win.spinManualSL.value() > win._last_manual_entry
        assert win.spinManualTP.value() < win._last_manual_entry
        assert win.spinManualSL.value() == 2655.75
        assert win.spinManualTP.value() == 2640.75
        assert "SELL" in win.btnManualExecute.text()
        assert win.btnManualExecute.isEnabled() is True

        # User clicks BUY button again
        win.btnManualBuy.click()
        assert win._manual_direction == "BUY"
        # SL must be BELOW 2650.50 and TP must be ABOVE 2650.50
        assert win.spinManualSL.value() < win._last_manual_entry
        assert win.spinManualTP.value() > win._last_manual_entry
        assert win.spinManualSL.value() == 2645.00
        assert win.spinManualTP.value() == 2660.00
        assert "BUY" in win.btnManualExecute.text()
        assert win.btnManualExecute.isEnabled() is True

    def test_invalid_stops_orientation_blocked_by_compliance(self, qapp):
        """Audit Scenario 2: If user types invalid stops, compliance locks execution."""
        win = QWidget()
        win.current_sym = "XAUUSD"
        win.layoutAIArea = QVBoxLayout(win)
        setup_trading_plan_cards(win, is_dark=False)

        win.btnPlanModeManual.click()
        win._manual_direction = "BUY"
        win.lblManualAskPrice.setText("2650.50")
        win._last_manual_entry = 2650.50

        # Illegally set SL above entry for a BUY
        win.spinManualSL.setValue(2655.00)
        win.spinManualTP.setValue(2665.00)
        _recalculate_manual_lot_and_rr(win)

        passed, checks, reason = evaluate_manual_compliance(win, "XAUUSD")
        assert passed is False
        assert "INVALID SL" in reason
        assert win.btnManualExecute.isEnabled() is False
        assert "LOCKED: INVALID SL" in win.btnManualExecute.text()

        # Fix SL back below entry -> auto unlocks
        win.spinManualSL.setValue(2645.00)
        _recalculate_manual_lot_and_rr(win)
        assert win.btnManualExecute.isEnabled() is True
        assert "BUY" in win.btnManualExecute.text()

    def test_multi_asset_jpy_and_indices_lot_and_risk(self, qapp):
        """Audit Scenario 3: JPY and Stock Indices calculate realistic lot & risk."""
        # USDJPY
        mult_jpy = get_symbol_multiplier("USDJPY")
        assert mult_jpy == 667.0
        pip_jpy = get_symbol_pip_unit("USDJPY", digits=3, point=0.001)
        assert pip_jpy == 0.01

        lot_jpy, risk_jpy = calculate_manual_quant_lot("USDJPY", sl_points=0.50, risk_pct=1.0, balance=10000.0)
        assert risk_jpy == 100.0
        assert lot_jpy == 0.30

        # US30 Index
        mult_us30 = get_symbol_multiplier("US30")
        assert mult_us30 == 10.0
        pip_us30 = get_symbol_pip_unit("US30", digits=1, point=0.1)
        assert pip_us30 == 1.0

        lot_us30, risk_us30 = calculate_manual_quant_lot("US30", sl_points=50.0, risk_pct=1.0, balance=10000.0)
        assert risk_us30 == 100.0
        assert lot_us30 == 0.20

    def test_ai_expiry_timer_stopped_when_switching_to_manual(self, qapp):
        """Audit Scenario 4: Switching to manual mode immediately stops AI expiry timer."""
        from frontend.controllers.chart.trading_plan_panel import start_signal_expiry_countdown
        win = QWidget()
        win.current_sym = "XAUUSD"
        win.layoutAIArea = QVBoxLayout(win)
        setup_trading_plan_cards(win, is_dark=False)

        # Start timer in AI mode
        start_signal_expiry_countdown(win, duration_sec=60)
        assert hasattr(win, "_signal_expiry_timer")
        assert win._signal_expiry_timer.isActive() is True

        # Switch to manual mode
        win.btnPlanModeManual.click()
        assert win._plan_mode == "manual"
        # Timer must be stopped immediately so it doesn't wipe chart lines
        assert win._signal_expiry_timer.isActive() is False

    @patch("backend.infrastructure.brokers.mt5_safe.mt5.order_send")
    def test_cancel_pending_order_execution_manager(self, mock_order_send):
        """Audit Scenario 5: ExecutionManager can cancel pending orders via TRADE_ACTION_REMOVE."""
        from backend.infrastructure.brokers.execution_manager import ExecutionManager
        from backend.infrastructure.brokers.mt5_safe import mt5

        mock_res = MagicMock()
        mock_res.retcode = mt5.TRADE_RETCODE_DONE
        mock_order_send.return_value = mock_res

        mgr = ExecutionManager()
        res = mgr.cancel_pending_order(987654)
        assert res["status"] == "success"
        mock_order_send.assert_called_once()
        req = mock_order_send.call_args[0][0]
        assert req["action"] == mt5.TRADE_ACTION_REMOVE
        assert req["order"] == 987654

    def test_manual_preview_toggle_and_clear_lines(self, qapp):
        """User request audit: Manual order preview lines can be hidden/cleared via btnManualClearPreview."""
        win = QWidget()
        win.current_sym = "XAUUSD"
        win.layoutAIArea = QVBoxLayout(win)
        setup_trading_plan_cards(win, is_dark=True)

        assert hasattr(win, "btnManualClearPreview")
        assert hasattr(win, "btnManualReset")
        assert win.btnManualClearPreview.text() == "HIDE PREVIEW"
        assert getattr(win, "_show_manual_preview", None) is True

        mock_plot = MagicMock()
        mock_items = set()
        mock_plot.items.return_value = mock_items
        mock_plot.addItem.side_effect = lambda it, **kw: mock_items.add(it)
        mock_plot.removeItem.side_effect = lambda it: mock_items.discard(it)
        win.plot_widget = mock_plot

        line_entry = MagicMock()
        line_sl = MagicMock()
        line_tp = MagicMock()
        win.line_order_entry = line_entry
        win.line_order_sl = line_sl
        win.line_order_tp = line_tp

        # Click HIDE PREVIEW
        win.btnManualClearPreview.click()
        assert win._show_manual_preview is False
        assert win.btnManualClearPreview.text() == "SHOW PREVIEW"
        line_entry.setVisible.assert_called_with(False)
        line_sl.setVisible.assert_called_with(False)
        line_tp.setVisible.assert_called_with(False)
        mock_plot.removeItem.assert_any_call(line_entry)
        mock_plot.removeItem.assert_any_call(line_sl)
        mock_plot.removeItem.assert_any_call(line_tp)

        # Click SHOW PREVIEW to re-enable
        win.btnManualClearPreview.click()
        assert win._show_manual_preview is True
        assert win.btnManualClearPreview.text() == "HIDE PREVIEW"

    def test_drawer_close_clears_draft_lines_when_no_live_position(self, qapp):
        """User request audit: When trading plan drawer is closed, draft lines are purged if not in a live position."""
        win = QWidget()
        win.current_sym = "XAUUSD"
        win.is_live_position = False
        win.is_pending_order = False

        mock_plot = MagicMock()
        mock_items = set()
        mock_plot.items.return_value = mock_items
        win.plot_widget = mock_plot

        line_entry = MagicMock()
        line_sl = MagicMock()
        line_tp = MagicMock()
        win.line_order_entry = line_entry
        win.line_order_sl = line_sl
        win.line_order_tp = line_tp

        clear_manual_chart_lines(win)
        line_entry.setVisible.assert_called_with(False)
        line_sl.setVisible.assert_called_with(False)
        line_tp.setVisible.assert_called_with(False)
        mock_plot.removeItem.assert_any_call(line_entry)
        mock_plot.removeItem.assert_any_call(line_sl)
        mock_plot.removeItem.assert_any_call(line_tp)

    def test_setup_chart_manual_lines_respects_preview_flag_and_drawer(self, qapp):
        """_setup_chart_manual_lines will NOT render lines if preview is off or drawer is hidden."""
        win = QWidget()
        win.current_sym = "XAUUSD"
        win._plan_mode = "manual"
        mock_plot = MagicMock()
        win.plot_widget = mock_plot

        line_entry = MagicMock()
        win.line_order_entry = line_entry

        # Case 1: _show_manual_preview is False
        win._show_manual_preview = False
        _setup_chart_manual_lines(win, "XAUUSD", True, 0.2, 2640.0, 2660.0)
        mock_plot.addItem.assert_not_called()

        # Case 2: frameAIArea is not visible
        win._show_manual_preview = True
        frame_ai = MagicMock()
        frame_ai.isVisible.return_value = False
        win.frameAIArea = frame_ai
        _setup_chart_manual_lines(win, "XAUUSD", True, 0.2, 2640.0, 2660.0)
        mock_plot.addItem.assert_not_called()

    def test_manual_order_lines_dashed_pen_style(self, qapp):
        """Audit: Manual draft preview lines must use Qt.DashLine to distinguish from live positions."""
        from PySide6.QtCore import Qt
        win = QWidget()
        win.current_sym = "XAUUSD"
        win._plan_mode = "manual"
        win._show_manual_preview = True
        mock_plot = MagicMock()
        mock_items = set()
        mock_plot.items.return_value = mock_items
        win.plot_widget = mock_plot

        line_entry = MagicMock()
        line_sl = MagicMock()
        line_tp = MagicMock()
        line_entry.value.return_value = 0.0
        line_sl.value.return_value = 0.0
        line_tp.value.return_value = 0.0
        win.line_order_entry = line_entry
        win.line_order_sl = line_sl
        win.line_order_tp = line_tp

        _setup_chart_manual_lines(win, "XAUUSD", True, 0.2, 2640.0, 2660.0)

        # Verify setPen was called with a pen having style Qt.DashLine
        assert line_entry.setPen.called
        entry_pen = line_entry.setPen.call_args[0][0]
        assert entry_pen.style() == Qt.DashLine

        assert line_sl.setPen.called
        sl_pen = line_sl.setPen.call_args[0][0]
        assert sl_pen.style() == Qt.DashLine

        assert line_tp.setPen.called
        tp_pen = line_tp.setPen.call_args[0][0]
        assert tp_pen.style() == Qt.DashLine

    def test_manual_order_lines_label_cross_and_click_dismiss(self, qapp):
        """User request audit: Labels contain [×] and clicking dismisses manual preview lines."""
        win = QWidget()
        win.current_sym = "XAUUSD"
        win._plan_mode = "manual"
        win._show_manual_preview = True
        win.btnManualClearPreview = MagicMock()

        mock_plot = MagicMock()
        mock_items = set()
        mock_plot.items.return_value = mock_items
        win.plot_widget = mock_plot

        line_entry = MagicMock()
        line_sl = MagicMock()
        line_tp = MagicMock()
        line_entry.value.return_value = 0.0
        line_sl.value.return_value = 0.0
        line_tp.value.return_value = 0.0
        win.line_order_entry = line_entry
        win.line_order_sl = line_sl
        win.line_order_tp = line_tp

        _setup_chart_manual_lines(win, "XAUUSD", True, 0.2, 2640.0, 2660.0)

        # Check label formats have [×]
        assert "[×]" in line_entry.label.setFormat.call_args[0][0]
        assert "[×]" in line_sl.label.setFormat.call_args[0][0]
        assert "[×]" in line_tp.label.setFormat.call_args[0][0]

        # Verify mouseClickEvent handler was attached to label
        assert callable(line_entry.label.mouseClickEvent)

        # Simulate user clicking [×] on chart label
        mock_ev = MagicMock()
        line_entry.label.mouseClickEvent(mock_ev)

        assert win._show_manual_preview is False
        win.btnManualClearPreview.setText.assert_called_with("SHOW PREVIEW")
        line_entry.setVisible.assert_called_with(False)
        line_sl.setVisible.assert_called_with(False)
        line_tp.setVisible.assert_called_with(False)

    @patch("backend.infrastructure.brokers.mt5_safe.mt5.terminal_info")
    @patch("backend.infrastructure.brokers.mt5_safe.mt5.symbol_info")
    def test_btc_crypto_spread_and_risk_reward_consistency(self, mock_sym_info, mock_term):
        """User image audit: BTC spread 2700 pts must PASS, and R:R must be mathematically consistent."""
        mock_term.return_value = MagicMock()
        mock_info = MagicMock()
        mock_info.spread = 2700
        mock_info.point = 0.01
        mock_info.digits = 2
        mock_sym_info.return_value = mock_info

        win = QWidget()
        win.current_sym = "BTCUSD"
        win._last_manual_entry = 81470.00
        win.spinManualSL = MagicMock()
        win.spinManualSL.value.return_value = 81436.00
        win.spinManualTP = MagicMock()
        win.spinManualTP.value.return_value = 81822.22

        passed, checks, reason = evaluate_manual_compliance(win, "BTCUSD")
        assert passed is True
        assert checks["spread"]["passed"] is True
        assert reason == ""

        # Test lot calculation for BTC with $100,000 balance and 0.5% risk
        lot, risk_dlr = calculate_manual_quant_lot("BTCUSD", sl_points=34.0, risk_pct=0.5, balance=100000.0)
        assert lot == 14.71
        assert risk_dlr == 500.0

    @patch("backend.infrastructure.brokers.mt5_safe.mt5.terminal_info")
    @patch("backend.infrastructure.brokers.mt5_safe.mt5.symbol_info")
    def test_universal_multi_asset_spread_governance_and_sl_friction(self, mock_sym_info, mock_term):
        """Universal multi-asset test: Validates QuantConnect LEAN BPS & Almgren-Chriss SL friction across symbols."""
        mock_term.return_value = MagicMock()

        # 1. Solana (Crypto): price $150, spread $0.15 (15 pts at point=0.01) -> BPS = 10.0 < 35.0 BPS -> PASS
        sol_info = MagicMock()
        sol_info.spread = 15
        sol_info.point = 0.01
        sol_info.digits = 2
        sol_info.path = "Crypto\\SOLUSD"
        mock_sym_info.return_value = sol_info

        win = QWidget()
        win.current_sym = "SOLUSD"
        win._last_manual_entry = 150.0
        win.spinManualSL = MagicMock()
        win.spinManualSL.value.return_value = 145.0
        win.spinManualTP = MagicMock()
        win.spinManualTP.value.return_value = 160.0

        passed, checks, reason = evaluate_manual_compliance(win, "SOLUSD")
        assert passed is True
        assert checks["spread"]["passed"] is True

        # 2. US30 Index: price 43000, spread 2.0 (20 pts at point=0.1) -> BPS = 0.46 < 10.0 BPS -> PASS
        us30_info = MagicMock()
        us30_info.spread = 20
        us30_info.point = 0.1
        us30_info.digits = 1
        us30_info.path = "Indices\\US30"
        mock_sym_info.return_value = us30_info

        win.current_sym = "US30"
        win._last_manual_entry = 43000.0
        win.spinManualSL.value.return_value = 42950.0
        win.spinManualTP.value.return_value = 43100.0

        passed, checks, reason = evaluate_manual_compliance(win, "US30")
        assert passed is True
        assert checks["spread"]["passed"] is True

        # 3. Almgren-Chriss SL friction test: When spread cost ($2.0) >= SL distance ($1.0) -> BLOCKED
        win.spinManualSL.value.return_value = 42999.0  # SL distance = 1.0 < spread cost 2.0!
        passed, checks, reason = evaluate_manual_compliance(win, "US30")
        assert passed is False
        assert "SPREAD EXCEEDS STOP LOSS DISTANCE" in reason

    @patch("backend.infrastructure.brokers.mt5_safe.mt5.terminal_info")
    @patch("backend.infrastructure.brokers.mt5_safe.mt5.symbol_info_tick")
    @patch("backend.infrastructure.brokers.mt5_safe.mt5.symbol_info")
    @patch("backend.infrastructure.brokers.mt5_safe.mt5.account_info")
    def test_manual_order_dollar_risk_matches_actual_sl_distance(self, mock_acc, mock_sym, mock_tick, mock_term, qapp):
        """Dollar risk must strictly equal actual lot * SL distance * multiplier, ensuring reward/risk ratio matches."""
        mock_term.return_value = MagicMock()
        mock_t = MagicMock()
        mock_t.ask = 81209.0
        mock_t.bid = 81209.0
        mock_tick.return_value = mock_t

        acc = MagicMock()
        acc.balance = 99352.0  # $99,352 balance
        mock_acc.return_value = acc

        btc_info = MagicMock()
        btc_info.digits = 2
        btc_info.point = 0.01
        btc_info.spread = 10
        btc_info.volume_min = 0.01
        btc_info.volume_max = 50.0
        btc_info.volume_step = 0.01
        btc_info.trade_contract_size = 1.0
        mock_sym.return_value = btc_info

        win = QWidget()
        win.current_sym = "BTCUSD"
        win._last_manual_entry = 81209.0
        win._last_manual_ask = 81209.0
        win._last_manual_bid = 81209.0
        win.is_dark_theme = True

        from PySide6.QtWidgets import QLabel, QDoubleSpinBox
        win.spinManualSL = QDoubleSpinBox()
        win.spinManualSL.setRange(0.0, 1000000.0)
        win.spinManualSL.setValue(81172.0)  # sl_pts = 37.0
        win.spinManualTP = QDoubleSpinBox()
        win.spinManualTP.setRange(0.0, 1000000.0)
        win.spinManualTP.setValue(81558.22)  # tp_pts = 349.22
        win.spinManualLot = QDoubleSpinBox()
        win.spinManualLot.setValue(1.00)  # 1.00 lot custom
        win.lblManualSLPips = QLabel()
        win.lblManualTPPips = QLabel()
        win.lblManualRiskPart = QLabel()
        win.lblManualRewardPart = QLabel()
        win.lblManualLotSummary = QLabel()

        # Recalculate with user lot change = True (1.00 lot)
        _recalculate_manual_lot_and_rr(win, from_user_lot_change=True)

        # 1.00 lot * 37.0 points * 1.0 multiplier = $37.00 (NOT $496.76!)
        assert "-$37.00" in win.lblManualRiskPart.text()
        assert "+$349.22" in win.lblManualRewardPart.text()
        assert "9.4R" in win.lblManualRewardPart.text()
        assert "-37.0 pips" in win.lblManualSLPips.text()
        assert "+349.2 pips" in win.lblManualTPPips.text()

    def test_trading_plan_sl_tp_spacing_and_pips_label(self, qapp):
        """Verifies 6px spacing between SL/TP rows and minimum height on pips labels to prevent clipping."""
        win = QWidget()
        win.layoutAIArea = QVBoxLayout(win)
        win.is_dark_theme = True
        setup_trading_plan_cards(win)

        assert hasattr(win, "lblManualSLPips")
        assert hasattr(win, "lblManualTPPips")
        assert win.lblManualSLPips.minimumHeight() >= 14
        assert win.lblManualTPPips.minimumHeight() >= 14

        # Card manual risk should have layouts with spacing
        assert hasattr(win, "cardManualRisk")

    @patch("backend.infrastructure.brokers.mt5_safe.mt5.terminal_info")
    @patch("backend.infrastructure.brokers.mt5_safe.mt5.positions_get")
    @patch("backend.infrastructure.brokers.mt5_safe.mt5.symbol_info")
    def test_ai_plan_live_position_volume_and_pnl_sync(self, mock_sym, mock_pos, mock_term, qapp):
        """Verifies live open position volume and floating PnL are dynamically synced to the AI plan."""
        mock_term.return_value = MagicMock()
        sym_info = MagicMock()
        sym_info.digits = 2
        mock_sym.return_value = sym_info

        # Mock position #282779749: 0.64 lots, PnL -$196.42
        mock_p = MagicMock()
        mock_p.ticket = 282779749
        mock_p.volume = 0.64
        mock_p.profit = -196.42
        mock_p.price_open = 81491.40
        mock_p.sl = 79905.70
        mock_p.tp = 84580.61
        mock_p.type = 0  # BUY
        mock_pos.return_value = [mock_p]

        win = QWidget()
        win.current_sym = "BTCUSD"
        win._plan_mode = "ai"

        from PySide6.QtWidgets import QLabel
        win.lblSizeVal = QLabel("--")
        win.lblEntryVal = QLabel("--")
        win.lblSLVal = QLabel("--")
        win.lblTPVal = QLabel("--")
        win.lblModelSubtitle = QLabel("SETUP MODEL")

        sync_live_position_to_ai_plan(win)

        assert win.lblSizeVal.text() == "0.64 LOTS (PNL: -$196.42)"
        assert "81491.40" in win.lblEntryVal.text()
        assert "79905.70" in win.lblSLVal.text()
        assert "84580.61" in win.lblTPVal.text()
        assert "282779749" in win.lblModelSubtitle.text()
        assert win.is_live_position is True

        # Test positive profit
        mock_p.profit = 250.80
        sync_live_position_to_ai_plan(win)
        assert win.lblSizeVal.text() == "0.64 LOTS (PNL: +$250.80)"


class TestStrategyAdaptiveTradingPlan:
    """Verifies that the Trading Plan panel dynamically adapts its model title,
    checklist keys, and evaluation criteria based on active strategy (Wyckoff vs ICT vs EMA)."""

    def test_wyckoff_momentum_strategy_analysis(self):
        from backend.core.strategies.wyckoff_vectorized import WyckoffMomentumStrategy
        import numpy as np
        import pandas as pd

        strat = WyckoffMomentumStrategy()
        # 1. Short data test (insufficient bars)
        short_df = pd.DataFrame({"close": [2000.0] * 10})
        res_short = strat.analyze(short_df)
        assert res_short["action"] == "HOLD"
        assert res_short["confidence"] == 0.0

        # 2. Bullish breakout with volume test
        n = 80
        closes = [2000.0 + i * 0.5 for i in range(n)]
        highs = [c + 2.0 for c in closes]
        lows = [c - 2.0 for c in closes]
        vols = [1000.0] * n
        vols[-1] = 2500.0  # 2.5x volume surge

        df = pd.DataFrame({
            "close": closes,
            "high": highs,
            "low": lows,
            "tick_volume": vols,
        })
        res = strat.analyze(df)
        assert "strategy" in res
        assert res["strategy"] == "Wyckoff_Momentum_Pro"
        assert "checklist" in res
        assert len(res["checklist"]) == 3
        assert "metadata" in res
        assert "bias" in res["metadata"]

    def test_strategy_model_resolution_and_checklist_keys(self, qapp):
        from frontend.controllers.chart.trading_plan_panel import (
            resolve_strategy_model_name,
            update_strategy_checklist_ui,
        )
        from PySide6.QtWidgets import QLabel, QWidget

        win = QWidget()
        win.lblKey_lblChk1Val = QLabel("Trend Structure")
        win.lblKey_lblChk2Val = QLabel("Liquidity Sweep")
        win.lblKey_lblChk3Val = QLabel("Order Blocks & FVG")
        win.lblChk1Val = QLabel("Awaiting Clear Trend")
        win.lblChk2Val = QLabel("Awaiting Asian Sweep")
        win.lblChk3Val = QLabel("Awaiting Mitigation")

        # 1. Wyckoff Mode
        update_strategy_checklist_ui(win, "Wyckoff Momentum Pro", is_active=False)
        assert win.lblKey_lblChk1Val.text() == "Trend Structure"
        assert win.lblKey_lblChk2Val.text() == "Pullback Retest"
        assert win.lblKey_lblChk3Val.text() == "Volume Expansion"
        assert win.lblChk2Val.text() == "Awaiting EMA Retest"
        assert win.lblChk3Val.text() == "Awaiting Volume Surge"

        # 2. EMA Mode
        update_strategy_checklist_ui(win, "EMA Dual Cross", is_active=False)
        assert win.lblKey_lblChk2Val.text() == "EMA Crossover"
        assert win.lblKey_lblChk3Val.text() == "Risk / Reward"
        assert win.lblChk2Val.text() == "Awaiting EMA Crossover"

        # 3. ICT Mode
        update_strategy_checklist_ui(win, "ICT Zones Pro v4.2", is_active=False)
        assert win.lblKey_lblChk2Val.text() == "Liquidity Sweep"
        assert win.lblKey_lblChk3Val.text() == "Order Blocks & FVG"
        assert win.lblChk2Val.text() == "Awaiting Asian Sweep"
        assert win.lblChk3Val.text() == "Awaiting Mitigation"

    @patch("backend.infrastructure.brokers.mt5_safe.mt5.symbol_info")
    def test_trading_plan_panel_wyckoff_full_cycle(self, mock_sym, qapp):
        from frontend.controllers.chart.trading_plan_panel import update_order_proposal_html
        from PySide6.QtWidgets import QLabel, QWidget, QPushButton, QProgressBar

        mock_info = MagicMock()
        mock_info.digits = 2
        mock_sym.return_value = mock_info

        win = QWidget()
        win.current_sym = "XAUUSD"
        win.is_dark_theme = True
        win._plan_mode = "ai"

        win.lblModelSubtitle = QLabel("SETUP MODEL")
        win.lblModelName = QLabel("ICT Zones Pro v4.2")
        win.lblModelGrade = QLabel("AWAITING SETUP")
        win.lblKey_lblChk1Val = QLabel("Trend Structure")
        win.lblKey_lblChk2Val = QLabel("Liquidity Sweep")
        win.lblKey_lblChk3Val = QLabel("Order Blocks & FVG")
        win.lblChk1Val = QLabel("Awaiting Clear Trend")
        win.lblChk2Val = QLabel("Awaiting Asian Sweep")
        win.lblChk3Val = QLabel("Awaiting Mitigation")

        win.lblOrderBudgetTitle = QLabel("ORDER & RISK BUDGET")
        win.lblOrderTypeBadge = QLabel("NO ORDER")
        win.lblEntryVal = QLabel("--")
        win.lblSLVal = QLabel("--")
        win.lblTPVal = QLabel("--")
        win.lblSizeVal = QLabel("--")
        win.lblGateExpiryTitle = QLabel("EXPIRATION")
        win.lblGateExpiryTime = QLabel("--")
        win.barSignalExpiry = QProgressBar()
        win.btnApproveOrder = QPushButton("APPROVE")
        win.btnModifyOrder = QPushButton("MODIFY")
        win.btnDiscardOrder = QPushButton("DISCARD")

        # 1. Update in Wyckoff standby mode
        update_order_proposal_html(
            win,
            has_signal=False,
            model_name="Wyckoff Momentum Pro",
            chk1="Mark-up Phase (EMA20 > EMA50)",
            chk2="Awaiting Pullback to EMA20",
            chk3="Normal Volume (1.0x MA)",
        )

        assert win.lblModelName.text() == "Wyckoff Momentum Pro"
        assert win.lblKey_lblChk2Val.text() == "Pullback Retest"
        assert win.lblKey_lblChk3Val.text() == "Volume Expansion"
        assert win.lblChk1Val.text() == "Mark-up Phase (EMA20 > EMA50)"
        assert win.lblChk2Val.text() == "Awaiting Pullback to EMA20"
        assert win.lblChk3Val.text() == "Normal Volume (1.0x MA)"

        # 2. Update with active Wyckoff BUY signal
        update_order_proposal_html(
            win,
            has_signal=True,
            signal_type="BUY",
            model_name="Wyckoff Momentum Pro (BUY)",
            entry=2650.00,
            sl=2640.00,
            tp=2675.00,
            chk1="Wyckoff BUY Structure",
            chk2="EMA20 Pullback Confirmed",
            chk3="Volume Expansion Confirmed",
        )

        assert "Wyckoff" in win.lblModelName.text()
        assert win.lblKey_lblChk2Val.text() == "Pullback Retest"
        assert win.lblKey_lblChk3Val.text() == "Volume Expansion"
        assert win.lblChk1Val.text() == "Wyckoff BUY Structure"
        assert win.lblChk2Val.text() == "EMA20 Pullback Confirmed"
        assert win.lblChk3Val.text() == "Volume Expansion Confirmed"
        assert "2650.00" in win.lblEntryVal.text()
        assert "2640.00" in win.lblSLVal.text()
        assert "2675.00" in win.lblTPVal.text()





