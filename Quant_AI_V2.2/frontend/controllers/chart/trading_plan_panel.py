from backend.infrastructure.brokers.mt5_safe import mt5
"""
Trading Plan, Order Proposal Cards, and Playbook Theme Engine
"""

import os
import time
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from PySide6 import QtCore, QtGui
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QFrame, QLabel, QHBoxLayout, QVBoxLayout, QGridLayout, QPushButton,
    QWidget, QProgressBar, QSizePolicy, QDoubleSpinBox, QLineEdit,
    QMessageBox, QComboBox
)
from loguru import logger
import pyqtgraph as pg
from backend.core.market_state_store import MarketStateStore



def get_symbol_multiplier(symbol: str, info=None) -> float:
    tick_val = getattr(info, "trade_tick_value", None)
    tick_sz = getattr(info, "trade_tick_size", None)
    if isinstance(tick_val, (int, float)) and isinstance(tick_sz, (int, float)) and tick_sz > 0 and tick_val > 0:
        return float(tick_val / tick_sz)
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


def get_symbol_pip_unit(symbol: str, digits: int = 2, point: float = 0.01) -> float:
    """Return price movement equivalent to 1 pip."""
    s = (symbol or "XAUUSD").upper().split(".")[0].replace("/", "")
    if "BTC" in s or "ETH" in s:
        return 1.0
    if "XAU" in s or "GOLD" in s or "XAG" in s:
        return 0.10
    if any(idx in s for idx in ["US30", "NAS100", "SPX500", "GER40", "DAX", "US100", "US500", "DJ30"]):
        return 1.0
    if "JPY" in s:
        return 0.01
    return (point * 10) if digits in (3, 5) else (point if point > 0 else 0.0001)


def classify_market_asset_class(symbol: str, info=None) -> str:
    """
    Classify financial symbol into universal institutional asset classes
    (Forex, Crypto, Commodities/Metals, Indices, Equities) via MT5 broker path and symbol patterns.
    Compliant with QuantConnect LEAN and CFA Market Microstructure standards.
    """
    path = getattr(info, "path", "").lower() if info else ""
    sym_u = (symbol or "").upper().split(".")[0].replace("/", "")

    if "crypto" in path or any(c in sym_u for c in ["BTC", "ETH", "SOL", "XRP", "DOGE", "BNB", "ADA", "LTC"]):
        return "crypto"
    if any(k in path for k in ["index", "indic"]) or any(c in sym_u for c in ["US30", "NAS", "SPX", "GER", "DAX", "UK100", "JP225", "DJ30", "US500", "US100"]):
        return "indices"
    if any(k in path for k in ["metal", "commodit", "energy", "oil"]) or any(c in sym_u for c in ["XAU", "GOLD", "XAG", "SILVER", "WTI", "BRENT", "XBR", "XTI"]):
        return "commodities"
    if any(k in path for k in ["stock", "equity", "share"]):
        return "equities"
    return "forex"


def calculate_safe_spread_allowance(symbol: str, info=None, current_price: float = 0.0) -> tuple[int, float]:
    """
    Computes universal institutional spread thresholds across multi-asset universes.
    Returns: (safe_points_allowance: int, max_safe_basis_points: float)
    
    References:
    - QuantConnect LEAN SpreadExecutionModel (Relative Spread BPS)
    - Sierra Chart & MQL5 Microstructure Reference (Normalized Volatility BPS)
    - Almgren-Chriss (2000) Optimal Execution of Portfolio Transactions
    """
    asset_class = classify_market_asset_class(symbol, info)
    
    bps_limits = {
        "forex": 8.0,         # 0.08%
        "indices": 10.0,      # 0.10%
        "commodities": 12.0,  # 0.12%
        "equities": 20.0,     # 0.20%
        "crypto": 35.0,       # 0.35%
    }
    max_bps = bps_limits.get(asset_class, 25.0)
    
    pt = float(info.point) if hasattr(info, "point") and isinstance(info.point, (int, float)) and info.point > 0 else 0.01
    dig = info.digits if isinstance(getattr(info, "digits", None), (int, float)) else 2
    
    if current_price and current_price > 0 and pt > 0:
        safe_points = int((current_price * (max_bps / 10000.0)) / pt)
    else:
        fallback_points = {
            "forex": 35,
            "indices": 250,
            "commodities": 45 if dig == 2 else 450,
            "equities": 50,
            "crypto": 6000,
        }
        safe_points = fallback_points.get(asset_class, 50)
        
    return max(safe_points, 10), max_bps


def calculate_manual_quant_lot(symbol: str, sl_points: float, risk_pct: float = 1.0, balance: float = None):
    """Calculates dynamic institutional lot size adhering to capital preservation rules across all asset classes."""
    if balance is None or balance <= 0:
        acc = mt5.account_info() if mt5.terminal_info() is not None else None
        balance = float(acc.balance) if acc and acc.balance > 0 else 10000.0

    target_risk_dlr = balance * (risk_pct / 100.0)
    if sl_points <= 0.00001:
        return 0.0, target_risk_dlr

    info = mt5.symbol_info(symbol) if mt5.terminal_info() is not None else None
    mult = get_symbol_multiplier(symbol, info)

    clean_sym = (symbol or "XAUUSD").upper().split(".")[0].replace("/", "")
    v_min = getattr(info, "volume_min", None)
    v_max = getattr(info, "volume_max", None)
    v_step = getattr(info, "volume_step", None)

    vol_min = float(v_min) if isinstance(v_min, (int, float)) and v_min > 0 else 0.01
    vol_max = float(v_max) if isinstance(v_max, (int, float)) and v_max > 0 else (
        50.0 if ("BTC" in clean_sym or "ETH" in clean_sym) else (
            100.0 if ("XAU" in clean_sym or "GOLD" in clean_sym) else 50.0
        )
    )
    vol_step = float(v_step) if isinstance(v_step, (int, float)) and v_step > 0 else 0.01

    from decimal import Decimal, ROUND_FLOOR
    if not __import__('math').isfinite(float(risk_pct)) or risk_pct<=0:
        return 0.0,target_risk_dlr
    step=Decimal(str(vol_step))
    calc_lot=float((Decimal(str(target_risk_dlr/(sl_points*mult)))/step).to_integral_value(rounding=ROUND_FLOOR)*step)
    lot=min(calc_lot,vol_max) if calc_lot>=vol_min else 0.0

    # Free Margin & Leverage Cap: Prevent MT5 retcode 10019 (NO_MONEY)
    acc = mt5.account_info() if mt5.terminal_info() is not None else None
    if acc and getattr(acc, "margin_free", 0.0) and float(acc.margin_free) > 0:
        free_m = float(acc.margin_free)
        lev = float(getattr(acc, "leverage", 100) or 100)
        tick = mt5.symbol_info_tick(symbol) if mt5.terminal_info() is not None else None
        ref_price = float(tick.ask if tick else (getattr(info, "bid", 2650.0) or 2650.0))
        if ref_price > 0 and mult > 0 and lev > 0:
            max_affordable_lot = (free_m * 0.90 * lev) / (ref_price * mult)
            if vol_step > 0:
                max_affordable_lot = round(max_affordable_lot / vol_step) * vol_step
            if max_affordable_lot >= vol_min:
                lot = min(lot, max_affordable_lot)

    return lot, target_risk_dlr


def clear_manual_chart_lines(window):
    """Safely remove and hide preview/draft order lines from the chart."""
    for line_name in ("line_order_entry", "line_order_sl", "line_order_tp"):
        if hasattr(window, line_name):
            l_obj = getattr(window, line_name)
            if l_obj is not None:
                try:
                    l_obj.setVisible(False)
                except Exception:
                    pass
                if hasattr(window, "plot_widget") and window.plot_widget:
                    try:
                        window.plot_widget.removeItem(l_obj)
                    except Exception:
                        pass


def resolve_strategy_model_name(window, model_name: Optional[str] = None) -> str:
    """Resolve human-readable model name based on active strategy contract."""
    candidate = model_name.strip() if (model_name and isinstance(model_name, str)) else None
    if candidate and candidate not in ("Quantitative Strategy", "--"):
        try:
            from backend.core.strategies import get_strategy_instance
            strat = get_strategy_instance(candidate)
            if hasattr(strat, "name") and strat.name:
                return str(strat.name)
        except Exception:
            pass
        return candidate

    active_id = getattr(window, "active_strategy_id", None)
    if active_id:
        try:
            from backend.core.strategies import get_strategy_instance
            strat = get_strategy_instance(active_id)
            return getattr(strat, "name", "ICT Zones Pro v4.2")
        except Exception:
            pass

    try:
        import shiboken6
        if hasattr(window, "comboStrategy") and window.comboStrategy is not None and shiboken6.isValid(window.comboStrategy):
            cur_data = window.comboStrategy.currentData()
            cur_text = window.comboStrategy.currentText()
            from backend.core.strategies import get_strategy_instance
            strat = get_strategy_instance(cur_data or cur_text)
            return getattr(strat, "name", cur_text.split("(")[0].strip())
    except Exception:
        pass

    try:
        from backend.core.strategies import get_strategy_instance
        strat = get_strategy_instance()
        return getattr(strat, "name", "ICT Zones Pro v4.2")
    except Exception:
        pass

    return "ICT Zones Pro v4.2"


def update_strategy_checklist_ui(
    window,
    model_name: Optional[str] = None,
    chk1: Optional[str] = None,
    chk2: Optional[str] = None,
    chk3: Optional[str] = None,
    is_active: bool = False,
    checklist: Optional[List[Any]] = None,
):
    """
    Polymorphic checklist renderer complying with Open-Closed Principle (OCP).
    Dynamically renders checklist items supplied by the active BaseStrategy instance.
    """
    from backend.core.strategies import get_strategy_instance, ChecklistItem, ChecklistStatus

    items: List[ChecklistItem] = []

    # 1. If explicit structured checklist items were passed, use them directly
    if checklist and isinstance(checklist, (list, tuple)) and len(checklist) > 0:
        for it in checklist:
            if isinstance(it, ChecklistItem):
                items.append(it)
            elif isinstance(it, dict):
                s_raw = it.get("status", "PENDING")
                s_val = ChecklistStatus(s_raw) if s_raw in ChecklistStatus.__members__ else ChecklistStatus.PENDING
                items.append(ChecklistItem(
                    key=it.get("key", "Condition"),
                    value=it.get("value", "--"),
                    status=s_val
                ))
            elif isinstance(it, str):
                items.append(ChecklistItem(key="Condition", value=it, status=ChecklistStatus.PENDING))

    # 2. If no structured checklist passed, query the strategy instance polymorphic contract
    if not items or len(items) < 3:
        strat = get_strategy_instance(model_name)
        if is_active and hasattr(strat, "get_active_checklist"):
            defaults = strat.get_active_checklist()
        else:
            defaults = strat.get_default_checklist()

        # If individual string overrides were passed (e.g. from existing unit tests), apply them
        override_vals = [chk1, chk2, chk3]
        items = []
        for idx, def_item in enumerate(defaults[:3]):
            val = override_vals[idx] if (idx < len(override_vals) and override_vals[idx] is not None) else def_item.value
            items.append(ChecklistItem(
                key=def_item.key,
                value=val,
                status=ChecklistStatus.PASSED if is_active else def_item.status
            ))

    # 3. Dynamic UI Render into Card 1 generic rows
    for i in range(1, 4):
        idx = i - 1
        item = items[idx] if idx < len(items) else ChecklistItem(key=f"Rule {i}", value="--", status=ChecklistStatus.PENDING)

        k_lbl = getattr(window, f"lblKey_lblChk{i}Val", None)
        v_lbl = getattr(window, f"lblChk{i}Val", None)

        if k_lbl is not None:
            k_lbl.setText(item.key)
        if v_lbl is not None:
            v_lbl.setText(item.value)


