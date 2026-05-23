#!/usr/bin/env python3
"""Canonical swarm command schema.

SwarmCommand is the common command envelope for commands routed from:
- overseer -> meta-agents
- meta-agents -> nodes
- nodes -> local execution handlers
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional

from src.swarms.common.utils import expires_in, is_expired, new_gid, to_jsonable, utc_ts


@dataclass(frozen=True, slots=True)
class SwarmCommand:
    """Canonical distributed command."""

    command_type: str
    source_agent: str
    source_swarm: str
    payload: Dict[str, Any] = field(default_factory=dict)

    gid: str = ""
    parent_gid: Optional[str] = None
    target_swarm: Optional[str] = None
    target_node: Optional[str] = None
    target_role: Optional[str] = None
    timestamp: float = 0.0
    expires_at: float = 0.0
    priority: int = 0
    trace_id: Optional[str] = None
    provenance: Dict[str, Any] = field(default_factory=dict)

    type: str = "swarm_command"

    def __post_init__(self) -> None:
        if not self.command_type:
            raise ValueError("command_type is required")
        if not self.source_agent:
            raise ValueError("source_agent is required")
        if not self.source_swarm:
            raise ValueError("source_swarm is required")

        object.__setattr__(self, "gid", self.gid or new_gid("cmd", namespace=self.source_swarm))
        object.__setattr__(self, "timestamp", float(self.timestamp or utc_ts()))
        object.__setattr__(self, "expires_at", float(self.expires_at or expires_in(600)))
        object.__setattr__(self, "priority", int(self.priority))

    @property
    def expired(self) -> bool:
        """Whether this command has expired."""
        return is_expired(self.expires_at)

    def to_dict(self, *, include_legacy_data: bool = True) -> Dict[str, Any]:
        """Return CRDT-compatible dict.

        include_legacy_data=True keeps backward compatibility with current
        agents that read command["data"]["action"].
        """
        data = {
            "type": self.type,
            "gid": self.gid,
            "command_type": self.command_type,
            "source_agent": self.source_agent,
            "source_swarm": self.source_swarm,
            "parent_gid": self.parent_gid,
            "target_swarm": self.target_swarm,
            "target_node": self.target_node,
            "target_role": self.target_role,
            "timestamp": self.timestamp,
            "expires_at": self.expires_at,
            "priority": self.priority,
            "trace_id": self.trace_id,
            "payload": to_jsonable(self.payload),
            "provenance": to_jsonable(self.provenance),
        }

        if include_legacy_data:
            data["data"] = {
                "action": self.command_type,
                **to_jsonable(self.payload),
            }

        return data

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "SwarmCommand":
        """Build SwarmCommand from a canonical-ish mapping.

        Legacy normalization should live in common.protocols.commands.
        """
        payload = data.get("payload")
        legacy_data = data.get("data")
        provenance = data.get("provenance")

        if not isinstance(payload, Mapping):
            payload = legacy_data if isinstance(legacy_data, Mapping) else {}

        command_type = (
            data.get("command_type")
            or data.get("action")
            or (legacy_data.get("action") if isinstance(legacy_data, Mapping) else None)
            or ""
        )

        return cls(
            gid=str(data.get("gid") or ""),
            command_type=str(command_type).upper(),
            source_agent=str(data.get("source_agent") or data.get("source_gid") or data.get("node_id") or "unknown"),
            source_swarm=str(data.get("source_swarm") or data.get("swarm") or "unknown"),
            parent_gid=str(data.get("parent_gid") or "") or None,
            target_swarm=str(data.get("target_swarm") or data.get("swarm") or "") or None,
            target_node=str(data.get("target_node") or data.get("target_node_id") or "") or None,
            target_role=str(data.get("target_role") or "") or None,
            timestamp=float(data.get("timestamp") or 0.0),
            expires_at=float(data.get("expires_at") or 0.0),
            priority=int(data.get("priority") or 0),
            trace_id=str(data.get("trace_id") or "") or None,
            payload=dict(payload) if isinstance(payload, Mapping) else {},
            provenance=dict(provenance) if isinstance(provenance, Mapping) else {},
        )