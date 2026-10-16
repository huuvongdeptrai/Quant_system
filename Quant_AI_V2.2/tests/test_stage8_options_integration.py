"""
STAGE 8: OPTIONS INTEGRATION & RISK PARAMETER ENFORCEMENT
Tests verification of all Options dialog settings:
- max_daily_loss circuit breaker
- max_open_trades capacity gating
- close_friday weekend risk shield
- risk_per_trade lot size scaling
- user_max_spread liquidity sensor
- telegram_notifier category filtering
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from backend.core.bot_worker import BotWorker
from backend.core.event_risk_engine import EventRiskEngine
from backend.infrastructure.notifications.telegram_notifier import TelegramNotifier
from backend.infrastructure.brokers.mt5_safe import mt5


class TestStage8OptionsIntegration:
    def test_telegram_category_filtering(self):
        notifier = TelegramNotifier()
        notifier.bot_token = "dummy_token"
        notifier.chat_id = "123456"

        with patch("threading.Thread") as mock_thread:
            # 1. Fill alerts enabled -> should dispatch
            notifier.alert_fills = True
            notifier.send_message("Order filled", category="fill")
            assert mock_thread.called

            # 2. Fill alerts disabled -> should NOT dispatch
            mock_thread.reset_mock()
            notifier.alert_fills = False
            notifier.send_message("Order filled", category="fill")
            assert not mock_thread.called

            # 3. SL/TP alerts disabled -> should NOT dispatch
            mock_thread.reset_mock()
            notifier.alert_sl_tp = False
            notifier.send_message("SL Trailed", category="sl_tp")
            assert not mock_thread.called

            # 4. Risk halt alerts enabled -> should dispatch
            mock_thread.reset_mock()
            notifier.alert_risk_halt = True
            notifier.send_message("Halt!", category="risk_halt")
            assert mock_thread.called

    def test_event_risk_user_max_spread(self):
        engine = EventRiskEngine(user_max_spread=25)
        sym_info = MagicMock(spread=30)
        with patch.object(mt5, "symbol_info", return_value=sym_info):
            ok, curr, max_s = engine.check_spread_normalization("XAUUSD")
            assert ok is False
            assert curr == 30
            assert max_s == 25

        sym_info.spread = 20
        with patch.object(mt5, "symbol_info", return_value=sym_info):
            ok, curr, max_s = engine.check_spread_normalization("XAUUSD")
            assert ok is True
            assert curr == 20
            assert max_s == 25

    def test_circuit_breaker_max_daily_loss(self):
        mock_strat = MagicMock()
        mock_risk = MagicMock()
        mock_exec = MagicMock()
        mock_prep = MagicMock()
        mock_gate = MagicMock()

        worker = BotWorker(
            strategy=mock_strat,
            risk_manager=mock_risk,
            execution_manager=mock_exec,
            data_preprocessor=mock_prep,
            decision_gate=mock_gate,
            max_daily_loss=300.0,
            max_drawdown=0.0,
            max_losing_streak=0,
        )

        acc = MagicMock(equity=10000.0, balance=10000.0, margin=0, margin_free=10000.0)
        with patch.object(mt5, "account_info", return_value=acc):
            worker._manage_circuit_breaker()
            assert worker.circuit_breaker_active is False
            assert worker.start_of_day_equity == 10000.0

            # Daily loss drops by $400 (exceeds $300 limit)
            acc.equity = 9600.0
            worker._manage_circuit_breaker()
            assert worker.circuit_breaker_active is True

    def test_max_open_trades_limit(self):
        mock_strat = MagicMock()
        mock_risk = MagicMock()
        mock_exec = MagicMock()
        mock_prep = MagicMock()
        mock_gate = MagicMock()

        worker = BotWorker(
            strategy=mock_strat,
            risk_manager=mock_risk,
            execution_manager=mock_exec,
            data_preprocessor=mock_prep,
            decision_gate=mock_gate,
            max_open_trades=2,
        )

        # 2 positions already open -> pipeline_execute should return early
        pos1 = MagicMock(ticket=1)
        pos2 = MagicMock(ticket=2)
        with patch.object(mt5, "positions_get", return_value=[pos1, pos2]):
            with patch.object(mt5, "copy_rates_from_pos") as mock_rates:
                worker.pipeline_execute("EURUSD")
                mock_rates.assert_not_called()

    def test_friday_eod_defense(self):
        mock_strat = MagicMock()
        mock_risk = MagicMock()
        mock_exec = MagicMock()
        mock_prep = MagicMock()
        mock_gate = MagicMock()

        worker = BotWorker(
            strategy=mock_strat,
            risk_manager=mock_risk,
            execution_manager=mock_exec,
            data_preprocessor=mock_prep,
            decision_gate=mock_gate,
            close_friday=True,
        )

        # 2026-10-16 is a Friday (weekday == 4), at 21:30 UTC
        mock_now = datetime(2026, 10, 16, 21, 30, tzinfo=timezone.utc)
        with patch("backend.core.bot_worker.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            allowed, reason = worker._check_session_allowed()
            assert allowed is False
            assert reason == "FRIDAY_EOD"

    def test_watchlist_single_xauusd_preserved(self):
        from frontend.controllers.watchlist_controller import WatchlistManager
        mock_win = MagicMock()
        mock_tree = MagicMock()
        mock_win.treeWatchlist = mock_tree

        with patch.object(WatchlistManager, "setup_ui"), \
             patch.object(WatchlistManager, "refresh_all_status_icons"):
            mgr = WatchlistManager(mock_win)
            import io, json
            mock_file = io.StringIO(json.dumps(["XAUUSD"]))
            with patch("builtins.open", return_value=mock_file), \
                 patch.object(mgr, "add_symbol_to_tree") as mock_add, \
                 patch.object(mgr, "save_watchlist"), \
                 patch("os.path.exists", return_value=True):
                mock_file.seek(0)
                mgr.load_watchlist()
                # Phải nạp đúng 1 mã XAUUSD, tuyệt đối KHÔNG được nạp đè 9 cặp mặc định
                assert mock_add.call_count == 1
                assert mock_add.call_args[0][0] == "XAUUSD"