def update_order_proposal_html(
    window,
    sym=None,
    entry=None,
    sl=None,
    tp=None,
    risk_dlr=None,
    risk_pct=None,
    reward_dlr=None,
    rr_ratio=None,
    status="WAITING OPERATOR APPROVAL",
    is_dark=None,
    spread=None,
    htf_bias=None,
    confidence=None,
    digits=None,
    model_name=None,
    grade=None,
    chk1=None,
    chk2=None,
    chk3=None,
    has_signal=False,
    signal_type="BUY",
    is_live_position=False,
    live_ticket=None,
    live_profit=0.0,
    live_volume=None,
    is_pending_order=False,
    pending_ticket=None,
    exec_mode="MANUAL",
    is_bot_active=False,
    checklist=None,
    calc_lot=None,
    **kwargs,
):
    """Render institutional Radar Matrix and Order Proposal Ticket with WCAG AAA contrast matching theme."""
    if calc_lot is not None and live_volume is None:
        live_volume = calc_lot
    raw_sym = sym or getattr(window, "current_sym", "XAUUSD") or "XAUUSD"
    clean_sym = raw_sym.split("\n")[0].strip()
    active_chart_sym = getattr(window, "current_sym", "").split("\n")[0].strip()

    if not hasattr(window, "active_signals_by_symbol"):
        window.active_signals_by_symbol = {}

    # If the call is for a different symbol than currently displayed on the chart canvas,
    # isolate it into MarketStateStore and active_signals_by_symbol without contaminating active chart UI
    if active_chart_sym and clean_sym.upper() != active_chart_sym.upper():
        store = MarketStateStore.get_instance()
        st = store.update_state(
            clean_sym,
            has_signal=has_signal,
            signal_type=signal_type,
            entry=entry,
            sl=sl,
            tp=tp,
            risk_dlr=risk_dlr,
            reward_dlr=reward_dlr,
            risk_pct=risk_pct,
            rr_ratio=rr_ratio,
            is_live_position=is_live_position,
            live_ticket=live_ticket,
            live_volume=live_volume,
            live_profit=live_profit,
            is_pending_order=is_pending_order,
            pending_ticket=pending_ticket,
            model_name=model_name,
            grade=grade,
            confidence=confidence,
            exec_mode=exec_mode,
            status=status,
            chk1=chk1,
            chk2=chk2,
            chk3=chk3,
            checklist=checklist,
            digits=digits,
        )
        window.active_signals_by_symbol[clean_sym] = st.to_dict()
        return

    info = mt5.symbol_info(clean_sym)
    if digits is None:
        digits = info.digits if info else (2 if (entry or 100) > 10 else 5)

    if is_dark is None:
        is_dark = getattr(window, "is_dark_theme", False)

    # 0. CHẾ ĐỘ THỦ CÔNG: KHÔNG CHO PHÉP TÍN HIỆU AI NỀN GHI ĐÈ GIAO DIỆN MANUAL COPILOT
    if getattr(window, "_plan_mode", "ai") == "manual":
        # Cache incoming background AI signals separately without contaminating active UI state
        if has_signal:
            sig_background = {
                "sym": clean_sym,
                "has_signal": True,
                "signal_type": signal_type,
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "is_live_position": is_live_position,
                "live_ticket": live_ticket,
                "live_volume": live_volume,
                "live_profit": live_profit,
                "model_name": model_name,
                "grade": grade,
                "confidence": confidence,
                "exec_mode": exec_mode,
                "status": status,
                "checklist": checklist,
            }
            window.active_signals_by_symbol[clean_sym] = sig_background
        elif clean_sym not in window.active_signals_by_symbol or not window.active_signals_by_symbol[clean_sym].get("has_signal"):
            store = MarketStateStore.get_instance()
            st = store.update_state(
                clean_sym,
                has_signal=False,
                signal_type=signal_type or "HOLD",
                model_name=model_name,
                grade=grade,
                chk1=chk1,
                chk2=chk2,
                chk3=chk3,
                checklist=checklist,
                status=status,
                digits=digits,
            )
            window.active_signals_by_symbol[clean_sym] = st.to_dict()
        return

    # 1. TRƯỜNG HỢP: KHÔNG CÓ TÍN HIỆU THỰC TẾ (HOLD / CHỜ SETUP)
    if not has_signal or entry is None or sl is None:
        window.order_proposal_active = False
        window.is_live_position = False
        window.live_ticket = None
        window.is_pending_order = False
        window.pending_ticket = None

        store = MarketStateStore.get_instance()
        st = store.update_state(
            clean_sym,
            has_signal=False,
            signal_type=signal_type or "HOLD",
            model_name=model_name,
            grade=grade,
            chk1=chk1,
            chk2=chk2,
            chk3=chk3,
            checklist=checklist,
            status=status if (status and status != "WAITING OPERATOR APPROVAL") else None,
            digits=digits,
            exec_mode=exec_mode,
            is_bot_active=is_bot_active,
        )
        standby_payload = st.to_dict()
        window.active_signal_data = standby_payload
        window.active_signals_by_symbol[clean_sym] = standby_payload

        # Gỡ bỏ toàn bộ đường lệnh ảo khỏi biểu đồ
        clear_manual_chart_lines(window)

        # Card 1: Mô hình thiết lập (Standby)
        resolved_model = resolve_strategy_model_name(window, st.model_name)
        if hasattr(window, "lblModelSubtitle") and window.lblModelSubtitle:
            window.lblModelSubtitle.setText("SETUP MODEL")
        if hasattr(window, "lblModelName") and window.lblModelName:
            window.lblModelName.setText(resolved_model)
        if hasattr(window, "lblModelGrade") and window.lblModelGrade:
            window.lblModelGrade.setText(st.grade or "STATUS: STANDBY")
            window.lblModelGrade.setStyleSheet(
                "background-color: #1e293b; color: #94a3b8; border: 1px solid #334155; "
                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 1px 5px;"
            )
        update_strategy_checklist_ui(window, resolved_model, st.chk1, st.chk2, st.chk3, is_active=False, checklist=st.checklist)

        # Card 2: Lệnh và Quản trị rủi ro (Chưa có lệnh)
        if hasattr(window, "lblOrderBudgetTitle") and window.lblOrderBudgetTitle:
            window.lblOrderBudgetTitle.setText("ORDER & RISK BUDGET")
        if hasattr(window, "lblOrderTypeBadge") and window.lblOrderTypeBadge:
            window.lblOrderTypeBadge.setText("NO ORDER")
            window.lblOrderTypeBadge.setStyleSheet(
                "background-color: #1e293b; color: #64748b; border: 1px solid #334155; "
                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 1px 5px;"
            )
        if hasattr(window, "lblEntryVal") and window.lblEntryVal:
            window.lblEntryVal.setText("--")
        if hasattr(window, "lblSLVal") and window.lblSLVal:
            window.lblSLVal.setText("--")
        if hasattr(window, "lblTPVal") and window.lblTPVal:
            window.lblTPVal.setText("--")
        if hasattr(window, "lblSizeVal") and window.lblSizeVal:
            window.lblSizeVal.setText("--")

        # Card 3: Cổng phê duyệt lệnh (Vô hiệu hóa)
        if hasattr(window, "lblGateExpiryTitle") and window.lblGateExpiryTitle:
            window.lblGateExpiryTitle.setText("EXPIRATION")
        if hasattr(window, "lblGateExpiryTime") and window.lblGateExpiryTime:
            window.lblGateExpiryTime.setText("--")
        if hasattr(window, "barSignalExpiry") and window.barSignalExpiry:
            window.barSignalExpiry.setValue(0)
        if hasattr(window, "btnApproveOrder") and window.btnApproveOrder:
            window.btnApproveOrder.setText("AWAITING STRATEGY SIGNAL")
            window.btnApproveOrder.setEnabled(False)
            window.btnApproveOrder.setCursor(Qt.ArrowCursor)
        if hasattr(window, "btnModifyOrder") and window.btnModifyOrder:
            window.btnModifyOrder.setEnabled(False)
        if hasattr(window, "btnDiscardOrder") and window.btnDiscardOrder:
            window.btnDiscardOrder.setText("DISCARD")
            window.btnDiscardOrder.setEnabled(False)

        if hasattr(window, "_signal_expiry_timer") and window._signal_expiry_timer is not None:
            try:
                window._signal_expiry_timer.stop()
            except Exception:
                pass

        if hasattr(window, "cardSetupModel"):
            apply_playbook_cards_theme(window, is_dark)
        return

    # 2. TRƯỜNG HỢP: CÓ TÍN HIỆU THỰC TẾ HOẶC CÓ VỊ THẾ LIVE
    if is_live_position:
        try:
            if mt5.terminal_info() is not None:
                p_list = None
                if live_ticket:
                    try:
                        p_cand = mt5.positions_get(ticket=int(live_ticket))
                        if p_cand and len(p_cand) > 0:
                            # CRITICAL: Verify ticket actually belongs to clean_sym
                            cand_s = getattr(p_cand[0], "symbol", None)
                            if not isinstance(cand_s, str) or not cand_s or cand_s.split(".")[0].upper() == clean_sym.split(".")[0].upper():
                                p_list = p_cand
                            else:
                                live_ticket = None
                                is_live_position = False
                    except Exception:
                        p_list = None
                if not p_list:
                    p_list = mt5.positions_get(symbol=clean_sym)
                if p_list and len(p_list) > 0:
                    pos = p_list[0]
                    # Verify symbol match
                    pos_s = getattr(pos, "symbol", None)
                    if isinstance(pos_s, str) and pos_s and pos_s.split(".")[0].upper() != clean_sym.split(".")[0].upper():
                        pos = None
                        p_list = None
                        is_live_position = False
                        live_ticket = None
                    else:
                        live_ticket = pos.ticket
                        if live_volume is None or live_volume <= 0:
                            live_volume = float(pos.volume)
                        live_profit = float(pos.profit)
                        if entry is None or entry == 0.0:
                            entry = float(pos.price_open)
                        if (sl is None or sl == 0.0) and pos.sl > 0:
                            sl = float(pos.sl)
                        if (tp is None or tp == 0.0) and pos.tp > 0:
                            tp = float(pos.tp)
                else:
                    is_live_position = False
                    live_ticket = None
        except Exception:
            pass

    window.order_proposal_active = True
    window.is_live_position = is_live_position
    window.live_ticket = live_ticket
    window.is_pending_order = is_pending_order
    window.pending_ticket = pending_ticket
    sl_pts = abs(entry - sl) if sl and sl > 0 else 0.0
    tp_pts = abs(tp - entry) if tp and tp > 0 else (sl_pts * 2.0 if sl_pts > 0 else 0.0)
    if tp is None and sl_pts > 0:
        tp = entry + (sl_pts * 2.0) if signal_type == "BUY" else entry - (sl_pts * 2.0)
    if rr_ratio is None:
        rr_ratio = round(tp_pts / sl_pts, 1) if sl_pts > 0 else 2.0

    # Lay so du thuc te tu MT5
    acc_info = mt5.account_info() if mt5.terminal_info() is not None else None
    real_balance = acc_info.balance if acc_info and acc_info.balance > 0 else 10000.0
    risk_pct_val = risk_pct if risk_pct is not None else 1.0

    sym_mult = get_symbol_multiplier(clean_sym, info)

    # Tinh toan khoi luong lot chuan rui ro
    if is_live_position or is_pending_order:
        calc_lot = float(live_volume) if live_volume is not None else 0.10
        risk_dlr = round(sl_pts * calc_lot * sym_mult, 2)
        reward_dlr = round(tp_pts * calc_lot * sym_mult, 2)
    else:
        calc_lot, _ = calculate_manual_quant_lot(clean_sym, sl_pts, risk_pct_val, balance=real_balance)
        risk_dlr = round(sl_pts * calc_lot * sym_mult, 2)
        reward_dlr = round(tp_pts * calc_lot * sym_mult, 2)
    risk_pct = round((risk_dlr / real_balance) * 100.0, 1) if real_balance > 0 else 1.0

    store = MarketStateStore.get_instance()
    st = store.update_state(
        clean_sym,
        has_signal=True,
        signal_type=signal_type,
        entry=entry,
        sl=sl,
        tp=tp,
        lot=calc_lot,
        risk_dlr=risk_dlr,
        reward_dlr=reward_dlr,
        risk_pct=risk_pct,
        rr_ratio=rr_ratio,
        is_live_position=is_live_position,
        live_ticket=live_ticket,
        live_volume=calc_lot if is_live_position else None,
        live_profit=live_profit,
        is_pending_order=is_pending_order,
        pending_ticket=pending_ticket,
        model_name=model_name,
        grade=grade,
        confidence=confidence,
        status=status,
        chk1=chk1,
        chk2=chk2,
        chk3=chk3,
        checklist=checklist,
        digits=digits,
        exec_mode=exec_mode,
        is_bot_active=is_bot_active,
    )
    sig_payload = st.to_dict()
    window.active_signal_data = sig_payload
    window.active_signals_by_symbol[clean_sym] = sig_payload

    # Tên hành động hiển thị
    if is_live_position:
        order_action_name = f"{signal_type} #{live_ticket}"
    elif is_pending_order:
        order_action_name = f"PENDING #{pending_ticket}"
    else:
        order_action_name = "BUY LIMIT" if signal_type == "BUY" else "SELL LIMIT"

    # Cập nhật đường ngang trên biểu đồ nến (Institutional Visualizer)
    try:
        is_dark_val = getattr(window, "is_dark_theme", False) if is_dark is None else is_dark
        bull_c = "#22c55e" if is_dark_val else "#15803D"
        bear_c = "#ef4444" if is_dark_val else "#B91C1C"
        dir_c = bull_c if signal_type == "BUY" else bear_c

        if is_live_position or is_pending_order:
            # Active broker positions and pending orders are rendered exclusively by sync_chart_orders
            if hasattr(window, "line_order_entry") and window.line_order_entry:
                window.line_order_entry.setVisible(False)
            if hasattr(window, "line_order_sl") and window.line_order_sl:
                window.line_order_sl.setVisible(False)
            if hasattr(window, "line_order_tp") and window.line_order_tp:
                window.line_order_tp.setVisible(False)
            if hasattr(window, "sync_chart_orders"):
                try:
                    window.sync_chart_orders()
                except Exception:
                    pass
        else:
            # Unapproved AI Proposal draft preview
            order_w = 1.2
            if hasattr(window, "line_order_entry") and window.line_order_entry:
                window.line_order_entry.setValue(entry)
                window.line_order_entry.setPen(pg.mkPen(color=dir_c, width=order_w, style=Qt.DashLine))
                window.line_order_entry.setMovable(False)
                window.line_order_entry.setVisible(True)
                if hasattr(window.line_order_entry, "label") and window.line_order_entry.label:
                    window.line_order_entry.label.setFormat(f"{order_action_name} | {calc_lot:.2f}L @ {entry:.{digits}f} (DRAFT)")
                    window.line_order_entry.label.setColor("#f8fafc")
                    window.line_order_entry.label.fill = pg.mkBrush(15, 23, 42, 235)
                    window.line_order_entry.label.border = pg.mkPen(color=dir_c, width=1.0)
                    window.line_order_entry.label.setPosition(0.92)
                    window.line_order_entry.label.setFont(pg.Qt.QtGui.QFont("Consolas", 8))
                if hasattr(window, "plot_widget"):
                    try:
                        if window.line_order_entry not in window.plot_widget.items():
                            window.plot_widget.addItem(window.line_order_entry, ignoreBounds=True)
                    except Exception:
                        pass

            if hasattr(window, "line_order_sl") and window.line_order_sl:
                if sl and sl > 0:
                    window.line_order_sl.setValue(sl)
                    window.line_order_sl.setPen(pg.mkPen(color=bear_c, width=1.0, style=Qt.DashLine))
                    window.line_order_sl.setMovable(True)
                    window.line_order_sl.setVisible(True)
                    if hasattr(window.line_order_sl, "label") and window.line_order_sl.label:
                        window.line_order_sl.label.setFormat(f"SL (DRAFT) | {sl:.{digits}f}")
                        window.line_order_sl.label.setColor("#f8fafc")
                        window.line_order_sl.label.fill = pg.mkBrush(15, 23, 42, 235)
                        window.line_order_sl.label.border = pg.mkPen(color=bear_c, width=1.0)
                        window.line_order_sl.label.setPosition(0.84)
                        window.line_order_sl.label.setFont(pg.Qt.QtGui.QFont("Consolas", 8))
                    if hasattr(window, "plot_widget"):
                        try:
                            if window.line_order_sl not in window.plot_widget.items():
                                window.plot_widget.addItem(window.line_order_sl, ignoreBounds=True)
                        except Exception:
                            pass
                else:
                    window.line_order_sl.setVisible(False)
                    if hasattr(window, "plot_widget") and window.plot_widget:
                        try:
                            window.plot_widget.removeItem(window.line_order_sl)
                        except Exception:
                            pass

            if hasattr(window, "line_order_tp") and window.line_order_tp:
                if tp and tp > 0:
                    window.line_order_tp.setValue(tp)
                    window.line_order_tp.setPen(pg.mkPen(color=bull_c, width=1.0, style=Qt.DashLine))
                    window.line_order_tp.setMovable(True)
                    window.line_order_tp.setVisible(True)
                    if hasattr(window.line_order_tp, "label") and window.line_order_tp.label:
                        window.line_order_tp.label.setFormat(f"TP (DRAFT) | {tp:.{digits}f}")
                        window.line_order_tp.label.setColor("#f8fafc")
                        window.line_order_tp.label.fill = pg.mkBrush(15, 23, 42, 235)
                        window.line_order_tp.label.border = pg.mkPen(color=bull_c, width=1.0)
                        window.line_order_tp.label.setPosition(0.76)
                        window.line_order_tp.label.setFont(pg.Qt.QtGui.QFont("Consolas", 8))
                    if hasattr(window, "plot_widget"):
                        try:
                            if window.line_order_tp not in window.plot_widget.items():
                                window.plot_widget.addItem(window.line_order_tp, ignoreBounds=True)
                        except Exception:
                            pass
                else:
                    window.line_order_tp.setVisible(False)
                    if hasattr(window, "plot_widget") and window.plot_widget:
                        try:
                            window.plot_widget.removeItem(window.line_order_tp)
                        except Exception:
                            pass
    except Exception as e:
        logger.error(f"[TradingPlanPanel] Failed to update chart order lines: {e}")

    # Card 1: Mô hình thiết lập (Active)
    resolved_model = resolve_strategy_model_name(window, model_name)
    if hasattr(window, "lblModelSubtitle") and window.lblModelSubtitle:
        if is_live_position:
            window.lblModelSubtitle.setText(f"POSITION IN MARKET (#{live_ticket})" if live_ticket else "POSITION IN MARKET")
        elif is_pending_order:
            window.lblModelSubtitle.setText(f"PENDING ORDER (#{pending_ticket})" if pending_ticket else "PENDING ORDER")
        else:
            window.lblModelSubtitle.setText("SETUP MODEL")
    if hasattr(window, "lblModelName") and window.lblModelName:
        window.lblModelName.setText(resolved_model)
    if hasattr(window, "lblModelGrade") and window.lblModelGrade:
        window.lblModelGrade.setText(grade or f"CONFIDENCE: {confidence or '85%'}")
        badge_bg = "#0d2818" if is_dark else "#f0fdf4"
        badge_border = "#272d3b" if is_dark else "#cbd5e1"
        badge_text = "#16a34a" if is_dark else "#15803d"
        window.lblModelGrade.setStyleSheet(f"background-color: {badge_bg}; color: {badge_text}; border: 1px solid {badge_border}; font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 1px 5px;")
    update_strategy_checklist_ui(window, resolved_model, chk1, chk2, chk3, is_active=True, checklist=checklist)

    # Card 2: Lệnh và Quản trị rủi ro (Active)
    if hasattr(window, "lblOrderBudgetTitle") and window.lblOrderBudgetTitle:
        window.lblOrderBudgetTitle.setText("LIVE POSITION & RISK" if is_live_position else ("PENDING ORDER & RISK" if is_pending_order else "ORDER & RISK BUDGET"))
    if hasattr(window, "lblOrderTypeBadge") and window.lblOrderTypeBadge:
        window.lblOrderTypeBadge.setText(order_action_name)
        if signal_type == "BUY":
            b_bg = "#0d2818" if is_dark else "#f0fdf4"
            b_border = "#272d3b" if is_dark else "#cbd5e1"
            b_text = "#16a34a" if is_dark else "#15803d"
        else:
            b_bg = "#271214" if is_dark else "#fef2f2"
            b_border = "#272d3b" if is_dark else "#cbd5e1"
            b_text = "#dc2626" if is_dark else "#b91c1c"
        window.lblOrderTypeBadge.setStyleSheet(f"background-color: {b_bg}; color: {b_text}; border: 1px solid {b_border}; font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 1px 5px;")
    if hasattr(window, "lblEntryVal") and window.lblEntryVal:
        window.lblEntryVal.setText(f"{entry:.{digits}f}")
    if hasattr(window, "lblSLVal") and window.lblSLVal:
        if is_live_position:
            window.lblSLVal.setText(f"{sl:.{digits}f}  (LIVE)" if sl and sl > 0 else "NO SL")
        else:
            window.lblSLVal.setText(f"{sl:.{digits}f}  (-${risk_dlr:.2f} | -{risk_pct:.1f}%)")
    if hasattr(window, "lblTPVal") and window.lblTPVal:
        if is_live_position:
            window.lblTPVal.setText(f"{tp:.{digits}f}  (LIVE)" if tp and tp > 0 else "NO TP")
        else:
            window.lblTPVal.setText(f"{tp:.{digits}f}  (+${reward_dlr:.2f} | +{rr_ratio:.1f}R)")
    if hasattr(window, "lblSizeVal") and window.lblSizeVal:
        if is_live_position:
            pnl_str = f"+${live_profit:.2f}" if live_profit >= 0 else f"-${abs(live_profit):.2f}"
            window.lblSizeVal.setText(f"{calc_lot:.2f} LOTS (PNL: {pnl_str})")
        else:
            window.lblSizeVal.setText(f"{calc_lot:.2f} LOTS (${risk_dlr:.2f})")

    # Card 3: Cổng phê duyệt lệnh (Active)
    if is_live_position:
        if hasattr(window, "lblGateExpiryTitle") and window.lblGateExpiryTitle:
            window.lblGateExpiryTitle.setText("EXECUTION STATE")
        if hasattr(window, "lblGateExpiryTime") and window.lblGateExpiryTime:
            window.lblGateExpiryTime.setText("LIVE")
        if hasattr(window, "barSignalExpiry") and window.barSignalExpiry:
            window.barSignalExpiry.setRange(0, 100)
            window.barSignalExpiry.setValue(100)
        if hasattr(window, "btnApproveOrder") and window.btnApproveOrder:
            if is_bot_active or exec_mode == "FULL-AUTO":
                ts_on = False
                try:
                    cfg_p = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "config", "settings.json")
                    if os.path.exists(cfg_p):
                        with open(cfg_p, "r", encoding="utf-8") as f_cfg:
                            ts_on = json.load(f_cfg).get("enable_trailing_stop", False)
                except Exception:
                    pass
                window.btnApproveOrder.setText("BOT AUTO MANAGING (TRAILING SL)" if ts_on else "BOT AUTO MANAGING (TARGET TP/SL)")
            else:
                window.btnApproveOrder.setText("POSITION IN MARKET")
            window.btnApproveOrder.setEnabled(False)
            window.btnApproveOrder.setCursor(Qt.ArrowCursor)
        if hasattr(window, "btnModifyOrder") and window.btnModifyOrder:
            window.btnModifyOrder.setEnabled(True)
        if hasattr(window, "btnDiscardOrder") and window.btnDiscardOrder:
            window.btnDiscardOrder.setText("CLOSE POSITION")
            window.btnDiscardOrder.setEnabled(True)
            window.btnDiscardOrder.setCursor(Qt.PointingHandCursor)
        if hasattr(window, "_signal_expiry_timer") and window._signal_expiry_timer:
            try:
                window._signal_expiry_timer.stop()
            except Exception:
                pass
    elif is_pending_order:
        if hasattr(window, "lblGateExpiryTitle") and window.lblGateExpiryTitle:
            window.lblGateExpiryTitle.setText("EXECUTION STATE")
        if hasattr(window, "lblGateExpiryTime") and window.lblGateExpiryTime:
            window.lblGateExpiryTime.setText("PENDING")
        if hasattr(window, "barSignalExpiry") and window.barSignalExpiry:
            window.barSignalExpiry.setRange(0, 100)
            window.barSignalExpiry.setValue(100)
        if hasattr(window, "btnApproveOrder") and window.btnApproveOrder:
            window.btnApproveOrder.setText(f"ORDER PLACED #{pending_ticket}")
            window.btnApproveOrder.setEnabled(False)
            window.btnApproveOrder.setCursor(Qt.ArrowCursor)
        if hasattr(window, "btnModifyOrder") and window.btnModifyOrder:
            window.btnModifyOrder.setEnabled(False)
        if hasattr(window, "btnDiscardOrder") and window.btnDiscardOrder:
            window.btnDiscardOrder.setText("CANCEL ORDER")
            window.btnDiscardOrder.setEnabled(True)
            window.btnDiscardOrder.setCursor(Qt.PointingHandCursor)
        if hasattr(window, "_signal_expiry_timer") and window._signal_expiry_timer:
            try:
                window._signal_expiry_timer.stop()
            except Exception:
                pass
    else:
        if exec_mode == "FULL-AUTO":
            if hasattr(window, "lblGateExpiryTitle") and window.lblGateExpiryTitle:
                window.lblGateExpiryTitle.setText("EXECUTION")
            if hasattr(window, "lblGateExpiryTime") and window.lblGateExpiryTime:
                window.lblGateExpiryTime.setText("AUTONOMOUS")
            if hasattr(window, "barSignalExpiry") and window.barSignalExpiry:
                window.barSignalExpiry.setRange(0, 100)
                window.barSignalExpiry.setValue(100)
            if hasattr(window, "btnApproveOrder") and window.btnApproveOrder:
                window.btnApproveOrder.setText("FULL-AUTO: BOT MANAGING")
                window.btnApproveOrder.setEnabled(False)
                window.btnApproveOrder.setCursor(Qt.ArrowCursor)
            if hasattr(window, "btnModifyOrder") and window.btnModifyOrder:
                window.btnModifyOrder.setEnabled(False)
            if hasattr(window, "btnDiscardOrder") and window.btnDiscardOrder:
                window.btnDiscardOrder.setText("DISCARD")
                window.btnDiscardOrder.setEnabled(False)
                window.btnDiscardOrder.setCursor(Qt.ArrowCursor)
            if hasattr(window, "_signal_expiry_timer") and window._signal_expiry_timer:
                try:
                    window._signal_expiry_timer.stop()
                except Exception:
                    pass
        elif exec_mode == "SEMI-AUTO":
            if hasattr(window, "lblGateExpiryTitle") and window.lblGateExpiryTitle:
                window.lblGateExpiryTitle.setText("EXPIRATION")
            if hasattr(window, "btnApproveOrder") and window.btnApproveOrder:
                window.btnApproveOrder.setText("APPROVE ORDER")
                window.btnApproveOrder.setEnabled(True)
                window.btnApproveOrder.setCursor(Qt.PointingHandCursor)
            if hasattr(window, "btnModifyOrder") and window.btnModifyOrder:
                window.btnModifyOrder.setEnabled(True)
            if hasattr(window, "btnDiscardOrder") and window.btnDiscardOrder:
                window.btnDiscardOrder.setText("DISCARD")
                window.btnDiscardOrder.setEnabled(True)
                window.btnDiscardOrder.setCursor(Qt.PointingHandCursor)
            start_signal_expiry_countdown(window)
        else: # MANUAL
            if hasattr(window, "lblGateExpiryTitle") and window.lblGateExpiryTitle:
                window.lblGateExpiryTitle.setText("EXECUTION")
            if hasattr(window, "lblGateExpiryTime") and window.lblGateExpiryTime:
                window.lblGateExpiryTime.setText("MANUAL")
            if hasattr(window, "barSignalExpiry") and window.barSignalExpiry:
                window.barSignalExpiry.setRange(0, 100)
                window.barSignalExpiry.setValue(100)
            if hasattr(window, "btnApproveOrder") and window.btnApproveOrder:
                window.btnApproveOrder.setText("MANUAL COPILOT ONLY")
                window.btnApproveOrder.setEnabled(False)
                window.btnApproveOrder.setCursor(Qt.ArrowCursor)
            if hasattr(window, "btnModifyOrder") and window.btnModifyOrder:
                window.btnModifyOrder.setEnabled(False)
            if hasattr(window, "btnDiscardOrder") and window.btnDiscardOrder:
                window.btnDiscardOrder.setText("DISCARD")
                window.btnDiscardOrder.setEnabled(False)
                window.btnDiscardOrder.setCursor(Qt.ArrowCursor)
            if hasattr(window, "_signal_expiry_timer") and window._signal_expiry_timer:
                try:
                    window._signal_expiry_timer.stop()
                except Exception:
                    pass

    if hasattr(window, "cardSetupModel"):
        apply_playbook_cards_theme(window, is_dark)


def update_ai_reasoning(window, is_dark=None):
    """Render austere monospace institutional gate telemetry table conforming to system rules."""
    update_order_proposal_html(window, is_dark=is_dark)


