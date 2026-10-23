# -*- coding: utf-8 -*-
"""
Unit tests for MacroContextBus, Multi-Asset Adapters, and System Risk Gate.
Verifies:
1. Multi-Asset Driver Dispatch (Forex, Metals, Crypto, Indices).
2. MacroContextBus Singleton & Slow-Cycle Profile Caching.
3. Human-In-The-Loop Semi-Auto Controls (manual_override_lock & force_defense_active).
4. Pre-Trade News Compliance Gatekeeper with Override Support.
5. In-Trade Position Defense Triggering at T-15m.
6. Watchlist 5th Column (MACRO/RISK) Compact Rendering.
"""
import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication

from backend.core.macro_context_bus import MacroContextBus, SymbolMacroProfile
from backend.infrastructure.data_providers.asset_registry import AssetRegistry, AssetClass
from backend.infrastructure.data_providers.adapters.forex_adapter import ForexContextAdapter
from backend.infrastructure.data_providers.adapters.equity_adapter import EquityIndexAdapter
from backend.infrastructure.ai_engines.ai.decision_gate import DecisionGate


def test_asset_registry_multi_asset_dispatch():
    """Verifies that AssetRegistry dispatches specialized adapters per asset class."""
    metals = AssetRegistry.get_adapter("XAUUSD")
    forex = AssetRegistry.get_adapter("EURUSD")
    crypto = AssetRegistry.get_adapter("BTCUSD")
    equity = AssetRegistry.get_adapter("US30")

    assert type(metals).__name__ == "PreciousMetalsAdapter"
    assert type(forex).__name__ == "ForexContextAdapter"
    assert type(crypto).__name__ == "CryptoContextAdapter"
    assert type(equity).__name__ == "EquityIndexAdapter"


def test_forex_context_adapter_currency_parsing_and_bias():
    """Verifies that ForexContextAdapter decomposes currency pairs and calculates bias."""
    adapter = ForexContextAdapter()
    base, quote = adapter.parse_currency_pair("EURUSD")
    assert base == "EUR"
    assert quote == "USD"

    base_jpy, quote_jpy = adapter.parse_currency_pair("USDJPY.m")
    assert base_jpy == "USD"
    assert quote_jpy == "JPY"

    bias = adapter.get_macro_bias("EURUSD")
    assert bias in ["BULLISH", "BEARISH", "NEUTRAL"]


def test_equity_index_adapter_bias():
    """Verifies that EquityIndexAdapter evaluates VIX volatility regimes."""
    adapter = EquityIndexAdapter()
    bias = adapter.get_macro_bias("US30")
    assert bias in ["BULLISH", "BEARISH", "NEUTRAL"]

    # Extreme VIX panic filter test
    allowed, reason = adapter.evaluate_risk_rules("US30", "BUY", {"vix": 35.0})
    assert allowed is False
    assert "VIX Market Panic" in reason


def test_macro_context_bus_singleton_and_profiles():
    """Verifies MacroContextBus singleton instance and in-memory profile caching."""
    bus1 = MacroContextBus.get_instance()
    bus2 = MacroContextBus.get_instance()
    assert bus1 is bus2

    prof_gold = bus1.get_profile("XAUUSD")
    assert prof_gold.symbol == "XAUUSD"
    assert prof_gold.asset_class == "COMMODITY_PRECIOUS"
    assert prof_gold.badge_text in ["BULL", "BEAR", "NEUT", "LOCK", "OVRD"] or prof_gold.badge_text.startswith("T-")

    prof_eur = bus1.get_profile("EURUSD")
    assert prof_eur.symbol == "EURUSD"
    assert prof_eur.asset_class == "FOREX"


