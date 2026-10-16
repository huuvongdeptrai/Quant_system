"""
Compatibility Facade Shim for OptionsDialog.
Transfers legacy imports directly to the modularized options package to guarantee
100% backwards compatibility for main.py, settings_controller.py, and unit tests.
"""

from frontend.widgets.options.options_dialog import OptionsDialog
from frontend.widgets.options.options_binder import OptionsConfigBinder, DEFAULTS

__all__ = ["OptionsDialog", "OptionsConfigBinder", "DEFAULTS"]
