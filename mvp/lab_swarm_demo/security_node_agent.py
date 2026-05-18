#!/usr/bin/env python3
"""
Security Node Agent – автономный узел роя безопасности.
Мониторит логи, применяет правила файрвола, обменивается данными через CRDT.

This agent runs on individual nodes, performing local security tasks like
monitoring logs for suspicious activity, managing firewall rules, scanning
for open ports, verifying file integrity, and auditing Python packages.
It communicates its status and receives commands via a CRDT system.
"""
import asyncio
import logging
import os
import sys
import time
import uuid
import random
import subprocess
import re
import hashlib
import json  # Added missing import for json
from typing import Dict, Any, List, Optional, Set

# Assuming 'src' and 'mvp/lab_swarm_demo' are in PYTHONPATH or the script
# is run from the project root.
from src.core.crdt_adapter import CRDTAdapter
from src.core.event_store import EventStore
from src.core.events import Event
from mvp.lab_swarm_demo.swarm_config import config

# Configure logging for the module
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s')
logger = logging.getLogger("SecurityNode")

# Global state for blocked IPs (shared across the module, not ideal for multiple
# SecurityNode instances in the same process, but typical for single-instance agents)
BLOCKED_IPS: Set[str] = set()
MAX_BLOCKED_IPS: int = 100

# Constants for task scheduling intervals (in main loop steps)
MAIN_LOOP_SLEEP_SECONDS: float = 2.0
LOG_MONITOR_INTERVAL_STEPS: int = 30
HEARTBEAT_INTERVAL_STEPS: int = 20
PORT_SCAN_INTERVAL_STEPS: int = 60
INTEGRITY_CHECK_INTERVAL_STEPS: int = 120
PIP_AUDIT_INTERVAL_STEPS: int = 150

