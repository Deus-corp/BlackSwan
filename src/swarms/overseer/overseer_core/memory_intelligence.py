"""Memory intelligence interpretation for Overseer.

This module reads memory swarm heartbeat metrics and converts them into a compact
operational assessment for Overseer. It does not perform actions by itself.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class MemoryIntelligenceStatus(str, Enum):
    """High-level memory intelligence state."""

    HEALTHY = "healthy"
    VALUABLE_ACTIVITY = "valuable_activity"
    NEEDS_REVIEW = "needs_review"
    DANGER_DETECTED = "danger_detected"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class MemoryIntelligenceAssessment:
    """Compact Overseer assessment of memory swarm intelligence state."""

    status: MemoryIntelligenceStatus
    total_records: int = 0
    recognized_records: int = 0
    gold_candidates: int = 0
    review_candidates: int = 0
    alert_candidates: int = 0
    dedupe_candidates: int = 0
    degraded: bool = False
    reason: str = "ok"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

def _extract_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract heartbeat metrics from canonical or wrapped heartbeat payloads."""
    candidates: list[Any] = [
        payload.get("metrics"),
        payload.get("payload", {}).get("metrics") if isinstance(payload.get("payload"), dict) else None,
        payload.get("data", {}).get("metrics") if isinstance(payload.get("data"), dict) else None,
        payload.get("record", {}).get("metrics") if isinstance(payload.get("record"), dict) else None,
        payload.get("custom_payload", {}).get("metrics") if isinstance(payload.get("custom_payload"), dict) else None,
    ]

    for candidate in candidates:
        if isinstance(candidate, dict):
            return candidate

    # Some normalized heartbeats may flatten metrics onto top-level keys.
    flattened_keys = {
        "memory_summary",
        "total_records",
        "records_recognized",
        "gold_candidates",
        "review_candidates",
        "alert_candidates",
        "dedupe_candidates",
    }
    if any(key in payload for key in flattened_keys):
        return payload

    return {}

def assess_memory_heartbeat(payload: dict[str, Any]) -> MemoryIntelligenceAssessment:
    """Assess one memory heartbeat payload."""
    if not isinstance(payload, dict):
        return MemoryIntelligenceAssessment(
            status=MemoryIntelligenceStatus.UNKNOWN,
            degraded=True,
            reason="invalid_payload",
        )

    metrics = _extract_metrics(payload)

    summary = metrics.get("memory_summary", {})
    if not isinstance(summary, dict):
        summary = {}

    total_records = _safe_int(summary.get("total_records", metrics.get("total_records", 0)))
    recognized_records = _safe_int(summary.get("recognized_records", metrics.get("records_recognized", 0)))
    gold_candidates = _safe_int(summary.get("gold_candidates", metrics.get("gold_candidates", 0)))
    review_candidates = _safe_int(summary.get("review_candidates", metrics.get("review_candidates", 0)))
    alert_candidates = _safe_int(summary.get("alert_candidates", metrics.get("alert_candidates", 0)))
    dedupe_candidates = _safe_int(summary.get("dedupe_candidates", metrics.get("dedupe_candidates", 0)))

    degraded = bool(summary.get("degraded", False)) or str(payload.get("status", "")).lower() == "degraded"
    reason = str(summary.get("reason") or metrics.get("last_error") or "ok")

    if degraded:
        status = MemoryIntelligenceStatus.DEGRADED
    elif alert_candidates > 0:
        status = MemoryIntelligenceStatus.DANGER_DETECTED
        reason = "memory_alert_candidates_detected"
    elif review_candidates > 0:
        status = MemoryIntelligenceStatus.NEEDS_REVIEW
        reason = "memory_review_candidates_detected"
    elif gold_candidates > 0:
        status = MemoryIntelligenceStatus.VALUABLE_ACTIVITY
        reason = "memory_gold_candidates_detected"
    elif total_records > 0:
        status = MemoryIntelligenceStatus.HEALTHY
    else:
        status = MemoryIntelligenceStatus.UNKNOWN
        reason = "no_memory_records"

    return MemoryIntelligenceAssessment(
        status=status,
        total_records=total_records,
        recognized_records=recognized_records,
        gold_candidates=gold_candidates,
        review_candidates=review_candidates,
        alert_candidates=alert_candidates,
        dedupe_candidates=dedupe_candidates,
        degraded=degraded,
        reason=reason,
    )


def aggregate_memory_assessments(
    assessments: list[MemoryIntelligenceAssessment],
) -> MemoryIntelligenceAssessment:
    """Aggregate multiple memory-node assessments into one Overseer view."""
    if not assessments:
        return MemoryIntelligenceAssessment(
            status=MemoryIntelligenceStatus.UNKNOWN,
            degraded=True,
            reason="no_memory_heartbeats",
        )

    total_records = sum(item.total_records for item in assessments)
    recognized_records = sum(item.recognized_records for item in assessments)
    gold_candidates = sum(item.gold_candidates for item in assessments)
    review_candidates = sum(item.review_candidates for item in assessments)
    alert_candidates = sum(item.alert_candidates for item in assessments)
    dedupe_candidates = sum(item.dedupe_candidates for item in assessments)

    degraded = any(item.degraded for item in assessments)

    if degraded:
        status = MemoryIntelligenceStatus.DEGRADED
        reason = "one_or_more_memory_nodes_degraded"
    elif alert_candidates > 0:
        status = MemoryIntelligenceStatus.DANGER_DETECTED
        reason = "memory_alert_candidates_detected"
    elif review_candidates > 0:
        status = MemoryIntelligenceStatus.NEEDS_REVIEW
        reason = "memory_review_candidates_detected"
    elif gold_candidates > 0:
        status = MemoryIntelligenceStatus.VALUABLE_ACTIVITY
        reason = "memory_gold_candidates_detected"
    else:
        status = MemoryIntelligenceStatus.HEALTHY
        reason = "ok"

    return MemoryIntelligenceAssessment(
        status=status,
        total_records=total_records,
        recognized_records=recognized_records,
        gold_candidates=gold_candidates,
        review_candidates=review_candidates,
        alert_candidates=alert_candidates,
        dedupe_candidates=dedupe_candidates,
        degraded=degraded,
        reason=reason,
    )


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default