"""
Watchlist Store - File Storage and Persistence Service.
Responsible for reading and writing user-configured watchlist symbols to JSON files.
"""

import os
import json
from typing import List, Optional, Tuple
from loguru import logger


DEFAULT_PAIRS: List[Tuple[str, str]] = [
    ("XAUUSD", "COMMODITIES"),
    ("XAGUSD", "COMMODITIES"),
    ("BTCUSD", "CRYPTO"),
    ("ETHUSD", "CRYPTO"),
    ("EURUSD", "FOREX"),
    ("GBPUSD", "FOREX"),
    ("USDJPY", "FOREX"),
    ("US30", "INDICES"),
    ("NAS100", "INDICES"),
]


class WatchlistStore:
    """Encapsulates JSON storage and retrieval of active symbols."""

    def __init__(self, root_dir: Optional[str] = None):
        if not root_dir:
            root_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            )
        self.root_dir = root_dir
        self.config_file = os.path.join(self.root_dir, "config", "watchlist.json")
        self.data_file = os.path.join(self.root_dir, "data", "watchlist.json")

    def get_candidate_paths(self) -> List[str]:
        return [
            self.config_file,
            self.data_file,
            os.path.join(self.root_dir, "data", "watchlist.json"),
        ]

    def load_saved_symbols(self) -> Tuple[bool, Optional[List[str]]]:
        for candidate in self.get_candidate_paths():
            if os.path.exists(candidate):
                try:
                    with open(candidate, "r", encoding="utf-8") as f:
                        raw = json.load(f)
                    if isinstance(raw, dict) and "symbols" in raw:
                        return True, list(raw["symbols"])
                    elif isinstance(raw, list):
                        return True, list(raw)
                except Exception as err:
                    logger.debug(f"[WatchlistStore] Error reading {candidate}: {err}")
                return True, []
        return False, None

    def save_symbols(self, symbols: List[str]) -> bool:
        target_paths = [
            self.data_file,
            self.config_file,
        ]
        success = True
        for target in target_paths:
            try:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, "w", encoding="utf-8") as f:
                    if "config" in target:
                        json.dump({"symbols": symbols}, f, indent=4)
                    else:
                        json.dump(symbols, f, indent=4)
                    f.flush()
                    try:
                        os.fsync(f.fileno())
                    except Exception:
                        pass
            except Exception as err:
                logger.debug(f"[WatchlistStore] Non-fatal save exception to {target}: {err}")
                success = False
        return success
