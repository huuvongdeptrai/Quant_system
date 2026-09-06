import os
import datetime
from PySide6.QtWidgets import (QHeaderView, QWidget, QHBoxLayout,
                                QLabel, QAbstractItemView, QTableWidgetItem)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from core.macro.calendar_engine import CalendarEngine

# Windows Qt khong render Unicode flag emoji -> dung badge text mau
COUNTRY_COLORS = {
    'US': '#3C4FBF', 'EU': '#1A6B3C', 'GB': '#8B0000',
    'JP': '#CC0000', 'AU': '#004B87', 'CA': '#CC0000',
    'CH': '#CC0000', 'NZ': '#00247D', 'CN': '#DE2910', 'DE': '#1A1A1A',
}

IMPACT_CONFIG = {
    2: ('\u25cf Cao',  '#F23645'),
    1: ('\u25cf V\u1eeba',  '#FF9800'),
    0: ('\u25cf Th\u1ea5p', '#CCAA00'),
}

WEEKDAYS_VI = [
    'Th\u1ee9 Hai', 'Th\u1ee9 Ba', 'Th\u1ee9 T\u01b0',
    'Th\u1ee9 N\u0103m', 'Th\u1ee9 S\u00e1u',
    'Th\u1ee9 B\u1ea3y', 'Ch\u1ee7 Nh\u1eadt'
]


class CalendarManager:
    def __init__(self, window):
        self.window = window
        self.engine = CalendarEngine()
        self.table = getattr(self.window, 'tableEconomicCalendar', None)
        if self.table:
            self._setup_table()
            self.load_calendar()

    def _setup_table(self):
        t = self.table
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.setSelectionMode(QAbstractItemView.NoSelection)
        t.setShowGrid(False)
        t.setAlternatingRowColors(False)

        hdr = t.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.Fixed)
        hdr.setSectionResizeMode(4, QHeaderView.Fixed)
        hdr.setSectionResizeMode(5, QHeaderView.Fixed)
        hdr.setSectionResizeMode(6, QHeaderView.Fixed)

        t.setColumnWidth(0, 75)
        t.setColumnWidth(1, 80)
        t.setColumnWidth(3, 90)
        t.setColumnWidth(4, 80)
        t.setColumnWidth(5, 80)
        t.setColumnWidth(6, 80)

    def _insert_date_separator(self, row, date_obj):
        t = self.table
        t.insertRow(row)

        # QUAN TRONG: setSpan truoc, roi moi setCellWidget
        t.setSpan(row, 0, 1, t.columnCount())

        today = datetime.date.today()
        is_today = (date_obj == today)
        bg_color = '#1A2744' if is_today else '#21262D' # Đổi màu nền ngày thường cho nổi bật hơn
        fg_color = '#58A6FF' if is_today else '#C9D1D9' # Chữ trắng xám thay vì xám chìm

        thu = WEEKDAYS_VI[date_obj.weekday()]
        label_text = f"   {thu}   |   {date_obj.strftime('%d/%m/%Y')}"

        # Background cho tat ca o (span chi gop hien thi, item van can set)
        for col in range(t.columnCount()):
            item = QTableWidgetItem()
            item.setBackground(QColor(bg_color))
            item.setFlags(Qt.ItemIsEnabled)
            if col == 0:
                item.setText(label_text)
                item.setForeground(QColor(fg_color))
                # Set font
                font = item.font()
                font.setBold(True)
                font.setPointSize(10)
                item.setFont(font)
                
            t.setItem(row, col, item)

        # Set chieu cao cuoi cung
        t.setRowHeight(row, 35)

    def _country_badge(self, country):
        color = COUNTRY_COLORS.get(country, '#444')
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(4, 0, 4, 0)
        badge = QLabel(country)
        badge.setStyleSheet(
            'background:' + color + '; color:white; font-size:11px;'
            ' font-weight:bold; padding:2px 6px; border-radius:3px;'
        )
        badge.setAlignment(Qt.AlignCenter)
        l.addWidget(badge, alignment=Qt.AlignCenter)
        return w

    def _impact_cell(self, impact):
        txt, color = IMPACT_CONFIG.get(impact, IMPACT_CONFIG[0])
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(4, 0, 4, 0)
        lbl = QLabel(txt)
        lbl.setStyleSheet('color:' + color + '; font-size:13px; font-weight:bold;')
        lbl.setAlignment(Qt.AlignCenter)
        l.addWidget(lbl, alignment=Qt.AlignCenter)
        return w

    def _cell(self, text, color='#C9D1D9', bold=False, align=Qt.AlignCenter):
        val = str(text) if text not in ('None', 'none', '', None) else '-'
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(6, 0, 6, 0)
        lbl = QLabel(val)
        weight = 'bold' if bold else 'normal'
        lbl.setStyleSheet('color:' + color + '; font-size:13px; font-weight:' + weight + ';')
        lbl.setAlignment(align)
        l.addWidget(lbl)
        return w

    def load_calendar(self):
        t = self.table
        t.setRowCount(0)
        events = self.engine.fetch_events()

        current_date = None
        for e in events:
            # sort_key la VN timestamp (da cong +7h trong engine)
            event_date = datetime.date.fromtimestamp(e['sort_key'])

            if event_date != current_date:
                current_date = event_date
                self._insert_date_separator(t.rowCount(), event_date)

            row = t.rowCount()
            t.insertRow(row)
            t.setRowHeight(row, 42)

            time_only = e['time'].split(' ')[-1]
            t.setCellWidget(row, 0, self._cell(time_only, bold=True))
            t.setCellWidget(row, 1, self._country_badge(e['country']))

            lbl_event = QLabel(e['title'])
            lbl_event.setStyleSheet('color:#C9D1D9; font-size:13px; padding-left:8px;')
            lbl_event.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            t.setCellWidget(row, 2, lbl_event)

            t.setCellWidget(row, 3, self._impact_cell(e['impact']))

            actual   = str(e['actual'])   if e['actual']   not in ('None', '', None) else '-'
            forecast = str(e['forecast']) if e['forecast'] not in ('None', '', None) else '-'
            previous = str(e['previous']) if e['previous'] not in ('None', '', None) else '-'

            actual_color = '#C9D1D9'
            if actual != '-' and forecast != '-':
                try:
                    actual_color = '#3FB950' if float(actual) > float(forecast) else '#F23645'
                except ValueError:
                    pass

            t.setCellWidget(row, 4, self._cell(actual, color=actual_color, bold=True))
            t.setCellWidget(row, 5, self._cell(forecast))
            t.setCellWidget(row, 6, self._cell(previous))
