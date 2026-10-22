"""
Kill Switch Handler - Emergency Liquidation & Algorithm Circuit Breaker.
Provides a 2-step armed click confirmation to prevent accidental flattening,
executes panic liquidations on MT5, halts trading threads, and dispatches alerts.
"""

from loguru import logger
from PySide6.QtCore import QTimer
from backend.infrastructure.brokers.mt5_safe import mt5
from backend.core.event_bus import event_bus
from backend.infrastructure.notifications.telegram_notifier import telegram_notifier

TXT_STANDBY = "BOT: STANDBY"


class KillSwitchHandler:
    """Coordinates the 2-step armed Flatten All button and panic liquidation logic."""

    def __init__(self, window, controller):
        self.window = window
        self.controller = controller
        self._flatten_armed = False
        self._flatten_countdown = 0
        self._flatten_timer = None

    def apply_flatten_btn_style(self):
        """Applies theme-appropriate red styling to the FLATTEN ALL button."""
        btn = getattr(self.controller, "btn_blotter_flatten", None)
        if not btn:
            return
        btn.setFixedHeight(20)
        is_dark = getattr(self.controller, "is_dark_theme", False)
        if is_dark:
            btn.setStyleSheet(
                "QPushButton { background-color: #991b1b; color: #ffffff; border: 1px solid #7f1d1d; "
                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0 8px; margin: 0px; } "
                "QPushButton:hover { background-color: #b91c1c; border-color: #991b1b; }"
            )
        else:
            btn.setStyleSheet(
                "QPushButton { background-color: #dc2626; color: #ffffff; border: 1px solid #cbd5e1; "
                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0 8px; margin: 0px; } "
                "QPushButton:hover { background-color: #b91c1c; border-color: #94a3b8; }"
            )

    def disarm_flatten_button(self):
        """Disarms confirmation state and restores button appearance."""
        self._flatten_armed = False
        self.controller._flatten_armed = False
        if self._flatten_timer and self._flatten_timer.isActive():
            self._flatten_timer.stop()
        btn = getattr(self.controller, "btn_blotter_flatten", None)
        if btn:
            btn.setText("FLATTEN ALL")
            self.apply_flatten_btn_style()

    def on_flatten_timer_tick(self):
        """Countdown timer decrement for armed confirmation."""
        self._flatten_countdown -= 1
        self.controller._flatten_countdown = self._flatten_countdown
        btn = getattr(self.controller, "btn_blotter_flatten", None)
        if not btn:
            return
        if self._flatten_countdown > 0:
            btn.setText(f"CONFIRM FLATTEN ({self._flatten_countdown}s)")
        else:
            self.disarm_flatten_button()

    def handle_kill_switch(self):
        """Emergency Kill-Switch / Flatten All: 2-step armed click confirmation."""
        btn = getattr(self.controller, "btn_blotter_flatten", None)
        if not btn:
            return

        is_armed = getattr(self.controller, "_flatten_armed", self._flatten_armed)
        if not is_armed:
            self._flatten_armed = True
            self.controller._flatten_armed = True
            self._flatten_countdown = 3
            self.controller._flatten_countdown = 3
            btn.setText("CONFIRM FLATTEN (3s)")
            btn.setStyleSheet(
                "QPushButton { background-color: #b91c1c; color: #ffffff; border: 1px solid #475569; "
                "font-family: Consolas, monospace; font-size: 8.5px; font-weight: bold; border-radius: 2px; padding: 0 6px; } "
                "QPushButton:hover { background-color: #dc2626; border-color: #991b1b; }"
            )
            if self._flatten_timer is None:
                self._flatten_timer = QTimer(self.window)
                self._flatten_timer.setInterval(1000)
                self._flatten_timer.timeout.connect(self.on_flatten_timer_tick)
                self.controller._flatten_timer = self._flatten_timer
            self._flatten_timer.start()
            return

        self.disarm_flatten_button()
        btn.setText("LIQUIDATING...")
        btn.setEnabled(False)

        # 1. Panic close all open positions and pending orders on MT5 broker
        results = []
        is_live = mt5.terminal_info() is not None
        if is_live:
            exec_mgr = getattr(self.controller, "exec_mgr", None)
            if exec_mgr and hasattr(exec_mgr, "panic_kill_switch_all"):
                results = exec_mgr.panic_kill_switch_all()
            else:
                logger.warning("[KillSwitchHandler] panic_kill_switch_all not found on exec_mgr")
        else:
            if hasattr(self.controller, "_demo_positions"):
                self.controller._demo_positions = []

        # 2. Halt bot worker and thread
        bot_worker = getattr(self.controller, "bot_worker", None)
        if bot_worker and hasattr(bot_worker, "stop"):
            bot_worker.stop()

        bot_thread = getattr(self.controller, "bot_thread", None)
        if bot_thread and hasattr(bot_thread, "isRunning") and bot_thread.isRunning():
            bot_thread.quit()
            bot_thread.wait(500)

        txt_start = getattr(self.window, "_TXT_START", getattr(self.controller, "_TXT_START", TXT_STANDBY))
        if hasattr(self.controller, "btnStart"):
            self.controller.btnStart.setText(txt_start)
            self.controller.btnStart.setProperty("running", "false")
            self.controller.btnStart.style().unpolish(self.controller.btnStart)
            self.controller.btnStart.style().polish(self.controller.btnStart)

        if hasattr(self.controller, "btn_bot_power"):
            if hasattr(self.controller.btn_bot_power, "set_running"):
                self.controller.btn_bot_power.set_running(False, emit_signal=False)
            else:
                self.controller.btn_bot_power.setProperty("running", "false")

        # 3. Log and Telegram Alert
        detail_msg = f" Liquidated {len(results)} orders." if results else " All active trading halted."
        event_bus.log_event.emit(
            "",
            "ERROR",
            f"EMERGENCY KILL-SWITCH EXECUTED!{detail_msg}",
            "#ef4444",
        )

        telegram_notifier.send_message(
            f"<b>[EMERGENCY KILL-SWITCH]</b>\nFlatten all positions triggered from Terminal!{detail_msg}\nStatus: HALTED"
        )

        # 4. Refresh blotter immediately
        btn.setEnabled(True)
        if hasattr(self.controller, "_render_blotter"):
            self.controller._render_blotter("active")
