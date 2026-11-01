path = "Kho_Do_An/Quant_AI_V2.2/tests/test_scalp_pullback_and_copilot.py"
with open(path, "r", encoding="utf-8", newline="") as f:
    text = f.read()

text = text.replace(
    'patch.object(dg, "_get_macro_bias", return_value="BULLISH"):, \\',
    'patch.object(dg, "_get_macro_bias", return_value="BULLISH"), \\'
)

with open(path, "w", encoding="utf-8", newline="") as f:
    f.write(text)
print("Fixed syntax")
