"""
LLM Client – a flexible client for local llama_cpp or remote DeepSeek API.
"""
import json
import os
import random
import requests
from typing import Any, Dict, Optional, Union
from loguru import logger

try:
    from llama_cpp import Llama
    LLAMA_AVAILABLE = True
except ImportError:
    Llama = None
    LLAMA_AVAILABLE = False
    logger.warning("llama-cpp-python not installed. Local LLM functionality will be unavailable.")


class LLMClient:
    """
    A flexible client for interacting with Large Language Models (LLMs),
    supporting both local llama.cpp models and remote API services like DeepSeek.
    """
    def __init__(self, model_name: Optional[str] = None, api_url: Optional[str] = None, n_ctx: int = 2048) -> None:
        """
        Initializes the LLMClient, attempting to load a local model first,
        then falling back to a remote API if specified or configured via environment variables.

        Args:
            model_name (Optional[str]): The name of the LLM model to use (e.g., "smollm17").
                                        Defaults to "deepseek" or LLM_MODEL environment variable.
                                        If "smollm17" or "deepseek" is chosen and no API URL is provided,
                                        it defaults to the DeepSeek API endpoint.
            api_url (Optional[str]): The URL of the LLM API endpoint.
                                     Defaults to DeepSeek API for "smollm17" or LLM_API_URL environment variable.
            n_ctx (int): The context window size for local llama.cpp models (default 2048).
        """
        # Determine model name, defaulting to "deepseek" if not specified
        self.model_name: str = model_name or os.getenv("LLM_MODEL", "deepseek")
        self.llm: Optional[Llama] = None
        self.use_local: bool = False

        # Configure API URL. If model_name is an alias for DeepSeek and no API_URL is given, use DeepSeek default.
        self.api_url: Optional[str]
        if (self.model_name == "smollm17" or self.model_name == "deepseek") and not api_url:
            self.api_url = os.getenv("LLM_API_URL", "https://api.deepseek.com/v1/chat/completions")
        else:
            self.api_url = api_url or os.getenv("LLM_API_URL")

        # Get API key from environment variable
        self.api_key: str = os.getenv("DEEPSEEK_API_KEY", "")

        # Attempt to load a local llama.cpp model
        # Exclude known remote model aliases ("smollm17", "deepseek") from local loading.
        if LLAMA_AVAILABLE and self.model_name not in ("smollm17", "deepseek"):
            model_path = f"./llama_cpp/{self.model_name}.gguf"
            if os.path.exists(model_path):
                try:
                    self.llm = Llama(
                        model_path=model_path,
                        n_ctx=n_ctx,
                        verbose=False # Suppress llama.cpp internal logging for cleaner output
                    )
                    self.use_local = True
                    logger.info(f"Local LLM loaded: {self.model_name} (n_ctx={n_ctx}) from {model_path}")
                except Exception as e:
                    logger.warning(f"Failed to load local LLM '{self.model_name}' from {model_path}: {e}")
            else:
                logger.warning(f"Local LLM model file not found: {model_path}. Skipping local LLM.")
        
        # Log the chosen LLM mode
        if self.use_local:
            pass # Message already logged above
        elif self.api_url and self.api_key:
            logger.info(f"LLMClient using remote API: {self.api_url} with model '{self.model_name}'")
        elif self.api_url and not self.api_key:
            logger.warning(f"LLMClient configured for remote API at {self.api_url}, but DEEPSEEK_API_KEY is missing. API calls will likely fail.")
        else:
            logger.warning("LLMClient: No local model loaded and no API URL/key configured. Will use fallback random parameters.")

    def generate(self, prompt: str, max_tokens: int = 200, temperature: float = 0.35,
                 response_format: Optional[Dict[str, str]] = None) -> str:
        """
        Generates a response from the LLM based on the provided prompt.
        Prioritizes the local model, then a remote API, otherwise returns random fallback parameters.

        Args:
            prompt (str): The input prompt for the LLM.
            max_tokens (int): The maximum number of tokens to generate in the response.
            temperature (float): Controls the randomness of the output. Higher values mean more random (0.0 to 2.0).
            response_format (Optional[Dict[str, str]]): Specifies the desired format for the response,
                                                        e.g., {"type": "json_object"}.

        Returns:
            str: The generated text response. If no LLM is available or an error occurs during generation,
                 a JSON string with random strategy parameters is returned as a fallback.
        """
        if self.use_local and self.llm:
            return self._generate_local(prompt, max_tokens, temperature)
        elif self.api_url and self.api_key: # Only attempt API call if an API key is present
            return self._generate_api(prompt, max_tokens, temperature, response_format)
        else:
            # No local model, no API configured, or API key missing – return random fallback parameters
            logger.warning("No functional LLM available (local or API with key). Returning random strategy parameters.")
            return self._random_strategy_json()

    def _generate_local(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """
        Generates a response using the local llama.cpp model.

        Args:
            prompt (str): The input prompt.
            max_tokens (int): The maximum number of tokens to generate.
            temperature (float): The sampling temperature.

        Returns:
            str: The generated text from the local LLM. Returns a JSON string with random strategy
                 parameters if an error occurs during local generation.
        """
        if not self.llm:
            logger.error("Attempted to use local LLM, but 'self.llm' is None. This indicates an initialization issue.")
            return self._random_strategy_json()
        
        try:
            output: Dict[str, Any] = self.llm(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=["<|User|>", "<|Assistant|>", "\n\n"] # Common stop tokens for chat models
            )
            return output["choices"][0]["text"].strip()
        except Exception as e:
            logger.error(f"Error generating response from local LLM: {e}. Returning random fallback parameters.")
            return self._random_strategy_json()

    def _generate_api(self, prompt: str, max_tokens: int, temperature: float, 
                      response_format: Optional[Dict[str, str]] = None) -> str:
        """
        Generates a response using a remote LLM API (e.g., DeepSeek).

        Args:
            prompt (str): The input prompt.
            max_tokens (int): The maximum number of tokens to generate.
            temperature (float): The sampling temperature.
            response_format (Optional[Dict[str, str]]): Specifies the desired format for the response,
                                                        e.g., {"type": "json_object"}.

        Returns:
            str: The generated text from the API. Returns a JSON string with random strategy parameters
                 if the API request fails or parsing the response encounters an error.
        """
        if not self.api_url or not self.api_key:
            logger.warning("API URL or API key is not set for remote API calls. Returning random fallback parameters.")
            return self._random_strategy_json()

        headers: Dict[str, str] = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        
        # Determine the actual model identifier to send to the API
        api_model_to_use: str
        if self.model_name in ("smollm17", "deepseek"):
            # Map internal aliases/generic name to the specific DeepSeek model name
            api_model_to_use = "deepseek-chat"
            logger.debug(f"Mapping internal model_name '{self.model_name}' to DeepSeek API model '{api_model_to_use}'.")
        else:
            api_model_to_use = self.model_name # Use the model_name as specified if it's not a known alias

        payload: Dict[str, Any] = {
            "model": api_model_to_use, # Use the determined API model identifier
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
            # Explicitly cast self.api_url to str as requests.post expects str
            resp = requests.post(str(self.api_url), json=payload, headers=headers, timeout=30)
            resp.raise_for_status() # Raises an HTTPError for bad responses (4xx or 5xx)
            data: Dict[str, Any] = resp.json()
            text: str = data["choices"][0]["message"]["content"].strip()
            
            # Extract JSON from markdown code blocks if present (common LLM output format)
            if text.startswith("```json"):
                text = text.split("```json", 1)[1].split("```", 1)[0].strip()
            elif text.startswith("```"): # Generic code block, assume it's JSON
                text = text.split("```", 1)[1].strip()
            return text
        except requests.exceptions.RequestException as e:
            logger.error(f"LLM API request failed: {e}. Returning random fallback parameters.")
            return self._random_strategy_json()
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            logger.error(f"Failed to parse LLM API response or invalid JSON: {e}. Full response: {data if 'data' in locals() else 'N/A'}. Returning random fallback parameters.")
            return self._random_strategy_json()

    def _random_strategy_json(self) -> str:
        """
        Generates random, but reasonable, strategy parameters in JSON format.
        This serves as a fallback when no LLM is available or an error occurs during generation,
        ensuring the system can still proceed with some parameters.

        Returns:
            str: A JSON string representing a set of random strategy parameters.
        """
        params: Dict[str, Union[float, int]] = {
            "max_risk_per_trade": round(random.uniform(0.01, 0.3), 4),
            "phi_llm": round(random.uniform(0.01, 1.0), 4),
            "stop_loss_ratio": round(random.uniform(0.001, 0.2), 4),
            "trailing_stop_ratio": round(random.uniform(0.0, 0.1), 4),
            "momentum_window": random.randint(2, 50), # Integer parameter
            "volatility_threshold": round(random.uniform(0.001, 0.3), 4),
        }
        return json.dumps(params)
