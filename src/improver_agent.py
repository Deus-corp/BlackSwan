#!/usr/bin/env python3
"""
Improver Agent – автономный улучшатель кода с поддержкой ротации ключей Gemini и генерацией предложений.
"""
import asyncio, logging, os, re, uuid, ast, time, json
from typing import List, Optional

import google.generativeai as genai

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s')
logger = logging.getLogger("ImproverAgent")

SCAN_DIRS = ["mvp/lab_swarm_demo", "src", "adapters", "sim", "dashboard"]
OUTPUT_DIR = "./data/improver_output"
FAILED_DIR = "./data/improver_failed"
PROPOSALS_DIR = "./data/improver_proposals"

SKIP_EXTENSIONS = {".gguf", ".db", ".jsonl", ".log", ".pyc", ".md", ".txt",
                   ".json", ".yml", ".ini", ".jar", ".sqlite3", ".pem", ".key",
                   ".sh", ".css", ".js", ".yaml", ".env", ".example"}
EXCLUDE_DIRS = {"__pycache__", ".pytest_cache", ".venv", ".github",
                "assets", "config", "docs", "formal", "grafana", "llama_cpp",
                "logs", "scripts", "site", "tests", "tools",
                "data", ".git", "node_modules", "prometheus_data", "grafana_data"}
EXCLUDE_FILES = {"Dockerfile", "=20.0"}
MAX_FILE_SIZE_KB = 200
MAX_FILES_PER_BATCH = 3
SLEEP_BETWEEN_CYCLES = 3600


class ImproverAgent:
    def __init__(self, single_pass: bool = False, proposals: bool = False):
        self.node_id = f"improver-{uuid.uuid4().hex[:8]}"
        self.single_pass = single_pass
        self.proposals = proposals
        self.files_processed = 0
        self.files_improved = 0

        # Ротация ключей Gemini
        keys_str = os.environ.get("GEMINI_API_KEYS", os.environ.get("GEMINI_API_KEY", ""))
        self.api_keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        if not self.api_keys:
            raise ValueError("No Gemini API keys found. Set GEMINI_API_KEYS or GEMINI_API_KEY in .env")
        self.key_index = 0
        self._configure_next_key()

    def _configure_next_key(self):
        """Переключает API-ключ на следующий из списка."""
        if self.api_keys:
            key = self.api_keys[self.key_index % len(self.api_keys)]
            genai.configure(api_key=key)
            self.api_model = genai.GenerativeModel('gemini-2.5-flash')
            logger.info(f"🔑 Switched to API key index {self.key_index % len(self.api_keys)}")

    async def _generate_with_retry(self, prompt: str, max_retries: int = 5) -> Optional[str]:
        """Вызывает Gemini с автоматическим retry при 429 и ротацией ключей."""
        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(self.api_model.generate_content, prompt)
                return response.text
            except Exception as e:
                if "429" in str(e):
                    # Извлекаем retry_delay из сообщения
                    delay = 60  # по умолчанию ждём минуту
                    match = re.search(r'retry_delay\s*\{\s*seconds:\s*(\d+)\s*\}', str(e))
                    if match:
                        delay = int(match.group(1)) + 5
                    logger.warning(f"Rate limited. Switching key and retrying in {delay}s (attempt {attempt+1})")
                    self.key_index += 1
                    self._configure_next_key()
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Gemini API error: {e}")
                    return None
        logger.error("All retries exhausted for Gemini request")
        return None

    async def run(self):
        logger.info(f"🔧 Agent {self.node_id} started (single_pass={self.single_pass}, proposals={self.proposals})")
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        os.makedirs(FAILED_DIR, exist_ok=True)
        os.makedirs(PROPOSALS_DIR, exist_ok=True)

        while True:
            await self._process_all_files()
            logger.info(f"Cycle done. Processed: {self.files_processed}, improved: {self.files_improved}")
            if self.proposals:
                await self._generate_proposals()
            if self.single_pass:
                break
            logger.info(f"💤 Sleeping {SLEEP_BETWEEN_CYCLES}s before next cycle …")
            await asyncio.sleep(SLEEP_BETWEEN_CYCLES)

    async def _process_all_files(self):
        batch = []
        for scan_dir in SCAN_DIRS:
            if not os.path.exists(scan_dir):
                continue
            for root, dirs, files in os.walk(scan_dir):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                for filename in sorted(files):
                    filepath = os.path.join(root, filename)
                    if self._should_skip(filepath):
                        continue
                    batch.append(filepath)
                    if len(batch) >= MAX_FILES_PER_BATCH:
                        await self._improve_batch(batch)
                        batch.clear()
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

    async def _improve_batch(self, filepaths: List[str]):
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

        prompt = f"""You are an expert Python code improver. For each file, output an IMPROVED version that preserves ALL functionality. Add type hints, docstrings, fix bugs. Separate files with '--- FILE: <path> ---'.

Files:
{files_content}
"""
        text = await self._generate_with_retry(prompt)
        if text:
            self._parse_and_save(text)

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
            is_valid = True
            try:
                ast.parse(improved_code)
            except SyntaxError as e:
                is_valid = False
                logger.error(f"❌ Syntax error for {original_path}: {e}")
            except Exception as e:
                is_valid = False
                logger.error(f"❌ Parse error for {original_path}: {e}")

            target_dir = OUTPUT_DIR if is_valid else FAILED_DIR
            output_path = os.path.join(target_dir, original_path)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            try:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(improved_code)
                if is_valid:
                    self.files_improved += 1
                    logger.info(f"✅ Mutation saved: {original_path}")
                else:
                    logger.warning(f"☣️ Quarantined: {output_path}")
            except Exception as e:
                logger.error(f"Write error {output_path}: {e}")

    async def _generate_proposals(self):
        """Генерирует идеи новых модулей и сохраняет их в PROPOSALS_DIR."""
        prompt = f"""Analyze the BlackSwan trading swarm project (directories: mvp/lab_swarm_demo, src, adapters, sim, dashboard).
Suggest 2-3 new Python modules or subfolders that could improve the system (e.g., new risk metrics, new strategies, new monitoring tools).
Return ONLY a raw JSON array (no markdown, no ```json) like:
[{{"path": "src/new_module.py", "description": "...", "code_skeleton": "..."}}]
"""
        text = await self._generate_with_retry(prompt)
        if text:
            # Очищаем ответ от всего, что не JSON
            text = text.strip()
            text = re.sub(r'```(?:json)?\s*', '', text)
            start = text.find('[')
            end = text.rfind(']')
            if start != -1 and end != -1 and end > start:
                text = text[start:end+1]
            try:
                proposals = json.loads(text)
                if isinstance(proposals, list):
                    for i, prop in enumerate(proposals):
                        fname = f"proposal_{int(time.time())}_{i}.json"
                        with open(os.path.join(PROPOSALS_DIR, fname), 'w') as f:
                            json.dump(prop, f, indent=2)
                        logger.info(f"💡 Proposal saved: {fname}")
            except Exception as e:
                logger.warning(f"Failed to parse proposals: {e}")
                logger.info(f"Raw proposals response: {text[:500]}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--single-pass", action="store_true")
    parser.add_argument("--proposals", action="store_true")
    args = parser.parse_args()
    node = ImproverAgent(single_pass=args.single_pass, proposals=args.proposals)
    try:
        asyncio.run(node.run())
    except KeyboardInterrupt:
        logger.info("ImproverAgent stopped.")