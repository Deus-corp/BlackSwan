#!/usr/bin/env python3
"""Production-ready base runtime for global swarm overseers.

An overseer coordinates multiple swarm ecosystems.

Typical cycle:

    collect_all_swarms
        -> global_decide
        -> route_directives
        -> persist_global_decision

This base class intentionally contains no domain-specific policy logic.
Specialized overseers should override:

- collect_all_swarms()
- global_decide()
- route_directives()
- persist_global_decision()
- publish_heartbeat()
- reconcile()
- healthcheck()
- maintenance()
- on_startup()
- on_shutdown()

The overseer sits above meta-agents:

    Overseer
      -> SecurityMetaAgent
          -> SecurityNode x N
      -> ExplorerMetaAgent
          -> ExplorerNode x N
      -> TradeMetaAgent
          -> TradeNode x N
      -> ImproverAgent
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import socket

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Mapping, Optional, Sequence

from src.core.crdt_adapter import CRDTAdapter
from swarm_config import config

from src.swarms.common.utils import (
    expires_in,
    new_gid,
    new_overseer_id,
    summarize_value,
    utc_ts,
)

from src.swarms.common.protocols import (
    make_swarm_command,
    make_swarm_event,
    make_swarm_heartbeat,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BaseOverseerConfig:
    """Runtime configuration for a global swarm overseer."""

    overseer_id: Optional[str] = None
    role: str = "overseer"
    version: str = "0.1.0"

    coordination_interval_seconds: float = 10.0
    heartbeat_interval_seconds: float = 30.0
    directive_gc_interval_seconds: float = 60.0
    reconcile_interval_seconds: float = 10.0
    healthcheck_interval_seconds: float = 15.0
    maintenance_interval_seconds: float = 60.0

    startup_timeout_seconds: float = 30.0
    shutdown_timeout_seconds: float = 30.0

    enable_heartbeat_loop: bool = True
    enable_directive_gc_loop: bool = True
    enable_reconcile_loop: bool = True
    enable_health_loop: bool = True
    enable_maintenance_loop: bool = True

    crdt_db_path: Optional[str] = None
    hostname: str = field(default_factory=socket.gethostname)

    @classmethod
    def default(
        cls,
        *,
        overseer_id: Optional[str] = None,
        version: str = "0.1.0",
    ) -> "BaseOverseerConfig":
        return cls(
            overseer_id=overseer_id,
            version=version,
            crdt_db_path=getattr(config, "crdt_db_path", None),
        )


@dataclass(slots=True)
class OverseerHealth:
    """Mutable health state for a running overseer."""

    status: str = "initializing"
    started_at: float = field(default_factory=utc_ts)

    last_coordinate_at: float = 0.0
    last_collect_at: float = 0.0
    last_decide_at: float = 0.0
    last_route_at: float = 0.0
    last_persist_at: float = 0.0
    last_heartbeat_at: float = 0.0
    last_reconcile_at: float = 0.0
    last_directive_gc_at: float = 0.0
    last_healthcheck_at: float = 0.0
    last_maintenance_at: float = 0.0

    consecutive_coordinate_failures: int = 0
    consecutive_collect_failures: int = 0
    consecutive_decide_failures: int = 0
    consecutive_route_failures: int = 0
    consecutive_persist_failures: int = 0
    consecutive_heartbeat_failures: int = 0
    consecutive_reconcile_failures: int = 0

    swarms_seen_last_cycle: int = 0
    directives_routed_last_cycle: int = 0

    last_decision: str = ""
    last_error: str = ""

    @property
    def uptime_seconds(self) -> float:
        return max(0.0, utc_ts() - self.started_at)


@dataclass(slots=True)
class GlobalDecision:
    """Generic global decision container for overseer cycles."""

    action: str = "MAINTAIN"
    confidence: float = 0.0
    rationale: str = ""
    event_gid: str = ""
    parent_gid: Optional[str] = None
    directives_required: bool = False
    directives: Sequence[Mapping[str, Any]] = field(default_factory=list)
    payload: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)


class BaseSwarmOverseer:
    """Reusable async runtime shell for global swarm overseers."""

    def __init__(
        self,
        *,
        overseer_config: BaseOverseerConfig,
        crdt: Optional[CRDTAdapter] = None,
        logger_name: Optional[str] = None,
    ) -> None:
        self.config = overseer_config

        self.role = overseer_config.role
        self.version = overseer_config.version
        self.hostname = overseer_config.hostname
        self.overseer_id = overseer_config.overseer_id or self._build_overseer_id()

        self.logger = logging.getLogger(logger_name or f"Swarm.Overseer.{self.overseer_id}")

        self.crdt = crdt or CRDTAdapter(
            node_id=self.overseer_id,
            db_path=overseer_config.crdt_db_path or getattr(config, "crdt_db_path", None),
        )

        self.health = OverseerHealth()
        self.shutdown_event = asyncio.Event()
        self.started_event = asyncio.Event()

        self._tasks: Dict[str, asyncio.Task[Any]] = {}
        self._stopping = False
        self._main_task: Optional[asyncio.Task[Any]] = None

    # ------------------------------------------------------------------
    # Identity helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_overseer_id() -> str:
        return new_overseer_id()

    def new_gid(self, prefix: str = "evt") -> str:
        return new_gid(prefix, namespace="overseer")

    # ------------------------------------------------------------------
    # Public lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start overseer runtime and block until shutdown."""
        if self._main_task is not None:
            raise RuntimeError("Overseer is already started")

        self._main_task = asyncio.current_task()
        self.health.status = "starting"

        loop = asyncio.get_running_loop()
        self._register_signal_handlers(loop)

        self.logger.info(
            "Starting overseer %s role=%s version=%s host=%s",
            self.overseer_id,
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

            await self.coordination_loop()

        except asyncio.CancelledError:
            self.logger.info("Overseer %s cancelled.", self.overseer_id)
            raise
        except Exception as exc:
            self.health.status = "failed"
            self.health.last_error = str(exc)
            self.logger.critical("Overseer %s crashed: %s", self.overseer_id, exc, exc_info=True)
            raise
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop overseer runtime gracefully."""
        if self._stopping:
            return

        self._stopping = True
        self.health.status = "stopping"
        self.shutdown_event.set()

        self.logger.info("Stopping overseer %s...", self.overseer_id)

        await self._cancel_background_tasks()

        try:
            await asyncio.wait_for(
                self.on_shutdown(),
                timeout=self.config.shutdown_timeout_seconds,
            )
        except asyncio.TimeoutError:
            self.logger.warning("Overseer %s shutdown hook timed out.", self.overseer_id)
        except Exception as exc:
            self.logger.error("Overseer %s shutdown hook failed: %s", self.overseer_id, exc, exc_info=True)

        await self._close_crdt_if_supported()

        self.health.status = "stopped"
        self.logger.info("Overseer %s stopped.", self.overseer_id)

    def request_shutdown(self) -> None:
        """Request graceful shutdown from sync code or signal handlers."""
        if self.shutdown_event.is_set():
            return
        self.logger.info("Shutdown requested for overseer %s.", self.overseer_id)
        self.shutdown_event.set()

    # ------------------------------------------------------------------
    # Main coordination loop
    # ------------------------------------------------------------------

    async def coordination_loop(self) -> None:
        """Main global orchestration loop."""
        while not self.shutdown_event.is_set():
            started_at = utc_ts()

            try:
                await self.coordinate()
                self.health.last_coordinate_at = utc_ts()
                self.health.consecutive_coordinate_failures = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.health.consecutive_coordinate_failures += 1
                self.health.last_error = str(exc)
                self.logger.error("coordinate failed: %s", exc, exc_info=True)
                await self.on_coordinate_error(exc)

            elapsed = utc_ts() - started_at
            sleep_for = max(0.0, self.config.coordination_interval_seconds - elapsed)

            try:
                await asyncio.wait_for(self.shutdown_event.wait(), timeout=sleep_for)
            except asyncio.TimeoutError:
                pass

    async def coordinate(self) -> Any:
        """Run one collect_all_swarms -> global_decide -> route_directives -> persist cycle."""
        ecosystem_snapshot = await self._safe_collect_all_swarms()
        decision = await self._safe_global_decide(ecosystem_snapshot)
        directives = await self._safe_route_directives(decision, ecosystem_snapshot)
        await self._safe_persist_global_decision(decision, ecosystem_snapshot, directives)

        self.health.last_decision = self._extract_decision_action(decision)
        self.health.directives_routed_last_cycle = len(directives) if isinstance(directives, Sequence) else 0

        return decision

    # ------------------------------------------------------------------
    # Safe wrappers around global hooks
    # ------------------------------------------------------------------

    async def _safe_collect_all_swarms(self) -> Any:
        try:
            snapshot = await self.collect_all_swarms()
            self.health.last_collect_at = utc_ts()
            self.health.consecutive_collect_failures = 0
            self.health.swarms_seen_last_cycle = self._count_swarms(snapshot)
            return snapshot
        except Exception:
            self.health.consecutive_collect_failures += 1
            raise

    async def _safe_global_decide(self, ecosystem_snapshot: Any) -> Any:
        try:
            decision = await self.global_decide(ecosystem_snapshot)
            self.health.last_decide_at = utc_ts()
            self.health.consecutive_decide_failures = 0
            return decision
        except Exception:
            self.health.consecutive_decide_failures += 1
            raise

    async def _safe_route_directives(
        self,
        decision: Any,
        ecosystem_snapshot: Any,
    ) -> Sequence[Mapping[str, Any]]:
        try:
            directives = await self.route_directives(decision, ecosystem_snapshot)
            self.health.last_route_at = utc_ts()
            self.health.consecutive_route_failures = 0
            return directives
        except Exception:
            self.health.consecutive_route_failures += 1
            raise

    async def _safe_persist_global_decision(
        self,
        decision: Any,
        ecosystem_snapshot: Any,
        directives: Sequence[Mapping[str, Any]],
    ) -> None:
        try:
            await self.persist_global_decision(decision, ecosystem_snapshot, directives)
            self.health.last_persist_at = utc_ts()
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

        if self.config.enable_directive_gc_loop:
            self._create_task("directive_gc_loop", self._directive_gc_loop())

        if self.config.enable_reconcile_loop:
            self._create_task("reconcile_loop", self._reconcile_loop())

        if self.config.enable_health_loop:
            self._create_task("health_loop", self._health_loop())

        if self.config.enable_maintenance_loop:
            self._create_task("maintenance_loop", self._maintenance_loop())

    def _create_task(self, name: str, coro: Awaitable[Any]) -> None:
        if name in self._tasks:
            raise RuntimeError(f"Task already exists: {name}")

        task = asyncio.create_task(coro, name=f"{self.overseer_id}:{name}")
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

    async def _directive_gc_loop(self) -> None:
        await self._periodic_loop(
            name="directive_gc",
            interval_seconds=self.config.directive_gc_interval_seconds,
            callback=self._safe_gc_expired_directives,
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
            started_at = utc_ts()

            try:
                await callback()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.health.last_error = str(exc)
                self.logger.error("%s loop failed: %s", name, exc, exc_info=True)

            elapsed = utc_ts() - started_at
            sleep_for = max(0.0, interval_seconds - elapsed)

            try:
                await asyncio.wait_for(self.shutdown_event.wait(), timeout=sleep_for)
            except asyncio.TimeoutError:
                pass

    async def _safe_publish_heartbeat(self) -> None:
        try:
            await self.publish_heartbeat()
            self.health.last_heartbeat_at = utc_ts()
            self.health.consecutive_heartbeat_failures = 0
        except Exception:
            self.health.consecutive_heartbeat_failures += 1
            raise

    async def _safe_gc_expired_directives(self) -> None:
        await self.gc_expired_directives()
        self.health.last_directive_gc_at = utc_ts()

    async def _safe_reconcile(self) -> None:
        try:
            await self.reconcile()
            self.health.last_reconcile_at = utc_ts()
            self.health.consecutive_reconcile_failures = 0
        except Exception:
            self.health.consecutive_reconcile_failures += 1
            raise

    async def _safe_healthcheck(self) -> None:
        await self.healthcheck()
        self.health.last_healthcheck_at = utc_ts()

    async def _safe_maintenance(self) -> None:
        await self.maintenance()
        self.health.last_maintenance_at = utc_ts()

    # ------------------------------------------------------------------
    # Default overridable hooks
    # ------------------------------------------------------------------

    async def on_startup(self) -> None:
        """Hook called before loops are started."""
        return None

    async def on_shutdown(self) -> None:
        """Hook called after loops are cancelled and before CRDT close."""
        return None

    async def collect_all_swarms(self) -> Any:
        """Collect normalized ecosystem-wide state.

        Specialized overseers should override this.
        """
        return self.default_collect_all_swarms()

    async def global_decide(self, ecosystem_snapshot: Any) -> Any:
        """Produce a global decision from ecosystem snapshot."""
        return GlobalDecision(
            action="MAINTAIN",
            confidence=0.0,
            rationale="Default no-op global decision.",
            event_gid=self.new_gid("decision"),
            directives_required=False,
            provenance={"agent": self.overseer_id},
        )

    async def route_directives(
        self,
        decision: Any,
        ecosystem_snapshot: Any,
    ) -> Sequence[Mapping[str, Any]]:
        """Route directives to target swarms/meta-agents.

        Default implementation emits directives listed on the decision object,
        or a single generic directive if directives_required=True.
        """
        explicit_directives = self._extract_directives(decision)
        if explicit_directives:
            routed = []
            for directive in explicit_directives:
                normalized = self._normalize_directive(directive, decision)
                await self.crdt.add_genome(normalized)
                routed.append(normalized)
            return routed

        if not self._extract_directives_required(decision):
            return []

        directive = self.build_directive_from_decision(decision)
        await self.crdt.add_genome(directive)
        return [directive]

    async def persist_global_decision(
        self,
        decision: Any,
        ecosystem_snapshot: Any,
        directives: Sequence[Mapping[str, Any]],
    ) -> None:
        """Persist global decision/event lineage.

        Default implementation emits a global policy_evaluated event to CRDT.
        Specialized overseers should also persist to memory/event store.
        """
        event = self.build_global_decision_event(decision, ecosystem_snapshot, directives)
        await self.crdt.add_genome(event)

    async def publish_heartbeat(self) -> None:
        """Publish generic overseer heartbeat."""
        heartbeat = self.build_heartbeat()
        await self.crdt.add_genome(heartbeat)

    async def gc_expired_directives(self) -> None:
        """Optional hook for expired directive cleanup.

        CRDT adapters may not support deletion, so default is no-op.
        """
        return None

    async def reconcile(self) -> None:
        """Optional hook for global state reconciliation."""
        return None

    async def healthcheck(self) -> None:
        """Run overseer health checks."""
        if self.health.consecutive_coordinate_failures >= 3:
            self.health.status = "degraded"
        elif self.health.status in {"initializing", "starting", "degraded"}:
            self.health.status = "running"

    async def maintenance(self) -> None:
        """Run periodic maintenance."""
        return None

    async def on_coordinate_error(self, exc: Exception) -> None:
        """Hook called when coordinate cycle fails."""
        return None

    # ------------------------------------------------------------------
    # Default CRDT ecosystem collector
    # ------------------------------------------------------------------

    def default_collect_all_swarms(self) -> Dict[str, Any]:
        """Collect a lightweight ecosystem snapshot from generic CRDT records."""
        state = getattr(self.crdt, "state", {})
        if not isinstance(state, Mapping):
            return {
                "swarms": {},
                "records": 0,
            }

        swarms: Dict[str, Dict[str, Any]] = {}

        for value in state.values():
            if not isinstance(value, Mapping):
                continue

            record_type = str(value.get("type", ""))

            swarm = (
                value.get("swarm")
                or value.get("source_swarm")
                or value.get("target_swarm")
                or value.get("data", {}).get("swarm")
                if isinstance(value.get("data"), Mapping)
                else None
            )

            if not swarm and record_type.startswith("security_"):
                swarm = "security"
            elif not swarm and record_type.startswith("explorer_"):
                swarm = "explorer"
            elif not swarm and record_type.startswith("trade_"):
                swarm = "trade"
            elif not swarm and record_type.startswith("meta_"):
                swarm = "meta"

            if not swarm:
                continue

            swarm_name = str(swarm)
            bucket = swarms.setdefault(
                swarm_name,
                {
                    "heartbeats": 0,
                    "events": 0,
                    "commands": 0,
                    "nodes": set(),
                    "latest_ts": 0.0,
                },
            )

            if record_type.endswith("heartbeat") or record_type == "swarm_heartbeat":
                bucket["heartbeats"] += 1
                node_id = value.get("node_id") or value.get("agent_id")
                if node_id:
                    bucket["nodes"].add(str(node_id))
            elif record_type in {"swarm_command", "sec_command", "meta_command_json", "explorer_command"}:
                bucket["commands"] += 1
            else:
                bucket["events"] += 1

            ts = value.get("timestamp", 0.0)
            try:
                bucket["latest_ts"] = max(float(bucket["latest_ts"]), float(ts))
            except (TypeError, ValueError):
                pass

        serializable_swarms: Dict[str, Any] = {}
        for name, bucket in swarms.items():
            serializable_swarms[name] = {
                "heartbeats": bucket["heartbeats"],
                "events": bucket["events"],
                "commands": bucket["commands"],
                "nodes": sorted(bucket["nodes"]),
                "node_count": len(bucket["nodes"]),
                "latest_ts": bucket["latest_ts"],
            }

        return {
            "swarms": serializable_swarms,
            "records": len(state),
            "timestamp": utc_ts(),
        }

    # ------------------------------------------------------------------
    # Generic builders
    # ------------------------------------------------------------------

    def build_directive_from_decision(self, decision: Any) -> Dict[str, Any]:
        """Build canonical overseer directive command from global decision."""
        action = self._extract_decision_action(decision)
        confidence = self._extract_float(decision, "confidence", 0.0)
        rationale = self._extract_string(decision, "rationale", "")
        event_gid = self._extract_string(decision, "event_gid", self.new_gid("decision"))
        payload = self._extract_mapping(decision, "payload")
        provenance = self._extract_mapping(decision, "provenance")

        target_swarm = payload.get("target_swarm") or payload.get("swarm") or "*"
        target_role = payload.get("target_role") or "meta_agent"
        target_node = payload.get("target_node")

        return make_swarm_command(
            command_type=action,
            source_agent=self.overseer_id,
            source_swarm="overseer",
            parent_gid=event_gid,
            target_swarm=str(target_swarm),
            target_node=str(target_node) if target_node else None,
            target_role=str(target_role) if target_role else None,
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
                "agent": self.overseer_id,
                "hostname": self.hostname,
                "pid": os.getpid(),
                **provenance,
            },
        )

    def build_global_decision_event(
        self,
        decision: Any,
        ecosystem_snapshot: Any,
        directives: Sequence[Mapping[str, Any]],
    ) -> Dict[str, Any]:
        """Build canonical global_policy_evaluated event."""
        action = self._extract_decision_action(decision)
        confidence = self._extract_float(decision, "confidence", 0.0)
        rationale = self._extract_string(decision, "rationale", "")
        parent_gid = self._extract_optional_string(decision, "parent_gid")
        provenance = self._extract_mapping(decision, "provenance")
        trace_id = self._extract_optional_string(decision, "trace_id")

        return make_swarm_event(
            event_type="global_policy_evaluated",
            source_swarm="overseer",
            source_agent=self.overseer_id,
            source_node=self.overseer_id,
            role=self.role,
            parent_gid=parent_gid,
            trace_id=trace_id,
            severity=0.0,
            payload={
                "action": action,
                "confidence": confidence,
                "rationale": rationale,
                "directives_routed": [dict(directive) for directive in directives],
                "ecosystem_summary": self.summarize_ecosystem_snapshot(ecosystem_snapshot),
            },
            provenance={
                "agent": self.overseer_id,
                "hostname": self.hostname,
                "pid": os.getpid(),
                **provenance,
            },
        )

    def build_heartbeat(self) -> Dict[str, Any]:
        """Build canonical overseer heartbeat."""
        return make_swarm_heartbeat(
            node_id=self.overseer_id,
            agent_id=self.overseer_id,
            swarm="overseer",
            role=self.role,
            version=self.version,
            status=self.health.status,
            metrics=self.health_snapshot(),
            provenance={
                "agent": self.overseer_id,
                "hostname": self.hostname,
                "pid": os.getpid(),
            },
        )

    def health_snapshot(self) -> Dict[str, Any]:
        return {
            "uptime_seconds": self.health.uptime_seconds,
            "last_coordinate_at": self.health.last_coordinate_at,
            "last_collect_at": self.health.last_collect_at,
            "last_decide_at": self.health.last_decide_at,
            "last_route_at": self.health.last_route_at,
            "last_persist_at": self.health.last_persist_at,
            "last_heartbeat_at": self.health.last_heartbeat_at,
            "last_reconcile_at": self.health.last_reconcile_at,
            "last_directive_gc_at": self.health.last_directive_gc_at,
            "last_healthcheck_at": self.health.last_healthcheck_at,
            "last_maintenance_at": self.health.last_maintenance_at,
            "consecutive_coordinate_failures": self.health.consecutive_coordinate_failures,
            "consecutive_collect_failures": self.health.consecutive_collect_failures,
            "consecutive_decide_failures": self.health.consecutive_decide_failures,
            "consecutive_route_failures": self.health.consecutive_route_failures,
            "consecutive_persist_failures": self.health.consecutive_persist_failures,
            "consecutive_heartbeat_failures": self.health.consecutive_heartbeat_failures,
            "consecutive_reconcile_failures": self.health.consecutive_reconcile_failures,
            "swarms_seen_last_cycle": self.health.swarms_seen_last_cycle,
            "directives_routed_last_cycle": self.health.directives_routed_last_cycle,
            "last_decision": self.health.last_decision,
            "last_error": self.health.last_error,
            "task_count": len(self._tasks),
        }

    def summarize_ecosystem_snapshot(self, snapshot: Any) -> Mapping[str, Any]:
        """Return compact serializable ecosystem snapshot summary."""
        if isinstance(snapshot, Mapping):
            swarms = snapshot.get("swarms")
            if isinstance(swarms, Mapping):
                return {
                    "type": "ecosystem",
                    "swarm_count": len(swarms),
                    "swarms": {
                        str(name): {
                            "node_count": data.get("node_count"),
                            "heartbeats": data.get("heartbeats"),
                            "events": data.get("events"),
                            "commands": data.get("commands"),
                            "latest_ts": data.get("latest_ts"),
                        }
                        for name, data in swarms.items()
                        if isinstance(data, Mapping)
                    },
                }

        return summarize_value(snapshot)

    # ------------------------------------------------------------------
    # Directive normalization
    # ------------------------------------------------------------------

    def _normalize_directive(self, directive: Mapping[str, Any], decision: Any) -> Dict[str, Any]:
        """Normalize explicit overseer directive into canonical swarm_command."""
        if directive.get("type") == "swarm_command":
            normalized = dict(directive)
            normalized.setdefault("gid", self.new_gid("directive"))
            normalized.setdefault("source_agent", self.overseer_id)
            normalized.setdefault("source_swarm", "overseer")
            normalized.setdefault("parent_gid", self._extract_string(decision, "event_gid", self.new_gid("decision")))
            normalized.setdefault("provenance", {"agent": self.overseer_id})
            return normalized

        action = str(
            directive.get("action")
            or directive.get("command_type")
            or self._extract_decision_action(decision)
        ).upper()

        payload = dict(directive.get("payload", {})) if isinstance(directive.get("payload"), Mapping) else {}
        data = dict(directive.get("data", {})) if isinstance(directive.get("data"), Mapping) else {}

        merged_payload = {
            **data,
            **payload,
        }

        target_swarm = directive.get("target_swarm") or merged_payload.get("target_swarm") or "*"
        target_role = directive.get("target_role") or merged_payload.get("target_role") or "meta_agent"
        target_node = directive.get("target_node") or merged_payload.get("target_node")

        provenance = directive.get("provenance") if isinstance(directive.get("provenance"), Mapping) else {}

        return make_swarm_command(
            command_type=action,
            source_agent=self.overseer_id,
            source_swarm="overseer",
            parent_gid=str(
                directive.get("parent_gid")
                or self._extract_string(decision, "event_gid", self.new_gid("decision"))
            ),
            target_swarm=str(target_swarm),
            target_node=str(target_node) if target_node else None,
            target_role=str(target_role) if target_role else None,
            ttl_seconds=float(merged_payload.get("ttl_seconds", 600.0)),
            priority=int(merged_payload.get("priority", directive.get("priority", 0) or 0)),
            trace_id=merged_payload.get("trace_id") or directive.get("trace_id"),
            payload={
                "action": action,
                **merged_payload,
            },
            provenance={
                "agent": self.overseer_id,
                **dict(provenance),
            },
        )

    # ------------------------------------------------------------------
    # Generic extraction helpers
    # ------------------------------------------------------------------

    def _count_swarms(self, snapshot: Any) -> int:
        if isinstance(snapshot, Mapping):
            swarms = snapshot.get("swarms")
            if isinstance(swarms, Mapping):
                return len(swarms)
            return len(snapshot)
        if isinstance(snapshot, Sequence) and not isinstance(snapshot, (str, bytes, bytearray)):
            return len(snapshot)
        return 1 if snapshot is not None else 0

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
    def _extract_directives_required(obj: Any) -> bool:
        if isinstance(obj, Mapping):
            value = obj.get("directives_required", obj.get("command_required", False))
        else:
            value = getattr(obj, "directives_required", getattr(obj, "command_required", False))

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

    @staticmethod
    def _extract_directives(obj: Any) -> Sequence[Mapping[str, Any]]:
        if isinstance(obj, Mapping):
            value = obj.get("directives", [])
        else:
            value = getattr(obj, "directives", [])

        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            return []

        return [item for item in value if isinstance(item, Mapping)]

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