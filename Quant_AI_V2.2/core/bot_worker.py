
import time
from datetime import datetime
from infrastructure.brokers.mt5_safe import mt5
from PySide6 import QtCore
from loguru import logger
import os
from pathlib import Path

# Cấu hình loguru (Rule 4 & Clean Paths)
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
logger.add(log_dir / "bot_worker.log", rotation="10 MB", retention=5, enqueue=True, encoding="utf-8")

import pandas as pd
from infrastructure.notifications.telegram_notifier import telegram_notifier

DEFAULT_LOOKBACK_BARS = 300

class WorkerSignals(QtCore.QObject):
    log_msg = QtCore.Signal(str, str, str, str)

class BotWorker(QtCore.QThread):
    def __init__(self, strategy, risk_manager, execution_manager, data_preprocessor, decision_gate, 
                 symbols: list[str] = ["XAUUSD"], timeframe: int = mt5.TIMEFRAME_M15, 
                 strategy_name: str = "ICT", ai_model_name: str = "qwen2.5"):
        super().__init__()
        self.is_running = True
        self.symbols = symbols
        self.timeframe = timeframe
        self.strategy_name = strategy_name
        self.ai_model_name = ai_model_name
        self.signals = WorkerSignals()
        
        # ==================================================
        # THIẾT LẬP HƯỚNG GIAO DỊCH (Có thể nối ra UI để tuỳ chỉnh)
        # Các tuỳ chọn: "AUTO", "LONG_ONLY", "SHORT_ONLY"
        # ==================================================
        self.trade_mode = "AUTO" 
        
        # Dependency Injection (Rule 6)
        self.risk_mgr = risk_manager
        self.exec_mgr = execution_manager
        self.prep = data_preprocessor
        self.ict = strategy
        self.gate = decision_gate
        
        # Khởi tạo sớm AI Engine nếu dùng chiến lược AI để tránh giật lag lúc khớp lệnh
        self.ai_engine = None
        if self.strategy_name == "AI":
            from infrastructure.ai_engines.ai.analysis_engine import AnalysisEngine
            self.ai_engine = AnalysisEngine(model_name=self.ai_model_name)

    def log(self, level: str, msg: str, color: str):
        t = datetime.now().strftime("%H:%M:%S")
        if level == "INFO": logger.info(msg)
        elif level == "WARNING": logger.warning(msg)
        elif level == "ERROR": logger.error(msg)
        self.signals.log_msg.emit(t, level, msg, color)
        
    def run(self):
        self.log("INFO", f"Khởi động Dây chuyền Bot (Chế độ cho phép: {self.trade_mode})...", "#3FB950")
        telegram_notifier.send_message(f"🟢 <b>[Quant AI V2.2]</b> Bắt đầu giao dịch tự động trên {', '.join(self.symbols)}.\nChế độ: <b>{self.trade_mode}</b>\nChiến lược: <b>{self.strategy_name}</b>")
        if not mt5.terminal_info(): return
        
        while self.is_running:
            for sym in self.symbols:
                if not self.is_running: break
                self.pipeline_execute(sym)
            
            # Đợi 10s nhưng chia nhỏ để có thể dừng ngay lập tức khi logout
            for _ in range(100):
                if not self.is_running: break
                time.sleep(0.1)
            
    def pipeline_execute(self, sym: str):
        rates = mt5.copy_rates_from_pos(sym, self.timeframe, 0, 500)
        if rates is None or len(rates) == 0: return
        refined = self.prep.process_technical_data(rates)
        if not refined: return
        
        positions = mt5.positions_get(symbol=sym)
        if positions: return # Đang có lệnh -> Không làm gì cả
        
        # --------------------------------------------------
        # LỚP 1: CHIẾN LƯỢC ICT ZONES PRO (V1)
        # --------------------------------------------------
        # TUỲ CHỌN CHIẾN LƯỢC GIAO DỊCH
        if self.strategy_name == "ICT":
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            
            ict_res = self.ict.analyze(df, macro_context={})
            signal = ict_res.get('signal', 'HOLD')
            if signal in ["HOLD", "WAIT"]: return
            
            sl_price = ict_res['sl']
            tp_price = ict_res['tp1']
            entry_price = ict_res['entry_price']
            confidence_str = f"Tín nhiệm: {ict_res['confidence']*100:.1f}%"
            
        elif self.strategy_name == "SMC":
            self.log("INFO", f"Đang mô phỏng chạy SMC Liquidity trên {sym} (Tính năng Sắp ra mắt)...", "#8B949E")
            time.sleep(30)
            return
            
        elif self.strategy_name == "AI":
            self.log("INFO", f"Đang gọi Local AI phân tích {sym}...", "#8B949E")
            if not self.ai_engine:
                from infrastructure.ai_engines.ai.analysis_engine import AnalysisEngine
                self.ai_engine = AnalysisEngine(model_name=self.ai_model_name)
            
            ai_res = self.ai_engine.analyze(sym)
            if 'error' in ai_res:
                self.log("ERROR", f"AI Lỗi: {ai_res['error']}", "#DA3633")
                return
                
            trend = ai_res.get('trend_intraday', '').upper()
            if 'TĂNG' in trend or 'UP' in trend:
                signal = 'BUY'
            elif 'GIẢM' in trend or 'DOWN' in trend:
                signal = 'SELL'
            else:
                signal = 'WAIT'
                
            if signal in ["HOLD", "WAIT"]: 
                self.log("INFO", f"AI khuyên đứng ngoài: {ai_res.get('scenario_a', '')[:50]}...", "#8B949E")
                return
                
            # Tính SL/TP cơ bản theo Support/Resistance 500 nến
            rates_df = pd.DataFrame(rates)
            current = rates_df['close'].iloc[-1]
            sup = rates_df['low'].min()
            res = rates_df['high'].max()
            sl_price, tp_price = self._calculate_sl_tp(signal, current, sup, res)
            entry_price = current
            confidence_str = "Tín nhiệm: AI Local"
            
        else:
            return

        # --------------------------------------------------
        # LỚP 2: MA TRẬN QUYẾT ĐỊNH (Vĩ mô + Vị trí giá + HTF)
        # --------------------------------------------------
        gate_result = self.gate.evaluate(sym, signal)
        if gate_result['decision'] == 'WAIT':
            self.log("INFO", f"[Gate] {signal} {sym}: {gate_result['reason']}", "#8B949E")
            return
        signal = gate_result['decision']  # Gate co the thay doi huong
            
        # --------------------------------------------------
        # LỚP 3: TÍNH TOÁN RỦI RO (RISK LAYER)
        # --------------------------------------------------
        sl_points = abs(entry_price - sl_price)
        if sl_points <= 0: sl_points = entry_price * 0.005 # Fallback
        
        lot = self.risk_mgr.calculate_lot_size(sym, sl_points, risk_pct=1.0)
        
        self.log("TRADE", f"[{self.strategy_name}] Duyệt {signal} {sym}. {confidence_str}. Vol: {lot} Lot. SL: {sl_price:.2f}", "#D2A8FF")
        
        # --------------------------------------------------
        # LỚP 4: BẮN LỆNH LÊN MT5 (EXECUTION LAYER)
        # --------------------------------------------------
        res = self.exec_mgr.execute_market_order(sym, signal == "BUY", lot, sl_price, tp_price, comment=f"Quant_{signal}")
        if res['status'] == 'success':
            self.log("SUCCESS", res['msg'], "#3FB950")
            telegram_notifier.send_message(f"🚀 <b>KHỚP LỆNH: {signal} {sym}</b>\nKhối lượng: {lot} Lot\nSL: {sl_price:.2f} | TP: {tp_price:.2f}\nLý do: {confidence_str}")
        else:
            self.log("ERROR", res['msg'], "#DA3633")

    def _strategy_logic(self, refined: dict) -> tuple[str, float, float, float]:
        current = refined['current_price']
        trend = refined['trend']
        sup = refined['support']
        res = refined['resistance']
        range_h = res - sup
        sig = "WAIT"
        
        if range_h > 0:
            if "TĂNG" in trend and (current - sup) < range_h * 0.2:
                sig = "BUY"
            elif "GIẢM" in trend and (res - current) < range_h * 0.2:
                sig = "SELL"
        return sig, sup, res, current
        
    def _validate_direction(self, signal: str) -> bool:
        """Trạm gác: Kiểm tra tín hiệu có thuận với Chế độ hay không"""
        if self.trade_mode == "AUTO": return True
        if self.trade_mode == "LONG_ONLY" and signal == "BUY": return True
        if self.trade_mode == "SHORT_ONLY" and signal == "SELL": return True
        return False
        
    def _calculate_sl_tp(self, signal: str, current: float, support: float, resistance: float) -> tuple[float, float]:
        if signal == "BUY":
            sl = current - support
            if sl <= 0: sl = current * 0.005
            tp = current + (sl * 2)
        else:
            sl = resistance - current
            if sl <= 0: sl = current * 0.005
            tp = current - (sl * 2)
        return sl, tp

    def stop(self):
        self.is_running = False
        self.log("INFO", "Tiến trình ngắt Bot an toàn đã được kích hoạt...", "#8B949E")
        telegram_notifier.send_message("🔴 <b>[Quant AI V2.2]</b> Bot đã ngừng hoạt động.")
