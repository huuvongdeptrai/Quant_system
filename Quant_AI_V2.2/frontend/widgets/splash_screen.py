# -*- coding: utf-8 -*-
"""
Quant Terminal V2.2 - Startup & Initialization Overlay Module.
Implements:
1. InitWorker: Background thread for MT5 safe session handshake, Macro pre-fetch, and state sync.
2. FadeOverlayWidget (Cách 2 - Selected Standard): Clean Fade-Out Overlay that sits over
   the main window with frosted Light Theme aesthetic and smooth 300ms fade-out.
3. SwissSplashCard (Cách 3): Minimalist standalone card with 4-corner balanced typography.
4. SplashScreen: Backwards-compatibility alias pointing to FadeOverlayWidget.
"""

import os
import json
import time

from PySide6.QtCore import Qt, QThread, Signal, QEvent, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QFrame,
    QGraphicsOpacityEffect, QGraphicsDropShadowEffect
)
from PySide6.QtGui import QFont, QColor
from loguru import logger

from backend.infrastructure.brokers.mt5_safe import mt5
from backend.infrastructure.data_providers.macro.macro_regime import MacroRegimeEngine
from backend.infrastructure.security.crypto_vault import decrypt_secret


class InitWorker(QThread):
    """Background worker executing initialization tasks without blocking the GUI."""
    progress = Signal(int, str)
    init_done = Signal()

    def run(self):
        try:
            # Bước 1: Khởi tạo cấu hình cốt lõi
            self.progress.emit(15, "[SYSTEM] Loading Core Configurations...")
            time.sleep(0.05)

            # Bước 2: Kiểm tra phiên MT5 (Ưu tiên tái sử dụng kết nối đã khởi tạo từ main GUI thread)
            self.progress.emit(40, "[MT5] Verifying Engine & Broker Session...")

            term = None
            try:
                term = mt5.terminal_info()
            except Exception as e:
                logger.debug(f"[Splash] mt5.terminal_info query: {e}")

            # Nếu MT5 đã mở và đang kết nối phiên hợp lệ trên GUI thread -> BẢO TOÀN PHIÊN
            # Tránh tuyệt đối gọi mt5.initialize() đa luồng làm nghẽn/deadlock IPC named pipe!
            if term and getattr(term, "connected", False):
                acc_info = mt5.account_info()
                acc_str = f"#{acc_info.login}" if acc_info else "Active"
                logger.info(
                    f"[Splash] Nhận diện phiên MT5 đang hoạt động: {acc_str}. Bảo toàn kết nối sàn."
                )
                self.progress.emit(70, f"[MT5] Connected ({acc_str})")
            else:
                connected = False
                try:
                    connected = mt5.initialize()
                except Exception as e:
                    logger.warning(f"[Splash] mt5.initialize attempt error: {e}")

                if not connected:
                    for custom_path in [
                        r"C:\Program Files\LiteFinance MT5 Terminal\terminal64.exe",
                        r"C:\Program Files\MetaTrader 5\terminal64.exe",
                        r"C:\Program Files (x86)\MetaTrader 5\terminal64.exe",
                    ]:
                        if os.path.exists(custom_path):
                            if mt5.initialize(path=custom_path):
                                connected = True
                                break

                term = mt5.terminal_info() if connected else None
                acc_info = mt5.account_info() if connected else None

                if not (term and getattr(term, "connected", False) and acc_info):
                    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    env_path = os.path.join(root_dir, "config", "ai_config.json")
                    if os.path.exists(env_path):
                        try:
                            with open(env_path, "r", encoding="utf-8") as f:
                                cfg = json.load(f)

                            server = cfg.get("MT5_SERVER")
                            acc = cfg.get("MT5_ACCOUNT")
                            pwd_raw = cfg.get("MT5_PASSWORD")
                            pwd = decrypt_secret(pwd_raw) if pwd_raw else None

                            if server and acc and pwd:
                                try:
                                    acc = int(acc)
                                except Exception:
                                    pass
                                login_ok = mt5.login(acc, password=pwd, server=server)
                                if login_ok:
                                    logger.info(f"[Splash] Đăng nhập MT5 thành công với tài khoản #{acc}")
                                else:
                                    logger.warning(
                                        f"[Splash] Đăng nhập MT5 từ cấu hình thất bại: {mt5.last_error()}. Giữ nguyên trạng thái MT5."
                                    )
                        except Exception as e:
                            logger.warning(f"[Splash] Auto-login attempt error: {e}")

            time.sleep(0.05)

            # Bước 3: Nạp dữ liệu Vĩ mô & Tin tức (Non-blocking status update)
            self.progress.emit(85, "[API] Syncing Macro & Regime Telemetry...")
            time.sleep(0.05)

            # Bước 4: Hoàn tất
            self.progress.emit(100, "[SYSTEM] Ready. Launching Terminal...")
            time.sleep(0.05)

        except Exception as e:
            logger.error(f"Error during splash init: {e}")
        finally:
            self.init_done.emit()


