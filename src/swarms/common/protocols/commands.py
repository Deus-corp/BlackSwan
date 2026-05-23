#!/usr/bin/env python3
"""Command protocol helpers.

This module provides backward-compatible helpers around the canonical
SwarmCommand schema.

It understands both canonical commands:

    {"type": "swarm_command", ...}

and legacy commands currently used by swarms:

    {"type": "sec_command", ...}
    {"type": "meta_command_json", ...}
    {"type": "explorer_command", ...}
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Dict, Iterable, Optional

from src.swarms.common.schemas import SwarmCommand
from src.swarms.common.utils import expires_in, is_expired, new_gid, utc_ts

CANONICAL_COMMAND_TYPE = "swarm_command"

LEGACY_COMMAND_TYPES = {
    "sec_command",
    "meta_command_json",
    "explorer_command",
    "trade_command",
}

KNOWN_COMMAND_TYPES = {
    CANONICAL_COMMAND_TYPE,
    *LEGACY_COMMAND_TYPES,
}


def is_command(value: Any) -> bool:
    """Return True if value looks like a swarm command."""
    return isinstance(value, Mapping) and str(value.get("type", "")) in KNOWN_COMMAND_TYPES


def make_swarm_command(
    *,
    command_type: str,
    source_agent: str,
    source_swarm: str,
    payload: Optional[Dict[str, Any]] = None,
    parent_gid: Optional[str] = None,
    target_swarm: Optional[str] = None,
    target_node: Optional[str] = None,
    target_role: Optional[str] = None,
    ttl_seconds: float = 600.0,
    priority: int = 0,
    trace_id: Optional[str] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build canonical CRDT-compatible swarm command dict."""
    command = SwarmCommand(
        command_type=command_type.upper(),
        source_agent=source_agent,
        source_swarm=source_swarm,
        payload=payload or {},
        parent_gid=parent_gid,
        target_swarm=target_swarm,
        target_node=target_node,
        target_role=target_role,
        expires_at=expires_in(ttl_seconds),
        priority=priority,
        trace_id=trace_id,
        provenance=provenance or {},
    )
    return command.to_dict(include_legacy_data=True)


def normalize_command(record: Mapping[str, Any]) -> Dict[str, Any]:
    """Normalize canonical or legacy command record.

    Returns {} if record is not command-like.
    """
    if not isinstance(record, Mapping):
        return {}

    record_type = str(record.get("type") or "")

    if record_type == "swarm_command":
        command_type = str(record.get("command_type") or record.get("action") or "").upper()
        if not command_type:
            payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}
            command_type = str(payload.get("action") or "").upper()

        if not command_type:
            return {}

        out = dict(record)
        out["command_type"] = command_type
        out["type"] = "swarm_command"
        return out

    if record_type in {"sec_command", "explorer_command", "meta_command_json", "trade_command"}:
        data = record.get("data") if isinstance(record.get("data"), Mapping) else {}
        payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}

        action = str(
            record.get("command_type")
            or record.get("action")
            or data.get("action")
            or payload.get("action")
            or ""
        ).upper()

        if not action:
            return {}

        target_swarm = str(
            record.get("target_swarm")
            or data.get("swarm")
            or payload.get("swarm")
            or _legacy_target_swarm(record_type)
            or ""
        )

        target_role = str(
            record.get("target_role")
            or data.get("role")
            or payload.get("role")
            or "node"
        )

        target_node = str(
            record.get("target_node")
            or record.get("target_node_id")
            or data.get("node_id")
            or payload.get("node_id")
            or ""
        )

        return {
            **dict(record),
            "type": "swarm_command",
            "legacy_type": record_type,
            "command_type": action,
            "target_swarm": target_swarm,
            "target_role": target_role,
            "target_node": target_node,
            "payload": dict(payload),
            "data": dict(data),
        }

    return {}

def _legacy_target_swarm(record_type: str) -> str:
    """Infer target swarm from legacy command type."""
    if record_type == "sec_command":
        return "security"
    if record_type == "explorer_command":
        return "explorer"
    if record_type == "meta_command_json":
        return "trade"
    if record_type == "trade_command":
        return "trade"
    return ""


