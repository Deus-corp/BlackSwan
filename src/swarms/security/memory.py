#!/usr/bin/env python3
"""SQLite-backed security memory and event chain storage."""

from __future__ import annotations
from dataclasses import dataclass, field

import json
import os
import sqlite3
import time
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TypedDict, Literal

from urllib.parse import urlparse

SecurityEventType = Literal[
    "heartbeat_received",
    "heartbeat_sent",
    "incident_observed",
    "policy_evaluated",
    "command_issued",
    "command_received",
    "command_applied",
    "threat_suspected",
    "block_applied",
    "unblock_applied",
    "integrity_alert",
    "vulnerability_alert",
    "open_ports_detected",
]


class SecurityEvent(TypedDict, total=False):
    type: Literal["security_event"]
    event_type: SecurityEventType
    gid: str
    source_gid: str
    parent_gid: Optional[str]
    timestamp: float
    provenance: Dict[str, Any]
    data: Dict[str, Any]


class SecurityCommand(TypedDict, total=False):
    type: Literal["sec_command"]
    event_type: Literal["command_issued"]
    gid: str
    source_gid: str
    parent_gid: Optional[str]
    timestamp: float
    expires_at: float
    provenance: Dict[str, Any]
    data: Dict[str, Any]

@dataclass
class FirewallPolicy:
    """Stored firewall policy."""
    rules: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: float = 0.0

@dataclass
class SecurityPolicy:
    """High-level security policy."""
    allow_emergency_flush: bool = False
    auto_unblock_after: int = 3600
    max_blocked_ips: int = 1000


