"""
LLM Client – a flexible client for local llama_cpp or remote DeepSeek API.

This module provides a unified interface for interacting with Large Language Models (LLMs),
supporting local inference via `llama-cpp-python` and remote calls to API services like DeepSeek.
It prioritizes local models if available and configured, falling back to remote APIs,
and provides a robust fallback mechanism if no LLM is accessible.
"""
import json
import os
import random
import requests
from typing import Any, Dict, Optional, Union, List
from loguru import logger

# Conditional import for llama_cpp to handle environments where it might not be installed.
LLAMA_AVAILABLE = False
try:
    from llama_cpp import Llama
    LLAMA_AVAILABLE = True
except ImportError:
    logger.warning("llama-cpp-python not installed. Local LLM functionality will be unavailable.")
except Exception as e:
    logger.error(f"An unexpected error occurred during llama_cpp import: {e}. Local LLM functionality will be unavailable.", exc_info=True)


class LLMClient:
    """
    A flexible client for interacting with Large Language Models (LLMs),
    supporting both local llama.cpp models and remote API services like DeepSeek.

    It attempts to load a local model first based on `model_name`. If a local model
    is not specified or fails to load, it falls back to a remote API if `api_url`
    and `api_key` are provided. As a last resort, it returns random strategy parameters.
    """
    def __init__(self, model_name: Optional[str] = None, api_url: Optional[str] = None, n_ctx: int = 2048) -> None:
        """
        Initializes the LLMClient.

        The client determines whether to use a local llama.cpp model or a remote API based on
        the `model_name`, provided `api_url`, and environment variables.

        Args:
            model_name (Optional[str]): The name of the LLM model to use (e.g., "smollm17", "deepseek",
                                        or a local GGUF model name like "my_model").
                                        Defaults to "deepseek" if not specified.
            api_url (Optional[str]): The URL of the LLM API endpoint.
                                     If `model_name` is "smollm17" or "deepseek" and `api_url` is `None`,
                                     it defaults to the DeepSeek API endpoint.
            n_ctx (int): The context window size for local llama.cpp models (default 2048).
                         This parameter is ignored for remote API calls.
        """
        self.model_name: str = model_name or os.getenv("LLM_MODEL", "deepseek")
        self.llm: Optional[Llama] = None
        self.use_local: bool = False

        # Determine the API URL. Prioritize explicitly passed api_url, then environment variable.
        # If model is DeepSeek alias and no API URL is given, default to DeepSeek's official URL.
        self.api_url: Optional[str]
        env_api_url: Optional[str] = os.getenv("LLM_API_URL")

        if api_url:
            self.api_url = api_url
        elif self.model_name in ("smollm17", "deepseek"):
            self.api_url = env_api_url or "https://api.deepseek.com/v1/chat/completions"
        else:
            self.api_url = env_api_url

        # Get API key from environment variable (assuming DEEPSEEK_API_KEY for DeepSeek).
        self.api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
        if not self.api_key and self.api_url:
            logger.warning(
                f"LLMClient configured for remote API at {self.api_url}, but DEEPSEEK_API_KEY environment variable "
                "is missing or empty. API calls will likely fail."
            )

        # Attempt to load a local llama.cpp model unless it's explicitly a remote model alias.
        if LLAMA_AVAILABLE and self.model_name not in ("smollm17", "deepseek"):
            # Assuming local GGUF models are stored in a `./llama_cpp/` directory
            model_path: str = os.path.join(".", "llama_cpp", f"{self.model_name}.gguf")
            if os.path.exists(model_path):
                try:
                    self.llm = Llama(
                        model_path=model_path,
                        n_ctx=n_ctx,
                        verbose=False, # Suppress llama.cpp internal logging for cleaner output
                        # Additional parameters like n_gpu_layers, logits_all, etc., could be added here
                    )
                    self.use_local = True
                    logger.info(f"Local LLM loaded successfully: {self.model_name} (n_ctx={n_ctx}) from {model_path}")
                except Exception as e:
                    logger.warning(
                        f"Failed to load local LLM '{self.model_name}' from {model_path}: {e}. "
                        "Falling back to remote API or random parameters."
                    )
                    self.llm = None # Ensure llm is None if loading fails
            else:
                logger.warning(f"Local LLM model file not found at: {model_path}. Skipping local LLM attempt.")
        
        # Log the final chosen LLM mode
        if self.use_local:
            pass # Message already logged above
        elif self.api_url and self.api_key:
            logger.info(f"LLMClient using remote API: {self.api_url} with model '{self.model_name}'")
        else:
            logger.warning(
                "LLMClient: No local model loaded and no remote API URL/key configured. "
                "All 'generate' calls will return fallback random parameters."
            )

    def generate(self, prompt: str, max_tokens: int = 200, temperature: float = 0.35,
                 response_format: Optional[Dict[str, str]] = None) -> str:
        """
        Generates a response from the LLM based on the provided prompt.

        This method attempts to use a local llama.cpp model first. If a local model
        is not available or fails, it falls back to a configured remote API.
        If neither is available or functional, it returns a JSON string with
        random strategy parameters as a safe fallback.

        Args:
            prompt (str): The input prompt for the LLM.
            max_tokens (int): The maximum number of tokens to generate in the response.
            temperature (float): Controls the randomness of the output. Higher values mean more random (0.0 to 2.0).
            response_format (Optional[Dict[str, str]]): Specifies the desired format for the response,
                                                        e.g., `{"type": "json_object"}` for APIs that support it.

        Returns:
            str: The generated text response. This will typically be a JSON string,
                 as the system prompt in `_generate_api` requests JSON output,
                 and `_random_strategy_json` also returns JSON.
        """
        if self.use_local and self.llm:
            logger.debug("Attempting to generate response using local LLM.")
            return self._generate_local(prompt, max_tokens, temperature)
        elif self.api_url and self.api_key: # Only attempt API call if an API key is present
            logger.debug(f"Attempting to generate response using remote API ({self.api_url}).")
            return self._generate_api(prompt, max_tokens, temperature, response_format)
        else:
            logger.warning(
                "No functional LLM available (local model not loaded or API key/URL missing). "
                "Returning random strategy parameters as fallback."
            )
            return self._random_strategy_json()

    def _generate_local(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """
        Generates a response using the local llama.cpp model.

        Args:
            prompt (str): The input prompt.
            max_tokens (int): The maximum number of tokens to generate.
            temperature (float): The sampling temperature.

        Returns:
            str: The generated text from the local LLM. If an error occurs during local
                 generation, a JSON string with random strategy parameters is returned.
        """
        if not self.llm:
            logger.error(
                "Attempted to use local LLM, but 'self.llm' is None. "
                "This indicates an initialization issue or a previous loading failure."
            )
            return self._random_strategy_json()
        
        try:
            # Llama.cpp's __call__ method can be used, but create_chat_completion is preferred
            # for chat models and explicit role handling.
            messages: List[Dict[str, str]] = [
                {"role": "system", "content": "You are a precise trading strategy optimizer. Always respond with valid JSON only. Ensure your entire response is a single JSON object."},
                {"role": "user", "content": prompt}
            ]
            
            output: Dict[str, Any] = self.llm.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=["<|User|>", "<|Assistant|>", "\n\n", "```"] # Common stop tokens for chat models and JSON markdown
            )
            # Extract content from the chat completion response structure
            content: str = output["choices"][0]["message"]["content"].strip()

            # Ensure the output is valid JSON by attempting to parse and re-serialize it.
            # This helps in case the local LLM deviates slightly from the instruction.
            try:
                parsed_json = json.loads(content)
                return json.dumps(parsed_json)
            except json.JSONDecodeError:
                logger.warning(f"Local LLM did not return valid JSON directly. Attempting heuristic extraction. Response: {content[:200]}...")
                # Fallback to heuristic extraction if direct load fails, as in _generate_api
                if content.startswith("```json"):
                    content = content.split("```json", 1)[1].split("```", 1)[0].strip()
                elif content.startswith("```"): # Generic code block, assume it's JSON
                    content = content.split("```", 1)[1].strip()
                try:
                    parsed_json = json.loads(content) # Try again after extraction
                    return json.dumps(parsed_json)
                except json.JSONDecodeError:
                    logger.error("Failed to extract valid JSON even with heuristics from local LLM output.")
                    return self._random_strategy_json() # Final fallback

        except Exception as e:
            logger.error(f"Error generating response from local LLM: {e}. Returning random fallback parameters.", exc_info=True)
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
                                                        e.g., `{"type": "json_object"}`.

        Returns:
            str: The generated text (expected to be JSON) from the API. If the API request fails
                 or parsing the response encounters an error, a JSON string with random strategy
                 parameters is returned as a fallback.
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

        # Add a timeout to the requests call to prevent indefinite blocking
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
            
            # Validate if the extracted text is indeed JSON
            try:
                parsed_json = json.loads(text)
                return json.dumps(parsed_json) # Return valid, compact JSON
            except json.JSONDecodeError:
                logger.error(
                    f"LLM API response content was not valid JSON after extraction: {text[:200]}... "
                    "Returning random fallback parameters."
                )
                return self._random_strategy_json()

        except requests.exceptions.RequestException as e:
            logger.error(f"LLM API request failed: {e}. Returning random fallback parameters.", exc_info=True)
            return self._random_strategy_json()
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            # Capture data in locals() for better debugging
            full_response_data = locals().get('data', 'N/A')
            logger.error(
                f"Failed to parse LLM API response or invalid JSON structure: {e}. "
                f"Full response: {full_response_data}. Returning random fallback parameters.", exc_info=True
            )
            return self._random_strategy_json()
        except Exception as e:
            logger.error(f"An unexpected error occurred during API generation: {e}. Returning random fallback parameters.", exc_info=True)
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
            # Added a random 'trend_strength_threshold' as a new reasonable parameter
            "trend_strength_threshold": round(random.uniform(0.1, 0.7), 4),
        }
        return json.dumps(params)
