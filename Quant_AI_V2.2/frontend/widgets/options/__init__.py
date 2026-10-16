"""
Options Configuration Package.
Provides modular tabs and binder for institutional settings.
"""

from frontend.widgets.options.options_dialog import OptionsDialog
from frontend.widgets.options.options_binder import OptionsConfigBinder, DEFAULTS

__all__ = ["OptionsDialog", "OptionsConfigBinder", "DEFAULTS"]
