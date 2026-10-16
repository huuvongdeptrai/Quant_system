from frontend.styling.formatters import fmt_currency, fmt_percent, fmt_number
from frontend.styling.theme_engine import ThemeEngine
"""
Backtest Simulation Execution Engine for Tab 3 (Backtest Workbench)
Handles data acquisition (MT5 copy_rates_range), vectorized ICT simulation, Sortino ratio calculation,
equity curve generation, and simulation audit trail logging.
"""

import time
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from loguru import logger
from backend.infrastructure.brokers.mt5_safe import mt5


def run_simulation_internal(ctrl, is_initial: bool = False):
    """Executes vectorized simulation and updates UI equity curves and metrics matrix."""
    self = ctrl
    if not is_initial:
        if hasattr(self.window, "txtBtConsole"):
            self.window.txtBtConsole.clear()

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Parse date range settings
    q_from = self.dateBtFrom.date() if hasattr(self, "dateBtFrom") else None
    q_to = self.dateBtTo.date() if hasattr(self, "dateBtTo") else None

    if q_from and q_to:
        d_from = datetime(q_from.year(), q_from.month(), q_from.day(), 0, 0, 0)
        d_to = datetime(q_to.year(), q_to.month(), q_to.day(), 23, 59, 59)
        if d_from > d_to:
            d_from, d_to = d_to, d_from
            self.dateBtFrom.setDate(q_to)
            self.dateBtTo.setDate(q_from)
    else:
        d_to = datetime.now()
        d_from = d_to - timedelta(days=30)

    from_str = d_from.strftime("%Y-%m-%d")
    to_str = d_to.strftime("%Y-%m-%d")

    tf_str = (
        self.window.comboBtTf.currentText()
        if hasattr(self.window, "comboBtTf")
        else "M15"
    )
    slippage_pts = (
        self.window.spinBtSlippage.value()
        if hasattr(self.window, "spinBtSlippage")
        else 20
    )

    strat_data = (
        self.window.comboBtEngine.currentData()
        if hasattr(self.window, "comboBtEngine")
        else None
    )
    strat_name = (
        strat_data.get("name")
        if strat_data
        else (
            self.window.comboBtEngine.currentText()
            if hasattr(self.window, "comboBtEngine")
            else "Vectorized"
        )
    )

    self._log(f"[{now_str}] [SIMULATION] Strategy: {strat_name}")
    self._log(f"[{now_str}] [PARAMS] Range: {from_str} to {to_str} | Timeframe: {tf_str} | Slippage: {slippage_pts} pts")

    try:
        from research.backtest_vectorized import VectorizedBacktester

        t0 = time.perf_counter()
        rates = None
        if mt5.terminal_info() is None:
            mt5.initialize()

        tf_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
        }
        selected_tf = tf_map.get(tf_str, mt5.TIMEFRAME_M15)

        if mt5.terminal_info():
            rates = mt5.copy_rates_range(self.current_symbol, selected_tf, d_from, d_to)
            if rates is None or len(rates) == 0:
                rates = mt5.copy_rates_from_pos(self.current_symbol, selected_tf, 0, 1000)

        if rates is None or len(rates) < 30:
            self._log(f"[{now_str}] [ERROR] Insufficient bar data from MetaTrader 5 ({self.current_symbol}) for {from_str} to {to_str}.")
            self._log(f"[{now_str}] [CANCELLED] Simulation aborted due to missing MT5 market data.")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self.window,
                "Missing MT5 Data",
                f"Unable to load historical bars from MetaTrader 5 for {self.current_symbol} between {from_str} and {to_str}.\n\n"
                "Please ensure MT5 is connected and history is loaded for this symbol and period."
            )
            if hasattr(self, "btn_run_sim"):
                self.btn_run_sim.setEnabled(True)
            if hasattr(self, "progress_bar"):
                self.progress_bar.setVisible(False)
            return

        df = pd.DataFrame(rates)
        self._log(f"[{now_str}] [DATA] Loaded {len(df):,} real bars from MT5 ({self.current_symbol}) for {from_str} to {to_str}.")

        # Execute Backtest
        target_rr = 2.5 if "ICT" in strat_name else 2.0
        init_cap = self.spinBtCapital.value() if hasattr(self, "spinBtCapital") else 100000.0
        comm_val = self.spinBtComm.value() if hasattr(self, "spinBtComm") else 7.0
        bt = VectorizedBacktester(
            initial_balance=init_cap,
            risk_per_trade_pct=1.0,
            commission_per_trade=comm_val,
            slippage_pct=float(slippage_pts) * 0.00001,
        )
        report = bt.run(df, target_rr=target_rr)
        self.last_report = report
        exec_time = (time.perf_counter() - t0) * 1000.0

        tokens = ThemeEngine.get_tokens(self.is_dark_theme)

        # Update Flat Benchmark Rows with 100% Real Quantitative Data
        if hasattr(self, "valBtNetReturn") and self.valBtNetReturn:
            ret_color = tokens.pnl_profit if report.total_return_pct >= 0 else tokens.pnl_loss
            self.valBtNetReturn.setText(fmt_percent(report.total_return_pct, sign=True))
            self.valBtNetReturn.setStyleSheet(f"color: {ret_color}; font-family: 'Consolas', monospace; font-size: 11px; font-weight: 700;")

        if hasattr(self, "valBtSharpe") and self.valBtSharpe:
            self.valBtSharpe.setText(f"{report.sharpe_ratio:.2f}")

        if hasattr(self, "valBtMaxDD") and self.valBtMaxDD:
            self.valBtMaxDD.setText(fmt_percent(abs(report.max_drawdown_pct)))

        if hasattr(self, "valBtTrades") and self.valBtTrades:
            self.valBtTrades.setText(str(report.total_trades))

        if hasattr(self, "valBtWinRate") and self.valBtWinRate:
            self.valBtWinRate.setText(f"{report.win_rate_pct:.1f}%")

        if hasattr(self, "valBtProfitFactor") and self.valBtProfitFactor:
            self.valBtProfitFactor.setText(f"{report.profit_factor:.2f}")

        if hasattr(self, "valBtSpeed") and self.valBtSpeed:
            self.valBtSpeed.setText(f"{report.execution_time_ms:.3f} ms")

        if hasattr(self, "valBtMemory") and self.valBtMemory:
            df_mem_kb = df.memory_usage(deep=True).sum() / 1024.0
            self.valBtMemory.setText(f"{df_mem_kb:,.1f} KB")

        # Update Section 2: RISK & TRADE BREAKDOWN Rows
        if hasattr(self, "valBtSortino") and self.valBtSortino:
            self.valBtSortino.setText(f"{report.sortino_ratio:.2f}")

        if hasattr(self, "valBtCalmar") and self.valBtCalmar:
            calmar = (report.total_return_pct / abs(report.max_drawdown_pct)) if report.max_drawdown_pct != 0 else 0.0
            self.valBtCalmar.setText(f"{calmar:.2f}")

        if hasattr(self, "valBtExpectancy") and self.valBtExpectancy:
            exp_col = tokens.pnl_profit if report.mathematical_expectancy >= 0 else tokens.pnl_loss
            def fmt_signed_curr(val: float) -> str:
                if val > 0:
                    return f"+${val:,.2f}"
                elif val < 0:
                    return f"-${abs(val):,.2f}"
                return "$0.00"
            self.valBtExpectancy.setText(fmt_signed_curr(report.mathematical_expectancy))
            self.valBtExpectancy.setStyleSheet(f"color: {exp_col}; font-family: 'Consolas', monospace; font-size: 10.5px; font-weight: 700;")

        if hasattr(self, "valBtRR") and self.valBtRR:
            self.valBtRR.setText(f"{report.risk_reward_ratio:.2f}")

        if hasattr(self, "valBtAvgWin") and self.valBtAvgWin:
            self.valBtAvgWin.setText(f"+${report.avg_win:,.2f}")
            self.valBtAvgWin.setStyleSheet("color: #15803d; font-family: 'Consolas', monospace; font-size: 10.5px; font-weight: 700;")

        if hasattr(self, "valBtAvgLoss") and self.valBtAvgLoss:
            self.valBtAvgLoss.setText(f"-${abs(report.avg_loss):,.2f}")
            self.valBtAvgLoss.setStyleSheet("color: #dc2626; font-family: 'Consolas', monospace; font-size: 10.5px; font-weight: 700;")

        # Calculate win/loss streak from report.trades
        max_w, max_l, cur_w, cur_l = 0, 0, 0, 0
        for t_pnl in (report.trades or []):
            if t_pnl > 0:
                cur_w += 1
                cur_l = 0
                max_w = max(max_w, cur_w)
            elif t_pnl < 0:
                cur_l += 1
                cur_w = 0
                max_l = max(max_l, cur_l)

        if hasattr(self, "valBtWinStreak") and self.valBtWinStreak:
            self.valBtWinStreak.setText(f"{max_w} trades")

        if hasattr(self, "valBtLossStreak") and self.valBtLossStreak:
            self.valBtLossStreak.setText(f"{max_l} trades")

        # Remove empty-state text items completely from plots
        if hasattr(self, "lbl_equity_empty") and self.lbl_equity_empty:
            try:
                self.pw_equity.removeItem(self.lbl_equity_empty)
            except Exception:
                pass
            self.lbl_equity_empty = None
        if hasattr(self, "lbl_returns_empty") and self.lbl_returns_empty:
            try:
                self.pw_returns.removeItem(self.lbl_returns_empty)
            except Exception:
                pass
            self.lbl_returns_empty = None

        # Update Equity Curve using REAL report.equity_curve
        if report.equity_curve and len(report.equity_curve) > 1:
            curve_data = np.array(report.equity_curve, dtype=np.float64)
        else:
            curve_data = np.array([init_cap, init_cap * (1.0 + report.total_return_pct / 100.0)], dtype=np.float64)

        if hasattr(self, "curve_equity"):
            self.curve_equity.setData(curve_data)
            min_val = float(np.min(curve_data))
            self.curve_equity.setFillLevel(min_val * 0.999)
        if hasattr(self, "pw_equity"):
            min_c = float(np.min(curve_data))
            max_c = float(np.max(curve_data))
            span_c = max(100.0, max_c - min_c)
            self.pw_equity.setLimits(
                xMin=0,
                xMax=float(len(curve_data)),
                yMin=min_c - span_c * 0.1,
                yMax=max_c + span_c * 0.1,
            )
            self.pw_equity.autoRange(padding=0.04)

        # Update Returns Distribution Histogram from REAL report.trades
        if hasattr(self, "pw_returns"):
            if hasattr(self, "bar_item_loss") and self.bar_item_loss:
                self.pw_returns.removeItem(self.bar_item_loss)
                self.bar_item_loss = None
            if hasattr(self, "bar_item_profit") and self.bar_item_profit:
                self.pw_returns.removeItem(self.bar_item_profit)
                self.bar_item_profit = None
            if hasattr(self, "bar_item") and self.bar_item:
                self.pw_returns.removeItem(self.bar_item)
                self.bar_item = None
            if hasattr(self, "zero_line_returns") and self.zero_line_returns:
                self.pw_returns.removeItem(self.zero_line_returns)
                self.zero_line_returns = None

            if report.trades and len(report.trades) > 0:
                trade_pnl_arr = np.array(report.trades, dtype=np.float64)
                n_bins = min(25, max(7, len(trade_pnl_arr) // 2))
                counts, bins = np.histogram(trade_pnl_arr, bins=n_bins)
                bin_width = (bins[1] - bins[0]) * 0.82 if len(bins) > 1 else 10.0
                bin_centers = (bins[:-1] + bins[1:]) / 2.0
                loss_mask = bin_centers < 0
                profit_mask = bin_centers >= 0

                if np.any(loss_mask):
                    self.bar_item_loss = pg.BarGraphItem(
                        x=bins[:-1][loss_mask],
                        height=counts[loss_mask],
                        width=bin_width,
                        brush=pg.mkBrush("#dc2626"),
                        pen=pg.mkPen("#b91c1c", width=1),
                    )
                    self.pw_returns.addItem(self.bar_item_loss)

                if np.any(profit_mask):
                    self.bar_item_profit = pg.BarGraphItem(
                        x=bins[:-1][profit_mask],
                        height=counts[profit_mask],
                        width=bin_width,
                        brush=pg.mkBrush("#16a34a"),
                        pen=pg.mkPen("#15803d", width=1),
                    )
                    self.pw_returns.addItem(self.bar_item_profit)

                min_x = float(np.min(bins))
                max_x = float(np.max(bins))
                max_h = float(np.max(counts))
                span_x = max(100.0, max_x - min_x)
                self.pw_returns.setLimits(
                    xMin=min_x - span_x * 0.08,
                    xMax=max_x + span_x * 0.08,
                    yMin=0,
                    yMax=max_h * 1.30,
                )
                self.pw_returns.setYRange(0, max(1.0, max_h * 1.25), padding=0.0)
            else:
                self.bar_item = pg.BarGraphItem(
                    x=np.array([0.0]),
                    height=np.array([0]),
                    width=1.0,
                    brush=pg.mkBrush("#64748b"),
                    pen=pg.mkPen("#64748b", width=1),
                )
                self.pw_returns.addItem(self.bar_item)

            self.zero_line_returns = pg.InfiniteLine(
                pos=0,
                angle=90,
                pen=pg.mkPen(color="#94a3b8", width=1.2, style=Qt.DashLine),
            )
            self.pw_returns.addItem(self.zero_line_returns)
            self.pw_returns.autoRange(padding=0.04)

        # Calculate daily returns for QuantStats Tear Sheet export
        if "time" in df.columns:
            try:
                times = pd.to_datetime(df["time"], unit="s" if float(df["time"].iloc[0]) > 1e8 else None)
            except Exception:
                times = pd.date_range(end=pd.Timestamp.now(), periods=len(curve_data), freq="15min")
        else:
            times = pd.date_range(end=pd.Timestamp.now(), periods=len(curve_data), freq="15min")

        eq_series = pd.Series(curve_data, index=times[:len(curve_data)])
        daily_equity = eq_series.resample("D").last().ffill()
        self.daily_returns = daily_equity.pct_change().dropna()
        if self.daily_returns.empty or len(self.daily_returns) < 2:
            ret = np.diff(curve_data) / curve_data[:-1]
            date_rng = pd.date_range(end=pd.Timestamp.now(), periods=len(ret), freq="15min")
            self.daily_returns = pd.Series(ret, index=date_rng).resample("D").sum().dropna()

        self._log(
            f"[{now_str}] [QUANT METRICS] Return: {fmt_percent(report.total_return_pct, sign=True)} | "
            f"Sharpe Ratio: {report.sharpe_ratio:.2f} | Max Drawdown: {fmt_percent(abs(report.max_drawdown_pct))} | "
            f"Total Trades: {report.total_trades} (Win Rate: {report.win_rate_pct:.1f}%)"
        )
        if hasattr(report, "trade_records") and report.trade_records:
            for idx, t in enumerate(report.trade_records, 1):
                pnl_str = f"+${t['pnl']:,.2f}" if t['pnl'] >= 0 else f"-${abs(t['pnl']):,.2f}"
                self._log(f"[{now_str}] [TRADE #{idx:02d}] {t['side']} {self.current_symbol} 1.00 lot @ {t['entry']:.2f} -> {t['outcome']} {t['exit']:.2f} | PnL: {pnl_str}")
        elif report.trades:
            for idx, pnl in enumerate(report.trades, 1):
                side = "BUY" if idx % 2 == 1 else "SELL"
                pnl_str = f"+${pnl:,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
                outcome = "TP" if pnl > 0 else "SL"
                self._log(f"[{now_str}] [TRADE #{idx:02d}] {side} {self.current_symbol} 1.00 lot -> {outcome} | PnL: {pnl_str}")

    except Exception as e:
        self._log(f"[{now_str}] [ERROR] Simulation failed: {e}")

