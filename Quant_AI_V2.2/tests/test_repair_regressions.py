"""Regression tests for real failure scenarios found in the November audit.

All broker effects are simulated. These tests do not certify live execution.
"""
import json
import math
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest

from backend.database.db_manager import DatabaseManager
from backend.core.engine_config import BotRunConfig
from backend.core.risk_manager import RiskManager
from backend.core.trading_commands import TradingCommandService
from backend.infrastructure.brokers.execution_manager import ExecutionManager
from backend.infrastructure.brokers.mt5_safe import mt5
from backend.core.bot_orchestrator import BotOrchestrator
from backend.backtest.backtest_ict_pro import EventDrivenBacktester


def test_replayed_open_preserves_terminal_history(tmp_path):
    db=DatabaseManager(str(tmp_path/'history.db'))
    assert db.record_open_trade(7,'XAUUSD','BUY',1,2000)
    assert db.record_close_trade(7,2010,993)
    assert not db.record_open_trade(7,'XAUUSD','BUY',1,1990)
    assert db.get_closed_trades()[0]['pnl']==993
    assert db.record_close_trade(7,2010,993)  # Same event is idempotent.
    assert not db.record_close_trade(7,2010,1)  # Conflicting event is not.


def test_updates_must_have_a_target(tmp_path):
    db=DatabaseManager(str(tmp_path/'updates.db'))
    assert not db.record_close_trade(999,2000,1)
    assert not db.update_trade_volume(999,.1)
    assert not db.record_open_trade(7,'X','BUY',-1,2000)
    assert not db.record_open_trade(8,'X','BUY',float('nan'),2000)


def test_scope_isolation_and_fixed_paths(tmp_path):
    a=DatabaseManager(str(tmp_path/'a.db'))
    a.bind_account(1,'broker')
    a.record_open_trade(7,'X','BUY',1,100)
    a.bind_account(2,'broker')
    assert a.get_open_trades()==[]
    a.record_open_trade(7,'X','SELL',.1,200)
    a.bind_account(1,'broker')
    assert a.get_open_trades()[0]['open_price']==100
    b=DatabaseManager(str(tmp_path/'b.db'))
    assert a is not b and a.db_path!=b.db_path
    assert len(a.get_open_trades())==1


def test_legacy_migration_keeps_unverified_data(tmp_path):
    path=tmp_path/'v0.db'
    with sqlite3.connect(path) as c:
        c.executescript("""
        CREATE TABLE trades(ticket INTEGER PRIMARY KEY,symbol TEXT,order_type TEXT,volume REAL,
          open_price REAL,close_price REAL,sl REAL,tp REAL,pnl REAL,open_time TEXT,close_time TEXT,status TEXT,comment TEXT);
        CREATE TABLE system_state(key TEXT PRIMARY KEY,value TEXT,updated_at TEXT);
        INSERT INTO trades VALUES(7,'X','BUY',1,100,0,90,120,0,'2026-01-01','','CLOSED','legacy');
        """)
    db=DatabaseManager(str(path))
    with db._connection() as c:
        assert c.execute('PRAGMA user_version').fetchone()[0]==2
        assert c.execute('SELECT status FROM trades').fetchone()[0]=='UNRESOLVED'
        assert c.execute('SELECT count(*) FROM trades_legacy_v0').fetchone()[0]==1
    assert path.with_name(path.name+'.pre_v2.bak').exists()
    db.bind_account(1,'broker')
    assert db.get_open_trades()==[]


def test_atomic_reservations_across_threads_and_restarts(tmp_path):
    path=str(tmp_path/'intents.db')
    db=DatabaseManager(path)
    def reserve(_):
        db.bind_account(1,'broker')
        return db.reserve_intent('same-signal','X',{'risk':1})
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids=list(pool.map(reserve,range(16)))
    assert sum(x is not None for x in ids)==1
    db.bind_account(1,'broker')
    intent=next(x for x in ids if x)
    db.finish_intent(intent,'UNKNOWN',{})
    DatabaseManager.reset_instance()
    db=DatabaseManager(path)
    db.bind_account(1,'broker')
    assert db.has_unresolved_intent('X')
    assert db.reserve_intent('another','X',{}) is None


