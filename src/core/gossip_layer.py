from __future__ import annotations

"""BlackSwan cluster gossip layer.

Features:
- SQLite-backed genome storage
- HMAC-authenticated gossip envelopes
- replay protection
- stale-message rejection
- configurable delta acceptance policy
- peer scoring and exponential backoff
- deterministic last-write-wins merge
- aiohttp HTTP endpoints for node-to-node gossip
"""

import asyncio
import hashlib
import hmac
import json
import logging
import math
import os
import random
import sqlite3
import time
import uuid
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Final, Optional

import aiohttp
from aiohttp import web

logger = logging.getLogger(__name__)

DEFAULT_GOSSIP_SECRET: Final[str] = "dev-secret"
SQLITE_TIMEOUT_SECONDS: Final[float] = 30.0
SQLITE_BUSY_TIMEOUT_MS: Final[int] = 30_000
SQLITE_WRITE_RETRIES: Final[int] = 6
SQLITE_WRITE_RETRY_DELAY_SECONDS: Final[float] = 0.05


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default

    if not math.isfinite(number):
        return default

    return number


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _json_dumps(data: Any) -> str:
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


@dataclass(frozen=True, slots=True)
class GossipConfig:
    """Configuration for the BlackSwan gossip layer."""

    node_id: str = field(default_factory=lambda: os.environ.get("NODE_ID", str(uuid.uuid4())))
    port: int = field(default_factory=lambda: int(os.environ.get("PORT", "8000")))
    bind_host: str = field(default_factory=lambda: os.environ.get("BIND_HOST", "0.0.0.0"))
    peers_csv: str = field(default_factory=lambda: os.environ.get("PEERS", ""))
    shared_secret: str = field(default_factory=lambda: os.environ.get("GOSSIP_SECRET", DEFAULT_GOSSIP_SECRET))
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
        return [peer.strip().rstrip("/") for peer in self.peers_csv.split(",") if peer.strip()]

    @property
    def secret_bytes(self) -> bytes:
        return self.shared_secret.encode("utf-8")


@dataclass(slots=True)
class GenomeRecord:
    """Single genome record exchanged through gossip."""

    gid: str
    params: dict[str, float]
    fitness: float
    niche: str = "exploration"
    origin: str = ""
    lineage: list[str] = field(default_factory=list)
    ts: float = field(default_factory=time.time)
    ver: int = 0
    node: str = ""

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "gid": self.gid,
            "params": dict(self.params),
            "fitness": float(self.fitness),
            "niche": self.niche,
            "origin": self.origin,
            "lineage": list(self.lineage),
            "ts": float(self.ts),
            "ver": int(self.ver),
            "node": self.node,
        }

    @staticmethod
    def from_dict(gid: str, data: dict[str, Any]) -> Optional[GenomeRecord]:
        if not isinstance(data, dict):
            logger.warning("Invalid genome data type for gid=%s: %s", gid, type(data).__name__)
            return None

        clean_gid = str(data.get("gid") or gid or "").strip()
        if not clean_gid:
            logger.warning("Rejecting genome with empty gid.")
            return None

        params_raw = data.get("params")
        if not isinstance(params_raw, dict) or not params_raw:
            logger.warning("Rejecting genome %s: params must be a non-empty dict.", clean_gid)
            return None

        params: dict[str, float] = {}
        for key, value in params_raw.items():
            clean_key = str(key or "").strip()
            if not clean_key:
                return None

            number = _safe_float(value, float("nan"))
            if not math.isfinite(number):
                logger.warning("Rejecting genome %s: invalid param %s=%r", clean_gid, clean_key, value)
                return None

            params[clean_key] = number

        lineage_raw = data.get("lineage", [])
        lineage = [str(item) for item in lineage_raw if item is not None] if isinstance(lineage_raw, list) else []

        return GenomeRecord(
            gid=clean_gid,
            params=params,
            fitness=_safe_float(data.get("fitness"), 0.0),
            niche=str(data.get("niche", "exploration")),
            origin=str(data.get("origin", "")),
            lineage=lineage,
            ts=_safe_float(data.get("ts"), time.time()),
            ver=max(0, _safe_int(data.get("ver"), 0)),
            node=str(data.get("node", "")),
        )


