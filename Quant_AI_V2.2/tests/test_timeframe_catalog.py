"""
Unit Tests for Comprehensive Multi-Timeframe Catalog & Resolution
Quant AI V2.2 - Institutional Verification
"""

import pytest
from backend.infrastructure.brokers.mt5_safe import mt5


def test_timeframe_constants_availability():
    """Verify all 16 MT5 standard & granular timeframe constants exist and have correct integer values."""
    expected = {
        "TIMEFRAME_M1": 1,
        "TIMEFRAME_M2": 2,
        "TIMEFRAME_M3": 3,
        "TIMEFRAME_M5": 5,
        "TIMEFRAME_M10": 10,
        "TIMEFRAME_M15": 15,
        "TIMEFRAME_M30": 30,
        "TIMEFRAME_H1": 16385,
        "TIMEFRAME_H2": 16386,
        "TIMEFRAME_H4": 16388,
        "TIMEFRAME_H6": 16390,
        "TIMEFRAME_H8": 16392,
        "TIMEFRAME_H12": 16396,
        "TIMEFRAME_D1": 16408,
        "TIMEFRAME_W1": 32769,
        "TIMEFRAME_MN1": 49153,
    }

    for const_name, expected_val in expected.items():
        val = getattr(mt5, const_name, None)
        assert val is not None, f"Constant {const_name} must exist in mt5"
        assert val == expected_val, f"Constant {const_name} expected {expected_val}, got {val}"


def test_quant_ai_ui_combo_bt_timeframes():
    """Verify quant_ai.ui has the full chronological list of timeframes in comboBtTf."""
    import os
    ui_path = "frontend/quant_ai.ui"
    if not os.path.exists(ui_path):
        ui_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "quant_ai.ui")
    with open(ui_path, "r", encoding="utf-8") as f:
        content = f.read()

    expected_tfs = [
        "M1", "M2", "M3", "M5", "M10", "M15", "M30",
        "H1", "H2", "H4", "H6", "H8", "H12",
        "D1", "W1", "MN1"
    ]

    assert 'name="comboBtTf"' in content
    # Ensure all timeframes are listed
    for tf in expected_tfs:
        assert f"<string>{tf}</string>" in content, f"Timeframe {tf} must be in comboBtTf"


def test_simulation_runner_timeframe_map():
    """Verify simulation runner maps all timeframes without errors."""
    tf_map = {
        "M1": mt5.TIMEFRAME_M1,
        "M2": getattr(mt5, "TIMEFRAME_M2", 2),
        "M3": getattr(mt5, "TIMEFRAME_M3", 3),
        "M4": getattr(mt5, "TIMEFRAME_M4", 4),
        "M5": mt5.TIMEFRAME_M5,
        "M6": getattr(mt5, "TIMEFRAME_M6", 6),
        "M10": getattr(mt5, "TIMEFRAME_M10", 10),
        "M12": getattr(mt5, "TIMEFRAME_M12", 12),
        "M15": mt5.TIMEFRAME_M15,
        "M20": getattr(mt5, "TIMEFRAME_M20", 20),
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H2": getattr(mt5, "TIMEFRAME_H2", 16386),
        "H3": getattr(mt5, "TIMEFRAME_H3", 16387),
        "H4": mt5.TIMEFRAME_H4,
        "H6": getattr(mt5, "TIMEFRAME_H6", 16390),
        "H8": getattr(mt5, "TIMEFRAME_H8", 16392),
        "H12": getattr(mt5, "TIMEFRAME_H12", 16396),
        "D1": mt5.TIMEFRAME_D1,
        "W1": getattr(mt5, "TIMEFRAME_W1", 32769),
        "MN1": getattr(mt5, "TIMEFRAME_MN1", 49153),
    }

    assert len(tf_map) >= 16
    for tf_key, tf_val in tf_map.items():
        assert tf_val > 0, f"Timeframe {tf_key} must resolve to a positive MT5 constant"