def apply_playbook_cards_theme(window, is_dark: bool):
    """Apply strict institutional palette to the 3-Card Trading Plan Playbook."""
    assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets")
    if not os.path.exists(assets_dir):
        assets_dir = os.path.join(os.path.dirname(__file__), "assets")

    # Strict Institutional Palette (Sierra Chart / CRD / Exocharts) - ZERO NEON
    card_bg = "#090d16" if is_dark else "#f8fafc"
    card_border = "#1e293b" if is_dark else "#cbd5e1"
    sep_color = "#1e293b" if is_dark else "#e2e8f0"
    sub_color = "#64748b"
    name_color = "#f8fafc" if is_dark else "#0f172a"
    entry_color = "#f8fafc" if is_dark else "#0f172a"
    text_sec = "#94a3b8" if is_dark else "#475569"
    bull_color = "#22c55e" if is_dark else "#15803d"  # Delta Bullish matte green, NO neon!
    bear_color = "#ef4444" if is_dark else "#dc2626"  # Coral Red, NO neon!

    # Badges (Strict Flat 2px radius, restrained forest green, zero fluorescent glare)
    badge_bg = "#0d2818" if is_dark else "#f0fdf4"
    badge_border = "#272d3b" if is_dark else "#cbd5e1"
    badge_text = "#16a34a" if is_dark else "#15803d"

    # Overlay container
    if hasattr(window, "frameAIArea") and window.frameAIArea:
        overlay_bg = "#090d16" if is_dark else "#ffffff"
        overlay_border = "#1e293b" if is_dark else "#cbd5e1"
        window.frameAIArea.setStyleSheet(
            f"QFrame#frameAIArea, QFrame#floatingTradingPlan {{ background-color: {overlay_bg}; border: 1px solid {overlay_border}; border-radius: 2px; }}"
        )

    # Title & Close button in header
    if hasattr(window, "lblAIGateTitle") and window.lblAIGateTitle:
        title_color = "#f8fafc" if is_dark else "#0f172a"
        window.lblAIGateTitle.setStyleSheet(
            f"color: {title_color}; font-family: 'Segoe UI', sans-serif; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; border: none; background: transparent;"
        )

    if hasattr(window, "btnAIClose") and window.btnAIClose:
        close_svg = os.path.join(assets_dir, "close_hairline.svg")
        if os.path.exists(close_svg):
            window.btnAIClose.setIcon(QIcon(close_svg))
            window.btnAIClose.setIconSize(QSize(11, 11))
            window.btnAIClose.setText("")
        hover_bg = "rgba(255, 255, 255, 0.08)" if is_dark else "rgba(0, 0, 0, 0.05)"
        window.btnAIClose.setStyleSheet(
            f"QPushButton#btnAIClose {{ background: transparent; border: none; padding: 2px; }} "
            f"QPushButton#btnAIClose:hover {{ background-color: {hover_bg}; border-radius: 2px; }}"
        )

    # Cards - Flatten completely (Zero nested card boxes, pure institutional flat sections)
    for card_name in ["cardSetupModel", "cardRiskBudget", "cardExecutionGate"]:
        if hasattr(window, card_name) and getattr(window, card_name):
            getattr(window, card_name).setStyleSheet(
                f"QFrame#{card_name} {{ background: transparent; border: none; border-radius: 0px; padding: 0px; }}"
            )

    for sep_name in ["sepCard1", "sepCard2", "sepCard2Sub", "sepDivider1", "sepDivider2"]:
        if hasattr(window, sep_name) and getattr(window, sep_name):
            getattr(window, sep_name).setStyleSheet(
                f"background-color: {sep_color}; height: 1px; border: none;"
            )

    sub_style = f"color: {sub_color}; font-family: 'Segoe UI', sans-serif; font-size: 8.5px; font-weight: 700; letter-spacing: 0.5px; border: none; background: transparent;"
    for sub_name in ["lblModelSubtitle", "lblOrderBudgetTitle", "lblGateExpiryTitle"]:
        if hasattr(window, sub_name) and getattr(window, sub_name):
            getattr(window, sub_name).setStyleSheet(sub_style)

    if hasattr(window, "lblModelName") and window.lblModelName:
        window.lblModelName.setStyleSheet(
            f"color: {name_color}; font-family: 'Segoe UI', sans-serif; font-size: 11px; font-weight: 700; border: none; background: transparent;"
        )

    # Dynamic styling for Model Grade (Confidence) and Order Type badges
    if hasattr(window, "lblOrderTypeBadge") and window.lblOrderTypeBadge:
        order_txt = window.lblOrderTypeBadge.text().upper()
        if "BUY" in order_txt:
            b_bg = "#0d2818" if is_dark else "#f0fdf4"
            b_border = "#1b4d2e" if is_dark else "#bbf7d0"
            b_text = "#22c55e" if is_dark else "#15803d"
        elif "SELL" in order_txt:
            b_bg = "#271214" if is_dark else "#fef2f2"
            b_border = "#4a1d24" if is_dark else "#fecaca"
            b_text = "#ef4444" if is_dark else "#dc2626"
        else:
            b_bg = "#1e293b" if is_dark else "#f1f5f9"
            b_border = "#334155" if is_dark else "#cbd5e1"
            b_text = "#94a3b8" if is_dark else "#64748b"
        window.lblOrderTypeBadge.setStyleSheet(
            f"background-color: {b_bg}; color: {b_text}; border: 1px solid {b_border}; "
            f"font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 1px 5px;"
        )

    if hasattr(window, "lblModelGrade") and window.lblModelGrade:
        grade_txt = window.lblModelGrade.text().upper()
        conf_val = 80
        if "%" in grade_txt:
            try:
                digits_str = "".join([c for c in grade_txt if c.isdigit()])
                if digits_str:
                    conf_val = int(digits_str)
            except Exception:
                conf_val = 80
        if "AWAITING" in grade_txt or "STANDBY" in grade_txt:
            g_bg = "#1e293b" if is_dark else "#f1f5f9"
            g_border = "#334155" if is_dark else "#cbd5e1"
            g_text = "#94a3b8" if is_dark else "#64748b"
        elif conf_val >= 70:
            g_bg = "#0d2818" if is_dark else "#f0fdf4"
            g_border = "#1b4d2e" if is_dark else "#bbf7d0"
            g_text = "#22c55e" if is_dark else "#15803d"
        elif conf_val >= 50:
            g_bg = "#2a1d0d" if is_dark else "#fffbeb"
            g_border = "#5e3e0f" if is_dark else "#fde68a"
            g_text = "#f59e0b" if is_dark else "#b45309"
        else:
            g_bg = "#271214" if is_dark else "#fef2f2"
            g_border = "#4a1d24" if is_dark else "#fecaca"
            g_text = "#ef4444" if is_dark else "#dc2626"
        window.lblModelGrade.setStyleSheet(
            f"background-color: {g_bg}; color: {g_text}; border: 1px solid {g_border}; "
            f"font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 1px 5px;"
        )

    key_style = f"color: {sub_color}; font-family: Consolas, monospace; font-size: 9.5px; border: none; background: transparent;"
    for k_attr in dir(window):
        if k_attr.startswith("lblKey_"):
            w = getattr(window, k_attr)
            if w:
                w.setStyleSheet(key_style)

    # Dynamic Checklist status and vector icons
    svg_file = "check_vector_emerald.svg" if is_dark else "check_vector_light.svg"
    icon_path = os.path.join(assets_dir, svg_file)
    chk_pixmap = QIcon(icon_path).pixmap(12, 12) if os.path.exists(icon_path) else None

    for val_name, ic_name in [("lblChk1Val", "lblChk1Icon"), ("lblChk2Val", "lblChk2Icon"), ("lblChk3Val", "lblChk3Icon")]:
        val_w = getattr(window, val_name, None)
        ic_w = getattr(window, ic_name, None)
        if val_w is not None:
            txt = val_w.text().lower()
            is_unmet = any(w in txt for w in ["awaiting", "monitoring", "standby", "pending", "no ", "--", "scanning", "sideways", "ranging", "đi ngang"])
            if is_unmet:
                val_w.setStyleSheet(f"color: {text_sec}; font-family: Consolas, monospace; font-size: 9.5px; font-weight: 500; border: none; background: transparent;")
                if ic_w:
                    ic_w.setVisible(False)
            else:
                val_w.setStyleSheet(f"color: {bull_color}; font-family: Consolas, monospace; font-size: 9.5px; font-weight: bold; border: none; background: transparent;")
                if ic_w:
                    ic_w.setVisible(True)
                    if chk_pixmap:
                        ic_w.setPixmap(chk_pixmap)

    # Card 2 values
    if hasattr(window, "lblEntryVal") and window.lblEntryVal:
        window.lblEntryVal.setStyleSheet(f"color: {entry_color}; font-family: Consolas, monospace; font-size: 13px; font-weight: 800; border: none; background: transparent;")
    if hasattr(window, "lblSLVal") and window.lblSLVal:
        window.lblSLVal.setStyleSheet(f"color: {bear_color}; font-family: Consolas, monospace; font-size: 9.5px; font-weight: bold; border: none; background: transparent;")
    if hasattr(window, "lblTPVal") and window.lblTPVal:
        window.lblTPVal.setStyleSheet(f"color: {bull_color}; font-family: Consolas, monospace; font-size: 9.5px; font-weight: bold; border: none; background: transparent;")
    if hasattr(window, "lblSizeVal") and window.lblSizeVal:
        window.lblSizeVal.setStyleSheet(f"color: {text_sec}; font-family: Consolas, monospace; font-size: 9.5px; font-weight: 600; border: none; background: transparent;")

    # Card 3 Expiration Window
    time_color = "#d97706" if is_dark else "#b45309"
    if hasattr(window, "lblGateExpiryTime") and window.lblGateExpiryTime:
        window.lblGateExpiryTime.setStyleSheet(f"color: {time_color}; font-family: Consolas, monospace; font-size: 9.5px; font-weight: bold; border: none; background: transparent;")

    if hasattr(window, "barSignalExpiry") and window.barSignalExpiry:
        bar_bg = "#18181b" if is_dark else "#e2e8f0"
        bar_fg = "#166534" if is_dark else "#15803d"  # Restrained forest green, NO neon!
        window.barSignalExpiry.setStyleSheet(
            f"QProgressBar#barSignalExpiry {{ background-color: {bar_bg}; border: none; border-radius: 1px; }} "
            f"QProgressBar#barSignalExpiry::chunk {{ background-color: {bar_fg}; }}"
        )

    # Approve button: Authoritative, institutional execution button (ZERO NEON)
    if hasattr(window, "btnApproveOrder") and window.btnApproveOrder:
        if is_dark:
            window.btnApproveOrder.setStyleSheet(
                "QPushButton#btnApproveOrder { background-color: #143d28; color: #f8fafc; border: 1px solid #1e5a3a; "
                "font-family: Consolas, monospace; font-size: 10px; font-weight: bold; border-radius: 2px; } "
                "QPushButton#btnApproveOrder:hover { background-color: #194d33; color: #ffffff; border-color: #236c46; } "
                "QPushButton#btnApproveOrder:disabled { background-color: #121824; color: #475569; border: 1px solid #1e293b; }"
            )
        else:
            window.btnApproveOrder.setStyleSheet(
                "QPushButton#btnApproveOrder { background-color: #15803d; color: #ffffff; border: 1px solid #166534; "
                "font-family: Consolas, monospace; font-size: 10px; font-weight: bold; border-radius: 2px; } "
                "QPushButton#btnApproveOrder:hover { background-color: #166534; color: #ffffff; border-color: #14532d; } "
                "QPushButton#btnApproveOrder:disabled { background-color: #f1f5f9; color: #94a3b8; border: 1px solid #cbd5e1; }"
            )

    if hasattr(window, "btnModifyOrder") and window.btnModifyOrder:
        if is_dark:
            window.btnModifyOrder.setStyleSheet(
                "QPushButton#btnModifyOrder { background-color: #141923; color: #94a3b8; border: 1px solid #273346; "
                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: 600; border-radius: 2px; } "
                "QPushButton#btnModifyOrder:hover { background-color: #1e2638; color: #cbd5e1; border-color: #3b4b66; } "
                "QPushButton#btnModifyOrder:disabled { background-color: #0b0f19; color: #334155; border: 1px solid #1e293b; }"
            )
        else:
            window.btnModifyOrder.setStyleSheet(
                "QPushButton#btnModifyOrder { background-color: #ffffff; color: #475569; border: 1px solid #cbd5e1; "
                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: 600; border-radius: 2px; } "
                "QPushButton#btnModifyOrder:hover { background-color: #f8fafc; color: #0f172a; border-color: #94a3b8; } "
                "QPushButton#btnModifyOrder:disabled { background-color: #f8fafc; color: #cbd5e1; border: 1px solid #e2e8f0; }"
            )

    if hasattr(window, "btnDiscardOrder") and window.btnDiscardOrder:
        if is_dark:
            window.btnDiscardOrder.setStyleSheet(
                "QPushButton#btnDiscardOrder { background-color: #241214; color: #dc2626; border: 1px solid #272d3b; "
                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: 600; border-radius: 2px; } "
                "QPushButton#btnDiscardOrder:hover { background-color: #33181b; color: #ef4444; border-color: #475569; } "
                "QPushButton#btnDiscardOrder:disabled { background-color: #0b0f19; color: #334155; border: 1px solid #1e293b; }"
            )
        else:
            window.btnDiscardOrder.setStyleSheet(
                "QPushButton#btnDiscardOrder { background-color: #ffffff; color: #dc2626; border: 1px solid #cbd5e1; "
                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: 600; border-radius: 2px; padding: 0 6px; } "
                "QPushButton#btnDiscardOrder:hover { background-color: #fef2f2; color: #b91c1c; border-color: #94a3b8; } "
                "QPushButton#btnDiscardOrder:disabled { background-color: #f8fafc; color: #cbd5e1; border: 1px solid #e2e8f0; }"
            )

    # Edge button restore Trading Plan
    if hasattr(window, "btn_edge_plan") and window.btn_edge_plan:
        chevron_left_svg = os.path.join(assets_dir, "chevron_left.svg")
        if os.path.exists(chevron_left_svg):
            window.btn_edge_plan.setIcon(QIcon(chevron_left_svg))
            window.btn_edge_plan.setIconSize(QSize(10, 10))
        if is_dark:
            window.btn_edge_plan.setStyleSheet(
                "QPushButton#btnEdgeTradingPlan { background-color: #0f172a; color: #94a3b8; border: 1px solid #1e293b; "
                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0 6px; min-height: 18px; max-height: 18px; } "
                "QPushButton#btnEdgeTradingPlan:hover { background-color: #1e293b; color: #f8fafc; border-color: #334155; }"
            )
        else:
            window.btn_edge_plan.setStyleSheet(
                "QPushButton#btnEdgeTradingPlan { background-color: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; "
                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0 6px; min-height: 18px; max-height: 18px; } "
                "QPushButton#btnEdgeTradingPlan:hover { background-color: #e2e8f0; color: #0f172a; border-color: #94a3b8; }"
            )

    # Mode Switcher Bar
    if hasattr(window, "framePlanModeSwitcher") and window.framePlanModeSwitcher:
        sw_bg = "#0b0f19" if is_dark else "#f1f5f9"
        sw_border = "#1e293b" if is_dark else "#cbd5e1"
        window.framePlanModeSwitcher.setStyleSheet(
            f"QFrame#framePlanModeSwitcher {{ background-color: {sw_bg}; border: 1px solid {sw_border}; border-radius: 2px; }}"
        )

    # Mode Buttons Styling via dynamic QSS property
    mode = getattr(window, "_plan_mode", "ai")
    for btn_name, is_act in [("btnPlanModeAI", mode == "ai"), ("btnPlanModeManual", mode == "manual")]:
        b = getattr(window, btn_name, None)
        if b:
            b.setProperty("active", "true" if is_act else "false")
            b.style().unpolish(b)
            b.style().polish(b)

    # Manual Copilot Cards
    for c_name in ["cardManualDir", "cardManualRisk", "cardManualGate", "cardManualAction"]:
        if hasattr(window, c_name) and getattr(window, c_name):
            getattr(window, c_name).setStyleSheet(
                f"QFrame#{c_name} {{ background: transparent; border: none; border-radius: 0px; padding: 0px; }}"
            )

    for s_name in ["sepManual1", "sepManual2", "sepManual3"]:
        if hasattr(window, s_name) and getattr(window, s_name):
            getattr(window, s_name).setStyleSheet(
                f"background-color: {sep_color}; height: 1px; border: none;"
            )

    # Direction Buttons (BUY / SELL) via dynamic QSS property
    man_dir = getattr(window, "_manual_direction", "BUY")
    if hasattr(window, "btnManualBuy") and window.btnManualBuy:
        is_sel = (man_dir == "BUY")
        window.btnManualBuy.setProperty("selected", "true" if is_sel else "false")
        window.btnManualBuy.style().unpolish(window.btnManualBuy)
        window.btnManualBuy.style().polish(window.btnManualBuy)

    if hasattr(window, "btnManualSell") and window.btnManualSell:
        is_sel = (man_dir == "SELL")
        window.btnManualSell.setProperty("selected", "true" if is_sel else "false")
        window.btnManualSell.style().unpolish(window.btnManualSell)
        window.btnManualSell.style().polish(window.btnManualSell)

    ask_fg = ("#22c55e" if is_dark else "#15803d") if man_dir == "BUY" else ("#94a3b8" if is_dark else "#64748b")
    bid_fg = ("#ef4444" if is_dark else "#dc2626") if man_dir == "SELL" else ("#94a3b8" if is_dark else "#64748b")
    if hasattr(window, "lblManualAskPrice") and window.lblManualAskPrice:
        window.lblManualAskPrice.setStyleSheet(f"color: {ask_fg}; font-family: Consolas, monospace; font-size: 11px; font-weight: 700; border: none; background: transparent;")
    if hasattr(window, "lblManualBidPrice") and window.lblManualBidPrice:
        window.lblManualBidPrice.setStyleSheet(f"color: {bid_fg}; font-family: Consolas, monospace; font-size: 11px; font-weight: 700; border: none; background: transparent;")
    if hasattr(window, "lblManualBuyText") and window.lblManualBuyText:
        window.lblManualBuyText.setStyleSheet(f"color: {ask_fg}; font-family: 'Segoe UI', sans-serif; font-size: 8.5px; font-weight: 700; border: none; background: transparent;")
    if hasattr(window, "lblManualSellText") and window.lblManualSellText:
        window.lblManualSellText.setStyleSheet(f"color: {bid_fg}; font-family: 'Segoe UI', sans-serif; font-size: 8.5px; font-weight: 700; border: none; background: transparent;")

    # Risk % Buttons via dynamic QSS property
    cur_risk = getattr(window, "_manual_risk_pct", 1.0)
    is_custom = getattr(window, "_user_custom_lot", False)
    for p_val, b_name in [(0.5, "btnRisk05"), (1.0, "btnRisk10"), (1.5, "btnRisk15"), (2.0, "btnRisk20")]:
        b = getattr(window, b_name, None)
        if b:
            is_sel = (not is_custom) and (abs(cur_risk - p_val) < 0.05)
            b.setProperty("selected", "true" if is_sel else "false")
            b.style().unpolish(b)
            b.style().polish(b)

    # Preset buttons
    for pre_name in ["btnPresetATR", "btnPresetSwing", "btnPresetRR15", "btnPresetRR20", "btnPresetRR30", "btnManualClearPreview", "btnManualReset"]:
        b = getattr(window, pre_name, None)
        if b:
            b.style().unpolish(b)
            b.style().polish(b)

    # SpinBoxes (SL / TP / Lot / Pending Price)
    for spin_name in ["spinManualSL", "spinManualTP", "spinManualLot", "spinManualPendingPrice"]:
        sp = getattr(window, spin_name, None)
        if sp:
            sp.style().unpolish(sp)
            sp.style().polish(sp)


    # Volume Stepper Buttons
    lot_step_style = (
        f"QPushButton {{ background-color: {'#071524' if is_dark else '#f1f5f9'}; color: {'#94a3b8' if is_dark else '#475569'}; "
        f"border: 1px solid {'#0c3359' if is_dark else '#cbd5e1'}; border-radius: 2px; font-family: Consolas, monospace; "
        f"font-size: 10px; font-weight: 700; min-height: 18px; max-height: 18px; min-width: 18px; max-width: 18px; padding: 0px; margin: 0px; }} "
        f"QPushButton:hover {{ background-color: {'#0c3359' if is_dark else '#e2e8f0'}; color: {'#38bdf8' if is_dark else '#0f172a'}; border-color: {'#38bdf8' if is_dark else '#94a3b8'}; }}"
    )
    if hasattr(window, "btnManualLotMinus") and window.btnManualLotMinus:
        window.btnManualLotMinus.setStyleSheet(lot_step_style)
    if hasattr(window, "btnManualLotPlus") and window.btnManualLotPlus:
        window.btnManualLotPlus.setStyleSheet(lot_step_style)

    # Order Type Selector (Dynamic unpolish/polish for Light/Dark mode)
    if hasattr(window, "comboManualOrderType") and window.comboManualOrderType:
        window.comboManualOrderType.style().unpolish(window.comboManualOrderType)
        window.comboManualOrderType.style().polish(window.comboManualOrderType)

    # Order Type & Pending Price Labels
    for lbl_name in ["lblManualOrderTypeLabel", "lblManualPendingPriceLabel"]:
        lbl_w = getattr(window, lbl_name, None)
        if lbl_w:
            lbl_w.setStyleSheet(f"color: {sub_color}; font-size: 9px; font-weight: 700; letter-spacing: 0.5px; border: none; background: transparent;")

    # Lot Summary Box (Transparent, no border, clean whitespace separation)
    if hasattr(window, "boxManualLotSummary") and window.boxManualLotSummary:
        window.boxManualLotSummary.setStyleSheet(
            "QFrame#boxManualLotSummary { background-color: transparent; border: none; border-radius: 0px; padding: 2px 0px; }"
        )

    # Execute Button
    if hasattr(window, "btnManualExecute") and window.btnManualExecute:
        window.btnManualExecute.setProperty("direction", man_dir)
        window.btnManualExecute.style().unpolish(window.btnManualExecute)
        window.btnManualExecute.style().polish(window.btnManualExecute)

    # Manual Titles & Badges
    if hasattr(window, "lblManualHeaderTitle") and window.lblManualHeaderTitle:
        window.lblManualHeaderTitle.setStyleSheet(sub_style)
    if hasattr(window, "lblManualRiskTitle") and window.lblManualRiskTitle:
        window.lblManualRiskTitle.setStyleSheet(sub_style)
    if hasattr(window, "lblManualGateTitle") and window.lblManualGateTitle:
        window.lblManualGateTitle.setStyleSheet(sub_style)
    if hasattr(window, "lblManualExecBadge") and window.lblManualExecBadge:
        window.lblManualExecBadge.setStyleSheet(
            "background-color: #1e293b; color: #38bdf8; border: 1px solid #334155; "
            "font-family: Consolas, monospace; font-size: 8px; font-weight: bold; border-radius: 2px; padding: 1px 4px;"
            if is_dark else
            "background-color: #f1f5f9; color: #0284c7; border: 1px solid #cbd5e1; "
            "font-family: Consolas, monospace; font-size: 8px; font-weight: bold; border-radius: 2px; padding: 1px 4px;"
        )

    # Split Risk (Red) / Reward (Green) Colors
    risk_color = "#ef4444" if is_dark else "#b91c1c"
    slash_color = "#64748b" if is_dark else "#94a3b8"
    reward_color = "#22c55e" if is_dark else "#15803d"

    if hasattr(window, "lblManualSpread") and window.lblManualSpread:
        window.lblManualSpread.setStyleSheet(
            f"color: {text_sec}; font-family: Consolas, monospace; font-size: 8.5px; border: none; background: transparent;"
        )
    if hasattr(window, "lblManualSLPips") and window.lblManualSLPips:
        window.lblManualSLPips.setStyleSheet(
            f"color: {risk_color}; font-family: Consolas, monospace; font-size: 8.5px; font-weight: 600; min-height: 14px; padding: 0px; border: none; background: transparent;"
        )
    if hasattr(window, "lblManualTPPips") and window.lblManualTPPips:
        window.lblManualTPPips.setStyleSheet(
            f"color: {reward_color}; font-family: Consolas, monospace; font-size: 8.5px; font-weight: 600; min-height: 14px; padding: 0px; border: none; background: transparent;"
        )
    if hasattr(window, "lblManualLotSummaryTitle") and window.lblManualLotSummaryTitle:
        window.lblManualLotSummaryTitle.setStyleSheet(
            f"{sub_style} min-height: 14px;"
        )

    if hasattr(window, "lblManualRiskPart") and window.lblManualRiskPart:
        window.lblManualRiskPart.setStyleSheet(
            f"color: {risk_color}; font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border: none; background: transparent;"
        )
    if hasattr(window, "lblManualSlash") and window.lblManualSlash:
        window.lblManualSlash.setStyleSheet(
            f"color: {slash_color}; font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border: none; background: transparent;"
        )
    if hasattr(window, "lblManualRewardPart") and window.lblManualRewardPart:
        window.lblManualRewardPart.setStyleSheet(
            f"color: {reward_color}; font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border: none; background: transparent;"
        )

    for k_lbl in ["lblGateCheck1Title", "lblGateCheck2Title", "lblGateCheck3Title", "lblGateCheck4Title", "lblManualRiskLabel", "lblManualSLLabel", "lblManualTPLabel"]:
        w = getattr(window, k_lbl, None)
        if w:
            w.setStyleSheet(f"color: {sub_color}; font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border: none; background: transparent;")


