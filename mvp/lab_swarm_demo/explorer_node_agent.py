#!/usr/bin/env python3
"""
Explorer Node Agent – собирает метаданные из интернета, публикует находки в CRDT.
"""
import asyncio, logging, os, sys, time, uuid, json
import aiohttp
from typing import Dict, Any, List, Optional

from src.core.crdt_adapter import CRDTAdapter
from src.core.events import Event
from src.core.event_store import EventStore
from swarm_config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s')
logger = logging.getLogger("ExplorerNode")

DEFAULT_TARGETS = [
    "https://httpbin.org/ip",
    "https://api.github.com",
]

class ExplorerNode:
    def __init__(self, node_id: str = None):
        self.node_id = node_id or f"exp-{uuid.uuid4().hex[:8]}"
        self.crdt = CRDTAdapter(node_id=self.node_id, db_path=config.crdt_db_path)
        self.event_store = EventStore(
            ledger_path="./data/ledgers/exp_events.jsonl",
            sqlite_path="./data/ledgers/exp_events.db",
        )
        self.step = 0
        self.session = None

    async def run(self):
        logger.info(f"🌐 ExplorerNode {self.node_id} started")
        self.session = aiohttp.ClientSession()
        while True:
            self.step += 1
            try:
                await self._explore()
                await self._send_heartbeat()
            except Exception as e:
                logger.error(f"Explorer cycle error: {e}")
            await asyncio.sleep(30.0)   # раз в 30 секунд

    async def _explore(self):
        # Единый вызов CRDT
        all_state = self.crdt.state

        # Проверяем команды от Overseer
        cmds = [v for k, v in all_state.items() if isinstance(v, dict) and v.get("type") == "explorer_command"]
        if cmds:
            latest_cmd = max(cmds, key=lambda x: x.get("timestamp", 0))
            if latest_cmd.get("data", {}).get("action") == "PAUSE":
                return

        # Получаем цели
        targets = await self._get_targets()

        # Фильтрация дубликатов
        recent_findings = [
            v for k, v in all_state.items()
            if isinstance(v, dict) and v.get("type") == "explorer_finding"
        ]
        recent_urls = {f["url"] for f in recent_findings[-10:]}

        for url in targets[:3]:
            if url in recent_urls:
                continue
            try:
                async with self.session.get(url, timeout=10) as resp:
                    content = await resp.text()
                    finding = {
                        "type": "explorer_finding",
                        "url": url,
                        "status": resp.status,
                        "content_preview": content[:200],
                        "timestamp": time.time(),
                        "gid": f"exp_f_{int(time.time())}",
                    }
                    await self.crdt.add_genome(finding)
                    logger.info(f"🔗 Found: {url} ({resp.status})")
            except Exception as e:
                logger.warning(f"Failed to fetch {url}: {e}")

    async def _get_targets(self) -> List[str]:
        # Читаем из CRDT команды от MetaAgent-Explorer
        all_state = self.crdt.state
        cmds = [v for k, v in all_state.items() if isinstance(v, dict) and v.get("type") == "explorer_targets"]
        if cmds:
            latest = max(cmds, key=lambda x: x.get("timestamp", 0))
            return latest.get("data", {}).get("urls", DEFAULT_TARGETS)
        return DEFAULT_TARGETS

    async def _send_heartbeat(self):
        if self.step % 5 != 0:
            return
        heartbeat = {
            "type": "explorer_heartbeat",
            "node_id": self.node_id,
            "timestamp": time.time(),
            "gid": f"exp_hb_{int(time.time())}",
        }
        await self.crdt.add_genome(heartbeat)

if __name__ == "__main__":
    node = ExplorerNode()
    try:
        asyncio.run(node.run())
    except KeyboardInterrupt:
        logger.info("ExplorerNode stopped.")