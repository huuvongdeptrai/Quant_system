"""
Unit & Integration Tests for Institutional Fair Value Gap (FVG) Engine
=====================================================================
Covers:
- 3-candle imbalance detection (bullish demand & bearish supply)
- Displacement confirmation & dynamic ATR noise filter
- Mitigation lifecycle: verified that filled zones terminate strictly at mitigation bar
- Consequent Encroachment (CE 50% equilibrium midpoint)
- Graphical rendering across dark & light themes
- Main chart integration via update_chart_fvgs
"""

import pytest
from unittest.mock import MagicMock
import pyqtgraph as pg
from frontend.controllers.chart.fvg_engine import (
    FVGZone,
    _calculate_tr_atr,
    detect_institutional_fvgs,
    render_institutional_fvg_items,
    update_chart_fvgs,
)


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = pg.QtWidgets.QApplication.instance()
    if not app:
        app = pg.QtWidgets.QApplication([])
    return app


def _generate_synthetic_candle(idx: int, o: float, c: float, l: float, h: float):
    # Format: (t, o, c, l, h) matching ChartData tuple
    return (float(idx), float(o), float(c), float(l), float(h))


def test_tr_atr_calculation():
    """Verify robust Average True Range calculation."""
    # Too few candles
    assert _calculate_tr_atr([], period=14) == 1.0
    assert _calculate_tr_atr([_generate_synthetic_candle(0, 100, 101, 99, 102)], period=14) == 1.0

    candles = [
        _generate_synthetic_candle(0, 100, 105, 98, 107),   # H-L = 9
        _generate_synthetic_candle(1, 105, 110, 103, 112),  # H-L = 9, TR = 9
        _generate_synthetic_candle(2, 110, 108, 106, 114),  # H-L = 8, TR = 8
        _generate_synthetic_candle(3, 108, 115, 107, 116),  # H-L = 9, TR = 9
    ]
    atr = _calculate_tr_atr(candles, period=14)
    assert 8.0 <= atr <= 9.0


def test_detect_bullish_fvg_unmitigated_and_mitigated():
    """
    Test 3-candle bullish imbalance (+FVG):
    - Bar 0: High = 100.0
    - Bar 1: Strong bullish impulse (O=100.5, C=110.0, L=100.2, H=111.0)
    - Bar 2: High continuation (O=109.0, C=112.0, L=104.0, H=113.0)
      => Gap between Bar 2 Low (104.0) and Bar 0 High (100.0) is 4.0 points.
      => Consequent Encroachment (50%) = (104.0 + 100.0) / 2 = 102.0.
    """
    # 1. Unmitigated Bullish FVG
    unmitigated_series = [
        _generate_synthetic_candle(0, 95.0, 99.0, 94.0, 100.0),    # Bar 0 (Origin): H=100.0
        _generate_synthetic_candle(1, 100.5, 110.0, 100.2, 111.0), # Bar 1 (Displacement): C=110.0 > 100.0
        _generate_synthetic_candle(2, 109.0, 112.0, 104.0, 113.0), # Bar 2 (Confirmation): L=104.0 > 100.0
        _generate_synthetic_candle(3, 112.0, 114.0, 108.0, 115.0), # Bar 3: Low stays above 104.0
        _generate_synthetic_candle(4, 114.0, 116.0, 111.0, 117.0), # Bar 4: Current price
    ]

    zones = detect_institutional_fvgs(unmitigated_series, cur_p=116.0, point=0.01)
    assert len(zones) >= 1
    bull_zone = [z for z in zones if z.type == "bull"][0]
    assert bull_zone.top == 104.0
    assert bull_zone.bottom == 100.0
    assert bull_zone.ce == 102.0
    assert bull_zone.gap_size == 4.0
    assert not bull_zone.is_mitigated
    # Active zone projects beyond latest candle
    assert bull_zone.end_idx >= len(unmitigated_series) - 1

    # 2. Mitigated Bullish FVG (Candle 4 retraces down to fill the gap at 99.5 <= bottom 100.0)
    mitigated_series = list(unmitigated_series)
    mitigated_series.append(_generate_synthetic_candle(5, 116.0, 99.0, 98.5, 116.5)) # Fills gap at index 5
    mitigated_series.append(_generate_synthetic_candle(6, 99.0, 102.0, 98.0, 103.0))

    mit_zones = detect_institutional_fvgs(mitigated_series, cur_p=102.0, point=0.01)
    filled = [z for z in mit_zones if z.is_mitigated and z.start_idx == 0]
    assert len(filled) == 1
    assert filled[0].is_mitigated is True
    assert filled[0].mitigated_idx == 5
    # Strict institutional requirement: end_idx MUST stop at the mitigation candle!
    assert filled[0].end_idx == 5


