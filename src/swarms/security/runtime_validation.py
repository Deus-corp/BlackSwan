"""Security swarm runtime validation helpers.

These helpers scan CRDT-visible runtime records and summarize validation results.
They are observational by default and do not block execution.
"""

from __future__ import annotations

import shlex

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
    "replay_lifecycle_retry_execution_plan",
    "replay_lifecycle_retry_execution_result",
    "replay_lifecycle_retry_rendered_command",
    "replay_lifecycle_retry_rendered_command_result",
    "replay_lifecycle_retry_execution_eligibility",
    "replay_lifecycle_retry_controlled_execution_result",
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

        if record_type == "replay_lifecycle_retry_execution_plan":
            result = validate_replay_lifecycle_retry_execution_plan(record)
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if record_type == "replay_lifecycle_retry_execution_result":
            result = validate_replay_lifecycle_retry_execution_result(record)
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if record_type == "replay_lifecycle_retry_rendered_command":
            result = validate_replay_lifecycle_retry_rendered_command(record)
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if record_type == "replay_lifecycle_retry_rendered_command_result":
            result = validate_replay_lifecycle_retry_rendered_command_result(record)
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if record_type == "replay_lifecycle_retry_execution_eligibility":
            result = validate_replay_lifecycle_retry_execution_eligibility(record)
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if record_type == "replay_lifecycle_retry_controlled_execution_result":
            result = validate_replay_lifecycle_retry_controlled_execution_result(record)
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

    retry_approval_decision_modes: dict[str, int] = {}
    retry_execution_result_statuses: dict[str, int] = {}
    retry_execution_result_reasons: dict[str, int] = {}
    retry_rendered_command_profiles: dict[str, int] = {}
    retry_rendered_command_decision_modes: dict[str, int] = {}
    retry_rendered_command_result_statuses: dict[str, int] = {}
    retry_rendered_command_result_reasons: dict[str, int] = {}
    retry_execution_eligibility_statuses: dict[str, int] = {}
    retry_execution_eligibility_reasons: dict[str, int] = {}
    controlled_execution_result_statuses: dict[str, int] = {}
    controlled_execution_result_reasons: dict[str, int] = {}
    controlled_execution_operator_authorized: dict[str, int] = {}
    controlled_execution_allowlist_matched: dict[str, int] = {}
    controlled_execution_command_parse_valid: dict[str, int] = {}
    controlled_execution_command_parse_allowlist_matched: dict[str, int] = {}
    controlled_execution_command_parse_execution_performed: dict[str, int] = {}

    for item in validation_list:
        record_type = str(item.get("record_type") or "").strip()

        if record_type == "replay_lifecycle_retry_approval":
            mode = str(item.get("decision_mode") or "unknown").strip() or "unknown"
            retry_approval_decision_modes[mode] = (
                retry_approval_decision_modes.get(mode, 0) + 1
            )

        elif record_type == "replay_lifecycle_retry_execution_result":
            status = str(item.get("status") or "unknown").strip() or "unknown"
            reason = str(item.get("reason") or "unknown").strip() or "unknown"

            retry_execution_result_statuses[status] = (
                retry_execution_result_statuses.get(status, 0) + 1
            )
            retry_execution_result_reasons[reason] = (
                retry_execution_result_reasons.get(reason, 0) + 1
            )

        elif record_type == "replay_lifecycle_retry_rendered_command":
            profile = str(item.get("timeout_profile") or "unknown").strip() or "unknown"
            mode = str(item.get("decision_mode") or "unknown").strip() or "unknown"

            retry_rendered_command_profiles[profile] = (
                retry_rendered_command_profiles.get(profile, 0) + 1
            )
            retry_rendered_command_decision_modes[mode] = (
                retry_rendered_command_decision_modes.get(mode, 0) + 1
            )

        elif record_type == "replay_lifecycle_retry_rendered_command_result":
            status = str(item.get("status") or "unknown").strip() or "unknown"
            reason = str(item.get("reason") or "unknown").strip() or "unknown"

            retry_rendered_command_result_statuses[status] = (
                retry_rendered_command_result_statuses.get(status, 0) + 1
            )
            retry_rendered_command_result_reasons[reason] = (
                retry_rendered_command_result_reasons.get(reason, 0) + 1
            )

        elif record_type == "replay_lifecycle_retry_execution_eligibility":
            status = str(item.get("status") or "unknown").strip() or "unknown"
            reason = str(item.get("reason") or "unknown").strip() or "unknown"

            retry_execution_eligibility_statuses[status] = (
                retry_execution_eligibility_statuses.get(status, 0) + 1
            )
            retry_execution_eligibility_reasons[reason] = (
                retry_execution_eligibility_reasons.get(reason, 0) + 1
            )

        if record_type == "replay_lifecycle_retry_controlled_execution_result":
            status = str(item.get("status") or "unknown").strip() or "unknown"
            reason = str(item.get("reason") or "unknown").strip() or "unknown"
            operator_authorized = str(
                bool(item.get("operator_authorized"))
            ).lower()
            allowlist_matched = str(
                bool(item.get("allowlist_matched"))
            ).lower()

            controlled_execution_result_statuses[status] = (
                controlled_execution_result_statuses.get(status, 0) + 1
            )
            controlled_execution_result_reasons[reason] = (
                controlled_execution_result_reasons.get(reason, 0) + 1
            )
            controlled_execution_operator_authorized[operator_authorized] = (
                controlled_execution_operator_authorized.get(operator_authorized, 0) + 1
            )
            controlled_execution_allowlist_matched[allowlist_matched] = (
                controlled_execution_allowlist_matched.get(allowlist_matched, 0) + 1
            )

            command_parse_valid = str(
                bool(item.get("command_parse_valid"))
            ).lower()
            command_parse_allowlist_matched = str(
                bool(item.get("command_parse_allowlist_matched"))
            ).lower()
            command_parse_execution_performed = str(
                bool(item.get("command_parse_execution_performed"))
            ).lower()

            controlled_execution_command_parse_valid[command_parse_valid] = (
                controlled_execution_command_parse_valid.get(command_parse_valid, 0) + 1
            )
            controlled_execution_command_parse_allowlist_matched[
                command_parse_allowlist_matched
            ] = (
                controlled_execution_command_parse_allowlist_matched.get(
                    command_parse_allowlist_matched, 0
                )
                + 1
            )
            controlled_execution_command_parse_execution_performed[
                command_parse_execution_performed
            ] = (
                controlled_execution_command_parse_execution_performed.get(
                    command_parse_execution_performed, 0
                )
                + 1
            )

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
        "retry_approval_decision_modes": retry_approval_decision_modes,
        "retry_execution_result_statuses": retry_execution_result_statuses,
        "retry_execution_result_reasons": retry_execution_result_reasons,
        "retry_rendered_command_profiles": retry_rendered_command_profiles,
        "retry_rendered_command_decision_modes": retry_rendered_command_decision_modes,
        "retry_rendered_command_result_statuses": retry_rendered_command_result_statuses,
        "retry_rendered_command_result_reasons": retry_rendered_command_result_reasons,
        "retry_execution_eligibility_statuses": retry_execution_eligibility_statuses,
        "retry_execution_eligibility_reasons": retry_execution_eligibility_reasons,
        "controlled_execution_result_statuses": controlled_execution_result_statuses,
        "controlled_execution_result_reasons": controlled_execution_result_reasons,
        "controlled_execution_operator_authorized": controlled_execution_operator_authorized,
        "controlled_execution_allowlist_matched": controlled_execution_allowlist_matched,
        "controlled_execution_command_parse_valid": controlled_execution_command_parse_valid,
        "controlled_execution_command_parse_allowlist_matched": (
            controlled_execution_command_parse_allowlist_matched
        ),
        "controlled_execution_command_parse_execution_performed": (
            controlled_execution_command_parse_execution_performed
        ),
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
        "security_validation_retry_approval_decision_modes": summary["retry_approval_decision_modes"],
        "security_validation_retry_execution_result_statuses": summary["retry_execution_result_statuses"],
        "security_validation_retry_execution_result_reasons": summary["retry_execution_result_reasons"],
        "security_validation_retry_rendered_command_profiles": summary["retry_rendered_command_profiles"],
        "security_validation_retry_rendered_command_decision_modes": summary["retry_rendered_command_decision_modes"],
        "security_validation_retry_rendered_command_result_statuses": summary["retry_rendered_command_result_statuses"],
        "security_validation_retry_rendered_command_result_reasons": summary["retry_rendered_command_result_reasons"],
        "security_validation_retry_execution_eligibility_statuses": summary["retry_execution_eligibility_statuses"],
        "security_validation_retry_execution_eligibility_reasons": summary["retry_execution_eligibility_reasons"],
        "security_validation_controlled_execution_result_statuses": summary[
            "controlled_execution_result_statuses"
        ],
        "security_validation_controlled_execution_result_reasons": summary[
            "controlled_execution_result_reasons"
        ],
        "security_validation_controlled_execution_operator_authorized": summary[
            "controlled_execution_operator_authorized"
        ],
        "security_validation_controlled_execution_allowlist_matched": summary[
            "controlled_execution_allowlist_matched"
        ],
        "security_validation_controlled_execution_command_parse_valid": summary[
            "controlled_execution_command_parse_valid"
        ],
        "security_validation_controlled_execution_command_parse_allowlist_matched": summary[
            "controlled_execution_command_parse_allowlist_matched"
        ],
        "security_validation_controlled_execution_command_parse_execution_performed": summary[
            "controlled_execution_command_parse_execution_performed"
        ],
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
    record_type = str(record.get("type") or "").strip()

    if record_type == "replay_lifecycle_retry_controlled_execution_result":
        return str(
            record.get("controlled_execution_result_id")
            or record.get("rendered_command_id")
            or ""
        ).strip()

    if record_type == "replay_lifecycle_retry_execution_eligibility":
        return str(
            record.get("eligibility_id")
            or record.get("rendered_command_id")
            or record.get("plan_id")
            or ""
        ).strip()

    if record_type == "replay_lifecycle_retry_rendered_command_result":
        return str(
            record.get("rendered_command_result_id")
            or record.get("rendered_command_id")
            or record.get("plan_id")
            or ""
        ).strip()

    if record_type == "replay_lifecycle_retry_rendered_command":
        return str(
            record.get("rendered_command_id")
            or record.get("plan_id")
            or ""
        ).strip()

    if record_type == "replay_lifecycle_retry_execution_result":
        return str(
            record.get("result_id")
            or record.get("plan_id")
            or ""
        ).strip()

    if record_type == "replay_lifecycle_retry_execution_plan":
        return str(record.get("plan_id") or "").strip()

    if record_type == "replay_lifecycle_retry_approval":
        return str(record.get("approval_id") or "").strip()

    if record_type == "replay_lifecycle_retry_proposal":
        return str(record.get("proposal_id") or "").strip()

    for key in (
        "directive_id",
        "scenario_id",
        "execution_id",
        "evidence_id",
        "memory_id",
        "id",
        "event_id",
        "result_id",
        "plan_id",
        "eligibility_id",
        "rendered_command_result_id",
        "rendered_command_id",
        "approval_id",
        "proposal_id",
        "controlled_execution_result_id",
    ):
        value = str(record.get(key) or "").strip()
        if value:
            return value

    payload = record.get("payload")
    if isinstance(payload, Mapping):
        for key in (
            "directive_id",
            "scenario_id",
            "execution_id",
            "evidence_id",
            "memory_id",
            "id",
            "event_id",
            "result_id",
            "plan_id",
            "eligibility_id",
            "rendered_command_result_id",
            "rendered_command_id",
            "approval_id",
            "proposal_id",
            "controlled_execution_result_id",
        ):
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
    decision_mode = str(record.get("decision_mode") or "").strip().lower()

    payload = record.get("payload")
    if not isinstance(payload, Mapping):
        payload = {}

    payload_proposal_id = str(payload.get("proposal_id") or "").strip()
    payload_timeout_profile = str(payload.get("timeout_profile") or "").strip()
    payload_command_template = str(payload.get("command_template") or "").strip()
    payload_decision_mode = str(payload.get("decision_mode") or "").strip().lower()

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

    if decision_mode not in {"manual", "policy"}:
        reasons.append("invalid_approval_decision_mode")

    if payload_decision_mode and payload_decision_mode != decision_mode:
        reasons.append("payload_decision_mode_mismatch")

    valid = not reasons

    return {
        "type": "security_validation_result",
        "record_type": "replay_lifecycle_retry_approval",
        "valid": valid,
        "severity": "info" if valid else "critical",
        "reasons": reasons,
        "subject": approval_id or proposal_id or "unknown",
        "decision_mode": decision_mode or "unknown",
    }


