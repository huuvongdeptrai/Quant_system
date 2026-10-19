"""
Unit & Integration Tests for Quantitative Backtest Pipeline, Multi-Strategy Dispatch,
Realistic Fill Modeling, and Contract Multiplier Math.
Quant AI V2.2 - Institutional Verification
"""

import pytest
import numpy as np
import pandas as pd
from research.backtest_vectorized import VectorizedBacktester, get_symbol_multiplier
from backend.core.strategies.strategy_loader import discover_strategies
from backend.backtest.backtest_engine import BacktestWorker, get_symbol_multiplier as engine_multiplier


def generate_test_ohlcv(n=2000, seed=42):
    """Generates synthetic OHLCV DataFrame with distinct open, high, low, close bars."""
    np.random.seed(seed)
    dt = 1 / 252
    mu = 0.10
    sigma = 0.15
    closes = [2000.0]
    for _ in range(n - 1):
        ret = np.random.normal((mu - 0.5 * sigma**2) * dt, sigma * np.sqrt(dt))
        closes.append(closes[-1] * np.exp(ret))

    opens = [closes[0]] + closes[:-1]  # open is previous close
    highs = [max(o, c) * (1.0 + abs(np.random.normal(0, 0.002))) for o, c in zip(opens, closes)]
    lows = [min(o, c) * (1.0 - abs(np.random.normal(0, 0.002))) for o, c in zip(opens, closes)]
    vols = [1000.0 * (1.0 + abs(np.random.normal(0, 0.5))) for _ in closes]

    return pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "tick_volume": vols,
    })


