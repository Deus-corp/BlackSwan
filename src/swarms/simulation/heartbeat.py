from __future__ import annotations

from typing import Any

from src.swarms.common.contracts import SwarmHeartbeat


def build_simulation_heartbeat(
    node_id: str,
    *,
    metrics: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
    status: str = "running",
) -> dict[str, Any]:
    """Build canonical heartbeat for simulation swarm nodes."""
    return SwarmHeartbeat(
        swarm="simulation",
        node_id=node_id,
        role="node",
        status=status,
        capabilities=[
            "scenario_run",
            "policy_evaluation",
            "stress_test",
            "counterfactual_simulation",
            "offline_mutation_validation",
        ],
        metrics=metrics or {},
        details=details or {},
    ).to_dict()