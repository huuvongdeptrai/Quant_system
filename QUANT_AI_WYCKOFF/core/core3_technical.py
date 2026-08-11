import pandas as pd
from typing import Dict, Any
from core.strategies.wyckoff_strategy import WyckoffStrategy
from core.strategies.smc_strategy import SMCStrategy

class TechnicalRouter:
    """
    Core 3: Technical Router
    Dispatches data and macro bias to active trading strategies (Wyckoff, SMC).
    """

    def __init__(self, active_strategy: str = "wyckoff"):
        self.active_strategy_name = active_strategy
        self.strategies = {
            "wyckoff": WyckoffStrategy(),
            "smc": SMCStrategy()
        }

    def process(self, df: pd.DataFrame, macro_context: Dict[str, Any]) -> Dict[str, Any]:
        strategy = self.strategies.get(self.active_strategy_name, self.strategies["wyckoff"])
        return strategy.analyze(df, macro_context)
