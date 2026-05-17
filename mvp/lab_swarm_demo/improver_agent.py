#!/usr/bin/env python3
"""
Improver Agent – автономный улучшатель кода.
Сканирует папки проекта, прогоняет файлы через LLM пакетами,
сохраняет улучшенные версии в data/improver_output/.
"""
import asyncio, logging, os, sys, time, uuid, json
from pathlib import Path

from src.intelligence.llm_client import LLMClient
from swarm_config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s')
logger = logging.getLogger("ImproverAgent")

SCAN_DIRS = ["mvp/lab_swarm_demo", "src", "adapters", "sim", "dashboard"]
OUTPUT_DIR = "./data/improver_output"
SKIP_EXTENSIONS = {
    ".gguf", ".db", ".jsonl", ".log", ".pyc", ".md", ".txt",
    ".json", ".yml", ".ini", ".jar", ".sqlite3", ".pem", ".key"
}
MAX_FILE_SIZE_KB = 500          # увеличен для пакетного режима
BATCH_SIZE = 5                  # файлов за один запрос
SLEEP_BETWEEN_CYCLES = 3600     # ночной режим

EXCLUDE_DIRS = {
    "__pycache__", ".pytest_cache", ".venv", ".github",
    "assets", "config", "docs", "formal", "grafana", "llama_cpp",
    "logs", "scripts", "site", "tests", "tools",
    "data", ".git", "node_modules", "prometheus_data", "grafana_data",
}

EXCLUDE_FILES = {
    "Dockerfile", "=20.0",
}

class ImproverAgent:
    def __init__(self, single_pass: bool = False):
        self.node_id = f"improver-{uuid.uuid4().hex[:8]}"
        self.llm = LLMClient(n_ctx=32768)   # максимальный контекст
        self.single_pass = single_pass
        self.files_processed = 0
        self.files_improved = 0

    async def run(self):
        logger.info(f"🔧 ImproverAgent {self.node_id} started (single_pass={self.single_pass})")
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        while True:
            await self._process_all_files()
            if self.single_pass:
                logger.info(f"✅ Single pass complete. Processed {self.files_processed}, improved {self.files_improved}")
                break
            logger.info(f"💤 Sleeping for {SLEEP_BETWEEN_CYCLES}s before next cycle...")
            await asyncio.sleep(SLEEP_BETWEEN_CYCLES)

    async def _process_all_files(self):
        batch = []
        for scan_dir in SCAN_DIRS:
            if not os.path.exists(scan_dir):
                continue
            for root, dirs, files in os.walk(scan_dir):
                # Исключаем нежелательные папки
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                for filename in sorted(files):
                    filepath = os.path.join(root, filename)
                    if self._should_skip(filepath):
                        continue
                    batch.append(filepath)
                    if len(batch) >= BATCH_SIZE:
                        await self._improve_batch(batch)
                        batch.clear()
        # остатки
        if batch:
            await self._improve_batch(batch)

    def _should_skip(self, filepath: str) -> bool:
        ext = os.path.splitext(filepath)[1].lower()
        if ext in SKIP_EXTENSIONS:
            return True
        try:
            size_kb = os.path.getsize(filepath) / 1024
            if size_kb > MAX_FILE_SIZE_KB:
                return True
        except:
            return True
        return False

    async def _improve_batch(self, filepaths: list):
        # Читаем содержимое всех файлов в пакете
        files_content = ""
        for fp in filepaths:
            try:
                with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                if not content.strip():
                    continue
                files_content += f"\n\n--- FILE: {fp} ---\n{content}"
                self.files_processed += 1
            except Exception as e:
                logger.warning(f"Cannot read {fp}: {e}")

        if not files_content.strip():
            return

        prompt = f"""User: You are an expert Python code improver. You will receive a batch of related source files from a trading swarm project. 
For each file, output an IMPROVED version. Preserve all functionality.
- Improve readability: better variable names, add type hints, simplify logic.
- Add docstrings if missing.
- Fix obvious bugs or inefficiencies.
- Do NOT add new features.
- Separate each improved file with the exact line '--- FILE: <path> ---' (without quotes).

{files_content}

Improved versions:
"""
        try:
            response = self.llm.generate(prompt, max_tokens=4096, temperature=0.2)
        except Exception as e:
            logger.error(f"LLM failed: {e}")
            return

        if not response:
            return

        # Парсим ответ: разделяем по маркеру '--- FILE: ... ---'
        import re
        blocks = re.split(r'(?=--- FILE: .+ ---)', response)
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            # извлекаем путь файла из заголовка
            header_match = re.match(r'--- FILE: (.+) ---', block)
            if not header_match:
                continue
            original_path = header_match.group(1)
            # тело файла – всё после заголовка
            improved_code = block[header_match.end():].strip()
            if not improved_code:
                continue

            # сохраняем в зеркальную структуру
            relative_path = os.path.relpath(original_path, start=os.getcwd())
            output_path = os.path.join(OUTPUT_DIR, relative_path)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            try:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(improved_code)
                self.files_improved += 1
                logger.info(f"✅ Improved: {original_path} → {output_path}")
            except Exception as e:
                logger.error(f"Cannot write {output_path}: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--single-pass", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    node = ImproverAgent(single_pass=args.single_pass)
    try:
        asyncio.run(node.run())
    except KeyboardInterrupt:
        logger.info("ImproverAgent stopped.")