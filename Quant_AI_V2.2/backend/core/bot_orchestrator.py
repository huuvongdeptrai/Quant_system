"""
Bot Orchestrator - Main Trading Pipeline Execution and Event Coordination Loop.
Coordinates quantitative strategy execution, decision gates, risk guards,
session compliance, and automated state recovery in an asynchronous QThread loop.
"""

import time
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

log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
logger.add(
    log_dir / "bot_worker.log",
    rotation="5 MB",
    compression="zip",
    retention=5,
    enqueue=True,
    encoding="utf-8",
)

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
        symbols: List[str] = ["XAUUSD"],
        timeframe: int = mt5.TIMEFRAME_M15,
        strategy_name: str = "ICT",
        ai_model_name: str = "qwen2.5",
        gate_mode: str = "FULL",
        news_filter_enabled: bool = True,
        news_pause_mins: int = 30,
        slippage: int = 20,
        risk_per_trade: float = 1.0,
        max_daily_loss: float = 500.0,
        max_drawdown: float = 5.0,
        max_losing_streak: int = 3,
        max_open_trades: int = 3,
        max_spread: int = 25,
        close_friday: bool = True,
        trailing_pips: int = 0,
        breakeven_pips: int = 0,
        enable_trailing_stop: bool = False,
        news_defense_enabled: bool = True,
        defense_window_mins: int = 15,
        news_defense_be_r: float = 1.5,
        allowed_sessions: Optional[List[str]] = None,
    ):
        super().__init__()
        self.is_running = True
        self.symbols = symbols
        self.timeframe = timeframe
        self.strategy_name = strategy_name
        self.gate_mode = gate_mode
        self.ai_model_name = ai_model_name
        self.signals = WorkerSignals()

        self.news_filter_enabled = news_filter_enabled
        self.news_pause_mins = news_pause_mins
        self.slippage = slippage
        self.risk_per_trade = risk_per_trade
        self.max_daily_loss = max_daily_loss
        self.max_drawdown = max_drawdown
        self.max_losing_streak = max_losing_streak
        self.max_open_trades = max_open_trades
        self.max_spread = max_spread
        self.close_friday = close_friday
        self.trailing_pips = trailing_pips
        self.breakeven_pips = breakeven_pips
        self.enable_trailing_stop = enable_trailing_stop
        self.news_defense_enabled = news_defense_enabled
        self.defense_window_mins = defense_window_mins
        self.news_defense_be_r = news_defense_be_r
        self.allowed_sessions = (
            allowed_sessions
            if allowed_sessions is not None
            else ["ASIAN", "LONDON", "NY"]
        )

        self.trade_mode = "AUTO"

        # Dependencies
        self.risk_mgr = risk_manager
        self.exec_mgr = execution_manager
        self.prep = data_preprocessor
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
            log_callback=self.log,
        )

        self.position_guard = PositionGuard(
            execution_manager=self.exec_mgr,
            db_manager=self.db,
            enable_trailing_stop=self.enable_trailing_stop,
            trailing_pips=self.trailing_pips,
            breakeven_pips=self.breakeven_pips,
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
        if self.strategy_name == "AI":
            from backend.infrastructure.ai_engines.ai.analysis_engine import AnalysisEngine

            self.ai_engine = AnalysisEngine(model_name=self.ai_model_name)

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
            f"🟢 <b>[Quant AI V2.2]</b> Automated execution started for {syms_display}.\nMode: <b>{self.trade_mode}</b>\nStrategy: <b>{self.strategy_name}</b>"
        )
        if not mt5.terminal_info():
            return

        while self.is_running:
            # 1. Circuit Breaker Protection
            self._manage_circuit_breaker()
            if self.circuit_guard.circuit_breaker_active:
                time.sleep(5)
                continue

            # 2. Position Guard (Trailing Stop & BE)
            self._manage_positions()

            # 3. Pre-News Active Defense (T-15 min)
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

            # 4. Friday EOD Liquidation Shield
            if getattr(self, "close_friday", True):
                self._manage_friday_eod()

            # 5. Cycle Watchlist Symbols
            for sym in self.symbols:
                if not self.is_running:
                    break
                self.pipeline_execute(sym)

            # Responsive polling sleep
            for _ in range(100):
                if not self.is_running:
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

    def _check_session_allowed(self) -> tuple[bool, str]:
        self.session_filter.allowed_sessions = self.allowed_sessions
        self.session_filter.close_friday = self.close_friday
        return self.session_filter.is_session_allowed()

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

    def pipeline_execute(self, sym: str) -> None:
        """Executes full strategy pipeline for a single watchlist asset."""
        if not self.state_recovery.can_open_new_trade(sym):
            return
        if self.circuit_guard.circuit_breaker_active:
            return

        # 1. Session Filter
        session_allowed, _ = self._check_session_allowed()
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
                self.log(
                    "WARNING",
                    f"SPREAD EXPANDED [{sym}]: Current spread {curr_spread} > Max safe {max_s}. Waiting for liquidity...",
                    "#F59E0B",
                )
                return

        # 3. Capacity & Position Gating
        if getattr(self, "max_open_trades", 0) > 0:
            all_positions = mt5.positions_get()
            if all_positions and len(all_positions) >= self.max_open_trades:
                return

        positions = mt5.positions_get(symbol=sym)
        if positions:
            return

        rates = mt5.copy_rates_from_pos(sym, self.timeframe, 0, 500)
        if rates is None or len(rates) == 0:
            return
        refined = self.prep.process_technical_data(rates)
        if not refined:
            return

        # Strategy Evaluation
        sample_id = None
        if self.strategy_name == "ICT":
            df = pd.DataFrame(rates)
            df["time"] = pd.to_datetime(df["time"], unit="s")
            ict_res = self.ict.analyze(df, macro_context={})
            signal = ict_res.get("signal", "HOLD")
            if signal in ["HOLD", "WAIT"]:
                return
            sl_price = ict_res["sl"]
            tp_price = ict_res["tp1"]
            entry_price = ict_res["entry_price"]
            confidence_str = f"Confidence: {ict_res['confidence']*100:.1f}%"

        elif self.strategy_name == "AI":
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
            current = rates_df["close"].iloc[-1]
            sup = rates_df["low"].min()
            res = rates_df["high"].max()
            sl_price, tp_price = self._calculate_sl_tp(signal, current, sup, res)
            entry_price = current
            confidence_str = "Confidence: Local AI"
            sample_id = ai_res.get("_sample_id")

        else:
            return

        # Directional Permissibility
        if not self._validate_direction(signal):
            return

        # Decision Gate Evaluation
        gate_result = self.gate.evaluate(
            sym, signal, timeframe=self.timeframe, gate_mode=self.gate_mode
        )
        if gate_result["decision"] == "WAIT":
            self.log(
                "INFO", f"[Gate] {signal} {sym}: {gate_result['reason']}", "#8B949E"
            )
            return
        signal = gate_result["decision"]

        # Order Dispatching via TradeDispatcher
        self.trade_dispatcher.dispatch_market_order(
            symbol=sym,
            signal=signal,
            entry_price=entry_price,
            sl_price=sl_price,
            tp_price=tp_price,
            risk_pct=self.risk_per_trade,
            strategy_name=self.strategy_name,
            confidence_str=confidence_str,
            sample_id=sample_id,
        )

    def stop(self) -> None:
        """Gracefully halts worker thread loop and sends notification."""
        self.is_running = False
        self.log("INFO", "Safe bot shutdown routine initiated...", "#8B949E")
        telegram_notifier.send_message(
            "🔴 <b>[Quant AI V2.2]</b> Bot stopped."
        )
