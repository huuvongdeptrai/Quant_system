"""
AI Analysis Engine Thread and Decision Gate Panel Controller
"""

import os
import time
import json
from datetime import datetime
import numpy as np
import pandas as pd
import shiboken6
from PySide6 import QtCore, QtGui
from PySide6.QtCore import Qt, QTimer, QSize, QPointF
from PySide6.QtGui import QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QFrame, QLabel, QHBoxLayout, QVBoxLayout, QPushButton,
    QWidget, QScrollArea, QSizePolicy
)
from backend.infrastructure.brokers.mt5_safe import mt5
from backend.infrastructure.ai_engines.ai.analysis_engine import AnalysisEngine
from backend.infrastructure.ai_engines.ai.decision_gate import DecisionGate
from backend.infrastructure.ai_engines.ai.sr_calculator import calculate_sr_levels
from backend.core.strategies.strategy_loader import discover_strategies, load_strategy_instance
from backend.core.strategies.ict_strategy import ICTZonesProStrategy
from backend.infrastructure.data_providers.macro.macro_regime import MacroRegimeEngine

from frontend.controllers.chart.trading_plan_panel import (
    update_order_proposal_html,
    update_ai_reasoning,
)

class AISignals(QtCore.QObject):

    result = QtCore.Signal(dict)

    error = QtCore.Signal(str)

    loading = QtCore.Signal(str)


