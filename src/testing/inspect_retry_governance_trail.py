"""Inspect replay retry governance trail records from CRDT.

This helper is read-only. It does not publish records and does not execute retry
commands.
"""

from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from typing import Any, Iterable, Mapping

from src.core.crdt_adapter import CRDTAdapter
from swarm_config import config

logger = logging.getLogger(__name__)

TRAIL_RECORD_TYPES = {
    "replay_lifecycle_retry_proposal",
    "replay_lifecycle_retry_approval",
    "replay_lifecycle_retry_execution_plan",
    "replay_lifecycle_retry_execution_result",
    "replay_lifecycle_retry_rendered_command",
    "replay_lifecycle_retry_execution_eligibility",
    "replay_lifecycle_retry_rendered_command_result",
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
    "replay_lifecycle_retry_real_execution_adapter_contract",
    "replay_lifecycle_retry_real_execution_adapter_request_schema",
    "replay_lifecycle_retry_real_execution_capability_policy_matrix",
    "replay_lifecycle_retry_real_execution_sandbox_adapter_scaffold",
    "replay_lifecycle_retry_real_execution_sandbox_adapter_request_preflight",
    "replay_lifecycle_retry_real_execution_sandbox_request_envelope_scaffold",
    "replay_lifecycle_retry_real_execution_sandbox_materialization_preflight_scaffold",
    "replay_lifecycle_retry_real_execution_sandbox_workspace_plan_scaffold",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect replay retry governance trail records.",
    )
    parser.add_argument(
        "--db-path",
        default=config.crdt_db_path,
        help="Path to CRDT sqlite database.",
    )
    parser.add_argument(
        "--proposal-id",
        default="",
        help="Optional proposal_id filter.",
    )
    parser.add_argument(
        "--approval-id",
        default="",
        help="Optional approval_id filter.",
    )
    parser.add_argument(
        "--plan-id",
        default="",
        help="Optional plan_id filter.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON summary.",
    )
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Exit with code 1 when the retry governance chain is incomplete.",
    )
    return parser


