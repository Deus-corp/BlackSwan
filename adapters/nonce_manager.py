"""Async-safe Ethereum nonce management using SQLite WAL mode."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class NonceManager:
    """Manage account nonces with process-safe SQLite reservations."""

    DEFAULT_DB_PATH = "/app/nonce_data/nonce.db"
    BUSY_TIMEOUT_MS = 10_000
    CONNECT_TIMEOUT_SECONDS = 10.0
    MAX_LOCK_RETRIES = 8

    def __init__(self, account_address: str, db_path: Optional[str] = None) -> None:
        clean_address = str(account_address or "").strip().lower()
        if not clean_address:
            raise ValueError("account_address cannot be empty")

        self.account_address = clean_address

        if db_path is None:
            path = Path(self.DEFAULT_DB_PATH)
        else:
            path = Path(db_path)

        path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(path)

        self._init_db()
        logger.info("NonceManager ready for %s... | db=%s", self.account_address[:8], self.db_path)

    def _init_db(self) -> None:
        """Initialize SQLite schema and WAL-related pragmas."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS nonces (
                    address TEXT PRIMARY KEY,
                    nonce INTEGER NOT NULL DEFAULT 0,
                    last_updated REAL NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mutation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    old_params TEXT,
                    new_params TEXT,
                    context TEXT
                )
                """
            )
            conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """Return configured SQLite connection."""
        conn = sqlite3.connect(
            self.db_path,
            timeout=self.CONNECT_TIMEOUT_SECONDS,
            isolation_level=None,
        )
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute(f"PRAGMA busy_timeout={self.BUSY_TIMEOUT_MS};")
        return conn

    async def get_nonce_async(self, onchain_pending_nonce: int) -> int:
        """Reserve next nonce using provided on-chain pending nonce."""
        return await asyncio.to_thread(self._get_next_nonce, onchain_pending_nonce)

    def _get_next_nonce(self, onchain_nonce: int) -> int:
        """Synchronously reserve next safe nonce."""
        safe_onchain = self._non_negative_int(onchain_nonce, "onchain_nonce")
        return self._reserve_from_onchain_nonce(safe_onchain)

    async def update_nonce_async(self, transaction_info: dict[str, Any]) -> Optional[int]:
        """Advance stored nonce from a successful transaction receipt/info dict."""
        return await asyncio.to_thread(self._update_nonce, transaction_info)

    def _update_nonce(self, transaction_info: dict[str, Any]) -> Optional[int]:
        """Synchronously advance stored nonce from transaction info."""
        if not isinstance(transaction_info, dict):
            logger.debug("Ignoring malformed transaction_info: %r", transaction_info)
            return None

        if transaction_info.get("status") != 1:
            logger.debug("Transaction info does not indicate success: %s", transaction_info)
            return None

        if "nonce" not in transaction_info or transaction_info.get("nonce") is None:
            logger.warning("Successful transaction info without nonce: %s", transaction_info)
            return None

        tx_nonce = self._non_negative_int(transaction_info.get("nonce"), "nonce")
        new_next_nonce = tx_nonce + 1

        def _op(conn: sqlite3.Connection) -> int:
            self._ensure_row(conn, initial_nonce=0)
            current_db_nonce = self._read_nonce(conn)

            if new_next_nonce > current_db_nonce:
                self._write_nonce(conn, new_next_nonce)
                logger.debug(
                    "Nonce for %s... updated to %s from successful tx nonce %s.",
                    self.account_address[:8],
                    new_next_nonce,
                    tx_nonce,
                )
                return new_next_nonce

            logger.debug(
                "No nonce update needed for tx nonce %s; db nonce=%s.",
                tx_nonce,
                current_db_nonce,
            )
            return current_db_nonce

        return self._with_immediate_transaction(_op)

    async def sync_with_chain_async(self, onchain_pending: int) -> None:
        """Synchronize stored nonce with on-chain pending nonce."""
        await asyncio.to_thread(self._sync_with_chain, onchain_pending)

    def _sync_with_chain(self, onchain_nonce: int) -> None:
        """Synchronously set stored nonce to on-chain pending nonce."""
        safe_onchain = self._non_negative_int(onchain_nonce, "onchain_nonce")

        def _op(conn: sqlite3.Connection) -> None:
            self._write_nonce(conn, safe_onchain)

        self._with_immediate_transaction(_op)
        logger.info("Nonce for %s... synced with chain: %s", self.account_address[:8], safe_onchain)

    async def reserve_nonce(self, w3: Any) -> int:
        """Fetch pending nonce from chain and atomically reserve next local nonce."""
        if w3 is None:
            raise ValueError("w3 is required")

        checksum_address = w3.to_checksum_address(self.account_address)

        last_error: Exception | None = None
        for attempt in range(self.MAX_LOCK_RETRIES):
            try:
                onchain_pending = await w3.eth.get_transaction_count(checksum_address, "pending")
                safe_onchain = self._non_negative_int(onchain_pending, "onchain_pending")
                return self._reserve_from_onchain_nonce(safe_onchain)

            except sqlite3.OperationalError as exc:
                last_error = exc
                if "database is locked" not in str(exc).lower():
                    raise
                delay = min(0.05 * (2**attempt), 1.0)
                logger.debug("Nonce DB locked; retrying in %.3fs.", delay)
                await asyncio.sleep(delay)

        raise RuntimeError("failed to reserve nonce after retries") from last_error

    async def record_mutation_async(
        self,
        *,
        node_id: str,
        old_params: dict[str, Any] | None = None,
        new_params: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> int:
        """Record mutation metadata in the nonce DB auxiliary history table."""
        return await asyncio.to_thread(
            self.record_mutation,
            node_id=node_id,
            old_params=old_params,
            new_params=new_params,
            context=context,
        )

    def record_mutation(
        self,
        *,
        node_id: str,
        old_params: dict[str, Any] | None = None,
        new_params: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> int:
        """Record mutation metadata and return inserted row id."""
        clean_node_id = str(node_id or "").strip()
        if not clean_node_id:
            raise ValueError("node_id cannot be empty")

        with self._get_connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO mutation_history (node_id, timestamp, old_params, new_params, context)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    clean_node_id,
                    time.time(),
                    self._json(old_params or {}),
                    self._json(new_params or {}),
                    self._json(context or {}),
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def get_current_nonce(self) -> Optional[int]:
        """Return current stored next nonce for this account, if present."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT nonce FROM nonces WHERE address = ?", (self.account_address,))
            row = cur.fetchone()
            return int(row[0]) if row else None

    def _reserve_from_onchain_nonce(self, onchain_nonce: int) -> int:
        def _op(conn: sqlite3.Connection) -> int:
            self._ensure_row(conn, initial_nonce=onchain_nonce)
            db_nonce = self._read_nonce(conn)
            safe_nonce = max(onchain_nonce, db_nonce)
            self._write_nonce(conn, safe_nonce + 1)
            return safe_nonce

        return self._with_immediate_transaction(_op)

    def _with_immediate_transaction(self, fn: Any) -> Any:
        with self._get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE;")
                result = fn(conn)
                conn.commit()
                return result
            except Exception:
                conn.rollback()
                raise

    def _ensure_row(self, conn: sqlite3.Connection, *, initial_nonce: int) -> None:
        conn.execute(
            """
            INSERT OR IGNORE INTO nonces (address, nonce, last_updated)
            VALUES (?, ?, ?)
            """,
            (self.account_address, initial_nonce, time.time()),
        )

    def _read_nonce(self, conn: sqlite3.Connection) -> int:
        cur = conn.execute("SELECT nonce FROM nonces WHERE address = ?", (self.account_address,))
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("nonce row missing after initialization")
        return int(row[0])

    def _write_nonce(self, conn: sqlite3.Connection, nonce: int) -> None:
        safe_nonce = self._non_negative_int(nonce, "nonce")
        conn.execute(
            """
            INSERT INTO nonces (address, nonce, last_updated)
            VALUES (?, ?, ?)
            ON CONFLICT(address) DO UPDATE SET
                nonce = excluded.nonce,
                last_updated = excluded.last_updated
            """,
            (self.account_address, safe_nonce, time.time()),
        )

    @staticmethod
    def _non_negative_int(value: Any, name: str) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be a non-negative integer") from exc

        if number < 0 or not math.isfinite(float(number)):
            raise ValueError(f"{name} must be a non-negative integer")
        return number

    @staticmethod
    def _json(data: dict[str, Any]) -> str:
        return json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)