#!/usr/bin/env python3
"""SQLite-backed security memory and shared runtime models."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import time
import uuid

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TypedDict, Literal
from urllib.parse import urlparse


# =========================================================
# Event types
# =========================================================

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


# =========================================================
# Shared event schemas
# =========================================================

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


# =========================================================
# Firewall policy
# =========================================================

@dataclass
class FirewallPolicy:
    chain_name: str = "SEC_AGENT_INPUT"

    allowlist_ips: List[str] = field(default_factory=list)
    blocklist_ips: List[str] = field(default_factory=list)

    per_ip_cooldown_seconds: int = 300

    max_blocked_ips: int = 1000

    allow_emergency_flush_input: bool = False

    @classmethod
    def from_env(cls) -> "FirewallPolicy":
        return cls(
            chain_name=os.getenv(
                "SEC_CHAIN_NAME",
                "SEC_AGENT_INPUT",
            ),

            allowlist_ips=[
                x.strip()
                for x in os.getenv(
                    "SEC_ALLOWLIST_IPS",
                    "",
                ).split(",")
                if x.strip()
            ],

            blocklist_ips=[
                x.strip()
                for x in os.getenv(
                    "SEC_BLOCKLIST_IPS",
                    "",
                ).split(",")
                if x.strip()
            ],

            per_ip_cooldown_seconds=int(
                os.getenv(
                    "SEC_PER_IP_COOLDOWN_SECONDS",
                    "300",
                )
            ),

            max_blocked_ips=int(
                os.getenv(
                    "SEC_MAX_BLOCKED_IPS",
                    "1000",
                )
            ),

            allow_emergency_flush_input=(
                os.getenv(
                    "SEC_ALLOW_EMERGENCY_FLUSH_INPUT",
                    "false",
                ).lower() == "true"
            ),
        )


# =========================================================
# Meta-agent policy
# =========================================================

@dataclass
class SecurityPolicy:
    allow_global_unblock: bool = True

    allow_emergency_flush_input: bool = False

    require_llm_confirmation: bool = False

    heartbeat_staleness_seconds: int = 180

    unblock_threshold_heartbeats: int = 2

    max_blocked_ips_soft: int = 200

    auto_unblock_after: int = 3600

    @classmethod
    def from_env(cls) -> "SecurityPolicy":
        return cls(
            allow_global_unblock=os.getenv(
                "SEC_ALLOW_GLOBAL_UNBLOCK",
                "true",
            ).lower() == "true",

            allow_emergency_flush_input=os.getenv(
                "SEC_ALLOW_EMERGENCY_FLUSH_INPUT",
                "false",
            ).lower() == "true",

            require_llm_confirmation=os.getenv(
                "SEC_REQUIRE_LLM_CONFIRMATION",
                "false",
            ).lower() == "true",

            heartbeat_staleness_seconds=int(
                os.getenv(
                    "SEC_HEARTBEAT_STALENESS_SECONDS",
                    "180",
                )
            ),

            unblock_threshold_heartbeats=int(
                os.getenv(
                    "SEC_UNBLOCK_THRESHOLD_HEARTBEATS",
                    "2",
                )
            ),

            max_blocked_ips_soft=int(
                os.getenv(
                    "SEC_MAX_BLOCKED_IPS_SOFT",
                    "200",
                )
            ),

            auto_unblock_after=int(
                os.getenv(
                    "SEC_AUTO_UNBLOCK_AFTER",
                    "3600",
                )
            ),
        )


# =========================================================
# Security memory
# =========================================================

class SecurityMemory:
    """SQLite-backed persistence."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")

            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS blocked_ips (
                    ip TEXT PRIMARY KEY,
                    source TEXT,
                    reason TEXT,
                    blocked_at INTEGER,
                    last_seen_at INTEGER,
                    active INTEGER DEFAULT 1,
                    metadata_json TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS command_receipts (
                    command_gid TEXT PRIMARY KEY,
                    received_at INTEGER,
                    applied_at INTEGER DEFAULT 0,
                    status TEXT,
                    action TEXT,
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

                CREATE INDEX IF NOT EXISTS idx_event_chain_parent
                ON event_chain(parent_gid);

                CREATE INDEX IF NOT EXISTS idx_event_chain_source
                ON event_chain(source_gid);

                CREATE INDEX IF NOT EXISTS idx_event_chain_type
                ON event_chain(event_type);
                """
            )

    def _serialize(self, obj: Any) -> str:
        return json.dumps(obj or {}, ensure_ascii=False)

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
                INSERT INTO event_chain (
                    ts,
                    event_gid,
                    parent_gid,
                    source_gid,
                    event_type,
                    action,
                    target_node_id,
                    target_ip,
                    status,
                    details_json,
                    provenance_json
                )
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
                    self._serialize(details),
                    self._serialize(provenance),
                ),
            )

    def record_block(
        self,
        ip: str,
        source: str,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:

        now = int(time.time())

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO blocked_ips (
                    ip,
                    source,
                    reason,
                    blocked_at,
                    last_seen_at,
                    active,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, 1, ?)

                ON CONFLICT(ip)
                DO UPDATE SET
                    source=excluded.source,
                    reason=excluded.reason,
                    last_seen_at=excluded.last_seen_at,
                    active=1,
                    metadata_json=excluded.metadata_json
                """,
                (
                    ip,
                    source,
                    reason,
                    now,
                    now,
                    self._serialize(metadata),
                ),
            )

    def is_recently_blocked(
        self,
        ip: str,
        cooldown_seconds: int,
    ) -> bool:

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT blocked_at
                FROM blocked_ips
                WHERE ip = ?
                """,
                (ip,),
            ).fetchone()

        if not row:
            return False

        return (
            int(time.time()) - int(row[0])
        ) < cooldown_seconds

    def active_block_count(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*)
                FROM blocked_ips
                WHERE active = 1
                """
            ).fetchone()

        return int(row[0]) if row else 0

    def list_active_blocks(self) -> List[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT ip
                FROM blocked_ips
                WHERE active = 1
                """
            ).fetchall()

        return [r[0] for r in rows]


# =========================================================
# Shared helpers
# =========================================================

def command_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def extract_domain(url: str) -> str:
    return urlparse(url).hostname or ""


def new_gid(prefix: str = "sec") -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def now_ts() -> int:
    return int(time.time())