def inspect_retry_governance_trail_from_records(
    records: Iterable[Any],
    *,
    proposal_id: str = "",
    approval_id: str = "",
    plan_id: str = "",
) -> dict[str, Any]:
    """Build a read-only summary of retry governance trail records."""
    clean_proposal_id = str(proposal_id or "").strip()
    clean_approval_id = str(approval_id or "").strip()
    clean_plan_id = str(plan_id or "").strip()

    trail_records = [
        dict(item)
        for item in records or []
        if isinstance(item, Mapping)
        and item.get("type") in TRAIL_RECORD_TYPES
        and _matches_filters(
            item,
            proposal_id=clean_proposal_id,
            approval_id=clean_approval_id,
            plan_id=clean_plan_id,
        )
    ]

    by_type = Counter(str(item.get("type") or "unknown") for item in trail_records)

    proposals = [
        item for item in trail_records
        if item.get("type") == "replay_lifecycle_retry_proposal"
    ]
    approvals = [
        item for item in trail_records
        if item.get("type") == "replay_lifecycle_retry_approval"
    ]
    plans = [
        item for item in trail_records
        if item.get("type") == "replay_lifecycle_retry_execution_plan"
    ]
    rendered_commands = [
        item for item in trail_records
        if item.get("type") == "replay_lifecycle_retry_rendered_command"
    ]
    rendered_command_results = [
        item for item in trail_records
        if item.get("type") == "replay_lifecycle_retry_rendered_command_result"
    ]
    eligibilities = [
        item
        for item in trail_records
        if item.get("type") == "replay_lifecycle_retry_execution_eligibility"
    ]
    controlled_execution_results = [
        item
        for item in trail_records
        if item.get("type") == "replay_lifecycle_retry_controlled_execution_result"
    ]
    results = [
        item for item in trail_records
        if item.get("type") == "replay_lifecycle_retry_execution_result"
    ]
    mock_execution_summaries = [
        item
        for item in trail_records
        if item.get("type") == "replay_lifecycle_retry_mock_execution_summary"
    ]
    real_preflights = [
        item
        for item in trail_records
        if item.get("type") == "replay_lifecycle_retry_real_execution_preflight"
    ]
    real_approvals = [
        item
        for item in trail_records
        if item.get("type") == "replay_lifecycle_retry_real_execution_approval"
    ]
    real_approval_transitions = [
        item
        for item in trail_records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_approval_transition"
    ]
    real_final_gates = [
        item
        for item in trail_records
        if item.get("type") == "replay_lifecycle_retry_real_execution_final_gate"
    ]
    real_dry_run_envelopes = [
        item
        for item in trail_records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_dry_run_envelope"
    ]
    real_noop_results = [
        item
        for item in trail_records
        if item.get("type") == "replay_lifecycle_retry_real_execution_noop_result"
    ]
    real_read_only_promotions = [
        item
        for item in trail_records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_read_only_promotion"
    ]
    real_read_only_final_gates = [
        item
        for item in trail_records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_read_only_final_gate"
    ]
    real_read_only_approvals = [
        item
        for item in trail_records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_read_only_approval"
    ]
    real_read_only_approval_transitions = [
        item
        for item in trail_records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_read_only_approval_transition"
    ]
    real_read_only_readiness_gates = [
        item
        for item in trail_records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_read_only_readiness_gate"
    ]
    real_read_only_execution_results = [
        item
        for item in trail_records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_read_only_execution_result"
    ]
    real_read_only_feedback_records = [
        item
        for item in trail_records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_read_only_feedback"
    ]
    real_read_only_repair_plans = [
        item
        for item in trail_records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_read_only_repair_plan"
    ]
    real_read_only_repair_action_bundles = [
        item
        for item in trail_records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_read_only_repair_action_bundle"
    ]
    real_read_only_repair_action_bundle_reviews = [
        item
        for item in trail_records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_read_only_repair_action_bundle_review"
    ]
    real_repair_approvals = [
        item
        for item in trail_records
        if item.get("type") == "replay_lifecycle_retry_real_execution_repair_approval"
    ]
    real_repair_approval_transitions = [
        item
        for item in trail_records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_repair_approval_transition"
    ]
    real_repair_final_gates = [
        item
        for item in trail_records
        if item.get("type") == "replay_lifecycle_retry_real_execution_repair_final_gate"
    ]
    real_repair_dry_run_envelopes = [
        item
        for item in trail_records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_repair_dry_run_envelope"
    ]
    real_repair_noop_results = [
        item
        for item in trail_records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_repair_noop_result"
    ]
    real_repair_noop_feedback_records = [
        item
        for item in trail_records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_repair_noop_feedback"
    ]
    real_repair_readiness_gates = [
        item
        for item in trail_records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_repair_readiness_gate"
    ]
    guarded_repair_execution_results = [
        item
        for item in trail_records
        if item.get("type")
        == "replay_lifecycle_retry_guarded_repair_execution_result"
    ]
    post_repair_evidence_checks = [
        item
        for item in trail_records
        if item.get("type") == "replay_lifecycle_retry_post_repair_evidence_check"
    ]
    real_execution_adapter_contracts = [
        item
        for item in trail_records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_adapter_contract"
    ]
    real_execution_adapter_request_schemas = [
        item
        for item in trail_records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_adapter_request_schema"
    ]
    real_execution_capability_policy_matrices = [
        item
        for item in trail_records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_capability_policy_matrix"
    ]
    real_execution_sandbox_adapter_scaffolds = [
        item
        for item in trail_records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_sandbox_adapter_scaffold"
    ]
    real_execution_sandbox_adapter_request_preflights = [
        item
        for item in trail_records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_sandbox_adapter_request_preflight"
    ]
    real_execution_sandbox_request_envelope_scaffolds = [
        item
        for item in trail_records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_sandbox_request_envelope_scaffold"
    ]
    real_execution_sandbox_materialization_preflight_scaffolds = [
        item
        for item in trail_records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_sandbox_materialization_preflight_scaffold"
    ]
    real_execution_sandbox_workspace_plan_scaffolds = [
        item
        for item in trail_records
        if item.get("type")
        == "replay_lifecycle_retry_real_execution_sandbox_workspace_plan_scaffold"
    ]

    approval_statuses = Counter(_clean_status(item.get("status")) for item in approvals)
    plan_statuses = Counter(_clean_status(item.get("status")) for item in plans)
    result_statuses = Counter(_clean_status(item.get("status")) for item in results)
    result_reasons = Counter(str(item.get("reason") or "unknown").strip() or "unknown" for item in results)
    decision_modes = Counter(
        str(item.get("decision_mode") or "unknown").strip() or "unknown"
        for item in approvals + plans + rendered_commands
    )
    rendered_command_statuses = Counter(
        _clean_status(item.get("status")) for item in rendered_commands
    )
    rendered_command_profiles = Counter(
        str(item.get("timeout_profile") or "unknown").strip() or "unknown"
        for item in rendered_commands
    )
    rendered_command_result_statuses = Counter(
        _clean_status(item.get("status")) for item in rendered_command_results
    )
    rendered_command_result_reasons = Counter(
        str(item.get("reason") or "unknown").strip() or "unknown"
        for item in rendered_command_results
    )
    eligibility_statuses = Counter(
        _clean_status(item.get("status")) for item in eligibilities
    )
    eligibility_reasons = Counter(
        str(item.get("reason") or "unknown").strip() or "unknown"
        for item in eligibilities
    )
    controlled_execution_result_statuses = Counter(
        _clean_status(item.get("status")) for item in controlled_execution_results
    )
    controlled_execution_result_reasons = Counter(
        str(item.get("reason") or "unknown").strip() or "unknown"
        for item in controlled_execution_results
    )
    controlled_command_parse_valid = Counter(
        str(
            bool(
                _command_parse(item).get("valid")
            )
        ).lower()
        for item in controlled_execution_results
    )
    controlled_command_parse_allowlist_matched = Counter(
        str(
            bool(
                _command_parse(item).get("allowlist_matched")
            )
        ).lower()
        for item in controlled_execution_results
    )
    controlled_command_parse_execution_performed = Counter(
        str(
            bool(
                _command_parse(item).get("execution_performed")
            )
        ).lower()
        for item in controlled_execution_results
    )
    controlled_execution_operator_authorized = Counter(
        str(bool(item.get("operator_authorized"))).lower()
        for item in controlled_execution_results
    )
    controlled_gate_statuses = Counter(
        str(_gate_evaluation(item).get("gate_status") or "unknown").strip()
        or "unknown"
        for item in controlled_execution_results
    )
    controlled_gate_would_execute = Counter(
        str(bool(_gate_evaluation(item).get("would_execute"))).lower()
        for item in controlled_execution_results
    )
    controlled_gate_would_execute_if_enabled = Counter(
        str(bool(_gate_evaluation(item).get("would_execute_if_enabled"))).lower()
        for item in controlled_execution_results
    )
    controlled_gate_execution_performed = Counter(
        str(bool(_gate_evaluation(item).get("execution_performed"))).lower()
        for item in controlled_execution_results
    )
    controlled_gate_reasons: Counter[str] = Counter()
    for item in controlled_execution_results:
        gate_reasons = _gate_evaluation(item).get("reasons")
        if isinstance(gate_reasons, list):
            for reason_item in gate_reasons:
                clean_reason = str(reason_item or "").strip()
                if clean_reason:
                    controlled_gate_reasons[clean_reason] += 1

    controlled_mock_statuses = Counter(
        str(_mock_execution(item).get("status") or "none").strip() or "none"
        for item in controlled_execution_results
    )
    controlled_mock_reasons = Counter(
        str(_mock_execution(item).get("reason") or "none").strip() or "none"
        for item in controlled_execution_results
    )
    controlled_mock_performed = Counter(
        str(bool(_mock_execution_payload(item).get("performed"))).lower()
        for item in controlled_execution_results
    )
    controlled_mock_subprocess_invoked = Counter(
        str(bool(_mock_execution_payload(item).get("subprocess_invoked"))).lower()
        for item in controlled_execution_results
    )
    mock_summary_statuses = Counter(
        _clean_status(item.get("status")) for item in mock_execution_summaries
    )
    mock_summary_reasons = Counter(
        _clean_status(item.get("reason")) for item in mock_execution_summaries
    )
    mock_summary_performed = Counter(
        str(bool(item.get("mock_performed"))).lower()
        for item in mock_execution_summaries
    )
    mock_summary_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in mock_execution_summaries
    )
    controlled_mock_adapter = Counter(
        str(_mock_adapter_result(item).get("adapter") or "none").strip() or "none"
        for item in controlled_execution_results
    )
    controlled_mock_adapter_mode = Counter(
        str(_mock_adapter_result(item).get("mode") or "none").strip() or "none"
        for item in controlled_execution_results
    )
    controlled_mock_adapter_result_statuses = Counter(
        str(_mock_adapter_result(item).get("status") or "none").strip() or "none"
        for item in controlled_execution_results
    )
    controlled_mock_adapter_subprocess_invoked = Counter(
        str(bool(_mock_adapter_result(item).get("subprocess_invoked"))).lower()
        for item in controlled_execution_results
    )
    controlled_mock_adapter_real_execution_enabled = Counter(
        str(bool(_mock_adapter_result(item).get("real_execution_enabled"))).lower()
        for item in controlled_execution_results
    )
    controlled_mock_adapter_payload_executed = Counter(
        str(
            bool(
                (
                    _mock_adapter_result(item).get("payload")
                    if isinstance(_mock_adapter_result(item).get("payload"), Mapping)
                    else {}
                ).get("executed")
            )
        ).lower()
        for item in controlled_execution_results
    )
    controlled_real_execution_requested = Counter(
        str(bool(item.get("real_execution_requested"))).lower()
        for item in controlled_execution_results
    )
    controlled_real_execution_performed = Counter(
        str(bool(item.get("real_execution_performed"))).lower()
        for item in controlled_execution_results
    )
    controlled_real_execution_supported = Counter(
        str(bool(item.get("real_execution_supported"))).lower()
        for item in controlled_execution_results
    )
    controlled_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in controlled_execution_results
    )
    real_preflight_statuses = Counter(
        _clean_status(item.get("status")) for item in real_preflights
    )
    real_preflight_reasons = Counter(
        str(item.get("reason") or "unknown").strip() or "unknown"
        for item in real_preflights
    )
    real_preflight_requested = Counter(
        str(bool(item.get("real_execution_requested"))).lower()
        for item in real_preflights
    )
    real_preflight_would_execute = Counter(
        str(bool(item.get("would_execute"))).lower()
        for item in real_preflights
    )
    real_preflight_execution_performed = Counter(
        str(bool(item.get("execution_performed"))).lower()
        for item in real_preflights
    )
    real_preflight_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in real_preflights
    )
    real_preflight_requires_explicit_pr = Counter(
        str(bool(item.get("real_adapter_requires_explicit_pr"))).lower()
        for item in real_preflights
    )
    real_approval_statuses = Counter(
        str(item.get("approval_status") or "unknown").strip() or "unknown"
        for item in real_approvals
    )
    real_approval_enabled = Counter(
        str(bool(item.get("real_execution_enabled"))).lower()
        for item in real_approvals
    )
    real_approval_subprocess_enabled = Counter(
        str(bool(item.get("subprocess_enabled"))).lower()
        for item in real_approvals
    )
    real_approval_execution_performed = Counter(
        str(bool(item.get("execution_performed"))).lower()
        for item in real_approvals
    )
    real_approval_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in real_approvals
    )
    real_approval_transition_statuses = Counter(
        str(item.get("to_status") or "unknown").strip() or "unknown"
        for item in real_approval_transitions
    )
    real_approval_transition_enabled = Counter(
        str(bool(item.get("real_execution_enabled"))).lower()
        for item in real_approval_transitions
    )
    real_approval_transition_subprocess_enabled = Counter(
        str(bool(item.get("subprocess_enabled"))).lower()
        for item in real_approval_transitions
    )
    real_approval_transition_execution_performed = Counter(
        str(bool(item.get("execution_performed"))).lower()
        for item in real_approval_transitions
    )
    real_approval_transition_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in real_approval_transitions
    )
    real_final_gate_statuses = Counter(
        str(item.get("gate_status") or "unknown").strip() or "unknown"
        for item in real_final_gates
    )
    real_final_gate_would_execute = Counter(
        str(bool(item.get("would_execute"))).lower()
        for item in real_final_gates
    )
    real_final_gate_ready = Counter(
        str(bool(item.get("ready_for_real_execution"))).lower()
        for item in real_final_gates
    )
    real_final_gate_real_execution_enabled = Counter(
        str(bool(item.get("real_execution_enabled"))).lower()
        for item in real_final_gates
    )
    real_final_gate_subprocess_enabled = Counter(
        str(bool(item.get("subprocess_enabled"))).lower()
        for item in real_final_gates
    )
    real_final_gate_execution_performed = Counter(
        str(bool(item.get("execution_performed"))).lower()
        for item in real_final_gates
    )
    real_final_gate_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in real_final_gates
    )
    real_dry_run_envelope_dry_run_only = Counter(
        str(bool(item.get("dry_run_only"))).lower()
        for item in real_dry_run_envelopes
    )
    real_dry_run_envelope_would_execute = Counter(
        str(bool(item.get("would_execute"))).lower()
        for item in real_dry_run_envelopes
    )
    real_dry_run_envelope_ready = Counter(
        str(bool(item.get("ready_for_real_execution"))).lower()
        for item in real_dry_run_envelopes
    )
    real_dry_run_envelope_real_execution_enabled = Counter(
        str(bool(item.get("real_execution_enabled"))).lower()
        for item in real_dry_run_envelopes
    )
    real_dry_run_envelope_subprocess_enabled = Counter(
        str(bool(item.get("subprocess_enabled"))).lower()
        for item in real_dry_run_envelopes
    )
    real_dry_run_envelope_execution_performed = Counter(
        str(bool(item.get("execution_performed"))).lower()
        for item in real_dry_run_envelopes
    )
    real_dry_run_envelope_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in real_dry_run_envelopes
    )
    real_noop_result_noop_only = Counter(
        str(bool(item.get("noop_only"))).lower()
        for item in real_noop_results
    )
    real_noop_result_rendered_command_executed = Counter(
        str(bool(item.get("rendered_command_executed"))).lower()
        for item in real_noop_results
    )
    real_noop_result_dry_run_command_executed = Counter(
        str(bool(item.get("dry_run_envelope_command_executed"))).lower()
        for item in real_noop_results
    )
    real_noop_result_real_execution_enabled = Counter(
        str(bool(item.get("real_execution_enabled"))).lower()
        for item in real_noop_results
    )
    real_noop_result_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in real_noop_results
    )
    real_noop_result_execution_performed = Counter(
        str(bool(item.get("execution_performed"))).lower()
        for item in real_noop_results
    )
    real_noop_result_exit_codes = Counter(
        str(item.get("exit_code"))
        for item in real_noop_results
    )
    real_noop_result_stdout_marker_observed = Counter(
        str("controlled-noop-ok" in str(item.get("stdout") or "")).lower()
        for item in real_noop_results
    )
    real_read_only_promotion_statuses = Counter(
        str(item.get("promotion_status") or "unknown").strip() or "unknown"
        for item in real_read_only_promotions
    )
    real_read_only_promotion_candidates = Counter(
        str(bool(item.get("read_only_candidate"))).lower()
        for item in real_read_only_promotions
    )
    real_read_only_promotion_command_parse_valid = Counter(
        str(bool(item.get("command_parse_valid"))).lower()
        for item in real_read_only_promotions
    )
    real_read_only_promotion_stdout_marker_observed = Counter(
        str(bool(item.get("stdout_marker_observed"))).lower()
        for item in real_read_only_promotions
    )
    real_read_only_promotion_noop_exit_codes = Counter(
        str(item.get("noop_exit_code"))
        for item in real_read_only_promotions
    )
    real_read_only_promotion_rendered_command_executed = Counter(
        str(bool(item.get("rendered_command_executed"))).lower()
        for item in real_read_only_promotions
    )
    real_read_only_promotion_dry_run_command_executed = Counter(
        str(bool(item.get("dry_run_envelope_command_executed"))).lower()
        for item in real_read_only_promotions
    )
    real_read_only_promotion_real_execution_enabled = Counter(
        str(bool(item.get("real_execution_enabled"))).lower()
        for item in real_read_only_promotions
    )
    real_read_only_promotion_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in real_read_only_promotions
    )
    real_read_only_promotion_execution_performed = Counter(
        str(bool(item.get("execution_performed"))).lower()
        for item in real_read_only_promotions
    )
    real_read_only_final_gate_statuses = Counter(
        str(item.get("gate_status") or "unknown").strip() or "unknown"
        for item in real_read_only_final_gates
    )
    real_read_only_final_gate_preconditions_satisfied = Counter(
        str(bool(item.get("promotion_preconditions_satisfied"))).lower()
        for item in real_read_only_final_gates
    )
    real_read_only_final_gate_ready = Counter(
        str(bool(item.get("ready_for_read_only_execution"))).lower()
        for item in real_read_only_final_gates
    )
    real_read_only_final_gate_would_execute = Counter(
        str(bool(item.get("would_execute"))).lower()
        for item in real_read_only_final_gates
    )
    real_read_only_final_gate_read_only_execution_enabled = Counter(
        str(bool(item.get("read_only_execution_enabled"))).lower()
        for item in real_read_only_final_gates
    )
    real_read_only_final_gate_real_execution_enabled = Counter(
        str(bool(item.get("real_execution_enabled"))).lower()
        for item in real_read_only_final_gates
    )
    real_read_only_final_gate_subprocess_enabled = Counter(
        str(bool(item.get("subprocess_enabled"))).lower()
        for item in real_read_only_final_gates
    )
    real_read_only_final_gate_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in real_read_only_final_gates
    )
    real_read_only_final_gate_execution_performed = Counter(
        str(bool(item.get("execution_performed"))).lower()
        for item in real_read_only_final_gates
    )
    real_read_only_final_gate_rendered_command_executed = Counter(
        str(bool(item.get("rendered_command_executed"))).lower()
        for item in real_read_only_final_gates
    )
    real_read_only_final_gate_dry_run_command_executed = Counter(
        str(bool(item.get("dry_run_envelope_command_executed"))).lower()
        for item in real_read_only_final_gates
    )
    real_read_only_approval_statuses = Counter(
        str(item.get("approval_status") or "unknown").strip() or "unknown"
        for item in real_read_only_approvals
    )
    real_read_only_approval_read_only_execution_enabled = Counter(
        str(bool(item.get("read_only_execution_enabled"))).lower()
        for item in real_read_only_approvals
    )
    real_read_only_approval_real_execution_enabled = Counter(
        str(bool(item.get("real_execution_enabled"))).lower()
        for item in real_read_only_approvals
    )
    real_read_only_approval_subprocess_enabled = Counter(
        str(bool(item.get("subprocess_enabled"))).lower()
        for item in real_read_only_approvals
    )
    real_read_only_approval_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in real_read_only_approvals
    )
    real_read_only_approval_execution_performed = Counter(
        str(bool(item.get("execution_performed"))).lower()
        for item in real_read_only_approvals
    )
    real_read_only_approval_rendered_command_executed = Counter(
        str(bool(item.get("rendered_command_executed"))).lower()
        for item in real_read_only_approvals
    )
    real_read_only_approval_dry_run_command_executed = Counter(
        str(bool(item.get("dry_run_envelope_command_executed"))).lower()
        for item in real_read_only_approvals
    )
    real_read_only_approval_transition_from_statuses = Counter(
        str(item.get("from_status") or "unknown").strip() or "unknown"
        for item in real_read_only_approval_transitions
    )
    real_read_only_approval_transition_to_statuses = Counter(
        str(item.get("to_status") or "unknown").strip() or "unknown"
        for item in real_read_only_approval_transitions
    )
    real_read_only_approval_transition_read_only_execution_enabled = Counter(
        str(bool(item.get("read_only_execution_enabled"))).lower()
        for item in real_read_only_approval_transitions
    )
    real_read_only_approval_transition_real_execution_enabled = Counter(
        str(bool(item.get("real_execution_enabled"))).lower()
        for item in real_read_only_approval_transitions
    )
    real_read_only_approval_transition_subprocess_enabled = Counter(
        str(bool(item.get("subprocess_enabled"))).lower()
        for item in real_read_only_approval_transitions
    )
    real_read_only_approval_transition_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in real_read_only_approval_transitions
    )
    real_read_only_approval_transition_execution_performed = Counter(
        str(bool(item.get("execution_performed"))).lower()
        for item in real_read_only_approval_transitions
    )
    real_read_only_approval_transition_rendered_command_executed = Counter(
        str(bool(item.get("rendered_command_executed"))).lower()
        for item in real_read_only_approval_transitions
    )
    real_read_only_approval_transition_dry_run_command_executed = Counter(
        str(bool(item.get("dry_run_envelope_command_executed"))).lower()
        for item in real_read_only_approval_transitions
    )
    real_read_only_readiness_gate_statuses = Counter(
        str(item.get("gate_status") or "unknown").strip() or "unknown"
        for item in real_read_only_readiness_gates
    )
    real_read_only_readiness_gate_satisfied = Counter(
        str(bool(item.get("read_only_readiness_satisfied"))).lower()
        for item in real_read_only_readiness_gates
    )
    real_read_only_readiness_gate_ready = Counter(
        str(bool(item.get("ready_for_guarded_read_only_execution"))).lower()
        for item in real_read_only_readiness_gates
    )
    real_read_only_readiness_gate_read_only_execution_enabled = Counter(
        str(bool(item.get("read_only_execution_enabled"))).lower()
        for item in real_read_only_readiness_gates
    )
    real_read_only_readiness_gate_real_execution_enabled = Counter(
        str(bool(item.get("real_execution_enabled"))).lower()
        for item in real_read_only_readiness_gates
    )
    real_read_only_readiness_gate_subprocess_enabled = Counter(
        str(bool(item.get("subprocess_enabled"))).lower()
        for item in real_read_only_readiness_gates
    )
    real_read_only_readiness_gate_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in real_read_only_readiness_gates
    )
    real_read_only_readiness_gate_execution_performed = Counter(
        str(bool(item.get("execution_performed"))).lower()
        for item in real_read_only_readiness_gates
    )
    real_read_only_readiness_gate_rendered_command_executed = Counter(
        str(bool(item.get("rendered_command_executed"))).lower()
        for item in real_read_only_readiness_gates
    )
    real_read_only_readiness_gate_dry_run_command_executed = Counter(
        str(bool(item.get("dry_run_envelope_command_executed"))).lower()
        for item in real_read_only_readiness_gates
    )
    real_read_only_execution_result_statuses = Counter(
        str(item.get("status") or "unknown").strip() or "unknown"
        for item in real_read_only_execution_results
    )
    real_read_only_execution_result_reasons = Counter(
        str(item.get("reason") or "unknown").strip() or "unknown"
        for item in real_read_only_execution_results
    )
    real_read_only_execution_result_exit_codes = Counter(
        "none" if item.get("exit_code") is None else str(item.get("exit_code"))
        for item in real_read_only_execution_results
    )
    real_read_only_execution_result_validation_reasons_empty = Counter(
        str(
            isinstance(item.get("validation_reasons"), list)
            and not item.get("validation_reasons")
        ).lower()
        for item in real_read_only_execution_results
    )
    real_read_only_execution_result_operator_authorized = Counter(
        str(bool(item.get("operator_authorized"))).lower()
        for item in real_read_only_execution_results
    )
    real_read_only_execution_result_allow_guarded = Counter(
        str(bool(item.get("allow_guarded_read_only_execution"))).lower()
        for item in real_read_only_execution_results
    )
    real_read_only_execution_result_read_only_execution_enabled = Counter(
        str(bool(item.get("read_only_execution_enabled"))).lower()
        for item in real_read_only_execution_results
    )
    real_read_only_execution_result_real_execution_enabled = Counter(
        str(bool(item.get("real_execution_enabled"))).lower()
        for item in real_read_only_execution_results
    )
    real_read_only_execution_result_subprocess_enabled = Counter(
        str(bool(item.get("subprocess_enabled"))).lower()
        for item in real_read_only_execution_results
    )
    real_read_only_execution_result_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in real_read_only_execution_results
    )
    real_read_only_execution_result_execution_performed = Counter(
        str(bool(item.get("execution_performed"))).lower()
        for item in real_read_only_execution_results
    )
    real_read_only_execution_result_read_only_command_executed = Counter(
        str(bool(item.get("read_only_command_executed"))).lower()
        for item in real_read_only_execution_results
    )
    real_read_only_execution_result_rendered_command_executed = Counter(
        str(bool(item.get("rendered_command_executed"))).lower()
        for item in real_read_only_execution_results
    )
    real_read_only_execution_result_dry_run_command_executed = Counter(
        str(bool(item.get("dry_run_envelope_command_executed"))).lower()
        for item in real_read_only_execution_results
    )
    real_read_only_feedback_statuses = Counter(
        str(item.get("feedback_status") or "unknown").strip() or "unknown"
        for item in real_read_only_feedback_records
    )
    real_read_only_feedback_source_statuses = Counter(
        str(item.get("source_status") or "unknown").strip() or "unknown"
        for item in real_read_only_feedback_records
    )
    real_read_only_feedback_source_exit_codes = Counter(
        "none" if item.get("source_exit_code") is None else str(item.get("source_exit_code"))
        for item in real_read_only_feedback_records
    )
    real_read_only_feedback_next_actions = Counter(
        str(item.get("recommended_next_action") or "unknown").strip() or "unknown"
        for item in real_read_only_feedback_records
    )
    real_read_only_feedback_execution_observed = Counter(
        str(bool(item.get("read_only_execution_was_observed"))).lower()
        for item in real_read_only_feedback_records
    )
    real_read_only_feedback_failed = Counter(
        str(bool(item.get("read_only_execution_failed"))).lower()
        for item in real_read_only_feedback_records
    )
    real_read_only_feedback_succeeded = Counter(
        str(bool(item.get("read_only_execution_succeeded"))).lower()
        for item in real_read_only_feedback_records
    )
    real_read_only_feedback_rejected = Counter(
        str(bool(item.get("read_only_execution_rejected"))).lower()
        for item in real_read_only_feedback_records
    )
    real_read_only_feedback_real_execution_enabled = Counter(
        str(bool(item.get("real_execution_enabled"))).lower()
        for item in real_read_only_feedback_records
    )
    real_read_only_feedback_feedback_execution_performed = Counter(
        str(bool(item.get("feedback_execution_performed"))).lower()
        for item in real_read_only_feedback_records
    )
    real_read_only_feedback_feedback_subprocess_invoked = Counter(
        str(bool(item.get("feedback_subprocess_invoked"))).lower()
        for item in real_read_only_feedback_records
    )
    real_read_only_feedback_execution_performed = Counter(
        str(bool(item.get("execution_performed"))).lower()
        for item in real_read_only_feedback_records
    )
    real_read_only_feedback_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in real_read_only_feedback_records
    )
    real_read_only_repair_plan_statuses = Counter(
        str(item.get("repair_plan_status") or "unknown").strip() or "unknown"
        for item in real_read_only_repair_plans
    )
    real_read_only_repair_plan_source_feedback_statuses = Counter(
        str(item.get("source_feedback_status") or "unknown").strip() or "unknown"
        for item in real_read_only_repair_plans
    )
    real_read_only_repair_plan_source_statuses = Counter(
        str(item.get("source_status") or "unknown").strip() or "unknown"
        for item in real_read_only_repair_plans
    )
    real_read_only_repair_plan_source_exit_codes = Counter(
        "none" if item.get("source_exit_code") is None else str(item.get("source_exit_code"))
        for item in real_read_only_repair_plans
    )
    real_read_only_repair_plan_next_actions = Counter(
        str(item.get("recommended_next_action") or "unknown").strip() or "unknown"
        for item in real_read_only_repair_plans
    )
    real_read_only_repair_plan_item_counts = Counter(
        str(item.get("repair_item_count") if isinstance(item.get("repair_item_count"), int) else "unknown")
        for item in real_read_only_repair_plans
    )
    real_read_only_repair_plan_requires_operator_review = Counter(
        str(bool(item.get("requires_operator_review"))).lower()
        for item in real_read_only_repair_plans
    )
    real_read_only_repair_plan_repair_execution_enabled = Counter(
        str(bool(item.get("repair_execution_enabled"))).lower()
        for item in real_read_only_repair_plans
    )
    real_read_only_repair_plan_real_execution_enabled = Counter(
        str(bool(item.get("real_execution_enabled"))).lower()
        for item in real_read_only_repair_plans
    )
    real_read_only_repair_plan_subprocess_enabled = Counter(
        str(bool(item.get("subprocess_enabled"))).lower()
        for item in real_read_only_repair_plans
    )
    real_read_only_repair_plan_repair_execution_performed = Counter(
        str(bool(item.get("repair_execution_performed"))).lower()
        for item in real_read_only_repair_plans
    )
    real_read_only_repair_plan_repair_subprocess_invoked = Counter(
        str(bool(item.get("repair_subprocess_invoked"))).lower()
        for item in real_read_only_repair_plans
    )
    real_read_only_repair_plan_execution_performed = Counter(
        str(bool(item.get("execution_performed"))).lower()
        for item in real_read_only_repair_plans
    )
    real_read_only_repair_plan_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in real_read_only_repair_plans
    )
    real_read_only_repair_action_bundle_statuses = Counter(
        str(item.get("bundle_status") or "unknown").strip() or "unknown"
        for item in real_read_only_repair_action_bundles
    )
    real_read_only_repair_action_bundle_source_plan_statuses = Counter(
        str(item.get("source_repair_plan_status") or "unknown").strip() or "unknown"
        for item in real_read_only_repair_action_bundles
    )
    real_read_only_repair_action_bundle_source_feedback_statuses = Counter(
        str(item.get("source_feedback_status") or "unknown").strip() or "unknown"
        for item in real_read_only_repair_action_bundles
    )
    real_read_only_repair_action_bundle_source_statuses = Counter(
        str(item.get("source_status") or "unknown").strip() or "unknown"
        for item in real_read_only_repair_action_bundles
    )
    real_read_only_repair_action_bundle_source_exit_codes = Counter(
        "none" if item.get("source_exit_code") is None else str(item.get("source_exit_code"))
        for item in real_read_only_repair_action_bundles
    )
    real_read_only_repair_action_bundle_next_actions = Counter(
        str(item.get("recommended_next_action") or "unknown").strip() or "unknown"
        for item in real_read_only_repair_action_bundles
    )
    real_read_only_repair_action_bundle_item_counts = Counter(
        str(item.get("bundle_item_count") if isinstance(item.get("bundle_item_count"), int) else "unknown")
        for item in real_read_only_repair_action_bundles
    )
    real_read_only_repair_action_bundle_source_item_counts = Counter(
        str(item.get("source_repair_item_count") if isinstance(item.get("source_repair_item_count"), int) else "unknown")
        for item in real_read_only_repair_action_bundles
    )
    real_read_only_repair_action_bundle_requires_operator_review = Counter(
        str(bool(item.get("requires_operator_review"))).lower()
        for item in real_read_only_repair_action_bundles
    )
    real_read_only_repair_action_bundle_reviewed = Counter(
        str(bool(item.get("bundle_reviewed"))).lower()
        for item in real_read_only_repair_action_bundles
    )
    real_read_only_repair_action_bundle_bundle_execution_enabled = Counter(
        str(bool(item.get("bundle_execution_enabled"))).lower()
        for item in real_read_only_repair_action_bundles
    )
    real_read_only_repair_action_bundle_repair_execution_enabled = Counter(
        str(bool(item.get("repair_execution_enabled"))).lower()
        for item in real_read_only_repair_action_bundles
    )
    real_read_only_repair_action_bundle_real_execution_enabled = Counter(
        str(bool(item.get("real_execution_enabled"))).lower()
        for item in real_read_only_repair_action_bundles
    )
    real_read_only_repair_action_bundle_subprocess_enabled = Counter(
        str(bool(item.get("subprocess_enabled"))).lower()
        for item in real_read_only_repair_action_bundles
    )
    real_read_only_repair_action_bundle_bundle_execution_performed = Counter(
        str(bool(item.get("bundle_execution_performed"))).lower()
        for item in real_read_only_repair_action_bundles
    )
    real_read_only_repair_action_bundle_bundle_subprocess_invoked = Counter(
        str(bool(item.get("bundle_subprocess_invoked"))).lower()
        for item in real_read_only_repair_action_bundles
    )
    real_read_only_repair_action_bundle_repair_execution_performed = Counter(
        str(bool(item.get("repair_execution_performed"))).lower()
        for item in real_read_only_repair_action_bundles
    )
    real_read_only_repair_action_bundle_repair_subprocess_invoked = Counter(
        str(bool(item.get("repair_subprocess_invoked"))).lower()
        for item in real_read_only_repair_action_bundles
    )
    real_read_only_repair_action_bundle_execution_performed = Counter(
        str(bool(item.get("execution_performed"))).lower()
        for item in real_read_only_repair_action_bundles
    )
    real_read_only_repair_action_bundle_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in real_read_only_repair_action_bundles
    )
    real_read_only_repair_action_bundle_review_statuses = Counter(
        str(item.get("review_status") or "unknown").strip() or "unknown"
        for item in real_read_only_repair_action_bundle_reviews
    )
    real_read_only_repair_action_bundle_review_source_bundle_statuses = Counter(
        str(item.get("source_bundle_status") or "unknown").strip() or "unknown"
        for item in real_read_only_repair_action_bundle_reviews
    )
    real_read_only_repair_action_bundle_review_source_plan_statuses = Counter(
        str(item.get("source_repair_plan_status") or "unknown").strip() or "unknown"
        for item in real_read_only_repair_action_bundle_reviews
    )
    real_read_only_repair_action_bundle_review_source_feedback_statuses = Counter(
        str(item.get("source_feedback_status") or "unknown").strip() or "unknown"
        for item in real_read_only_repair_action_bundle_reviews
    )
    real_read_only_repair_action_bundle_review_source_statuses = Counter(
        str(item.get("source_status") or "unknown").strip() or "unknown"
        for item in real_read_only_repair_action_bundle_reviews
    )
    real_read_only_repair_action_bundle_review_source_exit_codes = Counter(
        "none" if item.get("source_exit_code") is None else str(item.get("source_exit_code"))
        for item in real_read_only_repair_action_bundle_reviews
    )
    real_read_only_repair_action_bundle_review_source_item_counts = Counter(
        str(item.get("source_bundle_item_count") if isinstance(item.get("source_bundle_item_count"), int) else "unknown")
        for item in real_read_only_repair_action_bundle_reviews
    )
    real_read_only_repair_action_bundle_review_next_actions = Counter(
        str(item.get("recommended_next_action") or "unknown").strip() or "unknown"
        for item in real_read_only_repair_action_bundle_reviews
    )
    real_read_only_repair_action_bundle_review_operator_authorized = Counter(
        str(bool(item.get("operator_authorized"))).lower()
        for item in real_read_only_repair_action_bundle_reviews
    )
    real_read_only_repair_action_bundle_review_requires_operator_review = Counter(
        str(bool(item.get("requires_operator_review"))).lower()
        for item in real_read_only_repair_action_bundle_reviews
    )
    real_read_only_repair_action_bundle_review_reviewed = Counter(
        str(bool(item.get("reviewed"))).lower()
        for item in real_read_only_repair_action_bundle_reviews
    )
    real_read_only_repair_action_bundle_review_approved = Counter(
        str(bool(item.get("review_approved"))).lower()
        for item in real_read_only_repair_action_bundle_reviews
    )
    real_read_only_repair_action_bundle_review_rejected = Counter(
        str(bool(item.get("review_rejected"))).lower()
        for item in real_read_only_repair_action_bundle_reviews
    )
    real_read_only_repair_action_bundle_review_bundle_execution_enabled = Counter(
        str(bool(item.get("bundle_execution_enabled"))).lower()
        for item in real_read_only_repair_action_bundle_reviews
    )
    real_read_only_repair_action_bundle_review_repair_execution_enabled = Counter(
        str(bool(item.get("repair_execution_enabled"))).lower()
        for item in real_read_only_repair_action_bundle_reviews
    )
    real_read_only_repair_action_bundle_review_real_execution_enabled = Counter(
        str(bool(item.get("real_execution_enabled"))).lower()
        for item in real_read_only_repair_action_bundle_reviews
    )
    real_read_only_repair_action_bundle_review_subprocess_enabled = Counter(
        str(bool(item.get("subprocess_enabled"))).lower()
        for item in real_read_only_repair_action_bundle_reviews
    )
    real_read_only_repair_action_bundle_review_bundle_execution_performed = Counter(
        str(bool(item.get("bundle_execution_performed"))).lower()
        for item in real_read_only_repair_action_bundle_reviews
    )
    real_read_only_repair_action_bundle_review_bundle_subprocess_invoked = Counter(
        str(bool(item.get("bundle_subprocess_invoked"))).lower()
        for item in real_read_only_repair_action_bundle_reviews
    )
    real_read_only_repair_action_bundle_review_repair_execution_performed = Counter(
        str(bool(item.get("repair_execution_performed"))).lower()
        for item in real_read_only_repair_action_bundle_reviews
    )
    real_read_only_repair_action_bundle_review_repair_subprocess_invoked = Counter(
        str(bool(item.get("repair_subprocess_invoked"))).lower()
        for item in real_read_only_repair_action_bundle_reviews
    )
    real_read_only_repair_action_bundle_review_execution_performed = Counter(
        str(bool(item.get("execution_performed"))).lower()
        for item in real_read_only_repair_action_bundle_reviews
    )
    real_read_only_repair_action_bundle_review_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in real_read_only_repair_action_bundle_reviews
    )
    real_repair_approval_statuses = Counter(
        str(item.get("approval_status") or "unknown").strip() or "unknown"
        for item in real_repair_approvals
    )
    real_repair_approval_source_review_statuses = Counter(
        str(item.get("source_review_status") or "unknown").strip() or "unknown"
        for item in real_repair_approvals
    )
    real_repair_approval_source_bundle_statuses = Counter(
        str(item.get("source_bundle_status") or "unknown").strip() or "unknown"
        for item in real_repair_approvals
    )
    real_repair_approval_next_actions = Counter(
        str(item.get("recommended_next_action") or "unknown").strip() or "unknown"
        for item in real_repair_approvals
    )
    real_repair_approval_operator_authorized = Counter(
        str(bool(item.get("operator_authorized"))).lower()
        for item in real_repair_approvals
    )
    real_repair_approval_required = Counter(
        str(bool(item.get("repair_execution_approval_required"))).lower()
        for item in real_repair_approvals
    )
    real_repair_approval_approved = Counter(
        str(bool(item.get("repair_execution_approved"))).lower()
        for item in real_repair_approvals
    )
    real_repair_approval_rejected = Counter(
        str(bool(item.get("repair_execution_rejected"))).lower()
        for item in real_repair_approvals
    )
    real_repair_approval_repair_execution_enabled = Counter(
        str(bool(item.get("repair_execution_enabled"))).lower()
        for item in real_repair_approvals
    )
    real_repair_approval_real_execution_enabled = Counter(
        str(bool(item.get("real_execution_enabled"))).lower()
        for item in real_repair_approvals
    )
    real_repair_approval_subprocess_enabled = Counter(
        str(bool(item.get("subprocess_enabled"))).lower()
        for item in real_repair_approvals
    )
    real_repair_approval_repair_execution_performed = Counter(
        str(bool(item.get("repair_execution_performed"))).lower()
        for item in real_repair_approvals
    )
    real_repair_approval_repair_subprocess_invoked = Counter(
        str(bool(item.get("repair_subprocess_invoked"))).lower()
        for item in real_repair_approvals
    )
    real_repair_approval_execution_performed = Counter(
        str(bool(item.get("execution_performed"))).lower()
        for item in real_repair_approvals
    )
    real_repair_approval_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in real_repair_approvals
    )
    real_repair_approval_transition_from_statuses = Counter(
        str(item.get("from_status") or "unknown").strip() or "unknown"
        for item in real_repair_approval_transitions
    )
    real_repair_approval_transition_to_statuses = Counter(
        str(item.get("to_status") or "unknown").strip() or "unknown"
        for item in real_repair_approval_transitions
    )
    real_repair_approval_transition_source_approval_statuses = Counter(
        str(item.get("source_approval_status") or "unknown").strip() or "unknown"
        for item in real_repair_approval_transitions
    )
    real_repair_approval_transition_source_review_statuses = Counter(
        str(item.get("source_review_status") or "unknown").strip() or "unknown"
        for item in real_repair_approval_transitions
    )
    real_repair_approval_transition_next_actions = Counter(
        str(item.get("recommended_next_action") or "unknown").strip() or "unknown"
        for item in real_repair_approval_transitions
    )
    real_repair_approval_transition_operator_authorized = Counter(
        str(bool(item.get("operator_authorized"))).lower()
        for item in real_repair_approval_transitions
    )
    real_repair_approval_transition_required = Counter(
        str(bool(item.get("repair_execution_approval_required"))).lower()
        for item in real_repair_approval_transitions
    )
    real_repair_approval_transition_approved = Counter(
        str(bool(item.get("repair_execution_transition_approved"))).lower()
        for item in real_repair_approval_transitions
    )
    real_repair_approval_transition_rejected = Counter(
        str(bool(item.get("repair_execution_transition_rejected"))).lower()
        for item in real_repair_approval_transitions
    )
    real_repair_approval_transition_repair_execution_enabled = Counter(
        str(bool(item.get("repair_execution_enabled"))).lower()
        for item in real_repair_approval_transitions
    )
    real_repair_approval_transition_real_execution_enabled = Counter(
        str(bool(item.get("real_execution_enabled"))).lower()
        for item in real_repair_approval_transitions
    )
    real_repair_approval_transition_subprocess_enabled = Counter(
        str(bool(item.get("subprocess_enabled"))).lower()
        for item in real_repair_approval_transitions
    )
    real_repair_approval_transition_repair_execution_performed = Counter(
        str(bool(item.get("repair_execution_performed"))).lower()
        for item in real_repair_approval_transitions
    )
    real_repair_approval_transition_repair_subprocess_invoked = Counter(
        str(bool(item.get("repair_subprocess_invoked"))).lower()
        for item in real_repair_approval_transitions
    )
    real_repair_approval_transition_execution_performed = Counter(
        str(bool(item.get("execution_performed"))).lower()
        for item in real_repair_approval_transitions
    )
    real_repair_approval_transition_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in real_repair_approval_transitions
    )
    real_repair_final_gate_statuses = Counter(
        str(item.get("gate_status") or "unknown").strip() or "unknown"
        for item in real_repair_final_gates
    )
    real_repair_final_gate_preconditions_satisfied = Counter(
        str(bool(item.get("repair_preconditions_satisfied"))).lower()
        for item in real_repair_final_gates
    )
    real_repair_final_gate_ready = Counter(
        str(bool(item.get("ready_for_repair_execution"))).lower()
        for item in real_repair_final_gates
    )
    real_repair_final_gate_would_execute = Counter(
        str(bool(item.get("would_execute"))).lower()
        for item in real_repair_final_gates
    )
    real_repair_final_gate_next_actions = Counter(
        str(item.get("recommended_next_action") or "unknown").strip() or "unknown"
        for item in real_repair_final_gates
    )
    real_repair_final_gate_operator_authorized = Counter(
        str(bool(item.get("operator_authorized"))).lower()
        for item in real_repair_final_gates
    )
    real_repair_final_gate_transition_approved = Counter(
        str(bool(item.get("repair_execution_transition_approved"))).lower()
        for item in real_repair_final_gates
    )
    real_repair_final_gate_repair_execution_enabled = Counter(
        str(bool(item.get("repair_execution_enabled"))).lower()
        for item in real_repair_final_gates
    )
    real_repair_final_gate_real_execution_enabled = Counter(
        str(bool(item.get("real_execution_enabled"))).lower()
        for item in real_repair_final_gates
    )
    real_repair_final_gate_subprocess_enabled = Counter(
        str(bool(item.get("subprocess_enabled"))).lower()
        for item in real_repair_final_gates
    )
    real_repair_final_gate_repair_execution_performed = Counter(
        str(bool(item.get("repair_execution_performed"))).lower()
        for item in real_repair_final_gates
    )
    real_repair_final_gate_repair_subprocess_invoked = Counter(
        str(bool(item.get("repair_subprocess_invoked"))).lower()
        for item in real_repair_final_gates
    )
    real_repair_final_gate_execution_performed = Counter(
        str(bool(item.get("execution_performed"))).lower()
        for item in real_repair_final_gates
    )
    real_repair_final_gate_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in real_repair_final_gates
    )
    real_repair_dry_run_envelope_statuses = Counter(
        str(item.get("repair_dry_run_status") or "unknown").strip() or "unknown"
        for item in real_repair_dry_run_envelopes
    )
    real_repair_dry_run_envelope_dry_run_only = Counter(
        str(bool(item.get("dry_run_only"))).lower()
        for item in real_repair_dry_run_envelopes
    )
    real_repair_dry_run_envelope_modes = Counter(
        str(item.get("repair_dry_run_mode") or "unknown").strip() or "unknown"
        for item in real_repair_dry_run_envelopes
    )
    real_repair_dry_run_envelope_target_counts = Counter(
        str(item.get("repair_dry_run_target_count") or 0)
        for item in real_repair_dry_run_envelopes
    )
    real_repair_dry_run_envelope_source_gate_statuses = Counter(
        str(item.get("source_gate_status") or "unknown").strip() or "unknown"
        for item in real_repair_dry_run_envelopes
    )
    real_repair_dry_run_envelope_next_actions = Counter(
        str(item.get("recommended_next_action") or "unknown").strip() or "unknown"
        for item in real_repair_dry_run_envelopes
    )
    real_repair_dry_run_envelope_operator_authorized = Counter(
        str(bool(item.get("operator_authorized"))).lower()
        for item in real_repair_dry_run_envelopes
    )
    real_repair_dry_run_envelope_ready = Counter(
        str(bool(item.get("ready_for_repair_execution"))).lower()
        for item in real_repair_dry_run_envelopes
    )
    real_repair_dry_run_envelope_would_execute = Counter(
        str(bool(item.get("would_execute"))).lower()
        for item in real_repair_dry_run_envelopes
    )
    real_repair_dry_run_envelope_repair_execution_enabled = Counter(
        str(bool(item.get("repair_execution_enabled"))).lower()
        for item in real_repair_dry_run_envelopes
    )
    real_repair_dry_run_envelope_real_execution_enabled = Counter(
        str(bool(item.get("real_execution_enabled"))).lower()
        for item in real_repair_dry_run_envelopes
    )
    real_repair_dry_run_envelope_subprocess_enabled = Counter(
        str(bool(item.get("subprocess_enabled"))).lower()
        for item in real_repair_dry_run_envelopes
    )
    real_repair_dry_run_envelope_repair_execution_performed = Counter(
        str(bool(item.get("repair_execution_performed"))).lower()
        for item in real_repair_dry_run_envelopes
    )
    real_repair_dry_run_envelope_repair_subprocess_invoked = Counter(
        str(bool(item.get("repair_subprocess_invoked"))).lower()
        for item in real_repair_dry_run_envelopes
    )
    real_repair_dry_run_envelope_execution_performed = Counter(
        str(bool(item.get("execution_performed"))).lower()
        for item in real_repair_dry_run_envelopes
    )
    real_repair_dry_run_envelope_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in real_repair_dry_run_envelopes
    )
    real_repair_noop_result_statuses = Counter(
        str(item.get("repair_noop_status") or "unknown").strip() or "unknown"
        for item in real_repair_noop_results
    )
    real_repair_noop_result_exit_codes = Counter(
        str(item.get("exit_code"))
        for item in real_repair_noop_results
    )
    real_repair_noop_result_noop_only = Counter(
        str(bool(item.get("noop_only"))).lower()
        for item in real_repair_noop_results
    )
    real_repair_noop_result_stdout_marker_observed = Counter(
        str(bool(item.get("noop_stdout_marker_observed"))).lower()
        for item in real_repair_noop_results
    )
    real_repair_noop_result_source_envelope_statuses = Counter(
        str(item.get("source_envelope_status") or "unknown").strip() or "unknown"
        for item in real_repair_noop_results
    )
    real_repair_noop_result_source_target_counts = Counter(
        str(item.get("source_repair_dry_run_target_count") or 0)
        for item in real_repair_noop_results
    )
    real_repair_noop_result_next_actions = Counter(
        str(item.get("recommended_next_action") or "unknown").strip() or "unknown"
        for item in real_repair_noop_results
    )
    real_repair_noop_result_operator_authorized = Counter(
        str(bool(item.get("operator_authorized"))).lower()
        for item in real_repair_noop_results
    )
    real_repair_noop_result_repair_actions_executed = Counter(
        str(bool(item.get("repair_actions_executed"))).lower()
        for item in real_repair_noop_results
    )
    real_repair_noop_result_repair_bundle_executed = Counter(
        str(bool(item.get("repair_bundle_executed"))).lower()
        for item in real_repair_noop_results
    )
    real_repair_noop_result_repair_command_executed = Counter(
        str(bool(item.get("repair_command_executed"))).lower()
        for item in real_repair_noop_results
    )
    real_repair_noop_result_rendered_command_executed = Counter(
        str(bool(item.get("rendered_command_executed"))).lower()
        for item in real_repair_noop_results
    )
    real_repair_noop_result_dry_run_command_executed = Counter(
        str(bool(item.get("dry_run_command_executed"))).lower()
        for item in real_repair_noop_results
    )
    real_repair_noop_result_repair_execution_enabled = Counter(
        str(bool(item.get("repair_execution_enabled"))).lower()
        for item in real_repair_noop_results
    )
    real_repair_noop_result_real_execution_enabled = Counter(
        str(bool(item.get("real_execution_enabled"))).lower()
        for item in real_repair_noop_results
    )
    real_repair_noop_result_subprocess_enabled = Counter(
        str(bool(item.get("subprocess_enabled"))).lower()
        for item in real_repair_noop_results
    )
    real_repair_noop_result_repair_execution_performed = Counter(
        str(bool(item.get("repair_execution_performed"))).lower()
        for item in real_repair_noop_results
    )
    real_repair_noop_result_repair_subprocess_invoked = Counter(
        str(bool(item.get("repair_subprocess_invoked"))).lower()
        for item in real_repair_noop_results
    )
    real_repair_noop_result_execution_performed = Counter(
        str(bool(item.get("execution_performed"))).lower()
        for item in real_repair_noop_results
    )
    real_repair_noop_result_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in real_repair_noop_results
    )
    real_repair_noop_feedback_statuses = Counter(
        str(item.get("feedback_status") or "unknown").strip() or "unknown"
        for item in real_repair_noop_feedback_records
    )
    real_repair_noop_feedback_verified = Counter(
        str(bool(item.get("repair_noop_verified"))).lower()
        for item in real_repair_noop_feedback_records
    )
    real_repair_noop_feedback_path_can_proceed = Counter(
        str(bool(item.get("repair_path_can_proceed"))).lower()
        for item in real_repair_noop_feedback_records
    )
    real_repair_noop_feedback_next_gate_allowed = Counter(
        str(bool(item.get("repair_path_next_gate_allowed"))).lower()
        for item in real_repair_noop_feedback_records
    )
    real_repair_noop_feedback_next_actions = Counter(
        str(item.get("recommended_next_action") or "unknown").strip() or "unknown"
        for item in real_repair_noop_feedback_records
    )
    real_repair_noop_feedback_source_noop_statuses = Counter(
        str(item.get("source_noop_status") or "unknown").strip() or "unknown"
        for item in real_repair_noop_feedback_records
    )
    real_repair_noop_feedback_source_exit_codes = Counter(
        str(item.get("source_noop_exit_code"))
        for item in real_repair_noop_feedback_records
    )
    real_repair_noop_feedback_source_target_counts = Counter(
        str(item.get("source_repair_dry_run_target_count") or 0)
        for item in real_repair_noop_feedback_records
    )
    real_repair_noop_feedback_source_execution_performed = Counter(
        str(bool(item.get("source_execution_performed"))).lower()
        for item in real_repair_noop_feedback_records
    )
    real_repair_noop_feedback_source_subprocess_invoked = Counter(
        str(bool(item.get("source_subprocess_invoked"))).lower()
        for item in real_repair_noop_feedback_records
    )
    real_repair_noop_feedback_source_repair_actions_executed = Counter(
        str(bool(item.get("source_repair_actions_executed"))).lower()
        for item in real_repair_noop_feedback_records
    )
    real_repair_noop_feedback_source_repair_execution_enabled = Counter(
        str(bool(item.get("source_repair_execution_enabled"))).lower()
        for item in real_repair_noop_feedback_records
    )
    real_repair_noop_feedback_source_repair_execution_performed = Counter(
        str(bool(item.get("source_repair_execution_performed"))).lower()
        for item in real_repair_noop_feedback_records
    )
    real_repair_noop_feedback_source_repair_subprocess_invoked = Counter(
        str(bool(item.get("source_repair_subprocess_invoked"))).lower()
        for item in real_repair_noop_feedback_records
    )
    real_repair_noop_feedback_feedback_execution_performed = Counter(
        str(bool(item.get("feedback_execution_performed"))).lower()
        for item in real_repair_noop_feedback_records
    )
    real_repair_noop_feedback_feedback_subprocess_invoked = Counter(
        str(bool(item.get("feedback_subprocess_invoked"))).lower()
        for item in real_repair_noop_feedback_records
    )
    real_repair_noop_feedback_repair_execution_enabled = Counter(
        str(bool(item.get("repair_execution_enabled"))).lower()
        for item in real_repair_noop_feedback_records
    )
    real_repair_noop_feedback_real_execution_enabled = Counter(
        str(bool(item.get("real_execution_enabled"))).lower()
        for item in real_repair_noop_feedback_records
    )
    real_repair_noop_feedback_subprocess_enabled = Counter(
        str(bool(item.get("subprocess_enabled"))).lower()
        for item in real_repair_noop_feedback_records
    )
    real_repair_noop_feedback_repair_execution_performed = Counter(
        str(bool(item.get("repair_execution_performed"))).lower()
        for item in real_repair_noop_feedback_records
    )
    real_repair_noop_feedback_repair_subprocess_invoked = Counter(
        str(bool(item.get("repair_subprocess_invoked"))).lower()
        for item in real_repair_noop_feedback_records
    )
    real_repair_noop_feedback_execution_performed = Counter(
        str(bool(item.get("execution_performed"))).lower()
        for item in real_repair_noop_feedback_records
    )
    real_repair_noop_feedback_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in real_repair_noop_feedback_records
    )
    real_repair_readiness_gate_statuses = Counter(
        str(item.get("gate_status") or "unknown").strip() or "unknown"
        for item in real_repair_readiness_gates
    )
    real_repair_readiness_gate_satisfied = Counter(
        str(bool(item.get("repair_readiness_satisfied"))).lower()
        for item in real_repair_readiness_gates
    )
    real_repair_readiness_gate_guarded_ready = Counter(
        str(bool(item.get("ready_for_guarded_repair_execution"))).lower()
        for item in real_repair_readiness_gates
    )
    real_repair_readiness_gate_ready_for_repair_execution = Counter(
        str(bool(item.get("ready_for_repair_execution"))).lower()
        for item in real_repair_readiness_gates
    )
    real_repair_readiness_gate_would_execute = Counter(
        str(bool(item.get("would_execute"))).lower()
        for item in real_repair_readiness_gates
    )
    real_repair_readiness_gate_next_actions = Counter(
        str(item.get("recommended_next_action") or "unknown").strip() or "unknown"
        for item in real_repair_readiness_gates
    )
    real_repair_readiness_gate_source_feedback_statuses = Counter(
        str(item.get("source_feedback_status") or "unknown").strip() or "unknown"
        for item in real_repair_readiness_gates
    )
    real_repair_readiness_gate_source_noop_statuses = Counter(
        str(item.get("source_noop_status") or "unknown").strip() or "unknown"
        for item in real_repair_readiness_gates
    )
    real_repair_readiness_gate_source_exit_codes = Counter(
        str(item.get("source_noop_exit_code"))
        for item in real_repair_readiness_gates
    )
    real_repair_readiness_gate_source_target_counts = Counter(
        str(item.get("source_repair_dry_run_target_count") or 0)
        for item in real_repair_readiness_gates
    )
    real_repair_readiness_gate_source_execution_performed = Counter(
        str(bool(item.get("source_execution_performed"))).lower()
        for item in real_repair_readiness_gates
    )
    real_repair_readiness_gate_source_subprocess_invoked = Counter(
        str(bool(item.get("source_subprocess_invoked"))).lower()
        for item in real_repair_readiness_gates
    )
    real_repair_readiness_gate_source_repair_actions_executed = Counter(
        str(bool(item.get("source_repair_actions_executed"))).lower()
        for item in real_repair_readiness_gates
    )
    real_repair_readiness_gate_source_repair_execution_enabled = Counter(
        str(bool(item.get("source_repair_execution_enabled"))).lower()
        for item in real_repair_readiness_gates
    )
    real_repair_readiness_gate_source_repair_execution_performed = Counter(
        str(bool(item.get("source_repair_execution_performed"))).lower()
        for item in real_repair_readiness_gates
    )
    real_repair_readiness_gate_source_repair_subprocess_invoked = Counter(
        str(bool(item.get("source_repair_subprocess_invoked"))).lower()
        for item in real_repair_readiness_gates
    )
    real_repair_readiness_gate_repair_execution_enabled = Counter(
        str(bool(item.get("repair_execution_enabled"))).lower()
        for item in real_repair_readiness_gates
    )
    real_repair_readiness_gate_real_execution_enabled = Counter(
        str(bool(item.get("real_execution_enabled"))).lower()
        for item in real_repair_readiness_gates
    )
    real_repair_readiness_gate_subprocess_enabled = Counter(
        str(bool(item.get("subprocess_enabled"))).lower()
        for item in real_repair_readiness_gates
    )
    real_repair_readiness_gate_repair_execution_performed = Counter(
        str(bool(item.get("repair_execution_performed"))).lower()
        for item in real_repair_readiness_gates
    )
    real_repair_readiness_gate_repair_subprocess_invoked = Counter(
        str(bool(item.get("repair_subprocess_invoked"))).lower()
        for item in real_repair_readiness_gates
    )
    real_repair_readiness_gate_execution_performed = Counter(
        str(bool(item.get("execution_performed"))).lower()
        for item in real_repair_readiness_gates
    )
    real_repair_readiness_gate_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in real_repair_readiness_gates
    )
    guarded_repair_execution_statuses = Counter(
        str(item.get("repair_execution_status") or "unknown").strip() or "unknown"
        for item in guarded_repair_execution_results
    )
    guarded_repair_execution_allowed = Counter(
        str(bool(item.get("repair_execution_allowed"))).lower()
        for item in guarded_repair_execution_results
    )
    guarded_repair_execution_marker_observed = Counter(
        str(bool(item.get("guarded_repair_marker_observed"))).lower()
        for item in guarded_repair_execution_results
    )
    guarded_repair_execution_exit_codes = Counter(
        str(item.get("exit_code")) for item in guarded_repair_execution_results
    )
    guarded_repair_execution_target_counts = Counter(
        str(item.get("repair_action_target_count") or 0)
        for item in guarded_repair_execution_results
    )
    guarded_repair_execution_next_actions = Counter(
        str(item.get("recommended_next_action") or "unknown").strip() or "unknown"
        for item in guarded_repair_execution_results
    )
    guarded_repair_execution_source_gate_statuses = Counter(
        str(item.get("source_gate_status") or "unknown").strip() or "unknown"
        for item in guarded_repair_execution_results
    )
    guarded_repair_execution_source_feedback_statuses = Counter(
        str(item.get("source_feedback_status") or "unknown").strip() or "unknown"
        for item in guarded_repair_execution_results
    )
    guarded_repair_execution_source_noop_statuses = Counter(
        str(item.get("source_noop_status") or "unknown").strip() or "unknown"
        for item in guarded_repair_execution_results
    )
    guarded_repair_execution_source_ready_guarded = Counter(
        str(bool(item.get("source_ready_for_guarded_repair_execution"))).lower()
        for item in guarded_repair_execution_results
    )
    guarded_repair_execution_source_ready_repair = Counter(
        str(bool(item.get("source_ready_for_repair_execution"))).lower()
        for item in guarded_repair_execution_results
    )
    guarded_repair_execution_source_would_execute = Counter(
        str(bool(item.get("source_would_execute"))).lower()
        for item in guarded_repair_execution_results
    )
    guarded_repair_execution_source_execution_performed = Counter(
        str(bool(item.get("source_execution_performed"))).lower()
        for item in guarded_repair_execution_results
    )
    guarded_repair_execution_source_subprocess_invoked = Counter(
        str(bool(item.get("source_subprocess_invoked"))).lower()
        for item in guarded_repair_execution_results
    )
    guarded_repair_execution_repair_actions_executed = Counter(
        str(bool(item.get("repair_actions_executed"))).lower()
        for item in guarded_repair_execution_results
    )
    guarded_repair_execution_repair_bundle_executed = Counter(
        str(bool(item.get("repair_bundle_executed"))).lower()
        for item in guarded_repair_execution_results
    )
    guarded_repair_execution_repair_command_executed = Counter(
        str(bool(item.get("repair_command_executed"))).lower()
        for item in guarded_repair_execution_results
    )
    guarded_repair_execution_rendered_command_executed = Counter(
        str(bool(item.get("rendered_command_executed"))).lower()
        for item in guarded_repair_execution_results
    )
    guarded_repair_execution_dry_run_command_executed = Counter(
        str(bool(item.get("dry_run_command_executed"))).lower()
        for item in guarded_repair_execution_results
    )
    guarded_repair_execution_repair_execution_enabled = Counter(
        str(bool(item.get("repair_execution_enabled"))).lower()
        for item in guarded_repair_execution_results
    )
    guarded_repair_execution_real_execution_enabled = Counter(
        str(bool(item.get("real_execution_enabled"))).lower()
        for item in guarded_repair_execution_results
    )
    guarded_repair_execution_subprocess_enabled = Counter(
        str(bool(item.get("subprocess_enabled"))).lower()
        for item in guarded_repair_execution_results
    )
    guarded_repair_execution_repair_execution_performed = Counter(
        str(bool(item.get("repair_execution_performed"))).lower()
        for item in guarded_repair_execution_results
    )
    guarded_repair_execution_repair_subprocess_invoked = Counter(
        str(bool(item.get("repair_subprocess_invoked"))).lower()
        for item in guarded_repair_execution_results
    )
    guarded_repair_execution_execution_performed = Counter(
        str(bool(item.get("execution_performed"))).lower()
        for item in guarded_repair_execution_results
    )
    guarded_repair_execution_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in guarded_repair_execution_results
    )
    post_repair_evidence_statuses = Counter(
        str(item.get("post_repair_status") or "unknown").strip() or "unknown"
        for item in post_repair_evidence_checks
    )
    post_repair_evidence_allowed = Counter(
        str(bool(item.get("post_repair_evidence_check_allowed"))).lower()
        for item in post_repair_evidence_checks
    )
    post_repair_evidence_enabled = Counter(
        str(bool(item.get("post_repair_evidence_check_enabled"))).lower()
        for item in post_repair_evidence_checks
    )
    post_repair_evidence_marker_observed = Counter(
        str(bool(item.get("post_repair_evidence_marker_observed"))).lower()
        for item in post_repair_evidence_checks
    )
    post_repair_evidence_exit_codes = Counter(
        str(item.get("post_repair_evidence_exit_code"))
        for item in post_repair_evidence_checks
    )
    post_repair_evidence_outcome_verified = Counter(
        str(bool(item.get("repair_outcome_verified"))).lower()
        for item in post_repair_evidence_checks
    )
    post_repair_evidence_expected_counts = Counter(
        str(item.get("repair_targets_expected_count") or 0)
        for item in post_repair_evidence_checks
    )
    post_repair_evidence_verified_counts = Counter(
        str(item.get("repair_targets_verified_count") or 0)
        for item in post_repair_evidence_checks
    )
    post_repair_evidence_missing_counts = Counter(
        str(len(item.get("repair_targets_missing") or []))
        for item in post_repair_evidence_checks
    )
    post_repair_evidence_unexpected_counts = Counter(
        str(len(item.get("repair_targets_unexpected") or []))
        for item in post_repair_evidence_checks
    )
    post_repair_evidence_next_actions = Counter(
        str(item.get("recommended_next_action") or "unknown").strip() or "unknown"
        for item in post_repair_evidence_checks
    )
    post_repair_evidence_source_statuses = Counter(
        str(item.get("source_guarded_repair_execution_status") or "unknown").strip()
        or "unknown"
        for item in post_repair_evidence_checks
    )
    post_repair_evidence_source_allowed = Counter(
        str(bool(item.get("source_guarded_repair_execution_allowed"))).lower()
        for item in post_repair_evidence_checks
    )
    post_repair_evidence_source_marker_observed = Counter(
        str(bool(item.get("source_guarded_repair_marker_observed"))).lower()
        for item in post_repair_evidence_checks
    )
    post_repair_evidence_source_exit_codes = Counter(
        str(item.get("source_guarded_repair_exit_code"))
        for item in post_repair_evidence_checks
    )
    post_repair_evidence_source_repair_actions_executed = Counter(
        str(bool(item.get("source_repair_actions_executed"))).lower()
        for item in post_repair_evidence_checks
    )
    post_repair_evidence_source_repair_execution_enabled = Counter(
        str(bool(item.get("source_repair_execution_enabled"))).lower()
        for item in post_repair_evidence_checks
    )
    post_repair_evidence_source_real_execution_enabled = Counter(
        str(bool(item.get("source_real_execution_enabled"))).lower()
        for item in post_repair_evidence_checks
    )
    post_repair_evidence_source_repair_execution_performed = Counter(
        str(bool(item.get("source_repair_execution_performed"))).lower()
        for item in post_repair_evidence_checks
    )
    post_repair_evidence_source_repair_subprocess_invoked = Counter(
        str(bool(item.get("source_repair_subprocess_invoked"))).lower()
        for item in post_repair_evidence_checks
    )
    post_repair_evidence_execution_performed = Counter(
        str(bool(item.get("execution_performed"))).lower()
        for item in post_repair_evidence_checks
    )
    post_repair_evidence_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in post_repair_evidence_checks
    )
    post_repair_evidence_repair_execution_enabled = Counter(
        str(bool(item.get("repair_execution_enabled"))).lower()
        for item in post_repair_evidence_checks
    )
    post_repair_evidence_real_execution_enabled = Counter(
        str(bool(item.get("real_execution_enabled"))).lower()
        for item in post_repair_evidence_checks
    )
    post_repair_evidence_repair_execution_performed = Counter(
        str(bool(item.get("repair_execution_performed"))).lower()
        for item in post_repair_evidence_checks
    )
    post_repair_evidence_repair_subprocess_invoked = Counter(
        str(bool(item.get("repair_subprocess_invoked"))).lower()
        for item in post_repair_evidence_checks
    )
    real_execution_adapter_contract_statuses = Counter(
        str(item.get("contract_status") or "unknown").strip() or "unknown"
        for item in real_execution_adapter_contracts
    )
    real_execution_adapter_contract_schema_versions = Counter(
        str(item.get("schema_version") or "unknown").strip() or "unknown"
        for item in real_execution_adapter_contracts
    )
    real_execution_adapter_contract_request_schema_versions = Counter(
        str(item.get("adapter_request_schema_version") or "unknown").strip()
        or "unknown"
        for item in real_execution_adapter_contracts
    )
    real_execution_adapter_contract_result_schema_versions = Counter(
        str(item.get("adapter_result_schema_version") or "unknown").strip()
        or "unknown"
        for item in real_execution_adapter_contracts
    )
    real_execution_adapter_contract_next_actions = Counter(
        str(item.get("recommended_next_action") or "unknown").strip() or "unknown"
        for item in real_execution_adapter_contracts
    )
    real_execution_adapter_contract_source_post_repair_statuses = Counter(
        str(item.get("source_post_repair_status") or "unknown").strip()
        or "unknown"
        for item in real_execution_adapter_contracts
    )
    real_execution_adapter_contract_source_expected_counts = Counter(
        str(item.get("source_repair_targets_expected_count") or 0)
        for item in real_execution_adapter_contracts
    )
    real_execution_adapter_contract_source_verified_counts = Counter(
        str(item.get("source_repair_targets_verified_count") or 0)
        for item in real_execution_adapter_contracts
    )

    real_execution_adapter_contract_exists = Counter(
        str(bool(item.get("adapter_contract_exists"))).lower()
        for item in real_execution_adapter_contracts
    )
    real_execution_adapter_contract_request_schema_exists = Counter(
        str(bool(item.get("adapter_request_schema_exists"))).lower()
        for item in real_execution_adapter_contracts
    )
    real_execution_adapter_contract_result_schema_exists = Counter(
        str(bool(item.get("adapter_result_schema_exists"))).lower()
        for item in real_execution_adapter_contracts
    )
    real_execution_adapter_contract_fail_closed_default = Counter(
        str(bool(item.get("fail_closed_default"))).lower()
        for item in real_execution_adapter_contracts
    )
    real_execution_adapter_contract_sandbox_first = Counter(
        str(bool(item.get("sandbox_first"))).lower()
        for item in real_execution_adapter_contracts
    )
    real_execution_adapter_contract_capability_scoped = Counter(
        str(bool(item.get("capability_scoped"))).lower()
        for item in real_execution_adapter_contracts
    )
    real_execution_adapter_contract_policy_gated = Counter(
        str(bool(item.get("policy_gated"))).lower()
        for item in real_execution_adapter_contracts
    )
    real_execution_adapter_contract_unknown_capability_rejected = Counter(
        str(bool(item.get("unknown_capability_rejected"))).lower()
        for item in real_execution_adapter_contracts
    )
    real_execution_adapter_contract_unknown_policy_rejected = Counter(
        str(bool(item.get("unknown_policy_rejected"))).lower()
        for item in real_execution_adapter_contracts
    )
    real_execution_adapter_contract_adapter_enabled = Counter(
        str(bool(item.get("adapter_implementation_enabled"))).lower()
        for item in real_execution_adapter_contracts
    )
    real_execution_adapter_contract_request_generation_enabled = Counter(
        str(bool(item.get("adapter_request_generation_enabled"))).lower()
        for item in real_execution_adapter_contracts
    )
    real_execution_adapter_contract_result_generation_enabled = Counter(
        str(bool(item.get("adapter_result_generation_enabled"))).lower()
        for item in real_execution_adapter_contracts
    )
    real_execution_adapter_contract_sandbox_execution_enabled = Counter(
        str(bool(item.get("sandbox_execution_enabled"))).lower()
        for item in real_execution_adapter_contracts
    )
    real_execution_adapter_contract_policy_gated_real_enabled = Counter(
        str(bool(item.get("policy_gated_real_execution_enabled"))).lower()
        for item in real_execution_adapter_contracts
    )
    real_execution_adapter_contract_execution_performed = Counter(
        str(bool(item.get("execution_performed"))).lower()
        for item in real_execution_adapter_contracts
    )
    real_execution_adapter_contract_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in real_execution_adapter_contracts
    )
    real_execution_adapter_contract_real_execution_enabled = Counter(
        str(bool(item.get("real_execution_enabled"))).lower()
        for item in real_execution_adapter_contracts
    )
    real_execution_adapter_contract_external_side_effects = Counter(
        str(bool(item.get("external_side_effects_performed"))).lower()
        for item in real_execution_adapter_contracts
    )
    real_execution_adapter_contract_production_paths_mutated = Counter(
        str(bool(item.get("production_paths_mutated"))).lower()
        for item in real_execution_adapter_contracts
    )
    real_execution_adapter_contract_production_secrets_accessed = Counter(
        str(bool(item.get("production_secrets_accessed"))).lower()
        for item in real_execution_adapter_contracts
    )
    real_execution_adapter_contract_source_verified = Counter(
        str(bool(item.get("source_repair_outcome_verified"))).lower()
        for item in real_execution_adapter_contracts
    )
    real_execution_adapter_request_schema_statuses = Counter(
        str(item.get("adapter_request_schema_status") or "unknown").strip()
        or "unknown"
        for item in real_execution_adapter_request_schemas
    )
    real_execution_adapter_request_schema_versions = Counter(
        str(item.get("schema_version") or "unknown").strip() or "unknown"
        for item in real_execution_adapter_request_schemas
    )
    real_execution_adapter_request_schema_next_actions = Counter(
        str(item.get("recommended_next_action") or "unknown").strip() or "unknown"
        for item in real_execution_adapter_request_schemas
    )
    real_execution_adapter_request_schema_source_contract_statuses = Counter(
        str(item.get("source_contract_status") or "unknown").strip() or "unknown"
        for item in real_execution_adapter_request_schemas
    )
    real_execution_adapter_request_schema_source_expected_counts = Counter(
        str(item.get("source_repair_targets_expected_count") or 0)
        for item in real_execution_adapter_request_schemas
    )
    real_execution_adapter_request_schema_source_verified_counts = Counter(
        str(item.get("source_repair_targets_verified_count") or 0)
        for item in real_execution_adapter_request_schemas
    )

    real_execution_adapter_request_schema_exists = Counter(
        str(bool(item.get("adapter_request_schema_exists"))).lower()
        for item in real_execution_adapter_request_schemas
    )
    real_execution_adapter_request_schema_contract_exists = Counter(
        str(bool(item.get("adapter_contract_exists"))).lower()
        for item in real_execution_adapter_request_schemas
    )
    real_execution_adapter_request_schema_result_schema_exists = Counter(
        str(bool(item.get("adapter_result_schema_exists"))).lower()
        for item in real_execution_adapter_request_schemas
    )
    real_execution_adapter_request_schema_fail_closed_default = Counter(
        str(bool(item.get("fail_closed_default"))).lower()
        for item in real_execution_adapter_request_schemas
    )
    real_execution_adapter_request_schema_deny_by_default = Counter(
        str(bool(item.get("deny_by_default"))).lower()
        for item in real_execution_adapter_request_schemas
    )
    real_execution_adapter_request_schema_unknown_capability_rejected = Counter(
        str(bool(item.get("unknown_capability_rejected"))).lower()
        for item in real_execution_adapter_request_schemas
    )
    real_execution_adapter_request_schema_unknown_policy_rejected = Counter(
        str(bool(item.get("unknown_policy_rejected"))).lower()
        for item in real_execution_adapter_request_schemas
    )
    real_execution_adapter_request_schema_request_generation_enabled = Counter(
        str(bool(item.get("request_generation_enabled"))).lower()
        for item in real_execution_adapter_request_schemas
    )
    real_execution_adapter_request_schema_request_execution_enabled = Counter(
        str(bool(item.get("request_execution_enabled"))).lower()
        for item in real_execution_adapter_request_schemas
    )
    real_execution_adapter_request_schema_adapter_enabled = Counter(
        str(bool(item.get("adapter_implementation_enabled"))).lower()
        for item in real_execution_adapter_request_schemas
    )
    real_execution_adapter_request_schema_result_generation_enabled = Counter(
        str(bool(item.get("adapter_result_generation_enabled"))).lower()
        for item in real_execution_adapter_request_schemas
    )
    real_execution_adapter_request_schema_sandbox_execution_enabled = Counter(
        str(bool(item.get("sandbox_execution_enabled"))).lower()
        for item in real_execution_adapter_request_schemas
    )
    real_execution_adapter_request_schema_policy_gated_real_enabled = Counter(
        str(bool(item.get("policy_gated_real_execution_enabled"))).lower()
        for item in real_execution_adapter_request_schemas
    )
    real_execution_adapter_request_schema_execution_performed = Counter(
        str(bool(item.get("execution_performed"))).lower()
        for item in real_execution_adapter_request_schemas
    )
    real_execution_adapter_request_schema_subprocess_invoked = Counter(
        str(bool(item.get("subprocess_invoked"))).lower()
        for item in real_execution_adapter_request_schemas
    )
    real_execution_adapter_request_schema_real_execution_enabled = Counter(
        str(bool(item.get("real_execution_enabled"))).lower()
        for item in real_execution_adapter_request_schemas
    )
    real_execution_adapter_request_schema_external_side_effects = Counter(
        str(bool(item.get("external_side_effects_performed"))).lower()
        for item in real_execution_adapter_request_schemas
    )
    real_execution_adapter_request_schema_production_paths_mutated = Counter(
        str(bool(item.get("production_paths_mutated"))).lower()
        for item in real_execution_adapter_request_schemas
    )
    real_execution_adapter_request_schema_production_secrets_accessed = Counter(
        str(bool(item.get("production_secrets_accessed"))).lower()
        for item in real_execution_adapter_request_schemas
    )
    real_execution_adapter_request_schema_source_verified = Counter(
        str(bool(item.get("source_repair_outcome_verified"))).lower()
        for item in real_execution_adapter_request_schemas
    )
    real_execution_capability_policy_matrix_statuses = Counter(
        str(item.get("matrix_status") or "unknown").strip() or "unknown"
        for item in real_execution_capability_policy_matrices
    )
    real_execution_capability_policy_matrix_schema_versions = Counter(
        str(item.get("schema_version") or "unknown").strip() or "unknown"
        for item in real_execution_capability_policy_matrices
    )
    real_execution_capability_policy_matrix_next_actions = Counter(
        str(item.get("recommended_next_action") or "unknown").strip() or "unknown"
        for item in real_execution_capability_policy_matrices
    )
    real_execution_capability_policy_matrix_capability_counts = Counter(
        str(item.get("capability_count") or 0)
        for item in real_execution_capability_policy_matrices
    )
    real_execution_capability_policy_matrix_enabled_capability_counts = Counter(
        str(item.get("enabled_capability_count") or 0)
        for item in real_execution_capability_policy_matrices
    )
    real_execution_capability_policy_matrix_blocked_capability_counts = Counter(
        str(item.get("blocked_capability_count") or 0)
        for item in real_execution_capability_policy_matrices
    )
    real_execution_capability_policy_matrix_policy_rule_counts = Counter(
        str(item.get("policy_rule_count") or 0)
        for item in real_execution_capability_policy_matrices
    )
    real_execution_capability_policy_matrix_approved_policy_counts = Counter(
        str(item.get("approved_policy_count") or 0)
        for item in real_execution_capability_policy_matrices
    )
    real_execution_capability_policy_matrix_blocked_policy_counts = Counter(
        str(item.get("blocked_policy_count") or 0)
        for item in real_execution_capability_policy_matrices
    )
    real_execution_capability_policy_matrix_source_request_schema_statuses = Counter(
        str(item.get("source_request_schema_status") or "unknown").strip()
        or "unknown"
        for item in real_execution_capability_policy_matrices
    )
    real_execution_capability_policy_matrix_source_expected_counts = Counter(
        str(item.get("source_repair_targets_expected_count") or 0)
        for item in real_execution_capability_policy_matrices
    )
    real_execution_capability_policy_matrix_source_verified_counts = Counter(
        str(item.get("source_repair_targets_verified_count") or 0)
        for item in real_execution_capability_policy_matrices
    )

    def _bool_counter(key: str) -> Counter[str]:
        return Counter(
            str(bool(item.get(key))).lower()
            for item in real_execution_capability_policy_matrices
        )

    real_execution_capability_policy_matrix_registry_exists = _bool_counter(
        "capability_registry_exists"
    )
    real_execution_capability_policy_matrix_policy_exists = _bool_counter(
        "policy_matrix_exists"
    )
    real_execution_capability_policy_matrix_unknown_capability_rejected = _bool_counter(
        "unknown_capability_rejected"
    )
    real_execution_capability_policy_matrix_unknown_policy_rejected = _bool_counter(
        "unknown_policy_rejected"
    )
    real_execution_capability_policy_matrix_deny_by_default = _bool_counter(
        "deny_by_default"
    )
    real_execution_capability_policy_matrix_fail_closed_default = _bool_counter(
        "fail_closed_default"
    )
    real_execution_capability_policy_matrix_sandbox_real_blocked = _bool_counter(
        "sandbox_real_blocked"
    )
    real_execution_capability_policy_matrix_policy_gated_real_blocked = _bool_counter(
        "policy_gated_real_blocked"
    )
    real_execution_capability_policy_matrix_external_side_effects_allowed = _bool_counter(
        "external_side_effects_allowed"
    )
    real_execution_capability_policy_matrix_production_paths_allowed = _bool_counter(
        "production_paths_allowed"
    )
    real_execution_capability_policy_matrix_production_secrets_allowed = _bool_counter(
        "production_secrets_allowed"
    )
    real_execution_capability_policy_matrix_capability_execution_enabled = _bool_counter(
        "capability_execution_enabled"
    )
    real_execution_capability_policy_matrix_policy_execution_enabled = _bool_counter(
        "policy_execution_enabled"
    )
    real_execution_capability_policy_matrix_adapter_request_generation_enabled = _bool_counter(
        "adapter_request_generation_enabled"
    )
    real_execution_capability_policy_matrix_adapter_request_execution_enabled = _bool_counter(
        "adapter_request_execution_enabled"
    )
    real_execution_capability_policy_matrix_adapter_result_generation_enabled = _bool_counter(
        "adapter_result_generation_enabled"
    )
    real_execution_capability_policy_matrix_sandbox_execution_enabled = _bool_counter(
        "sandbox_execution_enabled"
    )
    real_execution_capability_policy_matrix_policy_gated_real_execution_enabled = _bool_counter(
        "policy_gated_real_execution_enabled"
    )
    real_execution_capability_policy_matrix_execution_performed = _bool_counter(
        "execution_performed"
    )
    real_execution_capability_policy_matrix_subprocess_invoked = _bool_counter(
        "subprocess_invoked"
    )
    real_execution_capability_policy_matrix_real_execution_enabled = _bool_counter(
        "real_execution_enabled"
    )
    real_execution_capability_policy_matrix_external_side_effects_performed = _bool_counter(
        "external_side_effects_performed"
    )
    real_execution_capability_policy_matrix_production_paths_mutated = _bool_counter(
        "production_paths_mutated"
    )
    real_execution_capability_policy_matrix_production_secrets_accessed = _bool_counter(
        "production_secrets_accessed"
    )
    real_execution_capability_policy_matrix_source_verified = _bool_counter(
        "source_repair_outcome_verified"
    )
    real_execution_sandbox_adapter_scaffold_statuses = Counter(
        str(item.get("sandbox_adapter_scaffold_status") or "unknown").strip()
        or "unknown"
        for item in real_execution_sandbox_adapter_scaffolds
    )
    real_execution_sandbox_adapter_scaffold_schema_versions = Counter(
        str(item.get("schema_version") or "unknown").strip() or "unknown"
        for item in real_execution_sandbox_adapter_scaffolds
    )
    real_execution_sandbox_adapter_scaffold_next_actions = Counter(
        str(item.get("recommended_next_action") or "unknown").strip()
        or "unknown"
        for item in real_execution_sandbox_adapter_scaffolds
    )
    real_execution_sandbox_adapter_scaffold_workspace_strategies = Counter(
        str(item.get("sandbox_workspace_strategy") or "unknown").strip()
        or "unknown"
        for item in real_execution_sandbox_adapter_scaffolds
    )
    real_execution_sandbox_adapter_scaffold_network_policies = Counter(
        str(item.get("sandbox_network_policy") or "unknown").strip()
        or "unknown"
        for item in real_execution_sandbox_adapter_scaffolds
    )
    real_execution_sandbox_adapter_scaffold_secret_policies = Counter(
        str(item.get("sandbox_secret_policy") or "unknown").strip()
        or "unknown"
        for item in real_execution_sandbox_adapter_scaffolds
    )
    real_execution_sandbox_adapter_scaffold_filesystem_policies = Counter(
        str(item.get("sandbox_filesystem_policy") or "unknown").strip()
        or "unknown"
        for item in real_execution_sandbox_adapter_scaffolds
    )

    def _sandbox_scaffold_bool_counter(key: str) -> Counter[str]:
        return Counter(
            str(bool(item.get(key))).lower()
            for item in real_execution_sandbox_adapter_scaffolds
        )

    real_execution_sandbox_adapter_scaffold_fail_closed = (
        _sandbox_scaffold_bool_counter("sandbox_adapter_fail_closed")
    )
    real_execution_sandbox_adapter_scaffold_deny_by_default = (
        _sandbox_scaffold_bool_counter("sandbox_adapter_deny_by_default")
    )
    real_execution_sandbox_adapter_scaffold_sandbox_execution_enabled = (
        _sandbox_scaffold_bool_counter("sandbox_execution_enabled")
    )
    real_execution_sandbox_adapter_scaffold_execution_performed = (
        _sandbox_scaffold_bool_counter("execution_performed")
    )
    real_execution_sandbox_adapter_scaffold_subprocess_invoked = (
        _sandbox_scaffold_bool_counter("subprocess_invoked")
    )
    real_execution_sandbox_adapter_scaffold_real_execution_enabled = (
        _sandbox_scaffold_bool_counter("real_execution_enabled")
    )
    real_execution_sandbox_adapter_scaffold_external_side_effects_performed = (
        _sandbox_scaffold_bool_counter("external_side_effects_performed")
    )
    real_execution_sandbox_adapter_scaffold_production_paths_mutated = (
        _sandbox_scaffold_bool_counter("production_paths_mutated")
    )
    real_execution_sandbox_adapter_scaffold_production_secrets_accessed = (
        _sandbox_scaffold_bool_counter("production_secrets_accessed")
    )

    real_execution_sandbox_adapter_request_preflight_statuses = Counter(
        str(item.get("sandbox_adapter_request_preflight_status") or "unknown").strip()
        or "unknown"
        for item in real_execution_sandbox_adapter_request_preflights
    )
    real_execution_sandbox_adapter_request_preflight_schema_versions = Counter(
        str(item.get("schema_version") or "unknown").strip() or "unknown"
        for item in real_execution_sandbox_adapter_request_preflights
    )
    real_execution_sandbox_adapter_request_preflight_next_actions = Counter(
        str(item.get("recommended_next_action") or "unknown").strip()
        or "unknown"
        for item in real_execution_sandbox_adapter_request_preflights
    )

    def _sandbox_request_preflight_bool_counter(key: str) -> Counter[str]:
        return Counter(
            str(bool(item.get(key))).lower()
            for item in real_execution_sandbox_adapter_request_preflights
        )

    real_execution_sandbox_adapter_request_preflight_fail_closed = (
        _sandbox_request_preflight_bool_counter(
            "sandbox_adapter_request_preflight_fail_closed"
        )
    )
    real_execution_sandbox_adapter_request_preflight_deny_by_default = (
        _sandbox_request_preflight_bool_counter(
            "sandbox_adapter_request_preflight_deny_by_default"
        )
    )
    real_execution_sandbox_adapter_request_preflight_request_generation_enabled = (
        _sandbox_request_preflight_bool_counter(
            "sandbox_adapter_request_generation_enabled"
        )
    )
    real_execution_sandbox_adapter_request_preflight_workspace_creation_enabled = (
        _sandbox_request_preflight_bool_counter("sandbox_workspace_creation_enabled")
    )
    real_execution_sandbox_adapter_request_preflight_input_materialization_enabled = (
        _sandbox_request_preflight_bool_counter(
            "sandbox_input_materialization_enabled"
        )
    )
    real_execution_sandbox_adapter_request_preflight_command_rendering_enabled = (
        _sandbox_request_preflight_bool_counter("sandbox_command_rendering_enabled")
    )
    real_execution_sandbox_adapter_request_preflight_sandbox_execution_enabled = (
        _sandbox_request_preflight_bool_counter("sandbox_execution_enabled")
    )
    real_execution_sandbox_adapter_request_preflight_result_generation_enabled = (
        _sandbox_request_preflight_bool_counter("sandbox_result_generation_enabled")
    )
    real_execution_sandbox_adapter_request_preflight_execution_performed = (
        _sandbox_request_preflight_bool_counter("execution_performed")
    )
    real_execution_sandbox_adapter_request_preflight_subprocess_invoked = (
        _sandbox_request_preflight_bool_counter("subprocess_invoked")
    )
    real_execution_sandbox_adapter_request_preflight_real_execution_enabled = (
        _sandbox_request_preflight_bool_counter("real_execution_enabled")
    )
    real_execution_sandbox_adapter_request_preflight_external_side_effects_performed = (
        _sandbox_request_preflight_bool_counter("external_side_effects_performed")
    )
    real_execution_sandbox_adapter_request_preflight_production_paths_mutated = (
        _sandbox_request_preflight_bool_counter("production_paths_mutated")
    )
    real_execution_sandbox_adapter_request_preflight_production_secrets_accessed = (
        _sandbox_request_preflight_bool_counter("production_secrets_accessed")
    )
    real_execution_sandbox_request_envelope_scaffold_statuses = Counter(
        str(item.get("sandbox_request_envelope_scaffold_status") or "unknown").strip()
        or "unknown"
        for item in real_execution_sandbox_request_envelope_scaffolds
    )
    real_execution_sandbox_request_envelope_scaffold_schema_versions = Counter(
        str(item.get("schema_version") or "unknown").strip() or "unknown"
        for item in real_execution_sandbox_request_envelope_scaffolds
    )
    real_execution_sandbox_request_envelope_scaffold_next_actions = Counter(
        str(item.get("recommended_next_action") or "unknown").strip()
        or "unknown"
        for item in real_execution_sandbox_request_envelope_scaffolds
    )

    def _sandbox_request_envelope_scaffold_bool_counter(key: str) -> Counter[str]:
        return Counter(
            str(bool(item.get(key))).lower()
            for item in real_execution_sandbox_request_envelope_scaffolds
        )

    real_execution_sandbox_request_envelope_scaffold_fail_closed = (
        _sandbox_request_envelope_scaffold_bool_counter(
            "sandbox_request_envelope_scaffold_fail_closed"
        )
    )
    real_execution_sandbox_request_envelope_scaffold_deny_by_default = (
        _sandbox_request_envelope_scaffold_bool_counter(
            "sandbox_request_envelope_scaffold_deny_by_default"
        )
    )
    real_execution_sandbox_request_envelope_scaffold_envelope_generation_enabled = (
        _sandbox_request_envelope_scaffold_bool_counter(
            "sandbox_request_envelope_generation_enabled"
        )
    )
    real_execution_sandbox_request_envelope_scaffold_envelope_materialized = (
        _sandbox_request_envelope_scaffold_bool_counter(
            "sandbox_request_envelope_materialized"
        )
    )
    real_execution_sandbox_request_envelope_scaffold_envelope_executable = (
        _sandbox_request_envelope_scaffold_bool_counter(
            "sandbox_request_envelope_executable"
        )
    )
    real_execution_sandbox_request_envelope_scaffold_request_generation_enabled = (
        _sandbox_request_envelope_scaffold_bool_counter(
            "sandbox_adapter_request_generation_enabled"
        )
    )
    real_execution_sandbox_request_envelope_scaffold_workspace_creation_enabled = (
        _sandbox_request_envelope_scaffold_bool_counter(
            "sandbox_workspace_creation_enabled"
        )
    )
    real_execution_sandbox_request_envelope_scaffold_input_materialization_enabled = (
        _sandbox_request_envelope_scaffold_bool_counter(
            "sandbox_input_materialization_enabled"
        )
    )
    real_execution_sandbox_request_envelope_scaffold_command_rendering_enabled = (
        _sandbox_request_envelope_scaffold_bool_counter(
            "sandbox_command_rendering_enabled"
        )
    )
    real_execution_sandbox_request_envelope_scaffold_sandbox_execution_enabled = (
        _sandbox_request_envelope_scaffold_bool_counter("sandbox_execution_enabled")
    )
    real_execution_sandbox_request_envelope_scaffold_result_generation_enabled = (
        _sandbox_request_envelope_scaffold_bool_counter(
            "sandbox_result_generation_enabled"
        )
    )
    real_execution_sandbox_request_envelope_scaffold_execution_performed = (
        _sandbox_request_envelope_scaffold_bool_counter("execution_performed")
    )
    real_execution_sandbox_request_envelope_scaffold_subprocess_invoked = (
        _sandbox_request_envelope_scaffold_bool_counter("subprocess_invoked")
    )
    real_execution_sandbox_request_envelope_scaffold_real_execution_enabled = (
        _sandbox_request_envelope_scaffold_bool_counter("real_execution_enabled")
    )
    real_execution_sandbox_request_envelope_scaffold_external_side_effects_performed = (
        _sandbox_request_envelope_scaffold_bool_counter(
            "external_side_effects_performed"
        )
    )
    real_execution_sandbox_request_envelope_scaffold_production_paths_mutated = (
        _sandbox_request_envelope_scaffold_bool_counter("production_paths_mutated")
    )
    real_execution_sandbox_request_envelope_scaffold_production_secrets_accessed = (
        _sandbox_request_envelope_scaffold_bool_counter(
            "production_secrets_accessed"
        )
    )
    real_execution_sandbox_materialization_preflight_scaffold_statuses = Counter(
        str(
            item.get("sandbox_materialization_preflight_scaffold_status")
            or "unknown"
        ).strip()
        or "unknown"
        for item in real_execution_sandbox_materialization_preflight_scaffolds
    )
    real_execution_sandbox_materialization_preflight_scaffold_schema_versions = Counter(
        str(item.get("schema_version") or "unknown").strip() or "unknown"
        for item in real_execution_sandbox_materialization_preflight_scaffolds
    )
    real_execution_sandbox_materialization_preflight_scaffold_next_actions = Counter(
        str(item.get("recommended_next_action") or "unknown").strip()
        or "unknown"
        for item in real_execution_sandbox_materialization_preflight_scaffolds
    )

    def _sandbox_materialization_preflight_scaffold_bool_counter(
        key: str,
    ) -> Counter[str]:
        return Counter(
            str(bool(item.get(key))).lower()
            for item in real_execution_sandbox_materialization_preflight_scaffolds
        )

    real_execution_sandbox_materialization_preflight_scaffold_fail_closed = (
        _sandbox_materialization_preflight_scaffold_bool_counter(
            "sandbox_materialization_preflight_scaffold_fail_closed"
        )
    )
    real_execution_sandbox_materialization_preflight_scaffold_deny_by_default = (
        _sandbox_materialization_preflight_scaffold_bool_counter(
            "sandbox_materialization_preflight_scaffold_deny_by_default"
        )
    )
    real_execution_sandbox_materialization_preflight_scaffold_preflight_enabled = (
        _sandbox_materialization_preflight_scaffold_bool_counter(
            "sandbox_materialization_preflight_enabled"
        )
    )
    real_execution_sandbox_materialization_preflight_scaffold_preflight_passed = (
        _sandbox_materialization_preflight_scaffold_bool_counter(
            "sandbox_materialization_preflight_passed"
        )
    )
    real_execution_sandbox_materialization_preflight_scaffold_envelope_generation_enabled = (
        _sandbox_materialization_preflight_scaffold_bool_counter(
            "sandbox_request_envelope_generation_enabled"
        )
    )
    real_execution_sandbox_materialization_preflight_scaffold_envelope_materialized = (
        _sandbox_materialization_preflight_scaffold_bool_counter(
            "sandbox_request_envelope_materialized"
        )
    )
    real_execution_sandbox_materialization_preflight_scaffold_envelope_executable = (
        _sandbox_materialization_preflight_scaffold_bool_counter(
            "sandbox_request_envelope_executable"
        )
    )
    real_execution_sandbox_materialization_preflight_scaffold_workspace_creation_enabled = (
        _sandbox_materialization_preflight_scaffold_bool_counter(
            "sandbox_workspace_creation_enabled"
        )
    )
    real_execution_sandbox_materialization_preflight_scaffold_input_materialization_enabled = (
        _sandbox_materialization_preflight_scaffold_bool_counter(
            "sandbox_input_materialization_enabled"
        )
    )
    real_execution_sandbox_materialization_preflight_scaffold_command_rendering_enabled = (
        _sandbox_materialization_preflight_scaffold_bool_counter(
            "sandbox_command_rendering_enabled"
        )
    )
    real_execution_sandbox_materialization_preflight_scaffold_sandbox_execution_enabled = (
        _sandbox_materialization_preflight_scaffold_bool_counter(
            "sandbox_execution_enabled"
        )
    )
    real_execution_sandbox_materialization_preflight_scaffold_result_generation_enabled = (
        _sandbox_materialization_preflight_scaffold_bool_counter(
            "sandbox_result_generation_enabled"
        )
    )
    real_execution_sandbox_materialization_preflight_scaffold_execution_performed = (
        _sandbox_materialization_preflight_scaffold_bool_counter(
            "execution_performed"
        )
    )
    real_execution_sandbox_materialization_preflight_scaffold_subprocess_invoked = (
        _sandbox_materialization_preflight_scaffold_bool_counter(
            "subprocess_invoked"
        )
    )
    real_execution_sandbox_materialization_preflight_scaffold_real_execution_enabled = (
        _sandbox_materialization_preflight_scaffold_bool_counter(
            "real_execution_enabled"
        )
    )
    real_execution_sandbox_materialization_preflight_scaffold_external_side_effects_performed = (
        _sandbox_materialization_preflight_scaffold_bool_counter(
            "external_side_effects_performed"
        )
    )
    real_execution_sandbox_materialization_preflight_scaffold_production_paths_mutated = (
        _sandbox_materialization_preflight_scaffold_bool_counter(
            "production_paths_mutated"
        )
    )
    real_execution_sandbox_materialization_preflight_scaffold_production_secrets_accessed = (
        _sandbox_materialization_preflight_scaffold_bool_counter(
            "production_secrets_accessed"
        )
    )
    real_execution_sandbox_workspace_plan_scaffold_statuses = Counter(
        str(item.get("sandbox_workspace_plan_scaffold_status") or "unknown").strip()
        or "unknown"
        for item in real_execution_sandbox_workspace_plan_scaffolds
    )
    real_execution_sandbox_workspace_plan_scaffold_schema_versions = Counter(
        str(item.get("schema_version") or "unknown").strip() or "unknown"
        for item in real_execution_sandbox_workspace_plan_scaffolds
    )
    real_execution_sandbox_workspace_plan_scaffold_next_actions = Counter(
        str(item.get("recommended_next_action") or "unknown").strip()
        or "unknown"
        for item in real_execution_sandbox_workspace_plan_scaffolds
    )

    def _sandbox_workspace_plan_scaffold_bool_counter(key: str) -> Counter[str]:
        return Counter(
            str(bool(item.get(key))).lower()
            for item in real_execution_sandbox_workspace_plan_scaffolds
        )

    real_execution_sandbox_workspace_plan_scaffold_fail_closed = (
        _sandbox_workspace_plan_scaffold_bool_counter(
            "sandbox_workspace_plan_scaffold_fail_closed"
        )
    )
    real_execution_sandbox_workspace_plan_scaffold_deny_by_default = (
        _sandbox_workspace_plan_scaffold_bool_counter(
            "sandbox_workspace_plan_scaffold_deny_by_default"
        )
    )
    real_execution_sandbox_workspace_plan_scaffold_plan_generation_enabled = (
        _sandbox_workspace_plan_scaffold_bool_counter(
            "sandbox_workspace_plan_generation_enabled"
        )
    )
    real_execution_sandbox_workspace_plan_scaffold_plan_materialized = (
        _sandbox_workspace_plan_scaffold_bool_counter(
            "sandbox_workspace_plan_materialized"
        )
    )
    real_execution_sandbox_workspace_plan_scaffold_plan_executable = (
        _sandbox_workspace_plan_scaffold_bool_counter(
            "sandbox_workspace_plan_executable"
        )
    )
    real_execution_sandbox_workspace_plan_scaffold_directory_creation_enabled = (
        _sandbox_workspace_plan_scaffold_bool_counter(
            "sandbox_workspace_directory_creation_enabled"
        )
    )
    real_execution_sandbox_workspace_plan_scaffold_workspace_created = (
        _sandbox_workspace_plan_scaffold_bool_counter("sandbox_workspace_created")
    )
    real_execution_sandbox_workspace_plan_scaffold_cleanup_registered = (
        _sandbox_workspace_plan_scaffold_bool_counter(
            "sandbox_workspace_cleanup_registered"
        )
    )
    real_execution_sandbox_workspace_plan_scaffold_materialization_preflight_enabled = (
        _sandbox_workspace_plan_scaffold_bool_counter(
            "sandbox_materialization_preflight_enabled"
        )
    )
    real_execution_sandbox_workspace_plan_scaffold_materialization_preflight_passed = (
        _sandbox_workspace_plan_scaffold_bool_counter(
            "sandbox_materialization_preflight_passed"
        )
    )
    real_execution_sandbox_workspace_plan_scaffold_envelope_generation_enabled = (
        _sandbox_workspace_plan_scaffold_bool_counter(
            "sandbox_request_envelope_generation_enabled"
        )
    )
    real_execution_sandbox_workspace_plan_scaffold_envelope_materialized = (
        _sandbox_workspace_plan_scaffold_bool_counter(
            "sandbox_request_envelope_materialized"
        )
    )
    real_execution_sandbox_workspace_plan_scaffold_envelope_executable = (
        _sandbox_workspace_plan_scaffold_bool_counter(
            "sandbox_request_envelope_executable"
        )
    )
    real_execution_sandbox_workspace_plan_scaffold_workspace_creation_enabled = (
        _sandbox_workspace_plan_scaffold_bool_counter(
            "sandbox_workspace_creation_enabled"
        )
    )
    real_execution_sandbox_workspace_plan_scaffold_input_materialization_enabled = (
        _sandbox_workspace_plan_scaffold_bool_counter(
            "sandbox_input_materialization_enabled"
        )
    )
    real_execution_sandbox_workspace_plan_scaffold_command_rendering_enabled = (
        _sandbox_workspace_plan_scaffold_bool_counter(
            "sandbox_command_rendering_enabled"
        )
    )
    real_execution_sandbox_workspace_plan_scaffold_sandbox_execution_enabled = (
        _sandbox_workspace_plan_scaffold_bool_counter("sandbox_execution_enabled")
    )
    real_execution_sandbox_workspace_plan_scaffold_result_generation_enabled = (
        _sandbox_workspace_plan_scaffold_bool_counter(
            "sandbox_result_generation_enabled"
        )
    )
    real_execution_sandbox_workspace_plan_scaffold_execution_performed = (
        _sandbox_workspace_plan_scaffold_bool_counter("execution_performed")
    )
    real_execution_sandbox_workspace_plan_scaffold_subprocess_invoked = (
        _sandbox_workspace_plan_scaffold_bool_counter("subprocess_invoked")
    )
    real_execution_sandbox_workspace_plan_scaffold_real_execution_enabled = (
        _sandbox_workspace_plan_scaffold_bool_counter("real_execution_enabled")
    )
    real_execution_sandbox_workspace_plan_scaffold_external_side_effects_performed = (
        _sandbox_workspace_plan_scaffold_bool_counter(
            "external_side_effects_performed"
        )
    )
    real_execution_sandbox_workspace_plan_scaffold_production_paths_mutated = (
        _sandbox_workspace_plan_scaffold_bool_counter("production_paths_mutated")
    )
    real_execution_sandbox_workspace_plan_scaffold_production_secrets_accessed = (
        _sandbox_workspace_plan_scaffold_bool_counter(
            "production_secrets_accessed"
        )
    )

    chain_ids = _build_chain_ids(
        proposals=proposals,
        approvals=approvals,
        plans=plans,
        rendered_commands=rendered_commands,
        rendered_command_results=rendered_command_results,
        eligibilities=eligibilities,
        controlled_execution_results=controlled_execution_results,
        mock_execution_summaries=mock_execution_summaries,
        real_preflights=real_preflights,
        real_approvals=real_approvals,
        real_approval_transitions=real_approval_transitions,
        real_final_gates=real_final_gates,
        real_dry_run_envelopes=real_dry_run_envelopes,
        real_noop_results=real_noop_results,
        real_read_only_promotions=real_read_only_promotions,
        real_read_only_final_gates=real_read_only_final_gates,
        real_read_only_approvals=real_read_only_approvals,
        real_read_only_approval_transitions=real_read_only_approval_transitions,
        real_read_only_readiness_gates=real_read_only_readiness_gates,
        real_read_only_execution_results=real_read_only_execution_results,
        real_read_only_feedback_records=real_read_only_feedback_records,
        real_read_only_repair_plans=real_read_only_repair_plans,
        real_read_only_repair_action_bundles=real_read_only_repair_action_bundles,
        real_read_only_repair_action_bundle_reviews=(
            real_read_only_repair_action_bundle_reviews
        ),
        real_repair_approvals=real_repair_approvals,
        real_repair_approval_transitions=real_repair_approval_transitions,
        real_repair_final_gates=real_repair_final_gates,
        real_repair_dry_run_envelopes=real_repair_dry_run_envelopes,
        real_repair_noop_results=real_repair_noop_results,
        real_repair_noop_feedback_records=real_repair_noop_feedback_records,
        real_repair_readiness_gates=real_repair_readiness_gates,
        guarded_repair_execution_results=guarded_repair_execution_results,
        post_repair_evidence_checks=post_repair_evidence_checks,
        real_execution_adapter_contracts=real_execution_adapter_contracts,
        real_execution_adapter_request_schemas=real_execution_adapter_request_schemas,
        real_execution_capability_policy_matrices=real_execution_capability_policy_matrices,
        real_execution_sandbox_adapter_scaffolds=(
            real_execution_sandbox_adapter_scaffolds
        ),
        real_execution_sandbox_adapter_request_preflights=(
            real_execution_sandbox_adapter_request_preflights
        ),
        real_execution_sandbox_request_envelope_scaffolds=(
            real_execution_sandbox_request_envelope_scaffolds
        ),
        real_execution_sandbox_materialization_preflight_scaffolds=(
            real_execution_sandbox_materialization_preflight_scaffolds
        ),
        real_execution_sandbox_workspace_plan_scaffolds=(
            real_execution_sandbox_workspace_plan_scaffolds
        ),
        results=results,
    )

    missing_stages = _missing_stages(
        proposals=proposals,
        approvals=approvals,
        plans=plans,
        rendered_commands=rendered_commands,
        rendered_command_results=rendered_command_results,
        eligibilities=eligibilities,
        results=results,
    )

    real_linkage = _real_linkage_summary(
        controlled_execution_results=controlled_execution_results,
        real_preflights=real_preflights,
        real_approvals=real_approvals,
    )

    real_dry_run_linkage = _real_dry_run_linkage_summary(
        real_final_gates=real_final_gates,
        real_dry_run_envelopes=real_dry_run_envelopes,
    )

    real_noop_linkage = _real_noop_linkage_summary(
        real_dry_run_envelopes=real_dry_run_envelopes,
        real_noop_results=real_noop_results,
    )

    real_read_only_promotion_linkage = (
        _real_read_only_promotion_linkage_summary(
            real_noop_results=real_noop_results,
            real_read_only_promotions=real_read_only_promotions,
        )
    )

    real_read_only_final_gate_linkage = (
        _real_read_only_final_gate_linkage_summary(
            real_read_only_promotions=real_read_only_promotions,
            real_read_only_final_gates=real_read_only_final_gates,
        )
    )

    real_read_only_approval_linkage = _real_read_only_approval_linkage_summary(
        real_read_only_final_gates=real_read_only_final_gates,
        real_read_only_approvals=real_read_only_approvals,
    )

    real_read_only_approval_transition_linkage = (
        _real_read_only_approval_transition_linkage_summary(
            real_read_only_approvals=real_read_only_approvals,
            real_read_only_approval_transitions=real_read_only_approval_transitions,
        )
    )

    real_read_only_readiness_gate_linkage = (
        _real_read_only_readiness_gate_linkage_summary(
            real_read_only_approval_transitions=(
                real_read_only_approval_transitions
            ),
            real_read_only_readiness_gates=real_read_only_readiness_gates,
        )
    )

    real_read_only_execution_result_linkage = (
        _real_read_only_execution_result_linkage_summary(
            real_read_only_readiness_gates=real_read_only_readiness_gates,
            real_read_only_execution_results=real_read_only_execution_results,
        )
    )

    real_read_only_feedback_linkage = _real_read_only_feedback_linkage_summary(
        real_read_only_execution_results=real_read_only_execution_results,
        real_read_only_feedback_records=real_read_only_feedback_records,
    )

    real_read_only_repair_plan_linkage = (
        _real_read_only_repair_plan_linkage_summary(
            real_read_only_feedback_records=real_read_only_feedback_records,
            real_read_only_repair_plans=real_read_only_repair_plans,
        )
    )

    real_read_only_repair_action_bundle_linkage = (
        _real_read_only_repair_action_bundle_linkage_summary(
            real_read_only_repair_plans=real_read_only_repair_plans,
            real_read_only_repair_action_bundles=(
                real_read_only_repair_action_bundles
            ),
        )
    )

    real_read_only_repair_action_bundle_review_linkage = (
        _real_read_only_repair_action_bundle_review_linkage_summary(
            real_read_only_repair_action_bundles=(
                real_read_only_repair_action_bundles
            ),
            real_read_only_repair_action_bundle_reviews=(
                real_read_only_repair_action_bundle_reviews
            ),
        )
    )

    real_repair_approval_linkage = _real_repair_approval_linkage_summary(
        real_read_only_repair_action_bundle_reviews=(
            real_read_only_repair_action_bundle_reviews
        ),
        real_repair_approvals=real_repair_approvals,
    )

    real_repair_approval_transition_linkage = (
        _real_repair_approval_transition_linkage_summary(
            real_repair_approvals=real_repair_approvals,
            real_repair_approval_transitions=real_repair_approval_transitions,
        )
    )

    real_repair_final_gate_linkage = _real_repair_final_gate_linkage_summary(
        real_repair_approval_transitions=real_repair_approval_transitions,
        real_repair_final_gates=real_repair_final_gates,
    )

    real_repair_dry_run_envelope_linkage = (
        _real_repair_dry_run_envelope_linkage_summary(
            real_repair_final_gates=real_repair_final_gates,
            real_repair_dry_run_envelopes=real_repair_dry_run_envelopes,
        )
    )

    real_repair_noop_result_linkage = _real_repair_noop_result_linkage_summary(
        real_repair_dry_run_envelopes=real_repair_dry_run_envelopes,
        real_repair_noop_results=real_repair_noop_results,
    )

    real_repair_noop_feedback_linkage = _real_repair_noop_feedback_linkage_summary(
        real_repair_noop_results=real_repair_noop_results,
        real_repair_noop_feedback_records=real_repair_noop_feedback_records,
    )

    real_repair_readiness_gate_linkage = (
        _real_repair_readiness_gate_linkage_summary(
            real_repair_noop_feedback_records=real_repair_noop_feedback_records,
            real_repair_readiness_gates=real_repair_readiness_gates,
        )
    )

    guarded_repair_execution_linkage = _guarded_repair_execution_linkage_summary(
        real_repair_readiness_gates=real_repair_readiness_gates,
        guarded_repair_execution_results=guarded_repair_execution_results,
    )

    post_repair_evidence_linkage = _post_repair_evidence_linkage_summary(
        guarded_repair_execution_results=guarded_repair_execution_results,
        post_repair_evidence_checks=post_repair_evidence_checks,
    )

    real_execution_adapter_contract_linkage = (
        _real_execution_adapter_contract_linkage_summary(
            post_repair_evidence_checks=post_repair_evidence_checks,
            real_execution_adapter_contracts=real_execution_adapter_contracts,
        )
    )

    real_execution_adapter_request_schema_linkage = (
        _real_execution_adapter_request_schema_linkage_summary(
            real_execution_adapter_contracts=real_execution_adapter_contracts,
            real_execution_adapter_request_schemas=real_execution_adapter_request_schemas,
        )
    )

    real_execution_capability_policy_matrix_linkage = (
        _real_execution_capability_policy_matrix_linkage_summary(
            real_execution_adapter_request_schemas=real_execution_adapter_request_schemas,
            real_execution_capability_policy_matrices=real_execution_capability_policy_matrices,
        )
    )

    real_execution_sandbox_adapter_scaffold_linkage = (
        _real_execution_sandbox_adapter_scaffold_linkage_summary(
            real_execution_capability_policy_matrices=(
                real_execution_capability_policy_matrices
            ),
            real_execution_sandbox_adapter_scaffolds=(
                real_execution_sandbox_adapter_scaffolds
            ),
        )
    )

    real_execution_sandbox_adapter_request_preflight_linkage = (
        _real_execution_sandbox_adapter_request_preflight_linkage_summary(
            real_execution_sandbox_adapter_scaffolds=(
                real_execution_sandbox_adapter_scaffolds
            ),
            real_execution_sandbox_adapter_request_preflights=(
                real_execution_sandbox_adapter_request_preflights
            ),
        )
    )

    real_execution_sandbox_request_envelope_scaffold_linkage = (
        _real_execution_sandbox_request_envelope_scaffold_linkage_summary(
            real_execution_sandbox_adapter_request_preflights=(
                real_execution_sandbox_adapter_request_preflights
            ),
            real_execution_sandbox_request_envelope_scaffolds=(
                real_execution_sandbox_request_envelope_scaffolds
            ),
        )
    )

    real_execution_sandbox_materialization_preflight_scaffold_linkage = (
        _real_execution_sandbox_materialization_preflight_scaffold_linkage_summary(
            real_execution_sandbox_request_envelope_scaffolds=(
                real_execution_sandbox_request_envelope_scaffolds
            ),
            real_execution_sandbox_materialization_preflight_scaffolds=(
                real_execution_sandbox_materialization_preflight_scaffolds
            ),
        )
    )

    real_execution_sandbox_workspace_plan_scaffold_linkage = (
        _real_execution_sandbox_workspace_plan_scaffold_linkage_summary(
            real_execution_sandbox_materialization_preflight_scaffolds=(
                real_execution_sandbox_materialization_preflight_scaffolds
            ),
            real_execution_sandbox_workspace_plan_scaffolds=(
                real_execution_sandbox_workspace_plan_scaffolds
            ),
        )
    )

    return {
        "type": "retry_governance_trail_summary",
        "total_records": len(trail_records),
        "filters": {
            "proposal_id": clean_proposal_id or None,
            "approval_id": clean_approval_id or None,
            "plan_id": clean_plan_id or None,
        },
        "by_type": dict(by_type),
        "counts": {
            "proposals": len(proposals),
            "approvals": len(approvals),
            "plans": len(plans),
            "rendered_commands": len(rendered_commands),
            "rendered_command_results": len(rendered_command_results),
            "eligibilities": len(eligibilities),
            "controlled_execution_results": len(controlled_execution_results),
            "mock_execution_summaries": len(mock_execution_summaries),
            "real_execution_preflights": len(real_preflights),
            "real_execution_approvals": len(real_approvals),
            "real_execution_approval_transitions": len(real_approval_transitions),
            "real_execution_final_gates": len(real_final_gates),
            "real_execution_dry_run_envelopes": len(real_dry_run_envelopes),
            "real_execution_noop_results": len(real_noop_results),
            "real_execution_read_only_promotions": len(real_read_only_promotions),
            "real_execution_read_only_final_gates": len(real_read_only_final_gates),
            "real_execution_read_only_approvals": len(real_read_only_approvals),
            "real_execution_read_only_approval_transitions": len(
                real_read_only_approval_transitions
            ),
            "real_execution_read_only_readiness_gates": len(real_read_only_readiness_gates),
            "real_execution_read_only_execution_results": len(real_read_only_execution_results),
            "real_execution_read_only_feedback_records": len(real_read_only_feedback_records),
            "real_execution_read_only_repair_plans": len(real_read_only_repair_plans),
            "real_execution_read_only_repair_action_bundles": len(
                real_read_only_repair_action_bundles
            ),
            "real_execution_read_only_repair_action_bundle_reviews": len(
                real_read_only_repair_action_bundle_reviews
            ),
            "real_execution_repair_approvals": len(real_repair_approvals),
            "real_execution_repair_approval_transitions": len(
                real_repair_approval_transitions
            ),
            "real_execution_repair_final_gates": len(real_repair_final_gates),
            "real_execution_repair_dry_run_envelopes": len(real_repair_dry_run_envelopes),
            "real_execution_repair_noop_results": len(real_repair_noop_results),
            "real_execution_repair_noop_feedback_records": len(real_repair_noop_feedback_records),
            "real_execution_repair_readiness_gates": len(real_repair_readiness_gates),
            "guarded_repair_execution_results": len(guarded_repair_execution_results),
            "post_repair_evidence_checks": len(post_repair_evidence_checks),
            "real_execution_adapter_contracts": len(real_execution_adapter_contracts),
            "real_execution_adapter_request_schemas": len(real_execution_adapter_request_schemas),
            "real_execution_capability_policy_matrices": len(real_execution_capability_policy_matrices),
            "real_execution_sandbox_adapter_scaffolds": len(
                real_execution_sandbox_adapter_scaffolds
            ),
            "real_execution_sandbox_adapter_request_preflights": len(
                real_execution_sandbox_adapter_request_preflights
            ),
            "real_execution_sandbox_request_envelope_scaffolds": len(
                real_execution_sandbox_request_envelope_scaffolds
            ),
            "real_execution_sandbox_materialization_preflight_scaffolds": len(
                real_execution_sandbox_materialization_preflight_scaffolds
            ),
            "real_execution_sandbox_workspace_plan_scaffolds": len(
                real_execution_sandbox_workspace_plan_scaffolds
            ),
            "results": len(results),
        },
        "approval_statuses": dict(approval_statuses),
        "plan_statuses": dict(plan_statuses),
        "rendered_command_statuses": dict(rendered_command_statuses),
        "rendered_command_profiles": dict(rendered_command_profiles),
        "rendered_command_result_statuses": dict(rendered_command_result_statuses),
        "rendered_command_result_reasons": dict(rendered_command_result_reasons),
        "eligibility_statuses": dict(eligibility_statuses),
        "eligibility_reasons": dict(eligibility_reasons),
        "controlled_execution_result_statuses": dict(
            controlled_execution_result_statuses
        ),
        "controlled_execution_result_reasons": dict(
            controlled_execution_result_reasons
        ),
        "extended_controlled_execution_observed": bool(controlled_execution_results),
        "result_statuses": dict(result_statuses),
        "result_reasons": dict(result_reasons),
        "decision_modes": dict(decision_modes),
        "chain_ids": chain_ids,
        "chain_complete": not missing_stages,
        "missing_stages": missing_stages,
        "controlled_command_parse_valid": dict(controlled_command_parse_valid),
        "controlled_command_parse_allowlist_matched": dict(
            controlled_command_parse_allowlist_matched
        ),
        "controlled_command_parse_execution_performed": dict(
            controlled_command_parse_execution_performed
        ),
        "controlled_execution_operator_authorized": dict(
            controlled_execution_operator_authorized
        ),
        "controlled_gate_statuses": dict(controlled_gate_statuses),
        "controlled_gate_would_execute": dict(controlled_gate_would_execute),
        "controlled_gate_would_execute_if_enabled": dict(
            controlled_gate_would_execute_if_enabled
        ),
        "controlled_gate_execution_performed": dict(
            controlled_gate_execution_performed
        ),
        "controlled_gate_reasons": dict(controlled_gate_reasons),
        "controlled_mock_statuses": dict(controlled_mock_statuses),
        "controlled_mock_reasons": dict(controlled_mock_reasons),
        "controlled_mock_performed": dict(controlled_mock_performed),
        "controlled_mock_subprocess_invoked": dict(
            controlled_mock_subprocess_invoked
        ),
        "mock_summary_statuses": dict(mock_summary_statuses),
        "mock_summary_reasons": dict(mock_summary_reasons),
        "mock_summary_performed": dict(mock_summary_performed),
        "mock_summary_subprocess_invoked": dict(mock_summary_subprocess_invoked),
        "controlled_mock_adapter": dict(controlled_mock_adapter),
        "controlled_mock_adapter_mode": dict(controlled_mock_adapter_mode),
        "controlled_mock_adapter_result_statuses": dict(
            controlled_mock_adapter_result_statuses
        ),
        "controlled_mock_adapter_subprocess_invoked": dict(
            controlled_mock_adapter_subprocess_invoked
        ),
        "controlled_mock_adapter_real_execution_enabled": dict(
            controlled_mock_adapter_real_execution_enabled
        ),
        "controlled_mock_adapter_payload_executed": dict(
            controlled_mock_adapter_payload_executed
        ),
        "controlled_real_execution_requested": dict(
            controlled_real_execution_requested
        ),
        "controlled_real_execution_performed": dict(
            controlled_real_execution_performed
        ),
        "controlled_real_execution_supported": dict(
            controlled_real_execution_supported
        ),
        "controlled_subprocess_invoked": dict(controlled_subprocess_invoked),
        "real_preflight_statuses": dict(real_preflight_statuses),
        "real_preflight_reasons": dict(real_preflight_reasons),
        "real_preflight_requested": dict(real_preflight_requested),
        "real_preflight_would_execute": dict(real_preflight_would_execute),
        "real_preflight_execution_performed": dict(
            real_preflight_execution_performed
        ),
        "real_preflight_subprocess_invoked": dict(
            real_preflight_subprocess_invoked
        ),
        "real_preflight_requires_explicit_pr": dict(
            real_preflight_requires_explicit_pr
        ),
        "real_approval_statuses": dict(real_approval_statuses),
        "real_approval_enabled": dict(real_approval_enabled),
        "real_approval_subprocess_enabled": dict(real_approval_subprocess_enabled),
        "real_approval_execution_performed": dict(real_approval_execution_performed),
        "real_approval_subprocess_invoked": dict(real_approval_subprocess_invoked),
        "real_linkage": real_linkage,
        "real_linkage_complete": bool(real_linkage.get("real_linkage_complete")),
        "real_preflight_controlled_matches": real_linkage.get(
            "real_preflight_controlled_matches", 0
        ),
        "real_preflight_rendered_matches": real_linkage.get(
            "real_preflight_rendered_matches", 0
        ),
        "real_preflight_orphans": real_linkage.get("real_preflight_orphans", 0),
        "real_approval_preflight_matches": real_linkage.get(
            "real_approval_preflight_matches", 0
        ),
        "real_approval_controlled_matches": real_linkage.get(
            "real_approval_controlled_matches", 0
        ),
        "real_approval_rendered_matches": real_linkage.get(
            "real_approval_rendered_matches", 0
        ),
        "real_approval_orphans": real_linkage.get("real_approval_orphans", 0),
        "real_approval_transition_statuses": dict(real_approval_transition_statuses),
        "real_approval_transition_enabled": dict(real_approval_transition_enabled),
        "real_approval_transition_subprocess_enabled": dict(
            real_approval_transition_subprocess_enabled
        ),
        "real_approval_transition_execution_performed": dict(
            real_approval_transition_execution_performed
        ),
        "real_approval_transition_subprocess_invoked": dict(
            real_approval_transition_subprocess_invoked
        ),
        "real_approval_latest_status": _real_approval_latest_status(
            real_approvals=real_approvals,
            real_approval_transitions=real_approval_transitions,
        ),
        "real_final_gate_statuses": dict(real_final_gate_statuses),
        "real_final_gate_would_execute": dict(real_final_gate_would_execute),
        "real_final_gate_ready": dict(real_final_gate_ready),
        "real_final_gate_real_execution_enabled": dict(
            real_final_gate_real_execution_enabled
        ),
        "real_final_gate_subprocess_enabled": dict(
            real_final_gate_subprocess_enabled
        ),
        "real_final_gate_execution_performed": dict(
            real_final_gate_execution_performed
        ),
        "real_final_gate_subprocess_invoked": dict(
            real_final_gate_subprocess_invoked
        ),
        "real_dry_run_envelope_dry_run_only": dict(
            real_dry_run_envelope_dry_run_only
        ),
        "real_dry_run_envelope_would_execute": dict(
            real_dry_run_envelope_would_execute
        ),
        "real_dry_run_envelope_ready": dict(real_dry_run_envelope_ready),
        "real_dry_run_envelope_real_execution_enabled": dict(
            real_dry_run_envelope_real_execution_enabled
        ),
        "real_dry_run_envelope_subprocess_enabled": dict(
            real_dry_run_envelope_subprocess_enabled
        ),
        "real_dry_run_envelope_execution_performed": dict(
            real_dry_run_envelope_execution_performed
        ),
        "real_dry_run_envelope_subprocess_invoked": dict(
            real_dry_run_envelope_subprocess_invoked
        ),
        "real_dry_run_linkage": real_dry_run_linkage,
        "real_dry_run_linkage_complete": bool(
            real_dry_run_linkage.get("real_dry_run_linkage_complete")
        ),
        "real_dry_run_envelope_final_gate_matches": real_dry_run_linkage.get(
            "real_dry_run_envelope_final_gate_matches", 0
        ),
        "real_dry_run_envelope_orphans": real_dry_run_linkage.get(
            "real_dry_run_envelope_orphans", 0
        ),
        "real_noop_result_noop_only": dict(real_noop_result_noop_only),
        "real_noop_result_rendered_command_executed": dict(
            real_noop_result_rendered_command_executed
        ),
        "real_noop_result_dry_run_command_executed": dict(
            real_noop_result_dry_run_command_executed
        ),
        "real_noop_result_real_execution_enabled": dict(
            real_noop_result_real_execution_enabled
        ),
        "real_noop_result_subprocess_invoked": dict(
            real_noop_result_subprocess_invoked
        ),
        "real_noop_result_execution_performed": dict(
            real_noop_result_execution_performed
        ),
        "real_noop_result_exit_codes": dict(real_noop_result_exit_codes),
        "real_noop_result_stdout_marker_observed": dict(
            real_noop_result_stdout_marker_observed
        ),
        "real_noop_linkage": real_noop_linkage,
        "real_noop_linkage_complete": bool(
            real_noop_linkage.get("real_noop_linkage_complete")
        ),
        "real_noop_result_dry_run_envelope_matches": real_noop_linkage.get(
            "real_noop_result_dry_run_envelope_matches", 0
        ),
        "real_noop_result_orphans": real_noop_linkage.get(
            "real_noop_result_orphans", 0
        ),
        "real_read_only_promotion_statuses": dict(
            real_read_only_promotion_statuses
        ),
        "real_read_only_promotion_candidates": dict(
            real_read_only_promotion_candidates
        ),
        "real_read_only_promotion_command_parse_valid": dict(
            real_read_only_promotion_command_parse_valid
        ),
        "real_read_only_promotion_stdout_marker_observed": dict(
            real_read_only_promotion_stdout_marker_observed
        ),
        "real_read_only_promotion_noop_exit_codes": dict(
            real_read_only_promotion_noop_exit_codes
        ),
        "real_read_only_promotion_rendered_command_executed": dict(
            real_read_only_promotion_rendered_command_executed
        ),
        "real_read_only_promotion_dry_run_command_executed": dict(
            real_read_only_promotion_dry_run_command_executed
        ),
        "real_read_only_promotion_real_execution_enabled": dict(
            real_read_only_promotion_real_execution_enabled
        ),
        "real_read_only_promotion_subprocess_invoked": dict(
            real_read_only_promotion_subprocess_invoked
        ),
        "real_read_only_promotion_execution_performed": dict(
            real_read_only_promotion_execution_performed
        ),
        "real_read_only_promotion_linkage": real_read_only_promotion_linkage,
        "real_read_only_promotion_linkage_complete": bool(
            real_read_only_promotion_linkage.get(
                "real_read_only_promotion_linkage_complete"
            )
        ),
        "real_read_only_promotion_noop_matches": (
            real_read_only_promotion_linkage.get(
                "real_read_only_promotion_noop_matches", 0
            )
        ),
        "real_read_only_promotion_orphans": (
            real_read_only_promotion_linkage.get(
                "real_read_only_promotion_orphans", 0
            )
        ),
        "real_read_only_final_gate_statuses": dict(
            real_read_only_final_gate_statuses
        ),
        "real_read_only_final_gate_preconditions_satisfied": dict(
            real_read_only_final_gate_preconditions_satisfied
        ),
        "real_read_only_final_gate_ready": dict(real_read_only_final_gate_ready),
        "real_read_only_final_gate_would_execute": dict(
            real_read_only_final_gate_would_execute
        ),
        "real_read_only_final_gate_read_only_execution_enabled": dict(
            real_read_only_final_gate_read_only_execution_enabled
        ),
        "real_read_only_final_gate_real_execution_enabled": dict(
            real_read_only_final_gate_real_execution_enabled
        ),
        "real_read_only_final_gate_subprocess_enabled": dict(
            real_read_only_final_gate_subprocess_enabled
        ),
        "real_read_only_final_gate_subprocess_invoked": dict(
            real_read_only_final_gate_subprocess_invoked
        ),
        "real_read_only_final_gate_execution_performed": dict(
            real_read_only_final_gate_execution_performed
        ),
        "real_read_only_final_gate_rendered_command_executed": dict(
            real_read_only_final_gate_rendered_command_executed
        ),
        "real_read_only_final_gate_dry_run_command_executed": dict(
            real_read_only_final_gate_dry_run_command_executed
        ),
        "real_read_only_final_gate_linkage": real_read_only_final_gate_linkage,
        "real_read_only_final_gate_linkage_complete": bool(
            real_read_only_final_gate_linkage.get(
                "real_read_only_final_gate_linkage_complete"
            )
        ),
        "real_read_only_final_gate_promotion_matches": (
            real_read_only_final_gate_linkage.get(
                "real_read_only_final_gate_promotion_matches", 0
            )
        ),
        "real_read_only_final_gate_orphans": (
            real_read_only_final_gate_linkage.get(
                "real_read_only_final_gate_orphans", 0
            )
        ),
        "real_read_only_approval_statuses": dict(
            real_read_only_approval_statuses
        ),
        "real_read_only_approval_read_only_execution_enabled": dict(
            real_read_only_approval_read_only_execution_enabled
        ),
        "real_read_only_approval_real_execution_enabled": dict(
            real_read_only_approval_real_execution_enabled
        ),
        "real_read_only_approval_subprocess_enabled": dict(
            real_read_only_approval_subprocess_enabled
        ),
        "real_read_only_approval_subprocess_invoked": dict(
            real_read_only_approval_subprocess_invoked
        ),
        "real_read_only_approval_execution_performed": dict(
            real_read_only_approval_execution_performed
        ),
        "real_read_only_approval_rendered_command_executed": dict(
            real_read_only_approval_rendered_command_executed
        ),
        "real_read_only_approval_dry_run_command_executed": dict(
            real_read_only_approval_dry_run_command_executed
        ),
        "real_read_only_approval_linkage": real_read_only_approval_linkage,
        "real_read_only_approval_linkage_complete": bool(
            real_read_only_approval_linkage.get(
                "real_read_only_approval_linkage_complete"
            )
        ),
        "real_read_only_approval_final_gate_matches": (
            real_read_only_approval_linkage.get(
                "real_read_only_approval_final_gate_matches", 0
            )
        ),
        "real_read_only_approval_orphans": (
            real_read_only_approval_linkage.get(
                "real_read_only_approval_orphans", 0
            )
        ),
        "real_read_only_approval_transition_from_statuses": dict(
            real_read_only_approval_transition_from_statuses
        ),
        "real_read_only_approval_transition_to_statuses": dict(
            real_read_only_approval_transition_to_statuses
        ),
        "real_read_only_approval_transition_read_only_execution_enabled": dict(
            real_read_only_approval_transition_read_only_execution_enabled
        ),
        "real_read_only_approval_transition_real_execution_enabled": dict(
            real_read_only_approval_transition_real_execution_enabled
        ),
        "real_read_only_approval_transition_subprocess_enabled": dict(
            real_read_only_approval_transition_subprocess_enabled
        ),
        "real_read_only_approval_transition_subprocess_invoked": dict(
            real_read_only_approval_transition_subprocess_invoked
        ),
        "real_read_only_approval_transition_execution_performed": dict(
            real_read_only_approval_transition_execution_performed
        ),
        "real_read_only_approval_transition_rendered_command_executed": dict(
            real_read_only_approval_transition_rendered_command_executed
        ),
        "real_read_only_approval_transition_dry_run_command_executed": dict(
            real_read_only_approval_transition_dry_run_command_executed
        ),
        "real_read_only_approval_latest_status": (
            _real_read_only_approval_latest_status(
                real_read_only_approvals=real_read_only_approvals,
                real_read_only_approval_transitions=(
                    real_read_only_approval_transitions
                ),
            )
        ),
        "real_read_only_approval_transition_linkage": (
            real_read_only_approval_transition_linkage
        ),
        "real_read_only_approval_transition_linkage_complete": bool(
            real_read_only_approval_transition_linkage.get(
                "real_read_only_approval_transition_linkage_complete"
            )
        ),
        "real_read_only_approval_transition_approval_matches": (
            real_read_only_approval_transition_linkage.get(
                "real_read_only_approval_transition_approval_matches", 0
            )
        ),
        "real_read_only_approval_transition_orphans": (
            real_read_only_approval_transition_linkage.get(
                "real_read_only_approval_transition_orphans", 0
            )
        ),
        "real_read_only_readiness_gate_statuses": dict(
            real_read_only_readiness_gate_statuses
        ),
        "real_read_only_readiness_gate_satisfied": dict(
            real_read_only_readiness_gate_satisfied
        ),
        "real_read_only_readiness_gate_ready": dict(
            real_read_only_readiness_gate_ready
        ),
        "real_read_only_readiness_gate_read_only_execution_enabled": dict(
            real_read_only_readiness_gate_read_only_execution_enabled
        ),
        "real_read_only_readiness_gate_real_execution_enabled": dict(
            real_read_only_readiness_gate_real_execution_enabled
        ),
        "real_read_only_readiness_gate_subprocess_enabled": dict(
            real_read_only_readiness_gate_subprocess_enabled
        ),
        "real_read_only_readiness_gate_subprocess_invoked": dict(
            real_read_only_readiness_gate_subprocess_invoked
        ),
        "real_read_only_readiness_gate_execution_performed": dict(
            real_read_only_readiness_gate_execution_performed
        ),
        "real_read_only_readiness_gate_rendered_command_executed": dict(
            real_read_only_readiness_gate_rendered_command_executed
        ),
        "real_read_only_readiness_gate_dry_run_command_executed": dict(
            real_read_only_readiness_gate_dry_run_command_executed
        ),
        "real_read_only_readiness_gate_linkage": (
            real_read_only_readiness_gate_linkage
        ),
        "real_read_only_readiness_gate_linkage_complete": bool(
            real_read_only_readiness_gate_linkage.get(
                "real_read_only_readiness_gate_linkage_complete"
            )
        ),
        "real_read_only_readiness_gate_transition_matches": (
            real_read_only_readiness_gate_linkage.get(
                "real_read_only_readiness_gate_transition_matches", 0
            )
        ),
        "real_read_only_readiness_gate_orphans": (
            real_read_only_readiness_gate_linkage.get(
                "real_read_only_readiness_gate_orphans", 0
            )
        ),
        "real_read_only_execution_result_statuses": dict(
            real_read_only_execution_result_statuses
        ),
        "real_read_only_execution_result_reasons": dict(
            real_read_only_execution_result_reasons
        ),
        "real_read_only_execution_result_exit_codes": dict(
            real_read_only_execution_result_exit_codes
        ),
        "real_read_only_execution_result_validation_reasons_empty": dict(
            real_read_only_execution_result_validation_reasons_empty
        ),
        "real_read_only_execution_result_operator_authorized": dict(
            real_read_only_execution_result_operator_authorized
        ),
        "real_read_only_execution_result_allow_guarded": dict(
            real_read_only_execution_result_allow_guarded
        ),
        "real_read_only_execution_result_read_only_execution_enabled": dict(
            real_read_only_execution_result_read_only_execution_enabled
        ),
        "real_read_only_execution_result_real_execution_enabled": dict(
            real_read_only_execution_result_real_execution_enabled
        ),
        "real_read_only_execution_result_subprocess_enabled": dict(
            real_read_only_execution_result_subprocess_enabled
        ),
        "real_read_only_execution_result_subprocess_invoked": dict(
            real_read_only_execution_result_subprocess_invoked
        ),
        "real_read_only_execution_result_execution_performed": dict(
            real_read_only_execution_result_execution_performed
        ),
        "real_read_only_execution_result_read_only_command_executed": dict(
            real_read_only_execution_result_read_only_command_executed
        ),
        "real_read_only_execution_result_rendered_command_executed": dict(
            real_read_only_execution_result_rendered_command_executed
        ),
        "real_read_only_execution_result_dry_run_command_executed": dict(
            real_read_only_execution_result_dry_run_command_executed
        ),
        "real_read_only_execution_result_linkage": (
            real_read_only_execution_result_linkage
        ),
        "real_read_only_execution_result_linkage_complete": bool(
            real_read_only_execution_result_linkage.get(
                "real_read_only_execution_result_linkage_complete"
            )
        ),
        "real_read_only_execution_result_gate_matches": (
            real_read_only_execution_result_linkage.get(
                "real_read_only_execution_result_gate_matches", 0
            )
        ),
        "real_read_only_execution_result_orphans": (
            real_read_only_execution_result_linkage.get(
                "real_read_only_execution_result_orphans", 0
            )
        ),
        "real_read_only_feedback_statuses": dict(
            real_read_only_feedback_statuses
        ),
        "real_read_only_feedback_source_statuses": dict(
            real_read_only_feedback_source_statuses
        ),
        "real_read_only_feedback_source_exit_codes": dict(
            real_read_only_feedback_source_exit_codes
        ),
        "real_read_only_feedback_next_actions": dict(
            real_read_only_feedback_next_actions
        ),
        "real_read_only_feedback_execution_observed": dict(
            real_read_only_feedback_execution_observed
        ),
        "real_read_only_feedback_failed": dict(real_read_only_feedback_failed),
        "real_read_only_feedback_succeeded": dict(
            real_read_only_feedback_succeeded
        ),
        "real_read_only_feedback_rejected": dict(real_read_only_feedback_rejected),
        "real_read_only_feedback_real_execution_enabled": dict(
            real_read_only_feedback_real_execution_enabled
        ),
        "real_read_only_feedback_feedback_execution_performed": dict(
            real_read_only_feedback_feedback_execution_performed
        ),
        "real_read_only_feedback_feedback_subprocess_invoked": dict(
            real_read_only_feedback_feedback_subprocess_invoked
        ),
        "real_read_only_feedback_execution_performed": dict(
            real_read_only_feedback_execution_performed
        ),
        "real_read_only_feedback_subprocess_invoked": dict(
            real_read_only_feedback_subprocess_invoked
        ),
        "real_read_only_feedback_linkage": real_read_only_feedback_linkage,
        "real_read_only_feedback_linkage_complete": bool(
            real_read_only_feedback_linkage.get(
                "real_read_only_feedback_linkage_complete"
            )
        ),
        "real_read_only_feedback_result_matches": (
            real_read_only_feedback_linkage.get(
                "real_read_only_feedback_result_matches", 0
            )
        ),
        "real_read_only_feedback_orphans": (
            real_read_only_feedback_linkage.get(
                "real_read_only_feedback_orphans", 0
            )
        ),
        "real_read_only_repair_plan_statuses": dict(
            real_read_only_repair_plan_statuses
        ),
        "real_read_only_repair_plan_source_feedback_statuses": dict(
            real_read_only_repair_plan_source_feedback_statuses
        ),
        "real_read_only_repair_plan_source_statuses": dict(
            real_read_only_repair_plan_source_statuses
        ),
        "real_read_only_repair_plan_source_exit_codes": dict(
            real_read_only_repair_plan_source_exit_codes
        ),
        "real_read_only_repair_plan_next_actions": dict(
            real_read_only_repair_plan_next_actions
        ),
        "real_read_only_repair_plan_item_counts": dict(
            real_read_only_repair_plan_item_counts
        ),
        "real_read_only_repair_plan_requires_operator_review": dict(
            real_read_only_repair_plan_requires_operator_review
        ),
        "real_read_only_repair_plan_repair_execution_enabled": dict(
            real_read_only_repair_plan_repair_execution_enabled
        ),
        "real_read_only_repair_plan_real_execution_enabled": dict(
            real_read_only_repair_plan_real_execution_enabled
        ),
        "real_read_only_repair_plan_subprocess_enabled": dict(
            real_read_only_repair_plan_subprocess_enabled
        ),
        "real_read_only_repair_plan_repair_execution_performed": dict(
            real_read_only_repair_plan_repair_execution_performed
        ),
        "real_read_only_repair_plan_repair_subprocess_invoked": dict(
            real_read_only_repair_plan_repair_subprocess_invoked
        ),
        "real_read_only_repair_plan_execution_performed": dict(
            real_read_only_repair_plan_execution_performed
        ),
        "real_read_only_repair_plan_subprocess_invoked": dict(
            real_read_only_repair_plan_subprocess_invoked
        ),
        "real_read_only_repair_plan_linkage": real_read_only_repair_plan_linkage,
        "real_read_only_repair_plan_linkage_complete": bool(
            real_read_only_repair_plan_linkage.get(
                "real_read_only_repair_plan_linkage_complete"
            )
        ),
        "real_read_only_repair_plan_feedback_matches": (
            real_read_only_repair_plan_linkage.get(
                "real_read_only_repair_plan_feedback_matches", 0
            )
        ),
        "real_read_only_repair_plan_orphans": (
            real_read_only_repair_plan_linkage.get(
                "real_read_only_repair_plan_orphans", 0
            )
        ),
        "real_read_only_repair_action_bundle_statuses": dict(
            real_read_only_repair_action_bundle_statuses
        ),
        "real_read_only_repair_action_bundle_source_plan_statuses": dict(
            real_read_only_repair_action_bundle_source_plan_statuses
        ),
        "real_read_only_repair_action_bundle_source_feedback_statuses": dict(
            real_read_only_repair_action_bundle_source_feedback_statuses
        ),
        "real_read_only_repair_action_bundle_source_statuses": dict(
            real_read_only_repair_action_bundle_source_statuses
        ),
        "real_read_only_repair_action_bundle_source_exit_codes": dict(
            real_read_only_repair_action_bundle_source_exit_codes
        ),
        "real_read_only_repair_action_bundle_next_actions": dict(
            real_read_only_repair_action_bundle_next_actions
        ),
        "real_read_only_repair_action_bundle_item_counts": dict(
            real_read_only_repair_action_bundle_item_counts
        ),
        "real_read_only_repair_action_bundle_source_item_counts": dict(
            real_read_only_repair_action_bundle_source_item_counts
        ),
        "real_read_only_repair_action_bundle_requires_operator_review": dict(
            real_read_only_repair_action_bundle_requires_operator_review
        ),
        "real_read_only_repair_action_bundle_reviewed": dict(
            real_read_only_repair_action_bundle_reviewed
        ),
        "real_read_only_repair_action_bundle_bundle_execution_enabled": dict(
            real_read_only_repair_action_bundle_bundle_execution_enabled
        ),
        "real_read_only_repair_action_bundle_repair_execution_enabled": dict(
            real_read_only_repair_action_bundle_repair_execution_enabled
        ),
        "real_read_only_repair_action_bundle_real_execution_enabled": dict(
            real_read_only_repair_action_bundle_real_execution_enabled
        ),
        "real_read_only_repair_action_bundle_subprocess_enabled": dict(
            real_read_only_repair_action_bundle_subprocess_enabled
        ),
        "real_read_only_repair_action_bundle_bundle_execution_performed": dict(
            real_read_only_repair_action_bundle_bundle_execution_performed
        ),
        "real_read_only_repair_action_bundle_bundle_subprocess_invoked": dict(
            real_read_only_repair_action_bundle_bundle_subprocess_invoked
        ),
        "real_read_only_repair_action_bundle_repair_execution_performed": dict(
            real_read_only_repair_action_bundle_repair_execution_performed
        ),
        "real_read_only_repair_action_bundle_repair_subprocess_invoked": dict(
            real_read_only_repair_action_bundle_repair_subprocess_invoked
        ),
        "real_read_only_repair_action_bundle_execution_performed": dict(
            real_read_only_repair_action_bundle_execution_performed
        ),
        "real_read_only_repair_action_bundle_subprocess_invoked": dict(
            real_read_only_repair_action_bundle_subprocess_invoked
        ),
        "real_read_only_repair_action_bundle_linkage": (
            real_read_only_repair_action_bundle_linkage
        ),
        "real_read_only_repair_action_bundle_linkage_complete": bool(
            real_read_only_repair_action_bundle_linkage.get(
                "real_read_only_repair_action_bundle_linkage_complete"
            )
        ),
        "real_read_only_repair_action_bundle_plan_matches": (
            real_read_only_repair_action_bundle_linkage.get(
                "real_read_only_repair_action_bundle_plan_matches", 0
            )
        ),
        "real_read_only_repair_action_bundle_orphans": (
            real_read_only_repair_action_bundle_linkage.get(
                "real_read_only_repair_action_bundle_orphans", 0
            )
        ),
        "real_read_only_repair_action_bundle_review_statuses": dict(
            real_read_only_repair_action_bundle_review_statuses
        ),
        "real_read_only_repair_action_bundle_review_source_bundle_statuses": dict(
            real_read_only_repair_action_bundle_review_source_bundle_statuses
        ),
        "real_read_only_repair_action_bundle_review_source_plan_statuses": dict(
            real_read_only_repair_action_bundle_review_source_plan_statuses
        ),
        "real_read_only_repair_action_bundle_review_source_feedback_statuses": dict(
            real_read_only_repair_action_bundle_review_source_feedback_statuses
        ),
        "real_read_only_repair_action_bundle_review_source_statuses": dict(
            real_read_only_repair_action_bundle_review_source_statuses
        ),
        "real_read_only_repair_action_bundle_review_source_exit_codes": dict(
            real_read_only_repair_action_bundle_review_source_exit_codes
        ),
        "real_read_only_repair_action_bundle_review_source_item_counts": dict(
            real_read_only_repair_action_bundle_review_source_item_counts
        ),
        "real_read_only_repair_action_bundle_review_next_actions": dict(
            real_read_only_repair_action_bundle_review_next_actions
        ),
        "real_read_only_repair_action_bundle_review_operator_authorized": dict(
            real_read_only_repair_action_bundle_review_operator_authorized
        ),
        "real_read_only_repair_action_bundle_review_requires_operator_review": dict(
            real_read_only_repair_action_bundle_review_requires_operator_review
        ),
        "real_read_only_repair_action_bundle_review_reviewed": dict(
            real_read_only_repair_action_bundle_review_reviewed
        ),
        "real_read_only_repair_action_bundle_review_approved": dict(
            real_read_only_repair_action_bundle_review_approved
        ),
        "real_read_only_repair_action_bundle_review_rejected": dict(
            real_read_only_repair_action_bundle_review_rejected
        ),
        "real_read_only_repair_action_bundle_review_bundle_execution_enabled": dict(
            real_read_only_repair_action_bundle_review_bundle_execution_enabled
        ),
        "real_read_only_repair_action_bundle_review_repair_execution_enabled": dict(
            real_read_only_repair_action_bundle_review_repair_execution_enabled
        ),
        "real_read_only_repair_action_bundle_review_real_execution_enabled": dict(
            real_read_only_repair_action_bundle_review_real_execution_enabled
        ),
        "real_read_only_repair_action_bundle_review_subprocess_enabled": dict(
            real_read_only_repair_action_bundle_review_subprocess_enabled
        ),
        "real_read_only_repair_action_bundle_review_bundle_execution_performed": dict(
            real_read_only_repair_action_bundle_review_bundle_execution_performed
        ),
        "real_read_only_repair_action_bundle_review_bundle_subprocess_invoked": dict(
            real_read_only_repair_action_bundle_review_bundle_subprocess_invoked
        ),
        "real_read_only_repair_action_bundle_review_repair_execution_performed": dict(
            real_read_only_repair_action_bundle_review_repair_execution_performed
        ),
        "real_read_only_repair_action_bundle_review_repair_subprocess_invoked": dict(
            real_read_only_repair_action_bundle_review_repair_subprocess_invoked
        ),
        "real_read_only_repair_action_bundle_review_execution_performed": dict(
            real_read_only_repair_action_bundle_review_execution_performed
        ),
        "real_read_only_repair_action_bundle_review_subprocess_invoked": dict(
            real_read_only_repair_action_bundle_review_subprocess_invoked
        ),
        "real_read_only_repair_action_bundle_review_linkage": (
            real_read_only_repair_action_bundle_review_linkage
        ),
        "real_read_only_repair_action_bundle_review_linkage_complete": bool(
            real_read_only_repair_action_bundle_review_linkage.get(
                "real_read_only_repair_action_bundle_review_linkage_complete"
            )
        ),
        "real_read_only_repair_action_bundle_review_bundle_matches": (
            real_read_only_repair_action_bundle_review_linkage.get(
                "real_read_only_repair_action_bundle_review_bundle_matches", 0
            )
        ),
        "real_read_only_repair_action_bundle_review_orphans": (
            real_read_only_repair_action_bundle_review_linkage.get(
                "real_read_only_repair_action_bundle_review_orphans", 0
            )
        ),
        "real_repair_approval_statuses": dict(real_repair_approval_statuses),
        "real_repair_approval_source_review_statuses": dict(
            real_repair_approval_source_review_statuses
        ),
        "real_repair_approval_source_bundle_statuses": dict(
            real_repair_approval_source_bundle_statuses
        ),
        "real_repair_approval_next_actions": dict(real_repair_approval_next_actions),
        "real_repair_approval_operator_authorized": dict(
            real_repair_approval_operator_authorized
        ),
        "real_repair_approval_required": dict(real_repair_approval_required),
        "real_repair_approval_approved": dict(real_repair_approval_approved),
        "real_repair_approval_rejected": dict(real_repair_approval_rejected),
        "real_repair_approval_repair_execution_enabled": dict(
            real_repair_approval_repair_execution_enabled
        ),
        "real_repair_approval_real_execution_enabled": dict(
            real_repair_approval_real_execution_enabled
        ),
        "real_repair_approval_subprocess_enabled": dict(
            real_repair_approval_subprocess_enabled
        ),
        "real_repair_approval_repair_execution_performed": dict(
            real_repair_approval_repair_execution_performed
        ),
        "real_repair_approval_repair_subprocess_invoked": dict(
            real_repair_approval_repair_subprocess_invoked
        ),
        "real_repair_approval_execution_performed": dict(
            real_repair_approval_execution_performed
        ),
        "real_repair_approval_subprocess_invoked": dict(
            real_repair_approval_subprocess_invoked
        ),
        "real_repair_approval_linkage": real_repair_approval_linkage,
        "real_repair_approval_linkage_complete": bool(
            real_repair_approval_linkage.get("real_repair_approval_linkage_complete")
        ),
        "real_repair_approval_review_matches": real_repair_approval_linkage.get(
            "real_repair_approval_review_matches", 0
        ),
        "real_repair_approval_orphans": real_repair_approval_linkage.get(
            "real_repair_approval_orphans", 0
        ),
        "real_repair_approval_transition_from_statuses": dict(
            real_repair_approval_transition_from_statuses
        ),
        "real_repair_approval_transition_to_statuses": dict(
            real_repair_approval_transition_to_statuses
        ),
        "real_repair_approval_transition_source_approval_statuses": dict(
            real_repair_approval_transition_source_approval_statuses
        ),
        "real_repair_approval_transition_source_review_statuses": dict(
            real_repair_approval_transition_source_review_statuses
        ),
        "real_repair_approval_transition_next_actions": dict(
            real_repair_approval_transition_next_actions
        ),
        "real_repair_approval_transition_operator_authorized": dict(
            real_repair_approval_transition_operator_authorized
        ),
        "real_repair_approval_transition_required": dict(
            real_repair_approval_transition_required
        ),
        "real_repair_approval_transition_approved": dict(
            real_repair_approval_transition_approved
        ),
        "real_repair_approval_transition_rejected": dict(
            real_repair_approval_transition_rejected
        ),
        "real_repair_approval_transition_repair_execution_enabled": dict(
            real_repair_approval_transition_repair_execution_enabled
        ),
        "real_repair_approval_transition_real_execution_enabled": dict(
            real_repair_approval_transition_real_execution_enabled
        ),
        "real_repair_approval_transition_subprocess_enabled": dict(
            real_repair_approval_transition_subprocess_enabled
        ),
        "real_repair_approval_transition_repair_execution_performed": dict(
            real_repair_approval_transition_repair_execution_performed
        ),
        "real_repair_approval_transition_repair_subprocess_invoked": dict(
            real_repair_approval_transition_repair_subprocess_invoked
        ),
        "real_repair_approval_transition_execution_performed": dict(
            real_repair_approval_transition_execution_performed
        ),
        "real_repair_approval_transition_subprocess_invoked": dict(
            real_repair_approval_transition_subprocess_invoked
        ),
        "real_repair_approval_transition_linkage": (
            real_repair_approval_transition_linkage
        ),
        "real_repair_approval_transition_linkage_complete": bool(
            real_repair_approval_transition_linkage.get(
                "real_repair_approval_transition_linkage_complete"
            )
        ),
        "real_repair_approval_transition_approval_matches": (
            real_repair_approval_transition_linkage.get(
                "real_repair_approval_transition_approval_matches", 0
            )
        ),
        "real_repair_approval_transition_orphans": (
            real_repair_approval_transition_linkage.get(
                "real_repair_approval_transition_orphans", 0
            )
        ),
        "real_repair_final_gate_statuses": dict(real_repair_final_gate_statuses),
        "real_repair_final_gate_preconditions_satisfied": dict(
            real_repair_final_gate_preconditions_satisfied
        ),
        "real_repair_final_gate_ready": dict(real_repair_final_gate_ready),
        "real_repair_final_gate_would_execute": dict(
            real_repair_final_gate_would_execute
        ),
        "real_repair_final_gate_next_actions": dict(
            real_repair_final_gate_next_actions
        ),
        "real_repair_final_gate_operator_authorized": dict(
            real_repair_final_gate_operator_authorized
        ),
        "real_repair_final_gate_transition_approved": dict(
            real_repair_final_gate_transition_approved
        ),
        "real_repair_final_gate_repair_execution_enabled": dict(
            real_repair_final_gate_repair_execution_enabled
        ),
        "real_repair_final_gate_real_execution_enabled": dict(
            real_repair_final_gate_real_execution_enabled
        ),
        "real_repair_final_gate_subprocess_enabled": dict(
            real_repair_final_gate_subprocess_enabled
        ),
        "real_repair_final_gate_repair_execution_performed": dict(
            real_repair_final_gate_repair_execution_performed
        ),
        "real_repair_final_gate_repair_subprocess_invoked": dict(
            real_repair_final_gate_repair_subprocess_invoked
        ),
        "real_repair_final_gate_execution_performed": dict(
            real_repair_final_gate_execution_performed
        ),
        "real_repair_final_gate_subprocess_invoked": dict(
            real_repair_final_gate_subprocess_invoked
        ),
        "real_repair_final_gate_linkage": real_repair_final_gate_linkage,
        "real_repair_final_gate_linkage_complete": bool(
            real_repair_final_gate_linkage.get(
                "real_repair_final_gate_linkage_complete"
            )
        ),
        "real_repair_final_gate_transition_matches": (
            real_repair_final_gate_linkage.get(
                "real_repair_final_gate_transition_matches", 0
            )
        ),
        "real_repair_final_gate_orphans": real_repair_final_gate_linkage.get(
            "real_repair_final_gate_orphans", 0
        ),
        "real_repair_dry_run_envelope_statuses": dict(
            real_repair_dry_run_envelope_statuses
        ),
        "real_repair_dry_run_envelope_dry_run_only": dict(
            real_repair_dry_run_envelope_dry_run_only
        ),
        "real_repair_dry_run_envelope_modes": dict(
            real_repair_dry_run_envelope_modes
        ),
        "real_repair_dry_run_envelope_target_counts": dict(
            real_repair_dry_run_envelope_target_counts
        ),
        "real_repair_dry_run_envelope_source_gate_statuses": dict(
            real_repair_dry_run_envelope_source_gate_statuses
        ),
        "real_repair_dry_run_envelope_next_actions": dict(
            real_repair_dry_run_envelope_next_actions
        ),
        "real_repair_dry_run_envelope_operator_authorized": dict(
            real_repair_dry_run_envelope_operator_authorized
        ),
        "real_repair_dry_run_envelope_ready": dict(
            real_repair_dry_run_envelope_ready
        ),
        "real_repair_dry_run_envelope_would_execute": dict(
            real_repair_dry_run_envelope_would_execute
        ),
        "real_repair_dry_run_envelope_repair_execution_enabled": dict(
            real_repair_dry_run_envelope_repair_execution_enabled
        ),
        "real_repair_dry_run_envelope_real_execution_enabled": dict(
            real_repair_dry_run_envelope_real_execution_enabled
        ),
        "real_repair_dry_run_envelope_subprocess_enabled": dict(
            real_repair_dry_run_envelope_subprocess_enabled
        ),
        "real_repair_dry_run_envelope_repair_execution_performed": dict(
            real_repair_dry_run_envelope_repair_execution_performed
        ),
        "real_repair_dry_run_envelope_repair_subprocess_invoked": dict(
            real_repair_dry_run_envelope_repair_subprocess_invoked
        ),
        "real_repair_dry_run_envelope_execution_performed": dict(
            real_repair_dry_run_envelope_execution_performed
        ),
        "real_repair_dry_run_envelope_subprocess_invoked": dict(
            real_repair_dry_run_envelope_subprocess_invoked
        ),
        "real_repair_dry_run_envelope_linkage": (
            real_repair_dry_run_envelope_linkage
        ),
        "real_repair_dry_run_envelope_linkage_complete": bool(
            real_repair_dry_run_envelope_linkage.get(
                "real_repair_dry_run_envelope_linkage_complete"
            )
        ),
        "real_repair_dry_run_envelope_final_gate_matches": (
            real_repair_dry_run_envelope_linkage.get(
                "real_repair_dry_run_envelope_final_gate_matches", 0
            )
        ),
        "real_repair_dry_run_envelope_orphans": (
            real_repair_dry_run_envelope_linkage.get(
                "real_repair_dry_run_envelope_orphans", 0
            )
        ),
        "real_repair_noop_result_statuses": dict(
            real_repair_noop_result_statuses
        ),
        "real_repair_noop_result_exit_codes": dict(
            real_repair_noop_result_exit_codes
        ),
        "real_repair_noop_result_noop_only": dict(
            real_repair_noop_result_noop_only
        ),
        "real_repair_noop_result_stdout_marker_observed": dict(
            real_repair_noop_result_stdout_marker_observed
        ),
        "real_repair_noop_result_source_envelope_statuses": dict(
            real_repair_noop_result_source_envelope_statuses
        ),
        "real_repair_noop_result_source_target_counts": dict(
            real_repair_noop_result_source_target_counts
        ),
        "real_repair_noop_result_next_actions": dict(
            real_repair_noop_result_next_actions
        ),
        "real_repair_noop_result_operator_authorized": dict(
            real_repair_noop_result_operator_authorized
        ),
        "real_repair_noop_result_repair_actions_executed": dict(
            real_repair_noop_result_repair_actions_executed
        ),
        "real_repair_noop_result_repair_bundle_executed": dict(
            real_repair_noop_result_repair_bundle_executed
        ),
        "real_repair_noop_result_repair_command_executed": dict(
            real_repair_noop_result_repair_command_executed
        ),
        "real_repair_noop_result_rendered_command_executed": dict(
            real_repair_noop_result_rendered_command_executed
        ),
        "real_repair_noop_result_dry_run_command_executed": dict(
            real_repair_noop_result_dry_run_command_executed
        ),
        "real_repair_noop_result_repair_execution_enabled": dict(
            real_repair_noop_result_repair_execution_enabled
        ),
        "real_repair_noop_result_real_execution_enabled": dict(
            real_repair_noop_result_real_execution_enabled
        ),
        "real_repair_noop_result_subprocess_enabled": dict(
            real_repair_noop_result_subprocess_enabled
        ),
        "real_repair_noop_result_repair_execution_performed": dict(
            real_repair_noop_result_repair_execution_performed
        ),
        "real_repair_noop_result_repair_subprocess_invoked": dict(
            real_repair_noop_result_repair_subprocess_invoked
        ),
        "real_repair_noop_result_execution_performed": dict(
            real_repair_noop_result_execution_performed
        ),
        "real_repair_noop_result_subprocess_invoked": dict(
            real_repair_noop_result_subprocess_invoked
        ),
        "real_repair_noop_result_linkage": real_repair_noop_result_linkage,
        "real_repair_noop_result_linkage_complete": bool(
            real_repair_noop_result_linkage.get(
                "real_repair_noop_result_linkage_complete"
            )
        ),
        "real_repair_noop_result_envelope_matches": (
            real_repair_noop_result_linkage.get(
                "real_repair_noop_result_envelope_matches", 0
            )
        ),
        "real_repair_noop_result_orphans": real_repair_noop_result_linkage.get(
            "real_repair_noop_result_orphans", 0
        ),
        "real_repair_noop_feedback_statuses": dict(
            real_repair_noop_feedback_statuses
        ),
        "real_repair_noop_feedback_verified": dict(
            real_repair_noop_feedback_verified
        ),
        "real_repair_noop_feedback_path_can_proceed": dict(
            real_repair_noop_feedback_path_can_proceed
        ),
        "real_repair_noop_feedback_next_gate_allowed": dict(
            real_repair_noop_feedback_next_gate_allowed
        ),
        "real_repair_noop_feedback_next_actions": dict(
            real_repair_noop_feedback_next_actions
        ),
        "real_repair_noop_feedback_source_noop_statuses": dict(
            real_repair_noop_feedback_source_noop_statuses
        ),
        "real_repair_noop_feedback_source_exit_codes": dict(
            real_repair_noop_feedback_source_exit_codes
        ),
        "real_repair_noop_feedback_source_target_counts": dict(
            real_repair_noop_feedback_source_target_counts
        ),
        "real_repair_noop_feedback_source_execution_performed": dict(
            real_repair_noop_feedback_source_execution_performed
        ),
        "real_repair_noop_feedback_source_subprocess_invoked": dict(
            real_repair_noop_feedback_source_subprocess_invoked
        ),
        "real_repair_noop_feedback_source_repair_actions_executed": dict(
            real_repair_noop_feedback_source_repair_actions_executed
        ),
        "real_repair_noop_feedback_source_repair_execution_enabled": dict(
            real_repair_noop_feedback_source_repair_execution_enabled
        ),
        "real_repair_noop_feedback_source_repair_execution_performed": dict(
            real_repair_noop_feedback_source_repair_execution_performed
        ),
        "real_repair_noop_feedback_source_repair_subprocess_invoked": dict(
            real_repair_noop_feedback_source_repair_subprocess_invoked
        ),
        "real_repair_noop_feedback_feedback_execution_performed": dict(
            real_repair_noop_feedback_feedback_execution_performed
        ),
        "real_repair_noop_feedback_feedback_subprocess_invoked": dict(
            real_repair_noop_feedback_feedback_subprocess_invoked
        ),
        "real_repair_noop_feedback_repair_execution_enabled": dict(
            real_repair_noop_feedback_repair_execution_enabled
        ),
        "real_repair_noop_feedback_real_execution_enabled": dict(
            real_repair_noop_feedback_real_execution_enabled
        ),
        "real_repair_noop_feedback_subprocess_enabled": dict(
            real_repair_noop_feedback_subprocess_enabled
        ),
        "real_repair_noop_feedback_repair_execution_performed": dict(
            real_repair_noop_feedback_repair_execution_performed
        ),
        "real_repair_noop_feedback_repair_subprocess_invoked": dict(
            real_repair_noop_feedback_repair_subprocess_invoked
        ),
        "real_repair_noop_feedback_execution_performed": dict(
            real_repair_noop_feedback_execution_performed
        ),
        "real_repair_noop_feedback_subprocess_invoked": dict(
            real_repair_noop_feedback_subprocess_invoked
        ),
        "real_repair_noop_feedback_linkage": real_repair_noop_feedback_linkage,
        "real_repair_noop_feedback_linkage_complete": bool(
            real_repair_noop_feedback_linkage.get(
                "real_repair_noop_feedback_linkage_complete"
            )
        ),
        "real_repair_noop_feedback_result_matches": (
            real_repair_noop_feedback_linkage.get(
                "real_repair_noop_feedback_result_matches", 0
            )
        ),
        "real_repair_noop_feedback_orphans": (
            real_repair_noop_feedback_linkage.get(
                "real_repair_noop_feedback_orphans", 0
            )
        ),
        "real_repair_readiness_gate_statuses": dict(
            real_repair_readiness_gate_statuses
        ),
        "real_repair_readiness_gate_satisfied": dict(
            real_repair_readiness_gate_satisfied
        ),
        "real_repair_readiness_gate_guarded_ready": dict(
            real_repair_readiness_gate_guarded_ready
        ),
        "real_repair_readiness_gate_ready_for_repair_execution": dict(
            real_repair_readiness_gate_ready_for_repair_execution
        ),
        "real_repair_readiness_gate_would_execute": dict(
            real_repair_readiness_gate_would_execute
        ),
        "real_repair_readiness_gate_next_actions": dict(
            real_repair_readiness_gate_next_actions
        ),
        "real_repair_readiness_gate_source_feedback_statuses": dict(
            real_repair_readiness_gate_source_feedback_statuses
        ),
        "real_repair_readiness_gate_source_noop_statuses": dict(
            real_repair_readiness_gate_source_noop_statuses
        ),
        "real_repair_readiness_gate_source_exit_codes": dict(
            real_repair_readiness_gate_source_exit_codes
        ),
        "real_repair_readiness_gate_source_target_counts": dict(
            real_repair_readiness_gate_source_target_counts
        ),
        "real_repair_readiness_gate_source_execution_performed": dict(
            real_repair_readiness_gate_source_execution_performed
        ),
        "real_repair_readiness_gate_source_subprocess_invoked": dict(
            real_repair_readiness_gate_source_subprocess_invoked
        ),
        "real_repair_readiness_gate_source_repair_actions_executed": dict(
            real_repair_readiness_gate_source_repair_actions_executed
        ),
        "real_repair_readiness_gate_source_repair_execution_enabled": dict(
            real_repair_readiness_gate_source_repair_execution_enabled
        ),
        "real_repair_readiness_gate_source_repair_execution_performed": dict(
            real_repair_readiness_gate_source_repair_execution_performed
        ),
        "real_repair_readiness_gate_source_repair_subprocess_invoked": dict(
            real_repair_readiness_gate_source_repair_subprocess_invoked
        ),
        "real_repair_readiness_gate_repair_execution_enabled": dict(
            real_repair_readiness_gate_repair_execution_enabled
        ),
        "real_repair_readiness_gate_real_execution_enabled": dict(
            real_repair_readiness_gate_real_execution_enabled
        ),
        "real_repair_readiness_gate_subprocess_enabled": dict(
            real_repair_readiness_gate_subprocess_enabled
        ),
        "real_repair_readiness_gate_repair_execution_performed": dict(
            real_repair_readiness_gate_repair_execution_performed
        ),
        "real_repair_readiness_gate_repair_subprocess_invoked": dict(
            real_repair_readiness_gate_repair_subprocess_invoked
        ),
        "real_repair_readiness_gate_execution_performed": dict(
            real_repair_readiness_gate_execution_performed
        ),
        "real_repair_readiness_gate_subprocess_invoked": dict(
            real_repair_readiness_gate_subprocess_invoked
        ),
        "real_repair_readiness_gate_linkage": real_repair_readiness_gate_linkage,
        "real_repair_readiness_gate_linkage_complete": bool(
            real_repair_readiness_gate_linkage.get(
                "real_repair_readiness_gate_linkage_complete"
            )
        ),
        "real_repair_readiness_gate_feedback_matches": (
            real_repair_readiness_gate_linkage.get(
                "real_repair_readiness_gate_feedback_matches", 0
            )
        ),
        "real_repair_readiness_gate_orphans": (
            real_repair_readiness_gate_linkage.get(
                "real_repair_readiness_gate_orphans", 0
            )
        ),
        "guarded_repair_execution_statuses": dict(
            guarded_repair_execution_statuses
        ),
        "guarded_repair_execution_allowed": dict(
            guarded_repair_execution_allowed
        ),
        "guarded_repair_execution_marker_observed": dict(
            guarded_repair_execution_marker_observed
        ),
        "guarded_repair_execution_exit_codes": dict(
            guarded_repair_execution_exit_codes
        ),
        "guarded_repair_execution_target_counts": dict(
            guarded_repair_execution_target_counts
        ),
        "guarded_repair_execution_next_actions": dict(
            guarded_repair_execution_next_actions
        ),
        "guarded_repair_execution_source_gate_statuses": dict(
            guarded_repair_execution_source_gate_statuses
        ),
        "guarded_repair_execution_source_feedback_statuses": dict(
            guarded_repair_execution_source_feedback_statuses
        ),
        "guarded_repair_execution_source_noop_statuses": dict(
            guarded_repair_execution_source_noop_statuses
        ),
        "guarded_repair_execution_source_ready_guarded": dict(
            guarded_repair_execution_source_ready_guarded
        ),
        "guarded_repair_execution_source_ready_repair": dict(
            guarded_repair_execution_source_ready_repair
        ),
        "guarded_repair_execution_source_would_execute": dict(
            guarded_repair_execution_source_would_execute
        ),
        "guarded_repair_execution_source_execution_performed": dict(
            guarded_repair_execution_source_execution_performed
        ),
        "guarded_repair_execution_source_subprocess_invoked": dict(
            guarded_repair_execution_source_subprocess_invoked
        ),
        "guarded_repair_execution_repair_actions_executed": dict(
            guarded_repair_execution_repair_actions_executed
        ),
        "guarded_repair_execution_repair_bundle_executed": dict(
            guarded_repair_execution_repair_bundle_executed
        ),
        "guarded_repair_execution_repair_command_executed": dict(
            guarded_repair_execution_repair_command_executed
        ),
        "guarded_repair_execution_rendered_command_executed": dict(
            guarded_repair_execution_rendered_command_executed
        ),
        "guarded_repair_execution_dry_run_command_executed": dict(
            guarded_repair_execution_dry_run_command_executed
        ),
        "guarded_repair_execution_repair_execution_enabled": dict(
            guarded_repair_execution_repair_execution_enabled
        ),
        "guarded_repair_execution_real_execution_enabled": dict(
            guarded_repair_execution_real_execution_enabled
        ),
        "guarded_repair_execution_subprocess_enabled": dict(
            guarded_repair_execution_subprocess_enabled
        ),
        "guarded_repair_execution_repair_execution_performed": dict(
            guarded_repair_execution_repair_execution_performed
        ),
        "guarded_repair_execution_repair_subprocess_invoked": dict(
            guarded_repair_execution_repair_subprocess_invoked
        ),
        "guarded_repair_execution_execution_performed": dict(
            guarded_repair_execution_execution_performed
        ),
        "guarded_repair_execution_subprocess_invoked": dict(
            guarded_repair_execution_subprocess_invoked
        ),
        "guarded_repair_execution_linkage": guarded_repair_execution_linkage,
        "guarded_repair_execution_linkage_complete": bool(
            guarded_repair_execution_linkage.get(
                "guarded_repair_execution_linkage_complete"
            )
        ),
        "guarded_repair_execution_gate_matches": (
            guarded_repair_execution_linkage.get(
                "guarded_repair_execution_gate_matches", 0
            )
        ),
        "guarded_repair_execution_orphans": (
            guarded_repair_execution_linkage.get(
                "guarded_repair_execution_orphans", 0
            )
        ),
        "post_repair_evidence_statuses": dict(post_repair_evidence_statuses),
        "post_repair_evidence_allowed": dict(post_repair_evidence_allowed),
        "post_repair_evidence_enabled": dict(post_repair_evidence_enabled),
        "post_repair_evidence_marker_observed": dict(
            post_repair_evidence_marker_observed
        ),
        "post_repair_evidence_exit_codes": dict(post_repair_evidence_exit_codes),
        "post_repair_evidence_outcome_verified": dict(
            post_repair_evidence_outcome_verified
        ),
        "post_repair_evidence_expected_counts": dict(
            post_repair_evidence_expected_counts
        ),
        "post_repair_evidence_verified_counts": dict(
            post_repair_evidence_verified_counts
        ),
        "post_repair_evidence_missing_counts": dict(
            post_repair_evidence_missing_counts
        ),
        "post_repair_evidence_unexpected_counts": dict(
            post_repair_evidence_unexpected_counts
        ),
        "post_repair_evidence_next_actions": dict(post_repair_evidence_next_actions),
        "post_repair_evidence_source_statuses": dict(
            post_repair_evidence_source_statuses
        ),
        "post_repair_evidence_source_allowed": dict(
            post_repair_evidence_source_allowed
        ),
        "post_repair_evidence_source_marker_observed": dict(
            post_repair_evidence_source_marker_observed
        ),
        "post_repair_evidence_source_exit_codes": dict(
            post_repair_evidence_source_exit_codes
        ),
        "post_repair_evidence_source_repair_actions_executed": dict(
            post_repair_evidence_source_repair_actions_executed
        ),
        "post_repair_evidence_source_repair_execution_enabled": dict(
            post_repair_evidence_source_repair_execution_enabled
        ),
        "post_repair_evidence_source_real_execution_enabled": dict(
            post_repair_evidence_source_real_execution_enabled
        ),
        "post_repair_evidence_source_repair_execution_performed": dict(
            post_repair_evidence_source_repair_execution_performed
        ),
        "post_repair_evidence_source_repair_subprocess_invoked": dict(
            post_repair_evidence_source_repair_subprocess_invoked
        ),
        "post_repair_evidence_execution_performed": dict(
            post_repair_evidence_execution_performed
        ),
        "post_repair_evidence_subprocess_invoked": dict(
            post_repair_evidence_subprocess_invoked
        ),
        "post_repair_evidence_repair_execution_enabled": dict(
            post_repair_evidence_repair_execution_enabled
        ),
        "post_repair_evidence_real_execution_enabled": dict(
            post_repair_evidence_real_execution_enabled
        ),
        "post_repair_evidence_repair_execution_performed": dict(
            post_repair_evidence_repair_execution_performed
        ),
        "post_repair_evidence_repair_subprocess_invoked": dict(
            post_repair_evidence_repair_subprocess_invoked
        ),
        "post_repair_evidence_linkage": post_repair_evidence_linkage,
        "post_repair_evidence_linkage_complete": bool(
            post_repair_evidence_linkage.get(
                "post_repair_evidence_linkage_complete"
            )
        ),
        "post_repair_evidence_guarded_result_matches": (
            post_repair_evidence_linkage.get(
                "post_repair_evidence_guarded_result_matches", 0
            )
        ),
        "post_repair_evidence_orphans": post_repair_evidence_linkage.get(
            "post_repair_evidence_orphans", 0
        ),
        "real_execution_adapter_contract_statuses": dict(
            real_execution_adapter_contract_statuses
        ),
        "real_execution_adapter_contract_schema_versions": dict(
            real_execution_adapter_contract_schema_versions
        ),
        "real_execution_adapter_contract_request_schema_versions": dict(
            real_execution_adapter_contract_request_schema_versions
        ),
        "real_execution_adapter_contract_result_schema_versions": dict(
            real_execution_adapter_contract_result_schema_versions
        ),
        "real_execution_adapter_contract_next_actions": dict(
            real_execution_adapter_contract_next_actions
        ),
        "real_execution_adapter_contract_exists": dict(
            real_execution_adapter_contract_exists
        ),
        "real_execution_adapter_contract_request_schema_exists": dict(
            real_execution_adapter_contract_request_schema_exists
        ),
        "real_execution_adapter_contract_result_schema_exists": dict(
            real_execution_adapter_contract_result_schema_exists
        ),
        "real_execution_adapter_contract_fail_closed_default": dict(
            real_execution_adapter_contract_fail_closed_default
        ),
        "real_execution_adapter_contract_sandbox_first": dict(
            real_execution_adapter_contract_sandbox_first
        ),
        "real_execution_adapter_contract_capability_scoped": dict(
            real_execution_adapter_contract_capability_scoped
        ),
        "real_execution_adapter_contract_policy_gated": dict(
            real_execution_adapter_contract_policy_gated
        ),
        "real_execution_adapter_contract_unknown_capability_rejected": dict(
            real_execution_adapter_contract_unknown_capability_rejected
        ),
        "real_execution_adapter_contract_unknown_policy_rejected": dict(
            real_execution_adapter_contract_unknown_policy_rejected
        ),
        "real_execution_adapter_contract_adapter_enabled": dict(
            real_execution_adapter_contract_adapter_enabled
        ),
        "real_execution_adapter_contract_request_generation_enabled": dict(
            real_execution_adapter_contract_request_generation_enabled
        ),
        "real_execution_adapter_contract_result_generation_enabled": dict(
            real_execution_adapter_contract_result_generation_enabled
        ),
        "real_execution_adapter_contract_sandbox_execution_enabled": dict(
            real_execution_adapter_contract_sandbox_execution_enabled
        ),
        "real_execution_adapter_contract_policy_gated_real_enabled": dict(
            real_execution_adapter_contract_policy_gated_real_enabled
        ),
        "real_execution_adapter_contract_execution_performed": dict(
            real_execution_adapter_contract_execution_performed
        ),
        "real_execution_adapter_contract_subprocess_invoked": dict(
            real_execution_adapter_contract_subprocess_invoked
        ),
        "real_execution_adapter_contract_real_execution_enabled": dict(
            real_execution_adapter_contract_real_execution_enabled
        ),
        "real_execution_adapter_contract_external_side_effects": dict(
            real_execution_adapter_contract_external_side_effects
        ),
        "real_execution_adapter_contract_production_paths_mutated": dict(
            real_execution_adapter_contract_production_paths_mutated
        ),
        "real_execution_adapter_contract_production_secrets_accessed": dict(
            real_execution_adapter_contract_production_secrets_accessed
        ),
        "real_execution_adapter_contract_source_post_repair_statuses": dict(
            real_execution_adapter_contract_source_post_repair_statuses
        ),
        "real_execution_adapter_contract_source_verified": dict(
            real_execution_adapter_contract_source_verified
        ),
        "real_execution_adapter_contract_source_expected_counts": dict(
            real_execution_adapter_contract_source_expected_counts
        ),
        "real_execution_adapter_contract_source_verified_counts": dict(
            real_execution_adapter_contract_source_verified_counts
        ),
        "real_execution_adapter_contract_linkage": (
            real_execution_adapter_contract_linkage
        ),
        "real_execution_adapter_contract_linkage_complete": bool(
            real_execution_adapter_contract_linkage.get(
                "real_execution_adapter_contract_linkage_complete"
            )
        ),
        "real_execution_adapter_contract_post_repair_matches": (
            real_execution_adapter_contract_linkage.get(
                "real_execution_adapter_contract_post_repair_matches", 0
            )
        ),
        "real_execution_adapter_contract_orphans": (
            real_execution_adapter_contract_linkage.get(
                "real_execution_adapter_contract_orphans", 0
            )
        ),
        "real_execution_adapter_request_schema_statuses": dict(
            real_execution_adapter_request_schema_statuses
        ),
        "real_execution_adapter_request_schema_versions": dict(
            real_execution_adapter_request_schema_versions
        ),
        "real_execution_adapter_request_schema_next_actions": dict(
            real_execution_adapter_request_schema_next_actions
        ),
        "real_execution_adapter_request_schema_exists": dict(
            real_execution_adapter_request_schema_exists
        ),
        "real_execution_adapter_request_schema_contract_exists": dict(
            real_execution_adapter_request_schema_contract_exists
        ),
        "real_execution_adapter_request_schema_result_schema_exists": dict(
            real_execution_adapter_request_schema_result_schema_exists
        ),
        "real_execution_adapter_request_schema_fail_closed_default": dict(
            real_execution_adapter_request_schema_fail_closed_default
        ),
        "real_execution_adapter_request_schema_deny_by_default": dict(
            real_execution_adapter_request_schema_deny_by_default
        ),
        "real_execution_adapter_request_schema_unknown_capability_rejected": dict(
            real_execution_adapter_request_schema_unknown_capability_rejected
        ),
        "real_execution_adapter_request_schema_unknown_policy_rejected": dict(
            real_execution_adapter_request_schema_unknown_policy_rejected
        ),
        "real_execution_adapter_request_schema_request_generation_enabled": dict(
            real_execution_adapter_request_schema_request_generation_enabled
        ),
        "real_execution_adapter_request_schema_request_execution_enabled": dict(
            real_execution_adapter_request_schema_request_execution_enabled
        ),
        "real_execution_adapter_request_schema_adapter_enabled": dict(
            real_execution_adapter_request_schema_adapter_enabled
        ),
        "real_execution_adapter_request_schema_result_generation_enabled": dict(
            real_execution_adapter_request_schema_result_generation_enabled
        ),
        "real_execution_adapter_request_schema_sandbox_execution_enabled": dict(
            real_execution_adapter_request_schema_sandbox_execution_enabled
        ),
        "real_execution_adapter_request_schema_policy_gated_real_enabled": dict(
            real_execution_adapter_request_schema_policy_gated_real_enabled
        ),
        "real_execution_adapter_request_schema_execution_performed": dict(
            real_execution_adapter_request_schema_execution_performed
        ),
        "real_execution_adapter_request_schema_subprocess_invoked": dict(
            real_execution_adapter_request_schema_subprocess_invoked
        ),
        "real_execution_adapter_request_schema_real_execution_enabled": dict(
            real_execution_adapter_request_schema_real_execution_enabled
        ),
        "real_execution_adapter_request_schema_external_side_effects": dict(
            real_execution_adapter_request_schema_external_side_effects
        ),
        "real_execution_adapter_request_schema_production_paths_mutated": dict(
            real_execution_adapter_request_schema_production_paths_mutated
        ),
        "real_execution_adapter_request_schema_production_secrets_accessed": dict(
            real_execution_adapter_request_schema_production_secrets_accessed
        ),
        "real_execution_adapter_request_schema_source_contract_statuses": dict(
            real_execution_adapter_request_schema_source_contract_statuses
        ),
        "real_execution_adapter_request_schema_source_verified": dict(
            real_execution_adapter_request_schema_source_verified
        ),
        "real_execution_adapter_request_schema_source_expected_counts": dict(
            real_execution_adapter_request_schema_source_expected_counts
        ),
        "real_execution_adapter_request_schema_source_verified_counts": dict(
            real_execution_adapter_request_schema_source_verified_counts
        ),
        "real_execution_adapter_request_schema_linkage": (
            real_execution_adapter_request_schema_linkage
        ),
        "real_execution_adapter_request_schema_linkage_complete": bool(
            real_execution_adapter_request_schema_linkage.get(
                "real_execution_adapter_request_schema_linkage_complete"
            )
        ),
        "real_execution_adapter_request_schema_contract_matches": (
            real_execution_adapter_request_schema_linkage.get(
                "real_execution_adapter_request_schema_contract_matches", 0
            )
        ),
        "real_execution_adapter_request_schema_orphans": (
            real_execution_adapter_request_schema_linkage.get(
                "real_execution_adapter_request_schema_orphans", 0
            )
        ),
        "real_execution_capability_policy_matrix_statuses": dict(
            real_execution_capability_policy_matrix_statuses
        ),
        "real_execution_capability_policy_matrix_schema_versions": dict(
            real_execution_capability_policy_matrix_schema_versions
        ),
        "real_execution_capability_policy_matrix_next_actions": dict(
            real_execution_capability_policy_matrix_next_actions
        ),
        "real_execution_capability_policy_matrix_capability_counts": dict(
            real_execution_capability_policy_matrix_capability_counts
        ),
        "real_execution_capability_policy_matrix_enabled_capability_counts": dict(
            real_execution_capability_policy_matrix_enabled_capability_counts
        ),
        "real_execution_capability_policy_matrix_blocked_capability_counts": dict(
            real_execution_capability_policy_matrix_blocked_capability_counts
        ),
        "real_execution_capability_policy_matrix_policy_rule_counts": dict(
            real_execution_capability_policy_matrix_policy_rule_counts
        ),
        "real_execution_capability_policy_matrix_approved_policy_counts": dict(
            real_execution_capability_policy_matrix_approved_policy_counts
        ),
        "real_execution_capability_policy_matrix_blocked_policy_counts": dict(
            real_execution_capability_policy_matrix_blocked_policy_counts
        ),
        "real_execution_capability_policy_matrix_registry_exists": dict(
            real_execution_capability_policy_matrix_registry_exists
        ),
        "real_execution_capability_policy_matrix_policy_exists": dict(
            real_execution_capability_policy_matrix_policy_exists
        ),
        "real_execution_capability_policy_matrix_unknown_capability_rejected": dict(
            real_execution_capability_policy_matrix_unknown_capability_rejected
        ),
        "real_execution_capability_policy_matrix_unknown_policy_rejected": dict(
            real_execution_capability_policy_matrix_unknown_policy_rejected
        ),
        "real_execution_capability_policy_matrix_deny_by_default": dict(
            real_execution_capability_policy_matrix_deny_by_default
        ),
        "real_execution_capability_policy_matrix_fail_closed_default": dict(
            real_execution_capability_policy_matrix_fail_closed_default
        ),
        "real_execution_capability_policy_matrix_sandbox_real_blocked": dict(
            real_execution_capability_policy_matrix_sandbox_real_blocked
        ),
        "real_execution_capability_policy_matrix_policy_gated_real_blocked": dict(
            real_execution_capability_policy_matrix_policy_gated_real_blocked
        ),
        "real_execution_capability_policy_matrix_external_side_effects_allowed": dict(
            real_execution_capability_policy_matrix_external_side_effects_allowed
        ),
        "real_execution_capability_policy_matrix_production_paths_allowed": dict(
            real_execution_capability_policy_matrix_production_paths_allowed
        ),
        "real_execution_capability_policy_matrix_production_secrets_allowed": dict(
            real_execution_capability_policy_matrix_production_secrets_allowed
        ),
        "real_execution_capability_policy_matrix_capability_execution_enabled": dict(
            real_execution_capability_policy_matrix_capability_execution_enabled
        ),
        "real_execution_capability_policy_matrix_policy_execution_enabled": dict(
            real_execution_capability_policy_matrix_policy_execution_enabled
        ),
        "real_execution_capability_policy_matrix_adapter_request_generation_enabled": dict(
            real_execution_capability_policy_matrix_adapter_request_generation_enabled
        ),
        "real_execution_capability_policy_matrix_adapter_request_execution_enabled": dict(
            real_execution_capability_policy_matrix_adapter_request_execution_enabled
        ),
        "real_execution_capability_policy_matrix_adapter_result_generation_enabled": dict(
            real_execution_capability_policy_matrix_adapter_result_generation_enabled
        ),
        "real_execution_capability_policy_matrix_sandbox_execution_enabled": dict(
            real_execution_capability_policy_matrix_sandbox_execution_enabled
        ),
        "real_execution_capability_policy_matrix_policy_gated_real_execution_enabled": dict(
            real_execution_capability_policy_matrix_policy_gated_real_execution_enabled
        ),
        "real_execution_capability_policy_matrix_execution_performed": dict(
            real_execution_capability_policy_matrix_execution_performed
        ),
        "real_execution_capability_policy_matrix_subprocess_invoked": dict(
            real_execution_capability_policy_matrix_subprocess_invoked
        ),
        "real_execution_capability_policy_matrix_real_execution_enabled": dict(
            real_execution_capability_policy_matrix_real_execution_enabled
        ),
        "real_execution_capability_policy_matrix_external_side_effects_performed": dict(
            real_execution_capability_policy_matrix_external_side_effects_performed
        ),
        "real_execution_capability_policy_matrix_production_paths_mutated": dict(
            real_execution_capability_policy_matrix_production_paths_mutated
        ),
        "real_execution_capability_policy_matrix_production_secrets_accessed": dict(
            real_execution_capability_policy_matrix_production_secrets_accessed
        ),
        "real_execution_capability_policy_matrix_source_request_schema_statuses": dict(
            real_execution_capability_policy_matrix_source_request_schema_statuses
        ),
        "real_execution_capability_policy_matrix_source_verified": dict(
            real_execution_capability_policy_matrix_source_verified
        ),
        "real_execution_capability_policy_matrix_source_expected_counts": dict(
            real_execution_capability_policy_matrix_source_expected_counts
        ),
        "real_execution_capability_policy_matrix_source_verified_counts": dict(
            real_execution_capability_policy_matrix_source_verified_counts
        ),
        "real_execution_capability_policy_matrix_linkage": (
            real_execution_capability_policy_matrix_linkage
        ),
        "real_execution_capability_policy_matrix_linkage_complete": bool(
            real_execution_capability_policy_matrix_linkage.get(
                "real_execution_capability_policy_matrix_linkage_complete"
            )
        ),
        "real_execution_capability_policy_matrix_request_schema_matches": (
            real_execution_capability_policy_matrix_linkage.get(
                "real_execution_capability_policy_matrix_request_schema_matches", 0
            )
        ),
        "real_execution_capability_policy_matrix_orphans": (
            real_execution_capability_policy_matrix_linkage.get(
                "real_execution_capability_policy_matrix_orphans", 0
            )
        ),
        "real_execution_sandbox_adapter_scaffold_statuses": dict(
            real_execution_sandbox_adapter_scaffold_statuses
        ),
        "real_execution_sandbox_adapter_scaffold_schema_versions": dict(
            real_execution_sandbox_adapter_scaffold_schema_versions
        ),
        "real_execution_sandbox_adapter_scaffold_next_actions": dict(
            real_execution_sandbox_adapter_scaffold_next_actions
        ),
        "real_execution_sandbox_adapter_scaffold_workspace_strategies": dict(
            real_execution_sandbox_adapter_scaffold_workspace_strategies
        ),
        "real_execution_sandbox_adapter_scaffold_network_policies": dict(
            real_execution_sandbox_adapter_scaffold_network_policies
        ),
        "real_execution_sandbox_adapter_scaffold_secret_policies": dict(
            real_execution_sandbox_adapter_scaffold_secret_policies
        ),
        "real_execution_sandbox_adapter_scaffold_filesystem_policies": dict(
            real_execution_sandbox_adapter_scaffold_filesystem_policies
        ),
        "real_execution_sandbox_adapter_scaffold_fail_closed": dict(
            real_execution_sandbox_adapter_scaffold_fail_closed
        ),
        "real_execution_sandbox_adapter_scaffold_deny_by_default": dict(
            real_execution_sandbox_adapter_scaffold_deny_by_default
        ),
        "real_execution_sandbox_adapter_scaffold_sandbox_execution_enabled": dict(
            real_execution_sandbox_adapter_scaffold_sandbox_execution_enabled
        ),
        "real_execution_sandbox_adapter_scaffold_execution_performed": dict(
            real_execution_sandbox_adapter_scaffold_execution_performed
        ),
        "real_execution_sandbox_adapter_scaffold_subprocess_invoked": dict(
            real_execution_sandbox_adapter_scaffold_subprocess_invoked
        ),
        "real_execution_sandbox_adapter_scaffold_real_execution_enabled": dict(
            real_execution_sandbox_adapter_scaffold_real_execution_enabled
        ),
        "real_execution_sandbox_adapter_scaffold_external_side_effects_performed": dict(
            real_execution_sandbox_adapter_scaffold_external_side_effects_performed
        ),
        "real_execution_sandbox_adapter_scaffold_production_paths_mutated": dict(
            real_execution_sandbox_adapter_scaffold_production_paths_mutated
        ),
        "real_execution_sandbox_adapter_scaffold_production_secrets_accessed": dict(
            real_execution_sandbox_adapter_scaffold_production_secrets_accessed
        ),
        "real_execution_sandbox_adapter_scaffold_linkage": (
            real_execution_sandbox_adapter_scaffold_linkage
        ),
        "real_execution_sandbox_adapter_scaffold_linkage_complete": bool(
            real_execution_sandbox_adapter_scaffold_linkage.get(
                "real_execution_sandbox_adapter_scaffold_linkage_complete"
            )
        ),
        "real_execution_sandbox_adapter_scaffold_matrix_matches": (
            real_execution_sandbox_adapter_scaffold_linkage.get(
                "real_execution_sandbox_adapter_scaffold_matrix_matches", 0
            )
        ),
        "real_execution_sandbox_adapter_scaffold_orphans": (
            real_execution_sandbox_adapter_scaffold_linkage.get(
                "real_execution_sandbox_adapter_scaffold_orphans", 0
            )
        ),
        "real_execution_sandbox_adapter_request_preflight_statuses": dict(
            real_execution_sandbox_adapter_request_preflight_statuses
        ),
        "real_execution_sandbox_adapter_request_preflight_schema_versions": dict(
            real_execution_sandbox_adapter_request_preflight_schema_versions
        ),
        "real_execution_sandbox_adapter_request_preflight_next_actions": dict(
            real_execution_sandbox_adapter_request_preflight_next_actions
        ),
        "real_execution_sandbox_adapter_request_preflight_fail_closed": dict(
            real_execution_sandbox_adapter_request_preflight_fail_closed
        ),
        "real_execution_sandbox_adapter_request_preflight_deny_by_default": dict(
            real_execution_sandbox_adapter_request_preflight_deny_by_default
        ),
        "real_execution_sandbox_adapter_request_preflight_request_generation_enabled": dict(
            real_execution_sandbox_adapter_request_preflight_request_generation_enabled
        ),
        "real_execution_sandbox_adapter_request_preflight_workspace_creation_enabled": dict(
            real_execution_sandbox_adapter_request_preflight_workspace_creation_enabled
        ),
        "real_execution_sandbox_adapter_request_preflight_input_materialization_enabled": dict(
            real_execution_sandbox_adapter_request_preflight_input_materialization_enabled
        ),
        "real_execution_sandbox_adapter_request_preflight_command_rendering_enabled": dict(
            real_execution_sandbox_adapter_request_preflight_command_rendering_enabled
        ),
        "real_execution_sandbox_adapter_request_preflight_sandbox_execution_enabled": dict(
            real_execution_sandbox_adapter_request_preflight_sandbox_execution_enabled
        ),
        "real_execution_sandbox_adapter_request_preflight_result_generation_enabled": dict(
            real_execution_sandbox_adapter_request_preflight_result_generation_enabled
        ),
        "real_execution_sandbox_adapter_request_preflight_execution_performed": dict(
            real_execution_sandbox_adapter_request_preflight_execution_performed
        ),
        "real_execution_sandbox_adapter_request_preflight_subprocess_invoked": dict(
            real_execution_sandbox_adapter_request_preflight_subprocess_invoked
        ),
        "real_execution_sandbox_adapter_request_preflight_real_execution_enabled": dict(
            real_execution_sandbox_adapter_request_preflight_real_execution_enabled
        ),
        "real_execution_sandbox_adapter_request_preflight_external_side_effects_performed": dict(
            real_execution_sandbox_adapter_request_preflight_external_side_effects_performed
        ),
        "real_execution_sandbox_adapter_request_preflight_production_paths_mutated": dict(
            real_execution_sandbox_adapter_request_preflight_production_paths_mutated
        ),
        "real_execution_sandbox_adapter_request_preflight_production_secrets_accessed": dict(
            real_execution_sandbox_adapter_request_preflight_production_secrets_accessed
        ),
        "real_execution_sandbox_adapter_request_preflight_linkage": (
            real_execution_sandbox_adapter_request_preflight_linkage
        ),
        "real_execution_sandbox_adapter_request_preflight_linkage_complete": bool(
            real_execution_sandbox_adapter_request_preflight_linkage.get(
                "real_execution_sandbox_adapter_request_preflight_linkage_complete"
            )
        ),
        "real_execution_sandbox_adapter_request_preflight_scaffold_matches": (
            real_execution_sandbox_adapter_request_preflight_linkage.get(
                "real_execution_sandbox_adapter_request_preflight_scaffold_matches",
                0,
            )
        ),
        "real_execution_sandbox_adapter_request_preflight_orphans": (
            real_execution_sandbox_adapter_request_preflight_linkage.get(
                "real_execution_sandbox_adapter_request_preflight_orphans",
                0,
            )
        ),
        "real_execution_sandbox_request_envelope_scaffold_statuses": dict(
            real_execution_sandbox_request_envelope_scaffold_statuses
        ),
        "real_execution_sandbox_request_envelope_scaffold_schema_versions": dict(
            real_execution_sandbox_request_envelope_scaffold_schema_versions
        ),
        "real_execution_sandbox_request_envelope_scaffold_next_actions": dict(
            real_execution_sandbox_request_envelope_scaffold_next_actions
        ),
        "real_execution_sandbox_request_envelope_scaffold_fail_closed": dict(
            real_execution_sandbox_request_envelope_scaffold_fail_closed
        ),
        "real_execution_sandbox_request_envelope_scaffold_deny_by_default": dict(
            real_execution_sandbox_request_envelope_scaffold_deny_by_default
        ),
        "real_execution_sandbox_request_envelope_scaffold_envelope_generation_enabled": dict(
            real_execution_sandbox_request_envelope_scaffold_envelope_generation_enabled
        ),
        "real_execution_sandbox_request_envelope_scaffold_envelope_materialized": dict(
            real_execution_sandbox_request_envelope_scaffold_envelope_materialized
        ),
        "real_execution_sandbox_request_envelope_scaffold_envelope_executable": dict(
            real_execution_sandbox_request_envelope_scaffold_envelope_executable
        ),
        "real_execution_sandbox_request_envelope_scaffold_request_generation_enabled": dict(
            real_execution_sandbox_request_envelope_scaffold_request_generation_enabled
        ),
        "real_execution_sandbox_request_envelope_scaffold_workspace_creation_enabled": dict(
            real_execution_sandbox_request_envelope_scaffold_workspace_creation_enabled
        ),
        "real_execution_sandbox_request_envelope_scaffold_input_materialization_enabled": dict(
            real_execution_sandbox_request_envelope_scaffold_input_materialization_enabled
        ),
        "real_execution_sandbox_request_envelope_scaffold_command_rendering_enabled": dict(
            real_execution_sandbox_request_envelope_scaffold_command_rendering_enabled
        ),
        "real_execution_sandbox_request_envelope_scaffold_sandbox_execution_enabled": dict(
            real_execution_sandbox_request_envelope_scaffold_sandbox_execution_enabled
        ),
        "real_execution_sandbox_request_envelope_scaffold_result_generation_enabled": dict(
            real_execution_sandbox_request_envelope_scaffold_result_generation_enabled
        ),
        "real_execution_sandbox_request_envelope_scaffold_execution_performed": dict(
            real_execution_sandbox_request_envelope_scaffold_execution_performed
        ),
        "real_execution_sandbox_request_envelope_scaffold_subprocess_invoked": dict(
            real_execution_sandbox_request_envelope_scaffold_subprocess_invoked
        ),
        "real_execution_sandbox_request_envelope_scaffold_real_execution_enabled": dict(
            real_execution_sandbox_request_envelope_scaffold_real_execution_enabled
        ),
        "real_execution_sandbox_request_envelope_scaffold_external_side_effects_performed": dict(
            real_execution_sandbox_request_envelope_scaffold_external_side_effects_performed
        ),
        "real_execution_sandbox_request_envelope_scaffold_production_paths_mutated": dict(
            real_execution_sandbox_request_envelope_scaffold_production_paths_mutated
        ),
        "real_execution_sandbox_request_envelope_scaffold_production_secrets_accessed": dict(
            real_execution_sandbox_request_envelope_scaffold_production_secrets_accessed
        ),
        "real_execution_sandbox_request_envelope_scaffold_linkage": (
            real_execution_sandbox_request_envelope_scaffold_linkage
        ),
        "real_execution_sandbox_request_envelope_scaffold_linkage_complete": bool(
            real_execution_sandbox_request_envelope_scaffold_linkage.get(
                "real_execution_sandbox_request_envelope_scaffold_linkage_complete"
            )
        ),
        "real_execution_sandbox_request_envelope_scaffold_preflight_matches": (
            real_execution_sandbox_request_envelope_scaffold_linkage.get(
                "real_execution_sandbox_request_envelope_scaffold_preflight_matches",
                0,
            )
        ),
        "real_execution_sandbox_request_envelope_scaffold_orphans": (
            real_execution_sandbox_request_envelope_scaffold_linkage.get(
                "real_execution_sandbox_request_envelope_scaffold_orphans",
                0,
            )
        ),
        "real_execution_sandbox_materialization_preflight_scaffold_statuses": dict(
            real_execution_sandbox_materialization_preflight_scaffold_statuses
        ),
        "real_execution_sandbox_materialization_preflight_scaffold_schema_versions": dict(
            real_execution_sandbox_materialization_preflight_scaffold_schema_versions
        ),
        "real_execution_sandbox_materialization_preflight_scaffold_next_actions": dict(
            real_execution_sandbox_materialization_preflight_scaffold_next_actions
        ),
        "real_execution_sandbox_materialization_preflight_scaffold_fail_closed": dict(
            real_execution_sandbox_materialization_preflight_scaffold_fail_closed
        ),
        "real_execution_sandbox_materialization_preflight_scaffold_deny_by_default": dict(
            real_execution_sandbox_materialization_preflight_scaffold_deny_by_default
        ),
        "real_execution_sandbox_materialization_preflight_scaffold_preflight_enabled": dict(
            real_execution_sandbox_materialization_preflight_scaffold_preflight_enabled
        ),
        "real_execution_sandbox_materialization_preflight_scaffold_preflight_passed": dict(
            real_execution_sandbox_materialization_preflight_scaffold_preflight_passed
        ),
        "real_execution_sandbox_materialization_preflight_scaffold_envelope_generation_enabled": dict(
            real_execution_sandbox_materialization_preflight_scaffold_envelope_generation_enabled
        ),
        "real_execution_sandbox_materialization_preflight_scaffold_envelope_materialized": dict(
            real_execution_sandbox_materialization_preflight_scaffold_envelope_materialized
        ),
        "real_execution_sandbox_materialization_preflight_scaffold_envelope_executable": dict(
            real_execution_sandbox_materialization_preflight_scaffold_envelope_executable
        ),
        "real_execution_sandbox_materialization_preflight_scaffold_workspace_creation_enabled": dict(
            real_execution_sandbox_materialization_preflight_scaffold_workspace_creation_enabled
        ),
        "real_execution_sandbox_materialization_preflight_scaffold_input_materialization_enabled": dict(
            real_execution_sandbox_materialization_preflight_scaffold_input_materialization_enabled
        ),
        "real_execution_sandbox_materialization_preflight_scaffold_command_rendering_enabled": dict(
            real_execution_sandbox_materialization_preflight_scaffold_command_rendering_enabled
        ),
        "real_execution_sandbox_materialization_preflight_scaffold_sandbox_execution_enabled": dict(
            real_execution_sandbox_materialization_preflight_scaffold_sandbox_execution_enabled
        ),
        "real_execution_sandbox_materialization_preflight_scaffold_result_generation_enabled": dict(
            real_execution_sandbox_materialization_preflight_scaffold_result_generation_enabled
        ),
        "real_execution_sandbox_materialization_preflight_scaffold_execution_performed": dict(
            real_execution_sandbox_materialization_preflight_scaffold_execution_performed
        ),
        "real_execution_sandbox_materialization_preflight_scaffold_subprocess_invoked": dict(
            real_execution_sandbox_materialization_preflight_scaffold_subprocess_invoked
        ),
        "real_execution_sandbox_materialization_preflight_scaffold_real_execution_enabled": dict(
            real_execution_sandbox_materialization_preflight_scaffold_real_execution_enabled
        ),
        "real_execution_sandbox_materialization_preflight_scaffold_external_side_effects_performed": dict(
            real_execution_sandbox_materialization_preflight_scaffold_external_side_effects_performed
        ),
        "real_execution_sandbox_materialization_preflight_scaffold_production_paths_mutated": dict(
            real_execution_sandbox_materialization_preflight_scaffold_production_paths_mutated
        ),
        "real_execution_sandbox_materialization_preflight_scaffold_production_secrets_accessed": dict(
            real_execution_sandbox_materialization_preflight_scaffold_production_secrets_accessed
        ),
        "real_execution_sandbox_materialization_preflight_scaffold_linkage": (
            real_execution_sandbox_materialization_preflight_scaffold_linkage
        ),
        "real_execution_sandbox_materialization_preflight_scaffold_linkage_complete": bool(
            real_execution_sandbox_materialization_preflight_scaffold_linkage.get(
                "real_execution_sandbox_materialization_preflight_scaffold_linkage_complete"
            )
        ),
        "real_execution_sandbox_materialization_preflight_scaffold_envelope_matches": (
            real_execution_sandbox_materialization_preflight_scaffold_linkage.get(
                "real_execution_sandbox_materialization_preflight_scaffold_envelope_matches",
                0,
            )
        ),
        "real_execution_sandbox_materialization_preflight_scaffold_orphans": (
            real_execution_sandbox_materialization_preflight_scaffold_linkage.get(
                "real_execution_sandbox_materialization_preflight_scaffold_orphans",
                0,
            )
        ),
        "real_execution_sandbox_workspace_plan_scaffold_statuses": dict(
            real_execution_sandbox_workspace_plan_scaffold_statuses
        ),
        "real_execution_sandbox_workspace_plan_scaffold_schema_versions": dict(
            real_execution_sandbox_workspace_plan_scaffold_schema_versions
        ),
        "real_execution_sandbox_workspace_plan_scaffold_next_actions": dict(
            real_execution_sandbox_workspace_plan_scaffold_next_actions
        ),
        "real_execution_sandbox_workspace_plan_scaffold_fail_closed": dict(
            real_execution_sandbox_workspace_plan_scaffold_fail_closed
        ),
        "real_execution_sandbox_workspace_plan_scaffold_deny_by_default": dict(
            real_execution_sandbox_workspace_plan_scaffold_deny_by_default
        ),
        "real_execution_sandbox_workspace_plan_scaffold_plan_generation_enabled": dict(
            real_execution_sandbox_workspace_plan_scaffold_plan_generation_enabled
        ),
        "real_execution_sandbox_workspace_plan_scaffold_plan_materialized": dict(
            real_execution_sandbox_workspace_plan_scaffold_plan_materialized
        ),
        "real_execution_sandbox_workspace_plan_scaffold_plan_executable": dict(
            real_execution_sandbox_workspace_plan_scaffold_plan_executable
        ),
        "real_execution_sandbox_workspace_plan_scaffold_directory_creation_enabled": dict(
            real_execution_sandbox_workspace_plan_scaffold_directory_creation_enabled
        ),
        "real_execution_sandbox_workspace_plan_scaffold_workspace_created": dict(
            real_execution_sandbox_workspace_plan_scaffold_workspace_created
        ),
        "real_execution_sandbox_workspace_plan_scaffold_cleanup_registered": dict(
            real_execution_sandbox_workspace_plan_scaffold_cleanup_registered
        ),
        "real_execution_sandbox_workspace_plan_scaffold_materialization_preflight_enabled": dict(
            real_execution_sandbox_workspace_plan_scaffold_materialization_preflight_enabled
        ),
        "real_execution_sandbox_workspace_plan_scaffold_materialization_preflight_passed": dict(
            real_execution_sandbox_workspace_plan_scaffold_materialization_preflight_passed
        ),
        "real_execution_sandbox_workspace_plan_scaffold_envelope_generation_enabled": dict(
            real_execution_sandbox_workspace_plan_scaffold_envelope_generation_enabled
        ),
        "real_execution_sandbox_workspace_plan_scaffold_envelope_materialized": dict(
            real_execution_sandbox_workspace_plan_scaffold_envelope_materialized
        ),
        "real_execution_sandbox_workspace_plan_scaffold_envelope_executable": dict(
            real_execution_sandbox_workspace_plan_scaffold_envelope_executable
        ),
        "real_execution_sandbox_workspace_plan_scaffold_workspace_creation_enabled": dict(
            real_execution_sandbox_workspace_plan_scaffold_workspace_creation_enabled
        ),
        "real_execution_sandbox_workspace_plan_scaffold_input_materialization_enabled": dict(
            real_execution_sandbox_workspace_plan_scaffold_input_materialization_enabled
        ),
        "real_execution_sandbox_workspace_plan_scaffold_command_rendering_enabled": dict(
            real_execution_sandbox_workspace_plan_scaffold_command_rendering_enabled
        ),
        "real_execution_sandbox_workspace_plan_scaffold_sandbox_execution_enabled": dict(
            real_execution_sandbox_workspace_plan_scaffold_sandbox_execution_enabled
        ),
        "real_execution_sandbox_workspace_plan_scaffold_result_generation_enabled": dict(
            real_execution_sandbox_workspace_plan_scaffold_result_generation_enabled
        ),
        "real_execution_sandbox_workspace_plan_scaffold_execution_performed": dict(
            real_execution_sandbox_workspace_plan_scaffold_execution_performed
        ),
        "real_execution_sandbox_workspace_plan_scaffold_subprocess_invoked": dict(
            real_execution_sandbox_workspace_plan_scaffold_subprocess_invoked
        ),
        "real_execution_sandbox_workspace_plan_scaffold_real_execution_enabled": dict(
            real_execution_sandbox_workspace_plan_scaffold_real_execution_enabled
        ),
        "real_execution_sandbox_workspace_plan_scaffold_external_side_effects_performed": dict(
            real_execution_sandbox_workspace_plan_scaffold_external_side_effects_performed
        ),
        "real_execution_sandbox_workspace_plan_scaffold_production_paths_mutated": dict(
            real_execution_sandbox_workspace_plan_scaffold_production_paths_mutated
        ),
        "real_execution_sandbox_workspace_plan_scaffold_production_secrets_accessed": dict(
            real_execution_sandbox_workspace_plan_scaffold_production_secrets_accessed
        ),
        "real_execution_sandbox_workspace_plan_scaffold_linkage": (
            real_execution_sandbox_workspace_plan_scaffold_linkage
        ),
        "real_execution_sandbox_workspace_plan_scaffold_linkage_complete": bool(
            real_execution_sandbox_workspace_plan_scaffold_linkage.get(
                "real_execution_sandbox_workspace_plan_scaffold_linkage_complete"
            )
        ),
        "real_execution_sandbox_workspace_plan_scaffold_materialization_matches": (
            real_execution_sandbox_workspace_plan_scaffold_linkage.get(
                "real_execution_sandbox_workspace_plan_scaffold_materialization_matches",
                0,
            )
        ),
        "real_execution_sandbox_workspace_plan_scaffold_orphans": (
            real_execution_sandbox_workspace_plan_scaffold_linkage.get(
                "real_execution_sandbox_workspace_plan_scaffold_orphans",
                0,
            )
        ),
    }

