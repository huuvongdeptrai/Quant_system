import os
import sys
import json
import re
import time
from pathlib import Path
from typing import Dict, Any, List, Literal
from dotenv import load_dotenv
from loguru import logger
import groq
from pydantic import BaseModel, Field, ValidationError

# Ensure project root (QUANT_AI_WYCKOFF) is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from system.interfaces import IMacroAnalyzer

load_dotenv()

# --- Layer 4: Strict Schema Validation (Data Contract) ---
class MacroResponse(BaseModel):
    bias: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    confidence: float = Field(ge=0.0, le=1.0)
    volatility_risk: Literal["LOW", "MEDIUM", "HIGH"]
    summary: str

class MacroBrain(IMacroAnalyzer):
    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        self.api_key = os.getenv("GROQ_API_KEY", "")
        self.model = model
        self.cache_path = PROJECT_ROOT / "data" / "macro_cache.json"
        
        if not self.api_key:
            logger.warning("GROQ_API_KEY is not set. MacroBrain will return NEUTRAL bias.")
            self.client = None
        else:
            self.client = groq.Groq(api_key=self.api_key)

    def _sanitize_json_string(self, raw_content: str) -> str:
        """
        Layer 2: Regex Sanitization to cut out garbage text from LLM hallucinations.
        """
        match = re.search(r'\{.*\}', raw_content, re.DOTALL)
        if match:
            return match.group(0)
        return raw_content

    def _build_initial_messages(self, symbol: str) -> List[Dict[str, str]]:
        """Build the initial system and user prompts."""
        # TODO: Replace mock data with real fetched macroeconomic indicators
        mock_dxy = 104.50
        mock_yield_10y = 4.25
        mock_sentiment = "Markets are cautious ahead of upcoming NFP data. Geopolitical tensions are slightly elevated."
        
        system_prompt = (
            "You are an elite Institutional Macro Economist and Quant Trader. "
            "Analyze macroeconomic data and provide directional bias and volatility risk. "
            "You must respond ONLY with a valid JSON object matching this schema:\n"
            '{"bias": "BULLISH"|"BEARISH"|"NEUTRAL", "confidence": float 0.0-1.0, "volatility_risk": "LOW"|"MEDIUM"|"HIGH", "summary": "str"}'
        )
        
        user_prompt = f"""
        Asset: {symbol}
        Macro Context:
        - DXY: {mock_dxy}
        - US 10Y Yield: {mock_yield_10y}%
        - Sentiment: {mock_sentiment}
        """
        
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

    def _save_cache(self, result: Dict[str, Any]) -> None:
        """Overwrite the local cache file for the UI to consume."""
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=4)
            logger.info(f"Successfully cached macro bias: {result.get('bias')} ({result.get('confidence')})")
        except Exception as e:
            logger.error(f"Failed to save macro cache: {e}")

    def analyze_macro_bias(self, symbol: str) -> Dict[str, Any]:
        """
        Layer 3: Self-Correction Loop for API calls and JSON validation.
        """
        fallback_result = {
            "bias": "NEUTRAL", 
            "confidence": 0.0, 
            "volatility_risk": "HIGH", 
            "summary": "LLM Hallucination / Auto-Healing Failed"
        }
        
        if not self.client:
            logger.error("Groq client not initialized. Returning fallback result.")
            return fallback_result

        messages = self._build_initial_messages(symbol)
        max_retries = 3

        for attempt in range(1, max_retries + 1):
            raw_content = ""
            try:
                logger.info(f"Requesting Macro Analysis for {symbol} (Attempt {attempt}/{max_retries})...")
                
                # Adding timeout=3.0 to avoid Latency Trap
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.1,
                    max_tokens=200,
                    response_format={"type": "json_object"},
                    timeout=3.0
                )
                
                raw_content = response.choices[0].message.content
                if not raw_content:
                    raise ValueError("Empty response from Groq API.")

                # Layer 2: Sanitize
                clean_json_str = self._sanitize_json_string(raw_content)
                
                # Layer 4: Schema Validation using Pydantic
                json_data = json.loads(clean_json_str)
                validated_data = MacroResponse(**json_data)
                
                # If we reach here, it's perfect.
                result = validated_data.model_dump()
                self._save_cache(result)
                return result
                
            except ValidationError as e:
                logger.warning(f"Pydantic Validation Error on attempt {attempt}: {e}")
                error_msg = f"Your previous response failed schema validation:\n{e}\nPlease correct it and output ONLY valid JSON matching the schema."
                messages.append({"role": "assistant", "content": raw_content})
                messages.append({"role": "user", "content": error_msg})
                
            except json.JSONDecodeError as e:
                logger.warning(f"JSON Decode Error on attempt {attempt}: {e}")
                error_msg = f"Your previous response was not valid JSON:\n{e}\nPlease provide ONLY valid JSON."
                messages.append({"role": "assistant", "content": raw_content})
                messages.append({"role": "user", "content": error_msg})
                
            except Exception as e:
                logger.error(f"Unexpected or Network Error on attempt {attempt}: {e}")
                # API timeouts or connection errors just retry the exact same prompt after a tiny backoff
                time.sleep(1)
                
        # Circuit Breaker: All attempts exhausted
        logger.error("Auto-Healing Loop exhausted. Circuit Breaker triggered.")
        return fallback_result

if __name__ == "__main__":
    logger.info("--- TESTING CORE 2 AUTO-HEALING MACRO BRAIN ---")
    brain = MacroBrain()
    result = brain.analyze_macro_bias("XAUUSD")
    print(f"\nFinal Result:\n{json.dumps(result, indent=4)}")
