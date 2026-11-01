import os
import sys
import types
import importlib.util

# Explicit opt-in only. This stub cannot trade and is never installed in production.
if os.environ.get("VECTRA_OFFLINE_TESTS") == "1":
    stub = types.ModuleType("MetaTrader5")
    constants = {
        "TIMEFRAME_M1":1,"TIMEFRAME_M5":5,"TIMEFRAME_M15":15,"TIMEFRAME_M30":30,
        "TIMEFRAME_H1":16385,"TIMEFRAME_H4":16388,"TIMEFRAME_D1":16408,"TIMEFRAME_W1":32769,"TIMEFRAME_MN1":49153,
        "ORDER_TYPE_BUY":0,"ORDER_TYPE_SELL":1,"ORDER_TYPE_BUY_LIMIT":2,"ORDER_TYPE_SELL_LIMIT":3,
        "ORDER_TYPE_BUY_STOP":4,"ORDER_TYPE_SELL_STOP":5,"ORDER_TIME_GTC":0,
        "ORDER_FILLING_FOK":0,"ORDER_FILLING_IOC":1,"ORDER_FILLING_RETURN":2,
        "TRADE_ACTION_DEAL":1,"TRADE_ACTION_PENDING":5,"TRADE_ACTION_SLTP":6,"TRADE_ACTION_MODIFY":7,"TRADE_ACTION_REMOVE":8,
        "TRADE_RETCODE_REQUOTE":10004,"TRADE_RETCODE_PLACED":10008,"TRADE_RETCODE_DONE":10009,
        "TRADE_RETCODE_DONE_PARTIAL":10010,"TRADE_RETCODE_TIMEOUT":10012,"TRADE_RETCODE_MARKET_CLOSED":10018,
        "TRADE_RETCODE_PRICE_CHANGED":10020,"TRADE_RETCODE_PRICE_OFF":10021,"TRADE_RETCODE_CONNECTION":10031,
    }
    for minutes in (2,3,4,6,10,12,20):
        constants[f'TIMEFRAME_M{minutes}']=minutes
    for hours in (2,3,6,8,12):
        constants[f'TIMEFRAME_H{hours}']=16384+hours
    stub.__dict__.update(constants)
    def unavailable(*args, **kwargs): return None
    for name in ("terminal_info","account_info","positions_get","orders_get","order_send","order_check",
                 "order_calc_margin","order_calc_profit","symbol_info","symbol_info_tick","symbols_get",
                 "copy_rates_from_pos","copy_rates_range","history_orders_get","history_deals_get","shutdown"):
        setattr(stub,name,unavailable)
    stub.initialize=lambda *a,**k:False
    stub.login=lambda *a,**k:False
    stub.symbol_select=lambda *a,**k:False
    stub.positions_total=lambda:0
    stub.last_error=lambda:(-1,"Offline test stub")
    sys.modules["MetaTrader5"]=stub

import pytest
from backend.infrastructure.brokers.mt5_safe import mt5


@pytest.fixture(autouse=True)
def isolate_mt5_environment():
    """Ensures MT5 connection state does not leak across test modules and boundaries."""
    yield
    try:
        mt5.shutdown()
    except Exception:
        pass

@pytest.fixture(autouse=True)
def isolated_trading_state(tmp_path, monkeypatch):
    from backend.database.db_manager import DatabaseManager
    from backend.core.trading_commands import TradingCommandService
    DatabaseManager.reset_instance()
    DatabaseManager(str(tmp_path / "isolated.sqlite"))
    TradingCommandService._runtime = None
    TradingCommandService._emergency_halt = False
    monkeypatch.setenv("QUANT_TESTING", "1")
    from backend.core.macro_context_bus import MacroContextBus
    MacroContextBus._instance=None
    from backend.core.macro_context_bus import SymbolMacroProfile
    from backend.infrastructure.data_providers.asset_registry import AssetRegistry
    bus=MacroContextBus.get_instance()
    for symbol in ('XAUUSD','EURUSD','GBPUSD','USDJPY','BTCUSD','ETHUSD','SOLUSD','US30','US500'):
        bus.set_profile(SymbolMacroProfile(symbol=symbol,asset_class=AssetRegistry.identify(symbol).value))
    yield
    DatabaseManager.reset_instance()
    TradingCommandService._runtime = None
    TradingCommandService._emergency_halt = False

@pytest.fixture(autouse=True)
def offline_network_guard(monkeypatch):
    if os.environ.get("VECTRA_OFFLINE_TESTS") != "1":
        return
    def blocked(*args, **kwargs):
        raise ConnectionError("External network disabled in offline regression tests")
    import requests
    monkeypatch.setattr(requests.sessions.Session, "request", blocked)
    try:
        import curl_cffi.requests
        monkeypatch.setattr(curl_cffi.requests.Session,"request",blocked)
    except ImportError:
        pass

_qt_app = None
@pytest.fixture(scope="session",autouse=True)
def persistent_qt_application():
    global _qt_app
    from PySide6.QtWidgets import QApplication
    _qt_app=QApplication.instance() or QApplication([])
    yield _qt_app
    from PySide6.QtCore import QThreadPool
    QThreadPool.globalInstance().waitForDone(5000)
    _qt_app.processEvents()

@pytest.fixture(autouse=True)
def nonblocking_offscreen_dialogs(monkeypatch):
    if os.environ.get("VECTRA_OFFLINE_TESTS") == "1":
        from PySide6.QtWidgets import QMessageBox
        for name in ('warning','critical','information'):
            monkeypatch.setattr(QMessageBox,name,lambda *a,**k:QMessageBox.StandardButton.Ok)


@pytest.fixture(scope="session", autouse=True)
def offline_market_sources():
    if os.environ.get("VECTRA_OFFLINE_TESTS") != "1":
        yield
        return
    import yfinance
    import pandas as pd
    patches = pytest.MonkeyPatch()
    patches.setattr(yfinance, "download", lambda *a, **k: pd.DataFrame())
    patches.setattr(yfinance.Ticker, "history", lambda *a, **k: pd.DataFrame())
    yield
    patches.undo()
