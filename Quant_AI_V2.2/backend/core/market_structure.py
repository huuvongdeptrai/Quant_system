"""
Market Structure & Trend Engine (System-Level Microstructure Core).

Provides institutional quantitative determination of market trend and structure:
- 5-bar / Adaptive Fractal Swing Highs and Swing Lows
- Price Action Geometry: Higher Highs/Lows (Uptrend), Lower Highs/Lows (Downtrend),
  Contraction (Triangle/Squeeze), Expansion (Broadening/Megaphone)
- Break of Structure (BOS) & Market Structure Shift (MSS) Detection
- Adaptive EMA Anchor with Dynamic Volatility Envelope
- Deterministic, Pure Mathematical Pipeline Independent of Trading Strategies
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple, Union
import numpy as np
import pandas as pd


@dataclass
class SwingPoint:
    """Represents a validated structural pivot point in price action."""
    index: int
    price: float
    is_high: bool
    time: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "price": self.price,
            "is_high": self.is_high,
            "time": self.time,
        }


@dataclass
class MarketStructureResult:
    """Standardized output of the System Market Structure & Trend Engine."""
    trend: str  # "BULLISH", "BEARISH", "SIDEWAYS"
    structure_label: str  # e.g. "Bullish (Higher Highs, Higher Lows)"
    phase: str  # "TRENDING_BULL", "TRENDING_BEAR", "CONTRACTION", "EXPANSION", "SIDEWAYS"
    current_price: float
    ema_anchor: float
    ema_position: str  # "ABOVE_EMA", "BELOW_EMA", "AT_EMA"
    distance_to_ema_pct: float
    swing_highs: List[float] = field(default_factory=list)
    swing_lows: List[float] = field(default_factory=list)
    last_swing_high: Optional[float] = None
    last_swing_low: Optional[float] = None
    bos_detected: bool = False
    bos_direction: Optional[str] = None  # "BULLISH_BOS", "BEARISH_BOS", None
    bos_level: Optional[float] = None
    confidence: float = 0.85
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trend": self.trend,
            "math_trend": self.trend.capitalize(),
            "structure": self.structure_label,
            "structure_label": self.structure_label,
            "phase": self.phase,
            "current_price": self.current_price,
            "ema_anchor": self.ema_anchor,
            "ema_50": self.ema_anchor,
            "ema_position": self.ema_position,
            "distance_to_ema_pct": self.distance_to_ema_pct,
            "swing_highs": self.swing_highs,
            "swing_lows": self.swing_lows,
            "last_swing_high": self.last_swing_high,
            "last_swing_low": self.last_swing_low,
            "bos_detected": self.bos_detected,
            "bos_direction": self.bos_direction,
            "bos_level": self.bos_level,
            "confidence": self.confidence,
            "details": self.details,
        }

    def __getitem__(self, item: str):
        return self.to_dict()[item]

    def get(self, item: str, default=None):
        return self.to_dict().get(item, default)

    def __contains__(self, key: str) -> bool:
        return key in self.to_dict()


class MarketStructureEngine:
    """
    Centralized quantitative market structure and trend detection engine.
    Used by DataPreprocessor, AnalysisEngine, and DecisionGate as the single source
    of truth for system-level price action geometry.
    """

    @staticmethod
    def _extract_arrays(data: Union[pd.DataFrame, np.ndarray, List[Dict[str, Any]]]) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Optional[np.ndarray]]:
        """Extracts (open, high, low, close, time) as 1D float64 numpy arrays."""
        if isinstance(data, pd.DataFrame):
            df = data.copy()
            # Normalize column names to lowercase
            col_map = {c: str(c).lower() for c in df.columns}
            df.rename(columns=col_map, inplace=True)
            highs = df["high"].to_numpy(dtype=float)
            lows = df["low"].to_numpy(dtype=float)
            closes = df["close"].to_numpy(dtype=float)
            opens = df["open"].to_numpy(dtype=float) if "open" in df.columns else closes.copy()
            times = df["time"].to_numpy() if "time" in df.columns else None
            return opens, highs, lows, closes, times

        if isinstance(data, np.ndarray):
            names = data.dtype.names
            if names:
                low_names = [n.lower() for n in names]
                def get_col(col_name):
                    for orig, l in zip(names, low_names):
                        if l == col_name:
                            return np.array(data[orig], dtype=float)
                    return None

                highs = get_col("high")
                lows = get_col("low")
                closes = get_col("close")
                opens = get_col("open")
                if opens is None and closes is not None:
                    opens = closes.copy()
                times = data["time"] if "time" in names else None
                if highs is not None and lows is not None and closes is not None:
                    return opens, highs, lows, closes, times

        if isinstance(data, (list, tuple)) and len(data) > 0 and isinstance(data[0], dict):
            highs = np.array([float(r.get("high", r.get("close", 0))) for r in data], dtype=float)
            lows = np.array([float(r.get("low", r.get("close", 0))) for r in data], dtype=float)
            closes = np.array([float(r.get("close", 0)) for r in data], dtype=float)
            opens = np.array([float(r.get("open", r.get("close", 0))) for r in data], dtype=float)
            times = np.array([r.get("time") for r in data]) if "time" in data[0] else None
            return opens, highs, lows, closes, times

        # Fallback empty
        return np.array([]), np.array([]), np.array([]), np.array([]), None

    @classmethod
    def detect_swings(
        cls,
        data: Union[pd.DataFrame, np.ndarray, List[Dict[str, Any]]],
        order: int = 2,
    ) -> Tuple[List[SwingPoint], List[SwingPoint]]:
        """
        Identifies structural swing highs and swing lows using an order-k window.
        A swing high at index i satisfies: high[i] > high[i ± 1..k].
        Adapts order dynamically if bar count is low.
        """
        _, highs, lows, _, times = cls._extract_arrays(data)
        n = len(highs)
        if n < 5:
            return [], []

        effective_order = order
        if n < 15 and effective_order > 1:
            effective_order = 1

        swing_highs: List[SwingPoint] = []
        swing_lows: List[SwingPoint] = []

        for i in range(effective_order, n - effective_order):
            h_curr = highs[i]
            l_curr = lows[i]

            is_sh = True
            is_sl = True
            for offset in range(1, effective_order + 1):
                if highs[i - offset] >= h_curr or highs[i + offset] >= h_curr:
                    is_sh = False
                if lows[i - offset] <= l_curr or lows[i + offset] <= l_curr:
                    is_sl = False

            t_val = times[i] if times is not None and i < len(times) else None

            if is_sh:
                swing_highs.append(SwingPoint(index=i, price=float(h_curr), is_high=True, time=t_val))
            if is_sl:
                swing_lows.append(SwingPoint(index=i, price=float(l_curr), is_high=False, time=t_val))

        return swing_highs, swing_lows

    @classmethod
    def analyze_market_structure(
        cls,
        data: Union[pd.DataFrame, np.ndarray, List[Dict[str, Any]]],
        current_price: Optional[float] = None,
        ema_period: int = 50,
        order: int = 2,
    ) -> MarketStructureResult:
        """
        Comprehensive market structure evaluation combining price geometry, fractal pivots,
        and dynamic volatility-anchored moving average.
        """
        opens, highs, lows, closes, _ = cls._extract_arrays(data)
        n = len(closes)

        if n == 0:
            p = float(current_price or 0.0)
            return MarketStructureResult(
                trend="SIDEWAYS",
                structure_label="Insufficient Data",
                phase="SIDEWAYS",
                current_price=p,
                ema_anchor=p,
                ema_position="AT_EMA",
                distance_to_ema_pct=0.0,
                confidence=0.5,
            )

        curr_p = float(current_price if current_price is not None and current_price > 0 else closes[-1])

        # 1. Adaptive EMA Anchor
        eff_period = min(ema_period, max(5, n // 2))
        alpha = 2.0 / (eff_period + 1.0)
        ema = float(np.mean(closes[:eff_period]))
        for price in closes[eff_period:]:
            ema = (price - ema) * alpha + ema

        # Dynamic ATR buffer (0.3 ATR or 0.15% of price if ATR not available)
        if n >= 14:
            trs = [
                max(
                    highs[k] - lows[k],
                    abs(highs[k] - closes[k - 1]),
                    abs(lows[k] - closes[k - 1]),
                )
                for k in range(1, n)
            ]
            atr = float(np.mean(trs[-14:])) if len(trs) >= 14 else (curr_p * 0.002)
        else:
            atr = float(np.mean(highs - lows)) if len(highs) > 0 else (curr_p * 0.002)

        buffer_pts = max(atr * 0.35, curr_p * 0.001)

        # Distance to EMA
        dist_ema = curr_p - ema
        dist_ema_pct = (dist_ema / ema * 100.0) if ema > 0 else 0.0

        if curr_p > (ema + buffer_pts):
            ema_pos = "ABOVE_EMA"
        elif curr_p < (ema - buffer_pts):
            ema_pos = "BELOW_EMA"
        else:
            ema_pos = "AT_EMA"

        # 2. Structural Fractal Swings
        sh_points, sl_points = cls.detect_swings(data, order=order)
        raw_sh = [p.price for p in sh_points]
        raw_sl = [p.price for p in sl_points]

        last_shs = raw_sh[-3:] if len(raw_sh) >= 3 else raw_sh
        last_sls = raw_sl[-3:] if len(raw_sl) >= 3 else raw_sl

        last_sh = raw_sh[-1] if len(raw_sh) > 0 else None
        last_sl = raw_sl[-1] if len(raw_sl) > 0 else None

        # 3. Break of Structure (BOS) / Market Structure Shift (MSS)
        bos_detected = False
        bos_direction = None
        bos_level = None

        if last_sh is not None and curr_p > last_sh:
            bos_detected = True
            bos_direction = "BULLISH_BOS"
            bos_level = last_sh
        elif last_sl is not None and curr_p < last_sl:
            bos_detected = True
            bos_direction = "BEARISH_BOS"
            bos_level = last_sl

        # 4. Geometry Evaluation (Higher Highs / Higher Lows / Contraction / Expansion)
        structure_label = "Sideways (Consolidation Range)"
        phase = "SIDEWAYS"
        trend = "SIDEWAYS"
        conf = 0.70

        if len(last_shs) >= 2 and len(last_sls) >= 2:
            sh_prev, sh_curr = last_shs[-2], last_shs[-1]
            sl_prev, sl_curr = last_sls[-2], last_sls[-1]

            # Bullish Market Structure: Higher Highs + Higher Lows
            if sh_curr > sh_prev and sl_curr > sl_prev:
                structure_label = "Bullish (Higher Highs, Higher Lows)"
                phase = "TRENDING_BULL"
                trend = "BULLISH"
                conf = 0.88 if ema_pos in ("ABOVE_EMA", "AT_EMA") else 0.75

            # Bearish Market Structure: Lower Highs + Lower Lows
            elif sh_curr < sh_prev and sl_curr < sl_prev:
                structure_label = "Bearish (Lower Highs, Lower Lows)"
                phase = "TRENDING_BEAR"
                trend = "BEARISH"
                conf = 0.88 if ema_pos in ("BELOW_EMA", "AT_EMA") else 0.75

            # Contraction / Squeeze: Lower Highs + Higher Lows
            elif sh_curr < sh_prev and sl_curr > sl_prev:
                structure_label = "Contraction (Convergence / Triangle)"
                phase = "CONTRACTION"
                trend = "SIDEWAYS"
                conf = 0.72

            # Expansion / Broadening: Higher Highs + Lower Lows
            elif sh_curr > sh_prev and sl_curr < sl_prev:
                structure_label = "Expansion (Megaphone / Broadening)"
                phase = "EXPANSION"
                # If expanding, follow EMA slope and break
                if ema_pos == "ABOVE_EMA" or bos_direction == "BULLISH_BOS":
                    trend = "BULLISH"
                elif ema_pos == "BELOW_EMA" or bos_direction == "BEARISH_BOS":
                    trend = "BEARISH"
                else:
                    trend = "SIDEWAYS"
                conf = 0.68

            # Mixed Swing Transitions
            else:
                if ema_pos == "ABOVE_EMA" and (sl_curr > sl_prev or bos_direction == "BULLISH_BOS"):
                    structure_label = "Bullish Pullback (Above EMA Anchor)"
                    phase = "TRENDING_BULL"
                    trend = "BULLISH"
                    conf = 0.80
                elif ema_pos == "BELOW_EMA" and (sh_curr < sh_prev or bos_direction == "BEARISH_BOS"):
                    structure_label = "Bearish Retest (Below EMA Anchor)"
                    phase = "TRENDING_BEAR"
                    trend = "BEARISH"
                    conf = 0.80
                else:
                    structure_label = "Equilibrium (Chop / Sideways)"
                    phase = "SIDEWAYS"
                    trend = "SIDEWAYS"
                    conf = 0.65

        # Fallback when swing count is minimal (e.g. short timeframe or fresh symbol)
        elif len(last_shs) >= 1 and len(last_sls) >= 1:
            if bos_direction == "BULLISH_BOS" or (ema_pos == "ABOVE_EMA" and curr_p > last_sls[-1]):
                structure_label = "Bullish Bias (Above EMA Anchor)"
                phase = "TRENDING_BULL"
                trend = "BULLISH"
                conf = 0.78
            elif bos_direction == "BEARISH_BOS" or (ema_pos == "BELOW_EMA" and curr_p < last_shs[-1]):
                structure_label = "Bearish Bias (Below EMA Anchor)"
                phase = "TRENDING_BEAR"
                trend = "BEARISH"
                conf = 0.78
            else:
                structure_label = "Consolidation Range"
                phase = "SIDEWAYS"
                trend = "SIDEWAYS"
                conf = 0.65
        else:
            # Pure EMA + Price Position fallback
            if ema_pos == "ABOVE_EMA":
                structure_label = "Bullish Momentum (Above EMA)"
                phase = "TRENDING_BULL"
                trend = "BULLISH"
                conf = 0.75
            elif ema_pos == "BELOW_EMA":
                structure_label = "Bearish Momentum (Below EMA)"
                phase = "TRENDING_BEAR"
                trend = "BEARISH"
                conf = 0.75
            else:
                structure_label = "Consolidation (At EMA Anchor)"
                phase = "SIDEWAYS"
                trend = "SIDEWAYS"
                conf = 0.60

        # Refine BOS label if break is recent and dominant
        if bos_detected:
            if bos_direction == "BULLISH_BOS" and trend != "BEARISH":
                structure_label = f"Bullish BOS (Broke {last_sh:.2f})"
                trend = "BULLISH"
                conf = min(0.95, conf + 0.08)
            elif bos_direction == "BEARISH_BOS" and trend != "BULLISH":
                structure_label = f"Bearish BOS (Broke {last_sl:.2f})"
                trend = "BEARISH"
                conf = min(0.95, conf + 0.08)

        details = {
            "atr": round(atr, 4),
            "buffer_pts": round(buffer_pts, 4),
            "num_bars": n,
            "num_swing_highs": len(raw_sh),
            "num_swing_lows": len(raw_sl),
        }

        return MarketStructureResult(
            trend=trend,
            structure_label=structure_label,
            phase=phase,
            current_price=round(curr_p, 4),
            ema_anchor=round(ema, 4),
            ema_position=ema_pos,
            distance_to_ema_pct=round(dist_ema_pct, 2),
            swing_highs=raw_sh,
            swing_lows=raw_sl,
            last_swing_high=last_sh,
            last_swing_low=last_sl,
            bos_detected=bos_detected,
            bos_direction=bos_direction,
            bos_level=bos_level,
            confidence=round(conf, 2),
            details=details,
        )
