#!/usr/bin/env python3
"""Top-level overseer composition root.

The Overseer is the global orchestrator above all swarm ecosystems.

Runtime lifecycle is provided by:
    src.swarms.common.base.overseer.BaseSwarmOverseer

Specialized overseer logic is delegated to:
    src.swarms.overseer.overseer_core

Cycle:
    collect_all_swarms
        -> global_decide
        -> route_directives
        -> persist_global_decision
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Sequence

from src.core.crdt_adapter import CRDTAdapter
from src.intelligence.llm_client import LLMClient
from src.swarms.common import (
    BaseOverseerConfig,
    BaseSwarmOverseer,
    make_swarm_event,
    utc_ts,
)
from src.swarms.overseer.overseer_core.collector import StateCollector
from src.swarms.overseer.overseer_core.executor import ActionExecutor
from src.swarms.overseer.overseer_core.models import OverseerDecision, SwarmSnapshot
from src.swarms.overseer.overseer_core.policy import PolicyEngine
from src.swarms.overseer.overseer_core.strategist import LLMStrategist
from swarm_config import config

logger = logging.getLogger(__name__)

DEFAULT_COORDINATION_INTERVAL_SECONDS = 150
DEFAULT_OVERSEER_VERSION = "0.2.0"

def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class OverseerCycleDecision:
    """Decision object passed through BaseSwarmOverseer hooks.

    It intentionally exposes the generic fields expected by BaseSwarmOverseer
    while also carrying the domain-specific OverseerDecision.
    """

    action: str
    confidence: float
    rationale: str
    event_gid: str
    parent_gid: Optional[str] = None
    directives_required: bool = False
    directives: Sequence[Mapping[str, Any]] = field(default_factory=list)
    payload: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)

    hard_rules: Optional[OverseerDecision] = None
    final_decision: Optional[OverseerDecision] = None
    llm_suggestions: Dict[str, Any] = field(default_factory=dict)


class OverseerNode(BaseSwarmOverseer):
    """Global orchestrator for BlackSwan swarm ecosystems."""

    def __init__(
        self,
        node_id: Optional[str] = None,
        coordination_interval_seconds: Optional[int] = None,
    ) -> None:
        interval = coordination_interval_seconds or int(
            float(os.environ.get(
                "OVERSEER_COORDINATION_INTERVAL_SECONDS",
                DEFAULT_COORDINATION_INTERVAL_SECONDS,
            ))
        )

        if interval <= 0:
            raise ValueError("coordination_interval_seconds must be positive")

        overseer_id = node_id or f"overseer-{uuid.uuid4().hex[:8]}"

        crdt = CRDTAdapter(
            node_id=overseer_id,
            db_path=config.crdt_db_path,
        )

        super().__init__(
            overseer_config=BaseOverseerConfig(
                overseer_id=overseer_id,
                role="overseer",
                version=DEFAULT_OVERSEER_VERSION,
                coordination_interval_seconds=float(interval),
                heartbeat_interval_seconds=30.0,
                directive_gc_interval_seconds=60.0,
                reconcile_interval_seconds=10.0,
                healthcheck_interval_seconds=15.0,
                maintenance_interval_seconds=60.0,
                crdt_db_path=config.crdt_db_path,
            ),
            crdt=crdt,
            logger_name="OverseerNode",
        )

        self.coordination_interval_seconds = interval

        self.llm = LLMClient(n_ctx=8192)

        self.collector = StateCollector(self.crdt)
        self.policy = PolicyEngine()
        self.strategist = LLMStrategist(self.llm)
        self.executor = ActionExecutor(self.crdt)
        self.enable_topology_restarts = _env_bool(
            "OVERSEER_ENABLE_TOPOLOGY_RESTARTS",
            False,
        )

        self._last_snapshot: Optional[SwarmSnapshot] = None
        self._last_topology_health: Dict[str, Any] = {}
        self._last_hard_rules: Optional[OverseerDecision] = None
        self._last_final_decision: Optional[OverseerDecision] = None
        self._last_llm_suggestions: Dict[str, Any] = {}

        self.logger.info(
            "🧭 Overseer initialized: %s interval=%ss",
            self.overseer_id,
            self.coordination_interval_seconds,
        )

    # ------------------------------------------------------------------
    # BaseSwarmOverseer hooks
    # ------------------------------------------------------------------

    async def on_startup(self) -> None:
        """Initialize overseer runtime."""
        self.logger.info(
            "🧭 Overseer %s startup complete.",
            self.overseer_id,
        )
        self.logger.info(
            "Topology restarts enabled: %s",
            self.enable_topology_restarts,
        )

    async def collect_all_swarms(self) -> SwarmSnapshot:
        """Collect normalized and topology-aware ecosystem state."""
        snapshot = self.collector.collect()
        topology_health = self.collector.collect_topology_health()

        self._last_snapshot = snapshot
        self._last_topology_health = dict(topology_health)

        self.logger.info(
            "Overseer snapshot: trade_nodes=%d security_nodes=%d explorer_nodes=%d improver_nodes=%d "
            "trade_capital=%.2f trade_fitness=%.4f blocked_ips=%d findings=%d vulnerabilities=%d",
            snapshot.trade_nodes,
            snapshot.security_nodes,
            snapshot.explorer_nodes,
            snapshot.improver_nodes,
            snapshot.trade_capital,
            snapshot.trade_fitness,
            snapshot.blocked_ips,
            snapshot.recent_findings,
            snapshot.recent_vulnerability_alerts,
        )

        self.logger.info(
            "Overseer generic swarm counts: %s",
            getattr(snapshot, "swarm_counts", {}),
        )

        self.logger.info(
            "Overseer topology health: %s",
            self.summarize_topology_health(topology_health),
        )

        return snapshot

    async def global_decide(self, ecosystem_snapshot: Any) -> OverseerCycleDecision:
        """Evaluate hard rules, query strategist, and merge final decision."""
        if not isinstance(ecosystem_snapshot, SwarmSnapshot):
            raise TypeError("Overseer expected SwarmSnapshot from collect_all_swarms()")

        snapshot = ecosystem_snapshot
        topology_summary = self.summarize_topology_health(self._last_topology_health)
        topology_rules = self.policy.evaluate_topology_rules(self._last_topology_health)
        observability_config = self.summarize_observability_config(
            self._last_topology_health,
            topology_rules,
        )
        topology_warnings = self.summarize_topology_warnings(topology_rules)
        topology_restart_candidates = self.summarize_topology_restart_candidates(topology_rules)
        topology_command_warnings = self.summarize_topology_command_warnings(topology_rules)
        topology_legacy_command_warnings = self.summarize_topology_legacy_command_warnings(topology_rules)

        hard_rules = self.policy.evaluate_hard_rules(snapshot)
        llm_suggestions = await self.strategist.suggest(snapshot)

        if not isinstance(llm_suggestions, Mapping):
            self.logger.warning(
                "LLMStrategist returned non-mapping suggestions: %r",
                llm_suggestions,
            )
            llm_suggestions = {}

        final_decision = self.policy.merge(hard_rules, llm_suggestions)

        self._last_hard_rules = hard_rules
        self._last_final_decision = final_decision
        self._last_llm_suggestions = dict(llm_suggestions)

        action = self._decision_action(final_decision)
        event_gid = self.new_gid("decision")

        decision = OverseerCycleDecision(
            action=action,
            confidence=float(final_decision.confidence),
            rationale=final_decision.reason,
            event_gid=event_gid,
            parent_gid=None,
            directives_required=self._decision_requires_execution(final_decision, snapshot),
            directives=[],
            payload={
                "source": final_decision.source,
                "reduce_risk": final_decision.reduce_risk,
                "increase_exploration": final_decision.increase_exploration,
                "unblock_ips": final_decision.unblock_ips,
                "spawn_nodes": final_decision.spawn_nodes,
                "continue_explorer": final_decision.continue_explorer,
                "run_improver_once": getattr(final_decision, "run_improver_once", False),
                "pause_improver": getattr(final_decision, "pause_improver", False),
                "snapshot": self.summarize_ecosystem_snapshot(snapshot),
                "topology": topology_summary,
                "topology_rules": topology_rules,
                "topology_warnings": topology_warnings,
                "topology_restart_candidates": topology_restart_candidates,
                "topology_command_warnings": topology_command_warnings,
                "topology_legacy_command_warnings": topology_legacy_command_warnings,
                "command_event_thresholds": topology_rules.get("command_event_thresholds", {}),
                "observability_config": observability_config,
            },
            provenance={
                "agent": self.overseer_id,
                "hard_rules": hard_rules.reason,
                "topology_rules": topology_rules,
                "topology_warnings": topology_warnings,
                "topology_restart_candidates": topology_restart_candidates,
                "topology_command_warnings": topology_command_warnings,
                "llm_suggestions": dict(llm_suggestions),
            },
            hard_rules=hard_rules,
            final_decision=final_decision,
            llm_suggestions=dict(llm_suggestions),
        )

        self.logger.info(
            "Overseer decision: action=%s confidence=%.2f source=%s reason=%s",
            decision.action,
            decision.confidence,
            final_decision.source,
            final_decision.reason,
        )

        return decision

    async def route_directives(
        self,
        decision: Any,
        ecosystem_snapshot: Any,
    ) -> Sequence[Mapping[str, Any]]:
        """Route global directives through overseer_core ActionExecutor.

        ActionExecutor already emits legacy-compatible commands into CRDT.
        This method returns a compact list of routed directive summaries for
        canonical global decision persistence.
        """
        if not isinstance(ecosystem_snapshot, SwarmSnapshot):
            raise TypeError("Overseer expected SwarmSnapshot in route_directives()")

        if not isinstance(decision, OverseerCycleDecision):
            return await super().route_directives(decision, ecosystem_snapshot)

        final_decision = decision.final_decision
        if final_decision is None:
            return []

        topology_rules = decision.payload.get("topology_rules", {}) if isinstance(decision.payload, Mapping) else {}
        topology_candidates = decision.payload.get("topology_restart_candidates", [])
        if not isinstance(topology_candidates, list):
            topology_candidates = []

        topology_command_warnings = decision.payload.get("topology_command_warnings", [])
        if not isinstance(topology_command_warnings, list):
            topology_command_warnings = []
        
        topology_legacy_command_warnings = decision.payload.get(
            "topology_legacy_command_warnings",
            [],
        )
        if not isinstance(topology_legacy_command_warnings, list):
            topology_legacy_command_warnings = []

        advisory_summaries = self._directive_summaries(
            final_decision,
            ecosystem_snapshot,
            parent_gid=decision.event_gid,
            advisory_only=True,
            topology_rules=topology_rules,
        )

        if not decision.directives_required:
            return advisory_summaries

        started_at = utc_ts()

        await self.executor.apply(
            ecosystem_snapshot,
            final_decision,
            started_at,
        )

        routed = self._directive_summaries(
            final_decision,
            ecosystem_snapshot,
            parent_gid=decision.event_gid,
            advisory_only=False,
            topology_rules=topology_rules,
        )

        command_friction_directives = self.summarize_command_friction_directives(
            topology_command_warnings,
            parent_gid=decision.event_gid,
        )
        if command_friction_directives:
            routed.extend(command_friction_directives)

        if self.enable_topology_restarts:
            executable_candidates: list[Dict[str, Any]] = []
            for item in topology_candidates:
                if not isinstance(item, Mapping):
                    continue
                executable = dict(item)
                executable["execution_enabled"] = True
                executable["advisory_only"] = False
                executable_candidates.append(executable)

            emitted_topology = await self._emit_topology_restart_candidates(
                candidates=executable_candidates,
                parent_gid=decision.event_gid,
            )

            if emitted_topology:
                routed = [
                    item for item in routed
                    if not (
                        item.get("source") == "topology_rules"
                        and item.get("execution_enabled") is False
                    )
                ]
                routed.extend(emitted_topology)

        legacy_migration_directives = self.summarize_legacy_command_migration_directives(
            topology_legacy_command_warnings,
            parent_gid=decision.event_gid,
        )
        if legacy_migration_directives:
            routed.extend(legacy_migration_directives)

        self.logger.info(
            "Overseer routed %d directive summaries for action=%s",
            len(routed),
            decision.action,
        )

        return routed

    async def persist_global_decision(
        self,
        decision: Any,
        ecosystem_snapshot: Any,
        directives: Sequence[Mapping[str, Any]],
    ) -> None:
        """Persist global overseer decision.

        The base implementation emits a canonical swarm_event into CRDT.
        We add a more specific overseer_cycle event as well for easier querying.
        """
        await super().persist_global_decision(
            decision,
            ecosystem_snapshot,
            directives,
        )

        if not isinstance(decision, OverseerCycleDecision):
            return

        event = make_swarm_event(
            event_type="overseer_cycle_completed",
            source_swarm="overseer",
            source_agent=self.overseer_id,
            source_node=self.overseer_id,
            role=self.role,
            parent_gid=decision.event_gid,
            severity=self._decision_severity(decision),
            payload={
                "action": decision.action,
                "confidence": decision.confidence,
                "rationale": decision.rationale,
                "directives": [dict(item) for item in directives],
                "snapshot": self.summarize_ecosystem_snapshot(ecosystem_snapshot),
                "topology": self.summarize_topology_health(self._last_topology_health),
                "topology_rules": decision.payload.get("topology_rules", {}),
                "topology_warnings": decision.payload.get("topology_warnings", []),
                "topology_restart_candidates": decision.payload.get("topology_restart_candidates", []),
                "topology_command_warnings": decision.payload.get("topology_command_warnings", []),
                "topology_legacy_command_warnings": decision.payload.get("topology_legacy_command_warnings", []),
                "command_event_thresholds": decision.payload.get("command_event_thresholds", {}),
                "observability_config": decision.payload.get("observability_config", {}),
                "decision_payload": dict(decision.payload),
            },
            provenance={
                "agent": self.overseer_id,
                **decision.provenance,
            },
        )

        await self.crdt.add_genome(event)

    async def publish_heartbeat(self) -> None:
        """Publish canonical overseer heartbeat plus legacy compatibility heartbeat."""
        await super().publish_heartbeat()

        legacy = {
            "type": "overseer_heartbeat",
            "gid": self.new_gid("hb_legacy"),
            "node_id": self.overseer_id,
            "agent_id": self.overseer_id,
            "swarm": "overseer",
            "role": "overseer",
            "status": self.health.status,
            "timestamp": utc_ts(),
            "provenance": {
                "agent": self.overseer_id,
                "coordination_interval_seconds": self.coordination_interval_seconds,
            },
        }

        await self.crdt.add_genome(legacy)

    async def healthcheck(self) -> None:
        """Overseer-specific topology-aware healthcheck."""
        await super().healthcheck()

        topology = self._last_topology_health or {}
        swarms = topology.get("swarms") if isinstance(topology, Mapping) else {}

        if not isinstance(swarms, Mapping):
            if self._last_snapshot is None:
                return

            if self._last_snapshot.trade_nodes == 0 and self._last_snapshot.security_nodes == 0:
                self.health.status = "degraded"
                self.health.last_error = "No trade/security nodes visible"

            return

        managed = {
            str(name): data
            for name, data in swarms.items()
            if isinstance(data, Mapping)
            and data.get("managed_by_overseer") is True
            and data.get("advisory_only") is not True
        }

        active_managed = {
            name: data
            for name, data in managed.items()
            if int(data.get("node_count") or 0) > 0
        }

        degraded = {
            name: data.get("status")
            for name, data in managed.items()
            if data.get("status") in {"stale", "degraded"}
        }

        if not active_managed:
            self.health.status = "degraded"
            self.health.last_error = "No active managed swarms visible"
            return

        if degraded:
            self.health.status = "degraded"
            self.health.last_error = f"Managed swarm health degraded: {degraded}"
            return

        self.health.status = "ok"
        self.health.last_error = ""

    async def maintenance(self) -> None:
        """Periodic overseer maintenance hook."""
        return None

    async def on_shutdown(self) -> None:
        """Shutdown hook."""
        self.logger.info("Overseer %s shutting down.", self.overseer_id)

    # ------------------------------------------------------------------
    # Snapshot / topology summary
    # ------------------------------------------------------------------

    def summarize_ecosystem_snapshot(self, snapshot: Any) -> Mapping[str, Any]:
        """Return compact summary for SwarmSnapshot or generic ecosystem snapshot."""
        if isinstance(snapshot, SwarmSnapshot):
            return {
                "type": "overseer_swarm_snapshot",
                "trade": {
                    "nodes": snapshot.trade_nodes,
                    "capital": snapshot.trade_capital,
                    "dq": snapshot.trade_dq,
                    "fitness": snapshot.trade_fitness,
                    "stale_nodes": snapshot.stale_trade_nodes,
                },
                "security": {
                    "nodes": snapshot.security_nodes,
                    "blocked_ips": snapshot.blocked_ips,
                    "stale_nodes": snapshot.stale_security_nodes,
                },
                "explorer": {
                    "nodes": snapshot.explorer_nodes,
                    "recent_findings": snapshot.recent_findings,
                    "recent_vulnerability_alerts": snapshot.recent_vulnerability_alerts,
                    "stale_nodes": snapshot.stale_explorer_nodes,
                },
                "improver": {
                    "nodes": snapshot.improver_nodes,
                    "files_processed": snapshot.improver_files_processed,
                    "files_improved": snapshot.improver_files_improved,
                    "files_quarantined": snapshot.improver_files_quarantined,
                    "files_failed": snapshot.improver_files_failed,
                    "last_cycle_duration_seconds": snapshot.improver_last_cycle_duration_seconds,
                    "last_error_count": snapshot.improver_last_error_count,
                    "stale_nodes": snapshot.stale_improver_nodes,
                },
                "resources": snapshot.resources,
            }

        return super().summarize_ecosystem_snapshot(snapshot)

    @staticmethod
    def summarize_topology_health(topology_health: Mapping[str, Any] | None) -> Dict[str, Any]:
        """Return compact topology health summary for events/logs."""
        if not isinstance(topology_health, Mapping):
            return {
                "type": "topology_health",
                "topology_version": "unknown",
                "swarm_count": 0,
                "total_nodes": 0,
                "total_stale_nodes": 0,
                "command_events": {},
                "swarms": {},
            }

        raw_swarms = topology_health.get("swarms")
        swarms: Dict[str, Any] = {}

        if isinstance(raw_swarms, Mapping):
            for swarm_name, raw_data in raw_swarms.items():
                if not isinstance(raw_data, Mapping):
                    continue

                swarms[str(swarm_name)] = {
                    "status": raw_data.get("status"),
                    "node_count": raw_data.get("node_count", 0),
                    "role_counts": raw_data.get("role_counts", {}),
                    "advisory_only": raw_data.get("advisory_only", False),
                    "managed_by_overseer": raw_data.get("managed_by_overseer", False),
                    "stale_nodes": raw_data.get("stale_nodes", []),
                    "commands": raw_data.get("commands", 0),
                    "events": raw_data.get("events", 0),
                    "command_events": raw_data.get("command_events", {}),
                    "command_event_window_seconds": raw_data.get("command_event_window_seconds", 0),
                    "legacy_commands": raw_data.get("legacy_commands", {}),
                    "legacy_command_window_seconds": raw_data.get("legacy_command_window_seconds", 0),
                    "latest_ts": raw_data.get("latest_ts", 0.0),
                }

        return {
            "type": "topology_health",
            "topology_version": topology_health.get("topology_version", "unknown"),
            "swarm_count": topology_health.get("swarm_count", len(swarms)),
            "total_nodes": topology_health.get("total_nodes", 0),
            "total_stale_nodes": topology_health.get("total_stale_nodes", 0),
            "command_events": topology_health.get("command_events", {}),
            "command_event_window_seconds": topology_health.get("command_event_window_seconds", 0),
            "legacy_commands": topology_health.get("legacy_commands", {}),
            "legacy_command_window_seconds": topology_health.get("legacy_command_window_seconds", 0),
            "observability_config": OverseerNode.summarize_observability_config(topology_health),
            "swarms": swarms,
        }

    @staticmethod
    def summarize_topology_warnings(topology_rules: Mapping[str, Any] | None) -> list[Dict[str, Any]]:
        """Convert topology rules into compact warning records for events/UI."""
        if not isinstance(topology_rules, Mapping):
            return []

        warnings: list[Dict[str, Any]] = []

        degraded = topology_rules.get("degraded_managed_swarms")
        if isinstance(degraded, Mapping):
            for swarm, status in degraded.items():
                warnings.append(
                    {
                        "type": "topology_warning",
                        "severity": "medium" if status == "degraded" else "high",
                        "swarm": str(swarm),
                        "status": str(status),
                        "reason": "managed_swarm_degraded",
                    }
                )

        absent = topology_rules.get("absent_managed_swarms")
        if isinstance(absent, list):
            for swarm in absent:
                warnings.append(
                    {
                        "type": "topology_warning",
                        "severity": "medium",
                        "swarm": str(swarm),
                        "status": "absent",
                        "reason": "managed_swarm_absent",
                    }
                )

        active = topology_rules.get("active_managed_swarms")
        if isinstance(active, list) and not active:
            warnings.append(
                {
                    "type": "topology_warning",
                    "severity": "high",
                    "swarm": "*",
                    "status": "no_active_managed_swarms",
                    "reason": "no_active_managed_swarms",
                }
            )

        return warnings

    async def _emit_topology_restart_candidates(
        self,
        *,
        candidates: Sequence[Mapping[str, Any]],
        parent_gid: str,
    ) -> list[Dict[str, Any]]:
        """Emit canonical RESTART_NODE commands for topology restart candidates.

        Disabled unless OVERSEER_ENABLE_TOPOLOGY_RESTARTS=true.
        Legacy compatibility commands are intentionally not emitted here.
        """
        if not self.enable_topology_restarts:
            return []

        emitted: list[Dict[str, Any]] = []

        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                continue

            if candidate.get("execution_enabled") is not True:
                continue

            target_swarm = str(candidate.get("target_swarm") or "")
            target_node = candidate.get("target_node")
            if not target_swarm or not target_node:
                continue

            command = {
                "type": "swarm_command",
                "command_type": "RESTART_NODE",
                "gid": self.new_gid("topology_cmd"),
                "source_swarm": "overseer",
                "source_agent": self.overseer_id,
                "source_node": self.overseer_id,
                "target_swarm": target_swarm,
                "target_role": "node",
                "target_node": str(target_node),
                "timestamp": utc_ts(),
                "expires_at": utc_ts() + 300,
                "parent_gid": parent_gid,
                "payload": {
                    "action": "RESTART_NODE",
                    "node_id": str(target_node),
                    "reason": candidate.get("reason") or "topology_restart_candidate",
                    "topology_status": candidate.get("topology_status"),
                },
                "provenance": {
                    "agent": self.overseer_id,
                    "source": "topology_rules",
                    "legacy_emitted": False,
                },
            }

            await self.crdt.add_genome(command)

            emitted.append(
                {
                    "type": "directive_summary",
                    "action": "RESTART_NODE",
                    "target_swarm": target_swarm,
                    "target_node": str(target_node),
                    "parent_gid": parent_gid,
                    "source": "topology_rules",
                    "topology_status": candidate.get("topology_status"),
                    "reason": candidate.get("reason"),
                    "advisory_only": False,
                    "execution_enabled": True,
                    "legacy_emitted": False,
                }
            )

        return emitted

    # ------------------------------------------------------------------
    # Decision helpers
    # ------------------------------------------------------------------

    @staticmethod
    def summarize_topology_restart_candidates(
        topology_rules: Mapping[str, Any] | None,
    ) -> list[Dict[str, Any]]:
        """Extract advisory topology restart candidates for events/UI."""
        if not isinstance(topology_rules, Mapping):
            return []

        raw_candidates = topology_rules.get("restart_candidates")
        if not isinstance(raw_candidates, list):
            return []

        candidates: list[Dict[str, Any]] = []

        for item in raw_candidates:
            if not isinstance(item, Mapping):
                continue

            candidates.append(
                {
                    "type": "topology_restart_candidate",
                    "action": str(item.get("action") or "RESTART_NODE"),
                    "target_swarm": item.get("target_swarm"),
                    "target_node": item.get("target_node"),
                    "topology_status": item.get("topology_status"),
                    "reason": item.get("reason"),
                    "advisory_only": True,
                    "execution_enabled": False,
                }
            )

        return candidates
    
    @staticmethod
    def summarize_topology_command_warnings(
        topology_rules: Mapping[str, Any] | None,
    ) -> list[Dict[str, Any]]:
        """Extract command-event friction warnings from topology rules."""
        if not isinstance(topology_rules, Mapping):
            return []

        raw_warnings = topology_rules.get("command_event_warnings")
        if not isinstance(raw_warnings, list):
            return []

        warnings: list[Dict[str, Any]] = []

        for item in raw_warnings:
            if not isinstance(item, Mapping):
                continue

            warnings.append(
                {
                    "type": "command_event_warning",
                    "swarm": str(item.get("swarm") or ""),
                    "blocked": int(item.get("blocked", 0) or 0),
                    "skipped": int(item.get("skipped", 0) or 0),
                    "unsupported": int(item.get("unsupported", 0) or 0),
                    "window_seconds": int(item.get("window_seconds", 0) or 0),
                    "reason": str(item.get("reason") or "command_events_indicate_friction"),
                    "advisory_only": True,
                    "execution_enabled": False,
                }
            )

        return warnings
    
    @staticmethod
    def summarize_topology_legacy_command_warnings(
        topology_rules: Mapping[str, Any] | None,
    ) -> list[Dict[str, Any]]:
        """Extract legacy-command usage warnings from topology rules."""
        if not isinstance(topology_rules, Mapping):
            return []

        raw_warnings = topology_rules.get("legacy_command_warnings")
        if not isinstance(raw_warnings, list):
            return []

        warnings: list[Dict[str, Any]] = []

        for item in raw_warnings:
            if not isinstance(item, Mapping):
                continue

            raw_legacy = item.get("legacy_commands")
            legacy_commands = (
                {str(k): int(v or 0) for k, v in raw_legacy.items()}
                if isinstance(raw_legacy, Mapping)
                else {}
            )

            total = int(item.get("total", 0) or sum(legacy_commands.values()))

            if total <= 0:
                continue

            warnings.append(
                {
                    "type": "legacy_command_warning",
                    "swarm": str(item.get("swarm") or ""),
                    "legacy_commands": legacy_commands,
                    "total": total,
                    "reason": str(item.get("reason") or "legacy_command_usage_detected"),
                    "advisory_only": True,
                    "execution_enabled": False,
                }
            )

        return warnings

    @staticmethod
    def _decision_action(decision: OverseerDecision) -> str:
        actions: list[str] = []

        if decision.reduce_risk:
            actions.append("REDUCE_RISK")

        if decision.increase_exploration:
            actions.append("INCREASE_EXPLORATION")

        if decision.unblock_ips:
            actions.append("UNBLOCK_IPS")

        if decision.spawn_nodes:
            actions.append("SPAWN_NODES")

        if not decision.continue_explorer:
            actions.append("PAUSE_EXPLORER")

        if getattr(decision, "run_improver_once", False):
            actions.append("RUN_IMPROVER_ONCE_ADVISORY")

        if getattr(decision, "pause_improver", False):
            actions.append("PAUSE_IMPROVER_ADVISORY")

        if not actions:
            return "MAINTAIN"

        return "+".join(actions)

    @staticmethod
    def _decision_requires_execution(
        decision: OverseerDecision,
        snapshot: SwarmSnapshot,
    ) -> bool:
        return any(
            [
                decision.reduce_risk,
                decision.increase_exploration,
                decision.unblock_ips,
                not decision.continue_explorer,
                bool(snapshot.stale_trade_nodes),
                bool(snapshot.stale_security_nodes),
                bool(snapshot.stale_explorer_nodes),
            ]
        )

    def _directive_summaries(
        self,
        decision: OverseerDecision,
        snapshot: SwarmSnapshot,
        *,
        parent_gid: str,
        advisory_only: bool = False,
        topology_rules: Mapping[str, Any] | None = None,
    ) -> list[Dict[str, Any]]:
        """Return compact summaries of directives emitted or advised by ActionExecutor.

        The actual commands are emitted by ActionExecutor. These summaries are
        only for canonical global decision event payloads.

        advisory_only=True keeps only advisory directives that are intentionally
        not executed yet, such as improver RUN_ONCE/PAUSE.
        """
        summaries: list[Dict[str, Any]] = []

        if not advisory_only:
            for node_id in snapshot.stale_trade_nodes:
                summaries.append(
                    {
                        "type": "directive_summary",
                        "action": "RESTART_NODE",
                        "target_swarm": "trade",
                        "target_node": node_id,
                        "parent_gid": parent_gid,
                    }
                )

            for node_id in snapshot.stale_security_nodes:
                summaries.append(
                    {
                        "type": "directive_summary",
                        "action": "RESTART_NODE",
                        "target_swarm": "security",
                        "target_node": node_id,
                        "parent_gid": parent_gid,
                    }
                )

            for node_id in snapshot.stale_explorer_nodes:
                summaries.append(
                    {
                        "type": "directive_summary",
                        "action": "RESTART_NODE",
                        "target_swarm": "explorer",
                        "target_node": node_id,
                        "parent_gid": parent_gid,
                    }
                )

            if decision.reduce_risk:
                summaries.append(
                    {
                        "type": "directive_summary",
                        "action": "REDUCE_RISK",
                        "target_swarm": "trade",
                        "parent_gid": parent_gid,
                    }
                )

            if decision.increase_exploration:
                summaries.append(
                    {
                        "type": "directive_summary",
                        "action": "INCREASE_EXPLORATION",
                        "target_swarm": "trade",
                        "parent_gid": parent_gid,
                    }
                )

            if decision.unblock_ips:
                summaries.append(
                    {
                        "type": "directive_summary",
                        "action": "UNBLOCK_ALL",
                        "target_swarm": "security",
                        "parent_gid": parent_gid,
                    }
                )

            if not decision.continue_explorer:
                summaries.append(
                    {
                        "type": "directive_summary",
                        "action": "PAUSE",
                        "target_swarm": "explorer",
                        "parent_gid": parent_gid,
                    }
                )

        if getattr(decision, "run_improver_once", False):
            summaries.append(
                {
                    "type": "directive_summary",
                    "action": "RUN_ONCE",
                    "target_swarm": "improver",
                    "target_role": "maintenance_agent",
                    "parent_gid": parent_gid,
                    "advisory_only": True,
                    "execution_enabled": False,
                }
            )

        if getattr(decision, "pause_improver", False):
            summaries.append(
                {
                    "type": "directive_summary",
                    "action": "PAUSE",
                    "target_swarm": "improver",
                    "target_role": "maintenance_agent",
                    "parent_gid": parent_gid,
                    "advisory_only": True,
                    "execution_enabled": False,
                }
            )

        topology_candidates = []
        if isinstance(topology_rules, Mapping):
            raw_candidates = topology_rules.get("restart_candidates")
            if isinstance(raw_candidates, list):
                topology_candidates = [
                    item for item in raw_candidates if isinstance(item, Mapping)
                ]

        for candidate in topology_candidates:
            summaries.append(
                {
                    "type": "directive_summary",
                    "action": str(candidate.get("action") or "RESTART_NODE"),
                    "target_swarm": candidate.get("target_swarm"),
                    "target_node": candidate.get("target_node"),
                    "parent_gid": parent_gid,
                    "source": "topology_rules",
                    "topology_status": candidate.get("topology_status"),
                    "reason": candidate.get("reason"),
                    "advisory_only": True,
                    "execution_enabled": False,
                }
            )

        return summaries
    
    @staticmethod
    def _decision_severity(decision: Any) -> float:
        """Map overseer decision/action into event severity."""
        action = str(getattr(decision, "action", "") or "").upper()
        payload = getattr(decision, "payload", {})
        confidence = float(getattr(decision, "confidence", 0.0) or 0.0)

        if isinstance(payload, Mapping):
            topology_warnings = payload.get("topology_warnings")
            topology_command_warnings = payload.get("topology_command_warnings")
            topology_restart_candidates = payload.get("topology_restart_candidates")
        else:
            topology_warnings = []
            topology_command_warnings = []
            topology_restart_candidates = []

        if action in {"REDUCE_RISK", "EMERGENCY", "HALT", "STOP"}:
            return 0.9

        if "REDUCE_RISK" in action:
            return 0.8

        if topology_warnings or topology_restart_candidates:
            return 0.6

        if topology_command_warnings:
            return 0.4

        if confidence < 0.5:
            return 0.3

        return 0.1
    
    @staticmethod
    def summarize_command_friction_directives(
        topology_command_warnings: Sequence[Mapping[str, Any]] | None,
        *,
        parent_gid: str,
    ) -> list[Dict[str, Any]]:
        """Convert command-event friction warnings into advisory directive summaries."""
        if not isinstance(topology_command_warnings, Sequence) or isinstance(
            topology_command_warnings,
            (str, bytes, bytearray),
        ):
            return []

        directives: list[Dict[str, Any]] = []

        for item in topology_command_warnings:
            if not isinstance(item, Mapping):
                continue

            swarm = str(item.get("swarm") or "")
            if not swarm:
                continue

            blocked = int(item.get("blocked", 0) or 0)
            skipped = int(item.get("skipped", 0) or 0)
            unsupported = int(item.get("unsupported", 0) or 0)

            if blocked <= 0 and skipped <= 0 and unsupported <= 0:
                continue

            directives.append(
                {
                    "type": "directive_summary",
                    "action": "INVESTIGATE_COMMAND_FRICTION",
                    "target_swarm": swarm,
                    "parent_gid": parent_gid,
                    "source": "topology_command_warnings",
                    "blocked": blocked,
                    "skipped": skipped,
                    "unsupported": unsupported,
                    "window_seconds": int(item.get("window_seconds", 0) or 0),
                    "reason": str(item.get("reason") or "command_events_indicate_friction"),
                    "advisory_only": True,
                    "execution_enabled": False,
                }
            )

        return directives
    
    @staticmethod
    def summarize_legacy_command_migration_directives(
        topology_legacy_command_warnings: Sequence[Mapping[str, Any]] | None,
        *,
        parent_gid: str,
    ) -> list[Dict[str, Any]]:
        """Convert legacy-command usage warnings into advisory migration summaries."""
        if not isinstance(topology_legacy_command_warnings, Sequence) or isinstance(
            topology_legacy_command_warnings,
            (str, bytes, bytearray),
        ):
            return []

        directives: list[Dict[str, Any]] = []

        for item in topology_legacy_command_warnings:
            if not isinstance(item, Mapping):
                continue

            swarm = str(item.get("swarm") or "")
            if not swarm:
                continue

            raw_legacy = item.get("legacy_commands")
            legacy_commands = (
                {str(k): int(v or 0) for k, v in raw_legacy.items()}
                if isinstance(raw_legacy, Mapping)
                else {}
            )

            total = int(item.get("total", 0) or sum(legacy_commands.values()))
            if total <= 0:
                continue

            directives.append(
                {
                    "type": "directive_summary",
                    "action": "MIGRATE_LEGACY_COMMANDS",
                    "target_swarm": swarm,
                    "parent_gid": parent_gid,
                    "source": "legacy_command_warnings",
                    "legacy_commands": legacy_commands,
                    "total": total,
                    "reason": str(item.get("reason") or "legacy_command_usage_detected"),
                    "advisory_only": True,
                    "execution_enabled": False,
                }
            )

        return directives
    
    @staticmethod
    def summarize_observability_config(
        topology_health: Mapping[str, Any] | None,
        topology_rules: Mapping[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Return compact observability config used by topology/policy summaries."""
        topology_health = topology_health if isinstance(topology_health, Mapping) else {}
        topology_rules = topology_rules if isinstance(topology_rules, Mapping) else {}

        return {
            "command_event_window_seconds": int(
                topology_health.get("command_event_window_seconds", 0) or 0
            ),
            "legacy_command_window_seconds": int(
                topology_health.get("legacy_command_window_seconds", 0) or 0
            ),
            "command_event_thresholds": topology_rules.get("command_event_thresholds", {}),
        }

async def main() -> None:
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
    )

    node = OverseerNode()
    await node.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Overseer stopped by user.")
    except SystemExit as exc:
        logger.info("Overseer stopped gracefully: %s", exc)
    except Exception as exc:
        logger.critical("Fatal overseer error: %s", exc, exc_info=True)
       