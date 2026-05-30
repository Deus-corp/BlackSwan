"""Security validation for directive/evidence/memory runtime records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


SAFE_DIRECTIVE_ACTIONS = {
    "OBSERVE",
    "REDUCE_RISK",
    "SET_DRY_RUN",
    "PROMOTE_GOLD_CANDIDATES",
}

ALLOWED_TARGET_SWARMS = {
    "trade",
    "memory",
    "simulation",
    "security",
    "explorer",
    "overseer",
    "*",
}

ALLOWED_RESULT_STATUSES = {
    "applied",
    "rejected",
    "ignored",
    "expired",
    "failed",
}

ALLOWED_RECORD_STATUSES = {
    "passed",
    "failed",
    "partial",
    "unknown",
    "issued",
    "applied",
    "rejected",
    "ignored",
    "expired",
}


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Result of a runtime record validation."""

    valid: bool
    severity: str = "info"
    reasons: list[str] = field(default_factory=list)
    record_type: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "severity": self.severity,
            "reasons": list(self.reasons),
            "record_type": self.record_type,
        }


def validate_runtime_record(record: Mapping[str, Any]) -> ValidationResult:
    """Validate one directive/evidence/memory runtime record."""
    if not isinstance(record, Mapping):
        return ValidationResult(
            valid=False,
            severity="critical",
            reasons=["record_not_mapping"],
            record_type="unknown",
        )

    record_type = str(record.get("type") or "").strip()

    if record_type == "swarm_directive":
        return validate_swarm_directive(record)

    if record_type == "swarm_directive_result":
        return validate_swarm_directive_result(record)

    if record_type == "evidence_record":
        return validate_evidence_record(record)

    if record_type == "memory_record" and str(record.get("kind") or "") == "runtime_evidence":
        return validate_runtime_evidence_memory_record(record)

    return ValidationResult(
        valid=False,
        severity="warning",
        reasons=["unsupported_record_type"],
        record_type=record_type or "unknown",
    )


def validate_swarm_directive(record: Mapping[str, Any]) -> ValidationResult:
    reasons: list[str] = []

    directive_id = str(record.get("directive_id") or "").strip()
    action = str(record.get("action") or "").strip().upper()
    source = str(record.get("source") or "").strip()
    target = str(record.get("target") or record.get("target_swarm") or "").strip()
    target_type = str(record.get("target_type") or "").strip().lower()

    if not directive_id:
        reasons.append("missing_directive_id")
    if not source:
        reasons.append("missing_source")
    if action not in SAFE_DIRECTIVE_ACTIONS:
        reasons.append("unsafe_or_unknown_action")
    if target and target not in ALLOWED_TARGET_SWARMS:
        reasons.append("unsupported_target")
    if target_type and target_type not in {"swarm", "node", "global"}:
        reasons.append("unsupported_target_type")

    payload = record.get("payload")
    if not isinstance(payload, Mapping):
        payload = {}

    if bool(payload.get("execution_enabled")) is True:
        reasons.append("execution_enabled_not_allowed")

    if action in {"REDUCE_RISK", "SET_DRY_RUN"}:
        if bool(payload.get("execution_enabled")) is True:
            reasons.append("safe_action_attempts_live_execution")

    valid = not reasons
    return ValidationResult(
        valid=valid,
        severity="info" if valid else "critical",
        reasons=reasons,
        record_type="swarm_directive",
    )


def validate_swarm_directive_result(record: Mapping[str, Any]) -> ValidationResult:
    reasons: list[str] = []

    directive_id = str(record.get("directive_id") or "").strip()
    status = str(record.get("status") or "").strip().lower()
    source = str(record.get("source") or record.get("node_id") or "").strip()
    swarm = str(record.get("swarm") or "").strip()

    if not directive_id:
        reasons.append("missing_directive_id")
    if status not in ALLOWED_RESULT_STATUSES:
        reasons.append("invalid_result_status")
    if not source:
        reasons.append("missing_source")
    if swarm and swarm not in ALLOWED_TARGET_SWARMS:
        reasons.append("unsupported_swarm")

    valid = not reasons
    return ValidationResult(
        valid=valid,
        severity="info" if valid else "warning",
        reasons=reasons,
        record_type="swarm_directive_result",
    )


def validate_evidence_record(record: Mapping[str, Any]) -> ValidationResult:
    reasons: list[str] = []

    evidence_id = str(record.get("evidence_id") or "").strip()
    subject = str(record.get("subject") or "").strip()
    status = str(record.get("status") or "").strip().lower()
    checks = record.get("checks")

    if not evidence_id:
        reasons.append("missing_evidence_id")
    if not subject:
        reasons.append("missing_subject")
    if status not in {"passed", "failed", "partial", "unknown"}:
        reasons.append("invalid_evidence_status")
    if checks is not None and not isinstance(checks, list):
        reasons.append("checks_not_list")

    if isinstance(checks, list):
        for item in checks:
            if not isinstance(item, Mapping):
                reasons.append("invalid_check_item")
                break
            check_status = str(item.get("status") or "").strip().lower()
            if check_status not in {"passed", "failed", "partial", "unknown"}:
                reasons.append("invalid_check_status")
                break

    valid = not reasons
    return ValidationResult(
        valid=valid,
        severity="info" if valid else "warning",
        reasons=reasons,
        record_type="evidence_record",
    )


def validate_runtime_evidence_memory_record(record: Mapping[str, Any]) -> ValidationResult:
    reasons: list[str] = []

    memory_id = str(record.get("memory_id") or record.get("id") or "").strip()
    status = str(record.get("status") or "").strip().lower()
    payload = record.get("payload")

    if not memory_id:
        reasons.append("missing_memory_id")
    if status not in {"passed", "failed", "partial", "unknown"}:
        reasons.append("invalid_memory_status")
    if not isinstance(payload, Mapping):
        reasons.append("missing_payload")
        payload = {}

    evidence_id = str(payload.get("evidence_id") or "").strip()
    if not evidence_id:
        reasons.append("missing_evidence_id_link")

    checks = payload.get("checks")
    if checks is not None and not isinstance(checks, list):
        reasons.append("checks_not_list")

    valid = not reasons
    return ValidationResult(
        valid=valid,
        severity="info" if valid else "warning",
        reasons=reasons,
        record_type="memory_record",
    )


__all__ = [
    "ALLOWED_RECORD_STATUSES",
    "ALLOWED_RESULT_STATUSES",
    "ALLOWED_TARGET_SWARMS",
    "SAFE_DIRECTIVE_ACTIONS",
    "ValidationResult",
    "validate_evidence_record",
    "validate_runtime_evidence_memory_record",
    "validate_runtime_record",
    "validate_swarm_directive",
    "validate_swarm_directive_result",
]