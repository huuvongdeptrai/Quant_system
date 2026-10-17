from backend.infrastructure.brokers.mt5_safe import mt5


class RiskManager:
    def __init__(self, default_risk_pct: float = 1.0):
        # Mặc định rủi ro 1% tài khoản cho mỗi lệnh
        self.default_risk_pct = default_risk_pct

    def calculate_lot_size(
        self, symbol: str, sl_points: float, risk_pct: float = None
    ) -> float:
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

        import math

        # Lấy thông số kỹ thuật của sàn
        tick_size = getattr(info, "trade_tick_size", 0.0) or 0.0
        tick_value = getattr(info, "trade_tick_value", 0.0) or 0.0
        vol_min = getattr(info, "volume_min", 0.01)
        vol_max = getattr(info, "volume_max", 100.0)

        if tick_size <= 0 or tick_value <= 0 or sl_points <= 0:
            return vol_min

        # Tính toán giá trị thua lỗ cho 1 Lot chuẩn
        loss_for_one_lot = (sl_points / tick_size) * tick_value

        if loss_for_one_lot <= 0 or math.isnan(loss_for_one_lot) or math.isinf(loss_for_one_lot):
            return vol_min

        # Tính số Lot thô
        raw_lot = risk_amount / loss_for_one_lot
        if math.isnan(raw_lot) or math.isinf(raw_lot):
            return vol_min

        # Chuẩn hoá số Lot theo quy định của sàn (Volume Step)
        # Tại sao phải dùng volume_step? Vì có sàn cho đánh 0.01, có sàn chỉ cho đánh 0.1 (Crypto)
        step = getattr(info, "volume_step", 0.01)
        if not step or step <= 0:
            step = 0.01

        lot = round(raw_lot / step) * step

        # Khoá số Lot không được nhỏ hơn Min và lớn hơn Max
        lot = max(vol_min, min(vol_max, lot))

        # Xác định số chữ số thập phân an toàn theo volume_step
        digits = 2
        if step < 0.01:
            digits = 3
        elif step >= 0.1:
            digits = 1

        return round(lot, digits)
