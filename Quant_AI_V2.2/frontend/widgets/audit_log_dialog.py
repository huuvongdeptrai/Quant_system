"""
System Journal Dialog for VECTRA.
Clean, institutional floating journal window accessed via Ctrl+L or bottom status bar.
"""

import os
from PySide6.QtWidgets import QDialog, QVBoxLayout, QSizePolicy
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.dirname(CURRENT_DIR)
ASSETS_DIR = os.path.join(FRONTEND_DIR, "assets")


class AuditLogDialog(QDialog):
    """Floating Institutional System Journal Dialog (Ctrl+L)."""

    def __init__(self, parent=None, log_widget=None, log_manager=None, is_dark=False):
        super().__init__(parent)
        self.parent_window = parent
        self.log_widget = log_widget
        self.log_manager = log_manager
        self.is_dark_theme = is_dark

        self.setWindowTitle("System Journal")
        self.resize(1080, 580)
        self.setMinimumSize(780, 400)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        icon_path = os.path.join(ASSETS_DIR, "nav_logs.svg")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._setup_ui()
        self.update_theme(is_dark)

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(4, 4, 4, 4)
        root_layout.setSpacing(0)

        if self.log_widget:
            self.log_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            root_layout.addWidget(self.log_widget, 1)

    def update_theme(self, is_dark: bool):
        self.is_dark_theme = is_dark
        if is_dark:
            self.setStyleSheet("QDialog { background-color: #080b11; }")
        else:
            self.setStyleSheet("QDialog { background-color: #f8fafc; }")

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
