from backend.infrastructure.brokers.mt5_safe import mt5
"""
Trading Plan, Order Proposal Cards, and Playbook Theme Engine
"""

import os
import time
from datetime import datetime
from PySide6 import QtCore, QtGui
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QFrame, QLabel, QHBoxLayout, QVBoxLayout, QPushButton,
    QWidget, QProgressBar, QSizePolicy
)

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

        # Gỡ bỏ toàn bộ đường lệnh ảo khỏi biểu đồ
        for line_name in ("line_order_entry", "line_order_sl", "line_order_tp"):
            if hasattr(window, line_name):
                l_obj = getattr(window, line_name)
                if l_obj is not None and hasattr(window, "plot_widget"):
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
            window.lblChk1Val.setText(chk1 or "Monitoring")
        if hasattr(window, "lblChk2Val") and window.lblChk2Val:
            window.lblChk2Val.setText(chk2 or "Awaiting Asian Sweep")
        if hasattr(window, "lblChk3Val") and window.lblChk3Val:
            window.lblChk3Val.setText(chk3 or "Awaiting Confluence")

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
            window.btnDiscardOrder.setEnabled(False)

        if hasattr(window, "_signal_expiry_timer") and window._signal_expiry_timer is not None:
            try:
                window._signal_expiry_timer.stop()
            except Exception:
                pass

        if hasattr(window, "cardSetupModel"):
            apply_playbook_cards_theme(window, is_dark)
        return

    # 2. TRƯỜNG HỢP: CÓ TÍN HIỆU THỰC TẾ (BUY / SELL)
    window.order_proposal_active = True
    window.active_signal_data = {
        "sym": clean_sym,
        "has_signal": True,
        "signal_type": signal_type,
        "entry": entry,
        "sl": sl,
        "tp": tp,
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

    # Cập nhật đường ngang trên biểu đồ nến
    order_action_name = "BUY LIMIT" if signal_type == "BUY" else "SELL LIMIT"
    if hasattr(window, "line_order_entry") and window.line_order_entry:
        window.line_order_entry.setValue(entry)
        window.line_order_entry.label.setFormat(f"{order_action_name}: {entry:.{digits}f} ({calc_lot:.2f} Lot)")
        if hasattr(window, "plot_widget"):
            try:
                window.plot_widget.addItem(window.line_order_entry, ignoreBounds=True)
            except Exception:
                pass

    if hasattr(window, "line_order_sl") and window.line_order_sl:
        window.line_order_sl.setValue(sl)
        window.line_order_sl.label.setFormat(f"STOP LOSS: {sl_p:.{digits}f} (-${risk_dlr:.2f} | -{risk_pct:.1f}%)")
        if hasattr(window, "plot_widget"):
            try:
                window.plot_widget.addItem(window.line_order_sl, ignoreBounds=True)
            except Exception:
                pass

    if hasattr(window, "line_order_tp") and window.line_order_tp:
        window.line_order_tp.setValue(tp)
        window.line_order_tp.label.setFormat(f"TAKE PROFIT: {tp:.{digits}f} (+${reward_dlr:.2f} | +{rr_ratio:.1f}R)")
        if hasattr(window, "plot_widget"):
            try:
                window.plot_widget.addItem(window.line_order_tp, ignoreBounds=True)
            except Exception:
                pass

    # Card 1: Mô hình thiết lập (Active)
    if hasattr(window, "lblModelSubtitle") and window.lblModelSubtitle:
        window.lblModelSubtitle.setText("SETUP MODEL")
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
        window.lblOrderBudgetTitle.setText("ORDER & RISK BUDGET")
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
        window.lblSLVal.setText(f"{sl:.{digits}f}  (-${risk_dlr:.2f} | -{risk_pct:.1f}%)")
    if hasattr(window, "lblTPVal") and window.lblTPVal:
        window.lblTPVal.setText(f"{tp:.{digits}f}  (+${reward_dlr:.2f} | +{rr_ratio:.1f}R)")
    if hasattr(window, "lblSizeVal") and window.lblSizeVal:
        window.lblSizeVal.setText(f"{calc_lot:.2f} LOTS (${risk_dlr:.2f})")

    # Card 3: Cổng phê duyệt lệnh (Active)
    if hasattr(window, "lblGateExpiryTitle") and window.lblGateExpiryTitle:
        window.lblGateExpiryTitle.setText("EXPIRATION")
    if hasattr(window, "btnApproveOrder") and window.btnApproveOrder:
        window.btnApproveOrder.setText("APPROVE ORDER")
        window.btnApproveOrder.setEnabled(True)
        window.btnApproveOrder.setCursor(Qt.PointingHandCursor)
    if hasattr(window, "btnModifyOrder") and window.btnModifyOrder:
        window.btnModifyOrder.setEnabled(True)
    if hasattr(window, "btnDiscardOrder") and window.btnDiscardOrder:
        window.btnDiscardOrder.setEnabled(True)

    if hasattr(window, "cardSetupModel"):
        apply_playbook_cards_theme(window, is_dark)

    start_signal_expiry_countdown(window)


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

    badge_style = f"background-color: {badge_bg}; color: {badge_text}; border: 1px solid {badge_border}; font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 1px 5px;"
    if hasattr(window, "lblModelGrade") and window.lblModelGrade:
        window.lblModelGrade.setStyleSheet(badge_style)
    if hasattr(window, "lblOrderTypeBadge") and window.lblOrderTypeBadge:
        window.lblOrderTypeBadge.setStyleSheet(badge_style)

    key_style = f"color: {sub_color}; font-family: Consolas, monospace; font-size: 9.5px; border: none; background: transparent;"
    for k_attr in dir(window):
        if k_attr.startswith("lblKey_"):
            w = getattr(window, k_attr)
            if w:
                w.setStyleSheet(key_style)

    # Checklist values and vector icons
    if hasattr(window, "lblChk1Val") and window.lblChk1Val:
        window.lblChk1Val.setStyleSheet(f"color: {bull_color}; font-family: Consolas, monospace; font-size: 9.5px; font-weight: bold; border: none; background: transparent;")
    if hasattr(window, "lblChk2Val") and window.lblChk2Val:
        window.lblChk2Val.setStyleSheet(f"color: {text_sec}; font-family: Consolas, monospace; font-size: 9.5px; font-weight: 600; border: none; background: transparent;")
    if hasattr(window, "lblChk3Val") and window.lblChk3Val:
        window.lblChk3Val.setStyleSheet(f"color: {text_sec}; font-family: Consolas, monospace; font-size: 9.5px; font-weight: 600; border: none; background: transparent;")

    svg_file = "check_vector_emerald.svg" if is_dark else "check_vector_light.svg"
    icon_path = os.path.join(assets_dir, svg_file)
    if os.path.exists(icon_path):
        chk_pixmap = QIcon(icon_path).pixmap(12, 12)
        for ic_name in ["lblChk1Icon", "lblChk2Icon", "lblChk3Icon"]:
            if hasattr(window, ic_name) and getattr(window, ic_name):
                getattr(window, ic_name).setPixmap(chk_pixmap)

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


def setup_trading_plan_cards(window, is_dark=False):
    """Construct streamlined institutional 3-card Trading Plan inside frameAIArea."""
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

    card_model_layout.addLayout(_make_checklist_row("Trend Structure", "Monitoring", "lblChk1Val", "lblChk1Icon"))
    card_model_layout.addLayout(_make_checklist_row("Liquidity Sweep", "Awaiting Asian Sweep", "lblChk2Val", "lblChk2Icon"))
    card_model_layout.addLayout(_make_checklist_row("Order Blocks & FVG", "Awaiting Confluence", "lblChk3Val", "lblChk3Icon"))

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

    from PySide6.QtWidgets import QProgressBar
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

    # Full-bleed Section Dividers
    sep_divider1 = QFrame()
    sep_divider1.setFrameShape(QFrame.HLine)
    sep_divider1.setObjectName("sepDivider1")
    sep_divider1.setFixedHeight(1)

    sep_divider2 = QFrame()
    sep_divider2.setFrameShape(QFrame.HLine)
    sep_divider2.setObjectName("sepDivider2")
    sep_divider2.setFixedHeight(1)

    # Expose widgets on window
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

    # Add flat sections with clean 1px full-bleed dividers
    window.layoutAIArea.addWidget(card_model)
    window.layoutAIArea.addWidget(sep_divider1)
    window.layoutAIArea.addWidget(card_order)
    window.layoutAIArea.addWidget(sep_divider2)
    window.layoutAIArea.addWidget(card_gate)
    window.layoutAIArea.addStretch()

    apply_playbook_cards_theme(window, is_dark)


def start_signal_expiry_countdown(window, duration_sec=None):
    """Start dynamic real-time 1-second countdown timer for Trading Plan signal expiration."""
    if duration_sec is None:
        try:
            cfg_p = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "settings.json")
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
    timer = QTimer(window)
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
                    try:
                        window.plot_widget.removeItem(getattr(window, l_name))
                    except Exception:
                        pass
            window.order_proposal_active = False

    timer.timeout.connect(_tick)
    window._signal_expiry_timer = timer
    timer.start()


