import subprocess
import time
import sys
import os

print("Starting MT5 API in background...")
api_process = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "api:app", "--host", "127.0.0.1", "--port", "8000"],
    cwd="mt5_service"
)

# Wait for API to start
time.sleep(3)

print("\n--- Running VWAP Scalping Backtest (M5, 1 Month = 8640 bars) ---")
os.environ["MT5_API_URL"] = "http://127.0.0.1:8000"
subprocess.run([
    sys.executable, "research/backtest.py",
    "--tf", "M5",
    "--count", "8640",
    "--strategy", "VWAP Scalping"
])

print("\nCleaning up API...")
api_process.terminate()
print("Done!")
