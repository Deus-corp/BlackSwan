#!/usr/bin/env python3
"""Common lifecycle command protocol.

Lifecycle commands are cross-swarm control commands:

- PAUSE
- RESUME
- RESTART_NODE
- RUN_ONCE

This module intentionally contains pure helpers only. Actual runtime effects
are applied by BaseSwarmNode/BaseSwarmMetaAgent/ImproverAgent implementations.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Dict, Optional

from src.swarms.common.protocols.commands import command_action

LIFECYCLE_PAUSE = "PAUSE"
LIFECYCLE_RESUME = "RESUME"
LIFECYCLE_RESTART_NODE = "RESTART_NODE"
LIFECYCLE_RUN_ONCE = "RUN_ONCE"

LIFECYCLE_COMMANDS = frozenset(
    {
        LIFECYCLE_PAUSE,
        LIFECYCLE_RESUME,
        LIFECYCLE_RESTART_NODE,
        LIFECYCLE_RUN_ONCE,
    }
)


def lifecycle_action(command: Mapping[str, Any]) -> str:
    """Return normalized lifecycle action or empty string."""
    action = command_action(command)
    return action if action in LIFECYCLE_COMMANDS else ""


def is_lifecycle_command(command: Mapping[str, Any]) -> bool:
    """Return True if command is a known lifecycle command."""
    return bool(lifecycle_action(command))


def command_payload(command: Mapping[str, Any]) -> Dict[str, Any]:
    """Return payload/data merged view for lifecycle commands.

    Canonical commands use payload.
    Legacy commands often use data.
    Payload wins over data for overlapping keys.
    """
    data = command.get("data") if isinstance(command.get("data"), Mapping) else {}
    payload = command.get("payload") if isinstance(command.get("payload"), Mapping) else {}

    merged: Dict[str, Any] = {}
    merged.update(dict(data))
    merged.update(dict(payload))
    return merged


def lifecycle_target_node(command: Mapping[str, Any]) -> str:
    """Return target node id if present."""
    payload = command_payload(command)

    return str(
        command.get("target_node")
        or command.get("target_node_id")
        or payload.get("node_id")
        or payload.get("target_node")
        or payload.get("target_node_id")
        or ""
    )


def lifecycle_target_swarm(command: Mapping[str, Any]) -> str:
    """Return target swarm if present."""
    payload = command_payload(command)

    return str(
        command.get("target_swarm")
        or payload.get("swarm")
        or payload.get("target_swarm")
        or ""
    )


def lifecycle_target_role(command: Mapping[str, Any]) -> str:
    """Return target role if present."""
    payload = command_payload(command)

    return str(
        command.get("target_role")
        or payload.get("role")
        or payload.get("target_role")
        or ""
    )


def lifecycle_reason(command: Mapping[str, Any]) -> str:
    """Return lifecycle command reason."""
    payload = command_payload(command)
    return str(payload.get("reason") or command.get("reason") or "")


def lifecycle_applies_to(
    command: Mapping[str, Any],
    *,
    node_id: str,
    swarm_type: str,
    role: str,
) -> bool:
    """Return True if lifecycle command targets this runtime."""
    target_swarm = lifecycle_target_swarm(command)
    target_role = lifecycle_target_role(command)
    target_node = lifecycle_target_node(command)

    if target_swarm and target_swarm not in {swarm_type, "*"}:
        return False

    if target_role and target_role not in {role, "*"}:
        return False

    if target_node and target_node not in {node_id, "*"}:
        return False

    return True


def lifecycle_summary(command: Mapping[str, Any]) -> Dict[str, Any]:
    """Return compact lifecycle command summary."""
    return {
        "type": "lifecycle_command_summary",
        "action": lifecycle_action(command),
        "target_swarm": lifecycle_target_swarm(command),
        "target_role": lifecycle_target_role(command),
        "target_node": lifecycle_target_node(command),
        "reason": lifecycle_reason(command),
        "command_gid": str(command.get("gid") or ""),
    }

LIFECYCLE_EVENT_APPLIED = "lifecycle_command_applied"
LIFECYCLE_EVENT_SKIPPED = "command_skipped"

LIFECYCLE_STATUS_APPLIED = "applied"
LIFECYCLE_STATUS_BLOCKED = "blocked"
LIFECYCLE_STATUS_SKIPPED = "skipped"
LIFECYCLE_STATUS_UNSUPPORTED = "unsupported"


def lifecycle_event_payload(
    command: Mapping[str, Any],
    *,
    status: str,
    reason: str = "",
    extra: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build standard lifecycle command event payload."""
    payload: Dict[str, Any] = {
        "action": lifecycle_action(command),
        "status": status,
        "reason": reason or lifecycle_reason(command),
        "command": lifecycle_summary(command),
    }

    if extra:
        payload.update({str(k): v for k, v in extra.items()})

    return payload


def is_lifecycle_event(record: Mapping[str, Any]) -> bool:
    """Return True if record is a lifecycle observability event."""
    return (
        record.get("type") == "swarm_event"
        and record.get("event_type") in {LIFECYCLE_EVENT_APPLIED, LIFECYCLE_EVENT_SKIPPED}
    )


def lifecycle_event_status(record: Mapping[str, Any]) -> str:
    """Return lifecycle event status if present."""
    payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}
    return str(payload.get("status") or "")


def lifecycle_event_action(record: Mapping[str, Any]) -> str:
    """Return lifecycle event action if present."""
    payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}
    return str(payload.get("action") or "")


def lifecycle_event_reason(record: Mapping[str, Any]) -> str:
    """Return lifecycle event reason if present."""
    payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}
    return str(payload.get("reason") or "")