#!/usr/bin/env python3
"""
Improver Agent – автономный улучшатель кода.
Первый проход: оригинальные файлы проекта.
Последующие проходы: улучшенные версии из data/improver_output/.
"""
import asyncio, logging, os, re, uuid, ast

from src.intelligence.llm_client import LLMClient
from swarm_config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s')
logger = logging.getLogger("ImproverAgent")

ORIGINAL_SCAN_DIRS = ["mvp/lab_swarm_demo", "src", "adapters", "sim", "dashboard"]
OUTPUT_DIR = "./data/improver_output"
FAILED_DIR = "./data/improver_failed"

SKIP_EXTENSIONS = {
    ".gguf", ".db", ".jsonl", ".log", ".pyc", ".md", ".txt",
    ".json", ".yml", ".ini", ".jar", ".sqlite3", ".pem", ".key"
}
EXCLUDE_DIRS = {
    "__pycache__", ".pytest_cache", ".venv", ".github",
    "assets", "config", "docs", "formal", "grafana", "llama_cpp",
    "logs", "scripts", "site", "tests", "tools",
    "data", ".git", "node_modules", "prometheus_data", "grafana_data",
}
EXCLUDE_FILES = {"Dockerfile", "=20.0"}

MAX_FILE_SIZE_KB = 100
MAX_BATCH_CHARS = 45000
SLEEP_BETWEEN_CYCLES = 3600


class ImproverAgent:
    def __init__(self, single_pass: bool = False):
        self.node_id = f"improver-{uuid.uuid4().hex[:8]}"
        self.llm = LLMClient(n_ctx=32768)
        self.single_pass = single_pass
        self.first_pass = True
        self.files_processed = 0
        self.files_improved = 0

    async def run(self):
        logger.info(f"🔧 Agent {self.node_id} started (single_pass={self.single_pass})")
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        os.makedirs(FAILED_DIR, exist_ok=True)

        while True:
            await self._process_all_files()
            logger.info(
                f"Cycle done. Processed: {self.files_processed}, improved: {self.files_improved}"
            )
            if self.single_pass:
                break
            self.first_pass = False
            logger.info(f"💤 Sleeping {SLEEP_BETWEEN_CYCLES}s before next cycle …")
            await asyncio.sleep(SLEEP_BETWEEN_CYCLES)

    async def _process_all_files(self):
        scan_dirs = ORIGINAL_SCAN_DIRS if self.first_pass else [OUTPUT_DIR]
        exclude_dirs = set(EXCLUDE_DIRS)
        if not self.first_pass:
            # не заходим в failed-папку
            exclude_dirs.add("improver_failed")

        batch = []
        current_chars = 0
        for scan_dir in scan_dirs:
            if not os.path.exists(scan_dir):
                continue
            for root, dirs, files in os.walk(scan_dir):
                dirs[:] = [d for d in dirs if d not in exclude_dirs]
                for filename in sorted(files):
                    filepath = os.path.join(root, filename)
                    if self._should_skip(filepath):
                        continue
                    file_size = os.path.getsize(filepath)
                    if current_chars + file_size > MAX_BATCH_CHARS and batch:
                        await self._improve_batch(batch)
                        batch.clear()
                        current_chars = 0
                    batch.append(filepath)
                    current_chars += file_size
        if batch:
            await self._improve_batch(batch)

    def _should_skip(self, filepath: str) -> bool:
        basename = os.path.basename(filepath)
        if basename in EXCLUDE_FILES:
            return True
        ext = os.path.splitext(filepath)[1].lower()
        if ext in SKIP_EXTENSIONS:
            return True
        try:
            size_kb = os.path.getsize(filepath) / 1024
            if size_kb > MAX_FILE_SIZE_KB:
                return True
        except Exception:
            return True
        return False

    async def _improve_batch(self, filepaths: list):
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
                logger.warning(f"Read error {fp}: {e}")

        if not files_content.strip():
            return

        prompt = f"""You are an expert Python code improver. Refactor the following batch of files.
Rules:
- Improve readability, add type hints, simplify logic.
- Fix obvious bugs. DO NOT add new features.
- Output EXACTLY in this format for each file:
--- FILE: <original_path> ---
<improved code>

Files to improve:
{files_content}
"""
        try:
            response = await asyncio.to_thread(
                self.llm.generate, prompt, max_tokens=8192, temperature=0.1
            )
        except Exception as e:
            logger.error(f"LLM failed: {e}")
            return

        if not response:
            return
        self._parse_and_save(response)

    def _parse_and_save(self, response: str):
        blocks = re.split(r'(?=--- FILE: .+ ---)', response)
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            header_match = re.match(r'--- FILE: (.+) ---', block)
            if not header_match:
                continue
            original_path = header_match.group(1).strip()
            improved_code = block[header_match.end():].strip()
            improved_code = re.sub(r'^```\w*\n', '', improved_code)
            improved_code = re.sub(r'\n```$', '', improved_code)
            if not improved_code:
                continue

            relative_path = os.path.relpath(original_path, start=os.getcwd())
            is_valid_syntax = True
            try:
                ast.parse(improved_code)
            except SyntaxError as e:
                is_valid_syntax = False
                logger.error(f"❌ Syntax Error in mutation for {relative_path}: {e}")
            except Exception as e:
                is_valid_syntax = False
                logger.error(f"❌ Unexpected parsing error for {relative_path}: {e}")

            target_dir = OUTPUT_DIR if is_valid_syntax else FAILED_DIR
            output_path = os.path.join(target_dir, relative_path)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            try:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(improved_code)
                if is_valid_syntax:
                    self.files_improved += 1
                    logger.info(f"✅ Evolution saved and verified: {relative_path}")
                else:
                    logger.warning(f"☣️ Lethal mutation quarantined: {output_path}")
            except Exception as e:
                logger.error(f"Write error {output_path}: {e}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--single-pass", action="store_true")
    args = parser.parse_args()
    node = ImproverAgent(single_pass=args.single_pass)
    try:
        asyncio.run(node.run())
    except KeyboardInterrupt:
        logger.info("ImproverAgent stopped.")