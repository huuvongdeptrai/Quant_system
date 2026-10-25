# -*- coding: utf-8 -*-
"""
Macro Context Bus - Centralized Multi-Asset State Service.
Compliant with QuantConnect LEAN Universe & Bloomberg CRD Pre-Trade Compliance Models.
Provides:
1. Slow-cycle (~60s) background profile generation for all watchlist assets.
2. Instant O(1) in-memory profile queries without MT5 API locking.
3. Semi-auto human-in-the-loop control flags: manual_override_lock & force_defense_active.
4. Autonomous In-Trade Position Defense triggering at T-15m before High-Impact events.
"""
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from loguru import logger

from backend.infrastructure.data_providers.asset_registry import AssetRegistry
from backend.core.event_risk_engine import EventRiskEngine
from backend.infrastructure.data_providers.macro.macro_regime import MacroRegimeEngine


@dataclass
class SymbolMacroProfile:
    """Standardized macro and risk profile for an individual financial asset."""
    symbol: str
    asset_class: str = "FOREX"
    directional_bias: str = "NEUTRAL"      # BULLISH, BEARISH, NEUTRAL
    macro_regime: str = "NEUTRAL"          # Overall macro regime stance
    news_blackout: bool = False            # True if within +-15m of High-Impact event
    event_risk_level: str = "LOW"          # LOW, MEDIUM, HIGH
    next_event_title: str = ""             # Title of upcoming high-impact event
    seconds_to_event: float = 999999.0     # Seconds until event
    manual_override_lock: bool = False     # Human permission to bypass lockout
    force_defense_active: bool = False     # Human manual trigger for immediate defense
    badge_text: str = "NEUT"               # Compact label for Watchlist column
    badge_color: str = "#64748b"           # Hex color for UI
    timestamp: float = field(default_factory=time.time)

    @property
    def is_lockout_active(self) -> bool:
        """Lockout is active only if news blackout is on AND human has not overridden."""
        return self.news_blackout and not self.manual_override_lock


