# src/memory/local_memory.py
"""
Minimal LocalMemoryAPI implementation.
Provides layered memory (episodic, semantic, policy) and snapshot/restore.
"""
import time
import json
import hashlib
import uuid # For more robust ID generation
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from pydantic import BaseModel, Field, model_validator, PrivateAttr # model_validator for pydantic v2

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
    id: str = Field(default_factory=lambda: uuid.uuid4().hex) # Default to UUID if not provided
    kind: str  # e.g., "event", "fact", "summary", "policy", "decision", "alert"
    scope: str = "local"   # e.g., "local", "swarm", "topic"
    topic: Optional[str] = None
    payload: Any = None
    payload_hash: str = "" # Hash of the payload for content-addressing
    source: Dict[str, Any] = Field(default_factory=lambda: {"originNodeId": "", "originPeerId": "", "parents": []})
    confidence: float = Field(default=1.0, ge=0.0, le=1.0) # 0..1
    priority: int = Field(default=0, ge=0, le=100)            # 0..100
    ttl_ms: Optional[int] = None # Time-to-live in milliseconds
    valid_until: Optional[int] = None # Unix timestamp (ms) when record becomes invalid
    created_at: int = Field(default_factory=lambda: int(time.time() * 1000))
    updated_at: int = Field(default_factory=lambda: int(time.time() * 1000))
    version: int = 1
    signature: Optional[str] = None
    verified: bool = False

    @model_validator(mode='after')
    def compute_payload_hash(self) -> 'MemoryRecord':
        """
        Computes the payload_hash if not already set and payload is not None.
        Uses json.dumps for deterministic hashing of complex payloads.
        """
        if not self.payload_hash and self.payload is not None:
            self.payload_hash = hashlib.sha256(
                json.dumps(self.payload, sort_keys=True).encode('utf-8')
            ).hexdigest()
        return self

class FactStoreItem(BaseModel):
    """
    Represents a structured fact, typically a subject-predicate-object triplet.
    """
    fact_id: str = Field(default_factory=lambda: uuid.uuid4().hex) # Ensure unique ID
    subject: str
    predicate: str
    object: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_refs: List[str] = Field(default_factory=list) # IDs of MemoryRecords that generated this fact

class EpisodeEvent(BaseModel):
    """
    Represents an event in an episodic memory, often derived from a MemoryRecord.
    """
    event_id: str
    kind: str
    message: str # A summarized message of the event
    ts: int = Field(default_factory=lambda: int(time.time() * 1000))
    refs: List[str] = Field(default_factory=list) # IDs of related MemoryRecords

class PolicyRule(BaseModel):
    """
    Represents an active policy or rule governing system behavior.
    """
    rule_id: str = Field(default_factory=lambda: uuid.uuid4().hex) # Ensure unique ID
    name: str
    description: str = ""
    enabled: bool = True
    priority: int = Field(default=0, ge=0, le=100)
    conditions: Dict[str, Any] = Field(default_factory=dict)
    actions: List[str] = Field(default_factory=list)
    version: int = 1

class MemorySnapshot(BaseModel):
    """
    Metadata for a memory snapshot, allowing for rollback points or transfer.
    """
    snapshot_id: str
    node_id: str
    created_at: int
    semantic_hash: str = "" # Hash of semantic memory state
    episodic_hash: str = "" # Hash of episodic memory state
    policy_hash: str = ""   # Hash of policy memory state
    record_count: int = 0
    signature: str = ""     # Digital signature of the snapshot metadata

# ---------- Memory Implementation ----------