def _missing_stages(
    *,
    proposals: list[Mapping[str, Any]],
    approvals: list[Mapping[str, Any]],
    plans: list[Mapping[str, Any]],
    rendered_commands: list[Mapping[str, Any]],
    rendered_command_results: list[Mapping[str, Any]],
    eligibilities: list[Mapping[str, Any]],
    results: list[Mapping[str, Any]],
) -> list[str]:
    missing: list[str] = []

    if not proposals:
        missing.append("proposal")
    if not approvals:
        missing.append("approval")
    if not plans:
        missing.append("plan")
    if not rendered_commands:
        missing.append("rendered_command")
    if not rendered_command_results:
        missing.append("rendered_command_result")
    if not eligibilities:
        missing.append("execution_eligibility")
    if not results:
        missing.append("result")

    return missing


def inspect_retry_governance_trail(args: argparse.Namespace) -> dict[str, Any]:
    """Read CRDT and summarize retry governance trail records."""
    db_path = str(args.db_path or config.crdt_db_path)

    crdt = CRDTAdapter(node_id="retry-governance-trail-reader", db_path=db_path)
    try:
        refresh = getattr(crdt, "refresh_from_storage", None)
        if callable(refresh):
            refresh()

        state = getattr(crdt, "state", {}) or {}
        return inspect_retry_governance_trail_from_records(
            list(state.values()),
            proposal_id=str(getattr(args, "proposal_id", "") or ""),
            approval_id=str(getattr(args, "approval_id", "") or ""),
            plan_id=str(getattr(args, "plan_id", "") or ""),
        )
    finally:
        close = getattr(crdt, "close", None)
        if callable(close):
            close()


