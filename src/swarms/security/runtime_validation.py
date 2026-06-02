"""Security swarm runtime validation helpers.

These helpers scan CRDT-visible runtime records and summarize validation results.
They are observational by default and do not block execution.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping

from src.security.directive_validation import (
    ValidationResult,
    validate_runtime_record,
)


VALIDATED_RECORD_TYPES = {
    "swarm_directive",
    "swarm_directive_result",
    "evidence_record",
    "memory_record",
    "replay_evidence_lifecycle_result",
    "replay_lifecycle_retry_proposal",
    "replay_lifecycle_retry_approval",
}


def validate_runtime_records(records: Iterable[Any]) -> list[dict[str, Any]]:
    """Validate runtime records and return serializable validation entries."""
    results: list[dict[str, Any]] = []

    for record in records or []:
        if not isinstance(record, Mapping):
            continue

        record_type = str(record.get("type") or "").strip()
        if record_type not in VALIDATED_RECORD_TYPES:
            continue

        if record_type == "memory_record" and str(record.get("kind") or "") != "runtime_evidence":
            continue

        if record_type == "replay_lifecycle_retry_proposal":
            result = validate_replay_lifecycle_retry_proposal(record)
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if record_type == "replay_evidence_lifecycle_result":
            result = validate_replay_evidence_lifecycle_result(record)
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if record_type == "replay_lifecycle_retry_approval":
            result = validate_replay_lifecycle_retry_approval(record)
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        validation = validate_runtime_record(record)
        results.append(
            {
                "type": "security_validation_result",
                "record_type": validation.record_type,
                "valid": validation.valid,
                "severity": validation.severity,
                "reasons": list(validation.reasons),
                "record_id": _record_id(record),
                "directive_id": _directive_id(record),
                "source": record.get("source") or record.get("node_id"),
            }
        )

    return results


def summarize_runtime_validations(validations: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarize security validation results."""
    validation_list = [dict(item) for item in validations or [] if isinstance(item, Mapping)]

    severity_counts = Counter(str(item.get("severity") or "unknown") for item in validation_list)
    record_type_counts = Counter(str(item.get("record_type") or "unknown") for item in validation_list)

    invalid = [item for item in validation_list if not bool(item.get("valid"))]
    critical = [item for item in validation_list if str(item.get("severity") or "") == "critical"]
    warnings = [item for item in validation_list if str(item.get("severity") or "") == "warning"]

    return {
        "type": "security_validation_summary",
        "validated_records": len(validation_list),
        "valid_records": len(validation_list) - len(invalid),
        "invalid_records": len(invalid),
        "critical_records": len(critical),
        "severity_counts": dict(severity_counts),
        "record_type_counts": dict(record_type_counts),
        "invalid_reasons": _reason_counts(invalid),
        "warning_reasons": _reason_counts(warnings),
    }


def build_security_validation_heartbeat_metrics(records: Iterable[Any]) -> dict[str, Any]:
    """Build security heartbeat metrics from runtime records."""
    validations = validate_runtime_records(records)
    summary = summarize_runtime_validations(validations)

    return {
        "security_validation_records": summary["validated_records"],
        "security_validation_valid_records": summary["valid_records"],
        "security_validation_invalid_records": summary["invalid_records"],
        "security_validation_critical_records": summary["critical_records"],
        "security_validation_severity_counts": summary["severity_counts"],
        "security_validation_record_type_counts": summary["record_type_counts"],
        "security_validation_invalid_reasons": summary["invalid_reasons"],
        "security_validation_warning_reasons": summary["warning_reasons"],
    }


