#!/usr/bin/env python3
"""Compatibility façade for the security shared runtime.

New code should prefer:
    src.swarms.common
    src.swarms.common.protocols
    src.swarms.common.schemas

This module remains to keep older security code imports stable.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.swarms.common import (
    json_dumps,
    json_loads_dict,
    make_swarm_command,
    make_swarm_event,
    new_gid,
    utc_ts,
    utc_ts_int,
)
from src.swarms.common.utils import compact_repr
from src.swarms.common.utils.ids import new_gid as common_new_gid
from src.swarms.common.utils.serialization import json_loads_dict as common_json_loads_dict

from .firewall import FirewallManager
from .memory import (
    FirewallPolicy,
    SecurityCommand,
    SecurityEvent,
    SecurityEventType,
    SecurityMemory,
    SecurityPolicy,
    command_exists,
    extract_domain,
    now_ts,
)

__all__ = [
    "FirewallManager",
    "FirewallPolicy",
    "SecurityCommand",
    "SecurityEvent",
    "SecurityEventType",
    "SecurityMemory",
    "SecurityPolicy",
    "command_exists",
    "extract_domain",
    "json_dumps",
    "json_loads_safe",
    "make_security_command",
    "make_security_event",
    "new_gid",
    "now_ts",
    "parse_json_loose",
    "prompt_hash",
]


def prompt_hash(text: str) -> str:
    """Compatibility wrapper for SHA-256 prompt hash."""
    import hashlib

    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def json_loads_safe(text: str | bytes | None) -> Dict[str, Any]:
    """Compatibility wrapper around common JSON loader."""
    return json_loads_dict(text)


def parse_json_loose(text: str | bytes | None) -> Dict[str, Any]:
    """Best-effort JSON object extraction.

    Kept for compatibility with older strategist/meta-agent code.
    """
    if text is None:
        return {}

    if isinstance(text, bytes):
        try:
            text = text.decode("utf-8", errors="ignore")
        except Exception:
            return {}

    parsed = common_json_loads_dict(text)
    if parsed:
        return parsed

    if not isinstance(text, str):
        return {}

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        return {}

    return common_json_loads_dict(text[start : end + 1])


def make_security_event(
    *,
    event_type: SecurityEventType,
    source_gid: str,
    parent_gid: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    provenance: Optional[Dict[str, Any]] = None,
    gid_prefix: str = "sec_evt",
) -> SecurityEvent:
    """Build legacy-compatible security event using canonical event protocol."""
    gid = common_new_gid(gid_prefix, namespace="security")

    canonical = make_swarm_event(
        event_type=event_type,
        source_swarm="security",
        source_node=source_gid,
        source_agent=source_gid,
        parent_gid=parent_gid,
        payload=data or {},
        provenance=provenance or {},
    )

    return {
        "type": "security_event",
        "event_type": event_type,
        "gid": gid,
        "source_gid": source_gid,
        "parent_gid": parent_gid,
        "timestamp": float(canonical.get("timestamp") or utc_ts()),
        "provenance": provenance or {},
        "data": data or {},
    }


def make_security_command(
    *,
    action: str,
    source_gid: str,
    parent_gid: Optional[str] = None,
    expires_at: Optional[int] = None,
    data: Optional[Dict[str, Any]] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> SecurityCommand:
    """Build legacy-compatible security command using canonical command protocol."""
    gid = common_new_gid("sec_cmd", namespace="security")

    canonical = make_swarm_command(
        command_type=action,
        source_agent=source_gid,
        source_swarm="security",
        parent_gid=parent_gid,
        target_swarm="security",
        target_role="node",
        ttl_seconds=max(1, int(expires_at - utc_ts_int())) if expires_at else 600,
        payload=data or {},
        provenance=provenance or {},
    )

    return {
        "type": "sec_command",
        "event_type": "command_issued",
        "gid": gid,
        "source_gid": source_gid,
        "parent_gid": parent_gid,
        "timestamp": float(canonical.get("timestamp") or utc_ts()),
        "expires_at": float(expires_at or canonical.get("expires_at") or utc_ts() + 600),
        "provenance": provenance or {},
        "data": {"action": action, **(data or {})},
    }