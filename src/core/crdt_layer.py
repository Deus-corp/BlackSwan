"""Operation-based CRDT for genome records.

This module implements deterministic Last-Write-Wins CRDT semantics over
genome-like records using Lamport clocks, operation logs, version vectors, and
SQLite persistence.

The storage layer is intentionally conservative: every operation opens its own
SQLite connection, enables WAL/busy timeout, and retries transient lock errors.
This makes the module safer for the local multi-process swarm runtime where
several nodes write to the same CRDT database.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Iterable, Literal, Optional

logger = logging.getLogger(__name__)

OPERATION_KIND_UPSERT: Final[str] = "upsert"
OPERATION_KIND_DELETE: Final[str] = "delete"
CRDTOperationKind = Literal["upsert", "delete"]

SQLITE_TIMEOUT_SECONDS: Final[float] = 30.0
SQLITE_BUSY_TIMEOUT_MS: Final[int] = 30_000
SQLITE_WRITE_RETRIES: Final[int] = 6
SQLITE_WRITE_RETRY_DELAY_SECONDS: Final[float] = 0.05


@dataclass(frozen=True, slots=True)
class CRDTOperation:
    """A single immutable CRDT operation."""

    op_id: str
    node_id: str
    clock: int
    kind: CRDTOperationKind
    gid: str
    payload: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if self.kind not in (OPERATION_KIND_UPSERT, OPERATION_KIND_DELETE):
            raise ValueError(f"Invalid CRDT operation kind: {self.kind!r}")
        if not str(self.op_id).strip():
            raise ValueError("op_id cannot be empty")
        if not str(self.node_id).strip():
            raise ValueError("node_id cannot be empty")
        if not str(self.gid).strip():
            raise ValueError("gid cannot be empty")
        if int(self.clock) < 0:
            raise ValueError("clock cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "op_id": self.op_id,
            "node_id": self.node_id,
            "clock": int(self.clock),
            "kind": self.kind,
            "gid": self.gid,
            "payload": dict(self.payload),
            "ts": float(self.ts),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> CRDTOperation:
        required = ("op_id", "node_id", "clock", "kind", "gid")
        missing = [key for key in required if key not in data]
        if missing:
            raise ValueError(f"Missing CRDT operation field(s): {', '.join(missing)}")

        kind = str(data["kind"])
        if kind not in (OPERATION_KIND_UPSERT, OPERATION_KIND_DELETE):
            raise ValueError(f"Invalid operation kind: {kind!r}")

        payload = data.get("payload", {})
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise ValueError("operation payload must be a dict")

        return CRDTOperation(
            op_id=str(data["op_id"]),
            node_id=str(data["node_id"]),
            clock=int(data["clock"]),
            kind=kind,  # type: ignore[arg-type]
            gid=str(data["gid"]),
            payload=dict(payload),
            ts=float(data.get("ts", time.time())),
        )


@dataclass(slots=True)
class VersionVector:
    """Highest observed Lamport clock per node."""

    clocks: dict[str, int] = field(default_factory=dict)

    def bump(self, node_id: str) -> int:
        clean_node_id = str(node_id or "").strip()
        if not clean_node_id:
            raise ValueError("node_id cannot be empty")

        self.clocks[clean_node_id] = self.clocks.get(clean_node_id, 0) + 1
        return self.clocks[clean_node_id]

    def observe(self, node_id: str, clock: int) -> None:
        clean_node_id = str(node_id or "").strip()
        if not clean_node_id:
            return

        try:
            clean_clock = max(0, int(clock))
        except (TypeError, ValueError):
            logger.warning("Ignoring invalid version-vector clock: node=%r clock=%r", node_id, clock)
            return

        self.clocks[clean_node_id] = max(self.clocks.get(clean_node_id, 0), clean_clock)

    def seen(self, node_id: str, clock: int) -> bool:
        clean_node_id = str(node_id or "").strip()
        if not clean_node_id:
            return False

        try:
            clean_clock = int(clock)
        except (TypeError, ValueError):
            return False

        return self.clocks.get(clean_node_id, 0) >= clean_clock

    def merge(self, other: VersionVector) -> None:
        for node_id, clock in other.clocks.items():
            self.observe(node_id, clock)

    def to_dict(self) -> dict[str, int]:
        return dict(self.clocks)

    @staticmethod
    def from_dict(data: Optional[dict[str, int]]) -> VersionVector:
        vv = VersionVector()
        if not isinstance(data, dict):
            return vv

        for node_id, clock in data.items():
            vv.observe(str(node_id), int(clock))

        return vv


@dataclass(slots=True)
class CRDTRecord:
    """Resolved state of a CRDT record."""

    gid: str
    payload: dict[str, Any]
    clock: int
    node_id: str
    deleted: bool = False
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gid": self.gid,
            "payload": dict(self.payload),
            "clock": int(self.clock),
            "node_id": self.node_id,
            "deleted": bool(self.deleted),
            "ts": float(self.ts),
        }


class CRDTStorage:
    """SQLite persistence for CRDT operations, records, version vectors, and snapshots."""

    def __init__(self, path: str) -> None:
        clean_path = str(path or "").strip()
        if not clean_path:
            raise ValueError("CRDT database path cannot be empty")

        self.path: Final[str] = clean_path
        self._lock = threading.RLock()

        db_parent = Path(self.path).expanduser().resolve().parent
        db_parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.path,
            timeout=SQLITE_TIMEOUT_SECONDS,
            check_same_thread=False,
            isolation_level=None,
        )
        conn.row_factory = sqlite3.Row
        conn.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS};")
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        return conn

    @staticmethod
    def _is_locked_error(exc: BaseException) -> bool:
        return isinstance(exc, sqlite3.OperationalError) and "locked" in str(exc).lower()

    def _with_retry(self, label: str, operation: Any) -> Any:
        last_exc: Optional[BaseException] = None

        for attempt in range(SQLITE_WRITE_RETRIES):
            try:
                return operation()
            except sqlite3.OperationalError as exc:
                last_exc = exc
                if not self._is_locked_error(exc) or attempt >= SQLITE_WRITE_RETRIES - 1:
                    logger.error("Database error during %s: %s", label, exc)
                    raise

                delay = SQLITE_WRITE_RETRY_DELAY_SECONDS * (2**attempt)
                logger.warning(
                    "SQLite database locked during %s; retrying in %.3fs (%s/%s)",
                    label,
                    delay,
                    attempt + 1,
                    SQLITE_WRITE_RETRIES,
                )
                time.sleep(delay)

        if last_exc is not None:
            raise last_exc

        return None

    @staticmethod
    def _dumps(value: dict[str, Any]) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)

    @staticmethod
    def _loads(value: str) -> dict[str, Any]:
        decoded = json.loads(value)
        if isinstance(decoded, dict):
            return decoded
        return {}

    def _init_db(self) -> None:
        def op() -> None:
            with self._lock:
                with self._connect() as conn:
                    conn.execute("BEGIN IMMEDIATE;")
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
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_ops_gid ON ops(gid);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_ops_node_clock ON ops(node_id, clock);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_ops_ts_clock ON ops(ts, clock);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_records_deleted ON records(deleted);")
                    conn.execute("COMMIT;")

        self._with_retry("initialize CRDT database", op)

    def save_op(self, op: CRDTOperation) -> None:
        payload_json = self._dumps(op.payload)

        def write() -> None:
            with self._lock:
                with self._connect() as conn:
                    conn.execute("BEGIN IMMEDIATE;")
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO ops(op_id, node_id, clock, kind, gid, payload, ts)
                        VALUES(?,?,?,?,?,?,?)
                        """,
                        (
                            op.op_id,
                            op.node_id,
                            int(op.clock),
                            op.kind,
                            op.gid,
                            payload_json,
                            float(op.ts),
                        ),
                    )
                    conn.execute("COMMIT;")

        self._with_retry(f"save operation {op.op_id}", write)

    def load_ops(self) -> list[CRDTOperation]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT op_id, node_id, clock, kind, gid, payload, ts
                    FROM ops
                    ORDER BY ts ASC, clock ASC, node_id ASC, op_id ASC
                    """
                ).fetchall()

        ops: list[CRDTOperation] = []
        for row in rows:
            try:
                ops.append(
                    CRDTOperation(
                        op_id=str(row["op_id"]),
                        node_id=str(row["node_id"]),
                        clock=int(row["clock"]),
                        kind=str(row["kind"]),  # type: ignore[arg-type]
                        gid=str(row["gid"]),
                        payload=self._loads(str(row["payload"])),
                        ts=float(row["ts"]),
                    )
                )
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                logger.error("Skipping malformed CRDT operation row: %s row=%r", exc, dict(row))

        return ops

    def save_record(self, record: CRDTRecord) -> None:
        payload_json = self._dumps(record.payload)

        def write() -> None:
            with self._lock:
                with self._connect() as conn:
                    conn.execute("BEGIN IMMEDIATE;")
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
                            int(record.clock),
                            record.node_id,
                            int(record.deleted),
                            float(record.ts),
                        ),
                    )
                    conn.execute("COMMIT;")

        self._with_retry(f"save record {record.gid}", write)

    def load_records(self) -> dict[str, CRDTRecord]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT gid, payload, clock, node_id, deleted, ts FROM records"
                ).fetchall()

        records: dict[str, CRDTRecord] = {}
        for row in rows:
            try:
                records[str(row["gid"])] = CRDTRecord(
                    gid=str(row["gid"]),
                    payload=self._loads(str(row["payload"])),
                    clock=int(row["clock"]),
                    node_id=str(row["node_id"]),
                    deleted=bool(row["deleted"]),
                    ts=float(row["ts"]),
                )
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                logger.error("Skipping malformed CRDT record row: %s row=%r", exc, dict(row))

        return records

    def load_vv(self) -> VersionVector:
        vv = VersionVector()

        with self._lock:
            with self._connect() as conn:
                rows = conn.execute("SELECT node_id, clock FROM version_vector").fetchall()

        for row in rows:
            vv.observe(str(row["node_id"]), int(row["clock"]))

        return vv

    def save_vv(self, vv: VersionVector) -> None:
        def write() -> None:
            with self._lock:
                with self._connect() as conn:
                    conn.execute("BEGIN IMMEDIATE;")
                    for node_id, clock in vv.clocks.items():
                        conn.execute(
                            """
                            INSERT INTO version_vector(node_id, clock)
                            VALUES(?,?)
                            ON CONFLICT(node_id) DO UPDATE SET clock=excluded.clock
                            """,
                            (str(node_id), int(clock)),
                        )
                    conn.execute("COMMIT;")

        self._with_retry("save version vector", write)

    def save_snapshot(self, key: str, data: bytes) -> None:
        clean_key = str(key or "").strip()
        if not clean_key:
            raise ValueError("snapshot key cannot be empty")

        def write() -> None:
            with self._lock:
                with self._connect() as conn:
                    conn.execute("BEGIN IMMEDIATE;")
                    conn.execute(
                        """
                        INSERT INTO memory_snapshots(key, data, updated_at)
                        VALUES(?,?,?)
                        ON CONFLICT(key) DO UPDATE SET
                            data=excluded.data,
                            updated_at=excluded.updated_at
                        """,
                        (clean_key, data, time.time()),
                    )
                    conn.execute("COMMIT;")

        self._with_retry(f"save snapshot {clean_key}", write)

    def load_snapshot(self, key: str) -> Optional[bytes]:
        clean_key = str(key or "").strip()
        if not clean_key:
            return None

        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT data FROM memory_snapshots WHERE key = ?",
                    (clean_key,),
                ).fetchone()

        if row is None:
            return None

        return row["data"]

    def compact(self) -> None:
        """Run lightweight SQLite maintenance."""
        def write() -> None:
            with self._lock:
                with self._connect() as conn:
                    conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                    conn.execute("VACUUM;")

        self._with_retry("compact CRDT storage", write)


class GenomeCRDT:
    """Operation-based LWW CRDT for genome records."""

    def __init__(self, node_id: str, storage: Optional[CRDTStorage] = None) -> None:
        clean_node_id = str(node_id or "").strip()
        if not clean_node_id:
            raise ValueError("node_id cannot be empty")

        self.node_id: Final[str] = clean_node_id
        self.clock = 0
        self.vv = VersionVector()
        self.storage = storage
        self._lock = threading.RLock()

        self._records: dict[str, CRDTRecord] = {}
        self._seen_ops: set[str] = set()

        if self.storage is not None:
            self._bootstrap_from_storage()
        else:
            logger.warning("GenomeCRDT initialized without persistent storage.")
            self._next_clock()

    def _bootstrap_from_storage(self) -> None:
        with self._lock:
            try:
                if self.storage is None:
                    return

                self._records = self.storage.load_records()
                self.vv = self.storage.load_vv()

                for op in self.storage.load_ops():
                    self._seen_ops.add(op.op_id)
                    self.clock = max(self.clock, int(op.clock))
                    self.vv.observe(op.node_id, op.clock)

                if self.clock <= 0 or not self.vv.seen(self.node_id, self.clock):
                    self._next_clock()

                logger.info(
                    "CRDT bootstrapped: records=%s seen_ops=%s clock=%s vv=%s",
                    len(self._records),
                    len(self._seen_ops),
                    self.clock,
                    self.vv.to_dict(),
                )
            except Exception as exc:
                logger.error("Failed to bootstrap CRDT from storage: %s. Starting empty.", exc)
                self._records = {}
                self._seen_ops = set()
                self.vv = VersionVector()
                self.clock = 0
                self._next_clock()

    def refresh_from_storage(self) -> int:
        """Refresh in-memory CRDT state from persistent storage.

        This is useful for local multi-process runtime where several CRDTAdapter
        instances write to the same SQLite database. It imports operations that
        were written by other processes after this object was initialized.

        Returns:
            Number of newly observed operations.
        """
        if self.storage is None:
            return 0

        refreshed = 0

        with self._lock:
            try:
                storage_records = self.storage.load_records()
                storage_vv = self.storage.load_vv()
                storage_ops = self.storage.load_ops()

                before_seen = len(self._seen_ops)

                for op in storage_ops:
                    self._seen_ops.add(op.op_id)
                    self.clock = max(self.clock, int(op.clock))
                    self.vv.observe(op.node_id, op.clock)

                self._records = storage_records
                self.vv.merge(storage_vv)

                if self.clock <= 0 or not self.vv.seen(self.node_id, self.clock):
                    self._next_clock()

                refreshed = max(0, len(self._seen_ops) - before_seen)

                logger.debug(
                    "CRDT refreshed from storage: records=%s new_ops=%s clock=%s vv=%s",
                    len(self._records),
                    refreshed,
                    self.clock,
                    self.vv.to_dict(),
                )
            except Exception:
                logger.exception("Failed to refresh CRDT from storage.")
                return 0

        return refreshed

    def _next_clock(self) -> int:
        self.clock += 1
        self.vv.observe(self.node_id, self.clock)
        return self.clock

    @staticmethod
    def _clean_gid(gid: str) -> str:
        clean_gid = str(gid or "").strip()
        if not clean_gid:
            raise ValueError("gid cannot be empty")
        return clean_gid

    def _should_apply(self, current: Optional[CRDTRecord], op: CRDTOperation) -> bool:
        if current is None:
            return True
        if op.clock > current.clock:
            return True
        if op.clock < current.clock:
            return False
        return op.node_id > current.node_id

    def _apply_op(self, op: CRDTOperation) -> bool:
        with self._lock:
            self.vv.observe(op.node_id, op.clock)

            if op.op_id in self._seen_ops:
                if self.storage is not None:
                    self.storage.save_op(op)
                    self.storage.save_vv(self.vv)
                return False

            self._seen_ops.add(op.op_id)
            current = self._records.get(op.gid)
            changed = self._should_apply(current, op)

            if changed:
                if op.kind == OPERATION_KIND_DELETE:
                    self._records[op.gid] = CRDTRecord(
                        gid=op.gid,
                        payload={},
                        clock=op.clock,
                        node_id=op.node_id,
                        deleted=True,
                        ts=op.ts,
                    )
                elif op.kind == OPERATION_KIND_UPSERT:
                    self._records[op.gid] = CRDTRecord(
                        gid=op.gid,
                        payload=dict(op.payload),
                        clock=op.clock,
                        node_id=op.node_id,
                        deleted=False,
                        ts=op.ts,
                    )
                else:
                    logger.error("Unknown operation kind %r for op_id=%s", op.kind, op.op_id)
                    changed = False

            if self.storage is not None:
                self.storage.save_op(op)
                if changed and op.gid in self._records:
                    self.storage.save_record(self._records[op.gid])
                self.storage.save_vv(self.vv)

            return changed

    def upsert(
        self,
        gid: str,
        payload: dict[str, Any],
        op_id: Optional[str] = None,
    ) -> CRDTOperation:
        clean_gid = self._clean_gid(gid)
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dict")

        with self._lock:
            op = CRDTOperation(
                op_id=str(op_id or uuid.uuid4()),
                node_id=self.node_id,
                clock=self._next_clock(),
                kind=OPERATION_KIND_UPSERT,
                gid=clean_gid,
                payload=dict(payload),
                ts=time.time(),
            )
            self._apply_op(op)
            return op

    def delete(self, gid: str, op_id: Optional[str] = None) -> CRDTOperation:
        clean_gid = self._clean_gid(gid)

        with self._lock:
            op = CRDTOperation(
                op_id=str(op_id or uuid.uuid4()),
                node_id=self.node_id,
                clock=self._next_clock(),
                kind=OPERATION_KIND_DELETE,
                gid=clean_gid,
                payload={},
                ts=time.time(),
            )
            self._apply_op(op)
            return op

    def merge(self, remote_ops: Iterable[dict[str, Any] | CRDTOperation]) -> int:
        applied = 0

        with self._lock:
            for item in remote_ops:
                try:
                    op = item if isinstance(item, CRDTOperation) else CRDTOperation.from_dict(item)
                    if self._apply_op(op):
                        applied += 1
                except (TypeError, ValueError, KeyError) as exc:
                    logger.error("Skipping malformed remote CRDT operation: %s item=%r", exc, item)

        return applied

    def get(self, gid: str) -> Optional[dict[str, Any]]:
        clean_gid = str(gid or "").strip()
        if not clean_gid:
            return None

        with self._lock:
            record = self._records.get(clean_gid)
            if record is None or record.deleted:
                return None
            return dict(record.payload)

    def state(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {
                gid: dict(record.payload)
                for gid, record in self._records.items()
                if not record.deleted
            }

    def tombstones(self) -> list[str]:
        with self._lock:
            return [gid for gid, record in self._records.items() if record.deleted]

    def delta_since(self, other_vv: VersionVector | dict[str, int]) -> list[dict[str, Any]]:
        vv = VersionVector.from_dict(other_vv) if isinstance(other_vv, dict) else other_vv

        with self._lock:
            return [
                op.to_dict()
                for op in self._load_ops_for_delta()
                if not vv.seen(op.node_id, op.clock)
            ]

    def _load_ops_for_delta(self) -> list[CRDTOperation]:
        if self.storage is not None:
            return self.storage.load_ops()

        ops: list[CRDTOperation] = []
        for record in self._records.values():
            payload_json = json.dumps(
                record.payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                default=str,
            )
            seed = (
                f"{record.gid}|{record.node_id}|{record.clock}|"
                f"{record.ts}|{record.deleted}|{payload_json}"
            )
            ops.append(
                CRDTOperation(
                    op_id=str(uuid.uuid5(uuid.NAMESPACE_DNS, seed)),
                    node_id=record.node_id,
                    clock=record.clock,
                    kind=OPERATION_KIND_DELETE if record.deleted else OPERATION_KIND_UPSERT,
                    gid=record.gid,
                    payload=dict(record.payload),
                    ts=record.ts,
                )
            )

        ops.sort(key=lambda op: (op.ts, op.clock, op.node_id, op.op_id))
        return ops

    def compact(self) -> None:
        if self.storage is not None:
            self.storage.compact()