def test_detect_bearish_fvg_unmitigated_and_mitigated():
    """
    Test 3-candle bearish imbalance (-FVG):
    - Bar 0: Low = 200.0
    - Bar 1: Strong bearish impulse (O=199.5, C=185.0, L=184.0, H=199.8)
    - Bar 2: Low continuation (O=186.0, C=183.0, L=182.0, H=194.0)
      => Gap between Bar 0 Low (200.0) and Bar 2 High (194.0) is 6.0 points.
      => Consequent Encroachment (50%) = (200.0 + 194.0) / 2 = 197.0.
    """
    series = [
        _generate_synthetic_candle(0, 205.0, 201.0, 200.0, 206.0), # Bar 0: L=200.0
        _generate_synthetic_candle(1, 199.5, 185.0, 184.0, 199.8), # Bar 1: C=185.0 < 200.0
        _generate_synthetic_candle(2, 186.0, 183.0, 182.0, 194.0), # Bar 2: H=194.0 < 200.0
        _generate_synthetic_candle(3, 183.0, 181.0, 179.0, 184.0), # Bar 3
        _generate_synthetic_candle(4, 181.0, 180.0, 178.0, 182.0), # Bar 4
    ]

    zones = detect_institutional_fvgs(series, cur_p=180.0, point=0.01)
    assert len(zones) >= 1
    bear_zone = [z for z in zones if z.type == "bear"][0]
    assert bear_zone.top == 200.0
    assert bear_zone.bottom == 194.0
    assert bear_zone.ce == 197.0
    assert bear_zone.gap_size == 6.0
    assert not bear_zone.is_mitigated

    # Test mitigation
    series.append(_generate_synthetic_candle(5, 180.0, 202.0, 179.5, 203.0)) # Bar 5 pierces 200.0
    mit_zones = detect_institutional_fvgs(series, cur_p=202.0, point=0.01)
    filled_bear = [z for z in mit_zones if z.is_mitigated and z.start_idx == 0]
    assert len(filled_bear) == 1
    assert filled_bear[0].is_mitigated is True
    assert filled_bear[0].mitigated_idx == 5
    assert filled_bear[0].end_idx == 5


def test_fvg_noise_filter():
    """Verify that micro-gaps smaller than minimum ATR threshold are rejected."""
    # Minimal 0.001 gap when ATR is ~5.0
    series = [
        _generate_synthetic_candle(0, 100.0, 105.0, 99.0, 105.0),
        _generate_synthetic_candle(1, 105.1, 110.0, 104.9, 110.2),
        _generate_synthetic_candle(2, 110.0, 112.0, 105.001, 112.5), # Gap = 0.001
        _generate_synthetic_candle(3, 112.0, 114.0, 111.0, 115.0),
        _generate_synthetic_candle(4, 114.0, 115.0, 113.0, 116.0),
    ]
    zones = detect_institutional_fvgs(series, cur_p=115.0, point=0.01, min_atr_mult=0.5)
    # The tiny 0.001 gap must be rejected
    tiny_gaps = [z for z in zones if z.gap_size < 0.05]
    assert len(tiny_gaps) == 0


def test_render_institutional_fvg_items_qt():
    """Verify PySide6 / pyqtgraph graphic item creation in both Dark and Light themes."""
    import pyqtgraph as pg

    # Ensure QApplication exists for font/graphic tests
    app = pg.QtWidgets.QApplication.instance()
    if not app:
        app = pg.QtWidgets.QApplication([])

    mock_plot = MagicMock()
    mock_plot.addItem = MagicMock()

    test_zones = [
        FVGZone(
            type="bull",
            start_idx=10,
            disp_idx=11,
            form_idx=12,
            end_idx=25,
            top=2500.0,
            bottom=2480.0,
            ce=2490.0,
            is_mitigated=False,
            gap_size=20.0,
            gap_pts=2000.0,
        ),
        FVGZone(
            type="bear",
            start_idx=15,
            disp_idx=16,
            form_idx=17,
            end_idx=20,
            top=2550.0,
            bottom=2535.0,
            ce=2542.5,
            is_mitigated=True,
            mitigated_idx=20,
            gap_size=15.0,
            gap_pts=1500.0,
        ),
    ]

    # 1. Dark Mode
    items_dark = render_institutional_fvg_items(mock_plot, test_zones, is_dark=True, visible=True)
    assert len(items_dark) > 0
    # Bull unmitigated should have: Rect, CE line, Badge Text => 3 items
    # Bear mitigated should have: Rect => 1 item (no CE line or badge to avoid clutter)
    assert len(items_dark) == 4

    # 2. Light Mode
    items_light = render_institutional_fvg_items(mock_plot, test_zones, is_dark=False, visible=True)
    assert len(items_light) == 4


def test_update_chart_fvgs_pipeline():
    """Verify the main entrypoint update_chart_fvgs interacts properly with window state."""
    mock_plot = MagicMock()
    mock_drawing_engine = MagicMock()
    mock_drawing_engine.fvg_items = []

    mock_window = MagicMock()
    mock_window.plot_widget = mock_plot
    mock_window.drawing_engine = mock_drawing_engine
    mock_window.is_dark_theme = True
    mock_window.current_sym = "XAUUSD"
    mock_window.digits = 2
    mock_window._last_manual_entry = 2500.0

    mock_window.chart_data_list = [
        _generate_synthetic_candle(0, 2400.0, 2410.0, 2395.0, 2415.0),
        _generate_synthetic_candle(1, 2416.0, 2445.0, 2415.5, 2450.0),
        _generate_synthetic_candle(2, 2446.0, 2460.0, 2430.0, 2465.0), # Bullish FVG [2415.0, 2430.0]
        _generate_synthetic_candle(3, 2461.0, 2470.0, 2455.0, 2475.0),
        _generate_synthetic_candle(4, 2471.0, 2480.0, 2468.0, 2485.0),
        _generate_synthetic_candle(5, 2481.0, 2490.0, 2478.0, 2495.0),
    ]

    zones = update_chart_fvgs(mock_window)
    assert len(zones) >= 1
    assert len(mock_drawing_engine.fvg_items) >= 1
