from __future__ import annotations

"""
Operation-based CRDT for genome records.

Design:
- deterministic last-write-wins at the field/entity level
- op log for replay / sync / recovery
- Lamport-style clocks per node
- tombstones for deletes
- SQLite persistence for state + operations

This module is intentionally small and testable.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple
import json
import os
import sqlite3
import threading
import time
import uuid


# =========================
# DATA MODEL
# =========================

@dataclass(frozen=True, slots=True)
class CRDTOperation:
    """
    Represents a single CRDT operation (upsert or delete) on a genome record.
    """
    op_id: str
    node_id: str
    clock: int
    kind: str  # "upsert" | "delete"
    gid: str
    payload: Dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the CRDTOperation instance to a dictionary.
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
        """
        return CRDTOperation(
            op_id=str(data["op_id"]),
            node_id=str(data["node_id"]),
            clock=int(data["clock"]),
            kind=str(data["kind"]),
            gid=str(data["gid"]),
            payload=dict(data.get("payload", {})),
            ts=float(data.get("ts", time.time())),
        )


@dataclass(slots=True)
class VersionVector:
    """
    A Version Vector tracks the highest clock value seen from each node.
    Used to determine causal order and identify missing operations during synchronization.
    """
    clocks: Dict[str, int] = field(default_factory=dict)

    def bump(self, node_id: str) -> int:
        """
        Increments the clock for a given node and returns the new clock value.
        """
        self.clocks[node_id] = self.clocks.get(node_id, 0) + 1
        return self.clocks[node_id]

    def observe(self, node_id: str, clock: int) -> None:
        """
        Updates the clock for a given node if the new clock value is higher.
        """
        self.clocks[node_id] = max(self.clocks.get(node_id, 0), int(clock))

    def seen(self, node_id: str, clock: int) -> bool:
        """
        Checks if a specific clock value for a node has been observed.
        """
        return self.clocks.get(node_id, 0) >= int(clock)

    def merge(self, other: VersionVector) -> None:
        """
        Merges another VersionVector into this one, updating clocks to their maximum values.
        """
        for node_id, clock in other.clocks.items():
            self.observe(node_id, clock)

    def to_dict(self) -> Dict[str, int]:
        """
        Converts the VersionVector to a dictionary.
        """
        return dict(self.clocks)

    @staticmethod
    def from_dict(data: Dict[str, int]) -> VersionVector:
        """
        Creates a VersionVector instance from a dictionary.
        """
        vv = VersionVector()
        for k, v in (data or {}).items():
            vv.clocks[str(k)] = int(v)
        return vv


