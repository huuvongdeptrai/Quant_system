"""
GIAI ĐOẠN 7: EVENT RISK ENGINE & PRE-NEWS ACTIVE DEFENSE
Kiểm thử Bộ lọc rủi ro tin tức đa tài sản & Chế độ phòng vệ vị thế tự động trước tin (T-15 phút)
"""

import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest

from backend.core.event_risk_engine import EventRiskEngine
from backend.infrastructure.brokers.mt5_safe import mt5


class TestStage7EventRiskEngine:
    def setup_method(self):
        self.mock_exec = MagicMock()
        self.mock_cal = MagicMock()
        self.engine = EventRiskEngine(
            execution_manager=self.mock_exec,
            calendar_engine=self.mock_cal,
            defense_window_mins=15,
            pause_window_mins=30,
            max_spread_multiplier=1.5,
        )

    # -------------------------------------------------------------
    # 1. Multi-Asset Currency Mapping Tests
    # -------------------------------------------------------------
    def test_multi_asset_currency_mapping(self):
        # US News
        assert self.engine.is_symbol_impacted_by_event("EURUSD", "US", "CPI") is True
        assert self.engine.is_symbol_impacted_by_event("USDJPY", "US", "Fed Rate Decision") is True
        assert self.engine.is_symbol_impacted_by_event("XAUUSD", "US", "Non-Farm Payrolls") is True
        assert self.engine.is_symbol_impacted_by_event("US30", "US", "GDP") is True
        assert self.engine.is_symbol_impacted_by_event("GBPJPY", "US", "CPI") is False

        # EU News (ECB)
        assert self.engine.is_symbol_impacted_by_event("EURUSD", "EU", "ECB Rate") is True
        assert self.engine.is_symbol_impacted_by_event("EURGBP", "EU", "ECB Press") is True
        assert self.engine.is_symbol_impacted_by_event("GBPJPY", "EU", "ECB Rate") is False
        assert self.engine.is_symbol_impacted_by_event("XAUUSD", "EU", "ECB Rate") is False

        # GB News (BOE)
        assert self.engine.is_symbol_impacted_by_event("GBPUSD", "GB", "BOE Rate") is True
        assert self.engine.is_symbol_impacted_by_event("EURUSD", "GB", "BOE Rate") is False

    # -------------------------------------------------------------
    # 2. News Pause Window Checking
    # -------------------------------------------------------------
    def test_check_news_impact_for_symbol(self):
        now_ts = datetime.now(timezone.utc).timestamp() + (7 * 3600)
        # Fake 1 tin đỏ US CPI lúc now + 10 phút (trong window 30 phút)
        self.engine._news_events_cache = [
            {
                "country": "US",
                "title": "CPI m/m",
                "impact": 2,
                "sort_key": now_ts + 600,
            }
        ]
        self.engine._news_events_ts = time.time()

        # EURUSD bị khóa vì có USD
        blocked, news = self.engine.check_news_impact_for_symbol("EURUSD")
        assert blocked is True
        assert "CPI" in news

        # EURGBP không bị khóa vì là tin US
        blocked, news = self.engine.check_news_impact_for_symbol("EURGBP")
        assert blocked is False
        assert news == ""

    # -------------------------------------------------------------
    # 3. Pre-News Defense: Rule 1 (Profit >= 1.5R -> Breakeven)
    # -------------------------------------------------------------
    @patch("backend.core.event_risk_engine.mt5.positions_get")
    @patch("backend.core.event_risk_engine.mt5.symbol_info_tick")
    @patch("backend.core.event_risk_engine.mt5.symbol_info")
    def test_pre_news_defense_auto_breakeven_large_profit(
        self, mock_info, mock_tick, mock_positions
    ):
        now_ts = datetime.now(timezone.utc).timestamp() + (7 * 3600)
        # Tin đỏ trong 10 phút tới (nằm trong defense_window 15m)
        self.engine._news_events_cache = [
            {"country": "US", "title": "FOMC", "impact": 2, "sort_key": now_ts + 600}
        ]
        self.engine._news_events_ts = time.time()

        # Position BUY EURUSD: open=1.0800, sl=1.0780 (risk = 20 pips)
        # Current Bid = 1.0840 (+40 pips = +2.0R >= 1.5R)
        pos = MagicMock()
        pos.ticket = 10101
        pos.symbol = "EURUSD"
        pos.type = mt5.ORDER_TYPE_BUY
        pos.volume = 0.5
        pos.price_open = 1.0800
        pos.sl = 1.0780
        pos.tp = 1.0900
        mock_positions.return_value = [pos]

        tick = MagicMock()
        tick.bid = 1.0840
        tick.ask = 1.0842
        mock_tick.return_value = tick

        sym_info = MagicMock()
        sym_info.point = 0.00001
        sym_info.digits = 5
        sym_info.volume_min = 0.01
        sym_info.volume_step = 0.01
        mock_info.return_value = sym_info

        self.mock_exec.modify_position.return_value = {"status": "success"}

        results = self.engine.evaluate_pre_news_defense()

        assert len(results) == 1
        assert results[0]["ticket"] == 10101
        assert results[0]["action"] == "AUTO_BREAKEVEN"
        assert results[0]["r_multiple"] >= 1.5
        # Modify position phải được gọi để dời SL về Breakeven
        self.mock_exec.modify_position.assert_called_once()
        call_args = self.mock_exec.modify_position.call_args[1]
        assert call_args["sl"] >= 1.0800  # Đã dời lên BE + buffer

    # -------------------------------------------------------------
    # 4. Pre-News Defense: Rule 2 (Profit 0.5R - 1.5R -> Partial Close 50%)
    # -------------------------------------------------------------
    @patch("backend.core.event_risk_engine.mt5.positions_get")
    @patch("backend.core.event_risk_engine.mt5.symbol_info_tick")
    @patch("backend.core.event_risk_engine.mt5.symbol_info")
    def test_pre_news_defense_partial_close_50(
        self, mock_info, mock_tick, mock_positions
    ):
        now_ts = datetime.now(timezone.utc).timestamp() + (7 * 3600)
        self.engine._news_events_cache = [
            {"country": "US", "title": "NFP", "impact": 2, "sort_key": now_ts + 600}
        ]
        self.engine._news_events_ts = time.time()

        # Position BUY EURUSD: open=1.0800, sl=1.0780 (risk = 20 pips)
        # Current Bid = 1.0820 (+20 pips = +1.0R, nằm trong 0.5R - 1.5R)
        pos = MagicMock()
        pos.ticket = 20202
        pos.symbol = "EURUSD"
        pos.type = mt5.ORDER_TYPE_BUY
        pos.volume = 0.40
        pos.price_open = 1.0800
        pos.sl = 1.0780
        pos.tp = 1.0900
        mock_positions.return_value = [pos]

        tick = MagicMock()
        tick.bid = 1.0820
        tick.ask = 1.0822
        mock_tick.return_value = tick

        sym_info = MagicMock()
        sym_info.point = 0.00001
        sym_info.digits = 5
        sym_info.volume_min = 0.01
        sym_info.volume_step = 0.01
        mock_info.return_value = sym_info

        self.mock_exec.close_position.return_value = {"status": "success"}
        self.mock_exec.modify_position.return_value = {"status": "success"}

        results = self.engine.evaluate_pre_news_defense()

        assert len(results) == 1
        assert results[0]["ticket"] == 20202
        assert results[0]["action"] == "PARTIAL_CLOSE_50"
        assert results[0]["closed_volume"] == 0.20  # 50% của 0.40

        # Close position phải được gọi với volume = 0.20
        self.mock_exec.close_position.assert_called_once_with(20202, volume=0.20)
        # Phần còn lại được dời về BE
        self.mock_exec.modify_position.assert_called_once()

    # -------------------------------------------------------------
    # 5. Pre-News Defense: Losing Positions Are Preserved (User Custom Settings)
    # -------------------------------------------------------------
    @patch("backend.core.event_risk_engine.mt5.positions_get")
    @patch("backend.core.event_risk_engine.mt5.symbol_info_tick")
    @patch("backend.core.event_risk_engine.mt5.symbol_info")
    def test_pre_news_defense_losing_position_ignored(
        self, mock_info, mock_tick, mock_positions
    ):
        now_ts = datetime.now(timezone.utc).timestamp() + (7 * 3600)
        self.engine._news_events_cache = [
            {"country": "US", "title": "CPI", "impact": 2, "sort_key": now_ts + 600}
        ]
        self.engine._news_events_ts = time.time()

        # Position BUY EURUSD đang âm: open=1.0800, sl=1.0780, bid=1.0785 (-0.75R)
        pos = MagicMock()
        pos.ticket = 30303
        pos.symbol = "EURUSD"
        pos.type = mt5.ORDER_TYPE_BUY
        pos.volume = 0.10
        pos.price_open = 1.0800
        pos.sl = 1.0780
        pos.tp = 1.0900
        mock_positions.return_value = [pos]

        tick = MagicMock()
        tick.bid = 1.0785
        tick.ask = 1.0787
        mock_tick.return_value = tick

        sym_info = MagicMock()
        sym_info.point = 0.00001
        sym_info.digits = 5
        sym_info.volume_min = 0.01
        sym_info.volume_step = 0.01
        mock_info.return_value = sym_info

        results = self.engine.evaluate_pre_news_defense()

        # Lệnh âm KHÔNG bị can thiệp
        assert len(results) == 0
        self.mock_exec.close_position.assert_not_called()
        self.mock_exec.modify_position.assert_not_called()

    # -------------------------------------------------------------
    # 6. Post-News Spread Normalization Sensor
    # -------------------------------------------------------------
    @patch("backend.core.event_risk_engine.mt5.symbol_info")
    def test_check_spread_normalization(self, mock_info):
        sym_info = MagicMock()
        # Forex base spread an toàn là 25, multiplier 1.5 -> max safe là 37
        sym_info.spread = 30
        mock_info.return_value = sym_info

        ok, curr, max_s = self.engine.check_spread_normalization("EURUSD")
        assert ok is True
        assert curr == 30
        assert max_s == 37

        # Khi spread giãn lên 65 points (vượt ngưỡng 37)
        sym_info.spread = 65
        ok, curr, max_s = self.engine.check_spread_normalization("EURUSD")
        assert ok is False
        assert curr == 65
