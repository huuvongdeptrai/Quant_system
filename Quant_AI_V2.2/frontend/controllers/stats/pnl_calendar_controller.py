"""
PnL Calendar Heatmap Controller for Tab 2 (Performance)
Manages 42-cell monthly calendar matrix, month switching, and daily realized PnL coloring.
"""

from datetime import datetime
import calendar
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidgetItem
from frontend.widgets.delegates import TradeZellaCalendarDelegate


class PnlCalendarController:
    """Manages the 42-cell TradeZella-style PnL calendar table."""

    def __init__(self, manager):
        self.mgr = manager
        self.window = manager.window

    def setup_calendar_table(self):
        if not hasattr(self.window, "tableCalendar"):
            return
        tb = self.window.tableCalendar
        tb.setColumnCount(7)
        tb.setHorizontalHeaderLabels(["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"])
        tb.verticalHeader().setVisible(False)
        tb.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tb.setSelectionMode(QAbstractItemView.NoSelection)
        tb.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tb.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.calendar_delegate = TradeZellaCalendarDelegate(tb)
        tb.setItemDelegate(self.calendar_delegate)

    def prev_month(self):
        m = self.mgr.current_cal_date.month - 1
        y = self.mgr.current_cal_date.year
        if m == 0:
            m = 12
            y -= 1
        self.mgr.current_cal_date = self.mgr.current_cal_date.replace(year=y, month=m, day=1)
        self.update_calendar(self.mgr.cached_trades)

    def next_month(self):
        m = self.mgr.current_cal_date.month + 1
        y = self.mgr.current_cal_date.year
        if m == 13:
            m = 1
            y += 1
        self.mgr.current_cal_date = self.mgr.current_cal_date.replace(year=y, month=m, day=1)
        self.update_calendar(self.mgr.cached_trades)

    def go_today(self):
        self.mgr.current_cal_date = datetime.now()
        self.update_calendar(self.mgr.cached_trades)

    def update_calendar(self, trades):
        if not hasattr(self.window, "tableCalendar"):
            return
        y = self.mgr.current_cal_date.year
        m = self.mgr.current_cal_date.month

        if hasattr(self.window, "lblCalMonth"):
            self.window.lblCalMonth.setText(f"{calendar.month_name[m].upper()} {y}")

        tb = self.window.tableCalendar
        tb.setRowCount(6)
        tb.clearContents()

        cal = calendar.Calendar(firstweekday=0)
        month_days = list(cal.itermonthdates(y, m))

        daily_pnl = {}
        daily_trades = {}
        for t in trades or []:
            dt_raw = t.get("timestamp")
            if dt_raw:
                try:
                    dt = datetime.fromtimestamp(dt_raw) if isinstance(dt_raw, (int, float)) else datetime.fromisoformat(str(dt_raw))
                    d_key = dt.date()
                    daily_pnl[d_key] = daily_pnl.get(d_key, 0.0) + t.get("pnl", 0.0)
                    daily_trades[d_key] = daily_trades.get(d_key, 0) + 1
                except Exception:
                    pass

        cur_month_pnl = 0.0
        cur_month_trades = 0
        cur_month_win_days = 0
        cur_month_loss_days = 0

        for row in range(6):
            for col in range(7):
                idx = row * 7 + col
                if idx < len(month_days):
                    d = month_days[idx]
                    pnl = daily_pnl.get(d, None)
                    t_cnt = daily_trades.get(d, 0)
                    is_cur_month = (d.month == m)

                    is_today = (d == datetime.now().date())
                    is_dark = getattr(self.window, "is_dark_theme", False)
                    item = QTableWidgetItem()
                    item.setData(Qt.UserRole, {
                        "date": d,
                        "day": d.day,
                        "pnl": pnl,
                        "trades": t_cnt,
                        "count": t_cnt,
                        "is_current_month": is_cur_month,
                        "is_other": not is_cur_month,
                        "is_today": is_today,
                        "is_dark": is_dark,
                    })
                    tb.setItem(row, col, item)

                    if is_cur_month and pnl is not None:
                        cur_month_pnl += pnl
                        cur_month_trades += t_cnt
                        if pnl > 0:
                            cur_month_win_days += 1
                        elif pnl < 0:
                            cur_month_loss_days += 1

        if hasattr(self.window, "lblCalNetPnl"):
            color = "#15803d" if cur_month_pnl >= 0 else "#b91c1c"
            sign = "+" if cur_month_pnl > 0 else ""
            self.window.lblCalNetPnl.setText(f"{sign}${cur_month_pnl:,.2f}")
            self.window.lblCalNetPnl.setStyleSheet(f"font-weight: bold; color: {color};")

        if hasattr(self.window, "lblCalWinLoss"):
            total_active_days = cur_month_win_days + cur_month_loss_days
            rate = (cur_month_win_days / total_active_days * 100) if total_active_days > 0 else 0
            self.window.lblCalWinLoss.setText(f"{cur_month_win_days}W / {cur_month_loss_days}L ({rate:.0f}%)")

        if hasattr(self.window, "lblCalMonthlyStats"):
            sign = "+" if cur_month_pnl > 0 else ("-" if cur_month_pnl < 0 else "")
            abs_pnl = abs(cur_month_pnl)
            pnl_str = f"{sign}${abs_pnl:,.0f}" if abs_pnl >= 1 else "$0"
            self.window.lblCalMonthlyStats.setText(f"Net: {pnl_str} | W: {cur_month_win_days} | L: {cur_month_loss_days}")
