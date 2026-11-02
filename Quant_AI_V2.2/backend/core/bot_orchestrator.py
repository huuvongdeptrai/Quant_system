"""
Bot Orchestrator - Main Trading Pipeline Execution and Event Coordination Loop.
Coordinates quantitative strategy execution, decision gates, risk guards,
session compliance, and automated state recovery in an asynchronous QThread loop.
"""

import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import pandas as pd
from loguru import logger
from PySide6 import QtCore

from backend.infrastructure.brokers.mt5_safe import mt5
from backend.infrastructure.notifications.telegram_notifier import telegram_notifier
from backend.database.db_manager import DatabaseManager
from backend.core.state_recovery import StateRecoveryManager
from backend.core.event_risk_engine import EventRiskEngine
from backend.core.position_guard import PositionGuard
from backend.core.circuit_breaker_guard import CircuitBreakerGuard
from backend.core.session_filter import SessionFilter
from backend.core.trade_dispatcher import TradeDispatcher
from backend.core.engine_config import (
    BotRunConfig,
    ExecutionMode,
    TradeMode,
    GateMode,
    resolve_mt5_timeframe,
    get_timeframe_name,
)
from backend.infrastructure.data_providers.multi_asset_data_feed import (
    MultiAssetDataFeed,
    MarketSlice,
)

try:
    log_dir = Path(__file__).resolve().parents[2] / "logs"
    log_dir.mkdir(exist_ok=True)
    if os.environ.get("QUANT_TESTING") != "1":
        logger.add(
            log_dir / "bot_worker.log",
            rotation="5 MB",
            compression="zip",
            retention=5,
            enqueue=False,
            encoding="utf-8",
        )
except Exception:
    pass

DEFAULT_LOOKBACK_BARS = 300


class WorkerSignals(QtCore.QObject):
    """Qt Signal container for streaming real-time worker logs to the GUI."""
    log_msg = QtCore.Signal(str, str, str, str)


