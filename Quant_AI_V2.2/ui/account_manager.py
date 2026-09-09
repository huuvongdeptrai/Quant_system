import os, json
from infrastructure.brokers.mt5_safe import mt5
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QApplication
from core.event_bus import event_bus
from loguru import logger

class LoginDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle("KẾT NỐI BROKER MT5")
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
        layout.addWidget(QLabel("Tên Server (Ví dụ: Exness-MT5-Real)"))
        self.inp_server = QLineEdit()
        layout.addWidget(self.inp_server)
        
        layout.addWidget(QLabel("Số Tài khoản (Login ID)"))
        self.inp_account = QLineEdit()
        layout.addWidget(self.inp_account)
        
        layout.addWidget(QLabel("Mật khẩu (Password)"))
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
        self.btn_login = QPushButton("ĐĂNG NHẬP")
        self.btn_login.setStyleSheet("background-color: #238636; color: white; border: none; font-size: 13px;")
        self.btn_logout = QPushButton("ĐĂNG XUẤT")
        self.btn_logout.setStyleSheet("background-color: transparent; border: none; color: #F23645; text-decoration: underline;")
        btn_layout.addWidget(self.btn_login)
        btn_layout.addWidget(self.btn_logout)
        layout.addLayout(btn_layout)
        
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "ai_config.json")
        if os.path.exists(env_path):
            try:
                with open(env_path, 'r', encoding='utf-8') as f: cfg = json.load(f)
                if 'MT5_SERVER' in cfg: self.inp_server.setText(cfg['MT5_SERVER'])
                if 'MT5_ACCOUNT' in cfg: self.inp_account.setText(str(cfg['MT5_ACCOUNT']))
                if 'MT5_PASSWORD' in cfg: self.inp_password.setText(cfg['MT5_PASSWORD'])
            except Exception as e:
                logger.error(f"Lỗi đọc config: {e}")
            
        self.btn_login.clicked.connect(self.do_login)
        self.btn_logout.clicked.connect(self.do_logout)

    def do_login(self):
        server = self.inp_server.text().strip()
        acc_str = self.inp_account.text().strip()
        pwd = self.inp_password.text().strip()
        
        if not server or not acc_str or not pwd:
            self.lbl_msg.setText("THIẾU THÔNG TIN")
            return
        try: acc = int(acc_str)
        except Exception as e:
            logger.warning(f"Lỗi chuyển đổi tài khoản thành số: {e}")
            self.lbl_msg.setText("TÀI KHOẢN PHẢI LÀ SỐ")
            return
            
        self.lbl_msg.setText("ĐANG KẾT NỐI...")
        self.lbl_msg.setStyleSheet("color: #F2C94C;")
        QApplication.processEvents()
        
        if not mt5.initialize(login=acc, password=pwd, server=server):
            err = mt5.last_error()
            logger.error(f"Lỗi khởi tạo MT5: {err}")
            self.lbl_msg.setText(f"LỖI KHỞI TẠO MT5 ({err[0]}, {err[1]})")
            self.lbl_msg.setStyleSheet("color: #F23645;")
            return
            
        if mt5.login(acc, password=pwd, server=server):
            if hasattr(self.window, 'labelStatus'):
                self.window.labelStatus.setText(f"● CONNECTED: {acc}")
                self.window.labelStatus.setStyleSheet("color: #10B981; font-weight: bold; font-size: 11px;")
            
            # Cập nhật Corner Label bên run_pro (nếu truy cập được)
            event_bus.log_event.emit("", "INFO", f"Đã kết nối Broker: {server} | Tải khoản: {acc}", "#3FB950")
            
            env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "ai_config.json")
            cfg = {}
            if os.path.exists(env_path):
                try:
                    with open(env_path, 'r', encoding='utf-8') as f: cfg = json.load(f)
                except Exception as e:
                    logger.error(f"Lỗi đọc config: {e}")
            cfg['MT5_SERVER'] = server
            cfg['MT5_ACCOUNT'] = acc
            cfg['MT5_PASSWORD'] = pwd
            with open(env_path, 'w', encoding='utf-8') as f: json.dump(cfg, f, indent=4)
                
            self.accept()
        else:
            self.lbl_msg.setText("SAI MẬT KHẨU / SERVER")
            self.lbl_msg.setStyleSheet("color: #F23645;")

    def do_logout(self):
        mt5.shutdown()
        if hasattr(self.window, 'labelStatus'):
            self.window.labelStatus.setText("● NOT CONNECTED")
            self.window.labelStatus.setStyleSheet("color: #8B949E; font-weight: bold; font-size: 11px;")
        if hasattr(self.window, 'valBalance'):
            self.window.valBalance.setText("$ 0.00")
            self.window.valEquity.setText("$ 0.00")
        event_bus.log_event.emit("", "WARNING", "Đã ngắt kết nối MT5", "#F2C94C")
        self.reject()

class AccountManager:
    def __init__(self, window):
        self.window = window
        if hasattr(self.window, 'btnOpenLogin'):
            self.window.btnOpenLogin.clicked.connect(self.open_login_modal)
            self.window.btnOpenLogin.setText("+ Add")
            self.window.btnOpenLogin.setStyleSheet("QPushButton { background: transparent; color: #8B949E; text-decoration: underline; font-weight: bold; border: none; } QPushButton:hover { color: #C9D1D9; }")

    def open_login_modal(self):
        dlg = LoginDialog(self.window)
        if dlg.exec():
            # Broadcast sự kiện kết nối thành công để kích hoạt load Watchlist, Update status
            event_bus.log_event.emit("", "INFO", "Hệ thống Broker sẵn sàng", "#3FB950")