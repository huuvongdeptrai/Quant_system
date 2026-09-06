# -*- coding: utf-8 -*-
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
                               QPushButton, QLabel, QComboBox, QDoubleSpinBox, 
                               QTextEdit, QFormLayout, QGroupBox, QTableWidget, 
                               QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox, QDateEdit)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt, QDate
from core.mt5_safe import mt5
import pandas as pd
import numpy as np
import pyqtgraph as pg
from ui.python_highlighter import CodeEditor, PythonHighlighter
from core.backtest_engine import BacktestWorker

DEFAULT_CODE = """def generate_signals(df):
    '''
    df chứa các cột: 'time', 'open', 'high', 'low', 'close', 'tick_volume'
    Bạn cần tạo ra cột 'signal': 1 (Buy), -1 (Sell), 0 (Không làm gì)
    '''
    # Chiến lược cắt chéo 2 đường EMA
    df['EMA_10'] = df['close'].ewm(span=10).mean()
    df['EMA_50'] = df['close'].ewm(span=50).mean()
    
    df['signal'] = 0
    # Cắt lên -> Mua
    df.loc[(df['EMA_10'] > df['EMA_50']) & (df['EMA_10'].shift(1) <= df['EMA_50'].shift(1)), 'signal'] = 1
    # Cắt xuống -> Bán
    df.loc[(df['EMA_10'] < df['EMA_50']) & (df['EMA_10'].shift(1) >= df['EMA_50'].shift(1)), 'signal'] = -1
    
    return df
"""

