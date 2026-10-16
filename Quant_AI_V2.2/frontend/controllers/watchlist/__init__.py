"""
Watchlist Controller Package.
Provides SymbolSearchDialog, WatchlistDelegate, WatchlistStore, and WatchlistManager.
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
