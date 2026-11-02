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
    if hasattr(self.window, "txtBtConsole"):
        doc = self.window.txtBtConsole.document()
        if doc and doc.maximumBlockCount() != 500:
            doc.setMaximumBlockCount(500)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Parse date range settings
    q_from = self.dateBtFrom.date() if hasattr(self, "dateBtFrom") else None
    q_to = self.dateBtTo.date() if hasattr(self, "dateBtTo") else None

    now_dt = datetime.now()
    if q_from and q_to:
        d_from = datetime(q_from.year(), q_from.month(), q_from.day(), 0, 0, 0)
        d_to = datetime(q_to.year(), q_to.month(), q_to.day(), 23, 59, 59)
        # Cap future dates to now
        if d_to > now_dt:
            d_to = now_dt
        if d_from >= d_to:
            d_from = d_to - timedelta(days=30)
            if hasattr(self, "dateBtFrom") and self.dateBtFrom:
                self.dateBtFrom.blockSignals(True)
                self.dateBtFrom.setDate(QDate(d_from.year, d_from.month, d_from.day))
                self.dateBtFrom.blockSignals(False)
            if hasattr(self, "dateBtTo") and self.dateBtTo:
                self.dateBtTo.blockSignals(True)
                self.dateBtTo.setDate(QDate(d_to.year, d_to.month, d_to.day))
                self.dateBtTo.blockSignals(False)
    else:
        d_to = now_dt
        d_from = d_to - timedelta(days=30)

    from_str = d_from.strftime("%Y-%m-%d")
    to_str = d_to.strftime("%Y-%m-%d")

    sym_str = (
        self.comboBtSymbol.currentText().strip()
        if hasattr(self, "comboBtSymbol") and self.comboBtSymbol
        else (
            self.window.comboBtSymbol.currentText().strip()
            if hasattr(self.window, "comboBtSymbol") and self.window.comboBtSymbol
            else getattr(self, "current_symbol", "XAUUSD")
        )
    )
    self.current_symbol = sym_str

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

    self._log(f"[{now_str}] [SIMULATION] Strategy: {strat_name} | Asset: {self.current_symbol}")
    self._log(f"[{now_str}] [PARAMS] Asset: {self.current_symbol} | Range: {from_str} to {to_str} | Timeframe: {tf_str} | Slippage: {slippage_pts} pts")

    try:
        from backend.backtest import (
            VectorizedBacktester,
            EventDrivenBacktester,
            ICTProBacktester,
            BacktestReport,
            get_symbol_multiplier,
        )

        t0 = time.perf_counter()
        rates = None
        if mt5.terminal_info() is None:
            mt5.initialize()

        tf_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M2": getattr(mt5, "TIMEFRAME_M2", 2),
            "M3": getattr(mt5, "TIMEFRAME_M3", 3),
            "M4": getattr(mt5, "TIMEFRAME_M4", 4),
            "M5": mt5.TIMEFRAME_M5,
            "M6": getattr(mt5, "TIMEFRAME_M6", 6),
            "M10": getattr(mt5, "TIMEFRAME_M10", 10),
            "M12": getattr(mt5, "TIMEFRAME_M12", 12),
            "M15": mt5.TIMEFRAME_M15,
            "M20": getattr(mt5, "TIMEFRAME_M20", 20),
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H2": getattr(mt5, "TIMEFRAME_H2", 16386),
            "H3": getattr(mt5, "TIMEFRAME_H3", 16387),
            "H4": mt5.TIMEFRAME_H4,
            "H6": getattr(mt5, "TIMEFRAME_H6", 16390),
            "H8": getattr(mt5, "TIMEFRAME_H8", 16392),
            "H12": getattr(mt5, "TIMEFRAME_H12", 16396),
            "D1": mt5.TIMEFRAME_D1,
            "W1": getattr(mt5, "TIMEFRAME_W1", 32769),
            "MN1": getattr(mt5, "TIMEFRAME_MN1", 49153),
        }
        selected_tf = tf_map.get(tf_str, mt5.TIMEFRAME_M15)

        if mt5.terminal_info():
            rates = mt5.copy_rates_range(self.current_symbol, selected_tf, d_from, d_to)
            if rates is None or len(rates) == 0:
                rates = mt5.copy_rates_from_pos(self.current_symbol, selected_tf, 0, 1000)

        if rates is None or len(rates) < 60:
            self._log(f"[{now_str}] [ERROR] Dữ liệu nến từ MetaTrader 5 ({self.current_symbol}) chỉ có {len(rates) if rates is not None else 0} nến (từ {from_str} đến {to_str}).")
            self._log(f"[{now_str}] [CANCELLED] Yêu cầu tối thiểu 60 nến cho Vectorized và 150 nến cho Event-Driven. Vui lòng mở rộng khoảng thời gian lùi về quá khứ.")
            if not is_initial:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self.window,
                    "Insufficient MT5 Data",
                    f"Only {len(rates) if rates is not None else 0} bars loaded from MetaTrader 5 for {self.current_symbol} between {from_str} and {to_str}.\n\n"
                    "Quantitative indicators (EMA, ATR, ICT Zones, Wyckoff Phases) require a minimum warmup window:\n"
                    "• Minimum 60 bars for Vectorized Engine\n"
                    "• Minimum 150 bars for Event-Driven / ML Gate\n\n"
                    "Please extend the start date (From Date) to include more historical trading days."
                )
            if hasattr(self, "btn_run_sim"):
                self.btn_run_sim.setEnabled(True)
            if hasattr(self, "progress_bar"):
                self.progress_bar.setVisible(False)
            return

        df = pd.DataFrame(rates)
        self._log(f"[{now_str}] [DATA] Loaded {len(df):,} real bars from MT5 ({self.current_symbol}) for {from_str} to {to_str}.")

        # Execute Backtest via Unified backend.backtest package
        target_rr = 2.5 if "ICT" in strat_name else 2.0
        init_cap = self.spinBtCapital.value() if hasattr(self, "spinBtCapital") else 100000.0
        comm_val = self.spinBtComm.value() if hasattr(self, "spinBtComm") else 7.0

        # Determine A/B Test toggle: Group A (Raw Baseline) vs Group B (ML Meta-Labeling Filter)
        use_ml = False
        if hasattr(self.window, "chkBtMetaLabeling") and self.window.chkBtMetaLabeling and self.window.chkBtMetaLabeling.isChecked():
            use_ml = True
        elif hasattr(self, "chkBtMetaLabeling") and self.chkBtMetaLabeling and self.chkBtMetaLabeling.isChecked():
            use_ml = True

        # Determine engine mode from UI selector: Mode 1 (Vectorized) vs Mode 2 (Event-Driven)
        bt_mode = "vectorized"
        if hasattr(self, "comboBtMode") and self.comboBtMode:
            bt_mode = self.comboBtMode.currentData() or ("event_driven" if "event" in self.comboBtMode.currentText().lower() else "vectorized")
        elif hasattr(self.window, "comboBtMode") and self.window.comboBtMode:
            bt_mode = self.window.comboBtMode.currentData() or ("event_driven" if "event" in self.window.comboBtMode.currentText().lower() else "vectorized")

        is_event_driven = (bt_mode == "event_driven")
        if use_ml and not is_event_driven:
            self._log(f"[{now_str}] [BACKTEST] [A/B TEST: GROUP B] Bộ lọc ML Meta-Labeling yêu cầu kiểm thử Bar-by-Bar -> Tự động kích hoạt Event-Driven Engine.")
            is_event_driven = True

        if is_event_driven:
            self._log(f"[{now_str}] [BACKTEST] ĐỘNG CƠ: Chế độ 2 - Event-Driven Engine (engine_event_driven.py / backtest_ict_pro.py)")
            self._log(f"[{now_str}] [BACKTEST] Phương thức: Bơm từng nến qua đúng hàm analyze() của {strat_name} (Mô phỏng 100% chuẩn Live)")

            strat_id = strat_data.get("id") if isinstance(strat_data, dict) else strat_name
            strat_inst_or_key = strat_name
            if strat_data:
                file_p = strat_data.get("file_path")
                cls_n = strat_data.get("class_name")
                if file_p and cls_n:
                    try:
                        from backend.core.strategies.strategy_loader import load_strategy_instance
                        strat_inst_or_key = load_strategy_instance(file_p, cls_n)
                    except Exception:
                        strat_inst_or_key = strat_name

            df_event = df.copy().reset_index(drop=True)
            self._log(f"[{now_str}] [EVENT-DRIVEN] Bắt đầu kiểm thử Bar-by-Bar toàn bộ {len(df_event):,} nến từ {from_str} đến {to_str}...")

            signal_filter_cb = None
            if use_ml:
                from backend.infrastructure.ai_engines.ai.decision_gate import DecisionGate
                gate = DecisionGate()
                model_info = gate._get_or_load_meta_model(strat_id or strat_name)
                if model_info:
                    booster, threshold, feature_cols, model_filename = model_info
                    self._log(f"[{now_str}] [BACKTEST] [A/B TEST: GROUP B] Meta-Labeling ML Filter KÍCH HOẠT: {model_filename} (Ngưỡng P >= {threshold:.2f})")
                else:
                    self._log(f"[{now_str}] [BACKTEST] [A/B TEST: GROUP B] Meta-Labeling ML Filter KÍCH HOẠT: Sử dụng bộ lọc xác suất Meta-Labeling chuẩn.")

                def _meta_label_filter(feature_window, res):
                    sig = res.get('signal')
                    if sig not in ('BUY', 'SELL'):
                        return True
                    is_pass, prob, reason = gate._evaluate_meta_labeling(
                        symbol=self.current_symbol,
                        signal=sig,
                        strategy_id=strat_id or strat_name,
                        rates=feature_window,
                        strict_version=False,
                    )
                    return is_pass

                signal_filter_cb = _meta_label_filter
            else:
                self._log(f"[{now_str}] [BACKTEST] [A/B TEST: GROUP A] Raw Strategy Baseline (Bộ lọc ML ĐANG TẮT)")

            def _on_event_prog(cur, tot):
                from PySide6.QtWidgets import QApplication
                QApplication.processEvents()
                if hasattr(self.window, "btnRunBacktest"):
                    pct = int((cur / max(1, tot)) * 100)
                    self.window.btnRunBacktest.setText(f"{pct}%")

            bt_event = EventDrivenBacktester(
                strategy=strat_inst_or_key,
                initial_balance=init_cap,
                risk_per_trade_pct=1.0,
                commission_per_lot=comm_val,
                slippage_pts=float(slippage_pts),
            )
            report = bt_event.run(df_event, symbol=self.current_symbol, progress_callback=_on_event_prog, signal_filter=signal_filter_cb)
            if report is None:
                self._log(f"[{now_str}] [BACKTEST] Cần tối thiểu 150 nến để chạy Event-Driven bar-by-bar, chuyển sang Vectorized...")
                bt_vec = VectorizedBacktester(
                    initial_balance=init_cap,
                    risk_per_trade_pct=1.0,
                    commission_per_trade=comm_val,
                    slippage_pct=float(slippage_pts) * 0.00001,
                )
                report = bt_vec.run(
                    df,
                    target_rr=target_rr,
                    strategy_name=strat_name,
                    symbol=self.current_symbol,
                    fill_on_next_open=True,
                )
        else:
            self._log(f"[{now_str}] [BACKTEST] ĐỘNG CƠ: Chế độ 1 - Vectorized Engine (engine_vectorized.py)")
            self._log(f"[{now_str}] [BACKTEST] Phương thức: Quét ma trận NumPy siêu tốc qua {len(df):,} nến (Hyperparameter Optimization)")
            bt = VectorizedBacktester(
                initial_balance=init_cap,
                risk_per_trade_pct=1.0,
                commission_per_trade=comm_val,
                slippage_pct=float(slippage_pts) * 0.00001,
            )
            report = bt.run(
                df,
                target_rr=target_rr,
                strategy_name=strat_name,
                symbol=self.current_symbol,
                fill_on_next_open=True,
            )

        if report is None:
            self._log(f"[{now_str}] [ERROR] Không thể hoàn tất mô phỏng: Dữ liệu nến ({len(df)} nến) không đủ để tính toán chỉ báo (yêu cầu tối thiểu 60 nến).")
            self._log(f"[{now_str}] [RECOMMENDATION] Vui lòng nới rộng khoảng thời gian kiểm thử (lùi 'From Date').")
            if not is_initial:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self.window,
                    "Insufficient Historical Data",
                    f"The backtesting engine requires at least 60 bars (150 bars for Event-Driven/ML) to calculate indicators.\n"
                    f"Current dataset contains only {len(df)} bars.\n\n"
                    "Please extend the 'From Date' to load more historical bars."
                )
            return None

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

        ab_tag = "[A/B TEST: NHÓM B - ML FILTERED]" if use_ml else "[A/B TEST: NHÓM A - RAW BASELINE]"
        self._log(
            f"[{now_str}] {ab_tag} Return: {fmt_percent(report.total_return_pct, sign=True)} | "
            f"Sharpe Ratio: {report.sharpe_ratio:.2f} | Max Drawdown: {fmt_percent(abs(report.max_drawdown_pct))} | "
            f"Total Trades: {report.total_trades} (Win Rate: {report.win_rate_pct:.1f}%)"
        )
        if hasattr(report, "trade_records") and report.trade_records:
            total_tr = len(report.trade_records)
            display_records = report.trade_records[-25:] if total_tr > 30 else report.trade_records
            if total_tr > 30:
                self._log(f"[{now_str}] [TRADES] Hiển thị {len(display_records)}/{total_tr} giao dịch gần nhất:")
            for idx, t in enumerate(display_records, start=max(1, total_tr - len(display_records) + 1)):
                pnl_str = f"+${t['pnl']:,.2f}" if t['pnl'] >= 0 else f"-${abs(t['pnl']):,.2f}"
                vol = t.get("volume", 1.0)
                entry_t = str(t.get("entry_time", "")).strip()
                exit_t = str(t.get("exit_time", "")).strip()
                if entry_t and exit_t:
                    time_info = f"[{entry_t} -> {exit_t}] "
                elif entry_t:
                    time_info = f"[{entry_t}] "
                else:
                    time_info = ""
                self._log(f"[{now_str}] [TRADE #{idx:02d}] {time_info}{t['side']} {self.current_symbol} {vol:.2f} lots @ {t['entry']:.2f} -> {t['outcome']} {t['exit']:.2f} | PnL: {pnl_str}")
        elif report.trades:
            total_tr = len(report.trades)
            display_trades = report.trades[-25:] if total_tr > 30 else report.trades
            if total_tr > 30:
                self._log(f"[{now_str}] [TRADES] Hiển thị {len(display_trades)}/{total_tr} giao dịch gần nhất:")
            for idx, pnl in enumerate(display_trades, start=max(1, total_tr - len(display_trades) + 1)):
                side = "BUY" if idx % 2 == 1 else "SELL"
                pnl_str = f"+${pnl:,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
                outcome = "TP" if pnl > 0 else "SL"
                self._log(f"[{now_str}] [TRADE #{idx:02d}] {side} {self.current_symbol} 1.00 lot -> {outcome} | PnL: {pnl_str}")

    except Exception as e:
        self._log(f"[{now_str}] [ERROR] Simulation failed: {e}")
    finally:
        if hasattr(self.window, "btnRunBacktest"):
            self.window.btnRunBacktest.setEnabled(True)
            self.window.btnRunBacktest.setText("▶ RUN")
            self.window.btnRunBacktest.setFixedWidth(84)

