"""
Circuit Breaker Guard - Autonomous Risk Halt & Account Protection Service.
Monitors daily equity drawdown, dollar-denominated loss limits, and consecutive
losing streaks to automatically freeze trading and prevent capital destruction.
"""

from datetime import datetime, timedelta, timezone
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
        bot_magic: Optional[int] = 999999,
        log_callback: Optional[Callable[[str, str, str], None]] = None,
    ):
        self.db = db_manager
        self.max_daily_loss = max_daily_loss
        self.max_drawdown = max_drawdown
        self.max_losing_streak = max_losing_streak
        self.bot_magic = bot_magic
        self.log_callback = log_callback

        self.start_of_day_equity = 0.0
        self.current_losing_streak = 0
        self.circuit_breaker_active = False
        self._circuit_breaker_alert_sent = False
        self.current_date = None
        self._account_identity = None

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
        self.history_available = True
        if self.max_losing_streak <= 0:
            return False, 0

        now = datetime.now(timezone.utc)
        t_from = datetime(now.year, now.month, now.day, 0, 0, 0,tzinfo=timezone.utc)
        t_to = now + timedelta(hours=2)
        deals = mt5.history_deals_get(t_from, t_to)
        if deals is None:
            self.history_available = False
            return False, 0
        if not deals:
            return False, 0

        exit_deals = [d for d in deals if d.entry == 1]
        # Ownership is determined from entry deals, never from the user/broker closing action.
        if not exit_deals:
            return False, 0

        positions=mt5.positions_get()
        if positions is None:
            self.history_available = False
            return False,0
        active={getattr(p,'identifier',p.ticket) for p in positions}
        grouped={}
        for d in exit_deals:
            pid=d.position_id
            if pid not in active:
                grouped[pid]=max(grouped.get(pid,0),d.time)
        streak=0
        for pid,_ in sorted(grouped.items(),key=lambda x:x[1],reverse=True):
            history=mt5.history_deals_get(position=pid)
            if not history:
                self.history_available = False
                break
            opening=[d for d in history if d.entry in (0,2)]
            if self.bot_magic is not None and not any(getattr(d,'magic',0)==self.bot_magic for d in opening):
                continue
            total_pnl=sum(float(getattr(d,k,0) or 0) for d in history for k in ('profit','commission','swap','fee'))
            if total_pnl<0:
                streak+=1
            elif total_pnl>0:
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
            return True

        self.db.bind_account(account.login, account.server)
        today = datetime.now(timezone.utc).date()
        today_str = today.strftime("%Y-%m-%d")
        acct_login = str(getattr(account, "login", "") or "")
        identity = (account.server, account.login)
        if self._account_identity != identity:
            # Database scope alone cannot reset a long-lived guard's cached equity/halt.
            self._account_identity = identity
            self.start_of_day_equity = 0.0
            self.current_date = None
            self.current_losing_streak = 0
            self.circuit_breaker_active = False
            self._circuit_breaker_alert_sent = False

        saved_date = self.db.get_system_state("start_of_day_date", default="")
        saved_equity = self.db.get_system_state("start_of_day_equity", default="")
        saved_acct = self.db.get_system_state("start_of_day_account", default="")

        # Account switch or new trading day requires fresh baseline anchoring
        is_account_changed = bool(saved_acct and acct_login and saved_acct != acct_login)
        is_new_day = (self.current_date != today or saved_date != today_str)

        if is_new_day or is_account_changed or self.start_of_day_equity <= 0:
            self.current_date = today

            if not is_account_changed and saved_date == today_str and saved_equity:
                try:
                    self.start_of_day_equity = float(saved_equity)
                except (ValueError, TypeError):
                    self.start_of_day_equity = float(account.equity)
            else:
                self.start_of_day_equity = float(account.equity)
                self.db.set_system_state("start_of_day_date", today_str)
                self.db.set_system_state("start_of_day_equity", str(self.start_of_day_equity))
                if acct_login:
                    self.db.set_system_state("start_of_day_account", acct_login)

            cb_date = self.db.get_system_state("circuit_breaker_date", default="")
            cb_active = self.db.get_system_state("circuit_breaker_active", default="False")
            if not is_account_changed and cb_date == today_str and cb_active == "True":
                self.circuit_breaker_active = True
                self._circuit_breaker_alert_sent = True
            else:
                self.circuit_breaker_active = False
                self._circuit_breaker_alert_sent = False
                self.db.set_system_state("circuit_breaker_active", "False")

            acct_tag = f" (#{acct_login})" if acct_login else ""
            self._log(
                "INFO",
                f"Session starting equity{acct_tag}: ${self.start_of_day_equity:,.2f}",
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
            if not self.history_available:
                self._log("WARNING", "Entry paused: broker history is unavailable")
                return True
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
                f"🚨 <b>[VECTRA CIRCUIT BREAKER - {reason}]</b>\n{msg}",
                category="risk_halt",
            )
