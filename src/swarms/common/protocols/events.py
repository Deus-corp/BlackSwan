#!/usr/bin/env python3
"""Event protocol helpers.

Provides canonical event builders and backward-compatible normalization.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Dict, Iterable, Optional

from src.swarms.common.schemas import SwarmEvent
from src.swarms.common.utils import new_gid, utc_ts

CANONICAL_EVENT_TYPE = "swarm_event"

LEGACY_EVENT_TYPES = {
    "security_event",
    "file_integrity_alert",
    "vulnerability_alert",
    "open_ports_detected",
    "ip_blocked",
    "all_ips_unblocked",
    "explorer_finding",
    "trade_opened",
    "trade_closed",
    "trade_failed",
    "policy_evaluated",
    "command_applied",
    "command_issued",
}

KNOWN_EVENT_TYPES = {
    CANONICAL_EVENT_TYPE,
    *LEGACY_EVENT_TYPES,
}


def is_event(value: Any) -> bool:
    """Return True if value looks like a swarm event."""
    if not isinstance(value, Mapping):
        return False

    record_type = str(value.get("type", ""))
    if record_type in KNOWN_EVENT_TYPES:
        return True

    return bool(value.get("event_type")) and record_type not in {
        "swarm_command",
        "sec_command",
        "meta_command_json",
        "explorer_command",
        "swarm_heartbeat",
        "security_heartbeat",
        "trade_heartbeat",
        "explorer_heartbeat",
    }


def make_swarm_event(
    *,
    event_type: str,
    source_swarm: str,
    source_node: str,
    payload: Optional[Dict[str, Any]] = None,
    source_agent: Optional[str] = None,
    role: Optional[str] = None,
    parent_gid: Optional[str] = None,
    trace_id: Optional[str] = None,
    severity: float = 0.0,
    provenance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build canonical CRDT/event-store compatible swarm event dict."""
    event = SwarmEvent(
        event_type=event_type,
        source_swarm=source_swarm,
        source_node=source_node,
        source_agent=source_agent,
        role=role,
        parent_gid=parent_gid,
        trace_id=trace_id,
        severity=severity,
        payload=payload or {},
        provenance=provenance or {},
    )
    return event.to_dict()


def normalize_event(value: Mapping[str, Any]) -> Dict[str, Any]:
    """Normalize canonical or legacy event into canonical dict."""
    if not is_event(value):
        raise ValueError(f"Not a known event: {value!r}")

    record_type = str(value.get("type", ""))

    if record_type == CANONICAL_EVENT_TYPE:
        return SwarmEvent.from_mapping(value).to_dict()

    return _normalize_legacy_event(value)


def normalize_events(values: Iterable[Any]) -> list[Dict[str, Any]]:
    """Normalize all event-like values from an iterable."""
    normalized: list[Dict[str, Any]] = []
    for value in values:
        if isinstance(value, Mapping) and is_event(value):
            try:
                normalized.append(normalize_event(value))
            except ValueError:
                continue
    return normalized


def event_severity(value: Mapping[str, Any]) -> float:
    """Return normalized event severity in 0..1."""
    try:
        severity = float(value.get("severity", 0.0))
    except (TypeError, ValueError):
        severity = _infer_severity(value)

    return max(0.0, min(1.0, severity))


def _normalize_legacy_event(value: Mapping[str, Any]) -> Dict[str, Any]:
    record_type = str(value.get("type", ""))
    event_type = str(value.get("event_type") or record_type)
    source_swarm = _infer_swarm(value)
    source_node = str(value.get("source_node") or value.get("node_id") or value.get("source_gid") or source_swarm)
    provenance = value.get("provenance") if isinstance(value.get("provenance"), Mapping) else {}

    payload = _legacy_payload(value)

    event = SwarmEvent(
        gid=str(value.get("gid") or new_gid("evt", namespace=source_swarm)),
        event_type=event_type,
        source_swarm=source_swarm,
        source_agent=str(value.get("source_agent") or value.get("source_gid") or source_node),
        source_node=source_node,
        role=str(value.get("role") or "") or None,
        parent_gid=str(value.get("parent_gid") or "") or None,
        trace_id=str(value.get("trace_id") or "") or None,
        timestamp=float(value.get("timestamp") or utc_ts()),
        severity=event_severity(value),
        payload=payload,
        provenance={
            "legacy_type": record_type,
            **dict(provenance),
        },
    )

    return event.to_dict()


def _infer_swarm(value: Mapping[str, Any]) -> str:
    if value.get("source_swarm"):
        return str(value["source_swarm"])
    if value.get("swarm"):
        return str(value["swarm"])

    record_type = str(value.get("type", ""))
    event_type = str(value.get("event_type", ""))

    token = f"{record_type}:{event_type}"

    if "security" in token or record_type in {
        "security_event",
        "file_integrity_alert",
        "vulnerability_alert",
        "open_ports_detected",
        "ip_blocked",
        "all_ips_unblocked",
    }:
        return "security"

    if "explorer" in token or record_type == "explorer_finding":
        return "explorer"

    if "trade" in token or record_type in {"trade_opened", "trade_closed", "trade_failed"}:
        return "trade"

    if "overseer" in token or event_type == "policy_evaluated":
        return "overseer"

    return "unknown"


def _infer_severity(value: Mapping[str, Any]) -> float:
    record_type = str(value.get("type", ""))
    event_type = str(value.get("event_type", ""))

    token = f"{record_type}:{event_type}"

    if "vulnerability" in token:
        return 0.9
    if "integrity" in token:
        return 0.95
    if "failed" in token:
        return 0.7
    if "alert" in token:
        return 0.75
    if "blocked" in token:
        return 0.3

    return 0.0


def _legacy_payload(value: Mapping[str, Any]) -> Dict[str, Any]:
    payload = value.get("payload")
    data = value.get("data")

    if isinstance(payload, Mapping):
        return dict(payload)

    if isinstance(data, Mapping):
        return dict(data)

    excluded = {
        "type",
        "gid",
        "event_type",
        "source_swarm",
        "source_agent",
        "source_node",
        "node_id",
        "source_gid",
        "parent_gid",
        "trace_id",
        "timestamp",
        "severity",
        "role",
        "provenance",
    }

    return {str(k): v for k, v in value.items() if k not in excluded}