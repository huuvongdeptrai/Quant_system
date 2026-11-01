path = "Kho_Do_An/Quant_AI_V2.2/tests/test_scalp_pullback_and_copilot.py"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

old_block = """    with patch.object(dg, "_get_price_position", return_value=mock_pos), \\
         patch.object(dg, "_get_htf_bias", return_value="BULLISH"), \\
         patch.object(dg, "_get_macro_bias", return_value="BULLISH"):"""

new_block = """    with patch.object(dg, "_get_price_position", return_value=mock_pos), \\
         patch.object(dg, "_get_htf_bias", return_value="BULLISH"), \\
         patch.object(dg, "_get_macro_bias", return_value="BULLISH"), \\
         patch("backend.infrastructure.data_providers.adapters.precious_metals_adapter.PreciousMetalsAdapter.evaluate_risk_rules", return_value=(True, "OK")):"""

if old_block in text:
    text = text.replace(old_block, new_block, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print("Successfully patched test_scalp_pullback_and_copilot.py")
else:
    print("Could not find old_block in text")
