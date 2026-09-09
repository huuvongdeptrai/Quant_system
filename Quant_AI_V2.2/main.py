import sys, os
from infrastructure.brokers.mt5_safe import mt5
from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QTimer, QFile, QIODevice, QObject
from PySide6.QtUiTools import QUiLoader
from ui.chart_components import setup_chart_ui
from core.event_bus import event_bus
from core.bot_worker import BotWorker
from ui.settings_manager import SettingsManager
from ui.watchlist_manager import WatchlistManager
from ui.log_manager import LogManager
from ui.account_manager import AccountManager
from ui.stats_manager import StatsManager
from ui.calendar_manager import CalendarManager
from ui.backtest_tab import setup_backtest_tab

_TXT_CONNECTED    = '<span style="color:#9CA3AF;font-family:Consolas,monospace;font-size:12px;">Tài Khoản: {}</span> <span style="color:#4B5563;font-size:12px;">|</span> <span style="color:#10B981;font-weight:bold;font-size:12px;">START SYSTEM</span>'
_TXT_DISCONNECTED = '<span style="color:#9CA3AF;font-family:Consolas,monospace;font-size:12px;">Tài Khoản: Trống</span> <span style="color:#4B5563;font-size:12px;">|</span> <span style="color:#F23645;font-weight:bold;font-size:12px;">ngắt kết nối</span>'
_TXT_START        = 'START SYSTEM'
_TXT_STOP         = 'STOP SYSTEM'
_CSS_START = 'QPushButton{background:transparent;color:#10B981;border:1px solid #10B981;padding:8px 18px;border-radius:6px;font-weight:bold;font-size:12px;}QPushButton:hover{background:rgba(16,185,129,0.15);}'
_CSS_STOP  = 'QPushButton{background:transparent;color:#F23645;border:1px solid #F23645;padding:8px 18px;border-radius:6px;font-weight:bold;font-size:12px;}QPushButton:hover{background:rgba(242,54,69,0.15);}'
_CSS_GREEN = 'margin-right:20px;'
_CSS_RED   = 'margin-right:20px;'


