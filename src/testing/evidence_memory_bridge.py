"""Bridge verified evidence records into memory records.

This controlled helper turns successful runtime evidence into explicit
memory_record payloads that the memory swarm can ingest through shared CRDT.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
import uuid
from typing import Any, Mapping

from swarm_config import config

from src.core.crdt_adapter import CRDTAdapter

logger = logging.getLogger(__name__)


def build_memory_record_from_evidence(
    evidence: Mapping[str, Any],
    *,
    source: str = "evidence-memory-bridge",
) -> dict[str, Any]:
    """Build a canonical memory_record from one evidence_record."""
    if not isinstance(evidence, Mapping):
        raise TypeError("evidence must be a mapping")

    if evidence.get("type") != "evidence_record":
        raise ValueError("evidence must have type='evidence_record'")

    evidence_id = str(evidence.get("evidence_id") or "").strip()
    if not evidence_id:
        raise ValueError("evidence_id must be present")

    status = str(evidence.get("status") or "unknown").strip().lower()
    subject = str(evidence.get("subject") or "unknown").strip() or "unknown"
    payload = evidence.get("payload") if isinstance(evidence.get("payload"), Mapping) else {}

    directive_id = str(payload.get("directive_id") or "").strip()
    memory_id = f"memory-evidence-{evidence_id}"

    return {
        "type": "memory_record",
        "memory_id": memory_id,
        "source": str(source or "evidence-memory-bridge"),
        "scope": "global",
        "kind": "runtime_evidence",
        "status": status,
        "subject": subject,
        "content": _build_content(
            subject=subject,
            status=status,
            directive_id=directive_id,
            evidence=evidence,
        ),
        "tags": _build_tags(subject=subject, status=status, directive_id=directive_id),
        "importance": _importance_for_status(status),
        "payload": {
            "evidence_id": evidence_id,
            "subject": subject,
            "status": status,
            "confidence": evidence.get("confidence"),
            "directive_id": directive_id or None,
            "checks": list(evidence.get("checks") or []),
            "evidence_payload": dict(payload),
        },
        "created_at": float(evidence.get("created_at") or time.time()),
    }


def build_memory_record_for_directive_evidence(
    *,
    directive_id: str,
    crdt_state: Mapping[str, Any],
    source: str = "evidence-memory-bridge",
) -> dict[str, Any]:
    """Find directive runtime evidence in CRDT state and build a memory record."""
    evidence = find_directive_evidence(
        directive_id=directive_id,
        crdt_state=crdt_state,
    )
    if evidence is None:
        raise ValueError(f"No evidence_record found for directive_id={directive_id!r}")

    return build_memory_record_from_evidence(evidence, source=source)


def find_directive_evidence(
    *,
    directive_id: str,
    crdt_state: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Find the latest evidence_record for a directive id."""
    matches: list[dict[str, Any]] = []

    for value in crdt_state.values():
        if not isinstance(value, Mapping):
            continue
        if value.get("type") != "evidence_record":
            continue

        payload = value.get("payload")
        if not isinstance(payload, Mapping):
            continue

        if str(payload.get("directive_id") or "") != directive_id:
            continue

        matches.append(dict(value))

    if not matches:
        return None

    return max(matches, key=lambda item: float(item.get("created_at") or 0.0))


async def publish_memory_record_for_directive_evidence(args: argparse.Namespace) -> dict[str, Any]:
    """Build and publish a memory_record from directive evidence in CRDT."""
    directive_id = str(args.directive_id or "").strip()
    if not directive_id:
        raise ValueError("directive_id must be a non-empty string")

    db_path = str(args.db_path or config.crdt_db_path)
    source = str(args.source or "evidence-memory-bridge")

    crdt = CRDTAdapter(node_id=source, db_path=db_path)

    try:
        refresh = getattr(crdt, "refresh_from_storage", None)
        if callable(refresh):
            refresh()

        state = getattr(crdt, "state", {}) or {}
        memory_record = build_memory_record_for_directive_evidence(
            directive_id=directive_id,
            crdt_state=state,
            source=source,
        )

        await crdt.add_genome(memory_record)
        return memory_record

    finally:
        close = getattr(crdt, "close", None)
        if callable(close):
            result = close()
            if asyncio.iscoroutine(result):
                await result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish memory_record from directive evidence.")
    parser.add_argument("--directive-id", required=True, help="Directive id with evidence_record.")
    parser.add_argument("--source", default="evidence-memory-bridge", help="Memory record source.")
    parser.add_argument("--db-path", default="", help="Override CRDT DB path.")
    return parser


async def async_main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s")

    memory_record = await publish_memory_record_for_directive_evidence(args)

    logger.info(
        "Published evidence memory record: memory_id=%s subject=%s status=%s directive_id=%s db=%s",
        memory_record.get("memory_id"),
        memory_record.get("subject"),
        memory_record.get("status"),
        args.directive_id,
        args.db_path or config.crdt_db_path,
    )


def main() -> None:
    asyncio.run(async_main())


def _build_content(
    *,
    subject: str,
    status: str,
    directive_id: str,
    evidence: Mapping[str, Any],
) -> str:
    confidence = evidence.get("confidence")
    checks = evidence.get("checks") if isinstance(evidence.get("checks"), list) else []
    passed = sum(1 for item in checks if isinstance(item, Mapping) and item.get("status") == "passed")
    total = len(checks)

    directive_part = f" directive_id={directive_id}" if directive_id else ""
    return (
        f"Runtime evidence '{subject}' completed with status={status}, "
        f"confidence={confidence}, checks={passed}/{total}.{directive_part}"
    )


def _build_tags(*, subject: str, status: str, directive_id: str) -> list[str]:
    tags = [
        "runtime_evidence",
        f"status:{status}",
        f"subject:{subject}",
    ]
    if directive_id:
        tags.append(f"directive:{directive_id}")
    return tags


def _importance_for_status(status: str) -> float:
    if status == "passed":
        return 0.85
    if status == "partial":
        return 0.65
    if status == "failed":
        return 0.75
    return 0.5


__all__ = [
    "build_memory_record_for_directive_evidence",
    "build_memory_record_from_evidence",
    "find_directive_evidence",
    "publish_memory_record_for_directive_evidence",
]


if __name__ == "__main__":
    main()