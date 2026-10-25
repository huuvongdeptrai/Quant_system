"""
Unit tests for MarketStateStore - Isolated Domain State Container (Pillar 3).
Validates thread-safety, singleton access, defensive state merging,
observer subscriptions, and decoupling from PyQt widgets.
"""

import threading
import time
import pytest
from backend.core.market_state_store import MarketStateStore, SymbolState


@pytest.fixture(autouse=True)
def clean_store():
    store = MarketStateStore.get_instance()
    store.reset()
    yield store
    store.reset()


def test_singleton_instance():
    """Verifies that MarketStateStore is a strict singleton."""
    s1 = MarketStateStore.get_instance()
    s2 = MarketStateStore.get_instance()
    assert s1 is s2


def test_update_and_defensive_merging():
    """Verifies that subsequent partial updates do NOT clobber previous attributes with None."""
    store = MarketStateStore.get_instance()

    # Initial standby update with trend structure
    st1 = store.update_state(
        "XAUUSD",
        has_signal=False,
        signal_type="HOLD",
        model_name="ICT Zones Pro v4.2",
        grade="STATUS: STANDBY",
        chk1="Bullish Bias Confirmed",
        chk2="Asian High Swept",
        chk3="Awaiting Mitigation",
        status="SCANNING_STANDBY",
        digits=2,
    )

    assert st1.symbol == "XAUUSD"
    assert st1.chk1 == "Bullish Bias Confirmed"
    assert st1.grade == "STATUS: STANDBY"

    # Ambient UI tick or drawer refresh with None values
    st2 = store.update_state(
        "XAUUSD",
        has_signal=False,
        model_name=None,
        chk1=None,
        grade=None,
    )

    # Must preserve previous values!
    assert st2.chk1 == "Bullish Bias Confirmed"
    assert st2.chk2 == "Asian High Swept"
    assert st2.grade == "STATUS: STANDBY"
    assert st2.model_name == "ICT Zones Pro v4.2"
    assert st2.digits == 2


def test_active_signal_state_conversion():
    """Verifies that active trade signals serialize to legacy dictionary cleanly."""
    store = MarketStateStore.get_instance()

    st = store.update_state(
        "BTCUSD",
        has_signal=True,
        signal_type="BUY",
        entry=67450.0,
        sl=66800.0,
        tp=68750.0,
        risk_dlr=100.0,
        reward_dlr=200.0,
        rr_ratio=2.0,
        lot=0.15,
        model_name="ICT Zones Pro v4.2",
        grade="PNL: +$45.00",
        is_live_position=True,
        live_ticket=123456,
        live_volume=0.15,
        live_profit=45.0,
    )

    d = st.to_dict()
    assert d["sym"] == "BTCUSD"
    assert d["has_signal"] is True
    assert d["signal_type"] == "BUY"
    assert d["entry"] == 67450.0
    assert d["sl"] == 66800.0
    assert d["tp"] == 68750.0
    assert d["is_live_position"] is True
    assert d["live_ticket"] == 123456
    assert d["live_profit"] == 45.0


def test_observer_pattern_subscription():
    """Verifies that subscriber callbacks are notified when symbol state mutates."""
    store = MarketStateStore.get_instance()
    notifications = []

    def on_state_changed(sym, state):
        notifications.append((sym, state.has_signal, state.signal_type))

    unsub = store.subscribe(on_state_changed)

    store.update_state("ETHUSD", has_signal=False, signal_type="HOLD")
    store.update_state("ETHUSD", has_signal=True, signal_type="BUY", entry=3450.0)

    assert len(notifications) == 2
    assert notifications[0] == ("ETHUSD", False, "HOLD")
    assert notifications[1] == ("ETHUSD", True, "BUY")

    # Unsubscribe and verify no more notifications
    unsub()
    store.update_state("ETHUSD", has_signal=False, signal_type="HOLD")
    assert len(notifications) == 2


def test_concurrent_multithreaded_updates():
    """Verifies thread-safety under heavy concurrent updates from multiple worker threads."""
    store = MarketStateStore.get_instance()
    threads = []
    errors = []

    def worker_loop(thread_id, sym):
        try:
            for i in range(50):
                store.update_state(
                    sym,
                    has_signal=(i % 2 == 0),
                    signal_type="BUY" if (i % 2 == 0) else "SELL",
                    entry=1000.0 + i + thread_id,
                    live_profit=float(i * 10),
                )
                time.sleep(0.001)
        except Exception as e:
            errors.append(e)

    for tid in range(5):
        t1 = threading.Thread(target=worker_loop, args=(tid, "XAUUSD"))
        t2 = threading.Thread(target=worker_loop, args=(tid, "BTCUSD"))
        threads.extend([t1, t2])
        t1.start()
        t2.start()

    for t in threads:
        t.join()

    assert len(errors) == 0
    assert store.get_state("XAUUSD") is not None
    assert store.get_state("BTCUSD") is not None