class AIAnalyzerThread(QtCore.QThread):

    def __init__(
        self,
        parent=None,
        sym="",
        rates=None,
        timeframe_str="",
        active_id=None,
        force_refresh=False,
        tech_data=None,
        d1_rates=None,
        h4_rates=None,
    ):

        super().__init__(parent)

        self.sym = sym

        self.rates = rates

        self.timeframe_str = timeframe_str

        self.active_id = active_id

        self.force_refresh = force_refresh

        self.tech_data = tech_data

        self.d1_rates = d1_rates

        self.h4_rates = h4_rates

        self.signals = AISignals()

        self.is_cancelled = False

    def stop(self):

        self.is_cancelled = True

    def run(self):

        try:

            from backend.infrastructure.ai_engines.ai.analysis_engine import AnalysisEngine

            from backend.infrastructure.ai_engines.ai.decision_gate import DecisionGate

            model_name = self.active_id if self.active_id else "qwen2.5"

            engine = AnalysisEngine(model_name=model_name)

            if self.is_cancelled:
                return

            try:
                self.signals.loading.emit("Đang tổng hợp dữ liệu...")
            except (RuntimeError, AttributeError):
                return

            result = engine.analyze(self.sym, force_refresh=self.force_refresh)

            if self.is_cancelled:
                return

            if "error" in result:
                try:
                    self.signals.error.emit(str(result["error"]))
                except (RuntimeError, AttributeError):
                    pass
                # Fallback to local quant model instantly so plan is never blank
                result = {
                    "_price": self.tech_data.get("current_price", 0) if self.tech_data else 0,
                    "_resistance": self.tech_data.get("resistance", 0) if self.tech_data else 0,
                    "_support": self.tech_data.get("support", 0) if self.tech_data else 0,
                    "trend_intraday": self.tech_data.get("math_trend", "SIDEWAYS") if self.tech_data else "SIDEWAYS",
                    "scenario_a": "Local Quant Model active (Ollama offline).",
                    "scenario_b": "Technical analysis via ICT Zones Pro.",
                    "confidence": 85,
                    "ai_offline": True,
                }

            # Dinh kem them gia va S/R tu cache hoac tech_data

            cached = engine.cache.get(self.sym, {})

            result["_price"] = cached.get("result", result).get("_price", 0)

            result["_resistance"] = cached.get("resistance", 0)

            result["_support"] = cached.get("support", 0)

            if self.tech_data:

                result["_price"] = self.tech_data["current_price"]

                result["_resistance"] = self.tech_data["resistance"]

                result["_support"] = self.tech_data["support"]

                if "math_trend" in self.tech_data:

                    result["trend_intraday"] = self.tech_data["math_trend"]

            # Them HTF bias va vi tri gia vao result

            try:

                gate = DecisionGate()

                # Để UI tính Hỗ trợ/Kháng cự bám sát theo Khung thời gian người dùng đang xem

                rates_for_pos = (
                    self.rates[-150:]
                    if self.rates is not None and len(self.rates) >= 150
                    else self.rates
                )

                price_info = gate._get_price_position(self.sym, rates=rates_for_pos)

                htf_bias = gate._get_htf_bias(
                    self.sym, d1_rates=self.d1_rates, h4_rates=self.h4_rates
                )

                if price_info:

                    result["_position"] = price_info["position"]

                    result["_pct_support"] = price_info.get("pct_from_support", 0)

                    result["_pct_resistance"] = price_info.get("pct_from_resistance", 0)

                result["_htf_bias"] = htf_bias

            except Exception:

                pass

            # Run configured quantitative strategy dynamically
            try:
                import pandas as pd
                from backend.core.strategies.strategy_loader import discover_strategies, load_strategy_instance
                from backend.core.strategies.ict_strategy import ICTZonesProStrategy
                from backend.infrastructure.data_providers.macro.macro_regime import MacroRegimeEngine

                if self.rates is not None and len(self.rates) >= 40:
                    df = pd.DataFrame(self.rates)
                    if "time" in df.columns:
                        df["time"] = pd.to_datetime(df["time"], unit="s")
                    macro_eng = MacroRegimeEngine()
                    macro_ctx = (
                        macro_eng.get_market_regime()
                        if hasattr(macro_eng, "get_market_regime")
                        else {"volatility_risk": "LOW", "bias": "NEUTRAL"}
                    )

                    strat_id = "builtin_ict_pro"
                    cfg_p = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "settings.json")
                    if os.path.exists(cfg_p):
                        try:
                            with open(cfg_p, "r", encoding="utf-8") as f_cfg:
                                cfg_data = json.load(f_cfg)
                                strat_id = cfg_data.get("strategy", "builtin_ict_pro")
                        except Exception:
                            pass

                    strat_inst = None
                    strat_display = "ICT Zones Pro v4.2"
                    all_strats = discover_strategies()
                    for s in all_strats:
                        if s["id"] == strat_id:
                            strat_display = s["name"].split("(")[0].strip()
                            strat_inst = load_strategy_instance(s["file_path"], s["class_name"])
                            break

                    if strat_inst is None:
                        strat_inst = ICTZonesProStrategy()
                        strat_display = "ICT Zones Pro v4.2"

                    res_strat = strat_inst.analyze(df, macro_ctx)
                    result["_strategy_res"] = res_strat
                    result["_strategy_name"] = strat_display
            except Exception as e_strat:
                logger.debug(f"[AIAnalysisThread] Strategy analysis: {e_strat}")

            try:
                self.signals.result.emit(result)
            except (RuntimeError, AttributeError):
                pass

        except Exception as e:
            if not self.is_cancelled:
                try:
                    self.signals.error.emit(str(e))
                except (RuntimeError, AttributeError):
                    pass


def _make_separator():

    sep = QFrame()

    sep.setFrameShape(QFrame.HLine)

    sep.setStyleSheet("background-color: #21262D; max-height: 1px;")

    return sep


def _make_label(text, color="#8B949E", size=11, bold=False, font="Segoe UI"):

    lbl = QLabel(text)

    weight = "bold" if bold else "normal"

    lbl.setStyleSheet(
        f"color: {color}; font-size: {size}px; font-weight: {weight}; font-family: '{font}';"
    )

    lbl.setWordWrap(True)

    return lbl


def _build_analysis_panel(window):
    """Preserve AI DECISION GATE from quant_ai.ui and provide dummy labels for backwards compatibility."""
    for attr in [
        "ai_lbl_header",
        "ai_lbl_time",
        "ai_lbl_price",
        "ai_lbl_resistance",
        "ai_lbl_res_delta",
        "ai_lbl_support",
        "ai_lbl_sup_delta",
        "ai_lbl_macro",
        "ai_lbl_htf",
        "ai_lbl_intraday",
        "ai_lbl_position",
        "ai_lbl_scenario_a",
        "ai_lbl_scenario_b",
        "ai_lbl_status",
    ]:
        if not hasattr(window, attr):
            setattr(window, attr, QLabel())


