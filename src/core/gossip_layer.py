from __future__ import annotations

"""
BlackSwan cluster gossip layer.

Features:
- persistent storage (SQLite)
- authenticated envelopes (HMAC)
- replay protection
- stale-message rejection
- configurable delta acceptance policy
- peer scoring and backoff
- deterministic last-write-wins merge
- aiohttp HTTP endpoints for node-to-node gossip

This module is intentionally self-contained for easier testing and reuse.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import random
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Deque, Dict, Iterable, Optional, Tuple

import aiohttp
from aiohttp import web

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


# =========================
# CONFIG
# =========================


@dataclass(frozen=True, slots=True)
class GossipConfig:
    """
    Configuration for the BlackSwan gossip layer.
    Settings are primarily sourced from environment variables, with sensible defaults.
    """

    node_id: str = field(default_factory=lambda: os.environ.get("NODE_ID", str(uuid.uuid4())))
    port: int = field(default_factory=lambda: int(os.environ.get("PORT", "8000")))
    bind_host: str = field(default_factory=lambda: os.environ.get("BIND_HOST", "0.0.0.0"))
    peers_csv: str = field(default_factory=lambda: os.environ.get("PEERS", ""))
    shared_secret: str = field(default_factory=lambda: os.environ.get("GOSSIP_SECRET", "dev-secret"))
    sqlite_path: str = field(default_factory=lambda: os.environ.get("GOSSIP_DB", "./gossip_state.sqlite3"))

    gossip_interval_s: float = field(default_factory=lambda: float(os.environ.get("GOSSIP_INTERVAL", "1.5")))
    request_timeout_s: float = field(default_factory=lambda: float(os.environ.get("REQUEST_TIMEOUT", "2.0")))
    max_clock_skew_s: float = field(default_factory=lambda: float(os.environ.get("MAX_CLOCK_SKEW", "15")))
    replay_cache_size: int = field(default_factory=lambda: int(os.environ.get("REPLAY_CACHE_SIZE", "2048")))
    max_state: int = field(default_factory=lambda: int(os.environ.get("MAX_STATE", "500")))
    ttl_s: int = field(default_factory=lambda: int(os.environ.get("TTL_SECONDS", "600")))
    min_fitness: float = field(default_factory=lambda: float(os.environ.get("MIN_FITNESS", "0.0")))

    @property
    def peers(self) -> list[str]:
        """Returns a list of peer URLs from the CSV string."""
        return [p.strip() for p in self.peers_csv.split(",") if p.strip()]

    @property
    def secret_bytes(self) -> bytes:
        """Returns the shared secret encoded as UTF-8 bytes."""
        return self.shared_secret.encode("utf-8")


# =========================
# DOMAIN MODELS
# =========================


@dataclass(slots=True)
class GenomeRecord:
    """
    Represents a single genome record to be gossiped across the cluster.
    Includes parameters, fitness, provenance, and versioning information.
    """

    gid: str
    params: Dict[str, float]
    fitness: float
    niche: str = "exploration"
    origin: str = ""
    lineage: list[str] = field(default_factory=list)
    ts: float = field(default_factory=time.time)
    ver: int = 0
    node: str = ""

    def to_public_dict(self) -> Dict[str, Any]:
        """
        Converts the GenomeRecord to a dictionary suitable for serialization
        and public sharing.
        """
        return {
            "gid": self.gid,
            "params": self.params,
            "fitness": self.fitness,
            "niche": self.niche,
            "origin": self.origin,
            "lineage": list(self.lineage),
            "ts": self.ts,
            "ver": self.ver,
            "node": self.node,
        }

    @staticmethod
    def from_dict(gid: str, data: Dict[str, Any]) -> Optional["GenomeRecord"]:
        """
        Creates a GenomeRecord instance from a dictionary.
        Performs basic validation and type conversion.

        Args:
            gid: The genome ID, which should be the primary identifier.
            data: A dictionary containing genome record data.

        Returns:
            A GenomeRecord instance if validation and conversion succeed,
            otherwise None.
        """
        if not isinstance(data, dict):
            logger.warning(f"Invalid data type for GenomeRecord.from_dict: {type(data)}")
            return None

        params_raw = data.get("params")
        if not isinstance(params_raw, dict):
            logger.warning(f"Invalid 'params' field type for GenomeRecord {gid}: {type(params_raw)}")
            return None

        clean_params: Dict[str, float] = {}
        for k, v in params_raw.items():
            try:
                clean_params[str(k)] = float(v)
            except (TypeError, ValueError):
                logger.warning(f"Could not convert param '{k}' with value '{v}' to float for GenomeRecord {gid}.")
                return None

        lineage_raw = data.get("lineage", [])
        if not isinstance(lineage_raw, list):
            logger.warning(f"Invalid 'lineage' field type for GenomeRecord {gid}: {type(lineage_raw)}")
            lineage_raw = []  # Default to empty list if invalid type

        lineage: list[str] = [str(x) for x in lineage_raw if x is not None] # Convert all elements to string

        try:
            return GenomeRecord(
                gid=str(gid),
                params=clean_params,
                fitness=_safe_float(data.get("fitness"), 0.0),
                niche=str(data.get("niche", "exploration")),
                origin=str(data.get("origin", "")),
                lineage=lineage,
                ts=_safe_float(data.get("ts"), time.time()),  # Use provided ts, fallback to current time for robustness
                ver=int(data.get("ver", 0)),
                node=str(data.get("node", "")),
            )
        except (TypeError, ValueError) as e:
            logger.warning(f"Error parsing GenomeRecord from dict for GID {gid}: {e}. Data: {data}")
            return None


@dataclass(slots=True)
class GossipEnvelope:
    """
    A message envelope for gossip, containing sender info, timestamp, nonce,
    versioning, delta (genome updates), and a signature for authentication.
    """

    sender: str
    ts: float
    nonce: str
    versions: Dict[str, int]
    delta: Dict[str, Dict[str, Any]]
    sig: str = ""

    def payload_bytes(self) -> bytes:
        """
        Generates the byte payload for signing/verification.
        Ensures deterministic serialization for consistent HMAC generation.
        """
        payload = {
            "sender": self.sender,
            "ts": self.ts,
            "nonce": self.nonce,
            "versions": self.versions,
            "delta": self.delta,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def sign(self, secret: bytes) -> str:
        """
        Signs the envelope payload using HMAC-SHA256 and the shared secret.
        Sets the `sig` attribute and returns it.

        Args:
            secret: The shared secret key as bytes.

        Returns:
            The hexadecimal string representation of the signature.
        """
        self.sig = hmac.new(secret, self.payload_bytes(), hashlib.sha256).hexdigest()
        return self.sig

    def verify(self, secret: bytes) -> bool:
        """
        Verifies the envelope's signature against the payload and shared secret.

        Args:
            secret: The shared secret key as bytes.

        Returns:
            True if the signature is valid, False otherwise.
        """
        if not self.sig:
            return False
        expected_sig = hmac.new(secret, self.payload_bytes(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_sig, self.sig)

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the GossipEnvelope to a dictionary.

        Returns:
            A dictionary representation of the envelope.
        """
        return {
            "sender": self.sender,
            "ts": self.ts,
            "nonce": self.nonce,
            "versions": self.versions,
            "delta": self.delta,
            "sig": self.sig,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> Optional["GossipEnvelope"]:
        """
        Creates a GossipEnvelope instance from a dictionary.
        Performs basic validation and type conversion.

        Args:
            data: A dictionary containing gossip envelope data.

        Returns:
            A GossipEnvelope instance if validation and conversion succeed,
            otherwise None.
        """
        if not isinstance(data, dict):
            logger.warning(f"Invalid data type for GossipEnvelope.from_dict: {type(data)}")
            return None
        try:
            versions_raw = data.get("versions", {})
            delta_raw = data.get("delta", {})

            if not isinstance(versions_raw, dict) or not isinstance(delta_raw, dict):
                logger.warning("Invalid 'versions' or 'delta' field type in incoming envelope.")
                return None

            versions: Dict[str, int] = {str(k): int(v) for k, v in versions_raw.items()}
            # Delta can contain nested dicts, so we take it as is for now,
            # validation will happen when converting to GenomeRecord.
            delta: Dict[str, Dict[str, Any]] = delta_raw

            return GossipEnvelope(
                sender=str(data.get("sender", "")),
                ts=_safe_float(data.get("ts"), 0.0),
                nonce=str(data.get("nonce", "")),
                versions=versions,
                delta=delta,
                sig=str(data.get("sig", "")),
            )
        except (TypeError, ValueError) as e:
            logger.warning(f"Error parsing GossipEnvelope from dict: {e}. Data: {data}")
            return None


# =========================
# ACCEPTANCE POLICY
# =========================


def _safe_float(value: Any, default: float = 0.0) -> float:
    """
    Safely converts a value to float, handling None, non-numeric strings, and NaN.

    Args:
        value: The value to convert.
        default: The default float value to return on failure.

    Returns:
        The converted float value or the default value.
    """
    try:
        v = float(value)
        if v != v:  # Check for NaN
            return default
        return v
    except (TypeError, ValueError):
        return default


@dataclass(slots=True)
class DeltaPolicy:
    """
    Configurable policy for whether a genome delta should be accepted.
    """

    min_fitness: float = 0.0
    min_param_value: float = 0.0
    max_param_value: float = 10.0
    trusted_niches: tuple[str, ...] = ("survival", "capital", "exploration")
    niche_bonus: Dict[str, float] = field(default_factory=dict)

    def accepts(self, genome: Dict[str, Any], trust: float = 1.0) -> bool:
        """
        Determines if a given genome (as a dictionary) meets the acceptance criteria.
        Trust acts as a soft gate, reducing acceptance probability for less trusted sources.

        Args:
            genome: A dictionary representing the genome record.
            trust: A float between 0.0 and 1.0 representing the trustworthiness
                   of the source. Higher trust increases acceptance probability.

        Returns:
            True if the genome is accepted, False otherwise.
        """
        if not isinstance(genome, dict):
            logger.debug(f"Rejecting genome: not a dictionary. Type: {type(genome)}")
            return False

        fitness = _safe_float(genome.get("fitness"), -1.0)
        if fitness < self.min_fitness:
            logger.debug(f"Rejecting genome {genome.get('gid', 'N/A')}: fitness {fitness} < {self.min_fitness}")
            return False

        params = genome.get("params", {})
        if not isinstance(params, dict) or not params:
            logger.debug(f"Rejecting genome {genome.get('gid', 'N/A')}: invalid or empty params.")
            return False

        for raw in params.values():
            value = _safe_float(raw, float("nan"))
            if value != value:  # NaN
                logger.debug(f"Rejecting genome {genome.get('gid', 'N/A')}: param value is NaN.")
                return False
            if not (self.min_param_value <= value <= self.max_param_value): # Inclusive range check
                logger.debug(
                    f"Rejecting genome {genome.get('gid', 'N/A')}: param value {value} out of range "
                    f"[{self.min_param_value}, {self.max_param_value}]."
                )
                return False

        niche = str(genome.get("niche", "exploration"))
        if niche not in self.trusted_niches and niche not in self.niche_bonus:
            logger.debug(f"Rejecting genome {genome.get('gid', 'N/A')}: untrusted niche '{niche}'.")
            return False

        # Trust is a soft gate: lower trust shrinks acceptance probability,
        # but never blocks deterministic policy if trust is high enough.
        # Ensure trust is clamped between 0.0 and 1.0.
        acceptance_probability = max(0.0, min(1.0, trust))
        if random.random() >= acceptance_probability:
            logger.debug(f"Rejecting genome {genome.get('gid', 'N/A')}: failed probabilistic trust gate (trust={trust:.2f}).")
            return False

        return True


# =========================
# SQLITE PERSISTENCE
# =========================


class SQLiteGenomeStore:
    """
    Manages persistent storage of GenomeRecords using SQLite.
    Includes methods for adding, merging, querying, and pruning genomes.
    """

    def __init__(self, path: str, node_id: str, ttl_s: int, max_state: int):
        """
        Initializes the SQLiteGenomeStore.

        Args:
            path: The file path for the SQLite database.
            node_id: The identifier for the current node, used for origin tracking.
            ttl_s: Time-to-live in seconds for genome records before pruning.
            max_state: Maximum number of genome records to keep after pruning.
        """
        self.path: str = path
        self.node_id: str = node_id
        self.ttl_s: int = ttl_s
        self.max_state: int = max_state
        self._lock: asyncio.Lock = asyncio.Lock()
        self._version: int = 0  # Monotonically increasing version for local changes
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """
        Establishes and returns a connection to the SQLite database.
        Sets row_factory to sqlite3.Row for dictionary-like access to rows.

        Returns:
            An opened SQLite database connection.
        """
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """
        Initializes the database schema if it doesn't already exist.
        Creates the 'genomes' table and an index for efficient querying.
        """
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS genomes (
                    gid TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    fitness REAL NOT NULL,
                    ver INTEGER NOT NULL,
                    node TEXT NOT NULL,
                    ts REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_genomes_fitness_ts
                ON genomes (fitness DESC, ts DESC)
                """
            )
            conn.commit()

        # Initialize _version from existing data
        with self._connect() as conn:
            row = conn.execute("SELECT MAX(ver) AS max_ver FROM genomes WHERE node = ?", (self.node_id,)).fetchone()
            if row and row["max_ver"] is not None:
                self._version = int(row["max_ver"])
            logger.info(f"SQLiteGenomeStore initialized for node {self.node_id} at {self.path}. Current local version: {self._version}")

    async def add(self, genome: GenomeRecord) -> str:
        """
        Adds a new genome or updates an existing one in the store.
        Assigns a new local version and the current node's ID.
        Updates the timestamp to the current time.

        Args:
            genome: The GenomeRecord to add or update.

        Returns:
            The GID of the added/updated genome.
        """
        async with self._lock:
            # Ensure GID is present, generate if not provided
            gid = genome.gid if genome.gid else str(uuid.uuid4())
            self._version += 1
            genome.gid = gid
            genome.ver = self._version
            genome.node = self.node_id
            genome.ts = time.time()  # Always update timestamp on local modification

            payload = json.dumps(genome.to_public_dict(), sort_keys=True, separators=(",", ":"))
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO genomes(gid, payload, fitness, ver, node, ts)
                    VALUES(?, ?, ?, ?, ?, ?)
                    ON CONFLICT(gid) DO UPDATE SET
                        payload=excluded.payload,
                        fitness=excluded.fitness,
                        ver=excluded.ver,
                        node=excluded.node,
                        ts=excluded.ts
                    """,
                    (gid, payload, genome.fitness, genome.ver, genome.node, genome.ts),
                )
                conn.commit()
            logger.debug(f"Added/updated genome {gid} locally. New version: {genome.ver}")
            return gid

    async def merge_many(self, remote: Dict[str, Dict[str, Any]]) -> int:
        """
        Merges multiple remote genome records into the local store.
        Uses a deterministic last-write-wins (higher version, then lexicographically higher node_id)
        comparison for conflict resolution.

        Args:
            remote: A dictionary of genome GIDs to their dictionary representations.
        Returns:
            The number of genomes successfully merged/updated.
        """
        merged_count = 0
        async with self._lock:
            with self._connect() as conn:
                for gid, raw_genome_data in remote.items():
                    rec = GenomeRecord.from_dict(gid, raw_genome_data)
                    if rec is None:
                        logger.warning(f"Skipping merge for GID {gid}: failed to parse remote genome data.")
                        continue

                    row = conn.execute(
                        "SELECT payload, ver, node FROM genomes WHERE gid = ?", (gid,)
                    ).fetchone()
                    
                    payload = json.dumps(rec.to_public_dict(), sort_keys=True, separators=(",", ":"))

                    if row is None:
                        # New genome, insert it
                        conn.execute(
                            "INSERT INTO genomes(gid, payload, fitness, ver, node, ts) VALUES(?, ?, ?, ?, ?, ?)",
                            (gid, payload, rec.fitness, rec.ver, rec.node, rec.ts),
                        )
                        merged_count += 1
                        logger.debug(f"Merged new genome: {gid} (ver {rec.ver})")
                    else:
                        # Existing genome, check for update based on last-write-wins
                        local_ver = int(row["ver"])
                        local_node = str(row["node"])

                        if (rec.ver, rec.node) > (local_ver, local_node):
                            conn.execute(
                                """
                                UPDATE genomes
                                SET payload = ?, fitness = ?, ver = ?, node = ?, ts = ?
                                WHERE gid = ?
                                """,
                                (payload, rec.fitness, rec.ver, rec.node, rec.ts, gid),
                            )
                            merged_count += 1
                            logger.debug(
                                f"Updated genome {gid}: local (ver {local_ver}, node {local_node}) "
                                f" < remote (ver {rec.ver}, node {rec.node})"
                            )
                conn.commit()
        if merged_count > 0:
            logger.info(f"Merged {merged_count} remote genomes.")
        return merged_count

    async def versions(self) -> Dict[str, int]:
        """
        Returns a dictionary of all genome GIDs and their current versions.

        Returns:
            A dictionary mapping genome IDs (str) to their versions (int).
        """
        async with self._lock:
            with self._connect() as conn:
                rows = conn.execute("SELECT gid, ver FROM genomes").fetchall()
                return {str(r["gid"]): int(r["ver"]) for r in rows}

    async def delta(self, known_versions: Dict[str, int]) -> Dict[str, Dict[str, Any]]:
        """
        Calculates the delta (new or updated genomes) based on a peer's known versions.

        Args:
            known_versions: A dictionary of GIDs and versions known by a peer.
        Returns:
            A dictionary of GIDs to genome data that the current store has
            but the peer doesn't have, or has an older version of.
        """
        async with self._lock:
            with self._connect() as conn:
                rows = conn.execute("SELECT gid, payload, ver FROM genomes").fetchall()
                out: Dict[str, Dict[str, Any]] = {}
                for row in rows:
                    gid = str(row["gid"])
                    ver = int(row["ver"])
                    if gid not in known_versions or known_versions[gid] < ver:
                        out[gid] = json.loads(str(row["payload"]))
                return out

    async def top(self, n: int) -> list[Dict[str, Any]]:
        """
        Retrieves the top N genomes sorted by fitness (descending) and timestamp (descending).

        Args:
            n: The maximum number of genomes to retrieve.
        Returns:
            A list of genome data dictionaries.
        """
        async with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT payload FROM genomes ORDER BY fitness DESC, ts DESC LIMIT ?",
                    (n,),
                ).fetchall()
                return [json.loads(str(r["payload"])) for r in rows]

    async def prune(self) -> int:
        """
        Prunes old or excess genome records from the store.
        Removes records older than TTL and then removes the lowest-fitness records
        if the total count exceeds max_state.

        Returns:
            The total number of records deleted.
        """
        async with self._lock:
            now = time.time()
            deleted_count = 0
            with self._connect() as conn:
                # 1. Prune by TTL
                cur = conn.execute("DELETE FROM genomes WHERE (? - ts) >= ?", (now, self.ttl_s))
                deleted_count += cur.rowcount if cur.rowcount is not None else 0
                if deleted_count > 0:
                    logger.info(f"Pruned {deleted_count} genomes by TTL.")

                # 2. Prune by max_state (keep top fitness)
                count_row = conn.execute("SELECT COUNT(*) AS c FROM genomes").fetchone()
                current_count = int(count_row["c"]) if count_row else 0
                
                if current_count > self.max_state:
                    overflow = current_count - self.max_state
                    # Select GIDs to delete (all but the top `self.max_state` genomes by fitness and timestamp)
                    delete_gids = conn.execute(
                        """
                        SELECT gid FROM genomes
                        ORDER BY fitness DESC, ts DESC
                        LIMIT -1 OFFSET ?
                        """,
                        (self.max_state,),
                    ).fetchall()
                    
                    if delete_gids:
                        gids_to_delete = tuple(str(r["gid"]) for r in delete_gids)
                        # Execute deletion for selected GIDs
                        cur_overflow = conn.execute(
                            f"DELETE FROM genomes WHERE gid IN ({','.join(['?'] * len(gids_to_delete))})",
                            gids_to_delete
                        )
                        deleted_count += cur_overflow.rowcount if cur_overflow.rowcount is not None else 0
                        logger.info(f"Pruned {overflow} genomes by max_state (kept top {self.max_state}).")
                conn.commit()
            return deleted_count

    async def size(self) -> int:
        """
        Returns the current number of genome records in the store.

        Returns:
            The total count of genomes as an integer.
        """
        async with self._lock:
            with self._connect() as conn:
                row = conn.execute("SELECT COUNT(*) AS c FROM genomes").fetchone()
                return int(row["c"]) if row else 0


