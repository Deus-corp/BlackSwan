#!/usr/bin/env python3
"""Firewall manager for security swarm integration.

Handles iptables chain management, IP blocking, and safe flushing operations.
"""

from __future__ import annotations

import ipaddress
import logging
import subprocess
from typing import List, Optional

from .memory import FirewallPolicy, SecurityMemory, command_exists, new_gid

logger = logging.getLogger(__name__)


class FirewallManager:
    """Manages a dedicated iptables chain for isolated rule enforcement."""

    def __init__(self, policy: FirewallPolicy, memory: SecurityMemory) -> None:
        self.policy = policy
        self.memory = memory
        self.ready: bool = False

    def _get_iptables_cmd(self) -> Optional[List[str]]:
        """Determine base command for iptables.

        Returns None if neither iptables nor sudo is available.
        """
        if command_exists("iptables"):
            return ["iptables"]

        if command_exists("sudo"):
            return ["sudo", "iptables"]

        return None

    def ensure_chain(self) -> None:
        """Create the dedicated chain and ensure it is linked to INPUT."""
        chain = self.policy.chain_name
        base = self._get_iptables_cmd()

        if base is None:
            self.ready = False
            logger.warning("iptables not available; firewall enforcement disabled.")
            return

        try:
            subprocess.run(
                base + ["-N", chain],
                check=False,
                timeout=5,
                capture_output=True,
                text=True,
            )

            check = subprocess.run(
                base + ["-C", "INPUT", "-j", chain],
                check=False,
                timeout=5,
                capture_output=True,
                text=True,
            )

            if check.returncode != 0:
                subprocess.run(
                    base + ["-I", "INPUT", "1", "-j", chain],
                    check=True,
                    timeout=5,
                    capture_output=True,
                    text=True,
                )

            self.ready = True
            logger.info("Firewall chain '%s' initialized.", chain)

        except Exception as exc:
            self.ready = False
            logger.warning("Failed to ensure firewall chain %s: %s", chain, exc)

    def block_ip(self, ip: str, *, source: str, reason: str) -> bool:
        """Block an IP by adding a DROP rule."""
        normalized_ip = self._normalize_ip(ip)
        if normalized_ip is None:
            logger.warning("Invalid IP skipped for block: %s", ip)
            return False

        if normalized_ip in (self.policy.allowlist_ips or []):
            logger.info("Skipping block for allowlisted IP: %s", normalized_ip)
            return False

        if self.memory.is_recently_blocked(normalized_ip, self.policy.per_ip_cooldown_seconds):
            return False

        if self.memory.active_block_count() >= self.policy.max_blocked_ips:
            logger.warning("Maximum blocked IP threshold reached.")
            return False

        base = self._get_iptables_cmd()
        if base is None:
            logger.warning("iptables not available; cannot block %s", normalized_ip)
            return False

        chain = self.policy.chain_name if self.ready else "INPUT"

        try:
            exists = subprocess.run(
                base + ["-C", chain, "-s", normalized_ip, "-j", "DROP"],
                check=False,
                timeout=5,
                capture_output=True,
                text=True,
            )

            if exists.returncode != 0:
                subprocess.run(
                    base + ["-A", chain, "-s", normalized_ip, "-j", "DROP"],
                    check=True,
                    timeout=5,
                    capture_output=True,
                    text=True,
                )

            self.memory.record_block(
                normalized_ip,
                source=source,
                reason=reason,
                metadata={"chain": chain},
            )
            return True

        except subprocess.CalledProcessError as exc:
            logger.error("Failed to execute block for %s: %s", normalized_ip, exc)
            return False
        except Exception as exc:
            logger.error("Unexpected firewall block error for %s: %s", normalized_ip, exc, exc_info=True)
            return False

    def unblock_ip(self, ip: str) -> bool:
        """Remove DROP rule for the specified IP."""
        normalized_ip = self._normalize_ip(ip)
        if normalized_ip is None:
            logger.warning("Invalid IP skipped for unblock: %s", ip)
            return False

        base = self._get_iptables_cmd()
        if base is None:
            logger.warning("iptables not available; marking unblock as applied for %s", normalized_ip)
            self.memory.record_unblock_request(normalized_ip)
            self.memory.record_unblock_applied(normalized_ip)
            return True

        chain = self.policy.chain_name if self.ready else "INPUT"

        try:
            result = subprocess.run(
                base + ["-D", chain, "-s", normalized_ip, "-j", "DROP"],
                check=False,
                timeout=5,
                capture_output=True,
                text=True,
            )

            if result.returncode not in {0, 1}:
                logger.warning(
                    "iptables unblock returned %s for %s: %s",
                    result.returncode,
                    normalized_ip,
                    (result.stderr or "").strip(),
                )

            self.memory.record_unblock_request(normalized_ip)
            self.memory.record_unblock_applied(normalized_ip)
            return True

        except Exception as exc:
            logger.error("Failed to execute unblock for %s: %s", normalized_ip, exc, exc_info=True)
            return False

    def unblock_all_managed(self) -> None:
        """Remove all active blocks and flush the managed chain."""
        for ip in list(self.memory.list_active_blocks()):
            self.unblock_ip(ip)

        if not self.ready:
            self.memory.record_unblock_request(None)
            self.memory.record_unblock_applied(None)
            return

        base = self._get_iptables_cmd()
        if base is None:
            self.memory.record_unblock_request(None)
            self.memory.record_unblock_applied(None)
            return

        try:
            subprocess.run(
                base + ["-F", self.policy.chain_name],
                check=True,
                timeout=5,
                capture_output=True,
                text=True,
            )
            self.memory.record_unblock_request(None)
            self.memory.record_unblock_applied(None)
        except subprocess.CalledProcessError as exc:
            logger.error("Failed to flush chain %s: %s", self.policy.chain_name, exc)
        except Exception as exc:
            logger.error("Unexpected flush error for chain %s: %s", self.policy.chain_name, exc, exc_info=True)

    def emergency_flush_input(self) -> bool:
        """Flush entire INPUT chain if policy permits."""
        if not self.policy.allow_emergency_flush_input:
            return False

        base = self._get_iptables_cmd()
        if base is None:
            logger.warning("iptables not available; emergency flush cannot be applied.")
            return False

        try:
            subprocess.run(
                base + ["-F", "INPUT"],
                check=True,
                timeout=5,
                capture_output=True,
                text=True,
            )

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
            self.memory.record_unblock_request(None)
            self.memory.record_unblock_applied(None)
            return True

        except subprocess.CalledProcessError as exc:
            logger.error("Emergency flush of INPUT chain failed: %s", exc)
            return False
        except Exception as exc:
            logger.error("Unexpected emergency flush error: %s", exc, exc_info=True)
            return False

    @staticmethod
    def _normalize_ip(ip: str) -> Optional[str]:
        try:
            return str(ipaddress.ip_address(str(ip).strip()))
        except ValueError:
            return None