def _matches_filters(
    record: Mapping[str, Any],
    *,
    proposal_id: str,
    approval_id: str,
    plan_id: str,
) -> bool:
    if proposal_id and str(record.get("proposal_id") or "").strip() != proposal_id:
        payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}
        if str(payload.get("proposal_id") or "").strip() != proposal_id:
            return False

    if approval_id and str(record.get("approval_id") or "").strip() != approval_id:
        payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}
        if str(payload.get("approval_id") or "").strip() != approval_id:
            return False

    if plan_id and str(record.get("plan_id") or "").strip() != plan_id:
        payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}
        if str(payload.get("plan_id") or "").strip() != plan_id:
            return False

    return True


def _clean_status(value: Any) -> str:
    return str(value or "unknown").strip().lower() or "unknown"


def _command_parse(record: Mapping[str, Any]) -> Mapping[str, Any]:
    command_parse = record.get("command_parse")
    if isinstance(command_parse, Mapping):
        return command_parse

    payload = record.get("payload")
    if isinstance(payload, Mapping):
        nested = payload.get("command_parse")
        if isinstance(nested, Mapping):
            return nested

    return {}


def _gate_evaluation(record: Mapping[str, Any]) -> Mapping[str, Any]:
    gate_evaluation = record.get("gate_evaluation")
    if isinstance(gate_evaluation, Mapping):
        return gate_evaluation

    payload = record.get("payload")
    if isinstance(payload, Mapping):
        nested = payload.get("gate_evaluation")
        if isinstance(nested, Mapping):
            return nested

    return {}


