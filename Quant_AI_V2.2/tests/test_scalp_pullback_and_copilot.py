# -*- coding: utf-8 -*-
"""
Unit tests for Scalp Pullback Counter-Trend Strategy Execution and UI Copilot Badge.
Verifies:
1. DecisionGate Scalp Pullback Activation (Resistance SELL vs Macro BULL, Support BUY vs Macro BEAR).
2. Pro-Trend Full-Sizing Verification (100% Vol, 2.5R TP).
3. Bot Orchestrator Quantitative Lot Halving (50% Risk) and 1.5R TP Capping.
4. UI Copilot Advisory Badge (PRO-TREND vs COUNTER-TREND) with Zero Lot Tampering.
"""
import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QDoubleSpinBox, QPushButton

from backend.infrastructure.ai_engines.ai.decision_gate import DecisionGate
from backend.core.macro_context_bus import MacroContextBus


def test_decision_gate_scalp_pullback_resistance_sell_macro_bull():
    """Verifies that SELL at Resistance with Macro BULL activates SCALP_PULLBACK (50% lot, 1.5R TP)."""
    dg = DecisionGate()
    bus = MacroContextBus.get_instance()
    bus.set_manual_override(False)

    prof = bus.get_profile("XAUUSD")
    prof.news_blackout = False

    mock_pos = {
        "position": "AT_RESISTANCE",
        "price": 2680.0,
        "support": 2620.0,
        "resistance": 2682.0,
        "pct_from_support": 0.95,
        "pct_from_resistance": 0.05,
    }

    with patch.object(dg, "_get_price_position", return_value=mock_pos), \
         patch.object(dg, "_get_htf_bias", return_value="BULLISH"), \
         patch.object(dg, "_get_macro_bias", return_value="BULLISH"):

        res = dg.evaluate("XAUUSD", "SELL", gate_mode="FULL")

        assert res["decision"] == "SELL"
        assert res["trade_mode"] == "SCALP_PULLBACK"
        assert res["size_multiplier"] == 0.5
        assert res["tp_limit_r"] == 1.5
        assert res["be_trigger_r"] == 1.0
        assert "Scalp Pullback" in res["reason"]


def test_decision_gate_scalp_pullback_support_buy_macro_bear():
    """Verifies that BUY at Support with Macro BEAR activates SCALP_PULLBACK (50% lot, 1.5R TP)."""
    dg = DecisionGate()
    bus = MacroContextBus.get_instance()
    bus.set_manual_override(False)

    prof = bus.get_profile("XAUUSD")
    prof.news_blackout = False

    mock_pos = {
        "position": "AT_SUPPORT",
        "price": 2622.0,
        "support": 2620.0,
        "resistance": 2680.0,
        "pct_from_support": 0.05,
        "pct_from_resistance": 0.95,
    }

    with patch.object(dg, "_get_price_position", return_value=mock_pos), \
         patch.object(dg, "_get_htf_bias", return_value="BEARISH"), \
         patch.object(dg, "_get_macro_bias", return_value="BEARISH"):

        res = dg.evaluate("XAUUSD", "BUY", gate_mode="FULL")

        assert res["decision"] == "BUY"
        assert res["trade_mode"] == "SCALP_PULLBACK"
        assert res["size_multiplier"] == 0.5
        assert res["tp_limit_r"] == 1.5
        assert res["be_trigger_r"] == 1.0
        assert "Scalp Pullback" in res["reason"]


def test_decision_gate_pro_trend_full_size():
    """Verifies that Pro-Trend trades retain 100% volume and standard 2.5R TP."""
    dg = DecisionGate()
    bus = MacroContextBus.get_instance()
    bus.set_manual_override(False)

    prof = bus.get_profile("XAUUSD")
    prof.news_blackout = False

    mock_pos = {
        "position": "AT_SUPPORT",
        "price": 2622.0,
        "support": 2620.0,
        "resistance": 2680.0,
        "pct_from_support": 0.05,
        "pct_from_resistance": 0.95,
    }

    with patch.object(dg, "_get_price_position", return_value=mock_pos), \
         patch.object(dg, "_get_htf_bias", return_value="BULLISH"), \
         patch.object(dg, "_get_macro_bias", return_value="BULLISH"):

        res = dg.evaluate("XAUUSD", "BUY", gate_mode="FULL")

        assert res["decision"] == "BUY"
        assert res["trade_mode"] == "NORMAL"
        assert res["size_multiplier"] == 1.0
        assert res["tp_limit_r"] == 2.5
        assert res["be_trigger_r"] == 1.5


