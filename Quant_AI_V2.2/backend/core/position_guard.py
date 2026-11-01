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
        bot_magic: Optional[int] = 999999,
        log_callback: Optional[Callable[[str, str, str], None]] = None,
    ):
        self.exec_mgr = execution_manager
        self.db = db_manager
        self.enable_trailing_stop = enable_trailing_stop
        self.trailing_pips = trailing_pips
        self.breakeven_pips = breakeven_pips
        self.bot_magic = bot_magic if bot_magic is not None else getattr(execution_manager, 'magic', 999999)
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
        live=mt5.positions_get()
        if live is not None:
            self._apply_time_barriers(live)
        managed={p.symbol for p in (live or ()) if getattr(p,'magic',None)==self.bot_magic}
        if self.enable_trailing_stop and (self.trailing_pips > 0 or self.breakeven_pips > 0):
            for sym in set(symbols)|managed:
                self._apply_trailing_for_symbol(sym)

        self.sync_closed_trades()

    def _apply_time_barriers(self, positions):
        """Count completed venue bars, not wall-clock hours across market closures.

        Only our persisted automatic execution policy arms a time exit. Legacy,
        manual and unrelated positions do not acquire a new exit rule on restart.
        """
        import json
        account=mt5.account_info()
        if account is None:
            return
        self.db.bind_account(account.login,account.server)
        for pos in positions:
            if getattr(pos,'magic',None)!=self.bot_magic:
                continue
            pid=getattr(pos,'identifier',pos.ticket)
            raw=self.db.get_system_state(f'position_policy:{pid}',default='')
            if not raw:
                continue
            try:
                policy=json.loads(raw)
                limit=int(policy['max_holding_bars'])
                timeframe=int(policy['timeframe'])
                if not 1<=limit<=10000:
                    continue
                rates=mt5.copy_rates_from_pos(pos.symbol,timeframe,0,limit+2)
                if rates is None or len(rates)<2:
                    continue
                times=sorted(int(r['time']) for r in rates)
                opened=int(pos.time)
                if opened>=times[-1]:
                    continue  # No completed holding bar yet.
                containing=max((i for i,t in enumerate(times[:-1]) if t<=opened),default=-1)
                completed=len(times)-1-containing if containing>=0 else len(times)-1
                if completed<limit:
                    continue
                key=f'time_exit:{pid}'
                saved=self.db.get_system_state(key,default='')
                if saved:
                    pending=json.loads(saved)
                    expected=pending.get('remaining')
                    if expected is None or abs(pos.volume-float(expected))>1e-8:
                        continue  # An ambiguous prior close must not be sent twice.
                if not self.db.set_system_state(key,json.dumps({'remaining':None})):
                    continue
                result=self.exec_mgr.close_position(pos.ticket)
                if result.get('status')=='partial':
                    # Broker confirmed a partial execution. A later poll must see
                    # that exact remaining exposure before another close is admitted.
                    self.db.set_system_state(key,json.dumps({'remaining':result['remaining_volume']}))
                elif result.get('status')=='error':
                    self.db.set_system_state(key,'')
                self._log('INFO',f'Time barrier close #{pos.ticket}: {result.get("status")}')
            except (ValueError,TypeError,KeyError) as exc:
                self._log('WARNING',f'Invalid time-exit policy for #{pos.ticket}: {exc}')

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

        # SC-07: Institutional Break-Even Buffer
        # Quote buffer only; commissions/swap and gap slippage can still produce a net loss.
        spread_pts = (float(info.spread) * point) if (hasattr(info, "spread") and isinstance(info.spread, (int, float)) and info.spread > 0) else (10 * point)
        be_buffer = max(spread_pts * 0.5, 5 * point)

        for pos in positions:
            # SC-01: Protect user manual trades & non-bot orders from automated trailing overwrites
            pos_magic = getattr(pos, "magic", 0)
            pos_comment = str(getattr(pos, "comment", "") or "").lower()
            if "manual" in pos_comment:
                continue
            if isinstance(pos_magic, (int, float)) and self.bot_magic is not None and int(pos_magic) != int(self.bot_magic):
                continue

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
                    new_sl = open_price + be_buffer

                if self.trailing_pips > 0 and profit_distance > 0:
                    potential_sl = current_price - offset_tr
                    if potential_sl > current_sl and potential_sl > open_price:
                        new_sl = max(new_sl, potential_sl)
            else:
                profit_distance = open_price - current_price
                if (
                    self.breakeven_pips > 0
                    and (current_sl > open_price or current_sl == 0)
                    and profit_distance >= offset_be
                ):
                    new_sl = open_price - be_buffer

                if self.trailing_pips > 0 and profit_distance > 0:
                    potential_sl = current_price + offset_tr
                    if potential_sl < current_sl or current_sl == 0:
                        if potential_sl < open_price:
                            new_sl = min(new_sl, potential_sl) if new_sl > 0 else potential_sl

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
            account=mt5.account_info()
            if account is None:
                return
            self.db.bind_account(account.login,account.server)
            db_open = self.db.get_open_trades()
            if not db_open:
                return

            live_positions = mt5.positions_get()
            if live_positions is None:
                # API connection drop - abort sync to protect open trades
                return

            live_ids = {getattr(p,"identifier",p.ticket) for p in live_positions}

            for trade in db_open:
                tk = trade["ticket"]
                if (trade.get("position_id") or tk) not in live_ids:
                    deals = mt5.history_deals_get(position=trade.get("position_id") or tk)
                    if not deals:
                        # Missing deals: do not overwrite with 0.0 / 0.0
                        continue

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
                    out_deals = [d for d in deals if getattr(d, "entry", 0) in (1, 3)]
                    if not out_deals:
                        continue
                    self.db.record_deals(deals)
                    exit_deal = max(out_deals, key=lambda x: getattr(x, "time_msc", getattr(x, "time", 0))) if out_deals else deals[-1]
                    exit_price = float(getattr(exit_deal, "price", 0.0) or 0.0)
                    reason = getattr(exit_deal, "comment", "CLOSED") or "CLOSED"

                    from datetime import datetime, timezone
                    closed_at=datetime.fromtimestamp(exit_deal.time,timezone.utc).isoformat()
                    if not self.db.record_close_trade(ticket=tk, close_price=exit_price, pnl=pnl,close_time=closed_at):
                        continue

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
        except (KeyError, ValueError, RuntimeError, OSError) as exc:
            logger.debug(f"[PositionGuard] Trade synchronization non-fatal exception: {exc}")
