# -*- coding: utf-8 -*-
"""
Unit tests for Startup Overlay & Initialization Resilience.
Validates:
1. FadeOverlayWidget watchdog fail-safe timer (never traps GUI).
2. Trader interactive dismissal: Mouse click anywhere bypasses overlay.
3. Trader hotkey dismissal: ESC / Space / Enter bypasses overlay.
4. InitWorker MT5 session preservation (no IPC named-pipe deadlock on multi-thread).
5. MacroRegimeEngine TTL caching (no blocking network calls on repeated evaluations).
"""

import time
import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QMouseEvent, QKeyEvent

from frontend.widgets.splash_screen import FadeOverlayWidget, InitWorker
from backend.infrastructure.data_providers.macro.macro_regime import MacroRegimeEngine, _MACRO_CACHE


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def test_fade_overlay_watchdog_fail_safe_configured(qapp):
    """Verifies that FadeOverlayWidget arms a fail-safe timer to prevent UI freeze."""
    parent = QMainWindow()
    overlay = FadeOverlayWidget(parent)
    assert hasattr(overlay, "_fail_safe_timer")
    assert overlay._fail_safe_timer.isSingleShot() is True
    assert overlay._fail_safe_timer.interval() <= 2500
    overlay.fade_out_and_destroy(50)


def test_fade_overlay_dismisses_on_mouse_click(qapp):
    """Verifies that clicking anywhere on the overlay dismisses it immediately."""
    parent = QMainWindow()
    overlay = FadeOverlayWidget(parent)
    overlay.show()

    assert not getattr(overlay, "_fading", False)
    event = QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPoint(50, 50), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    overlay.mousePressEvent(event)
    assert getattr(overlay, "_fading", False) is True


def test_fade_overlay_dismisses_on_escape_key(qapp):
    """Verifies that pressing ESC immediately dismisses the overlay."""
    parent = QMainWindow()
    overlay = FadeOverlayWidget(parent)
    overlay.show()

    assert not getattr(overlay, "_fading", False)
    event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    overlay.keyPressEvent(event)
    assert getattr(overlay, "_fading", False) is True


def test_init_worker_preserves_active_mt5_session(qapp):
    """
    Verifies that when an MT5 session is already active on the main thread,
    InitWorker reuses it and NEVER calls mt5.initialize(), preventing IPC deadlocks.
    """
    worker = InitWorker()

    mock_term = MagicMock(connected=True)
    mock_acc = MagicMock(login=1234567, server="Broker-Live")

    with patch("backend.infrastructure.brokers.mt5_safe.mt5.terminal_info", return_value=mock_term) as mock_info, \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.account_info", return_value=mock_acc), \
         patch("backend.infrastructure.brokers.mt5_safe.mt5.initialize") as mock_init:

        progress_calls = []
        worker.progress.connect(lambda val, msg: progress_calls.append((val, msg)))

        done_called = []
        worker.init_done.connect(lambda: done_called.append(True))

        worker.run()

        # MT5 initialize MUST NOT be called because session was already active
        mock_init.assert_not_called()
        assert len(done_called) == 1
        assert any(call[0] == 100 for call in progress_calls)


def test_macro_regime_engine_ttl_caching():
    """Verifies that MacroRegimeEngine serves cached reports within TTL to avoid network hang."""
    engine = MacroRegimeEngine()
    fake_report = {"Market": {"state": "Risk-On"}, "Monetary": {"state": "Neutral"}, "Economic": {"state": "Growth"}, "Telegram_News": "None"}

    _MACRO_CACHE["report"] = fake_report
    _MACRO_CACHE["timestamp"] = time.time()

    with patch.object(engine, "get_market_state") as mock_market:
        report = engine.generate_macro_report()
        mock_market.assert_not_called()
        assert report == fake_report
