"""
Trade Dispatcher - Institutional Execution and Order Routing Service.
Responsible for lot sizing validation, Stop Loss/Take Profit calculation,
direction compliance checks, MT5 market order execution, and LoRA dataset logging.
"""

from typing import Callable, Optional, Tuple
from loguru import logger

from backend.infrastructure.notifications.telegram_notifier import telegram_notifier


class TradeDispatcher:
    """Handles risk-adjusted position sizing and dispatches orders to broker API.

    Attributes:
        exec_mgr: Broker execution manager bridge.
        risk_mgr: Quantitative risk manager for position sizing.
        db: SQLite database manager.
        log_callback: Optional logging callback emitting (level, msg, color).
    """

    def __init__(
        self,
        execution_manager,
        risk_manager,
        db_manager,
        log_callback: Optional[Callable[[str, str, str], None]] = None,
    ):
        self.exec_mgr = execution_manager
        self.risk_mgr = risk_manager
        self.db = db_manager
        self.log_callback = log_callback

    def _log(self, level: str, msg: str, color: str = "#8B949E") -> None:
        if self.log_callback:
            self.log_callback(level, msg, color)
        else:
            if level == "INFO":
                logger.info(msg)
            elif level == "WARNING":
                logger.warning(msg)
            elif level == "ERROR":
                logger.error(msg)
            elif level == "SUCCESS":
                logger.info(f"SUCCESS: {msg}")

    def validate_direction(self, signal: str, trade_mode: str) -> bool:
        """Validates if signal complies with user-configured directional permission."""
        if trade_mode == "AUTO":
            return True
        if trade_mode == "LONG_ONLY" and signal == "BUY":
            return True
        if trade_mode == "SHORT_ONLY" and signal == "SELL":
            return True
        return False

    def calculate_sl_tp(
        self, signal: str, current: float, support: float, resistance: float
    ) -> Tuple[float, float]:
        """Calculates default technical SL/TP prices based on support/resistance range."""
        if signal == "BUY":
            sl_dist = current - support
            if sl_dist <= 0:
                sl_dist = current * 0.005
            sl_price = current - sl_dist
            tp_price = current + (sl_dist * 2)
        else:
            sl_dist = resistance - current
            if sl_dist <= 0:
                sl_dist = current * 0.005
            sl_price = current + sl_dist
            tp_price = current - (sl_dist * 2)
        return sl_price, tp_price

    def dispatch_market_order(
        self,
        symbol: str,
        signal: str,
        entry_price: float,
        sl_price: float,
        tp_price: float,
        risk_pct: float,
        strategy_name: str,
        confidence_str: str,
        sample_id: Optional[str] = None,
    ) -> Optional[dict]:
        """Calculates lot size, fires order to broker, and records database/LoRA state."""
        sl_points = abs(entry_price - sl_price)
        if sl_points <= 0:
            sl_points = entry_price * 0.005

        lot = self.risk_mgr.calculate_lot_size(symbol, sl_points, risk_pct=risk_pct)

        self._log(
            "TRADE",
            f"[{strategy_name}] Approved {signal} {symbol}. {confidence_str}. Vol: {lot} Lots. SL: {sl_price:.2f}",
            "#D2A8FF",
        )

        res = self.exec_mgr.execute_market_order(
            symbol, signal == "BUY", lot, sl_price, tp_price, comment=f"Quant_{signal}"
        )

        if res.get("status") == "success":
            self._log("SUCCESS", res["msg"], "#3FB950")
            ticket = res.get("ticket", 0)
            if ticket:
                self.db.record_open_trade(
                    ticket=ticket,
                    symbol=symbol,
                    order_type=signal,
                    volume=lot,
                    open_price=entry_price,
                    sl=sl_price,
                    tp=tp_price,
                    comment=f"Quant_{signal}",
                )

                if sample_id:
                    try:
                        from backend.infrastructure.ai_engines.dataset_recorder import (
                            dataset_recorder,
                        )
                        dataset_recorder.link_trade_execution(
                            sample_id=sample_id,
                            ticket=ticket,
                            entry_price=entry_price,
                            sl=sl_price,
                            tp=tp_price,
                            direction=signal,
                            lot=lot,
                        )
                    except (ImportError, AttributeError, RuntimeError) as err:
                        logger.debug(
                            f"[TradeDispatcher] DatasetRecorder link skipped for #{ticket}: {err}"
                        )

            telegram_notifier.send_message(
                f"🚀 <b>ORDER FILLED: {signal} {symbol}</b>\nVolume: {lot} Lots\nSL: {sl_price:.2f} | TP: {tp_price:.2f}\nReason: {confidence_str}",
                category="fill",
            )
            return res
        else:
            self._log("ERROR", res.get("msg", "Execution rejected"), "#DA3633")
            return res
