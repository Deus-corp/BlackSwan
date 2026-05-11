"""
NonceManager — async-safe управление nonce через SQLite (WAL-режим).
"""
import sqlite3
import time
import asyncio
from pathlib import Path
from typing import Optional
from loguru import logger


class NonceManager:
    def __init__(self, account_address: str, db_path: Optional[str] = None):
        self.account_address = account_address.lower()
        if db_path is None:
            db_dir = Path("/app/nonce_data")
            db_dir.mkdir(parents=True, exist_ok=True)
            db_path = db_dir / "nonce.db"
        self.db_path = str(db_path)
        self._init_db()
        logger.info(f"NonceManager ready for {self.account_address[:8]}... | db={self.db_path}")

    def _init_db(self):
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS nonces (
                    address TEXT PRIMARY KEY,
                    nonce INTEGER DEFAULT 0,
                    last_updated REAL DEFAULT 0
                )
            """)
            conn.commit()

    def _get_connection(self):
        return sqlite3.connect(self.db_path, timeout=8)

    async def get_nonce_async(self, onchain_pending_nonce: int) -> int:
        """Возвращает безопасный nonce (max(onchain, db) + инкремент)."""
        return await asyncio.to_thread(self._get_next_nonce, onchain_pending_nonce)

    def _get_next_nonce(self, onchain_nonce: int) -> int:
        with self._get_connection() as conn:
            # атомарно читаем и увеличиваем
            conn.execute("INSERT OR IGNORE INTO nonces (address, nonce, last_updated) VALUES (?, ?, ?)",
                         (self.account_address, onchain_nonce, time.time()))
            cur = conn.execute("SELECT nonce FROM nonces WHERE address = ?", (self.account_address,))
            row = cur.fetchone()
            db_nonce = row[0] if row else onchain_nonce
            safe_nonce = max(onchain_nonce, db_nonce)
            conn.execute("UPDATE nonces SET nonce = ?, last_updated = ? WHERE address = ?",
                         (safe_nonce + 1, time.time(), self.account_address))
            conn.commit()
            return safe_nonce

    async def update_nonce_async(self, receipt_or_tx_hash):
        """Обновляет nonce по успешному receipt."""
        return await asyncio.to_thread(self._update_nonce, receipt_or_tx_hash)

    def _update_nonce(self, receipt_or_tx_hash) -> int:
        # Если передан хеш, получить receipt (но мы будем вызывать уже с receipt)
        # Для async-версии будем передавать receipt
        if isinstance(receipt_or_tx_hash, dict) and receipt_or_tx_hash.get('status') == 1:
            new_nonce = receipt_or_tx_hash['nonce'] + 1
            with self._get_connection() as conn:
                conn.execute("UPDATE nonces SET nonce = ?, last_updated = ? WHERE address = ?",
                             (new_nonce, time.time(), self.account_address))
                conn.commit()
            logger.debug(f"Nonce updated to {new_nonce}")
            return new_nonce
        return receipt_or_tx_hash.get('nonce', 0)

    async def sync_with_chain_async(self, onchain_pending: int):
        await asyncio.to_thread(self._sync_with_chain, onchain_pending)

    def _sync_with_chain(self, onchain_nonce: int):
        with self._get_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO nonces (address, nonce, last_updated) VALUES (?, ?, ?)",
                         (self.account_address, onchain_nonce, time.time()))
            conn.commit()
        logger.info(f"Nonce synced with chain: {onchain_nonce}")