import MetaTrader5 as mt5
import pandas as pd
import pytz
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any, Optional, List
from loguru import logger

# Ensure project root (QUANT_AI_WYCKOFF) is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from system.interfaces import IDataProvider

# Load environment variables
load_dotenv()

class MT5DataEngine(IDataProvider):
    def __init__(self):
        self.login = int(os.getenv("MT5_LOGIN", os.getenv("MT5_ACCOUNT", 0)))
        self.password = os.getenv("MT5_PASSWORD", "")
        self.server = os.getenv("MT5_SERVER", "")
        self.path = os.getenv("MT5_PATH", "")
        self.timezone_str = os.getenv("MT5_TIMEZONE", "Europe/Kyiv")
        self.magic_number = int(os.getenv("MAGIC_NUMBER", 9999))
        self.connected = False
        self.last_timestamp: Optional[datetime] = None

    def _reconnect(self) -> bool:
        """Attempt to reconnect to MT5 with exponential backoff (2s, 5s, 10s)."""
        backoff_times = [2, 5, 10]
        
        # Chỉ truyền các tham số (params) nếu chúng thực sự tồn tại
        kwargs = {"timeout": 60000}  # Ép timeout lên 60 giây để tránh lỗi IPC Timeout
        if self.path: kwargs['path'] = self.path
        if self.login > 0: kwargs['login'] = self.login
        if self.password: kwargs['password'] = self.password
        if self.server: kwargs['server'] = self.server
        
        for attempt, wait_time in enumerate(backoff_times, 1):
            init_res = mt5.initialize(**kwargs)

            if init_res:
                logger.info(f"[Watchdog] Reconnected successfully on attempt {attempt}.")
                self.connected = True
                return True
            
            logger.warning(f"[Watchdog] Reconnect attempt {attempt} failed (error: {mt5.last_error()}). Retrying in {wait_time}s...")
            time.sleep(wait_time)
                
        logger.error("[Watchdog] All reconnection attempts failed. Halting logic.")
        self.connected = False
        return False

    def ping_server(self) -> bool:
        """Check connection and auto-reconnect if needed."""
        if not mt5.terminal_info():
            logger.warning("[Watchdog] Connection lost. Attempting reconnect...")
            if not self._reconnect():
                raise ConnectionError("CRITICAL: MT5 Connection lost and reconnect failed.")
        
        self.connected = True
        return self.connected

    def _normalize_dataframe(self, rates: tuple | None) -> pd.DataFrame | None:
        if rates is None or len(rates) == 0:
            logger.error("No rates received from MT5")
            return None
            
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # Localize to broker's geographical timezone (handles DST automatically)
        broker_tz = pytz.timezone(self.timezone_str)
        df['time'] = df['time'].dt.tz_localize(broker_tz)
        
        # Convert to UTC for standardized macro and cross-market analysis
        df['time'] = df['time'].dt.tz_convert(pytz.UTC)
        
        # Standardize columns
        df.rename(columns={'tick_volume': 'volume'}, inplace=True)
        df = df[['time', 'open', 'high', 'low', 'close', 'volume']]
        
        return df

    def fetch_ohlcv(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame | None:
        """Implement abstract method. Useful for general purpose."""
        self.ping_server()
        tf_map = {
            "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15, 
            "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4, 
            "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1
        }
        mt5_tf = tf_map.get(timeframe, mt5.TIMEFRAME_H4)
        
        rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, count)
        return self._normalize_dataframe(rates)

    def get_current_tick(self, symbol: str) -> Dict[str, float] | None:
        self.ping_server()
        tick = mt5.symbol_info_tick(symbol)
        
        if tick is None:
            logger.error(f"Failed to fetch tick for {symbol}")
            return None
            
        return {"bid": tick.bid, "ask": tick.ask, "last": tick.last}

    def smart_fetch(self, symbol: str, timeframe: str, is_boot: bool = False, lookback_bars: int = 200) -> pd.DataFrame | None:
        """
        Smart Fetching logic to prevent data gaps.
        - is_boot=True: Fetch `lookback_bars`.
        - is_boot=False: Fetch from `last_timestamp` to now.
        """
        self.ping_server()
        tf_map = {
            "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15, 
            "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4, 
            "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1
        }
        mt5_tf = tf_map.get(timeframe, mt5.TIMEFRAME_H4)

        if is_boot or self.last_timestamp is None:
            rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, lookback_bars)
        else:
            # Fetch from last_timestamp to now to cover any disconnect gaps
            # Using int(datetime.timestamp()) but need to provide it in UTC or Broker Time?
            # copy_rates_range uses Broker Time. We need to convert our UTC last_timestamp back to Broker Time for the API call.
            broker_tz = pytz.timezone(self.timezone_str)
            last_time_broker = self.last_timestamp.astimezone(broker_tz).replace(tzinfo=None)
            now_broker = datetime.now(pytz.UTC).astimezone(broker_tz).replace(tzinfo=None)
            
            rates = mt5.copy_rates_range(symbol, mt5_tf, last_time_broker, now_broker)

        df = self._normalize_dataframe(rates)
        
        if df is not None and not df.empty:
            self.last_timestamp = df['time'].iloc[-1]
            
        return df

    def get_open_positions(self, symbol: str) -> List[Dict[str, Any]]:
        self.ping_server()
        positions = mt5.positions_get(symbol=symbol)
        
        if positions is None:
            logger.warning(f"Failed to fetch open positions for {symbol} (or none exist)")
            return []
            
        filtered = []
        for pos in positions:
            if pos.magic == self.magic_number:
                filtered.append(pos._asdict())
                
        return filtered

if __name__ == "__main__":
    logger.info("--- TESTING CORE 1 DATA ENGINE ---")
    engine = MT5DataEngine()
    
    try:
        is_connected = engine.ping_server()
        logger.info(f"Watchdog Ping: {is_connected}")
        
        if is_connected:
            symbol = os.getenv("SYMBOL", "XAUUSD")
            
            logger.info(f"Fetching 5 bars (Boot Mode) for {symbol}...")
            df_boot = engine.smart_fetch(symbol, "H4", is_boot=True, lookback_bars=5)
            print(df_boot)
            
            logger.info("Sleeping 2s to test runtime fetch...")
            time.sleep(2)
            df_runtime = engine.smart_fetch(symbol, "H4", is_boot=False)
            
            if df_runtime is not None:
                logger.info(f"Runtime fetch returned {len(df_runtime)} bars.")
                print(df_runtime.tail(2))
            
            positions = engine.get_open_positions(symbol)
            logger.info(f"Open Positions (Magic: {engine.magic_number}): {len(positions)}")
            
    except Exception as e:
        logger.error(f"Critical execution error: {e}")
    finally:
        mt5.shutdown()