@pytest.fixture
def broker(monkeypatch):
    account=NS(login=123,server='test',balance=100000.,equity=100000.,margin_free=100000.)
    info=NS(digits=2,point=.01,trade_tick_size=.01,trade_tick_value=1.,
            volume_min=.01,volume_max=100.,volume_step=.01,trade_stops_level=0,
            filling_mode=2,spread=10,path='Metals')
    tick=NS(bid=2000.,ask=2000.1,time=int(time.time()))
    for name,value in {'account_info':account,'terminal_info':NS(connected=True,trade_allowed=True),
                       'symbol_info':info,'symbol_info_tick':tick,'positions_get':(),
                       'orders_get':(),'symbol_select':True,
                       'copy_rates_from_pos':np.array([(123,)],dtype=[('time','i8')]),
                       'order_calc_margin':100.,'order_calc_profit':-100.}.items():
        monkeypatch.setattr(mt5,name,Mock(return_value=value))
    monkeypatch.setattr('backend.core.trading_commands.SessionFilter.is_session_allowed',lambda *a,**k:(True,'TEST'))
    monkeypatch.setattr('backend.core.trading_commands.EventRiskEngine.check_spread_normalization',lambda *a:(True,10,25))
    monkeypatch.setattr('backend.core.trading_commands.EventRiskEngine.check_news_impact_for_symbol',lambda *a:(False,''))
    monkeypatch.setattr('backend.infrastructure.ai_engines.ai.decision_gate.DecisionGate.evaluate',lambda *a,**k:{'decision':'BUY','size_multiplier':1})
    config=BotRunConfig.from_dict(dict(execution_mode='FULL-AUTO',news_filter_enabled=False,
        close_friday=False,max_drawdown=0,max_daily_loss=0,max_losing_streak=0))
    runtime=NS(config=config,is_running=True)
    TradingCommandService.register_runtime(runtime)
    ex=ExecutionManager()
    return NS(account=account,info=info,tick=tick,runtime=runtime,ex=ex)


@pytest.mark.parametrize('volume',[0,-1,float('nan'),float('inf')])
def test_invalid_volume_never_sends(broker,volume,monkeypatch):
    send=Mock()
    monkeypatch.setattr(mt5,'order_send',send)
    assert broker.ex.execute_market_order('XAUUSD',True,volume,1990,2020)['status']=='error'
    send.assert_not_called()


def test_unknown_broker_outcome_blocks_retry(broker,monkeypatch):
    send=Mock(return_value=None)
    monkeypatch.setattr(mt5,'order_send',send)
    result=broker.ex.execute_market_order('XAUUSD',True,.1,1990,2020)
    assert result['status']=='unknown'
    assert broker.ex.execute_market_order('XAUUSD',True,.1,1990,2020)['status']=='error'
    assert send.call_count==1


@pytest.mark.parametrize('mode,running',[('SEMI-AUTO',True),('MANUAL',True),('FULL-AUTO',False)])
def test_automatic_admission_requires_armed_full_auto(broker,monkeypatch,mode,running):
    broker.runtime.execution_mode=mode
    broker.runtime.is_running=running
    send=Mock()
    monkeypatch.setattr(mt5,'order_send',send)
    assert broker.ex.execute_market_order('XAUUSD',True,.1,1990,2020)['status']=='error'
    send.assert_not_called()


def test_emergency_halt_covers_manual_entries(broker,monkeypatch):
    send=Mock()
    monkeypatch.setattr(mt5,'order_send',send)
    TradingCommandService.emergency_halt()
    assert broker.ex.execute_market_order('XAUUSD',True,.1,1990,2020,magic=0)['status']=='error'
    send.assert_not_called()


def test_stop_widening_recalculates_size(broker,monkeypatch):
    broker.info.trade_stops_level=1000
    raw=Mock(return_value={'status':'unknown','msg':'deliberate unresolved response'})
    monkeypatch.setattr(broker.ex,'_execute_market_order_raw',raw)
    broker.ex.execute_market_order('XAUUSD',True,10,1999,2020,risk_pct=.1)
    args=raw.call_args.args
    volume,sl=args[2],args[3]
    assert sl<1990
    assert volume*abs(2000.3-sl)*100 <= 100+1e-6


