#!/usr/bin/env python3
"""Firewall manager for security swarm integration.

Handles iptables chain management, IP blocking, and safe flushing operations.
"""

from __future__ import annotations

import logging
import subprocess
from typing import List, Optional

from src.swarms.security.memory import FirewallPolicy, SecurityMemory, command_exists, new_gid

logger = logging.getLogger(__name__)

class FirewallManager:
    """Manages a dedicated iptables chain for isolated rule enforcement."""

    def __init__(self, policy: FirewallPolicy, memory: SecurityMemory) -> None:
        self.policy = policy
        self.memory = memory
        self.ready: bool = False

    def _get_iptables_cmd(self) -> List[str]:
        """Determine base command for iptables (sudo vs direct)."""
        return ["iptables"] if command_exists("iptables") else ["sudo", "iptables"]

    def ensure_chain(self) -> None:
        """Creates the dedicated chain and ensures it is linked to INPUT."""
        chain = self.policy.chain_name
        base = self._get_iptables_cmd()
        try:
            subprocess.run(base + ["-N", chain], check=False, timeout=5, capture_output=True)
            # Ensure it is at the top of the INPUT chain
            subprocess.run(base + ["-C", "INPUT", "-j", chain], check=False, timeout=5, capture_output=True)
            subprocess.run(base + ["-I", "INPUT", "1", "-j", chain], check=False, timeout=5, capture_output=True)
            self.ready = True
            logger.info("Firewall chain '%s' initialized.", chain)
        except Exception as e:
            logger.warning("Failed to ensure firewall chain %s: %s", chain, e)

    def block_ip(self, ip: str, *, source: str, reason: str) -> bool:
        """Blocks an IP by adding a drop rule to the firewall chain."""
        if ip in (self.policy.allowlist_ips or []):
            logger.info("Skipping block for allowlisted IP: %s", ip)
            return False
        
        if self.memory.is_recently_blocked(ip, self.policy.per_ip_cooldown_seconds):
            return False
            
        if self.memory.active_block_count() >= self.policy.max_blocked_ips:
            logger.warning("Maximum blocked IP threshold reached.")
            return False

        base = self._get_iptables_cmd()
        chain = self.policy.chain_name if self.ready else "INPUT"
        try:
            subprocess.run(base + ["-A", chain, "-s", ip, "-j", "DROP"], check=True, timeout=5)
            self.memory.record_block(ip, source=source, reason=reason, metadata={"chain": chain})
            return True
        except subprocess.CalledProcessError as e:
            logger.error("Failed to execute block for %s: %s", ip, e)
            return False

    def unblock_ip(self, ip: str) -> bool:
        """Removes the block rule for the specified IP."""
        base = self._get_iptables_cmd()
        chain = self.policy.chain_name if self.ready else "INPUT"
        try:
            subprocess.run(base + ["-D", chain, "-s", ip, "-j", "DROP"], check=True, timeout=5)
            self.memory.record_unblock_request(ip)
            self.memory.record_unblock_applied(ip)
            return True
        except subprocess.CalledProcessError as e:
            logger.error("Failed to execute unblock for %s: %s", ip, e)
            return False

    def unblock_all_managed(self) -> None:
        """Removes all active blocks and flushes the managed chain."""
        for ip in list(self.memory.list_active_blocks()):
            self.unblock_ip(ip)
        
        if self.ready:
            try:
                base = self._get_iptables_cmd()
                subprocess.run(base + ["-F", self.policy.chain_name], check=True, timeout=5)
            except subprocess.CalledProcessError as e:
                logger.error("Failed to flush chain %s: %s", self.policy.chain_name, e)

    def emergency_flush_input(self) -> bool:
        """Flushes the entire INPUT chain if policy permits."""
        if not self.policy.allow_emergency_flush_input:
            return False
            
        try:
            base = self._get_iptables_cmd()
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
        except subprocess.CalledProcessError as e:
            logger.error("Emergency flush of INPUT chain failed: %s", e)
            return False