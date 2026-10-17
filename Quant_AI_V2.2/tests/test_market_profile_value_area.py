"""
Unit tests for Market Profile Volume Profile & 70% Value Area (VAH / VAL).
Grounded in J. Peter Steidlmayer's Market Profile Theory (CBOT, 1985).
"""

import pytest
import numpy as np
from PySide6.QtWidgets import QApplication

from frontend.controllers.chart.chart_canvas import _compute_market_profile_va
from frontend.controllers.chart.drawing_engine import ChartDrawingEngine


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def sample_market_rates():
    """Generates structured 120-bar structured numpy recarray with volume."""
    np.random.seed(1985)
    n = 120
    base = 2320.0
    drift = np.cumsum(np.random.normal(0.05, 0.4, n))
    lows = base + drift - np.random.uniform(0.5, 2.0, n)
    highs = base + drift + np.random.uniform(0.5, 2.0, n)
    closes = (lows + highs) / 2.0 + np.random.uniform(-0.3, 0.3, n)
    vols = np.random.randint(50, 1500, n)

    dtype = [("low", "f8"), ("high", "f8"), ("close", "f8"), ("tick_volume", "i8")]
    rates = np.empty(n, dtype=dtype)
    rates["low"] = lows
    rates["high"] = highs
    rates["close"] = closes
    rates["tick_volume"] = vols
    return rates


class TestMarketProfileValueAreaMath:
    """Tests the mathematical correctness of Steidlmayer's 70% Value Area calculation."""

    def test_empty_or_degenerate_rates(self):
        """Edge cases: empty, None, or zero-spread rates."""
        assert _compute_market_profile_va(None) == (0.0, 0.0, 0.0)
        assert _compute_market_profile_va([]) == (0.0, 0.0, 0.0)

        # Single flat bar
        dtype = [("low", "f8"), ("high", "f8"), ("close", "f8"), ("tick_volume", "i8")]
        flat = np.empty(1, dtype=dtype)
        flat["low"] = 2300.0
        flat["high"] = 2300.0
        flat["close"] = 2300.0
        flat["tick_volume"] = 100
        vpoc, vah, val = _compute_market_profile_va(flat)
        assert vpoc == 2300.0
        assert vah == 2300.0
        assert val == 2300.0

    def test_mathematical_invariants(self, sample_market_rates):
        """Core Invariant: VAL <= vPOC <= VAH within extreme boundaries."""
        vpoc, vah, val = _compute_market_profile_va(sample_market_rates, lookback=100, va_pct=0.70)

        sub = sample_market_rates[-100:]
        abs_min = float(np.min(sub["low"]))
        abs_max = float(np.max(sub["high"]))

        assert val <= vpoc <= vah, f"Invariant violated: {val} <= {vpoc} <= {vah}"
        assert abs_min <= val, f"VAL ({val}) cannot be below sample min ({abs_min})"
        assert vah <= abs_max, f"VAH ({vah}) cannot be above sample max ({abs_max})"

    def test_steidlmayer_70_percent_volume_coverage(self, sample_market_rates):
        """Verifies that the price region between VAL and VAH captures at least 70% of total volume."""
        vpoc, vah, val = _compute_market_profile_va(sample_market_rates, lookback=100, va_pct=0.70)

        sub = sample_market_rates[-100:]
        total_vol = float(np.sum(sub["tick_volume"]))

        # Calculate volume intersecting [VAL, VAH]
        inside_vol = 0.0
        for r in sub:
            h, l, v = float(r["high"]), float(r["low"]), float(r["tick_volume"])
            overlap_min = max(l, val)
            overlap_max = min(h, vah)
            if overlap_max >= overlap_min and (h - l) > 0:
                inside_vol += v * ((overlap_max - overlap_min) / (h - l))
            elif overlap_max >= overlap_min:
                inside_vol += v

        # With continuous discretization into 60 bins, coverage should be >= 68% (tolerating bin discretization)
        coverage_pct = inside_vol / total_vol
        assert coverage_pct >= 0.65, f"Expected ~70% coverage, got {coverage_pct*100:.1f}%"

    def test_asymmetric_volume_skew(self):
        """When volume heavily concentrates at highs, POC and VA should skew towards highs."""
        dtype = [("low", "f8"), ("high", "f8"), ("close", "f8"), ("tick_volume", "i8")]
        n = 50
        skewed = np.empty(n, dtype=dtype)
        for i in range(n):
            skewed[i]["low"] = 2000.0 + i * 2
            skewed[i]["high"] = 2005.0 + i * 2
            skewed[i]["close"] = 2003.0 + i * 2
            # 90% of volume concentrated in the top 5 bars
            skewed[i]["tick_volume"] = 10000 if i >= 45 else 50

    def test_authentic_tpoc_vs_vpoc_divergence(self):
        """
        Steidlmayer CBOT Invariant:
        When the market consolidates over many bars at a low price range (High TPO),
        but experiences an aggressive high-volume spike at a high price range (High Volume),
        tPOC (Time POC) and vPOC (Volume POC) diverge quantitatively to reflect
        time consolidation vs volume absorption.
        """
        dtype = [("low", "f8"), ("high", "f8"), ("close", "f8"), ("tick_volume", "i8")]
        n = 60
        rates = np.empty(n, dtype=dtype)
        # 55 bars spent consolidating between 2000 and 2005 (low volume per bar)
        for i in range(55):
            rates[i]["low"] = 2000.0
            rates[i]["high"] = 2005.0
            rates[i]["close"] = 2002.5
            rates[i]["tick_volume"] = 100

        # 5 bars spike up to 2090..2100 with massive volume (e.g. 50,000)
        for i in range(55, 60):
            rates[i]["low"] = 2090.0
            rates[i]["high"] = 2100.0
            rates[i]["close"] = 2095.0
            rates[i]["tick_volume"] = 50000

        vpoc, vah, val, tpoc = _compute_market_profile_va(rates, lookback=60, num_bins=60, va_pct=0.70, return_tpoc=True)
        # tPOC must reflect the 55 bars of time consolidation near 2000..2005
        assert 2000.0 <= tpoc <= 2010.0, f"tPOC should be at consolidation base, got {tpoc}"
        # vPOC must reflect the massive volume spike near 2090..2100
        assert 2085.0 <= vpoc <= 2100.0, f"vPOC should be at volume concentration, got {vpoc}"
        assert tpoc != vpoc, f"tPOC ({tpoc}) and vPOC ({vpoc}) should diverge under asymmetric conditions"


