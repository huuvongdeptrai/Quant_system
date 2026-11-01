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

    def is_session_allowed(self, symbol: Optional[str] = None) -> Tuple[bool, str]:
        """Determines if current UTC time falls within an authorized trading session.
        Crypto assets operate 24/7 and are unconditionally exempt from Forex session windows.

        Returns:
            Tuple[bool, str]: (is_allowed, session_name_or_block_reason)
        """
        if symbol:
            try:
                from backend.infrastructure.data_providers.asset_registry import AssetRegistry, AssetClass
                if AssetRegistry.identify(symbol) == AssetClass.CRYPTO:
                    return True, "CRYPTO_24_7"
            except Exception:
                pass

        now = datetime.now(timezone.utc)
        if self.close_friday and now.weekday() == 4 and now.hour >= 21:
            return False, "FRIDAY_EOD"

        # Weekend closure for non-crypto assets (Forex/Metals/Indices closed Saturday & Sunday until Sydney open 22:00 UTC)
        if now.weekday() == 5 or (now.weekday() == 6 and now.hour < 22):
            return False, "WEEKEND_CLOSED"

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
        Exempts Crypto assets since cryptocurrency markets trade continuously 24/7.

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
            all_positions=mt5.positions_get()
            managed={p.symbol for p in (all_positions or ()) if getattr(p,'magic',None)==execution_manager.magic}
            for sym in set(symbols)|managed:
                try:
                    from backend.infrastructure.data_providers.asset_registry import AssetRegistry, AssetClass
                    if AssetRegistry.identify(sym) == AssetClass.CRYPTO:
                        continue
                except Exception:
                    pass
                positions = mt5.positions_get(symbol=sym)
                if positions:
                    for pos in positions:
                        if pos.magic != execution_manager.magic or 'manual' in str(pos.comment).lower():
                            continue
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
