# src/core/event_store.py
"""
Append-only event store backed by JSONL with optional SQLite index.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional
import json
import sqlite3

from .events import Event


class EventStore:
    """
    Append-only event store that persists events to a JSONL file (ledger).
    Optionally, it can maintain an SQLite index for faster querying.
    """

    def __init__(self, ledger_path: str | Path, sqlite_path: str | Path | None = None) -> None:
        self.ledger_path = Path(ledger_path)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

        self.sqlite_path = Path(sqlite_path) if sqlite_path else None
        if self.sqlite_path:
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_sqlite()

    def _init_sqlite(self) -> None:
        """Initializes the SQLite database schema if an SQLite path is provided."""
        assert self.sqlite_path is not None
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    ts REAL NOT NULL,
                    node_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    parent_id TEXT,
                    hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_node ON events(node_id)")
            conn.commit()

    def append(self, event: Event) -> None:
        """
        Appends a new event to the JSONL ledger and, if configured,
        inserts it into the SQLite index.

        Args:
            event: The Event object to append.
        """
        if not event.verify_hash():
            raise ValueError("Event hash verification failed.")

        line = json.dumps(event.to_dict(), ensure_ascii=False)
        with self.ledger_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

        if self.sqlite_path:
            with sqlite3.connect(self.sqlite_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO events
                    (event_id, ts, node_id, type, parent_id, hash, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.ts,
                        event.node_id,
                        event.type,
                        event.parent_id,
                        event.hash,
                        json.dumps(event.payload, ensure_ascii=False),
                    ),
                )
                conn.commit()

    def iter_events(self) -> Iterable[Event]:
        """
        Iterates through all events stored in the JSONL ledger file.

        Yields:
            Event: An Event object for each valid line in the ledger.
        """
        if not self.ledger_path.exists():
            return
        with self.ledger_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield Event.from_dict(json.loads(line))
                except Exception: # Broad exception catch for potentially malformed JSONL lines
                    continue

    def tail(self, n: int = 100) -> List[Event]:
        """
        Retrieves the last 'n' events from the ledger.
        Note: This method reads all events into memory before extracting the tail.

        Args:
            n: The number of events to retrieve from the end of the ledger.

        Returns:
            A list containing the last 'n' events.
        """
        events = list(self.iter_events())
        return events[-n:] if n > 0 else []

    def get_by_type(self, event_type: str) -> List[Event]:
        """
        Retrieves all events of a specific type by iterating through the ledger.

        Args:
            event_type: The type of events to filter by.

        Returns:
            A list of Event objects matching the specified type.
        """
        return [e for e in self.iter_events() if e.type == event_type]

    def get_by_node(self, node_id: str) -> List[Event]:
        """
        Retrieves all events originating from a specific node ID by iterating through the ledger.

        Args:
            node_id: The ID of the node to filter events by.

        Returns:
            A list of Event objects originating from the specified node.
        """
        return [e for e in self.iter_events() if e.node_id == node_id]

    def replay(self, since_ts: float | None = None) -> Iterable[Event]:
        """
        Replays events from the ledger, optionally starting from a given timestamp.

        Args:
            since_ts: An optional timestamp (Unix epoch float). If provided,
                      only events with a timestamp greater than or equal to this
                      value will be yielded.

        Yields:
            Event: Events from the ledger that match the replay criteria.
        """
        for event in self.iter_events():
            if since_ts is None or event.ts >= since_ts:
                yield event