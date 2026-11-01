import os
import pytest
pytestmark=pytest.mark.skipif(os.environ.get("QT_QPA_PLATFORM")=="offscreen",reason="Native system tray requires a desktop session")
"""
Unit tests for SystemTrayManager - Background Mode, Anti-Sleep, and Context Menu Operations.
"""

import sys
import pytest
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt

from frontend.controllers.system_tray_manager import SystemTrayManager


class DummyTerminal:
    """Mock QuantTerminal for testing tray controller interactions."""
    def __init__(self):
        self.window = QWidget()
        self.bot_toggled = False
        self.kill_switch_triggered = False

    def _toggle_bot(self):
        self.bot_toggled = True

    class Header:
        def __init__(self, parent):
            self.parent = parent
        def _trigger_kill_switch(self):
            self.parent.kill_switch_triggered = True

    @property
    def header(self):
        return self.Header(self)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_system_tray_manager_initialization(qapp):
    terminal = DummyTerminal()
    tray = SystemTrayManager(terminal)

    assert tray.terminal == terminal
    assert tray.window == terminal.window
    assert tray.is_bot_active is False
    assert tray._keep_awake_active is False

    # Check context menu actions
    assert tray.tray_menu is not None
    assert tray.act_title is not None
    assert tray.act_status is not None
    assert tray.act_restore is not None
    assert tray.act_toggle_bot is not None
    assert tray.act_kill_switch is not None
    assert tray.act_exit is not None


def test_system_tray_minimize_and_restore(qapp):
    terminal = DummyTerminal()
    terminal.window.show()
    tray = SystemTrayManager(terminal)

    # Test minimize to tray
    tray.minimize_to_tray()
    assert terminal.window.isVisible() is False
    if sys.platform == "win32":
        assert tray._keep_awake_active is True

    # Test restore from tray
    tray.restore_from_tray()
    assert terminal.window.isVisible() is True
    # Since bot is not active, keep awake should be released
    if sys.platform == "win32":
        assert tray._keep_awake_active is False


def test_system_tray_status_update(qapp):
    terminal = DummyTerminal()
    tray = SystemTrayManager(terminal)

    # Update to Active
    tray.update_bot_status(is_active=True, open_positions=2, detail_msg="Scanning XAUUSD")
    assert tray.is_bot_active is True
    assert "ACTIVE" in tray.act_status.text()
    assert "2 Positions" in tray.act_status.text()
    assert tray.act_toggle_bot.text() == "Pause Bot Execution"

    # Update to Circuit Breaker
    tray.update_bot_status(is_active=False, open_positions=0, circuit_breaker=True)
    assert tray.is_bot_active is False
    assert "CIRCUIT BREAKER" in tray.act_status.text()
    assert tray.act_toggle_bot.text() == "Start Bot Execution"


def test_system_tray_emergency_actions(qapp):
    terminal = DummyTerminal()
    tray = SystemTrayManager(terminal)

    # Toggle bot
    tray._toggle_bot_execution()
    assert terminal.bot_toggled is True

    # Kill switch
    tray._trigger_kill_switch()
    assert terminal.kill_switch_triggered is True


def test_system_tray_render_icons(qapp):
    terminal = DummyTerminal()
    tray = SystemTrayManager(terminal)

    icon_idle = tray._render_status_icon(is_active=False)
    icon_active = tray._render_status_icon(is_active=True)
    icon_trade = tray._render_status_icon(is_active=True, in_trade=True)
    icon_err = tray._render_status_icon(is_active=False, is_error=True)

    assert not icon_idle.isNull()
    assert not icon_active.isNull()
    assert not icon_trade.isNull()
    assert not icon_err.isNull()
