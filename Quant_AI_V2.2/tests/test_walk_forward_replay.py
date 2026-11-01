"""Numeric checks for independent sizing, MTM and chronological label exclusion."""
from types import SimpleNamespace as NS
import numpy as np
import pandas as pd
import pytest
from backend.backtest.backtest_ict_pro import EventDrivenBacktester
from research.walk_forward_pipeline import training_before,choose_threshold,validate_bars,fit_model
from backend.core.meta_features import FEATURE_COLUMNS


def bars(n=180):
    return pd.DataFrame(dict(time=pd.date_range('2026-01-05',periods=n,freq='15min'),
        open=np.full(n,100.),high=np.full(n,101.),low=np.full(n,99.),close=np.full(n,100.),tick_volume=np.full(n,100)))


class TwoSignals:
    def analyze(self,window,macro_context=None):
        t=window.time.iloc[-1]
        minute=(t-pd.Timestamp('2026-01-05')).total_seconds()/900
        if minute==99:
            return dict(signal='BUY',sl=90,tp=110)
        if minute==101:
            return dict(signal='SELL',sl=110,tp=90)
        return dict(signal='HOLD')


def test_filter_recalculates_volume_and_cash_instead_of_summing_base_pnl():
    df=bars()
    df.loc[100,['open','high','low','close']]=[100,101,90,100]
    df.loc[102,['open','high','low','close']]=[100,101,90,100]
    base=EventDrivenBacktester(TwoSignals(),commission_per_lot=0,slippage_pts=0).run(df)
    filtered=EventDrivenBacktester(TwoSignals(),commission_per_lot=0,slippage_pts=0).run(
        df,signal_filter=lambda window,res:res['signal']=='SELL')
    assert base.total_trades==2
    assert filtered.total_trades==1
    assert base.trade_records[1]['volume']==pytest.approx(.99)
    assert filtered.trade_records[0]['volume']==pytest.approx(1.)
    assert base.trade_records[1]['pnl']==pytest.approx(990.)
    assert filtered.total_net_profit==pytest.approx(1000.)


def test_validation_drawdown_includes_filtered_open_loss():
    df=bars()
    df.loc[101,['open','high','low','close']]=[100,101,91,92]
    class Once:
        used=False
        def analyze(self,window,macro_context=None):
            if self.used:return dict(signal='HOLD')
            self.used=True
            return dict(signal='BUY',sl=90,tp=120)
    report=EventDrivenBacktester(Once(),commission_per_lot=0,slippage_pts=0).run(
        df,signal_filter=lambda *a:True)
    assert report.total_net_profit==0
    assert report.max_drawdown_pct>0
    assert len(report.equity_times)==len(report.equity_curve)


def test_boundary_gap_uses_venue_bars_across_weekend_and_purges_label_ends():
    times=list(pd.date_range('2022-12-30 19:30',periods=10,freq='15min'))
    times+=list(pd.date_range('2023-01-02',periods=10,freq='15min'))
    source=pd.DataFrame({'time':times})
    samples=pd.DataFrame({'signal_time':[times[0],times[1],times[9]],
                          'exit_time':[times[4],times[5],times[11]],'outcome':[0,1,0]})
    training,cutoff=training_before(samples,source,'2023-01-01',embargo_bars=5)
    assert cutoff==times[5]
    assert len(training)==1 and training.iloc[0]['exit_time']==times[4]


def test_threshold_selection_rejects_empty_or_risk_cap_failure():
    val={'0.0':dict(trades=100,objective=3,max_drawdown_pct=3),
         '.32':dict(trades=10,objective=.1,max_drawdown_pct=8),
         '.38':dict(trades=8,objective=.3,max_drawdown_pct=7)}
    assert choose_threshold(val)==.38
    with pytest.raises(ValueError):
        choose_threshold({'.38':dict(trades=8,objective=.3,max_drawdown_pct=15)})


def test_raw_ohlc_required_not_cached_trade_pnl():
    with pytest.raises(ValueError,match='OHLC source'):
        validate_bars(pd.DataFrame({'pnl':[100,200],'pred_prob':[.5,.7]}))
    df=bars();df.loc[0,'low']=102
    with pytest.raises(ValueError,match='OHLC geometry'):
        validate_bars(df)


def test_training_contract_with_real_lightgbm():
    rng=np.random.default_rng(8)
    data=pd.DataFrame(rng.normal(size=(100,len(FEATURE_COLUMNS))),columns=FEATURE_COLUMNS)
    data['outcome']=[0,1]*50
    model=fit_model(data)
    pred=model.predict(data[FEATURE_COLUMNS])
    assert len(pred)==100 and np.isfinite(pred).all() and ((pred>=0)&(pred<=1)).all()


def test_m15_volume_contract_and_actual_label_availability():
    df=bars()
    df['time']=pd.date_range('2026-01-05',periods=len(df),freq='5min')
    with pytest.raises(ValueError,match='M15'):
        validate_bars(df)
    df=bars();df.loc[0,'tick_volume']=-1
    with pytest.raises(ValueError,match='volume'):
        validate_bars(df)
    source=pd.DataFrame({'time':pd.date_range('2022-12-31 20:00',periods=40,freq='15min')})
    boundary=pd.Timestamp('2023-01-01')
    first=int(source.time.searchsorted(boundary));cut=source.time.iloc[first-5]
    samples=pd.DataFrame({'signal_time':[source.time.iloc[0]],'exit_time':[cut-pd.Timedelta(minutes=15)],
                          'label_end_time':[cut]})
    training,_=training_before(samples,source,boundary)
    assert training.empty  # An exit-bar timestamp before cutoff is insufficient.