@dataclass(slots=True)
class GossipEnvelope:
    """Authenticated gossip message envelope."""

    sender: str
    ts: float
    nonce: str
    versions: dict[str, int]
    delta: dict[str, dict[str, Any]]
    sig: str = ""

    def payload_bytes(self) -> bytes:
        payload = {
            "sender": self.sender,
            "ts": self.ts,
            "nonce": self.nonce,
            "versions": self.versions,
            "delta": self.delta,
        }
        return _json_dumps(payload).encode("utf-8")

    def sign(self, secret: bytes) -> str:
        self.sig = hmac.new(secret, self.payload_bytes(), hashlib.sha256).hexdigest()
        return self.sig

    def verify(self, secret: bytes) -> bool:
        if not self.sig:
            return False

        expected_sig = hmac.new(secret, self.payload_bytes(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_sig, self.sig)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sender": self.sender,
            "ts": self.ts,
            "nonce": self.nonce,
            "versions": dict(self.versions),
            "delta": dict(self.delta),
            "sig": self.sig,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Optional[GossipEnvelope]:
        if not isinstance(data, dict):
            return None

        sender = str(data.get("sender", "")).strip()
        nonce = str(data.get("nonce", "")).strip()
        if not sender or not nonce:
            logger.warning("Invalid gossip envelope: missing sender or nonce.")
            return None

        versions_raw = data.get("versions", {})
        delta_raw = data.get("delta", {})

        if not isinstance(versions_raw, dict) or not isinstance(delta_raw, dict):
            logger.warning("Invalid gossip envelope: versions and delta must be dicts.")
            return None

        versions: dict[str, int] = {}
        for key, value in versions_raw.items():
            versions[str(key)] = max(0, _safe_int(value, 0))

        delta: dict[str, dict[str, Any]] = {}
        for gid, payload in delta_raw.items():
            if isinstance(payload, dict):
                delta[str(gid)] = dict(payload)

        return GossipEnvelope(
            sender=sender,
            ts=_safe_float(data.get("ts"), 0.0),
            nonce=nonce,
            versions=versions,
            delta=delta,
            sig=str(data.get("sig", "")),
        )


@dataclass(slots=True)
class DeltaPolicy:
    """Configurable policy for accepting incoming genome deltas."""

    min_fitness: float = 0.0
    min_param_value: float = 0.0
    max_param_value: float = 10.0
    trusted_niches: tuple[str, ...] = ("survival", "capital", "exploration")
    niche_bonus: dict[str, float] = field(default_factory=dict)

    def accepts(self, genome: dict[str, Any], trust: float = 1.0) -> bool:
        if not isinstance(genome, dict):
            return False

        fitness = _safe_float(genome.get("fitness"), -1.0)
        if fitness < self.min_fitness:
            return False

        params = genome.get("params", {})
        if not isinstance(params, dict) or not params:
            return False

        for value in params.values():
            number = _safe_float(value, float("nan"))
            if not math.isfinite(number):
                return False
            if not (self.min_param_value <= number <= self.max_param_value):
                return False

        niche = str(genome.get("niche", "exploration"))
        if niche not in self.trusted_niches and niche not in self.niche_bonus:
            return False

        trust_probability = max(0.0, min(1.0, _safe_float(trust, 1.0)))
        return trust_probability >= 1.0 or random.random() < trust_probability


class SQLiteGenomeStore:
    """SQLite-backed storage for gossip genome records."""

    def __init__(self, path: str, node_id: str, ttl_s: int, max_state: int) -> None:
        clean_path = str(path or "").strip()
        clean_node_id = str(node_id or "").strip()

        if not clean_path:
            raise ValueError("SQLiteGenomeStore path cannot be empty")
        if not clean_node_id:
            raise ValueError("SQLiteGenomeStore node_id cannot be empty")

        self.path = clean_path
        self.node_id = clean_node_id
        self.ttl_s = max(0, int(ttl_s))
        self.max_state = max(1, int(max_state))
        self._lock = asyncio.Lock()
        self._version = 0

        Path(self.path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
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
                    logger.error("SQLite error during %s: %s", label, exc)
                    raise

                delay = SQLITE_WRITE_RETRY_DELAY_SECONDS * (2**attempt)
                logger.warning(
                    "SQLite locked during %s; retrying in %.3fs (%s/%s)",
                    label,
                    delay,
                    attempt + 1,
                    SQLITE_WRITE_RETRIES,
                )
                time.sleep(delay)

        if last_exc is not None:
            raise last_exc

        return None

    def _init_db(self) -> None:
        def write() -> None:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE;")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS genomes (
                        gid TEXT PRIMARY KEY NOT NULL,
                        payload TEXT NOT NULL,
                        fitness REAL NOT NULL,
                        ver INTEGER NOT NULL,
                        node TEXT NOT NULL,
                        ts REAL NOT NULL
                    ) STRICT
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_genomes_fitness_ts
                    ON genomes (fitness DESC, ts DESC)
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_genomes_node_ver ON genomes(node, ver);")
                conn.execute("COMMIT;")

        self._with_retry("initialize gossip store", write)

        with self._connect() as conn:
            row = conn.execute(
                "SELECT MAX(ver) AS max_ver FROM genomes WHERE node = ?",
                (self.node_id,),
            ).fetchone()
            self._version = int(row["max_ver"]) if row and row["max_ver"] is not None else 0

        logger.info(
            "SQLiteGenomeStore initialized for node %s at %s. Current local version: %s",
            self.node_id,
            self.path,
            self._version,
        )

    async def add(self, genome: GenomeRecord) -> str:
        if not isinstance(genome, GenomeRecord):
            raise TypeError("genome must be a GenomeRecord")

        async with self._lock:
            gid = str(genome.gid or uuid.uuid4())
            self._version += 1

            genome.gid = gid
            genome.ver = self._version
            genome.node = self.node_id
            genome.ts = time.time()

            payload = _json_dumps(genome.to_public_dict())

            def write() -> None:
                with self._connect() as conn:
                    conn.execute("BEGIN IMMEDIATE;")
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
                    conn.execute("COMMIT;")

            self._with_retry(f"add genome {gid}", write)
            return gid

    async def merge_many(self, remote: dict[str, dict[str, Any]]) -> int:
        if not isinstance(remote, dict):
            return 0

        merged_count = 0

        async with self._lock:
            def write() -> int:
                nonlocal merged_count
                with self._connect() as conn:
                    conn.execute("BEGIN IMMEDIATE;")

                    for gid, raw_genome_data in remote.items():
                        record = GenomeRecord.from_dict(str(gid), raw_genome_data)
                        if record is None:
                            continue

                        row = conn.execute(
                            "SELECT ver, node FROM genomes WHERE gid = ?",
                            (record.gid,),
                        ).fetchone()

                        should_write = False
                        if row is None:
                            should_write = True
                        else:
                            local_ver = int(row["ver"])
                            local_node = str(row["node"])
                            should_write = (record.ver, record.node) > (local_ver, local_node)

                        if not should_write:
                            continue

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
                            (
                                record.gid,
                                _json_dumps(record.to_public_dict()),
                                record.fitness,
                                record.ver,
                                record.node,
                                record.ts,
                            ),
                        )
                        merged_count += 1

                    conn.execute("COMMIT;")
                return merged_count

            result = self._with_retry("merge remote genomes", write)

        if result:
            logger.info("Merged %s remote genome(s).", result)

        return int(result or 0)

    async def versions(self) -> dict[str, int]:
        async with self._lock:
            with self._connect() as conn:
                rows = conn.execute("SELECT gid, ver FROM genomes").fetchall()
                return {str(row["gid"]): int(row["ver"]) for row in rows}

    async def delta(self, known_versions: dict[str, int]) -> dict[str, dict[str, Any]]:
        known = known_versions if isinstance(known_versions, dict) else {}

        async with self._lock:
            with self._connect() as conn:
                rows = conn.execute("SELECT gid, payload, ver FROM genomes").fetchall()

        out: dict[str, dict[str, Any]] = {}
        for row in rows:
            gid = str(row["gid"])
            ver = int(row["ver"])
            if _safe_int(known.get(gid), -1) < ver:
                try:
                    payload = json.loads(str(row["payload"]))
                    if isinstance(payload, dict):
                        out[gid] = payload
                except json.JSONDecodeError:
                    logger.warning("Skipping malformed genome payload for gid=%s", gid)

        return out

    async def top(self, n: int) -> list[dict[str, Any]]:
        limit = max(0, int(n))
        if limit == 0:
            return []

        async with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT payload FROM genomes ORDER BY fitness DESC, ts DESC LIMIT ?",
                    (limit,),
                ).fetchall()

        records: list[dict[str, Any]] = []
        for row in rows:
            try:
                payload = json.loads(str(row["payload"]))
                if isinstance(payload, dict):
                    records.append(payload)
            except json.JSONDecodeError:
                logger.warning("Skipping malformed genome payload in top().")

        return records

    async def prune(self) -> int:
        async with self._lock:
            now = time.time()

            def write() -> int:
                deleted_count = 0
                with self._connect() as conn:
                    conn.execute("BEGIN IMMEDIATE;")

                    cur = conn.execute("DELETE FROM genomes WHERE (? - ts) >= ?", (now, self.ttl_s))
                    deleted_count += max(0, cur.rowcount or 0)

                    row = conn.execute("SELECT COUNT(*) AS c FROM genomes").fetchone()
                    current_count = int(row["c"]) if row and row["c"] is not None else 0

                    if current_count > self.max_state:
                        rows = conn.execute(
                            """
                            SELECT gid FROM genomes
                            ORDER BY fitness DESC, ts DESC
                            LIMIT -1 OFFSET ?
                            """,
                            (self.max_state,),
                        ).fetchall()

                        gids = [str(row["gid"]) for row in rows]
                        if gids:
                            placeholders = ",".join("?" for _ in gids)
                            cur = conn.execute(
                                f"DELETE FROM genomes WHERE gid IN ({placeholders})",
                                tuple(gids),
                            )
                            deleted_count += max(0, cur.rowcount or 0)

                    conn.execute("COMMIT;")
                return deleted_count

            deleted = int(self._with_retry("prune gossip store", write) or 0)

        if deleted:
            logger.info("Pruned %s genome record(s).", deleted)

        return deleted

    async def size(self) -> int:
        async with self._lock:
            with self._connect() as conn:
                row = conn.execute("SELECT COUNT(*) AS c FROM genomes").fetchone()
                return int(row["c"]) if row and row["c"] is not None else 0


