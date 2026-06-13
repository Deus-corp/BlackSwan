"""Final pre-execution readiness report for controlled retry execution.

This helper is read-only. It aggregates the safe retry governance trail,
controlled execution observability, and controlled gate state before any
execution adapter is introduced.
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any, Mapping

from src.testing.check_controlled_retry_execution_observability import (
    _exit_code_for_result as controlled_observability_exit_code,
    check_controlled_retry_execution_observability,
)
from src.testing.check_retry_governance_observability import (
    _exit_code_for_result as retry_observability_exit_code,
    check_retry_governance_observability,
)
from src.testing.inspect_retry_governance_trail import (
    _exit_code_for_summary as trail_exit_code,
    inspect_retry_governance_trail,
)
from src.testing.controlled_retry_execution_adapter import (
    describe_controlled_retry_execution_adapter_contract,
)
from swarm_config import config

logger = logging.getLogger(__name__)


READINESS_SCHEMA_VERSION = "controlled-execution-readiness/v1"


def check_controlled_execution_readiness(args: argparse.Namespace) -> dict[str, Any]:
    """Build a read-only final pre-execution readiness report."""
    db_path = str(args.db_path or config.crdt_db_path)
    proposal_id = str(getattr(args, "proposal_id", "") or "").strip()
    rendered_command_id = str(getattr(args, "rendered_command_id", "") or "").strip()
    require_operator_authorized = bool(
        getattr(args, "require_operator_authorized", False)
    )

    trail_summary = inspect_retry_governance_trail(
        argparse.Namespace(
            db_path=db_path,
            proposal_id=proposal_id,
            approval_id="",
            plan_id="",
        )
    )
    retry_observability = check_retry_governance_observability(
        argparse.Namespace(
            db_path=db_path,
            proposal_id=proposal_id,
            json=False,
        )
    )
    controlled_observability = check_controlled_retry_execution_observability(
        argparse.Namespace(
            db_path=db_path,
            rendered_command_id=rendered_command_id,
            plan_id="",
            proposal_id=proposal_id,
            json=False,
        )
    )

    checks = _build_checks(
        trail_summary=trail_summary,
        retry_observability=retry_observability,
        controlled_observability=controlled_observability,
        require_operator_authorized=require_operator_authorized,
    )
    failed_checks = [item for item in checks if item.get("status") != "passed"]

    ready_for_mock_execution = not failed_checks
    ready_for_real_execution = False

    blocking_reasons = [str(item.get("name")) for item in failed_checks]
    if ready_for_mock_execution:
        blocking_reasons.append("real_execution_not_supported_yet")

    controlled_mock_statuses = _safe_mapping(
        trail_summary.get("controlled_mock_statuses")
    )
    controlled_mock_performed = _safe_mapping(
        trail_summary.get("controlled_mock_performed")
    )
    controlled_mock_subprocess_invoked = _safe_mapping(
        trail_summary.get("controlled_mock_subprocess_invoked")
    )
    mock_summary_statuses = _safe_mapping(
        trail_summary.get("mock_summary_statuses")
    )
    mock_summary_performed = _safe_mapping(
        trail_summary.get("mock_summary_performed")
    )
    mock_summary_subprocess_invoked = _safe_mapping(
        trail_summary.get("mock_summary_subprocess_invoked")
    )
    controlled_mock_adapter = _safe_mapping(
        trail_summary.get("controlled_mock_adapter")
    )
    controlled_mock_adapter_mode = _safe_mapping(
        trail_summary.get("controlled_mock_adapter_mode")
    )
    controlled_mock_adapter_result_statuses = _safe_mapping(
        trail_summary.get("controlled_mock_adapter_result_statuses")
    )
    controlled_mock_adapter_subprocess_invoked = _safe_mapping(
        trail_summary.get("controlled_mock_adapter_subprocess_invoked")
    )
    controlled_mock_adapter_real_execution_enabled = _safe_mapping(
        trail_summary.get("controlled_mock_adapter_real_execution_enabled")
    )
    controlled_mock_adapter_payload_executed = _safe_mapping(
        trail_summary.get("controlled_mock_adapter_payload_executed")
    )
    controlled_real_execution_requested = _safe_mapping(
        trail_summary.get("controlled_real_execution_requested")
    )
    controlled_real_execution_performed = _safe_mapping(
        trail_summary.get("controlled_real_execution_performed")
    )
    controlled_real_execution_supported = _safe_mapping(
        trail_summary.get("controlled_real_execution_supported")
    )
    controlled_subprocess_invoked = _safe_mapping(
        trail_summary.get("controlled_subprocess_invoked")
    )
    controlled_reasons = _safe_mapping(
        trail_summary.get("controlled_execution_result_reasons")
    )
    real_preflight_statuses = _safe_mapping(
        trail_summary.get("real_preflight_statuses")
    )
    real_preflight_reasons = _safe_mapping(
        trail_summary.get("real_preflight_reasons")
    )
    real_preflight_would_execute = _safe_mapping(
        trail_summary.get("real_preflight_would_execute")
    )
    real_preflight_execution_performed = _safe_mapping(
        trail_summary.get("real_preflight_execution_performed")
    )
    real_preflight_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_preflight_subprocess_invoked")
    )
    real_preflight_requires_explicit_pr = _safe_mapping(
        trail_summary.get("real_preflight_requires_explicit_pr")
    )
    real_approval_statuses = _safe_mapping(
        trail_summary.get("real_approval_statuses")
    )
    real_approval_enabled = _safe_mapping(
        trail_summary.get("real_approval_enabled")
    )
    real_approval_subprocess_enabled = _safe_mapping(
        trail_summary.get("real_approval_subprocess_enabled")
    )
    real_approval_execution_performed = _safe_mapping(
        trail_summary.get("real_approval_execution_performed")
    )
    real_approval_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_approval_subprocess_invoked")
    )
    real_approval_transition_statuses = _safe_mapping(
        trail_summary.get("real_approval_transition_statuses")
    )
    real_approval_transition_enabled = _safe_mapping(
        trail_summary.get("real_approval_transition_enabled")
    )
    real_approval_transition_subprocess_enabled = _safe_mapping(
        trail_summary.get("real_approval_transition_subprocess_enabled")
    )
    real_approval_transition_execution_performed = _safe_mapping(
        trail_summary.get("real_approval_transition_execution_performed")
    )
    real_approval_transition_subprocess_invoked = _safe_mapping(
       trail_summary.get("real_approval_transition_subprocess_invoked")
    )
    real_final_gate_statuses = _safe_mapping(
        trail_summary.get("real_final_gate_statuses")
    )
    real_final_gate_would_execute = _safe_mapping(
        trail_summary.get("real_final_gate_would_execute")
    )
    real_final_gate_ready = _safe_mapping(
        trail_summary.get("real_final_gate_ready")
    )
    real_final_gate_real_execution_enabled = _safe_mapping(
        trail_summary.get("real_final_gate_real_execution_enabled")
    )
    real_final_gate_subprocess_enabled = _safe_mapping(
        trail_summary.get("real_final_gate_subprocess_enabled")
    )
    real_final_gate_execution_performed = _safe_mapping(
        trail_summary.get("real_final_gate_execution_performed")
    )
    real_final_gate_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_final_gate_subprocess_invoked")
    )
    real_dry_run_envelope_dry_run_only = _safe_mapping(
        trail_summary.get("real_dry_run_envelope_dry_run_only")
    )
    real_dry_run_envelope_would_execute = _safe_mapping(
        trail_summary.get("real_dry_run_envelope_would_execute")
    )
    real_dry_run_envelope_ready = _safe_mapping(
        trail_summary.get("real_dry_run_envelope_ready")
    )
    real_dry_run_envelope_real_execution_enabled = _safe_mapping(
        trail_summary.get("real_dry_run_envelope_real_execution_enabled")
    )
    real_dry_run_envelope_subprocess_enabled = _safe_mapping(
        trail_summary.get("real_dry_run_envelope_subprocess_enabled")
    )
    real_dry_run_envelope_execution_performed = _safe_mapping(
        trail_summary.get("real_dry_run_envelope_execution_performed")
    )
    real_dry_run_envelope_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_dry_run_envelope_subprocess_invoked")
    )
    real_noop_result_stdout_marker_observed = _safe_mapping(
        trail_summary.get("real_noop_result_stdout_marker_observed")
    )
    real_noop_result_noop_only = _safe_mapping(
        trail_summary.get("real_noop_result_noop_only")
    )
    real_noop_result_rendered_command_executed = _safe_mapping(
        trail_summary.get("real_noop_result_rendered_command_executed")
    )
    real_noop_result_dry_run_command_executed = _safe_mapping(
        trail_summary.get("real_noop_result_dry_run_command_executed")
    )
    real_noop_result_real_execution_enabled = _safe_mapping(
        trail_summary.get("real_noop_result_real_execution_enabled")
    )
    real_noop_result_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_noop_result_subprocess_invoked")
    )
    real_noop_result_execution_performed = _safe_mapping(
        trail_summary.get("real_noop_result_execution_performed")
    )
    real_noop_result_exit_codes = _safe_mapping(
        trail_summary.get("real_noop_result_exit_codes")
    )
    real_noop_result_stdout_marker_observed = _safe_mapping(
        trail_summary.get("real_noop_result_stdout_marker_observed")
    )
    real_read_only_final_gate_statuses = _safe_mapping(
        trail_summary.get("real_read_only_final_gate_statuses")
    )
    real_read_only_final_gate_preconditions_satisfied = _safe_mapping(
        trail_summary.get("real_read_only_final_gate_preconditions_satisfied")
    )
    real_read_only_final_gate_ready = _safe_mapping(
        trail_summary.get("real_read_only_final_gate_ready")
    )
    real_read_only_final_gate_would_execute = _safe_mapping(
        trail_summary.get("real_read_only_final_gate_would_execute")
    )
    real_read_only_final_gate_read_only_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_final_gate_read_only_execution_enabled")
    )
    real_read_only_final_gate_real_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_final_gate_real_execution_enabled")
    )
    real_read_only_final_gate_subprocess_enabled = _safe_mapping(
        trail_summary.get("real_read_only_final_gate_subprocess_enabled")
    )
    real_read_only_final_gate_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_final_gate_subprocess_invoked")
    )
    real_read_only_final_gate_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_final_gate_execution_performed")
    )
    real_read_only_final_gate_rendered_command_executed = _safe_mapping(
        trail_summary.get("real_read_only_final_gate_rendered_command_executed")
    )
    real_read_only_final_gate_dry_run_command_executed = _safe_mapping(
        trail_summary.get("real_read_only_final_gate_dry_run_command_executed")
    )
    real_read_only_approval_statuses = _safe_mapping(
        trail_summary.get("real_read_only_approval_statuses")
    )
    real_read_only_approval_read_only_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_approval_read_only_execution_enabled")
    )
    real_read_only_approval_real_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_approval_real_execution_enabled")
    )
    real_read_only_approval_subprocess_enabled = _safe_mapping(
        trail_summary.get("real_read_only_approval_subprocess_enabled")
    )
    real_read_only_approval_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_approval_subprocess_invoked")
    )
    real_read_only_approval_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_approval_execution_performed")
    )
    real_read_only_approval_rendered_command_executed = _safe_mapping(
        trail_summary.get("real_read_only_approval_rendered_command_executed")
    )
    real_read_only_approval_dry_run_command_executed = _safe_mapping(
        trail_summary.get("real_read_only_approval_dry_run_command_executed")
    )
    real_read_only_approval_transition_from_statuses = _safe_mapping(
        trail_summary.get("real_read_only_approval_transition_from_statuses")
    )
    real_read_only_approval_transition_to_statuses = _safe_mapping(
        trail_summary.get("real_read_only_approval_transition_to_statuses")
    )
    real_read_only_approval_transition_read_only_execution_enabled = _safe_mapping(
        trail_summary.get(
            "real_read_only_approval_transition_read_only_execution_enabled"
        )
    )
    real_read_only_approval_transition_real_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_approval_transition_real_execution_enabled")
    )
    real_read_only_approval_transition_subprocess_enabled = _safe_mapping(
        trail_summary.get("real_read_only_approval_transition_subprocess_enabled")
    )
    real_read_only_approval_transition_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_approval_transition_subprocess_invoked")
    )
    real_read_only_approval_transition_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_approval_transition_execution_performed")
    )
    real_read_only_approval_transition_rendered_command_executed = _safe_mapping(
        trail_summary.get(
            "real_read_only_approval_transition_rendered_command_executed"
        )
    )
    real_read_only_approval_transition_dry_run_command_executed = _safe_mapping(
        trail_summary.get(
            "real_read_only_approval_transition_dry_run_command_executed"
        )
    )
    real_read_only_readiness_gate_statuses = _safe_mapping(
        trail_summary.get("real_read_only_readiness_gate_statuses")
    )
    real_read_only_readiness_gate_satisfied = _safe_mapping(
        trail_summary.get("real_read_only_readiness_gate_satisfied")
    )
    real_read_only_readiness_gate_ready = _safe_mapping(
        trail_summary.get("real_read_only_readiness_gate_ready")
    )
    real_read_only_readiness_gate_read_only_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_readiness_gate_read_only_execution_enabled")
    )
    real_read_only_readiness_gate_real_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_readiness_gate_real_execution_enabled")
    )
    real_read_only_readiness_gate_subprocess_enabled = _safe_mapping(
        trail_summary.get("real_read_only_readiness_gate_subprocess_enabled")
    )
    real_read_only_readiness_gate_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_readiness_gate_subprocess_invoked")
    )
    real_read_only_readiness_gate_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_readiness_gate_execution_performed")
    )
    real_read_only_readiness_gate_rendered_command_executed = _safe_mapping(
        trail_summary.get("real_read_only_readiness_gate_rendered_command_executed")
    )
    real_read_only_readiness_gate_dry_run_command_executed = _safe_mapping(
        trail_summary.get("real_read_only_readiness_gate_dry_run_command_executed")
    )
    real_read_only_execution_result_statuses = _safe_mapping(
        trail_summary.get("real_read_only_execution_result_statuses")
    )
    real_read_only_execution_result_exit_codes = _safe_mapping(
        trail_summary.get("real_read_only_execution_result_exit_codes")
    )
    real_read_only_execution_result_validation_reasons_empty = _safe_mapping(
        trail_summary.get("real_read_only_execution_result_validation_reasons_empty")
    )
    real_read_only_execution_result_operator_authorized = _safe_mapping(
        trail_summary.get("real_read_only_execution_result_operator_authorized")
    )
    real_read_only_execution_result_allow_guarded = _safe_mapping(
        trail_summary.get("real_read_only_execution_result_allow_guarded")
    )
    real_read_only_execution_result_read_only_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_execution_result_read_only_execution_enabled")
    )
    real_read_only_execution_result_real_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_execution_result_real_execution_enabled")
    )
    real_read_only_execution_result_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_execution_result_subprocess_invoked")
    )
    real_read_only_execution_result_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_execution_result_execution_performed")
    )
    real_read_only_execution_result_read_only_command_executed = _safe_mapping(
        trail_summary.get("real_read_only_execution_result_read_only_command_executed")
    )
    real_read_only_execution_result_rendered_command_executed = _safe_mapping(
        trail_summary.get("real_read_only_execution_result_rendered_command_executed")
    )
    real_read_only_execution_result_dry_run_command_executed = _safe_mapping(
        trail_summary.get("real_read_only_execution_result_dry_run_command_executed")
    )
    real_read_only_feedback_statuses = _safe_mapping(
        trail_summary.get("real_read_only_feedback_statuses")
    )
    real_read_only_feedback_source_statuses = _safe_mapping(
        trail_summary.get("real_read_only_feedback_source_statuses")
    )
    real_read_only_feedback_source_exit_codes = _safe_mapping(
        trail_summary.get("real_read_only_feedback_source_exit_codes")
    )
    real_read_only_feedback_next_actions = _safe_mapping(
        trail_summary.get("real_read_only_feedback_next_actions")
    )
    real_read_only_feedback_execution_observed = _safe_mapping(
        trail_summary.get("real_read_only_feedback_execution_observed")
    )
    real_read_only_feedback_failed = _safe_mapping(
        trail_summary.get("real_read_only_feedback_failed")
    )
    real_read_only_feedback_real_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_feedback_real_execution_enabled")
    )
    real_read_only_feedback_feedback_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_feedback_feedback_execution_performed")
    )
    real_read_only_feedback_feedback_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_feedback_feedback_subprocess_invoked")
    )
    real_read_only_feedback_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_feedback_execution_performed")
    )
    real_read_only_feedback_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_feedback_subprocess_invoked")
    )
    real_read_only_repair_plan_statuses = _safe_mapping(
        trail_summary.get("real_read_only_repair_plan_statuses")
    )
    real_read_only_repair_plan_source_feedback_statuses = _safe_mapping(
        trail_summary.get("real_read_only_repair_plan_source_feedback_statuses")
    )
    real_read_only_repair_plan_source_statuses = _safe_mapping(
        trail_summary.get("real_read_only_repair_plan_source_statuses")
    )
    real_read_only_repair_plan_source_exit_codes = _safe_mapping(
        trail_summary.get("real_read_only_repair_plan_source_exit_codes")
    )
    real_read_only_repair_plan_next_actions = _safe_mapping(
        trail_summary.get("real_read_only_repair_plan_next_actions")
    )
    real_read_only_repair_plan_item_counts = _safe_mapping(
        trail_summary.get("real_read_only_repair_plan_item_counts")
    )
    real_read_only_repair_plan_requires_operator_review = _safe_mapping(
        trail_summary.get("real_read_only_repair_plan_requires_operator_review")
    )
    real_read_only_repair_plan_repair_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_repair_plan_repair_execution_enabled")
    )
    real_read_only_repair_plan_real_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_repair_plan_real_execution_enabled")
    )
    real_read_only_repair_plan_subprocess_enabled = _safe_mapping(
        trail_summary.get("real_read_only_repair_plan_subprocess_enabled")
    )
    real_read_only_repair_plan_repair_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_repair_plan_repair_execution_performed")
    )
    real_read_only_repair_plan_repair_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_repair_plan_repair_subprocess_invoked")
    )
    real_read_only_repair_plan_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_repair_plan_execution_performed")
    )
    real_read_only_repair_plan_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_repair_plan_subprocess_invoked")
    )
    real_read_only_repair_action_bundle_statuses = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_statuses")
    )
    real_read_only_repair_action_bundle_source_plan_statuses = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_source_plan_statuses")
    )
    real_read_only_repair_action_bundle_source_feedback_statuses = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_source_feedback_statuses")
    )
    real_read_only_repair_action_bundle_source_statuses = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_source_statuses")
    )
    real_read_only_repair_action_bundle_source_exit_codes = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_source_exit_codes")
    )
    real_read_only_repair_action_bundle_next_actions = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_next_actions")
    )
    real_read_only_repair_action_bundle_item_counts = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_item_counts")
    )
    real_read_only_repair_action_bundle_source_item_counts = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_source_item_counts")
    )
    real_read_only_repair_action_bundle_requires_operator_review = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_requires_operator_review")
    )
    real_read_only_repair_action_bundle_reviewed = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_reviewed")
    )
    real_read_only_repair_action_bundle_bundle_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_bundle_execution_enabled")
    )
    real_read_only_repair_action_bundle_repair_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_repair_execution_enabled")
    )
    real_read_only_repair_action_bundle_real_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_real_execution_enabled")
    )
    real_read_only_repair_action_bundle_subprocess_enabled = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_subprocess_enabled")
    )
    real_read_only_repair_action_bundle_bundle_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_bundle_execution_performed")
    )
    real_read_only_repair_action_bundle_bundle_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_bundle_subprocess_invoked")
    )
    real_read_only_repair_action_bundle_repair_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_repair_execution_performed")
    )
    real_read_only_repair_action_bundle_repair_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_repair_subprocess_invoked")
    )
    real_read_only_repair_action_bundle_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_execution_performed")
    )
    real_read_only_repair_action_bundle_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_subprocess_invoked")
    )
    real_read_only_repair_action_bundle_review_statuses = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_statuses")
    )
    real_read_only_repair_action_bundle_review_source_bundle_statuses = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_source_bundle_statuses")
    )
    real_read_only_repair_action_bundle_review_source_plan_statuses = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_source_plan_statuses")
    )
    real_read_only_repair_action_bundle_review_source_feedback_statuses = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_source_feedback_statuses")
    )
    real_read_only_repair_action_bundle_review_source_statuses = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_source_statuses")
    )
    real_read_only_repair_action_bundle_review_source_exit_codes = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_source_exit_codes")
    )
    real_read_only_repair_action_bundle_review_source_item_counts = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_source_item_counts")
    )
    real_read_only_repair_action_bundle_review_next_actions = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_next_actions")
    )
    real_read_only_repair_action_bundle_review_operator_authorized = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_operator_authorized")
    )
    real_read_only_repair_action_bundle_review_requires_operator_review = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_requires_operator_review")
    )
    real_read_only_repair_action_bundle_review_reviewed = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_reviewed")
    )
    real_read_only_repair_action_bundle_review_approved = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_approved")
    )
    real_read_only_repair_action_bundle_review_rejected = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_rejected")
    )
    real_read_only_repair_action_bundle_review_bundle_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_bundle_execution_enabled")
    )
    real_read_only_repair_action_bundle_review_repair_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_repair_execution_enabled")
    )
    real_read_only_repair_action_bundle_review_real_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_real_execution_enabled")
    )
    real_read_only_repair_action_bundle_review_subprocess_enabled = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_subprocess_enabled")
    )
    real_read_only_repair_action_bundle_review_bundle_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_bundle_execution_performed")
    )
    real_read_only_repair_action_bundle_review_bundle_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_bundle_subprocess_invoked")
    )
    real_read_only_repair_action_bundle_review_repair_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_repair_execution_performed")
    )
    real_read_only_repair_action_bundle_review_repair_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_repair_subprocess_invoked")
    )
    real_read_only_repair_action_bundle_review_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_execution_performed")
    )
    real_read_only_repair_action_bundle_review_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_subprocess_invoked")
    )
    real_repair_approval_statuses = _safe_mapping(
        trail_summary.get("real_repair_approval_statuses")
    )
    real_repair_approval_source_review_statuses = _safe_mapping(
        trail_summary.get("real_repair_approval_source_review_statuses")
    )
    real_repair_approval_source_bundle_statuses = _safe_mapping(
        trail_summary.get("real_repair_approval_source_bundle_statuses")
    )
    real_repair_approval_next_actions = _safe_mapping(
        trail_summary.get("real_repair_approval_next_actions")
    )
    real_repair_approval_operator_authorized = _safe_mapping(
        trail_summary.get("real_repair_approval_operator_authorized")
    )
    real_repair_approval_required = _safe_mapping(
        trail_summary.get("real_repair_approval_required")
    )
    real_repair_approval_approved = _safe_mapping(
        trail_summary.get("real_repair_approval_approved")
    )
    real_repair_approval_rejected = _safe_mapping(
        trail_summary.get("real_repair_approval_rejected")
    )
    real_repair_approval_repair_execution_enabled = _safe_mapping(
        trail_summary.get("real_repair_approval_repair_execution_enabled")
    )
    real_repair_approval_real_execution_enabled = _safe_mapping(
        trail_summary.get("real_repair_approval_real_execution_enabled")
    )
    real_repair_approval_subprocess_enabled = _safe_mapping(
        trail_summary.get("real_repair_approval_subprocess_enabled")
    )
    real_repair_approval_repair_execution_performed = _safe_mapping(
        trail_summary.get("real_repair_approval_repair_execution_performed")
    )
    real_repair_approval_repair_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_repair_approval_repair_subprocess_invoked")
    )
    real_repair_approval_execution_performed = _safe_mapping(
        trail_summary.get("real_repair_approval_execution_performed")
    )
    real_repair_approval_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_repair_approval_subprocess_invoked")
    )

    adapter_contract = describe_controlled_retry_execution_adapter_contract()

    return {
        "type": "controlled_execution_readiness_report",
        "schema_version": READINESS_SCHEMA_VERSION,
        "schema_kind": "controlled_execution_readiness",
        "adapter_contract": adapter_contract,
        "real_adapter_supported": bool(
            adapter_contract.get("real_execution_supported")
        ),
        "real_adapter_runnable": bool(
            (
                adapter_contract.get("real_adapter_contract")
                if isinstance(adapter_contract.get("real_adapter_contract"), Mapping)
                else {}
            ).get("runnable")
        ),
        "real_adapter_requires_explicit_pr": bool(
            (
                (
                    adapter_contract.get("real_adapter_contract")
                    if isinstance(
                        adapter_contract.get("real_adapter_contract"), Mapping
                    )
                    else {}
                )
            ).get("requires_explicit_pr")
        ),
        "real_preflight_observed": _safe_int(real_preflight_statuses.get("blocked")) > 0,
        "real_preflight_blocked": _safe_int(real_preflight_statuses.get("blocked")),
        "real_preflight_would_execute": _safe_int(real_preflight_would_execute.get("true")),
        "real_preflight_execution_performed": _safe_int(real_preflight_execution_performed.get("true")),
        "real_preflight_subprocess_invoked": _safe_int(real_preflight_subprocess_invoked.get("true")),
        "real_preflight_requires_explicit_pr": _safe_int(real_preflight_requires_explicit_pr.get("true")),
        "real_approval_observed": sum(
            _safe_int(value) for value in real_approval_statuses.values()
        ) > 0,
        "real_approval_records": sum(
            _safe_int(value) for value in real_approval_statuses.values()
        ),
        "real_approval_enabled": _safe_int(real_approval_enabled.get("true")),
        "real_approval_subprocess_enabled": _safe_int(
            real_approval_subprocess_enabled.get("true")
        ),
        "real_approval_execution_performed": _safe_int(
            real_approval_execution_performed.get("true")
        ),
        "real_approval_subprocess_invoked": _safe_int(
            real_approval_subprocess_invoked.get("true")
        ),
        "real_linkage_complete": bool(trail_summary.get("real_linkage_complete")),
        "real_preflight_orphans": _safe_int(
            trail_summary.get("real_preflight_orphans")
        ),
        "real_approval_orphans": _safe_int(
            trail_summary.get("real_approval_orphans")
        ),
        "real_approval_transition_observed": sum(
            _safe_int(value, 0)
            for value in real_approval_transition_statuses.values()
        ) > 0,
        "real_approval_transition_records": sum(
            _safe_int(value, 0)
            for value in real_approval_transition_statuses.values()
        ),
        "real_approval_latest_status": str(
            trail_summary.get("real_approval_latest_status") or "unknown"
        ),
        "real_approval_transition_enabled": _safe_int(
            real_approval_transition_enabled.get("true"), 0
        ),
        "real_approval_transition_subprocess_enabled": _safe_int(
            real_approval_transition_subprocess_enabled.get("true"), 0
        ),
        "real_approval_transition_execution_performed": _safe_int(
            real_approval_transition_execution_performed.get("true"), 0
        ),
        "real_approval_transition_subprocess_invoked": _safe_int(
            real_approval_transition_subprocess_invoked.get("true"), 0
        ),
        "real_final_gate_observed": _safe_int(
            real_final_gate_statuses.get("blocked"), 0
        ) > 0,
        "real_final_gate_blocked": _safe_int(
            real_final_gate_statuses.get("blocked"), 0
        ),
        "real_final_gate_would_execute": _safe_int(
            real_final_gate_would_execute.get("true"), 0
        ),
        "real_final_gate_ready": _safe_int(
            real_final_gate_ready.get("true"), 0
        ),
        "real_final_gate_real_execution_enabled": _safe_int(
            real_final_gate_real_execution_enabled.get("true"), 0
        ),
        "real_final_gate_subprocess_enabled": _safe_int(
            real_final_gate_subprocess_enabled.get("true"), 0
        ),
        "real_final_gate_execution_performed": _safe_int(
            real_final_gate_execution_performed.get("true"), 0
        ),
        "real_final_gate_subprocess_invoked": _safe_int(
            real_final_gate_subprocess_invoked.get("true"), 0
        ),
        "real_dry_run_envelope_observed": _safe_int(
            real_dry_run_envelope_dry_run_only.get("true"), 0
        ) > 0,
        "real_dry_run_envelope_records": _safe_int(
            real_dry_run_envelope_dry_run_only.get("true"), 0
        ),
        "real_dry_run_envelope_would_execute": _safe_int(
            real_dry_run_envelope_would_execute.get("true"), 0
        ),
        "real_dry_run_envelope_ready": _safe_int(
            real_dry_run_envelope_ready.get("true"), 0
        ),
        "real_dry_run_envelope_real_execution_enabled": _safe_int(
            real_dry_run_envelope_real_execution_enabled.get("true"), 0
        ),
        "real_dry_run_envelope_subprocess_enabled": _safe_int(
            real_dry_run_envelope_subprocess_enabled.get("true"), 0
        ),
        "real_dry_run_envelope_execution_performed": _safe_int(
            real_dry_run_envelope_execution_performed.get("true"), 0
        ),
        "real_dry_run_envelope_subprocess_invoked": _safe_int(
            real_dry_run_envelope_subprocess_invoked.get("true"), 0
        ),
        "real_dry_run_linkage_complete": bool(
            trail_summary.get("real_dry_run_linkage_complete")
        ),
        "real_dry_run_envelope_orphans": _safe_int(
            trail_summary.get("real_dry_run_envelope_orphans"), 0
        ),
        "real_noop_result_observed": _safe_int(
            real_noop_result_noop_only.get("true"), 0
        ) > 0,
        "real_noop_result_records": _safe_int(
            real_noop_result_noop_only.get("true"), 0
        ),
        "real_noop_result_rendered_command_executed": _safe_int(
            real_noop_result_rendered_command_executed.get("true"), 0
        ),
        "real_noop_result_dry_run_command_executed": _safe_int(
            real_noop_result_dry_run_command_executed.get("true"), 0
        ),
        "real_noop_result_real_execution_enabled": _safe_int(
            real_noop_result_real_execution_enabled.get("true"), 0
        ),
        "real_noop_result_subprocess_invoked": _safe_int(
            real_noop_result_subprocess_invoked.get("true"), 0
        ),
        "real_noop_result_execution_performed": _safe_int(
            real_noop_result_execution_performed.get("true"), 0
        ),
        "real_noop_result_exit_code_zero": _safe_int(
            real_noop_result_exit_codes.get("0"), 0
        ),
        "real_noop_linkage_complete": bool(
            trail_summary.get("real_noop_linkage_complete")
        ),
        "real_noop_result_orphans": _safe_int(
            trail_summary.get("real_noop_result_orphans"), 0
        ),
        "real_noop_result_stdout_marker_observed": _safe_int(
            real_noop_result_stdout_marker_observed.get("true"), 0
        ),
        "real_read_only_promotion_observed": _safe_int(
            real_read_only_promotion_statuses.get("promoted"), 0
        ) > 0,
        "real_read_only_promotion_records": _safe_int(
            real_read_only_promotion_statuses.get("promoted"), 0
        ),
        "real_read_only_promotion_linkage_complete": bool(
            trail_summary.get("real_read_only_promotion_linkage_complete")
        ),
        "real_read_only_promotion_orphans": _safe_int(
            trail_summary.get("real_read_only_promotion_orphans"), 0
        ),
        "real_read_only_promotion_candidate": _safe_int(
            real_read_only_promotion_candidates.get("true"), 0
        ),
        "real_read_only_promotion_command_parse_valid": _safe_int(
            real_read_only_promotion_command_parse_valid.get("true"), 0
        ),
        "real_read_only_promotion_stdout_marker_observed": _safe_int(
            real_read_only_promotion_stdout_marker_observed.get("true"), 0
        ),
        "real_read_only_promotion_noop_exit_code_zero": _safe_int(
            real_read_only_promotion_noop_exit_codes.get("0"), 0
        ),
        "real_read_only_promotion_rendered_command_executed": _safe_int(
            real_read_only_promotion_rendered_command_executed.get("true"), 0
        ),
        "real_read_only_promotion_dry_run_command_executed": _safe_int(
            real_read_only_promotion_dry_run_command_executed.get("true"), 0
        ),
        "real_read_only_promotion_real_execution_enabled": _safe_int(
            real_read_only_promotion_real_execution_enabled.get("true"), 0
        ),
        "real_read_only_promotion_subprocess_invoked": _safe_int(
            real_read_only_promotion_subprocess_invoked.get("true"), 0
        ),
        "real_read_only_promotion_execution_performed": _safe_int(
            real_read_only_promotion_execution_performed.get("true"), 0
        ),
        "real_read_only_final_gate_observed": _safe_int(
            real_read_only_final_gate_statuses.get("blocked"), 0
        ) > 0,
        "real_read_only_final_gate_records": _safe_int(
            real_read_only_final_gate_statuses.get("blocked"), 0
        ),
        "real_read_only_final_gate_linkage_complete": bool(
            trail_summary.get("real_read_only_final_gate_linkage_complete")
        ),
        "real_read_only_final_gate_orphans": _safe_int(
            trail_summary.get("real_read_only_final_gate_orphans"), 0
        ),
        "real_read_only_final_gate_preconditions_satisfied": _safe_int(
            real_read_only_final_gate_preconditions_satisfied.get("true"), 0
        ),
        "real_read_only_final_gate_ready": _safe_int(
            real_read_only_final_gate_ready.get("true"), 0
        ),
        "real_read_only_final_gate_would_execute": _safe_int(
            real_read_only_final_gate_would_execute.get("true"), 0
        ),
        "real_read_only_final_gate_read_only_execution_enabled": _safe_int(
            real_read_only_final_gate_read_only_execution_enabled.get("true"), 0
        ),
        "real_read_only_final_gate_real_execution_enabled": _safe_int(
            real_read_only_final_gate_real_execution_enabled.get("true"), 0
        ),
        "real_read_only_final_gate_subprocess_enabled": _safe_int(
            real_read_only_final_gate_subprocess_enabled.get("true"), 0
        ),
        "real_read_only_final_gate_subprocess_invoked": _safe_int(
            real_read_only_final_gate_subprocess_invoked.get("true"), 0
        ),
        "real_read_only_final_gate_execution_performed": _safe_int(
            real_read_only_final_gate_execution_performed.get("true"), 0
        ),
        "real_read_only_final_gate_rendered_command_executed": _safe_int(
            real_read_only_final_gate_rendered_command_executed.get("true"), 0
        ),
        "real_read_only_final_gate_dry_run_command_executed": _safe_int(
            real_read_only_final_gate_dry_run_command_executed.get("true"), 0
        ),
        "real_read_only_approval_observed": _safe_int(
            real_read_only_approval_statuses.get("pending"), 0
        ) > 0,
        "real_read_only_approval_records": _safe_int(
            real_read_only_approval_statuses.get("pending"), 0
        ),
        "real_read_only_approval_linkage_complete": bool(
            trail_summary.get("real_read_only_approval_linkage_complete")
        ),
        "real_read_only_approval_orphans": _safe_int(
            trail_summary.get("real_read_only_approval_orphans"), 0
        ),
        "real_read_only_approval_pending": _safe_int(
            real_read_only_approval_statuses.get("pending"), 0
        ),
        "real_read_only_approval_read_only_execution_enabled": _safe_int(
            real_read_only_approval_read_only_execution_enabled.get("true"), 0
        ),
        "real_read_only_approval_real_execution_enabled": _safe_int(
            real_read_only_approval_real_execution_enabled.get("true"), 0
        ),
        "real_read_only_approval_subprocess_enabled": _safe_int(
            real_read_only_approval_subprocess_enabled.get("true"), 0
        ),
        "real_read_only_approval_subprocess_invoked": _safe_int(
            real_read_only_approval_subprocess_invoked.get("true"), 0
        ),
        "real_read_only_approval_execution_performed": _safe_int(
            real_read_only_approval_execution_performed.get("true"), 0
        ),
        "real_read_only_approval_rendered_command_executed": _safe_int(
            real_read_only_approval_rendered_command_executed.get("true"), 0
        ),
        "real_read_only_approval_dry_run_command_executed": _safe_int(
            real_read_only_approval_dry_run_command_executed.get("true"), 0
        ),
        "real_read_only_approval_transition_observed": (
            _safe_int(real_read_only_approval_transition_to_statuses.get("approved"), 0)
            + _safe_int(real_read_only_approval_transition_to_statuses.get("rejected"), 0)
        )
        > 0,
        "real_read_only_approval_transition_records": (
            _safe_int(real_read_only_approval_transition_to_statuses.get("approved"), 0)
            + _safe_int(real_read_only_approval_transition_to_statuses.get("rejected"), 0)
        ),
        "real_read_only_approval_transition_linkage_complete": bool(
            trail_summary.get("real_read_only_approval_transition_linkage_complete")
        ),
        "real_read_only_approval_transition_orphans": _safe_int(
            trail_summary.get("real_read_only_approval_transition_orphans"), 0
        ),
        "real_read_only_approval_latest_status": str(
            trail_summary.get("real_read_only_approval_latest_status") or "unknown"
        ),
        "real_read_only_approval_transition_from_pending": _safe_int(
            real_read_only_approval_transition_from_statuses.get("pending"), 0
        ),
        "real_read_only_approval_transition_approved": _safe_int(
            real_read_only_approval_transition_to_statuses.get("approved"), 0
        ),
        "real_read_only_approval_transition_rejected": _safe_int(
            real_read_only_approval_transition_to_statuses.get("rejected"), 0
        ),
        "real_read_only_approval_transition_read_only_execution_enabled": _safe_int(
            real_read_only_approval_transition_read_only_execution_enabled.get("true"), 0
        ),
        "real_read_only_approval_transition_real_execution_enabled": _safe_int(
            real_read_only_approval_transition_real_execution_enabled.get("true"), 0
        ),
        "real_read_only_approval_transition_subprocess_enabled": _safe_int(
            real_read_only_approval_transition_subprocess_enabled.get("true"), 0
        ),
        "real_read_only_approval_transition_subprocess_invoked": _safe_int(
            real_read_only_approval_transition_subprocess_invoked.get("true"), 0
        ),
        "real_read_only_approval_transition_execution_performed": _safe_int(
            real_read_only_approval_transition_execution_performed.get("true"), 0
        ),
        "real_read_only_approval_transition_rendered_command_executed": _safe_int(
            real_read_only_approval_transition_rendered_command_executed.get("true"), 0
        ),
        "real_read_only_approval_transition_dry_run_command_executed": _safe_int(
            real_read_only_approval_transition_dry_run_command_executed.get("true"), 0
        ),
        "real_read_only_readiness_gate_observed": _safe_int(
            real_read_only_readiness_gate_statuses.get("ready_blocked"), 0
        )
        > 0,
        "real_read_only_readiness_gate_records": _safe_int(
            real_read_only_readiness_gate_statuses.get("ready_blocked"), 0
        ),
        "real_read_only_readiness_gate_linkage_complete": bool(
            trail_summary.get("real_read_only_readiness_gate_linkage_complete")
        ),
        "real_read_only_readiness_gate_orphans": _safe_int(
            trail_summary.get("real_read_only_readiness_gate_orphans"), 0
        ),
        "real_read_only_readiness_gate_satisfied": _safe_int(
            real_read_only_readiness_gate_satisfied.get("true"), 0
        ),
        "real_read_only_readiness_gate_ready": _safe_int(
            real_read_only_readiness_gate_ready.get("true"), 0
        ),
        "real_read_only_readiness_gate_read_only_execution_enabled": _safe_int(
            real_read_only_readiness_gate_read_only_execution_enabled.get("true"), 0
        ),
        "real_read_only_readiness_gate_real_execution_enabled": _safe_int(
            real_read_only_readiness_gate_real_execution_enabled.get("true"), 0
        ),
        "real_read_only_readiness_gate_subprocess_enabled": _safe_int(
            real_read_only_readiness_gate_subprocess_enabled.get("true"), 0
        ),
        "real_read_only_readiness_gate_subprocess_invoked": _safe_int(
            real_read_only_readiness_gate_subprocess_invoked.get("true"), 0
        ),
        "real_read_only_readiness_gate_execution_performed": _safe_int(
            real_read_only_readiness_gate_execution_performed.get("true"), 0
        ),
        "real_read_only_readiness_gate_rendered_command_executed": _safe_int(
            real_read_only_readiness_gate_rendered_command_executed.get("true"), 0
        ),
        "real_read_only_readiness_gate_dry_run_command_executed": _safe_int(
            real_read_only_readiness_gate_dry_run_command_executed.get("true"), 0
        ),
        "real_read_only_execution_result_observed": (
            _safe_int(real_read_only_execution_result_statuses.get("executed"), 0)
            + _safe_int(real_read_only_execution_result_statuses.get("failed"), 0)
            + _safe_int(real_read_only_execution_result_statuses.get("rejected"), 0)
        )
        > 0,
        "real_read_only_execution_result_records": (
            _safe_int(real_read_only_execution_result_statuses.get("executed"), 0)
            + _safe_int(real_read_only_execution_result_statuses.get("failed"), 0)
            + _safe_int(real_read_only_execution_result_statuses.get("rejected"), 0)
        ),
        "real_read_only_execution_result_failed": _safe_int(
            real_read_only_execution_result_statuses.get("failed"), 0
        ),
        "real_read_only_execution_result_executed": _safe_int(
            real_read_only_execution_result_statuses.get("executed"), 0
        ),
        "real_read_only_execution_result_rejected": _safe_int(
            real_read_only_execution_result_statuses.get("rejected"), 0
        ),
        "real_read_only_execution_result_exit_code_1": _safe_int(
            real_read_only_execution_result_exit_codes.get("1"), 0
        ),
        "real_read_only_execution_result_linkage_complete": bool(
            trail_summary.get("real_read_only_execution_result_linkage_complete")
        ),
        "real_read_only_execution_result_orphans": _safe_int(
            trail_summary.get("real_read_only_execution_result_orphans"), 0
        ),
        "real_read_only_execution_result_validation_reasons_empty": _safe_int(
            real_read_only_execution_result_validation_reasons_empty.get("true"), 0
        ),
        "real_read_only_execution_result_operator_authorized": _safe_int(
            real_read_only_execution_result_operator_authorized.get("true"), 0
        ),
        "real_read_only_execution_result_allow_guarded": _safe_int(
            real_read_only_execution_result_allow_guarded.get("true"), 0
        ),
        "real_read_only_execution_result_read_only_execution_enabled": _safe_int(
            real_read_only_execution_result_read_only_execution_enabled.get("true"), 0
        ),
        "real_read_only_execution_result_real_execution_enabled": _safe_int(
            real_read_only_execution_result_real_execution_enabled.get("true"), 0
        ),
        "real_read_only_execution_result_subprocess_invoked": _safe_int(
            real_read_only_execution_result_subprocess_invoked.get("true"), 0
        ),
        "real_read_only_execution_result_execution_performed": _safe_int(
            real_read_only_execution_result_execution_performed.get("true"), 0
        ),
        "real_read_only_execution_result_read_only_command_executed": _safe_int(
            real_read_only_execution_result_read_only_command_executed.get("true"), 0
        ),
        "real_read_only_execution_result_rendered_command_executed": _safe_int(
            real_read_only_execution_result_rendered_command_executed.get("true"), 0
        ),
        "real_read_only_execution_result_dry_run_command_executed": _safe_int(
            real_read_only_execution_result_dry_run_command_executed.get("true"), 0
        ),
        "real_read_only_feedback_observed": _safe_int(
            real_read_only_feedback_statuses.get("actionable"), 0
        )
        > 0,
        "real_read_only_feedback_records": _safe_int(
            real_read_only_feedback_statuses.get("actionable"), 0
        ),
        "real_read_only_feedback_linkage_complete": bool(
            trail_summary.get("real_read_only_feedback_linkage_complete")
        ),
        "real_read_only_feedback_orphans": _safe_int(
            trail_summary.get("real_read_only_feedback_orphans"), 0
        ),
        "real_read_only_feedback_actionable": _safe_int(
            real_read_only_feedback_statuses.get("actionable"), 0
        ),
        "real_read_only_feedback_source_failed": _safe_int(
            real_read_only_feedback_source_statuses.get("failed"), 0
        ),
        "real_read_only_feedback_source_exit_code_1": _safe_int(
            real_read_only_feedback_source_exit_codes.get("1"), 0
        ),
        "real_read_only_feedback_next_action_investigate": _safe_int(
            real_read_only_feedback_next_actions.get(
                "investigate_failed_read_only_evidence_check"
            ),
            0,
        ),
        "real_read_only_feedback_execution_observed": _safe_int(
            real_read_only_feedback_execution_observed.get("true"), 0
        ),
        "real_read_only_feedback_failed": _safe_int(
            real_read_only_feedback_failed.get("true"), 0
        ),
        "real_read_only_feedback_real_execution_enabled": _safe_int(
            real_read_only_feedback_real_execution_enabled.get("true"), 0
        ),
        "real_read_only_feedback_feedback_execution_performed": _safe_int(
            real_read_only_feedback_feedback_execution_performed.get("true"), 0
        ),
        "real_read_only_feedback_feedback_subprocess_invoked": _safe_int(
            real_read_only_feedback_feedback_subprocess_invoked.get("true"), 0
        ),
        "real_read_only_feedback_execution_performed": _safe_int(
            real_read_only_feedback_execution_performed.get("true"), 0
        ),
        "real_read_only_feedback_subprocess_invoked": _safe_int(
            real_read_only_feedback_subprocess_invoked.get("true"), 0
        ),
        "real_read_only_repair_plan_observed": _safe_int(
            real_read_only_repair_plan_statuses.get("planned"), 0
        )
        > 0,
        "real_read_only_repair_plan_records": _safe_int(
            real_read_only_repair_plan_statuses.get("planned"), 0
        ),
        "real_read_only_repair_plan_linkage_complete": bool(
            trail_summary.get("real_read_only_repair_plan_linkage_complete")
        ),
        "real_read_only_repair_plan_orphans": _safe_int(
            trail_summary.get("real_read_only_repair_plan_orphans"), 0
        ),
        "real_read_only_repair_plan_planned": _safe_int(
            real_read_only_repair_plan_statuses.get("planned"), 0
        ),
        "real_read_only_repair_plan_source_actionable": _safe_int(
            real_read_only_repair_plan_source_feedback_statuses.get("actionable"), 0
        ),
        "real_read_only_repair_plan_source_failed": _safe_int(
            real_read_only_repair_plan_source_statuses.get("failed"), 0
        ),
        "real_read_only_repair_plan_source_exit_code_1": _safe_int(
            real_read_only_repair_plan_source_exit_codes.get("1"), 0
        ),
        "real_read_only_repair_plan_next_action_review": _safe_int(
            real_read_only_repair_plan_next_actions.get(
                "review_replay_evidence_repair_plan"
            ),
            0,
        ),
        "real_read_only_repair_plan_requires_operator_review": _safe_int(
            real_read_only_repair_plan_requires_operator_review.get("true"), 0
        ),
        "real_read_only_repair_plan_repair_execution_enabled": _safe_int(
            real_read_only_repair_plan_repair_execution_enabled.get("true"), 0
        ),
        "real_read_only_repair_plan_real_execution_enabled": _safe_int(
            real_read_only_repair_plan_real_execution_enabled.get("true"), 0
        ),
        "real_read_only_repair_plan_subprocess_enabled": _safe_int(
            real_read_only_repair_plan_subprocess_enabled.get("true"), 0
        ),
        "real_read_only_repair_plan_repair_execution_performed": _safe_int(
            real_read_only_repair_plan_repair_execution_performed.get("true"), 0
        ),
        "real_read_only_repair_plan_repair_subprocess_invoked": _safe_int(
            real_read_only_repair_plan_repair_subprocess_invoked.get("true"), 0
        ),
        "real_read_only_repair_plan_execution_performed": _safe_int(
            real_read_only_repair_plan_execution_performed.get("true"), 0
        ),
        "real_read_only_repair_plan_subprocess_invoked": _safe_int(
            real_read_only_repair_plan_subprocess_invoked.get("true"), 0
        ),
        "real_read_only_repair_action_bundle_observed": _safe_int(
            real_read_only_repair_action_bundle_statuses.get("assembled"), 0
        )
        > 0,
        "real_read_only_repair_action_bundle_records": _safe_int(
            real_read_only_repair_action_bundle_statuses.get("assembled"), 0
        ),
        "real_read_only_repair_action_bundle_linkage_complete": bool(
            trail_summary.get("real_read_only_repair_action_bundle_linkage_complete")
        ),
        "real_read_only_repair_action_bundle_orphans": _safe_int(
            trail_summary.get("real_read_only_repair_action_bundle_orphans"), 0
        ),
        "real_read_only_repair_action_bundle_assembled": _safe_int(
            real_read_only_repair_action_bundle_statuses.get("assembled"), 0
        ),
        "real_read_only_repair_action_bundle_source_planned": _safe_int(
            real_read_only_repair_action_bundle_source_plan_statuses.get("planned"), 0
        ),
        "real_read_only_repair_action_bundle_source_actionable": _safe_int(
            real_read_only_repair_action_bundle_source_feedback_statuses.get("actionable"), 0
        ),
        "real_read_only_repair_action_bundle_source_failed": _safe_int(
            real_read_only_repair_action_bundle_source_statuses.get("failed"), 0
        ),
        "real_read_only_repair_action_bundle_source_exit_code_1": _safe_int(
            real_read_only_repair_action_bundle_source_exit_codes.get("1"), 0
        ),
        "real_read_only_repair_action_bundle_next_action_review": _safe_int(
            real_read_only_repair_action_bundle_next_actions.get(
                "review_repair_action_bundle"
            ),
            0,
        ),
        "real_read_only_repair_action_bundle_requires_operator_review": _safe_int(
            real_read_only_repair_action_bundle_requires_operator_review.get("true"), 0
        ),
        "real_read_only_repair_action_bundle_reviewed": _safe_int(
            real_read_only_repair_action_bundle_reviewed.get("true"), 0
        ),
        "real_read_only_repair_action_bundle_bundle_execution_enabled": _safe_int(
            real_read_only_repair_action_bundle_bundle_execution_enabled.get("true"), 0
        ),
        "real_read_only_repair_action_bundle_repair_execution_enabled": _safe_int(
            real_read_only_repair_action_bundle_repair_execution_enabled.get("true"), 0
        ),
        "real_read_only_repair_action_bundle_real_execution_enabled": _safe_int(
            real_read_only_repair_action_bundle_real_execution_enabled.get("true"), 0
        ),
        "real_read_only_repair_action_bundle_subprocess_enabled": _safe_int(
            real_read_only_repair_action_bundle_subprocess_enabled.get("true"), 0
        ),
        "real_read_only_repair_action_bundle_bundle_execution_performed": _safe_int(
            real_read_only_repair_action_bundle_bundle_execution_performed.get("true"), 0
        ),
        "real_read_only_repair_action_bundle_bundle_subprocess_invoked": _safe_int(
            real_read_only_repair_action_bundle_bundle_subprocess_invoked.get("true"), 0
        ),
        "real_read_only_repair_action_bundle_execution_performed": _safe_int(
            real_read_only_repair_action_bundle_execution_performed.get("true"), 0
        ),
        "real_read_only_repair_action_bundle_subprocess_invoked": _safe_int(
            real_read_only_repair_action_bundle_subprocess_invoked.get("true"), 0
        ),
        "real_read_only_repair_action_bundle_review_observed": _safe_int(
            real_read_only_repair_action_bundle_review_statuses.get("approved"), 0
        )
        > 0,
        "real_read_only_repair_action_bundle_review_records": _safe_int(
            real_read_only_repair_action_bundle_review_statuses.get("approved"), 0
        ),
        "real_read_only_repair_action_bundle_review_linkage_complete": bool(
            trail_summary.get("real_read_only_repair_action_bundle_review_linkage_complete")
        ),
        "real_read_only_repair_action_bundle_review_orphans": _safe_int(
            trail_summary.get("real_read_only_repair_action_bundle_review_orphans"), 0
        ),
        "real_read_only_repair_action_bundle_review_approved_status": _safe_int(
            real_read_only_repair_action_bundle_review_statuses.get("approved"), 0
        ),
        "real_read_only_repair_action_bundle_review_source_assembled": _safe_int(
            real_read_only_repair_action_bundle_review_source_bundle_statuses.get("assembled"),
            0,
        ),
        "real_read_only_repair_action_bundle_review_source_planned": _safe_int(
            real_read_only_repair_action_bundle_review_source_plan_statuses.get("planned"), 0
        ),
        "real_read_only_repair_action_bundle_review_source_actionable": _safe_int(
            real_read_only_repair_action_bundle_review_source_feedback_statuses.get(
                "actionable"
            ),
            0,
        ),
        "real_read_only_repair_action_bundle_review_source_failed": _safe_int(
            real_read_only_repair_action_bundle_review_source_statuses.get("failed"), 0
        ),
        "real_read_only_repair_action_bundle_review_source_exit_code_1": _safe_int(
            real_read_only_repair_action_bundle_review_source_exit_codes.get("1"), 0
        ),
        "real_read_only_repair_action_bundle_review_source_item_count_9": _safe_int(
            real_read_only_repair_action_bundle_review_source_item_counts.get("9"), 0
        ),
        "real_read_only_repair_action_bundle_review_next_action_prepare": _safe_int(
            real_read_only_repair_action_bundle_review_next_actions.get(
                "prepare_repair_execution_approval_scaffold"
            ),
            0,
        ),
        "real_read_only_repair_action_bundle_review_operator_authorized": _safe_int(
            real_read_only_repair_action_bundle_review_operator_authorized.get("true"), 0
        ),
        "real_read_only_repair_action_bundle_review_reviewed": _safe_int(
            real_read_only_repair_action_bundle_review_reviewed.get("true"), 0
        ),
        "real_read_only_repair_action_bundle_review_approved": _safe_int(
            real_read_only_repair_action_bundle_review_approved.get("true"), 0
        ),
        "real_read_only_repair_action_bundle_review_bundle_execution_enabled": _safe_int(
            real_read_only_repair_action_bundle_review_bundle_execution_enabled.get("true"), 0
        ),
        "real_read_only_repair_action_bundle_review_repair_execution_enabled": _safe_int(
            real_read_only_repair_action_bundle_review_repair_execution_enabled.get("true"), 0
        ),
        "real_read_only_repair_action_bundle_review_real_execution_enabled": _safe_int(
            real_read_only_repair_action_bundle_review_real_execution_enabled.get("true"), 0
        ),
        "real_read_only_repair_action_bundle_review_subprocess_enabled": _safe_int(
            real_read_only_repair_action_bundle_review_subprocess_enabled.get("true"), 0
        ),
        "real_read_only_repair_action_bundle_review_bundle_execution_performed": _safe_int(
            real_read_only_repair_action_bundle_review_bundle_execution_performed.get("true"), 0
        ),
        "real_read_only_repair_action_bundle_review_bundle_subprocess_invoked": _safe_int(
            real_read_only_repair_action_bundle_review_bundle_subprocess_invoked.get("true"), 0
        ),
        "real_read_only_repair_action_bundle_review_execution_performed": _safe_int(
            real_read_only_repair_action_bundle_review_execution_performed.get("true"), 0
        ),
        "real_read_only_repair_action_bundle_review_subprocess_invoked": _safe_int(
            real_read_only_repair_action_bundle_review_subprocess_invoked.get("true"), 0
        ),
        "real_repair_approval_observed": _safe_int(
            real_repair_approval_statuses.get("pending"), 0
        )
        > 0,
        "real_repair_approval_records": _safe_int(
            real_repair_approval_statuses.get("pending"), 0
        ),
        "real_repair_approval_linkage_complete": bool(
            trail_summary.get("real_repair_approval_linkage_complete")
        ),
        "real_repair_approval_orphans": _safe_int(
            trail_summary.get("real_repair_approval_orphans"), 0
        ),
        "real_repair_approval_pending": _safe_int(
            real_repair_approval_statuses.get("pending"), 0
        ),
        "real_repair_approval_source_review_approved": _safe_int(
            real_repair_approval_source_review_statuses.get("approved"), 0
        ),
        "real_repair_approval_next_action_await": _safe_int(
            real_repair_approval_next_actions.get("await_repair_execution_approval"), 0
        ),
        "real_repair_approval_operator_authorized": _safe_int(
            real_repair_approval_operator_authorized.get("true"), 0
        ),
        "real_repair_approval_required": _safe_int(
            real_repair_approval_required.get("true"), 0
        ),
        "real_repair_approval_approved": _safe_int(
            real_repair_approval_approved.get("true"), 0
        ),
        "real_repair_approval_repair_execution_enabled": _safe_int(
            real_repair_approval_repair_execution_enabled.get("true"), 0
        ),
        "real_repair_approval_real_execution_enabled": _safe_int(
            real_repair_approval_real_execution_enabled.get("true"), 0
        ),
        "real_repair_approval_subprocess_enabled": _safe_int(
            real_repair_approval_subprocess_enabled.get("true"), 0
        ),
        "real_repair_approval_repair_execution_performed": _safe_int(
            real_repair_approval_repair_execution_performed.get("true"), 0
        ),
        "real_repair_approval_repair_subprocess_invoked": _safe_int(
            real_repair_approval_repair_subprocess_invoked.get("true"), 0
        ),
        "real_repair_approval_execution_performed": _safe_int(
            real_repair_approval_execution_performed.get("true"), 0
        ),
        "real_repair_approval_subprocess_invoked": _safe_int(
            real_repair_approval_subprocess_invoked.get("true"), 0
        ),
        "status": "passed" if ready_for_mock_execution else "failed",
        "ready_for_mock_execution": ready_for_mock_execution,
        "ready_for_real_execution": ready_for_real_execution,
        "blocking_reasons": blocking_reasons,
        "require_operator_authorized": require_operator_authorized,
        "proposal_id": proposal_id or None,
        "rendered_command_id": rendered_command_id or None,
        "summary": {
            "status": "passed" if ready_for_mock_execution else "failed",
            "ready_for_mock_execution": ready_for_mock_execution,
            "ready_for_real_execution": ready_for_real_execution,
            "blocking_reasons": blocking_reasons,
            "mock_execution_observed": _safe_int(
                controlled_mock_statuses.get("mock_executed")
            )
            > 0,
            "mock_execution_summary_observed": _safe_int(
                mock_summary_statuses.get("mock_executed")
            )
            > 0,
            "adapter_contract_observed": (
                _safe_int(controlled_mock_adapter.get("mock")) > 0
                and _safe_int(controlled_mock_adapter_mode.get("mock")) > 0
                and _safe_int(
                    controlled_mock_adapter_result_statuses.get("mock_executed")
                )
                > 0
            ),
            "adapter_subprocess_invoked": _safe_int(
                controlled_mock_adapter_subprocess_invoked.get("true")
            ),
            "adapter_real_execution_enabled": _safe_int(
                controlled_mock_adapter_real_execution_enabled.get("true")
            ),
            "adapter_payload_executed": _safe_int(
                controlled_mock_adapter_payload_executed.get("true")
            ),
            "real_adapter_supported": bool(
                adapter_contract.get("real_execution_supported")
            ),
            "real_adapter_runnable": bool(
                (
                    adapter_contract.get("real_adapter_contract")
                    if isinstance(
                        adapter_contract.get("real_adapter_contract"), Mapping
                    )
                    else {}
                ).get("runnable")
            ),
            "real_adapter_requires_explicit_pr": bool(
                (
                    (
                        adapter_contract.get("real_adapter_contract")
                        if isinstance(
                            adapter_contract.get("real_adapter_contract"), Mapping
                        )
                        else {}
                    )
                ).get("requires_explicit_pr")
            ),
            "real_execution_request_observed": _safe_int(
                controlled_real_execution_requested.get("true")
            )
            > 0,
            "real_execution_request_rejected": _safe_int(
                controlled_reasons.get("real_execution_not_supported")
            ),
            "real_preflight_observed": _safe_int(real_preflight_statuses.get("blocked")) > 0,
            "real_preflight_blocked": _safe_int(real_preflight_statuses.get("blocked")),
            "real_preflight_would_execute": _safe_int(
                real_preflight_would_execute.get("true")
            ),
            "real_preflight_execution_performed": _safe_int(
                real_preflight_execution_performed.get("true")
            ),
            "real_preflight_subprocess_invoked": _safe_int(
                real_preflight_subprocess_invoked.get("true")
            ),
            "real_preflight_requires_explicit_pr": _safe_int(
                real_preflight_requires_explicit_pr.get("true")
            ),
            "real_approval_observed": sum(
                _safe_int(value) for value in real_approval_statuses.values()
            ) > 0,
            "real_approval_records": sum(
                _safe_int(value) for value in real_approval_statuses.values()
            ),
            "real_approval_enabled": _safe_int(real_approval_enabled.get("true")),
            "real_approval_subprocess_enabled": _safe_int(
                real_approval_subprocess_enabled.get("true")
            ),
            "real_approval_execution_performed": _safe_int(
                real_approval_execution_performed.get("true")
            ),
            "real_approval_subprocess_invoked": _safe_int(
                real_approval_subprocess_invoked.get("true")
            ),
            "real_linkage_complete": bool(trail_summary.get("real_linkage_complete")),
            "real_preflight_orphans": _safe_int(
                trail_summary.get("real_preflight_orphans")
            ),
            "real_approval_orphans": _safe_int(
                trail_summary.get("real_approval_orphans")
            ),
            "real_approval_transition_observed": sum(
                _safe_int(value, 0)
                for value in real_approval_transition_statuses.values()
            ) > 0,
            "real_approval_transition_records": sum(
                _safe_int(value, 0)
                for value in real_approval_transition_statuses.values()
            ),
            "real_approval_latest_status": str(
                trail_summary.get("real_approval_latest_status") or "unknown"
            ),
            "real_approval_transition_enabled": _safe_int(
                real_approval_transition_enabled.get("true"), 0
            ),
            "real_approval_transition_subprocess_enabled": _safe_int(
                real_approval_transition_subprocess_enabled.get("true"), 0
            ),
            "real_approval_transition_execution_performed": _safe_int(
                real_approval_transition_execution_performed.get("true"), 0
            ),
            "real_approval_transition_subprocess_invoked": _safe_int(
                real_approval_transition_subprocess_invoked.get("true"), 0
            ),
            "real_final_gate_observed": _safe_int(
                real_final_gate_statuses.get("blocked"), 0
            ) > 0,
            "real_final_gate_blocked": _safe_int(
                real_final_gate_statuses.get("blocked"), 0
            ),
            "real_final_gate_would_execute": _safe_int(
                real_final_gate_would_execute.get("true"), 0
            ),
            "real_final_gate_ready": _safe_int(
                real_final_gate_ready.get("true"), 0
            ),
            "real_final_gate_real_execution_enabled": _safe_int(
                real_final_gate_real_execution_enabled.get("true"), 0
            ),
            "real_final_gate_subprocess_enabled": _safe_int(
                real_final_gate_subprocess_enabled.get("true"), 0
            ),
            "real_final_gate_execution_performed": _safe_int(
                real_final_gate_execution_performed.get("true"), 0
            ),
            "real_final_gate_subprocess_invoked": _safe_int(
                real_final_gate_subprocess_invoked.get("true"), 0
            ),
            "real_dry_run_envelope_observed": _safe_int(
                real_dry_run_envelope_dry_run_only.get("true"), 0
            ) > 0,
            "real_dry_run_envelope_records": _safe_int(
                real_dry_run_envelope_dry_run_only.get("true"), 0
            ),
            "real_dry_run_envelope_would_execute": _safe_int(
                real_dry_run_envelope_would_execute.get("true"), 0
            ),
            "real_dry_run_envelope_ready": _safe_int(
                real_dry_run_envelope_ready.get("true"), 0
            ),
            "real_dry_run_envelope_real_execution_enabled": _safe_int(
                real_dry_run_envelope_real_execution_enabled.get("true"), 0
            ),
            "real_dry_run_envelope_subprocess_enabled": _safe_int(
                real_dry_run_envelope_subprocess_enabled.get("true"), 0
            ),
            "real_dry_run_envelope_execution_performed": _safe_int(
                real_dry_run_envelope_execution_performed.get("true"), 0
            ),
            "real_dry_run_envelope_subprocess_invoked": _safe_int(
                real_dry_run_envelope_subprocess_invoked.get("true"), 0
            ),
            "real_dry_run_linkage_complete": bool(
                trail_summary.get("real_dry_run_linkage_complete")
            ),
            "real_dry_run_envelope_orphans": _safe_int(
                trail_summary.get("real_dry_run_envelope_orphans"), 0
            ),
            "real_noop_result_observed": _safe_int(
                real_noop_result_noop_only.get("true"), 0
            ) > 0,
            "real_noop_result_records": _safe_int(
                real_noop_result_noop_only.get("true"), 0
            ),
            "real_noop_result_rendered_command_executed": _safe_int(
                real_noop_result_rendered_command_executed.get("true"), 0
            ),
            "real_noop_result_dry_run_command_executed": _safe_int(
                real_noop_result_dry_run_command_executed.get("true"), 0
            ),
            "real_noop_result_real_execution_enabled": _safe_int(
                real_noop_result_real_execution_enabled.get("true"), 0
            ),
            "real_noop_result_subprocess_invoked": _safe_int(
                real_noop_result_subprocess_invoked.get("true"), 0
            ),
            "real_noop_result_execution_performed": _safe_int(
                real_noop_result_execution_performed.get("true"), 0
            ),
            "real_noop_result_exit_code_zero": _safe_int(
                real_noop_result_exit_codes.get("0"), 0
            ),
            "real_noop_linkage_complete": bool(
                trail_summary.get("real_noop_linkage_complete")
            ),
            "real_noop_result_orphans": _safe_int(
                trail_summary.get("real_noop_result_orphans"), 0
            ),
            "real_noop_result_stdout_marker_observed": _safe_int(
                real_noop_result_stdout_marker_observed.get("true"), 0
            ),
            "real_read_only_promotion_observed": _safe_int(
                real_read_only_promotion_statuses.get("promoted"), 0
            ) > 0,
            "real_read_only_promotion_records": _safe_int(
                real_read_only_promotion_statuses.get("promoted"), 0
            ),
            "real_read_only_promotion_linkage_complete": bool(
                trail_summary.get("real_read_only_promotion_linkage_complete")
            ),
            "real_read_only_promotion_orphans": _safe_int(
                trail_summary.get("real_read_only_promotion_orphans"), 0
            ),
            "real_read_only_promotion_candidate": _safe_int(
                real_read_only_promotion_candidates.get("true"), 0
            ),
            "real_read_only_promotion_command_parse_valid": _safe_int(
                real_read_only_promotion_command_parse_valid.get("true"), 0
            ),
            "real_read_only_promotion_stdout_marker_observed": _safe_int(
                real_read_only_promotion_stdout_marker_observed.get("true"), 0
            ),
            "real_read_only_promotion_noop_exit_code_zero": _safe_int(
                real_read_only_promotion_noop_exit_codes.get("0"), 0
            ),
            "real_read_only_promotion_rendered_command_executed": _safe_int(
                real_read_only_promotion_rendered_command_executed.get("true"), 0
            ),
            "real_read_only_promotion_dry_run_command_executed": _safe_int(
                real_read_only_promotion_dry_run_command_executed.get("true"), 0
            ),
            "real_read_only_promotion_real_execution_enabled": _safe_int(
                real_read_only_promotion_real_execution_enabled.get("true"), 0
            ),
            "real_read_only_promotion_subprocess_invoked": _safe_int(
                real_read_only_promotion_subprocess_invoked.get("true"), 0
            ),
            "real_read_only_promotion_execution_performed": _safe_int(
                real_read_only_promotion_execution_performed.get("true"), 0
            ),
            "real_read_only_final_gate_observed": _safe_int(
                real_read_only_final_gate_statuses.get("blocked"), 0
            ) > 0,
            "real_read_only_final_gate_records": _safe_int(
                real_read_only_final_gate_statuses.get("blocked"), 0
            ),
            "real_read_only_final_gate_linkage_complete": bool(
                trail_summary.get("real_read_only_final_gate_linkage_complete")
            ),
            "real_read_only_final_gate_orphans": _safe_int(
                trail_summary.get("real_read_only_final_gate_orphans"), 0
            ),
            "real_read_only_final_gate_preconditions_satisfied": _safe_int(
                real_read_only_final_gate_preconditions_satisfied.get("true"), 0
            ),
            "real_read_only_final_gate_ready": _safe_int(
                real_read_only_final_gate_ready.get("true"), 0
            ),
            "real_read_only_final_gate_would_execute": _safe_int(
                real_read_only_final_gate_would_execute.get("true"), 0
            ),
            "real_read_only_final_gate_read_only_execution_enabled": _safe_int(
                real_read_only_final_gate_read_only_execution_enabled.get("true"), 0
            ),
            "real_read_only_final_gate_real_execution_enabled": _safe_int(
                real_read_only_final_gate_real_execution_enabled.get("true"), 0
            ),
            "real_read_only_final_gate_subprocess_enabled": _safe_int(
                real_read_only_final_gate_subprocess_enabled.get("true"), 0
            ),
            "real_read_only_final_gate_subprocess_invoked": _safe_int(
                real_read_only_final_gate_subprocess_invoked.get("true"), 0
            ),
            "real_read_only_final_gate_execution_performed": _safe_int(
                real_read_only_final_gate_execution_performed.get("true"), 0
            ),
            "real_read_only_final_gate_rendered_command_executed": _safe_int(
                real_read_only_final_gate_rendered_command_executed.get("true"), 0
            ),
            "real_read_only_final_gate_dry_run_command_executed": _safe_int(
                real_read_only_final_gate_dry_run_command_executed.get("true"), 0
            ),
            "real_read_only_approval_observed": _safe_int(
                real_read_only_approval_statuses.get("pending"), 0
            ) > 0,
            "real_read_only_approval_records": _safe_int(
                real_read_only_approval_statuses.get("pending"), 0
            ),
            "real_read_only_approval_linkage_complete": bool(
                trail_summary.get("real_read_only_approval_linkage_complete")
            ),
            "real_read_only_approval_orphans": _safe_int(
                trail_summary.get("real_read_only_approval_orphans"), 0
            ),
            "real_read_only_approval_pending": _safe_int(
                real_read_only_approval_statuses.get("pending"), 0
            ),
            "real_read_only_approval_read_only_execution_enabled": _safe_int(
                real_read_only_approval_read_only_execution_enabled.get("true"), 0
            ),
            "real_read_only_approval_real_execution_enabled": _safe_int(
                real_read_only_approval_real_execution_enabled.get("true"), 0
            ),
            "real_read_only_approval_subprocess_enabled": _safe_int(
                real_read_only_approval_subprocess_enabled.get("true"), 0
            ),
            "real_read_only_approval_subprocess_invoked": _safe_int(
                real_read_only_approval_subprocess_invoked.get("true"), 0
            ),
            "real_read_only_approval_execution_performed": _safe_int(
                real_read_only_approval_execution_performed.get("true"), 0
            ),
            "real_read_only_approval_rendered_command_executed": _safe_int(
                real_read_only_approval_rendered_command_executed.get("true"), 0
            ),
            "real_read_only_approval_dry_run_command_executed": _safe_int(
                real_read_only_approval_dry_run_command_executed.get("true"), 0
            ),
            "real_read_only_approval_transition_observed": (
                _safe_int(real_read_only_approval_transition_to_statuses.get("approved"), 0)
                + _safe_int(real_read_only_approval_transition_to_statuses.get("rejected"), 0)
            )
            > 0,
            "real_read_only_approval_transition_records": (
                _safe_int(real_read_only_approval_transition_to_statuses.get("approved"), 0)
                + _safe_int(real_read_only_approval_transition_to_statuses.get("rejected"), 0)
            ),
            "real_read_only_approval_transition_linkage_complete": bool(
                trail_summary.get("real_read_only_approval_transition_linkage_complete")
            ),
            "real_read_only_approval_transition_orphans": _safe_int(
                trail_summary.get("real_read_only_approval_transition_orphans"), 0
            ),
            "real_read_only_approval_latest_status": str(
                trail_summary.get("real_read_only_approval_latest_status") or "unknown"
            ),
            "real_read_only_approval_transition_from_pending": _safe_int(
                real_read_only_approval_transition_from_statuses.get("pending"), 0
            ),
            "real_read_only_approval_transition_approved": _safe_int(
                real_read_only_approval_transition_to_statuses.get("approved"), 0
            ),
            "real_read_only_approval_transition_rejected": _safe_int(
                real_read_only_approval_transition_to_statuses.get("rejected"), 0
            ),
            "real_read_only_approval_transition_read_only_execution_enabled": _safe_int(
                real_read_only_approval_transition_read_only_execution_enabled.get("true"), 0
            ),
            "real_read_only_approval_transition_real_execution_enabled": _safe_int(
                real_read_only_approval_transition_real_execution_enabled.get("true"), 0
            ),
            "real_read_only_approval_transition_subprocess_enabled": _safe_int(
                real_read_only_approval_transition_subprocess_enabled.get("true"), 0
            ),
            "real_read_only_approval_transition_subprocess_invoked": _safe_int(
                real_read_only_approval_transition_subprocess_invoked.get("true"), 0
            ),
            "real_read_only_approval_transition_execution_performed": _safe_int(
                real_read_only_approval_transition_execution_performed.get("true"), 0
            ),
            "real_read_only_approval_transition_rendered_command_executed": _safe_int(
                real_read_only_approval_transition_rendered_command_executed.get("true"), 0
            ),
            "real_read_only_approval_transition_dry_run_command_executed": _safe_int(
                real_read_only_approval_transition_dry_run_command_executed.get("true"), 0
            ),
            "real_read_only_readiness_gate_observed": _safe_int(
                real_read_only_readiness_gate_statuses.get("ready_blocked"), 0
            )
            > 0,
            "real_read_only_readiness_gate_records": _safe_int(
                real_read_only_readiness_gate_statuses.get("ready_blocked"), 0
            ),
            "real_read_only_readiness_gate_linkage_complete": bool(
                trail_summary.get("real_read_only_readiness_gate_linkage_complete")
            ),
            "real_read_only_readiness_gate_orphans": _safe_int(
                trail_summary.get("real_read_only_readiness_gate_orphans"), 0
            ),
            "real_read_only_readiness_gate_satisfied": _safe_int(
                real_read_only_readiness_gate_satisfied.get("true"), 0
            ),
            "real_read_only_readiness_gate_ready": _safe_int(
                real_read_only_readiness_gate_ready.get("true"), 0
            ),
            "real_read_only_readiness_gate_read_only_execution_enabled": _safe_int(
                real_read_only_readiness_gate_read_only_execution_enabled.get("true"), 0
            ),
            "real_read_only_readiness_gate_real_execution_enabled": _safe_int(
                real_read_only_readiness_gate_real_execution_enabled.get("true"), 0
            ),
            "real_read_only_readiness_gate_subprocess_enabled": _safe_int(
                real_read_only_readiness_gate_subprocess_enabled.get("true"), 0
            ),
            "real_read_only_readiness_gate_subprocess_invoked": _safe_int(
                real_read_only_readiness_gate_subprocess_invoked.get("true"), 0
            ),
            "real_read_only_readiness_gate_execution_performed": _safe_int(
                real_read_only_readiness_gate_execution_performed.get("true"), 0
            ),
            "real_read_only_readiness_gate_rendered_command_executed": _safe_int(
                real_read_only_readiness_gate_rendered_command_executed.get("true"), 0
            ),
            "real_read_only_readiness_gate_dry_run_command_executed": _safe_int(
                real_read_only_readiness_gate_dry_run_command_executed.get("true"), 0
            ),
            "real_read_only_execution_result_observed": (
                _safe_int(real_read_only_execution_result_statuses.get("executed"), 0)
                + _safe_int(real_read_only_execution_result_statuses.get("failed"), 0)
                + _safe_int(real_read_only_execution_result_statuses.get("rejected"), 0)
            )
            > 0,
            "real_read_only_execution_result_records": (
                _safe_int(real_read_only_execution_result_statuses.get("executed"), 0)
                + _safe_int(real_read_only_execution_result_statuses.get("failed"), 0)
                + _safe_int(real_read_only_execution_result_statuses.get("rejected"), 0)
            ),
            "real_read_only_execution_result_failed": _safe_int(
                real_read_only_execution_result_statuses.get("failed"), 0
            ),
            "real_read_only_execution_result_executed": _safe_int(
                real_read_only_execution_result_statuses.get("executed"), 0
            ),
            "real_read_only_execution_result_rejected": _safe_int(
                real_read_only_execution_result_statuses.get("rejected"), 0
            ),
            "real_read_only_execution_result_exit_code_1": _safe_int(
                real_read_only_execution_result_exit_codes.get("1"), 0
            ),
            "real_read_only_execution_result_linkage_complete": bool(
                trail_summary.get("real_read_only_execution_result_linkage_complete")
            ),
            "real_read_only_execution_result_orphans": _safe_int(
                trail_summary.get("real_read_only_execution_result_orphans"), 0
            ),
            "real_read_only_execution_result_validation_reasons_empty": _safe_int(
                real_read_only_execution_result_validation_reasons_empty.get("true"), 0
            ),
            "real_read_only_execution_result_operator_authorized": _safe_int(
                real_read_only_execution_result_operator_authorized.get("true"), 0
            ),
            "real_read_only_execution_result_allow_guarded": _safe_int(
                real_read_only_execution_result_allow_guarded.get("true"), 0
            ),
            "real_read_only_execution_result_read_only_execution_enabled": _safe_int(
                real_read_only_execution_result_read_only_execution_enabled.get("true"), 0
            ),
            "real_read_only_execution_result_real_execution_enabled": _safe_int(
                real_read_only_execution_result_real_execution_enabled.get("true"), 0
            ),
            "real_read_only_execution_result_subprocess_invoked": _safe_int(
                real_read_only_execution_result_subprocess_invoked.get("true"), 0
            ),
            "real_read_only_execution_result_execution_performed": _safe_int(
                real_read_only_execution_result_execution_performed.get("true"), 0
            ),
            "real_read_only_execution_result_read_only_command_executed": _safe_int(
                real_read_only_execution_result_read_only_command_executed.get("true"), 0
            ),
            "real_read_only_execution_result_rendered_command_executed": _safe_int(
                real_read_only_execution_result_rendered_command_executed.get("true"), 0
            ),
            "real_read_only_execution_result_dry_run_command_executed": _safe_int(
                real_read_only_execution_result_dry_run_command_executed.get("true"), 0
            ),
            "real_read_only_feedback_observed": _safe_int(
                real_read_only_feedback_statuses.get("actionable"), 0
            )
            > 0,
            "real_read_only_feedback_records": _safe_int(
                real_read_only_feedback_statuses.get("actionable"), 0
            ),
            "real_read_only_feedback_linkage_complete": bool(
                trail_summary.get("real_read_only_feedback_linkage_complete")
            ),
            "real_read_only_feedback_orphans": _safe_int(
                trail_summary.get("real_read_only_feedback_orphans"), 0
            ),
            "real_read_only_feedback_actionable": _safe_int(
                real_read_only_feedback_statuses.get("actionable"), 0
            ),
            "real_read_only_feedback_source_failed": _safe_int(
                real_read_only_feedback_source_statuses.get("failed"), 0
            ),
            "real_read_only_feedback_source_exit_code_1": _safe_int(
                real_read_only_feedback_source_exit_codes.get("1"), 0
            ),
            "real_read_only_feedback_next_action_investigate": _safe_int(
                real_read_only_feedback_next_actions.get(
                    "investigate_failed_read_only_evidence_check"
                ),
                0,
            ),
            "real_read_only_feedback_execution_observed": _safe_int(
                real_read_only_feedback_execution_observed.get("true"), 0
            ),
            "real_read_only_feedback_failed": _safe_int(
                real_read_only_feedback_failed.get("true"), 0
            ),
            "real_read_only_feedback_real_execution_enabled": _safe_int(
                real_read_only_feedback_real_execution_enabled.get("true"), 0
            ),
            "real_read_only_feedback_feedback_execution_performed": _safe_int(
                real_read_only_feedback_feedback_execution_performed.get("true"), 0
            ),
            "real_read_only_feedback_feedback_subprocess_invoked": _safe_int(
                real_read_only_feedback_feedback_subprocess_invoked.get("true"), 0
            ),
            "real_read_only_feedback_execution_performed": _safe_int(
                real_read_only_feedback_execution_performed.get("true"), 0
            ),
            "real_read_only_feedback_subprocess_invoked": _safe_int(
                real_read_only_feedback_subprocess_invoked.get("true"), 0
            ),
            "real_read_only_repair_plan_observed": _safe_int(
                real_read_only_repair_plan_statuses.get("planned"), 0
            )
            > 0,
            "real_read_only_repair_plan_records": _safe_int(
                real_read_only_repair_plan_statuses.get("planned"), 0
            ),
            "real_read_only_repair_plan_linkage_complete": bool(
                trail_summary.get("real_read_only_repair_plan_linkage_complete")
            ),
            "real_read_only_repair_plan_orphans": _safe_int(
                trail_summary.get("real_read_only_repair_plan_orphans"), 0
            ),
            "real_read_only_repair_plan_planned": _safe_int(
                real_read_only_repair_plan_statuses.get("planned"), 0
            ),
            "real_read_only_repair_plan_source_actionable": _safe_int(
                real_read_only_repair_plan_source_feedback_statuses.get("actionable"), 0
            ),
            "real_read_only_repair_plan_source_failed": _safe_int(
                real_read_only_repair_plan_source_statuses.get("failed"), 0
            ),
            "real_read_only_repair_plan_source_exit_code_1": _safe_int(
                real_read_only_repair_plan_source_exit_codes.get("1"), 0
            ),
            "real_read_only_repair_plan_next_action_review": _safe_int(
                real_read_only_repair_plan_next_actions.get(
                    "review_replay_evidence_repair_plan"
                ),
                0,
            ),
            "real_read_only_repair_plan_requires_operator_review": _safe_int(
                real_read_only_repair_plan_requires_operator_review.get("true"), 0
            ),
            "real_read_only_repair_plan_repair_execution_enabled": _safe_int(
                real_read_only_repair_plan_repair_execution_enabled.get("true"), 0
            ),
            "real_read_only_repair_plan_real_execution_enabled": _safe_int(
                real_read_only_repair_plan_real_execution_enabled.get("true"), 0
            ),
            "real_read_only_repair_plan_subprocess_enabled": _safe_int(
                real_read_only_repair_plan_subprocess_enabled.get("true"), 0
            ),
            "real_read_only_repair_plan_repair_execution_performed": _safe_int(
                real_read_only_repair_plan_repair_execution_performed.get("true"), 0
            ),
            "real_read_only_repair_plan_repair_subprocess_invoked": _safe_int(
                real_read_only_repair_plan_repair_subprocess_invoked.get("true"), 0
            ),
            "real_read_only_repair_plan_execution_performed": _safe_int(
                real_read_only_repair_plan_execution_performed.get("true"), 0
            ),
            "real_read_only_repair_plan_subprocess_invoked": _safe_int(
                real_read_only_repair_plan_subprocess_invoked.get("true"), 0
            ),
            "real_read_only_repair_action_bundle_observed": _safe_int(
                real_read_only_repair_action_bundle_statuses.get("assembled"), 0
            )
            > 0,
            "real_read_only_repair_action_bundle_records": _safe_int(
                real_read_only_repair_action_bundle_statuses.get("assembled"), 0
            ),
            "real_read_only_repair_action_bundle_linkage_complete": bool(
                trail_summary.get("real_read_only_repair_action_bundle_linkage_complete")
            ),
            "real_read_only_repair_action_bundle_orphans": _safe_int(
                trail_summary.get("real_read_only_repair_action_bundle_orphans"), 0
            ),
            "real_read_only_repair_action_bundle_assembled": _safe_int(
                real_read_only_repair_action_bundle_statuses.get("assembled"), 0
            ),
            "real_read_only_repair_action_bundle_source_planned": _safe_int(
                real_read_only_repair_action_bundle_source_plan_statuses.get("planned"), 0
            ),
            "real_read_only_repair_action_bundle_source_actionable": _safe_int(
                real_read_only_repair_action_bundle_source_feedback_statuses.get("actionable"), 0
            ),
            "real_read_only_repair_action_bundle_source_failed": _safe_int(
                real_read_only_repair_action_bundle_source_statuses.get("failed"), 0
            ),
            "real_read_only_repair_action_bundle_source_exit_code_1": _safe_int(
                real_read_only_repair_action_bundle_source_exit_codes.get("1"), 0
            ),
            "real_read_only_repair_action_bundle_next_action_review": _safe_int(
                real_read_only_repair_action_bundle_next_actions.get(
                    "review_repair_action_bundle"
                ),
                0,
            ),
            "real_read_only_repair_action_bundle_requires_operator_review": _safe_int(
                real_read_only_repair_action_bundle_requires_operator_review.get("true"), 0
            ),
            "real_read_only_repair_action_bundle_reviewed": _safe_int(
                real_read_only_repair_action_bundle_reviewed.get("true"), 0
            ),
            "real_read_only_repair_action_bundle_bundle_execution_enabled": _safe_int(
                real_read_only_repair_action_bundle_bundle_execution_enabled.get("true"), 0
            ),
            "real_read_only_repair_action_bundle_repair_execution_enabled": _safe_int(
                real_read_only_repair_action_bundle_repair_execution_enabled.get("true"), 0
            ),
            "real_read_only_repair_action_bundle_real_execution_enabled": _safe_int(
                real_read_only_repair_action_bundle_real_execution_enabled.get("true"), 0
            ),
            "real_read_only_repair_action_bundle_subprocess_enabled": _safe_int(
                real_read_only_repair_action_bundle_subprocess_enabled.get("true"), 0
            ),
            "real_read_only_repair_action_bundle_bundle_execution_performed": _safe_int(
                real_read_only_repair_action_bundle_bundle_execution_performed.get("true"), 0
            ),
            "real_read_only_repair_action_bundle_bundle_subprocess_invoked": _safe_int(
                real_read_only_repair_action_bundle_bundle_subprocess_invoked.get("true"), 0
            ),
            "real_read_only_repair_action_bundle_execution_performed": _safe_int(
                real_read_only_repair_action_bundle_execution_performed.get("true"), 0
            ),
            "real_read_only_repair_action_bundle_subprocess_invoked": _safe_int(
                real_read_only_repair_action_bundle_subprocess_invoked.get("true"), 0
            ),
            "real_read_only_repair_action_bundle_review_observed": _safe_int(
                real_read_only_repair_action_bundle_review_statuses.get("approved"), 0
            )
            > 0,
            "real_read_only_repair_action_bundle_review_records": _safe_int(
                real_read_only_repair_action_bundle_review_statuses.get("approved"), 0
            ),
            "real_read_only_repair_action_bundle_review_linkage_complete": bool(
                trail_summary.get("real_read_only_repair_action_bundle_review_linkage_complete")
            ),
            "real_read_only_repair_action_bundle_review_orphans": _safe_int(
                trail_summary.get("real_read_only_repair_action_bundle_review_orphans"), 0
            ),
            "real_read_only_repair_action_bundle_review_approved_status": _safe_int(
                real_read_only_repair_action_bundle_review_statuses.get("approved"), 0
            ),
            "real_read_only_repair_action_bundle_review_source_assembled": _safe_int(
                real_read_only_repair_action_bundle_review_source_bundle_statuses.get("assembled"),
                0,
            ),
            "real_read_only_repair_action_bundle_review_source_planned": _safe_int(
                real_read_only_repair_action_bundle_review_source_plan_statuses.get("planned"), 0
            ),
            "real_read_only_repair_action_bundle_review_source_actionable": _safe_int(
                real_read_only_repair_action_bundle_review_source_feedback_statuses.get(
                    "actionable"
                ),
                0,
            ),
            "real_read_only_repair_action_bundle_review_source_failed": _safe_int(
                real_read_only_repair_action_bundle_review_source_statuses.get("failed"), 0
            ),
            "real_read_only_repair_action_bundle_review_source_exit_code_1": _safe_int(
                real_read_only_repair_action_bundle_review_source_exit_codes.get("1"), 0
            ),
            "real_read_only_repair_action_bundle_review_source_item_count_9": _safe_int(
                real_read_only_repair_action_bundle_review_source_item_counts.get("9"), 0
            ),
            "real_read_only_repair_action_bundle_review_next_action_prepare": _safe_int(
                real_read_only_repair_action_bundle_review_next_actions.get(
                    "prepare_repair_execution_approval_scaffold"
                ),
                0,
            ),
            "real_read_only_repair_action_bundle_review_operator_authorized": _safe_int(
                real_read_only_repair_action_bundle_review_operator_authorized.get("true"), 0
            ),
            "real_read_only_repair_action_bundle_review_reviewed": _safe_int(
                real_read_only_repair_action_bundle_review_reviewed.get("true"), 0
            ),
            "real_read_only_repair_action_bundle_review_approved": _safe_int(
                real_read_only_repair_action_bundle_review_approved.get("true"), 0
            ),
            "real_read_only_repair_action_bundle_review_bundle_execution_enabled": _safe_int(
                real_read_only_repair_action_bundle_review_bundle_execution_enabled.get("true"), 0
            ),
            "real_read_only_repair_action_bundle_review_repair_execution_enabled": _safe_int(
                real_read_only_repair_action_bundle_review_repair_execution_enabled.get("true"), 0
            ),
            "real_read_only_repair_action_bundle_review_real_execution_enabled": _safe_int(
                real_read_only_repair_action_bundle_review_real_execution_enabled.get("true"), 0
            ),
            "real_read_only_repair_action_bundle_review_subprocess_enabled": _safe_int(
                real_read_only_repair_action_bundle_review_subprocess_enabled.get("true"), 0
            ),
            "real_read_only_repair_action_bundle_review_bundle_execution_performed": _safe_int(
                real_read_only_repair_action_bundle_review_bundle_execution_performed.get("true"), 0
            ),
            "real_read_only_repair_action_bundle_review_bundle_subprocess_invoked": _safe_int(
                real_read_only_repair_action_bundle_review_bundle_subprocess_invoked.get("true"), 0
            ),
            "real_read_only_repair_action_bundle_review_execution_performed": _safe_int(
                real_read_only_repair_action_bundle_review_execution_performed.get("true"), 0
            ),
            "real_read_only_repair_action_bundle_review_subprocess_invoked": _safe_int(
                real_read_only_repair_action_bundle_review_subprocess_invoked.get("true"), 0
            ),
            "real_repair_approval_observed": _safe_int(
                real_repair_approval_statuses.get("pending"), 0
            )
            > 0,
            "real_repair_approval_records": _safe_int(
                real_repair_approval_statuses.get("pending"), 0
            ),
            "real_repair_approval_linkage_complete": bool(
                trail_summary.get("real_repair_approval_linkage_complete")
            ),
            "real_repair_approval_orphans": _safe_int(
                trail_summary.get("real_repair_approval_orphans"), 0
            ),
            "real_repair_approval_pending": _safe_int(
                real_repair_approval_statuses.get("pending"), 0
            ),
            "real_repair_approval_source_review_approved": _safe_int(
                real_repair_approval_source_review_statuses.get("approved"), 0
            ),
            "real_repair_approval_next_action_await": _safe_int(
                real_repair_approval_next_actions.get("await_repair_execution_approval"), 0
            ),
            "real_repair_approval_operator_authorized": _safe_int(
                real_repair_approval_operator_authorized.get("true"), 0
            ),
            "real_repair_approval_required": _safe_int(
                real_repair_approval_required.get("true"), 0
            ),
            "real_repair_approval_approved": _safe_int(
                real_repair_approval_approved.get("true"), 0
            ),
            "real_repair_approval_repair_execution_enabled": _safe_int(
                real_repair_approval_repair_execution_enabled.get("true"), 0
            ),
            "real_repair_approval_real_execution_enabled": _safe_int(
                real_repair_approval_real_execution_enabled.get("true"), 0
            ),
            "real_repair_approval_subprocess_enabled": _safe_int(
                real_repair_approval_subprocess_enabled.get("true"), 0
            ),
            "real_repair_approval_repair_execution_performed": _safe_int(
                real_repair_approval_repair_execution_performed.get("true"), 0
            ),
            "real_repair_approval_repair_subprocess_invoked": _safe_int(
                real_repair_approval_repair_subprocess_invoked.get("true"), 0
            ),
            "real_repair_approval_execution_performed": _safe_int(
                real_repair_approval_execution_performed.get("true"), 0
            ),
            "real_repair_approval_subprocess_invoked": _safe_int(
                real_repair_approval_subprocess_invoked.get("true"), 0
            ),
        },
        "required_fields": [
            "schema_version",
            "schema_kind",
            "type",
            "status",
            "ready_for_mock_execution",
            "ready_for_real_execution",
            "blocking_reasons",
            "adapter_contract_observed",
            "adapter_subprocess_invoked",
            "adapter_real_execution_enabled",
            "adapter_payload_executed",
            "checks",
            "exit_codes",
            "adapter_contract",
            "real_adapter_supported",
            "real_adapter_runnable",
            "real_adapter_requires_explicit_pr",
            "real_execution_request_observed",
            "real_execution_request_rejected",
            "real_preflight_observed",
            "real_preflight_blocked",
            "real_approval_observed",
            "real_approval_records",
            "real_linkage_complete",
            "real_preflight_orphans",
            "real_approval_orphans",
            "real_approval_transition_observed",
            "real_approval_transition_records",
            "real_approval_latest_status",
            "real_final_gate_observed",
            "real_final_gate_blocked",
            "real_dry_run_envelope_observed",
            "real_dry_run_envelope_records",
            "real_dry_run_linkage_complete",
            "real_dry_run_envelope_orphans",
            "real_noop_result_observed",
            "real_noop_result_records",
            "real_noop_linkage_complete",
            "real_noop_result_orphans",
            "real_noop_result_stdout_marker_observed",
            "real_read_only_promotion_observed",
            "real_read_only_promotion_records",
            "real_read_only_promotion_linkage_complete",
            "real_read_only_promotion_orphans",
            "real_read_only_final_gate_observed",
            "real_read_only_final_gate_records",
            "real_read_only_final_gate_linkage_complete",
            "real_read_only_final_gate_orphans",
            "real_read_only_approval_observed",
            "real_read_only_approval_records",
            "real_read_only_approval_linkage_complete",
            "real_read_only_approval_orphans",
            "real_read_only_approval_transition_observed",
            "real_read_only_approval_transition_records",
            "real_read_only_approval_transition_linkage_complete",
            "real_read_only_approval_transition_orphans",
            "real_read_only_approval_latest_status",
            "real_read_only_readiness_gate_observed",
            "real_read_only_readiness_gate_records",
            "real_read_only_readiness_gate_linkage_complete",
            "real_read_only_readiness_gate_orphans",
            "real_read_only_execution_result_observed",
            "real_read_only_execution_result_records",
            "real_read_only_execution_result_linkage_complete",
            "real_read_only_execution_result_orphans",
            "real_read_only_feedback_observed",
            "real_read_only_feedback_records",
            "real_read_only_feedback_linkage_complete",
            "real_read_only_feedback_orphans",
            "real_read_only_repair_plan_observed",
            "real_read_only_repair_plan_records",
            "real_read_only_repair_plan_linkage_complete",
            "real_read_only_repair_plan_orphans",
            "real_read_only_repair_action_bundle_observed",
            "real_read_only_repair_action_bundle_records",
            "real_read_only_repair_action_bundle_linkage_complete",
            "real_read_only_repair_action_bundle_orphans",
            "real_read_only_repair_action_bundle_review_observed",
            "real_read_only_repair_action_bundle_review_records",
            "real_read_only_repair_action_bundle_review_linkage_complete",
            "real_read_only_repair_action_bundle_review_orphans",
            "real_repair_approval_observed",
            "real_repair_approval_records",
            "real_repair_approval_linkage_complete",
            "real_repair_approval_orphans",
        ],
        "trail_summary": trail_summary,
        "retry_observability": retry_observability,
        "controlled_observability": controlled_observability,
        "checks": checks,
        "exit_codes": {
            "trail": trail_exit_code(trail_summary, require_complete=True),
            "retry_observability": retry_observability_exit_code(retry_observability),
            "controlled_observability": controlled_observability_exit_code(
                controlled_observability
            ),
            "real_execution": 1,
        },
        "mock_execution_observed": _safe_int(
            controlled_mock_statuses.get("mock_executed")
        )
        > 0,
        "mock_execution_performed": _safe_int(
            controlled_mock_performed.get("true")
        ),
        "mock_subprocess_invoked": _safe_int(
            controlled_mock_subprocess_invoked.get("true")
        ),
        "mock_execution_summary_observed": _safe_int(
            mock_summary_statuses.get("mock_executed")
        )
        > 0,
        "mock_execution_summary_performed": _safe_int(
            mock_summary_performed.get("true")
        ),
        "mock_summary_subprocess_invoked": _safe_int(
            mock_summary_subprocess_invoked.get("true")
        ),
        "adapter_contract_observed": (
            _safe_int(controlled_mock_adapter.get("mock")) > 0
            and _safe_int(controlled_mock_adapter_mode.get("mock")) > 0
            and _safe_int(
                controlled_mock_adapter_result_statuses.get("mock_executed")
            )
            > 0
        ),
        "adapter_mock": _safe_int(controlled_mock_adapter.get("mock")),
        "adapter_mode_mock": _safe_int(controlled_mock_adapter_mode.get("mock")),
        "adapter_result_mock_executed": _safe_int(
            controlled_mock_adapter_result_statuses.get("mock_executed")
        ),
        "adapter_subprocess_invoked": _safe_int(
            controlled_mock_adapter_subprocess_invoked.get("true")
        ),
        "adapter_real_execution_enabled": _safe_int(
            controlled_mock_adapter_real_execution_enabled.get("true")
        ),
        "adapter_payload_executed": _safe_int(
            controlled_mock_adapter_payload_executed.get("true")
        ),
        "real_execution_request_observed": _safe_int(
            controlled_real_execution_requested.get("true")
        )
        > 0,
        "real_execution_request_rejected": _safe_int(
            controlled_reasons.get("real_execution_not_supported")
        ),
        "real_execution_requested": _safe_int(
            controlled_real_execution_requested.get("true")
        ),
        "real_execution_performed": _safe_int(
            controlled_real_execution_performed.get("true")
        ),
        "real_execution_supported_count": _safe_int(
            controlled_real_execution_supported.get("true")
        ),
        "subprocess_invoked_count": _safe_int(
            controlled_subprocess_invoked.get("true")
        ),
    }


def _build_checks(
    *,
    trail_summary: Mapping[str, Any],
    retry_observability: Mapping[str, Any],
    controlled_observability: Mapping[str, Any],
    require_operator_authorized: bool,
) -> list[dict[str, Any]]:
    counts = _safe_mapping(trail_summary.get("counts"))
    controlled_statuses = _safe_mapping(
        trail_summary.get("controlled_execution_result_statuses")
    )
    controlled_reasons = _safe_mapping(
        trail_summary.get("controlled_execution_result_reasons")
    )
    command_parse_valid = _safe_mapping(
        trail_summary.get("controlled_command_parse_valid")
    )
    command_parse_allowlisted = _safe_mapping(
        trail_summary.get("controlled_command_parse_allowlist_matched")
    )
    command_parse_execution_performed = _safe_mapping(
        trail_summary.get("controlled_command_parse_execution_performed")
    )
    operator_authorized = _safe_mapping(
        trail_summary.get("controlled_execution_operator_authorized")
    )
    gate_statuses = _safe_mapping(trail_summary.get("controlled_gate_statuses"))
    gate_would_execute = _safe_mapping(
        trail_summary.get("controlled_gate_would_execute")
    )
    gate_execution_performed = _safe_mapping(
        trail_summary.get("controlled_gate_execution_performed")
    )
    gate_reasons = _safe_mapping(trail_summary.get("controlled_gate_reasons"))
    controlled_mock_statuses = _safe_mapping(
        trail_summary.get("controlled_mock_statuses")
    )
    controlled_mock_performed = _safe_mapping(
        trail_summary.get("controlled_mock_performed")
    )
    controlled_mock_subprocess_invoked = _safe_mapping(
        trail_summary.get("controlled_mock_subprocess_invoked")
    )
    mock_summary_statuses = _safe_mapping(trail_summary.get("mock_summary_statuses"))
    mock_summary_performed = _safe_mapping(trail_summary.get("mock_summary_performed"))
    mock_summary_subprocess_invoked = _safe_mapping(
        trail_summary.get("mock_summary_subprocess_invoked")
    )
    controlled_mock_adapter = _safe_mapping(
        trail_summary.get("controlled_mock_adapter")
    )
    controlled_mock_adapter_mode = _safe_mapping(
        trail_summary.get("controlled_mock_adapter_mode")
    )
    controlled_mock_adapter_result_statuses = _safe_mapping(
        trail_summary.get("controlled_mock_adapter_result_statuses")
    )
    controlled_mock_adapter_subprocess_invoked = _safe_mapping(
        trail_summary.get("controlled_mock_adapter_subprocess_invoked")
    )
    controlled_mock_adapter_real_execution_enabled = _safe_mapping(
        trail_summary.get("controlled_mock_adapter_real_execution_enabled")
    )
    controlled_mock_adapter_payload_executed = _safe_mapping(
        trail_summary.get("controlled_mock_adapter_payload_executed")
    )
    controlled_real_execution_requested = _safe_mapping(
        trail_summary.get("controlled_real_execution_requested")
    )
    controlled_real_execution_performed = _safe_mapping(
        trail_summary.get("controlled_real_execution_performed")
    )
    controlled_real_execution_supported = _safe_mapping(
        trail_summary.get("controlled_real_execution_supported")
    )
    controlled_subprocess_invoked = _safe_mapping(
        trail_summary.get("controlled_subprocess_invoked")
    )
    real_preflight_statuses = _safe_mapping(trail_summary.get("real_preflight_statuses"))
    real_preflight_reasons = _safe_mapping(trail_summary.get("real_preflight_reasons"))
    real_preflight_would_execute = _safe_mapping(trail_summary.get("real_preflight_would_execute"))
    real_preflight_execution_performed = _safe_mapping(trail_summary.get("real_preflight_execution_performed"))
    real_preflight_subprocess_invoked = _safe_mapping(trail_summary.get("real_preflight_subprocess_invoked"))
    real_preflight_requires_explicit_pr = _safe_mapping(trail_summary.get("real_preflight_requires_explicit_pr"))
    real_approval_statuses = _safe_mapping(trail_summary.get("real_approval_statuses"))
    real_approval_enabled = _safe_mapping(trail_summary.get("real_approval_enabled"))
    real_approval_subprocess_enabled = _safe_mapping(
        trail_summary.get("real_approval_subprocess_enabled")
    )
    real_approval_execution_performed = _safe_mapping(
        trail_summary.get("real_approval_execution_performed")
    )
    real_approval_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_approval_subprocess_invoked")
    )
    real_approval_transition_statuses = _safe_mapping(
        trail_summary.get("real_approval_transition_statuses")
    )
    real_approval_transition_enabled = _safe_mapping(
        trail_summary.get("real_approval_transition_enabled")
    )
    real_approval_transition_subprocess_enabled = _safe_mapping(
        trail_summary.get("real_approval_transition_subprocess_enabled")
    )
    real_approval_transition_execution_performed = _safe_mapping(
        trail_summary.get("real_approval_transition_execution_performed")
    )
    real_approval_transition_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_approval_transition_subprocess_invoked")
    )
    real_final_gate_statuses = _safe_mapping(
        trail_summary.get("real_final_gate_statuses")
    )
    real_final_gate_would_execute = _safe_mapping(
        trail_summary.get("real_final_gate_would_execute")
    )
    real_final_gate_ready = _safe_mapping(
        trail_summary.get("real_final_gate_ready")
    )
    real_final_gate_real_execution_enabled = _safe_mapping(
        trail_summary.get("real_final_gate_real_execution_enabled")
    )
    real_final_gate_subprocess_enabled = _safe_mapping(
        trail_summary.get("real_final_gate_subprocess_enabled")
    )
    real_final_gate_execution_performed = _safe_mapping(
        trail_summary.get("real_final_gate_execution_performed")
    )
    real_final_gate_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_final_gate_subprocess_invoked")
    )
    real_dry_run_envelope_dry_run_only = _safe_mapping(
        trail_summary.get("real_dry_run_envelope_dry_run_only")
    )
    real_dry_run_envelope_would_execute = _safe_mapping(
        trail_summary.get("real_dry_run_envelope_would_execute")
    )
    real_dry_run_envelope_ready = _safe_mapping(
        trail_summary.get("real_dry_run_envelope_ready")
    )
    real_dry_run_envelope_real_execution_enabled = _safe_mapping(
        trail_summary.get("real_dry_run_envelope_real_execution_enabled")
    )
    real_dry_run_envelope_subprocess_enabled = _safe_mapping(
        trail_summary.get("real_dry_run_envelope_subprocess_enabled")
    )
    real_dry_run_envelope_execution_performed = _safe_mapping(
        trail_summary.get("real_dry_run_envelope_execution_performed")
    )
    real_dry_run_envelope_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_dry_run_envelope_subprocess_invoked")
    )
    real_noop_result_noop_only = _safe_mapping(
        trail_summary.get("real_noop_result_noop_only")
    )
    real_noop_result_rendered_command_executed = _safe_mapping(
        trail_summary.get("real_noop_result_rendered_command_executed")
    )
    real_noop_result_dry_run_command_executed = _safe_mapping(
        trail_summary.get("real_noop_result_dry_run_command_executed")
    )
    real_noop_result_real_execution_enabled = _safe_mapping(
        trail_summary.get("real_noop_result_real_execution_enabled")
    )
    real_noop_result_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_noop_result_subprocess_invoked")
    )
    real_noop_result_execution_performed = _safe_mapping(
        trail_summary.get("real_noop_result_execution_performed")
    )
    real_noop_result_exit_codes = _safe_mapping(
        trail_summary.get("real_noop_result_exit_codes")
    )
    real_noop_result_stdout_marker_observed = _safe_mapping(
        trail_summary.get("real_noop_result_stdout_marker_observed")
    )
    real_read_only_promotion_statuses = _safe_mapping(
        trail_summary.get("real_read_only_promotion_statuses")
    )
    real_read_only_promotion_candidates = _safe_mapping(
        trail_summary.get("real_read_only_promotion_candidates")
    )
    real_read_only_promotion_command_parse_valid = _safe_mapping(
        trail_summary.get("real_read_only_promotion_command_parse_valid")
    )
    real_read_only_promotion_stdout_marker_observed = _safe_mapping(
        trail_summary.get("real_read_only_promotion_stdout_marker_observed")
    )
    real_read_only_promotion_noop_exit_codes = _safe_mapping(
        trail_summary.get("real_read_only_promotion_noop_exit_codes")
    )
    real_read_only_promotion_rendered_command_executed = _safe_mapping(
        trail_summary.get("real_read_only_promotion_rendered_command_executed")
    )
    real_read_only_promotion_dry_run_command_executed = _safe_mapping(
        trail_summary.get("real_read_only_promotion_dry_run_command_executed")
    )
    real_read_only_promotion_real_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_promotion_real_execution_enabled")
    )
    real_read_only_promotion_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_promotion_subprocess_invoked")
    )
    real_read_only_promotion_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_promotion_execution_performed")
    )
    real_read_only_final_gate_statuses = _safe_mapping(
        trail_summary.get("real_read_only_final_gate_statuses")
    )
    real_read_only_final_gate_preconditions_satisfied = _safe_mapping(
        trail_summary.get("real_read_only_final_gate_preconditions_satisfied")
    )
    real_read_only_final_gate_ready = _safe_mapping(
        trail_summary.get("real_read_only_final_gate_ready")
    )
    real_read_only_final_gate_would_execute = _safe_mapping(
        trail_summary.get("real_read_only_final_gate_would_execute")
    )
    real_read_only_final_gate_read_only_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_final_gate_read_only_execution_enabled")
    )
    real_read_only_final_gate_real_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_final_gate_real_execution_enabled")
    )
    real_read_only_final_gate_subprocess_enabled = _safe_mapping(
        trail_summary.get("real_read_only_final_gate_subprocess_enabled")
    )
    real_read_only_final_gate_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_final_gate_subprocess_invoked")
    )
    real_read_only_final_gate_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_final_gate_execution_performed")
    )
    real_read_only_final_gate_rendered_command_executed = _safe_mapping(
        trail_summary.get("real_read_only_final_gate_rendered_command_executed")
    )
    real_read_only_final_gate_dry_run_command_executed = _safe_mapping(
        trail_summary.get("real_read_only_final_gate_dry_run_command_executed")
    )
    real_read_only_approval_statuses = _safe_mapping(
        trail_summary.get("real_read_only_approval_statuses")
    )
    real_read_only_approval_read_only_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_approval_read_only_execution_enabled")
    )
    real_read_only_approval_real_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_approval_real_execution_enabled")
    )
    real_read_only_approval_subprocess_enabled = _safe_mapping(
        trail_summary.get("real_read_only_approval_subprocess_enabled")
    )
    real_read_only_approval_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_approval_subprocess_invoked")
    )
    real_read_only_approval_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_approval_execution_performed")
    )
    real_read_only_approval_rendered_command_executed = _safe_mapping(
        trail_summary.get("real_read_only_approval_rendered_command_executed")
    )
    real_read_only_approval_dry_run_command_executed = _safe_mapping(
        trail_summary.get("real_read_only_approval_dry_run_command_executed")
    )
    real_read_only_approval_transition_from_statuses = _safe_mapping(
        trail_summary.get("real_read_only_approval_transition_from_statuses")
    )
    real_read_only_approval_transition_to_statuses = _safe_mapping(
        trail_summary.get("real_read_only_approval_transition_to_statuses")
    )
    real_read_only_approval_transition_read_only_execution_enabled = _safe_mapping(
        trail_summary.get(
            "real_read_only_approval_transition_read_only_execution_enabled"
        )
    )
    real_read_only_approval_transition_real_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_approval_transition_real_execution_enabled")
    )
    real_read_only_approval_transition_subprocess_enabled = _safe_mapping(
        trail_summary.get("real_read_only_approval_transition_subprocess_enabled")
    )
    real_read_only_approval_transition_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_approval_transition_subprocess_invoked")
    )
    real_read_only_approval_transition_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_approval_transition_execution_performed")
    )
    real_read_only_approval_transition_rendered_command_executed = _safe_mapping(
        trail_summary.get(
            "real_read_only_approval_transition_rendered_command_executed"
        )
    )
    real_read_only_approval_transition_dry_run_command_executed = _safe_mapping(
        trail_summary.get(
            "real_read_only_approval_transition_dry_run_command_executed"
        )
    )
    real_read_only_readiness_gate_statuses = _safe_mapping(
        trail_summary.get("real_read_only_readiness_gate_statuses")
    )
    real_read_only_readiness_gate_satisfied = _safe_mapping(
        trail_summary.get("real_read_only_readiness_gate_satisfied")
    )
    real_read_only_readiness_gate_ready = _safe_mapping(
        trail_summary.get("real_read_only_readiness_gate_ready")
    )
    real_read_only_readiness_gate_read_only_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_readiness_gate_read_only_execution_enabled")
    )
    real_read_only_readiness_gate_real_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_readiness_gate_real_execution_enabled")
    )
    real_read_only_readiness_gate_subprocess_enabled = _safe_mapping(
        trail_summary.get("real_read_only_readiness_gate_subprocess_enabled")
    )
    real_read_only_readiness_gate_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_readiness_gate_subprocess_invoked")
    )
    real_read_only_readiness_gate_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_readiness_gate_execution_performed")
    )
    real_read_only_readiness_gate_rendered_command_executed = _safe_mapping(
        trail_summary.get("real_read_only_readiness_gate_rendered_command_executed")
    )
    real_read_only_readiness_gate_dry_run_command_executed = _safe_mapping(
        trail_summary.get("real_read_only_readiness_gate_dry_run_command_executed")
    )
    real_read_only_execution_result_statuses = _safe_mapping(
        trail_summary.get("real_read_only_execution_result_statuses")
    )
    real_read_only_execution_result_exit_codes = _safe_mapping(
        trail_summary.get("real_read_only_execution_result_exit_codes")
    )
    real_read_only_execution_result_validation_reasons_empty = _safe_mapping(
        trail_summary.get("real_read_only_execution_result_validation_reasons_empty")
    )
    real_read_only_execution_result_operator_authorized = _safe_mapping(
        trail_summary.get("real_read_only_execution_result_operator_authorized")
    )
    real_read_only_execution_result_allow_guarded = _safe_mapping(
        trail_summary.get("real_read_only_execution_result_allow_guarded")
    )
    real_read_only_execution_result_read_only_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_execution_result_read_only_execution_enabled")
    )
    real_read_only_execution_result_real_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_execution_result_real_execution_enabled")
    )
    real_read_only_execution_result_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_execution_result_subprocess_invoked")
    )
    real_read_only_execution_result_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_execution_result_execution_performed")
    )
    real_read_only_execution_result_read_only_command_executed = _safe_mapping(
        trail_summary.get("real_read_only_execution_result_read_only_command_executed")
    )
    real_read_only_execution_result_rendered_command_executed = _safe_mapping(
        trail_summary.get("real_read_only_execution_result_rendered_command_executed")
    )
    real_read_only_execution_result_dry_run_command_executed = _safe_mapping(
        trail_summary.get("real_read_only_execution_result_dry_run_command_executed")
    )
    real_read_only_feedback_statuses = _safe_mapping(
        trail_summary.get("real_read_only_feedback_statuses")
    )
    real_read_only_feedback_source_statuses = _safe_mapping(
        trail_summary.get("real_read_only_feedback_source_statuses")
    )
    real_read_only_feedback_source_exit_codes = _safe_mapping(
        trail_summary.get("real_read_only_feedback_source_exit_codes")
    )
    real_read_only_feedback_next_actions = _safe_mapping(
        trail_summary.get("real_read_only_feedback_next_actions")
    )
    real_read_only_feedback_execution_observed = _safe_mapping(
        trail_summary.get("real_read_only_feedback_execution_observed")
    )
    real_read_only_feedback_failed = _safe_mapping(
        trail_summary.get("real_read_only_feedback_failed")
    )
    real_read_only_feedback_real_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_feedback_real_execution_enabled")
    )
    real_read_only_feedback_feedback_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_feedback_feedback_execution_performed")
    )
    real_read_only_feedback_feedback_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_feedback_feedback_subprocess_invoked")
    )
    real_read_only_feedback_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_feedback_execution_performed")
    )
    real_read_only_feedback_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_feedback_subprocess_invoked")
    )
    real_read_only_repair_plan_statuses = _safe_mapping(
        trail_summary.get("real_read_only_repair_plan_statuses")
    )
    real_read_only_repair_plan_source_feedback_statuses = _safe_mapping(
        trail_summary.get("real_read_only_repair_plan_source_feedback_statuses")
    )
    real_read_only_repair_plan_source_statuses = _safe_mapping(
        trail_summary.get("real_read_only_repair_plan_source_statuses")
    )
    real_read_only_repair_plan_source_exit_codes = _safe_mapping(
        trail_summary.get("real_read_only_repair_plan_source_exit_codes")
    )
    real_read_only_repair_plan_next_actions = _safe_mapping(
        trail_summary.get("real_read_only_repair_plan_next_actions")
    )
    real_read_only_repair_plan_item_counts = _safe_mapping(
        trail_summary.get("real_read_only_repair_plan_item_counts")
    )
    real_read_only_repair_plan_requires_operator_review = _safe_mapping(
        trail_summary.get("real_read_only_repair_plan_requires_operator_review")
    )
    real_read_only_repair_plan_repair_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_repair_plan_repair_execution_enabled")
    )
    real_read_only_repair_plan_real_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_repair_plan_real_execution_enabled")
    )
    real_read_only_repair_plan_subprocess_enabled = _safe_mapping(
        trail_summary.get("real_read_only_repair_plan_subprocess_enabled")
    )
    real_read_only_repair_plan_repair_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_repair_plan_repair_execution_performed")
    )
    real_read_only_repair_plan_repair_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_repair_plan_repair_subprocess_invoked")
    )
    real_read_only_repair_plan_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_repair_plan_execution_performed")
    )
    real_read_only_repair_plan_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_repair_plan_subprocess_invoked")
    )
    real_read_only_repair_action_bundle_statuses = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_statuses")
    )
    real_read_only_repair_action_bundle_source_plan_statuses = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_source_plan_statuses")
    )
    real_read_only_repair_action_bundle_source_feedback_statuses = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_source_feedback_statuses")
    )
    real_read_only_repair_action_bundle_source_statuses = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_source_statuses")
    )
    real_read_only_repair_action_bundle_source_exit_codes = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_source_exit_codes")
    )
    real_read_only_repair_action_bundle_next_actions = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_next_actions")
    )
    real_read_only_repair_action_bundle_item_counts = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_item_counts")
    )
    real_read_only_repair_action_bundle_source_item_counts = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_source_item_counts")
    )
    real_read_only_repair_action_bundle_requires_operator_review = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_requires_operator_review")
    )
    real_read_only_repair_action_bundle_reviewed = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_reviewed")
    )
    real_read_only_repair_action_bundle_bundle_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_bundle_execution_enabled")
    )
    real_read_only_repair_action_bundle_repair_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_repair_execution_enabled")
    )
    real_read_only_repair_action_bundle_real_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_real_execution_enabled")
    )
    real_read_only_repair_action_bundle_subprocess_enabled = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_subprocess_enabled")
    )
    real_read_only_repair_action_bundle_bundle_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_bundle_execution_performed")
    )
    real_read_only_repair_action_bundle_bundle_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_bundle_subprocess_invoked")
    )
    real_read_only_repair_action_bundle_repair_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_repair_execution_performed")
    )
    real_read_only_repair_action_bundle_repair_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_repair_subprocess_invoked")
    )
    real_read_only_repair_action_bundle_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_execution_performed")
    )
    real_read_only_repair_action_bundle_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_subprocess_invoked")
    )
    real_read_only_repair_action_bundle_review_statuses = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_statuses")
    )
    real_read_only_repair_action_bundle_review_source_bundle_statuses = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_source_bundle_statuses")
    )
    real_read_only_repair_action_bundle_review_source_plan_statuses = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_source_plan_statuses")
    )
    real_read_only_repair_action_bundle_review_source_feedback_statuses = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_source_feedback_statuses")
    )
    real_read_only_repair_action_bundle_review_source_statuses = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_source_statuses")
    )
    real_read_only_repair_action_bundle_review_source_exit_codes = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_source_exit_codes")
    )
    real_read_only_repair_action_bundle_review_source_item_counts = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_source_item_counts")
    )
    real_read_only_repair_action_bundle_review_next_actions = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_next_actions")
    )
    real_read_only_repair_action_bundle_review_operator_authorized = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_operator_authorized")
    )
    real_read_only_repair_action_bundle_review_requires_operator_review = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_requires_operator_review")
    )
    real_read_only_repair_action_bundle_review_reviewed = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_reviewed")
    )
    real_read_only_repair_action_bundle_review_approved = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_approved")
    )
    real_read_only_repair_action_bundle_review_rejected = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_rejected")
    )
    real_read_only_repair_action_bundle_review_bundle_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_bundle_execution_enabled")
    )
    real_read_only_repair_action_bundle_review_repair_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_repair_execution_enabled")
    )
    real_read_only_repair_action_bundle_review_real_execution_enabled = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_real_execution_enabled")
    )
    real_read_only_repair_action_bundle_review_subprocess_enabled = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_subprocess_enabled")
    )
    real_read_only_repair_action_bundle_review_bundle_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_bundle_execution_performed")
    )
    real_read_only_repair_action_bundle_review_bundle_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_bundle_subprocess_invoked")
    )
    real_read_only_repair_action_bundle_review_repair_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_repair_execution_performed")
    )
    real_read_only_repair_action_bundle_review_repair_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_repair_subprocess_invoked")
    )
    real_read_only_repair_action_bundle_review_execution_performed = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_execution_performed")
    )
    real_read_only_repair_action_bundle_review_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_read_only_repair_action_bundle_review_subprocess_invoked")
    )
    real_repair_approval_statuses = _safe_mapping(
        trail_summary.get("real_repair_approval_statuses")
    )
    real_repair_approval_source_review_statuses = _safe_mapping(
        trail_summary.get("real_repair_approval_source_review_statuses")
    )
    real_repair_approval_source_bundle_statuses = _safe_mapping(
        trail_summary.get("real_repair_approval_source_bundle_statuses")
    )
    real_repair_approval_next_actions = _safe_mapping(
        trail_summary.get("real_repair_approval_next_actions")
    )
    real_repair_approval_operator_authorized = _safe_mapping(
        trail_summary.get("real_repair_approval_operator_authorized")
    )
    real_repair_approval_required = _safe_mapping(
        trail_summary.get("real_repair_approval_required")
    )
    real_repair_approval_approved = _safe_mapping(
        trail_summary.get("real_repair_approval_approved")
    )
    real_repair_approval_rejected = _safe_mapping(
        trail_summary.get("real_repair_approval_rejected")
    )
    real_repair_approval_repair_execution_enabled = _safe_mapping(
        trail_summary.get("real_repair_approval_repair_execution_enabled")
    )
    real_repair_approval_real_execution_enabled = _safe_mapping(
        trail_summary.get("real_repair_approval_real_execution_enabled")
    )
    real_repair_approval_subprocess_enabled = _safe_mapping(
        trail_summary.get("real_repair_approval_subprocess_enabled")
    )
    real_repair_approval_repair_execution_performed = _safe_mapping(
        trail_summary.get("real_repair_approval_repair_execution_performed")
    )
    real_repair_approval_repair_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_repair_approval_repair_subprocess_invoked")
    )
    real_repair_approval_execution_performed = _safe_mapping(
        trail_summary.get("real_repair_approval_execution_performed")
    )
    real_repair_approval_subprocess_invoked = _safe_mapping(
        trail_summary.get("real_repair_approval_subprocess_invoked")
    )

    checks = [
        _check(
            "trail_chain_complete",
            bool(trail_summary.get("chain_complete")),
            bool(trail_summary.get("chain_complete")),
        ),
        _check(
            "trail_has_controlled_execution_result",
            _safe_int(counts.get("controlled_execution_results")) > 0,
            _safe_int(counts.get("controlled_execution_results")),
        ),
        _check(
            "controlled_result_rejected",
            _safe_int(controlled_statuses.get("rejected")) > 0,
            _safe_int(controlled_statuses.get("rejected")),
        ),
        _check(
            "controlled_result_not_implemented",
            _safe_int(controlled_reasons.get("controlled_execution_not_implemented"))
            > 0,
            _safe_int(controlled_reasons.get("controlled_execution_not_implemented")),
        ),
        _check(
            "command_parse_valid",
            _safe_int(command_parse_valid.get("true")) > 0,
            _safe_int(command_parse_valid.get("true")),
        ),
        _check(
            "command_parse_allowlisted",
            _safe_int(command_parse_allowlisted.get("true")) > 0,
            _safe_int(command_parse_allowlisted.get("true")),
        ),
        _check(
            "command_parse_did_not_execute",
            _safe_int(command_parse_execution_performed.get("true")) == 0,
            _safe_int(command_parse_execution_performed.get("true")),
        ),
        _check(
            "controlled_gate_blocked",
            _safe_int(gate_statuses.get("blocked")) > 0,
            _safe_int(gate_statuses.get("blocked")),
        ),
        _check(
            "controlled_gate_would_not_execute",
            _safe_int(gate_would_execute.get("true")) == 0,
            _safe_int(gate_would_execute.get("true")),
        ),
        _check(
            "controlled_gate_did_not_execute",
            _safe_int(gate_execution_performed.get("true")) == 0,
            _safe_int(gate_execution_performed.get("true")),
        ),
        _check(
            "controlled_gate_not_enabled_reason_observed",
            _safe_int(gate_reasons.get("controlled_execution_not_enabled")) > 0,
            _safe_int(gate_reasons.get("controlled_execution_not_enabled")),
        ),
        _check(
            "retry_observability_passed",
            retry_observability.get("status") == "passed",
            retry_observability.get("status"),
        ),
        _check(
            "controlled_observability_passed",
            controlled_observability.get("status") == "passed",
            controlled_observability.get("status"),
        ),
        _check(
            "controlled_observability_reports_no_execution",
            _safe_int(
                controlled_observability.get(
                    "controlled_execution_gate_execution_performed"
                )
            )
            == 0
            and _safe_int(controlled_observability.get("controlled_execution_executed"))
            == 0,
            {
                "gate_execution_performed": controlled_observability.get(
                    "controlled_execution_gate_execution_performed"
                ),
                "controlled_execution_executed": controlled_observability.get(
                    "controlled_execution_executed"
                ),
            },
        ),
        _check(
            "mock_execution_observed",
            _safe_int(controlled_mock_statuses.get("mock_executed")) > 0,
            _safe_int(controlled_mock_statuses.get("mock_executed")),
        ),
        _check(
            "mock_execution_performed",
            _safe_int(controlled_mock_performed.get("true")) > 0,
            _safe_int(controlled_mock_performed.get("true")),
        ),
        _check(
            "mock_execution_did_not_invoke_subprocess",
            _safe_int(controlled_mock_subprocess_invoked.get("true")) == 0,
            _safe_int(controlled_mock_subprocess_invoked.get("true")),
        ),
        _check(
            "mock_execution_summary_observed",
            _safe_int(mock_summary_statuses.get("mock_executed")) > 0,
            _safe_int(mock_summary_statuses.get("mock_executed")),
        ),
        _check(
            "mock_execution_summary_performed",
            _safe_int(mock_summary_performed.get("true")) > 0,
            _safe_int(mock_summary_performed.get("true")),
        ),
        _check(
            "mock_execution_summary_did_not_invoke_subprocess",
            _safe_int(mock_summary_subprocess_invoked.get("true")) == 0,
            _safe_int(mock_summary_subprocess_invoked.get("true")),
        ),
        _check(
            "adapter_contract_observed",
            _safe_int(controlled_mock_adapter.get("mock")) > 0
            and _safe_int(controlled_mock_adapter_mode.get("mock")) > 0
            and _safe_int(
                controlled_mock_adapter_result_statuses.get("mock_executed")
            )
            > 0,
            {
                "adapter_mock": _safe_int(controlled_mock_adapter.get("mock")),
                "adapter_mode_mock": _safe_int(
                    controlled_mock_adapter_mode.get("mock")
                ),
                "adapter_result_mock_executed": _safe_int(
                    controlled_mock_adapter_result_statuses.get("mock_executed")
                ),
            },
        ),
        _check(
            "adapter_is_mock",
            _safe_int(controlled_mock_adapter.get("mock")) > 0,
            _safe_int(controlled_mock_adapter.get("mock")),
        ),
        _check(
            "adapter_mode_is_mock",
            _safe_int(controlled_mock_adapter_mode.get("mock")) > 0,
            _safe_int(controlled_mock_adapter_mode.get("mock")),
        ),
        _check(
            "adapter_result_mock_executed",
            _safe_int(
                controlled_mock_adapter_result_statuses.get("mock_executed")
            )
            > 0,
            _safe_int(
                controlled_mock_adapter_result_statuses.get("mock_executed")
            ),
        ),
        _check(
            "adapter_subprocess_not_invoked",
            _safe_int(controlled_mock_adapter_subprocess_invoked.get("true")) == 0,
            _safe_int(controlled_mock_adapter_subprocess_invoked.get("true")),
        ),
        _check(
            "adapter_real_execution_not_enabled",
            _safe_int(
                controlled_mock_adapter_real_execution_enabled.get("true")
            )
            == 0,
            _safe_int(
                controlled_mock_adapter_real_execution_enabled.get("true")
            ),
        ),
        _check(
            "adapter_payload_not_executed",
            _safe_int(controlled_mock_adapter_payload_executed.get("true")) == 0,
            _safe_int(controlled_mock_adapter_payload_executed.get("true")),
        ),
        _check(
            "real_execution_request_rejected_if_observed",
            _safe_int(controlled_real_execution_requested.get("true")) == 0
            or _safe_int(controlled_reasons.get("real_execution_not_supported")) > 0,
            {
                "requested": _safe_int(
                    controlled_real_execution_requested.get("true")
                ),
                "rejected": _safe_int(
                    controlled_reasons.get("real_execution_not_supported")
                ),
            },
        ),
        _check(
            "real_execution_request_did_not_execute",
            _safe_int(controlled_real_execution_performed.get("true")) == 0,
            _safe_int(controlled_real_execution_performed.get("true")),
        ),
        _check(
            "real_execution_request_did_not_enable_support",
            _safe_int(controlled_real_execution_supported.get("true")) == 0,
            _safe_int(controlled_real_execution_supported.get("true")),
        ),
        _check(
            "real_execution_request_did_not_invoke_subprocess",
            _safe_int(controlled_subprocess_invoked.get("true")) == 0,
            _safe_int(controlled_subprocess_invoked.get("true")),
        ),
        _check(
            "real_preflight_observed_if_real_request_observed",
            _safe_int(controlled_real_execution_requested.get("true")) == 0
            or _safe_int(real_preflight_statuses.get("blocked")) > 0,
            {
                "real_execution_requested": _safe_int(controlled_real_execution_requested.get("true")),
                "real_preflight_blocked": _safe_int(real_preflight_statuses.get("blocked")),
            },
        ),
        _check(
            "real_preflight_remains_blocked",
            _safe_int(real_preflight_statuses.get("blocked")) >= _safe_int(real_preflight_statuses.get("allowed")),
            dict(real_preflight_statuses),
        ),
        _check(
            "real_preflight_does_not_would_execute",
            _safe_int(real_preflight_would_execute.get("true")) == 0,
            _safe_int(real_preflight_would_execute.get("true")),
        ),
        _check(
            "real_preflight_does_not_execute",
            _safe_int(real_preflight_execution_performed.get("true")) == 0,
            _safe_int(real_preflight_execution_performed.get("true")),
        ),
        _check(
            "real_preflight_does_not_invoke_subprocess",
            _safe_int(real_preflight_subprocess_invoked.get("true")) == 0,
            _safe_int(real_preflight_subprocess_invoked.get("true")),
        ),
        _check(
            "real_preflight_requires_explicit_pr",
            _safe_int(real_preflight_requires_explicit_pr.get("true")) > 0
            or _safe_int(controlled_real_execution_requested.get("true")) == 0,
            _safe_int(real_preflight_requires_explicit_pr.get("true")),
        ),
        _check(
            "real_approval_observed_if_preflight_observed",
            _safe_int(real_preflight_statuses.get("blocked")) == 0
            or sum(_safe_int(value) for value in real_approval_statuses.values()) > 0,
            {
                "real_preflight_blocked": _safe_int(real_preflight_statuses.get("blocked")),
                "real_approval_records": sum(
                    _safe_int(value) for value in real_approval_statuses.values()
                ),
            },
        ),
        _check(
            "real_approval_does_not_enable_real_execution",
            _safe_int(real_approval_enabled.get("true")) == 0,
            _safe_int(real_approval_enabled.get("true")),
        ),
        _check(
            "real_approval_does_not_enable_subprocess",
            _safe_int(real_approval_subprocess_enabled.get("true")) == 0,
            _safe_int(real_approval_subprocess_enabled.get("true")),
        ),
        _check(
            "real_approval_does_not_execute",
            _safe_int(real_approval_execution_performed.get("true")) == 0,
            _safe_int(real_approval_execution_performed.get("true")),
        ),
        _check(
            "real_approval_does_not_invoke_subprocess",
            _safe_int(real_approval_subprocess_invoked.get("true")) == 0,
            _safe_int(real_approval_subprocess_invoked.get("true")),
        ),
        _check(
            "real_preflight_links_to_controlled_result",
            _safe_int(counts.get("real_execution_preflights"), 0) == 0
            or _safe_int(trail_summary.get("real_preflight_orphans"), 0) == 0,
            {
                "real_execution_preflights": _safe_int(
                    counts.get("real_execution_preflights"), 0
                ),
                "real_preflight_orphans": _safe_int(
                    trail_summary.get("real_preflight_orphans"), 0
                ),
            },
        ),
        _check(
            "real_approval_links_to_preflight",
            _safe_int(counts.get("real_execution_approvals"), 0) == 0
            or _safe_int(trail_summary.get("real_approval_orphans"), 0) == 0,
            {
                "real_execution_approvals": _safe_int(
                    counts.get("real_execution_approvals"), 0
                ),
                "real_approval_orphans": _safe_int(
                    trail_summary.get("real_approval_orphans"), 0
                ),
            },
        ),
        _check(
            "real_approval_transition_does_not_enable_real_execution",
            _safe_int(real_approval_transition_enabled.get("true"), 0) == 0,
            _safe_int(real_approval_transition_enabled.get("true"), 0),
        ),
        _check(
            "real_approval_transition_does_not_enable_subprocess",
            _safe_int(real_approval_transition_subprocess_enabled.get("true"), 0) == 0,
            _safe_int(real_approval_transition_subprocess_enabled.get("true"), 0),
        ),
        _check(
            "real_approval_transition_does_not_execute",
            _safe_int(real_approval_transition_execution_performed.get("true"), 0) == 0,
            _safe_int(real_approval_transition_execution_performed.get("true"), 0),
        ),
        _check(
            "real_approval_transition_does_not_invoke_subprocess",
            _safe_int(real_approval_transition_subprocess_invoked.get("true"), 0) == 0,
            _safe_int(real_approval_transition_subprocess_invoked.get("true"), 0),
        ),
        _check(
            "real_final_gate_observed_after_approved_transition",
            _safe_int(real_approval_transition_statuses.get("approved"), 0) == 0
            or _safe_int(real_final_gate_statuses.get("blocked"), 0) > 0,
            {
                "approved_transitions": _safe_int(
                    real_approval_transition_statuses.get("approved"), 0
                ),
                "blocked_final_gates": _safe_int(
                    real_final_gate_statuses.get("blocked"), 0
                ),
            },
        ),
        _check(
            "real_final_gate_remains_blocked",
            _safe_int(real_final_gate_statuses.get("blocked"), 0) > 0,
            _safe_int(real_final_gate_statuses.get("blocked"), 0),
        ),
        _check(
            "real_final_gate_would_not_execute",
            _safe_int(real_final_gate_would_execute.get("true"), 0) == 0,
            _safe_int(real_final_gate_would_execute.get("true"), 0),
        ),
        _check(
            "real_final_gate_not_ready",
            _safe_int(real_final_gate_ready.get("true"), 0) == 0,
            _safe_int(real_final_gate_ready.get("true"), 0),
        ),
        _check(
            "real_final_gate_does_not_enable_real_execution",
            _safe_int(real_final_gate_real_execution_enabled.get("true"), 0) == 0,
            _safe_int(real_final_gate_real_execution_enabled.get("true"), 0),
        ),
        _check(
            "real_final_gate_does_not_enable_subprocess",
            _safe_int(real_final_gate_subprocess_enabled.get("true"), 0) == 0,
            _safe_int(real_final_gate_subprocess_enabled.get("true"), 0),
        ),
        _check(
            "real_final_gate_does_not_execute",
            _safe_int(real_final_gate_execution_performed.get("true"), 0) == 0,
            _safe_int(real_final_gate_execution_performed.get("true"), 0),
        ),
        _check(
            "real_final_gate_does_not_invoke_subprocess",
            _safe_int(real_final_gate_subprocess_invoked.get("true"), 0) == 0,
            _safe_int(real_final_gate_subprocess_invoked.get("true"), 0),
        ),
        _check(
            "real_dry_run_envelope_observed_after_final_gate",
            _safe_int(real_final_gate_statuses.get("blocked"), 0) == 0
            or _safe_int(real_dry_run_envelope_dry_run_only.get("true"), 0) > 0,
            {
                "blocked_final_gates": _safe_int(
                    real_final_gate_statuses.get("blocked"), 0
                ),
                "dry_run_envelopes": _safe_int(
                    real_dry_run_envelope_dry_run_only.get("true"), 0
                ),
            },
        ),
        _check(
            "real_dry_run_envelope_is_dry_run_only",
            _safe_int(real_dry_run_envelope_dry_run_only.get("true"), 0) > 0,
            _safe_int(real_dry_run_envelope_dry_run_only.get("true"), 0),
        ),
        _check(
            "real_dry_run_envelope_would_not_execute",
            _safe_int(real_dry_run_envelope_would_execute.get("true"), 0) == 0,
            _safe_int(real_dry_run_envelope_would_execute.get("true"), 0),
        ),
        _check(
            "real_dry_run_envelope_not_ready",
            _safe_int(real_dry_run_envelope_ready.get("true"), 0) == 0,
            _safe_int(real_dry_run_envelope_ready.get("true"), 0),
        ),
        _check(
            "real_dry_run_envelope_does_not_enable_real_execution",
            _safe_int(real_dry_run_envelope_real_execution_enabled.get("true"), 0) == 0,
            _safe_int(real_dry_run_envelope_real_execution_enabled.get("true"), 0),
        ),
        _check(
            "real_dry_run_envelope_does_not_enable_subprocess",
            _safe_int(real_dry_run_envelope_subprocess_enabled.get("true"), 0) == 0,
            _safe_int(real_dry_run_envelope_subprocess_enabled.get("true"), 0),
        ),
        _check(
            "real_dry_run_envelope_does_not_execute",
            _safe_int(real_dry_run_envelope_execution_performed.get("true"), 0) == 0,
            _safe_int(real_dry_run_envelope_execution_performed.get("true"), 0),
        ),
        _check(
            "real_dry_run_envelope_does_not_invoke_subprocess",
            _safe_int(real_dry_run_envelope_subprocess_invoked.get("true"), 0) == 0,
            _safe_int(real_dry_run_envelope_subprocess_invoked.get("true"), 0),
        ),
        _check(
            "real_dry_run_envelope_links_to_final_gate",
            _safe_int(real_dry_run_envelope_dry_run_only.get("true"), 0) == 0
            or _safe_int(trail_summary.get("real_dry_run_envelope_orphans"), 0) == 0,
            {
                "real_dry_run_envelopes": _safe_int(
                    real_dry_run_envelope_dry_run_only.get("true"), 0
                ),
                "real_dry_run_envelope_orphans": _safe_int(
                    trail_summary.get("real_dry_run_envelope_orphans"), 0
                ),
            },
        ),
        _check(
            "real_noop_result_observed_after_dry_run_envelope",
            _safe_int(real_dry_run_envelope_dry_run_only.get("true"), 0) == 0
            or _safe_int(real_noop_result_noop_only.get("true"), 0) > 0,
            {
                "dry_run_envelopes": _safe_int(
                    real_dry_run_envelope_dry_run_only.get("true"), 0
                ),
                "noop_results": _safe_int(
                    real_noop_result_noop_only.get("true"), 0
                ),
            },
        ),
        _check(
            "real_noop_result_is_noop_only",
            _safe_int(real_noop_result_noop_only.get("true"), 0) > 0,
            _safe_int(real_noop_result_noop_only.get("true"), 0),
        ),
        _check(
            "real_noop_result_did_not_execute_rendered_command",
            _safe_int(real_noop_result_rendered_command_executed.get("true"), 0) == 0,
            _safe_int(real_noop_result_rendered_command_executed.get("true"), 0),
        ),
        _check(
            "real_noop_result_did_not_execute_dry_run_command",
            _safe_int(real_noop_result_dry_run_command_executed.get("true"), 0) == 0,
            _safe_int(real_noop_result_dry_run_command_executed.get("true"), 0),
        ),
        _check(
            "real_noop_result_does_not_enable_real_execution",
            _safe_int(real_noop_result_real_execution_enabled.get("true"), 0) == 0,
            _safe_int(real_noop_result_real_execution_enabled.get("true"), 0),
        ),
        _check(
            "real_noop_result_invoked_subprocess_once",
            _safe_int(real_noop_result_subprocess_invoked.get("true"), 0) == 1,
            _safe_int(real_noop_result_subprocess_invoked.get("true"), 0),
        ),
        _check(
            "real_noop_result_execution_performed_once",
            _safe_int(real_noop_result_execution_performed.get("true"), 0) == 1,
            _safe_int(real_noop_result_execution_performed.get("true"), 0),
        ),
        _check(
            "real_noop_result_exit_code_zero",
            _safe_int(real_noop_result_exit_codes.get("0"), 0) == 1,
            real_noop_result_exit_codes,
        ),
        _check(
            "real_noop_result_links_to_dry_run_envelope",
            _safe_int(real_noop_result_noop_only.get("true"), 0) == 0
            or _safe_int(trail_summary.get("real_noop_result_orphans"), 0) == 0,
            {
                "noop_results": _safe_int(
                    real_noop_result_noop_only.get("true"), 0
                ),
                "real_noop_result_orphans": _safe_int(
                    trail_summary.get("real_noop_result_orphans"), 0
                ),
            },
        ),
        _check(
            "real_noop_result_stdout_marker_observed",
            _safe_int(real_noop_result_stdout_marker_observed.get("true"), 0) == 1,
            _safe_int(real_noop_result_stdout_marker_observed.get("true"), 0),
        ),
        _check(
            "real_read_only_promotion_observed_after_noop_result",
            _safe_int(real_noop_result_noop_only.get("true"), 0) == 0
            or _safe_int(real_read_only_promotion_statuses.get("promoted"), 0) > 0,
            {
                "noop_results": _safe_int(real_noop_result_noop_only.get("true"), 0),
                "promotions": _safe_int(
                    real_read_only_promotion_statuses.get("promoted"), 0
                ),
            },
        ),
        _check(
            "real_read_only_promotion_links_to_noop_result",
            _safe_int(real_read_only_promotion_statuses.get("promoted"), 0) == 0
            or _safe_int(
                trail_summary.get("real_read_only_promotion_orphans"), 0
            )
            == 0,
            {
                "promotions": _safe_int(
                    real_read_only_promotion_statuses.get("promoted"), 0
                ),
                "orphans": _safe_int(
                    trail_summary.get("real_read_only_promotion_orphans"), 0
                ),
            },
        ),
        _check(
            "real_read_only_promotion_is_promoted",
            _safe_int(real_read_only_promotion_statuses.get("promoted"), 0) == 1,
            _safe_int(real_read_only_promotion_statuses.get("promoted"), 0),
        ),
        _check(
            "real_read_only_promotion_candidate",
            _safe_int(real_read_only_promotion_candidates.get("true"), 0) == 1,
            _safe_int(real_read_only_promotion_candidates.get("true"), 0),
        ),
        _check(
            "real_read_only_promotion_command_parse_valid",
            _safe_int(real_read_only_promotion_command_parse_valid.get("true"), 0)
            == 1,
            _safe_int(real_read_only_promotion_command_parse_valid.get("true"), 0),
        ),
        _check(
            "real_read_only_promotion_stdout_marker_observed",
            _safe_int(
                real_read_only_promotion_stdout_marker_observed.get("true"), 0
            )
            == 1,
            _safe_int(
                real_read_only_promotion_stdout_marker_observed.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_promotion_noop_exit_code_zero",
            _safe_int(real_read_only_promotion_noop_exit_codes.get("0"), 0) == 1,
            real_read_only_promotion_noop_exit_codes,
        ),
        _check(
            "real_read_only_promotion_did_not_execute_rendered_command",
            _safe_int(
                real_read_only_promotion_rendered_command_executed.get("true"), 0
            )
            == 0,
            _safe_int(
                real_read_only_promotion_rendered_command_executed.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_promotion_did_not_execute_dry_run_command",
            _safe_int(
                real_read_only_promotion_dry_run_command_executed.get("true"), 0
            )
            == 0,
            _safe_int(
                real_read_only_promotion_dry_run_command_executed.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_promotion_does_not_enable_real_execution",
            _safe_int(
                real_read_only_promotion_real_execution_enabled.get("true"), 0
            )
            == 0,
            _safe_int(
                real_read_only_promotion_real_execution_enabled.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_promotion_does_not_invoke_subprocess",
            _safe_int(real_read_only_promotion_subprocess_invoked.get("true"), 0)
            == 0,
            _safe_int(real_read_only_promotion_subprocess_invoked.get("true"), 0),
        ),
        _check(
            "real_read_only_promotion_does_not_execute",
            _safe_int(real_read_only_promotion_execution_performed.get("true"), 0)
            == 0,
            _safe_int(real_read_only_promotion_execution_performed.get("true"), 0),
        ),
        _check(
            "real_read_only_final_gate_observed_after_promotion",
            _safe_int(real_read_only_promotion_statuses.get("promoted"), 0) == 0
            or _safe_int(real_read_only_final_gate_statuses.get("blocked"), 0) > 0,
            {
                "promotions": _safe_int(
                    real_read_only_promotion_statuses.get("promoted"), 0
                ),
                "final_gates": _safe_int(
                    real_read_only_final_gate_statuses.get("blocked"), 0
                ),
            },
        ),
        _check(
            "real_read_only_final_gate_links_to_promotion",
            _safe_int(real_read_only_final_gate_statuses.get("blocked"), 0) == 0
            or _safe_int(
                trail_summary.get("real_read_only_final_gate_orphans"), 0
            )
            == 0,
            {
                "final_gates": _safe_int(
                    real_read_only_final_gate_statuses.get("blocked"), 0
                ),
                "orphans": _safe_int(
                    trail_summary.get("real_read_only_final_gate_orphans"), 0
                ),
            },
        ),
        _check(
            "real_read_only_final_gate_is_blocked",
            _safe_int(real_read_only_final_gate_statuses.get("blocked"), 0) == 1,
            _safe_int(real_read_only_final_gate_statuses.get("blocked"), 0),
        ),
        _check(
            "real_read_only_final_gate_preconditions_satisfied",
            _safe_int(
                real_read_only_final_gate_preconditions_satisfied.get("true"), 0
            )
            == 1,
            _safe_int(
                real_read_only_final_gate_preconditions_satisfied.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_final_gate_not_ready",
            _safe_int(real_read_only_final_gate_ready.get("true"), 0) == 0,
            _safe_int(real_read_only_final_gate_ready.get("true"), 0),
        ),
        _check(
            "real_read_only_final_gate_would_not_execute",
            _safe_int(real_read_only_final_gate_would_execute.get("true"), 0) == 0,
            _safe_int(real_read_only_final_gate_would_execute.get("true"), 0),
        ),
        _check(
            "real_read_only_final_gate_does_not_enable_read_only_execution",
            _safe_int(
                real_read_only_final_gate_read_only_execution_enabled.get("true"), 0
            )
            == 0,
            _safe_int(
                real_read_only_final_gate_read_only_execution_enabled.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_final_gate_does_not_enable_real_execution",
            _safe_int(
                real_read_only_final_gate_real_execution_enabled.get("true"), 0
            )
            == 0,
            _safe_int(
                real_read_only_final_gate_real_execution_enabled.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_final_gate_does_not_enable_subprocess",
            _safe_int(real_read_only_final_gate_subprocess_enabled.get("true"), 0)
            == 0,
            _safe_int(real_read_only_final_gate_subprocess_enabled.get("true"), 0),
        ),
        _check(
            "real_read_only_final_gate_does_not_invoke_subprocess",
            _safe_int(real_read_only_final_gate_subprocess_invoked.get("true"), 0)
            == 0,
            _safe_int(real_read_only_final_gate_subprocess_invoked.get("true"), 0),
        ),
        _check(
            "real_read_only_final_gate_does_not_execute",
            _safe_int(real_read_only_final_gate_execution_performed.get("true"), 0)
            == 0,
            _safe_int(real_read_only_final_gate_execution_performed.get("true"), 0),
        ),
        _check(
            "real_read_only_final_gate_did_not_execute_rendered_command",
            _safe_int(
                real_read_only_final_gate_rendered_command_executed.get("true"), 0
            )
            == 0,
            _safe_int(
                real_read_only_final_gate_rendered_command_executed.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_final_gate_did_not_execute_dry_run_command",
            _safe_int(
                real_read_only_final_gate_dry_run_command_executed.get("true"), 0
            )
            == 0,
            _safe_int(
                real_read_only_final_gate_dry_run_command_executed.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_approval_observed_after_final_gate",
            _safe_int(real_read_only_final_gate_statuses.get("blocked"), 0) == 0
            or _safe_int(real_read_only_approval_statuses.get("pending"), 0) > 0,
            {
                "final_gates": _safe_int(
                    real_read_only_final_gate_statuses.get("blocked"), 0
                ),
                "approvals": _safe_int(
                    real_read_only_approval_statuses.get("pending"), 0
                ),
            },
        ),
        _check(
            "real_read_only_approval_links_to_final_gate",
            _safe_int(real_read_only_approval_statuses.get("pending"), 0) == 0
            or _safe_int(
                trail_summary.get("real_read_only_approval_orphans"), 0
            )
            == 0,
            {
                "approvals": _safe_int(
                    real_read_only_approval_statuses.get("pending"), 0
                ),
                "orphans": _safe_int(
                    trail_summary.get("real_read_only_approval_orphans"), 0
                ),
            },
        ),
        _check(
            "real_read_only_approval_is_pending",
            _safe_int(real_read_only_approval_statuses.get("pending"), 0) == 1,
            _safe_int(real_read_only_approval_statuses.get("pending"), 0),
        ),
        _check(
            "real_read_only_approval_does_not_enable_read_only_execution",
            _safe_int(
                real_read_only_approval_read_only_execution_enabled.get("true"), 0
            )
            == 0,
            _safe_int(
                real_read_only_approval_read_only_execution_enabled.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_approval_does_not_enable_real_execution",
            _safe_int(real_read_only_approval_real_execution_enabled.get("true"), 0)
            == 0,
            _safe_int(real_read_only_approval_real_execution_enabled.get("true"), 0),
        ),
        _check(
            "real_read_only_approval_does_not_enable_subprocess",
            _safe_int(real_read_only_approval_subprocess_enabled.get("true"), 0)
            == 0,
            _safe_int(real_read_only_approval_subprocess_enabled.get("true"), 0),
        ),
        _check(
            "real_read_only_approval_does_not_invoke_subprocess",
            _safe_int(real_read_only_approval_subprocess_invoked.get("true"), 0)
            == 0,
            _safe_int(real_read_only_approval_subprocess_invoked.get("true"), 0),
        ),
        _check(
            "real_read_only_approval_does_not_execute",
            _safe_int(real_read_only_approval_execution_performed.get("true"), 0)
            == 0,
            _safe_int(real_read_only_approval_execution_performed.get("true"), 0),
        ),
        _check(
            "real_read_only_approval_did_not_execute_rendered_command",
            _safe_int(
                real_read_only_approval_rendered_command_executed.get("true"), 0
            )
            == 0,
            _safe_int(
                real_read_only_approval_rendered_command_executed.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_approval_did_not_execute_dry_run_command",
            _safe_int(
                real_read_only_approval_dry_run_command_executed.get("true"), 0
            )
            == 0,
            _safe_int(
                real_read_only_approval_dry_run_command_executed.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_approval_transition_observed_after_approval",
            _safe_int(real_read_only_approval_statuses.get("pending"), 0) == 0
            or _safe_int(
                real_read_only_approval_transition_to_statuses.get("approved"), 0
            )
            > 0
            or _safe_int(
                real_read_only_approval_transition_to_statuses.get("rejected"), 0
            )
            > 0,
            {
                "approvals": _safe_int(
                    real_read_only_approval_statuses.get("pending"), 0
                ),
                "approved_transitions": _safe_int(
                    real_read_only_approval_transition_to_statuses.get("approved"),
                    0,
                ),
                "rejected_transitions": _safe_int(
                    real_read_only_approval_transition_to_statuses.get("rejected"),
                    0,
                ),
            },
        ),
        _check(
            "real_read_only_approval_transition_links_to_approval",
            (
                _safe_int(
                    real_read_only_approval_transition_to_statuses.get("approved"),
                    0,
                )
                + _safe_int(
                    real_read_only_approval_transition_to_statuses.get("rejected"),
                    0,
                )
            )
            == 0
            or _safe_int(
                trail_summary.get("real_read_only_approval_transition_orphans"), 0
            )
            == 0,
            {
                "transitions": (
                    _safe_int(
                        real_read_only_approval_transition_to_statuses.get(
                            "approved"
                        ),
                        0,
                    )
                    + _safe_int(
                        real_read_only_approval_transition_to_statuses.get(
                            "rejected"
                        ),
                        0,
                    )
                ),
                "orphans": _safe_int(
                    trail_summary.get(
                        "real_read_only_approval_transition_orphans"
                    ),
                    0,
                ),
            },
        ),
        _check(
            "real_read_only_approval_transition_from_pending",
            _safe_int(
                real_read_only_approval_transition_from_statuses.get("pending"), 0
            )
            == 1,
            _safe_int(
                real_read_only_approval_transition_from_statuses.get("pending"), 0
            ),
        ),
        _check(
            "real_read_only_approval_transition_latest_status_approved",
            str(
                trail_summary.get("real_read_only_approval_latest_status")
                or "unknown"
            )
            == "approved",
            trail_summary.get("real_read_only_approval_latest_status"),
        ),
        _check(
            "real_read_only_approval_transition_does_not_enable_read_only_execution",
            _safe_int(
                real_read_only_approval_transition_read_only_execution_enabled.get(
                    "true"
                ),
                0,
            )
            == 0,
            _safe_int(
                real_read_only_approval_transition_read_only_execution_enabled.get(
                    "true"
                ),
                0,
            ),
        ),
        _check(
            "real_read_only_approval_transition_does_not_enable_real_execution",
            _safe_int(
                real_read_only_approval_transition_real_execution_enabled.get("true"),
                0,
            )
            == 0,
            _safe_int(
                real_read_only_approval_transition_real_execution_enabled.get("true"),
                0,
            ),
        ),
        _check(
            "real_read_only_approval_transition_does_not_enable_subprocess",
            _safe_int(
                real_read_only_approval_transition_subprocess_enabled.get("true"), 0
            )
            == 0,
            _safe_int(
                real_read_only_approval_transition_subprocess_enabled.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_approval_transition_does_not_invoke_subprocess",
            _safe_int(
                real_read_only_approval_transition_subprocess_invoked.get("true"), 0
            )
            == 0,
            _safe_int(
                real_read_only_approval_transition_subprocess_invoked.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_approval_transition_does_not_execute",
            _safe_int(
                real_read_only_approval_transition_execution_performed.get("true"), 0
            )
            == 0,
            _safe_int(
                real_read_only_approval_transition_execution_performed.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_approval_transition_did_not_execute_rendered_command",
            _safe_int(
                real_read_only_approval_transition_rendered_command_executed.get(
                    "true"
                ),
                0,
            )
            == 0,
            _safe_int(
                real_read_only_approval_transition_rendered_command_executed.get(
                    "true"
                ),
                0,
            ),
        ),
        _check(
            "real_read_only_approval_transition_did_not_execute_dry_run_command",
            _safe_int(
                real_read_only_approval_transition_dry_run_command_executed.get(
                    "true"
                ),
                0,
            )
            == 0,
            _safe_int(
                real_read_only_approval_transition_dry_run_command_executed.get(
                    "true"
                ),
                0,
            ),
        ),
        _check(
            "real_read_only_readiness_gate_observed_after_transition",
            _safe_int(
                real_read_only_approval_transition_to_statuses.get("approved"), 0
            )
            == 0
            or _safe_int(
                real_read_only_readiness_gate_statuses.get("ready_blocked"), 0
            )
            > 0,
            {
                "approved_transitions": _safe_int(
                    real_read_only_approval_transition_to_statuses.get("approved"),
                    0,
                ),
                "readiness_gates": _safe_int(
                    real_read_only_readiness_gate_statuses.get("ready_blocked"), 0
                ),
            },
        ),
        _check(
            "real_read_only_readiness_gate_links_to_transition",
            _safe_int(
                real_read_only_readiness_gate_statuses.get("ready_blocked"), 0
            )
            == 0
            or _safe_int(
                trail_summary.get("real_read_only_readiness_gate_orphans"), 0
            )
            == 0,
            {
                "readiness_gates": _safe_int(
                    real_read_only_readiness_gate_statuses.get("ready_blocked"), 0
                ),
                "orphans": _safe_int(
                    trail_summary.get("real_read_only_readiness_gate_orphans"), 0
                ),
            },
        ),
        _check(
            "real_read_only_readiness_gate_is_ready_blocked",
            _safe_int(
                real_read_only_readiness_gate_statuses.get("ready_blocked"), 0
            )
            == 1,
            _safe_int(
                real_read_only_readiness_gate_statuses.get("ready_blocked"), 0
            ),
        ),
        _check(
            "real_read_only_readiness_gate_satisfied",
            _safe_int(real_read_only_readiness_gate_satisfied.get("true"), 0) == 1,
            _safe_int(real_read_only_readiness_gate_satisfied.get("true"), 0),
        ),
        _check(
            "real_read_only_readiness_gate_ready_for_guarded_execution",
            _safe_int(real_read_only_readiness_gate_ready.get("true"), 0) == 1,
            _safe_int(real_read_only_readiness_gate_ready.get("true"), 0),
        ),
        _check(
            "real_read_only_readiness_gate_does_not_enable_read_only_execution",
            _safe_int(
                real_read_only_readiness_gate_read_only_execution_enabled.get(
                    "true"
                ),
                0,
            )
            == 0,
            _safe_int(
                real_read_only_readiness_gate_read_only_execution_enabled.get(
                    "true"
                ),
                0,
            ),
        ),
        _check(
            "real_read_only_readiness_gate_does_not_enable_real_execution",
            _safe_int(
                real_read_only_readiness_gate_real_execution_enabled.get("true"),
                0,
            )
            == 0,
            _safe_int(
                real_read_only_readiness_gate_real_execution_enabled.get("true"),
                0,
            ),
        ),
        _check(
            "real_read_only_readiness_gate_does_not_enable_subprocess",
            _safe_int(
                real_read_only_readiness_gate_subprocess_enabled.get("true"), 0
            )
            == 0,
            _safe_int(
                real_read_only_readiness_gate_subprocess_enabled.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_readiness_gate_does_not_invoke_subprocess",
            _safe_int(
                real_read_only_readiness_gate_subprocess_invoked.get("true"), 0
            )
            == 0,
            _safe_int(
                real_read_only_readiness_gate_subprocess_invoked.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_readiness_gate_does_not_execute",
            _safe_int(
                real_read_only_readiness_gate_execution_performed.get("true"), 0
            )
            == 0,
            _safe_int(
                real_read_only_readiness_gate_execution_performed.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_readiness_gate_did_not_execute_rendered_command",
            _safe_int(
                real_read_only_readiness_gate_rendered_command_executed.get(
                    "true"
                ),
                0,
            )
            == 0,
            _safe_int(
                real_read_only_readiness_gate_rendered_command_executed.get(
                    "true"
                ),
                0,
            ),
        ),
        _check(
            "real_read_only_readiness_gate_did_not_execute_dry_run_command",
            _safe_int(
                real_read_only_readiness_gate_dry_run_command_executed.get(
                    "true"
                ),
                0,
            )
            == 0,
            _safe_int(
                real_read_only_readiness_gate_dry_run_command_executed.get(
                    "true"
                ),
                0,
            ),
        ),
        _check(
            "real_read_only_execution_result_observed_after_readiness_gate",
            _safe_int(real_read_only_readiness_gate_ready.get("true"), 0) == 0
            or (
                _safe_int(real_read_only_execution_result_statuses.get("executed"), 0)
                + _safe_int(real_read_only_execution_result_statuses.get("failed"), 0)
                + _safe_int(real_read_only_execution_result_statuses.get("rejected"), 0)
            )
            > 0,
            {
                "readiness_gates_ready": _safe_int(
                    real_read_only_readiness_gate_ready.get("true"), 0
                ),
                "execution_results": (
                    _safe_int(
                        real_read_only_execution_result_statuses.get("executed"), 0
                    )
                    + _safe_int(
                        real_read_only_execution_result_statuses.get("failed"), 0
                    )
                    + _safe_int(
                        real_read_only_execution_result_statuses.get("rejected"), 0
                    )
                ),
            },
        ),
        _check(
            "real_read_only_execution_result_links_to_readiness_gate",
            (
                _safe_int(real_read_only_execution_result_statuses.get("executed"), 0)
                + _safe_int(real_read_only_execution_result_statuses.get("failed"), 0)
                + _safe_int(real_read_only_execution_result_statuses.get("rejected"), 0)
            )
            == 0
            or _safe_int(
                trail_summary.get("real_read_only_execution_result_orphans"), 0
            )
            == 0,
            _safe_int(trail_summary.get("real_read_only_execution_result_orphans"), 0),
        ),
        _check(
            "real_read_only_execution_result_authorized",
            _safe_int(real_read_only_execution_result_operator_authorized.get("true"), 0)
            == 1,
            _safe_int(real_read_only_execution_result_operator_authorized.get("true"), 0),
        ),
        _check(
            "real_read_only_execution_result_guarded_flag_observed",
            _safe_int(real_read_only_execution_result_allow_guarded.get("true"), 0)
            == 1,
            _safe_int(real_read_only_execution_result_allow_guarded.get("true"), 0),
        ),
        _check(
            "real_read_only_execution_result_validation_reasons_empty",
            _safe_int(
                real_read_only_execution_result_validation_reasons_empty.get("true"), 0
            )
            == 1,
            _safe_int(
                real_read_only_execution_result_validation_reasons_empty.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_execution_result_did_not_enable_real_execution",
            _safe_int(
                real_read_only_execution_result_real_execution_enabled.get("true"), 0
            )
            == 0,
            _safe_int(
                real_read_only_execution_result_real_execution_enabled.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_execution_result_enabled_read_only_execution",
            _safe_int(
                real_read_only_execution_result_read_only_execution_enabled.get("true"),
                0,
            )
            == 1,
            _safe_int(
                real_read_only_execution_result_read_only_execution_enabled.get("true"),
                0,
            ),
        ),
        _check(
            "real_read_only_execution_result_invoked_subprocess",
            _safe_int(
                real_read_only_execution_result_subprocess_invoked.get("true"), 0
            )
            == 1,
            _safe_int(
                real_read_only_execution_result_subprocess_invoked.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_execution_result_performed_execution",
            _safe_int(
                real_read_only_execution_result_execution_performed.get("true"), 0
            )
            == 1,
            _safe_int(
                real_read_only_execution_result_execution_performed.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_execution_result_executed_read_only_command",
            _safe_int(
                real_read_only_execution_result_read_only_command_executed.get("true"),
                0,
            )
            == 1,
            _safe_int(
                real_read_only_execution_result_read_only_command_executed.get("true"),
                0,
            ),
        ),
        _check(
            "real_read_only_execution_result_executed_rendered_command",
            _safe_int(
                real_read_only_execution_result_rendered_command_executed.get("true"),
                0,
            )
            == 1,
            _safe_int(
                real_read_only_execution_result_rendered_command_executed.get("true"),
                0,
            ),
        ),
        _check(
            "real_read_only_execution_result_executed_dry_run_command",
            _safe_int(
                real_read_only_execution_result_dry_run_command_executed.get("true"), 0
            )
            == 1,
            _safe_int(
                real_read_only_execution_result_dry_run_command_executed.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_feedback_observed_after_execution_result",
            _safe_int(real_read_only_execution_result_statuses.get("failed"), 0) == 0
            or _safe_int(real_read_only_feedback_statuses.get("actionable"), 0) > 0,
            {
                "failed_results": _safe_int(
                    real_read_only_execution_result_statuses.get("failed"), 0
                ),
                "actionable_feedback": _safe_int(
                    real_read_only_feedback_statuses.get("actionable"), 0
                ),
            },
        ),
        _check(
            "real_read_only_feedback_links_to_execution_result",
            _safe_int(real_read_only_feedback_statuses.get("actionable"), 0) == 0
            or _safe_int(trail_summary.get("real_read_only_feedback_orphans"), 0) == 0,
            _safe_int(trail_summary.get("real_read_only_feedback_orphans"), 0),
        ),
        _check(
            "real_read_only_feedback_is_actionable_for_failed_result",
            _safe_int(real_read_only_feedback_source_statuses.get("failed"), 0) == 0
            or _safe_int(real_read_only_feedback_statuses.get("actionable"), 0) == 1,
            {
                "source_failed": _safe_int(
                    real_read_only_feedback_source_statuses.get("failed"), 0
                ),
                "actionable": _safe_int(
                    real_read_only_feedback_statuses.get("actionable"), 0
                ),
            },
        ),
        _check(
            "real_read_only_feedback_next_action_observed",
            _safe_int(
                real_read_only_feedback_next_actions.get(
                    "investigate_failed_read_only_evidence_check"
                ),
                0,
            )
            == 1,
            _safe_int(
                real_read_only_feedback_next_actions.get(
                    "investigate_failed_read_only_evidence_check"
                ),
                0,
            ),
        ),
        _check(
            "real_read_only_feedback_observed_execution",
            _safe_int(real_read_only_feedback_execution_observed.get("true"), 0) == 1,
            _safe_int(real_read_only_feedback_execution_observed.get("true"), 0),
        ),
        _check(
            "real_read_only_feedback_marked_failed",
            _safe_int(real_read_only_feedback_failed.get("true"), 0) == 1,
            _safe_int(real_read_only_feedback_failed.get("true"), 0),
        ),
        _check(
            "real_read_only_feedback_did_not_enable_real_execution",
            _safe_int(real_read_only_feedback_real_execution_enabled.get("true"), 0)
            == 0,
            _safe_int(real_read_only_feedback_real_execution_enabled.get("true"), 0),
        ),
        _check(
            "real_read_only_feedback_did_not_perform_feedback_execution",
            _safe_int(
                real_read_only_feedback_feedback_execution_performed.get("true"), 0
            )
            == 0,
            _safe_int(
                real_read_only_feedback_feedback_execution_performed.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_feedback_did_not_invoke_feedback_subprocess",
            _safe_int(
                real_read_only_feedback_feedback_subprocess_invoked.get("true"), 0
            )
            == 0,
            _safe_int(
                real_read_only_feedback_feedback_subprocess_invoked.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_feedback_did_not_execute",
            _safe_int(real_read_only_feedback_execution_performed.get("true"), 0)
            == 0,
            _safe_int(real_read_only_feedback_execution_performed.get("true"), 0),
        ),
        _check(
            "real_read_only_feedback_did_not_invoke_subprocess",
            _safe_int(real_read_only_feedback_subprocess_invoked.get("true"), 0)
            == 0,
            _safe_int(real_read_only_feedback_subprocess_invoked.get("true"), 0),
        ),
        _check(
            "real_read_only_repair_plan_observed_after_feedback",
            _safe_int(real_read_only_feedback_statuses.get("actionable"), 0) == 0
            or _safe_int(real_read_only_repair_plan_statuses.get("planned"), 0) > 0,
            {
                "actionable_feedback": _safe_int(
                    real_read_only_feedback_statuses.get("actionable"), 0
                ),
                "planned_repair_plans": _safe_int(
                    real_read_only_repair_plan_statuses.get("planned"), 0
                ),
            },
        ),
        _check(
            "real_read_only_repair_plan_links_to_feedback",
            _safe_int(real_read_only_repair_plan_statuses.get("planned"), 0) == 0
            or _safe_int(trail_summary.get("real_read_only_repair_plan_orphans"), 0)
            == 0,
            _safe_int(trail_summary.get("real_read_only_repair_plan_orphans"), 0),
        ),
        _check(
            "real_read_only_repair_plan_is_planned",
            _safe_int(real_read_only_repair_plan_statuses.get("planned"), 0) == 1,
            _safe_int(real_read_only_repair_plan_statuses.get("planned"), 0),
        ),
        _check(
            "real_read_only_repair_plan_source_is_actionable_feedback",
            _safe_int(
                real_read_only_repair_plan_source_feedback_statuses.get("actionable"),
                0,
            )
            == 1,
            _safe_int(
                real_read_only_repair_plan_source_feedback_statuses.get("actionable"),
                0,
            ),
        ),
        _check(
            "real_read_only_repair_plan_source_failed",
            _safe_int(real_read_only_repair_plan_source_statuses.get("failed"), 0)
            == 1,
            _safe_int(real_read_only_repair_plan_source_statuses.get("failed"), 0),
        ),
        _check(
            "real_read_only_repair_plan_next_action_observed",
            _safe_int(
                real_read_only_repair_plan_next_actions.get(
                    "review_replay_evidence_repair_plan"
                ),
                0,
            )
            == 1,
            _safe_int(
                real_read_only_repair_plan_next_actions.get(
                    "review_replay_evidence_repair_plan"
                ),
                0,
            ),
        ),
        _check(
            "real_read_only_repair_plan_requires_operator_review",
            _safe_int(
                real_read_only_repair_plan_requires_operator_review.get("true"), 0
            )
            == 1,
            _safe_int(
                real_read_only_repair_plan_requires_operator_review.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_repair_plan_has_repair_items",
            sum(_safe_int(value, 0) for value in real_read_only_repair_plan_item_counts)
            > 0,
            real_read_only_repair_plan_item_counts,
        ),
        _check(
            "real_read_only_repair_plan_did_not_enable_repair_execution",
            _safe_int(
                real_read_only_repair_plan_repair_execution_enabled.get("true"), 0
            )
            == 0,
            _safe_int(
                real_read_only_repair_plan_repair_execution_enabled.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_repair_plan_did_not_enable_real_execution",
            _safe_int(real_read_only_repair_plan_real_execution_enabled.get("true"), 0)
            == 0,
            _safe_int(real_read_only_repair_plan_real_execution_enabled.get("true"), 0),
        ),
        _check(
            "real_read_only_repair_plan_did_not_enable_subprocess",
            _safe_int(real_read_only_repair_plan_subprocess_enabled.get("true"), 0)
            == 0,
            _safe_int(real_read_only_repair_plan_subprocess_enabled.get("true"), 0),
        ),
        _check(
            "real_read_only_repair_plan_did_not_perform_repair_execution",
            _safe_int(
                real_read_only_repair_plan_repair_execution_performed.get("true"), 0
            )
            == 0,
            _safe_int(
                real_read_only_repair_plan_repair_execution_performed.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_repair_plan_did_not_invoke_repair_subprocess",
            _safe_int(
                real_read_only_repair_plan_repair_subprocess_invoked.get("true"), 0
            )
            == 0,
            _safe_int(
                real_read_only_repair_plan_repair_subprocess_invoked.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_repair_plan_did_not_execute",
            _safe_int(real_read_only_repair_plan_execution_performed.get("true"), 0)
            == 0,
            _safe_int(real_read_only_repair_plan_execution_performed.get("true"), 0),
        ),
        _check(
            "real_read_only_repair_plan_did_not_invoke_subprocess",
            _safe_int(real_read_only_repair_plan_subprocess_invoked.get("true"), 0)
            == 0,
            _safe_int(real_read_only_repair_plan_subprocess_invoked.get("true"), 0),
        ),
        _check(
            "real_read_only_repair_action_bundle_observed_after_repair_plan",
            _safe_int(real_read_only_repair_plan_statuses.get("planned"), 0) == 0
            or _safe_int(real_read_only_repair_action_bundle_statuses.get("assembled"), 0)
            > 0,
            {
                "planned_repair_plans": _safe_int(
                    real_read_only_repair_plan_statuses.get("planned"), 0
                ),
                "assembled_bundles": _safe_int(
                    real_read_only_repair_action_bundle_statuses.get("assembled"), 0
                ),
            },
        ),
        _check(
            "real_read_only_repair_action_bundle_links_to_repair_plan",
            _safe_int(real_read_only_repair_action_bundle_statuses.get("assembled"), 0)
            == 0
            or _safe_int(
                trail_summary.get("real_read_only_repair_action_bundle_orphans"), 0
            )
            == 0,
            _safe_int(
                trail_summary.get("real_read_only_repair_action_bundle_orphans"), 0
            ),
        ),
        _check(
            "real_read_only_repair_action_bundle_is_assembled",
            _safe_int(real_read_only_repair_action_bundle_statuses.get("assembled"), 0)
            == 1,
            _safe_int(real_read_only_repair_action_bundle_statuses.get("assembled"), 0),
        ),
        _check(
            "real_read_only_repair_action_bundle_source_is_planned",
            _safe_int(
                real_read_only_repair_action_bundle_source_plan_statuses.get("planned"),
                0,
            )
            == 1,
            _safe_int(
                real_read_only_repair_action_bundle_source_plan_statuses.get("planned"),
                0,
            ),
        ),
        _check(
            "real_read_only_repair_action_bundle_next_action_observed",
            _safe_int(
                real_read_only_repair_action_bundle_next_actions.get(
                    "review_repair_action_bundle"
                ),
                0,
            )
            == 1,
            _safe_int(
                real_read_only_repair_action_bundle_next_actions.get(
                    "review_repair_action_bundle"
                ),
                0,
            ),
        ),
        _check(
            "real_read_only_repair_action_bundle_has_bundle_items",
            any(
                _safe_int(key, 0) > 0 and _safe_int(value, 0) > 0
                for key, value in real_read_only_repair_action_bundle_item_counts.items()
            ),
            real_read_only_repair_action_bundle_item_counts,
        ),
        _check(
            "real_read_only_repair_action_bundle_requires_operator_review",
            _safe_int(
                real_read_only_repair_action_bundle_requires_operator_review.get("true"),
                0,
            )
            == 1,
            _safe_int(
                real_read_only_repair_action_bundle_requires_operator_review.get("true"),
                0,
            ),
        ),
        _check(
            "real_read_only_repair_action_bundle_not_reviewed_yet",
            _safe_int(real_read_only_repair_action_bundle_reviewed.get("true"), 0)
            == 0,
            _safe_int(real_read_only_repair_action_bundle_reviewed.get("true"), 0),
        ),
        _check(
            "real_read_only_repair_action_bundle_did_not_enable_bundle_execution",
            _safe_int(
                real_read_only_repair_action_bundle_bundle_execution_enabled.get("true"),
                0,
            )
            == 0,
            _safe_int(
                real_read_only_repair_action_bundle_bundle_execution_enabled.get("true"),
                0,
            ),
        ),
        _check(
            "real_read_only_repair_action_bundle_did_not_enable_repair_execution",
            _safe_int(
                real_read_only_repair_action_bundle_repair_execution_enabled.get("true"),
                0,
            )
            == 0,
            _safe_int(
                real_read_only_repair_action_bundle_repair_execution_enabled.get("true"),
                0,
            ),
        ),
        _check(
            "real_read_only_repair_action_bundle_did_not_enable_real_execution",
            _safe_int(
                real_read_only_repair_action_bundle_real_execution_enabled.get("true"),
                0,
            )
            == 0,
            _safe_int(
                real_read_only_repair_action_bundle_real_execution_enabled.get("true"),
                0,
            ),
        ),
        _check(
            "real_read_only_repair_action_bundle_did_not_enable_subprocess",
            _safe_int(
                real_read_only_repair_action_bundle_subprocess_enabled.get("true"), 0
            )
            == 0,
            _safe_int(
                real_read_only_repair_action_bundle_subprocess_enabled.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_repair_action_bundle_did_not_perform_bundle_execution",
            _safe_int(
                real_read_only_repair_action_bundle_bundle_execution_performed.get("true"),
                0,
            )
            == 0,
            _safe_int(
                real_read_only_repair_action_bundle_bundle_execution_performed.get("true"),
                0,
            ),
        ),
        _check(
            "real_read_only_repair_action_bundle_did_not_invoke_bundle_subprocess",
            _safe_int(
                real_read_only_repair_action_bundle_bundle_subprocess_invoked.get("true"),
                0,
            )
            == 0,
            _safe_int(
                real_read_only_repair_action_bundle_bundle_subprocess_invoked.get("true"),
                0,
            ),
        ),
        _check(
            "real_read_only_repair_action_bundle_did_not_execute",
            _safe_int(
                real_read_only_repair_action_bundle_execution_performed.get("true"), 0
            )
            == 0,
            _safe_int(
                real_read_only_repair_action_bundle_execution_performed.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_repair_action_bundle_did_not_invoke_subprocess",
            _safe_int(
                real_read_only_repair_action_bundle_subprocess_invoked.get("true"), 0
            )
            == 0,
            _safe_int(
                real_read_only_repair_action_bundle_subprocess_invoked.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_repair_action_bundle_review_observed_after_bundle",
            _safe_int(real_read_only_repair_action_bundle_statuses.get("assembled"), 0)
            == 0
            or _safe_int(
                real_read_only_repair_action_bundle_review_statuses.get("approved"),
                0,
            )
            > 0,
            {
                "assembled_bundles": _safe_int(
                    real_read_only_repair_action_bundle_statuses.get("assembled"), 0
                ),
                "approved_reviews": _safe_int(
                    real_read_only_repair_action_bundle_review_statuses.get("approved"),
                    0,
                ),
            },
        ),
        _check(
            "real_read_only_repair_action_bundle_review_links_to_bundle",
            _safe_int(
                real_read_only_repair_action_bundle_review_statuses.get("approved"), 0
            )
            == 0
            or _safe_int(
                trail_summary.get(
                    "real_read_only_repair_action_bundle_review_orphans"
                ),
                0,
            )
            == 0,
            _safe_int(
                trail_summary.get("real_read_only_repair_action_bundle_review_orphans"),
                0,
            ),
        ),
        _check(
            "real_read_only_repair_action_bundle_review_is_approved",
            _safe_int(
                real_read_only_repair_action_bundle_review_statuses.get("approved"), 0
            )
            == 1,
            _safe_int(
                real_read_only_repair_action_bundle_review_statuses.get("approved"), 0
            ),
        ),
        _check(
            "real_read_only_repair_action_bundle_review_source_is_assembled",
            _safe_int(
                real_read_only_repair_action_bundle_review_source_bundle_statuses.get(
                    "assembled"
                ),
                0,
            )
            == 1,
            _safe_int(
                real_read_only_repair_action_bundle_review_source_bundle_statuses.get(
                    "assembled"
                ),
                0,
            ),
        ),
        _check(
            "real_read_only_repair_action_bundle_review_next_action_observed",
            _safe_int(
                real_read_only_repair_action_bundle_review_next_actions.get(
                    "prepare_repair_execution_approval_scaffold"
                ),
                0,
            )
            == 1,
            _safe_int(
                real_read_only_repair_action_bundle_review_next_actions.get(
                    "prepare_repair_execution_approval_scaffold"
                ),
                0,
            ),
        ),
        _check(
            "real_read_only_repair_action_bundle_review_operator_authorized",
            _safe_int(
                real_read_only_repair_action_bundle_review_operator_authorized.get(
                    "true"
                ),
                0,
            )
            == 1,
            _safe_int(
                real_read_only_repair_action_bundle_review_operator_authorized.get(
                    "true"
                ),
                0,
            ),
        ),
        _check(
            "real_read_only_repair_action_bundle_review_reviewed",
            _safe_int(
                real_read_only_repair_action_bundle_review_reviewed.get("true"), 0
            )
            == 1,
            _safe_int(
                real_read_only_repair_action_bundle_review_reviewed.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_repair_action_bundle_review_approved",
            _safe_int(
                real_read_only_repair_action_bundle_review_approved.get("true"), 0
            )
            == 1,
            _safe_int(
                real_read_only_repair_action_bundle_review_approved.get("true"), 0
            ),
        ),
        _check(
            "real_read_only_repair_action_bundle_review_did_not_enable_bundle_execution",
            _safe_int(
                real_read_only_repair_action_bundle_review_bundle_execution_enabled.get(
                    "true"
                ),
                0,
            )
            == 0,
            _safe_int(
                real_read_only_repair_action_bundle_review_bundle_execution_enabled.get(
                    "true"
                ),
                0,
            ),
        ),
        _check(
            "real_read_only_repair_action_bundle_review_did_not_enable_repair_execution",
            _safe_int(
                real_read_only_repair_action_bundle_review_repair_execution_enabled.get(
                    "true"
                ),
                0,
            )
            == 0,
            _safe_int(
                real_read_only_repair_action_bundle_review_repair_execution_enabled.get(
                    "true"
                ),
                0,
            ),
        ),
        _check(
            "real_read_only_repair_action_bundle_review_did_not_enable_real_execution",
            _safe_int(
                real_read_only_repair_action_bundle_review_real_execution_enabled.get(
                    "true"
                ),
                0,
            )
            == 0,
            _safe_int(
                real_read_only_repair_action_bundle_review_real_execution_enabled.get(
                    "true"
                ),
                0,
            ),
        ),
        _check(
            "real_read_only_repair_action_bundle_review_did_not_enable_subprocess",
            _safe_int(
                real_read_only_repair_action_bundle_review_subprocess_enabled.get(
                    "true"
                ),
                0,
            )
            == 0,
            _safe_int(
                real_read_only_repair_action_bundle_review_subprocess_enabled.get(
                    "true"
                ),
                0,
            ),
        ),
        _check(
            "real_read_only_repair_action_bundle_review_did_not_execute",
            _safe_int(
                real_read_only_repair_action_bundle_review_execution_performed.get(
                    "true"
                ),
                0,
            )
            == 0,
            _safe_int(
                real_read_only_repair_action_bundle_review_execution_performed.get(
                    "true"
                ),
                0,
            ),
        ),
        _check(
            "real_read_only_repair_action_bundle_review_did_not_invoke_subprocess",
            _safe_int(
                real_read_only_repair_action_bundle_review_subprocess_invoked.get(
                    "true"
                ),
                0,
            )
            == 0,
            _safe_int(
                real_read_only_repair_action_bundle_review_subprocess_invoked.get(
                    "true"
                ),
                0,
            ),
        ),
        _check(
            "real_repair_approval_observed_after_bundle_review",
            _safe_int(
                real_read_only_repair_action_bundle_review_statuses.get("approved"),
                0,
            )
            == 0
            or _safe_int(real_repair_approval_statuses.get("pending"), 0) > 0,
            {
                "approved_reviews": _safe_int(
                    real_read_only_repair_action_bundle_review_statuses.get("approved"),
                    0,
                ),
                "pending_repair_approvals": _safe_int(
                    real_repair_approval_statuses.get("pending"), 0
                ),
            },
        ),
        _check(
            "real_repair_approval_links_to_bundle_review",
            _safe_int(real_repair_approval_statuses.get("pending"), 0) == 0
            or _safe_int(trail_summary.get("real_repair_approval_orphans"), 0) == 0,
            _safe_int(trail_summary.get("real_repair_approval_orphans"), 0),
        ),
        _check(
            "real_repair_approval_is_pending",
            _safe_int(real_repair_approval_statuses.get("pending"), 0) == 1,
            _safe_int(real_repair_approval_statuses.get("pending"), 0),
        ),
        _check(
            "real_repair_approval_source_review_is_approved",
            _safe_int(real_repair_approval_source_review_statuses.get("approved"), 0)
            == 1,
            _safe_int(real_repair_approval_source_review_statuses.get("approved"), 0),
        ),
        _check(
            "real_repair_approval_next_action_observed",
            _safe_int(
                real_repair_approval_next_actions.get(
                    "await_repair_execution_approval"
                ),
                0,
            )
            == 1,
            _safe_int(
                real_repair_approval_next_actions.get(
                    "await_repair_execution_approval"
                ),
                0,
            ),
        ),
        _check(
            "real_repair_approval_operator_authorized",
            _safe_int(real_repair_approval_operator_authorized.get("true"), 0) == 1,
            _safe_int(real_repair_approval_operator_authorized.get("true"), 0),
        ),
        _check(
            "real_repair_approval_required",
            _safe_int(real_repair_approval_required.get("true"), 0) == 1,
            _safe_int(real_repair_approval_required.get("true"), 0),
        ),
        _check(
            "real_repair_approval_not_approved_yet",
            _safe_int(real_repair_approval_approved.get("true"), 0) == 0,
            _safe_int(real_repair_approval_approved.get("true"), 0),
        ),
        _check(
            "real_repair_approval_did_not_enable_repair_execution",
            _safe_int(real_repair_approval_repair_execution_enabled.get("true"), 0)
            == 0,
            _safe_int(real_repair_approval_repair_execution_enabled.get("true"), 0),
        ),
        _check(
            "real_repair_approval_did_not_enable_real_execution",
            _safe_int(real_repair_approval_real_execution_enabled.get("true"), 0)
            == 0,
            _safe_int(real_repair_approval_real_execution_enabled.get("true"), 0),
        ),
        _check(
            "real_repair_approval_did_not_enable_subprocess",
            _safe_int(real_repair_approval_subprocess_enabled.get("true"), 0) == 0,
            _safe_int(real_repair_approval_subprocess_enabled.get("true"), 0),
        ),
        _check(
            "real_repair_approval_did_not_perform_repair_execution",
            _safe_int(real_repair_approval_repair_execution_performed.get("true"), 0)
            == 0,
            _safe_int(real_repair_approval_repair_execution_performed.get("true"), 0),
        ),
        _check(
            "real_repair_approval_did_not_invoke_repair_subprocess",
            _safe_int(real_repair_approval_repair_subprocess_invoked.get("true"), 0)
            == 0,
            _safe_int(real_repair_approval_repair_subprocess_invoked.get("true"), 0),
        ),
        _check(
            "real_repair_approval_did_not_execute",
            _safe_int(real_repair_approval_execution_performed.get("true"), 0) == 0,
            _safe_int(real_repair_approval_execution_performed.get("true"), 0),
        ),
        _check(
            "real_repair_approval_did_not_invoke_subprocess",
            _safe_int(real_repair_approval_subprocess_invoked.get("true"), 0) == 0,
            _safe_int(real_repair_approval_subprocess_invoked.get("true"), 0),
        ),
    ]

    operator_authorized_count = _safe_int(operator_authorized.get("true"))
    if require_operator_authorized:
        checks.append(
            _check(
                "operator_authorized",
                operator_authorized_count > 0,
                operator_authorized_count,
            )
        )
    else:
        checks.append(
            _check(
                "operator_authorization_optional",
                True,
                operator_authorized_count,
            )
        )

    return checks


def _check(name: str, passed: bool, value: Any) -> dict[str, Any]:
    return {
        "name": name,
        "status": "passed" if passed else "failed",
        "value": value,
    }


def _safe_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def validate_controlled_execution_readiness_report_schema(
    report: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the machine-readable readiness report contract."""
    required_fields = [
        "schema_version",
        "schema_kind",
        "type",
        "status",
        "ready_for_mock_execution",
        "ready_for_real_execution",
        "blocking_reasons",
        "adapter_contract_observed",
        "adapter_subprocess_invoked",
        "adapter_real_execution_enabled",
        "adapter_payload_executed",
        "checks",
        "exit_codes",
        "adapter_contract",
        "real_adapter_supported",
        "real_adapter_runnable",
        "real_adapter_requires_explicit_pr",
        "real_execution_request_observed",
        "real_execution_request_rejected",
        "real_preflight_observed",
        "real_preflight_blocked",
        "real_approval_observed",
        "real_approval_records",
        "real_linkage_complete",
        "real_preflight_orphans",
        "real_approval_orphans",
        "real_final_gate_observed",
        "real_final_gate_blocked",
        "real_dry_run_envelope_observed",
        "real_dry_run_envelope_records",
        "real_dry_run_linkage_complete",
        "real_dry_run_envelope_orphans",
        "real_noop_result_observed",
        "real_noop_result_records",
        "real_noop_linkage_complete",
        "real_noop_result_orphans",
        "real_noop_result_stdout_marker_observed",
        "real_read_only_promotion_observed",
        "real_read_only_promotion_records",
        "real_read_only_promotion_linkage_complete",
        "real_read_only_promotion_orphans",
        "real_read_only_final_gate_observed",
        "real_read_only_final_gate_records",
        "real_read_only_final_gate_linkage_complete",
        "real_read_only_final_gate_orphans",
        "real_read_only_approval_observed",
        "real_read_only_approval_records",
        "real_read_only_approval_linkage_complete",
        "real_read_only_approval_orphans",
        "real_read_only_approval_transition_observed",
        "real_read_only_approval_transition_records",
        "real_read_only_approval_transition_linkage_complete",
        "real_read_only_approval_transition_orphans",
        "real_read_only_approval_latest_status",
        "real_read_only_readiness_gate_observed",
        "real_read_only_readiness_gate_records",
        "real_read_only_readiness_gate_linkage_complete",
        "real_read_only_readiness_gate_orphans",
        "real_read_only_execution_result_observed",
        "real_read_only_execution_result_records",
        "real_read_only_execution_result_linkage_complete",
        "real_read_only_execution_result_orphans",
        "real_read_only_feedback_observed",
        "real_read_only_feedback_records",
        "real_read_only_feedback_linkage_complete",
        "real_read_only_feedback_orphans",
        "real_read_only_repair_plan_observed",
        "real_read_only_repair_plan_records",
        "real_read_only_repair_plan_linkage_complete",
        "real_read_only_repair_plan_orphans",
        "real_read_only_repair_action_bundle_observed",
        "real_read_only_repair_action_bundle_records",
        "real_read_only_repair_action_bundle_linkage_complete",
        "real_read_only_repair_action_bundle_orphans",
        "real_read_only_repair_action_bundle_review_observed",
        "real_read_only_repair_action_bundle_review_records",
        "real_read_only_repair_action_bundle_review_linkage_complete",
        "real_read_only_repair_action_bundle_review_orphans",
        "real_repair_approval_observed",
        "real_repair_approval_records",
        "real_repair_approval_linkage_complete",
        "real_repair_approval_orphans",
    ]

    reasons: list[str] = []

    if report.get("schema_version") != READINESS_SCHEMA_VERSION:
        reasons.append("invalid_schema_version")
    if report.get("schema_kind") != "controlled_execution_readiness":
        reasons.append("invalid_schema_kind")
    if report.get("type") != "controlled_execution_readiness_report":
        reasons.append("invalid_report_type")
    if report.get("status") not in {"passed", "failed"}:
        reasons.append("invalid_status")

    for field in required_fields:
        if field not in report:
            reasons.append(f"missing_required_field:{field}")

    if not isinstance(report.get("ready_for_mock_execution"), bool):
        reasons.append("ready_for_mock_execution_must_be_bool")
    if not isinstance(report.get("ready_for_real_execution"), bool):
        reasons.append("ready_for_real_execution_must_be_bool")
    if report.get("ready_for_real_execution") is not False:
        reasons.append("ready_for_real_execution_must_remain_false")
    if not isinstance(report.get("blocking_reasons"), list):
        reasons.append("blocking_reasons_must_be_list")
    if not isinstance(report.get("checks"), list):
        reasons.append("checks_must_be_list")
    if not isinstance(report.get("exit_codes"), Mapping):
        reasons.append("exit_codes_must_be_mapping")

    for bool_field in (
        "adapter_contract_observed",
    ):
        if not isinstance(report.get(bool_field), bool):
            reasons.append(f"{bool_field}_must_be_bool")

    for int_field in (
        "adapter_subprocess_invoked",
        "adapter_real_execution_enabled",
        "adapter_payload_executed",
    ):
        if not isinstance(report.get(int_field), int):
            reasons.append(f"{int_field}_must_be_int")

    if report.get("real_adapter_requires_explicit_pr") is not True:
        reasons.append("real_adapter_requires_explicit_pr_must_remain_true")

    if not isinstance(report.get("adapter_contract"), Mapping):
        reasons.append("adapter_contract_must_be_mapping")
    if report.get("real_adapter_supported") is not False:
        reasons.append("real_adapter_supported_must_remain_false")
    if report.get("real_adapter_runnable") is not False:
        reasons.append("real_adapter_runnable_must_remain_false")

    if not isinstance(report.get("real_execution_request_observed"), bool):
        reasons.append("real_execution_request_observed_must_be_bool")
    if not isinstance(report.get("real_execution_request_rejected"), int):
        reasons.append("real_execution_request_rejected_must_be_int")

    if not isinstance(report.get("real_preflight_observed"), bool):
        reasons.append("real_preflight_observed_must_be_bool")
    if not isinstance(report.get("real_preflight_blocked"), int):
        reasons.append("real_preflight_blocked_must_be_int")

    if not isinstance(report.get("real_approval_observed"), bool):
        reasons.append("real_approval_observed_must_be_bool")
    if not isinstance(report.get("real_approval_records"), int):
        reasons.append("real_approval_records_must_be_int")

    if not isinstance(report.get("real_linkage_complete"), bool):
        reasons.append("real_linkage_complete_must_be_bool")
    if not isinstance(report.get("real_preflight_orphans"), int):
        reasons.append("real_preflight_orphans_must_be_int")
    if not isinstance(report.get("real_approval_orphans"), int):
        reasons.append("real_approval_orphans_must_be_int")

    if not isinstance(report.get("real_approval_transition_observed"), bool):
        reasons.append("real_approval_transition_observed_must_be_bool")
    if not isinstance(report.get("real_approval_transition_records"), int):
        reasons.append("real_approval_transition_records_must_be_int")
    if str(report.get("real_approval_latest_status") or "") not in {
        "unknown",
        "pending",
        "approved",
        "rejected",
    }:
        reasons.append("invalid_real_approval_latest_status")
    
    if not isinstance(report.get("real_final_gate_observed"), bool):
        reasons.append("real_final_gate_observed_must_be_bool")
    if not isinstance(report.get("real_final_gate_blocked"), int):
        reasons.append("real_final_gate_blocked_must_be_int")
    
    if not isinstance(report.get("real_dry_run_envelope_observed"), bool):
        reasons.append("real_dry_run_envelope_observed_must_be_bool")
    if not isinstance(report.get("real_dry_run_envelope_records"), int):
        reasons.append("real_dry_run_envelope_records_must_be_int")

    if not isinstance(report.get("real_dry_run_linkage_complete"), bool):
        reasons.append("real_dry_run_linkage_complete_must_be_bool")
    if not isinstance(report.get("real_dry_run_envelope_orphans"), int):
        reasons.append("real_dry_run_envelope_orphans_must_be_int")
    
    if not isinstance(report.get("real_noop_result_observed"), bool):
        reasons.append("real_noop_result_observed_must_be_bool")
    if not isinstance(report.get("real_noop_result_records"), int):
        reasons.append("real_noop_result_records_must_be_int")

    if not isinstance(report.get("real_noop_linkage_complete"), bool):
        reasons.append("real_noop_linkage_complete_must_be_bool")
    if not isinstance(report.get("real_noop_result_orphans"), int):
        reasons.append("real_noop_result_orphans_must_be_int")
    if not isinstance(report.get("real_noop_result_stdout_marker_observed"), int):
        reasons.append("real_noop_result_stdout_marker_observed_must_be_int")

    if not isinstance(report.get("real_read_only_promotion_observed"), bool):
        reasons.append("real_read_only_promotion_observed_must_be_bool")
    if not isinstance(report.get("real_read_only_promotion_records"), int):
        reasons.append("real_read_only_promotion_records_must_be_int")
    if not isinstance(report.get("real_read_only_promotion_linkage_complete"), bool):
        reasons.append("real_read_only_promotion_linkage_complete_must_be_bool")
    if not isinstance(report.get("real_read_only_promotion_orphans"), int):
        reasons.append("real_read_only_promotion_orphans_must_be_int")

    if not isinstance(report.get("real_read_only_final_gate_observed"), bool):
        reasons.append("real_read_only_final_gate_observed_must_be_bool")
    if not isinstance(report.get("real_read_only_final_gate_records"), int):
        reasons.append("real_read_only_final_gate_records_must_be_int")
    if not isinstance(report.get("real_read_only_final_gate_linkage_complete"), bool):
        reasons.append("real_read_only_final_gate_linkage_complete_must_be_bool")
    if not isinstance(report.get("real_read_only_final_gate_orphans"), int):
        reasons.append("real_read_only_final_gate_orphans_must_be_int")

    if not isinstance(report.get("real_read_only_approval_observed"), bool):
        reasons.append("real_read_only_approval_observed_must_be_bool")
    if not isinstance(report.get("real_read_only_approval_records"), int):
        reasons.append("real_read_only_approval_records_must_be_int")
    if not isinstance(report.get("real_read_only_approval_linkage_complete"), bool):
        reasons.append("real_read_only_approval_linkage_complete_must_be_bool")
    if not isinstance(report.get("real_read_only_approval_orphans"), int):
        reasons.append("real_read_only_approval_orphans_must_be_int")

    if not isinstance(report.get("real_read_only_approval_transition_observed"), bool):
        reasons.append("real_read_only_approval_transition_observed_must_be_bool")
    if not isinstance(report.get("real_read_only_approval_transition_records"), int):
        reasons.append("real_read_only_approval_transition_records_must_be_int")
    if not isinstance(
        report.get("real_read_only_approval_transition_linkage_complete"), bool
    ):
        reasons.append(
            "real_read_only_approval_transition_linkage_complete_must_be_bool"
        )
    if not isinstance(report.get("real_read_only_approval_transition_orphans"), int):
        reasons.append("real_read_only_approval_transition_orphans_must_be_int")
    if not isinstance(report.get("real_read_only_approval_latest_status"), str):
        reasons.append("real_read_only_approval_latest_status_must_be_str")
    
    if not isinstance(report.get("real_read_only_readiness_gate_observed"), bool):
        reasons.append("real_read_only_readiness_gate_observed_must_be_bool")
    if not isinstance(report.get("real_read_only_readiness_gate_records"), int):
        reasons.append("real_read_only_readiness_gate_records_must_be_int")
    if not isinstance(
        report.get("real_read_only_readiness_gate_linkage_complete"), bool
    ):
        reasons.append("real_read_only_readiness_gate_linkage_complete_must_be_bool")
    if not isinstance(report.get("real_read_only_readiness_gate_orphans"), int):
        reasons.append("real_read_only_readiness_gate_orphans_must_be_int")
    
    if not isinstance(report.get("real_read_only_execution_result_observed"), bool):
        reasons.append("real_read_only_execution_result_observed_must_be_bool")
    if not isinstance(report.get("real_read_only_execution_result_records"), int):
        reasons.append("real_read_only_execution_result_records_must_be_int")
    if not isinstance(
        report.get("real_read_only_execution_result_linkage_complete"), bool
    ):
        reasons.append("real_read_only_execution_result_linkage_complete_must_be_bool")
    if not isinstance(report.get("real_read_only_execution_result_orphans"), int):
        reasons.append("real_read_only_execution_result_orphans_must_be_int")

    if not isinstance(report.get("real_read_only_feedback_observed"), bool):
        reasons.append("real_read_only_feedback_observed_must_be_bool")
    if not isinstance(report.get("real_read_only_feedback_records"), int):
        reasons.append("real_read_only_feedback_records_must_be_int")
    if not isinstance(report.get("real_read_only_feedback_linkage_complete"), bool):
        reasons.append("real_read_only_feedback_linkage_complete_must_be_bool")
    if not isinstance(report.get("real_read_only_feedback_orphans"), int):
        reasons.append("real_read_only_feedback_orphans_must_be_int")

    if not isinstance(report.get("real_read_only_repair_plan_observed"), bool):
        reasons.append("real_read_only_repair_plan_observed_must_be_bool")
    if not isinstance(report.get("real_read_only_repair_plan_records"), int):
        reasons.append("real_read_only_repair_plan_records_must_be_int")
    if not isinstance(report.get("real_read_only_repair_plan_linkage_complete"), bool):
        reasons.append("real_read_only_repair_plan_linkage_complete_must_be_bool")
    if not isinstance(report.get("real_read_only_repair_plan_orphans"), int):
        reasons.append("real_read_only_repair_plan_orphans_must_be_int")
    
    if not isinstance(report.get("real_read_only_repair_action_bundle_observed"), bool):
        reasons.append("real_read_only_repair_action_bundle_observed_must_be_bool")
    if not isinstance(report.get("real_read_only_repair_action_bundle_records"), int):
        reasons.append("real_read_only_repair_action_bundle_records_must_be_int")
    if not isinstance(
        report.get("real_read_only_repair_action_bundle_linkage_complete"), bool
    ):
        reasons.append("real_read_only_repair_action_bundle_linkage_complete_must_be_bool")
    if not isinstance(report.get("real_read_only_repair_action_bundle_orphans"), int):
        reasons.append("real_read_only_repair_action_bundle_orphans_must_be_int")
    
    if not isinstance(
        report.get("real_read_only_repair_action_bundle_review_observed"), bool
    ):
        reasons.append("real_read_only_repair_action_bundle_review_observed_must_be_bool")
    if not isinstance(
        report.get("real_read_only_repair_action_bundle_review_records"), int
    ):
        reasons.append("real_read_only_repair_action_bundle_review_records_must_be_int")
    if not isinstance(
        report.get("real_read_only_repair_action_bundle_review_linkage_complete"), bool
    ):
        reasons.append(
            "real_read_only_repair_action_bundle_review_linkage_complete_must_be_bool"
        )
    if not isinstance(
        report.get("real_read_only_repair_action_bundle_review_orphans"), int
    ):
        reasons.append("real_read_only_repair_action_bundle_review_orphans_must_be_int")
    
    if not isinstance(report.get("real_repair_approval_observed"), bool):
        reasons.append("real_repair_approval_observed_must_be_bool")
    if not isinstance(report.get("real_repair_approval_records"), int):
        reasons.append("real_repair_approval_records_must_be_int")
    if not isinstance(report.get("real_repair_approval_linkage_complete"), bool):
        reasons.append("real_repair_approval_linkage_complete_must_be_bool")
    if not isinstance(report.get("real_repair_approval_orphans"), int):
        reasons.append("real_repair_approval_orphans_must_be_int")

    return {
        "type": "controlled_execution_readiness_schema_validation",
        "valid": not reasons,
        "schema_version": report.get("schema_version"),
        "schema_kind": report.get("schema_kind"),
        "reasons": reasons,
    }