class SecurityNode:
    """
    Autonomous security node agent.
    Monitors logs, applies firewall rules, and exchanges data via CRDT.
    """
    def __init__(self, node_id: Optional[str] = None) -> None:
        """
        Initializes the SecurityNode with a unique ID and its communication/storage components.

        Args:
            node_id: A unique identifier for this agent instance. If None, one will be generated.
        """
        self.node_id: str = node_id or f"sec-{uuid.uuid4().hex[:8]}"
        self.crdt: CRDTAdapter = CRDTAdapter(node_id=self.node_id, db_path=config.crdt_db_path)
        
        # Use separate files for security events to avoid collision with trading swarm
        self.event_store: EventStore = EventStore(
            ledger_path="./data/ledgers/sec_events.jsonl",
            sqlite_path="./data/ledgers/sec_events.db",
        )
        self.step: int = 0
        # Baseline hashes for file integrity checks, stored per instance
        self._baseline_file_hashes: Dict[str, str] = {}
        # List of critical files to monitor for integrity
        self._critical_files_to_monitor: List[str] = [
            "/app/mvp/lab_swarm_demo/security_node_agent.py",
            "/app/src/core/crdt_adapter.py",
            "/app/src/intelligence/llm_client.py", # Example: assuming LLM client is critical
        ]

    async def run(self) -> None:
        """
        Starts the main loop for the SecurityNode agent, performing security tasks periodically.
        The agent will run indefinitely until interrupted.
        """
        logger.info(f"🛡️ SecurityNode {self.node_id} started")
        try:
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
                    # Catch and log specific errors for individual tasks without stopping the agent
                    logger.error(f"Security task failed during step {self.step}: {e}", exc_info=True)
                await asyncio.sleep(MAIN_LOOP_SLEEP_SECONDS)
        except asyncio.CancelledError:
            logger.info(f"SecurityNode {self.node_id} run cancelled.")
        except Exception as e:
            logger.exception(f"SecurityNode {self.node_id} encountered a critical error: {e}")

    async def _monitor_logs(self) -> None:
        """
        Checks system logs (e.g., journalctl for SSH failures) for suspicious activity.
        Identified suspicious IPs are added to the block list.
        """
        if self.step % LOG_MONITOR_INTERVAL_STEPS != 0:
            return

        logger.debug("Monitoring logs for suspicious activity...")
        suspicious_ips: List[str] = []
        try:
            # Check for failed SSH attempts
            # Limiting to 2 minutes ago to avoid reprocessing old logs repeatedly
            result = subprocess.run(
                ["journalctl", "-u", "ssh", "--since", "2 minutes ago", "-o", "cat"],
                capture_output=True, text=True, timeout=5, check=True
            )
            failed_attempts = re.findall(r'Failed password for .* from (\S+) port', result.stdout)
            for ip in failed_attempts:
                if ip not in BLOCKED_IPS:
                    suspicious_ips.append(ip)
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to run journalctl command (exit code {e.returncode}): {e.stderr.strip()}")
        except subprocess.TimeoutExpired:
            logger.warning("journalctl command timed out.")
        except FileNotFoundError:
            logger.warning("journalctl not found. Log monitoring skipped.")
        except Exception as e:
            logger.error(f"Error during log monitoring: {e}", exc_info=True)

        for ip in suspicious_ips:
            await self._block_ip(ip)

    async def _block_ip(self, ip: str) -> None:
        """
        Blocks a given IP address using iptables and records an event.

        Args:
            ip: The IP address to block.
        """
        if ip in BLOCKED_IPS:
            logger.debug(f"IP {ip} is already blocked.")
            return
        if len(BLOCKED_IPS) >= MAX_BLOCKED_IPS:
            logger.warning(f"Max blocked IPs ({MAX_BLOCKED_IPS}) reached. Cannot block {ip}.")
            return

        logger.info(f"🚫 Blocking IP: {ip}")
        try:
            # Use iptables to drop incoming packets from the specified IP
            subprocess.run(["sudo", "iptables", "-A", "INPUT", "-s", ip, "-j", "DROP"], check=True, timeout=5)
            BLOCKED_IPS.add(ip)
            self.event_store.append(Event.create(
                node_id=self.node_id,
                event_type="ip_blocked",
                payload={"ip": ip, "timestamp": time.time()},
                parent_id=None,
            ))
            logger.info(f"Successfully blocked IP: {ip}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to execute iptables command to block {ip} (exit code {e.returncode}): {e.stderr.strip()}")
        except subprocess.TimeoutExpired:
            logger.warning(f"iptables command to block {ip} timed out.")
        except FileNotFoundError:
            logger.error("iptables or sudo command not found. Cannot block IP.")
        except Exception as e:
            logger.error(f"An unexpected error occurred while blocking IP {ip}: {e}", exc_info=True)

    async def _apply_security_commands(self) -> None:
        """
        Applies security commands received from the MetaAgent-Security via CRDT.
        Currently supports 'UNBLOCK_ALL'.
        """
        logger.debug("Checking for security commands from MetaAgent...")
        all_state: Dict[str, Any] = self.crdt.state
        commands: List[Dict[str, Any]] = [
            v for k, v in all_state.items()
            if isinstance(v, dict) and v.get("type") == "sec_command"
        ]

        for cmd in commands:
            action: str = cmd.get("data", {}).get("action", "")
            command_id: Optional[str] = cmd.get("gid")

            # Check if command is still valid (not expired)
            if cmd.get("expires_at", 0) > time.time():
                if action == "UNBLOCK_ALL":
                    logger.info(f"Received UNBLOCK_ALL command (GID: {command_id}). Executing...")
                    await self._unblock_all()
                    # Acknowledge or mark command as processed if CRDT supports it,
                    # or ensure idempotency. For now, simply execute.
            else:
                logger.debug(f"Expired security command ignored (GID: {command_id}).")

    async def _unblock_all(self) -> None:
        """
        Removes all IP blocks imposed by this agent using iptables.
        """
        logger.info("🔓 Unblocking all IPs")
        try:
            # Flush all rules in the INPUT chain
            subprocess.run(["sudo", "iptables", "-F", "INPUT"], check=True, timeout=5)
            BLOCKED_IPS.clear()
            logger.info("Successfully unblocked all IPs.")
            self.event_store.append(Event.create(
                node_id=self.node_id,
                event_type="all_ips_unblocked",
                payload={"timestamp": time.time()},
                parent_id=None,
            ))
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to execute iptables command to unblock all IPs (exit code {e.returncode}): {e.stderr.strip()}")
        except subprocess.TimeoutExpired:
            logger.warning("iptables command to unblock all IPs timed out.")
        except FileNotFoundError:
            logger.error("iptables or sudo command not found. Cannot unblock all IPs.")
        except Exception as e:
            logger.error(f"An unexpected error occurred while unblocking all IPs: {e}", exc_info=True)

    async def _send_heartbeat(self) -> None:
        """
        Sends a periodic heartbeat message to the CRDT, reporting the node's status.
        Includes the number of currently blocked IPs.
        """
        if self.step % HEARTBEAT_INTERVAL_STEPS != 0:
            return

        logger.debug("Sending heartbeat to CRDT...")
        heartbeat: Dict[str, Any] = {
            "type": "security_heartbeat",
            "node_id": self.node_id,
            "blocked_ips": len(BLOCKED_IPS),
            "timestamp": time.time(),
            "gid": f"sec_hb_{int(time.time() * 1000)}_{self.node_id}", # More unique GID
        }
        await self.crdt.add_genome(heartbeat)
        logger.debug(f"Heartbeat sent. Blocked IPs: {len(BLOCKED_IPS)}")

    async def _scan_ports(self) -> None:
        """
        Scans common ports on localhost to detect unexpectedly open ports.
        This is a safe local check and does not perform external network scans.
        """
        if self.step % PORT_SCAN_INTERVAL_STEPS != 0:
            return

        logger.debug("Scanning for open ports on localhost...")
        open_ports: List[int] = []
        # Common ports to check. Extend as needed.
        ports_to_check: List[int] = [22, 80, 443, 8080, 8443, 3000, 5000]

        for port in ports_to_check:
            try:
                # Attempt to open a connection to localhost on the port
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection('127.0.0.1', port),
                    timeout=1.0 # Shorter timeout for individual port checks
                )
                writer.close()
                await writer.wait_closed()
                open_ports.append(port)
            except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
                # Connection refused or timed out, port is likely closed or filtered
                pass
            except Exception as e:
                logger.warning(f"Unexpected error while scanning port {port}: {e}")

        if open_ports:
            logger.warning(f"🔍 Open ports detected on localhost: {open_ports}")
            self.event_store.append(Event.create(
                node_id=self.node_id,
                event_type="open_ports_detected",
                payload={"ports": open_ports, "timestamp": time.time()},
                parent_id=None,
            ))
        else:
            logger.debug("No unexpected open ports detected.")

    async def _verify_integrity(self) -> None:
        """
        Checks SHA256 hashes of critical files and compares them against a baseline.
        Alerts if changes are detected. The first run establishes the baseline.
        """
        if self.step % INTEGRITY_CHECK_INTERVAL_STEPS != 0:
            return

        logger.debug("Verifying file integrity...")
        changed_files: List[str] = []
        for filepath in self._critical_files_to_monitor:
            if not os.path.exists(filepath):
                logger.warning(f"Critical file not found: {filepath}")
                continue

            try:
                with open(filepath, "rb") as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()

                if filepath not in self._baseline_file_hashes:
                    # First run, establish baseline
                    self._baseline_file_hashes[filepath] = file_hash
                    logger.debug(f"Established baseline hash for {filepath}: {file_hash}")
                elif self._baseline_file_hashes[filepath] != file_hash:
                    # Hash mismatch detected
                    changed_files.append(filepath)
                    logger.warning(f"🔴 File integrity mismatch for {filepath}! "
                                   f"Expected: {self._baseline_file_hashes[filepath]}, Found: {file_hash}")
                    # Update baseline to new hash after alert to avoid repeated alerts on same change
                    self._baseline_file_hashes[filepath] = file_hash
                else:
                    logger.debug(f"File integrity OK for {filepath}.")
            except IOError as e:
                logger.error(f"Error reading file {filepath} for integrity check: {e}")
            except Exception as e:
                logger.error(f"Unexpected error during integrity check for {filepath}: {e}", exc_info=True)

        if changed_files:
            logger.warning(f"🔴 File integrity alert: The following critical files have changed: {changed_files}")
            self.event_store.append(Event.create(
                node_id=self.node_id,
                event_type="file_integrity_alert",
                payload={"changed_files": changed_files, "timestamp": time.time()},
                parent_id=None,
            ))

    async def _pip_audit(self) -> None:
        """
        Checks Python packages for known vulnerabilities using `pip-audit`.
        Requires `pip-audit` to be installed in the environment.
        """
        if self.step % PIP_AUDIT_INTERVAL_STEPS != 0:
            return

        logger.debug("Performing pip-audit for vulnerabilities...")
        try:
            # Run pip-audit and capture output as JSON
            result = subprocess.run(
                ["pip", "audit", "--format", "json"],
                capture_output=True, text=True, timeout=30, check=False # pip audit exits non-zero if vulns found
            )
            
            if result.returncode == 0:
                # No vulnerabilities found or pip-audit ran successfully with no issues
                logger.debug("pip-audit completed with no vulnerabilities found.")
                return
            elif result.returncode == 1: # pip-audit exits 1 if vulnerabilities are found
                try:
                    vulnerabilities = json.loads(result.stdout)
                    if vulnerabilities:
                        logger.warning(f"🔴 Found {len(vulnerabilities)} Python package vulnerabilities!")
                        self.event_store.append(Event.create(
                            node_id=self.node_id,
                            event_type="vulnerability_alert",
                            payload={"vulnerabilities": vulnerabilities, "timestamp": time.time()},
                            parent_id=None,
                        ))
                    else: # Should not happen if returncode is 1, but for safety
                         logger.warning("pip-audit exited with code 1, but no vulnerabilities parsed from JSON.")
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse pip-audit JSON output: {e}. Raw output: {result.stdout}")
            else: # Other non-zero exit codes indicate an error in pip-audit itself
                logger.error(f"pip-audit failed with exit code {result.returncode}: {result.stderr.strip()}")

        except subprocess.TimeoutExpired:
            logger.warning("pip-audit command timed out after 30 seconds.")
        except FileNotFoundError:
            logger.warning("pip-audit command not found. Please ensure 'pip install pip-audit' has been run.")
        except Exception as e:
            logger.error(f"An unexpected error occurred during pip-audit: {e}", exc_info=True)

if __name__ == "__main__":
    node = SecurityNode()
    try:
        asyncio.run(node.run())
    except KeyboardInterrupt:
        logger.info("SecurityNode stopped by user (KeyboardInterrupt).")
    except Exception as e:
        logger.critical(f"SecurityNode encountered an unexpected error during startup or main loop: {e}", exc_info=True)