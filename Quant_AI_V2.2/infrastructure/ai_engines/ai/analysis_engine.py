import os

import json

from datetime import datetime

from core.event_bus import event_bus

import time

from infrastructure.brokers.mt5_safe import mt5

from openai import OpenAI

from infrastructure.data_providers.macro.macro_regime import MacroRegimeEngine

from loguru import logger

env_path = r"C:\Users\vong2\OneDrive\Tài liệu\Quant_System\Quant_AI_V2.2\.env"

if not os.path.exists(env_path):

    env_path = (
        r"C:\Users\vong2\OneDrive\Tài liệu\Quant_System\Quant_AI_V2.2\config\.env"
    )

if os.path.exists(env_path):

    with open(env_path, "r", encoding="utf-8") as f:

        for line in f:

            if line.strip().startswith("GEMINI_API_KEY"):

                os.environ["GEMINI_API_KEY"] = (
                    line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                )


# Cache module-level: ton tai xuyen suot app, khong bi mat khi tao instance moi

_global_cache = {}


class AnalysisEngine:

    def __init__(self, model_name="qwen2.5"):

        self.model_name = model_name

        self.macro_engine = MacroRegimeEngine()

        self.cache = _global_cache

        gemini_key = os.environ.get("GEMINI_API_KEY")

        if "gemini" in self.model_name.lower() and gemini_key:

            logger.info(f"Using GEMINI Cloud API for {self.model_name}")

            self.client = OpenAI(
                api_key=gemini_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            )

        else:

            logger.info(f"Using LOCAL OLLAMA API for {self.model_name}")

            self.client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

    def _get_current_session(self):

        import datetime

        now_utc = datetime.datetime.utcnow().hour

        if 7 <= now_utc < 13:

            return "Phiên Âu (London)"

        elif 13 <= now_utc < 22:

            return "Phiên Mỹ (New York)"

        else:

            return "Phiên Á (Asian)"

    def _get_technicals(self, symbol, timeframe=mt5.TIMEFRAME_H1):

        if mt5.terminal_info() is None:

            return None

        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 150)

        if rates is None or len(rates) < 50:

            return None

        current_price = rates[-1]["close"]

        # 1. Tinh EMA 50

        closes = [r["close"] for r in rates]

        period = 50

        alpha = 2 / (period + 1)

        ema = sum(closes[:period]) / period

        for price in closes[period:]:

            ema = (price - ema) * alpha + ema

        ema_position = (
            "TRÊN EMA 50 (Phe Mua nắm quyền)"
            if current_price > ema
            else "DƯỚI EMA 50 (Phe Bán nắm quyền)"
        )

        # 2. Thuat toan Fractal N=2 ket hop Bo loc Volume (Volume-Validated Fractals - Wyckoff Stopping/Climax Volume)

        from infrastructure.ai_engines.ai.sr_calculator import calculate_sr_levels

        sub_rates = rates[-150:] if len(rates) >= 150 else rates

        sr_info = calculate_sr_levels(sub_rates, current_price=current_price)

        if sr_info:

            resistance = sr_info["resistance"]

            support = sr_info["support"]

        else:

            resistance = max([r["high"] for r in rates[-50:]])

            support = min([r["low"] for r in rates[-50:]])

        # Lay danh sach swing highs / lows cho cau truc thi truong

        swing_highs = []

        swing_lows = []

        for i in range(2, len(rates) - 2):

            high = rates[i]["high"]

            low = rates[i]["low"]

            if (
                high > rates[i - 1]["high"]
                and high > rates[i - 2]["high"]
                and high > rates[i + 1]["high"]
                and high > rates[i + 2]["high"]
            ):

                swing_highs.append(high)

            if (
                low < rates[i - 1]["low"]
                and low < rates[i - 2]["low"]
                and low < rates[i + 1]["low"]
                and low < rates[i + 2]["low"]
            ):

                swing_lows.append(low)

        # 3. Cau truc thi truong & Xu huong Ngan han (Toan hoc tat dinh - Pure Python Math)

        structure = "Đi ngang (Sideways)"

        math_trend = "Đi ngang"

        last_shs = swing_highs[-2:] if len(swing_highs) >= 2 else []

        last_sls = swing_lows[-2:] if len(swing_lows) >= 2 else []

        if len(last_shs) == 2 and len(last_sls) == 2:

            if last_shs[1] > last_shs[0] and last_sls[1] > last_sls[0]:

                structure = "Tăng (Higher Highs, Higher Lows)"

                if current_price > ema:

                    math_trend = "Tăng"

            elif last_shs[1] < last_shs[0] and last_sls[1] < last_sls[0]:

                structure = "Giảm (Lower Highs, Lower Lows)"

                if current_price < ema:

                    math_trend = "Giảm"

            elif last_shs[1] < last_shs[0] and last_sls[1] > last_sls[0]:

                structure = "Thu hẹp (Convergence/Triangle)"

            else:

                structure = "Mở rộng (Expansion/Megaphone)"

        elif current_price > (ema * 1.002):

            math_trend = "Tăng"

        elif current_price < (ema * 0.998):

            math_trend = "Giảm"

        return {
            "current_price": current_price,
            "resistance": resistance,
            "support": support,
            "ema_50": round(ema, 2),
            "ema_position": ema_position,
            "structure": structure,
            "math_trend": math_trend,
            "vol_confirmed": (
                bool(sr_info.get("vol_confirmed", False)) if sr_info else False
            ),
            "session": self._get_current_session(),
        }

    def _build_prompt(self, symbol, macro_data, tech_data):

        us10y_val = macro_data.get("Monetary", {}).get("us10y", 0)

        us10y_str = f"{us10y_val:.2f}%" if us10y_val else "N/A"

        prompt = f"""Bạn là một Quant Analyst chuyên nghiệp.

Hãy phân tích mã {symbol} dựa trên các dữ liệu sau và trả về DUY NHẤT 1 object JSON (không có markdown hay text nào khác). VIẾT CÓ DẤU TIẾNG VIỆT.



[TRẠNG THÁI VĨ MÔ (TradingView & Yahoo Finance)]

- Thị trường (VIX & DXY): {macro_data['Market']['state']} - {macro_data['Market']['reason']}

- Tiền tệ & Lợi suất (US10Y): {macro_data['Monetary']['state']} - {macro_data['Monetary']['reason']} (US10Y Yield: {us10y_str})

- Kinh tế: {macro_data['Economic']['state']} - {macro_data['Economic']['reason']}



[TIN TỨC KHẨN CẤP (Telegram)]

- {macro_data.get('Telegram_News', 'Không có tin tức')}



[KỸ THUẬT VÀ HÀNH ĐỘNG GIÁ - H1]

- Phiên giao dịch hiện tại: {tech_data.get('session', 'Phiên Á')}

- Giá hiện tại: {tech_data['current_price']}

- Trục xu hướng (EMA 50): {tech_data.get('ema_50', 0)} ({tech_data.get('ema_position', '')})

- Cấu trúc thị trường: {tech_data.get('structure', '')}

- Xu hướng kỹ thuật H1 (Thuần Toán): {tech_data.get('math_trend', 'Đi ngang')}

- Kháng cự Cấu trúc (Volume-Validated): {tech_data['resistance']}

- Hỗ trợ Cấu trúc (Volume-Validated): {tech_data['support']}



[YÊU CẦU OUTPUT JSON]

{{

  "trend_macro": "Tăng / Giảm / Đi ngang",

  "trend_intraday": "{tech_data.get('math_trend', 'Đi ngang')}",

  "scenario_a": "Kịch bản chính bám sát xu hướng...",

  "scenario_b": "Kịch bản phụ phòng ngừa đảo chiều..."

}}"""

        return prompt

    def analyze(self, symbol, force_refresh=False, tech_data=None):

        if not tech_data:

            tech_data = self._get_technicals(symbol)

        if not tech_data:

            return {"error": "Không lấy được dữ liệu MT5"}

        current_price = tech_data["current_price"]

        if not force_refresh and symbol in self.cache:

            cached = self.cache[symbol]

            if cached["support"] <= current_price <= cached["resistance"]:

                logger.info(f"[{symbol}] Cache hit")

                return cached["result"]

            else:

                logger.info(f"[{symbol}] S/R breakout -> re-analyze")

                event_bus.log_event.emit(
                    datetime.now().strftime("%H:%M:%S"),
                    "INFO",
                    f"Breakout S/R! Kích hoạt AI phân tích lại Vĩ mô {symbol}...",
                    "#E3A536",
                )

        if symbol not in self.cache:

            event_bus.log_event.emit(
                datetime.now().strftime("%H:%M:%S"),
                "INFO",
                f"Đang gọi Local AI quét Vĩ mô H1 cho {symbol}...",
                "#8B949E",
            )

        macro_data = self.macro_engine.generate_macro_report()

        prompt = self._build_prompt(symbol, macro_data, tech_data)

        schema = {
            "type": "json_schema",
            "json_schema": {
                "name": "market_analysis",
                "schema": {
                    "type": "object",
                    "properties": {
                        "trend_macro": {
                            "type": "string",
                            "enum": ["Tăng", "Giảm", "Đi ngang"],
                        },
                        "trend_intraday": {
                            "type": "string",
                            "enum": ["Tăng", "Giảm", "Đi ngang"],
                        },
                        "scenario_a": {"type": "string"},
                        "scenario_b": {"type": "string"},
                    },
                    "required": [
                        "trend_macro",
                        "trend_intraday",
                        "scenario_a",
                        "scenario_b",
                    ],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }

        try:

            logger.info(
                f"[{symbol}] Calling {self.model_name} with Structured Outputs..."
            )

            # logger.debug(prompt) - silenced prompt from console

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                response_format=schema,
            )

            result_text = response.choices[0].message.content

            if result_text.startswith("```json"):

                result_text = (
                    result_text.replace("```json", "").replace("```", "").strip()
                )

            elif result_text.startswith("```"):

                result_text = result_text.replace("```", "").strip()

            result_json = json.loads(result_text)

            self.cache[symbol] = {
                "timestamp": time.time(),
                "result": result_json,
                "resistance": tech_data["resistance"],
                "support": tech_data["support"],
            }

            return result_json

        except Exception as e:

            logger.error(f"AI API Error: {e}")

            return {"error": f"Lỗi AI: {e}"}
