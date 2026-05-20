#!/usr/bin/env python3
"""Security Node – local defensive agent using shared security runtime."""

## Notes
# `SEC_ALLOW_EMERGENCY_FLUSH_INPUT` defaults to `false`.
# The safe default is a dedicated chain (`SEC_AGENT_INPUT`) rather than touching all of `INPUT`.
# If you later decide to enable the emergency capability, it is already wired in, but it remains policy-gated and disabled by default.
# This shared runtime is the part that should remain stable; both agents now import the same memory, event schema, policy, and firewall logic.


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

from src.swarms.security.shared_runtime import (
    FirewallManager,
    FirewallPolicy,
    SecurityEvent,
    SecurityMemory,
    command_exists,
    extract_domain,
    json_dumps,
    new_gid,
    now_ts,
    parse_json_loose,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger("SecurityNode")

MAIN_LOOP_SLEEP_SECONDS: float = 2.0
LOG_MONITOR_INTERVAL_STEPS: int = 30
HEARTBEAT_INTERVAL_STEPS: int = 20
PORT_SCAN_INTERVAL_STEPS: int = 60
INTEGRITY_CHECK_INTERVAL_STEPS: int = 120
PIP_AUDIT_INTERVAL_STEPS: int = 150


BLOCKED_IPS: set[str] = set()


class SecurityNode:
    def __init__(self, node_id: Optional[str] = None, memory_db: Path = Path("./data/security_node_memory.sqlite3")) -> None:
        self.node_id = node_id or f"sec-{uuid.uuid4().hex[:8]}"
        self.crdt = CRDTAdapter(node_id=self.node_id, db_path=config.crdt_db_path)
        self.event_store = EventStore(ledger_path="./data/ledgers/sec_events.jsonl", sqlite_path="./data/ledgers/sec_events.db")
        self.memory = SecurityMemory(memory_db)
        self.policy = FirewallPolicy.from_env()
        self.firewall = FirewallManager(self.policy, self.memory)
        self.step = 0
        self._baseline_file_hashes: Dict[str, str] = {}
        self._critical_files_to_monitor: List[str] = [
            "/app/src/swarms/security/node.py",
            "/app/src/core/crdt_adapter.py",
            "/app/src/intelligence/llm_client.py",
            "/app/swarm_config.py",
        ]
        self._firewall_ready = False
        logger.info("🛡️ SecurityNode initialized: %s", self.node_id)

    async def run(self) -> None:
        logger.info("🛡️ SecurityNode %s started", self.node_id)
        try:
            self.firewall.ensure_chain()
            self._firewall_ready = True
            while True:
                self.step += 1
                try:
                    await self._monitor_logs()
                    await self._apply_security_commands()
                    await self._send_heartbeat()
                    await self._scan_ports()
                    await self._verify_integrity()
                    await self._pip_audit()
                except Exception as e:
                    logger.error("Security task failed during step %s: %s", self.step, e, exc_info=True)
                await asyncio.sleep(MAIN_LOOP_SLEEP_SECONDS)
        except asyncio.CancelledError:
            logger.info("SecurityNode %s run cancelled.", self.node_id)
        except Exception as e:
            logger.exception("SecurityNode %s encountered a critical error: %s", self.node_id, e)

    async def _monitor_logs(self) -> None:
        if self.step % LOG_MONITOR_INTERVAL_STEPS != 0:
            return

        suspicious_ips: List[str] = []
        try:
            result = subprocess.run(
                ["journalctl", "-u", "ssh", "--since", "2 minutes ago", "-o", "cat"],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
            failed_attempts = re.findall(r"Failed password for .* from (\S+) port", result.stdout)
            for ip in failed_attempts:
                if ip not in BLOCKED_IPS:
                    suspicious_ips.append(ip)
        except subprocess.CalledProcessError as e:
            logger.warning("journalctl failed (exit %s): %s", e.returncode, (e.stderr or "").strip())
        except subprocess.TimeoutExpired:
            logger.warning("journalctl timed out.")
        except FileNotFoundError:
            logger.warning("journalctl not found. Log monitoring skipped.")
        except Exception as e:
            logger.error("Error during log monitoring: %s", e, exc_info=True)

        for ip in suspicious_ips:
            await self._block_ip(ip, source="ssh_failed_login", reason="failed password attempts")

    async def _block_ip(self, ip: str, source: str = "unknown", reason: str = "") -> None:
        if ip in BLOCKED_IPS:
            return
        if self.memory.active_block_count() >= self.policy.max_blocked_ips:
            logger.warning("Max blocked IPs reached. Refusing to block %s.", ip)
            return
        if self.memory.is_recently_blocked(ip, self.policy.per_ip_cooldown_seconds):
            logger.info("⏭️ IP %s was recently blocked; skipping.", ip)
            return
        if ip in self.policy.allowlist_ips:
            logger.info("⏭️ IP %s is in allowlist; skipping block.", ip)
            return
        if ip in self.policy.blocklist_ips:
            logger.info("✅ IP %s is explicitly blocklisted.", ip)

        blocked = self.firewall.block_ip(ip, source=source, reason=reason)
        if not blocked:
            return

        BLOCKED_IPS.add(ip)
        event_gid = new_gid("sec_evt")
        self.memory.record_event_chain(
            event_gid=event_gid,
            parent_gid=None,
            source_gid=ip,
            event_type="block_applied",
            action="BLOCK_IP",
            target_ip=ip,
            status="applied",
            details={"source": source, "reason": reason, "chain": self.policy.chain_name if self.firewall.ready else "INPUT"},
            provenance={"agent": self.node_id, "source": source, "reason": reason},
        )
        self.event_store.append(Event.create(
            node_id=self.node_id,
            event_type="ip_blocked",
            payload={"ip": ip, "timestamp": time.time(), "agent_pid": os.getpid(), "source": source, "reason": reason},
            parent_id=None,
        ))
        logger.info("Successfully blocked IP: %s", ip)

    async def _apply_security_commands(self) -> None:
        all_state: Dict[str, Any] = self.crdt.state
        commands: List[Dict[str, Any]] = [v for v in all_state.values() if isinstance(v, dict) and v.get("type") == "sec_command"]

        for cmd in commands:
            action: str = str(cmd.get("data", {}).get("action", "")).upper()
            target_node_id: Optional[str] = cmd.get("data", {}).get("node_id")
            command_id: str = str(cmd.get("gid") or "")
            expires_at = float(cmd.get("expires_at", 0) or 0)
            provenance = cmd.get("provenance") if isinstance(cmd.get("provenance"), dict) else {}

            if not command_id or self.memory.receipt_seen(command_id):
                continue

            self.memory.record_receipt(command_id, action=action, provenance=provenance, status="received")
            self.memory.record_event_chain(
                event_gid=command_id,
                parent_gid=cmd.get("source_gid") if isinstance(cmd.get("source_gid"), str) else None,
                source_gid=cmd.get("source_gid") if isinstance(cmd.get("source_gid"), str) else None,
                event_type="command_received",
                action=action,
                target_node_id=str(target_node_id or ""),
                status="received",
                details={"expires_at": expires_at, "data": cmd.get("data", {})},
                provenance=provenance,
            )

            if expires_at <= time.time():
                logger.debug("Expired security command ignored: %s", command_id)
                continue

            if action == "UNBLOCK_ALL":
                await self._unblock_all(scope="managed_chain", parent_command=command_id)
                self.memory.mark_receipt_applied(command_id)
            elif action == "PARTIAL_UNBLOCK":
                await self._partial_unblock(cmd, parent_command=command_id)
                self.memory.mark_receipt_applied(command_id)
            elif action == "EMERGENCY_FLUSH_INPUT":
                if self.policy.allow_emergency_flush_input:
                    await self._emergency_flush_input(parent_command=command_id)
                    self.memory.mark_receipt_applied(command_id)
                else:
                    logger.warning("EMERGENCY_FLUSH_INPUT requested but disabled by policy.")
            elif action == "RESTART_NODE" and target_node_id == self.node_id:
                logger.critical("Received RESTART_NODE for self. Exiting for orchestrator restart.")
                sys.exit(0)

    async def _partial_unblock(self, cmd: Dict[str, Any], parent_command: Optional[str] = None) -> None:
        data = cmd.get("data", {}) if isinstance(cmd.get("data"), dict) else {}
        ips = data.get("ips", [])
        if not isinstance(ips, list):
            return
        for ip in ips:
            if not isinstance(ip, str):
                continue
            await self._unblock_ip(ip, parent_command=parent_command)

    async def _unblock_ip(self, ip: str, parent_command: Optional[str] = None) -> None:
        if ip not in BLOCKED_IPS:
            return
        ok = self.firewall.unblock_ip(ip)
        if not ok:
            return
        BLOCKED_IPS.discard(ip)
        self.memory.record_unblock_request(ip)
        self.memory.record_unblock_applied(ip)
        self.memory.record_event_chain(
            event_gid=new_gid("sec_evt"),
            parent_gid=parent_command,
            source_gid=ip,
            event_type="command_applied",
            action="UNBLOCK_IP",
            target_ip=ip,
            status="applied",
            details={"chain": self.policy.chain_name if self.firewall.ready else "INPUT"},
            provenance={"agent": self.node_id},
        )
        logger.info("🔓 Unblocked IP: %s", ip)

    async def _unblock_all(self, scope: str = "managed_chain", parent_command: Optional[str] = None) -> None:
        logger.info("🔓 Unblocking all IPs in scope=%s", scope)
        try:
            for ip in list(BLOCKED_IPS):
                await self._unblock_ip(ip, parent_command=parent_command)
            self.firewall.unblock_all_managed()
            self.event_store.append(Event.create(
                node_id=self.node_id,
                event_type="all_ips_unblocked",
                payload={"timestamp": time.time(), "agent_pid": os.getpid(), "scope": scope},
                parent_id=None,
            ))
        except Exception as e:
            logger.error("Unexpected error while unblocking all: %s", e, exc_info=True)

    async def _emergency_flush_input(self, parent_command: Optional[str] = None) -> None:
        logger.warning("⚠️ EMERGENCY: flushing INPUT chain as requested by policy.")
        try:
            ok = self.firewall.emergency_flush_input()
            if ok:
                BLOCKED_IPS.clear()
                self.memory.record_event_chain(
                    event_gid=new_gid("sec_evt"),
                    parent_gid=parent_command,
                    source_gid=self.node_id,
                    event_type="command_applied",
                    action="EMERGENCY_FLUSH_INPUT",
                    target_ip="",
                    status="applied",
                    details={"scope": "INPUT"},
                    provenance={"agent": self.node_id, "manual_override": True},
                )
                self.event_store.append(Event.create(
                    node_id=self.node_id,
                    event_type="all_ips_unblocked",
                    payload={"timestamp": time.time(), "agent_pid": os.getpid(), "scope": "INPUT"},
                    parent_id=None,
                ))
        except Exception as e:
            logger.error("Emergency flush error: %s", e, exc_info=True)

    async def _send_heartbeat(self) -> None:
        if self.step % HEARTBEAT_INTERVAL_STEPS != 0:
            return
        heartbeat_gid = new_gid("sec_hb")
        heartbeat: Dict[str, Any] = {
            "type": "security_heartbeat",
            "node_id": self.node_id,
            "blocked_ips": len(BLOCKED_IPS),
            "status": "ok",
            "timestamp": time.time(),
            "gid": heartbeat_gid,
            "provenance": {"agent": self.node_id, "active_blocks": self.memory.active_block_count()},
        }
        await self.crdt.add_genome(heartbeat)
        self.memory.record_event_chain(
            event_gid=heartbeat_gid,
            parent_gid=None,
            source_gid=self.node_id,
            event_type="heartbeat_sent",
            action="heartbeat",
            status="ok",
            details={"blocked_ips": len(BLOCKED_IPS)},
            provenance=heartbeat["provenance"],
        )

    async def _scan_ports(self) -> None:
        if self.step % PORT_SCAN_INTERVAL_STEPS != 0:
            return

        open_ports: List[int] = []
        ports_to_check: List[int] = [22, 80, 443, 8080, 8443, 3000, 5000, 5432]
        for port in ports_to_check:
            try:
                reader, writer = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", port), timeout=1.0)
                writer.close()
                await writer.wait_closed()
                open_ports.append(port)
            except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
                pass
            except Exception as e:
                logger.warning("Unexpected error while scanning port %s: %s", port, e)

        if open_ports:
            event_gid = new_gid("sec_evt")
            self.event_store.append(Event.create(
                node_id=self.node_id,
                event_type="open_ports_detected",
                payload={"ports": open_ports, "timestamp": time.time(), "agent_pid": os.getpid()},
                parent_id=None,
            ))
            self.memory.record_event_chain(
                event_gid=event_gid,
                parent_gid=None,
                source_gid=self.node_id,
                event_type="open_ports_detected",
                action="scan",
                status="detected",
                details={"ports": open_ports},
                provenance={"agent": self.node_id},
            )

    async def _verify_integrity(self) -> None:
        if self.step % INTEGRITY_CHECK_INTERVAL_STEPS != 0:
            return

        changed_files: List[str] = []
        for filepath in self._critical_files_to_monitor:
            if not os.path.exists(filepath):
                continue
            try:
                with open(filepath, "rb") as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                if filepath not in self._baseline_file_hashes:
                    self._baseline_file_hashes[filepath] = file_hash
                elif self._baseline_file_hashes[filepath] != file_hash:
                    changed_files.append(filepath)
                    self._baseline_file_hashes[filepath] = file_hash
            except IOError as e:
                logger.error("Error reading file %s: %s", filepath, e)
            except Exception as e:
                logger.error("Unexpected integrity error for %s: %s", filepath, e, exc_info=True)

        if changed_files:
            event_gid = new_gid("sec_evt")
            self.event_store.append(Event.create(
                node_id=self.node_id,
                event_type="file_integrity_alert",
                payload={"changed_files": changed_files, "timestamp": time.time(), "agent_pid": os.getpid()},
                parent_id=None,
            ))
            self.memory.record_event_chain(
                event_gid=event_gid,
                parent_gid=None,
                source_gid=self.node_id,
                event_type="integrity_alert",
                action="integrity_change",
                status="alert",
                details={"changed_files": changed_files},
                provenance={"agent": self.node_id},
            )

    async def _pip_audit(self) -> None:
        if self.step % PIP_AUDIT_INTERVAL_STEPS != 0:
            return

        try:
            cmd = ["pip-audit", "--format", "json"] if command_exists("pip-audit") else [sys.executable, "-m", "pip_audit", "--format", "json"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
            if result.returncode == 0:
                return
            if result.returncode == 1:
                try:
                    vulnerabilities: List[Dict[str, Any]] = json.loads(result.stdout)
                    if vulnerabilities:
                        event_gid = new_gid("sec_evt")
                        self.event_store.append(Event.create(
                            node_id=self.node_id,
                            event_type="vulnerability_alert",
                            payload={"vulnerabilities": vulnerabilities, "timestamp": time.time(), "agent_pid": os.getpid()},
                            parent_id=None,
                        ))
                        self.memory.record_event_chain(
                            event_gid=event_gid,
                            parent_gid=None,
                            source_gid=self.node_id,
                            event_type="vulnerability_alert",
                            action="audit",
                            status="alert",
                            details={"count": len(vulnerabilities)},
                            provenance={"agent": self.node_id},
                        )
                except json.JSONDecodeError:
                    logger.error("Failed to parse pip-audit JSON output.")
            else:
                logger.error("pip-audit failed (exit %s): %s", result.returncode, (result.stderr or "").strip())
        except subprocess.TimeoutExpired:
            logger.warning("pip-audit timed out.")
        except FileNotFoundError:
            logger.warning("pip-audit not found; skipping audit.")
        except Exception as e:
            logger.error("Unexpected pip-audit error: %s", e, exc_info=True)


if __name__ == "__main__":
    node = SecurityNode()
    try:
        asyncio.run(node.run())
    except KeyboardInterrupt:
        logger.info("SecurityNode stopped by user (KeyboardInterrupt).")
    except Exception as e:
        logger.critical("SecurityNode encountered an unexpected error during startup or main loop: %s", e, exc_info=True)
