import math
from decimal import Decimal, ROUND_FLOOR
from backend.infrastructure.brokers.mt5_safe import mt5


class RiskManager:
    def __init__(self, default_risk_pct: float = 1.0):
        # Mặc định rủi ro 1% tài khoản cho mỗi lệnh
        self.default_risk_pct = default_risk_pct

    def calculate_lot_size(
        self,
        symbol: str,
        sl_points: float,
        risk_pct: float = None,
        reject_under_min: bool = True,
    ) -> float:
        """
        Tính toán tự động số Lot cần đánh dựa trên rủi ro % tài khoản và khoảng cách StopLoss.
        Tuân thủ quy trình 4 bước chuẩn định chế:
        1. Xác định ngân sách rủi ro (RiskMoney = Balance * RiskPct / 100).
        2. Xác định mức lỗ dự kiến cho 1 lot chuẩn: Loss_1lot = (sl_points / tick_size) * tick_value.
        3. Tính raw_lot = RiskMoney / Loss_1lot.
        4. Làm tròn xuống (floor) theo volume_step và kiểm tra các giới hạn sàn:
           - Nếu lot < volume_min: Từ chối lệnh (trả về 0.0 nếu reject_under_min=True)
             nhằm bảo đảm rủi ro thực tế không vượt quá ngân sách.
           - Nếu lot > volume_max: Kẹp trần ở volume_max.
           - Hậu kiểm: lot * Loss_1lot <= RiskMoney.
        """
        if risk_pct is None:
            risk_pct = self.default_risk_pct

        try:
            if not math.isfinite(float(risk_pct)) or not 0 < float(risk_pct) <= 100 or not math.isfinite(float(sl_points)):
                return 0.0
        except (TypeError, ValueError):
            return 0.0
        account = mt5.account_info()
        info = mt5.symbol_info(symbol)

        if not account or not info:
            return 0.0

        # Lấy thông số kỹ thuật của sàn
        tick_size = getattr(info, "trade_tick_size", 0.0) or 0.0
        tick_value = getattr(info, "trade_tick_value", 0.0) or 0.0
        vol_min = getattr(info, "volume_min", 0.01)
        vol_max = getattr(info, "volume_max", 100.0)

        if tick_size <= 0 or tick_value <= 0 or sl_points <= 0:
            return 0.0 if reject_under_min else vol_min

        # Số tiền chấp nhận mất (Bằng đồng tiền cơ sở của tài khoản, vd: USD)
        risk_amount = account.balance * (risk_pct / 100.0)

        # Tính toán giá trị thua lỗ cho 1 Lot chuẩn
        loss_for_one_lot = (sl_points / tick_size) * tick_value

        if loss_for_one_lot <= 0 or math.isnan(loss_for_one_lot) or math.isinf(loss_for_one_lot):
            return 0.0 if reject_under_min else vol_min

        # Tính số Lot thô
        raw_lot = risk_amount / loss_for_one_lot
        if math.isnan(raw_lot) or math.isinf(raw_lot):
            return 0.0 if reject_under_min else vol_min

        # Chuẩn hoá số Lot theo quy định của sàn (Volume Step)
        step = getattr(info, "volume_step", 0.01)
        if not step or step <= 0:
            step = 0.01

        # Làm tròn xuống (floor) theo volume_step nhằm bảo đảm không bao giờ vượt ngân sách rủi ro
        lot = math.floor(raw_lot / step) * step

        # Kiểm tra ngưỡng tối thiểu volume_min
        if lot < vol_min:
            if reject_under_min:
                return 0.0
            lot = vol_min

        # Khoá số Lot không được lớn hơn Max
        lot = min(vol_max, lot)

        # Decimal quantization supports arbitrary broker steps without rounding risk upward.
        step_d = Decimal(str(step))
        lot_d = (Decimal(str(min(raw_lot, vol_max))) / step_d).to_integral_value(rounding=ROUND_FLOOR) * step_d
        lot = float(lot_d)
        if lot < vol_min:
            return 0.0
        if lot * loss_for_one_lot > risk_amount + 1e-6:
            lot = float(max(Decimal(0), lot_d-step_d))
        return lot if lot >= vol_min else 0.0
