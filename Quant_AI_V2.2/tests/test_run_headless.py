"""
Unit tests for run_headless.py - Headless configuration loading and orchestrator instantiation.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from run_headless import load_config, resolve_strategy, build_headless_orchestrator
from backend.core.engine_config import BotRunConfig, ExecutionMode, TradeMode, GateMode


def test_load_config_defaults():
    cfg = load_config()
    assert isinstance(cfg, BotRunConfig)
    assert len(cfg.symbols) >= 1
    assert cfg.trade_mode in (TradeMode.AUTO, TradeMode.LONG_ONLY, TradeMode.SHORT_ONLY)


def test_load_config_from_custom_json(tmp_path):
    custom_cfg = {
        "symbols": ["EURUSD", "GBPUSD"],
        "timeframe": 60,
        "strategy_id": "ict_pro",
        "trade_mode": "LONG_ONLY",
        "gate_mode": "TECH_ONLY",
        "risk_per_trade": 1.5,
    }
    cfg_file = tmp_path / "custom_vps.json"
    with open(cfg_file, "w", encoding="utf-8") as f:
        json.dump(custom_cfg, f)

    cfg = load_config(config_path=str(cfg_file))
    assert cfg.symbols == ("EURUSD", "GBPUSD")
    from backend.infrastructure.brokers.mt5_safe import mt5
    assert cfg.timeframe == mt5.TIMEFRAME_H1
    assert cfg.trade_mode == TradeMode.LONG_ONLY
    assert cfg.gate_mode == GateMode.TECH_ONLY
    assert cfg.risk_per_trade == 1.5


def test_load_config_cli_overrides():
    cli_mock = MagicMock()
    cli_mock.symbols = "BTCUSD,ETHUSD"
    cli_mock.timeframe = "15"
    cli_mock.strategy = "builtin_ict_pro"
    cli_mock.trade_mode = "SHORT_ONLY"
    cli_mock.gate_mode = "BYPASS"
    cli_mock.risk = 2.0
    cli_mock.ai_model = "deepseek"

    cfg = load_config(cli_args=cli_mock)
    assert cfg.symbols == ("BTCUSD", "ETHUSD")
    assert cfg.trade_mode == TradeMode.SHORT_ONLY
    assert cfg.gate_mode == GateMode.BYPASS
    assert cfg.risk_per_trade == 2.0
    assert cfg.ai_model_name == "deepseek"


def test_resolve_strategy():
    strat_ict = resolve_strategy("builtin_ict_pro")
    assert strat_ict is not None

    strat_ema = resolve_strategy("ema_stress_test")
    assert strat_ema is not None


def test_build_headless_orchestrator():
    cfg = BotRunConfig(symbols=("XAUUSD",), timeframe=15, risk_per_trade=1.0)
    orchestrator = build_headless_orchestrator(cfg)
    assert orchestrator is not None
    assert orchestrator.config == cfg
    assert orchestrator.symbols == ["XAUUSD"]
    assert orchestrator.is_running is True
