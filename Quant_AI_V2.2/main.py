import sys, os

from infrastructure.brokers.mt5_safe import mt5

from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout, QLabel, QPushButton

from PySide6.QtGui import QFont

from PySide6.QtCore import Qt, QTimer, QFile, QIODevice, QObject, QThread

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

from infrastructure.notifications.telegram_notifier import telegram_notifier

_TXT_CONNECTED = '<span style="color:#10B981;font-weight:bold;font-family:Consolas,monospace;font-size:12px;">● CONNECTED: {}</span>'

_TXT_DISCONNECTED = '<span style="color:#9CA3AF;font-family:Consolas,monospace;font-size:12px;">Tài Khoản: Trống</span> <span style="color:#4B5563;font-size:12px;">|</span> <span style="color:#F23645;font-weight:bold;font-size:12px;">ngắt kết nối</span>'

_TXT_START = "START SYSTEM"

_TXT_STOP = "STOP SYSTEM"

_CSS_START = "QPushButton{background:transparent;color:#10B981;border:1px solid #10B981;padding:8px 18px;border-radius:6px;font-weight:bold;font-size:12px;}QPushButton:hover{background:rgba(16,185,129,0.15);}"

_CSS_STOP = "QPushButton{background:transparent;color:#F23645;border:1px solid #F23645;padding:8px 18px;border-radius:6px;font-weight:bold;font-size:12px;}QPushButton:hover{background:rgba(242,54,69,0.15);}"

_CSS_GREEN = "margin-right:20px;"

_CSS_RED = "margin-right:20px;"


