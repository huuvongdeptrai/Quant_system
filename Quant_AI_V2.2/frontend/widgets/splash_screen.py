import os

import json

import time

from PySide6.QtCore import Qt, QThread, Signal

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar

from PySide6.QtGui import QFont, QColor

from loguru import logger


from backend.infrastructure.brokers.mt5_safe import mt5

from backend.infrastructure.data_providers.macro.macro_regime import MacroRegimeEngine

from backend.infrastructure.security.crypto_vault import decrypt_secret


class InitWorker(QThread):

    progress = Signal(int, str)

    init_done = Signal()

    def run(self):

        try:

            # Bước 1: Khởi tạo cơ bản

            self.progress.emit(10, "[SYSTEM] Loading Core Configurations...")

            time.sleep(0.3)

            # Bước 2: Thử Auto-Login vào MT5 nếu có config

            self.progress.emit(30, "[MT5] Initializing Engine & Connecting...")

            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            env_path = os.path.join(root_dir, "config", "ai_config.json")

            # 1. Kết nối với tiến trình MT5 đang mở
            connected = mt5.initialize()
            if not connected:
                # Tìm kiếm các đường dẫn cài đặt MT5 khả dụng (ví dụ: LiteFinance, MetaTrader 5)
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

            # 2. Nếu MT5 đã mở và đang kết nối phiên hợp lệ -> BẢO TOÀN PHIÊN (KHÔNG gọi mt5.login gây đứt kết nối)
            if term and getattr(term, "connected", False) and acc_info:
                logger.info(
                    f"[Splash] Nhận diện phiên MT5 đang hoạt động: Tài khoản #{acc_info.login} ({acc_info.server}). Bảo toàn kết nối sàn."
                )
            else:
                # Chỉ khi MT5 chưa kết nối hoặc chưa đăng nhập mới dùng thông tin từ ai_config.json
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

            time.sleep(0.5)

            # Bước 3: Nạp dữ liệu Vĩ mô & Tin tức

            self.progress.emit(60, "[API] Fetching Macro & Economic Calendar...")

            engine = MacroRegimeEngine()

            # Gọi nhẹ hàm fetch để load cache TradingView & YahooFinance

            try:

                engine.generate_macro_report()

            except Exception as e:

                logger.warning(f"Splash pre-fetch Macro failed: {e}")

            time.sleep(0.5)

            # Bước 4: Hoàn tất

            self.progress.emit(100, "[SYSTEM] Ready. Launching Terminal...")

            time.sleep(0.2)

        except Exception as e:

            logger.error(f"Error during splash init: {e}")

        finally:

            self.init_done.emit()


class SplashScreen(QWidget):

    def __init__(self):

        super().__init__()

        # 1. Khung Frameless

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setFixedSize(500, 300)

        # 2. Bố cục chính (Background Xám đen chuyên nghiệp)

        self.layout = QVBoxLayout(self)

        self.layout.setContentsMargins(0, 0, 0, 0)

        self.layout.setSpacing(0)

        self.container = QWidget()

        self.container.setStyleSheet("""

            QWidget {

                background-color: #0D1117;

                border: 1px solid #30363D;

                border-radius: 8px;

            }

        """)

        self.container_layout = QVBoxLayout(self.container)

        self.container_layout.setContentsMargins(40, 50, 40, 30)

        # 3. Typography

        self.lbl_title = QLabel("QUANT AI")

        self.lbl_title.setStyleSheet(
            "color: #FFFFFF; font-family: 'Segoe UI'; font-size: 32px; font-weight: 800; border: none;"
        )

        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_subtitle = QLabel("PROFESSIONAL TERMINAL")

        self.lbl_subtitle.setStyleSheet(
            "color: #58A6FF; font-family: 'Segoe UI'; font-size: 14px; font-weight: 600; letter-spacing: 2px; border: none;"
        )

        self.lbl_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.container_layout.addStretch(1)

        self.container_layout.addWidget(self.lbl_title)

        self.container_layout.addWidget(self.lbl_subtitle)

        self.container_layout.addStretch(1)

        # 4. Status & Progress

        self.lbl_status = QLabel("Initializing...")

        self.lbl_status.setStyleSheet(
            "color: #8B949E; font-family: 'Consolas'; font-size: 11px; border: none;"
        )

        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.progress_bar = QProgressBar()

        self.progress_bar.setFixedHeight(2)  # Siêu mỏng

        self.progress_bar.setTextVisible(False)

        self.progress_bar.setStyleSheet("""

            QProgressBar {

                background-color: #161B22;

                border: none;

                border-radius: 1px;

            }

            QProgressBar::chunk {

                background-color: #58A6FF;

                border-radius: 1px;

            }

        """)

        self.container_layout.addWidget(self.lbl_status)

        self.container_layout.addSpacing(8)

        self.container_layout.addWidget(self.progress_bar)

        self.layout.addWidget(self.container)

    def update_progress(self, val, msg):

        self.progress_bar.setValue(val)

        self.lbl_status.setText(msg)
