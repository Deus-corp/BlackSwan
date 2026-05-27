from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Literal


SwarmName = Literal[
    "trade",
    "security",
    "explorer",
    "improver",
    "overseer",
    "memory",
    "simulation",
]

SwarmStatus = Literal[
    "starting",
    "running",
    "paused",
    "degraded",
    "stopping",
    "stopped",
    "failed",
]


@dataclass(frozen=True, slots=True)
class SwarmHeartbeat:
    """Canonical heartbeat payload for every BlackSwan swarm."""

    swarm: SwarmName | str
    node_id: str
    role: str = "node"
    status: SwarmStatus | str = "running"
    capabilities: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    type: str = "swarm_heartbeat"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)

        # Backward-compatible aliases commonly expected by older readers.
        data.setdefault("node", self.node_id)
        data.setdefault("swarm_type", self.swarm)
        return data


@dataclass(frozen=True, slots=True)
class SwarmCommand:
    """Canonical command envelope for swarm coordination."""

    command: str
    target_swarm: SwarmName | str
    target_node_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    ttl_sec: float = 60.0
    issued_by: str = "operator"
    timestamp: float = field(default_factory=time.time)
    type: str = "swarm_command"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def is_expired(self, now: float | None = None) -> bool:
        current_time = time.time() if now is None else float(now)
        return current_time > self.timestamp + self.ttl_sec


@dataclass(frozen=True, slots=True)
class SwarmEvent:
    """Canonical event envelope emitted by a swarm node."""

    swarm: SwarmName | str
    node_id: str
    event: str
    payload: dict[str, Any] = field(default_factory=dict)
    severity: str = "info"
    timestamp: float = field(default_factory=time.time)
    type: str = "swarm_event"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SwarmCapability:
    """Describes one capability exposed by a swarm node."""

    name: str
    description: str = ""
    risk_level: int = 0
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SwarmPolicy:
    """Runtime safety/permission policy for a swarm node."""

    dry_run: bool = True
    execution_enabled: bool = False
    allow_network: bool = False
    allow_filesystem_write: bool = False
    allow_code_changes: bool = False
    max_risk_level: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def allows(self, capability: SwarmCapability | dict[str, Any]) -> bool:
        if isinstance(capability, SwarmCapability):
            risk_level = capability.risk_level
            enabled = capability.enabled
        else:
            risk_level = int(capability.get("risk_level", 0))
            enabled = bool(capability.get("enabled", True))

        return enabled and risk_level <= self.max_risk_level

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)