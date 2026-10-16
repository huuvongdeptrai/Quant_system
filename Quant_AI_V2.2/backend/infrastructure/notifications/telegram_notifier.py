# -*- coding: utf-8 -*-
import os
import sys
import json
import time
import hashlib
import threading
from typing import Dict
from datetime import datetime
import requests
from loguru import logger


class TelegramNotifier:
    def __init__(self):
        self.bot_token = ""
        self.chat_id = ""
        self.alert_fills = True
        self.alert_sl_tp = True
        self.alert_risk_halt = True
        self._alert_history: Dict[str, float] = {}
        self._recent_hashes: Dict[str, float] = {}
        self._is_listening = False
        self._load_config()

    def _load_config(self):
        root_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
        candidate_paths = [
            os.path.join(root_dir, "config", "ai_config.json"),
            os.path.join(root_dir, "config", "settings.json"),
            os.path.join(os.getcwd(), "config", "ai_config.json"),
            os.path.join(os.getcwd(), "config", "settings.json"),
        ]
        for env_path in candidate_paths:
            if os.path.exists(env_path):
                try:
                    with open(env_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                        token = cfg.get("TELEGRAM_BOT_TOKEN") or cfg.get("telegram_bot_token")
                        chat_id = cfg.get("TELEGRAM_CHAT_ID") or cfg.get("telegram_chat_id")
                        if token and not self.bot_token:
                            self.bot_token = str(token).strip()
                        if chat_id and not self.chat_id:
                            self.chat_id = str(chat_id).strip()
                        if "alert_fills" in cfg:
                            self.alert_fills = bool(cfg["alert_fills"])
                        if "alert_sl_tp" in cfg:
                            self.alert_sl_tp = bool(cfg["alert_sl_tp"])
                        if "alert_risk_halt" in cfg:
                            self.alert_risk_halt = bool(cfg["alert_risk_halt"])
                except Exception as e:
                    logger.error(f"Lỗi đọc config Telegram từ {env_path}: {e}")

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def send_message(self, text: str, category: str = "general"):
        if not self.is_configured():
            return

        # 1. Lọc danh mục cảnh báo dựa theo cài đặt người dùng trong Options
        cat = str(category).lower()
        if cat in ["fill", "order", "entry"] and not getattr(self, "alert_fills", True):
            return
        if cat in ["sl_tp", "trailing", "breakeven", "exit"] and not getattr(self, "alert_sl_tp", True):
            return
        if cat in ["risk_halt", "circuit_breaker", "halt"] and not getattr(self, "alert_risk_halt", True):
            return

        now_ts = time.time()
        today_str = datetime.now().strftime("%Y-%m-%d")

        # 2. Khống chế nghiêm ngặt tần suất thông báo rủi ro (Circuit Breaker / Daily Loss)
        # Chỉ gửi DUY NHẤT 1 LẦN trong ngày cho mỗi phân loại rủi ro để bảo vệ người dùng không bị spam
        if cat in ["risk_halt", "circuit_breaker", "halt"]:
            risk_subtype = "general_halt"
            text_lower = text.lower()
            if "daily loss" in text_lower:
                risk_subtype = "daily_loss"
            elif "drawdown" in text_lower:
                risk_subtype = "drawdown"
            elif "streak" in text_lower:
                risk_subtype = "losing_streak"

            dedup_key = f"{cat}_{risk_subtype}_{today_str}"
            if dedup_key in self._alert_history:
                logger.info(
                    f"[TelegramNotifier] Chặn gửi lặp thông báo rủi ro '{risk_subtype}' cho ngày {today_str}. Chỉ gửi 1 lần duy nhất!"
                )
                return
            self._alert_history[dedup_key] = now_ts

        # 3. Chống spam gửi liên tục các tin nhắn nội dung trùng khớp trong vòng 60 giây
        msg_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
        if msg_hash in self._recent_hashes:
            if now_ts - self._recent_hashes[msg_hash] < 60.0:
                logger.debug("[TelegramNotifier] Chặn tin nhắn trùng lặp trong vòng 60s.")
                return
        self._recent_hashes[msg_hash] = now_ts

        # 4. Chạy ngầm bằng thread để không block BotWorker
        threading.Thread(target=self._send_task, args=(text,), daemon=True).start()

    def _send_task(self, text: str):
        # Khi đang chạy kiểm thử pytest hoặc môi trường test, không dispatch HTTP request thật ra ngoài
        if "pytest" in sys.modules or os.environ.get("QUANT_TESTING") == "1":
            logger.debug(f"[Telegram Mock] Suppressed network dispatch in test environment: {text[:60]}")
            return

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}
            res = requests.post(url, json=payload, timeout=5)
            if res.status_code != 200:
                logger.warning(f"Failed to send Telegram message: {res.text}")
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")

    def start_listening(self, event_bus):
        if not self.is_configured():
            return
        self._is_listening = True

        threading.Thread(
            target=self._poll_updates, args=(event_bus,), daemon=True
        ).start()

    def _poll_updates(self, event_bus):
        offset = None
        while self._is_listening:
            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
                params = {"timeout": 10, "allowed_updates": ["message"]}
                if offset:
                    params["offset"] = offset

                res = requests.get(url, params=params, timeout=15)
                if res.status_code == 200:
                    data = res.json()
                    if data.get("ok"):
                        for item in data.get("result", []):
                            update_id = item["update_id"]
                            offset = update_id + 1

                            msg = item.get("message", {})
                            text = msg.get("text", "").lower().strip()
                            chat_id = str(msg.get("chat", {}).get("id", ""))

                            if chat_id == self.chat_id:
                                if text in ["turn on", "start", "/start", "on"]:
                                    event_bus.remote_command.emit("START")
                                    self.send_message(
                                        "✅ <b>[Remote Command]</b> Đã nhận lệnh: Khởi động Bot thành công!"
                                    )
                                elif text in ["turn off", "stop", "/stop", "off"]:
                                    event_bus.remote_command.emit("STOP")
                                    self.send_message(
                                        "🛑 <b>[Remote Command]</b> Đã nhận lệnh: Tạm dừng Bot an toàn!"
                                    )
            except Exception as e:
                time.sleep(2)


# Singleton instance
telegram_notifier = TelegramNotifier()
