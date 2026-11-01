# -*- coding: utf-8 -*-
"""
Script to apply rigorous academic updates to thesis chapters:
1. Update Section 3.5.2 in chuong_3_thiet_ke_he_thong.md with Structured Outputs schema + Python fallback/fail-closed distinction.
2. Clean AI cliché at line 276 ("nắm bắt bức tranh toàn cảnh" -> "theo dõi toàn diện bối cảnh kinh tế vĩ mô").
3. Update Section 3.6.1 in chuong_3_thiet_ke_he_thong.md with gk_vol x1000 vs x100 feature contract explanation.
4. Update Section 2.2.1 in chuong_2_co_so_ly_thuyet.md with FVG ATR design choice & comparative testing paragraph.
5. Add [7] citation to Garman-Klass in chuong_5_ket_luan.md line 25.
6. Cleanly expand all escaped literal \\n in chuong_3_thiet_ke_he_thong.md so markdown formatting is 100% valid.
"""

import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

thesis_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'docs', 'thesis')

# -------------------------------------------------------------
# 1. Update chuong_5_ket_luan.md: Add [7] to Garman-Klass
# -------------------------------------------------------------
ch5_path = os.path.join(thesis_dir, 'chuong_5_ket_luan.md')
with open(ch5_path, 'r', encoding='utf-8') as f:
    ch5_text = f.read()

if 'Garman-Klass [7]' not in ch5_text:
    ch5_text = ch5_text.replace('Ước lượng phương sai dải giá Garman-Klass,', 'Ước lượng phương sai dải giá Garman-Klass [7],')
    with open(ch5_path, 'w', encoding='utf-8', newline='') as f:
        f.write(ch5_text)
    print("Updated chuong_5_ket_luan.md: added citation [7] to Garman-Klass.")
else:
    print("chuong_5_ket_luan.md already has Garman-Klass [7].")

# -------------------------------------------------------------
# 2. Update chuong_2_co_so_ly_thuyet.md: FVG parameter explanation
# -------------------------------------------------------------
ch2_path = os.path.join(thesis_dir, 'chuong_2_co_so_ly_thuyet.md')
with open(ch2_path, 'r', encoding='utf-8') as f:
    ch2_text = f.read()

old_fvg_p = """Trong mã nguồn mô hình thực nghiệm của hệ thống VECTRA, hệ số tỷ lệ được ấn định ở mức $\\alpha = 0{,}15$.

*Nguyên tắc đóng dấu thời gian và loại trừ rò rỉ dữ liệu tương lai:* Mẫu hình FVG là một cấu trúc trải dài qua ba cây nến liên tiếp. Do đó, mẫu hình chỉ được xác nhận hoàn tất khi cây nến thứ ba đóng cửa tại thời điểm $t$. Toàn bộ véc-tơ đặc trưng và tín hiệu chỉ được tính toán và đóng dấu thời gian tại thời điểm $t$ khi dữ liệu nến thứ ba đã hoàn toàn sẵn có trong lịch sử, loại trừ nguy cơ rò rỉ dữ liệu tương lai.

*Bản chất đặc trưng hình học đại diện và tiêu chí nhận diện:* Trong phạm vi đồ án, FVG được định nghĩa theo điều kiện hình học giữa giá cao nhất của nến thứ nhất và giá thấp nhất của nến thứ ba đối với chiều tăng; chiều giảm được xác định theo điều kiện đối xứng. Ngoài điều kiện khoảng cách giá tối thiểu $\\epsilon_{\\text{threshold}} = \\alpha \\cdot \\text{ATR}_{14}(t)$ với $\\alpha = 0{,}15$, hệ thống sử dụng quan hệ giữa giá đóng cửa của nến giữa và nến thứ nhất như một tiêu chí xác nhận hướng. Đây là quy tắc nhận diện do đồ án lựa chọn và được đánh giá bằng thực nghiệm, không phải bằng chứng trực tiếp về sự thiếu hụt thanh khoản trên toàn thị trường hay dấu vết khớp lệnh của các tổ chức lớn."""

