# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

p = Path("Kho_Do_An/Quant_AI_V2.2/docs/thesis/chuong_3_thiet_ke_he_thong.md")
txt = p.read_text(encoding="utf-8")

# 1. Figure 3.2
old_3_2 = "> **[HÌNH 3.2: Giao diện trực quan hóa bối cảnh vĩ mô và bảng điều phối phòng vệ sự kiện kinh tế (Tab Macro Calendar) hiển thị dữ liệu của Tầng 2 trong kiến trúc hệ thống.]**"
new_3_2 = """![Hình 3.2: Giao diện trực quan hóa bối cảnh vĩ mô và bảng điều phối phòng vệ sự kiện kinh tế (Tab Macro Calendar)](images/hinh_3_2_tab_macro_calendar.png)

*Hình 3.2: Giao diện trực quan hóa bối cảnh vĩ mô và bảng điều phối phòng vệ sự kiện kinh tế (Tab Macro Calendar) hiển thị dữ liệu của Tầng 2 trong kiến trúc hệ thống*"""
assert old_3_2 in txt, "old_3_2 not found"
txt = txt.replace(old_3_2, new_3_2)

# 2. Figure 3.3
old_3_3 = "> **[HÌNH 3.3: Giao diện trạm điều khiển trung tâm (Main Trading Terminal) tích hợp biểu đồ nến vi sai 60 FPS, bảng theo dõi đa tài sản và bảng quản lý vị thế Blotter Dock.]**"
new_3_3 = """![Hình 3.3: Giao diện trạm điều khiển trung tâm (Main Trading Terminal)](images/hinh_3_3_main_trading_terminal.png)

*Hình 3.3: Giao diện trạm điều khiển trung tâm (Main Trading Terminal) tích hợp biểu đồ nến vi sai 60 FPS, bảng theo dõi đa tài sản và bảng quản lý vị thế Blotter Dock*"""
assert old_3_3 in txt, "old_3_3 not found"
txt = txt.replace(old_3_3, new_3_3)

# 3. Figure 3.4
old_3_4 = "> **[HÌNH 3.4: Giao diện phân hệ kiểm thử lịch sử (Tab Backtest) và cổng kiểm duyệt an toàn 4 điểm (Pre-trade Safety Drawer) trong trạm giao dịch VECTRA.]**"
new_3_4 = """![Hình 3.4: Giao diện phân hệ kiểm thử lịch sử (Tab Backtest) và cổng kiểm duyệt an toàn 4 điểm](images/hinh_3_4_tab_backtest.png)

*Hình 3.4: Giao diện phân hệ kiểm thử lịch sử (Tab Backtest) và cổng kiểm duyệt an toàn 4 điểm (Pre-trade Safety Drawer) trong trạm giao dịch VECTRA*"""
assert old_3_4 in txt, "old_3_4 not found"
txt = txt.replace(old_3_4, new_3_4)

p.write_text(txt, encoding="utf-8")
print("Successfully linked Figures 3.2, 3.3, 3.4 in Chapter 3!")
