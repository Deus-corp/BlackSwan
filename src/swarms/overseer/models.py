"""Data models for swarm overseer state management and decision coordination."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class SwarmSnapshot:
    """Represents a point-in-time state of the swarm infrastructure."""
    trade_nodes: int
    trade_capital: float
    trade_dq: float
    trade_fitness: float
    security_nodes: int
    blocked_ips: int
    explorer_nodes: int
    recent_findings: int
    recent_vulnerability_alerts: int
    resources: str
    stale_trade_nodes: List[str] = field(default_factory=list)
    stale_security_nodes: List[str] = field(default_factory=list)
    stale_explorer_nodes: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class OverseerDecision:
    """Encapsulates an actionable decision produced by the overseer model."""
    reduce_risk: bool = False
    increase_exploration: bool = False
    unblock_ips: bool = False
    spawn_nodes: bool = False
    continue_explorer: bool = True
    reason: str = ""
    source: str = "merged"
    confidence: float = 0.0