new_fvg_p = """Ngưỡng nhận diện FVG được thiết kế theo biên độ biến động thích ứng, với ngưỡng tối thiểu bằng $\\epsilon_{\\text{threshold}} = \\alpha \\cdot \\text{ATR}_{14}(t)$ (trong đó $\\alpha = 0{,}15$). Đây là tham số thiết kế được lựa chọn trong phạm vi nghiên cứu nhằm điều chỉnh điều kiện nhận diện khoảng trống theo biến động gần đây của thị trường, không được xem là một ngưỡng tối ưu phổ quát cho mọi tài sản hoặc chế độ thị trường. Công thức này được triển khai trong cả động cơ backtest và chiến lược vận hành. Việc xác nhận tương đương tín hiệu giữa hai thành phần cần dựa trên kiểm thử đối chiếu sử dụng cùng dữ liệu nến, điều kiện khởi tạo chỉ báo và cấu hình chiến lược.

*Nguyên tắc đóng dấu thời gian và loại trừ rò rỉ dữ liệu tương lai:* Mẫu hình FVG là một cấu trúc trải dài qua ba cây nến liên tiếp. Do đó, mẫu hình chỉ được xác nhận hoàn tất khi cây nến thứ ba đóng cửa tại thời điểm $t$. Toàn bộ véc-tơ đặc trưng và tín hiệu chỉ được tính toán và đóng dấu thời gian tại thời điểm $t$ khi dữ liệu nến thứ ba đã hoàn toàn sẵn có trong lịch sử, loại trừ nguy cơ rò rỉ dữ liệu tương lai.

*Bản chất đặc trưng hình học đại diện và tiêu chí nhận diện:* Trong phạm vi đồ án, FVG được định nghĩa theo điều kiện hình học giữa giá cao nhất của nến thứ nhất và giá thấp nhất của nến thứ ba đối với chiều tăng; chiều giảm được xác định theo điều kiện đối xứng. Ngoài điều kiện khoảng cách giá tối thiểu $\\epsilon_{\\text{threshold}} = 0{,}15 \\cdot \\text{ATR}_{14}(t)$, hệ thống sử dụng quan hệ giữa giá đóng cửa của nến gia tốc ở giữa và nến thứ nhất như một tiêu chí xác nhận hướng. Đây là quy tắc nhận diện do đồ án lựa chọn và được đánh giá bằng thực nghiệm, không phải bằng chứng trực tiếp về sự thiếu hụt thanh khoản trên toàn thị trường hay dấu vết khớp lệnh của các tổ chức lớn."""

# Normalize line endings for replacement
ch2_text_norm = ch2_text.replace('\r\n', '\n')
old_fvg_p_norm = old_fvg_p.replace('\r\n', '\n')
new_fvg_p_norm = new_fvg_p.replace('\r\n', '\n')

