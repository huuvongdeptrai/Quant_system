"""Safety regressions derived from the independent review, F01-F13.
All broker calls use the offline fixture. Passing asserts the corrected contract.
"""
import json
import pytest
import time
from datetime import datetime, timezone
from types import SimpleNamespace as NS
from unittest.mock import Mock

from tests.test_repair_regressions import broker, defense_setup
from backend.database.db_manager import DatabaseManager
from backend.core.trading_commands import TradingCommandService
from backend.core.circuit_breaker_guard import CircuitBreakerGuard
from backend.core.state_recovery import StateRecoveryManager
from backend.infrastructure.brokers.mt5_safe import mt5


def test_regression_unknown_other_symbol_reserves_capacity(broker,monkeypatch):
    broker.runtime.max_open_trades=1
    raw=Mock(return_value={'status':'unknown','msg':'Broker reply lost'})
    monkeypatch.setattr(broker.ex,'_execute_market_order_raw',raw)
    first=broker.ex.execute_market_order('XAUUSD',True,.1,1990,2020,signal_key='first')
    second=broker.ex.execute_market_order('EURUSD',True,.1,1990,2020,signal_key='second')
    assert first['status']=='unknown' and second['status']=='error'
    assert raw.call_count==1
    assert len(DatabaseManager().get_unresolved_intents())==1


def test_regression_full_gate_blocks_malformed_model_metadata(tmp_path,monkeypatch):
    from backend.infrastructure.ai_engines.ai.decision_gate import DecisionGate
    from backend.core.meta_features import FEATURE_VERSION, FEATURE_COLUMNS
    from backend.core.macro_context_bus import MacroContextBus
    from backend.infrastructure.data_providers.asset_registry import AssetRegistry
    gate=DecisionGate()
    gate._models_dir=tmp_path
    (tmp_path/'model.json').write_text(json.dumps({'feature_version':FEATURE_VERSION,'symbol':123}))
    gate._get_or_load_meta_model=Mock(return_value=(Mock(),.38,FEATURE_COLUMNS,'model.lgb'))
    gate._get_price_position=Mock(return_value=dict(position='AT_SUPPORT',price=100,support=90,resistance=120,pct_from_support=0))
    gate._get_htf_bias=Mock(return_value='BULLISH')
    gate._get_macro_bias=Mock(return_value='BULLISH')
    monkeypatch.setattr(MacroContextBus.get_instance(),'check_pre_trade_news_compliance',lambda *a:(True,'CLEAR',''))
    adapter=Mock()
    adapter.generate_context_report.return_value={}
    adapter.evaluate_risk_rules.return_value=(True,'')
    monkeypatch.setattr(AssetRegistry,'get_adapter',lambda *a:adapter)
    full=gate.evaluate('XAUUSD','BUY',gate_mode='FULL',strategy_id='known')
    technical=gate.evaluate('XAUUSD','BUY',gate_mode='TECH_ONLY',strategy_id='known')
    assert full['decision']=='WAIT'
    assert technical['decision']=='WAIT'


def pending_order():
    return NS(ticket=42,symbol='XAUUSD',type=mt5.ORDER_TYPE_BUY_LIMIT,
              price_open=1999.,sl=1990.,tp=2020.,volume_current=1.,
              type_time=0,type_filling=2,comment='manual pending',magic=0)


def test_regression_pending_modify_respects_halt_and_preserves_stops(broker,monkeypatch):
    TradingCommandService.emergency_halt()
    monkeypatch.setattr(mt5,'orders_get',Mock(return_value=[pending_order()]))
    monkeypatch.setattr(mt5,'order_calc_profit',lambda action,symbol,vol,entry,stop:(stop-entry)*100*vol)
    send=Mock(return_value=NS(retcode=10009))
    monkeypatch.setattr(mt5,'order_send',send)
    result=broker.ex.modify_pending_order(42,1999,1900,2020)
    assert result['status']=='error'
    send.assert_not_called()
    # Omitted protection must be retained, including during a halt.
    result=broker.ex.modify_pending_order(42,1999)
    assert result['status']=='success',result
    assert send.call_args.args[0]['sl']==1990
    assert send.call_args.args[0]['tp']==2020


