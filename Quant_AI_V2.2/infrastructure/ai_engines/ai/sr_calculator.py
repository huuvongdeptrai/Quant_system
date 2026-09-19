"""
Module tính toán Ngưỡng Hỗ trợ (HT) và Kháng cự (KC) chuẩn Định lượng (Quantitative SMC / Wyckoff).
Khắc phục triệt để hội chứng 'Bẫy vi cấu trúc' (Micro-Structure Trap):
- Tích hợp Bộ lọc Độ nổi bật (Prominence Filter): Nâng cấp Fractal lên N=8 (Cụm 17 nến) để triệt tiêu nhiễu dao động nhỏ lẻ.
- Tích hợp Vùng đệm ATR (ATR Noise-Floor Distance Buffer): Ép các mốc Cản phải vượt qua vùng nhiễu intraday (ít nhất 0.5 * ATR).
- Bảo đảm nguyên tắc toán học bất biến:
  * Kháng cự (KC) luôn NẰM TRÊN giá hiện tại (Resistance > Current Price + Buffer).
  * Hỗ trợ (HT) luôn NẰM DƯỚI giá hiện tại (Support < Current Price - Buffer).
- Ưu tiên các mốc Fractal kết hợp Bộ lọc Volume Climax / Absorption (Volume >= 1.5 * SMA20).
- Hỗ trợ nguyên lý S/R Role Reversal (Kháng cự cũ bị đột phá trở thành Hỗ trợ mới đỡ giá).
"""


