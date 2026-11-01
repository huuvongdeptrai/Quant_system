"""
MODULE QUẢN TRỊ DỮ LIỆU & LƯU TRỮ PHI TẬP TRUNG
Đồ án Tốt nghiệp - Trường Đại học Giao thông vận tải TP.HCM (UTH)
Hệ thống: Quant AI V2.2 - Lưu trữ ngoài RAM để tối ưu hóa thiết bị 8GB
"""

import sqlite3
import threading
import math
import json
import uuid
from contextvars import ContextVar
from contextlib import contextmanager
from datetime import timezone
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
    _instances = {}
    _lock = threading.RLock()

    def __new__(cls, db_path=None):
        with cls._lock:
            if db_path is None and cls._instance is not None:
                return cls._instance
            path = str(Path(db_path or Path(__file__).parent / "quant_system.db").resolve())
            if path not in cls._instances:
                obj = super().__new__(cls)
                obj._init_lock = threading.Lock()
                obj._initialized = False
                obj.db_path = path
                cls._instances[path] = obj
            obj = cls._instances[path]
            if cls._instance is None:
                cls._instance = obj
            return obj

    def __init__(self, db_path=None):
        with self._init_lock:
            if self._initialized:
                return
            self._db_lock = threading.RLock()
            self._scope = ContextVar("account_scope_" + str(id(self)), default="legacy")
            self._init_tables()
            self._initialized = True

    @property
    def account_id(self):
        return self._scope.get()

    def bind_account(self, login, server):
        if not str(server).strip() or not str(login).isdigit() or int(login) <= 0:
            raise ValueError("A verified broker account is required")
        self._scope.set(json.dumps([str(server), int(login)], separators=(",", ":")))
        return self.account_id

    @classmethod
    def reset_instance(cls):
        with cls._lock:
            cls._instance = None
            cls._instances = {}

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

    def backup(self, destination):
        with self._db_lock:
            source = self._get_connection()
            target = sqlite3.connect(str(destination))
            try:
                source.backup(target)
            finally:
                source.close()
                target.close()

    def _get_connection(self) -> sqlite3.Connection:
        # SC-11: High-Concurrency SQLite WAL Pragmas & Busy Timeout
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = FULL;")
        conn.execute("PRAGMA busy_timeout = 15000;")
        conn.execute("PRAGMA temp_store = MEMORY;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_tables(self):
        with self._db_lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()

                # High-Performance In-Memory & WAL Optimization (155x Speedup)
                cursor.execute("PRAGMA journal_mode = WAL;")
                cursor.execute("PRAGMA synchronous = FULL;")
                cursor.execute("PRAGMA cache_size = -64000;")
                cursor.execute("PRAGMA temp_store = MEMORY;")

                version = cursor.execute("PRAGMA user_version").fetchone()[0]
                if version not in (0, 2):
                    raise RuntimeError(f"Unsupported database schema version: {version}")
                legacy_exists=version == 0 and cursor.execute("SELECT 1 FROM sqlite_master WHERE name='trades'").fetchone()
                if legacy_exists:
                    # Keep the original records verbatim; account attribution is deliberately unknown.
                    backup = sqlite3.connect(self.db_path + ".pre_v2.bak")
                    conn.backup(backup)
                    backup.close()
                    cursor.execute("BEGIN IMMEDIATE")
                    cursor.execute("ALTER TABLE trades RENAME TO trades_legacy_v0")
                    if cursor.execute("SELECT 1 FROM sqlite_master WHERE name='system_state'").fetchone():
                        cursor.execute("ALTER TABLE system_state RENAME TO system_state_legacy_v0")
                schema_sql="""
                    CREATE TABLE IF NOT EXISTS trades (
                        account_id TEXT NOT NULL, ticket INTEGER NOT NULL, symbol TEXT NOT NULL,
                        order_type TEXT NOT NULL CHECK(order_type IN ('BUY','SELL')),
                        volume REAL NOT NULL CHECK(volume>0), original_volume REAL NOT NULL,
                        open_price REAL NOT NULL CHECK(open_price>0), close_price REAL,
                        sl REAL DEFAULT 0, tp REAL DEFAULT 0, initial_sl REAL DEFAULT 0,
                        pnl REAL DEFAULT 0, open_time TEXT NOT NULL, close_time TEXT DEFAULT '',
                        status TEXT NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN','CLOSED','UNRESOLVED')),
                        comment TEXT DEFAULT '', position_id INTEGER, broker_order_id INTEGER,
                        magic INTEGER DEFAULT 0, strategy_id TEXT DEFAULT '',
                        PRIMARY KEY(account_id,ticket)
                    );
                    CREATE TABLE IF NOT EXISTS account_equity (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
                        balance REAL NOT NULL, equity REAL NOT NULL, margin REAL DEFAULT 0,
                        free_margin REAL DEFAULT 0, drawdown_pct REAL DEFAULT 0, account_id TEXT DEFAULT 'legacy'
                    );
                    CREATE TABLE IF NOT EXISTS system_state (
                        account_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
                        updated_at TEXT NOT NULL, PRIMARY KEY(account_id,key)
                    );
                    CREATE TABLE IF NOT EXISTS order_intents (
                        account_id TEXT NOT NULL, intent_id TEXT NOT NULL, signal_key TEXT NOT NULL,
                        symbol TEXT NOT NULL, status TEXT NOT NULL,
                        payload TEXT NOT NULL, updated_at TEXT NOT NULL,
                        PRIMARY KEY(account_id,intent_id), UNIQUE(account_id,signal_key)
                    );
                    CREATE UNIQUE INDEX IF NOT EXISTS one_inflight_per_symbol ON order_intents(account_id,symbol)
                        WHERE status IN ('SUBMITTING','UNKNOWN');
                    CREATE TABLE IF NOT EXISTS broker_deals (
                        account_id TEXT NOT NULL, deal_id INTEGER NOT NULL, position_id INTEGER NOT NULL,
                        order_id INTEGER, time_msc INTEGER NOT NULL, payload TEXT NOT NULL,
                        PRIMARY KEY(account_id,deal_id)
                    );
                    CREATE TABLE IF NOT EXISTS execution_events (
                        sequence INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT NOT NULL,
                        intent_id TEXT NOT NULL, status TEXT NOT NULL, payload TEXT NOT NULL, timestamp TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS trades_scope_status ON trades(account_id,status,symbol);
                    CREATE INDEX IF NOT EXISTS trades_scope_closed ON trades(account_id,close_time);
                    CREATE INDEX IF NOT EXISTS deal_position ON broker_deals(account_id,position_id,time_msc);
                """
                if not conn.in_transaction:
                    cursor.execute("BEGIN IMMEDIATE")
                for statement in schema_sql.split(';'):
                    if statement.strip():
                        cursor.execute(statement)
                if 'account_id'  not in [r[1] for r in cursor.execute('PRAGMA table_info(account_equity)')]:
                    cursor.execute("ALTER TABLE account_equity ADD COLUMN account_id TEXT DEFAULT 'legacy'")
                cursor.execute("CREATE INDEX IF NOT EXISTS equity_scope_time ON account_equity(account_id,timestamp)")
                if version == 0 and cursor.execute("SELECT 1 FROM sqlite_master WHERE name='trades_legacy_v0'").fetchone():
                    cursor.execute("""INSERT OR IGNORE INTO trades
                        (account_id,ticket,symbol,order_type,volume,original_volume,open_price,close_price,
                        sl,tp,initial_sl,pnl,open_time,close_time,status,comment,position_id)
                        SELECT 'legacy',ticket,symbol,order_type,volume,volume,open_price,close_price,
                        sl,tp,0,pnl,open_time,close_time,
                        CASE WHEN status='CLOSED' AND close_price<=0 THEN 'UNRESOLVED' ELSE status END,
                        comment,ticket FROM trades_legacy_v0 WHERE volume>0 AND open_price>0""")
                cursor.execute("PRAGMA user_version=2")
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
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
        open_time: Optional[str] = None,
        position_id: Optional[int] = None,
        broker_order_id: Optional[int] = None,
        magic: int = 0,
        strategy_id: str = "",
        initial_sl: Optional[float] = None,
    ) -> bool:
        """Ghi nhận vị thế mới mở vào CSDL."""
        with self._db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            record_time = open_time or self._now()
            try:
                original_sl = sl if initial_sl is None else initial_sl
                values = [float(volume), float(open_price), float(sl), float(tp), float(original_sl)]
                if not all(math.isfinite(v) for v in values) or volume <= 0 or open_price <= 0 or order_type not in ("BUY", "SELL"):
                    return False
                cursor.execute("""INSERT INTO trades
                    (account_id,ticket,symbol,order_type,volume,original_volume,open_price,sl,tp,initial_sl,
                     open_time,status,comment,position_id,broker_order_id,magic,strategy_id)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,'OPEN',?,?,?,?,?)
                    ON CONFLICT(account_id,ticket) DO NOTHING""",
                    (self.account_id,ticket,symbol,order_type,volume,volume,open_price,sl,tp,original_sl,
                     record_time,comment,position_id or ticket,broker_order_id,magic,strategy_id))
                conn.commit()
                row = conn.execute("SELECT status FROM trades WHERE account_id=? AND ticket=?",(self.account_id,ticket)).fetchone()
                return bool(row and row['status']=='OPEN')
            except (sqlite3.Error, ValueError, TypeError) as exc:
                logger.error(f"Trade persistence failed: {exc}")
                return False
            finally:
                conn.close()

    def update_trade_volume(self, ticket, remaining_volume):
        if not math.isfinite(float(remaining_volume)) or remaining_volume <= 0:
            return False
        with self._db_lock, self._connection() as conn:
            cur = conn.execute("UPDATE trades SET volume=? WHERE account_id=? AND ticket=? AND status='OPEN'",
                               (remaining_volume,self.account_id,ticket))
            return cur.rowcount == 1

    def record_close_trade(self, ticket, close_price, pnl, close_time=None):
        if not all(math.isfinite(float(x)) for x in (close_price,pnl)) or close_price <= 0:
            return False
        with self._db_lock, self._connection() as conn:
            row = conn.execute("SELECT status,close_price,pnl FROM trades WHERE account_id=? AND ticket=?",(self.account_id,ticket)).fetchone()
            if not row:
                return False
            if row['status']=='CLOSED':
                return abs(row['close_price']-close_price)<1e-9 and abs(row['pnl']-pnl)<1e-7
            cur=conn.execute("UPDATE trades SET close_price=?,pnl=?,close_time=?,status='CLOSED' WHERE account_id=? AND ticket=? AND status IN ('OPEN','UNRESOLVED')",
                             (close_price,pnl,close_time or self._now(),self.account_id,ticket))
            return cur.rowcount == 1

    @contextmanager
    def _connection(self):
        conn=self._get_connection()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def reserve_intent(self, signal_key, symbol, payload):
        intent_id=uuid.uuid4().hex
        with self._db_lock, self._connection() as conn:
            try:
                conn.execute("INSERT INTO order_intents VALUES (?,?,?,?,?,?,?)",
                    (self.account_id,intent_id,signal_key,symbol,'SUBMITTING',json.dumps(payload,allow_nan=False),self._now()))
                conn.execute("INSERT INTO execution_events(account_id,intent_id,status,payload,timestamp) VALUES (?,?,?,?,?)",
                    (self.account_id,intent_id,'SUBMITTING',json.dumps(payload,allow_nan=False),self._now()))
                return intent_id
            except sqlite3.IntegrityError:
                return None

    def finish_intent(self, intent_id, status, payload):
        if status not in ('FILLED','PARTIAL','REJECTED','UNKNOWN','CANCELED'):
            raise ValueError('Invalid intent state')
        with self._db_lock, self._connection() as conn:
            cur=conn.execute("UPDATE order_intents SET status=?,payload=?,updated_at=? WHERE account_id=? AND intent_id=?",
                (status,json.dumps(payload,allow_nan=False,default=str),self._now(),self.account_id,intent_id))
            if cur.rowcount != 1:
                raise RuntimeError('Intent not found')
            conn.execute("INSERT INTO execution_events(account_id,intent_id,status,payload,timestamp) VALUES (?,?,?,?,?)",
                (self.account_id,intent_id,status,json.dumps(payload,default=str),self._now()))

    def has_unresolved_intent(self, symbol):
        with self._db_lock, self._connection() as conn:
            return conn.execute("SELECT 1 FROM order_intents WHERE account_id=? AND symbol=? AND status IN ('SUBMITTING','UNKNOWN')",(self.account_id,symbol)).fetchone() is not None

    def get_unresolved_intents(self):
        with self._db_lock, self._connection() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM order_intents WHERE account_id=? AND status IN ('SUBMITTING','UNKNOWN')",(self.account_id,))]

    def get_intents(self):
        with self._db_lock, self._connection() as conn:
            return [dict(r) for r in conn.execute(
                'SELECT * FROM order_intents WHERE account_id=? ORDER BY updated_at DESC', (self.account_id,))]

    def find_order_intent(self, order_id=None, broker_tag=None):
        """Resolve by broker identity first; comments are only a secondary positive link."""
        for intent in self.get_intents():
            payload = json.loads(intent['payload'])
            request = payload.get('request', payload)
            known_order = payload.get('order_id') or payload.get('ticket') or request.get('order_id')
            if order_id and known_order:
                if int(known_order) == int(order_id):
                    return intent
                continue
            if broker_tag and broker_tag.startswith('V2_') and request.get('broker_tag') == broker_tag:
                return intent
        return None

    def get_trade_by_position(self, position_id):
        with self._db_lock, self._connection() as conn:
            row = conn.execute('SELECT * FROM trades WHERE account_id=? AND position_id=?',
                               (self.account_id, position_id)).fetchone()
            return dict(row) if row else None

    def attach_execution_policy(self, ticket, position_id, request, order_id=None):
        """Attach only facts retained in our durable request, never a reconstructed trailing SL."""
        with self._db_lock, self._connection() as conn:
            cur = conn.execute('''UPDATE trades SET
                initial_sl=CASE WHEN initial_sl=0 THEN ? ELSE initial_sl END,
                strategy_id=CASE WHEN strategy_id='' THEN ? ELSE strategy_id END,
                broker_order_id=COALESCE(broker_order_id,?)
                WHERE account_id=? AND ticket=?''',
                (float(request.get('sl') or 0), request.get('strategy_id') or '', order_id,
                 self.account_id, ticket))
            if cur.rowcount != 1:
                return False
            policy = request.get('holding_policy')
            if policy:
                conn.execute('''INSERT INTO system_state VALUES (?,?,?,?)
                    ON CONFLICT(account_id,key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at''',
                    (self.account_id, f'position_policy:{position_id}',
                     json.dumps(policy, allow_nan=False), self._now()))
            return True

    def sync_position(self, old_ticket, pos):
        with self._db_lock, self._connection() as conn:
            conn.execute("UPDATE trades SET ticket=?,volume=?,sl=?,tp=? WHERE account_id=? AND ticket=? AND status='OPEN'",
                (pos.ticket,pos.volume,pos.sl,pos.tp,self.account_id,old_ticket))

    def record_deals(self, deals):
        with self._db_lock, self._connection() as conn:
            for d in deals:
                data=d._asdict() if hasattr(d,'_asdict') else vars(d)
                conn.execute("INSERT INTO broker_deals VALUES (?,?,?,?,?,?) ON CONFLICT(account_id,deal_id) DO NOTHING",
                    (self.account_id,int(d.ticket),int(d.position_id),int(getattr(d,'order',0)),int(getattr(d,'time_msc',d.time*1000)),json.dumps(data,default=str)))

    def get_open_trades(self, symbol: str = None) -> List[Dict[str, Any]]:
        """Lấy danh sách các vị thế đang mở từ CSDL."""
        with self._db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            if symbol:
                cursor.execute(
                    "SELECT * FROM trades WHERE account_id = ? AND status = 'OPEN' AND symbol = ?",
                    (self.account_id, symbol),
                )
            else:
                cursor.execute("SELECT * FROM trades WHERE account_id = ? AND status = 'OPEN'", (self.account_id,))
            rows = cursor.fetchall()
            trades = [dict(row) for row in rows]
            conn.close()
            return trades

    def get_closed_trades(self, limit: int = 500) -> List[Dict[str, Any]]:
        """Lấy danh sách các lệnh đã đóng từ CSDL."""
        with self._db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM trades WHERE account_id = ? AND status = 'CLOSED' ORDER BY close_time DESC LIMIT ?",
                (self.account_id,limit),
            )
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
            now_str = self._now()
            try:
                cursor.execute(
                    """
                    INSERT INTO account_equity (timestamp, balance, equity, margin, free_margin, drawdown_pct, account_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (now_str, balance, equity, margin, free_margin, drawdown_pct, self.account_id),
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
            now_str = self._now()
            try:
                cursor.execute(
                    """
                    INSERT INTO system_state (account_id,key,value,updated_at) VALUES (?,?,?,?)
                    ON CONFLICT(account_id,key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at
                """,
                    (self.account_id,key, value, now_str),
                )
                conn.commit()
                return True
            except Exception as e:
                logger.error(f"[DatabaseManager] Lỗi set state {key}: {e}")
                return False
            finally:
                conn.close()

    def get_system_state(self, key: str, default: str = None) -> Optional[str]:
        """Đọc biến trạng thái hệ thống."""
        with self._db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM system_state WHERE account_id = ? AND key = ?", (self.account_id,key))
            row = cursor.fetchone()
            conn.close()
            return row["value"] if row else default
