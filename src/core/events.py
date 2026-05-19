# src/core/events.py
"""
Append-only event definitions for the BlackSwan swarm.
Each event is immutable and has a stable hash.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


def _canonical_json(data: Dict[str, Any]) -> str:
    """
    Generates a canonical JSON string for hashing.
    Ensures consistent key ordering and no unnecessary whitespace,
    which is crucial for producing stable and reproducible hashes.

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
    It can optionally reference a parent event to establish causality or lineage.

    Attributes:
        event_id: A unique string identifier for the event (UUID).
        ts: A float representing the Unix epoch timestamp (UTC) when the event was created.
        node_id: The identifier of the node that originated this event.
        type: A string describing the category or type of the event (e.g., "Observation", "Action", "Thought").
        payload: A dictionary containing the specific data pertinent to this event.
                 This is the actual content of the event.
        parent_id: Optional. The ID of a preceding event to which this event relates,
                   establishing a parent-child relationship in an event graph.
        hash: A cryptographic hash (SHA256) of the event's canonical representation,
              used for integrity verification. This field is populated by the .create() method.
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
        timestamp (if not provided), and a cryptographic hash based on its content.

        Args:
            node_id: The identifier of the node that originated this event.
            event_type: A string describing the category or type of the event.
            payload: A dictionary containing the specific data pertinent to this event.
            parent_id: Optional. The ID of a preceding event to which this event relates.
            ts: Optional. A specific timestamp (Unix epoch float) for the event.
                If None, the current UTC time is used (via `time.time()`).

        Returns:
            A new Event instance with all fields populated, including the calculated hash.
        """
        event_id: str = str(uuid.uuid4())
        timestamp: float = time.time() if ts is None else ts

        # Create a dictionary representing the event's core content for hashing.
        # The 'hash' field itself is excluded from this base for calculation.
        base_for_hash: Dict[str, Any] = {
            "event_id": event_id,
            "ts": timestamp,
            "node_id": node_id,
            "type": event_type,
            "parent_id": parent_id,
            "payload": payload,
        }
        event_hash: str = hashlib.sha256(_canonical_json(base_for_hash).encode("utf-8")).hexdigest()

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
        based on its content and comparing it to the stored `hash` field.
        This ensures the event data has not been tampered with since creation.

        Returns:
            True if the re-calculated hash matches the stored hash, False otherwise.
        """
        base_for_hash: Dict[str, Any] = {
            "event_id": self.event_id,
            "ts": self.ts,
            "node_id": self.node_id,
            "type": self.type,
            "parent_id": self.parent_id,
            "payload": self.payload,
        }
        expected_hash: str = hashlib.sha256(_canonical_json(base_for_hash).encode("utf-8")).hexdigest()
        return expected_hash == self.hash

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the Event instance into a dictionary representation.

        Returns:
            A dictionary containing all event attributes, suitable for
            serialization (e.g., to JSON).
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Event:
        """
        Creates an Event instance from a dictionary.
        This is typically used when deserializing an event from storage or a network.

        Args:
            data: A dictionary containing the event's data, conforming to the
                  Event's structure. Expected keys include "event_id", "ts",
                  "node_id", "type", "payload". "parent_id" and "hash" are optional.

        Returns:
            An Event instance populated with data from the dictionary.

        Raises:
            KeyError: If essential keys ("event_id", "ts", "node_id", "type")
                      are missing from the input `data`.
            TypeError, ValueError: If `ts` cannot be converted to float or other
                                   type mismatches occur.
        """
        return cls(
            event_id=data["event_id"],
            ts=float(data["ts"]),  # Explicitly convert to float for robustness
            node_id=data["node_id"],
            type=data["type"],
            payload=data.get("payload", {}),  # BUG FIX: changed `data["get"]` to `data.get`
            parent_id=data.get("parent_id"),  # Use .get() for optional fields
            hash=data.get("hash", ""),        # Use .get() for optional fields
        )
