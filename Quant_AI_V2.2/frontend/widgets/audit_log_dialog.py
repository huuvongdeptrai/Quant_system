"""
Institutional System Audit & Execution Journal Dialog for VECTRA V2.2.
Floating audit monitor providing instant event stream access via Ctrl+L or Telemetry pill.
"""

import os
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QIcon, QColor, QKeySequence, QShortcut

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.dirname(CURRENT_DIR)
ASSETS_DIR = os.path.join(FRONTEND_DIR, "assets")


class AuditLogDialog(QDialog):
    """Floating Institutional Audit Trail & Journal Dialog (Ctrl+L)."""

    def __init__(self, parent=None, log_widget=None, log_manager=None, is_dark=False):
        super().__init__(parent)
        self.parent_window = parent
        self.log_widget = log_widget
        self.log_manager = log_manager
        self.is_dark_theme = is_dark

        self.setWindowTitle("VECTRA - System Audit & Execution Journal")
        self.resize(1120, 620)
        self.setMinimumSize(820, 440)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        icon_path = os.path.join(ASSETS_DIR, "nav_logs.svg")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._setup_ui()
        self.update_theme(is_dark)

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(4)

        # 1. Institutional Top Strip Header
        self.header_frame = QFrame(self)
        self.header_frame.setObjectName("auditDialogHeader")
        self.header_frame.setFixedHeight(30)
        hdr_layout = QHBoxLayout(self.header_frame)
        hdr_layout.setContentsMargins(10, 0, 8, 0)
        hdr_layout.setSpacing(8)

        # Pulse indicator dot
        self.dot_status = QFrame(self.header_frame)
        self.dot_status.setFixedSize(6, 6)
        self.dot_status.setStyleSheet("background-color: #10b981; border-radius: 3px;")
        hdr_layout.addWidget(self.dot_status)

        # Title
        self.lbl_title = QLabel("SYSTEM AUDIT & EXECUTION JOURNAL", self.header_frame)
        self.lbl_title.setFont(QFont("Consolas", 9, QFont.Bold))
        hdr_layout.addWidget(self.lbl_title)

        # Subtitle badge
        self.lbl_badge = QLabel("WAL LOGGING · REALTIME EVENT BUS", self.header_frame)
        self.lbl_badge.setFont(QFont("Segoe UI", 8, QFont.Medium))
        hdr_layout.addWidget(self.lbl_badge)

        hdr_layout.addStretch()

        # Keyboard hint
        self.lbl_hint = QLabel("Shortcuts: [Ctrl+L] Toggle   |   [Esc] Close", self.header_frame)
        self.lbl_hint.setFont(QFont("Consolas", 8))
        hdr_layout.addWidget(self.lbl_hint)

        root_layout.addWidget(self.header_frame)

        # 2. Body Area - Embeds Tab 4 directly
        if self.log_widget:
            self.log_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            root_layout.addWidget(self.log_widget, 1)

    def update_theme(self, is_dark: bool):
        self.is_dark_theme = is_dark
        if is_dark:
            self.setStyleSheet(
                "QDialog { background-color: #080b11; border: 1px solid #1e2430; }"
            )
            self.header_frame.setStyleSheet(
                "QFrame#auditDialogHeader { background-color: #0d121f; border: 1px solid #1e293b; border-radius: 2px; }"
            )
            self.lbl_title.setStyleSheet("color: #f8fafc; font-size: 9.5px; font-weight: 700; letter-spacing: 0.5px;")
            self.lbl_badge.setStyleSheet(
                "color: #38bdf8; background-color: rgba(56, 189, 248, 0.1); border: 1px solid rgba(56, 189, 248, 0.2); "
                "border-radius: 2px; padding: 1px 5px; font-size: 8.5px; font-weight: 600;"
            )
            self.lbl_hint.setStyleSheet("color: #64748b; font-size: 8.5px;")
            self.dot_status.setStyleSheet("background-color: #10b981; border-radius: 3px;")
        else:
            self.setStyleSheet(
                "QDialog { background-color: #f8fafc; border: 1px solid #cbd5e1; }"
            )
            self.header_frame.setStyleSheet(
                "QFrame#auditDialogHeader { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 2px; }"
            )
            self.lbl_title.setStyleSheet("color: #0f172a; font-size: 9.5px; font-weight: 700; letter-spacing: 0.5px;")
            self.lbl_badge.setStyleSheet(
                "color: #0284c7; background-color: rgba(2, 132, 199, 0.08); border: 1px solid rgba(2, 132, 199, 0.2); "
                "border-radius: 2px; padding: 1px 5px; font-size: 8.5px; font-weight: 600;"
            )
            self.lbl_hint.setStyleSheet("color: #64748b; font-size: 8.5px;")
            self.dot_status.setStyleSheet("background-color: #15803d; border-radius: 3px;")

        if self.log_manager and hasattr(self.log_manager, "update_theme"):
            self.log_manager.update_theme(is_dark, update_dialog=False)

    def open_dialog(self):
        """Centers and brings the dialog to the front."""
        if self.parent_window:
            geo = self.parent_window.geometry()
            x = geo.x() + max(0, (geo.width() - self.width()) // 2)
            y = geo.y() + max(0, (geo.height() - self.height()) // 2)
            self.move(x, y)

        self.show()
        self.raise_()
        self.activateWindow()
        return self

    def toggle_dialog(self):
        """Toggles the visibility of the dialog."""
        if self.isVisible():
            self.hide()
        else:
            self.open_dialog()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
            event.accept()
        elif (event.modifiers() == Qt.ControlModifier) and (event.key() == Qt.Key_L):
            self.close()
            event.accept()
        else:
            super().keyPressEvent(event)
