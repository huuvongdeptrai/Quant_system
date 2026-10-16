"""
Compatibility Facade Shim for WatchlistController.
Transfers legacy imports directly to the modularized watchlist package to guarantee
100% backwards compatibility for main.py, audit scripts, and pytest test suite.
"""

from frontend.controllers.watchlist.symbol_search_dialog import SymbolSearchDialog
from frontend.controllers.watchlist.watchlist_delegate import WatchlistDelegate
from frontend.controllers.watchlist.watchlist_store import WatchlistStore
from frontend.controllers.watchlist.watchlist_controller import (
    WatchlistManager, WatchlistController
)

__all__ = [
    "SymbolSearchDialog",
    "WatchlistDelegate",
    "WatchlistStore",
    "WatchlistManager",
    "WatchlistController",
]
