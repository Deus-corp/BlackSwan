#!/usr/bin/env python3
"""Production-ready base runtime for swarm meta-agents.

A meta-agent coordinates one swarm ecosystem. It normally:
- collects signals from nodes / CRDT / memory
- builds a normalized snapshot
- decides what should happen
- issues commands to nodes
- persists decisions and event lineage

This base class intentionally contains no domain-specific logic.
Specialized meta-agents should override hooks:

- collect()
- decide()
- issue_commands()
- persist_decision()
- publish_heartbeat()
- healthcheck()
- maintenance()
- on_startup()
- on_shutdown()

Main reasoning cycle:

    collect -> decide -> issue_commands -> persist_decision
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import socket
import sys

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Iterable, Mapping, Optional, Sequence

from src.core.crdt_adapter import CRDTAdapter
from swarm_config import config

from src.swarms.common.utils import (
    expires_in,
    new_gid,
    new_meta_agent_id,
    summarize_value,
    utc_ts,
)

from src.swarms.common.protocols import (
    make_swarm_command,
    make_swarm_event,
    make_swarm_heartbeat,
    is_lifecycle_command,
    lifecycle_action,
    lifecycle_applies_to,
    lifecycle_reason,
    lifecycle_summary,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BaseMetaAgentConfig:
    """Runtime configuration for a generic swarm meta-agent."""

    swarm_type: str
    role: str = "meta_agent"
    agent_id: Optional[str] = None
    version: str = "0.1.0"

    reflect_interval_seconds: float = 3.0
    heartbeat_interval_seconds: float = 30.0
    command_gc_interval_seconds: float = 60.0
    reconcile_interval_seconds: float = 10.0
    healthcheck_interval_seconds: float = 15.0
    maintenance_interval_seconds: float = 60.0

    startup_timeout_seconds: float = 30.0
    shutdown_timeout_seconds: float = 30.0

    enable_heartbeat_loop: bool = True
    enable_command_gc_loop: bool = True
    enable_reconcile_loop: bool = True
    enable_health_loop: bool = True
    enable_maintenance_loop: bool = True

    crdt_db_path: Optional[str] = None
    hostname: str = field(default_factory=socket.gethostname)

    @classmethod
    def from_swarm_type(
        cls,
        swarm_type: str,
        *,
        role: str = "meta_agent",
        agent_id: Optional[str] = None,
        version: str = "0.1.0",
    ) -> "BaseMetaAgentConfig":
        return cls(
            swarm_type=swarm_type,
            role=role,
            agent_id=agent_id,
            version=version,
            crdt_db_path=getattr(config, "crdt_db_path", None),
        )


@dataclass(slots=True)
class MetaAgentHealth:
    """Mutable health state for a running meta-agent."""

    status: str = "initializing"
    started_at: float = field(default_factory=utc_ts)

    last_reflect_at: float = 0.0
    last_collect_at: float = 0.0
    last_decide_at: float = 0.0
    last_command_issue_at: float = 0.0
    last_decision_persist_at: float = 0.0
    last_heartbeat_at: float = 0.0
    last_reconcile_at: float = 0.0
    last_command_gc_at: float = 0.0
    last_healthcheck_at: float = 0.0
    last_maintenance_at: float = 0.0

    consecutive_reflect_failures: int = 0
    consecutive_collect_failures: int = 0
    consecutive_decide_failures: int = 0
    consecutive_command_failures: int = 0
    consecutive_persist_failures: int = 0
    consecutive_heartbeat_failures: int = 0
    consecutive_reconcile_failures: int = 0

    collected_items_last_cycle: int = 0
    commands_issued_last_cycle: int = 0

    last_decision: str = ""
    last_error: str = ""

    @property
    def uptime_seconds(self) -> float:
        return max(0.0, utc_ts() - self.started_at)


@dataclass(slots=True)
class MetaDecision:
    """Generic decision container for meta-agent cycles.

    Specialized meta-agents may return their own decision object. The base
    implementation only assumes Mapping-like or attribute-based fields when
    persisting/building commands via helper methods.
    """

    action: str = "MAINTAIN"
    confidence: float = 0.0
    rationale: str = ""
    event_gid: str = ""
    parent_gid: Optional[str] = None
    command_required: bool = False
    target_swarm: Optional[str] = None
    target_node: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)


class BaseSwarmMetaAgent:
    """Reusable async runtime shell for specialized swarm meta-agents."""

    def __init__(
        self,
        *,
        meta_config: BaseMetaAgentConfig,
        crdt: Optional[CRDTAdapter] = None,
        logger_name: Optional[str] = None,
    ) -> None:
        self.config = meta_config

        self._seen_lifecycle_command_gids: set[str] = set()

        self.swarm_type = meta_config.swarm_type
        self.role = meta_config.role
        self.version = meta_config.version
        self.hostname = meta_config.hostname
        self.agent_id = meta_config.agent_id or self._build_agent_id(meta_config.swarm_type)

        self.logger = logging.getLogger(logger_name or f"Swarm.{self.swarm_type}.{self.agent_id}")

        self.crdt = crdt or CRDTAdapter(
            node_id=self.agent_id,
            db_path=meta_config.crdt_db_path or getattr(config, "crdt_db_path", None),
        )

        self.health = MetaAgentHealth()
        self.shutdown_event = asyncio.Event()
        self.started_event = asyncio.Event()

        self._tasks: Dict[str, asyncio.Task[Any]] = {}
        self._stopping = False
        self._main_task: Optional[asyncio.Task[Any]] = None

    # ------------------------------------------------------------------
    # Identity helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_agent_id(swarm_type: str) -> str:
        return new_meta_agent_id(swarm_type)

    def new_gid(self, prefix: str = "evt") -> str:
        return new_gid(prefix, namespace=self.swarm_type)

    # ------------------------------------------------------------------
    # Public lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start meta-agent runtime and block until shutdown."""
        if self._main_task is not None:
            raise RuntimeError("Meta-agent is already started")

        self._main_task = asyncio.current_task()
        self.health.status = "starting"

        loop = asyncio.get_running_loop()
        self._register_signal_handlers(loop)

        self.logger.info(
            "Starting %s meta-agent %s role=%s version=%s host=%s",
            self.swarm_type,
            self.agent_id,
            self.role,
            self.version,
            self.hostname,
        )

        try:
            await asyncio.wait_for(
                self.on_startup(),
                timeout=self.config.startup_timeout_seconds,
            )

            self.health.status = "running"
            self.started_event.set()

            self._start_background_loops()

            await self.reflect_loop()

        except asyncio.CancelledError:
            self.logger.info("Meta-agent %s cancelled.", self.agent_id)
            raise
        except Exception as exc:
            self.health.status = "failed"
            self.health.last_error = str(exc)
            self.logger.critical("Meta-agent %s crashed: %s", self.agent_id, exc, exc_info=True)
            raise
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop meta-agent runtime gracefully."""
        if self._stopping:
            return

        self._stopping = True
        self.health.status = "stopping"
        self.shutdown_event.set()

        self.logger.info("Stopping meta-agent %s...", self.agent_id)

        await self._cancel_background_tasks()

        try:
            await asyncio.wait_for(
                self.on_shutdown(),
                timeout=self.config.shutdown_timeout_seconds,
            )
        except asyncio.TimeoutError:
            self.logger.warning("Meta-agent %s shutdown hook timed out.", self.agent_id)
        except Exception as exc:
            self.logger.error("Meta-agent %s shutdown hook failed: %s", self.agent_id, exc, exc_info=True)

        await self._close_crdt_if_supported()

        self.health.status = "stopped"
        self.logger.info("Meta-agent %s stopped.", self.agent_id)

    def request_shutdown(self) -> None:
        """Request graceful shutdown from sync code or signal handlers."""
        if self.shutdown_event.is_set():
            return
        self.logger.info("Shutdown requested for meta-agent %s.", self.agent_id)
        self.shutdown_event.set()

    def _set_runtime_paused(self, paused: bool) -> None:
        """Set paused flag across known meta-agent runtime shapes."""
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
        """Return current paused state across known meta-agent runtime shapes."""
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

    async def handle_lifecycle_command(self, command: Mapping[str, Any]) -> bool:
        """Handle common lifecycle commands for meta-agents."""
        if not is_lifecycle_command(command):
            return False

        agent_id = str(getattr(self, "agent_id", "") or getattr(self, "node_id", ""))
        swarm_type = str(getattr(self, "swarm_type", "") or getattr(self, "swarm", ""))
        role = str(getattr(self, "role", "meta_agent"))

        if not lifecycle_applies_to(
            command,
            node_id=agent_id,
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
            self.logger.info("%s %s paused by lifecycle command.", type(self).__name__, agent_id)
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
            self.logger.info("%s %s resumed by lifecycle command.", type(self).__name__, agent_id)
            return True

        if action == "RESTART_NODE":
            await self._emit_lifecycle_event(
                action=action,
                status="applied",
                reason=reason,
                parent_gid=command_gid,
                command=command,
            )
            self.logger.critical("%s %s received lifecycle RESTART_NODE.", type(self).__name__, agent_id)
            sys.exit(0)

        if action == "RUN_ONCE":
            await self._emit_lifecycle_event(
                action=action,
                status="unsupported",
                reason=reason or "RUN_ONCE unsupported for meta_agent",
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

    async def _emit_lifecycle_event(
        self,
        *,
        action: str,
        status: str,
        reason: str,
        parent_gid: str,
        command: Mapping[str, Any],
    ) -> None:
        """Emit canonical lifecycle event for meta-agent."""
        crdt = getattr(self, "crdt", None)
        if crdt is None or not hasattr(crdt, "add_genome"):
            return

        agent_id = str(getattr(self, "agent_id", "") or getattr(self, "node_id", ""))
        swarm_type = str(getattr(self, "swarm_type", "") or getattr(self, "swarm", ""))
        role = str(getattr(self, "role", "meta_agent"))

        event = {
            "type": "swarm_event",
            "event_type": "lifecycle_command_applied",
            "gid": self.new_gid("lifecycle_evt") if hasattr(self, "new_gid") else "",
            "source_swarm": swarm_type,
            "source_agent": agent_id,
            "source_node": agent_id,
            "role": role,
            "parent_gid": parent_gid,
            "timestamp": utc_ts(),
            "payload": {
                "action": action,
                "status": status,
                "reason": reason,
                "command": lifecycle_summary(command),
            },
            "provenance": {
                "agent": agent_id,
                "source": "common_lifecycle",
            },
        }

        await crdt.add_genome(event)

    async def poll_lifecycle_commands(self) -> int:
        """Scan CRDT state for lifecycle commands targeting this meta-agent.

        Returns number of lifecycle commands handled.
        """
        state = getattr(getattr(self, "crdt", None), "state", {})
        if not isinstance(state, Mapping):
            return 0

        agent_id = str(getattr(self, "agent_id", "") or getattr(self, "node_id", ""))
        swarm_type = str(getattr(self, "swarm_type", "") or getattr(self, "swarm", ""))
        role = str(getattr(self, "role", "meta_agent"))

        handled = 0

        for record in list(state.values()):
            if not isinstance(record, Mapping):
                continue

            if record.get("type") != "swarm_command":
                continue

            if not is_lifecycle_command(record):
                continue

            gid = str(record.get("gid") or "")
            if gid and gid in self._seen_lifecycle_command_gids:
                continue

            expires_at = record.get("expires_at")
            if expires_at is not None:
                try:
                    if float(expires_at) <= utc_ts():
                        if gid:
                            self._seen_lifecycle_command_gids.add(gid)
                        continue
                except (TypeError, ValueError):
                    pass

            if not lifecycle_applies_to(
                record,
                node_id=agent_id,
                swarm_type=swarm_type,
                role=role,
            ):
                continue

            if await self.handle_lifecycle_command(record):
                if gid:
                    self._seen_lifecycle_command_gids.add(gid)
                handled += 1

        return handled

    # ------------------------------------------------------------------
    # Main reflection loop
    # ------------------------------------------------------------------

    async def reflect_loop(self) -> None:
        """Main meta-agent reasoning loop."""
        while not self.shutdown_event.is_set():
            started_at = utc_ts()

            try:
                await self.reflect()
                self.health.last_reflect_at = time.time()
                self.health.consecutive_reflect_failures = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.health.consecutive_reflect_failures += 1
                self.health.last_error = str(exc)
                self.logger.error("reflect failed: %s", exc, exc_info=True)
                await self.on_reflect_error(exc)

            elapsed = time.time() - started_at
            sleep_for = max(0.0, self.config.reflect_interval_seconds - elapsed)

            try:
                await asyncio.wait_for(self.shutdown_event.wait(), timeout=sleep_for)
            except asyncio.TimeoutError:
                pass

    async def reflect(self) -> Any:
        """Run one collect -> decide -> issue commands -> persist decision cycle."""
        await self.poll_lifecycle_commands()

        if self.is_paused():
            self.logger.info("%s %s is paused; skipping reflect cycle.", type(self).__name__, self.agent_id)
            self.health.status = "paused"
            return None

        snapshot = await self._safe_collect()
        decision = await self._safe_decide(snapshot)
        commands = await self._safe_issue_commands(decision, snapshot)
        await self._safe_persist_decision(decision, snapshot, commands)

        self.health.collected_items_last_cycle = self._count_collected_items(snapshot)
        self.health.commands_issued_last_cycle = len(commands) if isinstance(commands, Sequence) else 0
        self.health.last_decision = self._extract_decision_action(decision)
        return decision

    # ------------------------------------------------------------------
    # Safe wrappers around domain hooks
    # ------------------------------------------------------------------

    async def _safe_collect(self) -> Any:
        try:
            snapshot = await self.collect()
            self.health.last_collect_at = time.time()
            self.health.consecutive_collect_failures = 0
            self.health.collected_items_last_cycle = self._count_collected_items(snapshot)
            return snapshot
        except Exception:
            self.health.consecutive_collect_failures += 1
            raise

    async def _safe_decide(self, snapshot: Any) -> Any:
        try:
            decision = await self.decide(snapshot)
            self.health.last_decide_at = time.time()
            self.health.consecutive_decide_failures = 0
            return decision
        except Exception:
            self.health.consecutive_decide_failures += 1
            raise

    async def _safe_issue_commands(self, decision: Any, snapshot: Any) -> Sequence[Mapping[str, Any]]:
        try:
            commands = await self.issue_commands(decision, snapshot)
            self.health.last_command_issue_at = time.time()
            self.health.consecutive_command_failures = 0
            return commands
        except Exception:
            self.health.consecutive_command_failures += 1
            raise

    async def _safe_persist_decision(
        self,
        decision: Any,
        snapshot: Any,
        commands: Sequence[Mapping[str, Any]],
    ) -> None:
        try:
            await self.persist_decision(decision, snapshot, commands)
            self.health.last_decision_persist_at = time.time()
            self.health.consecutive_persist_failures = 0
        except Exception:
            self.health.consecutive_persist_failures += 1
            raise

    # ------------------------------------------------------------------
    # Background loops
    # ------------------------------------------------------------------

    def _start_background_loops(self) -> None:
        if self.config.enable_heartbeat_loop:
            self._create_task("heartbeat_loop", self._heartbeat_loop())

        if self.config.enable_command_gc_loop:
            self._create_task("command_gc_loop", self._command_gc_loop())

        if self.config.enable_reconcile_loop:
            self._create_task("reconcile_loop", self._reconcile_loop())

        if self.config.enable_health_loop:
            self._create_task("health_loop", self._health_loop())

        if self.config.enable_maintenance_loop:
            self._create_task("maintenance_loop", self._maintenance_loop())

    def _create_task(self, name: str, coro: Awaitable[Any]) -> None:
        if name in self._tasks:
            raise RuntimeError(f"Task already exists: {name}")

        task = asyncio.create_task(coro, name=f"{self.agent_id}:{name}")
        task.add_done_callback(lambda done_task, task_name=name: self._on_task_done(task_name, done_task))
        self._tasks[name] = task

    def _on_task_done(self, name: str, task: asyncio.Task[Any]) -> None:
        if self._stopping:
            return

        try:
            exc = task.exception()
        except asyncio.CancelledError:
            return

        if exc is None:
            self.logger.warning("Background task %s exited unexpectedly without error.", name)
            return

        self.health.last_error = str(exc)
        self.logger.error("Background task %s failed: %s", name, exc, exc_info=exc)

        if not self.shutdown_event.is_set():
            self.request_shutdown()

    async def _cancel_background_tasks(self) -> None:
        if not self._tasks:
            return

        for task in self._tasks.values():
            task.cancel()

        results = await asyncio.gather(*self._tasks.values(), return_exceptions=True)

        for name, result in zip(self._tasks.keys(), results):
            if isinstance(result, asyncio.CancelledError):
                self.logger.debug("Task %s cancelled.", name)
            elif isinstance(result, Exception):
                self.logger.debug("Task %s ended with error during shutdown: %s", name, result)

        self._tasks.clear()

    async def _heartbeat_loop(self) -> None:
        await self._periodic_loop(
            name="heartbeat",
            interval_seconds=self.config.heartbeat_interval_seconds,
            callback=self._safe_publish_heartbeat,
        )

    async def _command_gc_loop(self) -> None:
        await self._periodic_loop(
            name="command_gc",
            interval_seconds=self.config.command_gc_interval_seconds,
            callback=self._safe_gc_expired_commands,
        )

    async def _reconcile_loop(self) -> None:
        await self._periodic_loop(
            name="reconcile",
            interval_seconds=self.config.reconcile_interval_seconds,
            callback=self._safe_reconcile,
        )

    async def _health_loop(self) -> None:
        await self._periodic_loop(
            name="healthcheck",
            interval_seconds=self.config.healthcheck_interval_seconds,
            callback=self._safe_healthcheck,
        )

    async def _maintenance_loop(self) -> None:
        await self._periodic_loop(
            name="maintenance",
            interval_seconds=self.config.maintenance_interval_seconds,
            callback=self._safe_maintenance,
        )

    async def _periodic_loop(
        self,
        *,
        name: str,
        interval_seconds: float,
        callback: Callable[[], Awaitable[None]],
    ) -> None:
        while not self.shutdown_event.is_set():
            started_at = time.time()
            try:
                await callback()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.health.last_error = str(exc)
                self.logger.error("%s loop failed: %s", name, exc, exc_info=True)

            elapsed = time.time() - started_at
            sleep_for = max(0.0, interval_seconds - elapsed)

            try:
                await asyncio.wait_for(self.shutdown_event.wait(), timeout=sleep_for)
            except asyncio.TimeoutError:
                pass

    async def _safe_publish_heartbeat(self) -> None:
        try:
            await self.publish_heartbeat()
            self.health.last_heartbeat_at = time.time()
            self.health.consecutive_heartbeat_failures = 0
        except Exception:
            self.health.consecutive_heartbeat_failures += 1
            raise

    async def _safe_gc_expired_commands(self) -> None:
        await self.gc_expired_commands()
        self.health.last_command_gc_at = time.time()

    async def _safe_reconcile(self) -> None:
        try:
            await self.reconcile()
            self.health.last_reconcile_at = time.time()
            self.health.consecutive_reconcile_failures = 0
        except Exception:
            self.health.consecutive_reconcile_failures += 1
            raise

    async def _safe_healthcheck(self) -> None:
        await self.healthcheck()
        self.health.last_healthcheck_at = time.time()

    async def _safe_maintenance(self) -> None:
        await self.maintenance()
        self.health.last_maintenance_at = time.time()

    # ------------------------------------------------------------------
    # Default domain hooks
    # ------------------------------------------------------------------

    async def on_startup(self) -> None:
        """Hook called before loops are started."""
        return None

    async def on_shutdown(self) -> None:
        """Hook called after loops are cancelled and before CRDT close."""
        return None

    async def collect(self) -> Any:
        """Collect and normalize current swarm state.

        Specialized meta-agents should override this.
        """
        return {}

    async def decide(self, snapshot: Any) -> Any:
        """Produce a decision from a snapshot.

        Specialized meta-agents should override this.
        """
        return MetaDecision(
            action="MAINTAIN",
            confidence=0.0,
            rationale="Default no-op meta decision.",
            event_gid=self.new_gid("decision"),
            command_required=False,
            target_swarm=self.swarm_type,
            provenance={"agent": self.agent_id},
        )

    async def issue_commands(self, decision: Any, snapshot: Any) -> Sequence[Mapping[str, Any]]:
        """Issue commands based on a decision.

        Default implementation emits one generic swarm_command if the decision
        declares command_required=True.
        """
        if not self._extract_command_required(decision):
            return []

        command = self.build_command_from_decision(decision)
        await self.crdt.add_genome(command)
        return [command]

    async def persist_decision(
        self,
        decision: Any,
        snapshot: Any,
        commands: Sequence[Mapping[str, Any]],
    ) -> None:
        """Persist decision/event lineage.

        Default implementation emits a generic policy_evaluated event to CRDT.
        Swarm-specific implementations should also write to local memory.
        """
        event = self.build_decision_event(decision, snapshot, commands)
        await self.crdt.add_genome(event)

    async def publish_heartbeat(self) -> None:
        """Publish generic meta-agent heartbeat."""
        heartbeat = self.build_heartbeat()
        await self.crdt.add_genome(heartbeat)

    async def gc_expired_commands(self) -> None:
        """Optional hook for command cleanup.

        CRDT adapters may not support deletion, so default is no-op.
        """
        return None

    async def reconcile(self) -> None:
        """Optional hook for reconciling meta-agent state."""
        return None

    async def healthcheck(self) -> None:
        """Run meta-agent health checks."""
        if self.health.consecutive_reflect_failures >= 3:
            self.health.status = "degraded"
        elif self.health.status in {"initializing", "starting", "degraded"}:
            self.health.status = "running"

    async def maintenance(self) -> None:
        """Run periodic maintenance."""
        return None

    async def on_reflect_error(self, exc: Exception) -> None:
        """Hook called when reflect cycle fails."""
        return None

    # ------------------------------------------------------------------
    # Generic builders
    # ------------------------------------------------------------------

    def build_command_from_decision(self, decision: Any) -> Dict[str, Any]:
        """Build canonical command from a meta-agent decision."""
        action = self._extract_decision_action(decision)
        confidence = self._extract_float(decision, "confidence", 0.0)
        rationale = self._extract_string(decision, "rationale", "")
        event_gid = self._extract_string(decision, "event_gid", self.new_gid("decision"))
        target_swarm = self._extract_optional_string(decision, "target_swarm") or self.swarm_type
        target_node = self._extract_optional_string(decision, "target_node")
        payload = self._extract_mapping(decision, "payload")
        provenance = self._extract_mapping(decision, "provenance")

        return make_swarm_command(
            command_type=action,
            source_agent=self.agent_id,
            source_swarm=self.swarm_type,
            parent_gid=event_gid,
            target_swarm=target_swarm,
            target_node=target_node,
            target_role=payload.get("target_role"),
            ttl_seconds=float(payload.get("ttl_seconds", 600.0)),
            priority=int(payload.get("priority", 0)),
            trace_id=payload.get("trace_id"),
            payload={
                "action": action,
                "confidence": confidence,
                "rationale": rationale,
                **payload,
            },
            provenance={
                "agent": self.agent_id,
                "hostname": self.hostname,
                "pid": os.getpid(),
                **provenance,
            },
        )

    def build_decision_event(
        self,
        decision: Any,
        snapshot: Any,
        commands: Sequence[Mapping[str, Any]],
    ) -> Dict[str, Any]:
        """Build canonical policy_evaluated event from a meta-agent decision."""
        action = self._extract_decision_action(decision)
        confidence = self._extract_float(decision, "confidence", 0.0)
        rationale = self._extract_string(decision, "rationale", "")
        parent_gid = self._extract_optional_string(decision, "parent_gid")
        provenance = self._extract_mapping(decision, "provenance")
        trace_id = self._extract_optional_string(decision, "trace_id")

        return make_swarm_event(
            event_type="policy_evaluated",
            source_swarm=self.swarm_type,
            source_agent=self.agent_id,
            source_node=self.agent_id,
            role=self.role,
            parent_gid=parent_gid,
            trace_id=trace_id,
            severity=0.0,
            payload={
                "action": action,
                "confidence": confidence,
                "rationale": rationale,
                "commands_issued": [dict(cmd) for cmd in commands],
                "snapshot_summary": self.summarize_snapshot(snapshot),
            },
            provenance={
                "agent": self.agent_id,
                "hostname": self.hostname,
                "pid": os.getpid(),
                **provenance,
            },
        )

    def build_heartbeat(self) -> Dict[str, Any]:
        """Build canonical meta-agent heartbeat."""
        return make_swarm_heartbeat(
            node_id=self.agent_id,
            agent_id=self.agent_id,
            swarm=self.swarm_type,
            role=self.role,
            version=self.version,
            status=self.health.status,
            metrics=self.health_snapshot(),
            provenance={
                "agent": self.agent_id,
                "hostname": self.hostname,
                "pid": os.getpid(),
            },
        )

    def summarize_snapshot(self, snapshot: Any) -> Mapping[str, Any]:
        """Return serializable snapshot summary for decision events."""
        return summarize_value(snapshot)

    def health_snapshot(self) -> Dict[str, Any]:
        return {
            "uptime_seconds": self.health.uptime_seconds,
            "last_reflect_at": self.health.last_reflect_at,
            "last_collect_at": self.health.last_collect_at,
            "last_decide_at": self.health.last_decide_at,
            "last_command_issue_at": self.health.last_command_issue_at,
            "last_decision_persist_at": self.health.last_decision_persist_at,
            "last_heartbeat_at": self.health.last_heartbeat_at,
            "last_reconcile_at": self.health.last_reconcile_at,
            "last_command_gc_at": self.health.last_command_gc_at,
            "last_healthcheck_at": self.health.last_healthcheck_at,
            "last_maintenance_at": self.health.last_maintenance_at,
            "consecutive_reflect_failures": self.health.consecutive_reflect_failures,
            "consecutive_collect_failures": self.health.consecutive_collect_failures,
            "consecutive_decide_failures": self.health.consecutive_decide_failures,
            "consecutive_command_failures": self.health.consecutive_command_failures,
            "consecutive_persist_failures": self.health.consecutive_persist_failures,
            "consecutive_heartbeat_failures": self.health.consecutive_heartbeat_failures,
            "consecutive_reconcile_failures": self.health.consecutive_reconcile_failures,
            "collected_items_last_cycle": self.health.collected_items_last_cycle,
            "commands_issued_last_cycle": self.health.commands_issued_last_cycle,
            "last_decision": self.health.last_decision,
            "last_error": self.health.last_error,
            "task_count": len(self._tasks),
        }

    # ------------------------------------------------------------------
    # Generic extraction helpers
    # ------------------------------------------------------------------

    def _count_collected_items(self, snapshot: Any) -> int:
        if snapshot is None:
            return 0
        if isinstance(snapshot, Mapping):
            return len(snapshot)
        if isinstance(snapshot, Sequence) and not isinstance(snapshot, (str, bytes, bytearray)):
            return len(snapshot)

        for attr in ("events", "heartbeats", "incidents", "nodes", "signals"):
            value = getattr(snapshot, attr, None)
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
                return len(value)

        return 1

    @staticmethod
    def _extract_mapping(obj: Any, key: str) -> Dict[str, Any]:
        if isinstance(obj, Mapping):
            value = obj.get(key, {})
        else:
            value = getattr(obj, key, {})

        return dict(value) if isinstance(value, Mapping) else {}

    @staticmethod
    def _extract_string(obj: Any, key: str, default: str) -> str:
        if isinstance(obj, Mapping):
            value = obj.get(key, default)
        else:
            value = getattr(obj, key, default)
        return str(value or default)

    @staticmethod
    def _extract_optional_string(obj: Any, key: str) -> Optional[str]:
        if isinstance(obj, Mapping):
            value = obj.get(key)
        else:
            value = getattr(obj, key, None)
        return str(value) if value not in (None, "") else None

    @staticmethod
    def _extract_float(obj: Any, key: str, default: float) -> float:
        if isinstance(obj, Mapping):
            value = obj.get(key, default)
        else:
            value = getattr(obj, key, default)

        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _extract_command_required(obj: Any) -> bool:
        if isinstance(obj, Mapping):
            value = obj.get("command_required", False)
        else:
            value = getattr(obj, "command_required", False)

        if isinstance(value, bool):
            return value

        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _extract_decision_action(obj: Any) -> str:
        if isinstance(obj, Mapping):
            value = obj.get("action", obj.get("decision", "MAINTAIN"))
        else:
            value = getattr(obj, "action", getattr(obj, "decision", "MAINTAIN"))

        return str(value or "MAINTAIN").upper()

    # ------------------------------------------------------------------
    # Signals and resource closing
    # ------------------------------------------------------------------

    def _register_signal_handlers(self, loop: asyncio.AbstractEventLoop) -> None:
        def _handle_signal(sig: signal.Signals) -> None:
            self.logger.info("Received signal %s, requesting shutdown.", sig.name)
            self.request_shutdown()

        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, _handle_signal, sig)
            except NotImplementedError:
                self.logger.debug("Signal handlers are not supported on this platform.")
            except RuntimeError:
                self.logger.debug("Signal handlers can only be registered from the main thread.")
            except Exception as exc:
                self.logger.warning("Failed to register signal handler for %s: %s", sig.name, exc)

    async def _close_crdt_if_supported(self) -> None:
        close = getattr(self.crdt, "close", None)
        if close is None or not callable(close):
            return

        try:
            result = close()
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:
            self.logger.warning("Failed to close CRDT resources: %s", exc, exc_info=True)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def tasks(self) -> Mapping[str, asyncio.Task[Any]]:
        return dict(self._tasks)

    @property
    def is_running(self) -> bool:
        return self.health.status == "running" and not self.shutdown_event.is_set()