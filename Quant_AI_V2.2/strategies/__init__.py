# -*- coding: utf-8 -*-
"""
Strategies Module - Quant AI V2.2
=================================
Centralized directory containing all quantitative trading strategies:
- ict_strategy.py: ICT Zones Pro v4.2 (Asian Sweep + FVG)
- wyckoff_vectorized.py: Wyckoff Momentum Pro (Vectorized NumPy)
- ema_stress_test.py: EMA Dual Cross (Resilience Benchmark)
- custom_ict_fvg.py: Custom User Strategy Template
- strategy_loader.py: Auto-discovery and dynamic registry
"""

from .ict_strategy import ICTZonesProStrategy
from .ema_stress_test import EMAStressTestStrategy
from .wyckoff_vectorized import VectorizedBacktester
from .custom_ict_fvg import CustomICTFVGStrategy
from .strategy_loader import (
    discover_strategies,
    get_strategies_dir,
    get_user_strategies_dir,
    validate_strategy_file,
    import_strategy_file,
    load_strategy_instance,
)

__all__ = [
    "ICTZonesProStrategy",
    "EMAStressTestStrategy",
    "VectorizedBacktester",
    "CustomICTFVGStrategy",
    "discover_strategies",
    "get_strategies_dir",
    "get_user_strategies_dir",
    "validate_strategy_file",
    "import_strategy_file",
    "load_strategy_instance",
]
