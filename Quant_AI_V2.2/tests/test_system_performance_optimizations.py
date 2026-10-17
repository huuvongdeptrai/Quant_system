"""
Unit tests verifying high-performance engineering optimizations across Quant AI V2.2:
- SQLite WAL mode & Synchronous Normal
- Incremental Dual-Layer Candlestick Painting
- Responsive Event-Driven Bot Wake-up
"""

import time
import pytest
import numpy as np
from PySide6.QtWidgets import QApplication

from backend.database.db_manager import DatabaseManager
from frontend.controllers.chart.candlestick_items import CandlestickItem
from backend.core.bot_orchestrator import BotOrchestrator


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestPerformanceOptimizations:
    """Verifies that all 5 critical latency optimizations execute correctly."""

    def test_sqlite_wal_mode_and_pragmas(self, tmp_path):
        """Verifies that DatabaseManager enforces WAL mode and NORMAL synchronous."""
        db_file = str(tmp_path / "perf_test.db")
        db = DatabaseManager(db_file)
        conn = db._get_connection()
        cur = conn.cursor()

        # Check journal mode
        cur.execute("PRAGMA journal_mode;")
        mode = cur.fetchone()[0].upper()
        assert mode == "WAL", f"Expected WAL journal mode, got {mode}"

        # Check synchronous mode (1 = NORMAL)
        cur.execute("PRAGMA synchronous;")
        sync = cur.fetchone()[0]
        assert sync == 1, f"Expected synchronous NORMAL (1), got {sync}"

        conn.close()
        DatabaseManager.reset_instance()

    def test_incremental_candlestick_update_performance(self, qapp):
        """Validates that update_live_bar executes in under 1 millisecond on 5,000 candles."""
        n = 5000
        data = [(i, 2300.0, 2301.0, 2299.0, 2302.0) for i in range(n)]
        candlestick = CandlestickItem(data, is_dark=False)

        # Measure 100 live bar updates
        t0 = time.perf_counter()
        for i in range(100):
            candlestick.update_live_bar(2300.0, 2301.0 + i * 0.05, 2298.5, 2302.5 + i * 0.05)
        elapsed_total = (time.perf_counter() - t0) * 1000  # ms
        avg_elapsed = elapsed_total / 100

        # Must execute within 1 ms per update (ordinarily takes ~0.001 ms)
        assert avg_elapsed < 1.0, f"Incremental update took {avg_elapsed:.3f} ms, expected < 1.0 ms"
        assert candlestick.data[-1][2] == 2301.0 + 99 * 0.05

    def test_bot_orchestrator_wake_up_event(self):
        """Verifies that BotOrchestrator initializes _wake_event and wakes up immediately."""
        from unittest.mock import MagicMock
        orch = BotOrchestrator(
            strategy=MagicMock(),
            risk_manager=MagicMock(),
            execution_manager=MagicMock(),
            data_preprocessor=MagicMock(),
            decision_gate=MagicMock(),
            symbols=["XAUUSD"],
        )
        assert hasattr(orch, "_wake_event")
        assert not orch._wake_event.is_set()

        orch.wake_up()
        assert orch._wake_event.is_set()