class BacktestTab(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        
        main_splitter = QSplitter(Qt.Horizontal)
        
        # --- LEFT PANEL: Code Editor ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        toolbar = QHBoxLayout()
        lbl_code = QLabel("IDE CHIẾN LƯỢC")
        lbl_code.setStyleSheet("color: #8B949E; font-weight: bold; font-size: 12px; letter-spacing: 1px;")
        
        btn_load = QPushButton("Mở File")
        btn_save = QPushButton("Lưu File")
        btn_load.clicked.connect(self._load_file)
        btn_save.clicked.connect(self._save_file)
        
        toolbar.addWidget(lbl_code)
        toolbar.addStretch()
        toolbar.addWidget(btn_load)
        toolbar.addWidget(btn_save)
        
        self.code_editor = CodeEditor()
        self.code_editor.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0D1117;
                color: #E5E7EB;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 14px;
                border: 1px solid #30363D;
                border-radius: 5px;
            }
        """)
        self.code_editor.setPlainText(DEFAULT_CODE)
        self.highlighter = PythonHighlighter(self.code_editor.document())
        
        left_layout.addLayout(toolbar)
        left_layout.addWidget(self.code_editor)
        
        # --- RIGHT PANEL: Settings & Results ---
        right_panel = QSplitter(Qt.Vertical)
        
        # 1. Settings & Run
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        
        group_settings = QGroupBox("THÔNG SỐ BACKTEST")
        group_settings.setStyleSheet("""
            QGroupBox { border: none; padding-top: 15px; margin-top: 10px; }
            QGroupBox::title { color: #8B949E; font-weight: bold; font-size: 11px; letter-spacing: 1px; }
        """)
        form = QFormLayout(group_settings)
        
        self.combo_symbol = QComboBox()
        self.combo_symbol.addItems(["XAUUSD", "EURUSD", "GBPUSD", "BTCUSD"])
        self.combo_tf = QComboBox()
        self.combo_tf.addItem("M15", mt5.TIMEFRAME_M15)
        self.combo_tf.addItem("H1", mt5.TIMEFRAME_H1)
        self.combo_tf.addItem("M5", mt5.TIMEFRAME_M5)
        
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addMonths(-3))
        
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        
        self.spin_balance = QDoubleSpinBox()
        self.spin_balance.setRange(100, 1000000)
        self.spin_balance.setValue(10000)
        self.spin_balance.setPrefix("$ ")
        
        form.addRow("Mã giao dịch:", self.combo_symbol)
        form.addRow("Khung thời gian:", self.combo_tf)
        form.addRow("Từ ngày:", self.date_from)
        form.addRow("Đến ngày:", self.date_to)
        form.addRow("Vốn khởi điểm:", self.spin_balance)
        
        self.btn_run = QPushButton("RUN BACKTEST")
        self.btn_run.setStyleSheet("""
            QPushButton {
                background-color: #1F2328;
                color: #C9D1D9;
                border: 1px solid #30363D;
                font-weight: bold;
                font-size: 12px;
                letter-spacing: 1px;
                padding: 10px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #30363D; border: 1px solid #8B949E; }
            QPushButton:pressed { background-color: #21262D; }
            QPushButton:disabled { color: #484F58; border: 1px solid #21262D; }
        """)
        self.btn_run.clicked.connect(self._run_backtest)
        
        settings_layout.addWidget(group_settings)
        settings_layout.addWidget(self.btn_run)
        
        # 2. Charts (Equity Curve)
        self.equity_plot = pg.PlotWidget(title="Đường cong vốn (Equity Curve)")
        self.equity_plot.setBackground('#010409')
        self.equity_plot.showGrid(x=True, y=True, alpha=0.1)
        self.equity_plot.getAxis('left').setPen('#30363D')
        self.equity_plot.getAxis('bottom').setPen('#30363D')
        self.equity_plot.setMouseEnabled(x=False, y=False)
        self.equity_plot.hideButtons()
        
        self.equity_curve_item = pg.PlotDataItem(pen=pg.mkPen(color='#3FB950', width=2))
        self.equity_plot.addItem(self.equity_curve_item)
        
        # 3. Metrics Table
        self.table_metrics = QTableWidget()
        self.table_metrics.setColumnCount(2)
        self.table_metrics.setRowCount(6)
        self.table_metrics.horizontalHeader().setVisible(False)
        self.table_metrics.verticalHeader().setVisible(False)
        self.table_metrics.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_metrics.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_metrics.setStyleSheet("""
            QTableWidget { background-color: #010409; color: #8B949E; border: none; font-size: 12px; }
            QTableWidget::item { padding: 4px; border-bottom: 1px solid #1F2328; }
        """)
        
        metrics_labels = ["Tổng số lệnh:", "Win Rate:", "Lợi nhuận ròng:", "Max Drawdown:", "Profit Factor:", "Vốn cuối:"]
        for i, lbl in enumerate(metrics_labels):
            self.table_metrics.setItem(i, 0, QTableWidgetItem(lbl))
            
        # 4. Console Log
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("background-color: #010409; color: #8B949E; font-family: 'Consolas';")
        self.console.setMaximumHeight(100)
        
        right_panel.addWidget(settings_widget)
        right_panel.addWidget(self.equity_plot)
        right_panel.addWidget(self.table_metrics)
        right_panel.addWidget(self.console)
        right_panel.setSizes([150, 400, 150, 100])
        
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([600, 400])
        
        layout.addWidget(main_splitter)

    def _load_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Mở file chiến lược", "", "Python Files (*.py)")
        if file_name:
            with open(file_name, 'r', encoding='utf-8') as f:
                self.code_editor.setPlainText(f.read())
            self.current_file_path = file_name
            self._log(f"Đã tải file: {file_name}")

    def _save_file(self):
        file_name, _ = QFileDialog.getSaveFileName(self, "Lưu file chiến lược", "", "Python Files (*.py)")
        if file_name:
            with open(file_name, 'w', encoding='utf-8') as f:
                f.write(self.code_editor.toPlainText())
            self._log(f"Đã lưu file: {file_name}")

    def _log(self, msg):
        self.console.append(msg)
        # Scroll to bottom
        scrollbar = self.console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _run_backtest(self):
        self.console.clear()
        self._log("Khởi động Backtest Engine...")
        self.btn_run.setEnabled(False)
        self.btn_run.setText("ĐANG CHẠY...")
        
        code = self.code_editor.toPlainText()
        sym = self.combo_symbol.currentText()
        tf = self.combo_tf.currentData()
        bal = self.spin_balance.value()
        
        d_from = self.date_from.date().toPython()
        d_to = self.date_to.date().toPython()
        
        from datetime import datetime
        import pytz
        timezone = pytz.timezone("Etc/UTC")
        dt_from = datetime.combine(d_from, datetime.min.time()).replace(tzinfo=timezone)
        dt_to = datetime.combine(d_to, datetime.max.time()).replace(tzinfo=timezone)
        
        self._log(f"Đang lấy dữ liệu {sym} từ MT5...")
        rates = mt5.copy_rates_range(sym, tf, dt_from, dt_to)
        
        if rates is None or len(rates) == 0:
            self._on_error("Không thể lấy dữ liệu từ MT5. Kiểm tra kết nối.")
            return
            
        file_path = getattr(self, 'current_file_path', None)
        self.worker = BacktestWorker(sym, tf, bal, code, rates, file_path)
        self.worker.log_signal.connect(self._log)
        self.worker.error_signal.connect(self._on_error)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.start()

    def _on_error(self, err_msg):
        self._log(f"[LỖI] {err_msg}")
        QMessageBox.critical(self, "Lỗi Backtest", err_msg)
        self._reset_btn()

    def _on_finished(self, results):
        self._log("Mô phỏng hoàn tất! Đang vẽ biểu đồ...")
        metrics = results['metrics']
        eq_curve = results['equity_curve']
        
        # Cập nhật bảng metrics
        def set_val(row, text, color="#C9D1D9"):
            item = QTableWidgetItem(text)
            item.setForeground(Qt.GlobalColor.white if color=="#C9D1D9" else QColor(color))
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table_metrics.setItem(row, 1, item)

        set_val(0, str(metrics['total_trades']))
        set_val(1, f"{metrics['win_rate']:.2f}%")
        
        net_profit = metrics['net_profit']
        np_color = "#3FB950" if net_profit > 0 else "#F23645"
        set_val(2, f"${net_profit:,.2f}", np_color)
        
        set_val(3, f"{metrics['max_drawdown']:.2f}%", "#F23645")
        set_val(4, f"{metrics['profit_factor']:.2f}")
        set_val(5, f"${metrics['final_balance']:,.2f}", "#58A6FF")
        
        # Vẽ biểu đồ Equity Curve
        if len(eq_curve) > 0:
            y_data = [item['equity'] for item in eq_curve]
            self.equity_curve_item.setData(y_data)
            
        self._log("Hoàn thành!")
        self._reset_btn()

    def _reset_btn(self):
        self.btn_run.setEnabled(True)
        self.btn_run.setText("RUN BACKTEST")

def setup_backtest_tab(window):
    tab = BacktestTab(window)
    window.tabWidget.addTab(tab, "LẬP TRÌNH CHIẾN LƯỢC")