def evaluate_manual_compliance(window, symbol=None):
    """
    Evaluates institutional Pre-Trade Risk Gatekeeper:
    1. Daily Drawdown Guard (< 4.0% or max daily loss limit)
    2. Event Risk Engine (High-impact news filter ±15m)
    3. Exposure Gate (Max open positions limit)
    4. Spread Normalization (Safe spread limit)
    5. Stop-Loss & Take-Profit Orientation (Prevents MT5 Retcode 10016)
    
    Returns: (passed: bool, checks: dict, block_reason: str)
    """
    clean_sym = (symbol or getattr(window, "current_sym", "XAUUSD") or "XAUUSD").split("\n")[0].strip()
    checks = {
        "drawdown": {"passed": True, "msg": "Daily Loss: OK", "val": "PASS"},
        "news": {"passed": True, "msg": "News Filter: Clear", "val": "PASS"},
        "max_trades": {"passed": True, "msg": "Exposure: OK", "val": "PASS"},
        "spread": {"passed": True, "msg": "Spread: OK", "val": "PASS"},
        "stops": {"passed": True, "msg": "Stops: Valid", "val": "PASS"},
        "margin": {"passed": True, "msg": "Margin: OK", "val": "PASS"},
    }
    block_reason = ""

    cfg = {}
    try:
        cfg_p = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "config", "settings.json")
        if os.path.exists(cfg_p):
            with open(cfg_p, "r", encoding="utf-8") as f:
                cfg = json.load(f)
    except Exception:
        pass

    # 1. Daily Drawdown Check (SC-05: Harmonized with CircuitBreakerGuard Single Source of Truth)
    max_daily_loss = float(cfg.get("max_daily_loss", 5000.0))
    max_drawdown = float(cfg.get("max_drawdown", 5.0))
    acc = mt5.account_info() if mt5.terminal_info() is not None else None
    if acc:
        equity = float(acc.equity)
        balance = float(acc.balance)

        # Retrieve start_of_day equity baseline and circuit breaker latch from database
        cb_active = False
        start_of_day_eq = balance
        try:
            from backend.database.db_manager import DatabaseManager
            db = DatabaseManager()
            today_str = datetime.now().strftime("%Y-%m-%d")
            saved_date = db.get_system_state("circuit_breaker_date", default="")
            saved_active = db.get_system_state("circuit_breaker_active", default="False")
            if saved_date == today_str and saved_active == "True":
                cb_active = True

            sod_str = db.get_system_state("start_of_day_equity", default="")
            if sod_str:
                sod_val = float(sod_str)
                if sod_val > 0:
                    start_of_day_eq = sod_val
        except Exception:
            pass

        # Total daily loss includes both realized closed loss today and active floating drawdown
        daily_loss = max(0.0, start_of_day_eq - equity)
        dd_pct = (daily_loss / start_of_day_eq) * 100.0 if start_of_day_eq > 0 else 0.0

        if cb_active:
            checks["drawdown"] = {"passed": False, "msg": "Circuit Breaker Active (Trading Halted)", "val": "HALTED"}
            block_reason = "CIRCUIT BREAKER ACTIVE"
        elif max_daily_loss > 0 and daily_loss >= max_daily_loss:
            checks["drawdown"] = {"passed": False, "msg": f"Loss -${daily_loss:.0f} >= -${max_daily_loss:.0f}", "val": "HALTED"}
            block_reason = "DAILY LOSS LIMIT EXCEEDED"
        elif start_of_day_eq > 0 and max_drawdown > 0 and dd_pct >= max_drawdown:
            checks["drawdown"] = {"passed": False, "msg": f"DD {dd_pct:.1f}% >= {max_drawdown:.1f}%", "val": "HALTED"}
            block_reason = "MAX DRAWDOWN BREACHED"

    # 2. Event Risk Engine Check (News Filter via MacroContextBus)
    if not block_reason and cfg.get("news_defense_enabled", True):
        try:
            from backend.core.macro_context_bus import MacroContextBus
            bus = MacroContextBus.get_instance()
            is_passed, status_val, msg = bus.check_pre_trade_news_compliance(clean_sym)
            if not is_passed:
                checks["news"] = {
                    "passed": False,
                    "msg": msg,
                    "val": "BLOCKED",
                    "event": "News Lockout",
                }
                block_reason = "NEWS BLACKOUT LOCK"
            elif status_val == "OVERRIDE":
                checks["news"] = {
                    "passed": True,
                    "msg": msg,
                    "val": "PASS",
                    "event": "Manual Override",
                }
            else:
                checks["news"] = {
                    "passed": True,
                    "msg": "News Defense: Clear (No high-impact blackout)",
                    "val": "PASS",
                    "event": "Clear",
                }
        except Exception as e:
            logger.debug(f"[TradingPlan] News check error: {e}")

    # 3. Max Open Trades Check
    max_trades = int(cfg.get("max_open_trades", 3))
    if not block_reason and max_trades > 0 and mt5.terminal_info() is not None:
        try:
            all_pos = mt5.positions_get()
            count_pos = len(all_pos) if all_pos else 0
            if count_pos >= max_trades:
                checks["max_trades"] = {"passed": False, "msg": f"Open {count_pos}/{max_trades} max", "val": "LIMIT"}
                block_reason = f"MAX TRADES LIMIT ({count_pos}/{max_trades})"
        except Exception:
            pass

    # 4. Universal Multi-Asset Spread Normalization Check (QuantConnect LEAN & Sierra Chart Standards)
    if not block_reason and mt5.terminal_info() is not None:
        try:
            info = mt5.symbol_info(clean_sym)
            if info:
                cur_spd = info.spread
                pt = float(info.point) if hasattr(info, "point") and isinstance(info.point, (int, float)) and info.point > 0 else 0.01

                tick = mt5.symbol_info_tick(clean_sym)
                if tick and hasattr(tick, "ask") and hasattr(tick, "bid") and isinstance(tick.ask, (int, float)) and tick.ask > 0 and tick.bid > 0:
                    entry_ref = (tick.ask + tick.bid) / 2.0
                    spread_cost = tick.ask - tick.bid
                else:
                    entry_ref = getattr(window, "_last_manual_entry", 0.0)
                    if not isinstance(entry_ref, (int, float)) or entry_ref <= 0.0:
                        entry_ref = 0.0
                    spread_cost = cur_spd * pt

                spread_bps = (spread_cost / entry_ref * 10000.0) if entry_ref > 0 else 0.0
                safe_pts, max_bps = calculate_safe_spread_allowance(clean_sym, info, current_price=entry_ref)
                user_max = int(cfg.get("max_spread", 25))
                effective_pts = max(safe_pts, user_max) if user_max > safe_pts else safe_pts

                # Metric 1: Relative basis point expansion check
                is_wide = (cur_spd > effective_pts) and (spread_bps > max_bps if entry_ref > 0 else True)

                # Metric 2: Transaction cost friction against Stop Loss (Almgren-Chriss / López de Prado)
                if not is_wide and hasattr(window, "spinManualSL") and window.spinManualSL:
                    sl_val = float(window.spinManualSL.value()) if hasattr(window.spinManualSL, "value") and isinstance(window.spinManualSL.value(), (int, float)) else 0.0
                    if sl_val > 0 and entry_ref > 0:
                        sl_dist = abs(entry_ref - sl_val)
                        if sl_dist > 0 and spread_cost >= sl_dist:
                            is_wide = True
                            block_reason = "SPREAD EXCEEDS STOP LOSS DISTANCE"
                            checks["spread"] = {"passed": False, "msg": f"Spread ${spread_cost:.2f} >= SL ${sl_dist:.2f}", "val": "HIGH"}

                if is_wide and not block_reason:
                    checks["spread"] = {"passed": False, "msg": f"Spread {cur_spd} > {effective_pts} pts ({spread_bps:.1f} bps)", "val": "HIGH"}
                    block_reason = f"SPREAD TOO WIDE ({cur_spd} pts)"
        except Exception:
            pass

    # 5. Stop-Loss & Take-Profit Orientation Check (Zero Invalid Stops)
    if not block_reason and hasattr(window, "spinManualSL") and hasattr(window, "spinManualTP"):
        try:
            sl_w = window.spinManualSL
            tp_w = window.spinManualTP
            if hasattr(sl_w, "value") and hasattr(tp_w, "value"):
                sl_val = float(sl_w.value())
                tp_val = float(tp_w.value())
                is_buy = (getattr(window, "_manual_direction", "BUY") == "BUY")
                order_type_str = getattr(window, "_manual_order_type", "MARKET")
                
                # For pending orders, entry_ref is the pending trigger price (strictly > 0.01 to avoid default/min clamp error)
                if order_type_str != "MARKET" and hasattr(window, "spinManualPendingPrice") and window.spinManualPendingPrice and window.spinManualPendingPrice.value() > 0.01:
                    entry_ref = float(window.spinManualPendingPrice.value())
                else:
                    entry_ref = getattr(window, "_last_manual_entry", 0.0)
                    if not isinstance(entry_ref, (int, float)) or entry_ref <= 0.0:
                        tick = mt5.symbol_info_tick(clean_sym) if mt5.terminal_info() is not None else None
                        if tick and hasattr(tick, "ask") and hasattr(tick, "bid") and isinstance(tick.ask, (int, float)) and tick.ask > 0 and tick.bid > 0:
                            entry_ref = float(tick.ask if is_buy else tick.bid)
                        else:
                            entry_ref = 0.0

                # Validate Pending Order Price relative to current market price
                tick_curr = mt5.symbol_info_tick(clean_sym) if mt5.terminal_info() is not None else None
                c_ask = float(tick_curr.ask) if tick_curr and tick_curr.ask > 0 else 0.0
                c_bid = float(tick_curr.bid) if tick_curr and tick_curr.bid > 0 else 0.0
                if order_type_str == "BUY LIMIT" and c_ask > 0 and entry_ref >= c_ask:
                    checks["stops"] = {"passed": False, "msg": f"Buy Limit {entry_ref} >= Ask {c_ask}", "val": "INVALID"}
                    block_reason = "BUY LIMIT MUST BE BELOW MARKET ASK"
                elif order_type_str == "SELL LIMIT" and c_bid > 0 and entry_ref <= c_bid:
                    checks["stops"] = {"passed": False, "msg": f"Sell Limit {entry_ref} <= Bid {c_bid}", "val": "INVALID"}
                    block_reason = "SELL LIMIT MUST BE ABOVE MARKET BID"
                elif order_type_str == "BUY STOP" and c_ask > 0 and entry_ref <= c_ask:
                    checks["stops"] = {"passed": False, "msg": f"Buy Stop {entry_ref} <= Ask {c_ask}", "val": "INVALID"}
                    block_reason = "BUY STOP MUST BE ABOVE MARKET ASK"
                elif order_type_str == "SELL STOP" and c_bid > 0 and entry_ref >= c_bid:
                    checks["stops"] = {"passed": False, "msg": f"Sell Stop {entry_ref} >= Bid {c_bid}", "val": "INVALID"}
                    block_reason = "SELL STOP MUST BE BELOW MARKET BID"
                if entry_ref > 0.0 and sl_val > 0.0:
                    if is_buy and sl_val >= entry_ref:
                        checks["stops"] = {"passed": False, "msg": f"SL {sl_val} >= Buy {entry_ref}", "val": "INVALID"}
                        block_reason = "INVALID SL (MUST BE BELOW ENTRY)"
                    elif not is_buy and sl_val <= entry_ref:
                        checks["stops"] = {"passed": False, "msg": f"SL {sl_val} <= Sell {entry_ref}", "val": "INVALID"}
                        block_reason = "INVALID SL (MUST BE ABOVE ENTRY)"
                    elif tp_val > 0.0 and is_buy and tp_val <= entry_ref:
                        checks["stops"] = {"passed": False, "msg": f"TP {tp_val} <= Buy {entry_ref}", "val": "INVALID"}
                        block_reason = "INVALID TP (MUST BE ABOVE ENTRY)"
                    elif tp_val > 0.0 and not is_buy and tp_val >= entry_ref:
                        checks["stops"] = {"passed": False, "msg": f"TP {tp_val} >= Sell {entry_ref}", "val": "INVALID"}
                        block_reason = "INVALID TP (MUST BE BELOW ENTRY)"
        except Exception as e:
            logger.debug(f"[TradingPlan] Stops check error: {e}")

    # 6. Free Margin & Leverage Adequacy Check (Pre-Trade Liquidity Gate)
    if not block_reason and acc and hasattr(acc, "margin_free") and float(getattr(acc, "margin_free", 0.0)) > 0:
        try:
            free_margin = float(acc.margin_free)
            spin_lot = getattr(window, "spinManualLot", None)
            lot_to_check = float(spin_lot.value()) if (spin_lot and hasattr(spin_lot, "value") and spin_lot.value() > 0) else 0.01
            entry_p_check = _get_manual_effective_entry_price(window, is_buy, clean_sym)
            calc_action = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
            req_margin = mt5.order_calc_margin(calc_action, clean_sym, lot_to_check, entry_p_check)
            if req_margin is None or req_margin <= 0:
                mult = get_symbol_multiplier(clean_sym, mt5.symbol_info(clean_sym))
                lev = float(getattr(acc, "leverage", 100) or 100)
                req_margin = (entry_p_check * mult * lot_to_check) / lev if lev > 0 else 0.0

            if req_margin > 0 and req_margin > (free_margin * 0.95):
                checks["margin"] = {
                    "passed": False,
                    "msg": f"Margin: Req ${req_margin:,.0f} > Free ${free_margin:,.0f}",
                    "val": "INSUFFICIENT"
                }
                block_reason = f"INSUFFICIENT MARGIN (${req_margin:,.0f})"
            else:
                checks["margin"] = {
                    "passed": True,
                    "msg": f"Margin: Req ${req_margin:,.0f} <= Free ${free_margin:,.0f}",
                    "val": "PASS"
                }
        except Exception as e_m:
            logger.debug(f"[TradingPlan] Margin check error: {e_m}")

    passed = (block_reason == "")
    return passed, checks, block_reason


def _setup_chart_manual_lines(window, sym, is_buy, lot, sl, tp):
    """Render draggable SL and TP lines on the chart for the manual copilot order."""
    if getattr(window, "_plan_mode", "ai") != "manual":
        return
    if not hasattr(window, "plot_widget") or not window.plot_widget:
        return
    if not getattr(window, "_show_manual_preview", True):
        clear_manual_chart_lines(window)
        return

    # If Trading Plan drawer is collapsed and there is no active MT5 order,
    # do not draw unsubmitted manual draft preview lines on chart
    if hasattr(window, "frameAIArea") and not window.frameAIArea.isVisible():
        is_live = getattr(window, "is_live_position", False)
        is_pending_ord = getattr(window, "is_pending_order", False)
        if not is_live and not is_pending_ord:
            clear_manual_chart_lines(window)
            return

    info = mt5.symbol_info(sym)
    dig = info.digits if info else 2

    order_type_str = getattr(window, "_manual_order_type", "MARKET")
    is_pending = (order_type_str != "MARKET")

    if is_pending and hasattr(window, "spinManualPendingPrice") and window.spinManualPendingPrice and window.spinManualPendingPrice.value() > 0:
        entry_p = float(window.spinManualPendingPrice.value())
    else:
        tick = mt5.symbol_info_tick(sym) if mt5.terminal_info() is not None else None
        entry_p = (tick.ask if is_buy else tick.bid) if tick else getattr(window, "_last_manual_entry", 2650.0)

    is_d = getattr(window, "is_dark_theme", False)
    bull_c = "#22c55e" if is_d else "#15803D"
    bear_c = "#ef4444" if is_d else "#B91C1C"
    dir_c = bull_c if is_buy else bear_c

    # Entry line: Solid + Movable for Pending Orders; Dashed + Fixed for Market Orders
    if hasattr(window, "line_order_entry") and window.line_order_entry:
        try:
            cur_entry = float(window.line_order_entry.value())
            needs_entry = abs(cur_entry - entry_p) > 1e-6
        except Exception:
            needs_entry = True
        if needs_entry:
            window.line_order_entry.blockSignals(True)
            window.line_order_entry.setPos(entry_p)
            window.line_order_entry.blockSignals(False)
        pen_style = Qt.SolidLine if is_pending else Qt.DashLine
        window.line_order_entry.setPen(pg.mkPen(color=dir_c, width=1.2, style=pen_style))
        window.line_order_entry.setMovable(is_pending)
        dir_s = order_type_str if is_pending else ("BUY" if is_buy else "SELL")
        if hasattr(window.line_order_entry, "label") and window.line_order_entry.label:
            window.line_order_entry.label.setFormat(f"[PREVIEW] {dir_s} | {lot:.2f}L @ {entry_p:.{dig}f}  [×]")
            window.line_order_entry.label.setColor("#f8fafc")
            window.line_order_entry.label.fill = pg.mkBrush(15, 23, 42, 235)
            window.line_order_entry.label.border = pg.mkPen(color=dir_c, width=1.0)
            window.line_order_entry.label.setPosition(0.92)
            window.line_order_entry.label.setFont(pg.Qt.QtGui.QFont("Consolas", 8))
        window.line_order_entry.setVisible(True)
        if window.line_order_entry not in window.plot_widget.items():
            window.plot_widget.addItem(window.line_order_entry, ignoreBounds=True)

    # SL line (Draft Preview: Qt.DashLine)
    if hasattr(window, "line_order_sl") and window.line_order_sl:
        try:
            cur_sl = float(window.line_order_sl.value())
            needs_sl = abs(cur_sl - sl) > 1e-6
        except Exception:
            needs_sl = True
        if needs_sl:
            window.line_order_sl.blockSignals(True)
            window.line_order_sl.setPos(sl)
            window.line_order_sl.blockSignals(False)
        window.line_order_sl.setPen(pg.mkPen(color=bear_c, width=1.0, style=Qt.DashLine))
        window.line_order_sl.setMovable(True)
        if hasattr(window.line_order_sl, "label") and window.line_order_sl.label:
            window.line_order_sl.label.setFormat(f"[PREVIEW] SL | {sl:.{dig}f}  [×]")
            window.line_order_sl.label.setColor("#f8fafc")
            window.line_order_sl.label.fill = pg.mkBrush(15, 23, 42, 235)
            window.line_order_sl.label.border = pg.mkPen(color=bear_c, width=1.0)
            window.line_order_sl.label.setPosition(0.84)
            window.line_order_sl.label.setFont(pg.Qt.QtGui.QFont("Consolas", 8))
        window.line_order_sl.setVisible(True)
        if window.line_order_sl not in window.plot_widget.items():
            window.plot_widget.addItem(window.line_order_sl, ignoreBounds=True)

    # TP line (Draft Preview: Qt.DashLine)
    if hasattr(window, "line_order_tp") and window.line_order_tp:
        try:
            cur_tp = float(window.line_order_tp.value())
            needs_tp = abs(cur_tp - tp) > 1e-6
        except Exception:
            needs_tp = True
        if needs_tp:
            window.line_order_tp.blockSignals(True)
            window.line_order_tp.setPos(tp)
            window.line_order_tp.blockSignals(False)
        window.line_order_tp.setPen(pg.mkPen(color=bull_c, width=1.0, style=Qt.DashLine))
        window.line_order_tp.setMovable(True)
        if hasattr(window.line_order_tp, "label") and window.line_order_tp.label:
            window.line_order_tp.label.setFormat(f"[PREVIEW] TP | {tp:.{dig}f}  [×]")
            window.line_order_tp.label.setColor("#f8fafc")
            window.line_order_tp.label.fill = pg.mkBrush(15, 23, 42, 235)
            window.line_order_tp.label.border = pg.mkPen(color=bull_c, width=1.0)
            window.line_order_tp.label.setPosition(0.76)
            window.line_order_tp.label.setFont(pg.Qt.QtGui.QFont("Consolas", 8))
        window.line_order_tp.setVisible(True)
        if window.line_order_tp not in window.plot_widget.items():
            window.plot_widget.addItem(window.line_order_tp, ignoreBounds=True)

    # Interactive [×] dismiss handler on chart labels
    def _dismiss_manual_preview(ev=None):
        window._show_manual_preview = False
        clear_manual_chart_lines(window)
        if hasattr(window, "btnManualClearPreview") and window.btnManualClearPreview:
            window.btnManualClearPreview.setText("SHOW PREVIEW")
        if ev is not None:
            try:
                ev.accept()
            except Exception:
                pass

    for l_obj in (getattr(window, "line_order_entry", None), getattr(window, "line_order_sl", None), getattr(window, "line_order_tp", None)):
        if l_obj and hasattr(l_obj, "label") and l_obj.label:
            l_obj.label.setToolTip("Click [×] to dismiss draft order preview lines from chart")
            try:
                from pyqtgraph.Qt import QtCore, QtGui
                l_obj.label.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
            except Exception:
                pass
            l_obj.label.mouseClickEvent = _dismiss_manual_preview


def _get_manual_effective_entry_price(window, is_buy: bool, clean_sym: str) -> float:
    """Unified single-source-of-truth for manual order entry price (Pending Price vs Market Ask/Bid)."""
    order_type_str = getattr(window, "_manual_order_type", "MARKET")
    if order_type_str != "MARKET" and hasattr(window, "spinManualPendingPrice") and window.spinManualPendingPrice and window.spinManualPendingPrice.value() > 0.01:
        return float(window.spinManualPendingPrice.value())
    tick = mt5.symbol_info_tick(clean_sym) if mt5.terminal_info() is not None else None
    if tick and hasattr(tick, "ask") and isinstance(getattr(tick, "ask", None), (int, float)) and tick.ask > 0:
        return float(tick.ask if is_buy else tick.bid)
    fallback_p = getattr(window, "_last_manual_entry", 2650.50 if is_buy else 2650.25)
    if is_buy:
        if hasattr(window, "lblManualAskPrice") and window.lblManualAskPrice and window.lblManualAskPrice.text() not in ("", "0.00", "--"):
            try:
                return float(window.lblManualAskPrice.text())
            except ValueError:
                pass
        return float(getattr(window, "_last_manual_ask", fallback_p))
    else:
        if hasattr(window, "lblManualBidPrice") and window.lblManualBidPrice and window.lblManualBidPrice.text() not in ("", "0.00", "--"):
            try:
                return float(window.lblManualBidPrice.text())
            except ValueError:
                pass
        return float(getattr(window, "_last_manual_bid", fallback_p))


def _recalculate_manual_lot_and_rr(window, from_user_lot_change: bool = False):
    """Dynamically recalculate lot size, R:R ratio, dollar risk/reward when SL, TP, or Lot changes."""
    clean_sym = getattr(window, "current_sym", "XAUUSD").split("\n")[0].strip()
    is_buy = (getattr(window, "_manual_direction", "BUY") == "BUY")
    risk_pct = getattr(window, "_manual_risk_pct", 1.0)

    info = mt5.symbol_info(clean_sym)
    digits = info.digits if info else 2
    point = info.point if info and info.point > 0 else (0.01 if digits == 2 else 0.0001)

    entry_p = _get_manual_effective_entry_price(window, is_buy, clean_sym)

    window._last_manual_entry = entry_p

    sl_val = window.spinManualSL.value() if hasattr(window, "spinManualSL") else 0.0
    tp_val = window.spinManualTP.value() if hasattr(window, "spinManualTP") else 0.0

    sl_pts = abs(entry_p - sl_val)
    tp_pts = abs(tp_val - entry_p)

    acc = mt5.account_info() if mt5.terminal_info() is not None else None
    balance = float(acc.balance) if acc and acc.balance > 0 else 10000.0

    multiplier = get_symbol_multiplier(clean_sym, info)
    pip_unit = get_symbol_pip_unit(clean_sym, digits, point)

    min_lot = float(info.volume_min) if (info and hasattr(info, "volume_min") and info.volume_min) else 0.01

    if from_user_lot_change and hasattr(window, "spinManualLot") and window.spinManualLot:
        window._user_custom_lot = True
        lot = round(window.spinManualLot.value(), 2)
        apply_playbook_cards_theme(window, getattr(window, "is_dark_theme", False))
    elif getattr(window, "_user_custom_lot", False) and hasattr(window, "spinManualLot") and window.spinManualLot and window.spinManualLot.value() > 0:
        lot = round(window.spinManualLot.value(), 2)
    else:
        lot, _ = calculate_manual_quant_lot(clean_sym, sl_pts, risk_pct, balance=balance)

    # Compliance Mode Evaluation: DISCRETIONARY vs SYSTEM GUARD
    compliance_mode = getattr(window, "_manual_compliance_mode", "DISCRETIONARY")
    macro_bias = "NEUTRAL"
    is_pro_trend = False
    is_counter_trend = False
    try:
        from backend.core.macro_context_bus import MacroContextBus
        prof = MacroContextBus.get_instance().get_profile(clean_sym)
        if prof and hasattr(prof, "directional_bias"):
            macro_bias = prof.directional_bias.upper()
        is_pro_trend = (is_buy and "BULL" in macro_bias) or (not is_buy and "BEAR" in macro_bias)
        is_counter_trend = (is_buy and "BEAR" in macro_bias) or (not is_buy and "BULL" in macro_bias)
    except Exception:
        pass

    # If in SYSTEM GUARD and counter-trend, automatically scale down volume by 50%
    if compliance_mode == "SYSTEM_GUARD" and is_counter_trend:
        lot = max(min_lot, round(lot * 0.5, 2))

    if hasattr(window, "spinManualLot") and window.spinManualLot:
        window.spinManualLot.blockSignals(True)
        window.spinManualLot.setValue(lot)
        window.spinManualLot.blockSignals(False)

    risk_dlr = round(sl_pts * lot * multiplier, 2)
    risk_pct = round((risk_dlr / balance) * 100.0, 1) if balance > 0 else 1.0
    reward_dlr = round(tp_pts * lot * multiplier, 2)
    sl_pips = sl_pts / pip_unit if pip_unit > 0 else sl_pts
    tp_pips = tp_pts / pip_unit if pip_unit > 0 else tp_pts

    rr_ratio = round(tp_pts / sl_pts, 1) if sl_pts > 0.00001 else 2.0

    # Update UI Labels
    if hasattr(window, "lblManualLotVal") and window.lblManualLotVal and window.lblManualLotVal is not getattr(window, "spinManualLot", None):
        window.lblManualLotVal.setText(f"{lot:.2f} LOTS")
    if hasattr(window, "lblManualSLPips") and window.lblManualSLPips:
        window.lblManualSLPips.setText(f"-{sl_pips:.1f} pips")
    if hasattr(window, "lblManualTPPips") and window.lblManualTPPips:
        window.lblManualTPPips.setText(f"+{tp_pips:.1f} pips")

    # Split Risk (Red) / Reward (Green)
    if hasattr(window, "lblManualRiskPart") and window.lblManualRiskPart:
        window.lblManualRiskPart.setText(f"-${risk_dlr:.2f} ({risk_pct:.1f}%)")
    if hasattr(window, "lblManualRewardPart") and window.lblManualRewardPart:
        window.lblManualRewardPart.setText(f"+${reward_dlr:.2f} ({rr_ratio:.1f}R)")
    if hasattr(window, "lblManualLotSummary") and window.lblManualLotSummary:
        window.lblManualLotSummary.setText(
            f"-${risk_dlr:.2f} ({risk_pct:.1f}%) / +${reward_dlr:.2f} ({rr_ratio:.1f}R)"
        )

    # Evaluate compliance
    passed, checks, block_reason = evaluate_manual_compliance(window, clean_sym)

    # Update checklist indicators
    is_d = getattr(window, "is_dark_theme", False)
    bull_c = "#22c55e" if is_d else "#15803d"
    bear_c = "#ef4444" if is_d else "#dc2626"

    for chk_key, lbl_val_name in [
        ("drawdown", "lblGateCheck1Val"),
        ("news", "lblGateCheck2Val"),
        ("max_trades", "lblGateCheck3Val"),
        ("spread", "lblGateCheck4Val"),
    ]:
        v_widget = getattr(window, lbl_val_name, None)
        c_info = checks.get(chk_key, {})
        c_pass = c_info.get("passed", True)
        if v_widget:
            try:
                v_widget.setText(c_info.get("val", "PASS"))
                v_widget.setToolTip(c_info.get("msg", ""))
                v_widget.setStyleSheet(
                    f"color: {bull_c if c_pass else bear_c}; font-family: Consolas, monospace; "
                    f"font-size: 8.5px; font-weight: bold; border: none; background: transparent;"
                )
            except RuntimeError:
                pass
        row_lbl = getattr(window, lbl_val_name.replace("Val", ""), None)
        if row_lbl:
            try:
                row_lbl.setToolTip(c_info.get("msg", ""))
            except RuntimeError:
                pass

    # Update execute button with exact price or modification target
    dir_str = getattr(window, "_manual_direction", "BUY")
    order_type_str = getattr(window, "_manual_order_type", "MARKET")
    action_label = order_type_str if order_type_str != "MARKET" else dir_str
    mod_ticket = getattr(window, "_modifying_ticket", None)
    is_mod_pos = getattr(window, "_modifying_is_position", False)

    if hasattr(window, "btnManualExecute") and window.btnManualExecute:
        if mod_ticket:
            action_verb = "UPDATE SL/TP" if is_mod_pos else "MODIFY ORDER"
            window.btnManualExecute.setEnabled(True)
            window.btnManualExecute.setText(f"{action_verb} #{mod_ticket}")
            window.btnManualExecute.setToolTip(f"Commit modification for MT5 #{mod_ticket}")
        elif passed:
            window.btnManualExecute.setEnabled(True)
            window.btnManualExecute.setText(f"{action_label} {lot:.2f} LOTS {entry_p:.{digits}f}")
            window.btnManualExecute.setToolTip(f"Send institutional {action_label} order with {risk_pct}% risk")
        else:
            window.btnManualExecute.setEnabled(False)
            window.btnManualExecute.setText(f"LOCKED: {block_reason}")
            window.btnManualExecute.setToolTip(f"Order locked by quant guardrails: {block_reason}")
        window.btnManualExecute.setProperty("direction", dir_str)
        window.btnManualExecute.style().unpolish(window.btnManualExecute)
        window.btnManualExecute.style().polish(window.btnManualExecute)

    # Update Macro Copilot Advisory Badge (Dynamic mode awareness: DISCRETIONARY vs SYSTEM GUARD)
    if hasattr(window, "lblManualCopilotBadge") and window.lblManualCopilotBadge:
        try:
            bias_tag = "BULL" if "BULL" in macro_bias else ("BEAR" if "BEAR" in macro_bias else "NEUT")
            if compliance_mode == "SYSTEM_GUARD":
                if is_counter_trend:
                    badge_t = f"COUNTER-TREND ({bias_tag} · 50% VOL)"
                    b_color = "#f59e0b" if is_d else "#b45309"
                    b_bg = "#241805" if is_d else "#fef3c7"
                    b_bdr = "#b45309" if is_d else "#fcd34d"
                elif is_pro_trend:
                    badge_t = f"PRO-TREND ({bias_tag} · 100% VOL)"
                    b_color = "#22c55e" if is_d else "#15803d"
                    b_bg = "#0d2818" if is_d else "#f0fdf4"
                    b_bdr = "#15803d" if is_d else "#86efac"
                else:
                    badge_t = "SYSTEM GUARD (NEUTRAL)"
                    b_color = "#94a3b8" if is_d else "#64748b"
                    b_bg = "#1e293b" if is_d else "#f1f5f9"
                    b_bdr = "#334155" if is_d else "#cbd5e1"
            else:
                if is_counter_trend:
                    badge_t = f"COUNTER-TREND ({bias_tag})"
                    b_color = "#f59e0b" if is_d else "#b45309"
                    b_bg = "#241805" if is_d else "#fef3c7"
                    b_bdr = "#b45309" if is_d else "#fcd34d"
                elif is_pro_trend:
                    badge_t = f"PRO-TREND ({bias_tag})"
                    b_color = "#22c55e" if is_d else "#15803d"
                    b_bg = "#0d2818" if is_d else "#f0fdf4"
                    b_bdr = "#15803d" if is_d else "#86efac"
                else:
                    badge_t = "MACRO NEUTRAL"
                    b_color = "#94a3b8" if is_d else "#64748b"
                    b_bg = "#1e293b" if is_d else "#f1f5f9"
                    b_bdr = "#334155" if is_d else "#cbd5e1"

            window.lblManualCopilotBadge.setText(badge_t)
            window.lblManualCopilotBadge.setStyleSheet(
                f"background-color: {b_bg}; color: {b_color}; border: 1px solid {b_bdr}; "
                f"font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; "
                f"border-radius: 2px; padding: 1px 5px;"
            )
            mode_desc = "System Guard Active: Counter-trend orders automatically scale down to 50% volume." if compliance_mode == "SYSTEM_GUARD" else "Discretionary Active: 100% human discretion, full volume."
            window.lblManualCopilotBadge.setToolTip(
                f"Compliance Mode: {compliance_mode}\n"
                f"Macro Directional Bias: {macro_bias}\n"
                f"{mode_desc}"
            )
        except Exception:
            pass

    # Also update chart lines (suppress manual preview lines when modifying an existing broker ticket)
    if getattr(window, "_show_manual_preview", True) and not getattr(window, "_modifying_ticket", None):
        _setup_chart_manual_lines(window, clean_sym, is_buy, lot, sl_val, tp_val)
    else:
        clear_manual_chart_lines(window)


