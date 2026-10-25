"""
VECTRA V2.2 - Headless Institutional Quant Engine Runner.
Executes algorithmic trading strategies directly via MT5 in headless daemon mode.
Zero GUI dependency, ideal for 24/7 cloud servers (Linux / Windows VPS).
"""

import os
import sys
import json
import time
import signal
import argparse
from pathlib import Path
from typing import Optional

from loguru import logger

# Ensure project root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.infrastructure.brokers.mt5_safe import mt5
from backend.core.engine_config import (
    BotRunConfig,
    ExecutionMode,
    TradeMode,
    GateMode,
    resolve_mt5_timeframe,
    get_timeframe_name,
)
from backend.core.bot_orchestrator import BotOrchestrator, DEFAULT_LOOKBACK_BARS
from backend.core.risk_manager import RiskManager
from backend.infrastructure.brokers.execution_manager import ExecutionManager
from backend.core.preprocessor import DataPreprocessor
from backend.core.strategies.ict_strategy import ICTZonesProStrategy
from backend.infrastructure.ai_engines.ai.decision_gate import DecisionGate
from backend.infrastructure.notifications.telegram_notifier import telegram_notifier

# Configure loguru for headless daemon
log_dir = ROOT_DIR / "logs"
log_dir.mkdir(exist_ok=True)
logger.add(
    log_dir / "headless_bot.log",
    rotation="10 MB",
    retention=7,
    compression="zip",
    enqueue=True,
    encoding="utf-8",
)


def load_config(config_path: Optional[str] = None, cli_args: Optional[argparse.Namespace] = None) -> BotRunConfig:
    """Loads configuration from JSON file or command-line arguments."""
    cfg_data = {}

    # 1. Load from file if specified or if default vps_profile exists
    target_path = None
    if config_path and os.path.exists(config_path):
        target_path = Path(config_path)
    elif (ROOT_DIR / "config" / "vps_profile.json").exists():
        target_path = ROOT_DIR / "config" / "vps_profile.json"
    elif (ROOT_DIR / "config" / "settings.json").exists():
        target_path = ROOT_DIR / "config" / "settings.json"

    if target_path and target_path.exists():
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                cfg_data = json.load(f)
            logger.info(f"[HeadlessRunner] Loaded base configuration from {target_path}")
        except Exception as e:
            logger.warning(f"[HeadlessRunner] Could not parse {target_path}: {e}")

    # 2. Override with explicit CLI arguments
    if cli_args:
        if getattr(cli_args, "symbols", None):
            cfg_data["symbols"] = [s.strip().upper() for s in cli_args.symbols.split(",") if s.strip()]
        if getattr(cli_args, "timeframe", None):
            cfg_data["timeframe"] = cli_args.timeframe
        if getattr(cli_args, "strategy", None):
            cfg_data["strategy_id"] = cli_args.strategy
        if getattr(cli_args, "trade_mode", None):
            cfg_data["trade_mode"] = cli_args.trade_mode
        if getattr(cli_args, "gate_mode", None):
            cfg_data["gate_mode"] = cli_args.gate_mode
        if getattr(cli_args, "risk", None) is not None:
            cfg_data["risk_per_trade"] = cli_args.risk
        if getattr(cli_args, "ai_model", None):
            cfg_data["ai_model_name"] = cli_args.ai_model

    return BotRunConfig.from_dict(cfg_data)


def resolve_strategy(strategy_id: str):
    """Loads strategy instance dynamically by ID or falls back to ICTZonesProStrategy."""
    strat_str = str(strategy_id).lower()
    try:
        from backend.core.strategies.strategy_loader import discover_strategies, load_strategy_instance
        for s in discover_strategies():
            if s["id"] == strategy_id or s["name"].lower() == strat_str:
                instance = load_strategy_instance(s["file_path"], s["class_name"])
                if instance is not None:
                    return instance
    except Exception as e:
        logger.debug(f"[HeadlessRunner] Dynamic strategy loader check: {e}")

    if "ema" in strat_str:
        from backend.core.strategies.ema_stress_test import EMAStressTestStrategy
        return EMAStressTestStrategy(config={"fast_period": 10, "slow_period": 50})
    elif "wyckoff" in strat_str:
        from backend.core.strategies.wyckoff_vectorized import WyckoffMomentumStrategy
        return WyckoffMomentumStrategy()
    else:
        return ICTZonesProStrategy(config={"lookback_bars": DEFAULT_LOOKBACK_BARS})


