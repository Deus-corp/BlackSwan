"""Shared memory bridge for ingesting CRDT-backed memory events.

The bridge scans CRDT state for memory-compatible records and routes them
through MemorySwarmNode.ingest_record(), preserving quarantine validation.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

logger = logging.getLogger(__name__)

MEMORY_COMPATIBLE_TYPES = {
    "memory_record",
    "swarm_event",
}


class SharedMemoryBridge:
    """Bridge from shared CRDT payloads to memory swarm ingestion."""

    def __init__(self, *, include_swarm_events: bool = False) -> None:
        self.include_swarm_events = bool(include_swarm_events)
        self.seen_ids: set[str] = set()
        self.scanned_records = 0
        self.accepted_records = 0
        self.rejected_records = 0
        self.skipped_records = 0

    async def ingest_from_crdt(
        self,
        crdt: Any,
        node: Any,
        *,
        limit: int = 100,
        min_timestamp: float | None = None,
    ) -> dict[str, int]:
        """Scan CRDT state and ingest memory-compatible records."""
        accepted = 0
        rejected = 0
        scanned = 0
        skipped = 0

        for record_id, payload in self._iter_crdt_payloads(crdt):
            if scanned >= limit:
                break

            memory_record = self._to_memory_record(
                record_id,
                payload,
                include_swarm_events=self.include_swarm_events,
            )
            if memory_record is None:
                skipped += 1
                continue

            if min_timestamp is not None:
                record_ts = self._safe_float(payload.get("timestamp", payload.get("ts", 0.0)))
                if record_ts > 0 and record_ts < min_timestamp:
                    skipped += 1
                    continue

            if record_id in self.seen_ids:
                continue

            scanned += 1
            self.seen_ids.add(record_id)

            ok = await node.ingest_record(memory_record)
            if ok:
                accepted += 1
            else:
                rejected += 1

        self.scanned_records += scanned
        self.accepted_records += accepted
        self.rejected_records += rejected
        self.skipped_records += skipped

        return {
            "scanned": scanned,
            "accepted": accepted,
            "rejected": rejected,
            "skipped": skipped,
            "seen": len(self.seen_ids),
        }

    def stats(self) -> dict[str, int]:
        """Return bridge counters."""
        return {
            "seen_records": len(self.seen_ids),
            "scanned_records": self.scanned_records,
            "accepted_records": self.accepted_records,
            "rejected_records": self.rejected_records,
            "skipped_records": self.skipped_records,
        }

    @staticmethod
    def _iter_crdt_payloads(crdt: Any) -> Iterable[tuple[str, dict[str, Any]]]:
        state = getattr(crdt, "state", None)

        if isinstance(state, dict):
            for key, value in state.items():
                if isinstance(value, dict):
                    yield str(key), value
            return

        records = getattr(crdt, "records", None)
        if isinstance(records, dict):
            for key, value in records.items():
                if isinstance(value, dict):
                    yield str(key), value

    @classmethod
    def _to_memory_record(
        cls,
        record_id: str,
        payload: dict[str, Any],
        *,
        include_swarm_events: bool = False,
    ) -> dict[str, Any] | None:
        record_type = str(payload.get("type", "") or "")

        if record_type == "memory_record":
            return cls._memory_record_from_payload(record_id, payload)

        if record_type == "swarm_event" and include_swarm_events:
            return cls._memory_record_from_event(record_id, payload)

        return None

    @staticmethod
    def _memory_record_from_payload(record_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        memory_payload = payload.get("payload", {})
        if not isinstance(memory_payload, dict):
            memory_payload = {"value": memory_payload}

        source = payload.get("source", {})
        if not isinstance(source, dict):
            source = {}

        return {
            "id": str(payload.get("id") or record_id),
            "kind": str(payload.get("kind") or "event"),
            "scope": str(payload.get("scope") or "shared"),
            "topic": payload.get("topic"),
            "payload": memory_payload,
            "source": {
                "originNodeId": source.get("originNodeId")
                or source.get("origin_node_id")
                or payload.get("node_id")
                or payload.get("origin_node_id")
                or "",
                "originPeerId": source.get("originPeerId", ""),
                "swarm": source.get("swarm") or payload.get("swarm", ""),
                "parents": source.get("parents", []),
            },
            "confidence": float(payload.get("confidence", 1.0)),
            "priority": int(payload.get("priority", 0)),
            "signature": payload.get("signature"),
            "verified": bool(payload.get("verified", False)),
        }

    @staticmethod
    def _memory_record_from_event(record_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        event_payload = payload.get("payload", {})
        if not isinstance(event_payload, dict):
            event_payload = {"value": event_payload}

        return {
            "id": str(payload.get("id") or record_id),
            "kind": "event",
            "scope": "shared",
            "topic": str(payload.get("event") or payload.get("topic") or "swarm_event"),
            "payload": {
                **event_payload,
                "event": payload.get("event", ""),
                "severity": payload.get("severity", "info"),
                "tags": ["swarm_event", str(payload.get("swarm", ""))],
            },
            "source": {
                "originNodeId": str(payload.get("node_id") or ""),
                "originPeerId": "",
                "swarm": str(payload.get("swarm") or ""),
                "parents": [],
            },
            "confidence": float(payload.get("confidence", 1.0)),
            "priority": 0,
            "verified": False,
        }
    
    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default