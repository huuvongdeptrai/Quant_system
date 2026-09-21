from datetime import datetime
import re
import os
import csv
from PySide6.QtWidgets import (
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QMessageBox,
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt
from core.event_bus import event_bus


class LogManager:
    def __init__(self, window):
        self.window = window
        self.tb = self.window.tableLogs if hasattr(self.window, "tableLogs") else None
        self.current_tag_filter = "ALL"
        if self.tb:
            self.tb.setProperty("class", "log_table")
            self.setup_ui()
            event_bus.log_event.connect(self.on_log_event)

            # Controls
            if hasattr(self.window, "btnClearLogs"):
                self.window.btnClearLogs.clicked.connect(self.clear_logs)
            if hasattr(self.window, "btnExportLogs"):
                self.window.btnExportLogs.clicked.connect(self.export_logs)
            if hasattr(self.window, "searchLog"):
                self.window.searchLog.textChanged.connect(self.filter_logs)

            # Pill Tag Filters
            self._setup_pill_filters()

    def _setup_pill_filters(self):
        self.filter_btns = {
            "ALL": getattr(self.window, "btnFilterAll", None),
            "INFO": getattr(self.window, "btnFilterInfo", None),
            "EXECUTION": getattr(self.window, "btnFilterExec", None),
            "RECOVERY": getattr(self.window, "btnFilterRecovery", None),
            "WARNING": getattr(self.window, "btnFilterWarn", None),
        }

        for tag, btn in self.filter_btns.items():
            if btn:
                btn.clicked.connect(
                    lambda checked=False, t=tag: self._set_tag_filter(t)
                )

    def _set_tag_filter(self, tag):
        self.current_tag_filter = tag
        for t, btn in self.filter_btns.items():
            if btn:
                cls_name = "pill_filter_active" if t == tag else "pill_filter"
                btn.setProperty("class", cls_name)
                btn.style().unpolish(btn)
                btn.style().polish(btn)
        self.filter_logs()

    def setup_ui(self):
        self.tb.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.tb.setColumnWidth(0, 110)
        self.tb.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.tb.setColumnWidth(1, 100)
        self.tb.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tb.verticalHeader().setVisible(False)
        self.tb.setSelectionMode(QAbstractItemView.NoSelection)
        self.tb.setFocusPolicy(Qt.NoFocus)
        self.tb.setShowGrid(False)

    def on_log_event(self, time_str, level, msg, color_hex):
        if not self.tb:
            return
        # Fallback: nếu time_str không phải timestamp hợp lệ, tự tạo
        if not re.match(r"\d{2}:\d{2}", time_str):
            time_str = datetime.now().strftime("%H:%M:%S")
        row = self.tb.rowCount()
        self.tb.insertRow(row)

        i_time = QTableWidgetItem(f"[{time_str}]")
        i_level = QTableWidgetItem(level.upper())
        i_msg = QTableWidgetItem(msg)

        # FinTech Muted Palette for levels
        lvl = level.upper()
        if "WARN" in lvl:
            lvl_color = "#f59e0b"
        elif "ERR" in lvl or "FAIL" in lvl:
            lvl_color = "#ef4444"
        elif "EXEC" in lvl:
            lvl_color = "#fbbf24"
        elif "RECOV" in lvl:
            lvl_color = "#a855f7"
        elif "OK" in lvl or "SUCCESS" in lvl:
            lvl_color = "#22c55e"
        else:
            lvl_color = "#38bdf8"

        i_time.setForeground(QColor("#64748b"))
        i_level.setForeground(QColor(lvl_color))
        i_msg.setForeground(QColor("#f8fafc"))

        self.tb.setItem(row, 0, i_time)
        self.tb.setItem(row, 1, i_level)
        self.tb.setItem(row, 2, i_msg)

        auto_scroll = True
        if hasattr(self.window, "checkAutoScroll"):
            auto_scroll = self.window.checkAutoScroll.isChecked()
        if auto_scroll:
            self.tb.scrollToBottom()

        self.filter_logs()

    def filter_logs(self):
        if not self.tb:
            return
        query = (
            self.window.searchLog.text().lower()
            if hasattr(self.window, "searchLog")
            else ""
        )
        tag = self.current_tag_filter

        for i in range(self.tb.rowCount()):
            # Check Tag Filter
            tag_match = True
            if tag != "ALL":
                lvl_item = self.tb.item(i, 1)
                msg_item = self.tb.item(i, 2)
                lvl_text = lvl_item.text().upper() if lvl_item else ""
                msg_text = msg_item.text().upper() if msg_item else ""

                if tag == "INFO" and "INFO" not in lvl_text:
                    tag_match = False
                elif tag == "EXECUTION" and (
                    "EXEC" not in lvl_text and "EXEC" not in msg_text
                ):
                    tag_match = False
                elif tag == "RECOVERY" and (
                    "RECOV" not in lvl_text
                    and "PHỤC HỒI" not in msg_text
                    and "STATE" not in msg_text
                ):
                    tag_match = False
                elif tag == "WARNING" and (
                    "WARN" not in lvl_text and "ERR" not in lvl_text
                ):
                    tag_match = False

            # Check Query Filter
            query_match = True
            if query:
                match_found = False
                for j in range(self.tb.columnCount()):
                    item = self.tb.item(i, j)
                    if item and query in item.text().lower():
                        match_found = True
                        break
                query_match = match_found

            self.tb.setRowHidden(i, not (tag_match and query_match))

    def clear_logs(self):
        if self.tb:
            self.tb.setRowCount(0)

    def export_logs(self):
        if not self.tb:
            return
        export_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "exported_logs.csv"
        )
        try:
            with open(export_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Time", "Level", "Message"])
                for row in range(self.tb.rowCount()):
                    t = self.tb.item(row, 0).text() if self.tb.item(row, 0) else ""
                    l = self.tb.item(row, 1).text() if self.tb.item(row, 1) else ""
                    m = self.tb.item(row, 2).text() if self.tb.item(row, 2) else ""
                    writer.writerow([t, l, m])
            QMessageBox.information(
                self.window, "Thành công", f"Đã xuất log ra:\n{export_path}"
            )
        except Exception as e:
            QMessageBox.critical(self.window, "Lỗi", f"Không thể xuất file: {e}")
