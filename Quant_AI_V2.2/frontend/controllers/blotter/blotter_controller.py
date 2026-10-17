"""
Trade Blotter Controller for Quant_AI V2.2
Manages active positions, pending orders, trade history, and execution actions (Close, Modify, Flatten, Kill Switch).
Coordinates PositionsTableView, PositionActionsHandler, and KillSwitchHandler.
"""

from typing import Optional, Dict, Any
from frontend.controllers.blotter.positions_table_view import PositionsTableView
from frontend.controllers.blotter.position_actions import PositionActionsHandler
from frontend.controllers.blotter.kill_switch_dialog import KillSwitchHandler


class BlotterController:
    """Institutional Trade Blotter managing Executions Table, Orders, Positions, and Kill Switch."""

    def __init__(self, terminal):
        self.terminal = terminal
        self.window = terminal.window
        self.flatten_countdown = 0
        self.flatten_timer = None
        self.active_blotter_mode = "active"

        # Modular SRP Sub-components
        self.table_view = PositionsTableView(self.window, self)
        self.actions_handler = PositionActionsHandler(self.window, self)
        self.kill_switch_handler = KillSwitchHandler(self.window, self)

    def __getattr__(self, name):
        return getattr(self.terminal, name)

    def __setattr__(self, name, value):
        if name in (
            "terminal", "window", "flatten_countdown", "flatten_timer",
            "active_blotter_mode", "table_view", "actions_handler",
            "kill_switch_handler", "btn_blotter_flatten", "_flatten_armed",
            "_flatten_countdown", "_flatten_timer"
        ):
            super().__setattr__(name, value)
            if name == "active_blotter_mode" and hasattr(self, "terminal"):
                try:
                    setattr(self.terminal, name, value)
                except Exception:
                    pass
        else:
            super().__setattr__(name, value)
            if hasattr(self, "terminal"):
                setattr(self.terminal, name, value)

    def _setup_executions_table(self):
        """Setup institutional MT5-style Trade Blotter layout and controls."""
        return self.table_view.setup_ui()

    def _render_blotter(self, mode: Optional[str] = None):
        """Render active positions, history deals, or pending orders."""
        return self.table_view.render(mode)

    def _close_single_position(self, ticket: int) -> bool:
        """Institutional position liquidation at market price."""
        return self.actions_handler.close_single_position(ticket)

    def _modify_single_position(self, pos_info: Dict[str, Any]) -> bool:
        """Open institutional ModifyOrderDialog and modify SL/TP."""
        return self.actions_handler.modify_single_position(pos_info)

    def _apply_flatten_btn_style(self):
        """Apply theme-appropriate styling to FLATTEN ALL button."""
        return self.kill_switch_handler.apply_flatten_btn_style()

    def _disarm_flatten_button(self):
        """Disarm the armed countdown on the FLATTEN button."""
        return self.kill_switch_handler.disarm_flatten_button()

    def _on_flatten_timer_tick(self):
        """Timer tick handler for armed confirmation countdown."""
        return self.kill_switch_handler.on_flatten_timer_tick()

    def _handle_kill_switch(self):
        """Emergency Kill-Switch / Flatten All: 2-step armed click confirmation."""
        return self.kill_switch_handler.handle_kill_switch()
