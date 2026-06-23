"""Shared memory bridge for ingesting CRDT-backed memory events.

The bridge scans CRDT state for memory-compatible records and routes them
through MemorySwarmNode.ingest_record(), preserving quarantine validation.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

from src.swarms.memory.ingestion import (
    build_memory_ingest_candidate,
    is_explorer_useful_evidence_record,
    memory_record_from_ingest_candidate,
)

logger = logging.getLogger(__name__)

MEMORY_COMPATIBLE_TYPES = {
    "memory_record",
    "memory_ingest_candidate",
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
                record_ts = self._extract_record_timestamp(payload)

                # Only filter records with a reliable timestamp. Explicit memory records
                # without timestamp are still allowed through quarantine.
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

        await self._ingest_evidence_records(crdt, node, limit=50, min_timestamp=min_timestamp)

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
            if is_explorer_useful_evidence_record(payload):
                candidate = build_memory_ingest_candidate(payload)
                record = memory_record_from_ingest_candidate(candidate)
                record["kind"] = "evidence"
                return record

            if payload.get("record_kind") == "runtime_evidence":
                record = cls._memory_record_from_payload(record_id, payload)
                record["kind"] = "evidence"
                return record

            record = cls._memory_record_from_payload(record_id, payload)
            record["kind"] = "evidence"
            return record

        if record_type == "memory_ingest_candidate":
            record = memory_record_from_ingest_candidate(payload)
            record["kind"] = "evidence"
            return record

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

    @classmethod
    def _extract_record_timestamp(cls, payload: dict[str, Any]) -> float:
        """Extract best-effort timestamp from CRDT memory payload."""
        candidates = [
            payload.get("timestamp"),
            payload.get("ts"),
            payload.get("created_at"),
        ]

        inner_payload = payload.get("payload")
        if isinstance(inner_payload, dict):
            candidates.extend(
                [
                    inner_payload.get("timestamp"),
                    inner_payload.get("ts"),
                    inner_payload.get("created_at"),
                ]
            )

        source = payload.get("source")
        if isinstance(source, dict):
            candidates.extend(
                [
                    source.get("timestamp"),
                    source.get("ts"),
                    source.get("created_at"),
                ]
            )

        for value in candidates:
            parsed = cls._safe_float(value, 0.0)
            if parsed > 0:
                return parsed

        return 0.0
    

    async def _ingest_evidence_records(
        self,
        crdt: Any,
        memory_node: Any,
        limit: int = 50,
        min_timestamp: float | None = None,
    ) -> int:
        """Scan CRDT for EvidenceRecord and convert to memory_record."""
        state = getattr(crdt, "state", {}) or {}
        if not isinstance(state, dict):
            return 0

        ingested = 0
        for record in list(state.values())[:limit]:
            if not isinstance(record, dict):
                continue
            if record.get("type") != "evidence_record":
                continue

            # Проверяем, не обработан ли уже этот evidence_id
            evidence_id = str(record.get("evidence_id") or "")
            if not evidence_id:
                continue

            # Простейшая защита от повторного ingestion (можно улучшить)
            # Полагаемся на dedup в memory

            subject = str(record.get("subject") or "")
            status = str(record.get("status") or "")
            confidence = float(record.get("confidence", 0.0))
            checks = record.get("checks", [])
            payload = record.get("payload", {})

            # Формируем memory_record
            memory_record = {
                "type": "memory_record",
                "record_kind": "runtime_evidence",
                "schema_version": "1.0",
                "gid": f"mem-ev-{evidence_id}",
                "timestamp": record.get("created_at", utc_ts()),
                "source_swarm": "security",  # или из provenance
                "source_agent": "evidence_bridge",
                "source_record_gid": evidence_id,
                "subject": {
                    "type": "runtime_evidence",
                    "evidence_id": evidence_id,
                    "subject": subject,
                },
                "evidence": {
                    "evidence_kind": "runtime_evidence",
                    "status": status,
                    "confidence": confidence,
                    "checks": checks,
                },
                "payload": dict(payload),
                "provenance": {
                    "source": "evidence_to_memory_bridge",
                    "evidence_id": evidence_id,
                    "external_write_performed": False,
                    "real_execution_enabled": False,
                },
            }

            # Передаём в MemorySwarmNode на ingestion
            await memory_node.ingest_record(memory_record)
            ingested += 1

        return ingested