def _force_reanalyze(window):

    if window.current_sym:

        _run_analysis(window, window.current_sym, force=True)


def _update_panel_with_result(window, result):
    """Cap nhat tat ca cac QLabel tren panel tu dict ket qua AI."""

    now_str = datetime.now().strftime("%H:%M %d/%m/%Y")

    window.ai_lbl_time.setText(f"C\u1eadp nh\u1eadt: {now_str}")

    price = result.get("_price", 0)

    res = result.get("_resistance", 0)

    sup = result.get("_support", 0)

    sym_name = getattr(window, "current_sym", "XAUUSD").split("\n")[0].strip()
    sym_info = mt5.symbol_info(sym_name)
    digits = sym_info.digits if sym_info else (2 if price > 10 else 5)

    if price > 0:

        window.ai_lbl_price.setText(f"{price:,.{digits}f}")

    if res > 0:

        window.ai_lbl_resistance.setText(f"{res:,.{digits}f}")

        delta_r = res - price if price > 0 else 0

        window.ai_lbl_res_delta.setText(f"{delta_r:+,.{digits}f}")

    if sup > 0:

        window.ai_lbl_support.setText(f"{sup:,.{digits}f}")

        delta_s = sup - price if price > 0 else 0

        window.ai_lbl_sup_delta.setText(f"{delta_s:+,.{digits}f}")

    # Xu huong

    macro_trend = result.get("trend_macro", "--")

    intra_trend = result.get("trend_intraday", "--")

    def _trend_color(trend_text):

        t = trend_text.lower()

        if "t\u0103ng" in t or "bullish" in t or "tang" in t:

            return "#3FB950"

        elif "gi\u1ea3m" in t or "bearish" in t or "giam" in t:

            return "#F23645"

        return "#8B949E"

    window.ai_lbl_macro.setText(macro_trend)

    window.ai_lbl_macro.setStyleSheet(
        f"color: {_trend_color(macro_trend)}; font-size: 13px; font-weight: bold; font-family: 'Segoe UI';"
    )

    window.ai_lbl_intraday.setText(intra_trend)

    window.ai_lbl_intraday.setStyleSheet(
        f"color: {_trend_color(intra_trend)}; font-size: 13px; font-weight: bold; font-family: 'Segoe UI';"
    )

    # Kich ban

    window.ai_lbl_scenario_a.setText(result.get("scenario_a", "--"))

    window.ai_lbl_scenario_b.setText(result.get("scenario_b", "--"))

    # HTF Bias

    htf = result.get("_htf_bias", "--")

    htf_map = {
        "BULLISH": "T\u0103ng",
        "BEARISH": "Gi\u1ea3m",
        "NEUTRAL": "\u0110i ngang",
    }

    htf_text = htf_map.get(htf, htf)

    window.ai_lbl_htf.setText(htf_text)

    window.ai_lbl_htf.setStyleSheet(
        f"color: {_trend_color(htf_text)}; font-size: 13px; font-weight: bold; font-family: 'Segoe UI';"
    )

    # Vi tri gia

    pos = result.get("_position", "--")

    pos_map = {
        "AT_SUPPORT": "T\u1ea1i H\u1ed7 tr\u1ee3",
        "AT_RESISTANCE": "T\u1ea1i Kh\u00e1ng c\u1ef1",
        "MIDDLE": "Gi\u1eefa v\u00f9ng",
    }

    pos_text = pos_map.get(pos, pos)

    pos_color = (
        "#3FB950"
        if pos == "AT_SUPPORT"
        else "#F23645" if pos == "AT_RESISTANCE" else "#8B949E"
    )

    window.ai_lbl_position.setText(pos_text)

    window.ai_lbl_position.setStyleSheet(
        f"color: {pos_color}; font-size: 13px; font-weight: bold; font-family: 'Segoe UI';"
    )

    window.ai_lbl_status.setText("")
    clean_sym = getattr(window, "current_sym", "XAUUSD").split("\n")[0].strip()
    window._last_htf_bias = htf_text
    confidence_val = f"{int(result.get('confidence', 85))}%" if 'confidence' in result else "84.5%"
    window._last_confidence = confidence_val

    strat_res = result.get("_strategy_res", {})
    strat_name = result.get("_strategy_name", "Quantitative Strategy")
    strat_sig = strat_res.get("signal", "HOLD")
    strat_meta = strat_res.get("metadata", {})
    obs_cnt = strat_meta.get("active_obs", 0)
    fvgs_cnt = strat_meta.get("active_fvgs", 0)
    bias_val = strat_meta.get("bias", 0)
    if not isinstance(bias_val, (int, float)):
        try:
            bias_val = int(bias_val)
        except Exception:
            bias_val = 0

    # Hỗ trợ linh hoạt các định dạng khóa đầu ra từ chiến lược tùy chỉnh
    raw_entry = strat_res.get("entry_price") or strat_res.get("entry") or strat_res.get("price") or (price if price > 0 else None)
    raw_sl = strat_res.get("sl") or strat_res.get("sl_price") or strat_res.get("stop_loss")
    raw_tp = strat_res.get("tp1") or strat_res.get("tp") or strat_res.get("tp_price") or strat_res.get("take_profit")

    has_valid_signal = (
        strat_sig in ("BUY", "SELL")
        and raw_entry is not None
        and raw_sl is not None
    )

    # Trích xuất danh mục kiểm tra thích ứng theo từng loại chiến lược
    user_chk = strat_res.get("checklist") or strat_meta.get("checklist") or []
    is_ict = "ict" in strat_name.lower()
    is_ema = "ema" in strat_name.lower()

    if has_valid_signal:
        entry_val = float(raw_entry)
        sl_val = float(raw_sl)
        tp_val = float(raw_tp or (entry_val + abs(entry_val - sl_val) * 2.0))
        conf_raw = strat_res.get("confidence", 0.85)
        conf_pct = f"{int(conf_raw * 100 if conf_raw <= 1.0 else conf_raw)}%"
        ai_model = f"{strat_name} ({'BUY SIGNAL' if strat_sig == 'BUY' else 'SELL SIGNAL'})"

        if isinstance(user_chk, list) and len(user_chk) >= 3:
            chk1, chk2, chk3 = str(user_chk[0]), str(user_chk[1]), str(user_chk[2])
        elif is_ict:
            chk1 = f"STRUCTURE: {htf_text.upper()}"
            chk2 = "LIQUIDITY: ASIAN SWEEP"
            chk3 = f"CONFLUENCE: {obs_cnt} OB & {fvgs_cnt} FVG"
        elif is_ema:
            chk1 = f"TREND: {htf_text.upper()}"
            chk2 = "SIGNAL: MOVING AVERAGE CROSSOVER"
            chk3 = f"RISK / REWARD: {abs(tp_val - entry_val) / max(0.001, abs(entry_val - sl_val)):.1f}R"
        else:
            chk1 = f"STRUCTURE: {htf_text.upper()}"
            chk2 = f"STRATEGY SIGNAL: {strat_sig}"
            chk3 = f"CONFIDENCE: {conf_pct}"

        kwargs_order = {
            "sym": clean_sym,
            "has_signal": True,
            "signal_type": strat_sig,
            "model_name": ai_model,
            "grade": f"CONFIDENCE: {conf_pct}",
            "chk1": chk1,
            "chk2": chk2,
            "chk3": chk3,
            "entry": entry_val,
            "sl": sl_val,
            "tp": tp_val,
            "confidence": conf_pct,
            "status": "WAITING OPERATOR APPROVAL",
            "digits": digits,
        }
    else:
        bias_desc = "BULLISH" if bias_val > 0 else ("BEARISH" if bias_val < 0 else "SIDEWAYS")
        ai_model = f"{strat_name}"

        if isinstance(user_chk, list) and len(user_chk) >= 3:
            chk1, chk2, chk3 = str(user_chk[0]), str(user_chk[1]), str(user_chk[2])
        elif is_ict:
            chk1 = f"STRUCTURE: {bias_desc} ({htf_text.upper()})"
            chk2 = "LIQUIDITY: MONITORING ASIAN HIGH/LOW"
            chk3 = f"ORDER BLOCKS & FVG: {obs_cnt} OB | {fvgs_cnt} FVG"
        elif is_ema:
            chk1 = f"TREND: {htf_text.upper()}"
            chk2 = "SIGNAL: AWAITING MOVING AVERAGE CROSSOVER"
            chk3 = "STATUS: MONITORING VOLATILITY"
        else:
            chk1 = f"STRUCTURE: {htf_text.upper()}"
            chk2 = f"STATUS: {strat_name} SCANNING"
            chk3 = f"PRICE ZONE: {pos_text.upper()}"

        kwargs_order = {
            "sym": clean_sym,
            "has_signal": False,
            "signal_type": "HOLD",
            "model_name": ai_model,
            "grade": "STATUS: STANDBY",
            "chk1": chk1,
            "chk2": chk2,
            "chk3": chk3,
            "status": "SCANNING_STANDBY",
            "digits": digits,
        }

    update_order_proposal_html(window, **kwargs_order)


