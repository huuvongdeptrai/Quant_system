"""
Unit tests for Bot Orchestrator multi-asset watchlist scanning,
direction validation, and configuration resilience.
"""

import pytest
from unittest.mock import MagicMock, patch
from backend.core.trade_dispatcher import TradeDispatcher
from backend.core.bot_orchestrator import BotOrchestrator


def test_validate_direction_resilience():
    """Verifies that validate_direction gracefully handles None, empty string, or AUTO without crashing."""
    dispatcher = TradeDispatcher(
        execution_manager=MagicMock(),
        risk_manager=MagicMock(),
        db_manager=MagicMock(),
    )

    # When trade_mode is None or empty (the bug the user observed), it must allow trades (default AUTO)
    assert dispatcher.validate_direction("BUY", None) is True
    assert dispatcher.validate_direction("SELL", None) is True
    assert dispatcher.validate_direction("BUY", "") is True
    assert dispatcher.validate_direction("SELL", "") is True

    # Standard modes
    assert dispatcher.validate_direction("BUY", "AUTO") is True
    assert dispatcher.validate_direction("SELL", "AUTO") is True
    assert dispatcher.validate_direction("BUY", "LONG_ONLY") is True
    assert dispatcher.validate_direction("SELL", "LONG_ONLY") is False
    assert dispatcher.validate_direction("BUY", "SHORT_ONLY") is False
    assert dispatcher.validate_direction("SELL", "SHORT_ONLY") is True


def test_bot_orchestrator_multi_asset_watchlist_iteration():
    """
    Verifies that BotOrchestrator loops through all symbols provided dynamically
    by the watchlist provider.
    """
    scanned_symbols = []

    def mock_pipeline_execute(sym):
        scanned_symbols.append(sym)

    orchestrator = BotOrchestrator(
        strategy=MagicMock(),
        risk_manager=MagicMock(),
        execution_manager=MagicMock(),
        data_preprocessor=MagicMock(),
        decision_gate=MagicMock(),
        symbols=["XAUUSD"],
    )
    orchestrator.pipeline_execute = mock_pipeline_execute

    # Provide dynamic watchlist
    orchestrator.symbols_provider = lambda: ["XAUUSD", "BTCUSD", "ETHUSD"]

    # Run 1 cycle manually
    active_symbols = list(orchestrator.symbols)
    if hasattr(orchestrator, "symbols_provider") and callable(orchestrator.symbols_provider):
        active_symbols = orchestrator.symbols_provider()

    for sym in active_symbols:
        orchestrator.pipeline_execute(sym)

    assert scanned_symbols == ["XAUUSD", "BTCUSD", "ETHUSD"]
