"""Chronological validation and independent portfolio replay for Meta-Labeling.

The seed model is trained on 2022. Thresholds are ranked ONLY on 2023-2024;
one frozen threshold is evaluated on 2025-2026. Each forecast year's model
uses completed labels strictly before a five-venue-bar boundary gap.

Source OHLC is required. Cached trade PnLs are never used as a portfolio simulator.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

from backend.backtest.backtest_ict_pro import EventDrivenBacktester
from backend.core.meta_features import FEATURE_COLUMNS, FEATURE_VERSION, build_meta_features
from backend.core.strategies.wyckoff_vectorized import WyckoffMomentumStrategy

PARAMETERS = dict(objective='binary',metric='binary_logloss',learning_rate=.03,
                  num_leaves=12,max_depth=3,min_child_samples=15,feature_fraction=.8,
                  verbosity=-1,seed=42,num_threads=1)
STRATEGY_PARAMETERS = dict(vol_mult=1.10,adx_threshold=16.,min_headroom_atr=.4,session_filter=False)


class ResearchWyckoff(WyckoffMomentumStrategy):
    def __init__(self):
        super().__init__(STRATEGY_PARAMETERS)

    def analyze(self, window, macro_context=None):
        result=super().analyze(window,macro_context)
        if not 6<=pd.Timestamp(window['time'].iloc[-1]).hour<=21:
            result.signal='HOLD'
        return result


def validate_bars(df):
    required={'time','open','high','low','close','tick_volume'}
    if not required.issubset(df.columns):
        raise ValueError(f'OHLC source is required; missing {sorted(required-set(df.columns))}')
    df=df.copy()
    df['time']=pd.to_datetime(df['time'],unit='s' if pd.api.types.is_numeric_dtype(df['time']) else None,utc=True).dt.tz_localize(None)
    if not df['time'].is_monotonic_increasing or df['time'].duplicated().any():
        raise ValueError('Bars must have unique ascending UTC timestamps')
    intervals=df['time'].diff().dropna()
    if intervals.empty or intervals.mode().iloc[0]!=pd.Timedelta(minutes=15):
        raise ValueError('The versioned model pipeline requires M15 bars')
    volumes=df['tick_volume'].to_numpy(float)
    if not np.isfinite(volumes).all() or (volumes<0).any():
        raise ValueError('Tick volume must be finite and nonnegative')
    prices=df[['open','high','low','close']].to_numpy(float)
    if not np.isfinite(prices).all() or (prices<=0).any():
        raise ValueError('Prices must be finite and positive')
    if ((df['high']<df[['open','close','low']].max(axis=1)) |
            (df['low']>df[['open','close','high']].min(axis=1))).any():
        raise ValueError('Invalid OHLC geometry')
    if len(df)<150:
        raise ValueError('At least 150 completed bars are required')
    return df.reset_index(drop=True)


def harvest_samples(df, symbol='XAUUSD', strategy_factory=ResearchWyckoff):
    report=EventDrivenBacktester(strategy_factory()).run(df,symbol=symbol)
    index={pd.Timestamp(t):i for i,t in enumerate(df['time'])}
    rows=[]
    for trade in report.trade_records:
        signal_time=pd.Timestamp(trade['signal_time'])
        i=index[signal_time]
        feature=build_meta_features(df.iloc[max(0,i-299):i+1],trade['side'])
        exit_index=index[pd.Timestamp(trade['exit_time'])]
        label_end=(df['time'].iloc[exit_index+1] if exit_index+1<len(df) else
                   df['time'].iloc[exit_index]+pd.Timedelta(minutes=15))
        rows.append({**feature,'signal_time':signal_time,'entry_time':pd.Timestamp(trade['entry_time']),
                     'exit_time':pd.Timestamp(trade['exit_time']),'label_end_time':label_end,
                     'outcome':int(trade['outcome']=='TP')})
    return pd.DataFrame(rows)


def training_before(samples, bars, forecast_start, embargo_bars=5):
    """Purge label overlaps and leave an explicit pre-test venue-bar gap.

    For strictly expanding past-only training this is a boundary gap; there are
    no future-side training rows on which a post-test embargo could operate.
    """
    if embargo_bars<0:
        raise ValueError('embargo_bars must be nonnegative')
    forecast_start=pd.Timestamp(forecast_start)
    first=int(bars['time'].searchsorted(forecast_start))
    if first<embargo_bars or first>=len(bars):
        raise ValueError('Insufficient bars at forecast boundary')
    cutoff=bars['time'].iloc[first-embargo_bars]
    label_ends=samples['label_end_time'] if 'label_end_time' in samples else samples['exit_time']
    training=samples[(samples['signal_time']<cutoff) & (label_ends<cutoff)].copy()
    return training,cutoff


def fit_model(training):
    import lightgbm as lgb
    if training.empty or training['outcome'].nunique()<2:
        raise ValueError('Training requires completed labels from both classes')
    return lgb.train(PARAMETERS,lgb.Dataset(training[FEATURE_COLUMNS],label=training['outcome']),num_boost_round=80)


def replay_portfolio(bars,models,threshold,start,end,symbol='XAUUSD',strategy_factory=ResearchWyckoff):
    """Regenerate signals, risk sizing and MTM after filtering, with independent cash."""
    subset=bars[bars['time']<pd.Timestamp(end)].copy()
    predictions=[]
    def allow(window,result):
        moment=pd.Timestamp(window['time'].iloc[-1])
        # Forecast year is the earliest available execution bar, not label end.
        next_index=int(subset['time'].searchsorted(moment,side='right'))
        forecast_year=int(subset['time'].iloc[next_index].year)
        model=models.get(forecast_year)
        if model is None:
            raise ValueError(f'No past-only model for {forecast_year}')
        features=build_meta_features(window,result['signal'])
        probability=float(model.predict(np.array([[features[c] for c in FEATURE_COLUMNS]]))[0])
        if not np.isfinite(probability) or not 0<=probability<=1:
            raise ValueError('Invalid forecast probability')
        predictions.append(dict(signal_time=str(moment),probability=probability,threshold=threshold))
        return probability>=threshold
    tester=EventDrivenBacktester(strategy_factory(),initial_balance=100000.,risk_per_trade_pct=1.,
                                 commission_per_lot=7.,slippage_pts=20.,max_holding_bars=20)
    report=tester.run(subset,symbol=symbol,trading_start=start,
                      signal_filter=None if threshold==0 else allow)
    if report is None:
        raise ValueError('Insufficient bars for independent replay')
    # Drop warmup-only cash timestamps; report PnL and MTM are computed by the engine.
    report.equity_curve=[v for t,v in zip(report.equity_times,report.equity_curve) if pd.Timestamp(t)>=pd.Timestamp(start)]
    return report,predictions


def summarize(report):
    dd=report.max_drawdown_pct/100
    return dict(trades=report.total_trades,wins=report.win_trades,losses=report.loss_trades,
                net_profit_usd=report.total_net_profit,max_drawdown_pct=report.max_drawdown_pct,
                profit_factor=report.profit_factor,winrate_pct=report.win_rate_pct,
                objective=(report.total_net_profit/report.initial_balance)/dd if dd>0 else None)


def choose_threshold(validation):
    candidates=[(float(t),r) for t,r in validation.items() if float(t)>0 and r['trades']>0 and r['objective'] is not None]
    if not candidates:
        raise ValueError('Validation has no eligible threshold; do not evaluate/select using test results')
    feasible=[item for item in candidates if item[1]['max_drawdown_pct']<=10]
    if not feasible:
        raise ValueError('No validation threshold meets the 10% drawdown cap; revise on validation only')
    return max(feasible,key=lambda item:(item[1]['objective'],-item[0]))[0]


def run_pipeline(bars,output,symbol='XAUUSD',export_model=None,strategy_factory=ResearchWyckoff):
    bars=validate_bars(bars)
    # Identity covers values and UTC timestamps, not just a mutable filename.
    digest=hashlib.sha256(pd.util.hash_pandas_object(bars,index=False).values.tobytes()).hexdigest()
    samples=harvest_samples(bars,symbol,strategy_factory)
    if samples.empty:
        raise ValueError('No primary events; no model or performance report can be validated')
    models={};splits={}
    for year in (2023,2024,2025,2026):
        training,cutoff=training_before(samples,bars,f'{year}-01-01')
        models[year]=fit_model(training)
        splits[str(year)]=dict(train_samples=len(training),label_end_exclusive=str(cutoff),boundary_gap_bars=5)
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    validation={}
    for threshold in (0.,.32,.34,.36,.38,.40,.42):
        report,_=replay_portfolio(bars,models,threshold,'2023-01-01','2025-01-01',symbol,strategy_factory)
        validation[str(threshold)]=summarize(report)
    # Freeze selection BEFORE running the independent test portfolio.
    threshold=choose_threshold(validation)
    manifest=dict(dataset_sha256=digest,feature_version=FEATURE_VERSION,feature_columns=FEATURE_COLUMNS,
                  symbol=symbol,timeframe='M15',holding_bars=20,parameters=PARAMETERS,
                  strategy_parameters=STRATEGY_PARAMETERS,validation_start='2023-01-01',
                  validation_end_exclusive='2025-01-01',test_start='2025-01-01',
                  test_end_exclusive='2027-01-01',splits=splits,threshold=threshold,validation=validation)
    (output/'frozen_validation_manifest.json').write_text(json.dumps(manifest,indent=2,allow_nan=False))
    tests={}
    for operating in (0.,threshold):
        report,predictions=replay_portfolio(bars,models,operating,'2025-01-01','2027-01-01',symbol,strategy_factory)
        tests[str(operating)]=summarize(report)
        pd.DataFrame(report.trade_records).to_csv(output/f'test_trades_{operating}.csv',index=False)
        pd.DataFrame(predictions).to_csv(output/f'test_predictions_{operating}.csv',index=False)
    manifest['test']=tests
    manifest['source_end']=str(bars['time'].max())
    (output/'walk_forward_results.json').write_text(json.dumps(manifest,indent=2,allow_nan=False))
    if export_model:
        # This deployment fit is separate from every model used in the OOS reports.
        deployment=fit_model(samples)
        path=Path(export_model);path.parent.mkdir(parents=True,exist_ok=True)
        deployment.save_model(str(path))
        metadata=dict(strategy_id='builtin_wyckoff',feature_version=FEATURE_VERSION,
                      feature_cols=FEATURE_COLUMNS,threshold=threshold,symbol=symbol,timeframe='M15',
                      max_holding_bars=20,dataset_sha256=digest,trained_from=str(samples.signal_time.min()),
                      trained_through=str(samples.label_end_time.max()),total_samples=len(samples),
                      description='Deployment fit after chronological evaluation; not the models used for OOS forecasts')
        path.with_suffix('.json').write_text(json.dumps(metadata,indent=2,allow_nan=False))
    return manifest


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--data',help='Immutable CSV/parquet OHLC source with completed M15 bars')
    source.add_argument('--mt5',action='store_true',help='Explicitly obtain completed bars from local MT5')
    parser.add_argument('--output',default='research/verified_walk_forward')
    parser.add_argument('--symbol',default='XAUUSD')
    parser.add_argument('--export-model',help='Optional deployment .lgb path; never changes the bundled model by default')
    args=parser.parse_args(argv)
    if args.data:
        path=Path(args.data)
        bars=pd.read_parquet(path) if path.suffix=='.parquet' else pd.read_csv(path)
    else:
        from backend.infrastructure.brokers.mt5_safe import mt5
        if not mt5.initialize():
            raise RuntimeError('MT5 initialization failed')
        try:
            rates=mt5.copy_rates_from_pos(args.symbol,mt5.TIMEFRAME_M15,1,99999)
            if rates is None:
                raise RuntimeError('Completed OHLC source unavailable')
            bars=pd.DataFrame(rates)
        finally:
            mt5.shutdown()
    result=run_pipeline(bars,args.output,args.symbol,args.export_model)
    print(json.dumps({'threshold':result['threshold'],'test':result['test']},indent=2))


if __name__=='__main__':
    main()