def test_regression_defense_retries_be_at_minimum_remainder(broker,monkeypatch):
    engine,execution,pos=defense_setup(broker,monkeypatch,2007)
    pos.volume=.02
    execution.close_position.return_value={'status':'success'}
    execution.modify_position.side_effect=[{'status':'error'},{'status':'success'}]
    assert engine.evaluate_pre_news_defense()==[]
    pos.volume=.01  # First close was confirmed, first BE modification rejected.
    assert len(engine.evaluate_pre_news_defense())==1
    assert execution.close_position.call_count==1
    assert execution.modify_position.call_count==2


def test_regression_calendar_exception_invalidates_old_flag(monkeypatch):
    from backend.core.event_risk_engine import EventRiskEngine
    calendar=Mock()
    calendar.fetch_events.side_effect=RuntimeError('network unavailable')
    engine=EventRiskEngine(calendar_engine=calendar)
    engine._calendar_valid=True  # Prior successful fetch.
    engine._news_events_ts=0
    engine._news_events_cache=[{'impact':2,'country':'US','sort_key':time.time(),'title':'NFP'}]
    blocked,reason=engine.check_news_impact_for_symbol('XAUUSD')
    assert blocked
    assert not engine._calendar_valid


def test_regression_account_switch_reloads_scoped_equity(broker,monkeypatch):
    db=DatabaseManager()
    guard=CircuitBreakerGuard(db,max_drawdown=5,max_daily_loss=0,max_losing_streak=0)
    assert not guard.evaluate_circuit_breaker()  # A: equity=100000
    db.bind_account(456,'test')
    today=datetime.now(timezone.utc).strftime('%Y-%m-%d')
    for key,value in {'start_of_day_date':today,'start_of_day_equity':'1000',
                      'start_of_day_account':'456'}.items():
        db.set_system_state(key,value)
    broker.account.login=456
    broker.account.equity=broker.account.balance=1000
    assert not guard.evaluate_circuit_breaker()
    assert guard.start_of_day_equity==1000
    assert db.get_system_state('circuit_breaker_active')=='False'


def test_regression_filled_pending_is_rebuilt_in_trade_ledger(broker,monkeypatch):
    db=DatabaseManager()
    db.bind_account(123,'test')
    intent=db.reserve_intent('pending','XAUUSD',{'broker_tag':'V2_pending'})
    db.finish_intent(intent,'UNKNOWN',{'request':{'broker_tag':'V2_pending'}})
    def deal(ticket,entry,price):
        return NS(ticket=ticket,position_id=88,order=77,time=int(time.time()),time_msc=int(time.time()*1000),
                  comment='V2_pending',entry=entry,price=price,volume=.1,profit=0,commission=0,swap=0,fee=0,
                  symbol='XAUUSD',type=0,magic=999999)
    # Pending order filled and position closed between two reconciliation polls.
    monkeypatch.setattr(mt5,'history_deals_get',Mock(return_value=[deal(1,0,2000),deal(2,1,2010)]))
    summary=StateRecoveryManager(db).reconcile_on_startup()
    assert summary['status']=='SUCCESS'
    with db._connection() as c:
        assert c.execute('SELECT status FROM order_intents').fetchone()[0]=='FILLED'
        assert c.execute('SELECT count(*) FROM broker_deals').fetchone()[0]==2
        assert c.execute('SELECT count(*) FROM trades').fetchone()[0]==1
        assert c.execute('SELECT status FROM trades').fetchone()[0]=='CLOSED'


def test_regression_admission_uses_current_runtime_session_config(broker):
    broker.runtime.allowed_sessions=['LONDON']
    effective=TradingCommandService._config(broker.runtime)
    assert tuple(effective.allowed_sessions)==('LONDON',)


def test_regression_full_close_partial_fill_updates_remaining_volume(broker,monkeypatch):
    db=DatabaseManager()
    db.bind_account(123,'test')
    db.record_open_trade(7,'XAUUSD','BUY',.1,2000,sl=1990)
    pos=NS(ticket=7,symbol='XAUUSD',type=0,volume=.1)
    monkeypatch.setattr(mt5,'positions_get',Mock(return_value=[pos]))
    monkeypatch.setattr(mt5,'order_send',Mock(return_value=NS(retcode=10010,deal=22,volume=.04)))
    result=broker.ex.close_position(7)
    assert result['status']=='partial' and result['partial_fill']
    assert result['remaining_volume']==pytest.approx(.06)
    assert db.get_open_trades()[0]['volume']==pytest.approx(.06)


