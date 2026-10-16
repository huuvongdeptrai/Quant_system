import os, json, threading
import requests
from loguru import logger


class TelegramNotifier:
    def __init__(self):
        self.bot_token = ""
        self.chat_id = ""
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
                except Exception as e:
                    logger.error(f"Lỗi đọc config Telegram từ {env_path}: {e}")

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def send_message(self, text: str):
        if not self.is_configured():
            return

        # Chạy ngầm bằng thread để không block BotWorker
        threading.Thread(target=self._send_task, args=(text,), daemon=True).start()

    def _send_task(self, text: str):
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
        import time

        threading.Thread(
            target=self._poll_updates, args=(event_bus,), daemon=True
        ).start()

    def _poll_updates(self, event_bus):
        import time

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
