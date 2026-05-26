"""Immutable append-only ledger events with deterministic integrity hashes."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Final


def _canonical_json(data: dict[str, Any]) -> str:
    """Return deterministic compact JSON suitable for hashing."""
    return json.dumps(
        data,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def _compute_hash(data: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(data).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Event:
    """Immutable event stored in the BlackSwan append-only ledger."""

    event_id: str
    ts: float
    node_id: str
    type: str
    payload: dict[str, Any]
    parent_id: str | None = None
    hash: str = ""

    def __post_init__(self) -> None:
        if not str(self.event_id or "").strip():
            raise ValueError("event_id must be a non-empty string")
        if not str(self.node_id or "").strip():
            raise ValueError("node_id must be a non-empty string")
        if not str(self.type or "").strip():
            raise ValueError("type must be a non-empty string")
        if not isinstance(self.payload, dict):
            raise TypeError("payload must be a dictionary")

        object.__setattr__(self, "event_id", str(self.event_id).strip())
        object.__setattr__(self, "ts", float(self.ts))
        object.__setattr__(self, "node_id", str(self.node_id).strip())
        object.__setattr__(self, "type", str(self.type).strip())
        object.__setattr__(self, "payload", dict(self.payload))

        if self.parent_id is not None:
            parent_id = str(self.parent_id).strip()
            object.__setattr__(self, "parent_id", parent_id or None)

        if not self.hash:
            object.__setattr__(self, "hash", self.compute_hash())

    @classmethod
    def create(
        cls,
        node_id: str,
        event_type: str,
        payload: dict[str, Any],
        parent_id: str | None = None,
        ts: float | None = None,
        event_id: str | None = None,
    ) -> Event:
        """Create a new event and compute its integrity hash."""
        return cls(
            event_id=str(event_id or uuid.uuid4()),
            ts=float(ts if ts is not None else time.time()),
            node_id=node_id,
            type=event_type,
            payload=payload,
            parent_id=parent_id,
        )

    @property
    def hash_payload(self) -> dict[str, Any]:
        """Return the fields covered by the integrity hash."""
        return {
            "event_id": self.event_id,
            "ts": self.ts,
            "node_id": self.node_id,
            "type": self.type,
            "parent_id": self.parent_id,
            "payload": self.payload,
        }

    def compute_hash(self) -> str:
        """Compute the SHA256 integrity hash for current event contents."""
        return _compute_hash(self.hash_payload)

    def verify_hash(self) -> bool:
        """Return True if the stored hash matches the event contents."""
        return self.compute_hash() == self.hash

    def to_dict(self) -> dict[str, Any]:
        """Serialize the event to a dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Event:
        """Deserialize an Event from a dictionary."""
        if not isinstance(data, dict):
            raise TypeError("Event data must be a dictionary")

        required: Final[set[str]] = {"event_id", "ts", "node_id", "type", "payload"}
        missing = required.difference(data)
        if missing:
            raise ValueError(f"Missing required Event keys: {sorted(missing)}")

        payload = data["payload"]
        if not isinstance(payload, dict):
            raise TypeError("Event payload must be a dictionary")

        return cls(
            event_id=str(data["event_id"]),
            ts=float(data["ts"]),
            node_id=str(data["node_id"]),
            type=str(data["type"]),
            payload=dict(payload),
            parent_id=data.get("parent_id"),
            hash=str(data.get("hash", "")),
        )