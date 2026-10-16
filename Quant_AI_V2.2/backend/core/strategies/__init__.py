# -*- coding: utf-8 -*-
"""
Quantitative Trading Strategies Module (Legacy Path Forwarder)
All strategies are now centralized in the top-level 'strategies/' directory.
"""

from strategies.ict_strategy import ICTZonesProStrategy
from strategies.ema_stress_test import EMAStressTestStrategy
from strategies.wyckoff_vectorized import VectorizedBacktester
from strategies.strategy_loader import (
    discover_strategies,
    load_strategy_instance,
    get_strategies_dir,
    get_user_strategies_dir,
    validate_strategy_file,
    import_strategy_file,
)

__all__ = [
    "ICTZonesProStrategy",
    "EMAStressTestStrategy",
    "VectorizedBacktester",
    "discover_strategies",
    "load_strategy_instance",
    "get_strategies_dir",
    "get_user_strategies_dir",
    "validate_strategy_file",
    "import_strategy_file",
]