def test_macro_context_bus_manual_override_and_pre_trade_gate():
    """Verifies that manual_override_lock bypasses high-impact news blackout."""
    bus = MacroContextBus.get_instance()
    bus.set_manual_override(False)

    prof = bus.get_profile("EURUSD")
    # Simulate news blackout
    prof.news_blackout = True
    prof.next_event_title = "ECB Rate Decision"

    # 1. Without override -> BLOCKED
    cleared, status, msg = bus.check_pre_trade_news_compliance("EURUSD")
    assert cleared is False
    assert status == "BLOCKED"
    assert "ECB Rate Decision" in msg

    # 2. Human operator toggles OVERRIDE LOCK -> PASS (OVERRIDE)
    bus.set_manual_override(True)
    cleared_ovr, status_ovr, msg_ovr = bus.check_pre_trade_news_compliance("EURUSD")
    assert cleared_ovr is True
    assert status_ovr == "OVERRIDE"
    assert "Manual Override Active" in msg_ovr

    # Reset override
    bus.set_manual_override(False)


def test_macro_context_bus_force_defense_trigger():
    """Verifies that trigger_force_defense executes immediately without waiting for T-15m."""
    bus = MacroContextBus.get_instance()
    with patch.object(bus._event_risk_engine, "evaluate_pre_news_defense", return_value=[{"action": "BE"}]) as mock_def:
        results = bus.trigger_force_defense()
        assert len(results) == 1
        mock_def.assert_called_once()


def test_decision_gate_integrates_news_compliance():
    """Verifies that DecisionGate enforces pre-trade news gate before allowing BUY/SELL."""
    dg = DecisionGate()
    bus = MacroContextBus.get_instance()
    bus.set_manual_override(False)

    # Free mode allows trades regardless
    res_free = dg.evaluate("EURUSD", "BUY", gate_mode="FREE")
    assert res_free["decision"] == "BUY"

    # Mock technical position at support with Bullish HTF trend
    mock_pos = {
        "position": "AT_SUPPORT",
        "price": 1.0850,
        "support": 1.0840,
        "resistance": 1.0920,
        "pct_from_support": 0.10,
        "pct_from_resistance": 0.90,
    }

    with patch.object(dg, "_get_price_position", return_value=mock_pos),          patch.object(dg, "_get_htf_bias", return_value="BULLISH"),          patch.object(dg, "_get_macro_bias", return_value="BULLISH"):

        # 1. Clear news -> BUY approved
        prof = bus.get_profile("EURUSD")
        prof.news_blackout = False
        res_ok = dg.evaluate("EURUSD", "BUY", gate_mode="FULL")
        assert res_ok["decision"] == "BUY"

        # 2. Red event blackout without override -> Blocked with WAIT
        prof.news_blackout = True
        prof.next_event_title = "ECB Rate Decision"
        res_blocked = dg.evaluate("EURUSD", "BUY", gate_mode="FULL")
        assert res_blocked["decision"] == "WAIT"
        assert "NewsDefenseGate" in res_blocked["reason"]

        # 3. Manual override active -> Approved with OVERRIDE
        bus.set_manual_override(True)
        res_overridden = dg.evaluate("EURUSD", "BUY", gate_mode="FULL")
        assert res_overridden["decision"] == "BUY"

        # Cleanup
        bus.set_manual_override(False)
        prof.news_blackout = False


def test_watchlist_5th_column_macro_badge():
    """Verifies that Watchlist tree has 5 columns and renders compact MACRO badges."""
    app = QApplication.instance() or QApplication([])
    from frontend.controllers.watchlist.watchlist_controller import WatchlistManager
    from PySide6.QtWidgets import QMainWindow, QTreeWidget

    mock_win = QMainWindow()
    mock_tree = QTreeWidget()
    mock_win.treeWatchlist = mock_tree

    wm = WatchlistManager(mock_win)
    assert wm.tree.columnCount() == 5
    header_labels = [wm.tree.headerItem().text(i) for i in range(5)]
    assert header_labels == ["SYMBOL", "BID", "PIPS", "%CHG", "MACRO"]

    # Add item and verify 5th column
    wm.add_symbol_to_tree("EURUSD", "FOREX", auto_save=False)
    cat = wm.tree.topLevelItem(0)
    assert cat is not None
    item = cat.child(0)
    assert item is not None
    badge_text = item.text(4)
    assert badge_text in ["BULL", "BEAR", "NEUT", "LOCK", "OVRD"] or badge_text.startswith("T-")