def test_partial_fill_is_persisted_with_broker_identity(broker,monkeypatch):
    from collections import namedtuple
    D=namedtuple('Deal','ticket position_id order time time_msc price volume profit commission swap fee')
    deal=D(44,88,55,int(time.time()),int(time.time()*1000),2000.2,.04,0,-.14,0,0)
    pos=NS(ticket=99,identifier=88,symbol='XAUUSD',type=0,volume=.04,price_open=2000.2,sl=1990.,tp=2020.,magic=999999)
    # First exposure query sees flat; post-fill query sees the broker position.
    monkeypatch.setattr(mt5,'positions_get',Mock(side_effect=[(),[pos]]))
    monkeypatch.setattr(mt5,'history_deals_get',Mock(return_value=[deal]))
    monkeypatch.setattr(mt5,'order_send',Mock(return_value=NS(retcode=10010,order=55,deal=44,price=2000.2,volume=.04)))
    result=broker.ex.execute_market_order('XAUUSD',True,.1,1990,2020)
    assert result['status']=='success' and result['partial'], result
    assert result['ticket']==99 and result['position_id']==88 and result['volume']==.04
    db=DatabaseManager()
    assert db.get_open_trades()[0]['broker_order_id']==55
    with db._connection() as c:
        assert c.execute('SELECT count(*) FROM broker_deals').fetchone()[0]==1


def test_fine_volume_step_preserves_risk(broker):
    broker.info.volume_step=.0001
    broker.info.volume_min=.0001
    broker.info.trade_tick_size=1
    broker.info.trade_tick_value=1
    distance=100/.01595
    lot=RiskManager().calculate_lot_size('X',distance,.1)
    assert lot*distance<=100+1e-6


def test_recovery_api_failure_does_not_allow_entry(broker,monkeypatch):
    from backend.core.state_recovery import StateRecoveryManager
    monkeypatch.setattr(mt5,'positions_get',Mock(return_value=None))
    assert not StateRecoveryManager(DatabaseManager()).can_open_new_trade('XAUUSD')


@pytest.mark.parametrize('mode',['MANUAL','SEMI-AUTO'])
def test_worker_cannot_dispatch_in_nonautomatic_mode(mode):
    state=NS(is_running=True,execution_mode=mode)
    BotOrchestrator.pipeline_execute(state,'XAUUSD')  # Must return before any dependency call.


def frame(n=180):
    return pd.DataFrame(dict(time=pd.date_range('2026-01-05',periods=n,freq='15min'),
        open=np.full(n,100.),high=np.full(n,101.),low=np.full(n,99.),close=np.full(n,100.)))


class OneSignal:
    def __init__(self,sl=90,tp=120): self.used=False;self.sl=sl;self.tp=tp
    def analyze(self,df,macro_context):
        if self.used:return {'signal':'HOLD'}
        self.used=True
        return {'signal':'BUY','entry_price':float(df['close'].iloc[-1]),'sl':self.sl,'tp1':self.tp}


def test_gap_stop_and_causal_entry():
    df=frame()
    df.loc[101,['open','high','low','close']]=[80,85,75,80]
    report=EventDrivenBacktester(OneSignal(),commission_per_lot=0,slippage_pts=0).run(df)
    trade=report.trade_records[0]
    assert trade['exit']==80
    assert pd.Timestamp(trade['signal_time'])<pd.Timestamp(trade['entry_time'])


def test_holding_barrier_and_final_liquidation():
    report=EventDrivenBacktester(OneSignal(),slippage_pts=0).run(frame())
    assert report.trade_records[0]['outcome']=='TIME'
    assert report.trade_records[0]['holding_bars']==20
    report=EventDrivenBacktester(OneSignal(),max_holding_bars=None,slippage_pts=0).run(frame())
    assert report.trade_records[0]['outcome']=='END_OF_DATA'


def test_equity_drawdown_includes_open_loss():
    df=frame()
    df.loc[105,['open','high','low','close']]=[100,101,91,92]
    report=EventDrivenBacktester(OneSignal(),commission_per_lot=0,slippage_pts=0).run(df)
    assert report.total_net_profit==0
    assert report.max_drawdown_pct>0


def test_vwap_variance_and_snapshot_isolation():
    from backend.core.preprocessor import DataPreprocessor
    from backend.core.market_state_store import MarketStateStore
    df=pd.DataFrame(dict(high=[100,102],low=[100,102],close=[100,102],volume=[1,1]))
    result=DataPreprocessor()._calculate_session_vwap(df)
    assert result['vwap_upper1']==102
    store=MarketStateStore.get_instance()
    store.reset()
    store.update_state('X',live_ticket=7,is_live_position=True)
    snap=store.get_state('X');snap.live_ticket=99
    assert store.get_state('X').live_ticket==7
    store.update_state('X',live_ticket=None,is_live_position=False)
    assert store.get_state('X').live_ticket is None


def test_stop_during_validation_never_submits(broker,monkeypatch):
    def margin(*args):
        broker.runtime.is_running=False
        return 100.
    monkeypatch.setattr(mt5,'order_calc_margin',margin)
    send=Mock()
    monkeypatch.setattr(mt5,'order_send',send)
    assert broker.ex.execute_market_order('XAUUSD',True,.1,1990,2020)['status']=='error'
    send.assert_not_called()


