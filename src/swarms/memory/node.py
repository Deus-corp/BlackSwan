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
from pathlib import Path
import argparse

from src.core.crdt_adapter import CRDTAdapter
from src.memory.local_memory import LocalMemoryAPI, MemoryRecord
from src.swarms.memory.heartbeat import build_memory_heartbeat
from src.memory.quarantine import QuarantineBuffer, ReputationManagerProtocol
from src.swarms.memory.shared_bridge import SharedMemoryBridge
from src.memory.recognition import MemoryRecognizer
from src.memory.recognition_policy import MemoryRecognitionPolicy
from src.memory.gold_filter import select_gold_memory_samples
from src.memory.exporter import save_jsonl
from src.memory.summary import build_memory_summary
from swarm_config import config

from src.memory.resilience import (
    MemoryAvailability,
    MemoryHealth,
    assess_memory_resilience,
)

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
        self.recognizer = MemoryRecognizer()
        self.recognition_policy = MemoryRecognitionPolicy()
        include_swarm_events = (
            os.environ.get("MEMORY_INGEST_SWARM_EVENTS", "false").lower()
            in {"1", "true", "yes", "on"}
        )
        self.shared_bridge = SharedMemoryBridge(include_swarm_events=include_swarm_events)
        self.heartbeats_published = 0
        self.records_ingested = 0
        self.records_rejected = 0
        self.records_recognized = 0
        self.recognition_counts: dict[str, int] = {}
        self.recognition_action_counts: dict[str, int] = {}
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

        total_records = int(stats_data.get("total_records", 0))
        shared_seen_records = int(bridge_stats.get("seen_records", 0))
        shared_scanned_records = int(bridge_stats.get("scanned_records", 0))
        shared_accepted_records = int(bridge_stats.get("accepted_records", 0))
        shared_rejected_records = int(bridge_stats.get("rejected_records", 0))
        shared_skipped_records = int(bridge_stats.get("skipped_records", 0))

        try:
            recent_records = await self.memory.recent(limit=200)
        except Exception as exc:
            logger.debug("[%s] Failed to load recent records for memory summary: %s", self.node_id, exc)
            recent_records = []

        gold_samples = select_gold_memory_samples(recent_records)
        memory_summary = build_memory_summary(
            recent_records,
            total_records=total_records,
            recognition_counts=dict(self.recognition_counts),
            recognition_action_counts=dict(self.recognition_action_counts),
            degraded=bool(self.last_error),
            reason=self.last_error or "ok",
        )

        memory_health = MemoryHealth(
            local=MemoryAvailability.AVAILABLE,
            own=MemoryAvailability.AVAILABLE,
            shared=MemoryAvailability.AVAILABLE if not self.last_error else MemoryAvailability.DEGRADED,
            global_memory=MemoryAvailability.AVAILABLE,
            memory_swarm_seen=True,
            crdt_available=not bool(self.last_error),
            last_error=self.last_error,
        )

        memory_resilience = assess_memory_resilience(
            memory_health,
            total_records=total_records,
            shared_seen_records=shared_seen_records,
            shared_accepted_records=shared_accepted_records,
            shared_rejected_records=shared_rejected_records,
            shared_skipped_records=shared_skipped_records,
        )

        payload = build_memory_heartbeat(
            self.node_id,
            metrics={
                "heartbeats_published": self.heartbeats_published,
                "records_ingested": self.records_ingested,
                "records_recognized": self.records_recognized,
                "recognition_counts": dict(self.recognition_counts),
                "recognition_action_counts": dict(self.recognition_action_counts),
                "records_rejected": self.records_rejected,
                "total_records": total_records,
                "by_scope": dict(stats_data.get("by_scope", {})),
                "by_kind": dict(stats_data.get("by_kind", {})),
                "verified_records": int(stats_data.get("verified_records", 0)),
                "expired_records": int(stats_data.get("expired_records", 0)),
                "episodic_records": int(details.get("episodic_count", 0)),
                "semantic_records": int(details.get("semantic_count", 0)),
                "policy_records": int(details.get("policy_count", 0)),
                "snapshot_count": int(details.get("snapshot_count", 0)),
                "shared_seen_records": shared_seen_records,
                "shared_scanned_records": shared_scanned_records,
                "shared_accepted_records": shared_accepted_records,
                "shared_rejected_records": shared_rejected_records,
                "shared_skipped_records": shared_skipped_records,
                "memory_summary": memory_summary.to_dict(),
                "memory_resilience": memory_resilience.to_dict(),
                "resilience_status": memory_resilience.status.value,
                "resilience_degraded": memory_resilience.degraded,
                "fallback_active": memory_resilience.fallback_active,
                "shared_bridge_lagging": memory_resilience.shared_bridge_lagging,
                "recovery_needed": memory_resilience.recovery_needed,
                "review_candidates": memory_summary.review_candidates,
                "alert_candidates": memory_summary.alert_candidates,
                "dedupe_candidates": memory_summary.dedupe_candidates,
                "quarantine_candidates": memory_summary.quarantine_candidates,
                "gold_candidates": memory_summary.gold_candidates,
                "pending_consolidations": 0,
                "runtime_evidence_records": memory_summary.runtime_evidence_records,
                "runtime_evidence_gold_candidates": memory_summary.runtime_evidence_gold_candidates,
                "runtime_evidence_review_candidates": memory_summary.runtime_evidence_review_candidates,
                "runtime_evidence_alert_candidates": memory_summary.runtime_evidence_alert_candidates,
            },
            details={
                "last_error": self.last_error,
                "crdt_db_path": str(config.crdt_db_path),
                "memory_backend": str(stats_data.get("backend", "local")),
                "node_id": self.node_id,
                "memory_health": memory_health.to_dict(),
                "memory_resilience": memory_resilience.to_dict(),
                "gold_sample_candidates": len(gold_samples),
            },
            status="running" if not self.last_error else "degraded",
        )

        await self.crdt.add_genome(payload)
        self.heartbeats_published += 1
        logger.info(
            "[%s] Published memory swarm heartbeat count=%d total_records=%s "
            "shared_seen=%s shared_accepted=%s shared_rejected=%s shared_skipped=%s "
            "recognized=%s recognition_counts=%s recognition_action_counts=%s "
            "gold=%s review=%s alert=%s dedupe=%s "
            "resilience=%s fallback=%s bridge_lagging=%s recovery_needed=%s",
            self.node_id,
            self.heartbeats_published,
            total_records,
            shared_seen_records,
            shared_accepted_records,
            shared_rejected_records,
            shared_skipped_records,
            self.records_recognized,
            dict(self.recognition_counts),
            dict(self.recognition_action_counts),
            memory_summary.gold_candidates,
            memory_summary.review_candidates,
            memory_summary.alert_candidates,
            memory_summary.dedupe_candidates,
            memory_resilience.status.value,
            memory_resilience.fallback_active,
            memory_resilience.shared_bridge_lagging,
            memory_resilience.recovery_needed,
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
    
    async def export_gold_samples(self, output_path: str | Path) -> Path:
        """Export current gold candidate memory samples to JSONL.

        This is an explicit/manual operation. It is intentionally not called
        automatically from the heartbeat loop.
        """
        recent_records = await self.memory.recent(limit=1000)
        gold_samples = select_gold_memory_samples(recent_records)
        return save_jsonl(gold_samples, output_path)
    
    async def _recent_records_for_recognition(self, limit: int = 50) -> list[Any]:
        """Return recent records used as recognition context."""
        try:
            return await self.memory.recent(limit=limit)
        except Exception as exc:
            logger.debug("[%s] Failed to load recognition context: %s", self.node_id, exc)
            return []

    async def _annotate_with_recognition(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Add deterministic recognition metadata to an incoming record."""
        record = dict(raw)

        existing = await self._recent_records_for_recognition()
        result = self.recognizer.recognize(record, existing)
        decision = self.recognition_policy.decide(result)

        payload = record.get("payload", {})
        if not isinstance(payload, dict):
            payload = {"value": payload}

        recognition_data = {
            "label": result.label.value,
            "confidence": result.confidence,
            "novelty_score": result.novelty_score,
            "familiarity_score": result.familiarity_score,
            "risk_score": result.risk_score,
            "value_score": result.value_score,
            "duplicate_of": result.duplicate_of,
            "fingerprint": result.fingerprint,
        }

        recognition_policy_data = decision.to_dict()
        payload["recognition"] = recognition_data
        payload["recognition_policy"] = recognition_policy_data

        tags = payload.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        if not isinstance(tags, list):
            tags = []

        tags = [str(tag) for tag in tags if str(tag).strip()]
        tags.append(f"recognition:{result.label.value}")

        if result.risk_score >= 0.75:
            tags.append("risk:high")
        elif result.risk_score >= 0.5:
            tags.append("risk:medium")

        if result.value_score >= 0.75:
            tags.append("value:high")
        elif result.value_score >= 0.5:
            tags.append("value:medium")

        for label in decision.labels:
            tags.append(f"policy:{label}")

        for action in decision.actions:
            tags.append(f"action:{action.value}")

        payload["tags"] = sorted(set(tags))
        record["payload"] = payload

        source = record.get("source", {})
        if not isinstance(source, dict):
            source = {}
        source["recognition_label"] = result.label.value
        source["recognition_confidence"] = result.confidence
        source["recognition_policy_severity"] = decision.severity
        source["recognition_policy_reason"] = decision.reason
        record["source"] = source

        self.records_recognized += 1
        self.recognition_counts[result.label.value] = self.recognition_counts.get(result.label.value, 0) + 1
        for action in decision.actions:
            self.recognition_action_counts[action.value] = (
                self.recognition_action_counts.get(action.value, 0) + 1
            )

        return record
    
    async def ingest_record(self, raw: dict[str, Any]) -> bool:
        """Recognize, validate, and ingest an external memory record."""
        try:
            annotated = await self._annotate_with_recognition(raw)
        except Exception as exc:
            logger.warning("[%s] Recognition failed; ingesting raw record: %s", self.node_id, exc)
            annotated = raw

        accepted = await self.quarantine.process(annotated)

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

def build_parser() -> argparse.ArgumentParser:
    """Build MemorySwarmNode CLI parser."""
    parser = argparse.ArgumentParser(description="BlackSwan memory swarm node")
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="Run memory swarm heartbeat loop.")
    run.add_argument(
        "--heartbeat-interval",
        type=float,
        default=float(os.environ.get("MEMORY_HEARTBEAT_INTERVAL_SECONDS", DEFAULT_HEARTBEAT_INTERVAL_SECONDS)),
        help="Heartbeat interval in seconds.",
    )

    export_gold = sub.add_parser("export-gold", help="Export current gold candidate samples to JSONL.")
    export_gold.add_argument(
        "--output",
        required=True,
        help="Output JSONL file path.",
    )
    export_gold.add_argument(
        "--heartbeat-interval",
        type=float,
        default=float(os.environ.get("MEMORY_HEARTBEAT_INTERVAL_SECONDS", DEFAULT_HEARTBEAT_INTERVAL_SECONDS)),
        help="Heartbeat interval used only for node initialization.",
    )
    export_gold.add_argument(
        "--no-scan-shared",
        action="store_true",
        help="Export only current local memory without scanning shared CRDT records first.",
    )
    export_gold.add_argument(
        "--crdt-db-path",
        default=os.environ.get("CRDT_DB_PATH", str(config.crdt_db_path)),
        help="CRDT SQLite database path to scan before export.",
    )

    return parser


async def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s | %(levelname)s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
    )

    parser = build_parser()
    args = parser.parse_args()

    command = args.command or "run"
    interval = float(getattr(args, "heartbeat_interval", DEFAULT_HEARTBEAT_INTERVAL_SECONDS))

    node = MemorySwarmNode(heartbeat_interval_seconds=interval)

    if command == "export-gold":
        node.crdt = CRDTAdapter(
            node_id=node.node_id,
            db_path=str(args.crdt_db_path),
        )

        if not args.no_scan_shared:
            node.ingest_records_since_start = False
            scan_result = await node.scan_shared_memory()
            logger.info("Scanned shared memory before gold export: %s", scan_result)

        output_path = await node.export_gold_samples(Path(args.output))
        logger.info("Exported memory gold samples to %s", output_path)
        return

    await node.start()


if __name__ == "__main__":
    asyncio.run(main())