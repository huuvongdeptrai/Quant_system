import os

path_dg = "Kho_Do_An/Quant_AI_V2.2/backend/infrastructure/ai_engines/ai/decision_gate.py"
with open(path_dg, "r", encoding="utf-8") as f:
    c = f.read()
c = c.replace("threshold = 0.36", "threshold = 0.38")
c = c.replace('meta.get("threshold", 0.36)', 'meta.get("threshold", 0.38)')
with open(path_dg, "w", encoding="utf-8") as f:
    f.write(c)
print("Updated decision_gate.py")

path_test = "Kho_Do_An/Quant_AI_V2.2/tests/test_ml_meta_labeling_model_registry.py"
with open(path_test, "r", encoding="utf-8") as f:
    c_test = f.read()
c_test = c_test.replace("assert thresh == 0.36", "assert thresh == 0.38")
with open(path_test, "w", encoding="utf-8") as f:
    f.write(c_test)
print("Updated test_ml_meta_labeling_model_registry.py")
