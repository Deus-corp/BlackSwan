"""Append-only event store backed by JSONL with an optional SQLite index."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from collections import deque
from pathlib import Path
from typing import Iterable, Optional

from .events import Event

logger = logging.getLogger(__name__)

SQLITE_TIMEOUT_SECONDS = 30.0
SQLITE_BUSY_TIMEOUT_MS = 30_000
SQLITE_WRITE_RETRIES = 6
SQLITE_WRITE_RETRY_DELAY_SECONDS = 0.05


class EventStore:
    """Append-only event ledger with optional SQLite indexing."""

    __slots__ = ("ledger_path", "sqlite_path", "_lock")

    def __init__(self, ledger_path: str | Path, sqlite_path: str | Path | None = None) -> None:
        self.ledger_path = self._clean_path(ledger_path, "ledger_path")
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

        self.sqlite_path: Optional[Path] = None
        if sqlite_path is not None:
            self.sqlite_path = self._clean_path(sqlite_path, "sqlite_path")
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.RLock()

        if self.sqlite_path is not None:
            self._init_sqlite()

    def __repr__(self) -> str:
        return f"EventStore(ledger_path={str(self.ledger_path)!r}, sqlite_path={str(self.sqlite_path)!r})"

    @staticmethod
    def _clean_path(value: str | Path, field_name: str) -> Path:
        if not isinstance(value, (str, Path)):
            raise TypeError(f"{field_name} must be a string or pathlib.Path")

        path = Path(value)
        if not str(path).strip():
            raise ValueError(f"{field_name} cannot be empty")

        return path

    def _connect(self) -> sqlite3.Connection:
        if self.sqlite_path is None:
            raise RuntimeError("SQLite index is not configured")

        conn = sqlite3.connect(
            str(self.sqlite_path),
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

    def _with_retry(self, label: str, operation):
        last_exc: Optional[BaseException] = None

        for attempt in range(SQLITE_WRITE_RETRIES):
            try:
                return operation()
            except sqlite3.OperationalError as exc:
                last_exc = exc
                if not self._is_locked_error(exc) or attempt >= SQLITE_WRITE_RETRIES - 1:
                    logger.error("SQLite error during %s: %s", label, exc)
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
    def _event_to_json(event: Event) -> str:
        return json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _payload_to_json(event: Event) -> str:
        return json.dumps(event.payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

    @staticmethod
    def _event_from_json(raw: str) -> Event:
        return Event.from_dict(json.loads(raw))

    def _init_sqlite(self) -> None:
        def write() -> None:
            with self._lock:
                with self._connect() as conn:
                    conn.execute("BEGIN IMMEDIATE;")
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS events (
                            event_id TEXT PRIMARY KEY NOT NULL,
                            ts REAL NOT NULL,
                            node_id TEXT NOT NULL,
                            type TEXT NOT NULL,
                            parent_id TEXT,
                            hash TEXT NOT NULL,
                            event_json TEXT NOT NULL,
                            payload_json TEXT NOT NULL
                        ) STRICT
                        """
                    )

                    columns = {
                        row["name"]
                        for row in conn.execute("PRAGMA table_info(events)").fetchall()
                    }
                    if "event_json" not in columns:
                        conn.execute("ALTER TABLE events ADD COLUMN event_json TEXT NOT NULL DEFAULT '{}';")

                    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_node ON events(node_id);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_parent ON events(parent_id);")
                    conn.execute("COMMIT;")

        self._with_retry("initialize event store sqlite", write)
        logger.info("SQLite database schema initialized at %r.", str(self.sqlite_path))

    def append(self, event: Event) -> None:
        """Append an event to JSONL and optional SQLite index."""
        if not isinstance(event, Event):
            raise TypeError(f"Expected Event, got {type(event).__name__}")

        if not event.verify_hash():
            logger.error("Event hash verification failed: event_id=%s", event.event_id)
            raise ValueError(f"Event hash verification failed for event_id={event.event_id}")

        event_json = self._event_to_json(event)

        with self._lock:
            with self.ledger_path.open("a", encoding="utf-8") as file:
                file.write(event_json + "\n")

        if self.sqlite_path is not None:
            self._index_event(event, event_json)

    def _index_event(self, event: Event, event_json: str) -> None:
        payload_json = self._payload_to_json(event)

        def write() -> None:
            with self._lock:
                with self._connect() as conn:
                    conn.execute("BEGIN IMMEDIATE;")
                    conn.execute(
                        """
                        INSERT INTO events(event_id, ts, node_id, type, parent_id, hash, event_json, payload_json)
                        VALUES(?,?,?,?,?,?,?,?)
                        ON CONFLICT(event_id) DO UPDATE SET
                            ts=excluded.ts,
                            node_id=excluded.node_id,
                            type=excluded.type,
                            parent_id=excluded.parent_id,
                            hash=excluded.hash,
                            event_json=excluded.event_json,
                            payload_json=excluded.payload_json
                        """,
                        (
                            event.event_id,
                            float(event.ts),
                            str(event.node_id),
                            str(event.type),
                            event.parent_id,
                            str(event.hash),
                            event_json,
                            payload_json,
                        ),
                    )
                    conn.execute("COMMIT;")

        self._with_retry(f"index event {event.event_id}", write)

    def iter_events(self) -> Iterable[Event]:
        """Iterate valid events from the JSONL ledger."""
        if not self.ledger_path.exists() or not self.ledger_path.is_file():
            return

        with self.ledger_path.open("r", encoding="utf-8") as file:
            for line_num, line in enumerate(file, 1):
                raw = line.strip()
                if not raw:
                    continue

                try:
                    yield self._event_from_json(raw)
                except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                    logger.warning(
                        "Skipping malformed event line %s in %s: %s",
                        line_num,
                        self.ledger_path,
                        exc,
                    )

    def tail(self, n: int = 100) -> list[Event]:
        """Return the last n valid events from the JSONL ledger."""
        if not isinstance(n, int) or n < 0:
            raise ValueError("n must be a non-negative integer")
        if n == 0:
            return []

        buffer: deque[Event] = deque(maxlen=n)
        for event in self.iter_events():
            buffer.append(event)

        return list(buffer)

    def get_by_type(self, event_type: str) -> list[Event]:
        """Return events matching a type."""
        clean_type = self._clean_text(event_type, "event_type")

        if self.sqlite_path is None:
            return [event for event in self.iter_events() if event.type == clean_type]

        return self._query_events("SELECT event_json, payload_json FROM events WHERE type = ? ORDER BY ts", (clean_type,))

    def get_by_node(self, node_id: str) -> list[Event]:
        """Return events emitted by node_id."""
        clean_node_id = self._clean_text(node_id, "node_id")

        if self.sqlite_path is None:
            return [event for event in self.iter_events() if event.node_id == clean_node_id]

        return self._query_events(
            "SELECT event_json, payload_json FROM events WHERE node_id = ? ORDER BY ts",
            (clean_node_id,),
        )

    def replay(self, since_ts: Optional[float] = None) -> Iterable[Event]:
        """Replay events from the ledger or SQLite index."""
        if since_ts is not None:
            since_ts = float(since_ts)
            if since_ts < 0:
                raise ValueError("since_ts must be non-negative")

        if self.sqlite_path is not None and since_ts is not None:
            for event in self._query_events(
                "SELECT event_json, payload_json FROM events WHERE ts >= ? ORDER BY ts",
                (since_ts,),
            ):
                yield event
            return

        for event in self.iter_events():
            if since_ts is None or event.ts >= since_ts:
                yield event

    def count(self) -> int:
        """Return event count."""
        if self.sqlite_path is not None:
            with self._lock:
                with self._connect() as conn:
                    row = conn.execute("SELECT COUNT(*) AS count FROM events").fetchone()
                    return int(row["count"]) if row else 0

        return sum(1 for _ in self.iter_events())

    def _query_events(self, sql: str, params: tuple[object, ...]) -> list[Event]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(sql, params).fetchall()

        events: list[Event] = []
        for row in rows:
            event = self._event_from_sqlite_row(row)
            if event is not None:
                events.append(event)

        return events

    def _event_from_sqlite_row(self, row: sqlite3.Row) -> Optional[Event]:
        try:
            event_json = row["event_json"] if "event_json" in row.keys() else None
            if event_json and event_json != "{}":
                return self._event_from_json(str(event_json))

            payload_json = row["payload_json"]
            payload = json.loads(payload_json)
            if isinstance(payload, dict) and {
                "event_id",
                "ts",
                "node_id",
                "type",
                "hash",
            }.issubset(payload):
                return Event.from_dict(payload)

            logger.warning("SQLite event row does not contain full event_json; skipping row.")
            return None

        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.warning("Skipping malformed SQLite event row: %s", exc)
            return None

    @staticmethod
    def _clean_text(value: str, field_name: str) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{field_name} must be a string")

        clean_value = value.strip()
        if not clean_value:
            raise ValueError(f"{field_name} cannot be empty")

        return clean_value