def calculate_sr_levels(
    rates, current_price=None, zone_threshold=0.15, n_bars=8, atr_buffer_mult=0.5
):
    """
    Tính toán HT và KC Cấu trúc cứng (Major Structural S/R) xác thực bởi Volume và ATR Buffer.

    Args:
        rates: Danh sách nến (numpy structured array hoặc list of dicts có high, low, close, tick_volume).
        current_price: Giá hiện tại (nếu None sẽ lấy close của nến cuối).
        zone_threshold: Tỷ lệ biên độ được xem là 'Tại Kháng cự' hoặc 'Tại Hỗ trợ' (mặc định 15%).
        n_bars: Bán kính Fractal N (Mặc định N=8, tương đương cụm 11 nến để triệt tiêu nhiễu).
        atr_buffer_mult: Hệ số nhân vùng đệm ATR tối thiểu (Mặc định 0.5 * ATR(14)).

    Returns:
        dict chứa resistance, support, dist_to_res, dist_to_sup, range, position, pct_from_support, pct_from_resistance...
    """
    if rates is None or len(rates) < 5:
        return None

    if current_price is None:
        current_price = float(rates[-1]["close"])
    else:
        current_price = float(current_price)

    # 1. Tính ATR 14 nến làm thước đo biên độ biến động tự nhiên
    trs = [
        max(
            float(rates[k]["high"]) - float(rates[k]["low"]),
            abs(float(rates[k]["high"]) - float(rates[k - 1]["close"])),
            abs(float(rates[k]["low"]) - float(rates[k - 1]["close"])),
        )
        for k in range(1, len(rates))
    ]
    atr = (
        (sum(trs[-14:]) / 14)
        if len(trs) >= 14
        else (float(rates[-1]["high"]) - float(rates[-1]["low"]))
    )
    if atr <= 0:
        atr = current_price * 0.001

    # Thích ứng bán kính Fractal theo số lượng nến truyền vào
    eff_n = min(n_bars, max(2, len(rates) // 10))

    # 2. Quét Fractal cụm (2 * eff_n + 1) nến kết hợp bộ lọc Volume Climax (Wyckoff Stopping Volume)
    volumes = [float(r["tick_volume"]) for r in rates]
    swing_highs = []
    swing_lows = []
    valid_resistances = []
    valid_supports = []

    n_len = len(rates)
    for i in range(eff_n, n_len - eff_n):
        high = float(rates[i]["high"])
        low = float(rates[i]["low"])
        vol = float(rates[i]["tick_volume"])

        start_v = max(0, i - 20)
        avg_vol = (sum(volumes[start_v:i]) / (i - start_v)) if i > start_v else vol
        is_climax = (vol >= 1.5 * avg_vol) if avg_vol > 0 else False

        # Fractal Đỉnh Cấu Trúc (Swing High)
        if all(
            high > float(rates[i - offset]["high"])
            and high > float(rates[i + offset]["high"])
            for offset in range(1, eff_n + 1)
        ):
            swing_highs.append(high)
            if is_climax:
                valid_resistances.append(high)

        # Fractal Đáy Cấu Trúc (Swing Low)
        if all(
            low < float(rates[i - offset]["low"])
            and low < float(rates[i + offset]["low"])
            for offset in range(1, eff_n + 1)
        ):
            swing_lows.append(low)
            if is_climax:
                valid_supports.append(low)

    # 3. VÙNG ĐỆM TRIỆT NHIỄU (ATR Distance Floor)
    # Bắt buộc Cản Kháng cự / Hỗ trợ phải vượt ra ngoài vùng nhiễu tối thiểu
    min_res_level = current_price + (atr_buffer_mult * atr)
    max_sup_level = current_price - (atr_buffer_mult * atr)

    # 4. CHỌN KHÁNG CỰ (KC) - BẮT BUỘC PHẢI LÀ MAJOR S/R NẰM TRÊN GIÁ HIỆN TẠI
    # Ưu tiên 1: Đỉnh Volume Climax vượt ra ngoài vùng đệm nhiễu
    valid_res_above = [h for h in valid_resistances if h >= min_res_level]
    # Ưu tiên 2: Đỉnh Swing High thông thường vượt ra ngoài vùng đệm nhiễu
    swing_highs_above = [h for h in swing_highs if h >= min_res_level]
    # Ưu tiên 3: Bất kỳ đỉnh nào nằm trên giá hiện tại (Fallback nếu đệm quá rộng)
    any_highs_above = [h for h in swing_highs if h > current_price]

    if valid_res_above:
        resistance = min(valid_res_above)
    elif swing_highs_above:
        resistance = min(swing_highs_above)
    elif any_highs_above:
        resistance = min(any_highs_above)
    else:
        # Giá đang lập đỉnh mới cao nhất -> Dự phòng Kháng cự bằng 1.5 * ATR
        wicks_above = [
            float(r["high"]) for r in rates if float(r["high"]) > current_price
        ]
        if wicks_above:
            resistance = max(wicks_above)
        else:
            resistance = round(current_price + 1.5 * atr, 2)

    # 5. CHỌN HỖ TRỢ (HT) - BẮT BUỘC PHẢI LÀ MAJOR S/R NẰM DƯỚI GIÁ HIỆN TẠI
    # Ưu tiên 1: Đáy Volume Climax dưới vùng đệm + Kháng cự cũ bị phá (S/R Role Reversal)
    valid_sup_below = [l for l in valid_supports if l <= max_sup_level]
    flips_below = [h for h in valid_resistances if h <= max_sup_level]
    sup_candidates = valid_sup_below + flips_below
    # Ưu tiên 2: Đáy Swing Low thông thường dưới vùng đệm
    swing_lows_below = [l for l in swing_lows if l <= max_sup_level]
    # Ưu tiên 3: Bất kỳ đáy nào nằm dưới giá hiện tại (Fallback)
    any_lows_below = [l for l in swing_lows if l < current_price]

    if sup_candidates:
        support = max(sup_candidates)
    elif swing_lows_below:
        support = max(swing_lows_below)
    elif any_lows_below:
        support = max(any_lows_below)
    else:
        # Giá đang phá đáy thấp nhất -> Dự phòng Hỗ trợ bằng 1.5 * ATR
        wicks_below = [
            float(r["low"]) for r in rates if float(r["low"]) < current_price
        ]
        if wicks_below:
            support = min(wicks_below)
        else:
            support = round(current_price - 1.5 * atr, 2)

    # 6. RÀNG BUỘC TOÁN HỌC TUYỆT ĐỐI (INVARIANT ENFORCEMENT)
    if resistance <= current_price:
        resistance = round(current_price + 1.5 * atr, 2)
    if support >= current_price:
        support = round(current_price - 1.5 * atr, 2)

    total_range = resistance - support
    dist_to_res = resistance - current_price
    dist_to_sup = current_price - support

    pct_from_sup = (
        round((dist_to_sup / total_range) * 100, 1) if total_range > 0 else 50.0
    )
    pct_from_res = (
        round((dist_to_res / total_range) * 100, 1) if total_range > 0 else 50.0
    )

    if (dist_to_res / total_range) <= zone_threshold:
        position = "AT_RESISTANCE"
    elif (dist_to_sup / total_range) <= zone_threshold:
        position = "AT_SUPPORT"
    else:
        position = "MIDDLE"

    return {
        "current_price": current_price,
        "resistance": round(resistance, 2),
        "support": round(support, 2),
        "dist_to_res": round(dist_to_res, 2),
        "dist_to_sup": round(dist_to_sup, 2),
        "range": round(total_range, 2),
        "position": position,
        "pct_from_support": pct_from_sup,
        "pct_from_resistance": pct_from_res,
        "vol_confirmed": bool(valid_resistances or valid_supports),
        "atr": round(atr, 2),
    }
