"""
LLM Client – гибкий клиент для локального llama_cpp или удалённого DeepSeek API.
"""
import os
import json
import requests
from typing import Optional, Dict, Any
from loguru import logger

# Попробуем импортировать llama_cpp; если нет – будем использовать только API
try:
    from llama_cpp import Llama
    LLAMA_AVAILABLE = True
except ImportError:
    Llama = None
    LLAMA_AVAILABLE = False


class LLMClient:
    def __init__(self, model_name: Optional[str] = None, api_url: Optional[str] = None):
        self.model_name = model_name or os.getenv("LLM_MODEL", "deepseek")
        self.llm = None
        self.use_local = False

        # Определяем, нужно ли загружать локальную модель
        # Если выбран deepseek/smollm17 и есть API URL – используем API
        if self.model_name in ("deepseek", "smollm17") and not api_url:
            api_url = os.getenv("LLM_API_URL", "https://api.deepseek.com/v1/chat/completions")
        self.api_url = api_url
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")

        if LLAMA_AVAILABLE and self.model_name not in ("deepseek", "smollm17"):
            # Только если явно не указан API, пробуем загрузить локально
            try:
                self.llm = Llama(model_path=f"./llama_cpp/models/{self.model_name}.gguf",
                                 n_ctx=2048, verbose=False)
                self.use_local = True
                logger.info(f"Local LLM loaded: {self.model_name}")
            except Exception as e:
                logger.warning(f"Cannot load local LLM: {e}")
        if not self.use_local and not self.api_url:
            logger.warning("LLMClient: no local model and no API URL configured")
        elif self.api_url:
            logger.info(f"LLMClient using remote API: {self.api_url}")

    def generate(self, prompt: str, max_tokens: int = 200, temperature: float = 0.35,
                 response_format: Optional[Dict[str, Any]] = None) -> str:
        if self.use_local and self.llm:
            return self._generate_local(prompt, max_tokens, temperature)
        elif self.api_url:
            return self._generate_api(prompt, max_tokens, temperature, response_format)
        else:
            raise RuntimeError("LLMClient is not properly configured")

    def _generate_local(self, prompt: str, max_tokens: int, temperature: float) -> str:
        output = self.llm(prompt, max_tokens=max_tokens, temperature=temperature,
                          stop=["<|User|>", "<|Assistant|>", "\n\n"])
        return output["choices"][0]["text"].strip()

    def _generate_api(self, prompt: str, max_tokens: int, temperature: float,
                      response_format: Optional[Dict[str, Any]] = None) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": "You are a precise trading strategy optimizer. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        if response_format:
            payload["response_format"] = response_format

        try:
            resp = requests.post(self.api_url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"].strip()
            # Очистка от ```json
            if text.startswith("```json"):
                text = text.split("```json")[1].split("```")[0].strip()
            elif text.startswith("```"):
                text = text.split("```")[1].strip()
            return text
        except Exception as e:
            logger.error(f"LLM API request failed: {e}")
            # Fallback: вернуть текущие параметры без изменений (будет обработано в вызывающем коде)
            return '{"max_risk_per_trade": 0.05, "phi_llm": 0.15}'

    def _fallback_generate(self, prompt, max_tokens=128, temperature=0.7):
        # Для совместимости, если кто-то вызовет старый метод
        return self.generate(prompt, max_tokens, temperature)