"""
Options Config Binder - Persistence and Serialization Service.
Responsible for two-way synchronization between in-memory Options tab widgets
and file-system JSON stores (settings.json, ai_config.json).
"""

import os
import json
from typing import Dict, Any, Tuple
from loguru import logger

from backend.infrastructure.notifications.telegram_notifier import telegram_notifier

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
WIDGETS_DIR = os.path.dirname(CURRENT_DIR)
FRONTEND_DIR = os.path.dirname(WIDGETS_DIR)
ROOT_DIR = os.path.dirname(FRONTEND_DIR)

CONFIG_PATH = os.path.join(ROOT_DIR, "config", "settings.json")
AI_CONFIG_PATH = os.path.join(ROOT_DIR, "config", "ai_config.json")
ASSETS_DIR = os.path.join(ROOT_DIR, "frontend", "assets")

DEFAULTS = {
    "risk_per_trade": 1.0,
    "max_drawdown": 5.0,
    "max_daily_loss": 500.0,
    "max_open_trades": 3,
    "max_losing_streak": 3,
    "execution_mode": "FULL-AUTO",
    "max_spread": 25,
    "slippage": 20,
    "enable_trailing_stop": False,
    "breakeven_pips": 0,
    "trailing_pips": 0,
    "news_defense_enabled": True,
    "news_defense_mins": 15,
    "news_defense_be_r": 1.5,
    "session_asian": True,
    "session_london": True,
    "session_ny": True,
    "close_friday": True,
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "alert_fills": True,
    "alert_sl_tp": True,
    "alert_risk_halt": True,
    "audio_sound_fx": True,
    "signal_expiry_sec": 60,
    "strategy": "builtin_ict_pro",
    "timeframe": 15,
}


class OptionsConfigBinder:
    """Manages reading and writing application configurations with atomic persistence."""

    @staticmethod
    def load_settings() -> Tuple[Dict[str, Any], str, str]:
        """Loads merged dictionary from settings.json and retrieves fallback AI tokens.

        Returns:
            Tuple[Dict[str, Any], str, str]: (data_dict, fallback_tg_token, fallback_tg_chat)
        """
        data = {}
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError) as err:
                logger.warning(f"[OptionsConfigBinder] Failed to read settings.json: {err}")

        fallback_token = ""
        fallback_chat = ""
        if os.path.exists(AI_CONFIG_PATH):
            try:
                with open(AI_CONFIG_PATH, "r", encoding="utf-8") as f_ai:
                    ai_c = json.load(f_ai)
                    fallback_token = ai_c.get("TELEGRAM_BOT_TOKEN", "")
                    fallback_chat = ai_c.get("TELEGRAM_CHAT_ID", "")
            except (json.JSONDecodeError, OSError) as err:
                logger.debug(f"[OptionsConfigBinder] AI config read non-fatal error: {err}")

        return data, fallback_token, fallback_chat

    @staticmethod
    def save_settings(new_data: Dict[str, Any]) -> bool:
        """Atomically persists updated settings and propagates tokens to Notifiers."""
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            merged_data = {}
            if os.path.exists(CONFIG_PATH):
                try:
                    with open(CONFIG_PATH, "r", encoding="utf-8") as f_prev:
                        merged_data = json.load(f_prev)
                except (json.JSONDecodeError, OSError):
                    pass

            merged_data.update(new_data)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(merged_data, f, indent=4)

            # Sync Notifier Singleton
            tok = new_data.get("telegram_bot_token", "").strip()
            cid = new_data.get("telegram_chat_id", "").strip()
            if tok:
                telegram_notifier.bot_token = tok
            if cid:
                telegram_notifier.chat_id = cid

            telegram_notifier.alert_fills = bool(new_data.get("alert_fills", True))
            telegram_notifier.alert_sl_tp = bool(new_data.get("alert_sl_tp", True))
            telegram_notifier.alert_risk_halt = bool(new_data.get("alert_risk_halt", True))

            # Sync AI Config if existing
            if os.path.exists(AI_CONFIG_PATH):
                try:
                    with open(AI_CONFIG_PATH, "r", encoding="utf-8") as f_ai:
                        ai_data = json.load(f_ai)
                    ai_data["TELEGRAM_BOT_TOKEN"] = tok
                    ai_data["TELEGRAM_CHAT_ID"] = cid
                    with open(AI_CONFIG_PATH, "w", encoding="utf-8") as f_ai:
                        json.dump(ai_data, f_ai, indent=4)
                except (json.JSONDecodeError, OSError) as err:
                    logger.debug(f"[OptionsConfigBinder] AI config sync non-fatal error: {err}")

            return True
        except Exception as exc:
            logger.error(f"[OptionsConfigBinder] Error saving settings to disk: {exc}")
            return False
