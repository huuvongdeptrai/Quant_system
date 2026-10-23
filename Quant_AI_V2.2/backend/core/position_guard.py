"""
Position Guard - Autonomous Trailing Stop and Breakeven Protection Service.
Responsible for monitoring active MT5 positions, executing Trailing Stop,
Break-Even shifts, and syncing closed trade outcomes with SQLite and LoRA DatasetRecorder.
"""

from typing import Callable, List, Optional
from loguru import logger

from backend.infrastructure.brokers.mt5_safe import mt5
from backend.infrastructure.notifications.telegram_notifier import telegram_notifier


class PositionGuard:
    """Manages active position stops, trailing offsets, and trade closure persistence.

    Attributes:
        exec_mgr: Execution manager bridge.
        db: SQLite database manager.
        enable_trailing_stop: Master toggle for trailing/breakeven management.
        trailing_pips: Pips offset for trailing stop distance.
        breakeven_pips: Pips profit threshold required before moving SL to BE.
        log_callback: Optional logging callback emitting (level, msg, color).
    """

    def __init__(
        self,
        execution_manager,
        db_manager,
        enable_trailing_stop: bool = False,
        trailing_pips: int = 0,
        breakeven_pips: int = 0,
        log_callback: Optional[Callable[[str, str, str], None]] = None,
    ):
        self.exec_mgr = execution_manager
        self.db = db_manager
        self.enable_trailing_stop = enable_trailing_stop
        self.trailing_pips = trailing_pips
        self.breakeven_pips = breakeven_pips
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

    def manage_positions(self, symbols: List[str]) -> None:
        """Inspects all open positions for trailing stop adjustments and syncs closed trades."""
        if self.enable_trailing_stop and (self.trailing_pips > 0 or self.breakeven_pips > 0):
            for sym in symbols:
                self._apply_trailing_for_symbol(sym)

        self.sync_closed_trades()

    def _apply_trailing_for_symbol(self, sym: str) -> None:
        positions = mt5.positions_get(symbol=sym)
        if not positions:
            return

        info = mt5.symbol_info(sym)
        if not info:
            return

        point = info.point
        offset_be = self.breakeven_pips * point * 10
        offset_tr = self.trailing_pips * point * 10

        for pos in positions:
            is_buy = pos.type == 0
            open_price = pos.price_open
            current_price = pos.price_current
            current_sl = pos.sl
            new_sl = current_sl

            if is_buy:
                profit_distance = current_price - open_price
                if (
                    self.breakeven_pips > 0
                    and current_sl < open_price
                    and profit_distance >= offset_be
                ):
                    new_sl = open_price + (2 * point)

                if self.trailing_pips > 0 and profit_distance > 0:
                    potential_sl = current_price - offset_tr
                    if potential_sl > current_sl and potential_sl > open_price:
                        new_sl = potential_sl
            else:
                profit_distance = open_price - current_price
                if (
                    self.breakeven_pips > 0
                    and (current_sl > open_price or current_sl == 0)
                    and profit_distance >= offset_be
                ):
                    new_sl = open_price - (2 * point)

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
                    self._log(
                        "INFO",
                        f"[Trailing SL] Trailed SL for {sym} to {new_sl:.2f}",
                        "#FF9800",
                    )
                    telegram_notifier.send_message(
                        f"🔄 <b>[TRAILING SL]</b> #{pos.ticket} {sym}: Trailed SL to {new_sl:.2f}",
                        category="sl_tp",
                    )

    def sync_closed_trades(self) -> None:
        """Audits database open trades against live broker positions to record outcomes."""
        try:
            db_open = self.db.get_open_trades()
            if not db_open:
                return

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
                        def _get_val(obj, attr):
                            v = getattr(obj, attr, 0.0)
                            return float(v) if isinstance(v, (int, float)) else 0.0

                        pnl = sum(
                            _get_val(d, "profit")
                            + _get_val(d, "commission")
                            + _get_val(d, "swap")
                            + _get_val(d, "fee")
                            for d in deals
                        )
                        exit_price = float(deals[-1].price or 0.0) if isinstance(getattr(deals[-1], "price", None), (int, float)) else 0.0
                        reason = getattr(deals[-1], "comment", "CLOSED") or "CLOSED"

                    self.db.record_close_trade(ticket=tk, close_price=exit_price, pnl=pnl)

                    try:
                        from backend.infrastructure.ai_engines.dataset_recorder import (
                            dataset_recorder,
                        )
                        dataset_recorder.record_trade_outcome(
                            ticket=tk, pnl=pnl, exit_price=exit_price, reason=reason
                        )
                    except (ImportError, AttributeError, RuntimeError) as err:
                        logger.debug(f"[PositionGuard] Dataset recording skipped for #{tk}: {err}")

                    self._log(
                        "INFO",
                        f"Trade #{tk} closed. PnL: ${pnl:+.2f}. Recorded to LoRA Dataset.",
                        "#3FB950" if pnl > 0 else "#DA3633",
                    )

                    try:
                        sym_c = trade.get("symbol", "")
                        vol_c = float(trade.get("volume", 0.0))
                        open_c = float(trade.get("open_price", 0.0))
                        order_t = trade.get("order_type", "TRADE")
                        deal_comment = str(reason).lower()

                        if "tp" in deal_comment or (pnl > 0 and "sl" not in deal_comment):
                            badge = "🎯 <b>[TAKE PROFIT HIT]</b>"
                        elif "sl" in deal_comment or pnl < 0:
                            badge = "🛑 <b>[STOP LOSS HIT]</b>"
                        else:
                            badge = "🏁 <b>[POSITION CLOSED]</b>"

                        pnl_sign = "+" if pnl >= 0 else "-"
                        telegram_notifier.send_message(
                            f"{badge}\n"
                            f"Ticket: <b>#{tk}</b> | Symbol: <b>{sym_c}</b>\n"
                            f"Action: <b>{order_t}</b> {vol_c:.2f} Lots\n"
                            f"Entry: <b>{open_c}</b> ➔ Exit: <b>{exit_price}</b>\n"
                            f"PnL: <b>{pnl_sign}${abs(pnl):.2f}</b>\n"
                            f"Reason: <i>{reason}</i>",
                            category="sl_tp",
                        )
                    except Exception as e_tg:
                        logger.debug(f"[PositionGuard] Telegram close notification error: {e_tg}")
        except (KeyError, ValueError, RuntimeError) as exc:
            logger.debug(f"[PositionGuard] Trade synchronization non-fatal exception: {exc}")
