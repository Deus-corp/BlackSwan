#!/usr/bin/env python3
"""Canonical swarm heartbeat schema."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional

from src.swarms.common.utils import new_gid, to_jsonable, utc_ts


@dataclass(frozen=True, slots=True)
class SwarmHeartbeat:
    """Canonical heartbeat emitted by nodes, meta-agents, and overseers."""

    node_id: str
    swarm: str
    role: str
    status: str = "ok"
    metrics: Dict[str, Any] = field(default_factory=dict)

    gid: str = ""
    agent_id: Optional[str] = None
    version: str = "0.1.0"
    timestamp: float = 0.0
    trace_id: Optional[str] = None
    provenance: Dict[str, Any] = field(default_factory=dict)

    type: str = "swarm_heartbeat"

    def __post_init__(self) -> None:
        if not self.node_id:
            raise ValueError("node_id is required")
        if not self.swarm:
            raise ValueError("swarm is required")
        if not self.role:
            raise ValueError("role is required")

        object.__setattr__(self, "gid", self.gid or new_gid("hb", namespace=self.swarm))
        object.__setattr__(self, "timestamp", float(self.timestamp or utc_ts()))

        if self.agent_id is None:
            object.__setattr__(self, "agent_id", self.node_id)

    def to_dict(self) -> Dict[str, Any]:
        """Return CRDT-compatible heartbeat dict."""
        return {
            "type": self.type,
            "gid": self.gid,
            "node_id": self.node_id,
            "agent_id": self.agent_id,
            "swarm": self.swarm,
            "role": self.role,
            "version": self.version,
            "status": self.status,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
            "metrics": to_jsonable(self.metrics),
            "provenance": to_jsonable(self.provenance),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "SwarmHeartbeat":
        """Build SwarmHeartbeat from a canonical-ish mapping.

        Legacy normalization should live in common.protocols.heartbeats.
        """
        metrics = data.get("metrics")
        provenance = data.get("provenance")

        return cls(
            gid=str(data.get("gid") or ""),
            node_id=str(data.get("node_id") or data.get("agent_id") or ""),
            agent_id=str(data.get("agent_id") or data.get("node_id") or "") or None,
            swarm=str(data.get("swarm") or data.get("source_swarm") or ""),
            role=str(data.get("role") or "node"),
            version=str(data.get("version") or "0.1.0"),
            status=str(data.get("status") or "ok"),
            timestamp=float(data.get("timestamp") or 0.0),
            trace_id=str(data.get("trace_id") or "") or None,
            metrics=dict(metrics) if isinstance(metrics, Mapping) else {},
            provenance=dict(provenance) if isinstance(provenance, Mapping) else {},
        )