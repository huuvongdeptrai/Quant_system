"""
Session Filter - Market Hours & Weekend Risk Defense Service.
Validates trading session timeframes (Asia, London, New York) and protects
capital against unpredictable weekend gap risk by enforcing Friday EOD liquidation.
"""

from datetime import datetime, timezone
from typing import Callable, List, Optional, Tuple
from loguru import logger

from backend.infrastructure.brokers.mt5_safe import mt5
from backend.infrastructure.notifications.telegram_notifier import telegram_notifier


class SessionFilter:
    """Controls session entry authorization and enforces Friday end-of-day liquidation.

    Attributes:
        allowed_sessions: List of allowed session strings (e.g. ['ASIAN', 'LONDON', 'NY']).
        close_friday: When True, prevents new entries and flattens positions Friday >= 21:00 UTC.
        log_callback: Optional logging callback emitting (level, msg, color).
    """

    def __init__(
        self,
        allowed_sessions: Optional[List[str]] = None,
        close_friday: bool = True,
        log_callback: Optional[Callable[[str, str, str], None]] = None,
    ):
        self.allowed_sessions = (
            allowed_sessions
            if allowed_sessions is not None
            else ["ASIAN", "LONDON", "NY"]
        )
        self.close_friday = close_friday
        self.log_callback = log_callback

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

    def is_session_allowed(self) -> Tuple[bool, str]:
        """Determines if current UTC time falls within an authorized trading session.

        Returns:
            Tuple[bool, str]: (is_allowed, session_name_or_block_reason)
        """
        now = datetime.now(timezone.utc)
        if self.close_friday and now.weekday() == 4 and now.hour >= 21:
            return False, "FRIDAY_EOD"

        if not self.allowed_sessions:
            return True, "ALL"

        now_utc = now.hour
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

    def manage_friday_eod(self, symbols: List[str], execution_manager) -> List[int]:
        """Liquidates open positions on Friday EOD (>= 21:00 UTC) to hedge weekend gap risk.

        Args:
            symbols: List of traded symbols to audit and close.
            execution_manager: Broker adapter for order closure.

        Returns:
            List of closed ticket numbers.
        """
        if not self.close_friday:
            return []

        now = datetime.now(timezone.utc)
        closed_tickets = []
        if now.weekday() == 4 and now.hour >= 21:
            for sym in symbols:
                positions = mt5.positions_get(symbol=sym)
                if positions:
                    for pos in positions:
                        res = execution_manager.close_position(pos.ticket)
                        if res.get("status") == "success":
                            closed_tickets.append(pos.ticket)
                            self._log(
                                "WARNING",
                                f"[FRIDAY EOD] Closed #{pos.ticket} {sym} to protect against weekend gap risk.",
                                "#EAB308",
                            )
                            telegram_notifier.send_message(
                                f"⚠️ <b>[WEEKEND RISK DEFENSE]</b>\nClosed #{pos.ticket} {sym} at Friday EOD (UTC {now.strftime('%H:%M')}).",
                                category="risk_halt",
                            )
        return closed_tickets
