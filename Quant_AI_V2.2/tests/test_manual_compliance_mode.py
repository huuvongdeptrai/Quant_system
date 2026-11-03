"""
Unit and Integration Tests for Manual Compliance Mode & Order Unblocking:
1. Config Schema & Options Persistence (DISCRETIONARY vs SYSTEM_GUARD).
2. StateRecoveryManager Ghost/Orphaned Intent Timeout.
3. TradingCommandService Manual Autonomy (Unblocked by bot intents / existing positions).
4. TradingPlanPanel Card M1 Compliance Mode & 50% Lot Scaling on Counter-Trend.
"""

import json
import time
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import numpy as np
import pytest

from PySide6.QtWidgets import QApplication, QWidget, QLabel, QDoubleSpinBox, QPushButton
from backend.core.engine_config import BotRunConfig
from frontend.widgets.options.options_binder import OptionsConfigBinder, DEFAULTS
from backend.database.db_manager import DatabaseManager
from backend.core.state_recovery import StateRecoveryManager
from backend.core.trading_commands import TradingCommandService
from backend.infrastructure.brokers.execution_manager import ExecutionManager
from backend.infrastructure.brokers.mt5_safe import mt5


def test_bot_run_config_manual_compliance_mode():
    cfg_default = BotRunConfig()
    assert cfg_default.manual_compliance_mode == "DISCRETIONARY"

    cfg_custom = BotRunConfig.from_dict({"manual_compliance_mode": "SYSTEM_GUARD"})
    assert cfg_custom.manual_compliance_mode == "SYSTEM_GUARD"

    d = cfg_custom.to_dict()
    assert d.get("manual_compliance_mode") == "SYSTEM_GUARD"


def test_options_binder_defaults_and_roundtrip(tmp_path, monkeypatch):
    assert "manual_compliance_mode" in DEFAULTS
    assert DEFAULTS["manual_compliance_mode"] == "DISCRETIONARY"

    fake_cfg = tmp_path / "settings.json"
    fake_cfg.write_text(json.dumps({"manual_compliance_mode": "SYSTEM_GUARD"}), encoding="utf-8")
    monkeypatch.setattr("frontend.widgets.options.options_binder.CONFIG_PATH", str(fake_cfg))

    loaded, _, _ = OptionsConfigBinder.load_settings()
    assert loaded.get("manual_compliance_mode") == "SYSTEM_GUARD"

    OptionsConfigBinder.save_settings({"manual_compliance_mode": "DISCRETIONARY"})
    loaded2, _, _ = OptionsConfigBinder.load_settings()
    assert loaded2.get("manual_compliance_mode") == "DISCRETIONARY"


def test_state_recovery_orphaned_intent_timeout(monkeypatch):
    db = DatabaseManager()
    db.bind_account(999999, "TestServer")

    # Reserve intent older than 60s
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=70)).isoformat()
    intent_id = db.reserve_intent("test_orphan_key", "XAUUSD", {"broker_tag": "V2_orphan", "symbol": "XAUUSD"})
    db.finish_intent(intent_id, "UNKNOWN", {"request": {"broker_tag": "V2_orphan"}})

    # Manually backdate updated_at in order_intents
    with db._connection() as conn:
        conn.execute("UPDATE order_intents SET updated_at=? WHERE intent_id=?", (old_time, intent_id))

    assert db.has_unresolved_intent("XAUUSD")

    # Mock MT5 to return valid account info, empty live orders, empty deals, and empty history
    monkeypatch.setattr(mt5, "account_info", Mock(return_value=NS(login=999999, server="TestServer")))
    monkeypatch.setattr(mt5, "orders_get", Mock(return_value=[]))
    monkeypatch.setattr(mt5, "positions_get", Mock(return_value=[]))
    monkeypatch.setattr(mt5, "history_deals_get", Mock(return_value=[]))
    monkeypatch.setattr(mt5, "history_orders_get", Mock(return_value=[]))

    recovery = StateRecoveryManager(db)
    recovery.reconcile_intents()

    # The orphaned intent must have timed out and changed to CANCELED
    assert not db.has_unresolved_intent("XAUUSD")
    with db._connection() as conn:
        row = conn.execute("SELECT status FROM order_intents WHERE intent_id=?", (intent_id,)).fetchone()
        assert row[0] == "CANCELED"