def test_gate_risk_scaling_is_applied_once(broker,monkeypatch):
    monkeypatch.setattr('backend.infrastructure.ai_engines.ai.decision_gate.DecisionGate.evaluate',
        lambda *a,**k:dict(decision='BUY',size_multiplier=.5,trade_mode='SCALP_PULLBACK',tp_limit_r=1.5))
    raw=Mock(return_value=dict(status='unknown',msg='test'))
    monkeypatch.setattr(broker.ex,'_execute_market_order_raw',raw)
    broker.ex.execute_market_order('XAUUSD',True,5,1990,2050)
    _,_,lot,sl,tp=raw.call_args.args
    assert lot*abs(2000.3-sl)*100<=500+1e-6
    assert lot*abs(2000.3-sl)*100>490
    assert tp<=2000.1+abs(2000.1-sl)*1.5+1e-6


def defense_setup(broker,monkeypatch,price):
    from backend.core.event_risk_engine import EventRiskEngine
    pos=NS(ticket=88,identifier=77,symbol='XAUUSD',magic=999999,comment='bot',
           type=0,price_open=2000.,sl=1990.,tp=2050.,volume=.1)
    monkeypatch.setattr(mt5,'positions_get',Mock(return_value=[pos]))
    broker.tick.bid=price
    db=DatabaseManager()
    db.bind_account(123,'test')
    assert db.record_open_trade(88,'XAUUSD','BUY',.1,2000,sl=1990,tp=2050,position_id=77,magic=999999)
    execution=Mock(magic=999999)
    engine=EventRiskEngine(execution)
    engine.refresh_events_if_needed=lambda:None
    engine._news_events_cache=[dict(impact=2,sort_key=time.time()+100,country='US',title='test')]
    return engine,execution,pos


def test_failed_news_breakeven_is_retried(broker,monkeypatch):
    engine,execution,pos=defense_setup(broker,monkeypatch,2020)
    execution.modify_position.side_effect=[{'status':'error'},{'status':'success'}]
    assert engine.evaluate_pre_news_defense()==[]
    assert len(engine.evaluate_pre_news_defense())==1
    assert execution.modify_position.call_count==2


def test_unknown_partial_close_is_not_duplicated(broker,monkeypatch):
    engine,execution,pos=defense_setup(broker,monkeypatch,2007)
    execution.close_position.return_value={'status':'unknown'}
    execution.modify_position.return_value={'status':'success'}
    assert engine.evaluate_pre_news_defense()==[]
    assert engine.evaluate_pre_news_defense()==[]
    assert execution.close_position.call_count==1
    pos.volume=.05  # Broker later confirms the intended reduction.
    assert len(engine.evaluate_pre_news_defense())==1
    assert execution.close_position.call_count==1


def test_friday_liquidation_protects_manual_positions(broker,monkeypatch):
    from datetime import datetime,timezone
    from backend.core.session_filter import SessionFilter
    class Friday(datetime):
        @classmethod
        def now(cls,*args):return cls(2026,10,30,21,30,tzinfo=timezone.utc)
    monkeypatch.setattr('backend.core.session_filter.datetime',Friday)
    positions=[NS(ticket=1,symbol='XAUUSD',magic=0,comment='manual'),
               NS(ticket=2,symbol='XAUUSD',magic=999999,comment='bot')]
    monkeypatch.setattr(mt5,'positions_get',Mock(return_value=positions))
    execution=Mock(magic=999999)
    execution.close_position.return_value={'status':'success'}
    assert SessionFilter().manage_friday_eod(['XAUUSD'],execution)==[2]
    execution.close_position.assert_called_once_with(2)


def test_corrupt_attached_model_blocks_instead_of_bypassing():
    from backend.infrastructure.ai_engines.ai.decision_gate import DecisionGate
    gate=DecisionGate()
    gate._get_or_load_meta_model=Mock(side_effect=RuntimeError('corrupt model'))
    passed,prob,_=gate._evaluate_meta_labeling('X','BUY',rates=frame())
    assert passed is False and prob==0


def test_stale_macro_context_is_not_reported_clear():
    from backend.core.macro_context_bus import MacroContextBus,SymbolMacroProfile
    bus=MacroContextBus.get_instance()
    bus.set_profile(SymbolMacroProfile(symbol='X',timestamp=0))
    bus._trigger_async_refresh=Mock()
    passed,_,_=bus.check_pre_trade_news_compliance('X')
    assert not passed
    bus._trigger_async_refresh.assert_called_once()