def sync_live_position_to_ai_plan(window):
    """Dynamically synchronizes live open MT5 positions and pending orders with on-chart lines & AI Strategy Card."""
    if getattr(window, "_plan_mode", "ai") == "manual":
        return

    clean_sym = getattr(window, "current_sym", "").split("\n")[0].strip()
    if not clean_sym:
        return

    try:
        if mt5.terminal_info() is None:
            return

        pos = None
        ticket = getattr(window, "live_ticket", None)
        if ticket:
            try:
                positions = mt5.positions_get(ticket=int(ticket))
                if positions and len(positions) > 0:
                    pos_sym = getattr(positions[0], "symbol", "").split(".")[0].upper()
                    if pos_sym == clean_sym.split(".")[0].upper():
                        pos = positions[0]
                    else:
                        window.live_ticket = None
                        window.is_live_position = False
            except Exception:
                pos = None
        if pos is None:
            positions = mt5.positions_get(symbol=clean_sym)
            if positions and len(positions) > 0:
                pos = positions[0]

        # Check for MT5 pending orders if no open position exists
        pending_order = None
        if pos is None:
            try:
                p_orders = mt5.orders_get(symbol=clean_sym)
                if p_orders and len(p_orders) > 0:
                    pending_order = p_orders[0]
            except Exception:
                pending_order = None

        if not hasattr(window, "active_signals_by_symbol"):
            window.active_signals_by_symbol = {}

        if pos is None and pending_order is None:
            was_live = getattr(window, "is_live_position", False)
            was_pending = getattr(window, "is_pending_order", False)
            window.is_live_position = False
            window.is_pending_order = False
            window.live_ticket = None

            # If an active position or pending order in MT5 just closed/cancelled, re-evaluate quantitative strategy immediately
            if was_live or was_pending:
                if hasattr(window, "lblModelSubtitle") and window.lblModelSubtitle:
                    window.lblModelSubtitle.setText("SETUP MODEL")
                if hasattr(window, "lblOrderBudgetTitle") and window.lblOrderBudgetTitle:
                    window.lblOrderBudgetTitle.setText("ORDER & RISK BUDGET")
                if hasattr(window, "lblOrderTypeBadge") and window.lblOrderTypeBadge:
                    window.lblOrderTypeBadge.setText("NO ORDER")
                if hasattr(window, "lblEntryVal") and window.lblEntryVal:
                    window.lblEntryVal.setText("--")
                if hasattr(window, "lblSLVal") and window.lblSLVal:
                    window.lblSLVal.setText("--")
                if hasattr(window, "lblTPVal") and window.lblTPVal:
                    window.lblTPVal.setText("--")
                if hasattr(window, "lblSizeVal") and window.lblSizeVal:
                    window.lblSizeVal.setText("--")
                if hasattr(window, "btnApproveOrder") and window.btnApproveOrder:
                    window.btnApproveOrder.setText("AWAITING STRATEGY SIGNAL")
                    window.btnApproveOrder.setEnabled(False)
                clear_manual_chart_lines(window)
                from frontend.controllers.chart.ai_panel_controller import _run_analysis
                _run_analysis(window, clean_sym, force=True)
                return

            # Check if there is an active proposal waiting for operator approval for clean_sym
            curr_sig = window.active_signals_by_symbol.get(clean_sym, {})
            if curr_sig.get("has_signal") and not curr_sig.get("is_live_position") and not curr_sig.get("is_pending_order"):
                return

            # In standby mode without an open MT5 position, preserve the strategy's calculated
            # dynamic checklist and do not clobber Card 1 / Card 2 on every market tick.
            return

        if pos is not None:
            ticket = pos.ticket
            vol = float(pos.volume)
            pnl = float(pos.profit)
            open_p = float(pos.price_open)
            pos_sl = float(pos.sl)
            pos_tp = float(pos.tp)
            pos_type = "BUY" if pos.type == 0 else "SELL"

            info = mt5.symbol_info(clean_sym)
            digits = info.digits if info else (2 if open_p > 10 else 5)

            window.is_live_position = True
            window.is_pending_order = False
            window.live_ticket = ticket
            pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"

            if hasattr(window, "lblSizeVal") and window.lblSizeVal:
                window.lblSizeVal.setText(f"{vol:.2f} LOTS (PNL: {pnl_str})")

            if hasattr(window, "lblEntryVal") and window.lblEntryVal:
                window.lblEntryVal.setText(f"{open_p:.{digits}f}")

            if hasattr(window, "lblSLVal") and window.lblSLVal:
                window.lblSLVal.setText(f"{pos_sl:.{digits}f}  (LIVE)" if pos_sl > 0 else "NO SL")

            if hasattr(window, "lblTPVal") and window.lblTPVal:
                window.lblTPVal.setText(f"{pos_tp:.{digits}f}  (LIVE)" if pos_tp > 0 else "NO TP")

            if hasattr(window, "lblOrderTypeBadge") and window.lblOrderTypeBadge:
                window.lblOrderTypeBadge.setText(pos_type)

            if hasattr(window, "lblOrderBudgetTitle") and window.lblOrderBudgetTitle:
                window.lblOrderBudgetTitle.setText("LIVE POSITION & RISK")

            if hasattr(window, "lblModelSubtitle") and window.lblModelSubtitle:
                window.lblModelSubtitle.setText(f"POSITION IN MARKET (#{ticket})")

            # Store active signal data for future tab switches or reopenings
            if not hasattr(window, "active_signal_data") or not isinstance(window.active_signal_data, dict):
                window.active_signal_data = {}
            live_payload = {
                "sym": clean_sym,
                "has_signal": True,
                "signal_type": pos_type,
                "entry": open_p,
                "sl": pos_sl if pos_sl > 0 else 0.0,
                "tp": pos_tp if pos_tp > 0 else 0.0,
                "is_live_position": True,
                "is_pending_order": False,
                "live_ticket": ticket,
                "live_profit": pnl,
                "live_volume": vol,
            }
            window.active_signal_data.update(live_payload)
            window.active_signals_by_symbol[clean_sym] = window.active_signal_data

            # Draw / update on-chart order lines for the live MT5 position (only real SL/TP from broker)
            update_order_proposal_html(
                window,
                sym=clean_sym,
                entry=open_p,
                sl=pos_sl if pos_sl > 0 else 0.0,
                tp=pos_tp if pos_tp > 0 else 0.0,
                has_signal=True,
                signal_type=pos_type,
                is_live_position=True,
                live_ticket=ticket,
                live_volume=vol,
                live_profit=pnl,
                digits=digits,
            )

        elif pending_order is not None:
            t_ord = pending_order.ticket
            vol_ord = float(pending_order.volume_initial)
            open_ord = float(pending_order.price_open)
            ord_sl = float(pending_order.sl)
            ord_tp = float(pending_order.tp)
            type_str = "BUY LIMIT" if pending_order.type == mt5.ORDER_TYPE_BUY_LIMIT else (
                "SELL LIMIT" if pending_order.type == mt5.ORDER_TYPE_SELL_LIMIT else (
                    "BUY STOP" if pending_order.type == mt5.ORDER_TYPE_BUY_STOP else "SELL STOP"
                )
            )
            pos_type = "BUY" if "BUY" in type_str else "SELL"

            info = mt5.symbol_info(clean_sym)
            digits = info.digits if info else (2 if open_ord > 10 else 5)

            window.is_live_position = False
            window.is_pending_order = True
            window.live_ticket = t_ord

            if hasattr(window, "lblSizeVal") and window.lblSizeVal:
                window.lblSizeVal.setText(f"{vol_ord:.2f} LOTS (PENDING)")

            if hasattr(window, "lblEntryVal") and window.lblEntryVal:
                window.lblEntryVal.setText(f"{open_ord:.{digits}f}")

            if hasattr(window, "lblSLVal") and window.lblSLVal:
                window.lblSLVal.setText(f"{ord_sl:.{digits}f}  (PENDING)" if ord_sl > 0 else "NO SL")

            if hasattr(window, "lblTPVal") and window.lblTPVal:
                window.lblTPVal.setText(f"{ord_tp:.{digits}f}  (PENDING)" if ord_tp > 0 else "NO TP")

            if hasattr(window, "lblOrderTypeBadge") and window.lblOrderTypeBadge:
                window.lblOrderTypeBadge.setText(type_str)

            if hasattr(window, "lblOrderBudgetTitle") and window.lblOrderBudgetTitle:
                window.lblOrderBudgetTitle.setText("PENDING ORDER & RISK")

            if hasattr(window, "lblModelSubtitle") and window.lblModelSubtitle:
                window.lblModelSubtitle.setText(f"PENDING ORDER (#{t_ord})")

            # Store active signal data for pending order
            if not hasattr(window, "active_signal_data") or not isinstance(window.active_signal_data, dict):
                window.active_signal_data = {}
            pending_payload = {
                "sym": clean_sym,
                "has_signal": True,
                "signal_type": pos_type,
                "entry": open_ord,
                "sl": ord_sl if ord_sl > 0 else 0.0,
                "tp": ord_tp if ord_tp > 0 else 0.0,
                "is_live_position": False,
                "is_pending_order": True,
                "live_ticket": t_ord,
                "live_volume": vol_ord,
            }
            window.active_signal_data.update(pending_payload)
            window.active_signals_by_symbol[clean_sym] = window.active_signal_data

            # Draw / update on-chart order lines for the MT5 pending order (only real SL/TP from broker)
            update_order_proposal_html(
                window,
                sym=clean_sym,
                entry=open_ord,
                sl=ord_sl if ord_sl > 0 else 0.0,
                tp=ord_tp if ord_tp > 0 else 0.0,
                has_signal=True,
                signal_type=pos_type,
                is_pending_order=True,
                pending_ticket=t_ord,
                live_volume=vol_ord,
                digits=digits,
            )
    except Exception as e:
        logger.debug(f"[sync_live_position_to_ai_plan] Error: {e}")


def populate_manual_order_for_modification(window, ticket, order_type_str, volume, price, sl=0.0, tp=0.0, is_position=False):
    """
    Prefills the Manual Order Copilot to modify an existing MT5 broker order or position.
    Seamlessly switches drawer to MANUAL ORDER mode, binds modification state, and configures spinboxes.
    """
    if not hasattr(window, "containerPlanManual"):
        return

    # 1. Switch to Manual Order tab
    if hasattr(window, "_switch_plan_mode"):
        window._switch_plan_mode("manual")
    elif hasattr(window, "btnPlanModeManual"):
        window.btnPlanModeManual.click()

    # 2. Bind modification ticket
    window._modifying_ticket = int(ticket)
    window._modifying_is_position = bool(is_position)

    # 3. Direction
    is_buy = ("BUY" in str(order_type_str).upper())
    window._manual_direction = "BUY" if is_buy else "SELL"
    if hasattr(window, "btnManualBuy") and window.btnManualBuy:
        window.btnManualBuy.setProperty("selected", "true" if is_buy else "false")
        window.btnManualBuy.style().unpolish(window.btnManualBuy)
        window.btnManualBuy.style().polish(window.btnManualBuy)
    if hasattr(window, "btnManualSell") and window.btnManualSell:
        window.btnManualSell.setProperty("selected", "true" if not is_buy else "false")
        window.btnManualSell.style().unpolish(window.btnManualSell)
        window.btnManualSell.style().polish(window.btnManualSell)

    # 4. Order Type
    clean_type = str(order_type_str).upper().replace("_", " ").strip()
    if is_position:
        clean_type = "MARKET"
    window._manual_order_type = clean_type
    if hasattr(window, "comboManualOrderType") and window.comboManualOrderType:
        idx = window.comboManualOrderType.findText(clean_type)
        if idx >= 0:
            window.comboManualOrderType.blockSignals(True)
            window.comboManualOrderType.setCurrentIndex(idx)
            window.comboManualOrderType.blockSignals(False)

    # 5. Pending Price
    clean_sym = getattr(window, "current_sym", "XAUUSD").split("\n")[0].strip()
    info = mt5.symbol_info(clean_sym)
    digits = info.digits if info else (2 if price > 10 else 5)
    if not is_position and hasattr(window, "spinManualPendingPrice") and window.spinManualPendingPrice:
        window.spinManualPendingPrice.blockSignals(True)
        window.spinManualPendingPrice.setValue(round(float(price), digits))
        window.spinManualPendingPrice.blockSignals(False)

    # 6. Volume
    if hasattr(window, "spinManualLot") and window.spinManualLot:
        window.spinManualLot.blockSignals(True)
        window.spinManualLot.setValue(round(float(volume), 2))
        window.spinManualLot.blockSignals(False)
        window._user_custom_lot = True

    # 7. SL and TP
    if hasattr(window, "spinManualSL") and window.spinManualSL:
        window.spinManualSL.blockSignals(True)
        window.spinManualSL.setValue(round(float(sl), digits) if sl and float(sl) > 0 else 0.0)
        window.spinManualSL.blockSignals(False)

    if hasattr(window, "spinManualTP") and window.spinManualTP:
        window.spinManualTP.blockSignals(True)
        window.spinManualTP.setValue(round(float(tp), digits) if tp and float(tp) > 0 else 0.0)
        window.spinManualTP.blockSignals(False)

    # 8. Execution Button & Gate Title
    action_verb = "UPDATE SL/TP" if is_position else "MODIFY ORDER"
    if hasattr(window, "btnManualExecute") and window.btnManualExecute:
        window.btnManualExecute.setEnabled(True)
        window.btnManualExecute.setText(f"{action_verb} #{ticket}")
        window.btnManualExecute.setToolTip(f"Commit modification for MT5 #{ticket}")
        window.btnManualExecute.setProperty("direction", "BUY" if is_buy else "SELL")
        window.btnManualExecute.style().unpolish(window.btnManualExecute)
        window.btnManualExecute.style().polish(window.btnManualExecute)

    if hasattr(window, "lblManualGateTitle") and window.lblManualGateTitle:
        window.lblManualGateTitle.setText(f"ORDER MODIFICATION (#{ticket})")

    # 9. Recalculate metrics & preview
    _recalculate_manual_lot_and_rr(window)

    # 10. Open drawer
    if hasattr(window, "_open_ai_drawer"):
        window._open_ai_drawer()
    elif hasattr(window, "frameAIArea") and window.frameAIArea:
        window.frameAIArea.setVisible(True)


def sync_manual_copilot_quotes(window):
    """Syncs live Bid/Ask prices and default SL/TP values for the Manual Quant Copilot."""
    clean_sym = getattr(window, "current_sym", "XAUUSD").split("\n")[0].strip()
    info = mt5.symbol_info(clean_sym)
    digits = info.digits if info else 2
    point = info.point if info and info.point > 0 else (0.01 if digits == 2 else 0.0001)
    pip_unit = get_symbol_pip_unit(clean_sym, digits, point)
    pt_unit = (pip_unit / 10.0) if pip_unit > 0 else (point if point > 0 else 0.01)

    tick = mt5.symbol_info_tick(clean_sym) if mt5.terminal_info() is not None else None
    if tick:
        ask = tick.ask
        bid = tick.bid
        spd = round((ask - bid) / pt_unit, 1)
    else:
        ask = None
        bid = None
        if hasattr(window, "lblManualAskPrice") and window.lblManualAskPrice and window.lblManualAskPrice.text() not in ("", "0.00", "--"):
            try:
                ask = float(window.lblManualAskPrice.text())
            except ValueError:
                pass
        if hasattr(window, "lblManualBidPrice") and window.lblManualBidPrice and window.lblManualBidPrice.text() not in ("", "0.00", "--"):
            try:
                bid = float(window.lblManualBidPrice.text())
            except ValueError:
                pass
        if ask is None:
            ask = getattr(window, "_last_manual_ask", 2650.25)
        if bid is None:
            bid = getattr(window, "_last_manual_bid", 2650.00)
        spd = round((ask - bid) / pt_unit, 1) if pt_unit > 0 else 25.0

    window._last_manual_ask = ask
    window._last_manual_bid = bid
    is_buy = (getattr(window, "_manual_direction", "BUY") == "BUY")
    ref_p = ask if is_buy else bid
    old_entry = getattr(window, "_last_manual_entry", ref_p)
    window._last_manual_entry = ref_p

    if hasattr(window, "lblManualAskPrice") and window.lblManualAskPrice:
        window.lblManualAskPrice.setText(f"{ask:.{digits}f}")
    if hasattr(window, "lblManualBidPrice") and window.lblManualBidPrice:
        window.lblManualBidPrice.setText(f"{bid:.{digits}f}")
    if hasattr(window, "lblManualSpread") and window.lblManualSpread:
        window.lblManualSpread.setText(f"SPREAD: {spd} PTS")

    # Initialize or symmetrically invert spinboxes if at 0 or invalid orientation
    if hasattr(window, "spinManualSL") and hasattr(window, "spinManualTP"):
        cur_sl = window.spinManualSL.value()
        cur_tp = window.spinManualTP.value()

        sym_u = clean_sym.upper()
        if "XAU" in sym_u or "GOLD" in sym_u:
            default_dist = 2.50
        elif "BTC" in sym_u or "ETH" in sym_u:
            default_dist = 500.0
        elif any(c in sym_u for c in ["US30", "NAS100", "SPX500", "GER40"]):
            default_dist = 50.0
        elif "JPY" in sym_u:
            default_dist = 0.35
        else:
            default_dist = 0.0025

        window.spinManualSL.setDecimals(digits)
        window.spinManualTP.setDecimals(digits)
        window.spinManualSL.setRange(0.00001, 1000000.0)
        window.spinManualTP.setRange(0.00001, 1000000.0)

        # Check if stops need re-alignment (uninitialized or wrong orientation for direction or symbol changed)
        sym_changed = (clean_sym != getattr(window, "_last_reseed_sym", None))
        window._last_reseed_sym = clean_sym

        # Reseed pending entry price if symbol changed or currently invalid <= 0.01
        if hasattr(window, "spinManualPendingPrice") and window.spinManualPendingPrice:
            window.spinManualPendingPrice.setDecimals(digits)
            cur_p_val = window.spinManualPendingPrice.value()
            pt_dist = max(pip_unit * 15.0, 50 * point)
            order_type_s = getattr(window, "_manual_order_type", "MARKET")
            if sym_changed or cur_p_val <= 0.01 or (ref_p > 0 and abs(cur_p_val - ref_p) > ref_p * 0.5):
                if order_type_s == "BUY LIMIT":
                    window.spinManualPendingPrice.setValue(round(bid - pt_dist, digits))
                elif order_type_s == "SELL LIMIT":
                    window.spinManualPendingPrice.setValue(round(ask + pt_dist, digits))
                elif order_type_s == "BUY STOP":
                    window.spinManualPendingPrice.setValue(round(ask + pt_dist, digits))
                elif order_type_s == "SELL STOP":
                    window.spinManualPendingPrice.setValue(round(bid - pt_dist, digits))
                else:
                    window.spinManualPendingPrice.setValue(round(ref_p, digits))

        order_type_s = getattr(window, "_manual_order_type", "MARKET")
        if order_type_s != "MARKET" and hasattr(window, "spinManualPendingPrice") and window.spinManualPendingPrice and window.spinManualPendingPrice.value() > 0.01:
            ref_p_stops = float(window.spinManualPendingPrice.value())
        else:
            ref_p_stops = ref_p

        needs_realign = sym_changed or (cur_sl <= 0.0 or cur_tp <= 0.0)
        if not needs_realign:
            if is_buy and (cur_sl >= ref_p_stops or cur_tp <= ref_p_stops):
                needs_realign = True
            elif not is_buy and (cur_sl <= ref_p_stops or cur_tp >= ref_p_stops):
                needs_realign = True

        if needs_realign:
            if sym_changed:
                dist_sl = default_dist
                dist_tp = default_dist * 2.0
            else:
                dist_sl = abs(old_entry - cur_sl) if cur_sl > 0.0 and abs(old_entry - cur_sl) > 0.00001 else default_dist
                dist_tp = abs(cur_tp - old_entry) if cur_tp > 0.0 and abs(cur_tp - old_entry) > 0.00001 else (dist_sl * 2.0)

            new_sl = round(ref_p_stops - dist_sl if is_buy else ref_p_stops + dist_sl, digits)
            new_tp = round(ref_p_stops + dist_tp if is_buy else ref_p_stops - dist_tp, digits)

            window.spinManualSL.blockSignals(True)
            window.spinManualTP.blockSignals(True)
            window.spinManualSL.setValue(new_sl)
            window.spinManualTP.setValue(new_tp)
            window.spinManualSL.blockSignals(False)
            window.spinManualTP.blockSignals(False)

    _recalculate_manual_lot_and_rr(window)