def test_regression_statistics_merge_identifier_and_ticket(broker,monkeypatch):
    from backend.core.stats_engine import StatsEngine
    db=DatabaseManager()
    db.bind_account(123,'test')
    db.record_open_trade(99,'XAUUSD','SELL',.1,2000,sl=2010,position_id=88)
    db.record_close_trade(99,1990,100)
    common=dict(position_id=88,symbol='XAUUSD',volume=.1,commission=0,swap=0,fee=0)
    opening=NS(**common,entry=0,type=1,time=100,price=2000,profit=0)
    closing=NS(**common,entry=1,type=0,time=200,price=1990,profit=100)
    monkeypatch.setattr(mt5,'history_deals_get',Mock(return_value=[opening,closing]))
    history=StatsEngine().get_full_history()
    assert len(history)==1
    assert history[0]['ticket']==88
    assert history[0]['pnl']==100
    assert history[0]['type']=='Sell'


def test_regression_live_h20_time_exit_is_durable(broker,monkeypatch):
    import numpy as np
    from backend.core.position_guard import PositionGuard
    old_position=NS(ticket=7,identifier=7,symbol='XAUUSD',magic=999999,
                    time=int(time.time()-2*86400),volume=.1)
    monkeypatch.setattr(mt5,'positions_get',Mock(return_value=[old_position]))
    bars=np.array([(old_position.time+i*900,) for i in range(22)],dtype=[('time','i8')])
    monkeypatch.setattr(mt5,'copy_rates_from_pos',Mock(return_value=bars))
    db=DatabaseManager();db.bind_account(123,'test')
    db.record_open_trade(7,'XAUUSD','BUY',.1,2000,position_id=7)
    db.attach_execution_policy(7,7,{'holding_policy':{'timeframe':15,'max_holding_bars':20}})
    execution=Mock(magic=999999)
    execution.close_position.return_value={'status':'unknown'}
    guard=PositionGuard(execution,db,enable_trailing_stop=False)
    guard.manage_positions(['XAUUSD'])
    guard.manage_positions(['XAUUSD'])
    execution.close_position.assert_called_once_with(7)


def test_regression_known_pending_retains_initial_stop_on_fill(broker,monkeypatch):
    db=DatabaseManager()
    db.bind_account(123,'test')
    intent=db.reserve_intent('pending','XAUUSD',{'broker_tag':'V2_pending','sl':1990,'volume':.1,'strategy_id':'builtin_wyckoff'})
    pos=NS(ticket=7,identifier=7,symbol='XAUUSD',magic=999999,type=0,time=int(time.time()),
           volume=.1,price_open=2000,sl=1990,tp=2020)
    monkeypatch.setattr(mt5,'positions_get',Mock(return_value=[pos]))
    deal=NS(ticket=1,position_id=7,order=77,time=int(time.time()),time_msc=int(time.time()*1000),comment='V2_pending')
    monkeypatch.setattr(mt5,'history_deals_get',Mock(return_value=[deal]))
    StateRecoveryManager(db).reconcile_on_startup()
    trade=db.get_open_trades()[0]
    assert trade['initial_sl']==1990
    assert trade['broker_order_id']==77
    assert trade['strategy_id']=='builtin_wyckoff'


def test_regression_pending_uses_return_fill_policy(broker,monkeypatch):
    send=Mock(return_value=NS(retcode=10008,order=77))
    monkeypatch.setattr(mt5,'order_send',send)
    result=broker.ex._execute_pending_order_raw('XAUUSD','BUY_LIMIT',1999,.1,1990,2020,max_retries=1)
    assert result['status']=='success'
    assert send.call_args.args[0]['type_filling']==mt5.ORDER_FILLING_RETURN


