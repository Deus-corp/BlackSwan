#!/usr/bin/env python3
"""
Explorer Node Agent – collects metadata from the internet, publishes findings to CRDT.

This agent is responsible for actively browsing specified URLs, fetching their content,
and extracting relevant metadata (like HTTP status, content preview). It then publishes
these "explorer_finding" records to the CRDT, making them available for other agents
(like the ExplorerMetaAgent) to process. It also sends periodic heartbeats.
"""
import asyncio
import logging
import os
import sys
import time
import uuid
import json
import aiohttp
from typing import Dict, Any, List, Optional, Set, Tuple, Final

from src.core.crdt_adapter import CRDTAdapter
# Event is imported but not used within ExplorerNode's logic.
# It can be removed as it's not utilized in this file.
# from src.core.events import Event
from src.core.event_store import EventStore
from swarm_config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s')
logger = logging.getLogger("ExplorerNode")

# Using a tuple for DEFAULT_TARGETS implies immutability for this constant set.
DEFAULT_TARGETS: Final[Tuple[str, ...]] = (
    "https://httpbin.org/ip",
    "https://api.github.com",
    "https://www.google.com",
)

class ExplorerNode:
    """
    Explorer Node Agent collects metadata from the internet by visiting URLs
    and publishes these findings (e.g., URL status, content preview) to a CRDT.
    It also sends heartbeats to signal its active status.
    """
    def __init__(self, node_id: Optional[str] = None):
        """
        Initializes the ExplorerNode with a unique ID, CRDT adapter,
        an event store, a step counter, and an uninitialized aiohttp ClientSession.

        Args:
            node_id (Optional[str]): A unique identifier for this node. If None, one is generated.
        """
        self.node_id: str = node_id or f"exp-{uuid.uuid4().hex[:8]}"
        self.crdt: CRDTAdapter = CRDTAdapter(node_id=self.node_id, db_path=config.crdt_db_path)
        # EventStore is initialized but its methods are not explicitly called in the provided code.
        # It's assumed to be part of a broader eventing infrastructure or for future use.
        self.event_store: EventStore = EventStore(
            ledger_path="./data/ledgers/exp_events.jsonl",
            sqlite_path="./data/ledgers/exp_events.db",
        )
        self.step: int = 0
        self.session: Optional[aiohttp.ClientSession] = None
        # Keep track of recently visited URLs to avoid immediate re-visits within a short period.
        self._recently_visited_urls: Set[str] = set()
        logger.info(f"🌐 Initializing ExplorerNode with ID: {self.node_id}")

    def __repr__(self) -> str:
        """
        Returns a string representation of the ExplorerNode instance.
        """
        return f"ExplorerNode(node_id='{self.node_id}', step={self.step})"

    async def run(self) -> None:
        """
        Runs the main asynchronous loop of the ExplorerNode.

        It initializes an aiohttp ClientSession, then repeatedly performs
        exploration and sends heartbeats. The session is properly closed
        when the loop exits, ensuring no resource leaks.
        The loop can be gracefully stopped by a KeyboardInterrupt or an
        `asyncio.CancelledError` (e.g., from a PAUSE command or external signal).
        """
        logger.info(f"🌐 ExplorerNode {self.node_id} started")
        # ClientSession should be created within an async context.
        # It's created here once and closed in the finally block.
        self.session = aiohttp.ClientSession()
        try:
            while True:
                self.step += 1
                try:
                    await self._check_and_execute_commands()
                    await self._explore()
                    await self._send_heartbeat()
                except asyncio.CancelledError:
                    # This specific CancelledError is used to handle commands like PAUSE
                    # and will break out of the main loop, effectively stopping the agent.
                    logger.info("ExplorerNode task cancelled by command. Exiting run loop.")
                    break
                except Exception as e:
                    logger.error(f"Explorer cycle error: {e}", exc_info=True)
                await asyncio.sleep(30.0)   # Sleep for 30 seconds before the next cycle
        finally:
            if self.session:
                await self.session.close()
                logger.info("aiohttp ClientSession closed.")
            logger.info("ExplorerNode run loop finished.")

    async def _check_and_execute_commands(self) -> None:
        """
        Checks the CRDT for active commands (e.g., PAUSE) and executes them.
        If a PAUSE command is found, it raises an asyncio.CancelledError
        to signal a temporary halt to the main `run` loop. This allows for
        external control over the agent's operation.
        """
        # CRDTAdapter.state is assumed to be an in-memory representation, hence not awaited.
        all_state: Dict[str, Any] = self.crdt.state
        commands: List[Dict[str, Any]] = [
            v for k, v in all_state.items()
            if isinstance(v, dict) and v.get("type") == "explorer_command"
        ]
        if commands:
            # Sort by timestamp to ensure the latest command is considered.
            latest_cmd: Dict[str, Any] = max(commands, key=lambda x: x.get("timestamp", 0))
            if latest_cmd.get("data", {}).get("action") == "PAUSE":
                logger.info(f"Received PAUSE command. Halting exploration for now. Command ID: {latest_cmd.get('gid')}")
                # Raising CancelledError here effectively stops the `run` loop.
                # For a true "temporary pause" that eventually resumes without agent restart,
                # this logic would need to be changed to set a `self.paused` flag and
                # introduce a `while self.paused: await asyncio.sleep(...)` block.
                # The current implementation's effect is to stop until restarted or cancelled again.
                raise asyncio.CancelledError("ExplorerNode paused by command.")

    async def _explore(self) -> None:
        """
        Carries out the exploration task:
        1. Retrieves target URLs, prioritizing those from a MetaAgent, otherwise using defaults.
        2. Filters out recently visited URLs to avoid duplicates within a short period.
        3. Fetches content from a subset of target URLs (max 3), records findings
           (URL, status, content preview), and publishes them to CRDT.
        Handles various network errors during fetching.
        """
        if self.session is None:
            logger.error("aiohttp ClientSession is not initialized. Cannot explore.")
            return

        targets: List[str] = await self._get_targets()
        urls_to_visit: List[str] = []

        # Populate urls_to_visit with unique and not recently visited URLs.
        for url in targets:
            if url not in self._recently_visited_urls:
                urls_to_visit.append(url)
            if len(urls_to_visit) >= 3: # Process up to 3 unique targets per cycle
                break

        if not urls_to_visit:
            logger.debug("No new unique targets to explore in this cycle.")
            return

        for url in urls_to_visit:
            self._recently_visited_urls.add(url) # Add to recently visited before attempting fetch
            try:
                # self.session is guaranteed to be initialized due to the check at the start of _explore()
                # and by the `run` method's `self.session = aiohttp.ClientSession()`.
                async with self.session.get(url, timeout=10) as resp:
                    resp.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
                    content: str = await resp.text()
                    finding: Dict[str, Any] = {
                        "type": "explorer_finding",
                        "url": url,
                        "status": resp.status,
                        "content_preview": content[:200], # Store first 200 chars as preview
                        "timestamp": time.time(),
                        "gid": f"exp_f_{int(time.time())}_{uuid.uuid4().hex[:4]}", # Unique GID
                    }
                    await self.crdt.add_genome(finding)
                    logger.info(f"🔗 Found: {url} (Status: {resp.status})")
            except aiohttp.ClientResponseError as e:
                logger.warning(f"Failed to fetch {url} due to HTTP error: {e.status} {e.message}")
            except aiohttp.ClientConnectorError as e:
                logger.warning(f"Failed to connect to {url}: {e}")
            except asyncio.TimeoutError:
                logger.warning(f"Timeout while fetching {url}")
            except Exception as e: # Catch any other unexpected errors during fetching
                logger.error(f"An unexpected error occurred while fetching {url}: {e}", exc_info=True)

        # Clear _recently_visited_urls after a certain number of cycles.
        # This prevents it from growing indefinitely and allows re-visiting old URLs eventually.
        # Clearing every 10 steps (approx 5 minutes with a 30s cycle) seems reasonable.
        if self.step % 10 == 0:
            self._recently_visited_urls.clear()
            logger.debug("Cleared recently visited URLs cache.")


    async def _get_targets(self) -> List[str]:
        """
        Retrieves a list of target URLs for exploration.
        It first checks the CRDT for "explorer_targets" suggested by a MetaAgent.
        If found, it returns the URLs from the latest such command.
        Otherwise, it falls back to the `DEFAULT_TARGETS`.
        Ensures all returned URLs are valid strings.

        Returns:
            List[str]: A list of URLs to explore.
        """
        # CRDTAdapter.state is assumed to be an in-memory representation, hence not awaited.
        all_state: Dict[str, Any] = self.crdt.state
        meta_agent_targets: List[Dict[str, Any]] = [
            v for k, v in all_state.items()
            if isinstance(v, dict) and v.get("type") == "explorer_targets"
        ]
        if meta_agent_targets:
            # Sort by timestamp to get the absolute latest targets command.
            latest: Dict[str, Any] = max(meta_agent_targets, key=lambda x: x.get("timestamp", 0))
            urls = latest.get("data", {}).get("urls", [])
            # Filter for valid string URLs, strip whitespace, and remove duplicates.
            valid_urls: List[str] = list(dict.fromkeys([
                str(u).strip() for u in urls
                if isinstance(u, str) and u.strip() # Ensure it's a non-empty string after stripping
            ]))
            if valid_urls:
                logger.debug(f"Using MetaAgent suggested targets: {valid_urls}")
                return valid_urls

        logger.debug("Using default targets as no MetaAgent targets are available or valid.")
        return list(DEFAULT_TARGETS) # Convert tuple to list for consistency in return type.

    async def _send_heartbeat(self) -> None:
        """
        Sends a heartbeat message to the CRDT every 5 steps.
        This signals that the ExplorerNode is active and operational.
        """
        if self.step % 5 != 0:
            return
        heartbeat: Dict[str, Any] = {
            "type": "explorer_heartbeat",
            "node_id": self.node_id,
            "timestamp": time.time(),
            "gid": f"exp_hb_{int(time.time())}_{uuid.uuid4().hex[:4]}", # Unique GID for the heartbeat
        }
        await self.crdt.add_genome(heartbeat)
        logger.debug(f"Sent heartbeat (step {self.step}).")


if __name__ == "__main__":
    node: ExplorerNode = ExplorerNode()
    try:
        asyncio.run(node.run())
    except KeyboardInterrupt:
        logger.info("ExplorerNode stopped by user (KeyboardInterrupt).")
    except asyncio.CancelledError:
        # This could be caught if _check_and_execute_commands raises it, or if an external
        # cancellation signal is sent to the running task.
        logger.info("ExplorerNode stopped due to a cancellation event (e.g., PAUSE command or external signal).")
    except Exception as e:
        logger.critical(f"ExplorerNode encountered a fatal error: {e}", exc_info=True)