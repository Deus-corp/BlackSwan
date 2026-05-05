"""
LLM Client — обёртка для локальной модели через llama-cpp-python.
Поддерживает DeepSeek-R1 и SmolLM2-1.7B.
Модель выбирается через переменную окружения LLM_MODEL.
"""
import os
from llama_cpp import Llama

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

    def generate(self, prompt: str, max_tokens: int = 128, temperature: float = 0.7) -> str:
        if self.model_name == "deepseek":
            full_prompt = f"<|User|>{prompt}<|Assistant|>"
            response = self.llm(full_prompt, max_tokens=max_tokens, temperature=temperature,
                                stop=["<|User|>", "<|Assistant|>"])
            text = response["choices"][0]["text"]
            if ":" in text:
                text = text.split(" response:")[-1]
            return text.strip()
        else:
            response = self.llm(prompt, max_tokens=max_tokens, temperature=temperature,
                                stop=["<|User|>", "\n\n"])
            return response["choices"][0]["text"].strip()