def test_regression_accepted_queued_market_stays_unresolved(broker,monkeypatch):
    monkeypatch.setattr(mt5,'order_send',Mock(return_value=NS(retcode=10008,order=77,comment='Placed')))
    result=broker.ex.execute_market_order('XAUUSD',True,.1,1990,2020)
    assert result['status']=='unknown'
    db=DatabaseManager()
    assert db.has_unresolved_intent('XAUUSD')
    with db._connection() as c:
        assert c.execute('SELECT status FROM order_intents').fetchone()[0]=='UNKNOWN'


def test_amendment_rejects_over_budget_without_broker_rpc(broker,monkeypatch):
    monkeypatch.setattr(mt5,'orders_get',Mock(return_value=[pending_order()]))
    monkeypatch.setattr(mt5,'order_calc_profit',lambda action,symbol,vol,entry,stop:(stop-entry)*100*vol)
    send=Mock();monkeypatch.setattr(mt5,'order_send',send)
    result=broker.ex.modify_pending_order(42,1999,1900,2020)
    assert result['status']=='error' and 'budget' in result['msg']
    send.assert_not_called()


def test_unknown_amendment_is_durable_and_not_sent_again(broker,monkeypatch):
    monkeypatch.setattr(mt5,'orders_get',Mock(return_value=[pending_order()]))
    monkeypatch.setattr(mt5,'order_calc_profit',lambda action,symbol,vol,entry,stop:(stop-entry)*100*vol)
    send=Mock(return_value=None);monkeypatch.setattr(mt5,'order_send',send)
    assert broker.ex.modify_pending_order(42,1999,1991,2020)['status']=='unknown'
    assert broker.ex.modify_pending_order(42,1999,1991,2020)['status']=='error'
    assert send.call_count==1
    db=DatabaseManager()
    saved=db.get_unresolved_intents()
    assert len(saved)==1 and json.loads(saved[0]['payload'])['amendment']['pending']


def test_pending_closed_between_polls_reconciliation_is_idempotent(broker,monkeypatch):
    db=DatabaseManager();db.bind_account(123,'test')
    intent=db.reserve_intent('closed-between-polls','XAUUSD',{'broker_tag':'V2_closed','sl':1990})
    now=int(time.time())
    common=dict(position_id=88,order=77,symbol='XAUUSD',type=1,magic=999999,time=now,time_msc=now*1000,
                volume=.1,swap=0,fee=0,comment='V2_closed')
    opening=NS(**common,ticket=1,entry=0,price=2000,profit=0,commission=-.35)
    closing=NS(**common,ticket=2,entry=1,price=1990,profit=100,commission=-.35)
    monkeypatch.setattr(mt5,'history_deals_get',Mock(return_value=[opening,closing]))
    recovery=StateRecoveryManager(db)
    recovery.reconcile_on_startup();recovery.reconcile_on_startup()
    closed=db.get_closed_trades()
    assert len(closed)==1 and closed[0]['pnl']==pytest.approx(99.3)
    assert closed[0]['order_type']=='SELL'
    assert not db.has_unresolved_intent('XAUUSD')


def test_incomplete_pending_history_does_not_release_reservation(broker,monkeypatch):
    db=DatabaseManager();db.bind_account(123,'test')
    db.reserve_intent('missing-exit','XAUUSD',{'broker_tag':'V2_missing'})
    now=int(time.time())
    opening=NS(ticket=1,position_id=88,order=77,time=now,time_msc=now*1000,
               symbol='XAUUSD',entry=0,type=0,price=2000,volume=.1,comment='V2_missing')
    monkeypatch.setattr(mt5,'history_deals_get',Mock(return_value=[opening]))
    StateRecoveryManager(db).reconcile_on_startup()
    assert db.has_unresolved_intent('XAUUSD')
    assert db.get_closed_trades()==[]


def test_holding_policy_does_not_apply_to_legacy_or_manual(broker,monkeypatch):
    from backend.core.position_guard import PositionGuard
    old=NS(ticket=7,identifier=7,symbol='XAUUSD',magic=999999,time=1,volume=.1)
    monkeypatch.setattr(mt5,'positions_get',Mock(return_value=[old]))
    execution=Mock(magic=999999)
    guard=PositionGuard(execution,DatabaseManager(),enable_trailing_stop=False)
    guard.manage_positions(['XAUUSD'])
    execution.close_position.assert_not_called()


