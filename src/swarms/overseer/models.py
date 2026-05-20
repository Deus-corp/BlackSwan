"""Data models for overseer coordination."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class SwarmSnapshot:
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
    stale_trade_nodes: List[str]
    stale_security_nodes: List[str]
    stale_explorer_nodes: List[str]


@dataclass(frozen=True)
class OverseerDecision:
    reduce_risk: bool = False
    increase_exploration: bool = False
    unblock_ips: bool = False
    spawn_nodes: bool = False
    continue_explorer: bool = True
    reason: str = ""
    source: str = "merged"
    confidence: float = 0.0