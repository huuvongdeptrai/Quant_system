"""
Compatibility Facade Shim for BlotterController.
Transfers legacy imports directly to the modularized blotter package to guarantee
100% backwards compatibility for main.py, audit scripts, and pytest test suite.
"""

from frontend.controllers.blotter.positions_table_view import PositionsTableView
from frontend.controllers.blotter.position_actions import PositionActionsHandler
from frontend.controllers.blotter.kill_switch_dialog import KillSwitchHandler
from frontend.controllers.blotter.blotter_controller import BlotterController

__all__ = [
    "PositionsTableView",
    "PositionActionsHandler",
    "KillSwitchHandler",
    "BlotterController",
]
