"""
LLM Client – supports local llama_cpp, DeepSeek API, and Groq API.
"""
import json
import os
import random
import requests
from typing import Any, Dict, Optional, Union, List
from loguru import logger

LLAMA_AVAILABLE = False
try:
    from llama_cpp import Llama
    LLAMA_AVAILABLE = True
except ImportError:
    logger.warning("llama-cpp-python not installed. Local LLM functionality will be unavailable.")
except Exception as e:
    logger.error(f"Unexpected error during llama_cpp import: {e}", exc_info=True)


class LLMClient:
    def __init__(self, model_name: Optional[str] = None, api_url: Optional[str] = None, n_ctx: int = 2048) -> None:
        self.model_name: str = model_name or os.getenv("LLM_MODEL", "deepseek")
        self.llm: Optional[Llama] = None
        self.use_local: bool = False

        # Определяем провайдера
        self.provider: str = "deepseek"
        self.api_key: str = ""

        # Если задан GROQ_API_KEY, приоритет у Groq
        if os.getenv("GROQ_API_KEY"):
            self.provider = "groq"
            self.api_key = os.getenv("GROQ_API_KEY", "")
            self.api_url = api_url or "https://api.groq.com/openai/v1/chat/completions"
            logger.info("LLMClient configured for Groq API")
        else:
            self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
            env_api_url = os.getenv("LLM_API_URL")
            if api_url:
                self.api_url = api_url
            elif self.model_name in ("smollm17", "deepseek"):
                self.api_url = env_api_url or "https://api.deepseek.com/v1/chat/completions"
            else:
                self.api_url = env_api_url
            if self.api_url and self.api_key:
                logger.info(f"LLMClient using remote API: {self.api_url} with model '{self.model_name}'")
            else:
                logger.warning("LLMClient: no API key/URL for DeepSeek. Only local or fallback will work.")

        # Попытка загрузить локальную модель, если это не удалённые провайдеры
        if LLAMA_AVAILABLE and self.model_name not in ("smollm17", "deepseek", "groq"):
            model_path = os.path.join(".", "llama_cpp", f"{self.model_name}.gguf")
            if os.path.exists(model_path):
                try:
                    self.llm = Llama(model_path=model_path, n_ctx=n_ctx, verbose=False)
                    self.use_local = True
                    logger.info(f"Local LLM loaded: {self.model_name} (n_ctx={n_ctx})")
                except Exception as e:
                    logger.warning(f"Failed to load local LLM '{self.model_name}': {e}")
                    self.llm = None
            else:
                logger.warning(f"Local LLM model file not found: {model_path}")

        if self.use_local:
            pass
        elif not self.api_url or not self.api_key:
            logger.warning("No local model and no remote API configured. Will use random fallback.")

    def generate(self, prompt: str, max_tokens: int = 200, temperature: float = 0.35,
                 response_format: Optional[Dict[str, str]] = None) -> str:
        if self.use_local and self.llm:
            logger.debug("Using local LLM.")
            return self._generate_local(prompt, max_tokens, temperature)
        elif self.api_url and self.api_key:
            logger.debug(f"Using remote API ({self.api_url})")
            return self._generate_api(prompt, max_tokens, temperature, response_format)
        else:
            logger.warning("No LLM available. Returning random parameters.")
            return self._random_strategy_json()

    def _generate_local(self, prompt: str, max_tokens: int, temperature: float) -> str:
        # ... без изменений (приведён ниже полностью для целостности)
        # Оставляем существующий код _generate_local
        if not self.llm:
            return self._random_strategy_json()
        try:
            messages = [
                {"role": "system", "content": "You are a precise trading strategy optimizer. Always respond with valid JSON only. Ensure your entire response is a single JSON object."},
                {"role": "user", "content": prompt}
            ]
            output = self.llm.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=["<|User|>", "<|Assistant|>", "\n\n", "```"]
            )
            content = output["choices"][0]["message"]["content"].strip()
            try:
                parsed = json.loads(content)
                return json.dumps(parsed)
            except json.JSONDecodeError:
                logger.warning("Local LLM output not JSON, trying heuristic extraction...")
                if content.startswith("```json"):
                    content = content.split("```json", 1)[1].split("```", 1)[0].strip()
                elif content.startswith("```"):
                    content = content.split("```", 1)[1].strip()
                try:
                    parsed = json.loads(content)
                    return json.dumps(parsed)
                except json.JSONDecodeError:
                    logger.error("Failed to extract JSON from local LLM output.")
                    return self._random_strategy_json()
        except Exception as e:
            logger.error(f"Local LLM error: {e}")
            return self._random_strategy_json()

    def _generate_api(self, prompt: str, max_tokens: int, temperature: float,
                      response_format: Optional[Dict[str, str]] = None) -> str:
        if not self.api_url or not self.api_key:
            return self._random_strategy_json()

        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}

        # Выбираем модель в зависимости от провайдера
        if self.provider == "groq":
            api_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        else:
            if self.model_name in ("smollm17", "deepseek"):
                api_model = "deepseek-chat"
            else:
                api_model = self.model_name

        payload = {
            "model": api_model,
            "messages": [
                {"role": "system", "content": "You are a precise trading strategy optimizer. Always respond with valid JSON only. Ensure your entire response is a single JSON object."},
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

            # Извлекаем JSON из возможных Markdown-блоков
            if text.startswith("```json"):
                text = text.split("```json", 1)[1].split("```", 1)[0].strip()
            elif text.startswith("```"):
                text = text.split("```", 1)[1].strip()

            try:
                parsed = json.loads(text)
                return json.dumps(parsed)
            except json.JSONDecodeError:
                logger.error(f"API response not valid JSON after extraction: {text[:200]}...")
                return self._random_strategy_json()

        except Exception as e:
            logger.error(f"API request failed: {e}")
            return self._random_strategy_json()

    def _random_strategy_json(self) -> str:
        params = {
            "max_risk_per_trade": round(random.uniform(0.01, 0.3), 4),
            "phi_llm": round(random.uniform(0.01, 1.0), 4),
            "stop_loss_ratio": round(random.uniform(0.001, 0.2), 4),
            "trailing_stop_ratio": round(random.uniform(0.0, 0.1), 4),
            "momentum_window": random.randint(2, 50),
            "volatility_threshold": round(random.uniform(0.001, 0.3), 4),
            "trend_strength_threshold": round(random.uniform(0.1, 0.7), 4),
        }
        return json.dumps(params)