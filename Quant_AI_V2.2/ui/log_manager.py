import os
import csv
from PySide6.QtWidgets import QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt
from core.event_bus import event_bus

class LogManager:
    def __init__(self, window):
        self.window = window
        self.tb = self.window.tableLogs if hasattr(self.window, 'tableLogs') else None
        if self.tb:
            self.setup_ui()
            event_bus.log_event.connect(self.on_log_event)
            
            # Đọc tên nút từ UI (thường là btnClearLogs, btnExportLogs)
            if hasattr(self.window, 'btnClearLogs'):
                self.window.btnClearLogs.clicked.connect(self.clear_logs)
            if hasattr(self.window, 'btnExportLogs'):
                self.window.btnExportLogs.clicked.connect(self.export_logs)
            if hasattr(self.window, 'searchLog'):
                self.window.searchLog.textChanged.connect(self.filter_logs)

    def setup_ui(self):
        self.tb.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.tb.setColumnWidth(0, 120)
        self.tb.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.tb.setColumnWidth(1, 120)
        self.tb.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tb.verticalHeader().setVisible(False)
        self.tb.setSelectionMode(QAbstractItemView.NoSelection)
        self.tb.setFocusPolicy(Qt.NoFocus)
        self.tb.setShowGrid(False)

    def on_log_event(self, time_str, level, msg, color_hex):
        if not self.tb: return
        row = self.tb.rowCount()
        self.tb.insertRow(row)
        
        i_time = QTableWidgetItem(time_str)
        i_level = QTableWidgetItem(level)
        i_msg = QTableWidgetItem(msg)
        
        i_time.setForeground(QColor("#8B949E"))
        i_level.setForeground(QColor(color_hex))
        i_msg.setForeground(QColor("#E5E7EB"))
        
        self.tb.setItem(row, 0, i_time)
        self.tb.setItem(row, 1, i_level)
        self.tb.setItem(row, 2, i_msg)
        self.tb.scrollToBottom()
        self.filter_logs() # Cập nhật hiển thị ngay lập tức

    def filter_logs(self):
        if not self.tb or not hasattr(self.window, 'searchLog'): return
        query = self.window.searchLog.text().lower()
        for i in range(self.tb.rowCount()):
            match = False
            for j in range(self.tb.columnCount()):
                item = self.tb.item(i, j)
                if item and query in item.text().lower():
                    match = True
                    break
            self.tb.setRowHidden(i, not match)

    def clear_logs(self):
        if self.tb:
            self.tb.setRowCount(0)
            
    def export_logs(self):
        if not self.tb: return
        export_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "exported_logs.csv")
        try:
            with open(export_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Time", "Level", "Message"])
                for row in range(self.tb.rowCount()):
                    t = self.tb.item(row, 0).text() if self.tb.item(row, 0) else ""
                    l = self.tb.item(row, 1).text() if self.tb.item(row, 1) else ""
                    m = self.tb.item(row, 2).text() if self.tb.item(row, 2) else ""
                    writer.writerow([t, l, m])
            QMessageBox.information(self.window, "Thành công", f"Đã xuất log ra:\n{export_path}")
        except Exception as e:
            QMessageBox.critical(self.window, "Lỗi", f"Không thể xuất file: {e}")