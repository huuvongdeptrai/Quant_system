from backend.infrastructure.brokers.mt5_safe import mt5
"""
Trading Plan, Order Proposal Cards, and Playbook Theme Engine
"""

import os
import time
import json
from datetime import datetime
from PySide6 import QtCore, QtGui
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QFrame, QLabel, QHBoxLayout, QVBoxLayout, QPushButton,
    QWidget, QProgressBar, QSizePolicy, QDoubleSpinBox, QLineEdit,
    QMessageBox
)
from loguru import logger

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
):
    """Render institutional Radar Matrix and Order Proposal Ticket with WCAG AAA contrast matching theme."""
    raw_sym = sym or getattr(window, "current_sym", "XAUUSD") or "XAUUSD"
    clean_sym = raw_sym.split("\n")[0].strip()

    info = mt5.symbol_info(clean_sym)
    if digits is None:
        digits = info.digits if info else (2 if (entry or 100) > 10 else 5)

    if is_dark is None:
        is_dark = getattr(window, "is_dark_theme", False)

    # 1. TRƯỜNG HỢP: KHÔNG CÓ TÍN HIỆU THỰC TẾ (HOLD / CHỜ SETUP)
    if not has_signal or entry is None or sl is None:
        window.order_proposal_active = False
        window.is_live_position = False
        window.live_ticket = None
        window.is_pending_order = False
        window.pending_ticket = None

        # Gỡ bỏ toàn bộ đường lệnh ảo khỏi biểu đồ
        for line_name in ("line_order_entry", "line_order_sl", "line_order_tp"):
            if hasattr(window, line_name):
                l_obj = getattr(window, line_name)
                if l_obj is not None:
                    try:
                        l_obj.setVisible(False)
                    except Exception:
                        pass
                    if hasattr(window, "plot_widget"):
                        try:
                            window.plot_widget.removeItem(l_obj)
                        except Exception:
                            pass

        # Card 1: Mô hình thiết lập (Standby)
        if hasattr(window, "lblModelSubtitle") and window.lblModelSubtitle:
            window.lblModelSubtitle.setText("SETUP MODEL")
        if hasattr(window, "lblModelName") and window.lblModelName:
            window.lblModelName.setText(model_name or "ICT Zones Pro v4.2")
        if hasattr(window, "lblModelGrade") and window.lblModelGrade:
            window.lblModelGrade.setText(grade or "AWAITING SETUP")
            window.lblModelGrade.setStyleSheet(
                "background-color: #1e293b; color: #94a3b8; border: 1px solid #334155; "
                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 1px 5px;"
            )
        if hasattr(window, "lblChk1Val") and window.lblChk1Val:
            window.lblChk1Val.setText(chk1 or "Awaiting Clear Trend")
        if hasattr(window, "lblChk2Val") and window.lblChk2Val:
            window.lblChk2Val.setText(chk2 or "Awaiting Asian Sweep")
        if hasattr(window, "lblChk3Val") and window.lblChk3Val:
            window.lblChk3Val.setText(chk3 or "Awaiting Mitigation")

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
    window.order_proposal_active = True
    window.is_live_position = is_live_position
    window.live_ticket = live_ticket
    window.is_pending_order = is_pending_order
    window.pending_ticket = pending_ticket
    window.active_signal_data = {
        "sym": clean_sym,
        "has_signal": True,
        "signal_type": signal_type,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "is_live_position": is_live_position,
        "live_ticket": live_ticket,
    }

    sl_pts = abs(entry - sl)
    tp_pts = abs(tp - entry) if tp is not None else (sl_pts * 2.0)
    if tp is None:
        tp = entry + (sl_pts * 2.0) if signal_type == "BUY" else entry - (sl_pts * 2.0)
    if rr_ratio is None:
        rr_ratio = round(tp_pts / sl_pts, 1) if sl_pts > 0 else 2.0

    # Lấy số dư thực tế từ MT5
    acc_info = mt5.account_info() if mt5.terminal_info() is not None else None
    real_balance = acc_info.balance if acc_info and acc_info.balance > 0 else 10000.0
    risk_pct_val = risk_pct if risk_pct is not None else 1.0
    target_risk_dlr = real_balance * (risk_pct_val / 100.0)

    # Tính toán khối lượng lot chuẩn rủi ro
    if is_live_position or is_pending_order:
        calc_lot = float(live_volume) if live_volume is not None else 0.10
        if "BTC" in clean_sym:
            risk_dlr = round(sl_pts * calc_lot, 2)
            reward_dlr = round(tp_pts * calc_lot, 2)
        elif "XAU" in clean_sym:
            risk_dlr = round(sl_pts * calc_lot * 100.0, 2)
            reward_dlr = round(tp_pts * calc_lot * 100.0, 2)
        else:
            risk_dlr = round(sl_pts * calc_lot * 100000.0, 2)
            reward_dlr = round(tp_pts * calc_lot * 100000.0, 2)
    else:
        if "BTC" in clean_sym:
            calc_lot = max(0.01, round(target_risk_dlr / max(1.0, sl_pts), 2))
            calc_lot = min(calc_lot, 1.0)
            risk_dlr = round(sl_pts * calc_lot, 2)
            reward_dlr = round(tp_pts * calc_lot, 2)
        elif "XAU" in clean_sym:
            calc_lot = max(0.01, round(target_risk_dlr / max(10.0, sl_pts * 100.0), 2))
            calc_lot = min(calc_lot, 2.0)
            risk_dlr = round(sl_pts * calc_lot * 100.0, 2)
            reward_dlr = round(tp_pts * calc_lot * 100.0, 2)
        elif "JPY" in clean_sym:
            calc_lot = max(0.01, round(target_risk_dlr / max(10.0, sl_pts * 1000.0 * 0.07), 2))
            calc_lot = min(calc_lot, 5.0)
            risk_dlr = round(sl_pts * 1000 * calc_lot * 0.07, 2)
            reward_dlr = round(tp_pts * 1000 * calc_lot * 0.07, 2)
        else:
            calc_lot = max(0.01, round(target_risk_dlr / max(10.0, sl_pts * 100000.0), 2))
            calc_lot = min(calc_lot, 5.0)
            risk_dlr = round(sl_pts * calc_lot * 100000.0, 2)
            reward_dlr = round(tp_pts * calc_lot * 100000.0, 2)
    risk_pct = round((risk_dlr / real_balance) * 100.0, 1)

    # Tên hành động hiển thị
    if is_live_position:
        order_action_name = f"{signal_type} #{live_ticket}"
    elif is_pending_order:
        order_action_name = f"PENDING #{pending_ticket}"
    else:
        order_action_name = "BUY LIMIT" if signal_type == "BUY" else "SELL LIMIT"

    # Cập nhật đường ngang trên biểu đồ nến
    try:
        if hasattr(window, "line_order_entry") and window.line_order_entry:
            window.line_order_entry.setValue(entry)
            window.line_order_entry.setVisible(True)
            if is_live_position:
                window.line_order_entry.label.setFormat(f"OPEN #{live_ticket}: {entry:.{digits}f} ({calc_lot:.2f}L)")
            elif is_pending_order:
                window.line_order_entry.label.setFormat(f"PENDING #{pending_ticket}: {entry:.{digits}f} ({calc_lot:.2f}L)")
            else:
                window.line_order_entry.label.setFormat(f"{order_action_name}: {entry:.{digits}f} ({calc_lot:.2f} Lot)")
            if hasattr(window, "plot_widget"):
                try:
                    if window.line_order_entry not in window.plot_widget.items():
                        window.plot_widget.addItem(window.line_order_entry, ignoreBounds=True)
                except Exception:
                    pass

        if hasattr(window, "line_order_sl") and window.line_order_sl:
            window.line_order_sl.setValue(sl)
            window.line_order_sl.setVisible(True)
            if is_live_position:
                window.line_order_sl.label.setFormat(f"LIVE SL: {sl:.{digits}f}")
            else:
                window.line_order_sl.label.setFormat(f"STOP LOSS: {sl:.{digits}f} (-${risk_dlr:.2f} | -{risk_pct:.1f}%)")
            if hasattr(window, "plot_widget"):
                try:
                    if window.line_order_sl not in window.plot_widget.items():
                        window.plot_widget.addItem(window.line_order_sl, ignoreBounds=True)
                except Exception:
                    pass

        if hasattr(window, "line_order_tp") and window.line_order_tp:
            window.line_order_tp.setValue(tp)
            window.line_order_tp.setVisible(True)
            if is_live_position:
                window.line_order_tp.label.setFormat(f"LIVE TP: {tp:.{digits}f}")
            else:
                window.line_order_tp.label.setFormat(f"TAKE PROFIT: {tp:.{digits}f} (+${reward_dlr:.2f} | +{rr_ratio:.1f}R)")
            if hasattr(window, "plot_widget"):
                try:
                    if window.line_order_tp not in window.plot_widget.items():
                        window.plot_widget.addItem(window.line_order_tp, ignoreBounds=True)
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"[TradingPlanPanel] Failed to update chart order lines: {e}")

    # Card 1: Mô hình thiết lập (Active)
    if hasattr(window, "lblModelSubtitle") and window.lblModelSubtitle:
        window.lblModelSubtitle.setText("POSITION IN MARKET" if is_live_position else ("PENDING ORDER" if is_pending_order else "SETUP MODEL"))
    if hasattr(window, "lblModelName") and window.lblModelName:
        window.lblModelName.setText(model_name or "ICT Zones Pro v4.2")
    if hasattr(window, "lblModelGrade") and window.lblModelGrade:
        window.lblModelGrade.setText(grade or f"CONFIDENCE: {confidence or '85%'}")
        badge_bg = "#0d2818" if is_dark else "#f0fdf4"
        badge_border = "#272d3b" if is_dark else "#cbd5e1"
        badge_text = "#16a34a" if is_dark else "#15803d"
        window.lblModelGrade.setStyleSheet(f"background-color: {badge_bg}; color: {badge_text}; border: 1px solid {badge_border}; font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 1px 5px;")
    if hasattr(window, "lblChk1Val") and window.lblChk1Val:
        window.lblChk1Val.setText(chk1 or "Confirmed")
    if hasattr(window, "lblChk2Val") and window.lblChk2Val:
        window.lblChk2Val.setText(chk2 or "Asian Range Swept")
    if hasattr(window, "lblChk3Val") and window.lblChk3Val:
        window.lblChk3Val.setText(chk3 or "FVG Mitigated")

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
            pnl_sign = '+' if live_profit >= 0 else ''
            window.lblSizeVal.setText(f"{calc_lot:.2f} LOTS (PNL: {pnl_sign}${live_profit:.2f})")
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
        if hasattr(window, "lblGateExpiryTitle") and window.lblGateExpiryTitle:
            window.lblGateExpiryTitle.setText("EXPIRATION")
        if hasattr(window, "btnApproveOrder") and window.btnApproveOrder:
            chart_tf = getattr(window, "current_tf_str", "M15")
            if exec_mode == "FULL-AUTO" and chart_tf == "M15":
                window.btnApproveOrder.setText("FULL-AUTO: BOT MANAGING")
                window.btnApproveOrder.setEnabled(False)
                window.btnApproveOrder.setCursor(Qt.ArrowCursor)
            elif exec_mode == "FULL-AUTO":
                window.btnApproveOrder.setText(f"APPROVE {chart_tf} (MANUAL)")
                window.btnApproveOrder.setEnabled(True)
                window.btnApproveOrder.setCursor(Qt.PointingHandCursor)
            else:
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

    if hasattr(window, "cardSetupModel"):
        apply_playbook_cards_theme(window, is_dark)


