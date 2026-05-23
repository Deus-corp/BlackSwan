#!/usr/bin/env python3
"""Security Node – local defensive execution agent.

This node is now based on the shared BaseSwarmNode runtime.

Responsibilities:
- monitor local security signals
- apply firewall actions
- emit security telemetry/events
- consume security commands from CRDT
- publish canonical swarm heartbeats with security metrics
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
from typing import Any, Dict, List, Mapping, Optional

from src.core.event_store import EventStore
from src.core.events import Event
from src.swarms.common import (
    BaseNodeConfig,
    BaseSwarmNode,
    command_action,
    make_swarm_event,
)
from src.swarms.security.node_core import (
    FirewallManager,
    FirewallPolicy,
    SecurityMemory,
    command_exists,
    new_gid,
)
from swarm_config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
)

logger = logging.getLogger("SecurityNode")

LOG_MONITOR_INTERVAL_STEPS: int = 30
PORT_SCAN_INTERVAL_STEPS: int = 60
INTEGRITY_CHECK_INTERVAL_STEPS: int = 120
PIP_AUDIT_INTERVAL_STEPS: int = 150
COMMAND_DEDUP_WINDOW_SECONDS: float = 5.0


class SecurityNode(BaseSwarmNode):
    """Security swarm node running on the common node runtime."""

    def __init__(
        self,
        node_id: Optional[str] = None,
        memory_db: Optional[Path] = None,
    ) -> None:
        super().__init__(
            node_config=BaseNodeConfig(
                swarm_type="security",
                role="node",
                node_id=node_id or f"sec-{uuid.uuid4().hex[:8]}",
                version="0.2.0",
                tick_interval_seconds=2.0,
                heartbeat_interval_seconds=40.0,
                command_poll_interval_seconds=2.0,
                reconcile_interval_seconds=10.0,
                healthcheck_interval_seconds=15.0,
                maintenance_interval_seconds=60.0,
                crdt_db_path=config.crdt_db_path,
            ),
            logger_name="SecurityNode",
        )

        self._repo_root = Path(__file__).resolve().parents[3]

        if memory_db is None:
            memory_db = self._repo_root / "data" / "security_node_memory.sqlite3"

        ledger_dir = self._repo_root / "data" / "ledgers"
        ledger_dir.mkdir(parents=True, exist_ok=True)

        self.event_store = EventStore(
            ledger_path=str(ledger_dir / "sec_events.jsonl"),
            sqlite_path=str(ledger_dir / "sec_events.db"),
        )

        self.memory = SecurityMemory(memory_db)
        self.policy = FirewallPolicy.from_env()
        self.firewall = FirewallManager(self.policy, self.memory)

        self.blocked_ips: set[str] = set()
        self._baseline_file_hashes: Dict[str, str] = {}

        self._recent_command_semantic_keys: Dict[str, float] = {}

        self._critical_files_to_monitor: List[str] = [
            str(self._repo_root / "src" / "swarms" / "security" / "node.py"),
            str(self._repo_root / "src" / "swarms" / "security" / "meta_agent.py"),
            str(self._repo_root / "src" / "swarms" / "security" / "node_core" / "shared_runtime.py"),
            str(self._repo_root / "src" / "core" / "crdt_adapter.py"),
            str(self._repo_root / "src" / "intelligence" / "llm_client.py"),
            str(self._repo_root / "swarm_config.py"),
        ]

        self.logger.info("🛡️ SecurityNode initialized: %s", self.node_id)

    # ------------------------------------------------------------------
    # BaseSwarmNode hooks
    # ------------------------------------------------------------------

    async def on_startup(self) -> None:
        """Initialize local security runtime."""
        self.firewall.ensure_chain()
        self.logger.info(
            "SecurityNode %s startup complete. firewall_ready=%s chain=%s",
            self.node_id,
            self.firewall.ready,
            self.policy.chain_name,
        )

    async def process_tick(self) -> None:
        """Run one security node work cycle.

        The shared BaseSwarmNode runtime calls this periodically.
        """
        await self._monitor_logs()
        await self._scan_ports()
        await self._verify_integrity()
        await self._pip_audit()

    async def process_command(self, command: Mapping[str, Any]) -> None:
        """Process security commands from common/legacy CRDT command formats."""
        action = command_action(command)
        data = command.get("data") if isinstance(command.get("data"), Mapping) else {}
        payload = command.get("payload") if isinstance(command.get("payload"), Mapping) else {}

        command_id = str(command.get("gid") or "")
        if not command_id:
            return

        if self.memory.receipt_seen(command_id):
            return

        if self._security_command_seen_recently(command):
            return

        if await self.handle_lifecycle_command(command):
            return

        provenance = command.get("provenance") if isinstance(command.get("provenance"), dict) else {}

        self.memory.record_receipt(
            command_id,
            action=action,
            provenance=provenance,
            status="received",
        )

        self.memory.record_event_chain(
            event_gid=command_id,
            parent_gid=command.get("parent_gid") if isinstance(command.get("parent_gid"), str) else None,
            source_gid=str(command.get("source_agent") or command.get("source_gid") or ""),
            event_type="command_received",
            action=action,
            target_node_id=str(command.get("target_node") or data.get("node_id") or payload.get("node_id") or ""),
            status="received",
            details={
                "expires_at": command.get("expires_at"),
                "data": dict(data),
                "payload": dict(payload),
            },
            provenance=provenance,
        )

        if action == "UNBLOCK_ALL":
            await self._unblock_all(parent_command=command_id)
            self.memory.mark_receipt_applied(command_id)

        elif action == "PARTIAL_UNBLOCK":
            await self._partial_unblock(command, parent_command=command_id)
            self.memory.mark_receipt_applied(command_id)

        elif action == "EMERGENCY_FLUSH_INPUT":
            if self.policy.allow_emergency_flush_input:
                await self._emergency_flush_input(parent_command=command_id)
                self.memory.mark_receipt_applied(command_id)
            else:
                self.logger.warning("EMERGENCY_FLUSH_INPUT requested but disabled by policy.")

        elif action == "RESTART_NODE":
            target_node = (
                command.get("target_node")
                or command.get("target_node_id")
                or data.get("node_id")
                or payload.get("node_id")
            )

            if target_node in {self.node_id, "*", None, ""}:
                self.memory.mark_receipt_applied(command_id)
                self.logger.critical("Received RESTART_NODE for self. Exiting for orchestrator restart.")
                sys.exit(0)

    async def publish_heartbeat(self) -> None:
        """Publish canonical heartbeat plus legacy security heartbeat for compatibility."""
        await super().publish_heartbeat()

        legacy_heartbeat = {
            "type": "security_heartbeat",
            "node_id": self.node_id,
            "blocked_ips": len(self.blocked_ips),
            "status": self.health.status,
            "timestamp": time.time(),
            "gid": new_gid("sec_hb"),
            "provenance": {
                "agent": self.node_id,
                "active_blocks": self.memory.active_block_count(),
                "firewall_ready": self.firewall.ready,
                "chain": self.policy.chain_name,
            },
        }

        await self.crdt.add_genome(legacy_heartbeat)

        self.memory.record_event_chain(
            event_gid=legacy_heartbeat["gid"],
            parent_gid=None,
            source_gid=self.node_id,
            event_type="heartbeat_sent",
            action="heartbeat",
            status=self.health.status,
            details={
                "blocked_ips": len(self.blocked_ips),
                "active_blocks": self.memory.active_block_count(),
                "firewall_ready": self.firewall.ready,
            },
            provenance=legacy_heartbeat["provenance"],
        )

    def build_heartbeat(self) -> Dict[str, Any]:
        """Build canonical security heartbeat with security-specific metrics."""
        heartbeat = super().build_heartbeat()
        metrics = heartbeat.setdefault("metrics", {})

        metrics.update(
            {
                "blocked_ips": len(self.blocked_ips),
                "active_blocks": self.memory.active_block_count(),
                "firewall_ready": self.firewall.ready,
                "firewall_chain": self.policy.chain_name,
                "allow_emergency_flush_input": self.policy.allow_emergency_flush_input,
                "max_blocked_ips": self.policy.max_blocked_ips,
            }
        )

        return heartbeat

    async def reconcile(self) -> None:
        """Reconcile in-memory blocked IP cache with persisted memory."""
        try:
            self.blocked_ips = set(self.memory.list_active_blocks())
        except Exception as exc:
            self.logger.warning("SecurityNode reconcile failed: %s", exc)

    async def healthcheck(self) -> None:
        """Security-specific healthcheck."""
        await super().healthcheck()

        if self.memory.active_block_count() >= self.policy.max_blocked_ips:
            self.health.status = "degraded"
            self.health.last_error = "max_blocked_ips reached"

        if not self.firewall.ready:
            self.health.status = "degraded"
            self.health.last_error = "firewall chain is not ready"

    async def on_shutdown(self) -> None:
        """Cleanup security node resources."""
        self.logger.info("SecurityNode %s shutting down.", self.node_id)

    def _security_command_semantic_key(self, command: Mapping[str, Any]) -> str:
        """Build local semantic key for deduplicating canonical + legacy security commands."""
        data = command.get("data") if isinstance(command.get("data"), Mapping) else {}
        payload = command.get("payload") if isinstance(command.get("payload"), Mapping) else {}

        action = str(
            command.get("command_type")
            or data.get("action")
            or payload.get("action")
            or ""
        ).upper()

        target_node = str(
            command.get("target_node")
            or command.get("target_node_id")
            or data.get("node_id")
            or payload.get("node_id")
            or ""
        )

        # Legacy security PAUSE/RESUME/RESTART_NODE may omit target_node.
        # Treat lifecycle duplicates as equivalent locally.
        if action in {"PAUSE", "RESUME", "RESTART_NODE"}:
            target_node = ""

        ips = payload.get("ips") or data.get("ips") or []
        if isinstance(ips, list):
            ips_key = ",".join(sorted(str(ip) for ip in ips if isinstance(ip, str)))
        else:
            ips_key = ""

        return f"{action}|node={target_node}|ips={ips_key}"


    def _security_command_seen_recently(self, command: Mapping[str, Any]) -> bool:
        """Return True if equivalent security command was processed recently."""
        now = time.time()

        expired = [
            key
            for key, seen_at in self._recent_command_semantic_keys.items()
            if now - seen_at > COMMAND_DEDUP_WINDOW_SECONDS
        ]
        for key in expired:
            self._recent_command_semantic_keys.pop(key, None)

        key = self._security_command_semantic_key(command)
        if not key.strip("|"):
            return False

        seen_at = self._recent_command_semantic_keys.get(key)
        if seen_at is not None and now - seen_at <= COMMAND_DEDUP_WINDOW_SECONDS:
            logger.info("Skipping duplicate security command within dedup window: %s", key)
            return True

        self._recent_command_semantic_keys[key] = now
        return False

    # ------------------------------------------------------------------
    # Security actions
    # ------------------------------------------------------------------

    async def _monitor_logs(self) -> None:
        if self.health_snapshot_tick() % LOG_MONITOR_INTERVAL_STEPS != 0:
            return

        suspicious_ips: List[str] = []

        try:
            result = subprocess.run(
                ["journalctl", "-u", "ssh", "--since", "2 minutes ago", "-o", "cat"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            if result.returncode not in {0, 1}:
                self.logger.debug("journalctl returned %s: %s", result.returncode, (result.stderr or "").strip())

            failed_attempts = re.findall(r"Failed password for .* from (\S+) port", result.stdout)

            for ip in failed_attempts:
                if ip not in self.blocked_ips:
                    suspicious_ips.append(ip)

        except subprocess.TimeoutExpired:
            self.logger.warning("journalctl timed out.")
        except FileNotFoundError:
            self.logger.debug("journalctl not found. Log monitoring skipped.")
        except Exception as exc:
            self.logger.error("Error during log monitoring: %s", exc, exc_info=True)

        for ip in suspicious_ips:
            await self._block_ip(ip, source="ssh_failed_login", reason="failed password attempts")

    async def _block_ip(self, ip: str, *, source: str, reason: str) -> None:
        if ip in self.blocked_ips:
            return

        if self.memory.active_block_count() >= self.policy.max_blocked_ips:
            self.logger.warning("Max blocked IPs reached. Refusing to block %s.", ip)
            return

        if self.memory.is_recently_blocked(ip, self.policy.per_ip_cooldown_seconds):
            self.logger.info("IP %s was recently blocked; skipping.", ip)
            return

        if ip in self.policy.allowlist_ips:
            self.logger.info("IP %s is allowlisted; skipping block.", ip)
            return

        if ip in self.policy.blocklist_ips:
            self.logger.info("IP %s is explicitly blocklisted.", ip)

        blocked = self.firewall.block_ip(ip, source=source, reason=reason)
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
                "chain": self.policy.chain_name if self.firewall.ready else "INPUT",
            },
            provenance={
                "agent": self.node_id,
                "source": source,
                "reason": reason,
            },
        )

        canonical_event = make_swarm_event(
            event_type="block_applied",
            source_swarm="security",
            source_node=self.node_id,
            role=self.role,
            severity=0.3,
            payload={
                "ip": ip,
                "source": source,
                "reason": reason,
                "chain": self.policy.chain_name if self.firewall.ready else "INPUT",
            },
            provenance={"agent": self.node_id},
        )
        await self.crdt.add_genome(canonical_event)

        self.event_store.append(
            Event.create(
                node_id=self.node_id,
                event_type="ip_blocked",
                payload={
                    "ip": ip,
                    "timestamp": time.time(),
                    "agent_pid": os.getpid(),
                    "source": source,
                    "reason": reason,
                },
                parent_id=None,
            )
        )

        self.logger.info("Successfully blocked IP: %s", ip)

    async def _partial_unblock(self, command: Mapping[str, Any], parent_command: Optional[str] = None) -> None:
        data = command.get("data") if isinstance(command.get("data"), Mapping) else {}
        payload = command.get("payload") if isinstance(command.get("payload"), Mapping) else {}

        ips = payload.get("ips") or data.get("ips") or []
        if not isinstance(ips, list):
            return

        for ip in ips:
            if isinstance(ip, str):
                await self._unblock_ip(ip, parent_command=parent_command)

    async def _unblock_ip(self, ip: str, parent_command: Optional[str] = None) -> None:
        if ip not in self.blocked_ips and ip not in self.memory.list_active_blocks():
            return

        ok = self.firewall.unblock_ip(ip)
        if not ok:
            return

        self.blocked_ips.discard(ip)

        self.memory.record_unblock_request(ip)
        self.memory.record_unblock_applied(ip)

        self.memory.record_event_chain(
            event_gid=new_gid("sec_evt"),
            parent_gid=parent_command,
            source_gid=self.node_id,
            event_type="command_applied",
            action="UNBLOCK_IP",
            target_ip=ip,
            status="applied",
            details={"chain": self.policy.chain_name if self.firewall.ready else "INPUT"},
            provenance={"agent": self.node_id},
        )

        canonical_event = make_swarm_event(
            event_type="unblock_applied",
            source_swarm="security",
            source_node=self.node_id,
            role=self.role,
            parent_gid=parent_command,
            severity=0.1,
            payload={"ip": ip},
            provenance={"agent": self.node_id},
        )
        await self.crdt.add_genome(canonical_event)

        self.logger.info("Unblocked IP: %s", ip)

    async def _unblock_all(self, parent_command: Optional[str] = None) -> None:
        self.logger.info("Unblocking all managed IPs.")

        try:
            active_ips = set(self.blocked_ips) | set(self.memory.list_active_blocks())

            for ip in list(active_ips):
                await self._unblock_ip(ip, parent_command=parent_command)

            self.firewall.unblock_all_managed()
            self.blocked_ips.clear()

            self.memory.record_event_chain(
                event_gid=new_gid("sec_evt"),
                parent_gid=parent_command,
                source_gid=self.node_id,
                event_type="command_applied",
                action="UNBLOCK_ALL",
                status="applied",
                details={"scope": "managed_chain"},
                provenance={"agent": self.node_id},
            )

            canonical_event = make_swarm_event(
                event_type="unblock_applied",
                source_swarm="security",
                source_node=self.node_id,
                role=self.role,
                parent_gid=parent_command,
                severity=0.2,
                payload={"scope": "managed_chain"},
                provenance={"agent": self.node_id},
            )
            await self.crdt.add_genome(canonical_event)

            self.event_store.append(
                Event.create(
                    node_id=self.node_id,
                    event_type="all_ips_unblocked",
                    payload={
                        "timestamp": time.time(),
                        "agent_pid": os.getpid(),
                        "scope": "managed_chain",
                    },
                    parent_id=None,
                )
            )

        except Exception as exc:
            self.logger.error("Unexpected error while unblocking all: %s", exc, exc_info=True)

    async def _emergency_flush_input(self, parent_command: Optional[str] = None) -> None:
        self.logger.warning("EMERGENCY: flushing INPUT chain as requested by policy.")

        try:
            ok = self.firewall.emergency_flush_input()
            if not ok:
                return

            self.blocked_ips.clear()

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

            canonical_event = make_swarm_event(
                event_type="command_applied",
                source_swarm="security",
                source_node=self.node_id,
                role=self.role,
                parent_gid=parent_command,
                severity=0.8,
                payload={"action": "EMERGENCY_FLUSH_INPUT", "scope": "INPUT"},
                provenance={"agent": self.node_id, "manual_override": True},
            )
            await self.crdt.add_genome(canonical_event)

            self.event_store.append(
                Event.create(
                    node_id=self.node_id,
                    event_type="all_ips_unblocked",
                    payload={
                        "timestamp": time.time(),
                        "agent_pid": os.getpid(),
                        "scope": "INPUT",
                    },
                    parent_id=None,
                )
            )

        except Exception as exc:
            self.logger.error("Emergency flush error: %s", exc, exc_info=True)

    # ------------------------------------------------------------------
    # Observability tasks
    # ------------------------------------------------------------------

    async def _scan_ports(self) -> None:
        if self.health_snapshot_tick() % PORT_SCAN_INTERVAL_STEPS != 0:
            return

        open_ports: List[int] = []
        ports_to_check: List[int] = [22, 80, 443, 8080, 8443, 3000, 5000, 5432]

        for port in ports_to_check:
            try:
                _reader, writer = await asyncio.wait_for(
                    asyncio.open_connection("127.0.0.1", port),
                    timeout=1.0,
                )
                writer.close()
                await writer.wait_closed()
                open_ports.append(port)
            except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
                pass
            except Exception as exc:
                self.logger.warning("Unexpected error while scanning port %s: %s", port, exc)

        if not open_ports:
            return

        event_gid = new_gid("sec_evt")

        self.event_store.append(
            Event.create(
                node_id=self.node_id,
                event_type="open_ports_detected",
                payload={
                    "ports": open_ports,
                    "timestamp": time.time(),
                    "agent_pid": os.getpid(),
                },
                parent_id=None,
            )
        )

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

        canonical_event = make_swarm_event(
            event_type="open_ports_detected",
            source_swarm="security",
            source_node=self.node_id,
            role=self.role,
            severity=0.55,
            payload={"ports": open_ports},
            provenance={"agent": self.node_id},
        )
        await self.crdt.add_genome(canonical_event)

    async def _verify_integrity(self) -> None:
        if self.health_snapshot_tick() % INTEGRITY_CHECK_INTERVAL_STEPS != 0:
            return

        changed_files: List[str] = []

        for filepath in self._critical_files_to_monitor:
            if not os.path.exists(filepath):
                continue

            try:
                with open(filepath, "rb") as handle:
                    file_hash = hashlib.sha256(handle.read()).hexdigest()

                if filepath not in self._baseline_file_hashes:
                    self._baseline_file_hashes[filepath] = file_hash
                elif self._baseline_file_hashes[filepath] != file_hash:
                    changed_files.append(filepath)
                    self._baseline_file_hashes[filepath] = file_hash

            except IOError as exc:
                self.logger.error("Error reading file %s: %s", filepath, exc)
            except Exception as exc:
                self.logger.error("Unexpected integrity error for %s: %s", filepath, exc, exc_info=True)

        if not changed_files:
            return

        event_gid = new_gid("sec_evt")

        self.event_store.append(
            Event.create(
                node_id=self.node_id,
                event_type="file_integrity_alert",
                payload={
                    "changed_files": changed_files,
                    "timestamp": time.time(),
                    "agent_pid": os.getpid(),
                },
                parent_id=None,
            )
        )

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

        canonical_event = make_swarm_event(
            event_type="file_integrity_alert",
            source_swarm="security",
            source_node=self.node_id,
            role=self.role,
            severity=0.95,
            payload={"changed_files": changed_files},
            provenance={"agent": self.node_id},
        )
        await self.crdt.add_genome(canonical_event)

    async def _pip_audit(self) -> None:
        if self.health_snapshot_tick() % PIP_AUDIT_INTERVAL_STEPS != 0:
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

            if result.returncode == 0:
                return

            if result.returncode != 1:
                self.logger.error("pip-audit failed (exit %s): %s", result.returncode, (result.stderr or "").strip())
                return

            try:
                vulnerabilities = json.loads(result.stdout)
            except json.JSONDecodeError:
                self.logger.error("Failed to parse pip-audit JSON output.")
                return

            if not vulnerabilities:
                return

            event_gid = new_gid("sec_evt")

            self.event_store.append(
                Event.create(
                    node_id=self.node_id,
                    event_type="vulnerability_alert",
                    payload={
                        "vulnerabilities": vulnerabilities,
                        "timestamp": time.time(),
                        "agent_pid": os.getpid(),
                    },
                    parent_id=None,
                )
            )

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

            canonical_event = make_swarm_event(
                event_type="vulnerability_alert",
                source_swarm="security",
                source_node=self.node_id,
                role=self.role,
                severity=0.9,
                payload={
                    "count": len(vulnerabilities),
                    "vulnerabilities": vulnerabilities,
                },
                provenance={"agent": self.node_id},
            )
            await self.crdt.add_genome(canonical_event)

        except subprocess.TimeoutExpired:
            self.logger.warning("pip-audit timed out.")
        except FileNotFoundError:
            self.logger.debug("pip-audit not found; skipping audit.")
        except Exception as exc:
            self.logger.error("Unexpected pip-audit error: %s", exc, exc_info=True)

    # ------------------------------------------------------------------
    # Small helpers
    # ------------------------------------------------------------------

    def health_snapshot_tick(self) -> int:
        """Use BaseSwarmNode loop counter if present; fallback to uptime-derived tick."""
        # BaseSwarmNode does not currently expose step_count directly, so we derive
        # a stable tick from uptime / tick interval.
        try:
            return int(self.health.uptime_seconds // max(0.001, self.config.tick_interval_seconds))
        except Exception:
            return 0


async def main() -> None:
    node = SecurityNode()
    await node.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("SecurityNode stopped by user.")
    except SystemExit as exc:
        logger.info("SecurityNode stopped gracefully: %s", exc)
    except Exception as exc:
        logger.critical("SecurityNode encountered an unexpected error: %s", exc, exc_info=True)