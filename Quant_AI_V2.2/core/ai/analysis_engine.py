import os
import json
import time
import MetaTrader5 as mt5
from openai import OpenAI
from core.macro.macro_regime import MacroRegimeEngine
from loguru import logger

env_path = r'C:\Users\vong2\OneDrive\Tài liệu\Quant_System\Quant_AI_V2.2\.env'
if not os.path.exists(env_path):
    env_path = r'C:\Users\vong2\OneDrive\Tài liệu\Quant_System\Quant_AI_V2.2\config\.env'
if os.path.exists(env_path):
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip().startswith('GEMINI_API_KEY'):
                os.environ['GEMINI_API_KEY'] = line.strip().split('=', 1)[1].strip().strip('"').strip("'")

# Cache module-level: ton tai xuyen suot app, khong bi mat khi tao instance moi
_global_cache = {}

class AnalysisEngine:
    def __init__(self, model_name='qwen2.5'):
        self.model_name = model_name
        self.macro_engine = MacroRegimeEngine()
        self.cache = _global_cache

        gemini_key = os.environ.get('GEMINI_API_KEY')

        if 'gemini' in self.model_name.lower() and gemini_key:
            logger.info(f'Using GEMINI Cloud API for {self.model_name}')
            self.client = OpenAI(
                api_key=gemini_key,
                base_url='https://generativelanguage.googleapis.com/v1beta/openai/'
            )
        else:
            logger.info(f'Using LOCAL OLLAMA API for {self.model_name}')
            self.client = OpenAI(
                base_url='http://localhost:11434/v1',
                api_key='ollama'
            )

    def _get_technicals(self, symbol, timeframe=mt5.TIMEFRAME_H1):
        if mt5.terminal_info() is None:
            return None

        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 100)
        if rates is None or len(rates) == 0:
            return None

        current_price = rates[-1]['close']
        recent_highs = [r['high'] for r in rates[-50:]]
        recent_lows = [r['low'] for r in rates[-50:]]
        resistance = max(recent_highs)
        support = min(recent_lows)

        return {
            'current_price': current_price,
            'resistance': resistance,
            'support': support
        }

    def _build_prompt(self, symbol, macro_data, tech_data):
        prompt = (
            "Bạn là một Quant Analyst chuyên nghiệp.\n"
            "Hãy phân tích mã {sym} dựa trên các dữ liệu sau "
            "và trả về DUY NHẤT 1 object JSON "
            "(không có markdown hay text nào khác). "
            "VIẾT CÓ DẤU TIẾNG VIỆT.\n\n"
            "[TRẠNG THÁI VĨ MÔ]\n"
            "- Thị trường: {mkt_state} - {mkt_reason}\n"
            "- Tiền tệ: {mon_state} - {mon_reason}\n"
            "- Kinh tế: {eco_state} - {eco_reason}\n\n"
            "[KỸ THUẬT - H1]\n"
            "- Giá hiện tại: {price}\n"
            "- Kháng cự: {res}\n"
            "- Hỗ trợ: {sup}\n\n"
            "[YÊU CẦU OUTPUT JSON]\n"
            '{{"trend_macro": "Tăng / Giảm / Đi ngang",'
            ' "trend_intraday": "Tăng / Giảm / Đi ngang",'
            ' "scenario_a": "Kịch bản chính...",'
            ' "scenario_b": "Kịch bản phụ..."}}'
        )
        return prompt.format(
            sym=symbol,
            mkt_state=macro_data['Market']['state'],
            mkt_reason=macro_data['Market']['reason'],
            mon_state=macro_data['Monetary']['state'],
            mon_reason=macro_data['Monetary']['reason'],
            eco_state=macro_data['Economic']['state'],
            eco_reason=macro_data['Economic']['reason'],
            price=tech_data['current_price'],
            res=tech_data['resistance'],
            sup=tech_data['support']
        )

    def analyze(self, symbol, force_refresh=False, tech_data=None):
        if not tech_data:
            tech_data = self._get_technicals(symbol)
        if not tech_data:
            return {'error': 'Không lấy được dữ liệu MT5'}

        current_price = tech_data['current_price']

        if not force_refresh and symbol in self.cache:
            cached = self.cache[symbol]
            if cached['support'] <= current_price <= cached['resistance']:
                logger.info(f'[{symbol}] Cache hit')
                return cached['result']
            else:
                logger.info(f'[{symbol}] S/R breakout -> re-analyze')

        macro_data = self.macro_engine.generate_macro_report()
        prompt = self._build_prompt(symbol, macro_data, tech_data)

        try:
            logger.info(f'[{symbol}] Calling {self.model_name}...')

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{'role': 'user', 'content': prompt}],
                temperature=0.0,
                response_format={'type': 'json_object'}
            )

            result_text = response.choices[0].message.content

            if result_text.startswith('```json'):
                result_text = result_text.replace('```json', '').replace('```', '').strip()
            elif result_text.startswith('```'):
                result_text = result_text.replace('```', '').strip()

            result_json = json.loads(result_text)

            self.cache[symbol] = {
                'timestamp': time.time(),
                'result': result_json,
                'resistance': tech_data['resistance'],
                'support': tech_data['support']
            }

            return result_json

        except Exception as e:
            logger.error(f'AI API Error: {e}')
            return {'error': f'Lỗi AI: {e}'}
