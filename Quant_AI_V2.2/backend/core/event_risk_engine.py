"""
Event Risk Engine - Multi-Asset High-Impact News Filter & Active Position Defense
===================================================================================
Institutional Risk Layer for Quant_AI V2.2:
1. Multi-Asset Currency Mapping:
   - Ánh xạ tiền tệ chính xác theo sự kiện (US -> USD, EU -> EUR, GB -> GBP, JP -> JPY, AU -> AUD, CA -> CAD).
   - Phân loại tài sản đặc biệt: Vàng (XAUUSD), Bạc (XAGUSD), Chỉ số Mỹ (US30, NAS100) phụ thuộc vào tin USD.
   - Không cào bằng toàn bộ danh mục: Tin ECB chỉ phong tỏa cặp EUR, tin BOE chỉ phong tỏa cặp GBP, v.v.
2. Pre-News Active Position Defense (T-15 phút trước giờ G):
   - Lệnh lãi >= 1.5R: Tự động dời SL về giá hòa vốn (Breakeven + buffer bù phí).
   - Lệnh lãi nhẹ 0.5R - 1.5R: Tự động chốt 50% khối lượng (Partial Close) và dời SL còn lại về hòa vốn.
   - Lệnh âm: Giữ nguyên để người dùng tự tùy chỉnh theo cấu hình SL/Risk cá nhân.
3. Post-News Liquidity & Spread Normalizer:
   - Kiểm tra Spread thực tế đã co lại dưới ngưỡng an toàn trước khi mở lại giao dịch.
"""

import time
from datetime import datetime, timezone
from loguru import logger
from backend.infrastructure.brokers.mt5_safe import mt5


COUNTRY_CURRENCY_MAP = {
    "US": "USD",
    "EU": "EUR",
    "GB": "GBP",
    "JP": "JPY",
    "AU": "AUD",
    "CA": "CAD",
    "CH": "CHF",
    "NZ": "NZD",
}

# Tài sản phụ thuộc trực tiếp vào tin vĩ mô Mỹ (USD High-Impact)
USD_DEPENDENT_ASSETS = {
    "XAUUSD", "GOLD", "XAGUSD", "SILVER",
    "US30", "DJ30", "WS30", "NAS100", "USTEC", "US500", "SPX500",
    "BTCUSD", "ETHUSD", "USOIL", "UKOIL", "WTI"
}


