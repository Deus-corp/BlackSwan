"""
LLM Client — обёртка для локальной модели через llama-cpp-python.
Может быть расширен для DeepSeek API в будущем.
"""
from llama_cpp import Llama

class LLMClient:
    def __init__(self, model_path: str = None):
        if model_path is None:
            model_path = "llama_cpp/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf"
        self.llm = Llama(
            model_path="/app/llama_cpp/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf",  # путь из контейнера
            n_ctx=512,
            n_threads=4,
            verbose=False
        )

    def generate(self, prompt: str, max_tokens: int = 128, temperature: float = 0.7) -> str:
        """Отправляет запрос и возвращает сгенерированный текст."""
        response = self.llm(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=["<|User|>", "\n\n"]
        )
        return response["choices"][0]["text"].strip()