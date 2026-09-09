import json
import os
import requests

class AICoreBase:
    def analyze_market(self, prompt: str, context: str) -> str:
        raise NotImplementedError

class GenericOpenAIClient(AICoreBase):
    def __init__(self, base_url, api_key, model_name):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.model_name = model_name

    def analyze_market_stream(self, prompt: str, context: str):
        import time
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": context},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "stream": True
        }
        
        max_retries = 3
        backoff = 2
        for attempt in range(max_retries):
            try:
                with requests.post(url, headers=headers, json=payload, stream=True, timeout=10) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if line:
                            line_decoded = line.decode('utf-8')
                            if line_decoded.startswith('data: '):
                                data_str = line_decoded[6:]
                                if data_str == '[DONE]':
                                    break
                                try:
                                    import json
                                    chunk = json.loads(data_str)
                                    delta = chunk['choices'][0]['delta']
                                    if 'content' in delta:
                                        yield delta['content']
                                except Exception:
                                    pass
                return # Thành công, thoát vòng lặp
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    yield f"\nLỖI AI SAU {max_retries} LẦN THỬ: {str(e)}"

class AIFactory:
    def __init__(self, config_path=None):
        if config_path is None:
            self.config_path = os.path.join(os.path.dirname(__file__), "ai_config.json")
        else:
            self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self):
        if not os.path.exists(self.config_path):
            return {}
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_model_names(self):
        return list(self.config.keys())

    def create_client(self, model_name: str) -> AICoreBase:
        if model_name not in self.config:
            raise ValueError(f"Model {model_name} chưa được cấu hình.")
        
        cfg = self.config[model_name]
        # Hiện tại đa số các hãng (Groq, LMStudio, Ollama, OpenAI) đều dùng chung chuẩn API của OpenAI
        if cfg["type"] == "openai_compatible":
            return GenericOpenAIClient(cfg["base_url"], cfg["api_key"], cfg["default_model"])
        else:
            raise ValueError(f"Loại AI {cfg['type']} chưa được hỗ trợ.")
