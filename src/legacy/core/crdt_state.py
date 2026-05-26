"""Legacy Last-Write-Wins register CRDT for lightweight state replication.

Prefer ``src.core.crdt_layer.GenomeCRDT`` for production swarm state. This module
is intentionally small and remains useful for tests, local caches, and simple
key/value replication.
"""

from __future__ import annotations

import copy
import threading
import time
from typing import Any, Optional, TypedDict


class CRDTEntry(TypedDict):
    """Timestamped value stored in the LWW register."""

    value: Any
    timestamp: float


class CRDTState:
    """Thread-safe Last-Write-Wins key/value register."""

    __slots__ = ("node_id", "_state", "_lock")

    def __init__(self, node_id: str) -> None:
        clean_node_id = str(node_id or "").strip()
        if not clean_node_id:
            raise ValueError("node_id cannot be empty")

        self.node_id: str = clean_node_id
        self._state: dict[str, CRDTEntry] = {}
        self._lock = threading.RLock()

    def update(self, key: str, value: Any, *, timestamp: Optional[float] = None) -> None:
        """Update a key locally with the current time or an explicit timestamp."""
        clean_key = self._clean_key(key)
        ts = self._normalize_timestamp(timestamp if timestamp is not None else time.time())

        with self._lock:
            self._state[clean_key] = {
                "value": copy.deepcopy(value),
                "timestamp": ts,
            }

    def merge(self, remote_state: dict[str, CRDTEntry]) -> bool:
        """Merge remote entries using LWW timestamp resolution."""
        if not isinstance(remote_state, dict):
            return False

        changed = False

        with self._lock:
            for raw_key, raw_entry in remote_state.items():
                key = str(raw_key or "").strip()
                entry = self._normalize_entry(raw_entry)

                if not key or entry is None:
                    continue

                local_entry = self._state.get(key)
                if local_entry is None or entry["timestamp"] > local_entry["timestamp"]:
                    self._state[key] = entry
                    changed = True

        return changed

    def get(self, key: str, default: Any = None) -> Any:
        """Return a deep copy of the value for key, or default when absent."""
        clean_key = str(key or "").strip()
        if not clean_key:
            return default

        with self._lock:
            entry = self._state.get(clean_key)
            if entry is None:
                return default
            return copy.deepcopy(entry["value"])

    def contains(self, key: str) -> bool:
        """Return True when key exists in the local state."""
        clean_key = str(key or "").strip()
        if not clean_key:
            return False

        with self._lock:
            return clean_key in self._state

    def delete(self, key: str) -> bool:
        """Remove a key from the local state.

        This is a local deletion, not a CRDT tombstone. Use GenomeCRDT when
        delete propagation is required.
        """
        clean_key = str(key or "").strip()
        if not clean_key:
            return False

        with self._lock:
            return self._state.pop(clean_key, None) is not None

    def keys(self) -> list[str]:
        """Return a sorted list of local state keys."""
        with self._lock:
            return sorted(self._state.keys())

    def clear(self) -> None:
        """Clear all local state."""
        with self._lock:
            self._state.clear()

    def to_dict(self) -> dict[str, CRDTEntry]:
        """Return a deep copy of the full state."""
        with self._lock:
            return copy.deepcopy(self._state)

    @staticmethod
    def _clean_key(key: str) -> str:
        clean_key = str(key or "").strip()
        if not clean_key:
            raise ValueError("key cannot be empty")
        return clean_key

    @staticmethod
    def _normalize_timestamp(value: Any) -> float:
        try:
            ts = float(value)
        except (TypeError, ValueError):
            ts = time.time()

        if ts < 0:
            return 0.0
        return ts

    @classmethod
    def _normalize_entry(cls, entry: Any) -> Optional[CRDTEntry]:
        if not isinstance(entry, dict):
            return None
        if "value" not in entry or "timestamp" not in entry:
            return None

        return {
            "value": copy.deepcopy(entry["value"]),
            "timestamp": cls._normalize_timestamp(entry["timestamp"]),
        }