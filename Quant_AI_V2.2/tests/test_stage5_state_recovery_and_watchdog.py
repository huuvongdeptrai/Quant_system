"""
GIAI ĐOẠN 5: STATE RECOVERY & WATCHDOG RESILIENCE (QUẢN TRỊ DỮ LIỆU & PHỤC HỒI TRẠNG THÁI)
Đồ án Tốt nghiệp - Trường Đại học Giao thông vận tải TP.HCM (UTH)
Hệ thống: Quant AI V2.2 - Kiểm định Phục hồi sau sự cố & Vòng lặp giám sát Heartbeat
"""

import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from backend.database.db_manager import DatabaseManager
from backend.core.state_recovery import StateRecoveryManager
from backend.core.watchdog import MT5Watchdog
from backend.infrastructure.brokers.mt5_safe import mt5


class TestStage5StateRecoveryAndWatchdog:
    def setup_method(self):
        DatabaseManager.reset_instance()

    def teardown_method(self):
        DatabaseManager.reset_instance()

    def test_database_manager_crud(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_db_path = os.path.join(tmpdir, "test_quant.db")
            db = DatabaseManager(db_path=test_db_path)

            ok = db.record_open_trade(
                ticket=888888,
                symbol="XAUUSD",
                order_type="BUY",
                volume=0.1,
                open_price=2300.0,
                sl=2290.0,
                tp=2325.0,
                comment="Unit_Test",
            )
            assert ok is True

            open_trades = db.get_open_trades("XAUUSD")
            assert len(open_trades) == 1
            assert open_trades[0]["ticket"] == 888888
            assert open_trades[0]["status"] == "OPEN"

            ok_close = db.record_close_trade(
                ticket=888888, close_price=2325.0, pnl=250.0
            )
            assert ok_close is True
            assert len(db.get_open_trades("XAUUSD")) == 0

            db.record_equity_snapshot(
                balance=100000.0, equity=100250.0, drawdown_pct=0.0
            )
            db.set_system_state("circuit_breaker_active", "False")
            assert db.get_system_state("circuit_breaker_active") == "False"

    def test_state_recovery_reconcile_on_crash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_db_path = os.path.join(tmpdir, "test_recovery.db")
            db = DatabaseManager(db_path=test_db_path)
            recovery_mgr = StateRecoveryManager(db_manager=db)

            # Trong DB có lệnh #111111 (đang ghi OPEN)
            db.record_open_trade(
                ticket=111111,
                symbol="XAUUSD",
                order_type="BUY",
                volume=0.05,
                open_price=2200.0,
            )

            # Trên MT5: có lệnh mồ côi #222222, lệnh #111111 đã hit TP
            mock_pos_222 = MagicMock(
                ticket=222222,
                symbol="XAUUSD",
                type=mt5.ORDER_TYPE_BUY,
                volume=0.1,
                price_open=2305.0,
                sl=2295.0,
                tp=2330.0,
                time=1700000000,
                magic=1002,
            )

            # Giả lập Deal đóng cho lệnh #111111
            mock_deal_111 = MagicMock(
                ticket=999,
                order=111111,
                position_id=111111,
                time=1700000100,
                time_msc=1700000100000,
                entry=1,  # DEAL_ENTRY_OUT
                price=2215.0,
                profit=75.0,
                commission=-1.5,
                swap=0.0,
                fee=0.0,
            )

            with patch.object(
                mt5, "positions_get", return_value=[mock_pos_222]
            ), patch.object(
                mt5, "history_deals_get", return_value=[mock_deal_111]
            ):
                summary = recovery_mgr.reconcile_on_startup()

                assert summary["status"] == "SUCCESS"
                assert (
                    summary["recovered_orphans"] == 1
                ), "Phải phục hồi 1 lệnh mồ côi #222222"
                assert summary["reconciled_closed"] == 1, "Phải đóng 1 lệnh ma #111111"

                open_trades = db.get_open_trades("XAUUSD")
                assert len(open_trades) == 1
                assert open_trades[0]["ticket"] == 222222

                can_open = recovery_mgr.can_open_new_trade("XAUUSD")
                assert (
                    can_open is False
                ), "Không được phép mở lệnh mới khi XAUUSD đang có vị thế chạy!"

    def test_state_recovery_api_error_protection(self):
        """Kiểm tra an toàn: Khi positions_get() trả về None (mất kết nối API), dừng đối soát để bảo vệ CSDL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_db_path = os.path.join(tmpdir, "test_recovery_err.db")
            db = DatabaseManager(db_path=test_db_path)
            recovery_mgr = StateRecoveryManager(db_manager=db)

            # Lệnh #333333 đang OPEN trong CSDL
            db.record_open_trade(
                ticket=333333,
                symbol="XAUUSD",
                order_type="BUY",
                volume=0.1,
                open_price=2400.0,
            )

            with patch.object(mt5, "positions_get", return_value=None), patch.object(
                mt5, "last_error", return_value=(10004, "No connection to trade server")
            ):
                summary = recovery_mgr.reconcile_on_startup()

                assert summary["status"] == "FAILED_API_ERROR"
                assert summary["reconciled_closed"] == 0

                # Lệnh #333333 trong CSDL phải được giữ nguyên trạng thái OPEN, không được xóa nhầm!
                open_trades = db.get_open_trades("XAUUSD")
                assert len(open_trades) == 1
                assert open_trades[0]["ticket"] == 333333
                assert open_trades[0]["status"] == "OPEN"

    def test_state_recovery_missing_deals_protection(self):
        """Kiểm tra an toàn: Khi vị thế không còn trên MT5 nhưng không tìm thấy deals, KHÔNG được ghi đè 0/0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_db_path = os.path.join(tmpdir, "test_missing_deals.db")
            db = DatabaseManager(db_path=test_db_path)
            recovery_mgr = StateRecoveryManager(db_manager=db)

            db.record_open_trade(
                ticket=444444,
                symbol="XAUUSD",
                order_type="BUY",
                volume=0.2,
                open_price=2500.0,
            )

            # Sàn báo không còn vị thế, nhưng tra cứu history_deals_get trả về None / rỗng
            with patch.object(
                mt5, "positions_get", return_value=[]
            ), patch.object(
                mt5, "history_deals_get", return_value=None
            ):
                summary = recovery_mgr.reconcile_on_startup()

                # Không được tính là đóng thành công vì chưa rõ kết quả
                assert summary["reconciled_closed"] == 0

                # Lệnh vẫn giữ nguyên trong CSDL
                open_trades = db.get_open_trades("XAUUSD")
                assert len(open_trades) == 1
                assert open_trades[0]["ticket"] == 444444
                assert open_trades[0]["status"] == "OPEN"

                # Có cờ cảnh báo trong system_state
                state_val = db.get_system_state("unreconciled_trade_444444")
                assert state_val == "MISSING_DEALS_FROM_BROKER"

    def test_mt5_watchdog_heartbeat_and_reconnect(self):
        watchdog = MT5Watchdog(check_interval_sec=1.0, max_reconnect_retries=2)

        # Test 1: Kiểm tra kết nối bình thường với mock
        mock_term = MagicMock(connected=True)
        mock_acc = MagicMock(login=123456)
        with patch.object(mt5, "terminal_info", return_value=mock_term), patch.object(
            mt5, "account_info", return_value=mock_acc
        ):
            is_healthy = watchdog.check_health()
            assert is_healthy is True
            assert watchdog.is_connected is True

        # Test 2: Mô phỏng đứt kết nối mạng
        mock_disconnected_term = MagicMock(connected=False)
        with patch.object(mt5, "terminal_info", return_value=mock_disconnected_term):
            is_healthy_fail = watchdog.check_health()
            assert is_healthy_fail is False
            assert watchdog.is_connected is False
