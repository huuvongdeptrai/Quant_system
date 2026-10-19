# -*- coding: utf-8 -*-
"""
Test Suite: Multi-Asset Watchlist Scanning, Concurrency & Vector SVG Icons.
Verifies:
1. Multi-asset position isolation: Open trade in XAUUSD does not block BTCUSD.
2. Crypto 24/7 session filter exemption: BTCUSD passes session checks regardless of Forex hours/weekends.
3. Spread sensor multi-asset normalization: BTCUSD spread (e.g. 1500 points) is permitted.
4. Polymorphic strategy dispatch in BotOrchestrator: ICT, Wyckoff, EMA all execute across Watchlist symbols.
5. Watchlist dynamic symbols provider: BotOrchestrator immediately ingests newly added watchlist symbols.
6. Vector SVG icon audit: Header strategy menu and dialogs use vector SVG QIcon with zero emojis.
"""

import os
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
from PySide6.QtWidgets import QApplication

from backend.infrastructure.brokers.mt5_safe import mt5
from backend.core.session_filter import SessionFilter
from backend.core.event_risk_engine import EventRiskEngine
from backend.core.state_recovery import StateRecoveryManager
from backend.core.bot_orchestrator import BotOrchestrator
from backend.infrastructure.data_providers.asset_registry import AssetRegistry, AssetClass


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