class SecurityMemory:
    """SQLite-backed persistence for security agents."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
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

                CREATE TABLE IF NOT EXISTS observed_heartbeats (
                    node_id TEXT PRIMARY KEY,
                    source_gid TEXT,
                    last_seen_ts INTEGER NOT NULL,
                    blocked_ips INTEGER DEFAULT 0,
                    status TEXT DEFAULT '',
                    provenance_json TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS security_incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER NOT NULL,
                    event_gid TEXT NOT NULL,
                    source_gid TEXT,
                    parent_gid TEXT,
                    incident_type TEXT NOT NULL,
                    severity REAL DEFAULT 0.0,
                    details_json TEXT DEFAULT '{}',
                    provenance_json TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS policy_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER NOT NULL,
                    event_gid TEXT NOT NULL,
                    parent_gid TEXT,
                    decision TEXT NOT NULL,
                    confidence REAL DEFAULT 0.0,
                    rationale TEXT DEFAULT '',
                    model_name TEXT DEFAULT '',
                    prompt_hash TEXT DEFAULT '',
                    provenance_json TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS command_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER NOT NULL,
                    event_gid TEXT NOT NULL,
                    parent_gid TEXT,
                    command_type TEXT NOT NULL,
                    target_node_id TEXT,
                    action TEXT NOT NULL,
                    expires_at INTEGER NOT NULL,
                    provenance_json TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS blocked_ips (
                    ip TEXT PRIMARY KEY,
                    source TEXT DEFAULT '',
                    reason TEXT DEFAULT '',
                    blocked_at INTEGER NOT NULL,
                    last_seen_at INTEGER NOT NULL,
                    unblock_requested_at INTEGER DEFAULT 0,
                    unblock_applied_at INTEGER DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 1,
                    metadata_json TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS command_receipts (
                    command_gid TEXT PRIMARY KEY,
                    received_at INTEGER NOT NULL,
                    applied_at INTEGER DEFAULT 0,
                    status TEXT NOT NULL,
                    action TEXT NOT NULL,
                    provenance_json TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS event_chain (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER NOT NULL,
                    event_gid TEXT NOT NULL,
                    parent_gid TEXT,
                    source_gid TEXT,
                    event_type TEXT NOT NULL,
                    action TEXT DEFAULT '',
                    target_node_id TEXT DEFAULT '',
                    target_ip TEXT DEFAULT '',
                    status TEXT DEFAULT '',
                    details_json TEXT DEFAULT '{}',
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

                CREATE INDEX IF NOT EXISTS idx_event_chain_parent ON event_chain(parent_gid);
                CREATE INDEX IF NOT EXISTS idx_event_chain_source ON event_chain(source_gid);
                CREATE INDEX IF NOT EXISTS idx_event_chain_type ON event_chain(event_type);
                """
            )

    def _json(self, obj: Any) -> str:
        return json.dumps(obj, ensure_ascii=False)

    def record_event_chain(
        self,
        *,
        event_gid: str,
        parent_gid: Optional[str],
        source_gid: Optional[str],
        event_type: SecurityEventType,
        action: str = "",
        target_node_id: str = "",
        target_ip: str = "",
        status: str = "",
        details: Optional[Dict[str, Any]] = None,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO event_chain (ts, event_gid, parent_gid, source_gid, event_type, action, target_node_id, target_ip, status, details_json, provenance_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(time.time()),
                    event_gid,
                    parent_gid,
                    source_gid,
                    event_type,
                    action,
                    target_node_id,
                    target_ip,
                    status,
                    self._json(details or {}),
                    self._json(provenance or {}),
                ),
            )

    def upsert_heartbeat(self, *, node_id: str, source_gid: str, blocked_ips: int, status: str, provenance: Dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO observed_heartbeats (node_id, source_gid, last_seen_ts, blocked_ips, status, provenance_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    source_gid = excluded.source_gid,
                    last_seen_ts = excluded.last_seen_ts,
                    blocked_ips = excluded.blocked_ips,
                    status = excluded.status,
                    provenance_json = excluded.provenance_json
                """,
                (node_id, source_gid, int(time.time()), blocked_ips, status, self._json(provenance)),
            )

    def record_incident(
        self,
        *,
        event_gid: str,
        source_gid: Optional[str],
        parent_gid: Optional[str],
        incident_type: str,
        severity: float,
        details: Dict[str, Any],
        provenance: Dict[str, Any],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO security_incidents (ts, event_gid, source_gid, parent_gid, incident_type, severity, details_json, provenance_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (int(time.time()), event_gid, source_gid, parent_gid, incident_type, severity, self._json(details), self._json(provenance)),
            )

    def record_policy_decision(
        self,
        *,
        event_gid: str,
        parent_gid: Optional[str],
        decision: str,
        confidence: float,
        rationale: str,
        model_name: str,
        prompt_hash: str,
        provenance: Dict[str, Any],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO policy_decisions (ts, event_gid, parent_gid, decision, confidence, rationale, model_name, prompt_hash, provenance_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (int(time.time()), event_gid, parent_gid, decision, confidence, rationale, model_name, prompt_hash, self._json(provenance)),
            )

    def record_command(
        self,
        *,
        event_gid: str,
        parent_gid: Optional[str],
        command_type: str,
        target_node_id: Optional[str],
        action: str,
        expires_at: int,
        provenance: Dict[str, Any],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO command_events (ts, event_gid, parent_gid, command_type, target_node_id, action, expires_at, provenance_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (int(time.time()), event_gid, parent_gid, command_type, target_node_id, action, expires_at, self._json(provenance)),
            )

    def record_receipt(self, command_gid: str, action: str, provenance: Dict[str, Any], status: str = "received") -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO command_receipts (command_gid, received_at, applied_at, status, action, provenance_json)
                VALUES (?, ?, 0, ?, ?, ?)
                ON CONFLICT(command_gid) DO UPDATE SET
                    status = excluded.status,
                    action = excluded.action,
                    provenance_json = excluded.provenance_json
                """,
                (command_gid, int(time.time()), status, action, self._json(provenance)),
            )

    def mark_receipt_applied(self, command_gid: str, status: str = "applied") -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE command_receipts SET applied_at = ?, status = ? WHERE command_gid = ?",
                (int(time.time()), status, command_gid),
            )

    def receipt_seen(self, command_gid: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT command_gid FROM command_receipts WHERE command_gid = ?", (command_gid,)).fetchone()
        return row is not None

    def record_block(self, ip: str, source: str, reason: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        now = int(time.time())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO blocked_ips (ip, source, reason, blocked_at, last_seen_at, active, metadata_json)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(ip) DO UPDATE SET
                    source = excluded.source,
                    reason = excluded.reason,
                    last_seen_at = excluded.last_seen_at,
                    active = 1,
                    metadata_json = excluded.metadata_json
                """,
                (ip, source, reason, now, now, self._json(metadata or {})),
            )

    def record_unblock_request(self, ip: Optional[str]) -> None:
        now = int(time.time())
        with self._connect() as conn:
            if ip is None:
                conn.execute("UPDATE blocked_ips SET unblock_requested_at = ? WHERE active = 1", (now,))
            else:
                conn.execute("UPDATE blocked_ips SET unblock_requested_at = ? WHERE ip = ?", (now, ip))

    def record_unblock_applied(self, ip: Optional[str]) -> None:
        now = int(time.time())
        with self._connect() as conn:
            if ip is None:
                conn.execute("UPDATE blocked_ips SET unblock_applied_at = ?, active = 0 WHERE active = 1", (now,))
            else:
                conn.execute("UPDATE blocked_ips SET unblock_applied_at = ?, active = 0 WHERE ip = ?", (now, ip))

    def is_recently_blocked(self, ip: str, cooldown_seconds: int) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT blocked_at FROM blocked_ips WHERE ip = ?", (ip,)).fetchone()
        if row is None:
            return False
        return int(time.time()) - int(row[0]) < cooldown_seconds

    def active_block_count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM blocked_ips WHERE active = 1").fetchone()
        return int(row["cnt"] if row else 0)

    def list_active_blocks(self) -> List[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT ip FROM blocked_ips WHERE active = 1 ORDER BY blocked_at DESC").fetchall()
        return [str(r[0]) for r in rows]

    def recent_heartbeats(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM observed_heartbeats ORDER BY last_seen_ts DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def recent_incidents(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM security_incidents ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

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
                if ts - window_start > 300:
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

    def can_fetch_domain(self, domain: str, max_per_window: int = 3, window_seconds: int = 300) -> Tuple[bool, str]:
        if not domain:
            return False, "missing_domain"
        now = int(time.time())
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM domain_state WHERE domain = ?", (domain,)).fetchone()
        if row is not None:
            window_start = int(row["window_start_ts"] or now)
            window_count = int(row["window_fetch_count"] or 0)
            if now - window_start <= window_seconds and window_count >= max_per_window:
                return False, "domain_window_rate_limited"
        return True, "ok"

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
    
def command_exists(cmd: str) -> bool:
    """Check if a command exists in PATH."""
    return shutil.which(cmd) is not None

def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return parsed.hostname or ""

def new_gid() -> str:
    """Generate a new globally unique identifier."""
    return str(uuid.uuid4())