def _mock_execution(record: Mapping[str, Any]) -> Mapping[str, Any]:
    mock_execution = record.get("mock_execution")
    if isinstance(mock_execution, Mapping):
        return mock_execution

    payload = record.get("payload")
    if isinstance(payload, Mapping):
        nested = payload.get("mock_execution")
        if isinstance(nested, Mapping):
            return nested

    return {}


def _mock_execution_payload(record: Mapping[str, Any]) -> Mapping[str, Any]:
    mock_execution = _mock_execution(record)
    nested = mock_execution.get("mock_execution")
    if isinstance(nested, Mapping):
        return nested

    return {}


def _mock_adapter_result(record: Mapping[str, Any]) -> Mapping[str, Any]:
    mock_payload = _mock_execution_payload(record)
    adapter_result = mock_payload.get("adapter_result")
    if isinstance(adapter_result, Mapping):
        return adapter_result

    return {}


def _build_chain_ids(
    *,
    proposals: list[Mapping[str, Any]],
    approvals: list[Mapping[str, Any]],
    plans: list[Mapping[str, Any]],
    rendered_commands: list[Mapping[str, Any]],
    rendered_command_results: list[Mapping[str, Any]],
    eligibilities: list[Mapping[str, Any]],
    controlled_execution_results: list[Mapping[str, Any]],
    mock_execution_summaries: list[Mapping[str, Any]],
    real_preflights: list[Mapping[str, Any]],
    real_approvals: list[Mapping[str, Any]],
    real_approval_transitions: list[Mapping[str, Any]],
    real_final_gates: list[Mapping[str, Any]],
    real_dry_run_envelopes: list[Mapping[str, Any]],
    real_noop_results: list[Mapping[str, Any]],
    real_read_only_promotions: list[Mapping[str, Any]],
    real_read_only_final_gates: list[Mapping[str, Any]],
    real_read_only_approvals: list[Mapping[str, Any]],
    real_read_only_approval_transitions: list[Mapping[str, Any]],
    real_read_only_readiness_gates: list[Mapping[str, Any]],
    real_read_only_execution_results: list[Mapping[str, Any]],
    real_read_only_feedback_records: list[Mapping[str, Any]],
    real_read_only_repair_plans: list[Mapping[str, Any]],
    real_read_only_repair_action_bundles: list[Mapping[str, Any]],
    real_read_only_repair_action_bundle_reviews: list[Mapping[str, Any]],
    real_repair_approvals: list[Mapping[str, Any]],
    real_repair_approval_transitions: list[Mapping[str, Any]],
    real_repair_final_gates: list[Mapping[str, Any]],
    real_repair_dry_run_envelopes: list[Mapping[str, Any]],
    real_repair_noop_results: list[Mapping[str, Any]],
    real_repair_noop_feedback_records: list[Mapping[str, Any]],
    real_repair_readiness_gates: list[Mapping[str, Any]],
    guarded_repair_execution_results: list[Mapping[str, Any]],
    post_repair_evidence_checks: list[Mapping[str, Any]],
    real_execution_adapter_contracts: list[Mapping[str, Any]],
    real_execution_adapter_request_schemas: list[Mapping[str, Any]],
    real_execution_capability_policy_matrices: list[Mapping[str, Any]],
    real_execution_sandbox_adapter_scaffolds: list[Mapping[str, Any]],
    real_execution_sandbox_adapter_request_preflights: list[Mapping[str, Any]],
    real_execution_sandbox_request_envelope_scaffolds: list[Mapping[str, Any]],
    real_execution_sandbox_materialization_preflight_scaffolds: list[Mapping[str, Any]],
    real_execution_sandbox_workspace_plan_scaffolds: list[Mapping[str, Any]],
    results: list[Mapping[str, Any]],
) -> dict[str, list[str]]:
    all_records = (
        proposals
        + approvals
        + plans
        + rendered_commands
        + rendered_command_results
        + eligibilities
        + controlled_execution_results
        + mock_execution_summaries
        + real_preflights
        + real_approvals
        + real_approval_transitions
        + real_final_gates
        + real_dry_run_envelopes
        + real_noop_results
        + real_read_only_promotions
        + real_read_only_final_gates
        + real_read_only_approvals
        + real_read_only_approval_transitions
        + real_read_only_readiness_gates
        + real_read_only_execution_results
        + real_read_only_feedback_records
        + real_read_only_repair_plans
        + real_read_only_repair_action_bundles
        + real_read_only_repair_action_bundle_reviews
        + real_repair_approvals
        + real_repair_approval_transitions
        + real_repair_final_gates
        + real_repair_dry_run_envelopes
        + real_repair_noop_results
        + real_repair_noop_feedback_records
        + real_repair_readiness_gates
        + guarded_repair_execution_results
        + post_repair_evidence_checks
        + real_execution_adapter_contracts
        + real_execution_adapter_request_schemas
        + real_execution_capability_policy_matrices
        + real_execution_sandbox_adapter_scaffolds
        + real_execution_sandbox_adapter_request_preflights
        + real_execution_sandbox_request_envelope_scaffolds
        + real_execution_sandbox_materialization_preflight_scaffolds
        + real_execution_sandbox_workspace_plan_scaffolds
        + results
    )

    return {
        "proposal_ids": sorted(
           {
                str(item.get("proposal_id") or "").strip()
                for item in all_records
                if str(item.get("proposal_id") or "").strip()
            }
        ),
        "approval_ids": sorted(
            {
                str(item.get("approval_id") or "").strip()
                for item in approvals
                + plans
                + rendered_commands
                + rendered_command_results
                + eligibilities
                + controlled_execution_results
                + mock_execution_summaries
                + real_preflights
                + real_approvals
                + real_approval_transitions
                + real_final_gates
                + real_dry_run_envelopes
                + real_noop_results
                + real_read_only_promotions
                + real_read_only_final_gates
                + real_read_only_approvals
                + real_read_only_approval_transitions
                + real_read_only_readiness_gates
                + real_read_only_execution_results
                + real_read_only_feedback_records
                + real_read_only_repair_plans
                + real_read_only_repair_action_bundles
                + real_read_only_repair_action_bundle_reviews
                + real_repair_approvals
                + real_repair_approval_transitions
                + real_repair_final_gates
                + real_repair_dry_run_envelopes
                + real_repair_noop_results
                + real_repair_noop_feedback_records
                + real_repair_readiness_gates
                + guarded_repair_execution_results
                + post_repair_evidence_checks
                + real_execution_adapter_contracts
                + real_execution_adapter_request_schemas
                + real_execution_capability_policy_matrices
                + real_execution_sandbox_adapter_scaffolds
                + real_execution_sandbox_adapter_request_preflights
                + real_execution_sandbox_request_envelope_scaffolds
                + real_execution_sandbox_materialization_preflight_scaffolds
                + real_execution_sandbox_workspace_plan_scaffolds
                + results
               if str(item.get("approval_id") or "").strip()
            }
        ),
        "plan_ids": sorted(
           {
                str(item.get("plan_id") or "").strip()
                for item in plans
                + rendered_commands
                + rendered_command_results
                + eligibilities
                + controlled_execution_results
                + mock_execution_summaries
                + real_preflights
                + real_approvals
                + real_approval_transitions
                + real_final_gates
                + real_dry_run_envelopes
                + real_noop_results
                + real_read_only_promotions
                + real_read_only_final_gates
                + real_read_only_approvals
                + real_read_only_approval_transitions
                + real_read_only_readiness_gates
                + real_read_only_execution_results
                + real_read_only_feedback_records
                + real_read_only_repair_plans
                + real_read_only_repair_action_bundles
                + real_read_only_repair_action_bundle_reviews
                + real_repair_approvals
                + real_repair_approval_transitions
                + real_repair_final_gates
                + real_repair_dry_run_envelopes
                + real_repair_noop_results
                + real_repair_noop_feedback_records
                + real_repair_readiness_gates
                + guarded_repair_execution_results
                + post_repair_evidence_checks
                + real_execution_adapter_contracts
                + real_execution_adapter_request_schemas
                + real_execution_capability_policy_matrices
                + real_execution_sandbox_adapter_scaffolds
                + real_execution_sandbox_adapter_request_preflights
                + real_execution_sandbox_request_envelope_scaffolds
                + real_execution_sandbox_materialization_preflight_scaffolds
                + real_execution_sandbox_workspace_plan_scaffolds
                + results
                if str(item.get("plan_id") or "").strip()
            }
        ),
        "rendered_command_ids": sorted(
            {
                str(item.get("rendered_command_id") or "").strip()
                for item in (
                    rendered_commands
                    + rendered_command_results
                    + eligibilities
                    + controlled_execution_results
                    + mock_execution_summaries
                    + real_preflights
                    + real_approvals
                    + real_approval_transitions
                    + real_final_gates
                    + real_dry_run_envelopes
                    + real_noop_results
                    + real_read_only_promotions
                    + real_read_only_final_gates
                    + real_read_only_approvals
                    + real_read_only_approval_transitions
                    + real_read_only_readiness_gates
                    + real_read_only_execution_results
                    + real_read_only_feedback_records
                    + real_read_only_repair_plans
                    + real_read_only_repair_action_bundles
                    + real_read_only_repair_action_bundle_reviews
                    + real_repair_approvals
                    + real_repair_approval_transitions
                    + real_repair_final_gates
                    + real_repair_dry_run_envelopes
                    + real_repair_noop_results
                    + real_repair_noop_feedback_records
                    + real_repair_readiness_gates
                    + guarded_repair_execution_results
                    + post_repair_evidence_checks
                    + real_execution_adapter_contracts
                    + real_execution_adapter_request_schemas
                    + real_execution_capability_policy_matrices
                    + real_execution_sandbox_adapter_scaffolds
                    + real_execution_sandbox_adapter_request_preflights
                    + real_execution_sandbox_request_envelope_scaffolds
                    + real_execution_sandbox_materialization_preflight_scaffolds
                    + real_execution_sandbox_workspace_plan_scaffolds
                    + results
                )
                if str(item.get("rendered_command_id") or "").strip()
            }
        ),
        "rendered_command_result_ids": sorted(
            {
                str(item.get("rendered_command_result_id") or "").strip()
                for item in rendered_command_results
                if str(item.get("rendered_command_result_id") or "").strip()
            }
        ),
        "eligibility_ids": sorted(
            {
                str(item.get("eligibility_id") or "").strip()
                for item in eligibilities
                if str(item.get("eligibility_id") or "").strip()
            }
        ),
        "controlled_execution_result_ids": sorted(
            {
                str(item.get("controlled_execution_result_id") or "").strip()
                for item in controlled_execution_results
                if str(item.get("controlled_execution_result_id") or "").strip()
            }
        ),
        "result_ids": sorted(
            {
                str(item.get("result_id") or "").strip()
                for item in results
                if str(item.get("result_id") or "").strip()
            }
        ),
        "mock_execution_summary_ids": sorted(
            {
                str(item.get("mock_execution_summary_id") or "").strip()
                for item in mock_execution_summaries
                if str(item.get("mock_execution_summary_id") or "").strip()
            }
        ),
        "real_execution_preflight_ids": sorted(
            {
                str(item.get("real_execution_preflight_id") or "").strip()
                for item in real_preflights
                if str(item.get("real_execution_preflight_id") or "").strip()
            }
        ),
        "real_execution_approval_ids": sorted(
            {
                str(item.get("real_execution_approval_id") or "").strip()
                for item in real_approvals
                if str(item.get("real_execution_approval_id") or "").strip()
            }
        ),
        "real_execution_approval_transition_ids": sorted(
            {
                str(item.get("real_execution_approval_transition_id") or "").strip()
                for item in real_approval_transitions
                if str(item.get("real_execution_approval_transition_id") or "").strip()
            }
        ),
        "real_execution_final_gate_ids": sorted(
            {
                str(item.get("real_execution_final_gate_id") or "").strip()
                for item in real_final_gates
                if str(item.get("real_execution_final_gate_id") or "").strip()
            }
        ),
        "real_execution_dry_run_envelope_ids": sorted(
            {
                str(item.get("real_execution_dry_run_envelope_id") or "").strip()
                for item in real_dry_run_envelopes
                if str(item.get("real_execution_dry_run_envelope_id") or "").strip()
            }
        ),
        "real_execution_noop_result_ids": sorted(
            {
                str(item.get("real_execution_noop_result_id") or "").strip()
                for item in real_noop_results
                if str(item.get("real_execution_noop_result_id") or "").strip()
            }
        ),
        "real_execution_read_only_promotion_ids": sorted(
            {
                str(
                    item.get("real_execution_read_only_promotion_id") or ""
                ).strip()
                for item in real_read_only_promotions
                if str(
                    item.get("real_execution_read_only_promotion_id") or ""
                ).strip()
            }
        ),
        "real_execution_read_only_final_gate_ids": sorted(
            {
                str(item.get("real_execution_read_only_final_gate_id") or "").strip()
                for item in real_read_only_final_gates
                if str(item.get("real_execution_read_only_final_gate_id") or "").strip()
            }
        ),
        "real_execution_read_only_approval_ids": sorted(
            {
                str(item.get("real_execution_read_only_approval_id") or "").strip()
                for item in real_read_only_approvals
                if str(item.get("real_execution_read_only_approval_id") or "").strip()
            }
        ),
        "real_execution_read_only_approval_transition_ids": sorted(
            {
                str(
                    item.get("real_execution_read_only_approval_transition_id") or ""
                ).strip()
                for item in real_read_only_approval_transitions
                if str(
                    item.get("real_execution_read_only_approval_transition_id") or ""
                ).strip()
            }
        ),
        "real_execution_read_only_readiness_gate_ids": sorted(
            {
                str(item.get("real_execution_read_only_readiness_gate_id") or "").strip()
                for item in real_read_only_readiness_gates
                if str(item.get("real_execution_read_only_readiness_gate_id") or "").strip()
            }
        ),
        "real_execution_read_only_execution_result_ids": sorted(
            {
                str(item.get("real_execution_read_only_execution_result_id") or "").strip()
                for item in real_read_only_execution_results
                if str(item.get("real_execution_read_only_execution_result_id") or "").strip()
            }
        ),
        "real_execution_read_only_feedback_ids": sorted(
            {
                str(item.get("real_execution_read_only_feedback_id") or "").strip()
                for item in real_read_only_feedback_records
                if str(item.get("real_execution_read_only_feedback_id") or "").strip()
            }
        ),
        "real_execution_read_only_repair_plan_ids": sorted(
            {
                str(item.get("real_execution_read_only_repair_plan_id") or "").strip()
                for item in real_read_only_repair_plans
                if str(item.get("real_execution_read_only_repair_plan_id") or "").strip()
            }
        ),
        "real_execution_read_only_repair_action_bundle_ids": sorted(
            {
                str(
                    item.get("real_execution_read_only_repair_action_bundle_id") or ""
                ).strip()
                for item in real_read_only_repair_action_bundles
                if str(
                    item.get("real_execution_read_only_repair_action_bundle_id") or ""
                ).strip()
            }
        ),
        "real_execution_read_only_repair_action_bundle_review_ids": sorted(
            {
                str(
                    item.get(
                        "real_execution_read_only_repair_action_bundle_review_id"
                    )
                    or ""
                ).strip()
                for item in real_read_only_repair_action_bundle_reviews
                if str(
                    item.get(
                        "real_execution_read_only_repair_action_bundle_review_id"
                    )
                    or ""
                ).strip()
            }
        ),
        "real_execution_repair_approval_ids": sorted(
            {
                str(item.get("real_execution_repair_approval_id") or "").strip()
                for item in real_repair_approvals
                if str(item.get("real_execution_repair_approval_id") or "").strip()
            }
        ),
        "real_execution_repair_approval_transition_ids": sorted(
            {
                str(
                    item.get("real_execution_repair_approval_transition_id") or ""
                ).strip()
                for item in real_repair_approval_transitions
                if str(
                    item.get("real_execution_repair_approval_transition_id") or ""
                ).strip()
            }
        ),
        "real_execution_repair_final_gate_ids": sorted(
            {
                str(item.get("real_execution_repair_final_gate_id") or "").strip()
                for item in real_repair_final_gates
                if str(item.get("real_execution_repair_final_gate_id") or "").strip()
            }
        ),
        "real_execution_repair_dry_run_envelope_ids": sorted(
            {
                str(
                    item.get("real_execution_repair_dry_run_envelope_id") or ""
                ).strip()
                for item in real_repair_dry_run_envelopes
                if str(
                    item.get("real_execution_repair_dry_run_envelope_id") or ""
                ).strip()
            }
        ),
        "real_execution_repair_noop_result_ids": sorted(
            {
                str(item.get("real_execution_repair_noop_result_id") or "").strip()
                for item in real_repair_noop_results
                if str(item.get("real_execution_repair_noop_result_id") or "").strip()
            }
        ),
        "real_execution_repair_noop_feedback_ids": sorted(
            {
                str(item.get("real_execution_repair_noop_feedback_id") or "").strip()
                for item in real_repair_noop_feedback_records
                if str(
                    item.get("real_execution_repair_noop_feedback_id") or ""
                ).strip()
            }
        ),
        "real_execution_repair_readiness_gate_ids": sorted(
            {
                str(item.get("real_execution_repair_readiness_gate_id") or "").strip()
                for item in real_repair_readiness_gates
                if str(
                    item.get("real_execution_repair_readiness_gate_id") or ""
                ).strip()
            }
        ),
        "guarded_repair_execution_result_ids": sorted(
            {
                str(item.get("guarded_repair_execution_result_id") or "").strip()
                for item in guarded_repair_execution_results
                if str(item.get("guarded_repair_execution_result_id") or "").strip()
            }
        ),
        "post_repair_evidence_check_ids": sorted(
            {
                str(item.get("post_repair_evidence_check_id") or "").strip()
                for item in post_repair_evidence_checks
                if str(item.get("post_repair_evidence_check_id") or "").strip()
            }
        ),
        "real_execution_adapter_contract_ids": sorted(
            {
                str(item.get("real_execution_adapter_contract_id") or "").strip()
                for item in real_execution_adapter_contracts
                if str(item.get("real_execution_adapter_contract_id") or "").strip()
            }
        ),
        "real_execution_adapter_request_schema_ids": sorted(
            {
                str(
                    item.get("real_execution_adapter_request_schema_id") or ""
                ).strip()
                for item in real_execution_adapter_request_schemas
                if str(
                    item.get("real_execution_adapter_request_schema_id") or ""
                ).strip()
            }
        ),
        "real_execution_capability_policy_matrix_ids": sorted(
            {
                str(
                    item.get("real_execution_capability_policy_matrix_id") or ""
                ).strip()
                for item in real_execution_capability_policy_matrices
                if str(
                    item.get("real_execution_capability_policy_matrix_id") or ""
                ).strip()
            }
        ),
        "real_execution_sandbox_adapter_scaffold_ids": sorted(
            {
                str(
                    item.get("real_execution_sandbox_adapter_scaffold_id") or ""
                ).strip()
                for item in real_execution_sandbox_adapter_scaffolds
                if str(
                    item.get("real_execution_sandbox_adapter_scaffold_id") or ""
                ).strip()
            }
        ),
        "real_execution_sandbox_adapter_request_preflight_ids": sorted(
            {
                str(
                    item.get(
                        "real_execution_sandbox_adapter_request_preflight_id"
                    )
                    or ""
                ).strip()
                for item in real_execution_sandbox_adapter_request_preflights
                if str(
                    item.get(
                        "real_execution_sandbox_adapter_request_preflight_id"
                    )
                    or ""
                ).strip()
            }
        ),
        "real_execution_sandbox_request_envelope_scaffold_ids": sorted(
            {
                str(
                    item.get("real_execution_sandbox_request_envelope_scaffold_id")
                    or ""
                ).strip()
                for item in real_execution_sandbox_request_envelope_scaffolds
                if str(
                    item.get("real_execution_sandbox_request_envelope_scaffold_id")
                    or ""
                ).strip()
            }
        ),
        "real_execution_sandbox_materialization_preflight_scaffold_ids": sorted(
            {
                str(
                    item.get(
                        "real_execution_sandbox_materialization_preflight_scaffold_id"
                    )
                    or ""
                ).strip()
                for item in real_execution_sandbox_materialization_preflight_scaffolds
                if str(
                    item.get(
                        "real_execution_sandbox_materialization_preflight_scaffold_id"
                    )
                    or ""
                ).strip()
            }
        ),
        "real_execution_sandbox_workspace_plan_scaffold_ids": sorted(
            {
                str(
                    item.get("real_execution_sandbox_workspace_plan_scaffold_id")
                    or ""
                ).strip()
                for item in real_execution_sandbox_workspace_plan_scaffolds
                if str(
                    item.get("real_execution_sandbox_workspace_plan_scaffold_id")
                    or ""
                ).strip()
            }
        ),
    }