class MacroContextBus:
    """
    Centralized Thread-Safe Macro and Risk Distribution Bus (Singleton).
    """
    _instance: Optional["MacroContextBus"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._profiles: Dict[str, SymbolMacroProfile] = {}
        self._manual_override_lock: bool = False
        self._force_defense_active: bool = False
        self._last_cycle_ts: float = 0.0
        self._cycle_interval_sec: int = 60
        self._event_risk_engine = EventRiskEngine()
        self._macro_regime = MacroRegimeEngine()
        self._data_lock = threading.Lock()
        self._pending_symbols: set = set()

    @classmethod
    def get_instance(cls) -> "MacroContextBus":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    # ---------------------------------------------------------
    # Semi-Auto Human-In-The-Loop Controls
    # ---------------------------------------------------------
    def set_manual_override(self, enabled: bool) -> None:
        """Sets user manual override flag to bypass news blackout lockouts."""
        with self._data_lock:
            self._manual_override_lock = enabled
            for sym, prof in self._profiles.items():
                prof.manual_override_lock = enabled
                self._update_badge(prof)
        logger.info(f"[MacroContextBus] Manual Override Lock set to: {enabled}")

    def get_manual_override(self) -> bool:
        with self._data_lock:
            return self._manual_override_lock

    def trigger_force_defense(self) -> List[Dict[str, Any]]:
        """Immediately executes pre-news active position defense on MT5."""
        logger.info("[MacroContextBus] FORCE DEFENSE triggered by human operator.")
        with self._data_lock:
            self._force_defense_active = True
        try:
            results = self._event_risk_engine.evaluate_pre_news_defense()
            return results
        except Exception as e:
            logger.warning(f"[MacroContextBus] Error executing force defense: {e}")
            return []

    # ---------------------------------------------------------
    # Badge Formatting Helper
    # ---------------------------------------------------------
    def _update_badge(self, profile: SymbolMacroProfile) -> None:
        """Calculates ultra-compact label and color for Watchlist display."""
        if profile.is_lockout_active:
            profile.badge_text = "LOCK"
            profile.badge_color = "#ef4444"
        elif profile.news_blackout and profile.manual_override_lock:
            profile.badge_text = "OVRD"
            profile.badge_color = "#f59e0b"
        elif 0 < profile.seconds_to_event <= 1800:  # T-30m countdown
            mins = max(1, int(profile.seconds_to_event / 60))
            profile.badge_text = f"T-{mins}m"
            profile.badge_color = "#f59e0b"
        elif profile.directional_bias == "BULLISH":
            profile.badge_text = "BULL"
            profile.badge_color = "#22c55e"
        elif profile.directional_bias == "BEARISH":
            profile.badge_text = "BEAR"
            profile.badge_color = "#ef4444"
        else:
            profile.badge_text = "NEUT"
            profile.badge_color = "#64748b"

    # ---------------------------------------------------------
    # Profile Computation (Slow Cycle)
    # ---------------------------------------------------------
    def refresh_symbol_profile(self, symbol: str) -> SymbolMacroProfile:
        """Computes standardized profile for an individual symbol."""
        clean_sym = symbol.upper().split(".")[0].replace("/", "").strip()
        asset_cls = AssetRegistry.identify(clean_sym).value

        # 1. Macro Bias from Asset Adapter
        try:
            adapter = AssetRegistry.get_adapter(clean_sym)
            bias = adapter.get_macro_bias(clean_sym)
        except Exception as e:
            logger.debug(f"[MacroContextBus] Adapter error for {clean_sym}: {e}")
            bias = "NEUTRAL"

        # 2. Macro Regime stance
        try:
            regime_dict = self._macro_regime.get_current_regime()
            regime_stance = regime_dict.get("bias", "NEUTRAL")
        except Exception:
            regime_stance = "NEUTRAL"

        # 3. News Impact and Upcoming Events from EventRiskEngine
        is_impacted = False
        event_title = ""
        risk_level = "LOW"
        seconds_to_event = 999999.0

        try:
            is_impacted, event_title = self._event_risk_engine.check_news_impact_for_symbol(clean_sym)
            if is_impacted:
                risk_level = "HIGH"

            # Check next upcoming high-impact event for countdown
            self._event_risk_engine.refresh_events_if_needed()
            cache = getattr(self._event_risk_engine, "_news_events_cache", [])
            now_ts = datetime.now(timezone.utc).timestamp()

            for e in cache:
                if e.get("impact", 0) >= 2:
                    c = e.get("country", "")
                    t = e.get("title", "")
                    if self._event_risk_engine.is_symbol_impacted_by_event(clean_sym, c, t):
                        diff_sec = e.get("sort_key", 0) - now_ts
                        # Future event within 24 hours
                        if 0 < diff_sec < seconds_to_event:
                            seconds_to_event = diff_sec
                            if not event_title:
                                event_title = t
        except Exception as e:
            logger.debug(f"[MacroContextBus] Event check error for {clean_sym}: {e}")

        # Construct profile
        prof = SymbolMacroProfile(
            symbol=clean_sym,
            asset_class=asset_cls,
            directional_bias=bias,
            macro_regime=regime_stance,
            news_blackout=is_impacted,
            event_risk_level=risk_level,
            next_event_title=event_title,
            seconds_to_event=seconds_to_event,
            manual_override_lock=self._manual_override_lock,
            force_defense_active=self._force_defense_active,
            timestamp=time.time(),
        )
        self._update_badge(prof)
        return prof

    def refresh_cycle(self, symbols: Optional[List[str]] = None) -> Dict[str, SymbolMacroProfile]:
        """
        Runs slow cycle evaluation across all symbols.
        Also automatically executes In-Trade Position Defense if any upcoming event is in T-15m.
        """
        if not symbols:
            # Default to active symbols from WatchlistStore
            try:
                from frontend.controllers.watchlist.watchlist_store import WatchlistStore
                ws = WatchlistStore()
                symbols = ws.get_saved_symbols_flat()
            except Exception:
                symbols = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "US30", "BTCUSD"]

        updated: Dict[str, SymbolMacroProfile] = {}
        has_t15_event = False

        for sym in symbols:
            prof = self.refresh_symbol_profile(sym)
            updated[prof.symbol] = prof
            if 0 < prof.seconds_to_event <= 900:  # T-15 minutes (900 seconds)
                has_t15_event = True

        with self._data_lock:
            self._profiles.update(updated)
            self._last_cycle_ts = time.time()

        # In-Trade Defense Execution Hook (Autonomous at T-15m)
        if has_t15_event:
            try:
                def_results = self._event_risk_engine.evaluate_pre_news_defense()
                if def_results:
                    logger.info(f"[MacroContextBus] In-Trade Defense secured {len(def_results)} positions at T-15m.")
            except Exception as e:
                logger.warning(f"[MacroContextBus] In-Trade defense error: {e}")

        return self._profiles

    def _trigger_async_refresh(self, clean_sym: str) -> None:
        """Schedules asynchronous profile calculation in background thread without blocking callers."""
        with self._data_lock:
            if clean_sym in self._pending_symbols:
                return
            self._pending_symbols.add(clean_sym)

        def _worker():
            try:
                prof = self.refresh_symbol_profile(clean_sym)
                with self._data_lock:
                    existing = self._profiles.get(clean_sym)
                    if existing is not None:
                        existing.asset_class = prof.asset_class
                        existing.directional_bias = prof.directional_bias
                        existing.macro_regime = prof.macro_regime
                        existing.news_blackout = prof.news_blackout
                        existing.event_risk_level = prof.event_risk_level
                        existing.next_event_title = prof.next_event_title
                        existing.seconds_to_event = prof.seconds_to_event
                        existing.timestamp = prof.timestamp
                        self._update_badge(existing)
                    else:
                        self._profiles[clean_sym] = prof
            except Exception as e:
                logger.debug(f"[MacroContextBus] Background profile compute error for {clean_sym}: {e}")
            finally:
                with self._data_lock:
                    self._pending_symbols.discard(clean_sym)

        t = threading.Thread(target=_worker, name=f"MacroProfileWorker-{clean_sym}", daemon=True)
        t.start()

    def get_profile(self, symbol: str, sync_fallback: bool = False) -> SymbolMacroProfile:
        """Instant O(1) profile lookup from in-memory cache without blocking GUI/callers."""
        clean_sym = symbol.upper().split(".")[0].replace("/", "").strip()
        with self._data_lock:
            prof = self._profiles.get(clean_sym)
            if prof is not None:
                return prof

        if sync_fallback:
            prof = self.refresh_symbol_profile(clean_sym)
            with self._data_lock:
                self._profiles[clean_sym] = prof
            return prof

        try:
            asset_cls = AssetRegistry.identify(clean_sym).value
        except Exception:
            asset_cls = "FOREX"

        default_prof = SymbolMacroProfile(
            symbol=clean_sym,
            asset_class=asset_cls,
            badge_text="NEUT",
            badge_color="#64748b",
            directional_bias="NEUTRAL",
            macro_regime="NEUTRAL",
            news_blackout=False,
            event_risk_level="LOW",
            next_event_title="",
            seconds_to_event=999999.0,
            manual_override_lock=self._manual_override_lock,
            force_defense_active=self._force_defense_active,
            timestamp=time.time(),
        )
        self._update_badge(default_prof)
        with self._data_lock:
            self._profiles[clean_sym] = default_prof

        self._trigger_async_refresh(clean_sym)
        return default_prof

    def check_pre_trade_news_compliance(self, symbol: str) -> Tuple[bool, str, str]:
        """
        Pre-Trade Gate validation specifically for News Defense.
        Returns: (is_passed: bool, status_val: 'PASS' | 'BLOCKED' | 'OVERRIDE', message: str)
        """
        prof = self.get_profile(symbol)
        if not prof.news_blackout:
            return True, "PASS", "News Defense: Clear (No blackout)"

        if prof.manual_override_lock:
            return True, "OVERRIDE", f"News Lockout Bypassed: {prof.next_event_title} (Manual Override Active)"

        return False, "BLOCKED", f"News Defense: Locked ({prof.next_event_title} Blackout ?15m)"

    def get_macro_context(self, symbol: str) -> Dict[str, Any]:
        """
        Returns a standardized dictionary representation of the symbol's macro context,
        ready for strategy ingestion (ICT, Wyckoff, AI Analyzer, etc.).
        """
        prof = self.get_profile(symbol)
        return {
            "symbol": prof.symbol,
            "macro_bias": prof.directional_bias,
            "bias": prof.directional_bias,
            "macro_regime": prof.macro_regime,
            "volatility_risk": prof.event_risk_level,
            "volatility": prof.event_risk_level,
            "news_lockout": prof.is_lockout_active,
            "news_blackout": prof.news_blackout,
            "active_event": prof.next_event_title,
            "next_event_title": prof.next_event_title,
            "seconds_to_event": prof.seconds_to_event,
            "manual_override": prof.manual_override_lock,
            "badge_text": prof.badge_text,
        }