def execute_manual_quant_order(window):
    """Executes the validated manual quant market order via ExecutionManager."""
    if hasattr(window, "spinManualLot") and window.spinManualLot:
        try:
            window.spinManualLot.interpretText()
        except Exception:
            pass
    clean_sym = getattr(window, "current_sym", "XAUUSD").split("\n")[0].strip()
    is_buy = (getattr(window, "_manual_direction", "BUY") == "BUY")
    risk_pct = getattr(window, "_manual_risk_pct", 1.0)

    # 1. Pre-trade compliance re-check
    passed, checks, block_reason = evaluate_manual_compliance(window, clean_sym)
    if not passed:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(
            window,
            "Execution Blocked by Quant Guardrail",
            f"Pre-Trade Compliance failed:\n\n{block_reason}\n\nExecution has been safely intercepted to protect capital."
        )
        return

    sl_p = window.spinManualSL.value() if hasattr(window, "spinManualSL") else 0.0
    tp_p = window.spinManualTP.value() if hasattr(window, "spinManualTP") else 0.0

    entry_p = _get_manual_effective_entry_price(window, is_buy, clean_sym)
    sl_pts = abs(entry_p - sl_p)
    if hasattr(window, "spinManualLot") and window.spinManualLot and window.spinManualLot.value() > 0:
        lot_size = round(window.spinManualLot.value(), 2)
    else:
        lot_size, _ = calculate_manual_quant_lot(clean_sym, sl_pts, risk_pct)

    # Orientation verification
    if sl_p > 0 and ((is_buy and sl_p >= entry_p) or (not is_buy and sl_p <= entry_p)):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(
            window,
            "Invalid Stop Loss",
            f"Stop loss ({sl_p}) is on the illegal side of entry ({entry_p}) for a {('BUY' if is_buy else 'SELL')} order."
        )
        return

    exec_mgr = None
    if hasattr(window, "quant_terminal") and hasattr(window.quant_terminal, "exec_mgr"):
        exec_mgr = window.quant_terminal.exec_mgr
    if not exec_mgr:
        from backend.infrastructure.brokers.execution_manager import ExecutionManager
        exec_mgr = ExecutionManager(slippage=20, magic_number=999999)

    from backend.core.event_bus import event_bus
    dir_str = "BUY" if is_buy else "SELL"

    mod_ticket = getattr(window, "_modifying_ticket", None)
    is_modifying_pos = getattr(window, "_modifying_is_position", False)

    # CASE A: Modifying an existing MT5 broker order or position
    if mod_ticket:
        if mt5.terminal_info() is not None:
            if is_modifying_pos:
                order_res = exec_mgr.modify_position(
                    int(mod_ticket),
                    sl=sl_p,
                    tp=tp_p
                )
            else:
                pending_price = 0.0
                if hasattr(window, "spinManualPendingPrice") and window.spinManualPendingPrice:
                    pending_price = window.spinManualPendingPrice.value()
                order_res = exec_mgr.modify_pending_order(
                    int(mod_ticket),
                    price=pending_price,
                    sl=sl_p,
                    tp=tp_p
                )
        else:
            order_res = {"status": "success", "ticket": mod_ticket}

        if order_res and order_res.get("status") == "success":
            window._modifying_ticket = None
            window._modifying_is_position = False
            if hasattr(window, "lblManualGateTitle") and window.lblManualGateTitle:
                window.lblManualGateTitle.setText("PRE-TRADE COMPLIANCE GATE")
            if hasattr(window, "btnManualExecute"):
                window.btnManualExecute.setText(f"MODIFIED #{mod_ticket}")
                window.btnManualExecute.setEnabled(False)
                QTimer.singleShot(3000, lambda: _recalculate_manual_lot_and_rr(window))
            event_bus.log_event.emit("", "SUCCESS", f"Đã cập nhật lệnh #{mod_ticket} thành công trên sàn MT5", "#10b981")
            if hasattr(window, "sync_chart_orders"):
                window.sync_chart_orders()
            return
        else:
            err_msg = order_res.get("msg", "Error") if order_res else "Failed to modify order"
            event_bus.log_event.emit("", "ERROR", f"Không thể cập nhật lệnh #{mod_ticket}: {err_msg}", "#ef4444")
            if hasattr(window, "btnManualExecute"):
                window.btnManualExecute.setText("RETRY MODIFY")
                window.btnManualExecute.setEnabled(True)
            return

    # CASE B: Standard New Order Execution
    order_res = None
    _order_type_str = getattr(window, "_manual_order_type", "MARKET")

    if mt5.terminal_info() is not None:
        if _order_type_str == "MARKET":
            order_res = exec_mgr.execute_market_order(
                symbol=clean_sym,
                is_buy=is_buy,
                volume=lot_size,
                sl_price=sl_p,
                tp_price=tp_p,
                comment="VECTRA_Manual",
                magic=0
            )
        else:
            # Pending order: BUY_LIMIT / SELL_LIMIT / BUY_STOP / SELL_STOP
            pending_price = 0.0
            if hasattr(window, "spinManualPendingPrice") and window.spinManualPendingPrice:
                pending_price = window.spinManualPendingPrice.value()
            if pending_price <= 0:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    window,
                    "Missing Entry Price",
                    f"Please enter a valid pending entry price for {_order_type_str} order."
                )
                return
            # Convert "BUY LIMIT" -> "BUY_LIMIT" for ExecutionManager
            mt5_order_type_key = _order_type_str.replace(" ", "_")
            order_res = exec_mgr.execute_pending_order(
                symbol=clean_sym,
                order_type=mt5_order_type_key,
                price=pending_price,
                volume=lot_size,
                sl_price=sl_p,
                tp_price=tp_p,
                comment="VECTRA_Manual_Pending",
                magic=0
            )
    else:
        order_res = {"status": "success", "ticket": int(time.time()) % 1000000, "price": entry_p}

    if order_res and order_res.get("status") == "success":
        ticket = order_res.get("ticket", "OK")
        if hasattr(window, "btnManualExecute"):
            window.btnManualExecute.setText(f"FILLED #{ticket}")
            window.btnManualExecute.setEnabled(False)
            QTimer.singleShot(4000, lambda: _recalculate_manual_lot_and_rr(window))
        event_bus.log_event.emit("", "SUCCESS", f"VECTRA Manual {_order_type_str} Filled: {dir_str} {lot_size:.2f} lots {clean_sym} #{ticket}", "#10b981")

        try:
            from backend.database.db_manager import DatabaseManager
            db = DatabaseManager()
            if isinstance(ticket, int):
                db.record_open_trade(
                    ticket=ticket,
                    symbol=clean_sym,
                    order_type=dir_str,
                    volume=lot_size,
                    open_price=entry_p,
                    sl=sl_p,
                    tp=tp_p,
                    comment="VECTRA_Manual",
                )
        except Exception as e_db:
            logger.debug(f"[TradingPlan] DB record manual order error: {e_db}")

        try:
            from backend.infrastructure.notifications.telegram_notifier import telegram_notifier
            dig = digits if "digits" in locals() else (2 if entry_p > 10 else 5)
            telegram_notifier.send_message(
                f"[EXEC] <b>MANUAL ORDER FILLED: {dir_str} {clean_sym}</b>\n"
                f"Ticket: <b>#{ticket}</b>\n"
                f"Volume: <b>{lot_size:.2f} Lots</b> @ <b>{entry_p:.{dig}f}</b>\n"
                f"SL: <b>{sl_p:.{dig}f}</b> | TP: <b>{tp_p:.{dig}f}</b>",
                category="fill",
            )
        except Exception as e_tg:
            logger.debug(f"[TradingPlan] Telegram manual notification error: {e_tg}")

        if hasattr(window, "quant_terminal") and hasattr(window.quant_terminal, "blotter_buttons"):
            qt = window.quant_terminal
            if "active" in qt.blotter_buttons:
                qt.blotter_buttons["active"].click()
    else:
        err_msg = order_res.get("msg", "Rejected") if order_res else "Broker disconnected"
        if hasattr(window, "btnManualExecute"):
            window.btnManualExecute.setText(f"RETRY: {err_msg[:16]}")
            window.btnManualExecute.setEnabled(True)
        event_bus.log_event.emit("", "ERROR", f"Manual order rejected: {err_msg}", "#ef4444")
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(window, "Execution Error", f"MT5 rejected manual order:\n\n{err_msg}")


