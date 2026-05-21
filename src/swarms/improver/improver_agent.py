from __future__ import annotations

import asyncio
import ast
import dataclasses
import json
import logging
import os
import random
import re
import subprocess
import textwrap
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import google.generativeai as genai
import requests

from src.swarms.improver.memory import MemoryStore
from src.swarms.improver.models import (
    CritiqueResponse,
    DraftResponse,
    FileItem,
    FilePatchPlan,
    ImprovementResult,
    MemoryHit,
    PatchOperation,
)
from src.swarms.improver.prompting import (
    build_critic_prompt,
    build_json_repair_prompt,
    build_patch_prompt,
    build_proposals_prompt,
    build_prompt,
    safe_json_extract,
)
from src.swarms.improver.validation import (
    atomic_write_text,
    changed_line_ratio,
    command_exists,
    extract_python_imports,
    fingerprint_text,
    guess_language,
    run_pytest_smoke,
    safe_output_path,
    validate_patch_manifest,
    validate_result,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("ImproverAgent")


SCAN_DIRS = ["src", "adapters", "sim", "dashboard", "."]
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
}
EXCLUDE_FILES = {"Dockerfile", ".env"}
MAX_FILE_SIZE_KB = 200
MAX_FILES_PER_BATCH = 3
SLEEP_BETWEEN_CYCLES = 3600
MAX_PROMPT_CHARS = 24_000
MAX_CHANGED_LINES_RATIO = 0.35
DEFAULT_MODEL_NAME = "gemini-2.5-flash"
CRITIC_MODEL_NAME = "gemini-2.5-flash"


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
    """
    AST-first patcher for Python files.

    Supports precise replacement of functions, classes, imports, and fallback
    block replacements when the AST target can be inferred.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return code, False, f"ast_parse_failed:{e}"

    target = patch.target.strip()
    replacement = patch.new_code or patch.after or ""
    if not replacement.strip() and patch.type != "delete":
        return code, False, "empty_replacement"

    candidates: List[ast.AST] = []

    for node in ast.walk(tree):
        try:
            if patch.type in {"replace_function", "replace_block"} and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == target and hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                    candidates.append(node)
            elif patch.type in {"replace_class", "replace_block"} and isinstance(node, ast.ClassDef):
                if node.name == target and hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                    candidates.append(node)
            elif patch.type == "replace_import" and isinstance(node, (ast.Import, ast.ImportFrom)):
                segment = ast.get_source_segment(code, node) or ""
                if patch.before.strip() and patch.before.strip() in segment:
                    candidates.append(node)
                else:
                    aliases = getattr(node, "names", [])
                    if target and (
                        target in segment
                        or any(getattr(alias, "name", "") == target or getattr(alias, "asname", "") == target for alias in aliases)
                    ):
                        candidates.append(node)
        except Exception:
            continue

    if not candidates and patch.type == "replace_block" and patch.before.strip():
        # block fallback: replace exact text if the AST target is not inferable
        idx = code.find(patch.before)
        if idx != -1:
            return code[:idx] + replacement + code[idx + len(patch.before):], True, "text_block_fallback"

    if not candidates:
        return code, False, f"target_not_found:{target or patch.type}"

    # Prefer earliest occurrence in source order.
    candidates.sort(key=lambda n: (getattr(n, "lineno", 10**9), getattr(n, "col_offset", 0)))
    node = candidates[0]
    start_line = int(getattr(node, "lineno"))
    start_col = int(getattr(node, "col_offset"))
    end_line = int(getattr(node, "end_lineno", start_line))
    end_col = int(getattr(node, "end_col_offset", 0))

    if patch.type == "delete":
        return _replace_source_span(code, start_line, start_col, end_line, end_col, ""), True, f"ast_deleted:{target or patch.type}"

    new_code = _replace_source_span(code, start_line, start_col, end_line, end_col, replacement)
    if new_code == code:
        return code, False, "ast_noop"
    return new_code, True, f"ast_replaced:{target or patch.type}"


DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MISTRAL_MODEL = "mistral-large-latest"
DEFAULT_MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"


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
        prefer_patch: bool = True,
        patch_only_python: bool = True,
        allow_full_rewrite_python: bool = False,
    ) -> None:
        self.node_id = f"improver-{uuid.uuid4().hex[:8]}"
        self.single_pass = single_pass
        self.proposals = proposals
        self.enable_validation = enable_validation
        self.enable_critique = enable_critique
        self.max_files_per_batch = max_files_per_batch
        self.prefer_patch = prefer_patch
        self.patch_only_python = patch_only_python
        self.allow_full_rewrite_python = allow_full_rewrite_python

        self.scan_dirs = list(scan_dirs or SCAN_DIRS)
        self.output_dir = output_dir or OUTPUT_DIR
        self.failed_dir = failed_dir or FAILED_DIR
        self.proposals_dir = proposals_dir or PROPOSALS_DIR
        self.staging_dir = staging_dir or STAGING_DIR

        self.files_processed = 0
        self.files_improved = 0
        self.files_quarantined = 0
        self.files_failed = 0
        self.batch_pytest_ok: Optional[bool] = None

        self.use_mistral = False
        self.use_groq = False
        self.use_gemini = False

        self.provider_name = "auto"
        self.memory = MemoryStore(memory_db)

        self._setup_provider()

    def _setup_provider(self) -> None:
        mistral_api_key = os.environ.get("MISTRAL_API_KEY", "")
        groq_api_key = os.environ.get("GROQ_API_KEY2") or os.environ.get("GROQ_API_KEY", "")

        if mistral_api_key:
            self.use_mistral = True
            self.mistral_api_key = mistral_api_key
            self.mistral_api_url = os.environ.get("MISTRAL_API_URL", DEFAULT_MISTRAL_API_URL)
            self.mistral_model = os.environ.get("MISTRAL_MODEL", DEFAULT_MISTRAL_MODEL)
            self.mistral_critic_model = os.environ.get("MISTRAL_CRITIC_MODEL", self.mistral_model)
            logger.info("🔑 Mistral API key found. Will use Mistral (model=%s).", self.mistral_model)
            return

        if groq_api_key:
            self.use_groq = True
            self.groq_api_key = groq_api_key
            self.groq_api_url = os.environ.get("GROQ_API_URL", DEFAULT_GROQ_API_URL)
            self.groq_model = os.environ.get("GROQ_MODEL", DEFAULT_GROQ_MODEL)
            self.groq_critic_model = os.environ.get("GROQ_CRITIC_MODEL", self.groq_model)
            logger.info("🔑 Groq API key found. Will use Groq (model=%s).", self.groq_model)
            return

        keys_str = os.environ.get("GEMINI_API_KEYS", os.environ.get("GEMINI_API_KEY", ""))
        self.gemini_api_keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        if not self.gemini_api_keys:
            raise ValueError("No Mistral/Groq/Gemini keys found. Set MISTRAL_API_KEY, GROQ_API_KEY, or GEMINI_API_KEYS.")
        self.use_gemini = True
        self.key_index = 0
        self.model_name = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL_NAME)
        self.critic_model_name = os.environ.get("GEMINI_CRITIC_MODEL", CRITIC_MODEL_NAME)
        self._configure_next_gemini_key()
        logger.info("🔑 Falling back to Gemini (model=%s).", self.model_name)

    def _configure_next_gemini_key(self) -> None:
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
        if self.use_mistral:
            return await self._generate_mistral(prompt, critic, max_retries=max_retries)
        if self.use_groq:
            return await self._generate_groq(prompt, critic, max_retries=max_retries)
        return await self._generate_gemini(prompt, critic, max_retries=max_retries)

    async def _generate_groq(self, prompt: str, critic: bool = False, max_retries: int = 5) -> Optional[str]:
        model = self.groq_critic_model if critic else self.groq_model
        for attempt in range(max_retries):
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.groq_api_key}",
                }
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You are a precise code improver. Return ONLY valid JSON."},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 4096,
                    "temperature": 0.2,
                }
                response = await asyncio.to_thread(requests.post, self.groq_api_url, json=payload, headers=headers, timeout=90)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
            except Exception as e:
                err = str(e)
                delay = 60 if ("429" in err or "rate" in err.lower()) else min(10 * (attempt + 1), 30)
                logger.warning("Groq API error: %s (retry in %ss)", e, delay)
                await asyncio.sleep(delay)
        return None

    async def _generate_mistral(self, prompt: str, critic: bool = False, max_retries: int = 6) -> Optional[str]:
        model = self.mistral_critic_model if critic else self.mistral_model
        for attempt in range(max_retries):
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.mistral_api_key}",
                }
                payload = {
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a precise code improver. Return ONLY valid JSON matching the schema. "
                                "No markdown, no commentary, no code fences."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 16384,
                    "temperature": 0.15,
                }
                response = await asyncio.to_thread(requests.post, self.mistral_api_url, json=payload, headers=headers, timeout=120)
                if response.status_code == 429:
                    delay = 20 + 10 * attempt
                    logger.warning("Mistral rate limited, retrying in %ss", delay)
                    await asyncio.sleep(delay)
                    continue
                if response.status_code >= 500:
                    delay = 10 + 5 * attempt
                    logger.warning("Mistral server error (%s), retrying in %ss", response.status_code, delay)
                    await asyncio.sleep(delay)
                    continue
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
            except requests.exceptions.Timeout:
                logger.warning("Mistral timeout, retrying (%s/%s)", attempt + 1, max_retries)
                await asyncio.sleep(10)
            except Exception as e:
                logger.warning("Mistral API error: %s", e)
                await asyncio.sleep(min(15, 5 * (attempt + 1)))
        return None

    async def _generate_gemini(self, prompt: str, critic: bool = False, max_retries: int = 6) -> Optional[str]:
        model = self.critic_model if critic else self.api_model
        total_keys = max(1, len(self.gemini_api_keys))
        for attempt in range(max_retries * total_keys):
            try:
                response = await asyncio.to_thread(model.generate_content, prompt)
                return getattr(response, "text", None)
            except Exception as e:
                err = str(e)
                kind = self._classify_error(err)
                if kind == "auth":
                    logger.error("Invalid Gemini API key (index %s), switching.", self.key_index % total_keys)
                    self.key_index += 1
                    self._configure_next_gemini_key()
                    await asyncio.sleep(1)
                    continue
                if kind == "rate_limit":
                    delay = self._extract_retry_delay(err) or min(60 * (attempt + 1), 300)
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

    async def run(self) -> None:
        logger.info(
            "🔧 Agent %s started (single_pass=%s, proposals=%s, validation=%s, critique=%s, patch_first=%s)",
            self.node_id,
            self.single_pass,
            self.proposals,
            self.enable_validation,
            self.enable_critique,
            self.prefer_patch,
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.failed_dir.mkdir(parents=True, exist_ok=True)
        self.proposals_dir.mkdir(parents=True, exist_ok=True)
        self.staging_dir.mkdir(parents=True, exist_ok=True)

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

    async def _process_all_files(self) -> None:
        batch: List[str] = []
        for scan_dir in self.scan_dirs:
            if not os.path.exists(scan_dir):
                continue
            for root, dirs, files in os.walk(scan_dir):
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
        if basename in EXCLUDE_FILES:
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

        query = " ".join(query_parts)
        hits = self.memory.search_episodes(query, limit=8)

        for pattern in self.memory.get_recent_success_patterns(limit=5):
            hits.append(
                MemoryHit(
                    kind="pattern",
                    score=float(pattern.get("success_count", 0)) - float(pattern.get("failure_count", 0)) + float(pattern.get("last_score", 0.0)),
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

    def _normalize_plan(self, raw_payload: Dict[str, Any]) -> DraftResponse:
        files: List[FilePatchPlan] = []
        raw_files = raw_payload.get("files", [])
        if not isinstance(raw_files, list):
            raw_files = []

        for item in raw_files:
            if not isinstance(item, dict):
                continue
            patches, patch_notes = validate_patch_manifest(item)
            patch_plans = patches if patches else []

            path = str(item.get("path", "") or "")
            action = str(item.get("action", "patch") or "patch")
            summary = str(item.get("summary", "") or "")
            notes = str(item.get("notes", "") or "")

            full_code = str(item.get("full_code", "") or "")
            if path.endswith(".py") and self.patch_only_python and not self.allow_full_rewrite_python:
                full_code = ""
            risk = float(item.get("risk", 0.0) or 0.0)
            tags = item.get("tags", []) if isinstance(item.get("tags", []), list) else []

            if not path:
                continue

            files.append(
                FilePatchPlan(
                    path=path,
                    action=action if action in {"patch", "replace_file", "skip"} else "patch",
                    summary=summary,
                    risk=max(0.0, min(1.0, risk)),
                    tags=[str(t) for t in tags[:12]],
                    patches=patch_plans,
                    full_code=full_code,
                    notes="; ".join([notes] + patch_notes).strip("; "),
                )
            )

        return DraftResponse(
            files=files,
            overall_summary=str(raw_payload.get("overall_summary", "") or ""),
            overall_risk=float(raw_payload.get("overall_risk", 0.0) or 0.0),
            should_repair=bool(raw_payload.get("should_repair", False)),
            critique_notes=str(raw_payload.get("critique_notes", "") or ""),
        )

    def _normalize_critique(self, raw_payload: Dict[str, Any]) -> CritiqueResponse:
        blocking = raw_payload.get("blocking_issues", [])
        non_blocking = raw_payload.get("non_blocking_suggestions", [])
        if not isinstance(blocking, list):
            blocking = []
        if not isinstance(non_blocking, list):
            non_blocking = []
        return CritiqueResponse(
            approved=bool(raw_payload.get("approved", False)),
            overall_risk=float(raw_payload.get("overall_risk", 0.0) or 0.0),
            blocking_issues=[str(x) for x in blocking[:20]],
            non_blocking_suggestions=[str(x) for x in non_blocking[:20]],
            preferred_action=str(raw_payload.get("preferred_action", "") or ""),
            critique=str(raw_payload.get("critique", "") or ""),
        )

    def _parse_prompt_payload(self, text: str) -> Optional[Dict[str, Any]]:
        parsed = safe_json_extract(text)
        if isinstance(parsed, dict):
            return parsed
        return None

    def _build_issue_summary(self, item: FileItem, context_hits: Sequence[MemoryHit], strategy: str) -> str:
        bits = [f"path={item.path}", f"language={item.language}", f"strategy={strategy}"]
        if item.imports:
            bits.append("imports=" + ",".join(item.imports[:10]))
        if context_hits:
            top = context_hits[:3]
            bits.append("memory=" + "; ".join(f"{h.kind}:{h.score:.2f}" for h in top))
        return " | ".join(bits)

    async def _draft_for_file(self, item: FileItem, context_hits: Sequence[MemoryHit], strategy: str) -> Optional[DraftResponse]:
        issue_summary = self._build_issue_summary(item, context_hits, strategy)
        prompt = build_patch_prompt(
            item,
            context_hits,
            strategy,
            issue_summary,
            patch_only=item.language == "python" and self.patch_only_python,
        )
        text = await self._generate_with_retry(prompt)
        if not text:
            return None

        payload = self._parse_prompt_payload(text)
        if payload is None:
            repair_prompt = build_json_repair_prompt(text, {"files": [{"path": "path/to/file.py", "action": "patch", "patches": []}]})
            repaired = await self._generate_with_retry(repair_prompt)
            if repaired:
                payload = self._parse_prompt_payload(repaired)
        if payload is None:
            return None
        return self._normalize_plan(payload)

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

    def _apply_patch_operation(self, original: FileItem, code: str, patch: PatchOperation) -> Tuple[str, bool, str]:
        if patch.type == "replace_file":
            return patch.new_code or code, True, "replace_file"

        # AST-first for Python files and node-shaped patch types.
        if original.language == "python" and patch.type in {"replace_function", "replace_class", "replace_block", "replace_import", "delete"}:
            patched_code, ok, note = _python_ast_patch(code, patch)
            if ok:
                return patched_code, True, note
            # If AST targeting failed, continue to conservative text fallback.
            if patch.type in {"replace_function", "replace_class", "replace_block"} and patch.before.strip():
                idx = code.find(patch.before)
                if idx != -1 and patch.new_code.strip():
                    return code[:idx] + patch.new_code + code[idx + len(patch.before):], True, "text_before_fallback"

        if patch.type == "replace_import":
            lines = code.splitlines()
            new_lines: List[str] = []
            replaced = False
            for line in lines:
                if patch.before and patch.before.strip() in line:
                    if patch.after.strip():
                        new_lines.append(patch.after)
                    replaced = True
                else:
                    new_lines.append(line)
            if not replaced and patch.new_code.strip():
                new_lines.insert(0, patch.new_code.strip())
                replaced = True
            return "\n".join(new_lines) + ("\n" if code.endswith("\n") else ""), replaced, "replace_import"

        if patch.type in {"replace_function", "replace_class", "replace_block"}:
            target = patch.target.strip()
            if not target:
                return code, False, "empty_target"

            pattern = re.compile(
                rf"(^[ \t]*(?:async\s+def|def|class)\s+{re.escape(target)}\b[\s\S]*?)(?=^[ \t]*(?:async\s+def|def|class)\s+\w+\b|\Z)",
                re.MULTILINE,
            )
            if patch.before.strip():
                pattern = re.compile(re.escape(patch.before), re.MULTILINE | re.DOTALL)

            match = pattern.search(code)
            if not match:
                return code, False, f"target_not_found:{target}"
            replacement = patch.new_code.strip()
            if not replacement:
                return code, False, "empty_replacement"
            new_code = code[: match.start()] + replacement + code[match.end() :]
            return new_code, True, f"replaced:{target}"

        if patch.type == "insert_before" and patch.before.strip():
            idx = code.find(patch.before)
            if idx == -1:
                return code, False, "before_not_found"
            return code[:idx] + patch.new_code + "\n" + code[idx:], True, "insert_before"

        if patch.type == "insert_after" and patch.after.strip():
            idx = code.find(patch.after)
            if idx == -1:
                return code, False, "after_not_found"
            end = idx + len(patch.after)
            return code[:end] + "\n" + patch.new_code + code[end:], True, "insert_after"

        if patch.type == "delete" and patch.before.strip():
            idx = code.find(patch.before)
            if idx == -1:
                return code, False, "delete_target_not_found"
            return code.replace(patch.before, "", 1), True, "delete"

        return code, False, f"unsupported_patch_type:{patch.type}"

    def _apply_plan(self, original: FileItem, plan: DraftResponse) -> ImprovementResult:
        current_code = original.content
        applied_any = False
        used_patches: List[PatchOperation] = []

        for file_plan in plan.files:
            if file_plan.path != original.path:
                continue
            if file_plan.action == "skip":
                break

            if file_plan.action == "replace_file" and file_plan.full_code.strip():
                current_code = file_plan.full_code
                applied_any = True
                used_patches.extend(file_plan.patches)
                break

            for patch in file_plan.patches:
                next_code, ok, _note = self._apply_patch_operation(original, current_code, patch)
                if ok:
                    current_code = next_code
                    applied_any = True
                    used_patches.append(patch)

            if (
                not applied_any
                and file_plan.full_code.strip()
                and (original.language != "python" or self.allow_full_rewrite_python)
            ):
                current_code = file_plan.full_code
                applied_any = True
                break

        summary = plan.overall_summary or (plan.files[0].summary if plan.files else "")
        tags: List[str] = []
        for file_plan in plan.files:
            tags.extend(file_plan.tags)
        tags = list(dict.fromkeys([t for t in tags if t]))

        return ImprovementResult(
            original_path=original.path,
            proposed_path=original.path,
            code=current_code,
            language=original.language,
            risk=max((p.risk for p in plan.files), default=plan.overall_risk),
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
            max_changed_lines_ratio=MAX_CHANGED_LINES_RATIO,
        )
        result.validation.pytest_ok = self.batch_pytest_ok
        if self.batch_pytest_ok is False:
            result.validation.notes.append("pytest_failed")
        result.validation.patch_applied_ok = bool(result.patches) or result.fallback_used
        if result.fallback_used:
            result.validation.notes.append("fallback_used")
        result.changed_lines_ratio = changed_line_ratio(original.content, result.code)
        result.score = self._score_result(result)

    def _persist_result(self, original: FileItem, result: ImprovementResult) -> None:
        success = (
            result.validation.syntactically_valid
            and result.validation.compile_ok
            and result.score >= 15.0
            and ("changed_too_much" not in result.validation.notes)
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
            "original_fingerprint": original.fingerprint,
            "new_fingerprint": fingerprint_text(result.code),
            "timestamp": int(time.time()),
            "fallback_used": result.fallback_used,
            "patch_only_python": self.patch_only_python,
            "allow_full_rewrite_python": self.allow_full_rewrite_python,
        }

        try:
            output_path = safe_output_path(target_dir, result.proposed_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            stage_path = self.staging_dir / f"{Path(result.proposed_path).name}.{int(time.time())}.json"
            atomic_write_text(stage_path, json.dumps(meta, ensure_ascii=False, indent=2))
            atomic_write_text(output_path, result.code)

            logger.info(
                "%s %s (score=%s)",
                "✅ Saved improved file:" if success else "☣️ Quarantined file:",
                result.proposed_path,
                result.score,
            )
        except Exception as e:
            logger.error("Persist error for %s: %s", original.path, e)
            self.files_failed += 1
            meta = {"error": str(e), "original_path": original.path}

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
            result.memory_tags = list(dict.fromkeys((result.memory_tags or []) + [strategy, item.language, "patch_first"]))

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
