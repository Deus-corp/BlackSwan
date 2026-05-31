"""Replay scenario metrics for the simulation swarm."""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping


def summarize_replay_scenarios(records: Iterable[Any]) -> dict[str, Any]:
    """Summarize simulation replay scenarios from CRDT-visible records."""
    scenarios = [
        item
        for item in records or []
        if isinstance(item, Mapping)
        and item.get("type") == "simulation_replay_scenario"
    ]

    status_counts = Counter(str(item.get("status") or "unknown").strip().lower() for item in scenarios)
    replay_kind_counts = Counter(str(item.get("replay_kind") or "unknown").strip().lower() for item in scenarios)
    action_counts = Counter(str(item.get("action") or "unknown").strip().upper() for item in scenarios)

    executions = [
        item
        for item in records or []
        if isinstance(item, Mapping)
        and item.get("type") == "simulation_replay_execution"
    ]

    execution_status_counts = Counter(
        str(item.get("status") or "unknown").strip().lower()
        for item in executions
    )

    return {
        "simulation_replay_scenarios": len(scenarios),
        "simulation_replay_pending": int(status_counts.get("pending", 0)),
        "simulation_replay_completed": int(status_counts.get("completed", 0)),
        "simulation_replay_failed": int(status_counts.get("failed", 0)),
        "simulation_replay_status_counts": dict(status_counts),
        "simulation_replay_kind_counts": dict(replay_kind_counts),
        "simulation_replay_action_counts": dict(action_counts),
        "simulation_replay_executions": len(executions),
        "simulation_replay_execution_completed": int(execution_status_counts.get("completed", 0)),
        "simulation_replay_execution_failed": int(execution_status_counts.get("failed", 0)),
        "simulation_replay_execution_status_counts": dict(execution_status_counts),
    }


def build_simulation_replay_heartbeat_metrics(records: Iterable[Any]) -> dict[str, Any]:
    """Build heartbeat-ready replay metrics."""
    return summarize_replay_scenarios(records)


__all__ = [
    "build_simulation_replay_heartbeat_metrics",
    "summarize_replay_scenarios",
]