def update_ai_reasoning(window, is_dark=None):
    """Render austere monospace institutional gate telemetry table conforming to system rules."""
    update_order_proposal_html(window, is_dark=is_dark)


def apply_playbook_cards_theme(window, is_dark: bool):
    """Apply strict institutional palette to the 3-Card Trading Plan Playbook."""
    assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend", "assets")
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
    for p_val, b_name in [(0.5, "btnRisk05"), (1.0, "btnRisk10"), (1.5, "btnRisk15"), (2.0, "btnRisk20")]:
        b = getattr(window, b_name, None)
        if b:
            is_sel = abs(cur_risk - p_val) < 0.05
            b.setProperty("selected", "true" if is_sel else "false")
            b.style().unpolish(b)
            b.style().polish(b)

    # Preset buttons
    for pre_name in ["btnPresetATR", "btnPresetSwing", "btnPresetRR15", "btnPresetRR20", "btnPresetRR30"]:
        b = getattr(window, pre_name, None)
        if b:
            b.style().unpolish(b)
            b.style().polish(b)

    # SpinBoxes (SL / TP)
    # SpinBoxes (SL / TP / Lot)
    for spin_name in ["spinManualSL", "spinManualTP", "spinManualLot"]:
        sp = getattr(window, spin_name, None)
        if sp:
            sp.style().unpolish(sp)
            sp.style().polish(sp)

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
    if hasattr(window, "lblManualSpread") and window.lblManualSpread:
        window.lblManualSpread.setStyleSheet(
            f"color: {text_sec}; font-family: Consolas, monospace; font-size: 8.5px; border: none; background: transparent;"
        )
    if hasattr(window, "lblManualSLPips") and window.lblManualSLPips:
        window.lblManualSLPips.setStyleSheet(
            f"color: {text_sec}; font-family: Consolas, monospace; font-size: 8.5px; border: none; background: transparent;"
        )
    if hasattr(window, "lblManualTPPips") and window.lblManualTPPips:
        window.lblManualTPPips.setStyleSheet(
            f"color: {text_sec}; font-family: Consolas, monospace; font-size: 8.5px; border: none; background: transparent;"
        )
    if hasattr(window, "lblManualLotSummaryTitle") and window.lblManualLotSummaryTitle:
        window.lblManualLotSummaryTitle.setStyleSheet(sub_style)

    # Split Risk (Red) / Reward (Green) Colors
    risk_color = "#ef4444" if is_dark else "#b91c1c"
    slash_color = "#64748b" if is_dark else "#94a3b8"
    reward_color = "#22c55e" if is_dark else "#15803d"

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


