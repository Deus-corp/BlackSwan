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
    "replay_lifecycle_retry_mock_execution_summary",
    "replay_lifecycle_retry_real_execution_preflight",
    "replay_lifecycle_retry_real_execution_approval",
    "replay_lifecycle_retry_real_execution_approval_transition",
    "replay_lifecycle_retry_real_execution_final_gate",
    "replay_lifecycle_retry_real_execution_dry_run_envelope",
    "replay_lifecycle_retry_real_execution_noop_result",
    "replay_lifecycle_retry_real_execution_read_only_promotion",
    "replay_lifecycle_retry_real_execution_read_only_final_gate",
    "replay_lifecycle_retry_real_execution_read_only_approval",
    "replay_lifecycle_retry_real_execution_read_only_approval_transition",
    "replay_lifecycle_retry_real_execution_read_only_readiness_gate",
    "replay_lifecycle_retry_real_execution_read_only_execution_result",
    "replay_lifecycle_retry_real_execution_read_only_feedback",
    "replay_lifecycle_retry_real_execution_read_only_repair_plan",
    "replay_lifecycle_retry_real_execution_read_only_repair_action_bundle",
    "replay_lifecycle_retry_real_execution_read_only_repair_action_bundle_review",
    "replay_lifecycle_retry_real_execution_repair_approval",
    "replay_lifecycle_retry_real_execution_repair_approval_transition",
    "replay_lifecycle_retry_real_execution_repair_final_gate",
    "replay_lifecycle_retry_real_execution_repair_dry_run_envelope",
    "replay_lifecycle_retry_real_execution_repair_noop_result",
    "replay_lifecycle_retry_real_execution_repair_noop_feedback",
    "replay_lifecycle_retry_real_execution_repair_readiness_gate",
    "replay_lifecycle_retry_guarded_repair_execution_result",
    "replay_lifecycle_retry_post_repair_evidence_check",
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

        if record_type == "replay_lifecycle_retry_mock_execution_summary":
            result = validate_replay_lifecycle_retry_mock_execution_summary(record)
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if record_type == "replay_lifecycle_retry_real_execution_preflight":
            result = validate_replay_lifecycle_retry_real_execution_preflight(record)
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if record_type == "replay_lifecycle_retry_real_execution_approval":
            result = validate_replay_lifecycle_retry_real_execution_approval(record)
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if record_type == "replay_lifecycle_retry_real_execution_approval_transition":
            result = validate_replay_lifecycle_retry_real_execution_approval_transition(
                record
            )
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if record_type == "replay_lifecycle_retry_real_execution_final_gate":
            result = validate_replay_lifecycle_retry_real_execution_final_gate(record)
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if record_type == "replay_lifecycle_retry_real_execution_dry_run_envelope":
            result = validate_replay_lifecycle_retry_real_execution_dry_run_envelope(
                record
            )
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if record_type == "replay_lifecycle_retry_real_execution_noop_result":
            result = validate_replay_lifecycle_retry_real_execution_noop_result(record)
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if record_type == "replay_lifecycle_retry_real_execution_read_only_promotion":
            result = (
                validate_replay_lifecycle_retry_real_execution_read_only_promotion(
                    record
                )
            )
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if record_type == "replay_lifecycle_retry_real_execution_read_only_final_gate":
            result = (
                validate_replay_lifecycle_retry_real_execution_read_only_final_gate(
                    record
                )
            )
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if record_type == "replay_lifecycle_retry_real_execution_read_only_approval":
            result = (
                validate_replay_lifecycle_retry_real_execution_read_only_approval(
                    record
                )
            )
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if (
            record_type
            == "replay_lifecycle_retry_real_execution_read_only_approval_transition"
        ):
            result = (
                validate_replay_lifecycle_retry_real_execution_read_only_approval_transition(
                    record
                )
            )
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if (
            record_type
            == "replay_lifecycle_retry_real_execution_read_only_readiness_gate"
        ):
            result = (
                validate_replay_lifecycle_retry_real_execution_read_only_readiness_gate(
                    record
                )
            )
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if (
            record_type
            == "replay_lifecycle_retry_real_execution_read_only_execution_result"
        ):
            result = (
                validate_replay_lifecycle_retry_real_execution_read_only_execution_result(
                    record
                )
            )
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if record_type == "replay_lifecycle_retry_real_execution_read_only_feedback":
            result = validate_replay_lifecycle_retry_real_execution_read_only_feedback(
                record
            )
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if record_type == "replay_lifecycle_retry_real_execution_read_only_repair_plan":
            result = (
                validate_replay_lifecycle_retry_real_execution_read_only_repair_plan(
                    record
                )
            )
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if (
            record_type
            == "replay_lifecycle_retry_real_execution_read_only_repair_action_bundle"
        ):
            result = (
                validate_replay_lifecycle_retry_real_execution_read_only_repair_action_bundle(
                    record
                )
            )
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if (
            record_type
            == "replay_lifecycle_retry_real_execution_read_only_repair_action_bundle_review"
        ):
            result = (
                validate_replay_lifecycle_retry_real_execution_read_only_repair_action_bundle_review(
                    record
                )
            )
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if record_type == "replay_lifecycle_retry_real_execution_repair_approval":
            result = validate_replay_lifecycle_retry_real_execution_repair_approval(
                record
            )
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if (
            record_type
            == "replay_lifecycle_retry_real_execution_repair_approval_transition"
        ):
            result = (
                validate_replay_lifecycle_retry_real_execution_repair_approval_transition(
                    record
                )
            )
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if record_type == "replay_lifecycle_retry_real_execution_repair_final_gate":
            result = validate_replay_lifecycle_retry_real_execution_repair_final_gate(
                record
            )
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if (
            record_type
            == "replay_lifecycle_retry_real_execution_repair_dry_run_envelope"
        ):
            result = (
                validate_replay_lifecycle_retry_real_execution_repair_dry_run_envelope(
                    record
                )
            )
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if record_type == "replay_lifecycle_retry_real_execution_repair_noop_result":
            result = validate_replay_lifecycle_retry_real_execution_repair_noop_result(
                record
            )
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if record_type == "replay_lifecycle_retry_real_execution_repair_noop_feedback":
            result = (
                validate_replay_lifecycle_retry_real_execution_repair_noop_feedback(
                    record
                )
            )
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if record_type == "replay_lifecycle_retry_real_execution_repair_readiness_gate":
            result = (
                validate_replay_lifecycle_retry_real_execution_repair_readiness_gate(
                    record
                )
            )
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if record_type == "replay_lifecycle_retry_guarded_repair_execution_result":
            result = validate_replay_lifecycle_retry_guarded_repair_execution_result(
                record
            )
            results.append(
                {
                    **result,
                    "record_id": _record_id(record),
                    "directive_id": _directive_id(record),
                    "source": record.get("source") or record.get("node_id"),
                }
            )
            continue

        if record_type == "replay_lifecycle_retry_post_repair_evidence_check":
            result = validate_replay_lifecycle_retry_post_repair_evidence_check(
                record
            )
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
    controlled_execution_gate_statuses: dict[str, int] = {}
    controlled_execution_gate_would_execute: dict[str, int] = {}
    controlled_execution_gate_would_execute_if_enabled: dict[str, int] = {}
    controlled_execution_gate_execution_performed: dict[str, int] = {}
    controlled_execution_gate_reasons: dict[str, int] = {}
    controlled_execution_mock_statuses: dict[str, int] = {}
    controlled_execution_mock_performed: dict[str, int] = {}
    controlled_execution_mock_subprocess_invoked: dict[str, int] = {}
    mock_summary_statuses: dict[str, int] = {}
    mock_summary_reasons: dict[str, int] = {}
    mock_summary_performed: dict[str, int] = {}
    mock_summary_subprocess_invoked: dict[str, int] = {}
    controlled_execution_mock_adapter: dict[str, int] = {}
    controlled_execution_mock_adapter_mode: dict[str, int] = {}
    controlled_execution_mock_adapter_result_statuses: dict[str, int] = {}
    controlled_execution_mock_adapter_subprocess_invoked: dict[str, int] = {}
    controlled_execution_mock_adapter_real_execution_enabled: dict[str, int] = {}
    controlled_execution_mock_adapter_payload_executed: dict[str, int] = {}
    controlled_execution_real_requested: dict[str, int] = {}
    controlled_execution_real_performed: dict[str, int] = {}
    controlled_execution_real_supported: dict[str, int] = {}
    controlled_execution_subprocess_invoked: dict[str, int] = {}
    real_preflight_statuses: dict[str, int] = {}
    real_preflight_reasons: dict[str, int] = {}
    real_preflight_requested: dict[str, int] = {}
    real_preflight_would_execute: dict[str, int] = {}
    real_preflight_execution_performed: dict[str, int] = {}
    real_preflight_subprocess_invoked: dict[str, int] = {}
    real_preflight_requires_explicit_pr: dict[str, int] = {}
    real_approval_statuses: dict[str, int] = {}
    real_approval_enabled: dict[str, int] = {}
    real_approval_subprocess_enabled: dict[str, int] = {}
    real_approval_execution_performed: dict[str, int] = {}
    real_approval_subprocess_invoked: dict[str, int] = {}
    real_approval_transition_statuses: dict[str, int] = {}
    real_approval_transition_enabled: dict[str, int] = {}
    real_approval_transition_subprocess_enabled: dict[str, int] = {}
    real_approval_transition_execution_performed: dict[str, int] = {}
    real_approval_transition_subprocess_invoked: dict[str, int] = {}
    real_final_gate_statuses: dict[str, int] = {}
    real_final_gate_would_execute: dict[str, int] = {}
    real_final_gate_ready: dict[str, int] = {}
    real_final_gate_real_execution_enabled: dict[str, int] = {}
    real_final_gate_subprocess_enabled: dict[str, int] = {}
    real_final_gate_execution_performed: dict[str, int] = {}
    real_final_gate_subprocess_invoked: dict[str, int] = {}
    real_dry_run_envelope_dry_run_only: dict[str, int] = {}
    real_dry_run_envelope_would_execute: dict[str, int] = {}
    real_dry_run_envelope_ready: dict[str, int] = {}
    real_dry_run_envelope_real_execution_enabled: dict[str, int] = {}
    real_dry_run_envelope_subprocess_enabled: dict[str, int] = {}
    real_dry_run_envelope_execution_performed: dict[str, int] = {}
    real_dry_run_envelope_subprocess_invoked: dict[str, int] = {}
    real_noop_result_noop_only: dict[str, int] = {}
    real_noop_result_rendered_command_executed: dict[str, int] = {}
    real_noop_result_dry_run_command_executed: dict[str, int] = {}
    real_noop_result_real_execution_enabled: dict[str, int] = {}
    real_noop_result_subprocess_invoked: dict[str, int] = {}
    real_noop_result_execution_performed: dict[str, int] = {}
    real_noop_result_exit_codes: dict[str, int] = {}
    real_read_only_promotion_statuses: dict[str, int] = {}
    real_read_only_promotion_candidates: dict[str, int] = {}
    real_read_only_promotion_command_parse_valid: dict[str, int] = {}
    real_read_only_promotion_stdout_marker_observed: dict[str, int] = {}
    real_read_only_promotion_noop_exit_codes: dict[str, int] = {}
    real_read_only_promotion_rendered_command_executed: dict[str, int] = {}
    real_read_only_promotion_dry_run_command_executed: dict[str, int] = {}
    real_read_only_promotion_real_execution_enabled: dict[str, int] = {}
    real_read_only_promotion_subprocess_invoked: dict[str, int] = {}
    real_read_only_promotion_execution_performed: dict[str, int] = {}
    real_read_only_final_gate_statuses: dict[str, int] = {}
    real_read_only_final_gate_preconditions_satisfied: dict[str, int] = {}
    real_read_only_final_gate_ready: dict[str, int] = {}
    real_read_only_final_gate_would_execute: dict[str, int] = {}
    real_read_only_final_gate_read_only_execution_enabled: dict[str, int] = {}
    real_read_only_final_gate_real_execution_enabled: dict[str, int] = {}
    real_read_only_final_gate_subprocess_enabled: dict[str, int] = {}
    real_read_only_final_gate_subprocess_invoked: dict[str, int] = {}
    real_read_only_final_gate_execution_performed: dict[str, int] = {}
    real_read_only_final_gate_rendered_command_executed: dict[str, int] = {}
    real_read_only_final_gate_dry_run_command_executed: dict[str, int] = {}
    real_read_only_approval_statuses: dict[str, int] = {}
    real_read_only_approval_read_only_execution_enabled: dict[str, int] = {}
    real_read_only_approval_real_execution_enabled: dict[str, int] = {}
    real_read_only_approval_subprocess_enabled: dict[str, int] = {}
    real_read_only_approval_subprocess_invoked: dict[str, int] = {}
    real_read_only_approval_execution_performed: dict[str, int] = {}
    real_read_only_approval_rendered_command_executed: dict[str, int] = {}
    real_read_only_approval_dry_run_command_executed: dict[str, int] = {}
    real_read_only_approval_transition_from_statuses: dict[str, int] = {}
    real_read_only_approval_transition_to_statuses: dict[str, int] = {}
    real_read_only_approval_transition_read_only_execution_enabled: dict[str, int] = {}
    real_read_only_approval_transition_real_execution_enabled: dict[str, int] = {}
    real_read_only_approval_transition_subprocess_enabled: dict[str, int] = {}
    real_read_only_approval_transition_subprocess_invoked: dict[str, int] = {}
    real_read_only_approval_transition_execution_performed: dict[str, int] = {}
    real_read_only_approval_transition_rendered_command_executed: dict[str, int] = {}
    real_read_only_approval_transition_dry_run_command_executed: dict[str, int] = {}
    real_read_only_readiness_gate_statuses: dict[str, int] = {}
    real_read_only_readiness_gate_satisfied: dict[str, int] = {}
    real_read_only_readiness_gate_ready: dict[str, int] = {}
    real_read_only_readiness_gate_read_only_execution_enabled: dict[str, int] = {}
    real_read_only_readiness_gate_real_execution_enabled: dict[str, int] = {}
    real_read_only_readiness_gate_subprocess_enabled: dict[str, int] = {}
    real_read_only_readiness_gate_subprocess_invoked: dict[str, int] = {}
    real_read_only_readiness_gate_execution_performed: dict[str, int] = {}
    real_read_only_readiness_gate_rendered_command_executed: dict[str, int] = {}
    real_read_only_readiness_gate_dry_run_command_executed: dict[str, int] = {}
    real_read_only_execution_result_statuses: dict[str, int] = {}
    real_read_only_execution_result_reasons: dict[str, int] = {}
    real_read_only_execution_result_exit_codes: dict[str, int] = {}
    real_read_only_execution_result_validation_reasons_empty: dict[str, int] = {}
    real_read_only_execution_result_operator_authorized: dict[str, int] = {}
    real_read_only_execution_result_allow_guarded: dict[str, int] = {}
    real_read_only_execution_result_read_only_execution_enabled: dict[str, int] = {}
    real_read_only_execution_result_real_execution_enabled: dict[str, int] = {}
    real_read_only_execution_result_subprocess_enabled: dict[str, int] = {}
    real_read_only_execution_result_subprocess_invoked: dict[str, int] = {}
    real_read_only_execution_result_execution_performed: dict[str, int] = {}
    real_read_only_execution_result_read_only_command_executed: dict[str, int] = {}
    real_read_only_execution_result_rendered_command_executed: dict[str, int] = {}
    real_read_only_execution_result_dry_run_command_executed: dict[str, int] = {}
    real_read_only_feedback_statuses: dict[str, int] = {}
    real_read_only_feedback_source_statuses: dict[str, int] = {}
    real_read_only_feedback_source_exit_codes: dict[str, int] = {}
    real_read_only_feedback_next_actions: dict[str, int] = {}
    real_read_only_feedback_execution_observed: dict[str, int] = {}
    real_read_only_feedback_failed: dict[str, int] = {}
    real_read_only_feedback_succeeded: dict[str, int] = {}
    real_read_only_feedback_rejected: dict[str, int] = {}
    real_read_only_feedback_real_execution_enabled: dict[str, int] = {}
    real_read_only_feedback_feedback_execution_performed: dict[str, int] = {}
    real_read_only_feedback_feedback_subprocess_invoked: dict[str, int] = {}
    real_read_only_feedback_execution_performed: dict[str, int] = {}
    real_read_only_feedback_subprocess_invoked: dict[str, int] = {}
    real_read_only_repair_plan_statuses: dict[str, int] = {}
    real_read_only_repair_plan_source_feedback_statuses: dict[str, int] = {}
    real_read_only_repair_plan_source_statuses: dict[str, int] = {}
    real_read_only_repair_plan_source_exit_codes: dict[str, int] = {}
    real_read_only_repair_plan_next_actions: dict[str, int] = {}
    real_read_only_repair_plan_item_counts: dict[str, int] = {}
    real_read_only_repair_plan_requires_operator_review: dict[str, int] = {}
    real_read_only_repair_plan_repair_execution_enabled: dict[str, int] = {}
    real_read_only_repair_plan_real_execution_enabled: dict[str, int] = {}
    real_read_only_repair_plan_subprocess_enabled: dict[str, int] = {}
    real_read_only_repair_plan_repair_execution_performed: dict[str, int] = {}
    real_read_only_repair_plan_repair_subprocess_invoked: dict[str, int] = {}
    real_read_only_repair_plan_execution_performed: dict[str, int] = {}
    real_read_only_repair_plan_subprocess_invoked: dict[str, int] = {}
    real_read_only_repair_action_bundle_statuses: dict[str, int] = {}
    real_read_only_repair_action_bundle_source_plan_statuses: dict[str, int] = {}
    real_read_only_repair_action_bundle_source_feedback_statuses: dict[str, int] = {}
    real_read_only_repair_action_bundle_source_statuses: dict[str, int] = {}
    real_read_only_repair_action_bundle_source_exit_codes: dict[str, int] = {}
    real_read_only_repair_action_bundle_next_actions: dict[str, int] = {}
    real_read_only_repair_action_bundle_item_counts: dict[str, int] = {}
    real_read_only_repair_action_bundle_source_item_counts: dict[str, int] = {}
    real_read_only_repair_action_bundle_requires_operator_review: dict[str, int] = {}
    real_read_only_repair_action_bundle_reviewed: dict[str, int] = {}
    real_read_only_repair_action_bundle_bundle_execution_enabled: dict[str, int] = {}
    real_read_only_repair_action_bundle_repair_execution_enabled: dict[str, int] = {}
    real_read_only_repair_action_bundle_real_execution_enabled: dict[str, int] = {}
    real_read_only_repair_action_bundle_subprocess_enabled: dict[str, int] = {}
    real_read_only_repair_action_bundle_bundle_execution_performed: dict[str, int] = {}
    real_read_only_repair_action_bundle_bundle_subprocess_invoked: dict[str, int] = {}
    real_read_only_repair_action_bundle_repair_execution_performed: dict[str, int] = {}
    real_read_only_repair_action_bundle_repair_subprocess_invoked: dict[str, int] = {}
    real_read_only_repair_action_bundle_execution_performed: dict[str, int] = {}
    real_read_only_repair_action_bundle_subprocess_invoked: dict[str, int] = {}
    real_read_only_repair_action_bundle_review_statuses: dict[str, int] = {}
    real_read_only_repair_action_bundle_review_source_bundle_statuses: dict[str, int] = {}
    real_read_only_repair_action_bundle_review_source_plan_statuses: dict[str, int] = {}
    real_read_only_repair_action_bundle_review_source_feedback_statuses: dict[str, int] = {}
    real_read_only_repair_action_bundle_review_source_statuses: dict[str, int] = {}
    real_read_only_repair_action_bundle_review_source_exit_codes: dict[str, int] = {}
    real_read_only_repair_action_bundle_review_source_item_counts: dict[str, int] = {}
    real_read_only_repair_action_bundle_review_next_actions: dict[str, int] = {}
    real_read_only_repair_action_bundle_review_operator_authorized: dict[str, int] = {}
    real_read_only_repair_action_bundle_review_requires_operator_review: dict[str, int] = {}
    real_read_only_repair_action_bundle_review_reviewed: dict[str, int] = {}
    real_read_only_repair_action_bundle_review_approved: dict[str, int] = {}
    real_read_only_repair_action_bundle_review_rejected: dict[str, int] = {}
    real_read_only_repair_action_bundle_review_bundle_execution_enabled: dict[str, int] = {}
    real_read_only_repair_action_bundle_review_repair_execution_enabled: dict[str, int] = {}
    real_read_only_repair_action_bundle_review_real_execution_enabled: dict[str, int] = {}
    real_read_only_repair_action_bundle_review_subprocess_enabled: dict[str, int] = {}
    real_read_only_repair_action_bundle_review_bundle_execution_performed: dict[str, int] = {}
    real_read_only_repair_action_bundle_review_bundle_subprocess_invoked: dict[str, int] = {}
    real_read_only_repair_action_bundle_review_repair_execution_performed: dict[str, int] = {}
    real_read_only_repair_action_bundle_review_repair_subprocess_invoked: dict[str, int] = {}
    real_read_only_repair_action_bundle_review_execution_performed: dict[str, int] = {}
    real_read_only_repair_action_bundle_review_subprocess_invoked: dict[str, int] = {}
    real_repair_approval_statuses: dict[str, int] = {}
    real_repair_approval_source_review_statuses: dict[str, int] = {}
    real_repair_approval_source_bundle_statuses: dict[str, int] = {}
    real_repair_approval_next_actions: dict[str, int] = {}
    real_repair_approval_operator_authorized: dict[str, int] = {}
    real_repair_approval_required: dict[str, int] = {}
    real_repair_approval_approved: dict[str, int] = {}
    real_repair_approval_rejected: dict[str, int] = {}
    real_repair_approval_bundle_execution_enabled: dict[str, int] = {}
    real_repair_approval_repair_execution_enabled: dict[str, int] = {}
    real_repair_approval_real_execution_enabled: dict[str, int] = {}
    real_repair_approval_subprocess_enabled: dict[str, int] = {}
    real_repair_approval_bundle_execution_performed: dict[str, int] = {}
    real_repair_approval_bundle_subprocess_invoked: dict[str, int] = {}
    real_repair_approval_repair_execution_performed: dict[str, int] = {}
    real_repair_approval_repair_subprocess_invoked: dict[str, int] = {}
    real_repair_approval_execution_performed: dict[str, int] = {}
    real_repair_approval_subprocess_invoked: dict[str, int] = {}
    real_repair_approval_transition_from_statuses: dict[str, int] = {}
    real_repair_approval_transition_to_statuses: dict[str, int] = {}
    real_repair_approval_transition_source_approval_statuses: dict[str, int] = {}
    real_repair_approval_transition_source_review_statuses: dict[str, int] = {}
    real_repair_approval_transition_next_actions: dict[str, int] = {}
    real_repair_approval_transition_operator_authorized: dict[str, int] = {}
    real_repair_approval_transition_required: dict[str, int] = {}
    real_repair_approval_transition_approved: dict[str, int] = {}
    real_repair_approval_transition_rejected: dict[str, int] = {}
    real_repair_approval_transition_bundle_execution_enabled: dict[str, int] = {}
    real_repair_approval_transition_repair_execution_enabled: dict[str, int] = {}
    real_repair_approval_transition_real_execution_enabled: dict[str, int] = {}
    real_repair_approval_transition_subprocess_enabled: dict[str, int] = {}
    real_repair_approval_transition_bundle_execution_performed: dict[str, int] = {}
    real_repair_approval_transition_bundle_subprocess_invoked: dict[str, int] = {}
    real_repair_approval_transition_repair_execution_performed: dict[str, int] = {}
    real_repair_approval_transition_repair_subprocess_invoked: dict[str, int] = {}
    real_repair_approval_transition_execution_performed: dict[str, int] = {}
    real_repair_approval_transition_subprocess_invoked: dict[str, int] = {}
    real_repair_final_gate_statuses: dict[str, int] = {}
    real_repair_final_gate_preconditions_satisfied: dict[str, int] = {}
    real_repair_final_gate_ready: dict[str, int] = {}
    real_repair_final_gate_would_execute: dict[str, int] = {}
    real_repair_final_gate_next_actions: dict[str, int] = {}
    real_repair_final_gate_operator_authorized: dict[str, int] = {}
    real_repair_final_gate_transition_approved: dict[str, int] = {}
    real_repair_final_gate_repair_execution_enabled: dict[str, int] = {}
    real_repair_final_gate_real_execution_enabled: dict[str, int] = {}
    real_repair_final_gate_subprocess_enabled: dict[str, int] = {}
    real_repair_final_gate_repair_execution_performed: dict[str, int] = {}
    real_repair_final_gate_repair_subprocess_invoked: dict[str, int] = {}
    real_repair_final_gate_execution_performed: dict[str, int] = {}
    real_repair_final_gate_subprocess_invoked: dict[str, int] = {}
    real_repair_dry_run_envelope_statuses: dict[str, int] = {}
    real_repair_dry_run_envelope_dry_run_only: dict[str, int] = {}
    real_repair_dry_run_envelope_modes: dict[str, int] = {}
    real_repair_dry_run_envelope_target_counts: dict[str, int] = {}
    real_repair_dry_run_envelope_source_gate_statuses: dict[str, int] = {}
    real_repair_dry_run_envelope_next_actions: dict[str, int] = {}
    real_repair_dry_run_envelope_operator_authorized: dict[str, int] = {}
    real_repair_dry_run_envelope_ready: dict[str, int] = {}
    real_repair_dry_run_envelope_would_execute: dict[str, int] = {}
    real_repair_dry_run_envelope_repair_execution_enabled: dict[str, int] = {}
    real_repair_dry_run_envelope_real_execution_enabled: dict[str, int] = {}
    real_repair_dry_run_envelope_subprocess_enabled: dict[str, int] = {}
    real_repair_dry_run_envelope_repair_execution_performed: dict[str, int] = {}
    real_repair_dry_run_envelope_repair_subprocess_invoked: dict[str, int] = {}
    real_repair_dry_run_envelope_execution_performed: dict[str, int] = {}
    real_repair_dry_run_envelope_subprocess_invoked: dict[str, int] = {}
    real_repair_noop_result_statuses: dict[str, int] = {}
    real_repair_noop_result_exit_codes: dict[str, int] = {}
    real_repair_noop_result_noop_only: dict[str, int] = {}
    real_repair_noop_result_stdout_marker_observed: dict[str, int] = {}
    real_repair_noop_result_source_envelope_statuses: dict[str, int] = {}
    real_repair_noop_result_source_target_counts: dict[str, int] = {}
    real_repair_noop_result_next_actions: dict[str, int] = {}
    real_repair_noop_result_operator_authorized: dict[str, int] = {}
    real_repair_noop_result_repair_actions_executed: dict[str, int] = {}
    real_repair_noop_result_repair_bundle_executed: dict[str, int] = {}
    real_repair_noop_result_repair_command_executed: dict[str, int] = {}
    real_repair_noop_result_rendered_command_executed: dict[str, int] = {}
    real_repair_noop_result_dry_run_command_executed: dict[str, int] = {}
    real_repair_noop_result_repair_execution_enabled: dict[str, int] = {}
    real_repair_noop_result_real_execution_enabled: dict[str, int] = {}
    real_repair_noop_result_subprocess_enabled: dict[str, int] = {}
    real_repair_noop_result_repair_execution_performed: dict[str, int] = {}
    real_repair_noop_result_repair_subprocess_invoked: dict[str, int] = {}
    real_repair_noop_result_execution_performed: dict[str, int] = {}
    real_repair_noop_result_subprocess_invoked: dict[str, int] = {}
    real_repair_noop_feedback_statuses: dict[str, int] = {}
    real_repair_noop_feedback_verified: dict[str, int] = {}
    real_repair_noop_feedback_path_can_proceed: dict[str, int] = {}
    real_repair_noop_feedback_next_gate_allowed: dict[str, int] = {}
    real_repair_noop_feedback_next_actions: dict[str, int] = {}
    real_repair_noop_feedback_source_noop_statuses: dict[str, int] = {}
    real_repair_noop_feedback_source_exit_codes: dict[str, int] = {}
    real_repair_noop_feedback_source_target_counts: dict[str, int] = {}
    real_repair_noop_feedback_source_execution_performed: dict[str, int] = {}
    real_repair_noop_feedback_source_subprocess_invoked: dict[str, int] = {}
    real_repair_noop_feedback_source_repair_actions_executed: dict[str, int] = {}
    real_repair_noop_feedback_source_repair_execution_enabled: dict[str, int] = {}
    real_repair_noop_feedback_source_repair_execution_performed: dict[str, int] = {}
    real_repair_noop_feedback_source_repair_subprocess_invoked: dict[str, int] = {}
    real_repair_noop_feedback_feedback_execution_performed: dict[str, int] = {}
    real_repair_noop_feedback_feedback_subprocess_invoked: dict[str, int] = {}
    real_repair_noop_feedback_repair_execution_enabled: dict[str, int] = {}
    real_repair_noop_feedback_real_execution_enabled: dict[str, int] = {}
    real_repair_noop_feedback_subprocess_enabled: dict[str, int] = {}
    real_repair_noop_feedback_repair_execution_performed: dict[str, int] = {}
    real_repair_noop_feedback_repair_subprocess_invoked: dict[str, int] = {}
    real_repair_noop_feedback_execution_performed: dict[str, int] = {}
    real_repair_noop_feedback_subprocess_invoked: dict[str, int] = {}
    real_repair_readiness_gate_statuses: dict[str, int] = {}
    real_repair_readiness_gate_satisfied: dict[str, int] = {}
    real_repair_readiness_gate_guarded_ready: dict[str, int] = {}
    real_repair_readiness_gate_ready_for_repair_execution: dict[str, int] = {}
    real_repair_readiness_gate_would_execute: dict[str, int] = {}
    real_repair_readiness_gate_next_actions: dict[str, int] = {}
    real_repair_readiness_gate_source_feedback_statuses: dict[str, int] = {}
    real_repair_readiness_gate_source_noop_statuses: dict[str, int] = {}
    real_repair_readiness_gate_source_exit_codes: dict[str, int] = {}
    real_repair_readiness_gate_source_target_counts: dict[str, int] = {}
    real_repair_readiness_gate_source_execution_performed: dict[str, int] = {}
    real_repair_readiness_gate_source_subprocess_invoked: dict[str, int] = {}
    real_repair_readiness_gate_source_repair_actions_executed: dict[str, int] = {}
    real_repair_readiness_gate_source_repair_execution_enabled: dict[str, int] = {}
    real_repair_readiness_gate_source_repair_execution_performed: dict[str, int] = {}
    real_repair_readiness_gate_source_repair_subprocess_invoked: dict[str, int] = {}
    real_repair_readiness_gate_repair_execution_enabled: dict[str, int] = {}
    real_repair_readiness_gate_real_execution_enabled: dict[str, int] = {}
    real_repair_readiness_gate_subprocess_enabled: dict[str, int] = {}
    real_repair_readiness_gate_repair_execution_performed: dict[str, int] = {}
    real_repair_readiness_gate_repair_subprocess_invoked: dict[str, int] = {}
    real_repair_readiness_gate_execution_performed: dict[str, int] = {}
    real_repair_readiness_gate_subprocess_invoked: dict[str, int] = {}
    guarded_repair_execution_statuses: dict[str, int] = {}
    guarded_repair_execution_allowed: dict[str, int] = {}
    guarded_repair_execution_marker_observed: dict[str, int] = {}
    guarded_repair_execution_exit_codes: dict[str, int] = {}
    guarded_repair_execution_target_counts: dict[str, int] = {}
    guarded_repair_execution_next_actions: dict[str, int] = {}
    guarded_repair_execution_source_gate_statuses: dict[str, int] = {}
    guarded_repair_execution_source_feedback_statuses: dict[str, int] = {}
    guarded_repair_execution_source_noop_statuses: dict[str, int] = {}
    guarded_repair_execution_source_ready_guarded: dict[str, int] = {}
    guarded_repair_execution_source_ready_repair: dict[str, int] = {}
    guarded_repair_execution_source_would_execute: dict[str, int] = {}
    guarded_repair_execution_source_execution_performed: dict[str, int] = {}
    guarded_repair_execution_source_subprocess_invoked: dict[str, int] = {}
    guarded_repair_execution_repair_actions_executed: dict[str, int] = {}
    guarded_repair_execution_repair_bundle_executed: dict[str, int] = {}
    guarded_repair_execution_repair_command_executed: dict[str, int] = {}
    guarded_repair_execution_rendered_command_executed: dict[str, int] = {}
    guarded_repair_execution_dry_run_command_executed: dict[str, int] = {}
    guarded_repair_execution_repair_execution_enabled: dict[str, int] = {}
    guarded_repair_execution_real_execution_enabled: dict[str, int] = {}
    guarded_repair_execution_subprocess_enabled: dict[str, int] = {}
    guarded_repair_execution_repair_execution_performed: dict[str, int] = {}
    guarded_repair_execution_repair_subprocess_invoked: dict[str, int] = {}
    guarded_repair_execution_execution_performed: dict[str, int] = {}
    guarded_repair_execution_subprocess_invoked: dict[str, int] = {}
    post_repair_evidence_statuses: dict[str, int] = {}
    post_repair_evidence_allowed: dict[str, int] = {}
    post_repair_evidence_enabled: dict[str, int] = {}
    post_repair_evidence_marker_observed: dict[str, int] = {}
    post_repair_evidence_exit_codes: dict[str, int] = {}
    post_repair_evidence_outcome_verified: dict[str, int] = {}
    post_repair_evidence_expected_counts: dict[str, int] = {}
    post_repair_evidence_verified_counts: dict[str, int] = {}
    post_repair_evidence_missing_counts: dict[str, int] = {}
    post_repair_evidence_unexpected_counts: dict[str, int] = {}
    post_repair_evidence_next_actions: dict[str, int] = {}
    post_repair_evidence_source_statuses: dict[str, int] = {}
    post_repair_evidence_source_allowed: dict[str, int] = {}
    post_repair_evidence_source_marker_observed: dict[str, int] = {}
    post_repair_evidence_source_exit_codes: dict[str, int] = {}
    post_repair_evidence_source_repair_actions_executed: dict[str, int] = {}
    post_repair_evidence_source_repair_execution_enabled: dict[str, int] = {}
    post_repair_evidence_source_real_execution_enabled: dict[str, int] = {}
    post_repair_evidence_source_repair_execution_performed: dict[str, int] = {}
    post_repair_evidence_source_repair_subprocess_invoked: dict[str, int] = {}
    post_repair_evidence_execution_performed: dict[str, int] = {}
    post_repair_evidence_subprocess_invoked: dict[str, int] = {}
    post_repair_evidence_repair_execution_enabled: dict[str, int] = {}
    post_repair_evidence_real_execution_enabled: dict[str, int] = {}
    post_repair_evidence_repair_execution_performed: dict[str, int] = {}
    post_repair_evidence_repair_subprocess_invoked: dict[str, int] = {}

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
            gate_status = str(item.get("gate_status") or "unknown").strip() or "unknown"
            gate_would_execute = str(bool(item.get("gate_would_execute"))).lower()
            gate_would_execute_if_enabled = str(
                bool(item.get("gate_would_execute_if_enabled"))
            ).lower()
            gate_execution_performed = str(
                bool(item.get("gate_execution_performed"))
            ).lower()

            controlled_execution_gate_statuses[gate_status] = (
                controlled_execution_gate_statuses.get(gate_status, 0) + 1
            )
            controlled_execution_gate_would_execute[gate_would_execute] = (
                controlled_execution_gate_would_execute.get(gate_would_execute, 0) + 1
            )
            controlled_execution_gate_would_execute_if_enabled[
                gate_would_execute_if_enabled
            ] = (
                controlled_execution_gate_would_execute_if_enabled.get(
                    gate_would_execute_if_enabled, 0
                )
                + 1
            )
            controlled_execution_gate_execution_performed[
                gate_execution_performed
            ] = (
                controlled_execution_gate_execution_performed.get(
                    gate_execution_performed, 0
                )
                + 1
            )

            gate_reasons = item.get("gate_reasons")
            if isinstance(gate_reasons, list):
                for reason_item in gate_reasons:
                    clean_reason = str(reason_item or "").strip()
                    if clean_reason:
                        controlled_execution_gate_reasons[clean_reason] = (
                            controlled_execution_gate_reasons.get(clean_reason, 0) + 1
                        )

            mock_status = str(item.get("mock_execution_status") or "none").strip() or "none"
            mock_performed = str(bool(item.get("mock_execution_performed"))).lower()
            mock_subprocess_invoked = str(
                bool(item.get("mock_subprocess_invoked"))
            ).lower()

            controlled_execution_mock_statuses[mock_status] = (
                controlled_execution_mock_statuses.get(mock_status, 0) + 1
            )
            controlled_execution_mock_performed[mock_performed] = (
                controlled_execution_mock_performed.get(mock_performed, 0) + 1
            )
            controlled_execution_mock_subprocess_invoked[mock_subprocess_invoked] = (
                controlled_execution_mock_subprocess_invoked.get(
                    mock_subprocess_invoked, 0
                )
                + 1
            )

            mock_adapter = str(item.get("mock_adapter") or "none").strip() or "none"
            mock_adapter_mode = (
                str(item.get("mock_adapter_mode") or "none").strip() or "none"
            )
            mock_adapter_result_status = (
                str(item.get("mock_adapter_result_status") or "none").strip()
                or "none"
            )
            mock_adapter_subprocess_invoked = str(
                bool(item.get("mock_adapter_subprocess_invoked"))
            ).lower()
            mock_adapter_real_execution_enabled = str(
                bool(item.get("mock_adapter_real_execution_enabled"))
            ).lower()
            mock_adapter_payload_executed = str(
                bool(item.get("mock_adapter_payload_executed"))
            ).lower()

            controlled_execution_mock_adapter[mock_adapter] = (
                controlled_execution_mock_adapter.get(mock_adapter, 0) + 1
            )
            controlled_execution_mock_adapter_mode[mock_adapter_mode] = (
                controlled_execution_mock_adapter_mode.get(mock_adapter_mode, 0) + 1
            )
            controlled_execution_mock_adapter_result_statuses[
                mock_adapter_result_status
            ] = (
                controlled_execution_mock_adapter_result_statuses.get(
                    mock_adapter_result_status, 0
                )
                + 1
            )
            controlled_execution_mock_adapter_subprocess_invoked[
                mock_adapter_subprocess_invoked
            ] = (
                controlled_execution_mock_adapter_subprocess_invoked.get(
                    mock_adapter_subprocess_invoked, 0
                )
                + 1
            )
            controlled_execution_mock_adapter_real_execution_enabled[
                mock_adapter_real_execution_enabled
            ] = (
                controlled_execution_mock_adapter_real_execution_enabled.get(
                    mock_adapter_real_execution_enabled, 0
                )
                + 1
            )
            controlled_execution_mock_adapter_payload_executed[
                mock_adapter_payload_executed
            ] = (
                controlled_execution_mock_adapter_payload_executed.get(
                    mock_adapter_payload_executed, 0
                )
                + 1
            )
            real_requested = str(bool(item.get("real_execution_requested"))).lower()
            real_performed = str(bool(item.get("real_execution_performed"))).lower()
            real_supported = str(bool(item.get("real_execution_supported"))).lower()
            subprocess_invoked = str(bool(item.get("subprocess_invoked"))).lower()

            controlled_execution_real_requested[real_requested] = (
                controlled_execution_real_requested.get(real_requested, 0) + 1
            )
            controlled_execution_real_performed[real_performed] = (
                controlled_execution_real_performed.get(real_performed, 0) + 1
            )
            controlled_execution_real_supported[real_supported] = (
                controlled_execution_real_supported.get(real_supported, 0) + 1
            )
            controlled_execution_subprocess_invoked[subprocess_invoked] = (
                controlled_execution_subprocess_invoked.get(subprocess_invoked, 0) + 1
            )

        if record_type == "replay_lifecycle_retry_mock_execution_summary":
            status = str(item.get("status") or "unknown").strip() or "unknown"
            reason = str(item.get("reason") or "unknown").strip() or "unknown"
            performed = str(bool(item.get("mock_performed"))).lower()
            subprocess_invoked = str(bool(item.get("subprocess_invoked"))).lower()

            mock_summary_statuses[status] = mock_summary_statuses.get(status, 0) + 1
            mock_summary_reasons[reason] = mock_summary_reasons.get(reason, 0) + 1
            mock_summary_performed[performed] = mock_summary_performed.get(performed, 0) + 1
            mock_summary_subprocess_invoked[subprocess_invoked] = (
                mock_summary_subprocess_invoked.get(subprocess_invoked, 0) + 1
            )

        if item.get("record_type") == "replay_lifecycle_retry_real_execution_preflight":
            status_value = str(item.get("status") or "unknown")
            reason_value = str(item.get("reason") or "unknown")
            real_preflight_statuses[status_value] = real_preflight_statuses.get(status_value, 0) + 1
            real_preflight_reasons[reason_value] = real_preflight_reasons.get(reason_value, 0) + 1

            for target, key in (
                (real_preflight_requested, "real_execution_requested"),
                (real_preflight_would_execute, "would_execute"),
                (real_preflight_execution_performed, "execution_performed"),
                (real_preflight_subprocess_invoked, "subprocess_invoked"),
                (real_preflight_requires_explicit_pr, "real_adapter_requires_explicit_pr"),
            ):
                value = str(bool(item.get(key))).lower()
                target[value] = target.get(value, 0) + 1

        if record_type == "replay_lifecycle_retry_real_execution_approval":
            status_value = str(item.get("approval_status") or "unknown").strip() or "unknown"
            real_approval_statuses[status_value] = real_approval_statuses.get(status_value, 0) + 1

            for target, key in (
                (real_approval_enabled, "real_execution_enabled"),
                (real_approval_subprocess_enabled, "subprocess_enabled"),
                (real_approval_execution_performed, "execution_performed"),
                (real_approval_subprocess_invoked, "subprocess_invoked"),
            ):
                value = str(bool(item.get(key))).lower()
                target[value] = target.get(value, 0) + 1

        if record_type == "replay_lifecycle_retry_real_execution_approval_transition":
            to_status = str(item.get("to_status") or "unknown").strip() or "unknown"
            real_approval_transition_statuses[to_status] = (
                real_approval_transition_statuses.get(to_status, 0) + 1
            )

            for target, key in (
                (real_approval_transition_enabled, "real_execution_enabled"),
                (
                    real_approval_transition_subprocess_enabled,
                    "subprocess_enabled",
                ),
                (
                    real_approval_transition_execution_performed,
                    "execution_performed",
                ),
                (
                    real_approval_transition_subprocess_invoked,
                    "subprocess_invoked",
                ),
            ):
                value = str(bool(item.get(key))).lower()
                target[value] = target.get(value, 0) + 1

        if record_type == "replay_lifecycle_retry_real_execution_final_gate":
            gate_status = str(item.get("gate_status") or "unknown").strip() or "unknown"
            real_final_gate_statuses[gate_status] = (
                real_final_gate_statuses.get(gate_status, 0) + 1
            )

            for target, key in (
                (real_final_gate_would_execute, "would_execute"),
                (real_final_gate_ready, "ready_for_real_execution"),
                (real_final_gate_real_execution_enabled, "real_execution_enabled"),
                (real_final_gate_subprocess_enabled, "subprocess_enabled"),
                (real_final_gate_execution_performed, "execution_performed"),
                (real_final_gate_subprocess_invoked, "subprocess_invoked"),
            ):
                value = str(bool(item.get(key))).lower()
                target[value] = target.get(value, 0) + 1

        if record_type == "replay_lifecycle_retry_real_execution_dry_run_envelope":
            for target, key in (
                (real_dry_run_envelope_dry_run_only, "dry_run_only"),
                (real_dry_run_envelope_would_execute, "would_execute"),
                (real_dry_run_envelope_ready, "ready_for_real_execution"),
                (
                    real_dry_run_envelope_real_execution_enabled,
                    "real_execution_enabled",
                ),
                (real_dry_run_envelope_subprocess_enabled, "subprocess_enabled"),
                (real_dry_run_envelope_execution_performed, "execution_performed"),
                (real_dry_run_envelope_subprocess_invoked, "subprocess_invoked"),
            ):
                value = str(bool(item.get(key))).lower()
                target[value] = target.get(value, 0) + 1
        
        if record_type == "replay_lifecycle_retry_real_execution_noop_result":
            for target, key in (
                (real_noop_result_noop_only, "noop_only"),
                (
                    real_noop_result_rendered_command_executed,
                    "rendered_command_executed",
                ),
                (
                    real_noop_result_dry_run_command_executed,
                    "dry_run_envelope_command_executed",
                ),
                (real_noop_result_real_execution_enabled, "real_execution_enabled"),
                (real_noop_result_subprocess_invoked, "subprocess_invoked"),
                (real_noop_result_execution_performed, "execution_performed"),
            ):
                value = str(bool(item.get(key))).lower()
                target[value] = target.get(value, 0) + 1

            exit_code = str(item.get("exit_code"))
            real_noop_result_exit_codes[exit_code] = (
                real_noop_result_exit_codes.get(exit_code, 0) + 1
            )
        
        if record_type == "replay_lifecycle_retry_real_execution_read_only_promotion":
            status = str(item.get("promotion_status") or "unknown").strip() or "unknown"
            real_read_only_promotion_statuses[status] = (
                real_read_only_promotion_statuses.get(status, 0) + 1
            )

            for target, key in (
                (real_read_only_promotion_candidates, "read_only_candidate"),
                (
                    real_read_only_promotion_command_parse_valid,
                    "command_parse_valid",
                ),
                (
                    real_read_only_promotion_stdout_marker_observed,
                    "stdout_marker_observed",
                ),
                (
                    real_read_only_promotion_rendered_command_executed,
                    "rendered_command_executed",
                ),
                (
                    real_read_only_promotion_dry_run_command_executed,
                    "dry_run_envelope_command_executed",
                ),
                (
                    real_read_only_promotion_real_execution_enabled,
                    "real_execution_enabled",
                ),
                (
                    real_read_only_promotion_subprocess_invoked,
                    "subprocess_invoked",
                ),
                (
                    real_read_only_promotion_execution_performed,
                    "execution_performed",
                ),
            ):
                value = str(bool(item.get(key))).lower()
                target[value] = target.get(value, 0) + 1

            exit_code = str(item.get("noop_exit_code"))
            real_read_only_promotion_noop_exit_codes[exit_code] = (
                real_read_only_promotion_noop_exit_codes.get(exit_code, 0) + 1
            )

        if record_type == "replay_lifecycle_retry_real_execution_read_only_final_gate":
            status = str(item.get("gate_status") or "unknown").strip() or "unknown"
            real_read_only_final_gate_statuses[status] = (
                real_read_only_final_gate_statuses.get(status, 0) + 1
            )

            for target, key in (
                (
                    real_read_only_final_gate_preconditions_satisfied,
                    "promotion_preconditions_satisfied",
                ),
                (
                    real_read_only_final_gate_ready,
                    "ready_for_read_only_execution",
                ),
                (real_read_only_final_gate_would_execute, "would_execute"),
                (
                    real_read_only_final_gate_read_only_execution_enabled,
                    "read_only_execution_enabled",
                ),
                (
                    real_read_only_final_gate_real_execution_enabled,
                    "real_execution_enabled",
                ),
                (
                    real_read_only_final_gate_subprocess_enabled,
                    "subprocess_enabled",
                ),
                (
                    real_read_only_final_gate_subprocess_invoked,
                    "subprocess_invoked",
                ),
                (
                    real_read_only_final_gate_execution_performed,
                    "execution_performed",
                ),
                (
                    real_read_only_final_gate_rendered_command_executed,
                    "rendered_command_executed",
                ),
                (
                    real_read_only_final_gate_dry_run_command_executed,
                    "dry_run_envelope_command_executed",
                ),
            ):
                value = str(bool(item.get(key))).lower()
                target[value] = target.get(value, 0) + 1

        if record_type == "replay_lifecycle_retry_real_execution_read_only_approval":
            status = str(item.get("approval_status") or "unknown").strip() or "unknown"
            real_read_only_approval_statuses[status] = (
                real_read_only_approval_statuses.get(status, 0) + 1
            )

            for target, key in (
                (
                    real_read_only_approval_read_only_execution_enabled,
                    "read_only_execution_enabled",
                ),
                (
                    real_read_only_approval_real_execution_enabled,
                    "real_execution_enabled",
                ),
                (
                    real_read_only_approval_subprocess_enabled,
                    "subprocess_enabled",
                ),
                (
                    real_read_only_approval_subprocess_invoked,
                    "subprocess_invoked",
                ),
                (
                    real_read_only_approval_execution_performed,
                    "execution_performed",
                ),
                (
                    real_read_only_approval_rendered_command_executed,
                    "rendered_command_executed",
                ),
                (
                    real_read_only_approval_dry_run_command_executed,
                    "dry_run_envelope_command_executed",
                ),
            ):
                value = str(bool(item.get(key))).lower()
                target[value] = target.get(value, 0) + 1

        if (
            record_type
            == "replay_lifecycle_retry_real_execution_read_only_approval_transition"
        ):
            from_status = str(item.get("from_status") or "unknown").strip() or "unknown"
            to_status = str(item.get("to_status") or "unknown").strip() or "unknown"

            real_read_only_approval_transition_from_statuses[from_status] = (
                real_read_only_approval_transition_from_statuses.get(from_status, 0)
                + 1
            )
            real_read_only_approval_transition_to_statuses[to_status] = (
                real_read_only_approval_transition_to_statuses.get(to_status, 0)
                + 1
            )

            for target, key in (
                (
                    real_read_only_approval_transition_read_only_execution_enabled,
                    "read_only_execution_enabled",
                ),
                (
                    real_read_only_approval_transition_real_execution_enabled,
                    "real_execution_enabled",
                ),
                (
                    real_read_only_approval_transition_subprocess_enabled,
                    "subprocess_enabled",
                ),
                (
                    real_read_only_approval_transition_subprocess_invoked,
                    "subprocess_invoked",
                ),
                (
                    real_read_only_approval_transition_execution_performed,
                    "execution_performed",
                ),
                (
                    real_read_only_approval_transition_rendered_command_executed,
                    "rendered_command_executed",
                ),
                (
                    real_read_only_approval_transition_dry_run_command_executed,
                    "dry_run_envelope_command_executed",
                ),
            ):
                value = str(bool(item.get(key))).lower()
                target[value] = target.get(value, 0) + 1
        
        if (
            record_type
            == "replay_lifecycle_retry_real_execution_read_only_readiness_gate"
        ):
            status = str(item.get("gate_status") or "unknown").strip() or "unknown"
            real_read_only_readiness_gate_statuses[status] = (
                real_read_only_readiness_gate_statuses.get(status, 0) + 1
            )

            for target, key in (
                (
                    real_read_only_readiness_gate_satisfied,
                    "read_only_readiness_satisfied",
                ),
                (
                    real_read_only_readiness_gate_ready,
                    "ready_for_guarded_read_only_execution",
                ),
                (
                    real_read_only_readiness_gate_read_only_execution_enabled,
                    "read_only_execution_enabled",
                ),
                (
                    real_read_only_readiness_gate_real_execution_enabled,
                    "real_execution_enabled",
                ),
                (
                    real_read_only_readiness_gate_subprocess_enabled,
                    "subprocess_enabled",
                ),
                (
                    real_read_only_readiness_gate_subprocess_invoked,
                    "subprocess_invoked",
                ),
                (
                    real_read_only_readiness_gate_execution_performed,
                    "execution_performed",
                ),
                (
                    real_read_only_readiness_gate_rendered_command_executed,
                    "rendered_command_executed",
                ),
                (
                    real_read_only_readiness_gate_dry_run_command_executed,
                    "dry_run_envelope_command_executed",
                ),
            ):
                value = str(bool(item.get(key))).lower()
                target[value] = target.get(value, 0) + 1
        
        if (
            record_type
            == "replay_lifecycle_retry_real_execution_read_only_execution_result"
        ):
            status = str(item.get("status") or "unknown").strip() or "unknown"
            reason = str(item.get("reason") or "unknown").strip() or "unknown"
            exit_code = item.get("exit_code")
            exit_code_key = "none" if exit_code is None else str(exit_code)

            real_read_only_execution_result_statuses[status] = (
                real_read_only_execution_result_statuses.get(status, 0) + 1
            )
            real_read_only_execution_result_reasons[reason] = (
                real_read_only_execution_result_reasons.get(reason, 0) + 1
            )
            real_read_only_execution_result_exit_codes[exit_code_key] = (
                real_read_only_execution_result_exit_codes.get(exit_code_key, 0) + 1
            )

            validation_reasons = item.get("validation_reasons")
            validation_empty = isinstance(validation_reasons, list) and not validation_reasons
            key = str(validation_empty).lower()
            real_read_only_execution_result_validation_reasons_empty[key] = (
                real_read_only_execution_result_validation_reasons_empty.get(key, 0)
                + 1
            )

            for target, key_name in (
                (
                    real_read_only_execution_result_operator_authorized,
                    "operator_authorized",
                ),
                (
                    real_read_only_execution_result_allow_guarded,
                    "allow_guarded_read_only_execution",
                ),
                (
                    real_read_only_execution_result_read_only_execution_enabled,
                    "read_only_execution_enabled",
                ),
                (
                    real_read_only_execution_result_real_execution_enabled,
                    "real_execution_enabled",
                ),
                (
                    real_read_only_execution_result_subprocess_enabled,
                    "subprocess_enabled",
                ),
                (
                    real_read_only_execution_result_subprocess_invoked,
                    "subprocess_invoked",
                ),
                (
                    real_read_only_execution_result_execution_performed,
                    "execution_performed",
                ),
                (
                    real_read_only_execution_result_read_only_command_executed,
                    "read_only_command_executed",
                ),
                (
                    real_read_only_execution_result_rendered_command_executed,
                    "rendered_command_executed",
                ),
                (
                    real_read_only_execution_result_dry_run_command_executed,
                    "dry_run_envelope_command_executed",
                ),
            ):
                value = str(bool(item.get(key_name))).lower()
                target[value] = target.get(value, 0) + 1
        
        if record_type == "replay_lifecycle_retry_real_execution_read_only_feedback":
            feedback_status = str(item.get("feedback_status") or "unknown").strip() or "unknown"
            source_status = str(item.get("source_status") or "unknown").strip() or "unknown"
            next_action = str(item.get("recommended_next_action") or "unknown").strip() or "unknown"
            exit_code = item.get("source_exit_code")
            exit_code_key = "none" if exit_code is None else str(exit_code)

            real_read_only_feedback_statuses[feedback_status] = (
                real_read_only_feedback_statuses.get(feedback_status, 0) + 1
            )
            real_read_only_feedback_source_statuses[source_status] = (
                real_read_only_feedback_source_statuses.get(source_status, 0) + 1
            )
            real_read_only_feedback_next_actions[next_action] = (
                real_read_only_feedback_next_actions.get(next_action, 0) + 1
            )
            real_read_only_feedback_source_exit_codes[exit_code_key] = (
                real_read_only_feedback_source_exit_codes.get(exit_code_key, 0) + 1
            )

            for target, key_name in (
                (real_read_only_feedback_execution_observed, "read_only_execution_was_observed"),
                (real_read_only_feedback_failed, "read_only_execution_failed"),
                (real_read_only_feedback_succeeded, "read_only_execution_succeeded"),
                (real_read_only_feedback_rejected, "read_only_execution_rejected"),
                (real_read_only_feedback_real_execution_enabled, "real_execution_enabled"),
                (real_read_only_feedback_feedback_execution_performed, "feedback_execution_performed"),
                (real_read_only_feedback_feedback_subprocess_invoked, "feedback_subprocess_invoked"),
                (real_read_only_feedback_execution_performed, "execution_performed"),
                (real_read_only_feedback_subprocess_invoked, "subprocess_invoked"),
            ):
                value = str(bool(item.get(key_name))).lower()
                target[value] = target.get(value, 0) + 1

        if record_type == "replay_lifecycle_retry_real_execution_read_only_repair_plan":
            status = str(item.get("repair_plan_status") or "unknown").strip() or "unknown"
            source_feedback_status = (
                str(item.get("source_feedback_status") or "unknown").strip()
                or "unknown"
            )
            source_status = str(item.get("source_status") or "unknown").strip() or "unknown"
            next_action = (
                str(item.get("recommended_next_action") or "unknown").strip()
                or "unknown"
            )
            exit_code = item.get("source_exit_code")
            exit_code_key = "none" if exit_code is None else str(exit_code)
            item_count = item.get("repair_item_count")
            item_count_key = str(item_count if isinstance(item_count, int) else "unknown")

            real_read_only_repair_plan_statuses[status] = (
                real_read_only_repair_plan_statuses.get(status, 0) + 1
            )
            real_read_only_repair_plan_source_feedback_statuses[
                source_feedback_status
            ] = (
                real_read_only_repair_plan_source_feedback_statuses.get(
                    source_feedback_status, 0
                )
                + 1
            )
            real_read_only_repair_plan_source_statuses[source_status] = (
                real_read_only_repair_plan_source_statuses.get(source_status, 0) + 1
            )
            real_read_only_repair_plan_source_exit_codes[exit_code_key] = (
                real_read_only_repair_plan_source_exit_codes.get(exit_code_key, 0) + 1
            )
            real_read_only_repair_plan_next_actions[next_action] = (
                real_read_only_repair_plan_next_actions.get(next_action, 0) + 1
            )
            real_read_only_repair_plan_item_counts[item_count_key] = (
                real_read_only_repair_plan_item_counts.get(item_count_key, 0) + 1
            )

            for target, key_name in (
                (
                    real_read_only_repair_plan_requires_operator_review,
                    "requires_operator_review",
                ),
                (
                    real_read_only_repair_plan_repair_execution_enabled,
                    "repair_execution_enabled",
                ),
                (
                    real_read_only_repair_plan_real_execution_enabled,
                    "real_execution_enabled",
                ),
                (
                    real_read_only_repair_plan_subprocess_enabled,
                    "subprocess_enabled",
                ),
                (
                    real_read_only_repair_plan_repair_execution_performed,
                    "repair_execution_performed",
                ),
                (
                    real_read_only_repair_plan_repair_subprocess_invoked,
                    "repair_subprocess_invoked",
                ),
                (
                    real_read_only_repair_plan_execution_performed,
                    "execution_performed",
                ),
                (
                    real_read_only_repair_plan_subprocess_invoked,
                    "subprocess_invoked",
                ),
            ):
                value = str(bool(item.get(key_name))).lower()
                target[value] = target.get(value, 0) + 1
            
        if (
            record_type
            == "replay_lifecycle_retry_real_execution_read_only_repair_action_bundle"
        ):
            status = str(item.get("bundle_status") or "unknown").strip() or "unknown"
            source_plan_status = (
                str(item.get("source_repair_plan_status") or "unknown").strip()
                or "unknown"
            )
            source_feedback_status = (
                str(item.get("source_feedback_status") or "unknown").strip()
                or "unknown"
            )
            source_status = str(item.get("source_status") or "unknown").strip() or "unknown"
            next_action = (
                str(item.get("recommended_next_action") or "unknown").strip()
                or "unknown"
            )
            exit_code = item.get("source_exit_code")
            exit_code_key = "none" if exit_code is None else str(exit_code)
            bundle_item_count = item.get("bundle_item_count")
            bundle_item_count_key = str(
                bundle_item_count if isinstance(bundle_item_count, int) else "unknown"
            )
            source_item_count = item.get("source_repair_item_count")
            source_item_count_key = str(
                source_item_count if isinstance(source_item_count, int) else "unknown"
            )

            real_read_only_repair_action_bundle_statuses[status] = (
                real_read_only_repair_action_bundle_statuses.get(status, 0) + 1
            )
            real_read_only_repair_action_bundle_source_plan_statuses[
                source_plan_status
            ] = (
                real_read_only_repair_action_bundle_source_plan_statuses.get(
                    source_plan_status, 0
                )
                + 1
            )
            real_read_only_repair_action_bundle_source_feedback_statuses[
                source_feedback_status
            ] = (
                real_read_only_repair_action_bundle_source_feedback_statuses.get(
                    source_feedback_status, 0
                )
                + 1
            )
            real_read_only_repair_action_bundle_source_statuses[source_status] = (
                real_read_only_repair_action_bundle_source_statuses.get(
                    source_status, 0
                )
                + 1
            )
            real_read_only_repair_action_bundle_source_exit_codes[exit_code_key] = (
                real_read_only_repair_action_bundle_source_exit_codes.get(
                    exit_code_key, 0
                )
                + 1
            )
            real_read_only_repair_action_bundle_next_actions[next_action] = (
                real_read_only_repair_action_bundle_next_actions.get(
                    next_action, 0
                )
                + 1
            )
            real_read_only_repair_action_bundle_item_counts[bundle_item_count_key] = (
                real_read_only_repair_action_bundle_item_counts.get(
                    bundle_item_count_key, 0
                )
                + 1
            )
            real_read_only_repair_action_bundle_source_item_counts[
                source_item_count_key
            ] = (
                real_read_only_repair_action_bundle_source_item_counts.get(
                    source_item_count_key, 0
                )
                + 1
            )

            for target, key_name in (
                (
                    real_read_only_repair_action_bundle_requires_operator_review,
                    "requires_operator_review",
                ),
                (real_read_only_repair_action_bundle_reviewed, "bundle_reviewed"),
                (
                    real_read_only_repair_action_bundle_bundle_execution_enabled,
                    "bundle_execution_enabled",
                ),
                (
                    real_read_only_repair_action_bundle_repair_execution_enabled,
                    "repair_execution_enabled",
                ),
                (
                    real_read_only_repair_action_bundle_real_execution_enabled,
                    "real_execution_enabled",
                ),
                (
                    real_read_only_repair_action_bundle_subprocess_enabled,
                    "subprocess_enabled",
                ),
                (
                    real_read_only_repair_action_bundle_bundle_execution_performed,
                    "bundle_execution_performed",
                ),
                (
                    real_read_only_repair_action_bundle_bundle_subprocess_invoked,
                    "bundle_subprocess_invoked",
                ),
                (
                    real_read_only_repair_action_bundle_repair_execution_performed,
                    "repair_execution_performed",
                ),
                (
                    real_read_only_repair_action_bundle_repair_subprocess_invoked,
                    "repair_subprocess_invoked",
                ),
                (
                    real_read_only_repair_action_bundle_execution_performed,
                    "execution_performed",
                ),
                (
                    real_read_only_repair_action_bundle_subprocess_invoked,
                    "subprocess_invoked",
                ),
            ):
                value = str(bool(item.get(key_name))).lower()
                target[value] = target.get(value, 0) + 1

        if (
            record_type
            == "replay_lifecycle_retry_real_execution_read_only_repair_action_bundle_review"
        ):
            status = str(item.get("review_status") or "unknown").strip() or "unknown"
            source_bundle_status = (
                str(item.get("source_bundle_status") or "unknown").strip()
                or "unknown"
            )
            source_plan_status = (
                str(item.get("source_repair_plan_status") or "unknown").strip()
                or "unknown"
            )
            source_feedback_status = (
                str(item.get("source_feedback_status") or "unknown").strip()
                or "unknown"
            )
            source_status = str(item.get("source_status") or "unknown").strip() or "unknown"
            next_action = (
                str(item.get("recommended_next_action") or "unknown").strip()
                or "unknown"
            )
            exit_code = item.get("source_exit_code")
            exit_code_key = "none" if exit_code is None else str(exit_code)
            source_item_count = item.get("source_bundle_item_count")
            source_item_count_key = str(
                source_item_count if isinstance(source_item_count, int) else "unknown"
            )

            real_read_only_repair_action_bundle_review_statuses[status] = (
                real_read_only_repair_action_bundle_review_statuses.get(status, 0) + 1
            )
            real_read_only_repair_action_bundle_review_source_bundle_statuses[
                source_bundle_status
            ] = (
                real_read_only_repair_action_bundle_review_source_bundle_statuses.get(
                    source_bundle_status, 0
                )
                + 1
            )
            real_read_only_repair_action_bundle_review_source_plan_statuses[
                source_plan_status
            ] = (
                real_read_only_repair_action_bundle_review_source_plan_statuses.get(
                    source_plan_status, 0
                )
                + 1
            )
            real_read_only_repair_action_bundle_review_source_feedback_statuses[
                source_feedback_status
            ] = (
                real_read_only_repair_action_bundle_review_source_feedback_statuses.get(
                    source_feedback_status, 0
                )
                + 1
            )
            real_read_only_repair_action_bundle_review_source_statuses[
                source_status
            ] = (
                real_read_only_repair_action_bundle_review_source_statuses.get(
                    source_status, 0
                )
                + 1
            )
            real_read_only_repair_action_bundle_review_source_exit_codes[
                exit_code_key
            ] = (
                real_read_only_repair_action_bundle_review_source_exit_codes.get(
                    exit_code_key, 0
                )
                + 1
            )
            real_read_only_repair_action_bundle_review_source_item_counts[
                source_item_count_key
            ] = (
                real_read_only_repair_action_bundle_review_source_item_counts.get(
                    source_item_count_key, 0
                )
                + 1
            )
            real_read_only_repair_action_bundle_review_next_actions[next_action] = (
                real_read_only_repair_action_bundle_review_next_actions.get(
                    next_action, 0
                )
                + 1
            )

            for target, key_name in (
                (
                    real_read_only_repair_action_bundle_review_operator_authorized,
                    "operator_authorized",
                ),
                (
                    real_read_only_repair_action_bundle_review_requires_operator_review,
                    "requires_operator_review",
                ),
                (
                    real_read_only_repair_action_bundle_review_reviewed,
                    "reviewed",
                ),
                (
                    real_read_only_repair_action_bundle_review_approved,
                    "review_approved",
                ),
                (
                    real_read_only_repair_action_bundle_review_rejected,
                    "review_rejected",
                ),
                (
                    real_read_only_repair_action_bundle_review_bundle_execution_enabled,
                    "bundle_execution_enabled",
                ),
                (
                    real_read_only_repair_action_bundle_review_repair_execution_enabled,
                    "repair_execution_enabled",
                ),
                (
                    real_read_only_repair_action_bundle_review_real_execution_enabled,
                    "real_execution_enabled",
                ),
                (
                    real_read_only_repair_action_bundle_review_subprocess_enabled,
                    "subprocess_enabled",
                ),
                (
                    real_read_only_repair_action_bundle_review_bundle_execution_performed,
                    "bundle_execution_performed",
                ),
                (
                    real_read_only_repair_action_bundle_review_bundle_subprocess_invoked,
                    "bundle_subprocess_invoked",
                ),
                (
                    real_read_only_repair_action_bundle_review_repair_execution_performed,
                    "repair_execution_performed",
                ),
                (
                    real_read_only_repair_action_bundle_review_repair_subprocess_invoked,
                    "repair_subprocess_invoked",
                ),
                (
                    real_read_only_repair_action_bundle_review_execution_performed,
                    "execution_performed",
                ),
                (
                    real_read_only_repair_action_bundle_review_subprocess_invoked,
                    "subprocess_invoked",
                ),
            ):
                value = str(bool(item.get(key_name))).lower()
                target[value] = target.get(value, 0) + 1
        
        if record_type == "replay_lifecycle_retry_real_execution_repair_approval":
            status = str(item.get("approval_status") or "unknown").strip() or "unknown"
            source_review_status = (
                str(item.get("source_review_status") or "unknown").strip()
                or "unknown"
            )
            source_bundle_status = (
                str(item.get("source_bundle_status") or "unknown").strip()
                or "unknown"
            )
            next_action = (
                str(item.get("recommended_next_action") or "unknown").strip()
                or "unknown"
            )

            real_repair_approval_statuses[status] = (
                real_repair_approval_statuses.get(status, 0) + 1
            )
            real_repair_approval_source_review_statuses[source_review_status] = (
                real_repair_approval_source_review_statuses.get(
                    source_review_status, 0
                )
                + 1
            )
            real_repair_approval_source_bundle_statuses[source_bundle_status] = (
                real_repair_approval_source_bundle_statuses.get(
                    source_bundle_status, 0
                )
                + 1
            )
            real_repair_approval_next_actions[next_action] = (
                real_repair_approval_next_actions.get(next_action, 0) + 1
            )

            for target, key_name in (
                (real_repair_approval_operator_authorized, "operator_authorized"),
                (
                    real_repair_approval_required,
                    "repair_execution_approval_required",
                ),
                (real_repair_approval_approved, "repair_execution_approved"),
                (real_repair_approval_rejected, "repair_execution_rejected"),
                (
                    real_repair_approval_bundle_execution_enabled,
                    "bundle_execution_enabled",
                ),
                (
                    real_repair_approval_repair_execution_enabled,
                    "repair_execution_enabled",
                ),
                (
                    real_repair_approval_real_execution_enabled,
                    "real_execution_enabled",
                ),
                (real_repair_approval_subprocess_enabled, "subprocess_enabled"),
                (
                    real_repair_approval_bundle_execution_performed,
                    "bundle_execution_performed",
                ),
                (
                    real_repair_approval_bundle_subprocess_invoked,
                    "bundle_subprocess_invoked",
                ),
                (
                    real_repair_approval_repair_execution_performed,
                    "repair_execution_performed",
                ),
                (
                    real_repair_approval_repair_subprocess_invoked,
                    "repair_subprocess_invoked",
                ),
                (real_repair_approval_execution_performed, "execution_performed"),
                (real_repair_approval_subprocess_invoked, "subprocess_invoked"),
            ):
                value = str(bool(item.get(key_name))).lower()
                target[value] = target.get(value, 0) + 1

        if (
            record_type
            == "replay_lifecycle_retry_real_execution_repair_approval_transition"
        ):
            from_status = str(item.get("from_status") or "unknown").strip() or "unknown"
            to_status = str(item.get("to_status") or "unknown").strip() or "unknown"
            source_approval_status = (
                str(item.get("source_approval_status") or "unknown").strip()
                or "unknown"
            )
            source_review_status = (
                str(item.get("source_review_status") or "unknown").strip()
                or "unknown"
            )
            next_action = (
                str(item.get("recommended_next_action") or "unknown").strip()
                or "unknown"
            )

            real_repair_approval_transition_from_statuses[from_status] = (
                real_repair_approval_transition_from_statuses.get(from_status, 0) + 1
            )
            real_repair_approval_transition_to_statuses[to_status] = (
                real_repair_approval_transition_to_statuses.get(to_status, 0) + 1
            )
            real_repair_approval_transition_source_approval_statuses[
                source_approval_status
            ] = (
                real_repair_approval_transition_source_approval_statuses.get(
                    source_approval_status, 0
                )
                + 1
            )
            real_repair_approval_transition_source_review_statuses[
                source_review_status
            ] = (
                real_repair_approval_transition_source_review_statuses.get(
                    source_review_status, 0
                )
                + 1
            )
            real_repair_approval_transition_next_actions[next_action] = (
                real_repair_approval_transition_next_actions.get(next_action, 0) + 1
            )

            for target, key_name in (
                (
                    real_repair_approval_transition_operator_authorized,
                    "operator_authorized",
                ),
                (
                    real_repair_approval_transition_required,
                    "repair_execution_approval_required",
                ),
                (
                    real_repair_approval_transition_approved,
                    "repair_execution_transition_approved",
                ),
                (
                    real_repair_approval_transition_rejected,
                    "repair_execution_transition_rejected",
                ),
                (
                    real_repair_approval_transition_bundle_execution_enabled,
                    "bundle_execution_enabled",
                ),
                (
                    real_repair_approval_transition_repair_execution_enabled,
                    "repair_execution_enabled",
                ),
                (
                    real_repair_approval_transition_real_execution_enabled,
                    "real_execution_enabled",
                ),
                (
                    real_repair_approval_transition_subprocess_enabled,
                    "subprocess_enabled",
                ),
                (
                    real_repair_approval_transition_bundle_execution_performed,
                    "bundle_execution_performed",
                ),
                (
                    real_repair_approval_transition_bundle_subprocess_invoked,
                    "bundle_subprocess_invoked",
                ),
                (
                    real_repair_approval_transition_repair_execution_performed,
                    "repair_execution_performed",
                ),
                (
                    real_repair_approval_transition_repair_subprocess_invoked,
                    "repair_subprocess_invoked",
                ),
                (
                    real_repair_approval_transition_execution_performed,
                    "execution_performed",
                ),
                (
                    real_repair_approval_transition_subprocess_invoked,
                    "subprocess_invoked",
                ),
            ):
                value = str(bool(item.get(key_name))).lower()
                target[value] = target.get(value, 0) + 1

        if record_type == "replay_lifecycle_retry_real_execution_repair_final_gate":
            status = str(item.get("gate_status") or "unknown").strip() or "unknown"
            next_action = (
                str(item.get("recommended_next_action") or "unknown").strip()
                or "unknown"
            )

            real_repair_final_gate_statuses[status] = (
                real_repair_final_gate_statuses.get(status, 0) + 1
            )
            real_repair_final_gate_next_actions[next_action] = (
                real_repair_final_gate_next_actions.get(next_action, 0) + 1
            )

            for target, key_name in (
                (real_repair_final_gate_preconditions_satisfied, "repair_preconditions_satisfied"),
                (real_repair_final_gate_ready, "ready_for_repair_execution"),
                (real_repair_final_gate_would_execute, "would_execute"),
                (real_repair_final_gate_operator_authorized, "operator_authorized"),
                (real_repair_final_gate_transition_approved, "repair_execution_transition_approved"),
                (real_repair_final_gate_repair_execution_enabled, "repair_execution_enabled"),
                (real_repair_final_gate_real_execution_enabled, "real_execution_enabled"),
                (real_repair_final_gate_subprocess_enabled, "subprocess_enabled"),
                (real_repair_final_gate_repair_execution_performed, "repair_execution_performed"),
                (real_repair_final_gate_repair_subprocess_invoked, "repair_subprocess_invoked"),
                (real_repair_final_gate_execution_performed, "execution_performed"),
                (real_repair_final_gate_subprocess_invoked, "subprocess_invoked"),
            ):
                value = str(bool(item.get(key_name))).lower()
                target[value] = target.get(value, 0) + 1
        
        if (
            record_type
            == "replay_lifecycle_retry_real_execution_repair_dry_run_envelope"
        ):
            status = (
                str(item.get("repair_dry_run_status") or "unknown").strip()
                or "unknown"
            )
            mode = (
                str(item.get("repair_dry_run_mode") or "unknown").strip()
                or "unknown"
            )
            gate_status = (
                str(item.get("source_gate_status") or "unknown").strip()
                or "unknown"
            )
            next_action = (
                str(item.get("recommended_next_action") or "unknown").strip()
                or "unknown"
            )
            target_count = str(item.get("repair_dry_run_target_count") or 0)

            real_repair_dry_run_envelope_statuses[status] = (
                real_repair_dry_run_envelope_statuses.get(status, 0) + 1
            )
            real_repair_dry_run_envelope_modes[mode] = (
                real_repair_dry_run_envelope_modes.get(mode, 0) + 1
            )
            real_repair_dry_run_envelope_source_gate_statuses[gate_status] = (
                real_repair_dry_run_envelope_source_gate_statuses.get(
                    gate_status, 0
                )
                + 1
            )
            real_repair_dry_run_envelope_next_actions[next_action] = (
                real_repair_dry_run_envelope_next_actions.get(next_action, 0) + 1
            )
            real_repair_dry_run_envelope_target_counts[target_count] = (
                real_repair_dry_run_envelope_target_counts.get(target_count, 0) + 1
            )

            for target, key_name in (
                (real_repair_dry_run_envelope_dry_run_only, "dry_run_only"),
                (real_repair_dry_run_envelope_operator_authorized, "operator_authorized"),
                (real_repair_dry_run_envelope_ready, "ready_for_repair_execution"),
                (real_repair_dry_run_envelope_would_execute, "would_execute"),
                (
                    real_repair_dry_run_envelope_repair_execution_enabled,
                    "repair_execution_enabled",
                ),
                (
                    real_repair_dry_run_envelope_real_execution_enabled,
                    "real_execution_enabled",
                ),
                (
                    real_repair_dry_run_envelope_subprocess_enabled,
                    "subprocess_enabled",
                ),
                (
                    real_repair_dry_run_envelope_repair_execution_performed,
                    "repair_execution_performed",
                ),
                (
                    real_repair_dry_run_envelope_repair_subprocess_invoked,
                    "repair_subprocess_invoked",
                ),
                (
                    real_repair_dry_run_envelope_execution_performed,
                    "execution_performed",
                ),
                (
                    real_repair_dry_run_envelope_subprocess_invoked,
                    "subprocess_invoked",
                ),
            ):
                value = str(bool(item.get(key_name))).lower()
                target[value] = target.get(value, 0) + 1

        if record_type == "replay_lifecycle_retry_real_execution_repair_noop_result":
            status = str(item.get("repair_noop_status") or "unknown").strip() or "unknown"
            exit_code = str(item.get("exit_code"))
            source_status = (
                str(item.get("source_envelope_status") or "unknown").strip()
                or "unknown"
            )
            target_count = str(item.get("source_repair_dry_run_target_count") or 0)
            next_action = (
                str(item.get("recommended_next_action") or "unknown").strip()
                or "unknown"
            )

            real_repair_noop_result_statuses[status] = (
                real_repair_noop_result_statuses.get(status, 0) + 1
            )
            real_repair_noop_result_exit_codes[exit_code] = (
                real_repair_noop_result_exit_codes.get(exit_code, 0) + 1
            )
            real_repair_noop_result_source_envelope_statuses[source_status] = (
                real_repair_noop_result_source_envelope_statuses.get(source_status, 0)
                + 1
            )
            real_repair_noop_result_source_target_counts[target_count] = (
                real_repair_noop_result_source_target_counts.get(target_count, 0) + 1
            )
            real_repair_noop_result_next_actions[next_action] = (
                real_repair_noop_result_next_actions.get(next_action, 0) + 1
            )

            for target, key_name in (
                (real_repair_noop_result_noop_only, "noop_only"),
                (
                    real_repair_noop_result_stdout_marker_observed,
                    "noop_stdout_marker_observed",
                ),
                (real_repair_noop_result_operator_authorized, "operator_authorized"),
                (
                    real_repair_noop_result_repair_actions_executed,
                    "repair_actions_executed",
                ),
                (
                    real_repair_noop_result_repair_bundle_executed,
                    "repair_bundle_executed",
                ),
                (
                    real_repair_noop_result_repair_command_executed,
                    "repair_command_executed",
                ),
                (
                    real_repair_noop_result_rendered_command_executed,
                    "rendered_command_executed",
                ),
                (
                    real_repair_noop_result_dry_run_command_executed,
                    "dry_run_command_executed",
                ),
                (
                    real_repair_noop_result_repair_execution_enabled,
                    "repair_execution_enabled",
                ),
                (
                    real_repair_noop_result_real_execution_enabled,
                    "real_execution_enabled",
                ),
                (
                    real_repair_noop_result_subprocess_enabled,
                    "subprocess_enabled",
                ),
                (
                    real_repair_noop_result_repair_execution_performed,
                    "repair_execution_performed",
                ),
                (
                    real_repair_noop_result_repair_subprocess_invoked,
                    "repair_subprocess_invoked",
                ),
                (
                    real_repair_noop_result_execution_performed,
                    "execution_performed",
                ),
                (
                    real_repair_noop_result_subprocess_invoked,
                    "subprocess_invoked",
                ),
            ):
                value = str(bool(item.get(key_name))).lower()
                target[value] = target.get(value, 0) + 1
        
        if record_type == "replay_lifecycle_retry_real_execution_repair_noop_feedback":
            status = str(item.get("feedback_status") or "unknown").strip() or "unknown"
            source_status = (
                str(item.get("source_noop_status") or "unknown").strip()
                or "unknown"
            )
            exit_code = str(item.get("source_noop_exit_code"))
            target_count = str(item.get("source_repair_dry_run_target_count") or 0)
            next_action = (
                str(item.get("recommended_next_action") or "unknown").strip()
                or "unknown"
            )

            real_repair_noop_feedback_statuses[status] = (
                real_repair_noop_feedback_statuses.get(status, 0) + 1
            )
            real_repair_noop_feedback_source_noop_statuses[source_status] = (
                real_repair_noop_feedback_source_noop_statuses.get(source_status, 0)
                + 1
            )
            real_repair_noop_feedback_source_exit_codes[exit_code] = (
                real_repair_noop_feedback_source_exit_codes.get(exit_code, 0) + 1
            )
            real_repair_noop_feedback_source_target_counts[target_count] = (
                real_repair_noop_feedback_source_target_counts.get(target_count, 0)
                + 1
            )
            real_repair_noop_feedback_next_actions[next_action] = (
                real_repair_noop_feedback_next_actions.get(next_action, 0) + 1
            )

            for target, key_name in (
                (real_repair_noop_feedback_verified, "repair_noop_verified"),
                (
                    real_repair_noop_feedback_path_can_proceed,
                    "repair_path_can_proceed",
                ),
                (
                    real_repair_noop_feedback_next_gate_allowed,
                    "repair_path_next_gate_allowed",
                ),
                (
                    real_repair_noop_feedback_source_execution_performed,
                    "source_execution_performed",
                ),
                (
                    real_repair_noop_feedback_source_subprocess_invoked,
                    "source_subprocess_invoked",
                ),
                (
                    real_repair_noop_feedback_source_repair_actions_executed,
                    "source_repair_actions_executed",
                ),
                (
                    real_repair_noop_feedback_source_repair_execution_enabled,
                    "source_repair_execution_enabled",
                ),
                (
                    real_repair_noop_feedback_source_repair_execution_performed,
                    "source_repair_execution_performed",
                ),
                (
                    real_repair_noop_feedback_source_repair_subprocess_invoked,
                    "source_repair_subprocess_invoked",
                ),
                (
                    real_repair_noop_feedback_feedback_execution_performed,
                    "feedback_execution_performed",
                ),
                (
                    real_repair_noop_feedback_feedback_subprocess_invoked,
                    "feedback_subprocess_invoked",
                ),
                (
                    real_repair_noop_feedback_repair_execution_enabled,
                    "repair_execution_enabled",
                ),
                (
                    real_repair_noop_feedback_real_execution_enabled,
                    "real_execution_enabled",
                ),
                (
                    real_repair_noop_feedback_subprocess_enabled,
                    "subprocess_enabled",
                ),
                (
                    real_repair_noop_feedback_repair_execution_performed,
                    "repair_execution_performed",
                ),
                (
                    real_repair_noop_feedback_repair_subprocess_invoked,
                    "repair_subprocess_invoked",
                ),
                (
                    real_repair_noop_feedback_execution_performed,
                    "execution_performed",
                ),
                (
                    real_repair_noop_feedback_subprocess_invoked,
                    "subprocess_invoked",
                ),
            ):
                value = str(bool(item.get(key_name))).lower()
                target[value] = target.get(value, 0) + 1
        
        if record_type == "replay_lifecycle_retry_real_execution_repair_readiness_gate":
            status = str(item.get("gate_status") or "unknown").strip() or "unknown"
            feedback_status = (
                str(item.get("source_feedback_status") or "unknown").strip()
                or "unknown"
            )
            noop_status = (
                str(item.get("source_noop_status") or "unknown").strip()
                or "unknown"
            )
            exit_code = str(item.get("source_noop_exit_code"))
            target_count = str(item.get("source_repair_dry_run_target_count") or 0)
            next_action = (
                str(item.get("recommended_next_action") or "unknown").strip()
                or "unknown"
            )

            real_repair_readiness_gate_statuses[status] = (
                real_repair_readiness_gate_statuses.get(status, 0) + 1
            )
            real_repair_readiness_gate_source_feedback_statuses[feedback_status] = (
                real_repair_readiness_gate_source_feedback_statuses.get(
                    feedback_status, 0
                )
                + 1
            )
            real_repair_readiness_gate_source_noop_statuses[noop_status] = (
                real_repair_readiness_gate_source_noop_statuses.get(noop_status, 0)
                + 1
            )
            real_repair_readiness_gate_source_exit_codes[exit_code] = (
                real_repair_readiness_gate_source_exit_codes.get(exit_code, 0) + 1
            )
            real_repair_readiness_gate_source_target_counts[target_count] = (
                real_repair_readiness_gate_source_target_counts.get(target_count, 0)
                + 1
            )
            real_repair_readiness_gate_next_actions[next_action] = (
                real_repair_readiness_gate_next_actions.get(next_action, 0) + 1
            )

            for target, key_name in (
                (
                    real_repair_readiness_gate_satisfied,
                    "repair_readiness_satisfied",
                ),
                (
                    real_repair_readiness_gate_guarded_ready,
                    "ready_for_guarded_repair_execution",
                ),
                (
                    real_repair_readiness_gate_ready_for_repair_execution,
                    "ready_for_repair_execution",
                ),
                (real_repair_readiness_gate_would_execute, "would_execute"),
                (
                    real_repair_readiness_gate_source_execution_performed,
                    "source_execution_performed",
                ),
                (
                    real_repair_readiness_gate_source_subprocess_invoked,
                    "source_subprocess_invoked",
                ),
                (
                    real_repair_readiness_gate_source_repair_actions_executed,
                    "source_repair_actions_executed",
                ),
                (
                    real_repair_readiness_gate_source_repair_execution_enabled,
                    "source_repair_execution_enabled",
                ),
                (
                    real_repair_readiness_gate_source_repair_execution_performed,
                    "source_repair_execution_performed",
                ),
                (
                    real_repair_readiness_gate_source_repair_subprocess_invoked,
                    "source_repair_subprocess_invoked",
                ),
                (
                    real_repair_readiness_gate_repair_execution_enabled,
                    "repair_execution_enabled",
                ),
                (
                    real_repair_readiness_gate_real_execution_enabled,
                    "real_execution_enabled",
                ),
                (
                    real_repair_readiness_gate_subprocess_enabled,
                    "subprocess_enabled",
                ),
                (
                    real_repair_readiness_gate_repair_execution_performed,
                    "repair_execution_performed",
                ),
                (
                    real_repair_readiness_gate_repair_subprocess_invoked,
                    "repair_subprocess_invoked",
                ),
                (
                    real_repair_readiness_gate_execution_performed,
                    "execution_performed",
                ),
                (
                    real_repair_readiness_gate_subprocess_invoked,
                    "subprocess_invoked",
                ),
            ):
                value = str(bool(item.get(key_name))).lower()
                target[value] = target.get(value, 0) + 1
        
        if record_type == "replay_lifecycle_retry_guarded_repair_execution_result":
            status = str(item.get("repair_execution_status") or "unknown").strip() or "unknown"
            exit_code = str(item.get("exit_code"))
            target_count = str(item.get("repair_action_target_count") or 0)
            next_action = str(item.get("recommended_next_action") or "unknown").strip() or "unknown"
            source_gate = str(item.get("source_gate_status") or "unknown").strip() or "unknown"
            source_feedback = str(item.get("source_feedback_status") or "unknown").strip() or "unknown"
            source_noop = str(item.get("source_noop_status") or "unknown").strip() or "unknown"

            guarded_repair_execution_statuses[status] = guarded_repair_execution_statuses.get(status, 0) + 1
            guarded_repair_execution_exit_codes[exit_code] = guarded_repair_execution_exit_codes.get(exit_code, 0) + 1
            guarded_repair_execution_target_counts[target_count] = guarded_repair_execution_target_counts.get(target_count, 0) + 1
            guarded_repair_execution_next_actions[next_action] = guarded_repair_execution_next_actions.get(next_action, 0) + 1
            guarded_repair_execution_source_gate_statuses[source_gate] = guarded_repair_execution_source_gate_statuses.get(source_gate, 0) + 1
            guarded_repair_execution_source_feedback_statuses[source_feedback] = guarded_repair_execution_source_feedback_statuses.get(source_feedback, 0) + 1
            guarded_repair_execution_source_noop_statuses[source_noop] = guarded_repair_execution_source_noop_statuses.get(source_noop, 0) + 1

            for target, key_name in (
                (guarded_repair_execution_allowed, "repair_execution_allowed"),
                (guarded_repair_execution_marker_observed, "guarded_repair_marker_observed"),
                (guarded_repair_execution_source_ready_guarded, "source_ready_for_guarded_repair_execution"),
                (guarded_repair_execution_source_ready_repair, "source_ready_for_repair_execution"),
                (guarded_repair_execution_source_would_execute, "source_would_execute"),
                (guarded_repair_execution_source_execution_performed, "source_execution_performed"),
                (guarded_repair_execution_source_subprocess_invoked, "source_subprocess_invoked"),
                (guarded_repair_execution_repair_actions_executed, "repair_actions_executed"),
                (guarded_repair_execution_repair_bundle_executed, "repair_bundle_executed"),
                (guarded_repair_execution_repair_command_executed, "repair_command_executed"),
                (guarded_repair_execution_rendered_command_executed, "rendered_command_executed"),
                (guarded_repair_execution_dry_run_command_executed, "dry_run_command_executed"),
                (guarded_repair_execution_repair_execution_enabled, "repair_execution_enabled"),
                (guarded_repair_execution_real_execution_enabled, "real_execution_enabled"),
                (guarded_repair_execution_subprocess_enabled, "subprocess_enabled"),
                (guarded_repair_execution_repair_execution_performed, "repair_execution_performed"),
                (guarded_repair_execution_repair_subprocess_invoked, "repair_subprocess_invoked"),
                (guarded_repair_execution_execution_performed, "execution_performed"),
                (guarded_repair_execution_subprocess_invoked, "subprocess_invoked"),
            ):
                value = str(bool(item.get(key_name))).lower()
                target[value] = target.get(value, 0) + 1
        
        if record_type == "replay_lifecycle_retry_post_repair_evidence_check":
            status = str(item.get("post_repair_status") or "unknown").strip() or "unknown"
            exit_code = str(item.get("post_repair_evidence_exit_code"))
            expected_count = str(item.get("repair_targets_expected_count") or 0)
            verified_count = str(item.get("repair_targets_verified_count") or 0)
            missing_count = str(len(item.get("repair_targets_missing") or []))
            unexpected_count = str(len(item.get("repair_targets_unexpected") or []))
            next_action = str(item.get("recommended_next_action") or "unknown").strip() or "unknown"
            source_status = str(item.get("source_guarded_repair_execution_status") or "unknown").strip() or "unknown"
            source_exit_code = str(item.get("source_guarded_repair_exit_code"))

            post_repair_evidence_statuses[status] = post_repair_evidence_statuses.get(status, 0) + 1
            post_repair_evidence_exit_codes[exit_code] = post_repair_evidence_exit_codes.get(exit_code, 0) + 1
            post_repair_evidence_expected_counts[expected_count] = post_repair_evidence_expected_counts.get(expected_count, 0) + 1
            post_repair_evidence_verified_counts[verified_count] = post_repair_evidence_verified_counts.get(verified_count, 0) + 1
            post_repair_evidence_missing_counts[missing_count] = post_repair_evidence_missing_counts.get(missing_count, 0) + 1
            post_repair_evidence_unexpected_counts[unexpected_count] = post_repair_evidence_unexpected_counts.get(unexpected_count, 0) + 1
            post_repair_evidence_next_actions[next_action] = post_repair_evidence_next_actions.get(next_action, 0) + 1
            post_repair_evidence_source_statuses[source_status] = post_repair_evidence_source_statuses.get(source_status, 0) + 1
            post_repair_evidence_source_exit_codes[source_exit_code] = post_repair_evidence_source_exit_codes.get(source_exit_code, 0) + 1

            for target, key_name in (
                (post_repair_evidence_allowed, "post_repair_evidence_check_allowed"),
                (post_repair_evidence_enabled, "post_repair_evidence_check_enabled"),
                (post_repair_evidence_marker_observed, "post_repair_evidence_marker_observed"),
                (post_repair_evidence_outcome_verified, "repair_outcome_verified"),
                (post_repair_evidence_source_allowed, "source_guarded_repair_execution_allowed"),
                (post_repair_evidence_source_marker_observed, "source_guarded_repair_marker_observed"),
                (post_repair_evidence_source_repair_actions_executed, "source_repair_actions_executed"),
                (post_repair_evidence_source_repair_execution_enabled, "source_repair_execution_enabled"),
                (post_repair_evidence_source_real_execution_enabled, "source_real_execution_enabled"),
                (post_repair_evidence_source_repair_execution_performed, "source_repair_execution_performed"),
                (post_repair_evidence_source_repair_subprocess_invoked, "source_repair_subprocess_invoked"),
                (post_repair_evidence_execution_performed, "execution_performed"),
                (post_repair_evidence_subprocess_invoked, "subprocess_invoked"),
                (post_repair_evidence_repair_execution_enabled, "repair_execution_enabled"),
                (post_repair_evidence_real_execution_enabled, "real_execution_enabled"),
                (post_repair_evidence_repair_execution_performed, "repair_execution_performed"),
                (post_repair_evidence_repair_subprocess_invoked, "repair_subprocess_invoked"),
            ):
                value = str(bool(item.get(key_name))).lower()
                target[value] = target.get(value, 0) + 1

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
        "controlled_execution_gate_statuses": controlled_execution_gate_statuses,
        "controlled_execution_gate_would_execute": controlled_execution_gate_would_execute,
        "controlled_execution_gate_would_execute_if_enabled": (
            controlled_execution_gate_would_execute_if_enabled
        ),
        "controlled_execution_gate_execution_performed": (
            controlled_execution_gate_execution_performed
        ),
        "controlled_execution_gate_reasons": controlled_execution_gate_reasons,
        "controlled_execution_mock_statuses": controlled_execution_mock_statuses,
        "controlled_execution_mock_performed": controlled_execution_mock_performed,
        "controlled_execution_mock_subprocess_invoked": controlled_execution_mock_subprocess_invoked,
        "mock_summary_statuses": mock_summary_statuses,
        "mock_summary_reasons": mock_summary_reasons,
        "mock_summary_performed": mock_summary_performed,
        "mock_summary_subprocess_invoked": mock_summary_subprocess_invoked,
        "controlled_execution_mock_adapter": controlled_execution_mock_adapter,
        "controlled_execution_mock_adapter_mode": controlled_execution_mock_adapter_mode,
        "controlled_execution_mock_adapter_result_statuses": (
            controlled_execution_mock_adapter_result_statuses
        ),
        "controlled_execution_mock_adapter_subprocess_invoked": (
            controlled_execution_mock_adapter_subprocess_invoked
        ),
        "controlled_execution_mock_adapter_real_execution_enabled": (
            controlled_execution_mock_adapter_real_execution_enabled
        ),
        "controlled_execution_mock_adapter_payload_executed": (
            controlled_execution_mock_adapter_payload_executed
        ),
        "controlled_execution_real_requested": controlled_execution_real_requested,
        "controlled_execution_real_performed": controlled_execution_real_performed,
        "controlled_execution_real_supported": controlled_execution_real_supported,
        "controlled_execution_subprocess_invoked": controlled_execution_subprocess_invoked,
        "real_preflight_statuses": real_preflight_statuses,
        "real_preflight_reasons": real_preflight_reasons,
        "real_preflight_requested": real_preflight_requested,
        "real_preflight_would_execute": real_preflight_would_execute,
        "real_preflight_execution_performed": real_preflight_execution_performed,
        "real_preflight_subprocess_invoked": real_preflight_subprocess_invoked,
        "real_preflight_requires_explicit_pr": real_preflight_requires_explicit_pr,
        "real_approval_statuses": real_approval_statuses,
        "real_approval_enabled": real_approval_enabled,
        "real_approval_subprocess_enabled": real_approval_subprocess_enabled,
        "real_approval_execution_performed": real_approval_execution_performed,
        "real_approval_subprocess_invoked": real_approval_subprocess_invoked,
        "real_approval_transition_statuses": real_approval_transition_statuses,
        "real_approval_transition_enabled": real_approval_transition_enabled,
        "real_approval_transition_subprocess_enabled": real_approval_transition_subprocess_enabled,
        "real_approval_transition_execution_performed": real_approval_transition_execution_performed,
        "real_approval_transition_subprocess_invoked": real_approval_transition_subprocess_invoked,
        "real_final_gate_statuses": real_final_gate_statuses,
        "real_final_gate_would_execute": real_final_gate_would_execute,
        "real_final_gate_ready": real_final_gate_ready,
        "real_final_gate_real_execution_enabled": real_final_gate_real_execution_enabled,
        "real_final_gate_subprocess_enabled": real_final_gate_subprocess_enabled,
        "real_final_gate_execution_performed": real_final_gate_execution_performed,
        "real_final_gate_subprocess_invoked": real_final_gate_subprocess_invoked,
        "real_dry_run_envelope_dry_run_only": real_dry_run_envelope_dry_run_only,
        "real_dry_run_envelope_would_execute": real_dry_run_envelope_would_execute,
        "real_dry_run_envelope_ready": real_dry_run_envelope_ready,
        "real_dry_run_envelope_real_execution_enabled": (
            real_dry_run_envelope_real_execution_enabled
        ),
        "real_dry_run_envelope_subprocess_enabled": (
            real_dry_run_envelope_subprocess_enabled
        ),
        "real_dry_run_envelope_execution_performed": (
            real_dry_run_envelope_execution_performed
        ),
        "real_dry_run_envelope_subprocess_invoked": (
            real_dry_run_envelope_subprocess_invoked
        ),
        "real_noop_result_noop_only": real_noop_result_noop_only,
        "real_noop_result_rendered_command_executed": (
            real_noop_result_rendered_command_executed
        ),
        "real_noop_result_dry_run_command_executed": (
            real_noop_result_dry_run_command_executed
        ),
        "real_noop_result_real_execution_enabled": real_noop_result_real_execution_enabled,
        "real_noop_result_subprocess_invoked": real_noop_result_subprocess_invoked,
        "real_noop_result_execution_performed": real_noop_result_execution_performed,
        "real_noop_result_exit_codes": real_noop_result_exit_codes,
        "real_read_only_promotion_statuses": real_read_only_promotion_statuses,
        "real_read_only_promotion_candidates": real_read_only_promotion_candidates,
        "real_read_only_promotion_command_parse_valid": (
            real_read_only_promotion_command_parse_valid
        ),
        "real_read_only_promotion_stdout_marker_observed": (
            real_read_only_promotion_stdout_marker_observed
        ),
        "real_read_only_promotion_noop_exit_codes": (
            real_read_only_promotion_noop_exit_codes
        ),
        "real_read_only_promotion_rendered_command_executed": (
            real_read_only_promotion_rendered_command_executed
        ),
        "real_read_only_promotion_dry_run_command_executed": (
            real_read_only_promotion_dry_run_command_executed
        ),
        "real_read_only_promotion_real_execution_enabled": (
            real_read_only_promotion_real_execution_enabled
        ),
        "real_read_only_promotion_subprocess_invoked": (
            real_read_only_promotion_subprocess_invoked
        ),
        "real_read_only_promotion_execution_performed": (
            real_read_only_promotion_execution_performed
        ),
        "real_read_only_final_gate_statuses": real_read_only_final_gate_statuses,
        "real_read_only_final_gate_preconditions_satisfied": (
            real_read_only_final_gate_preconditions_satisfied
        ),
        "real_read_only_final_gate_ready": real_read_only_final_gate_ready,
        "real_read_only_final_gate_would_execute": real_read_only_final_gate_would_execute,
        "real_read_only_final_gate_read_only_execution_enabled": (
            real_read_only_final_gate_read_only_execution_enabled
        ),
        "real_read_only_final_gate_real_execution_enabled": (
            real_read_only_final_gate_real_execution_enabled
        ),
        "real_read_only_final_gate_subprocess_enabled": (
            real_read_only_final_gate_subprocess_enabled
        ),
        "real_read_only_final_gate_subprocess_invoked": (
            real_read_only_final_gate_subprocess_invoked
        ),
        "real_read_only_final_gate_execution_performed": (
            real_read_only_final_gate_execution_performed
        ),
        "real_read_only_final_gate_rendered_command_executed": (
            real_read_only_final_gate_rendered_command_executed
        ),
        "real_read_only_final_gate_dry_run_command_executed": (
            real_read_only_final_gate_dry_run_command_executed
        ),
        "real_read_only_approval_statuses": real_read_only_approval_statuses,
        "real_read_only_approval_read_only_execution_enabled": (
            real_read_only_approval_read_only_execution_enabled
        ),
        "real_read_only_approval_real_execution_enabled": (
            real_read_only_approval_real_execution_enabled
        ),
        "real_read_only_approval_subprocess_enabled": (
            real_read_only_approval_subprocess_enabled
        ),
        "real_read_only_approval_subprocess_invoked": (
            real_read_only_approval_subprocess_invoked
        ),
        "real_read_only_approval_execution_performed": (
            real_read_only_approval_execution_performed
        ),
        "real_read_only_approval_rendered_command_executed": (
            real_read_only_approval_rendered_command_executed
        ),
        "real_read_only_approval_dry_run_command_executed": (
            real_read_only_approval_dry_run_command_executed
        ),
        "real_read_only_approval_transition_from_statuses": (
            real_read_only_approval_transition_from_statuses
        ),
        "real_read_only_approval_transition_to_statuses": (
            real_read_only_approval_transition_to_statuses
        ),
        "real_read_only_approval_transition_read_only_execution_enabled": (
            real_read_only_approval_transition_read_only_execution_enabled
        ),
        "real_read_only_approval_transition_real_execution_enabled": (
            real_read_only_approval_transition_real_execution_enabled
        ),
        "real_read_only_approval_transition_subprocess_enabled": (
            real_read_only_approval_transition_subprocess_enabled
        ),
        "real_read_only_approval_transition_subprocess_invoked": (
            real_read_only_approval_transition_subprocess_invoked
        ),
        "real_read_only_approval_transition_execution_performed": (
            real_read_only_approval_transition_execution_performed
        ),
        "real_read_only_approval_transition_rendered_command_executed": (
            real_read_only_approval_transition_rendered_command_executed
        ),
        "real_read_only_approval_transition_dry_run_command_executed": (
            real_read_only_approval_transition_dry_run_command_executed
        ),
        "real_read_only_readiness_gate_statuses": real_read_only_readiness_gate_statuses,
        "real_read_only_readiness_gate_satisfied": real_read_only_readiness_gate_satisfied,
        "real_read_only_readiness_gate_ready": real_read_only_readiness_gate_ready,
        "real_read_only_readiness_gate_read_only_execution_enabled": (
            real_read_only_readiness_gate_read_only_execution_enabled
        ),
        "real_read_only_readiness_gate_real_execution_enabled": (
            real_read_only_readiness_gate_real_execution_enabled
        ),
        "real_read_only_readiness_gate_subprocess_enabled": (
            real_read_only_readiness_gate_subprocess_enabled
        ),
        "real_read_only_readiness_gate_subprocess_invoked": (
            real_read_only_readiness_gate_subprocess_invoked
        ),
        "real_read_only_readiness_gate_execution_performed": (
            real_read_only_readiness_gate_execution_performed
        ),
        "real_read_only_readiness_gate_rendered_command_executed": (
            real_read_only_readiness_gate_rendered_command_executed
        ),
        "real_read_only_readiness_gate_dry_run_command_executed": (
            real_read_only_readiness_gate_dry_run_command_executed
        ),
        "real_read_only_execution_result_statuses": real_read_only_execution_result_statuses,
        "real_read_only_execution_result_reasons": real_read_only_execution_result_reasons,
        "real_read_only_execution_result_exit_codes": real_read_only_execution_result_exit_codes,
        "real_read_only_execution_result_validation_reasons_empty": (
            real_read_only_execution_result_validation_reasons_empty
        ),
        "real_read_only_execution_result_operator_authorized": (
            real_read_only_execution_result_operator_authorized
        ),
        "real_read_only_execution_result_allow_guarded": (
            real_read_only_execution_result_allow_guarded
        ),
        "real_read_only_execution_result_read_only_execution_enabled": (
            real_read_only_execution_result_read_only_execution_enabled
        ),
        "real_read_only_execution_result_real_execution_enabled": (
           real_read_only_execution_result_real_execution_enabled
        ),
        "real_read_only_execution_result_subprocess_enabled": (
            real_read_only_execution_result_subprocess_enabled
        ),
        "real_read_only_execution_result_subprocess_invoked": (
            real_read_only_execution_result_subprocess_invoked
        ),
        "real_read_only_execution_result_execution_performed": (
            real_read_only_execution_result_execution_performed
        ),
        "real_read_only_execution_result_read_only_command_executed": (
            real_read_only_execution_result_read_only_command_executed
        ),
        "real_read_only_execution_result_rendered_command_executed": (
            real_read_only_execution_result_rendered_command_executed
        ),
        "real_read_only_execution_result_dry_run_command_executed": (
            real_read_only_execution_result_dry_run_command_executed
        ),
        "real_read_only_feedback_statuses": real_read_only_feedback_statuses,
        "real_read_only_feedback_source_statuses": real_read_only_feedback_source_statuses,
        "real_read_only_feedback_source_exit_codes": real_read_only_feedback_source_exit_codes,
        "real_read_only_feedback_next_actions": real_read_only_feedback_next_actions,
        "real_read_only_feedback_execution_observed": real_read_only_feedback_execution_observed,
        "real_read_only_feedback_failed": real_read_only_feedback_failed,
        "real_read_only_feedback_succeeded": real_read_only_feedback_succeeded,
        "real_read_only_feedback_rejected": real_read_only_feedback_rejected,
        "real_read_only_feedback_real_execution_enabled": real_read_only_feedback_real_execution_enabled,
        "real_read_only_feedback_feedback_execution_performed": real_read_only_feedback_feedback_execution_performed,
        "real_read_only_feedback_feedback_subprocess_invoked": real_read_only_feedback_feedback_subprocess_invoked,
        "real_read_only_feedback_execution_performed": real_read_only_feedback_execution_performed,
        "real_read_only_feedback_subprocess_invoked": real_read_only_feedback_subprocess_invoked,
        "real_read_only_repair_plan_statuses": real_read_only_repair_plan_statuses,
        "real_read_only_repair_plan_source_feedback_statuses": (
            real_read_only_repair_plan_source_feedback_statuses
        ),
        "real_read_only_repair_plan_source_statuses": (
            real_read_only_repair_plan_source_statuses
        ),
        "real_read_only_repair_plan_source_exit_codes": (
            real_read_only_repair_plan_source_exit_codes
        ),
        "real_read_only_repair_plan_next_actions": (
            real_read_only_repair_plan_next_actions
        ),
        "real_read_only_repair_plan_item_counts": (
            real_read_only_repair_plan_item_counts
        ),
        "real_read_only_repair_plan_requires_operator_review": (
            real_read_only_repair_plan_requires_operator_review
        ),
        "real_read_only_repair_plan_repair_execution_enabled": (
            real_read_only_repair_plan_repair_execution_enabled
        ),
        "real_read_only_repair_plan_real_execution_enabled": (
            real_read_only_repair_plan_real_execution_enabled
        ),
        "real_read_only_repair_plan_subprocess_enabled": (
            real_read_only_repair_plan_subprocess_enabled
        ),
        "real_read_only_repair_plan_repair_execution_performed": (
            real_read_only_repair_plan_repair_execution_performed
        ),
        "real_read_only_repair_plan_repair_subprocess_invoked": (
            real_read_only_repair_plan_repair_subprocess_invoked
        ),
        "real_read_only_repair_plan_execution_performed": (
            real_read_only_repair_plan_execution_performed
        ),
        "real_read_only_repair_plan_subprocess_invoked": (
            real_read_only_repair_plan_subprocess_invoked
        ),
        "real_read_only_repair_action_bundle_statuses": (
           real_read_only_repair_action_bundle_statuses
        ),
        "real_read_only_repair_action_bundle_source_plan_statuses": (
            real_read_only_repair_action_bundle_source_plan_statuses
        ),
        "real_read_only_repair_action_bundle_source_feedback_statuses": (
            real_read_only_repair_action_bundle_source_feedback_statuses
        ),
        "real_read_only_repair_action_bundle_source_statuses": (
            real_read_only_repair_action_bundle_source_statuses
        ),
        "real_read_only_repair_action_bundle_source_exit_codes": (
            real_read_only_repair_action_bundle_source_exit_codes
        ),
        "real_read_only_repair_action_bundle_next_actions": (
            real_read_only_repair_action_bundle_next_actions
        ),
        "real_read_only_repair_action_bundle_item_counts": (
            real_read_only_repair_action_bundle_item_counts
        ),
        "real_read_only_repair_action_bundle_source_item_counts": (
            real_read_only_repair_action_bundle_source_item_counts
        ),
        "real_read_only_repair_action_bundle_requires_operator_review": (
            real_read_only_repair_action_bundle_requires_operator_review
        ),
        "real_read_only_repair_action_bundle_reviewed": (
            real_read_only_repair_action_bundle_reviewed
        ),
        "real_read_only_repair_action_bundle_bundle_execution_enabled": (
            real_read_only_repair_action_bundle_bundle_execution_enabled
        ),
        "real_read_only_repair_action_bundle_repair_execution_enabled": (
            real_read_only_repair_action_bundle_repair_execution_enabled
        ),
        "real_read_only_repair_action_bundle_real_execution_enabled": (
            real_read_only_repair_action_bundle_real_execution_enabled
        ),
        "real_read_only_repair_action_bundle_subprocess_enabled": (
            real_read_only_repair_action_bundle_subprocess_enabled
        ),
        "real_read_only_repair_action_bundle_bundle_execution_performed": (
            real_read_only_repair_action_bundle_bundle_execution_performed
        ),
        "real_read_only_repair_action_bundle_bundle_subprocess_invoked": (
            real_read_only_repair_action_bundle_bundle_subprocess_invoked
        ),
        "real_read_only_repair_action_bundle_repair_execution_performed": (
            real_read_only_repair_action_bundle_repair_execution_performed
        ),
        "real_read_only_repair_action_bundle_repair_subprocess_invoked": (
            real_read_only_repair_action_bundle_repair_subprocess_invoked
        ),
        "real_read_only_repair_action_bundle_execution_performed": (
            real_read_only_repair_action_bundle_execution_performed
        ),
        "real_read_only_repair_action_bundle_subprocess_invoked": (
            real_read_only_repair_action_bundle_subprocess_invoked
        ),
        "real_read_only_repair_action_bundle_review_statuses": (
            real_read_only_repair_action_bundle_review_statuses
        ),
        "real_read_only_repair_action_bundle_review_source_bundle_statuses": (
            real_read_only_repair_action_bundle_review_source_bundle_statuses
        ),
        "real_read_only_repair_action_bundle_review_source_plan_statuses": (
            real_read_only_repair_action_bundle_review_source_plan_statuses
        ),
        "real_read_only_repair_action_bundle_review_source_feedback_statuses": (
            real_read_only_repair_action_bundle_review_source_feedback_statuses
        ),
        "real_read_only_repair_action_bundle_review_source_statuses": (
            real_read_only_repair_action_bundle_review_source_statuses
        ),
        "real_read_only_repair_action_bundle_review_source_exit_codes": (
            real_read_only_repair_action_bundle_review_source_exit_codes
        ),
        "real_read_only_repair_action_bundle_review_source_item_counts": (
            real_read_only_repair_action_bundle_review_source_item_counts
        ),
        "real_read_only_repair_action_bundle_review_next_actions": (
            real_read_only_repair_action_bundle_review_next_actions
        ),
        "real_read_only_repair_action_bundle_review_operator_authorized": (
            real_read_only_repair_action_bundle_review_operator_authorized
        ),
        "real_read_only_repair_action_bundle_review_requires_operator_review": (
            real_read_only_repair_action_bundle_review_requires_operator_review
        ),
        "real_read_only_repair_action_bundle_review_reviewed": (
            real_read_only_repair_action_bundle_review_reviewed
        ),
        "real_read_only_repair_action_bundle_review_approved": (
            real_read_only_repair_action_bundle_review_approved
        ),
        "real_read_only_repair_action_bundle_review_rejected": (
            real_read_only_repair_action_bundle_review_rejected
        ),
        "real_read_only_repair_action_bundle_review_bundle_execution_enabled": (
            real_read_only_repair_action_bundle_review_bundle_execution_enabled
        ),
        "real_read_only_repair_action_bundle_review_repair_execution_enabled": (
            real_read_only_repair_action_bundle_review_repair_execution_enabled
        ),
        "real_read_only_repair_action_bundle_review_real_execution_enabled": (
            real_read_only_repair_action_bundle_review_real_execution_enabled
        ),
        "real_read_only_repair_action_bundle_review_subprocess_enabled": (
            real_read_only_repair_action_bundle_review_subprocess_enabled
        ),
        "real_read_only_repair_action_bundle_review_bundle_execution_performed": (
            real_read_only_repair_action_bundle_review_bundle_execution_performed
        ),
        "real_read_only_repair_action_bundle_review_bundle_subprocess_invoked": (
            real_read_only_repair_action_bundle_review_bundle_subprocess_invoked
        ),
        "real_read_only_repair_action_bundle_review_repair_execution_performed": (
            real_read_only_repair_action_bundle_review_repair_execution_performed
        ),
        "real_read_only_repair_action_bundle_review_repair_subprocess_invoked": (
            real_read_only_repair_action_bundle_review_repair_subprocess_invoked
        ),
        "real_read_only_repair_action_bundle_review_execution_performed": (
            real_read_only_repair_action_bundle_review_execution_performed
        ),
        "real_read_only_repair_action_bundle_review_subprocess_invoked": (
            real_read_only_repair_action_bundle_review_subprocess_invoked
        ),
        "real_repair_approval_statuses": real_repair_approval_statuses,
        "real_repair_approval_source_review_statuses": (
            real_repair_approval_source_review_statuses
        ),
        "real_repair_approval_source_bundle_statuses": (
            real_repair_approval_source_bundle_statuses
        ),
        "real_repair_approval_next_actions": real_repair_approval_next_actions,
        "real_repair_approval_operator_authorized": (
            real_repair_approval_operator_authorized
        ),
        "real_repair_approval_required": real_repair_approval_required,
        "real_repair_approval_approved": real_repair_approval_approved,
        "real_repair_approval_rejected": real_repair_approval_rejected,
        "real_repair_approval_bundle_execution_enabled": (
            real_repair_approval_bundle_execution_enabled
        ),
        "real_repair_approval_repair_execution_enabled": (
            real_repair_approval_repair_execution_enabled
        ),
        "real_repair_approval_real_execution_enabled": (
            real_repair_approval_real_execution_enabled
        ),
        "real_repair_approval_subprocess_enabled": (
            real_repair_approval_subprocess_enabled
        ),
        "real_repair_approval_bundle_execution_performed": (
            real_repair_approval_bundle_execution_performed
        ),
        "real_repair_approval_bundle_subprocess_invoked": (
            real_repair_approval_bundle_subprocess_invoked
        ),
        "real_repair_approval_repair_execution_performed": (
            real_repair_approval_repair_execution_performed
        ),
        "real_repair_approval_repair_subprocess_invoked": (
            real_repair_approval_repair_subprocess_invoked
        ),
        "real_repair_approval_execution_performed": (
            real_repair_approval_execution_performed
        ),
        "real_repair_approval_subprocess_invoked": (
            real_repair_approval_subprocess_invoked
        ),
        "real_repair_approval_transition_from_statuses": (
            real_repair_approval_transition_from_statuses
        ),
        "real_repair_approval_transition_to_statuses": (
            real_repair_approval_transition_to_statuses
        ),
        "real_repair_approval_transition_source_approval_statuses": (
            real_repair_approval_transition_source_approval_statuses
        ),
        "real_repair_approval_transition_source_review_statuses": (
            real_repair_approval_transition_source_review_statuses
        ),
        "real_repair_approval_transition_next_actions": (
            real_repair_approval_transition_next_actions
        ),
        "real_repair_approval_transition_operator_authorized": (
            real_repair_approval_transition_operator_authorized
        ),
        "real_repair_approval_transition_required": (
            real_repair_approval_transition_required
        ),
        "real_repair_approval_transition_approved": (
            real_repair_approval_transition_approved
        ),
        "real_repair_approval_transition_rejected": (
            real_repair_approval_transition_rejected
        ),
        "real_repair_approval_transition_bundle_execution_enabled": (
            real_repair_approval_transition_bundle_execution_enabled
        ),
        "real_repair_approval_transition_repair_execution_enabled": (
            real_repair_approval_transition_repair_execution_enabled
        ),
        "real_repair_approval_transition_real_execution_enabled": (
            real_repair_approval_transition_real_execution_enabled
        ),
        "real_repair_approval_transition_subprocess_enabled": (
            real_repair_approval_transition_subprocess_enabled
        ),
        "real_repair_approval_transition_bundle_execution_performed": (
            real_repair_approval_transition_bundle_execution_performed
        ),
        "real_repair_approval_transition_bundle_subprocess_invoked": (
            real_repair_approval_transition_bundle_subprocess_invoked
        ),
        "real_repair_approval_transition_repair_execution_performed": (
            real_repair_approval_transition_repair_execution_performed
        ),
        "real_repair_approval_transition_repair_subprocess_invoked": (
        real_repair_approval_transition_repair_subprocess_invoked
        ),
        "real_repair_approval_transition_execution_performed": (
            real_repair_approval_transition_execution_performed
        ),
        "real_repair_approval_transition_subprocess_invoked": (
            real_repair_approval_transition_subprocess_invoked
        ),
        "real_repair_final_gate_statuses": real_repair_final_gate_statuses,
        "real_repair_final_gate_preconditions_satisfied": (
            real_repair_final_gate_preconditions_satisfied
        ),
        "real_repair_final_gate_ready": real_repair_final_gate_ready,
        "real_repair_final_gate_would_execute": real_repair_final_gate_would_execute,
        "real_repair_final_gate_next_actions": real_repair_final_gate_next_actions,
        "real_repair_final_gate_operator_authorized": (
            real_repair_final_gate_operator_authorized
        ),
        "real_repair_final_gate_transition_approved": (
            real_repair_final_gate_transition_approved
        ),
        "real_repair_final_gate_repair_execution_enabled": (
            real_repair_final_gate_repair_execution_enabled
        ),
        "real_repair_final_gate_real_execution_enabled": (
            real_repair_final_gate_real_execution_enabled
        ),
        "real_repair_final_gate_subprocess_enabled": (
            real_repair_final_gate_subprocess_enabled
        ),
        "real_repair_final_gate_repair_execution_performed": (
            real_repair_final_gate_repair_execution_performed
        ),
        "real_repair_final_gate_repair_subprocess_invoked": (
            real_repair_final_gate_repair_subprocess_invoked
        ),
        "real_repair_final_gate_execution_performed": (
            real_repair_final_gate_execution_performed
        ),
        "real_repair_final_gate_subprocess_invoked": (
            real_repair_final_gate_subprocess_invoked
        ),
        "real_repair_dry_run_envelope_statuses": (
            real_repair_dry_run_envelope_statuses
        ),
        "real_repair_dry_run_envelope_dry_run_only": (
            real_repair_dry_run_envelope_dry_run_only
        ),
        "real_repair_dry_run_envelope_modes": real_repair_dry_run_envelope_modes,
        "real_repair_dry_run_envelope_target_counts": (
            real_repair_dry_run_envelope_target_counts
        ),
        "real_repair_dry_run_envelope_source_gate_statuses": (
            real_repair_dry_run_envelope_source_gate_statuses
        ),
        "real_repair_dry_run_envelope_next_actions": (
            real_repair_dry_run_envelope_next_actions
        ),
        "real_repair_dry_run_envelope_operator_authorized": (
            real_repair_dry_run_envelope_operator_authorized
        ),
        "real_repair_dry_run_envelope_ready": real_repair_dry_run_envelope_ready,
        "real_repair_dry_run_envelope_would_execute": (
            real_repair_dry_run_envelope_would_execute
        ),
        "real_repair_dry_run_envelope_repair_execution_enabled": (
            real_repair_dry_run_envelope_repair_execution_enabled
        ),
        "real_repair_dry_run_envelope_real_execution_enabled": (
            real_repair_dry_run_envelope_real_execution_enabled
        ),
        "real_repair_dry_run_envelope_subprocess_enabled": (
            real_repair_dry_run_envelope_subprocess_enabled
        ),
        "real_repair_dry_run_envelope_repair_execution_performed": (
            real_repair_dry_run_envelope_repair_execution_performed
        ),
        "real_repair_dry_run_envelope_repair_subprocess_invoked": (
            real_repair_dry_run_envelope_repair_subprocess_invoked
        ),
        "real_repair_dry_run_envelope_execution_performed": (
            real_repair_dry_run_envelope_execution_performed
        ),
        "real_repair_dry_run_envelope_subprocess_invoked": (
            real_repair_dry_run_envelope_subprocess_invoked
        ),
        "real_repair_noop_result_statuses": real_repair_noop_result_statuses,
        "real_repair_noop_result_exit_codes": real_repair_noop_result_exit_codes,
        "real_repair_noop_result_noop_only": real_repair_noop_result_noop_only,
        "real_repair_noop_result_stdout_marker_observed": (
            real_repair_noop_result_stdout_marker_observed
        ),
        "real_repair_noop_result_source_envelope_statuses": (
            real_repair_noop_result_source_envelope_statuses
        ),
        "real_repair_noop_result_source_target_counts": (
            real_repair_noop_result_source_target_counts
        ),
        "real_repair_noop_result_next_actions": real_repair_noop_result_next_actions,
        "real_repair_noop_result_operator_authorized": (
            real_repair_noop_result_operator_authorized
        ),
        "real_repair_noop_result_repair_actions_executed": (
            real_repair_noop_result_repair_actions_executed
        ),
        "real_repair_noop_result_repair_bundle_executed": (
            real_repair_noop_result_repair_bundle_executed
        ),
        "real_repair_noop_result_repair_command_executed": (
            real_repair_noop_result_repair_command_executed
        ),
        "real_repair_noop_result_rendered_command_executed": (
            real_repair_noop_result_rendered_command_executed
        ),
        "real_repair_noop_result_dry_run_command_executed": (
            real_repair_noop_result_dry_run_command_executed
        ),
        "real_repair_noop_result_repair_execution_enabled": (
            real_repair_noop_result_repair_execution_enabled
        ),
        "real_repair_noop_result_real_execution_enabled": (
            real_repair_noop_result_real_execution_enabled
        ),
        "real_repair_noop_result_subprocess_enabled": (
            real_repair_noop_result_subprocess_enabled
        ),
        "real_repair_noop_result_repair_execution_performed": (
            real_repair_noop_result_repair_execution_performed
        ),
        "real_repair_noop_result_repair_subprocess_invoked": (
            real_repair_noop_result_repair_subprocess_invoked
        ),
        "real_repair_noop_result_execution_performed": (
            real_repair_noop_result_execution_performed
        ),
        "real_repair_noop_result_subprocess_invoked": (
            real_repair_noop_result_subprocess_invoked
        ),
        "real_repair_noop_feedback_statuses": real_repair_noop_feedback_statuses,
        "real_repair_noop_feedback_verified": real_repair_noop_feedback_verified,
        "real_repair_noop_feedback_path_can_proceed": (
            real_repair_noop_feedback_path_can_proceed
        ),
        "real_repair_noop_feedback_next_gate_allowed": (
            real_repair_noop_feedback_next_gate_allowed
        ),
        "real_repair_noop_feedback_next_actions": real_repair_noop_feedback_next_actions,
        "real_repair_noop_feedback_source_noop_statuses": (
            real_repair_noop_feedback_source_noop_statuses
        ),
        "real_repair_noop_feedback_source_exit_codes": (
            real_repair_noop_feedback_source_exit_codes
        ),
        "real_repair_noop_feedback_source_target_counts": (
            real_repair_noop_feedback_source_target_counts
        ),
        "real_repair_noop_feedback_source_execution_performed": (
            real_repair_noop_feedback_source_execution_performed
        ),
        "real_repair_noop_feedback_source_subprocess_invoked": (
            real_repair_noop_feedback_source_subprocess_invoked
        ),
        "real_repair_noop_feedback_source_repair_actions_executed": (
            real_repair_noop_feedback_source_repair_actions_executed
        ),
        "real_repair_noop_feedback_source_repair_execution_enabled": (
            real_repair_noop_feedback_source_repair_execution_enabled
        ),
        "real_repair_noop_feedback_source_repair_execution_performed": (
            real_repair_noop_feedback_source_repair_execution_performed
        ),
        "real_repair_noop_feedback_source_repair_subprocess_invoked": (
            real_repair_noop_feedback_source_repair_subprocess_invoked
        ),
        "real_repair_noop_feedback_feedback_execution_performed": (
            real_repair_noop_feedback_feedback_execution_performed
        ),
        "real_repair_noop_feedback_feedback_subprocess_invoked": (
            real_repair_noop_feedback_feedback_subprocess_invoked
        ),
        "real_repair_noop_feedback_repair_execution_enabled": (
            real_repair_noop_feedback_repair_execution_enabled
        ),
        "real_repair_noop_feedback_real_execution_enabled": (
            real_repair_noop_feedback_real_execution_enabled
        ),
        "real_repair_noop_feedback_subprocess_enabled": (
            real_repair_noop_feedback_subprocess_enabled
        ),
        "real_repair_noop_feedback_repair_execution_performed": (
            real_repair_noop_feedback_repair_execution_performed
        ),
        "real_repair_noop_feedback_repair_subprocess_invoked": (
            real_repair_noop_feedback_repair_subprocess_invoked
        ),
        "real_repair_noop_feedback_execution_performed": (
            real_repair_noop_feedback_execution_performed
        ),
        "real_repair_noop_feedback_subprocess_invoked": (
            real_repair_noop_feedback_subprocess_invoked
        ),
        "real_repair_readiness_gate_statuses": real_repair_readiness_gate_statuses,
        "real_repair_readiness_gate_satisfied": real_repair_readiness_gate_satisfied,
        "real_repair_readiness_gate_guarded_ready": real_repair_readiness_gate_guarded_ready,
        "real_repair_readiness_gate_ready_for_repair_execution": (
            real_repair_readiness_gate_ready_for_repair_execution
        ),
        "real_repair_readiness_gate_would_execute": real_repair_readiness_gate_would_execute,
        "real_repair_readiness_gate_next_actions": real_repair_readiness_gate_next_actions,
        "real_repair_readiness_gate_source_feedback_statuses": (
            real_repair_readiness_gate_source_feedback_statuses
        ),
        "real_repair_readiness_gate_source_noop_statuses": (
            real_repair_readiness_gate_source_noop_statuses
        ),
        "real_repair_readiness_gate_source_exit_codes": (
            real_repair_readiness_gate_source_exit_codes
        ),
        "real_repair_readiness_gate_source_target_counts": (
            real_repair_readiness_gate_source_target_counts
        ),
        "real_repair_readiness_gate_source_execution_performed": (
            real_repair_readiness_gate_source_execution_performed
        ),
        "real_repair_readiness_gate_source_subprocess_invoked": (
            real_repair_readiness_gate_source_subprocess_invoked
        ),
        "real_repair_readiness_gate_source_repair_actions_executed": (
            real_repair_readiness_gate_source_repair_actions_executed
        ),
        "real_repair_readiness_gate_source_repair_execution_enabled": (
            real_repair_readiness_gate_source_repair_execution_enabled
        ),
        "real_repair_readiness_gate_source_repair_execution_performed": (
            real_repair_readiness_gate_source_repair_execution_performed
        ),
        "real_repair_readiness_gate_source_repair_subprocess_invoked": (
            real_repair_readiness_gate_source_repair_subprocess_invoked
        ),
        "real_repair_readiness_gate_repair_execution_enabled": (
            real_repair_readiness_gate_repair_execution_enabled
        ),
        "real_repair_readiness_gate_real_execution_enabled": (
            real_repair_readiness_gate_real_execution_enabled
        ),
        "real_repair_readiness_gate_subprocess_enabled": (
            real_repair_readiness_gate_subprocess_enabled
        ),
        "real_repair_readiness_gate_repair_execution_performed": (
            real_repair_readiness_gate_repair_execution_performed
        ),
        "real_repair_readiness_gate_repair_subprocess_invoked": (
            real_repair_readiness_gate_repair_subprocess_invoked
        ),
        "real_repair_readiness_gate_execution_performed": (
            real_repair_readiness_gate_execution_performed
        ),
        "real_repair_readiness_gate_subprocess_invoked": (
            real_repair_readiness_gate_subprocess_invoked
        ),
        "guarded_repair_execution_statuses": guarded_repair_execution_statuses,
        "guarded_repair_execution_allowed": guarded_repair_execution_allowed,
        "guarded_repair_execution_marker_observed": guarded_repair_execution_marker_observed,
        "guarded_repair_execution_exit_codes": guarded_repair_execution_exit_codes,
        "guarded_repair_execution_target_counts": guarded_repair_execution_target_counts,
        "guarded_repair_execution_next_actions": guarded_repair_execution_next_actions,
        "guarded_repair_execution_source_gate_statuses": guarded_repair_execution_source_gate_statuses,
        "guarded_repair_execution_source_feedback_statuses": guarded_repair_execution_source_feedback_statuses,
        "guarded_repair_execution_source_noop_statuses": guarded_repair_execution_source_noop_statuses,
        "guarded_repair_execution_source_ready_guarded": guarded_repair_execution_source_ready_guarded,
        "guarded_repair_execution_source_ready_repair": guarded_repair_execution_source_ready_repair,
        "guarded_repair_execution_source_would_execute": guarded_repair_execution_source_would_execute,
        "guarded_repair_execution_source_execution_performed": guarded_repair_execution_source_execution_performed,
        "guarded_repair_execution_source_subprocess_invoked": guarded_repair_execution_source_subprocess_invoked,
        "guarded_repair_execution_repair_actions_executed": guarded_repair_execution_repair_actions_executed,
        "guarded_repair_execution_repair_bundle_executed": guarded_repair_execution_repair_bundle_executed,
        "guarded_repair_execution_repair_command_executed": guarded_repair_execution_repair_command_executed,
        "guarded_repair_execution_rendered_command_executed": guarded_repair_execution_rendered_command_executed,
        "guarded_repair_execution_dry_run_command_executed": guarded_repair_execution_dry_run_command_executed,
        "guarded_repair_execution_repair_execution_enabled": guarded_repair_execution_repair_execution_enabled,
        "guarded_repair_execution_real_execution_enabled": guarded_repair_execution_real_execution_enabled,
        "guarded_repair_execution_subprocess_enabled": guarded_repair_execution_subprocess_enabled,
        "guarded_repair_execution_repair_execution_performed": guarded_repair_execution_repair_execution_performed,
        "guarded_repair_execution_repair_subprocess_invoked": guarded_repair_execution_repair_subprocess_invoked,
        "guarded_repair_execution_execution_performed": guarded_repair_execution_execution_performed,
        "guarded_repair_execution_subprocess_invoked": guarded_repair_execution_subprocess_invoked,
        "post_repair_evidence_statuses": post_repair_evidence_statuses,
        "post_repair_evidence_allowed": post_repair_evidence_allowed,
        "post_repair_evidence_enabled": post_repair_evidence_enabled,
        "post_repair_evidence_marker_observed": post_repair_evidence_marker_observed,
        "post_repair_evidence_exit_codes": post_repair_evidence_exit_codes,
        "post_repair_evidence_outcome_verified": post_repair_evidence_outcome_verified,
        "post_repair_evidence_expected_counts": post_repair_evidence_expected_counts,
        "post_repair_evidence_verified_counts": post_repair_evidence_verified_counts,
        "post_repair_evidence_missing_counts": post_repair_evidence_missing_counts,
        "post_repair_evidence_unexpected_counts": post_repair_evidence_unexpected_counts,
        "post_repair_evidence_next_actions": post_repair_evidence_next_actions,
        "post_repair_evidence_source_statuses": post_repair_evidence_source_statuses,
        "post_repair_evidence_source_allowed": post_repair_evidence_source_allowed,
        "post_repair_evidence_source_marker_observed": post_repair_evidence_source_marker_observed,
        "post_repair_evidence_source_exit_codes": post_repair_evidence_source_exit_codes,
        "post_repair_evidence_source_repair_actions_executed": post_repair_evidence_source_repair_actions_executed,
        "post_repair_evidence_source_repair_execution_enabled": post_repair_evidence_source_repair_execution_enabled,
        "post_repair_evidence_source_real_execution_enabled": post_repair_evidence_source_real_execution_enabled,
        "post_repair_evidence_source_repair_execution_performed": post_repair_evidence_source_repair_execution_performed,
        "post_repair_evidence_source_repair_subprocess_invoked": post_repair_evidence_source_repair_subprocess_invoked,
        "post_repair_evidence_execution_performed": post_repair_evidence_execution_performed,
        "post_repair_evidence_subprocess_invoked": post_repair_evidence_subprocess_invoked,
        "post_repair_evidence_repair_execution_enabled": post_repair_evidence_repair_execution_enabled,
        "post_repair_evidence_real_execution_enabled": post_repair_evidence_real_execution_enabled,
        "post_repair_evidence_repair_execution_performed": post_repair_evidence_repair_execution_performed,
        "post_repair_evidence_repair_subprocess_invoked": post_repair_evidence_repair_subprocess_invoked,
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
        "security_validation_controlled_execution_gate_statuses": summary[
            "controlled_execution_gate_statuses"
        ],
        "security_validation_controlled_execution_gate_would_execute": summary[
            "controlled_execution_gate_would_execute"
        ],
        "security_validation_controlled_execution_gate_would_execute_if_enabled": summary[
            "controlled_execution_gate_would_execute_if_enabled"
        ],
        "security_validation_controlled_execution_gate_execution_performed": summary[
            "controlled_execution_gate_execution_performed"
        ],
        "security_validation_controlled_execution_gate_reasons": summary[
            "controlled_execution_gate_reasons"
        ],
        "security_validation_controlled_execution_mock_statuses": summary[
            "controlled_execution_mock_statuses"
        ],
        "security_validation_controlled_execution_mock_performed": summary[
            "controlled_execution_mock_performed"
        ],
        "security_validation_controlled_execution_mock_subprocess_invoked": summary[
            "controlled_execution_mock_subprocess_invoked"
        ],
        "security_validation_mock_summary_statuses": summary["mock_summary_statuses"],
        "security_validation_mock_summary_reasons": summary["mock_summary_reasons"],
        "security_validation_mock_summary_performed": summary["mock_summary_performed"],
        "security_validation_mock_summary_subprocess_invoked": summary[
            "mock_summary_subprocess_invoked"
        ],
        "security_validation_controlled_execution_mock_adapter": summary[
            "controlled_execution_mock_adapter"
        ],
        "security_validation_controlled_execution_mock_adapter_mode": summary[
            "controlled_execution_mock_adapter_mode"
        ],
        "security_validation_controlled_execution_mock_adapter_result_statuses": summary[
            "controlled_execution_mock_adapter_result_statuses"
        ],
        "security_validation_controlled_execution_mock_adapter_subprocess_invoked": summary[
            "controlled_execution_mock_adapter_subprocess_invoked"
        ],
        "security_validation_controlled_execution_mock_adapter_real_execution_enabled": summary[
            "controlled_execution_mock_adapter_real_execution_enabled"
        ],
        "security_validation_controlled_execution_mock_adapter_payload_executed": summary[
            "controlled_execution_mock_adapter_payload_executed"
        ],
        "security_validation_controlled_execution_real_requested": summary[
            "controlled_execution_real_requested"
        ],
        "security_validation_controlled_execution_real_performed": summary[
            "controlled_execution_real_performed"
        ],
        "security_validation_controlled_execution_real_supported": summary[
            "controlled_execution_real_supported"
        ],
        "security_validation_controlled_execution_subprocess_invoked": summary[
            "controlled_execution_subprocess_invoked"
        ],
        "security_validation_real_preflight_statuses": summary["real_preflight_statuses"],
        "security_validation_real_preflight_reasons": summary["real_preflight_reasons"],
        "security_validation_real_preflight_requested": summary["real_preflight_requested"],
        "security_validation_real_preflight_would_execute": summary["real_preflight_would_execute"],
        "security_validation_real_preflight_execution_performed": summary["real_preflight_execution_performed"],
        "security_validation_real_preflight_subprocess_invoked": summary["real_preflight_subprocess_invoked"],
        "security_validation_real_preflight_requires_explicit_pr": summary["real_preflight_requires_explicit_pr"],
        "security_validation_real_approval_statuses": summary["real_approval_statuses"],
        "security_validation_real_approval_enabled": summary["real_approval_enabled"],
        "security_validation_real_approval_subprocess_enabled": summary[
            "real_approval_subprocess_enabled"
        ],
        "security_validation_real_approval_execution_performed": summary[
            "real_approval_execution_performed"
        ],
        "security_validation_real_approval_subprocess_invoked": summary[
            "real_approval_subprocess_invoked"
        ],
        "security_validation_real_approval_transition_statuses": summary[
            "real_approval_transition_statuses"
        ],
        "security_validation_real_approval_transition_enabled": summary[
            "real_approval_transition_enabled"
        ],
        "security_validation_real_approval_transition_subprocess_enabled": summary[
            "real_approval_transition_subprocess_enabled"
        ],
        "security_validation_real_approval_transition_execution_performed": summary[
            "real_approval_transition_execution_performed"
        ],
        "security_validation_real_approval_transition_subprocess_invoked": summary[
            "real_approval_transition_subprocess_invoked"
        ],
        "security_validation_real_final_gate_statuses": summary[
            "real_final_gate_statuses"
        ],
        "security_validation_real_final_gate_would_execute": summary[
            "real_final_gate_would_execute"
        ],
        "security_validation_real_final_gate_ready": summary[
            "real_final_gate_ready"
        ],
        "security_validation_real_final_gate_real_execution_enabled": summary[
            "real_final_gate_real_execution_enabled"
        ],
        "security_validation_real_final_gate_subprocess_enabled": summary[
            "real_final_gate_subprocess_enabled"
        ],
        "security_validation_real_final_gate_execution_performed": summary[
            "real_final_gate_execution_performed"
        ],
        "security_validation_real_final_gate_subprocess_invoked": summary[
            "real_final_gate_subprocess_invoked"
        ],
        "security_validation_real_dry_run_envelope_dry_run_only": summary[
            "real_dry_run_envelope_dry_run_only"
        ],
        "security_validation_real_dry_run_envelope_would_execute": summary[
            "real_dry_run_envelope_would_execute"
        ],
        "security_validation_real_dry_run_envelope_ready": summary[
            "real_dry_run_envelope_ready"
        ],
        "security_validation_real_dry_run_envelope_real_execution_enabled": summary[
            "real_dry_run_envelope_real_execution_enabled"
        ],
        "security_validation_real_dry_run_envelope_subprocess_enabled": summary[
            "real_dry_run_envelope_subprocess_enabled"
        ],
        "security_validation_real_dry_run_envelope_execution_performed": summary[
            "real_dry_run_envelope_execution_performed"
        ],
        "security_validation_real_dry_run_envelope_subprocess_invoked": summary[
            "real_dry_run_envelope_subprocess_invoked"
        ],
        "security_validation_real_noop_result_noop_only": summary[
            "real_noop_result_noop_only"
        ],
        "security_validation_real_noop_result_rendered_command_executed": summary[
            "real_noop_result_rendered_command_executed"
        ],
        "security_validation_real_noop_result_dry_run_command_executed": summary[
            "real_noop_result_dry_run_command_executed"
        ],
        "security_validation_real_noop_result_real_execution_enabled": summary[
            "real_noop_result_real_execution_enabled"
        ],
        "security_validation_real_noop_result_subprocess_invoked": summary[
            "real_noop_result_subprocess_invoked"
        ],
        "security_validation_real_noop_result_execution_performed": summary[
            "real_noop_result_execution_performed"
        ],
        "security_validation_real_noop_result_exit_codes": summary[
            "real_noop_result_exit_codes"
        ],
        "security_validation_real_read_only_promotion_statuses": summary[
            "real_read_only_promotion_statuses"
        ],
        "security_validation_real_read_only_promotion_candidates": summary[
            "real_read_only_promotion_candidates"
        ],
        "security_validation_real_read_only_promotion_command_parse_valid": summary[
            "real_read_only_promotion_command_parse_valid"
        ],
        "security_validation_real_read_only_promotion_stdout_marker_observed": summary[
            "real_read_only_promotion_stdout_marker_observed"
        ],
        "security_validation_real_read_only_promotion_noop_exit_codes": summary[
            "real_read_only_promotion_noop_exit_codes"
        ],
        "security_validation_real_read_only_promotion_rendered_command_executed": summary[
            "real_read_only_promotion_rendered_command_executed"
        ],
        "security_validation_real_read_only_promotion_dry_run_command_executed": summary[
            "real_read_only_promotion_dry_run_command_executed"
        ],
        "security_validation_real_read_only_promotion_real_execution_enabled": summary[
            "real_read_only_promotion_real_execution_enabled"
        ],
        "security_validation_real_read_only_promotion_subprocess_invoked": summary[
            "real_read_only_promotion_subprocess_invoked"
        ],
        "security_validation_real_read_only_promotion_execution_performed": summary[
            "real_read_only_promotion_execution_performed"
        ],
        "security_validation_real_read_only_final_gate_statuses": summary[
            "real_read_only_final_gate_statuses"
        ],
        "security_validation_real_read_only_final_gate_preconditions_satisfied": summary[
            "real_read_only_final_gate_preconditions_satisfied"
        ],
        "security_validation_real_read_only_final_gate_ready": summary[
            "real_read_only_final_gate_ready"
        ],
        "security_validation_real_read_only_final_gate_would_execute": summary[
            "real_read_only_final_gate_would_execute"
        ],
        "security_validation_real_read_only_final_gate_read_only_execution_enabled": summary[
            "real_read_only_final_gate_read_only_execution_enabled"
        ],
        "security_validation_real_read_only_final_gate_subprocess_invoked": summary[
            "real_read_only_final_gate_subprocess_invoked"
        ],
        "security_validation_real_read_only_final_gate_execution_performed": summary[
            "real_read_only_final_gate_execution_performed"
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
    
    if record_type == "replay_lifecycle_retry_mock_execution_summary":
        return str(
            record.get("mock_execution_summary_id")
            or record.get("controlled_execution_result_id")
            or record.get("source_controlled_execution_result_id")
            or ""
        ).strip()
    
    if record_type == "replay_lifecycle_retry_real_execution_preflight":
        return str(
            record.get("real_execution_preflight_id")
            or record.get("controlled_execution_result_id")
            or record.get("rendered_command_id")
            or ""
        ).strip()
    
    if record_type == "replay_lifecycle_retry_real_execution_approval":
        return str(
            record.get("real_execution_approval_id")
            or record.get("real_execution_preflight_id")
            or record.get("controlled_execution_result_id")
            or ""
        ).strip()
    
    if record_type == "replay_lifecycle_retry_real_execution_approval_transition":
        return str(
            record.get("real_execution_approval_transition_id")
            or record.get("real_execution_approval_id")
            or record.get("real_execution_preflight_id")
            or ""
        ).strip()
    
    if record_type == "replay_lifecycle_retry_real_execution_final_gate":
        return str(
            record.get("real_execution_final_gate_id")
            or record.get("real_execution_approval_transition_id")
            or record.get("real_execution_approval_id")
            or ""
        ).strip()
    
    if record_type == "replay_lifecycle_retry_real_execution_dry_run_envelope":
        return str(
            record.get("real_execution_dry_run_envelope_id")
            or record.get("real_execution_final_gate_id")
            or record.get("real_execution_approval_transition_id")
            or ""
        ).strip()
    
    if record_type == "replay_lifecycle_retry_real_execution_noop_result":
        return str(
            record.get("real_execution_noop_result_id")
            or record.get("real_execution_dry_run_envelope_id")
            or record.get("real_execution_final_gate_id")
            or ""
        ).strip()
    
    if record_type == "replay_lifecycle_retry_real_execution_read_only_promotion":
        return str(
            record.get("real_execution_read_only_promotion_id")
            or record.get("real_execution_noop_result_id")
            or record.get("real_execution_dry_run_envelope_id")
            or ""
        ).strip()
    
    if record_type == "replay_lifecycle_retry_real_execution_read_only_final_gate":
        return str(
            record.get("real_execution_read_only_final_gate_id")
            or record.get("real_execution_read_only_promotion_id")
            or record.get("real_execution_noop_result_id")
            or ""
        ).strip()
    
    if record_type == "replay_lifecycle_retry_real_execution_read_only_approval":
        return str(
            record.get("real_execution_read_only_approval_id")
            or record.get("real_execution_read_only_final_gate_id")
            or record.get("real_execution_read_only_promotion_id")
            or ""
        ).strip()
    
    if record_type == "replay_lifecycle_retry_real_execution_read_only_approval_transition":
        return str(
            record.get("real_execution_read_only_approval_transition_id")
            or record.get("real_execution_read_only_approval_id")
            or record.get("real_execution_read_only_final_gate_id")
            or ""
        ).strip()
    
    if record_type == "replay_lifecycle_retry_real_execution_read_only_readiness_gate":
        return str(
            record.get("real_execution_read_only_readiness_gate_id")
            or record.get("real_execution_read_only_approval_transition_id")
            or record.get("real_execution_read_only_approval_id")
            or ""
        ).strip()
    
    if record_type == "replay_lifecycle_retry_real_execution_read_only_execution_result":
        return str(
            record.get("real_execution_read_only_execution_result_id")
            or record.get("real_execution_read_only_readiness_gate_id")
            or record.get("rendered_command_id")
            or ""
        ).strip()
    
    if record_type == "replay_lifecycle_retry_real_execution_read_only_feedback":
        return str(
            record.get("real_execution_read_only_feedback_id")
            or record.get("real_execution_read_only_execution_result_id")
            or record.get("real_execution_read_only_readiness_gate_id")
            or ""
        ).strip()
    
    if record_type == "replay_lifecycle_retry_real_execution_read_only_repair_plan":
        return str(
            record.get("real_execution_read_only_repair_plan_id")
            or record.get("real_execution_read_only_feedback_id")
            or record.get("real_execution_read_only_execution_result_id")
            or ""
        ).strip()
    
    if (
        record_type
        == "replay_lifecycle_retry_real_execution_read_only_repair_action_bundle"
    ):
        return str(
            record.get("real_execution_read_only_repair_action_bundle_id")
            or record.get("real_execution_read_only_repair_plan_id")
            or record.get("real_execution_read_only_feedback_id")
            or ""
        ).strip()
    
    if (
        record_type
        == "replay_lifecycle_retry_real_execution_read_only_repair_action_bundle_review"
    ):
        return str(
            record.get("real_execution_read_only_repair_action_bundle_review_id")
            or record.get("real_execution_read_only_repair_action_bundle_id")
            or record.get("real_execution_read_only_repair_plan_id")
            or ""
        ).strip()
    
    if record_type == "replay_lifecycle_retry_real_execution_repair_approval":
        return str(
            record.get("real_execution_repair_approval_id")
            or record.get("real_execution_read_only_repair_action_bundle_review_id")
            or record.get("real_execution_read_only_repair_action_bundle_id")
            or ""
        ).strip()
    
    if (
        record_type
        == "replay_lifecycle_retry_real_execution_repair_approval_transition"
    ):
        return str(
            record.get("real_execution_repair_approval_transition_id")
            or record.get("real_execution_repair_approval_id")
            or record.get("real_execution_read_only_repair_action_bundle_review_id")
            or ""
        ).strip()
    
    if record_type == "replay_lifecycle_retry_real_execution_repair_final_gate":
        return str(
            record.get("real_execution_repair_final_gate_id")
            or record.get("real_execution_repair_approval_transition_id")
            or record.get("real_execution_repair_approval_id")
            or ""
        ).strip()
    
    if (
        record_type
        == "replay_lifecycle_retry_real_execution_repair_dry_run_envelope"
    ):
        return str(
            record.get("real_execution_repair_dry_run_envelope_id")
            or record.get("real_execution_repair_final_gate_id")
            or record.get("real_execution_repair_approval_transition_id")
            or ""
        ).strip()
    
    if record_type == "replay_lifecycle_retry_real_execution_repair_noop_result":
        return str(
            record.get("real_execution_repair_noop_result_id")
            or record.get("real_execution_repair_dry_run_envelope_id")
            or record.get("real_execution_repair_final_gate_id")
            or ""
        ).strip()
    
    if record_type == "replay_lifecycle_retry_real_execution_repair_noop_feedback":
        return str(
            record.get("real_execution_repair_noop_feedback_id")
            or record.get("real_execution_repair_noop_result_id")
            or record.get("real_execution_repair_dry_run_envelope_id")
            or ""
        ).strip()
    
    if record_type == "replay_lifecycle_retry_real_execution_repair_readiness_gate":
        return str(
            record.get("real_execution_repair_readiness_gate_id")
            or record.get("real_execution_repair_noop_feedback_id")
            or record.get("real_execution_repair_noop_result_id")
            or ""
        ).strip()
    
    if record_type == "replay_lifecycle_retry_guarded_repair_execution_result":
        return str(
            record.get("guarded_repair_execution_result_id")
            or record.get("real_execution_repair_readiness_gate_id")
            or ""
        ).strip()
    
    if record_type == "replay_lifecycle_retry_post_repair_evidence_check":
        return str(
            record.get("post_repair_evidence_check_id")
            or record.get("guarded_repair_execution_result_id")
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
        "real_execution_preflight_id",
        "real_execution_approval_id",
        "real_execution_approval_transition_id",
        "real_execution_final_gate_id",
        "real_execution_dry_run_envelope_id",
        "real_execution_noop_result_id",
        "real_execution_read_only_promotion_id",
        "real_execution_read_only_final_gate_id",
        "real_execution_read_only_approval_id",
        "real_execution_read_only_approval_transition_id",
        "real_execution_read_only_readiness_gate_id",
        "real_execution_read_only_execution_result_id",
        "real_execution_read_only_feedback_id",
        "real_execution_read_only_repair_plan_id",
        "real_execution_read_only_repair_action_bundle_id",
        "real_execution_read_only_repair_action_bundle_review_id",
        "real_execution_repair_approval_id",
        "real_execution_repair_approval_transition_id",
        "real_execution_repair_final_gate_id",
        "real_execution_repair_dry_run_envelope_id",
        "real_execution_repair_noop_result_id",
        "real_execution_repair_noop_feedback_id",
        "real_execution_repair_readiness_gate_id",
        "guarded_repair_execution_result_id",
        "post_repair_evidence_check_id",
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
            "real_execution_preflight_id",
            "real_execution_approval_id",
            "real_execution_approval_transition_id",
            "real_execution_final_gate_id",
            "real_execution_dry_run_envelope_id",
            "real_execution_noop_result_id",
            "real_execution_read_only_promotion_id",
            "real_execution_read_only_final_gate_id",
            "real_execution_read_only_approval_id",
            "real_execution_read_only_approval_transition_id",
            "real_execution_read_only_readiness_gate_id",
            "real_execution_read_only_execution_result_id",
            "real_execution_read_only_feedback_id",
            "real_execution_read_only_repair_plan_id",
            "real_execution_read_only_repair_action_bundle_id",
            "real_execution_read_only_repair_action_bundle_review_id",
            "real_execution_repair_approval_id",
            "real_execution_repair_approval_transition_id",
            "real_execution_repair_final_gate_id",
            "real_execution_repair_dry_run_envelope_id",
            "real_execution_repair_noop_result_id",
            "real_execution_repair_noop_feedback_id",
            "real_execution_repair_readiness_gate_id",
            "guarded_repair_execution_result_id",
            "post_repair_evidence_check_id",
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

    gate_evaluation = record.get("gate_evaluation")
    if not isinstance(gate_evaluation, Mapping):
        gate_evaluation = payload_mapping.get("gate_evaluation")

    gate_mapping = gate_evaluation if isinstance(gate_evaluation, Mapping) else {}
    gate_status = str(gate_mapping.get("gate_status") or "unknown").strip() or "unknown"
    gate_would_execute = bool(gate_mapping.get("would_execute"))
    gate_would_execute_if_enabled = bool(gate_mapping.get("would_execute_if_enabled"))
    gate_execution_performed = bool(gate_mapping.get("execution_performed"))
    gate_reasons = gate_mapping.get("reasons")
    gate_reason_list = [
        str(item).strip()
        for item in gate_reasons
        if str(item).strip()
    ] if isinstance(gate_reasons, list) else []

    mock_execution = record.get("mock_execution")
    if not isinstance(mock_execution, Mapping):
        mock_execution = payload_mapping.get("mock_execution")

    mock_mapping = mock_execution if isinstance(mock_execution, Mapping) else {}
    mock_status = str(mock_mapping.get("status") or "none").strip() or "none"

    mock_payload = mock_mapping.get("mock_execution")
    mock_payload_mapping = mock_payload if isinstance(mock_payload, Mapping) else {}

    mock_performed = bool(mock_payload_mapping.get("performed"))
    mock_subprocess_invoked = bool(mock_payload_mapping.get("subprocess_invoked"))

    adapter_result = mock_payload_mapping.get("adapter_result")
    adapter_result_mapping = (
        adapter_result if isinstance(adapter_result, Mapping) else {}
    )
    adapter_result_payload = adapter_result_mapping.get("payload")
    adapter_result_payload_mapping = (
        adapter_result_payload if isinstance(adapter_result_payload, Mapping) else {}
    )

    adapter_name = str(adapter_result_mapping.get("adapter") or "none").strip() or "none"
    adapter_mode = str(adapter_result_mapping.get("mode") or "none").strip() or "none"
    adapter_result_status = (
        str(adapter_result_mapping.get("status") or "none").strip() or "none"
    )
    adapter_result_subprocess_invoked = bool(
        adapter_result_mapping.get("subprocess_invoked")
    )
    adapter_result_real_execution_enabled = bool(
        adapter_result_mapping.get("real_execution_enabled")
    )
    adapter_result_payload_executed = bool(
        adapter_result_payload_mapping.get("executed")
    )

    real_execution_requested = bool(record.get("real_execution_requested"))
    real_execution_performed = bool(record.get("real_execution_performed"))
    real_execution_supported = bool(record.get("real_execution_supported"))
    subprocess_invoked = bool(record.get("subprocess_invoked"))

    payload_real_execution_requested = bool(
        payload_mapping.get("real_execution_requested")
    )
    payload_real_execution_performed = bool(
        payload_mapping.get("real_execution_performed")
    )
    payload_real_execution_supported = bool(
        payload_mapping.get("real_execution_supported")
    )
    payload_subprocess_invoked = bool(payload_mapping.get("subprocess_invoked"))

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
        "real_execution_not_supported",
    }:
        reasons.append("invalid_reason")

    if timeout_profile and timeout_profile not in {"standard", "patient"}:
        reasons.append("invalid_timeout_profile")

    if decision_mode and decision_mode not in {"manual", "policy"}:
        reasons.append("invalid_decision_mode")

    if not gate_mapping:
        reasons.append("missing_gate_evaluation")

    if gate_would_execute:
        reasons.append("gate_would_execute_must_remain_false")

    if gate_execution_performed:
        reasons.append("gate_must_not_perform_execution")

    if mock_subprocess_invoked:
        reasons.append("mock_execution_must_not_invoke_subprocess")

    if mock_performed and payload_executed:
        reasons.append("mock_execution_must_not_set_payload_executed")

    if mock_performed and not adapter_result_mapping:
        reasons.append("missing_mock_adapter_result")

    if adapter_result_mapping:
        if adapter_name != "mock":
            reasons.append("mock_adapter_result_must_use_mock_adapter")
        if adapter_mode != "mock":
            reasons.append("mock_adapter_result_must_use_mock_mode")
        if adapter_result_subprocess_invoked:
            reasons.append("mock_adapter_result_must_not_invoke_subprocess")
        if adapter_result_real_execution_enabled:
            reasons.append("mock_adapter_result_must_not_enable_real_execution")
        if adapter_result_payload_executed:
            reasons.append("mock_adapter_result_payload_must_not_execute")

    if real_execution_performed or payload_real_execution_performed:
        reasons.append("real_execution_must_not_be_performed")
    if real_execution_supported or payload_real_execution_supported:
        reasons.append("real_execution_must_not_be_supported")
    if subprocess_invoked or payload_subprocess_invoked:
        reasons.append("controlled_execution_must_not_invoke_subprocess")
    if real_execution_requested and reason != "real_execution_not_supported":
        reasons.append("real_execution_request_must_be_rejected_as_not_supported")
    if (
        payload_real_execution_requested
        and payload_mapping.get("reason") != "real_execution_not_supported"
    ):
        reasons.append("payload_real_execution_request_must_be_rejected_as_not_supported")

    # PR 28.2 skeleton phase: execution is not implemented yet.
    if status == "executed":
        reasons.append("controlled_execution_not_allowed_yet")

    if reason == "controlled_execution_not_implemented" and status != "rejected":
        reasons.append("not_implemented_result_must_be_rejected")

    if reason == "controlled_execution_not_implemented" and payload_executed:
        reasons.append("not_implemented_result_must_not_execute")

    if operator_authorized and payload_executed:
        reasons.append("operator_authorized_result_must_not_execute_yet")

    # operator_authorized may be true once the operator explicitly provides
    # --allow-controlled-execution. In PR 29.3 it records intent only and is
    # valid as long as the result remains rejected and payload.executed=false.

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
        "gate_status": gate_status,
        "gate_would_execute": gate_would_execute,
        "gate_would_execute_if_enabled": gate_would_execute_if_enabled,
        "gate_execution_performed": gate_execution_performed,
        "gate_reasons": gate_reason_list,
        "mock_execution_status": mock_status,
        "mock_execution_performed": mock_performed,
        "mock_subprocess_invoked": mock_subprocess_invoked,
        "mock_adapter": adapter_name,
        "mock_adapter_mode": adapter_mode,
        "mock_adapter_result_status": adapter_result_status,
        "mock_adapter_subprocess_invoked": adapter_result_subprocess_invoked,
        "mock_adapter_real_execution_enabled": adapter_result_real_execution_enabled,
        "mock_adapter_payload_executed": adapter_result_payload_executed,
        "real_execution_requested": real_execution_requested,
        "real_execution_performed": real_execution_performed,
        "real_execution_supported": real_execution_supported,
        "subprocess_invoked": subprocess_invoked,
    }


def validate_replay_lifecycle_retry_mock_execution_summary(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate derived controlled mock execution summary records."""
    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    summary_id = str(record.get("mock_execution_summary_id") or "").strip()
    controlled_execution_result_id = str(
        record.get("controlled_execution_result_id")
        or record.get("source_controlled_execution_result_id")
        or ""
    ).strip()
    status = str(record.get("status") or "").strip()
    reason = str(record.get("reason") or "").strip()

    mock_performed = bool(record.get("mock_performed"))
    subprocess_invoked = bool(record.get("subprocess_invoked"))
    real_execution_enabled = bool(record.get("real_execution_enabled"))
    payload_executed = bool(payload_mapping.get("executed"))
    derived = bool(record.get("derived"))

    reasons: list[str] = []

    if not summary_id:
        reasons.append("missing_mock_execution_summary_id")
    if not controlled_execution_result_id:
        reasons.append("missing_controlled_execution_result_id")
    if status not in {"mock_executed", "blocked"}:
        reasons.append("invalid_mock_summary_status")
    if status == "mock_executed" and reason != "mock_execution_completed":
        reasons.append("invalid_mock_summary_reason")
    if status == "mock_executed" and not mock_performed:
        reasons.append("mock_summary_status_requires_mock_performed")
    if subprocess_invoked:
        reasons.append("mock_summary_must_not_invoke_subprocess")
    if real_execution_enabled:
        reasons.append("mock_summary_must_not_enable_real_execution")
    if payload_executed:
        reasons.append("mock_summary_payload_must_not_execute")
    if not derived:
        reasons.append("mock_summary_must_be_derived")

    return {
        "type": "security_validation_result",
        "record_type": "replay_lifecycle_retry_mock_execution_summary",
        "valid": not reasons,
        "severity": "critical" if reasons else "info",
        "reasons": reasons,
        "subject": summary_id or controlled_execution_result_id,
        "status": status,
        "reason": reason,
        "mock_performed": mock_performed,
        "subprocess_invoked": subprocess_invoked,
        "real_execution_enabled": real_execution_enabled,
        "payload_executed": payload_executed,
        "derived": derived,
    }


def validate_replay_lifecycle_retry_real_execution_preflight(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate fail-closed real execution preflight records."""
    reasons: list[str] = []

    preflight_id = str(record.get("real_execution_preflight_id") or "").strip()
    controlled_execution_result_id = str(
        record.get("controlled_execution_result_id") or ""
    ).strip()
    rendered_command_id = str(record.get("rendered_command_id") or "").strip()
    status = str(record.get("status") or "").strip()
    reason = str(record.get("reason") or "").strip()

    real_execution_requested = bool(record.get("real_execution_requested"))
    would_execute = bool(record.get("would_execute"))
    execution_performed = bool(record.get("execution_performed"))
    subprocess_invoked = bool(record.get("subprocess_invoked"))
    real_execution_supported = bool(record.get("real_execution_supported"))
    subprocess_supported = bool(record.get("subprocess_supported"))
    real_adapter_runnable = bool(record.get("real_adapter_runnable"))
    real_adapter_requires_explicit_pr = bool(
        record.get("real_adapter_requires_explicit_pr")
    )

    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    if not preflight_id:
        reasons.append("missing_real_execution_preflight_id")
    if not controlled_execution_result_id:
        reasons.append("missing_controlled_execution_result_id")
    if not rendered_command_id:
        reasons.append("missing_rendered_command_id")
    if status != "blocked":
        reasons.append("real_preflight_must_remain_blocked")
    if reason not in {
        "real_execution_request_missing",
        "operator_authorization_missing",
        "command_not_allowlisted",
        "command_parse_invalid",
        "command_parse_not_allowlisted",
        "real_execution_not_supported",
        "subprocess_not_supported",
        "real_adapter_not_runnable",
        "real_adapter_requires_explicit_pr",
    }:
        reasons.append("invalid_real_preflight_reason")
    if would_execute:
        reasons.append("real_preflight_must_not_would_execute")
    if execution_performed:
        reasons.append("real_preflight_must_not_execute")
    if subprocess_invoked:
        reasons.append("real_preflight_must_not_invoke_subprocess")
    if real_execution_supported:
        reasons.append("real_preflight_must_not_support_real_execution")
    if subprocess_supported:
        reasons.append("real_preflight_must_not_support_subprocess")
    if real_adapter_runnable:
        reasons.append("real_preflight_adapter_must_not_be_runnable")
    if not real_adapter_requires_explicit_pr:
        reasons.append("real_preflight_must_require_explicit_pr")

    if bool(payload_mapping.get("would_execute")):
        reasons.append("payload_real_preflight_must_not_would_execute")
    if bool(payload_mapping.get("execution_performed")):
        reasons.append("payload_real_preflight_must_not_execute")
    if bool(payload_mapping.get("subprocess_invoked")):
        reasons.append("payload_real_preflight_must_not_invoke_subprocess")

    return {
        "type": "security_validation_result",
        "record_type": "replay_lifecycle_retry_real_execution_preflight",
        "valid": not reasons,
        "severity": "info" if not reasons else "critical",
        "reasons": reasons,
        "subject": preflight_id,
        "status": status,
        "reason": reason,
        "real_execution_requested": real_execution_requested,
        "would_execute": would_execute,
        "execution_performed": execution_performed,
        "subprocess_invoked": subprocess_invoked,
        "real_execution_supported": real_execution_supported,
        "subprocess_supported": subprocess_supported,
        "real_adapter_runnable": real_adapter_runnable,
        "real_adapter_requires_explicit_pr": real_adapter_requires_explicit_pr,
    }


def validate_replay_lifecycle_retry_real_execution_approval(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate explicit fail-closed real execution approval records."""
    reasons: list[str] = []

    real_execution_approval_id = str(
        record.get("real_execution_approval_id") or ""
    ).strip()
    real_execution_preflight_id = str(
        record.get("real_execution_preflight_id") or ""
    ).strip()
    controlled_execution_result_id = str(
        record.get("controlled_execution_result_id") or ""
    ).strip()
    rendered_command_id = str(record.get("rendered_command_id") or "").strip()
    approval_status = str(record.get("approval_status") or "").strip().lower()
    reason = str(record.get("reason") or "").strip()

    operator_authorized = bool(record.get("operator_authorized"))
    real_execution_requested = bool(record.get("real_execution_requested"))
    real_execution_enabled = bool(record.get("real_execution_enabled"))
    subprocess_enabled = bool(record.get("subprocess_enabled"))
    execution_performed = bool(record.get("execution_performed"))
    subprocess_invoked = bool(record.get("subprocess_invoked"))

    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    if not real_execution_approval_id:
        reasons.append("missing_real_execution_approval_id")
    if not real_execution_preflight_id:
        reasons.append("missing_real_execution_preflight_id")
    if not controlled_execution_result_id:
        reasons.append("missing_controlled_execution_result_id")
    if not rendered_command_id:
        reasons.append("missing_rendered_command_id")

    if approval_status not in {"pending", "approved", "rejected"}:
        reasons.append("invalid_real_execution_approval_status")

    if reason not in {
        "real_execution_explicit_approval_required",
        "real_execution_explicit_approval_rejected",
    }:
        reasons.append("invalid_real_execution_approval_reason")

    if real_execution_enabled or bool(payload_mapping.get("real_execution_enabled")):
        reasons.append("real_execution_approval_must_not_enable_real_execution")
    if subprocess_enabled or bool(payload_mapping.get("subprocess_enabled")):
        reasons.append("real_execution_approval_must_not_enable_subprocess")
    if execution_performed or bool(payload_mapping.get("execution_performed")):
        reasons.append("real_execution_approval_must_not_execute")
    if subprocess_invoked or bool(payload_mapping.get("subprocess_invoked")):
        reasons.append("real_execution_approval_must_not_invoke_subprocess")

    if approval_status == "approved" and reason != "real_execution_explicit_approval_required":
        reasons.append("approved_real_execution_approval_must_remain_required_only")

    return {
        "type": "security_validation_result",
        "record_type": "replay_lifecycle_retry_real_execution_approval",
        "valid": not reasons,
        "severity": "critical" if reasons else "info",
        "reasons": reasons,
        "subject": real_execution_approval_id or real_execution_preflight_id,
        "approval_status": approval_status or "unknown",
        "reason": reason or "unknown",
        "operator_authorized": operator_authorized,
        "real_execution_requested": real_execution_requested,
        "real_execution_enabled": real_execution_enabled,
        "subprocess_enabled": subprocess_enabled,
        "execution_performed": execution_performed,
        "subprocess_invoked": subprocess_invoked,
    }


def validate_replay_lifecycle_retry_real_execution_approval_transition(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable fail-closed real execution approval transitions."""
    reasons: list[str] = []

    transition_id = str(
        record.get("real_execution_approval_transition_id") or ""
    ).strip()
    real_execution_approval_id = str(
        record.get("real_execution_approval_id") or ""
    ).strip()
    real_execution_preflight_id = str(
        record.get("real_execution_preflight_id") or ""
    ).strip()
    controlled_execution_result_id = str(
        record.get("controlled_execution_result_id") or ""
    ).strip()
    rendered_command_id = str(record.get("rendered_command_id") or "").strip()
    from_status = str(record.get("from_status") or "").strip().lower()
    to_status = str(record.get("to_status") or "").strip().lower()
    reason = str(record.get("reason") or "").strip()

    real_execution_enabled = bool(record.get("real_execution_enabled"))
    subprocess_enabled = bool(record.get("subprocess_enabled"))
    execution_performed = bool(record.get("execution_performed"))
    subprocess_invoked = bool(record.get("subprocess_invoked"))

    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    if not transition_id:
        reasons.append("missing_real_execution_approval_transition_id")
    if not real_execution_approval_id:
        reasons.append("missing_real_execution_approval_id")
    if not real_execution_preflight_id:
        reasons.append("missing_real_execution_preflight_id")
    if not controlled_execution_result_id:
        reasons.append("missing_controlled_execution_result_id")
    if not rendered_command_id:
        reasons.append("missing_rendered_command_id")

    if from_status != "pending":
        reasons.append("real_approval_transition_must_start_from_pending")
    if to_status not in {"approved", "rejected"}:
        reasons.append("invalid_real_approval_transition_to_status")
    if from_status == to_status:
        reasons.append("real_approval_transition_must_change_status")
    if reason != "real_execution_approval_transition_recorded":
        reasons.append("invalid_real_approval_transition_reason")

    if real_execution_enabled or bool(payload_mapping.get("real_execution_enabled")):
        reasons.append("real_approval_transition_must_not_enable_real_execution")
    if subprocess_enabled or bool(payload_mapping.get("subprocess_enabled")):
        reasons.append("real_approval_transition_must_not_enable_subprocess")
    if execution_performed or bool(payload_mapping.get("execution_performed")):
        reasons.append("real_approval_transition_must_not_execute")
    if subprocess_invoked or bool(payload_mapping.get("subprocess_invoked")):
        reasons.append("real_approval_transition_must_not_invoke_subprocess")

    return {
        "type": "security_validation_result",
        "record_type": "replay_lifecycle_retry_real_execution_approval_transition",
        "valid": not reasons,
        "severity": "critical" if reasons else "info",
        "reasons": reasons,
        "subject": transition_id or real_execution_approval_id,
        "from_status": from_status or "unknown",
        "to_status": to_status or "unknown",
        "reason": reason or "unknown",
        "real_execution_enabled": real_execution_enabled,
        "subprocess_enabled": subprocess_enabled,
        "execution_performed": execution_performed,
        "subprocess_invoked": subprocess_invoked,
    }


def validate_replay_lifecycle_retry_real_execution_final_gate(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate fail-closed final real execution gate records."""
    reasons: list[str] = []

    final_gate_id = str(record.get("real_execution_final_gate_id") or "").strip()
    transition_id = str(
        record.get("real_execution_approval_transition_id") or ""
    ).strip()
    real_execution_approval_id = str(
        record.get("real_execution_approval_id") or ""
    ).strip()
    real_execution_preflight_id = str(
        record.get("real_execution_preflight_id") or ""
    ).strip()
    controlled_execution_result_id = str(
        record.get("controlled_execution_result_id") or ""
    ).strip()
    rendered_command_id = str(record.get("rendered_command_id") or "").strip()
    gate_status = str(record.get("gate_status") or "").strip()
    from_status = str(record.get("from_status") or "").strip().lower()
    to_status = str(record.get("to_status") or "").strip().lower()

    would_execute = bool(record.get("would_execute"))
    ready_for_real_execution = bool(record.get("ready_for_real_execution"))
    real_adapter_supported = bool(record.get("real_adapter_supported"))
    real_adapter_runnable = bool(record.get("real_adapter_runnable"))
    subprocess_supported = bool(record.get("subprocess_supported"))
    real_execution_enabled = bool(record.get("real_execution_enabled"))
    subprocess_enabled = bool(record.get("subprocess_enabled"))
    execution_performed = bool(record.get("execution_performed"))
    subprocess_invoked = bool(record.get("subprocess_invoked"))

    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    gate_reasons_raw = record.get("reasons")
    gate_reasons = [
        str(item).strip()
        for item in gate_reasons_raw
        if str(item).strip()
    ] if isinstance(gate_reasons_raw, list) else []

    if not final_gate_id:
        reasons.append("missing_real_execution_final_gate_id")
    if not transition_id:
        reasons.append("missing_real_execution_approval_transition_id")
    if not real_execution_approval_id:
        reasons.append("missing_real_execution_approval_id")
    if not real_execution_preflight_id:
        reasons.append("missing_real_execution_preflight_id")
    if not controlled_execution_result_id:
        reasons.append("missing_controlled_execution_result_id")
    if not rendered_command_id:
        reasons.append("missing_rendered_command_id")

    if from_status != "pending":
        reasons.append("real_final_gate_requires_pending_source_transition")
    if to_status != "approved":
        reasons.append("real_final_gate_requires_approved_transition")

    if gate_status != "blocked":
        reasons.append("real_final_gate_must_remain_blocked")
    if would_execute or bool(payload_mapping.get("would_execute")):
        reasons.append("real_final_gate_would_execute_must_remain_false")
    if ready_for_real_execution or bool(
        payload_mapping.get("ready_for_real_execution")
    ):
        reasons.append("real_final_gate_must_not_be_ready")
    if real_adapter_supported or bool(payload_mapping.get("real_adapter_supported")):
        reasons.append("real_final_gate_must_not_support_real_adapter")
    if real_adapter_runnable or bool(payload_mapping.get("real_adapter_runnable")):
        reasons.append("real_final_gate_must_not_make_real_adapter_runnable")
    if subprocess_supported or bool(payload_mapping.get("subprocess_supported")):
        reasons.append("real_final_gate_must_not_support_subprocess")
    if real_execution_enabled or bool(payload_mapping.get("real_execution_enabled")):
        reasons.append("real_final_gate_must_not_enable_real_execution")
    if subprocess_enabled or bool(payload_mapping.get("subprocess_enabled")):
        reasons.append("real_final_gate_must_not_enable_subprocess")
    if execution_performed or bool(payload_mapping.get("execution_performed")):
        reasons.append("real_final_gate_must_not_execute")
    if subprocess_invoked or bool(payload_mapping.get("subprocess_invoked")):
        reasons.append("real_final_gate_must_not_invoke_subprocess")

    for required_reason in (
        "real_adapter_not_supported",
        "subprocess_not_supported",
        "explicit_execution_pr_required",
    ):
        if required_reason not in gate_reasons:
            reasons.append(f"missing_real_final_gate_reason:{required_reason}")

    return {
        "type": "security_validation_result",
        "record_type": "replay_lifecycle_retry_real_execution_final_gate",
        "valid": not reasons,
        "severity": "critical" if reasons else "info",
        "reasons": reasons,
        "subject": final_gate_id or transition_id,
        "gate_status": gate_status or "unknown",
        "from_status": from_status or "unknown",
        "to_status": to_status or "unknown",
        "would_execute": would_execute,
        "ready_for_real_execution": ready_for_real_execution,
        "real_adapter_supported": real_adapter_supported,
        "real_adapter_runnable": real_adapter_runnable,
        "subprocess_supported": subprocess_supported,
        "real_execution_enabled": real_execution_enabled,
        "subprocess_enabled": subprocess_enabled,
        "execution_performed": execution_performed,
        "subprocess_invoked": subprocess_invoked,
        "gate_reasons": gate_reasons,
    }


def validate_replay_lifecycle_retry_real_execution_dry_run_envelope(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate no-subprocess real execution dry-run envelope records."""
    reasons: list[str] = []

    envelope_id = str(
        record.get("real_execution_dry_run_envelope_id") or ""
    ).strip()
    final_gate_id = str(record.get("real_execution_final_gate_id") or "").strip()
    transition_id = str(
        record.get("real_execution_approval_transition_id") or ""
    ).strip()
    approval_id = str(record.get("real_execution_approval_id") or "").strip()
    preflight_id = str(record.get("real_execution_preflight_id") or "").strip()
    controlled_result_id = str(
        record.get("controlled_execution_result_id") or ""
    ).strip()
    rendered_command_id = str(record.get("rendered_command_id") or "").strip()
    command = str(record.get("command") or "").strip()
    reason = str(record.get("reason") or "").strip()

    argv = record.get("argv")
    cwd = record.get("cwd")
    env_keys = record.get("env_keys")

    dry_run_only = bool(record.get("dry_run_only"))
    would_execute = bool(record.get("would_execute"))
    ready_for_real_execution = bool(record.get("ready_for_real_execution"))
    real_execution_enabled = bool(record.get("real_execution_enabled"))
    subprocess_enabled = bool(record.get("subprocess_enabled"))
    execution_performed = bool(record.get("execution_performed"))
    subprocess_invoked = bool(record.get("subprocess_invoked"))

    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    if not envelope_id:
        reasons.append("missing_real_execution_dry_run_envelope_id")
    if not final_gate_id:
        reasons.append("missing_real_execution_final_gate_id")
    if not transition_id:
        reasons.append("missing_real_execution_approval_transition_id")
    if not approval_id:
        reasons.append("missing_real_execution_approval_id")
    if not preflight_id:
        reasons.append("missing_real_execution_preflight_id")
    if not controlled_result_id:
        reasons.append("missing_controlled_execution_result_id")
    if not rendered_command_id:
        reasons.append("missing_rendered_command_id")
    if not command:
        reasons.append("missing_command")

    if not isinstance(argv, list) or not argv:
        reasons.append("dry_run_envelope_argv_must_be_non_empty_list")
    if not isinstance(cwd, str) or not cwd.strip():
        reasons.append("dry_run_envelope_cwd_must_be_non_empty_string")
    if not isinstance(env_keys, list):
        reasons.append("dry_run_envelope_env_keys_must_be_list")

    forbidden_env_fragments = (
        "TOKEN",
        "SECRET",
        "PASSWORD",
        "KEY",
        "CREDENTIAL",
    )
    if isinstance(env_keys, list):
        for key in env_keys:
            key_text = str(key or "").upper()
            if any(fragment in key_text for fragment in forbidden_env_fragments):
                reasons.append("dry_run_envelope_env_keys_must_not_include_secrets")
                break

    if reason != "real_execution_dry_run_envelope_recorded":
        reasons.append("invalid_dry_run_envelope_reason")

    if not dry_run_only or not bool(payload_mapping.get("dry_run_only", True)):
        reasons.append("dry_run_envelope_must_remain_dry_run_only")
    if would_execute or bool(payload_mapping.get("would_execute")):
        reasons.append("dry_run_envelope_would_execute_must_remain_false")
    if ready_for_real_execution or bool(
        payload_mapping.get("ready_for_real_execution")
    ):
        reasons.append("dry_run_envelope_must_not_be_ready")
    if real_execution_enabled or bool(payload_mapping.get("real_execution_enabled")):
        reasons.append("dry_run_envelope_must_not_enable_real_execution")
    if subprocess_enabled or bool(payload_mapping.get("subprocess_enabled")):
        reasons.append("dry_run_envelope_must_not_enable_subprocess")
    if execution_performed or bool(payload_mapping.get("execution_performed")):
        reasons.append("dry_run_envelope_must_not_execute")
    if subprocess_invoked or bool(payload_mapping.get("subprocess_invoked")):
        reasons.append("dry_run_envelope_must_not_invoke_subprocess")

    return {
        "type": "security_validation_result",
        "record_type": "replay_lifecycle_retry_real_execution_dry_run_envelope",
        "valid": not reasons,
        "severity": "critical" if reasons else "info",
        "reasons": reasons,
        "subject": envelope_id or final_gate_id,
        "dry_run_only": dry_run_only,
        "would_execute": would_execute,
        "ready_for_real_execution": ready_for_real_execution,
        "real_execution_enabled": real_execution_enabled,
        "subprocess_enabled": subprocess_enabled,
        "execution_performed": execution_performed,
        "subprocess_invoked": subprocess_invoked,
        "argv_len": len(argv) if isinstance(argv, list) else 0,
        "env_key_count": len(env_keys) if isinstance(env_keys, list) else 0,
        "reason": reason or "unknown",
    }


def validate_replay_lifecycle_retry_real_execution_noop_result(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate guarded noop subprocess harness result records."""
    reasons: list[str] = []

    result_id = str(record.get("real_execution_noop_result_id") or "").strip()
    envelope_id = str(
        record.get("real_execution_dry_run_envelope_id") or ""
    ).strip()
    final_gate_id = str(record.get("real_execution_final_gate_id") or "").strip()
    transition_id = str(
        record.get("real_execution_approval_transition_id") or ""
    ).strip()
    approval_id = str(record.get("real_execution_approval_id") or "").strip()
    preflight_id = str(record.get("real_execution_preflight_id") or "").strip()
    controlled_result_id = str(
        record.get("controlled_execution_result_id") or ""
    ).strip()
    rendered_command_id = str(record.get("rendered_command_id") or "").strip()
    reason = str(record.get("reason") or "").strip()

    noop_argv = record.get("noop_argv")
    noop_only = bool(record.get("noop_only"))
    rendered_command_executed = bool(record.get("rendered_command_executed"))
    dry_run_envelope_command_executed = bool(
        record.get("dry_run_envelope_command_executed")
    )
    real_execution_enabled = bool(record.get("real_execution_enabled"))
    subprocess_invoked = bool(record.get("subprocess_invoked"))
    execution_performed = bool(record.get("execution_performed"))
    exit_code = record.get("exit_code")
    stdout = str(record.get("stdout") or "")
    stderr = str(record.get("stderr") or "")

    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    if not result_id:
        reasons.append("missing_real_execution_noop_result_id")
    if not envelope_id:
        reasons.append("missing_real_execution_dry_run_envelope_id")
    if not final_gate_id:
        reasons.append("missing_real_execution_final_gate_id")
    if not transition_id:
        reasons.append("missing_real_execution_approval_transition_id")
    if not approval_id:
        reasons.append("missing_real_execution_approval_id")
    if not preflight_id:
        reasons.append("missing_real_execution_preflight_id")
    if not controlled_result_id:
        reasons.append("missing_controlled_execution_result_id")
    if not rendered_command_id:
        reasons.append("missing_rendered_command_id")

    if not isinstance(noop_argv, list) or not noop_argv:
        reasons.append("noop_result_argv_must_be_non_empty_list")
    if reason != "real_execution_noop_harness_completed":
        reasons.append("invalid_noop_result_reason")

    if not noop_only or not bool(payload_mapping.get("noop_only", True)):
        reasons.append("noop_result_must_remain_noop_only")
    if rendered_command_executed or bool(
        payload_mapping.get("rendered_command_executed")
    ):
        reasons.append("noop_result_must_not_execute_rendered_command")
    if dry_run_envelope_command_executed or bool(
        payload_mapping.get("dry_run_envelope_command_executed")
    ):
        reasons.append("noop_result_must_not_execute_dry_run_envelope_command")
    if real_execution_enabled or bool(payload_mapping.get("real_execution_enabled")):
        reasons.append("noop_result_must_not_enable_real_execution")
    if not subprocess_invoked or not bool(
        payload_mapping.get("subprocess_invoked", True)
    ):
        reasons.append("noop_result_must_invoke_subprocess")
    if not execution_performed or not bool(
        payload_mapping.get("execution_performed", True)
    ):
        reasons.append("noop_result_must_record_execution_performed")
    if exit_code != 0:
        reasons.append("noop_result_exit_code_must_be_zero")
    if "controlled-noop-ok" not in stdout:
        reasons.append("noop_result_stdout_must_contain_marker")
    if stderr:
        reasons.append("noop_result_stderr_must_be_empty")

    return {
        "type": "security_validation_result",
        "record_type": "replay_lifecycle_retry_real_execution_noop_result",
        "valid": not reasons,
        "severity": "critical" if reasons else "info",
        "reasons": reasons,
        "subject": result_id or envelope_id,
        "noop_only": noop_only,
        "rendered_command_executed": rendered_command_executed,
        "dry_run_envelope_command_executed": dry_run_envelope_command_executed,
        "real_execution_enabled": real_execution_enabled,
        "subprocess_invoked": subprocess_invoked,
        "execution_performed": execution_performed,
        "exit_code": exit_code,
        "stdout_marker_observed": "controlled-noop-ok" in stdout,
        "reason": reason or "unknown",
    }


def validate_replay_lifecycle_retry_real_execution_read_only_promotion(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate no-execution read-only evidence command promotion records."""
    reasons: list[str] = []

    promotion_id = str(
        record.get("real_execution_read_only_promotion_id") or ""
    ).strip()
    noop_result_id = str(record.get("real_execution_noop_result_id") or "").strip()
    envelope_id = str(
        record.get("real_execution_dry_run_envelope_id") or ""
    ).strip()
    final_gate_id = str(record.get("real_execution_final_gate_id") or "").strip()
    transition_id = str(
        record.get("real_execution_approval_transition_id") or ""
    ).strip()
    approval_id = str(record.get("real_execution_approval_id") or "").strip()
    preflight_id = str(record.get("real_execution_preflight_id") or "").strip()
    controlled_result_id = str(
        record.get("controlled_execution_result_id") or ""
    ).strip()
    rendered_command_id = str(record.get("rendered_command_id") or "").strip()

    promotion_status = str(record.get("promotion_status") or "").strip()
    read_only_module = str(record.get("read_only_module") or "").strip()
    reason = str(record.get("reason") or "").strip()

    read_only_argv = record.get("read_only_argv")
    read_only_candidate = bool(record.get("read_only_candidate"))
    command_parse_valid = bool(record.get("command_parse_valid"))
    stdout_marker_observed = bool(record.get("stdout_marker_observed"))
    noop_exit_code = record.get("noop_exit_code")
    noop_only = bool(record.get("noop_only"))
    rendered_command_executed = bool(record.get("rendered_command_executed"))
    dry_run_command_executed = bool(
        record.get("dry_run_envelope_command_executed")
    )
    real_execution_enabled = bool(record.get("real_execution_enabled"))
    subprocess_invoked = bool(record.get("subprocess_invoked"))
    execution_performed = bool(record.get("execution_performed"))

    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    if not promotion_id:
        reasons.append("missing_real_execution_read_only_promotion_id")
    if not noop_result_id:
        reasons.append("missing_real_execution_noop_result_id")
    if not envelope_id:
        reasons.append("missing_real_execution_dry_run_envelope_id")
    if not final_gate_id:
        reasons.append("missing_real_execution_final_gate_id")
    if not transition_id:
        reasons.append("missing_real_execution_approval_transition_id")
    if not approval_id:
        reasons.append("missing_real_execution_approval_id")
    if not preflight_id:
        reasons.append("missing_real_execution_preflight_id")
    if not controlled_result_id:
        reasons.append("missing_controlled_execution_result_id")
    if not rendered_command_id:
        reasons.append("missing_rendered_command_id")

    if promotion_status not in {"promoted", "blocked"}:
        reasons.append("invalid_read_only_promotion_status")
    if promotion_status != "promoted":
        reasons.append("read_only_promotion_must_be_promoted")
    if read_only_module != "src.testing.run_replay_evidence_check":
        reasons.append("read_only_promotion_module_must_be_allowlisted")
    if not isinstance(read_only_argv, list) or not read_only_argv:
        reasons.append("read_only_promotion_argv_must_be_non_empty_list")
    if reason != "real_execution_read_only_promotion_recorded":
        reasons.append("invalid_read_only_promotion_reason")

    if not read_only_candidate or not bool(
        payload_mapping.get("read_only_candidate", True)
    ):
        reasons.append("read_only_promotion_must_be_candidate")
    if not command_parse_valid or not bool(
        payload_mapping.get("command_parse_valid", True)
    ):
        reasons.append("read_only_promotion_command_parse_must_be_valid")
    if not stdout_marker_observed or not bool(
        payload_mapping.get("stdout_marker_observed", True)
    ):
        reasons.append("read_only_promotion_stdout_marker_must_be_observed")
    if noop_exit_code != 0 or payload_mapping.get("noop_exit_code", 0) != 0:
        reasons.append("read_only_promotion_noop_exit_code_must_be_zero")
    if not noop_only or not bool(payload_mapping.get("noop_only", True)):
        reasons.append("read_only_promotion_requires_noop_only_source")

    if rendered_command_executed or bool(
        payload_mapping.get("rendered_command_executed")
    ):
        reasons.append("read_only_promotion_must_not_execute_rendered_command")
    if dry_run_command_executed or bool(
        payload_mapping.get("dry_run_envelope_command_executed")
    ):
        reasons.append("read_only_promotion_must_not_execute_dry_run_command")
    if real_execution_enabled or bool(payload_mapping.get("real_execution_enabled")):
        reasons.append("read_only_promotion_must_not_enable_real_execution")
    if subprocess_invoked or bool(payload_mapping.get("subprocess_invoked")):
        reasons.append("read_only_promotion_must_not_invoke_subprocess")
    if execution_performed or bool(payload_mapping.get("execution_performed")):
        reasons.append("read_only_promotion_must_not_execute")

    return {
        "type": "security_validation_result",
        "record_type": "replay_lifecycle_retry_real_execution_read_only_promotion",
        "valid": not reasons,
        "severity": "critical" if reasons else "info",
        "reasons": reasons,
        "subject": promotion_id or noop_result_id,
        "promotion_status": promotion_status or "unknown",
        "read_only_candidate": read_only_candidate,
        "command_parse_valid": command_parse_valid,
        "stdout_marker_observed": stdout_marker_observed,
        "noop_exit_code": noop_exit_code,
        "noop_only": noop_only,
        "rendered_command_executed": rendered_command_executed,
        "dry_run_envelope_command_executed": dry_run_command_executed,
        "real_execution_enabled": real_execution_enabled,
        "subprocess_invoked": subprocess_invoked,
        "execution_performed": execution_performed,
        "read_only_module": read_only_module or "unknown",
        "reason": reason or "unknown",
    }


def validate_replay_lifecycle_retry_real_execution_read_only_final_gate(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate fail-closed read-only execution final gate records."""
    reasons: list[str] = []

    gate_id = str(
        record.get("real_execution_read_only_final_gate_id") or ""
    ).strip()
    promotion_id = str(
        record.get("real_execution_read_only_promotion_id") or ""
    ).strip()
    noop_result_id = str(record.get("real_execution_noop_result_id") or "").strip()
    envelope_id = str(
        record.get("real_execution_dry_run_envelope_id") or ""
    ).strip()
    final_gate_id = str(record.get("real_execution_final_gate_id") or "").strip()
    transition_id = str(
        record.get("real_execution_approval_transition_id") or ""
    ).strip()
    approval_id = str(record.get("real_execution_approval_id") or "").strip()
    preflight_id = str(record.get("real_execution_preflight_id") or "").strip()
    controlled_result_id = str(
        record.get("controlled_execution_result_id") or ""
    ).strip()
    rendered_command_id = str(record.get("rendered_command_id") or "").strip()

    gate_status = str(record.get("gate_status") or "").strip()
    promotion_status = str(record.get("promotion_status") or "").strip()
    read_only_module = str(record.get("read_only_module") or "").strip()
    reason = str(record.get("reason") or "").strip()

    read_only_argv = record.get("read_only_argv")
    blocking_reasons = record.get("blocking_reasons")
    precondition_failures = record.get("precondition_failures")

    promotion_preconditions_satisfied = bool(
        record.get("promotion_preconditions_satisfied")
    )
    ready_for_read_only_execution = bool(
        record.get("ready_for_read_only_execution")
    )
    would_execute = bool(record.get("would_execute"))
    read_only_execution_enabled = bool(record.get("read_only_execution_enabled"))
    real_execution_enabled = bool(record.get("real_execution_enabled"))
    subprocess_enabled = bool(record.get("subprocess_enabled"))
    subprocess_invoked = bool(record.get("subprocess_invoked"))
    execution_performed = bool(record.get("execution_performed"))
    rendered_command_executed = bool(record.get("rendered_command_executed"))
    dry_run_command_executed = bool(
        record.get("dry_run_envelope_command_executed")
    )

    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    if not gate_id:
        reasons.append("missing_real_execution_read_only_final_gate_id")
    if not promotion_id:
        reasons.append("missing_real_execution_read_only_promotion_id")
    if not noop_result_id:
        reasons.append("missing_real_execution_noop_result_id")
    if not envelope_id:
        reasons.append("missing_real_execution_dry_run_envelope_id")
    if not final_gate_id:
        reasons.append("missing_real_execution_final_gate_id")
    if not transition_id:
        reasons.append("missing_real_execution_approval_transition_id")
    if not approval_id:
        reasons.append("missing_real_execution_approval_id")
    if not preflight_id:
        reasons.append("missing_real_execution_preflight_id")
    if not controlled_result_id:
        reasons.append("missing_controlled_execution_result_id")
    if not rendered_command_id:
        reasons.append("missing_rendered_command_id")

    if gate_status != "blocked":
        reasons.append("read_only_final_gate_must_remain_blocked")
    if promotion_status != "promoted":
        reasons.append("read_only_final_gate_requires_promoted_source")
    if read_only_module != "src.testing.run_replay_evidence_check":
        reasons.append("read_only_final_gate_module_must_be_allowlisted")
    if not isinstance(read_only_argv, list) or not read_only_argv:
        reasons.append("read_only_final_gate_argv_must_be_non_empty_list")
    if reason != "read_only_execution_requires_separate_pr":
        reasons.append("invalid_read_only_final_gate_reason")

    if not isinstance(blocking_reasons, list):
        reasons.append("read_only_final_gate_blocking_reasons_must_be_list")
    elif "read_only_execution_requires_separate_pr" not in {
        str(item) for item in blocking_reasons
    }:
        reasons.append("read_only_final_gate_must_require_separate_pr")

    if not isinstance(precondition_failures, list):
        reasons.append("read_only_final_gate_precondition_failures_must_be_list")

    if not promotion_preconditions_satisfied or not bool(
        payload_mapping.get("promotion_preconditions_satisfied", True)
    ):
        reasons.append("read_only_final_gate_preconditions_must_be_satisfied")
    if ready_for_read_only_execution or bool(
        payload_mapping.get("ready_for_read_only_execution")
    ):
        reasons.append("read_only_final_gate_must_not_be_ready")
    if would_execute or bool(payload_mapping.get("would_execute")):
        reasons.append("read_only_final_gate_would_execute_must_remain_false")
    if read_only_execution_enabled or bool(
        payload_mapping.get("read_only_execution_enabled")
    ):
        reasons.append("read_only_final_gate_must_not_enable_read_only_execution")
    if real_execution_enabled or bool(payload_mapping.get("real_execution_enabled")):
        reasons.append("read_only_final_gate_must_not_enable_real_execution")
    if subprocess_enabled or bool(payload_mapping.get("subprocess_enabled")):
        reasons.append("read_only_final_gate_must_not_enable_subprocess")
    if subprocess_invoked or bool(payload_mapping.get("subprocess_invoked")):
        reasons.append("read_only_final_gate_must_not_invoke_subprocess")
    if execution_performed or bool(payload_mapping.get("execution_performed")):
        reasons.append("read_only_final_gate_must_not_execute")
    if rendered_command_executed or bool(
        payload_mapping.get("rendered_command_executed")
    ):
        reasons.append("read_only_final_gate_must_not_execute_rendered_command")
    if dry_run_command_executed or bool(
        payload_mapping.get("dry_run_envelope_command_executed")
    ):
        reasons.append("read_only_final_gate_must_not_execute_dry_run_command")

    return {
        "type": "security_validation_result",
        "record_type": "replay_lifecycle_retry_real_execution_read_only_final_gate",
        "valid": not reasons,
        "severity": "critical" if reasons else "info",
        "reasons": reasons,
        "subject": gate_id or promotion_id,
        "gate_status": gate_status or "unknown",
        "promotion_preconditions_satisfied": promotion_preconditions_satisfied,
        "ready_for_read_only_execution": ready_for_read_only_execution,
        "would_execute": would_execute,
        "read_only_execution_enabled": read_only_execution_enabled,
        "real_execution_enabled": real_execution_enabled,
        "subprocess_enabled": subprocess_enabled,
        "subprocess_invoked": subprocess_invoked,
        "execution_performed": execution_performed,
        "rendered_command_executed": rendered_command_executed,
        "dry_run_envelope_command_executed": dry_run_command_executed,
        "reason": reason or "unknown",
    }


def validate_replay_lifecycle_retry_real_execution_read_only_approval(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate explicit read-only execution approval records."""
    reasons: list[str] = []

    approval_record_id = str(
        record.get("real_execution_read_only_approval_id") or ""
    ).strip()
    final_gate_id = str(
        record.get("real_execution_read_only_final_gate_id") or ""
    ).strip()
    promotion_id = str(
        record.get("real_execution_read_only_promotion_id") or ""
    ).strip()
    noop_result_id = str(record.get("real_execution_noop_result_id") or "").strip()
    envelope_id = str(
        record.get("real_execution_dry_run_envelope_id") or ""
    ).strip()
    rendered_command_id = str(record.get("rendered_command_id") or "").strip()

    approval_status = str(record.get("approval_status") or "").strip()
    read_only_module = str(record.get("read_only_module") or "").strip()
    reason = str(record.get("reason") or "").strip()
    read_only_argv = record.get("read_only_argv")

    read_only_execution_enabled = bool(record.get("read_only_execution_enabled"))
    real_execution_enabled = bool(record.get("real_execution_enabled"))
    subprocess_enabled = bool(record.get("subprocess_enabled"))
    subprocess_invoked = bool(record.get("subprocess_invoked"))
    execution_performed = bool(record.get("execution_performed"))
    rendered_command_executed = bool(record.get("rendered_command_executed"))
    dry_run_command_executed = bool(
        record.get("dry_run_envelope_command_executed")
    )

    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    if not approval_record_id:
        reasons.append("missing_real_execution_read_only_approval_id")
    if not final_gate_id:
        reasons.append("missing_real_execution_read_only_final_gate_id")
    if not promotion_id:
        reasons.append("missing_real_execution_read_only_promotion_id")
    if not noop_result_id:
        reasons.append("missing_real_execution_noop_result_id")
    if not envelope_id:
        reasons.append("missing_real_execution_dry_run_envelope_id")
    if not rendered_command_id:
        reasons.append("missing_rendered_command_id")

    if approval_status not in {"pending", "approved", "rejected"}:
        reasons.append("invalid_read_only_approval_status")
    if reason != "read_only_execution_explicit_approval_required":
        reasons.append("invalid_read_only_approval_reason")
    if read_only_module != "src.testing.run_replay_evidence_check":
        reasons.append("read_only_approval_module_must_be_allowlisted")
    if not isinstance(read_only_argv, list) or not read_only_argv:
        reasons.append("read_only_approval_argv_must_be_non_empty_list")

    if read_only_execution_enabled or bool(
        payload_mapping.get("read_only_execution_enabled")
    ):
        reasons.append("read_only_approval_must_not_enable_read_only_execution")
    if real_execution_enabled or bool(payload_mapping.get("real_execution_enabled")):
        reasons.append("read_only_approval_must_not_enable_real_execution")
    if subprocess_enabled or bool(payload_mapping.get("subprocess_enabled")):
        reasons.append("read_only_approval_must_not_enable_subprocess")
    if subprocess_invoked or bool(payload_mapping.get("subprocess_invoked")):
        reasons.append("read_only_approval_must_not_invoke_subprocess")
    if execution_performed or bool(payload_mapping.get("execution_performed")):
        reasons.append("read_only_approval_must_not_execute")
    if rendered_command_executed or bool(
        payload_mapping.get("rendered_command_executed")
    ):
        reasons.append("read_only_approval_must_not_execute_rendered_command")
    if dry_run_command_executed or bool(
        payload_mapping.get("dry_run_envelope_command_executed")
    ):
        reasons.append("read_only_approval_must_not_execute_dry_run_command")

    return {
        "type": "security_validation_result",
        "record_type": "replay_lifecycle_retry_real_execution_read_only_approval",
        "valid": not reasons,
        "severity": "critical" if reasons else "info",
        "reasons": reasons,
        "subject": approval_record_id or final_gate_id,
        "approval_status": approval_status or "unknown",
        "read_only_execution_enabled": read_only_execution_enabled,
        "real_execution_enabled": real_execution_enabled,
        "subprocess_enabled": subprocess_enabled,
        "subprocess_invoked": subprocess_invoked,
        "execution_performed": execution_performed,
        "rendered_command_executed": rendered_command_executed,
        "dry_run_envelope_command_executed": dry_run_command_executed,
        "reason": reason or "unknown",
    }


def validate_replay_lifecycle_retry_real_execution_read_only_approval_transition(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable read-only execution approval transition records."""
    reasons: list[str] = []

    transition_id = str(
        record.get("real_execution_read_only_approval_transition_id") or ""
    ).strip()
    approval_id = str(
        record.get("real_execution_read_only_approval_id") or ""
    ).strip()
    final_gate_id = str(
        record.get("real_execution_read_only_final_gate_id") or ""
    ).strip()
    promotion_id = str(
        record.get("real_execution_read_only_promotion_id") or ""
    ).strip()
    noop_result_id = str(record.get("real_execution_noop_result_id") or "").strip()
    envelope_id = str(
        record.get("real_execution_dry_run_envelope_id") or ""
    ).strip()
    rendered_command_id = str(record.get("rendered_command_id") or "").strip()

    from_status = str(record.get("from_status") or "").strip()
    to_status = str(record.get("to_status") or "").strip()
    read_only_module = str(record.get("read_only_module") or "").strip()
    reason = str(record.get("reason") or "").strip()
    read_only_argv = record.get("read_only_argv")

    read_only_execution_enabled = bool(record.get("read_only_execution_enabled"))
    real_execution_enabled = bool(record.get("real_execution_enabled"))
    subprocess_enabled = bool(record.get("subprocess_enabled"))
    subprocess_invoked = bool(record.get("subprocess_invoked"))
    execution_performed = bool(record.get("execution_performed"))
    rendered_command_executed = bool(record.get("rendered_command_executed"))
    dry_run_command_executed = bool(
        record.get("dry_run_envelope_command_executed")
    )

    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    if not transition_id:
        reasons.append("missing_real_execution_read_only_approval_transition_id")
    if not approval_id:
        reasons.append("missing_real_execution_read_only_approval_id")
    if not final_gate_id:
        reasons.append("missing_real_execution_read_only_final_gate_id")
    if not promotion_id:
        reasons.append("missing_real_execution_read_only_promotion_id")
    if not noop_result_id:
        reasons.append("missing_real_execution_noop_result_id")
    if not envelope_id:
        reasons.append("missing_real_execution_dry_run_envelope_id")
    if not rendered_command_id:
        reasons.append("missing_rendered_command_id")

    if from_status != "pending":
        reasons.append("read_only_approval_transition_from_status_must_be_pending")
    if to_status not in {"approved", "rejected"}:
        reasons.append("invalid_read_only_approval_transition_to_status")
    if reason != "read_only_execution_approval_transition_recorded":
        reasons.append("invalid_read_only_approval_transition_reason")
    if read_only_module != "src.testing.run_replay_evidence_check":
        reasons.append("read_only_approval_transition_module_must_be_allowlisted")
    if not isinstance(read_only_argv, list) or not read_only_argv:
        reasons.append("read_only_approval_transition_argv_must_be_non_empty_list")

    if read_only_execution_enabled or bool(
        payload_mapping.get("read_only_execution_enabled")
    ):
        reasons.append(
            "read_only_approval_transition_must_not_enable_read_only_execution"
        )
    if real_execution_enabled or bool(payload_mapping.get("real_execution_enabled")):
        reasons.append("read_only_approval_transition_must_not_enable_real_execution")
    if subprocess_enabled or bool(payload_mapping.get("subprocess_enabled")):
        reasons.append("read_only_approval_transition_must_not_enable_subprocess")
    if subprocess_invoked or bool(payload_mapping.get("subprocess_invoked")):
        reasons.append("read_only_approval_transition_must_not_invoke_subprocess")
    if execution_performed or bool(payload_mapping.get("execution_performed")):
        reasons.append("read_only_approval_transition_must_not_execute")
    if rendered_command_executed or bool(
        payload_mapping.get("rendered_command_executed")
    ):
        reasons.append(
            "read_only_approval_transition_must_not_execute_rendered_command"
        )
    if dry_run_command_executed or bool(
        payload_mapping.get("dry_run_envelope_command_executed")
    ):
        reasons.append(
            "read_only_approval_transition_must_not_execute_dry_run_command"
        )

    return {
        "type": "security_validation_result",
        "record_type": (
            "replay_lifecycle_retry_real_execution_read_only_approval_transition"
        ),
        "valid": not reasons,
        "severity": "critical" if reasons else "info",
        "reasons": reasons,
        "subject": transition_id or approval_id,
        "from_status": from_status or "unknown",
        "to_status": to_status or "unknown",
        "read_only_execution_enabled": read_only_execution_enabled,
        "real_execution_enabled": real_execution_enabled,
        "subprocess_enabled": subprocess_enabled,
        "subprocess_invoked": subprocess_invoked,
        "execution_performed": execution_performed,
        "rendered_command_executed": rendered_command_executed,
        "dry_run_envelope_command_executed": dry_run_command_executed,
        "reason": reason or "unknown",
    }


def validate_replay_lifecycle_retry_real_execution_read_only_readiness_gate(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate read-only execution readiness gate records."""
    reasons: list[str] = []

    gate_id = str(
        record.get("real_execution_read_only_readiness_gate_id") or ""
    ).strip()
    transition_id = str(
        record.get("real_execution_read_only_approval_transition_id") or ""
    ).strip()
    approval_id = str(
        record.get("real_execution_read_only_approval_id") or ""
    ).strip()
    final_gate_id = str(
        record.get("real_execution_read_only_final_gate_id") or ""
    ).strip()
    promotion_id = str(
        record.get("real_execution_read_only_promotion_id") or ""
    ).strip()
    noop_result_id = str(record.get("real_execution_noop_result_id") or "").strip()
    envelope_id = str(
        record.get("real_execution_dry_run_envelope_id") or ""
    ).strip()
    rendered_command_id = str(record.get("rendered_command_id") or "").strip()

    gate_status = str(record.get("gate_status") or "").strip()
    from_status = str(record.get("read_only_approval_from_status") or "").strip()
    latest_status = str(record.get("read_only_approval_latest_status") or "").strip()
    read_only_module = str(record.get("read_only_module") or "").strip()
    reason = str(record.get("reason") or "").strip()

    read_only_argv = record.get("read_only_argv")
    blocking_reasons = record.get("blocking_reasons")
    precondition_failures = record.get("precondition_failures")

    read_only_readiness_satisfied = bool(
        record.get("read_only_readiness_satisfied")
    )
    ready_for_guarded_read_only_execution = bool(
        record.get("ready_for_guarded_read_only_execution")
    )
    read_only_execution_enabled = bool(record.get("read_only_execution_enabled"))
    real_execution_enabled = bool(record.get("real_execution_enabled"))
    subprocess_enabled = bool(record.get("subprocess_enabled"))
    subprocess_invoked = bool(record.get("subprocess_invoked"))
    execution_performed = bool(record.get("execution_performed"))
    rendered_command_executed = bool(record.get("rendered_command_executed"))
    dry_run_command_executed = bool(
        record.get("dry_run_envelope_command_executed")
    )

    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    if not gate_id:
        reasons.append("missing_real_execution_read_only_readiness_gate_id")
    if not transition_id:
        reasons.append("missing_real_execution_read_only_approval_transition_id")
    if not approval_id:
        reasons.append("missing_real_execution_read_only_approval_id")
    if not final_gate_id:
        reasons.append("missing_real_execution_read_only_final_gate_id")
    if not promotion_id:
        reasons.append("missing_real_execution_read_only_promotion_id")
    if not noop_result_id:
        reasons.append("missing_real_execution_noop_result_id")
    if not envelope_id:
        reasons.append("missing_real_execution_dry_run_envelope_id")
    if not rendered_command_id:
        reasons.append("missing_rendered_command_id")

    if gate_status != "ready_blocked":
        reasons.append("read_only_readiness_gate_must_be_ready_blocked")
    if from_status != "pending":
        reasons.append("read_only_readiness_gate_from_status_must_be_pending")
    if latest_status != "approved":
        reasons.append("read_only_readiness_gate_latest_status_must_be_approved")
    if reason != "guarded_read_only_execution_requires_separate_pr":
        reasons.append("invalid_read_only_readiness_gate_reason")
    if read_only_module != "src.testing.run_replay_evidence_check":
        reasons.append("read_only_readiness_gate_module_must_be_allowlisted")
    if not isinstance(read_only_argv, list) or not read_only_argv:
        reasons.append("read_only_readiness_gate_argv_must_be_non_empty_list")

    if not isinstance(blocking_reasons, list):
        reasons.append("read_only_readiness_gate_blocking_reasons_must_be_list")
    elif "guarded_read_only_execution_requires_separate_pr" not in {
        str(item) for item in blocking_reasons
    }:
        reasons.append("read_only_readiness_gate_must_require_separate_pr")

    if not isinstance(precondition_failures, list):
        reasons.append("read_only_readiness_gate_precondition_failures_must_be_list")
    elif precondition_failures:
        reasons.append("read_only_readiness_gate_precondition_failures_must_be_empty")

    if not read_only_readiness_satisfied or not bool(
        payload_mapping.get("read_only_readiness_satisfied", True)
    ):
        reasons.append("read_only_readiness_gate_must_be_satisfied")
    if not ready_for_guarded_read_only_execution or not bool(
        payload_mapping.get("ready_for_guarded_read_only_execution", True)
    ):
        reasons.append("read_only_readiness_gate_must_be_ready_for_guarded_execution")

    if read_only_execution_enabled or bool(
        payload_mapping.get("read_only_execution_enabled")
    ):
        reasons.append("read_only_readiness_gate_must_not_enable_read_only_execution")
    if real_execution_enabled or bool(payload_mapping.get("real_execution_enabled")):
        reasons.append("read_only_readiness_gate_must_not_enable_real_execution")
    if subprocess_enabled or bool(payload_mapping.get("subprocess_enabled")):
        reasons.append("read_only_readiness_gate_must_not_enable_subprocess")
    if subprocess_invoked or bool(payload_mapping.get("subprocess_invoked")):
        reasons.append("read_only_readiness_gate_must_not_invoke_subprocess")
    if execution_performed or bool(payload_mapping.get("execution_performed")):
        reasons.append("read_only_readiness_gate_must_not_execute")
    if rendered_command_executed or bool(
        payload_mapping.get("rendered_command_executed")
    ):
        reasons.append("read_only_readiness_gate_must_not_execute_rendered_command")
    if dry_run_command_executed or bool(
        payload_mapping.get("dry_run_envelope_command_executed")
    ):
        reasons.append("read_only_readiness_gate_must_not_execute_dry_run_command")

    return {
        "type": "security_validation_result",
        "record_type": (
            "replay_lifecycle_retry_real_execution_read_only_readiness_gate"
        ),
        "valid": not reasons,
        "severity": "critical" if reasons else "info",
        "reasons": reasons,
        "subject": gate_id or transition_id,
        "gate_status": gate_status or "unknown",
        "read_only_approval_from_status": from_status or "unknown",
        "read_only_approval_latest_status": latest_status or "unknown",
        "read_only_readiness_satisfied": read_only_readiness_satisfied,
        "ready_for_guarded_read_only_execution": (
            ready_for_guarded_read_only_execution
        ),
        "read_only_execution_enabled": read_only_execution_enabled,
        "real_execution_enabled": real_execution_enabled,
        "subprocess_enabled": subprocess_enabled,
        "subprocess_invoked": subprocess_invoked,
        "execution_performed": execution_performed,
        "rendered_command_executed": rendered_command_executed,
        "dry_run_envelope_command_executed": dry_run_command_executed,
        "reason": reason or "unknown",
    }


def validate_replay_lifecycle_retry_real_execution_read_only_execution_result(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate guarded read-only execution result records."""
    reasons: list[str] = []

    result_id = str(
        record.get("real_execution_read_only_execution_result_id") or ""
    ).strip()
    readiness_gate_id = str(
        record.get("real_execution_read_only_readiness_gate_id") or ""
    ).strip()
    transition_id = str(
        record.get("real_execution_read_only_approval_transition_id") or ""
    ).strip()
    approval_id = str(
        record.get("real_execution_read_only_approval_id") or ""
    ).strip()
    rendered_command_id = str(record.get("rendered_command_id") or "").strip()

    status = str(record.get("status") or "").strip()
    reason = str(record.get("reason") or "").strip()
    read_only_module = str(record.get("read_only_module") or "").strip()
    read_only_argv = record.get("read_only_argv")
    validation_reasons = record.get("validation_reasons")

    operator_authorized = bool(record.get("operator_authorized"))
    allow_guarded = bool(record.get("allow_guarded_read_only_execution"))
    read_only_execution_enabled = bool(record.get("read_only_execution_enabled"))
    real_execution_enabled = bool(record.get("real_execution_enabled"))
    subprocess_enabled = bool(record.get("subprocess_enabled"))
    subprocess_invoked = bool(record.get("subprocess_invoked"))
    execution_performed = bool(record.get("execution_performed"))
    read_only_command_executed = bool(record.get("read_only_command_executed"))
    rendered_command_executed = bool(record.get("rendered_command_executed"))
    dry_run_command_executed = bool(
        record.get("dry_run_envelope_command_executed")
    )

    exit_code = record.get("exit_code")
    stdout = record.get("stdout")
    stderr = record.get("stderr")

    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    if not result_id:
        reasons.append("missing_real_execution_read_only_execution_result_id")
    if not readiness_gate_id:
        reasons.append("missing_real_execution_read_only_readiness_gate_id")
    if not transition_id:
        reasons.append("missing_real_execution_read_only_approval_transition_id")
    if not approval_id:
        reasons.append("missing_real_execution_read_only_approval_id")
    if not rendered_command_id:
        reasons.append("missing_rendered_command_id")

    if status not in {"executed", "failed", "rejected"}:
        reasons.append("invalid_read_only_execution_result_status")
    if read_only_module != "src.testing.run_replay_evidence_check":
        reasons.append("read_only_execution_result_module_must_be_allowlisted")
    if not isinstance(read_only_argv, list) or not read_only_argv:
        reasons.append("read_only_execution_result_argv_must_be_non_empty_list")
    if not isinstance(validation_reasons, list):
        reasons.append("read_only_execution_result_validation_reasons_must_be_list")
    if not isinstance(stdout, str):
        reasons.append("read_only_execution_result_stdout_must_be_str")
    if not isinstance(stderr, str):
        reasons.append("read_only_execution_result_stderr_must_be_str")

    if real_execution_enabled or bool(payload_mapping.get("real_execution_enabled")):
        reasons.append("read_only_execution_result_must_not_enable_real_execution")

    if status in {"executed", "failed"}:
        if not operator_authorized:
            reasons.append("read_only_execution_result_requires_operator_authorized")
        if not allow_guarded:
            reasons.append("read_only_execution_result_requires_guarded_flag")
        if not read_only_execution_enabled:
            reasons.append("read_only_execution_result_must_enable_read_only_execution")
        if not subprocess_enabled:
            reasons.append("read_only_execution_result_must_enable_subprocess")
        if not subprocess_invoked:
            reasons.append("read_only_execution_result_must_invoke_subprocess")
        if not execution_performed:
            reasons.append("read_only_execution_result_must_perform_execution")
        if not read_only_command_executed:
            reasons.append("read_only_execution_result_must_execute_read_only_command")
        if not rendered_command_executed:
            reasons.append("read_only_execution_result_must_execute_rendered_command")
        if not dry_run_command_executed:
            reasons.append("read_only_execution_result_must_execute_dry_run_command")
        if not isinstance(exit_code, int):
            reasons.append("read_only_execution_result_exit_code_must_be_int")
        if validation_reasons:
            reasons.append("read_only_execution_result_validation_reasons_must_be_empty")
        if reason not in {
            "guarded_read_only_execution_completed",
            "guarded_read_only_execution_failed",
        }:
            reasons.append("invalid_read_only_execution_result_reason")

    if status == "rejected":
        if read_only_execution_enabled:
            reasons.append("rejected_read_only_execution_must_not_enable_execution")
        if subprocess_enabled:
            reasons.append("rejected_read_only_execution_must_not_enable_subprocess")
        if subprocess_invoked:
            reasons.append("rejected_read_only_execution_must_not_invoke_subprocess")
        if execution_performed:
            reasons.append("rejected_read_only_execution_must_not_execute")
        if read_only_command_executed:
            reasons.append("rejected_read_only_execution_must_not_execute_command")
        if exit_code is not None:
            reasons.append("rejected_read_only_execution_exit_code_must_be_none")
        if reason != "guarded_read_only_execution_rejected":
            reasons.append("invalid_rejected_read_only_execution_reason")

    return {
        "type": "security_validation_result",
        "record_type": (
            "replay_lifecycle_retry_real_execution_read_only_execution_result"
        ),
        "valid": not reasons,
        "severity": "critical" if reasons else "info",
        "reasons": reasons,
        "subject": result_id or readiness_gate_id,
        "status": status or "unknown",
        "reason": reason or "unknown",
        "operator_authorized": operator_authorized,
        "allow_guarded_read_only_execution": allow_guarded,
        "read_only_execution_enabled": read_only_execution_enabled,
        "real_execution_enabled": real_execution_enabled,
        "subprocess_enabled": subprocess_enabled,
        "subprocess_invoked": subprocess_invoked,
        "execution_performed": execution_performed,
        "read_only_command_executed": read_only_command_executed,
        "rendered_command_executed": rendered_command_executed,
        "dry_run_envelope_command_executed": dry_run_command_executed,
        "exit_code": exit_code,
        "validation_reasons": validation_reasons if isinstance(validation_reasons, list) else [],
    }


def validate_replay_lifecycle_retry_real_execution_read_only_feedback(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate post-read-only execution feedback records."""
    reasons: list[str] = []

    feedback_id = str(
        record.get("real_execution_read_only_feedback_id") or ""
    ).strip()
    execution_result_id = str(
        record.get("real_execution_read_only_execution_result_id") or ""
    ).strip()
    readiness_gate_id = str(
        record.get("real_execution_read_only_readiness_gate_id") or ""
    ).strip()
    rendered_command_id = str(record.get("rendered_command_id") or "").strip()

    source_status = str(record.get("source_status") or "").strip()
    source_reason = str(record.get("source_reason") or "").strip()
    feedback_status = str(record.get("feedback_status") or "").strip()
    recommended_next_action = str(
        record.get("recommended_next_action") or ""
    ).strip()
    reason = str(record.get("reason") or "").strip()

    source_exit_code = record.get("source_exit_code")
    failure_hints = record.get("failure_hints")

    read_only_execution_was_observed = bool(
        record.get("read_only_execution_was_observed")
    )
    read_only_execution_failed = bool(record.get("read_only_execution_failed"))
    read_only_execution_succeeded = bool(record.get("read_only_execution_succeeded"))
    read_only_execution_rejected = bool(record.get("read_only_execution_rejected"))

    operator_authorized = bool(record.get("operator_authorized"))
    allow_guarded = bool(record.get("allow_guarded_read_only_execution"))
    read_only_execution_enabled = bool(record.get("read_only_execution_enabled"))
    real_execution_enabled = bool(record.get("real_execution_enabled"))

    source_subprocess_invoked = bool(record.get("source_subprocess_invoked"))
    source_execution_performed = bool(record.get("source_execution_performed"))
    source_read_only_command_executed = bool(
        record.get("source_read_only_command_executed")
    )
    source_rendered_command_executed = bool(
        record.get("source_rendered_command_executed")
    )
    source_dry_run_command_executed = bool(
        record.get("source_dry_run_command_executed")
    )

    feedback_execution_performed = bool(record.get("feedback_execution_performed"))
    feedback_subprocess_invoked = bool(record.get("feedback_subprocess_invoked"))
    execution_performed = bool(record.get("execution_performed"))
    subprocess_invoked = bool(record.get("subprocess_invoked"))

    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    if not feedback_id:
        reasons.append("missing_real_execution_read_only_feedback_id")
    if not execution_result_id:
        reasons.append("missing_real_execution_read_only_execution_result_id")
    if not readiness_gate_id:
        reasons.append("missing_real_execution_read_only_readiness_gate_id")
    if not rendered_command_id:
        reasons.append("missing_rendered_command_id")

    if source_status not in {"executed", "failed", "rejected", "unknown"}:
        reasons.append("invalid_read_only_feedback_source_status")
    if feedback_status not in {"successful", "actionable", "blocked", "unknown"}:
        reasons.append("invalid_read_only_feedback_status")
    if reason != "read_only_execution_feedback_recorded":
        reasons.append("invalid_read_only_feedback_reason")
    if not recommended_next_action:
        reasons.append("missing_read_only_feedback_recommended_next_action")
    if not isinstance(failure_hints, list):
        reasons.append("read_only_feedback_failure_hints_must_be_list")

    if real_execution_enabled or bool(payload_mapping.get("real_execution_enabled")):
        reasons.append("read_only_feedback_must_not_enable_real_execution")

    if feedback_execution_performed or bool(
        payload_mapping.get("feedback_execution_performed")
    ):
        reasons.append("read_only_feedback_must_not_perform_feedback_execution")
    if feedback_subprocess_invoked or bool(
        payload_mapping.get("feedback_subprocess_invoked")
    ):
        reasons.append("read_only_feedback_must_not_invoke_feedback_subprocess")
    if execution_performed or bool(payload_mapping.get("execution_performed")):
        reasons.append("read_only_feedback_must_not_execute")
    if subprocess_invoked or bool(payload_mapping.get("subprocess_invoked")):
        reasons.append("read_only_feedback_must_not_invoke_subprocess")

    if source_status == "failed":
        if feedback_status != "actionable":
            reasons.append("failed_read_only_feedback_must_be_actionable")
        if recommended_next_action != "investigate_failed_read_only_evidence_check":
            reasons.append("failed_read_only_feedback_next_action_mismatch")
        if source_exit_code is None:
            reasons.append("failed_read_only_feedback_requires_source_exit_code")
        if not read_only_execution_was_observed:
            reasons.append("failed_read_only_feedback_must_observe_execution")
        if not read_only_execution_failed:
            reasons.append("failed_read_only_feedback_must_mark_failed")
        if not operator_authorized:
            reasons.append("failed_read_only_feedback_requires_operator_authorized")
        if not allow_guarded:
            reasons.append("failed_read_only_feedback_requires_guarded_flag")
        if not read_only_execution_enabled:
            reasons.append("failed_read_only_feedback_requires_read_only_enabled")
        if not source_subprocess_invoked:
            reasons.append("failed_read_only_feedback_requires_source_subprocess")
        if not source_execution_performed:
            reasons.append("failed_read_only_feedback_requires_source_execution")
        if not source_read_only_command_executed:
            reasons.append("failed_read_only_feedback_requires_source_read_only_command")
        if not source_rendered_command_executed:
            reasons.append("failed_read_only_feedback_requires_source_rendered_command")
        if not source_dry_run_command_executed:
            reasons.append("failed_read_only_feedback_requires_source_dry_run_command")

    if source_status == "executed":
        if feedback_status != "successful":
            reasons.append("successful_read_only_feedback_status_mismatch")
        if recommended_next_action != "promote_successful_read_only_execution_evidence":
            reasons.append("successful_read_only_feedback_next_action_mismatch")
        if source_exit_code != 0:
            reasons.append("successful_read_only_feedback_exit_code_must_be_zero")
        if not read_only_execution_succeeded:
            reasons.append("successful_read_only_feedback_must_mark_succeeded")

    if source_status == "rejected":
        if feedback_status != "blocked":
            reasons.append("rejected_read_only_feedback_status_mismatch")
        if recommended_next_action != "resolve_guarded_read_only_execution_rejection":
            reasons.append("rejected_read_only_feedback_next_action_mismatch")
        if not read_only_execution_rejected:
            reasons.append("rejected_read_only_feedback_must_mark_rejected")

    return {
        "type": "security_validation_result",
        "record_type": "replay_lifecycle_retry_real_execution_read_only_feedback",
        "valid": not reasons,
        "severity": "critical" if reasons else "info",
        "reasons": reasons,
        "subject": feedback_id or execution_result_id,
        "source_status": source_status or "unknown",
        "source_reason": source_reason or "unknown",
        "source_exit_code": source_exit_code,
        "feedback_status": feedback_status or "unknown",
        "recommended_next_action": recommended_next_action or "unknown",
        "read_only_execution_was_observed": read_only_execution_was_observed,
        "read_only_execution_failed": read_only_execution_failed,
        "read_only_execution_succeeded": read_only_execution_succeeded,
        "read_only_execution_rejected": read_only_execution_rejected,
        "operator_authorized": operator_authorized,
        "allow_guarded_read_only_execution": allow_guarded,
        "read_only_execution_enabled": read_only_execution_enabled,
        "real_execution_enabled": real_execution_enabled,
        "source_subprocess_invoked": source_subprocess_invoked,
        "source_execution_performed": source_execution_performed,
        "source_read_only_command_executed": source_read_only_command_executed,
        "source_rendered_command_executed": source_rendered_command_executed,
        "source_dry_run_command_executed": source_dry_run_command_executed,
        "feedback_execution_performed": feedback_execution_performed,
        "feedback_subprocess_invoked": feedback_subprocess_invoked,
        "execution_performed": execution_performed,
        "subprocess_invoked": subprocess_invoked,
        "reason": reason or "unknown",
    }


def validate_replay_lifecycle_retry_real_execution_read_only_repair_plan(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate read-only execution repair plan records."""
    reasons: list[str] = []

    repair_plan_id = str(
        record.get("real_execution_read_only_repair_plan_id") or ""
    ).strip()
    feedback_id = str(
        record.get("real_execution_read_only_feedback_id") or ""
    ).strip()
    execution_result_id = str(
        record.get("real_execution_read_only_execution_result_id") or ""
    ).strip()
    rendered_command_id = str(record.get("rendered_command_id") or "").strip()

    repair_plan_status = str(record.get("repair_plan_status") or "").strip()
    source_feedback_status = str(record.get("source_feedback_status") or "").strip()
    source_status = str(record.get("source_status") or "").strip()
    source_exit_code = record.get("source_exit_code")
    recommended_next_action = str(
        record.get("recommended_next_action") or ""
    ).strip()
    reason = str(record.get("reason") or "").strip()

    repair_items = record.get("repair_items")
    repair_targets = record.get("repair_targets")
    repair_item_count = record.get("repair_item_count")

    requires_operator_review = bool(record.get("requires_operator_review"))
    repair_execution_enabled = bool(record.get("repair_execution_enabled"))
    real_execution_enabled = bool(record.get("real_execution_enabled"))
    subprocess_enabled = bool(record.get("subprocess_enabled"))
    repair_execution_performed = bool(record.get("repair_execution_performed"))
    repair_subprocess_invoked = bool(record.get("repair_subprocess_invoked"))
    execution_performed = bool(record.get("execution_performed"))
    subprocess_invoked = bool(record.get("subprocess_invoked"))

    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    if not repair_plan_id:
        reasons.append("missing_real_execution_read_only_repair_plan_id")
    if not feedback_id:
        reasons.append("missing_real_execution_read_only_feedback_id")
    if not execution_result_id:
        reasons.append("missing_real_execution_read_only_execution_result_id")
    if not rendered_command_id:
        reasons.append("missing_rendered_command_id")

    if repair_plan_status not in {"planned", "blocked", "no_repair_needed", "unknown"}:
        reasons.append("invalid_read_only_repair_plan_status")
    if source_feedback_status not in {"actionable", "blocked", "successful", "unknown"}:
        reasons.append("invalid_read_only_repair_plan_source_feedback_status")
    if source_status not in {"failed", "executed", "rejected", "unknown"}:
        reasons.append("invalid_read_only_repair_plan_source_status")
    if recommended_next_action != "review_replay_evidence_repair_plan":
        reasons.append("invalid_read_only_repair_plan_next_action")
    if reason != "read_only_execution_repair_plan_recorded":
        reasons.append("invalid_read_only_repair_plan_reason")

    if not isinstance(repair_items, list):
        reasons.append("read_only_repair_plan_items_must_be_list")
    if not isinstance(repair_targets, list):
        reasons.append("read_only_repair_plan_targets_must_be_list")
    if not isinstance(repair_item_count, int):
        reasons.append("read_only_repair_plan_item_count_must_be_int")
    elif isinstance(repair_items, list) and repair_item_count != len(repair_items):
        reasons.append("read_only_repair_plan_item_count_mismatch")

    if source_feedback_status == "actionable":
        if repair_plan_status != "planned":
            reasons.append("actionable_read_only_repair_plan_must_be_planned")
        if source_status != "failed":
            reasons.append("actionable_read_only_repair_plan_source_must_be_failed")
        if source_exit_code is None:
            reasons.append("actionable_read_only_repair_plan_requires_source_exit_code")
        if isinstance(repair_item_count, int) and repair_item_count <= 0:
            reasons.append("actionable_read_only_repair_plan_requires_items")
        if not requires_operator_review:
            reasons.append("actionable_read_only_repair_plan_requires_operator_review")

    if source_feedback_status == "successful":
        if repair_plan_status != "no_repair_needed":
            reasons.append("successful_read_only_repair_plan_status_mismatch")

    if source_feedback_status == "blocked":
        if repair_plan_status != "blocked":
            reasons.append("blocked_read_only_repair_plan_status_mismatch")

    if repair_execution_enabled or bool(payload_mapping.get("repair_execution_enabled")):
        reasons.append("read_only_repair_plan_must_not_enable_repair_execution")
    if real_execution_enabled or bool(payload_mapping.get("real_execution_enabled")):
        reasons.append("read_only_repair_plan_must_not_enable_real_execution")
    if subprocess_enabled or bool(payload_mapping.get("subprocess_enabled")):
        reasons.append("read_only_repair_plan_must_not_enable_subprocess")
    if repair_execution_performed or bool(
        payload_mapping.get("repair_execution_performed")
    ):
        reasons.append("read_only_repair_plan_must_not_perform_repair_execution")
    if repair_subprocess_invoked or bool(payload_mapping.get("repair_subprocess_invoked")):
        reasons.append("read_only_repair_plan_must_not_invoke_repair_subprocess")
    if execution_performed or bool(payload_mapping.get("execution_performed")):
        reasons.append("read_only_repair_plan_must_not_execute")
    if subprocess_invoked or bool(payload_mapping.get("subprocess_invoked")):
        reasons.append("read_only_repair_plan_must_not_invoke_subprocess")

    return {
        "type": "security_validation_result",
        "record_type": "replay_lifecycle_retry_real_execution_read_only_repair_plan",
        "valid": not reasons,
        "severity": "critical" if reasons else "info",
        "reasons": reasons,
        "subject": repair_plan_id or feedback_id,
        "repair_plan_status": repair_plan_status or "unknown",
        "source_feedback_status": source_feedback_status or "unknown",
        "source_status": source_status or "unknown",
        "source_exit_code": source_exit_code,
        "recommended_next_action": recommended_next_action or "unknown",
        "repair_item_count": repair_item_count if isinstance(repair_item_count, int) else 0,
        "requires_operator_review": requires_operator_review,
        "repair_execution_enabled": repair_execution_enabled,
        "real_execution_enabled": real_execution_enabled,
        "subprocess_enabled": subprocess_enabled,
        "repair_execution_performed": repair_execution_performed,
        "repair_subprocess_invoked": repair_subprocess_invoked,
        "execution_performed": execution_performed,
        "subprocess_invoked": subprocess_invoked,
        "reason": reason or "unknown",
    }


def validate_replay_lifecycle_retry_real_execution_read_only_repair_action_bundle(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate read-only repair action bundle records."""
    reasons: list[str] = []

    bundle_id = str(
        record.get("real_execution_read_only_repair_action_bundle_id") or ""
    ).strip()
    repair_plan_id = str(
        record.get("real_execution_read_only_repair_plan_id") or ""
    ).strip()
    feedback_id = str(record.get("real_execution_read_only_feedback_id") or "").strip()
    execution_result_id = str(
        record.get("real_execution_read_only_execution_result_id") or ""
    ).strip()
    rendered_command_id = str(record.get("rendered_command_id") or "").strip()

    bundle_status = str(record.get("bundle_status") or "").strip()
    source_repair_plan_status = str(
        record.get("source_repair_plan_status") or ""
    ).strip()
    source_feedback_status = str(record.get("source_feedback_status") or "").strip()
    source_status = str(record.get("source_status") or "").strip()
    source_exit_code = record.get("source_exit_code")
    recommended_next_action = str(
        record.get("recommended_next_action") or ""
    ).strip()
    reason = str(record.get("reason") or "").strip()

    source_repair_item_count = record.get("source_repair_item_count")
    bundle_item_count = record.get("bundle_item_count")
    bundle_items = record.get("bundle_items")
    bundle_targets = record.get("bundle_targets")

    requires_operator_review = bool(record.get("requires_operator_review"))
    bundle_reviewed = bool(record.get("bundle_reviewed"))
    bundle_execution_enabled = bool(record.get("bundle_execution_enabled"))
    repair_execution_enabled = bool(record.get("repair_execution_enabled"))
    real_execution_enabled = bool(record.get("real_execution_enabled"))
    subprocess_enabled = bool(record.get("subprocess_enabled"))
    bundle_execution_performed = bool(record.get("bundle_execution_performed"))
    bundle_subprocess_invoked = bool(record.get("bundle_subprocess_invoked"))
    repair_execution_performed = bool(record.get("repair_execution_performed"))
    repair_subprocess_invoked = bool(record.get("repair_subprocess_invoked"))
    execution_performed = bool(record.get("execution_performed"))
    subprocess_invoked = bool(record.get("subprocess_invoked"))

    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    if not bundle_id:
        reasons.append("missing_real_execution_read_only_repair_action_bundle_id")
    if not repair_plan_id:
        reasons.append("missing_real_execution_read_only_repair_plan_id")
    if not feedback_id:
        reasons.append("missing_real_execution_read_only_feedback_id")
    if not execution_result_id:
        reasons.append("missing_real_execution_read_only_execution_result_id")
    if not rendered_command_id:
        reasons.append("missing_rendered_command_id")

    if bundle_status not in {"assembled", "unknown"}:
        reasons.append("invalid_read_only_repair_action_bundle_status")
    if source_repair_plan_status not in {
        "planned",
        "blocked",
        "no_repair_needed",
        "unknown",
    }:
        reasons.append("invalid_read_only_repair_action_bundle_source_plan_status")
    if source_feedback_status not in {"actionable", "blocked", "successful", "unknown"}:
        reasons.append("invalid_read_only_repair_action_bundle_source_feedback_status")
    if source_status not in {"failed", "executed", "rejected", "unknown"}:
        reasons.append("invalid_read_only_repair_action_bundle_source_status")
    if recommended_next_action != "review_repair_action_bundle":
        reasons.append("invalid_read_only_repair_action_bundle_next_action")
    if reason != "read_only_repair_action_bundle_recorded":
        reasons.append("invalid_read_only_repair_action_bundle_reason")

    if not isinstance(bundle_items, list):
        reasons.append("read_only_repair_action_bundle_items_must_be_list")
    if not isinstance(bundle_targets, list):
        reasons.append("read_only_repair_action_bundle_targets_must_be_list")
    if not isinstance(bundle_item_count, int):
        reasons.append("read_only_repair_action_bundle_item_count_must_be_int")
    elif isinstance(bundle_items, list) and bundle_item_count != len(bundle_items):
        reasons.append("read_only_repair_action_bundle_item_count_mismatch")

    if isinstance(source_repair_item_count, int) and isinstance(bundle_item_count, int):
        if source_repair_item_count > 0 and bundle_item_count != source_repair_item_count:
            reasons.append("read_only_repair_action_bundle_source_item_count_mismatch")

    if source_repair_plan_status == "planned":
        if bundle_status != "assembled":
            reasons.append("planned_read_only_repair_action_bundle_must_be_assembled")
        if source_feedback_status != "actionable":
            reasons.append("planned_read_only_repair_action_bundle_source_must_be_actionable")
        if source_status != "failed":
            reasons.append("planned_read_only_repair_action_bundle_source_must_be_failed")
        if source_exit_code is None:
            reasons.append("planned_read_only_repair_action_bundle_requires_source_exit_code")
        if isinstance(bundle_item_count, int) and bundle_item_count <= 0:
            reasons.append("planned_read_only_repair_action_bundle_requires_items")
        if not requires_operator_review:
            reasons.append("planned_read_only_repair_action_bundle_requires_operator_review")

    if bundle_reviewed:
        reasons.append("read_only_repair_action_bundle_must_not_be_reviewed_yet")

    if bundle_execution_enabled or bool(payload_mapping.get("bundle_execution_enabled")):
        reasons.append("read_only_repair_action_bundle_must_not_enable_bundle_execution")
    if repair_execution_enabled or bool(payload_mapping.get("repair_execution_enabled")):
        reasons.append("read_only_repair_action_bundle_must_not_enable_repair_execution")
    if real_execution_enabled or bool(payload_mapping.get("real_execution_enabled")):
        reasons.append("read_only_repair_action_bundle_must_not_enable_real_execution")
    if subprocess_enabled or bool(payload_mapping.get("subprocess_enabled")):
        reasons.append("read_only_repair_action_bundle_must_not_enable_subprocess")
    if bundle_execution_performed or bool(
        payload_mapping.get("bundle_execution_performed")
    ):
        reasons.append("read_only_repair_action_bundle_must_not_perform_bundle_execution")
    if bundle_subprocess_invoked or bool(
        payload_mapping.get("bundle_subprocess_invoked")
    ):
        reasons.append("read_only_repair_action_bundle_must_not_invoke_bundle_subprocess")
    if repair_execution_performed or bool(
        payload_mapping.get("repair_execution_performed")
    ):
        reasons.append("read_only_repair_action_bundle_must_not_perform_repair_execution")
    if repair_subprocess_invoked or bool(
        payload_mapping.get("repair_subprocess_invoked")
    ):
        reasons.append("read_only_repair_action_bundle_must_not_invoke_repair_subprocess")
    if execution_performed or bool(payload_mapping.get("execution_performed")):
        reasons.append("read_only_repair_action_bundle_must_not_execute")
    if subprocess_invoked or bool(payload_mapping.get("subprocess_invoked")):
        reasons.append("read_only_repair_action_bundle_must_not_invoke_subprocess")

    if isinstance(bundle_items, list):
        for item in bundle_items:
            if not isinstance(item, Mapping):
                reasons.append("read_only_repair_action_bundle_item_must_be_mapping")
                continue
            if bool(item.get("execution_allowed")):
                reasons.append("read_only_repair_action_bundle_item_must_not_allow_execution")
            if bool(item.get("subprocess_allowed")):
                reasons.append("read_only_repair_action_bundle_item_must_not_allow_subprocess")
            if bool(item.get("real_execution_allowed")):
                reasons.append("read_only_repair_action_bundle_item_must_not_allow_real_execution")
            if bool(item.get("execution_performed")):
                reasons.append("read_only_repair_action_bundle_item_must_not_execute")
            if bool(item.get("subprocess_invoked")):
                reasons.append("read_only_repair_action_bundle_item_must_not_invoke_subprocess")

    return {
        "type": "security_validation_result",
        "record_type": (
            "replay_lifecycle_retry_real_execution_read_only_repair_action_bundle"
        ),
        "valid": not reasons,
        "severity": "critical" if reasons else "info",
        "reasons": reasons,
        "subject": bundle_id or repair_plan_id,
        "bundle_status": bundle_status or "unknown",
        "source_repair_plan_status": source_repair_plan_status or "unknown",
        "source_feedback_status": source_feedback_status or "unknown",
        "source_status": source_status or "unknown",
        "source_exit_code": source_exit_code,
        "recommended_next_action": recommended_next_action or "unknown",
        "source_repair_item_count": (
            source_repair_item_count if isinstance(source_repair_item_count, int) else 0
        ),
        "bundle_item_count": bundle_item_count if isinstance(bundle_item_count, int) else 0,
        "requires_operator_review": requires_operator_review,
        "bundle_reviewed": bundle_reviewed,
        "bundle_execution_enabled": bundle_execution_enabled,
        "repair_execution_enabled": repair_execution_enabled,
        "real_execution_enabled": real_execution_enabled,
        "subprocess_enabled": subprocess_enabled,
        "bundle_execution_performed": bundle_execution_performed,
        "bundle_subprocess_invoked": bundle_subprocess_invoked,
        "repair_execution_performed": repair_execution_performed,
        "repair_subprocess_invoked": repair_subprocess_invoked,
        "execution_performed": execution_performed,
        "subprocess_invoked": subprocess_invoked,
        "reason": reason or "unknown",
    }


def validate_replay_lifecycle_retry_real_execution_read_only_repair_action_bundle_review(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate read-only repair action bundle review records."""
    reasons: list[str] = []

    review_id = str(
        record.get("real_execution_read_only_repair_action_bundle_review_id") or ""
    ).strip()
    bundle_id = str(
        record.get("real_execution_read_only_repair_action_bundle_id") or ""
    ).strip()
    repair_plan_id = str(
        record.get("real_execution_read_only_repair_plan_id") or ""
    ).strip()
    feedback_id = str(record.get("real_execution_read_only_feedback_id") or "").strip()
    execution_result_id = str(
        record.get("real_execution_read_only_execution_result_id") or ""
    ).strip()
    rendered_command_id = str(record.get("rendered_command_id") or "").strip()

    review_status = str(record.get("review_status") or "").strip()
    source_bundle_status = str(record.get("source_bundle_status") or "").strip()
    source_repair_plan_status = str(
        record.get("source_repair_plan_status") or ""
    ).strip()
    source_feedback_status = str(record.get("source_feedback_status") or "").strip()
    source_status = str(record.get("source_status") or "").strip()
    source_exit_code = record.get("source_exit_code")
    source_bundle_item_count = record.get("source_bundle_item_count")
    recommended_next_action = str(
        record.get("recommended_next_action") or ""
    ).strip()
    reason = str(record.get("reason") or "").strip()

    operator_authorized = bool(record.get("operator_authorized"))
    requires_operator_review = bool(record.get("requires_operator_review"))
    reviewed = bool(record.get("reviewed"))
    review_approved = bool(record.get("review_approved"))
    review_rejected = bool(record.get("review_rejected"))

    bundle_execution_enabled = bool(record.get("bundle_execution_enabled"))
    repair_execution_enabled = bool(record.get("repair_execution_enabled"))
    real_execution_enabled = bool(record.get("real_execution_enabled"))
    subprocess_enabled = bool(record.get("subprocess_enabled"))
    bundle_execution_performed = bool(record.get("bundle_execution_performed"))
    bundle_subprocess_invoked = bool(record.get("bundle_subprocess_invoked"))
    repair_execution_performed = bool(record.get("repair_execution_performed"))
    repair_subprocess_invoked = bool(record.get("repair_subprocess_invoked"))
    execution_performed = bool(record.get("execution_performed"))
    subprocess_invoked = bool(record.get("subprocess_invoked"))

    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    if not review_id:
        reasons.append(
            "missing_real_execution_read_only_repair_action_bundle_review_id"
        )
    if not bundle_id:
        reasons.append("missing_real_execution_read_only_repair_action_bundle_id")
    if not repair_plan_id:
        reasons.append("missing_real_execution_read_only_repair_plan_id")
    if not feedback_id:
        reasons.append("missing_real_execution_read_only_feedback_id")
    if not execution_result_id:
        reasons.append("missing_real_execution_read_only_execution_result_id")
    if not rendered_command_id:
        reasons.append("missing_rendered_command_id")

    if review_status not in {"pending", "approved", "rejected"}:
        reasons.append("invalid_read_only_repair_action_bundle_review_status")
    if source_bundle_status not in {"assembled", "unknown"}:
        reasons.append("invalid_read_only_repair_action_bundle_review_source_bundle_status")
    if source_repair_plan_status not in {
        "planned",
        "blocked",
        "no_repair_needed",
        "unknown",
    }:
        reasons.append("invalid_read_only_repair_action_bundle_review_source_plan_status")
    if source_feedback_status not in {"actionable", "blocked", "successful", "unknown"}:
        reasons.append("invalid_read_only_repair_action_bundle_review_source_feedback_status")
    if source_status not in {"failed", "executed", "rejected", "unknown"}:
        reasons.append("invalid_read_only_repair_action_bundle_review_source_status")

    expected_next_actions = {
        "pending": "await_repair_action_bundle_review",
        "approved": "prepare_repair_execution_approval_scaffold",
        "rejected": "revise_repair_action_bundle",
    }
    if recommended_next_action != expected_next_actions.get(review_status):
        reasons.append("invalid_read_only_repair_action_bundle_review_next_action")
    if reason != "read_only_repair_action_bundle_review_recorded":
        reasons.append("invalid_read_only_repair_action_bundle_review_reason")

    if review_status == "pending":
        if reviewed:
            reasons.append("pending_read_only_repair_action_bundle_review_must_not_be_reviewed")
        if review_approved or review_rejected:
            reasons.append("pending_read_only_repair_action_bundle_review_invalid_flags")

    if review_status == "approved":
        if not reviewed:
            reasons.append("approved_read_only_repair_action_bundle_review_must_be_reviewed")
        if not review_approved:
            reasons.append("approved_read_only_repair_action_bundle_review_must_be_approved")
        if review_rejected:
            reasons.append("approved_read_only_repair_action_bundle_review_must_not_be_rejected")
        if not operator_authorized:
            reasons.append("approved_read_only_repair_action_bundle_review_requires_operator_authorized")
        if source_bundle_status != "assembled":
            reasons.append("approved_read_only_repair_action_bundle_review_source_bundle_must_be_assembled")
        if source_repair_plan_status != "planned":
            reasons.append("approved_read_only_repair_action_bundle_review_source_plan_must_be_planned")

    if review_status == "rejected":
        if not reviewed:
            reasons.append("rejected_read_only_repair_action_bundle_review_must_be_reviewed")
        if review_approved:
            reasons.append("rejected_read_only_repair_action_bundle_review_must_not_be_approved")
        if not review_rejected:
            reasons.append("rejected_read_only_repair_action_bundle_review_must_be_rejected")

    if not requires_operator_review:
        reasons.append("read_only_repair_action_bundle_review_requires_operator_review")
    if not isinstance(source_bundle_item_count, int):
        reasons.append("read_only_repair_action_bundle_review_source_item_count_must_be_int")

    if bundle_execution_enabled or bool(payload_mapping.get("bundle_execution_enabled")):
        reasons.append("read_only_repair_action_bundle_review_must_not_enable_bundle_execution")
    if repair_execution_enabled or bool(payload_mapping.get("repair_execution_enabled")):
        reasons.append("read_only_repair_action_bundle_review_must_not_enable_repair_execution")
    if real_execution_enabled or bool(payload_mapping.get("real_execution_enabled")):
        reasons.append("read_only_repair_action_bundle_review_must_not_enable_real_execution")
    if subprocess_enabled or bool(payload_mapping.get("subprocess_enabled")):
        reasons.append("read_only_repair_action_bundle_review_must_not_enable_subprocess")
    if bundle_execution_performed or bool(
        payload_mapping.get("bundle_execution_performed")
    ):
        reasons.append("read_only_repair_action_bundle_review_must_not_perform_bundle_execution")
    if bundle_subprocess_invoked or bool(
        payload_mapping.get("bundle_subprocess_invoked")
    ):
        reasons.append("read_only_repair_action_bundle_review_must_not_invoke_bundle_subprocess")
    if repair_execution_performed or bool(
        payload_mapping.get("repair_execution_performed")
    ):
        reasons.append("read_only_repair_action_bundle_review_must_not_perform_repair_execution")
    if repair_subprocess_invoked or bool(
        payload_mapping.get("repair_subprocess_invoked")
    ):
        reasons.append("read_only_repair_action_bundle_review_must_not_invoke_repair_subprocess")
    if execution_performed or bool(payload_mapping.get("execution_performed")):
        reasons.append("read_only_repair_action_bundle_review_must_not_execute")
    if subprocess_invoked or bool(payload_mapping.get("subprocess_invoked")):
        reasons.append("read_only_repair_action_bundle_review_must_not_invoke_subprocess")

    return {
        "type": "security_validation_result",
        "record_type": (
            "replay_lifecycle_retry_real_execution_read_only_repair_action_bundle_review"
        ),
        "valid": not reasons,
        "severity": "critical" if reasons else "info",
        "reasons": reasons,
        "subject": review_id or bundle_id,
        "review_status": review_status or "unknown",
        "source_bundle_status": source_bundle_status or "unknown",
        "source_repair_plan_status": source_repair_plan_status or "unknown",
        "source_feedback_status": source_feedback_status or "unknown",
        "source_status": source_status or "unknown",
        "source_exit_code": source_exit_code,
        "source_bundle_item_count": (
            source_bundle_item_count
            if isinstance(source_bundle_item_count, int)
            else 0
        ),
        "recommended_next_action": recommended_next_action or "unknown",
        "operator_authorized": operator_authorized,
        "requires_operator_review": requires_operator_review,
        "reviewed": reviewed,
        "review_approved": review_approved,
        "review_rejected": review_rejected,
        "bundle_execution_enabled": bundle_execution_enabled,
        "repair_execution_enabled": repair_execution_enabled,
        "real_execution_enabled": real_execution_enabled,
        "subprocess_enabled": subprocess_enabled,
        "bundle_execution_performed": bundle_execution_performed,
        "bundle_subprocess_invoked": bundle_subprocess_invoked,
        "repair_execution_performed": repair_execution_performed,
        "repair_subprocess_invoked": repair_subprocess_invoked,
        "execution_performed": execution_performed,
        "subprocess_invoked": subprocess_invoked,
        "reason": reason or "unknown",
    }


def validate_replay_lifecycle_retry_real_execution_repair_approval(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate repair execution approval scaffold records."""
    reasons: list[str] = []

    repair_approval_id = str(
        record.get("real_execution_repair_approval_id") or ""
    ).strip()
    review_id = str(
        record.get("real_execution_read_only_repair_action_bundle_review_id") or ""
    ).strip()
    bundle_id = str(
        record.get("real_execution_read_only_repair_action_bundle_id") or ""
    ).strip()
    repair_plan_id = str(
        record.get("real_execution_read_only_repair_plan_id") or ""
    ).strip()
    feedback_id = str(record.get("real_execution_read_only_feedback_id") or "").strip()
    read_only_result_id = str(
        record.get("real_execution_read_only_execution_result_id") or ""
    ).strip()
    rendered_command_id = str(record.get("rendered_command_id") or "").strip()

    approval_status = str(record.get("approval_status") or "").strip()
    source_review_status = str(record.get("source_review_status") or "").strip()
    source_bundle_status = str(record.get("source_bundle_status") or "").strip()
    source_repair_plan_status = str(
        record.get("source_repair_plan_status") or ""
    ).strip()
    source_feedback_status = str(record.get("source_feedback_status") or "").strip()
    source_status = str(record.get("source_status") or "").strip()
    recommended_next_action = str(
        record.get("recommended_next_action") or ""
    ).strip()
    reason = str(record.get("reason") or "").strip()

    source_reviewed = bool(record.get("source_reviewed"))
    source_review_approved = bool(record.get("source_review_approved"))
    operator_authorized = bool(record.get("operator_authorized"))
    requires_operator_review = bool(record.get("requires_operator_review"))
    repair_execution_approval_required = bool(
        record.get("repair_execution_approval_required")
    )
    repair_execution_approved = bool(record.get("repair_execution_approved"))
    repair_execution_rejected = bool(record.get("repair_execution_rejected"))

    bundle_execution_enabled = bool(record.get("bundle_execution_enabled"))
    repair_execution_enabled = bool(record.get("repair_execution_enabled"))
    real_execution_enabled = bool(record.get("real_execution_enabled"))
    subprocess_enabled = bool(record.get("subprocess_enabled"))
    bundle_execution_performed = bool(record.get("bundle_execution_performed"))
    bundle_subprocess_invoked = bool(record.get("bundle_subprocess_invoked"))
    repair_execution_performed = bool(record.get("repair_execution_performed"))
    repair_subprocess_invoked = bool(record.get("repair_subprocess_invoked"))
    execution_performed = bool(record.get("execution_performed"))
    subprocess_invoked = bool(record.get("subprocess_invoked"))

    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    if not repair_approval_id:
        reasons.append("missing_real_execution_repair_approval_id")
    if not review_id:
        reasons.append(
            "missing_real_execution_read_only_repair_action_bundle_review_id"
        )
    if not bundle_id:
        reasons.append("missing_real_execution_read_only_repair_action_bundle_id")
    if not repair_plan_id:
        reasons.append("missing_real_execution_read_only_repair_plan_id")
    if not feedback_id:
        reasons.append("missing_real_execution_read_only_feedback_id")
    if not read_only_result_id:
        reasons.append("missing_real_execution_read_only_execution_result_id")
    if not rendered_command_id:
        reasons.append("missing_rendered_command_id")

    if approval_status not in {"pending", "approved", "rejected"}:
        reasons.append("invalid_repair_execution_approval_status")
    if source_review_status != "approved":
        reasons.append("repair_execution_approval_source_review_must_be_approved")
    if not source_reviewed:
        reasons.append("repair_execution_approval_source_must_be_reviewed")
    if not source_review_approved:
        reasons.append("repair_execution_approval_source_must_be_review_approved")
    if source_bundle_status not in {"assembled", "unknown"}:
        reasons.append("invalid_repair_execution_approval_source_bundle_status")
    if source_repair_plan_status not in {"planned", "blocked", "no_repair_needed", "unknown"}:
        reasons.append("invalid_repair_execution_approval_source_plan_status")
    if source_feedback_status not in {"actionable", "blocked", "successful", "unknown"}:
        reasons.append("invalid_repair_execution_approval_source_feedback_status")
    if source_status not in {"failed", "executed", "rejected", "unknown"}:
        reasons.append("invalid_repair_execution_approval_source_status")

    expected_next_actions = {
        "pending": "await_repair_execution_approval",
        "approved": "await_repair_execution_approval_transition",
        "rejected": "revise_repair_action_bundle",
    }
    if recommended_next_action != expected_next_actions.get(approval_status):
        reasons.append("invalid_repair_execution_approval_next_action")
    if reason != "repair_execution_explicit_approval_required":
        reasons.append("invalid_repair_execution_approval_reason")

    if not operator_authorized:
        reasons.append("repair_execution_approval_requires_operator_authorized")
    if not requires_operator_review:
        reasons.append("repair_execution_approval_requires_operator_review")
    if not repair_execution_approval_required:
        reasons.append("repair_execution_approval_required_flag_missing")

    if approval_status == "pending":
        if repair_execution_approved:
            reasons.append("pending_repair_execution_approval_must_not_be_approved")
        if repair_execution_rejected:
            reasons.append("pending_repair_execution_approval_must_not_be_rejected")

    if approval_status == "approved":
        if not repair_execution_approved:
            reasons.append("approved_repair_execution_approval_must_be_approved")
        if repair_execution_rejected:
            reasons.append("approved_repair_execution_approval_must_not_be_rejected")

    if approval_status == "rejected":
        if repair_execution_approved:
            reasons.append("rejected_repair_execution_approval_must_not_be_approved")
        if not repair_execution_rejected:
            reasons.append("rejected_repair_execution_approval_must_be_rejected")

    if bundle_execution_enabled or bool(payload_mapping.get("bundle_execution_enabled")):
        reasons.append("repair_execution_approval_must_not_enable_bundle_execution")
    if repair_execution_enabled or bool(payload_mapping.get("repair_execution_enabled")):
        reasons.append("repair_execution_approval_must_not_enable_repair_execution")
    if real_execution_enabled or bool(payload_mapping.get("real_execution_enabled")):
        reasons.append("repair_execution_approval_must_not_enable_real_execution")
    if subprocess_enabled or bool(payload_mapping.get("subprocess_enabled")):
        reasons.append("repair_execution_approval_must_not_enable_subprocess")
    if bundle_execution_performed or bool(
        payload_mapping.get("bundle_execution_performed")
    ):
        reasons.append("repair_execution_approval_must_not_perform_bundle_execution")
    if bundle_subprocess_invoked or bool(payload_mapping.get("bundle_subprocess_invoked")):
        reasons.append("repair_execution_approval_must_not_invoke_bundle_subprocess")
    if repair_execution_performed or bool(
        payload_mapping.get("repair_execution_performed")
    ):
        reasons.append("repair_execution_approval_must_not_perform_repair_execution")
    if repair_subprocess_invoked or bool(payload_mapping.get("repair_subprocess_invoked")):
        reasons.append("repair_execution_approval_must_not_invoke_repair_subprocess")
    if execution_performed or bool(payload_mapping.get("execution_performed")):
        reasons.append("repair_execution_approval_must_not_execute")
    if subprocess_invoked or bool(payload_mapping.get("subprocess_invoked")):
        reasons.append("repair_execution_approval_must_not_invoke_subprocess")

    return {
        "type": "security_validation_result",
        "record_type": "replay_lifecycle_retry_real_execution_repair_approval",
        "valid": not reasons,
        "severity": "critical" if reasons else "info",
        "reasons": reasons,
        "subject": repair_approval_id or review_id,
        "approval_status": approval_status or "unknown",
        "source_review_status": source_review_status or "unknown",
        "source_reviewed": source_reviewed,
        "source_review_approved": source_review_approved,
        "source_bundle_status": source_bundle_status or "unknown",
        "source_repair_plan_status": source_repair_plan_status or "unknown",
        "source_feedback_status": source_feedback_status or "unknown",
        "source_status": source_status or "unknown",
        "source_exit_code": record.get("source_exit_code"),
        "source_bundle_item_count": record.get("source_bundle_item_count"),
        "recommended_next_action": recommended_next_action or "unknown",
        "operator_authorized": operator_authorized,
        "requires_operator_review": requires_operator_review,
        "repair_execution_approval_required": repair_execution_approval_required,
        "repair_execution_approved": repair_execution_approved,
        "repair_execution_rejected": repair_execution_rejected,
        "bundle_execution_enabled": bundle_execution_enabled,
        "repair_execution_enabled": repair_execution_enabled,
        "real_execution_enabled": real_execution_enabled,
        "subprocess_enabled": subprocess_enabled,
        "bundle_execution_performed": bundle_execution_performed,
        "bundle_subprocess_invoked": bundle_subprocess_invoked,
        "repair_execution_performed": repair_execution_performed,
        "repair_subprocess_invoked": repair_subprocess_invoked,
        "execution_performed": execution_performed,
        "subprocess_invoked": subprocess_invoked,
        "reason": reason or "unknown",
    }


def validate_replay_lifecycle_retry_real_execution_repair_approval_transition(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate repair execution approval transition records."""
    reasons: list[str] = []

    transition_id = str(
        record.get("real_execution_repair_approval_transition_id") or ""
    ).strip()
    repair_approval_id = str(
        record.get("real_execution_repair_approval_id") or ""
    ).strip()
    review_id = str(
        record.get("real_execution_read_only_repair_action_bundle_review_id") or ""
    ).strip()
    bundle_id = str(
        record.get("real_execution_read_only_repair_action_bundle_id") or ""
    ).strip()
    repair_plan_id = str(
        record.get("real_execution_read_only_repair_plan_id") or ""
    ).strip()
    feedback_id = str(record.get("real_execution_read_only_feedback_id") or "").strip()
    read_only_result_id = str(
        record.get("real_execution_read_only_execution_result_id") or ""
    ).strip()
    rendered_command_id = str(record.get("rendered_command_id") or "").strip()

    from_status = str(record.get("from_status") or "").strip()
    to_status = str(record.get("to_status") or "").strip()
    source_approval_status = str(record.get("source_approval_status") or "").strip()
    source_review_status = str(record.get("source_review_status") or "").strip()
    source_bundle_status = str(record.get("source_bundle_status") or "").strip()
    source_repair_plan_status = str(
        record.get("source_repair_plan_status") or ""
    ).strip()
    source_feedback_status = str(record.get("source_feedback_status") or "").strip()
    source_status = str(record.get("source_status") or "").strip()
    recommended_next_action = str(
        record.get("recommended_next_action") or ""
    ).strip()
    reason = str(record.get("reason") or "").strip()

    source_reviewed = bool(record.get("source_reviewed"))
    source_review_approved = bool(record.get("source_review_approved"))
    operator_authorized = bool(record.get("operator_authorized"))
    requires_operator_review = bool(record.get("requires_operator_review"))
    repair_execution_approval_required = bool(
        record.get("repair_execution_approval_required")
    )
    transition_approved = bool(record.get("repair_execution_transition_approved"))
    transition_rejected = bool(record.get("repair_execution_transition_rejected"))

    bundle_execution_enabled = bool(record.get("bundle_execution_enabled"))
    repair_execution_enabled = bool(record.get("repair_execution_enabled"))
    real_execution_enabled = bool(record.get("real_execution_enabled"))
    subprocess_enabled = bool(record.get("subprocess_enabled"))
    bundle_execution_performed = bool(record.get("bundle_execution_performed"))
    bundle_subprocess_invoked = bool(record.get("bundle_subprocess_invoked"))
    repair_execution_performed = bool(record.get("repair_execution_performed"))
    repair_subprocess_invoked = bool(record.get("repair_subprocess_invoked"))
    execution_performed = bool(record.get("execution_performed"))
    subprocess_invoked = bool(record.get("subprocess_invoked"))

    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    if not transition_id:
        reasons.append("missing_real_execution_repair_approval_transition_id")
    if not repair_approval_id:
        reasons.append("missing_real_execution_repair_approval_id")
    if not review_id:
        reasons.append(
            "missing_real_execution_read_only_repair_action_bundle_review_id"
        )
    if not bundle_id:
        reasons.append("missing_real_execution_read_only_repair_action_bundle_id")
    if not repair_plan_id:
        reasons.append("missing_real_execution_read_only_repair_plan_id")
    if not feedback_id:
        reasons.append("missing_real_execution_read_only_feedback_id")
    if not read_only_result_id:
        reasons.append("missing_real_execution_read_only_execution_result_id")
    if not rendered_command_id:
        reasons.append("missing_rendered_command_id")

    if from_status != "pending":
        reasons.append("repair_execution_approval_transition_from_status_must_be_pending")
    if source_approval_status != "pending":
        reasons.append(
            "repair_execution_approval_transition_source_approval_must_be_pending"
        )
    if to_status not in {"approved", "rejected"}:
        reasons.append("invalid_repair_execution_approval_transition_to_status")

    if source_review_status != "approved":
        reasons.append(
            "repair_execution_approval_transition_source_review_must_be_approved"
        )
    if not source_reviewed:
        reasons.append("repair_execution_approval_transition_source_must_be_reviewed")
    if not source_review_approved:
        reasons.append(
            "repair_execution_approval_transition_source_must_be_review_approved"
        )

    if source_bundle_status not in {"assembled", "unknown"}:
        reasons.append("invalid_repair_execution_approval_transition_source_bundle_status")
    if source_repair_plan_status not in {
        "planned",
        "blocked",
        "no_repair_needed",
        "unknown",
    }:
        reasons.append("invalid_repair_execution_approval_transition_source_plan_status")
    if source_feedback_status not in {"actionable", "blocked", "successful", "unknown"}:
        reasons.append(
            "invalid_repair_execution_approval_transition_source_feedback_status"
        )
    if source_status not in {"failed", "executed", "rejected", "unknown"}:
        reasons.append("invalid_repair_execution_approval_transition_source_status")

    expected_next_actions = {
        "approved": "prepare_repair_execution_final_gate",
        "rejected": "revise_repair_execution_approval",
    }
    if recommended_next_action != expected_next_actions.get(to_status):
        reasons.append("invalid_repair_execution_approval_transition_next_action")
    if reason != "repair_execution_approval_transition_recorded":
        reasons.append("invalid_repair_execution_approval_transition_reason")

    if not operator_authorized:
        reasons.append("repair_execution_approval_transition_requires_operator_authorized")
    if not requires_operator_review:
        reasons.append("repair_execution_approval_transition_requires_operator_review")
    if not repair_execution_approval_required:
        reasons.append("repair_execution_approval_transition_required_flag_missing")

    if to_status == "approved":
        if not transition_approved:
            reasons.append(
                "approved_repair_execution_approval_transition_must_be_approved"
            )
        if transition_rejected:
            reasons.append(
                "approved_repair_execution_approval_transition_must_not_be_rejected"
            )

    if to_status == "rejected":
        if transition_approved:
            reasons.append(
                "rejected_repair_execution_approval_transition_must_not_be_approved"
            )
        if not transition_rejected:
            reasons.append(
                "rejected_repair_execution_approval_transition_must_be_rejected"
            )

    if bundle_execution_enabled or bool(payload_mapping.get("bundle_execution_enabled")):
        reasons.append(
            "repair_execution_approval_transition_must_not_enable_bundle_execution"
        )
    if repair_execution_enabled or bool(payload_mapping.get("repair_execution_enabled")):
        reasons.append(
            "repair_execution_approval_transition_must_not_enable_repair_execution"
        )
    if real_execution_enabled or bool(payload_mapping.get("real_execution_enabled")):
        reasons.append(
            "repair_execution_approval_transition_must_not_enable_real_execution"
        )
    if subprocess_enabled or bool(payload_mapping.get("subprocess_enabled")):
        reasons.append("repair_execution_approval_transition_must_not_enable_subprocess")
    if bundle_execution_performed or bool(
        payload_mapping.get("bundle_execution_performed")
    ):
        reasons.append(
            "repair_execution_approval_transition_must_not_perform_bundle_execution"
        )
    if bundle_subprocess_invoked or bool(
        payload_mapping.get("bundle_subprocess_invoked")
    ):
        reasons.append(
            "repair_execution_approval_transition_must_not_invoke_bundle_subprocess"
        )
    if repair_execution_performed or bool(
        payload_mapping.get("repair_execution_performed")
    ):
        reasons.append(
            "repair_execution_approval_transition_must_not_perform_repair_execution"
        )
    if repair_subprocess_invoked or bool(
        payload_mapping.get("repair_subprocess_invoked")
    ):
        reasons.append(
            "repair_execution_approval_transition_must_not_invoke_repair_subprocess"
        )
    if execution_performed or bool(payload_mapping.get("execution_performed")):
        reasons.append("repair_execution_approval_transition_must_not_execute")
    if subprocess_invoked or bool(payload_mapping.get("subprocess_invoked")):
        reasons.append("repair_execution_approval_transition_must_not_invoke_subprocess")

    return {
        "type": "security_validation_result",
        "record_type": (
            "replay_lifecycle_retry_real_execution_repair_approval_transition"
        ),
        "valid": not reasons,
        "severity": "critical" if reasons else "info",
        "reasons": reasons,
        "subject": transition_id or repair_approval_id,
        "from_status": from_status or "unknown",
        "to_status": to_status or "unknown",
        "source_approval_status": source_approval_status or "unknown",
        "source_review_status": source_review_status or "unknown",
        "source_reviewed": source_reviewed,
        "source_review_approved": source_review_approved,
        "source_bundle_status": source_bundle_status or "unknown",
        "source_repair_plan_status": source_repair_plan_status or "unknown",
        "source_feedback_status": source_feedback_status or "unknown",
        "source_status": source_status or "unknown",
        "source_exit_code": record.get("source_exit_code"),
        "source_bundle_item_count": record.get("source_bundle_item_count"),
        "recommended_next_action": recommended_next_action or "unknown",
        "operator_authorized": operator_authorized,
        "requires_operator_review": requires_operator_review,
        "repair_execution_approval_required": repair_execution_approval_required,
        "repair_execution_transition_approved": transition_approved,
        "repair_execution_transition_rejected": transition_rejected,
        "bundle_execution_enabled": bundle_execution_enabled,
        "repair_execution_enabled": repair_execution_enabled,
        "real_execution_enabled": real_execution_enabled,
        "subprocess_enabled": subprocess_enabled,
        "bundle_execution_performed": bundle_execution_performed,
        "bundle_subprocess_invoked": bundle_subprocess_invoked,
        "repair_execution_performed": repair_execution_performed,
        "repair_subprocess_invoked": repair_subprocess_invoked,
        "execution_performed": execution_performed,
        "subprocess_invoked": subprocess_invoked,
        "reason": reason or "unknown",
    }


def validate_replay_lifecycle_retry_real_execution_repair_final_gate(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate repair execution final gate records."""
    reasons: list[str] = []

    gate_id = str(record.get("real_execution_repair_final_gate_id") or "").strip()
    transition_id = str(
        record.get("real_execution_repair_approval_transition_id") or ""
    ).strip()
    approval_id = str(record.get("real_execution_repair_approval_id") or "").strip()
    review_id = str(
        record.get("real_execution_read_only_repair_action_bundle_review_id") or ""
    ).strip()
    bundle_id = str(
        record.get("real_execution_read_only_repair_action_bundle_id") or ""
    ).strip()
    repair_plan_id = str(
        record.get("real_execution_read_only_repair_plan_id") or ""
    ).strip()
    rendered_command_id = str(record.get("rendered_command_id") or "").strip()

    gate_status = str(record.get("gate_status") or "").strip()
    next_action = str(record.get("recommended_next_action") or "").strip()
    reason = str(record.get("reason") or "").strip()

    source_transition_to_status = str(
        record.get("source_transition_to_status") or ""
    ).strip()
    source_transition_approved = bool(record.get("source_transition_approved"))
    source_review_status = str(record.get("source_review_status") or "").strip()
    source_bundle_status = str(record.get("source_bundle_status") or "").strip()
    source_repair_plan_status = str(
        record.get("source_repair_plan_status") or ""
    ).strip()

    repair_preconditions_satisfied = bool(
        record.get("repair_preconditions_satisfied")
    )
    ready_for_repair_execution = bool(record.get("ready_for_repair_execution"))
    would_execute = bool(record.get("would_execute"))
    operator_authorized = bool(record.get("operator_authorized"))
    repair_execution_approval_required = bool(
        record.get("repair_execution_approval_required")
    )
    transition_approved = bool(record.get("repair_execution_transition_approved"))

    bundle_execution_enabled = bool(record.get("bundle_execution_enabled"))
    repair_execution_enabled = bool(record.get("repair_execution_enabled"))
    real_execution_enabled = bool(record.get("real_execution_enabled"))
    subprocess_enabled = bool(record.get("subprocess_enabled"))
    bundle_execution_performed = bool(record.get("bundle_execution_performed"))
    bundle_subprocess_invoked = bool(record.get("bundle_subprocess_invoked"))
    repair_execution_performed = bool(record.get("repair_execution_performed"))
    repair_subprocess_invoked = bool(record.get("repair_subprocess_invoked"))
    execution_performed = bool(record.get("execution_performed"))
    subprocess_invoked = bool(record.get("subprocess_invoked"))

    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    if not gate_id:
        reasons.append("missing_real_execution_repair_final_gate_id")
    if not transition_id:
        reasons.append("missing_real_execution_repair_approval_transition_id")
    if not approval_id:
        reasons.append("missing_real_execution_repair_approval_id")
    if not review_id:
        reasons.append("missing_real_execution_read_only_repair_action_bundle_review_id")
    if not bundle_id:
        reasons.append("missing_real_execution_read_only_repair_action_bundle_id")
    if not repair_plan_id:
        reasons.append("missing_real_execution_read_only_repair_plan_id")
    if not rendered_command_id:
        reasons.append("missing_rendered_command_id")

    if gate_status not in {"ready_blocked", "blocked"}:
        reasons.append("invalid_repair_execution_final_gate_status")
    if source_transition_to_status != "approved":
        reasons.append("repair_final_gate_source_transition_must_be_approved")
    if not source_transition_approved:
        reasons.append("repair_final_gate_source_transition_approved_flag_required")
    if not transition_approved:
        reasons.append("repair_final_gate_transition_approved_flag_required")
    if source_review_status != "approved":
        reasons.append("repair_final_gate_source_review_must_be_approved")
    if source_bundle_status != "assembled":
        reasons.append("repair_final_gate_source_bundle_must_be_assembled")
    if source_repair_plan_status != "planned":
        reasons.append("repair_final_gate_source_repair_plan_must_be_planned")
    if not operator_authorized:
        reasons.append("repair_final_gate_requires_operator_authorized")
    if not repair_execution_approval_required:
        reasons.append("repair_final_gate_requires_repair_execution_approval_required")

    if gate_status == "ready_blocked" and not repair_preconditions_satisfied:
        reasons.append("ready_blocked_repair_final_gate_requires_satisfied_preconditions")
    if gate_status == "blocked" and repair_preconditions_satisfied:
        reasons.append("blocked_repair_final_gate_must_not_report_satisfied_preconditions")

    if ready_for_repair_execution:
        reasons.append("repair_final_gate_must_not_be_ready_for_repair_execution")
    if would_execute:
        reasons.append("repair_final_gate_must_not_would_execute")
    if next_action != "prepare_repair_execution_dry_run_envelope":
        reasons.append("invalid_repair_final_gate_next_action")
    if reason != "repair_execution_final_gate_recorded":
        reasons.append("invalid_repair_final_gate_reason")

    if bundle_execution_enabled or bool(payload_mapping.get("bundle_execution_enabled")):
        reasons.append("repair_final_gate_must_not_enable_bundle_execution")
    if repair_execution_enabled or bool(payload_mapping.get("repair_execution_enabled")):
        reasons.append("repair_final_gate_must_not_enable_repair_execution")
    if real_execution_enabled or bool(payload_mapping.get("real_execution_enabled")):
        reasons.append("repair_final_gate_must_not_enable_real_execution")
    if subprocess_enabled or bool(payload_mapping.get("subprocess_enabled")):
        reasons.append("repair_final_gate_must_not_enable_subprocess")
    if bundle_execution_performed or bool(payload_mapping.get("bundle_execution_performed")):
        reasons.append("repair_final_gate_must_not_perform_bundle_execution")
    if bundle_subprocess_invoked or bool(payload_mapping.get("bundle_subprocess_invoked")):
        reasons.append("repair_final_gate_must_not_invoke_bundle_subprocess")
    if repair_execution_performed or bool(payload_mapping.get("repair_execution_performed")):
        reasons.append("repair_final_gate_must_not_perform_repair_execution")
    if repair_subprocess_invoked or bool(payload_mapping.get("repair_subprocess_invoked")):
        reasons.append("repair_final_gate_must_not_invoke_repair_subprocess")
    if execution_performed or bool(payload_mapping.get("execution_performed")):
        reasons.append("repair_final_gate_must_not_execute")
    if subprocess_invoked or bool(payload_mapping.get("subprocess_invoked")):
        reasons.append("repair_final_gate_must_not_invoke_subprocess")

    return {
        "type": "security_validation_result",
        "record_type": "replay_lifecycle_retry_real_execution_repair_final_gate",
        "valid": not reasons,
        "severity": "critical" if reasons else "info",
        "reasons": reasons,
        "subject": gate_id or transition_id,
        "gate_status": gate_status or "unknown",
        "repair_preconditions_satisfied": repair_preconditions_satisfied,
        "ready_for_repair_execution": ready_for_repair_execution,
        "would_execute": would_execute,
        "recommended_next_action": next_action or "unknown",
        "operator_authorized": operator_authorized,
        "repair_execution_approval_required": repair_execution_approval_required,
        "repair_execution_transition_approved": transition_approved,
        "source_transition_to_status": source_transition_to_status or "unknown",
        "source_transition_approved": source_transition_approved,
        "source_review_status": source_review_status or "unknown",
        "source_bundle_status": source_bundle_status or "unknown",
        "source_repair_plan_status": source_repair_plan_status or "unknown",
        "bundle_execution_enabled": bundle_execution_enabled,
        "repair_execution_enabled": repair_execution_enabled,
        "real_execution_enabled": real_execution_enabled,
        "subprocess_enabled": subprocess_enabled,
        "bundle_execution_performed": bundle_execution_performed,
        "bundle_subprocess_invoked": bundle_subprocess_invoked,
        "repair_execution_performed": repair_execution_performed,
        "repair_subprocess_invoked": repair_subprocess_invoked,
        "execution_performed": execution_performed,
        "subprocess_invoked": subprocess_invoked,
        "reason": reason or "unknown",
    }


def validate_replay_lifecycle_retry_real_execution_repair_dry_run_envelope(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate repair execution dry-run envelope records."""
    reasons: list[str] = []

    envelope_id = str(
        record.get("real_execution_repair_dry_run_envelope_id") or ""
    ).strip()
    final_gate_id = str(
        record.get("real_execution_repair_final_gate_id") or ""
    ).strip()
    transition_id = str(
        record.get("real_execution_repair_approval_transition_id") or ""
    ).strip()
    repair_approval_id = str(
        record.get("real_execution_repair_approval_id") or ""
    ).strip()
    bundle_id = str(
        record.get("real_execution_read_only_repair_action_bundle_id") or ""
    ).strip()
    repair_plan_id = str(
        record.get("real_execution_read_only_repair_plan_id") or ""
    ).strip()
    rendered_command_id = str(record.get("rendered_command_id") or "").strip()

    dry_run_status = str(record.get("repair_dry_run_status") or "").strip()
    dry_run_mode = str(record.get("repair_dry_run_mode") or "").strip()
    source_gate_status = str(record.get("source_gate_status") or "").strip()
    next_action = str(record.get("recommended_next_action") or "").strip()
    reason = str(record.get("reason") or "").strip()

    dry_run_only = bool(record.get("dry_run_only"))
    source_ready_blocked = bool(record.get("source_final_gate_ready_blocked"))
    source_preconditions_satisfied = bool(
        record.get("source_final_gate_preconditions_satisfied")
    )
    source_transition_approved = bool(record.get("source_transition_approved"))
    operator_authorized = bool(record.get("operator_authorized"))
    ready_for_repair_execution = bool(record.get("ready_for_repair_execution"))
    would_execute = bool(record.get("would_execute"))

    repair_dry_run_target_count = record.get("repair_dry_run_target_count")
    repair_dry_run_targets = record.get("repair_dry_run_targets")
    if not isinstance(repair_dry_run_targets, list):
        repair_dry_run_targets = []

    report = record.get("repair_dry_run_report")
    report_mapping = report if isinstance(report, Mapping) else {}

    bundle_execution_enabled = bool(record.get("bundle_execution_enabled"))
    repair_execution_enabled = bool(record.get("repair_execution_enabled"))
    real_execution_enabled = bool(record.get("real_execution_enabled"))
    subprocess_enabled = bool(record.get("subprocess_enabled"))
    bundle_execution_performed = bool(record.get("bundle_execution_performed"))
    bundle_subprocess_invoked = bool(record.get("bundle_subprocess_invoked"))
    repair_execution_performed = bool(record.get("repair_execution_performed"))
    repair_subprocess_invoked = bool(record.get("repair_subprocess_invoked"))
    execution_performed = bool(record.get("execution_performed"))
    subprocess_invoked = bool(record.get("subprocess_invoked"))

    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    if not envelope_id:
        reasons.append("missing_real_execution_repair_dry_run_envelope_id")
    if not final_gate_id:
        reasons.append("missing_real_execution_repair_final_gate_id")
    if not transition_id:
        reasons.append("missing_real_execution_repair_approval_transition_id")
    if not repair_approval_id:
        reasons.append("missing_real_execution_repair_approval_id")
    if not bundle_id:
        reasons.append("missing_real_execution_read_only_repair_action_bundle_id")
    if not repair_plan_id:
        reasons.append("missing_real_execution_read_only_repair_plan_id")
    if not rendered_command_id:
        reasons.append("missing_rendered_command_id")

    if dry_run_status != "prepared":
        reasons.append("invalid_repair_dry_run_envelope_status")
    if not dry_run_only:
        reasons.append("repair_dry_run_envelope_must_be_dry_run_only")
    if dry_run_mode != "repair_action_bundle_validation":
        reasons.append("invalid_repair_dry_run_envelope_mode")
    if source_gate_status != "ready_blocked":
        reasons.append("repair_dry_run_envelope_source_gate_must_be_ready_blocked")
    if not source_ready_blocked:
        reasons.append("repair_dry_run_envelope_source_ready_blocked_required")
    if not source_preconditions_satisfied:
        reasons.append("repair_dry_run_envelope_source_preconditions_required")
    if not source_transition_approved:
        reasons.append("repair_dry_run_envelope_source_transition_approved_required")
    if not operator_authorized:
        reasons.append("repair_dry_run_envelope_requires_operator_authorized")

    if repair_dry_run_target_count != len(repair_dry_run_targets):
        reasons.append("repair_dry_run_envelope_target_count_mismatch")
    if len(repair_dry_run_targets) <= 0:
        reasons.append("repair_dry_run_envelope_targets_required")

    if report_mapping.get("applies_changes") is not False:
        reasons.append("repair_dry_run_report_must_not_apply_changes")
    if report_mapping.get("invokes_subprocess") is not False:
        reasons.append("repair_dry_run_report_must_not_invoke_subprocess")
    if report_mapping.get("executes_bundle") is not False:
        reasons.append("repair_dry_run_report_must_not_execute_bundle")

    if ready_for_repair_execution:
        reasons.append("repair_dry_run_envelope_must_not_be_ready_for_repair_execution")
    if would_execute:
        reasons.append("repair_dry_run_envelope_must_not_would_execute")
    if next_action != "prepare_repair_execution_noop_harness":
        reasons.append("invalid_repair_dry_run_envelope_next_action")
    if reason != "repair_execution_dry_run_envelope_recorded":
        reasons.append("invalid_repair_dry_run_envelope_reason")

    if bundle_execution_enabled or bool(payload_mapping.get("bundle_execution_enabled")):
        reasons.append("repair_dry_run_envelope_must_not_enable_bundle_execution")
    if repair_execution_enabled or bool(payload_mapping.get("repair_execution_enabled")):
        reasons.append("repair_dry_run_envelope_must_not_enable_repair_execution")
    if real_execution_enabled or bool(payload_mapping.get("real_execution_enabled")):
        reasons.append("repair_dry_run_envelope_must_not_enable_real_execution")
    if subprocess_enabled or bool(payload_mapping.get("subprocess_enabled")):
        reasons.append("repair_dry_run_envelope_must_not_enable_subprocess")
    if bundle_execution_performed or bool(
        payload_mapping.get("bundle_execution_performed")
    ):
        reasons.append("repair_dry_run_envelope_must_not_perform_bundle_execution")
    if bundle_subprocess_invoked or bool(
        payload_mapping.get("bundle_subprocess_invoked")
    ):
        reasons.append("repair_dry_run_envelope_must_not_invoke_bundle_subprocess")
    if repair_execution_performed or bool(
        payload_mapping.get("repair_execution_performed")
    ):
        reasons.append("repair_dry_run_envelope_must_not_perform_repair_execution")
    if repair_subprocess_invoked or bool(payload_mapping.get("repair_subprocess_invoked")):
        reasons.append("repair_dry_run_envelope_must_not_invoke_repair_subprocess")
    if execution_performed or bool(payload_mapping.get("execution_performed")):
        reasons.append("repair_dry_run_envelope_must_not_execute")
    if subprocess_invoked or bool(payload_mapping.get("subprocess_invoked")):
        reasons.append("repair_dry_run_envelope_must_not_invoke_subprocess")

    return {
        "type": "security_validation_result",
        "record_type": (
            "replay_lifecycle_retry_real_execution_repair_dry_run_envelope"
        ),
        "valid": not reasons,
        "severity": "critical" if reasons else "info",
        "reasons": reasons,
        "subject": envelope_id or final_gate_id,
        "repair_dry_run_status": dry_run_status or "unknown",
        "dry_run_only": dry_run_only,
        "repair_dry_run_mode": dry_run_mode or "unknown",
        "repair_dry_run_target_count": repair_dry_run_target_count,
        "source_gate_status": source_gate_status or "unknown",
        "source_final_gate_ready_blocked": source_ready_blocked,
        "source_final_gate_preconditions_satisfied": source_preconditions_satisfied,
        "source_transition_approved": source_transition_approved,
        "operator_authorized": operator_authorized,
        "ready_for_repair_execution": ready_for_repair_execution,
        "would_execute": would_execute,
        "recommended_next_action": next_action or "unknown",
        "bundle_execution_enabled": bundle_execution_enabled,
        "repair_execution_enabled": repair_execution_enabled,
        "real_execution_enabled": real_execution_enabled,
        "subprocess_enabled": subprocess_enabled,
        "bundle_execution_performed": bundle_execution_performed,
        "bundle_subprocess_invoked": bundle_subprocess_invoked,
        "repair_execution_performed": repair_execution_performed,
        "repair_subprocess_invoked": repair_subprocess_invoked,
        "execution_performed": execution_performed,
        "subprocess_invoked": subprocess_invoked,
        "reason": reason or "unknown",
    }


def validate_replay_lifecycle_retry_real_execution_repair_noop_result(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate repair execution noop result records.

    This record is allowed to have execution_performed=true and
    subprocess_invoked=true only for the controlled noop subprocess. It must
    never execute repair actions, the repair bundle, the repair command, or the
    original rendered command.
    """
    reasons: list[str] = []

    result_id = str(record.get("real_execution_repair_noop_result_id") or "").strip()
    envelope_id = str(
        record.get("real_execution_repair_dry_run_envelope_id") or ""
    ).strip()
    final_gate_id = str(
        record.get("real_execution_repair_final_gate_id") or ""
    ).strip()
    transition_id = str(
        record.get("real_execution_repair_approval_transition_id") or ""
    ).strip()
    repair_approval_id = str(
        record.get("real_execution_repair_approval_id") or ""
    ).strip()
    bundle_id = str(
        record.get("real_execution_read_only_repair_action_bundle_id") or ""
    ).strip()
    repair_plan_id = str(
        record.get("real_execution_read_only_repair_plan_id") or ""
    ).strip()
    rendered_command_id = str(record.get("rendered_command_id") or "").strip()

    status = str(record.get("repair_noop_status") or "").strip()
    reason = str(record.get("reason") or "").strip()
    next_action = str(record.get("recommended_next_action") or "").strip()
    noop_marker = str(record.get("noop_marker") or "").strip()
    stdout = str(record.get("stdout") or "")
    stderr = str(record.get("stderr") or "")

    exit_code = record.get("exit_code")
    noop_only = bool(record.get("noop_only"))
    stdout_marker_observed = bool(record.get("noop_stdout_marker_observed"))
    source_dry_run_only = bool(record.get("source_dry_run_only"))
    source_final_gate_ready_blocked = bool(
        record.get("source_final_gate_ready_blocked")
    )
    source_transition_approved = bool(record.get("source_transition_approved"))
    operator_authorized = bool(record.get("operator_authorized"))

    source_envelope_status = str(record.get("source_envelope_status") or "").strip()
    source_mode = str(record.get("source_repair_dry_run_mode") or "").strip()
    source_target_count = record.get("source_repair_dry_run_target_count")

    dry_run_envelope_executed = bool(record.get("dry_run_envelope_executed"))
    repair_dry_run_envelope_executed = bool(
        record.get("repair_dry_run_envelope_executed")
    )
    repair_actions_executed = bool(record.get("repair_actions_executed"))
    repair_bundle_executed = bool(record.get("repair_bundle_executed"))
    repair_command_executed = bool(record.get("repair_command_executed"))
    rendered_command_executed = bool(record.get("rendered_command_executed"))
    dry_run_command_executed = bool(record.get("dry_run_command_executed"))

    bundle_execution_enabled = bool(record.get("bundle_execution_enabled"))
    repair_execution_enabled = bool(record.get("repair_execution_enabled"))
    real_execution_enabled = bool(record.get("real_execution_enabled"))
    subprocess_enabled = bool(record.get("subprocess_enabled"))
    bundle_execution_performed = bool(record.get("bundle_execution_performed"))
    bundle_subprocess_invoked = bool(record.get("bundle_subprocess_invoked"))
    repair_execution_performed = bool(record.get("repair_execution_performed"))
    repair_subprocess_invoked = bool(record.get("repair_subprocess_invoked"))

    execution_performed = bool(record.get("execution_performed"))
    subprocess_invoked = bool(record.get("subprocess_invoked"))

    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    if not result_id:
        reasons.append("missing_real_execution_repair_noop_result_id")
    if not envelope_id:
        reasons.append("missing_real_execution_repair_dry_run_envelope_id")
    if not final_gate_id:
        reasons.append("missing_real_execution_repair_final_gate_id")
    if not transition_id:
        reasons.append("missing_real_execution_repair_approval_transition_id")
    if not repair_approval_id:
        reasons.append("missing_real_execution_repair_approval_id")
    if not bundle_id:
        reasons.append("missing_real_execution_read_only_repair_action_bundle_id")
    if not repair_plan_id:
        reasons.append("missing_real_execution_read_only_repair_plan_id")
    if not rendered_command_id:
        reasons.append("missing_rendered_command_id")

    if status not in {"completed", "failed"}:
        reasons.append("invalid_repair_noop_status")
    if not noop_only:
        reasons.append("repair_noop_result_must_be_noop_only")
    if not noop_marker:
        reasons.append("missing_repair_noop_marker")
    if noop_marker and noop_marker not in stdout:
        reasons.append("repair_noop_marker_missing_from_stdout")
    if stdout_marker_observed != bool(noop_marker and noop_marker in stdout):
        reasons.append("repair_noop_stdout_marker_observed_mismatch")

    if status == "completed":
        if exit_code != 0:
            reasons.append("completed_repair_noop_result_requires_exit_code_zero")
        if not stdout_marker_observed:
            reasons.append("completed_repair_noop_result_requires_stdout_marker")
        if reason != "repair_execution_noop_harness_completed":
            reasons.append("invalid_completed_repair_noop_reason")
        if next_action != "inspect_repair_noop_result":
            reasons.append("invalid_completed_repair_noop_next_action")

    if status == "failed":
        if reason != "repair_execution_noop_harness_failed":
            reasons.append("invalid_failed_repair_noop_reason")
        if next_action != "investigate_repair_noop_harness_failure":
            reasons.append("invalid_failed_repair_noop_next_action")

    if source_envelope_status != "prepared":
        reasons.append("repair_noop_source_envelope_must_be_prepared")
    if not source_dry_run_only:
        reasons.append("repair_noop_source_envelope_must_be_dry_run_only")
    if source_mode != "repair_action_bundle_validation":
        reasons.append("repair_noop_source_mode_must_be_repair_action_bundle_validation")
    if not source_final_gate_ready_blocked:
        reasons.append("repair_noop_source_final_gate_must_be_ready_blocked")
    if not source_transition_approved:
        reasons.append("repair_noop_source_transition_must_be_approved")
    if not operator_authorized:
        reasons.append("repair_noop_requires_operator_authorized")
    if not isinstance(source_target_count, int) or source_target_count <= 0:
        reasons.append("repair_noop_source_targets_required")

    # Controlled noop subprocess must be observed.
    if not execution_performed:
        reasons.append("repair_noop_must_record_noop_execution_performed")
    if not subprocess_invoked:
        reasons.append("repair_noop_must_record_noop_subprocess_invoked")

    # But repair execution must remain disabled and unperformed.
    if dry_run_envelope_executed or bool(
        payload_mapping.get("dry_run_envelope_executed")
    ):
        reasons.append("repair_noop_must_not_execute_dry_run_envelope")
    if repair_dry_run_envelope_executed or bool(
        payload_mapping.get("repair_dry_run_envelope_executed")
    ):
        reasons.append("repair_noop_must_not_execute_repair_dry_run_envelope")
    if repair_actions_executed or bool(payload_mapping.get("repair_actions_executed")):
        reasons.append("repair_noop_must_not_execute_repair_actions")
    if repair_bundle_executed or bool(payload_mapping.get("repair_bundle_executed")):
        reasons.append("repair_noop_must_not_execute_repair_bundle")
    if repair_command_executed or bool(payload_mapping.get("repair_command_executed")):
        reasons.append("repair_noop_must_not_execute_repair_command")
    if rendered_command_executed or bool(payload_mapping.get("rendered_command_executed")):
        reasons.append("repair_noop_must_not_execute_rendered_command")
    if dry_run_command_executed or bool(payload_mapping.get("dry_run_command_executed")):
        reasons.append("repair_noop_must_not_execute_dry_run_command")

    if bundle_execution_enabled or bool(payload_mapping.get("bundle_execution_enabled")):
        reasons.append("repair_noop_must_not_enable_bundle_execution")
    if repair_execution_enabled or bool(payload_mapping.get("repair_execution_enabled")):
        reasons.append("repair_noop_must_not_enable_repair_execution")
    if real_execution_enabled or bool(payload_mapping.get("real_execution_enabled")):
        reasons.append("repair_noop_must_not_enable_real_execution")
    if subprocess_enabled or bool(payload_mapping.get("subprocess_enabled")):
        reasons.append("repair_noop_must_not_enable_subprocess")
    if bundle_execution_performed or bool(
        payload_mapping.get("bundle_execution_performed")
    ):
        reasons.append("repair_noop_must_not_perform_bundle_execution")
    if bundle_subprocess_invoked or bool(
        payload_mapping.get("bundle_subprocess_invoked")
    ):
        reasons.append("repair_noop_must_not_invoke_bundle_subprocess")
    if repair_execution_performed or bool(
        payload_mapping.get("repair_execution_performed")
    ):
        reasons.append("repair_noop_must_not_perform_repair_execution")
    if repair_subprocess_invoked or bool(payload_mapping.get("repair_subprocess_invoked")):
        reasons.append("repair_noop_must_not_invoke_repair_subprocess")

    return {
        "type": "security_validation_result",
        "record_type": "replay_lifecycle_retry_real_execution_repair_noop_result",
        "valid": not reasons,
        "severity": "critical" if reasons else "info",
        "reasons": reasons,
        "subject": result_id or envelope_id,
        "repair_noop_status": status or "unknown",
        "noop_only": noop_only,
        "noop_stdout_marker_observed": stdout_marker_observed,
        "noop_marker": noop_marker or "unknown",
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "source_envelope_status": source_envelope_status or "unknown",
        "source_dry_run_only": source_dry_run_only,
        "source_repair_dry_run_mode": source_mode or "unknown",
        "source_repair_dry_run_target_count": source_target_count,
        "source_final_gate_ready_blocked": source_final_gate_ready_blocked,
        "source_transition_approved": source_transition_approved,
        "operator_authorized": operator_authorized,
        "dry_run_envelope_executed": dry_run_envelope_executed,
        "repair_dry_run_envelope_executed": repair_dry_run_envelope_executed,
        "repair_actions_executed": repair_actions_executed,
        "repair_bundle_executed": repair_bundle_executed,
        "repair_command_executed": repair_command_executed,
        "rendered_command_executed": rendered_command_executed,
        "dry_run_command_executed": dry_run_command_executed,
        "bundle_execution_enabled": bundle_execution_enabled,
        "repair_execution_enabled": repair_execution_enabled,
        "real_execution_enabled": real_execution_enabled,
        "subprocess_enabled": subprocess_enabled,
        "bundle_execution_performed": bundle_execution_performed,
        "bundle_subprocess_invoked": bundle_subprocess_invoked,
        "repair_execution_performed": repair_execution_performed,
        "repair_subprocess_invoked": repair_subprocess_invoked,
        "execution_performed": execution_performed,
        "subprocess_invoked": subprocess_invoked,
        "recommended_next_action": next_action or "unknown",
        "reason": reason or "unknown",
    }


def validate_replay_lifecycle_retry_real_execution_repair_noop_feedback(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate repair noop feedback records."""
    reasons: list[str] = []

    feedback_id = str(
        record.get("real_execution_repair_noop_feedback_id") or ""
    ).strip()
    noop_result_id = str(
        record.get("real_execution_repair_noop_result_id") or ""
    ).strip()
    envelope_id = str(
        record.get("real_execution_repair_dry_run_envelope_id") or ""
    ).strip()
    final_gate_id = str(
        record.get("real_execution_repair_final_gate_id") or ""
    ).strip()
    transition_id = str(
        record.get("real_execution_repair_approval_transition_id") or ""
    ).strip()
    repair_approval_id = str(
        record.get("real_execution_repair_approval_id") or ""
    ).strip()
    bundle_id = str(
        record.get("real_execution_read_only_repair_action_bundle_id") or ""
    ).strip()
    repair_plan_id = str(
        record.get("real_execution_read_only_repair_plan_id") or ""
    ).strip()
    rendered_command_id = str(record.get("rendered_command_id") or "").strip()

    feedback_status = str(record.get("feedback_status") or "").strip()
    reason = str(record.get("reason") or "").strip()
    next_action = str(record.get("recommended_next_action") or "").strip()

    source_noop_status = str(record.get("source_noop_status") or "").strip()
    source_noop_exit_code = record.get("source_noop_exit_code")
    source_envelope_status = str(record.get("source_envelope_status") or "").strip()
    source_mode = str(record.get("source_repair_dry_run_mode") or "").strip()
    source_target_count = record.get("source_repair_dry_run_target_count")

    repair_noop_verified = bool(record.get("repair_noop_verified"))
    repair_path_can_proceed = bool(record.get("repair_path_can_proceed"))
    repair_path_next_gate_allowed = bool(record.get("repair_path_next_gate_allowed"))

    source_noop_only = bool(record.get("source_noop_only"))
    source_noop_stdout_marker_observed = bool(
        record.get("source_noop_stdout_marker_observed")
    )
    source_execution_performed = bool(record.get("source_execution_performed"))
    source_subprocess_invoked = bool(record.get("source_subprocess_invoked"))
    source_dry_run_only = bool(record.get("source_dry_run_only"))
    source_final_gate_ready_blocked = bool(
        record.get("source_final_gate_ready_blocked")
    )
    source_transition_approved = bool(record.get("source_transition_approved"))
    operator_authorized = bool(record.get("operator_authorized"))

    source_repair_actions_executed = bool(
        record.get("source_repair_actions_executed")
    )
    source_repair_bundle_executed = bool(
        record.get("source_repair_bundle_executed")
    )
    source_repair_command_executed = bool(
        record.get("source_repair_command_executed")
    )
    source_repair_execution_enabled = bool(
        record.get("source_repair_execution_enabled")
    )
    source_repair_execution_performed = bool(
        record.get("source_repair_execution_performed")
    )
    source_repair_subprocess_invoked = bool(
        record.get("source_repair_subprocess_invoked")
    )

    feedback_execution_performed = bool(record.get("feedback_execution_performed"))
    feedback_subprocess_invoked = bool(record.get("feedback_subprocess_invoked"))
    ready_for_repair_execution = bool(record.get("ready_for_repair_execution"))
    would_execute = bool(record.get("would_execute"))

    bundle_execution_enabled = bool(record.get("bundle_execution_enabled"))
    repair_execution_enabled = bool(record.get("repair_execution_enabled"))
    real_execution_enabled = bool(record.get("real_execution_enabled"))
    subprocess_enabled = bool(record.get("subprocess_enabled"))
    bundle_execution_performed = bool(record.get("bundle_execution_performed"))
    bundle_subprocess_invoked = bool(record.get("bundle_subprocess_invoked"))
    repair_execution_performed = bool(record.get("repair_execution_performed"))
    repair_subprocess_invoked = bool(record.get("repair_subprocess_invoked"))
    execution_performed = bool(record.get("execution_performed"))
    subprocess_invoked = bool(record.get("subprocess_invoked"))

    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    if not feedback_id:
        reasons.append("missing_real_execution_repair_noop_feedback_id")
    if not noop_result_id:
        reasons.append("missing_real_execution_repair_noop_result_id")
    if not envelope_id:
        reasons.append("missing_real_execution_repair_dry_run_envelope_id")
    if not final_gate_id:
        reasons.append("missing_real_execution_repair_final_gate_id")
    if not transition_id:
        reasons.append("missing_real_execution_repair_approval_transition_id")
    if not repair_approval_id:
        reasons.append("missing_real_execution_repair_approval_id")
    if not bundle_id:
        reasons.append("missing_real_execution_read_only_repair_action_bundle_id")
    if not repair_plan_id:
        reasons.append("missing_real_execution_read_only_repair_plan_id")
    if not rendered_command_id:
        reasons.append("missing_rendered_command_id")

    if feedback_status not in {"actionable", "blocked"}:
        reasons.append("invalid_repair_noop_feedback_status")
    if reason != "repair_execution_noop_feedback_recorded":
        reasons.append("invalid_repair_noop_feedback_reason")

    if feedback_status == "actionable":
        if not repair_noop_verified:
            reasons.append("actionable_repair_noop_feedback_requires_verified_noop")
        if not repair_path_can_proceed:
            reasons.append("actionable_repair_noop_feedback_requires_path_can_proceed")
        if not repair_path_next_gate_allowed:
            reasons.append(
                "actionable_repair_noop_feedback_requires_next_gate_allowed"
            )
        if next_action != "prepare_repair_execution_readiness_gate":
            reasons.append("invalid_actionable_repair_noop_feedback_next_action")

    if feedback_status == "blocked":
        if repair_path_can_proceed:
            reasons.append("blocked_repair_noop_feedback_must_not_allow_path")
        if repair_path_next_gate_allowed:
            reasons.append("blocked_repair_noop_feedback_must_not_allow_next_gate")

    if source_noop_status != "completed":
        reasons.append("repair_noop_feedback_source_noop_must_be_completed")
    if source_noop_exit_code != 0:
        reasons.append("repair_noop_feedback_source_exit_code_must_be_zero")
    if not source_noop_only:
        reasons.append("repair_noop_feedback_source_must_be_noop_only")
    if not source_noop_stdout_marker_observed:
        reasons.append("repair_noop_feedback_source_marker_required")
    if not source_execution_performed:
        reasons.append("repair_noop_feedback_source_execution_required")
    if not source_subprocess_invoked:
        reasons.append("repair_noop_feedback_source_subprocess_required")
    if source_envelope_status != "prepared":
        reasons.append("repair_noop_feedback_source_envelope_must_be_prepared")
    if not source_dry_run_only:
        reasons.append("repair_noop_feedback_source_envelope_must_be_dry_run_only")
    if source_mode != "repair_action_bundle_validation":
        reasons.append("repair_noop_feedback_source_mode_invalid")
    if not isinstance(source_target_count, int) or source_target_count <= 0:
        reasons.append("repair_noop_feedback_source_targets_required")
    if not source_final_gate_ready_blocked:
        reasons.append("repair_noop_feedback_source_gate_must_be_ready_blocked")
    if not source_transition_approved:
        reasons.append("repair_noop_feedback_source_transition_must_be_approved")
    if not operator_authorized:
        reasons.append("repair_noop_feedback_requires_operator_authorized")

    if source_repair_actions_executed:
        reasons.append("repair_noop_feedback_source_must_not_execute_repair_actions")
    if source_repair_bundle_executed:
        reasons.append("repair_noop_feedback_source_must_not_execute_repair_bundle")
    if source_repair_command_executed:
        reasons.append("repair_noop_feedback_source_must_not_execute_repair_command")
    if source_repair_execution_enabled:
        reasons.append("repair_noop_feedback_source_must_not_enable_repair_execution")
    if source_repair_execution_performed:
        reasons.append("repair_noop_feedback_source_must_not_perform_repair_execution")
    if source_repair_subprocess_invoked:
        reasons.append("repair_noop_feedback_source_must_not_invoke_repair_subprocess")

    if feedback_execution_performed or bool(
        payload_mapping.get("feedback_execution_performed")
    ):
        reasons.append("repair_noop_feedback_must_not_execute_feedback")
    if feedback_subprocess_invoked or bool(
        payload_mapping.get("feedback_subprocess_invoked")
    ):
        reasons.append("repair_noop_feedback_must_not_invoke_feedback_subprocess")
    if ready_for_repair_execution:
        reasons.append("repair_noop_feedback_must_not_be_ready_for_repair_execution")
    if would_execute:
        reasons.append("repair_noop_feedback_must_not_would_execute")

    if bundle_execution_enabled or bool(payload_mapping.get("bundle_execution_enabled")):
        reasons.append("repair_noop_feedback_must_not_enable_bundle_execution")
    if repair_execution_enabled or bool(payload_mapping.get("repair_execution_enabled")):
        reasons.append("repair_noop_feedback_must_not_enable_repair_execution")
    if real_execution_enabled or bool(payload_mapping.get("real_execution_enabled")):
        reasons.append("repair_noop_feedback_must_not_enable_real_execution")
    if subprocess_enabled or bool(payload_mapping.get("subprocess_enabled")):
        reasons.append("repair_noop_feedback_must_not_enable_subprocess")
    if bundle_execution_performed or bool(
        payload_mapping.get("bundle_execution_performed")
    ):
        reasons.append("repair_noop_feedback_must_not_perform_bundle_execution")
    if bundle_subprocess_invoked or bool(
        payload_mapping.get("bundle_subprocess_invoked")
    ):
        reasons.append("repair_noop_feedback_must_not_invoke_bundle_subprocess")
    if repair_execution_performed or bool(
        payload_mapping.get("repair_execution_performed")
    ):
        reasons.append("repair_noop_feedback_must_not_perform_repair_execution")
    if repair_subprocess_invoked or bool(payload_mapping.get("repair_subprocess_invoked")):
        reasons.append("repair_noop_feedback_must_not_invoke_repair_subprocess")
    if execution_performed or bool(payload_mapping.get("execution_performed")):
        reasons.append("repair_noop_feedback_must_not_execute")
    if subprocess_invoked or bool(payload_mapping.get("subprocess_invoked")):
        reasons.append("repair_noop_feedback_must_not_invoke_subprocess")

    return {
        "type": "security_validation_result",
        "record_type": "replay_lifecycle_retry_real_execution_repair_noop_feedback",
        "valid": not reasons,
        "severity": "critical" if reasons else "info",
        "reasons": reasons,
        "subject": feedback_id or noop_result_id,
        "feedback_status": feedback_status or "unknown",
        "repair_noop_verified": repair_noop_verified,
        "repair_path_can_proceed": repair_path_can_proceed,
        "repair_path_next_gate_allowed": repair_path_next_gate_allowed,
        "recommended_next_action": next_action or "unknown",
        "source_noop_status": source_noop_status or "unknown",
        "source_noop_exit_code": source_noop_exit_code,
        "source_noop_only": source_noop_only,
        "source_noop_stdout_marker_observed": source_noop_stdout_marker_observed,
        "source_execution_performed": source_execution_performed,
        "source_subprocess_invoked": source_subprocess_invoked,
        "source_envelope_status": source_envelope_status or "unknown",
        "source_dry_run_only": source_dry_run_only,
        "source_repair_dry_run_mode": source_mode or "unknown",
        "source_repair_dry_run_target_count": source_target_count,
        "source_final_gate_ready_blocked": source_final_gate_ready_blocked,
        "source_transition_approved": source_transition_approved,
        "operator_authorized": operator_authorized,
        "source_repair_actions_executed": source_repair_actions_executed,
        "source_repair_bundle_executed": source_repair_bundle_executed,
        "source_repair_command_executed": source_repair_command_executed,
        "source_repair_execution_enabled": source_repair_execution_enabled,
        "source_repair_execution_performed": source_repair_execution_performed,
        "source_repair_subprocess_invoked": source_repair_subprocess_invoked,
        "feedback_execution_performed": feedback_execution_performed,
        "feedback_subprocess_invoked": feedback_subprocess_invoked,
        "ready_for_repair_execution": ready_for_repair_execution,
        "would_execute": would_execute,
        "bundle_execution_enabled": bundle_execution_enabled,
        "repair_execution_enabled": repair_execution_enabled,
        "real_execution_enabled": real_execution_enabled,
        "subprocess_enabled": subprocess_enabled,
        "bundle_execution_performed": bundle_execution_performed,
        "bundle_subprocess_invoked": bundle_subprocess_invoked,
        "repair_execution_performed": repair_execution_performed,
        "repair_subprocess_invoked": repair_subprocess_invoked,
        "execution_performed": execution_performed,
        "subprocess_invoked": subprocess_invoked,
        "reason": reason or "unknown",
    }


def validate_replay_lifecycle_retry_real_execution_repair_readiness_gate(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate repair execution readiness gate records."""
    reasons: list[str] = []

    gate_id = str(
        record.get("real_execution_repair_readiness_gate_id") or ""
    ).strip()
    feedback_id = str(
        record.get("real_execution_repair_noop_feedback_id") or ""
    ).strip()
    noop_result_id = str(
        record.get("real_execution_repair_noop_result_id") or ""
    ).strip()
    envelope_id = str(
        record.get("real_execution_repair_dry_run_envelope_id") or ""
    ).strip()
    final_gate_id = str(
        record.get("real_execution_repair_final_gate_id") or ""
    ).strip()
    transition_id = str(
        record.get("real_execution_repair_approval_transition_id") or ""
    ).strip()
    repair_approval_id = str(
        record.get("real_execution_repair_approval_id") or ""
    ).strip()
    rendered_command_id = str(record.get("rendered_command_id") or "").strip()

    gate_status = str(record.get("gate_status") or "").strip()
    reason = str(record.get("reason") or "").strip()
    next_action = str(record.get("recommended_next_action") or "").strip()

    repair_readiness_satisfied = bool(record.get("repair_readiness_satisfied"))
    ready_for_guarded_repair_execution = bool(
        record.get("ready_for_guarded_repair_execution")
    )
    ready_for_repair_execution = bool(record.get("ready_for_repair_execution"))
    would_execute = bool(record.get("would_execute"))

    blocking_reasons = record.get("blocking_reasons")
    blocking_reasons_list = blocking_reasons if isinstance(blocking_reasons, list) else []

    source_feedback_status = str(record.get("source_feedback_status") or "").strip()
    source_repair_noop_verified = bool(record.get("source_repair_noop_verified"))
    source_repair_path_can_proceed = bool(
        record.get("source_repair_path_can_proceed")
    )
    source_repair_path_next_gate_allowed = bool(
        record.get("source_repair_path_next_gate_allowed")
    )
    source_noop_status = str(record.get("source_noop_status") or "").strip()
    source_noop_exit_code = record.get("source_noop_exit_code")
    source_noop_only = bool(record.get("source_noop_only"))
    source_noop_stdout_marker_observed = bool(
        record.get("source_noop_stdout_marker_observed")
    )
    source_execution_performed = bool(record.get("source_execution_performed"))
    source_subprocess_invoked = bool(record.get("source_subprocess_invoked"))
    source_envelope_status = str(record.get("source_envelope_status") or "").strip()
    source_dry_run_only = bool(record.get("source_dry_run_only"))
    source_mode = str(record.get("source_repair_dry_run_mode") or "").strip()
    source_target_count = record.get("source_repair_dry_run_target_count")
    source_final_gate_ready_blocked = bool(
        record.get("source_final_gate_ready_blocked")
    )
    source_transition_approved = bool(record.get("source_transition_approved"))
    operator_authorized = bool(record.get("operator_authorized"))

    source_repair_actions_executed = bool(record.get("source_repair_actions_executed"))
    source_repair_bundle_executed = bool(record.get("source_repair_bundle_executed"))
    source_repair_command_executed = bool(record.get("source_repair_command_executed"))
    source_repair_execution_enabled = bool(
        record.get("source_repair_execution_enabled")
    )
    source_repair_execution_performed = bool(
        record.get("source_repair_execution_performed")
    )
    source_repair_subprocess_invoked = bool(
        record.get("source_repair_subprocess_invoked")
    )

    bundle_execution_enabled = bool(record.get("bundle_execution_enabled"))
    repair_execution_enabled = bool(record.get("repair_execution_enabled"))
    real_execution_enabled = bool(record.get("real_execution_enabled"))
    subprocess_enabled = bool(record.get("subprocess_enabled"))
    bundle_execution_performed = bool(record.get("bundle_execution_performed"))
    bundle_subprocess_invoked = bool(record.get("bundle_subprocess_invoked"))
    repair_execution_performed = bool(record.get("repair_execution_performed"))
    repair_subprocess_invoked = bool(record.get("repair_subprocess_invoked"))
    execution_performed = bool(record.get("execution_performed"))
    subprocess_invoked = bool(record.get("subprocess_invoked"))

    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    if not gate_id:
        reasons.append("missing_real_execution_repair_readiness_gate_id")
    if not feedback_id:
        reasons.append("missing_real_execution_repair_noop_feedback_id")
    if not noop_result_id:
        reasons.append("missing_real_execution_repair_noop_result_id")
    if not envelope_id:
        reasons.append("missing_real_execution_repair_dry_run_envelope_id")
    if not final_gate_id:
        reasons.append("missing_real_execution_repair_final_gate_id")
    if not transition_id:
        reasons.append("missing_real_execution_repair_approval_transition_id")
    if not repair_approval_id:
        reasons.append("missing_real_execution_repair_approval_id")
    if not rendered_command_id:
        reasons.append("missing_rendered_command_id")

    if gate_status != "ready_blocked":
        reasons.append("repair_readiness_gate_must_be_ready_blocked")
    if reason != "repair_execution_readiness_gate_recorded":
        reasons.append("invalid_repair_readiness_gate_reason")
    if next_action != "prepare_guarded_repair_execution_harness":
        reasons.append("invalid_repair_readiness_gate_next_action")

    if not repair_readiness_satisfied:
        reasons.append("repair_readiness_gate_requires_satisfied_readiness")
    if not ready_for_guarded_repair_execution:
        reasons.append("repair_readiness_gate_requires_guarded_ready")
    if ready_for_repair_execution:
        reasons.append("repair_readiness_gate_must_not_be_ready_for_repair_execution")
    if would_execute:
        reasons.append("repair_readiness_gate_must_not_would_execute")

    if "guarded_repair_execution_requires_separate_pr" not in blocking_reasons_list:
        reasons.append("repair_readiness_gate_requires_separate_pr_blocker")

    if source_feedback_status != "actionable":
        reasons.append("repair_readiness_gate_source_feedback_must_be_actionable")
    if not source_repair_noop_verified:
        reasons.append("repair_readiness_gate_source_noop_must_be_verified")
    if not source_repair_path_can_proceed:
        reasons.append("repair_readiness_gate_source_path_must_proceed")
    if not source_repair_path_next_gate_allowed:
        reasons.append("repair_readiness_gate_source_next_gate_must_be_allowed")
    if source_noop_status != "completed":
        reasons.append("repair_readiness_gate_source_noop_must_be_completed")
    if source_noop_exit_code != 0:
        reasons.append("repair_readiness_gate_source_noop_exit_code_must_be_zero")
    if not source_noop_only:
        reasons.append("repair_readiness_gate_source_must_be_noop_only")
    if not source_noop_stdout_marker_observed:
        reasons.append("repair_readiness_gate_source_marker_required")
    if not source_execution_performed:
        reasons.append("repair_readiness_gate_source_noop_execution_required")
    if not source_subprocess_invoked:
        reasons.append("repair_readiness_gate_source_noop_subprocess_required")
    if source_envelope_status != "prepared":
        reasons.append("repair_readiness_gate_source_envelope_must_be_prepared")
    if not source_dry_run_only:
        reasons.append("repair_readiness_gate_source_envelope_must_be_dry_run_only")
    if source_mode != "repair_action_bundle_validation":
        reasons.append("repair_readiness_gate_source_mode_invalid")
    if not isinstance(source_target_count, int) or source_target_count <= 0:
        reasons.append("repair_readiness_gate_source_targets_required")
    if not source_final_gate_ready_blocked:
        reasons.append("repair_readiness_gate_source_final_gate_must_be_ready_blocked")
    if not source_transition_approved:
        reasons.append("repair_readiness_gate_source_transition_must_be_approved")
    if not operator_authorized:
        reasons.append("repair_readiness_gate_requires_operator_authorized")

    if source_repair_actions_executed:
        reasons.append("repair_readiness_gate_source_must_not_execute_repair_actions")
    if source_repair_bundle_executed:
        reasons.append("repair_readiness_gate_source_must_not_execute_repair_bundle")
    if source_repair_command_executed:
        reasons.append("repair_readiness_gate_source_must_not_execute_repair_command")
    if source_repair_execution_enabled:
        reasons.append("repair_readiness_gate_source_must_not_enable_repair_execution")
    if source_repair_execution_performed:
        reasons.append("repair_readiness_gate_source_must_not_perform_repair_execution")
    if source_repair_subprocess_invoked:
        reasons.append("repair_readiness_gate_source_must_not_invoke_repair_subprocess")

    if bundle_execution_enabled or bool(payload_mapping.get("bundle_execution_enabled")):
        reasons.append("repair_readiness_gate_must_not_enable_bundle_execution")
    if repair_execution_enabled or bool(payload_mapping.get("repair_execution_enabled")):
        reasons.append("repair_readiness_gate_must_not_enable_repair_execution")
    if real_execution_enabled or bool(payload_mapping.get("real_execution_enabled")):
        reasons.append("repair_readiness_gate_must_not_enable_real_execution")
    if subprocess_enabled or bool(payload_mapping.get("subprocess_enabled")):
        reasons.append("repair_readiness_gate_must_not_enable_subprocess")
    if bundle_execution_performed or bool(
        payload_mapping.get("bundle_execution_performed")
    ):
        reasons.append("repair_readiness_gate_must_not_perform_bundle_execution")
    if bundle_subprocess_invoked or bool(
        payload_mapping.get("bundle_subprocess_invoked")
    ):
        reasons.append("repair_readiness_gate_must_not_invoke_bundle_subprocess")
    if repair_execution_performed or bool(
        payload_mapping.get("repair_execution_performed")
    ):
        reasons.append("repair_readiness_gate_must_not_perform_repair_execution")
    if repair_subprocess_invoked or bool(payload_mapping.get("repair_subprocess_invoked")):
        reasons.append("repair_readiness_gate_must_not_invoke_repair_subprocess")
    if execution_performed or bool(payload_mapping.get("execution_performed")):
        reasons.append("repair_readiness_gate_must_not_execute")
    if subprocess_invoked or bool(payload_mapping.get("subprocess_invoked")):
        reasons.append("repair_readiness_gate_must_not_invoke_subprocess")

    return {
        "type": "security_validation_result",
        "record_type": "replay_lifecycle_retry_real_execution_repair_readiness_gate",
        "valid": not reasons,
        "severity": "critical" if reasons else "info",
        "reasons": reasons,
        "subject": gate_id or feedback_id,
        "gate_status": gate_status or "unknown",
        "repair_readiness_satisfied": repair_readiness_satisfied,
        "ready_for_guarded_repair_execution": ready_for_guarded_repair_execution,
        "ready_for_repair_execution": ready_for_repair_execution,
        "would_execute": would_execute,
        "recommended_next_action": next_action or "unknown",
        "source_feedback_status": source_feedback_status or "unknown",
        "source_repair_noop_verified": source_repair_noop_verified,
        "source_repair_path_can_proceed": source_repair_path_can_proceed,
        "source_repair_path_next_gate_allowed": source_repair_path_next_gate_allowed,
        "source_noop_status": source_noop_status or "unknown",
        "source_noop_exit_code": source_noop_exit_code,
        "source_execution_performed": source_execution_performed,
        "source_subprocess_invoked": source_subprocess_invoked,
        "source_envelope_status": source_envelope_status or "unknown",
        "source_dry_run_only": source_dry_run_only,
        "source_repair_dry_run_mode": source_mode or "unknown",
        "source_repair_dry_run_target_count": source_target_count,
        "source_final_gate_ready_blocked": source_final_gate_ready_blocked,
        "source_transition_approved": source_transition_approved,
        "operator_authorized": operator_authorized,
        "source_repair_actions_executed": source_repair_actions_executed,
        "source_repair_bundle_executed": source_repair_bundle_executed,
        "source_repair_command_executed": source_repair_command_executed,
        "source_repair_execution_enabled": source_repair_execution_enabled,
        "source_repair_execution_performed": source_repair_execution_performed,
        "source_repair_subprocess_invoked": source_repair_subprocess_invoked,
        "bundle_execution_enabled": bundle_execution_enabled,
        "repair_execution_enabled": repair_execution_enabled,
        "real_execution_enabled": real_execution_enabled,
        "subprocess_enabled": subprocess_enabled,
        "bundle_execution_performed": bundle_execution_performed,
        "bundle_subprocess_invoked": bundle_subprocess_invoked,
        "repair_execution_performed": repair_execution_performed,
        "repair_subprocess_invoked": repair_subprocess_invoked,
        "execution_performed": execution_performed,
        "subprocess_invoked": subprocess_invoked,
        "reason": reason or "unknown",
    }


def validate_replay_lifecycle_retry_guarded_repair_execution_result(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate guarded repair execution result records."""
    reasons: list[str] = []

    result_id = str(record.get("guarded_repair_execution_result_id") or "").strip()
    gate_id = str(record.get("real_execution_repair_readiness_gate_id") or "").strip()
    feedback_id = str(record.get("real_execution_repair_noop_feedback_id") or "").strip()
    noop_result_id = str(record.get("real_execution_repair_noop_result_id") or "").strip()
    envelope_id = str(record.get("real_execution_repair_dry_run_envelope_id") or "").strip()
    final_gate_id = str(record.get("real_execution_repair_final_gate_id") or "").strip()
    rendered_command_id = str(record.get("rendered_command_id") or "").strip()

    status = str(record.get("repair_execution_status") or "").strip()
    reason = str(record.get("reason") or "").strip()
    next_action = str(record.get("recommended_next_action") or "").strip()

    repair_execution_allowed = bool(record.get("repair_execution_allowed"))
    guarded_repair_execution = bool(record.get("guarded_repair_execution"))
    marker_observed = bool(record.get("guarded_repair_marker_observed"))
    exit_code = record.get("exit_code")
    target_count = record.get("repair_action_target_count")

    source_gate_status = str(record.get("source_gate_status") or "").strip()
    source_ready_guarded = bool(record.get("source_ready_for_guarded_repair_execution"))
    source_ready_repair = bool(record.get("source_ready_for_repair_execution"))
    source_would_execute = bool(record.get("source_would_execute"))
    source_feedback_status = str(record.get("source_feedback_status") or "").strip()
    source_noop_status = str(record.get("source_noop_status") or "").strip()
    source_noop_exit_code = record.get("source_noop_exit_code")
    source_execution_performed = bool(record.get("source_execution_performed"))
    source_subprocess_invoked = bool(record.get("source_subprocess_invoked"))
    source_repair_readiness_satisfied = bool(
        record.get("source_repair_readiness_satisfied")
    )
    source_repair_noop_verified = bool(record.get("source_repair_noop_verified"))
    source_repair_path_can_proceed = bool(record.get("source_repair_path_can_proceed"))
    source_repair_path_next_gate_allowed = bool(
        record.get("source_repair_path_next_gate_allowed")
    )
    operator_authorized = bool(record.get("operator_authorized"))

    repair_actions_executed = bool(record.get("repair_actions_executed"))
    repair_bundle_executed = bool(record.get("repair_bundle_executed"))
    repair_command_executed = bool(record.get("repair_command_executed"))
    rendered_command_executed = bool(record.get("rendered_command_executed"))
    dry_run_command_executed = bool(record.get("dry_run_command_executed"))

    bundle_execution_enabled = bool(record.get("bundle_execution_enabled"))
    repair_execution_enabled = bool(record.get("repair_execution_enabled"))
    real_execution_enabled = bool(record.get("real_execution_enabled"))
    subprocess_enabled = bool(record.get("subprocess_enabled"))
    bundle_execution_performed = bool(record.get("bundle_execution_performed"))
    bundle_subprocess_invoked = bool(record.get("bundle_subprocess_invoked"))
    repair_execution_performed = bool(record.get("repair_execution_performed"))
    repair_subprocess_invoked = bool(record.get("repair_subprocess_invoked"))
    execution_performed = bool(record.get("execution_performed"))
    subprocess_invoked = bool(record.get("subprocess_invoked"))

    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    if not result_id:
        reasons.append("missing_guarded_repair_execution_result_id")
    if not gate_id:
        reasons.append("missing_real_execution_repair_readiness_gate_id")
    if not feedback_id:
        reasons.append("missing_real_execution_repair_noop_feedback_id")
    if not noop_result_id:
        reasons.append("missing_real_execution_repair_noop_result_id")
    if not envelope_id:
        reasons.append("missing_real_execution_repair_dry_run_envelope_id")
    if not final_gate_id:
        reasons.append("missing_real_execution_repair_final_gate_id")
    if not rendered_command_id:
        reasons.append("missing_rendered_command_id")

    if status not in {"succeeded", "failed", "rejected"}:
        reasons.append("invalid_guarded_repair_execution_status")
    if not guarded_repair_execution:
        reasons.append("guarded_repair_execution_result_requires_guarded_marker")

    if source_gate_status != "ready_blocked":
        reasons.append("guarded_repair_execution_source_gate_must_be_ready_blocked")
    if not source_repair_readiness_satisfied:
        reasons.append("guarded_repair_execution_source_readiness_must_be_satisfied")
    if not source_ready_guarded:
        reasons.append("guarded_repair_execution_source_guarded_ready_required")
    if source_ready_repair:
        reasons.append("guarded_repair_execution_source_must_not_be_ready_for_repair")
    if source_would_execute:
        reasons.append("guarded_repair_execution_source_must_not_would_execute")
    if source_feedback_status != "actionable":
        reasons.append("guarded_repair_execution_source_feedback_must_be_actionable")
    if not source_repair_noop_verified:
        reasons.append("guarded_repair_execution_source_noop_must_be_verified")
    if not source_repair_path_can_proceed:
        reasons.append("guarded_repair_execution_source_path_must_proceed")
    if not source_repair_path_next_gate_allowed:
        reasons.append("guarded_repair_execution_source_next_gate_must_be_allowed")
    if source_noop_status != "completed":
        reasons.append("guarded_repair_execution_source_noop_must_be_completed")
    if source_noop_exit_code != 0:
        reasons.append("guarded_repair_execution_source_noop_exit_code_must_be_zero")
    if not source_execution_performed:
        reasons.append("guarded_repair_execution_source_noop_execution_required")
    if not source_subprocess_invoked:
        reasons.append("guarded_repair_execution_source_noop_subprocess_required")
    if not operator_authorized:
        reasons.append("guarded_repair_execution_requires_operator_authorized")

    if not isinstance(target_count, int) or target_count <= 0:
        reasons.append("guarded_repair_execution_targets_required")

    if rendered_command_executed or bool(payload_mapping.get("rendered_command_executed")):
        reasons.append("guarded_repair_execution_must_not_execute_rendered_command")
    if dry_run_command_executed or bool(payload_mapping.get("dry_run_command_executed")):
        reasons.append("guarded_repair_execution_must_not_execute_dry_run_command")
    if real_execution_enabled or bool(payload_mapping.get("real_execution_enabled")):
        reasons.append("guarded_repair_execution_must_not_enable_real_execution")

    if status == "rejected":
        if repair_execution_allowed:
            reasons.append("rejected_guarded_repair_execution_must_not_be_allowed")
        if execution_performed or subprocess_invoked:
            reasons.append("rejected_guarded_repair_execution_must_not_execute")
        if repair_actions_executed or repair_execution_performed:
            reasons.append("rejected_guarded_repair_execution_must_not_repair")
        if next_action != "authorize_guarded_repair_execution":
            reasons.append("invalid_rejected_guarded_repair_execution_next_action")

    if status == "succeeded":
        if not repair_execution_allowed:
            reasons.append("succeeded_guarded_repair_execution_requires_allowed")
        if reason != "guarded_repair_execution_succeeded":
            reasons.append("invalid_succeeded_guarded_repair_execution_reason")
        if next_action != "run_post_repair_evidence_check":
            reasons.append("invalid_succeeded_guarded_repair_execution_next_action")
        if exit_code != 0:
            reasons.append("succeeded_guarded_repair_execution_exit_code_must_be_zero")
        if not marker_observed:
            reasons.append("succeeded_guarded_repair_execution_marker_required")
        if not bundle_execution_enabled:
            reasons.append("succeeded_guarded_repair_execution_requires_bundle_enabled")
        if not repair_execution_enabled:
            reasons.append("succeeded_guarded_repair_execution_requires_repair_enabled")
        if not subprocess_enabled:
            reasons.append("succeeded_guarded_repair_execution_requires_subprocess_enabled")
        if not bundle_execution_performed:
            reasons.append("succeeded_guarded_repair_execution_requires_bundle_performed")
        if not bundle_subprocess_invoked:
            reasons.append("succeeded_guarded_repair_execution_requires_bundle_subprocess")
        if not repair_actions_executed:
            reasons.append("succeeded_guarded_repair_execution_requires_repair_actions")
        if not repair_bundle_executed:
            reasons.append("succeeded_guarded_repair_execution_requires_repair_bundle")
        if not repair_command_executed:
            reasons.append("succeeded_guarded_repair_execution_requires_repair_command")
        if not repair_execution_performed:
            reasons.append("succeeded_guarded_repair_execution_requires_repair_performed")
        if not repair_subprocess_invoked:
            reasons.append("succeeded_guarded_repair_execution_requires_repair_subprocess")
        if not execution_performed:
            reasons.append("succeeded_guarded_repair_execution_requires_execution")
        if not subprocess_invoked:
            reasons.append("succeeded_guarded_repair_execution_requires_subprocess")

    if status == "failed":
        if not repair_execution_allowed:
            reasons.append("failed_guarded_repair_execution_requires_allowed")
        if reason != "guarded_repair_execution_failed":
            reasons.append("invalid_failed_guarded_repair_execution_reason")
        if next_action != "investigate_guarded_repair_execution_failure":
            reasons.append("invalid_failed_guarded_repair_execution_next_action")
        if repair_actions_executed:
            reasons.append("failed_guarded_repair_execution_must_not_mark_actions_executed")
        if repair_execution_performed:
            reasons.append("failed_guarded_repair_execution_must_not_mark_repair_performed")

    return {
        "type": "security_validation_result",
        "record_type": "replay_lifecycle_retry_guarded_repair_execution_result",
        "valid": not reasons,
        "severity": "critical" if reasons else "info",
        "reasons": reasons,
        "subject": result_id or gate_id,
        "repair_execution_status": status or "unknown",
        "repair_execution_allowed": repair_execution_allowed,
        "guarded_repair_execution": guarded_repair_execution,
        "guarded_repair_marker_observed": marker_observed,
        "exit_code": exit_code,
        "repair_action_target_count": target_count,
        "source_gate_status": source_gate_status or "unknown",
        "source_ready_for_guarded_repair_execution": source_ready_guarded,
        "source_ready_for_repair_execution": source_ready_repair,
        "source_would_execute": source_would_execute,
        "source_feedback_status": source_feedback_status or "unknown",
        "source_noop_status": source_noop_status or "unknown",
        "source_noop_exit_code": source_noop_exit_code,
        "source_execution_performed": source_execution_performed,
        "source_subprocess_invoked": source_subprocess_invoked,
        "source_repair_readiness_satisfied": source_repair_readiness_satisfied,
        "source_repair_noop_verified": source_repair_noop_verified,
        "source_repair_path_can_proceed": source_repair_path_can_proceed,
        "source_repair_path_next_gate_allowed": source_repair_path_next_gate_allowed,
        "operator_authorized": operator_authorized,
        "repair_actions_executed": repair_actions_executed,
        "repair_bundle_executed": repair_bundle_executed,
        "repair_command_executed": repair_command_executed,
        "rendered_command_executed": rendered_command_executed,
        "dry_run_command_executed": dry_run_command_executed,
        "bundle_execution_enabled": bundle_execution_enabled,
        "repair_execution_enabled": repair_execution_enabled,
        "real_execution_enabled": real_execution_enabled,
        "subprocess_enabled": subprocess_enabled,
        "bundle_execution_performed": bundle_execution_performed,
        "bundle_subprocess_invoked": bundle_subprocess_invoked,
        "repair_execution_performed": repair_execution_performed,
        "repair_subprocess_invoked": repair_subprocess_invoked,
        "execution_performed": execution_performed,
        "subprocess_invoked": subprocess_invoked,
        "recommended_next_action": next_action or "unknown",
        "reason": reason or "unknown",
    }


def validate_replay_lifecycle_retry_post_repair_evidence_check(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate post-repair evidence check records."""
    reasons: list[str] = []

    check_id = str(record.get("post_repair_evidence_check_id") or "").strip()
    guarded_result_id = str(
        record.get("guarded_repair_execution_result_id") or ""
    ).strip()
    readiness_gate_id = str(
        record.get("real_execution_repair_readiness_gate_id") or ""
    ).strip()
    feedback_id = str(
        record.get("real_execution_repair_noop_feedback_id") or ""
    ).strip()
    noop_result_id = str(
        record.get("real_execution_repair_noop_result_id") or ""
    ).strip()
    envelope_id = str(
        record.get("real_execution_repair_dry_run_envelope_id") or ""
    ).strip()
    rendered_command_id = str(record.get("rendered_command_id") or "").strip()

    status = str(record.get("post_repair_status") or "").strip()
    reason = str(record.get("reason") or "").strip()
    next_action = str(record.get("recommended_next_action") or "").strip()

    allowed = bool(record.get("post_repair_evidence_check_allowed"))
    enabled = bool(record.get("post_repair_evidence_check_enabled"))
    marker_observed = bool(record.get("post_repair_evidence_marker_observed"))
    exit_code = record.get("post_repair_evidence_exit_code")
    repair_outcome_verified = bool(record.get("repair_outcome_verified"))

    expected_count = record.get("repair_targets_expected_count")
    verified_count = record.get("repair_targets_verified_count")
    missing_targets = record.get("repair_targets_missing")
    unexpected_targets = record.get("repair_targets_unexpected")

    source_status = str(
        record.get("source_guarded_repair_execution_status") or ""
    ).strip()
    source_allowed = bool(record.get("source_guarded_repair_execution_allowed"))
    source_marker = bool(record.get("source_guarded_repair_marker_observed"))
    source_exit_code = record.get("source_guarded_repair_exit_code")
    source_next_action = str(
        record.get("source_guarded_repair_next_action") or ""
    ).strip()

    source_repair_actions_executed = bool(
        record.get("source_repair_actions_executed")
    )
    source_repair_bundle_executed = bool(
        record.get("source_repair_bundle_executed")
    )
    source_repair_command_executed = bool(
        record.get("source_repair_command_executed")
    )
    source_rendered_command_executed = bool(
        record.get("source_rendered_command_executed")
    )
    source_dry_run_command_executed = bool(
        record.get("source_dry_run_command_executed")
    )
    source_repair_execution_enabled = bool(
        record.get("source_repair_execution_enabled")
    )
    source_real_execution_enabled = bool(record.get("source_real_execution_enabled"))
    source_repair_execution_performed = bool(
        record.get("source_repair_execution_performed")
    )
    source_repair_subprocess_invoked = bool(
        record.get("source_repair_subprocess_invoked")
    )
    operator_authorized = bool(record.get("operator_authorized"))

    evidence_execution_performed = bool(
        record.get("evidence_check_execution_performed")
    )
    evidence_subprocess_invoked = bool(
        record.get("evidence_check_subprocess_invoked")
    )

    repair_execution_enabled = bool(record.get("repair_execution_enabled"))
    real_execution_enabled = bool(record.get("real_execution_enabled"))
    subprocess_enabled = bool(record.get("subprocess_enabled"))
    repair_execution_performed = bool(record.get("repair_execution_performed"))
    repair_subprocess_invoked = bool(record.get("repair_subprocess_invoked"))
    execution_performed = bool(record.get("execution_performed"))
    subprocess_invoked = bool(record.get("subprocess_invoked"))

    payload = record.get("payload")
    payload_mapping = payload if isinstance(payload, Mapping) else {}

    if not check_id:
        reasons.append("missing_post_repair_evidence_check_id")
    if not guarded_result_id:
        reasons.append("missing_guarded_repair_execution_result_id")
    if not readiness_gate_id:
        reasons.append("missing_real_execution_repair_readiness_gate_id")
    if not feedback_id:
        reasons.append("missing_real_execution_repair_noop_feedback_id")
    if not noop_result_id:
        reasons.append("missing_real_execution_repair_noop_result_id")
    if not envelope_id:
        reasons.append("missing_real_execution_repair_dry_run_envelope_id")
    if not rendered_command_id:
        reasons.append("missing_rendered_command_id")

    if status not in {"passed", "failed", "rejected"}:
        reasons.append("invalid_post_repair_evidence_status")

    if source_status != "succeeded":
        reasons.append("post_repair_evidence_source_repair_must_be_succeeded")
    if not source_allowed:
        reasons.append("post_repair_evidence_source_repair_must_be_allowed")
    if not source_marker:
        reasons.append("post_repair_evidence_source_marker_required")
    if source_exit_code != 0:
        reasons.append("post_repair_evidence_source_exit_code_must_be_zero")
    if source_next_action != "run_post_repair_evidence_check":
        reasons.append("post_repair_evidence_source_next_action_invalid")

    if not source_repair_actions_executed:
        reasons.append("post_repair_evidence_source_repair_actions_required")
    if not source_repair_bundle_executed:
        reasons.append("post_repair_evidence_source_repair_bundle_required")
    if not source_repair_command_executed:
        reasons.append("post_repair_evidence_source_repair_command_required")
    if source_rendered_command_executed:
        reasons.append("post_repair_evidence_source_must_not_execute_rendered")
    if source_dry_run_command_executed:
        reasons.append("post_repair_evidence_source_must_not_execute_dry_run")
    if not source_repair_execution_enabled:
        reasons.append("post_repair_evidence_source_repair_enabled_required")
    if source_real_execution_enabled:
        reasons.append("post_repair_evidence_source_must_not_enable_real_execution")
    if not source_repair_execution_performed:
        reasons.append("post_repair_evidence_source_repair_performed_required")
    if not source_repair_subprocess_invoked:
        reasons.append("post_repair_evidence_source_repair_subprocess_required")
    if not operator_authorized:
        reasons.append("post_repair_evidence_requires_operator_authorized")

    if not isinstance(expected_count, int) or expected_count <= 0:
        reasons.append("post_repair_evidence_expected_targets_required")
    if not isinstance(verified_count, int) or verified_count <= 0:
        reasons.append("post_repair_evidence_verified_targets_required")
    if expected_count != verified_count:
        reasons.append("post_repair_evidence_target_count_mismatch")
    if missing_targets != []:
        reasons.append("post_repair_evidence_missing_targets_must_be_empty")
    if unexpected_targets != []:
        reasons.append("post_repair_evidence_unexpected_targets_must_be_empty")

    if repair_execution_enabled or bool(payload_mapping.get("repair_execution_enabled")):
        reasons.append("post_repair_evidence_must_not_enable_repair_execution")
    if real_execution_enabled or bool(payload_mapping.get("real_execution_enabled")):
        reasons.append("post_repair_evidence_must_not_enable_real_execution")
    if repair_execution_performed or bool(
        payload_mapping.get("repair_execution_performed")
    ):
        reasons.append("post_repair_evidence_must_not_perform_repair_execution")
    if repair_subprocess_invoked or bool(payload_mapping.get("repair_subprocess_invoked")):
        reasons.append("post_repair_evidence_must_not_invoke_repair_subprocess")

    if status == "rejected":
        if allowed:
            reasons.append("rejected_post_repair_evidence_must_not_be_allowed")
        if enabled:
            reasons.append("rejected_post_repair_evidence_must_not_be_enabled")
        if evidence_execution_performed or execution_performed:
            reasons.append("rejected_post_repair_evidence_must_not_execute")
        if evidence_subprocess_invoked or subprocess_invoked:
            reasons.append("rejected_post_repair_evidence_must_not_invoke_subprocess")
        if repair_outcome_verified:
            reasons.append("rejected_post_repair_evidence_must_not_verify")
        if next_action != "authorize_post_repair_evidence_check":
            reasons.append("invalid_rejected_post_repair_evidence_next_action")

    if status == "passed":
        if not allowed:
            reasons.append("passed_post_repair_evidence_requires_allowed")
        if not enabled:
            reasons.append("passed_post_repair_evidence_requires_enabled")
        if reason != "post_repair_evidence_check_passed":
            reasons.append("invalid_passed_post_repair_evidence_reason")
        if next_action != "close_repair_loop":
            reasons.append("invalid_passed_post_repair_evidence_next_action")
        if exit_code != 0:
            reasons.append("passed_post_repair_evidence_exit_code_must_be_zero")
        if not marker_observed:
            reasons.append("passed_post_repair_evidence_marker_required")
        if not repair_outcome_verified:
            reasons.append("passed_post_repair_evidence_requires_verified_outcome")
        if not evidence_execution_performed:
            reasons.append("passed_post_repair_evidence_requires_evidence_execution")
        if not evidence_subprocess_invoked:
            reasons.append("passed_post_repair_evidence_requires_evidence_subprocess")
        if not subprocess_enabled:
            reasons.append("passed_post_repair_evidence_requires_subprocess_enabled")
        if not execution_performed:
            reasons.append("passed_post_repair_evidence_requires_execution")
        if not subprocess_invoked:
            reasons.append("passed_post_repair_evidence_requires_subprocess")

    if status == "failed":
        if not allowed:
            reasons.append("failed_post_repair_evidence_requires_allowed")
        if not enabled:
            reasons.append("failed_post_repair_evidence_requires_enabled")
        if reason != "post_repair_evidence_check_failed":
            reasons.append("invalid_failed_post_repair_evidence_reason")
        if next_action != "investigate_post_repair_failure":
            reasons.append("invalid_failed_post_repair_evidence_next_action")
        if repair_outcome_verified:
            reasons.append("failed_post_repair_evidence_must_not_verify_outcome")

    return {
        "type": "security_validation_result",
        "record_type": "replay_lifecycle_retry_post_repair_evidence_check",
        "valid": not reasons,
        "severity": "critical" if reasons else "info",
        "reasons": reasons,
        "subject": check_id or guarded_result_id,
        "post_repair_status": status or "unknown",
        "post_repair_evidence_check_allowed": allowed,
        "post_repair_evidence_check_enabled": enabled,
        "post_repair_evidence_marker_observed": marker_observed,
        "post_repair_evidence_exit_code": exit_code,
        "repair_outcome_verified": repair_outcome_verified,
        "repair_targets_expected_count": expected_count,
        "repair_targets_verified_count": verified_count,
        "repair_targets_missing": missing_targets,
        "repair_targets_unexpected": unexpected_targets,
        "source_guarded_repair_execution_status": source_status or "unknown",
        "source_guarded_repair_execution_allowed": source_allowed,
        "source_guarded_repair_marker_observed": source_marker,
        "source_guarded_repair_exit_code": source_exit_code,
        "source_guarded_repair_next_action": source_next_action or "unknown",
        "source_repair_actions_executed": source_repair_actions_executed,
        "source_repair_bundle_executed": source_repair_bundle_executed,
        "source_repair_command_executed": source_repair_command_executed,
        "source_rendered_command_executed": source_rendered_command_executed,
        "source_dry_run_command_executed": source_dry_run_command_executed,
        "source_repair_execution_enabled": source_repair_execution_enabled,
        "source_real_execution_enabled": source_real_execution_enabled,
        "source_repair_execution_performed": source_repair_execution_performed,
        "source_repair_subprocess_invoked": source_repair_subprocess_invoked,
        "operator_authorized": operator_authorized,
        "evidence_check_execution_performed": evidence_execution_performed,
        "evidence_check_subprocess_invoked": evidence_subprocess_invoked,
        "repair_execution_enabled": repair_execution_enabled,
        "real_execution_enabled": real_execution_enabled,
        "subprocess_enabled": subprocess_enabled,
        "repair_execution_performed": repair_execution_performed,
        "repair_subprocess_invoked": repair_subprocess_invoked,
        "execution_performed": execution_performed,
        "subprocess_invoked": subprocess_invoked,
        "recommended_next_action": next_action or "unknown",
        "reason": reason or "unknown",
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
    "validate_replay_lifecycle_retry_mock_execution_summary",
    "validate_replay_lifecycle_retry_real_execution_preflight",
    "validate_replay_lifecycle_retry_real_execution_approval",
    "validate_replay_lifecycle_retry_real_execution_approval_transition",
    "validate_replay_lifecycle_retry_real_execution_final_gate",
    "validate_replay_lifecycle_retry_real_execution_dry_run_envelope",
    "validate_replay_lifecycle_retry_real_execution_noop_result",
    "validate_replay_lifecycle_retry_real_execution_read_only_promotion",
    "validate_replay_lifecycle_retry_real_execution_read_only_final_gate",
    "validate_replay_lifecycle_retry_real_execution_read_only_approval",
    "validate_replay_lifecycle_retry_real_execution_read_only_approval_transition",
    "validate_replay_lifecycle_retry_real_execution_read_only_readiness_gate",
    "validate_replay_lifecycle_retry_real_execution_read_only_execution_result",
    "validate_replay_lifecycle_retry_real_execution_read_only_feedback",
    "validate_replay_lifecycle_retry_real_execution_read_only_repair_plan",
    "validate_replay_lifecycle_retry_real_execution_read_only_repair_action_bundle",
    "validate_replay_lifecycle_retry_real_execution_read_only_repair_action_bundle_review",
    "validate_replay_lifecycle_retry_real_execution_repair_approval",
    "validate_replay_lifecycle_retry_real_execution_repair_approval_transition",
    "validate_replay_lifecycle_retry_real_execution_repair_final_gate",
    "validate_replay_lifecycle_retry_real_execution_repair_dry_run_envelope",
    "validate_replay_lifecycle_retry_real_execution_repair_noop_result",
    "validate_replay_lifecycle_retry_real_execution_repair_noop_feedback",
    "validate_replay_lifecycle_retry_real_execution_repair_readiness_gate",
    "validate_replay_lifecycle_retry_guarded_repair_execution_result",
    "validate_replay_lifecycle_retry_post_repair_evidence_check",
]