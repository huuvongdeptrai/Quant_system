from backend.infrastructure.brokers.mt5_safe import mt5
import pandas as pd
from datetime import datetime, timezone
from loguru import logger


class StatsEngine:
    def __init__(self):
        pass

    def get_account_statistics(self):
        """
        Kéo lịch sử MT5 và tính toán các chỉ số Prop-firm:
        - Tổng số lệnh (Total Trades)
        - Tỷ lệ thắng (Win Rate)
        - Lợi nhuận ròng (Net Profit)
        - Tỷ lệ Risk/Reward (R:R)
        """
        if not mt5.terminal_info():
            return None

        from datetime import timedelta

        # Lấy lịch sử (giới hạn 365 ngày gần nhất để tránh timeout)
        date_from = datetime.now(timezone.utc) - timedelta(days=365)
        date_to = datetime.now(timezone.utc) + timedelta(days=1)

        deals = mt5.history_deals_get(date_from, date_to)

        if deals is None or len(deals) == 0:
            return self._empty_stats()

        # Lọc các deal Đóng Lệnh (Entry Out)
        # Bỏ qua các deal Nạp/Rút tiền (Balance) hoặc Mở lệnh (Entry In)
        live=mt5.positions_get()
        if live is None:
            return None
        active={getattr(p,'identifier',p.ticket) for p in live}
        positions={d.position_id for d in deals if d.entry in (1,3)}-active
        trades=[]
        for pid in positions:
            history=mt5.history_deals_get(position=pid)
            if not history:
                continue
            exits=[d for d in history if d.entry in (1,3)]
            if not exits:
                continue
            last=max(exits,key=lambda d:d.time)
            trades.append(dict(time=last.time,symbol=last.symbol,
                volume=sum(float(d.volume) for d in history if d.entry==0),
                profit=sum(d.profit for d in history),commission=sum(d.commission for d in history),
                swap=sum(d.swap for d in history),
                total_pnl=sum(float(getattr(d,k,0) or 0) for d in history for k in ('profit','commission','swap','fee'))))

        if not trades:
            try:
                import time
                from backend.database.db_manager import DatabaseManager
                db=DatabaseManager()
                account=mt5.account_info()
                if account is None:
                    return self._empty_stats()
                db.bind_account(account.login,account.server)
                db_trades = db.get_closed_trades()
                if db_trades:
                    for dt in db_trades:
                        trades.append({
                            "time": int(time.time()),
                            "symbol": dt.get("symbol", "XAUUSD"),
                            "volume": dt.get("volume", 0.0),
                            "profit": dt.get("pnl", 0.0),
                            "commission": 0.0,
                            "swap": 0.0,
                            "total_pnl": dt.get("pnl", 0.0),
                        })
            except Exception as err:
                logger.debug(f"[StatsEngine] Non-critical error loading db_trades: {err}")

        if not trades:
            return self._empty_stats()

        df = pd.DataFrame(trades)

        # 1. Total Trades
        total_trades = len(df)

        # 2. Win Rate
        winning_trades = df[df["total_pnl"] > 0]
        losing_trades = df[df["total_pnl"] < 0]

        wins_count = len(winning_trades)
        losses_count = len(losing_trades)

        win_rate = (wins_count / total_trades * 100) if total_trades > 0 else 0.0

        # 3. Net Profit
        net_profit = df["total_pnl"].sum()

        # 4. R:R (Risk/Reward)
        avg_win = winning_trades["total_pnl"].mean() if wins_count > 0 else 0.0
        avg_loss = abs(losing_trades["total_pnl"].mean()) if losses_count > 0 else 0.0

        rr_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0
        if avg_loss == 0 and avg_win > 0:
            rr_ratio = 99.9  # Coi như vô cực nếu chưa thua lệnh nào

        return {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "net_profit": net_profit,
            "rr_ratio": rr_ratio,
            "wins": wins_count,
            "losses": losses_count,
            "trades": df.to_dict("records") if total_trades > 0 else [],
        }

    def get_full_history(self):
        """
        Lấy toàn bộ lịch sử giao dịch và ghép nối lệnh (In/Out) theo position_id
        để tính ra Thời lượng và Số Pip.
        """
        if not mt5.terminal_info():
            return []

        from datetime import timedelta

        date_from = datetime.now(timezone.utc) - timedelta(days=365)
        date_to = datetime.now(timezone.utc) + timedelta(days=1)
        deals = mt5.history_deals_get(date_from, date_to)
        if not deals:
            return []

        live=mt5.positions_get()
        if live is None:
            return []
        active={getattr(p,'identifier',p.ticket) for p in live}
        grouped={}
        for d in deals:
            if d.position_id not in active:
                grouped.setdefault(d.position_id,[]).append(d)
        complete=[]
        for pid,group in grouped.items():
            history=mt5.history_deals_get(position=pid)
            if history:
                group=list(history)
            ins=[d for d in group if d.entry==0]
            outs=[d for d in group if d.entry in (1,3)]
            if not ins or not outs:
                continue
            from types import SimpleNamespace
            first=min(ins,key=lambda d:d.time)
            last=max(outs,key=lambda d:d.time)
            entry=SimpleNamespace(**first._asdict()) if hasattr(first,'_asdict') else SimpleNamespace(**vars(first))
            entry.price=sum(d.price*d.volume for d in ins)/sum(d.volume for d in ins)
            exit_data=last._asdict() if hasattr(last,'_asdict') else vars(last)
            out=SimpleNamespace(**exit_data)
            out.profit=sum(float(getattr(d,k,0) or 0) for d in group for k in ('profit','commission','swap','fee'))
            out.commission=out.swap=0.0
            out.volume=sum(d.volume for d in outs)
            out.price=sum(d.price*d.volume for d in outs)/sum(d.volume for d in outs)
            out.entry=1
            complete.extend([entry,out])
        deals=complete
        entries = {}
        trades = []
        for d in deals:
            if d.entry == 0:  # DEAL_ENTRY_IN
                entries[d.position_id] = d
            elif d.entry == 1:  # DEAL_ENTRY_OUT
                entry = entries.get(d.position_id)
                if not entry:
                    is_buy = (d.type == 1)
                    duration_str = "--:--"
                    pips = 0.0
                else:
                    duration = d.time - entry.time
                    is_buy = entry.type == mt5.ORDER_TYPE_BUY

                    # Tính số pip
                    info = mt5.symbol_info(d.symbol)
                    point = info.point if info else 0.0001

                    if is_buy:
                        pips = (d.price - entry.price) / point
                    else:
                        pips = (entry.price - d.price) / point

                    if point in [0.00001, 0.001]:
                        pips = pips / 10

                    hours, remainder = divmod(duration, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    duration_str = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"

                trades.append(
                    {
                        "ticket": d.position_id,  # Dùng position_id làm mã lệnh
                        "type": "Buy" if is_buy else "Sell",
                        "close_time": datetime.fromtimestamp(d.time).strftime(
                            "%d thg %m %Y\n%H:%M:%S"
                        ),
                        "volume": d.volume,
                        "symbol": d.symbol,
                        "pnl": d.profit + d.commission + d.swap,
                        "pips": pips,
                        "duration": duration_str,
                        "timestamp": d.time,  # Dùng để sort
                    }
                )

        # Also include any closed trades persisted in SQLite
        try:
            import time
            from backend.database.db_manager import DatabaseManager
            db=DatabaseManager()
            account=mt5.account_info()
            if account is None:
                return trades
            db.bind_account(account.login,account.server)
            db_trades = db.get_closed_trades()
            if db_trades:
                existing_tickets = {t["ticket"] for t in trades}
                for dt in db_trades:
                    t_num = dt.get("position_id") or dt.get("ticket", 0)
                    if t_num not in existing_tickets:
                        existing_tickets.add(t_num)
                        c_time_str = dt.get("close_time", "")
                        try:
                            ts = int(datetime.fromisoformat(c_time_str).replace(tzinfo=timezone.utc).timestamp()) if c_time_str else int(time.time())
                        except Exception:
                            ts = int(time.time())
                        trades.append({
                            "ticket": t_num,
                            "type": dt.get("order_type", "BUY").capitalize(),
                            "close_time": c_time_str,
                            "volume": dt.get("volume", 0.0),
                            "symbol": dt.get("symbol", "XAUUSD"),
                            "pnl": dt.get("pnl", 0.0),
                            "pips": 0.0,
                            "duration": "--:--",
                            "timestamp": ts,
                        })
        except Exception as err:
            logger.debug(f"[StatsEngine] Non-critical error processing trades: {err}")

        # Sắp xếp mới nhất lên đầu
        trades.sort(key=lambda x: x["timestamp"], reverse=True)
        return trades

    def _empty_stats(self):
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "net_profit": 0.0,
            "rr_ratio": 0.0,
            "wins": 0,
            "losses": 0,
        }
