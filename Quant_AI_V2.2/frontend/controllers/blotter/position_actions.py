"""
Position Actions Handler - Trade Blotter Execution and Modification Services.
Handles market order liquidation and SL/TP parameter modifications with
EventBus telemetry and Telegram alerts.
"""

from typing import Dict, Any
from loguru import logger
from backend.infrastructure.brokers.mt5_safe import mt5
from backend.core.event_bus import event_bus
from backend.infrastructure.notifications.telegram_notifier import telegram_notifier
from frontend.widgets.modify_order_dialog import ModifyOrderDialog


class PositionActionsHandler:
    """Encapsulates execution operations on active positions (Close, Modify)."""

    def __init__(self, window, controller):
        self.window = window
        self.controller = controller

    def close_single_position(self, ticket: int) -> bool:
        """Institutional position liquidation at market price."""
        is_live = mt5.terminal_info() is not None
        success = False
        if is_live:
            exec_mgr = getattr(self.controller, "exec_mgr", None)
            if exec_mgr:
                res = exec_mgr.close_position(ticket)
                if res.get("status") == "success":
                    lat = res.get("latency_ms", 0.0)
                    event_bus.log_event.emit(
                        "",
                        "INFO",
                        f"LIQUIDATED POSITION #{ticket} | LATENCY: {lat:.1f}ms",
                        "#10b981",
                    )
                    telegram_notifier.send_message(
                        f"<b>[TRADE LIQUIDATION]</b>\nPosition #{ticket} closed successfully.\nExecution latency: {lat:.1f}ms"
                    )
                    success = True
                else:
                    err_msg = res.get("msg", "Unknown error")
                    event_bus.log_event.emit(
                        "",
                        "ERROR",
                        f"FAILED TO CLOSE #{ticket}: {err_msg}",
                        "#ef4444",
                    )
            else:
                logger.error("[PositionActionsHandler] exec_mgr unavailable for close_position")
        else:
            # Simulated demo closure
            if hasattr(self.controller, "_demo_positions") and self.controller._demo_positions:
                self.controller._demo_positions = [
                    p for p in self.controller._demo_positions if p["ticket"] != ticket
                ]
            event_bus.log_event.emit(
                "",
                "INFO",
                f"[SIMULATION] LIQUIDATED POSITION #{ticket}",
                "#10b981",
            )
            success = True

        if hasattr(self.controller, "_render_blotter"):
            self.controller._render_blotter("active")
        return success

    def modify_single_position(self, pos_info: Dict[str, Any]) -> bool:
        """Open institutional ModifyOrderDialog and execute TRADE_ACTION_SLTP."""
        ticket = pos_info.get("ticket", 0)
        sym = pos_info.get("symbol", "XAUUSD")
        order_type = pos_info.get("side", "BUY")
        vol = float(pos_info.get("volume", pos_info.get("lots", 0.1)))
        open_p = float(pos_info.get("open_price", pos_info.get("entry", 0.0)))
        cur_p = float(pos_info.get("current_price", pos_info.get("current", 0.0)))
        sl = float(pos_info.get("sl", 0.0))
        tp = float(pos_info.get("tp", 0.0))
        digits = int(pos_info.get("digits", 2))
        is_dark = getattr(self.controller, "is_dark_theme", False)

        dlg = ModifyOrderDialog(
            ticket=ticket,
            symbol=sym,
            order_type=order_type,
            volume=vol,
            open_price=open_p,
            current_price=cur_p,
            current_sl=sl,
            current_tp=tp,
            digits=digits,
            is_dark=is_dark,
            parent=self.window,
        )
        if not dlg.exec():
            return False

        new_sl, new_tp = dlg.get_values()
        is_live = mt5.terminal_info() is not None
        success = False
        if is_live:
            exec_mgr = getattr(self.controller, "exec_mgr", None)
            if exec_mgr:
                res = exec_mgr.modify_position(ticket, new_sl, new_tp)
                if res.get("status") == "success":
                    event_bus.log_event.emit(
                        "",
                        "INFO",
                        f"MODIFIED ORDER #{ticket} | SL: {new_sl} | TP: {new_tp}",
                        "#10b981",
                    )
                    success = True
                else:
                    event_bus.log_event.emit(
                        "",
                        "ERROR",
                        f"FAILED TO MODIFY #{ticket}: {res.get('msg', 'Error')}",
                        "#ef4444",
                    )
            else:
                logger.error("[PositionActionsHandler] exec_mgr unavailable for modify_position")
        else:
            if hasattr(self.controller, "_demo_positions") and self.controller._demo_positions:
                for p in self.controller._demo_positions:
                    if p["ticket"] == ticket:
                        p["sl"] = new_sl
                        p["tp"] = new_tp
            event_bus.log_event.emit(
                "",
                "INFO",
                f"[SIMULATION] MODIFIED #{ticket} | SL: {new_sl} | TP: {new_tp}",
                "#10b981",
            )
            success = True

        if hasattr(self.controller, "_render_blotter"):
            self.controller._render_blotter("active")
        return success
