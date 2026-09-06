from core.mt5_safe import mt5

class ExecutionManager:
    def __init__(self, magic_number: int = 999999):
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

    def execute_market_order(self, symbol: str, is_buy: bool, volume: float, sl_price: float, tp_price: float, comment: str = "Quant_AI") -> dict:
        """
        Bắn lệnh vào thị trường (Market Order). Trả về dict kết quả chuẩn.
        """
        if not mt5.symbol_select(symbol, True):
            return {"status": "error", "msg": f"Không thể lấy dữ liệu mã {symbol}"}
            
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return {"status": "error", "msg": f"Không có giá Tick cho {symbol}"}
            
        order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
        price = tick.ask if is_buy else tick.bid
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": order_type,
            "price": float(price),
            "sl": float(sl_price),
            "tp": float(tp_price),
            "deviation": 20, # Chấp nhận trượt giá 20 point để chống requote
            "magic": self.magic,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._get_fill_policy(symbol),
        }
        
        result = mt5.order_send(request)
        
        if result is None:
            return {"status": "error", "msg": f"Lệnh bị sập. Lỗi hệ thống: {mt5.last_error()}"}
            
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {"status": "error", "msg": f"Sàn từ chối lệnh: {result.comment} (Mã lỗi: {result.retcode})"}
            
        return {
            "status": "success", 
            "msg": f"Đã khớp lệnh {'BUY' if is_buy else 'SELL'} {volume} {symbol} tại giá {price}",
            "ticket": result.order
        }

    def close_all_positions(self, symbol: str) -> list[str]:
        """
        Đóng toàn bộ vị thế của một mã (Panic Close / Chốt lời toàn bộ).
        """
        positions = mt5.positions_get(symbol=symbol)
        if not positions:
            return []
            
        results = []
        for pos in positions:
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                results.append(f"Lỗi đóng lệnh {pos.ticket}: Không có dữ liệu tick")
                continue
                
            is_buy = pos.type == mt5.ORDER_TYPE_BUY
            
            # Lệnh đóng là lệnh ngược lại
            close_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
            close_price = tick.bid if is_buy else tick.ask
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": pos.volume,
                "type": close_type,
                "position": pos.ticket,
                "price": close_price,
                "deviation": 20,
                "magic": self.magic,
                "comment": "Quant_Close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": self._get_fill_policy(symbol),
            }
            res = mt5.order_send(request)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                results.append(f"Đã đóng lệnh {pos.ticket} thành công.")
            else:
                results.append(f"Lỗi đóng lệnh {pos.ticket}: {res.comment if res else 'Unknown'}")
                
        return results
