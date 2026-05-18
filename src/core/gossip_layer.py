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

from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, Iterable, Optional, Tuple
import asyncio
import hashlib
import hmac
import json
import os
import random
import sqlite3
import time
import uuid

import aiohttp
from aiohttp import web


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
        """Returns the shared secret encoded as bytes."""
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
        """
        if not isinstance(data, dict):
            return None
        params = data.get("params")
        if not isinstance(params, dict):
            return None
        try:
            clean_params = {str(k): float(v) for k, v in params.items()}
            lineage = data.get("lineage", [])
            if not isinstance(lineage, list):
                lineage = []
            return GenomeRecord(
                gid=str(gid),
                params=clean_params,
                fitness=float(data.get("fitness", 0.0)),
                niche=str(data.get("niche", "exploration")),
                origin=str(data.get("origin", "")),
                lineage=[str(x) for x in lineage if isinstance(x, (str, int))],
                ts=float(data.get("ts", time.time())),
                ver=int(data.get("ver", 0)),
                node=str(data.get("node", "")),
            )
        except (TypeError, ValueError):
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
        """Generates the byte payload for signing/verification."""
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
        Signs the envelope payload using HMAC and the shared secret.
        Sets the `sig` attribute and returns it.
        """
        self.sig = hmac.new(secret, self.payload_bytes(), hashlib.sha256).hexdigest()
        return self.sig

    def verify(self, secret: bytes) -> bool:
        """
        Verifies the envelope's signature against the payload and shared secret.
        """
        if not self.sig:
            return False
        expected = hmac.new(secret, self.payload_bytes(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, self.sig)

    def to_dict(self) -> Dict[str, Any]:
        """Converts the GossipEnvelope to a dictionary."""
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
        """
        if not isinstance(data, dict):
            return None
        try:
            versions = data.get("versions", {})
            delta = data.get("delta", {})
            if not isinstance(versions, dict) or not isinstance(delta, dict):
                return None
            return GossipEnvelope(
                sender=str(data.get("sender", "")),
                ts=float(data.get("ts", 0.0)),
                nonce=str(data.get("nonce", "")),
                versions={str(k): int(v) for k, v in versions.items()},
                delta=delta,
                sig=str(data.get("sig", "")),
            )
        except (TypeError, ValueError):
            return None


# =========================
# ACCEPTANCE POLICY
# =========================

def _safe_float(value: Any, default: float = 0.0) -> float:
    """Safely converts a value to float, handling None, non-numeric, and NaN."""
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
        """
        if not isinstance(genome, dict):
            return False

        fitness = _safe_float(genome.get("fitness"), -1.0)
        if fitness < self.min_fitness:
            return False

        params = genome.get("params", {})
        if not isinstance(params, dict) or not params:
            return False

        for raw in params.values():
            value = _safe_float(raw, float("nan"))
            if value != value:  # NaN
                return False
            if not (self.min_param_value < value < self.max_param_value):
                return False

        niche = str(genome.get("niche", "exploration"))
        if niche not in self.trusted_niches and niche not in self.niche_bonus:
            return False

        # trust is a soft gate: lower trust shrinks acceptance probability
        # but never blocks deterministic policy if trust is high enough.
        return random.random() < max(0.0, min(1.0, trust))


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
        self.path = path
        self.node_id = node_id
        self.ttl_s = ttl_s
        self.max_state = max_state
        self._lock = asyncio.Lock()
        self._version: int = 0  # Monotonically increasing version for local changes
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """Establishes and returns a connection to the SQLite database."""
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initializes the database schema if it doesn't already exist."""
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

    async def add(self, genome: GenomeRecord) -> str:
        """
        Adds a new genome or updates an existing one in the store.
        Assigns a new version and the current node's ID.
        """
        async with self._lock:
            gid = genome.gid or str(uuid.uuid4())
            self._version += 1
            genome.gid = gid
            genome.ver = self._version
            genome.node = self.node_id
            genome.ts = genome.ts or time.time()

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
            return gid

    async def merge_many(self, remote: Dict[str, Dict[str, Any]]) -> int:
        """
        Merges multiple remote genome records into the local store.
        Uses a deterministic last-write-wins (version, node_id) comparison.

        Args:
            remote: A dictionary of genome GIDs to their dictionary representations.
        Returns:
            The number of genomes successfully merged/updated.
        """
        merged = 0
        async with self._lock:
            with self._connect() as conn:
                for gid, raw in remote.items():
                    rec = GenomeRecord.from_dict(gid, raw)
                    if rec is None:
                        continue

                    row = conn.execute("SELECT payload, ver, node FROM genomes WHERE gid = ?", (gid,)).fetchone()
                    if row is None:
                        # New genome, insert it
                        payload = json.dumps(rec.to_public_dict(), sort_keys=True, separators=(",", ":"))
                        conn.execute(
                            "INSERT INTO genomes(gid, payload, fitness, ver, node, ts) VALUES(?, ?, ?, ?, ?, ?)",
                            (gid, payload, rec.fitness, rec.ver, rec.node, rec.ts),
                        )
                        merged += 1
                    else:
                        # Existing genome, check for update
                        local_ver = int(row["ver"])
                        local_node = str(row["node"])
                        # Last-write-wins: (higher version, then lexicographically higher node ID)
                        if (rec.ver, rec.node) > (local_ver, local_node):
                            payload = json.dumps(rec.to_public_dict(), sort_keys=True, separators=(",", ":"))
                            conn.execute(
                                """
                                UPDATE genomes
                                SET payload = ?, fitness = ?, ver = ?, node = ?, ts = ?
                                WHERE gid = ?
                                """,
                                (payload, rec.fitness, rec.ver, rec.node, rec.ts, gid),
                            )
                            merged += 1
                conn.commit()
        return merged

    async def versions(self) -> Dict[str, int]:
        """Returns a dictionary of all genome GIDs and their current versions."""
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
            deleted = 0
            with self._connect() as conn:
                # 1. Prune by TTL
                cur = conn.execute("DELETE FROM genomes WHERE (? - ts) >= ?", (now, self.ttl_s))
                deleted += cur.rowcount if cur.rowcount is not None else 0

                # 2. Prune by max_state (keep top fitness)
                count_row = conn.execute("SELECT COUNT(*) AS c FROM genomes").fetchone()
                count = int(count_row["c"]) if count_row else 0
                if count > self.max_state:
                    overflow = int(count - self.max_state)
                    # Delete all but the top `self.max_state` genomes by fitness and timestamp
                    conn.execute(
                        """
                        DELETE FROM genomes
                        WHERE gid IN (
                            SELECT gid FROM genomes
                            ORDER BY fitness DESC, ts DESC
                            LIMIT -1 OFFSET ?
                        )
                        """,
                        (self.max_state,),
                    )
                    deleted += overflow
                conn.commit()
            return deleted

    async def size(self) -> int:
        """Returns the current number of genome records in the store."""
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
    score: float = 1.0  # Represents trustworthiness/reliability
    successes: int = 0
    failures: int = 0
    last_seen: float = 0.0
    last_error: str = ""
    backoff_until: float = 0.0

    def mark_success(self) -> None:
        """Updates metrics after a successful interaction with the peer."""
        self.successes += 1
        self.last_seen = time.time()
        self.last_error = ""
        self.score = min(2.0, self.score * 1.03 + 0.01) # Slowly increase score
        self.backoff_until = 0.0

    def mark_failure(self, error: str) -> None:
        """Updates metrics after a failed interaction with the peer."""
        self.failures += 1
        self.last_error = error[:200] # Cap error message length
        self.score = max(0.2, self.score * 0.85) # Decrease score faster
        delay = min(30.0, 0.5 * (2 ** min(self.failures, 6))) # Exponential backoff, capped at 30s
        self.backoff_until = time.time() + delay

    def can_attempt(self) -> bool:
        """Checks if an attempt to contact this peer is allowed based on backoff."""
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
        self.cfg = cfg
        self.store = store
        self.policy = policy or DeltaPolicy(min_fitness=cfg.min_fitness)
        self.peers = cfg.peers
        self.peer_metrics: Dict[str, PeerMetrics] = {p: PeerMetrics() for p in self.peers}
        self.peer_versions: Dict[str, Dict[str, int]] = {p: {} for p in self.peers}
        self.replay_cache: Dict[Tuple[str, str], float] = {} # Stores (sender, nonce) -> timestamp
        self.replay_order: list[Tuple[str, str]] = [] # For LRU-like eviction
        self._replay_lock = asyncio.Lock()

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
                return False
            self.replay_cache[key] = time.time()
            self.replay_order.append(key)
            # Prune cache if it exceeds max size
            while len(self.replay_order) > self.cfg.replay_cache_size:
                old = self.replay_order.pop(0)
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
        return abs(time.time() - ts) <= self.cfg.max_clock_skew_s

    def _peer_allowed(self, peer: str) -> bool:
        """
        Checks if a peer is allowed to be contacted based on its metrics (e.g., backoff).

        Args:
            peer: The URL of the peer.
        Returns:
            True if allowed, False otherwise.
        """
        metrics = self.peer_metrics.get(peer)
        return metrics is not None and metrics.can_attempt()

    def _choose_peer(self) -> Optional[str]:
        """
        Selects a peer to gossip with, prioritizing healthier peers.

        Returns:
            The URL of a chosen peer, or None if no peers are available.
        """
        candidates = [p for p in self.peers if self._peer_allowed(p)]
        if not candidates:
            return None
        # Choose peers based on their score (higher score = more likely to be chosen)
        weights = [self.peer_metrics[p].score for p in candidates]
        return random.choices(candidates, weights=weights, k=1)[0]

    def _filtered_delta(self, delta: Dict[str, Dict[str, Any]], trust: float) -> Dict[str, Dict[str, Any]]:
        """
        Filters a delta of genomes based on the configured DeltaPolicy.

        Args:
            delta: The incoming delta of genome records.
            trust: The trust score of the peer sending the delta.
        Returns:
            A new dictionary containing only the accepted genome records.
        """
        out: Dict[str, Dict[str, Any]] = {}
        for gid, genome in delta.items():
            if self.policy.accepts(genome, trust=trust):
                out[gid] = genome
        return out

    async def incoming(self, env_data: Dict[str, Any]) -> web.Response:
        """
        Handles an incoming gossip envelope from another peer.
        Performs validation, merges deltas, and prepares a response.

        Args:
            env_data: The dictionary representation of the incoming envelope.
        Returns:
            An aiohttp web.Response with status and data.
        """
        env = GossipEnvelope.from_dict(env_data)
        if env is None:
            return web.json_response({"error": "invalid_envelope"}, status=400)

        if env.sender == self.cfg.node_id:
            return web.json_response({"error": "self_message"}, status=400)

        if not self._fresh_enough(env.ts):
            return web.json_response({"error": "stale_envelope"}, status=400)

        if not env.verify(self.cfg.secret_bytes):
            return web.json_response({"error": "bad_signature"}, status=401)

        if not await self._remember_nonce(env.sender, env.nonce):
            return web.json_response({"error": "replay_detected"}, status=409)

        # Initialize metrics for new peers
        if env.sender not in self.peer_metrics:
            self.peer_metrics[env.sender] = PeerMetrics()
            self.peer_versions[env.sender] = {}

        trust = self.peer_metrics[env.sender].score
        merged = await self.store.merge_many(self._filtered_delta(env.delta, trust=trust))
        local_versions = await self.store.versions()
        local_delta = await self.store.delta(env.versions)

        self.peer_versions[env.sender] = dict(env.versions) # Store peer's last known versions
        self.peer_metrics[env.sender].mark_success() # Mark successful interaction

        return web.json_response({
            "ok": True,
            "merged": merged,
            "versions": local_versions,
            "delta": local_delta,
        })

    async def sync_once(self, session: aiohttp.ClientSession, peer: str) -> None:
        """
        Attempts a single gossip synchronization round with a specific peer.

        Args:
            session: An aiohttp client session.
            peer: The URL of the peer to sync with.
        """
        # Initialize metrics for new peers if they somehow weren't already
        if peer not in self.peer_metrics:
            self.peer_metrics[peer] = PeerMetrics()
            self.peer_versions[peer] = {}

        if not self._peer_allowed(peer):
            return # Skip if peer is in backoff

        try:
            known_versions = self.peer_versions.get(peer, {})
            local_versions = await self.store.versions()
            local_delta = await self.store.delta(known_versions) # Send what peer doesn't have
            env = self._make_envelope(local_delta, local_versions)

            async with session.post(
                f"{peer}/gossip",
                json=env.to_dict(),
                timeout=self.cfg.request_timeout_s,
            ) as resp:
                resp.raise_for_status() # Raise an exception for bad status codes (4xx, 5xx)
                data = await resp.json()

            remote_versions = data.get("versions", {})
            remote_delta = data.get("delta", {})

            if isinstance(remote_versions, dict):
                # Update our knowledge of the peer's versions
                self.peer_versions[peer] = {str(k): int(v) for k, v in remote_versions.items()}

            if isinstance(remote_delta, dict):
                # Merge incoming delta from peer
                trust = self.peer_metrics[peer].score
                await self.store.merge_many(self._filtered_delta(remote_delta, trust=trust))

            self.peer_metrics[peer].mark_success()

        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError, TypeError) as e:
            # Handle network, JSON parsing, or data structure errors
            self.peer_metrics[peer].mark_failure(str(e))
        except Exception as e:
            # Catch any other unexpected exceptions
            self.peer_metrics[peer].mark_failure(str(e))

    async def sync_loop(self) -> None:
        """
        Continuously runs the gossip synchronization process, choosing peers
        and performing syncs at regular intervals.
        """
        # Add a small buffer to the total timeout to account for network latency and processing
        timeout = aiohttp.ClientTimeout(total=self.cfg.request_timeout_s + 1.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            while True:
                peer = self._choose_peer()
                if peer:
                    await self.sync_once(session, peer)
                await asyncio.sleep(self.cfg.gossip_interval_s)

    def stats(self) -> Dict[str, Any]:
        """Returns current statistics about the gossip protocol and peer metrics."""
        return {
            "node_id": self.cfg.node_id,
            "peers": self.peers,
            "peer_metrics": {peer: asdict(metrics) for peer, metrics in self.peer_metrics.items()},
        }


# =========================
# NODE + HTTP APP
# =========================

class GossipNode:
    """
    Manages the lifecycle of a gossip node, integrating the configuration,
    storage, protocol, and exposing HTTP endpoints.
    """
    def __init__(self, cfg: GossipConfig, policy: Optional[DeltaPolicy] = None):
        """
        Initializes the GossipNode.

        Args:
            cfg: The gossip configuration.
            policy: An optional DeltaPolicy for filtering incoming genomes.
        """
        self.cfg = cfg
        self.store = SQLiteGenomeStore(cfg.sqlite_path, cfg.node_id, cfg.ttl_s, cfg.max_state)
        self.protocol = GossipProtocol(cfg, self.store, policy=policy)
        self._bg_tasks: list[asyncio.Task] = []

    def build_app(self) -> web.Application:
        """
        Builds and configures the aiohttp web application for the gossip node.

        Returns:
            The configured aiohttp.web.Application instance.
        """
        app = web.Application()
        app.add_routes([
            web.post("/gossip", self.handle_gossip),
            web.get("/health", self.handle_health),
            web.get("/stats", self.handle_stats),
        ])
        app.on_startup.append(self.on_startup)
        app.on_cleanup.append(self.on_cleanup)
        return app

    async def on_startup(self, app: web.Application) -> None:
        """
        Aiohttp startup hook. Starts background tasks for gossip sync and pruning.

        Args:
            app: The aiohttp application instance.
        """
        self._bg_tasks.append(asyncio.create_task(self.protocol.sync_loop()))
        self._bg_tasks.append(asyncio.create_task(self._prune_loop()))

    async def on_cleanup(self, app: web.Application) -> None:
        """
        Aiohttp cleanup hook. Cancels all running background tasks.

        Args:
            app: The aiohttp application instance.
        """
        for task in self._bg_tasks:
            task.cancel()
        # Wait for all tasks to finish cancellation, ignoring exceptions
        await asyncio.gather(*self._bg_tasks, return_exceptions=True)

    async def _prune_loop(self) -> None:
        """
        Periodically prunes the genome store based on configured TTL and max_state.
        """
        # Prune more frequently than TTL to ensure timely cleanup
        while True:
            await asyncio.sleep(max(5.0, self.cfg.ttl_s / 4))
            await self.store.prune()

    async def handle_gossip(self, request: web.Request) -> web.Response:
        """
        HTTP POST handler for incoming gossip messages.
        """
        try:
            payload = await request.json()
        except Exception:
            return web.json_response({"error": "invalid_json"}, status=400)
        return await self.protocol.incoming(payload)

    async def handle_health(self, request: web.Request) -> web.Response:
        """
        HTTP GET handler for health checks.
        """
        return web.json_response({
            "ok": True,
            "node_id": self.cfg.node_id,
            "peer_count": len(self.cfg.peers),
        })

    async def handle_stats(self, request: web.Request) -> web.Response:
        """
        HTTP GET handler for node statistics, including store size and protocol metrics.
        """
        size = await self.store.size()
        return web.json_response({
            "node_id": self.cfg.node_id,
            "store_size": size,
            "protocol": self.protocol.stats(),
        })


def main() -> None:
    """
    Main entry point for running the GossipNode as an aiohttp web application.
    """
    cfg = GossipConfig()
    node = GossipNode(cfg)
    app = node.build_app()
    web.run_app(app, host=cfg.bind_host, port=cfg.port)


if __name__ == "__main__":
    main()