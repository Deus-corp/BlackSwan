from llama_cpp import Llama

llm = Llama(
    model_path="llama_cpp/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf",
    n_ctx=512,          # минимальный контекст для скорости
    n_threads=4,        # меньше потоков = меньше накладных расходов
    n_batch=1,          # самый консервативный режим
    verbose=False
)

prompt = "Say 'hello'."
print("🤖 Запрос...")
response = llm(prompt, max_tokens=8, temperature=0.0)
print("✅ Ответ:", response["choices"][0]["text"])