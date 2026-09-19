"""
MODULE QUẢN TRỊ DỮ LIỆU & LƯU TRỮ PHI TẬP TRUNG
Đồ án Tốt nghiệp - Trường Đại học Giao thông vận tải TP.HCM (UTH)
Hệ thống: Quant AI V2.2 - Lưu trữ ngoài RAM để tối ưu hóa thiết bị 8GB
"""

import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger


class DatabaseManager:
    """
    Quản lý lưu trữ SQLite cục bộ, an toàn đa luồng (Thread-safe).
    Lưu vết toàn bộ Lịch sử lệnh, Biến động vốn (Equity Curve), và Trạng thái Bot.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DatabaseManager, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str = None):
        if getattr(self, "_initialized", False):
            if db_path is not None and db_path != self.db_path:
                self.db_path = db_path
                self._init_tables()
            return

        if db_path is None:
            base_dir = Path(__file__).resolve().parent
            db_path = str(base_dir / "quant_system.db")

        self.db_path = db_path
        self._db_lock = threading.Lock()
        self._init_tables()
        self._initialized = True
        logger.info(
            f"[DatabaseManager] Khởi tạo cơ sở dữ liệu SQLite thành công tại: {self.db_path}"
        )

    @classmethod
    def reset_instance(cls):
        with cls._lock:
            cls._instance = None

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        with self._db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 1. Bảng lưu trữ lệnh giao dịch
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    ticket INTEGER PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    volume REAL NOT NULL,
                    open_price REAL NOT NULL,
                    close_price REAL DEFAULT 0.0,
                    sl REAL DEFAULT 0.0,
                    tp REAL DEFAULT 0.0,
                    pnl REAL DEFAULT 0.0,
                    open_time TEXT NOT NULL,
                    close_time TEXT DEFAULT '',
                    status TEXT DEFAULT 'OPEN',
                    comment TEXT DEFAULT ''
                )
            """)

            # 2. Bảng lưu thông số biến động vốn (Equity Curve)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS account_equity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    balance REAL NOT NULL,
                    equity REAL NOT NULL,
                    margin REAL DEFAULT 0.0,
                    free_margin REAL DEFAULT 0.0,
                    drawdown_pct REAL DEFAULT 0.0
                )
            """)

            # 3. Bảng lưu trạng thái hệ thống phục vụ State Recovery
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            conn.commit()
            conn.close()

    def record_open_trade(
        self,
        ticket: int,
        symbol: str,
        order_type: str,
        volume: float,
        open_price: float,
        sl: float = 0.0,
        tp: float = 0.0,
        comment: str = "",
    ) -> bool:
        """Ghi nhận vị thế mới mở vào CSDL."""
        with self._db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO trades 
                    (ticket, symbol, order_type, volume, open_price, sl, tp, open_time, status, comment)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?)
                """,
                    (
                        ticket,
                        symbol,
                        order_type,
                        volume,
                        open_price,
                        sl,
                        tp,
                        now_str,
                        comment,
                    ),
                )
                conn.commit()
                return True
            except Exception as e:
                logger.error(f"[DatabaseManager] Lỗi lưu lệnh #{ticket}: {e}")
                return False
            finally:
                conn.close()

    def record_close_trade(self, ticket: int, close_price: float, pnl: float) -> bool:
        """Cập nhật trạng thái lệnh đã đóng vào CSDL."""
        with self._db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                cursor.execute(
                    """
                    UPDATE trades 
                    SET close_price = ?, pnl = ?, close_time = ?, status = 'CLOSED'
                    WHERE ticket = ?
                """,
                    (close_price, pnl, now_str, ticket),
                )
                conn.commit()
                return True
            except Exception as e:
                logger.error(f"[DatabaseManager] Lỗi cập nhật đóng lệnh #{ticket}: {e}")
                return False
            finally:
                conn.close()

    def get_open_trades(self, symbol: str = None) -> List[Dict[str, Any]]:
        """Lấy danh sách các vị thế đang mở từ CSDL."""
        with self._db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            if symbol:
                cursor.execute(
                    "SELECT * FROM trades WHERE status = 'OPEN' AND symbol = ?",
                    (symbol,),
                )
            else:
                cursor.execute("SELECT * FROM trades WHERE status = 'OPEN'")
            rows = cursor.fetchall()
            trades = [dict(row) for row in rows]
            conn.close()
            return trades

    def record_equity_snapshot(
        self,
        balance: float,
        equity: float,
        margin: float = 0.0,
        free_margin: float = 0.0,
        drawdown_pct: float = 0.0,
    ):
        """Ghi nhận snapshot biến động vốn phục vụ vẽ biểu đồ và phân tích Drawdown."""
        with self._db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                cursor.execute(
                    """
                    INSERT INTO account_equity (timestamp, balance, equity, margin, free_margin, drawdown_pct)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (now_str, balance, equity, margin, free_margin, drawdown_pct),
                )
                conn.commit()
            except Exception as e:
                logger.error(f"[DatabaseManager] Lỗi lưu equity snapshot: {e}")
            finally:
                conn.close()

    def set_system_state(self, key: str, value: str):
        """Lưu trữ một biến trạng thái hệ thống vào DB."""
        with self._db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO system_state (key, value, updated_at)
                    VALUES (?, ?, ?)
                """,
                    (key, value, now_str),
                )
                conn.commit()
            except Exception as e:
                logger.error(f"[DatabaseManager] Lỗi set state {key}: {e}")
            finally:
                conn.close()

    def get_system_state(self, key: str, default: str = None) -> Optional[str]:
        """Đọc biến trạng thái hệ thống."""
        with self._db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM system_state WHERE key = ?", (key,))
            row = cursor.fetchone()
            conn.close()
            return row["value"] if row else default
