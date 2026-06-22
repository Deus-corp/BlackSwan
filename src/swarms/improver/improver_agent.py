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
import difflib
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
    normalize_command,
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
    run_pytest_smoke_with_diagnostics,
    run_pytest_paths_with_diagnostics,
    safe_output_path,
    validate_result,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("ImproverAgent")

SCAN_DIRS = ["src", "adapters", "sim", "dashboard"]
OUTPUT_DIR = Path("./data/improver_output")
FAILED_DIR = Path("./data/improver_failed")
PROPOSALS_DIR = Path("./data/improver_proposals")
RESEARCH_DIR = Path("./data/improver_research")
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
        max_cycles: Optional[int] = None,
        max_rate_limit_attempts: int = 48,
        max_llm_attempts: int = 48,
        llm_request_timeout: float = 180.0,
        proposals: bool = False,
        memory_db: Path = DEFAULT_MEMORY_DB,
        enable_validation: bool = True,
        enable_critique: bool = True,
        max_files_per_batch: int = MAX_FILES_PER_BATCH,
        max_files_total: Optional[int] = None,
        scan_dirs: Optional[Sequence[str]] = None,
        output_dir: Optional[Path] = OUTPUT_DIR,
        failed_dir: Optional[Path] = FAILED_DIR,
        proposals_dir: Optional[Path] = PROPOSALS_DIR,
        staging_dir: Optional[Path] = STAGING_DIR,
        research_dir: Optional[Path] = RESEARCH_DIR,
        research_mode: bool = False,
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
        self.max_cycles = max_cycles
        self.max_rate_limit_attempts = max(1, int(max_rate_limit_attempts))
        self.max_llm_attempts = max(1, int(max_llm_attempts))
        self.llm_request_timeout = max(1.0, float(llm_request_timeout))
        self.cycles_completed = 0
        self.proposals = proposals
        self.enable_validation = enable_validation
        self.enable_critique = enable_critique
        self.max_files_per_batch = max_files_per_batch
        self.max_files_total = max_files_total
        self.prefer_patch = prefer_patch

        self.scan_dirs = list(SCAN_DIRS if scan_dirs is None else scan_dirs)
        self.output_dir = output_dir or OUTPUT_DIR
        self.failed_dir = failed_dir or FAILED_DIR
        self.proposals_dir = proposals_dir or PROPOSALS_DIR
        self.staging_dir = staging_dir or STAGING_DIR
        self.research_dir = research_dir or RESEARCH_DIR
        self.research_mode = research_mode
        self.workspace_dir = workspace_dir
        self._using_workspace = False
        self._workspace_prepared = False

        self.files_processed = 0
        self.files_improved = 0
        self.files_quarantined = 0
        self.files_failed = 0
        self.batch_pytest_ok: Optional[bool] = None
        self.batch_pytest_diagnostics: Dict[str, Any] = {}
        self.batch_related_pytest_ok: Optional[bool] = None
        self.batch_related_pytest_diagnostics: Dict[str, Any] = {}

        self.provider: str = "unknown"
        self.use_gemini = False
        self.use_deepseek = False

        self.gemini_api_keys: List[str] = []
        self.key_index = 0
        self.model_name = DEFAULT_MODEL_NAME
        self.critic_model_name = CRITIC_MODEL_NAME
        self.gemini_models: List[str] = []
        self.gemini_critic_models: List[str] = []
        self.gemini_model_index = 0
        self.gemini_critic_model_index = 0
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
        if self.max_cycles is not None and self.cycles_completed >= self.max_cycles:
            logger.info(
                "ImproverAgent %s reached max_cycles=%s; requesting shutdown.",
                self.node_id,
                self.max_cycles,
            )
            self.request_shutdown()
            return

        await self._process_cycle(trigger="scheduled")
        self.cycles_completed += 1

        if self.single_pass or (
            self.max_cycles is not None and self.cycles_completed >= self.max_cycles
        ):
            logger.info(
                "ImproverAgent %s stopping after %s cycle(s).",
                self.node_id,
                self.cycles_completed,
            )
            self.request_shutdown()

    async def process_command(self, command: Mapping[str, Any]) -> None:
        """Process improver commands from canonical/legacy CRDT command formats."""
        normalized = normalize_command(command)

        action = command_action(normalized)
        payload = normalized.get("payload") if isinstance(normalized.get("payload"), Mapping) else {}
        data = normalized.get("data") if isinstance(normalized.get("data"), Mapping) else {}

        command_id = str(normalized.get("gid") or command.get("gid") or "")

        # Lifecycle commands, especially RUN_ONCE, must go through the shared
        # lifecycle handler because it owns pause/resume/restart semantics and
        # the explicit safety gate for RUN_ONCE.
        if await self.handle_lifecycle_command(normalized):
            return

        # Defensive fallback: RUN_ONCE must never bypass handle_lifecycle_command.
        # If it reaches this point, treat it as unsupported/blocked rather than
        # starting an improvement cycle without the lifecycle safety gate.
        if action == "RUN_ONCE":
            await self._emit_improver_event(
                event_type="command_blocked",
                parent_gid=command_id or None,
                payload={
                    "action": action,
                    "status": "blocked",
                    "reason": "run_once_requires_lifecycle_safety_gate",
                },
            )
            logger.warning(
                "ImproverAgent %s refused RUN_ONCE outside lifecycle handler.",
                self.node_id,
            )
            return

        # These branches are retained as compatibility fallback for older commands
        # if the shared lifecycle handler does not consume them for any reason.
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
            value = payload.get(
                "enabled",
                data.get("enabled", payload.get("value", data.get("value"))),
            )
            self.proposals = self._to_bool(value, default=self.proposals)
            await self._emit_improver_event(
                event_type="command_applied",
                parent_gid=command_id or None,
                payload={"action": action, "proposals": self.proposals},
            )
            return

        if action == "SET_SINGLE_PASS":
            value = payload.get(
                "enabled",
                data.get("enabled", payload.get("value", data.get("value"))),
            )
            self.single_pass = self._to_bool(value, default=self.single_pass)
            await self._emit_improver_event(
                event_type="command_applied",
                parent_gid=command_id or None,
                payload={"action": action, "single_pass": self.single_pass},
            )
            return

        if action == "RESTART_NODE":
            target_node = str(
                normalized.get("target_node")
                or normalized.get("target_node_id")
                or ""
            )

            if target_node in {self.node_id, "*", "None", ""}:
                await self._emit_improver_event(
                    event_type="command_applied",
                    parent_gid=command_id or None,
                    payload={"action": action, "target_node": target_node},
                )
                logger.critical("Received RESTART_NODE for self. Exiting for orchestrator restart.")
                self._request_shutdown_compat()
                raise SystemExit(0)

            await self._emit_improver_event(
                event_type="command_skipped",
                parent_gid=command_id or None,
                payload={
                    "action": action,
                    "target_node": target_node,
                    "status": "skipped",
                    "reason": "target_node_mismatch",
                },
            )
            return

        if action:
            await self._emit_improver_event(
                event_type="command_unsupported",
                parent_gid=command_id or None,
                payload={
                    "action": action,
                    "status": "unsupported",
                },
            )

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

    def _parse_csv_list(self, value: str) -> List[str]:
        return [item.strip() for item in str(value or "").split(",") if item.strip()]

    def _setup_provider(self) -> None:
        gemini_keys_str = os.environ.get("GEMINI_API_KEYS", os.environ.get("GEMINI_API_KEY", ""))
        gemini_api_keys = [k.strip() for k in gemini_keys_str.split(",") if k.strip()]

        if gemini_api_keys:
            self.provider = "gemini"
            self.use_gemini = True
            self.gemini_api_keys = gemini_api_keys
            self.key_index = 0

            models_raw = os.environ.get("GEMINI_MODELS", "").strip()
            critic_models_raw = os.environ.get("GEMINI_CRITIC_MODELS", "").strip()

            self.gemini_models = self._parse_csv_list(models_raw)
            if not self.gemini_models:
                self.gemini_models = [os.environ.get("GEMINI_MODEL", DEFAULT_MODEL_NAME).strip()]

            self.gemini_critic_models = self._parse_csv_list(critic_models_raw)
            if not self.gemini_critic_models:
                critic_default = os.environ.get("GEMINI_CRITIC_MODEL", "").strip()
                if critic_default:
                    self.gemini_critic_models = [critic_default]
                else:
                    self.gemini_critic_models = list(self.gemini_models)

            self.gemini_model_index = 0
            self.gemini_critic_model_index = 0
            self.model_name = self.gemini_models[self.gemini_model_index]
            self.critic_model_name = self.gemini_critic_models[self.gemini_critic_model_index]

            self._configure_next_gemini_key()
            logger.info(
                "🔑 Gemini API keys found: %d keys. Using model %s. Model chain=%s critic_chain=%s",
                len(self.gemini_api_keys),
                self.model_name,
                self.gemini_models,
                self.gemini_critic_models,
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

    def _advance_gemini_model(self, *, critic: bool = False) -> None:
        """Advance Gemini model fallback chain and reconfigure current key."""
        if critic:
            if self.gemini_critic_models:
                self.gemini_critic_model_index = (
                    self.gemini_critic_model_index + 1
                ) % len(self.gemini_critic_models)
                self.critic_model_name = self.gemini_critic_models[self.gemini_critic_model_index]
        else:
            if self.gemini_models:
                self.gemini_model_index = (
                    self.gemini_model_index + 1
                ) % len(self.gemini_models)
                self.model_name = self.gemini_models[self.gemini_model_index]

        logger.warning(
            "🔁 Switching Gemini %s model: planner=%s critic=%s",
            "critic" if critic else "planner",
            self.model_name,
            self.critic_model_name,
        )
        self._configure_next_gemini_key()

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

        total_keys = max(1, len(self.gemini_api_keys))
        legacy_max_attempts = max(1, max_retries * total_keys)
        max_attempts = min(
            legacy_max_attempts,
            max(1, int(getattr(self, "max_llm_attempts", legacy_max_attempts))),
        )
        max_rate_limit_attempts = max(1, int(getattr(self, "max_rate_limit_attempts", max_attempts)))
        request_timeout = max(1.0, float(getattr(self, "llm_request_timeout", 180.0)))

        rate_limit_attempts = 0
        api_error_attempts = 0

        for attempt in range(max_attempts):
            model = self.critic_model if critic else self.api_model

            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(model.generate_content, prompt),
                    timeout=request_timeout,
                )
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

            except asyncio.TimeoutError:
                api_error_attempts += 1
                logger.warning(
                    "Gemini generation timed out after %.1fs "
                    "(api attempt %s/%s, total attempt %s/%s, model=%s)",
                    request_timeout,
                    api_error_attempts,
                    max_attempts,
                    attempt + 1,
                    max_attempts,
                    self.critic_model_name if critic else self.model_name,
                )
                self.key_index += 1
                if self.key_index % total_keys == 0:
                    self._advance_gemini_model(critic=critic)
                else:
                    self._configure_next_gemini_key()
                continue

            except Exception as e:
                kind = self._classify_error(str(e))

                if kind == "auth":
                    logger.error(
                        "Invalid Gemini API key (index %s), switching.",
                        self.key_index % total_keys,
                    )
                    self.key_index += 1
                    self._configure_next_gemini_key()
                    await asyncio.sleep(1)
                    continue

                if kind == "rate_limit":
                    rate_limit_attempts += 1

                    if rate_limit_attempts >= max_rate_limit_attempts:
                        logger.warning(
                            "Gemini rate-limit retry cap reached (%s/%s). Failing current generation.",
                            rate_limit_attempts,
                            max_rate_limit_attempts,
                        )
                        return None

                    delay = self._extract_retry_delay(str(e)) or min(60 * (attempt + 1), 300)
                    logger.warning(
                        "Gemini rate limited. Switching route and retrying in %ss "
                        "(rate-limit attempt %s/%s, total attempt %s/%s, model=%s)",
                        delay,
                        rate_limit_attempts,
                        max_rate_limit_attempts,
                        attempt + 1,
                        max_attempts,
                        self.critic_model_name if critic else self.model_name,
                    )

                    self.key_index += 1
                    if self.key_index % total_keys == 0:
                        self._advance_gemini_model(critic=critic)
                    else:
                        self._configure_next_gemini_key()

                    await asyncio.sleep(delay)
                    continue

                api_error_attempts += 1
                logger.warning(
                    "Gemini API error classified as %s: %s "
                    "(api attempt %s/%s, total attempt %s/%s, model=%s)",
                    kind,
                    e,
                    api_error_attempts,
                    max_attempts,
                    attempt + 1,
                    max_attempts,
                    self.critic_model_name if critic else self.model_name,
                )

                self.key_index += 1
                if self.key_index % total_keys == 0:
                    self._advance_gemini_model(critic=critic)
                else:
                    self._configure_next_gemini_key()

                await asyncio.sleep(min(30, 5 * (attempt + 1)))

        logger.warning(
            "Gemini generation failed after %s total attempt(s), rate_limit_attempts=%s.",
            max_attempts,
            rate_limit_attempts,
        )
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

        if self.research_mode:
            self.research_dir.mkdir(parents=True, exist_ok=True)

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

        processed_this_cycle = 0

        async def flush_batch(batch: List[str]) -> bool:
            nonlocal processed_this_cycle

            if not batch:
                return False

            await self._improve_batch(batch)
            processed_this_cycle += len(batch)
            batch.clear()

            if self.max_files_total is not None and processed_this_cycle >= self.max_files_total:
                logger.info(
                    "Reached max_files_total=%s for this cycle; stopping file scan.",
                    self.max_files_total,
                )
                return True

            return False

        config_path = "swarm_config.py"
        if os.path.exists(config_path) and not self._should_skip(config_path):
            if self.max_files_total is None or processed_this_cycle < self.max_files_total:
                if await flush_batch([config_path]):
                    return

        batch: List[str] = []
        for scan_dir in self.scan_dirs:
            scan_path = Path(scan_dir)
            if not scan_path.exists():
                continue

            for root, dirs, files in os.walk(scan_path):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

                for filename in sorted(files):
                    if self.max_files_total is not None and processed_this_cycle + len(batch) >= self.max_files_total:
                        if await flush_batch(batch):
                            return

                    filepath = os.path.join(root, filename)
                    if self._should_skip(filepath):
                        continue

                    batch.append(filepath)

                    if len(batch) >= self.max_files_per_batch:
                        if await flush_batch(batch):
                            return

        if batch:
            await flush_batch(batch)

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
    
    @staticmethod
    def _safe_read_text(path: Path, limit: int = 4_000) -> str:
        try:
            if not path.exists() or not path.is_file():
                return ""
            text = path.read_text(encoding="utf-8", errors="replace")
            if len(text) > limit:
                return text[:limit] + "\n# [TRUNCATED]\n"
            return text
        except Exception:
            return ""

    @staticmethod
    def _module_name_from_path(path: Path) -> str:
        parts = list(path.with_suffix("").parts)
        if "src" in parts:
            parts = parts[parts.index("src") + 1 :]
        return ".".join(part for part in parts if part and part != "__init__")

    def _find_source_root_for_item(self, file_item: FileItem) -> Path:
        path = Path(file_item.path)

        if self._using_workspace and self.workspace_dir:
            try:
                return Path(self.workspace_dir).resolve()
            except Exception:
                pass

        for scan_dir in self.scan_dirs:
            scan_path = Path(scan_dir)
            try:
                resolved_scan = scan_path.resolve()
                resolved_file = path.resolve()
                if resolved_scan in resolved_file.parents or resolved_scan == resolved_file.parent:
                    return resolved_scan
            except Exception:
                continue

        return path.parent

    def _relative_to_source_root(self, path: Path, root: Path) -> str:
        try:
            return str(path.resolve().relative_to(root.resolve()))
        except Exception:
            return path.name

    def _build_file_context_pack(self, file_item: FileItem) -> Dict[str, Any]:
        """Build compact project-local context for LLM planning."""
        path = Path(file_item.path)
        root = self._find_source_root_for_item(file_item)
        parent = path.parent

        sibling_files: list[str] = []
        try:
            sibling_files = sorted(
                self._relative_to_source_root(candidate, root)
                for candidate in parent.iterdir()
                if candidate.is_file()
                and candidate.name != path.name
                and not self._should_skip(str(candidate))
            )[:20]
        except Exception:
            sibling_files = []

        init_file = parent / "__init__.py"
        init_preview = self._safe_read_text(init_file, limit=3_000)

        reverse_imports: list[str] = []
        module_stem = path.stem
        module_name = self._module_name_from_path(path)

        search_roots: list[Path] = []
        if self._using_workspace and self.workspace_dir:
            search_roots.append(Path(self.workspace_dir))
        else:
            search_roots.extend(Path(scan_dir) for scan_dir in self.scan_dirs)

        for search_root in search_roots:
            try:
                if not search_root.exists():
                    continue
                for candidate in search_root.rglob("*.py"):
                    if candidate == path or self._should_skip(str(candidate)):
                        continue
                    text = self._safe_read_text(candidate, limit=8_000)
                    if not text:
                        continue

                    needles = {
                        f"import {module_stem}",
                        f"from {module_stem} import",
                        f"from .{module_stem} import",
                    }
                    if module_name:
                        needles.add(f"import {module_name}")
                        needles.add(f"from {module_name} import")

                    if any(needle in text for needle in needles):
                        reverse_imports.append(self._relative_to_source_root(candidate, root))
                        if len(reverse_imports) >= 20:
                            break
            except Exception:
                continue

        related_tests: list[str] = []
        related_test_previews: list[dict[str, str]] = []

        try:
            project_root = Path.cwd()
            test_candidates = [
                project_root / "tests",
                project_root / "src" / "testing",
            ]

            for test_root in test_candidates:
                if not test_root.exists():
                    continue

                for candidate in test_root.rglob("*.py"):
                    candidate_text = ""
                    name = candidate.name.lower()

                    if module_stem.lower() in name:
                        candidate_text = self._safe_read_text(candidate, limit=3_000)
                    else:
                        probe_text = self._safe_read_text(candidate, limit=8_000)
                        if module_stem in probe_text:
                            candidate_text = probe_text[:3_000]

                    if not candidate_text:
                        continue

                    rel_test = str(candidate.relative_to(project_root))
                    related_tests.append(rel_test)

                    if len(related_test_previews) < 3:
                        related_test_previews.append(
                            {
                                "path": rel_test,
                                "preview": candidate_text,
                            }
                        )

                    if len(related_tests) >= 20:
                        break
        except Exception:
            related_tests = []
            related_test_previews = []

        return {
            "source_root": str(root),
            "relative_path": self._relative_to_source_root(path, root),
            "module_name": module_name,
            "package_init_preview": init_preview,
            "sibling_files": sibling_files,
            "reverse_imports": sorted(set(reverse_imports))[:20],
            "related_tests": sorted(set(related_tests))[:20],
            "related_test_previews": related_test_previews,
            "guidance": [
                "Preserve public imports and module-level API unless clearly justified.",
                "Check sibling_files and package_init_preview before renaming exports.",
                "Treat reverse_imports as downstream dependents that may break.",
                "Prefer safe, testable, minimal changes over broad rewrites.",
                "Use related_test_previews to avoid changing behavior that existing tests depend on.",
            ],
        }
    
    def _related_test_paths_for_items(self, file_items: Sequence[FileItem]) -> List[str]:
        paths: list[str] = []

        for item in file_items:
            context = self._build_file_context_pack(item)
            for test_path in context.get("related_tests", []):
                if isinstance(test_path, str) and test_path:
                    paths.append(test_path)

        return sorted(set(paths))

    def _python_plan_prompt(self, file_item: FileItem, context_hits: Sequence[MemoryHit], strategy: str) -> str:
        project_context = self._build_file_context_pack(file_item)
        return build_python_prompt(
            file_item,
            context_hits,
            strategy,
            project_context=project_context,
        )

    def _non_python_plan_prompt(self, file_item: FileItem, context_hits: Sequence[MemoryHit], strategy: str) -> str:
        project_context = self._build_file_context_pack(file_item)
        return build_non_python_prompt(
            file_item,
            context_hits,
            strategy,
            prefer_patch=self.prefer_patch,
            project_context=project_context,
        )

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
        self.batch_pytest_diagnostics = {}

        if not self.enable_validation:
            self.batch_pytest_diagnostics = {"reason": "validation_disabled"}
            return None

        ok, diagnostics = run_pytest_smoke_with_diagnostics(Path.cwd())
        self.batch_pytest_diagnostics = diagnostics
        return ok
    
    def _validate_related_batch_tests(self, file_items: Sequence[FileItem]) -> Optional[bool]:
        self.batch_related_pytest_diagnostics = {}

        if not self.enable_validation:
            self.batch_related_pytest_diagnostics = {"reason": "validation_disabled"}
            return None

        related_tests = self._related_test_paths_for_items(file_items)
        ok, diagnostics = run_pytest_paths_with_diagnostics(Path.cwd(), related_tests)
        self.batch_related_pytest_diagnostics = diagnostics
        return ok
    
    @staticmethod
    def _numeric_literals_from_python(source: str) -> list[str]:
        """Extract numeric literals from Python source using AST.

        This intentionally ignores strings/comments and catches changes to
        numeric constants, defaults, thresholds, intervals, limits, and ratios.
        """
        try:
            tree = ast.parse(source)
        except Exception:
            return []

        values: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, complex)):
                values.append(repr(node.value))

        return values

    @staticmethod
    def _numeric_literals_from_text(source: str) -> list[str]:
        """Fallback numeric literal extraction for non-Python or invalid Python."""
        pattern = re.compile(
            r"""
            (?<![\w.])
            [-+]?
            (?:
                \d+\.\d+
                |
                \d+
            )
            (?:[eE][-+]?\d+)?
            (?![\w.])
            """,
            re.VERBOSE,
        )
        return pattern.findall(source or "")

    def _numeric_literal_counts(self, source: str, *, language: str) -> dict[str, int]:
        if language == "python":
            literals = self._numeric_literals_from_python(source)
            if not literals:
                literals = self._numeric_literals_from_text(source)
        else:
            literals = self._numeric_literals_from_text(source)

        counts: dict[str, int] = {}
        for literal in literals:
            counts[literal] = counts.get(literal, 0) + 1
        return counts

    @staticmethod
    def _count_delta(before: dict[str, int], after: dict[str, int]) -> dict[str, dict[str, int]]:
        removed: dict[str, int] = {}
        added: dict[str, int] = {}

        for key, value in before.items():
            delta = value - after.get(key, 0)
            if delta > 0:
                removed[key] = delta

        for key, value in after.items():
            delta = value - before.get(key, 0)
            if delta > 0:
                added[key] = delta

        return {
            "removed": removed,
            "added": added,
        }

    def _detect_numeric_semantic_change(
        self,
        original: FileItem,
        result: ImprovementResult,
    ) -> dict[str, Any]:
        """Detect numeric/default changes that may alter runtime semantics."""
        before = self._numeric_literal_counts(original.content, language=original.language)
        after = self._numeric_literal_counts(result.code, language=original.language)

        delta = self._count_delta(before, after)
        changed = bool(delta["removed"] or delta["added"])

        total_changed = sum(delta["removed"].values()) + sum(delta["added"].values())

        return {
            "changed": changed,
            "total_changed": total_changed,
            "removed": delta["removed"],
            "added": delta["added"],
        }

    def _validate_and_score(self, original: FileItem, result: ImprovementResult) -> None:
        result.validation = validate_result(
            original,
            result.code,
            enable_validation=self.enable_validation,
            staging_dir=self.staging_dir,
            max_changed_lines_ratio=self._allowed_changed_lines_ratio(result),
        )
        effective_pytest_ok = self.batch_pytest_ok

        if self.batch_related_pytest_ok is not None:
            effective_pytest_ok = self.batch_related_pytest_ok
            result.validation.diagnostics["pytest_scope"] = "related"
        else:
            result.validation.diagnostics["pytest_scope"] = "global"

        result.validation.pytest_ok = effective_pytest_ok

        if self.batch_related_pytest_diagnostics:
            result.validation.diagnostics["related_pytest"] = self.batch_related_pytest_diagnostics

        if self.batch_pytest_diagnostics:
            result.validation.diagnostics["global_pytest"] = self.batch_pytest_diagnostics

        if effective_pytest_ok is False:
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

        numeric_delta = self._detect_numeric_semantic_change(original, result)

        if numeric_delta["changed"]:
            result.validation.notes.append("numeric_semantic_change")
            result.risk = max(float(result.risk or 0.0), 0.35)

            # Penalize unverified numeric/default changes. These may still be
            # valuable, but they require stronger validation before acceptance.
            result.score = round(max(0.0, result.score - min(8.0, 2.0 * numeric_delta["total_changed"])), 2)

            logger.warning(
                "Numeric semantic change detected for %s: removed=%s added=%s score=%s risk=%s",
                original.path,
                numeric_delta["removed"],
                numeric_delta["added"],
                result.score,
                result.risk,
            )

    def _result_relative_path(self, file_path: str | Path) -> Path:
        """Return stable relative path for improver result artifacts."""
        path = Path(file_path)

        candidates: List[Path] = []

        if self._using_workspace and self.workspace_dir:
            candidates.append(Path(self.workspace_dir))

        for scan_dir in self.scan_dirs:
            candidates.append(Path(scan_dir))

        try:
            resolved_path = path.resolve()
        except Exception:
            resolved_path = path

        for root in candidates:
            try:
                return resolved_path.relative_to(root.resolve())
            except Exception:
                continue

        parts = path.parts
        if "src" in parts:
            idx = parts.index("src")
            return Path(*parts[idx:])

        return Path(path.name)
    
    @staticmethod
    def _result_diff_text(
        original: FileItem,
        result: ImprovementResult,
        *,
        max_lines: int = 1200,
    ) -> tuple[str, bool]:
        """Build a bounded unified diff for research artifacts."""
        diff_lines = list(
            difflib.unified_diff(
                original.content.splitlines(),
                result.code.splitlines(),
                fromfile=original.path,
                tofile=result.proposed_path or original.path,
                lineterm="",
            )
        )

        truncated = len(diff_lines) > max_lines
        if truncated:
            diff_lines = diff_lines[:max_lines]
            diff_lines.append(f"... truncated {len(diff_lines) - max_lines} lines")

        return "\n".join(diff_lines), truncated

    def _persist_research_artifact(
        self,
        *,
        original: FileItem,
        result: ImprovementResult,
        relative_path: Path,
        meta: Mapping[str, Any],
        quarantined_path: Path,
    ) -> None:
        """Persist a review artifact for creative/risky quarantined results."""
        if not self.research_mode:
            return

        try:
            diff_text, diff_truncated = self._result_diff_text(original, result)
            ts = int(time.time())

            research_base = safe_output_path(
                self.research_dir,
                f"{relative_path}.{ts}.research.json",
            )
            diff_path = safe_output_path(
                self.research_dir,
                f"{relative_path}.{ts}.research.diff",
            )

            research_base.parent.mkdir(parents=True, exist_ok=True)
            diff_path.parent.mkdir(parents=True, exist_ok=True)

            research_payload: Dict[str, Any] = {
                **dict(meta),
                "research_mode": True,
                "research_reason": "quarantined_candidate",
                "quarantined_path": str(quarantined_path),
                "diff_path": str(diff_path),
                "diff_truncated": diff_truncated,
                "review_recommendation": "human_or_overseer_review_required",
            }

            atomic_write_text(
                research_base,
                json.dumps(research_payload, ensure_ascii=False, indent=2),
            )
            atomic_write_text(diff_path, diff_text)

            logger.info(
                "Saved research artifact: %s diff=%s",
                research_base,
                diff_path,
            )
        except Exception as exc:
            logger.warning(
                "Failed to persist research artifact for %s: %s",
                original.path,
                exc,
            )

    def _persist_result(self, original: FileItem, result: ImprovementResult) -> None:
        original_fp = original.fingerprint
        new_fp = fingerprint_text(result.code)
        relative_path = self._result_relative_path(original.path)

        no_change_reason = ""
        if result.code == original.content:
            no_change_reason = "no_change"
        elif result.code.splitlines() == original.content.splitlines():
            no_change_reason = "no_change_line_equivalent"
        elif new_fp == original_fp:
            no_change_reason = "no_change_fingerprint"

        if no_change_reason:
            result.validation.notes.append(no_change_reason)
            logger.info(
                "No-op improvement skipped: %s reason=%s",
                original.path,
                no_change_reason,
            )

            meta: Dict[str, Any] = {
                "original_path": original.path,
                "proposed_path": result.proposed_path,
                "artifact_relative_path": str(relative_path),
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
                "numeric_semantic_change": "numeric_semantic_change" in result.validation.notes,
                "research_mode": self.research_mode,
                "skipped": True,
                "skip_reason": no_change_reason,
            }

            self.memory.record_episode(result)
            self.memory.record_file_outcome(original.path, result.score, False, meta=meta)
            self.memory.record_strategy_outcome(result.strategy, result.score, False)
            return

        has_numeric_semantic_change = "numeric_semantic_change" in result.validation.notes

        success = (
            result.validation.syntactically_valid
            and result.validation.compile_ok
            and result.validation.pytest_ok is not False
            and not (has_numeric_semantic_change and result.validation.pytest_ok is not True)
            and result.score >= 12.0
            and "changed_too_much" not in result.validation.notes
            and not any(str(note).startswith("no_change") for note in result.validation.notes)
        )

        target_dir = self.output_dir if success else self.failed_dir

        if success:
            self.files_improved += 1
        else:
            self.files_quarantined += 1

        meta: Dict[str, Any] = {
            "original_path": original.path,
            "proposed_path": result.proposed_path,
            "artifact_relative_path": str(relative_path),
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
            "research_mode": self.research_mode,
            "fallback_used": result.fallback_used,
            "prefer_patch": self.prefer_patch,
        }

        try:
            output_path = safe_output_path(target_dir, str(relative_path))
            output_path.parent.mkdir(parents=True, exist_ok=True)

            stage_path = self.staging_dir / f"{relative_path.name}.{int(time.time())}.json"

            atomic_write_text(stage_path, json.dumps(meta, ensure_ascii=False, indent=2))
            atomic_write_text(output_path, result.code)

            if not success:
                self._persist_research_artifact(
                    original=original,
                    result=result,
                    relative_path=relative_path,
                    meta=meta,
                    quarantined_path=output_path,
                )

            if self._using_workspace and success:
                try:
                    ws_root = Path(self.workspace_dir) if self.workspace_dir else None
                    if ws_root is not None:
                        original_path = Path(result.original_path)
                        ws_file = (
                            ws_root / original_path
                            if not original_path.is_absolute()
                            else ws_root / original_path.name
                        )
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
                str(relative_path),
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
        self.batch_related_pytest_ok = self._validate_related_batch_tests(file_items)

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