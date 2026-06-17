#!/usr/bin/env python3
"""Production-ready base runtime for swarm node agents.

This module provides a reusable lifecycle shell for specialized swarm nodes.

It intentionally knows nothing about trading, security, exploration, mutation,
or any other domain logic. Domain-specific agents should subclass BaseSwarmNode
and override lifecycle hooks such as:

- on_startup()
- process_tick()
- process_command()
- reconcile()
- publish_heartbeat()
- on_shutdown()

Design goals:
- stable async lifecycle
- task supervision
- graceful shutdown
- signal handling
- CRDT wiring
- heartbeat loop
- reconciliation loop
- command polling loop
- health loop
- extension-friendly hooks
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import socket
import sys

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Iterable, Mapping, Optional, Set

from src.core.crdt_adapter import CRDTAdapter
from swarm_config import config

from src.swarms.common.utils import (
    expires_in,
    is_expired,
    new_gid,
    new_node_id,
    summarize_value,
    utc_ts,
)

from src.swarms.common.protocols import (
    command_is_expired,
    command_targets,
    make_swarm_heartbeat,
    is_lifecycle_command,
    lifecycle_action,
    lifecycle_applies_to,
    lifecycle_reason,
    lifecycle_summary,
    LIFECYCLE_EVENT_APPLIED,
    lifecycle_event_payload,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BaseNodeConfig:
    """Runtime configuration for a generic swarm node."""

    swarm_type: str
    role: str = "node"
    node_id: Optional[str] = None
    version: str = "0.1.0"

    tick_interval_seconds: float = 1.0
    heartbeat_interval_seconds: float = 30.0
    command_poll_interval_seconds: float = 2.0
    reconcile_interval_seconds: float = 5.0
    healthcheck_interval_seconds: float = 15.0
    maintenance_interval_seconds: float = 60.0

    startup_timeout_seconds: float = 30.0
    shutdown_timeout_seconds: float = 30.0

    enable_heartbeat_loop: bool = True
    enable_command_loop: bool = True
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
        role: str = "node",
        node_id: Optional[str] = None,
        version: str = "0.1.0",
    ) -> "BaseNodeConfig":
        return cls(
            swarm_type=swarm_type,
            role=role,
            node_id=node_id,
            version=version,
            crdt_db_path=getattr(config, "crdt_db_path", None),
        )


@dataclass(slots=True)
class NodeHealth:
    """Mutable health state for a running node."""

    status: str = "initializing"
    paused: bool = False
    started_at: float = field(default_factory=utc_ts)
    last_tick_at: float = 0.0
    last_heartbeat_at: float = 0.0
    last_command_poll_at: float = 0.0
    last_reconcile_at: float = 0.0
    last_healthcheck_at: float = 0.0
    last_maintenance_at: float = 0.0
    consecutive_tick_failures: int = 0
    consecutive_command_failures: int = 0
    consecutive_reconcile_failures: int = 0
    consecutive_heartbeat_failures: int = 0
    last_error: str = ""

    @property
    def uptime_seconds(self) -> float:
        return max(0.0, utc_ts() - self.started_at)


class BaseSwarmNode:
    """Reusable async runtime shell for specialized swarm nodes.

    Subclasses usually override:
    - on_startup()
    - process_tick()
    - process_command()
    - publish_heartbeat()
    - reconcile()
    - healthcheck()
    - maintenance()
    - on_shutdown()
    """

    def __init__(
        self,
        *,
        node_config: BaseNodeConfig,
        crdt: Optional[CRDTAdapter] = None,
        logger_name: Optional[str] = None,
    ) -> None:
        self.config = node_config

        self.swarm_type = node_config.swarm_type
        self.role = node_config.role
        self.version = node_config.version
        self.hostname = node_config.hostname
        self.node_id = node_config.node_id or self._build_node_id(node_config.swarm_type)

        self.logger = logging.getLogger(logger_name or f"Swarm.{self.swarm_type}.{self.node_id}")

        self.crdt = crdt or CRDTAdapter(
            node_id=self.node_id,
            db_path=node_config.crdt_db_path or getattr(config, "crdt_db_path", None),
        )

        self.health = NodeHealth()
        self.shutdown_event = asyncio.Event()
        self.started_event = asyncio.Event()

        self._command_consumer_started_at = utc_ts()
        self._command_history_grace_seconds = float(
            os.getenv("SWARM_COMMAND_HISTORY_GRACE_SECONDS", "5")
        )
        self._processed_command_gids: set[str] = set()

        self._tasks: Dict[str, asyncio.Task[Any]] = {}
        self._stopping = False
        self._main_task: Optional[asyncio.Task[Any]] = None

    # ---------------------------------------------------------------------
    # Identity helpers
    # ---------------------------------------------------------------------

    @staticmethod
    def _build_node_id(swarm_type: str) -> str:
        return new_node_id(swarm_type)

    def new_gid(self, prefix: str = "evt") -> str:
        return new_gid(prefix, namespace=self.swarm_type)

    async def handle_lifecycle_command(self, command: Mapping[str, Any]) -> bool:
        """Handle common lifecycle commands.

        Returns True if command was lifecycle command and was handled/skipped
        by lifecycle layer.

        Specialized swarm commands should continue after this only when this
        method returns False.
        """
        if not is_lifecycle_command(command):
            return False

        node_id = str(getattr(self, "node_id", "") or getattr(self, "agent_id", ""))
        swarm_type = str(getattr(self, "swarm_type", "") or getattr(self, "swarm", ""))
        role = str(getattr(self, "role", ""))

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
            self.logger.info("%s %s paused by lifecycle command.", type(self).__name__, node_id)
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
            self.logger.info("%s %s resumed by lifecycle command.", type(self).__name__, node_id)
            return True

        if action == "RESTART_NODE":
            await self._emit_lifecycle_event(
                action=action,
                status="applied",
                reason=reason,
                parent_gid=command_gid,
                command=command,
            )
            self.logger.critical("%s %s received lifecycle RESTART_NODE.", type(self).__name__, node_id)
            sys.exit(0)

        if action == "RUN_ONCE":
            handled = await self._run_lifecycle_once(command)
            await self._emit_lifecycle_event(
                action=action,
                status="applied" if handled else "unsupported",
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

    # ---------------------------------------------------------------------
    # Public lifecycle
    # ---------------------------------------------------------------------

    async def start(self) -> None:
        """Start the node runtime and block until shutdown."""
        if self._main_task is not None:
            raise RuntimeError("Node is already started")

        self._main_task = asyncio.current_task()
        self.health.status = "starting"

        loop = asyncio.get_running_loop()
        self._register_signal_handlers(loop)

        self.logger.info(
            "Starting %s node %s role=%s version=%s host=%s",
            self.swarm_type,
            self.node_id,
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

            await self.main_loop()

        except asyncio.CancelledError:
            self.logger.info("Node %s cancelled.", self.node_id)
            raise
        except Exception as exc:
            self.health.status = "failed"
            self.health.last_error = str(exc)
            self.logger.critical("Node %s crashed: %s", self.node_id, exc, exc_info=True)
            raise
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop the node runtime gracefully."""
        if self._stopping:
            return

        self._stopping = True
        self.health.status = "stopping"
        self.shutdown_event.set()

        self.logger.info("Stopping node %s...", self.node_id)

        await self._cancel_background_tasks()

        try:
            await asyncio.wait_for(
                self.on_shutdown(),
                timeout=self.config.shutdown_timeout_seconds,
            )
        except asyncio.TimeoutError:
            self.logger.warning("Node %s shutdown hook timed out.", self.node_id)
        except Exception as exc:
            self.logger.error("Node %s shutdown hook failed: %s", self.node_id, exc, exc_info=True)

        await self._close_crdt_if_supported()

        self.health.status = "stopped"
        self.logger.info("Node %s stopped.", self.node_id)

    def request_shutdown(self) -> None:
        """Request graceful shutdown from sync code or signal handlers."""
        if self.shutdown_event.is_set():
            return
        self.logger.info("Shutdown requested for node %s.", self.node_id)
        self.shutdown_event.set()

    # ---------------------------------------------------------------------
    # Main orchestration
    # ---------------------------------------------------------------------

    async def main_loop(self) -> None:
        """Main domain tick loop.

        Subclasses should implement process_tick(); this loop provides the
        runtime shell, interval scheduling, pause handling, and failure
        accounting.

        Command/background loops remain active while paused so RESUME can be
        received and applied.
        """
        while not self.shutdown_event.is_set():
            started_at = utc_ts()
            try:
                if self.is_paused():
                    self.health.status = "paused"
                    self.health.paused = True
                    self.logger.debug(
                        "%s %s is paused; skipping process_tick.",
                        type(self).__name__,
                        self.node_id,
                    )
                else:
                    if self.health.status == "paused":
                        self.health.status = "running"
                    self.health.paused = False
                    await self.process_tick()
                    self.health.last_tick_at = utc_ts()
                    self.health.consecutive_tick_failures = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.health.consecutive_tick_failures += 1
                self.health.last_error = str(exc)
                self.logger.error("process_tick failed: %s", exc, exc_info=True)
                await self.on_tick_error(exc)

            elapsed = utc_ts() - started_at
            sleep_for = max(0.0, self.config.tick_interval_seconds - elapsed)

            try:
                await asyncio.wait_for(self.shutdown_event.wait(), timeout=sleep_for)
            except asyncio.TimeoutError:
                pass

    def _start_background_loops(self) -> None:
        if self.config.enable_heartbeat_loop:
            self._create_task("heartbeat_loop", self._heartbeat_loop())

        if self.config.enable_command_loop:
            self._create_task("command_loop", self._command_loop())

        if self.config.enable_reconcile_loop:
            self._create_task("reconcile_loop", self._reconcile_loop())

        if self.config.enable_health_loop:
            self._create_task("health_loop", self._health_loop())

        if self.config.enable_maintenance_loop:
            self._create_task("maintenance_loop", self._maintenance_loop())

    def _create_task(self, name: str, coro: Awaitable[Any]) -> None:
        if name in self._tasks:
            raise RuntimeError(f"Task already exists: {name}")

        task = asyncio.create_task(coro, name=f"{self.node_id}:{name}")
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

    # ---------------------------------------------------------------------
    # Background loops
    # ---------------------------------------------------------------------

    async def _heartbeat_loop(self) -> None:
        await self._periodic_loop(
            name="heartbeat",
            interval_seconds=self.config.heartbeat_interval_seconds,
            callback=self._safe_publish_heartbeat,
        )

    async def _command_loop(self) -> None:
        await self._periodic_loop(
            name="command_poll",
            interval_seconds=self.config.command_poll_interval_seconds,
            callback=self._safe_poll_commands,
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

    # ---------------------------------------------------------------------
    # Safe wrappers around overridable hooks
    # ---------------------------------------------------------------------

    async def _safe_publish_heartbeat(self) -> None:
        try:
            await self.publish_heartbeat()
            self.health.last_heartbeat_at = utc_ts()
            self.health.consecutive_heartbeat_failures = 0
        except Exception:
            self.health.consecutive_heartbeat_failures += 1
            raise

    async def _safe_poll_commands(self) -> None:
        try:
            commands = await self.poll_commands()
            self.health.last_command_poll_at = utc_ts()
            self.health.consecutive_command_failures = 0

            for command in commands:
                if self._should_skip_command_record(command):
                    continue

                await self.process_command(command)
        except Exception:
            self.health.consecutive_command_failures += 1
            raise

    def _should_skip_command_record(self, command: Mapping[str, Any]) -> bool:
        """Return True when a command should not be consumed by this runtime.

        This protects live nodes from replaying historical CRDT commands on
        startup and from re-processing expired or already-seen commands.
        """
        if not isinstance(command, Mapping):
            return True

        gid = str(command.get("gid") or "")
        if gid and gid in self._processed_command_gids:
            return True

        now = utc_ts()

        expires_at = command.get("expires_at")
        if expires_at is not None:
            try:
                if float(expires_at) < now:
                    if gid:
                        self._processed_command_gids.add(gid)
                    return True
            except Exception:
                pass

        timestamp = command.get("timestamp")
        if timestamp is not None:
            try:
                command_ts = float(timestamp)
                if command_ts < self._command_consumer_started_at - self._command_history_grace_seconds:
                    if gid:
                        self._processed_command_gids.add(gid)
                    return True
            except Exception:
                pass

        if gid:
            self._processed_command_gids.add(gid)

        return False

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

    # ---------------------------------------------------------------------
    # Default hook implementations
    # ---------------------------------------------------------------------

    async def on_startup(self) -> None:
        """Hook called before loops are started."""
        return None

    async def on_shutdown(self) -> None:
        """Hook called after loops are cancelled and before CRDT close."""
        return None

    async def process_tick(self) -> None:
        """Main node work unit.

        Subclasses should override this method.
        """
        await asyncio.sleep(0)

    async def on_tick_error(self, exc: Exception) -> None:
        """Hook called when process_tick fails."""
        return None

    async def poll_commands(self) -> Iterable[Mapping[str, Any]]:
        """Return commands relevant to this node.

        Default implementation scans CRDT for commands targeting this exact node,
        swarm, or role. Supports both canonical and legacy command formats through
        common.protocols.commands.
        """
        state = getattr(self.crdt, "state", {})
        if not isinstance(state, Mapping):
            return []

        commands: list[Mapping[str, Any]] = []

        for value in state.values():
            if not isinstance(value, Mapping):
                continue

            try:
                if command_is_expired(value):
                    continue

                if command_targets(
                    value,
                    swarm=self.swarm_type,
                    node_id=self.node_id,
                    role=self.role,
                ):
                    commands.append(value)
            except ValueError:
                continue

        return commands

    async def process_command(self, command: Mapping[str, Any]) -> None:
        if await self.handle_lifecycle_command(command):
            return
        """Process a command.

        Subclasses should override this. The default only handles shutdown.
        """
        data = command.get("data") if isinstance(command.get("data"), Mapping) else {}
        action = str(data.get("action", command.get("action", ""))).upper()

        if action in {"STOP_NODE", "SHUTDOWN"}:
            self.request_shutdown()

    async def reconcile(self) -> None:
        """Reconcile local state with swarm state."""
        return None

    async def healthcheck(self) -> None:
        """Run health checks.

        The default marks the node degraded if tick failures are accumulating.
        """
        if self.health.consecutive_tick_failures >= 3:
            self.health.status = "degraded"
        elif self.health.status in {"initializing", "starting", "degraded"}:
            self.health.status = "running"

    async def maintenance(self) -> None:
        """Run periodic maintenance."""
        return None

    async def publish_heartbeat(self) -> None:
        """Publish a generic canonical heartbeat to CRDT.

        Specialized nodes may override build_heartbeat() to add domain metrics,
        or override publish_heartbeat() if they also need legacy compatibility
        records.
        """
        heartbeat = self.build_heartbeat()
        await self.crdt.add_genome(heartbeat)

    def build_heartbeat(self) -> Dict[str, Any]:
        """Build a canonical CRDT-compatible heartbeat payload."""
        return make_swarm_heartbeat(
            node_id=self.node_id,
            agent_id=self.node_id,
            swarm=self.swarm_type,
            role=self.role,
            version=self.version,
            status=self.health.status,
            metrics=self.health_snapshot(),
            provenance={
                "agent": self.node_id,
                "hostname": self.hostname,
                "pid": os.getpid(),
            },
        )

    def health_snapshot(self) -> Dict[str, Any]:
        """Return serializable health state."""
        return {
            "uptime_seconds": self.health.uptime_seconds,
            "paused": self.health.paused,
            "last_tick_at": self.health.last_tick_at,
            "last_heartbeat_at": self.health.last_heartbeat_at,
            "last_command_poll_at": self.health.last_command_poll_at,
            "last_reconcile_at": self.health.last_reconcile_at,
            "last_healthcheck_at": self.health.last_healthcheck_at,
            "last_maintenance_at": self.health.last_maintenance_at,
            "consecutive_tick_failures": self.health.consecutive_tick_failures,
            "consecutive_command_failures": self.health.consecutive_command_failures,
            "consecutive_reconcile_failures": self.health.consecutive_reconcile_failures,
            "consecutive_heartbeat_failures": self.health.consecutive_heartbeat_failures,
            "last_error": self.health.last_error,
            "task_count": len(self._tasks),
        }

    # ---------------------------------------------------------------------
    # Command targeting
    # ---------------------------------------------------------------------

    def _command_targets_this_node(self, command: Mapping[str, Any]) -> bool:
        data = command.get("data") if isinstance(command.get("data"), Mapping) else {}

        target_node = command.get("target_node") or command.get("target_node_id") or data.get("node_id")
        target_swarm = command.get("target_swarm") or command.get("swarm") or data.get("swarm")
        target_role = command.get("target_role") or data.get("role")

        if target_node and str(target_node) not in {self.node_id, "*"}:
            return False

        if target_swarm and str(target_swarm) not in {self.swarm_type, "*"}:
            return False

        if target_role and str(target_role) not in {self.role, "*"}:
            return False

        return True

    # ---------------------------------------------------------------------
    # Signals and resource closing
    # ---------------------------------------------------------------------

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

    # ---------------------------------------------------------------------
    # Introspection
    # ---------------------------------------------------------------------

    @property
    def tasks(self) -> Mapping[str, asyncio.Task[Any]]:
        return dict(self._tasks)

    @property
    def is_running(self) -> bool:
        return self.health.status == "running" and not self.shutdown_event.is_set()

    def _set_runtime_paused(self, paused: bool) -> None:
        """Set paused flag across known runtime shapes.

        Different swarms historically used different fields:
        - self.paused
        - self._paused
        - self.health.paused
        - self.metrics["paused"]
        - self.runtime_metrics["paused"]

        Keep all common shapes synchronized.
        """
        value = bool(paused)

        if hasattr(self.health, "paused"):
            self.health.paused = value

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

        ctx = getattr(self, "ctx", None)
        if ctx is not None:
            try:
                setattr(ctx, "paused", value)
            except Exception:
                pass

    def is_paused(self) -> bool:
        """Return current paused state across known runtime shapes."""
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

    async def _run_lifecycle_once(self, command: Mapping[str, Any]) -> bool:
        """Run one lifecycle cycle if subclass exposes a compatible hook."""
        for method_name in ("run_once", "_run_once", "run_single_cycle", "_run_single_cycle"):
            method = getattr(self, method_name, None)
            if callable(method):
                result = method(command)
                if hasattr(result, "__await__"):
                    await result
                return True

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
        """Emit canonical lifecycle event if CRDT/event helpers are available."""
        crdt = getattr(self, "crdt", None)
        if crdt is None or not hasattr(crdt, "add_genome"):
            return

        node_id = str(getattr(self, "node_id", "") or getattr(self, "agent_id", ""))
        swarm_type = str(getattr(self, "swarm_type", "") or getattr(self, "swarm", ""))
        role = str(getattr(self, "role", ""))

        event = {
            "type": "swarm_event",
            "event_type": LIFECYCLE_EVENT_APPLIED,
            "gid": self.new_gid("lifecycle_evt") if hasattr(self, "new_gid") else "",
            "source_swarm": swarm_type,
            "source_agent": node_id,
            "source_node": node_id,
            "role": role,
            "parent_gid": parent_gid,
            "timestamp": utc_ts(),
            "payload": lifecycle_event_payload(
                command,
                status=status,
                reason=reason,
            ),
            "provenance": {
                "agent": node_id,
                "source": "common_lifecycle",
            },
        }

        await crdt.add_genome(event)