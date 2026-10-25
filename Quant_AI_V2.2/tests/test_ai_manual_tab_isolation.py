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


@pytest.fixture(scope="session")
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

    with patch("backend.infrastructure.brokers.mt5_safe.mt5.terminal_info", return_value=None), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.positions_get", return_value=[]), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.orders_get", return_value=[]):
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


def test_drawer_close_preserves_on_chart_order_lines(qapp):
    """
    Verifies institutional requirement:
    Closing the Trading Plan drawer must NEVER remove the active order lines from the chart,
    enabling continuous price-action tracking across full-width chart.
    """
    win = _create_test_window()

    # Setup active order proposal
    update_order_proposal_html(
        win,
        sym="XAUUSD",
        entry=4137.88,
        sl=4147.88,
        tp=4117.88,
        has_signal=True,
        signal_type="SELL",
        calc_lot=0.95,
        model_name="ICT Zones Pro v4.2",
    )

    assert win.line_order_entry.isVisible() is True
    assert win.line_order_sl.isVisible() is True
    assert win.line_order_tp.isVisible() is True

    # Close drawer
    win._close_ai_drawer()

    # Lines MUST remain visible on chart!
    assert win.line_order_entry.isVisible() is True
    assert win.line_order_sl.isVisible() is True
    assert win.line_order_tp.isVisible() is True


def test_sync_live_position_renders_pending_orders(qapp):
    """
    Verifies that MT5 pending orders (e.g. SELL LIMIT) are detected and rendered on chart.
    """
    from frontend.controllers.chart.trading_plan_panel import sync_live_position_to_ai_plan

    win = _create_test_window()
    win._plan_mode = "ai"

    # Mock MT5: no open positions, but 1 pending order
    mock_order = MagicMock()
    mock_order.ticket = 998877
    mock_order.symbol = "XAUUSD"
    mock_order.type = 3  # ORDER_TYPE_SELL_LIMIT
    mock_order.volume_initial = 0.95
    mock_order.price_open = 4137.88
    mock_order.sl = 4147.88
    mock_order.tp = 4117.88

    with patch("backend.infrastructure.brokers.mt5_safe.mt5.terminal_info", return_value=MagicMock()), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.positions_get", return_value=[]), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.orders_get", return_value=[mock_order]):
        sync_live_position_to_ai_plan(win)

    assert win.is_pending_order is True
    assert win.pending_ticket == 998877
    assert (998877, "ENTRY") in win.chart_order_lines
    assert win.chart_order_lines[(998877, "ENTRY")].isVisible() is True
    assert win.line_order_entry.isVisible() is False
    assert win.lblOrderTypeBadge.text() == "PENDING #998877"


def test_drawer_close_clears_unsubmitted_manual_draft_preview(qapp):
    """
    Verifies that unsubmitted manual draft preview lines are hidden when the drawer is closed,
    preventing phantom order confusion when no trade was actually placed.
    """
    from frontend.controllers.chart.trading_plan_panel import _setup_chart_manual_lines

    win = _create_test_window()
    win.show()
    win._open_ai_drawer()
    win._plan_mode = "manual"
    win.is_live_position = False
    win.is_pending_order = False
    win._show_manual_preview = True

    # Setup manual draft lines while drawer is open
    _setup_chart_manual_lines(win, "XAUUSD", is_buy=True, lot=1.45, sl=4130.35, tp=4137.85)
    assert win.line_order_entry.isVisible() is True
    assert win.line_order_sl.isVisible() is True
    assert win.line_order_tp.isVisible() is True

    # Closing drawer without placing order MUST clear unsubmitted draft lines!
    win._close_ai_drawer()
    assert win.line_order_entry.isVisible() is False
    assert win.line_order_sl.isVisible() is False
    assert win.line_order_tp.isVisible() is False
    win.close()


def test_drawer_close_reopen_preserves_trend_and_checklist(qapp):
    """
    Verifies that when AI analysis identifies a trend (e.g. Bullish/Bearish Bias Confirmed)
    in standby mode, closing the drawer and reopening it does NOT clobber the trend or checklist.
    """
    from backend.core.strategies import ChecklistItem, ChecklistStatus

    win = _create_test_window()
    win.show()
    win._plan_mode = "ai"

    chk = [
        ChecklistItem("Trend Structure", "Bullish Bias Confirmed", ChecklistStatus.PASSED),
        ChecklistItem("Liquidity Sweep", "Awaiting Asian Sweep", ChecklistStatus.PENDING),
        ChecklistItem("Order Blocks & FVG", "Awaiting Mitigation", ChecklistStatus.PENDING),
    ]

    # Standby analysis completes with trend identified
    update_order_proposal_html(
        win,
        sym="XAUUSD",
        has_signal=False,
        signal_type="HOLD",
        model_name="ICT",
        grade="STATUS: STANDBY",
        chk1="Bullish Bias Confirmed",
        checklist=chk,
    )

    assert win.lblChk1Val.text() == "Bullish Bias Confirmed"
    assert win.lblModelGrade.text() == "STATUS: STANDBY"

    # Close drawer
    win._close_ai_drawer()

    # Reopen drawer
    win._open_ai_drawer()

    # Must preserve trend structure and standby grade without clobbering to default
    assert win.lblChk1Val.text() == "Bullish Bias Confirmed"
    assert win.lblModelGrade.text() == "STATUS: STANDBY"
    win.close()


def test_tab_switch_to_manual_and_back_preserves_trend_and_checklist(qapp):
    """
    Verifies that switching to Manual tab and then back to AI tab does NOT lose
    the calculated trend or checklist.
    """
    from backend.core.strategies import ChecklistItem, ChecklistStatus

    win = _create_test_window()
    win.show()
    win._plan_mode = "ai"

    chk = [
        ChecklistItem("Trend Structure", "Bearish Bias Confirmed", ChecklistStatus.PASSED),
        ChecklistItem("Liquidity Sweep", "Awaiting Asian Sweep", ChecklistStatus.PENDING),
        ChecklistItem("Order Blocks & FVG", "Awaiting Mitigation", ChecklistStatus.PENDING),
    ]

    update_order_proposal_html(
        win,
        sym="XAUUSD",
        has_signal=False,
        signal_type="HOLD",
        model_name="ICT",
        grade="STATUS: STANDBY",
        chk1="Bearish Bias Confirmed",
        checklist=chk,
    )

    assert win.lblChk1Val.text() == "Bearish Bias Confirmed"

    # Switch to manual mode
    win._switch_plan_mode("manual")
    assert win._plan_mode == "manual"

    # Switch back to AI mode
    win._switch_plan_mode("ai")
    assert win._plan_mode == "ai"

    # Must retain Bearish Bias Confirmed
    assert win.lblChk1Val.text() == "Bearish Bias Confirmed"
    assert win.lblModelGrade.text() == "STATUS: STANDBY"
    win.close()

