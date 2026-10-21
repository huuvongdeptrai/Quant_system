"""
Unified Institutional Timezone Manager.
Single Source of Truth for timezone normalization and display across
Chart Candles, Crosshair OHLC, Macro Calendar, and Execution Logs.
"""

import json
import os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, Any, List, Optional
from loguru import logger

SUPPORTED_TIMEZONES = {
    "UTC+7": {
        "key": "UTC+7",
        "short_label": "UTC+7",
        "menu_text": "UTC+7 (Hanoi / Bangkok / Indochina)",
        "cal_header": "TIME (VN)",
        "tz_info": timezone(timedelta(hours=7)),
    },
    "UTC": {
        "key": "UTC",
        "short_label": "UTC",
        "menu_text": "UTC (London / Universal Time)",
        "cal_header": "TIME (UTC)",
        "tz_info": timezone.utc,
    },
    "US/Eastern": {
        "key": "US/Eastern",
        "short_label": "NY (ET)",
        "menu_text": "New York Wall St (US Eastern)",
        "cal_header": "TIME (NY)",
        "tz_info": ZoneInfo("America/New_York"),
    },
    "Broker": {
        "key": "Broker",
        "short_label": "BROKER",
        "menu_text": "Broker Server Time",
        "cal_header": "TIME (SRV)",
        "tz_info": None,
    },
}


class TimezoneManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TimezoneManager, cls).__new__(cls)
            cls._instance._active_key = "UTC+7"
            cls._instance._listeners = []
            cls._instance._load_from_config()
        return cls._instance

    def _load_from_config(self):
        try:
            root_d = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            cfg_p = os.path.join(root_d, "config", "settings.json")
            if os.path.exists(cfg_p):
                with open(cfg_p, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                tz_key = cfg.get("display_timezone", "UTC+7")
                if tz_key in SUPPORTED_TIMEZONES:
                    self._active_key = tz_key
        except Exception as e:
            logger.debug(f"[TimezoneManager] Load config error: {e}")

    def save_to_config(self, tz_key: str):
        try:
            root_d = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            cfg_p = os.path.join(root_d, "config", "settings.json")
            cfg = {}
            if os.path.exists(cfg_p):
                with open(cfg_p, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            cfg["display_timezone"] = tz_key
            with open(cfg_p, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4)
        except Exception as e:
            logger.debug(f"[TimezoneManager] Save config error: {e}")

    @property
    def active_key(self) -> str:
        return self._active_key

    @property
    def short_label(self) -> str:
        return SUPPORTED_TIMEZONES.get(self._active_key, {}).get("short_label", "UTC+7")

    @property
    def cal_header(self) -> str:
        return SUPPORTED_TIMEZONES.get(self._active_key, {}).get("cal_header", "TIME (VN)")

    def set_active_timezone(self, tz_key: str):
        if tz_key not in SUPPORTED_TIMEZONES:
            return
        if self._active_key != tz_key:
            self._active_key = tz_key
            self.save_to_config(tz_key)
            self._notify_listeners()

    def add_listener(self, callback):
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify_listeners(self):
        for cb in list(self._listeners):
            try:
                cb(self._active_key)
            except Exception as e:
                logger.debug(f"[TimezoneManager] Listener callback error: {e}")

    def get_broker_offset(self) -> int:
        """Determines broker server time offset from UTC in seconds."""
        try:
            from backend.infrastructure.brokers.mt5_safe import mt5
            if hasattr(mt5, "get_broker_utc_offset"):
                return mt5.get_broker_utc_offset()
        except Exception:
            pass
        return 7200  # Default UTC+2 (EET)

    def mt5_to_utc_ts(self, mt5_ts: int) -> int:
        """Converts raw MT5 rate timestamp (broker server time) to true UTC epoch."""
        return int(mt5_ts) - self.get_broker_offset()

    def utc_to_display_dt(self, utc_ts: float) -> datetime:
        """Converts UTC epoch timestamp to datetime in active display timezone."""
        dt_utc = datetime.fromtimestamp(utc_ts, tz=timezone.utc)
        if self._active_key == "Broker":
            offset = self.get_broker_offset()
            return dt_utc.astimezone(timezone(timedelta(seconds=offset)))
        tz_info = SUPPORTED_TIMEZONES.get(self._active_key, {}).get("tz_info")
        if tz_info:
            return dt_utc.astimezone(tz_info)
        return dt_utc.astimezone(timezone(timedelta(hours=7)))

    def format_utc_ts(self, utc_ts: float, fmt: str = "%d/%m %H:%M") -> str:
        """Formats UTC epoch timestamp according to active display timezone."""
        return self.utc_to_display_dt(utc_ts).strftime(fmt)

    def format_mt5_ts(self, mt5_ts: int, fmt: str = "%d/%m %H:%M") -> str:
        """Normalizes MT5 broker timestamp to UTC and formats in active display timezone."""
        utc_ts = self.mt5_to_utc_ts(mt5_ts)
        return self.format_utc_ts(utc_ts, fmt)


timezone_manager = TimezoneManager()
