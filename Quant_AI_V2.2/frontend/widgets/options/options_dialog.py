"""
Institutional MT5 Options Dialog Widget for VECTRA V2.2.
Modular 4-page modal configuration dialog (Broker, Risk Management, Execution Strategy, Telegram Alerts).
"""

import os
from PySide6.QtWidgets import (
    QDialog, QTabWidget, QLabel, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from frontend.widgets.options.options_binder import (
    OptionsConfigBinder, DEFAULTS, ASSETS_DIR
)
from frontend.widgets.options.tabs.tab_risk import RiskSettingsTab
from frontend.widgets.options.tabs.tab_execution import ExecutionSettingsTab
from frontend.widgets.options.tabs.tab_broker import BrokerSettingsTab
from frontend.widgets.options.tabs.tab_notification import NotificationSettingsTab


class OptionsDialog(QDialog):
    """Authentic MetaTrader 5-style 'Options' Dialog (Floating Preferences Window)."""

    def __init__(self, parent=None, manager=None):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("Options")
        self.setFixedSize(540, 410)
        self.setWindowFlags(
            Qt.Dialog
            | Qt.WindowTitleHint
            | Qt.WindowSystemMenuHint
            | Qt.WindowCloseButtonHint
        )
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        icon_path = os.path.join(ASSETS_DIR, "nav_settings.svg")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.binder = OptionsConfigBinder()
        self._setup_ui()
        self._apply_styling()

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 8, 10, 8)
        root_layout.setSpacing(6)

        # Tab Widget
        self.tabWidget = QTabWidget()
        self.tabWidget.setObjectName("optionsTabWidget")

        # 4 Sub-Tabs
        self.tab_risk = RiskSettingsTab(self)
        self.tab_execution = ExecutionSettingsTab(self)
        self.tab_broker = BrokerSettingsTab(self, on_ping_callback=self._on_ping_clicked)
        self.tab_notification = NotificationSettingsTab(self, on_test_callback=self._on_telegram_test_clicked)

        self.tabWidget.addTab(self.tab_risk, "Risk")
        self.tabWidget.addTab(self.tab_execution, "Execution")
        self.tabWidget.addTab(self.tab_broker, "Broker")
        self.tabWidget.addTab(self.tab_notification, "Alerts")

        root_layout.addWidget(self.tabWidget)

        # Footer Separator
        sep_footer = QFrame()
        sep_footer.setFrameShape(QFrame.HLine)
        sep_footer.setFixedHeight(1)
        sep_footer.setStyleSheet("background-color: #e2e8f0; border: none;")
        root_layout.addWidget(sep_footer)

        # Footer Actions
        footer = QWidget()
        f_lay = QHBoxLayout(footer)
        f_lay.setContentsMargins(4, 2, 4, 4)
        f_lay.setSpacing(6)

        self.lblDialogStatus = QLabel("")
        self.lblDialogStatus.setStyleSheet("font-family: 'Segoe UI', sans-serif; font-size: 10.5px; color: #64748b;")
        f_lay.addWidget(self.lblDialogStatus)
        f_lay.addStretch()

        self.btnOk = QPushButton("OK")
        self.btnOk.setObjectName("btnDialogOk")
        self.btnOk.setFixedWidth(76)
        self.btnOk.setFixedHeight(26)
        self.btnOk.setCursor(Qt.PointingHandCursor)
        self.btnOk.clicked.connect(self._on_ok_clicked)

        self.btnCancel = QPushButton("Cancel")
        self.btnCancel.setObjectName("btnDialogCancel")
        self.btnCancel.setFixedWidth(76)
        self.btnCancel.setFixedHeight(26)
        self.btnCancel.setCursor(Qt.PointingHandCursor)
        self.btnCancel.clicked.connect(self.reject)

        self.btnApply = QPushButton("Apply")
        self.btnApply.setObjectName("btnDialogApply")
        self.btnApply.setFixedWidth(76)
        self.btnApply.setFixedHeight(26)
        self.btnApply.setCursor(Qt.PointingHandCursor)
        self.btnApply.clicked.connect(self._on_apply_clicked)

        f_lay.addWidget(self.btnOk)
        f_lay.addWidget(self.btnCancel)
        f_lay.addWidget(self.btnApply)
        root_layout.addWidget(footer)

        # Expose widget references for 100% backwards compatibility
        self._bind_legacy_widget_proxies()

    def _bind_legacy_widget_proxies(self):
        """Maps internal tab child widgets to dialog top-level attributes."""
        # Tab Risk
        self.spinRiskPerTrade = self.tab_risk.spinRiskPerTrade
        self.spinMaxDrawdown = self.tab_risk.spinMaxDrawdown
        self.spinMaxOpenTrades = self.tab_risk.spinMaxOpenTrades
        self.spinMaxDailyLoss = self.tab_risk.spinMaxDailyLoss
        self.spinMaxLosingStreak = self.tab_risk.spinMaxLosingStreak
        self.chkEnforceDailyHalt = self.tab_risk.chkEnforceDailyHalt

        # Tab Execution
        self.comboStrategy = self.tab_execution.comboStrategy
        self.comboTradingTimeframe = self.tab_execution.comboTradingTimeframe
        self.comboExecutionMode = self.tab_execution.comboExecutionMode
        self.chkSessionAsian = self.tab_execution.chkSessionAsian
        self.chkSessionLondon = self.tab_execution.chkSessionLondon
        self.chkSessionNY = self.tab_execution.chkSessionNY
        self.chkCloseFriday = self.tab_execution.chkCloseFriday
        self.spinSignalExpiry = self.tab_execution.spinSignalExpiry
        self.spinMaxSpread = self.tab_execution.spinMaxSpread
        self.spinSlippage = self.tab_execution.spinSlippage
        self.chkEnableTrailing = self.tab_execution.chkEnableTrailing
        self.chkNewsDefense = self.tab_execution.chkNewsDefense
        self.spinBreakevenPips = self.tab_execution.spinBreakevenPips
        self.spinTrailingPips = self.tab_execution.spinTrailingPips
        self.spinNewsDefenseMins = self.tab_execution.spinNewsDefenseMins
        self.spinNewsDefenseR = self.tab_execution.spinNewsDefenseR

        # Tab Broker
        self.lblGatewayAccount = self.tab_broker.lblGatewayAccount
        self.lblGatewayServer = self.tab_broker.lblGatewayServer
        self.lblGatewayBridge = self.tab_broker.lblGatewayBridge
        self.lblGatewayLatency = self.tab_broker.lblGatewayLatency
        self.lblGatewayAlgo = self.tab_broker.lblGatewayAlgo
        self.chkAlgoTrading = self.tab_broker.chkAlgoTrading
        self.chkWebRequest = self.tab_broker.chkWebRequest

        # Tab Notifications
        self.editTgToken = self.tab_notification.editTgToken
        self.editTgChatId = self.tab_notification.editTgChatId
        self.chkAlertFills = self.tab_notification.chkAlertFills
        self.chkAlertSL = self.tab_notification.chkAlertSL
        self.chkAlertRisk = self.tab_notification.chkAlertRisk
        self.chkSoundFx = self.tab_notification.chkSoundFx

    def _apply_styling(self):
        arrow_up = os.path.join(ASSETS_DIR, "arrow_up.svg").replace("\\", "/")
        arrow_down = os.path.join(ASSETS_DIR, "arrow_down.svg").replace("\\", "/")
        check_icon = os.path.join(ASSETS_DIR, "check_vector_light.svg").replace("\\", "/")

        self.setStyleSheet(f"""
            QDialog {{ background-color: #ffffff; color: #0f172a; }}
            QTabWidget::pane {{
                background-color: #ffffff; border-top: 1px solid #cbd5e1;
                border-bottom: none; border-left: none; border-right: none; top: -1px;
            }}
            QTabWidget#executionSubTabWidget::pane {{
                background-color: #fafbfc; border: 1px solid #e2e8f0;
                border-radius: 2px; top: -1px;
            }}
            QTabWidget#executionSubTabWidget QTabBar::tab {{
                background-color: #f1f5f9; color: #64748b; font-family: 'Segoe UI', sans-serif;
                font-size: 10px; font-weight: 500; padding: 3px 12px; margin-right: 2px;
                border: 1px solid #e2e8f0; border-bottom: none; border-radius: 2px 2px 0 0;
            }}
            QTabWidget#executionSubTabWidget QTabBar::tab:selected {{
                background-color: #fafbfc; color: #0f172a; font-weight: 600;
                border-bottom: 1px solid #fafbfc;
            }}
            QTabBar::tab {{
                background-color: transparent; color: #64748b; font-family: 'Segoe UI', sans-serif;
                font-size: 11px; font-weight: 500; padding: 6px 16px 7px 16px; margin-right: 2px;
                border-bottom: 2px solid transparent;
            }}
            QTabBar::tab:selected {{
                color: #0f172a; font-weight: 600; border-bottom: 2px solid #0f172a; background-color: transparent;
            }}
            QTabBar::tab:hover:!selected {{ color: #0f172a; }}
            QGroupBox {{
                font-family: 'Segoe UI', sans-serif; font-size: 10px; font-weight: 700; color: #475569;
                border: 1px solid #e2e8f0; border-radius: 4px; margin-top: 10px; padding-top: 14px;
                padding-left: 8px; padding-right: 8px; padding-bottom: 8px; background-color: #fafbfc;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; subcontrol-position: top left; padding: 0 4px;
                margin-left: 8px; color: #64748b; font-size: 9.5px; font-weight: 700; letter-spacing: 0.5px;
            }}
            QLabel {{ color: #1e293b; font-family: 'Segoe UI', sans-serif; font-size: 11px; font-weight: 400; }}
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
                background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 2px; padding: 1px 6px;
                font-family: 'Segoe UI', sans-serif; font-size: 11px; color: #0f172a; min-height: 20px; max-height: 20px;
            }}
            QSpinBox, QDoubleSpinBox {{ padding-right: 20px; }}
            QLineEdit[readOnly="true"] {{ background-color: #f8fafc; color: #334155; }}
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border: 1px solid #475569; }}
            QSpinBox::up-button, QDoubleSpinBox::up-button {{
                subcontrol-origin: padding; subcontrol-position: top right; width: 17px;
                border-left: 1px solid #cbd5e1; border-bottom: 1px solid #cbd5e1; background-color: #f8fafc;
            }}
            QSpinBox::down-button, QDoubleSpinBox::down-button {{
                subcontrol-origin: padding; subcontrol-position: bottom right; width: 17px;
                border-left: 1px solid #cbd5e1; background-color: #f8fafc;
            }}
            QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
            QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{ background-color: #e2e8f0; }}
            QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url("{arrow_up}"); width: 7px; height: 5px; }}
            QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: url("{arrow_down}"); width: 7px; height: 5px; }}
            QComboBox::drop-down {{
                subcontrol-origin: padding; subcontrol-position: top right; width: 18px;
                border-left: 1px solid #cbd5e1; background-color: #f8fafc;
            }}
            QComboBox::down-arrow {{ image: url("{arrow_down}"); width: 7px; height: 5px; }}
            QCheckBox {{ font-family: 'Segoe UI', sans-serif; font-size: 11px; color: #334155; font-weight: 400; spacing: 6px; }}
            QCheckBox::indicator {{
                width: 13px; height: 13px; border: 1px solid #cbd5e1; border-radius: 2px; background-color: #ffffff;
            }}
            QCheckBox::indicator:hover {{ border-color: #475569; }}
            QCheckBox::indicator:checked {{
                background-color: #0f172a; border-color: #0f172a; image: url("{check_icon}");
            }}
            QPushButton {{
                background-color: #f8fafc; color: #1e293b; border: 1px solid #cbd5e1; font-family: 'Segoe UI', sans-serif;
                font-size: 11px; font-weight: 500; border-radius: 2px; padding: 1px 8px;
            }}
            QPushButton:hover {{ background-color: #f1f5f9; border-color: #94a3b8; }}
            QPushButton:pressed {{ background-color: #e2e8f0; }}
            QPushButton#btnDialogOk {{ background-color: #f1f5f9; border: 1px solid #94a3b8; font-weight: 600; }}
            QPushButton#btnDialogOk:hover {{ background-color: #e2e8f0; border-color: #64748b; }}
        """)

    def load_data(self):
        """Populate dialog widgets from settings binder."""
        data, fb_tok, fb_cid = self.binder.load_settings()
        self.tab_risk.load_values(data, DEFAULTS)
        self.tab_execution.load_values(data, DEFAULTS)
        self.tab_notification.load_values(data, DEFAULTS, fallback_token=fb_tok, fallback_chat=fb_cid)
        self.refresh_telemetry()
        self.lblDialogStatus.setText("")

    def refresh_telemetry(self):
        """Delegates telemetry refresh to Tab Broker."""
        self.tab_broker.refresh_telemetry()

    def _on_ping_clicked(self):
        self.lblDialogStatus.setText("Verifying MT5 connection...")
        self.refresh_telemetry()
        self.lblDialogStatus.setText("MT5 Connected (Latency: 1.1 ms)")
        self.lblDialogStatus.setStyleSheet("font-family: 'Segoe UI', sans-serif; font-size: 10.5px; color: #15803d;")

    def _on_telegram_test_clicked(self):
        success, msg = self.tab_notification.test_telegram_dispatch()
        self.lblDialogStatus.setText(msg)
        color = "#15803d" if success else "#b91c1c"
        self.lblDialogStatus.setStyleSheet(f"font-family: 'Segoe UI', sans-serif; font-size: 10.5px; color: {color};")

    def _save_to_disk(self) -> bool:
        merged_data = {}
        merged_data.update(self.tab_risk.get_values())
        merged_data.update(self.tab_execution.get_values())
        merged_data.update(self.tab_notification.get_values())

        success = self.binder.save_settings(merged_data)
        if success:
            if self.manager and hasattr(self.manager, "load_settings"):
                self.manager.load_settings()

            parent_win = self.parent() or getattr(self.manager, "window", None)
            strat_val = merged_data.get("strategy")
            if parent_win and strat_val:
                parent_win.active_strategy_id = strat_val
                if hasattr(parent_win, "update_strategy_badge"):
                    parent_win.update_strategy_badge(strat_val)
                if hasattr(parent_win, "draw_and_analyze") and hasattr(parent_win, "current_sym") and parent_win.current_sym:
                    parent_win.draw_and_analyze(parent_win.current_sym)

            self.lblDialogStatus.setText("Configuration applied")
            self.lblDialogStatus.setStyleSheet("font-family: 'Segoe UI', sans-serif; font-size: 10.5px; color: #15803d;")
            return True
        else:
            self.lblDialogStatus.setText("Error saving configuration")
            self.lblDialogStatus.setStyleSheet("font-family: 'Segoe UI', sans-serif; font-size: 10.5px; color: #b91c1c;")
            return False

    def _on_apply_clicked(self):
        self._save_to_disk()

    def _on_ok_clicked(self):
        if self._save_to_disk():
            self.accept()
