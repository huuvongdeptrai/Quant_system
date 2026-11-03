"""Durable admission for every MT5 entry path (GUI, worker and manual orders).

Broker calls are never held inside a SQLite transaction. An unresolved outcome
retains its reservation until an operator/broker reconciliation resolves it.
"""
import hashlib
import json
import math
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING

from backend.infrastructure.brokers.mt5_safe import mt5
from backend.database.db_manager import DatabaseManager
from backend.core.engine_config import BotRunConfig
from backend.core.risk_manager import RiskManager
from backend.core.circuit_breaker_guard import CircuitBreakerGuard
from backend.core.session_filter import SessionFilter
from backend.core.event_risk_engine import EventRiskEngine


class TradingCommandService:
    _lock = threading.RLock()
    _runtime = None
    _emergency_halt = False

    @classmethod
    def register_runtime(cls, runtime):
        with cls._lock:
            cls._runtime = runtime
            cls._emergency_halt = False

    @classmethod
    def emergency_halt(cls):
        with cls._lock:
            cls._emergency_halt = True
            if cls._runtime:
                cls._runtime.is_running = False

    def __init__(self, execution, db=None):
        self.execution = execution
        self.db = db or DatabaseManager()

    @staticmethod
    def _config(runtime):
        if runtime is not None:
            return BotRunConfig.from_dict({**runtime.config.to_dict(), **{
                k: getattr(runtime, k, getattr(runtime.config, k))
                for k in ('risk_per_trade','max_daily_loss','max_drawdown','max_losing_streak',
                          'max_open_trades','max_spread','slippage','close_friday',
                          'news_filter_enabled','news_pause_mins','execution_mode','trade_mode',
                          'allowed_sessions','timeframe','gate_mode')
            }})
        path = Path(__file__).resolve().parents[2] / 'config' / 'settings.json'
        return BotRunConfig.from_dict(json.loads(path.read_text(encoding='utf-8')) if path.exists() else {})

    @staticmethod
    def _error(message, status='error'):
        return {'status':status, 'msg':message}

    def submit(self, symbol, is_buy, volume, sl_price, tp_price, comment='VECTRA', magic=None,
               max_retries=3, risk_pct=None, signal_key=None, approval=False,
               strategy_id=None, pending_type=None, pending_price=None):
        # One process-wide admission lock also prevents a Stop/Flatten racing a new entry.
        with self._lock, mt5._session_lock:
            try:
                return self._submit(symbol,is_buy,volume,sl_price,tp_price,comment,magic,
                    risk_pct,signal_key,approval,strategy_id,pending_type,pending_price)
            except Exception as exc:
                return self._error(f'Entry blocked: {exc}')

    def _submit(self,symbol,is_buy,volume,sl,tp,comment,magic,risk_pct,signal_key,approval,
                strategy_id,pending_type,pending_price):
        if not isinstance(is_buy,bool) or not all(math.isfinite(float(x)) for x in (volume,sl,tp)) or volume<=0 or sl<=0 or tp<=0:
            return self._error('Invalid volume or protective stops')
        runtime = self._runtime
        config = self._config(runtime)
        manual = magic == 0 or 'manual' in comment.lower()
        if self._emergency_halt:
            return self._error('Emergency entry halt is active')
        if not manual:
            if approval:
                if config.execution_mode.value != 'SEMI-AUTO':
                    return self._error('Approval is only valid in SEMI-AUTO mode')
            elif runtime is None or not runtime.is_running or config.execution_mode.value != 'FULL-AUTO':
                return self._error('Autonomous execution is not armed')
        terminal, account = mt5.terminal_info(), mt5.account_info()
        if terminal is None or not terminal.connected or not terminal.trade_allowed or account is None:
            return self._error('Verified broker connection is required')
        account_key = self.db.bind_account(account.login, account.server)
        if config.trade_mode.value == ('SHORT_ONLY' if is_buy else 'LONG_ONLY'):
            return self._error('Direction is disabled')
        guard = CircuitBreakerGuard(self.db, config.max_daily_loss, config.max_drawdown,
                                    config.max_losing_streak, bot_magic=self.execution.magic)
        if guard.evaluate_circuit_breaker():
            return self._error('Circuit breaker is active')
        if not SessionFilter(list(config.allowed_sessions),config.close_friday).is_session_allowed(symbol)[0]:
            return self._error('Session is closed')
        events = EventRiskEngine(self.execution,pause_window_mins=config.news_pause_mins,
                                 user_max_spread=config.max_spread)
        if not events.check_spread_normalization(symbol)[0]:
            return self._error('Spread is unavailable or exceeds limit')
        if config.news_filter_enabled and events.check_news_impact_for_symbol(symbol)[0]:
            return self._error('News blackout')
        positions, orders = mt5.positions_get(), mt5.orders_get()
        if positions is None or orders is None:
            return self._error('Broker exposure is unavailable')
        if not manual and (any(p.symbol == symbol for p in positions) or any(o.symbol == symbol for o in orders)):
            return self._error('Existing position or pending order')
        # Count an unresolved symbol once even if its order/position is already visible.
        visible_symbols = {p.symbol for p in positions} | {o.symbol for o in orders}
        reserved_symbols = {i['symbol'] for i in self.db.get_unresolved_intents()}
        reserved_slots = len(reserved_symbols - visible_symbols)
        if not manual and (len(positions)+len(orders)+reserved_slots >= config.max_open_trades):
            return self._error('Capacity or unresolved execution blocks entry')
        elif manual and (len(positions)+len(orders) >= config.max_open_trades):
            return self._error(f'Max open trades limit reached ({len(positions)+len(orders)}/{config.max_open_trades})')
        if not manual and self.db.has_unresolved_intent(symbol):
            return self._error('Capacity or unresolved execution blocks entry')
        if not manual and any(t['symbol']==symbol for t in self.db.get_open_trades()):
            return self._error('Persisted position requires reconciliation')
        info, tick = mt5.symbol_info(symbol), mt5.symbol_info_tick(symbol)
        if info is None or tick is None or tick.bid<=0 or tick.ask<=0:
            return self._error('Quote unavailable')
        tick_time = getattr(tick,'time',0)
        broker_offset = int(round((tick_time - time.time()) / 3600.0)) * 3600
        broker_now = time.time() + broker_offset
        if not isinstance(tick_time,(int,float)) or broker_now-tick_time > 120 or tick_time-broker_now>5:
            return self._error('Quote is stale or has an invalid timestamp')
        price = float(pending_price if pending_type else (tick.ask if is_buy else tick.bid))
        if not math.isfinite(price) or price<=0 or not (sl<price<tp if is_buy else tp<price<sl):
            return self._error('Invalid entry/SL/TP orientation')
        if pending_type:
            valid_type = pending_type in ('BUY_LIMIT','SELL_LIMIT','BUY_STOP','SELL_STOP')
            correct_side = {'BUY_LIMIT':price<tick.ask,'BUY_STOP':price>tick.ask,
                            'SELL_LIMIT':price>tick.bid,'SELL_STOP':price<tick.bid}.get(pending_type,False)
            if not valid_type or not correct_side:
                return self._error('Invalid pending order price/type')
        step = Decimal(str(info.trade_tick_size))
        if step <= 0:
            return self._error('Invalid price tick size')
        minimum = max(0,float(info.trade_stops_level))*float(info.point)
        reference = price if pending_type else (tick.bid if is_buy else tick.ask)
        sl = min(sl,reference-minimum-float(step)) if is_buy else max(sl,reference+minimum+float(step))
        tp = max(tp,reference+minimum+float(step)) if is_buy else min(tp,reference-minimum-float(step))
        def snap(v,up):
            return float((Decimal(str(v))/step).to_integral_value(rounding=ROUND_CEILING if up else ROUND_FLOOR)*step)
        sl,tp=snap(sl,not is_buy),snap(tp,is_buy)
        selected_risk = config.risk_per_trade if risk_pct is None else min(config.risk_per_trade,float(risk_pct))
        if not math.isfinite(selected_risk) or selected_risk<=0:
            return self._error('Invalid risk budget')
        # Include maximum configured entry deviation in the pre-trade loss estimate.
        adverse_entry = price + (1 if is_buy else -1)*config.slippage*info.point
        risk_distance = abs(adverse_entry-sl)
        lot = min(float(volume),RiskManager().calculate_lot_size(symbol,risk_distance,selected_risk))
        lot = self.execution.normalize_volume(symbol,lot)
        if lot<=0:
            return self._error('Risk budget cannot fund minimum volume')
        action = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
        margin = mt5.order_calc_margin(action,symbol,lot,price)
        loss = mt5.order_calc_profit(action,symbol,lot,adverse_entry,sl)
        if not isinstance(margin,(int,float)) or not isinstance(loss,(int,float)) or not math.isfinite(margin) or not math.isfinite(loss):
            return self._error('Broker margin/loss calculation unavailable')
        budget=float(account.balance)*selected_risk/100
        if margin>account.margin_free or abs(loss)>budget+1e-6:
            return self._error('Margin or loss budget exceeded')
        if not manual:
            from backend.infrastructure.ai_engines.ai.decision_gate import DecisionGate
            bars=mt5.copy_rates_from_pos(symbol,config.timeframe,1,300)
            gate=DecisionGate().evaluate(symbol,'BUY' if is_buy else 'SELL',timeframe=config.timeframe,
                gate_mode=config.gate_mode.value,rates=bars,strategy_id=strategy_id or config.strategy_id,
                enable_meta_labeling=getattr(config, 'enable_meta_labeling', True))
            if gate.get('decision') != ('BUY' if is_buy else 'SELL'):
                return self._error(gate.get('reason','Decision gate rejected entry'))
            multiplier=float(gate.get('size_multiplier',1))
            if not math.isfinite(multiplier) or not 0<multiplier<=1:
                return self._error('Invalid gate sizing')
            # Never increase a previously sized request.
            cap=RiskManager().calculate_lot_size(symbol,risk_distance,selected_risk*multiplier)
            lot=self.execution.normalize_volume(symbol,min(lot,cap))
            if lot<=0:
                return self._error('Scaled budget cannot fund minimum volume')
            if gate.get('trade_mode')=='SCALP_PULLBACK':
                target=abs(price-sl)*float(gate.get('tp_limit_r',1.5))
                tp=min(tp,price+target) if is_buy else max(tp,price-target)
        # Recheck identity before reserving or sending. Stop and Flatten share this lock.
        latest=mt5.account_info()
        if latest is None or (latest.login,latest.server)!=(account.login,account.server):
            return self._error('Account changed during validation')
        if not manual and approval and self._config(runtime).execution_mode.value!='SEMI-AUTO':
            return self._error('Approval mode changed during validation')
        if not manual and not approval and (not runtime.is_running or
                str(runtime.execution_mode if hasattr(runtime,'execution_mode') else runtime.config.execution_mode.value)!='FULL-AUTO' or
                getattr(getattr(runtime,"circuit_guard",None),"circuit_breaker_active",False)):
            return self._error('Trading stopped during pre-trade checks')
        self.execution.slippage=config.slippage
        payload=dict(symbol=symbol,is_buy=is_buy,volume=lot,price=price,sl=sl,tp=tp,
                     comment=comment,strategy_id=strategy_id or config.strategy_id,
                     risk_pct=selected_risk, pending_type=pending_type, magic=0 if manual else
                     (self.execution.magic if magic is None else magic), manual=manual)
        if not manual:
            payload['holding_policy'] = {'timeframe':config.timeframe, 'max_holding_bars':20}
        if signal_key is None:
            if manual:
                signal_key=json.dumps(["MANUAL",symbol,time.time_ns(),is_buy,pending_type])
            else:
                bars=mt5.copy_rates_from_pos(symbol,config.timeframe,1,1)
                if bars is None or len(bars)==0:
                    return self._error('Signal timestamp unavailable')
                signal_key=json.dumps([strategy_id or config.strategy_id,symbol,config.timeframe,int(bars[-1]['time']),is_buy,manual,pending_type])
        key=hashlib.sha256(str(signal_key).encode()).hexdigest()
        payload['broker_tag']='V2_'+key[:20]
        intent=self.db.reserve_intent(key,symbol,payload)
        if not intent:
            return self._error('Signal already submitted or execution unresolved')
        try:
            if pending_type:
                result=self.execution._execute_pending_order_raw(symbol,pending_type,price,lot,sl,tp,
                    comment=payload['broker_tag'],magic=0 if manual else magic,max_retries=1)
            else:
                result=self.execution._execute_market_order_raw(symbol,is_buy,lot,sl,tp,
                    comment=payload['broker_tag'],magic=0 if manual else magic,max_retries=1,validated_price=price)
            result=result or self._error('Missing broker result','unknown')
            payload['order_id']=result.get('order_id') or result.get('ticket')
            result['intent_id']=intent
            state='UNKNOWN' if result['status']=='unknown' else ('FILLED' if result['status']=='success' else 'REJECTED')
            if result.get('partial'):
                state='PARTIAL'
            if state in ('FILLED','PARTIAL') and not pending_type:
                live=mt5.positions_get(symbol=symbol)
                deal_id=result.get('deal_id')
                deals=mt5.history_deals_get(ticket=deal_id) if deal_id else None
                pid=int(deals[0].position_id) if deals else None
                pos=next((p for p in (live or ()) if pid is not None and p.identifier==pid),None)
                if pos is None:
                    state='UNKNOWN'
                    result['status']='unknown'
                    result['msg']='Fill reported; position identity requires reconciliation'
                else:
                    self.db.record_deals(deals)
                    ok=self.db.record_open_trade(pos.ticket,symbol,'BUY' if is_buy else 'SELL',pos.volume,
                        pos.price_open,sl=pos.sl,tp=pos.tp,comment=comment,position_id=pos.identifier,
                        broker_order_id=result['order_id'],magic=pos.magic,strategy_id=payload['strategy_id'],
                        initial_sl=payload['sl'], open_time=datetime.fromtimestamp(
                            getattr(pos,'time',time.time()),timezone.utc).isoformat())
                    if not ok:
                        raise RuntimeError('Broker filled but position persistence failed')
                    if not self.db.attach_execution_policy(pos.ticket,pos.identifier,payload,result['order_id']):
                        raise RuntimeError('Broker filled but execution policy persistence failed')
                    result.update(ticket=pos.ticket,position_id=pos.identifier,volume=pos.volume,
                                  price=pos.price_open,sl=pos.sl,tp=pos.tp)
            if pending_type and result.get('status')=='success':
                state='FILLED' if manual else 'UNKNOWN'  # Manual finishes immediately; bot awaits reconciliation.
            self.db.finish_intent(intent,state,{**result,'request':payload})
            return result
        except Exception as exc:
            try:
                self.db.finish_intent(intent,'UNKNOWN',{'error':str(exc),'request':payload})
            except Exception:
                pass  # The durable SUBMITTING row still blocks entry after restart.
            return self._error(f'Execution requires reconciliation: {exc}','unknown')

    def modify_pending(self, ticket, price, sl=None, tp=None):
        """Re-admit fixed-volume amendments; omission preserves existing protection.

        A durable amendment marker precedes the RPC. An ambiguous amendment cannot
        be retried until reconciliation confirms the target or a terminal order.
        """
        with self._lock, mt5._session_lock:
            intent = None
            marker = None
            try:
                account = mt5.account_info()
                terminal = mt5.terminal_info()
                if account is None or terminal is None or not terminal.connected or not terminal.trade_allowed:
                    return self._error('Verified broker connection is required')
                self.db.bind_account(account.login, account.server)
                orders = mt5.orders_get(ticket=int(ticket))
                if orders is None or len(orders) != 1:
                    return self._error('Pending order unavailable')
                order = orders[0]
                symbol = order.symbol
                types = {mt5.ORDER_TYPE_BUY_LIMIT:True, mt5.ORDER_TYPE_BUY_STOP:True,
                         mt5.ORDER_TYPE_SELL_LIMIT:False, mt5.ORDER_TYPE_SELL_STOP:False}
                if order.type not in types:
                    return self._error('Unsupported pending order type')
                is_buy = types[order.type]
                volume = float(order.volume_current)
                old_price, old_sl, old_tp = float(order.price_open), float(order.sl), float(order.tp)
                price, sl, tp = float(price), old_sl if sl is None else float(sl), old_tp if tp is None else float(tp)
                if not all(math.isfinite(v) and v > 0 for v in (price,sl,tp,volume)):
                    return self._error('Protective stops cannot be removed by amendment')
                if not (sl < price < tp if is_buy else tp < price < sl):
                    return self._error('Invalid pending order geometry')
                config = self._config(self._runtime)
                info, tick = mt5.symbol_info(symbol), mt5.symbol_info_tick(symbol)
                if info is None or tick is None:
                    return self._error('Quote unavailable or stale')
                tick_time = getattr(tick, 'time', 0)
                broker_offset = int(round((tick_time - time.time()) / 3600.0)) * 3600
                broker_now = time.time() + broker_offset
                if not isinstance(tick_time, (int, float)) or abs(broker_now - tick_time) > 120:
                    return self._error('Quote unavailable or stale')
                step = float(info.trade_tick_size)
                if step <= 0 or any(abs(v/step-round(v/step))>1e-6 for v in (price,sl,tp)):
                    return self._error('Amendment prices must align with broker tick size')
                minimum = float(info.trade_stops_level)*float(info.point)
                quote = tick.ask if is_buy else tick.bid
                above = order.type in (mt5.ORDER_TYPE_BUY_STOP,mt5.ORDER_TYPE_SELL_LIMIT)
                if (price-quote if above else quote-price) < max(minimum,step)-1e-9:
                    return self._error('Pending price too close to market or on wrong side')
                if abs(price-sl)<minimum or abs(tp-price)<minimum:
                    return self._error('Pending stops too close')
                action = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
                adverse = price+(1 if is_buy else -1)*config.slippage*info.point
                loss = mt5.order_calc_profit(action,symbol,volume,adverse,sl)
                old_adverse = old_price+(1 if is_buy else -1)*config.slippage*info.point
                old_loss = mt5.order_calc_profit(action,symbol,volume,old_adverse,old_sl) if old_sl>0 else None
                if not isinstance(loss,(int,float)) or not math.isfinite(loss) or loss>=0:
                    return self._error('Broker loss estimate unavailable')
                old_loss = abs(old_loss) if isinstance(old_loss,(int,float)) and math.isfinite(old_loss) and old_sl>0 else float('inf')
                increases_risk = abs(loss)>old_loss+1e-6
                # Moving a pending entry can activate exposure even when its SL
                # loss is smaller. Only protection-only changes bypass a halt.
                requires_admission = increases_risk or abs(price-old_price)>1e-9
                intent = self.db.find_order_intent(ticket,getattr(order,'comment',''))
                previous = json.loads(intent['payload']) if intent else {}
                if previous.get('amendment',{}).get('pending'):
                    return self._error('Prior amendment requires reconciliation')
                request = dict(previous.get('request',previous))
                if requires_admission:
                    if self._emergency_halt or (self._runtime is not None and not self._runtime.is_running):
                        return self._error('Trading halt blocks risk-increasing amendment')
                    guard = CircuitBreakerGuard(self.db,config.max_daily_loss,config.max_drawdown,
                                                config.max_losing_streak,bot_magic=self.execution.magic)
                    if guard.evaluate_circuit_breaker():
                        return self._error('Circuit breaker blocks risk increase')
                    if not SessionFilter(list(config.allowed_sessions),config.close_friday).is_session_allowed(symbol)[0]:
                        return self._error('Session is closed')
                    events = EventRiskEngine(self.execution,pause_window_mins=config.news_pause_mins,
                                             user_max_spread=config.max_spread)
                    if not events.check_spread_normalization(symbol)[0]:
                        return self._error('Spread blocks risk increase')
                    if config.news_filter_enabled and events.check_news_impact_for_symbol(symbol)[0]:
                        return self._error('News blackout')
                    risk = min(config.risk_per_trade,float(request.get('risk_pct',config.risk_per_trade)))
                    if not math.isfinite(risk) or abs(loss)>account.balance*risk/100+1e-6:
                        return self._error('Amendment exceeds loss budget; reduce order volume by cancel/recreate')
                    margin = mt5.order_calc_margin(action,symbol,volume,price)
                    if not isinstance(margin,(int,float)) or not math.isfinite(margin) or margin>account.margin_free:
                        return self._error('Margin unavailable or insufficient')
                latest = mt5.account_info()
                if latest is None or (latest.login,latest.server)!=(account.login,account.server):
                    return self._error('Account changed during amendment validation')
                request.setdefault('symbol',symbol)
                request.setdefault('broker_tag',getattr(order,'comment',''))
                request['order_id']=int(ticket)
                target = {**request,'price':price,'sl':sl,'tp':tp,'volume':volume}
                if intent is None:
                    intent_id = self.db.reserve_intent('amend:'+str(ticket)+':'+str(time.time_ns()),symbol,request)
                    if not intent_id:
                        return self._error('Unresolved execution blocks amendment')
                    intent = {'intent_id':intent_id}
                marker = {'request':request,'order_id':int(ticket),'amendment':{
                    'pending':True,'target':target,'before':{'price':old_price,'sl':old_sl,'tp':old_tp}}}
                self.db.finish_intent(intent['intent_id'],'UNKNOWN',marker)
                result = self.execution._modify_pending_order_raw(ticket,price,sl,tp)
                if result['status']=='success':
                    self.db.finish_intent(intent['intent_id'],'UNKNOWN',{'request':target,'order_id':int(ticket)})
                elif result['status']=='error':
                    self.db.finish_intent(intent['intent_id'],'UNKNOWN',{'request':request,'order_id':int(ticket)})
                return result
            except Exception as exc:
                # SUBMITTING/UNKNOWN remains durable even if post-RPC persistence fails.
                return self._error(f'Amendment requires reconciliation: {exc}', 'unknown' if marker else 'error')
