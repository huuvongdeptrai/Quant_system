import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('Kho_Do_An/Quant_AI_V2.2/backend/core/strategies/wyckoff_vectorized.py', 'r', encoding='utf-8') as f:
    text = f.read()

for i, line in enumerate(text.splitlines()):
    if any(k in line.lower() for k in ['cand_tp', 'cand_sl', 'tp1', 'tp =', 'sl =', 'target', 'risk_reward']):
        print(f"{i+1}: {line.strip()}")
