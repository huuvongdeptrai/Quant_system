import subprocess
import time
import sys
import os

print('Starting MT5 API in background...')
api_process = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'api:app', '--host', '127.0.0.1', '--port', '8000'],
    cwd='mt5_service'
)
time.sleep(3)
print('\n--- Running ICT Backtest (M15, 1 Week = 800 bars, Bias = BEARISH) ---')
os.environ['MT5_API_URL'] = 'http://127.0.0.1:8000'
subprocess.run([
    sys.executable, 'research/backtest.py',
    '--tf', 'M15',
    '--count', '800',
    '--strategy', 'ICT Zones Pro',
    '--bias', 'BEARISH'
])
api_process.terminate()
print('Done!')
