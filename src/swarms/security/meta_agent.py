#!/usr/bin/env python3
"""Security MetaAgent – swarm-level security coordinator.

This meta-agent is based on the shared BaseSwarmMetaAgent runtime.

Responsibilities:
- collect security heartbeats, events, and commands from CRDT
- normalize legacy/canonical records through common protocols
- evaluate security policy
- issue commands to security nodes
- persist policy decisions and event lineage

It must NOT manipulate firewall directly. Firewall execution belongs to
SecurityNode.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from src.swarms.common import (
    BaseMetaAgentConfig,
    BaseSwarmMetaAgent,
    MetaDecision,
    age_seconds,
    command_action,
    make_swarm_event,
    normalize_commands,
    normalize_events,
    normalize_heartbeats,
)
from src.swarms.security.node_core import (
    SecurityMemory,
    SecurityPolicy,
    new_gid,
)
from swarm_config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
)

logger = logging.getLogger("SecurityMetaAgent")


@dataclass(frozen=True, slots=True)
class SecurityMetaSnapshot:
    """Normalized security swarm snapshot."""

    heartbeats: List[Dict[str, Any]] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    commands: List[Dict[str, Any]] = field(default_factory=list)

    node_count: int = 0
    stale_nodes: List[str] = field(default_factory=list)

    blocked_ips: int = 0
    active_blocks: int = 0

    critical_events: int = 0
    vulnerability_alerts: int = 0
    integrity_alerts: int = 0
    open_port_alerts: int = 0

    latest_event_ts: float = 0.0

    def is_empty(self) -> bool:
        return not self.heartbeats and not self.events and not self.commands


class SecurityMetaAgent(BaseSwarmMetaAgent):
    """Security swarm meta-agent on the common runtime."""

    def __init__(
        self,
        node_id: Optional[str] = None,
        memory_db: Optional[Path] = None,
    ) -> None:
        agent_id = node_id or f"sec-meta-{uuid.uuid4().hex[:8]}"

        super().__init__(
            meta_config=BaseMetaAgentConfig(
                swarm_type="security",
                role="meta_agent",
                agent_id=agent_id,
                version="0.2.0",
                reflect_interval_seconds=3.0,
                heartbeat_interval_seconds=30.0,
                command_gc_interval_seconds=60.0,
                reconcile_interval_seconds=10.0,
                healthcheck_interval_seconds=15.0,
                maintenance_interval_seconds=60.0,
                crdt_db_path=config.crdt_db_path,
            ),
            logger_name="SecurityMetaAgent",
        )

        self._repo_root = Path(__file__).resolve().parents[3]

        if memory_db is None:
            memory_db = self._repo_root / "data" / "security_meta_memory.sqlite3"

        self.memory = SecurityMemory(memory_db)
        self.policy = SecurityPolicy.from_env()

        self.logger.info("🔐 SecurityMetaAgent initialized: %s", self.agent_id)

    # ------------------------------------------------------------------
    # BaseSwarmMetaAgent hooks
    # ------------------------------------------------------------------

    async def on_startup(self) -> None:
        self.logger.info(
            "SecurityMetaAgent %s startup complete. policy=%s",
            self.agent_id,
            self.policy,
        )

    async def collect(self) -> SecurityMetaSnapshot:
        """Collect and normalize security swarm state from CRDT."""
        state = getattr(self.crdt, "state", {})
        if not isinstance(state, Mapping):
            return SecurityMetaSnapshot()

        values = list(state.values())

        heartbeats = [
            hb
            for hb in normalize_heartbeats(values)
            if hb.get("swarm") == "security"
        ]

        events = [
            event
            for event in normalize_events(values)
            if event.get("source_swarm") == "security"
        ]

        commands = [
            cmd
            for cmd in normalize_commands(values)
            if cmd.get("target_swarm") in {"security", "*", None}
            or cmd.get("source_swarm") == "security"
        ]

        stale_nodes: List[str] = []
        blocked_ips = 0

        for hb in heartbeats:
            node_id = str(hb.get("node_id") or hb.get("agent_id") or "")
            metrics = hb.get("metrics") if isinstance(hb.get("metrics"), Mapping) else {}

            blocked_ips += self._safe_int(metrics.get("blocked_ips", 0))

            timestamp = hb.get("timestamp")
            if age_seconds(timestamp) > self.policy.heartbeat_staleness_seconds:
                if node_id:
                    stale_nodes.append(node_id)

            self._persist_heartbeat_if_possible(hb)

        critical_events = 0
        vulnerability_alerts = 0
        integrity_alerts = 0
        open_port_alerts = 0
        latest_event_ts = 0.0

        for event in events:
            event_type = str(event.get("event_type") or "")
            severity = self._safe_float(event.get("severity", 0.0))

            if severity >= 0.9:
                critical_events += 1

            if "vulnerability" in event_type:
                vulnerability_alerts += 1
            if "integrity" in event_type:
                integrity_alerts += 1
            if "open_ports" in event_type:
                open_port_alerts += 1

            latest_event_ts = max(latest_event_ts, self._safe_float(event.get("timestamp", 0.0)))
            self._persist_incident_if_possible(event)

        active_blocks = self._safe_call_int(self.memory.active_block_count)

        return SecurityMetaSnapshot(
            heartbeats=heartbeats,
            events=events,
            commands=commands,
            node_count=len({str(hb.get("node_id") or hb.get("agent_id")) for hb in heartbeats}),
            stale_nodes=sorted(set(stale_nodes)),
            blocked_ips=blocked_ips,
            active_blocks=active_blocks,
            critical_events=critical_events,
            vulnerability_alerts=vulnerability_alerts,
            integrity_alerts=integrity_alerts,
            open_port_alerts=open_port_alerts,
            latest_event_ts=latest_event_ts,
        )

    async def decide(self, snapshot: SecurityMetaSnapshot) -> MetaDecision:
        """Evaluate security policy and return a meta decision."""
        event_gid = new_gid("sec_policy")

        if snapshot.is_empty():
            return MetaDecision(
                action="MAINTAIN",
                confidence=0.0,
                rationale="No security signals available.",
                event_gid=event_gid,
                command_required=False,
                target_swarm="security",
                target_node=None,
                payload={},
                provenance={"agent": self.agent_id, "policy": "security_meta"},
            )

        if (
            snapshot.critical_events > 0
            and self.policy.allow_emergency_flush_input
            and snapshot.active_blocks < self.policy.max_blocked_ips_soft
        ):
            return MetaDecision(
                action="EMERGENCY_FLUSH_INPUT",
                confidence=0.9,
                rationale=(
                    "Critical security event detected and emergency flush is enabled "
                    "by policy."
                ),
                event_gid=event_gid,
                command_required=True,
                target_swarm="security",
                target_node=None,
                payload={
                    "target_role": "node",
                    "critical_events": snapshot.critical_events,
                    "ttl_seconds": 600,
                },
                provenance={"agent": self.agent_id, "policy": "security_meta"},
            )

        if (
            snapshot.active_blocks > self.policy.max_blocked_ips_soft
            and self.policy.allow_global_unblock
        ):
            return MetaDecision(
                action="UNBLOCK_ALL",
                confidence=0.82,
                rationale=(
                    f"Active block count {snapshot.active_blocks} exceeds soft limit "
                    f"{self.policy.max_blocked_ips_soft}; global unblock is enabled."
                ),
                event_gid=event_gid,
                command_required=True,
                target_swarm="security",
                target_node=None,
                payload={
                    "target_role": "node",
                    "active_blocks": snapshot.active_blocks,
                    "soft_limit": self.policy.max_blocked_ips_soft,
                    "ttl_seconds": 600,
                },
                provenance={"agent": self.agent_id, "policy": "security_meta"},
            )

        if len(snapshot.stale_nodes) >= 3:
            return MetaDecision(
                action="ESCALATE",
                confidence=0.78,
                rationale=f"Multiple stale security nodes detected: {snapshot.stale_nodes}",
                event_gid=event_gid,
                command_required=False,
                target_swarm="security",
                target_node=None,
                payload={
                    "stale_nodes": snapshot.stale_nodes,
                    "target_role": "meta_agent",
                },
                provenance={"agent": self.agent_id, "policy": "security_meta"},
            )

        return MetaDecision(
            action="MAINTAIN",
            confidence=0.86,
            rationale=(
                "Security posture stable. "
                f"nodes={snapshot.node_count}, active_blocks={snapshot.active_blocks}, "
                f"critical_events={snapshot.critical_events}"
            ),
            event_gid=event_gid,
            command_required=False,
            target_swarm="security",
            target_node=None,
            payload={
                "node_count": snapshot.node_count,
                "active_blocks": snapshot.active_blocks,
                "blocked_ips": snapshot.blocked_ips,
                "critical_events": snapshot.critical_events,
                "stale_nodes": snapshot.stale_nodes,
            },
            provenance={"agent": self.agent_id, "policy": "security_meta"},
        )

    async def issue_commands(
        self,
        decision: Any,
        snapshot: Any,
    ) -> Sequence[Mapping[str, Any]]:
        """Issue security commands.

        Uses the base implementation for canonical swarm_command emission.
        Also records command metadata into SecurityMemory.
        """
        commands = await super().issue_commands(decision, snapshot)

        for command in commands:
            self._persist_command_if_possible(command, decision)

        return commands

    async def persist_decision(
        self,
        decision: Any,
        snapshot: Any,
        commands: Sequence[Mapping[str, Any]],
    ) -> None:
        """Persist decision into SecurityMemory and emit canonical event."""
        await super().persist_decision(decision, snapshot, commands)

        action = self._extract_decision_action(decision)
        confidence = self._extract_float(decision, "confidence", 0.0)
        rationale = self._extract_string(decision, "rationale", "")
        event_gid = self._extract_string(decision, "event_gid", new_gid("sec_policy"))
        parent_gid = self._extract_optional_string(decision, "parent_gid")
        provenance = self._extract_mapping(decision, "provenance")

        if hasattr(self.memory, "record_policy_decision"):
            try:
                self.memory.record_policy_decision(
                    event_gid=event_gid,
                    parent_gid=parent_gid,
                    decision=action,
                    confidence=confidence,
                    rationale=rationale,
                    model_name="deterministic_security_policy",
                    prompt_hash="",
                    provenance={
                        "agent": self.agent_id,
                        **provenance,
                    },
                )
            except Exception as exc:
                self.logger.warning("Failed to persist policy decision: %s", exc)

        if hasattr(self.memory, "record_event_chain"):
            try:
                self.memory.record_event_chain(
                    event_gid=event_gid,
                    parent_gid=parent_gid,
                    source_gid=self.agent_id,
                    event_type="policy_evaluated",
                    action=action,
                    status="evaluated",
                    details={
                        "confidence": confidence,
                        "rationale": rationale,
                        "commands_issued": len(commands),
                        "snapshot": self.summarize_snapshot(snapshot),
                    },
                    provenance={
                        "agent": self.agent_id,
                        **provenance,
                    },
                )
            except Exception as exc:
                self.logger.warning("Failed to persist event chain decision: %s", exc)

    async def publish_heartbeat(self) -> None:
        """Publish canonical heartbeat plus legacy meta heartbeat for compatibility."""
        await super().publish_heartbeat()

        legacy = {
            "type": "meta_heartbeat",
            "gid": new_gid("sec_meta_hb"),
            "node_id": self.agent_id,
            "agent_id": self.agent_id,
            "swarm": "security",
            "role": "meta_agent",
            "status": self.health.status,
            "timestamp": self.health.last_heartbeat_at,
            "provenance": {
                "agent": self.agent_id,
                "active_blocks": self._safe_call_int(self.memory.active_block_count),
            },
        }

        await self.crdt.add_genome(legacy)

    async def healthcheck(self) -> None:
        """Security meta-agent healthcheck."""
        await super().healthcheck()

        if self.health.consecutive_decide_failures >= 3:
            self.health.status = "degraded"
            self.health.last_error = "repeated decide failures"

        if self.health.consecutive_persist_failures >= 3:
            self.health.status = "degraded"
            self.health.last_error = "repeated persistence failures"

    async def on_shutdown(self) -> None:
        self.logger.info("SecurityMetaAgent %s shutting down.", self.agent_id)

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _persist_heartbeat_if_possible(self, heartbeat: Mapping[str, Any]) -> None:
        if not hasattr(self.memory, "upsert_heartbeat"):
            return

        try:
            metrics = heartbeat.get("metrics") if isinstance(heartbeat.get("metrics"), Mapping) else {}
            self.memory.upsert_heartbeat(
                node_id=str(heartbeat.get("node_id") or heartbeat.get("agent_id") or ""),
                source_gid=str(heartbeat.get("gid") or ""),
                blocked_ips=self._safe_int(metrics.get("blocked_ips", 0)),
                status=str(heartbeat.get("status") or "unknown"),
                provenance=heartbeat.get("provenance") if isinstance(heartbeat.get("provenance"), dict) else {},
            )
        except Exception as exc:
            self.logger.debug("Heartbeat persistence skipped: %s", exc)

    def _persist_incident_if_possible(self, event: Mapping[str, Any]) -> None:
        if not hasattr(self.memory, "record_incident"):
            return

        try:
            payload = event.get("payload") if isinstance(event.get("payload"), Mapping) else {}
            self.memory.record_incident(
                event_gid=str(event.get("gid") or new_gid("sec_inc")),
                source_gid=str(event.get("source_agent") or event.get("source_node") or self.agent_id),
                parent_gid=str(event.get("parent_gid") or "") or None,
                incident_type=str(event.get("event_type") or event.get("type") or "unknown"),
                severity=self._safe_float(event.get("severity", 0.0)),
                details=dict(payload),
                provenance=event.get("provenance") if isinstance(event.get("provenance"), dict) else {},
            )
        except Exception as exc:
            self.logger.debug("Incident persistence skipped: %s", exc)

    def _persist_command_if_possible(self, command: Mapping[str, Any], decision: Any) -> None:
        if not hasattr(self.memory, "record_command"):
            return

        try:
            self.memory.record_command(
                event_gid=str(command.get("gid") or new_gid("sec_cmd")),
                parent_gid=str(command.get("parent_gid") or "") or None,
                command_type=str(command.get("type") or "swarm_command"),
                target_node_id=str(command.get("target_node") or "") or None,
                action=command_action(command),
                expires_at=int(self._safe_float(command.get("expires_at"), 0.0)),
                provenance=command.get("provenance") if isinstance(command.get("provenance"), dict) else {},
            )
        except Exception as exc:
            self.logger.warning("Command persistence skipped: %s", exc)

    # ------------------------------------------------------------------
    # Snapshot helpers
    # ------------------------------------------------------------------

    def summarize_snapshot(self, snapshot: Any) -> Mapping[str, Any]:
        if isinstance(snapshot, SecurityMetaSnapshot):
            return {
                "type": "security_meta_snapshot",
                "heartbeats": len(snapshot.heartbeats),
                "events": len(snapshot.events),
                "commands": len(snapshot.commands),
                "node_count": snapshot.node_count,
                "stale_nodes": snapshot.stale_nodes,
                "blocked_ips": snapshot.blocked_ips,
                "active_blocks": snapshot.active_blocks,
                "critical_events": snapshot.critical_events,
                "vulnerability_alerts": snapshot.vulnerability_alerts,
                "integrity_alerts": snapshot.integrity_alerts,
                "open_port_alerts": snapshot.open_port_alerts,
                "latest_event_ts": snapshot.latest_event_ts,
            }

        return super().summarize_snapshot(snapshot)

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_call_int(func: Any, default: int = 0) -> int:
        try:
            return int(func())
        except Exception:
            return default


async def main() -> None:
    agent = SecurityMetaAgent()
    await agent.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("SecurityMetaAgent stopped by user.")
    except SystemExit as exc:
        logger.info("SecurityMetaAgent stopped gracefully: %s", exc)
    except Exception as exc:
        logger.critical("SecurityMetaAgent encountered an unexpected error: %s", exc, exc_info=True)