def test_trading_commands_manual_allows_concurrent_and_ignores_bot_intent(monkeypatch):
    db = DatabaseManager()
    db.bind_account(12345, "TestServer")

    account = NS(login=12345, server='TestServer', balance=100000., equity=100000., margin_free=100000.)
    info = NS(digits=2, point=.01, trade_tick_size=.01, trade_tick_value=1.,
              volume_min=.01, volume_max=100., volume_step=.01, trade_stops_level=0,
              filling_mode=2, spread=10, path='Metals')
    tick = NS(bid=2000., ask=2000.1, time=int(time.time()))

    class DummyOrder:
        ticket = 1001
        symbol = "XAUUSD"
        magic = 999999

    class DummyPos:
        ticket = 2001
        identifier = 2001
        symbol = "XAUUSD"
        magic = 999999
        volume = 0.1
        price_open = 2000.0
        sl = 1990.0
        tp = 2020.0
        time = int(time.time())

    for name, value in {
        'account_info': account, 'terminal_info': NS(connected=True, trade_allowed=True),
        'symbol_info': info, 'symbol_info_tick': tick, 'positions_get': (DummyPos(),),
        'orders_get': (DummyOrder(),), 'symbol_select': True,
        'copy_rates_from_pos': np.array([(int(time.time()),)], dtype=[('time', 'i8')]),
        'order_calc_margin': 100., 'order_calc_profit': -100.
    }.items():
        monkeypatch.setattr(mt5, name, Mock(return_value=value))

    monkeypatch.setattr('backend.core.trading_commands.SessionFilter.is_session_allowed', lambda *a, **k: (True, 'TEST'))
    monkeypatch.setattr('backend.core.trading_commands.EventRiskEngine.check_spread_normalization', lambda *a: (True, 10, 25))
    monkeypatch.setattr('backend.core.trading_commands.EventRiskEngine.check_news_impact_for_symbol', lambda *a: (False, ''))
    monkeypatch.setattr('backend.infrastructure.ai_engines.ai.decision_gate.DecisionGate.evaluate', lambda *a, **k: {'decision': 'BUY', 'size_multiplier': 1})

    config = BotRunConfig.from_dict(dict(execution_mode='FULL-AUTO', news_filter_enabled=False,
                                         close_friday=False, max_drawdown=0, max_daily_loss=0, max_losing_streak=0))
    runtime = NS(config=config, is_running=True)
    TradingCommandService.register_runtime(runtime)
    ex = ExecutionManager()

    # An unresolved bot intent exists on XAUUSD
    intent_id = db.reserve_intent("bot_sig", "XAUUSD", {"broker_tag": "V2_bot"})
    db.finish_intent(intent_id, "UNKNOWN", {"request": {"broker_tag": "V2_bot"}})
    assert db.has_unresolved_intent("XAUUSD")

    cmd = TradingCommandService(ex)
    cmd.db = db

    # 1. Automated bot entry MUST be blocked by existing position and unresolved bot intent
    res_auto = cmd.submit("XAUUSD", is_buy=True, volume=0.01, sl_price=1990.0, tp_price=2020.0,
                          comment="VECTRA_Bot", magic=999999)
    assert res_auto["status"] == "error"
    assert "Existing position" in res_auto["msg"] or "Capacity or unresolved" in res_auto["msg"]

    # 2. Manual order (magic=0, comment="VECTRA_Manual") is NOT blocked by single-symbol bot position or bot intent
    monkeypatch.setattr(ex, "_execute_market_order_raw", Mock(return_value={"status": "success", "ticket": 3001, "order_id": 3001}))

    res_man = cmd.submit("XAUUSD", is_buy=True, volume=0.01, sl_price=1990.0, tp_price=2020.0,
                         comment="VECTRA_Manual", magic=0)
    assert res_man.get("status") in ("success", "unknown")


