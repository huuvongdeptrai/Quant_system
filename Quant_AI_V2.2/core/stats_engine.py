
from infrastructure.brokers.mt5_safe import mt5
import pandas as pd
from datetime import datetime

class StatsEngine:
    def __init__(self):
        pass

    def get_account_statistics(self):
        """
        Kéo lịch sử MT5 và tính toán các chỉ số Prop-firm:
        - Tổng số lệnh (Total Trades)
        - Tỷ lệ thắng (Win Rate)
        - Lợi nhuận ròng (Net Profit)
        - Tỷ lệ Risk/Reward (R:R)
        """
        if not mt5.terminal_info():
            return None

        from datetime import timedelta
        # Lấy lịch sử (giới hạn 365 ngày gần nhất để tránh timeout)
        date_from = datetime.now() - timedelta(days=365)
        date_to = datetime.now() + timedelta(days=1)
        
        deals = mt5.history_deals_get(date_from, date_to)
        
        if deals is None or len(deals) == 0:
            return self._empty_stats()
            
        # Lọc các deal Đóng Lệnh (Entry Out)
        # Bỏ qua các deal Nạp/Rút tiền (Balance) hoặc Mở lệnh (Entry In)
        trades = []
        for d in deals:
            # deal.entry == 1 (DEAL_ENTRY_OUT)
            if d.entry == 1:
                trades.append({
                    'time': d.time,
                    'symbol': d.symbol,
                    'volume': d.volume,
                    'profit': d.profit,
                    'commission': d.commission,
                    'swap': d.swap,
                    'total_pnl': d.profit + d.commission + d.swap
                })
                
        if not trades:
            return self._empty_stats()
            
        df = pd.DataFrame(trades)
        
        # 1. Total Trades
        total_trades = len(df)
        
        # 2. Win Rate
        winning_trades = df[df['total_pnl'] > 0]
        losing_trades = df[df['total_pnl'] < 0]
        
        wins_count = len(winning_trades)
        losses_count = len(losing_trades)
        
        win_rate = (wins_count / total_trades * 100) if total_trades > 0 else 0.0
        
        # 3. Net Profit
        net_profit = df['total_pnl'].sum()
        
        # 4. R:R (Risk/Reward)
        avg_win = winning_trades['total_pnl'].mean() if wins_count > 0 else 0.0
        avg_loss = abs(losing_trades['total_pnl'].mean()) if losses_count > 0 else 0.0
        
        rr_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0
        if avg_loss == 0 and avg_win > 0:
            rr_ratio = 99.9 # Coi như vô cực nếu chưa thua lệnh nào
            
        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'net_profit': net_profit,
            'rr_ratio': rr_ratio,
            'wins': wins_count,
            'losses': losses_count,
            'trades': df.to_dict('records') if total_trades > 0 else []
        }

    def get_full_history(self):
        """
        Lấy toàn bộ lịch sử giao dịch và ghép nối lệnh (In/Out) theo position_id
        để tính ra Thời lượng và Số Pip.
        """
        if not mt5.terminal_info(): return []
        
        from datetime import timedelta
        date_from = datetime.now() - timedelta(days=365)
        date_to = datetime.now() + timedelta(days=1)
        deals = mt5.history_deals_get(date_from, date_to)
        if not deals: return []
        
        entries = {}
        trades = []
        for d in deals:
            if d.entry == 0: # DEAL_ENTRY_IN
                entries[d.position_id] = d
            elif d.entry == 1: # DEAL_ENTRY_OUT
                entry = entries.get(d.position_id)
                if not entry: continue
                
                duration = d.time - entry.time
                is_buy = entry.type == mt5.ORDER_TYPE_BUY
                
                # Tính số pip
                info = mt5.symbol_info(d.symbol)
                point = info.point if info else 0.0001
                
                if is_buy:
                    pips = (d.price - entry.price) / point
                else:
                    pips = (entry.price - d.price) / point
                    
                # Chuyển đổi point sang pip (thường 1 pip = 10 point với Forex)
                if point in [0.00001, 0.001]: pips = pips / 10
                
                hours, remainder = divmod(duration, 3600)
                minutes, seconds = divmod(remainder, 60)
                duration_str = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
                
                trades.append({
                    'ticket': d.position_id, # Dùng position_id làm mã lệnh
                    'type': 'Buy' if is_buy else 'Sell',
                    'close_time': datetime.fromtimestamp(d.time).strftime("%d thg %m %Y\n%H:%M:%S"),
                    'volume': d.volume,
                    'symbol': d.symbol,
                    'pnl': d.profit + d.commission + d.swap,
                    'pips': pips,
                    'duration': duration_str,
                    'timestamp': d.time # Dùng để sort
                })
        
        # Sắp xếp mới nhất lên đầu
        trades.sort(key=lambda x: x['timestamp'], reverse=True)
        return trades

    def _empty_stats(self):
        return {
            'total_trades': 0,
            'win_rate': 0.0,
            'net_profit': 0.0,
            'rr_ratio': 0.0,
            'wins': 0,
            'losses': 0
        }
