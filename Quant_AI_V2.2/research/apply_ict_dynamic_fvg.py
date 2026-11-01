# -*- coding: utf-8 -*-
import sys

fpath = r'Kho_Do_An\Quant_AI_V2.2\backend\core\strategies\ict_strategy.py'
with open(fpath, 'r', encoding='utf-8') as f:
    content = f.read()

target = """            # 2. Phát hiện vùng FVG
            thresh = self.fvg_threshold_per / 100

            is_bull_fvg = (
                (l_i > prev2_h)
                and (prev_c > prev2_h)
                and ((l_i - prev2_h) / prev2_h > thresh)
            )

            is_bear_fvg = (
                (h_i < prev2_l)
                and (prev_c < prev2_l)
                and ((prev2_l - h_i) / h_i > thresh)
            )"""

replacement = """            # 2. Phát hiện vùng FVG (Chuẩn hóa vi cấu trúc thích ứng ATR động 14 chu kỳ)
            atr_i = atr_arr[i] if not np.isnan(atr_arr[i]) and atr_arr[i] > 0 else 1.0
            if self.use_dynamic_atr_fvg:
                min_gap = self.fvg_atr_mult * atr_i
                is_bull_fvg = (
                    (l_i - prev2_h > min_gap)
                    and (prev_c > c_arr[i - 2])
                )
                is_bear_fvg = (
                    (prev2_l - h_i > min_gap)
                    and (prev_c < c_arr[i - 2])
                )
            else:
                thresh = self.fvg_threshold_per / 100
                is_bull_fvg = (
                    (l_i > prev2_h)
                    and (prev_c > prev2_h)
                    and ((l_i - prev2_h) / prev2_h > thresh)
                )
                is_bear_fvg = (
                    (h_i < prev2_l)
                    and (prev_c < prev2_l)
                    and ((prev2_l - h_i) / h_i > thresh)
                )"""

# Handle CRLF if needed
if target not in content:
    target = target.replace('\n', '\r\n')
    replacement = replacement.replace('\n', '\r\n')

if target in content:
    new_content = content.replace(target, replacement, 1)
    with open(fpath, 'w', encoding='utf-8', newline='') as f:
        f.write(new_content)
    print("Successfully updated ict_strategy.py with dynamic ATR FVG!")
else:
    print("Error: Target not found in ict_strategy.py")
    sys.exit(1)
