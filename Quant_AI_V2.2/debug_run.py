import subprocess
import sys

with open('crash.log', 'w', encoding='utf-8') as f:
    process = subprocess.Popen([sys.executable, 'run_pro.py'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        f.write(line)
        f.flush()
        print(line, end='')
