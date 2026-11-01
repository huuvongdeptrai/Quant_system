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
    Hội tụ 4 điều kiện định lượng chuẩn mực:
    1. Cấu trúc xu hướng & Chế độ thị trường (Mark-up: EMA20 > EMA50 / Mark-down: EMA20 < EMA50 + ADX >= 20.0 xác nhận sóng mạnh, triệt tiêu sideway)
    2. Kiểm định hồi quy động & Biên độ cản (Pullback kiểm định EMA20 + Headroom tới cản gần nhất >= 1.0x ATR)
    3. Bùng nổ khối lượng & Nỗ lực so với Kết quả (Volume >= 1.25x Volume MA20 + Xác nhận nến không bị từ chối râu dài)
    4. Quản trị rủi ro cấu trúc động (Stop Loss = 1.5x ATR, Target TP = 2.5x Risk)
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.strategy_id = "builtin_wyckoff"
        self.name = "Wyckoff Momentum Pro"
        self.target_rr = float(self.config.get("target_rr", 2.5))
        self.atr_mult = float(self.config.get("atr_mult", 1.5))
        self.vol_mult = float(self.config.get("vol_mult", 1.25))
        self.adx_period = int(self.config.get("adx_period", 14))
        self.adx_threshold = float(self.config.get("adx_threshold", 20.0))
        self.sr_lookback = int(self.config.get("sr_lookback", 30))
        self.min_headroom_atr = float(self.config.get("min_headroom_atr", 1.0))
        self.wick_rejection_max = float(self.config.get("wick_rejection_max", 0.50))
        self.session_filter = bool(self.config.get("session_filter", True))

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "id": self.strategy_id,
            "name": "Wyckoff Momentum Pro",
            "description": "Vectorized NumPy ATR envelope, ADX trend filter, and Volume expansion momentum model.",
            "author": "Quant AI Core",
            "version": "2.2",
            "checklist_schema": [
                {"key": "Trend Structure", "description": "Mark-up/Mark-down phase based on EMA20 vs EMA50 and ADX strength"},
                {"key": "Pullback Retest", "description": "Dynamic retest of EMA20 support/resistance with structural headroom"},
                {"key": "Volume Expansion", "description": "Volume absorption and Effort vs Result relative to MA20"},
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

    def _calc_adx(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
        """
        Calculates J. Welles Wilder Average Directional Index (ADX) vectorized in NumPy.
        Identifies trend regime vs sideways/choppy market.
        """
        n = len(closes)
        if n < period + 2:
            return np.full(n, 25.0)

        tr1 = highs[1:] - lows[1:]
        tr2 = np.abs(highs[1:] - closes[:-1])
        tr3 = np.abs(lows[1:] - closes[:-1])
        tr = np.maximum(tr1, np.maximum(tr2, tr3))

        up_move = highs[1:] - highs[:-1]
        down_move = lows[:-1] - lows[1:]
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        tr_smooth = np.zeros(n)
        p_dm_smooth = np.zeros(n)
        m_dm_smooth = np.zeros(n)

        tr_smooth[period] = np.sum(tr[:period])
        p_dm_smooth[period] = np.sum(plus_dm[:period])
        m_dm_smooth[period] = np.sum(minus_dm[:period])

        for i in range(period + 1, n):
            tr_smooth[i] = tr_smooth[i - 1] - (tr_smooth[i - 1] / period) + tr[i - 1]
            p_dm_smooth[i] = p_dm_smooth[i - 1] - (p_dm_smooth[i - 1] / period) + plus_dm[i - 1]
            m_dm_smooth[i] = m_dm_smooth[i - 1] - (m_dm_smooth[i - 1] / period) + minus_dm[i - 1]

        with np.errstate(divide="ignore", invalid="ignore"):
            plus_di = np.where(tr_smooth > 0, 100.0 * (p_dm_smooth / tr_smooth), 0.0)
            minus_di = np.where(tr_smooth > 0, 100.0 * (m_dm_smooth / tr_smooth), 0.0)
            di_sum = plus_di + minus_di
            dx = np.where(di_sum > 0, 100.0 * np.abs(plus_di - minus_di) / di_sum, 0.0)

        adx = np.zeros(n)
        adx_start = 2 * period
        if n > adx_start:
            adx[adx_start] = np.mean(dx[period : adx_start + 1])
            for i in range(adx_start + 1, n):
                adx[i] = (adx[i - 1] * (period - 1) + dx[i]) / period
        else:
            adx[:] = dx

        return adx

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

        # 2. Vectorized EMAs, Volume Moving Average & ADX
        ema20 = self._calc_ema(closes, 20)
        ema50 = self._calc_ema(closes, 50)
        vol_ma = self._calc_ema(volumes, 20)
        adx_series = self._calc_adx(highs, lows, closes, period=self.adx_period)

        # Đánh giá tại nến hiện tại (n - 1)
        curr_c = closes[-1]
        prev_c = closes[-2]
        curr_v = volumes[-1]
        curr_a = atr[-1] if atr[-1] > 0 else 1.0
        curr_adx = float(adx_series[-1]) if not np.isnan(adx_series[-1]) else 25.0

        curr_ema20 = ema20[-1]
        prev_ema20 = ema20[-2]
        curr_ema50 = ema50[-1]
        curr_vol_ma = vol_ma[-1] if vol_ma[-1] > 0 else 1.0

        vol_ratio = curr_v / curr_vol_ma
        is_bull_trend = curr_ema20 > curr_ema50
        is_bear_trend = curr_ema20 < curr_ema50
        is_trend_strong = curr_adx >= self.adx_threshold
        bias = 1 if is_bull_trend else (-1 if is_bear_trend else 0)

        # 3. Phân tích Biên độ Cản (S/R Headroom Clearance)
        lookback_sr = min(self.sr_lookback, n - 2)
        if lookback_sr >= 10:
            recent_high = float(np.max(highs[-lookback_sr - 1 : -1]))
            recent_low = float(np.min(lows[-lookback_sr - 1 : -1]))
        else:
            recent_high = float("inf")
            recent_low = -float("inf")

        min_headroom = self.min_headroom_atr * curr_a
        has_headroom_buy = (recent_high - curr_c >= min_headroom) or (curr_c >= recent_high)
        has_headroom_sell = (curr_c - recent_low >= min_headroom) or (curr_c <= recent_low)

        # 4. Nỗ lực so với Kết quả (Wyckoff Effort vs Result - Candle Spread & Wick Analysis)
        curr_o = float(df["open"].iloc[-1]) if "open" in df.columns else curr_c
        curr_h = float(highs[-1])
        curr_l = float(lows[-1])
        candle_range = curr_h - curr_l
        if candle_range > 0:
            upper_wick = curr_h - max(curr_c, curr_o)
            lower_wick = min(curr_c, curr_o) - curr_l
            valid_effort_buy = (upper_wick / candle_range) <= self.wick_rejection_max
            valid_effort_sell = (lower_wick / candle_range) <= self.wick_rejection_max
        else:
            valid_effort_buy = True
            valid_effort_sell = True

        # Tín hiệu vào lệnh chuẩn Wyckoff Trend Momentum nâng cấp
        base_buy_pullback = (
            is_bull_trend
            and curr_c > curr_ema20
            and prev_c <= prev_ema20
            and curr_v >= self.vol_mult * curr_vol_ma
        )
        base_sell_pullback = (
            is_bear_trend
            and curr_c < curr_ema20
            and prev_c >= prev_ema20
            and curr_v >= self.vol_mult * curr_vol_ma
        )

        buy_cond = base_buy_pullback and is_trend_strong and valid_effort_buy and has_headroom_buy
        sell_cond = base_sell_pullback and is_trend_strong and valid_effort_sell and has_headroom_sell

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

        # Phien thanh khoan to chuc (London & New York: 07:00 - 17:00 UTC)
        if self.session_filter and "time" in df.columns:
            try:
                time_val = df["time"].iloc[-1]
                utc_hour = getattr(time_val, "hour", None)
                if utc_hour is None:
                    utc_hour = pd.to_datetime(time_val).hour
                if utc_hour is not None and not (7 <= utc_hour <= 17):
                    default_chk = self.get_default_checklist()
                    default_chk[0] = ChecklistItem(
                        key="Trend Structure",
                        value="Asian Off-Hours (Standby for London 07:00 UTC)",
                        status=ChecklistStatus.NEUTRAL
                    )
                    return StrategySignal(
                        strategy_id=self.strategy_id,
                        strategy_name=self.name,
                        action="HOLD",
                        signal="HOLD",
                        confidence=0.0,
                        checklist=default_chk,
                        metadata={
                            "strategy": "Wyckoff_Momentum_Pro",
                            "session": "ASIAN_OFF_HOURS",
                            "bias": 0,
                            "active_obs": 0,
                            "active_fvgs": 0,
                            "checklist": [c.value for c in default_chk],
                        },
                    )
            except Exception:
                pass

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
            chk1 = f"Mark-up Phase (ADX {curr_adx:.1f} · Strong Trend)" if not is_counter else "Counter-Trend Spring Reaction"
            chk2 = "EMA20 Support Retested · Headroom Clear"
            chk3 = f"Vol Expansion ({vol_ratio:.1f}x MA · Effort Validated)"
        elif sell_cond and (macro_bias != "BULLISH" or allow_counter_trend):
            is_counter = (macro_bias == "BULLISH")
            action = "SELL"
            sl = entry_price + sl_dist
            rr = 1.5 if is_counter else self.target_rr
            tp1 = entry_price - sl_dist * rr
            tp2 = entry_price - sl_dist * (rr * 1.5)
            raw_conf = 0.88 if volatility != "HIGH" else 0.75
            confidence = raw_conf * (0.8 if is_counter else 1.0)
            chk1 = f"Mark-down Phase (ADX {curr_adx:.1f} · Strong Trend)" if not is_counter else "Counter-Trend Upthrust Reaction"
            chk2 = "EMA20 Resistance Retested · Headroom Clear"
            chk3 = f"Vol Expansion ({vol_ratio:.1f}x MA · Effort Validated)"
        else:
            # Standby Evaluation
            if is_bull_trend:
                if is_trend_strong:
                    chk1 = f"Mark-up Phase (ADX {curr_adx:.1f} · Strong Trend)"
                else:
                    chk1 = f"Choppy Range (ADX {curr_adx:.1f} < {self.adx_threshold:.0f})"

                if not has_headroom_buy and base_buy_pullback:
                    chk2 = f"Near Resistance · Headroom Choked (<{self.min_headroom_atr:.1f} ATR)"
                elif curr_c <= curr_ema20:
                    chk2 = "Testing EMA20 Support"
                elif abs(curr_c - curr_ema20) <= 0.6 * curr_a:
                    chk2 = "Pullback Near EMA20"
                else:
                    chk2 = "Awaiting Pullback to EMA20"
            elif is_bear_trend:
                if is_trend_strong:
                    chk1 = f"Mark-down Phase (ADX {curr_adx:.1f} · Strong Trend)"
                else:
                    chk1 = f"Choppy Range (ADX {curr_adx:.1f} < {self.adx_threshold:.0f})"

                if not has_headroom_sell and base_sell_pullback:
                    chk2 = f"Near Support · Headroom Choked (<{self.min_headroom_atr:.1f} ATR)"
                elif curr_c >= curr_ema20:
                    chk2 = "Testing EMA20 Resistance"
                elif abs(curr_c - curr_ema20) <= 0.6 * curr_a:
                    chk2 = "Retest Near EMA20"
                else:
                    chk2 = "Awaiting Retest to EMA20"
            else:
                chk1 = "Awaiting Trend Direction"
                chk2 = "Awaiting EMA Setup"

            if vol_ratio >= self.vol_mult:
                if (is_bull_trend and not valid_effort_buy) or (is_bear_trend and not valid_effort_sell):
                    chk3 = f"Effort Rejected · High Absorption Wick ({vol_ratio:.1f}x MA)"
                else:
                    chk3 = f"Volume Expansion ({vol_ratio:.1f}x MA)"
            else:
                chk3 = f"Normal Volume ({vol_ratio:.1f}x MA)"

        # Construct dynamic self-describing checklist
        chk1_status = (
            ChecklistStatus.PASSED if action in ("BUY", "SELL")
            else (ChecklistStatus.PASSED if (is_trend_strong and (is_bull_trend or is_bear_trend)) else ChecklistStatus.PENDING)
        )
        chk2_status = (
            ChecklistStatus.PASSED if action in ("BUY", "SELL")
            else (ChecklistStatus.FAILED if ((is_bull_trend and not has_headroom_buy and base_buy_pullback) or (is_bear_trend and not has_headroom_sell and base_sell_pullback)) else ChecklistStatus.PENDING)
        )
        chk3_status = (
            ChecklistStatus.PASSED if action in ("BUY", "SELL")
            else (ChecklistStatus.FAILED if (vol_ratio >= self.vol_mult and ((is_bull_trend and not valid_effort_buy) or (is_bear_trend and not valid_effort_sell))) else (ChecklistStatus.PASSED if vol_ratio >= self.vol_mult else ChecklistStatus.PENDING))
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
                "adx": float(round(curr_adx, 1)),
                "is_trend_strong": bool(is_trend_strong),
                "has_headroom": bool(has_headroom_buy if is_bull_trend else has_headroom_sell),
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

    def run(self, df, target_rr=2.5, strategy_name="wyckoff", symbol="XAUUSD", fill_on_next_open=True):
        from backend.backtest.backtest_vectorized import VectorizedBacktester as Engine
        return Engine(self.initial_balance,self.risk_per_trade_pct,self.commission_per_trade,self.slippage_pct).run(
            df,target_rr,strategy_name,symbol,fill_on_next_open)


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
