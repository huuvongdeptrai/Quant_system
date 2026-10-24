from backend.infrastructure.brokers.mt5_safe import mt5
from backend.infrastructure.data_providers.macro.macro_regime import MacroRegimeEngine
from backend.infrastructure.data_providers.asset_registry import AssetRegistry

from loguru import logger

# Nguong xac dinh "gia o gan S/R" (20% bien do)

ZONE_THRESHOLD = 0.20


class DecisionGate:
    """

    Ma tran quyet dinh ket hop Xu huong Vi mo + Vi tri gia so voi S/R.

    Tra ve: 'BUY', 'SELL', hoac 'WAIT'.

    """

    def __init__(self):

        self.macro_engine = MacroRegimeEngine()

    def _get_price_position(self, symbol, timeframe=mt5.TIMEFRAME_H1, rates=None):
        """Xac dinh vi tri gia hien tai so voi vung Ho tro / Khang cu xac thuc boi Volume (Volume-Validated Fractals)."""

        if rates is None:
            if mt5.terminal_info() is not None:
                mt5.symbol_select(symbol, True)
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 150)

        if rates is None or len(rates) == 0:

            return None

        from backend.infrastructure.ai_engines.ai.sr_calculator import calculate_sr_levels

        sub_rates = rates[-150:] if len(rates) >= 150 else rates

        sr_info = calculate_sr_levels(sub_rates, zone_threshold=ZONE_THRESHOLD)

        if not sr_info:

            return None

        return {
            "position": sr_info["position"],
            "price": sr_info["current_price"],
            "support": sr_info["support"],
            "resistance": sr_info["resistance"],
            "pct_from_support": sr_info["pct_from_support"],
            "pct_from_resistance": sr_info["pct_from_resistance"],
        }

    def _get_htf_bias(self, symbol, d1_rates=None, h4_rates=None):
        """Xac dinh xu huong dai han bang Price vs EMA 50 + ATR Envelope."""

        # 1. Lay 150 nen de EMA 50 hoi tu tot nhat

        if d1_rates is None:
            if mt5.terminal_info() is not None:
                mt5.symbol_select(symbol, True)
            d1_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 150)

        if h4_rates is None:
            if mt5.terminal_info() is not None:
                mt5.symbol_select(symbol, True)
            h4_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 150)

        # Tinh toan Bias tung khung

        def get_single_tf_bias(rates):
            if rates is None or len(rates) < 15:
                return "NEUTRAL"

            if len(rates) >= 65:
                closes = [r["close"] for r in rates]
                highs = [r["high"] for r in rates]
                lows = [r["low"] for r in rates]
                ema50 = self._ema(closes, 50)
                atr14 = self._atr(highs, lows, closes, 14)
                current_close = closes[-1]
                buffer_zone = 0.5 * atr14
                if current_close > (ema50 + buffer_zone):
                    return "BULLISH"
                elif current_close < (ema50 - buffer_zone):
                    return "BEARISH"
                else:
                    return "NEUTRAL"

            # Adaptive market structure fallback for low candle buffers (15 to 64 bars)
            from backend.core.market_structure import MarketStructureEngine
            struct = MarketStructureEngine.analyze_market_structure(rates, ema_period=min(50, max(5, len(rates) // 2)))
            return "BULLISH" if struct.trend == "BULLISH" else ("BEARISH" if struct.trend == "BEARISH" else "NEUTRAL")

        d1_bias = get_single_tf_bias(d1_rates)

        h4_bias = get_single_tf_bias(h4_rates)

        # 2. Ma tran Dong thuan (MTF Matrix)

        if d1_bias == "BULLISH" and h4_bias == "BULLISH":

            return "BULLISH"

        elif d1_bias == "BEARISH" and h4_bias == "BEARISH":

            return "BEARISH"

        elif d1_bias == "NEUTRAL" or h4_bias == "NEUTRAL":

            return "NEUTRAL"

        else:

            # Trai chieu (VD: D1 TANG nhung H4 GIAM) -> Nhin tu Vi mo, do la Pullback

            # De dam bao logic PULLBACK tuong thich code hien tai (cho phep Buy at Support),

            # ta tra ve NEUTRAL HTF_Bias de combined_bias xu ly linh hoat.

            return "NEUTRAL"

    def _ema(self, data, period):
        """Tinh EMA don gian."""

        if len(data) < period:

            return data[-1]

        multiplier = 2 / (period + 1)

        ema = sum(data[:period]) / period

        for price in data[period:]:

            ema = (price - ema) * multiplier + ema

        return ema

    def _atr(self, highs, lows, closes, period=14):
        """Tinh Average True Range (ATR)."""

        if len(highs) < period + 1:

            return 0

        true_ranges = []

        for i in range(1, len(highs)):

            tr1 = highs[i] - lows[i]

            tr2 = abs(highs[i] - closes[i - 1])

            tr3 = abs(lows[i] - closes[i - 1])

            true_ranges.append(max(tr1, tr2, tr3))

        # SMA of TR for initial ATR

        atr = sum(true_ranges[-period:]) / period

        return atr

    def _get_macro_bias(self, symbol="XAUUSD"):
        """Lấy trạng thái vĩ mô định lượng động từ MacroContextBus."""
        try:
            from backend.core.macro_context_bus import MacroContextBus
            bus = MacroContextBus.get_instance()
            prof = bus.get_profile(symbol)
            return prof.directional_bias
        except Exception:
            try:
                adapter = AssetRegistry.get_adapter(symbol)
                return adapter.get_macro_bias(symbol)
            except Exception as e:
                logger.warning(f"Fallback macro bias for {symbol}: {e}")
                return "NEUTRAL"

    def evaluate(self, symbol, signal_from_strategy, timeframe=None, gate_mode="FULL", rates=None):
        """

        Diem vao chinh: kiem duyet tin hieu tu Strategy.



        Args:

            symbol: Ma giao dich (VD: 'XAUUSD')

            signal_from_strategy: 'BUY' hoac 'SELL' tu ICT Strategy

            timeframe: Khung thoi gian hien tai cua Bot

            gate_mode: Che do bo loc

                - 'FULL'      : Vi mo + HTF + Vi tri gia (Mac dinh)

                - 'TREND'     : Chi Vi mo + HTF (Khong kiem tra vi tri)

                - 'TECHNICAL' : Chi Vi tri gia (Khong quan tam vi mo/HTF)

                - 'FREE'      : Khong bo loc, pass thang tin hieu



        Returns:

            dict: {'decision': 'BUY'/'SELL'/'WAIT', 'reason': '...', ...}

        """

        from backend.infrastructure.brokers.mt5_safe import mt5

        # ======== CHE DO TU DO (FREE) ========

        # Khong co bat ky rang buoc nao, dung cho Stress Test

        if gate_mode == "FREE":

            logger.info(
                f"[DecisionGate] {symbol}: GateMode=FREE -> {signal_from_strategy}"
            )

            return {
                "decision": signal_from_strategy,
                "reason": "Gate Mode: Tu Do - Khong ap dung bo loc.",
                "htf_bias": "N/A",
                "macro_bias": "N/A",
                "combined_bias": "N/A",
                "position": "N/A",
                "price_info": {},
                "trade_mode": "NORMAL",
                "size_multiplier": 1.0,
                "tp_limit_r": 2.5,
                "be_trigger_r": 1.5,
            }

        tf = timeframe if timeframe else mt5.TIMEFRAME_H1

        price_info = self._get_price_position(symbol, timeframe=tf, rates=rates)

        if not price_info:

            return {
                "decision": "WAIT",
                "reason": "Khong lay duoc du lieu gia",
                "trade_mode": "BLOCKED",
                "size_multiplier": 0.0,
                "tp_limit_r": 0.0,
                "be_trigger_r": 0.0,
                "htf_bias": "N/A",
                "macro_bias": "N/A",
                "combined_bias": "N/A",
                "position": "N/A",
                "price_info": {},
            }

        position = price_info["position"]

        # ======== CHE DO KY THUAT (TECHNICAL) ========

        # Chi dua vao Vi tri gia trong kenh Donchian, bo qua Vi mo & HTF

        # Phu hop: Range trading, Sideway market

        if gate_mode == "TECHNICAL":

            decision = "WAIT"

            reason = ""
            trade_mode = "BLOCKED"
            size_multiplier = 0.0
            tp_limit_r = 0.0
            be_trigger_r = 0.0

            if position == "AT_SUPPORT" and signal_from_strategy == "BUY":

                decision = "BUY"
                trade_mode = "NORMAL"
                size_multiplier = 1.0
                tp_limit_r = 2.5
                be_trigger_r = 1.5

                reason = f'[KT] Gia tai Ho tro {price_info["support"]:.2f}. Mua vao bien duoi.'

            elif position == "AT_RESISTANCE" and signal_from_strategy == "SELL":

                decision = "SELL"
                trade_mode = "NORMAL"
                size_multiplier = 1.0
                tp_limit_r = 2.5
                be_trigger_r = 1.5

                reason = f'[KT] Gia tai Khang cu {price_info["resistance"]:.2f}. Ban tai bien tren.'

            elif position == "MIDDLE":

                reason = f'[KT] Gia o giua vung ({price_info["pct_from_support"]}% tu HT). Cho.'

            else:

                reason = f"[KT] Vi tri {position} nhung tin hieu nguoc chieu. Bo qua."

            logger.info(
                f"[DecisionGate] {symbol}: GateMode=TECHNICAL, Pos={position} -> {decision}"
            )

            return {
                "decision": decision,
                "reason": reason,
                "htf_bias": "N/A",
                "macro_bias": "N/A",
                "combined_bias": "N/A",
                "position": position,
                "price_info": price_info,
                "trade_mode": trade_mode,
                "size_multiplier": size_multiplier,
                "tp_limit_r": tp_limit_r,
                "be_trigger_r": be_trigger_r,
            }

        # Lay Bias cho TREND va FULL mode
        htf_bias = self._get_htf_bias(symbol)
        macro_bias = self._get_macro_bias(symbol)

        # Dong thuan giua Macro va HTF

        if macro_bias == htf_bias:

            combined_bias = macro_bias

        elif macro_bias == "NEUTRAL":

            combined_bias = htf_bias

        elif htf_bias == "NEUTRAL":

            combined_bias = macro_bias

        else:

            combined_bias = "NEUTRAL"

        # ======== CHE DO XU HUONG (TREND) ========

        # Xu huong Vi mo + HTF, KHONG xet Vi tri gia

        # Phu hop: Scalping theo xu huong, EMA trong uptrend/downtrend ro rang

        if gate_mode == "TREND":

            decision = "WAIT"

            reason = ""
            trade_mode = "BLOCKED"
            size_multiplier = 0.0
            tp_limit_r = 0.0
            be_trigger_r = 0.0

            if combined_bias == "BULLISH" and signal_from_strategy == "BUY":

                decision = "BUY"
                trade_mode = "NORMAL"
                size_multiplier = 1.0
                tp_limit_r = 2.5
                be_trigger_r = 1.5

                reason = f'[Trend] Xu huong TANG dong thuan. BUY tai {price_info["price"]:.2f}.'

            elif combined_bias == "BEARISH" and signal_from_strategy == "SELL":

                decision = "SELL"
                trade_mode = "NORMAL"
                size_multiplier = 1.0
                tp_limit_r = 2.5
                be_trigger_r = 1.5

                reason = f'[Trend] Xu huong GIAM dong thuan. SELL tai {price_info["price"]:.2f}.'

            elif combined_bias == "NEUTRAL":

                reason = f"[Trend] Xu huong TRUNG TINH. Khong du dieu kien."

            else:

                reason = f"[Trend] Tin hieu nguoc xu huong {combined_bias}. Bo qua."

            logger.info(
                f"[DecisionGate] {symbol}: GateMode=TREND, Combined={combined_bias} -> {decision}"
            )

            return {
                "decision": decision,
                "reason": reason,
                "htf_bias": htf_bias,
                "macro_bias": macro_bias,
                "combined_bias": combined_bias,
                "position": position,
                "price_info": price_info,
                "trade_mode": trade_mode,
                "size_multiplier": size_multiplier,
                "tp_limit_r": tp_limit_r,
                "be_trigger_r": be_trigger_r,
            }

        # ======== CHE DO DAY DU (FULL) — Mac dinh ========

        # Vi mo + HTF + Vi tri gia + Xu ly Xung dot (Scalp Pullback)

        decision = "WAIT"

        reason = ""
        trade_mode = "BLOCKED"
        size_multiplier = 0.0
        tp_limit_r = 0.0
        be_trigger_r = 0.0

        if position == "MIDDLE":

            decision = "WAIT"

            reason = f'Gia o giua vung ({price_info["pct_from_support"]}% tu HT). Khong co loi the vi tri.'

        elif position == "AT_SUPPORT":

            if combined_bias in ["BULLISH", "NEUTRAL"]:

                if signal_from_strategy == "BUY":

                    decision = "BUY"
                    trade_mode = "NORMAL"
                    size_multiplier = 1.0
                    tp_limit_r = 2.5
                    be_trigger_r = 1.5

                    reason = f'Xu huong {combined_bias} + Gia tai Ho tro {price_info["support"]:.2f}. Thuan chieu.'

                else:

                    decision = "WAIT"

                    reason = f"Strategy ra SELL nhung gia dang tai Ho tro va xu huong {combined_bias}. Bo qua."

            elif combined_bias == "BEARISH":

                if signal_from_strategy == "BUY":

                    # SCALP PULLBACK: Bat hoi tai ho tro khi xu huong HTF/Macro giam
                    decision = "BUY"
                    trade_mode = "SCALP_PULLBACK"
                    size_multiplier = 0.5
                    tp_limit_r = 1.5
                    be_trigger_r = 1.0
                    reason = (
                        f'[Scalp Pullback] Strategy BUY bat hoi tai Ho tro {price_info["support"]:.2f} '
                        f'nguoc huong Macro BEARISH. Giam 50% lot, TP 1.5R, BE tai 1.0R.'
                    )

                else:

                    decision = "WAIT"

                    reason = f"Strategy ra SELL ngay tai Ho tro {price_info['support']:.2f}. Cho breakdown xac nhan."

        elif position == "AT_RESISTANCE":

            if combined_bias in ["BEARISH", "NEUTRAL"]:

                if signal_from_strategy == "SELL":

                    decision = "SELL"
                    trade_mode = "NORMAL"
                    size_multiplier = 1.0
                    tp_limit_r = 2.5
                    be_trigger_r = 1.5

                    reason = f'Xu huong {combined_bias} + Gia tai Khang cu {price_info["resistance"]:.2f}. Thuan chieu.'

                else:

                    decision = "WAIT"

                    reason = f"Strategy ra BUY nhung gia dang tai Khang cu va xu huong {combined_bias}. Bo qua."

            elif combined_bias == "BULLISH":

                if signal_from_strategy == "SELL":

                    # SCALP PULLBACK: Danh pullback tai khang cu khi xu huong HTF/Macro tang
                    decision = "SELL"
                    trade_mode = "SCALP_PULLBACK"
                    size_multiplier = 0.5
                    tp_limit_r = 1.5
                    be_trigger_r = 1.0
                    reason = (
                        f'[Scalp Pullback] Strategy SELL dao chieu tai Khang cu {price_info["resistance"]:.2f} '
                        f'nguoc huong Macro BULLISH. Giam 50% lot, TP 1.5R, BE tai 1.0R.'
                    )

                else:

                    decision = "WAIT"

                    reason = f"Strategy ra BUY ngay tai Khang cu {price_info['resistance']:.2f}. Cho breakout xac nhan."

        # Pre-Trade Compliance: Event Risk / News Blackout Gate
        if decision in ["BUY", "SELL"]:
            try:
                from backend.core.macro_context_bus import MacroContextBus
                bus = MacroContextBus.get_instance()
                is_cleared, status_val, news_msg = bus.check_pre_trade_news_compliance(symbol)
                if not is_cleared:
                    logger.info(f"[DecisionGate] {symbol}: Blocked by Pre-Trade News Gate -> {news_msg}")
                    decision = "WAIT"
                    trade_mode = "BLOCKED"
                    size_multiplier = 0.0
                    reason = f"[NewsDefenseGate] {news_msg}"
            except Exception as e:
                logger.warning(f"[DecisionGate] Error checking news compliance: {e}")

        # Kiem tra them quy tac rui ro dac thu cua Lop tai san (Asset-Specific Risk Rules)
        if decision in ["BUY", "SELL"]:
            try:
                adapter = AssetRegistry.get_adapter(symbol)
                context_report = adapter.generate_context_report(symbol)
                try:
                    is_safe, risk_reason = adapter.evaluate_risk_rules(symbol, decision, context_report, trade_mode=trade_mode)
                except TypeError:
                    is_safe, risk_reason = adapter.evaluate_risk_rules(symbol, decision, context_report)
                if not is_safe:
                    logger.info(f"[DecisionGate] {symbol}: Risk Rule Blocked -> {risk_reason}")
                    decision = "WAIT"
                    trade_mode = "BLOCKED"
                    size_multiplier = 0.0
                    reason = f"[AssetRiskGate] {risk_reason}"
            except Exception as e:
                logger.warning(f"[DecisionGate] Error checking asset risk rules: {e}")

        logger.info(
            f"[DecisionGate] {symbol}: GateMode=FULL, Strategy={signal_from_strategy}, "
            f"HTF={htf_bias}, Macro={macro_bias}, Combined={combined_bias}, "
            f"Position={position}, TradeMode={trade_mode} -> {decision}"
        )

        return {
            "decision": decision,
            "reason": reason,
            "htf_bias": htf_bias,
            "macro_bias": macro_bias,
            "combined_bias": combined_bias,
            "position": position,
            "price_info": price_info,
            "trade_mode": trade_mode,
            "size_multiplier": size_multiplier,
            "tp_limit_r": tp_limit_r,
            "be_trigger_r": be_trigger_r,
        }
