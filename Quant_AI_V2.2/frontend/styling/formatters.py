"""
Quant Terminal V2.2 - Institutional Financial Formatter Engine
Centralized, strictly typed formatting utilities for financial metrics,
currency, percentages, pips, volumes, and timestamps.
Guarantees consistent notation (e.g. -$450.00, NEVER $-450) across all UI tabs.
"""

from datetime import datetime
from typing import Union


def fmt_currency(
    value: Union[int, float, None],
    decimals: int = 2,
    sign: bool = False,
    compact: bool = False,
) -> str:
    """
    Format a monetary value in USD standard.
    Examples:
        fmt_currency(-450) -> "-$450.00"
        fmt_currency(1250.5, sign=True) -> "+$1,250.50"
        fmt_currency(110000, compact=True) -> "$110k"
        fmt_currency(-5000, compact=True) -> "-$5k"
    """
    if value is None:
        return "$0.00"

    try:
        val = float(value)
    except (ValueError, TypeError):
        return "$0.00"

    is_neg = val < 0
    abs_val = abs(val)

    if compact:
        if abs_val >= 1_000_000:
            formatted_num = f"{abs_val / 1_000_000:.1f}M"
        elif abs_val >= 1_000:
            formatted_num = f"{abs_val / 1_000:.0f}k"
        else:
            formatted_num = f"{abs_val:,.0f}"
    else:
        formatted_num = f"{abs_val:,.{decimals}f}"

    if is_neg:
        return f"-${formatted_num}"
    elif sign and val > 0:
        return f"+${formatted_num}"
    else:
        return f"${formatted_num}"


def fmt_percent(
    value: Union[int, float, None],
    decimals: int = 2,
    sign: bool = False,
) -> str:
    """
    Format a percentage value.
    Examples:
        fmt_percent(12.45) -> "12.45%"
        fmt_percent(12.45, sign=True) -> "+12.45%"
        fmt_percent(-3.2) -> "-3.20%"
    """
    if value is None:
        return "0.00%"

    try:
        val = float(value)
    except (ValueError, TypeError):
        return "0.00%"

    is_neg = val < 0
    abs_val = abs(val)
    formatted = f"{abs_val:.{decimals}f}%"

    if is_neg:
        return f"-{formatted}"
    elif sign and val > 0:
        return f"+{formatted}"
    else:
        return formatted


def fmt_pips(
    value: Union[int, float, None],
    decimals: int = 1,
    sign: bool = False,
    include_unit: bool = True,
) -> str:
    """
    Format pips value.
    Examples:
        fmt_pips(45.2, sign=True) -> "+45.2 pips"
        fmt_pips(-12.0) -> "-12.0 pips"
    """
    if value is None:
        return "0.0 pips" if include_unit else "0.0"

    try:
        val = float(value)
    except (ValueError, TypeError):
        return "0.0 pips" if include_unit else "0.0"

    unit = " pips" if include_unit else ""
    if val < 0:
        return f"-{abs(val):.{decimals}f}{unit}"
    elif sign and val > 0:
        return f"+{val:.{decimals}f}{unit}"
    else:
        return f"{val:.{decimals}f}{unit}"


def fmt_volume(value: Union[int, float, None], decimals: int = 2) -> str:
    """
    Format trading lot volume.
    Example: fmt_volume(0.5) -> "0.50 lots"
    """
    if value is None:
        return "0.00 lots"
    try:
        val = float(value)
        return f"{val:.{decimals}f} lots"
    except (ValueError, TypeError):
        return "0.00 lots"


def fmt_number(
    value: Union[int, float, None],
    decimals: int = 0,
    compact: bool = False,
) -> str:
    """
    Format raw numbers with thousands separator or compact notation.
    """
    if value is None:
        return "0"
    try:
        val = float(value)
    except (ValueError, TypeError):
        return "0"

    if compact:
        abs_val = abs(val)
        prefix = "-" if val < 0 else ""
        if abs_val >= 1_000_000:
            return f"{prefix}{abs_val / 1_000_000:.1f}M"
        elif abs_val >= 1_000:
            return f"{prefix}{abs_val / 1_000:.0f}k"
        else:
            return f"{prefix}{abs_val:.0f}"

    if decimals == 0:
        return f"{int(round(val)):,}"
    return f"{val:,.{decimals}f}"


def fmt_timestamp(
    ts: Union[int, float, datetime, None],
    fmt: str = "%Y-%m-%d %H:%M:%S",
) -> str:
    """
    Convert a timestamp (epoch seconds or datetime object) into standard formatted string.
    """
    if ts is None:
        return "--:--:--"
    if isinstance(ts, (int, float)):
        try:
            dt = datetime.fromtimestamp(ts)
            return dt.strftime(fmt)
        except Exception:
            return "--:--:--"
    elif isinstance(ts, datetime):
        return ts.strftime(fmt)
    return str(ts)
