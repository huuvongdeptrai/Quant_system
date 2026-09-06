import pyqtgraph as pg
import csv
import math
import calendar
from datetime import datetime
from PySide6.QtWidgets import (QTableWidgetItem, QVBoxLayout, QHBoxLayout,
                                QWidget, QLabel, QFileDialog, QMessageBox,
                                QAbstractItemView, QHeaderView)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from core.stats_engine import StatsEngine


class StatsManager:
    """Quản lý toàn bộ Tab Thống Ke: KPI, Lich su lenh, Lich PnL, Bieu do."""

    def __init__(self, window):
        self.window = window
        self.engine = StatsEngine()
        self.current_cal_date = datetime.now()

        self._setup_history_table()
        self._setup_calendar_table()
        self._setup_charts()
        self._bind_events()

    # ------------------------------------------------------------------
    # SETUP
    # ------------------------------------------------------------------
    def _bind_events(self):
        if hasattr(self.window, 'btnCalPrev'):
            self.window.btnCalPrev.clicked.connect(self._prev_month)
        if hasattr(self.window, 'btnCalNext'):
            self.window.btnCalNext.clicked.connect(self._next_month)
        if hasattr(self.window, 'btnCalToday'):
            self.window.btnCalToday.clicked.connect(self._go_today)
        if hasattr(self.window, 'btnExportTrades'):
            self.window.btnExportTrades.clicked.connect(self.export_csv)
        if hasattr(self.window, 'searchStats'):
            self.window.searchStats.textChanged.connect(self.filter_history)

    def filter_history(self):
        if not hasattr(self.window, 'tableHistory') or not hasattr(self.window, 'searchStats'):
            return
        ht = self.window.tableHistory
        query = self.window.searchStats.text().lower()
        for i in range(ht.rowCount()):
            match = False
            if not query:
                match = True
            else:
                for j in range(ht.columnCount()):
                    widget = ht.cellWidget(i, j)
                    if widget:
                        for lbl in widget.findChildren(QLabel):
                            if query in lbl.text().lower():
                                match = True
                                break
                    if match: break
            ht.setRowHidden(i, not match)

    def _setup_history_table(self):
        if not hasattr(self.window, 'tableHistory'):
            return
        ht = self.window.tableHistory
        ht.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        ht.verticalHeader().setVisible(False)
        ht.setEditTriggers(QAbstractItemView.NoEditTriggers)
        ht.setSelectionMode(QAbstractItemView.NoSelection)

    def _setup_calendar_table(self):
        if not hasattr(self.window, 'tableCalendar'):
            return
        tb = self.window.tableCalendar
        tb.setRowCount(6)
        tb.setColumnCount(7)
        tb.verticalHeader().setVisible(False)
        tb.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tb.setSelectionMode(QAbstractItemView.NoSelection)
        tb.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tb.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tb.setStyleSheet("""
            QTableWidget {
                background-color: #0D1117;
                gridline-color: #30363D;
                border: 1px solid #30363D;
            }
            QHeaderView::section {
                background-color: #161B22;
                color: #8B949E;
                border: 1px solid #30363D;
                padding: 6px;
                font-weight: bold;
            }
        """)

    def _setup_charts(self):
        def add_plot(groupbox):
            if not groupbox.layout():
                layout = QVBoxLayout(groupbox)
                layout.setContentsMargins(10, 30, 10, 10)
            else:
                layout = groupbox.layout()
            pw = pg.PlotWidget(background='#0D1117')
            pw.showGrid(x=False, y=True, alpha=0.08)
            pw.getPlotItem().hideButtons()
            pw.setMenuEnabled(False)
            pw.setMouseEnabled(x=False, y=False)
            pw.getPlotItem().setMouseEnabled(x=False, y=False)
            for axis_name in ('left', 'bottom'):
                ax = pw.getAxis(axis_name)
                ax.setPen(pg.mkPen(color='#30363D'))
                ax.setTextPen(pg.mkPen(color='#8B949E'))
                ax.setStyle(tickLength=-5)
            layout.addWidget(pw)
            return pw

        if hasattr(self.window, 'chartEquity'):
            self.pw_hourly_pnl = add_plot(self.window.chartEquity)
        if hasattr(self.window, 'chartLongShort'):
            self.pw_buy_sell = add_plot(self.window.chartLongShort)
        if hasattr(self.window, 'chartProfitBySymbol'):
            self.pw_volume = add_plot(self.window.chartProfitBySymbol)
        if hasattr(self.window, 'chartHourly'):
            self.pw_symbol = add_plot(self.window.chartHourly)

    # ------------------------------------------------------------------
    # PUBLIC: Update All
    # ------------------------------------------------------------------
    def refresh(self):
        """Load lai toan bo du lieu KPI, Bang lich su, Lich PnL, Bieu do."""
        stats = self.engine.get_account_statistics()
        trades = self.engine.get_full_history()

        self._update_kpi(stats)
        self._update_history_table(trades)
        self._update_calendar(trades)
        self._update_charts(trades)

    # ------------------------------------------------------------------
    # PRIVATE: KPI Cards
    # ------------------------------------------------------------------
    def _update_kpi(self, stats):
        if not stats:
            return
        if hasattr(self.window, 'valTotalTrades'):
            self.window.valTotalTrades.setText(str(stats['total_trades']))
        if hasattr(self.window, 'valWinRate'):
            self.window.valWinRate.setText(f"{stats['win_rate']:.2f}%")
        if hasattr(self.window, 'valNetProfit'):
            prefix = '+' if stats['net_profit'] >= 0 else ''
            self.window.valNetProfit.setText(f"{prefix}${stats['net_profit']:.2f}")
            color = '#3FB950' if stats['net_profit'] >= 0 else '#F23645'
            self.window.valNetProfit.setStyleSheet(
                f'color: {color}; font-size: 24px; font-weight: bold;')
        if hasattr(self.window, 'valRR'):
            self.window.valRR.setText(f"{stats['rr_ratio']:.2f}")

    # ------------------------------------------------------------------
    # PRIVATE: History Table
    # ------------------------------------------------------------------
    def _make_badge(self, text, bg, fg):
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f'background-color: {bg}; color: {fg}; padding: 4px 10px; '
            f'border-radius: 6px; font-weight: bold; font-size: 13px;')
        lbl.setAlignment(Qt.AlignCenter)
        l.addWidget(lbl, alignment=Qt.AlignCenter)
        return w

    def _update_history_table(self, trades):
        if not hasattr(self.window, 'tableHistory'):
            return
        ht = self.window.tableHistory
        ht.setRowCount(0)
        for t in trades:
            self._add_history_row(
                str(t['ticket']), t['type'] == 'Buy', t['close_time'],
                f"{t['volume']:.2f}", t['symbol'],
                f"{t['pnl']:.2f} $", f"{t['pips']:.1f}", t['duration']
            )

    def _add_history_row(self, ticket, is_buy, time_str, vol, sym, pnl, pips, duration):
        ht = self.window.tableHistory
        row = ht.rowCount()
        ht.insertRow(row)
        ht.setRowHeight(row, 50)

        color_dir = '#3FB950' if is_buy else '#F23645'
        txt_dir = 'Mua' if is_buy else 'Bán'
        lbl_lenh = QLabel(
            f'<span style="font-weight:bold;color:#E5E7EB;font-size:14px;">{ticket}</span>'
            f'<br><span style="color:{color_dir};font-size:12px;">{txt_dir}</span>')
        lbl_lenh.setAlignment(Qt.AlignCenter)
        ht.setCellWidget(row, 0, lbl_lenh)

        parts = time_str.split('\n') if '\n' in time_str else [time_str, '']
        date_part, time_part = parts[0], parts[1] if len(parts) > 1 else ''
        lbl_time = QLabel(
            f'<span style="font-weight:bold;color:#E5E7EB;font-size:13px;">{date_part}</span>'
            f'<br><span style="color:#8B949E;font-size:12px;">{time_part}</span>')
        lbl_time.setAlignment(Qt.AlignCenter)
        ht.setCellWidget(row, 1, lbl_time)

        for col, text in [(2, vol), (3, sym)]:
            lbl = QLabel(text)
            lbl.setStyleSheet('color: #E5E7EB; font-size: 14px; font-weight: bold;')
            lbl.setAlignment(Qt.AlignCenter)
            ht.setCellWidget(row, col, lbl)

        is_profit = float(pnl.replace(',', '.').replace('$', '').replace(' ', '').strip()) >= 0
        pnl_color = '#3FB950' if is_profit else '#F23645'
        pnl_bg = '#172C22' if is_profit else '#3C1618'
        ht.setCellWidget(row, 4, self._make_badge(pnl, pnl_bg, pnl_color))

        try:
            is_pip_pos = float(pips.replace(',', '.').strip()) >= 0
        except ValueError:
            is_pip_pos = True
        pip_color = '#3FB950' if is_pip_pos else '#F23645'
        pip_bg = '#172C22' if is_pip_pos else '#3C1618'
        ht.setCellWidget(row, 5, self._make_badge(pips, pip_bg, pip_color))
        ht.setCellWidget(row, 6, self._make_badge(duration, '#161B22', '#8B949E'))

    # ------------------------------------------------------------------
    # PRIVATE: PnL Calendar
    # ------------------------------------------------------------------
    def _prev_month(self):
        m = self.current_cal_date.month - 1
        y = self.current_cal_date.year
        if m == 0:
            m = 12
            y -= 1
        self.current_cal_date = self.current_cal_date.replace(year=y, month=m, day=1)
        self._update_calendar(self.engine.get_full_history())

    def _next_month(self):
        m = self.current_cal_date.month + 1
        y = self.current_cal_date.year
        if m == 13:
            m = 1
            y += 1
        self.current_cal_date = self.current_cal_date.replace(year=y, month=m, day=1)
        self._update_calendar(self.engine.get_full_history())

    def _go_today(self):
        self.current_cal_date = datetime.now()
        self._update_calendar(self.engine.get_full_history())

    def _update_calendar(self, trades):
        if not hasattr(self.window, 'tableCalendar'):
            return
        y = self.current_cal_date.year
        m = self.current_cal_date.month

        months_vi = ['', 'Mot', 'Hai', 'Ba', 'Tu', 'Nam', 'Sau',
                     'Bay', 'Tam', 'Chin', 'Muoi', 'Muoi Mot', 'Muoi Hai']
        if hasattr(self.window, 'lblCalMonth'):
            self.window.lblCalMonth.setText(f'Thang {months_vi[m]} {y}')

        tb = self.window.tableCalendar
        tb.clearContents()
        cal = calendar.monthcalendar(y, m)

        daily_pnl = {}
        daily_count = {}
        for t in trades:
            dt = datetime.fromtimestamp(t['timestamp'])
            if dt.year == y and dt.month == m:
                daily_pnl[dt.day] = daily_pnl.get(dt.day, 0) + t['pnl']
                daily_count[dt.day] = daily_count.get(dt.day, 0) + 1

        monthly_total = sum(daily_pnl.values())
        if hasattr(self.window, 'lblCalMonthlyStats'):
            prefix = '+' if monthly_total >= 0 else ''
            self.window.lblCalMonthlyStats.setText(f'{prefix}{monthly_total:.2f} $')
            color = '#3FB950' if monthly_total >= 0 else '#F23645'
            bg = '#1B2E24' if monthly_total >= 0 else '#3C1618'
            self.window.lblCalMonthlyStats.setStyleSheet(
                f'background: {bg}; color: {color}; padding: 4px 10px; '
                f'border-radius: 10px; font-weight: bold;')

        today = datetime.now()
        is_current_month = (y == today.year and m == today.month)
        for row in range(len(cal)):
            for col in range(7):
                day = cal[row][col]
                if day == 0:
                    item = QTableWidgetItem('')
                    item.setBackground(QColor('#0D1117'))
                    tb.setItem(row, col, item)
                else:
                    pnl = daily_pnl.get(day, 0)
                    count = daily_count.get(day, 0)
                    text = f'{day}\n'
                    if count > 0:
                        prefix = '+' if pnl > 0 else ''
                        text += f'\n{prefix}{pnl:.2f} $\nCac giao dich: {count}'
                    item = QTableWidgetItem(text)
                    item.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)
                    if is_current_month and day == today.day:
                        item.setBackground(QColor('#1F6FEB'))
                        item.setForeground(QColor('white'))
                    elif pnl > 0:
                        item.setBackground(QColor(35, 134, 54, 80))
                        item.setForeground(QColor('#3FB950'))
                    elif pnl < 0:
                        item.setBackground(QColor(218, 54, 51, 60))
                        item.setForeground(QColor('#F23645'))
                    else:
                        item.setBackground(QColor('#1A1E24'))
                        item.setForeground(QColor('#8B949E'))
                    tb.setItem(row, col, item)

    # ------------------------------------------------------------------
    # PRIVATE: Charts
    # ------------------------------------------------------------------
    def _format_dollar_ticks(self, pw):
        ax = pw.getAxis('left')
        ax.setLabel(units=None)
        ax.enableAutoSIPrefix(False)

    def _make_dollar_yticks(self, max_val):
        if max_val == 0:
            max_val = 1
        raw_step = max_val / 3
        magnitude = 10 ** math.floor(math.log10(raw_step)) if raw_step > 0 else 1
        nice_steps = [1, 2, 5, 10, 20, 50, 100, 250, 500, 1000]
        step = magnitude
        for s in nice_steps:
            if s * magnitude >= raw_step:
                step = s * magnitude
                break
        ticks = []
        val = 0
        while val <= max_val * 1.2:
            ticks.append((val, f'${val:,.2f}'))
            if val != 0:
                ticks.append((-val, f'-${val:,.2f}'))
            val += step
        return ticks

    def _update_charts(self, trades):
        if not trades:
            return

        if hasattr(self, 'pw_hourly_pnl'):
            pw = self.pw_hourly_pnl
            pw.clear()
            hourly_pnl = {}
            for t in trades:
                h = datetime.fromtimestamp(t['timestamp']).hour
                hourly_pnl[h] = hourly_pnl.get(h, 0) + t['pnl']
            if hourly_pnl:
                hours = sorted(hourly_pnl.keys())
                pnls = [hourly_pnl[h] for h in hours]
                brushes = ['#3FB950' if v >= 0 else '#F23645' for v in pnls]
                pw.addItem(pg.BarGraphItem(x=hours, height=pnls, width=0.4, brushes=brushes))
                pw.addLine(y=0, pen=pg.mkPen('#8B949E', width=1, style=Qt.DashLine))
                # Rut gon 15h thay vi 15:00 de tranh de chu
                pw.getAxis('bottom').setTicks([[(h, f'{h}h') for h in hours]])
                self._format_dollar_ticks(pw)
                pw.getAxis('left').setTicks([self._make_dollar_yticks(max(abs(v) for v in pnls))])

        if hasattr(self, 'pw_buy_sell'):
            pw = self.pw_buy_sell
            pw.clear()
            sell_pnl = sum(t['pnl'] for t in trades if t['type'] == 'Sell')
            buy_pnl = sum(t['pnl'] for t in trades if t['type'] == 'Buy')
            brushes = ['#F23645' if sell_pnl < 0 else '#3FB950',
                       '#3FB950' if buy_pnl >= 0 else '#F23645']
            pw.addItem(pg.BarGraphItem(x=[1, 2], height=[sell_pnl, buy_pnl], width=0.4, brushes=brushes))
            pw.addLine(y=0, pen=pg.mkPen('#8B949E', width=1, style=Qt.DashLine))
            pw.getAxis('bottom').setTicks([[(1, 'Bán'), (2, 'Mua')]])
            self._format_dollar_ticks(pw)
            max_v = max(abs(sell_pnl), abs(buy_pnl)) if (sell_pnl or buy_pnl) else 1
            pw.getAxis('left').setTicks([self._make_dollar_yticks(max_v)])

        if hasattr(self, 'pw_volume'):
            pw = self.pw_volume
            pw.clear()
            vol_pnl = {}
            for t in trades:
                vol_key = round(t['volume'], 2)
                vol_pnl[vol_key] = vol_pnl.get(vol_key, 0) + t['pnl']
            if vol_pnl:
                vols = sorted(vol_pnl.keys())
                pnls = [vol_pnl[v] for v in vols]
                x = list(range(len(vols)))
                brushes = ['#3FB950' if v >= 0 else '#F23645' for v in pnls]
                pw.addItem(pg.BarGraphItem(x=x, height=pnls, width=0.4, brushes=brushes))
                pw.addLine(y=0, pen=pg.mkPen('#8B949E', width=1, style=Qt.DashLine))
                pw.getAxis('bottom').setTicks([[(i, f'{v:.2f}') for i, v in enumerate(vols)]])
                self._format_dollar_ticks(pw)
                pw.getAxis('left').setTicks([self._make_dollar_yticks(max(abs(v) for v in pnls))])

        if hasattr(self, 'pw_symbol'):
            pw = self.pw_symbol
            pw.clear()
            sym_pnl = {}
            for t in trades:
                sym_pnl[t['symbol']] = sym_pnl.get(t['symbol'], 0) + t['pnl']
            if sym_pnl:
                syms = list(sym_pnl.keys())
                pnls = list(sym_pnl.values())
                x = list(range(len(syms)))
                brushes = ['#3FB950' if v >= 0 else '#F23645' for v in pnls]
                pw.addItem(pg.BarGraphItem(x=x, height=pnls, width=0.4, brushes=brushes))
                pw.addLine(y=0, pen=pg.mkPen('#8B949E', width=1, style=Qt.DashLine))
                pw.getAxis('bottom').setTicks([[(i, sym) for i, sym in enumerate(syms)]])
                self._format_dollar_ticks(pw)
                pw.getAxis('left').setTicks([self._make_dollar_yticks(max(abs(v) for v in pnls))])

    # ------------------------------------------------------------------
    # PUBLIC: Export CSV
    # ------------------------------------------------------------------
    def export_csv(self):
        trades = self.engine.get_full_history()
        if not trades:
            QMessageBox.warning(self.window, 'Xuất dữ liệu', 'Không có dữ liệu giao dịch để xuất.')
            return
        path, _ = QFileDialog.getSaveFileName(
            self.window, 'Lưu Lịch sử Giao dịch', 'Trade_History.csv', 'CSV Files (*.csv)')
        if not path:
            return
        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Mã Lệnh', 'Loại', 'Mã GD', 'Khối lượng',
                                 'PnL ($)', 'Pips', 'Thời lượng', 'Giờ đóng lệnh'])
                for t in trades:
                    writer.writerow([
                        t['ticket'], t['type'], t['symbol'], t['volume'],
                        t['pnl'], t['pips'], t['duration'],
                        t['close_time'].replace('\n', ' ')
                    ])
            QMessageBox.information(self.window, 'Thành công', f'Đã xuất dữ liệu ra file:\n{path}')
        except Exception as e:
            QMessageBox.critical(self.window, 'Lỗi', f'Không thể lưu file:\n{e}')
