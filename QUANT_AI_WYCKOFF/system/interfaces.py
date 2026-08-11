from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, Any, Optional

class IDataProvider(ABC):
    """Abstract class for Data Provider (e.g. MT5 Data Fetcher)"""
    
    @abstractmethod
    def fetch_ohlcv(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame:
        pass

    @abstractmethod
    def get_current_tick(self, symbol: str) -> Dict[str, float]:
        pass

class IMacroAnalyzer(ABC):
    """Abstract class for Macro / LLM Analysis Core"""
    
    @abstractmethod
    def analyze_macro_bias(self, symbol: str) -> Dict[str, Any]:
        pass

class IStrategy(ABC):
    """Abstract class for Technical Strategies (Wyckoff, SMC, etc.)"""
    
    @abstractmethod
    def analyze(self, df: pd.DataFrame, macro_context: Dict[str, Any]) -> Dict[str, Any]:
        pass

class IRiskManager(ABC):
    """Abstract class for Risk Management Core"""
    
    @abstractmethod
    def calculate_position_size(self, account_balance: float, entry_price: float, sl_price: float, symbol: str) -> float:
        pass

    @abstractmethod
    def validate_trade(self, trade_signal: Dict[str, Any]) -> bool:
        pass

class IExecutionManager(ABC):
    """Abstract class for Order Execution Core"""
    
    @abstractmethod
    def execute_order(self, order_packet: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def manage_open_positions(self) -> None:
        pass
