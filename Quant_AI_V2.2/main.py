import sys, os

from infrastructure.brokers.mt5_safe import mt5

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QTableWidgetItem,
)

from PySide6.QtGui import QFont, QIcon, QColor

from PySide6.QtCore import Qt, QTimer, QFile, QIODevice, QObject, QThread, QSize

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

_TXT_CONNECTED = "ĐÃ KẾT NỐI: {}"

_TXT_DISCONNECTED = "CHƯA KẾT NỐI MT5"

_TXT_START = "KHỞI CHẠY BOT"

_TXT_STOP = "DỪNG HỆ THỐNG"


class QuantTerminal(QObject):

    def __init__(self):

        super().__init__()

        self._load_ui()

        self._setup_navigation_rail()

        self._setup_corner_widget()

        self.settings = SettingsManager(self.window)

        self.watchlist = WatchlistManager(self.window)

        self.logs = LogManager(self.window)

        self.account = AccountManager(self.window)

        self.stats = StatsManager(self.window)

        self.calendar = CalendarManager(self.window)

        setup_chart_ui(self.window)

        setup_backtest_tab(self.window)

        self._setup_executions_table()

        if hasattr(self.window, "btnEmergencyKill"):

            self.window.btnEmergencyKill.clicked.connect(self._handle_kill_switch)

        self.window.tabWidget.currentChanged.connect(self._on_tab_changed)

        self.bot_thread = None

        self.bot_worker = None

        self._tick_timer = QTimer()

        self._tick_timer.timeout.connect(self._on_tick)

        self._tick_timer.start(1000)

        telegram_notifier.start_listening(event_bus)

        event_bus.remote_command.connect(self._handle_remote_command)

        self.window.show()

    def _setup_executions_table(self):

        if not hasattr(self.window, "tableExecutions"):

            return

        tbl = self.window.tableExecutions

        from datetime import datetime, timedelta

        now = datetime.now()

        sample_trades = [
            (
                now.strftime("%H:%M:%S"),
                "33273901",
                "XAUUSD",
                "ICT FVG",
                "0.50",
                "10009",
            ),
            (
                (now - timedelta(minutes=14)).strftime("%H:%M:%S"),
                "32973706",
                "XAUUSD",
                "ICT FVG",
                "1.00",
                "10009",
            ),
            (
                (now - timedelta(minutes=28)).strftime("%H:%M:%S"),
                "32873893",
                "XAUUSD",
                "ICT FVG",
                "0.50",
                "10009",
            ),
            (
                (now - timedelta(minutes=45)).strftime("%H:%M:%S"),
                "32873835",
                "XAUUSD",
                "ICT FVG",
                "1.00",
                "10009",
            ),
            (
                (now - timedelta(minutes=62)).strftime("%H:%M:%S"),
                "32761290",
                "XAUUSD",
                "ICT FVG",
                "0.50",
                "10009",
            ),
        ]

        tbl.setRowCount(len(sample_trades))

        for row, data in enumerate(sample_trades):

            for col, text in enumerate(data):

                item = QTableWidgetItem(text)

                item.setTextAlignment(Qt.AlignCenter)

                if col == 5:

                    item.setForeground(QColor("#22c55e"))

                tbl.setItem(row, col, item)

        tbl.resizeColumnsToContents()

    def _handle_kill_switch(self):

        if self.bot_worker:

            self.bot_worker.stop()

        if self.bot_thread and self.bot_thread.isRunning():

            self.bot_thread.quit()

            self.bot_thread.wait(500)

        self.btnStart.setText(_TXT_START)

        self.btnStart.setProperty("running", "false")

        self.btnStart.style().unpolish(self.btnStart)

        self.btnStart.style().polish(self.btnStart)

        event_bus.log_event.emit(
            "",
            "ERROR",
            "EMERGENCY KILL-SWITCH K\u00cdCH HO\u1ea0T! T\u1ea4T C\u1ea2 GIAO D\u1ecaCH \u0110\u00c3 D\u1eeaNG.",
            "#ef4444",
        )

        telegram_notifier.send_message(
            "<b>[C\u1ea2NH B\u00c1O KH\u1ea8N C\u1ea4P]</b>\nEmergency Kill-Switch \u0111\u00e3 \u0111\u01b0\u1ee3c k\u00edch ho\u1ea1t tr\u00ean Tr\u1ea1m \u0111i\u1ec1u khi\u1ec3n!"
        )

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

    def _setup_navigation_rail(self):

        self.nav_rail = QFrame()

        self.nav_rail.setObjectName("leftSidebar")

        self.nav_rail.setFixedWidth(64)

        layout = QVBoxLayout(self.nav_rail)

        layout.setContentsMargins(6, 12, 6, 12)

        layout.setSpacing(10)

        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        assets_dir = os.path.join(os.path.dirname(__file__), "ui", "assets")

        logo_btn = QPushButton()

        logo_btn.setIcon(QIcon(os.path.join(assets_dir, "nav_logo.svg")))

        logo_btn.setIconSize(QSize(28, 28))

        logo_btn.setProperty("class", "nav_button")

        logo_btn.setEnabled(False)

        layout.addWidget(logo_btn)

        self.nav_buttons = []

        def _make_nav_btn(icon_file, tooltip, target_tab, tab_name):

            btn = QPushButton()

            btn.setIcon(QIcon(os.path.join(assets_dir, icon_file)))

            btn.setIconSize(QSize(20, 20))

            btn.setToolTip(tooltip)

            btn.setCheckable(True)

            btn.setProperty("class", "nav_button")

            btn.clicked.connect(lambda: self._switch_nav_tab(target_tab, btn, tab_name))

            layout.addWidget(btn)

            self.nav_buttons.append((btn, target_tab, tab_name))

            return btn

        self.btnNavTerminal = _make_nav_btn(
            "nav_terminal.svg",
            "Trạm Điều Khiển Live",
            self.window.tab2,
            "TRẠM ĐIỀU KHIỂN ĐỊNH LƯỢNG (LIVE)",
        )

        self.btnNavStats = _make_nav_btn(
            "nav_analytics.svg",
            "Thống Kê & Hiệu Năng",
            self.window.tab3,
            "THỐNG KÊ & PHÂN TÍCH HIỆU NĂNG",
        )

        self.btnNavBacktest = _make_nav_btn(
            "nav_backtest.svg",
            "Backtest & Kịch Bản",
            self.window.tab_5,
            "BACKTEST & THỬ NGHIỆM KỊCH BẢN",
        )

        self.btnNavSettings = _make_nav_btn(
            "nav_settings.svg",
            "Cài Đặt & Rủi Ro",
            self.window.tab1,
            "CÀI ĐẶT THUẬT TOÁN & QUẢN TRỊ RỦI RO",
        )

        self.btnNavLogs = _make_nav_btn(
            "nav_logs.svg",
            "Nhật Ký Hệ Thống",
            self.window.tab4,
            "NHẬT KÝ VẬN HÀNH THỜI GIAN THỰC",
        )

        layout.addStretch()

        self.window.horizontalLayout.insertWidget(0, self.nav_rail)

        self.window.tabWidget.tabBar().setVisible(False)

        self._switch_nav_tab(
            self.window.tab2, self.btnNavTerminal, "TRẠM ĐIỀU KHIỂN ĐỊNH LƯỢNG (LIVE)"
        )

    def _switch_nav_tab(self, target_tab, active_btn, tab_name=""):

        self.window.tabWidget.setCurrentWidget(target_tab)

        for btn, tab, _ in self.nav_buttons:

            btn.setChecked(btn == active_btn)

        if hasattr(self, "lbl_tab_title") and tab_name:

            self.lbl_tab_title.setText(tab_name)

        if target_tab == self.window.tab3:

            self.stats.refresh()

    def _setup_corner_widget(self):

        top_header = QFrame()

        top_header.setObjectName("topHeader")

        top_header.setFixedHeight(46)

        top_header.setStyleSheet(
            "background-color: #080b11; border-bottom: 1px solid rgba(255,255,255,0.06); padding: 0px 10px;"
        )

        layout = QHBoxLayout(top_header)

        layout.setContentsMargins(12, 4, 12, 4)

        self.lbl_tab_title = QLabel("TRẠM ĐIỀU KHIỂN ĐỊNH LƯỢNG (LIVE)")

        self.lbl_tab_title.setStyleSheet(
            "color: #f8fafc; font-weight: 700; font-size: 11px; letter-spacing: 0.5px;"
        )

        layout.addWidget(self.lbl_tab_title)

        layout.addStretch()

        self.lbl_status = QLabel(_TXT_DISCONNECTED)

        self.lbl_status.setStyleSheet(
            "color: #ef4444; font-weight: 600; font-size: 11px; margin-right: 15px;"
        )

        layout.addWidget(self.lbl_status)

        self.btnStart = QPushButton(_TXT_START)

        self.btnStart.setProperty("class", "btn_primary")

        self.btnStart.setCursor(Qt.PointingHandCursor)

        self.btnStart.setFixedHeight(30)

        layout.addWidget(self.btnStart)

        self.window.mainContentWidget.layout().insertWidget(0, top_header)

        self.btnStart.clicked.connect(self._toggle_bot)

    def _on_tick(self):

        if mt5.terminal_info() is None:

            self.lbl_status.setText(_TXT_DISCONNECTED)

            self.lbl_status.setStyleSheet(
                "color: #ef4444; font-weight: 600; font-size: 11px; margin-right: 15px;"
            )

            if hasattr(self.window, "labelStatus"):

                self.window.labelStatus.setText("CHƯA KẾT NỐI")

                self.window.labelStatus.setStyleSheet(
                    "color: #ef4444; font-weight: 600; font-size: 11px;"
                )

            return

        acc = mt5.account_info()

        if acc:

            self.lbl_status.setText(_TXT_CONNECTED.format(acc.login))

            self.lbl_status.setStyleSheet(
                "color: #22c55e; font-weight: 600; font-size: 11px; margin-right: 15px;"
            )

            if hasattr(self.window, "labelStatus"):

                self.window.labelStatus.setText(f"ĐÃ KẾT NỐI: {acc.login}")

                self.window.labelStatus.setStyleSheet(
                    "color: #22c55e; font-weight: 600; font-size: 11px;"
                )

            if hasattr(self.window, "valBalance"):

                self.window.valBalance.setText(f"${acc.balance:,.2f}")

                self.window.valEquity.setText(f"${acc.equity:,.2f}")

            if hasattr(self.window, "valMargin"):

                margin_pct = (acc.margin / acc.equity * 100) if acc.equity > 0 else 0

                self.window.valMargin.setText(f"{margin_pct:.2f}%")

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

            self.btnStart.setProperty("running", "true")

            self.btnStart.style().unpolish(self.btnStart)

            self.btnStart.style().polish(self.btnStart)

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
                f"<b>[HỆ THỐNG KHỞI ĐỘNG]</b>\n"
                f"Bot giao dịch đã được bật thành công!\n\n"
                f"<b>Cấu hình hiện tại:</b>\n"
                f"- Cặp giao dịch: XAUUSD\n"
                f"- Khung thời gian: {tf_name}\n"
                f"- Chiến lược: {strat_name}\n"
                f"- Chế độ Bộ lọc: {gate_mode_display}\n"
                f"- Mô hình AI: {ai_name}\n"
                f"- Quản lý rủi ro: 1.0% / Lệnh\n\n"
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
                "<b>[HỆ THỐNG TẠM DỪNG]</b>\nBot đã được tắt an toàn."
            )

            self.btnStart.setText(_TXT_START)

            self.btnStart.setProperty("running", "false")

            self.btnStart.style().unpolish(self.btnStart)

            self.btnStart.style().polish(self.btnStart)

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