@dataclass(slots=True)
class PeerMetrics:
    """Operational health and backoff metrics for one peer."""

    score: float = 1.0
    successes: int = 0
    failures: int = 0
    last_seen: float = 0.0
    last_error: str = ""
    backoff_until: float = 0.0

    def mark_success(self) -> None:
        self.successes += 1
        self.last_seen = time.time()
        self.last_error = ""
        self.score = min(2.0, self.score * 1.03 + 0.01)
        self.backoff_until = 0.0

    def mark_failure(self, error: str) -> None:
        self.failures += 1
        self.last_error = str(error)[:200]
        self.score = max(0.2, self.score * 0.85)
        delay = min(60.0, 0.5 * (2 ** min(self.failures, 7)))
        self.backoff_until = time.time() + delay
        logger.warning(
            "Peer failure count=%s score=%.2f backoff=%.1fs error=%s",
            self.failures,
            self.score,
            delay,
            self.last_error,
        )

    def can_attempt(self) -> bool:
        return time.time() >= self.backoff_until


class GossipProtocol:
    """Core gossip protocol implementation."""

    def __init__(
        self,
        cfg: GossipConfig,
        store: SQLiteGenomeStore,
        policy: Optional[DeltaPolicy] = None,
    ) -> None:
        self.cfg = cfg
        self.store = store
        self.policy = policy or DeltaPolicy(min_fitness=cfg.min_fitness)
        self.peers = list(cfg.peers)
        self.peer_metrics: dict[str, PeerMetrics] = {peer: PeerMetrics() for peer in self.peers}
        self.peer_versions: dict[str, dict[str, int]] = {peer: {} for peer in self.peers}
        self.replay_cache: OrderedDict[tuple[str, str], float] = OrderedDict()
        self._replay_lock = asyncio.Lock()

    def _make_envelope(self, delta: dict[str, dict[str, Any]], versions: dict[str, int]) -> GossipEnvelope:
        envelope = GossipEnvelope(
            sender=self.cfg.node_id,
            ts=time.time(),
            nonce=uuid.uuid4().hex,
            versions=dict(versions),
            delta=dict(delta),
        )
        envelope.sign(self.cfg.secret_bytes)
        return envelope

    async def _remember_nonce(self, sender: str, nonce: str) -> bool:
        key = (sender, nonce)

        async with self._replay_lock:
            if key in self.replay_cache:
                logger.warning("Replay detected from sender=%s nonce=%s", sender, nonce)
                return False

            self.replay_cache[key] = time.time()
            self.replay_cache.move_to_end(key)

            while len(self.replay_cache) > self.cfg.replay_cache_size:
                self.replay_cache.popitem(last=False)

            return True

    def _fresh_enough(self, ts: float) -> bool:
        now = time.time()
        return abs(now - ts) <= self.cfg.max_clock_skew_s

    def _peer_allowed(self, peer_url: str) -> bool:
        metrics = self.peer_metrics.get(peer_url)
        return True if metrics is None else metrics.can_attempt()

    def _choose_peer(self) -> Optional[str]:
        candidates = [peer for peer in self.peers if self._peer_allowed(peer)]
        if not candidates:
            return None

        weights = [self.peer_metrics.get(peer, PeerMetrics()).score for peer in candidates]
        if sum(weights) <= 0:
            return random.choice(candidates)

        return random.choices(candidates, weights=weights, k=1)[0]

    def _filtered_delta(self, delta: dict[str, dict[str, Any]], trust: float) -> dict[str, dict[str, Any]]:
        if not isinstance(delta, dict):
            return {}

        return {
            str(gid): dict(genome)
            for gid, genome in delta.items()
            if isinstance(genome, dict) and self.policy.accepts(genome, trust=trust)
        }

    async def incoming(self, env_data: dict[str, Any]) -> web.Response:
        envelope = GossipEnvelope.from_dict(env_data)
        if envelope is None:
            return web.json_response({"error": "invalid_envelope"}, status=400)

        if envelope.sender == self.cfg.node_id:
            return web.json_response({"error": "self_message"}, status=400)

        metrics = self.peer_metrics.setdefault(envelope.sender, PeerMetrics())
        self.peer_versions.setdefault(envelope.sender, {})

        if not self._fresh_enough(envelope.ts):
            metrics.mark_failure("stale_envelope")
            return web.json_response({"error": "stale_envelope"}, status=400)

        if not envelope.verify(self.cfg.secret_bytes):
            metrics.mark_failure("bad_signature")
            return web.json_response({"error": "bad_signature"}, status=401)

        if not await self._remember_nonce(envelope.sender, envelope.nonce):
            metrics.mark_failure("replay_detected")
            return web.json_response({"error": "replay_detected"}, status=409)

        trust = metrics.score
        filtered_delta = self._filtered_delta(envelope.delta, trust=trust)
        merged = await self.store.merge_many(filtered_delta)

        local_versions = await self.store.versions()
        local_delta = await self.store.delta(envelope.versions)

        self.peer_versions[envelope.sender] = dict(envelope.versions)
        metrics.mark_success()

        logger.info(
            "Processed gossip from %s: merged=%s return_delta=%s score=%.2f",
            envelope.sender,
            merged,
            len(local_delta),
            metrics.score,
        )

        return web.json_response(
            {
                "ok": True,
                "merged": merged,
                "versions": local_versions,
                "delta": local_delta,
            }
        )

    async def sync_once(self, session: aiohttp.ClientSession, peer_url: str) -> None:
        peer = str(peer_url or "").strip().rstrip("/")
        if not peer:
            return

        metrics = self.peer_metrics.setdefault(peer, PeerMetrics())
        self.peer_versions.setdefault(peer, {})

        if not metrics.can_attempt():
            return

        try:
            known_versions = self.peer_versions.get(peer, {})
            local_versions = await self.store.versions()
            local_delta = await self.store.delta(known_versions)
            envelope = self._make_envelope(local_delta, local_versions)

            async with session.post(
                f"{peer}/gossip",
                json=envelope.to_dict(),
                timeout=self.cfg.request_timeout_s,
            ) as response:
                response.raise_for_status()
                data = await response.json()

            if not isinstance(data, dict):
                raise ValueError("peer response must be a JSON object")

            remote_versions_raw = data.get("versions", {})
            remote_delta_raw = data.get("delta", {})
            if not isinstance(remote_versions_raw, dict) or not isinstance(remote_delta_raw, dict):
                raise ValueError("peer response versions/delta must be dicts")

            remote_versions = {str(k): max(0, _safe_int(v, 0)) for k, v in remote_versions_raw.items()}
            self.peer_versions[peer] = remote_versions

            trust = metrics.score
            filtered_remote_delta = self._filtered_delta(remote_delta_raw, trust=trust)
            merged = await self.store.merge_many(filtered_remote_delta)

            metrics.mark_success()
            logger.info("Synced with %s: sent=%s merged=%s score=%.2f", peer, len(local_delta), merged, metrics.score)

        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            metrics.mark_failure(f"network_error: {exc}")
        except (json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
            metrics.mark_failure(f"protocol_error: {exc}")
        except Exception as exc:
            logger.exception("Unexpected gossip sync failure with %s: %s", peer, exc)
            metrics.mark_failure(f"unexpected_error: {exc}")

    async def sync_loop(self) -> None:
        timeout = aiohttp.ClientTimeout(total=float(self.cfg.request_timeout_s) + 1.0)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            logger.info("Gossip sync loop started interval=%.2fs peers=%s", self.cfg.gossip_interval_s, len(self.peers))

            while True:
                try:
                    peer = self._choose_peer()
                    if peer:
                        await self.sync_once(session, peer)
                except asyncio.CancelledError:
                    logger.info("Gossip sync loop cancelled.")
                    raise
                except Exception as exc:
                    logger.exception("Gossip sync loop iteration failed: %s", exc)

                await asyncio.sleep(max(0.1, float(self.cfg.gossip_interval_s)))

    def stats(self) -> dict[str, Any]:
        return {
            "node_id": self.cfg.node_id,
            "configured_peers": list(self.peers),
            "peer_metrics": {peer: asdict(metrics) for peer, metrics in self.peer_metrics.items()},
            "replay_cache_size": len(self.replay_cache),
        }


class GossipNode:
    """Lifecycle wrapper for gossip storage, protocol, and HTTP endpoints."""

    def __init__(self, cfg: GossipConfig, policy: Optional[DeltaPolicy] = None) -> None:
        self.cfg = cfg
        self.store = SQLiteGenomeStore(cfg.sqlite_path, cfg.node_id, cfg.ttl_s, cfg.max_state)
        self.protocol = GossipProtocol(cfg, self.store, policy=policy)
        self._bg_tasks: list[asyncio.Task[Any]] = []

    def build_app(self) -> web.Application:
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
        self._bg_tasks = [
            asyncio.create_task(self.protocol.sync_loop(), name="gossip_sync_loop"),
            asyncio.create_task(self._prune_loop(), name="gossip_prune_loop"),
        ]
        logger.info("GossipNode background tasks started.")

    async def on_cleanup(self, app: web.Application) -> None:
        for task in self._bg_tasks:
            task.cancel()

        if self._bg_tasks:
            await asyncio.gather(*self._bg_tasks, return_exceptions=True)

        self._bg_tasks.clear()
        logger.info("GossipNode cleanup complete.")

    async def _prune_loop(self) -> None:
        prune_interval = max(5.0, float(self.cfg.ttl_s) / 4.0)

        while True:
            try:
                await asyncio.sleep(prune_interval)
                deleted = await self.store.prune()
                if deleted:
                    logger.debug("Pruned %s gossip genome record(s).", deleted)
            except asyncio.CancelledError:
                logger.info("Gossip prune loop cancelled.")
                raise
            except Exception as exc:
                logger.exception("Gossip prune loop failed: %s", exc)

    async def handle_gossip(self, request: web.Request) -> web.Response:
        try:
            payload = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "invalid_json"}, status=400)
        except Exception as exc:
            logger.warning("Failed to read gossip request JSON: %s", exc)
            return web.json_response({"error": "request_payload_error"}, status=400)

        if not isinstance(payload, dict):
            return web.json_response({"error": "invalid_payload"}, status=400)

        return await self.protocol.incoming(payload)

    async def handle_health(self, request: web.Request) -> web.Response:
        return web.json_response(
            {
                "ok": True,
                "node_id": self.cfg.node_id,
                "peer_count": len(self.cfg.peers),
                "status": "running",
            }
        )

    async def handle_stats(self, request: web.Request) -> web.Response:
        return web.json_response(
            {
                "node_id": self.cfg.node_id,
                "store_size": await self.store.size(),
                "protocol": self.protocol.stats(),
            }
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    cfg = GossipConfig()
    logger.info("Starting GossipNode node_id=%s bind=%s:%s", cfg.node_id, cfg.bind_host, cfg.port)
    web.run_app(GossipNode(cfg).build_app(), host=cfg.bind_host, port=cfg.port)


if __name__ == "__main__":
    main()