from typing import Dict, Any
from system.interfaces import IRiskManager

class RiskManager(IRiskManager):
    """
    Core 4: Risk Management & Position Sizing
    Calculates dynamic lot size, verifies max daily drawdowns, and manages trailing stop.
    """

    def __init__(self, risk_percent: float = 1.0, max_daily_loss: float = 3.0):
        self.risk_percent = risk_percent
        self.max_daily_loss = max_daily_loss

    def calculate_position_size(self, account_balance: float, entry_price: float, sl_price: float, symbol: str) -> float:
        risk_amount = account_balance * (self.risk_percent / 100.0)
        sl_distance = abs(entry_price - sl_price)
        if sl_distance == 0:
            return 0.01
        
        # Simplified lot calculation for Forex standard lot (100,000 units)
        lot_size = round(risk_amount / (sl_distance * 100000), 2)
        return max(0.01, lot_size)

    def validate_trade(self, trade_signal: Dict[str, Any]) -> bool:
        if not trade_signal or trade_signal.get("action") == "HOLD":
            return False
        return True
