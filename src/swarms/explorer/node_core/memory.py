from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from swarm_config import config
from .policy import NodePolicy
from .types import EventType, ExplorerFinding
from .utils import extract_domain, normalize_url


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
        normalized = normalize_url(url)
        domain = extract_domain(normalized)
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)

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
                    (url, normalized, domain, ts, ts, event_gid, metadata_json),
                )
                return True

            conn.execute(
                """
                UPDATE seen_targets
                SET last_seen_ts = ?, seen_count = seen_count + 1, last_event_gid = ?, metadata_json = ?
                WHERE url = ?
                """,
                (ts, event_gid, metadata_json, url),
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
        domain = extract_domain(url)

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
                    domain,
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
                domain=domain or "",
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

    def _domain_window_seconds(self) -> int:
        return int(getattr(config, "explorer_domain_window_seconds", 300) or 300)

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
        row = conn.execute(
            "SELECT domain, window_start_ts, window_fetch_count FROM domain_state WHERE domain = ?",
            (domain,),
        ).fetchone()

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
        url = finding.get("url") or ""
        domain = finding.get("domain") or extract_domain(url) or ""
        provenance_json = json.dumps(finding.get("provenance") or {}, ensure_ascii=False)

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
                        url,
                        domain,
                        finding.get("content_hash"),
                        finding.get("classification", "unclassified"),
                        float(finding.get("confidence", 0.0) or 0.0),
                        finding.get("reason", "") or "",
                        finding.get("fetch_status", "") or "",
                        finding.get("fetch_error", "") or "",
                        ts,
                        ts,
                        provenance_json,
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
                        url,
                        domain,
                        finding.get("content_hash") or None,
                        finding.get("classification", "unclassified"),
                        float(finding.get("confidence", 0.0) or 0.0),
                        finding.get("reason", "") or "",
                        finding.get("fetch_status", "") or "",
                        finding.get("fetch_error", "") or "",
                        ts,
                        provenance_json,
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
                "SELECT COUNT(*) AS cnt FROM fetch_events WHERE domain = ? AND ts >= ?",
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

    def mark_domain_fetch(self, domain: str, policy: Optional[NodePolicy] = None) -> None:
        if not domain:
            return

        ts = int(time.time())
        window_seconds = policy.domain_window_seconds if policy else self._domain_window_seconds()

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
                return

            window_start = int(row["window_start_ts"] or ts)
            window_count = int(row["window_fetch_count"] or 0)
            if ts - window_start > window_seconds:
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
        return [dict(row) for row in rows]