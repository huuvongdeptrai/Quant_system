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



    def _check_headless_mt5(self):
        try:
            import json, sys
            if sys.platform != "win32":
                return
            root_d = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            cfg_p = os.path.join(root_d, "config", "settings.json")
            if not os.path.exists(cfg_p):
                return
            with open(cfg_p, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if not cfg.get("headless_mt5", False):
                return
            self.hide_mt5_window()
        except Exception as e:
            logger.debug(f"[MT5Safe] Headless check error: {e}")

    def hide_mt5_window(self):
        """Hides the MT5 desktop window using Win32 API SW_HIDE."""
        try:
            import ctypes, sys
            if sys.platform != "win32":
                return False
            user32 = ctypes.windll.user32
            hidden = []
            def enum_proc(hwnd, lParam):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        title = buff.value
                        if "MetaTrader" in title or "terminal64" in title.lower():
                            user32.ShowWindow(hwnd, 0) # SW_HIDE = 0
                            hidden.append(hwnd)
                return True
            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            user32.EnumWindows(EnumWindowsProc(enum_proc), 0)
            if hidden:
                logger.info(f"[MT5Safe] Silent background mode active: hidden {len(hidden)} MT5 window(s).")
                return True
            return False
        except Exception as e:
            logger.warning(f"[MT5Safe] Failed to hide MT5 window: {e}")
            return False

    def show_mt5_window(self):
        """Restores the MT5 desktop window using Win32 API SW_SHOW."""
        try:
            import ctypes, sys
            if sys.platform != "win32":
                return False
            user32 = ctypes.windll.user32
            def enum_proc(hwnd, lParam):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value
                    if "MetaTrader" in title:
                        user32.ShowWindow(hwnd, 5) # SW_SHOW = 5
                return True
            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            user32.EnumWindows(EnumWindowsProc(enum_proc), 0)
            return True
        except Exception as e:
            logger.warning(f"[MT5Safe] Failed to show MT5 window: {e}")
            return False

mt5 = MT5SafeController()
