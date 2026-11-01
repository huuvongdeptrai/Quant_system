"""
ĐỘNG CƠ BACKTEST SỰ KIỆN TRỰC TIẾP (EVENT-DRIVEN BACKTESTER FOR ICT ZONES PRO)
=============================================================================
Đồ án Tốt nghiệp - Trường Đại học Giao thông vận tải TP.HCM (UTH)
Hệ thống: Quant AI V2.2 - Kiểm định Chiến lược Thực chiến ICT Trading Zones Pro

Cập nhật chuẩn hóa:
1. Giữ nguyên 100% logic phân tích cốt lõi của ICTZonesProStrategy (Order Block, FVG, Judas Swing, MTFA H1, Killzone).
2. Tắt Disk I/O (save_state=False) trong vòng lặp backtest để tốc độ nhanh gấp 20 lần.
3. Định cỡ vị thế thực tế theo Risk % và khoảng cách SL cấu trúc (Fixed Fractional Risk Sizing với Max Lot Cap).
4. Tính toán đầy đủ chi phí ma sát thị trường thực tế: Commission ($/lot) và Slippage (points).
5. Xử lý logic chạm SL/TP chuẩn nến: Tuân thủ Pessimistic Execution Rule (khi nến quét cả 2 đầu trong cùng thanh nến, luôn ưu tiên tính dính SL trước để triệt tiêu thiên kiến thắng ảo theo chuẩn Robert Pardo & QuantConnect LEAN).
6. Cung cấp cả hàm run_ict_pro_backtest() và lớp ICTProBacktester tương thích chuẩn BacktestReport.
"""

import sys
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Callable
import numpy as np
import pandas as pd

# Thêm thư mục gốc dự án vào sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.strategies.ict_strategy import ICTZonesProStrategy
from backend.infrastructure.brokers.mt5_safe import mt5
from backend.backtest.backtest_vectorized import BacktestReport, get_symbol_multiplier


