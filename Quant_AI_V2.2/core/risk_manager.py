from core.mt5_safe import mt5

class RiskManager:
    def __init__(self, default_risk_pct: float = 1.0):
        # Mặc định rủi ro 1% tài khoản cho mỗi lệnh
        self.default_risk_pct = default_risk_pct

    def calculate_lot_size(self, symbol: str, sl_points: float, risk_pct: float = None) -> float:
        """
        Tính toán tự động số Lot cần đánh dựa trên rủi ro % tài khoản và khoảng cách StopLoss.
        Sử dụng Type Hints để làm tài liệu sống (Self-documenting code).
        """
        if risk_pct is None:
            risk_pct = self.default_risk_pct
            
        account = mt5.account_info()
        info = mt5.symbol_info(symbol)
        
        if not account or not info:
            return 0.0

        # Số tiền chấp nhận mất (Bằng đồng tiền cơ sở của tài khoản, vd: USD)
        risk_amount = account.balance * (risk_pct / 100.0)
        
        # Lấy thông số kỹ thuật của sàn
        tick_size = info.trade_tick_size
        tick_value = info.trade_tick_value
        
        if tick_size == 0 or tick_value == 0 or sl_points == 0:
            return info.volume_min

        # Tính toán giá trị thua lỗ cho 1 Lot chuẩn
        loss_for_one_lot = (sl_points / tick_size) * tick_value
        
        if loss_for_one_lot == 0:
            return info.volume_min
            
        # Tính số Lot thô
        raw_lot = risk_amount / loss_for_one_lot
        
        # Chuẩn hoá số Lot theo quy định của sàn (Volume Step)
        # Tại sao phải dùng volume_step? Vì có sàn cho đánh 0.01, có sàn chỉ cho đánh 0.1 (Crypto)
        step = info.volume_step
        lot = round(raw_lot / step) * step
        
        # Khoá số Lot không được nhỏ hơn Min và lớn hơn Max
        lot = max(info.volume_min, min(info.volume_max, lot))
        
        # Làm tròn 2 chữ số thập phân an toàn
        return round(lot, 2)
