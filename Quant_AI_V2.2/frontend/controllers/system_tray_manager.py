"""
System Tray Manager - Background Execution and Anti-Sleep Management Controller.
Provides seamless minimization to Windows System Tray, anti-sleep OS execution locks,
and quick emergency control actions for institutional background bot operation.
"""

import sys
import ctypes
from pathlib import Path
from typing import Optional

from loguru import logger
from PySide6.QtCore import QObject, Qt, QPoint
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QAction, QKeySequence
from PySide6.QtWidgets import (
    QSystemTrayIcon,
    QMenu,
    QApplication,
    QMessageBox,
)

# Windows API constants for preventing system sleep
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002


class SystemTrayManager(QObject):
    """
    Manages the application's System Tray lifecycle, background execution,
    OS thread execution state (anti-sleep), and quick emergency actions.
    """

    def __init__(self, terminal):
        super().__init__()
        self.terminal = terminal
        self.window = getattr(terminal, "window", None)
        self.is_bot_active = False
        self._keep_awake_active = False
        self.tray_icon: Optional[QSystemTrayIcon] = None
        self.tray_menu: Optional[QMenu] = None

        # Actions
        self.act_title: Optional[QAction] = None
        self.act_status: Optional[QAction] = None
        self.act_restore: Optional[QAction] = None
        self.act_toggle_bot: Optional[QAction] = None
        self.act_kill_switch: Optional[QAction] = None
        self.act_exit: Optional[QAction] = None

        self._init_tray()

    def _init_tray(self) -> None:
        """Initializes the QSystemTrayIcon if supported by the host operating system."""
        try:
            if not QSystemTrayIcon.isSystemTrayAvailable():
                logger.warning("[SystemTrayManager] System tray is not available on this platform.")
                return

            self.tray_menu = self._build_context_menu()
            icon = self._render_status_icon(is_active=False)

            self.tray_icon = QSystemTrayIcon(icon, self.window or self)
            self.tray_icon.setContextMenu(self.tray_menu)
            self.tray_icon.setToolTip("VECTRA V2.2 - Institutional Quant Engine\nStatus: STANDBY")
            self.tray_icon.activated.connect(self._on_tray_activated)
            self.tray_icon.show()
            logger.info("[SystemTrayManager] System tray icon initialized successfully.")
        except Exception as e:
            logger.error(f"[SystemTrayManager] Failed to initialize system tray icon: {e}")
            self.tray_icon = None

    def _render_status_icon(self, is_active: bool = False, in_trade: bool = False, is_error: bool = False) -> QIcon:
        """
        Renders a sharp, high-contrast flat tray icon with a dynamic status badge.
        Adheres to institutional design tokens (no gradients, clear status color).
        """
        pix = QPixmap(32, 32)
        pix.fill(Qt.transparent)

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)

        # Base Glyph: Stylized Geometric 'V' (VECTRA)
        # Background dark rounded shield
        painter.setPen(QColor(255, 255, 255, 30))
        painter.setBrush(QColor("#090d16"))
        painter.drawRoundedRect(1, 1, 30, 30, 3, 3)

        # Draw Cyan Chevron/Polygon
        painter.setPen(QColor("#38bdf8"))
        painter.setBrush(Qt.NoBrush)
        pen = painter.pen()
        pen.setWidth(2)
        painter.setPen(pen)

        # Draw 'V'
        painter.drawLine(8, 9, 16, 22)
        painter.drawLine(16, 22, 24, 9)

        # Draw dynamic status badge in bottom-right corner
        badge_color = QColor("#94a3b8")  # Standby Gray
        if is_error:
            badge_color = QColor("#ef4444")  # Coral Red (Circuit breaker)
        elif in_trade:
            badge_color = QColor("#f59e0b")  # Amber / In-Trade
        elif is_active:
            badge_color = QColor("#22c55e")  # Matte Green (Active scanning)

        painter.setPen(QColor("#090d16"))
        painter.setBrush(badge_color)
        painter.drawEllipse(20, 20, 10, 10)

        painter.end()
        return QIcon(pix)

    def _build_context_menu(self) -> QMenu:
        """Constructs an institutional dark-themed flat context menu."""
        menu = QMenu(self.window)
        menu.setObjectName("systemTrayMenu")
        menu.setStyleSheet("""
            QMenu#systemTrayMenu {
                background-color: #070a12;
                color: #e2e8f0;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 2px;
                padding: 4px;
                font-family: 'Segoe UI', 'Consolas', sans-serif;
                font-size: 12px;
            }
            QMenu#systemTrayMenu::item {
                padding: 6px 20px;
                border-radius: 2px;
            }
            QMenu#systemTrayMenu::item:selected {
                background-color: #101524;
                color: #38bdf8;
            }
            QMenu#systemTrayMenu::item:disabled {
                color: #64748b;
            }
            QMenu#systemTrayMenu::separator {
                height: 1px;
                background-color: rgba(255, 255, 255, 0.08);
                margin: 4px 6px;
            }
        """)

        # Header Title (Disabled)
        self.act_title = menu.addAction("VECTRA V2.2 - Quant Engine")
        self.act_title.setEnabled(False)
        font = self.act_title.font()
        font.setBold(True)
        self.act_title.setFont(font)

        # Status Line (Disabled)
        self.act_status = menu.addAction("Status: STANDBY (0 Open Positions)")
        self.act_status.setEnabled(False)

        menu.addSeparator()

        # Restore / Dashboard
        self.act_restore = menu.addAction("Open Dashboard")
        self.act_restore.triggered.connect(self.restore_from_tray)
        font_restore = self.act_restore.font()
        font_restore.setBold(True)
        self.act_restore.setFont(font_restore)

        # Bot Control
        self.act_toggle_bot = menu.addAction("Start Bot Execution")
        self.act_toggle_bot.triggered.connect(self._toggle_bot_execution)

        # Emergency Kill Switch
        self.act_kill_switch = menu.addAction("Emergency Close All (Kill Switch)")
        self.act_kill_switch.triggered.connect(self._trigger_kill_switch)

        menu.addSeparator()

        # Exit
        self.act_exit = menu.addAction("Exit VECTRA Entirely")
        self.act_exit.triggered.connect(self._exit_application)

        return menu

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handles single or double clicks on the tray icon to restore the GUI."""
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.restore_from_tray()

    def minimize_to_tray(self) -> None:
        """
        Hides the primary GUI window, pauses display rendering to save GPU/CPU,
        engages OS anti-sleep protection, and displays a confirmation bubble.
        """
        if not self.window:
            return

        self.window.hide()
        self.set_keep_awake(True)

        if self.tray_icon and self.tray_icon.isVisible():
            self.tray_icon.showMessage(
                "VECTRA V2.2 Running in Background",
                "Trading engine is actively scanning in the background.\nDouble-click this tray icon anytime to restore the dashboard.",
                QSystemTrayIcon.MessageIcon.Information,
                3500,
            )
        logger.info("[SystemTrayManager] Dashboard hidden. Running headless in background with Anti-Sleep lock.")

    def restore_from_tray(self) -> None:
        """Restores and focuses the main application window."""
        if not self.window:
            return

        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

        # If bot is not actively running, release anti-sleep lock
        if not self.is_bot_active:
            self.set_keep_awake(False)

        logger.info("[SystemTrayManager] Dashboard restored to active foreground.")

    def update_bot_status(
        self,
        is_active: bool,
        open_positions: int = 0,
        circuit_breaker: bool = False,
        detail_msg: str = "",
    ) -> None:
        """
        Dynamically updates the tray icon badge, tooltip, and menu actions
        to reflect the real-time execution state of the backend engine.
        """
        self.is_bot_active = is_active

        # Update Tray Icon
        in_trade = (open_positions > 0)
        new_icon = self._render_status_icon(
            is_active=is_active,
            in_trade=in_trade,
            is_error=circuit_breaker,
        )
        if self.tray_icon:
            self.tray_icon.setIcon(new_icon)

        # Update Menu Status Action
        status_label = "ACTIVE" if is_active else "STANDBY"
        if circuit_breaker:
            status_label = "HALTED (CIRCUIT BREAKER)"
        
        status_text = f"Status: {status_label} ({open_positions} Positions)"
        if self.act_status:
            self.act_status.setText(status_text)

        # Update Toggle Action text
        if self.act_toggle_bot:
            if is_active:
                self.act_toggle_bot.setText("Pause Bot Execution")
            else:
                self.act_toggle_bot.setText("Start Bot Execution")

        # Update Tooltip
        tooltip_lines = [
            "VECTRA V2.2 - Institutional Quant Engine",
            f"Engine: {status_label}",
            f"Positions: {open_positions}",
        ]
        if detail_msg:
            tooltip_lines.append(detail_msg)
        if self.tray_icon:
            self.tray_icon.setToolTip("\n".join(tooltip_lines))

        # Maintain anti-sleep lock if bot is actively running
        if is_active:
            self.set_keep_awake(True)

    def set_keep_awake(self, enabled: bool = True) -> None:
        """
        Engages or releases Windows SetThreadExecutionState to prevent the OS
        from sleeping or suspending network sockets while bot is executing.
        """
        if sys.platform != "win32":
            return

        if getattr(self, "_keep_awake_active", None) == enabled:
            return

        try:
            if enabled:
                # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
                self._keep_awake_active = True
                logger.debug("[SystemTrayManager] OS Anti-Sleep lock engaged (ES_SYSTEM_REQUIRED).")
            else:
                # Restore default OS sleep timer
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
                self._keep_awake_active = False
                logger.debug("[SystemTrayManager] OS Anti-Sleep lock released.")
        except Exception as e:
            logger.warning(f"[SystemTrayManager] Could not update SetThreadExecutionState: {e}")

    def _toggle_bot_execution(self) -> None:
        """Toggles bot on/off via the main QuantTerminal controller."""
        if hasattr(self.terminal, "_toggle_bot"):
            self.terminal._toggle_bot()

    def _trigger_kill_switch(self) -> None:
        """Triggers emergency closure of all active positions."""
        if hasattr(self.terminal, "header") and hasattr(self.terminal.header, "_trigger_kill_switch"):
            self.terminal.header._trigger_kill_switch()
        elif hasattr(self.terminal, "exec_mgr"):
            try:
                self.terminal.exec_mgr.close_all_positions()
            except Exception as e:
                logger.error(f"[SystemTrayManager] Emergency close all failed: {e}")

    def _exit_application(self) -> None:
        """Cleanly releases locks and terminates the entire application."""
        self.set_keep_awake(False)
        if self.tray_icon:
            self.tray_icon.hide()

        app = QApplication.instance()
        if app:
            app.quit()