# =========================
# PEER METRICS
# =========================


@dataclass(slots=True)
class PeerMetrics:
    """
    Tracks operational metrics for a single peer, including score,
    success/failure counts, last interaction time, and backoff status.
    """

    score: float = 1.0  # Represents trustworthiness/reliability (higher is better)
    successes: int = 0
    failures: int = 0
    last_seen: float = 0.0
    last_error: str = ""
    backoff_until: float = 0.0

    def mark_success(self) -> None:
        """
        Updates metrics after a successful interaction with the peer.
        Increases score, resets backoff, and updates last_seen.
        """
        self.successes += 1
        self.last_seen = time.time()
        self.last_error = ""
        # Slowly increase score, capped at 2.0
        self.score = min(2.0, self.score * 1.03 + 0.01)
        self.backoff_until = 0.0
        logger.debug(f"Peer success. New score: {self.score:.2f}")

    def mark_failure(self, error: str) -> None:
        """
        Updates metrics after a failed interaction with the peer.
        Decreases score, sets exponential backoff, and records the error.

        Args:
            error: A string describing the reason for the failure.
        """
        self.failures += 1
        self.last_error = error[:200]  # Cap error message length
        # Decrease score faster, floored at 0.2
        self.score = max(0.2, self.score * 0.85)
        # Exponential backoff: 0.5, 1, 2, 4, 8, 16 seconds, capped at 30s
        delay = min(30.0, 0.5 * (2**min(self.failures, 6)))
        self.backoff_until = time.time() + delay
        logger.warning(
            f"Peer failure (score: {self.score:.2f}, failures: {self.failures}). "
            f"Backing off for {delay:.1f}s. Error: {self.last_error}"
        )

    def can_attempt(self) -> bool:
        """
        Checks if an attempt to contact this peer is allowed based on backoff status.

        Returns:
            True if the current time is beyond the backoff period, False otherwise.
        """
        return time.time() >= self.backoff_until


