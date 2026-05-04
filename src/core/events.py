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
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


@dataclass(frozen=True)
class Event:
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
    ) -> "Event":
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
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        return cls(
            event_id=data["event_id"],
            ts=float(data["ts"]),
            node_id=data["node_id"],
            type=data["type"],
            payload=data["payload"],
            parent_id=data.get("parent_id"),
            hash=data.get("hash", ""),
        )