class BotOrchestrator(QtCore.QObject):
    """Central orchestrator managing multi-asset algorithmic execution and safety guards."""

    def __init__(
        self,
        strategy,
        risk_manager,
        execution_manager,
        data_preprocessor,
        decision_gate,
        config: Optional[BotRunConfig] = None,
        symbols: Optional[List[str]] = None,
        timeframe: Optional[int] = None,
        strategy_name: Optional[str] = None,
        ai_model_name: Optional[str] = None,
        gate_mode: Optional[str] = None,
        news_filter_enabled: Optional[bool] = None,
        news_pause_mins: Optional[int] = None,
        slippage: Optional[int] = None,
        risk_per_trade: Optional[float] = None,
        max_daily_loss: Optional[float] = None,
        max_drawdown: Optional[float] = None,
        max_losing_streak: Optional[int] = None,
        max_open_trades: Optional[int] = None,
        max_spread: Optional[int] = None,
        close_friday: Optional[bool] = None,
        trailing_pips: Optional[int] = None,
        breakeven_pips: Optional[int] = None,
        enable_trailing_stop: Optional[bool] = None,
        news_defense_enabled: Optional[bool] = None,
        defense_window_mins: Optional[int] = None,
        news_defense_be_r: Optional[float] = None,
        allowed_sessions: Optional[List[str]] = None,
        trade_mode: Optional[str] = None,
        **kwargs,
    ):
        super().__init__()
        self.is_running = True
        self.signals = WorkerSignals()

        # Enterprise Pillar 1: Validated Immutable BotRunConfig
        if config is not None:
            self.config = config
        else:
            cfg_dict = {
                "symbols": symbols if symbols is not None else ["XAUUSD"],
                "timeframe": timeframe if timeframe is not None else mt5.TIMEFRAME_M15,
                "strategy_id": strategy_name if strategy_name is not None else "Wyckoff",
                "ai_model_name": ai_model_name if ai_model_name is not None else "qwen2.5",
                "gate_mode": gate_mode if gate_mode is not None else "FULL",
                "news_filter_enabled": news_filter_enabled if news_filter_enabled is not None else True,
                "news_pause_mins": news_pause_mins if news_pause_mins is not None else 30,
                "slippage": slippage if slippage is not None else 20,
                "risk_per_trade": risk_per_trade if risk_per_trade is not None else 1.0,
                "max_daily_loss": max_daily_loss if max_daily_loss is not None else 500.0,
                "max_drawdown": max_drawdown if max_drawdown is not None else 5.0,
                "max_losing_streak": max_losing_streak if max_losing_streak is not None else 3,
                "max_open_trades": max_open_trades if max_open_trades is not None else 5,
                "max_spread": max_spread if max_spread is not None else 25,
                "close_friday": close_friday if close_friday is not None else True,
                "trailing_pips": trailing_pips if trailing_pips is not None else 0,
                "breakeven_pips": breakeven_pips if breakeven_pips is not None else 0,
                "enable_trailing_stop": enable_trailing_stop if enable_trailing_stop is not None else False,
                "news_defense_enabled": news_defense_enabled if news_defense_enabled is not None else True,
                "defense_window_mins": defense_window_mins if defense_window_mins is not None else 15,
                "news_defense_be_r": news_defense_be_r if news_defense_be_r is not None else 1.5,
                "allowed_sessions": allowed_sessions if allowed_sessions is not None else ["ASIAN", "LONDON", "NY"],
                "trade_mode": trade_mode if trade_mode is not None else "AUTO",
            }
            self.config = BotRunConfig.from_dict(cfg_dict)

        # Unpack from immutable config schema to preserve 100% backward compatibility
        self.symbols = list(self.config.symbols)
        self.timeframe = self.config.timeframe
        self.strategy_name = self.config.strategy_id
        self.gate_mode = self.config.gate_mode.value
        self.trade_mode = self.config.trade_mode.value
        self.ai_model_name = self.config.ai_model_name
        self.execution_mode = self.config.execution_mode.value

        self.news_filter_enabled = self.config.news_filter_enabled
        self.news_pause_mins = self.config.news_pause_mins
        self.slippage = self.config.slippage
        self.risk_per_trade = self.config.risk_per_trade
        self.max_daily_loss = self.config.max_daily_loss
        self.max_drawdown = self.config.max_drawdown
        self.max_losing_streak = self.config.max_losing_streak
        self.max_open_trades = self.config.max_open_trades
        self.max_spread = self.config.max_spread
        self.close_friday = self.config.close_friday
        self.trailing_pips = self.config.trailing_pips
        self.breakeven_pips = self.config.breakeven_pips
        self.enable_trailing_stop = self.config.enable_trailing_stop
        self.news_defense_enabled = self.config.news_defense_enabled
        self.defense_window_mins = self.config.defense_window_mins
        self.news_defense_be_r = self.config.news_defense_be_r
        self.allowed_sessions = list(self.config.allowed_sessions)

        # Dependencies
        self.risk_mgr = risk_manager
        self.exec_mgr = execution_manager
        self.prep = data_preprocessor
        self.data_feed = MultiAssetDataFeed(max_workers=8, default_lookback=DEFAULT_LOOKBACK_BARS)
        self.ict = strategy
        self.gate = decision_gate
        self.db = DatabaseManager()
        self.state_recovery = StateRecoveryManager(self.db)

        # Specialized Single-Responsibility Guards
        self.circuit_guard = CircuitBreakerGuard(
            db_manager=self.db,
            max_daily_loss=self.max_daily_loss,
            max_drawdown=self.max_drawdown,
            max_losing_streak=self.max_losing_streak,
            bot_magic=getattr(self.exec_mgr, "magic", 999999),
            log_callback=self.log,
        )

        self.position_guard = PositionGuard(
            execution_manager=self.exec_mgr,
            db_manager=self.db,
            enable_trailing_stop=self.enable_trailing_stop,
            trailing_pips=self.trailing_pips,
            breakeven_pips=self.breakeven_pips,
            bot_magic=getattr(self.exec_mgr, "magic", 999999),
            log_callback=self.log,
        )

        self.session_filter = SessionFilter(
            allowed_sessions=self.allowed_sessions,
            close_friday=self.close_friday,
            log_callback=self.log,
        )

        self.trade_dispatcher = TradeDispatcher(
            execution_manager=self.exec_mgr,
            risk_manager=self.risk_mgr,
            db_manager=self.db,
            log_callback=self.log,
        )

        self.event_risk = EventRiskEngine(
            execution_manager=self.exec_mgr,
            defense_window_mins=self.defense_window_mins,
            pause_window_mins=self.news_pause_mins,
            news_defense_enabled=self.news_defense_enabled,
            be_r_threshold=self.news_defense_be_r,
            user_max_spread=self.max_spread,
        )

        self.ai_engine = None
        self._wake_event = threading.Event()
        self._last_spread_warning_ts = {}
        self._last_reconcile = 0.0
        from backend.core.trading_commands import TradingCommandService
        TradingCommandService.register_runtime(self)
        if self.strategy_name == "AI":
            from backend.infrastructure.ai_engines.ai.analysis_engine import AnalysisEngine

            self.ai_engine = AnalysisEngine(model_name=self.ai_model_name)

    def wake_up(self) -> None:
        """Immediately wakes up the background polling cycle without waiting for sleep interval."""
        if hasattr(self, "_wake_event"):
            self._wake_event.set()

    @property
    def circuit_breaker_active(self) -> bool:
        return self.circuit_guard.circuit_breaker_active

    @circuit_breaker_active.setter
    def circuit_breaker_active(self, value: bool) -> None:
        self.circuit_guard.circuit_breaker_active = value

    @property
    def _circuit_breaker_alert_sent(self) -> bool:
        return self.circuit_guard._circuit_breaker_alert_sent

    @_circuit_breaker_alert_sent.setter
    def _circuit_breaker_alert_sent(self, value: bool) -> None:
        self.circuit_guard._circuit_breaker_alert_sent = value

    @property
    def start_of_day_equity(self) -> float:
        return self.circuit_guard.start_of_day_equity

    @start_of_day_equity.setter
    def start_of_day_equity(self, value: float) -> None:
        self.circuit_guard.start_of_day_equity = value

    @property
    def current_losing_streak(self) -> int:
        return self.circuit_guard.current_losing_streak

    @current_losing_streak.setter
    def current_losing_streak(self, value: int) -> None:
        self.circuit_guard.current_losing_streak = value

    def log(self, level: str, msg: str, color: str = "#8B949E") -> None:
        """Emits formatted log message to GUI and persists into loguru."""
        t = datetime.now().strftime("%H:%M:%S")
        if level == "INFO":
            logger.info(msg)
        elif level == "WARNING":
            logger.warning(msg)
        elif level == "ERROR":
            logger.error(msg)
        self.signals.log_msg.emit(t, level, msg, color)

    def start_working(self) -> None:
        """Primary worker thread entry point executed in background."""
        self.log(
            "INFO",
            f"Starting Bot Pipeline (Allowed Mode: {self.trade_mode})...",
            "#3FB950",
        )
        rec_summary = self.state_recovery.reconcile_on_startup()
        self.log(
            "INFO",
            f"[State Recovery] DB Audit: {rec_summary.get('active_positions_count', 0)} MT5 positions, recovered {rec_summary.get('recovered_orphans', 0)} orphaned orders.",
            "#58A6FF",
        )
        today_str = datetime.now().strftime("%Y-%m-%d")
        cb_date = self.db.get_system_state("circuit_breaker_date", default="")
        if cb_date == today_str and rec_summary.get("circuit_breaker_active", False):
            self.circuit_guard.circuit_breaker_active = True
            self.circuit_guard._circuit_breaker_alert_sent = True
            self.log(
                "WARNING",
                f"[Circuit Breaker] Trạng thái cầu dao bảo vệ vốn hôm nay ({today_str}) đang KÍCH HOẠT. Tạm ngưng giao dịch.",
                "#F23645",
            )
        syms_display = ", ".join(self.symbols) if self.symbols else "Standby (0 symbols in watchlist)"
        telegram_notifier.send_message(
            f"🟢 <b>[VECTRA V2.2]</b> Automated execution started for {syms_display}.\nMode: <b>{self.trade_mode}</b>\nStrategy: <b>{self.strategy_name}</b>"
        )
        if not mt5.terminal_info():
            return

        while self.is_running:
            if time.monotonic()-self._last_reconcile>=15:
                self.state_recovery.reconcile_on_startup()
                self._last_reconcile=time.monotonic()
            # 1. Circuit Breaker Protection
            self._manage_circuit_breaker()
            cb_active = self.circuit_guard.circuit_breaker_active
            if self.close_friday:
                self._manage_friday_eod()

            # 2. Position Guard (Trailing Stop & BE) - SC-03: Always maintain active in-trade defense
            self._manage_positions()

            # 3. Pre-News Active Defense (T-15 min) - SC-03: Always protect open positions
            if self.news_filter_enabled and getattr(self, "news_defense_enabled", True) and hasattr(self, "event_risk"):
                defense_actions = self.event_risk.evaluate_pre_news_defense()
                for act in defense_actions:
                    self.log(
                        "INFO",
                        f"[DEFENSE] #{act['ticket']} {act['symbol']} | {act['action']} (+{act['r_multiple']}R) before '{act['news']}'",
                        "#38BDF8",
                    )
                    telegram_notifier.send_message(
                        f"🛡️ <b>[PRE-NEWS DEFENSE]</b>\n#{act['ticket']} {act['symbol']}: {act['action']} (+{act['r_multiple']}R) before '{act['news']}'",
                        category="sl_tp",
                    )

            # SC-03: If Circuit Breaker is active, freeze NEW order evaluations only, while continuing position defense above
            if cb_active:
                poll_cycles = getattr(self, "poll_cycles", 15)
                for _ in range(poll_cycles):
                    if not self.is_running:
                        break
                    time.sleep(0.1)
                continue

            # 4. Friday EOD Liquidation Shield
            if getattr(self, "close_friday", True):
                self._manage_friday_eod()

            # 5. Dynamic Watchlist Refresh & Multi-Asset Execution
            active_symbols = list(self.symbols)
            if hasattr(self, "symbols_provider") and callable(self.symbols_provider):
                try:
                    dyn_syms = self.symbols_provider()
                    if dyn_syms:
                        active_symbols = dyn_syms
                        self.symbols = dyn_syms
                except Exception as e_sym:
                    logger.debug(f"[BotOrchestrator] Dynamic symbols refresh: {e_sym}")

            # Enterprise Pillar 2: Synchronized Multi-Asset Market Slice Ingestion
            slice_data = self.data_feed.pull_slice(active_symbols, self.timeframe, count=DEFAULT_LOOKBACK_BARS)

            for sym in active_symbols:
                if not self.is_running:
                    break
                self.pipeline_execute(sym, market_slice=slice_data)

            # Responsive event-driven polling sleep (reduced from 10s to 1.5s, wakeable immediately)
            poll_cycles = getattr(self, "poll_cycles", 15)  # 15 * 0.1s = 1.5s max
            for _ in range(poll_cycles):
                if not self.is_running:
                    break
                if hasattr(self, "_wake_event") and self._wake_event.is_set():
                    self._wake_event.clear()
                    break
                time.sleep(0.1)

    # -------------------------------------------------------------
    # Delegated Guard Methods (Preserving 100% Backwards Compatibility)
    # -------------------------------------------------------------
    def _manage_circuit_breaker(self) -> None:
        self.circuit_guard.max_daily_loss = self.max_daily_loss
        self.circuit_guard.max_drawdown = self.max_drawdown
        self.circuit_guard.max_losing_streak = self.max_losing_streak
        self.circuit_guard.evaluate_circuit_breaker()

    def _manage_positions(self) -> None:
        self.position_guard.enable_trailing_stop = self.enable_trailing_stop
        self.position_guard.trailing_pips = self.trailing_pips
        self.position_guard.breakeven_pips = self.breakeven_pips
        self.position_guard.manage_positions(self.symbols)

    def _manage_friday_eod(self) -> None:
        self.session_filter.close_friday = self.close_friday
        self.session_filter.manage_friday_eod(self.symbols, self.exec_mgr)

    def _check_session_allowed(self, symbol: Optional[str] = None) -> tuple[bool, str]:
        self.session_filter.allowed_sessions = self.allowed_sessions
        self.session_filter.close_friday = self.close_friday
        return self.session_filter.is_session_allowed(symbol=symbol)

    def _check_losing_streak(self) -> tuple[bool, int]:
        self.circuit_guard.max_losing_streak = self.max_losing_streak
        return self.circuit_guard.check_losing_streak()

    def _check_news_impact(self, symbol: Optional[str] = None) -> tuple[bool, str]:
        if not self.news_filter_enabled or self.news_pause_mins <= 0:
            return False, ""
        if hasattr(self, "event_risk"):
            if symbol:
                return self.event_risk.check_news_impact_for_symbol(symbol)
            self.event_risk.refresh_events_if_needed()
            events = self.event_risk._news_events_cache
            now_ts = datetime.now(timezone.utc).timestamp()
            window_sec = self.news_pause_mins * 60
            for e in events:
                if e.get("impact", 0) >= 2:
                    event_ts = e.get("sort_key", 0)
                    if abs(now_ts - event_ts) <= window_sec:
                        return True, f"{e.get('title', '')} ({e.get('country', '')})"
        return False, ""

    def _strategy_logic(self, refined: dict) -> tuple[str, float, float, float]:
        """Legacy helper: evaluates basic channel signal and boundaries from refined indicators."""
        current = refined["current_price"]
        trend = refined["trend"]
        sup = refined["support"]
        res = refined["resistance"]
        range_h = res - sup
        sig = "WAIT"

        if range_h > 0:
            if "TĂNG" in trend and (current - sup) < range_h * 0.2:
                sig = "BUY"
            elif "GIẢM" in trend and (res - current) < range_h * 0.2:
                sig = "SELL"
        return sig, sup, res, current

    def _calculate_sl_tp(
        self, signal: str, current: float, support: float, resistance: float
    ) -> tuple[float, float]:
        return self.trade_dispatcher.calculate_sl_tp(signal, current, support, resistance)

    def _validate_direction(self, signal: str) -> bool:
        return self.trade_dispatcher.validate_direction(signal, self.trade_mode)

    def pipeline_execute(self, sym: str, market_slice: Optional[MarketSlice] = None) -> None:
        """Executes full strategy pipeline for a single watchlist asset using synchronized MarketSlice."""
        if not self.is_running or self.execution_mode != ExecutionMode.FULL_AUTO.value:
            return
        account = mt5.account_info()
        if account is None:
            return
        self.db.bind_account(account.login, account.server)
        if not self.state_recovery.can_open_new_trade(sym):
            return
        if self.circuit_guard.circuit_breaker_active:
            return

        # 1. Session Filter (Asset-Aware)
        session_allowed, _ = self._check_session_allowed(sym)
        if not session_allowed:
            return

        # 2. News Risk & Spread Sensor
        if self.news_filter_enabled:
            news_blocked, news_title = self.event_risk.check_news_impact_for_symbol(sym)
            if news_blocked:
                self.log(
                    "WARNING",
                    f"TRADING HALTED [{sym}]: High-impact news '{news_title}' within ±{self.news_pause_mins}m window!",
                    "#FF9800",
                )
                return

            spread_ok, curr_spread, max_s = self.event_risk.check_spread_normalization(sym)
            if not spread_ok:
                now_mono = time.monotonic()
                last_warn = getattr(self, "_last_spread_warning_ts", {}).get(sym, 0.0)
                if now_mono - last_warn >= 60.0:
                    if not hasattr(self, "_last_spread_warning_ts"):
                        self._last_spread_warning_ts = {}
                    self._last_spread_warning_ts[sym] = now_mono
                    self.log(
                        "WARNING",
                        f"SPREAD EXPANDED [{sym}]: Current spread {curr_spread} > Max safe {max_s}. Waiting for liquidity...",
                        "#F59E0B",
                    )
                return
            else:
                if hasattr(self, "_last_spread_warning_ts") and sym in self._last_spread_warning_ts:
                    self._last_spread_warning_ts.pop(sym, None)

        # 3. Capacity & Position Gating
        clean_target = sym.split(".")[0].replace("/", "").upper()
        all_positions = mt5.positions_get()
        if all_positions:
            # 3a. Per-asset isolation: Single position per distinct symbol (Gold never blocks BTC)
            if any(getattr(p, "symbol", "").split(".")[0].replace("/", "").upper() == clean_target for p in all_positions):
                return

            # 3b. Portfolio capacity: Max concurrent open trades across universe
            max_open = int(getattr(self, "max_open_trades", 5) or 5)
            if len(all_positions) >= max_open:
                return

        # Synchronized Market Slice Rates Extraction (Pillar 2)
        rates = None
        if market_slice is not None and market_slice.has_symbol(sym):
            rates = market_slice.get_rates(sym)

        if rates is None or len(rates) == 0:
            try:
                mt5.symbol_select(sym, True)
            except Exception:
                pass
            rates = mt5.copy_rates_from_pos(sym, self.timeframe, 1, 500)

        if rates is None or len(rates) == 0:
            return
        refined = self.prep.process_technical_data(rates)
        if not refined:
            return

        # 4. Strategy Evaluation (Polymorphic Quantitative Execution)
        sample_id = None
        current = float(rates[-1]["close"])

        if self.strategy_name == "AI":
            if not self.ai_engine:
                from backend.infrastructure.ai_engines.ai.analysis_engine import AnalysisEngine

                self.ai_engine = AnalysisEngine(model_name=self.ai_model_name)

            ai_res = self.ai_engine.analyze(sym)
            if "error" in ai_res:
                self.log("ERROR", f"AI Error: {ai_res['error']}", "#DA3633")
                return

            trend = ai_res.get("trend_intraday", "").upper()
            if "TĂNG" in trend or "UP" in trend:
                signal = "BUY"
            elif "GIẢM" in trend or "DOWN" in trend:
                signal = "SELL"
            else:
                signal = "WAIT"

            if signal in ["HOLD", "WAIT"]:
                self.log(
                    "INFO",
                    f"AI advises stand aside: {ai_res.get('scenario_a', '')[:50]}...",
                    "#8B949E",
                )
                return

            rates_df = pd.DataFrame(rates)
            sup = float(rates_df["low"].min())
            res = float(rates_df["high"].max())
            sl_price, tp_price = self._calculate_sl_tp(signal, current, sup, res)
            entry_price = current
            confidence_str = "Confidence: Local AI"
            sample_id = ai_res.get("_sample_id")

        elif hasattr(self.ict, "analyze"):
            df = pd.DataFrame(rates)
            df["time"] = pd.to_datetime(df["time"], unit="s")

            try:
                from backend.core.macro_context_bus import MacroContextBus
                bus = MacroContextBus.get_instance()
                macro_ctx = bus.get_macro_context(sym)
            except Exception:
                macro_ctx = {}

            try:
                strat_res = self.ict.analyze(df, macro_context=macro_ctx)
            except TypeError:
                strat_res = self.ict.analyze(df)

            signal = strat_res.get("signal", "HOLD")
            if signal in ["HOLD", "WAIT"]:
                return

            entry_price = float(strat_res.get("entry_price") or current)
            sl_price = float(strat_res.get("sl") or 0.0)
            tp_price = float(strat_res.get("tp1") or strat_res.get("tp") or 0.0)

            if sl_price <= 0 or tp_price <= 0:
                sup = float(df["low"].tail(50).min())
                res_lvl = float(df["high"].tail(50).max())
                calc_sl, calc_tp = self._calculate_sl_tp(signal, entry_price, sup, res_lvl)
                if sl_price <= 0:
                    sl_price = calc_sl
                if tp_price <= 0:
                    tp_price = calc_tp

            conf_val = strat_res.get("confidence", 0.85)
            confidence_str = f"Confidence: {conf_val*100:.1f}%"

        else:
            return

        # Directional Permissibility
        if not self._validate_direction(signal):
            return

        # TradingCommandService owns the final gate and risk scaling for all entry paths.
        strat_id = getattr(self.ict,"strategy_id",None) or self.config.strategy_id
        effective_risk_pct = self.risk_per_trade

        # Order Dispatching via TradeDispatcher
        self.trade_dispatcher.dispatch_market_order(
            symbol=sym,
            signal=signal,
            entry_price=entry_price,
            sl_price=sl_price,
            tp_price=tp_price,
            risk_pct=effective_risk_pct,
            strategy_name=strat_id,
            confidence_str=confidence_str,
            sample_id=sample_id,
            signal_key=f"{strat_id}:{sym}:{self.timeframe}:{int(rates[-1]['time'])}:{signal}",
        )

    def stop(self) -> None:
        """Gracefully halts worker thread loop and sends notification."""
        from backend.core.trading_commands import TradingCommandService
        with TradingCommandService._lock:
            self.is_running = False
        self.wake_up()
        self.log("INFO", "Safe bot shutdown routine initiated...", "#8B949E")
        try:
            telegram_notifier.send_message(
                "🔴 <b>[VECTRA V2.2]</b> Bot stopped."
            )
        except Exception as e:
            logger.debug(f"[BotOrchestrator] Stop notification: {e}")
