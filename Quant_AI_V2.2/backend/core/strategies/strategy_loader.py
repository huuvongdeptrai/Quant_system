# -*- coding: utf-8 -*-
"""
Forwarding proxy to centralized strategies/strategy_loader.py
Ensures 100% backward compatibility for existing code imports.
"""

from strategies.strategy_loader import (
    get_strategies_dir,
    get_user_strategies_dir,
    validate_strategy_file,
    import_strategy_file,
    discover_strategies,
    load_strategy_instance,
)

__all__ = [
    "get_strategies_dir",
    "get_user_strategies_dir",
    "validate_strategy_file",
    "import_strategy_file",
    "discover_strategies",
    "load_strategy_instance",
]