class QuantTerminal(QObject):

    def __init__(self):

        super().__init__()

        self._load_ui()

        self.settings = SettingsManager(self.window)

        self.watchlist = WatchlistManager(self.window)

        self.logs = LogManager(self.window)

        self.account = AccountManager(self.window)

        self.stats = StatsManager(self.window)

        self.calendar = CalendarManager(self.window)

        setup_chart_ui(self.window)

        setup_backtest_tab(self.window)

        self._setup_corner_widget()

        self.window.tabWidget.currentChanged.connect(self._on_tab_changed)

        self.bot_thread = None

        self.bot_worker = None

        self._tick_timer = QTimer()

        self._tick_timer.timeout.connect(self._on_tick)

        self._tick_timer.start(1000)

        telegram_notifier.start_listening(event_bus)

        event_bus.remote_command.connect(self._handle_remote_command)

        # frameChartArea setup handled by setup_chart_ui above

        self.window.show()

    def _load_ui(self):

        ui_file = QFile(os.path.join(os.path.dirname(__file__), "quant_ai.ui"))

        ui_file.open(QIODevice.OpenModeFlag.ReadOnly)

        self.window = QUiLoader().load(ui_file, None)

        ui_file.close()

        # Load Global QSS Theme

        qss_path = os.path.join(os.path.dirname(__file__), "ui", "style.qss")

        if os.path.exists(qss_path):

            with open(qss_path, "r", encoding="utf-8") as f:

                self.window.setStyleSheet(f.read())

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

            if hasattr(self.window, "labelStatus"):

                self.window.labelStatus.setText("● CHƯA KẾT NỐI")

                self.window.labelStatus.setStyleSheet(
                    "color: #F23645; font-weight: bold; font-size: 11px;"
                )

            return

        acc = mt5.account_info()

        if acc:

            self.lbl_status.setText(_TXT_CONNECTED.format(acc.login))

            self.lbl_status.setStyleSheet(_CSS_GREEN)

            # Đồng bộ Sidebar trái dưới

            if hasattr(self.window, "labelStatus"):

                self.window.labelStatus.setText(f"● CONNECTED: {acc.login}")

                self.window.labelStatus.setStyleSheet(
                    "color: #10B981; font-weight: bold; font-size: 11px;"
                )

            if hasattr(self.window, "valBalance"):

                self.window.valBalance.setText(f"${acc.balance:,.2f}")

                eq_color = "#10B981" if acc.equity >= acc.balance else "#F23645"

                self.window.valEquity.setText(f"${acc.equity:,.2f}")

                self.window.valEquity.setStyleSheet(
                    f"color: {eq_color}; font-family: 'Consolas', monospace; font-size: 14px; font-weight: bold;"
                )

            if hasattr(self.window, "valMargin"):

                margin_pct = (acc.margin / acc.equity * 100) if acc.equity > 0 else 0

                margin_color = (
                    "#10B981"
                    if margin_pct < 50
                    else "#F2C94C" if margin_pct < 80 else "#F23645"
                )

                self.window.valMargin.setText(f"{margin_pct:.2f}%")

                self.window.valMargin.setStyleSheet(
                    f"color: {margin_color}; font-family: 'Consolas', monospace; font-size: 14px; font-weight: bold;"
                )

        for sym in self.watchlist.get_all_symbols():

            tick = mt5.symbol_info_tick(sym)

            if tick:

                event_bus.market_tick.emit(sym, tick.bid, tick.ask)

    def _handle_remote_command(self, cmd):

        if cmd == "STOP" and self.bot_thread and self.bot_thread.isRunning():

            self._toggle_bot()

        elif cmd == "START" and (
            self.bot_thread is None or not self.bot_thread.isRunning()
        ):

            self._toggle_bot()

    def _toggle_bot(self):

        if mt5.terminal_info() is None:

            event_bus.log_event.emit(
                "", "ERROR", "Ch\u01b0a k\u1ebft n\u1ed1i MT5!", "#F23645"
            )

            return

        if self.bot_thread is None or not self.bot_thread.isRunning():

            tf = (
                self.window.comboTimeframe.currentData()
                if hasattr(self.window, "comboTimeframe")
                else mt5.TIMEFRAME_M15
            )

            strategy = (
                self.window.comboStrategy.currentData()
                if hasattr(self.window, "comboStrategy")
                else "ICT"
            )

            ai_model = (
                self.window.comboAIModel.currentText()
                if hasattr(self.window, "comboAIModel")
                else "qwen2.5"
            )

            gate_mode = (
                self.window.comboGateMode.currentData()
                if hasattr(self.window, "comboGateMode")
                else "FULL"
            )

            news_filter = (
                self.window.chkNewsFilter.isChecked()
                if hasattr(self.window, "chkNewsFilter")
                else True
            )

            news_pause_mins = (
                self.window.spinNewsPause.value()
                if hasattr(self.window, "spinNewsPause")
                else 30
            )

            slippage = (
                self.window.spinSlippage.value()
                if hasattr(self.window, "spinSlippage")
                else 20
            )

            # Khởi tạo các thành phần cốt lõi và tiêm (inject) vào BotWorker

            from core.risk_manager import RiskManager

            from infrastructure.brokers.execution_manager import ExecutionManager

            from core.preprocessor import DataPreprocessor

            from core.strategies.ict_strategy import ICTZonesProStrategy

            from core.strategies.ema_stress_test import EMAStressTestStrategy

            from infrastructure.ai_engines.ai.decision_gate import DecisionGate

            from core.bot_worker import DEFAULT_LOOKBACK_BARS

            risk_mgr = RiskManager(default_risk_pct=1.0)

            exec_mgr = ExecutionManager(slippage=slippage)

            prep = DataPreprocessor()

            if strategy == "EMA_TEST":

                active_strat = EMAStressTestStrategy(
                    config={"fast_period": 10, "slow_period": 50}
                )

            else:

                active_strat = ICTZonesProStrategy(
                    config={"lookback_bars": DEFAULT_LOOKBACK_BARS}
                )

            gate = DecisionGate()

            # Get UI Values

            r_risk = (
                self.window.spinRiskPerTrade.value()
                if hasattr(self.window, "spinRiskPerTrade")
                else 1.0
            )

            r_maxdd = (
                self.window.spinMaxDrawdown.value()
                if hasattr(self.window, "spinMaxDrawdown")
                else 5.0
            )

            r_maxloss = (
                self.window.spinMaxLosingStreak.value()
                if hasattr(self.window, "spinMaxLosingStreak")
                else 3
            )

            r_trail = (
                self.window.spinTrailingPips.value()
                if hasattr(self.window, "spinTrailingPips")
                else 15
            )

            r_be = (
                self.window.spinBreakevenPips.value()
                if hasattr(self.window, "spinBreakevenPips")
                else 10
            )

            # Sessions

            allowed_sessions = []

            if (
                hasattr(self.window, "chkSessionAsian")
                and self.window.chkSessionAsian.isChecked()
            ):
                allowed_sessions.append("ASIAN")

            if (
                hasattr(self.window, "chkSessionLondon")
                and self.window.chkSessionLondon.isChecked()
            ):
                allowed_sessions.append("LONDON")

            if (
                hasattr(self.window, "chkSessionNY")
                and self.window.chkSessionNY.isChecked()
            ):
                allowed_sessions.append("NY")

            self.bot_worker = BotWorker(
                strategy=active_strat,
                risk_manager=risk_mgr,
                execution_manager=exec_mgr,
                data_preprocessor=prep,
                decision_gate=gate,
                symbols=self.watchlist.get_all_symbols() or ["XAUUSD"],
                timeframe=tf,
                strategy_name=strategy,
                ai_model_name=ai_model,
                gate_mode=gate_mode,
                news_filter_enabled=news_filter,
                news_pause_mins=news_pause_mins,
                slippage=slippage,
                risk_per_trade=r_risk,
                max_drawdown=r_maxdd,
                max_losing_streak=r_maxloss,
                trailing_pips=r_trail,
                breakeven_pips=r_be,
                allowed_sessions=allowed_sessions,
            )

            self.bot_worker.signals.log_msg.connect(event_bus.log_event.emit)

            if hasattr(self.window, "comboBias"):

                self.bot_worker.trade_mode = self.window.comboBias.currentData()

            self.bot_thread = QThread()

            self.bot_worker.moveToThread(self.bot_thread)

            self.bot_thread.started.connect(self.bot_worker.start_working)

            self.bot_thread.start()

            self.btnStart.setText(_TXT_STOP)

            self.btnStart.setStyleSheet(_CSS_STOP)

            # --- GỬI THÔNG BÁO TELEGRAM CHI TIẾT ---

            tf_name = (
                self.window.comboTimeframe.currentText()
                if hasattr(self.window, "comboTimeframe")
                else "M15"
            )

            strat_name = (
                self.window.comboStrategy.currentText()
                if hasattr(self.window, "comboStrategy")
                else "ICT"
            )

            ai_name = (
                self.window.comboAIModel.currentText()
                if hasattr(self.window, "comboAIModel")
                else "qwen2.5"
            )

            gate_mode_display = (
                self.window.comboGateMode.currentText()
                if hasattr(self.window, "comboGateMode")
                else "Day du"
            )

            msg = (
                f"🟢 <b>[HỆ THỐNG KHỞI ĐỘNG]</b>\n"
                f"Bot giao dịch đã được bật thành công!\n\n"
                f"⚙️ <b>Cấu hình hiện tại:</b>\n"
                f"🔹 Cặp giao dịch: XAUUSD\n"
                f"🔹 Khung thời gian: {tf_name}\n"
                f"🔹 Chiến lược: {strat_name}\n"
                f"🔹 Chế độ Bộ lọc: {gate_mode_display}\n"
                f"🔹 Mô hình AI: {ai_name}\n"
                f"🔹 Quản lý rủi ro: 1.0% / Lệnh\n\n"
                f"<i>Chờ tín hiệu từ thị trường...</i>"
            )

            telegram_notifier.send_message(msg)

        else:

            if self.bot_worker:

                self.bot_worker.stop()

            if self.bot_thread:

                self.bot_thread.quit()

                self.bot_thread.wait()

            self.bot_thread = None

            self.bot_worker = None

            telegram_notifier.send_message(
                "🛑 <b>[HỆ THỐNG TẠM DỪNG]</b>\nBot đã được tắt an toàn."
            )

            self.btnStart.setText(_TXT_START)

            self.btnStart.setStyleSheet(_CSS_START)

    def _on_tab_changed(self, index):

        if index == 2:

            self.stats.refresh()

    def closeEvent(self, event):
        if self._tick_timer.isActive():
            self._tick_timer.stop()
        if self.bot_thread and self.bot_thread.isRunning():
            if self.bot_worker:
                self.bot_worker.stop()
            if self.bot_thread:
                self.bot_thread.quit()
                self.bot_thread.wait(1000)
        # Cho phep cac luong AI hoan tat truoc khi giai phong de tranh warning
        if (
            hasattr(self.window, "ai_thread")
            and self.window.ai_thread
            and self.window.ai_thread.isRunning()
        ):
            self.window.ai_thread.stop()
            self.window.ai_thread.quit()
            self.window.ai_thread.wait(1000)
        event.accept()


if __name__ == "__main__":

    app = QApplication(sys.argv)

    app.setFont(QFont("Segoe UI", 10))

    from ui.splash_screen import SplashScreen, InitWorker

    splash = SplashScreen()

    splash.show()

    worker = InitWorker()

    worker.progress.connect(splash.update_progress)

    def on_init_finished():

        global terminal

        terminal = QuantTerminal()

        splash.close()

    worker.init_done.connect(on_init_finished)

    worker.start()

    sys.exit(app.exec())