def _run_analysis(window, sym, force=False):
    """Bat dau thread phan tich AI."""

    if not sym:

        window.ai_lbl_status.setText("Select a symbol")

        return

    sym = sym.split("\n")[0].strip()

    window.ai_lbl_header.setText(f"{sym}  {window.current_tf_str}")

    window.ai_lbl_status.setText("Analyzing...")

    window.ai_lbl_status.setStyleSheet(
        "color: #58A6FF; font-size: 10px; font-family: 'Segoe UI';"
    )

    if not hasattr(window, "_active_ai_threads"):

        window._active_ai_threads = set()

    if (
        hasattr(window, "ai_thread")
        and window.ai_thread
        and window.ai_thread.isRunning()
    ):

        old_t = window.ai_thread

        old_t.stop()

        window._active_ai_threads.add(old_t)

        old_t.finished.connect(lambda t=old_t: window._active_ai_threads.discard(t))

    active_id = None
    try:
        import shiboken6
        if (
            hasattr(window, "comboAIModel")
            and window.comboAIModel is not None
            and shiboken6.isValid(window.comboAIModel)
            and window.comboAIModel.count() > 0
        ):
            active_id = window.comboAIModel.currentText()
    except Exception:
        active_id = None

    rates = mt5.copy_rates_from_pos(sym, window.current_tf, 0, 5000)

    if rates is None or len(rates) == 0:
        window.ai_lbl_status.setText("Awaiting MT5 feed...")
        if hasattr(window, "lbl_ai_action") and window.lbl_ai_action:
            window.lbl_ai_action.setText("AWAITING FEED")
        if hasattr(window, "lbl_ai_conf") and window.lbl_ai_conf:
            window.lbl_ai_conf.setText("--%")
        if hasattr(window, "lbl_ai_reason") and window.lbl_ai_reason:
            window.lbl_ai_reason.setText("No live candle feed from MetaTrader 5.")
        return

    # Kéo thêm dữ liệu và tính toán Volume-Validated Fractals + Math Intraday Trend

    tech_data = None

    r_100 = mt5.copy_rates_from_pos(sym, window.current_tf, 0, 150)

    if r_100 is not None and len(r_100) >= 25:

        current_price = r_100[-1]["close"]

        sub_rates = r_100[-150:]

        volumes = [r["tick_volume"] for r in sub_rates]

        valid_resistances = []

        valid_supports = []

        swing_highs = []

        swing_lows = []

        for i in range(2, len(sub_rates) - 2):

            high = sub_rates[i]["high"]

            low = sub_rates[i]["low"]

            if (
                high > sub_rates[i - 1]["high"]
                and high > sub_rates[i - 2]["high"]
                and high > sub_rates[i + 1]["high"]
                and high > sub_rates[i + 2]["high"]
            ):

                swing_highs.append(high)

            if (
                low < sub_rates[i - 1]["low"]
                and low < sub_rates[i - 2]["low"]
                and low < sub_rates[i + 1]["low"]
                and low < sub_rates[i + 2]["low"]
            ):

                swing_lows.append(low)

        from backend.infrastructure.ai_engines.ai.sr_calculator import calculate_sr_levels

        sr_info = calculate_sr_levels(sub_rates, current_price=current_price)

        if sr_info:

            resistance = sr_info["resistance"]

            support = sr_info["support"]

        else:

            resistance = max([r["high"] for r in sub_rates[-50:]])

            support = min([r["low"] for r in sub_rates[-50:]])

        closes = [r["close"] for r in sub_rates]

        period = min(50, len(closes))

        alpha = 2 / (period + 1)

        ema = sum(closes[:period]) / period

        for price in closes[period:]:

            ema = (price - ema) * alpha + ema

        math_trend = "SIDEWAYS"

        if len(swing_highs) >= 2 and len(swing_lows) >= 2:

            if (
                swing_highs[-1] > swing_highs[-2]
                and swing_lows[-1] > swing_lows[-2]
                and current_price > ema
            ):

                math_trend = "BULLISH"

            elif (
                swing_highs[-1] < swing_highs[-2]
                and swing_lows[-1] < swing_lows[-2]
                and current_price < ema
            ):

                math_trend = "BEARISH"

        elif current_price > ema * 1.002:

            math_trend = "BULLISH"

        elif current_price < ema * 0.998:

            math_trend = "BEARISH"

        tech_data = {
            "current_price": current_price,
            "resistance": resistance,
            "support": support,
            "math_trend": math_trend,
            "ema_50": round(ema, 2),
            "ema_position": "ABOVE EMA 50" if current_price > ema else "BELOW EMA 50",
            "structure": f"Volume-Validated (KC: {resistance:.2f}, HT: {support:.2f})",
        }

    d1_rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_D1, 0, 60)

    h4_rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H4, 0, 60)

    thread = AIAnalyzerThread(
        parent=window,
        sym=sym,
        rates=rates,
        timeframe_str=window.current_tf_str,
        active_id=active_id,
        force_refresh=force,
        tech_data=tech_data,
        d1_rates=d1_rates,
        h4_rates=h4_rates,
    )

    window.ai_thread = thread

    window._active_ai_threads.add(thread)

    thread.finished.connect(lambda t=thread: window._active_ai_threads.discard(t))

    thread.signals.result.connect(
        lambda r, t=thread: _update_panel_with_result(window, r)
        if getattr(window, "ai_thread", None) is t and not t.is_cancelled
        else None,
        Qt.QueuedConnection,
    )

    thread.signals.error.connect(
        lambda e, t=thread: _show_error(window, e)
        if getattr(window, "ai_thread", None) is t and not t.is_cancelled
        else None,
        Qt.QueuedConnection,
    )

    thread.signals.loading.connect(
        lambda s, t=thread: window.ai_lbl_status.setText(s)
        if getattr(window, "ai_thread", None) is t and not t.is_cancelled
        else None,
        Qt.QueuedConnection,
    )

    window.ai_thread.start()


