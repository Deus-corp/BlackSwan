from __future__ import annotations # For forward references in type hints (e.g., CRDTStorage)

"""
Operation-based CRDT for genome records.

This module implements a CRDT (Conflict-free Replicated Data Type) based on operations
to manage genome records. It is designed to ensure deterministic Last-Write-Wins (LWW)
at the field/entity level, utilizing operation logs, Lamport clocks, and SQLite-based persistence.
"""

import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Union, Literal, Final

logger = logging.getLogger(__name__)

# =========================
# DATA MODEL
# =========================

# Define allowed operation kinds as constants and Literal for type safety
OPERATION_KIND_UPSERT: Final = "upsert"
OPERATION_KIND_DELETE: Final = "delete"
CRDTOperationKind = Literal[OPERATION_KIND_UPSERT, OPERATION_KIND_DELETE]


@dataclass(frozen=True, slots=True)
class CRDTOperation:
    """
    Represents a single CRDT operation (upsert or delete) on a genome record.
    Operations are immutable and used for replication and conflict resolution.

    Attributes:
        op_id (str): A unique identifier for the operation.
        node_id (str): The identifier of the node that created the operation.
        clock (int): The Lamport clock value of the node at the time of operation creation.
        kind (CRDTOperationKind): The type of operation: "upsert" (insert/update) or "delete" (deletion).
        gid (str): The globally unique identifier of the genome record this operation acts upon.
        payload (Dict[str, Any]): The data payload of the operation (empty for "delete").
        ts (float): The Unix timestamp when the operation was created.
    """
    op_id: str
    node_id: str
    clock: int
    kind: CRDTOperationKind
    gid: str
    payload: Dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the CRDTOperation instance to a dictionary.

        Returns:
            Dict[str, Any]: A dictionary representation of the operation.
        """
        return {
            "op_id": self.op_id,
            "node_id": self.node_id,
            "clock": self.clock,
            "kind": self.kind,
            "gid": self.gid,
            "payload": self.payload,
            "ts": self.ts,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> CRDTOperation:
        """
        Creates a CRDTOperation instance from a dictionary.

        Args:
            data (Dict[str, Any]): A dictionary containing the operation data.

        Returns:
            CRDTOperation: The created CRDTOperation instance.

        Raises:
            ValueError: If a required field is missing or has an incorrect type/value.
        """
        required_fields = ["op_id", "node_id", "clock", "kind", "gid"]
        for field_name in required_fields:
            if field_name not in data:
                raise ValueError(f"Missing required field '{field_name}' in CRDTOperation data.")
        
        kind_value = str(data["kind"])
        if kind_value not in (OPERATION_KIND_UPSERT, OPERATION_KIND_DELETE):
            raise ValueError(f"Invalid operation kind '{kind_value}'. Must be '{OPERATION_KIND_UPSERT}' or '{OPERATION_KIND_DELETE}'.")

        try:
            return CRDTOperation(
                op_id=str(data["op_id"]),
                node_id=str(data["node_id"]),
                clock=int(data["clock"]),
                kind=kind_value, # type: ignore # Validated against Literal, safe to assign
                gid=str(data["gid"]),
                payload=dict(data.get("payload", {})),
                ts=float(data.get("ts", time.time())),
            )
        except (TypeError, ValueError) as e:
            # Re-raise with more context if type conversion fails
            raise ValueError(f"Type conversion error when creating CRDTOperation from dict: {e}. Data: {data}") from e


@dataclass(slots=True)
class VersionVector:
    """
    A Version Vector tracks the highest clock value observed from each node.
    It is used to determine causal order and identify missing operations
    during synchronization.

    Attributes:
        clocks (Dict[str, int]): A dictionary mapping node IDs to their highest observed Lamport clock values.
    """
    clocks: Dict[str, int] = field(default_factory=dict)

    def bump(self, node_id: str) -> int:
        """
        Increments the clock for a given node and returns the new clock value.

        Args:
            node_id (str): The identifier of the node whose clock to increment.

        Returns:
            int: The new clock value for the node.
        """
        self.clocks[node_id] = self.clocks.get(node_id, 0) + 1
        return self.clocks[node_id]

    def observe(self, node_id: str, clock: int) -> None:
        """
        Updates the clock for a given node if the new clock value is higher than the current one.
        Ensures `node_id` is a string and `clock` is an integer.

        Args:
            node_id (str): The identifier of the node.
            clock (int): The clock value to observe.
        """
        try:
            self.clocks[str(node_id)] = max(self.clocks.get(str(node_id), 0), int(clock))
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to observe clock for node '{node_id}' with clock '{clock}': {e}. Skipping update.")

    def seen(self, node_id: str, clock: int) -> bool:
        """
        Checks if a specific clock value for a node has been observed.
        Ensures `node_id` is a string and `clock` is an integer for comparison.

        Args:
            node_id (str): The identifier of the node.
            clock (int): The clock value to check.

        Returns:
            bool: True if the clock value has been observed (i.e., current clock >= `clock`),
                  False otherwise.
        """
        try:
            return self.clocks.get(str(node_id), 0) >= int(clock)
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to check seen status for node '{node_id}' with clock '{clock}': {e}. Returning False.")
            return False

    def merge(self, other: VersionVector) -> None:
        """
        Merges another VersionVector into this one, updating clocks to their maximum values.

        Args:
            other (VersionVector): The other VersionVector to merge.
        """
        for node_id, clock in other.clocks.items():
            self.observe(node_id, clock)

    def to_dict(self) -> Dict[str, int]:
        """
        Converts the VersionVector to a dictionary.

        Returns:
            Dict[str, int]: A dictionary representation of the version vector.
        """
        return dict(self.clocks)

    @staticmethod
    def from_dict(data: Optional[Dict[str, int]]) -> VersionVector:
        """
        Creates an VersionVector instance from a dictionary.

        Args:
            data (Optional[Dict[str, int]]): A dictionary containing the version vector data.
                                            Can be None, in which case an empty VV will be created.

        Returns:
            VersionVector: The created VersionVector instance.
        """
        vv = VersionVector()
        # Ensure keys are strings and values are integers, gracefully handling errors
        for k, v in (data or {}).items():
            try:
                vv.clocks[str(k)] = int(v)
            except (TypeError, ValueError) as e:
                logger.warning(f"Skipping invalid entry in VersionVector data: key={k!r}, value={v!r}. Error: {e}")
        return vv


@dataclass(slots=True)
class CRDTRecord:
    """
    Represents the current resolved state of a genome record in the CRDT.
    This is the state after applying all operations according to LWW rules.

    Attributes:
        gid (str): Globally unique identifier for the genome record.
        payload (Dict[str, Any]): The current data payload of the record.
        clock (int): The Lamport clock value of the operation that last updated this record.
        node_id (str): The ID of the node that created the operation that last updated this record.
        deleted (bool): True if the record is marked as deleted (tombstone), False otherwise.
        ts (float): The Unix timestamp of the operation that last updated this record.
    """
    gid: str
    payload: Dict[str, Any]
    clock: int
    node_id: str
    deleted: bool = False
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the CRDTRecord instance to a dictionary.

        Returns:
            Dict[str, Any]: A dictionary representation of the record.
        """
        return {
            "gid": self.gid,
            "payload": self.payload,
            "clock": self.clock,
            "node_id": self.node_id,
            "deleted": self.deleted,
            "ts": self.ts,
        }