def normalize_commands(records: Iterable[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    """Normalize command-like records from an iterable.

    Invalid/non-command records are skipped.

    Supports:
    - canonical swarm_command
    - legacy sec_command
    - legacy explorer_command
    - legacy meta_command_json
    - legacy trade_command
    """
    normalized: list[Dict[str, Any]] = []

    for record in records:
        if not isinstance(record, Mapping):
            continue

        item = normalize_command(record)
        if item:
            normalized.append(item)

    return normalized


def command_targets(
    command: Mapping[str, Any],
    *,
    swarm: str,
    node_id: Optional[str] = None,
    role: Optional[str] = None,
) -> bool:
    """Return True if command targets the given swarm/node/role.

    Missing targets mean broadcast/compatible.
    Wildcard "*" is accepted.
    """
    normalized = normalize_command(command) if command.get("type") != CANONICAL_COMMAND_TYPE else dict(command)

    payload = normalized.get("payload") if isinstance(normalized.get("payload"), Mapping) else {}
    data = normalized.get("data") if isinstance(normalized.get("data"), Mapping) else {}

    target_swarm = normalized.get("target_swarm") or payload.get("target_swarm") or data.get("swarm")
    target_node = normalized.get("target_node") or payload.get("target_node") or data.get("node_id")
    target_role = normalized.get("target_role") or payload.get("target_role") or data.get("role")

    if target_swarm and str(target_swarm) not in {swarm, "*"}:
        return False

    if node_id and target_node and str(target_node) not in {node_id, "*"}:
        return False

    if role and target_role and str(target_role) not in {role, "*"}:
        return False

    return True


def command_action(command: Mapping[str, Any]) -> str:
    """Extract normalized command action."""
    payload = command.get("payload") if isinstance(command.get("payload"), Mapping) else {}
    data = command.get("data") if isinstance(command.get("data"), Mapping) else {}

    action = (
        command.get("command_type")
        or command.get("action")
        or payload.get("action")
        or data.get("action")
        or ""
    )
    return str(action).upper()


def command_is_expired(command: Mapping[str, Any]) -> bool:
    """Return True if command has expired."""
    return is_expired(command.get("expires_at"))


def _normalize_legacy_command(value: Mapping[str, Any]) -> Dict[str, Any]:
    record_type = str(value.get("type", ""))
    data = value.get("data") if isinstance(value.get("data"), Mapping) else {}
    provenance = value.get("provenance") if isinstance(value.get("provenance"), Mapping) else {}

    action = (
        value.get("command_type")
        or value.get("action")
        or data.get("action")
        or record_type
    )

    source_swarm = _infer_swarm_from_legacy_command(record_type, value)
    target_swarm = value.get("target_swarm") or data.get("swarm") or _infer_target_swarm(record_type, data)

    command = SwarmCommand(
        gid=str(value.get("gid") or new_gid("cmd", namespace=source_swarm)),
        command_type=str(action).upper(),
        source_agent=str(value.get("source_agent") or value.get("source_gid") or value.get("origin") or source_swarm),
        source_swarm=source_swarm,
        parent_gid=str(value.get("parent_gid") or "") or None,
        target_swarm=str(target_swarm or "") or None,
        target_node=str(value.get("target_node") or value.get("target_node_id") or data.get("node_id") or "") or None,
        target_role=str(value.get("target_role") or data.get("role") or "") or None,
        timestamp=float(value.get("timestamp") or utc_ts()),
        expires_at=float(value.get("expires_at") or expires_in(600)),
        priority=int(value.get("priority") or 0),
        trace_id=str(value.get("trace_id") or "") or None,
        payload={
            "legacy_type": record_type,
            **dict(data),
        },
        provenance=dict(provenance),
    )

    return command.to_dict(include_legacy_data=True)


def _infer_swarm_from_legacy_command(record_type: str, value: Mapping[str, Any]) -> str:
    if value.get("source_swarm"):
        return str(value["source_swarm"])
    if value.get("swarm"):
        return str(value["swarm"])

    if record_type == "sec_command":
        return "security"
    if record_type == "explorer_command":
        return "explorer"
    if record_type == "trade_command":
        return "trade"
    if record_type == "meta_command_json":
        return "overseer"

    return "unknown"


def _infer_target_swarm(record_type: str, data: Mapping[str, Any]) -> Optional[str]:
    if data.get("swarm"):
        return str(data["swarm"])

    if record_type == "sec_command":
        return "security"
    if record_type == "explorer_command":
        return "explorer"
    if record_type == "trade_command":
        return "trade"
    if record_type == "meta_command_json":
        return "trade"

    return None

_VOLATILE_COMMAND_KEYS = {
    "gid",
    "id",
    "timestamp",
    "created_at",
    "expires_at",
    "parent_gid",
    "source_gid",
    "source_agent",
    "source_node",
    "source_swarm",
    "provenance",
}

def _stable_command_value(value: Any) -> Any:
    """Return JSON-stable command value without volatile fields."""
    if isinstance(value, Mapping):
        return {
            str(k): _stable_command_value(v)
            for k, v in sorted(value.items(), key=lambda item: str(item[0]))
            if str(k) not in _VOLATILE_COMMAND_KEYS
        }

    if isinstance(value, (list, tuple)):
        return [_stable_command_value(v) for v in value]

    if isinstance(value, set):
        return sorted(_stable_command_value(v) for v in value)

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    return repr(value)


def command_fingerprint(command: Mapping[str, Any]) -> str:
    """Build stable semantic fingerprint for canonical/legacy commands."""
    action = command_action(command)

    data = command.get("data") if isinstance(command.get("data"), Mapping) else {}
    payload = command.get("payload") if isinstance(command.get("payload"), Mapping) else {}

    target_swarm = str(
        command.get("target_swarm")
        or command.get("swarm")
        or data.get("swarm")
        or payload.get("swarm")
        or ""
    )

    target_role = str(
        command.get("target_role")
        or command.get("role")
        or data.get("role")
        or payload.get("role")
        or ""
    )

    target_node = str(
        command.get("target_node")
        or command.get("target_node_id")
        or data.get("node_id")
        or payload.get("node_id")
        or ""
    )

    normalized = {
        "action": action,
        "target_swarm": target_swarm,
        "target_role": target_role,
        "target_node": target_node,
        "data": _stable_command_value(data),
        "payload": _stable_command_value(payload),
    }

    raw = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()