class LocalMemoryAPI:
    """
    Provides a local, layered memory implementation for an agent or node.
    Supports episodic, semantic, and policy memory layers, as well as snapshot/restore.
    """
    # Using PrivateAttr for internal attributes to clearly distinguish them
    # from potential Pydantic model fields, although this class is not a Pydantic model itself.
    # It serves as documentation and a reminder of Pydantic patterns.
    _records: Dict[str, MemoryRecord] = PrivateAttr(default_factory=dict)
    _episodic: List[EpisodeEvent] = PrivateAttr(default_factory=list)
    _semantic: Dict[str, FactStoreItem] = PrivateAttr(default_factory=dict) # Changed to Dict for O(1) upsert
    _policies: Dict[str, PolicyRule] = PrivateAttr(default_factory=dict)     # Changed to Dict for O(1) upsert
    _snapshots: List[MemorySnapshot] = PrivateAttr(default_factory=list)

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

        If `record.id` is not provided during instantiation, a UUID is generated.
        `record.updated_at` is always updated.
        `record.payload_hash` is computed if not already set (via Pydantic model_validator).

        Args:
            record: The MemoryRecord to store.

        Returns:
            The ID of the stored record.
        """
        record.updated_at = int(time.time() * 1000)
        self._records[record.id] = record

        # Automatic classification to episodic memory
        if record.kind == "event":
            # Check if an event with this record.id already exists to prevent duplicates
            if not any(e.event_id == record.id for e in self._episodic):
                self._episodic.append(EpisodeEvent(
                    event_id=record.id,
                    kind=record.kind,
                    message=str(record.payload), # `str()` provides a basic summary
                    refs=record.source.get("parents", [])
                ))
        return record.id

    async def upsert_fact(self, fact: FactStoreItem) -> None:
        """
        Adds or updates a structured fact in the semantic memory.
        Uses `fact_id` as the key for O(1) upsert.

        Args:
            fact: The FactStoreItem to add or update.
        """
        self._semantic[fact.fact_id] = fact

    async def store_policy(self, rule: PolicyRule) -> None:
        """
        Adds or updates a policy rule in the policy memory.
        Uses `rule_id` as the key for O(1) upsert.

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
        sorted_recs = sorted(self._records.values(), key=lambda r: r.created_at, reverse=True)
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
        """
        if not self.storage:
            print("WARNING: No storage backend configured, cannot save memory state.")
            return
        
        data = {
            'node_id': self.node_id,
            'records': [r.model_dump() for r in self._records.values()],
            'episodic': [e.model_dump() for e in self._episodic],
            'semantic': [s.model_dump() for s in self._semantic.values()],
            'policies': [p.model_dump() for p in self._policies.values()],
            'snapshots': [s.model_dump() for s in self._snapshots],
            'updated_at': int(time.time() * 1000)
        }
        try:
            # Using indent for readability in storage, can be removed for efficiency
            self.storage.save_snapshot(self.node_id, json.dumps(data, indent=2).encode('utf-8'))
            # Consider adding a logger here instead of print
            # logger.debug(f"Memory state for node {self.node_id} saved to storage.")
        except Exception as e:
            print(f"ERROR: Failed to save memory state to storage for node {self.node_id}: {e}")

    async def load_from_db(self) -> None:
        """
        Loads the memory state from the configured storage backend.
        This method is typically called during initialization.
        """
        if not self.storage:
            print("WARNING: No storage backend configured, cannot load memory state.")
            return
        raw_data = self.storage.load_snapshot(self.node_id)
        if not raw_data:
            # Consider adding a logger here instead of print
            # logger.info(f"No previous memory state found for node {self.node_id}.")
            return
        try:
            data = json.loads(raw_data.decode('utf-8'))
            self._records = {r['id']: MemoryRecord(**r) for r in data.get('records', [])}
            self._episodic = [EpisodeEvent(**e) for e in data.get('episodic', [])]
            # When loading semantic and policies, convert lists back to dicts
            self._semantic = {f['fact_id']: FactStoreItem(**f) for f in data.get('semantic', []) if 'fact_id' in f}
            self._policies = {p['rule_id']: PolicyRule(**p) for p in data.get('policies', []) if 'rule_id' in p}
            self._snapshots = [MemorySnapshot(**s) for s in data.get('snapshots', [])]
            # logger.info(f"Memory state for node {self.node_id} loaded from storage.")
        except json.JSONDecodeError as e:
            print(f"ERROR: Failed to decode memory snapshot JSON for node {self.node_id}: {e}")
        except Exception as e:
            print(f"ERROR: Failed to load memory state for node {self.node_id}: {e}")


    # ---------- SNAPSHOT / RESTORE ----------

    async def snapshot(self) -> MemorySnapshot:
        """
        Creates a metadata snapshot of the current memory state.
        This captures the counts and content hashes of various memory layers.
        Note: This only stores metadata about the snapshot, not the full memory content itself.
        The full content for restoration from a snapshot needs to be managed externally
        (e.g., by combining with `save_to_db`/`load_from_db`).

        Returns:
            A MemorySnapshot object representing the current state.
        """
        # Ensure consistent order for hashing by sorting values before dumping
        # This makes hashes deterministic given the same content
        semantic_data = json.dumps(sorted([f.model_dump() for f in self._semantic.values()], key=lambda x: x['fact_id']), sort_keys=True).encode('utf-8')
        episodic_data = json.dumps(sorted([e.model_dump() for e in self._episodic], key=lambda x: x['event_id']), sort_keys=True).encode('utf-8')
        policy_data = json.dumps(sorted([p.model_dump() for p in self._policies.values()], key=lambda x: x['rule_id']), sort_keys=True).encode('utf-8')

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
        Auxiliary memory layers (_episodic, _semantic, _policies) are cleared
        and then reconstructed from the provided `records` where possible,
        or left empty if reliable reconstruction from `MemoryRecord.payload` is not guaranteed.

        Args:
            snapshot: The MemorySnapshot metadata (currently used for context, not data source).
            records: The list of MemoryRecord objects to restore into the main store.
        """
        # Clear all existing memory to prepare for restoration
        self._records.clear()
        self._episodic.clear()
        self._semantic.clear()
        self._policies.clear()

        # Restore main records and reconstruct auxiliary layers if possible
        for rec in records:
            self._records[rec.id] = rec
            # Reconstruct episodic events
            if rec.kind == "event":
                self._episodic.append(EpisodeEvent(
                    event_id=rec.id,
                    kind=rec.kind,
                    message=str(rec.payload),
                    refs=rec.source.get("parents", [])
                ))
            # Note: Reconstructing _semantic (FactStoreItem) and _policies (PolicyRule) reliably
            # from raw MemoryRecords without explicit payload structure (e.g., payload *is* a FactStoreItem dict)
            # is not safely possible within this general `restore` method.
            # If a full state restore from a snapshot is desired, `load_from_db` should be used,
            # which relies on the complete serialized state saved by `save_to_db`.
            # This 'restore' method specifically focuses on the `_records` layer and its direct derivatives.

        # The `snapshot` object passed here contains hashes, but the actual data for semantic/policy
        # layers is not directly passed.

    async def forget(self, kind: Optional[str] = None, older_than_ms: Optional[int] = None) -> int:
        """
        Deletes MemoryRecords based on specified criteria.

        Args:
            kind: Optional filter to delete records of a specific kind.
            older_than_ms: Optional timestamp (in milliseconds) before which
                           records should be deleted (i.e., created_at < older_than_ms).

        Returns:
            The number of records deleted.
        """
        to_delete_ids: List[str] = []
        for rid, rec in self._records.items():
            if kind is not None and rec.kind != kind:
                continue
            # Fix: Condition for "older_than_ms" should be `rec.created_at < older_than_ms`
            if older_than_ms is not None and rec.created_at >= older_than_ms: 
                # Keep records that are newer or exactly at the threshold
                continue
            to_delete_ids.append(rid)
        
        for rid in to_delete_ids:
            del self._records[rid]
            # Also remove from auxiliary layers if they were directly derived by record.id
            self._episodic = [e for e in self._episodic if e.event_id != rid]
            # Note: Removal from _semantic and _policies is not directly managed here,
            # as these layers are keyed by their own IDs (fact_id, rule_id)
            # and may or may not be directly tied to a single MemoryRecord ID.
            # A more sophisticated garbage collection or explicit linkage would be needed.
        
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
            "snapshot_count": len(self._snapshots)
        }

    async def seal(self) -> None:
        """
        Placeholder method for 'sealing' the memory, typically for audit or immutability.
        Current implementation does nothing.
        """
        pass