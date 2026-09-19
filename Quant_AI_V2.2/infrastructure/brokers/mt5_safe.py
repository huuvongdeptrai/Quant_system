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
            return _mt5.initialize(*args, **kwargs)

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


mt5 = MT5SafeController()
