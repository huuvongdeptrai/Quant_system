from backend.infrastructure.security.crypto_vault import encrypt_secret, decrypt_secret

from PySide6.QtGui import QIcon, QPixmap

from PySide6.QtCore import QSize

import os, json

from backend.infrastructure.brokers.mt5_safe import mt5

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QApplication,
)

from backend.core.event_bus import event_bus

from loguru import logger


class LoginDialog(QDialog):

    def __init__(self, window):

        super().__init__(window)

        self.window = window

        self.setWindowTitle("METATRADER 5 ACCOUNT LOGIN")

        self.setFixedSize(350, 300)

        # Áp dụng UI/UX Standards: Bỏ viền QLineEdit nếu không cần thiết, dùng padding và background tĩnh

        self.setStyleSheet("""

            QDialog { background-color: #0D1117; color: white; }

            QLabel { color: white; font-weight: bold; }

            QLineEdit { background: #21262D; color: white; border: none; padding: 8px; border-radius: 4px; }

            QLineEdit:focus { border: 1px solid #58A6FF; }

            QPushButton { padding: 8px; font-weight: bold; border-radius: 4px; }

        """)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Server Name (e.g. Exness-MT5-Real)"))

        self.inp_server = QLineEdit()

        layout.addWidget(self.inp_server)

        layout.addWidget(QLabel("Login ID (Account Number)"))

        self.inp_account = QLineEdit()

        layout.addWidget(self.inp_account)

        layout.addWidget(QLabel("Password"))

        self.inp_password = QLineEdit()

        self.inp_password.setEchoMode(QLineEdit.Password)

        layout.addWidget(self.inp_password)

        layout.addSpacing(10)

        self.lbl_msg = QLabel("")

        self.lbl_msg.setStyleSheet("color: #F23645;")

        layout.addWidget(self.lbl_msg)

        # Sử dụng khoảng trắng thay vì viền để tạo Grouping

        layout.addSpacing(20)

        btn_layout = QHBoxLayout()

        self.btn_login = QPushButton("LOGIN")

        self.btn_login.setStyleSheet(
            "background-color: #238636; color: white; border: none; font-size: 13px;"
        )

        self.btn_logout = QPushButton("LOGOUT")

        self.btn_logout.setStyleSheet(
            "background-color: transparent; border: none; color: #F23645; text-decoration: underline;"
        )

        btn_layout.addWidget(self.btn_login)

        btn_layout.addWidget(self.btn_logout)

        layout.addLayout(btn_layout)

        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        env_path = os.path.join(root_dir, "config", "ai_config.json")

        if os.path.exists(env_path):

            try:

                with open(env_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)

                if "MT5_SERVER" in cfg:
                    self.inp_server.setText(cfg["MT5_SERVER"])

                if "MT5_ACCOUNT" in cfg:
                    self.inp_account.setText(str(cfg["MT5_ACCOUNT"]))

                if "MT5_PASSWORD" in cfg:
                    self.inp_password.setText(decrypt_secret(cfg["MT5_PASSWORD"]))

            except Exception as e:

                logger.error(f"Failed to read config: {e}")

        self.btn_login.clicked.connect(self.do_login)

        self.btn_logout.clicked.connect(self.do_logout)

    def do_login(self):

        server = self.inp_server.text().strip()

        acc_str = self.inp_account.text().strip()

        pwd = self.inp_password.text().strip()

        if not server or not acc_str or not pwd:

            self.lbl_msg.setText("MISSING CREDENTIALS")

            return

        try:
            acc = int(acc_str)

        except Exception as e:

            logger.warning(f"Account ID conversion error: {e}")

            self.lbl_msg.setText("ACCOUNT ID MUST BE NUMERIC")

            return

        self.lbl_msg.setText("CONNECTING...")

        self.lbl_msg.setStyleSheet("color: #F2C94C;")

        QApplication.processEvents()

        connected = mt5.initialize(login=acc, password=pwd, server=server)

        if not connected:

            connected = mt5.initialize()

        if not connected:

            err = mt5.last_error()

            logger.error(f"MT5 initialization error: {err}")

            self.lbl_msg.setText(f"MT5 INIT FAILED ({err[0]}, {err[1]})")

            self.lbl_msg.setStyleSheet("color: #F23645;")

            return

        if mt5.login(acc, password=pwd, server=server):

            if hasattr(self.window, "labelStatus"):

                self.window.labelStatus.setText(f"● CONNECTED: {acc}")

                self.window.labelStatus.setStyleSheet(
                    "color: #10B981; font-weight: bold; font-size: 11px;"
                )

            # Cập nhật Corner Label bên run_pro (nếu truy cập được)

            event_bus.log_event.emit(
                "", "INFO", f"Broker connected: {server} | Account: {acc}", "#3FB950"
            )

            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            env_path = os.path.join(root_dir, "config", "ai_config.json")

            cfg = {}

            if os.path.exists(env_path):

                try:

                    with open(env_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)

                except Exception as e:

                    logger.error(f"Failed to read config: {e}")

            cfg["MT5_SERVER"] = server

            cfg["MT5_ACCOUNT"] = acc

            cfg["MT5_PASSWORD"] = encrypt_secret(pwd)

            with open(env_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4)

            self.accept()

        else:

            self.lbl_msg.setText("INVALID PASSWORD OR SERVER")

            self.lbl_msg.setStyleSheet("color: #F23645;")

    def do_logout(self):

        mt5.shutdown()

        if hasattr(self.window, "labelStatus"):

            self.window.labelStatus.setText("● NOT CONNECTED")

            self.window.labelStatus.setStyleSheet(
                "color: #8B949E; font-weight: bold; font-size: 11px;"
            )

        if hasattr(self.window, "valBalance"):

            self.window.valBalance.setText("$ 0.00")

            self.window.valEquity.setText("$ 0.00")

        event_bus.log_event.emit("", "WARNING", "MT5 connection disconnected", "#F2C94C")

        self.reject()


class AccountManager:

    def __init__(self, window):

        self.window = window

        if hasattr(self.window, "btnOpenLogin"):

            self.window.btnOpenLogin.clicked.connect(self.open_login_modal)

            self.window.btnOpenLogin.setText("")

            assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
            if not os.path.exists(assets_dir):
                assets_dir = os.path.join(os.path.dirname(__file__), "assets")
            icon_path = os.path.join(assets_dir, "gear_icon.svg")

            if os.path.exists(icon_path):
                try:
                    with open(icon_path, "rb") as f:
                        data = f.read()
                    pix = QPixmap()
                    pix.loadFromData(data)
                    self.window.btnOpenLogin.setIcon(QIcon(pix))
                except Exception:
                    self.window.btnOpenLogin.setIcon(QIcon(icon_path))

            self.window.btnOpenLogin.setIconSize(QSize(16, 16))

            self.window.btnOpenLogin.setProperty("class", "btn_sidebar_gear")

            self.window.btnOpenLogin.setToolTip("MT5 Account Login / Switch")

    def open_login_modal(self):

        dlg = LoginDialog(self.window)

        if dlg.exec():

            # Broadcast sự kiện kết nối thành công để kích hoạt load Watchlist, Update status

            event_bus.log_event.emit("", "INFO", "Broker connection ready", "#3FB950")

# Backward compatibility alias
AccountController = AccountManager