def _format_summary(summary: Mapping[str, Any]) -> str:
    counts = summary.get("counts") if isinstance(summary.get("counts"), Mapping) else {}
    result_statuses = (
        summary.get("result_statuses")
        if isinstance(summary.get("result_statuses"), Mapping)
        else {}
    )
    result_reasons = (
        summary.get("result_reasons")
        if isinstance(summary.get("result_reasons"), Mapping)
        else {}
    )
    rendered_command_result_statuses = (
        summary.get("rendered_command_result_statuses")
        if isinstance(summary.get("rendered_command_result_statuses"), Mapping)
        else {}
    )
    rendered_command_result_reasons = (
        summary.get("rendered_command_result_reasons")
        if isinstance(summary.get("rendered_command_result_reasons"), Mapping)
        else {}
    )
    eligibility_statuses = (
        summary.get("eligibility_statuses")
        if isinstance(summary.get("eligibility_statuses"), Mapping)
        else {}
    )
    eligibility_reasons = (
        summary.get("eligibility_reasons")
        if isinstance(summary.get("eligibility_reasons"), Mapping)
        else {}
    )
    controlled_execution_result_statuses = (
        summary.get("controlled_execution_result_statuses")
        if isinstance(summary.get("controlled_execution_result_statuses"), Mapping)
        else {}
    )
    controlled_execution_result_reasons = (
        summary.get("controlled_execution_result_reasons")
        if isinstance(summary.get("controlled_execution_result_reasons"), Mapping)
        else {}
    )
    controlled_command_parse_valid = (
        summary.get("controlled_command_parse_valid")
        if isinstance(summary.get("controlled_command_parse_valid"), Mapping)
        else {}
    )
    controlled_command_parse_allowlist_matched = (
        summary.get("controlled_command_parse_allowlist_matched")
        if isinstance(summary.get("controlled_command_parse_allowlist_matched"), Mapping)
        else {}
    )
    controlled_command_parse_execution_performed = (
        summary.get("controlled_command_parse_execution_performed")
        if isinstance(summary.get("controlled_command_parse_execution_performed"), Mapping)
        else {}
    )
    controlled_execution_operator_authorized = (
        summary.get("controlled_execution_operator_authorized")
        if isinstance(summary.get("controlled_execution_operator_authorized"), Mapping)
        else {}
    )
    controlled_gate_statuses = (
        summary.get("controlled_gate_statuses")
        if isinstance(summary.get("controlled_gate_statuses"), Mapping)
        else {}
    )
    controlled_gate_would_execute = (
        summary.get("controlled_gate_would_execute")
        if isinstance(summary.get("controlled_gate_would_execute"), Mapping)
        else {}
    )
    controlled_gate_would_execute_if_enabled = (
        summary.get("controlled_gate_would_execute_if_enabled")
        if isinstance(summary.get("controlled_gate_would_execute_if_enabled"), Mapping)
        else {}
    )
    controlled_gate_execution_performed = (
        summary.get("controlled_gate_execution_performed")
        if isinstance(summary.get("controlled_gate_execution_performed"), Mapping)
        else {}
    )
    controlled_gate_reasons = (
        summary.get("controlled_gate_reasons")
        if isinstance(summary.get("controlled_gate_reasons"), Mapping)
        else {}
    )
    controlled_mock_statuses = (
        summary.get("controlled_mock_statuses")
        if isinstance(summary.get("controlled_mock_statuses"), Mapping)
        else {}
    )
    controlled_mock_performed = (
        summary.get("controlled_mock_performed")
        if isinstance(summary.get("controlled_mock_performed"), Mapping)
        else {}
    )
    controlled_mock_subprocess_invoked = (
        summary.get("controlled_mock_subprocess_invoked")
        if isinstance(summary.get("controlled_mock_subprocess_invoked"), Mapping)
        else {}
    )
    controlled_mock_adapter = (
        summary.get("controlled_mock_adapter")
        if isinstance(summary.get("controlled_mock_adapter"), Mapping)
        else {}
    )
    controlled_mock_adapter_mode = (
        summary.get("controlled_mock_adapter_mode")
        if isinstance(summary.get("controlled_mock_adapter_mode"), Mapping)
        else {}
    )
    controlled_mock_adapter_subprocess_invoked = (
        summary.get("controlled_mock_adapter_subprocess_invoked")
        if isinstance(
            summary.get("controlled_mock_adapter_subprocess_invoked"), Mapping
        )
        else {}
    )
    controlled_mock_adapter_real_execution_enabled = (
        summary.get("controlled_mock_adapter_real_execution_enabled")
        if isinstance(
            summary.get("controlled_mock_adapter_real_execution_enabled"), Mapping
        )
        else {}
    )
    controlled_mock_adapter_payload_executed = (
        summary.get("controlled_mock_adapter_payload_executed")
        if isinstance(summary.get("controlled_mock_adapter_payload_executed"), Mapping)
        else {}
    )
    controlled_real_execution_requested = (
        summary.get("controlled_real_execution_requested")
        if isinstance(summary.get("controlled_real_execution_requested"), Mapping)
        else {}
    )
    controlled_real_execution_performed = (
        summary.get("controlled_real_execution_performed")
        if isinstance(summary.get("controlled_real_execution_performed"), Mapping)
        else {}
    )
    controlled_real_execution_supported = (
        summary.get("controlled_real_execution_supported")
        if isinstance(summary.get("controlled_real_execution_supported"), Mapping)
        else {}
    )
    controlled_subprocess_invoked = (
        summary.get("controlled_subprocess_invoked")
        if isinstance(summary.get("controlled_subprocess_invoked"), Mapping)
        else {}
    )
    real_preflight_statuses = (
        summary.get("real_preflight_statuses")
        if isinstance(summary.get("real_preflight_statuses"), Mapping)
        else {}
    )
    real_preflight_would_execute = (
        summary.get("real_preflight_would_execute")
        if isinstance(summary.get("real_preflight_would_execute"), Mapping)
        else {}
    )
    real_preflight_execution_performed = (
        summary.get("real_preflight_execution_performed")
        if isinstance(summary.get("real_preflight_execution_performed"), Mapping)
        else {}
    )
    real_preflight_subprocess_invoked = (
        summary.get("real_preflight_subprocess_invoked")
        if isinstance(summary.get("real_preflight_subprocess_invoked"), Mapping)
        else {}
    )
    real_preflight_requires_explicit_pr = (
        summary.get("real_preflight_requires_explicit_pr")
        if isinstance(summary.get("real_preflight_requires_explicit_pr"), Mapping)
        else {}
    )
    real_approval_statuses = (
        summary.get("real_approval_statuses")
        if isinstance(summary.get("real_approval_statuses"), Mapping)
        else {}
    )
    real_approval_enabled = (
        summary.get("real_approval_enabled")
        if isinstance(summary.get("real_approval_enabled"), Mapping)
        else {}
    )
    real_approval_subprocess_enabled = (
        summary.get("real_approval_subprocess_enabled")
        if isinstance(summary.get("real_approval_subprocess_enabled"), Mapping)
        else {}
    )
    real_approval_execution_performed = (
        summary.get("real_approval_execution_performed")
        if isinstance(summary.get("real_approval_execution_performed"), Mapping)
        else {}
    )
    real_approval_subprocess_invoked = (
        summary.get("real_approval_subprocess_invoked")
        if isinstance(summary.get("real_approval_subprocess_invoked"), Mapping)
        else {}
    )

    chain_complete = bool(summary.get("chain_complete"))
    missing_stages = summary.get("missing_stages")
    if isinstance(missing_stages, list):
        missing_text = ",".join(str(item) for item in missing_stages) or "none"
    else:
        missing_text = "unknown"

    return (
        "Retry governance trail: "
        f"proposals={counts.get('proposals', 0)} "
        f"approvals={counts.get('approvals', 0)} "
        f"plans={counts.get('plans', 0)} "
        f"rendered={counts.get('rendered_commands', 0)} "
        f"rendered_results={counts.get('rendered_command_results', 0)} "
        f"eligibilities={counts.get('eligibilities', 0)} "
        f"controlled_results={counts.get('controlled_execution_results', 0)} "
        f"results={counts.get('results', 0)} "
        f"skipped={result_statuses.get('skipped', 0)} "
        f"rejected={result_statuses.get('rejected', 0)} "
        f"execution_disabled={result_reasons.get('execution_disabled', 0)} "
        f"execution_not_supported={result_reasons.get('execution_not_supported', 0)} "
        f"rendered_skipped={rendered_command_result_statuses.get('skipped', 0)} "
        f"rendered_execution_disabled={rendered_command_result_reasons.get('execution_disabled', 0)} "
        f"blocked={eligibility_statuses.get('blocked', 0)} "
        f"eligibility_execution_disabled={eligibility_reasons.get('execution_disabled', 0)} "
        f"controlled_rejected={controlled_execution_result_statuses.get('rejected', 0)} "
        f"controlled_not_implemented={controlled_execution_result_reasons.get('controlled_execution_not_implemented', 0)} "
        f"extended_controlled_execution_observed={str(bool(summary.get('extended_controlled_execution_observed'))).lower()} "
        f"chain_complete={str(chain_complete).lower()} "
        f"missing_stages={missing_text} "
        f"command_parse_valid={controlled_command_parse_valid.get('true', 0)} "
        f"command_parse_allowlisted={controlled_command_parse_allowlist_matched.get('true', 0)} "
        f"command_parse_execution_performed={controlled_command_parse_execution_performed.get('true', 0)} "
        f"operator_authorized={controlled_execution_operator_authorized.get('true', 0)} "
        f"gate_blocked={controlled_gate_statuses.get('blocked', 0)} "
        f"gate_would_execute={controlled_gate_would_execute.get('true', 0)} "
        f"gate_would_execute_if_enabled={controlled_gate_would_execute_if_enabled.get('true', 0)} "
        f"gate_execution_performed={controlled_gate_execution_performed.get('true', 0)} "
        f"gate_not_enabled={controlled_gate_reasons.get('controlled_execution_not_enabled', 0)} "
        f"mock_executed={controlled_mock_statuses.get('mock_executed', 0)} "
        f"mock_performed={controlled_mock_performed.get('true', 0)} "
        f"mock_subprocess_invoked={controlled_mock_subprocess_invoked.get('true', 0)} "
        f"mock_summaries={counts.get('mock_execution_summaries', 0)} "
        f"mock_summary_executed={mock_summary_statuses.get('mock_executed', 0)} "
        f"mock_summary_performed={mock_summary_performed.get('true', 0)} "
        f"mock_summary_subprocess_invoked={mock_summary_subprocess_invoked.get('true', 0)} "
        f"adapter_mock={controlled_mock_adapter.get('mock', 0)} "
        f"adapter_mode_mock={controlled_mock_adapter_mode.get('mock', 0)} "
        f"adapter_subprocess_invoked={controlled_mock_adapter_subprocess_invoked.get('true', 0)} "
        f"adapter_real_execution_enabled={controlled_mock_adapter_real_execution_enabled.get('true', 0)} "
        f"adapter_payload_executed={controlled_mock_adapter_payload_executed.get('true', 0)} "
        f"real_execution_requested={controlled_real_execution_requested.get('true', 0)} "
        f"real_execution_performed={controlled_real_execution_performed.get('true', 0)} "
        f"real_execution_supported={controlled_real_execution_supported.get('true', 0)} "
        f"subprocess_invoked={controlled_subprocess_invoked.get('true', 0)} "
        f"real_preflights={counts.get('real_execution_preflights', 0)} "
        f"real_preflight_blocked={real_preflight_statuses.get('blocked', 0)} "
        f"real_preflight_would_execute={real_preflight_would_execute.get('true', 0)} "
        f"real_preflight_execution_performed={real_preflight_execution_performed.get('true', 0)} "
        f"real_preflight_subprocess_invoked={real_preflight_subprocess_invoked.get('true', 0)} "
        f"real_preflight_requires_explicit_pr={real_preflight_requires_explicit_pr.get('true', 0)} "
        f"real_approvals={counts.get('real_execution_approvals', 0)} "
        f"real_approval_pending={real_approval_statuses.get('pending', 0)} "
        f"real_approval_approved={real_approval_statuses.get('approved', 0)} "
        f"real_approval_rejected={real_approval_statuses.get('rejected', 0)} "
        f"real_approval_enabled={real_approval_enabled.get('true', 0)} "
        f"real_approval_subprocess_enabled={real_approval_subprocess_enabled.get('true', 0)} "
        f"real_approval_execution_performed={real_approval_execution_performed.get('true', 0)} "
        f"real_approval_subprocess_invoked={real_approval_subprocess_invoked.get('true', 0)} "
        f"real_linkage_complete={str(bool(summary.get('real_linkage_complete'))).lower()} "
        f"real_preflight_orphans={summary.get('real_preflight_orphans', 0)} "
        f"real_approval_orphans={summary.get('real_approval_orphans', 0)} "
        f"real_dry_run_linkage_complete={str(bool(summary.get('real_dry_run_linkage_complete'))).lower()} "
        f"real_dry_run_envelope_orphans={summary.get('real_dry_run_envelope_orphans', 0)} "
        f"real_noop_linkage_complete={str(bool(summary.get('real_noop_linkage_complete'))).lower()} "
        f"real_noop_result_orphans={summary.get('real_noop_result_orphans', 0)} "
    )


