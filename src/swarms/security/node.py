#!/usr/bin/env python3
"""Security Node – defensive execution agent.

Responsibilities:
- observes local host state
- applies firewall actions
- emits heartbeats/incidents into CRDT
- consumes commands from SecurityMetaAgent
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.crdt_adapter import CRDTAdapter
from src.core.event_store import EventStore
from src.core.events import Event
from swarm_config import config

from src.swarms.security.node_core import (
    FirewallManager,
    FirewallPolicy,
    SecurityMemory,
    command_exists,
    new_gid,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger("SecurityNode")

MAIN_LOOP_SLEEP_SECONDS = 2.0
LOG_MONITOR_INTERVAL_STEPS = 30
HEARTBEAT_INTERVAL_STEPS = 20
PORT_SCAN_INTERVAL_STEPS = 60
INTEGRITY_CHECK_INTERVAL_STEPS = 120
PIP_AUDIT_INTERVAL_STEPS = 150


class SecurityNode:
    """Low-level execution/security node."""

    def __init__(
        self,
        node_id: Optional[str] = None,
        memory_db: Path = Path("./data/security_node_memory.sqlite3"),
    ) -> None:
        self.node_id = node_id or f"sec-{uuid.uuid4().hex[:8]}"

        self.crdt = CRDTAdapter(
            node_id=self.node_id,
            db_path=config.crdt_db_path,
        )

        self.event_store = EventStore(
            ledger_path="./data/ledgers/sec_events.jsonl",
            sqlite_path="./data/ledgers/sec_events.db",
        )

        self.memory = SecurityMemory(memory_db)
        self.policy = FirewallPolicy.from_env()
        self.firewall = FirewallManager(self.policy, self.memory)

        self.step = 0
        self.blocked_ips: set[str] = set()

        self._baseline_file_hashes: Dict[str, str] = {}

        self._critical_files_to_monitor = [
            "/app/src/swarms/security/node.py",
            "/app/src/core/crdt_adapter.py",
            "/app/src/intelligence/llm_client.py",
            "/app/swarm_config.py",
        ]

        logger.info("🛡️ SecurityNode initialized: %s", self.node_id)

    async def run(self) -> None:
        logger.info("🛡️ SecurityNode %s started", self.node_id)

        self.firewall.ensure_chain()

        while True:
            self.step += 1

            try:
                await self._monitor_logs()
                await self._apply_security_commands()
                await self._send_heartbeat()
                await self._scan_ports()
                await self._verify_integrity()
                await self._pip_audit()
            except Exception as exc:
                logger.exception("SecurityNode loop failure: %s", exc)

            await asyncio.sleep(MAIN_LOOP_SLEEP_SECONDS)

    async def _monitor_logs(self) -> None:
        if self.step % LOG_MONITOR_INTERVAL_STEPS != 0:
            return

        try:
            result = subprocess.run(
                ["journalctl", "-u", "ssh", "--since", "2 minutes ago", "-o", "cat"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            failed_attempts = re.findall(
                r"Failed password for .* from (\S+) port",
                result.stdout,
            )

            for ip in failed_attempts:
                await self._block_ip(
                    ip,
                    source="ssh_failed_login",
                    reason="failed password attempts",
                )

        except Exception as exc:
            logger.warning("Log monitor failure: %s", exc)

    async def _block_ip(
        self,
        ip: str,
        *,
        source: str,
        reason: str,
    ) -> None:
        if ip in self.blocked_ips:
            return

        blocked = self.firewall.block_ip(
            ip,
            source=source,
            reason=reason,
        )

        if not blocked:
            return

        self.blocked_ips.add(ip)

        event_gid = new_gid("sec_evt")

        self.memory.record_event_chain(
            event_gid=event_gid,
            parent_gid=None,
            source_gid=self.node_id,
            event_type="block_applied",
            action="BLOCK_IP",
            target_ip=ip,
            status="applied",
            details={
                "source": source,
                "reason": reason,
            },
            provenance={"agent": self.node_id},
        )

        self.event_store.append(
            Event.create(
                node_id=self.node_id,
                event_type="ip_blocked",
                payload={
                    "ip": ip,
                    "source": source,
                    "reason": reason,
                    "timestamp": time.time(),
                },
                parent_id=None,
            )
        )

        logger.info("Blocked IP: %s", ip)

    async def _apply_security_commands(self) -> None:
        commands = [
            value
            for value in self.crdt.state.values()
            if isinstance(value, dict)
            and value.get("type") == "sec_command"
        ]

        for cmd in commands:
            command_id = str(cmd.get("gid") or "")

            if not command_id:
                continue

            if self.memory.receipt_seen(command_id):
                continue

            action = str(cmd.get("data", {}).get("action", "")).upper()

            self.memory.record_receipt(
                command_id,
                action=action,
                provenance={"agent": self.node_id},
                status="received",
            )

            if action == "UNBLOCK_ALL":
                await self._unblock_all(command_id)
                self.memory.mark_receipt_applied(command_id)

            elif action == "EMERGENCY_FLUSH_INPUT":
                ok = self.firewall.emergency_flush_input()

                if ok:
                    self.blocked_ips.clear()
                    self.memory.mark_receipt_applied(command_id)

            elif action == "RESTART_NODE":
                logger.critical("Restart requested for node")
                sys.exit(0)

    async def _unblock_all(self, parent_command: Optional[str]) -> None:
        for ip in list(self.blocked_ips):
            ok = self.firewall.unblock_ip(ip)

            if ok:
                self.blocked_ips.discard(ip)

        self.firewall.unblock_all_managed()

        self.memory.record_event_chain(
            event_gid=new_gid("sec_evt"),
            parent_gid=parent_command,
            source_gid=self.node_id,
            event_type="unblock_applied",
            action="UNBLOCK_ALL",
            status="applied",
            details={"count": len(self.blocked_ips)},
            provenance={"agent": self.node_id},
        )

    async def _send_heartbeat(self) -> None:
        if self.step % HEARTBEAT_INTERVAL_STEPS != 0:
            return

        heartbeat = {
            "type": "security_heartbeat",
            "gid": new_gid("sec_hb"),
            "node_id": self.node_id,
            "timestamp": time.time(),
            "blocked_ips": len(self.blocked_ips),
            "status": "ok",
            "provenance": {
                "agent": self.node_id,
            },
        }

        await self.crdt.add_genome(heartbeat)

    async def _scan_ports(self) -> None:
        if self.step % PORT_SCAN_INTERVAL_STEPS != 0:
            return

        open_ports: List[int] = []

        for port in [22, 80, 443, 8080, 5432]:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection("127.0.0.1", port),
                    timeout=1.0,
                )
                writer.close()
                await writer.wait_closed()
                open_ports.append(port)
            except Exception:
                pass

        if not open_ports:
            return

        self.event_store.append(
            Event.create(
                node_id=self.node_id,
                event_type="open_ports_detected",
                payload={
                    "ports": open_ports,
                    "timestamp": time.time(),
                },
                parent_id=None,
            )
        )

    async def _verify_integrity(self) -> None:
        if self.step % INTEGRITY_CHECK_INTERVAL_STEPS != 0:
            return

        changed_files: List[str] = []

        for filepath in self._critical_files_to_monitor:
            if not os.path.exists(filepath):
                continue

            try:
                with open(filepath, "rb") as handle:
                    digest = hashlib.sha256(handle.read()).hexdigest()

                previous = self._baseline_file_hashes.get(filepath)

                if previous and previous != digest:
                    changed_files.append(filepath)

                self._baseline_file_hashes[filepath] = digest

            except Exception as exc:
                logger.warning("Integrity check failed for %s: %s", filepath, exc)

        if changed_files:
            self.event_store.append(
                Event.create(
                    node_id=self.node_id,
                    event_type="file_integrity_alert",
                    payload={
                        "changed_files": changed_files,
                        "timestamp": time.time(),
                    },
                    parent_id=None,
                )
            )

    async def _pip_audit(self) -> None:
        if self.step % PIP_AUDIT_INTERVAL_STEPS != 0:
            return

        try:
            cmd = (
                ["pip-audit", "--format", "json"]
                if command_exists("pip-audit")
                else [sys.executable, "-m", "pip_audit", "--format", "json"]
            )

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            if result.returncode != 1:
                return

            vulnerabilities = json.loads(result.stdout)

            if vulnerabilities:
                self.event_store.append(
                    Event.create(
                        node_id=self.node_id,
                        event_type="vulnerability_alert",
                        payload={
                            "vulnerabilities": vulnerabilities,
                            "timestamp": time.time(),
                        },
                        parent_id=None,
                    )
                )

        except Exception as exc:
            logger.warning("pip audit failed: %s", exc)


if __name__ == "__main__":
    asyncio.run(SecurityNode().run())