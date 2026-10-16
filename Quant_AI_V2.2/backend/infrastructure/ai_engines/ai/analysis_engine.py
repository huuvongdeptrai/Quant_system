import os

import json

from datetime import datetime

from backend.core.event_bus import event_bus

import time

from backend.infrastructure.brokers.mt5_safe import mt5

from openai import OpenAI

from backend.infrastructure.data_providers.macro.macro_regime import MacroRegimeEngine
from backend.infrastructure.data_providers.asset_registry import AssetRegistry

from loguru import logger

# Load GEMINI_API_KEY from .env if present
_current_file_dir = os.path.dirname(os.path.abspath(__file__))
for _candidate in [
    os.path.join(os.getcwd(), ".env"),
    os.path.join(os.getcwd(), "config", ".env"),
    os.path.join(_current_file_dir, "..", "..", "..", "..", ".env"),
    os.path.join(_current_file_dir, "..", "..", "..", "..", "config", ".env"),
]:
    _abs_cand = os.path.abspath(_candidate)
    if os.path.exists(_abs_cand):
        try:
            with open(_abs_cand, "r", encoding="utf-8") as _f:
                for _line in _f:
                    if _line.strip().startswith("GEMINI_API_KEY"):
                        os.environ["GEMINI_API_KEY"] = (
                            _line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                        )
                        break
        except Exception:
            pass
        if "GEMINI_API_KEY" in os.environ:
            break


# Cache module-level: ton tai xuyen suot app, khong bi mat khi tao instance moi

_global_cache = {}


