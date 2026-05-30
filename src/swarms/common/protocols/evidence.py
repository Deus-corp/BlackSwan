"""Evidence protocol for swarm/runtime validation records.

Evidence records capture verifiable checks behind briefs, directives, results,
tests, runtime smoke checks, and safety gates.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping


class EvidenceStatus(str, Enum):
    """Overall evidence status."""

    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class EvidenceSeverity(str, Enum):
    """Evidence severity."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class EvidenceCheck:
    """Single evidence check item."""

    name: str
    status: str
    value: Any = None
    detail: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _clean_required(self.name, "name"))
        object.__setattr__(self, "status", normalize_status(self.status))
        object.__setattr__(self, "detail", str(self.detail or "").strip())
        object.__setattr__(self, "payload", _safe_dict(self.payload))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "value": self.value,
            "detail": self.detail,
            "payload": dict(self.payload),
        }


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    """Evidence record for a runtime, test, event, directive, or decision."""

    evidence_id: str
    subject: str
    source: str
    status: str
    confidence: float = 0.0
    severity: str = EvidenceSeverity.INFO.value
    checks: list[dict[str, Any]] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", _clean_required(self.evidence_id, "evidence_id"))
        object.__setattr__(self, "subject", _clean_required(self.subject, "subject"))
        object.__setattr__(self, "source", _clean_required(self.source, "source"))
        object.__setattr__(self, "status", normalize_status(self.status))
        object.__setattr__(self, "confidence", _clamp_confidence(self.confidence))
        object.__setattr__(self, "severity", normalize_severity(self.severity))
        object.__setattr__(self, "checks", _safe_checks(self.checks))
        object.__setattr__(self, "payload", _safe_dict(self.payload))
        object.__setattr__(self, "created_at", _safe_float(self.created_at, time.time()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "evidence_record",
            "evidence_id": self.evidence_id,
            "subject": self.subject,
            "source": self.source,
            "status": self.status,
            "confidence": self.confidence,
            "severity": self.severity,
            "checks": [dict(item) for item in self.checks],
            "payload": dict(self.payload),
            "created_at": self.created_at,
        }


def build_evidence_check(
    *,
    name: str,
    status: str,
    value: Any = None,
    detail: str = "",
    payload: Mapping[str, Any] | None = None,
) -> EvidenceCheck:
    """Build a normalized evidence check."""
    return EvidenceCheck(
        name=name,
        status=status,
        value=value,
        detail=detail,
        payload=dict(payload or {}),
    )


def build_evidence_record(
    *,
    subject: str,
    source: str,
    status: str = EvidenceStatus.UNKNOWN.value,
    confidence: float = 0.0,
    severity: str = EvidenceSeverity.INFO.value,
    checks: Iterable[EvidenceCheck | Mapping[str, Any]] | None = None,
    payload: Mapping[str, Any] | None = None,
    evidence_id: str | None = None,
    created_at: float | None = None,
) -> EvidenceRecord:
    """Build a normalized evidence record."""
    return EvidenceRecord(
        evidence_id=str(evidence_id or uuid.uuid4().hex),
        subject=subject,
        source=source,
        status=status,
        confidence=confidence,
        severity=severity,
        checks=[
            item.to_dict() if isinstance(item, EvidenceCheck) else dict(item)
            for item in checks or []
            if isinstance(item, (EvidenceCheck, Mapping))
        ],
        payload=dict(payload or {}),
        created_at=float(created_at if created_at is not None else time.time()),
    )


def normalize_evidence_record(data: Mapping[str, Any] | EvidenceRecord) -> EvidenceRecord:
    """Normalize a raw mapping or EvidenceRecord into an EvidenceRecord."""
    if isinstance(data, EvidenceRecord):
        return data

    if not isinstance(data, Mapping):
        raise TypeError(f"EvidenceRecord data must be a mapping, got {type(data).__name__}")

    return build_evidence_record(
        evidence_id=str(data.get("evidence_id") or data.get("id") or uuid.uuid4().hex),
        subject=str(data.get("subject") or ""),
        source=str(data.get("source") or "unknown"),
        status=str(data.get("status") or EvidenceStatus.UNKNOWN.value),
        confidence=_safe_float(data.get("confidence"), 0.0),
        severity=str(data.get("severity") or EvidenceSeverity.INFO.value),
        checks=_safe_checks(data.get("checks") or []),
        payload=_safe_dict(data.get("payload") or {}),
        created_at=_safe_float(data.get("created_at") or data.get("timestamp"), time.time()),
    )


def evidence_to_record(evidence: Mapping[str, Any] | EvidenceRecord) -> dict[str, Any]:
    """Convert evidence into a CRDT/event-friendly record."""
    return normalize_evidence_record(evidence).to_dict()


def normalize_status(value: Any) -> str:
    raw = str(value or EvidenceStatus.UNKNOWN.value).strip().lower()
    allowed = {item.value for item in EvidenceStatus}
    return raw if raw in allowed else EvidenceStatus.UNKNOWN.value


def normalize_severity(value: Any) -> str:
    raw = str(value or EvidenceSeverity.INFO.value).strip().lower()
    allowed = {item.value for item in EvidenceSeverity}
    return raw if raw in allowed else EvidenceSeverity.INFO.value


def _safe_checks(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, Mapping)):
        return []

    checks: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, EvidenceCheck):
            checks.append(item.to_dict())
        elif isinstance(item, Mapping):
            check = {
                "name": str(item.get("name") or "").strip(),
                "status": normalize_status(item.get("status")),
                "value": item.get("value"),
                "detail": str(item.get("detail") or "").strip(),
                "payload": _safe_dict(item.get("payload") or {}),
            }
            if check["name"]:
                checks.append(check)
    return checks


def _clean_required(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must be a non-empty string")
    return text


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp_confidence(value: Any) -> float:
    number = _safe_float(value, 0.0)
    return max(0.0, min(1.0, number))


__all__ = [
    "EvidenceCheck",
    "EvidenceRecord",
    "EvidenceSeverity",
    "EvidenceStatus",
    "build_evidence_check",
    "build_evidence_record",
    "evidence_to_record",
    "normalize_evidence_record",
    "normalize_severity",
    "normalize_status",
]