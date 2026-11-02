"""
Engine Configuration Module - Immutable Institutional Parameter Schema.
Complies with QuantConnect LEAN and CFA/FRM Risk Management standards.
Provides strict validation, immutable dataclasses, and fail-safe defaults
to decouple the execution engine completely from PyQt GUI widgets.
"""

import math
from dataclasses import dataclass
from enum import Enum
from typing import Tuple, List, Optional, Any, Dict
from loguru import logger
from backend.infrastructure.brokers.mt5_safe import mt5

TF_MAP = {
    1: mt5.TIMEFRAME_M1,
    5: mt5.TIMEFRAME_M5,
    15: mt5.TIMEFRAME_M15,
    30: mt5.TIMEFRAME_M30,
    60: mt5.TIMEFRAME_H1,
    240: mt5.TIMEFRAME_H4,
    1440: mt5.TIMEFRAME_D1,
    10080: getattr(mt5, "TIMEFRAME_W1", 32769),
    43200: getattr(mt5, "TIMEFRAME_MN1", 49153),
}

TF_NAMES = {
    mt5.TIMEFRAME_M1: "M1",
    mt5.TIMEFRAME_M5: "M5",
    mt5.TIMEFRAME_M15: "M15",
    mt5.TIMEFRAME_M30: "M30",
    mt5.TIMEFRAME_H1: "H1",
    mt5.TIMEFRAME_H4: "H4",
    mt5.TIMEFRAME_D1: "D1",
    getattr(mt5, "TIMEFRAME_W1", 32769): "W1",
    getattr(mt5, "TIMEFRAME_MN1", 49153): "MN1",
}


def resolve_mt5_timeframe(val: Any) -> int:
    """Safely converts an integer, string or MT5 timeframe constant to MT5 constant."""
    if val is None:
        return mt5.TIMEFRAME_M15
    try:
        int_val = int(val)
        if int_val in TF_MAP:
            return TF_MAP[int_val]
        if int_val in TF_NAMES:
            return int_val
    except (ValueError, TypeError):
        pass
    s_val = str(val).strip().upper()
    for tf_const, name in TF_NAMES.items():
        if s_val == name.upper():
            return tf_const
    return mt5.TIMEFRAME_M15


def get_timeframe_name(tf_val: int) -> str:
    """Returns human-readable name of MT5 timeframe constant."""
    return TF_NAMES.get(tf_val, "M15")


class ExecutionMode(str, Enum):
    FULL_AUTO = "FULL-AUTO"
    SEMI_AUTO = "SEMI-AUTO"
    MANUAL = "MANUAL"

    @classmethod
    def from_str(cls, val: Any) -> "ExecutionMode":
        if isinstance(val, cls):
            return val
        s = str(val or "").strip().upper()
        if "FULL" in s:
            return cls.FULL_AUTO
        if "MANUAL" in s:
            return cls.MANUAL
        return cls.SEMI_AUTO


class TradeMode(str, Enum):
    AUTO = "AUTO"
    LONG_ONLY = "LONG_ONLY"
    SHORT_ONLY = "SHORT_ONLY"

    @classmethod
    def from_str(cls, val: Any) -> "TradeMode":
        if isinstance(val, cls):
            return val
        s = str(val or "").strip().upper()
        if "LONG" in s or "BUY" in s:
            return cls.LONG_ONLY
        if "SHORT" in s or "SELL" in s:
            return cls.SHORT_ONLY
        return cls.AUTO


class GateMode(str, Enum):
    FULL = "FULL"
    TECH_ONLY = "TECH_ONLY"
    BYPASS = "BYPASS"

    @classmethod
    def from_str(cls, val: Any) -> "GateMode":
        if isinstance(val, cls):
            return val
        s = str(val or "").strip().upper()
        if "TECH" in s:
            return cls.TECH_ONLY
        if "BYPASS" in s or "RAW" in s or s == "FREE":
            return cls.BYPASS
        return cls.FULL