def _real_linkage_summary(
    *,
    controlled_execution_results: list[Mapping[str, Any]],
    real_preflights: list[Mapping[str, Any]],
    real_approvals: list[Mapping[str, Any]],
) -> dict[str, Any]:
    
    def clean(value: Any) -> str:
        return str(value or "").strip()
    
    controlled_ids = {
        clean(item.get("controlled_execution_result_id"))
        for item in controlled_execution_results
        if clean(item.get("controlled_execution_result_id"))
    }
    rendered_ids = {
        clean(item.get("rendered_command_id"))
        for item in controlled_execution_results
        if clean(item.get("rendered_command_id"))
    }
    preflight_ids = {
        clean(item.get("real_execution_preflight_id"))
        for item in real_preflights
        if clean(item.get("real_execution_preflight_id"))
    }

    preflight_controlled_matches = 0
    preflight_rendered_matches = 0
    orphan_preflights = 0

    for preflight in real_preflights:
        controlled_id = clean(preflight.get("controlled_execution_result_id"))
        rendered_id = clean(preflight.get("rendered_command_id"))

        if controlled_id and controlled_id in controlled_ids:
            preflight_controlled_matches += 1
        else:
            orphan_preflights += 1

        if rendered_id and rendered_id in rendered_ids:
            preflight_rendered_matches += 1

    approval_preflight_matches = 0
    approval_controlled_matches = 0
    approval_rendered_matches = 0
    orphan_approvals = 0

    for approval in real_approvals:
        preflight_id = clean(approval.get("real_execution_preflight_id"))
        controlled_id = clean(approval.get("controlled_execution_result_id"))
        rendered_id = clean(approval.get("rendered_command_id"))

        if preflight_id and preflight_id in preflight_ids:
            approval_preflight_matches += 1
        else:
            orphan_approvals += 1

        if controlled_id and controlled_id in controlled_ids:
            approval_controlled_matches += 1

        if rendered_id and rendered_id in rendered_ids:
            approval_rendered_matches += 1

    return {
        "real_preflight_controlled_matches": preflight_controlled_matches,
        "real_preflight_rendered_matches": preflight_rendered_matches,
        "real_preflight_orphans": orphan_preflights,
        "real_approval_preflight_matches": approval_preflight_matches,
        "real_approval_controlled_matches": approval_controlled_matches,
        "real_approval_rendered_matches": approval_rendered_matches,
        "real_approval_orphans": orphan_approvals,
        "real_linkage_complete": (
            bool(real_preflights)
            and all(
                clean(item.get("controlled_execution_result_id")) in controlled_ids
                and clean(item.get("rendered_command_id")) in rendered_ids
                for item in real_preflights
            )
            and (
                not real_approvals
                or all(
                    clean(item.get("real_execution_preflight_id")) in preflight_ids
                    and clean(item.get("controlled_execution_result_id"))
                    in controlled_ids
                    and clean(item.get("rendered_command_id")) in rendered_ids
                    for item in real_approvals
                )
            )
        ),
    }


