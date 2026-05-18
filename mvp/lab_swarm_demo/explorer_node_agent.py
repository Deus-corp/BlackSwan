#!/usr/bin/env python3
"""
Explorer Node Agent – собирает метаданные из интернета, публикует находки в CRDT.
"""
import asyncio, logging, os, sys, time, uuid, json
import aiohttp
from typing import Dict, Any, List, Optional

from src.core.crdt_adapter import CRDTAdapter
from src.core.events import Event # Event is imported but not used, kept as per instructions
from src.core.event_store import EventStore
from swarm_config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s')
logger = logging.getLogger("ExplorerNode")

DEFAULT_TARGETS: List[str] = [
    "https://httpbin.org/ip",
    "https://api.github.com",
]

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
        """
        self.node_id: str = node_id or f"exp-{uuid.uuid4().hex[:8]}"
        self.crdt: CRDTAdapter = CRDTAdapter(node_id=self.node_id, db_path=config.crdt_db_path)
        self.event_store: EventStore = EventStore(
            ledger_path="./data/ledgers/exp_events.jsonl",
            sqlite_path="./data/ledgers/exp_events.db",
        )
        self.step: int = 0
        self.session: Optional[aiohttp.ClientSession] = None

    async def run(self) -> None:
        """
        Runs the main asynchronous loop of the ExplorerNode.
        It initializes an aiohttp ClientSession, then repeatedly performs
        exploration and sends heartbeats. The session is properly closed
        when the loop exits.
        """
        logger.info(f"🌐 ExplorerNode {self.node_id} started")
        self.session = aiohttp.ClientSession()
        try:
            while True:
                self.step += 1
                try:
                    await self._explore()
                    await self._send_heartbeat()
                except Exception as e:
                    logger.error(f"Explorer cycle error: {e}")
                await asyncio.sleep(30.0)   # раз в 30 секунд
        finally:
            if self.session:
                await self.session.close()
                logger.info("aiohttp ClientSession closed.")

    async def _explore(self) -> None:
        """
        Carries out the exploration task:
        1. Fetches the current state from CRDT to check for commands and recent findings.
        2. If a "PAUSE" command is active, returns immediately.
        3. Retrieves target URLs, prioritizing those from a MetaAgent, otherwise using defaults.
        4. Filters out recently visited URLs to avoid duplicates.
        5. Fetches content from a subset of target URLs (max 3), records findings
           (URL, status, content preview), and publishes them to CRDT.
        Handles network errors during fetching.
        """
        # Единый вызов CRDT
        all_state: Dict[str, Any] = self.crdt.state

        # Проверяем команды от Overseer
        cmds: List[Dict[str, Any]] = [v for k, v in all_state.items() if isinstance(v, dict) and v.get("type") == "explorer_command"]
        if cmds:
            latest_cmd: Dict[str, Any] = max(cmds, key=lambda x: x.get("timestamp", 0))
            if latest_cmd.get("data", {}).get("action") == "PAUSE":
                return

        # Получаем цели
        targets: List[str] = await self._get_targets()

        # Фильтрация дубликатов
        recent_findings: List[Dict[str, Any]] = [
            v for k, v in all_state.items()
            if isinstance(v, dict) and v.get("type") == "explorer_finding"
        ]
        # Ensure 'url' key exists before adding to set
        recent_urls: set[str] = {f["url"] for f in recent_findings[-10:] if "url" in f}

        for url in targets[:3]: # Process up to 3 targets per cycle
            if url in recent_urls:
                continue
            try:
                # self.session is guaranteed to be initialized and not None here due to run() method structure
                async with self.session.get(url, timeout=10) as resp: # type: ignore [union-attr]
                    content: str = await resp.text()
                    finding: Dict[str, Any] = {
                        "type": "explorer_finding",
                        "url": url,
                        "status": resp.status,
                        "content_preview": content[:200], # Store first 200 chars as preview
                        "timestamp": time.time(),
                        "gid": f"exp_f_{int(time.time())}",
                    }
                    await self.crdt.add_genome(finding)
                    logger.info(f"🔗 Found: {url} ({resp.status})")
            except Exception as e:
                logger.warning(f"Failed to fetch {url}: {e}")

    async def _get_targets(self) -> List[str]:
        """
        Retrieves a list of target URLs for exploration.
        It first checks the CRDT for "explorer_targets" suggested by a MetaAgent.
        If found, it returns the URLs from the latest such command.
        Otherwise, it falls back to the `DEFAULT_TARGETS`.
        Ensures all returned URLs are strings.
        """
        # Читаем из CRDT команды от MetaAgent-Explorer
        all_state: Dict[str, Any] = self.crdt.state
        cmds: List[Dict[str, Any]] = [v for k, v in all_state.items() if isinstance(v, dict) and v.get("type") == "explorer_targets"]
        if cmds:
            latest: Dict[str, Any] = max(cmds, key=lambda x: x.get("timestamp", 0))
            # Ensure 'urls' exists and contains only string elements
            return [str(u) for u in latest.get("data", {}).get("urls", []) if isinstance(u, str)]
        return DEFAULT_TARGETS

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
            "gid": f"exp_hb_{int(time.time())}",
        }
        await self.crdt.add_genome(heartbeat)

if __name__ == "__main__":
    node: ExplorerNode = ExplorerNode()
    try:
        asyncio.run(node.run())
    except KeyboardInterrupt:
        logger.info("ExplorerNode stopped.")