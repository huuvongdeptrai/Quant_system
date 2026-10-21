import os
import threading
import MetaTrader5 as _mt5
from loguru import logger


class MT5SafeController:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(MT5SafeController, cls).__new__(cls)
                cls._instance._mt5_lock = threading.Lock()
        return cls._instance

    def __getattr__(self, name):
        attr = getattr(_mt5, name)
        if callable(attr):

            def wrapper(*args, **kwargs):
                with self._mt5_lock:
                    if kwargs:
                        return attr(*args, **kwargs)
                    return attr(*args)

            return wrapper
        return attr

    def initialize(self, *args, **kwargs):
        with self._mt5_lock:
            res = _mt5.initialize(*args, **kwargs)
            if not res and not args and not kwargs:
                for custom_path in [
                    r"C:\Program Files\LiteFinance MT5 Terminal\terminal64.exe",
                    r"C:\Program Files\MetaTrader 5\terminal64.exe",
                    r"C:\Program Files (x86)\MetaTrader 5\terminal64.exe",
                ]:
                    if os.path.exists(custom_path):
                        res = _mt5.initialize(path=custom_path)
                        if res:
                            break
            if res:
                self._check_headless_mt5()
            return res

    def login(self, *args, **kwargs):
        with self._mt5_lock:
            return _mt5.login(*args, **kwargs)

    def shutdown(self):
        with self._mt5_lock:
            _mt5.shutdown()

    def terminal_info(self):
        with self._mt5_lock:
            return _mt5.terminal_info()

    def account_info(self):
        with self._mt5_lock:
            return _mt5.account_info()

    def symbols_get(self, *args, **kwargs):
        with self._mt5_lock:
            if kwargs:
                return _mt5.symbols_get(*args, **kwargs)
            return _mt5.symbols_get(*args)

    def symbol_select(self, symbol, enable=True):
        with self._mt5_lock:
            return _mt5.symbol_select(symbol, enable)

    def symbol_info(self, symbol):
        with self._mt5_lock:
            if _mt5.symbol_select(symbol, True):
                return _mt5.symbol_info(symbol)
            return None

    def symbol_info_tick(self, symbol):
        with self._mt5_lock:
            if _mt5.symbol_select(symbol, True):
                return _mt5.symbol_info_tick(symbol)
            return None

    def copy_rates_from_pos(self, symbol, timeframe, start_pos, count):
        with self._mt5_lock:
            if _mt5.symbol_select(symbol, True):
                return _mt5.copy_rates_from_pos(symbol, timeframe, start_pos, count)
            return None

    def history_orders_get(self, *args, **kwargs):
        with self._mt5_lock:
            if kwargs:
                return _mt5.history_orders_get(*args, **kwargs)
            return _mt5.history_orders_get(*args)

    def history_deals_get(self, *args, **kwargs):
        with self._mt5_lock:
            if kwargs:
                return _mt5.history_deals_get(*args, **kwargs)
            return _mt5.history_deals_get(*args)

    def orders_get(self, *args, **kwargs):
        with self._mt5_lock:
            if kwargs:
                return _mt5.orders_get(*args, **kwargs)
            return _mt5.orders_get(*args)

    def positions_get(self, *args, **kwargs):
        with self._mt5_lock:
            if kwargs:
                return _mt5.positions_get(*args, **kwargs)
            return _mt5.positions_get(*args)

    def positions_total(self):
        with self._mt5_lock:
            return _mt5.positions_total()

    def order_send(self, request):
        with self._mt5_lock:
            return _mt5.order_send(request)

    def order_check(self, request):
        with self._mt5_lock:
            return _mt5.order_check(request)

    def order_calc_margin(self, action, symbol, volume, price):
        with self._mt5_lock:
            return _mt5.order_calc_margin(action, symbol, volume, price)

    def order_calc_profit(self, action, symbol, volume, price_open, price_close):
        with self._mt5_lock:
            return _mt5.order_calc_profit(
                action, symbol, volume, price_open, price_close
            )

    def get_broker_utc_offset(self) -> int:
        """
        Calculates broker server UTC offset in seconds (e.g. +7200 for UTC+2 EET).
        Returns offset such that: broker_time = utc_time + offset.
        Defaults to +7200 (2h) if disconnected.
        """
        try:
            with self._mt5_lock:
                from datetime import datetime, timezone
                for sym in ("XAUUSD", "EURUSD", "GBPUSD", "BTCUSD"):
                    tick = _mt5.symbol_info_tick(sym)
                    if tick and getattr(tick, "time", 0) > 0:
                        utc_now = datetime.now(timezone.utc).timestamp()
                        diff = tick.time - utc_now
                        offset_hours = round(diff / 3600.0)
                        return int(offset_hours * 3600)
        except Exception as e:
            logger.debug(f"[MT5Safe] Error determining broker UTC offset: {e}")
        return 7200



    def _check_headless_mt5(self):
        try:
            import json, sys
            if sys.platform != "win32":
                return
            root_d = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            cfg_p = os.path.join(root_d, "config", "settings.json")
            headless = True
            if os.path.exists(cfg_p):
                with open(cfg_p, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                headless = cfg.get("headless_mt5", True)
            if headless:
                self.hide_mt5_window()
        except Exception as e:
            logger.debug(f"[MT5Safe] Headless check error: {e}")

    def _get_mt5_pids(self):
        """Retrieves active PIDs for MT5 executable instances."""
        try:
            import psutil
            pids = set()
            for p in psutil.process_iter(["pid", "name"]):
                try:
                    pname = p.info.get("name")
                    if pname and pname.lower() in ("terminal64.exe", "terminal.exe", "metatrader.exe"):
                        pids.add(p.info["pid"])
                except Exception:
                    pass
            return pids
        except Exception:
            return set()

    def hide_mt5_window(self):
        """Hides the MT5 desktop window using Win32 API SW_HIDE based on PID, Class Name, and Title."""
        try:
            import ctypes, sys
            from ctypes import wintypes
            if sys.platform != "win32":
                return False

            user32 = ctypes.windll.user32
            hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
            if hdesk:
                user32.SetThreadDesktop(hdesk)

            mt5_pids = self._get_mt5_pids()
            hidden = []

            def enum_proc(hwnd, lParam):
                if user32.IsWindowVisible(hwnd):
                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

                    class_buff = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(hwnd, class_buff, 256)
                    c_name = class_buff.value

                    is_mt5 = False
                    if pid.value in mt5_pids:
                        is_mt5 = True
                    elif "MetaQuotes::MetaTrader" in c_name:
                        is_mt5 = True
                    else:
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buff, length + 1)
                            t = buff.value
                            if "MetaTrader" in t or "terminal64" in t.lower() or "Hedge" in t:
                                is_mt5 = True

                    if is_mt5:
                        user32.ShowWindow(hwnd, 0)  # SW_HIDE = 0
                        hidden.append(hwnd)
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            if hdesk:
                user32.EnumDesktopWindows(hdesk, WNDENUMPROC(enum_proc), 0)
            else:
                user32.EnumWindows(WNDENUMPROC(enum_proc), 0)

            if hidden:
                logger.info(f"[MT5Safe] Silent background mode active: hidden {len(hidden)} MT5 window(s).")
                return True
            return False
        except Exception as e:
            logger.warning(f"[MT5Safe] Failed to hide MT5 window: {e}")
            return False

    def show_mt5_window(self):
        """Restores the MT5 desktop main window using Win32 API SW_SHOW."""
        try:
            import ctypes, sys
            from ctypes import wintypes
            if sys.platform != "win32":
                return False

            user32 = ctypes.windll.user32
            hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
            if hdesk:
                user32.SetThreadDesktop(hdesk)

            mt5_pids = self._get_mt5_pids()
            shown = []

            def enum_proc(hwnd, lParam):
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

                class_buff = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, class_buff, 256)
                c_name = class_buff.value

                if pid.value in mt5_pids or "MetaQuotes::MetaTrader" in c_name:
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        user32.ShowWindow(hwnd, 5)  # SW_SHOW = 5
                        user32.SetForegroundWindow(hwnd)
                        shown.append(hwnd)
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            if hdesk:
                user32.EnumDesktopWindows(hdesk, WNDENUMPROC(enum_proc), 0)
            else:
                user32.EnumWindows(WNDENUMPROC(enum_proc), 0)

            if shown:
                logger.info(f"[MT5Safe] Restored {len(shown)} MT5 main window(s).")
                return True
            return False
        except Exception as e:
            logger.warning(f"[MT5Safe] Failed to show MT5 window: {e}")
            return False

    def is_mt5_window_visible(self):
        """Checks if the MT5 main window is currently visible."""
        try:
            import ctypes, sys
            from ctypes import wintypes
            if sys.platform != "win32":
                return False

            user32 = ctypes.windll.user32
            hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
            if hdesk:
                user32.SetThreadDesktop(hdesk)

            mt5_pids = self._get_mt5_pids()
            visible = []

            def enum_proc(hwnd, lParam):
                if user32.IsWindowVisible(hwnd):
                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    class_buff = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(hwnd, class_buff, 256)
                    c_name = class_buff.value
                    if pid.value in mt5_pids or "MetaQuotes::MetaTrader" in c_name:
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            visible.append(hwnd)
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            if hdesk:
                user32.EnumDesktopWindows(hdesk, WNDENUMPROC(enum_proc), 0)
            else:
                user32.EnumWindows(WNDENUMPROC(enum_proc), 0)

            return len(visible) > 0
        except Exception:
            return False

mt5 = MT5SafeController()
