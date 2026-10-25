"""
Unit tests for Institutional Engine Configuration Schema (Pillar 1).
Validates immutable BotRunConfig, enum parsing, safe fallbacks,
and BotOrchestrator headless decoupling.
"""

import pytest
from unittest.mock import MagicMock
from backend.infrastructure.brokers.mt5_safe import mt5
from backend.core.engine_config import (
    BotRunConfig,
    ExecutionMode,
    TradeMode,
    GateMode,
    resolve_mt5_timeframe,
    get_timeframe_name,
)
from backend.core.bot_orchestrator import BotOrchestrator


def test_bot_run_config_defaults():
    """Verifies that default BotRunConfig has zero None values and strict type safety."""
    cfg = BotRunConfig()
    assert cfg.symbols == ("XAUUSD",)
    assert cfg.timeframe == mt5.TIMEFRAME_M15
    assert cfg.strategy_id == "builtin_ict_pro"
    assert cfg.execution_mode == ExecutionMode.SEMI_AUTO
    assert cfg.trade_mode == TradeMode.AUTO
    assert cfg.gate_mode == GateMode.FULL
    assert cfg.ai_model_name == "qwen2.5"
    assert cfg.risk_per_trade == 1.0
    assert cfg.max_daily_loss == 500.0
    assert cfg.max_drawdown == 5.0
    assert cfg.max_losing_streak == 3
    assert cfg.max_open_trades == 5
    assert cfg.max_spread == 25
    assert cfg.slippage == 20
    assert cfg.close_friday is True
    assert cfg.trailing_pips == 0
    assert cfg.breakeven_pips == 0
    assert cfg.enable_trailing_stop is False
    assert cfg.news_filter_enabled is True
    assert cfg.news_pause_mins == 30
    assert cfg.news_defense_enabled is True
    assert cfg.defense_window_mins == 15
    assert cfg.news_defense_be_r == 1.5
    assert cfg.allowed_sessions == ("ASIAN", "LONDON", "NY")


def test_bot_run_config_from_dict_null_resilience():
    """Verifies that from_dict gracefully handles None, empty, or corrupted fields without crashing."""
    corrupted_dict = {
        "symbols": None,
        "timeframe": None,
        "strategy_id": None,
        "execution_mode": None,
        "trade_mode": None,
        "gate_mode": None,
        "ai_model_name": None,
        "risk_per_trade": "invalid_num",
        "max_daily_loss": None,
        "max_spread": "fifty",
        "close_friday": "true",
        "allowed_sessions": None,
    }
    cfg = BotRunConfig.from_dict(corrupted_dict)
    assert cfg.symbols == ("XAUUSD",)
    assert cfg.timeframe == mt5.TIMEFRAME_M15
    assert cfg.trade_mode == TradeMode.AUTO
    assert cfg.gate_mode == GateMode.FULL
    assert cfg.execution_mode == ExecutionMode.SEMI_AUTO
    assert cfg.risk_per_trade == 1.0
    assert cfg.max_daily_loss == 500.0
    assert cfg.max_spread == 25
    assert cfg.allowed_sessions == ("ASIAN", "LONDON", "NY")


def test_timeframe_resolver():
    """Verifies resolution between integer minutes, MT5 constants, and human-readable strings."""
    assert resolve_mt5_timeframe(1) == mt5.TIMEFRAME_M1
    assert resolve_mt5_timeframe(5) == mt5.TIMEFRAME_M5
    assert resolve_mt5_timeframe(15) == mt5.TIMEFRAME_M15
    assert resolve_mt5_timeframe(60) == mt5.TIMEFRAME_H1
    assert resolve_mt5_timeframe("H1") == mt5.TIMEFRAME_H1
    assert resolve_mt5_timeframe("M15") == mt5.TIMEFRAME_M15
    assert resolve_mt5_timeframe(None) == mt5.TIMEFRAME_M15

    assert get_timeframe_name(mt5.TIMEFRAME_H1) == "H1"
    assert get_timeframe_name(mt5.TIMEFRAME_M15) == "M15"


def test_enums_parsing():
    """Verifies robust enum string coercion."""
    assert ExecutionMode.from_str("full-auto") == ExecutionMode.FULL_AUTO
    assert ExecutionMode.from_str("manual") == ExecutionMode.MANUAL
    assert ExecutionMode.from_str("semi-auto") == ExecutionMode.SEMI_AUTO
    assert ExecutionMode.from_str(None) == ExecutionMode.SEMI_AUTO

    assert TradeMode.from_str("long_only") == TradeMode.LONG_ONLY
    assert TradeMode.from_str("buy") == TradeMode.LONG_ONLY
    assert TradeMode.from_str("short_only") == TradeMode.SHORT_ONLY
    assert TradeMode.from_str("sell") == TradeMode.SHORT_ONLY
    assert TradeMode.from_str("auto") == TradeMode.AUTO
    assert TradeMode.from_str(None) == TradeMode.AUTO

    assert GateMode.from_str("full") == GateMode.FULL
    assert GateMode.from_str("tech_only") == GateMode.TECH_ONLY
    assert GateMode.from_str("bypass") == GateMode.BYPASS
    assert GateMode.from_str(None) == GateMode.FULL


def test_bot_orchestrator_initialization_with_config():
    """Verifies that BotOrchestrator accepts BotRunConfig directly and unpacks cleanly."""
    cfg = BotRunConfig(
        symbols=("BTCUSD", "ETHUSD"),
        timeframe=mt5.TIMEFRAME_H1,
        strategy_id="builtin_ict_pro",
        trade_mode=TradeMode.LONG_ONLY,
        gate_mode=GateMode.TECH_ONLY,
        execution_mode=ExecutionMode.FULL_AUTO,
        risk_per_trade=2.5,
    )

    orch = BotOrchestrator(
        strategy=MagicMock(),
        risk_manager=MagicMock(),
        execution_manager=MagicMock(),
        data_preprocessor=MagicMock(),
        decision_gate=MagicMock(),
        config=cfg,
    )

    assert orch.config == cfg
    assert orch.symbols == ["BTCUSD", "ETHUSD"]
    assert orch.timeframe == mt5.TIMEFRAME_H1
    assert orch.trade_mode == "LONG_ONLY"
    assert orch.gate_mode == "TECH_ONLY"
    assert orch.execution_mode == "FULL-AUTO"
    assert orch.risk_per_trade == 2.5


def test_bot_orchestrator_legacy_kwargs_backward_compatibility():
    """Verifies that BotOrchestrator without config still creates an internal BotRunConfig seamlessly."""
    orch = BotOrchestrator(
        strategy=MagicMock(),
        risk_manager=MagicMock(),
        execution_manager=MagicMock(),
        data_preprocessor=MagicMock(),
        decision_gate=MagicMock(),
        symbols=["EURUSD"],
        timeframe=mt5.TIMEFRAME_M30,
        strategy_name="EMA_Cross",
        risk_per_trade=1.5,
    )

    assert isinstance(orch.config, BotRunConfig)
    assert orch.symbols == ["EURUSD"]
    assert orch.timeframe == mt5.TIMEFRAME_M30
    assert orch.strategy_name == "EMA_Cross"
    assert orch.risk_per_trade == 1.5
    assert orch.trade_mode == "AUTO"
