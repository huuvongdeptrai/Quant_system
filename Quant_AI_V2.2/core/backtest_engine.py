# -*- coding: utf-8 -*-
from PySide6.QtCore import QThread, Signal
import pandas as pd
import numpy as np
from infrastructure.brokers.mt5_safe import mt5
import os
import sys

class BacktestWorker(QThread):
    finished_signal = Signal(dict)
    log_signal = Signal(str)
    error_signal = Signal(str)

    def __init__(self, symbol, timeframe, balance, user_code, rates, file_path=None):
        super().__init__()
        self.symbol = symbol
        self.timeframe = timeframe
        self.initial_balance = balance
        self.user_code = user_code
        self.rates = rates
        self.file_path = file_path

    def run(self):
        df = pd.DataFrame(self.rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        self.log_signal.emit(f"Tải thành công {len(df)} nến. Đang biên dịch mã chiến lược...")
        
        # Tiêm động __file__ và thêm dự án vào sys.path để code người dùng 
        # có thể import thoải mái từ 'core.xyz' mà không bị lỗi module hay biến __file__.
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if base_dir not in sys.path:
            sys.path.insert(0, base_dir)
            
        script_path = os.path.abspath(self.file_path) if self.file_path else os.path.join(base_dir, 'strategies', 'virtual_strategy.py')
        
        # Compile and run user code
        exec_globals = {
            'pd': pd,
            'np': np,
            '__builtins__': __builtins__,
            '__file__': script_path,
            '__name__': '__main__'
        }
        
        try:
            exec(self.user_code, exec_globals)
            if 'generate_signals' not in exec_globals:
                self.error_signal.emit("Lỗi: Không tìm thấy hàm 'generate_signals(df)' trong code của bạn.")
                return
            
            generate_signals = exec_globals['generate_signals']
            df = generate_signals(df)
        except Exception as e:
            self.error_signal.emit(f"Lỗi thực thi Code Python:\n{str(e)}")
            return

        if 'signal' not in df.columns:
            self.error_signal.emit("Lỗi: Code của bạn không tạo ra cột 'signal'.")
            return
            
        self.log_signal.emit("Biên dịch thành công. Đang chạy mô phỏng giao dịch siêu tốc...")
        
        balance = self.initial_balance
        in_pos = False
        pos_type = 0
        entry_price = 0
        entry_time = None
        
        trades = []
        equity_curve = []
        
        # We need a list of trade markers for plotting: (time, type, price)
        markers = []
        
        # Hỗ trợ SL và TP nếu chiến lược có trả về
        has_sl = 'sl' in df.columns
        has_tp = 'tp' in df.columns
        current_sl = None
        current_tp = None
        
        for i in range(1, len(df)):
            sig = df['signal'].iloc[i-1]
            curr_price = df['open'].iloc[i]
            curr_time = df['time'].iloc[i]
            curr_high = df['high'].iloc[i]
            curr_low = df['low'].iloc[i]
            
            if not in_pos and sig != 0:
                in_pos = True
                pos_type = sig
                entry_price = curr_price
                entry_time = curr_time
                if has_sl: current_sl = df['sl'].iloc[i-1]
                if has_tp: current_tp = df['tp'].iloc[i-1]
                markers.append({'time': curr_time, 'type': 'BUY' if sig==1 else 'SELL', 'price': curr_price, 'action': 'OPEN'})
            
            elif in_pos:
                exit_reason = None
                exit_price = curr_price
                
                # 1. Kiểm tra dính SL / TP (Kiểm tra trong cùng cây nến)
                if pos_type == 1: # Đang BUY
                    if current_sl and current_sl > 0 and curr_low <= current_sl:
                        exit_reason = 'SL'
                        exit_price = current_sl
                    elif current_tp and current_tp > 0 and curr_high >= current_tp:
                        exit_reason = 'TP'
                        exit_price = current_tp
                else: # Đang SELL
                    if current_sl and current_sl > 0 and curr_high >= current_sl:
                        exit_reason = 'SL'
                        exit_price = current_sl
                    elif current_tp and current_tp > 0 and curr_low <= current_tp:
                        exit_reason = 'TP'
                        exit_price = current_tp
                        
                # 2. Hoặc đóng lệnh do Tín hiệu đảo chiều
                if not exit_reason and ((pos_type == 1 and sig == -1) or (pos_type == -1 and sig == 1)):
                    exit_reason = 'REVERSAL'
                    exit_price = curr_price
                    
                # Thực thi đóng lệnh
                if exit_reason:
                    if pos_type == 1:
                        pnl = (exit_price - entry_price) / entry_price * balance * 10
                    else:
                        pnl = (entry_price - exit_price) / entry_price * balance * 10
                        
                    balance += pnl
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': curr_time,
                        'type': 'BUY' if pos_type == 1 else 'SELL',
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl': pnl,
                        'reason': exit_reason
                    })
                    markers.append({'time': curr_time, 'type': 'EXIT', 'price': exit_price, 'action': 'CLOSE'})
                    in_pos = False
                    current_sl = None
                    current_tp = None
                    
                    # Cân nhắc mở lệnh ngược lại ngay lập tức nếu là Tín hiệu đảo chiều
                    if exit_reason == 'REVERSAL':
                        in_pos = True
                        pos_type = sig
                        entry_price = curr_price
                        entry_time = curr_time
                        if has_sl: current_sl = df['sl'].iloc[i-1]
                        if has_tp: current_tp = df['tp'].iloc[i-1]
                        markers.append({'time': curr_time, 'type': 'BUY' if sig==1 else 'SELL', 'price': curr_price, 'action': 'OPEN'})
                    
            equity_curve.append({'time': curr_time, 'equity': balance})
            
        # Compile Results
        total_trades = len(trades)
        wins = len([t for t in trades if t['pnl'] > 0])
        losses = total_trades - wins
        win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
        
        gross_profit = sum([t['pnl'] for t in trades if t['pnl'] > 0])
        gross_loss = abs(sum([t['pnl'] for t in trades if t['pnl'] < 0]))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        net_profit = balance - self.initial_balance
        
        # Max Drawdown
        if len(equity_curve) > 0:
            eq_df = pd.DataFrame(equity_curve)
            eq_df['rolling_max'] = eq_df['equity'].cummax()
            eq_df['drawdown'] = (eq_df['equity'] - eq_df['rolling_max']) / eq_df['rolling_max'] * 100
            max_drawdown = abs(eq_df['drawdown'].min())
        else:
            max_drawdown = 0.0

        metrics = {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'profit_factor': profit_factor,
            'net_profit': net_profit,
            'max_drawdown': max_drawdown,
            'final_balance': balance
        }

        self.finished_signal.emit({
            'df': df,
            'metrics': metrics,
            'trades': trades,
            'equity_curve': equity_curve,
            'markers': markers
        })
