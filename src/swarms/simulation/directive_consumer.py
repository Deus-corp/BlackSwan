"""Simulation swarm directive consumer.

The simulation swarm currently treats replay execution as gated. RUN_REPLAY is
recognized but rejected until a safe dry-run executor is implemented.
"""

from __future__ import annotations

import time
from typing import Any, Mapping

from src.swarms.common.protocols.directives import build_directive_result
from src.swarms.simulation.replay_executor import execute_replay_dry_run_from_records


def directive_applies_to_simulation(directive: Mapping[str, Any]) -> bool:
    """Return whether a directive targets the simulation swarm."""
    target = str(directive.get("target") or directive.get("target_swarm") or "").strip()
    target_type = str(directive.get("target_type") or "").strip().lower()

    if target in {"", "*", "simulation"}:
        return target_type in {"", "swarm", "global"}

    return False


async def apply_simulation_directive(node: Any, directive: Mapping[str, Any]) -> dict[str, Any]:
    """Apply or reject a simulation directive safely."""
    if not directive_applies_to_simulation(directive):
        return _result(
            node=node,
            directive=directive,
            status="ignored",
            reason="directive_not_targeted_to_simulation",
        )

    action = str(directive.get("action") or "").strip().upper()
    payload = directive.get("payload") if isinstance(directive.get("payload"), Mapping) else {}

    if action == "OBSERVE":
        return _result(
            node=node,
            directive=directive,
            status="applied",
            reason="observe_acknowledged",
        )

    if action == "RUN_REPLAY":
        scenario_id = str(payload.get("scenario_id") or "").strip()
        dry_run = bool(payload.get("dry_run", True))

        if not scenario_id:
            return _result(
                node=node,
                directive=directive,
                status="rejected",
                reason="run_replay_missing_scenario_id",
            )

        if dry_run is not True:
            return _result(
                node=node,
                directive=directive,
                status="rejected",
                reason="run_replay_requires_dry_run",
            )

        try:
            state = getattr(getattr(node, "crdt", None), "state", {}) or {}
            records = list(state.values()) if isinstance(state, dict) else []
            execution = execute_replay_dry_run_from_records(
                records=records,
                directive=directive,
                source=str(getattr(node, "node_id", "simulation")),
            )
        except Exception as exc:
            return _result(
                node=node,
                directive=directive,
                status="rejected",
                reason="run_replay_dry_run_failed",
                extra={
                    "scenario_id": scenario_id,
                    "dry_run": True,
                    "error": str(exc),
                },
            )

        return _result(
            node=node,
            directive=directive,
            status="applied",
            reason="run_replay_dry_run_completed",
            extra={
                "scenario_id": scenario_id,
                "dry_run": True,
                "execution": execution,
            },
        )

    return _result(
        node=node,
        directive=directive,
        status="ignored",
        reason="unsupported_simulation_directive",
    )


def _result(
    *,
    node: Any,
    directive: Mapping[str, Any],
    status: str,
    reason: str,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "reason": reason,
        "handled_at": time.time(),
    }
    if extra:
        payload.update(dict(extra))

    result = build_directive_result(
        directive_id=str(directive.get("directive_id") or ""),
        status=status,
        source=str(getattr(node, "node_id", "simulation")),
        swarm="simulation",
        payload=payload,
    ).to_dict()

    result["status"] = status
    result["payload"] = payload
    return result


__all__ = [
    "apply_simulation_directive",
    "directive_applies_to_simulation",
]