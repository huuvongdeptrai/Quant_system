"""
MODULE GIÁM SÁT KẾT NỐI & TỰ ĐỘNG PHỤC HỒI (MT5 WATCHDOG & HEARTBEAT)
Đồ án Tốt nghiệp - Trường Đại học Giao thông vận tải TP.HCM (UTH)
Hệ thống: Quant AI V2.2 - Tự động phát hiện đứt mạng và tái kết nối MT5
"""

import time
import threading
from typing import Callable, Optional
from loguru import logger
from backend.infrastructure.brokers.mt5_safe import mt5


class MT5Watchdog:
    """
    Vòng lặp giám sát nhịp tim (Heartbeat) của Broker MT5:
    - Định kỳ kiểm tra kết nối với máy chủ sàn.
    - Tự động tái thiết lập kết nối (Auto-Reconnect) khi mạng chập chờn.
    - Kích hoạt callback thông báo khi có sự cố mạng.
    """

    def __init__(self, check_interval_sec: float = 5.0, max_reconnect_retries: int = 5):
        self.check_interval_sec = check_interval_sec
        self.max_reconnect_retries = max_reconnect_retries
        self._is_running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_heartbeat = 0.0
        self._connected = False
        self._on_disconnect_callback: Optional[Callable] = None
        self._on_reconnect_callback: Optional[Callable] = None

    def _try_auto_login(self):
        try:
            import os, json
            from pathlib import Path
            root_d = Path(__file__).resolve().parents[2]
            cfg_p = root_d / "config" / "ai_config.json"
            if cfg_p.exists():
                with open(cfg_p, "r", encoding="utf-8") as f:
                    cfg_data = json.load(f)
                srv = cfg_data.get("MT5_SERVER")
                acc_num = cfg_data.get("MT5_ACCOUNT")
                pwd_enc = cfg_data.get("MT5_PASSWORD")
                from backend.core.security_guard import decrypt_secret
                pwd_dec = decrypt_secret(pwd_enc) if pwd_enc else None
                if srv and acc_num and pwd_dec:
                    mt5.login(int(acc_num), password=pwd_dec, server=srv)
        except Exception as e:
            logger.debug(f"[Watchdog] Auto-login fallback error: {e}")

    def check_health(self) -> bool:
        """Kiểm tra tức thời tình trạng kết nối tới MT5."""
        term_info = mt5.terminal_info()
        acc_info = mt5.account_info()

        if term_info is None or acc_info is None:
            self._connected = False
            return False

        # Kiểm tra cờ connected từ terminal_info
        if hasattr(term_info, "connected") and not term_info.connected:
            self._connected = False
            return False

        self._connected = True
        self._last_heartbeat = time.time()
        return True

    def attempt_reconnect(self) -> bool:
        """Thực hiện tái kết nối tự động với Exponential Backoff."""
        logger.warning(
            "[Watchdog] Phát hiện mất kết nối tới máy chủ MT5! Đang tiến hành tái kết nối..."
        )
        if self._on_disconnect_callback:
            try:
                self._on_disconnect_callback()
            except Exception as e:
                logger.error(f"[Watchdog] Lỗi khi gọi on_disconnect_callback: {e}")

        for attempt in range(1, self.max_reconnect_retries + 1):
            delay = min(2 ** (attempt - 1), 10)
            logger.info(
                f"[Watchdog] Thử kết nối lại lần {attempt}/{self.max_reconnect_retries} (Chờ {delay}s)..."
            )
            if self._stop_event.wait(delay):
                return False

            try:
                mt5.shutdown()
                if mt5.initialize():
                    if mt5.account_info() is None:
                        self._try_auto_login()
                    if self.check_health():
                        logger.info(
                            f"[Watchdog] TÁI KẾT NỐI THÀNH CÔNG ở lần thử thứ {attempt}!"
                        )
                        if self._on_reconnect_callback:
                            try:
                                self._on_reconnect_callback()
                            except Exception as e:
                                logger.error(
                                    f"[Watchdog] Lỗi khi gọi on_reconnect_callback: {e}"
                                )
                        return True
            except Exception as e:
                logger.error(f"[Watchdog] Ngoại lệ khi thử kết nối lại: {e}")

        logger.critical(
            f"[Watchdog] THẤT BẠI: Đã thử {self.max_reconnect_retries} lần nhưng không thể kết nối lại MT5!"
        )
        return False

    def start(self):
        """Khởi chạy luồng giám sát ngầm."""
        if self._is_running:
            return
        self._stop_event.clear()
        self._is_running = True
        self._thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="MT5_Watchdog_Thread"
        )
        self._thread.start()
        logger.info("[Watchdog] Luồng giám sát nhịp tim MT5 đã kích hoạt.")

    def stop(self):
        """Dừng luồng giám sát."""
        self._is_running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("[Watchdog] Đã dừng luồng giám sát nhịp tim.")

    def _monitor_loop(self):
        while self._is_running:
            if not self.check_health():
                self.attempt_reconnect()
            self._stop_event.wait(self.check_interval_sec)

    @property
    def is_connected(self) -> bool:
        return self._connected