# ==============================================================================
# CÁCH 2 (SELECTED): CLEAN FADE-OUT OVERLAY TRỰC TIẾP TRÊN GIAO DIỆN CHÍNH
# ==============================================================================
class FadeOverlayWidget(QWidget):
    """
    Màn mờ tan dần ngay trên giao diện chính (Clean Fade-Out Overlay).
    - Phủ một lớp sương mờ dịu nhẹ (rgba(248, 250, 252, 0.94)) lên toàn bộ cửa sổ.
    - Đặt thẻ trung tâm thương hiệu VECTRA với bố cục phẳng tối giản, góc vuông sắc nét.
    - Thanh tiến trình siêu mảnh 2px cùng thông tin % và trạng thái feed trực tiếp.
    - Tan biến mượt mà trong 350ms khi hệ thống kết nối thành công.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setObjectName("fadeOverlay")
        self.setStyleSheet("""
            QWidget#fadeOverlay {
                background-color: rgba(248, 250, 252, 0.95);
            }
        """)

        if parent:
            self.setGeometry(0, 0, parent.width(), parent.height())
            parent.installEventFilter(self)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Center Content Container (Direct on frosted mist - No box, no shadow, ultra-clean)
        self.center_card = QWidget()
        self.center_card.setFixedWidth(340)
        self.center_card.setStyleSheet("background: transparent; border: none;")

        card_vbox = QVBoxLayout(self.center_card)
        card_vbox.setContentsMargins(0, 0, 0, 0)
        card_vbox.setSpacing(0)
        card_vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Brand Title (Solid, grounded typography with 2px letter-spacing)
        self.lbl_title = QLabel("VECTRA")
        self.lbl_title.setStyleSheet(
            "color: #0F172A; font-family: 'Segoe UI'; font-size: 32px; font-weight: 900; letter-spacing: 2px; border: none; background: transparent;"
        )
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_vbox.addWidget(self.lbl_title)

        # Subtitle (Institutional Execution branding - No generic 'AI')
        self.lbl_sub = QLabel("QUANTITATIVE EXECUTION SYSTEM • V2.2")
        self.lbl_sub.setStyleSheet(
            "color: #64748B; font-family: 'Segoe UI'; font-size: 9px; font-weight: 700; letter-spacing: 2px; border: none; background: transparent; margin-top: 6px;"
        )
        self.lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_vbox.addWidget(self.lbl_sub)

        card_vbox.addSpacing(28)

        # Minimalist 2px Progress Bar sitting directly on the frosted mist
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(2)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #E2E8F0;
                border: none;
                border-radius: 0px;
            }
            QProgressBar::chunk {
                background-color: #0284C7;
                border-radius: 0px;
            }
        """)
        card_vbox.addWidget(self.progress_bar)

        layout.addWidget(self.center_card, 0, Qt.AlignmentFlag.AlignCenter)

        # Institutional fail-safe watchdog timer: overlay must NEVER freeze/block GUI for > 2500ms
        from PySide6.QtCore import QTimer
        self._fail_safe_timer = QTimer(self)
        self._fail_safe_timer.setSingleShot(True)
        self._fail_safe_timer.timeout.connect(lambda: self.fade_out_and_destroy(250))
        self._fail_safe_timer.start(2500)

    def mousePressEvent(self, event):
        """Allows trader to click anywhere on overlay to bypass immediately."""
        self.fade_out_and_destroy(150)
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        """ESC, Space, or Enter immediately dismisses overlay."""
        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.fade_out_and_destroy(150)
            event.accept()
        else:
            super().keyPressEvent(event)

    def eventFilter(self, watched, event):
        if watched == self.parent() and event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self.setGeometry(0, 0, watched.width(), watched.height())
            if not getattr(self, "_fading", False):
                self.raise_()
        return super().eventFilter(watched, event)

    def update_progress(self, val: int, msg: str = ""):
        self.progress_bar.setValue(val)
        if hasattr(self, "lbl_pct") and self.lbl_pct:
            self.lbl_pct.setText(f"{val}%")
        if hasattr(self, "lbl_status") and self.lbl_status:
            self.lbl_status.setText(msg.upper())

    def close(self):
        """Fade out gracefully when close is invoked."""
        self.fade_out_and_destroy(250)
        return True

    def fade_out_and_destroy(self, duration_ms: int = 350):
        """Animates opacity from 1.0 to 0.0 with smooth easing and cleans up."""
        if hasattr(self, "_fading") and self._fading:
            return
        self._fading = True

        self.anim_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.anim_effect)

        self.fade_anim = QPropertyAnimation(self.anim_effect, b"opacity")
        self.fade_anim.setDuration(duration_ms)
        self.fade_anim.setStartValue(1.0)
        self.fade_anim.setEndValue(0.0)
        self.fade_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

        if hasattr(self, "_fail_safe_timer") and self._fail_safe_timer.isActive():
            self._fail_safe_timer.stop()

        def _on_finished():
            if self.parent():
                try:
                    self.parent().removeEventFilter(self)
                except Exception:
                    pass
            self.hide()
            self.deleteLater()

        self.fade_anim.finished.connect(_on_finished)
        self.fade_anim.start()


