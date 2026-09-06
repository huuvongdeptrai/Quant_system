import sys
from pathlib import Path
import pandas as pd
from loguru import logger
import warnings
import matplotlib.pyplot as plt

# Tắt cảnh báo pandas
warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.core1_data.mt5_engine import MT5DataEngine
from core.core3_strategy import get_strategy

def run_backtest(symbol="XAUUSD", timeframe="M5", count=1000, strategy_name="ICT Zones Pro"):
    logger.info(f"Starting Backtest: {strategy_name} on {symbol} {timeframe} (Bars: {count})")
    
    # 1. Fetch historical data via MT5
    mt5 = MT5DataEngine()
    df = mt5.fetch_ohlcv(symbol, timeframe, count)
    
    if df is None or df.empty:
        logger.error("Failed to fetch data from MT5. Make sure MetaTrader 5 is running and logged in!")
        return
        
    logger.info(f"Data fetched successfully. Start time: {df.index[0]} - End time: {df.index[-1]}")
    
    # 2. Init strategy
    strategy = get_strategy(strategy_name)
    
    # 3. State Management
    initial_balance = 10000.0
    positions = []
    trades_history = []
    
    start_bar = 300 if "ICT" in strategy_name else 120  # ICT cần 300 nến, VWAP chỉ cần 120
    
    logger.info("Running simulation...")
    
    for i in range(start_bar, len(df)):
        current_idx = df.index[i]
        current_row = df.iloc[i]
        
        # --- QUẢN LÝ LỆNH ĐANG MỞ (Check SL/TP) ---
        active_positions = []
        for pos in positions:
            exited = False
            
            # Lệnh BUY
            if pos['type'] == 'BUY':
                # Dời SL về Hòa vốn (Breakeven) và Chốt lời 1 nửa (Partial) nếu chạm TP1
                if pos.get('tp1') and current_row['high'] >= pos['tp1']:
                    if pos['sl'] < pos['entry']:
                        pos['sl'] = pos['entry']
                        
                    if not pos.get('partial_taken'):
                        half_qty = pos['qty'] / 2.0
                        partial_pnl = (pos['tp1'] - pos['entry']) * half_qty
                        pos['realized_pnl'] = pos.get('realized_pnl', 0) + partial_pnl
                        pos['qty'] = half_qty
                        pos['partial_taken'] = True
                        logger.info(f"[{current_idx}] PARTIAL BUY at {pos['tp1']:.2f} | PnL: ${partial_pnl:.2f}")
                        
                if current_row['low'] <= pos['sl']:
                    pnl = (pos['sl'] - pos['entry']) * pos['qty']
                    pos['pnl'] = pnl + pos.get('realized_pnl', 0)
                    pos['exit_price'] = pos['sl']
                    pos['exit_time'] = current_idx
                    pos['exit_reason'] = 'SL (Stop Loss)' if pos['sl'] < pos['entry'] else 'BE (Breakeven)'
                    exited = True
                elif pos['tp2'] and current_row['high'] >= pos['tp2']:
                    pnl = (pos['tp2'] - pos['entry']) * pos['qty']
                    pos['pnl'] = pnl + pos.get('realized_pnl', 0)
                    pos['exit_price'] = pos['tp2']
                    pos['exit_time'] = current_idx
                    pos['exit_reason'] = 'TP2 (Take Profit)'
                    exited = True
                    
            # Lệnh SELL
            elif pos['type'] == 'SELL':
                # Dời SL về Hòa vốn (Breakeven) và Chốt lời 1 nửa (Partial) nếu chạm TP1
                if pos.get('tp1') and current_row['low'] <= pos['tp1']:
                    if pos['sl'] > pos['entry']:
                        pos['sl'] = pos['entry']
                        
                    if not pos.get('partial_taken'):
                        half_qty = pos['qty'] / 2.0
                        partial_pnl = (pos['entry'] - pos['tp1']) * half_qty
                        pos['realized_pnl'] = pos.get('realized_pnl', 0) + partial_pnl
                        pos['qty'] = half_qty
                        pos['partial_taken'] = True
                        logger.info(f"[{current_idx}] PARTIAL SELL at {pos['tp1']:.2f} | PnL: ${partial_pnl:.2f}")
                        
                if current_row['high'] >= pos['sl']:
                    pnl = (pos['entry'] - pos['sl']) * pos['qty']
                    pos['pnl'] = pnl + pos.get('realized_pnl', 0)
                    pos['exit_price'] = pos['sl']
                    pos['exit_time'] = current_idx
                    pos['exit_reason'] = 'SL (Stop Loss)' if pos['sl'] > pos['entry'] else 'BE (Breakeven)'
                    exited = True
                elif pos['tp2'] and current_row['low'] <= pos['tp2']:
                    pnl = (pos['entry'] - pos['tp2']) * pos['qty']
                    pos['pnl'] = pnl + pos.get('realized_pnl', 0)
                    pos['exit_price'] = pos['tp2']
                    pos['exit_time'] = current_idx
                    pos['exit_reason'] = 'TP2 (Take Profit)'
                    exited = True
                    
            if exited:
                # Phí giao dịch (Commission giả lập)
                fee = (pos.get('initial_qty', pos['qty']) * pos['entry'] * 0.00005) 
                pos['pnl'] = pos['pnl'] - fee
                trades_history.append(pos)
                logger.info(f"[{current_idx}] CLOSED {pos['type']} at {pos['exit_price']:.2f} | Reason: {pos['exit_reason']} | PnL: ${pos['pnl']:.2f}")
            else:
                active_positions.append(pos)
                
        positions = active_positions
        
        # --- TÌM TÍN HIỆU MỚI ---
        if len(positions) == 0:
            history_slice = df.iloc[:i].copy()
            signal = strategy.analyze(history_slice, macro_context={"overall_bias": "BEARISH"})
            
            if signal.get('signal') in ['BUY', 'SELL']:
                action = signal['signal']
                entry = signal['entry_price']
                sl = signal['sl']
                tp1 = signal['tp1']
                tp2 = signal['tp2']
                
                # Quản lý rủi ro 1% CỐ ĐỊNH trên vốn ban đầu ($100)
                risk_per_trade = initial_balance * 0.01
                risk_amt = abs(entry - sl)
                qty = (risk_per_trade / risk_amt) if risk_amt > 0 else 0
                
                if qty > 0:
                    positions.append({
                        'type': action,
                        'entry': entry,
                        'sl': sl,
                        'tp1': tp1,
                        'tp2': tp2,
                        'qty': qty,
                        'initial_qty': qty,
                        'entry_time': history_slice.index[-1],
                        'realized_pnl': 0,
                        'partial_taken': False
                    })
                    logger.info(f"[{history_slice.index[-1]}] OPENED {action} | Entry: {entry:.2f} | SL: {sl:.2f} | TP1: {tp1:.2f}")

    # --- TỔNG KẾT VÀ XUẤT BÁO CÁO ---
    if not trades_history:
        logger.info("No trades executed.")
        return None
        
    df_trades = pd.DataFrame(trades_history)
    df_trades = df_trades[['entry_time', 'exit_time', 'type', 'entry', 'sl', 'tp1', 'tp2', 'exit_price', 'exit_reason', 'pnl']]
    
    # Đổi tên cột cho đẹp
    df_trades.rename(columns={
        'entry_time': 'Entry Time',
        'exit_time': 'Exit Time',
        'type': 'Action',
        'entry': 'Entry Price',
        'sl': 'Stop Loss',
        'tp1': 'Take Profit 1',
        'tp2': 'Take Profit 2',
        'exit_price': 'Exit Price',
        'exit_reason': 'Exit Reason',
        'pnl': 'Net PnL ($)'
    }, inplace=True)
    
    # Tính toán Equity
    df_trades['Cumulative PnL'] = df_trades['Net PnL ($)'].cumsum()
    df_trades['Equity'] = initial_balance + df_trades['Cumulative PnL']
    final_balance = df_trades['Equity'].iloc[-1]
    
    # Tính toán Metrics
    wins = df_trades[df_trades['Net PnL ($)'] > 0]
    losses = df_trades[df_trades['Net PnL ($)'] <= 0]
    win_rate = (len(wins) / len(df_trades)) * 100
    
    gross_profit = wins['Net PnL ($)'].sum()
    gross_loss = abs(losses['Net PnL ($)'].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    df_trades['Peak'] = df_trades['Equity'].cummax()
    df_trades['Drawdown'] = (df_trades['Equity'] - df_trades['Peak']) / df_trades['Peak']
    max_drawdown = abs(df_trades['Drawdown'].min()) * 100
    
    # 1. Lưu CSV
    data_dir = PROJECT_ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    csv_path = data_dir / f"{timeframe}_Trades_Report.csv"
    df_trades.drop(columns=['Cumulative PnL', 'Peak', 'Drawdown']).to_csv(csv_path, index=False)
    logger.info(f"✅ Đã lưu Trade Log: {csv_path}")
    
    # 2. Vẽ và Lưu Biểu Đồ
    try:
        plt.style.use('dark_background')
        plt.figure(figsize=(10, 5))
        plt.plot(df_trades['Exit Time'], df_trades['Equity'], marker='o', linestyle='-', color='#00ffcc', linewidth=2)
        plt.fill_between(df_trades['Exit Time'], df_trades['Equity'], initial_balance, color='#00ffcc', alpha=0.1)
        plt.axhline(y=initial_balance, color='red', linestyle='--', alpha=0.5, label='Initial Balance')
        
        plt.title(f"Equity Curve - ICT Zones Pro ({symbol} {timeframe})", fontsize=14, pad=15)
        plt.xlabel("Time", fontsize=10)
        plt.ylabel("Balance (USD)", fontsize=10)
        plt.grid(True, linestyle=':', alpha=0.4)
        plt.legend()
        plt.tight_layout()
        
        png_path = data_dir / f"{timeframe}_Equity_Curve.png"
        plt.savefig(png_path, dpi=300)
        plt.close()
        logger.info(f"✅ Đã lưu Biểu Đồ: {png_path}")
    except Exception as e:
        logger.warning(f"Không thể vẽ biểu đồ. Lỗi: {e}")

    logger.info("\n" + "="*40)
    logger.info("         PERFORMANCE METRICS")
    logger.info("="*40)
    logger.info(f"Strategy      : {strategy_name}")
    logger.info(f"Initial Bal   : ${initial_balance:.2f}")
    logger.info(f"Final Bal     : ${final_balance:.2f}")
    logger.info(f"Total Trades  : {len(df_trades)}")
    logger.info(f"Win Rate      : {win_rate:.2f}%")
    logger.info(f"Profit Factor : {profit_factor:.2f}")
    logger.info(f"Max Drawdown  : {max_drawdown:.2f}%")
    logger.info(f"Gross Profit  : ${gross_profit:.2f}")
    logger.info(f"Gross Loss    : -${gross_loss:.2f}")
    
    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", type=str, default="XAUUSD")
    parser.add_argument("--tf", type=str, default="M5")
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--strategy", type=str, default="ICT Zones Pro")
    parser.add_argument("--bias", type=str, default="NEUTRAL")
    args = parser.parse_args()
    
    run_backtest(symbol=args.symbol, timeframe=args.tf, count=args.count, strategy_name=args.strategy)