def validate_replay_lifecycle_retry_execution_plan(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate non-executing replay lifecycle retry execution plan records."""
    reasons: list[str] = []

    plan_id = str(record.get("plan_id") or "").strip()
    proposal_id = str(record.get("proposal_id") or "").strip()
    approval_id = str(record.get("approval_id") or "").strip()
    status = str(record.get("status") or "").strip().lower()
    execution_enabled = bool(record.get("execution_enabled"))
    timeout_profile = str(record.get("timeout_profile") or "").strip()
    command_template = str(record.get("command_template") or "").strip()
    decision_mode = str(record.get("decision_mode") or "").strip().lower()

    payload = record.get("payload")
    if not isinstance(payload, Mapping):
        payload = {}

    payload_proposal_id = str(payload.get("proposal_id") or "").strip()
    payload_approval_id = str(payload.get("approval_id") or "").strip()
    payload_timeout_profile = str(payload.get("timeout_profile") or "").strip()
    payload_command_template = str(payload.get("command_template") or "").strip()
    payload_decision_mode = str(payload.get("decision_mode") or "").strip().lower()

    if not plan_id:
        reasons.append("missing_plan_id")

    if not proposal_id:
        reasons.append("missing_proposal_id")

    if not approval_id:
        reasons.append("missing_approval_id")

    if status != "planned":
        reasons.append("invalid_retry_plan_status")

    if execution_enabled:
        reasons.append("retry_plan_execution_enabled_before_runner")

    if timeout_profile not in {"standard", "patient"}:
        reasons.append("invalid_retry_plan_timeout_profile")

    if decision_mode not in {"manual", "policy"}:
        reasons.append("invalid_retry_plan_decision_mode")

    if not command_template:
        reasons.append("missing_retry_plan_command_template")
    else:
        if "python -m src.testing.run_replay_evidence_check" not in command_template:
            reasons.append("invalid_retry_plan_command_template")
        if "--timeout-profile" not in command_template:
            reasons.append("missing_retry_plan_timeout_profile_argument")

    if payload_proposal_id and payload_proposal_id != proposal_id:
        reasons.append("payload_proposal_id_mismatch")

    if payload_approval_id and payload_approval_id != approval_id:
        reasons.append("payload_approval_id_mismatch")

    if payload_timeout_profile and payload_timeout_profile != timeout_profile:
        reasons.append("payload_timeout_profile_mismatch")

    if payload_command_template and payload_command_template != command_template:
        reasons.append("payload_command_template_mismatch")

    if payload_decision_mode and payload_decision_mode != decision_mode:
        reasons.append("payload_decision_mode_mismatch")

    valid = not reasons

    return {
        "type": "security_validation_result",
        "record_type": "replay_lifecycle_retry_execution_plan",
        "valid": valid,
        "severity": "info" if valid else "critical",
        "reasons": reasons,
        "subject": plan_id or approval_id or proposal_id or "unknown",
        "decision_mode": decision_mode or "unknown",
    }


def validate_replay_lifecycle_retry_execution_result(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate replay lifecycle retry execution result records."""
    reasons: list[str] = []

    result_id = str(record.get("result_id") or "").strip()
    plan_id = str(record.get("plan_id") or "").strip()
    status = str(record.get("status") or "").strip().lower()
    reason = str(record.get("reason") or "").strip()
    execution_enabled = bool(record.get("execution_enabled"))

    payload = record.get("payload")
    if not isinstance(payload, Mapping):
        payload = {}

    executed = bool(payload.get("executed"))
    payload_plan_id = str(payload.get("plan_id") or "").strip()
    payload_execution_enabled = bool(payload.get("execution_enabled"))

    if not result_id:
        reasons.append("missing_result_id")

    if not plan_id:
        reasons.append("missing_plan_id")

    if status not in {"skipped", "rejected"}:
        reasons.append("invalid_retry_execution_result_status")

    if status == "skipped" and reason != "execution_disabled":
        reasons.append("invalid_skipped_retry_execution_reason")

    if status == "rejected" and reason != "execution_not_supported":
        reasons.append("invalid_rejected_retry_execution_reason")

    if executed:
        reasons.append("retry_execution_result_executed_before_runner_support")

    if execution_enabled and status != "rejected":
        reasons.append("enabled_retry_execution_result_must_be_rejected")

    if payload_plan_id and payload_plan_id != plan_id:
        reasons.append("payload_plan_id_mismatch")

    if payload_execution_enabled != execution_enabled:
        reasons.append("payload_execution_enabled_mismatch")

    valid = not reasons

    return {
        "type": "security_validation_result",
        "record_type": "replay_lifecycle_retry_execution_result",
        "valid": valid,
        "severity": "info" if valid else "critical",
        "reasons": reasons,
        "subject": result_id or plan_id or "unknown",
        "status": status or "unknown",
        "reason": reason or "unknown",
    }


def validate_replay_lifecycle_retry_rendered_command(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate non-executing rendered retry command records."""
    reasons: list[str] = []

    rendered_command_id = str(record.get("rendered_command_id") or "").strip()
    plan_id = str(record.get("plan_id") or "").strip()
    proposal_id = str(record.get("proposal_id") or "").strip()
    approval_id = str(record.get("approval_id") or "").strip()
    status = str(record.get("status") or "").strip().lower()
    execution_enabled = bool(record.get("execution_enabled"))
    command = str(record.get("command") or "").strip()
    timeout_profile = str(record.get("timeout_profile") or "").strip()
    decision_mode = str(record.get("decision_mode") or "").strip().lower()

    payload = record.get("payload")
    if not isinstance(payload, Mapping):
        payload = {}

    payload_command = str(payload.get("command") or "").strip()
    payload_plan_id = str(payload.get("plan_id") or "").strip()
    payload_executed = bool(payload.get("executed"))
    payload_execution_enabled = bool(payload.get("execution_enabled"))
    payload_timeout_profile = str(payload.get("timeout_profile") or "").strip()
    payload_decision_mode = str(payload.get("decision_mode") or "").strip().lower()

    if not rendered_command_id:
        reasons.append("missing_rendered_command_id")
    if not plan_id:
        reasons.append("missing_plan_id")
    if not proposal_id:
        reasons.append("missing_proposal_id")
    if not approval_id:
        reasons.append("missing_approval_id")
    if status != "rendered":
        reasons.append("invalid_rendered_command_status")
    if execution_enabled:
        reasons.append("rendered_command_execution_enabled_before_runner")
    if payload_execution_enabled:
        reasons.append("payload_execution_enabled_before_runner")
    if payload_executed:
        reasons.append("rendered_command_executed_before_runner")
    if timeout_profile not in {"standard", "patient"}:
        reasons.append("invalid_rendered_command_timeout_profile")
    if decision_mode not in {"manual", "policy"}:
        reasons.append("invalid_rendered_command_decision_mode")

    if not command:
        reasons.append("missing_rendered_command")
    else:
        reasons.extend(_validate_rendered_retry_command_text(command, timeout_profile=timeout_profile))

    if payload_command and payload_command != command:
        reasons.append("payload_command_mismatch")
    if payload_plan_id and payload_plan_id != plan_id:
        reasons.append("payload_plan_id_mismatch")
    if payload_timeout_profile and payload_timeout_profile != timeout_profile:
        reasons.append("payload_timeout_profile_mismatch")
    if payload_decision_mode and payload_decision_mode != decision_mode:
        reasons.append("payload_decision_mode_mismatch")

    valid = not reasons

    return {
        "type": "security_validation_result",
        "record_type": "replay_lifecycle_retry_rendered_command",
        "valid": valid,
        "severity": "info" if valid else "critical",
        "reasons": reasons,
        "subject": rendered_command_id or plan_id or "unknown",
        "timeout_profile": timeout_profile or "unknown",
        "decision_mode": decision_mode or "unknown",
    }


def _validate_rendered_retry_command_text(command: str, *, timeout_profile: str) -> list[str]:
    reasons: list[str] = []

    forbidden = [";", "&&", "|", ">", "<", "`", "$("]
    if any(token in command for token in forbidden):
        reasons.append("rendered_command_contains_unsafe_shell_syntax")
        return reasons

    try:
        parts = shlex.split(command)
    except ValueError:
        reasons.append("rendered_command_parse_failed")
        return reasons

    if parts[:3] != ["python", "-m", "src.testing.run_replay_evidence_check"]:
        reasons.append("invalid_rendered_command_module")

    if "--scenario-id" not in parts:
        reasons.append("missing_rendered_command_scenario_id")
    if "--directive-id" not in parts:
        reasons.append("missing_rendered_command_directive_id")
    if "--timeout-profile" not in parts:
        reasons.append("missing_rendered_command_timeout_profile_argument")
    else:
        profile_index = parts.index("--timeout-profile")
        if profile_index + 1 >= len(parts):
            reasons.append("missing_rendered_command_timeout_profile_value")
        elif parts[profile_index + 1] != timeout_profile:
            reasons.append("rendered_command_timeout_profile_mismatch")

    return reasons


def validate_replay_lifecycle_retry_rendered_command_result(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate non-executing rendered retry command result records."""
    reasons: list[str] = []

    result_id = str(record.get("rendered_command_result_id") or "").strip()
    rendered_command_id = str(record.get("rendered_command_id") or "").strip()
    plan_id = str(record.get("plan_id") or "").strip()
    proposal_id = str(record.get("proposal_id") or "").strip()
    approval_id = str(record.get("approval_id") or "").strip()
    status = str(record.get("status") or "").strip().lower()
    reason = str(record.get("reason") or "").strip()
    execution_enabled = bool(record.get("execution_enabled"))
    command = str(record.get("command") or "").strip()
    timeout_profile = str(record.get("timeout_profile") or "").strip()
    decision_mode = str(record.get("decision_mode") or "").strip().lower()

    payload = record.get("payload")
    if not isinstance(payload, Mapping):
        payload = {}

    payload_rendered_command_id = str(payload.get("rendered_command_id") or "").strip()
    payload_plan_id = str(payload.get("plan_id") or "").strip()
    payload_command = str(payload.get("command") or "").strip()
    payload_execution_enabled = bool(payload.get("execution_enabled"))
    payload_executed = bool(payload.get("executed"))
    payload_timeout_profile = str(payload.get("timeout_profile") or "").strip()
    payload_decision_mode = str(payload.get("decision_mode") or "").strip().lower()

    if not result_id:
        reasons.append("missing_rendered_command_result_id")
    if not rendered_command_id:
        reasons.append("missing_rendered_command_id")
    if not plan_id:
        reasons.append("missing_plan_id")
    if not proposal_id:
        reasons.append("missing_proposal_id")
    if not approval_id:
        reasons.append("missing_approval_id")
    if not command:
        reasons.append("missing_rendered_command_result_command")
    if timeout_profile and timeout_profile not in {"standard", "patient"}:
        reasons.append("invalid_rendered_command_result_timeout_profile")
    if decision_mode and decision_mode not in {"manual", "policy"}:
        reasons.append("invalid_rendered_command_result_decision_mode")

    if status == "skipped":
        if reason != "execution_disabled":
            reasons.append("invalid_skipped_rendered_command_result_reason")
        if execution_enabled:
            reasons.append("skipped_rendered_command_result_execution_enabled")
    elif status == "rejected":
        if reason != "execution_not_supported":
            reasons.append("invalid_rejected_rendered_command_result_reason")
        # execution_enabled=True is allowed here: runner explicitly rejected enabled command.
    else:
        reasons.append("invalid_rendered_command_result_status")

    if payload_execution_enabled != execution_enabled:
        reasons.append("payload_execution_enabled_mismatch")
    if payload_executed:
        reasons.append("rendered_command_result_executed_before_runner")
    if payload_rendered_command_id and payload_rendered_command_id != rendered_command_id:
        reasons.append("payload_rendered_command_id_mismatch")
    if payload_plan_id and payload_plan_id != plan_id:
        reasons.append("payload_plan_id_mismatch")
    if payload_command and payload_command != command:
        reasons.append("payload_command_mismatch")
    if payload_timeout_profile and payload_timeout_profile != timeout_profile:
        reasons.append("payload_timeout_profile_mismatch")
    if payload_decision_mode and payload_decision_mode != decision_mode:
        reasons.append("payload_decision_mode_mismatch")

    valid = not reasons

    return {
        "type": "security_validation_result",
        "record_type": "replay_lifecycle_retry_rendered_command_result",
        "valid": valid,
        "severity": "info" if valid else "critical",
        "reasons": reasons,
        "subject": result_id or rendered_command_id or plan_id or "unknown",
        "status": status or "unknown",
        "reason": reason or "unknown",
        "timeout_profile": timeout_profile or "unknown",
        "decision_mode": decision_mode or "unknown",
    }


ELIGIBILITY_BLOCK_REASONS = {
    "execution_disabled",
    "execution_not_supported",
    "missing_rendered_command_result",
    "missing_rendered_command",
}


def validate_replay_lifecycle_retry_execution_eligibility(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate non-executing retry execution eligibility records."""
    reasons: list[str] = []

    eligibility_id = str(record.get("eligibility_id") or "").strip()
    rendered_command_id = str(record.get("rendered_command_id") or "").strip()
    plan_id = str(record.get("plan_id") or "").strip()
    proposal_id = str(record.get("proposal_id") or "").strip()
    approval_id = str(record.get("approval_id") or "").strip()
    status = str(record.get("status") or "").strip().lower()
    reason = str(record.get("reason") or "").strip()
    execution_supported = bool(record.get("execution_supported"))
    execution_enabled = bool(record.get("execution_enabled"))
    timeout_profile = str(record.get("timeout_profile") or "").strip()
    decision_mode = str(record.get("decision_mode") or "").strip().lower()
    command = str(record.get("command") or "").strip()

    payload = record.get("payload")
    if not isinstance(payload, Mapping):
        payload = {}

    payload_rendered_command_id = str(payload.get("rendered_command_id") or "").strip()
    payload_plan_id = str(payload.get("plan_id") or "").strip()
    payload_status = str(payload.get("status") or "").strip().lower()
    payload_reason = str(payload.get("reason") or "").strip()
    payload_execution_supported = bool(payload.get("execution_supported"))
    payload_execution_enabled = bool(payload.get("execution_enabled"))
    payload_executed = bool(payload.get("executed"))
    payload_timeout_profile = str(payload.get("timeout_profile") or "").strip()
    payload_decision_mode = str(payload.get("decision_mode") or "").strip().lower()
    payload_command = str(payload.get("command") or "").strip()

    if not eligibility_id:
        reasons.append("missing_eligibility_id")

    if reason != "missing_rendered_command" and not rendered_command_id:
        reasons.append("missing_rendered_command_id")

    if reason != "missing_rendered_command" and not plan_id:
        reasons.append("missing_plan_id")

    if reason not in {"missing_rendered_command", "missing_rendered_command_result"}:
        if not proposal_id:
            reasons.append("missing_proposal_id")
        if not approval_id:
            reasons.append("missing_approval_id")

    if status != "blocked":
        reasons.append("invalid_execution_eligibility_status")

    if reason not in ELIGIBILITY_BLOCK_REASONS:
        reasons.append("invalid_execution_eligibility_reason")

    if execution_supported:
        reasons.append("execution_supported_before_runner")

    if execution_enabled:
        reasons.append("execution_enabled_before_runner")

    if payload_execution_supported:
        reasons.append("payload_execution_supported_before_runner")

    if payload_execution_enabled:
        reasons.append("payload_execution_enabled_before_runner")

    if payload_executed:
        reasons.append("execution_eligibility_executed_before_runner")

    if payload_status and payload_status != status:
        reasons.append("payload_status_mismatch")

    if payload_reason and payload_reason != reason:
        reasons.append("payload_reason_mismatch")

    if payload_rendered_command_id and payload_rendered_command_id != rendered_command_id:
        reasons.append("payload_rendered_command_id_mismatch")

    if payload_plan_id and payload_plan_id != plan_id:
        reasons.append("payload_plan_id_mismatch")

    if payload_timeout_profile and payload_timeout_profile != timeout_profile:
        reasons.append("payload_timeout_profile_mismatch")

    if payload_decision_mode and payload_decision_mode != decision_mode:
        reasons.append("payload_decision_mode_mismatch")

    if payload_command and payload_command != command:
        reasons.append("payload_command_mismatch")

    if timeout_profile and timeout_profile not in {"standard", "patient", "unknown"}:
        reasons.append("invalid_execution_eligibility_timeout_profile")

    if decision_mode and decision_mode not in {"manual", "policy", "unknown"}:
        reasons.append("invalid_execution_eligibility_decision_mode")

    valid = not reasons

    return {
        "type": "security_validation_result",
        "record_type": "replay_lifecycle_retry_execution_eligibility",
        "valid": valid,
        "severity": "info" if valid else "critical",
        "reasons": reasons,
        "subject": eligibility_id or rendered_command_id or plan_id or "unknown",
        "status": status or "unknown",
        "reason": reason or "unknown",
        "timeout_profile": timeout_profile or "unknown",
        "decision_mode": decision_mode or "unknown",
    }


def validate_replay_lifecycle_retry_controlled_execution_result(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate reject-only controlled retry execution result records."""
    reasons: list[str] = []

    controlled_execution_result_id = str(
        record.get("controlled_execution_result_id") or ""
    ).strip()
    rendered_command_id = str(record.get("rendered_command_id") or "").strip()
    plan_id = str(record.get("plan_id") or "").strip()
    proposal_id = str(record.get("proposal_id") or "").strip()
    approval_id = str(record.get("approval_id") or "").strip()
    status = str(record.get("status") or "").strip()
    reason = str(record.get("reason") or "").strip()
    command = str(record.get("command") or "").strip()
    timeout_profile = str(record.get("timeout_profile") or "").strip()
    decision_mode = str(record.get("decision_mode") or "").strip()

    execution_enabled = bool(record.get("execution_enabled"))
    operator_authorized = bool(record.get("operator_authorized"))
    allowlist_matched = bool(record.get("allowlist_matched"))

    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}
    payload_executed = bool(payload_mapping.get("executed"))

    command_parse = record.get("command_parse")
    if not isinstance(command_parse, Mapping):
        command_parse = payload_mapping.get("command_parse")

    command_parse_mapping = command_parse if isinstance(command_parse, Mapping) else {}
    command_parse_valid = bool(command_parse_mapping.get("valid"))
    command_parse_allowlist_matched = bool(
        command_parse_mapping.get("allowlist_matched")
    )
    command_parse_execution_performed = bool(
        command_parse_mapping.get("execution_performed")
    )

    if not controlled_execution_result_id:
        reasons.append("missing_controlled_execution_result_id")
    if not rendered_command_id:
        reasons.append("missing_rendered_command_id")
    if not plan_id:
        reasons.append("missing_plan_id")
    if not proposal_id:
        reasons.append("missing_proposal_id")
    if not approval_id:
        reasons.append("missing_approval_id")

    if status not in {"rejected", "skipped", "executed"}:
        reasons.append("invalid_status")

    if not command_parse_mapping:
        reasons.append("missing_command_parse")

    if command_parse_execution_performed:
        reasons.append("command_parse_must_not_execute")

    if reason not in {
        "controlled_execution_not_implemented",
        "execution_disabled",
        "operator_authorization_missing",
        "readiness_not_passed",
        "command_not_allowlisted",
        "duplicate_controlled_execution_result",
    }:
        reasons.append("invalid_reason")

    if timeout_profile and timeout_profile not in {"standard", "patient"}:
        reasons.append("invalid_timeout_profile")

    if decision_mode and decision_mode not in {"manual", "policy"}:
        reasons.append("invalid_decision_mode")

    # PR 28.2 skeleton phase: execution is not implemented yet.
    if status == "executed":
        reasons.append("controlled_execution_not_allowed_yet")

    if reason == "controlled_execution_not_implemented" and status != "rejected":
        reasons.append("not_implemented_result_must_be_rejected")

    if reason == "controlled_execution_not_implemented" and payload_executed:
        reasons.append("not_implemented_result_must_not_execute")

    if operator_authorized:
        reasons.append("operator_authorization_not_supported_yet")

    # allowlist_matched may be true once the parser recognizes a safe command.
    # It is valid as long as the skeleton still rejects and payload.executed=false.

    if execution_enabled and reason == "controlled_execution_not_implemented":
        # The skeleton may preserve rendered execution_enabled=true, but it still must reject.
        # This is informational and remains valid as long as no execution happened.
        pass

    severity = "critical" if reasons else "info"

    return {
        "type": "security_validation_result",
        "record_type": "replay_lifecycle_retry_controlled_execution_result",
        "valid": not reasons,
        "severity": severity,
        "reasons": reasons,
        "subject": controlled_execution_result_id or rendered_command_id,
        "status": status or "unknown",
        "reason": reason or "unknown",
        "operator_authorized": operator_authorized,
        "allowlist_matched": allowlist_matched,
        "execution_enabled": execution_enabled,
        "payload_executed": payload_executed,
        "timeout_profile": timeout_profile or "unknown",
        "decision_mode": decision_mode or "unknown",
        "command": command,
        "command_parse_valid": command_parse_valid,
        "command_parse_allowlist_matched": command_parse_allowlist_matched,
        "command_parse_execution_performed": command_parse_execution_performed,
    }


__all__ = [
    "VALIDATED_RECORD_TYPES",
    "build_security_validation_heartbeat_metrics",
    "summarize_runtime_validations",
    "validate_replay_evidence_lifecycle_result",
    "validate_runtime_records",
    "validate_replay_lifecycle_retry_proposal",
    "validate_replay_lifecycle_retry_approval",
    "validate_replay_lifecycle_retry_execution_plan",
    "validate_replay_lifecycle_retry_execution_result",
    "validate_replay_lifecycle_retry_rendered_command",
    "validate_replay_lifecycle_retry_rendered_command_result",
    "validate_replay_lifecycle_retry_execution_eligibility",
    "validate_replay_lifecycle_retry_controlled_execution_result",
]