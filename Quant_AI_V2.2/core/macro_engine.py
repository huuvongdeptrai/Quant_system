from core.mt5_safe import mt5

class MacroEngine:
    def __init__(self):
        # BẢNG ĐIỀU HƯỚNG TƯƠNG QUAN LIÊN THỊ TRƯỜNG
        # Sau này muốn mở rộng quỹ, chỉ cần thêm mã vào đây
        self.correlation_map = {
            'XAU': ['DXY', 'USVIX', 'US10Y'], # Tên mã có thể thay đổi tùy Broker (VD: DXY, USDX, DX)
            'BTC': ['USTEC', 'US500'],
            'DEFAULT': ['DXY']
        }

    def _get_live_price(self, symbol_list):
        # Hàm quét giá tự động: Thử nhiều tên gọi khác nhau của Broker
        for sym in symbol_list:
            mt5.symbol_select(sym, True)
            tick = mt5.symbol_info_tick(sym)
            if tick and tick.bid > 0:
                return f"{sym}: {tick.bid}"
        return None

    def build_macro_context(self, target_symbol):
        ctx = "\n--- PHÂN TÍCH LIÊN THỊ TRƯỜNG (INTERMARKET) ---\n"
        
        # 1. Nhận diện cấu trúc mã
        target_upper = target_symbol.upper()
        drivers = self.correlation_map['DEFAULT']
        
        if 'XAU' in target_upper or 'GOLD' in target_upper:
            drivers = self.correlation_map['XAU']
            ctx += "🔍 Nhận diện tài sản: VÀNG (Tài sản trú ẩn an toàn)\n"
        elif 'BTC' in target_upper or 'CRYPTO' in target_upper:
            drivers = self.correlation_map['BTC']
            ctx += "🔍 Nhận diện tài sản: BITCOIN (Tài sản rủi ro cao)\n"
        else:
            ctx += "🔍 Nhận diện tài sản: NGOẠI TỆ / TIÊU CHUẨN\n"

        # 2. Quét giá trực tiếp từ MT5 cho các mã ảnh hưởng
        macro_data = []
        
        # Mapping các tên gọi phổ biến của Broker
        broker_symbols = {
            'DXY': ['DXY', 'USDX', 'DX_m', 'USDOLLAR'],
            'USVIX': ['VIX', 'USVIX', 'VOLATILITY'],
            'US10Y': ['US10Y', 'US10YR', 'TNX'],
            'USTEC': ['USTEC', 'NAS100', 'NDX', 'US100'],
            'US500': ['US500', 'SPX500', 'SP500']
        }

        for driver in drivers:
            possible_names = broker_symbols.get(driver, [driver])
            price_str = self._get_live_price(possible_names)
            if price_str:
                macro_data.append(price_str)
                
        if macro_data:
            ctx += "Tình trạng dòng tiền thế giới (Live MT5): " + ", ".join(macro_data) + "\n"
        else:
            ctx += "Tình trạng dòng tiền thế giới: Trống (Không tìm thấy mã tương quan trên Broker này)\n"
            
        # 3. CHỖ TRỐNG CHO MODULE TIN TỨC (TELEGRAM)
        # Sẽ tích hợp module Telegram Scraper của V1 vào đây sau
        ctx += "\n--- TIN TỨC KINH TẾ ---\n"
        ctx += "(Luồng tin tức Telegram sẽ được nạp vào đây...)\n"
        
        return ctx