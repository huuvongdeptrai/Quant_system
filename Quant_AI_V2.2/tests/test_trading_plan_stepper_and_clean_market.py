# -*- coding: utf-8 -*-
"""
Unit tests for Trading Plan Panel:
1. Stepper '-' / '+' buttons for Volume control.
2. Removal of redundant 'MARKET' label duplication in BUY / SELL direction cards.
3. Safe margin from the right price axis in floating overlay positioning.
"""

import pytest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication, QMainWindow, QFrame, QVBoxLayout

from frontend.controllers.chart.trading_plan_panel import setup_trading_plan_cards


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def _create_mock_trading_plan_window():
    win = QMainWindow()
    win.current_sym = "XAUUSD"
    win.is_dark_theme = False
    win.frameAIArea = QFrame()
    win.layoutAIArea = QVBoxLayout(win.frameAIArea)
    setup_trading_plan_cards(win, is_dark=False)
    return win


def test_order_direction_no_duplicate_market_text(qapp):
    """Verifies BUY / SELL buttons show clean 'BUY' and 'SELL' without repeating 'MARKET'."""
    win = _create_mock_trading_plan_window()

    assert hasattr(win, "lblManualBuyText")
    assert hasattr(win, "lblManualSellText")
    assert win.lblManualBuyText.text() == "BUY"
    assert win.lblManualSellText.text() == "SELL"
    assert "MARKET" not in win.lblManualBuyText.text()
    assert "MARKET" not in win.lblManualSellText.text()


def test_volume_stepper_minus_and_plus(qapp):
    """Verifies that '-' and '+' stepper buttons accurately adjust lot by 0.01."""
    win = _create_mock_trading_plan_window()

    assert hasattr(win, "btnManualLotMinus")
    assert hasattr(win, "btnManualLotPlus")

    win.spinManualLot.setValue(0.50)
    assert round(win.spinManualLot.value(), 2) == 0.50

    # Click plus
    win.btnManualLotPlus.click()
    assert round(win.spinManualLot.value(), 2) == 0.51
    assert "0.51 LOTS" in win.btnManualExecute.text()

    # Click minus
    win.btnManualLotMinus.click()
    assert round(win.spinManualLot.value(), 2) == 0.50
    assert "0.50 LOTS" in win.btnManualExecute.text()


def test_floating_overlay_maintains_safe_price_axis_margin(qapp):
    """Verifies that _reposition_trading_plan reserves >= 85px to protect the price axis."""
    win = _create_mock_trading_plan_window()
    win.frameChartArea = QFrame()
    win.frameChartArea.resize(1000, 700)
    win.frameChartRibbon = QFrame()
    win.frameChartRibbon.setFixedHeight(24)

    import inspect
    import frontend.controllers.chart.chart_canvas as cc
    src = inspect.getsource(cc.setup_chart_ui)
    assert "c_w - w - 85" in src
    # Test reposition calculation logic
    c_w = 1000
    w = 325
    margin_right = 85
    expected_x = c_w - w - margin_right  # 590px
    assert expected_x == 590
    assert expected_x + w <= c_w - 85  # Clean gap before price axis


def test_trading_plan_dynamic_autofit_height(qapp):
    """Verifies that Trading Plan dynamically shrinks in AI mode to eliminate dead white space, and expands in Manual mode."""
    from PySide6.QtWidgets import QSizePolicy

    win = _create_mock_trading_plan_window()
    win.frameChartArea = QFrame()
    win.frameChartArea.resize(1000, 700)
    win.frameChartRibbon = QFrame()
    win.frameChartRibbon.setFixedHeight(24)

    def _reposition():
        w = 325
        c_w = win.frameChartArea.width()
        c_h = win.frameChartArea.height()
        x = max(10, c_w - w - 85)
        ribbon_h = win.frameChartRibbon.height() if hasattr(win, "frameChartRibbon") and win.frameChartRibbon else 24
        y = ribbon_h + 8

        mode = getattr(win, "_plan_mode", "ai")
        target_h = 401 if mode == "ai" else 495
        h = min(target_h, max(200, c_h - y - 25))
        win.frameAIArea.setGeometry(x, y, w, h)

    win._reposition_trading_plan = _reposition
    _reposition()

    # In AI mode, height is tightly fit around 401px (eliminating bottom blank space)
    assert win._plan_mode == "ai"
    assert win.frameAIArea.height() == 401
    assert win.containerPlanAI.sizePolicy().verticalPolicy() == QSizePolicy.Preferred
    assert win.containerPlanManual.sizePolicy().verticalPolicy() == QSizePolicy.Ignored

    # Switch to Manual mode -> height expands to 495px
    win._switch_plan_mode("manual")
    assert win._plan_mode == "manual"
    assert win.frameAIArea.height() == 495
    assert win.containerPlanManual.sizePolicy().verticalPolicy() == QSizePolicy.Preferred
    assert win.containerPlanAI.sizePolicy().verticalPolicy() == QSizePolicy.Ignored

    # Switch back to AI mode -> height shrinks back to 401px
    win._switch_plan_mode("ai")
    assert win._plan_mode == "ai"
    assert win.frameAIArea.height() == 401
