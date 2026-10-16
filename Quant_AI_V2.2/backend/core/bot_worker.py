import time
from datetime import datetime, timedelta, timezone
from backend.infrastructure.brokers.mt5_safe import mt5
from PySide6 import QtCore
from loguru import logger
import os
from pathlib import Path

# Cấu hình loguru (Rule 4 & Clean Paths)
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

import pandas as pd
from backend.infrastructure.notifications.telegram_notifier import telegram_notifier
from backend.database.db_manager import DatabaseManager
from backend.core.state_recovery import StateRecoveryManager
from backend.core.event_risk_engine import EventRiskEngine

DEFAULT_LOOKBACK_BARS = 300


class WorkerSignals(QtCore.QObject):
    log_msg = QtCore.Signal(str, str, str, str)


class BotWorker(QtCore.QObject):
    def __init__(
        self,
        strategy,
        risk_manager,
        execution_manager,
        data_preprocessor,
        decision_gate,
        symbols: list[str] = ["XAUUSD"],
        timeframe: int = mt5.TIMEFRAME_M15,
        strategy_name: str = "ICT",
        ai_model_name: str = "qwen2.5",
        gate_mode: str = "FULL",
        news_filter_enabled: bool = True,
        news_pause_mins: int = 30,
        slippage: int = 20,
        risk_per_trade: float = 1.0,
        max_drawdown: float = 5.0,
        max_losing_streak: int = 3,
        trailing_pips: int = 15,
        breakeven_pips: int = 10,
        allowed_sessions: list[str] = None,
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
        self.max_drawdown = max_drawdown
        self.max_losing_streak = max_losing_streak
        self.trailing_pips = trailing_pips
        self.breakeven_pips = breakeven_pips

        self.allowed_sessions = (
            allowed_sessions
            if allowed_sessions is not None
            else ["ASIAN", "LONDON", "NY"]
        )

        self.start_of_day_equity = 0.0
        self.current_losing_streak = 0
        self.circuit_breaker_active = False

        # ==================================================
        # THIẾT LẬP HƯỚNG GIAO DỊCH (Có thể nối ra UI để tuỳ chỉnh)
        # Các tuỳ chọn: "AUTO", "LONG_ONLY", "SHORT_ONLY"
        # ==================================================
        self.trade_mode = "AUTO"

        # Dependency Injection (Rule 6)
        self.risk_mgr = risk_manager
        self.exec_mgr = execution_manager
        self.prep = data_preprocessor
        self.ict = strategy
        self.gate = decision_gate
        self.db = DatabaseManager()
        self.state_recovery = StateRecoveryManager(self.db)
        self.event_risk = EventRiskEngine(
            execution_manager=self.exec_mgr,
            defense_window_mins=15,
            pause_window_mins=self.news_pause_mins,
        )

        # Khởi tạo sớm AI Engine nếu dùng chiến lược AI để tránh giật lag lúc khớp lệnh
        self.ai_engine = None
        self.ai_engine = None
        if self.strategy_name == "AI":
            from backend.infrastructure.ai_engines.ai.analysis_engine import AnalysisEngine

            self.ai_engine = AnalysisEngine(model_name=self.ai_model_name)

    def log(self, level: str, msg: str, color: str):
        t = datetime.now().strftime("%H:%M:%S")
        if level == "INFO":
            logger.info(msg)
        elif level == "WARNING":
            logger.warning(msg)
        elif level == "ERROR":
            logger.error(msg)
        self.signals.log_msg.emit(t, level, msg, color)

    def start_working(self):
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
        telegram_notifier.send_message(
            f"🟢 <b>[Quant AI V2.2]</b> Automated execution started for {', '.join(self.symbols)}.\nMode: <b>{self.trade_mode}</b>\nStrategy: <b>{self.strategy_name}</b>"
        )
        if not mt5.terminal_info():
            return

        while self.is_running:
            # 1. Quản lý rủi ro & Cầu dao bảo vệ tài khoản (Circuit Breaker)
            self._manage_circuit_breaker()
            if getattr(self, "circuit_breaker_active", False):
                time.sleep(5)
                continue

            # 2. Quản lý vị thế mở (Tự động Trailing Stop & dời hòa vốn Breakeven)
            self._manage_positions()

            # 3. Kích hoạt chế độ phòng thủ vị thế trước giờ tin (T-15 phút)
            if self.news_filter_enabled and hasattr(self, "event_risk"):
                defense_actions = self.event_risk.evaluate_pre_news_defense()
                for act in defense_actions:
                    self.log(
                        "INFO",
                        f"[DEFENSE] #{act['ticket']} {act['symbol']} | {act['action']} (+{act['r_multiple']}R) before '{act['news']}'",
                        "#38BDF8",
                    )

            for sym in self.symbols:
                if not self.is_running:
                    break
                self.pipeline_execute(sym)

            # Đợi 10s nhưng chia nhỏ để có thể dừng ngay lập tức khi logout
            for _ in range(100):
                if not self.is_running:
                    break
                time.sleep(0.1)

    def _check_session_allowed(self) -> tuple[bool, str]:
        """
        Kiểm tra phiên giao dịch hiện tại (ASIAN, LONDON, NY) có thuộc danh sách cho phép không.
        """
        if not self.allowed_sessions:
            return True, "ALL"

        now_utc = datetime.utcnow().hour
        if 7 <= now_utc < 13:
            current_session = "LONDON"
        elif 13 <= now_utc < 22:
            current_session = "NY"
        else:
            current_session = "ASIAN"

        allowed = [s.upper() for s in self.allowed_sessions]
        if current_session in allowed:
            return True, current_session
        return False, current_session

    def _check_news_impact(self, symbol: str = None) -> tuple[bool, str]:
        """
        Kiểm tra xem hiện tại có đang nằm trong khoảng ±news_pause_mins của tin tức đỏ hay không.
        Nếu truyền symbol, kiểm tra chính xác theo mã tài sản bị ảnh hưởng (Multi-Asset Mapping).
        """
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

        return False, ""

    def _check_losing_streak(self) -> tuple[bool, int]:
        """
        Đếm chuỗi lệnh thua liên tiếp trong ngày hôm nay từ lịch sử MT5.
        """
        if self.max_losing_streak <= 0:
            return False, 0

        now = datetime.now()
        t_from = datetime(now.year, now.month, now.day, 0, 0, 0)
        t_to = now + timedelta(hours=2)
        deals = mt5.history_deals_get(t_from, t_to)
        if not deals:
            return False, 0

        # Lọc các deal chốt lệnh (DEAL_ENTRY_OUT == 1)
        exit_deals = [d for d in deals if d.entry == 1]
        if not exit_deals:
            return False, 0

        # Sắp xếp mới nhất trước
        exit_deals.sort(key=lambda x: x.time, reverse=True)
        streak = 0
        for d in exit_deals:
            total_pnl = d.profit + d.commission + d.swap
            if total_pnl < 0:
                streak += 1
            elif total_pnl > 0:
                break

        self.current_losing_streak = streak
        if streak >= self.max_losing_streak:
            return True, streak
        return False, streak

    def pipeline_execute(self, sym: str):
        if not self.state_recovery.can_open_new_trade(sym):
            return
        if getattr(self, "circuit_breaker_active", False):
            return

        # 1. Bộ lọc Phiên giao dịch (Session Filter)
        session_allowed, current_sess = self._check_session_allowed()
        if not session_allowed:
            return

        # 2. Bộ lọc Tin tức Kinh tế Mạnh & Cảm biến Giãn Spread Đa tài sản
        if self.news_filter_enabled:
            news_blocked, news_title = self.event_risk.check_news_impact_for_symbol(sym)
            if news_blocked:
                self.log(
                    "WARNING",
                    f"TRADING HALTED [{sym}]: High-impact news '{news_title}' within ±{self.news_pause_mins}m window!",
                    "#FF9800",
                )
                return

            spread_ok, curr_spread, max_spread = self.event_risk.check_spread_normalization(sym)
            if not spread_ok:
                self.log(
                    "WARNING",
                    f"SPREAD EXPANDED [{sym}]: Current spread {curr_spread} > Max safe {max_spread}. Waiting for liquidity...",
                    "#F59E0B",
                )
                return

        rates = mt5.copy_rates_from_pos(sym, self.timeframe, 0, 500)
        if rates is None or len(rates) == 0:
            return
        refined = self.prep.process_technical_data(rates)
        if not refined:
            return

        positions = mt5.positions_get(symbol=sym)
        if positions:
            return  # Đang có lệnh -> Không làm gì cả

        # --------------------------------------------------
        # LỚP 1: CHIẾN LƯỢC ICT ZONES PRO (V1)
        # --------------------------------------------------
        # TUỲ CHỌN CHIẾN LƯỢC GIAO DỊCH
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

        elif self.strategy_name == "SMC":
            self.log(
                "INFO",
                f"Simulating SMC Liquidity on {sym} (Feature coming soon)...",
                "#8B949E",
            )
            time.sleep(30)
            return

        elif self.strategy_name == "AI":
            if not self.ai_engine:
                from backend.infrastructure.ai_engines.ai.analysis_engine import AnalysisEngine

                self.ai_engine = AnalysisEngine(model_name=self.ai_model_name)

            # Log đã được di chuyển vào trong AnalysisEngine để tránh spam
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

            # Tính SL/TP cơ bản theo Support/Resistance 500 nến
            rates_df = pd.DataFrame(rates)
            current = rates_df["close"].iloc[-1]
            sup = rates_df["low"].min()
            res = rates_df["high"].max()
            sl_price, tp_price = self._calculate_sl_tp(signal, current, sup, res)
            entry_price = current
            confidence_str = "Confidence: Local AI"

        else:
            return

        # --------------------------------------------------
        # LỚP 2: MA TRẬN QUYẾT ĐỊNH (Vĩ mô + Vị trí giá + HTF)
        # --------------------------------------------------
        gate_result = self.gate.evaluate(
            sym, signal, timeframe=self.timeframe, gate_mode=self.gate_mode
        )
        if gate_result["decision"] == "WAIT":
            self.log(
                "INFO", f"[Gate] {signal} {sym}: {gate_result['reason']}", "#8B949E"
            )
            return
        signal = gate_result["decision"]  # Gate co the thay doi huong

        # --------------------------------------------------
        # LỚP 3: TÍNH TOÁN RỦI RO (RISK LAYER)
        # --------------------------------------------------
        sl_points = abs(entry_price - sl_price)
        if sl_points <= 0:
            sl_points = entry_price * 0.005  # Fallback

        lot = self.risk_mgr.calculate_lot_size(sym, sl_points, risk_pct=1.0)

        self.log(
            "TRADE",
            f"[{self.strategy_name}] Approved {signal} {sym}. {confidence_str}. Vol: {lot} Lots. SL: {sl_price:.2f}",
            "#D2A8FF",
        )

        # --------------------------------------------------
        # LỚP 4: BẮN LỆNH LÊN MT5 (EXECUTION LAYER)
        # --------------------------------------------------
        res = self.exec_mgr.execute_market_order(
            sym, signal == "BUY", lot, sl_price, tp_price, comment=f"Quant_{signal}"
        )
        if res["status"] == "success":
            self.log("SUCCESS", res["msg"], "#3FB950")
            ticket = res.get("ticket", 0)
            if ticket:
                self.db.record_open_trade(
                    ticket=ticket,
                    symbol=sym,
                    order_type=signal,
                    volume=lot,
                    open_price=entry_price,
                    sl=sl_price,
                    tp=tp_price,
                    comment=f"Quant_{signal}",
                )
                # Link to LoRA DatasetRecorder
                if self.strategy_name == "AI" and "ai_res" in locals():
                    sample_id = ai_res.get("_sample_id")
                    if sample_id:
                        try:
                            from backend.infrastructure.ai_engines.dataset_recorder import dataset_recorder
                            dataset_recorder.link_trade_execution(
                                sample_id=sample_id,
                                ticket=ticket,
                                entry_price=entry_price,
                                sl=sl_price,
                                tp=tp_price,
                                direction=signal,
                                lot=lot,
                            )
                        except Exception:
                            pass
            telegram_notifier.send_message(
                f"🚀 <b>ORDER FILLED: {signal} {sym}</b>\nVolume: {lot} Lots\nSL: {sl_price:.2f} | TP: {tp_price:.2f}\nReason: {confidence_str}"
            )
        else:
            self.log("ERROR", res["msg"], "#DA3633")

    def _manage_circuit_breaker(self):
        # Tùy chỉnh: Nếu Max Drawdown = 0 -> Vô hiệu hóa
        if self.max_drawdown <= 0:
            return

        account = mt5.account_info()
        if not account:
            return

        today = datetime.now().date()
        if not hasattr(self, "current_date") or self.current_date != today:
            self.current_date = today
            self.start_of_day_equity = account.equity
            self.circuit_breaker_active = False
            self.log(
                "INFO",
                f"New trading session. Starting Equity: ${self.start_of_day_equity:,.2f}",
                "#8B949E",
            )

        if self.circuit_breaker_active:
            return

        drawdown_pct = (
            (self.start_of_day_equity - account.equity) / self.start_of_day_equity
        ) * 100
        self.db.record_equity_snapshot(
            account.balance,
            account.equity,
            account.margin,
            account.margin_free,
            drawdown_pct,
        )
        if drawdown_pct >= self.max_drawdown:
            self.circuit_breaker_active = True
            msg = f"CIRCUIT BREAKER TRIGGERED: Account drawdown {drawdown_pct:.2f}% exceeded limit {self.max_drawdown}%. Trading halted for today!"
            self.log("ERROR", msg, "#F23645")
            telegram_notifier.send_message(
                f"🚨 <b>[QUANT AI CIRCUIT BREAKER]</b>\n{msg}"
            )
            return

        # Kiểm tra Cầu dao Chuỗi Thua Liên Tiếp (Losing Streak)
        if self.max_losing_streak > 0:
            is_streak_hit, streak_count = self._check_losing_streak()
            if is_streak_hit:
                self.circuit_breaker_active = True
                msg = f"CIRCUIT BREAKER TRIGGERED: Max consecutive loss streak of {streak_count} hit (Limit: {self.max_losing_streak}). Trading halted for today!"
                self.log("ERROR", msg, "#F23645")
                telegram_notifier.send_message(
                    f"🚨 <b>[QUANT AI CIRCUIT BREAKER - LOSING STREAK]</b>\n{msg}"
                )

    def _manage_positions(self):
        # Tùy chỉnh: Nếu Trailing hoặc Breakeven = 0 -> Vô hiệu hóa tính năng đó
        if self.trailing_pips <= 0 and self.breakeven_pips <= 0:
            return

        for sym in self.symbols:
            positions = mt5.positions_get(symbol=sym)
            if not positions:
                continue

            info = mt5.symbol_info(sym)
            if not info:
                continue

            point = info.point

            for pos in positions:
                is_buy = pos.type == 0
                open_price = pos.price_open
                current_price = pos.price_current
                current_sl = pos.sl

                # 1 Pip = 10 Points
                offset_be = self.breakeven_pips * point * 10
                offset_tr = self.trailing_pips * point * 10

                new_sl = current_sl

                if is_buy:
                    profit_distance = current_price - open_price
                    # Breakeven
                    if (
                        self.breakeven_pips > 0
                        and current_sl < open_price
                        and profit_distance >= offset_be
                    ):
                        new_sl = open_price + (2 * point)

                    # Trailing
                    if self.trailing_pips > 0 and profit_distance > 0:
                        potential_sl = current_price - offset_tr
                        if potential_sl > current_sl and potential_sl > open_price:
                            new_sl = potential_sl
                else:
                    profit_distance = open_price - current_price
                    # Breakeven
                    if (
                        self.breakeven_pips > 0
                        and (current_sl > open_price or current_sl == 0)
                        and profit_distance >= offset_be
                    ):
                        new_sl = open_price - (2 * point)

                    # Trailing
                    if self.trailing_pips > 0 and profit_distance > 0:
                        potential_sl = current_price + offset_tr
                        if potential_sl < current_sl or current_sl == 0:
                            if potential_sl < open_price:
                                new_sl = potential_sl

                if new_sl != current_sl and abs(new_sl - current_sl) > point * 5:
                    request = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": pos.ticket,
                        "sl": new_sl,
                        "tp": pos.tp,
                    }
                    res = mt5.order_send(request)
                    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                        self.log(
                            "INFO",
                            f"[Auto SL] Trailed SL for {sym} to {new_sl:.2f} (Break Even)",
                            "#FF9800",
                        )

        # Cập nhật kết quả giao dịch đã đóng vào CSDL và LoRA DatasetRecorder
        try:
            db_open = self.db.get_open_trades()
            if db_open:
                live_positions = mt5.positions_get()
                live_tickets = {p.ticket for p in live_positions} if live_positions else set()
                for trade in db_open:
                    tk = trade["ticket"]
                    if tk not in live_tickets:
                        deals = mt5.history_deals_get(position=tk)
                        pnl = 0.0
                        exit_price = 0.0
                        reason = "CLOSED"
                        if deals:
                            pnl = sum(d.profit for d in deals)
                            exit_price = deals[-1].price
                            reason = getattr(deals[-1], "comment", "CLOSED") or "CLOSED"
                        self.db.record_close_trade(ticket=tk, close_price=exit_price, pnl=pnl)
                        from backend.infrastructure.ai_engines.dataset_recorder import dataset_recorder
                        dataset_recorder.record_trade_outcome(ticket=tk, pnl=pnl, exit_price=exit_price, reason=reason)
                        self.log(
                            "INFO",
                            f"Trade #{tk} closed. PnL: ${pnl:+.2f}. Recorded to LoRA Dataset.",
                            "#3FB950" if pnl > 0 else "#DA3633",
                        )
        except Exception:
            pass

    def _strategy_logic(self, refined: dict) -> tuple[str, float, float, float]:
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

    def _validate_direction(self, signal: str) -> bool:
        """Trạm gác: Kiểm tra tín hiệu có thuận với Chế độ hay không"""
        if self.trade_mode == "AUTO":
            return True
        if self.trade_mode == "LONG_ONLY" and signal == "BUY":
            return True
        if self.trade_mode == "SHORT_ONLY" and signal == "SELL":
            return True
        return False

    def _calculate_sl_tp(
        self, signal: str, current: float, support: float, resistance: float
    ) -> tuple[float, float]:
        if signal == "BUY":
            sl_dist = current - support
            if sl_dist <= 0:
                sl_dist = current * 0.005
            sl_price = current - sl_dist
            tp_price = current + (sl_dist * 2)
        else:
            sl_dist = resistance - current
            if sl_dist <= 0:
                sl_dist = current * 0.005
            sl_price = current + sl_dist
            tp_price = current - (sl_dist * 2)
        return sl_price, tp_price

    def stop(self):
        self.is_running = False
        self.log("INFO", "Safe bot shutdown routine initiated...", "#8B949E")
        telegram_notifier.send_message(
            "🔴 <b>[Quant AI V2.2]</b> Bot stopped."
        )