@dataclass(frozen=True)
class BotRunConfig:
    """
    Immutable, validated quantitative engine configuration.
    Guarantees no None values can leak into trade execution pipeline.
    """
    symbols: Tuple[str, ...] = ("XAUUSD",)
    timeframe: int = mt5.TIMEFRAME_M15
    strategy_id: str = "builtin_ict_pro"
    execution_mode: ExecutionMode = ExecutionMode.SEMI_AUTO
    trade_mode: TradeMode = TradeMode.AUTO
    gate_mode: GateMode = GateMode.FULL
    ai_model_name: str = "qwen2.5"

    # Risk and Money Management
    risk_per_trade: float = 1.0
    max_daily_loss: float = 500.0
    max_drawdown: float = 5.0
    max_losing_streak: int = 3
    max_open_trades: int = 5
    max_spread: int = 25
    slippage: int = 20

    # Active Defense & Trailing
    close_friday: bool = True
    trailing_pips: int = 0
    breakeven_pips: int = 0
    enable_trailing_stop: bool = False

    # News and Event Defense
    news_filter_enabled: bool = True
    news_pause_mins: int = 30
    news_defense_enabled: bool = True
    defense_window_mins: int = 15
    news_defense_be_r: float = 1.5
    enable_meta_labeling: bool = True

    # Session Controls
    allowed_sessions: Tuple[str, ...] = ("ASIAN", "LONDON", "NY")

    def __post_init__(self):
        if not math.isfinite(self.risk_per_trade) or not 0 < self.risk_per_trade <= 100:
            raise ValueError('risk_per_trade must be finite and in (0,100]')
        for name in ('max_daily_loss','max_drawdown','max_losing_streak','max_spread','slippage',
                     'trailing_pips','breakeven_pips','news_pause_mins','defense_window_mins'):
            if not math.isfinite(getattr(self,name)) or getattr(self,name)<0:
                raise ValueError(f'{name} must be finite and nonnegative')
        if self.max_open_trades < 1:
            raise ValueError('max_open_trades must be positive')

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BotRunConfig":
        """Builds a validated BotRunConfig from arbitrary dictionary with fallback defaults."""
        if not isinstance(data, dict):
            data = {}

        raw_syms = data.get("symbols", ("XAUUSD",))
        if isinstance(raw_syms, list):
            syms_tuple = tuple(str(s).strip() for s in raw_syms if s)
        elif isinstance(raw_syms, str):
            syms_tuple = tuple(s.strip() for s in raw_syms.split(",") if s.strip())
        elif isinstance(raw_syms, tuple):
            syms_tuple = raw_syms
        else:
            syms_tuple = ("XAUUSD",)
        if not syms_tuple:
            syms_tuple = ("XAUUSD",)

        # Timeframe resolution
        raw_tf = data.get("timeframe", mt5.TIMEFRAME_M15)
        tf_resolved = resolve_mt5_timeframe(raw_tf)

        # Enums
        exec_m = ExecutionMode.from_str(data.get("execution_mode"))
        trade_m = TradeMode.from_str(data.get("trade_mode") or data.get("market_bias"))
        gate_m = GateMode.from_str(data.get("gate_mode") or data.get("decision_gate_mode"))

        def _to_float(v, default):
            try:
                result=float(v) if v is not None else default
                return result if math.isfinite(result) else default
            except (ValueError, TypeError):
                return default

        def _to_int(v, default):
            try:
                return int(v) if v is not None else default
            except (ValueError, TypeError):
                return default

        def _to_bool(value,default):
            if value is None:
                return default
            if isinstance(value,str):
                if value.strip().lower() in ('false','0','no','off'):
                    return False
                if value.strip().lower() in ('true','1','yes','on'):
                    return True
                return default
            return bool(value)

        # Sessions
        raw_sessions = data.get("allowed_sessions")
        if isinstance(raw_sessions, (list, tuple)):
            sessions_tuple = tuple(str(s).upper() for s in raw_sessions if str(s).strip())
        elif any(k in data for k in ('session_asian','session_london','session_ny')):
            sessions_tuple = tuple(name for name,key in (
                ('ASIAN','session_asian'),('LONDON','session_london'),('NY','session_ny'))
                if _to_bool(data.get(key),True))
        else:
            sessions_tuple = ("ASIAN", "LONDON", "NY")

        return cls(
            symbols=syms_tuple,
            timeframe=tf_resolved,
            strategy_id=str(data.get("strategy_id") or data.get("strategy") or "builtin_ict_pro"),
            execution_mode=exec_m,
            trade_mode=trade_m,
            gate_mode=gate_m,
            ai_model_name=str(data.get("ai_model_name") or "qwen2.5"),
            risk_per_trade=_to_float(data.get("risk_per_trade"), 1.0),
            max_daily_loss=_to_float(data.get("max_daily_loss"), 500.0),
            max_drawdown=_to_float(data.get("max_drawdown"), 5.0),
            max_losing_streak=_to_int(data.get("max_losing_streak"), 3),
            max_open_trades=_to_int(data.get("max_open_trades"), 5),
            max_spread=_to_int(data.get("max_spread"), 25),
            slippage=_to_int(data.get("slippage"), 20),
            close_friday=_to_bool(data.get("close_friday"), True),
            trailing_pips=_to_int(data.get("trailing_pips"), 0),
            breakeven_pips=_to_int(data.get("breakeven_pips"), 0),
            enable_trailing_stop=_to_bool(data.get("enable_trailing_stop"), False),
            news_filter_enabled=_to_bool(data.get("news_filter_enabled"), True),
            news_pause_mins=_to_int(data.get("news_pause_mins"), 30),
            news_defense_enabled=_to_bool(data.get("news_defense_enabled"), True),
            defense_window_mins=_to_int(data.get("defense_window_mins"), 15),
            news_defense_be_r=_to_float(data.get("news_defense_be_r"), 1.5),
            enable_meta_labeling=_to_bool(data.get("enable_meta_labeling"), True),
            allowed_sessions=sessions_tuple,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts to plain dictionary representation."""
        return {
            "symbols": list(self.symbols),
            "timeframe": self.timeframe,
            "strategy_id": self.strategy_id,
            "execution_mode": self.execution_mode.value,
            "trade_mode": self.trade_mode.value,
            "gate_mode": self.gate_mode.value,
            "ai_model_name": self.ai_model_name,
            "risk_per_trade": self.risk_per_trade,
            "max_daily_loss": self.max_daily_loss,
            "max_drawdown": self.max_drawdown,
            "max_losing_streak": self.max_losing_streak,
            "max_open_trades": self.max_open_trades,
            "max_spread": self.max_spread,
            "slippage": self.slippage,
            "close_friday": self.close_friday,
            "trailing_pips": self.trailing_pips,
            "breakeven_pips": self.breakeven_pips,
            "enable_trailing_stop": self.enable_trailing_stop,
            "news_filter_enabled": self.news_filter_enabled,
            "news_pause_mins": self.news_pause_mins,
            "news_defense_enabled": self.news_defense_enabled,
            "defense_window_mins": self.defense_window_mins,
            "news_defense_be_r": self.news_defense_be_r,
            "enable_meta_labeling": self.enable_meta_labeling,
            "allowed_sessions": list(self.allowed_sessions),
        }
