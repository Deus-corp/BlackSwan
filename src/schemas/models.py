"""Shared schema models for BlackSwan runtime telemetry and API payloads."""

from __future__ import annotations

from typing import Literal, TypedDict


ContainerStatus = Literal["starting", "running", "healthy", "degraded", "stopped", "failed", "unknown"]


class ContainerMetrics(TypedDict):
    """Container resource consumption and status snapshot."""

    cpu_usage: float
    memory_usage: float
    status: str


class RuntimeServiceMetrics(TypedDict, total=False):
    """Metrics for a local cluster service/process."""

    service: str
    node_id: str
    pid: int
    returncode: int | None
    uptime_seconds: float
    restart_count: int
    status: ContainerStatus
    log_path: str


class SwarmNodeMetrics(TypedDict, total=False):
    """Generic swarm node metrics."""

    node_id: str
    swarm: str
    role: str
    status: str
    timestamp: float
    step: int
    capital: float
    fitness: float
    diversity: float
    crdt_size: int


class TradeNodeMetrics(SwarmNodeMetrics, total=False):
    """Trade-specific node metrics."""

    dry_run: bool
    execution_enabled: bool
    market_mode: str
    best_symbol: str
    best_price: float
    dq: float
    llm_mutations: int