def build_headless_orchestrator(config: BotRunConfig) -> BotOrchestrator:
    """Initializes all domain managers and wires the Headless BotOrchestrator."""
    strategy = resolve_strategy(config.strategy_id)
    risk_mgr = RiskManager(default_risk_pct=config.risk_per_trade)
    exec_mgr = ExecutionManager(slippage=config.slippage)
    preprocessor = DataPreprocessor()
    decision_gate = DecisionGate()

    orchestrator = BotOrchestrator(
        strategy=strategy,
        risk_manager=risk_mgr,
        execution_manager=exec_mgr,
        data_preprocessor=preprocessor,
        decision_gate=decision_gate,
        config=config,
    )

    # Route Qt signals directly to console / Loguru
    orchestrator.signals.log_msg.connect(
        lambda t, lvl, msg, col: logger.log(
            "INFO" if lvl == "INFO" else ("WARNING" if lvl in ("WARN", "WARNING") else "ERROR"),
            f"[{lvl}] {msg}",
        )
    )
    return orchestrator


def main():
    parser = argparse.ArgumentParser(
        description="VECTRA V2.2 Headless Quant Engine Runner (VPS / Service Daemon)"
    )
    parser.add_argument("--config", "-c", type=str, help="Path to JSON configuration file (e.g. config/vps_profile.json)")
    parser.add_argument("--symbols", "-s", type=str, help="Comma-separated symbols (e.g. XAUUSD,BTCUSD,EURUSD)")
    parser.add_argument("--timeframe", "-tf", type=str, default="15", help="Timeframe (e.g. 15, M15, H1, D1)")
    parser.add_argument("--strategy", type=str, help="Strategy ID (e.g. builtin_ict_pro)")
    parser.add_argument("--trade-mode", "-m", type=str, choices=["AUTO", "LONG_ONLY", "SHORT_ONLY"], help="Trade Directional Mode")
    parser.add_argument("--gate-mode", "-g", type=str, choices=["FULL", "TECH_ONLY", "BYPASS"], help="Decision Gate Mode")
    parser.add_argument("--risk", "-r", type=float, help="Risk percentage per trade (e.g. 1.0)")
    parser.add_argument("--ai-model", type=str, help="AI Model Name (e.g. qwen2.5)")
    args = parser.parse_args()

    print("=" * 70)
    print(" VECTRA V2.2 - Headless Institutional Quant Engine")
    print(" Architecture: MultiAssetDataFeed + MarketSlice + MarketStateStore")
    print(" Mode: Non-GUI Background Service / VPS Daemon")
    print("=" * 70)

    # 1. Verify MT5 Terminal connection
    if not mt5.initialize():
        logger.error("[HeadlessRunner] Failed to initialize MetaTrader 5 API.")
        print("[ERROR] Could not connect to MetaTrader 5 terminal. Ensure MT5 is running.")
        sys.exit(1)

    term_info = mt5.terminal_info()
    acc_info = mt5.account_info()
    if term_info and acc_info:
        logger.info(f"[HeadlessRunner] MT5 Connected: Account #{acc_info.login} on {acc_info.server}")
        print(f"[OK] MT5 Connected: #{acc_info.login} ({acc_info.server})")
    else:
        logger.warning("[HeadlessRunner] MT5 connected but terminal_info is incomplete.")

    # 2. Build immutable configuration
    config = load_config(config_path=args.config, cli_args=args)
    tf_name = get_timeframe_name(config.timeframe)
    print(f"[CONFIG] Watchlist: {', '.join(config.symbols)}")
    print(f"[CONFIG] Timeframe: {tf_name} ({config.timeframe})")
    print(f"[CONFIG] Strategy: {config.strategy_id} | Trade Mode: {config.trade_mode.value}")
    print(f"[CONFIG] Gate Mode: {config.gate_mode.value} | Risk: {config.risk_per_trade}%")
    print("-" * 70)

    # 3. Instantiate orchestrator
    orchestrator = build_headless_orchestrator(config)

    # 4. Graceful shutdown handler
    def handle_shutdown(signum, frame):
        sig_name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
        logger.info(f"[HeadlessRunner] Received signal {sig_name}. Initiating safe shutdown...")
        print(f"\n[SHUTDOWN] Terminating engine loop cleanly ({sig_name})...")
        orchestrator.is_running = False
        telegram_notifier.send_message("⚠️ <b>[VECTRA HEADLESS]</b> Engine shutdown initiated by system signal.")

    signal.signal(signal.SIGINT, handle_shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_shutdown)

    # 5. Start trading pipeline
    telegram_notifier.send_message(
        f"🟢 <b>[VECTRA HEADLESS DAEMON]</b>\n"
        f"Online on VPS/Server.\n"
        f"Symbols: <b>{', '.join(config.symbols)}</b>\n"
        f"Mode: <b>{config.trade_mode.value}</b> | TF: <b>{tf_name}</b>"
    )
    print("[RUNNING] Engine started. Press Ctrl+C to terminate safely.")
    try:
        orchestrator.start_working()
    except Exception as e:
        logger.critical(f"[HeadlessRunner] Uncaught exception in orchestrator loop: {e}")
        import traceback
        logger.critical(traceback.format_exc())
    finally:
        print("[STOPPED] VECTRA Headless Engine shutdown complete.")
        logger.info("[HeadlessRunner] VECTRA Headless Engine shutdown complete.")


if __name__ == "__main__":
    main()