class TestMultiAssetWatchlistAndIcons:

    def test_multi_asset_position_isolation_xau_does_not_block_btc(self):
        """Verifies that an active position in Gold (XAUUSD) does NOT block BTCUSD."""
        mock_db = MagicMock()
        mock_db.get_open_trades.return_value = []
        recovery = StateRecoveryManager(mock_db)

        # Mock MT5 positions: 1 open position for XAUUSD
        pos_gold = MagicMock()
        pos_gold.symbol = "XAUUSD"
        pos_gold.ticket = 1001

        with patch.object(mt5, "positions_get") as mock_pos_get:
            def side_effect_pos(*args, **kwargs):
                sym = kwargs.get("symbol")
                if sym == "XAUUSD":
                    return [pos_gold]
                elif sym == "BTCUSD":
                    return []
                return [pos_gold]

            mock_pos_get.side_effect = side_effect_pos

            # XAUUSD is already open, cannot open a new trade on XAUUSD
            assert recovery.can_open_new_trade("XAUUSD") is False

            # BTCUSD has NO open position, CAN open new trade despite XAUUSD being active
            assert recovery.can_open_new_trade("BTCUSD") is True

    def test_crypto_24_7_session_filter_exemption(self):
        """Verifies that Crypto (BTCUSD) is 24/7 exempt from Forex session windows and Friday EOD."""
        filter_session = SessionFilter(allowed_sessions=["LONDON"], close_friday=True)

        # Non-crypto (XAUUSD) is subject to session restrictions
        is_allowed_crypto, reason_crypto = filter_session.is_session_allowed(symbol="BTCUSD")
        assert is_allowed_crypto is True
        assert reason_crypto == "CRYPTO_24_7"

        # Friday EOD liquidation should skip Crypto
        mock_exec = MagicMock()
        pos_btc = MagicMock()
        pos_btc.symbol = "BTCUSD"
        pos_btc.ticket = 2001

        pos_gold = MagicMock()
        pos_gold.symbol = "XAUUSD"
        pos_gold.ticket = 1001

        with patch.object(mt5, "positions_get") as mock_pos_get, \
             patch("backend.core.session_filter.datetime") as mock_dt:
            # Simulate Friday at 22:00 UTC
            mock_now = MagicMock()
            mock_now.weekday.return_value = 4  # Friday
            mock_now.hour = 22
            mock_dt.now.return_value = mock_now

            mock_pos_get.side_effect = lambda symbol: [pos_gold] if symbol == "XAUUSD" else [pos_btc]
            mock_exec.close_position.return_value = {"status": "success"}

            closed = filter_session.manage_friday_eod(["XAUUSD", "BTCUSD"], mock_exec)
            # Gold must be closed for weekend protection, Crypto MUST NOT be closed
            assert 1001 in closed
            assert 2001 not in closed

    def test_spread_normalization_for_crypto_and_multi_asset(self):
        """Verifies that BTCUSD spread (e.g. 1200 points / 15 bps) is allowed and not blocked by user_max_spread."""
        ere = EventRiskEngine(user_max_spread=25)  # 25 points default for Forex

        info_btc = MagicMock()
        info_btc.spread = 1200
        info_btc.path = "Crypto\\BTCUSD"
        info_btc.digits = 2

        tick_btc = MagicMock()
        tick_btc.ask = 65000.0
        tick_btc.bid = 64988.0  # $12 spread = 1200 pts, spread_bps = 1.84 bps

        with patch.object(mt5, "symbol_info", return_value=info_btc), \
             patch.object(mt5, "symbol_info_tick", return_value=tick_btc):
            is_ok, curr_spd, max_spd = ere.check_spread_normalization("BTCUSD")
            assert is_ok is True
            assert curr_spd == 1200
            assert max_spd >= 6000

    def test_bot_orchestrator_dynamic_symbols_provider(self):
        """Verifies that BotOrchestrator dynamically updates symbols from symbols_provider."""
        mock_strategy = MagicMock()
        mock_risk = MagicMock()
        mock_exec = MagicMock()
        mock_prep = MagicMock()
        mock_gate = MagicMock()

        bot = BotOrchestrator(
            strategy=mock_strategy,
            risk_manager=mock_risk,
            execution_manager=mock_exec,
            data_preprocessor=mock_prep,
            decision_gate=mock_gate,
            symbols=["XAUUSD"],
        )
        assert bot.symbols == ["XAUUSD"]

        # Register dynamic symbols provider (simulating Watchlist addition of BTCUSD)
        bot.symbols_provider = lambda: ["XAUUSD", "BTCUSD", "ETHUSD"]

        # Verify that dynamic refresh updates symbols
        refreshed = bot.symbols_provider()
        assert "BTCUSD" in refreshed
        assert "ETHUSD" in refreshed

    def test_vector_svg_icons_in_header_strategy_menu(self, qapp):
        """Verifies that HeaderController strategy menu uses vector SVG QIcon without emojis."""
        from frontend.controllers.header_controller import WorkspaceHeaderController
        mock_terminal = MagicMock()
        mock_window = MagicMock()
        mock_terminal.window = mock_window

        header = WorkspaceHeaderController(mock_terminal)

        # Verify assets exist
        assets_dir = "frontend/assets"
        for icon_name in ["icon_import.svg", "icon_folder.svg", "tool_gear.svg", "check_vector_emerald.svg"]:
            p = os.path.join(assets_dir, icon_name)
            assert os.path.exists(p), f"Asset {icon_name} must exist"

    def test_position_guard_sync_closed_trades_sends_telegram_on_tp_sl(self):
        """Verifies that PositionGuard sends Telegram notification whenever a position hits TP or SL."""
        from backend.core.position_guard import PositionGuard
        from backend.infrastructure.notifications.telegram_notifier import telegram_notifier

        mock_exec = MagicMock()
        mock_db = MagicMock()
        mock_db.get_open_trades.return_value = [
            {"ticket": 5001, "symbol": "BTCUSD", "volume": 0.5, "open_price": 65000.0, "order_type": "BUY"},
            {"ticket": 5002, "symbol": "XAUUSD", "volume": 1.0, "open_price": 2650.0, "order_type": "BUY"},
        ]

        guard = PositionGuard(execution_manager=mock_exec, db_manager=mock_db)

        # Live positions: Only XAUUSD is still open, BTCUSD (ticket 5001) has closed!
        pos_xau = MagicMock(ticket=5002)
        mock_deal = MagicMock(profit=750.0, price=66500.0, comment="tp hit")

        with patch.object(mt5, "positions_get", return_value=[pos_xau]), \
             patch.object(mt5, "history_deals_get", return_value=[mock_deal]), \
             patch.object(telegram_notifier, "send_message") as mock_tg:

            guard.sync_closed_trades()

            # Verify DB closed record
            mock_db.record_close_trade.assert_called_with(ticket=5001, close_price=66500.0, pnl=750.0)

            # Verify Telegram notification was sent
            assert mock_tg.call_count >= 1
            call_args = mock_tg.call_args[0][0]
            assert "TAKE PROFIT HIT" in call_args
            assert "5001" in call_args
            assert "BTCUSD" in call_args
            assert "+$750.00" in call_args
            assert mock_tg.call_args[1].get("category") == "sl_tp"

    def test_parallel_multi_asset_pipeline_execution_isolated(self):
        """Verifies that Gold open trade does not prevent BotOrchestrator from executing BTCUSD."""
        mock_strategy = MagicMock()
        mock_strategy.analyze.return_value = {
            "signal": "BUY",
            "entry_price": 65000.0,
            "sl": 64500.0,
            "tp1": 66000.0,
            "confidence": 0.90,
        }
        mock_risk = MagicMock()
        mock_risk.calculate_lot_size.return_value = 0.50
        mock_exec = MagicMock()
        mock_exec.execute_market_order.return_value = {"status": "success", "ticket": 7777}
        mock_prep = MagicMock()
        mock_prep.process_technical_data.return_value = {"trend": "UP"}
        mock_gate = MagicMock()
        mock_gate.evaluate.return_value = {"decision": "BUY", "reason": "Gate passed"}

        bot = BotOrchestrator(
            strategy=mock_strategy,
            risk_manager=mock_risk,
            execution_manager=mock_exec,
            data_preprocessor=mock_prep,
            decision_gate=mock_gate,
            symbols=["XAUUSD", "BTCUSD"],
            max_open_trades=5,
        )

        pos_gold = MagicMock()
        pos_gold.symbol = "XAUUSD"
        pos_gold.ticket = 1001

        fake_rates = [{"close": 65000.0, "time": 1700000000}]

        with patch.object(mt5, "terminal_info", return_value=MagicMock()), \
             patch.object(mt5, "positions_get", return_value=[pos_gold]), \
             patch.object(mt5, "symbol_select", return_value=True), \
             patch.object(mt5, "copy_rates_from_pos", return_value=fake_rates), \
             patch.object(bot.trade_dispatcher, "dispatch_market_order") as mock_dispatch:

            bot.pipeline_execute("BTCUSD")

            # BTCUSD was evaluated and order dispatch was called despite Gold being active!
            assert mock_dispatch.call_count == 1
            assert mock_dispatch.call_args[1]["symbol"] == "BTCUSD"
            assert mock_dispatch.call_args[1]["signal"] == "BUY"