# =========================
# STORAGE
# =========================

class CRDTStorage:
    """
    Manages persistence for CRDT operations, records, version vectors,
    and memory snapshots using an SQLite database.

    CRDTStorage ensures thread-safety through an internal `threading.RLock`.
    Each database interaction is protected by this lock, and a new connection
    is opened for each operation within the locked context to avoid
    `sqlite3.ProgrammingError` in multi-threaded scenarios.
    """

    def __init__(self, path: str) -> None:
        """
        Initializes CRDTStorage with the given database path.

        Args:
            path (str): The path to the SQLite database file.
        """
        self.path: Final = path
        self._lock = threading.RLock() # Reentrant lock for thread safety
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """
        Establishes and returns a connection to the SQLite database.
        Uses `check_same_thread=False` to allow SQLite to be used across threads
        if connections were shared, but in this implementation, each `_connect` call
        within a locked block ensures a unique connection per operation per thread.
        This also enables WAL mode and sets a busy timeout to mitigate "database is locked" errors
        during concurrent access.

        Returns:
            sqlite3.Connection: An SQLite connection object.
        """
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # Allows accessing columns by name
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;") # 5-second timeout
        return conn

    def _init_db(self) -> None:
        """
        Initializes the database schema, creating necessary tables if they do not exist.
        Uses STRICT tables to enforce data types.
        """
        with self._lock: # Lock during schema initialization
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ops (
                        op_id TEXT PRIMARY KEY NOT NULL,
                        node_id TEXT NOT NULL,
                        clock INTEGER NOT NULL,
                        kind TEXT NOT NULL,
                        gid TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        ts REAL NOT NULL
                    ) STRICT
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS records (
                        gid TEXT PRIMARY KEY NOT NULL,
                        payload TEXT NOT NULL,
                        clock INTEGER NOT NULL,
                        node_id TEXT NOT NULL,
                        deleted INTEGER NOT NULL,
                        ts REAL NOT NULL
                    ) STRICT
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS version_vector (
                        node_id TEXT PRIMARY KEY NOT NULL,
                        clock INTEGER NOT NULL
                    ) STRICT
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memory_snapshots (
                        key TEXT PRIMARY KEY NOT NULL,
                        data BLOB,
                        updated_at REAL
                    ) STRICT
                    """
                )
                conn.commit()

    def save_op(self, op: CRDTOperation) -> None:
        """
        Saves a CRDT operation to the database.
        The operation is inserted if it does not exist (duplicates by op_id are ignored).

        Args:
            op (CRDTOperation): The operation to save.

        Raises:
            sqlite3.Error: If a database error occurs during saving.
            TypeError: If the operation payload is not JSON serializable.
        """
        try:
            payload_json = json.dumps(op.payload, sort_keys=True) # Deterministic serialization
        except TypeError as e:
            logger.error(f"Failed to serialize payload for op {op.op_id}: {e}")
            raise

        with self._lock:
            with self._connect() as conn:
                try:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO ops(op_id, node_id, clock, kind, gid, payload, ts)
                        VALUES(?,?,?,?,?,?,?)
                        """,
                        (
                            op.op_id,
                            op.node_id,
                            op.clock,
                            op.kind,
                            op.gid,
                            payload_json,
                            op.ts,
                        ),
                    )
                    conn.commit()
                except sqlite3.Error as e:
                    logger.error(f"Database error saving operation {op.op_id}: {e}")
                    raise

    def load_ops(self) -> List[CRDTOperation]:
        """
        Loads all CRDT operations from the database, ordered by timestamp, then by Lamport clock.

        Returns:
            List[CRDTOperation]: A list of loaded operations.
        """
        out: List[CRDTOperation] = []
        with self._lock:
            with self._connect() as conn:
                try:
                    rows = conn.execute(
                        "SELECT op_id, node_id, clock, kind, gid, payload, ts FROM ops ORDER BY ts ASC, clock ASC"
                    ).fetchall()
                    for row in rows:
                        try:
                            out.append(
                                CRDTOperation(
                                    op_id=row["op_id"],
                                    node_id=row["node_id"],
                                    clock=int(row["clock"]),
                                    kind=row["kind"], # type: ignore # Assumed valid from DB STRICT schema
                                    gid=row["gid"],
                                    payload=json.loads(row["payload"]),
                                    ts=float(row["ts"]),
                                )
                            )
                        except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
                            op_id_info = row["op_id"] if "op_id" in row else "N/A"
                            logger.error(f"Failed to load CRDTOperation from DB (op_id: {op_id_info}): {e}. Skipping row.")
                except sqlite3.Error as e:
                    logger.error(f"Database error loading operations: {e}")
        return out

    def save_record(self, record: CRDTRecord) -> None:
        """
        Saves a CRDT record (representing the current genome state) to the database.
        Updates an existing record or inserts a new one using `ON CONFLICT`.

        Args:
            record (CRDTRecord): The record to save.

        Raises:
            sqlite3.Error: If a database error occurs during saving.
            TypeError: If the record payload is not JSON serializable.
        """
        try:
            payload_json = json.dumps(record.payload, sort_keys=True) # Deterministic serialization
        except TypeError as e:
            logger.error(f"Failed to serialize payload for record {record.gid}: {e}")
            raise

        with self._lock:
            with self._connect() as conn:
                try:
                    conn.execute(
                        """
                        INSERT INTO records(gid, payload, clock, node_id, deleted, ts)
                        VALUES(?,?,?,?,?,?)
                        ON CONFLICT(gid) DO UPDATE SET
                            payload=excluded.payload,
                            clock=excluded.clock,
                            node_id=excluded.node_id,
                            deleted=excluded.deleted,
                            ts=excluded.ts
                        """,
                        (
                            record.gid,
                            payload_json,
                            record.clock,
                            record.node_id,
                            int(record.deleted), # SQLite stores bools as integers
                            record.ts,
                        ),
                    )
                    conn.commit()
                except sqlite3.Error as e:
                    logger.error(f"Database error saving record {record.gid}: {e}")
                    raise

    def load_records(self) -> Dict[str, CRDTRecord]:
        """
        Loads all CRDT records (current state of genomes) from the database.

        Returns:
            Dict[str, CRDTRecord]: A dictionary mapping GID to CRDTRecord instances.
        """
        out: Dict[str, CRDTRecord] = {}
        with self._lock:
            with self._connect() as conn:
                try:
                    rows = conn.execute(
                        "SELECT gid, payload, clock, node_id, deleted, ts FROM records"
                    ).fetchall()
                    for row in rows:
                        try:
                            out[row["gid"]] = CRDTRecord(
                                gid=row["gid"],
                                payload=json.loads(row["payload"]),
                                clock=int(row["clock"]),
                                node_id=row["node_id"],
                                deleted=bool(row["deleted"]),
                                ts=float(row["ts"]),
                            )
                        except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
                            gid_info = row["gid"] if "gid" in row else "N/A"
                            logger.error(f"Failed to load CRDTRecord from DB (gid: {gid_info}): {e}. Skipping row.")
                except sqlite3.Error as e:
                    logger.error(f"Database error loading records: {e}")
        return out

    def load_vv(self) -> VersionVector:
        """
        Loads the VersionVector from the database.

        Returns:
            VersionVector: The loaded version vector.
        """
        vv = VersionVector()
        with self._lock:
            with self._connect() as conn:
                try:
                    rows = conn.execute("SELECT node_id, clock FROM version_vector").fetchall()
                    for row in rows:
                        try:
                            vv.clocks[str(row["node_id"])] = int(row["clock"])
                        except (TypeError, ValueError) as e:
                            node_id_info = row["node_id"] if "node_id" in row else "N/A"
                            logger.warning(f"Skipping invalid entry in version_vector (node_id: {node_id_info}): {e}.")
                except sqlite3.Error as e:
                    logger.error(f"Database error loading version vector: {e}")
        return vv

    def save_vv(self, vv: VersionVector) -> None:
        """
        Saves the VersionVector to the database.
        Updates existing entries or inserts new ones for each node.

        Args:
            vv (VersionVector): The version vector to save.
        """
        with self._lock:
            with self._connect() as conn:
                try:
                    for node_id, clock in vv.clocks.items():
                        conn.execute(
                            """
                            INSERT INTO version_vector(node_id, clock)
                            VALUES(?,?)
                            ON CONFLICT(node_id) DO UPDATE SET clock=excluded.clock
                            """,
                            (node_id, int(clock)),
                        )
                    conn.commit()
                except sqlite3.Error as e:
                    logger.error(f"Database error saving version vector: {e}")
                    raise

    def save_snapshot(self, key: str, data: bytes) -> None:
        """
        Saves binary memory snapshot data by a given key.
        Updates an existing snapshot or inserts a new one.

        Args:
            key (str): The unique key for the memory snapshot.
            data (bytes): The binary snapshot data.

        Raises:
            sqlite3.Error: If a database error occurs during saving.
        """
        with self._lock:
            with self._connect() as conn:
                try:
                    conn.execute(
                        "INSERT OR REPLACE INTO memory_snapshots (key, data, updated_at) VALUES (?, ?, ?)",
                        (key, data, time.time())
                    )
                    conn.commit()
                except sqlite3.Error as e:
                    logger.error(f"Database error saving snapshot for key '{key}': {e}")
                    raise

    def load_snapshot(self, key: str) -> Optional[bytes]:
        """
        Loads binary memory snapshot data by a given key.

        Args:
            key (str): The unique key for the memory snapshot.

        Returns:
            Optional[bytes]: The binary snapshot data if found, otherwise None.
        """
        with self._lock:
            with self._connect() as conn:
                try:
                    row = conn.execute(
                        "SELECT data FROM memory_snapshots WHERE key = ?",
                        (key,)
                    ).fetchone()
                    if row:
                        return row["data"] # Access by column name
                except sqlite3.Error as e:
                    logger.error(f"Database error loading snapshot for key '{key}': {e}")
        return None


