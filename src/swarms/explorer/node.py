#!/usr/bin/env python3
"""Explorer Node – fetcher/extractor with SQLite memory, event chain, robots policy,
allowlist/blocklist filtering, and per-domain rate limiting.

Adds:
- event_chain table for full parent/child traceability.
- robots.txt support with caching.
- allowlist/blocklist policy for domains and URL prefixes.
- per-domain fetch window limiting to avoid noisy sources.
- explicit provenance on all emitted CRDT records.
- target_received -> fetch_started -> content_extracted/fetch_failed -> finding_published chain.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple, TypedDict
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import httpx

from src.core.crdt_adapter import CRDTAdapter
from swarm_config import config

def fingerprint_text(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger(__name__)


EventType = Literal[
    "target_received",
    "fetch_started",
    "fetch_failed",
    "content_extracted",
    "finding_published",
]


class ExplorerEvent(TypedDict, total=False):
    type: Literal["explorer_event"]
    event_type: EventType
    gid: str
    source_gid: str
    parent_gid: Optional[str]
    timestamp: float
    provenance: Dict[str, Any]
    data: Dict[str, Any]


class ExplorerFinding(TypedDict, total=False):
    type: Literal["explorer_finding"]
    event_type: Literal["finding_published"]
    gid: str
    source_gid: str
    url: Optional[str]
    domain: Optional[str]
    content_preview: Optional[str]
    content_hash: Optional[str]
    fetch_status: str
    fetch_error: Optional[str]
    classification: Literal["USEFUL", "HARMFUL", "NEUTRAL", "unclassified"]
    confidence: float
    reason: str
    timestamp: float
    provenance: Dict[str, Any]


TRACKING_PARAMS_PREFIXES = ("utm_",)
TRACKING_PARAMS_EXACT = {"fbclid", "gclid", "msclkid", "ref", "source", "spm"}


@dataclass
class NodePolicy:
    allow_domains: List[str] = field(default_factory=list)
    block_domains: List[str] = field(default_factory=list)
    allow_url_prefixes: List[str] = field(default_factory=list)
    block_url_prefixes: List[str] = field(default_factory=list)
    respect_robots: bool = True
    user_agent: str = "ExplorerNode/3.0"
    domain_window_seconds: int = 300
    max_fetches_per_domain_window: int = 3

    @classmethod
    def from_env(cls) -> "NodePolicy":
        def split_csv(name: str) -> List[str]:
            raw = (config.get(name) if hasattr(config, "get") else None) or ""
            if not raw:
                import os
                raw = os.environ.get(name, "")
            return [x.strip().lower() for x in raw.split(",") if x.strip()]

        def get_int(name: str, default: int) -> int:
            import os
            try:
                return int(os.environ.get(name, str(default)))
            except Exception:
                return default

        def get_bool(name: str, default: bool) -> bool:
            import os
            raw = os.environ.get(name)
            if raw is None:
                return default
            return raw.strip().lower() in {"1", "true", "yes", "on"}

        return cls(
            allow_domains=split_csv("EXPLORER_ALLOW_DOMAINS"),
            block_domains=split_csv("EXPLORER_BLOCK_DOMAINS"),
            allow_url_prefixes=[x for x in split_csv("EXPLORER_ALLOW_URL_PREFIXES")],
            block_url_prefixes=[x for x in split_csv("EXPLORER_BLOCK_URL_PREFIXES")],
            respect_robots=get_bool("EXPLORER_RESPECT_ROBOTS", True),
            user_agent=(split_csv("EXPLORER_USER_AGENT") or ["ExplorerNode/3.0"])[0],
            domain_window_seconds=get_int("EXPLORER_DOMAIN_WINDOW_SECONDS", 300),
            max_fetches_per_domain_window=get_int("EXPLORER_MAX_FETCHES_PER_DOMAIN_WINDOW", 3),
        )


@dataclass
class NodeMemory:
    db_path: Path

    def __post_init__(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS seen_targets (
                    url TEXT PRIMARY KEY,
                    normalized_url TEXT NOT NULL,
                    domain TEXT,
                    first_seen_ts INTEGER NOT NULL,
                    last_seen_ts INTEGER NOT NULL,
                    seen_count INTEGER NOT NULL DEFAULT 1,
                    last_event_gid TEXT,
                    metadata_json TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS event_chain (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER NOT NULL,
                    event_gid TEXT NOT NULL,
                    parent_gid TEXT,
                    source_gid TEXT,
                    event_type TEXT NOT NULL,
                    url TEXT,
                    domain TEXT,
                    status TEXT,
                    content_hash TEXT,
                    provenance_json TEXT DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_event_chain_parent ON event_chain(parent_gid);
                CREATE INDEX IF NOT EXISTS idx_event_chain_source ON event_chain(source_gid);
                CREATE INDEX IF NOT EXISTS idx_event_chain_type ON event_chain(event_type);

                CREATE TABLE IF NOT EXISTS fetch_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    event_gid TEXT NOT NULL,
                    source_gid TEXT,
                    url TEXT,
                    domain TEXT,
                    status TEXT NOT NULL,
                    http_status INTEGER,
                    error TEXT,
                    content_hash TEXT,
                    content_bytes INTEGER DEFAULT 0,
                    provenance_json TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS content_hashes (
                    content_hash TEXT PRIMARY KEY,
                    first_seen_ts INTEGER NOT NULL,
                    last_seen_ts INTEGER NOT NULL,
                    seen_count INTEGER NOT NULL DEFAULT 1,
                    sample_url TEXT,
                    sample_domain TEXT
                );

                CREATE TABLE IF NOT EXISTS findings (
                    source_gid TEXT PRIMARY KEY,
                    event_gid TEXT NOT NULL,
                    url TEXT,
                    domain TEXT,
                    content_hash TEXT,
                    classification TEXT DEFAULT 'unclassified',
                    confidence REAL DEFAULT 0.0,
                    reason TEXT DEFAULT '',
                    fetch_status TEXT DEFAULT '',
                    fetch_error TEXT DEFAULT '',
                    first_seen_ts INTEGER NOT NULL,
                    last_seen_ts INTEGER NOT NULL,
                    provenance_json TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS domain_state (
                    domain TEXT PRIMARY KEY,
                    first_seen_ts INTEGER NOT NULL,
                    last_seen_ts INTEGER NOT NULL,
                    fetch_count INTEGER NOT NULL DEFAULT 0,
                    window_start_ts INTEGER NOT NULL,
                    window_fetch_count INTEGER NOT NULL DEFAULT 0,
                    last_status TEXT DEFAULT '',
                    robots_allowed INTEGER DEFAULT 1,
                    robots_checked_ts INTEGER DEFAULT 0,
                    robots_json TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS robots_cache (
                    domain TEXT PRIMARY KEY,
                    fetched_ts INTEGER NOT NULL,
                    allowed INTEGER NOT NULL DEFAULT 1,
                    crawl_delay REAL DEFAULT NULL,
                    robots_txt TEXT DEFAULT ''
                );
                """
            )

    def remember_target(self, url: str, event_gid: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        ts = int(time.time())
        domain = extract_domain(url)
        with self._connect() as conn:
            row = conn.execute("SELECT url FROM seen_targets WHERE url = ?", (url,)).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO seen_targets (
                        url, normalized_url, domain, first_seen_ts, last_seen_ts,
                        seen_count, last_event_gid, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (url, url, domain, ts, ts, event_gid, json.dumps(metadata or {}, ensure_ascii=False)),
                )
                return True

            conn.execute(
                """
                UPDATE seen_targets
                SET last_seen_ts = ?, seen_count = seen_count + 1, last_event_gid = ?, metadata_json = ?
                WHERE url = ?
                """,
                (ts, event_gid, json.dumps(metadata or {}, ensure_ascii=False), url),
            )
            return False

    def seen_target(self, url: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT url FROM seen_targets WHERE url = ?", (url,)).fetchone()
        return row is not None

    def record_event_chain(
        self,
        *,
        event_gid: str,
        event_type: EventType,
        source_gid: Optional[str],
        parent_gid: Optional[str],
        url: Optional[str],
        status: Optional[str] = None,
        content_hash: Optional[str] = None,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> None:
        ts = int(time.time())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO event_chain (
                    ts, event_gid, parent_gid, source_gid, event_type, url, domain,
                    status, content_hash, provenance_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    event_gid,
                    parent_gid,
                    source_gid,
                    event_type,
                    url,
                    extract_domain(url),
                    status,
                    content_hash,
                    json.dumps(provenance or {}, ensure_ascii=False),
                ),
            )

    def record_fetch_event(
        self,
        *,
        event_type: EventType,
        event_gid: str,
        source_gid: Optional[str],
        parent_gid: Optional[str],
        url: str,
        status: str,
        http_status: Optional[int] = None,
        error: Optional[str] = None,
        content_hash: Optional[str] = None,
        content_bytes: int = 0,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> None:
        ts = int(time.time())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO fetch_events (
                    ts, event_type, event_gid, source_gid, url, domain,
                    status, http_status, error, content_hash, content_bytes, provenance_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    event_type,
                    event_gid,
                    source_gid,
                    url,
                    extract_domain(url),
                    status,
                    http_status,
                    error,
                    content_hash,
                    content_bytes,
                    json.dumps(provenance or {}, ensure_ascii=False),
                ),
            )
            self._upsert_domain_state(
                conn,
                domain=extract_domain(url) or "",
                status=status,
                robots_allowed=provenance.get("robots_allowed") if provenance else None,
                content_hash=content_hash,
            )
        self.record_event_chain(
            event_gid=event_gid,
            event_type=event_type,
            source_gid=source_gid,
            parent_gid=parent_gid,
            url=url,
            status=status,
            content_hash=content_hash,
            provenance=provenance,
        )
        if content_hash:
            self._record_content_hash(url=url, content_hash=content_hash)

    def _upsert_domain_state(
        self,
        conn: sqlite3.Connection,
        *,
        domain: str,
        status: str,
        robots_allowed: Optional[int] = None,
        content_hash: Optional[str] = None,
    ) -> None:
        if not domain:
            return
        ts = int(time.time())
        row = conn.execute("SELECT domain, window_start_ts, window_fetch_count, fetch_count FROM domain_state WHERE domain = ?", (domain,)).fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO domain_state (
                    domain, first_seen_ts, last_seen_ts, fetch_count,
                    window_start_ts, window_fetch_count, last_status,
                    robots_allowed, robots_checked_ts, robots_json
                ) VALUES (?, ?, ?, 1, ?, 1, ?, COALESCE(?, 1), ?, ?)
                """,
                (
                    domain,
                    ts,
                    ts,
                    ts,
                    status,
                    robots_allowed,
                    ts if robots_allowed is not None else 0,
                    json.dumps({"last_content_hash": content_hash} if content_hash else {}, ensure_ascii=False),
                ),
            )
            return

        window_start = int(row["window_start_ts"] or ts)
        window_count = int(row["window_fetch_count"] or 0)
        if ts - window_start > self._domain_window_seconds():
            window_start = ts
            window_count = 0
        window_count += 1

        conn.execute(
            """
            UPDATE domain_state
            SET last_seen_ts = ?,
                fetch_count = fetch_count + 1,
                window_start_ts = ?,
                window_fetch_count = ?,
                last_status = ?,
                robots_allowed = COALESCE(?, robots_allowed),
                robots_checked_ts = CASE WHEN ? IS NOT NULL THEN ? ELSE robots_checked_ts END,
                robots_json = CASE
                    WHEN ? IS NOT NULL THEN json_set(COALESCE(robots_json, '{}'), '$.last_content_hash', ?)
                    ELSE robots_json
                END
            WHERE domain = ?
            """,
            (
                ts,
                window_start,
                window_count,
                status,
                robots_allowed,
                robots_allowed,
                ts,
                content_hash,
                content_hash,
                domain,
            ),
        )

    def _domain_window_seconds(self) -> int:
        return int(getattr(config, "explorer_domain_window_seconds", 300) or 300)

    def _record_content_hash(self, url: str, content_hash: str) -> None:
        ts = int(time.time())
        with self._connect() as conn:
            row = conn.execute("SELECT content_hash FROM content_hashes WHERE content_hash = ?", (content_hash,)).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO content_hashes (
                        content_hash, first_seen_ts, last_seen_ts, seen_count, sample_url, sample_domain
                    ) VALUES (?, ?, ?, 1, ?, ?)
                    """,
                    (content_hash, ts, ts, url, extract_domain(url)),
                )
            else:
                conn.execute(
                    """
                    UPDATE content_hashes
                    SET last_seen_ts = ?, seen_count = seen_count + 1
                    WHERE content_hash = ?
                    """,
                    (ts, content_hash),
                )

    def seen_content(self, content_hash: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT content_hash FROM content_hashes WHERE content_hash = ?", (content_hash,)).fetchone()
        return row is not None

    def remember_finding(self, finding: ExplorerFinding) -> None:
        source_gid = str(finding.get("source_gid") or finding.get("gid") or "").strip()
        if not source_gid:
            return
        ts = int(finding.get("timestamp") or time.time())
        with self._connect() as conn:
            row = conn.execute("SELECT source_gid FROM findings WHERE source_gid = ?", (source_gid,)).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO findings (
                        source_gid, event_gid, url, domain, content_hash, classification, confidence,
                        reason, fetch_status, fetch_error, first_seen_ts, last_seen_ts, provenance_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_gid,
                        str(finding.get("gid") or source_gid),
                        finding.get("url"),
                        finding.get("domain") or extract_domain(finding.get("url")),
                        finding.get("content_hash"),
                        finding.get("classification", "unclassified"),
                        float(finding.get("confidence", 0.0) or 0.0),
                        finding.get("reason", "") or "",
                        finding.get("fetch_status", "") or "",
                        finding.get("fetch_error", "") or "",
                        ts,
                        ts,
                        json.dumps(finding.get("provenance") or {}, ensure_ascii=False),
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE findings
                    SET event_gid = ?,
                        url = COALESCE(NULLIF(?, ''), url),
                        domain = COALESCE(NULLIF(?, ''), domain),
                        content_hash = COALESCE(NULLIF(?, ''), content_hash),
                        classification = ?,
                        confidence = ?,
                        reason = ?,
                        fetch_status = ?,
                        fetch_error = ?,
                        last_seen_ts = ?,
                        provenance_json = ?
                    WHERE source_gid = ?
                    """,
                    (
                        str(finding.get("gid") or source_gid),
                        finding.get("url") or "",
                        finding.get("domain") or extract_domain(finding.get("url")),
                        finding.get("content_hash") or None,
                        finding.get("classification", "unclassified"),
                        float(finding.get("confidence", 0.0) or 0.0),
                        finding.get("reason", "") or "",
                        finding.get("fetch_status", "") or "",
                        finding.get("fetch_error", "") or "",
                        ts,
                        json.dumps(finding.get("provenance") or {}, ensure_ascii=False),
                        source_gid,
                    ),
                )

    def has_seen_finding(self, source_gid: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT source_gid FROM findings WHERE source_gid = ?", (source_gid,)).fetchone()
        return row is not None

    def get_recent_unclassified(self, limit: int = 8) -> List[ExplorerFinding]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM findings
                WHERE classification = 'unclassified'
                ORDER BY last_seen_ts DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        out: List[ExplorerFinding] = []
        for r in rows:
            out.append(
                {
                    "type": "explorer_finding",
                    "source_gid": str(r["source_gid"]),
                    "url": r["url"],
                    "domain": r["domain"],
                    "content_preview": None,
                    "content_hash": r["content_hash"],
                    "fetch_status": str(r["fetch_status"] or ""),
                    "fetch_error": str(r["fetch_error"] or "") or None,
                    "classification": "unclassified",
                    "confidence": float(r["confidence"] or 0.0),
                    "reason": str(r["reason"] or ""),
                    "timestamp": float(r["last_seen_ts"]),
                    "gid": str(r["event_gid"]),
                    "provenance": json.loads(r["provenance_json"] or "{}"),
                }
            )
        return out

    def get_recent_domain_fetches(self, domain: str, since_ts: int) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM fetch_events
                WHERE domain = ? AND ts >= ?
                """,
                (domain, since_ts),
            ).fetchone()
        return int(row["cnt"] if row else 0)

    def can_fetch_domain(self, domain: str, policy: NodePolicy) -> Tuple[bool, str]:
        if not domain:
            return False, "missing_domain"
        now = int(time.time())
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM domain_state WHERE domain = ?", (domain,)).fetchone()

        if row is not None:
            window_start = int(row["window_start_ts"] or now)
            window_count = int(row["window_fetch_count"] or 0)
            if now - window_start <= policy.domain_window_seconds and window_count >= policy.max_fetches_per_domain_window:
                return False, "domain_window_rate_limited"

        return True, "ok"

    def mark_domain_fetch(self, domain: str) -> None:
        if not domain:
            return
        ts = int(time.time())
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM domain_state WHERE domain = ?", (domain,)).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO domain_state (
                        domain, first_seen_ts, last_seen_ts, fetch_count,
                        window_start_ts, window_fetch_count, last_status,
                        robots_allowed, robots_checked_ts, robots_json
                    ) VALUES (?, ?, ?, 1, ?, 1, 'ok', 1, 0, '{}')
                    """,
                    (domain, ts, ts, ts),
                )
            else:
                window_start = int(row["window_start_ts"] or ts)
                window_count = int(row["window_fetch_count"] or 0)
                if ts - window_start > getattr(config, "explorer_domain_window_seconds", 300):
                    window_start = ts
                    window_count = 0
                window_count += 1
                conn.execute(
                    """
                    UPDATE domain_state
                    SET last_seen_ts = ?,
                        fetch_count = fetch_count + 1,
                        window_start_ts = ?,
                        window_fetch_count = ?,
                        last_status = 'ok'
                    WHERE domain = ?
                    """,
                    (ts, window_start, window_count, domain),
                )

    def record_robots_cache(self, domain: str, allowed: bool, crawl_delay: Optional[float], robots_txt: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO robots_cache (domain, fetched_ts, allowed, crawl_delay, robots_txt)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(domain) DO UPDATE SET
                    fetched_ts = excluded.fetched_ts,
                    allowed = excluded.allowed,
                    crawl_delay = excluded.crawl_delay,
                    robots_txt = excluded.robots_txt
                """,
                (domain, int(time.time()), 1 if allowed else 0, crawl_delay, robots_txt[:20000]),
            )

    def get_robots_cache(self, domain: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM robots_cache WHERE domain = ?", (domain,)).fetchone()
        return dict(row) if row else None

    def top_domains(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT domain, COUNT(*) AS cnt
                FROM findings
                WHERE domain IS NOT NULL AND domain != ''
                GROUP BY domain
                ORDER BY cnt DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


# ----------------------------
# Helpers
# ----------------------------


def normalize_url(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    if raw.startswith("www."):
        raw = "https://" + raw
    parsed = urlparse(raw)
    if not parsed.scheme:
        parsed = urlparse("https://" + raw.lstrip("/"))

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = re.sub(r"/+$", "", parsed.path or "") or "/"

    filtered_qs = []
    for k, v in parse_qsl(parsed.query, keep_blank_values=True):
        lk = k.lower()
        if lk in TRACKING_PARAMS_EXACT or any(lk.startswith(p) for p in TRACKING_PARAMS_PREFIXES):
            continue
        filtered_qs.append((k, v))

    query = urlencode(filtered_qs, doseq=True)
    return urlunparse((scheme, netloc, path, "", query, ""))


def extract_domain(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        return urlparse(url).netloc.lower() or None
    except Exception:
        return None


def is_valid_http_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


# ----------------------------
# Explorer node
# ----------------------------


class ExplorerNode:
    def __init__(self, memory_db: Path = Path("./data/explorer_node_memory.sqlite3")) -> None:
        self.node_id = f"exp-node-{uuid.uuid4().hex[:8]}"
        self.crdt = CRDTAdapter(node_id=self.node_id, db_path=config.crdt_db_path)
        self.memory = NodeMemory(memory_db)
        self.policy = NodePolicy.from_env()
        self.http_timeout = httpx.Timeout(20.0, connect=10.0)
        self.batch_limit = 10
        self.step = 0
        self.idle_backoff_s = 1.0
        self.robots_parser_cache: Dict[str, RobotFileParser] = {}
        logger.info("🧭 ExplorerNode initialized: %s", self.node_id)

    async def run(self) -> None:
        logger.info("🧭 ExplorerNode %s started", self.node_id)
        async with httpx.AsyncClient(
            timeout=self.http_timeout,
            follow_redirects=True,
            headers={"User-Agent": self.policy.user_agent},
        ) as client:
            while True:
                self.step += 1
                try:
                    did_work = await self._consume_targets_and_explore(client)
                    self.idle_backoff_s = 1.0 if did_work else min(self.idle_backoff_s * 1.5, 30.0)
                except Exception as e:
                    logger.error("ExplorerNode loop error: %s", e, exc_info=True)
                    self.idle_backoff_s = min(self.idle_backoff_s * 2.0, 60.0)
                await asyncio.sleep(self.idle_backoff_s)

    async def _consume_targets_and_explore(self, client: httpx.AsyncClient) -> bool:
        targets = self._collect_targets()
        if not targets:
            return False

        targets = targets[: self.batch_limit]
        did_work = False
        for url in targets:
            try:
                await self._fetch_and_emit(client, url)
                did_work = True
            except Exception as e:
                logger.warning("Failed to explore %s: %s", url, e)
        return did_work

    def _collect_targets(self) -> List[str]:
        urls: List[str] = []
        seen_local: set[str] = set()

        for v in self.crdt.state.values():
            if not isinstance(v, dict):
                continue
            if v.get("type") != "explorer_targets":
                continue

            data = v.get("data") if isinstance(v.get("data"), dict) else {}
            raw_urls = data.get("urls", []) if isinstance(data, dict) else []
            event_gid = str(v.get("gid") or "").strip()
            source_gids = v.get("source_gids") if isinstance(v.get("source_gids"), list) else []
            provenance = v.get("provenance") if isinstance(v.get("provenance"), dict) else {}

            for raw in raw_urls:
                if not isinstance(raw, str):
                    continue
                url = normalize_url(raw)
                if not self._passes_policy(url):
                    continue
                if url in seen_local or self.memory.seen_target(url):
                    continue

                seen_local.add(url)
                self.memory.remember_target(url, event_gid=event_gid, metadata={"source_gids": source_gids, "provenance": provenance})
                self._record_event_chain(
                    event_type="target_received",
                    event_gid=f"exp_evt_{int(time.time())}_{uuid.uuid4().hex[:6]}",
                    source_gid=event_gid or url,
                    parent_gid=event_gid or None,
                    url=url,
                    status="received",
                    provenance={"source_gids": source_gids, "provenance": provenance, "agent": self.node_id},
                )
                urls.append(url)

        return urls

    def _passes_policy(self, url: str) -> bool:
        if not is_valid_http_url(url):
            return False

        parsed = urlparse(url)
        domain = (parsed.netloc or "").lower()
        if not domain:
            return False

        if self.policy.allow_domains and not any(domain == d or domain.endswith("." + d) for d in self.policy.allow_domains):
            return False
        if any(domain == d or domain.endswith("." + d) for d in self.policy.block_domains):
            return False

        if self.policy.allow_url_prefixes and not any(url.startswith(prefix) for prefix in self.policy.allow_url_prefixes):
            return False
        if any(url.startswith(prefix) for prefix in self.policy.block_url_prefixes):
            return False

        return True

    async def _fetch_and_emit(self, client: httpx.AsyncClient, url: str) -> None:
        if not url:
            return

        target_gid = f"exp_tgt_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        fetch_gid = f"exp_fetch_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        domain = extract_domain(url) or ""

        allowed, reason = self.memory.can_fetch_domain(domain, self.policy)
        if not allowed:
            logger.info("⏭️ Skipping %s due to domain policy: %s", url, reason)
            self._record_event_chain(
                event_type="fetch_failed",
                event_gid=fetch_gid,
                source_gid=target_gid,
                parent_gid=None,
                url=url,
                status=reason,
                provenance={"agent": self.node_id, "policy_reason": reason},
            )
            return

        robots_allowed, crawl_delay = await self._robots_allows(client, url)
        if self.policy.respect_robots and not robots_allowed:
            logger.info("⛔ robots.txt disallowed %s", url)
            self.memory.record_fetch_event(
                event_type="fetch_failed",
                event_gid=fetch_gid,
                source_gid=target_gid,
                parent_gid=None,
                url=url,
                status="robots_disallowed",
                http_status=None,
                error="robots.txt disallowed",
                content_hash=None,
                content_bytes=0,
                provenance={"agent": self.node_id, "robots_allowed": False},
            )
            return

        provenance = {
            "agent": self.node_id,
            "target_gid": target_gid,
            "url": url,
            "timestamp": time.time(),
            "robots_allowed": robots_allowed,
            "crawl_delay": crawl_delay,
        }

        self._record_event_chain(
            event_type="fetch_started",
            event_gid=fetch_gid,
            source_gid=target_gid,
            parent_gid=None,
            url=url,
            status="started",
            provenance=provenance,
        )

        try:
            resp = await client.get(url)
            http_status = resp.status_code
            status = "ok" if http_status < 400 else f"http_{http_status}"
            text = resp.text or ""
            content_hash = fingerprint_text(text)
            content_bytes = len(text.encode("utf-8", errors="ignore"))

            self.memory.record_fetch_event(
                event_type="content_extracted",
                event_gid=fetch_gid,
                source_gid=target_gid,
                parent_gid=fetch_gid,
                url=url,
                status=status,
                http_status=http_status,
                error=None,
                content_hash=content_hash,
                content_bytes=content_bytes,
                provenance=provenance,
            )
            self.memory.mark_domain_fetch(domain)

            if self.memory.seen_content(content_hash):
                logger.debug("Skipping duplicate content hash for %s", url)
                return

            preview = make_content_preview(text)
            finding: ExplorerFinding = {
                "type": "explorer_finding",
                "event_type": "finding_published",
                "gid": f"exp_find_{int(time.time())}_{uuid.uuid4().hex[:6]}",
                "source_gid": target_gid,
                "url": url,
                "domain": domain,
                "content_preview": preview,
                "content_hash": content_hash,
                "fetch_status": status,
                "fetch_error": None,
                "classification": "unclassified",
                "confidence": 0.0,
                "reason": "page fetched and preview extracted",
                "timestamp": time.time(),
                "provenance": {
                    "agent": self.node_id,
                    "parent_gid": fetch_gid,
                    "target_gid": target_gid,
                    "fetch_status": status,
                    "http_status": http_status,
                    "content_hash": content_hash,
                    "content_bytes": content_bytes,
                    "robots_allowed": robots_allowed,
                },
            }

            self.memory.record_fetch_event(
                event_type="finding_published",
                event_gid=finding["gid"],
                source_gid=target_gid,
                parent_gid=fetch_gid,
                url=url,
                status=status,
                http_status=http_status,
                error=None,
                content_hash=content_hash,
                content_bytes=content_bytes,
                provenance=finding["provenance"],
            )
            self.memory.remember_finding(finding)
            await self._emit_crdt(finding)
            logger.info("📥 Emitted finding for %s (%s)", url, status)

        except Exception as e:
            err = str(e)[:500]
            self.memory.record_fetch_event(
                event_type="fetch_failed",
                event_gid=fetch_gid,
                source_gid=target_gid,
                parent_gid=fetch_gid,
                url=url,
                status="error",
                http_status=None,
                error=err,
                content_hash=None,
                content_bytes=0,
                provenance=provenance,
            )
            self._record_event_chain(
                event_type="fetch_failed",
                event_gid=fetch_gid,
                source_gid=target_gid,
                parent_gid=None,
                url=url,
                status="error",
                provenance={"agent": self.node_id, "error": err},
            )
            finding: ExplorerFinding = {
                "type": "explorer_finding",
                "event_type": "finding_published",
                "gid": f"exp_find_{int(time.time())}_{uuid.uuid4().hex[:6]}",
                "source_gid": target_gid,
                "url": url,
                "domain": domain,
                "content_preview": None,
                "content_hash": None,
                "fetch_status": "error",
                "fetch_error": err,
                "classification": "unclassified",
                "confidence": 0.0,
                "reason": "fetch failed",
                "timestamp": time.time(),
                "provenance": {
                    "agent": self.node_id,
                    "parent_gid": fetch_gid,
                    "target_gid": target_gid,
                    "error": err,
                },
            }
            self.memory.remember_finding(finding)
            await self._emit_crdt(finding)
            logger.warning("🌐 Fetch failed for %s: %s", url, e)

    async def _robots_allows(self, client: httpx.AsyncClient, url: str) -> Tuple[bool, Optional[float]]:
        if not self.policy.respect_robots:
            return True, None

        domain = extract_domain(url)
        if not domain:
            return False, None

        cached = self.memory.get_robots_cache(domain)
        if cached is not None:
            allowed = bool(cached.get("allowed", 1))
            crawl_delay = cached.get("crawl_delay")
            return allowed, float(crawl_delay) if crawl_delay is not None else None

        robots_url = f"{urlparse(url).scheme}://{domain}/robots.txt"
        rp = RobotFileParser()
        try:
            resp = await client.get(robots_url)
            robots_txt = resp.text if resp.status_code < 400 else ""
            rp.parse(robots_txt.splitlines())
            allowed = rp.can_fetch(self.policy.user_agent, url)
            crawl_delay = rp.crawl_delay(self.policy.user_agent)
            self.robots_parser_cache[domain] = rp
            self.memory.record_robots_cache(domain, allowed=allowed, crawl_delay=crawl_delay, robots_txt=robots_txt)
            return allowed, crawl_delay
        except Exception as e:
            logger.debug("robots.txt fetch failed for %s: %s", domain, e)
            # Conservative default: if robots cannot be fetched, allow but log/cache a soft pass.
            self.memory.record_robots_cache(domain, allowed=True, crawl_delay=None, robots_txt="")
            return True, None

    def _record_event_chain(
        self,
        *,
        event_type: EventType,
        event_gid: str,
        source_gid: Optional[str],
        parent_gid: Optional[str],
        url: Optional[str],
        status: Optional[str] = None,
        content_hash: Optional[str] = None,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.memory.record_event_chain(
            event_gid=event_gid,
            event_type=event_type,
            source_gid=source_gid,
            parent_gid=parent_gid,
            url=url,
            status=status,
            content_hash=content_hash,
            provenance=provenance,
        )

    async def _emit_crdt(self, record: ExplorerEvent | ExplorerFinding) -> None:
        await self.crdt.add_genome(record)  # type: ignore[arg-type]


if __name__ == "__main__":
    node = ExplorerNode()
    try:
        asyncio.run(node.run())
    except KeyboardInterrupt:
        logger.info("ExplorerNode stopped by user (KeyboardInterrupt).")
    except Exception as e:
        logger.critical("ExplorerNode encountered a fatal error: %s", e, exc_info=True)
