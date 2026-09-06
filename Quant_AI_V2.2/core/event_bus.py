from PySide6.QtCore import QObject, Signal

class QuantEventBus(QObject):
    """
    Trạm điều phối Sự kiện trung tâm (Event Bus).
    Thiết kế theo chuẩn Singleton để các module giao tiếp lỏng (Loose Coupling).
    """
    market_tick = Signal(str, float, float) # symbol, bid, ask
    signal_generated = Signal(dict)
    order_executed = Signal(dict)
    log_event = Signal(str, str, str, str) # time, level, msg, color
    chart_update_requested = Signal(str) # symbol

event_bus = QuantEventBus()