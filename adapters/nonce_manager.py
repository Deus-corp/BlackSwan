"""
NonceManager — async-safe nonce management using SQLite (WAL-mode).
Provides atomic nonce reservation and synchronization with on-chain nonces.
"""
import sqlite3
import time
import asyncio
import json
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger


class NonceManager:
    """
    Manages nonces for a given Ethereum account address in an async-safe manner
    using an SQLite database. Supports atomic nonce reservation and synchronization
    with the blockchain.
    """

    def __init__(self, account_address: str, db_path: Optional[str] = None):
        """
        Initializes the NonceManager.

        Args:
            account_address (str): The Ethereum account address for which to manage nonces.
            db_path (Optional[str]): Path to the SQLite database file. If None, it defaults
                                      to '/app/nonce_data/nonce.db'.
        """
        self.account_address: str = account_address.lower()
        if db_path is None:
            db_dir: Path = Path("/app/nonce_data")
            db_dir.mkdir(parents=True, exist_ok=True)
            self.db_path: str = str(db_dir / "nonce.db")
        else:
            self.db_path: str = db_path
        self._init_db()
        logger.info(f"NonceManager ready for {self.account_address[:8]}... | db={self.db_path}")

    def _init_db(self) -> None:
        """
        Initializes the SQLite database with necessary tables and PRAGMA settings.
        Sets journal_mode to WAL for better concurrency and busy_timeout for handling contention.
        """
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=5000;") # 5 seconds
            conn.execute("""
                CREATE TABLE IF NOT EXISTS nonces (
                    address TEXT PRIMARY KEY,
                    nonce INTEGER DEFAULT 0,
                    last_updated REAL DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mutation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id TEXT,
                    timestamp REAL,
                    old_params TEXT,
                    new_params TEXT,
                    context TEXT
                )
            """)
            conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """
        Returns a new SQLite database connection with a specified timeout.

        Returns:
            sqlite3.Connection: An SQLite database connection object.
        """
        return sqlite3.connect(self.db_path, timeout=8)

    async def get_nonce_async(self, onchain_pending_nonce: int) -> int:
        """
        Asynchronously retrieves a safe nonce, which is the maximum of the provided
        on-chain pending nonce and the stored database nonce, then increments it for future use.
        This method is less atomic for concurrent processes than `reserve_nonce`.

        Args:
            onchain_pending_nonce (int): The current pending transaction count for the account on-chain.

        Returns:
            int: The safe nonce to use for the next transaction.
        """
        return await asyncio.to_thread(self._get_next_nonce, onchain_pending_nonce)

    def _get_next_nonce(self, onchain_nonce: int) -> int:
        """
        Synchronously calculates the next safe nonce. It ensures the stored nonce
        is at least `onchain_nonce`, then updates the database to reflect the next available nonce.

        Args:
            onchain_nonce (int): The current pending transaction count for the account on-chain.

        Returns:
            int: The safe nonce to use for the next transaction.
        """
        with self._get_connection() as conn:
            # Ensure the address exists in the nonces table
            conn.execute("INSERT OR IGNORE INTO nonces (address, nonce, last_updated) VALUES (?, ?, ?)",
                         (self.account_address, onchain_nonce, time.time()))
            
            # Fetch current DB nonce
            cur = conn.execute("SELECT nonce FROM nonces WHERE address = ?", (self.account_address,))
            row = cur.fetchone()
            db_nonce: int = row[0] if row else onchain_nonce # Should always find a row due to INSERT OR IGNORE

            # The safe nonce is the maximum of what's on-chain and what's in DB
            safe_nonce: int = max(onchain_nonce, db_nonce)
            
            # Update the DB to the *next* available nonce
            conn.execute("UPDATE nonces SET nonce = ?, last_updated = ? WHERE address = ?",
                         (safe_nonce + 1, time.time(), self.account_address))
            conn.commit()
            return safe_nonce

    async def update_nonce_async(self, transaction_info: Dict[str, Any]) -> Optional[int]:
        """
        Asynchronously updates the stored nonce based on a successful transaction's information.
        This method is designed to confirm a transaction and ensure the database nonce
        is at least one greater than the successful transaction's nonce, only incrementing.

        Args:
            transaction_info (Dict[str, Any]): A dictionary containing transaction details.
                It *must* include 'status' (1 for success) and 'nonce' (the nonce of the transaction).

        Returns:
            Optional[int]: The new stored nonce if updated, or None if no update occurred
            (e.g., transaction not successful, nonce not found, or stored nonce is already higher).
        """
        return await asyncio.to_thread(self._update_nonce, transaction_info)

    def _update_nonce(self, transaction_info: Dict[str, Any]) -> Optional[int]:
        """
        Synchronously updates the stored nonce based on a successful transaction's information.
        This prevents the stored nonce from being decremented by an older receipt.

        Args:
            transaction_info (Dict[str, Any]): A dictionary containing transaction details.
                It *must* include 'status' (1 for success) and 'nonce' (the nonce of the transaction).

        Returns:
            Optional[int]: The new stored nonce if updated, or None if no update occurred.
        """
        if isinstance(transaction_info, dict) and transaction_info.get('status') == 1:
            tx_nonce: Optional[int] = transaction_info.get('nonce')
            if tx_nonce is not None:
                new_next_nonce: int = tx_nonce + 1
                with self._get_connection() as conn:
                    cur = conn.execute("SELECT nonce FROM nonces WHERE address = ?", (self.account_address,))
                    row = cur.fetchone()
                    # If address not found, initialize with new_next_nonce, otherwise get current DB nonce
                    current_db_nonce: int = row[0] if row else new_next_nonce

                    # Only update if the new_next_nonce is strictly greater than the current stored nonce
                    if new_next_nonce > current_db_nonce:
                        conn.execute("UPDATE nonces SET nonce = ?, last_updated = ? WHERE address = ?",
                                     (new_next_nonce, time.time(), self.account_address))
                        conn.commit()
                        logger.debug(f"Nonce for {self.account_address[:8]}... updated to {new_next_nonce} "
                                     f"based on successful tx nonce {tx_nonce}.")
                        return new_next_nonce
                    else:
                        logger.debug(f"No nonce update needed for tx nonce {tx_nonce}. "
                                     f"DB nonce for {self.account_address[:8]}... is already {current_db_nonce} or higher.")
                        return current_db_nonce # Return current DB nonce as it's already sufficiently high
            else:
                logger.warning(f"Transaction info dict provided without 'nonce' field for successful transaction: {transaction_info}")
                return None
        else:
            logger.debug(f"Transaction info does not indicate a successful transaction or is malformed: {transaction_info}")
            return None

    async def sync_with_chain_async(self, onchain_pending: int) -> None:
        """
        Asynchronously synchronizes the stored nonce with the latest on-chain pending nonce.
        This method will overwrite the stored nonce if the on-chain nonce is newer.

        Args:
            onchain_pending (int): The current pending transaction count for the account on-chain.
        """
        await asyncio.to_thread(self._sync_with_chain, onchain_pending)

    def _sync_with_chain(self, onchain_nonce: int) -> None:
        """
        Synchronously synchronizes the stored nonce with the latest on-chain pending nonce.
        """
        with self._get_connection() as conn:
            # INSERT OR REPLACE ensures the row exists and updates it if it does
            conn.execute("INSERT OR REPLACE INTO nonces (address, nonce, last_updated) VALUES (?, ?, ?)",
                         (self.account_address, onchain_nonce, time.time()))
            conn.commit()
        logger.info(f"Nonce for {self.account_address[:8]}... synced with chain: {onchain_nonce}")

    async def reserve_nonce(self, w3: Any) -> int:
        """
        Asynchronously and atomically reserves the next available nonce for the account.
        This method fetches the latest on-chain pending nonce, compares it with the
        database-stored nonce, and atomically increments the stored nonce before returning it.
        It uses optimistic locking to handle concurrent access.

        Args:
            w3 (Any): An instance of web3.py (web3.Web3) to query the blockchain.

        Returns:
            int: The unique nonce reserved for the next transaction.
        """
        checksum_address: str = w3.to_checksum_address(self.account_address)
        while True:
            # Get the current pending transaction count from the chain
            onchain_pending: int = await w3.eth.get_transaction_count(checksum_address, "pending")
            
            with self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE") # Start a transaction with immediate lock
                try:
                    # Fetch current nonce from DB
                    cur = conn.execute("SELECT nonce FROM nonces WHERE address = ?", (self.account_address,))
                    row = cur.fetchone()
                    # If no record, initialize with onchain_pending, otherwise use stored
                    db_nonce: int = row[0] if row else onchain_pending

                    # Determine the nonce to use: max of on-chain pending and DB-stored
                    use_nonce: int = max(onchain_pending, db_nonce)
                    next_nonce: int = use_nonce + 1

                    # Optimistic update: only update if the nonce in DB is still what we read (db_nonce)
                    conn.execute(
                        "UPDATE nonces SET nonce = ?, last_updated = ? WHERE address = ? AND nonce = ?",
                        (next_nonce, time.time(), self.account_address, db_nonce)
                    )

                    if conn.total_changes == 0:
                        # Another process/thread updated the nonce before us; rollback and retry
                        conn.rollback()
                        logger.debug(f"Conflict reserving nonce for {self.account_address[:8]}..., retrying...")
                        await asyncio.sleep(0.02) # Small delay before retrying
                        continue # Loop to try again
                    else:
                        conn.commit()
                        logger.debug(f"Reserved nonce {use_nonce} for {self.account_address[:8]}... Next in DB: {next_nonce}")
                        return use_nonce
                except Exception as e:
                    conn.rollback()
                    logger.exception(f"Error during nonce reservation for {self.account_address[:8]}...: {e}")
                    raise # Re-raise the exception after rollback
            
    def save_mutation(self, node_id: str, old_params: Dict[str, Any], new_params: Dict[str, Any], context: str) -> None:
        """
        Saves a record of a mutation (parameter change) to the mutation history table.

        Args:
            node_id (str): Identifier for the node or component where the mutation occurred.
            old_params (Dict[str, Any]): Dictionary of parameters before the mutation.
            new_params (Dict[str, Any]): Dictionary of parameters after the mutation.
            context (str): A descriptive string about the context of the mutation.
        """
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO mutation_history (node_id, timestamp, old_params, new_params, context) VALUES (?, ?, ?, ?, ?)",
                (node_id, time.time(), json.dumps(old_params), json.dumps(new_params), context)
            )
            conn.commit()
