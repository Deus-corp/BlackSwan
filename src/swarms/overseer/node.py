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
    GlobalDecision,
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
            os.environ.get(
                "OVERSEER_COORDINATION_INTERVAL_SECONDS",
                DEFAULT_COORDINATION_INTERVAL_SECONDS,
            )
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

        self._last_snapshot: Optional[SwarmSnapshot] = None
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

    async def collect_all_swarms(self) -> SwarmSnapshot:
        """Collect normalized ecosystem state using overseer_core collector."""
        snapshot = self.collector.collect()
        self._last_snapshot = snapshot

        self.logger.info(
            "Overseer snapshot: trade_nodes=%d security_nodes=%d explorer_nodes=%d "
            "trade_capital=%.2f trade_fitness=%.4f blocked_ips=%d findings=%d vulnerabilities=%d",
            snapshot.trade_nodes,
            snapshot.security_nodes,
            snapshot.explorer_nodes,
            snapshot.trade_capital,
            snapshot.trade_fitness,
            snapshot.blocked_ips,
            snapshot.recent_findings,
            snapshot.recent_vulnerability_alerts,
        )

        return snapshot

    async def global_decide(self, ecosystem_snapshot: Any) -> OverseerCycleDecision:
        """Evaluate hard rules, query strategist, and merge final decision."""
        if not isinstance(ecosystem_snapshot, SwarmSnapshot):
            raise TypeError("Overseer expected SwarmSnapshot from collect_all_swarms()")

        snapshot = ecosystem_snapshot

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
                "snapshot": self.summarize_ecosystem_snapshot(snapshot),
            },
            provenance={
                "agent": self.overseer_id,
                "hard_rules": hard_rules.reason,
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

        if not decision.directives_required:
            return []

        started_at = utc_ts()

        await self.executor.apply(
            ecosystem_snapshot,
            final_decision,
            started_at,
        )

        routed = self._directive_summaries(final_decision, ecosystem_snapshot, parent_gid=decision.event_gid)

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
        """Overseer-specific healthcheck."""
        await super().healthcheck()

        if self._last_snapshot is None:
            return

        if self._last_snapshot.trade_nodes == 0 and self._last_snapshot.security_nodes == 0:
            self.health.status = "degraded"
            self.health.last_error = "No trade/security nodes visible"

    async def maintenance(self) -> None:
        """Periodic overseer maintenance hook."""
        return None

    async def on_shutdown(self) -> None:
        """Shutdown hook."""
        self.logger.info("Overseer %s shutting down.", self.overseer_id)

    # ------------------------------------------------------------------
    # Snapshot summary
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

    # ------------------------------------------------------------------
    # Decision helpers
    # ------------------------------------------------------------------

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
    ) -> list[Dict[str, Any]]:
        """Return compact summaries of directives emitted by ActionExecutor.

        The actual commands are emitted by ActionExecutor. These summaries are
        only for canonical global decision event payloads.
        """
        summaries: list[Dict[str, Any]] = []

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

        return summaries

    @staticmethod
    def _decision_severity(decision: OverseerCycleDecision) -> float:
        if decision.action == "MAINTAIN":
            return 0.0

        if "REDUCE_RISK" in decision.action:
            return 0.7

        if "UNBLOCK" in decision.action:
            return 0.5

        if "PAUSE" in decision.action:
            return 0.45

        if "PAUSE_IMPROVER" in decision.action:
            return 0.35

        return 0.3


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