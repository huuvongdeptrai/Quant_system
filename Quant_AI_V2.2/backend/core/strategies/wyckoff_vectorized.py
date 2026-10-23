"""
GIAI ĐOẠN 2 & 6: VECTORIZED BACKTESTING ENGINE (TỐI ƯU HÓA MA TRẬN NUMPY CHO MÁY 8GB RAM)
Đồ án Tốt nghiệp - Trường Đại học Giao thông vận tải TP.HCM (UTH)
Hệ thống: Quant AI V2.2 - Đo lường hiệu năng quá khứ không thiên kiến (Kèm Commission & Slippage)
"""

import time
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
from dataclasses import dataclass

from backend.core.strategies.base_strategy import (
    BaseStrategy,
    StrategySignal,
    ChecklistItem,
    ChecklistStatus,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class BacktestReport:
    sample_size: int
    initial_balance: float
    final_equity: float
    total_net_profit: float
    total_return_pct: float
    max_drawdown_dollars: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    profit_factor: float
    total_trades: int
    win_trades: int
    loss_trades: int
    win_rate_pct: float
    avg_win: float
    avg_loss: float
    risk_reward_ratio: float
    mathematical_expectancy: float
    execution_time_ms: float
    total_commission_paid: float = 0.0
    equity_curve: list = None
    trades: list = None
    trade_records: list = None


def get_symbol_multiplier(symbol: str) -> float:
    """Return USD value change per 1.0 price unit per 1.0 standard lot."""
    s = (symbol or "XAUUSD").upper().split(".")[0].replace("/", "")
    if "BTC" in s or "ETH" in s:
        return 1.0
    if "XAU" in s or "GOLD" in s or "XAG" in s:
        return 100.0
    if any(idx in s for idx in ["US30", "NAS100", "SPX500", "GER40", "DAX", "US100", "US500", "DJ30"]):
        return 10.0
    if "JPY" in s:
        return 667.0
    return 100000.0


class WyckoffMomentumStrategy(BaseStrategy):
    """
    Chiến lược Wyckoff Trend Momentum & Volume Expansion (Real-time Matrix Engine).
    Hội tụ 3 điều kiện định lượng:
    1. Cấu trúc xu hướng (Mark-up: EMA20 > EMA50 / Mark-down: EMA20 < EMA50)
    2. Kiểm định hồi quy động (Pullback / Retest kiểm định đường EMA20)
    3. Bùng nổ khối lượng hấp thụ (Volume >= 1.1x Volume MA20)
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.strategy_id = "builtin_wyckoff"
        self.name = "Wyckoff Momentum Pro"
        self.target_rr = float(self.config.get("target_rr", 2.5))
        self.atr_mult = float(self.config.get("atr_mult", 1.5))
        self.vol_mult = float(self.config.get("vol_mult", 1.1))

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "id": self.strategy_id,
            "name": "Wyckoff Momentum Pro",
            "description": "Vectorized NumPy ATR envelope and Volume expansion momentum model.",
            "author": "Quant AI Core",
            "version": "2.2",
            "checklist_schema": [
                {"key": "Trend Structure", "description": "Mark-up or Mark-down phase based on EMA20 vs EMA50"},
                {"key": "Pullback Retest", "description": "Dynamic retest or pullback to EMA20 support/resistance"},
                {"key": "Volume Expansion", "description": "Volume absorption and expansion relative to MA20"},
            ],
        }

    def get_default_checklist(self) -> List[ChecklistItem]:
        return [
            ChecklistItem(key="Trend Structure", value="Awaiting Clear Trend", status=ChecklistStatus.PENDING),
            ChecklistItem(key="Pullback Retest", value="Awaiting EMA Retest", status=ChecklistStatus.PENDING),
            ChecklistItem(key="Volume Expansion", value="Awaiting Volume Surge", status=ChecklistStatus.PENDING),
        ]

    def _calc_ema(self, arr: np.ndarray, period: int) -> np.ndarray:
        res = np.zeros(len(arr))
        alpha = 2.0 / (period + 1.0)
        res[period - 1] = np.mean(arr[:period])
        for i in range(period, len(arr)):
            res[i] = (arr[i] - res[i - 1]) * alpha + res[i - 1]
        return res

    def analyze(
        self, df: pd.DataFrame, macro_context: Dict[str, Any] = None
    ) -> StrategySignal:
        macro_context = macro_context or {}
        if df is None or len(df) < 55:
            default_chk = self.get_default_checklist()
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_name=self.name,
                action="HOLD",
                signal="HOLD",
                confidence=0.0,
                checklist=default_chk,
                metadata={
                    "strategy": "Wyckoff_Momentum_Pro",
                    "bias": 0,
                    "active_obs": 0,
                    "active_fvgs": 0,
                    "checklist": [c.value for c in default_chk],
                },
            )

        closes = df["close"].to_numpy(dtype=np.float64)
        highs = df["high"].to_numpy(dtype=np.float64)
        lows = df["low"].to_numpy(dtype=np.float64)
        volumes = (
            df["tick_volume"].to_numpy(dtype=np.float64)
            if "tick_volume" in df.columns
            else np.ones(len(closes)) * 1000.0
        )
        n = len(closes)

        # 1. Tính ATR(14)
        tr1 = highs[1:] - lows[1:]
        tr2 = np.abs(highs[1:] - closes[:-1])
        tr3 = np.abs(lows[1:] - closes[:-1])
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        atr = np.zeros(n)
        atr[14] = np.mean(tr[:14])
        for i in range(15, n):
            atr[i] = (atr[i - 1] * 13 + tr[i - 1]) / 14.0

        # 2. Vectorized EMAs & Volume Moving Average
        ema20 = self._calc_ema(closes, 20)
        ema50 = self._calc_ema(closes, 50)
        vol_ma = self._calc_ema(volumes, 20)

        # Đánh giá tại nến hiện tại (n - 1)
        curr_c = closes[-1]
        prev_c = closes[-2]
        curr_v = volumes[-1]
        curr_a = atr[-1] if atr[-1] > 0 else 1.0

        curr_ema20 = ema20[-1]
        prev_ema20 = ema20[-2]
        curr_ema50 = ema50[-1]
        curr_vol_ma = vol_ma[-1] if vol_ma[-1] > 0 else 1.0

        vol_ratio = curr_v / curr_vol_ma
        is_bull_trend = curr_ema20 > curr_ema50
        is_bear_trend = curr_ema20 < curr_ema50
        bias = 1 if is_bull_trend else (-1 if is_bear_trend else 0)

        # Tín hiệu vào lệnh chuẩn Wyckoff Trend Momentum
        buy_cond = (
            is_bull_trend
            and curr_c > curr_ema20
            and prev_c <= prev_ema20
            and curr_v >= self.vol_mult * curr_vol_ma
        )
        sell_cond = (
            is_bear_trend
            and curr_c < curr_ema20
            and prev_c >= prev_ema20
            and curr_v >= self.vol_mult * curr_vol_ma
        )

        sl_dist = self.atr_mult * curr_a
        action = "HOLD"
        entry_price = float(curr_c)
        sl = None
        tp1 = None
        tp2 = None
        confidence = 0.0

        volatility = macro_context.get("volatility_risk", "LOW")
        macro_bias = macro_context.get("bias", "NEUTRAL")
        news_lockout = macro_context.get("news_lockout", False) or macro_context.get("news_blackout", False)

        if news_lockout:
            event_name = macro_context.get("active_event") or macro_context.get("next_event_title") or "High-Impact Event"
            return {
                "signal": "HOLD",
                "action": "HOLD",
                "reason": f"NEWS_BLACKOUT_ACTIVE: {event_name}",
                "entry_price": 0.0,
                "sl": 0.0,
                "tp": 0.0,
                "confidence": 0.0,
                "checklist": [],
                "metadata": {"news_locked": True},
            }

        allow_counter_trend = macro_context.get("allow_counter_trend", True)

        if buy_cond and (macro_bias != "BEARISH" or allow_counter_trend):
            is_counter = (macro_bias == "BEARISH")
            action = "BUY"
            sl = entry_price - sl_dist
            rr = 1.5 if is_counter else self.target_rr
            tp1 = entry_price + sl_dist * rr
            tp2 = entry_price + sl_dist * (rr * 1.5)
            raw_conf = 0.88 if volatility != "HIGH" else 0.75
            confidence = raw_conf * (0.8 if is_counter else 1.0)
            chk1 = "Mark-up Phase (EMA20 > EMA50)" if not is_counter else "Counter-Trend Spring Reaction"
            chk2 = "EMA20 Pullback Confirmed"
            chk3 = f"Vol Expansion ({vol_ratio:.1f}x MA)"
        elif sell_cond and (macro_bias != "BULLISH" or allow_counter_trend):
            is_counter = (macro_bias == "BULLISH")
            action = "SELL"
            sl = entry_price + sl_dist
            rr = 1.5 if is_counter else self.target_rr
            tp1 = entry_price - sl_dist * rr
            tp2 = entry_price - sl_dist * (rr * 1.5)
            raw_conf = 0.88 if volatility != "HIGH" else 0.75
            confidence = raw_conf * (0.8 if is_counter else 1.0)
            chk1 = "Mark-down Phase (EMA20 < EMA50)" if not is_counter else "Counter-Trend Upthrust Reaction"
            chk2 = "EMA20 Retest Confirmed"
            chk3 = f"Vol Expansion ({vol_ratio:.1f}x MA)"
        else:
            # Standby Evaluation
            if is_bull_trend:
                chk1 = "Mark-up Phase (EMA20 > EMA50)"
                if curr_c <= curr_ema20:
                    chk2 = "Testing EMA20 Support"
                elif abs(curr_c - curr_ema20) <= 0.6 * curr_a:
                    chk2 = "Pullback Near EMA20"
                else:
                    chk2 = "Awaiting Pullback to EMA20"
            elif is_bear_trend:
                chk1 = "Mark-down Phase (EMA20 < EMA50)"
                if curr_c >= curr_ema20:
                    chk2 = "Testing EMA20 Resistance"
                elif abs(curr_c - curr_ema20) <= 0.6 * curr_a:
                    chk2 = "Retest Near EMA20"
                else:
                    chk2 = "Awaiting Retest to EMA20"
            else:
                chk1 = "Awaiting Trend Direction"
                chk2 = "Awaiting EMA Setup"

            if vol_ratio >= self.vol_mult:
                chk3 = f"Volume Expansion ({vol_ratio:.1f}x MA)"
            else:
                chk3 = f"Normal Volume ({vol_ratio:.1f}x MA)"

        # Construct dynamic self-describing checklist
        chk1_status = (
            ChecklistStatus.PASSED if action in ("BUY", "SELL")
            else (ChecklistStatus.PASSED if is_bull_trend or is_bear_trend else ChecklistStatus.PENDING)
        )
        chk2_status = ChecklistStatus.PASSED if action in ("BUY", "SELL") else ChecklistStatus.PENDING
        chk3_status = (
            ChecklistStatus.PASSED if (action in ("BUY", "SELL") or vol_ratio >= self.vol_mult)
            else ChecklistStatus.PENDING
        )

        checklist_items = [
            ChecklistItem(key="Trend Structure", value=chk1, status=chk1_status),
            ChecklistItem(key="Pullback Retest", value=chk2, status=chk2_status),
            ChecklistItem(key="Volume Expansion", value=chk3, status=chk3_status),
        ]

        return StrategySignal(
            strategy_id=self.strategy_id,
            strategy_name=self.name,
            action=action,
            signal=action,
            entry_price=entry_price if action != "HOLD" else None,
            sl=sl,
            tp1=tp1,
            tp2=tp2,
            confidence=confidence,
            score=85.0 if action != "HOLD" else 45.0,
            checklist=checklist_items,
            metadata={
                "strategy": "Wyckoff_Momentum_Pro",
                "trend": chk1,
                "pullback": chk2,
                "volume": chk3,
                "vol_ratio": float(round(vol_ratio, 2)),
                "bias": bias,
                "active_obs": 0,
                "active_fvgs": 0,
                "checklist": [c.value for c in checklist_items],
            },
        )


class VectorizedBacktester:
    """
    Động cơ Backtest Vectorized xử lý thuần ma trận NumPy.
    Tối ưu cho RAM 8GB: Tốc độ xử lý 10,000 nến trong < 0.1s.
    Hỗ trợ mô phỏng ma sát thị trường thực: Commission và Slippage.
    """

    def __init__(
        self,
        initial_balance: float = 100000.0,
        risk_per_trade_pct: float = 1.0,
        commission_per_trade: float = 0.0,
        slippage_pct: float = 0.0,
    ):
        self.initial_balance = initial_balance
        self.risk_per_trade_pct = risk_per_trade_pct
        self.commission_per_trade = commission_per_trade
        self.slippage_pct = slippage_pct
        self._strategy_engine = WyckoffMomentumStrategy()

    def analyze(self, df: pd.DataFrame, macro_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Backward-compatible proxy to WyckoffMomentumStrategy.analyze()."""
        return self._strategy_engine.analyze(df, macro_context)

    def _calc_ema(self, arr: np.ndarray, period: int) -> np.ndarray:
        res = np.zeros(len(arr))
        alpha = 2.0 / (period + 1.0)
        res[period - 1] = np.mean(arr[:period])
        for i in range(period, len(arr)):
            res[i] = (arr[i] - res[i - 1]) * alpha + res[i - 1]
        return res

    def run(
        self,
        df: pd.DataFrame,
        target_rr: float = 2.5,
        strategy_name: str = "wyckoff",
        symbol: str = "XAUUSD",
        fill_on_next_open: bool = False,
    ) -> BacktestReport:
        start_time = time.perf_counter()

        closes = df["close"].to_numpy(dtype=np.float64)
        highs = df["high"].to_numpy(dtype=np.float64)
        lows = df["low"].to_numpy(dtype=np.float64)
        opens = (
            df["open"].to_numpy(dtype=np.float64)
            if "open" in df.columns
            else closes
        )
        volumes = (
            df["tick_volume"].to_numpy(dtype=np.float64)
            if "tick_volume" in df.columns
            else np.ones(len(closes)) * 1000.0
        )
        n = len(closes)

        # 1. Tính ATR(14) Vectorized
        tr1 = highs[1:] - lows[1:]
        tr2 = np.abs(highs[1:] - closes[:-1])
        tr3 = np.abs(lows[1:] - closes[:-1])
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        atr = np.zeros(n)
        atr[14] = np.mean(tr[:14])
        for i in range(15, n):
            atr[i] = (atr[i - 1] * 13 + tr[i - 1]) / 14.0

        # 2. Vectorized EMAs & Volume Moving Average
        ema20 = self._calc_ema(closes, 20)
        ema50 = self._calc_ema(closes, 50)
        vol_ma = self._calc_ema(volumes, 20)

        # 3. Trích xuất mốc thời gian nến (Audit Timestamps for Order Execution)
        time_strs = None
        if "time" in df.columns:
            try:
                raw_time = df["time"]
                if not pd.api.types.is_datetime64_any_dtype(raw_time):
                    first_val = float(raw_time.iloc[0]) if len(raw_time) > 0 else 0
                    if first_val > 1e8:
                        dt_series = pd.to_datetime(raw_time, unit="s")
                    else:
                        dt_series = pd.to_datetime(raw_time)
                else:
                    dt_series = raw_time
                time_strs = dt_series.dt.strftime("%Y-%m-%d %H:%M").to_numpy()
            except Exception:
                time_strs = None
        elif isinstance(df.index, pd.DatetimeIndex):
            try:
                time_strs = df.index.strftime("%Y-%m-%d %H:%M").to_numpy()
            except Exception:
                time_strs = None

        if time_strs is None or len(time_strs) != n:
            time_strs = [f"Bar #{idx}" for idx in range(n)]

        # 4. Mô phỏng khớp lệnh Vectorized
        trades_pnl = []
        trade_records = []
        in_pos = False
        pos_type = 0  # 1: Buy, -1: Sell
        sl_price = 0.0
        tp_price = 0.0
        risk_amt = 0.0
        lot_size = 0.1
        total_comm = 0.0
        mult = get_symbol_multiplier(symbol)
        entry_time_str = ""

        balance = self.initial_balance
        equity_curve = [balance]

        for i in range(60, n):
            c, h, l, a, v = closes[i], highs[i], lows[i], atr[i], volumes[i]
            if a <= 0:
                continue

            if in_pos:
                friction = self.commission_per_trade + (
                    risk_amt * (self.slippage_pct / 100.0)
                )
                if pos_type == 1:
                    if l <= sl_price:
                        loss_pnl = -risk_amt - friction
                        trades_pnl.append(loss_pnl)
                        exit_time_str = time_strs[i] if i < len(time_strs) else ""
                        trade_records.append({
                            "trade_id": len(trade_records) + 1,
                            "side": "BUY",
                            "entry": entry_price,
                            "exit": sl_price,
                            "sl": sl_price,
                            "tp": tp_price,
                            "outcome": "SL",
                            "pnl": loss_pnl,
                            "volume": round(lot_size, 2),
                            "symbol": symbol,
                            "entry_time": entry_time_str,
                            "exit_time": exit_time_str,
                        })
                        balance += loss_pnl
                        total_comm += friction
                        in_pos = False
                    elif h >= tp_price:
                        win_pnl = (risk_amt * target_rr) - friction
                        trades_pnl.append(win_pnl)
                        exit_time_str = time_strs[i] if i < len(time_strs) else ""
                        trade_records.append({
                            "trade_id": len(trade_records) + 1,
                            "side": "BUY",
                            "entry": entry_price,
                            "exit": tp_price,
                            "sl": sl_price,
                            "tp": tp_price,
                            "outcome": "TP",
                            "pnl": win_pnl,
                            "volume": round(lot_size, 2),
                            "symbol": symbol,
                            "entry_time": entry_time_str,
                            "exit_time": exit_time_str,
                        })
                        balance += win_pnl
                        total_comm += friction
                        in_pos = False
                elif pos_type == -1:
                    if h >= sl_price:
                        loss_pnl = -risk_amt - friction
                        trades_pnl.append(loss_pnl)
                        exit_time_str = time_strs[i] if i < len(time_strs) else ""
                        trade_records.append({
                            "trade_id": len(trade_records) + 1,
                            "side": "SELL",
                            "entry": entry_price,
                            "exit": sl_price,
                            "sl": sl_price,
                            "tp": tp_price,
                            "outcome": "SL",
                            "pnl": loss_pnl,
                            "volume": round(lot_size, 2),
                            "symbol": symbol,
                            "entry_time": entry_time_str,
                            "exit_time": exit_time_str,
                        })
                        balance += loss_pnl
                        total_comm += friction
                        in_pos = False
                    elif l <= tp_price:
                        win_pnl = (risk_amt * target_rr) - friction
                        trades_pnl.append(win_pnl)
                        exit_time_str = time_strs[i] if i < len(time_strs) else ""
                        trade_records.append({
                            "trade_id": len(trade_records) + 1,
                            "side": "SELL",
                            "entry": entry_price,
                            "exit": tp_price,
                            "sl": sl_price,
                            "tp": tp_price,
                            "outcome": "TP",
                            "pnl": win_pnl,
                            "volume": round(lot_size, 2),
                            "symbol": symbol,
                            "entry_time": entry_time_str,
                            "exit_time": exit_time_str,
                        })
                        balance += win_pnl
                        total_comm += friction
                        in_pos = False

            if not in_pos and i < n - 5:
                risk_amt = balance * (self.risk_per_trade_pct / 100.0)
                sl_dist = 1.5 * a
                lot_size = max(0.01, min(round(risk_amt / (max(sl_dist, 0.0001) * mult), 2), 50.0))

                strat_lower = (strategy_name or "wyckoff").lower()
                if "ict" in strat_lower or "fvg" in strat_lower:
                    # ICT Zones Pro v4.2 (Fair Value Gap displacement + trend alignment)
                    is_bull_fvg = (lows[i] - highs[i - 2]) > (0.15 * a) and closes[i - 1] > closes[i - 2]
                    is_bear_fvg = (lows[i - 2] - highs[i]) > (0.15 * a) and closes[i - 1] < closes[i - 2]
                    buy_cond = is_bull_fvg and c > ema20[i] and ema20[i] >= ema50[i]
                    sell_cond = is_bear_fvg and c < ema20[i] and ema20[i] <= ema50[i]
                elif "ema" in strat_lower:
                    # EMA Dual Cross (Fast EMA20 crossing Slow EMA50)
                    buy_cond = ema20[i] > ema50[i] and closes[i - 1] <= ema20[i - 1] and c > ema20[i]
                    sell_cond = ema20[i] < ema50[i] and closes[i - 1] >= ema20[i - 1] and c < ema20[i]
                else:
                    # Wyckoff Trend Momentum + Volume Expansion (Default baseline)
                    buy_cond = (
                        ema20[i] > ema50[i]
                        and c > ema20[i]
                        and closes[i - 1] <= ema20[i - 1]
                        and v >= 1.1 * vol_ma[i]
                    )
                    sell_cond = (
                        ema20[i] < ema50[i]
                        and c < ema20[i]
                        and closes[i - 1] >= ema20[i - 1]
                        and v >= 1.1 * vol_ma[i]
                    )

                if buy_cond:
                    in_pos = True
                    pos_type = 1
                    entry_bar = i + 1 if fill_on_next_open and "open" in df.columns and i + 1 < n else i
                    entry_price = float(opens[i + 1]) if fill_on_next_open and "open" in df.columns and i + 1 < n else c
                    sl_price = entry_price - sl_dist
                    tp_price = entry_price + sl_dist * target_rr
                    entry_time_str = time_strs[entry_bar] if entry_bar < len(time_strs) else ""
                elif sell_cond:
                    in_pos = True
                    pos_type = -1
                    entry_bar = i + 1 if fill_on_next_open and "open" in df.columns and i + 1 < n else i
                    entry_price = float(opens[i + 1]) if fill_on_next_open and "open" in df.columns and i + 1 < n else c
                    sl_price = entry_price + sl_dist
                    tp_price = entry_price - sl_dist * target_rr
                    entry_time_str = time_strs[entry_bar] if entry_bar < len(time_strs) else ""

            equity_curve.append(balance)

        end_time = time.perf_counter()
        exec_ms = (end_time - start_time) * 1000.0

        # 4. Thống kê số liệu Định lượng & Chuẩn Quỹ Prop-Firm
        trades = np.array(trades_pnl)
        total_trades = len(trades)
        if total_trades == 0:
            return None

        wins = trades[trades > 0]
        losses = trades[trades < 0]
        win_count = len(wins)
        loss_count = len(losses)
        win_rate = (win_count / total_trades) * 100.0

        total_net = float(np.sum(trades))
        total_return = (total_net / self.initial_balance) * 100.0
        final_eq = self.initial_balance + total_net

        # Max Drawdown
        eq_arr = np.array(equity_curve)
        peak_arr = np.maximum.accumulate(eq_arr)
        dd_arr = peak_arr - eq_arr
        max_dd_dollars = float(np.max(dd_arr))
        dd_pct_arr = (dd_arr / peak_arr) * 100.0
        max_dd_pct = float(np.max(dd_pct_arr))

        # Sharpe & Sortino (Annualized 252)
        returns = trades / self.initial_balance
        mean_ret = np.mean(returns) if len(returns) > 0 else 0
        std_ret = np.std(returns) if len(returns) > 0 else 1
        sharpe = float((mean_ret / std_ret) * np.sqrt(252)) if std_ret > 0 else 0.0

        downside_diff = np.minimum(0.0, returns)
        downside_dev = float(np.sqrt(np.mean(downside_diff ** 2)))
        sortino = (
            float((mean_ret / downside_dev) * np.sqrt(252)) if downside_dev > 0 else 0.0
        )

        # Profit Factor
        gross_profit = float(np.sum(wins)) if len(wins) > 0 else 0.0
        gross_loss = float(abs(np.sum(losses))) if len(losses) > 0 else 1.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 999.0

        avg_w = float(np.mean(wins)) if len(wins) > 0 else 0.0
        avg_l = float(abs(np.mean(losses))) if len(losses) > 0 else 0.0
        rr_ratio = (avg_w / avg_l) if avg_l > 0 else target_rr

        # Kỳ vọng toán học (Expectancy)
        win_prob = win_count / total_trades
        loss_prob = loss_count / total_trades
        expectancy = (win_prob * avg_w) - (loss_prob * avg_l)

        return BacktestReport(
            sample_size=n,
            initial_balance=self.initial_balance,
            final_equity=final_eq,
            total_net_profit=total_net,
            total_return_pct=total_return,
            max_drawdown_dollars=max_dd_dollars,
            max_drawdown_pct=max_dd_pct,
            sharpe_ratio=round(sharpe, 2),
            sortino_ratio=round(sortino, 2),
            profit_factor=round(profit_factor, 2),
            total_trades=total_trades,
            win_trades=win_count,
            loss_trades=loss_count,
            win_rate_pct=round(win_rate, 2),
            avg_win=round(avg_w, 2),
            avg_loss=round(avg_l, 2),
            risk_reward_ratio=round(rr_ratio, 2),
            mathematical_expectancy=round(expectancy, 2),
            execution_time_ms=round(exec_ms, 2),
            total_commission_paid=round(total_comm, 2),
            equity_curve=equity_curve,
            trades=trades_pnl,
            trade_records=trade_records,
        )


if __name__ == "__main__":
    from infrastructure.brokers.mt5_safe import mt5

    print("Running Vectorized NumPy Backtest on XAUUSD H1 (5,000 bars)...")
    df = None
    if mt5.initialize():
        rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_H1, 0, 5000)
        if rates is not None and len(rates) >= 500:
            df = pd.DataFrame(rates)
            df["time"] = pd.to_datetime(df["time"], unit="s")

    if df is None:
        np.random.seed(42)
        dt = 1 / 252
        mu = 0.08
        sigma = 0.16
        prices = [2000.0]
        for _ in range(5000):
            ret = np.random.normal((mu - 0.5 * sigma**2) * dt, sigma * np.sqrt(dt))
            prices.append(prices[-1] * np.exp(ret))
        highs = [p * (1 + abs(np.random.normal(0, 0.003))) for p in prices]
        lows = [p * (1 - abs(np.random.normal(0, 0.003))) for p in prices]
        df = pd.DataFrame(
            {
                "close": prices,
                "high": highs,
                "low": lows,
                "tick_volume": np.ones(len(prices)) * 1200,
            }
        )

    bt = VectorizedBacktester(
        initial_balance=100000.0,
        risk_per_trade_pct=1.0,
        commission_per_trade=7.0,
        slippage_pct=0.0002,
    )
    rep = bt.run(df, target_rr=2.5)

    print("\n" + "=" * 65)
    print("   VECTORIZED NUMPY BACKTEST REPORT (UNBIASED H1)")
    print("=" * 65)
    print(f" Sample Size (H1 Bars)       : {rep.sample_size:,} bars (~1 year)")
    print(f" Initial Balance             : {rep.initial_balance:,.2f} USD")
    print(f" Final Equity                : {rep.final_equity:,.2f} USD")
    print(
        f" Total Net Profit            : +{rep.total_net_profit:,.2f} USD (+{rep.total_return_pct:.2f}%)"
    )
    print(
        f" Win Rate                    : {rep.win_rate_pct:.2f}% ({rep.win_trades} Wins / {rep.loss_trades} Losses)"
    )
    print(
        f" Max Drawdown                : {rep.max_drawdown_pct:.2f}% ({rep.max_drawdown_dollars:,.2f} USD)"
    )
    print(f" Sharpe Ratio                : {rep.sharpe_ratio:.2f}")
    print(f" Profit Factor               : {rep.profit_factor:.2f}")
    print(
        f" Average Win / Loss          : {rep.avg_win:,.2f} USD / {rep.avg_loss:,.2f} USD (R:R {rep.risk_reward_ratio:.2f})"
    )
    print(
        f" Mathematical Expectancy     : +{rep.mathematical_expectancy:,.2f} USD / trade"
    )
    print(f" Total Commission Paid       : {rep.total_commission_paid:,.2f} USD")
    print(f" Execution Time (Pure Matrix): {rep.execution_time_ms:.2f} ms")
    print("=" * 65)


__all__ = [
    "VectorizedBacktester",
    "WyckoffMomentumStrategy",
    "BacktestReport",
    "get_symbol_multiplier",
]
