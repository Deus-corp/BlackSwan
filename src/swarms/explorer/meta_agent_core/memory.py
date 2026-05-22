from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .types import ClassificationItem, EventType, ExplorerFinding
from .utils import extract_domain, normalize_url


@dataclass
class MetaAgentMemory:
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

                CREATE TABLE IF NOT EXISTS observed_findings (
                    source_gid TEXT PRIMARY KEY,
                    event_gid TEXT NOT NULL,
                    url TEXT,
                    domain TEXT,
                    content_hash TEXT,
                    first_seen_ts INTEGER NOT NULL,
                    last_seen_ts INTEGER NOT NULL,
                    classification TEXT DEFAULT 'unclassified',
                    confidence REAL DEFAULT 0.0,
                    reason TEXT DEFAULT '',
                    fetch_status TEXT DEFAULT '',
                    fetch_error TEXT DEFAULT '',
                    provenance_json TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS classification_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER NOT NULL,
                    event_gid TEXT NOT NULL,
                    parent_gid TEXT,
                    source_gid TEXT NOT NULL,
                    url TEXT,
                    classification TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    reason TEXT NOT NULL,
                    model_name TEXT,
                    prompt_hash TEXT,
                    provenance_json TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS target_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER NOT NULL,
                    event_gid TEXT NOT NULL,
                    parent_gid TEXT,
                    source_gids_json TEXT NOT NULL,
                    urls_json TEXT NOT NULL,
                    prompt_hash TEXT,
                    score REAL DEFAULT 0.0,
                    provenance_json TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS url_state (
                    url TEXT PRIMARY KEY,
                    normalized_url TEXT NOT NULL,
                    domain TEXT,
                    first_seen_ts INTEGER NOT NULL,
                    last_seen_ts INTEGER NOT NULL,
                    seen_count INTEGER NOT NULL DEFAULT 1,
                    last_score REAL DEFAULT 0.0,
                    last_classification TEXT DEFAULT '',
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

                CREATE INDEX IF NOT EXISTS idx_meta_event_chain_parent ON event_chain(parent_gid);
                CREATE INDEX IF NOT EXISTS idx_meta_event_chain_source ON event_chain(source_gid);
                CREATE INDEX IF NOT EXISTS idx_meta_event_chain_type ON event_chain(event_type);
                """
            )

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
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO event_chain (
                    ts, event_gid, parent_gid, source_gid, event_type, url, domain,
                    status, content_hash, provenance_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(time.time()),
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

    def observe_finding(self, finding: ExplorerFinding) -> None:
        source_gid = str(finding.get("source_gid") or finding.get("gid") or "").strip()
        if not source_gid:
            return

        ts = int(finding.get("timestamp") or time.time())
        url = finding.get("url") or ""
        domain = finding.get("domain") or extract_domain(url)
        event_gid = str(finding.get("gid") or source_gid)

        with self._connect() as conn:
            row = conn.execute(
                "SELECT source_gid FROM observed_findings WHERE source_gid = ?",
                (source_gid,),
            ).fetchone()

            if row is None:
                conn.execute(
                    """
                    INSERT INTO observed_findings (
                        source_gid, event_gid, url, domain, content_hash, first_seen_ts, last_seen_ts,
                        classification, confidence, reason, fetch_status, fetch_error, provenance_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_gid,
                        event_gid,
                        url,
                        domain,
                        finding.get("content_hash") or None,
                        ts,
                        ts,
                        finding.get("classification", "unclassified"),
                        float(finding.get("confidence", 0.0) or 0.0),
                        finding.get("reason", "") or "",
                        finding.get("fetch_status", "") or "",
                        finding.get("fetch_error", "") or "",
                        json.dumps(finding.get("provenance") or {}, ensure_ascii=False),
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE observed_findings
                    SET event_gid = ?,
                        url = COALESCE(NULLIF(?, ''), url),
                        domain = COALESCE(NULLIF(?, ''), domain),
                        content_hash = COALESCE(NULLIF(?, ''), content_hash),
                        last_seen_ts = ?,
                        classification = ?,
                        confidence = ?,
                        reason = ?,
                        fetch_status = ?,
                        fetch_error = ?,
                        provenance_json = ?
                    WHERE source_gid = ?
                    """,
                    (
                        event_gid,
                        url,
                        domain,
                        finding.get("content_hash") or None,
                        ts,
                        finding.get("classification", "unclassified"),
                        float(finding.get("confidence", 0.0) or 0.0),
                        finding.get("reason", "") or "",
                        finding.get("fetch_status", "") or "",
                        finding.get("fetch_error", "") or "",
                        json.dumps(finding.get("provenance") or {}, ensure_ascii=False),
                        source_gid,
                    ),
                )

    def record_classification(
        self,
        item: ClassificationItem,
        *,
        event_gid: str,
        parent_gid: Optional[str],
        prompt_hash: str,
        model_name: str,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> None:
        ts = int(time.time())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO classification_events (
                    ts, event_gid, parent_gid, source_gid, url, classification,
                    confidence, reason, model_name, prompt_hash, provenance_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    event_gid,
                    parent_gid,
                    item["source_gid"],
                    item.get("url"),
                    item["classification"],
                    float(item["confidence"]),
                    item["reason"],
                    model_name,
                    prompt_hash,
                    json.dumps(provenance or {}, ensure_ascii=False),
                ),
            )
            conn.execute(
                """
                UPDATE observed_findings
                SET classification = ?, confidence = ?, reason = ?, last_seen_ts = ?
                WHERE source_gid = ?
                """,
                (
                    item["classification"],
                    float(item["confidence"]),
                    item["reason"],
                    ts,
                    item["source_gid"],
                ),
            )

    def record_targets(
        self,
        urls: List[str],
        source_gids: List[str],
        *,
        event_gid: str,
        parent_gid: Optional[str],
        prompt_hash: str,
        score: float,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> None:
        ts = int(time.time())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO target_events (
                    ts, event_gid, parent_gid, source_gids_json, urls_json, prompt_hash, score, provenance_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    event_gid,
                    parent_gid,
                    json.dumps(source_gids, ensure_ascii=False),
                    json.dumps(urls, ensure_ascii=False),
                    prompt_hash,
                    score,
                    json.dumps(provenance or {}, ensure_ascii=False),
                ),
            )

            for url in urls:
                normalized = normalize_url(url)
                conn.execute(
                    """
                    INSERT INTO url_state (
                        url, normalized_url, domain, first_seen_ts, last_seen_ts, seen_count,
                        last_score, last_classification, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, 1, ?, '', '{}')
                    ON CONFLICT(url) DO UPDATE SET
                        last_seen_ts = excluded.last_seen_ts,
                        seen_count = seen_count + 1,
                        last_score = excluded.last_score,
                        normalized_url = excluded.normalized_url,
                        domain = excluded.domain
                    """,
                    (url, normalized, extract_domain(normalized), ts, ts, score),
                )

    def seen_target(self, url: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT url FROM url_state WHERE url = ?", (url,)).fetchone()
        return row is not None

    def remember_target(self, url: str, score: float, classification: str = "") -> None:
        ts = int(time.time())
        normalized = normalize_url(url)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO url_state (
                    url, normalized_url, domain, first_seen_ts, last_seen_ts, seen_count,
                    last_score, last_classification, metadata_json
                ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, '{}')
                ON CONFLICT(url) DO UPDATE SET
                    last_seen_ts = excluded.last_seen_ts,
                    seen_count = seen_count + 1,
                    last_score = excluded.last_score,
                    last_classification = excluded.last_classification,
                    normalized_url = excluded.normalized_url,
                    domain = excluded.domain
                """,
                (url, normalized, extract_domain(normalized), ts, ts, score, classification),
            )

    def get_top_domains(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT domain, COUNT(*) AS cnt
                FROM observed_findings
                WHERE domain IS NOT NULL AND domain != ''
                GROUP BY domain
                ORDER BY cnt DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_recent_unclassified(self, limit: int = 8) -> List[ExplorerFinding]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM observed_findings
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

    def get_last_event_gid(self, event_type: EventType) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT event_gid FROM event_chain WHERE event_type = ? ORDER BY ts DESC, id DESC LIMIT 1",
                (event_type,),
            ).fetchone()
        return str(row["event_gid"]) if row else None
