import subprocess

# M5: 1 Tuần = 5 ngày giao dịch * 24h * 12 nến/h = 1440 nến.
# Cộng thêm 350 nến cho lookback = 1800 nến
print("========================================")
print("Chạy Backtest 1 tuần cho khung M5...")
print("========================================")
subprocess.run(["python", "research/backtest.py", "--tf", "M5", "--count", "1800"])

# M15: 1 Tuần = 5 ngày giao dịch * 24h * 4 nến/h = 480 nến.
# Cộng thêm 350 nến cho lookback = 850 nến
print("\n========================================")
print("Chạy Backtest 1 tuần cho khung M15...")
print("========================================")
subprocess.run(["python", "research/backtest.py", "--tf", "M15", "--count", "850"])

print("\nHoàn tất! Hãy kiểm tra thư mục 'data/' để lấy file CSV và Ảnh biểu đồ.")
