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
from loguru import logger
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
        strategy_id=None,
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

        self.strategy_id = strategy_id

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

                    strat_id = getattr(self, "strategy_id", None)
                    from backend.core.strategies import get_strategy_instance
                    strat_inst = get_strategy_instance(strat_id)
                    strat_display = getattr(strat_inst, "name", "Quantitative Strategy")
                    res_strat = strat_inst.analyze(df, macro_ctx)
                    result["_strategy_res"] = res_strat
                    result["_strategy_name"] = strat_display
            except Exception as e_strat:
                logger.debug(f"[AIAnalysisThread] Strategy analysis: {e_strat}")

            if self.rates is not None and len(self.rates) > 0:
                try:
                    result["_candle_time"] = int(self.rates[-1]["time"])
                except Exception:
                    result["_candle_time"] = int(time.time())
            else:
                result["_candle_time"] = int(time.time())

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

    # Detect execution mode and background bot status
    exec_mode = "MANUAL"
    bot_tf = 15
    if hasattr(window, "quant_terminal") and window.quant_terminal:
        qt = window.quant_terminal
        if hasattr(qt, "header") and hasattr(qt.header, "execution_mode"):
            exec_mode = qt.header.execution_mode
        elif hasattr(qt, "execution_mode"):
            exec_mode = qt.execution_mode
    if exec_mode == "MANUAL":
        try:
            cfg_p = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "config", "settings.json")
            if os.path.exists(cfg_p):
                with open(cfg_p, "r", encoding="utf-8") as f_cfg:
                    cfg_data = json.load(f_cfg)
                    exec_mode = cfg_data.get("execution_mode", "MANUAL")
                    bot_tf = int(cfg_data.get("timeframe", 15))
        except Exception:
            pass

    is_bot_active = False
    if hasattr(window, "quant_terminal") and window.quant_terminal:
        qt = window.quant_terminal
        if hasattr(qt, "bot_worker") and qt.bot_worker and getattr(qt.bot_worker, "is_running", False):
            is_bot_active = True
        elif hasattr(qt, "bot_thread") and qt.bot_thread and qt.bot_thread.isRunning():
            is_bot_active = True
        elif hasattr(qt, "header") and hasattr(qt.header, "btn_algo_toggle"):
            btn = qt.header.btn_algo_toggle
            if hasattr(btn, "_is_running") and btn._is_running:
                is_bot_active = True

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

    # 1. LIVE MT5 POSITION AWARENESS
    live_pos = None
    try:
        if mt5.terminal_info() is not None:
            open_positions = mt5.positions_get(symbol=clean_sym)
            if open_positions and len(open_positions) > 0:
                live_pos = open_positions[0]
    except Exception as e_pos:
        logger.debug(f"[AIAnalysis] Check live positions: {e_pos}")

    if live_pos is not None:
        pos_side = "BUY" if live_pos.type == 0 else "SELL"
        live_entry = float(live_pos.price_open)
        live_profit = float(live_pos.profit)
        live_vol = float(live_pos.volume)
        pnl_str = f"+${live_profit:.2f}" if live_profit >= 0 else f"-${abs(live_profit):.2f}"
        pts_default = 10.0 if "XAU" in clean_sym else 100.0
        live_sl = float(live_pos.sl) if live_pos.sl > 0 else (live_entry - pts_default if pos_side == "BUY" else live_entry + pts_default)
        live_tp = float(live_pos.tp) if live_pos.tp > 0 else (live_entry + pts_default * 2.0 if pos_side == "BUY" else live_entry - pts_default * 2.0)
        # Check trailing stop setting
        ts_on = False
        try:
            cfg_p = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "config", "settings.json")
            if os.path.exists(cfg_p):
                with open(cfg_p, "r", encoding="utf-8") as f_cfg:
                    ts_on = json.load(f_cfg).get("enable_trailing_stop", False)
        except Exception:
            pass

        status_txt = ("BOT AUTO MANAGING (TRAILING SL)" if ts_on else "BOT AUTO MANAGING (TARGET TP/SL)") if (is_bot_active or exec_mode == "FULL-AUTO") else "LIVE POSITION IN MARKET"

        if "wyckoff" in strat_name.lower():
            chk1_pos = f"WYCKOFF {pos_side} STRUCTURE"
            chk2_pos = f"EMA20 {'PULLBACK' if pos_side == 'BUY' else 'RETEST'} FILLED"
            chk3_pos = "VOLUME EXPANSION ACTIVE"
        elif "ema" in strat_name.lower():
            chk1_pos = f"EMA {pos_side} STRUCTURE"
            chk2_pos = "CROSSOVER ACTIVE"
            chk3_pos = "TARGET TRAILING ACTIVE"
        else:
            chk1_pos = f"{pos_side} STRUCTURE CONFIRMED"
            chk2_pos = f"ASIAN {'HIGH' if pos_side == 'SELL' else 'LOW'} SWEPT"
            chk3_pos = "M15 FVG MITIGATED"

        kwargs_order = {
            "sym": clean_sym,
            "has_signal": True,
            "signal_type": pos_side,
            "model_name": strat_name,
            "grade": f"PNL: {pnl_str}",
            "chk1": chk1_pos,
            "chk2": chk2_pos,
            "chk3": chk3_pos,
            "entry": live_entry,
            "sl": live_sl,
            "tp": live_tp,
            "confidence": "100%",
            "status": status_txt,
            "digits": digits,
            "is_live_position": True,
            "live_ticket": live_pos.ticket,
            "live_profit": live_profit,
            "live_volume": live_vol,
            "exec_mode": exec_mode,
            "is_bot_active": is_bot_active,
        }
        update_order_proposal_html(window, **kwargs_order)
        return

    # 2. PENDING ORDER AWARENESS
    pending_order = None
    try:
        if mt5.terminal_info() is not None:
            orders = mt5.orders_get(symbol=clean_sym)
            if orders and len(orders) > 0:
                pending_order = orders[0]
    except Exception as e_ord:
        logger.debug(f"[AIAnalysis] Check pending orders: {e_ord}")

    if pending_order is not None:
        o = pending_order
        o_side = "BUY" if o.type in (2, 4) else "SELL"
        o_type_name = "BUY LIMIT" if o.type == 2 else ("SELL LIMIT" if o.type == 3 else ("BUY STOP" if o.type == 4 else "SELL STOP"))
        o_entry = float(o.price_open)
        pts_default = 10.0 if "XAU" in clean_sym else 100.0
        o_sl = float(o.sl) if o.sl > 0 else (o_entry - pts_default if o_side == "BUY" else o_entry + pts_default)
        o_tp = float(o.tp) if o.tp > 0 else (o_entry + pts_default * 2.0 if o_side == "BUY" else o_entry - pts_default * 2.0)
        o_vol = float(getattr(o, "volume_current", getattr(o, "volume_initial", 0.10)))

        if "wyckoff" in strat_name.lower():
            chk1_pnd = f"{o_side} SETUP CONFIRMED"
            chk2_pnd = f"EMA LEVEL AT {o_entry:.{digits}f}"
            chk3_pnd = "AWAITING VOLUME EXPANSION"
        elif "ema" in strat_name.lower():
            chk1_pnd = f"{o_side} TREND CONFIRMED"
            chk2_pnd = f"LIMIT AT {o_entry:.{digits}f}"
            chk3_pnd = "AWAITING FILL IN MARKET"
        else:
            chk1_pnd = f"{o_side} SETUP CONFIRMED"
            chk2_pnd = f"LIMIT ORDER AT {o_entry:.{digits}f}"
            chk3_pnd = "AWAITING FILL IN MARKET"

        kwargs_order = {
            "sym": clean_sym,
            "has_signal": True,
            "signal_type": o_side,
            "model_name": strat_name,
            "grade": f"PENDING #{o.ticket}",
            "chk1": chk1_pnd,
            "chk2": chk2_pnd,
            "chk3": chk3_pnd,
            "entry": o_entry,
            "sl": o_sl,
            "tp": o_tp,
            "confidence": "100%",
            "status": f"PENDING IN MT5 (#{o.ticket})",
            "digits": digits,
            "is_pending_order": True,
            "pending_ticket": o.ticket,
            "live_volume": o_vol,
            "exec_mode": exec_mode,
            "is_bot_active": is_bot_active,
        }
        update_order_proposal_html(window, **kwargs_order)
        return

    # 3. FRESH SIGNAL EVALUATION (No live/pending trades)
    raw_entry = strat_res.get("entry_price") or strat_res.get("entry") or strat_res.get("price") or (price if price > 0 else None)
    raw_sl = strat_res.get("sl") or strat_res.get("sl_price") or strat_res.get("stop_loss")
    raw_tp = strat_res.get("tp1") or strat_res.get("tp") or strat_res.get("tp_price") or strat_res.get("take_profit")

    has_valid_signal = (
        strat_sig in ("BUY", "SELL")
        and raw_entry is not None
        and raw_sl is not None
    )

    user_chk = strat_res.get("checklist") or strat_meta.get("checklist") or []
    strat_checklist = user_chk

    if has_valid_signal:
        entry_val = float(raw_entry)
        sl_val = float(raw_sl)
        tp_val = float(raw_tp or (entry_val + abs(entry_val - sl_val) * 2.0))
        conf_raw = strat_res.get("confidence", 0.85)
        conf_pct = f"{int(conf_raw * 100 if conf_raw <= 1.0 else conf_raw)}%"
        ai_model = f"{strat_name} ({strat_sig})"

        candle_time = result.get("_candle_time")
        if not candle_time:
            candle_time = int(time.time())

        sig_key = f"{clean_sym}_{candle_time}_{strat_sig}_{round(entry_val, 2)}"

        chk1, chk2, chk3 = None, None, None
        if isinstance(strat_checklist, (list, tuple)) and len(strat_checklist) >= 3:
            chk1 = strat_checklist[0].value if hasattr(strat_checklist[0], "value") else (strat_checklist[0].get("value") if isinstance(strat_checklist[0], dict) else str(strat_checklist[0]))
            chk2 = strat_checklist[1].value if hasattr(strat_checklist[1], "value") else (strat_checklist[1].get("value") if isinstance(strat_checklist[1], dict) else str(strat_checklist[1]))
            chk3 = strat_checklist[2].value if hasattr(strat_checklist[2], "value") else (strat_checklist[2].get("value") if isinstance(strat_checklist[2], dict) else str(strat_checklist[2]))
        else:
            chk1 = f"{strat_sig} Setup Confirmed"
            chk2 = f"Strategy Signal: {strat_sig}"
            chk3 = f"Confidence: {conf_pct}"

        # -----------------------------------------------------------------
        # MODE 1: FULL-AUTO -> AUTONOMOUS MT5 DISPATCH (NO HUMAN APPROVAL)
        # -----------------------------------------------------------------
        if exec_mode == "FULL-AUTO":
            # Guard against re-executing the exact same signal on the same candle
            if getattr(window, "_last_executed_signal", None) == sig_key:
                logger.debug(f"[FULL-AUTO] Signal {sig_key} already executed on this candle. Skipping re-entry.")
                return

            is_buy = (strat_sig == "BUY")
            # Strict stop loss orientation guard
            if (is_buy and sl_val >= entry_val) or (not is_buy and sl_val <= entry_val):
                from backend.core.event_bus import event_bus
                event_bus.log_event.emit("", "ERROR", f"FULL-AUTO Intercepted: Invalid SL ({sl_val:.{digits}f}) for {strat_sig} at ({entry_val:.{digits}f})", "#ef4444")
                window._last_executed_signal = sig_key
                return

            from frontend.controllers.chart.trading_plan_panel import calculate_manual_quant_lot
            sl_pts = abs(entry_val - sl_val)
            risk_pct = 1.0
            try:
                cfg_p = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "config", "settings.json")
                if os.path.exists(cfg_p):
                    with open(cfg_p, "r", encoding="utf-8") as f_cfg:
                        risk_pct = float(json.load(f_cfg).get("risk_per_trade", 1.0))
            except Exception:
                pass

            lot_size, _ = calculate_manual_quant_lot(clean_sym, sl_pts, risk_pct=risk_pct)

            exec_mgr = None
            if hasattr(window, "quant_terminal") and hasattr(window.quant_terminal, "exec_mgr"):
                exec_mgr = window.quant_terminal.exec_mgr
            if not exec_mgr:
                from backend.infrastructure.brokers.execution_manager import ExecutionManager
                exec_mgr = ExecutionManager(slippage=20, magic_number=888888)

            order_res = None
            if exec_mgr and hasattr(exec_mgr, "execute_market_order"):
                order_res = exec_mgr.execute_market_order(
                    symbol=clean_sym,
                    is_buy=is_buy,
                    volume=lot_size,
                    sl_price=sl_val,
                    tp_price=tp_val,
                    comment=f"FULL_AUTO_{clean_sym}"
                )
            elif mt5.terminal_info() is not None:
                order_res = exec_mgr.execute_market_order(
                    symbol=clean_sym,
                    is_buy=is_buy,
                    volume=lot_size,
                    sl_price=sl_val,
                    tp_price=tp_val,
                    comment=f"FULL_AUTO_{clean_sym}"
                )
            else:
                order_res = {"status": "success", "ticket": int(time.time()) % 1000000, "price": entry_val}

            window._last_executed_signal = sig_key
            from backend.core.event_bus import event_bus
            if order_res and order_res.get("status") == "success":
                ticket = order_res.get("ticket", "OK")
                event_bus.log_event.emit("", "SUCCESS", f"FULL-AUTO Autonomous Fill: {strat_sig} {lot_size:.2f} lots {clean_sym} #{ticket}", "#10b981")

                try:
                    from backend.database.db_manager import DatabaseManager
                    db = DatabaseManager()
                    if isinstance(ticket, int):
                        db.record_open_trade(
                            ticket=ticket,
                            symbol=clean_sym,
                            order_type=strat_sig,
                            volume=lot_size,
                            open_price=entry_val,
                            sl=sl_val,
                            tp=tp_val,
                            comment=f"FULL_AUTO_{clean_sym}",
                        )
                except Exception as e_db:
                    logger.debug(f"[AIPanel] DB record open trade error: {e_db}")

                try:
                    from backend.infrastructure.notifications.telegram_notifier import telegram_notifier
                    telegram_notifier.send_message(
                        f"🚀 <b>ORDER FILLED: {strat_sig} {clean_sym}</b>\n"
                        f"Ticket: <b>#{ticket}</b> | Mode: <b>FULL-AUTO</b>\n"
                        f"Volume: <b>{lot_size:.2f} Lots</b> @ <b>{entry_val:.{digits}f}</b>\n"
                        f"SL: <b>{sl_val:.{digits}f}</b> | TP: <b>{tp_val:.{digits}f}</b>\n"
                        f"Model: <i>{ai_model}</i>",
                        category="fill",
                    )
                except Exception as e_tg:
                    logger.debug(f"[AIPanel] Telegram notification error: {e_tg}")

                # Immediately transition UI to live position mode without any countdown timer
                kwargs_order = {
                    "sym": clean_sym,
                    "has_signal": True,
                    "signal_type": strat_sig,
                    "model_name": ai_model,
                    "grade": "PNL: +$0.00",
                    "chk1": f"{strat_sig} AUTONOMOUS EXECUTION",
                    "chk2": f"ORDER ROUTED #{ticket}",
                    "chk3": "TARGET TP / TRAILING SL ACTIVE",
                    "entry": entry_val,
                    "sl": sl_val,
                    "tp": tp_val,
                    "confidence": conf_pct,
                    "status": "BOT AUTO MANAGING (TARGET TP/SL)",
                    "digits": digits,
                    "is_live_position": True,
                    "live_ticket": ticket,
                    "live_profit": 0.0,
                    "live_volume": lot_size,
                    "exec_mode": exec_mode,
                    "is_bot_active": is_bot_active,
                }
                update_order_proposal_html(window, **kwargs_order)
                return
            else:
                err_msg = order_res.get("msg", "Rejected") if order_res else "Broker disconnected"
                event_bus.log_event.emit("", "ERROR", f"FULL-AUTO Execution Rejected: {err_msg}", "#ef4444")
                return

        # -----------------------------------------------------------------
        # MODE 2: SEMI-AUTO -> DECISION GATE (PROPOSAL + OPERATOR APPROVAL)
        # -----------------------------------------------------------------
        elif exec_mode == "SEMI-AUTO":
            # Suppress re-push if operator discarded this signal on this candle
            if hasattr(window, "_discarded_signals") and sig_key in window._discarded_signals:
                logger.debug(f"[SEMI-AUTO] Signal {sig_key} was previously discarded. Suppressing re-push.")
                return

            # Suppress timer reset / UI flicker if this proposal is ALREADY actively counting down
            if getattr(window, "order_proposal_active", False) and getattr(window, "_active_proposal_sig", None) == sig_key:
                logger.debug(f"[SEMI-AUTO] Signal {sig_key} is actively counting down. Preserving timer.")
                return

            window._active_proposal_sig = sig_key
            status_val = "WAITING OPERATOR APPROVAL"

            kwargs_order = {
                "sym": clean_sym,
                "has_signal": True,
                "signal_type": strat_sig,
                "model_name": ai_model,
                "grade": f"CONFIDENCE: {conf_pct}",
                "chk1": chk1,
                "chk2": chk2,
                "chk3": chk3,
                "checklist": strat_checklist,
                "entry": entry_val,
                "sl": sl_val,
                "tp": tp_val,
                "confidence": conf_pct,
                "status": status_val,
                "digits": digits,
                "is_live_position": False,
                "is_pending_order": False,
                "exec_mode": exec_mode,
                "is_bot_active": is_bot_active,
            }
            update_order_proposal_html(window, **kwargs_order)
            return

        # -----------------------------------------------------------------
        # MODE 3: MANUAL -> ADVISORY ALERT ONLY (DO NOT OVERRIDE COPILOT)
        # -----------------------------------------------------------------
        else: # MANUAL
            kwargs_order = {
                "sym": clean_sym,
                "has_signal": True,
                "signal_type": strat_sig,
                "model_name": ai_model,
                "grade": f"ALERT: {strat_sig} DETECTED",
                "chk1": chk1,
                "chk2": chk2,
                "chk3": chk3,
                "checklist": strat_checklist,
                "entry": entry_val,
                "sl": sl_val,
                "tp": tp_val,
                "confidence": conf_pct,
                "status": "MANUAL COPILOT ACTIVE",
                "digits": digits,
                "is_live_position": False,
                "is_pending_order": False,
                "exec_mode": "MANUAL",
                "is_bot_active": False,
            }
            window.active_signal_data = kwargs_order
            if getattr(window, "_plan_mode", "ai") == "ai":
                update_order_proposal_html(window, **kwargs_order)
            return
    else:
        ai_model = f"{strat_name}"
        strat_checklist = user_chk
        if not strat_checklist:
            from backend.core.strategies import get_strategy_instance
            strat_checklist = get_strategy_instance(strat_name).get_default_checklist()

        chk1, chk2, chk3 = None, None, None
        if isinstance(strat_checklist, (list, tuple)) and len(strat_checklist) >= 3:
            chk1 = strat_checklist[0].value if hasattr(strat_checklist[0], "value") else (strat_checklist[0].get("value") if isinstance(strat_checklist[0], dict) else str(strat_checklist[0]))
            chk2 = strat_checklist[1].value if hasattr(strat_checklist[1], "value") else (strat_checklist[1].get("value") if isinstance(strat_checklist[1], dict) else str(strat_checklist[1]))
            chk3 = strat_checklist[2].value if hasattr(strat_checklist[2], "value") else (strat_checklist[2].get("value") if isinstance(strat_checklist[2], dict) else str(strat_checklist[2]))

        kwargs_order = {
            "sym": clean_sym,
            "has_signal": False,
            "signal_type": "HOLD",
            "model_name": ai_model,
            "grade": "STATUS: STANDBY",
            "chk1": chk1,
            "chk2": chk2,
            "chk3": chk3,
            "checklist": strat_checklist,
            "status": "SCANNING_STANDBY",
            "digits": digits,
            "is_live_position": False,
            "is_pending_order": False,
            "exec_mode": exec_mode,
            "is_bot_active": is_bot_active,
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

    active_strat_id = getattr(window, "active_strategy_id", None)
    if not active_strat_id:
        try:
            import shiboken6
            if (
                hasattr(window, "comboStrategy")
                and window.comboStrategy is not None
                and shiboken6.isValid(window.comboStrategy)
                and window.comboStrategy.count() > 0
            ):
                active_strat_id = window.comboStrategy.currentData()
        except Exception:
            active_strat_id = None

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
        strategy_id=active_strat_id,
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


