import time
from loguru import logger
from infrastructure.brokers.mt5_safe import mt5


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

    def execute_market_order(
        self,
        symbol: str,
        is_buy: bool,
        volume: float,
        sl_price: float,
        tp_price: float,
        comment: str = "Quant_AI",
        max_retries: int = 3,
    ) -> dict:
        """
        Bắn lệnh vào thị trường (Market Order) kèm:
        - Latency Logging: Đo đạc chính xác thời gian khớp lệnh (< 500ms).
        - Fault Tolerance & Auto-Retry: Tự động thử lại khi gặp Requote / Price Changed.
        """
        start_exec = time.perf_counter()

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

            # Làm tròn SL/TP theo digits của sàn
            sl_val = round(float(sl_price), digits) if sl_price > 0 else 0.0
            tp_val = round(float(tp_price), digits) if tp_price > 0 else 0.0

            # Kiểm tra Stops Level chống sàn từ chối
            if info and info.trade_stops_level > 0:
                min_dist = info.trade_stops_level * info.point
                if sl_val > 0:
                    dist = (price - sl_val) if is_buy else (sl_val - price)
                    if dist < min_dist:
                        sl_val = round(
                            price - min_dist if is_buy else price + min_dist, digits
                        )
                if tp_val > 0:
                    dist = (tp_val - price) if is_buy else (price - tp_val)
                    if dist < min_dist:
                        tp_val = round(
                            price + min_dist if is_buy else price - min_dist, digits
                        )

            curr_deviation = self.slippage + (attempt - 1) * 10

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(volume),
                "type": order_type,
                "price": price,
                "sl": sl_val,
                "tp": tp_val,
                "deviation": curr_deviation,
                "magic": self.magic,
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
                if attempt < max_retries:
                    time.sleep(0.1)
                    continue
                return {
                    "status": "error",
                    "msg": f"Lenh bi sap. Loi he thong: {err_code}",
                    "latency_ms": round_latency_ms,
                    "retries": attempt - 1,
                }

            total_latency_ms = (time.perf_counter() - start_exec) * 1000.0

            if result.retcode == mt5.TRADE_RETCODE_DONE:
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
                    "msg": f"Da khop lenh {'BUY' if is_buy else 'SELL'} {volume} {symbol} tai gia {price} (Do tre: {total_latency_ms:.1f} ms)",
                    "ticket": result.order,
                    "latency_ms": round(total_latency_ms, 2),
                    "retries": attempt - 1,
                    "retcode": result.retcode,
                }

            # Xử lý các mã lỗi có thể thử lại
            RETRYABLE_RETCODES = [
                mt5.TRADE_RETCODE_REQUOTE,
                mt5.TRADE_RETCODE_PRICE_CHANGED,
                mt5.TRADE_RETCODE_PRICE_OFF,
                mt5.TRADE_RETCODE_TIMEOUT,
                mt5.TRADE_RETCODE_CONNECTION,
            ]

            if result.retcode in RETRYABLE_RETCODES and attempt < max_retries:
                logger.warning(
                    f"[ExecutionManager] Gap ma loi san #{result.retcode} ({result.comment}). Thu lai {attempt+1}/{max_retries}..."
                )
                time.sleep(0.15)
                continue
            else:
                logger.error(
                    f"[ExecutionManager] San tu choi lenh: {result.comment} (Ma loi: {result.retcode})"
                )
                return {
                    "status": "error",
                    "msg": f"San tu choi lenh: {result.comment} (Ma loi: {result.retcode})",
                    "latency_ms": round(total_latency_ms, 2),
                    "retries": attempt - 1,
                    "retcode": result.retcode,
                }

    def close_position(self, ticket: int) -> dict:
        """
        Đóng một vị thế cụ thể theo số Ticket kèm đo lường độ trễ.
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

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": sym,
            "volume": pos.volume,
            "type": close_type,
            "position": pos.ticket,
            "price": close_price,
            "deviation": self.slippage,
            "magic": self.magic,
            "comment": "Quant_Close_Single",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._get_fill_policy(sym),
        }
        res = mt5.order_send(request)
        total_latency_ms = (time.perf_counter() - start_exec) * 1000.0

        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            return {
                "status": "success",
                "msg": f"Da dong thanh cong vi the #{ticket} (Do tre: {total_latency_ms:.1f} ms)",
                "deal": res.deal,
                "latency_ms": round(total_latency_ms, 2),
            }
        return {
            "status": "error",
            "msg": f"Loi dong vi the #{ticket}: {res.comment if res else 'Unknown'}",
            "latency_ms": round(total_latency_ms, 2),
        }

    def close_all_positions(self, symbol: str) -> list[str]:
        """
        Đóng toàn bộ vị thế của một mã (Panic Close / Chốt lời toàn bộ).
        """
        positions = mt5.positions_get(symbol=symbol)
        if not positions:
            return []

        results = []
        info = mt5.symbol_info(symbol)
        digits = info.digits if info else 2

        for pos in positions:
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
