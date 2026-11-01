# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

p = Path("Kho_Do_An/Quant_AI_V2.2/docs/thesis/chuong_2_co_so_ly_thuyet.md")
txt = p.read_text(encoding="utf-8")

# 1. Replace Figure 2.1 placeholder
old_fig_2_1 = "> **[GHI CHÚ MINH HỌA HÌNH 2.1: Sơ đồ hình học vi cấu trúc của Khoảng trống thanh khoản (Imbalance) hình thành giữa ba nến liên tiếp và cơ chế tái kiểm định.]**"
new_fig_2_1 = """![Hình 2.1: Sơ đồ hình học vi cấu trúc của Khoảng trống thanh khoản (Fair Value Gap) và cơ chế tái kiểm định](images/hinh_2_1_fvg_imbalance.png)

*Hình 2.1: Sơ đồ hình học vi cấu trúc của Khoảng trống thanh khoản (Fair Value Gap) và cơ chế tái kiểm định của dòng tiền định chế*"""

assert old_fig_2_1 in txt, "old_fig_2_1 not found"
txt = txt.replace(old_fig_2_1, new_fig_2_1)

# 2. Replace Figure 2.2 placeholder
old_fig_2_2 = "> **[GHI CHÚ MINH HỌA HÌNH 2.2: Sơ đồ cấu trúc pha và nguyên lý Nỗ lực - Kết quả theo lý thuyết Wyckoff.]**"
new_fig_2_2 = """![Hình 2.2: Sơ đồ cấu trúc pha và nguyên lý Nỗ lực - Kết quả theo phương pháp Wyckoff](images/hinh_2_2_wyckoff_schematic.png)

*Hình 2.2: Sơ đồ cấu trúc pha và nguyên lý Nỗ lực - Kết quả theo phương pháp Wyckoff kết hợp nhận diện điểm bẫy thanh khoản (Spring)*"""

assert old_fig_2_2 in txt, "old_fig_2_2 not found"
txt = txt.replace(old_fig_2_2, new_fig_2_2)

# 3. Update Figure 2.3 image path
old_fig_2_3 = "![Hình 2.3: Sơ đồ luồng quyết định hai tầng của Kiến trúc Học máy Meta-Labeling theo phương pháp luận Marcos López de Prado](images/hinh_2_2_meta_labeling_flow.png)"
new_fig_2_3 = "![Hình 2.3: Sơ đồ luồng quyết định hai tầng của Kiến trúc Học máy Meta-Labeling theo phương pháp luận Marcos López de Prado](images/hinh_2_3_meta_labeling_flow.png)"

assert old_fig_2_3 in txt, "old_fig_2_3 not found"
txt = txt.replace(old_fig_2_3, new_fig_2_3)

p.write_text(txt, encoding="utf-8")
print("Successfully linked all figures in Chapter 2!")
