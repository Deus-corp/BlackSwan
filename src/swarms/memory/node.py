#!/usr/bin/env python3
"""Memory swarm node.

The memory swarm is responsible for memory-oriented autonomous functions:
episodic memory, semantic memory, retrieval, consolidation, and gold sample
export. This initial node is intentionally minimal: it publishes canonical
swarm heartbeats so Overseer and dashboard layers can see memory as a first-
class swarm.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import uuid
from typing import Any, Optional

from src.core.crdt_adapter import CRDTAdapter
from src.swarms.memory.heartbeat import build_memory_heartbeat
from swarm_config import config

logger = logging.getLogger(__name__)

DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 30.0


class MemorySwarmNode:
    """Minimal memory swarm node with CRDT heartbeat publishing."""

    def __init__(
        self,
        node_id: Optional[str] = None,
        heartbeat_interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    ) -> None:
        if heartbeat_interval_seconds <= 0:
            raise ValueError("heartbeat_interval_seconds must be positive")

        self.node_id = node_id or os.environ.get("MEMORY_NODE_ID") or f"memory-{uuid.uuid4().hex[:8]}"
        self.heartbeat_interval_seconds = float(heartbeat_interval_seconds)
        self._stop_event = asyncio.Event()

        self.crdt = CRDTAdapter(
            node_id=self.node_id,
            db_path=config.crdt_db_path,
        )

        self.heartbeats_published = 0
        self.last_error = ""

        logger.info(
            "MemorySwarmNode initialized node_id=%s heartbeat_interval=%.1fs",
            self.node_id,
            self.heartbeat_interval_seconds,
        )

    async def publish_heartbeat(self) -> None:
        """Publish canonical memory swarm heartbeat."""
        payload = build_memory_heartbeat(
            self.node_id,
            metrics={
                "heartbeats_published": self.heartbeats_published,
                "episodic_records": 0,
                "semantic_rules": 0,
                "pending_consolidations": 0,
            },
            details={
                "last_error": self.last_error,
                "crdt_db_path": str(config.crdt_db_path),
            },
            status="running" if not self.last_error else "degraded",
        )

        await self.crdt.add_genome(payload)
        self.heartbeats_published += 1
        logger.info(
            "[%s] Published memory swarm heartbeat count=%d",
            self.node_id,
            self.heartbeats_published,
        )

    async def start(self) -> None:
        """Run heartbeat loop until stopped."""
        logger.info("MemorySwarmNode %s starting.", self.node_id)

        self._install_signal_handlers()

        await self.publish_heartbeat()

        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.heartbeat_interval_seconds,
                )
            except asyncio.TimeoutError:
                await self.publish_heartbeat()
            except Exception as exc:
                self.last_error = str(exc)
                logger.exception("MemorySwarmNode heartbeat loop error: %s", exc)

        logger.info("MemorySwarmNode %s stopped.", self.node_id)

    async def stop(self) -> None:
        """Request graceful shutdown."""
        self._stop_event.set()

    def _install_signal_handlers(self) -> None:
        loop = asyncio.get_running_loop()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._stop_event.set)
            except NotImplementedError:
                # Windows/event-loop compatibility.
                pass


async def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s | %(levelname)s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
    )

    interval = float(os.environ.get("MEMORY_HEARTBEAT_INTERVAL_SECONDS", DEFAULT_HEARTBEAT_INTERVAL_SECONDS))
    node = MemorySwarmNode(heartbeat_interval_seconds=interval)
    await node.start()


if __name__ == "__main__":
    asyncio.run(main())