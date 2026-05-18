"""
LWW-Register CRDT для репликации состояния.
Каждый ключ хранит значение и timestamp.
При конфликте побеждает запись с наибольшим timestamp.
"""
import time
from typing import Any, Dict, Optional, Union

class CRDTState:
    """
    Implements a Last-Write-Wins (LWW) Register CRDT for state replication.
    Each key stores a value and a timestamp.
    In case of a conflict, the entry with the largest timestamp wins.
    """
    def __init__(self, node_id: str):
        """
        Initializes the CRDTState with a unique node identifier.

        Args:
            node_id: A unique identifier for this node.
        """
        self.node_id: str = node_id
        # State stores key -> {"value": Any, "timestamp": float}
        # The inner dictionary's value can be of any type, while the timestamp is a float.
        self.state: Dict[str, Dict[str, Union[Any, float]]] = {}

    def update(self, key: str, value: Any) -> None:
        """
        Locally updates a key with a new value and the current timestamp.
        Local updates always take precedence as their timestamp is guaranteed to be newer
        or equal to any previous local timestamp for the same key.

        Args:
            key: The key to update.
            value: The new value to associate with the key.
        """
        self.state[key] = {
            "value": value,
            "timestamp": time.time()
        }

    def merge(self, remote_state: Dict[str, Dict[str, Union[Any, float]]]) -> bool:
        """
        Merges the current state with a remote state.
        For each key present in both states, the entry with the higher timestamp wins.
        New keys from the remote state are added.

        Args:
            remote_state: The remote CRDT state (a dictionary) to merge with.
                          Expected format: {key: {"value": Any, "timestamp": float}}

        Returns:
            True if any changes were made to the local state as a result of the merge, False otherwise.
        """
        changed = False
        for key, remote_entry in remote_state.items():
            # If key is not in local state, add it directly
            if key not in self.state:
                self.state[key] = remote_entry
                changed = True
            # If key is in local state, compare timestamps and update if remote is newer
            elif remote_entry["timestamp"] > self.state[key]["timestamp"]:
                self.state[key] = remote_entry
                changed = True
        return changed

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieves the value associated with a key.

        Args:
            key: The key whose value is to be retrieved.

        Returns:
            The value associated with the key, or None if the key does not exist.
        """
        entry = self.state.get(key)
        return entry["value"] if entry else None

    def to_dict(self) -> Dict[str, Dict[str, Union[Any, float]]]:
        """
        Serializes the current state into a dictionary suitable for transmission over a network.

        Returns:
            A dictionary representing the current CRDT state.
        """
        return self.state
