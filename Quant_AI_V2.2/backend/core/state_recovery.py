"""
MODULE PHỤC HỒI TRẠNG THÁI HỆ THỐNG (STATE RECOVERY MANAGER)
Đồ án Tốt nghiệp - Trường Đại học Giao thông vận tải TP.HCM (UTH)
Hệ thống: Quant AI V2.2 - Tự động đồng bộ CSDL và Vị thế sàn sau sự cố mất điện / rớt mạng
"""

import time
from datetime import datetime, timezone, timedelta
import json
from typing import Dict, Any, List, Optional
from loguru import logger
from backend.infrastructure.brokers.mt5_safe import mt5
from backend.database.db_manager import DatabaseManager


class StateRecoveryManager:
    """
    Quản lý phục hồi trạng thái hệ thống sau sự cố sập nguồn / rớt mạng:
    1. Quét đối soát giữa vị thế thực tế trên MT5 và vị thế ghi nhận trong SQLite.
    2. Cập nhật các lệnh đã chạm SL/TP trong lúc hệ thống offline.
    3. Ngăn chặn triệt để hành vi đặt lệnh mới chồng chéo (Duplicate Execution).
    """

    def __init__(self, db_manager: DatabaseManager = None):
        self.db = db_manager or DatabaseManager()

    def reconcile_on_startup(self, magic: Optional[int] = None) -> Dict[str, Any]:
        """
        Thực thi quy trình đối soát toàn diện ngay khi Bot khởi động lại.
        Đã xử lý triệt để:
        1. Phân biệt lỗi API (None) với tài khoản rỗng ().
        2. Không ghi đè PnL/Giá = 0 khi không lấy được deals lịch sử.
        3. Kiểm tra kết quả ghi SQLite trước khi tăng biến đếm.
        4. Trích xuất thời gian khớp lệnh thực tế từ máy chủ MT5 (UTC).
        """
        logger.info(
            "[StateRecovery] Bắt đầu quy trình đối soát phục hồi trạng thái hệ thống..."
        )

        # 1. TRUY VẤN VỊ THẾ SÀN VÀ XỬ LÝ LỖI NGHIÊM NGẶT
        account=mt5.account_info()
        if account is not None and isinstance(getattr(account,'login',None),int):
            self.db.bind_account(account.login,account.server)
        live_positions = mt5.positions_get()
        if live_positions is None:
            err_code, err_str = mt5.last_error()
            if err_code in (-10001, -10002, -10004):
                logger.warning(
                    f"[StateRecovery] Lỗi IPC ({err_code}: {err_str}) khi truy vấn vị thế sàn. "
                    "Đang thử tái thiết lập kênh kết nối MT5..."
                )
                try:
                    mt5.shutdown()
                    if mt5.initialize():
                        account = mt5.account_info()
                        if account is not None and isinstance(getattr(account, 'login', None), int):
                            self.db.bind_account(account.login, account.server)
                        live_positions = mt5.positions_get()
                except Exception as e_rec:
                    logger.debug(f"[StateRecovery] Ngoại lệ phục hồi IPC: {e_rec}")

        if live_positions is None:
            err_code, err_str = mt5.last_error()
            logger.critical(
                f"[StateRecovery] LỖI KẾT NỐI API: mt5.positions_get() trả về None "
                f"(Mã lỗi: {err_code} - {err_str}). DỪNG ĐỐI SOÁT ĐỂ BẢO VỆ CSDL!"
            )
            return {
                "status": "FAILED_API_ERROR",
                "error": f"API error code {err_code}: {err_str}",
                "active_positions_count": 0,
                "recovered_orphans": 0,
                "reconciled_closed": 0,
                "synced_active": 0,
                "circuit_breaker_active": (
                    self.db.get_system_state("circuit_breaker_active", default="False")
                    == "True"
                ),
            }

        if account is None or not isinstance(getattr(account, 'login', None), int):
            return {"status":"FAILED_ACCOUNT_UNVERIFIED", "active_positions_count":0,
                    "recovered_orphans":0,"reconciled_closed":0,"synced_active":0,
                    "circuit_breaker_active":True}

        self.reconcile_intents(live_positions=live_positions)

        # Lọc vị thế theo phạm vi quản lý của nền tảng nếu có chỉ định magic
        if magic is not None and magic != 0:
            managed_positions = [
                p for p in live_positions if getattr(p, "magic", 0) == magic
            ]
        else:
            managed_positions = list(live_positions)

        live_tickets = {pos.ticket: pos for pos in managed_positions}
        live_ids={getattr(pos,'identifier',pos.ticket) for pos in live_positions}

        # 2. Lấy danh sách vị thế đang đánh dấu là 'OPEN' trong CSDL
        db_open_trades = self.db.get_open_trades()
        db_tickets = {trade["ticket"]: trade for trade in db_open_trades}

        recovered_orphans = 0
        reconciled_closed = 0
        synced_active = 0
        failed_writes = 0

        # 3. ĐỐI SOÁT CHIỀU 1: Lệnh có trên MT5 nhưng DB chưa ghi nhận (Orphan positions)
        for ticket, pos in live_tickets.items():
            old=next((t for t in db_tickets.values() if t.get('position_id')==getattr(pos,'identifier',ticket)),None)
            if old:
                self.db.sync_position(old['ticket'],pos)
                synced_active+=1
                continue
            if ticket not in db_tickets:
                order_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
                # Lấy thời gian mở thực tế từ sàn MT5 (UTC) nếu có
                pos_time = getattr(pos, "time", None)
                pos_time_utc = (
                    datetime.fromtimestamp(pos_time, timezone.utc).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    if pos_time
                    else datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                )

                ok = self.db.record_open_trade(
                    ticket=ticket,
                    symbol=pos.symbol,
                    order_type=order_type,
                    volume=pos.volume,
                    open_price=pos.price_open,
                    sl=pos.sl,
                    tp=pos.tp,
                    open_time=pos_time_utc,
                    position_id=getattr(pos,"identifier",ticket),
                    initial_sl=0,  # Current trailing SL is not evidence of original risk.
                    magic=getattr(pos,"magic",0),
                    comment=f"Recovered_From_MT5_Magic_{getattr(pos, 'magic', 0)}",
                )
                if ok:
                    recovered_orphans += 1
                    logger.warning(
                        f"[StateRecovery] Đã phục hồi vị thế mồ côi #{ticket} {pos.symbol} từ MT5 vào CSDL!"
                    )
                else:
                    failed_writes += 1
                    logger.error(
                        f"[StateRecovery] Không thể ghi vị thế mồ côi #{ticket} vào CSDL!"
                    )
            else:
                synced_active += 1

        # 4. ĐỐI SOÁT CHIỀU 2: Lệnh DB đánh dấu OPEN nhưng MT5 không còn (Đã cắn SL/TP khi offline)
        for ticket, trade in db_tickets.items():
            if (trade.get("position_id") or ticket) not in live_ids:
                deals = None
                try:
                    deals = mt5.history_deals_get(position=trade.get("position_id") or ticket)
                except Exception as e_deal:
                    logger.error(
                        f"[StateRecovery] Ngoại lệ khi tra cứu Deals cho #{ticket}: {e_deal}"
                    )

                # NẾU KHÔNG CÓ DEALS: TUYỆT ĐỐI KHÔNG ĐÓNG LỆNH VỚI GIÁ VÀ PNL = 0
                if not deals:
                    logger.warning(
                        f"[StateRecovery] Vị thế #{ticket} không còn trên MT5 nhưng KHÔNG tìm thấy Deals "
                        f"lịch sử tương ứng. Giữ nguyên trạng thái để kiểm toán thủ công!"
                    )
                    self.db.set_system_state(
                        f"unreconciled_trade_{ticket}", "MISSING_DEALS_FROM_BROKER"
                    )
                    continue

                # Khi có deals: Tìm deal đóng (DEAL_ENTRY_OUT) cuối cùng theo thời gian
                out_deals = [d for d in deals if getattr(d, "entry", 0) in (1, 3)]
                if not out_deals:
                    continue
                self.db.record_deals(deals)
                exit_deal = (
                    max(
                        out_deals,
                        key=lambda x: getattr(
                            x, "time_msc", getattr(x, "time", 0)
                        ),
                    )
                    if out_deals
                    else deals[-1]
                )

                exit_price = float(getattr(exit_deal, "price", 0.0) or 0.0)
                deal_time = getattr(exit_deal, "time", None)
                exit_time_utc = (
                    datetime.fromtimestamp(deal_time, timezone.utc).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    if deal_time
                    else datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                )

                def _get_v(obj, attr):
                    v = getattr(obj, attr, 0.0)
                    return float(v) if isinstance(v, (int, float)) else 0.0

                pnl = sum(
                    _get_v(d, "profit")
                    + _get_v(d, "commission")
                    + _get_v(d, "swap")
                    + _get_v(d, "fee")
                    for d in deals
                )

                # Chỉ ghi nhận khi CSDL cập nhật thành công
                ok_close = self.db.record_close_trade(
                    ticket=ticket,
                    close_price=exit_price,
                    pnl=pnl,
                    close_time=exit_time_utc,
                )
                if ok_close:
                    reconciled_closed += 1
                    logger.info(
                        f"[StateRecovery] Lệnh #{ticket} đã được đóng trên Broker trong lúc offline "
                        f"(@{exit_price}, PnL: ${pnl:+.2f}). Cập nhật CSDL thành CLOSED."
                    )
                else:
                    failed_writes += 1
                    logger.error(
                        f"[StateRecovery] Không thể cập nhật trạng thái đóng cho #{ticket} trong CSDL!"
                    )

        # 5. Khôi phục trạng thái Circuit Breaker
        cb_state = self.db.get_system_state("circuit_breaker_active", default="False")

        status_result = "SUCCESS" if failed_writes == 0 else "PARTIAL_SUCCESS_WITH_WRITE_ERRORS"
        summary = {
            "status": status_result,
            "active_positions_count": len(live_tickets),
            "recovered_orphans": recovered_orphans,
            "reconciled_closed": reconciled_closed,
            "synced_active": synced_active,
            "failed_writes": failed_writes,
            "circuit_breaker_active": (cb_state == "True"),
        }
        logger.info(f"[StateRecovery] Phục hồi hoàn tất: {summary}")
        return summary

    def reconcile_intents(self, live_positions=None):
        """Rebuild complete broker-confirmed lifecycles before releasing reservations.

        Positive order/deal identities take precedence over comments. Missing or
        incomplete history is never interpreted as a rejection or a flat fill.
        """
        account=mt5.account_info()
        if account is None:
            return
        self.db.bind_account(account.login, account.server)
        if live_positions is None:
            live_positions=mt5.positions_get()
        orders=mt5.orders_get()
        if live_positions is None or orders is None:
            return
        live_by_id={getattr(p,'identifier',p.ticket):p for p in live_positions}
        for intent in self.db.get_unresolved_intents():
            payload=json.loads(intent['payload'])
            request=payload.get('request',payload)
            tag=request.get('broker_tag')
            order_id=payload.get('order_id') or payload.get('ticket') or request.get('order_id')
            def linked(obj, is_deal=False):
                if order_id:
                    return (getattr(obj,'order',None) if is_deal else getattr(obj,'ticket',None))==order_id
                return bool(tag and tag.startswith('V2_') and getattr(obj,'comment','')==tag)
            working=[o for o in orders if linked(o)]
            amendment=payload.get('amendment',{})
            if amendment.get('pending') and working:
                target=amendment['target']
                if any(all(abs(float(getattr(o,k))-float(target[v]))<1e-8
                           for k,v in (('price_open','price'),('sl','sl'),('tp','tp'))) for o in working):
                    request=target
                    payload={'request':request,'order_id':order_id}
                    self.db.finish_intent(intent['intent_id'],'UNKNOWN',payload)
                else:
                    continue
            updated_str = intent.get('updated_at') or ''
            try:
                updated_dt = datetime.fromisoformat(updated_str)
                if updated_dt.tzinfo is None:
                    updated_dt = updated_dt.replace(tzinfo=timezone.utc)
            except Exception:
                updated_dt = datetime.now(timezone.utc)
            start = updated_dt - timedelta(minutes=5)
            end = datetime.now(timezone.utc) + timedelta(minutes=1)
            # A historical position query below supplies its entire entry/exit lifecycle.
            deals=mt5.history_deals_get(start,end)
            if deals is None:
                continue
            matches=[d for d in deals if linked(d, is_deal=True)]
            if matches:
                position_ids={int(d.position_id) for d in matches if getattr(d,'position_id',0)>0}
                resolved=bool(position_ids)
                for pid in position_ids:
                    complete=mt5.history_deals_get(position=pid)
                    if not complete:
                        resolved=False
                        continue
                    complete=[d for d in complete if getattr(d,'position_id',None)==pid]
                    self.db.record_deals(complete)
                    pos=live_by_id.get(pid)
                    opening=[d for d in complete if getattr(d,'entry',None)==0]
                    first=min(opening,key=lambda d:getattr(d,'time_msc',d.time*1000)) if opening else None
                    broker_order=getattr(first,'order',None) or order_id or getattr(matches[0],'order',None)
                    if pos is not None:
                        saved=self.db.get_trade_by_position(pid)
                        if not saved:
                            if not self.db.record_open_trade(pos.ticket,pos.symbol,
                                    'BUY' if pos.type==mt5.ORDER_TYPE_BUY else 'SELL',pos.volume,pos.price_open,
                                    sl=pos.sl,tp=pos.tp,initial_sl=float(request.get('sl') or 0),
                                    open_time=datetime.fromtimestamp(pos.time,timezone.utc).isoformat(),
                                    position_id=pid,broker_order_id=broker_order,magic=pos.magic,
                                    strategy_id=request.get('strategy_id','')):
                                resolved=False
                                continue
                        else:
                            self.db.sync_position(saved['ticket'],pos)
                        if not self.db.attach_execution_policy(pos.ticket,pid,request,broker_order):
                            resolved=False
                    else:
                        # A fill and its exit can both happen between polls. Reconstruct
                        # only a volume-complete history; a partial exit is not flat proof.
                        exits=[d for d in complete if getattr(d,'entry',None) in (1,3)]
                        if not opening or not exits or any(getattr(d,'entry',None)==2 for d in complete):
                            resolved=False
                            continue
                        in_volume=sum(float(d.volume) for d in opening)
                        out_volume=sum(float(d.volume) for d in exits)
                        if in_volume<=0 or abs(in_volume-out_volume)>1e-8:
                            resolved=False
                            continue
                        open_price=sum(d.price*d.volume for d in opening)/in_volume
                        close_price=sum(d.price*d.volume for d in exits)/out_volume
                        last=max(exits,key=lambda d:getattr(d,'time_msc',d.time*1000))
                        pnl=sum(float(getattr(d,k,0) or 0) for d in complete
                                for k in ('profit','commission','swap','fee'))
                        saved=self.db.get_trade_by_position(pid)
                        ticket=saved['ticket'] if saved else pid
                        if not saved and not self.db.record_open_trade(ticket,first.symbol,
                                'BUY' if getattr(first,'type',0)==mt5.ORDER_TYPE_BUY else 'SELL',
                                in_volume,open_price,sl=float(request.get('sl') or 0),tp=float(request.get('tp') or 0),
                                position_id=pid,broker_order_id=broker_order,magic=getattr(first,'magic',0),
                                strategy_id=request.get('strategy_id',''),
                                open_time=datetime.fromtimestamp(first.time,timezone.utc).isoformat()):
                            resolved=False
                            continue
                        if not self.db.attach_execution_policy(ticket,pid,request,broker_order):
                            resolved=False
                            continue
                        if not self.db.record_close_trade(ticket,close_price,pnl,
                                datetime.fromtimestamp(last.time,timezone.utc).isoformat()):
                            resolved=False
                if resolved and not working and not amendment.get('pending'):
                    self.db.finish_intent(intent['intent_id'],'FILLED',{
                        'request':request,'order_id':order_id,
                        'reconciled_deals':[d.ticket for d in matches]})
                continue
            if working:
                continue
            # Direct TTL Stale Pruning: if not active in orders or deals and older than 60s, cancel immediately
            age_sec = (datetime.now(timezone.utc) - updated_dt).total_seconds()
            if not matches and age_sec > 60:
                self.db.finish_intent(intent['intent_id'], 'CANCELED', {
                    'request': request, 'reason': f'Stale TTL timeout ({int(age_sec)}s) pruned'
                })
                continue

            history=mt5.history_orders_get(start,end)
            if history is None:
                continue
            terminal=[o for o in history if linked(o) and getattr(o,'state',None) in (2,5,6)]
            if terminal:
                # A partially filled then canceled order still requires its fills.
                if any(float(getattr(o,'volume_initial',0) or 0)>
                       float(getattr(o,'volume_current',0) or 0)+1e-9 for o in terminal):
                    continue
                self.db.finish_intent(intent['intent_id'],'CANCELED',{
                    'request':request,'broker_order':terminal[-1].ticket})
            elif age_sec > 60:
                # Orphaned intent: Not working in broker, no deals, and no terminal order in history
                self.db.finish_intent(intent['intent_id'], 'CANCELED', {
                    'request': request, 'reason': 'Orphaned intent timed out after 60s'})

    def can_open_new_trade(self, symbol: str) -> bool:
        """
        Kiểm tra an toàn: Tuyệt đối không mở lệnh mới nếu mã này đã có vị thế đang chạy.
        """
        clean = symbol.split(".")[0].replace("/", "").upper()
        # Kiểm tra đồng thời cả trên MT5 lẫn Database
        if self.db.has_unresolved_intent(symbol):
            return False
        positions = mt5.positions_get(symbol=symbol)
        if positions is None:
            return False
        if positions and len(positions) > 0:
            if any(
                getattr(p, "symbol", "").split(".")[0].replace("/", "").upper()
                == clean
                for p in positions
            ):
                return False
        else:
            all_pos = mt5.positions_get()
            if all_pos is None:
                return False
            if all_pos:
                if any(
                    getattr(p, "symbol", "").split(".")[0].replace("/", "").upper()
                    == clean
                    for p in all_pos
                ):
                    return False

        db_trades = self.db.get_open_trades()
        if db_trades:
            if any(
                t.get("symbol", "").split(".")[0].replace("/", "").upper()
                == clean
                for t in db_trades
            ):
                return False

        return True
