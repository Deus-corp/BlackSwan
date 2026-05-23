#!/usr/bin/env python3
"""Heartbeat protocol helpers.

Provides canonical heartbeat builders and backward-compatible normalization for:

    swarm_heartbeat
    security_heartbeat
    trade_heartbeat
    explorer_heartbeat
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Dict, Iterable, Optional

from src.swarms.common.schemas import SwarmHeartbeat
from src.swarms.common.utils import new_gid, utc_ts

CANONICAL_HEARTBEAT_TYPE = "swarm_heartbeat"

LEGACY_HEARTBEAT_TYPES = {
    "security_heartbeat",
    "trade_heartbeat",
    "explorer_heartbeat",
    "overseer_heartbeat",
    "meta_heartbeat",
}

KNOWN_HEARTBEAT_TYPES = {
    CANONICAL_HEARTBEAT_TYPE,
    *LEGACY_HEARTBEAT_TYPES,
}


def is_heartbeat(value: Any) -> bool:
    """Return True if value looks like a swarm heartbeat."""
    return isinstance(value, Mapping) and str(value.get("type", "")) in KNOWN_HEARTBEAT_TYPES


def make_swarm_heartbeat(
    *,
    node_id: str,
    swarm: str,
    role: str,
    status: str = "ok",
    metrics: Optional[Dict[str, Any]] = None,
    agent_id: Optional[str] = None,
    version: str = "0.1.0",
    trace_id: Optional[str] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build canonical CRDT-compatible heartbeat dict."""
    heartbeat = SwarmHeartbeat(
        node_id=node_id,
        agent_id=agent_id,
        swarm=swarm,
        role=role,
        status=status,
        version=version,
        metrics=metrics or {},
        trace_id=trace_id,
        provenance=provenance or {},
    )
    return heartbeat.to_dict()


def normalize_heartbeat(value: Mapping[str, Any]) -> Dict[str, Any]:
    """Normalize canonical or legacy heartbeat into canonical dict."""
    if not is_heartbeat(value):
        raise ValueError(f"Not a known heartbeat: {value!r}")

    record_type = str(value.get("type", ""))

    if record_type == CANONICAL_HEARTBEAT_TYPE:
        return SwarmHeartbeat.from_mapping(value).to_dict()

    return _normalize_legacy_heartbeat(value)


def normalize_heartbeats(values: Iterable[Any]) -> list[Dict[str, Any]]:
    """Normalize all heartbeat-like values from an iterable."""
    normalized: list[Dict[str, Any]] = []
    for value in values:
        if isinstance(value, Mapping) and is_heartbeat(value):
            try:
                normalized.append(normalize_heartbeat(value))
            except ValueError:
                continue
    return normalized


def heartbeat_swarm(value: Mapping[str, Any]) -> str:
    """Infer swarm from canonical or legacy heartbeat."""
    if value.get("swarm"):
        return str(value["swarm"])

    record_type = str(value.get("type", ""))
    return _infer_swarm_from_heartbeat_type(record_type)


def heartbeat_node_id(value: Mapping[str, Any]) -> str:
    """Extract node_id from heartbeat."""
    return str(value.get("node_id") or value.get("agent_id") or value.get("gid") or "")


def _normalize_legacy_heartbeat(value: Mapping[str, Any]) -> Dict[str, Any]:
    record_type = str(value.get("type", ""))
    swarm = _infer_swarm_from_heartbeat_type(record_type)

    node_id = str(value.get("node_id") or value.get("agent_id") or value.get("gid") or f"{swarm}-unknown")
    provenance = value.get("provenance") if isinstance(value.get("provenance"), Mapping) else {}

    metrics = _legacy_metrics(value, swarm)

    heartbeat = SwarmHeartbeat(
        gid=str(value.get("gid") or new_gid("hb", namespace=swarm)),
        node_id=node_id,
        agent_id=str(value.get("agent_id") or node_id),
        swarm=swarm,
        role=str(value.get("role") or "node"),
        version=str(value.get("version") or "legacy"),
        status=str(value.get("status") or "ok"),
        timestamp=float(value.get("timestamp") or utc_ts()),
        trace_id=str(value.get("trace_id") or "") or None,
        metrics=metrics,
        provenance={
            "legacy_type": record_type,
            **dict(provenance),
        },
    )

    return heartbeat.to_dict()


def _infer_swarm_from_heartbeat_type(record_type: str) -> str:
    if record_type == "security_heartbeat":
        return "security"
    if record_type == "trade_heartbeat":
        return "trade"
    if record_type == "explorer_heartbeat":
        return "explorer"
    if record_type == "overseer_heartbeat":
        return "overseer"
    if record_type == "meta_heartbeat":
        return "meta"
    return "unknown"


def _legacy_metrics(value: Mapping[str, Any], swarm: str) -> Dict[str, Any]:
    """Extract legacy top-level heartbeat fields into metrics."""
    excluded = {
        "type",
        "gid",
        "node_id",
        "agent_id",
        "swarm",
        "role",
        "version",
        "status",
        "timestamp",
        "trace_id",
        "provenance",
        "metrics",
    }

    metrics: Dict[str, Any] = {}

    existing_metrics = value.get("metrics")
    if isinstance(existing_metrics, Mapping):
        metrics.update(dict(existing_metrics))

    for key, item in value.items():
        if key not in excluded:
            metrics[str(key)] = item

    metrics.setdefault("swarm", swarm)
    return metrics