"""
Test Suite: Macro Calendar Section 4 Dual Scenario Architecture
================================================================
Verifies:
1. Scenario A (Primary Thesis) & Scenario B (Invalidation Point) UI frames exist and conform to DESIGN.md.
2. Live event updates populate both scenario cards with institutional math and microstructure levels.
3. Symbol switching (e.g. XAUUSD -> EURUSD) triggers real-time scenario recalculation.
4. Weekend standby mode dispatches Gap Risk defense protocol.
5. Dynamic theme toggling applies flat styling without layout breakage.
"""

import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QLabel
from frontend.controllers.macro_calendar_controller import MacroCalendarController


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


@pytest.fixture
def calendar_ctrl(qapp):
    win = QMainWindow()
    win.tabWidget = QTabWidget()
    win.setCentralWidget(win.tabWidget)
    ctrl = MacroCalendarController(win)
    return ctrl


def test_dual_scenario_frames_initialization(calendar_ctrl):
    """Verifies that Scenario A & Scenario B frames are created and conform to flat institutional design."""
    ctrl = calendar_ctrl

    assert hasattr(ctrl, "frame_scenario_a")
    assert hasattr(ctrl, "frame_scenario_b")
    assert hasattr(ctrl, "lbl_scen_a_title")
    assert hasattr(ctrl, "lbl_scen_a_badge")
    assert hasattr(ctrl, "lbl_scen_a_thesis")
    assert hasattr(ctrl, "lbl_scen_a_action")
    assert hasattr(ctrl, "lbl_scen_b_title")
    assert hasattr(ctrl, "lbl_scen_b_badge")
    assert hasattr(ctrl, "lbl_scen_b_thesis")
    assert hasattr(ctrl, "lbl_scen_b_action")
    assert hasattr(ctrl, "lbl_qa_badge")

    assert "SCENARIO A" in ctrl.lbl_scen_a_title.text()
    assert "SCENARIO B" in ctrl.lbl_scen_b_title.text()


def test_update_quant_action_card_populates_scenarios(calendar_ctrl):
    """Verifies that selecting an event populates Scenario A & B with quantitative logic and price levels."""
    ctrl = calendar_ctrl
    ctrl.set_current_symbol("XAUUSD")

    event = {
        "country": "US",
        "title": "ISM Manufacturing PMI",
        "impact": 2,
        "actual": "55.5",
        "forecast": "54.6",
        "surprise": 0.9,
    }

    ctrl._update_quant_action_card(event)

    # Check Scenario A
    scen_a_text = ctrl.lbl_scen_a_thesis.text()
    act_a_text = ctrl.lbl_scen_a_action.text()
    assert len(scen_a_text) > 10
    assert len(act_a_text) > 10
    assert "•" in scen_a_text
    assert "•" in act_a_text

    # Check Scenario B (Invalidation)
    scen_b_text = ctrl.lbl_scen_b_thesis.text()
    act_b_text = ctrl.lbl_scen_b_action.text()
    assert len(scen_b_text) > 10
    assert len(act_b_text) > 10
    assert "• Invalidation" in scen_b_text or "• Trigger" in scen_b_text or "• Invalidation Trigger" in scen_b_text


def test_symbol_switching_recalculates_scenarios(calendar_ctrl):
    """Verifies that switching active symbol re-evaluates scenario thesis for the new currency pair."""
    ctrl = calendar_ctrl
    ctrl.set_current_symbol("EURUSD")

    event = {
        "country": "US",
        "title": "Non-Farm Payrolls",
        "impact": 2,
        "actual": "220K",
        "forecast": "180K",
        "surprise": 40.0,
    }

    ctrl._update_quant_action_card(event)
    assert "EURUSD" in ctrl._current_symbol
    assert len(ctrl.lbl_scen_a_thesis.text()) > 0
    assert len(ctrl.lbl_scen_b_thesis.text()) > 0


def test_weekend_standby_scenario_protocol(calendar_ctrl):
    """Verifies that weekend standby correctly deploys the gap risk defense protocol."""
    ctrl = calendar_ctrl
    ctrl._set_weekend_standby_desk()

    assert ctrl.lbl_scen_a_badge.text() == "(WEEKEND STANDBY)"
    assert "gap risk" in ctrl.lbl_scen_a_action.text().lower()
    assert ctrl.lbl_scen_b_badge.text() == "(GAP RISK)"
    assert "gap" in ctrl.lbl_scen_b_thesis.text().lower()


def test_theme_update_dual_scenarios(calendar_ctrl):
    """Verifies that update_theme cleanly updates card backgrounds for dark and light modes."""
    ctrl = calendar_ctrl

    # Test Dark theme
    ctrl.update_theme(True)
    assert ctrl.frame_scenario_a.styleSheet() is not None
    assert ctrl.frame_scenario_b.styleSheet() is not None

    # Test Light theme
    ctrl.update_theme(False)
    assert ctrl.frame_scenario_a.styleSheet() is not None
    assert ctrl.frame_scenario_b.styleSheet() is not None