class QuantTerminal(QObject):
    def __init__(self):
        super().__init__()
        self._load_ui()
        self.settings  = SettingsManager(self.window)
        self.watchlist = WatchlistManager(self.window)
        self.logs      = LogManager(self.window)
        self.account   = AccountManager(self.window)
        self.stats     = StatsManager(self.window)
        self.calendar  = CalendarManager(self.window)
        setup_chart_ui(self.window)
        setup_backtest_tab(self.window)
        self._setup_corner_widget()
        self.window.tabWidget.currentChanged.connect(self._on_tab_changed)
        self.bot_thread = None
        self._tick_timer = QTimer()
        self._tick_timer.timeout.connect(self._on_tick)
        self._tick_timer.start(1000)
        if hasattr(self.window, 'frameChartArea'):
            setup_chart_ui(self.window)
        self.window.show()

    def _load_ui(self):
        ui_file = QFile(os.path.join(os.path.dirname(__file__), 'quant_ai.ui'))
        ui_file.open(QIODevice.OpenModeFlag.ReadOnly)
        self.window = QUiLoader().load(ui_file, None)
        ui_file.close()
        self.window.closeEvent = self.closeEvent
        self.window.mainSplitter.setSizes([260, 1040])

    def _setup_corner_widget(self):
        corner = QWidget()
        layout = QHBoxLayout(corner)
        layout.setContentsMargins(0, 0, 15, 0)
        self.lbl_status = QLabel(_TXT_DISCONNECTED)
        self.lbl_status.setStyleSheet(_CSS_RED)
        self.btnStart = QPushButton(_TXT_START)
        self.btnStart.setStyleSheet(_CSS_START)
        layout.addWidget(self.lbl_status)
        layout.addWidget(self.btnStart)
        self.window.tabWidget.setCornerWidget(corner, Qt.TopRightCorner)
        self.btnStart.clicked.connect(self._toggle_bot)

    def _on_tick(self):
        if mt5.terminal_info() is None:
            self.lbl_status.setText(_TXT_DISCONNECTED)
            self.lbl_status.setStyleSheet(_CSS_RED)
            return
        acc = mt5.account_info()
        if acc:
            self.lbl_status.setText(_TXT_CONNECTED.format(acc.login))
            self.lbl_status.setStyleSheet(_CSS_GREEN)
            if hasattr(self.window, 'valBalance'):
                self.window.valBalance.setText(f'$ {acc.balance:,.2f}')
                self.window.valBalance.setStyleSheet("color: white; font-weight: bold;")
                
                eq_color = '#10B981' if acc.equity >= acc.balance else '#F23645'
                self.window.valEquity.setText(f'$ {acc.equity:,.2f}')
                self.window.valEquity.setStyleSheet(f"color: {eq_color}; font-weight: bold;")
        for sym in self.watchlist.get_all_symbols():
            tick = mt5.symbol_info_tick(sym)
            if tick:
                event_bus.market_tick.emit(sym, tick.bid, tick.ask)

    def _toggle_bot(self):
        if mt5.terminal_info() is None:
            event_bus.log_event.emit('', 'ERROR', 'Ch\u01b0a k\u1ebft n\u1ed1i MT5!', '#F23645')
            return
        if self.bot_thread is None or not self.bot_thread.isRunning():
            tf = self.window.comboTimeframe.currentData() if hasattr(self.window, 'comboTimeframe') else mt5.TIMEFRAME_M15
            strategy = self.window.comboStrategy.currentData() if hasattr(self.window, 'comboStrategy') else 'ICT'
            ai_model = self.window.comboAIModel.currentText() if hasattr(self.window, 'comboAIModel') else 'qwen2.5'
            
            # Khởi tạo các thành phần cốt lõi và tiêm (inject) vào BotWorker
            from core.risk_manager import RiskManager
            from infrastructure.brokers.execution_manager import ExecutionManager
            from core.preprocessor import DataPreprocessor
            from core.ict_strategy import ICTZonesProStrategy
            from infrastructure.ai_engines.ai.decision_gate import DecisionGate
            from core.bot_worker import DEFAULT_LOOKBACK_BARS
            
            risk_mgr = RiskManager(default_risk_pct=1.0)
            exec_mgr = ExecutionManager()
            prep = DataPreprocessor()
            ict_strat = ICTZonesProStrategy(config={'lookback_bars': DEFAULT_LOOKBACK_BARS})
            gate = DecisionGate()
            
            self.bot_thread = BotWorker(
                strategy=ict_strat, risk_manager=risk_mgr, execution_manager=exec_mgr, 
                data_preprocessor=prep, decision_gate=gate,
                symbols=['XAUUSD'], timeframe=tf, strategy_name=strategy, ai_model_name=ai_model
            )
            self.bot_thread.signals.log_msg.connect(event_bus.log_event.emit)
            if hasattr(self.window, 'comboBias'):
                self.bot_thread.trade_mode = self.window.comboBias.currentData()
            self.bot_thread.start()
            self.btnStart.setText(_TXT_STOP)
            self.btnStart.setStyleSheet(_CSS_STOP)
        else:
            self.bot_thread.stop()
            self.bot_thread.wait()
            self.bot_thread = None
            self.btnStart.setText(_TXT_START)
            self.btnStart.setStyleSheet(_CSS_START)

    def _on_tab_changed(self, index):
        if index == 2:
            self.stats.refresh()

    def closeEvent(self, event):
        if self._tick_timer.isActive():
            self._tick_timer.stop()
        if self.bot_thread and self.bot_thread.isRunning():
            self.bot_thread.stop()
            self.bot_thread.terminate()
            self.bot_thread.wait()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    terminal = QuantTerminal()
    sys.exit(app.exec())