# =========================
# GOSSIP PROTOCOL
# =========================


class GossipProtocol:
    """
    Implements the core gossip logic, handling message creation,
    validation, and peer synchronization.
    """

    def __init__(
        self,
        cfg: GossipConfig,
        store: SQLiteGenomeStore,
        policy: Optional[DeltaPolicy] = None,
    ):
        """
        Initializes the GossipProtocol.

        Args:
            cfg: The gossip configuration.
            store: The SQLiteGenomeStore instance for persistence.
            policy: An optional DeltaPolicy for filtering incoming genomes.
                    Defaults to a policy based on `cfg.min_fitness`.
        """
        self.cfg: GossipConfig = cfg
        self.store: SQLiteGenomeStore = store
        self.policy: DeltaPolicy = policy or DeltaPolicy(min_fitness=cfg.min_fitness)
        self.peers: list[str] = cfg.peers
        self.peer_metrics: Dict[str, PeerMetrics] = {p: PeerMetrics() for p in self.peers}
        self.peer_versions: Dict[str, Dict[str, int]] = {
            p: {} for p in self.peers
        }  # Stores peer's last known versions
        self.replay_cache: Dict[Tuple[str, str], float] = {}  # Stores (sender, nonce) -> timestamp
        # Using collections.deque for efficient O(1) appends and pops from both ends
        self.replay_order: Deque[Tuple[str, str]] = Deque()  # For LRU-like eviction
        self._replay_lock: asyncio.Lock = asyncio.Lock()

    def _make_envelope(self, delta: Dict[str, Dict[str, Any]], versions: Dict[str, int]) -> GossipEnvelope:
        """
        Constructs and signs a new GossipEnvelope with the current node's data.

        Args:
            delta: The delta of genome records to send.
            versions: The sender's current versions of all genomes.
        Returns:
            A signed GossipEnvelope instance.
        """
        env = GossipEnvelope(
            sender=self.cfg.node_id,
            ts=time.time(),
            nonce=uuid.uuid4().hex,
            versions=versions,
            delta=delta,
        )
        env.sign(self.cfg.secret_bytes)
        return env

    async def _remember_nonce(self, sender: str, nonce: str) -> bool:
        """
        Adds a nonce to the replay cache. Returns False if already seen (replay detected).

        Args:
            sender: The ID of the sender.
            nonce: The unique nonce from the envelope.
        Returns:
            True if the nonce was new and remembered, False if it was a replay.
        """
        key = (sender, nonce)
        async with self._replay_lock:
            if key in self.replay_cache:
                logger.warning(f"Replay detected: nonce '{nonce}' from sender '{sender}' already in cache.")
                return False
            self.replay_cache[key] = time.time()
            self.replay_order.append(key)
            # Prune cache if it exceeds max size
            while len(self.replay_order) > self.cfg.replay_cache_size:
                old = self.replay_order.popleft()  # Use popleft for deque
                self.replay_cache.pop(old, None)
            return True

    def _fresh_enough(self, ts: float) -> bool:
        """
        Checks if a timestamp is within the acceptable clock skew.

        Args:
            ts: The timestamp from the incoming message.
        Returns:
            True if the timestamp is fresh enough, False otherwise.
        """
        current_time = time.time()
        is_fresh = abs(current_time - ts) <= self.cfg.max_clock_skew_s
        if not is_fresh:
            logger.warning(f"Stale envelope: message timestamp {ts} (diff {abs(current_time - ts):.2f}s) "
                           f"exceeds max skew {self.cfg.max_clock_skew_s}s.")
        return is_fresh

    def _peer_allowed(self, peer: str) -> bool:
        """
        Checks if a peer is allowed to be contacted based on its metrics (e.g., backoff).

        Args:
            peer: The URL of the peer.
        Returns:
            True if allowed, False otherwise.
        """
        metrics = self.peer_metrics.get(peer)
        if metrics is None:
            # If peer is not in metrics, it's new or not configured, assume allowed to initiate contact
            return True
        return metrics.can_attempt()

    def _choose_peer(self) -> Optional[str]:
        """
        Selects a peer to gossip with, prioritizing healthier peers.

        Returns:
            The URL of a chosen peer, or None if no peers are available or all are in backoff.
        """
        candidates = [p for p in self.peers if self._peer_allowed(p)]
        if not candidates:
            return None
        # Choose peers based on their score (higher score = more likely to be chosen)
        weights = [self.peer_metrics.get(p, PeerMetrics()).score for p in candidates]
        # Normalize weights to avoid issues with all zero or negative (though scores are >=0.2)
        total_weight = sum(weights)
        if total_weight == 0: # Should not happen with min score 0.2, but as a safeguard
            return random.choice(candidates)
        return random.choices(candidates, weights=weights, k=1)[0]

    def _filtered_delta(self, delta: Dict[str, Dict[str, Any]], trust: float) -> Dict[str, Dict[str, Any]]:
        """
        Filters a delta of genomes based on the configured DeltaPolicy.

        Args:
            delta: The incoming delta of genome records.
            trust: The trust score of the peer sending the delta, used by the policy.
        Returns:
            A new dictionary containing only the accepted genome records.
        """
        out: Dict[str, Dict[str, Any]] = {}
        for gid, genome in delta.items():
            if self.policy.accepts(genome, trust=trust):
                out[gid] = genome
            else:
                logger.debug(f"Rejected genome '{gid}' from incoming delta by policy.")
        return out

    async def incoming(self, env_data: Dict[str, Any]) -> web.Response:
        """
        Handles an incoming gossip envelope from another peer.
        Performs validation (format, sender, timestamp, signature, replay),
        merges accepted deltas, and prepares a response containing local versions
        and deltas for the sender.

        Args:
            env_data: The dictionary representation of the incoming envelope.
        Returns:
            An aiohttp web.Response with status and data.
        """
        env = GossipEnvelope.from_dict(env_data)
        if env is None:
            logger.warning("Rejected incoming gossip: Invalid envelope format.")
            return web.json_response({"error": "invalid_envelope"}, status=400)

        if env.sender == self.cfg.node_id:
            logger.warning(f"Rejected incoming gossip from self ({env.sender}).")
            return web.json_response({"error": "self_message"}, status=400)

        if not self._fresh_enough(env.ts):
            return web.json_response({"error": "stale_envelope"}, status=400)

        if not env.verify(self.cfg.secret_bytes):
            logger.warning(f"Rejected incoming gossip from {env.sender}: Bad signature.")
            return web.json_response({"error": "bad_signature"}, status=401)

        if not await self._remember_nonce(env.sender, env.nonce):
            return web.json_response({"error": "replay_detected"}, status=409)

        # Initialize metrics for new peers if they connect
        if env.sender not in self.peer_metrics:
            logger.info(f"Discovered new peer: {env.sender}. Initializing metrics.")
            self.peer_metrics[env.sender] = PeerMetrics()
            self.peer_versions[env.sender] = {}

        trust = self.peer_metrics[env.sender].score
        filtered_delta = self._filtered_delta(env.delta, trust=trust)
        merged = await self.store.merge_many(filtered_delta)
        
        local_versions = await self.store.versions()
        # Calculate delta to send back: what *we* have that the *sender* doesn't know about or has an older version of
        local_delta = await self.store.delta(env.versions)

        # Store peer's last known versions to avoid sending them data they already have next time
        self.peer_versions[env.sender] = dict(env.versions)
        self.peer_metrics[env.sender].mark_success()  # Mark successful interaction

        logger.info(f"Processed gossip from {env.sender}: merged {merged} genomes, returning {len(local_delta)} delta items.")
        return web.json_response(
            {
                "ok": True,
                "merged": merged,
                "versions": local_versions,
                "delta": local_delta,
            }
        )

    async def sync_once(self, session: aiohttp.ClientSession, peer_url: str) -> None:
        """
        Attempts a single gossip synchronization round with a specific peer.
        Sends our delta and versions, then processes the peer's response.

        Args:
            session: An aiohttp client session for making HTTP requests.
            peer_url: The URL of the peer to sync with (e.g., "http://peer-host:port").
        """
        # Initialize metrics for new peers if they weren't already
        if peer_url not in self.peer_metrics:
            logger.info(f"Initializing metrics for peer {peer_url}.")
            self.peer_metrics[peer_url] = PeerMetrics()
            self.peer_versions[peer_url] = {}

        if not self._peer_allowed(peer_url):
            logger.debug(f"Skipping sync with {peer_url}: currently in backoff.")
            return  # Skip if peer is in backoff

        try:
            known_versions = self.peer_versions.get(peer_url, {})
            local_versions = await self.store.versions()
            # Determine what we need to send to the peer based on what they *don't* know
            local_delta_to_send = await self.store.delta(known_versions)
            env = self._make_envelope(local_delta_to_send, local_versions)

            logger.debug(f"Syncing with {peer_url}: sending {len(local_delta_to_send)} delta items.")
            async with session.post(
                f"{peer_url}/gossip",
                json=env.to_dict(),
                timeout=self.cfg.request_timeout_s,
            ) as resp:
                resp.raise_for_status()  # Raise an exception for bad status codes (4xx, 5xx)
                data = await resp.json()

            # Process response from peer
            remote_versions = data.get("versions", {})
            remote_delta = data.get("delta", {})

            if not isinstance(remote_versions, dict) or not isinstance(remote_delta, dict):
                raise ValueError("Invalid response data structure from peer.")

            # Update our knowledge of the peer's versions
            self.peer_versions[peer_url] = {str(k): int(v) for k, v in remote_versions.items()}

            # Merge incoming delta from peer, applying policy based on peer's trust score
            trust = self.peer_metrics[peer_url].score
            filtered_remote_delta = self._filtered_delta(remote_delta, trust=trust)
            merged_count = await self.store.merge_many(filtered_remote_delta)

            self.peer_metrics[peer_url].mark_success()
            logger.info(
                f"Successfully synced with {peer_url}. "
                f"Merged {merged_count} remote genomes. "
                f"Peer's new score: {self.peer_metrics[peer_url].score:.2f}"
            )

        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError, TypeError) as e:
            # Handle network, JSON parsing, or data structure errors from peer response
            error_msg = f"Failed to sync with {peer_url} due to client/protocol error: {e}"
            logger.error(error_msg, exc_info=False) # No full traceback unless needed
            self.peer_metrics[peer_url].mark_failure(error_msg)
        except Exception as e:
            # Catch any other unexpected exceptions during sync
            error_msg = f"Unexpected error during sync with {peer_url}: {e}"
            logger.error(error_msg, exc_info=True)
            self.peer_metrics[peer_url].mark_failure(error_msg)

    async def sync_loop(self) -> None:
        """
        Continuously runs the gossip synchronization process, choosing peers
        and performing syncs at regular intervals.
        """
        # Add a small buffer to the total timeout to account for network latency and processing
        timeout = aiohttp.ClientTimeout(total=self.cfg.request_timeout_s + 1.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            logger.info(f"Gossip sync loop started. Interval: {self.cfg.gossip_interval_s}s.")
            while True:
                peer = self._choose_peer()
                if peer:
                    logger.debug(f"Chosen peer for sync: {peer}")
                    await self.sync_once(session, peer)
                else:
                    logger.debug("No eligible peers to sync with at this time.")
                await asyncio.sleep(self.cfg.gossip_interval_s)

    def stats(self) -> Dict[str, Any]:
        """
        Returns current statistics about the gossip protocol and peer metrics.

        Returns:
            A dictionary containing node ID, peer list, and detailed peer metrics.
        """
        return {
            "node_id": self.cfg.node_id,
            "configured_peers": self.peers,
            "peer_metrics": {peer: asdict(metrics) for peer, metrics in self.peer_metrics.items()},
        }


# =========================
# NODE + HTTP APP
# =========================


class GossipNode:
    """
    Manages the lifecycle of a gossip node, integrating the configuration,
    storage, protocol, and exposing HTTP endpoints via aiohttp.
    """

    def __init__(self, cfg: GossipConfig, policy: Optional[DeltaPolicy] = None):
        """
        Initializes the GossipNode.

        Args:
            cfg: The gossip configuration.
            policy: An optional DeltaPolicy for filtering incoming genomes.
        """
        self.cfg: GossipConfig = cfg
        self.store: SQLiteGenomeStore = SQLiteGenomeStore(cfg.sqlite_path, cfg.node_id, cfg.ttl_s, cfg.max_state)
        self.protocol: GossipProtocol = GossipProtocol(cfg, self.store, policy=policy)
        self._bg_tasks: list[asyncio.Task] = []

    def build_app(self) -> web.Application:
        """
        Builds and configures the aiohttp web application for the gossip node.
        Registers routes and startup/cleanup hooks.

        Returns:
            The configured aiohttp.web.Application instance.
        """
        app = web.Application()
        app.add_routes(
            [
                web.post("/gossip", self.handle_gossip),
                web.get("/health", self.handle_health),
                web.get("/stats", self.handle_stats),
            ]
        )
        app.on_startup.append(self.on_startup)
        app.on_cleanup.append(self.on_cleanup)
        return app

    async def on_startup(self, app: web.Application) -> None:
        """
        Aiohttp startup hook. Starts background tasks for gossip sync and pruning.

        Args:
            app: The aiohttp application instance.
        """
        logger.info("GossipNode starting up...")
        self._bg_tasks.append(asyncio.create_task(self.protocol.sync_loop(), name="gossip_sync_loop"))
        self._bg_tasks.append(asyncio.create_task(self._prune_loop(), name="gossip_prune_loop"))
        logger.info("Background tasks for gossip sync and pruning started.")

    async def on_cleanup(self, app: web.Application) -> None:
        """
        Aiohttp cleanup hook. Cancels all running background tasks gracefully.

        Args:
            app: The aiohttp application instance.
        """
        logger.info("GossipNode shutting down. Cancelling background tasks...")
        for task in self._bg_tasks:
            task.cancel()
        # Wait for all tasks to finish cancellation, ignoring exceptions
        await asyncio.gather(*self._bg_tasks, return_exceptions=True)
        logger.info("Background tasks cancelled. GossipNode cleanup complete.")

    async def _prune_loop(self) -> None:
        """
        Periodically prunes the genome store based on configured TTL and max_state.
        """
        prune_interval = max(5.0, self.cfg.ttl_s / 4)
        logger.info(f"Prune loop started. Pruning every {prune_interval:.1f}s.")
        while True:
            await asyncio.sleep(prune_interval)
            try:
                deleted_count = await self.store.prune()
                if deleted_count > 0:
                    logger.debug(f"Pruned {deleted_count} records from the store.")
            except Exception as e:
                logger.error(f"Error during pruning: {e}", exc_info=True)

    async def handle_gossip(self, request: web.Request) -> web.Response:
        """
        HTTP POST handler for incoming gossip messages.
        Parses the JSON payload and passes it to the gossip protocol for processing.

        Args:
            request: The aiohttp request object.
        Returns:
            An aiohttp web.Response.
        """
        try:
            payload = await request.json()
        except json.JSONDecodeError:
            logger.warning(f"Received invalid JSON from {request.remote}")
            return web.json_response({"error": "invalid_json"}, status=400)
        except Exception as e:
            logger.error(f"Error reading JSON from request: {e}", exc_info=True)
            return web.json_response({"error": "request_payload_error"}, status=400)
        return await self.protocol.incoming(payload)

    async def handle_health(self, request: web.Request) -> web.Response:
        """
        HTTP GET handler for health checks.
        Provides basic node status information.

        Args:
            request: The aiohttp request object.
        Returns:
            An aiohttp web.Response with health status.
        """
        return web.json_response(
            {
                "ok": True,
                "node_id": self.cfg.node_id,
                "peer_count": len(self.cfg.peers),
                "status": "running",
            }
        )

    async def handle_stats(self, request: web.Request) -> web.Response:
        """
        HTTP GET handler for node statistics, including store size and protocol metrics.

        Args:
            request: The aiohttp request object.
        Returns:
            An aiohttp web.Response with node statistics.
        """
        size = await self.store.size()
        return web.json_response(
            {
                "node_id": self.cfg.node_id,
                "store_size": size,
                "protocol": self.protocol.stats(),
            }
        )


def main() -> None:
    """
    Main entry point for running the GossipNode as an aiohttp web application.
    Initializes configuration and starts the web server.
    """
    cfg = GossipConfig()
    logger.info(f"Starting GossipNode with ID: {cfg.node_id}, binding to {cfg.bind_host}:{cfg.port}")
    node = GossipNode(cfg)
    app = node.build_app()
    web.run_app(app, host=cfg.bind_host, port=cfg.port)


if __name__ == "__main__":
    main()