def test_bot_orchestrator_scalp_pullback_scaling_and_tp_capping():
    """Verifies that BotOrchestrator halves risk and caps TP to 1.5R when trade_mode is SCALP_PULLBACK."""
    from backend.core.bot_orchestrator import BotOrchestrator

    mock_exec = MagicMock()
    mock_risk = MagicMock()
    mock_gate = MagicMock()
    mock_prep = MagicMock()
    mock_ict = MagicMock()

    bot = BotOrchestrator(
        strategy=mock_ict,
        risk_manager=mock_risk,
        execution_manager=mock_exec,
        data_preprocessor=mock_prep,
        decision_gate=mock_gate,
        symbols=["XAUUSD"],
        risk_per_trade=1.0,
        strategy_name="ICT_SmartMoney",
    )

    # Mock dispatcher
    bot.trade_dispatcher = MagicMock()

    # Simulate DecisionGate returning SCALP_PULLBACK
    mock_gate.evaluate.return_value = {
        "decision": "SELL",
        "trade_mode": "SCALP_PULLBACK",
        "size_multiplier": 0.5,
        "tp_limit_r": 1.5,
        "be_trigger_r": 1.0,
        "reason": "[Scalp Pullback] Rejection at Resistance",
    }

    # Simulate strategy analysis: Entry = 2680, SL = 2690 (dist = 10 pts). Default TP = 2650 (3.0R dist = 30 pts)
    rates = [{"time": 1000 + i * 60, "open": 2680, "high": 2685, "low": 2675, "close": 2680, "tick_volume": 100} for i in range(100)]
    mock_ict.analyze.return_value = {
        "signal": "SELL",
        "entry_price": 2680.0,
        "sl": 2690.0,
        "tp": 2650.0,  # 3.0R TP from strategy
        "confidence": 0.90,
    }
    bot.ict = mock_ict

    bot.state_recovery = MagicMock()
    bot.state_recovery.can_open_new_trade.return_value = True
    bot.circuit_guard = MagicMock()
    bot.circuit_guard.circuit_breaker_active = False
    bot.news_filter_enabled = False

    with patch.object(bot, "_check_session_allowed", return_value=(True, "NY")), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.positions_get", return_value=[]), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.copy_rates_from_pos", return_value=rates):
        bot.pipeline_execute("XAUUSD")

    # Assert dispatch_market_order was called
    bot.trade_dispatcher.dispatch_market_order.assert_called_once()
    kwargs = bot.trade_dispatcher.dispatch_market_order.call_args[1]

    assert kwargs["signal"] == "SELL"
    # Risk should be scaled by 0.5 -> 0.5%
    assert kwargs["risk_pct"] == 0.5
    # TP should be capped to 1.5R: entry (2680) - 1.5 * 10 = 2665.0
    assert kwargs["tp_price"] == 2665.0
    assert "SCALP PULLBACK" in kwargs["confidence_str"]


def test_manual_order_copilot_badge_advisory():
    """Verifies that manual order view displays PRO-TREND or COUNTER-TREND badge without altering user's lot."""
    app = QApplication.instance() or QApplication([])
    from frontend.controllers.chart.trading_plan_panel import _recalculate_manual_lot_and_rr

    mock_win = QMainWindow()
    mock_win.current_sym = "XAUUSD"
    mock_win.is_dark_theme = True
    mock_win._manual_direction = "BUY"
    mock_win._user_custom_lot = True

    # Setup components
    lbl_badge = QLabel("INITIAL")
    mock_win.lblManualCopilotBadge = lbl_badge
    spin_lot = QDoubleSpinBox()
    spin_lot.setValue(0.75)  # Custom lot chosen by user
    mock_win.spinManualLot = spin_lot
    spin_sl = QDoubleSpinBox()
    spin_sl.setValue(2640.0)
    mock_win.spinManualSL = spin_sl
    spin_tp = QDoubleSpinBox()
    spin_tp.setValue(2680.0)
    mock_win.spinManualTP = spin_tp

    btn_exec = QPushButton()
    mock_win.btnManualExecute = btn_exec

    bus = MacroContextBus.get_instance()
    prof = bus.get_profile("XAUUSD")

    # Case A: Macro BULLISH + Manual BUY -> PRO-TREND (BULL)
    prof.directional_bias = "BULLISH"
    mock_win._manual_direction = "BUY"
    _recalculate_manual_lot_and_rr(mock_win)

    assert "PRO-TREND" in lbl_badge.text()
    assert "BULL" in lbl_badge.text()
    # User's lot MUST NOT be changed!
    assert spin_lot.value() == 0.75

    # Case B: Macro BULLISH + Manual SELL -> COUNTER-TREND (BULL)
    mock_win._manual_direction = "SELL"
    _recalculate_manual_lot_and_rr(mock_win)

    assert "COUNTER-TREND" in lbl_badge.text()
    assert "BULL" in lbl_badge.text()
    # User's lot MUST STILL NOT be changed!
    assert spin_lot.value() == 0.75
