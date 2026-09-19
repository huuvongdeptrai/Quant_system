"""
GIAI ĐOẠN 1: UNIT TESTING (KIỂM ĐỊNH TOÁN HỌC & THUẬT TOÁN)
Đồ án Tốt nghiệp - Trường Đại học Giao thông vận tải TP.HCM (UTH)
Hệ thống: Quant AI V2.2 - Lõi 3 (Decision Gate, SR Calculator) & Lõi 4 (Risk/Execution)
"""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from infrastructure.ai_engines.ai.sr_calculator import calculate_sr_levels
from infrastructure.ai_engines.ai.decision_gate import DecisionGate
from core.risk_manager import RiskManager
from infrastructure.brokers.mt5_safe import mt5


def generate_mock_candles(
    n=150, base_price=2000.0, trend=0.0, noise=2.0, base_vol=1000.0
):
    rates = []
    curr = base_price
    for i in range(n):
        curr += trend + np.random.uniform(-noise, noise)
        high = curr + np.random.uniform(0.5, 3.0)
        low = curr - np.random.uniform(0.5, 3.0)
        close = np.random.uniform(low, high)
        vol = base_vol + np.random.uniform(-100, 100)
        rates.append((i * 3600, curr, high, low, close, vol, 0, 0))

    dtype = [
        ("time", "<i8"),
        ("open", "<f8"),
        ("high", "<f8"),
        ("low", "<f8"),
        ("close", "<f8"),
        ("tick_volume", "<f8"),
        ("spread", "<i4"),
        ("real_volume", "<i8"),
    ]
    return np.array(rates, dtype=dtype)


class TestStage1UnitMath:
    def test_mathematical_invariants(self):
        rates = generate_mock_candles(n=150, base_price=2300.0, trend=0.1)
        curr_price = float(rates[-1]["close"])
        res = calculate_sr_levels(
            rates, current_price=curr_price, n_bars=8, atr_buffer_mult=0.5
        )

        assert res is not None
        assert res["support"] < curr_price
        assert res["resistance"] > curr_price
        assert abs(res["range"] - (res["resistance"] - res["support"])) <= 0.02
        assert res["dist_to_res"] > 0
        assert res["dist_to_sup"] > 0

    def test_fake_breakout_volume_rejection(self):
        rates = generate_mock_candles(
            n=150, base_price=2000.0, noise=1.5, base_vol=1000.0
        )
        rates[100]["high"] = 2050.0
        rates[100]["tick_volume"] = 600.0

        curr_price = 2010.0
        res = calculate_sr_levels(
            rates, current_price=curr_price, n_bars=8, atr_buffer_mult=0.5
        )
        assert res["resistance"] <= 2050.0

    def test_edge_case_liquidity_shock_gap(self):
        rates = generate_mock_candles(n=150, base_price=2000.0)
        rates[-2]["close"] = 2000.0
        rates[-1]["open"] = 2035.0
        rates[-1]["high"] = 2045.0
        rates[-1]["low"] = 2030.0
        rates[-1]["close"] = 2040.0
        rates[-1]["tick_volume"] = 8000.0

        curr_price = float(rates[-1]["close"])
        res = calculate_sr_levels(
            rates, current_price=curr_price, n_bars=8, atr_buffer_mult=0.5
        )

        assert res is not None
        assert res["atr"] > 2.0
        assert res["support"] < curr_price
        assert res["resistance"] > curr_price
        assert (
            res["dist_to_res"] >= 0.5 * res["atr"]
            or res["dist_to_sup"] >= 0.5 * res["atr"]
        )

    def test_htf_atr_envelope_sideway_detection(self):
        gate = DecisionGate()
        flat_rates = generate_mock_candles(
            n=100, base_price=2000.0, trend=0.0, noise=0.5
        )
        closes = [r["close"] for r in flat_rates]
        ema50 = gate._ema(closes, 50)
        flat_rates[-1]["close"] = ema50

        bias_neutral = gate._get_htf_bias(
            "XAUUSD", d1_rates=flat_rates, h4_rates=flat_rates
        )
        assert bias_neutral == "NEUTRAL"

    def test_htf_multi_timeframe_matrix_divergence(self):
        gate = DecisionGate()
        d1_rates = generate_mock_candles(n=100, base_price=2000.0, trend=0.5)
        d1_rates[-1]["close"] = 2100.0

        h4_rates = generate_mock_candles(n=100, base_price=2000.0, trend=-0.5)
        h4_rates[-1]["close"] = 1900.0

        bias = gate._get_htf_bias("XAUUSD", d1_rates=d1_rates, h4_rates=h4_rates)
        assert bias == "NEUTRAL"

    def test_risk_manager_edge_cases_zero_division(self):
        """
        KIỂM THỬ BIÊN QUẢN TRỊ RỦI RO (EDGE-CASE ZERO DIVISION GUARD):
        1. sl_points = 0.0 -> Khóa an toàn, trả về volume_min, không gây ZeroDivisionError.
        2. tick_size = 0.0 hoặc tick_value = 0.0 -> Trả về volume_min an toàn.
        3. Rủi ro cực lớn hoặc cực nhỏ -> Tự động kẹp trong dải [volume_min, volume_max].
        """
        rm = RiskManager(default_risk_pct=1.0)

        mock_acc = MagicMock(balance=100000.0)
        mock_info = MagicMock(
            trade_tick_size=0.01,
            trade_tick_value=1.0,
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
        )

        with patch.object(mt5, "account_info", return_value=mock_acc), patch.object(
            mt5, "symbol_info", return_value=mock_info
        ):

            # Case 1: SL = 0.0 (Lỗi người dùng nhập SL trùng Entry)
            lot_zero_sl = rm.calculate_lot_size("XAUUSD", sl_points=0.0)
            assert (
                lot_zero_sl == 0.01
            ), f"SL=0 phải trả về volume_min, nhận được: {lot_zero_sl}"

            # Case 2: Sàn lỗi trả về tick_size = 0
            mock_info.trade_tick_size = 0.0
            lot_zero_tick = rm.calculate_lot_size("XAUUSD", sl_points=5.0)
            assert lot_zero_tick == 0.01, "tick_size=0 phải trả về volume_min an toàn"

            # Case 3: Rủi ro vượt trần (Calculated Lot > volume_max)
            mock_info.trade_tick_size = 0.01
            mock_acc.balance = 100_000_000.0  # Vốn 100 triệu USD
            lot_max_clamped = rm.calculate_lot_size("XAUUSD", sl_points=0.1)
            assert (
                lot_max_clamped == 100.0
            ), f"Lot phải được kẹp tại volume_max=100, nhận được: {lot_max_clamped}"
