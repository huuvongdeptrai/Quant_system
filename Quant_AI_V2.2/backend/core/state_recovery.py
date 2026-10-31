"""
MODULE PHỤC HỒI TRẠNG THÁI HỆ THỐNG (STATE RECOVERY MANAGER)
Đồ án Tốt nghiệp - Trường Đại học Giao thông vận tải TP.HCM (UTH)
Hệ thống: Quant AI V2.2 - Tự động đồng bộ CSDL và Vị thế sàn sau sự cố mất điện / rớt mạng
"""

import time
from datetime import datetime, timezone
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
        live_positions = mt5.positions_get()
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

        # Lọc vị thế theo phạm vi quản lý của nền tảng nếu có chỉ định magic
        if magic is not None and magic != 0:
            managed_positions = [
                p for p in live_positions if getattr(p, "magic", 0) == magic
            ]
        else:
            managed_positions = list(live_positions)

        live_tickets = {pos.ticket: pos for pos in managed_positions}

        # 2. Lấy danh sách vị thế đang đánh dấu là 'OPEN' trong CSDL
        db_open_trades = self.db.get_open_trades()
        db_tickets = {trade["ticket"]: trade for trade in db_open_trades}

        recovered_orphans = 0
        reconciled_closed = 0
        synced_active = 0
        failed_writes = 0

        # 3. ĐỐI SOÁT CHIỀU 1: Lệnh có trên MT5 nhưng DB chưa ghi nhận (Orphan positions)
        for ticket, pos in live_tickets.items():
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
            if ticket not in live_tickets:
                deals = None
                try:
                    deals = mt5.history_deals_get(position=ticket)
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

    def can_open_new_trade(self, symbol: str) -> bool:
        """
        Kiểm tra an toàn: Tuyệt đối không mở lệnh mới nếu mã này đã có vị thế đang chạy.
        """
        clean = symbol.split(".")[0].replace("/", "").upper()
        # Kiểm tra đồng thời cả trên MT5 lẫn Database
        positions = mt5.positions_get(symbol=symbol)
        if positions and len(positions) > 0:
            if any(
                getattr(p, "symbol", "").split(".")[0].replace("/", "").upper()
                == clean
                for p in positions
            ):
                return False
        else:
            all_pos = mt5.positions_get()
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
