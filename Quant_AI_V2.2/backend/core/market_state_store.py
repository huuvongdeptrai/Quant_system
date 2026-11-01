"""
Market State Store - Thread-Safe Decoupled Domain State Container (Pillar 3).
Complies with Sierra Chart DTC Architecture and Bloomberg AIM standards.
Provides an isolated, thread-safe, decoupled state container for multi-asset
market structure, checklists, active order proposals, and live broker positions.
Decouples domain trading state completely from PyQt QMainWindow objects.
"""

import copy
import time
import threading
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable, Tuple
from loguru import logger


@dataclass
class SymbolState:
    """Thread-safe state snapshot for a single financial instrument."""
    symbol: str
    has_signal: bool = False
    signal_type: str = "HOLD"
    entry: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    risk_dlr: Optional[float] = None
    reward_dlr: Optional[float] = None
    risk_pct: Optional[float] = None
    rr_ratio: Optional[float] = None
    lot: Optional[float] = None
    is_live_position: bool = False
    live_ticket: Optional[int] = None
    live_volume: Optional[float] = None
    live_profit: float = 0.0
    is_pending_order: bool = False
    pending_ticket: Optional[int] = None
    model_name: Optional[str] = None
    grade: Optional[str] = None
    confidence: Optional[str] = None
    status: str = "SCANNING_STANDBY"
    chk1: Optional[str] = None
    chk2: Optional[str] = None
    chk3: Optional[str] = None
    checklist: Optional[List[Any]] = None
    digits: Optional[int] = None
    exec_mode: str = "MANUAL"
    is_bot_active: bool = False
    market_structure: Optional[Any] = None
    last_updated: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Converts state to plain dictionary matching legacy active_signals_by_symbol schema."""
        return {
            "sym": self.symbol,
            "has_signal": self.has_signal,
            "signal_type": self.signal_type,
            "entry": self.entry,
            "sl": self.sl,
            "tp": self.tp,
            "risk_dlr": self.risk_dlr,
            "reward_dlr": self.reward_dlr,
            "risk_pct": self.risk_pct,
            "rr_ratio": self.rr_ratio,
            "lot": self.lot,
            "is_live_position": self.is_live_position,
            "live_ticket": self.live_ticket,
            "live_volume": self.live_volume,
            "live_profit": self.live_profit,
            "is_pending_order": self.is_pending_order,
            "pending_ticket": self.pending_ticket,
            "model_name": self.model_name,
            "grade": self.grade,
            "confidence": self.confidence,
            "status": self.status,
            "chk1": self.chk1,
            "chk2": self.chk2,
            "chk3": self.chk3,
            "checklist": self.checklist,
            "digits": self.digits,
            "exec_mode": self.exec_mode,
            "is_bot_active": self.is_bot_active,
            "market_structure": self.market_structure,
            "last_updated": self.last_updated,
        }


class MarketStateStore:
    """
    Singleton Thread-Safe Domain State Store.
    Manages symbol states across AI analyzers, bot orchestrators, and GUI controllers.
    """
    _instance: Optional["MarketStateStore"] = None
    _init_lock = threading.Lock()

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._lock = threading.RLock()
        self._states: Dict[str, SymbolState] = {}
        self._listeners: List[Callable[[str, SymbolState], None]] = []
        self._initialized = True

    @classmethod
    def get_instance(cls) -> "MarketStateStore":
        """Retrieves or creates the thread-safe singleton store instance."""
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get_state(self, symbol: str) -> Optional[SymbolState]:
        """Thread-safe retrieval of a SymbolState snapshot."""
        clean = str(symbol or "").split("\n")[0].strip().upper()
        with self._lock:
            return copy.deepcopy(self._states.get(clean))

    def get_state_dict(self, symbol: str) -> Dict[str, Any]:
        """Retrieves state dictionary compatible with legacy UI active_signals_by_symbol."""
        clean = str(symbol or "").split("\n")[0].strip().upper()
        with self._lock:
            st = self._states.get(clean)
            return copy.deepcopy(st.to_dict()) if st else {"sym": clean, "has_signal": False}

    def update_state(self, symbol: str, **kwargs) -> SymbolState:
        """
        Atomically merges incoming telemetry into symbol state.
        Preserves existing valid fields when incoming kwargs are None.
        """
        clean = str(symbol or "").split("\n")[0].strip().upper()
        with self._lock:
            prev = self._states.get(clean)

            # Defensive merging against clobbering with None
            has_signal = kwargs.get("has_signal", prev.has_signal if prev else False)
            sig_type = kwargs.get("signal_type") or (prev.signal_type if prev else "HOLD")
            entry = kwargs["entry"] if "entry" in kwargs else (prev.entry if prev else None)
            sl = kwargs["sl"] if "sl" in kwargs else (prev.sl if prev else None)
            tp = kwargs["tp"] if "tp" in kwargs else (prev.tp if prev else None)
            risk_dlr = kwargs.get("risk_dlr") if kwargs.get("risk_dlr") is not None else (prev.risk_dlr if prev else None)
            reward_dlr = kwargs.get("reward_dlr") if kwargs.get("reward_dlr") is not None else (prev.reward_dlr if prev else None)
            risk_pct = kwargs.get("risk_pct") if kwargs.get("risk_pct") is not None else (prev.risk_pct if prev else None)
            rr_ratio = kwargs.get("rr_ratio") if kwargs.get("rr_ratio") is not None else (prev.rr_ratio if prev else None)
            lot = kwargs["lot"] if "lot" in kwargs else (prev.lot if prev else None)
            if lot is None and kwargs.get("calc_lot") is not None:
                lot = kwargs.get("calc_lot")

            is_live = kwargs.get("is_live_position", prev.is_live_position if prev else False)
            live_ticket = kwargs["live_ticket"] if "live_ticket" in kwargs else (prev.live_ticket if prev else None)
            live_volume = kwargs["live_volume"] if "live_volume" in kwargs else (prev.live_volume if prev else None)
            live_profit = kwargs.get("live_profit", prev.live_profit if prev else 0.0)

            is_pending = kwargs.get("is_pending_order", prev.is_pending_order if prev else False)
            pending_ticket = kwargs["pending_ticket"] if "pending_ticket" in kwargs else (prev.pending_ticket if prev else None)

            model_name = kwargs.get("model_name") or (prev.model_name if prev else None)
            grade = kwargs.get("grade") or (prev.grade if prev else ("STATUS: STANDBY" if not has_signal else None))
            confidence = kwargs.get("confidence") or (prev.confidence if prev else None)

            status = kwargs.get("status")
            if not status or status == "WAITING OPERATOR APPROVAL":
                if not has_signal:
                    status = (prev.status if prev and prev.status != "WAITING OPERATOR APPROVAL" else "SCANNING_STANDBY")
                else:
                    status = status or (prev.status if prev else "WAITING OPERATOR APPROVAL")

            chk1 = kwargs.get("chk1") if kwargs.get("chk1") is not None else (prev.chk1 if prev else None)
            chk2 = kwargs.get("chk2") if kwargs.get("chk2") is not None else (prev.chk2 if prev else None)
            chk3 = kwargs.get("chk3") if kwargs.get("chk3") is not None else (prev.chk3 if prev else None)
            checklist = kwargs.get("checklist") if kwargs.get("checklist") is not None else (prev.checklist if prev else None)
            digits = kwargs.get("digits") if kwargs.get("digits") is not None else (prev.digits if prev else None)
            exec_mode = kwargs.get("exec_mode") or (prev.exec_mode if prev else "MANUAL")
            is_bot_active = kwargs.get("is_bot_active", prev.is_bot_active if prev else False)
            market_struct = kwargs.get("market_structure") if kwargs.get("market_structure") is not None else (prev.market_structure if prev else None)

            new_state = SymbolState(
                symbol=clean,
                has_signal=bool(has_signal),
                signal_type=str(sig_type),
                entry=entry,
                sl=sl,
                tp=tp,
                risk_dlr=risk_dlr,
                reward_dlr=reward_dlr,
                risk_pct=risk_pct,
                rr_ratio=rr_ratio,
                lot=lot,
                is_live_position=bool(is_live),
                live_ticket=live_ticket,
                live_volume=live_volume,
                live_profit=float(live_profit),
                is_pending_order=bool(is_pending),
                pending_ticket=pending_ticket,
                model_name=model_name,
                grade=grade,
                confidence=confidence,
                status=str(status),
                chk1=chk1,
                chk2=chk2,
                chk3=chk3,
                checklist=checklist,
                digits=digits,
                exec_mode=exec_mode,
                is_bot_active=bool(is_bot_active),
                market_structure=market_struct,
                last_updated=time.time(),
            )
            self._states[clean] = new_state
            listeners_snapshot = list(self._listeners)

        # Notify outside lock to prevent deadlock in observer callbacks
        for listener in listeners_snapshot:
            try:
                listener(clean, new_state)
            except Exception as e_listener:
                logger.debug(f"[MarketStateStore] Listener error for {clean}: {e_listener}")

        return new_state

    def subscribe(self, callback: Callable[[str, SymbolState], None]) -> Callable[[], None]:
        """Subscribes an observer callback. Returns unsubscribe callable."""
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

        def unsubscribe():
            with self._lock:
                if callback in self._listeners:
                    self._listeners.remove(callback)

        return unsubscribe

    def get_all_states(self) -> Dict[str, SymbolState]:
        """Thread-safe snapshot of all instrument states."""
        with self._lock:
            return copy.deepcopy(self._states)

    def clear_symbol(self, symbol: str) -> None:
        """Removes a symbol from the store."""
        clean = str(symbol or "").split("\n")[0].strip().upper()
        with self._lock:
            self._states.pop(clean, None)

    def reset(self) -> None:
        """Resets the store (primarily for unit test isolation)."""
        with self._lock:
            self._states.clear()
            self._listeners.clear()
