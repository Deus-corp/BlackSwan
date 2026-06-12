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