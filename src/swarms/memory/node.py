#!/usr/bin/env python3
"""Memory swarm node.

The memory swarm is responsible for memory-oriented autonomous functions:
episodic memory, semantic memory, retrieval, consolidation, and gold sample
export.

This node now owns a LocalMemoryAPI backend and publishes real memory health
metrics in canonical swarm heartbeats. It remains advisory-only in topology:
it observes, indexes, and reports memory state, but does not execute risky
actions without explicit future gates.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import uuid
import time
from typing import Any, Optional

from src.core.crdt_adapter import CRDTAdapter
from src.memory.local_memory import LocalMemoryAPI, MemoryRecord
from src.swarms.memory.heartbeat import build_memory_heartbeat
from src.memory.quarantine import QuarantineBuffer, ReputationManagerProtocol
from src.swarms.memory.shared_bridge import SharedMemoryBridge
from swarm_config import config

logger = logging.getLogger(__name__)

DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 30.0

class TrustAllReputation:
    """Development fallback reputation manager.

    Production deployments should inject a real ReputationManager.
    """

    def is_trusted(self, entity_id: str) -> bool:
        return bool(str(entity_id or "").strip())

class MemorySwarmNode:
    """Memory swarm node with CRDT heartbeat publishing and local memory stats."""

    def __init__(
        self,
        node_id: Optional[str] = None,
        heartbeat_interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
        reputation: ReputationManagerProtocol | None = None,
    ) -> None:
        if heartbeat_interval_seconds <= 0:
            raise ValueError("heartbeat_interval_seconds must be positive")

        self.node_id = node_id or os.environ.get("MEMORY_NODE_ID") or f"memory-{uuid.uuid4().hex[:8]}"
        self.heartbeat_interval_seconds = float(heartbeat_interval_seconds)
        self._stop_event = asyncio.Event()
        self.started_at = time.time()
        self.ingest_records_since_start = (
            os.environ.get("MEMORY_INGEST_RECORDS_SINCE_START", "true").lower()
            not in {"0", "false", "no", "off"}
        )

        self.crdt = CRDTAdapter(
            node_id=self.node_id,
            db_path=config.crdt_db_path,
        )
        self.memory = LocalMemoryAPI(node_id=self.node_id)
        self.reputation = reputation or TrustAllReputation()
        self.quarantine = QuarantineBuffer(self.memory, self.reputation)
        include_swarm_events = (
            os.environ.get("MEMORY_INGEST_SWARM_EVENTS", "false").lower()
            in {"1", "true", "yes", "on"}
        )
        self.shared_bridge = SharedMemoryBridge(include_swarm_events=include_swarm_events)
        self.heartbeats_published = 0
        self.records_ingested = 0
        self.records_rejected = 0
        self.last_error = ""

        logger.info(
            "MemorySwarmNode initialized node_id=%s heartbeat_interval=%.1fs",
            self.node_id,
            self.heartbeat_interval_seconds,
        )

    async def publish_heartbeat(self) -> None:
        """Publish canonical memory swarm heartbeat with local memory stats."""
        stats = await self.memory.stats()
        stats_data = stats.to_dict() if hasattr(stats, "to_dict") else dict(stats)

        details = dict(stats_data.get("details", {}))

        bridge = getattr(self, "shared_bridge", None)
        bridge_stats = bridge.stats() if bridge is not None else {}

        payload = build_memory_heartbeat(
            self.node_id,
            metrics={
                "heartbeats_published": self.heartbeats_published,
                "records_ingested": self.records_ingested,
                "records_rejected": self.records_rejected,
                "total_records": int(stats_data.get("total_records", 0)),
                "by_scope": dict(stats_data.get("by_scope", {})),
                "by_kind": dict(stats_data.get("by_kind", {})),
                "verified_records": int(stats_data.get("verified_records", 0)),
                "expired_records": int(stats_data.get("expired_records", 0)),
                "episodic_records": int(details.get("episodic_count", 0)),
                "semantic_records": int(details.get("semantic_count", 0)),
                "policy_records": int(details.get("policy_count", 0)),
                "snapshot_count": int(details.get("snapshot_count", 0)),
                "shared_seen_records": int(bridge_stats.get("seen_records", 0)),
                "shared_scanned_records": int(bridge_stats.get("scanned_records", 0)),
                "shared_accepted_records": int(bridge_stats.get("accepted_records", 0)),
                "shared_rejected_records": int(bridge_stats.get("rejected_records", 0)),
                "shared_skipped_records": int(bridge_stats.get("skipped_records", 0)),
                "pending_consolidations": 0,
            },
            details={
                "last_error": self.last_error,
                "crdt_db_path": str(config.crdt_db_path),
                "memory_backend": str(stats_data.get("backend", "local")),
                "node_id": self.node_id,
            },
            status="running" if not self.last_error else "degraded",
        )

        await self.crdt.add_genome(payload)
        self.heartbeats_published += 1
        logger.info(
            "[%s] Published memory swarm heartbeat count=%d total_records=%s "
            "shared_seen=%s shared_accepted=%s shared_rejected=%s shared_skipped=%s",
            self.node_id,
            self.heartbeats_published,
            stats_data.get("total_records", 0),
            bridge_stats.get("seen_records", 0),
            bridge_stats.get("accepted_records", 0),
            bridge_stats.get("rejected_records", 0),
            bridge_stats.get("skipped_records", 0),
        )

    async def remember_event(
        self,
        message: str,
        *,
        topic: str = "memory_swarm",
        scope: str = "own",
    ) -> str:
        """Store a simple own-memory event and return record id."""
        record = MemoryRecord(
            kind="event",
            scope=scope,
            topic=topic,
            payload={
                "message": message,
                "tags": ["memory", "event", topic],
            },
            source={
                "originNodeId": self.node_id,
                "swarm": "memory",
                "parents": [],
            },
            verified=True,
        )

        record_id = await self.memory.remember(record)
        self.records_ingested += 1
        return record_id
    
    async def ingest_record(self, raw: dict[str, Any]) -> bool:
        """Validate and ingest an external memory record through quarantine."""
        accepted = await self.quarantine.process(raw)

        if accepted:
            self.records_ingested += 1
            self.last_error = ""
        else:
            self.records_rejected += 1

        return accepted

    async def start(self) -> None:
        """Run heartbeat loop until stopped."""
        logger.info("MemorySwarmNode %s starting.", self.node_id)

        self._install_signal_handlers()

        await self.remember_event("memory swarm node started", topic="lifecycle")
        await self.scan_shared_memory()
        await self.publish_heartbeat()

        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.heartbeat_interval_seconds,
                )
            except asyncio.TimeoutError:
                await self.scan_shared_memory()
                await self.publish_heartbeat()
            except Exception as exc:
                self.last_error = str(exc)
                logger.exception("MemorySwarmNode heartbeat loop error: %s", exc)

        await self.remember_event("memory swarm node stopped", topic="lifecycle")
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
                pass

    async def scan_shared_memory(self) -> dict[str, int]:
        """Refresh CRDT state and ingest shared memory-compatible records."""
        refresh = getattr(self.crdt, "refresh_from_storage", None)
        if callable(refresh):
            refresh()

        min_timestamp = self.started_at if self.ingest_records_since_start else None
        return await self.shared_bridge.ingest_from_crdt(
            self.crdt,
            self,
            limit=100,
            min_timestamp=min_timestamp,
        )

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