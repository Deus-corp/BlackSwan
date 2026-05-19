# src/memory/local_memory.py
"""
Minimal LocalMemoryAPI implementation.
Provides layered memory (episodic, semantic, policy) and snapshot/restore functionality.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, Field, model_validator


# Define a protocol for the storage interface for better type hinting
@runtime_checkable
class StorageProtocol(Protocol):
    """
    Protocol defining the expected interface for a storage backend.
    """
    def save_snapshot(self, node_id: str, data: bytes) -> None:
        """Saves the given data bytes associated with a node_id."""
        ...

    def load_snapshot(self, node_id: str) -> Optional[bytes]:
        """Loads data bytes associated with a node_id, or None if not found."""
        ...


# ---------- Data Models ----------

class MemoryRecord(BaseModel):
    """
    Represents a single atomic piece of information stored in memory.
    """
    id: str = Field(default_factory=lambda: uuid.uuid4().hex, description="Unique identifier for the memory record.")
    kind: str = Field(description='Type of the record, e.g., "event", "fact", "summary", "policy", "decision", "alert".')
    scope: str = Field("local", description='Scope of the record, e.g., "local", "swarm", "topic".')
    topic: Optional[str] = Field(default=None, description="Optional topic or category for the record.")
    payload: Any = Field(default=None, description="The actual content or data of the record. Can be any serializable type.")
    payload_hash: str = Field(default="", description="SHA256 hash of the payload for content-addressing and integrity checks.")
    source: Dict[str, Any] = Field(
        default_factory=lambda: {"originNodeId": "", "originPeerId": "", "parents": []},
        description="Metadata about the source of the record, including origin node/peer IDs and parent record IDs."
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score (0.0 to 1.0) in the accuracy or reliability of the record.")
    priority: int = Field(default=0, ge=0, le=100, description="Priority level (0 to 100) for processing or retention.")
    ttl_ms: Optional[int] = Field(default=None, description="Time-to-live in milliseconds, after which the record may be considered stale.")
    valid_until: Optional[int] = Field(default=None, description="Unix timestamp (ms) when the record becomes invalid.")
    created_at: int = Field(default_factory=lambda: int(time.time() * 1000), description="Unix timestamp (ms) of record creation.")
    updated_at: int = Field(default_factory=lambda: int(time.time() * 1000), description="Unix timestamp (ms) of last record update.")
    version: int = Field(default=1, description="Version of the record schema.")
    signature: Optional[str] = Field(default=None, description="Cryptographic signature for integrity and authenticity.")
    verified: bool = Field(default=False, description="Indicates if the record's signature has been verified.")

    @model_validator(mode='after')
    def compute_payload_hash(self) -> 'MemoryRecord':
        """
        Computes the payload_hash if not already set and payload is not None.
        Uses `json.dumps` for deterministic hashing of complex payloads by sorting keys.
        """
        if not self.payload_hash and self.payload is not None:
            # Ensure deterministic JSON serialization for consistent hashing
            self.payload_hash = hashlib.sha256(
                json.dumps(self.payload, sort_keys=True, ensure_ascii=False).encode('utf-8')
            ).hexdigest()
        return self


class FactStoreItem(BaseModel):
    """
    Represents a structured fact, typically a subject-predicate-object triplet,
    stored in the semantic memory layer.
    """
    fact_id: str = Field(default_factory=lambda: uuid.uuid4().hex, description="Unique identifier for the fact.")
    subject: str = Field(description="The subject of the fact.")
    predicate: str = Field(description="The predicate describing the relationship or attribute.")
    object: str = Field(description="The object of the fact.")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score (0.0 to 1.0) in this fact.")
    source_refs: List[str] = Field(default_factory=list, description="List of IDs of MemoryRecords that generated or support this fact.")


class EpisodeEvent(BaseModel):
    """
    Represents an event in an episodic memory, often derived from a MemoryRecord.
    """
    event_id: str = Field(description="Identifier for the event, often matching a MemoryRecord ID.")
    kind: str = Field(description="Type or category of the event.")
    message: str = Field(description="A summarized message or description of the event.")
    ts: int = Field(default_factory=lambda: int(time.time() * 1000), description="Unix timestamp (ms) when the event occurred.")
    refs: List[str] = Field(default_factory=list, description="List of IDs of related MemoryRecords or other entities.")


class PolicyRule(BaseModel):
    """
    Represents an active policy or rule governing system behavior.
    """
    rule_id: str = Field(default_factory=lambda: uuid.uuid4().hex, description="Unique identifier for the policy rule.")
    name: str = Field(description="A human-readable name for the policy.")
    description: str = Field(default="", description="Detailed description of what the policy does.")
    enabled: bool = Field(default=True, description="Whether the policy is currently active.")
    priority: int = Field(default=0, ge=0, le=100, description="Priority level (0 to 100) for policy evaluation.")
    conditions: Dict[str, Any] = Field(default_factory=dict, description="A dictionary of conditions that trigger the policy.")
    actions: List[str] = Field(default_factory=list, description="A list of actions to be taken when the policy conditions are met.")
    version: int = Field(default=1, description="Version of the policy rule schema.")


class MemorySnapshot(BaseModel):
    """
    Metadata for a memory snapshot, allowing for rollback points or transfer.
    """
    snapshot_id: str = Field(description="Unique identifier for this snapshot.")
    node_id: str = Field(description="Identifier of the node that created this snapshot.")
    created_at: int = Field(description="Unix timestamp (ms) when the snapshot was created.")
    semantic_hash: str = Field(default="", description="SHA256 hash of the semantic memory state at the time of snapshot.")
    episodic_hash: str = Field(default="", description="SHA256 hash of the episodic memory state at the time of snapshot.")
    policy_hash: str = Field(default="", description="SHA256 hash of the policy memory state at the time of snapshot.")
    record_count: int = Field(default=0, description="Number of MemoryRecords included in the state this snapshot represents.")
    signature: str = Field(default="", description="Digital signature of the snapshot metadata for authenticity.")


# ---------- Memory Implementation ----------

class LocalMemoryAPI:
    """
    Provides a local, layered memory implementation for an agent or node.
    Supports episodic, semantic, and policy memory layers, as well as snapshot/restore.
    """
    # Type hints for instance attributes, initialized in __init__.
    _records: Dict[str, MemoryRecord]
    _episodic: List[EpisodeEvent]
    _semantic: Dict[str, FactStoreItem]
    _policies: Dict[str, PolicyRule]
    _snapshots: List[MemorySnapshot]

    def __init__(self, node_id: str = "unknown", storage: Optional[StorageProtocol] = None):
        """
        Initializes the LocalMemoryAPI.

        Args:
            node_id: The identifier for the node owning this memory.
            storage: An optional object conforming to StorageProtocol for persistence.
        """
        self.node_id: str = node_id
        self.storage: Optional[StorageProtocol] = storage
        
        # Initialize internal memory stores
        self._records = {}
        self._episodic = []
        self._semantic = {}
        self._policies = {}
        self._snapshots = []

    # ---------- WRITE METHODS ----------

    async def remember(self, record: MemoryRecord) -> str:
        """
        Stores a MemoryRecord in the main record store and potentially
        categorizes it into specialized memory layers.

        If `record.id` is not provided during instantiation, a UUID is generated
        by the Pydantic model's default_factory.
        `record.updated_at` is always updated upon storage.
        `record.payload_hash` is computed by the Pydantic model's validator if not already set.

        Args:
            record: The MemoryRecord to store.

        Returns:
            The ID of the stored record.
        """
        record.updated_at = int(time.time() * 1000)
        self._records[record.id] = record

        # Automatic classification to episodic memory
        if record.kind == "event":
            # Check if an event with this record.id already exists to prevent duplicates.
            # This is an O(N) check for `_episodic`, which is a list. For very large
            # episodic memory, consider making `_episodic` a `Dict[str, EpisodeEvent]`
            # for O(1) lookups and upserts, similar to `_semantic` and `_policies`.
            if not any(e.event_id == record.id for e in self._episodic):
                self._episodic.append(EpisodeEvent(
                    event_id=record.id,
                    kind=record.kind,
                    message=str(record.payload), # `str()` provides a basic summary for display
                    refs=record.source.get("parents", [])
                ))
        return record.id

    async def upsert_fact(self, fact: FactStoreItem) -> None:
        """
        Adds or updates a structured fact in the semantic memory.
        Uses `fact.fact_id` as the key for O(1) upsert.

        Args:
            fact: The FactStoreItem to add or update.
        """
        self._semantic[fact.fact_id] = fact

    async def store_policy(self, rule: PolicyRule) -> None:
        """
        Adds or updates a policy rule in the policy memory.
        Uses `rule.rule_id` as the key for O(1) upsert.

        Args:
            rule: The PolicyRule to add or update.
        """
        self._policies[rule.rule_id] = rule

    # ---------- READ METHODS ----------

    async def get_by_id(self, record_id: str) -> Optional[MemoryRecord]:
        """
        Retrieves a MemoryRecord by its ID.

        Args:
            record_id: The ID of the record to retrieve.

        Returns:
            The MemoryRecord if found, otherwise None.
        """
        return self._records.get(record_id)

    async def query(self, kind: Optional[str] = None, scope: Optional[str] = None,
                    min_confidence: float = 0.0) -> List[MemoryRecord]:
        """
        Queries the main record store based on kind, scope, and minimum confidence.

        Args:
            kind: Optional filter for the 'kind' of record (e.g., "event", "fact").
            scope: Optional filter for the 'scope' of the record (e.g., "local", "swarm").
            min_confidence: Minimum confidence level (0.0 to 1.0) for records to be included.

        Returns:
            A list of matching MemoryRecord objects.
        """
        results: List[MemoryRecord] = []
        for rec in self._records.values():
            if kind is not None and rec.kind != kind:
                continue
            if scope is not None and rec.scope != scope:
                continue
            if rec.confidence < min_confidence:
                continue
            results.append(rec)
        return results

    async def recent(self, kind: Optional[str] = None, limit: int = 50) -> List[MemoryRecord]:
        """
        Retrieves a list of the most recently created MemoryRecords,
        optionally filtered by kind.

        Args:
            kind: Optional filter for the 'kind' of record.
            limit: The maximum number of records to return.

        Returns:
            A list of the most recent MemoryRecord objects, sorted by creation time (descending).
        """
        # Sorting by creation time in descending order
        sorted_recs: List[MemoryRecord] = sorted(self._records.values(), key=lambda r: r.created_at, reverse=True)
        if kind:
            sorted_recs = [r for r in sorted_recs if r.kind == kind]
        return sorted_recs[:limit]
    
    async def get_all_facts(self) -> List[FactStoreItem]:
        """
        Retrieves all stored facts from the semantic memory.
        """
        return list(self._semantic.values())

    async def get_all_policies(self) -> List[PolicyRule]:
        """
        Retrieves all stored policy rules from the policy memory.
        """
        return list(self._policies.values())

    async def get_all_episodic_events(self) -> List[EpisodeEvent]:
        """
        Retrieves all stored episodic events.
        """
        return self._episodic

    async def save_to_db(self) -> None:
        """
        Saves the entire current memory state to the configured storage backend.
        The memory state includes all records, episodic events, semantic facts,
        policy rules, and snapshot metadata.

        If no storage backend is configured, a warning is printed.
        Errors during serialization or storage are caught and printed.
        """
        if not self.storage:
            print("WARNING: No storage backend configured, cannot save memory state.")
            # Consider using a proper logging system (e.g., `import logging; logging.warning(...)`)
            return
        
        data: Dict[str, Any] = {
            'node_id': self.node_id,
            'records': [r.model_dump() for r in self._records.values()],
            'episodic': [e.model_dump() for e in self._episodic],
            'semantic': [s.model_dump() for s in self._semantic.values()],
            'policies': [p.model_dump() for p in self._policies.values()],
            'snapshots': [s.model_dump() for s in self._snapshots],
            'updated_at': int(time.time() * 1000)
        }
        try:
            # Using indent for readability in storage; remove for efficiency in production.
            # `ensure_ascii=False` for proper handling of non-ASCII characters.
            self.storage.save_snapshot(self.node_id, json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8'))
            # logging.debug(f"Memory state for node {self.node_id} saved to storage.")
        except Exception as e:
            print(f"ERROR: Failed to save memory state to storage for node {self.node_id}: {e}")
            # logging.exception(f"Failed to save memory state for node {self.node_id}.")

    async def load_from_db(self) -> None:
        """
        Loads the memory state from the configured storage backend.
        This method is typically called during initialization to restore a previous state.

        If no storage backend is configured, a warning is printed.
        If no snapshot data is found, an info message is printed.
        Errors during deserialization or loading are caught and printed.
        """
        if not self.storage:
            print("WARNING: No storage backend configured, cannot load memory state.")
            # logging.warning(...)
            return
        
        raw_data: Optional[bytes] = self.storage.load_snapshot(self.node_id)
        if not raw_data:
            # logging.info(f"No previous memory state found for node {self.node_id}.")
            return
        
        try:
            data: Dict[str, Any] = json.loads(raw_data.decode('utf-8'))
            self._records = {r['id']: MemoryRecord(**r) for r in data.get('records', [])}
            self._episodic = [EpisodeEvent(**e) for e in data.get('episodic', [])]
            # When loading semantic and policies, convert lists of dicts back to dicts, keyed by their respective IDs.
            self._semantic = {f['fact_id']: FactStoreItem(**f) for f in data.get('semantic', []) if 'fact_id' in f}
            self._policies = {p['rule_id']: PolicyRule(**p) for p in data.get('policies', []) if 'rule_id' in p}
            self._snapshots = [MemorySnapshot(**s) for s in data.get('snapshots', [])]
            # logging.info(f"Memory state for node {self.node_id} loaded from storage.")
        except json.JSONDecodeError as e:
            print(f"ERROR: Failed to decode memory snapshot JSON for node {self.node_id}: {e}")
            # logging.error(f"Failed to decode memory snapshot JSON for node {self.node_id}.", exc_info=True)
        except Exception as e:
            print(f"ERROR: Failed to load memory state for node {self.node_id}: {e}")
            # logging.error(f"Failed to load memory state for node {self.node_id}.", exc_info=True)


    # ---------- SNAPSHOT / RESTORE ----------

    async def snapshot(self) -> MemorySnapshot:
        """
        Creates a metadata snapshot of the current memory state.
        This captures the counts and content hashes of various memory layers.
        Note: This only stores metadata about the snapshot, not the full memory content itself.
        The full content for restoration from a snapshot needs to be managed externally
        (e.g., by combining with `save_to_db`/`load_from_db`).

        The hashes are computed deterministically by sorting elements before JSON serialization
        to ensure consistency across different runs or environments.

        Returns:
            A MemorySnapshot object representing the current state.
        """
        # Ensure consistent order for hashing by sorting values before dumping.
        # `ensure_ascii=False` is used to allow non-ASCII characters and be consistent with saving.
        semantic_data: bytes = json.dumps(
            sorted([f.model_dump() for f in self._semantic.values()], key=lambda x: x['fact_id']),
            sort_keys=True, ensure_ascii=False
        ).encode('utf-8')
        episodic_data: bytes = json.dumps(
            sorted([e.model_dump() for e in self._episodic], key=lambda x: x['event_id']),
            sort_keys=True, ensure_ascii=False
        ).encode('utf-8')
        policy_data: bytes = json.dumps(
            sorted([p.model_dump() for p in self._policies.values()], key=lambda x: x['rule_id']),
            sort_keys=True, ensure_ascii=False
        ).encode('utf-8')

        snapshot = MemorySnapshot(
            snapshot_id=uuid.uuid4().hex, # Use UUID for uniqueness
            node_id=self.node_id,
            created_at=int(time.time() * 1000),
            record_count=len(self._records),
            semantic_hash=hashlib.sha256(semantic_data).hexdigest(),
            episodic_hash=hashlib.sha256(episodic_data).hexdigest(),
            policy_hash=hashlib.sha256(policy_data).hexdigest(),
        )
        self._snapshots.append(snapshot)
        return snapshot

    async def restore(self, snapshot: MemorySnapshot, records: List[MemoryRecord]) -> None:
        """
        Restores the core MemoryRecord store from a provided list of records.
        This method assumes `records` contains the desired state.

        Auxiliary memory layers (`_episodic`, `_semantic`, `_policies`) are cleared
        and then `_episodic` is reconstructed from the provided `records` where possible.
        `_semantic` and `_policies` are *not* directly reconstructed from generic `MemoryRecord`
        payloads by this method, as their full state is not reliably derivable without
        explicit payload structure. For a full state restore including all layers,
        `load_from_db` should be used, which relies on a complete serialized memory dump.

        Args:
            snapshot: The MemorySnapshot metadata. Currently used for context/metadata,
                      not as the direct source for memory content.
            records: The list of MemoryRecord objects to restore into the main store.
        """
        # Clear all existing memory layers to prepare for a clean restoration
        self._records.clear()
        self._episodic.clear()
        self._semantic.clear()
        self._policies.clear()
        self._snapshots.clear() # Clear existing snapshot metadata as they refer to a prior state

        # Restore main records and reconstruct episodic layer from them
        for rec in records:
            self._records[rec.id] = rec
            # Reconstruct episodic events if the record's kind is "event"
            if rec.kind == "event":
                self._episodic.append(EpisodeEvent(
                    event_id=rec.id,
                    kind=rec.kind,
                    message=str(rec.payload), # A basic string representation of the payload
                    refs=rec.source.get("parents", [])
                ))
        
        # Semantic and policy memories are not reconstructed here.
        # If the MemoryRecord payloads themselves were guaranteed to be `FactStoreItem`
        # or `PolicyRule` dictionaries, a reconstruction logic could be added.
        # However, `MemoryRecord.payload` is `Any`, so direct reconstruction is not safe.

    async def forget(self, kind: Optional[str] = None, older_than_ms: Optional[int] = None) -> int:
        """
        Deletes MemoryRecords based on specified criteria.
        Records are deleted if they match the `kind` (if specified)
        AND were created *before* the `older_than_ms` timestamp (if specified).

        Args:
            kind: Optional filter to delete records of a specific kind.
            older_than_ms: Optional Unix timestamp (in milliseconds). Records
                           with `created_at` timestamp strictly less than
                           `older_than_ms` will be deleted.

        Returns:
            The number of records deleted.
        """
        to_delete_ids: List[str] = []
        for rid, rec in self._records.items():
            if kind is not None and rec.kind != kind:
                continue # Skip if kind filter does not match
            if older_than_ms is not None and rec.created_at >= older_than_ms: 
                continue # Skip if record is newer than or exactly at the `older_than_ms` threshold
            
            # If we reach here, the record matches all criteria for deletion
            to_delete_ids.append(rid)
        
        for rid in to_delete_ids:
            del self._records[rid]
            # Also remove associated entries from auxiliary layers that are directly
            # keyed by the MemoryRecord's ID (like episodic events).
            # This list comprehension is an O(N) operation on `_episodic`.
            self._episodic = [e for e in self._episodic if e.event_id != rid]
            
            # Note: Removal from `_semantic` and `_policies` is not directly handled here,
            # as these layers are keyed by their own unique IDs (`fact_id`, `rule_id`)
            # and may not be directly tied to a single `MemoryRecord.id`.
            # A more sophisticated garbage collection or explicit linkage mechanism
            # would be needed if direct cascade deletion across all layers is required.
        
        return len(to_delete_ids)

    async def clear_all_memory(self) -> None:
        """
        Clears all memory layers entirely, including records, episodic events,
        semantic facts, policy rules, and snapshot metadata.
        """
        self._records.clear()
        self._episodic.clear()
        self._semantic.clear()
        self._policies.clear()
        self._snapshots.clear()

    # ---------- UTILS ----------
    async def compress(self) -> Dict[str, Any]:
        """
        Provides metrics about the current memory state.
        This is a placeholder for a more complex compression or summarization logic.

        Returns:
            A dictionary containing various memory usage statistics.
        """
        return {
            "total_records": len(self._records),
            "episodic_count": len(self._episodic),
            "semantic_count": len(self._semantic),
            "policy_count": len(self._policies),
            "snapshot_count": len(self._snapshots),
            "memory_usage_bytes": 0 # Placeholder for actual memory usage calculation if needed
        }

    async def seal(self) -> None:
        """
        Placeholder method for 'sealing' the memory, typically for audit or immutability purposes.
        Current implementation does nothing.
        """
        pass