def _reason_counts(records: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in records:
        reasons = item.get("reasons")
        if not isinstance(reasons, list):
            continue
        for reason in reasons:
            clean = str(reason or "").strip()
            if clean:
                counts[clean] += 1
    return dict(counts)


def _record_id(record: Mapping[str, Any]) -> str:
    for key in ("proposal_id", "directive_id", "scenario_id", "execution_id", "evidence_id", "memory_id", "id", "event_id", "approval_id"):
        value = str(record.get(key) or "").strip()
        if value:
            return value
    payload = record.get("payload")
    if isinstance(payload, Mapping):
        for key in ("proposal_id", "directive_id", "scenario_id", "execution_id", "evidence_id", "memory_id", "id", "event_id", "approval_id"):
            value = str(payload.get(key) or "").strip()
            if value:
                return value
    return ""


def _directive_id(record: Mapping[str, Any]) -> str | None:
    value = str(record.get("directive_id") or "").strip()
    if value:
        return value
    payload = record.get("payload")
    if isinstance(payload, Mapping):
        value = str(payload.get("directive_id") or "").strip()
        if value:
            return value
    return None

def validate_replay_evidence_lifecycle_result(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate replay evidence lifecycle result records."""
    reasons: list[str] = []
    warning_reasons: list[str] = []

    status = str(record.get("status") or "").strip().lower()
    scenario_id = str(record.get("scenario_id") or "").strip()
    directive_id = str(record.get("directive_id") or "").strip()
    checks = record.get("checks")

    payload = record.get("payload")
    if not isinstance(payload, Mapping):
        payload = {}

    failure_reason = str(payload.get("failure_reason") or "").strip()

    if status not in {"passed", "failed"}:
        reasons.append("invalid_status")

    if status == "passed" and failure_reason:
        reasons.append("passed_result_contains_failure_reason")

    if status == "failed" and failure_reason:
        warning_reasons.append(failure_reason)

    if not scenario_id:
        reasons.append("missing_scenario_id")

    if not directive_id:
        reasons.append("missing_directive_id")

    if not isinstance(checks, list) or not checks:
        reasons.append("missing_checks")
    else:
        for check in checks:
            if not isinstance(check, Mapping):
                reasons.append("invalid_check")
                continue

            check_name = str(check.get("name") or "").strip()
            check_status = str(check.get("status") or "").strip().lower()

            if not check_name:
                reasons.append("missing_check_name")

            if check_status not in {"passed", "failed"}:
                reasons.append("invalid_check_status")

        if status == "passed":
            failed_checks = [
                check
                for check in checks
                if isinstance(check, Mapping)
                and str(check.get("status") or "").strip().lower() != "passed"
            ]
            if failed_checks:
                reasons.append("passed_result_contains_failed_checks")

    valid = not reasons
    severity = "critical" if reasons else ("warning" if warning_reasons else "info")

    return {
        "type": "security_validation_result",
        "record_type": "replay_evidence_lifecycle_result",
        "valid": valid,
        "severity": severity,
        "reasons": reasons + warning_reasons,
        "subject": directive_id or scenario_id or "unknown",
    }


def validate_replay_lifecycle_retry_proposal(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate pending replay lifecycle retry proposal records."""
    reasons: list[str] = []

    proposal_id = str(record.get("proposal_id") or "").strip()
    status = str(record.get("status") or "").strip().lower()
    reason = str(record.get("reason") or "").strip()
    timeout_profile = str(record.get("timeout_profile") or "").strip()
    command_template = str(record.get("command_template") or "").strip()

    payload = record.get("payload")
    if not isinstance(payload, Mapping):
        payload = {}

    payload_recommendation = str(payload.get("recommendation") or "").strip()
    payload_reason = str(payload.get("reason") or "").strip()
    payload_timeout_profile = str(payload.get("timeout_profile") or "").strip()

    if not proposal_id:
        reasons.append("missing_proposal_id")

    if status != "pending":
        reasons.append("non_pending_retry_proposal")

    if reason != "execution_not_observed_before_timeout":
        reasons.append("invalid_retry_reason")

    if timeout_profile not in {"standard", "patient"}:
        reasons.append("invalid_timeout_profile")

    if not command_template:
        reasons.append("missing_command_template")
    else:
        if "python -m src.testing.run_replay_evidence_check" not in command_template:
            reasons.append("invalid_command_template")
        if "--timeout-profile" not in command_template:
            reasons.append("missing_timeout_profile_argument")

    if payload_recommendation != "retry_replay_lifecycle_check":
        reasons.append("invalid_payload_recommendation")

    if payload_reason and payload_reason != reason:
        reasons.append("payload_reason_mismatch")

    if payload_timeout_profile and payload_timeout_profile != timeout_profile:
        reasons.append("payload_timeout_profile_mismatch")

    valid = not reasons

    return {
        "type": "security_validation_result",
        "record_type": "replay_lifecycle_retry_proposal",
        "valid": valid,
        "severity": "info" if valid else "critical",
        "reasons": reasons,
        "subject": proposal_id or "unknown",
    }


def validate_replay_lifecycle_retry_approval(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate replay lifecycle retry approval records."""
    reasons: list[str] = []

    approval_id = str(record.get("approval_id") or "").strip()
    proposal_id = str(record.get("proposal_id") or "").strip()
    status = str(record.get("status") or "").strip().lower()
    approved_by = str(record.get("approved_by") or "").strip()
    execution_enabled = bool(record.get("execution_enabled"))

    payload = record.get("payload")
    if not isinstance(payload, Mapping):
        payload = {}

    payload_proposal_id = str(payload.get("proposal_id") or "").strip()
    payload_timeout_profile = str(payload.get("timeout_profile") or "").strip()
    payload_command_template = str(payload.get("command_template") or "").strip()

    if not approval_id:
        reasons.append("missing_approval_id")

    if not proposal_id:
        reasons.append("missing_proposal_id")

    if status not in {"approved", "rejected"}:
        reasons.append("invalid_approval_status")

    if not approved_by:
        reasons.append("missing_approved_by")

    if execution_enabled:
        reasons.append("approval_execution_enabled_before_runner")

    if payload_proposal_id and payload_proposal_id != proposal_id:
        reasons.append("payload_proposal_id_mismatch")

    if status == "approved":
        if payload_timeout_profile not in {"standard", "patient"}:
            reasons.append("invalid_approval_timeout_profile")

        if not payload_command_template:
            reasons.append("missing_approval_command_template")
        else:
            if "python -m src.testing.run_replay_evidence_check" not in payload_command_template:
                reasons.append("invalid_approval_command_template")
            if "--timeout-profile" not in payload_command_template:
                reasons.append("missing_approval_timeout_profile_argument")

    valid = not reasons

    return {
        "type": "security_validation_result",
        "record_type": "replay_lifecycle_retry_approval",
        "valid": valid,
        "severity": "info" if valid else "critical",
        "reasons": reasons,
        "subject": approval_id or proposal_id or "unknown",
    }


__all__ = [
    "VALIDATED_RECORD_TYPES",
    "build_security_validation_heartbeat_metrics",
    "summarize_runtime_validations",
    "validate_replay_evidence_lifecycle_result",
    "validate_runtime_records",
    "validate_replay_lifecycle_retry_proposal",
    "validate_replay_lifecycle_retry_approval",
]