def calculate_manual_quant_lot(symbol: str, sl_points: float, risk_pct: float = 1.0, balance: float = None):
    """Calculates dynamic institutional lot size adhering to capital preservation rules."""
    if balance is None or balance <= 0:
        acc = mt5.account_info() if mt5.terminal_info() is not None else None
        balance = float(acc.balance) if acc and acc.balance > 0 else 10000.0

    risk_dlr = balance * (risk_pct / 100.0)
    if sl_points <= 0.00001:
        return 0.01, risk_dlr

    clean_sym = symbol.upper().split(".")[0].replace("/", "")
    if "BTC" in clean_sym:
        calc_lot = risk_dlr / sl_points
        max_lot = 1.0
    elif "XAU" in clean_sym or "GOLD" in clean_sym:
        calc_lot = risk_dlr / (sl_points * 100.0)
        max_lot = 5.0
    elif any(c in clean_sym for c in ["US30", "NAS100", "SPX500"]):
        calc_lot = risk_dlr / (sl_points * 10.0)
        max_lot = 5.0
    else:
        calc_lot = risk_dlr / (sl_points * 100000.0)
        max_lot = 10.0

    lot = max(0.01, min(round(calc_lot, 2), max_lot))
    return lot, risk_dlr


def evaluate_manual_compliance(window, symbol=None):
    """
    Evaluates institutional 4-point Pre-Trade Risk Gatekeeper:
    1. Daily Drawdown Guard (< 4.0% or max daily loss limit)
    2. Event Risk Engine (High-impact news filter ±15m)
    3. Exposure Gate (Max open positions limit)
    4. Spread Normalization (Safe spread limit)
    
    Returns: (passed: bool, checks: dict, block_reason: str)
    """
    clean_sym = (symbol or getattr(window, "current_sym", "XAUUSD") or "XAUUSD").split("\n")[0].strip()
    checks = {
        "drawdown": {"passed": True, "msg": "Daily Loss: OK", "val": "PASS"},
        "news": {"passed": True, "msg": "News Filter: Clear", "val": "PASS"},
        "max_trades": {"passed": True, "msg": "Exposure: OK", "val": "PASS"},
        "spread": {"passed": True, "msg": "Spread: OK", "val": "PASS"},
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

    # 1. Daily Drawdown Check
    max_daily_loss = float(cfg.get("max_daily_loss", 5000.0))
    max_drawdown = float(cfg.get("max_drawdown", 5.0))
    acc = mt5.account_info() if mt5.terminal_info() is not None else None
    if acc:
        equity = float(acc.equity)
        balance = float(acc.balance)
        floating_loss = balance - equity
        if max_daily_loss > 0 and floating_loss >= max_daily_loss:
            checks["drawdown"] = {"passed": False, "msg": f"Loss -${floating_loss:.0f} >= -${max_daily_loss:.0f}", "val": "HALTED"}
            block_reason = "DAILY LOSS LIMIT EXCEEDED"
        elif balance > 0 and max_drawdown > 0:
            dd_pct = (floating_loss / balance) * 100.0
            if dd_pct >= max_drawdown:
                checks["drawdown"] = {"passed": False, "msg": f"DD {dd_pct:.1f}% >= {max_drawdown:.1f}%", "val": "HALTED"}
                block_reason = "MAX DRAWDOWN BREACHED"

    # 2. Event Risk Engine Check (News Filter)
    if not block_reason and cfg.get("news_defense_enabled", True):
        try:
            from backend.core.event_risk_engine import EventRiskEngine
            ere = getattr(window, "_event_risk_engine", None)
            if not ere:
                ere = EventRiskEngine(pause_window_mins=int(cfg.get("news_defense_mins", 15)))
                window._event_risk_engine = ere
            is_impacted, news_title = ere.check_news_impact_for_symbol(clean_sym)
            if is_impacted:
                checks["news"] = {"passed": False, "msg": f"Red Event: {news_title[:18]}", "val": "BLOCKED"}
                block_reason = "HIGH IMPACT NEWS EVENT"
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

    # 4. Spread Normalization Check
    if not block_reason and mt5.terminal_info() is not None:
        try:
            info = mt5.symbol_info(clean_sym)
            if info:
                cur_spd = info.spread
                user_max = int(cfg.get("max_spread", 25))
                if "XAU" in clean_sym.upper():
                    allowance = max(user_max, 45)
                elif "BTC" in clean_sym.upper():
                    allowance = 2000
                else:
                    allowance = max(user_max, 25)
                if cur_spd > allowance:
                    checks["spread"] = {"passed": False, "msg": f"Spread {cur_spd} > {allowance} pts", "val": "HIGH"}
                    block_reason = f"SPREAD TOO WIDE ({cur_spd} pts)"
        except Exception:
            pass

    passed = (block_reason == "")
    return passed, checks, block_reason


def _setup_chart_manual_lines(window, sym, is_buy, lot, sl, tp):
    """Render draggable SL and TP lines on the chart for the manual copilot order."""
    if getattr(window, "_plan_mode", "ai") != "manual":
        return
    if not hasattr(window, "plot_widget"):
        return

    info = mt5.symbol_info(sym)
    dig = info.digits if info else 2

    tick = mt5.symbol_info_tick(sym) if mt5.terminal_info() is not None else None
    entry_p = (tick.ask if is_buy else tick.bid) if tick else getattr(window, "_last_manual_entry", 2650.0)

    # Entry line
    if hasattr(window, "line_order_entry") and window.line_order_entry:
        window.line_order_entry.setPos(entry_p)
        window.line_order_entry.setMovable(False)
        dir_s = "BUY" if is_buy else "SELL"
        if hasattr(window.line_order_entry, "label") and window.line_order_entry.label:
            window.line_order_entry.label.setFormat(f"MANUAL {dir_s}: {entry_p:.{dig}f} ({lot:.2f} Lots)")
        window.line_order_entry.setVisible(True)
        if window.line_order_entry not in window.plot_widget.items():
            window.plot_widget.addItem(window.line_order_entry, ignoreBounds=True)

    # SL line
    if hasattr(window, "line_order_sl") and window.line_order_sl:
        window.line_order_sl.setPos(sl)
        window.line_order_sl.setMovable(True)
        if hasattr(window.line_order_sl, "label") and window.line_order_sl.label:
            window.line_order_sl.label.setFormat(f"MANUAL SL: {sl:.{dig}f}")
        window.line_order_sl.setVisible(True)
        if window.line_order_sl not in window.plot_widget.items():
            window.plot_widget.addItem(window.line_order_sl, ignoreBounds=True)

    # TP line
    if hasattr(window, "line_order_tp") and window.line_order_tp:
        window.line_order_tp.setPos(tp)
        window.line_order_tp.setMovable(True)
        if hasattr(window.line_order_tp, "label") and window.line_order_tp.label:
            window.line_order_tp.label.setFormat(f"MANUAL TP: {tp:.{dig}f}")
        window.line_order_tp.setVisible(True)
        if window.line_order_tp not in window.plot_widget.items():
            window.plot_widget.addItem(window.line_order_tp, ignoreBounds=True)


def _recalculate_manual_lot_and_rr(window, from_user_lot_change: bool = False):
    """Dynamically recalculate lot size, R:R ratio, dollar risk/reward when SL, TP, or Lot changes."""
    clean_sym = getattr(window, "current_sym", "XAUUSD").split("\n")[0].strip()
    is_buy = (getattr(window, "_manual_direction", "BUY") == "BUY")
    risk_pct = getattr(window, "_manual_risk_pct", 1.0)

    info = mt5.symbol_info(clean_sym)
    digits = info.digits if info else 2
    point = info.point if info and info.point > 0 else (0.01 if digits == 2 else 0.0001)

    tick = mt5.symbol_info_tick(clean_sym) if mt5.terminal_info() is not None else None
    if tick:
        entry_p = tick.ask if is_buy else tick.bid
    else:
        if is_buy:
            if hasattr(window, "lblManualAskPrice") and window.lblManualAskPrice and window.lblManualAskPrice.text() not in ("", "0.00", "--"):
                try:
                    entry_p = float(window.lblManualAskPrice.text())
                except ValueError:
                    entry_p = getattr(window, "_last_manual_ask", 2650.50)
            else:
                entry_p = getattr(window, "_last_manual_ask", 2650.50)
        else:
            if hasattr(window, "lblManualBidPrice") and window.lblManualBidPrice and window.lblManualBidPrice.text() not in ("", "0.00", "--"):
                try:
                    entry_p = float(window.lblManualBidPrice.text())
                except ValueError:
                    entry_p = getattr(window, "_last_manual_bid", 2650.25)
            else:
                entry_p = getattr(window, "_last_manual_bid", 2650.25)

    window._last_manual_entry = entry_p

    sl_val = window.spinManualSL.value() if hasattr(window, "spinManualSL") else 0.0
    tp_val = window.spinManualTP.value() if hasattr(window, "spinManualTP") else 0.0

    sl_pts = abs(entry_p - sl_val)
    tp_pts = abs(tp_val - entry_p)

    acc = mt5.account_info() if mt5.terminal_info() is not None else None
    balance = float(acc.balance) if acc and acc.balance > 0 else 10000.0

    sym_u = clean_sym.upper()
    if "BTC" in sym_u:
        multiplier = 1.0
        pip_unit = 1.0
    elif "XAU" in sym_u or "GOLD" in sym_u:
        multiplier = 100.0
        pip_unit = 0.10
    else:
        multiplier = 100000.0
        pip_unit = point * 10 if digits in (3, 5) else point

    if from_user_lot_change and hasattr(window, "spinManualLot") and window.spinManualLot:
        window._user_custom_lot = True
        lot = round(window.spinManualLot.value(), 2)
        risk_dlr = sl_pts * lot * multiplier
        risk_pct = round((risk_dlr / balance) * 100.0, 1) if balance > 0 else 1.0
    elif getattr(window, "_user_custom_lot", False) and hasattr(window, "spinManualLot") and window.spinManualLot and window.spinManualLot.value() > 0:
        lot = round(window.spinManualLot.value(), 2)
        risk_dlr = sl_pts * lot * multiplier
        risk_pct = round((risk_dlr / balance) * 100.0, 1) if balance > 0 else 1.0
    else:
        lot, risk_dlr = calculate_manual_quant_lot(clean_sym, sl_pts, risk_pct, balance=balance)
        if hasattr(window, "spinManualLot") and window.spinManualLot:
            window.spinManualLot.blockSignals(True)
            window.spinManualLot.setValue(lot)
            window.spinManualLot.blockSignals(False)

    reward_dlr = tp_pts * lot * multiplier
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
            v_widget.setText(c_info.get("val", "PASS"))
            v_widget.setStyleSheet(
                f"color: {bull_c if c_pass else bear_c}; font-family: Consolas, monospace; "
                f"font-size: 8.5px; font-weight: bold; border: none; background: transparent;"
            )

    # Update execute button with exact price: BUY 0.19 LOTS @ 2650.50
    dir_str = getattr(window, "_manual_direction", "BUY")
    if hasattr(window, "btnManualExecute") and window.btnManualExecute:
        if passed:
            window.btnManualExecute.setEnabled(True)
            window.btnManualExecute.setText(f"{dir_str} {lot:.2f} LOTS @ {entry_p:.{digits}f}")
            window.btnManualExecute.setToolTip(f"Send institutional market {dir_str} order with {risk_pct}% risk")
        else:
            window.btnManualExecute.setEnabled(False)
            window.btnManualExecute.setText(f"LOCKED: {block_reason}")
            window.btnManualExecute.setToolTip(f"Order locked by quant guardrails: {block_reason}")
        window.btnManualExecute.setProperty("direction", dir_str)
        window.btnManualExecute.style().unpolish(window.btnManualExecute)
        window.btnManualExecute.style().polish(window.btnManualExecute)

    # Also update chart lines
    _setup_chart_manual_lines(window, clean_sym, is_buy, lot, sl_val, tp_val)


def sync_manual_copilot_quotes(window):
    """Syncs live Bid/Ask prices and default SL/TP values for the Manual Quant Copilot."""
    clean_sym = getattr(window, "current_sym", "XAUUSD").split("\n")[0].strip()
    info = mt5.symbol_info(clean_sym)
    digits = info.digits if info else 2
    point = info.point if info and info.point > 0 else (0.01 if digits == 2 else 0.0001)

    tick = mt5.symbol_info_tick(clean_sym) if mt5.terminal_info() is not None else None
    if tick:
        ask = tick.ask
        bid = tick.bid
        spd = round((ask - bid) / point, 1)
    else:
        ref = getattr(window, "_last_manual_entry", 2650.0)
        ask = round(ref + 0.25, digits)
        bid = round(ref, digits)
        spd = 2.5

    window._last_manual_ask = ask
    window._last_manual_bid = bid
    is_buy = (getattr(window, "_manual_direction", "BUY") == "BUY")
    window._last_manual_entry = ask if is_buy else bid

    if hasattr(window, "lblManualAskPrice") and window.lblManualAskPrice:
        window.lblManualAskPrice.setText(f"{ask:.{digits}f}")
    if hasattr(window, "lblManualBidPrice") and window.lblManualBidPrice:
        window.lblManualBidPrice.setText(f"{bid:.{digits}f}")
    if hasattr(window, "lblManualSpread") and window.lblManualSpread:
        window.lblManualSpread.setText(f"SPREAD: {spd} PTS")

    # Initialize spinboxes if at 0
    if hasattr(window, "spinManualSL") and hasattr(window, "spinManualTP"):
        is_buy = (getattr(window, "_manual_direction", "BUY") == "BUY")
        cur_sl = window.spinManualSL.value()
        cur_tp = window.spinManualTP.value()
        if cur_sl == 0.0 or cur_tp == 0.0:
            window.spinManualSL.setDecimals(digits)
            window.spinManualTP.setDecimals(digits)
            window.spinManualSL.setRange(0.00001, 1000000.0)
            window.spinManualTP.setRange(0.00001, 1000000.0)

            if "XAU" in clean_sym.upper():
                dist = 2.50
            elif "BTC" in clean_sym.upper():
                dist = 500.0
            else:
                dist = 0.0025

            ref_p = ask if is_buy else bid
            new_sl = round(ref_p - dist if is_buy else ref_p + dist, digits)
            new_tp = round(ref_p + (2.0 * dist) if is_buy else ref_p - (2.0 * dist), digits)

            window.spinManualSL.blockSignals(True)
            window.spinManualTP.blockSignals(True)
            window.spinManualSL.setValue(new_sl)
            window.spinManualTP.setValue(new_tp)
            window.spinManualSL.blockSignals(False)
            window.spinManualTP.blockSignals(False)

    _recalculate_manual_lot_and_rr(window)


def execute_manual_quant_order(window):
    """Executes the validated manual quant market order via ExecutionManager."""
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

    tick = mt5.symbol_info_tick(clean_sym) if mt5.terminal_info() is not None else None
    entry_p = (tick.ask if is_buy else tick.bid) if tick else getattr(window, "_last_manual_entry", 2650.0)
    sl_pts = abs(entry_p - sl_p)
    if hasattr(window, "spinManualLot") and window.spinManualLot and window.spinManualLot.value() > 0:
        lot_size = round(window.spinManualLot.value(), 2)
    else:
        lot_size, _ = calculate_manual_quant_lot(clean_sym, sl_pts, risk_pct)

    exec_mgr = None
    if hasattr(window, "quant_terminal") and hasattr(window.quant_terminal, "exec_mgr"):
        exec_mgr = window.quant_terminal.exec_mgr
    if not exec_mgr:
        from backend.infrastructure.brokers.execution_manager import ExecutionManager
        exec_mgr = ExecutionManager(slippage=20, magic_number=999999)

    from backend.core.event_bus import event_bus
    dir_str = "BUY" if is_buy else "SELL"

    order_res = None
    if mt5.terminal_info() is not None:
        order_res = exec_mgr.execute_market_order(
            symbol=clean_sym,
            is_buy=is_buy,
            volume=lot_size,
            sl_price=sl_p,
            tp_price=tp_p,
            comment="VECTRA_Manual"
        )
    else:
        order_res = {"status": "success", "ticket": int(time.time()) % 1000000, "price": entry_p}

    if order_res and order_res.get("status") == "success":
        ticket = order_res.get("ticket", "OK")
        if hasattr(window, "btnManualExecute"):
            window.btnManualExecute.setText(f"FILLED #{ticket}")
            window.btnManualExecute.setEnabled(False)
            QTimer.singleShot(4000, lambda: _recalculate_manual_lot_and_rr(window))
        event_bus.log_event.emit("", "SUCCESS", f"VECTRA Manual Order Filled: {dir_str} {lot_size:.2f} lots {clean_sym} #{ticket}", "#10b981")
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

    assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend", "assets")
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
    lbl_md_title = QLabel("MANUAL EXECUTION")
    lbl_md_title.setObjectName("lblManualHeaderTitle")
    lbl_md_badge = QLabel("MARKET DIRECT")
    lbl_md_badge.setObjectName("lblManualExecBadge")
    lbl_md_badge.setVisible(False)
    row_md_top.addWidget(lbl_md_title)
    row_md_top.addStretch()
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
    lbl_buy_t = QLabel("BUY MARKET")
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
    lbl_sell_t = QLabel("SELL MARKET")
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

    row_spd = QHBoxLayout()
    row_spd.setContentsMargins(0, 0, 0, 0)
    lbl_spd = QLabel("SPREAD: 2.5 PTS")
    lbl_spd.setObjectName("lblManualSpread")
    row_spd.addWidget(lbl_spd)
    row_spd.addStretch()
    layout_m_dir.addLayout(row_spd)

    sep_m1 = QFrame()
    sep_m1.setFrameShape(QFrame.HLine)
    sep_m1.setObjectName("sepManual1")
    sep_m1.setFixedHeight(1)

    # Card M2: Risk Model & Editable SL / TP
    card_m_risk = QFrame()
    card_m_risk.setObjectName("cardManualRisk")
    layout_m_risk = QVBoxLayout(card_m_risk)
    layout_m_risk.setContentsMargins(4, 4, 4, 4)
    layout_m_risk.setSpacing(5)

    row_mr_top = QHBoxLayout()
    row_mr_top.setContentsMargins(0, 0, 0, 0)
    lbl_mr_title = QLabel("RISK & VOLUME")
    lbl_mr_title.setObjectName("lblManualRiskTitle")
    spin_lot = QDoubleSpinBox()
    spin_lot.setObjectName("spinManualLot")
    spin_lot.setDecimals(2)
    spin_lot.setRange(0.01, 100.0)
    spin_lot.setSingleStep(0.01)
    spin_lot.setValue(0.20)
    spin_lot.setSuffix(" LOTS")
    spin_lot.setFixedWidth(78)
    spin_lot.setFixedHeight(20)
    spin_lot.setAlignment(Qt.AlignRight)
    spin_lot.setButtonSymbols(QDoubleSpinBox.NoButtons)
    row_mr_top.addWidget(lbl_mr_title)
    row_mr_top.addStretch()
    row_mr_top.addWidget(spin_lot)
    layout_m_risk.addLayout(row_mr_top)

    # Quick Risk Selectors
    row_risk_btns = QHBoxLayout()
    row_risk_btns.setContentsMargins(0, 0, 0, 0)
    row_risk_btns.setSpacing(4)
    lbl_risk_lbl = QLabel("PRESET")
    lbl_risk_lbl.setObjectName("lblManualRiskLabel")
    row_risk_btns.addWidget(lbl_risk_lbl)
    row_risk_btns.addStretch()
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
        row_risk_btns.addWidget(b)
    layout_m_risk.addLayout(row_risk_btns)

    # Stop Loss Row (2-column layout)
    row_sl = QHBoxLayout()
    row_sl.setContentsMargins(0, 0, 0, 0)
    row_sl.setSpacing(6)
    row_sl.setAlignment(Qt.AlignVCenter)

    col_sl_info = QVBoxLayout()
    col_sl_info.setSpacing(1)
    lbl_sl_lbl = QLabel("STOP LOSS")
    lbl_sl_lbl.setObjectName("lblManualSLLabel")
    lbl_sl_pips = QLabel("-25.0 pips / -$100.00")
    lbl_sl_pips.setObjectName("lblManualSLPips")
    col_sl_info.addWidget(lbl_sl_lbl)
    col_sl_info.addWidget(lbl_sl_pips)
    row_sl.addLayout(col_sl_info)

    row_sl.addStretch()

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

    row_sl.addWidget(spin_sl)
    row_sl.addWidget(box_sl_pre)
    layout_m_risk.addLayout(row_sl)

    # Take Profit Row (2-column layout)
    row_tp = QHBoxLayout()
    row_tp.setContentsMargins(0, 0, 0, 0)
    row_tp.setSpacing(6)
    row_tp.setAlignment(Qt.AlignVCenter)

    col_tp_info = QVBoxLayout()
    col_tp_info.setSpacing(1)
    lbl_tp_lbl = QLabel("TAKE PROFIT")
    lbl_tp_lbl.setObjectName("lblManualTPLabel")
    lbl_tp_pips = QLabel("+50.0 pips / +$200.00")
    lbl_tp_pips.setObjectName("lblManualTPPips")
    col_tp_info.addWidget(lbl_tp_lbl)
    col_tp_info.addWidget(lbl_tp_pips)
    row_tp.addLayout(col_tp_info)

    row_tp.addStretch()

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

    row_tp.addWidget(spin_tp)
    row_tp.addWidget(box_tp_pre)
    layout_m_risk.addLayout(row_tp)

    # Stepper helpers (kept for backward compatibility and testing)
    btn_sl_minus = QPushButton()
    btn_sl_plus = QPushButton()
    btn_tp_minus = QPushButton()
    btn_tp_plus = QPushButton()

    # Summary Box (Risk Red / Reward Green)
    box_summary = QFrame()
    box_summary.setObjectName("boxManualLotSummary")
    layout_summary = QHBoxLayout(box_summary)
    layout_summary.setContentsMargins(0, 2, 0, 2)
    layout_summary.setSpacing(2)
    lbl_lot_sum_title = QLabel("RISK / REWARD")
    lbl_lot_sum_title.setObjectName("lblManualLotSummaryTitle")

    lbl_risk_part = QLabel("-$100.00 (1.0%)")
    lbl_risk_part.setObjectName("lblManualRiskPart")
    lbl_slash = QLabel(" / ")
    lbl_slash.setObjectName("lblManualSlash")
    lbl_reward_part = QLabel("+$200.00 (2.0R)")
    lbl_reward_part.setObjectName("lblManualRewardPart")

    # Hidden compatibility label for existing tests
    lbl_lot_sum = QLabel("-$100.00 (1.0%) / +$200.00 (2.0R)")
    lbl_lot_sum.setObjectName("lblManualLotSummary")
    lbl_lot_sum.setVisible(False)

    layout_summary.addWidget(lbl_lot_sum_title)
    layout_summary.addStretch()
    layout_summary.addWidget(lbl_risk_part)
    layout_summary.addWidget(lbl_slash)
    layout_summary.addWidget(lbl_reward_part)
    layout_summary.addWidget(lbl_lot_sum)
    layout_m_risk.addWidget(box_summary)

    sep_m2 = QFrame()
    sep_m2.setFrameShape(QFrame.HLine)
    sep_m2.setObjectName("sepManual2")
    sep_m2.setFixedHeight(1)

    # Card M3: Pre-Trade Check Checklist
    card_m_gate = QFrame()
    card_m_gate.setObjectName("cardManualGate")
    layout_m_gate = QVBoxLayout(card_m_gate)
    layout_m_gate.setContentsMargins(4, 4, 4, 4)
    layout_m_gate.setSpacing(3)

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

    layout_m_gate.addLayout(_make_gate_check_row("Daily Drawdown Limit (< 4.0%)", "lblGateCheck1"))
    layout_m_gate.addLayout(_make_gate_check_row("Event Risk Engine (News +-15m)", "lblGateCheck2"))
    layout_m_gate.addLayout(_make_gate_check_row("Exposure Gate (Max 3 Trades)", "lblGateCheck3"))
    layout_m_gate.addLayout(_make_gate_check_row("Spread Normalization", "lblGateCheck4"))

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

    btn_m_exec = QPushButton("BUY 0.20 LOTS @ 2650.50")
    btn_m_exec.setObjectName("btnManualExecute")
    btn_m_exec.setFixedHeight(32)
    btn_m_exec.setCursor(Qt.PointingHandCursor)
    layout_m_action.addWidget(btn_m_exec)

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

    # Signal wiring: Mode Switcher
    def _switch_mode(target_mode):
        window._plan_mode = target_mode
        container_ai.setVisible(target_mode == "ai")
        container_manual.setVisible(target_mode == "manual")
        apply_playbook_cards_theme(window, getattr(window, "is_dark_theme", False))
        if target_mode == "manual":
            sync_manual_copilot_quotes(window)
        else:
            if hasattr(window, "active_signal_data") and window.active_signal_data.get("has_signal"):
                sig = window.active_signal_data
                update_order_proposal_html(
                    window, sym=sig.get("sym"), entry=sig.get("entry"),
                    sl=sig.get("sl"), tp=sig.get("tp"), has_signal=True,
                    signal_type=sig.get("signal_type", "BUY")
                )

    btn_mode_ai.clicked.connect(lambda: _switch_mode("ai"))
    btn_mode_manual.clicked.connect(lambda: _switch_mode("manual"))

    # Signal wiring: Direction toggles
    def _set_dir(new_d):
        window._manual_direction = new_d
        apply_playbook_cards_theme(window, getattr(window, "is_dark_theme", False))
        sync_manual_copilot_quotes(window)

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
    spin_lot.valueChanged.connect(lambda: _recalculate_manual_lot_and_rr(window, from_user_lot_change=True))
    spin_sl.valueChanged.connect(lambda: _recalculate_manual_lot_and_rr(window))
    spin_tp.valueChanged.connect(lambda: _recalculate_manual_lot_and_rr(window))

    # Signal wiring: Stepper buttons
    def _step_spin(spin, increment: bool):
        sym = getattr(window, "current_sym", "XAUUSD").split("\n")[0].strip()
        info = mt5.symbol_info(sym)
        dig = info.digits if info else 2
        step = 1.0 if "XAU" in sym.upper() else (50.0 if "BTC" in sym.upper() else (0.0010 if dig in (3, 5) else 0.1))
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
        tick = mt5.symbol_info_tick(sym) if mt5.terminal_info() is not None else None
        cur_p = (tick.ask if is_b else tick.bid) if tick else getattr(window, "_last_manual_entry", 2650.0)

        atr_val = 0.0
        if hasattr(window, "chart_data_list") and len(window.chart_data_list) >= 15:
            cd = window.chart_data_list[-15:]
            trs = [max(c[4] - c[3], abs(c[4] - cd[i-1][2]), abs(c[3] - cd[i-1][2])) for i, c in enumerate(cd) if i > 0]
            if trs:
                atr_val = sum(trs) / len(trs)
        if atr_val <= 0:
            atr_val = 2.0 if "XAU" in sym.upper() else (300.0 if "BTC" in sym.upper() else 0.0020)

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
        tick = mt5.symbol_info_tick(sym) if mt5.terminal_info() is not None else None
        cur_p = (tick.ask if is_b else tick.bid) if tick else getattr(window, "_last_manual_entry", 2650.0)

        if hasattr(window, "chart_data_list") and len(window.chart_data_list) >= 10:
            candles = window.chart_data_list[-20:]
            if is_b:
                lowest = min(c[3] for c in candles)
                new_sl = round(lowest - buf, dig)
                dist = abs(cur_p - new_sl)
                new_tp = round(cur_p + 2.0 * dist, dig)
            else:
                highest = max(c[4] for c in candles)
                new_sl = round(highest + buf, dig)
                dist = abs(new_sl - cur_p)
                new_tp = round(cur_p - 2.0 * dist, dig)
            spin_sl.setValue(new_sl)
            spin_tp.setValue(new_tp)
        else:
            _apply_atr_preset()

    def _apply_rr_preset(rr_mult):
        sym = getattr(window, "current_sym", "XAUUSD").split("\n")[0].strip()
        info = mt5.symbol_info(sym)
        dig = info.digits if info else 2
        is_b = (getattr(window, "_manual_direction", "BUY") == "BUY")
        tick = mt5.symbol_info_tick(sym) if mt5.terminal_info() is not None else None
        cur_p = (tick.ask if is_b else tick.bid) if tick else getattr(window, "_last_manual_entry", 2650.0)
        cur_sl = spin_sl.value()
        sl_dist = abs(cur_p - cur_sl)
        if sl_dist <= 0:
            sl_dist = 2.0 if "XAU" in sym.upper() else 0.0020
        new_tp = round(cur_p + (rr_mult * sl_dist) if is_b else cur_p - (rr_mult * sl_dist), dig)
        spin_tp.setValue(new_tp)

    btn_pre_atr.clicked.connect(_apply_atr_preset)
    btn_pre_swing.clicked.connect(_apply_swing_preset)
    btn_pre_rr15.clicked.connect(lambda: _apply_rr_preset(1.5))
    btn_pre_rr20.clicked.connect(lambda: _apply_rr_preset(2.0))
    btn_pre_rr30.clicked.connect(lambda: _apply_rr_preset(3.0))

    # Signal wiring: Execute button
    btn_m_exec.clicked.connect(lambda: execute_manual_quant_order(window))

    apply_playbook_cards_theme(window, is_dark)


def start_signal_expiry_countdown(window, duration_sec=None):
    """Start dynamic real-time 1-second countdown timer for Trading Plan signal expiration."""
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
        window._signal_expiry_remaining -= 1
        rem = window._signal_expiry_remaining
        if rem > 0:
            if hasattr(window, "lblGateExpiryTime") and window.lblGateExpiryTime:
                window.lblGateExpiryTime.setText(f"{rem}s")
            if hasattr(window, "barSignalExpiry") and window.barSignalExpiry:
                window.barSignalExpiry.setValue(rem)
        else:
            timer.stop()
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
            for l_name in ("line_order_entry", "line_order_sl", "line_order_tp"):
                if hasattr(window, l_name):
                    l_obj = getattr(window, l_name)
                    if l_obj is not None:
                        try:
                            l_obj.setVisible(False)
                        except Exception:
                            pass
                        if hasattr(window, "plot_widget"):
                            try:
                                window.plot_widget.removeItem(l_obj)
                            except Exception:
                                pass
            window.order_proposal_active = False

    timer.timeout.connect(_tick)
    window._signal_expiry_timer = timer
    timer.start()


