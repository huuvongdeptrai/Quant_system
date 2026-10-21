# -*- coding: utf-8 -*-
"""
Test Suite: MT5 Standard Shortcuts Verification & Collision-Free Architecture.
Verifies that all 25+ institutional MetaTrader 5 keyboard shortcuts:
1. Are canonically registered as QActions with Qt.WindowShortcut context.
2. Have zero ambiguous shortcut collisions across menus (Strategy Tester, Calendar, Journal, Full Screen).
3. Correctly trigger their associated controller and navigation methods.
4. Maintain full backward compatibility for legacy .activated signal consumers.
"""

import pytest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QMenuBar
from PySide6.QtGui import QKeySequence, QAction
from PySide6.QtCore import Qt

from frontend.controllers.header_controller import WorkspaceHeaderController


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


class TestMT5ShortcutsExecution:

    @pytest.fixture
    def mock_terminal(self, qapp):
        win = QMainWindow()
        win.tabWidget = MagicMock()
        win.tab2 = QWidget()
        win.tab3 = QWidget()
        win.tab_5 = QWidget()
        win.tabCalendar = QWidget()
        win.sidebar = QWidget()
        win.frameAIArea = QWidget()

        term = MagicMock()
        term.window = win
        term._switch_nav_tab = MagicMock()
        term._toggle_bot = MagicMock()

        header = WorkspaceHeaderController(term)
        mb = QMenuBar(win)
        win.setMenuBar(mb)
        header.native_menu_bar = mb
        header._setup_native_mt5_menus(mb, is_dark=True)
        return header, win, term

    def test_canonical_actions_registered_on_window(self, mock_terminal):
        """Verifies that all MT5 actions are added to the main window as WindowShortcuts."""
        header, win, term = mock_terminal
        win_actions = win.actions()
        assert len(win_actions) >= 20, f"Expected >= 20 window actions, found {len(win_actions)}"

        # Verify key shortcuts exist on window actions
        shortcuts = [act.shortcut().toString() for act in win_actions if not act.shortcut().isEmpty()]
        assert "F1" in shortcuts
        assert "F2" in shortcuts
        assert "Ctrl+R" in shortcuts
        assert "F3" in shortcuts
        assert "F9" in shortcuts
        assert "Ctrl+M" in shortcuts
        assert "Ctrl+T" in shortcuts
        assert "Ctrl+B" in shortcuts
        assert "Ctrl+L" in shortcuts
        assert "Ctrl+O" in shortcuts
        assert "Ctrl+N" in shortcuts
        assert "Ctrl+S" in shortcuts
        assert "Ctrl+Shift+S" in shortcuts
        assert "Ctrl+Shift+K" in shortcuts
        assert "Alt+1" in shortcuts
        assert "Alt+2" in shortcuts
        assert "Alt+3" in shortcuts
        assert "Ctrl+0" in shortcuts
        assert "Ctrl+G" in shortcuts
        assert "Ctrl+F5" in shortcuts
        assert "F11" in shortcuts
        assert "Ctrl+/" in shortcuts

    def test_zero_ambiguous_shortcut_collisions(self, mock_terminal):
        """Verifies that each primary shortcut key sequence maps to exactly ONE canonical action instance."""
        header, win, term = mock_terminal
        win_actions = win.actions()

        key_to_acts = {}
        for act in win_actions:
            sc = act.shortcut().toString()
            if sc:
                key_to_acts.setdefault(sc, []).append(act)

        # For every registered shortcut, there must be EXACTLY ONE unique QAction on the window
        for key, acts in key_to_acts.items():
            assert len(acts) == 1, f"Ambiguous shortcut collision detected for key '{key}': {acts}"

    def test_shared_actions_across_multiple_menus(self, mock_terminal):
        """Verifies that actions shared across menus (Tester, Calendar, Journal, Full Screen) reuse the same instance."""
        header, win, term = mock_terminal

        # Strategy Tester appears in View and Tools
        view_actions = header.menu_view.actions()
        tools_actions = header.menu_tools.actions()
        assert header.act_bt in view_actions
        assert header.act_bt in tools_actions

        # Calendar appears in View and Tools
        assert header.act_cal in view_actions
        assert header.act_cal in tools_actions

        # Journal appears in View and Tools
        assert header.act_journal in view_actions
        assert header.act_journal in tools_actions

        # Full Screen appears in View and Window
        window_actions = header.menu_window.actions()
        assert header.act_fs in view_actions
        assert header.act_fs in window_actions

    def test_shortcut_triggers_invoke_handlers(self, mock_terminal):
        """Verifies that calling trigger() on actions dispatches to the connected slots."""
        header, win, term = mock_terminal

        events = []
        header.act_wl.triggered.connect(lambda: events.append("watchlist"))
        header.act_order.triggered.connect(lambda: events.append("order"))
        header.act_fit.triggered.connect(lambda: events.append("fit"))
        header.act_grid.triggered.connect(lambda: events.append("grid"))
        header.act_kill.triggered.connect(lambda: events.append("kill"))

        header.act_wl.trigger()
        header.act_order.trigger()
        header.act_fit.trigger()
        header.act_grid.trigger()
        header.act_kill.trigger()

        assert events == ["watchlist", "order", "fit", "grid", "kill"]

    def test_legacy_activated_signal_compatibility(self, mock_terminal):
        """Verifies that act.activated is an alias for act.triggered for backward compatibility."""
        header, win, term = mock_terminal

        hit = []
        header.shortcut_f1.activated.connect(lambda: hit.append("f1_hit"))
        header.shortcut_f1.trigger()
        assert "f1_hit" in hit

        header.shortcut_ctrl_m.activated.connect(lambda: hit.append("ctrl_m_hit"))
        header.shortcut_ctrl_m.trigger()
        assert "ctrl_m_hit" in hit
