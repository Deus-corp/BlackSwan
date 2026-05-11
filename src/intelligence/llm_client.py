"""
LLM Client — обёртка для локальной модели через llama-cpp-python.
Поддерживает DeepSeek-R1 и SmolLM2-1.7B.
Модель выбирается через переменную окружения LLM_MODEL.
"""
import os
from llama_cpp import Llama
from typing import Dict, Any, Optional

MODEL_NAME = os.environ.get("LLM_MODEL", "deepseek")  # по умолчанию DeepSeek

MODEL_PATHS = {
    "deepseek": "llama_cpp/DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf",
    "smollm17": "llama_cpp/SmolLM2-1.7B-Instruct-Q4_K_M.gguf",
}

class LLMClient:
    def __init__(self, model_name: str = None):
        if model_name is None:
            model_name = MODEL_NAME
        # Безопасный fallback: если модель не найдена – берём deepseek
        model_path = MODEL_PATHS.get(model_name, MODEL_PATHS.get("deepseek"))

        if model_path is None:
            raise ValueError(f"Unknown model {model_name} and no default model available")

        self.model_name = model_name
        self.llm = Llama(
            model_path=model_path,
            n_ctx=512,
            n_threads=4,
            verbose=False,
            chat_format="deepseek" if self.model_name == "deepseek" else None,
        )

    def generate(
        self,
        prompt: str,
        max_tokens: int = 200,
        temperature: float = 0.35,
        response_format: Optional[Dict[str, Any]] = None
    ) -> str:
        messages = [
            {"role": "system", "content": "You are a precise trading strategy optimizer. Always respond with valid JSON only."},
            {"role": "user", "content": prompt}
        ]
        kwargs = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stop": ["<|User|>", "<|Assistant|>", "\n\n"],
        }
        if response_format:
            kwargs["response_format"] = response_format
        try:
            response = self.llm.create_chat_completion(**kwargs)
            text = response["choices"][0]["message"]["content"].strip()
            # Очистка
            if text.startswith("```json"):
                text = text.split("```json")[1].split("```")[0].strip()
            elif text.startswith("```"):
                text = text.split("```")[1].strip()
            return text
        except Exception:
            return self._fallback_generate(prompt, max_tokens, temperature)

    def _fallback_generate(self, prompt: str, max_tokens: int = 128, temperature: float = 0.7) -> str:
        if self.model_name.startswith("deepseek"):
            full_prompt = f"<|User|>{prompt}<|Assistant|>"
            response = self.llm(full_prompt, max_tokens=max_tokens, temperature=temperature,
                                stop=["<|User|>", "<|Assistant|>"])
        else:
            response = self.llm(prompt, max_tokens=max_tokens, temperature=temperature,
                                stop=["<|User|>", "\n\n"])
        return response["choices"][0]["text"].strip()