def setup_trading_plan_cards(window, is_dark=False):
    """Construct streamlined institutional Trading Plan & Manual Quant Copilot inside frameAIArea."""
    if not hasattr(window, "layoutAIArea"):
        return

    assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets")
    if not os.path.exists(assets_dir):
        assets_dir = os.path.join(os.path.dirname(__file__), "assets")

    # Hide legacy text / gauges
    if hasattr(window, "txtAIReasoning") and window.txtAIReasoning:
        window.txtAIReasoning.setVisible(False)
    if hasattr(window, "lblAISubtitle") and window.lblAISubtitle:
        window.lblAISubtitle.setVisible(False)
    if hasattr(window, "cardDXY") and window.cardDXY:
        window.cardDXY.setVisible(False)
    if hasattr(window, "cardUS10Y") and window.cardUS10Y:
        window.cardUS10Y.setVisible(False)
    if hasattr(window, "btnEmergencyKill") and window.btnEmergencyKill:
        window.btnEmergencyKill.setVisible(False)

    window.layoutAIArea.setContentsMargins(10, 8, 10, 8)
    window.layoutAIArea.setSpacing(6)

    # Avoid duplicate construction
    if hasattr(window, "cardSetupModel") and window.cardSetupModel:
        apply_playbook_cards_theme(window, is_dark)
        return

    # 0. MODE SWITCHER BAR
    frame_mode = QFrame()
    frame_mode.setObjectName("framePlanModeSwitcher")
    frame_mode.setFixedHeight(28)
    layout_mode = QHBoxLayout(frame_mode)
    layout_mode.setContentsMargins(2, 2, 2, 2)
    layout_mode.setSpacing(2)

    btn_mode_ai = QPushButton("AI STRATEGY")
    btn_mode_ai.setObjectName("btnPlanModeAI")
    btn_mode_ai.setCursor(Qt.PointingHandCursor)

    btn_mode_manual = QPushButton("MANUAL ORDER")
    btn_mode_manual.setObjectName("btnPlanModeManual")
    btn_mode_manual.setCursor(Qt.PointingHandCursor)

    layout_mode.addWidget(btn_mode_ai)
    layout_mode.addWidget(btn_mode_manual)

    window.framePlanModeSwitcher = frame_mode
    window.btnPlanModeAI = btn_mode_ai
    window.btnPlanModeManual = btn_mode_manual

    # ================= CONTAINER 1: AI SIGNAL PLAN =================
    container_ai = QWidget()
    container_ai.setObjectName("containerPlanAI")
    layout_ai = QVBoxLayout(container_ai)
    layout_ai.setContentsMargins(0, 0, 0, 0)
    layout_ai.setSpacing(6)

    # CARD 1: SETUP MODEL & CONFLUENCE
    card_model = QFrame()
    card_model.setObjectName("cardSetupModel")
    card_model_layout = QVBoxLayout(card_model)
    card_model_layout.setContentsMargins(10, 7, 10, 7)
    card_model_layout.setSpacing(4)

    row_m_top = QHBoxLayout()
    row_m_top.setSpacing(6)
    v_m_title = QVBoxLayout()
    v_m_title.setSpacing(1)
    lbl_m_sub = QLabel("SETUP MODEL")
    lbl_m_sub.setObjectName("lblModelSubtitle")
    lbl_m_name = QLabel("ICT Zones Pro v4.2")
    lbl_m_name.setObjectName("lblModelName")
    v_m_title.addWidget(lbl_m_sub)
    v_m_title.addWidget(lbl_m_name)
    row_m_top.addLayout(v_m_title)
    row_m_top.addStretch()

    lbl_m_grade = QLabel("AWAITING SETUP")
    lbl_m_grade.setObjectName("lblModelGrade")
    row_m_top.addWidget(lbl_m_grade)
    card_model_layout.addLayout(row_m_top)

    sep1 = QFrame()
    sep1.setFrameShape(QFrame.HLine)
    sep1.setObjectName("sepCard1")
    sep1.setFixedHeight(1)
    card_model_layout.addWidget(sep1)

    def _make_checklist_row(k_text, v_text, v_obj_name, icon_obj_name):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        lbl_k = QLabel(k_text)
        lbl_k.setObjectName(f"lblKey_{v_obj_name}")
        lbl_v = QLabel(v_text)
        lbl_v.setObjectName(v_obj_name)
        lbl_ic = QLabel()
        lbl_ic.setObjectName(icon_obj_name)
        lbl_ic.setFixedSize(12, 12)
        lbl_ic.setScaledContents(True)

        svg_file = "check_vector_emerald.svg" if is_dark else "check_vector_light.svg"
        icon_path = os.path.join(assets_dir, svg_file)
        if os.path.exists(icon_path):
            lbl_ic.setPixmap(QIcon(icon_path).pixmap(12, 12))
        lbl_ic.setVisible(False)

        setattr(window, f"lblKey_{v_obj_name}", lbl_k)
        setattr(window, v_obj_name, lbl_v)
        setattr(window, icon_obj_name, lbl_ic)

        row.addWidget(lbl_k)
        row.addStretch()
        row.addWidget(lbl_v)
        row.addWidget(lbl_ic)
        return row

    def _make_row(k_text, v_text, v_obj_name):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        lbl_k = QLabel(k_text)
        lbl_k.setObjectName(f"lblKey_{v_obj_name}")
        lbl_v = QLabel(v_text)
        lbl_v.setObjectName(v_obj_name)
        setattr(window, f"lblKey_{v_obj_name}", lbl_k)
        setattr(window, v_obj_name, lbl_v)
        row.addWidget(lbl_k)
        row.addStretch()
        row.addWidget(lbl_v)
        return row

    card_model_layout.addLayout(_make_checklist_row("Trend Structure", "Awaiting Clear Trend", "lblChk1Val", "lblChk1Icon"))
    card_model_layout.addLayout(_make_checklist_row("Liquidity Sweep", "Awaiting Asian Sweep", "lblChk2Val", "lblChk2Icon"))
    card_model_layout.addLayout(_make_checklist_row("Order Blocks & FVG", "Awaiting Mitigation", "lblChk3Val", "lblChk3Icon"))

    init_model = resolve_strategy_model_name(window, None)
    lbl_m_name.setText(init_model)
    update_strategy_checklist_ui(window, init_model, is_active=False)

    # CARD 2: ORDER & RISK (Concise & Institutional)
    card_order = QFrame()
    card_order.setObjectName("cardRiskBudget")
    card_order_layout = QVBoxLayout(card_order)
    card_order_layout.setContentsMargins(4, 6, 4, 6)
    card_order_layout.setSpacing(4)

    row_o_top = QHBoxLayout()
    row_o_top.setSpacing(6)
    lbl_o_title = QLabel("ORDER & RISK BUDGET")
    lbl_o_title.setObjectName("lblOrderBudgetTitle")
    lbl_o_badge = QLabel("NO ORDER")
    lbl_o_badge.setObjectName("lblOrderTypeBadge")
    row_o_top.addWidget(lbl_o_title)
    row_o_top.addStretch()
    row_o_top.addWidget(lbl_o_badge)
    card_order_layout.addLayout(row_o_top)

    sep2 = QFrame()
    sep2.setFrameShape(QFrame.HLine)
    sep2.setObjectName("sepCard2")
    sep2.setFixedHeight(1)
    card_order_layout.addWidget(sep2)

    card_order_layout.addLayout(_make_row("ENTRY PRICE", "--", "lblEntryVal"))
    card_order_layout.addLayout(_make_row("STOP LOSS", "--", "lblSLVal"))
    card_order_layout.addLayout(_make_row("TAKE PROFIT", "--", "lblTPVal"))

    sep2_sub = QFrame()
    sep2_sub.setFrameShape(QFrame.HLine)
    sep2_sub.setObjectName("sepCard2Sub")
    sep2_sub.setFixedHeight(1)
    card_order_layout.addWidget(sep2_sub)

    card_order_layout.addLayout(_make_row("VOLUME", "--", "lblSizeVal"))

    # CARD 2.5: AI PRE-TRADE COMPLIANCE GATE (Unified with Manual Copilot)
    card_ai_comp = QFrame()
    card_ai_comp.setObjectName("cardAICompliance")
    layout_ai_comp = QVBoxLayout(card_ai_comp)
    layout_ai_comp.setContentsMargins(4, 4, 4, 4)
    layout_ai_comp.setSpacing(2)

    lbl_ac_title = QLabel("PRE-TRADE COMPLIANCE GATE")
    lbl_ac_title.setObjectName("lblAIGateTitle")
    layout_ai_comp.addWidget(lbl_ac_title)

    def _make_ai_gate_check_row(title, obj_key):
        r = QHBoxLayout()
        r.setContentsMargins(0, 0, 0, 0)
        lbl_t = QLabel(title)
        lbl_t.setObjectName(f"{obj_key}Title")
        lbl_v = QLabel("PASS")
        lbl_v.setObjectName(f"{obj_key}Val")
        lbl_v.setAlignment(Qt.AlignRight)
        lbl_t.setStyleSheet("border: none; background: transparent;")
        lbl_v.setStyleSheet("border: none; background: transparent;")
        setattr(window, f"{obj_key}Title", lbl_t)
        setattr(window, f"{obj_key}Val", lbl_v)
        r.addWidget(lbl_t)
        r.addStretch()
        r.addWidget(lbl_v)
        return r

    layout_ai_comp.addLayout(_make_ai_gate_check_row("Daily Drawdown (< 4%)", "lblAIGateCheck1"))
    layout_ai_comp.addLayout(_make_ai_gate_check_row("News Defense (±15m)", "lblAIGateCheck2"))
    layout_ai_comp.addLayout(_make_ai_gate_check_row("Max Open Trades (≤ 3)", "lblAIGateCheck3"))
    layout_ai_comp.addLayout(_make_ai_gate_check_row("Spread Check", "lblAIGateCheck4"))

    sep_ai_comp = QFrame()
    sep_ai_comp.setFrameShape(QFrame.HLine)
    sep_ai_comp.setFixedHeight(1)

    # CARD 3: OPERATOR APPROVAL GATE (Streamlined & Bug-Free)
    card_gate = QFrame()
    card_gate.setObjectName("cardExecutionGate")
    card_gate_layout = QVBoxLayout(card_gate)
    card_gate_layout.setContentsMargins(4, 6, 4, 6)
    card_gate_layout.setSpacing(5)

    row_g_top = QHBoxLayout()
    lbl_g_title = QLabel("EXPIRATION")
    lbl_g_title.setObjectName("lblGateExpiryTitle")
    lbl_g_time = QLabel("--")
    lbl_g_time.setObjectName("lblGateExpiryTime")
    row_g_top.addWidget(lbl_g_title)
    row_g_top.addStretch()
    row_g_top.addWidget(lbl_g_time)
    card_gate_layout.addLayout(row_g_top)

    bar_expiry = QProgressBar()
    bar_expiry.setObjectName("barSignalExpiry")
    bar_expiry.setRange(0, 60)
    bar_expiry.setValue(0)
    bar_expiry.setFixedHeight(2)
    bar_expiry.setTextVisible(False)
    card_gate_layout.addWidget(bar_expiry)

    btn_approve = QPushButton("AWAITING STRATEGY SIGNAL")
    btn_approve.setObjectName("btnApproveOrder")
    btn_approve.setFixedHeight(28)
    btn_approve.setEnabled(False)
    btn_approve.setCursor(Qt.ArrowCursor)
    btn_approve.setToolTip("Approve and route order to MetaTrader 5")
    card_gate_layout.addWidget(btn_approve)

    row_actions = QHBoxLayout()
    row_actions.setContentsMargins(0, 0, 0, 0)
    row_actions.setSpacing(6)

    btn_modify = QPushButton("MODIFY")
    btn_modify.setObjectName("btnModifyOrder")
    btn_modify.setFixedHeight(22)
    btn_modify.setEnabled(False)
    btn_modify.setCursor(Qt.PointingHandCursor)

    btn_discard = QPushButton("DISCARD")
    btn_discard.setObjectName("btnDiscardOrder")
    btn_discard.setFixedHeight(22)
    btn_discard.setEnabled(False)
    btn_discard.setCursor(Qt.PointingHandCursor)

    row_actions.addWidget(btn_modify)
    row_actions.addWidget(btn_discard)
    card_gate_layout.addLayout(row_actions)

    sep_divider1 = QFrame()
    sep_divider1.setFrameShape(QFrame.HLine)
    sep_divider1.setObjectName("sepDivider1")
    sep_divider1.setFixedHeight(1)

    sep_divider2 = QFrame()
    sep_divider2.setFrameShape(QFrame.HLine)
    sep_divider2.setObjectName("sepDivider2")
    sep_divider2.setFixedHeight(1)

    layout_ai.addWidget(card_model)
    layout_ai.addWidget(sep_divider1)
    layout_ai.addWidget(card_order)
    layout_ai.addWidget(sep_divider2)
    layout_ai.addWidget(card_gate)

    # Expose AI widgets on window
    window.cardSetupModel = card_model
    window.cardRiskBudget = card_order
    window.cardExecutionGate = card_gate
    window.sepCard1 = sep1
    window.sepCard2 = sep2
    window.sepCard2Sub = sep2_sub
    window.sepDivider1 = sep_divider1
    window.sepDivider2 = sep_divider2
    window.lblModelSubtitle = lbl_m_sub
    window.lblModelName = lbl_m_name
    window.lblModelGrade = lbl_m_grade
    window.lblOrderBudgetTitle = lbl_o_title
    window.lblOrderTypeBadge = lbl_o_badge
    window.lblGateExpiryTitle = lbl_g_title
    window.lblGateExpiryTime = lbl_g_time
    window.lblSignalExpiry = lbl_g_time
    window.barSignalExpiry = bar_expiry
    window.btnApproveOrder = btn_approve
    window.btnModifyOrder = btn_modify
    window.btnDiscardOrder = btn_discard

    # ================= CONTAINER 2: MANUAL QUANT COPILOT =================
    container_manual = QWidget()
    container_manual.setObjectName("containerPlanManual")
    layout_manual = QVBoxLayout(container_manual)
    layout_manual.setContentsMargins(0, 0, 0, 0)
    layout_manual.setSpacing(5)

    # Card M1: Direction & Live Execution Quotes
    card_m_dir = QFrame()
    card_m_dir.setObjectName("cardManualDir")
    layout_m_dir = QVBoxLayout(card_m_dir)
    layout_m_dir.setContentsMargins(4, 4, 4, 4)
    layout_m_dir.setSpacing(4)

    row_md_top = QHBoxLayout()
    row_md_top.setContentsMargins(0, 0, 0, 0)
    lbl_md_title = QLabel("ORDER")
    lbl_md_title.setObjectName("lblManualHeaderTitle")
    lbl_md_badge = QLabel("MARKET DIRECT")
    lbl_md_badge.setObjectName("lblManualExecBadge")
    lbl_md_badge.setVisible(False)
    lbl_copilot_badge = QLabel("MACRO ALIGNED")
    lbl_copilot_badge.setObjectName("lblManualCopilotBadge")
    lbl_copilot_badge.setFixedHeight(18)
    lbl_spd = QLabel("SPREAD: 14.0 PTS")
    lbl_spd.setObjectName("lblManualSpread")
    lbl_spd.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    row_md_top.addWidget(lbl_md_title)
    row_md_top.addSpacing(6)
    row_md_top.addWidget(lbl_copilot_badge)
    row_md_top.addStretch()
    row_md_top.addWidget(lbl_spd)
    layout_m_dir.addLayout(row_md_top)

    row_quotes = QHBoxLayout()
    row_quotes.setContentsMargins(0, 0, 0, 0)
    row_quotes.setSpacing(6)

    # BUY Button Card
    btn_buy = QPushButton()
    btn_buy.setObjectName("btnManualBuy")
    btn_buy.setCursor(Qt.PointingHandCursor)
    btn_buy.setFixedHeight(34)
    layout_buy = QHBoxLayout(btn_buy)
    layout_buy.setContentsMargins(8, 2, 8, 2)
    layout_buy.setSpacing(4)
    lbl_buy_t = QLabel("BUY")
    lbl_buy_t.setObjectName("lblManualBuyText")
    lbl_ask_p = QLabel("0.00")
    lbl_ask_p.setObjectName("lblManualAskPrice")
    lbl_ask_p.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    layout_buy.addWidget(lbl_buy_t)
    layout_buy.addStretch()
    layout_buy.addWidget(lbl_ask_p)

    # SELL Button Card
    btn_sell = QPushButton()
    btn_sell.setObjectName("btnManualSell")
    btn_sell.setCursor(Qt.PointingHandCursor)
    btn_sell.setFixedHeight(34)
    layout_sell = QHBoxLayout(btn_sell)
    layout_sell.setContentsMargins(8, 2, 8, 2)
    layout_sell.setSpacing(4)
    lbl_sell_t = QLabel("SELL")
    lbl_sell_t.setObjectName("lblManualSellText")
    lbl_bid_p = QLabel("0.00")
    lbl_bid_p.setObjectName("lblManualBidPrice")
    lbl_bid_p.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    layout_sell.addWidget(lbl_sell_t)
    layout_sell.addStretch()
    layout_sell.addWidget(lbl_bid_p)

    row_quotes.addWidget(btn_buy)
    row_quotes.addWidget(btn_sell)
    layout_m_dir.addLayout(row_quotes)

    # --- ORDER TYPE & ENTRY PRICE (Institutional Side-by-Side: Market vs Pending) ---
    row_order_inputs = QHBoxLayout()
    row_order_inputs.setContentsMargins(0, 0, 0, 0)
    row_order_inputs.setSpacing(4)

    combo_order_type = QComboBox()
    combo_order_type.setObjectName("comboManualOrderType")
    combo_order_type.addItems(["MARKET", "BUY LIMIT", "SELL LIMIT", "BUY STOP", "SELL STOP"])
    combo_order_type.setCursor(Qt.PointingHandCursor)
    combo_order_type.setFixedHeight(22)

    spin_pending_price = QDoubleSpinBox()
    spin_pending_price.setObjectName("spinManualPendingPrice")
    spin_pending_price.setDecimals(2)
    spin_pending_price.setRange(0.0, 1000000.0)
    spin_pending_price.setValue(0.0)
    spin_pending_price.setSingleStep(0.5)
    spin_pending_price.setFixedHeight(22)
    spin_pending_price.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    spin_pending_price.setButtonSymbols(QDoubleSpinBox.NoButtons)

    # Helper dummy labels kept for API backward compatibility in tests
    lbl_order_type = QLabel("")
    lbl_order_type.setObjectName("lblManualOrderTypeLabel")
    lbl_order_type.setVisible(False)
    lbl_pending_price = QLabel("")
    lbl_pending_price.setObjectName("lblManualPendingPriceLabel")
    lbl_pending_price.setVisible(False)

    row_order_inputs.addWidget(combo_order_type, 1)
    row_order_inputs.addWidget(spin_pending_price, 1)
    layout_m_dir.addLayout(row_order_inputs)

    # Store references on window
    window.comboManualOrderType = combo_order_type
    window.spinManualPendingPrice = spin_pending_price
    window.lblManualOrderTypeLabel = lbl_order_type
    window.lblManualPendingPriceLabel = lbl_pending_price
    window._manual_order_type = "MARKET"

    # Recalculate and redraw lines when pending price changes
    spin_pending_price.valueChanged.connect(lambda: _recalculate_manual_lot_and_rr(window))

    # -- Initially hide pending price
    spin_pending_price.setVisible(False)
    lbl_pending_price_ref = lbl_pending_price

    def _on_order_type_changed(idx):
        order_str = combo_order_type.currentText()  # e.g. "BUY LIMIT"
        window._manual_order_type = order_str
        is_pending = (order_str != "MARKET")
        lbl_pending_price_ref.setVisible(is_pending)
        spin_pending_price.setVisible(is_pending)

        # Update BUY/SELL button labels (Clean institutional: no redundant MARKET duplicate)
        if order_str == "MARKET":
            lbl_buy_t.setText("BUY")
            lbl_sell_t.setText("SELL")
        elif "LIMIT" in order_str:
            lbl_buy_t.setText("BUY LIMIT")
            lbl_sell_t.setText("SELL LIMIT")
        elif "STOP" in order_str:
            lbl_buy_t.setText("BUY STOP")
            lbl_sell_t.setText("SELL STOP")

        # Smart default pending price based on current market & order type
        if is_pending:
            sym = getattr(window, "current_sym", "XAUUSD").split("\n")[0].strip()
            info = mt5.symbol_info(sym)
            dig = info.digits if info else 2
            pt = info.point if info and info.point > 0 else 0.01
            pip_u = get_symbol_pip_unit(sym, dig, pt)
            step_dist = max(pip_u * 15.0, 50 * pt)

            tick = mt5.symbol_info_tick(sym) if mt5.terminal_info() is not None else None
            curr_ask = float(tick.ask) if tick and tick.ask > 0 else float(getattr(window, "_last_manual_ask", 2650.25))
            curr_bid = float(tick.bid) if tick and tick.bid > 0 else float(getattr(window, "_last_manual_bid", 2650.00))

            spin_pending_price.setDecimals(dig)
            spin_pending_price.setSingleStep(pip_u if pip_u > 0 else pt * 10)

            # Auto-align direction
            if "BUY" in order_str:
                window._manual_direction = "BUY"
            elif "SELL" in order_str:
                window._manual_direction = "SELL"

            cur_p_val = spin_pending_price.value()
            needs_new_price = False

            if cur_p_val <= 0.01:
                needs_new_price = True
            elif order_str == "BUY LIMIT" and cur_p_val >= curr_ask:
                needs_new_price = True
            elif order_str == "SELL LIMIT" and cur_p_val <= curr_bid:
                needs_new_price = True
            elif order_str == "BUY STOP" and cur_p_val <= curr_ask:
                needs_new_price = True
            elif order_str == "SELL STOP" and cur_p_val >= curr_bid:
                needs_new_price = True

            if needs_new_price:
                if order_str == "BUY LIMIT":
                    spin_pending_price.setValue(round(curr_bid - step_dist, dig))
                elif order_str == "SELL LIMIT":
                    spin_pending_price.setValue(round(curr_ask + step_dist, dig))
                elif order_str == "BUY STOP":
                    spin_pending_price.setValue(round(curr_ask + step_dist, dig))
                elif order_str == "SELL STOP":
                    spin_pending_price.setValue(round(curr_bid - step_dist, dig))

            # Re-align SL and TP symmetrically relative to new pending entry price
            new_entry_p = spin_pending_price.value()
            is_b = (getattr(window, "_manual_direction", "BUY") == "BUY")
            cur_sl = window.spinManualSL.value() if hasattr(window, "spinManualSL") else 0.0
            cur_tp = window.spinManualTP.value() if hasattr(window, "spinManualTP") else 0.0
            sl_invalid = (cur_sl <= 0.0) or (is_b and cur_sl >= new_entry_p) or (not is_b and cur_sl <= new_entry_p)
            tp_invalid = (cur_tp <= 0.0) or (is_b and cur_tp <= new_entry_p) or (not is_b and cur_tp >= new_entry_p)
            if sl_invalid or tp_invalid:
                dist_sl = step_dist
                dist_tp = step_dist * 2.0
                if hasattr(window, "spinManualSL") and window.spinManualSL:
                    window.spinManualSL.blockSignals(True)
                    window.spinManualSL.setValue(round(new_entry_p - dist_sl if is_b else new_entry_p + dist_sl, dig))
                    window.spinManualSL.blockSignals(False)
                if hasattr(window, "spinManualTP") and window.spinManualTP:
                    window.spinManualTP.blockSignals(True)
                    window.spinManualTP.setValue(round(new_entry_p + dist_tp if is_b else new_entry_p - dist_tp, dig))
                    window.spinManualTP.blockSignals(False)

        # Both buttons always stay interactive to allow direction switching
        btn_buy.setEnabled(True)
        btn_sell.setEnabled(True)
        apply_playbook_cards_theme(window, getattr(window, "is_dark_theme", False))
        _recalculate_manual_lot_and_rr(window)

    combo_order_type.currentIndexChanged.connect(_on_order_type_changed)

    sep_m1 = QFrame()
    sep_m1.setFrameShape(QFrame.HLine)
    sep_m1.setObjectName("sepManual1")
    sep_m1.setFixedHeight(1)

    # Card M2: Risk Model & Editable SL / TP (Clean Grid Layout with generous spacing)
    card_m_risk = QFrame()
    card_m_risk.setObjectName("cardManualRisk")
    layout_m_risk = QGridLayout(card_m_risk)
    layout_m_risk.setContentsMargins(4, 4, 4, 4)
    layout_m_risk.setVerticalSpacing(8)
    layout_m_risk.setHorizontalSpacing(6)

    lbl_mr_title = QLabel("RISK & VOLUME")
    lbl_mr_title.setObjectName("lblManualRiskTitle")
    lbl_mr_title.setMinimumHeight(14)
    spin_lot = QDoubleSpinBox()
    spin_lot.setObjectName("spinManualLot")
    spin_lot.setDecimals(2)
    spin_lot.setRange(0.01, 100.0)
    spin_lot.setSingleStep(0.01)
    spin_lot.setValue(0.20)
    spin_lot.setSuffix(" LOTS")
    spin_lot.setFixedWidth(86)
    spin_lot.setFixedHeight(20)
    spin_lot.setAlignment(Qt.AlignRight)
    spin_lot.setButtonSymbols(QDoubleSpinBox.NoButtons)

    # Box with '-' / '+' stepper buttons flanking spin_lot
    box_lot_ctrl = QWidget()
    box_lot_ctrl.setFixedHeight(22)
    layout_lot_ctrl = QHBoxLayout(box_lot_ctrl)
    layout_lot_ctrl.setContentsMargins(0, 0, 0, 0)
    layout_lot_ctrl.setSpacing(2)
    layout_lot_ctrl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

    btn_lot_minus = QPushButton("-")
    btn_lot_minus.setObjectName("btnManualLotMinus")
    btn_lot_minus.setFixedSize(18, 20)
    btn_lot_minus.setCursor(Qt.PointingHandCursor)
    btn_lot_minus.setToolTip("Decrease 0.01 Lot")

    btn_lot_plus = QPushButton("+")
    btn_lot_plus.setObjectName("btnManualLotPlus")
    btn_lot_plus.setFixedSize(18, 20)
    btn_lot_plus.setCursor(Qt.PointingHandCursor)
    btn_lot_plus.setToolTip("Increase 0.01 Lot")

    layout_lot_ctrl.addWidget(btn_lot_minus, 0, Qt.AlignVCenter)
    layout_lot_ctrl.addWidget(spin_lot, 0, Qt.AlignVCenter)
    layout_lot_ctrl.addWidget(btn_lot_plus, 0, Qt.AlignVCenter)

    def _step_lot(delta):
        cur_v = round(spin_lot.value() + delta, 2)
        cur_v = max(0.01, min(100.0, cur_v))
        spin_lot.setValue(cur_v)
        _recalculate_manual_lot_and_rr(window, from_user_lot_change=True)

    btn_lot_minus.clicked.connect(lambda: _step_lot(-0.01))
    btn_lot_plus.clicked.connect(lambda: _step_lot(0.01))

    window.btnManualLotMinus = btn_lot_minus
    window.btnManualLotPlus = btn_lot_plus

    layout_m_risk.addWidget(lbl_mr_title, 0, 0, Qt.AlignLeft | Qt.AlignVCenter)
    layout_m_risk.addWidget(box_lot_ctrl, 0, 1, 1, 2, Qt.AlignRight | Qt.AlignVCenter)

    # Quick Risk Selectors
    lbl_risk_lbl = QLabel("% RISK")
    lbl_risk_lbl.setObjectName("lblManualRiskLabel")
    lbl_risk_lbl.setMinimumHeight(14)
    box_risk_btns = QWidget()
    layout_risk_btns = QHBoxLayout(box_risk_btns)
    layout_risk_btns.setContentsMargins(0, 0, 0, 0)
    layout_risk_btns.setSpacing(4)
    layout_risk_btns.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    btn_r05 = QPushButton("0.5%")
    btn_r05.setObjectName("btnRisk05")
    btn_r05.setProperty("class", "risk_pct_btn")
    btn_r10 = QPushButton("1.0%")
    btn_r10.setObjectName("btnRisk10")
    btn_r10.setProperty("class", "risk_pct_btn")
    btn_r15 = QPushButton("1.5%")
    btn_r15.setObjectName("btnRisk15")
    btn_r15.setProperty("class", "risk_pct_btn")
    btn_r20 = QPushButton("2.0%")
    btn_r20.setObjectName("btnRisk20")
    btn_r20.setProperty("class", "risk_pct_btn")
    for b in [btn_r05, btn_r10, btn_r15, btn_r20]:
        b.setCursor(Qt.PointingHandCursor)
        layout_risk_btns.addWidget(b)
    layout_m_risk.addWidget(lbl_risk_lbl, 1, 0, Qt.AlignLeft | Qt.AlignVCenter)
    layout_m_risk.addWidget(box_risk_btns, 1, 1, 1, 2, Qt.AlignRight | Qt.AlignVCenter)

    # Stop Loss Row (2-column layout)
    col_sl_info = QVBoxLayout()
    col_sl_info.setContentsMargins(0, 0, 0, 0)
    col_sl_info.setSpacing(2)
    lbl_sl_lbl = QLabel("STOP LOSS")
    lbl_sl_lbl.setObjectName("lblManualSLLabel")
    lbl_sl_lbl.setMinimumHeight(14)
    lbl_sl_pips = QLabel("-25.0 pips / -$100.00")
    lbl_sl_pips.setObjectName("lblManualSLPips")
    lbl_sl_pips.setMinimumHeight(14)
    col_sl_info.addWidget(lbl_sl_lbl)
    col_sl_info.addWidget(lbl_sl_pips)
    layout_m_risk.addLayout(col_sl_info, 2, 0, Qt.AlignLeft | Qt.AlignVCenter)

    spin_sl = QDoubleSpinBox()
    spin_sl.setObjectName("spinManualSL")
    spin_sl.setFixedHeight(24)
    spin_sl.setFixedWidth(78)
    spin_sl.setAlignment(Qt.AlignRight)
    spin_sl.setButtonSymbols(QDoubleSpinBox.NoButtons)

    box_sl_pre = QWidget()
    box_sl_pre.setFixedWidth(104)
    box_sl_pre.setFixedHeight(24)
    layout_sl_pre = QHBoxLayout(box_sl_pre)
    layout_sl_pre.setContentsMargins(0, 0, 0, 0)
    layout_sl_pre.setSpacing(2)
    layout_sl_pre.setAlignment(Qt.AlignVCenter)

    btn_pre_atr = QPushButton("ATR")
    btn_pre_atr.setObjectName("btnPresetATR")
    btn_pre_atr.setProperty("class", "preset_tag_btn")
    btn_pre_atr.setFixedHeight(24)
    btn_pre_atr.setCursor(Qt.PointingHandCursor)

    btn_pre_swing = QPushButton("SWING")
    btn_pre_swing.setObjectName("btnPresetSwing")
    btn_pre_swing.setProperty("class", "preset_tag_btn")
    btn_pre_swing.setFixedHeight(24)
    btn_pre_swing.setCursor(Qt.PointingHandCursor)

    layout_sl_pre.addWidget(btn_pre_atr)
    layout_sl_pre.addWidget(btn_pre_swing)

    layout_m_risk.addWidget(spin_sl, 2, 1, Qt.AlignVCenter)
    layout_m_risk.addWidget(box_sl_pre, 2, 2, Qt.AlignVCenter)

    # Take Profit Row (2-column layout)
    col_tp_info = QVBoxLayout()
    col_tp_info.setContentsMargins(0, 0, 0, 0)
    col_tp_info.setSpacing(2)
    lbl_tp_lbl = QLabel("TAKE PROFIT")
    lbl_tp_lbl.setObjectName("lblManualTPLabel")
    lbl_tp_lbl.setMinimumHeight(14)
    lbl_tp_pips = QLabel("+50.0 pips / +$200.00")
    lbl_tp_pips.setObjectName("lblManualTPPips")
    lbl_tp_pips.setMinimumHeight(14)
    col_tp_info.addWidget(lbl_tp_lbl)
    col_tp_info.addWidget(lbl_tp_pips)
    layout_m_risk.addLayout(col_tp_info, 3, 0, Qt.AlignLeft | Qt.AlignVCenter)

    spin_tp = QDoubleSpinBox()
    spin_tp.setObjectName("spinManualTP")
    spin_tp.setFixedHeight(24)
    spin_tp.setFixedWidth(78)
    spin_tp.setAlignment(Qt.AlignRight)
    spin_tp.setButtonSymbols(QDoubleSpinBox.NoButtons)

    box_tp_pre = QWidget()
    box_tp_pre.setFixedWidth(104)
    box_tp_pre.setFixedHeight(24)
    layout_tp_pre = QHBoxLayout(box_tp_pre)
    layout_tp_pre.setContentsMargins(0, 0, 0, 0)
    layout_tp_pre.setSpacing(2)
    layout_tp_pre.setAlignment(Qt.AlignVCenter)

    btn_pre_rr15 = QPushButton("1.5R")
    btn_pre_rr15.setObjectName("btnPresetRR15")
    btn_pre_rr15.setProperty("class", "preset_tag_btn")
    btn_pre_rr15.setFixedHeight(24)
    btn_pre_rr15.setCursor(Qt.PointingHandCursor)

    btn_pre_rr20 = QPushButton("2.0R")
    btn_pre_rr20.setObjectName("btnPresetRR20")
    btn_pre_rr20.setProperty("class", "preset_tag_btn")
    btn_pre_rr20.setFixedHeight(24)
    btn_pre_rr20.setCursor(Qt.PointingHandCursor)

    btn_pre_rr30 = QPushButton("3.0R")
    btn_pre_rr30.setObjectName("btnPresetRR30")
    btn_pre_rr30.setProperty("class", "preset_tag_btn")
    btn_pre_rr30.setFixedHeight(24)
    btn_pre_rr30.setCursor(Qt.PointingHandCursor)

    layout_tp_pre.addWidget(btn_pre_rr15)
    layout_tp_pre.addWidget(btn_pre_rr20)
    layout_tp_pre.addWidget(btn_pre_rr30)

    layout_m_risk.addWidget(spin_tp, 3, 1, Qt.AlignVCenter)
    layout_m_risk.addWidget(box_tp_pre, 3, 2, Qt.AlignVCenter)

    # Stepper helpers (kept for backward compatibility and testing)
    btn_sl_minus = QPushButton()
    btn_sl_plus = QPushButton()
    btn_tp_minus = QPushButton()
    btn_tp_plus = QPushButton()

    # Summary Box (Risk Red / Reward Green)
    lbl_lot_sum_title = QLabel("RISK / REWARD")
    lbl_lot_sum_title.setObjectName("lblManualLotSummaryTitle")
    lbl_lot_sum_title.setMinimumHeight(14)

    box_summary = QFrame()
    box_summary.setObjectName("boxManualLotSummary")
    layout_summary = QHBoxLayout(box_summary)
    layout_summary.setContentsMargins(0, 0, 0, 0)
    layout_summary.setSpacing(2)
    layout_summary.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

    lbl_risk_part = QLabel("-$100.00 (1.0%)")
    lbl_risk_part.setObjectName("lblManualRiskPart")
    lbl_risk_part.setMinimumHeight(14)
    lbl_slash = QLabel(" / ")
    lbl_slash.setObjectName("lblManualSlash")
    lbl_slash.setMinimumHeight(14)
    lbl_reward_part = QLabel("+$200.00 (2.0R)")
    lbl_reward_part.setObjectName("lblManualRewardPart")
    lbl_reward_part.setMinimumHeight(14)

    # Hidden compatibility label for existing tests
    lbl_lot_sum = QLabel("-$100.00 (1.0%) / +$200.00 (2.0R)")
    lbl_lot_sum.setObjectName("lblManualLotSummary")
    lbl_lot_sum.setVisible(False)

    layout_summary.addWidget(lbl_risk_part)
    layout_summary.addWidget(lbl_slash)
    layout_summary.addWidget(lbl_reward_part)
    layout_summary.addWidget(lbl_lot_sum)

    layout_m_risk.addWidget(lbl_lot_sum_title, 4, 0, Qt.AlignLeft | Qt.AlignVCenter)
    layout_m_risk.addWidget(box_summary, 4, 1, 1, 2, Qt.AlignRight | Qt.AlignVCenter)

    sep_m2 = QFrame()
    sep_m2.setFrameShape(QFrame.HLine)
    sep_m2.setObjectName("sepManual2")
    sep_m2.setFixedHeight(1)

    # Card M3: Pre-Trade Check Checklist
    card_m_gate = QFrame()
    card_m_gate.setObjectName("cardManualGate")
    layout_m_gate = QVBoxLayout(card_m_gate)
    layout_m_gate.setContentsMargins(4, 3, 4, 3)
    layout_m_gate.setSpacing(2)

    lbl_mg_title = QLabel("PRE-TRADE CHECK")
    lbl_mg_title.setObjectName("lblManualGateTitle")
    layout_m_gate.addWidget(lbl_mg_title)

    def _make_gate_check_row(title, obj_key):
        r = QHBoxLayout()
        r.setContentsMargins(0, 0, 0, 0)
        lbl_t = QLabel(title)
        lbl_t.setObjectName(f"{obj_key}Title")
        lbl_v = QLabel("PASS")
        lbl_v.setObjectName(f"{obj_key}Val")
        lbl_v.setAlignment(Qt.AlignRight)
        lbl_t.setStyleSheet("border: none; background: transparent;")
        lbl_v.setStyleSheet("border: none; background: transparent;")
        setattr(window, f"{obj_key}Title", lbl_t)
        setattr(window, f"{obj_key}Val", lbl_v)
        setattr(window, f"{obj_key}Icon", None)
        r.addWidget(lbl_t)
        r.addStretch()
        r.addWidget(lbl_v)
        return r

    layout_m_gate.addLayout(_make_gate_check_row("Daily Drawdown (< 4%)", "lblGateCheck1"))
    layout_m_gate.addLayout(_make_gate_check_row("News Defense (±15m)", "lblGateCheck2"))
    layout_m_gate.addLayout(_make_gate_check_row("Max Open Trades (≤ 3)", "lblGateCheck3"))
    layout_m_gate.addLayout(_make_gate_check_row("Spread Check", "lblGateCheck4"))

    sep_m3 = QFrame()
    sep_m3.setFrameShape(QFrame.HLine)
    sep_m3.setObjectName("sepManual3")
    sep_m3.setFixedHeight(1)

    # Card M4: Action Button
    card_m_action = QFrame()
    card_m_action.setObjectName("cardManualAction")
    layout_m_action = QVBoxLayout(card_m_action)
    layout_m_action.setContentsMargins(4, 2, 4, 2)
    layout_m_action.setSpacing(4)

    btn_m_exec = QPushButton("BUY 0.20 LOTS 2650.50")
    btn_m_exec.setObjectName("btnManualExecute")
    btn_m_exec.setFixedHeight(32)
    btn_m_exec.setCursor(Qt.PointingHandCursor)
    layout_m_action.addWidget(btn_m_exec)

    row_m_subaction = QHBoxLayout()
    row_m_subaction.setContentsMargins(0, 0, 0, 0)
    row_m_subaction.setSpacing(6)

    btn_m_clear_preview = QPushButton("HIDE PREVIEW")
    btn_m_clear_preview.setObjectName("btnManualClearPreview")
    btn_m_clear_preview.setFixedHeight(22)
    btn_m_clear_preview.setCursor(Qt.PointingHandCursor)
    btn_m_clear_preview.setToolTip("Toggle preview order lines on the chart")

    btn_m_reset = QPushButton("RESET")
    btn_m_reset.setObjectName("btnManualReset")
    btn_m_reset.setFixedHeight(22)
    btn_m_reset.setCursor(Qt.PointingHandCursor)
    btn_m_reset.setToolTip("Reset SL/TP to standard ATR volatility defaults")

    row_m_subaction.addWidget(btn_m_clear_preview, 2)
    row_m_subaction.addWidget(btn_m_reset, 1)
    layout_m_action.addLayout(row_m_subaction)

    layout_manual.addWidget(card_m_dir)
    layout_manual.addWidget(sep_m1)
    layout_manual.addWidget(card_m_risk)
    layout_manual.addWidget(sep_m2)
    layout_manual.addWidget(card_m_gate)
    layout_manual.addWidget(sep_m3)
    layout_manual.addWidget(card_m_action)

    # Expose Manual widgets on window
    window.cardManualDir = card_m_dir
    window.cardManualRisk = card_m_risk
    window.cardManualGate = card_m_gate
    window.cardManualAction = card_m_action
    window.sepManual1 = sep_m1
    window.sepManual2 = sep_m2
    window.sepManual3 = sep_m3
    window.lblManualHeaderTitle = lbl_md_title
    window.lblManualExecBadge = lbl_md_badge
    window.lblManualCopilotBadge = lbl_copilot_badge
    window.btnManualBuy = btn_buy
    window.lblManualBuyText = lbl_buy_t
    window.lblManualAskPrice = lbl_ask_p
    window.btnManualSell = btn_sell
    window.lblManualSellText = lbl_sell_t
    window.lblManualBidPrice = lbl_bid_p
    window.lblManualSpread = lbl_spd
    window.lblManualRiskTitle = lbl_mr_title
    window.spinManualLot = spin_lot
    window.lblManualLotVal = spin_lot
    window.lblManualRiskLabel = lbl_risk_lbl
    window.btnRisk05 = btn_r05
    window.btnRisk10 = btn_r10
    window.btnRisk15 = btn_r15
    window.btnRisk20 = btn_r20
    window.lblManualSLLabel = lbl_sl_lbl
    window.lblManualSLPips = lbl_sl_pips
    window.btnSLMinus = btn_sl_minus
    window.spinManualSL = spin_sl
    window.btnSLPlus = btn_sl_plus
    window.btnPresetATR = btn_pre_atr
    window.btnPresetSwing = btn_pre_swing
    window.lblManualTPLabel = lbl_tp_lbl
    window.lblManualTPPips = lbl_tp_pips
    window.btnTPMinus = btn_tp_minus
    window.spinManualTP = spin_tp
    window.btnTPPlus = btn_tp_plus
    window.btnPresetRR15 = btn_pre_rr15
    window.btnPresetRR20 = btn_pre_rr20
    window.btnPresetRR30 = btn_pre_rr30
    window.boxManualLotSummary = box_summary
    window.lblManualLotSummaryTitle = lbl_lot_sum_title
    window.lblManualRiskPart = lbl_risk_part
    window.lblManualSlash = lbl_slash
    window.lblManualRewardPart = lbl_reward_part
    window.lblManualLotSummary = lbl_lot_sum
    window.lblManualGateTitle = lbl_mg_title
    window.btnManualExecute = btn_m_exec
    window.btnManualClearPreview = btn_m_clear_preview
    window.btnManualReset = btn_m_reset
    window._show_manual_preview = True

    # Assemble containers into parent layout
    window.containerPlanAI = container_ai
    window.containerPlanManual = container_manual
    window.layoutAIArea.addWidget(frame_mode)
    window.layoutAIArea.addWidget(container_ai)
    window.layoutAIArea.addWidget(container_manual)
    window.layoutAIArea.addStretch()

    # Defaults
    window._plan_mode = "ai"
    window._manual_direction = "BUY"
    window._manual_risk_pct = 1.0
    container_ai.setVisible(True)
    container_manual.setVisible(False)
    container_ai.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
    container_manual.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

    # Signal wiring: Mode Switcher
    def _switch_mode(target_mode):
        window._plan_mode = target_mode
        is_ai = (target_mode == "ai")
        container_ai.setVisible(is_ai)
        container_manual.setVisible(not is_ai)

        if is_ai:
            container_ai.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
            container_manual.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        else:
            container_manual.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
            container_ai.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

        apply_playbook_cards_theme(window, getattr(window, "is_dark_theme", False))

        if hasattr(window, "frameAIArea") and window.frameAIArea:
            window.frameAIArea.adjustSize()
        if hasattr(window, "_reposition_trading_plan") and callable(window._reposition_trading_plan):
            window._reposition_trading_plan()
        if target_mode == "manual":
            # PAUSE / STOP AI countdown timer so it doesn't wipe chart lines!
            if hasattr(window, "_signal_expiry_timer") and window._signal_expiry_timer is not None:
                try:
                    window._signal_expiry_timer.stop()
                except Exception:
                    pass
            sync_manual_copilot_quotes(window)
        else:
            # Clear modification state when switching back to AI Strategy
            window._modifying_ticket = None
            window._modifying_is_position = False
            if hasattr(window, "lblManualGateTitle") and window.lblManualGateTitle:
                window.lblManualGateTitle.setText("PRE-TRADE COMPLIANCE GATE")
            sync_live_position_to_ai_plan(window)
            clean_curr = getattr(window, "current_sym", "").split("\n")[0].strip()
            store = MarketStateStore.get_instance()
            sig = store.get_state_dict(clean_curr)
            if not sig or not sig.get("model_name"):
                sig_fb = getattr(window, "active_signals_by_symbol", {}).get(clean_curr, {})
                if sig_fb:
                    sig = sig_fb
            if sig and sig.get("has_signal"):
                update_order_proposal_html(
                    window, sym=clean_curr, entry=sig.get("entry"),
                    sl=sig.get("sl"), tp=sig.get("tp"), has_signal=True,
                    signal_type=sig.get("signal_type", "BUY"),
                    is_live_position=sig.get("is_live_position", False),
                    live_ticket=sig.get("live_ticket", None),
                    live_volume=sig.get("live_volume", None),
                    live_profit=sig.get("live_profit", 0.0),
                    model_name=sig.get("model_name", None),
                    grade=sig.get("grade", None),
                    status=sig.get("status", "LIVE POSITION IN MARKET"),
                    checklist=sig.get("checklist", None),
                )
            else:
                clear_manual_chart_lines(window)
                update_order_proposal_html(
                    window,
                    sym=clean_curr,
                    has_signal=False,
                    signal_type=sig.get("signal_type", "HOLD") if sig else "HOLD",
                    model_name=sig.get("model_name", None) if sig else None,
                    grade=sig.get("grade", "STATUS: STANDBY") if sig else "STATUS: STANDBY",
                    chk1=sig.get("chk1", None) if sig else None,
                    chk2=sig.get("chk2", None) if sig else None,
                    chk3=sig.get("chk3", None) if sig else None,
                    checklist=sig.get("checklist", None) if sig else None,
                    status=sig.get("status", "SCANNING_STANDBY") if sig else "SCANNING_STANDBY",
                    digits=sig.get("digits", None) if sig else None,
                )

    btn_mode_ai.clicked.connect(lambda: _switch_mode("ai"))
    btn_mode_manual.clicked.connect(lambda: _switch_mode("manual"))
    window._switch_plan_mode = _switch_mode

    # Signal wiring: Direction toggles
    def _set_dir(new_d):
        window._manual_direction = new_d
        # If in pending mode, dynamically synchronize comboManualOrderType to match clicked side
        if hasattr(window, "comboManualOrderType") and window.comboManualOrderType:
            curr_ot = window.comboManualOrderType.currentText()
            if "LIMIT" in curr_ot:
                target_ot = "BUY LIMIT" if new_d == "BUY" else "SELL LIMIT"
                if curr_ot != target_ot:
                    idx_tgt = window.comboManualOrderType.findText(target_ot)
                    if idx_tgt >= 0:
                        window.comboManualOrderType.setCurrentIndex(idx_tgt)
            elif "STOP" in curr_ot:
                target_ot = "BUY STOP" if new_d == "BUY" else "SELL STOP"
                if curr_ot != target_ot:
                    idx_tgt = window.comboManualOrderType.findText(target_ot)
                    if idx_tgt >= 0:
                        window.comboManualOrderType.setCurrentIndex(idx_tgt)

        apply_playbook_cards_theme(window, getattr(window, "is_dark_theme", False))
        sync_manual_copilot_quotes(window)

    try:
        from frontend.widgets.options.options_binder import OptionsConfigBinder
        s_data, _, _ = OptionsConfigBinder.load_settings()
        window._manual_compliance_mode = s_data.get("manual_compliance_mode", "DISCRETIONARY")
    except Exception:
        window._manual_compliance_mode = "DISCRETIONARY"

    btn_buy.clicked.connect(lambda: _set_dir("BUY"))
    btn_sell.clicked.connect(lambda: _set_dir("SELL"))

    # Signal wiring: Risk % buttons
    def _set_risk(r_val):
        window._user_custom_lot = False
        window._manual_risk_pct = r_val
        apply_playbook_cards_theme(window, getattr(window, "is_dark_theme", False))
        _recalculate_manual_lot_and_rr(window)

    btn_r05.clicked.connect(lambda: _set_risk(0.5))
    btn_r10.clicked.connect(lambda: _set_risk(1.0))
    btn_r15.clicked.connect(lambda: _set_risk(1.5))
    btn_r20.clicked.connect(lambda: _set_risk(2.0))

    # Signal wiring: SpinBox changes
    def _on_lot_text_edited(txt):
        try:
            spin_lot.interpretText()
            _recalculate_manual_lot_and_rr(window, from_user_lot_change=True)
        except Exception:
            pass

    if hasattr(spin_lot, "lineEdit") and spin_lot.lineEdit():
        spin_lot.lineEdit().textEdited.connect(_on_lot_text_edited)

    spin_lot.valueChanged.connect(lambda: _recalculate_manual_lot_and_rr(window, from_user_lot_change=True))
    spin_sl.valueChanged.connect(lambda: _recalculate_manual_lot_and_rr(window))
    spin_tp.valueChanged.connect(lambda: _recalculate_manual_lot_and_rr(window))

    # Signal wiring: Stepper buttons
    def _step_spin(spin, increment: bool):
        sym = getattr(window, "current_sym", "XAUUSD").split("\n")[0].strip()
        info = mt5.symbol_info(sym)
        dig = info.digits if info else 2
        sym_u = sym.upper()
        if "XAU" in sym_u or "GOLD" in sym_u:
            step = 1.0
        elif "BTC" in sym_u or "ETH" in sym_u:
            step = 50.0
        elif any(c in sym_u for c in ["US30", "NAS100", "SPX500"]):
            step = 10.0
        elif "JPY" in sym_u:
            step = 0.10
        else:
            step = 0.0010 if dig in (3, 5) else 0.1
        cur = spin.value()
        spin.setValue(round(cur + step if increment else cur - step, dig))

    btn_sl_minus.clicked.connect(lambda: _step_spin(spin_sl, False))
    btn_sl_plus.clicked.connect(lambda: _step_spin(spin_sl, True))
    btn_tp_minus.clicked.connect(lambda: _step_spin(spin_tp, False))
    btn_tp_plus.clicked.connect(lambda: _step_spin(spin_tp, True))

    # Signal wiring: Presets
    def _apply_atr_preset():
        sym = getattr(window, "current_sym", "XAUUSD").split("\n")[0].strip()
        info = mt5.symbol_info(sym)
        dig = info.digits if info else 2
        is_b = (getattr(window, "_manual_direction", "BUY") == "BUY")
        cur_p = _get_manual_effective_entry_price(window, is_b, sym)

        atr_val = 0.0
        if hasattr(window, "chart_data_list") and len(window.chart_data_list) >= 15:
            cd = window.chart_data_list[-15:]
            trs = [max(c[4] - c[3], abs(c[4] - cd[i-1][2]), abs(c[3] - cd[i-1][2])) for i, c in enumerate(cd) if i > 0]
            if trs:
                atr_val = sum(trs) / len(trs)
        if atr_val <= 0:
            sym_u = sym.upper()
            if "XAU" in sym_u or "GOLD" in sym_u:
                atr_val = 2.0
            elif "BTC" in sym_u or "ETH" in sym_u:
                atr_val = 300.0
            elif any(c in sym_u for c in ["US30", "NAS100", "SPX500"]):
                atr_val = 40.0
            elif "JPY" in sym_u:
                atr_val = 0.25
            else:
                atr_val = 0.0020

        sl_dist = round(1.5 * atr_val, dig)
        spin_sl.setValue(round(cur_p - sl_dist if is_b else cur_p + sl_dist, dig))
        spin_tp.setValue(round(cur_p + (2.0 * sl_dist) if is_b else cur_p - (2.0 * sl_dist), dig))

    def _apply_swing_preset():
        sym = getattr(window, "current_sym", "XAUUSD").split("\n")[0].strip()
        info = mt5.symbol_info(sym)
        dig = info.digits if info else 2
        point = info.point if info and info.point > 0 else (0.01 if dig == 2 else 0.0001)
        buf = 2.0 * point * (10 if dig in (3, 5) else 1)
        is_b = (getattr(window, "_manual_direction", "BUY") == "BUY")
        cur_p = _get_manual_effective_entry_price(window, is_b, sym)

        applied = False
        if hasattr(window, "chart_data_list") and len(window.chart_data_list) >= 10:
            candles = window.chart_data_list[-20:]
            if is_b:
                lowest = min(c[3] for c in candles)
                new_sl = round(lowest - buf, dig)
                if new_sl < cur_p:
                    dist = abs(cur_p - new_sl)
                    new_tp = round(cur_p + 2.0 * dist, dig)
                    spin_sl.setValue(new_sl)
                    spin_tp.setValue(new_tp)
                    applied = True
            else:
                highest = max(c[4] for c in candles)
                new_sl = round(highest + buf, dig)
                if new_sl > cur_p:
                    dist = abs(new_sl - cur_p)
                    new_tp = round(cur_p - 2.0 * dist, dig)
                    spin_sl.setValue(new_sl)
                    spin_tp.setValue(new_tp)
                    applied = True
        if not applied:
            _apply_atr_preset()

    def _apply_rr_preset(rr_mult):
        sym = getattr(window, "current_sym", "XAUUSD").split("\n")[0].strip()
        info = mt5.symbol_info(sym)
        dig = info.digits if info else 2
        is_b = (getattr(window, "_manual_direction", "BUY") == "BUY")
        cur_p = _get_manual_effective_entry_price(window, is_b, sym)
        cur_sl = spin_sl.value()

        # Check if cur_sl is on the valid side of cur_p
        sl_dist = abs(cur_p - cur_sl) if (cur_sl > 0 and ((is_b and cur_sl < cur_p) or (not is_b and cur_sl > cur_p))) else 0.0
        if sl_dist <= 0:
            sym_u = sym.upper()
            if "XAU" in sym_u or "GOLD" in sym_u:
                sl_dist = 2.50
            elif "BTC" in sym_u or "ETH" in sym_u:
                sl_dist = 500.0
            elif any(c in sym_u for c in ["US30", "NAS100", "SPX500"]):
                sl_dist = 50.0
            elif "JPY" in sym_u:
                sl_dist = 0.35
            else:
                sl_dist = 0.0025
            spin_sl.setValue(round(cur_p - sl_dist if is_b else cur_p + sl_dist, dig))

        new_tp = round(cur_p + (rr_mult * sl_dist) if is_b else cur_p - (rr_mult * sl_dist), dig)
        spin_tp.setValue(new_tp)

    btn_pre_atr.clicked.connect(_apply_atr_preset)
    btn_pre_swing.clicked.connect(_apply_swing_preset)
    btn_pre_rr15.clicked.connect(lambda: _apply_rr_preset(1.5))
    btn_pre_rr20.clicked.connect(lambda: _apply_rr_preset(2.0))
    btn_pre_rr30.clicked.connect(lambda: _apply_rr_preset(3.0))

    # Signal wiring: Execute button
    btn_m_exec.clicked.connect(lambda: execute_manual_quant_order(window))

    # Signal wiring: Preview toggle and Reset
    def _toggle_manual_preview():
        cur_vis = getattr(window, "_show_manual_preview", True)
        new_vis = not cur_vis
        window._show_manual_preview = new_vis
        if new_vis:
            btn_m_clear_preview.setText("HIDE PREVIEW")
            _recalculate_manual_lot_and_rr(window)
        else:
            btn_m_clear_preview.setText("SHOW PREVIEW")
            clear_manual_chart_lines(window)

    def _reset_manual_defaults():
        window._modifying_ticket = None
        window._modifying_is_position = False
        if hasattr(window, "lblManualGateTitle") and window.lblManualGateTitle:
            window.lblManualGateTitle.setText("PRE-TRADE COMPLIANCE GATE")
        window._show_manual_preview = True
        btn_m_clear_preview.setText("HIDE PREVIEW")
        _apply_atr_preset()
        _recalculate_manual_lot_and_rr(window)

    btn_m_clear_preview.clicked.connect(_toggle_manual_preview)
    btn_m_reset.clicked.connect(_reset_manual_defaults)

    apply_playbook_cards_theme(window, is_dark)


