# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

# Ch3
p3 = Path("Kho_Do_An/Quant_AI_V2.2/docs/thesis/chuong_3_thiet_ke_he_thong.md")
t3 = p3.read_text(encoding="utf-8")
t3 = t3.replace("Khác biệt hoàn toàn với các công cụ", "Khác với các công cụ")
t3 = t3.replace("mà hoàn toàn không gây trễ luồng xử lý giao diện:", "hạn chế tối đa việc gây trễ luồng xử lý giao diện:")
p3.write_text(t3, encoding="utf-8")

# Ch4
p4 = Path("Kho_Do_An/Quant_AI_V2.2/docs/thesis/chuong_4_thuc_nghiem.md")
t4 = p4.read_text(encoding="utf-8")
t4 = t4.replace("Đồ thị tiêu thụ bộ nhớ duy trì hoàn toàn nằm ngang", "Đồ thị tiêu thụ bộ nhớ duy trì ổn định nằm ngang")
t4 = t4.replace("luồng đồ họa hoàn toàn không bị chặn", "luồng đồ họa không bị chặn")
p4.write_text(t4, encoding="utf-8")

print("Done updates.")
