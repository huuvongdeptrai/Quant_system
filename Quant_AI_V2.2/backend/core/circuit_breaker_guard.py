"""
Circuit Breaker Guard - Autonomous Risk Halt & Account Protection Service.
Monitors daily equity drawdown, dollar-denominated loss limits, and consecutive
losing streaks to automatically freeze trading and prevent capital destruction.
"""

from datetime import datetime, timedelta
from typing import Callable, Optional, Tuple
from loguru import logger

from backend.infrastructure.brokers.mt5_safe import mt5
from backend.infrastructure.notifications.telegram_notifier import telegram_notifier


class CircuitBreakerGuard:
    """Evaluates real-time equity risk and locks bot execution when safety limits breach.

    Attributes:
        db: Database manager for persisting circuit breaker dates and equity snapshots.
        max_daily_loss: Maximum dollar loss permitted in a calendar day.
        max_drawdown: Maximum percentage drawdown allowed from start-of-day equity.
        max_losing_streak: Number of consecutive losing trades before triggering halt.
        log_callback: Optional logging callback emitting (level, msg, color).
    """

    def __init__(
        self,
        db_manager,
        max_daily_loss: float = 500.0,
        max_drawdown: float = 5.0,
        max_losing_streak: int = 3,
        log_callback: Optional[Callable[[str, str, str], None]] = None,
    ):
        self.db = db_manager
        self.max_daily_loss = max_daily_loss
        self.max_drawdown = max_drawdown
        self.max_losing_streak = max_losing_streak
        self.log_callback = log_callback

        self.start_of_day_equity = 0.0
        self.current_losing_streak = 0
        self.circuit_breaker_active = False
        self._circuit_breaker_alert_sent = False
        self.current_date = None

    def _log(self, level: str, msg: str, color: str = "#8B949E") -> None:
        if self.log_callback:
            self.log_callback(level, msg, color)
        else:
            if level == "INFO":
                logger.info(msg)
            elif level == "WARNING":
                logger.warning(msg)
            elif level == "ERROR":
                logger.error(msg)

    def check_losing_streak(self) -> Tuple[bool, int]:
        """Counts consecutive losing deals closed today from MT5 trade history."""
        if self.max_losing_streak <= 0:
            return False, 0

        now = datetime.now()
        t_from = datetime(now.year, now.month, now.day, 0, 0, 0)
        t_to = now + timedelta(hours=2)
        deals = mt5.history_deals_get(t_from, t_to)
        if not deals:
            return False, 0

        exit_deals = [d for d in deals if d.entry == 1]
        if not exit_deals:
            return False, 0

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

    def evaluate_circuit_breaker(self) -> bool:
        """Inspects account equity against daily loss, drawdown, and losing streak rules.

        Returns:
            True if circuit breaker is triggered/active, False if normal execution permitted.
        """
        if self.max_drawdown <= 0 and self.max_daily_loss <= 0 and self.max_losing_streak <= 0:
            return False

        account = mt5.account_info()
        if not account:
            return self.circuit_breaker_active

        today = datetime.now().date()
        today_str = today.strftime("%Y-%m-%d")

        if self.current_date != today:
            self.current_date = today
            saved_date = self.db.get_system_state("start_of_day_date", default="")
            saved_equity = self.db.get_system_state("start_of_day_equity", default="")

            if saved_date == today_str and saved_equity:
                try:
                    self.start_of_day_equity = float(saved_equity)
                except (ValueError, TypeError):
                    self.start_of_day_equity = float(account.equity)
            else:
                self.start_of_day_equity = float(account.equity)
                self.db.set_system_state("start_of_day_date", today_str)
                self.db.set_system_state("start_of_day_equity", str(self.start_of_day_equity))

            cb_date = self.db.get_system_state("circuit_breaker_date", default="")
            cb_active = self.db.get_system_state("circuit_breaker_active", default="False")
            if cb_date == today_str and cb_active == "True":
                self.circuit_breaker_active = True
                self._circuit_breaker_alert_sent = True
            else:
                self.circuit_breaker_active = False
                self._circuit_breaker_alert_sent = False
                self.db.set_system_state("circuit_breaker_active", "False")
            self._log(
                "INFO",
                f"Session starting equity: ${self.start_of_day_equity:,.2f}",
                "#8B949E",
            )

        if self.circuit_breaker_active:
            return True

        # 1. Percent Drawdown Check
        drawdown_pct = 0.0
        if self.start_of_day_equity > 0:
            drawdown_pct = (
                (self.start_of_day_equity - account.equity) / self.start_of_day_equity
            ) * 100

        self.db.record_equity_snapshot(
            float(getattr(account, "balance", 0.0) or 0.0),
            float(getattr(account, "equity", 0.0) or 0.0),
            float(getattr(account, "margin", 0.0) or 0.0),
            float(getattr(account, "margin_free", 0.0) or 0.0),
            float(drawdown_pct),
        )

        if self.max_drawdown > 0 and drawdown_pct >= self.max_drawdown:
            self._trigger_halt(
                f"CIRCUIT BREAKER TRIGGERED: Account drawdown {drawdown_pct:.2f}% exceeded limit {self.max_drawdown}%. Trading halted for today!",
                today_str,
                "DRAWDOWN",
            )
            return True

        # 2. Daily Dollar Loss Check
        daily_loss_dlr = self.start_of_day_equity - account.equity
        if self.max_daily_loss > 0 and daily_loss_dlr >= self.max_daily_loss:
            self._trigger_halt(
                f"CIRCUIT BREAKER TRIGGERED: Daily loss ${daily_loss_dlr:,.2f} exceeded limit ${self.max_daily_loss:,.2f}. Trading halted for today!",
                today_str,
                "DAILY LOSS",
            )
            return True

        # 3. Consecutive Losing Streak Check
        if self.max_losing_streak > 0:
            is_streak_hit, streak_count = self.check_losing_streak()
            if is_streak_hit:
                self._trigger_halt(
                    f"CIRCUIT BREAKER TRIGGERED: Max consecutive loss streak of {streak_count} hit (Limit: {self.max_losing_streak}). Trading halted for today!",
                    today_str,
                    "LOSING STREAK",
                )
                return True

        return False

    def _trigger_halt(self, msg: str, today_str: str, reason: str) -> None:
        self.circuit_breaker_active = True
        self.db.set_system_state("circuit_breaker_active", "True")
        self.db.set_system_state("circuit_breaker_date", today_str)
        self._log("ERROR", msg, "#F23645")

        if not self._circuit_breaker_alert_sent:
            self._circuit_breaker_alert_sent = True
            telegram_notifier.send_message(
                f"🚨 <b>[QUANT AI CIRCUIT BREAKER - {reason}]</b>\n{msg}",
                category="risk_halt",
            )