if old_fvg_p_norm in ch2_text_norm:
    ch2_text_norm = ch2_text_norm.replace(old_fvg_p_norm, new_fvg_p_norm)
    with open(ch2_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(ch2_text_norm)
    print("Updated chuong_2_co_so_ly_thuyet.md with rigorous FVG design choice description.")
else:
    print("Warning: old FVG text not found in Chapter 2, check manually.")

# -------------------------------------------------------------
# 3. Update chuong_3_thiet_ke_he_thong.md
# -------------------------------------------------------------
ch3_path = os.path.join(thesis_dir, 'chuong_3_thiet_ke_he_thong.md')
with open(ch3_path, 'r', encoding='utf-8') as f:
    ch3_text = f.read()

# First, clean literal \n on all lines where it was accidentally escaped
# Note: we must preserve actual LaTeX commands like \neq, \nabla, \nu, \neg, \norm
import re

def expand_escaped_newlines(text):
    # Split text into lines
    lines = text.splitlines()
    new_lines = []
    latex_tokens = {'nabla', 'neq', 'nu', 'neg', 'norm', 'newline', 'not', 'notin', 'ni', 'natural'}
    for line in lines:
        if r'\n' in line:
            # Replace \n when not part of LaTeX commands
            # We can use regex to replace \n followed by space, letter (not in latex_tokens), or end of string
            def repl(m):
                # m.group(0) is \n...
                suffix = m.group(1)
                if suffix in latex_tokens:
                    return m.group(0) # keep as is
                return '\n' + suffix
            line_expanded = re.sub(r'\\n([a-zA-Z]*)', repl, line)
            # also replace \\n\\n with \n\n
            line_expanded = line_expanded.replace(r'\n', '\n')
            new_lines.append(line_expanded)
        else:
            new_lines.append(line)
    return '\n'.join(new_lines)

ch3_expanded = expand_escaped_newlines(ch3_text)

# Replace Section 3.5.2 text
sec_352_new = """### 3.5.2. Cơ chế đầu ra có cấu trúc và kiểm định kết quả phân tích vĩ mô

Để tích hợp kết quả phân tích từ mô hình ngôn ngữ lớn vào đường ống định lượng, hệ thống sử dụng cơ chế đầu ra có cấu trúc (Structured Outputs) dựa trên JSON Schema. Lược đồ phản hồi được định nghĩa theo cấu trúc thực tế của hệ thống, bao gồm các trường `trend_macro`, `trend_intraday`, `scenario_a` và `scenario_b`, với kiểu dữ liệu và các giá trị được phép quy định trong schema tương ứng:
- `trend_macro`: Xu hướng vĩ mô trung hạn, bắt buộc thuộc tập giá trị rời rạc `{"BULLISH", "BEARISH", "SIDEWAYS"}`.
- `trend_intraday`: Xu hướng trong ngày theo hành động giá H1, bắt buộc thuộc `{"BULLISH", "BEARISH", "SIDEWAYS"}`.
- `scenario_a`: Kịch bản giao dịch định chế chính và điều kiện kích hoạt.
- `scenario_b`: Kịch bản phòng ngừa rủi ro và các mốc vô hiệu hóa cấu trúc.

Ở tầng sinh kết quả, yêu cầu định dạng có cấu trúc giúp hạn chế sai lệch cú pháp và bảo đảm phản hồi tuân thủ các ràng buộc schema được backend hỗ trợ. Tuy nhiên, tính hợp lệ về cấu trúc không đồng nghĩa với tính chính xác của nhận định tài chính. Mô hình vẫn có thể đưa ra kết luận sai về xu hướng hoặc tạo ra các kịch bản không phù hợp với dữ liệu đầu vào; do đó, kết quả ngôn ngữ không được xem là bằng chứng độc lập để bảo đảm một quyết định giao dịch.

Ở tầng ứng dụng Python, hệ thống tiếp tục xử lý các tình huống bất thường như lỗi kết nối, quá thời gian chờ, phản hồi bị từ chối, dữ liệu không đầy đủ hoặc không thể giải mã theo định dạng mong đợi. Kết quả chỉ được chuyển tiếp đến các thành phần sử dụng sau khi hoàn thành các bước kiểm tra cần thiết. Khi phân hệ LLM không khả dụng, hệ thống sử dụng cơ chế dự phòng định lượng tất định theo thiết kế của `precious_metals_adapter.py`, dựa trên các biến số vĩ mô được cấu hình. Trạng thái nguồn dữ liệu và trạng thái dự phòng cần được ghi nhận để phân biệt kết quả do LLM tạo ra với kết quả từ bộ tính toán tất định.

Cần phân biệt cơ chế chuyển sang bộ tính toán dự phòng với nguyên tắc Fail-Closed. Việc sử dụng một nguồn dự phòng là cơ chế chuyển đổi khi có lỗi (fallback); chỉ khi các điều kiện cho phép giao dịch không còn được xác nhận hoặc cả nguồn dự phòng cũng không hợp lệ, hệ thống mới được mô tả là khóa mở vị thế mới theo chính sách Fail-Closed. Trong mọi trường hợp, các chốt an toàn và điều kiện quản trị rủi ro tất định vẫn có quyền ngăn giao dịch, không phụ thuộc vào việc phản hồi LLM có hợp lệ về cú pháp hay không.

*Bảng 3.4: Bảng quy tắc xử lý nguồn dữ liệu vĩ mô và trạng thái điều phối hệ thống*

| Nguồn tín hiệu vĩ mô | Kết quả suy luận / Trạng thái kết nối | Giá trị điều phối `macro_bias` | Hành vi điều phối của hệ thống |
| :--- | :--- | :--- | :--- |
| **LLM (Qwen 2.5 Structured)** | Hợp lệ theo JSON Schema | `BULLISH` / `BEARISH` / `SIDEWAYS` | Cung cấp xu hướng định tính cho Cổng quyết định Tầng 4 |
| **Dự phòng định lượng (Fallback)** | LLM ngoại tuyến hoặc hết thời gian chờ | Lấy từ mô hình 5 nhân tố của `precious_metals_adapter` | Chuyển đổi sang bộ tính toán tất định từ Real Yield, DXY, VIX |
| **Khóa an toàn (Fail-Closed)** | Mất toàn bộ nguồn cấp dữ liệu hoặc vi phạm chốt rủi ro | `ERROR` / `BLOCKED` | Tầng 4 từ chối cấp phép, khóa mở mọi vị thế mới |"""

# Find Section 3.5.2 to replace
# From "### 3.5.2" up to "### 3.5.3"
pattern_352 = re.compile(r'### 3\.5\.2\..*?(?=### 3\.5\.3\.)', re.DOTALL)
if pattern_352.search(ch3_expanded):
    ch3_expanded = pattern_352.sub(sec_352_new + '\n\n', ch3_expanded)
    print("Replaced Section 3.5.2 successfully!")
else:
    print("Warning: Section 3.5.2 pattern not found!")

# Clean cliché in Section 3.5.3
ch3_expanded = ch3_expanded.replace(
    'Để hỗ trợ người vận hành nắm bắt bức tranh toàn cảnh về bối cảnh kinh tế',
    'Để hỗ trợ người vận hành theo dõi toàn diện bối cảnh kinh tế vĩ mô'
)

# Update Section 3.6.1 gk_vol text
gk_target = """Trong hệ thống VECTRA, biến `gk_vol` được tính bằng căn bậc hai của phương sai Garman–Klass trung bình trên cửa sổ 14 nến, sau đó nhân hệ số chuẩn hóa 1000:

$$\\text{gk\\_vol}(t) = \\sqrt{\\max\\left(0, \\frac{1}{14} \\sum_{j=0}^{13} \\sigma^2_{\\text{GK}}(t-j)\\right)} \\times 1000$$"""

gk_replacement = """Trong hệ thống VECTRA, biến `gk_vol` được tính bằng căn bậc hai của phương sai Garman–Klass trung bình trên cửa sổ 14 nến, sau đó nhân hệ số chuẩn hóa 1000:

$$\\text{gk\\_vol}(t) = \\sqrt{\\max\\left(0, \\frac{1}{14} \\sum_{j=0}^{13} \\sigma^2_{\\text{GK}}(t-j)\\right)} \\times 1000$$

Trong mô hình Meta-Labeling, đặc trưng `gk_vol` được chuẩn hóa bằng hệ số $1000$ ở cả giai đoạn huấn luyện và suy luận. Một hàm tính toán riêng sử dụng hệ số $100$ phục vụ biểu diễn biến động theo đơn vị phần trăm trong giao diện và nội dung gửi đến mô hình ngôn ngữ lớn; giá trị này không được sử dụng trực tiếp trong véc-tơ đặc trưng LightGBM. Việc phân tách hai cách biểu diễn không tạo ra sự khác biệt về thang đo của đặc trưng đầu vào mô hình, với điều kiện công thức, cửa sổ tính toán và nguồn dữ liệu sử dụng giữa huấn luyện và suy luận được duy trì nhất quán."""

if gk_target in ch3_expanded:
    ch3_expanded = ch3_expanded.replace(gk_target, gk_replacement)
    print("Updated Section 3.6.1 gk_vol description successfully!")
else:
    print("Warning: gk_target not found in Chapter 3!")

with open(ch3_path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(ch3_expanded)

print("Updated chuong_3_thiet_ke_he_thong.md successfully.")