def test_adverse_quote_change_after_sizing_is_rejected(broker,monkeypatch):
    fresh=NS(**vars(broker.tick))
    fresh.ask+=1
    monkeypatch.setattr(mt5,'symbol_info_tick',Mock(side_effect=[broker.tick,fresh]))
    send=Mock()
    monkeypatch.setattr(mt5,'order_send',send)
    result=broker.ex.execute_market_order('XAUUSD',True,.1,1990,2020)
    assert result['status']=='error'
    assert 'quote change' in result['msg']
    send.assert_not_called()


def test_unavailable_broker_history_blocks_new_entries(broker,monkeypatch):
    broker.runtime.max_losing_streak=3
    monkeypatch.setattr(mt5,'history_deals_get',lambda *a,**k:None)
    send=Mock()
    monkeypatch.setattr(mt5,'order_send',send)
    assert broker.ex.execute_market_order('XAUUSD',True,.1,1990,2020)['status']=='error'
    send.assert_not_called()


def test_statistics_aggregate_partial_exits_and_all_costs(monkeypatch):
    from backend.core.stats_engine import StatsEngine
    opening=NS(position_id=88,entry=0,time=100,symbol='XAUUSD',volume=.1,price=2000.,profit=0.,commission=-2.,swap=0.,fee=-1.)
    partial=NS(position_id=88,entry=1,time=200,symbol='XAUUSD',volume=.04,price=2002.,profit=8.,commission=-.8,swap=0.,fee=0.)
    closing=NS(position_id=88,entry=1,time=300,symbol='XAUUSD',volume=.06,price=2003.,profit=18.,commission=-1.2,swap=-.5,fee=0.)
    monkeypatch.setattr(mt5,'terminal_info',lambda:True)
    monkeypatch.setattr(mt5,'positions_get',lambda:())
    monkeypatch.setattr(mt5,'history_deals_get',lambda *a,**k:[opening,partial,closing])
    result=StatsEngine().get_account_statistics()
    assert result['total_trades']==1
    assert result['net_profit']==pytest.approx(20.5)
    assert result['trades'][0]['volume']==pytest.approx(.1)


def test_expired_gui_proposal_cannot_be_approved(monkeypatch):
    import ast
    from pathlib import Path
    # Exercise the actual callback without constructing a native chart window.
    source=Path('frontend/controllers/chart/chart_canvas.py').read_text(encoding='utf-8')
    node=next(n for n in ast.walk(ast.parse(source)) if isinstance(n,ast.FunctionDef) and n.name=='_on_approve')
    window=NS(order_proposal_active=True,is_live_position=False,_signal_expiry_remaining=0)
    namespace={'window':window}
    exec(compile(ast.Module(body=[node],type_ignores=[]),'<chart approval>','exec'),namespace)
    send=Mock()
    monkeypatch.setattr(mt5,'order_send',send)
    namespace['_on_approve']()
    assert window.order_proposal_active is False
    send.assert_not_called()


def test_recovery_requires_verified_account(monkeypatch):
    from backend.core.state_recovery import StateRecoveryManager
    monkeypatch.setattr(mt5,'account_info',lambda:None)
    monkeypatch.setattr(mt5,'positions_get',lambda:())
    db=DatabaseManager()
    assert StateRecoveryManager(db).reconcile_on_startup()['status']=='FAILED_ACCOUNT_UNVERIFIED'
    assert not db.get_open_trades()


def test_recovered_position_does_not_invent_initial_risk(monkeypatch):
    from backend.core.state_recovery import StateRecoveryManager
    pos=NS(ticket=9,identifier=8,symbol='XAUUSD',type=0,volume=.1,price_open=2000.,sl=2005.,tp=2020.,time=1000,magic=999999)
    monkeypatch.setattr(mt5,'account_info',lambda:NS(login=1,server='test'))
    monkeypatch.setattr(mt5,'positions_get',lambda:[pos])
    db=DatabaseManager()
    assert StateRecoveryManager(db).reconcile_on_startup()['recovered_orphans']==1
    assert db.get_open_trades()[0]['initial_sl']==0


def test_news_partial_close_requires_durable_marker(broker,monkeypatch):
    engine,execution,_=defense_setup(broker,monkeypatch,2007)
    monkeypatch.setattr(DatabaseManager(),'set_system_state',lambda *a:False)
    assert engine.evaluate_pre_news_defense()==[]
    execution.close_position.assert_not_called()
