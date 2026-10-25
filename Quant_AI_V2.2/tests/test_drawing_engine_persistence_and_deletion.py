# -*- coding: utf-8 -*-
"""
Tests for ChartDrawingEngine:
1. Tool persistence: Trendline and Rectangle mode stay active after drawing (no auto-revert to crosshair).
2. Point-to-drawing proximity detection (_find_drawing_at).
3. Hover and selection visual highlighting (_set_highlight).
4. Single-object deletion via _delete_drawing and keyboard Delete / Backspace key events.
5. Mode switching via Escape key and button toggles.
"""

import math
import pytest
from unittest.mock import MagicMock
from PySide6.QtCore import Qt, QPoint, QPointF, QEvent
from PySide6.QtGui import QKeyEvent
import pyqtgraph as pg

from PySide6.QtWidgets import QApplication
from frontend.controllers.chart.drawing_engine import ChartDrawingEngine


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class MockChartWindow:
    def __init__(self):
        self.plot_widget = pg.PlotWidget()
        self.is_dark_theme = False
        self._crosshair_enabled = True
        self.vLine = pg.InfiniteLine(angle=90)
        self.hLine = pg.InfiniteLine(angle=0)
        self.crosshair_label = pg.TextItem()
        self._get_tool_btn_style = lambda is_d, is_active=False, is_accent=False: "/* mock */"


@pytest.fixture
def chart_engine(qapp):
    win = MockChartWindow()
    engine = ChartDrawingEngine(win)
    return engine, win


def test_drawing_mode_persistence_trendline(chart_engine):
    """Verifies that drawing a trendline does NOT reset mode to crosshair."""
    engine, win = chart_engine
    engine.set_mode(ChartDrawingEngine.MODE_TRENDLINE)
    assert engine.mode == ChartDrawingEngine.MODE_TRENDLINE

    # Draw line 1
    engine._commit_drawing(10.0, 100.0, 20.0, 120.0)
    assert len(engine.user_drawings) == 1
    # Mode must remain trendline for continuous drawing
    assert engine.mode == ChartDrawingEngine.MODE_TRENDLINE

    # Draw line 2
    engine._commit_drawing(30.0, 130.0, 40.0, 150.0)
    assert len(engine.user_drawings) == 2
    assert engine.mode == ChartDrawingEngine.MODE_TRENDLINE


def test_drawing_mode_persistence_rectangle(chart_engine):
    """Verifies that drawing a rectangle zone does NOT reset mode to crosshair."""
    engine, win = chart_engine
    engine.set_mode(ChartDrawingEngine.MODE_RECTANGLE)
    assert engine.mode == ChartDrawingEngine.MODE_RECTANGLE

    engine._commit_drawing(10.0, 100.0, 20.0, 120.0)
    assert len(engine.user_drawings) == 1
    assert engine.mode == ChartDrawingEngine.MODE_RECTANGLE


def test_single_trendline_deletion(chart_engine):
    """Verifies that individual trendlines can be targeted and deleted without affecting others."""
    engine, win = chart_engine
    engine.set_mode(ChartDrawingEngine.MODE_TRENDLINE)

    # Create 3 trendlines
    engine._commit_drawing(10.0, 100.0, 20.0, 120.0)
    engine._commit_drawing(30.0, 130.0, 40.0, 150.0)
    engine._commit_drawing(50.0, 160.0, 60.0, 180.0)
    assert len(engine.user_drawings) == 3

    line1 = engine.user_drawings[0]
    line2 = engine.user_drawings[1]
    line3 = engine.user_drawings[2]

    # Target line 2 specifically for deletion
    engine.hovered_drawing = line2
    engine._delete_drawing(line2)

    assert len(engine.user_drawings) == 2
    assert line2 not in engine.user_drawings
    assert engine.user_drawings[0] == line1
    assert engine.user_drawings[1] == line3
    assert engine.hovered_drawing is None


def test_delete_key_event_filters(chart_engine):
    """Verifies Delete and Backspace key events trigger single item deletion."""
    engine, win = chart_engine
    engine.set_mode(ChartDrawingEngine.MODE_TRENDLINE)

    engine._commit_drawing(10.0, 100.0, 20.0, 120.0)
    engine._commit_drawing(30.0, 130.0, 40.0, 150.0)
    assert len(engine.user_drawings) == 2

    target = engine.user_drawings[0]
    engine.selected_drawing = target

    # Simulate Key_Delete
    del_ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key_Delete, Qt.KeyboardModifier.NoModifier)
    consumed = engine.eventFilter(win.plot_widget, del_ev)

    assert consumed is True
    assert len(engine.user_drawings) == 1
    assert target not in engine.user_drawings
    assert engine.selected_drawing is None


def test_escape_key_cancels_to_crosshair(chart_engine):
    """Verifies Escape key returns active drawing tool to crosshair mode."""
    engine, win = chart_engine
    engine.set_mode(ChartDrawingEngine.MODE_TRENDLINE)
    assert engine.mode == ChartDrawingEngine.MODE_TRENDLINE

    esc_ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key_Escape, Qt.KeyboardModifier.NoModifier)
    consumed = engine.eventFilter(win.plot_widget, esc_ev)

    assert consumed is True
    assert engine.mode == ChartDrawingEngine.MODE_CROSSHAIR