def _exit_code_for_result(result: Mapping[str, Any]) -> int:
    return 0 if result.get("status") == "passed" else 1


def _format_result(result: Mapping[str, Any]) -> str:
    failed = result.get("blocking_reasons")
    blocking_reasons = failed if isinstance(failed, list) and failed else ["none"]

    return (
        "Controlled execution readiness: "
        f"status={result.get('status')} "
        f"schema_version={result.get('schema_version')} "
        f"ready_for_mock_execution="
        f"{str(bool(result.get('ready_for_mock_execution'))).lower()} "
        f"ready_for_real_execution="
        f"{str(bool(result.get('ready_for_real_execution'))).lower()} "
        f"require_operator_authorized="
        f"{str(bool(result.get('require_operator_authorized'))).lower()} "
        f"blocking_reasons={','.join(str(item) for item in blocking_reasons)} "
        f"mock_execution_observed="
        f"{str(bool(result.get('mock_execution_observed'))).lower()} "
        f"mock_execution_performed={result.get('mock_execution_performed', 0)} "
        f"mock_subprocess_invoked={result.get('mock_subprocess_invoked', 0)} "
        f"mock_execution_summary_observed={str(bool(result.get('mock_execution_summary_observed'))).lower()} "
        f"mock_execution_summary_performed={result.get('mock_execution_summary_performed', 0)} "
        f"mock_summary_subprocess_invoked={result.get('mock_summary_subprocess_invoked', 0)} "
        f"adapter_contract_observed="
        f"{str(bool(result.get('adapter_contract_observed'))).lower()} "
        f"adapter_mock={result.get('adapter_mock', 0)} "
        f"adapter_mode_mock={result.get('adapter_mode_mock', 0)} "
        f"adapter_result_mock_executed={result.get('adapter_result_mock_executed', 0)} "
        f"adapter_subprocess_invoked={result.get('adapter_subprocess_invoked', 0)} "
        f"adapter_real_execution_enabled={result.get('adapter_real_execution_enabled', 0)} "
        f"adapter_payload_executed={result.get('adapter_payload_executed', 0)} "
        f"real_adapter_supported="
        f"{str(bool(result.get('real_adapter_supported'))).lower()} "
        f"real_adapter_runnable="
        f"{str(bool(result.get('real_adapter_runnable'))).lower()} "
        f"real_adapter_requires_explicit_pr="
        f"{str(bool(result.get('real_adapter_requires_explicit_pr'))).lower()} "
        f"real_execution_request_observed="
        f"{str(bool(result.get('real_execution_request_observed'))).lower()} "
        f"real_execution_request_rejected={result.get('real_execution_request_rejected', 0)} "
        f"real_execution_requested={result.get('real_execution_requested', 0)} "
        f"real_execution_performed={result.get('real_execution_performed', 0)} "
        f"real_execution_supported_count={result.get('real_execution_supported_count', 0)} "
        f"subprocess_invoked_count={result.get('subprocess_invoked_count', 0)} "
        f"real_preflight_observed={str(bool(result.get('real_preflight_observed'))).lower()} "
        f"real_preflight_blocked={result.get('real_preflight_blocked', 0)} "
        f"real_preflight_would_execute={result.get('real_preflight_would_execute', 0)} "
        f"real_preflight_execution_performed={result.get('real_preflight_execution_performed', 0)} "
        f"real_preflight_subprocess_invoked={result.get('real_preflight_subprocess_invoked', 0)} "
        f"real_approval_observed={str(bool(result.get('real_approval_observed'))).lower()} "
        f"real_approval_records={result.get('real_approval_records', 0)} "
        f"real_approval_enabled={result.get('real_approval_enabled', 0)} "
        f"real_approval_subprocess_enabled={result.get('real_approval_subprocess_enabled', 0)} "
        f"real_approval_execution_performed={result.get('real_approval_execution_performed', 0)} "
        f"real_approval_subprocess_invoked={result.get('real_approval_subprocess_invoked', 0)} "
        f"real_linkage_complete={str(bool(result.get('real_linkage_complete'))).lower()} "
        f"real_preflight_orphans={result.get('real_preflight_orphans', 0)} "
        f"real_approval_orphans={result.get('real_approval_orphans', 0)} "
        f"real_approval_transition_observed={str(bool(result.get('real_approval_transition_observed'))).lower()} "
        f"real_approval_transition_records={result.get('real_approval_transition_records', 0)} "
        f"real_approval_latest_status={result.get('real_approval_latest_status', 'unknown')} "
        f"real_approval_transition_enabled={result.get('real_approval_transition_enabled', 0)} "
        f"real_approval_transition_subprocess_enabled={result.get('real_approval_transition_subprocess_enabled', 0)} "
        f"real_approval_transition_execution_performed={result.get('real_approval_transition_execution_performed', 0)} "
        f"real_approval_transition_subprocess_invoked={result.get('real_approval_transition_subprocess_invoked', 0)} "
        f"real_final_gate_observed={str(bool(result.get('real_final_gate_observed'))).lower()} "
        f"real_final_gate_blocked={result.get('real_final_gate_blocked', 0)} "
        f"real_final_gate_would_execute={result.get('real_final_gate_would_execute', 0)} "
        f"real_final_gate_ready={result.get('real_final_gate_ready', 0)} "
        f"real_final_gate_real_execution_enabled={result.get('real_final_gate_real_execution_enabled', 0)} "
        f"real_final_gate_subprocess_enabled={result.get('real_final_gate_subprocess_enabled', 0)} "
        f"real_final_gate_execution_performed={result.get('real_final_gate_execution_performed', 0)} "
        f"real_final_gate_subprocess_invoked={result.get('real_final_gate_subprocess_invoked', 0)} "
        f"real_dry_run_envelope_observed={str(bool(result.get('real_dry_run_envelope_observed'))).lower()} "
        f"real_dry_run_envelope_records={result.get('real_dry_run_envelope_records', 0)} "
        f"real_dry_run_envelope_would_execute={result.get('real_dry_run_envelope_would_execute', 0)} "
        f"real_dry_run_envelope_ready={result.get('real_dry_run_envelope_ready', 0)} "
        f"real_dry_run_envelope_real_execution_enabled={result.get('real_dry_run_envelope_real_execution_enabled', 0)} "
        f"real_dry_run_envelope_subprocess_enabled={result.get('real_dry_run_envelope_subprocess_enabled', 0)} "
        f"real_dry_run_envelope_execution_performed={result.get('real_dry_run_envelope_execution_performed', 0)} "
        f"real_dry_run_envelope_subprocess_invoked={result.get('real_dry_run_envelope_subprocess_invoked', 0)} "
        f"real_dry_run_linkage_complete={str(bool(result.get('real_dry_run_linkage_complete'))).lower()} "
        f"real_dry_run_envelope_orphans={result.get('real_dry_run_envelope_orphans', 0)} "
        f"real_noop_result_observed={str(bool(result.get('real_noop_result_observed'))).lower()} "
        f"real_noop_result_records={result.get('real_noop_result_records', 0)} "
        f"real_noop_result_rendered_command_executed={result.get('real_noop_result_rendered_command_executed', 0)} "
        f"real_noop_result_dry_run_command_executed={result.get('real_noop_result_dry_run_command_executed', 0)} "
        f"real_noop_result_real_execution_enabled={result.get('real_noop_result_real_execution_enabled', 0)} "
        f"real_noop_result_subprocess_invoked={result.get('real_noop_result_subprocess_invoked', 0)} "
        f"real_noop_result_execution_performed={result.get('real_noop_result_execution_performed', 0)} "
        f"real_noop_result_exit_code_zero={result.get('real_noop_result_exit_code_zero', 0)} "
        f"real_noop_linkage_complete={str(bool(result.get('real_noop_linkage_complete'))).lower()} "
        f"real_noop_result_orphans={result.get('real_noop_result_orphans', 0)} "
        f"real_noop_result_stdout_marker_observed={result.get('real_noop_result_stdout_marker_observed', 0)} "
        f"real_read_only_promotion_observed={str(bool(result.get('real_read_only_promotion_observed'))).lower()} "
        f"real_read_only_promotion_records={result.get('real_read_only_promotion_records', 0)} "
        f"real_read_only_promotion_linkage_complete={str(bool(result.get('real_read_only_promotion_linkage_complete'))).lower()} "
        f"real_read_only_promotion_orphans={result.get('real_read_only_promotion_orphans', 0)} "
        f"real_read_only_promotion_candidate={result.get('real_read_only_promotion_candidate', 0)} "
        f"real_read_only_promotion_command_parse_valid={result.get('real_read_only_promotion_command_parse_valid', 0)} "
        f"real_read_only_promotion_stdout_marker_observed={result.get('real_read_only_promotion_stdout_marker_observed', 0)} "
        f"real_read_only_promotion_noop_exit_code_zero={result.get('real_read_only_promotion_noop_exit_code_zero', 0)} "
        f"real_read_only_promotion_rendered_command_executed={result.get('real_read_only_promotion_rendered_command_executed', 0)} "
        f"real_read_only_promotion_dry_run_command_executed={result.get('real_read_only_promotion_dry_run_command_executed', 0)} "
        f"real_read_only_promotion_real_execution_enabled={result.get('real_read_only_promotion_real_execution_enabled', 0)} "
        f"real_read_only_promotion_subprocess_invoked={result.get('real_read_only_promotion_subprocess_invoked', 0)} "
        f"real_read_only_promotion_execution_performed={result.get('real_read_only_promotion_execution_performed', 0)} "
        f"real_read_only_final_gate_observed={str(bool(result.get('real_read_only_final_gate_observed'))).lower()} "
        f"real_read_only_final_gate_records={result.get('real_read_only_final_gate_records', 0)} "
        f"real_read_only_final_gate_linkage_complete={str(bool(result.get('real_read_only_final_gate_linkage_complete'))).lower()} "
        f"real_read_only_final_gate_orphans={result.get('real_read_only_final_gate_orphans', 0)} "
        f"real_read_only_final_gate_preconditions_satisfied={result.get('real_read_only_final_gate_preconditions_satisfied', 0)} "
        f"real_read_only_final_gate_ready={result.get('real_read_only_final_gate_ready', 0)} "
        f"real_read_only_final_gate_would_execute={result.get('real_read_only_final_gate_would_execute', 0)} "
        f"real_read_only_final_gate_read_only_execution_enabled={result.get('real_read_only_final_gate_read_only_execution_enabled', 0)} "
        f"real_read_only_final_gate_real_execution_enabled={result.get('real_read_only_final_gate_real_execution_enabled', 0)} "
        f"real_read_only_final_gate_subprocess_enabled={result.get('real_read_only_final_gate_subprocess_enabled', 0)} "
        f"real_read_only_final_gate_subprocess_invoked={result.get('real_read_only_final_gate_subprocess_invoked', 0)} "
        f"real_read_only_final_gate_execution_performed={result.get('real_read_only_final_gate_execution_performed', 0)} "
        f"real_read_only_final_gate_rendered_command_executed={result.get('real_read_only_final_gate_rendered_command_executed', 0)} "
        f"real_read_only_final_gate_dry_run_command_executed={result.get('real_read_only_final_gate_dry_run_command_executed', 0)} "
        f"real_read_only_approval_observed={str(bool(result.get('real_read_only_approval_observed'))).lower()} "
        f"real_read_only_approval_records={result.get('real_read_only_approval_records', 0)} "
        f"real_read_only_approval_linkage_complete={str(bool(result.get('real_read_only_approval_linkage_complete'))).lower()} "
        f"real_read_only_approval_orphans={result.get('real_read_only_approval_orphans', 0)} "
        f"real_read_only_approval_pending={result.get('real_read_only_approval_pending', 0)} "
        f"real_read_only_approval_read_only_execution_enabled={result.get('real_read_only_approval_read_only_execution_enabled', 0)} "
        f"real_read_only_approval_real_execution_enabled={result.get('real_read_only_approval_real_execution_enabled', 0)} "
        f"real_read_only_approval_subprocess_enabled={result.get('real_read_only_approval_subprocess_enabled', 0)} "
        f"real_read_only_approval_subprocess_invoked={result.get('real_read_only_approval_subprocess_invoked', 0)} "
        f"real_read_only_approval_execution_performed={result.get('real_read_only_approval_execution_performed', 0)} "
        f"real_read_only_approval_rendered_command_executed={result.get('real_read_only_approval_rendered_command_executed', 0)} "
        f"real_read_only_approval_dry_run_command_executed={result.get('real_read_only_approval_dry_run_command_executed', 0)} "
        f"real_read_only_approval_transition_observed={str(bool(result.get('real_read_only_approval_transition_observed'))).lower()} "
        f"real_read_only_approval_transition_records={result.get('real_read_only_approval_transition_records', 0)} "
        f"real_read_only_approval_transition_linkage_complete={str(bool(result.get('real_read_only_approval_transition_linkage_complete'))).lower()} "
        f"real_read_only_approval_transition_orphans={result.get('real_read_only_approval_transition_orphans', 0)} "
        f"real_read_only_approval_latest_status={result.get('real_read_only_approval_latest_status', 'unknown')} "
        f"real_read_only_approval_transition_from_pending={result.get('real_read_only_approval_transition_from_pending', 0)} "
        f"real_read_only_approval_transition_approved={result.get('real_read_only_approval_transition_approved', 0)} "
        f"real_read_only_approval_transition_rejected={result.get('real_read_only_approval_transition_rejected', 0)} "
        f"real_read_only_approval_transition_read_only_execution_enabled={result.get('real_read_only_approval_transition_read_only_execution_enabled', 0)} "
        f"real_read_only_approval_transition_real_execution_enabled={result.get('real_read_only_approval_transition_real_execution_enabled', 0)} "
        f"real_read_only_approval_transition_subprocess_enabled={result.get('real_read_only_approval_transition_subprocess_enabled', 0)} "
        f"real_read_only_approval_transition_subprocess_invoked={result.get('real_read_only_approval_transition_subprocess_invoked', 0)} "
        f"real_read_only_approval_transition_execution_performed={result.get('real_read_only_approval_transition_execution_performed', 0)} "
        f"real_read_only_approval_transition_rendered_command_executed={result.get('real_read_only_approval_transition_rendered_command_executed', 0)} "
        f"real_read_only_approval_transition_dry_run_command_executed={result.get('real_read_only_approval_transition_dry_run_command_executed', 0)} "
        f"real_read_only_readiness_gate_observed={str(bool(result.get('real_read_only_readiness_gate_observed'))).lower()} "
        f"real_read_only_readiness_gate_records={result.get('real_read_only_readiness_gate_records', 0)} "
        f"real_read_only_readiness_gate_linkage_complete={str(bool(result.get('real_read_only_readiness_gate_linkage_complete'))).lower()} "
        f"real_read_only_readiness_gate_orphans={result.get('real_read_only_readiness_gate_orphans', 0)} "
        f"real_read_only_readiness_gate_satisfied={result.get('real_read_only_readiness_gate_satisfied', 0)} "
        f"real_read_only_readiness_gate_ready={result.get('real_read_only_readiness_gate_ready', 0)} "
        f"real_read_only_readiness_gate_read_only_execution_enabled={result.get('real_read_only_readiness_gate_read_only_execution_enabled', 0)} "
        f"real_read_only_readiness_gate_real_execution_enabled={result.get('real_read_only_readiness_gate_real_execution_enabled', 0)} "
        f"real_read_only_readiness_gate_subprocess_enabled={result.get('real_read_only_readiness_gate_subprocess_enabled', 0)} "
        f"real_read_only_readiness_gate_subprocess_invoked={result.get('real_read_only_readiness_gate_subprocess_invoked', 0)} "
        f"real_read_only_readiness_gate_execution_performed={result.get('real_read_only_readiness_gate_execution_performed', 0)} "
        f"real_read_only_readiness_gate_rendered_command_executed={result.get('real_read_only_readiness_gate_rendered_command_executed', 0)} "
        f"real_read_only_readiness_gate_dry_run_command_executed={result.get('real_read_only_readiness_gate_dry_run_command_executed', 0)} "
        f"real_read_only_execution_result_observed={str(bool(result.get('real_read_only_execution_result_observed'))).lower()} "
        f"real_read_only_execution_result_records={result.get('real_read_only_execution_result_records', 0)} "
        f"real_read_only_execution_result_failed={result.get('real_read_only_execution_result_failed', 0)} "
        f"real_read_only_execution_result_executed={result.get('real_read_only_execution_result_executed', 0)} "
        f"real_read_only_execution_result_rejected={result.get('real_read_only_execution_result_rejected', 0)} "
        f"real_read_only_execution_result_exit_code_1={result.get('real_read_only_execution_result_exit_code_1', 0)} "
        f"real_read_only_execution_result_linkage_complete={str(bool(result.get('real_read_only_execution_result_linkage_complete'))).lower()} "
        f"real_read_only_execution_result_orphans={result.get('real_read_only_execution_result_orphans', 0)} "
        f"real_read_only_execution_result_validation_reasons_empty={result.get('real_read_only_execution_result_validation_reasons_empty', 0)} "
        f"real_read_only_execution_result_operator_authorized={result.get('real_read_only_execution_result_operator_authorized', 0)} "
        f"real_read_only_execution_result_allow_guarded={result.get('real_read_only_execution_result_allow_guarded', 0)} "
        f"real_read_only_execution_result_read_only_execution_enabled={result.get('real_read_only_execution_result_read_only_execution_enabled', 0)} "
        f"real_read_only_execution_result_real_execution_enabled={result.get('real_read_only_execution_result_real_execution_enabled', 0)} "
        f"real_read_only_execution_result_subprocess_invoked={result.get('real_read_only_execution_result_subprocess_invoked', 0)} "
        f"real_read_only_execution_result_execution_performed={result.get('real_read_only_execution_result_execution_performed', 0)} "
        f"real_read_only_execution_result_read_only_command_executed={result.get('real_read_only_execution_result_read_only_command_executed', 0)} "
        f"real_read_only_execution_result_rendered_command_executed={result.get('real_read_only_execution_result_rendered_command_executed', 0)} "
        f"real_read_only_execution_result_dry_run_command_executed={result.get('real_read_only_execution_result_dry_run_command_executed', 0)} "
        f"real_read_only_feedback_observed={str(bool(result.get('real_read_only_feedback_observed'))).lower()} "
        f"real_read_only_feedback_records={result.get('real_read_only_feedback_records', 0)} "
        f"real_read_only_feedback_linkage_complete={str(bool(result.get('real_read_only_feedback_linkage_complete'))).lower()} "
        f"real_read_only_feedback_orphans={result.get('real_read_only_feedback_orphans', 0)} "
        f"real_read_only_feedback_actionable={result.get('real_read_only_feedback_actionable', 0)} "
        f"real_read_only_feedback_source_failed={result.get('real_read_only_feedback_source_failed', 0)} "
        f"real_read_only_feedback_source_exit_code_1={result.get('real_read_only_feedback_source_exit_code_1', 0)} "
        f"real_read_only_feedback_next_action_investigate={result.get('real_read_only_feedback_next_action_investigate', 0)} "
        f"real_read_only_feedback_execution_observed={result.get('real_read_only_feedback_execution_observed', 0)} "
        f"real_read_only_feedback_failed={result.get('real_read_only_feedback_failed', 0)} "
        f"real_read_only_feedback_real_execution_enabled={result.get('real_read_only_feedback_real_execution_enabled', 0)} "
        f"real_read_only_feedback_feedback_execution_performed={result.get('real_read_only_feedback_feedback_execution_performed', 0)} "
        f"real_read_only_feedback_feedback_subprocess_invoked={result.get('real_read_only_feedback_feedback_subprocess_invoked', 0)} "
        f"real_read_only_feedback_execution_performed={result.get('real_read_only_feedback_execution_performed', 0)} "
        f"real_read_only_feedback_subprocess_invoked={result.get('real_read_only_feedback_subprocess_invoked', 0)} "
        f"real_read_only_repair_plan_observed={str(bool(result.get('real_read_only_repair_plan_observed'))).lower()} "
        f"real_read_only_repair_plan_records={result.get('real_read_only_repair_plan_records', 0)} "
        f"real_read_only_repair_plan_linkage_complete={str(bool(result.get('real_read_only_repair_plan_linkage_complete'))).lower()} "
        f"real_read_only_repair_plan_orphans={result.get('real_read_only_repair_plan_orphans', 0)} "
        f"real_read_only_repair_plan_planned={result.get('real_read_only_repair_plan_planned', 0)} "
        f"real_read_only_repair_plan_source_actionable={result.get('real_read_only_repair_plan_source_actionable', 0)} "
        f"real_read_only_repair_plan_source_failed={result.get('real_read_only_repair_plan_source_failed', 0)} "
        f"real_read_only_repair_plan_source_exit_code_1={result.get('real_read_only_repair_plan_source_exit_code_1', 0)} "
        f"real_read_only_repair_plan_next_action_review={result.get('real_read_only_repair_plan_next_action_review', 0)} "
        f"real_read_only_repair_plan_requires_operator_review={result.get('real_read_only_repair_plan_requires_operator_review', 0)} "
        f"real_read_only_repair_plan_repair_execution_enabled={result.get('real_read_only_repair_plan_repair_execution_enabled', 0)} "
        f"real_read_only_repair_plan_real_execution_enabled={result.get('real_read_only_repair_plan_real_execution_enabled', 0)} "
        f"real_read_only_repair_plan_subprocess_enabled={result.get('real_read_only_repair_plan_subprocess_enabled', 0)} "
        f"real_read_only_repair_plan_repair_execution_performed={result.get('real_read_only_repair_plan_repair_execution_performed', 0)} "
        f"real_read_only_repair_plan_repair_subprocess_invoked={result.get('real_read_only_repair_plan_repair_subprocess_invoked', 0)} "
        f"real_read_only_repair_plan_execution_performed={result.get('real_read_only_repair_plan_execution_performed', 0)} "
        f"real_read_only_repair_plan_subprocess_invoked={result.get('real_read_only_repair_plan_subprocess_invoked', 0)} "
        f"real_read_only_repair_action_bundle_observed={str(bool(result.get('real_read_only_repair_action_bundle_observed'))).lower()} "
        f"real_read_only_repair_action_bundle_records={result.get('real_read_only_repair_action_bundle_records', 0)} "
        f"real_read_only_repair_action_bundle_linkage_complete={str(bool(result.get('real_read_only_repair_action_bundle_linkage_complete'))).lower()} "
        f"real_read_only_repair_action_bundle_orphans={result.get('real_read_only_repair_action_bundle_orphans', 0)} "
        f"real_read_only_repair_action_bundle_assembled={result.get('real_read_only_repair_action_bundle_assembled', 0)} "
        f"real_read_only_repair_action_bundle_source_planned={result.get('real_read_only_repair_action_bundle_source_planned', 0)} "
        f"real_read_only_repair_action_bundle_source_actionable={result.get('real_read_only_repair_action_bundle_source_actionable', 0)} "
        f"real_read_only_repair_action_bundle_source_failed={result.get('real_read_only_repair_action_bundle_source_failed', 0)} "
        f"real_read_only_repair_action_bundle_source_exit_code_1={result.get('real_read_only_repair_action_bundle_source_exit_code_1', 0)} "
        f"real_read_only_repair_action_bundle_next_action_review={result.get('real_read_only_repair_action_bundle_next_action_review', 0)} "
        f"real_read_only_repair_action_bundle_requires_operator_review={result.get('real_read_only_repair_action_bundle_requires_operator_review', 0)} "
        f"real_read_only_repair_action_bundle_reviewed={result.get('real_read_only_repair_action_bundle_reviewed', 0)} "
        f"real_read_only_repair_action_bundle_bundle_execution_enabled={result.get('real_read_only_repair_action_bundle_bundle_execution_enabled', 0)} "
        f"real_read_only_repair_action_bundle_repair_execution_enabled={result.get('real_read_only_repair_action_bundle_repair_execution_enabled', 0)} "
        f"real_read_only_repair_action_bundle_real_execution_enabled={result.get('real_read_only_repair_action_bundle_real_execution_enabled', 0)} "
        f"real_read_only_repair_action_bundle_subprocess_enabled={result.get('real_read_only_repair_action_bundle_subprocess_enabled', 0)} "
        f"real_read_only_repair_action_bundle_bundle_execution_performed={result.get('real_read_only_repair_action_bundle_bundle_execution_performed', 0)} "
        f"real_read_only_repair_action_bundle_bundle_subprocess_invoked={result.get('real_read_only_repair_action_bundle_bundle_subprocess_invoked', 0)} "
        f"real_read_only_repair_action_bundle_execution_performed={result.get('real_read_only_repair_action_bundle_execution_performed', 0)} "
        f"real_read_only_repair_action_bundle_subprocess_invoked={result.get('real_read_only_repair_action_bundle_subprocess_invoked', 0)} "
        f"real_read_only_repair_action_bundle_review_observed={str(bool(result.get('real_read_only_repair_action_bundle_review_observed'))).lower()} "
        f"real_read_only_repair_action_bundle_review_records={result.get('real_read_only_repair_action_bundle_review_records', 0)} "
        f"real_read_only_repair_action_bundle_review_linkage_complete={str(bool(result.get('real_read_only_repair_action_bundle_review_linkage_complete'))).lower()} "
        f"real_read_only_repair_action_bundle_review_orphans={result.get('real_read_only_repair_action_bundle_review_orphans', 0)} "
        f"real_read_only_repair_action_bundle_review_approved_status={result.get('real_read_only_repair_action_bundle_review_approved_status', 0)} "
        f"real_read_only_repair_action_bundle_review_source_assembled={result.get('real_read_only_repair_action_bundle_review_source_assembled', 0)} "
        f"real_read_only_repair_action_bundle_review_source_planned={result.get('real_read_only_repair_action_bundle_review_source_planned', 0)} "
        f"real_read_only_repair_action_bundle_review_source_actionable={result.get('real_read_only_repair_action_bundle_review_source_actionable', 0)} "
        f"real_read_only_repair_action_bundle_review_source_failed={result.get('real_read_only_repair_action_bundle_review_source_failed', 0)} "
        f"real_read_only_repair_action_bundle_review_source_exit_code_1={result.get('real_read_only_repair_action_bundle_review_source_exit_code_1', 0)} "
        f"real_read_only_repair_action_bundle_review_source_item_count_9={result.get('real_read_only_repair_action_bundle_review_source_item_count_9', 0)} "
        f"real_read_only_repair_action_bundle_review_next_action_prepare={result.get('real_read_only_repair_action_bundle_review_next_action_prepare', 0)} "
        f"real_read_only_repair_action_bundle_review_operator_authorized={result.get('real_read_only_repair_action_bundle_review_operator_authorized', 0)} "
        f"real_read_only_repair_action_bundle_review_reviewed={result.get('real_read_only_repair_action_bundle_review_reviewed', 0)} "
        f"real_read_only_repair_action_bundle_review_approved={result.get('real_read_only_repair_action_bundle_review_approved', 0)} "
        f"real_read_only_repair_action_bundle_review_bundle_execution_enabled={result.get('real_read_only_repair_action_bundle_review_bundle_execution_enabled', 0)} "
        f"real_read_only_repair_action_bundle_review_repair_execution_enabled={result.get('real_read_only_repair_action_bundle_review_repair_execution_enabled', 0)} "
        f"real_read_only_repair_action_bundle_review_real_execution_enabled={result.get('real_read_only_repair_action_bundle_review_real_execution_enabled', 0)} "
        f"real_read_only_repair_action_bundle_review_subprocess_enabled={result.get('real_read_only_repair_action_bundle_review_subprocess_enabled', 0)} "
        f"real_read_only_repair_action_bundle_review_bundle_execution_performed={result.get('real_read_only_repair_action_bundle_review_bundle_execution_performed', 0)} "
        f"real_read_only_repair_action_bundle_review_bundle_subprocess_invoked={result.get('real_read_only_repair_action_bundle_review_bundle_subprocess_invoked', 0)} "
        f"real_read_only_repair_action_bundle_review_execution_performed={result.get('real_read_only_repair_action_bundle_review_execution_performed', 0)} "
        f"real_read_only_repair_action_bundle_review_subprocess_invoked={result.get('real_read_only_repair_action_bundle_review_subprocess_invoked', 0)} "
        f"real_repair_approval_observed={str(bool(result.get('real_repair_approval_observed'))).lower()} "
        f"real_repair_approval_records={result.get('real_repair_approval_records', 0)} "
        f"real_repair_approval_linkage_complete={str(bool(result.get('real_repair_approval_linkage_complete'))).lower()} "
        f"real_repair_approval_orphans={result.get('real_repair_approval_orphans', 0)} "
        f"real_repair_approval_pending={result.get('real_repair_approval_pending', 0)} "
        f"real_repair_approval_source_review_approved={result.get('real_repair_approval_source_review_approved', 0)} "
        f"real_repair_approval_next_action_await={result.get('real_repair_approval_next_action_await', 0)} "
        f"real_repair_approval_operator_authorized={result.get('real_repair_approval_operator_authorized', 0)} "
        f"real_repair_approval_required={result.get('real_repair_approval_required', 0)} "
        f"real_repair_approval_approved={result.get('real_repair_approval_approved', 0)} "
        f"real_repair_approval_repair_execution_enabled={result.get('real_repair_approval_repair_execution_enabled', 0)} "
        f"real_repair_approval_real_execution_enabled={result.get('real_repair_approval_real_execution_enabled', 0)} "
        f"real_repair_approval_subprocess_enabled={result.get('real_repair_approval_subprocess_enabled', 0)} "
        f"real_repair_approval_repair_execution_performed={result.get('real_repair_approval_repair_execution_performed', 0)} "
        f"real_repair_approval_repair_subprocess_invoked={result.get('real_repair_approval_repair_subprocess_invoked', 0)} "
        f"real_repair_approval_execution_performed={result.get('real_repair_approval_execution_performed', 0)} "
        f"real_repair_approval_subprocess_invoked={result.get('real_repair_approval_subprocess_invoked', 0)} "
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check controlled execution readiness before any execution adapter.",
    )
    parser.add_argument(
        "--db-path",
        default=config.crdt_db_path,
        help="Path to CRDT sqlite database.",
    )
    parser.add_argument(
        "--proposal-id",
        default="",
        help="Retry governance proposal id filter.",
    )
    parser.add_argument(
        "--rendered-command-id",
        default="",
        help="Controlled rendered command id filter.",
    )
    parser.add_argument(
        "--require-operator-authorized",
        action="store_true",
        help="Require operator_authorized=true for mock execution readiness.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON result.",
    )
    return parser


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s",
    )
    args = build_parser().parse_args()
    result = check_controlled_execution_readiness(args)
    schema_validation = validate_controlled_execution_readiness_report_schema(result)
    result["schema_validation"] = schema_validation

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(_format_result(result))

    raise SystemExit(_exit_code_for_result(result))


if __name__ == "__main__":
    main()