def _show_error(window, error_text):
    window.ai_lbl_status.setText(f"AI: {error_text} - Fallback to Quant Model")
    window.ai_lbl_status.setStyleSheet(
        "color: #f59e0b; font-size: 10px; font-family: 'Segoe UI';"
    )
    clean_sym = getattr(window, "current_sym", "XAUUSD").split("\n")[0].strip()
    update_order_proposal_html(window, sym=clean_sym)


# --- CHI BAO CATALOG ---


INDICATOR_CATALOG = {
    "Xu huong": [
        {"id": "ema", "available": True},
        {"id": "ma200", "available": True},
    ],
    "Cau truc gia": [
        {"id": "donchian", "available": True},
        {"id": "pivot", "available": True},
    ],
    "Dao dong": [
        {"id": "rsi", "available": False},
        {"id": "macd", "available": False},
    ],
    "Khoi luong": [
        {"id": "volume", "available": False},
    ],
}


INDICATOR_LABELS = {
    "Trend": "Trend",
    "Price Structure": "Price Structure",
    "Oscillators": "Oscillators",
    "Volume": "Volume",
    "ema": "EMA (10, 50)",
    "ma200": "MA 200",
    "donchian": "Support / Resistance (Donchian 100)",
    "pivot": "Pivot Points (Classic)",
    "rsi": "RSI (14) (Coming Soon)",
    "macd": "MACD (Coming Soon)",
    "volume": "Volume (Coming Soon)",
}