# =========================
# CRDT CORE
# =========================

class GenomeCRDT:
    """
    Operation-based CRDT for managing genome records with deterministic
    Last-Write-Wins (LWW) semantics.

    Conflict Resolution Rules (applied to operations on the same GID):
    - Priority is given to the operation with a higher Lamport clock value (`clock`).
    - If clock values are equal, priority is given to the operation with a lexicographically
      larger `node_id` (this is a deterministic tie-breaker).
    - A delete operation (kind="delete") has priority over older updates and is handled
      like any other operation, considering clock and node_id.
    - Duplicate operations are ignored based on `op_id`.
    """

    def __init__(self, node_id: str, storage: Optional[CRDTStorage] = None) -> None:
        """
        Initializes a GenomeCRDT instance.

        Args:
            node_id (str): A unique identifier for this node.
            storage (Optional[CRDTStorage]): An optional storage backend for persistence.
                                             If None, the CRDT operates only in-memory,
                                             and the operation log will not be persisted.
        """
        self.node_id: Final = node_id
        self.clock: int = 0 # Local Lamport clock, always increasing for this node's initiated ops
        self.vv: VersionVector = VersionVector() # Tracks highest clocks from all nodes
        self.storage: Optional[CRDTStorage] = storage
        self._lock = threading.RLock() # Reentrant lock for concurrent access

        # In-memory state
        self._records: Dict[str, CRDTRecord] = {} # Current resolved state of all genome records by GID
        self._seen_ops: Set[str] = set() # Set of unique operation IDs already processed

        if self.storage is not None:
            self._bootstrap_from_storage()
        else:
            logger.warning("GenomeCRDT initialized without persistent storage. Data will be lost on exit.")
            # For in-memory-only, ensure local clock and VV are initialized minimally
            self._next_clock() # Initialize clock and VV for this node to 1

    def _bootstrap_from_storage(self) -> None:
        """
        Loads the initial state from the configured storage backend.
        This includes resolved records, the version vector, and marking
        already processed operations. When loading operations, the local
        clock and version vector are updated to reflect all historical operations.

        Note: If a `compact()` method were implemented and operations were pruned,
        `_load_ops_for_delta` might not provide a full historical log.
        This current bootstrapping assumes the full log is available.
        """
        with self._lock:
            try:
                self._records = self.storage.load_records() if self.storage else {}
                self.vv = self.storage.load_vv() if self.storage else VersionVector()
                
                # Replay ops to update _seen_ops and ensure local clock and VV are fully caught up
                ops_from_storage = self.storage.load_ops() if self.storage else []
                for op in ops_from_storage:
                    self._seen_ops.add(op.op_id)
                    # Update this node's Lamport clock if an observed operation has a higher clock.
                    # This ensures our local clock is causally consistent with all observed history.
                    self.clock = max(self.clock, op.clock)
                    self.vv.observe(op.node_id, op.clock)
                
                # Ensure local clock is at least 1 and observed in VV if no ops were loaded,
                # or if the current node's clock from history is still 0.
                if self.clock == 0 or not self.vv.seen(self.node_id, self.clock):
                    self._next_clock() # Ensures this node has at least one clock tick recorded

                logger.info(
                    f"CRDT bootstrapped from storage. Records: {len(self._records)}, "
                    f"Seen Ops: {len(self._seen_ops)}, Current Clock: {self.clock}, VV: {self.vv.to_dict()}"
                )
            except Exception as e:
                logger.error(f"Failed to bootstrap CRDT from storage: {e}. Starting with empty state.")
                self._records = {}
                self.vv = VersionVector()
                self.clock = 0
                self._seen_ops = set()
                self._next_clock() # Initialize clock and VV minimally even after bootstrap failure

    def _next_clock(self) -> int:
        """
        Increments the local node's Lamport clock and updates the version vector for this node.
        This method should be called when this node is initiating a new operation.

        Returns:
            int: The new clock value.
        """
        self.clock += 1
        self.vv.observe(self.node_id, self.clock)
        return self.clock

    def _should_apply(self, current: Optional[CRDTRecord], op: CRDTOperation) -> bool:
        """
        Determines whether an incoming operation should be applied based on LWW rules.

        Args:
            current (Optional[CRDTRecord]): The current state of the record for this GID,
                                            or None if the record does not exist.
            op (CRDTOperation): The incoming operation.

        Returns:
            bool: True if the operation should be applied; False otherwise.
        """
        if current is None:
            return True # No existing record, always apply new operations

        # LWW Rule 1: Higher Lamport clock wins
        if op.clock > current.clock:
            return True
        if op.clock < current.clock:
            return False

        # LWW Rule 2: If clocks are equal, lexicographically larger node_id wins
        return op.node_id > current.node_id

    def _apply_op(self, op: CRDTOperation) -> bool:
        """
        Applies a CRDT operation to the local state and persists it if storage is enabled.
        Updates `_seen_ops` and `vv` for any observed operation, regardless of whether
        it actually modified `_records` (e.g., if it was a duplicate or an older operation).

        Args:
            op (CRDTOperation): The operation to apply.

        Returns:
            bool: True if the operation caused a change in the local resolved records (`_records`);
                  False otherwise (e.g., it was a duplicate, or rejected by LWW rules).
        """
        with self._lock:
            # Always update our version vector, as we have now observed this operation
            self.vv.observe(op.node_id, op.clock)

            # If we've already seen this exact operation, we don't need to re-apply it to _records.
            # We still persist it to storage (INSERT OR IGNORE) and update VV.
            if op.op_id in self._seen_ops:
                if self.storage is not None:
                    self.storage.save_op(op) # `INSERT OR IGNORE` handles duplicates
                    self.storage.save_vv(self.vv) # Always save VV as it's updated
                return False # Not considered an 'application' to _records if already seen

            # Mark this operation as seen to prevent future re-processing
            self._seen_ops.add(op.op_id)
            
            current_record = self._records.get(op.gid)
            
            # Decide if the operation should modify the current resolved state (`_records`)
            apply_to_records = self._should_apply(current_record, op)

            if apply_to_records:
                if op.kind == OPERATION_KIND_DELETE:
                    new_record = CRDTRecord(
                        gid=op.gid,
                        payload={}, # Payload is typically empty/ignored for deletes (tombstone)
                        clock=op.clock,
                        node_id=op.node_id,
                        deleted=True,
                        ts=op.ts,
                    )
                elif op.kind == OPERATION_KIND_UPSERT:
                    new_record = CRDTRecord(
                        gid=op.gid,
                        payload=dict(op.payload), # Create a copy to ensure immutability
                        clock=op.clock,
                        node_id=op.node_id,
                        deleted=False,
                        ts=op.ts,
                    )
                else:
                    # This case should ideally be caught earlier by type hints / validation in from_dict,
                    # but as a safeguard against corrupted data or unexpected operation kinds.
                    logger.error(f"Unknown operation kind '{op.kind}' for op_id: {op.op_id}. Skipping application to records.")
                    apply_to_records = False # Do not change records for unknown kind

                if apply_to_records:
                    self._records[op.gid] = new_record

            # Persist the operation, the updated record (if applied), and the version vector
            if self.storage is not None:
                self.storage.save_op(op)
                if apply_to_records: # Only save record if its state actually changed
                    self.storage.save_record(self._records[op.gid])
                self.storage.save_vv(self.vv) # Always save VV as it's updated for every seen op

            return apply_to_records # Return whether the _records state was changed


    def upsert(self, gid: str, payload: Dict[str, Any], op_id: Optional[str] = None) -> CRDTOperation:
        """
        Creates and applies an 'upsert' operation for a genome record.
        This operation is generated locally by this node.

        Args:
            gid (str): The globally unique identifier for the genome record.
            payload (Dict[str, Any]): The data payload for the genome.
            op_id (Optional[str]): An optional unique ID for the operation.
                                    If None, a new UUID will be generated.

        Returns:
            CRDTOperation: The created and applied CRDT operation.
        """
        with self._lock:
            # Always ensure the local clock is advanced *before* creating a new operation
            clock = self._next_clock()
            op = CRDTOperation(
                op_id=op_id or str(uuid.uuid4()),
                node_id=self.node_id,
                clock=clock,
                kind=OPERATION_KIND_UPSERT,
                gid=gid,
                payload=dict(payload), # Create a copy to ensure payload immutability
                ts=time.time(),
            )
            self._apply_op(op) # This will also save op to storage
            return op

    def delete(self, gid: str, op_id: Optional[str] = None) -> CRDTOperation:
        """
        Creates and applies a 'delete' operation for a genome record.
        This operation is generated locally by this node.

        Args:
            gid (str): The globally unique identifier of the genome record to delete.
            op_id (Optional[str]): An optional unique ID for the operation.
                                    If None, a new UUID will be generated.

        Returns:
            CRDTOperation: The created and applied CRDT operation.
        """
        with self._lock:
            # Always ensure the local clock is advanced *before* creating a new operation
            clock = self._next_clock()
            op = CRDTOperation(
                op_id=op_id or str(uuid.uuid4()),
                node_id=self.node_id,
                clock=clock,
                kind=OPERATION_KIND_DELETE,
                gid=gid,
                payload={}, # Payload is empty for delete operations
                ts=time.time(),
            )
            self._apply_op(op) # This will also save op to storage
            return op

    def merge(self, remote_ops: Iterable[Union[Dict[str, Any], CRDTOperation]]) -> int:
        """
        Merges a collection of remote CRDT operations into the local state.
        Each operation is processed according to LWW rules.

        Args:
            remote_ops (Iterable[Union[Dict[str, Any], CRDTOperation]]): An iterable of operations,
                                                                  which can be dictionaries
                                                                  or CRDTOperation objects.

        Returns:
            int: The count of unique operations that were successfully applied to
                 the local resolved state (`_records`). This means operations that
                 caused a change in `_records`.
        """
        applied_to_records_count = 0
        with self._lock:
            for item in remote_ops:
                try:
                    op = item if isinstance(item, CRDTOperation) else CRDTOperation.from_dict(item)
                    if self._apply_op(op): # _apply_op returns True if _records was changed
                        applied_to_records_count += 1
                except (ValueError, KeyError, TypeError) as e:
                    # Log and skip malformed remote operations to avoid crashing the system
                    logger.error(f"Failed to process remote operation: {e}. Item: {item}")
            return applied_to_records_count

    def get(self, gid: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the payload of a genome record by its GID, if it exists and is not deleted.

        Args:
            gid (str): The globally unique identifier of the genome record.

        Returns:
            Optional[Dict[str, Any]]: The genome's payload, or None if the record is not found or is deleted.
                                      A copy of the payload is returned to prevent external modification
                                      of the internal state.
        """
        with self._lock:
            record = self._records.get(gid)
            if record is None or record.deleted:
                return None
            return dict(record.payload) # Return a copy to prevent external modification of internal state

    def state(self) -> Dict[str, Dict[str, Any]]:
        """
        Returns the current state of all active (non-deleted) genome records.

        Returns:
            Dict[str, Dict[str, Any]]: A dictionary mapping GIDs to their corresponding payloads.
                                        Copies of payloads are returned.
        """
        with self._lock:
            return {
                gid: dict(rec.payload) # Return a copy of the payload
                for gid, rec in self._records.items()
                if not rec.deleted
            }

    def tombstones(self) -> List[str]:
        """
        Returns a list of GIDs for records that have been marked as deleted (tombstones).

        Returns:
            List[str]: A list of GIDs that are currently tombstones.
        """
        with self._lock:
            return [gid for gid, rec in self._records.items() if rec.deleted]

    def delta_since(self, other_vv: Union[VersionVector, Dict[str, int]]) -> List[Dict[str, Any]]:
        """
        Calculates the set of operations unknown to another node, based on its VersionVector.
        Returns operations that the current node has, and `other_vv` has not yet seen.

        Important note: If a `compact()` method were implemented and old operations
        were pruned from the log, `delta_since` might not be able to provide
        the full history of operations. In such a case, synchronization for
        nodes lagging significantly might require a full state transfer.
        When running without persistent storage, this method synthesizes
        operations from the current resolved state, which reflects only the *latest*
        operation for each GID and might not include all historical 'delete' operations.

        Args:
            other_vv (Union[VersionVector, Dict[str, int]]): The VersionVector of the other node
                                                       or its dictionary representation.

        Returns:
            List[Dict[str, Any]]: A list of operations (as dictionaries) that the other node should receive.
        """
        if isinstance(other_vv, dict):
            other_vv = VersionVector.from_dict(other_vv)

        with self._lock:
            out: List[Dict[str, Any]] = []
            # We iterate through all operations (from storage or synthesized for in-memory)
            # and check if the remote node has seen them.
            for op in self._load_ops_for_delta():
                if not other_vv.seen(op.node_id, op.clock):
                    out.append(op.to_dict())
            return out

    def _load_ops_for_delta(self) -> List[CRDTOperation]:
        """
        Helper method to load operations from storage or synthesize them
        from current records if storage is not configured.

        If storage is absent, operations are synthesized from the current in-memory state
        (`_records`). This means for each active or deleted record, a corresponding
        upsert or delete operation is created.
        These synthesized operations represent the *latest* state-changing operation
        for each GID at its current clock/node_id. They are not true historical
        operations and will have generated `op_id`s. This mode has limitations
        for full historical synchronization (e.g., if a node needs to learn about
        intermediate states or operations that were later overwritten by others
        with lower LWW priority).
        """
        if self.storage is not None:
            return self.storage.load_ops()

        # If no storage, synthesize a minimal log from current in-memory state.
        # This will only include operations reflecting the *latest* state for each GID.
        synthesized_ops: List[CRDTOperation] = []
        for rec in self._records.values():
            # For delta_since, we need an operation object.
            # Since CRDTRecord does not store the original op_id, we generate a deterministic one
            # using UUID5 to ensure consistency across restarts/reconstructions for the same record data.
            op_id_seed = f"{rec.gid}-{rec.node_id}-{rec.clock}-{rec.ts}-{rec.deleted}-{json.dumps(rec.payload, sort_keys=True)}"
            op_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, op_id_seed))
            
            synthesized_ops.append(
                CRDTOperation(
                    op_id=op_id,
                    node_id=rec.node_id,
                    clock=rec.clock,
                    kind=OPERATION_KIND_DELETE if rec.deleted else OPERATION_KIND_UPSERT,
                    gid=rec.gid,
                    payload=dict(rec.payload), # Use a copy
                    ts=rec.ts,
                )
            )
        # It's important to sort these synthesized operations for consistent delta reporting,
        # mimicking the `ORDER BY ts ASC, clock ASC` from actual storage. Tie-break with node_id then op_id.
        synthesized_ops.sort(key=lambda op: (op.ts, op.clock, op.node_id, op.op_id))
        return synthesized_ops