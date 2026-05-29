"""Trade node command helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Dict


def command_value(normalized: Mapping[str, Any], key: str, default: Any = None) -> Any:
    """Read a command value from payload first, then from top-level fields."""
    payload = normalized.get("payload")
    if isinstance(payload, Mapping) and key in payload:
        return payload.get(key)
    return normalized.get(key, default)


def command_action(normalized: Mapping[str, Any]) -> str:
    """Return normalized command action name."""
    action = (
        normalized.get("action")
        or normalized.get("command")
        or normalized.get("command_type")
        or command_value(normalized, "action")
        or command_value(normalized, "command")
        or command_value(normalized, "command_type")
        or ""
    )
    return str(action).strip().upper()


def command_has_explicit_approval(normalized: Mapping[str, Any]) -> bool:
    """Return True if a command explicitly carries approval."""
    for key in (
        "explicit_approval",
        "approved",
        "approval",
        "authorized",
        "safety_gate",
    ):
        explicit = command_value(normalized, key, None)
        if explicit is None:
            continue

        if isinstance(explicit, bool):
            return explicit

        normalized_value = str(explicit).strip().lower()
        if normalized_value in {"1", "true", "yes", "y", "approved", "authorized"}:
            return True

    return False


def command_applies_to_node(normalized: Mapping[str, Any], *, node_id: str, target_swarm: str = "trade") -> bool:
    """Return True if the normalized command targets this node or swarm."""
    targets = normalized.get("targets")
    target = normalized.get("target")
    command_target_swarm = normalized.get("target_swarm") or normalized.get("swarm")

    payload = normalized.get("payload")
    if isinstance(payload, Mapping):
        if targets is None:
            targets = payload.get("targets")
        if target is None:
            target = payload.get("target")
        if command_target_swarm is None:
            command_target_swarm = payload.get("target_swarm") or payload.get("swarm")

    accepted_node_targets = {
        str(node_id),
        "all",
        "*",
    }

    accepted_swarm_targets = {
        str(target_swarm),
        "all",
        "*",
    }

    if isinstance(targets, (list, tuple, set)):
        target_values = {str(item) for item in targets}
        if target_values & accepted_node_targets:
            return True
        if target_values & accepted_swarm_targets:
            return True

    if target is not None:
        clean_target = str(target)
        if clean_target in accepted_node_targets or clean_target in accepted_swarm_targets:
            return True

    if command_target_swarm is not None:
        if str(command_target_swarm) in accepted_swarm_targets:
            return True

    return False


__all__ = [
    "command_action",
    "command_applies_to_node",
    "command_has_explicit_approval",
    "command_value",
]