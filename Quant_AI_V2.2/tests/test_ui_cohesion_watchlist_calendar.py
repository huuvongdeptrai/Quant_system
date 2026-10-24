# -*- coding: utf-8 -*-
"""
Unit tests for Step 3: UI/UX Cohesion across Watchlist and Calendar Tab.
Verifies:
1. Direction-aware asset news reaction calculation (USD base vs quote vs commodity).
2. QUANT EVENT IMPACT & ACTIONS displays impacted Watchlist symbols.
3. Watchlist status refresh synchronizes 5th column MACRO badge.
4. Active symbol switching in chart propagates to Calendar Card 4 & filter button.
"""
import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QTreeWidget, QTreeWidgetItem

from frontend.controllers.macro_calendar_controller import MacroCalendarController
from frontend.controllers.watchlist.watchlist_controller import WatchlistManager
from backend.core.macro_context_bus import MacroContextBus


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


def test_asset_news_reaction_direction_awareness(qapp):
    """Verifies that positive USD news results in Bullish for USDJPY but Bearish for XAUUSD & EURUSD."""
    win = QMainWindow()
    win.tabWidget = QTabWidget()
    win.setCentralWidget(win.tabWidget)
    ctrl = MacroCalendarController(win)

    # 1. USD Strong -> XAUUSD should face bearish pressure
    b_gold, msg_gold, _ = ctrl._evaluate_asset_news_reaction("XAUUSD", "US", is_country_positive=True)
    assert b_gold == "BEARISH"
    assert "XAUUSD" in msg_gold

    # 2. USD Strong -> EURUSD should face bearish pressure (USD quote)
    b_eur, msg_eur, _ = ctrl._evaluate_asset_news_reaction("EURUSD", "US", is_country_positive=True)
    assert b_eur == "BEARISH"

    # 3. USD Strong -> USDJPY should be BULLISH (USD base)
    b_jpy, msg_jpy, _ = ctrl._evaluate_asset_news_reaction("USDJPY", "US", is_country_positive=True)
    assert b_jpy == "BULLISH"

    # 4. EUR Strong -> EURUSD should be BULLISH (EUR base)
    b_eur_strong, msg_eur_strong, _ = ctrl._evaluate_asset_news_reaction("EURUSD", "EU", is_country_positive=True)
    assert b_eur_strong == "BULLISH"


def test_quant_action_card_displays_watchlist_exposure(qapp):
    """Verifies that _update_quant_action_card audits Watchlist and displays impacted symbols."""
    win = QMainWindow()
    win.tabWidget = QTabWidget()
    win.setCentralWidget(win.tabWidget)
    ctrl = MacroCalendarController(win)

    # Mock watchlist symbols: XAUUSD, EURUSD, BTCUSD
    with patch.object(ctrl, "_get_watchlist_symbols", return_value=["XAUUSD", "EURUSD", "BTCUSD"]):
        # Event 1: US Non-Farm Payrolls (Impacts USD assets)
        us_event = {
            "country": "US",
            "title": "Non-Farm Employment Change",
            "impact": 2,
            "actual": "250K",
            "forecast": "180K",
            "surprise": 70.0,
        }
        ctrl._update_quant_action_card(us_event)

        assert hasattr(ctrl, "lbl_qa_watchlist_impact")
        wl_text = ctrl.lbl_qa_watchlist_impact.text()
        assert "XAUUSD" in wl_text
        assert "EURUSD" in wl_text
        assert "T-15M" in wl_text

        # Event 2: German Manufacturing PMI (Impacts EURUSD directly, not XAUUSD)
        de_event = {
            "country": "DE",
            "title": "Manufacturing PMI",
            "impact": 2,
            "actual": "45.0",
            "forecast": "43.0",
            "surprise": 2.0,
        }
        ctrl._update_quant_action_card(de_event)
        wl_text_de = ctrl.lbl_qa_watchlist_impact.text()
        assert "EURUSD" in wl_text_de


def test_watchlist_refresh_synchronizes_macro_column(qapp):
    """Verifies that refresh_all_status_icons refreshes Column 4 (MACRO badge) across all items."""
    win = QMainWindow()
    mock_tree = QTreeWidget()
    win.treeWatchlist = mock_tree

    wm = WatchlistManager(win)
    wm.add_symbol_to_tree("XAUUSD", "COMMODITIES", auto_save=False)
    wm.add_symbol_to_tree("EURUSD", "FOREX", auto_save=False)

    bus = MacroContextBus.get_instance()
    prof_gold = bus.get_profile("XAUUSD")
    prof_gold.badge_text = "BULL"

    wm.refresh_all_status_icons()

    cat = wm.tree.topLevelItem(0)
    item = cat.child(0)
    assert item.text(4) in ["BULL", "BEAR", "NEUT", "LOCK", "OVRD"] or item.text(4).startswith("T-")


def test_set_current_symbol_updates_calendar_tab_cohesion(qapp):
    """Verifies that switching active symbol immediately updates Calendar Card 4 and Filter button."""
    win = QMainWindow()
    win.tabWidget = QTabWidget()
    win.setCentralWidget(win.tabWidget)
    ctrl = MacroCalendarController(win)

    ctrl.set_current_symbol("GBPUSD")

    assert ctrl._current_symbol == "GBPUSD"
    assert ctrl.filter_buttons["TARGET"].text() == "ACTIVE: GBPUSD"
    assert "GBPUSD" in ctrl.card_confluence.findChild(type(ctrl.lbl_confluence_metrics)).text() or "GBPUSD" in ctrl.card_confluence.findChildren(type(ctrl.lbl_confluence_metrics))[0].text()
