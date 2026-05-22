"""
Last-Write-Wins (LWW) Register CRDT implementation for distributed state replication.

This module provides a thread-safe LWW-Register structure. Conflicts are resolved
by selecting the value associated with the highest timestamp. 

NOTE: This is a legacy implementation. Please prefer GenomeCRDT systems for production.
"""
import threading
import time
from typing import Any, Dict, Optional, TypedDict

class CRDTEntry(TypedDict):
    """Structure representing a timestamped CRDT entry."""
    value: Any
    timestamp: float

class CRDTState:
    """
    Thread-safe Last-Write-Wins (LWW) Register CRDT.
    
    Attributes:
        node_id (str): Unique identifier for the local node.
    """

    def __init__(self, node_id: str) -> None:
        """Initializes the CRDT state store."""
        self.node_id: str = node_id
        self._state: Dict[str, CRDTEntry] = {}
        self._lock = threading.RLock()

    def update(self, key: str, value: Any) -> None:
        """
        Updates a key locally with the current system timestamp.

        Args:
            key: The state key to update.
            value: The data to store.
        """
        with self._lock:
            self._state[key] = {
                "value": value,
                "timestamp": time.time()
            }

    def merge(self, remote_state: Dict[str, CRDTEntry]) -> bool:
        """
        Merges remote state into local state using LWW resolution.

        Args:
            remote_state: Dictionary of entries to integrate.

        Returns:
            bool: True if the local state was modified.
        """
        changed = False
        with self._lock:
            for key, entry in remote_state.items():
                if not isinstance(entry, dict) or "value" not in entry or "timestamp" not in entry:
                    continue

                local_entry = self._state.get(key)
                if local_entry is None or entry["timestamp"] > local_entry["timestamp"]:
                    self._state[key] = entry
                    changed = True
        return changed

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieves the value for a given key.

        Args:
            key: The lookup key.

        Returns:
            The stored value if found, else None.
        """
        with self._lock:
            entry = self._state.get(key)
            return entry["value"] if entry is not None else None

    def to_dict(self) -> Dict[str, CRDTEntry]:
        """
        Returns a thread-safe shallow copy of the state.
        """
        with self._lock:
            return self._state.copy()