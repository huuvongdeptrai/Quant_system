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
import json
import math
from decimal import Decimal, ROUND_FLOOR
from datetime import datetime, timezone
from loguru import logger
from backend.infrastructure.brokers.mt5_safe import mt5


COUNTRY_CURRENCY_MAP = {
    "US": "USD",
    "EU": "EUR",
    "DE": "EUR",
    "FR": "EUR",
    "IT": "EUR",
    "ES": "EUR",
    "GB": "GBP",
    "UK": "GBP",
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
        news_defense_enabled: bool = True,
        be_r_threshold: float = 1.5,
        user_max_spread: int = 0,
    ):
        self.exec_mgr = execution_manager
        self.cal_engine = calendar_engine
        self.defense_window_mins = defense_window_mins
        self.pause_window_mins = pause_window_mins
        self.max_spread_multiplier = max_spread_multiplier
        self.news_defense_enabled = news_defense_enabled
        self.be_r_threshold = be_r_threshold
        self.user_max_spread = user_max_spread

        self._news_events_cache = []
        self._news_events_ts = 0.0
        self._calendar_valid=False
        # Ghi nhận các vị thế đã được phòng thủ để tránh gọi lặp lại mỗi chu kỳ
        self._defended_positions = {}  # {ticket: {"action": "breakeven"|"partial", "event_ts": ts}}

    def refresh_events_if_needed(self):
        """Cache events trong 10 phút để tránh spam request đến Calendar API."""
        now = time.time()
        if (now - self._news_events_ts) > 600:
            if not self.cal_engine:
                from backend.infrastructure.data_providers.macro.calendar_engine import CalendarEngine
                self.cal_engine = CalendarEngine()
            try:
                self._news_events_cache = self.cal_engine.fetch_events()
                self._calendar_valid=getattr(self.cal_engine,"last_fetch_success",False) is True
                self._news_events_ts = now
            except Exception as e:
                logger.warning(f"[EventRisk] Calendar fetch failed: {e}")
                self._calendar_valid = False
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
        # SC-04: Respect Manual Override from Macro Calendar Desk
        try:
            from backend.core.macro_context_bus import MacroContextBus
            if MacroContextBus.get_instance().get_manual_override():
                return False, ""
        except Exception:
            pass

        self.refresh_events_if_needed()
        if not self._calendar_valid and not self._news_events_cache and self.pause_window_mins>0:
            return True,"Calendar data unavailable"
        if not self._news_events_cache or self.pause_window_mins <= 0:
            return False, ""

        now_ts = datetime.now(timezone.utc).timestamp()
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
        if not getattr(self, "news_defense_enabled", True):
            return []

        # SC-04: Respect Manual Override from Macro Calendar Desk
        try:
            from backend.core.macro_context_bus import MacroContextBus
            if MacroContextBus.get_instance().get_manual_override():
                logger.info("[EventRisk] Pre-News Defense bypassed due to active manual override on Calendar Desk.")
                return []
        except Exception:
            pass

        self.refresh_events_if_needed()
        if not self._news_events_cache or not self.exec_mgr:
            return []

        now_ts = datetime.now(timezone.utc).timestamp()
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
        account=mt5.account_info()
        if account is None:
            return []
        identity=(account.server,account.login)
        if getattr(self,'_defense_account',None)!=identity:
            self._defended_positions.clear()
            self._defense_account=identity

        for pos in positions:
            # SC-04 & SC-06: Do NOT defend or modify user manual trades
            pos_magic = getattr(pos, "magic", 0)
            pos_comment = str(getattr(pos, "comment", "") or "").lower()
            if "manual" in pos_comment:
                continue
            bot_magic = getattr(self.exec_mgr, "magic", 999999) if self.exec_mgr else 999999
            if isinstance(pos_magic, (int, float)) and bot_magic is not None and int(pos_magic) != int(bot_magic):
                continue

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

            event_id = f"{getattr(pos,'identifier',ticket)}_{impacting_event.get('sort_key', 0)}"
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

            from backend.database.db_manager import DatabaseManager
            db=DatabaseManager()
            acc=mt5.account_info()
            if acc is None:
                continue
            db.bind_account(acc.login,acc.server)
            saved=next((t for t in db.get_open_trades() if t.get('position_id')==getattr(pos,'identifier',ticket) or t['ticket']==ticket),None)
            if not saved or not saved.get('initial_sl'):
                continue
            initial_sl=saved['initial_sl']
            # Use original risk even after trailing/BE or manual removal of the current SL.
            risk_dist = abs(open_price - initial_sl)
            if not math.isfinite(risk_dist) or risk_dist <= 0:
                continue

            # Khoảng lãi hiện tại
            profit_dist = (curr_price - open_price) if is_buy else (open_price - curr_price)
            r_multiple = profit_dist / risk_dist if risk_dist > 0 else 0.0

            news_title = f"{impacting_event.get('title')} ({impacting_event.get('country')})"

            # Buffer bù phí commission (2 pips)
            be_buffer = 2.0 * point * (10 if digits in (3, 5) else 1)
            be_sl = round(open_price + (be_buffer if is_buy else -be_buffer), digits)

            # QUY TẮC 1: Lệnh đang lãi >= be_r_threshold (mặc định 1.5R) -> Tự động dời SL về Hòa vốn (Breakeven)
            threshold_be = getattr(self, "be_r_threshold", 1.5)
            persisted_key='defense:'+event_id
            if db.get_system_state(persisted_key,default='')=='DONE':
                continue
            if r_multiple >= threshold_be:
                # Chỉ dời nếu SL mới tốt hơn SL hiện tại
                should_move = (be_sl > sl_price) if is_buy else (be_sl < sl_price or sl_price == 0)
                if should_move:
                    res = self.exec_mgr.modify_position(ticket, sl=be_sl, tp=pos.tp)
                    logger.info(
                        f"[EventRisk] AUTO-BREAKEVEN: Ticket #{ticket} ({sym}) profit +{r_multiple:.2f}R >= {threshold_be}R. "
                        f"SL moved to {be_sl} before '{news_title}'."
                    )
                    if not res or res.get('status')!='success':
                        continue
                    db.set_system_state(persisted_key,'DONE')
                    self._defended_positions[event_id] = {"action": "breakeven", "r": r_multiple}
                    defense_results.append({
                        "ticket": ticket,
                        "symbol": sym,
                        "action": "AUTO_BREAKEVEN",
                        "r_multiple": round(r_multiple, 2),
                        "news": news_title,
                        "status": res.get("status", "unknown")
                    })

            # QUY TẮC 2: Lệnh đang lãi nhẹ 0.5R - be_r_threshold -> Chốt 50% Volume & dời phần còn lại về Breakeven
            elif 0.5 <= r_multiple < threshold_be:
                previous=db.get_system_state(persisted_key,default='')
                partial_done=previous=='PARTIAL_DONE'
                if previous.startswith('PARTIAL_PENDING:'):
                    original,target=json.loads(previous.split(':',1)[1])
                    if pos.volume<=target+1e-9:
                        partial_done=True
                        if not db.set_system_state(persisted_key,'PARTIAL_DONE'):
                            continue
                    else:
                        continue
                min_vol = info.volume_min
                step_vol = info.volume_step
                if not math.isfinite(step_vol) or step_vol <= 0:
                    continue
                half_vol = float((Decimal(str(pos.volume)) / 2 / Decimal(str(step_vol))).to_integral_value(rounding=ROUND_FLOOR) * Decimal(str(step_vol)))

                if partial_done or (half_vol >= min_vol and (pos.volume - half_vol) >= min_vol):
                    if partial_done:
                        close_res={'status':'success'}
                    else:
                        if not db.set_system_state(persisted_key,'PARTIAL_PENDING:'+json.dumps([pos.volume,pos.volume-half_vol])):
                            continue  # No irreversible action without a durable recovery marker.
                        close_res = self.exec_mgr.close_position(ticket, volume=half_vol)
                        if not close_res or close_res.get('status')!='success':
                            if close_res and close_res.get('status')=='error' and close_res.get('retcode'):
                                db.set_system_state(persisted_key,'')
                            continue
                        if close_res.get('partial_fill'):
                            continue
                        db.set_system_state(persisted_key,'PARTIAL_DONE')
                    # Dời SL phần còn lại về Breakeven
                    protected=max(sl_price,be_sl) if is_buy else (min(sl_price,be_sl) if sl_price>0 else be_sl)
                    be_res = self.exec_mgr.modify_position(ticket, sl=protected, tp=pos.tp)
                    if not be_res or be_res.get('status')!='success':
                        continue
                    db.set_system_state(persisted_key,'DONE')
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
            return False, 0, 0

        curr_spread = info.spread
        path = getattr(info, "path", "").lower() if info else ""
        sym_upper = symbol.upper().split(".")[0].replace("/", "")

        is_crypto = "crypto" in path or any(c in sym_upper for c in ["BTC", "ETH", "SOL", "XRP", "DOGE", "BNB"])
        if is_crypto:
            base_safe_spread = 6000
        elif any(idx in path for idx in ["index", "indic"]) or any(idx in sym_upper for idx in ["US30", "NAS100", "US500", "SPX", "GER40", "DAX"]):
            base_safe_spread = 80
        elif any(k in path for k in ["metal", "commodit"]) or "XAU" in sym_upper or "GOLD" in sym_upper:
            base_safe_spread = 45 if getattr(info, "digits", 2) == 2 else 450
        elif "stock" in path or "equity" in path:
            base_safe_spread = 50
        else:
            base_safe_spread = 25

        user_lim = getattr(self, "user_max_spread", 0) or 0
        if user_lim > 0:
            if is_crypto:
                max_allowed = max(base_safe_spread, user_lim * 100)
            else:
                max_allowed = user_lim
        else:
            max_allowed = int(base_safe_spread * self.max_spread_multiplier)

        if curr_spread > max_allowed:
            return False, curr_spread, max_allowed

        return True, curr_spread, max_allowed
