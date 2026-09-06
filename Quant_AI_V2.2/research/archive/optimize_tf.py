import pandas as pd
from backtest import run_backtest
from loguru import logger
import sys

logger.remove()
logger.add(sys.stdout, level="WARNING") 

def run_optimization():
    timeframes = ['M5', 'M15', 'M30', 'H1']
    results = []
    
    print("Running Backtest Optimization...")
    print("==========================================================")
    
    for tf in timeframes:
        print(f"Testing {tf} (1000 bars)...")
        res = run_backtest(symbol="XAUUSD", timeframe=tf, count=1000, strategy_name="ICT Zones Pro")
        if res:
            results.append(res)
            
    print("\nDONE. RESULTS TABLE:")
    print("| Timeframe | Trades | Win Rate | Profit | Loss | Net Profit | Final Bal |")
    print("|-----------|--------|----------|--------|------|------------|-----------|")
    
    best_tf = None
    best_net = -999999
    
    for r in results:
        net_profit = r['profit'] + r['loss']
        if net_profit > best_net:
            best_net = net_profit
            best_tf = r['tf']
            
        print(f"| {r['tf']:>9} | {r['trades']:>6} | {r['win_rate']:>7.2f}% | {r['profit']:>6.2f} | {r['loss']:>4.2f} | {net_profit:>10.2f} | {r['final_balance']:>9.2f} |")
        
    print("\nBEST TIMEFRAME:")
    print(f"Based on 1000 bars, the best timeframe is {best_tf} with a net profit of ${best_net:.2f}.")

if __name__ == '__main__':
    run_optimization()
