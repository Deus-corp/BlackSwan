from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Final


def _canonical_json(data: dict[str, Any]) -> str:
    """
    Generates a deterministic JSON string for hashing.

    Uses lexicographical key sorting and compact separators to ensure
    identical inputs consistently yield identical hash strings.
    """
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class Event:
    """
    Represents an immutable event within the BlackSwan swarm's append-only ledger.

    Attributes:
        event_id: Unique UUIDv4 identifier.
        ts: Unix epoch timestamp.
        node_id: Originating node identifier.
        type: Category identifier (e.g., 'Observation', 'Action').
        payload: Event-specific data dictionary.
        parent_id: Optional reference to a preceding event ID.
        hash: SHA256 integrity hash of the event contents.
    """
    event_id: str
    ts: float
    node_id: str
    type: str
    payload: dict[str, Any]
    parent_id: str | None = None
    hash: str = ""

    @classmethod
    def create(
        cls,
        node_id: str,
        event_type: str,
        payload: dict[str, Any],
        parent_id: str | None = None,
        ts: float | None = None,
    ) -> Event:
        """
        Creates a new Event instance and computes its integrity hash.

        Args:
            node_id: Identifier of the originating node.
            event_type: Category identifier for the event.
            payload: Data dictionary content of the event.
            parent_id: Optional UUID of a related prior event.
            ts: Optional override for the event timestamp.
        """
        if not node_id.strip():
            raise ValueError("node_id must be a non-empty string.")
        if not event_type.strip():
            raise ValueError("event_type must be a non-empty string.")
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dictionary.")

        event_id: str = str(uuid.uuid4())
        timestamp: float = ts if ts is not None else time.time()

        base_data: dict[str, Any] = {
            "event_id": event_id,
            "ts": timestamp,
            "node_id": node_id,
            "type": event_type,
            "parent_id": parent_id,
            "payload": payload,
        }
        event_hash: str = hashlib.sha256(_canonical_json(base_data).encode("utf-8")).hexdigest()

        return cls(
            event_id=event_id,
            ts=timestamp,
            node_id=node_id,
            type=event_type,
            payload=payload,
            parent_id=parent_id,
            hash=event_hash,
        )

    def verify_hash(self) -> bool:
        """
        Validates the event's integrity by comparing its hash against the current content.
        """
        base_data: dict[str, Any] = {
            "event_id": self.event_id,
            "ts": self.ts,
            "node_id": self.node_id,
            "type": self.type,
            "parent_id": self.parent_id,
            "payload": self.payload,
        }
        expected_hash: str = hashlib.sha256(_canonical_json(base_data).encode("utf-8")).hexdigest()
        return expected_hash == self.hash

    def to_dict(self) -> dict[str, Any]:
        """
        Serializes the event into a standard dictionary representation.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Event:
        """
        Deserializes a dictionary into an Event instance.

        Raises:
            ValueError: If required fields are missing or malformed.
            TypeError: If the input is not a dictionary.
        """
        if not isinstance(data, dict):
            raise TypeError("Input data must be a dictionary.")

        required: Final[set[str]] = {"event_id", "ts", "node_id", "type", "payload"}
        if not required.issubset(data.keys()):
            missing = required - data.keys()
            raise ValueError(f"Missing required keys for Event: {missing}")

        try:
            ts = float(data["ts"])
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid timestamp format: {data.get('ts')}") from e

        return cls(
            event_id=str(data["event_id"]),
            ts=ts,
            node_id=str(data["node_id"]),
            type=str(data["type"]),
            payload=dict(data["payload"]),
            parent_id=data.get("parent_id"),
            hash=str(data.get("hash", "")),
        )