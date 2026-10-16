"""
Frontend Controllers Package for Quant_AI V2.2
Provides modular controllers for every tab and subsystem:
- Tab 1: chart_controller, blotter_controller, watchlist_controller, header_controller, navigation_controller
- Tab 2: performance_controller
- Tab 3: backtest_controller
- Tab 4: logs_controller
- Tab 5: settings_controller
- Aux: account_controller, macro_calendar_controller
"""

from .chart_controller import setup_chart_ui, update_chart_theme
from .blotter_controller import BlotterController
from .navigation_controller import NavigationController
from .header_controller import HeaderController, WorkspaceHeaderController
from .watchlist_controller import WatchlistController, WatchlistManager
from .performance_controller import PerformanceController, StatsManager
from .backtest_controller import BacktestController, BacktestWorkbenchController, setup_backtest_tab
from .logs_controller import LogsController, LogManager
from .settings_controller import SettingsManager
from .account_controller import AccountController, AccountManager
from .macro_calendar_controller import MacroCalendarController, CalendarManager

__all__ = [
    "setup_chart_ui",
    "update_chart_theme",
    "BlotterController",
    "NavigationController",
    "HeaderController",
    "WorkspaceHeaderController",
    "WatchlistController",
    "WatchlistManager",
    "PerformanceController",
    "StatsManager",
    "BacktestController",
    "BacktestWorkbenchController",
    "setup_backtest_tab",
    "LogsController",
    "LogManager",
    "SettingsManager",
    "AccountController",
    "AccountManager",
    "MacroCalendarController",
    "CalendarManager",
]
