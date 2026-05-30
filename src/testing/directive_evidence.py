"""Build evidence records from runtime directive lifecycle checks."""

from __future__ import annotations

from typing import Any, Mapping

from src.swarms.common.protocols.evidence import (
    EvidenceStatus,
    build_evidence_check,
    build_evidence_record,
    evidence_to_record,
)


def build_directive_runtime_evidence(
    *,
    directive_id: str,
    crdt_state: Mapping[str, Any],
    source: str = "runtime-check",
) -> dict[str, Any]:
    """Build evidence from CRDT directive/result records."""
    directive = _find_record(
        crdt_state,
        record_type="swarm_directive",
        directive_id=directive_id,
    )
    result = _find_record(
        crdt_state,
        record_type="swarm_directive_result",
        directive_id=directive_id,
    )

    checks = [
        build_evidence_check(
            name="directive_seeded",
            status=EvidenceStatus.PASSED.value if directive else EvidenceStatus.FAILED.value,
            value=bool(directive),
            detail="swarm_directive record exists in CRDT.",
            payload=_compact_directive(directive),
        ),
        build_evidence_check(
            name="directive_result_published",
            status=EvidenceStatus.PASSED.value if result else EvidenceStatus.FAILED.value,
            value=bool(result),
            detail="swarm_directive_result record exists in CRDT.",
            payload=_compact_result(result),
        ),
        build_evidence_check(
            name="directive_applied",
            status=EvidenceStatus.PASSED.value
            if result and str(result.get("status") or "").lower() == "applied"
            else EvidenceStatus.FAILED.value,
            value=str(result.get("status") or "") if result else None,
            detail="Directive result status is applied.",
            payload=_compact_result(result),
        ),
    ]

    passed = all(check.status == EvidenceStatus.PASSED.value for check in checks)
    status = EvidenceStatus.PASSED.value if passed else EvidenceStatus.FAILED.value

    evidence = build_evidence_record(
        subject="runtime_directive_seed_check",
        source=source,
        status=status,
        confidence=1.0 if passed else 0.0,
        checks=checks,
        payload={
            "directive_id": directive_id,
            "directive": _compact_directive(directive),
            "result": _compact_result(result),
        },
    )

    return evidence_to_record(evidence)


def _find_record(
    crdt_state: Mapping[str, Any],
    *,
    record_type: str,
    directive_id: str,
) -> dict[str, Any] | None:
    for value in crdt_state.values():
        if not isinstance(value, Mapping):
            continue
        if value.get("type") != record_type:
            continue
        if str(value.get("directive_id") or "") != directive_id:
            continue
        return dict(value)
    return None


def _compact_directive(record: Mapping[str, Any] | None) -> dict[str, Any]:
    if not record:
        return {}
    return {
        "directive_id": record.get("directive_id"),
        "action": record.get("action"),
        "source": record.get("source"),
        "target_type": record.get("target_type"),
        "target": record.get("target"),
        "status": record.get("status"),
    }


def _compact_result(record: Mapping[str, Any] | None) -> dict[str, Any]:
    if not record:
        return {}
    return {
        "directive_id": record.get("directive_id"),
        "status": record.get("status"),
        "source": record.get("source"),
        "swarm": record.get("swarm"),
        "node_id": record.get("node_id"),
        "message": record.get("message"),
    }


__all__ = ["build_directive_runtime_evidence"]