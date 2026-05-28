"""Data models for swarm overseer state and decision coordination."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True, slots=True)
class SwarmSnapshot:
    """Point-in-time normalized state of the swarm ecosystem.

    Legacy fields are preserved for policy/strategist/executor compatibility.
    Generic fields are added so all current/future swarms can be represented
    equally: trade, security, explorer, improver, overseer, memory, simulation.
    """

    # Trade swarm
    trade_nodes: int
    trade_capital: float
    trade_dq: float
    trade_fitness: float

    # Security swarm
    security_nodes: int
    blocked_ips: int

    # Explorer swarm
    explorer_nodes: int
    recent_findings: int
    recent_vulnerability_alerts: int

    # Improver swarm / maintenance layer
    improver_nodes: int = 0
    improver_files_processed: int = 0
    improver_files_improved: int = 0
    improver_files_quarantined: int = 0
    improver_files_failed: int = 0
    improver_last_cycle_duration_seconds: float = 0.0
    improver_last_error_count: int = 0

    # Generic swarm view
    swarm_counts: Dict[str, int] = field(default_factory=dict)
    swarm_role_counts: Dict[str, Dict[str, int]] = field(default_factory=dict)
    stale_swarm_nodes: Dict[str, List[str]] = field(default_factory=dict)
    latest_swarm_heartbeats: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    recent_heartbeats_by_swarm: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    # Host/resource context
    resources: str = ""

    # Legacy stale nodes by swarm
    stale_trade_nodes: List[str] = field(default_factory=list)
    stale_security_nodes: List[str] = field(default_factory=list)
    stale_explorer_nodes: List[str] = field(default_factory=list)
    stale_improver_nodes: List[str] = field(default_factory=list)

    @property
    def total_nodes(self) -> int:
        """Total visible nodes across swarms."""
        if self.swarm_counts:
            return int(sum(self.swarm_counts.values()))

        return int(
            self.trade_nodes
            + self.security_nodes
            + self.explorer_nodes
            + self.improver_nodes
        )

    @property
    def stale_node_count(self) -> int:
        """Total stale nodes across all known swarms."""
        if self.stale_swarm_nodes:
            return sum(len(nodes) for nodes in self.stale_swarm_nodes.values())

        return (
            len(self.stale_trade_nodes)
            + len(self.stale_security_nodes)
            + len(self.stale_explorer_nodes)
            + len(self.stale_improver_nodes)
        )

    @property
    def memory_nodes(self) -> int:
        """Visible memory swarm nodes."""
        return int(self.swarm_counts.get("memory", 0))

    @property
    def simulation_nodes(self) -> int:
        """Visible simulation swarm nodes."""
        return int(self.swarm_counts.get("simulation", 0))

    @property
    def overseer_nodes(self) -> int:
        """Visible overseer nodes."""
        return int(self.swarm_counts.get("overseer", 0))

    @property
    def has_security_pressure(self) -> bool:
        """Whether security subsystem reports active pressure."""
        return self.blocked_ips > 0 or self.recent_vulnerability_alerts > 0

    @property
    def has_trade_pressure(self) -> bool:
        """Whether trade subsystem reports risk pressure."""
        return self.trade_dq > 0.0 or self.trade_capital <= 0.0

    @property
    def has_explorer_pressure(self) -> bool:
        """Whether explorer subsystem reports high activity/pressure."""
        return self.recent_findings > 0

    @property
    def has_improver_pressure(self) -> bool:
        """Whether improver reports failed/quarantined/error-heavy activity."""
        return (
            self.improver_files_failed > 0
            or self.improver_files_quarantined > 0
            or self.improver_last_error_count > 0
        )

    def stale_nodes_by_swarm(self) -> Dict[str, List[str]]:
        """Return stale node ids grouped by swarm."""
        grouped = {
            "trade": list(self.stale_trade_nodes),
            "security": list(self.stale_security_nodes),
            "explorer": list(self.stale_explorer_nodes),
            "improver": list(self.stale_improver_nodes),
        }

        for swarm, nodes in self.stale_swarm_nodes.items():
            grouped[str(swarm)] = list(nodes)

        return grouped

    def compact_summary(self) -> Dict[str, object]:
        """Return compact serializable summary for logs/events."""
        return {
            "total_nodes": self.total_nodes,
            "trade_nodes": self.trade_nodes,
            "trade_capital": self.trade_capital,
            "trade_dq": self.trade_dq,
            "trade_fitness": self.trade_fitness,
            "security_nodes": self.security_nodes,
            "blocked_ips": self.blocked_ips,
            "explorer_nodes": self.explorer_nodes,
            "recent_findings": self.recent_findings,
            "recent_vulnerability_alerts": self.recent_vulnerability_alerts,
            "improver_nodes": self.improver_nodes,
            "improver_files_processed": self.improver_files_processed,
            "improver_files_improved": self.improver_files_improved,
            "improver_files_quarantined": self.improver_files_quarantined,
            "improver_files_failed": self.improver_files_failed,
            "improver_last_cycle_duration_seconds": self.improver_last_cycle_duration_seconds,
            "improver_last_error_count": self.improver_last_error_count,
            "memory_nodes": self.memory_nodes,
            "simulation_nodes": self.simulation_nodes,
            "overseer_nodes": self.overseer_nodes,
            "swarm_counts": dict(self.swarm_counts),
            "swarm_role_counts": {
                swarm: dict(counts)
                for swarm, counts in self.swarm_role_counts.items()
            },
            "stale_node_count": self.stale_node_count,
            "stale_nodes": self.stale_nodes_by_swarm(),
            "resources": self.resources,
        }


@dataclass(frozen=True, slots=True)
class OverseerDecision:
    """Actionable decision produced by the overseer policy layer."""

    reduce_risk: bool = False
    increase_exploration: bool = False
    unblock_ips: bool = False
    spawn_nodes: bool = False
    continue_explorer: bool = True

    # v1: advisory/read-only maintenance fields.
    # They are intentionally not executed by ActionExecutor yet.
    run_improver_once: bool = False
    pause_improver: bool = False

    reason: str = ""
    source: str = "merged"
    confidence: float = 0.0

    @property
    def has_actionable_directives(self) -> bool:
        """Whether this decision implies at least one currently executable directive."""
        return any(
            [
                self.reduce_risk,
                self.increase_exploration,
                self.unblock_ips,
                not self.continue_explorer,
            ]
        )

    @property
    def advisory_only(self) -> bool:
        """Whether decision contains only advisory/non-executable intent."""
        advisory_flags = any(
            [
                self.spawn_nodes,
                self.run_improver_once,
                self.pause_improver,
            ]
        )
        return advisory_flags and not self.has_actionable_directives

    def action_flags(self) -> Dict[str, bool]:
        """Return decision flags as a serializable dict."""
        return {
            "reduce_risk": self.reduce_risk,
            "increase_exploration": self.increase_exploration,
            "unblock_ips": self.unblock_ips,
            "spawn_nodes": self.spawn_nodes,
            "continue_explorer": self.continue_explorer,
            "run_improver_once": self.run_improver_once,
            "pause_improver": self.pause_improver,
        }

    def action_label(self) -> str:
        """Return compact human-readable action label."""
        actions: list[str] = []

        if self.reduce_risk:
            actions.append("REDUCE_RISK")

        if self.increase_exploration:
            actions.append("INCREASE_EXPLORATION")

        if self.unblock_ips:
            actions.append("UNBLOCK_IPS")

        if self.spawn_nodes:
            actions.append("SPAWN_NODES_ADVISORY")

        if not self.continue_explorer:
            actions.append("PAUSE_EXPLORER")

        if self.run_improver_once:
            actions.append("RUN_IMPROVER_ONCE_ADVISORY")

        if self.pause_improver:
            actions.append("PAUSE_IMPROVER_ADVISORY")

        if not actions:
            return "MAINTAIN"

        return "+".join(actions)

    def compact_summary(self) -> Dict[str, object]:
        """Return compact serializable summary for logs/events."""
        return {
            "action": self.action_label(),
            "flags": self.action_flags(),
            "source": self.source,
            "confidence": self.confidence,
            "reason": self.reason,
            "has_actionable_directives": self.has_actionable_directives,
            "advisory_only": self.advisory_only,
        }