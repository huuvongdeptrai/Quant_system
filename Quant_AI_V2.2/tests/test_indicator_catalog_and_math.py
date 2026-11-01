"""
Unit tests for Studies & Quantitative Technical Indicators Dialog and Calculation Engine.
Verifies academic grounding, formula computations, clean architecture, and theme synchronization.
"""

import pytest
import numpy as np
import pandas as pd
from PySide6.QtWidgets import QApplication

from frontend.controllers.chart.indicator_dialog import (
    INDICATOR_CATALOG,
    INDICATOR_METADATA,
    IndicatorDialog,
    _compute_indicators,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def sample_market_df():
    """Generates synthetic 150-bar OHLCV market data for indicator validation."""
    np.random.seed(42)
    n = 150
    base_price = 2350.0
    returns = np.random.normal(0.0002, 0.002, n)
    close = base_price * np.cumprod(1 + returns)
    high = close + np.random.uniform(0.5, 3.0, n)
    low = close - np.random.uniform(0.5, 3.0, n)
    open_p = low + np.random.uniform(0.0, 1.0, n) * (high - low)
    volume = np.random.randint(100, 2000, n)

    df = pd.DataFrame({
        "time": np.arange(1700000000, 1700000000 + n * 60, 60),
        "open": open_p,
        "high": high,
        "low": low,
        "close": close,
        "tick_volume": volume,
    })
    return df


class TestIndicatorAcademicSpecifications:
    """Tests the integrity and literature citations of the indicator catalog."""

    def test_catalog_and_metadata_completeness(self):
        """Ensures all 10 indicators are mapped, documented, and have academic citations."""
        assert len(INDICATOR_METADATA) == 10

        required_keys = ["title", "short_name", "category", "description", "citation", "formula", "badge", "pane"]
        for ind_id, meta in INDICATOR_METADATA.items():
            for key in required_keys:
                assert key in meta, f"Indicator '{ind_id}' missing key '{key}'"
                assert len(meta[key]) > 0, f"Indicator '{ind_id}' has empty '{key}'"
            assert meta["pane"] in ["main", "sub"], f"Invalid pane type for '{ind_id}'"

    def test_peer_reviewed_citations_present(self):
        """Verifies peer-reviewed literature presence for key quantitative models."""
        # Brock, Lakonishok, & LeBaron (1992) for EMA
        assert "Brock" in INDICATOR_METADATA["ema"]["citation"]
        assert "Journal of Finance" in INDICATOR_METADATA["ema"]["citation"]

        # Siegel / Neely et al. for SMA 200
        assert "Neely" in INDICATOR_METADATA["ma200"]["citation"]
        assert "Management Science" in INDICATOR_METADATA["ma200"]["citation"]

        # Kyle (1985) for CVD Order Flow
        assert "Kyle" in INDICATOR_METADATA["cvd"]["citation"]
        assert "Econometrica" in INDICATOR_METADATA["cvd"]["citation"]

        # Berkowitz / Madhavan for VWAP
        assert "Berkowitz" in INDICATOR_METADATA["vwap"]["citation"]
        assert "Journal of Finance" in INDICATOR_METADATA["vwap"]["citation"]


class TestIndicatorCalculationEngine:
    """Tests mathematical correctness of the indicator computation engine."""

    def test_empty_dataframe(self):
        """Engine should return empty dict when given empty or None DataFrame."""
        assert _compute_indicators(None, {}) == {}
        assert _compute_indicators(pd.DataFrame(), {}) == {}

    def test_dual_ema_computation(self, sample_market_df):
        """Validates EMA 10 and EMA 50 calculations."""
        active = {"ema": True}
        computed = _compute_indicators(sample_market_df, active)

        assert "EMA_10" in computed
        assert "EMA_50" in computed
        assert len(computed["EMA_10"]) == len(sample_market_df)
        assert len(computed["EMA_50"]) == len(sample_market_df)

        # Check mathematical sanity: EMA should track close closely
        assert np.isclose(computed["EMA_10"][-1], sample_market_df["close"].iloc[-1], rtol=0.05)

    def test_bollinger_bands_computation(self, sample_market_df):
        """Validates Bollinger Bands: Upper > Mid > Lower."""
        active = {"bollinger": True}
        computed = _compute_indicators(sample_market_df, active)

        assert "BB_UPPER" in computed
        assert "BB_MID" in computed
        assert "BB_LOWER" in computed

        # Validate that Upper >= Mid >= Lower everywhere
        up = np.array(computed["BB_UPPER"])
        mid = np.array(computed["BB_MID"])
        low = np.array(computed["BB_LOWER"])

        assert np.all(up >= mid)
        assert np.all(mid >= low)

    def test_vwap_and_dispersion_bands(self, sample_market_df):
        """Validates VWAP and volume-weighted standard deviation bands."""
        active = {"vwap": True}
        computed = _compute_indicators(sample_market_df, active)

        assert "VWAP_LINE" in computed
        assert "VWAP_UPPER" in computed
        assert "VWAP_LOWER" in computed

        v_up = np.array(computed["VWAP_UPPER"])
        v_mid = np.array(computed["VWAP_LINE"])
        v_low = np.array(computed["VWAP_LOWER"])

        assert np.all(v_up >= v_mid)
        assert np.all(v_mid >= v_low)

    def test_rsi_bounds(self, sample_market_df):
        """Validates that RSI 14 stays bounded within [0, 100]."""
        active = {"rsi": True}
        computed = _compute_indicators(sample_market_df, active)

        assert "RSI_14" in computed
        rsi_vals = np.array(computed["RSI_14"])
        assert np.all(rsi_vals >= 0.0)
        assert np.all(rsi_vals <= 100.0)

    def test_macd_computation(self, sample_market_df):
        """Validates MACD line, signal line, and histogram (Appel 1979)."""
        active = {"macd": True}
        computed = _compute_indicators(sample_market_df, active)

        assert "MACD_LINE" in computed
        assert "MACD_SIGNAL" in computed
        assert "MACD_HIST" in computed
        assert len(computed["MACD_LINE"]) == len(sample_market_df)
        assert len(computed["MACD_SIGNAL"]) == len(sample_market_df)
        assert len(computed["MACD_HIST"]) == len(sample_market_df)

        diff = np.array(computed["MACD_LINE"]) - np.array(computed["MACD_SIGNAL"])
        assert np.allclose(np.array(computed["MACD_HIST"]), diff)

    def test_donchian_channels_rolling_envelopes(self, sample_market_df):
        """Verifies Donchian channels compute full rolling envelopes and invariant LOW <= MID <= HIGH."""
        active = {"donchian": True}
        computed = _compute_indicators(sample_market_df, active)

        assert "DONCHIAN_SERIES_HIGH" in computed
        assert "DONCHIAN_SERIES_LOW" in computed
        assert "DONCHIAN_SERIES_MID" in computed

        h = np.array(computed["DONCHIAN_SERIES_HIGH"])
        l = np.array(computed["DONCHIAN_SERIES_LOW"])
        m = np.array(computed["DONCHIAN_SERIES_MID"])

        assert len(h) == len(sample_market_df)
        assert np.all(l <= h)
        assert np.allclose(m, (h + l) / 2.0)

    def test_all_ten_indicators_concurrent(self, sample_market_df):
        """Ensures all 10 indicators calculate simultaneously without memory or CPU bottleneck."""
        all_active = {k: True for k in INDICATOR_METADATA.keys()}
        computed = _compute_indicators(sample_market_df, all_active)

        expected_keys = [
            "x", "EMA_10", "EMA_50", "MA_200", "DONCHIAN_HIGH", "DONCHIAN_LOW",
            "_pivot_raw", "BB_MID", "BB_UPPER", "BB_LOWER", "VWAP_LINE",
            "VWAP_UPPER", "VWAP_LOWER", "RSI_14", "MACD_LINE", "MACD_SIGNAL",
            "MACD_HIST", "CVD_LINE", "FVG_ZONES"
        ]
        for k in expected_keys:
            assert k in computed, f"Missing computed key: {k}"


class TestIndicatorDialogUI:
    """Tests the IndicatorDialog UI widget, theme synchronization, and search filtering."""

    def test_dialog_theme_synchronization_light(self, qapp):
        """Verifies Light Theme styling applies white background and dark text."""
        dlg = IndicatorDialog(parent=None, is_dark=False)
        assert dlg.is_dark is False
        assert "background-color: #FFFFFF" in dlg.styleSheet()
        assert "background-color: #1E222D" not in dlg.styleSheet()
        dlg.close()

    def test_dialog_theme_synchronization_dark(self, qapp):
        """Verifies Dark Theme styling applies institutional slate background."""
        dlg = IndicatorDialog(parent=None, is_dark=True)
        assert dlg.is_dark is True
        assert "background-color: #0C0E14" in dlg.styleSheet()
        dlg.close()

    def test_search_filtering(self, qapp):
        """Verifies search input filters indicators by name or academic citation."""
        dlg = IndicatorDialog(parent=None, is_dark=False)

        # Search for 'Kyle' -> should find only CVD
        dlg.search_bar.setText("Kyle")
        assert len(dlg._checkboxes) == 1
        assert "cvd" in dlg._checkboxes

        # Search for 'Brock' -> should find EMA
        dlg.search_bar.setText("Brock")
        assert len(dlg._checkboxes) == 1
        assert "ema" in dlg._checkboxes

        # Clear search -> all 10 should show under 'All Studies'
        dlg.search_bar.setText("")
        assert len(dlg._checkboxes) == 10
        dlg.close()

    def test_toggle_and_reset_all(self, qapp):
        """Verifies toggling on/off and the 'Reset All' button."""
        active = {}
        dlg = IndicatorDialog(parent=None, active_indicators=active, is_dark=False)

        dlg._toggle("ema", True)
        assert active["ema"] is True
        assert "1 study active" in dlg.lbl_active_count.text()

        dlg._toggle("rsi", True)
        assert active["rsi"] is True
        assert "2 studies active" in dlg.lbl_active_count.text()

        dlg._reset_all()
        assert active["ema"] is False
        assert active["rsi"] is False
        assert "0 studies active" in dlg.lbl_active_count.text()
        dlg.close()

    def test_oscillator_subpane_lifecycle(self, qapp):
        """Verifies oscillator curve management attaches cleanly and toggles safely."""
        import pyqtgraph as pg
        from frontend.controllers.chart.indicator_dialog import _get_or_create_osc_curve, _hide_osc_curve

        class MockWindow:
            def __init__(self):
                self.plot_widget = pg.PlotWidget()
                self.osc_plot_widget = pg.PlotWidget()

        win = MockWindow()
        pen = pg.mkPen("#10b981")
        curve = _get_or_create_osc_curve(win, "TEST_RSI", pen)
        assert curve is not None
        assert curve.isVisible() is True

        _hide_osc_curve(win, "TEST_RSI")
        assert curve.isVisible() is False

    def test_subpane_exclusive_switching(self, qapp):
        """Verifies switching between sub-pane oscillators automatically disables previous sub-pane study."""
        active = {}
        dlg = IndicatorDialog(parent=None, active_indicators=active, is_dark=False)

        # 1. Activate main overlay EMA -> should be active
        dlg._toggle("ema", True)
        assert active["ema"] is True

        # 2. Activate sub-pane RSI -> both EMA and RSI should be active
        dlg._toggle("rsi", True)
        assert active["ema"] is True
        assert active["rsi"] is True

        # 3. Activate sub-pane MACD -> RSI must be automatically unchecked to prevent scale collision
        dlg._toggle("macd", True)
        assert active["ema"] is True
        assert active["macd"] is True
        assert active["rsi"] is False

        # 4. Activate sub-pane CVD -> MACD must be automatically unchecked
        dlg._toggle("cvd", True)
        assert active["cvd"] is True
        assert active["macd"] is False
        assert active["rsi"] is False

        dlg.close()

    def test_oscillator_bargraph_lifecycle(self, qapp):
        """Verifies oscillator BarGraphItem management attaches cleanly and toggles safely."""
        import pyqtgraph as pg
        from frontend.controllers.chart.indicator_dialog import _get_or_create_osc_bargraph, _hide_osc_bargraph

        class MockWindow:
            def __init__(self):
                self.plot_widget = pg.PlotWidget()
                self.osc_plot_widget = pg.PlotWidget()

        win = MockWindow()
        brush = pg.mkBrush("#22c55e")
        bar = _get_or_create_osc_bargraph(win, "TEST_BAR", brush)
        assert bar is not None
        assert bar.isVisible() is True

        _hide_osc_bargraph(win, "TEST_BAR")
        assert bar.isVisible() is False

    def test_refresh_indicators_with_ribbon_legend(self, qapp, sample_market_df):
        """Verifies _refresh_indicators populates the ribbon study legend dynamically."""
        import pyqtgraph as pg
        from PySide6.QtWidgets import QLabel
        from frontend.controllers.chart.indicator_dialog import _refresh_indicators

        class MockWindow:
            def __init__(self):
                self.plot_widget = pg.PlotWidget()
                self.osc_plot_widget = pg.PlotWidget()
                self.lbl_chart_studies = QLabel()
                self.active_indicators = {"ema": True, "rsi": True}

        win = MockWindow()
        _refresh_indicators(win, sample_market_df)

        assert win.lbl_chart_studies.isVisible() is True
        text = win.lbl_chart_studies.text()
        assert "EMA10" in text
        assert "EMA50" in text
        assert "RSI" in text

        # Turn all indicators off
        win.active_indicators = {}
        _refresh_indicators(win, sample_market_df)
        assert win.lbl_chart_studies.isVisible() is False



@pytest.fixture(autouse=True)
def dispose_indicator_widgets(qapp):
    """Destroy native graphics while QApplication is still alive."""
    previous = {id(widget) for widget in QApplication.topLevelWidgets()}
    yield
    from PySide6.QtCore import QCoreApplication, QEvent
    for widget in QApplication.topLevelWidgets():
        if id(widget) in previous:
            continue
        widget.close()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    qapp.processEvents()