def _real_dry_run_linkage_summary(
    *,
    real_final_gates: list[Mapping[str, Any]],
    real_dry_run_envelopes: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    final_gate_ids = {
        clean(item.get("real_execution_final_gate_id"))
        for item in real_final_gates
        if clean(item.get("real_execution_final_gate_id"))
    }

    envelope_final_gate_matches = 0
    envelope_orphans = 0

    for envelope in real_dry_run_envelopes:
        final_gate_id = clean(envelope.get("real_execution_final_gate_id"))

        if final_gate_id and final_gate_id in final_gate_ids:
            envelope_final_gate_matches += 1
        else:
            envelope_orphans += 1

    return {
        "real_dry_run_envelope_final_gate_matches": envelope_final_gate_matches,
        "real_dry_run_envelope_orphans": envelope_orphans,
        "real_dry_run_linkage_complete": (
            bool(real_dry_run_envelopes)
            and envelope_orphans == 0
        ),
    }


def _real_noop_linkage_summary(
    *,
    real_dry_run_envelopes: list[Mapping[str, Any]],
    real_noop_results: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    dry_run_envelope_ids = {
        clean(item.get("real_execution_dry_run_envelope_id"))
        for item in real_dry_run_envelopes
        if clean(item.get("real_execution_dry_run_envelope_id"))
    }

    noop_dry_run_matches = 0
    noop_orphans = 0

    for noop_result in real_noop_results:
        envelope_id = clean(noop_result.get("real_execution_dry_run_envelope_id"))

        if envelope_id and envelope_id in dry_run_envelope_ids:
            noop_dry_run_matches += 1
        else:
            noop_orphans += 1

    return {
        "real_noop_result_dry_run_envelope_matches": noop_dry_run_matches,
        "real_noop_result_orphans": noop_orphans,
        "real_noop_linkage_complete": bool(real_noop_results)
        and noop_orphans == 0,
    }


def _real_read_only_promotion_linkage_summary(
    *,
    real_noop_results: list[Mapping[str, Any]],
    real_read_only_promotions: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    noop_result_ids = {
        clean(item.get("real_execution_noop_result_id"))
        for item in real_noop_results
        if clean(item.get("real_execution_noop_result_id"))
    }

    promotion_noop_matches = 0
    promotion_orphans = 0

    for promotion in real_read_only_promotions:
        noop_result_id = clean(promotion.get("real_execution_noop_result_id"))

        if noop_result_id and noop_result_id in noop_result_ids:
            promotion_noop_matches += 1
        else:
            promotion_orphans += 1

    return {
        "real_read_only_promotion_noop_matches": promotion_noop_matches,
        "real_read_only_promotion_orphans": promotion_orphans,
        "real_read_only_promotion_linkage_complete": bool(
            real_read_only_promotions
        )
        and promotion_orphans == 0,
    }


def _real_approval_latest_status(
    *,
    real_approvals: list[Mapping[str, Any]],
    real_approval_transitions: list[Mapping[str, Any]],
) -> str:
    if any(
        str(item.get("to_status") or "").strip().lower() == "rejected"
        for item in real_approval_transitions
    ):
        return "rejected"
    if any(
        str(item.get("to_status") or "").strip().lower() == "approved"
        for item in real_approval_transitions
    ):
        return "approved"
    if any(
        str(item.get("approval_status") or "").strip().lower() == "pending"
        for item in real_approvals
    ):
        return "pending"
    return "unknown"


def _real_read_only_final_gate_linkage_summary(
    *,
    real_read_only_promotions: list[Mapping[str, Any]],
    real_read_only_final_gates: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    promotion_ids = {
        clean(item.get("real_execution_read_only_promotion_id"))
        for item in real_read_only_promotions
        if clean(item.get("real_execution_read_only_promotion_id"))
    }

    gate_promotion_matches = 0
    gate_orphans = 0

    for gate in real_read_only_final_gates:
        promotion_id = clean(gate.get("real_execution_read_only_promotion_id"))

        if promotion_id and promotion_id in promotion_ids:
            gate_promotion_matches += 1
        else:
            gate_orphans += 1

    return {
        "real_read_only_final_gate_promotion_matches": gate_promotion_matches,
        "real_read_only_final_gate_orphans": gate_orphans,
        "real_read_only_final_gate_linkage_complete": bool(
            real_read_only_final_gates
        )
        and gate_orphans == 0,
    }


def _real_read_only_approval_linkage_summary(
    *,
    real_read_only_final_gates: list[Mapping[str, Any]],
    real_read_only_approvals: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    final_gate_ids = {
        clean(item.get("real_execution_read_only_final_gate_id"))
        for item in real_read_only_final_gates
        if clean(item.get("real_execution_read_only_final_gate_id"))
    }

    approval_final_gate_matches = 0
    approval_orphans = 0

    for approval in real_read_only_approvals:
        final_gate_id = clean(approval.get("real_execution_read_only_final_gate_id"))

        if final_gate_id and final_gate_id in final_gate_ids:
            approval_final_gate_matches += 1
        else:
            approval_orphans += 1

    return {
        "real_read_only_approval_final_gate_matches": approval_final_gate_matches,
        "real_read_only_approval_orphans": approval_orphans,
        "real_read_only_approval_linkage_complete": bool(real_read_only_approvals)
        and approval_orphans == 0,
    }


def _real_read_only_approval_latest_status(
    *,
    real_read_only_approvals: list[Mapping[str, Any]],
    real_read_only_approval_transitions: list[Mapping[str, Any]],
) -> str:
    if real_read_only_approval_transitions:
        latest = real_read_only_approval_transitions[-1]
        return str(latest.get("to_status") or "unknown").strip() or "unknown"

    if real_read_only_approvals:
        latest = real_read_only_approvals[-1]
        return str(latest.get("approval_status") or "unknown").strip() or "unknown"

    return "unknown"


def _real_read_only_approval_transition_linkage_summary(
    *,
    real_read_only_approvals: list[Mapping[str, Any]],
    real_read_only_approval_transitions: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    approval_ids = {
        clean(item.get("real_execution_read_only_approval_id"))
        for item in real_read_only_approvals
        if clean(item.get("real_execution_read_only_approval_id"))
    }

    transition_approval_matches = 0
    transition_orphans = 0

    for transition in real_read_only_approval_transitions:
        approval_id = clean(transition.get("real_execution_read_only_approval_id"))

        if approval_id and approval_id in approval_ids:
            transition_approval_matches += 1
        else:
            transition_orphans += 1

    return {
        "real_read_only_approval_transition_approval_matches": (
            transition_approval_matches
        ),
        "real_read_only_approval_transition_orphans": transition_orphans,
        "real_read_only_approval_transition_linkage_complete": bool(
            real_read_only_approval_transitions
        )
        and transition_orphans == 0,
    }


def _real_read_only_readiness_gate_linkage_summary(
    *,
    real_read_only_approval_transitions: list[Mapping[str, Any]],
    real_read_only_readiness_gates: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    transition_ids = {
        clean(item.get("real_execution_read_only_approval_transition_id"))
        for item in real_read_only_approval_transitions
        if clean(item.get("real_execution_read_only_approval_transition_id"))
    }

    gate_transition_matches = 0
    gate_orphans = 0

    for gate in real_read_only_readiness_gates:
        transition_id = clean(
            gate.get("real_execution_read_only_approval_transition_id")
        )

        if transition_id and transition_id in transition_ids:
            gate_transition_matches += 1
        else:
            gate_orphans += 1

    return {
        "real_read_only_readiness_gate_transition_matches": gate_transition_matches,
        "real_read_only_readiness_gate_orphans": gate_orphans,
        "real_read_only_readiness_gate_linkage_complete": bool(
            real_read_only_readiness_gates
        )
        and gate_orphans == 0,
    }


def _real_read_only_execution_result_linkage_summary(
    *,
    real_read_only_readiness_gates: list[Mapping[str, Any]],
    real_read_only_execution_results: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    gate_ids = {
        clean(item.get("real_execution_read_only_readiness_gate_id"))
        for item in real_read_only_readiness_gates
        if clean(item.get("real_execution_read_only_readiness_gate_id"))
    }

    result_gate_matches = 0
    result_orphans = 0

    for result in real_read_only_execution_results:
        gate_id = clean(result.get("real_execution_read_only_readiness_gate_id"))

        if gate_id and gate_id in gate_ids:
            result_gate_matches += 1
        else:
            result_orphans += 1

    return {
        "real_read_only_execution_result_gate_matches": result_gate_matches,
        "real_read_only_execution_result_orphans": result_orphans,
        "real_read_only_execution_result_linkage_complete": bool(
            real_read_only_execution_results
        )
        and result_orphans == 0,
    }


def _real_read_only_feedback_linkage_summary(
    *,
    real_read_only_execution_results: list[Mapping[str, Any]],
    real_read_only_feedback_records: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    result_ids = {
        clean(item.get("real_execution_read_only_execution_result_id"))
        for item in real_read_only_execution_results
        if clean(item.get("real_execution_read_only_execution_result_id"))
    }

    feedback_result_matches = 0
    feedback_orphans = 0

    for feedback in real_read_only_feedback_records:
        result_id = clean(
            feedback.get("real_execution_read_only_execution_result_id")
        )

        if result_id and result_id in result_ids:
            feedback_result_matches += 1
        else:
            feedback_orphans += 1

    return {
        "real_read_only_feedback_result_matches": feedback_result_matches,
        "real_read_only_feedback_orphans": feedback_orphans,
        "real_read_only_feedback_linkage_complete": bool(
            real_read_only_feedback_records
        )
        and feedback_orphans == 0,
    }


def _real_read_only_repair_plan_linkage_summary(
    *,
    real_read_only_feedback_records: list[Mapping[str, Any]],
    real_read_only_repair_plans: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    feedback_ids = {
        clean(item.get("real_execution_read_only_feedback_id"))
        for item in real_read_only_feedback_records
        if clean(item.get("real_execution_read_only_feedback_id"))
    }

    repair_feedback_matches = 0
    repair_orphans = 0

    for plan in real_read_only_repair_plans:
        feedback_id = clean(plan.get("real_execution_read_only_feedback_id"))
        if feedback_id and feedback_id in feedback_ids:
            repair_feedback_matches += 1
        else:
            repair_orphans += 1

    return {
        "real_read_only_repair_plan_feedback_matches": repair_feedback_matches,
        "real_read_only_repair_plan_orphans": repair_orphans,
        "real_read_only_repair_plan_linkage_complete": bool(
            real_read_only_repair_plans
        )
        and repair_orphans == 0,
    }


def _real_read_only_repair_action_bundle_linkage_summary(
    *,
    real_read_only_repair_plans: list[Mapping[str, Any]],
    real_read_only_repair_action_bundles: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    repair_plan_ids = {
        clean(item.get("real_execution_read_only_repair_plan_id"))
        for item in real_read_only_repair_plans
        if clean(item.get("real_execution_read_only_repair_plan_id"))
    }

    bundle_plan_matches = 0
    bundle_orphans = 0

    for bundle in real_read_only_repair_action_bundles:
        repair_plan_id = clean(bundle.get("real_execution_read_only_repair_plan_id"))
        if repair_plan_id and repair_plan_id in repair_plan_ids:
            bundle_plan_matches += 1
        else:
            bundle_orphans += 1

    return {
        "real_read_only_repair_action_bundle_plan_matches": bundle_plan_matches,
        "real_read_only_repair_action_bundle_orphans": bundle_orphans,
        "real_read_only_repair_action_bundle_linkage_complete": bool(
            real_read_only_repair_action_bundles
        )
        and bundle_orphans == 0,
    }


def _real_read_only_repair_action_bundle_review_linkage_summary(
    *,
    real_read_only_repair_action_bundles: list[Mapping[str, Any]],
    real_read_only_repair_action_bundle_reviews: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    bundle_ids = {
        clean(item.get("real_execution_read_only_repair_action_bundle_id"))
        for item in real_read_only_repair_action_bundles
        if clean(item.get("real_execution_read_only_repair_action_bundle_id"))
    }

    review_bundle_matches = 0
    review_orphans = 0

    for review in real_read_only_repair_action_bundle_reviews:
        bundle_id = clean(review.get("real_execution_read_only_repair_action_bundle_id"))
        if bundle_id and bundle_id in bundle_ids:
            review_bundle_matches += 1
        else:
            review_orphans += 1

    return {
        "real_read_only_repair_action_bundle_review_bundle_matches": (
            review_bundle_matches
        ),
        "real_read_only_repair_action_bundle_review_orphans": review_orphans,
        "real_read_only_repair_action_bundle_review_linkage_complete": bool(
            real_read_only_repair_action_bundle_reviews
        )
        and review_orphans == 0,
    }


def _real_repair_approval_linkage_summary(
    *,
    real_read_only_repair_action_bundle_reviews: list[Mapping[str, Any]],
    real_repair_approvals: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    review_ids = {
        clean(item.get("real_execution_read_only_repair_action_bundle_review_id"))
        for item in real_read_only_repair_action_bundle_reviews
        if clean(item.get("real_execution_read_only_repair_action_bundle_review_id"))
    }

    approval_review_matches = 0
    approval_orphans = 0

    for approval in real_repair_approvals:
        review_id = clean(
            approval.get("real_execution_read_only_repair_action_bundle_review_id")
        )
        if review_id and review_id in review_ids:
            approval_review_matches += 1
        else:
            approval_orphans += 1

    return {
        "real_repair_approval_review_matches": approval_review_matches,
        "real_repair_approval_orphans": approval_orphans,
        "real_repair_approval_linkage_complete": bool(real_repair_approvals)
        and approval_orphans == 0,
    }


def _real_repair_approval_transition_linkage_summary(
    *,
    real_repair_approvals: list[Mapping[str, Any]],
    real_repair_approval_transitions: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    approval_ids = {
        clean(item.get("real_execution_repair_approval_id"))
        for item in real_repair_approvals
        if clean(item.get("real_execution_repair_approval_id"))
    }

    transition_approval_matches = 0
    transition_orphans = 0

    for transition in real_repair_approval_transitions:
        approval_id = clean(transition.get("real_execution_repair_approval_id"))
        if approval_id and approval_id in approval_ids:
            transition_approval_matches += 1
        else:
            transition_orphans += 1

    return {
        "real_repair_approval_transition_approval_matches": (
            transition_approval_matches
        ),
        "real_repair_approval_transition_orphans": transition_orphans,
        "real_repair_approval_transition_linkage_complete": bool(
            real_repair_approval_transitions
        )
        and transition_orphans == 0,
    }


def _real_repair_final_gate_linkage_summary(
    *,
    real_repair_approval_transitions: list[Mapping[str, Any]],
    real_repair_final_gates: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    transition_ids = {
        clean(item.get("real_execution_repair_approval_transition_id"))
        for item in real_repair_approval_transitions
        if clean(item.get("real_execution_repair_approval_transition_id"))
    }

    gate_transition_matches = 0
    gate_orphans = 0

    for gate in real_repair_final_gates:
        transition_id = clean(gate.get("real_execution_repair_approval_transition_id"))
        if transition_id and transition_id in transition_ids:
            gate_transition_matches += 1
        else:
            gate_orphans += 1

    return {
        "real_repair_final_gate_transition_matches": gate_transition_matches,
        "real_repair_final_gate_orphans": gate_orphans,
        "real_repair_final_gate_linkage_complete": bool(real_repair_final_gates)
        and gate_orphans == 0,
    }


def _real_repair_dry_run_envelope_linkage_summary(
    *,
    real_repair_final_gates: list[Mapping[str, Any]],
    real_repair_dry_run_envelopes: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    final_gate_ids = {
        clean(item.get("real_execution_repair_final_gate_id"))
        for item in real_repair_final_gates
        if clean(item.get("real_execution_repair_final_gate_id"))
    }

    envelope_gate_matches = 0
    envelope_orphans = 0

    for envelope in real_repair_dry_run_envelopes:
        gate_id = clean(envelope.get("real_execution_repair_final_gate_id"))
        if gate_id and gate_id in final_gate_ids:
            envelope_gate_matches += 1
        else:
            envelope_orphans += 1

    return {
        "real_repair_dry_run_envelope_final_gate_matches": envelope_gate_matches,
        "real_repair_dry_run_envelope_orphans": envelope_orphans,
        "real_repair_dry_run_envelope_linkage_complete": bool(
            real_repair_dry_run_envelopes
        )
        and envelope_orphans == 0,
    }


def _real_repair_noop_result_linkage_summary(
    *,
    real_repair_dry_run_envelopes: list[Mapping[str, Any]],
    real_repair_noop_results: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    envelope_ids = {
        clean(item.get("real_execution_repair_dry_run_envelope_id"))
        for item in real_repair_dry_run_envelopes
        if clean(item.get("real_execution_repair_dry_run_envelope_id"))
    }

    result_envelope_matches = 0
    result_orphans = 0

    for result in real_repair_noop_results:
        envelope_id = clean(result.get("real_execution_repair_dry_run_envelope_id"))
        if envelope_id and envelope_id in envelope_ids:
            result_envelope_matches += 1
        else:
            result_orphans += 1

    return {
        "real_repair_noop_result_envelope_matches": result_envelope_matches,
        "real_repair_noop_result_orphans": result_orphans,
        "real_repair_noop_result_linkage_complete": bool(real_repair_noop_results)
        and result_orphans == 0,
    }


def _real_repair_noop_feedback_linkage_summary(
    *,
    real_repair_noop_results: list[Mapping[str, Any]],
    real_repair_noop_feedback_records: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    noop_result_ids = {
        clean(item.get("real_execution_repair_noop_result_id"))
        for item in real_repair_noop_results
        if clean(item.get("real_execution_repair_noop_result_id"))
    }

    feedback_result_matches = 0
    feedback_orphans = 0

    for feedback in real_repair_noop_feedback_records:
        result_id = clean(feedback.get("real_execution_repair_noop_result_id"))
        if result_id and result_id in noop_result_ids:
            feedback_result_matches += 1
        else:
            feedback_orphans += 1

    return {
        "real_repair_noop_feedback_result_matches": feedback_result_matches,
        "real_repair_noop_feedback_orphans": feedback_orphans,
        "real_repair_noop_feedback_linkage_complete": bool(
            real_repair_noop_feedback_records
        )
        and feedback_orphans == 0,
    }


def _real_repair_readiness_gate_linkage_summary(
    *,
    real_repair_noop_feedback_records: list[Mapping[str, Any]],
    real_repair_readiness_gates: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    feedback_ids = {
        clean(item.get("real_execution_repair_noop_feedback_id"))
        for item in real_repair_noop_feedback_records
        if clean(item.get("real_execution_repair_noop_feedback_id"))
    }

    gate_feedback_matches = 0
    gate_orphans = 0

    for gate in real_repair_readiness_gates:
        feedback_id = clean(gate.get("real_execution_repair_noop_feedback_id"))
        if feedback_id and feedback_id in feedback_ids:
            gate_feedback_matches += 1
        else:
            gate_orphans += 1

    return {
        "real_repair_readiness_gate_feedback_matches": gate_feedback_matches,
        "real_repair_readiness_gate_orphans": gate_orphans,
        "real_repair_readiness_gate_linkage_complete": bool(
            real_repair_readiness_gates
        )
        and gate_orphans == 0,
    }


def _guarded_repair_execution_linkage_summary(
    *,
    real_repair_readiness_gates: list[Mapping[str, Any]],
    guarded_repair_execution_results: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    gate_ids = {
        clean(item.get("real_execution_repair_readiness_gate_id"))
        for item in real_repair_readiness_gates
        if clean(item.get("real_execution_repair_readiness_gate_id"))
    }

    result_gate_matches = 0
    result_orphans = 0

    for result in guarded_repair_execution_results:
        gate_id = clean(result.get("real_execution_repair_readiness_gate_id"))
        if gate_id and gate_id in gate_ids:
            result_gate_matches += 1
        else:
            result_orphans += 1

    return {
        "guarded_repair_execution_gate_matches": result_gate_matches,
        "guarded_repair_execution_orphans": result_orphans,
        "guarded_repair_execution_linkage_complete": bool(
            guarded_repair_execution_results
        )
        and result_orphans == 0,
    }


def _post_repair_evidence_linkage_summary(
    *,
    guarded_repair_execution_results: list[Mapping[str, Any]],
    post_repair_evidence_checks: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    guarded_result_ids = {
        clean(item.get("guarded_repair_execution_result_id"))
        for item in guarded_repair_execution_results
        if clean(item.get("guarded_repair_execution_result_id"))
    }

    check_result_matches = 0
    check_orphans = 0

    for check in post_repair_evidence_checks:
        result_id = clean(check.get("guarded_repair_execution_result_id"))
        if result_id and result_id in guarded_result_ids:
            check_result_matches += 1
        else:
            check_orphans += 1

    return {
        "post_repair_evidence_guarded_result_matches": check_result_matches,
        "post_repair_evidence_orphans": check_orphans,
        "post_repair_evidence_linkage_complete": bool(post_repair_evidence_checks)
        and check_orphans == 0,
    }


def _real_execution_adapter_contract_linkage_summary(
    *,
    post_repair_evidence_checks: list[Mapping[str, Any]],
    real_execution_adapter_contracts: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    post_repair_ids = {
        clean(item.get("post_repair_evidence_check_id"))
        for item in post_repair_evidence_checks
        if clean(item.get("post_repair_evidence_check_id"))
    }

    contract_post_repair_matches = 0
    contract_orphans = 0

    for contract in real_execution_adapter_contracts:
        check_id = clean(contract.get("post_repair_evidence_check_id"))
        if check_id and check_id in post_repair_ids:
            contract_post_repair_matches += 1
        else:
            contract_orphans += 1

    return {
        "real_execution_adapter_contract_post_repair_matches": (
            contract_post_repair_matches
        ),
        "real_execution_adapter_contract_orphans": contract_orphans,
        "real_execution_adapter_contract_linkage_complete": bool(
            real_execution_adapter_contracts
        )
        and contract_orphans == 0,
    }


def _real_execution_adapter_request_schema_linkage_summary(
    *,
    real_execution_adapter_contracts: list[Mapping[str, Any]],
    real_execution_adapter_request_schemas: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    contract_ids = {
        clean(item.get("real_execution_adapter_contract_id"))
        for item in real_execution_adapter_contracts
        if clean(item.get("real_execution_adapter_contract_id"))
    }

    request_schema_contract_matches = 0
    request_schema_orphans = 0

    for schema in real_execution_adapter_request_schemas:
        contract_id = clean(schema.get("real_execution_adapter_contract_id"))
        if contract_id and contract_id in contract_ids:
            request_schema_contract_matches += 1
        else:
            request_schema_orphans += 1

    return {
        "real_execution_adapter_request_schema_contract_matches": (
            request_schema_contract_matches
        ),
        "real_execution_adapter_request_schema_orphans": request_schema_orphans,
        "real_execution_adapter_request_schema_linkage_complete": bool(
            real_execution_adapter_request_schemas
        )
        and request_schema_orphans == 0,
    }


def _real_execution_capability_policy_matrix_linkage_summary(
    *,
    real_execution_adapter_request_schemas: list[Mapping[str, Any]],
    real_execution_capability_policy_matrices: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    request_schema_ids = {
        clean(item.get("real_execution_adapter_request_schema_id"))
        for item in real_execution_adapter_request_schemas
        if clean(item.get("real_execution_adapter_request_schema_id"))
    }

    matrix_request_schema_matches = 0
    matrix_orphans = 0

    for matrix in real_execution_capability_policy_matrices:
        request_schema_id = clean(matrix.get("real_execution_adapter_request_schema_id"))
        if request_schema_id and request_schema_id in request_schema_ids:
            matrix_request_schema_matches += 1
        else:
            matrix_orphans += 1

    return {
        "real_execution_capability_policy_matrix_request_schema_matches": (
            matrix_request_schema_matches
        ),
        "real_execution_capability_policy_matrix_orphans": matrix_orphans,
        "real_execution_capability_policy_matrix_linkage_complete": bool(
            real_execution_capability_policy_matrices
        )
        and matrix_orphans == 0,
    }


def _real_execution_sandbox_adapter_scaffold_linkage_summary(
    *,
    real_execution_capability_policy_matrices: list[Mapping[str, Any]],
    real_execution_sandbox_adapter_scaffolds: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    matrix_ids = {
        clean(item.get("real_execution_capability_policy_matrix_id"))
        for item in real_execution_capability_policy_matrices
        if clean(item.get("real_execution_capability_policy_matrix_id"))
    }

    scaffold_matrix_matches = 0
    scaffold_orphans = 0

    for scaffold in real_execution_sandbox_adapter_scaffolds:
        matrix_id = clean(scaffold.get("real_execution_capability_policy_matrix_id"))
        if matrix_id and matrix_id in matrix_ids:
            scaffold_matrix_matches += 1
        else:
            scaffold_orphans += 1

    return {
        "real_execution_sandbox_adapter_scaffold_matrix_matches": (
            scaffold_matrix_matches
        ),
        "real_execution_sandbox_adapter_scaffold_orphans": scaffold_orphans,
        "real_execution_sandbox_adapter_scaffold_linkage_complete": bool(
            real_execution_sandbox_adapter_scaffolds
        )
        and scaffold_orphans == 0,
    }


def _real_execution_sandbox_adapter_request_preflight_linkage_summary(
    *,
    real_execution_sandbox_adapter_scaffolds: list[Mapping[str, Any]],
    real_execution_sandbox_adapter_request_preflights: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    scaffold_ids = {
        clean(item.get("real_execution_sandbox_adapter_scaffold_id"))
        for item in real_execution_sandbox_adapter_scaffolds
        if clean(item.get("real_execution_sandbox_adapter_scaffold_id"))
    }

    preflight_scaffold_matches = 0
    preflight_orphans = 0

    for preflight in real_execution_sandbox_adapter_request_preflights:
        scaffold_id = clean(preflight.get("real_execution_sandbox_adapter_scaffold_id"))
        if scaffold_id and scaffold_id in scaffold_ids:
            preflight_scaffold_matches += 1
        else:
            preflight_orphans += 1

    return {
        "real_execution_sandbox_adapter_request_preflight_scaffold_matches": (
            preflight_scaffold_matches
        ),
        "real_execution_sandbox_adapter_request_preflight_orphans": (
            preflight_orphans
        ),
        "real_execution_sandbox_adapter_request_preflight_linkage_complete": bool(
            real_execution_sandbox_adapter_request_preflights
        )
        and preflight_orphans == 0,
    }


def _real_execution_sandbox_request_envelope_scaffold_linkage_summary(
    *,
    real_execution_sandbox_adapter_request_preflights: list[Mapping[str, Any]],
    real_execution_sandbox_request_envelope_scaffolds: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    preflight_ids = {
        clean(item.get("real_execution_sandbox_adapter_request_preflight_id"))
        for item in real_execution_sandbox_adapter_request_preflights
        if clean(item.get("real_execution_sandbox_adapter_request_preflight_id"))
    }

    envelope_preflight_matches = 0
    envelope_orphans = 0

    for envelope in real_execution_sandbox_request_envelope_scaffolds:
        preflight_id = clean(
            envelope.get("real_execution_sandbox_adapter_request_preflight_id")
        )
        if preflight_id and preflight_id in preflight_ids:
            envelope_preflight_matches += 1
        else:
            envelope_orphans += 1

    return {
        "real_execution_sandbox_request_envelope_scaffold_preflight_matches": (
            envelope_preflight_matches
        ),
        "real_execution_sandbox_request_envelope_scaffold_orphans": (
            envelope_orphans
        ),
        "real_execution_sandbox_request_envelope_scaffold_linkage_complete": bool(
            real_execution_sandbox_request_envelope_scaffolds
        )
        and envelope_orphans == 0,
    }


def _real_execution_sandbox_materialization_preflight_scaffold_linkage_summary(
    *,
    real_execution_sandbox_request_envelope_scaffolds: list[Mapping[str, Any]],
    real_execution_sandbox_materialization_preflight_scaffolds: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    envelope_ids = {
        clean(item.get("real_execution_sandbox_request_envelope_scaffold_id"))
        for item in real_execution_sandbox_request_envelope_scaffolds
        if clean(item.get("real_execution_sandbox_request_envelope_scaffold_id"))
    }

    materialization_envelope_matches = 0
    materialization_orphans = 0

    for materialization in real_execution_sandbox_materialization_preflight_scaffolds:
        envelope_id = clean(
            materialization.get("real_execution_sandbox_request_envelope_scaffold_id")
        )
        if envelope_id and envelope_id in envelope_ids:
            materialization_envelope_matches += 1
        else:
            materialization_orphans += 1

    return {
        "real_execution_sandbox_materialization_preflight_scaffold_envelope_matches": (
            materialization_envelope_matches
        ),
        "real_execution_sandbox_materialization_preflight_scaffold_orphans": (
            materialization_orphans
        ),
        "real_execution_sandbox_materialization_preflight_scaffold_linkage_complete": bool(
            real_execution_sandbox_materialization_preflight_scaffolds
        )
        and materialization_orphans == 0,
    }


def _real_execution_sandbox_workspace_plan_scaffold_linkage_summary(
    *,
    real_execution_sandbox_materialization_preflight_scaffolds: list[
        Mapping[str, Any]
    ],
    real_execution_sandbox_workspace_plan_scaffolds: list[Mapping[str, Any]],
) -> dict[str, Any]:
    def clean(value: Any) -> str:
        return str(value or "").strip()

    materialization_ids = {
        clean(
            item.get(
                "real_execution_sandbox_materialization_preflight_scaffold_id"
            )
        )
        for item in real_execution_sandbox_materialization_preflight_scaffolds
        if clean(
            item.get(
                "real_execution_sandbox_materialization_preflight_scaffold_id"
            )
        )
    }

    workspace_plan_materialization_matches = 0
    workspace_plan_orphans = 0

    for workspace_plan in real_execution_sandbox_workspace_plan_scaffolds:
        materialization_id = clean(
            workspace_plan.get(
                "real_execution_sandbox_materialization_preflight_scaffold_id"
            )
        )
        if materialization_id and materialization_id in materialization_ids:
            workspace_plan_materialization_matches += 1
        else:
            workspace_plan_orphans += 1

    return {
        "real_execution_sandbox_workspace_plan_scaffold_materialization_matches": (
            workspace_plan_materialization_matches
        ),
        "real_execution_sandbox_workspace_plan_scaffold_orphans": (
            workspace_plan_orphans
        ),
        "real_execution_sandbox_workspace_plan_scaffold_linkage_complete": bool(
            real_execution_sandbox_workspace_plan_scaffolds
        )
        and workspace_plan_orphans == 0,
    }


def _exit_code_for_summary(
    summary: Mapping[str, Any],
    *,
    require_complete: bool = False,
) -> int:
    if require_complete and not bool(summary.get("chain_complete")):
        return 1
    return 0


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    args = build_parser().parse_args()
    summary = inspect_retry_governance_trail(args)

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(_format_summary(summary))

    raise SystemExit(
        _exit_code_for_summary(
            summary,
            require_complete=bool(getattr(args, "require_complete", False)),
        )
    )


if __name__ == "__main__":
    main()