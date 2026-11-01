"""
Unit tests for Unified Institutional Timezone Engine and Cross-Workspace Synchronization.
Validates that Chart TimeAxis, Crosshair Tooltip, and Macro Economic Calendar remain 100% synchronized.
"""

import pytest
from datetime import datetime, timezone
from backend.core.timezone_manager import timezone_manager, SUPPORTED_TIMEZONES


def test_timezone_manager_supported_profiles():
    """Validates that all essential trading timezones are registered."""
    assert "UTC+7" in SUPPORTED_TIMEZONES
    assert "UTC" in SUPPORTED_TIMEZONES
    assert "US/Eastern" in SUPPORTED_TIMEZONES
    assert "Broker" in SUPPORTED_TIMEZONES


def test_mt5_broker_offset_normalization():
    """Validates broker server offset compensation."""
    offset = timezone_manager.get_broker_offset()
    assert isinstance(offset, int)
    assert offset % 3600 == 0  # Must be exact hour increments (e.g. 7200 for EET UTC+2)


def test_chart_and_calendar_time_alignment():
    """
    Validates that a candle from MT5 and an economic event from calendar
    occurring at the same UTC instant display identical strings across all timezones.
    """
    # Suppose an event occurs at 12:30:00 UTC
    utc_epoch = 1792499400.0  # 12:30:00 UTC
    broker_offset = timezone_manager.get_broker_offset()
    mt5_bar_time = int(utc_epoch)

    for tz_key in ["UTC+7", "UTC", "US/Eastern", "Broker"]:
        timezone_manager.set_active_timezone(tz_key)
        candle_str = timezone_manager.format_mt5_ts(mt5_bar_time, "%H:%M")
        calendar_str = timezone_manager.format_utc_ts(utc_epoch, "%H:%M")
        assert candle_str == calendar_str, f"Mismatch in {tz_key}: {candle_str} vs {calendar_str}"

    # Restore default UTC+7
    timezone_manager.set_active_timezone("UTC+7")
    assert timezone_manager.active_key == "UTC+7"
    assert timezone_manager.short_label == "UTC+7"
    assert timezone_manager.cal_header == "TIME (VN)"


def test_calendar_timezone_listener_dispatch():
    """Validates that listeners are notified when timezone changes."""
    dispatched = []

    def mock_listener(tz_key):
        dispatched.append(tz_key)

    timezone_manager.add_listener(mock_listener)
    timezone_manager.set_active_timezone("UTC")
    assert "UTC" in dispatched

    timezone_manager.set_active_timezone("UTC+7")
    assert "UTC+7" in dispatched

    timezone_manager.remove_listener(mock_listener)