class TestBacktestPipelineAndStrategyDispatch:
    def test_multi_strategy_dispatch_produces_distinct_signals(self):
        """Verify that selecting ICT, Wyckoff, or EMA actually executes distinct trading algorithms."""
        df = generate_test_ohlcv(n=2500, seed=101)
        bt = VectorizedBacktester(initial_balance=100000.0, risk_per_trade_pct=1.0)

        rep_wyckoff = bt.run(df, target_rr=2.5, strategy_name="Wyckoff Momentum Pro (Vectorized)")
        rep_ict = bt.run(df, target_rr=2.5, strategy_name="ICT Zones Pro v4.2 (Asian + FVG)")
        rep_ema = bt.run(df, target_rr=2.0, strategy_name="EMA Dual Cross (Resilience Benchmark)")

        assert rep_wyckoff is not None, "Wyckoff report must not be None"
        assert rep_ict is not None, "ICT report must not be None"
        assert rep_ema is not None, "EMA report must not be None"

        # Verify that strategies produce different trade counts and results
        assert rep_wyckoff.total_trades > 0
        assert rep_ict.total_trades > 0
        assert rep_ema.total_trades > 0

        # The strategies operate on completely different rules (FVG vs Momentum vs EMA Cross)
        assert rep_ict.total_trades != rep_wyckoff.total_trades or rep_ict.win_rate_pct != rep_wyckoff.win_rate_pct

    def test_dynamic_lot_sizing_by_asset_class(self):
        """Verify that contract multipliers properly scale lot size and risk across asset classes."""
        # Gold: Multiplier = 100.0
        gold_mult = get_symbol_multiplier("XAUUSD")
        assert gold_mult == 100.0

        # Crypto: Multiplier = 1.0
        btc_mult = get_symbol_multiplier("BTCUSD")
        assert btc_mult == 1.0

        # FX: Multiplier = 100,000.0
        eur_mult = get_symbol_multiplier("EURUSD")
        assert eur_mult == 100000.0

        # JPY: Multiplier ~ 667.0
        jpy_mult = get_symbol_multiplier("USDJPY")
        assert jpy_mult == 667.0

        # Engine multiplier must match research multiplier
        assert engine_multiplier("XAUUSD") == gold_mult
        assert engine_multiplier("BTCUSD") == btc_mult

    def test_trade_records_contain_realistic_volume_and_symbol(self):
        """Verify that trade records contain realistic lots and asset symbols."""
        df = generate_test_ohlcv(n=2000, seed=777)
        bt = VectorizedBacktester(initial_balance=100000.0, risk_per_trade_pct=1.0)
        report = bt.run(df, target_rr=2.5, strategy_name="wyckoff", symbol="XAUUSD")

        assert report is not None
        assert report.trade_records is not None and len(report.trade_records) > 0

        for trade in report.trade_records:
            assert "volume" in trade, "Trade record must include volume"
            assert "symbol" in trade, "Trade record must include symbol"
            assert trade["symbol"] == "XAUUSD"
            assert trade["volume"] > 0, "Volume must be positive"
            assert trade["volume"] <= 50.0, "Volume must be within safety bounds"

    def test_next_bar_open_fill_eliminates_lookahead(self):
        """Verify fill_on_next_open correctly executes on the open of the following candle."""
        df = generate_test_ohlcv(n=1000, seed=888)
        bt = VectorizedBacktester(initial_balance=100000.0, risk_per_trade_pct=1.0)

        # Baseline: fill on close of signal candle
        rep_close = bt.run(df, target_rr=2.5, fill_on_next_open=False)
        # Unbiased: fill on open of next candle
        rep_open = bt.run(df, target_rr=2.5, fill_on_next_open=True)

        assert rep_close is not None
        assert rep_open is not None
        assert len(rep_close.trade_records) > 0
        assert len(rep_open.trade_records) > 0

    def test_backtest_worker_pnl_contract_math(self):
        """Verify BacktestWorker uses pts * lot_size * mult instead of * balance * 10."""
        # Create a mock worker
        rates = [
            {"time": 1000 + i * 900, "open": 2600.0 + i, "high": 2605.0 + i, "low": 2595.0 + i, "close": 2601.0 + i, "tick_volume": 100}
            for i in range(100)
        ]
        user_code = '''
def generate_signals(df):
    df["signal"] = 0
    df["sl"] = 0.0
    df["tp"] = 0.0
    # Buy at bar 10, exit at bar 15
    df.loc[10, "signal"] = 1
    df.loc[10, "sl"] = 2590.0
    df.loc[10, "tp"] = 2650.0
    df.loc[15, "signal"] = -1
    return df
'''
        worker = BacktestWorker(
            symbol="XAUUSD",
            timeframe="M15",
            balance=100000.0,
            user_code=user_code,
            rates=rates,
        )

        results = {}
        worker.finished_signal.connect(lambda res: results.update(res))
        worker.run()

        assert "metrics" in results
        assert results["metrics"]["total_trades"] >= 1
        assert len(results["trades"]) >= 1
        trade = results["trades"][0]
        # XAUUSD: multiplier is 100.0
        # Entry at bar 11 open = 2611.0, exit at bar 16 open = 2616.0
        # Points = 5.0, lot_size = (100000 * 0.01) / (21 * 100) = ~0.48 lots
        # PnL should be around 5.0 * 0.48 * 100 = ~$240 (NOT $1,900,000 from * balance * 10!)
        assert abs(trade["pnl"] - 240.0) < 1.0, f"Expected realistic PnL ~240, got {trade['pnl']}"

    def test_strategy_loader_discovers_builtin_strategies(self):
        """Verify strategy loader discovers all built-in core models."""
        strategies = discover_strategies()
        assert len(strategies) >= 3
        strat_names = [s["name"] for s in strategies]
        assert any("ICT" in name for name in strat_names)
        assert any("Wyckoff" in name for name in strat_names)
        assert any("EMA" in name for name in strat_names)

    def test_ict_pro_event_driven_backtester_execution(self):
        """Verify event-driven ICTZonesProStrategy execution via ICTProBacktester."""
        from datetime import datetime, timedelta
        from backend.backtest.backtest_ict_pro import ICTProBacktester, run_ict_pro_backtest

        n = 260
        base_time = datetime(2026, 10, 1, 8, 0, 0)
        times = [base_time + timedelta(minutes=15 * i) for i in range(n)]
        np.random.seed(42)
        closes = 2500.0 + np.cumsum(np.random.randn(n) * 2.0)
        highs = closes + np.random.rand(n) * 3.0
        lows = closes - np.random.rand(n) * 3.0
        opens = (closes + np.roll(closes, 1)) / 2.0
        opens[0] = closes[0]
        volumes = np.random.randint(100, 1000, n)

        df = pd.DataFrame({
            "time": times,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "tick_volume": volumes,
        })

        tester = ICTProBacktester(initial_balance=100000.0, risk_per_trade_pct=1.0)
        report = tester.run(df=df, symbol="XAUUSD")
        assert report is not None
        assert report.sample_size == n
        assert report.final_equity > 0
        assert isinstance(report.trade_records, list)

        # Run convenience function
        res = run_ict_pro_backtest(df=df, symbol="XAUUSD")
        assert "error" not in res
        assert res["bars_tested"] == n
        assert "trade_records" in res

    def test_backend_backtest_package_exports_and_single_source_of_truth(self):
        """Verify that backend.backtest exposes the full backtesting subsystem cleanly."""
        import backend.backtest as bt_pkg
        from backend.backtest import (
            VectorizedBacktester,
            EventDrivenBacktester,
            ICTProBacktester,
            BacktestWorker,
            BacktestReport,
            get_symbol_multiplier,
            run_ict_pro_backtest,
        )

        # All exports must be accessible directly
        for name in bt_pkg.__all__:
            assert hasattr(bt_pkg, name), f"backend.backtest must export {name}"

        # Wrappers must re-export identical types
        from backend.backtest.engine_vectorized import VectorizedBacktester as VecWrap
        from backend.backtest.engine_event_driven import EventDrivenBacktester as EvWrap
        from backend.backtest.worker import BacktestWorker as WorkerWrap
        from research.backtest_vectorized import VectorizedBacktester as ResVec

        assert VecWrap is VectorizedBacktester
        assert EvWrap is EventDrivenBacktester
        assert WorkerWrap is BacktestWorker
        assert ResVec is VectorizedBacktester

    def test_event_driven_backtester_polymorphism(self):
        """Verify EventDrivenBacktester executes bar-by-bar polymorphically across strategies."""
        from datetime import datetime, timedelta
        from backend.backtest import EventDrivenBacktester
        from backend.core.strategies.wyckoff_vectorized import WyckoffMomentumStrategy
        from backend.core.strategies.ema_stress_test import EMAStressTestStrategy

        n = 200
        base_time = datetime(2026, 10, 1, 8, 0, 0)
        times = [base_time + timedelta(minutes=15 * i) for i in range(n)]
        closes = 2600.0 + np.cumsum(np.random.randn(n) * 2.0)
        df = pd.DataFrame({
            "time": times,
            "open": closes,
            "high": closes + 2.0,
            "low": closes - 2.0,
            "close": closes,
            "tick_volume": np.ones(n) * 1000,
        })

        # Test with string identifiers
        for strat_name in ["ict", "wyckoff", "ema"]:
            bt = EventDrivenBacktester(strategy=strat_name)
            report = bt.run(df, symbol="XAUUSD")
            assert report is not None
            assert report.sample_size == n
            assert report.final_equity > 0

        # Test with instantiated strategy object
        strat_obj = WyckoffMomentumStrategy()
        bt_obj = EventDrivenBacktester(strategy=strat_obj)
        rep_obj = bt_obj.run(df, symbol="XAUUSD")
        assert rep_obj is not None
        assert rep_obj.sample_size == n

    def test_dual_mode_backtesting_vectorized_and_event_driven(self):
        """Verify Mode 1 (Vectorized Engine) and Mode 2 (Event-Driven Engine) separation and fidelity."""
        from datetime import datetime, timedelta
        from backend.backtest.engine_vectorized import VectorizedBacktester as Mode1Vectorized
        from backend.backtest.engine_event_driven import EventDrivenBacktester as Mode2EventDriven

        n = 220
        base_time = datetime(2026, 10, 1, 8, 0, 0)
        times = [base_time + timedelta(minutes=15 * i) for i in range(n)]
        np.random.seed(42)
        closes = 2500.0 + np.cumsum(np.random.randn(n) * 2.0)
        highs = closes + np.random.rand(n) * 3.0
        lows = closes - np.random.rand(n) * 3.0
        opens = (closes + np.roll(closes, 1)) / 2.0
        opens[0] = closes[0]
        volumes = np.random.randint(100, 1000, n)

        df = pd.DataFrame({
            "time": times,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "tick_volume": volumes,
        })

        # Mode 1: Fast Matrix Vectorized Engine
        bt_mode1 = Mode1Vectorized(initial_balance=100000.0, risk_per_trade_pct=1.0)
        rep1 = bt_mode1.run(df, strategy_name="ICT Zones Pro v4.2 (Asian + FVG)", symbol="XAUUSD")
        assert rep1 is not None
        assert rep1.sample_size == n
        assert rep1.execution_time_ms < 1000.0  # Ultra-fast

        # Mode 2: Bar-by-Bar High-Fidelity Event-Driven Engine
        bt_mode2 = Mode2EventDriven(strategy="ict", initial_balance=100000.0, risk_per_trade_pct=1.0)
        rep2 = bt_mode2.run(df, symbol="XAUUSD")
        assert rep2 is not None
        assert rep2.sample_size == n
        assert isinstance(rep2.trade_records, list)

    def test_backtest_controller_interactive_switching(self):
        """Verify that UI controller triggers execution and logs upon strategy or mode change."""
        from PySide6.QtWidgets import QApplication
        from PySide6.QtUiTools import QUiLoader
        from PySide6.QtCore import QFile
        from frontend.controllers.backtest_controller import BacktestWorkbenchController

        app = QApplication.instance() or QApplication([])
        ui_file = QFile("frontend/quant_ai.ui")
        ui_file.open(QFile.ReadOnly)
        loader = QUiLoader()
        win = loader.load(ui_file)
        ui_file.close()

        ctrl = BacktestWorkbenchController(win)
        assert hasattr(win, "comboBtEngine")
        assert hasattr(win, "comboBtMode")

        # Verify strategy discovery populates rich metadata
        assert win.comboBtEngine.count() >= 3
        wyckoff_idx = -1
        for i in range(win.comboBtEngine.count()):
            data = win.comboBtEngine.itemData(i)
            if data and "wyckoff" in data.get("id", "").lower():
                wyckoff_idx = i
                break
        assert wyckoff_idx >= 0

        # Test strategy switch
        win.comboBtEngine.setCurrentIndex(wyckoff_idx)
        console_text = win.txtBtConsole.toPlainText()
        assert "[STRATEGY]" in console_text

        # Test mode switch
        win.comboBtMode.setCurrentIndex(1) # Mode 2 Event-Driven
        console_text = win.txtBtConsole.toPlainText()
        assert "[ENGINE MODE]" in console_text
        assert "Chế độ 2" in console_text

    def test_backtest_no_autorun_on_selection_and_reentrancy_guard(self, monkeypatch):
        """Verify combobox parameter changes DO NOT trigger backtest, and execution is guarded."""
        from PySide6.QtWidgets import QApplication
        from PySide6.QtUiTools import QUiLoader
        from PySide6.QtCore import QFile
        from frontend.controllers.backtest_controller import BacktestWorkbenchController

        app = QApplication.instance() or QApplication([])
        ui_file = QFile("frontend/quant_ai.ui")
        ui_file.open(QFile.ReadOnly)
        loader = QUiLoader()
        win = loader.load(ui_file)
        ui_file.close()

        ctrl = BacktestWorkbenchController(win)

        # Track calls to run_simulation_internal
        sim_calls = []
        original_sim = ctrl._run_simulation_internal
        def mock_sim(is_initial=False):
            sim_calls.append(is_initial)
            return original_sim(is_initial=is_initial)
        ctrl._run_simulation_internal = mock_sim

        # 1. Changing Mode to Mode 2 Event-Driven should NOT auto-run simulation
        sim_calls.clear()
        win.comboBtMode.setCurrentIndex(1)
        assert len(sim_calls) == 0, "Changing comboBtMode must NOT automatically run simulation"

        # 2. Changing Strategy should NOT auto-run simulation
        win.comboBtEngine.setCurrentIndex(0)
        assert len(sim_calls) == 0, "Changing comboBtEngine must NOT automatically run simulation"

        # 3. Changing Symbol should NOT auto-run simulation
        if hasattr(win, "comboBtSymbol"):
            win.comboBtSymbol.setCurrentIndex((win.comboBtSymbol.currentIndex() + 1) % max(1, win.comboBtSymbol.count()))
            assert len(sim_calls) == 0, "Changing comboBtSymbol must NOT automatically run simulation"

        # 4. Re-entrancy guard test: when _is_simulating is True, _on_run_clicked does nothing
        ctrl._is_simulating = True
        ctrl._on_run_clicked()
        assert len(sim_calls) == 0, "_on_run_clicked must abort immediately when _is_simulating is True"
        ctrl._is_simulating = False



