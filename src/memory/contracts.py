"""Canonical memory contracts for resilient multi-swarm memory.

The memory architecture distinguishes several scopes:

- local: process-local, fast, possibly volatile memory.
- own: durable memory owned by a specific node/swarm.
- shared: CRDT/event-backed memory shared between swarms.
- global: consolidated memory managed by memory swarm.

These contracts are intentionally lightweight and can be used by local memory,
memory swarm, intelligence modules, and future dashboard/API layers.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable


MemoryScope = Literal["local", "own", "shared", "global"]

MemoryKind = Literal[
    "event",
    "experience",
    "fact",
    "rule",
    "decision",
    "artifact",
    "observation",
    "heartbeat",
    "policy",
]

MemoryConfidence = Literal["low", "medium", "high", "verified"]


@dataclass(frozen=True, slots=True)
class MemoryIdentity:
    """Ownership identity for memory records."""

    node_id: str
    swarm: str = ""
    role: str = "node"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class MemoryEnvelope:
    """Canonical serializable memory envelope."""

    id: str
    kind: MemoryKind | str
    scope: MemoryScope | str
    owner: MemoryIdentity
    payload: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    confidence: float = 1.0
    source: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    ttl_seconds: float | None = None
    verified: bool = False
    signature: str = ""

    def is_expired(self, now: float | None = None) -> bool:
        if self.ttl_seconds is None:
            return False
        current_time = time.time() if now is None else float(now)
        return current_time > self.created_at + self.ttl_seconds

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["owner"] = self.owner.to_dict()
        return data


@dataclass(frozen=True, slots=True)
class MemoryQuery:
    """Query object for memory backends."""

    scope: MemoryScope | str | None = None
    kind: MemoryKind | str | None = None
    owner_node_id: str | None = None
    swarm: str | None = None
    tags: list[str] = field(default_factory=list)
    text: str = ""
    limit: int = 50
    include_expired: bool = False


@dataclass(frozen=True, slots=True)
class MemoryStats:
    """Backend memory health and count summary."""

    total_records: int = 0
    by_scope: dict[str, int] = field(default_factory=dict)
    by_kind: dict[str, int] = field(default_factory=dict)
    verified_records: int = 0
    expired_records: int = 0
    backend: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@runtime_checkable
class MemoryBackendProtocol(Protocol):
    """Minimal protocol for local/own/shared/global memory backends."""

    async def remember(self, record: Any) -> str:
        """Store a memory record and return its id."""
        ...

    async def get_by_id(self, record_id: str) -> Any | None:
        """Return record by id, if present."""
        ...

    async def recall(self, query: MemoryQuery | dict[str, Any]) -> list[Any]:
        """Recall records matching a query."""
        ...

    async def recent(self, kind: str | None = None, limit: int = 50) -> list[Any]:
        """Return recent records."""
        ...

    async def stats(self) -> MemoryStats | dict[str, Any]:
        """Return backend stats."""
        ...