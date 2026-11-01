from typing import Dict, Any, Optional, Tuple, List
import pandas as pd
import numpy as np
import pytz
from datetime import datetime
from backend.core.market_structure import MarketStructureEngine, MarketStructureResult, SwingPoint


class DataPreprocessor:
    """
    Institutional Data Preprocessor & Quantitative Microstructure Engine.
    Converts raw tick/bar feeds into standardized statistical & order-flow feature vectors:
    - Timezone normalization (Broker local -> International UTC)
    - Garman-Klass Realized Volatility estimator (8x efficiency vs close-to-close)
    - Session VWAP & Standard Deviation Bands (±1σ, ±2σ Fair Value)
    - Volume Profile Point of Control (POC) & Value Area (VAH / VAL 70%)
    - Microstructure Order Flow Imbalance (Cumulative Volume Delta - CVD Proxy)
    - Dynamic Z-Score of Price vs EMA50 normalized by ATR(14)
    - Major Structural Support/Resistance (Wyckoff Volume-Validated)
    """

    def __init__(self):
        pass

    def detect_market_structure(
        self,
        rates_data: Any,
        current_price: Optional[float] = None,
        ema_period: int = 50,
        order: int = 2,
    ) -> MarketStructureResult:
        """
        Public system-level market structure and trend detector.
        Provides deterministic fractal swings, Higher Highs/Lows, BOS/MSS, and trend classification.
        """
        return MarketStructureEngine.analyze_market_structure(
            rates_data,
            current_price=current_price,
            ema_period=ema_period,
            order=order,
        )

    def detect_fractal_swings(
        self,
        rates_data: Any,
        order: int = 2,
    ) -> Tuple[List[SwingPoint], List[SwingPoint]]:
        """
        Trích xuất các điểm đảo chiều Fractal Swings (mặc định 5 nến: order=2).
        Trả về cặp danh sách: (swing_highs, swing_lows).
        """
        return MarketStructureEngine.detect_swings(rates_data, order=order)


    def _calculate_garman_klass_vol(self, df: pd.DataFrame, window: int = 14) -> float:
        """
        Garman-Klass Realized Volatility estimator:
        Uses Open, High, Low, and Close to extract true intraday variance without noise.
        """
        if len(df) < window:
            return 0.0
        log_hl = (np.log(df["high"] / np.where(df["low"] <= 0, 1e-6, df["low"]))) ** 2
        log_co = (np.log(df["close"] / np.where(df["open"] <= 0, 1e-6, df["open"]))) ** 2
        gk_term = 0.5 * log_hl - (2.0 * np.log(2.0) - 1.0) * log_co
        rolling_gk = gk_term.tail(window).mean()
        if rolling_gk <= 0 or np.isnan(rolling_gk):
            return 0.0
        return float(np.sqrt(rolling_gk) * 100.0)

    def _calculate_session_vwap(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculates Session Volume-Weighted Average Price (VWAP) and Standard Deviation Bands.
        Determines institutional Fair Value vs Premium/Discount extensions.
        """
        typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
        vol = df["volume"]

        cum_vol = vol.cumsum()
        safe_cum_vol = np.where(cum_vol == 0, 1.0, cum_vol)
        cum_pv = (typical_price * vol).cumsum()
        vwap_series = cum_pv / safe_cum_vol

        var = (vol * typical_price.pow(2)).cumsum() / safe_cum_vol - vwap_series.pow(2)
        std_vwap = np.sqrt(np.maximum(0.0, var))

        last_vwap = float(vwap_series.iloc[-1])
        last_std = float(std_vwap.iloc[-1])
        curr_price = float(df["close"].iloc[-1])

        vwap_upper1 = last_vwap + last_std
        vwap_lower1 = last_vwap - last_std
        vwap_upper2 = last_vwap + 2.0 * last_std
        vwap_lower2 = last_vwap - 2.0 * last_std

        vwap_z = ((curr_price - last_vwap) / last_std) if last_std > 0 else 0.0

        if curr_price > vwap_upper2:
            regime = "EXTREME_OVERBOUGHT_VWAP (+2σ)"
        elif curr_price > vwap_upper1:
            regime = "PREMIUM_OVER_VWAP (+1σ)"
        elif curr_price < vwap_lower2:
            regime = "EXTREME_OVERSOLD_VWAP (-2σ)"
        elif curr_price < vwap_lower1:
            regime = "DISCOUNT_UNDER_VWAP (-1σ)"
        else:
            regime = "FAIR_VALUE_INTRADAY"

        return {
            "vwap": round(last_vwap, 2),
            "vwap_upper1": round(vwap_upper1, 2),
            "vwap_lower1": round(vwap_lower1, 2),
            "vwap_upper2": round(vwap_upper2, 2),
            "vwap_lower2": round(vwap_lower2, 2),
            "vwap_z_score": round(vwap_z, 2),
            "vwap_regime": regime,
        }

    def _calculate_volume_profile(
        self, df: pd.DataFrame, n_bars: int = 100, n_bins: int = 25
    ) -> Dict[str, Any]:
        """
        Discretizes price range and aggregates traded volume.
        Extracts Point of Control (POC) and Value Area (VAH / VAL 70%).
        """
        sub = df.tail(n_bars)
        if len(sub) < 10:
            return {"poc": 0.0, "vah": 0.0, "val": 0.0, "dist_to_poc_pct": 0.0}

        p_min = float(sub["low"].min())
        p_max = float(sub["high"].max())
        if p_max <= p_min:
            curr = float(sub["close"].iloc[-1])
            return {"poc": curr, "vah": curr, "val": curr, "dist_to_poc_pct": 0.0}

        bin_edges = np.linspace(p_min, p_max, n_bins + 1)
        bin_vols = np.zeros(n_bins)

        for _, row in sub.iterrows():
            h, l, v = float(row["high"]), float(row["low"]), float(row["volume"])
            if h <= l or v <= 0:
                continue
            overlaps = (bin_edges[1:] >= l) & (bin_edges[:-1] <= h)
            count = np.sum(overlaps)
            if count > 0:
                bin_vols[overlaps] += v / count

        max_bin_idx = int(np.argmax(bin_vols))
        poc_price = float((bin_edges[max_bin_idx] + bin_edges[max_bin_idx + 1]) / 2.0)

        # 70% Value Area
        total_vol = np.sum(bin_vols)
        target_vol = total_vol * 0.70
        accum_vol = bin_vols[max_bin_idx]
        idx_lo = max_bin_idx
        idx_hi = max_bin_idx

        while accum_vol < target_vol and (idx_lo > 0 or idx_hi < n_bins - 1):
            v_next_lo = bin_vols[idx_lo - 1] if idx_lo > 0 else 0
            v_next_hi = bin_vols[idx_hi + 1] if idx_hi < n_bins - 1 else 0
            if v_next_lo >= v_next_hi and idx_lo > 0:
                idx_lo -= 1
                accum_vol += v_next_lo
            elif idx_hi < n_bins - 1:
                idx_hi += 1
                accum_vol += v_next_hi
            else:
                break

        val_price = float(bin_edges[idx_lo])
        vah_price = float(bin_edges[idx_hi + 1])

        curr = float(sub["close"].iloc[-1])
        dist_poc_pct = ((curr - poc_price) / poc_price) * 100.0 if poc_price > 0 else 0.0

        return {
            "poc": round(poc_price, 2),
            "vah": round(vah_price, 2),
            "val": round(val_price, 2),
            "dist_to_poc_pct": round(dist_poc_pct, 2),
        }

    def _calculate_cvd_proxy(self, df: pd.DataFrame, window: int = 14) -> Dict[str, Any]:
        """
        Approximates Buyer/Seller volume imbalance from bar microstructure using
        Wick Absorption Decomposition (Aronson & Lee-Ready Quantitative Heuristic):
        - Body Delta: Volume * (Close - Open) / Range
        - Lower Wick Absorption (Aggressive Buyer Absorption at lows): Volume * LowerWick / Range
        - Upper Wick Absorption (Aggressive Seller Absorption at highs): Volume * UpperWick / Range
        Net Bar Delta = Body Delta + 0.5 * (Lower Wick - Upper Wick) / Range
        """
        sub = df.tail(window).copy()
        highs = sub["high"].to_numpy(dtype=float)
        lows = sub["low"].to_numpy(dtype=float)
        opens = sub["open"].to_numpy(dtype=float)
        closes = sub["close"].to_numpy(dtype=float)
        volumes = sub["volume"].to_numpy(dtype=float)

        ranges = np.maximum(highs - lows, 1e-6)
        body_deltas = volumes * ((closes - opens) / ranges)

        upper_wicks = highs - np.maximum(opens, closes)
        lower_wicks = np.minimum(opens, closes) - lows

        wick_deltas = volumes * ((lower_wicks - upper_wicks) / (2.0 * ranges))
        total_bar_deltas = body_deltas + wick_deltas

        cvd_rolling = float(np.sum(total_bar_deltas))
        avg_vol = float(np.mean(volumes)) * window
        ratio = (cvd_rolling / avg_vol) if avg_vol > 0 else 0.0

        # Divergence Detection over the window:
        # If price made a new high but CVD is negative -> Bearish Absorption Divergence (Institutional Distribution)
        # If price made a new low but CVD is positive -> Bullish Absorption Divergence (Institutional Accumulation / Judas Swing)
        divergence = "NONE"
        if len(closes) >= 5:
            price_highest = closes[-1] >= np.max(closes[:-1])
            price_lowest = closes[-1] <= np.min(closes[:-1])
            if price_highest and ratio < -0.05:
                divergence = "BEARISH_ABSORPTION_DIV"
            elif price_lowest and ratio > 0.05:
                divergence = "BULLISH_ABSORPTION_DIV"

        if ratio > 0.20 or divergence == "BULLISH_ABSORPTION_DIV":
            pressure = "STRONG_BUYER_ABSORPTION"
        elif ratio < -0.20 or divergence == "BEARISH_ABSORPTION_DIV":
            pressure = "STRONG_SELLER_ABSORPTION"
        else:
            pressure = "BALANCED_ORDER_FLOW"

        return {
            "cvd_rolling": round(cvd_rolling, 1),
            "cvd_pressure_ratio": round(ratio, 2),
            "cvd_pressure": pressure,
            "cvd_divergence": divergence,
        }

    def process_technical_data(self, rates_data, broker_timezone="Europe/Kyiv") -> Optional[Dict[str, Any]]:
        # 1. Chuyển đổi Data thô sang DataFrame
        df = pd.DataFrame(rates_data)
        if len(df) < 15:
            return None

        for col in ["open", "high", "low", "close"]:
            if col in df.columns:
                df[col] = df[col].astype(float)
            else:
                df[col] = df["close"].astype(float)

        # CHUẨN HOÁ MÚI GIỜ
        if "time" in df.columns:
            df["time"] = pd.to_datetime(df["time"], unit="s")
            try:
                df["time"] = df["time"].dt.tz_localize(pytz.UTC)
                current_time_utc = df.iloc[-1]["time"].strftime("%Y-%m-%d %H:%M:%S UTC")
            except Exception:
                current_time_utc = "Không xác định"
        else:
            current_time_utc = "Không xác định"

        if "volume" not in df.columns:
            if "tick_volume" in df.columns:
                df.rename(columns={"tick_volume": "volume"}, inplace=True)
            else:
                df["volume"] = 1000.0
        elif "tick_volume" in df.columns:
            df.drop(columns=["tick_volume"], inplace=True)

        # Ensure no duplicate columns and clean index
        df = df.loc[:, ~df.columns.duplicated()].copy()
        df.reset_index(drop=True, inplace=True)

        # 2. Làm sạch dữ liệu (Xử lý NaN)
        df.ffill(inplace=True)

        # 3. Trích xuất đặc trưng Cổ điển
        df["EMA20"] = df["close"].ewm(span=20, adjust=False).mean()
        df["EMA50"] = df["close"].ewm(span=50, adjust=False).mean()

        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / np.where(loss == 0, 1e-6, loss)
        df["RSI"] = 100 - (100 / (1 + rs))

        # 4. Gắn nhãn dữ liệu Định lượng
        current = df.iloc[-1]
        rsi = float(current["RSI"]) if not np.isnan(current["RSI"]) else 50.0

        if rsi > 70:
            rsi_label = "QUÁ MUA (Khả năng đảo chiều giảm)"
        elif rsi < 30:
            rsi_label = "QUÁ BÁN (Khả năng bật tăng)"
        else:
            rsi_label = "TRUNG TÍNH"

        # 4. Nhận diện Vi cấu trúc và Xu hướng Hệ thống (Fractal Swings & Price Action Geometry)
        struct_res = MarketStructureEngine.analyze_market_structure(
            df, current_price=float(current["close"]), ema_period=50
        )
        if struct_res.trend == "BULLISH":
            trend_label = "TĂNG (Uptrend)"
        elif struct_res.trend == "BEARISH":
            trend_label = "GIẢM (Downtrend)"
        else:
            trend_label = "ĐI NGANG (Sideways)"

        # 5. Phân tích Cấu trúc S/R chuẩn Wyckoff Volume-Validated
        try:
            from backend.infrastructure.ai_engines.ai.sr_calculator import calculate_sr_levels

            sub_rates = rates_data[-150:] if len(rates_data) >= 150 else rates_data
            sr_info = calculate_sr_levels(sub_rates, zone_threshold=0.20)
            if sr_info:
                support = sr_info["support"]
                resistance = sr_info["resistance"]
            else:
                recent_50 = df.tail(50)
                resistance = float(recent_50["high"].max())
                support = float(recent_50["low"].min())
        except Exception:
            recent_50 = df.tail(50)
            resistance = float(recent_50["high"].max())
            support = float(recent_50["low"].min())

        # 6. Biên độ nến đơn giản (Legacy backward compatibility)
        recent_10 = df.tail(10)
        volatility = float(recent_10["high"].max() - recent_10["low"].min())

        # 7. CÁC ĐẶC TRƯNG VI CẤU TRÚC ĐỊNH LƯỢNG MỚI (INSTITUTIONAL QUANT)
        # a) Garman-Klass Realized Volatility (%)
        gk_vol = self._calculate_garman_klass_vol(df, window=14)

        # b) Session VWAP & Bands
        session_df=df
        if "time" in df.columns:
            session_df=df[df['time'].dt.date==df['time'].iloc[-1].date()]
        vwap_data = self._calculate_session_vwap(session_df)

        # c) Volume Profile & Point of Control (POC)
        vp_data = self._calculate_volume_profile(df, n_bars=100, n_bins=25)

        # d) Cumulative Volume Delta (CVD Proxy)
        cvd_data = self._calculate_cvd_proxy(df, window=14)

        # e) Dynamic Z-Score của giá so với EMA50 (Đo lường độ lệch chuẩn)
        trs = [
            max(
                df["high"].iloc[k] - df["low"].iloc[k],
                abs(df["high"].iloc[k] - df["close"].iloc[k - 1]),
                abs(df["low"].iloc[k] - df["close"].iloc[k - 1]),
            )
            for k in range(1, len(df))
        ]
        atr14 = float(np.mean(trs[-14:])) if len(trs) >= 14 else 1.0
        ema50_z = round((float(current["close"]) - float(current["EMA50"])) / atr14, 2) if atr14 > 0 else 0.0

        micro_summary = (
            f"VWAP: {vwap_data['vwap']} ({vwap_data['vwap_regime']}), "
            f"POC: {vp_data['poc']} (Dist: {vp_data['dist_to_poc_pct']:+.2f}%), "
            f"GK Vol: {gk_vol:.2f}%, OrderFlow: {cvd_data['cvd_pressure']}"
        )

        return {
            # --- 8 Existing Legacy Keys (Zero Breakage Guarantee) ---
            "current_time_utc": current_time_utc,
            "current_price": round(float(current["close"]), 2),
            "rsi_value": round(rsi, 1),
            "rsi_label": rsi_label,
            "trend": trend_label,
            "resistance": round(float(resistance), 2),
            "support": round(float(support), 2),
            "volatility": round(volatility, 4),
            # --- New Institutional Microstructure & Order Flow Features ---
            "garman_klass_vol": round(gk_vol, 3),
            "vwap": vwap_data["vwap"],
            "vwap_upper1": vwap_data["vwap_upper1"],
            "vwap_lower1": vwap_data["vwap_lower1"],
            "vwap_z_score": vwap_data["vwap_z_score"],
            "vwap_regime": vwap_data["vwap_regime"],
            "poc": vp_data["poc"],
            "vah": vp_data["vah"],
            "val": vp_data["val"],
            "dist_to_poc_pct": vp_data["dist_to_poc_pct"],
            "cvd_rolling": cvd_data["cvd_rolling"],
            "cvd_pressure_ratio": cvd_data["cvd_pressure_ratio"],
            "cvd_pressure": cvd_data["cvd_pressure"],
            "cvd_divergence": cvd_data.get("cvd_divergence", "NONE"),
            "ema50_z_score": ema50_z,
            "microstructure_summary": micro_summary,
            # --- System Market Structure & Geometry Features ---
            "market_structure": struct_res.to_dict(),
            "structure": struct_res.structure_label,
            "structure_label": struct_res.structure_label,
            "math_trend": struct_res.trend.capitalize(),
            "bos_detected": struct_res.bos_detected,
            "bos_direction": struct_res.bos_direction,
            "bos_level": struct_res.bos_level,
            "swing_highs": struct_res.swing_highs,
            "swing_lows": struct_res.swing_lows,
            "structure_confidence": struct_res.confidence,
        }
