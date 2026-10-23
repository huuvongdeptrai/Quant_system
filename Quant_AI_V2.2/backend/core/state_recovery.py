"""
MODULE PHỤC HỒI TRẠNG THÁI HỆ THỐNG (STATE RECOVERY MANAGER)
Đồ án Tốt nghiệp - Trường Đại học Giao thông vận tải TP.HCM (UTH)
Hệ thống: Quant AI V2.2 - Tự động đồng bộ CSDL và Vị thế sàn sau sự cố mất điện / rớt mạng
"""

from typing import Dict, Any, List
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

    def reconcile_on_startup(self) -> Dict[str, Any]:
        """
        Thực thi quy trình đối soát toàn diện ngay khi Bot khởi động lại.
        """
        logger.info(
            "[StateRecovery] Bắt đầu quy trình đối soát phục hồi trạng thái hệ thống..."
        )

        # 1. Lấy danh sách vị thế thực tế đang mở trên MT5
        live_positions = mt5.positions_get()
        live_tickets = (
            {pos.ticket: pos for pos in live_positions} if live_positions else {}
        )

        # 2. Lấy danh sách vị thế đang đánh dấu là 'OPEN' trong CSDL
        db_open_trades = self.db.get_open_trades()
        db_tickets = {trade["ticket"]: trade for trade in db_open_trades}

        recovered_orphans = 0
        reconciled_closed = 0
        synced_active = 0

        # 3. Đối soát: Lệnh có trên MT5 nhưng DB chưa ghi nhận (Orphan positions)
        for ticket, pos in live_tickets.items():
            if ticket not in db_tickets:
                order_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
                self.db.record_open_trade(
                    ticket=ticket,
                    symbol=pos.symbol,
                    order_type=order_type,
                    volume=pos.volume,
                    open_price=pos.price_open,
                    sl=pos.sl,
                    tp=pos.tp,
                    comment="Recovered_From_MT5",
                )
                recovered_orphans += 1
                logger.warning(
                    f"[StateRecovery] Đã phục hồi vị thế mồ côi #{ticket} {pos.symbol} từ MT5 vào CSDL!"
                )
            else:
                synced_active += 1

        # 4. Đối soát: Lệnh DB đánh dấu OPEN nhưng MT5 không còn (Đã cắn SL/TP khi offline)
        for ticket, trade in db_tickets.items():
            if ticket not in live_tickets:
                # Tra cứu lịch sử Deals từ MT5 để khôi phục chính xác giá đóng và PnL thực tế
                exit_price = 0.0
                pnl = 0.0
                try:
                    deals = mt5.history_deals_get(position=ticket)
                    if deals:
                        exit_price = float(deals[-1].price or 0.0)
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
                except Exception as e_deal:
                    logger.debug(f"[StateRecovery] Tra cứu Deals cho #{ticket} lỗi: {e_deal}")

                # Đóng lệnh trong DB với giá trị thực
                self.db.record_close_trade(ticket=ticket, close_price=exit_price, pnl=pnl)
                reconciled_closed += 1
                logger.info(
                    f"[StateRecovery] Lệnh #{ticket} đã được đóng trên Broker trong lúc offline (@{exit_price}, PnL: ${pnl:+.2f}). Cập nhật CSDL thành CLOSED."
                )

        # 5. Khôi phục trạng thái Circuit Breaker
        cb_state = self.db.get_system_state("circuit_breaker_active", default="False")

        summary = {
            "status": "SUCCESS",
            "active_positions_count": len(live_tickets),
            "recovered_orphans": recovered_orphans,
            "reconciled_closed": reconciled_closed,
            "synced_active": synced_active,
            "circuit_breaker_active": (cb_state == "True"),
        }
        logger.info(f"[StateRecovery] Phục hồi hoàn tất: {summary}")
        return summary

    def can_open_new_trade(self, symbol: str) -> bool:
        """
        Kiểm tra an toàn: Tuyệt đối không mở lệnh mới nếu mã này đã có vị thế đang chạy.
        """
        clean = symbol.split(".")[0].replace("/", "").upper()
        # Kiểm tra đồng thời cả trên MT5 lẫn Database
        positions = mt5.positions_get(symbol=symbol)
        if positions and len(positions) > 0:
            if any(getattr(p, "symbol", "").split(".")[0].replace("/", "").upper() == clean for p in positions):
                return False
        else:
            all_pos = mt5.positions_get()
            if all_pos:
                if any(getattr(p, "symbol", "").split(".")[0].replace("/", "").upper() == clean for p in all_pos):
                    return False

        db_trades = self.db.get_open_trades()
        if db_trades:
            if any(t.get("symbol", "").split(".")[0].replace("/", "").upper() == clean for t in db_trades):
                return False

        return True