class AnalysisEngine:
    _warned_ollama_offline = False

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
                timeout=8.0,
            )
        else:
            logger.info(f"Using LOCAL OLLAMA API for {self.model_name}")
            self.client = OpenAI(
                base_url="http://localhost:11434/v1",
                api_key="ollama",
                timeout=120.0,
            )

    def _get_current_session(self):

        import datetime

        now_utc = datetime.datetime.utcnow().hour

        if 7 <= now_utc < 13:
            return "London Session"
        elif 13 <= now_utc < 22:
            return "New York Session"
        else:
            return "Asian Session"

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
            "ABOVE EMA 50 (Buyers in control)"
            if current_price > ema
            else "BELOW EMA 50 (Sellers in control)"
        )

        # 2. Thuat toan Fractal N=2 ket hop Bo loc Volume (Volume-Validated Fractals - Wyckoff Stopping/Climax Volume)

        from backend.infrastructure.ai_engines.ai.sr_calculator import calculate_sr_levels

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

        structure = "Sideways"

        math_trend = "Sideways"

        last_shs = swing_highs[-2:] if len(swing_highs) >= 2 else []

        last_sls = swing_lows[-2:] if len(swing_lows) >= 2 else []

        if len(last_shs) == 2 and len(last_sls) == 2:

            if last_shs[1] > last_shs[0] and last_sls[1] > last_sls[0]:

                structure = "Bullish (Higher Highs, Higher Lows)"

                if current_price > ema:

                    math_trend = "Bullish"

            elif last_shs[1] < last_shs[0] and last_sls[1] < last_sls[0]:

                structure = "Bearish (Lower Highs, Lower Lows)"

                if current_price < ema:

                    math_trend = "Bearish"

            elif last_shs[1] < last_shs[0] and last_sls[1] > last_sls[0]:

                structure = "Contraction (Convergence / Triangle)"

            else:

                structure = "Expansion (Megaphone)"

        elif current_price > (ema * 1.002):

            math_trend = "Bullish"

        elif current_price < (ema * 0.998):

            math_trend = "Bearish"

        # 4. Trích xuất đặc trưng Vi cấu trúc & Dòng lệnh (Microstructure & Order Flow)
        micro_data = {}
        try:
            from backend.core.preprocessor import DataPreprocessor
            prep_res = DataPreprocessor().process_technical_data(rates)
            if prep_res:
                micro_data = {
                    "vwap": prep_res.get("vwap", 0.0),
                    "vwap_regime": prep_res.get("vwap_regime", "FAIR_VALUE_INTRADAY"),
                    "vwap_z_score": prep_res.get("vwap_z_score", 0.0),
                    "poc": prep_res.get("poc", 0.0),
                    "vah": prep_res.get("vah", 0.0),
                    "val": prep_res.get("val", 0.0),
                    "dist_to_poc_pct": prep_res.get("dist_to_poc_pct", 0.0),
                    "garman_klass_vol": prep_res.get("garman_klass_vol", 0.0),
                    "cvd_pressure": prep_res.get("cvd_pressure", "BALANCED_ORDER_FLOW"),
                    "cvd_pressure_ratio": prep_res.get("cvd_pressure_ratio", 0.0),
                    "microstructure_summary": prep_res.get("microstructure_summary", ""),
                }
        except Exception:
            pass

        res_dict = {
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
        res_dict.update(micro_data)
        return res_dict

    def _build_prompt(self, symbol, macro_data, tech_data, adapter=None):
        if adapter:
            macro_section = adapter.build_prompt_section(symbol, macro_data)
        else:
            us10y_val = macro_data.get("Monetary", {}).get("us10y", 0)
            us10y_str = f"{us10y_val:.2f}%" if us10y_val else "N/A"
            macro_section = f"""[MACRO CONTEXT (TradingView & Yahoo Finance)]
- Market Regime (VIX & DXY): {macro_data.get('Market', {}).get('state', '')} - {macro_data.get('Market', {}).get('reason', '')}
- Monetary Policy & Yields (US10Y): {macro_data.get('Monetary', {}).get('state', '')} - {macro_data.get('Monetary', {}).get('reason', '')} (US10Y Yield: {us10y_str})
- Economic Landscape: {macro_data.get('Economic', {}).get('state', '')} - {macro_data.get('Economic', {}).get('reason', '')}
- Breaking Catalysts: {macro_data.get('Telegram_News', 'No breaking catalysts')}"""

        prompt = f"""You are an institutional Quantitative Portfolio Analyst & Risk Strategist.
Analyze {symbol} based on the following intermarket and price action inputs. Return EXACTLY 1 valid JSON object (no markdown, no preamble). ALL OUTPUT MUST BE IN PROFESSIONAL ENGLISH.

{macro_section}

[H1 TECHNICALS & PRICE ACTION]
- Active Trading Session: {tech_data.get('session', 'London')}
- Current Market Price: {tech_data['current_price']}
- Trend Anchor (EMA 50): {tech_data.get('ema_50', 0)} ({tech_data.get('ema_position', '')})
- Market Structure: {tech_data.get('structure', '')}
- Mathematical Intraday Trend: {tech_data.get('math_trend', 'SIDEWAYS')}
- Key Structural Resistance (Volume-Validated): {tech_data['resistance']}
- Key Structural Support (Volume-Validated): {tech_data['support']}
- Institutional Microstructure & Order Flow:
  * Session VWAP: {tech_data.get('vwap', 'N/A')} ({tech_data.get('vwap_regime', 'Fair Value')}, Z: {tech_data.get('vwap_z_score', 0):+.2f}σ)
  * Point of Control (POC): {tech_data.get('poc', 'N/A')} (Dist: {tech_data.get('dist_to_poc_pct', 0):+.2f}%, Value Area: [{tech_data.get('val', 0)} - {tech_data.get('vah', 0)}])
  * Garman-Klass Realized Volatility: {tech_data.get('garman_klass_vol', 0):.2f}%
  * Order Flow Imbalance (CVD Proxy): {tech_data.get('cvd_pressure', 'BALANCED_ORDER_FLOW')} (Ratio: {tech_data.get('cvd_pressure_ratio', 0):+.2f})

[REQUIRED JSON OUTPUT SCHEMA]
{{
  "trend_macro": "BULLISH / BEARISH / SIDEWAYS",
  "trend_intraday": "{tech_data.get('math_trend', 'Sideways')}",
  "scenario_a": "Primary institutional trade scenario...",
  "scenario_b": "Contingency / invalidation scenario..."
}}"""
        return prompt

    def analyze(self, symbol, force_refresh=False, tech_data=None):

        if not tech_data:

            tech_data = self._get_technicals(symbol)

        if not tech_data:

            return {"error": "Failed to fetch MT5 market data"}

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
                    f"Breakout S/R! Triggering AI Macro re-evaluation for {symbol}...",
                    "#E3A536",
                )

        if symbol not in self.cache:
            event_bus.log_event.emit(
                datetime.now().strftime("%H:%M:%S"),
                "INFO",
                f"Invoking Local AI to evaluate Multi-Asset Context on H1 for {symbol}...",
                "#8B949E",
            )

        adapter = AssetRegistry.get_adapter(symbol)
        macro_data = adapter.generate_context_report(symbol)
        prompt = self._build_prompt(symbol, macro_data, tech_data, adapter=adapter)

        schema = {
            "type": "json_schema",
            "json_schema": {
                "name": "market_analysis",
                "schema": {
                    "type": "object",
                    "properties": {
                        "trend_macro": {
                            "type": "string",
                            "enum": ["BULLISH", "BEARISH", "SIDEWAYS"],
                        },
                        "trend_intraday": {
                            "type": "string",
                            "enum": ["BULLISH", "BEARISH", "SIDEWAYS"],
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

        # Quick socket check for local Ollama to avoid 15s freeze when Ollama is offline
        if "gemini" not in self.model_name.lower():
            import socket
            try:
                with socket.create_connection(("127.0.0.1", 11434), timeout=0.3):
                    AnalysisEngine._warned_ollama_offline = False
            except Exception:
                if not getattr(AnalysisEngine, "_warned_ollama_offline", False):
                    logger.warning("AI Service Offline (Ollama not running at localhost:11434). Local quantitative model fallback active.")
                    AnalysisEngine._warned_ollama_offline = True
                else:
                    logger.debug("AI Service Offline (Ollama not running at localhost:11434)")
                return {"error": "Ollama offline (localhost:11434)"}

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

            # Record inference dataset for LoRA fine-tuning
            try:
                from backend.infrastructure.ai_engines.dataset_recorder import dataset_recorder
                sample_id = dataset_recorder.record_inference(
                    symbol=symbol,
                    prompt=prompt,
                    ai_response=result_json,
                    metadata={"model": self.model_name, "session": tech_data.get("session", "N/A")}
                )
                result_json["_sample_id"] = sample_id
            except Exception as rec_ex:
                logger.debug(f"Dataset recording bypassed: {rec_ex}")

            self.cache[symbol] = {
                "timestamp": time.time(),
                "result": result_json,
                "resistance": tech_data["resistance"],
                "support": tech_data["support"],
            }

            return result_json

        except Exception as e:
            err_msg = str(e)
            if "Connection error" in err_msg or "ConnectError" in err_msg or "connection error" in err_msg.lower():
                logger.warning(f"AI Service Offline (Ollama not running at localhost:11434): {e}")
                return {"error": "Ollama offline (localhost:11434)"}
            elif "timed out" in err_msg.lower() or "timeout" in err_msg.lower():
                logger.warning(f"AI Service Timeout: Model {self.model_name} response exceeded 30s: {e}")
                return {"error": f"AI response timeout (> 30s). Please retry or select a lighter model."}
            logger.error(f"AI API Error: {e}")
            return {"error": f"AI Inference Error: {e}"}
