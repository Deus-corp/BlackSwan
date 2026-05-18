# src/core/events.py
"""
Append-only event definitions for the BlackSwan swarm.
Each event is immutable and has a stable hash.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional
import hashlib
import json
import time
import uuid


def _canonical_json(data: Dict[str, Any]) -> str:
    """
    Generates a canonical JSON string for hashing.
    Ensures consistent key ordering and no unnecessary whitespace,
    which is crucial for producing stable hashes.

    Args:
        data: A dictionary to be serialized into a canonical JSON string.

    Returns:
        A canonical JSON string representation of the input data.
    """
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


@dataclass(frozen=True)
class Event:
    """
    Represents an immutable event within the BlackSwan swarm's append-only ledger.

    Each event is uniquely identified, timestamped, associated with a source node,
    has a specific type, carries a payload, and includes a self-verifying hash.
    It can optionally reference a parent event.
    """
    event_id: str
    ts: float
    node_id: str
    type: str
    payload: Dict[str, Any]
    parent_id: Optional[str] = None
    hash: str = ""

    @classmethod
    def create(
        cls,
        node_id: str,
        event_type: str,
        payload: Dict[str, Any],
        parent_id: Optional[str] = None,
        ts: Optional[float] = None,
    ) -> Event:
        """
        Creates a new Event instance, automatically generating a unique ID,
        timestamp (if not provided), and a cryptographic hash.

        Args:
            node_id: The identifier of the node that originated this event.
            event_type: A string describing the category or type of the event.
            payload: A dictionary containing the specific data pertinent to this event.
            parent_id: Optional. The ID of a preceding event to which this event relates.
            ts: Optional. A specific timestamp (Unix epoch float) for the event.
                If None, the current UTC time is used.

        Returns:
            A new Event instance with all fields populated, including the calculated hash.
        """
        event_id = str(uuid.uuid4())
        timestamp = time.time() if ts is None else ts

        base = {
            "event_id": event_id,
            "ts": timestamp,
            "node_id": node_id,
            "type": event_type,
            "parent_id": parent_id,
            "payload": payload,
        }
        event_hash = hashlib.sha256(_canonical_json(base).encode("utf-8")).hexdigest()

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
        Verifies the integrity of the event by re-calculating its hash
        based on its content and comparing it to the `hash` field.

        Returns:
            True if the re-calculated hash matches the stored hash, False otherwise.
        """
        base = {
            "event_id": self.event_id,
            "ts": self.ts,
            "node_id": self.node_id,
            "type": self.type,
            "parent_id": self.parent_id,
            "payload": self.payload,
        }
        expected = hashlib.sha256(_canonical_json(base).encode("utf-8")).hexdigest()
        return expected == self.hash

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the Event instance into a dictionary representation.

        Returns:
            A dictionary containing all event attributes.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Event:
        """
        Creates an Event instance from a dictionary.
        This is typically used when deserializing an event from storage.

        Args:
            data: A dictionary containing the event's data, conforming to the
                  Event's structure.

        Returns:
            An Event instance populated with data from the dictionary.
        """
        return cls(
            event_id=data["event_id"],
            ts=float(data["ts"]),
            node_id=data["node_id"],
            type=data["type"],
            payload=data["payload"],
            parent_id=data.get("parent_id"), # Use .get() for optional fields for robustness
            hash=data.get("hash", ""),     # Use .get() for optional fields for robustness
        )