@dataclass(slots=True)
class CRDTRecord:
    """
    Represents the current state of a genome record in the CRDT.
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
    Manages persistence for CRDT operations, records, version vector, and memory snapshots
    using an SQLite database.
    """
    def __init__(self, path: str) -> None:
        """
        Initializes the CRDTStorage with the given database path.

        Args:
            path (str): The file path for the SQLite database.
        """
        self.path = path
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """
        Establishes and returns a connection to the SQLite database.
        """
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """
        Initializes the database schema by creating necessary tables if they don't exist.
        """
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ops (
                    op_id TEXT PRIMARY KEY,
                    node_id TEXT NOT NULL,
                    clock INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    gid TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    ts REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS records (
                    gid TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    clock INTEGER NOT NULL,
                    node_id TEXT NOT NULL,
                    deleted INTEGER NOT NULL,
                    ts REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS version_vector (
                    node_id TEXT PRIMARY KEY,
                    clock INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_snapshots (
                    key TEXT PRIMARY KEY,
                    data BLOB,
                    updated_at REAL
                )
                """
            )
            conn.commit()

    def save_op(self, op: CRDTOperation) -> None:
        """
        Saves a CRDT operation to the database.

        Args:
            op (CRDTOperation): The operation to save.
        """
        with self._lock, self._connect() as conn:
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
                    json.dumps(op.payload, sort_keys=True),
                    op.ts,
                ),
            )
            conn.commit()

    def load_ops(self) -> List[CRDTOperation]:
        """
        Loads all CRDT operations from the database, ordered by timestamp and clock.

        Returns:
            List[CRDTOperation]: A list of loaded operations.
        """
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT op_id, node_id, clock, kind, gid, payload, ts FROM ops ORDER BY ts ASC, clock ASC"
            ).fetchall()
            out: List[CRDTOperation] = []
            for row in rows:
                out.append(
                    CRDTOperation(
                        op_id=row["op_id"],
                        node_id=row["node_id"],
                        clock=int(row["clock"]),
                        kind=row["kind"],
                        gid=row["gid"],
                        payload=json.loads(row["payload"]),
                        ts=float(row["ts"]),
                    )
                )
            return out

    def save_record(self, record: CRDTRecord) -> None:
        """
        Saves a CRDT record (representing the current state of a genome) to the database.
        Updates an existing record or inserts a new one.

        Args:
            record (CRDTRecord): The record to save.
        """
        with self._lock, self._connect() as conn:
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
                    json.dumps(record.payload, sort_keys=True),
                    record.clock,
                    record.node_id,
                    int(record.deleted),
                    record.ts,
                ),
            )
            conn.commit()

    def load_records(self) -> Dict[str, CRDTRecord]:
        """
        Loads all CRDT records (current state of genomes) from the database.

        Returns:
            Dict[str, CRDTRecord]: A dictionary mapping GIDs to CRDTRecord instances.
        """
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT gid, payload, clock, node_id, deleted, ts FROM records"
            ).fetchall()
            out: Dict[str, CRDTRecord] = {}
            for row in rows:
                out[row["gid"]] = CRDTRecord(
                    gid=row["gid"],
                    payload=json.loads(row["payload"]),
                    clock=int(row["clock"]),
                    node_id=row["node_id"],
                    deleted=bool(row["deleted"]),
                    ts=float(row["ts"]),
                )
            return out

    def load_vv(self) -> VersionVector:
        """
        Loads the VersionVector from the database.

        Returns:
            VersionVector: The loaded version vector.
        """
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT node_id, clock FROM version_vector").fetchall()
            vv = VersionVector()
            for row in rows:
                vv.clocks[row["node_id"]] = int(row["clock"])
            return vv

    def save_vv(self, vv: VersionVector) -> None:
        """
        Saves the VersionVector to the database.

        Args:
            vv (VersionVector): The version vector to save.
        """
        with self._lock, self._connect() as conn:
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

    def save_snapshot(self, key: str, data: bytes) -> None:
        """Сохраняет бинарный снапшот памяти."""
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO memory_snapshots (key, data, updated_at) VALUES (?, ?, ?)",
                (key, data, time.time())
            )
            conn.commit()

    def load_snapshot(self, key: str) -> Optional[bytes]:
        """Загружает снапшот памяти."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT data FROM memory_snapshots WHERE key = ?",
                (key,)
            ).fetchone()
            if row:
                return row[0]
            return None


# =========================
# CRDT CORE
# =========================

class GenomeCRDT:
    """
    Operation-based CRDT for managing genome records with deterministic Last-Write-Wins (LWW) semantics.

    Rules:
    - each gid maps to one record
    - higher clock wins
    - on equal clock, lexicographically larger node_id wins
    - delete is represented by tombstone and wins over older updates
    - duplicate operations are ignored via op_id
    """

    def __init__(self, node_id: str, storage: Optional[CRDTStorage] = None) -> None:
        """
        Initializes the GenomeCRDT instance.

        Args:
            node_id (str): The unique identifier for this node.
            storage (Optional[CRDTStorage]): An optional storage backend for persistence.
        """
        self.node_id = node_id
        self.clock: int = 0
        self.vv: VersionVector = VersionVector()
        self.storage: Optional[CRDTStorage] = storage
        self._lock = threading.RLock()

        self._records: Dict[str, CRDTRecord] = {}
        self._seen_ops: set[str] = set()

        if self.storage is not None:
            self._bootstrap_from_storage()

    def _bootstrap_from_storage(self) -> None:
        """
        Loads initial state from the configured storage backend.
        """
        self._records = self.storage.load_records()
        self.vv = self.storage.load_vv()
        for op in self.storage.load_ops():
            self._seen_ops.add(op.op_id)
            self.clock = max(self.clock, op.clock)
            self.vv.observe(op.node_id, op.clock)

    def _next_clock(self) -> int:
        """
        Increments the local clock and updates the version vector for this node.

        Returns:
            int: The new clock value.
        """
        self.clock += 1
        self.vv.observe(self.node_id, self.clock)
        return self.clock

    def _should_apply(self, current: Optional[CRDTRecord], op: CRDTOperation) -> bool:
        """
        Determines if an incoming operation should be applied based on LWW rules.

        Args:
            current (Optional[CRDTRecord]): The current record state for the given GID, or None if not present.
            op (CRDTOperation): The incoming operation.

        Returns:
            bool: True if the operation should be applied, False otherwise.
        """
        if current is None:
            return True
        if op.clock > current.clock:
            return True
        if op.clock < current.clock:
            return False
        # Tie-breaker: lexicographically larger node_id wins
        return op.node_id > current.node_id

    def _apply_op(self, op: CRDTOperation) -> bool:
        """
        Applies a CRDT operation to the local state and persists it if storage is enabled.

        Args:
            op (CRDTOperation): The operation to apply.

        Returns:
            bool: True if the operation was applied, False if it was a duplicate or rejected.
        """
        if op.op_id in self._seen_ops:
            return False

        current = self._records.get(op.gid)
        if current is not None and not self._should_apply(current, op):
            self._seen_ops.add(op.op_id)
            self.vv.observe(op.node_id, op.clock)
            if self.storage is not None:
                self.storage.save_op(op)
                self.storage.save_vv(self.vv) # Also save VV even if op is rejected
            return False

        if op.kind not in ("upsert", "delete"):
            raise ValueError(f"Unknown operation kind: {op.kind}")

        if op.kind == "delete":
            record = CRDTRecord(
                gid=op.gid,
                payload={},
                clock=op.clock,
                node_id=op.node_id,
                deleted=True,
                ts=op.ts,
            )
        else: # kind == "upsert"
            payload = dict(op.payload)
            record = CRDTRecord(
                gid=op.gid,
                payload=payload,
                clock=op.clock,
                node_id=op.node_id,
                deleted=False,
                ts=op.ts,
            )

        self._records[op.gid] = record
        self._seen_ops.add(op.op_id)
        self.vv.observe(op.node_id, op.clock)

        if self.storage is not None:
            self.storage.save_op(op)
            self.storage.save_record(record)
            self.storage.save_vv(self.vv)

        return True

    def upsert(self, gid: str, payload: Dict[str, Any], op_id: Optional[str] = None) -> CRDTOperation:
        """
        Creates and applies an 'upsert' operation for a genome record.

        Args:
            gid (str): The globally unique ID for the genome record.
            payload (Dict[str, Any]): The data payload for the genome.
            op_id (Optional[str]): An optional unique ID for the operation.
                                    If None, a new UUID will be generated.

        Returns:
            CRDTOperation: The created and applied CRDT operation.
        """
        with self._lock:
            clock = self._next_clock()
            op = CRDTOperation(
                op_id=op_id or str(uuid.uuid4()),
                node_id=self.node_id,
                clock=clock,
                kind="upsert",
                gid=gid,
                payload=dict(payload),
                ts=time.time(),
            )
            self._apply_op(op)
            return op

    def delete(self, gid: str, op_id: Optional[str] = None) -> CRDTOperation:
        """
        Creates and applies a 'delete' operation for a genome record.

        Args:
            gid (str): The globally unique ID of the genome record to delete.
            op_id (Optional[str]): An optional unique ID for the operation.
                                    If None, a new UUID will be generated.

        Returns:
            CRDTOperation: The created and applied CRDT operation.
        """
        with self._lock:
            clock = self._next_clock()
            op = CRDTOperation(
                op_id=op_id or str(uuid.uuid4()),
                node_id=self.node_id,
                clock=clock,
                kind="delete",
                gid=gid,
                payload={},
                ts=time.time(),
            )
            self._apply_op(op)
            return op

    def merge(self, remote_ops: Iterable[Dict[str, Any] | CRDTOperation]) -> int:
        """
        Merges a collection of remote CRDT operations into the local state.

        Args:
            remote_ops (Iterable[Dict[str, Any] | CRDTOperation]): An iterable of
                                                                  operations, which can be
                                                                  dictionaries or CRDTOperation objects.

        Returns:
            int: The number of unique operations successfully applied.
        """
        applied = 0
        with self._lock:
            for item in remote_ops:
                op = item if isinstance(item, CRDTOperation) else CRDTOperation.from_dict(item)
                if op.op_id in self._seen_ops:
                    continue
                # If the operation is from this node, just record it as seen and update VV
                # without re-applying, as it originated here.
                if op.node_id == self.node_id:
                    self.vv.observe(op.node_id, op.clock)
                    self._seen_ops.add(op.op_id)
                    # If using storage, ensure this operation is also saved
                    if self.storage is not None:
                        self.storage.save_op(op)
                        self.storage.save_vv(self.vv)
                    continue
                if self._apply_op(op):
                    applied += 1
            return applied

    def get(self, gid: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the payload of a genome record by its GID, if it exists and is not deleted.

        Args:
            gid (str): The globally unique ID of the genome record.

        Returns:
            Optional[Dict[str, Any]]: The payload of the genome, or None if not found or deleted.
        """
        with self._lock:
            record = self._records.get(gid)
            if record is None or record.deleted:
                return None
            return dict(record.payload)

    def state(self) -> Dict[str, Dict[str, Any]]:
        """
        Returns the current state of all active (non-deleted) genome records.

        Returns:
            Dict[str, Dict[str, Any]]: A dictionary mapping GIDs to their respective payloads.
        """
        with self._lock:
            return {
                gid: dict(rec.payload)
                for gid, rec in self._records.items()
                if not rec.deleted
            }

    def tombstones(self) -> List[str]:
        """
        Returns a list of GIDs for records that have been marked as deleted.

        Returns:
            List[str]: A list of GIDs that are currently tombstones.
        """
        with self._lock:
            return [gid for gid, rec in self._records.items() if rec.deleted]

    def delta_since(self, other_vv: VersionVector | Dict[str, int]) -> List[Dict[str, Any]]:
        """
        Calculates the set of operations that are unknown to another node, based on its VersionVector.

        Args:
            other_vv (VersionVector | Dict[str, int]): The VersionVector of the other node,
                                                       or a dictionary representation of it.

        Returns:
            List[Dict[str, Any]]: A list of operations (as dictionaries) that the other node needs to receive.
        """
        if isinstance(other_vv, dict):
            other_vv = VersionVector.from_dict(other_vv)

        with self._lock:
            out: List[Dict[str, Any]] = []
            for op_id, op in self._load_ops_from_state():
                if not other_vv.seen(op.node_id, op.clock):
                    out.append(op.to_dict())
            return out

    def _load_ops_from_state(self) -> List[Tuple[str, CRDTOperation]]:
        """
        Helper to load operations from storage or synthesize them from current records
        if no storage is configured.

        Returns:
            List[Tuple[str, CRDTOperation]]: A list of (op_id, CRDTOperation) tuples.
        """
        # We keep the operation log in storage. If storage is absent, synthesize
        # a minimal log from current state so the object remains usable.
        if self.storage is not None:
            return [(op.op_id, op) for op in self.storage.load_ops()]

        out: List[Tuple[str, CRDTOperation]] = []
        for gid, rec in self._records.items():
            kind = "delete" if rec.deleted else "upsert"
            op = CRDTOperation(
                op_id=f"synth-{gid}-{rec.clock}-{rec.node_id}",
                node_id=rec.node_id,
                clock=rec.clock,
                kind=kind,
                gid=gid,
                payload=dict(rec.payload),
                ts=rec.ts,
            )
            out.append((op.op_id, op))
        return out

    def compact(self) -> None:
        """
        In storage-backed mode, compaction removes the op log and keeps only
        the latest records + version vector snapshot. In memory mode it is a no-op.
        """
        if self.storage is None:
            return

        with self._lock, self.storage._connect() as conn:
            conn.execute("DELETE FROM ops")
            conn.commit()

    def known_versions(self) -> Dict[str, int]:
        """
        Returns the current VersionVector as a dictionary.

        Returns:
            Dict[str, int]: A dictionary mapping node IDs to their highest observed clock values.
        """
        with self._lock:
            return self.vv.to_dict()

    def record_count(self) -> int:
        """
        Returns the total number of records (including tombstones) currently held in the CRDT.

        Returns:
            int: The count of all records.
        """
        with self._lock:
            return len(self._records)

    def max_clock(self) -> int:
        """
        Returns the highest clock value generated by this node.

        Returns:
            int: The maximum clock value.
        """
        with self._lock:
            return self.clock