def test_placed_market_reconciles_by_order_id_when_comment_is_stripped(broker,monkeypatch):
    monkeypatch.setattr(mt5,'order_send',Mock(return_value=NS(retcode=10008,order=77,comment='Placed')))
    assert broker.ex.execute_market_order('XAUUSD',True,.1,1990,2020)['status']=='unknown'
    now=int(time.time())
    pos=NS(ticket=99,identifier=88,symbol='XAUUSD',magic=999999,type=0,time=now,
           volume=.1,price_open=2000,sl=1990,tp=2020)
    deal=NS(ticket=22,position_id=88,order=77,time=now,time_msc=now*1000,entry=0,
            symbol='XAUUSD',type=0,price=2000,volume=.1,comment='broker replaced comment')
    monkeypatch.setattr(mt5,'positions_get',Mock(return_value=[pos]))
    monkeypatch.setattr(mt5,'history_deals_get',Mock(return_value=[deal]))
    db=DatabaseManager()
    StateRecoveryManager(db).reconcile_on_startup()
    assert not db.has_unresolved_intent('XAUUSD')
    row=db.get_open_trades()[0]
    assert row['initial_sl']==1990 and row['position_id']==88
    assert db.get_system_state('position_policy:88')


def test_amendment_positive_broker_snapshot_clears_unknown_marker(broker,monkeypatch):
    order=pending_order()
    monkeypatch.setattr(mt5,'orders_get',Mock(return_value=[order]))
    monkeypatch.setattr(mt5,'order_calc_profit',lambda action,symbol,vol,entry,stop:(stop-entry)*100*vol)
    monkeypatch.setattr(mt5,'order_send',Mock(return_value=None))
    assert broker.ex.modify_pending_order(42,1999,1991,2020)['status']=='unknown'
    order.sl=1991
    monkeypatch.setattr(mt5,'history_deals_get',Mock(return_value=[]))
    db=DatabaseManager()
    StateRecoveryManager(db).reconcile_intents()
    payload=json.loads(db.get_unresolved_intents()[0]['payload'])
    assert not payload.get('amendment',{}).get('pending')
    assert payload['request']['sl']==1991
    assert db.has_unresolved_intent('XAUUSD')  # Working order still consumes capacity.


def test_stop_mode_switch_during_validation_cannot_send(broker,monkeypatch):
    def change(*args):
        broker.runtime.execution_mode='MANUAL'
        return 100
    monkeypatch.setattr(mt5,'order_calc_margin',change)
    send=Mock();monkeypatch.setattr(mt5,'order_send',send)
    result=broker.ex.execute_market_order('XAUUSD',True,.1,1990,2020)
    assert result['status']=='error'
    send.assert_not_called()


def test_saved_checkbox_sessions_are_used_without_runtime():
    from backend.core.engine_config import BotRunConfig
    config=BotRunConfig.from_dict({'session_asian':False,'session_london':True,'session_ny':False})
    assert config.allowed_sessions==('LONDON',)


def test_halt_blocks_pending_entry_reprice_even_if_stop_loss_is_smaller(broker,monkeypatch):
    monkeypatch.setattr(mt5,'orders_get',Mock(return_value=[pending_order()]))
    monkeypatch.setattr(mt5,'order_calc_profit',lambda action,symbol,vol,entry,stop:(stop-entry)*100*vol)
    TradingCommandService.emergency_halt()
    send=Mock();monkeypatch.setattr(mt5,'order_send',send)
    result=broker.ex.modify_pending_order(42,1998,1990,2020)
    assert result['status']=='error'
    send.assert_not_called()


def test_accepted_close_stays_unknown_until_broker_confirmation(broker,monkeypatch):
    pos=NS(ticket=7,symbol='XAUUSD',type=0,volume=.1)
    monkeypatch.setattr(mt5,'positions_get',Mock(return_value=[pos]))
    monkeypatch.setattr(mt5,'order_send',Mock(return_value=NS(retcode=10008,order=77,comment='Placed')))
    assert broker.ex.close_position(7)['status']=='unknown'
