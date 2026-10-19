import pytest
from backend.infrastructure.brokers.mt5_safe import mt5


@pytest.fixture(autouse=True)
def isolate_mt5_environment():
    """Ensures MT5 connection state does not leak across test modules and boundaries."""
    yield
    try:
        mt5.shutdown()
    except Exception:
        pass
