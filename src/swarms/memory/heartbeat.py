from __future__ import annotations

from typing import Any

from src.swarms.common.contracts import SwarmHeartbeat


def build_memory_heartbeat(
    node_id: str,
    *,
    metrics: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
    status: str = "running",
) -> dict[str, Any]:
    """Build canonical heartbeat for memory swarm nodes."""
    return SwarmHeartbeat(
        swarm="memory",
        node_id=node_id,
        role="node",
        status=status,
        capabilities=[
            "episodic_memory",
            "semantic_memory",
            "retrieval",
            "consolidation",
            "gold_sample_export",
        ],
        metrics=metrics or {},
        details=details or {},
    ).to_dict()