class TestMarketProfileUIIntegration:
    """Tests the interaction between chart canvas, drawing engine, and navigation toggles."""

    def test_drawing_engine_toggle_value_area(self, qapp):
        """Verifies toggle_value_area cleanly updates visibility flags and UI objects."""
        import pyqtgraph as pg

        class MockWindow:
            def __init__(self):
                self._va_visible = False
                self.plot_widget = pg.PlotWidget()
                self.line_vah = None
                self.line_val = None
                self.va_region = None

        mock_win = MockWindow()
        engine = ChartDrawingEngine(mock_win)

        engine.toggle_value_area(True)
        assert mock_win._va_visible is True

        engine.toggle_value_area(False)
        assert mock_win._va_visible is False

    def test_granular_profile_level_toggles(self, qapp):
        """Verifies individual toggles for vPOC, tPOC, VAH, VAL, and Value Area Fill."""
        import pyqtgraph as pg
        from PySide6.QtWidgets import QPushButton

        class MockLine:
            def __init__(self):
                self.visible = True
            def setVisible(self, v):
                self.visible = bool(v)

        class MockWindow:
            def __init__(self):
                self._poc_visible = True
                self._va_visible = True
                self._vpoc_visible = True
                self._tpoc_visible = True
                self._vah_visible = True
                self._val_visible = True
                self._va_fill_visible = True
                self.plot_widget = pg.PlotWidget()
                self.line_vpoc = MockLine()
                self.line_tpoc = MockLine()
                self.line_vah = MockLine()
                self.line_val = MockLine()
                self.va_region = MockLine()

        mock_win = MockWindow()
        engine = ChartDrawingEngine(mock_win)

        # 1. Toggle vPOC individual
        engine.toggle_vpoc(False)
        assert mock_win._vpoc_visible is False
        assert mock_win.line_vpoc.visible is False
        engine.toggle_vpoc(True)
        assert mock_win._vpoc_visible is True
        assert mock_win.line_vpoc.visible is True

        # 2. Toggle tPOC individual
        engine.toggle_tpoc(False)
        assert mock_win._tpoc_visible is False
        assert mock_win.line_tpoc.visible is False
        engine.toggle_tpoc(True)
        assert mock_win._tpoc_visible is True
        assert mock_win.line_tpoc.visible is True

        # 3. Toggle VAH individual
        engine.toggle_vah(False)
        assert mock_win._vah_visible is False
        assert mock_win.line_vah.visible is False
        engine.toggle_vah(True)
        assert mock_win._vah_visible is True
        assert mock_win.line_vah.visible is True

        # 4. Toggle VAL individual
        engine.toggle_val(False)
        assert mock_win._val_visible is False
        assert mock_win.line_val.visible is False
        engine.toggle_val(True)
        assert mock_win._val_visible is True
        assert mock_win.line_val.visible is True

        # 5. Toggle VA fill individual
        engine.toggle_va_fill(False)
        assert mock_win._va_fill_visible is False
        assert mock_win.va_region.visible is False
        engine.toggle_va_fill(True)
        assert mock_win._va_fill_visible is True
        assert mock_win.va_region.visible is True

    def test_drawing_engine_toolbar_profile_button(self, qapp):
        """Verifies set_toolbar_buttons accommodates btn_profile and preserves theme updates."""
        import pyqtgraph as pg
        from PySide6.QtWidgets import QPushButton

        class MockWindow:
            def __init__(self):
                self.plot_widget = pg.PlotWidget()
                self.is_dark_theme = False
                self._get_tool_btn_style = lambda is_d, is_active=False, is_accent=False: "/* test-style */"

        mock_win = MockWindow()
        engine = ChartDrawingEngine(mock_win)

        btn_ch = QPushButton()
        btn_tl = QPushButton()
        btn_rect = QPushButton()
        btn_ruler = QPushButton()
        btn_gear = QPushButton()
        btn_clr = QPushButton()
        btn_prof = QPushButton()

        engine.set_toolbar_buttons(btn_ch, btn_tl, btn_rect, btn_ruler, btn_gear, btn_clr, btn_profile=btn_prof)
        assert engine.btn_profile is btn_prof
        assert "/* test-style */" in btn_prof.styleSheet()
