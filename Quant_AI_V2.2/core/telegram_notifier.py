import os, json, threading
import requests
import logging

logger = logging.getLogger("TelegramNotifier")

class TelegramNotifier:
    def __init__(self):
        self.bot_token = ""
        self.chat_id = ""
        self._load_config()

    def _load_config(self):
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "ai_config.json")
        if os.path.exists(env_path):
            try:
                with open(env_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    self.bot_token = cfg.get("TELEGRAM_BOT_TOKEN", "").strip()
                    self.chat_id = cfg.get("TELEGRAM_CHAT_ID", "").strip()
            except Exception as e:
                logger.error(f"Lỗi đọc config Telegram: {e}")

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
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML"
            }
            res = requests.post(url, json=payload, timeout=5)
            if res.status_code != 200:
                logger.warning(f"Failed to send Telegram message: {res.text}")
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")

# Singleton instance
telegram_notifier = TelegramNotifier()