class EventRiskEngine:
    """Manages news risk filtering, asset mapping, and pre-news position defense."""

    def __init__(
        self,
        execution_manager=None,
        calendar_engine=None,
        defense_window_mins: int = 15,
        pause_window_mins: int = 30,
        max_spread_multiplier: float = 1.5,
    ):
        self.exec_mgr = execution_manager
        self.cal_engine = calendar_engine
        self.defense_window_mins = defense_window_mins
        self.pause_window_mins = pause_window_mins
        self.max_spread_multiplier = max_spread_multiplier

        self._news_events_cache = []
        self._news_events_ts = 0.0
        # Ghi nhận các vị thế đã được phòng thủ để tránh gọi lặp lại mỗi chu kỳ
        self._defended_positions = {}  # {ticket: {"action": "breakeven"|"partial", "event_ts": ts}}

    def refresh_events_if_needed(self):
        """Cache events trong 10 phút để tránh spam request đến Calendar API."""
        now = time.time()
        if not self._news_events_cache or (now - self._news_events_ts) > 600:
            if not self.cal_engine:
                from backend.infrastructure.data_providers.macro.calendar_engine import CalendarEngine
                self.cal_engine = CalendarEngine()
            try:
                self._news_events_cache = self.cal_engine.fetch_events()
                self._news_events_ts = now
            except Exception as e:
                logger.warning(f"[EventRisk] Calendar fetch failed: {e}")
                self._news_events_cache = []
                self._news_events_ts = now

    def is_symbol_impacted_by_event(self, symbol: str, event_country: str, event_title: str) -> bool:
        """
        Kiểm tra xem một mã tài sản cụ thể có bị ảnh hưởng bởi tin tức của quốc gia đó không.
        Giải quyết triệt để lỗi cào bằng đa tài sản.
        """
        sym_clean = symbol.upper().split(".")[0].replace("/", "")
        event_cur = COUNTRY_CURRENCY_MAP.get(event_country.upper(), event_country.upper())

        # 1. Nếu tiền tệ của tin tức nằm trong tên cặp tiền (VD: USD trong EURUSD, GBP trong GBPJPY)
        if event_cur and event_cur in sym_clean:
            return True

        # 2. Nếu là tin Mỹ (US) và tài sản phụ thuộc trực tiếp vào USD (Vàng, Dầu, Chỉ số Mỹ, Crypto)
        if event_country.upper() == "US":
            for dep in USD_DEPENDENT_ASSETS:
                if sym_clean.startswith(dep) or dep in sym_clean:
                    return True

        return False

    def check_news_impact_for_symbol(self, symbol: str) -> tuple[bool, str]:
        """
        Kiểm tra xem mã tài sản này có đang nằm trong khoảng ±pause_window_mins của tin tức đỏ không.
        Chỉ khóa các mã bị ảnh hưởng trực tiếp bởi quốc gia ra tin.
        """
        self.refresh_events_if_needed()
        if not self._news_events_cache or self.pause_window_mins <= 0:
            return False, ""

        now_ts = datetime.now(timezone.utc).timestamp() + (7 * 3600)  # Giờ VN
        window_sec = self.pause_window_mins * 60

        for e in self._news_events_cache:
            if e.get("impact", 0) >= 2:  # Tin đỏ (High Impact)
                event_ts = e.get("sort_key", 0)
                if abs(now_ts - event_ts) <= window_sec:
                    country = e.get("country", "")
                    title = e.get("title", "")
                    if self.is_symbol_impacted_by_event(symbol, country, title):
                        return True, f"{title} ({country})"

        return False, ""

    def evaluate_pre_news_defense(self) -> list[dict]:
        """
        KÍCH HOẠT CHẾ ĐỘ PHÒNG THỦ VỊ THẾ TRƯỚC GIỜ TIN (T - 15 phút):
        - Quét toàn bộ lệnh đang chạy trên MT5.
        - Lọc các lệnh thuộc các cặp tiền bị ảnh hưởng bởi tin đỏ sắp tới.
        - Áp dụng các quy tắc bảo toàn vốn:
          * Lãi >= 1.5R: Dời SL về Breakeven (Hòa vốn + buffer).
          * Lãi 0.5R - 1.5R: Chốt 50% khối lượng (Partial Close) và dời SL về Breakeven.
          * Lệnh âm: Giữ nguyên để người dùng tự quản lý theo chiến lược.
        """
        self.refresh_events_if_needed()
        if not self._news_events_cache or not self.exec_mgr:
            return []

        now_ts = datetime.now(timezone.utc).timestamp() + (7 * 3600)
        defense_sec = self.defense_window_mins * 60

        # Tìm các sự kiện đỏ sắp diễn ra trong khoảng [now, now + 15 phút]
        upcoming_events = []
        for e in self._news_events_cache:
            if e.get("impact", 0) >= 2:
                event_ts = e.get("sort_key", 0)
                # Đang nằm trong giai đoạn trước giờ tin: 0 < (event_ts - now_ts) <= defense_sec
                if 0 <= (event_ts - now_ts) <= defense_sec:
                    upcoming_events.append(e)

        if not upcoming_events:
            return []

        positions = mt5.positions_get()
        if not positions:
            return []

        defense_results = []

        for pos in positions:
            sym = pos.symbol
            ticket = pos.ticket

            # Kiểm tra xem mã của vị thế này có bị ảnh hưởng bởi tin sắp ra không
            impacting_event = None
            for e in upcoming_events:
                if self.is_symbol_impacted_by_event(sym, e.get("country", ""), e.get("title", "")):
                    impacting_event = e
                    break

            if not impacting_event:
                continue

            event_id = f"{ticket}_{impacting_event.get('sort_key', 0)}"
            if event_id in self._defended_positions:
                continue  # Đã phòng vệ lệnh này cho sự kiện này rồi

            # Tính toán chỉ số R-multiple hiện tại
            tick = mt5.symbol_info_tick(sym)
            info = mt5.symbol_info(sym)
            if not tick or not info:
                continue

            point = info.point if info.point > 0 else 0.0001
            digits = info.digits if info else 2
            is_buy = (pos.type == mt5.ORDER_TYPE_BUY)

            curr_price = tick.bid if is_buy else tick.ask
            open_price = pos.price_open
            sl_price = pos.sl

            # Khoảng cách R rủi ro ban đầu
            if sl_price and sl_price > 0:
                risk_dist = abs(open_price - sl_price)
            else:
                risk_dist = 20.0 * point * 10  # Fallback 20 pips

            if risk_dist <= 0:
                risk_dist = 20.0 * point * 10

            # Khoảng lãi hiện tại
            profit_dist = (curr_price - open_price) if is_buy else (open_price - curr_price)
            r_multiple = profit_dist / risk_dist if risk_dist > 0 else 0.0

            news_title = f"{impacting_event.get('title')} ({impacting_event.get('country')})"

            # Buffer bù phí commission (2 pips)
            be_buffer = 2.0 * point * (10 if digits in (3, 5) else 1)
            be_sl = round(open_price + (be_buffer if is_buy else -be_buffer), digits)

            # QUY TẮC 1: Lệnh đang lãi >= 1.5R -> Tự động dời SL về Hòa vốn (Breakeven)
            if r_multiple >= 1.5:
                # Chỉ dời nếu SL mới tốt hơn SL hiện tại
                should_move = (be_sl > sl_price) if is_buy else (be_sl < sl_price or sl_price == 0)
                if should_move:
                    res = self.exec_mgr.modify_position(ticket, sl=be_sl, tp=pos.tp)
                    logger.info(
                        f"[EventRisk] AUTO-BREAKEVEN: Ticket #{ticket} ({sym}) profit +{r_multiple:.2f}R >= 1.5R. "
                        f"SL moved to {be_sl} before '{news_title}'."
                    )
                    self._defended_positions[event_id] = {"action": "breakeven", "r": r_multiple}
                    defense_results.append({
                        "ticket": ticket,
                        "symbol": sym,
                        "action": "AUTO_BREAKEVEN",
                        "r_multiple": round(r_multiple, 2),
                        "news": news_title,
                        "status": res.get("status", "unknown")
                    })

            # QUY TẮC 2: Lệnh đang lãi nhẹ 0.5R - 1.5R -> Chốt 50% Volume & dời phần còn lại về Breakeven
            elif 0.5 <= r_multiple < 1.5:
                half_vol = round(pos.volume * 0.5, 2)
                min_vol = info.volume_min if info else 0.01
                step_vol = info.volume_step if info else 0.01
                half_vol = round(round(half_vol / step_vol) * step_vol, 2)

                if half_vol >= min_vol and (pos.volume - half_vol) >= min_vol:
                    close_res = self.exec_mgr.close_position(ticket, volume=half_vol)
                    # Dời SL phần còn lại về Breakeven
                    be_res = self.exec_mgr.modify_position(ticket, sl=be_sl, tp=pos.tp)
                    logger.info(
                        f"[EventRisk] PARTIAL CLOSE 50%: Ticket #{ticket} ({sym}) profit +{r_multiple:.2f}R. "
                        f"Closed {half_vol} lots & moved remaining to BE before '{news_title}'."
                    )
                    self._defended_positions[event_id] = {"action": "partial_close", "r": r_multiple}
                    defense_results.append({
                        "ticket": ticket,
                        "symbol": sym,
                        "action": "PARTIAL_CLOSE_50",
                        "r_multiple": round(r_multiple, 2),
                        "closed_volume": half_vol,
                        "news": news_title,
                        "status": close_res.get("status", "unknown")
                    })

            # Lệnh âm: Giữ nguyên theo yêu cầu người dùng (không can thiệp ép cắt sớm)

        return defense_results

    def check_spread_normalization(self, symbol: str) -> tuple[bool, int, int]:
        """
        Cảm biến thanh khoản sau tin: Kiểm tra spread hiện tại có bị giãn bất thường không.
        Returns: (is_ok, current_spread, max_allowed_spread)
        """
        info = mt5.symbol_info(symbol)
        if not info:
            return True, 0, 0

        curr_spread = info.spread
        # Spread trung bình an toàn dựa trên quy định của từng loại tài sản
        # Forex 5 số: ~15-25 points; Vàng: ~25-45 points; Chỉ số: ~50-100 points
        sym_upper = symbol.upper()
        if "XAU" in sym_upper or "GOLD" in sym_upper:
            base_safe_spread = 45
        elif any(idx in sym_upper for idx in ["US30", "NAS100", "US500", "SPX"]):
            base_safe_spread = 80
        elif "BTC" in sym_upper:
            base_safe_spread = 2000
        else:
            base_safe_spread = 25

        max_allowed = int(base_safe_spread * self.max_spread_multiplier)
        if curr_spread > max_allowed:
            return False, curr_spread, max_allowed

        return True, curr_spread, max_allowed
