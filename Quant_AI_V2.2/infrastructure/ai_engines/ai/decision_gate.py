from infrastructure.brokers.mt5_safe import mt5
from infrastructure.data_providers.macro.macro_regime import MacroRegimeEngine
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
        """Xac dinh vi tri gia hien tai so voi vung Ho tro / Khang cu."""
        if rates is None:
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 100)
        if rates is None or len(rates) == 0:
            return None

        price = rates[-1]['close']
        highs = [r['high'] for r in rates[-50:]]
        lows = [r['low'] for r in rates[-50:]]
        resistance = max(highs)
        support = min(lows)
        total_range = resistance - support

        if total_range <= 0:
            return {'position': 'MIDDLE', 'price': price, 'support': support, 'resistance': resistance}

        dist_to_support = (price - support) / total_range
        dist_to_resistance = (resistance - price) / total_range

        if dist_to_support <= ZONE_THRESHOLD:
            position = 'AT_SUPPORT'
        elif dist_to_resistance <= ZONE_THRESHOLD:
            position = 'AT_RESISTANCE'
        else:
            position = 'MIDDLE'

        return {
            'position': position,
            'price': price,
            'support': support,
            'resistance': resistance,
            'pct_from_support': round(dist_to_support * 100, 1),
            'pct_from_resistance': round(dist_to_resistance * 100, 1)
        }

    def _get_htf_bias(self, symbol, d1_rates=None, h4_rates=None):
        """Xac dinh xu huong dai han bang EMA tren D1 va H4."""
        if d1_rates is None: d1_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 60)
        if h4_rates is None: h4_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 60)

        d1_bias = 'NEUTRAL'
        h4_bias = 'NEUTRAL'

        if d1_rates is not None and len(d1_rates) >= 50:
            closes = [r['close'] for r in d1_rates]
            ema20 = self._ema(closes, 20)
            ema50 = self._ema(closes, 50)
            if ema20 > ema50:
                d1_bias = 'BULLISH'
            elif ema20 < ema50:
                d1_bias = 'BEARISH'

        if h4_rates is not None and len(h4_rates) >= 50:
            closes = [r['close'] for r in h4_rates]
            ema20 = self._ema(closes, 20)
            ema50 = self._ema(closes, 50)
            if ema20 > ema50:
                h4_bias = 'BULLISH'
            elif ema20 < ema50:
                h4_bias = 'BEARISH'

        # Dong thuan: ca D1 va H4 cung huong moi tinh la ro xu huong
        if d1_bias == 'BULLISH' and h4_bias == 'BULLISH':
            return 'BULLISH'
        elif d1_bias == 'BEARISH' and h4_bias == 'BEARISH':
            return 'BEARISH'
        else:
            return 'NEUTRAL'

    def _ema(self, data, period):
        """Tinh EMA don gian."""
        if len(data) < period:
            return data[-1]
        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period
        for price in data[period:]:
            ema = (price - ema) * multiplier + ema
        return ema

    def _get_macro_bias(self):
        """Lay trang thai vi mo va chuyen thanh BULLISH/BEARISH/NEUTRAL cho Vang."""
        report = self.macro_engine.generate_macro_report()

        market = report['Market']
        monetary = report['Monetary']

        # Logic cho XAUUSD:
        # DXY giam + Risk-Off = Vang tang
        # DXY tang + Hawkish = Vang giam
        score = 0

        if market['dxy_trend'] == 'DOWN':
            score += 1  # USD yeu -> Vang tang
        elif market['dxy_trend'] == 'UP':
            score -= 1  # USD manh -> Vang giam

        if market['state'] == 'Risk-Off':
            score += 1  # Tru an -> Vang tang

        if 'Hawkish' in monetary['state']:
            score -= 1  # Lai suat tang -> Vang giam
        elif 'Dovish' in monetary['state']:
            score += 1  # Lai suat giam -> Vang tang

        if score >= 1:
            return 'BULLISH'
        elif score <= -1:
            return 'BEARISH'
        return 'NEUTRAL'

    def evaluate(self, symbol, signal_from_strategy):
        """
        Diem vao chinh: kiem duyet tin hieu tu Strategy.

        Args:
            symbol: Ma giao dich (VD: 'XAUUSD')
            signal_from_strategy: 'BUY' hoac 'SELL' tu ICT Strategy

        Returns:
            dict: {'decision': 'BUY'/'SELL'/'WAIT', 'reason': '...'}
        """
        price_info = self._get_price_position(symbol)
        if not price_info:
            return {'decision': 'WAIT', 'reason': 'Khong lay duoc du lieu gia'}

        htf_bias = self._get_htf_bias(symbol)
        macro_bias = self._get_macro_bias()
        position = price_info['position']

        # Dong thuan giua Macro va HTF
        if macro_bias == htf_bias:
            combined_bias = macro_bias
        elif macro_bias == 'NEUTRAL':
            combined_bias = htf_bias
        elif htf_bias == 'NEUTRAL':
            combined_bias = macro_bias
        else:
            combined_bias = 'NEUTRAL'  # Xung dot -> khong ro xu huong

        # ======== MA TRAN QUYET DINH ========
        # Xu huong Tang + Gia tai Ho tro   -> CHO BUY
        # Xu huong Tang + Gia tai Khang cu -> CHO (doi breakout hoac pullback)
        # Xu huong Giam + Gia tai Khang cu -> CHO SELL
        # Xu huong Giam + Gia tai Ho tro   -> CHO (doi breakdown hoac bounce)
        # Xu huong Ngang + Gia tai Ho tro  -> CHO BUY (trade bien duoi)
        # Xu huong Ngang + Gia tai Khang cu-> CHO SELL (trade bien tren)
        # Gia o giua vung                  -> CHO (khong co loi the vi tri)

        decision = 'WAIT'
        reason = ''

        if position == 'MIDDLE':
            decision = 'WAIT'
            reason = f'Gia o giua vung ({price_info["pct_from_support"]}% tu HT). Khong co loi the vi tri.'

        elif position == 'AT_SUPPORT':
            if combined_bias in ['BULLISH', 'NEUTRAL']:
                if signal_from_strategy == 'BUY':
                    decision = 'BUY'
                    reason = f'Xu huong {combined_bias} + Gia tai Ho tro {price_info["support"]:.2f}. Thuan chieu.'
                else:
                    decision = 'WAIT'
                    reason = f'Strategy ra SELL nhung gia dang tai Ho tro va xu huong {combined_bias}. Bo qua.'
            elif combined_bias == 'BEARISH':
                decision = 'WAIT'
                reason = f'Xu huong BEARISH nhung gia tai Ho tro. Chua ro breakdown hay bounce.'

        elif position == 'AT_RESISTANCE':
            if combined_bias in ['BEARISH', 'NEUTRAL']:
                if signal_from_strategy == 'SELL':
                    decision = 'SELL'
                    reason = f'Xu huong {combined_bias} + Gia tai Khang cu {price_info["resistance"]:.2f}. Thuan chieu.'
                else:
                    decision = 'WAIT'
                    reason = f'Strategy ra BUY nhung gia dang tai Khang cu va xu huong {combined_bias}. Bo qua.'
            elif combined_bias == 'BULLISH':
                decision = 'WAIT'
                reason = f'Xu huong BULLISH nhung gia tai Khang cu. Chua ro breakout hay rejection.'

        logger.info(
            f'[DecisionGate] {symbol}: Strategy={signal_from_strategy}, '
            f'HTF={htf_bias}, Macro={macro_bias}, Combined={combined_bias}, '
            f'Position={position} -> {decision}'
        )

        return {
            'decision': decision,
            'reason': reason,
            'htf_bias': htf_bias,
            'macro_bias': macro_bias,
            'combined_bias': combined_bias,
            'position': position,
            'price_info': price_info
        }
