"""Dry-run replay executor for simulation replay scenarios."""

from __future__ import annotations

import time
from typing import Any, Iterable, Mapping


def find_replay_scenario(records: Iterable[Any], scenario_id: str) -> dict[str, Any] | None:
    """Find a simulation replay scenario by id."""
    target_id = str(scenario_id or "").strip()
    if not target_id:
        return None

    for item in records or []:
        if not isinstance(item, Mapping):
            continue
        if item.get("type") != "simulation_replay_scenario":
            continue
        if str(item.get("scenario_id") or "").strip() == target_id:
            return dict(item)

    return None


def execute_replay_dry_run(
    *,
    scenario: Mapping[str, Any],
    directive: Mapping[str, Any],
    source: str = "simulation",
) -> dict[str, Any]:
    """Execute a replay scenario in dry-run mode.

    This is intentionally non-invasive: it validates scenario shape and returns
    a deterministic execution receipt. It does not mutate trading state or call
    external systems.
    """
    if not isinstance(scenario, Mapping):
        raise TypeError("scenario must be a mapping")

    if scenario.get("type") != "simulation_replay_scenario":
        raise ValueError("scenario must have type='simulation_replay_scenario'")

    scenario_id = str(scenario.get("scenario_id") or "").strip()
    if not scenario_id:
        raise ValueError("scenario_id is required")

    payload = directive.get("payload") if isinstance(directive.get("payload"), Mapping) else {}
    if bool(payload.get("dry_run", True)) is not True:
        raise ValueError("dry_run replay execution requires dry_run=True")

    expected_status = str(scenario.get("expected_result_status") or "applied")
    action = str(scenario.get("action") or "unknown")

    return {
        "type": "simulation_replay_execution",
        "execution_id": f"exec-{scenario_id}",
        "scenario_id": scenario_id,
        "directive_id": directive.get("directive_id"),
        "source": str(source or "simulation"),
        "status": "completed",
        "dry_run": True,
        "action": action,
        "expected_result_status": expected_status,
        "checks": [
            {
                "name": "scenario_found",
                "status": "passed",
                "value": True,
            },
            {
                "name": "dry_run_required",
                "status": "passed",
                "value": True,
            },
            {
                "name": "expected_result_status_present",
                "status": "passed" if bool(expected_status) else "failed",
                "value": expected_status,
            },
        ],
        "created_at": time.time(),
    }


def execute_replay_dry_run_from_records(
    *,
    records: Iterable[Any],
    directive: Mapping[str, Any],
    source: str = "simulation",
) -> dict[str, Any]:
    """Find and dry-run execute a replay scenario referenced by directive."""
    payload = directive.get("payload") if isinstance(directive.get("payload"), Mapping) else {}
    scenario_id = str(payload.get("scenario_id") or "").strip()

    scenario = find_replay_scenario(records, scenario_id)
    if scenario is None:
        raise ValueError(f"simulation replay scenario not found: {scenario_id}")

    return execute_replay_dry_run(
        scenario=scenario,
        directive=directive,
        source=source,
    )


__all__ = [
    "execute_replay_dry_run",
    "execute_replay_dry_run_from_records",
    "find_replay_scenario",
]