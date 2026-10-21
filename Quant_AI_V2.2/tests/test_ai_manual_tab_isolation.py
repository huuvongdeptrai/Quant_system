"""
Unit tests for AI Strategy and Manual Order Tab Isolation and Standby Purity.
Ensures that:
1. In Standby (Awaiting setup), AI Strategy Card strictly displays NO ORDER with -- values and clean chart.
2. Switching to Manual Order and back to AI Strategy does NOT leak manual order metrics into the AI card.
"""

import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QMainWindow, QFrame, QVBoxLayout

from frontend.controllers.chart.chart_canvas import setup_chart_ui
from frontend.controllers.chart.trading_plan_panel import (
    setup_trading_plan_cards,
    update_order_proposal_html,
    clear_manual_chart_lines,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def _create_test_window():
    win = QMainWindow()
    win.current_sym = "XAUUSD"
    win.is_dark_theme = True

    # Setup Chart UI
    win.frameChartArea = QFrame()
    win.frameChartArea.setLayout(QVBoxLayout())
    setup_chart_ui(win)

    # Setup Trading Plan Drawer
    win.frameAIArea = QFrame()
    win.layoutAIArea = QVBoxLayout(win.frameAIArea)
    setup_trading_plan_cards(win, is_dark=True)
    return win


def test_ai_strategy_standby_state_purity(qapp):
    """Verifies that in Standby, Card 2 is NO ORDER and chart lines are cleared."""
    win = _create_test_window()

    # Emit standby update (no signal)
    update_order_proposal_html(
        win,
        sym="XAUUSD",
        has_signal=False,
        model_name="ICT Zones Pro v4.2",
    )

    assert win.lblOrderTypeBadge.text() == "NO ORDER"
    assert win.lblEntryVal.text() == "--"
    assert win.lblSLVal.text() == "--"
    assert win.lblTPVal.text() == "--"
    assert win.lblSizeVal.text() == "--"
    assert win.btnApproveOrder.text() == "AWAITING STRATEGY SIGNAL"
    assert win.btnApproveOrder.isEnabled() is False

    # Chart order lines must not be active
    assert win.line_order_entry.isVisible() is False or not win.order_proposal_active


def test_manual_to_ai_tab_switch_state_isolation(qapp):
    """
    Simulates user switching from AI Strategy -> Manual Order -> AI Strategy.
    Verifies that manual order values do NOT leak into AI Strategy Card.
    """
    win = _create_test_window()

    # 1. Start in Standby AI mode
    update_order_proposal_html(
        win,
        sym="XAUUSD",
        has_signal=False,
        model_name="ICT Zones Pro v4.2",
    )
    assert win.lblOrderTypeBadge.text() == "NO ORDER"

    # 2. Switch to MANUAL ORDER
    win.btnPlanModeManual.click()
    assert win._plan_mode == "manual"
    assert not win.containerPlanManual.isHidden()
    assert win.containerPlanAI.isHidden()

    # Simulate manual user entering 4137.88 entry, 4147.88 SL, 4117.88 TP
    if hasattr(win, "spinManualPendingPrice") and win.spinManualPendingPrice:
        win.spinManualPendingPrice.setValue(4137.88)
    if hasattr(win, "spinManualSL") and win.spinManualSL:
        win.spinManualSL.setValue(4147.88)
    if hasattr(win, "spinManualTP") and win.spinManualTP:
        win.spinManualTP.setValue(4117.88)

    # 3. Switch BACK to AI STRATEGY
    win.btnPlanModeAI.click()
    assert win._plan_mode == "ai"
    assert not win.containerPlanAI.isHidden()
    assert win.containerPlanManual.isHidden()

    # 4. AI Strategy Card must be strictly clean (STANDBY NO ORDER), not leaking 4137.88!
    assert win.lblOrderTypeBadge.text() == "NO ORDER"
    assert win.lblEntryVal.text() == "--"
    assert win.lblSLVal.text() == "--"
    assert win.lblTPVal.text() == "--"
    assert win.lblSizeVal.text() == "--"
    assert win.btnApproveOrder.text() == "AWAITING STRATEGY SIGNAL"
    assert win.btnApproveOrder.isEnabled() is False
