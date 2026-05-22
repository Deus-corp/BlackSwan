from __future__ import annotations

import asyncio
import ast
import json
import logging
import os
import random
import re
import textwrap
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import google.generativeai as genai
except Exception:  # pragma: no cover - optional dependency
    genai = None  # type: ignore[assignment]

from .improver_agent_core.memory import MemoryStore
from .improver_agent_core.models import (
    CritiqueResponse,
    DraftResponse,
    FileItem,
    FilePatchPlan,
    ImprovementResult,
    MemoryHit,
    PatchOperation,
)
from .improver_agent_core.prompting import (
    build_critic_prompt,
    build_json_repair_prompt,
    build_non_python_prompt,
    build_proposals_prompt,
    build_python_prompt,
    safe_json_extract,
)
from .improver_agent_core.validation import (
    atomic_write_text,
    changed_line_ratio,
    extract_python_imports,
    fingerprint_text,
    guess_language,
    run_pytest_smoke,
    safe_output_path,
    validate_result,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("ImproverAgent")

SCAN_DIRS = ["src", "adapters", "sim", "dashboard"]
OUTPUT_DIR = Path("./data/improver_output")
FAILED_DIR = Path("./data/improver_failed")
PROPOSALS_DIR = Path("./data/improver_proposals")
STAGING_DIR = Path("./data/improver_staging")
DEFAULT_MEMORY_DB = Path("./data/improver_memory.sqlite3")

SKIP_EXTENSIONS = {
    ".gguf", ".db", ".jsonl", ".log", ".pyc", ".md", ".txt",
    ".json", ".yml", ".ini", ".jar", ".sqlite3", ".pem", ".key",
    ".sh", ".css", ".js", ".yaml", ".env", ".example",
}
EXCLUDE_DIRS = {
    "__pycache__", ".pytest_cache", ".venv", ".github",
    "assets", "config", "docs", "formal", "grafana", "llama_cpp",
    "logs", "scripts", "site", "tests", "tools",
    "data", ".git", "node_modules", "prometheus_data", "grafana_data",
    "improver_workspace", "improver_output", "improver_failed",
    "improver_proposals", "improver_staging", "improver_memory",
    "ledgers", "meta_agent", "nonce",
}
EXCLUDE_FILES = {"Dockerfile", ".env", ".DS_Store"}
MAX_FILE_SIZE_KB = 200
MAX_FILES_PER_BATCH = 1
SLEEP_BETWEEN_CYCLES = 3600
MAX_CHANGED_LINES_RATIO = 0.35
DEFAULT_MODEL_NAME = "gemini-3.1-flash-lite"
CRITIC_MODEL_NAME = "gemini-3.1-flash-lite"
DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"
DEFAULT_DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


def _line_col_to_index(code: str, line: int, col: int) -> int:
    lines = code.splitlines(keepends=True)
    if line <= 1:
        return min(max(0, col), len(code))
    if line > len(lines):
        return len(code)
    return min(sum(len(lines[i]) for i in range(line - 1)) + col, len(code))


def _replace_source_span(
    code: str,
    start_line: int,
    start_col: int,
    end_line: int,
    end_col: int,
    replacement: str,
) -> str:
    start = _line_col_to_index(code, start_line, start_col)
    end = _line_col_to_index(code, end_line, end_col)
    if end < start:
        return code
    replacement = textwrap.dedent(replacement or "").strip("\n")
    if start_col > 0 and replacement:
        replacement = textwrap.indent(replacement, " " * start_col)
    new_code = code[:start] + replacement + code[end:]
    if code.endswith("\n") and not new_code.endswith("\n"):
        new_code += "\n"
    return new_code


def _python_ast_patch(code: str, patch: PatchOperation) -> Tuple[str, bool, str]:
    """AST-first patching for Python. Used only as a fallback path."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return code, False, f"ast_parse_failed:{e}"

    target = patch.target.strip()
    replacement = patch.new_code or patch.after or ""
    if patch.type != "delete" and not replacement.strip():
        return code, False, "empty_replacement"

    candidates: List[ast.AST] = []
    for node in ast.walk(tree):
        try:
            if patch.type in {"replace_function", "replace_block"} and isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                if node.name == target and hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                    candidates.append(node)
            elif patch.type in {"replace_class", "replace_block"} and isinstance(node, ast.ClassDef):
                if node.name == target and hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                    candidates.append(node)
            elif patch.type == "replace_import" and isinstance(node, (ast.Import, ast.ImportFrom)):
                segment = ast.get_source_segment(code, node) or ""
                aliases = getattr(node, "names", [])
                if (patch.before.strip() and patch.before.strip() in segment) or any(
                    target
                    and (
                        target == getattr(alias, "name", "")
                        or target == getattr(alias, "asname", "")
                        or target in segment
                    )
                    for alias in aliases
                ):
                    candidates.append(node)
        except Exception:
            continue

    if not candidates and patch.type == "replace_block" and patch.before.strip():
        idx = code.find(patch.before)
        if idx != -1:
            return code[:idx] + replacement + code[idx + len(patch.before) :], True, "text_block_fallback"

    if not candidates:
        return code, False, f"target_not_found:{target or patch.type}"

    candidates.sort(key=lambda n: (getattr(n, "lineno", 10**9), getattr(n, "col_offset", 0)))
    node = candidates[0]
    start_line = int(getattr(node, "lineno"))
    start_col = int(getattr(node, "col_offset"))
    end_line = int(getattr(node, "end_lineno", start_line))
    end_col = int(getattr(node, "end_col_offset", 0))

    if patch.type == "delete":
        return _replace_source_span(
            code,
            start_line,
            start_col,
            end_line,
            end_col,
            "",
        ), True, f"ast_deleted:{target or patch.type}"

    new_code = _replace_source_span(code, start_line, start_col, end_line, end_col, replacement)
    if new_code == code:
        return code, False, "ast_noop"
    return new_code, True, f"ast_replaced:{target or patch.type}"


class ImproverAgent:
    def __init__(
        self,
        single_pass: bool = False,
        proposals: bool = False,
        memory_db: Path = DEFAULT_MEMORY_DB,
        enable_validation: bool = True,
        enable_critique: bool = True,
        max_files_per_batch: int = MAX_FILES_PER_BATCH,
        scan_dirs: Optional[Sequence[str]] = None,
        output_dir: Optional[Path] = OUTPUT_DIR,
        failed_dir: Optional[Path] = FAILED_DIR,
        proposals_dir: Optional[Path] = PROPOSALS_DIR,
        staging_dir: Optional[Path] = STAGING_DIR,
        prefer_patch: bool = False,
        workspace_dir: Optional[Path] = None,
    ) -> None:
        self.node_id = f"improver-{uuid.uuid4().hex[:8]}"
        self.single_pass = single_pass
        self.proposals = proposals
        self.enable_validation = enable_validation
        self.enable_critique = enable_critique
        self.max_files_per_batch = max_files_per_batch
        self.prefer_patch = prefer_patch

        self.scan_dirs = list(scan_dirs or SCAN_DIRS)
        self.output_dir = output_dir or OUTPUT_DIR
        self.failed_dir = failed_dir or FAILED_DIR
        self.proposals_dir = proposals_dir or PROPOSALS_DIR
        self.staging_dir = staging_dir or STAGING_DIR
        self.workspace_dir = workspace_dir
        self._using_workspace = False

        self.files_processed = 0
        self.files_improved = 0
        self.files_quarantined = 0
        self.files_failed = 0
        self.batch_pytest_ok: Optional[bool] = None

        self.provider: str = "unknown"
        self.use_gemini = False
        self.use_deepseek = False

        self.gemini_api_keys: List[str] = []
        self.key_index = 0
        self.model_name = DEFAULT_MODEL_NAME
        self.critic_model_name = CRITIC_MODEL_NAME
        self.api_model: Any = None
        self.critic_model: Any = None

        self.deepseek_api_key = ""
        self.deepseek_model = DEFAULT_DEEPSEEK_MODEL
        self.deepseek_api_url = DEFAULT_DEEPSEEK_API_URL

        self.memory = MemoryStore(memory_db)
        self._setup_provider()

    def _setup_provider(self) -> None:
        gemini_keys_str = os.environ.get("GEMINI_API_KEYS", os.environ.get("GEMINI_API_KEY", ""))
        gemini_api_keys = [k.strip() for k in gemini_keys_str.split(",") if k.strip()]
        if gemini_api_keys:
            self.provider = "gemini"
            self.use_gemini = True
            self.gemini_api_keys = gemini_api_keys
            self.key_index = 0
            self.model_name = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL_NAME)
            self.critic_model_name = os.environ.get("GEMINI_CRITIC_MODEL", CRITIC_MODEL_NAME)
            self._configure_next_gemini_key()
            logger.info(
                "🔑 Gemini API keys found: %d keys. Using model %s.",
                len(self.gemini_api_keys),
                self.model_name,
            )
            return

        ds_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if ds_key:
            self.provider = "deepseek"
            self.use_deepseek = True
            self.deepseek_api_key = ds_key
            self.deepseek_model = os.environ.get("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL)
            self.deepseek_api_url = os.environ.get("DEEPSEEK_API_URL", DEFAULT_DEEPSEEK_API_URL)
            logger.info("🔑 DeepSeek API key found. Will use DeepSeek (model=%s).", self.deepseek_model)
            return

        raise ValueError("No Gemini or DeepSeek API keys found.")

    def _configure_next_gemini_key(self) -> None:
        if genai is None:
            raise RuntimeError("google-generativeai is not installed, but Gemini provider was selected.")
        if not self.gemini_api_keys:
            raise RuntimeError("No Gemini API keys configured.")
        key = self.gemini_api_keys[self.key_index % len(self.gemini_api_keys)]
        genai.configure(api_key=key)
        self.api_model = genai.GenerativeModel(self.model_name)
        self.critic_model = genai.GenerativeModel(self.critic_model_name)
        logger.info("🔑 Switched to Gemini API key index %s", self.key_index % len(self.gemini_api_keys))

    def _classify_error(self, err: str) -> str:
        e = err.lower()
        if "401" in e or "403" in e or "permission" in e:
            return "auth"
        if "429" in e or "resource_exhausted" in e or "rate" in e:
            return "rate_limit"
        if "deadline" in e or "timeout" in e or "temporarily unavailable" in e:
            return "transient"
        return "unknown"

    def _extract_retry_delay(self, error_text: str) -> Optional[int]:
        match = re.search(r"retry_delay\s*\{\s*seconds:\s*(\d+)\s*\}", error_text)
        if match:
            return int(match.group(1)) + 5
        match = re.search(r"wait\s+(\d+)s", error_text)
        if match:
            return int(match.group(1)) + 5
        return None

    async def _generate_with_retry(self, prompt: str, critic: bool = False, max_retries: int = 6) -> Optional[str]:
        if self.use_deepseek:
            return await self._generate_deepseek(prompt, critic, max_retries=max_retries)
        return await self._generate_gemini(prompt, critic, max_retries=max_retries)

    async def _generate_gemini(self, prompt: str, critic: bool = False, max_retries: int = 6) -> Optional[str]:
        if self.api_model is None:
            raise RuntimeError("Gemini model is not initialized.")
        model = self.critic_model if critic else self.api_model
        total_keys = max(1, len(self.gemini_api_keys))

        for attempt in range(max_retries * total_keys):
            try:
                response = await asyncio.to_thread(model.generate_content, prompt)
                text = getattr(response, "text", None)
                if text:
                    return text.strip()

                candidates = getattr(response, "candidates", None)
                if candidates:
                    parts: List[str] = []
                    for candidate in candidates:
                        content = getattr(candidate, "content", None)
                        cand_parts = getattr(content, "parts", None) if content else None
                        if cand_parts:
                            for part in cand_parts:
                                part_text = getattr(part, "text", None)
                                if part_text:
                                    parts.append(part_text)
                    if parts:
                        return "\n".join(parts).strip()

                return None
            except Exception as e:
                kind = self._classify_error(str(e))
                if kind == "auth":
                    logger.error("Invalid Gemini API key (index %s), switching.", self.key_index % total_keys)
                    self.key_index += 1
                    self._configure_next_gemini_key()
                    await asyncio.sleep(1)
                    continue
                if kind == "rate_limit":
                    delay = self._extract_retry_delay(str(e)) or min(60 * (attempt + 1), 300)
                    logger.warning(
                        "Gemini rate limited. Switching key and retrying in %ss (attempt %s/%s)",
                        delay,
                        attempt + 1,
                        max_retries * total_keys,
                    )
                    self.key_index += 1
                    self._configure_next_gemini_key()
                    await asyncio.sleep(delay)
                    continue
                logger.error("Gemini API error: %s", e)
                await asyncio.sleep(min(30, 5 * (attempt + 1)))
        return None

    async def _generate_deepseek(self, prompt: str, critic: bool = False, max_retries: int = 6) -> Optional[str]:
        import requests

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.deepseek_api_key}",
        }
        system_prompt = (
            "You are a strict code reviewer. Return ONLY valid JSON."
            if critic
            else "You are a precise code improver. Return ONLY valid JSON."
        )
        payload = {
            "model": self.deepseek_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 16384,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        for attempt in range(max_retries):
            try:
                resp = await asyncio.to_thread(
                    requests.post,
                    self.deepseek_api_url,
                    json=payload,
                    headers=headers,
                    timeout=120,
                )
                if resp.status_code == 429:
                    delay = 30 * (attempt + 1)
                    logger.warning("DeepSeek rate limited, retrying in %ss", delay)
                    await asyncio.sleep(delay)
                    continue
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
            except Exception as e:
                logger.warning("DeepSeek API error: %s", e)
                await asyncio.sleep(10)
        return None

    def _prepare_workspace(self, workspace_dir: Path) -> None:
        import shutil

        workspace_dir.mkdir(parents=True, exist_ok=True)
        copied = 0

        for scan_dir in self.scan_dirs:
            scan_path = Path(scan_dir)
            if not scan_path.exists() or not scan_path.is_dir():
                continue

            scan_label = str(scan_path) if not scan_path.is_absolute() else (scan_path.name or "root")
            for root, dirs, files in os.walk(scan_path):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                for file in files:
                    src = os.path.join(root, file)
                    if self._should_skip(src):
                        continue
                    rel = os.path.relpath(src, scan_path)
                    dst = workspace_dir / scan_label / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    copied += 1

        logger.info("Prepared workspace: copied %s files to %s", copied, workspace_dir)
        self.scan_dirs = [str(workspace_dir)]
        self._using_workspace = True

    async def run(self) -> None:
        logger.info(
            "🔧 Agent %s started (provider=%s, single_pass=%s, proposals=%s, validation=%s, critique=%s)",
            self.node_id,
            self.provider,
            self.single_pass,
            self.proposals,
            self.enable_validation,
            self.enable_critique,
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.failed_dir.mkdir(parents=True, exist_ok=True)
        self.proposals_dir.mkdir(parents=True, exist_ok=True)
        self.staging_dir.mkdir(parents=True, exist_ok=True)

        if self.workspace_dir:
            self._prepare_workspace(self.workspace_dir)

        while True:
            await self._process_all_files()
            logger.info(
                "Cycle done. processed=%s improved=%s quarantined=%s failed=%s",
                self.files_processed,
                self.files_improved,
                self.files_quarantined,
                self.files_failed,
            )
            if self.proposals:
                await self._generate_proposals()
            if self.single_pass:
                break
            logger.info("💤 Sleeping %ss before next cycle …", SLEEP_BETWEEN_CYCLES)
            await asyncio.sleep(SLEEP_BETWEEN_CYCLES)

    def _allowed_changed_lines_ratio(self, result: ImprovementResult) -> float:
        if result.language == "python":
            return 1.0
        if any(p.type == "replace_file" for p in result.patches):
            return 1.0
        return 0.6

    async def _process_all_files(self) -> None:
        config_path = "swarm_config.py"
        if os.path.exists(config_path) and not self._should_skip(config_path):
            await self._improve_batch([config_path])

        batch: List[str] = []
        for scan_dir in self.scan_dirs:
            scan_path = Path(scan_dir)
            if not scan_path.exists():
                continue
            for root, dirs, files in os.walk(scan_path):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                for filename in sorted(files):
                    filepath = os.path.join(root, filename)
                    if self._should_skip(filepath):
                        continue
                    batch.append(filepath)
                    if len(batch) >= self.max_files_per_batch:
                        await self._improve_batch(batch)
                        batch.clear()
        if batch:
            await self._improve_batch(batch)

    def _should_skip(self, filepath: str) -> bool:
        basename = os.path.basename(filepath)
        if basename in EXCLUDE_FILES or basename.startswith("swarm_config"):
            return True
        ext = os.path.splitext(filepath)[1].lower()
        if ext in SKIP_EXTENSIONS:
            return True
        try:
            return os.path.getsize(filepath) / 1024 > MAX_FILE_SIZE_KB
        except Exception:
            return True

    def _read_file(self, fp: str) -> Optional[FileItem]:
        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            if not content.strip():
                return None
            size_kb = max(0.001, os.path.getsize(fp) / 1024)
            language = guess_language(fp)
            imports = extract_python_imports(content) if language == "python" else []
            return FileItem(
                path=str(Path(fp).as_posix()),
                content=content,
                size_kb=size_kb,
                language=language,
                imports=imports,
                fingerprint=fingerprint_text(content),
            )
        except Exception as e:
            logger.warning("Read error %s: %s", fp, e)
            return None

    def _should_skip_by_history(self, item: FileItem) -> bool:
        previous = self.memory.get_file_fingerprint(item.path)
        return previous is not None and previous == item.fingerprint

    def _collect_context(self, file_items: Sequence[FileItem]) -> List[MemoryHit]:
        query_parts: List[str] = []
        for item in file_items:
            query_parts.extend(Path(item.path).parts[-3:])
            query_parts.extend(item.imports[:5])
            query_parts.append(item.language)
        hits = self.memory.search_episodes(" ".join(query_parts), limit=8)
        for pattern in self.memory.get_recent_success_patterns(limit=5):
            hits.append(
                MemoryHit(
                    kind="pattern",
                    score=float(pattern.get("success_count", 0))
                    - float(pattern.get("failure_count", 0))
                    + float(pattern.get("last_score", 0.0)),
                    payload=pattern,
                )
            )
        for pattern in self.memory.get_recent_failure_patterns(limit=5):
            hits.append(
                MemoryHit(
                    kind="failure_pattern",
                    score=float(pattern.get("failure_count", 0)) - float(pattern.get("success_count", 0)),
                    payload=pattern,
                )
            )
        return hits

    def _choose_strategy(self, file_items: Sequence[FileItem]) -> str:
        stats = self.memory.get_strategy_stats()
        strategies = ["default", "typing", "refactor", "bugfix", "optimize", "docstring"]
        weights: List[float] = []
        for strategy in strategies:
            st = stats.get(strategy, {})
            avg_score = float(st.get("avg_score", 0.0))
            total = float(st.get("total", 0.0))
            exploration = 1.0 / (1.0 + total)
            weights.append(max(0.1, avg_score + 1.0 + exploration + random.random() * 0.1))
        return random.choices(strategies, weights=weights, k=1)[0]

    def _python_plan_prompt(self, file_item: FileItem, context_hits: Sequence[MemoryHit], strategy: str) -> str:
        return build_python_prompt(file_item, context_hits, strategy)

    def _non_python_plan_prompt(self, file_item: FileItem, context_hits: Sequence[MemoryHit], strategy: str) -> str:
        return build_non_python_prompt(file_item, context_hits, strategy, prefer_patch=self.prefer_patch)

    def _coerce_str_list(self, value: Any, limit: int = 50) -> List[str]:
        if not isinstance(value, list):
            return []
        out: List[str] = []
        for item in value[:limit]:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                out.append(text)
        return out

    def _normalize_plan(self, raw_payload: Dict[str, Any]) -> DraftResponse:
        files: List[FilePatchPlan] = []
        raw_files = raw_payload.get("files", [])
        if not isinstance(raw_files, list):
            raw_files = []

        for item in raw_files:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path", "") or "").strip()
            if not path:
                continue

            raw_patches = item.get("patches", [])
            patches: List[PatchOperation] = []
            if isinstance(raw_patches, list):
                for p in raw_patches:
                    if not isinstance(p, dict):
                        continue
                    try:
                        patches.append(
                            PatchOperation(
                                type=str(p.get("type", "") or ""),
                                target=str(p.get("target", "") or ""),
                                new_code=str(p.get("new_code", "") or ""),
                                summary=str(p.get("summary", "") or ""),
                                reason=str(p.get("reason", "") or ""),
                                confidence=float(p.get("confidence", 0.0) or 0.0),
                                scope=str(p.get("scope", "") or ""),
                                before=str(p.get("before", "") or ""),
                                after=str(p.get("after", "") or ""),
                            )
                        )
                    except Exception:
                        continue

            full_code = str(item.get("code", item.get("full_code", "")) or "")
            raw_action = str(item.get("action", "") or "").strip().lower()
            if raw_action not in {"patch", "replace_file", "skip"}:
                raw_action = "patch" if patches and not full_code.strip() else "replace_file"

            try:
                risk = float(item.get("risk", 0.0) or 0.0)
            except Exception:
                risk = 0.0

            files.append(
                FilePatchPlan(
                    path=path,
                    action=raw_action,  # type: ignore[arg-type]
                    summary=str(item.get("summary", "") or ""),
                    risk=risk,
                    tags=self._coerce_str_list(item.get("tags", []), limit=25),
                    patches=patches,
                    full_code=full_code,
                    notes=str(item.get("notes", "") or ""),
                )
            )

        try:
            overall_risk = float(raw_payload.get("overall_risk", 0.0) or 0.0)
        except Exception:
            overall_risk = 0.0

        return DraftResponse(
            files=files,
            overall_summary=str(raw_payload.get("overall_summary", "") or ""),
            overall_risk=overall_risk,
            should_repair=bool(raw_payload.get("should_repair", False)),
            critique_notes=str(raw_payload.get("critique_notes", "") or ""),
        )

    def _parse_prompt_payload(self, text: str) -> Optional[Dict[str, Any]]:
        parsed = safe_json_extract(text)
        if isinstance(parsed, dict):
            return parsed
        return None

    async def _draft_for_file(
        self,
        item: FileItem,
        context_hits: Sequence[MemoryHit],
        strategy: str,
    ) -> Optional[DraftResponse]:
        prompt = (
            self._python_plan_prompt(item, context_hits, strategy)
            if item.language == "python"
            else self._non_python_plan_prompt(item, context_hits, strategy)
        )
        text = await self._generate_with_retry(prompt)
        if not text:
            return None

        payload = self._parse_prompt_payload(text)
        if payload is None:
            repair_schema = {
                "files": [
                    {
                        "path": item.path,
                        "code": "",
                        "summary": "",
                        "risk": 0.0,
                        "tags": [],
                    }
                ],
                "overall_summary": "",
                "overall_risk": 0.0,
                "should_repair": False,
                "critique_notes": "",
            }
            repair_prompt = build_json_repair_prompt(text, repair_schema)
            repaired = await self._generate_with_retry(repair_prompt)
            if repaired:
                payload = self._parse_prompt_payload(repaired)

        if payload is None:
            return None

        plan = self._normalize_plan(payload)
        if item.language == "python":
            has_code = any(fp.path == item.path and fp.full_code.strip() for fp in plan.files)
            if not has_code:
                return None
        return plan

    def _normalize_critique(self, raw_payload: Dict[str, Any]) -> CritiqueResponse:
        blocking = raw_payload.get("blocking_issues", [])
        non_blocking = raw_payload.get("non_blocking_suggestions", [])
        if not isinstance(blocking, list):
            blocking = []
        if not isinstance(non_blocking, list):
            non_blocking = []
        try:
            overall_risk = float(raw_payload.get("overall_risk", 0.0) or 0.0)
        except Exception:
            overall_risk = 0.0
        return CritiqueResponse(
            approved=bool(raw_payload.get("approved", False)),
            overall_risk=overall_risk,
            blocking_issues=[str(x) for x in blocking[:20]],
            non_blocking_suggestions=[str(x) for x in non_blocking[:20]],
            preferred_action=str(raw_payload.get("preferred_action", "") or ""),
            critique=str(raw_payload.get("critique", "") or ""),
        )

    async def _criticize_results(
        self,
        file_items: Sequence[FileItem],
        drafted_results: Sequence[ImprovementResult],
        context_hits: Sequence[MemoryHit],
        strategy: str,
    ) -> CritiqueResponse:
        critique_prompt = build_critic_prompt(file_items, drafted_results, context_hits, strategy)
        critique_text = await self._generate_with_retry(critique_prompt, critic=True)
        if not critique_text:
            return CritiqueResponse(approved=False, critique="critic unavailable")

        payload = self._parse_prompt_payload(critique_text)
        if payload is None:
            repair_prompt = build_json_repair_prompt(critique_text, {"approved": False})
            repaired = await self._generate_with_retry(repair_prompt, critic=True)
            if repaired:
                payload = self._parse_prompt_payload(repaired)
        if payload is None:
            return CritiqueResponse(approved=False, critique=critique_text[:1000])
        return self._normalize_critique(payload)

    def _apply_non_python_patch_operation(self, code: str, patch: PatchOperation) -> Tuple[str, bool, str]:
        if patch.type == "replace_file":
            return patch.new_code or code, True, "replace_file"
        if patch.type in {"replace_block", "replace_function", "replace_class"} and patch.before.strip():
            idx = code.find(patch.before)
            if idx == -1:
                return code, False, "target_not_found"
            replacement = patch.new_code.strip()
            if not replacement:
                return code, False, "empty_replacement"
            return code.replace(patch.before, replacement, 1), True, "text_replace"
        if patch.type == "delete" and patch.before.strip():
            if patch.before not in code:
                return code, False, "delete_target_not_found"
            return code.replace(patch.before, "", 1), True, "deleted"
        if patch.type == "replace_import" and patch.before.strip():
            if patch.before not in code:
                return code, False, "import_target_not_found"
            return code.replace(patch.before, patch.after or patch.new_code, 1), True, "import_replaced"
        if patch.type == "insert_before" and patch.before.strip():
            idx = code.find(patch.before)
            if idx == -1:
                return code, False, "insert_before_target_not_found"
            return code[:idx] + (patch.new_code or "") + code[idx:], True, "insert_before"
        if patch.type == "insert_after" and patch.after.strip():
            idx = code.find(patch.after)
            if idx == -1:
                return code, False, "insert_after_target_not_found"
            insert_at = idx + len(patch.after)
            return code[:insert_at] + (patch.new_code or "") + code[insert_at:], True, "insert_after"
        return code, False, f"unsupported_patch_type:{patch.type}"

    def _apply_plan(self, original: FileItem, plan: DraftResponse) -> ImprovementResult:
        file_plan = next((fp for fp in plan.files if fp.path == original.path), None)
        if file_plan is None:
            file_plan = plan.files[0] if plan.files else None
        if file_plan is None:
            return ImprovementResult(
                original_path=original.path,
                proposed_path=original.path,
                code=original.content,
                language=original.language,
                risk=0.0,
                summary="",
                strategy="default",
            )

        current_code = original.content
        applied_any = False
        used_patches: List[PatchOperation] = []

        if original.language == "python":
            full = file_plan.full_code.strip()
            if full:
                current_code = full
                applied_any = True
            else:
                return ImprovementResult(
                    original_path=original.path,
                    proposed_path=original.path,
                    code=original.content,
                    language=original.language,
                    risk=max(0.0, min(1.0, file_plan.risk or plan.overall_risk)),
                    summary=file_plan.summary or plan.overall_summary,
                    memory_tags=self._coerce_str_list(file_plan.tags, limit=25),
                    critique=plan.critique_notes,
                    strategy="default",
                    patches=[],
                    fallback_used=True,
                )
        else:
            if self.prefer_patch and file_plan.patches:
                for patch in file_plan.patches:
                    next_code, ok, _note = self._apply_non_python_patch_operation(current_code, patch)
                    if ok:
                        current_code = next_code
                        applied_any = True
                        used_patches.append(patch)
            if not applied_any and file_plan.full_code.strip():
                current_code = file_plan.full_code
                applied_any = True

        summary = plan.overall_summary or file_plan.summary
        tags = list(dict.fromkeys([str(t) for t in file_plan.tags if t]))
        return ImprovementResult(
            original_path=original.path,
            proposed_path=original.path,
            code=current_code,
            language=original.language,
            risk=max(0.0, min(1.0, file_plan.risk or plan.overall_risk)),
            summary=summary,
            memory_tags=tags,
            critique=plan.critique_notes,
            strategy="default",
            patches=used_patches,
            fallback_used=not applied_any,
        )

    def _score_result(self, result: ImprovementResult) -> float:
        score = 0.0
        if result.validation.syntactically_valid:
            score += 10
        if result.validation.compile_ok:
            score += 10
        if result.validation.ruff_ok is True:
            score += 10
        if result.validation.mypy_ok is True:
            score += 10
        if result.validation.pytest_ok is True:
            score += 25
        score -= result.risk * 25.0
        score -= max(0.0, result.changed_lines_ratio - 0.25) * 30.0
        if result.summary:
            score += min(8.0, len(result.summary) / 40.0)
        if result.memory_tags:
            score += min(5.0, len(result.memory_tags))
        if result.validation.notes:
            score -= min(20.0, len(result.validation.notes) * 3.0)
        if result.fallback_used:
            score -= 5.0
        return round(score, 2)

    def _validate_batch_tests(self) -> Optional[bool]:
        if not self.enable_validation:
            return None
        return run_pytest_smoke(Path.cwd())

    def _validate_and_score(self, original: FileItem, result: ImprovementResult) -> None:
        result.validation = validate_result(
            original,
            result.code,
            enable_validation=self.enable_validation,
            staging_dir=self.staging_dir,
            max_changed_lines_ratio=self._allowed_changed_lines_ratio(result),
        )
        result.validation.pytest_ok = self.batch_pytest_ok
        if self.batch_pytest_ok is False:
            result.validation.notes.append("pytest_failed")
        result.validation.patch_applied_ok = (
            bool(result.patches)
            or result.fallback_used
            or result.code != original.content
        )
        if result.fallback_used:
            result.validation.notes.append("fallback_used")
        result.changed_lines_ratio = changed_line_ratio(original.content, result.code)
        result.score = self._score_result(result)

    def _persist_result(self, original: FileItem, result: ImprovementResult) -> None:
        original_fp = original.fingerprint
        new_fp = fingerprint_text(result.code)

        if new_fp == original_fp:
            result.validation.notes.append("no_change")
            result.validation.syntactically_valid = False
            result.validation.compile_ok = False
            logger.warning("No-op result detected for %s; quarantining as no_change.", original.path)

        success = (
            result.validation.syntactically_valid
            and result.validation.compile_ok
            and result.score >= 12.0
            and "changed_too_much" not in result.validation.notes
            and "no_change" not in result.validation.notes
        )

        target_dir = self.output_dir if success else self.failed_dir
        if success:
            self.files_improved += 1
        else:
            self.files_quarantined += 1

        meta: Dict[str, Any] = {
            "original_path": original.path,
            "proposed_path": result.proposed_path,
            "strategy": result.strategy,
            "risk": result.risk,
            "score": result.score,
            "validation": asdict(result.validation),
            "summary": result.summary,
            "critique": result.critique,
            "tags": result.memory_tags,
            "patches": [
                {
                    "type": patch.type,
                    "target": patch.target,
                    "summary": patch.summary,
                    "reason": patch.reason,
                    "confidence": patch.confidence,
                    "scope": patch.scope,
                }
                for patch in result.patches
            ],
            "original_fingerprint": original_fp,
            "new_fingerprint": new_fp,
            "timestamp": int(time.time()),
            "fallback_used": result.fallback_used,
            "prefer_patch": self.prefer_patch,
        }

        try:
            output_path = safe_output_path(target_dir, result.proposed_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            stage_path = self.staging_dir / f"{Path(result.proposed_path).name}.{int(time.time())}.json"
            atomic_write_text(stage_path, json.dumps(meta, ensure_ascii=False, indent=2))
            atomic_write_text(output_path, result.code)

            if self._using_workspace and success:
                try:
                    ws_root = Path(self.workspace_dir) if self.workspace_dir else None
                    if ws_root is not None:
                        original_path = Path(result.original_path)
                        ws_file = ws_root / original_path if not original_path.is_absolute() else ws_root / original_path.name
                        if not ws_file.exists():
                            ws_file = next(ws_root.rglob(original_path.name), None)
                        if ws_file:
                            ws_file.write_text(result.code, encoding="utf-8")
                            logger.debug("Updated workspace file: %s", ws_file)
                except Exception as ws_err:
                    logger.warning("Failed to update workspace file %s: %s", result.original_path, ws_err)

            logger.info(
                "%s %s (score=%s)",
                "✅ Saved improved file:" if success else "☣️ Quarantined file:",
                result.proposed_path,
                result.score,
            )
        except Exception as e:
            logger.error("Persist error for %s: %s", original.path, e)
            self.files_failed += 1

        self.memory.record_episode(result)
        self.memory.record_file_outcome(original.path, result.score, success, meta=meta)
        self.memory.record_strategy_outcome(result.strategy, result.score, success)

        for tag in result.memory_tags or ["generic"]:
            self.memory.record_pattern(
                pattern_key=f"{result.strategy}:{tag}",
                description=result.summary or tag,
                score=result.score,
                success=success,
                extra={
                    "path": original.path,
                    "risk": result.risk,
                    "validation": asdict(result.validation),
                    "fallback_used": result.fallback_used,
                },
            )

    async def _improve_batch(self, filepaths: List[str]) -> None:
        file_items: List[FileItem] = []
        for fp in filepaths:
            item = self._read_file(fp)
            if item is None:
                continue
            if self._should_skip_by_history(item):
                logger.info("Skipping unchanged file: %s", item.path)
                continue
            file_items.append(item)
            self.files_processed += 1

        if not file_items:
            return

        self.batch_pytest_ok = self._validate_batch_tests()
        strategy = self._choose_strategy(file_items)
        context_hits = self._collect_context(file_items)

        for item in file_items:
            plan = await self._draft_for_file(item, context_hits, strategy)
            if plan is None:
                self.files_failed += 1
                self._save_raw_failure([item], "", reason="no_response")
                continue

            result = self._apply_plan(item, plan)
            result.strategy = strategy
            result.memory_tags = list(dict.fromkeys((result.memory_tags or []) + [strategy, item.language]))
            if self.enable_critique:
                critique = await self._criticize_results([item], [result], context_hits, strategy)
                if critique.critique:
                    result.critique = critique.critique

            self._validate_and_score(item, result)
            self._persist_result(item, result)

    def _save_raw_failure(self, file_items: Sequence[FileItem], raw_text: str, reason: str) -> None:
        ts = int(time.time())
        for item in file_items:
            out = self.failed_dir / f"{Path(item.path).name}.{ts}.{reason}.txt"
            try:
                out.parent.mkdir(parents=True, exist_ok=True)
                atomic_write_text(out, (raw_text or "")[:20_000])
            except Exception as e:
                logger.warning("Could not write raw failure for %s: %s", item.path, e)

    async def _generate_proposals(self) -> None:
        prompt = build_proposals_prompt(
            self.memory.get_recent_success_patterns(limit=10),
            self.memory.get_strategy_stats(),
            self.scan_dirs,
        )
        text = await self._generate_with_retry(prompt)
        if not text:
            logger.warning("Proposals generation returned no text.")
            return

        payload = safe_json_extract(text)
        if not isinstance(payload, dict):
            repair_prompt = build_json_repair_prompt(text, {"proposals": []})
            repaired = await self._generate_with_retry(repair_prompt)
            if repaired:
                payload = safe_json_extract(repaired)

        if not isinstance(payload, dict):
            logger.warning("Failed to parse proposals response as JSON. Raw response saved.")
            ts = int(time.time())
            raw_path = self.proposals_dir / f"raw_proposals_response_{ts}.txt"
            try:
                atomic_write_text(raw_path, text[:20_000])
            except Exception as e:
                logger.warning("Could not save raw proposals response: %s", e)
            return

        ts = int(time.time())
        out = self.proposals_dir / f"proposals_{ts}.json"
        try:
            atomic_write_text(out, json.dumps(payload, ensure_ascii=False, indent=2))
            logger.info("Saved proposals payload to %s", out)
        except Exception as e:
            logger.warning("Could not save proposals payload: %s", e)


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