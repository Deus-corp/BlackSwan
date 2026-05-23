#!/usr/bin/env python3
"""Canonical swarm event schema.

SwarmEvent is the common event envelope for all swarm ecosystems.

It is intentionally generic and domain-neutral. Trade, security, explorer,
improver, and overseer events should fit into this envelope through payload
and provenance fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional

from src.swarms.common.utils import new_gid, to_jsonable, utc_ts


@dataclass(frozen=True, slots=True)
class SwarmEvent:
    """Canonical event emitted by any swarm component."""

    event_type: str
    source_swarm: str
    source_node: str
    payload: Dict[str, Any] = field(default_factory=dict)

    gid: str = ""
    parent_gid: Optional[str] = None
    trace_id: Optional[str] = None
    timestamp: float = 0.0
    severity: float = 0.0
    source_agent: Optional[str] = None
    role: Optional[str] = None
    provenance: Dict[str, Any] = field(default_factory=dict)

    type: str = "swarm_event"

    def __post_init__(self) -> None:
        if not self.event_type:
            raise ValueError("event_type is required")
        if not self.source_swarm:
            raise ValueError("source_swarm is required")
        if not self.source_node:
            raise ValueError("source_node is required")

        object.__setattr__(self, "gid", self.gid or new_gid("evt", namespace=self.source_swarm))
        object.__setattr__(self, "timestamp", float(self.timestamp or utc_ts()))
        object.__setattr__(self, "severity", max(0.0, min(1.0, float(self.severity))))

        if self.source_agent is None:
            object.__setattr__(self, "source_agent", self.source_node)

    def to_dict(self) -> Dict[str, Any]:
        """Return CRDT/event-store compatible dict."""
        return {
            "type": self.type,
            "gid": self.gid,
            "event_type": self.event_type,
            "source_swarm": self.source_swarm,
            "source_agent": self.source_agent,
            "source_node": self.source_node,
            "role": self.role,
            "parent_gid": self.parent_gid,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "severity": self.severity,
            "payload": to_jsonable(self.payload),
            "provenance": to_jsonable(self.provenance),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "SwarmEvent":
        """Build SwarmEvent from a mapping.

        This expects canonical-ish data. Legacy normalization should live in
        common.protocols.events.
        """
        payload = data.get("payload", {})
        provenance = data.get("provenance", {})

        return cls(
            gid=str(data.get("gid") or ""),
            event_type=str(data.get("event_type") or data.get("type") or ""),
            source_swarm=str(data.get("source_swarm") or data.get("swarm") or ""),
            source_agent=str(data.get("source_agent") or data.get("agent_id") or data.get("node_id") or "") or None,
            source_node=str(data.get("source_node") or data.get("node_id") or data.get("agent_id") or ""),
            role=str(data.get("role") or "") or None,
            parent_gid=str(data.get("parent_gid") or "") or None,
            trace_id=str(data.get("trace_id") or "") or None,
            timestamp=float(data.get("timestamp") or 0.0),
            severity=float(data.get("severity") or 0.0),
            payload=dict(payload) if isinstance(payload, Mapping) else {},
            provenance=dict(provenance) if isinstance(provenance, Mapping) else {},
        )