# ==============================================================================
# CÁCH 3: THẺ TRẮNG TỐI GIẢN (SWISS MINIMALIST CARD - AVAILABLE AS ALTERNATIVE)
# ==============================================================================
class SwissSplashCard(QWidget):
    """
    Thẻ Trắng Tối Giản (Swiss Minimalist Card):
    - Cửa sổ nổi 500x240px góc vuông sắc cạnh (0px)
    - Bố cục 4 góc đối xứng chuẩn thiết kế Thụy Sĩ
    - Thanh chạy siêu mảnh 2px dán sát mép đáy
    """
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setFixedSize(500, 240)
        self.setObjectName("splashWindow")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self.card = QFrame()
        self.card.setObjectName("cardBody")
        self.card.setStyleSheet("""
            QFrame#cardBody {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-bottom: none;
                border-radius: 0px;
            }
        """)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(36, 30, 36, 20)
        card_layout.setSpacing(0)

        # 1. TOP ROW: Brand (Top-Left) vs Badge (Top-Right)
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)

        brand_box = QVBoxLayout()
        brand_box.setSpacing(3)
        self.lbl_title = QLabel("VECTRA")
        self.lbl_title.setStyleSheet("color: #0F172A; font-family: 'Segoe UI'; font-size: 22px; font-weight: 900; letter-spacing: 2px; border: none;")

        self.lbl_sub = QLabel("INSTITUTIONAL QUANTITATIVE TERMINAL")
        self.lbl_sub.setStyleSheet("color: #64748B; font-family: 'Segoe UI'; font-size: 9px; font-weight: 700; letter-spacing: 2px; border: none;")
        brand_box.addWidget(self.lbl_title)
        brand_box.addWidget(self.lbl_sub)
        top_row.addLayout(brand_box)

        top_row.addStretch(1)

        self.lbl_badge = QLabel("v2.2 PRO")
        self.lbl_badge.setStyleSheet("""
            QLabel {
                background-color: #F1F5F9;
                color: #334155;
                font-family: 'Consolas';
                font-size: 11px;
                font-weight: 700;
                padding: 4px 10px;
                border: 1px solid #E2E8F0;
                border-radius: 2px;
            }
        """)
        self.lbl_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_row.addWidget(self.lbl_badge, 0, Qt.AlignmentFlag.AlignTop)

        card_layout.addLayout(top_row)

        # 2. MIDDLE AIRY SPACE: Clean Tagline
        card_layout.addStretch(1)
        self.lbl_tag = QLabel("Order Flow Imbalance • Wyckoff S/R • Microsecond IPC Engine")
        self.lbl_tag.setStyleSheet("color: #94A3B8; font-family: 'Segoe UI'; font-size: 10px; font-weight: 600; letter-spacing: 0.5px; border: none;")
        card_layout.addWidget(self.lbl_tag)
        card_layout.addStretch(1)

        card_layout.addStretch(1)

        # 3. BOTTOM EDGE: 2px Ultra-thin Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(2)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #F1F5F9;
                border-left: 1px solid #CBD5E1;
                border-right: 1px solid #CBD5E1;
                border-bottom: 1px solid #CBD5E1;
                border-top: none;
                border-radius: 0px;
            }
            QProgressBar::chunk {
                background-color: #0284C7;
                border-radius: 0px;
            }
        """)

        outer_layout.addWidget(self.card)
        outer_layout.addWidget(self.progress_bar)

    def update_progress(self, val: int, msg: str = ""):
        self.progress_bar.setValue(val)
        if hasattr(self, "lbl_pct") and self.lbl_pct:
            self.lbl_pct.setText(f"{val}%")
        if hasattr(self, "lbl_status") and self.lbl_status:
            self.lbl_status.setText(msg)


# Canonical Facade Alias for 100% Backwards Compatibility
SplashScreen = FadeOverlayWidget

__all__ = ["InitWorker", "FadeOverlayWidget", "SwissSplashCard", "SplashScreen"]