def test_trading_plan_panel_compliance_mode_lot_scaling(monkeypatch):
    app = QApplication.instance() or QApplication([])

    from frontend.controllers.chart.trading_plan_panel import (
        _recalculate_manual_lot_and_rr,
        _update_manual_mode_button_style,
    )
    from backend.core.macro_context_bus import MacroContextBus, SymbolMacroProfile

    # Set up mock window
    win = QWidget()
    win.current_sym = "XAUUSD"
    win._manual_direction = "BUY"
    win._manual_risk_pct = 1.0
    win._user_custom_lot = False
    win._manual_compliance_mode = "SYSTEM_GUARD"
    win.is_dark_theme = True

    spin_lot = QDoubleSpinBox()
    spin_lot.setValue(1.0)
    win.spinManualLot = spin_lot

    spin_sl = QDoubleSpinBox()
    spin_sl.setValue(2640.0)
    win.spinManualSL = spin_sl

    spin_tp = QDoubleSpinBox()
    spin_tp.setValue(2670.0)
    win.spinManualTP = spin_tp

    lbl_badge = QLabel()
    win.lblManualCopilotBadge = lbl_badge

    btn_toggle = QPushButton()
    win.btnManualModeToggle = btn_toggle

    # Mock symbol info
    sym_info = Mock()
    sym_info.digits = 2
    sym_info.point = 0.01
    sym_info.trade_tick_size = 0.01
    sym_info.volume_min = 0.01
    monkeypatch.setattr(mt5, "symbol_info", Mock(return_value=sym_info))
    monkeypatch.setattr(mt5, "terminal_info", Mock(return_value=Mock(trade_allowed=True)))
    monkeypatch.setattr(mt5, "account_info", Mock(return_value=Mock(balance=100000.0, equity=100000.0)))
    monkeypatch.setattr(mt5, "symbol_info_tick", Mock(return_value=Mock(bid=2650.0, ask=2650.25)))

    # Set Macro Profile to BEARISH
    bus = MacroContextBus.get_instance()
    bus.set_profile(SymbolMacroProfile(symbol="XAUUSD", directional_bias="BEARISH", macro_regime="RECESSION"))

    # 1. In SYSTEM_GUARD with BEARISH macro bias, BUY is counter-trend:
    monkeypatch.setattr("frontend.controllers.chart.trading_plan_panel.calculate_manual_quant_lot", lambda *a, **k: (1.0, 1000.0))
    _recalculate_manual_lot_and_rr(win)

    assert win.spinManualLot.value() == 0.5
    assert "COUNTER-TREND" in win.lblManualCopilotBadge.text()
    assert "50% VOL" in win.lblManualCopilotBadge.text()

    # 2. Change direction to SELL (pro-trend): full 100% volume
    win._manual_direction = "SELL"
    _recalculate_manual_lot_and_rr(win)
    assert win.spinManualLot.value() == 1.0
    assert "PRO-TREND" in win.lblManualCopilotBadge.text()
    assert "100% VOL" in win.lblManualCopilotBadge.text()

    # 3. Switch to DISCRETIONARY mode: BUY should now be full 100% volume
    win._manual_direction = "BUY"
    win._manual_compliance_mode = "DISCRETIONARY"
    _update_manual_mode_button_style(win)
    assert "[ MODE: DISCRETIONARY ]" in win.btnManualModeToggle.text()

    _recalculate_manual_lot_and_rr(win)
    assert win.spinManualLot.value() == 1.0
    assert "COUNTER-TREND" in win.lblManualCopilotBadge.text()
