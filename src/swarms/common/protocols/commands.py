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
        payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}
        data = record.get("data") if isinstance(record.get("data"), Mapping) else {}

        command_type = str(
            record.get("command_type")
            or record.get("action")
            or payload.get("command_type")
            or payload.get("action")
            or data.get("command_type")
            or data.get("action")
            or ""
        ).upper()

        if not command_type:
            return {}

        target_swarm = str(
            record.get("target_swarm")
            or payload.get("target_swarm")
            or data.get("target_swarm")
            or payload.get("swarm")
            or data.get("swarm")
            or ""
        )

        target_role = str(
            record.get("target_role")
            or payload.get("target_role")
            or data.get("target_role")
            or payload.get("role")
            or data.get("role")
            or ""
        )

        target_node = str(
            record.get("target_node")
            or record.get("target_node_id")
            or payload.get("target_node")
            or payload.get("target_node_id")
            or data.get("target_node")
            or data.get("target_node_id")
            or payload.get("node_id")
            or data.get("node_id")
            or ""
        )

        out = dict(record)
        out["type"] = "swarm_command"
        out["command_type"] = command_type
        out["target_swarm"] = target_swarm
        out["target_role"] = target_role
        out["target_node"] = target_node
        out["payload"] = dict(payload)
        out["data"] = dict(data)
        return out

    if record_type in {"sec_command", "explorer_command", "meta_command_json", "trade_command"}:
        data = record.get("data") if isinstance(record.get("data"), Mapping) else {}
        payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}

        action = str(
            record.get("command_type")
            or record.get("action")
            or data.get("command_type")
            or data.get("action")
            or payload.get("command_type")
            or payload.get("action")
            or ""
        ).upper()

        if not action:
            return {}

        legacy_type_to_swarm = {
            "sec_command": "security",
            "explorer_command": "explorer",
            "trade_command": "trade",
        }

        legacy_type_to_role = {
            "sec_command": "node",
            "explorer_command": "node",
            "trade_command": "node",
        }

        explicit_target_swarm = (
            record.get("target_swarm")
            or data.get("target_swarm")
            or payload.get("target_swarm")
            or data.get("swarm")
            or payload.get("swarm")
        )

        explicit_target_role = (
            record.get("target_role")
            or data.get("target_role")
            or payload.get("target_role")
            or data.get("role")
            or payload.get("role")
        )

        target_swarm = str(
            explicit_target_swarm
            or legacy_type_to_swarm.get(record_type)
            or ""
        )

        target_role = str(
            explicit_target_role
            or legacy_type_to_role.get(record_type)
            or "node"
        )

        target_node = str(
            record.get("target_node")
            or record.get("target_node_id")
            or data.get("target_node")
            or data.get("target_node_id")
            or payload.get("target_node")
            or payload.get("target_node_id")
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
    """Build stable semantic fingerprint for canonical/legacy command dedup."""
    if not isinstance(command, Mapping):
        return ""

    normalized = normalize_command(command)
    if not normalized:
        normalized = dict(command)

    material = {
        "action": command_action(normalized),
        "target_swarm": str(normalized.get("target_swarm") or ""),
        "target_role": str(normalized.get("target_role") or ""),
        "target_node": str(
            normalized.get("target_node")
            or normalized.get("target_node_id")
            or ""
        ),
        "semantic_payload": _stable_command_value(
            _semantic_command_payload(normalized)
        ),
    }

    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

COMMAND_EVENT_APPLIED = "command_applied"
COMMAND_EVENT_SKIPPED = "command_skipped"
COMMAND_EVENT_BLOCKED = "command_blocked"
COMMAND_EVENT_UNSUPPORTED = "command_unsupported"

COMMAND_STATUS_APPLIED = "applied"
COMMAND_STATUS_SKIPPED = "skipped"
COMMAND_STATUS_BLOCKED = "blocked"
COMMAND_STATUS_UNSUPPORTED = "unsupported"
COMMAND_STATUS_RECEIVED = "received"

_COMMAND_SEMANTIC_ALIAS_KEYS = {
    "action",
    "command_type",
    "target_swarm",
    "swarm",
    "target_role",
    "role",
    "target_node",
    "target_node_id",
    "node_id",
}


def _semantic_command_payload(command: Mapping[str, Any]) -> Dict[str, Any]:
    """Merge payload/data into semantic extras for fingerprinting.

    Transport aliases such as action/target/node are represented by normalized
    top-level fields and must not affect the fingerprint twice.
    """
    merged: Dict[str, Any] = {}

    data = command.get("data") if isinstance(command.get("data"), Mapping) else {}
    payload = command.get("payload") if isinstance(command.get("payload"), Mapping) else {}

    for source in (data, payload):
        for key, value in source.items():
            key_text = str(key)
            if key_text in _COMMAND_SEMANTIC_ALIAS_KEYS:
                continue
            if key_text in _VOLATILE_COMMAND_KEYS:
                continue
            merged[key_text] = value

    return merged

def command_event_payload(
    command: Mapping[str, Any],
    *,
    status: str,
    reason: str = "",
    extra: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build standard command observability payload for non-lifecycle commands."""
    payload: Dict[str, Any] = {
        "action": command_action(command),
        "status": status,
        "reason": reason,
        "command_type": command_action(command),
        "command_gid": str(command.get("gid") or ""),
        "target_swarm": str(command.get("target_swarm") or ""),
        "target_role": str(command.get("target_role") or ""),
        "target_node": str(
            command.get("target_node")
            or command.get("target_node_id")
            or ""
        ),
    }

    data = command.get("data") if isinstance(command.get("data"), Mapping) else {}
    payload_data = command.get("payload") if isinstance(command.get("payload"), Mapping) else {}

    if not payload["reason"]:
        payload["reason"] = str(
            payload_data.get("reason")
            or data.get("reason")
            or command.get("reason")
            or ""
        )

    if not payload["target_node"]:
        payload["target_node"] = str(
            payload_data.get("node_id")
            or data.get("node_id")
            or payload_data.get("target_node")
            or data.get("target_node")
            or ""
        )

    if extra:
        payload.update({str(k): v for k, v in extra.items()})

    return payload


def is_command_event(record: Mapping[str, Any]) -> bool:
    """Return True if record is a command observability event."""
    return (
        record.get("type") == "swarm_event"
        and record.get("event_type")
        in {
            COMMAND_EVENT_APPLIED,
            COMMAND_EVENT_SKIPPED,
            COMMAND_EVENT_BLOCKED,
            COMMAND_EVENT_UNSUPPORTED,
        }
    )


def command_event_status(record: Mapping[str, Any]) -> str:
    """Return command event status if present."""
    payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}
    return str(payload.get("status") or "")


def command_event_action(record: Mapping[str, Any]) -> str:
    """Return command event action if present."""
    payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}
    return str(payload.get("action") or payload.get("command_type") or "")


def command_event_reason(record: Mapping[str, Any]) -> str:
    """Return command event reason if present."""
    payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}
    return str(payload.get("reason") or "")