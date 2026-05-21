# src/core/event_store.py
"""
Append-only event store backed by JSONL with optional SQLite index.
"""
from __future__ import annotations

import json
import sqlite3
import logging
from pathlib import Path
from typing import Iterable, List, Optional, Union

from .events import Event # Assuming Event class is defined elsewhere and imported

# Configure logging for this module
logger = logging.getLogger(__name__)


class EventStore:
    """
    Append-only event store that persists events to a JSONL file (ledger).
    Additionally, it can maintain an SQLite index for faster querying.

    Events are stored one per line in the JSONL ledger. If an SQLite path is
    provided, an SQLite database is maintained to index events for quicker
    retrieval by properties like type, node ID, or timestamp.
    """

    ledger_path: Path
    sqlite_path: Optional[Path]

    def __init__(self, ledger_path: Union[str, Path], sqlite_path: Union[str, Path, None] = None) -> None:
        """
        Initializes the EventStore.

        Args:
            ledger_path: The path to the JSONL file where events will be appended.
                         Parent directories will be created if they do not exist.
            sqlite_path: Optional. The path to the SQLite database file to be used
                         as an index. If provided, parent directories will be created,
                         and the database schema will be initialized.

        Raises:
            ValueError: If `ledger_path` is an empty string or `sqlite_path` is an empty string (if provided).
            TypeError: If `ledger_path` or `sqlite_path` are of unexpected types.
        """
        if not isinstance(ledger_path, (str, Path)):
            raise TypeError("ledger_path must be a string or pathlib.Path object.")
        self.ledger_path = Path(ledger_path)
        if not str(self.ledger_path).strip():
            raise ValueError("ledger_path cannot be empty.")

        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ledger directory '{self.ledger_path.parent}' ensured.")

        if sqlite_path is not None:
            if not isinstance(sqlite_path, (str, Path)):
                raise TypeError("sqlite_path must be a string, pathlib.Path object, or None.")
            self.sqlite_path = Path(sqlite_path)
            if not str(self.sqlite_path).strip():
                raise ValueError("sqlite_path cannot be an empty string if provided.")
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_sqlite()
        else:
            self.sqlite_path = None
            logger.debug("EventStore initialized without SQLite index.")

    def __repr__(self) -> str:
        """
        Returns a string representation of the EventStore instance.
        """
        sqlite_str = f"'{self.sqlite_path}'" if self.sqlite_path else "None"
        return f"EventStore(ledger_path='{self.ledger_path}', sqlite_path={sqlite_str})"

    def _init_sqlite(self) -> None:
        """
        Initializes the SQLite database schema if an SQLite path is provided.
        This method creates the 'events' table and necessary indices if they don't exist.

        Raises:
            RuntimeError: If SQLite path is not configured when this method is called.
            sqlite3.Error: If there's an issue connecting to or initializing the SQLite database.
        """
        if self.sqlite_path is None:
            # This check is defensive; _init_sqlite is only called if sqlite_path exists.
            logger.error("Attempted to initialize SQLite without a configured path.")
            raise RuntimeError("SQLite path is not configured for EventStore.")

        try:
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
            logger.info(f"SQLite database schema initialized at '{self.sqlite_path}'.")
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize SQLite database at '{self.sqlite_path}': {e}")
            raise

    def append(self, event: Event) -> None:
        """
        Appends a new event to the JSONL ledger and, if configured,
        inserts it into the SQLite index.

        Args:
            event: The Event object to append.

        Raises:
            TypeError: If `event` is not an instance of `Event`.
            ValueError: If event hash verification fails, indicating a corrupted or invalid event.
            IOError: If there's an issue writing to the ledger file.
            sqlite3.Error: If there's an issue inserting into the SQLite index.
        """
        if not isinstance(event, Event):
            raise TypeError(f"Expected an 'Event' object, but got {type(event).__name__}.")

        if not event.verify_hash():
            logger.error(f"Event hash verification failed for event_id: {event.event_id}. Event details: {event.to_dict()}")
            raise ValueError(f"Event hash verification failed for event_id: {event.event_id}.")

        line: str = json.dumps(event.to_dict(), ensure_ascii=False)
        try:
            with self.ledger_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
            logger.debug(f"Event '{event.event_id}' appended to ledger '{self.ledger_path}'.")
        except IOError as e:
            logger.error(f"Failed to write event '{event.event_id}' to ledger '{self.ledger_path}': {e}")
            raise

        if self.sqlite_path:
            try:
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
                logger.debug(f"Event '{event.event_id}' inserted/replaced in SQLite index at '{self.sqlite_path}'.")
            except sqlite3.Error as e:
                logger.error(f"Failed to insert event '{event.event_id}' into SQLite index at '{self.sqlite_path}': {e}")
                raise

    def iter_events(self) -> Iterable[Event]:
        """
        Iterates through all events stored in the JSONL ledger file.
        Lines that cannot be parsed as valid JSON or Event objects are skipped,
        with a warning logged.

        Yields:
            Event: An Event object for each valid line in the ledger.

        Raises:
            IOError: If there's a critical issue reading the ledger file.
        """
        if not self.ledger_path.exists():
            logger.info(f"Ledger file '{self.ledger_path}' does not exist. No events to iterate.")
            return
        if not self.ledger_path.is_file():
            logger.error(f"Ledger path '{self.ledger_path}' is not a file or is inaccessible. Cannot iterate events.")
            return
        
        try:
            with self.ledger_path.open("r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event_dict = json.loads(line)
                        yield Event.from_dict(event_dict)
                    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
                        logger.warning(
                            f"Skipping malformed event line {line_num} in ledger '{self.ledger_path}': "
                            f"Content: '{line[:100]}{'...' if len(line) > 100 else ''}'. Error: {e}",
                            exc_info=False # No need for full traceback for each malformed line
                        )
                        continue
        except IOError as e:
            logger.error(f"Error reading ledger file '{self.ledger_path}': {e}")
            raise # Re-raise if file itself cannot be read, indicating a critical issue.

    def tail(self, n: int = 100) -> List[Event]:
        """
        Retrieves the last 'n' events from the ledger.

        Note: This method reads all events into memory before extracting the tail.
        For very large ledgers, this can be memory-intensive. For production systems
        with extremely large ledgers, a more optimized approach (e.g., reading from
        the end of the file) might be necessary.

        Args:
            n: The number of events to retrieve from the end of the ledger.
               If n is 0 or negative, an empty list is returned.

        Returns:
            A list containing the last 'n' events.

        Raises:
            ValueError: If `n` is not a non-negative integer.
        """
        if not isinstance(n, int) or n < 0:
            raise ValueError("n must be a non-negative integer.")
        if n == 0:
            return []
        events_list: List[Event] = list(self.iter_events()) # Renamed to avoid shadowing 'events'
        return events_list[-n:]

    def get_by_type(self, event_type: str) -> List[Event]:
        """
        Retrieves all events of a specific type.
        This method will use the SQLite index if available; otherwise, it iterates
        through the entire JSONL ledger, which can be slow for large ledgers.

        Args:
            event_type: The type of events to filter by.

        Returns:
            A list of Event objects matching the specified type.

        Raises:
            ValueError: If `event_type` is an empty string.
            sqlite3.Error: If there's an issue querying the SQLite index.
        """
        if not isinstance(event_type, str) or not event_type.strip():
            raise ValueError("event_type must be a non-empty string.")
        
        cleaned_event_type = event_type.strip()

        if self.sqlite_path:
            try:
                with sqlite3.connect(self.sqlite_path) as conn:
                    cursor = conn.execute("SELECT payload_json FROM events WHERE type = ?", (cleaned_event_type,))
                    events_list: List[Event] = [] # Renamed to events_list to avoid conflict with outer scope
                    for row in cursor.fetchall():
                        try:
                            events_list.append(Event.from_dict(json.loads(row[0])))
                        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
                            logger.warning(
                                f"Skipping malformed event from SQLite index for type '{cleaned_event_type}': "
                                f"Content: '{row[0][:100]}{'...' if len(row[0]) > 100 else ''}'. Error: {e}",
                                exc_info=False
                            )
                            continue
                    return events_list
            except sqlite3.Error as e:
                logger.error(f"Failed to query events by type '{cleaned_event_type}' from SQLite index at '{self.sqlite_path}': {e}")
                raise # Re-raise on SQLite error as it indicates a problem with the index itself.
        else:
            logger.info(f"SQLite not configured. Falling back to iterating ledger for type '{cleaned_event_type}'.")
            return [e for e in self.iter_events() if e.type == cleaned_event_type]

    def get_by_node(self, node_id: str) -> List[Event]:
        """
        Retrieves all events originating from a specific node ID.
        This method will use the SQLite index if available; otherwise, it iterates
        through the entire JSONL ledger, which can be slow for large ledgers.

        Args:
            node_id: The ID of the node to filter events by.

        Returns:
            A list of Event objects originating from the specified node.

        Raises:
            ValueError: If `node_id` is an empty string.
            sqlite3.Error: If there's an issue querying the SQLite index.
        """
        if not isinstance(node_id, str) or not node_id.strip():
            raise ValueError("node_id must be a non-empty string.")
        
        cleaned_node_id = node_id.strip()

        if self.sqlite_path:
            try:
                with sqlite3.connect(self.sqlite_path) as conn:
                    cursor = conn.execute("SELECT payload_json FROM events WHERE node_id = ?", (cleaned_node_id,))
                    events_list: List[Event] = [] # Renamed to events_list
                    for row in cursor.fetchall():
                        try:
                            events_list.append(Event.from_dict(json.loads(row[0])))
                        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
                            logger.warning(
                                f"Skipping malformed event from SQLite index for node '{cleaned_node_id}': "
                                f"Content: '{row[0][:100]}{'...' if len(row[0]) > 100 else ''}'. Error: {e}",
                                exc_info=False
                            )
                            continue
                    return events_list
            except sqlite3.Error as e:
                logger.error(f"Failed to query events by node '{cleaned_node_id}' from SQLite index at '{self.sqlite_path}': {e}")
                raise
        else:
            logger.info(f"SQLite not configured. Falling back to iterating ledger for node '{cleaned_node_id}'.")
            return [e for e in self.iter_events() if e.node_id == cleaned_node_id]

    def replay(self, since_ts: Optional[float] = None) -> Iterable[Event]:
        """
        Replays events from the ledger, optionally starting from a given timestamp.
        If an SQLite index is available, it will use the index for `since_ts` queries
        for efficiency. Otherwise, it iterates through the JSONL ledger.

        Args:
            since_ts: An optional timestamp (Unix epoch float). If provided,
                      only events with a timestamp greater than or equal to this
                      value will be yielded.

        Yields:
            Event: Events from the ledger that match the replay criteria.

        Raises:
            ValueError: If `since_ts` is provided but is not a non-negative float/integer.
            sqlite3.Error: If there's an issue querying the SQLite index.
        """
        if since_ts is not None and (not isinstance(since_ts, (int, float)) or since_ts < 0):
            raise ValueError("since_ts must be a non-negative float or integer, or None.")

        if self.sqlite_path and since_ts is not None:
            logger.debug(f"Replaying events from SQLite index since timestamp '{since_ts}'.")
            try:
                with sqlite3.connect(self.sqlite_path) as conn:
                    cursor = conn.execute("SELECT payload_json FROM events WHERE ts >= ? ORDER BY ts", (since_ts,))
                    for row in cursor:
                        try:
                            yield Event.from_dict(json.loads(row[0]))
                        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
                            logger.warning(
                                f"Skipping malformed event from SQLite index during replay (ts >= {since_ts}): "
                                f"Content: '{row[0][:100]}{'...' if len(row[0]) > 100 else ''}'. Error: {e}",
                                exc_info=False
                            )
                            continue
            except sqlite3.Error as e:
                logger.error(f"Failed to replay events from SQLite index since timestamp '{since_ts}' at '{self.sqlite_path}': {e}")
                # Re-raise on SQLite error to indicate a problem with the index itself.
                raise
        else:
            logger.debug(f"Replaying events from ledger (since_ts: {since_ts}).")
            # If since_ts is None, iterate all events. If provided but SQLite is not used, filter during iteration.
            for event in self.iter_events():
                # Assuming Event.ts is available and comparable (float timestamp). The Event class should ensure 'ts' is always a float.
                if since_ts is None or event.ts >= since_ts:
                    yield event