import time
import math
from decimal import Decimal, ROUND_FLOOR
from typing import Optional, List, Dict, Any
from loguru import logger
from backend.infrastructure.brokers.mt5_safe import mt5


class ExecutionManager:
    """
    Module quản lý khớp lệnh (Execution Layer) tích hợp:
    - Đo lường độ trễ mạng & sàn (Latency Logging với time.perf_counter).
    - Khả năng chống chịu lỗi sàn (Resilience & Auto-Retry khi gặp Requote, Slippage, Timeout).
    - Tự động phát hiện chính sách khớp lệnh (Fill Policy Detector).
    """

    def __init__(self, magic_number: int = 999999, slippage: int = 20):
        self.slippage = slippage
        self.magic = magic_number

    def _get_fill_policy(self, symbol: str) -> int:
        """
        Thuật toán tự động dò tìm loại Fill Policy mà Broker hỗ trợ.
        Giải quyết vấn đề 90% lệnh MT5 bị từ chối do khác biệt Fill Policy giữa các sàn.
        """
        info = mt5.symbol_info(symbol)
        if not info:
            return mt5.ORDER_FILLING_RETURN

        fill_modes = info.filling_mode
        SYMBOL_FILLING_FOK = 1
        SYMBOL_FILLING_IOC = 2

        if fill_modes & SYMBOL_FILLING_FOK:
            return mt5.ORDER_FILLING_FOK
        elif fill_modes & SYMBOL_FILLING_IOC:
            return mt5.ORDER_FILLING_IOC
        else:
            return mt5.ORDER_FILLING_RETURN

    def normalize_volume(self, symbol: str, volume: float) -> float:
        """
        Chuan hoa khoi luong theo thong so san (volume_min, volume_max, volume_step).
        Dap ung tieu chuan QuantConnect LEAN / MetaTrader 5 API specification:
        - Quantize ve boi so cua volume_step.
        - Gioi han trong khoang [volume_min, volume_max].
        - Loai bo loi so hoc dau phay dong (float precision error).
        """
        info = mt5.symbol_info(symbol)
        try:
            vol = float(volume)
        except (TypeError, ValueError):
            return 0.0

        def _safe_float(val, default):
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                return float(val)
            try:
                if isinstance(val, str):
                    return float(val)
            except (ValueError, TypeError):
                pass
            return default

        vol_min = _safe_float(getattr(info, "volume_min", None), 0.01) if info else 0.01
        vol_max = _safe_float(getattr(info, "volume_max", None), 100.0) if info else 100.0
        vol_step = _safe_float(getattr(info, "volume_step", None), 0.01) if info else 0.01

        if vol_step <= 0:
            vol_step = 0.01
        if vol_min <= 0:
            vol_min = vol_step
        if vol_max < vol_min:
            vol_max = 100.0

        step_str = f"{vol_step:.8f}".rstrip("0")
        digits = len(step_str.split(".")[1]) if "." in step_str else 0

        if not math.isfinite(vol) or vol <= 0 or vol < vol_min:
            return 0.0
        steps_count = int((Decimal(str(vol)) / Decimal(str(vol_step))).to_integral_value(rounding=ROUND_FLOOR))
        normalized = round(steps_count * vol_step, digits)

        if normalized < vol_min:
            return 0.0
        elif normalized > vol_max:
            normalized = vol_max

        return round(float(normalized), digits)

    def execute_market_order(self, symbol, is_buy, volume, sl_price, tp_price,
                             comment="VECTRA", magic=None, max_retries=3, **kwargs):
        """All entry requests share durable pre-trade admission and risk checks."""
        from backend.core.trading_commands import TradingCommandService
        return TradingCommandService(self).submit(
            symbol, is_buy, volume, sl_price, tp_price, comment, magic,
            max_retries=max_retries, **kwargs)

    def _execute_market_order_raw(
        self,
        symbol: str,
        is_buy: bool,
        volume: float,
        sl_price: float,
        tp_price: float,
        comment: str = "VECTRA",
        magic: Optional[int] = None,
        max_retries: int = 3,
        validated_price: Optional[float] = None,
    ) -> dict:
        """
        Bắn lệnh vào thị trường (Market Order) kèm:
        - Latency Logging: Đo đạc chính xác thời gian khớp lệnh (< 500ms).
        - Ambiguous outcomes stay unresolved; repricing requires new admission checks.
        """
        start_exec = time.perf_counter()
        if not isinstance(volume, (int, float)) or not math.isfinite(volume) or volume <= 0:
            return {"status": "error", "msg": "Invalid volume", "retries": 0}

        # Kiểm tra trạng thái cho phép giao dịch tự động của phần mềm MT5 (Algo Trading)
        terminal_info = mt5.terminal_info()
        if terminal_info and not terminal_info.trade_allowed:
            err_msg = "Chưa bật 'Algo Trading' trên phần mềm MT5 (Bấm Ctrl+E trên MT5 để kích hoạt)"
            logger.error(f"[ExecutionManager] {err_msg} (Ma loi: 10027)")
            return {
                "status": "error",
                "msg": err_msg,
                "latency_ms": 0.0,
                "retries": 0,
                "retcode": 10027,
            }

        for attempt in range(1, max_retries + 1):
            if not mt5.symbol_select(symbol, True):
                return {
                    "status": "error",
                    "msg": f"Khong the lay du lieu ma {symbol}",
                    "latency_ms": 0.0,
                    "retries": 0,
                }

            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                return {
                    "status": "error",
                    "msg": f"Khong co gia Tick cho {symbol}",
                    "latency_ms": 0.0,
                    "retries": 0,
                }

            info = mt5.symbol_info(symbol)
            digits = info.digits if info else 2

            order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
            price = tick.ask if is_buy else tick.bid
            price = round(float(price), digits)
            if validated_price is not None and ((price > validated_price + 1e-9) if is_buy else (price < validated_price - 1e-9)):
                return {"status":"error", "msg":"Adverse quote change: recalculate order risk", "retries":0}
            norm_volume = self.normalize_volume(symbol, volume)

            # Làm tròn SL/TP theo digits của sàn
            sl_val = round(float(sl_price), digits) if sl_price > 0 else 0.0
            tp_val = round(float(tp_price), digits) if tp_price > 0 else 0.0

            # Stop changes require a fresh risk calculation by TradingCommandService.
            if norm_volume <= 0 or sl_val <= 0 or tp_val <= 0 or not all(math.isfinite(v) for v in (price, sl_val, tp_val)):
                return {"status":"error", "msg":"Invalid order geometry or volume", "retries":attempt-1}
            if (is_buy and not sl_val < price < tp_val) or (not is_buy and not tp_val < price < sl_val):
                return {"status":"error", "msg":"Stops on incorrect side of price", "retries":attempt-1}
            if info and info.trade_stops_level > 0:
                min_dist = info.trade_stops_level * info.point
                reference = tick.bid if is_buy else tick.ask
                if (reference-sl_val if is_buy else sl_val-reference) < min_dist or (tp_val-reference if is_buy else reference-tp_val) < min_dist:
                    return {"status":"error", "msg":"Stop distance changed: recalculate order risk", "retries":attempt-1}

            curr_deviation = self.slippage

            target_magic = magic if magic is not None else (0 if "manual" in comment.lower() else self.magic)
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": norm_volume,
                "type": order_type,
                "price": price,
                "sl": sl_val,
                "tp": tp_val,
                "deviation": curr_deviation,
                "magic": target_magic,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": self._get_fill_policy(symbol),
            }

            req_start = time.perf_counter()
            result = mt5.order_send(request)
            req_end = time.perf_counter()
            round_latency_ms = (req_end - req_start) * 1000.0

            if result is None:
                err_code = mt5.last_error()
                logger.error(
                    f"[ExecutionManager] MT5 order_send returned None. Error: {err_code}"
                )
                return {"status":"unknown", "msg":f"Broker outcome unknown: {err_code}", "retries":attempt-1}

            total_latency_ms = (time.perf_counter() - start_exec) * 1000.0

            if result.retcode in (mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_DONE_PARTIAL):
                if total_latency_ms > 500.0:
                    logger.warning(
                        f"[ExecutionManager] CANH BAO DO TRE: {total_latency_ms:.2f} ms (> 500 ms)!"
                    )
                else:
                    logger.info(
                        f"[ExecutionManager] Khop lenh thanh cong sau {total_latency_ms:.2f} ms (Attempt {attempt})."
                    )

                return {
                    "status": "success",
                    "msg": f"Da khop lenh {'BUY' if is_buy else 'SELL'} {norm_volume} {symbol} tai gia {price} (Do tre: {total_latency_ms:.1f} ms)",
                    "ticket": result.order,
                    "order_id": result.order,
                    "deal_id": result.deal,
                    "price": float(result.price),
                    "volume": float(result.volume),
                    "partial": result.retcode == mt5.TRADE_RETCODE_DONE_PARTIAL,
                    "latency_ms": round(total_latency_ms, 2),
                    "retries": attempt - 1,
                    "retcode": result.retcode,
                }

            if result.retcode == mt5.TRADE_RETCODE_PLACED:
                return {'status':'unknown', 'msg':'Order accepted; waiting for broker fills',
                        'order_id':result.order, 'retcode':result.retcode, 'retries':attempt-1}

            # Xử lý các mã lỗi có thể thử lại
            if result.retcode in (mt5.TRADE_RETCODE_TIMEOUT, mt5.TRADE_RETCODE_CONNECTION):
                return {"status":"unknown", "msg":result.comment, "retcode":result.retcode, "retries":attempt-1}
            RETRYABLE_RETCODES = []

            if result.retcode in RETRYABLE_RETCODES and attempt < max_retries:
                logger.warning(
                    f"[ExecutionManager] Gap ma loi san #{result.retcode} ({result.comment}). Thu lai {attempt+1}/{max_retries}..."
                )
                time.sleep(0.15)
                continue
            else:
                comment_text = result.comment
                if result.retcode == 10027:
                    comment_text = "Chưa bật 'Algo Trading' trên MT5 (Nhấn Ctrl+E)"
                logger.error(
                    f"[ExecutionManager] San tu choi lenh: {comment_text} (Ma loi: {result.retcode})"
                )
                return {
                    "status": "error",
                    "msg": f"San tu choi lenh: {comment_text} (Ma loi: {result.retcode})",
                    "latency_ms": round(total_latency_ms, 2),
                    "retries": attempt - 1,
                    "retcode": result.retcode,
                }

    def execute_pending_order(self, symbol, order_type, price, volume, sl_price, tp_price,
                              comment="VECTRA_Pending", magic=None, max_retries=3):
        from backend.core.trading_commands import TradingCommandService
        return TradingCommandService(self).submit(symbol, order_type.startswith("BUY"), volume,
            sl_price, tp_price, comment, magic, pending_type=order_type, pending_price=price,
            max_retries=max_retries)

    def _execute_pending_order_raw(
        self,
        symbol: str,
        order_type: str,  # "BUY_LIMIT", "SELL_LIMIT", "BUY_STOP", "SELL_STOP"
        price: float,
        volume: float,
        sl_price: float,
        tp_price: float,
        comment: str = "VECTRA_Pending",
        magic: Optional[int] = None,
        max_retries: int = 3,
    ) -> dict:
        """
        Bắn lệnh chờ vào thị trường (Pending Order: Limit / Stop) kèm:
        - Mapping chuẩn MT5 API (ORDER_TYPE_BUY_LIMIT, SELL_LIMIT, BUY_STOP, SELL_STOP).
        - Latency Logging: Đo đạc thời gian gửi lệnh qua time.perf_counter.
        - Kiểm tra Stops Level chống sàn từ chối.
        - TRADE_ACTION_PENDING.
        """
        start_exec = time.perf_counter()

        terminal_info = mt5.terminal_info()
        if terminal_info and not terminal_info.trade_allowed:
            err_msg = "Chưa bật 'Algo Trading' trên phần mềm MT5 (Bấm Ctrl+E trên MT5 để kích hoạt)"
            logger.error(f"[ExecutionManager] {err_msg} (Ma loi: 10027)")
            return {
                "status": "error",
                "msg": err_msg,
                "latency_ms": 0.0,
                "retries": 0,
                "retcode": 10027,
            }

        type_map = {
            "BUY_LIMIT": mt5.ORDER_TYPE_BUY_LIMIT,
            "SELL_LIMIT": mt5.ORDER_TYPE_SELL_LIMIT,
            "BUY_STOP": mt5.ORDER_TYPE_BUY_STOP,
            "SELL_STOP": mt5.ORDER_TYPE_SELL_STOP,
        }
        clean_type_str = order_type.upper().strip()
        if clean_type_str not in type_map:
            return {
                "status": "error",
                "msg": f"Loai lenh cho khong hop le: {order_type}. Chi ho tro BUY_LIMIT, SELL_LIMIT, BUY_STOP, SELL_STOP",
                "latency_ms": 0.0,
                "retries": 0,
            }

        mt5_order_type = type_map[clean_type_str]

        for attempt in range(1, max_retries + 1):
            if not mt5.symbol_select(symbol, True):
                return {
                    "status": "error",
                    "msg": f"Khong the lay du lieu ma {symbol}",
                    "latency_ms": 0.0,
                    "retries": 0,
                }

            info = mt5.symbol_info(symbol)
            digits = info.digits if info else 2
            point = info.point if info and info.point > 0 else 0.01

            target_price = round(float(price), digits)
            norm_volume = self.normalize_volume(symbol, volume)
            sl_val = round(float(sl_price), digits) if sl_price > 0 else 0.0
            tp_val = round(float(tp_price), digits) if tp_price > 0 else 0.0

            # Kiểm tra Stops Level
            if info and info.trade_stops_level > 0:
                min_dist = info.trade_stops_level * point
                tick = mt5.symbol_info_tick(symbol)
                if tick:
                    curr_p = tick.ask if "BUY" in clean_type_str else tick.bid
                    if abs(target_price - curr_p) < min_dist:
                        logger.warning(
                            f"[ExecutionManager] Gia dat cho {target_price} qua sat gia hien tai {curr_p} (StopsLevel: {min_dist})"
                        )

            target_magic = magic if magic is not None else (0 if "manual" in comment.lower() else self.magic)
            request = {
                "action": mt5.TRADE_ACTION_PENDING,
                "symbol": symbol,
                "volume": norm_volume,
                "type": mt5_order_type,
                "price": target_price,
                "sl": sl_val,
                "tp": tp_val,
                "deviation": self.slippage,
                "magic": target_magic,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_RETURN,
            }

            req_start = time.perf_counter()
            result = mt5.order_send(request)
            req_end = time.perf_counter()
            round_latency_ms = (req_end - req_start) * 1000.0

            if result is None:
                return {"status":"unknown", "msg":str(mt5.last_error()), "retries":attempt-1}

            total_latency_ms = (time.perf_counter() - start_exec) * 1000.0

            if result.retcode in (mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_PLACED):
                logger.info(
                    f"[ExecutionManager] Dat lenh cho {clean_type_str} {norm_volume} {symbol} @ {target_price} thanh cong #{result.order} sau {total_latency_ms:.2f} ms."
                )
                return {
                    "status": "success",
                    "msg": f"Da dat lenh cho {clean_type_str} {norm_volume} {symbol} tai gia {target_price} (Ticket #{result.order})",
                    "ticket": result.order,
                    "price": target_price,
                    "volume": norm_volume,
                    "latency_ms": round(total_latency_ms, 2),
                    "retries": attempt - 1,
                    "retcode": result.retcode,
                }

            if result.retcode in (mt5.TRADE_RETCODE_TIMEOUT, mt5.TRADE_RETCODE_CONNECTION):
                return {"status":"unknown", "msg":result.comment, "retcode":result.retcode, "retries":attempt-1}
            RETRYABLE_RETCODES = []

            if result.retcode in RETRYABLE_RETCODES and attempt < max_retries:
                logger.warning(
                    f"[ExecutionManager] Gap ma loi san #{result.retcode} ({result.comment}). Thu lai {attempt+1}/{max_retries}..."
                )
                time.sleep(0.15)
                continue
            else:
                comment_text = result.comment
                if result.retcode == 10027:
                    comment_text = "Chưa bật 'Algo Trading' trên MT5 (Nhấn Ctrl+E)"
                logger.error(
                    f"[ExecutionManager] San tu choi lenh cho: {comment_text} (Ma loi: {result.retcode})"
                )
                return {
                    "status": "error",
                    "msg": f"San tu choi lenh cho: {comment_text} (Ma loi: {result.retcode})",
                    "latency_ms": round(total_latency_ms, 2),
                    "retries": attempt - 1,
                    "retcode": result.retcode,
                }

    def close_position(self, ticket: int, volume: float = None) -> dict:
        """
        Đóng một vị thế cụ thể theo số Ticket kèm đo lường độ trễ.
        Hỗ trợ đóng một phần (Partial Close) nếu chỉ định volume.
        """
        start_exec = time.perf_counter()
        positions = mt5.positions_get(ticket=ticket)
        if not positions or len(positions) == 0:
            return {
                "status": "error",
                "msg": f"Khong tim thay vi the #{ticket}",
                "latency_ms": 0.0,
            }

        pos = positions[0]
        sym = pos.symbol
        tick = mt5.symbol_info_tick(sym)
        if not tick:
            return {
                "status": "error",
                "msg": f"Khong co du lieu tick cho {sym}",
                "latency_ms": 0.0,
            }

        info = mt5.symbol_info(sym)
        digits = info.digits if info else 2

        is_buy = pos.type == mt5.ORDER_TYPE_BUY
        close_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
        close_price = tick.bid if is_buy else tick.ask
        close_price = round(float(close_price), digits)

        if volume is not None and (not math.isfinite(float(volume)) or float(volume) <= 0 or float(volume) > pos.volume):
            return {"status":"error", "msg":"Invalid close volume"}
        if volume is not None and 0 < float(volume) < pos.volume:
            norm_close = self.normalize_volume(sym, volume)
            min_step = 0.01
            if info:
                val_min = getattr(info, "volume_min", None)
                if isinstance(val_min, (int, float)) and not isinstance(val_min, bool) and val_min > 0:
                    min_step = float(val_min)
            remaining = pos.volume - norm_close
            if norm_close <= 0 or norm_close >= pos.volume or remaining < min_step:
                return {"status":"error", "msg":"Partial close would leave invalid remainder"}
            else:
                close_volume = norm_close
                is_partial = True
        else:
            close_volume = pos.volume
            is_partial = False

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": sym,
            "volume": close_volume,
            "type": close_type,
            "position": pos.ticket,
            "price": close_price,
            "deviation": self.slippage,
            "magic": self.magic,
            "comment": "Quant_Close_Partial" if is_partial else "Quant_Close_Single",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._get_fill_policy(sym),
        }
        res = mt5.order_send(request)
        total_latency_ms = (time.perf_counter() - start_exec) * 1000.0

        if res and res.retcode in (mt5.TRADE_RETCODE_DONE,mt5.TRADE_RETCODE_DONE_PARTIAL):
            filled=getattr(res,'volume',None)
            if not isinstance(filled,(int,float)) or not math.isfinite(filled) or filled<=0:
                if res.retcode==mt5.TRADE_RETCODE_DONE_PARTIAL:
                    return {'status':'unknown','msg':'Partial close volume requires reconciliation'}
                filled=close_volume
            remaining_vol=max(0.0,pos.volume-float(filled))
            completed_request = float(filled)>=close_volume-1e-9
            action_desc = f"Closed {filled} lots of position #{ticket}; remaining {remaining_vol}"
            # SC-08: Synchronize remaining volume with DatabaseManager on partial close
            if remaining_vol>0:
                try:
                    from backend.database.db_manager import DatabaseManager
                    db=DatabaseManager()
                    account=mt5.account_info()
                    if account is not None:
                        db.bind_account(account.login,account.server)
                        db.update_trade_volume(ticket, remaining_vol)
                except Exception as e_db:
                    logger.debug(f"[ExecutionManager] Partial close DB sync skipped: {e_db}")
            return {
                "status": "success" if completed_request else "partial",
                "msg": f"{action_desc} (Do tre: {total_latency_ms:.1f} ms)",
                "deal": res.deal,
                "partial_fill": res.retcode == mt5.TRADE_RETCODE_DONE_PARTIAL,
                "filled_volume": float(filled),
                "remaining_volume": remaining_vol,
                "position_closed": remaining_vol<=1e-9,
                "retcode": res.retcode,
                "latency_ms": round(total_latency_ms, 2),
            }
        if res is None or res.retcode in (mt5.TRADE_RETCODE_TIMEOUT,mt5.TRADE_RETCODE_CONNECTION,mt5.TRADE_RETCODE_PLACED):
            return {"status":"unknown","msg":"Close requires broker reconciliation"}
        return {
            "status": "error",
            "msg": f"Loi dong vi the #{ticket}: {res.comment if res else 'Unknown'}",
            "retcode": res.retcode if res else None,
            "latency_ms": round(total_latency_ms, 2),
        }

    def close_all_positions(self, symbol: str, bot_only: bool = True) -> list[str]:
        """
        Đóng toàn bộ vị thế của một mã (Panic Close / Chốt lời toàn bộ).
        - bot_only=True: Chỉ đóng lệnh của Bot (magic khớp self.magic và không phải lệnh manual), bảo vệ lệnh tay của user.
        - bot_only=False: Thanh lý mọi vị thế của symbol trên tài khoản.
        """
        positions = mt5.positions_get(symbol=symbol)
        if not positions:
            return []

        results = []
        info = mt5.symbol_info(symbol)
        digits = info.digits if info else 2

        for pos in positions:
            # SC-06: Protect user manual trades from accidental liquidation
            pos_magic = getattr(pos, "magic", 0)
            pos_comment = str(getattr(pos, "comment", "") or "").lower()
            if bot_only:
                if "manual" in pos_comment:
                    continue
                if isinstance(pos_magic, (int, float)) and self.magic is not None and int(pos_magic) != int(self.magic):
                    continue
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                results.append(f"Loi dong lenh {pos.ticket}: Khong co du lieu tick")
                continue

            is_buy = pos.type == mt5.ORDER_TYPE_BUY
            close_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
            close_price = tick.bid if is_buy else tick.ask
            close_price = round(float(close_price), digits)

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": pos.volume,
                "type": close_type,
                "position": pos.ticket,
                "price": close_price,
                "deviation": self.slippage,
                "magic": self.magic,
                "comment": "Quant_Close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": self._get_fill_policy(symbol),
            }
            res = mt5.order_send(request)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                results.append(f"Da dong lenh {pos.ticket} thanh cong.")
            else:
                results.append(
                    f"Loi dong lenh {pos.ticket}: {res.comment if res else 'Unknown'}"
                )

        return results

    def panic_kill_switch_all(self) -> list[str]:
        """
        Kill Switch Toàn Hệ Thống: Đóng sạch mọi vị thế mở trên tài khoản và hủy toàn bộ lệnh chờ (Pending Orders).
        """
        results = []
        positions = mt5.positions_get()
        if positions:
            for pos in positions:
                sym = pos.symbol
                tick = mt5.symbol_info_tick(sym)
                if not tick:
                    continue
                info = mt5.symbol_info(sym)
                digits = info.digits if info else 2
                is_buy = pos.type == mt5.ORDER_TYPE_BUY
                close_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
                close_price = round(float(tick.bid if is_buy else tick.ask), digits)
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": sym,
                    "volume": pos.volume,
                    "type": close_type,
                    "position": pos.ticket,
                    "price": close_price,
                    "deviation": self.slippage,
                    "magic": self.magic,
                    "comment": "PANIC_KILL_SWITCH",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": self._get_fill_policy(sym),
                }
                res = mt5.order_send(request)
                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                    results.append(f"[KILL SWITCH] Da dong vi the {sym} #{pos.ticket}")
                else:
                    results.append(
                        f"[KILL SWITCH] Loi dong {sym} #{pos.ticket}: {res.comment if res else 'Unknown'}"
                    )

        orders = mt5.orders_get()
        if orders:
            for ord in orders:
                req = {"action": mt5.TRADE_ACTION_REMOVE, "order": ord.ticket}
                res = mt5.order_send(req)
                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                    results.append(f"[KILL SWITCH] Da huy lenh cho #{ord.ticket}")

        return results

    def modify_position(self, ticket: int, sl: float, tp: float) -> dict:
        """
        Dieu chinh Stop Loss va Take Profit cho mot vi the dang mo (TRADE_ACTION_SLTP).
        """
        start_exec = time.perf_counter()
        positions = mt5.positions_get(ticket=ticket)
        if not positions or len(positions) == 0:
            return {
                "status": "error",
                "msg": f"Khong tim thay vi the #{ticket}",
                "latency_ms": 0.0,
            }

        pos = positions[0]
        sym = pos.symbol
        info = mt5.symbol_info(sym)
        digits = info.digits if info else 2

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": pos.ticket,
            "symbol": sym,
            "sl": round(float(sl), digits),
            "tp": round(float(tp), digits),
        }
        res = mt5.order_send(request)
        total_latency_ms = (time.perf_counter() - start_exec) * 1000.0

        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            return {
                "status": "success",
                "msg": f"Da cap nhat SL/TP cho vi the #{ticket} thanh cong (Do tre: {total_latency_ms:.1f} ms)",
                "latency_ms": round(total_latency_ms, 2),
            }
        return {
            "status": "error",
            "msg": f"Loi sua vi the #{ticket}: {res.comment if res else 'Unknown'}",
            "latency_ms": round(total_latency_ms, 2),
        }

    def cancel_pending_order(self, ticket: int) -> dict:
        """
        Huy mot lenh cho (Pending Order) tren MT5 bang TRADE_ACTION_REMOVE.
        """
        start_exec = time.perf_counter()
        request = {
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": ticket,
        }
        res = mt5.order_send(request)
        total_latency_ms = (time.perf_counter() - start_exec) * 1000.0

        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            return {
                "status": "success",
                "msg": f"Da huy lenh cho #{ticket} thanh cong (Do tre: {total_latency_ms:.1f} ms)",
                "latency_ms": round(total_latency_ms, 2),
            }
        return {
            "status": "error",
            "msg": f"Loi huy lenh cho #{ticket}: {res.comment if res else 'Unknown'}",
            "latency_ms": round(total_latency_ms, 2),
        }

    def modify_pending_order(self, ticket: int, price: float, sl=None, tp=None) -> dict:
        from backend.core.trading_commands import TradingCommandService
        return TradingCommandService(self).modify_pending(ticket, price, sl, tp)

    def _modify_pending_order_raw(
        self, ticket: int, price: float, sl: float = 0.0, tp: float = 0.0
    ) -> dict:
        """
        Dieu chinh muc gia, Stop Loss hoac Take Profit cho mot lenh cho (Pending Order) tren MT5 (TRADE_ACTION_MODIFY).
        """
        start_exec = time.perf_counter()
        orders = mt5.orders_get(ticket=ticket)
        if not orders or len(orders) == 0:
            return {
                "status": "error",
                "msg": f"Khong tim thay lenh cho #{ticket}",
                "latency_ms": 0.0,
            }

        ord_obj = orders[0]
        sym = ord_obj.symbol
        info = mt5.symbol_info(sym)
        digits = info.digits if info else (2 if price > 10 else 5)

        request = {
            "action": mt5.TRADE_ACTION_MODIFY,
            "order": int(ticket),
            "price": round(float(price), digits),
            "sl": round(float(sl), digits) if sl and sl > 0 else 0.0,
            "tp": round(float(tp), digits) if tp and tp > 0 else 0.0,
            "type_time": getattr(ord_obj, "type_time", mt5.ORDER_TIME_GTC),
            "type_filling": getattr(ord_obj, "type_filling", mt5.ORDER_FILLING_IOC),
        }
        res = mt5.order_send(request)
        total_latency_ms = (time.perf_counter() - start_exec) * 1000.0

        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            return {
                "status": "success",
                "ticket": ticket,
                "price": round(float(price), digits),
                "msg": f"Da cap nhat lenh cho #{ticket} sang gia {price:.{digits}f} thanh cong (Do tre: {total_latency_ms:.1f} ms)",
                "latency_ms": round(total_latency_ms, 2),
            }
        if res is None or res.retcode in (mt5.TRADE_RETCODE_TIMEOUT,mt5.TRADE_RETCODE_CONNECTION,mt5.TRADE_RETCODE_PLACED):
            return {'status':'unknown','msg':'Amendment requires broker reconciliation'}
        return {
            "status": "error",
            "msg": f"Loi sua lenh cho #{ticket}: {res.comment if res else 'Unknown'}",
            "retcode": getattr(res, "retcode", None),
            "latency_ms": round(total_latency_ms, 2),
        }
