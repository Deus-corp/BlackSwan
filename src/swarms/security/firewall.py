#!/usr/bin/env python3
"""Firewall helper for the security swarm.

Keeps all iptables operations isolated to a dedicated chain.
Emergency flushing of INPUT is supported only when the policy flag allows it.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Optional

from .memory import FirewallPolicy, SecurityMemory, command_exists
from .shared_runtime import new_gid

logger = logging.getLogger(__name__)


class FirewallManager:
    """Manage a dedicated iptables chain instead of touching all INPUT rules."""

    def __init__(self, policy: FirewallPolicy, memory: SecurityMemory):
        self.policy = policy
        self.memory = memory
        self.ready = False

    def _iptables(self) -> list[str]:
        if command_exists("iptables"):
            return ["iptables"]
        return ["sudo", "iptables"]

    def ensure_chain(self) -> None:
        chain = self.policy.chain_name
        base = self._iptables()
        try:
            subprocess.run(base + ["-N", chain], check=False, timeout=5)
            subprocess.run(base + ["-C", "INPUT", "-j", chain], check=False, timeout=5)
            subprocess.run(base + ["-I", "INPUT", "1", "-j", chain], check=False, timeout=5)
            self.ready = True
            logger.info("🔐 Firewall chain ready: %s", chain)
        except Exception as e:
            logger.warning("Could not ensure firewall chain %s: %s", chain, e)

    def block_ip(self, ip: str, *, source: str, reason: str) -> bool:
        if ip in (self.policy.allowlist_ips or []):
            logger.info("⏭️ Allowlisted IP skipped: %s", ip)
            return False
        if self.memory.is_recently_blocked(ip, self.policy.per_ip_cooldown_seconds):
            return False
        if self.memory.active_block_count() >= self.policy.max_blocked_ips:
            logger.warning("Max blocked IPs reached, refusing %s", ip)
            return False

        base = self._iptables()
        chain = self.policy.chain_name if self.ready else "INPUT"
        try:
            subprocess.run(base + ["-A", chain, "-s", ip, "-j", "DROP"], check=True, timeout=5)
            self.memory.record_block(ip, source=source, reason=reason, metadata={"chain": chain})
            return True
        except Exception as e:
            logger.error("Failed to block %s: %s", ip, e)
            return False

    def unblock_ip(self, ip: str) -> bool:
        base = self._iptables()
        chain = self.policy.chain_name if self.ready else "INPUT"
        try:
            subprocess.run(base + ["-D", chain, "-s", ip, "-j", "DROP"], check=True, timeout=5)
            self.memory.record_unblock_request(ip)
            self.memory.record_unblock_applied(ip)
            return True
        except Exception as e:
            logger.error("Failed to unblock %s: %s", ip, e)
            return False

    def unblock_all_managed(self) -> None:
        for ip in list(self.memory.list_active_blocks()):
            self.unblock_ip(ip)
        if self.ready:
            base = self._iptables()
            try:
                subprocess.run(base + ["-F", self.policy.chain_name], check=True, timeout=5)
            except Exception as e:
                logger.error("Failed to flush managed chain %s: %s", self.policy.chain_name, e)

    def emergency_flush_input(self) -> bool:
        if not self.policy.allow_emergency_flush_input:
            return False
        base = self._iptables()
        try:
            subprocess.run(base + ["-F", "INPUT"], check=True, timeout=5)
            self.memory.record_event_chain(
                event_gid=new_gid("sec_evt"),
                parent_gid=None,
                source_gid="security_node",
                event_type="command_applied",
                action="EMERGENCY_FLUSH_INPUT",
                status="applied",
                details={"scope": "INPUT"},
                provenance={"manual_override": True},
            )
            return True
        except Exception as e:
            logger.error("Emergency flush INPUT failed: %s", e)
            return False