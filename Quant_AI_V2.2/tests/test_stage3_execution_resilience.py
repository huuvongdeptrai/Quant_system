"""
GIAI ĐOẠN 3: FORWARD TESTING & EXECUTION RESILIENCE (SÁT HẠCH MÔI TRƯỜNG THỰC)
Đồ án Tốt nghiệp - Trường Đại học Giao thông vận tải TP.HCM (UTH)
Hệ thống: Quant AI V2.2 - Kiểm định Độ trễ (Latency Logging) & Khả năng Chịu lỗi Sàn (Requote/Exceptions)
"""

import time
import pytest
from unittest.mock import MagicMock, patch
from infrastructure.brokers.execution_manager import ExecutionManager
from infrastructure.brokers.mt5_safe import mt5


class TestStage3ExecutionResilience:
    """Kiểm thử độ trễ và khả năng phục hồi khi sàn từ chối lệnh / requote."""

    def test_live_broker_ping_and_order_check_latency(self):
        """
        ĐO LƯỜNG ĐỘ TRỄ KẾT NỐI SÀN (LIVE LATENCY LOGGING):
        Kiểm tra thời gian ping và phản hồi của Broker qua hàm order_check().
        Tiêu chuẩn: Độ trễ phản hồi sàn bắt buộc phải < 500 ms.
        """
        assert mt5.initialize(), "Không thể kết nối MT5 Broker"

        symbol = "XAUUSD"
        mt5.symbol_select(symbol, True)
        tick = mt5.symbol_info_tick(symbol)
        assert tick is not None, f"Không lấy được giá tick của {symbol}"

        # Kiểm tra độ trễ kiểm tra lệnh (Order Check Latency)
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": 0.01,
            "type": mt5.ORDER_TYPE_BUY,
            "price": tick.ask,
            "sl": tick.ask - 5.0,
            "tp": tick.ask + 10.0,
            "deviation": 20,
            "magic": 999999,
            "comment": "Latency_Benchmark",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        start = time.perf_counter()
        check_res = mt5.order_check(req)
        end = time.perf_counter()
        latency_ms = (end - start) * 1000.0

        print(
            f"\n[Broker Latency Benchmark] MT5 order_check latency: {latency_ms:.2f} ms"
        )
        assert check_res is not None, "order_check trả về None"
        assert (
            latency_ms < 500.0
        ), f"Độ trễ sàn {latency_ms:.2f} ms vượt ngưỡng tiêu chuẩn (< 500 ms)"

    def test_requote_auto_retry_mechanism(self):
        """
        MÔ PHỎNG LỖI REQUOTE (MÃ 10004 - TRƯỢT GIÁ GIỜ RA TIN):
        Khi sàn báo Requote ở 2 lần đầu và thành công ở lần thứ 3:
        Kỳ vọng: ExecutionManager tự động thử lại (Retry) mà không bị crash hay treo vòng lặp.
        """
        exec_mgr = ExecutionManager(magic_number=999999, slippage=20)

        # Mock kết quả trả về: 2 lần đầu Requote (10004), lần 3 thành công (10009)
        res_requote = MagicMock(retcode=mt5.TRADE_RETCODE_REQUOTE, comment="Requote")
        res_success = MagicMock(
            retcode=mt5.TRADE_RETCODE_DONE, comment="Done", order=12345678
        )

        mock_responses = [res_requote, res_requote, res_success]

        with patch.object(mt5, "order_send", side_effect=mock_responses):
            result = exec_mgr.execute_market_order(
                "XAUUSD",
                is_buy=True,
                volume=0.01,
                sl_price=2000.0,
                tp_price=2050.0,
                max_retries=3,
            )

            assert result["status"] == "success"
            assert result["ticket"] == 12345678
            assert (
                result["retries"] == 2
            ), f"Phải sử dụng 2 lần retry, nhận được: {result['retries']}"
            assert result["latency_ms"] > 0

    def test_fatal_rejection_fail_fast(self):
        """
        MÔ PHỎNG LỖI BẤT KHẢ KHÁNG (MÃ 10018 - THỊ TRƯỜNG ĐÃ ĐÓNG CỬA):
        Kỳ vọng: Hệ thống fail-fast ngay lập tức (không retry vô ích gây lag máy),
        trả về thông báo lỗi có cấu trúc.
        """
        exec_mgr = ExecutionManager(magic_number=999999, slippage=20)
        res_market_closed = MagicMock(
            retcode=mt5.TRADE_RETCODE_MARKET_CLOSED, comment="Market closed"
        )

        with patch.object(mt5, "order_send", return_value=res_market_closed):
            result = exec_mgr.execute_market_order(
                "XAUUSD",
                is_buy=True,
                volume=0.01,
                sl_price=2000.0,
                tp_price=2050.0,
                max_retries=3,
            )

            assert result["status"] == "error"
            assert result["retcode"] == mt5.TRADE_RETCODE_MARKET_CLOSED
            assert (
                result["retries"] == 0
            ), "Lỗi đóng cửa thị trường không được phép retry lãng phí tài nguyên"