def start_signal_expiry_countdown(window, duration_sec=None):
    """Start dynamic real-time 1-second countdown timer for Trading Plan signal expiration."""
    if getattr(window, "is_live_position", False) or getattr(window, "_plan_mode", "ai") == "manual":
        return

    if duration_sec is None:
        try:
            cfg_p = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "config", "settings.json")
            if os.path.exists(cfg_p):
                with open(cfg_p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    duration_sec = int(data.get("signal_expiry_sec", 60))
            else:
                duration_sec = 60
        except Exception:
            duration_sec = 60

    duration_sec = max(10, int(duration_sec))

    if hasattr(window, "_signal_expiry_timer") and window._signal_expiry_timer is not None:
        try:
            window._signal_expiry_timer.stop()
        except Exception:
            pass

    window._signal_expiry_total = duration_sec
    window._signal_expiry_remaining = duration_sec

    if hasattr(window, "barSignalExpiry") and window.barSignalExpiry:
        window.barSignalExpiry.setRange(0, duration_sec)
        window.barSignalExpiry.setValue(duration_sec)
    if hasattr(window, "lblGateExpiryTime") and window.lblGateExpiryTime:
        window.lblGateExpiryTime.setText(f"{duration_sec}s")
    if hasattr(window, "btnApproveOrder") and window.btnApproveOrder:
        window.btnApproveOrder.setEnabled(True)
        window.btnApproveOrder.setText("APPROVE ORDER")

    from PySide6.QtCore import QTimer
    timer = QTimer(window if isinstance(window, QtCore.QObject) else None)
    timer.setInterval(1000)

    def _tick():
        if not hasattr(window, "_signal_expiry_remaining"):
            timer.stop()
            return
        if getattr(window, "_plan_mode", "ai") == "manual":
            timer.stop()
            return

        # Real-time Price-Action Invalidation Gate: Cancel setup instantly if market breaches levels
        clean_sym = getattr(window, "current_sym", "XAUUSD").split("\n")[0].strip()
        tick = mt5.symbol_info_tick(clean_sym) if mt5.terminal_info() is not None else None
        if tick and hasattr(window, "line_order_sl") and hasattr(window, "line_order_entry"):
            try:
                cur_bid = float(tick.bid)
                cur_ask = float(tick.ask)
                entry_val = float(window.line_order_entry.value()) if window.line_order_entry.isVisible() else 0.0
                sl_val = float(window.line_order_sl.value()) if window.line_order_sl.isVisible() else 0.0
                tp_val = float(window.line_order_tp.value()) if (hasattr(window, "line_order_tp") and window.line_order_tp.isVisible()) else 0.0
                is_buy_proposal = (sl_val < entry_val) if (sl_val > 0 and entry_val > 0) else True

                price_invalidated = False
                if is_buy_proposal and sl_val > 0 and cur_bid <= sl_val:
                    price_invalidated = True
                elif not is_buy_proposal and sl_val > 0 and cur_ask >= sl_val:
                    price_invalidated = True
                elif is_buy_proposal and tp_val > 0 and cur_bid >= tp_val:
                    price_invalidated = True
                elif not is_buy_proposal and tp_val > 0 and cur_ask <= tp_val:
                    price_invalidated = True

                if price_invalidated:
                    timer.stop()
                    if hasattr(window, "_active_proposal_sig") and window._active_proposal_sig:
                        if not hasattr(window, "_discarded_signals"):
                            window._discarded_signals = set()
                        window._discarded_signals.add(window._active_proposal_sig)
                    if hasattr(window, "lblGateExpiryTime") and window.lblGateExpiryTime:
                        window.lblGateExpiryTime.setText("0s")
                    if hasattr(window, "btnApproveOrder") and window.btnApproveOrder:
                        window.btnApproveOrder.setEnabled(False)
                        window.btnApproveOrder.setText("INVALIDATED")
                    if hasattr(window, "lblSignalExpiry") and window.lblSignalExpiry:
                        window.lblSignalExpiry.setText("STATUS: SETUP INVALIDATED (PRICE BREACHED)")
                        window.lblSignalExpiry.setStyleSheet("color: #ef4444; font-family: 'Consolas', monospace; font-size: 9.5px; font-weight: bold;")
                    clear_manual_chart_lines(window)
                    window.order_proposal_active = False
                    return
            except Exception as e_inv:
                logger.debug(f"[TradingPlan] Invalidation tick check: {e_inv}")

        window._signal_expiry_remaining -= 1
        rem = window._signal_expiry_remaining
        if rem > 0:
            if hasattr(window, "lblGateExpiryTime") and window.lblGateExpiryTime:
                window.lblGateExpiryTime.setText(f"{rem}s")
            if hasattr(window, "barSignalExpiry") and window.barSignalExpiry:
                window.barSignalExpiry.setValue(rem)
        else:
            timer.stop()
            if hasattr(window, "_active_proposal_sig") and window._active_proposal_sig:
                if not hasattr(window, "_discarded_signals"):
                    window._discarded_signals = set()
                window._discarded_signals.add(window._active_proposal_sig)
            if hasattr(window, "lblGateExpiryTime") and window.lblGateExpiryTime:
                window.lblGateExpiryTime.setText("0s")
            if hasattr(window, "barSignalExpiry") and window.barSignalExpiry:
                window.barSignalExpiry.setValue(0)
            if hasattr(window, "btnApproveOrder") and window.btnApproveOrder:
                window.btnApproveOrder.setEnabled(False)
                window.btnApproveOrder.setText("EXPIRED")
            if hasattr(window, "lblSignalExpiry") and window.lblSignalExpiry:
                window.lblSignalExpiry.setText("STATUS: SIGNAL EXPIRED")
                window.lblSignalExpiry.setStyleSheet("color: #ef4444; font-family: 'Consolas', monospace; font-size: 9.5px; font-weight: bold;")
            clear_manual_chart_lines(window)
            window.order_proposal_active = False

    timer.timeout.connect(_tick)
    window._signal_expiry_timer = timer
    timer.start()


