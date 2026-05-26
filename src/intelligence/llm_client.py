"""LLM Client – supports local llama_cpp, DeepSeek API, Groq API, and safe fallback."""

from __future__ import annotations

import json
import os
import random
import re
import time
from typing import Any, Optional

import requests
from loguru import logger

LLAMA_AVAILABLE = False
Llama: Any = None

try:
    from llama_cpp import Llama as _Llama

    Llama = _Llama
    LLAMA_AVAILABLE = True
except ImportError:
    logger.warning("llama-cpp-python not installed. Local LLM functionality is unavailable.")
except Exception as exc:
    logger.error("Unexpected error during llama_cpp import: {}", exc, exc_info=True)


class LLMClient:
    """Small JSON-oriented LLM client with remote/local/fallback generation."""

    DEFAULT_LOCAL_DIR = "./llama_cpp"
    DEFAULT_DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
    DEFAULT_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

    DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"
    DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"

    DEFAULT_TIMEOUT_SECONDS = 30
    DEFAULT_MAX_RETRIES = 2
    DEFAULT_BACKOFF_SECONDS = 1.0

    STRATEGY_KEYS = (
        "max_risk_per_trade",
        "phi_llm",
        "stop_loss_ratio",
        "trailing_stop_ratio",
        "momentum_window",
        "volatility_threshold",
        "trend_strength_threshold",
    )

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_url: Optional[str] = None,
        n_ctx: int = 2048,
        *,
        provider: Optional[str] = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self.model_name = str(model_name or os.getenv("LLM_MODEL", "deepseek")).strip()
        self.llm: Optional[Any] = None
        self.use_local = False

        self.provider = self._resolve_provider(provider)
        self.api_key = self._resolve_api_key(self.provider)
        self.api_url = self._resolve_api_url(self.provider, api_url)
        self.timeout_seconds = max(1, int(timeout_seconds))
        self.max_retries = max(1, int(max_retries))

        self._configure_local_if_needed(n_ctx=n_ctx)
        self._log_configuration()

    def generate(
        self,
        prompt: str,
        max_tokens: int = 200,
        temperature: float = 0.35,
        response_format: Optional[dict[str, str]] = None,
    ) -> str:
        """Generate text, preferring local model when configured, then API, then fallback JSON."""
        clean_prompt = str(prompt or "")
        max_tokens = max(1, int(max_tokens))
        temperature = max(0.0, min(2.0, float(temperature)))

        if self.use_local and self.llm is not None:
            logger.debug("Using local LLM.")
            return self._generate_local(clean_prompt, max_tokens, temperature)

        if self.api_url and self.api_key:
            logger.debug("Using remote API ({})", self.api_url)
            return self._generate_api(clean_prompt, max_tokens, temperature, response_format)

        logger.warning("No LLM available. Returning random strategy parameters.")
        return self._random_strategy_json()

    def _resolve_provider(self, provider: Optional[str]) -> str:
        clean_provider = str(provider or os.getenv("LLM_PROVIDER", "")).strip().lower()
        if clean_provider in {"local", "deepseek", "groq"}:
            return clean_provider

        if os.getenv("GROQ_API_KEY"):
            return "groq"

        if os.getenv("DEEPSEEK_API_KEY"):
            return "deepseek"

        if self.model_name not in {"smollm17", "deepseek", "groq"}:
            return "local"

        return "deepseek"

    @staticmethod
    def _resolve_api_key(provider: str) -> str:
        if provider == "groq":
            return str(os.getenv("GROQ_API_KEY", "")).strip()
        if provider == "deepseek":
            return str(os.getenv("DEEPSEEK_API_KEY", "")).strip()
        return ""

    def _resolve_api_url(self, provider: str, api_url: Optional[str]) -> str:
        if api_url:
            return str(api_url).strip()

        env_api_url = str(os.getenv("LLM_API_URL", "")).strip()
        if env_api_url:
            return env_api_url

        if provider == "groq":
            return self.DEFAULT_GROQ_URL

        if provider == "deepseek":
            return self.DEFAULT_DEEPSEEK_URL

        return ""

    def _configure_local_if_needed(self, *, n_ctx: int) -> None:
        if self.provider != "local":
            return

        if not LLAMA_AVAILABLE:
            logger.warning("Local LLM requested but llama-cpp-python is unavailable.")
            return

        model_path = os.getenv("LLM_MODEL_PATH", "")
        if not model_path:
            model_path = os.path.join(self.DEFAULT_LOCAL_DIR, f"{self.model_name}.gguf")

        if not os.path.exists(model_path):
            logger.warning("Local LLM model file not found: {}", model_path)
            return

        try:
            self.llm = Llama(model_path=model_path, n_ctx=max(512, int(n_ctx)), verbose=False)
            self.use_local = True
            logger.info("Local LLM loaded: {} path={} n_ctx={}", self.model_name, model_path, n_ctx)
        except Exception as exc:
            logger.warning("Failed to load local LLM '{}': {}", self.model_name, exc)
            self.llm = None
            self.use_local = False

    def _log_configuration(self) -> None:
        if self.use_local:
            return

        if self.provider == "groq":
            if self.api_key and self.api_url:
                logger.info("LLMClient configured for Groq API model={}", self._api_model())
            else:
                logger.warning("LLMClient provider=groq but GROQ_API_KEY or api_url is missing.")
            return

        if self.provider == "deepseek":
            if self.api_key and self.api_url:
                logger.info("LLMClient configured for DeepSeek API model={}", self._api_model())
            else:
                logger.warning("LLMClient provider=deepseek but DEEPSEEK_API_KEY or api_url is missing.")
            return

        logger.warning("No local model and no remote API configured. Random fallback will be used.")

    def _generate_local(self, prompt: str, max_tokens: int, temperature: float) -> str:
        if self.llm is None:
            return self._random_strategy_json()

        try:
            output = self.llm.create_chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a precise trading strategy optimizer. "
                            "Always respond with a single valid JSON object only."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                stop=["<|User|>", "<|Assistant|>", "```"],
            )

            content = str(output["choices"][0]["message"]["content"]).strip()
            normalized = self._normalize_json_response(content)
            if normalized is not None:
                return normalized

            logger.warning("Local LLM output was not valid JSON.")
            return self._random_strategy_json()

        except Exception as exc:
            logger.warning("Local LLM error: {}", exc, exc_info=True)
            return self._random_strategy_json()

    def _generate_api(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        response_format: Optional[dict[str, str]] = None,
    ) -> str:
        if not self.api_url or not self.api_key:
            return self._random_strategy_json()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload: dict[str, Any] = {
            "model": self._api_model(),
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a precise trading strategy optimizer. "
                        "Always respond with a single valid JSON object only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if response_format:
            payload["response_format"] = dict(response_format)

        last_error: Optional[BaseException] = None

        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )

                if response.status_code == 429 and attempt < self.max_retries - 1:
                    delay = self._retry_delay(response, attempt)
                    logger.warning("LLM API rate limited; retrying in {:.2f}s.", delay)
                    time.sleep(delay)
                    continue

                response.raise_for_status()
                data = response.json()
                text = str(data["choices"][0]["message"]["content"]).strip()

                normalized = self._normalize_json_response(text)
                if normalized is not None:
                    return normalized

                logger.warning("API response was not valid JSON after extraction: {}...", text[:200])
                return self._random_strategy_json()

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "API request failed ({}/{}): {}",
                    attempt + 1,
                    self.max_retries,
                    exc,
                )

                if attempt < self.max_retries - 1:
                    time.sleep(self.DEFAULT_BACKOFF_SECONDS * (attempt + 1))

        logger.error("LLM API generation failed after retries: {}", last_error)
        return self._random_strategy_json()

    def _api_model(self) -> str:
        if self.provider == "groq":
            return str(os.getenv("GROQ_MODEL", self.DEFAULT_GROQ_MODEL)).strip()

        if self.provider == "deepseek":
            if self.model_name in {"smollm17", "deepseek"}:
                return str(os.getenv("DEEPSEEK_MODEL", self.DEFAULT_DEEPSEEK_MODEL)).strip()
            return self.model_name

        return self.model_name

    @classmethod
    def _normalize_json_response(cls, text: str) -> Optional[str]:
        candidate = cls._extract_json_object(text)
        if candidate is None:
            return None

        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            return None

        if not isinstance(parsed, dict):
            return None

        return json.dumps(parsed, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @classmethod
    def _extract_json_object(cls, text: str) -> Optional[str]:
        if not text:
            return None

        clean_text = cls._strip_noise(str(text))

        for pattern in (
            r"```json\s*(\{.*?\})\s*```",
            r"```\s*(\{.*?\})\s*```",
        ):
            match = re.search(pattern, clean_text, re.DOTALL | re.IGNORECASE)
            if match:
                candidate = match.group(1).strip()
                if cls._is_valid_json_object(candidate):
                    return candidate

        starts = [idx for idx, char in enumerate(clean_text) if char == "{"]

        for start in starts:
            depth = 0
            in_string = False
            escape = False

            for idx in range(start, len(clean_text)):
                char = clean_text[idx]

                if in_string:
                    if escape:
                        escape = False
                    elif char == "\\":
                        escape = True
                    elif char == '"':
                        in_string = False
                    continue

                if char == '"':
                    in_string = True
                elif char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = clean_text[start : idx + 1].strip()
                        if cls._is_valid_json_object(candidate):
                            return candidate
                        break

        return None

    @staticmethod
    def _strip_noise(text: str) -> str:
        text = re.sub(
            r"<\s*think\s*>.*?(?:<\s*/\s*think\s*>|$)",
            "",
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        text = re.sub(r"<[^>]+>", "", text)
        return text.strip()

    @staticmethod
    def _is_valid_json_object(candidate: str) -> bool:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            return False
        return isinstance(parsed, dict)

    @staticmethod
    def _retry_delay(response: requests.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(0.5, min(60.0, float(retry_after)))
            except ValueError:
                pass

        return min(30.0, 1.0 + (2**attempt))

    def _random_strategy_json(self) -> str:
        params = {
            "max_risk_per_trade": round(random.uniform(0.01, 0.2), 4),
            "phi_llm": round(random.uniform(0.01, 1.0), 4),
            "stop_loss_ratio": round(random.uniform(0.001, 0.2), 4),
            "trailing_stop_ratio": round(random.uniform(0.001, 0.1), 4),
            "momentum_window": random.randint(2, 50),
            "volatility_threshold": round(random.uniform(0.001, 0.3), 4),
            "trend_strength_threshold": round(random.uniform(0.1, 0.7), 4),
        }
        return json.dumps(params, ensure_ascii=False, sort_keys=True, separators=(",", ":"))