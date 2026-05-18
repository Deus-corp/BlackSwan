"""
LLM Client – гибкий клиент для локального llama_cpp или удалённого DeepSeek API.
"""
import os
import json
import random # This import is already present and correctly used.
import requests
from typing import Optional, Dict, Any
from loguru import logger

try:
    from llama_cpp import Llama
    LLAMA_AVAILABLE = True
except ImportError:
    Llama = None
    LLAMA_AVAILABLE = False


class LLMClient:
    """
    A flexible client for interacting with Large Language Models (LLMs),
    supporting both local llama.cpp models and remote API services like DeepSeek.
    """
    def __init__(self, model_name: Optional[str] = None, api_url: Optional[str] = None, n_ctx: int = 2048):
        """
        Initializes the LLMClient, attempting to load a local model first,
        then falling back to a remote API if specified or configured via environment variables.

        Args:
            model_name (Optional[str]): The name of the LLM model to use (e.g., "smollm17").
                                        Defaults to "deepseek" or LLM_MODEL environment variable.
            api_url (Optional[str]): The URL of the LLM API endpoint.
                                     Defaults to DeepSeek API for "smollm17" or LLM_API_URL environment variable.
            n_ctx (int): The context window size for local llama.cpp models.
        """
        self.model_name: str = model_name or os.getenv("LLM_MODEL", "deepseek")
        self.llm: Optional[Llama] = None
        self.use_local: bool = False

        if self.model_name == "smollm17" and not api_url:
            api_url = os.getenv("LLM_API_URL", "https://api.deepseek.com/v1/chat/completions")
        self.api_url: Optional[str] = api_url
        self.api_key: str = os.getenv("DEEPSEEK_API_KEY", "")

        if LLAMA_AVAILABLE and self.model_name not in ("smollm17",):
            try:
                # Assuming model_path is relative to the current working directory
                self.llm = Llama(model_path=f"./llama_cpp/{self.model_name}.gguf",
                                 n_ctx=n_ctx, verbose=False)
                self.use_local = True
                logger.info(f"Local LLM loaded: {self.model_name} (n_ctx={n_ctx})")
            except Exception as e:
                logger.warning(f"Cannot load local LLM '{self.model_name}': {e}")
        
        if not self.use_local and not self.api_url:
            logger.warning("LLMClient: no local model and no API URL configured – will use fallback random params")
        elif self.api_url:
            logger.info(f"LLMClient using remote API: {self.api_url}")

    def generate(self, prompt: str, max_tokens: int = 200, temperature: float = 0.35,
                 response_format: Optional[Dict[str, Any]] = None) -> str:
        """
        Generates a response from the LLM based on the provided prompt.
        Prioritizes local model, then remote API, otherwise returns random fallback parameters.

        Args:
            prompt (str): The input prompt for the LLM.
            max_tokens (int): The maximum number of tokens to generate in the response.
            temperature (float): Controls the randomness of the output. Higher values mean more random.
            response_format (Optional[Dict[str, Any]]): Specifies the desired format for the response,
                                                        e.g., {"type": "json_object"}.

        Returns:
            str: The generated text response, or a JSON string with random strategy parameters
                 if no LLM is available.
        """
        if self.use_local and self.llm:
            return self._generate_local(prompt, max_tokens, temperature)
        elif self.api_url:
            return self._generate_api(prompt, max_tokens, temperature, response_format)
        else:
            # Нет ни локальной модели, ни API – сразу возвращаем случайные новые параметры
            logger.warning("No LLM available (local or API). Returning random strategy parameters.")
            return self._random_strategy_json()

    def _generate_local(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """
        Generates a response using the local llama.cpp model.

        Args:
            prompt (str): The input prompt.
            max_tokens (int): The maximum number of tokens to generate.
            temperature (float): The sampling temperature.

        Returns:
            str: The generated text from the local LLM.
        """
        if not self.llm:
            logger.error("Attempted to use local LLM, but 'self.llm' is None.")
            return self._random_strategy_json()
            
        output = self.llm(prompt, max_tokens=max_tokens, temperature=temperature,
                          stop=["<|User|>", "<|Assistant|>", "\n\n"])
        return output["choices"][0]["text"].strip()

    def _generate_api(self, prompt: str, max_tokens: int, temperature: float, 
                      response_format: Optional[Dict[str, Any]] = None) -> str:
        """
        Generates a response using a remote LLM API (e.g., DeepSeek).

        Args:
            prompt (str): The input prompt.
            max_tokens (int): The maximum number of tokens to generate.
            temperature (float): The sampling temperature.
            response_format (Optional[Dict[str, Any]]): Specifies the desired format for the response.

        Returns:
            str: The generated text from the API, or a JSON string with random strategy parameters
                 if the API request fails.
        """
        if not self.api_key:
            logger.warning("No DEEPSEEK_API_KEY set for API calls, using random fallback params")
            return self._random_strategy_json()

        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
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
            resp.raise_for_status() # Raises an HTTPError for bad responses (4xx or 5xx)
            data = resp.json()
            text = data["choices"][0]["message"]["content"].strip()
            
            # Extract JSON from markdown code blocks if present
            if text.startswith("```json"):
                text = text.split("```json")[1].split("```")[0].strip()
            elif text.startswith("```"):
                text = text.split("```")[1].strip()
            return text
        except requests.exceptions.RequestException as e:
            logger.error(f"LLM API request failed: {e}")
            return self._random_strategy_json()
        except (KeyError, IndexError) as e:
            logger.error(f"Failed to parse LLM API response: {e}. Full response: {data}")
            return self._random_strategy_json()

    def _random_strategy_json(self) -> str:
        """
        Генерирует случайные, но разумные параметры стратегии в виде JSON.
        This serves as a fallback when no LLM is available or an error occurs.

        Returns:
            str: A JSON string representing a set of random strategy parameters.
        """
        # Removed redundant 'import random' as it's already at the top
        params = {
            "max_risk_per_trade": round(random.uniform(0.01, 0.3), 4),
            "phi_llm": round(random.uniform(0.01, 1.0), 4),
            "stop_loss_ratio": round(random.uniform(0.001, 0.2), 4),
            "trailing_stop_ratio": round(random.uniform(0.0, 0.1), 4),
            "momentum_window": random.randint(2, 50),
            "volatility_threshold": round(random.uniform(0.001, 0.3), 4),
        }
        return json.dumps(params)