"""
Unit Tests for Execution Volume Normalization & Step Quantization
Quant AI V2.2 - Institutional Verification
"""

import pytest
from unittest.mock import MagicMock
from backend.infrastructure.brokers.execution_manager import ExecutionManager
from backend.infrastructure.brokers.mt5_safe import mt5


class TestExecutionVolumeNormalization:
    """Institutional Brokerage Model - Lot Size & Volume Step Quantization."""

    def test_normalize_volume_standard_forex(self, monkeypatch):
        """Forex pair: min 0.01, max 100.0, step 0.01."""
        mock_info = MagicMock()
        mock_info.volume_min = 0.01
        mock_info.volume_max = 100.0
        mock_info.volume_step = 0.01
        monkeypatch.setattr(mt5, "symbol_info", lambda s: mock_info)

        em = ExecutionManager()

        # Exact steps
        assert em.normalize_volume("EURUSD", 0.01) == 0.01
        assert em.normalize_volume("EURUSD", 1.50) == 1.50

        # Fractional rounding
        assert em.normalize_volume("EURUSD", 0.0154) == 0.02
        assert em.normalize_volume("EURUSD", 0.0149) == 0.01

        # Min clamp
        assert em.normalize_volume("EURUSD", 0.002) == 0.01
        assert em.normalize_volume("EURUSD", -0.5) == 0.01

        # Max clamp
        assert em.normalize_volume("EURUSD", 150.0) == 100.0

    def test_normalize_volume_indices_large_step(self, monkeypatch):
        """Index contract: min 0.1, max 50.0, step 0.1."""
        mock_info = MagicMock()
        mock_info.volume_min = 0.1
        mock_info.volume_max = 50.0
        mock_info.volume_step = 0.1
        monkeypatch.setattr(mt5, "symbol_info", lambda s: mock_info)

        em = ExecutionManager()

        # Step quantization
        assert em.normalize_volume("US500", 0.24) == 0.2
        assert em.normalize_volume("US500", 0.26) == 0.3

        # Below min clamps to min
        assert em.normalize_volume("US500", 0.05) == 0.1

        # Above max clamps to max
        assert em.normalize_volume("US500", 99.0) == 50.0

    def test_normalize_volume_integer_contracts(self, monkeypatch):
        """Futures contract with integer lots: min 1.0, max 200.0, step 1.0."""
        mock_info = MagicMock()
        mock_info.volume_min = 1.0
        mock_info.volume_max = 200.0
        mock_info.volume_step = 1.0
        monkeypatch.setattr(mt5, "symbol_info", lambda s: mock_info)

        em = ExecutionManager()

        assert em.normalize_volume("XAU_FUT", 1.4) == 1.0
        assert em.normalize_volume("XAU_FUT", 1.8) == 2.0
        assert em.normalize_volume("XAU_FUT", 0.3) == 1.0

    def test_close_position_partial_volume_normalization(self, monkeypatch):
        """Partial close quantizes request and avoids orphan fragments below min_step."""
        mock_info = MagicMock()
        mock_info.volume_min = 0.01
        mock_info.volume_max = 100.0
        mock_info.volume_step = 0.01
        mock_info.digits = 2
        mock_info.filling_mode = 1
        monkeypatch.setattr(mt5, "symbol_info", lambda s: mock_info)

        mock_tick = MagicMock()
        mock_tick.bid = 2000.00
        mock_tick.ask = 2000.20
        monkeypatch.setattr(mt5, "symbol_info_tick", lambda s: mock_tick)

        mock_pos = MagicMock()
        mock_pos.ticket = 12345
        mock_pos.symbol = "XAUUSD"
        mock_pos.type = 0  # BUY
        mock_pos.volume = 0.03
        monkeypatch.setattr(mt5, "positions_get", lambda ticket=None: [mock_pos])

        sent_request = None
        def fake_order_send(req):
            nonlocal sent_request
            sent_request = req
            res = MagicMock()
            res.retcode = 10009  # TRADE_RETCODE_DONE
            res.deal = 9999
            return res

        monkeypatch.setattr(mt5, "order_send", fake_order_send)

        em = ExecutionManager()

        # Partial close 50% of 0.03 = 0.015 -> quantizes to 0.02
        # Remaining = 0.03 - 0.02 = 0.01 >= min_step (0.01) -> partial close
        res = em.close_position(12345, volume=0.015)
        assert res["status"] == "success"
        assert sent_request["volume"] == 0.02
        assert "Quant_Close_Partial" in sent_request["comment"]

        # Partial close where remaining would be < 0.01:
        # e.g., pos.volume = 0.02, request close 0.015 -> norm_close = 0.02
        # (pos.volume - norm_close) = 0.00 < 0.01 -> closes whole 0.02
        mock_pos.volume = 0.02
        res2 = em.close_position(12345, volume=0.015)
        assert res2["status"] == "success"
        assert sent_request["volume"] == 0.02
        assert "Quant_Close_Single" in sent_request["comment"]