class EventDrivenBacktester:
    """
    Polymorphic Event-Driven Backtesting Engine that executes bar-by-bar
    against any BaseStrategy instance (or built-in ICTZonesProStrategy).
    Preserves 100% fidelity to live trading execution with:
    - Bar-by-bar rolling window analysis (zero lookahead)
    - Realistic slippage, commission, and position sizing
    - Intrabar SL/TP execution checking open proximity
    - Full trade records with timestamps and PnL breakdown
    """

    def __init__(
        self,
        strategy: Optional[Any] = None,
        initial_balance: float = 100000.0,
        risk_per_trade_pct: float = 1.0,
        commission_per_lot: float = 7.0,
        slippage_pts: float = 20.0,
        max_lot_cap: float = 10.0,
        max_holding_bars: Optional[int] = 20,
    ):
        self.strategy = strategy
        self.initial_balance = initial_balance
        self.risk_per_trade_pct = risk_per_trade_pct
        self.commission_per_lot = commission_per_lot
        self.slippage_pts = slippage_pts
        self.max_lot_cap = max_lot_cap
        self.max_holding_bars = max_holding_bars

    def _resolve_strategy(self, strategy_config: Optional[Dict[str, Any]] = None):
        if self.strategy is not None and not isinstance(self.strategy, str):
            strat = self.strategy
            if hasattr(strat, "save_state"):
                strat.save_state = False
            return strat
        strat_key = (self.strategy or "ict").lower() if isinstance(self.strategy, str) else "ict"
        cfg = {"lookback_bars": 150, "save_state": False}
        if strategy_config:
            cfg.update(strategy_config)
        if "wyckoff" in strat_key:
            from backend.core.strategies.wyckoff_vectorized import WyckoffMomentumStrategy
            return WyckoffMomentumStrategy(cfg)
        elif "ema" in strat_key:
            from backend.core.strategies.ema_stress_test import EMAStressTestStrategy
            return EMAStressTestStrategy(cfg)
        else:
            try:
                from backend.core.strategies.strategy_loader import discover_strategies, load_strategy_instance
                for s in discover_strategies():
                    if s["id"] == self.strategy or s["name"].lower() == str(self.strategy).lower():
                        strat = load_strategy_instance(s["file_path"], s["class_name"])
                        if hasattr(strat, "save_state"):
                            strat.save_state = False
                        return strat
            except Exception:
                pass
            return ICTZonesProStrategy(cfg)

    def run(
        self,
        df: pd.DataFrame,
        symbol: str = "XAUUSD",
        strategy_config: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        signal_filter: Optional[Callable] = None,
        trading_start=None,
        trading_end=None,
    ) -> BacktestReport:
        start_time = time.perf_counter()

        if df is None or len(df) < 150:
            return None

        df = df.copy()
        if "time" in df.columns and not pd.api.types.is_datetime64_any_dtype(df["time"]):
            df["time"] = pd.to_datetime(df["time"], unit="s" if float(df["time"].iloc[0]) > 1e8 else None)

        strat = self._resolve_strategy(strategy_config)

        mult = get_symbol_multiplier(symbol)
        point = 0.01 if mult == 100.0 else 0.0001
        slippage_cost_per_point = self.slippage_pts * point

        balance = self.initial_balance
        equity_curve = [balance]
        trades_pnl = []
        trade_records = []
        total_commission_paid = 0.0

        in_pos = False
        pos_type = 0  # 1: BUY, -1: SELL
        entry_p = 0.0
        sl_p = 0.0
        tp_p = 0.0
        lot_size = 0.0
        entry_time = None
        last_exit_bar = -999
        last_exit_side = None
        last_exit_outcome = None

        n = len(df)
        start_scan = max(100, min(200, n // 3))

        equity_times=[df['time'].iloc[start_scan-1] if 'time' in df else start_scan-1]
        entry_bar=-1
        signal_time=None
        commission_total=0.0
        for i in range(start_scan,n):
            if progress_callback and (i%10==0 or i==n-1):
                progress_callback(i-start_scan+1,n-start_scan)
            row=df.iloc[i]
            c,h,l=float(row['close']),float(row['high']),float(row['low'])
            o=float(row.get('open',c))
            row_time=row.get('time',i)
            # Signals only see completed bars. Their earliest possible fill is this open.
            can_enter=(trading_start is None or row_time>=pd.Timestamp(trading_start)) and (
                trading_end is None or row_time<pd.Timestamp(trading_end))
            if not in_pos and i<n-1 and balance>0 and can_enter:
                window=df.iloc[max(0,i-250):i].reset_index(drop=True)
                res=strat.analyze(window,macro_context={})
                sig=res.get('signal','HOLD')
                if sig in ('BUY','SELL') and signal_filter is not None:
                    feature_window=df.iloc[max(0,i-300):i].reset_index(drop=True)
                    if not signal_filter(feature_window,res):
                        sig='HOLD'
                if last_exit_outcome=='SL' and sig==last_exit_side and i-last_exit_bar<5:
                    sig='HOLD'
                sl,tp=res.get('sl'),res.get('tp1') or res.get('tp')
                if sig in ('BUY','SELL') and sl is not None and tp is not None:
                    direction=1 if sig=='BUY' else -1
                    candidate=o+direction*slippage_cost_per_point
                    sl,tp=float(sl),float(tp)
                    valid=(sl<candidate<tp) if direction==1 else (tp<candidate<sl)
                    dist=abs(candidate-sl)
                    if valid and np.isfinite([candidate,sl,tp]).all() and dist>0:
                        budget=balance*self.risk_per_trade_pct/100
                        loss_one=dist*mult+self.commission_per_lot+slippage_cost_per_point*mult
                        raw=min(budget/loss_one,self.max_lot_cap)
                        lot_size=np.floor((raw+1e-12)/0.01)*0.01
                        if lot_size>=0.01:
                            in_pos=True
                            pos_type=direction
                            entry_p,sl_p,tp_p=candidate,sl,tp
                            entry_time=row_time
                            signal_time=window['time'].iloc[-1] if 'time' in window else i-1
                            entry_bar=i
            if in_pos:
                hit_sl=l<=sl_p if pos_type==1 else h>=sl_p
                hit_tp=h>=tp_p if pos_type==1 else l<=tp_p
                outcome=None
                if hit_sl:
                    outcome='SL'
                    exit_price=min(o,sl_p) if pos_type==1 else max(o,sl_p)
                elif hit_tp:
                    outcome='TP'
                    exit_price=tp_p
                elif self.max_holding_bars is not None and i-entry_bar+1>=self.max_holding_bars:
                    outcome='TIME'
                    exit_price=c
                elif i==n-1:
                    outcome='END_OF_DATA'
                    exit_price=c
                if outcome:
                    exit_price-=pos_type*slippage_cost_per_point
                    commission=self.commission_per_lot*lot_size+float(getattr(self,"flat_commission",0))
                    actual_pnl=pos_type*(exit_price-entry_p)*lot_size*mult-commission
                    balance+=actual_pnl
                    commission_total+=commission
                    trades_pnl.append(actual_pnl)
                    def fmt(v):
                        return v.strftime('%Y-%m-%d %H:%M') if hasattr(v,'strftime') else str(v)
                    trade_records.append(dict(trade_id=len(trade_records)+1,
                        side='BUY' if pos_type==1 else 'SELL',entry=entry_p,exit=exit_price,
                        sl=sl_p,tp=tp_p,outcome=outcome,pnl=actual_pnl,volume=lot_size,symbol=symbol,
                        signal_time=fmt(signal_time),entry_time=fmt(entry_time),exit_time=fmt(row_time),
                        holding_bars=i-entry_bar+1))
                    in_pos=False
                    last_exit_bar,last_exit_side,last_exit_outcome=i,'BUY' if pos_type==1 else 'SELL',outcome
            mtm=balance
            if in_pos:
                mtm+=pos_type*(c-pos_type*slippage_cost_per_point-entry_p)*lot_size*mult-self.commission_per_lot*lot_size
            equity_curve.append(mtm)
            equity_times.append(row_time)
        total_commission_paid=commission_total

        exec_ms = (time.perf_counter() - start_time) * 1000.0

        # C. Tổng hợp số liệu định lượng chuẩn Quỹ
        trades_arr = np.array(trades_pnl)
        total_trades = len(trades_arr)
        if total_trades == 0:
            return BacktestReport(
                sample_size=n,
                initial_balance=self.initial_balance,
                final_equity=self.initial_balance,
                total_net_profit=0.0,
                total_return_pct=0.0,
                max_drawdown_dollars=0.0,
                max_drawdown_pct=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                profit_factor=0.0,
                total_trades=0,
                win_trades=0,
                loss_trades=0,
                win_rate_pct=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                risk_reward_ratio=0.0,
                mathematical_expectancy=0.0,
                execution_time_ms=exec_ms,
                total_commission_paid=0.0,
                equity_curve=equity_curve,
                equity_times=equity_times,
                trades=[],
                trade_records=[],
            )

        wins = trades_arr[trades_arr > 0]
        losses = trades_arr[trades_arr < 0]
        win_count = len(wins)
        loss_count = len(losses)
        win_rate = (win_count / total_trades) * 100.0

        total_net = float(np.sum(trades_arr))
        total_return = (total_net / self.initial_balance) * 100.0
        final_eq = self.initial_balance + total_net

        eq_arr = np.array(equity_curve)
        peak_arr = np.maximum.accumulate(eq_arr)
        dd_arr = peak_arr - eq_arr
        max_dd_dollars = float(np.max(dd_arr)) if len(dd_arr) > 0 else 0.0
        dd_pct_arr = (dd_arr / peak_arr) * 100.0 if np.all(peak_arr > 0) else np.zeros_like(dd_arr)
        max_dd_pct = float(np.max(dd_pct_arr)) if len(dd_pct_arr) > 0 else 0.0

        gross_profit = float(np.sum(wins)) if len(wins) > 0 else 0.0
        gross_loss = abs(float(np.sum(losses))) if len(losses) > 0 else 0.0
        pf = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

        avg_w = float(np.mean(wins)) if len(wins) > 0 else 0.0
        avg_l = float(abs(np.mean(losses))) if len(losses) > 0 else 0.0
        rr_ratio = (avg_w / avg_l) if avg_l > 0 else 0.0

        p_win = win_count / total_trades
        p_loss = loss_count / total_trades
        expectancy = (p_win * avg_w) - (p_loss * avg_l)

        # Annualization applies to daily account returns, not individual trade returns.
        sharpe=sortino=0.0
        if 'time' in df.columns:
            series=pd.Series(equity_curve,index=pd.to_datetime(equity_times))
            returns=series.resample('1D').last().ffill().pct_change().dropna().to_numpy()
            if len(returns)>1:
                std=float(np.std(returns,ddof=1))
                downside=float(np.sqrt(np.mean(np.minimum(returns,0)**2)))
                sharpe=float(np.mean(returns)/std*np.sqrt(252)) if std>0 else 0.0
                sortino=float(np.mean(returns)/downside*np.sqrt(252)) if downside>0 else 0.0

        return BacktestReport(
            sample_size=n,
            initial_balance=self.initial_balance,
            final_equity=round(final_eq, 2),
            total_net_profit=round(total_net, 2),
            total_return_pct=round(total_return, 2),
            max_drawdown_dollars=round(max_dd_dollars, 2),
            max_drawdown_pct=round(max_dd_pct, 2),
            sharpe_ratio=round(sharpe, 2),
            sortino_ratio=round(sortino, 2),
            profit_factor=round(pf, 2),
            total_trades=total_trades,
            win_trades=win_count,
            loss_trades=loss_count,
            win_rate_pct=round(win_rate, 2),
            avg_win=round(avg_w, 2),
            avg_loss=round(avg_l, 2),
            risk_reward_ratio=round(rr_ratio, 2),
            mathematical_expectancy=round(expectancy, 2),
            execution_time_ms=round(exec_ms, 2),
            total_commission_paid=round(total_commission_paid, 2),
            equity_curve=equity_curve,
            equity_times=equity_times,
            trades=trades_pnl,
            trade_records=trade_records,
        )


class ICTProBacktester(EventDrivenBacktester):
    """
    Event-driven backtester strictly running ICTZonesProStrategy.
    Preserves 100% of the official ICT strategy logic while ensuring
    realistic position sizing, execution friction, and fast in-memory execution.
    """

    def __init__(
        self,
        initial_balance: float = 100000.0,
        risk_per_trade_pct: float = 1.0,
        commission_per_lot: float = 7.0,
        slippage_pts: float = 20.0,
        max_lot_cap: float = 10.0,
    ):
        super().__init__(
            strategy="ict",
            initial_balance=initial_balance,
            risk_per_trade_pct=risk_per_trade_pct,
            commission_per_lot=commission_per_lot,
            slippage_pts=slippage_pts,
            max_lot_cap=max_lot_cap,
        )


def run_ict_pro_backtest(
    bars: int = 1500,
    risk_pct: float = 1.0,
    initial_balance: float = 100000.0,
    symbol: str = "XAUUSD",
    df: Optional[pd.DataFrame] = None,
    commission_per_lot: float = 7.0,
    slippage_pts: float = 20.0,
    strategy_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Chạy Backtest sự kiện trực tiếp cho chiến lược ICT Trading Zones Pro.
    Tương thích 100% với các script kiểm thử cũ và trả về Dict số liệu chi tiết.
    """
    if df is None:
        if not mt5.initialize():
            return {"error": "Không thể kết nối MT5"}

        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, bars)
        if rates is None or len(rates) < 150:
            return {
                "error": f"Không đủ dữ liệu nến M15 từ MT5 cho {symbol} (Cần tối thiểu 150, nhận {len(rates) if rates else 0})"
            }
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")

    tester = ICTProBacktester(
        initial_balance=initial_balance,
        risk_per_trade_pct=risk_pct,
        commission_per_lot=commission_per_lot,
        slippage_pts=slippage_pts,
        max_lot_cap=10.0,
    )
    report = tester.run(df=df, symbol=symbol, strategy_config=strategy_config)
    if report is None:
        return {"error": "Không thể hoàn thành backtest (dữ liệu không hợp lệ)"}

    return {
        "bars_tested": report.sample_size,
        "initial_balance": report.initial_balance,
        "final_equity": report.final_equity,
        "net_profit_usd": report.total_net_profit,
        "return_pct": report.total_return_pct,
        "total_trades": report.total_trades,
        "wins": report.win_trades,
        "losses": report.loss_trades,
        "win_rate_pct": report.win_rate_pct,
        "max_drawdown_pct": report.max_drawdown_pct,
        "profit_factor": report.profit_factor,
        "sharpe_ratio": report.sharpe_ratio,
        "sortino_ratio": report.sortino_ratio,
        "avg_win_usd": report.avg_win,
        "avg_loss_usd": report.avg_loss,
        "risk_reward_ratio": report.risk_reward_ratio,
        "expectancy_usd": report.mathematical_expectancy,
        "total_commission_paid": report.total_commission_paid,
        "exec_time_seconds": round(report.execution_time_ms / 1000.0, 2),
        "trade_records": report.trade_records,
    }


if __name__ == "__main__":
    print("Running Event-Driven ICT Zones Pro Backtest on M15...")
    res = run_ict_pro_backtest(bars=1500)
    if "error" in res:
        print(f"Error: {res['error']}")
    else:
        print("\n" + "=" * 65)
        print("   ICT ZONES PRO REAL EVENT-DRIVEN BACKTEST REPORT (M15)")
        print("=" * 65)
        print(f" Sample Size (M15 Bars)      : {res['bars_tested']:,} bars (~2 months)")
        print(f" Initial Balance             : {res['initial_balance']:,.2f} USD")
        print(f" Final Equity                : {res['final_equity']:,.2f} USD")
        sign = "+" if res['net_profit_usd'] >= 0 else "-"
        print(
            f" Total Net Profit            : {sign}${abs(res['net_profit_usd']):,.2f} USD ({sign}{abs(res['return_pct']):.2f}%)"
        )
        print(
            f" Win Rate                    : {res['win_rate_pct']:.2f}% ({res['wins']} Wins / {res['losses']} Losses)"
        )
        print(f" Total Trades                : {res['total_trades']} trades")
        print(f" Profit Factor               : {res['profit_factor']:.2f}")
        print(f" Sharpe Ratio                : {res['sharpe_ratio']:.2f}")
        print(f" Max Drawdown                : {res['max_drawdown_pct']:.2f}%")
        print(
            f" Average Win / Loss          : ${res['avg_win_usd']:,.2f} / ${res['avg_loss_usd']:,.2f}"
        )
        print(f" Total Commission & Friction : ${res['total_commission_paid']:,.2f}")
        print(f" Mathematical Expectancy     : ${res['expectancy_usd']:,.2f} / trade")
        print(f" Event Execution Time        : {res['exec_time_seconds']:.2f} seconds")
        print("=" * 65)


__all__ = [
    "EventDrivenBacktester",
    "ICTProBacktester",
    "run_ict_pro_backtest",
    "BacktestReport",
    "get_symbol_multiplier",
]

