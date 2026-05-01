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
        return [p.strip() for p in self.peers_csv.split(",") if p.strip()]

    @property
    def secret_bytes(self) -> bytes:
        return self.shared_secret.encode("utf-8")


# =========================
# DOMAIN MODELS
# =========================

@dataclass(slots=True)
class GenomeRecord:
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
    sender: str
    ts: float
    nonce: str
    versions: Dict[str, int]
    delta: Dict[str, Dict[str, Any]]
    sig: str = ""

    def payload_bytes(self) -> bytes:
        payload = {
            "sender": self.sender,
            "ts": self.ts,
            "nonce": self.nonce,
            "versions": self.versions,
            "delta": self.delta,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def sign(self, secret: bytes) -> str:
        self.sig = hmac.new(secret, self.payload_bytes(), hashlib.sha256).hexdigest()
        return self.sig

    def verify(self, secret: bytes) -> bool:
        if not self.sig:
            return False
        expected = hmac.new(secret, self.payload_bytes(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, self.sig)

    def to_dict(self) -> Dict[str, Any]:
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
    def __init__(self, path: str, node_id: str, ttl_s: int, max_state: int):
        self.path = path
        self.node_id = node_id
        self.ttl_s = ttl_s
        self.max_state = max_state
        self._lock = asyncio.Lock()
        self._version = 0
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
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
        merged = 0
        async with self._lock:
            with self._connect() as conn:
                for gid, raw in remote.items():
                    rec = GenomeRecord.from_dict(gid, raw)
                    if rec is None:
                        continue

                    row = conn.execute("SELECT payload, ver, node FROM genomes WHERE gid = ?", (gid,)).fetchone()
                    if row is None:
                        payload = json.dumps(rec.to_public_dict(), sort_keys=True, separators=(",", ":"))
                        conn.execute(
                            "INSERT INTO genomes(gid, payload, fitness, ver, node, ts) VALUES(?, ?, ?, ?, ?, ?)",
                            (gid, payload, rec.fitness, rec.ver, rec.node, rec.ts),
                        )
                        merged += 1
                    else:
                        local_ver = int(row["ver"])
                        local_node = str(row["node"])
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
        async with self._lock:
            with self._connect() as conn:
                rows = conn.execute("SELECT gid, ver FROM genomes").fetchall()
                return {str(r["gid"]): int(r["ver"]) for r in rows}

    async def delta(self, known_versions: Dict[str, int]) -> Dict[str, Dict[str, Any]]:
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
        async with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT payload FROM genomes ORDER BY fitness DESC, ts DESC LIMIT ?",
                    (n,),
                ).fetchall()
                return [json.loads(str(r["payload"])) for r in rows]

    async def prune(self) -> int:
        async with self._lock:
            now = time.time()
            deleted = 0
            with self._connect() as conn:
                cur = conn.execute("DELETE FROM genomes WHERE (? - ts) >= ?", (now, self.ttl_s))
                deleted += cur.rowcount if cur.rowcount is not None else 0

                count = conn.execute("SELECT COUNT(*) AS c FROM genomes").fetchone()["c"]
                if count > self.max_state:
                    overflow = int(count - self.max_state)
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
        async with self._lock:
            with self._connect() as conn:
                row = conn.execute("SELECT COUNT(*) AS c FROM genomes").fetchone()
                return int(row["c"])


# =========================
# PEER METRICS
# =========================

@dataclass(slots=True)
class PeerMetrics:
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
        self.last_error = error[:200]
        self.score = max(0.2, self.score * 0.85)
        delay = min(30.0, 0.5 * (2 ** min(self.failures, 6)))
        self.backoff_until = time.time() + delay

    def can_attempt(self) -> bool:
        return time.time() >= self.backoff_until


# =========================
# GOSSIP PROTOCOL
# =========================

def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        v = float(value)
        if v != v:
            return default
        return v
    except (TypeError, ValueError):
        return default


class GossipProtocol:
    def __init__(
        self,
        cfg: GossipConfig,
        store: SQLiteGenomeStore,
        policy: Optional[DeltaPolicy] = None,
    ):
        self.cfg = cfg
        self.store = store
        self.policy = policy or DeltaPolicy(min_fitness=cfg.min_fitness)
        self.peers = cfg.peers
        self.peer_metrics: Dict[str, PeerMetrics] = {p: PeerMetrics() for p in self.peers}
        self.peer_versions: Dict[str, Dict[str, int]] = {p: {} for p in self.peers}
        self.replay_cache: Dict[Tuple[str, str], float] = {}
        self.replay_order: list[Tuple[str, str]] = []
        self._replay_lock = asyncio.Lock()

    def _make_envelope(self, delta: Dict[str, Dict[str, Any]], versions: Dict[str, int]) -> GossipEnvelope:
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
        key = (sender, nonce)
        async with self._replay_lock:
            if key in self.replay_cache:
                return False
            self.replay_cache[key] = time.time()
            self.replay_order.append(key)
            while len(self.replay_order) > self.cfg.replay_cache_size:
                old = self.replay_order.pop(0)
                self.replay_cache.pop(old, None)
            return True

    def _fresh_enough(self, ts: float) -> bool:
        return abs(time.time() - ts) <= self.cfg.max_clock_skew_s

    def _peer_allowed(self, peer: str) -> bool:
        metrics = self.peer_metrics.get(peer)
        return metrics is not None and metrics.can_attempt()

    def _choose_peer(self) -> Optional[str]:
        candidates = [p for p in self.peers if self._peer_allowed(p)]
        if not candidates:
            return None
        weights = [self.peer_metrics[p].score for p in candidates]
        return random.choices(candidates, weights=weights, k=1)[0]

    def _filtered_delta(self, delta: Dict[str, Dict[str, Any]], trust: float) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for gid, genome in delta.items():
            if self.policy.accepts(genome, trust=trust):
                out[gid] = genome
        return out

    async def incoming(self, env_data: Dict[str, Any]) -> web.Response:
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

        if env.sender not in self.peer_metrics:
            self.peer_metrics[env.sender] = PeerMetrics()
            self.peer_versions[env.sender] = {}

        trust = self.peer_metrics[env.sender].score
        merged = await self.store.merge_many(self._filtered_delta(env.delta, trust=trust))
        local_versions = await self.store.versions()
        local_delta = await self.store.delta(env.versions)

        self.peer_versions[env.sender] = dict(env.versions)
        self.peer_metrics[env.sender].mark_success()

        return web.json_response({
            "ok": True,
            "merged": merged,
            "versions": local_versions,
            "delta": local_delta,
        })

    async def sync_once(self, session: aiohttp.ClientSession, peer: str) -> None:
        if peer not in self.peer_metrics:
            self.peer_metrics[peer] = PeerMetrics()
            self.peer_versions[peer] = {}

        if not self._peer_allowed(peer):
            return

        try:
            known_versions = self.peer_versions.get(peer, {})
            local_versions = await self.store.versions()
            local_delta = await self.store.delta(known_versions)
            env = self._make_envelope(local_delta, local_versions)

            async with session.post(
                f"{peer}/gossip",
                json=env.to_dict(),
                timeout=self.cfg.request_timeout_s,
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()

            remote_versions = data.get("versions", {})
            remote_delta = data.get("delta", {})

            if isinstance(remote_versions, dict):
                self.peer_versions[peer] = {str(k): int(v) for k, v in remote_versions.items()}

            if isinstance(remote_delta, dict):
                trust = self.peer_metrics[peer].score
                await self.store.merge_many(self._filtered_delta(remote_delta, trust=trust))

            self.peer_metrics[peer].mark_success()

        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError, TypeError) as e:
            self.peer_metrics[peer].mark_failure(str(e))
        except Exception as e:
            self.peer_metrics[peer].mark_failure(str(e))

    async def sync_loop(self) -> None:
        timeout = aiohttp.ClientTimeout(total=self.cfg.request_timeout_s + 1.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            while True:
                peer = self._choose_peer()
                if peer:
                    await self.sync_once(session, peer)
                await asyncio.sleep(self.cfg.gossip_interval_s)

    def stats(self) -> Dict[str, Any]:
        return {
            "node_id": self.cfg.node_id,
            "peers": self.peers,
            "peer_metrics": {peer: asdict(metrics) for peer, metrics in self.peer_metrics.items()},
        }


# =========================
# NODE + HTTP APP
# =========================

class GossipNode:
    def __init__(self, cfg: GossipConfig, policy: Optional[DeltaPolicy] = None):
        self.cfg = cfg
        self.store = SQLiteGenomeStore(cfg.sqlite_path, cfg.node_id, cfg.ttl_s, cfg.max_state)
        self.protocol = GossipProtocol(cfg, self.store, policy=policy)
        self._bg_tasks: list[asyncio.Task] = []

    def build_app(self) -> web.Application:
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
        self._bg_tasks.append(asyncio.create_task(self.protocol.sync_loop()))
        self._bg_tasks.append(asyncio.create_task(self._prune_loop()))

    async def on_cleanup(self, app: web.Application) -> None:
        for task in self._bg_tasks:
            task.cancel()
        await asyncio.gather(*self._bg_tasks, return_exceptions=True)

    async def _prune_loop(self) -> None:
        while True:
            await asyncio.sleep(max(5.0, self.cfg.ttl_s / 4))
            await self.store.prune()

    async def handle_gossip(self, request: web.Request) -> web.Response:
        try:
            payload = await request.json()
        except Exception:
            return web.json_response({"error": "invalid_json"}, status=400)
        return await self.protocol.incoming(payload)

    async def handle_health(self, request: web.Request) -> web.Response:
        return web.json_response({
            "ok": True,
            "node_id": self.cfg.node_id,
            "peer_count": len(self.cfg.peers),
        })

    async def handle_stats(self, request: web.Request) -> web.Response:
        size = await self.store.size()
        return web.json_response({
            "node_id": self.cfg.node_id,
            "store_size": size,
            "protocol": self.protocol.stats(),
        })


def main() -> None:
    cfg = GossipConfig()
    node = GossipNode(cfg)
    app = node.build_app()
    web.run_app(app, host=cfg.bind_host, port=cfg.port)


if __name__ == "__main__":
    main()
