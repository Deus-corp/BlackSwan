from __future__ import annotations

import asyncio
import ast
import json
import logging
import os
import random
import re
import sys
import textwrap
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
import sys

try:
    import google.generativeai as genai
except Exception:  # pragma: no cover - optional dependency
    genai = None  # type: ignore[assignment]

from src.swarms.common import (
    BaseNodeConfig,
    BaseSwarmNode,
    is_lifecycle_command,
    lifecycle_action,
    lifecycle_applies_to,
    lifecycle_reason,
    lifecycle_summary,
    command_action,
    make_swarm_event,
    utc_ts,
    LIFECYCLE_EVENT_APPLIED,
    lifecycle_event_payload,
)
from swarm_config import config

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
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef),
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
        return _replace_source_span(code, start_line, start_col, end_line, end_col, ""), True, f"ast_deleted:{target or patch.type}"

    new_code = _replace_source_span(code, start_line, start_col, end_line, end_col, replacement)
    if new_code == code:
        return code, False, "ast_noop"
    return new_code, True, f"ast_replaced:{target or patch.type}"


class ImproverAgent(BaseSwarmNode):
    """Managed code-improvement agent.

    This agent is intentionally treated as a specialized maintenance swarm node.
    It keeps its Gemini/DeepSeek improvement workflow, but participates in the
    shared swarm runtime through canonical heartbeats, commands, and events.
    """

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
        node_id: Optional[str] = None,
    ) -> None:
        improver_node_id = node_id or f"improver-{uuid.uuid4().hex[:8]}"

        super().__init__(
            node_config=BaseNodeConfig(
                swarm_type="improver",
                role="maintenance_agent",
                node_id=improver_node_id,
                version="0.2.0",
                tick_interval_seconds=float(SLEEP_BETWEEN_CYCLES),
                heartbeat_interval_seconds=60.0,
                command_poll_interval_seconds=5.0,
                reconcile_interval_seconds=30.0,
                healthcheck_interval_seconds=30.0,
                maintenance_interval_seconds=300.0,
                crdt_db_path=config.crdt_db_path,
            ),
            logger_name="ImproverAgent",
        )

        self.single_pass = single_pass
        self.proposals = proposals
        self.enable_validation = enable_validation
        self.enable_critique = enable_critique
        self.max_files_per_batch = max_files_per_batch
        self.prefer_patch = prefer_patch

        self.scan_dirs = list(SCAN_DIRS if scan_dirs is None else scan_dirs)
        self.output_dir = output_dir or OUTPUT_DIR
        self.failed_dir = failed_dir or FAILED_DIR
        self.proposals_dir = proposals_dir or PROPOSALS_DIR
        self.staging_dir = staging_dir or STAGING_DIR
        self.workspace_dir = workspace_dir
        self._using_workspace = False
        self._workspace_prepared = False

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

        self._paused = False
        self._cycle_lock = asyncio.Lock()
        self._last_cycle_started_at = 0.0
        self._last_cycle_finished_at = 0.0
        self._last_cycle_duration_seconds = 0.0
        self._last_cycle_processed = 0
        self._last_cycle_improved = 0
        self._last_cycle_quarantined = 0
        self._last_cycle_failed = 0
        self._last_cycle_proposals_generated = False
        self._last_error = ""

        self._setup_provider()

    # ------------------------------------------------------------------
    # Shared runtime hooks
    # ------------------------------------------------------------------

    async def on_startup(self) -> None:
        """Prepare filesystem runtime."""
        self._ensure_runtime_dirs()

        if self.workspace_dir and not self._workspace_prepared:
            self._prepare_workspace(self.workspace_dir)
            self._workspace_prepared = True

        logger.info(
            "🔧 ImproverAgent %s started (provider=%s, single_pass=%s, proposals=%s, validation=%s, critique=%s)",
            self.node_id,
            self.provider,
            self.single_pass,
            self.proposals,
            self.enable_validation,
            self.enable_critique,
        )

    async def process_tick(self) -> None:
        """Run one managed improvement cycle."""
        if self._paused:
            return

        await self._process_cycle(trigger="scheduled")

        if self.single_pass:
            self._request_shutdown_compat()

    async def process_command(self, command: Mapping[str, Any]) -> None:
        """Process improver commands from canonical/legacy CRDT command formats."""
        if await self.handle_lifecycle_command(command):
            return

        action = command_action(command)
        payload = command.get("payload") if isinstance(command.get("payload"), Mapping) else {}
        data = command.get("data") if isinstance(command.get("data"), Mapping) else {}
        command_id = str(command.get("gid") or "")

        if action == "PAUSE":
            self._paused = True
            await self._emit_improver_event(
                event_type="command_applied",
                parent_gid=command_id or None,
                payload={"action": action, "status": "paused"},
            )
            logger.info("ImproverAgent %s paused.", self.node_id)
            return

        if action == "RESUME":
            self._paused = False
            await self._emit_improver_event(
                event_type="command_applied",
                parent_gid=command_id or None,
                payload={"action": action, "status": "resumed"},
            )
            logger.info("ImproverAgent %s resumed.", self.node_id)
            return

        if action == "RUN_ONCE":
            await self._process_cycle(trigger="command", parent_gid=command_id or None)
            return

        if action == "GENERATE_PROPOSALS":
            self._ensure_runtime_dirs()
            await self._generate_proposals()
            await self._emit_improver_event(
                event_type="improver_proposals_generated",
                parent_gid=command_id or None,
                payload={"action": action},
            )
            return

        if action == "SET_PROPOSALS":
            value = payload.get("enabled", data.get("enabled", payload.get("value", data.get("value"))))
            self.proposals = self._to_bool(value, default=self.proposals)
            await self._emit_improver_event(
                event_type="command_applied",
                parent_gid=command_id or None,
                payload={"action": action, "proposals": self.proposals},
            )
            return

        if action == "SET_SINGLE_PASS":
            value = payload.get("enabled", data.get("enabled", payload.get("value", data.get("value"))))
            self.single_pass = self._to_bool(value, default=self.single_pass)
            await self._emit_improver_event(
                event_type="command_applied",
                parent_gid=command_id or None,
                payload={"action": action, "single_pass": self.single_pass},
            )
            return

        if action == "RESTART_NODE":
            target_node = (
                command.get("target_node")
                or command.get("target_node_id")
                or payload.get("node_id")
                or data.get("node_id")
            )

            if target_node in {self.node_id, "*", None, ""}:
                await self._emit_improver_event(
                    event_type="command_applied",
                    parent_gid=command_id or None,
                    payload={"action": action, "target_node": target_node},
                )
                logger.critical("Received RESTART_NODE for self. Exiting for orchestrator restart.")
                self._request_shutdown_compat()
                raise SystemExit(0)

    def build_heartbeat(self) -> Dict[str, Any]:
        """Build canonical heartbeat with improver-specific metrics."""
        heartbeat = super().build_heartbeat()
        metrics = heartbeat.setdefault("metrics", {})

        metrics.update(
            {
                "provider": self.provider,
                "model_name": self.model_name if self.use_gemini else self.deepseek_model,
                "critic_model_name": self.critic_model_name if self.use_gemini else self.deepseek_model,
                "single_pass": self.single_pass,
                "proposals": self.proposals,
                "enable_validation": self.enable_validation,
                "enable_critique": self.enable_critique,
                "prefer_patch": self.prefer_patch,
                "paused": self._paused,
                "scan_dirs": list(self.scan_dirs),
                "max_files_per_batch": self.max_files_per_batch,
                "files_processed": self.files_processed,
                "files_improved": self.files_improved,
                "files_quarantined": self.files_quarantined,
                "files_failed": self.files_failed,
                "batch_pytest_ok": self.batch_pytest_ok,
                "last_cycle_started_at": self._last_cycle_started_at,
                "last_cycle_finished_at": self._last_cycle_finished_at,
                "last_cycle_duration_seconds": self._last_cycle_duration_seconds,
                "last_cycle_processed": self._last_cycle_processed,
                "last_cycle_improved": self._last_cycle_improved,
                "last_cycle_quarantined": self._last_cycle_quarantined,
                "last_cycle_failed": self._last_cycle_failed,
                "last_cycle_proposals_generated": self._last_cycle_proposals_generated,
                "last_error": self._last_error,
            }
        )

        return heartbeat

    async def publish_heartbeat(self) -> None:
        """Publish canonical heartbeat plus legacy improver heartbeat."""
        await super().publish_heartbeat()

        legacy = {
            "type": "improver_heartbeat",
            "gid": self._make_gid("improver_hb"),
            "node_id": self.node_id,
            "agent_id": self.node_id,
            "swarm": "improver",
            "role": self.role,
            "status": "paused" if self._paused else self.health.status,
            "timestamp": utc_ts(),
            "provider": self.provider,
            "model_name": self.model_name if self.use_gemini else self.deepseek_model,
            "files_processed": self.files_processed,
            "files_improved": self.files_improved,
            "files_quarantined": self.files_quarantined,
            "files_failed": self.files_failed,
            "provenance": {
                "agent": self.node_id,
                "legacy": True,
            },
        }

        await self.crdt.add_genome(legacy)

    async def healthcheck(self) -> None:
        """Improver-specific healthcheck."""
        await super().healthcheck()

        if self._paused:
            self.health.status = "paused"

        if self._last_error:
            self.health.status = "degraded"
            self.health.last_error = self._last_error

        if self.provider == "unknown":
            self.health.status = "degraded"
            self.health.last_error = "provider is unknown"

    async def on_shutdown(self) -> None:
        logger.info("ImproverAgent %s shutting down.", self.node_id)

    async def run(self) -> None:
        """Backward-compatible run entrypoint."""
        await self.start()

    def _set_runtime_paused(self, paused: bool) -> None:
        """Set paused flag for improver runtime."""
        value = bool(paused)

        for attr in ("paused", "_paused"):
            try:
                setattr(self, attr, value)
            except Exception:
                pass

        health = getattr(self, "health", None)
        if health is not None:
            try:
                setattr(health, "paused", value)
            except Exception:
                pass

        for metrics_attr in ("metrics", "runtime_metrics"):
            metrics = getattr(self, metrics_attr, None)
            if isinstance(metrics, dict):
                metrics["paused"] = value


    def is_paused(self) -> bool:
        """Return current paused state."""
        for attr in ("paused", "_paused"):
            value = getattr(self, attr, None)
            if isinstance(value, bool):
                return value

        health = getattr(self, "health", None)
        if health is not None:
            value = getattr(health, "paused", None)
            if isinstance(value, bool):
                return value

        for metrics_attr in ("metrics", "runtime_metrics"):
            metrics = getattr(self, metrics_attr, None)
            if isinstance(metrics, dict) and isinstance(metrics.get("paused"), bool):
                return bool(metrics["paused"])

        return False
    
    async def _emit_lifecycle_event(
        self,
        *,
        action: str,
        status: str,
        reason: str,
        parent_gid: str,
        command: Mapping[str, Any],
    ) -> None:
        """Emit canonical lifecycle event for improver."""
        event = make_swarm_event(
            event_type=LIFECYCLE_EVENT_APPLIED,
            source_swarm=self.swarm_type,
            source_agent=self.node_id,
            source_node=self.node_id,
            role=self.role,
            parent_gid=parent_gid,
            severity=0.1 if status == "applied" else 0.3,
            payload=lifecycle_event_payload(
                command,
                status=status,
                reason=reason,
            ),
            provenance={
                "agent": self.node_id,
                "source": "common_lifecycle",
            },
        )

        await self.crdt.add_genome(event)

    async def handle_lifecycle_command(self, command: Mapping[str, Any]) -> bool:
        """Handle common lifecycle commands for ImproverAgent.

        RUN_ONCE is safety-gated and handled explicitly.
        Returns True if command was lifecycle command and should not continue
        into legacy/specialized command handling.
        """
        if not is_lifecycle_command(command):
            return False

        node_id = str(getattr(self, "node_id", ""))
        swarm_type = str(getattr(self, "swarm_type", "improver"))
        role = str(getattr(self, "role", "maintenance_agent"))

        if not lifecycle_applies_to(
            command,
            node_id=node_id,
            swarm_type=swarm_type,
            role=role,
        ):
            return True

        action = lifecycle_action(command)
        reason = lifecycle_reason(command)
        command_gid = str(command.get("gid") or "")

        if action == "PAUSE":
            self._set_runtime_paused(True)
            await self._emit_lifecycle_event(
                action=action,
                status="applied",
                reason=reason,
                parent_gid=command_gid,
                command=command,
            )
            self.logger.info("ImproverAgent %s paused by lifecycle command.", self.node_id)
            return True

        if action == "RESUME":
            self._set_runtime_paused(False)
            await self._emit_lifecycle_event(
                action=action,
                status="applied",
                reason=reason,
                parent_gid=command_gid,
                command=command,
            )
            self.logger.info("ImproverAgent %s resumed by lifecycle command.", self.node_id)
            return True

        if action == "RESTART_NODE":
            await self._emit_lifecycle_event(
                action=action,
                status="applied",
                reason=reason,
                parent_gid=command_gid,
                command=command,
            )
            self.logger.critical("ImproverAgent %s received lifecycle RESTART_NODE.", self.node_id)
            sys.exit(0)

        if action == "RUN_ONCE":
            if not self._lifecycle_run_once_allowed(command):
                await self._emit_lifecycle_event(
                    action=action,
                    status="blocked",
                    reason=reason or "RUN_ONCE requires explicit improver safety gate",
                    parent_gid=command_gid,
                    command=command,
                )
                self.logger.warning(
                    "ImproverAgent %s refused RUN_ONCE lifecycle command: explicit safety gate required.",
                    self.node_id,
                )
                return True

            if self.is_paused():
                await self._emit_lifecycle_event(
                    action=action,
                    status="blocked",
                    reason=reason or "improver is paused",
                    parent_gid=command_gid,
                    command=command,
                )
                self.logger.warning("ImproverAgent %s refused RUN_ONCE because it is paused.", self.node_id)
                return True

            await self._process_cycle(
                trigger="lifecycle_run_once",
                parent_gid=command_gid,
            )

            await self._emit_lifecycle_event(
                action=action,
                status="applied",
                reason=reason,
                parent_gid=command_gid,
                command=command,
            )
            return True

        await self._emit_lifecycle_event(
            action=action,
            status="unsupported",
            reason=reason,
            parent_gid=command_gid,
            command=command,
        )
        return True
    
    def _lifecycle_run_once_allowed(self, command: Mapping[str, Any]) -> bool:
        """Return True only when RUN_ONCE has explicit safety approval.

        Accepted forms:
        - payload.explicit_approval == True
        - payload.safety_gate == "approved"
        - payload.allow_api_calls == True only if you want API-enabled cycle
        """
        payload = command.get("payload") if isinstance(command.get("payload"), Mapping) else {}
        data = command.get("data") if isinstance(command.get("data"), Mapping) else {}

        explicit_approval = bool(
            payload.get("explicit_approval")
            or data.get("explicit_approval")
        )

        safety_gate = str(
            payload.get("safety_gate")
            or data.get("safety_gate")
            or ""
        ).lower()

        return explicit_approval or safety_gate in {"approved", "true", "1", "yes"}

    # ------------------------------------------------------------------
    # Provider setup and generation
    # ------------------------------------------------------------------

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
            logger.info("🔑 Gemini API keys found: %d keys. Using model %s.", len(self.gemini_api_keys), self.model_name)
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

    # ------------------------------------------------------------------
    # Managed cycle
    # ------------------------------------------------------------------

    async def _process_cycle(
        self,
        *,
        trigger: str,
        parent_gid: str | None = None,
    ) -> None:
        if self.is_paused():
            self.logger.info(
                "ImproverAgent %s is paused; skipping improvement cycle trigger=%s.",
                self.node_id,
                trigger,
            )
            return
        
        if parent_gid is None:
            parent_gid = self.new_gid("cycle_parent") if hasattr(self, "new_gid") else ""
        
        if self._cycle_lock.locked():
            logger.info("Improver cycle already running; skipping trigger=%s", trigger)
            return

        async with self._cycle_lock:
            self._ensure_runtime_dirs()

            if self.workspace_dir and not self._workspace_prepared:
                self._prepare_workspace(self.workspace_dir)
                self._workspace_prepared = True

            before_processed = self.files_processed
            before_improved = self.files_improved
            before_quarantined = self.files_quarantined
            before_failed = self.files_failed

            self._last_cycle_started_at = utc_ts()
            self._last_cycle_proposals_generated = False

            try:
                await self._process_all_files()

                if self.proposals:
                    await self._generate_proposals()
                    self._last_cycle_proposals_generated = True

                self._last_error = ""

            except Exception as exc:
                self._last_error = str(exc)[:500]
                logger.error("Improver cycle failed: %s", exc, exc_info=True)
                raise

            finally:
                self._last_cycle_finished_at = utc_ts()
                self._last_cycle_duration_seconds = max(0.0, self._last_cycle_finished_at - self._last_cycle_started_at)
                self._last_cycle_processed = self.files_processed - before_processed
                self._last_cycle_improved = self.files_improved - before_improved
                self._last_cycle_quarantined = self.files_quarantined - before_quarantined
                self._last_cycle_failed = self.files_failed - before_failed

                await self._emit_improver_event(
                    event_type="improver_cycle_completed",
                    parent_gid=parent_gid,
                    payload={
                        "trigger": trigger,
                        "duration_seconds": self._last_cycle_duration_seconds,
                        "processed": self._last_cycle_processed,
                        "improved": self._last_cycle_improved,
                        "quarantined": self._last_cycle_quarantined,
                        "failed": self._last_cycle_failed,
                        "proposals_generated": self._last_cycle_proposals_generated,
                        "provider": self.provider,
                        "model_name": self.model_name if self.use_gemini else self.deepseek_model,
                        "last_error": self._last_error,
                    },
                    severity=0.4 if self._last_error else 0.0,
                )

                logger.info(
                    "Cycle done. processed=%s improved=%s quarantined=%s failed=%s",
                    self.files_processed,
                    self.files_improved,
                    self.files_quarantined,
                    self.files_failed,
                )

    async def _emit_improver_event(
        self,
        *,
        event_type: str,
        payload: Mapping[str, Any],
        parent_gid: Optional[str] = None,
        severity: float = 0.0,
    ) -> None:
        event = make_swarm_event(
            event_type=event_type,
            source_swarm="improver",
            source_node=self.node_id,
            source_agent=self.node_id,
            role=self.role,
            parent_gid=parent_gid,
            severity=severity,
            payload=dict(payload),
            provenance={
                "agent": self.node_id,
                "provider": self.provider,
            },
        )
        await self.crdt.add_genome(event)

    def _ensure_runtime_dirs(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.failed_dir.mkdir(parents=True, exist_ok=True)
        self.proposals_dir.mkdir(parents=True, exist_ok=True)
        self.staging_dir.mkdir(parents=True, exist_ok=True)

    def _request_shutdown_compat(self) -> None:
        if hasattr(self, "request_shutdown") and callable(self.request_shutdown):
            self.request_shutdown()
            return
        if hasattr(self, "shutdown_event"):
            self.shutdown_event.set()

    # ------------------------------------------------------------------
    # Original improver implementation
    # ------------------------------------------------------------------

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

    def _allowed_changed_lines_ratio(self, result: ImprovementResult) -> float:
        if result.language == "python":
            return 1.0
        if any(p.type == "replace_file" for p in result.patches):
            return 1.0
        return 0.6

    async def _process_all_files(self) -> None:
        if not self.scan_dirs:
            logger.info("No scan directories configured; skipping improvement cycle.")
            return

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
        return parsed if isinstance(parsed, dict) else None

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

    # ------------------------------------------------------------------
    # Small helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_bool(value: Any, *, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value

        if value is None:
            return default

        if isinstance(value, (int, float)):
            return bool(value)

        if isinstance(value, str):
            cleaned = value.strip().lower()
            if cleaned in {"1", "true", "yes", "y", "on", "enable", "enabled"}:
                return True
            if cleaned in {"0", "false", "no", "n", "off", "disable", "disabled"}:
                return False

        return default

    @staticmethod
    def _make_gid(prefix: str) -> str:
        return f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:8]}"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--single-pass", action="store_true")
    parser.add_argument("--proposals", action="store_true")
    parser.add_argument("--prefer-patch", action="store_true")
    parser.add_argument("--no-validation", action="store_true")
    parser.add_argument("--no-critique", action="store_true")
    args = parser.parse_args()

    node = ImproverAgent(
        single_pass=args.single_pass,
        proposals=args.proposals,
        prefer_patch=args.prefer_patch,
        enable_validation=not args.no_validation,
        enable_critique=not args.no_critique,
    )

    try:
        asyncio.run(node.run())
    except KeyboardInterrupt:
        logger.info("ImproverAgent stopped.")
    except SystemExit as exc:
        logger.info("ImproverAgent stopped gracefully: %s", exc)
    except Exception as exc:
        logger.critical("ImproverAgent fatal error: %s", exc, exc_info=True)
        raise