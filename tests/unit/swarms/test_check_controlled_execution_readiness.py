import argparse

from src.testing.check_controlled_execution_readiness import (
    _build_checks,
    _exit_code_for_result,
    _format_result,
    READINESS_SCHEMA_VERSION,
    validate_controlled_execution_readiness_report_schema,
)


def _trail_summary(**overrides):
    item = {
        "chain_complete": True,
        "counts": {
            "controlled_execution_results": 1,
        },
        "controlled_execution_result_statuses": {
            "rejected": 1,
        },
        "controlled_execution_result_reasons": {
            "controlled_execution_not_implemented": 1,
        },
        "controlled_command_parse_valid": {
            "true": 1,
        },
        "controlled_command_parse_allowlist_matched": {
            "true": 1,
        },
        "controlled_command_parse_execution_performed": {
            "false": 1,
        },
        "controlled_execution_operator_authorized": {
            "true": 1,
        },
        "controlled_gate_statuses": {
            "blocked": 1,
        },
        "controlled_gate_would_execute": {
            "false": 1,
        },
        "controlled_gate_execution_performed": {
            "false": 1,
        },
        "controlled_gate_reasons": {
            "controlled_execution_not_enabled": 1,
            "controlled_execution_implementation_not_enabled": 1,
        },
        "controlled_mock_statuses": {
            "mock_executed": 1,
        },
        "controlled_mock_performed": {
            "true": 1,
        },
        "controlled_mock_subprocess_invoked": {
            "false": 1,
        },
        "mock_summary_statuses": {
            "mock_executed": 1,
        },
        "mock_summary_performed": {
            "true": 1,
        },
        "mock_summary_subprocess_invoked": {
            "false": 1,
        },
        "controlled_mock_adapter": {
            "mock": 1,
        },
        "controlled_mock_adapter_mode": {
            "mock": 1,
        },
        "controlled_mock_adapter_result_statuses": {
            "mock_executed": 1,
        },
        "controlled_mock_adapter_subprocess_invoked": {
            "false": 1,
        },
        "controlled_mock_adapter_real_execution_enabled": {
            "false": 1,
        },
        "controlled_mock_adapter_payload_executed": {
            "false": 1,
        },
        "controlled_real_execution_requested": {
            "false": 1,
        },
        "controlled_real_execution_performed": {
            "false": 1,
        },
        "controlled_real_execution_supported": {
            "false": 1,
        },
        "controlled_subprocess_invoked": {
            "false": 1,
        },
        "real_preflight_statuses": {"blocked": 1},
        "real_preflight_reasons": {"real_execution_not_supported": 1},
        "real_preflight_would_execute": {"false": 1},
        "real_preflight_execution_performed": {"false": 1},
        "real_preflight_subprocess_invoked": {"false": 1},
        "real_preflight_requires_explicit_pr": {"true": 1},
        "real_approval_statuses": {"pending": 1},
        "real_approval_enabled": {"false": 1},
        "real_approval_subprocess_enabled": {"false": 1},
        "real_approval_execution_performed": {"false": 1},
        "real_approval_subprocess_invoked": {"false": 1},
        "real_linkage_complete": True,
        "real_preflight_orphans": 0,
        "real_approval_orphans": 0,
        "real_approval_transition_statuses": {"approved": 1},
        "real_approval_transition_enabled": {"false": 1},
        "real_approval_transition_subprocess_enabled": {"false": 1},
        "real_approval_transition_execution_performed": {"false": 1},
        "real_approval_transition_subprocess_invoked": {"false": 1},
        "real_approval_latest_status": "approved",
        "real_final_gate_statuses": {"blocked": 1},
        "real_final_gate_would_execute": {"false": 1},
        "real_final_gate_ready": {"false": 1},
        "real_final_gate_real_execution_enabled": {"false": 1},
        "real_final_gate_subprocess_enabled": {"false": 1},
        "real_final_gate_execution_performed": {"false": 1},
        "real_final_gate_subprocess_invoked": {"false": 1},
        "real_dry_run_envelope_dry_run_only": {"true": 1},
        "real_dry_run_envelope_would_execute": {"false": 1},
        "real_dry_run_envelope_ready": {"false": 1},
        "real_dry_run_envelope_real_execution_enabled": {"false": 1},
        "real_dry_run_envelope_subprocess_enabled": {"false": 1},
        "real_dry_run_envelope_execution_performed": {"false": 1},
        "real_dry_run_envelope_subprocess_invoked": {"false": 1},
        "real_dry_run_linkage_complete": True,
        "real_dry_run_envelope_orphans": 0,
        "real_noop_result_noop_only": {"true": 1},
        "real_noop_result_rendered_command_executed": {"false": 1},
        "real_noop_result_dry_run_command_executed": {"false": 1},
        "real_noop_result_real_execution_enabled": {"false": 1},
        "real_noop_result_subprocess_invoked": {"true": 1},
        "real_noop_result_execution_performed": {"true": 1},
        "real_noop_result_exit_codes": {"0": 1},
        "real_noop_result_stdout_marker_observed": {"true": 1},
        "real_noop_linkage_complete": True,
        "real_noop_result_orphans": 0,
        "real_read_only_promotion_statuses": {"promoted": 1},
        "real_read_only_promotion_candidates": {"true": 1},
        "real_read_only_promotion_command_parse_valid": {"true": 1},
        "real_read_only_promotion_stdout_marker_observed": {"true": 1},
        "real_read_only_promotion_noop_exit_codes": {"0": 1},
        "real_read_only_promotion_rendered_command_executed": {"false": 1},
        "real_read_only_promotion_dry_run_command_executed": {"false": 1},
        "real_read_only_promotion_real_execution_enabled": {"false": 1},
        "real_read_only_promotion_subprocess_invoked": {"false": 1},
        "real_read_only_promotion_execution_performed": {"false": 1},
        "real_read_only_promotion_linkage_complete": True,
        "real_read_only_promotion_orphans": 0,
        "real_read_only_final_gate_statuses": {"blocked": 1},
        "real_read_only_final_gate_preconditions_satisfied": {"true": 1},
        "real_read_only_final_gate_ready": {"false": 1},
        "real_read_only_final_gate_would_execute": {"false": 1},
        "real_read_only_final_gate_read_only_execution_enabled": {"false": 1},
        "real_read_only_final_gate_real_execution_enabled": {"false": 1},
        "real_read_only_final_gate_subprocess_enabled": {"false": 1},
        "real_read_only_final_gate_subprocess_invoked": {"false": 1},
        "real_read_only_final_gate_execution_performed": {"false": 1},
        "real_read_only_final_gate_rendered_command_executed": {"false": 1},
        "real_read_only_final_gate_dry_run_command_executed": {"false": 1},
        "real_read_only_final_gate_linkage_complete": True,
        "real_read_only_final_gate_orphans": 0,
        "real_read_only_approval_statuses": {"pending": 1},
        "real_read_only_approval_read_only_execution_enabled": {"false": 1},
        "real_read_only_approval_real_execution_enabled": {"false": 1},
        "real_read_only_approval_subprocess_enabled": {"false": 1},
        "real_read_only_approval_subprocess_invoked": {"false": 1},
        "real_read_only_approval_execution_performed": {"false": 1},
        "real_read_only_approval_rendered_command_executed": {"false": 1},
        "real_read_only_approval_dry_run_command_executed": {"false": 1},
        "real_read_only_approval_linkage_complete": True,
        "real_read_only_approval_orphans": 0,
        "real_read_only_approval_transition_from_statuses": {"pending": 1},
        "real_read_only_approval_transition_to_statuses": {"approved": 1},
        "real_read_only_approval_transition_read_only_execution_enabled": {"false": 1},
        "real_read_only_approval_transition_real_execution_enabled": {"false": 1},
        "real_read_only_approval_transition_subprocess_enabled": {"false": 1},
        "real_read_only_approval_transition_subprocess_invoked": {"false": 1},
        "real_read_only_approval_transition_execution_performed": {"false": 1},
        "real_read_only_approval_transition_rendered_command_executed": {"false": 1},
        "real_read_only_approval_transition_dry_run_command_executed": {"false": 1},
        "real_read_only_approval_latest_status": "approved",
        "real_read_only_approval_transition_linkage_complete": True,
        "real_read_only_approval_transition_orphans": 0,
        "real_read_only_readiness_gate_statuses": {"ready_blocked": 1},
        "real_read_only_readiness_gate_satisfied": {"true": 1},
        "real_read_only_readiness_gate_ready": {"true": 1},
        "real_read_only_readiness_gate_read_only_execution_enabled": {"false": 1},
        "real_read_only_readiness_gate_real_execution_enabled": {"false": 1},
        "real_read_only_readiness_gate_subprocess_enabled": {"false": 1},
        "real_read_only_readiness_gate_subprocess_invoked": {"false": 1},
        "real_read_only_readiness_gate_execution_performed": {"false": 1},
        "real_read_only_readiness_gate_rendered_command_executed": {"false": 1},
        "real_read_only_readiness_gate_dry_run_command_executed": {"false": 1},
        "real_read_only_readiness_gate_linkage_complete": True,
        "real_read_only_readiness_gate_orphans": 0,
        "real_read_only_execution_result_statuses": {"failed": 1},
        "real_read_only_execution_result_reasons": {
            "guarded_read_only_execution_failed": 1,
        },
        "real_read_only_execution_result_exit_codes": {"1": 1},
        "real_read_only_execution_result_validation_reasons_empty": {"true": 1},
        "real_read_only_execution_result_operator_authorized": {"true": 1},
        "real_read_only_execution_result_allow_guarded": {"true": 1},
        "real_read_only_execution_result_read_only_execution_enabled": {"true": 1},
        "real_read_only_execution_result_real_execution_enabled": {"false": 1},
        "real_read_only_execution_result_subprocess_invoked": {"true": 1},
        "real_read_only_execution_result_execution_performed": {"true": 1},
        "real_read_only_execution_result_read_only_command_executed": {"true": 1},
        "real_read_only_execution_result_rendered_command_executed": {"true": 1},
        "real_read_only_execution_result_dry_run_command_executed": {"true": 1},
        "real_read_only_execution_result_linkage_complete": True,
        "real_read_only_execution_result_orphans": 0,
        "real_read_only_feedback_statuses": {"actionable": 1},
        "real_read_only_feedback_source_statuses": {"failed": 1},
        "real_read_only_feedback_source_exit_codes": {"1": 1},
        "real_read_only_feedback_next_actions": {
            "investigate_failed_read_only_evidence_check": 1,
        },
        "real_read_only_feedback_execution_observed": {"true": 1},
        "real_read_only_feedback_failed": {"true": 1},
        "real_read_only_feedback_succeeded": {"false": 1},
        "real_read_only_feedback_rejected": {"false": 1},
        "real_read_only_feedback_real_execution_enabled": {"false": 1},
        "real_read_only_feedback_feedback_execution_performed": {"false": 1},
        "real_read_only_feedback_feedback_subprocess_invoked": {"false": 1},
        "real_read_only_feedback_execution_performed": {"false": 1},
        "real_read_only_feedback_subprocess_invoked": {"false": 1},
        "real_read_only_feedback_linkage_complete": True,
        "real_read_only_feedback_orphans": 0,
        "real_read_only_repair_plan_statuses": {"planned": 1},
        "real_read_only_repair_plan_source_feedback_statuses": {"actionable": 1},
        "real_read_only_repair_plan_source_statuses": {"failed": 1},
        "real_read_only_repair_plan_source_exit_codes": {"1": 1},
        "real_read_only_repair_plan_next_actions": {
            "review_replay_evidence_repair_plan": 1,
        },
        "real_read_only_repair_plan_item_counts": {"9": 1},
        "real_read_only_repair_plan_requires_operator_review": {"true": 1},
        "real_read_only_repair_plan_repair_execution_enabled": {"false": 1},
        "real_read_only_repair_plan_real_execution_enabled": {"false": 1},
        "real_read_only_repair_plan_subprocess_enabled": {"false": 1},
        "real_read_only_repair_plan_repair_execution_performed": {"false": 1},
        "real_read_only_repair_plan_repair_subprocess_invoked": {"false": 1},
        "real_read_only_repair_plan_execution_performed": {"false": 1},
        "real_read_only_repair_plan_subprocess_invoked": {"false": 1},
        "real_read_only_repair_plan_linkage_complete": True,
        "real_read_only_repair_plan_orphans": 0,
        "real_read_only_repair_action_bundle_statuses": {"assembled": 1},
        "real_read_only_repair_action_bundle_source_plan_statuses": {"planned": 1},
        "real_read_only_repair_action_bundle_source_feedback_statuses": {"actionable": 1},
        "real_read_only_repair_action_bundle_source_statuses": {"failed": 1},
        "real_read_only_repair_action_bundle_source_exit_codes": {"1": 1},
        "real_read_only_repair_action_bundle_next_actions": {
            "review_repair_action_bundle": 1,
        },
        "real_read_only_repair_action_bundle_item_counts": {"9": 1},
        "real_read_only_repair_action_bundle_source_item_counts": {"9": 1},
        "real_read_only_repair_action_bundle_requires_operator_review": {"true": 1},
        "real_read_only_repair_action_bundle_reviewed": {"false": 1},
        "real_read_only_repair_action_bundle_bundle_execution_enabled": {"false": 1},
        "real_read_only_repair_action_bundle_repair_execution_enabled": {"false": 1},
        "real_read_only_repair_action_bundle_real_execution_enabled": {"false": 1},
        "real_read_only_repair_action_bundle_subprocess_enabled": {"false": 1},
        "real_read_only_repair_action_bundle_bundle_execution_performed": {"false": 1},
        "real_read_only_repair_action_bundle_bundle_subprocess_invoked": {"false": 1},
        "real_read_only_repair_action_bundle_execution_performed": {"false": 1},
        "real_read_only_repair_action_bundle_subprocess_invoked": {"false": 1},
        "real_read_only_repair_action_bundle_linkage_complete": True,
        "real_read_only_repair_action_bundle_orphans": 0,
        "real_read_only_repair_action_bundle_review_statuses": {"approved": 1},
        "real_read_only_repair_action_bundle_review_source_bundle_statuses": {
            "assembled": 1
        },
        "real_read_only_repair_action_bundle_review_source_plan_statuses": {
            "planned": 1
        },
        "real_read_only_repair_action_bundle_review_source_feedback_statuses": {
            "actionable": 1
        },
        "real_read_only_repair_action_bundle_review_source_statuses": {"failed": 1},
        "real_read_only_repair_action_bundle_review_source_exit_codes": {"1": 1},
        "real_read_only_repair_action_bundle_review_source_item_counts": {"9": 1},
        "real_read_only_repair_action_bundle_review_next_actions": {
            "prepare_repair_execution_approval_scaffold": 1,
        },
        "real_read_only_repair_action_bundle_review_operator_authorized": {"true": 1},
        "real_read_only_repair_action_bundle_review_requires_operator_review": {"true": 1},
        "real_read_only_repair_action_bundle_review_reviewed": {"true": 1},
        "real_read_only_repair_action_bundle_review_approved": {"true": 1},
        "real_read_only_repair_action_bundle_review_rejected": {"false": 1},
        "real_read_only_repair_action_bundle_review_bundle_execution_enabled": {"false": 1},
        "real_read_only_repair_action_bundle_review_repair_execution_enabled": {"false": 1},
        "real_read_only_repair_action_bundle_review_real_execution_enabled": {"false": 1},
        "real_read_only_repair_action_bundle_review_subprocess_enabled": {"false": 1},
        "real_read_only_repair_action_bundle_review_bundle_execution_performed": {"false": 1},
        "real_read_only_repair_action_bundle_review_bundle_subprocess_invoked": {"false": 1},
        "real_read_only_repair_action_bundle_review_execution_performed": {"false": 1},
        "real_read_only_repair_action_bundle_review_subprocess_invoked": {"false": 1},
        "real_read_only_repair_action_bundle_review_linkage_complete": True,
        "real_read_only_repair_action_bundle_review_orphans": 0,
        "real_repair_approval_statuses": {"pending": 1},
        "real_repair_approval_source_review_statuses": {"approved": 1},
        "real_repair_approval_source_bundle_statuses": {"assembled": 1},
        "real_repair_approval_next_actions": {
            "await_repair_execution_approval": 1,
        },
        "real_repair_approval_operator_authorized": {"true": 1},
        "real_repair_approval_required": {"true": 1},
        "real_repair_approval_approved": {"false": 1},
        "real_repair_approval_rejected": {"false": 1},
        "real_repair_approval_repair_execution_enabled": {"false": 1},
        "real_repair_approval_real_execution_enabled": {"false": 1},
        "real_repair_approval_subprocess_enabled": {"false": 1},
        "real_repair_approval_repair_execution_performed": {"false": 1},
        "real_repair_approval_repair_subprocess_invoked": {"false": 1},
        "real_repair_approval_execution_performed": {"false": 1},
        "real_repair_approval_subprocess_invoked": {"false": 1},
        "real_repair_approval_linkage_complete": True,
        "real_repair_approval_orphans": 0,
        "real_repair_approval_transition_from_statuses": {"pending": 1},
        "real_repair_approval_transition_to_statuses": {"approved": 1},
        "real_repair_approval_transition_source_approval_statuses": {"pending": 1},
        "real_repair_approval_transition_source_review_statuses": {"approved": 1},
        "real_repair_approval_transition_next_actions": {
            "prepare_repair_execution_final_gate": 1,
        },
        "real_repair_approval_transition_operator_authorized": {"true": 1},
        "real_repair_approval_transition_required": {"true": 1},
        "real_repair_approval_transition_approved": {"true": 1},
        "real_repair_approval_transition_rejected": {"false": 1},
        "real_repair_approval_transition_repair_execution_enabled": {"false": 1},
        "real_repair_approval_transition_real_execution_enabled": {"false": 1},
        "real_repair_approval_transition_subprocess_enabled": {"false": 1},
        "real_repair_approval_transition_repair_execution_performed": {"false": 1},
        "real_repair_approval_transition_repair_subprocess_invoked": {"false": 1},
        "real_repair_approval_transition_execution_performed": {"false": 1},
        "real_repair_approval_transition_subprocess_invoked": {"false": 1},
        "real_repair_approval_transition_linkage_complete": True,
        "real_repair_approval_transition_orphans": 0,
        "real_repair_final_gate_statuses": {"ready_blocked": 1},
        "real_repair_final_gate_preconditions_satisfied": {"true": 1},
        "real_repair_final_gate_ready": {"false": 1},
        "real_repair_final_gate_would_execute": {"false": 1},
        "real_repair_final_gate_next_actions": {
            "prepare_repair_execution_dry_run_envelope": 1,
        },
        "real_repair_final_gate_operator_authorized": {"true": 1},
        "real_repair_final_gate_transition_approved": {"true": 1},
        "real_repair_final_gate_repair_execution_enabled": {"false": 1},
        "real_repair_final_gate_real_execution_enabled": {"false": 1},
        "real_repair_final_gate_subprocess_enabled": {"false": 1},
        "real_repair_final_gate_repair_execution_performed": {"false": 1},
        "real_repair_final_gate_repair_subprocess_invoked": {"false": 1},
        "real_repair_final_gate_execution_performed": {"false": 1},
        "real_repair_final_gate_subprocess_invoked": {"false": 1},
        "real_repair_final_gate_linkage_complete": True,
        "real_repair_final_gate_orphans": 0,
    }
    item.update(overrides)
    return item


def _retry_observability(**overrides):
    item = {
        "status": "passed",
    }
    item.update(overrides)
    return item


def _controlled_observability(**overrides):
    item = {
        "status": "passed",
        "controlled_execution_executed": 0,
        "controlled_execution_gate_execution_performed": 0,
    }
    item.update(overrides)
    return item


def _report(**overrides):
    report = {
        "type": "controlled_execution_readiness_report",
        "schema_version": READINESS_SCHEMA_VERSION,
        "schema_kind": "controlled_execution_readiness",
        "status": "passed",
        "ready_for_mock_execution": True,
        "ready_for_real_execution": False,
        "blocking_reasons": ["real_execution_not_supported_yet"],
        "mock_execution_observed": True,
        "mock_execution_performed": 1,
        "mock_subprocess_invoked": 0,
        "adapter_contract_observed": True,
        "adapter_mock": 1,
        "adapter_mode_mock": 1,
        "adapter_result_mock_executed": 1,
        "adapter_subprocess_invoked": 0,
        "adapter_real_execution_enabled": 0,
        "adapter_payload_executed": 0,
        "real_dry_run_linkage_complete": True,
        "real_dry_run_envelope_orphans": 0,
        "checks": [],
        "exit_codes": {
            "trail": 0,
            "retry_observability": 0,
            "controlled_observability": 0,
            "real_execution": 1,
        },
    }
    report.update(overrides)
    return report


def test_controlled_execution_readiness_checks_pass_for_safe_pre_execution_stack() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    assert [item for item in checks if item["status"] != "passed"] == []


def test_controlled_execution_readiness_checks_fail_without_operator_when_required() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            controlled_execution_operator_authorized={"false": 1}
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert failed == ["operator_authorized"]


def test_controlled_execution_readiness_checks_allow_missing_operator_when_optional() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            controlled_execution_operator_authorized={"false": 1}
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=False,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert failed == []


def test_controlled_execution_readiness_checks_fail_when_gate_would_execute() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            controlled_gate_would_execute={"true": 1}
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=False,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "controlled_gate_would_not_execute" in failed


def test_controlled_execution_readiness_checks_fail_when_observability_failed() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(),
        retry_observability=_retry_observability(status="failed"),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=False,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "retry_observability_passed" in failed


def test_controlled_execution_readiness_format_reports_mock_and_real_readiness() -> None:
    text = _format_result(
        {
            "status": "passed",
            "ready_for_mock_execution": True,
            "ready_for_real_execution": False,
            "require_operator_authorized": True,
            "blocking_reasons": ["real_execution_not_supported_yet"],
            "mock_execution_observed": True,
            "mock_execution_performed": 1,
            "mock_subprocess_invoked": 0,
            "adapter_contract_observed": True,
            "adapter_mock": 1,
            "adapter_mode_mock": 1,
            "adapter_result_mock_executed": 1,
            "adapter_subprocess_invoked": 0,
            "adapter_real_execution_enabled": 0,
            "adapter_payload_executed": 0,
            "schema_version": READINESS_SCHEMA_VERSION,
            "real_adapter_supported": False,
            "real_adapter_runnable": False,
            "real_adapter_requires_explicit_pr": True,
            "real_execution_request_observed": True,
            "real_execution_request_rejected": 1,
            "real_execution_requested": 1,
            "real_execution_performed": 0,
            "real_execution_supported_count": 0,
            "subprocess_invoked_count": 0,
            "real_preflight_observed": True,
            "real_preflight_blocked": 1,
            "real_preflight_would_execute": 0,
            "real_preflight_execution_performed": 0,
            "real_preflight_subprocess_invoked": 0,
            "real_preflight_requires_explicit_pr": 1,
            "real_approval_observed": True,
            "real_approval_records": 1,
            "real_approval_enabled": 0,
            "real_approval_subprocess_enabled": 0,
            "real_approval_execution_performed": 0,
            "real_approval_subprocess_invoked": 0,
            "real_dry_run_envelope_observed": True,
            "real_dry_run_envelope_records": 1,
            "real_dry_run_envelope_would_execute": 0,
            "real_dry_run_envelope_ready": 0,
            "real_dry_run_envelope_real_execution_enabled": 0,
            "real_dry_run_envelope_subprocess_enabled": 0,
            "real_dry_run_envelope_execution_performed": 0,
            "real_dry_run_envelope_subprocess_invoked": 0,
            "real_noop_result_observed": True,
            "real_noop_result_records": 1,
            "real_noop_result_rendered_command_executed": 0,
            "real_noop_result_dry_run_command_executed": 0,
            "real_noop_result_real_execution_enabled": 0,
            "real_noop_result_subprocess_invoked": 1,
            "real_noop_result_execution_performed": 1,
            "real_noop_result_exit_code_zero": 1,
            "real_noop_linkage_complete": True,
            "real_noop_result_orphans": 0,
            "real_noop_result_stdout_marker_observed": 1,
            "real_read_only_promotion_observed": True,
            "real_read_only_promotion_records": 1,
            "real_read_only_promotion_linkage_complete": True,
            "real_read_only_promotion_orphans": 0,
            "real_read_only_promotion_candidate": 1,
            "real_read_only_promotion_command_parse_valid": 1,
            "real_read_only_promotion_stdout_marker_observed": 1,
            "real_read_only_promotion_noop_exit_code_zero": 1,
            "real_read_only_promotion_rendered_command_executed": 0,
            "real_read_only_promotion_dry_run_command_executed": 0,
            "real_read_only_promotion_real_execution_enabled": 0,
            "real_read_only_promotion_subprocess_invoked": 0,
            "real_read_only_promotion_execution_performed": 0,
            "real_read_only_final_gate_observed": True,
            "real_read_only_final_gate_records": 1,
            "real_read_only_final_gate_linkage_complete": True,
            "real_read_only_final_gate_orphans": 0,
            "real_read_only_final_gate_preconditions_satisfied": 1,
            "real_read_only_final_gate_ready": 0,
            "real_read_only_final_gate_would_execute": 0,
            "real_read_only_final_gate_read_only_execution_enabled": 0,
            "real_read_only_final_gate_real_execution_enabled": 0,
            "real_read_only_final_gate_subprocess_enabled": 0,
            "real_read_only_final_gate_subprocess_invoked": 0,
            "real_read_only_final_gate_execution_performed": 0,
            "real_read_only_final_gate_rendered_command_executed": 0,
            "real_read_only_final_gate_dry_run_command_executed": 0,
        }
    )

    assert "status=passed" in text
    assert "ready_for_mock_execution=true" in text
    assert "ready_for_real_execution=false" in text
    assert "require_operator_authorized=true" in text
    assert "blocking_reasons=real_execution_not_supported_yet" in text
    assert "mock_execution_observed=true" in text
    assert "mock_execution_performed=1" in text
    assert "mock_subprocess_invoked=0" in text
    assert "adapter_contract_observed=true" in text
    assert "adapter_mock=1" in text
    assert "adapter_mode_mock=1" in text
    assert "adapter_result_mock_executed=1" in text
    assert "adapter_subprocess_invoked=0" in text
    assert "adapter_real_execution_enabled=0" in text
    assert "adapter_payload_executed=0" in text
    assert f"schema_version={READINESS_SCHEMA_VERSION}" in text
    assert "real_adapter_supported=false" in text
    assert "real_adapter_runnable=false" in text
    assert "real_adapter_requires_explicit_pr=true" in text
    assert "real_execution_request_observed=true" in text
    assert "real_execution_request_rejected=1" in text
    assert "real_execution_requested=1" in text
    assert "real_execution_performed=0" in text
    assert "real_execution_supported_count=0" in text
    assert "subprocess_invoked_count=0" in text
    assert "real_preflight_observed=true" in text
    assert "real_preflight_blocked=1" in text
    assert "real_preflight_would_execute=0" in text
    assert "real_preflight_execution_performed=0" in text
    assert "real_preflight_subprocess_invoked=0" in text
    assert "real_approval_observed=true" in text
    assert "real_approval_records=1" in text
    assert "real_approval_enabled=0" in text
    assert "real_approval_subprocess_enabled=0" in text
    assert "real_approval_execution_performed=0" in text
    assert "real_approval_subprocess_invoked=0" in text
    assert "real_dry_run_envelope_observed=true" in text
    assert "real_dry_run_envelope_records=1" in text
    assert "real_dry_run_envelope_would_execute=0" in text
    assert "real_dry_run_envelope_subprocess_invoked=0" in text
    assert "real_noop_result_observed=true" in text
    assert "real_noop_result_records=1" in text
    assert "real_noop_result_subprocess_invoked=1" in text
    assert "real_noop_result_exit_code_zero=1" in text
    assert "real_noop_linkage_complete=true" in text
    assert "real_noop_result_orphans=0" in text
    assert "real_noop_result_stdout_marker_observed=1" in text
    assert "real_read_only_promotion_observed=true" in text
    assert "real_read_only_promotion_records=1" in text
    assert "real_read_only_promotion_linkage_complete=true" in text
    assert "real_read_only_promotion_orphans=0" in text
    assert "real_read_only_promotion_candidate=1" in text
    assert "real_read_only_promotion_command_parse_valid=1" in text
    assert "real_read_only_promotion_stdout_marker_observed=1" in text
    assert "real_read_only_promotion_noop_exit_code_zero=1" in text
    assert "real_read_only_promotion_rendered_command_executed=0" in text
    assert "real_read_only_promotion_dry_run_command_executed=0" in text
    assert "real_read_only_promotion_real_execution_enabled=0" in text
    assert "real_read_only_promotion_subprocess_invoked=0" in text
    assert "real_read_only_promotion_execution_performed=0" in text
    assert "real_read_only_final_gate_observed=true" in text
    assert "real_read_only_final_gate_records=1" in text
    assert "real_read_only_final_gate_linkage_complete=true" in text
    assert "real_read_only_final_gate_orphans=0" in text
    assert "real_read_only_final_gate_preconditions_satisfied=1" in text
    assert "real_read_only_final_gate_ready=0" in text
    assert "real_read_only_final_gate_would_execute=0" in text
    assert "real_read_only_final_gate_read_only_execution_enabled=0" in text
    assert "real_read_only_final_gate_real_execution_enabled=0" in text
    assert "real_read_only_final_gate_subprocess_enabled=0" in text
    assert "real_read_only_final_gate_subprocess_invoked=0" in text
    assert "real_read_only_final_gate_execution_performed=0" in text
    assert "real_read_only_final_gate_rendered_command_executed=0" in text
    assert "real_read_only_final_gate_dry_run_command_executed=0" in text


def test_controlled_execution_readiness_exit_code() -> None:
    assert _exit_code_for_result({"status": "passed"}) == 0
    assert _exit_code_for_result({"status": "failed"}) == 1


def test_controlled_execution_readiness_checks_fail_when_mock_missing() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            controlled_mock_statuses={},
            controlled_mock_performed={},
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "mock_execution_observed" in failed
    assert "mock_execution_performed" in failed


def test_controlled_execution_readiness_checks_fail_when_mock_summary_missing() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            mock_summary_statuses={},
            mock_summary_performed={},
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "mock_execution_summary_observed" in failed
    assert "mock_execution_summary_performed" in failed


def test_controlled_execution_readiness_checks_fail_when_adapter_contract_missing() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            controlled_mock_adapter={},
            controlled_mock_adapter_mode={},
            controlled_mock_adapter_result_statuses={},
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "adapter_contract_observed" in failed
    assert "adapter_is_mock" in failed
    assert "adapter_mode_is_mock" in failed
    assert "adapter_result_mock_executed" in failed


def test_controlled_execution_readiness_checks_fail_when_adapter_invokes_subprocess() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            controlled_mock_adapter_subprocess_invoked={"true": 1}
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "adapter_subprocess_not_invoked" in failed


def test_controlled_execution_readiness_checks_fail_when_adapter_payload_executed() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            controlled_mock_adapter_payload_executed={"true": 1}
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "adapter_payload_not_executed" in failed


def test_controlled_execution_readiness_checks_fail_when_adapter_real_execution_enabled() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            controlled_mock_adapter_real_execution_enabled={"true": 1}
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "adapter_real_execution_not_enabled" in failed


def test_controlled_execution_readiness_checks_fail_when_adapter_is_not_mock() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            controlled_mock_adapter={"real": 1},
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "adapter_contract_observed" in failed
    assert "adapter_is_mock" in failed


def test_controlled_execution_readiness_checks_fail_when_adapter_mode_is_not_mock() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            controlled_mock_adapter_mode={"real": 1},
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "adapter_contract_observed" in failed
    assert "adapter_mode_is_mock" in failed


def test_controlled_execution_readiness_report_contract_shape_from_checks() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )
    failed_checks = [item for item in checks if item["status"] != "passed"]
    report = {
        "type": "controlled_execution_readiness_report",
        "schema_version": READINESS_SCHEMA_VERSION,
        "schema_kind": "controlled_execution_readiness",
        "real_adapter_requires_explicit_pr": True,
        "adapter_contract": {
            "type": "controlled_retry_execution_adapter_contract",
            "real_execution_supported": False,
            "real_adapter_contract": {
                "runnable": False,
            },
        },
        "real_adapter_supported": False,
        "real_adapter_runnable": False,
        "real_execution_request_observed": False,
        "real_execution_request_rejected": 0,
        "real_preflight_observed": True,
        "real_preflight_blocked": 1,
        "real_approval_observed": True,
        "real_approval_records": 1,
        "real_linkage_complete": True,
        "real_preflight_orphans": 0,
        "real_approval_orphans": 0,
        "real_approval_transition_observed": True,
        "real_approval_transition_records": 1,
        "real_approval_latest_status": "approved",
        "real_approval_transition_enabled": 0,
        "real_approval_transition_subprocess_enabled": 0,
        "real_approval_transition_execution_performed": 0,
        "real_approval_transition_subprocess_invoked": 0,
        "real_final_gate_observed": True,
        "real_final_gate_blocked": 1,
        "real_dry_run_envelope_observed": True,
        "real_dry_run_envelope_records": 1,
        "real_dry_run_envelope_would_execute": 0,
        "real_dry_run_envelope_ready": 0,
        "real_dry_run_envelope_real_execution_enabled": 0,
        "real_dry_run_envelope_subprocess_enabled": 0,
        "real_dry_run_envelope_execution_performed": 0,
        "real_dry_run_envelope_subprocess_invoked": 0,
        "real_dry_run_linkage_complete": True,
        "real_dry_run_envelope_orphans": 0,
        "real_noop_result_observed": True,
        "real_noop_result_records": 1,
        "real_noop_result_rendered_command_executed": 0,
        "real_noop_result_dry_run_command_executed": 0,
        "real_noop_result_real_execution_enabled": 0,
        "real_noop_result_subprocess_invoked": 1,
        "real_noop_result_execution_performed": 1,
        "real_noop_result_exit_code_zero": 1,
        "real_noop_linkage_complete": True,
        "real_noop_result_orphans": 0,
        "real_noop_result_stdout_marker_observed": 1,
        "real_read_only_promotion_observed": True,
        "real_read_only_promotion_records": 1,
        "real_read_only_promotion_linkage_complete": True,
        "real_read_only_promotion_orphans": 0,
        "real_read_only_promotion_candidate": 1,
        "real_read_only_promotion_command_parse_valid": 1,
        "real_read_only_promotion_stdout_marker_observed": 1,
        "real_read_only_promotion_noop_exit_code_zero": 1,
        "real_read_only_promotion_rendered_command_executed": 0,
        "real_read_only_promotion_dry_run_command_executed": 0,
        "real_read_only_promotion_real_execution_enabled": 0,
        "real_read_only_promotion_subprocess_invoked": 0,
        "real_read_only_promotion_execution_performed": 0,
        "real_read_only_final_gate_observed": True,
        "real_read_only_final_gate_records": 1,
        "real_read_only_final_gate_linkage_complete": True,
        "real_read_only_final_gate_orphans": 0,
        "real_read_only_final_gate_preconditions_satisfied": 1,
        "real_read_only_final_gate_ready": 0,
        "real_read_only_final_gate_would_execute": 0,
        "real_read_only_final_gate_read_only_execution_enabled": 0,
        "real_read_only_final_gate_real_execution_enabled": 0,
        "real_read_only_final_gate_subprocess_enabled": 0,
        "real_read_only_final_gate_subprocess_invoked": 0,
        "real_read_only_final_gate_execution_performed": 0,
        "real_read_only_final_gate_rendered_command_executed": 0,
        "real_read_only_final_gate_dry_run_command_executed": 0,
        "real_read_only_approval_observed": True,
        "real_read_only_approval_records": 1,
        "real_read_only_approval_linkage_complete": True,
        "real_read_only_approval_orphans": 0,
        "real_read_only_approval_pending": 1,
        "real_read_only_approval_read_only_execution_enabled": 0,
        "real_read_only_approval_real_execution_enabled": 0,
        "real_read_only_approval_subprocess_enabled": 0,
        "real_read_only_approval_subprocess_invoked": 0,
        "real_read_only_approval_execution_performed": 0,
        "real_read_only_approval_rendered_command_executed": 0,
        "real_read_only_approval_dry_run_command_executed": 0,
        "real_read_only_approval_transition_observed": True,
        "real_read_only_approval_transition_records": 1,
        "real_read_only_approval_transition_linkage_complete": True,
        "real_read_only_approval_transition_orphans": 0,
        "real_read_only_approval_latest_status": "approved",
        "real_read_only_approval_transition_from_pending": 1,
        "real_read_only_approval_transition_approved": 1,
        "real_read_only_approval_transition_rejected": 0,
        "real_read_only_approval_transition_read_only_execution_enabled": 0,
        "real_read_only_approval_transition_real_execution_enabled": 0,
        "real_read_only_approval_transition_subprocess_enabled": 0,
        "real_read_only_approval_transition_subprocess_invoked": 0,
        "real_read_only_approval_transition_execution_performed": 0,
        "real_read_only_approval_transition_rendered_command_executed": 0,
        "real_read_only_approval_transition_dry_run_command_executed": 0,
        "real_read_only_readiness_gate_observed": True,
        "real_read_only_readiness_gate_records": 1,
        "real_read_only_readiness_gate_linkage_complete": True,
        "real_read_only_readiness_gate_orphans": 0,
        "real_read_only_readiness_gate_satisfied": 1,
        "real_read_only_readiness_gate_ready": 1,
        "real_read_only_readiness_gate_read_only_execution_enabled": 0,
        "real_read_only_readiness_gate_real_execution_enabled": 0,
        "real_read_only_readiness_gate_subprocess_enabled": 0,
        "real_read_only_readiness_gate_subprocess_invoked": 0,
        "real_read_only_readiness_gate_execution_performed": 0,
        "real_read_only_readiness_gate_rendered_command_executed": 0,
        "real_read_only_readiness_gate_dry_run_command_executed": 0,
        "real_read_only_execution_result_observed": True,
        "real_read_only_execution_result_records": 1,
        "real_read_only_execution_result_failed": 1,
        "real_read_only_execution_result_executed": 0,
        "real_read_only_execution_result_rejected": 0,
        "real_read_only_execution_result_exit_code_1": 1,
        "real_read_only_execution_result_linkage_complete": True,
        "real_read_only_execution_result_orphans": 0,
        "real_read_only_execution_result_validation_reasons_empty": 1,
        "real_read_only_execution_result_operator_authorized": 1,
        "real_read_only_execution_result_allow_guarded": 1,
        "real_read_only_execution_result_read_only_execution_enabled": 1,
        "real_read_only_execution_result_real_execution_enabled": 0,
        "real_read_only_execution_result_subprocess_invoked": 1,
        "real_read_only_execution_result_execution_performed": 1,
        "real_read_only_execution_result_read_only_command_executed": 1,
        "real_read_only_execution_result_rendered_command_executed": 1,
        "real_read_only_execution_result_dry_run_command_executed": 1,
        "real_read_only_feedback_observed": True,
        "real_read_only_feedback_records": 1,
        "real_read_only_feedback_linkage_complete": True,
        "real_read_only_feedback_orphans": 0,
        "real_read_only_feedback_actionable": 1,
        "real_read_only_feedback_source_failed": 1,
        "real_read_only_feedback_source_exit_code_1": 1,
        "real_read_only_feedback_next_action_investigate": 1,
        "real_read_only_feedback_execution_observed": 1,
        "real_read_only_feedback_failed": 1,
        "real_read_only_feedback_real_execution_enabled": 0,
        "real_read_only_feedback_feedback_execution_performed": 0,
        "real_read_only_feedback_feedback_subprocess_invoked": 0,
        "real_read_only_feedback_execution_performed": 0,
        "real_read_only_feedback_subprocess_invoked": 0,
        "real_read_only_repair_plan_observed": True,
        "real_read_only_repair_plan_records": 1,
        "real_read_only_repair_plan_linkage_complete": True,
        "real_read_only_repair_plan_orphans": 0,
        "real_read_only_repair_plan_planned": 1,
        "real_read_only_repair_plan_source_actionable": 1,
        "real_read_only_repair_plan_source_failed": 1,
        "real_read_only_repair_plan_source_exit_code_1": 1,
        "real_read_only_repair_plan_next_action_review": 1,
        "real_read_only_repair_plan_requires_operator_review": 1,
        "real_read_only_repair_plan_repair_execution_enabled": 0,
        "real_read_only_repair_plan_real_execution_enabled": 0,
        "real_read_only_repair_plan_subprocess_enabled": 0,
        "real_read_only_repair_plan_repair_execution_performed": 0,
        "real_read_only_repair_plan_repair_subprocess_invoked": 0,
        "real_read_only_repair_plan_execution_performed": 0,
        "real_read_only_repair_plan_subprocess_invoked": 0,
        "real_read_only_repair_action_bundle_observed": True,
        "real_read_only_repair_action_bundle_records": 1,
        "real_read_only_repair_action_bundle_linkage_complete": True,
        "real_read_only_repair_action_bundle_orphans": 0,
        "real_read_only_repair_action_bundle_assembled": 1,
        "real_read_only_repair_action_bundle_source_planned": 1,
        "real_read_only_repair_action_bundle_source_actionable": 1,
        "real_read_only_repair_action_bundle_source_failed": 1,
        "real_read_only_repair_action_bundle_source_exit_code_1": 1,
        "real_read_only_repair_action_bundle_next_action_review": 1,
        "real_read_only_repair_action_bundle_requires_operator_review": 1,
        "real_read_only_repair_action_bundle_reviewed": 0,
        "real_read_only_repair_action_bundle_bundle_execution_enabled": 0,
        "real_read_only_repair_action_bundle_repair_execution_enabled": 0,
        "real_read_only_repair_action_bundle_real_execution_enabled": 0,
        "real_read_only_repair_action_bundle_subprocess_enabled": 0,
        "real_read_only_repair_action_bundle_bundle_execution_performed": 0,
        "real_read_only_repair_action_bundle_bundle_subprocess_invoked": 0,
        "real_read_only_repair_action_bundle_execution_performed": 0,
        "real_read_only_repair_action_bundle_subprocess_invoked": 0,
        "real_read_only_repair_action_bundle_review_observed": True,
        "real_read_only_repair_action_bundle_review_records": 1,
        "real_read_only_repair_action_bundle_review_linkage_complete": True,
        "real_read_only_repair_action_bundle_review_orphans": 0,
        "real_read_only_repair_action_bundle_review_approved_status": 1,
        "real_read_only_repair_action_bundle_review_source_assembled": 1,
        "real_read_only_repair_action_bundle_review_source_planned": 1,
        "real_read_only_repair_action_bundle_review_source_actionable": 1,
        "real_read_only_repair_action_bundle_review_source_failed": 1,
        "real_read_only_repair_action_bundle_review_source_exit_code_1": 1,
        "real_read_only_repair_action_bundle_review_source_item_count_9": 1,
        "real_read_only_repair_action_bundle_review_next_action_prepare": 1,
        "real_read_only_repair_action_bundle_review_operator_authorized": 1,
        "real_read_only_repair_action_bundle_review_reviewed": 1,
        "real_read_only_repair_action_bundle_review_approved": 1,
        "real_read_only_repair_action_bundle_review_bundle_execution_enabled": 0,
        "real_read_only_repair_action_bundle_review_repair_execution_enabled": 0,
        "real_read_only_repair_action_bundle_review_real_execution_enabled": 0,
        "real_read_only_repair_action_bundle_review_subprocess_enabled": 0,
        "real_read_only_repair_action_bundle_review_bundle_execution_performed": 0,
        "real_read_only_repair_action_bundle_review_bundle_subprocess_invoked": 0,
        "real_read_only_repair_action_bundle_review_execution_performed": 0,
        "real_read_only_repair_action_bundle_review_subprocess_invoked": 0,
        "real_repair_approval_observed": True,
        "real_repair_approval_records": 1,
        "real_repair_approval_linkage_complete": True,
        "real_repair_approval_orphans": 0,
        "real_repair_approval_pending": 1,
        "real_repair_approval_source_review_approved": 1,
        "real_repair_approval_next_action_await": 1,
        "real_repair_approval_operator_authorized": 1,
        "real_repair_approval_required": 1,
        "real_repair_approval_approved": 0,
        "real_repair_approval_repair_execution_enabled": 0,
        "real_repair_approval_real_execution_enabled": 0,
        "real_repair_approval_subprocess_enabled": 0,
        "real_repair_approval_repair_execution_performed": 0,
        "real_repair_approval_repair_subprocess_invoked": 0,
        "real_repair_approval_execution_performed": 0,
        "real_repair_approval_subprocess_invoked": 0,
        "real_repair_approval_transition_observed": True,
        "real_repair_approval_transition_records": 1,
        "real_repair_approval_transition_linkage_complete": True,
        "real_repair_approval_transition_orphans": 0,
        "real_repair_approval_transition_from_pending": 1,
        "real_repair_approval_transition_to_approved": 1,
        "real_repair_approval_transition_source_approval_pending": 1,
        "real_repair_approval_transition_next_action_final_gate": 1,
        "real_repair_approval_transition_operator_authorized": 1,
        "real_repair_approval_transition_required": 1,
        "real_repair_approval_transition_approved": 1,
        "real_repair_approval_transition_repair_execution_enabled": 0,
        "real_repair_approval_transition_real_execution_enabled": 0,
        "real_repair_approval_transition_subprocess_enabled": 0,
        "real_repair_approval_transition_repair_execution_performed": 0,
        "real_repair_approval_transition_repair_subprocess_invoked": 0,
        "real_repair_approval_transition_execution_performed": 0,
        "real_repair_approval_transition_subprocess_invoked": 0,
        "real_repair_final_gate_observed": True,
        "real_repair_final_gate_records": 1,
        "real_repair_final_gate_linkage_complete": True,
        "real_repair_final_gate_orphans": 0,
        "real_repair_final_gate_ready_blocked": 1,
        "real_repair_final_gate_preconditions_satisfied": 1,
        "real_repair_final_gate_ready": 0,
        "real_repair_final_gate_would_execute": 0,
        "real_repair_final_gate_next_action_dry_run_envelope": 1,
        "real_repair_final_gate_operator_authorized": 1,
        "real_repair_final_gate_transition_approved": 1,
        "real_repair_final_gate_repair_execution_enabled": 0,
        "real_repair_final_gate_real_execution_enabled": 0,
        "real_repair_final_gate_subprocess_enabled": 0,
        "real_repair_final_gate_repair_execution_performed": 0,
        "real_repair_final_gate_repair_subprocess_invoked": 0,
        "real_repair_final_gate_execution_performed": 0,
        "real_repair_final_gate_subprocess_invoked": 0,
        "status": "passed" if not failed_checks else "failed",
        "ready_for_mock_execution": not failed_checks,
        "ready_for_real_execution": False,
        "blocking_reasons": (
            ["real_execution_not_supported_yet"]
            if not failed_checks
            else [item["name"] for item in failed_checks]
        ),
        "adapter_contract_observed": True,
        "adapter_subprocess_invoked": 0,
        "adapter_real_execution_enabled": 0,
        "adapter_payload_executed": 0,
        "checks": checks,
        "exit_codes": {
            "trail": 0,
            "retry_observability": 0,
            "controlled_observability": 0,
            "real_execution": 1,
        },
    }

    schema_validation = validate_controlled_execution_readiness_report_schema(report)

    assert failed_checks == []
    assert schema_validation["valid"] is True
    assert report["schema_version"] == READINESS_SCHEMA_VERSION
    assert report["ready_for_real_execution"] is False
    assert report["blocking_reasons"] == ["real_execution_not_supported_yet"]


def test_controlled_execution_readiness_schema_validation_result_shape() -> None:
    report = {
        "type": "controlled_execution_readiness_report",
        "schema_version": READINESS_SCHEMA_VERSION,
        "schema_kind": "controlled_execution_readiness",
        "status": "passed",
        "ready_for_mock_execution": True,
        "ready_for_real_execution": False,
        "blocking_reasons": ["real_execution_not_supported_yet"],
        "adapter_contract_observed": True,
        "adapter_subprocess_invoked": 0,
        "adapter_real_execution_enabled": 0,
        "adapter_payload_executed": 0,
        "adapter_contract": {
            "type": "controlled_retry_execution_adapter_contract",
            "schema_version": "controlled-retry-execution-adapter/v1",
            "supported_adapters": ["mock"],
            "unsupported_adapters": ["real"],
            "placeholder_adapters": ["real"],
            "real_execution_supported": False,
            "subprocess_supported": False,
            "real_adapter_contract": {
                "name": "real",
                "mode": "real",
                "supported": False,
                "runnable": False,
                "requires_explicit_pr": True,
                "failure_reason": "controlled_retry_real_execution_adapter_not_supported",
            },
        },
        "real_adapter_supported": False,
        "real_adapter_runnable": False,
        "real_adapter_requires_explicit_pr": True,
        "real_execution_request_observed": False,
        "real_execution_request_rejected": 0,
        "real_preflight_observed": True,
        "real_preflight_blocked": 1,
        "real_approval_observed": True,
        "real_approval_records": 1,
        "real_linkage_complete": True,
        "real_preflight_orphans": 0,
        "real_approval_orphans": 0,
        "real_approval_transition_observed": True,
        "real_approval_transition_records": 1,
        "real_approval_latest_status": "approved",
        "real_approval_transition_enabled": 0,
        "real_approval_transition_subprocess_enabled": 0,
        "real_approval_transition_execution_performed": 0,
        "real_approval_transition_subprocess_invoked": 0,
        "real_final_gate_observed": True,
        "real_final_gate_blocked": 1,
        "real_dry_run_envelope_observed": True,
        "real_dry_run_envelope_records": 1,
        "real_dry_run_envelope_would_execute": 0,
        "real_dry_run_envelope_ready": 0,
        "real_dry_run_envelope_real_execution_enabled": 0,
        "real_dry_run_envelope_subprocess_enabled": 0,
        "real_dry_run_envelope_execution_performed": 0,
        "real_dry_run_envelope_subprocess_invoked": 0,
        "real_dry_run_linkage_complete": True,
        "real_dry_run_envelope_orphans": 0,
        "real_noop_result_observed": True,
        "real_noop_result_records": 1,
        "real_noop_result_rendered_command_executed": 0,
        "real_noop_result_dry_run_command_executed": 0,
        "real_noop_result_real_execution_enabled": 0,
        "real_noop_result_subprocess_invoked": 1,
        "real_noop_result_execution_performed": 1,
        "real_noop_result_exit_code_zero": 1,
        "real_noop_linkage_complete": True,
        "real_noop_result_orphans": 0,
        "real_noop_result_stdout_marker_observed": 1,
        "real_read_only_promotion_observed": True,
        "real_read_only_promotion_records": 1,
        "real_read_only_promotion_linkage_complete": True,
        "real_read_only_promotion_orphans": 0,
        "real_read_only_promotion_candidate": 1,
        "real_read_only_promotion_command_parse_valid": 1,
        "real_read_only_promotion_stdout_marker_observed": 1,
        "real_read_only_promotion_noop_exit_code_zero": 1,
        "real_read_only_promotion_rendered_command_executed": 0,
        "real_read_only_promotion_dry_run_command_executed": 0,
        "real_read_only_promotion_real_execution_enabled": 0,
        "real_read_only_promotion_subprocess_invoked": 0,
        "real_read_only_promotion_execution_performed": 0,
        "real_read_only_final_gate_observed": True,
        "real_read_only_final_gate_records": 1,
        "real_read_only_final_gate_linkage_complete": True,
        "real_read_only_final_gate_orphans": 0,
        "real_read_only_final_gate_preconditions_satisfied": 1,
        "real_read_only_final_gate_ready": 0,
        "real_read_only_final_gate_would_execute": 0,
        "real_read_only_final_gate_read_only_execution_enabled": 0,
        "real_read_only_final_gate_real_execution_enabled": 0,
        "real_read_only_final_gate_subprocess_enabled": 0,
        "real_read_only_final_gate_subprocess_invoked": 0,
        "real_read_only_final_gate_execution_performed": 0,
        "real_read_only_final_gate_rendered_command_executed": 0,
        "real_read_only_final_gate_dry_run_command_executed": 0,
        "real_read_only_approval_observed": True,
        "real_read_only_approval_records": 1,
        "real_read_only_approval_linkage_complete": True,
        "real_read_only_approval_orphans": 0,
        "real_read_only_approval_pending": 1,
        "real_read_only_approval_read_only_execution_enabled": 0,
        "real_read_only_approval_real_execution_enabled": 0,
        "real_read_only_approval_subprocess_enabled": 0,
        "real_read_only_approval_subprocess_invoked": 0,
        "real_read_only_approval_execution_performed": 0,
        "real_read_only_approval_rendered_command_executed": 0,
        "real_read_only_approval_dry_run_command_executed": 0,
        "real_read_only_approval_transition_observed": True,
        "real_read_only_approval_transition_records": 1,
        "real_read_only_approval_transition_linkage_complete": True,
        "real_read_only_approval_transition_orphans": 0,
        "real_read_only_approval_latest_status": "approved",
        "real_read_only_approval_transition_from_pending": 1,
        "real_read_only_approval_transition_approved": 1,
        "real_read_only_approval_transition_rejected": 0,
        "real_read_only_approval_transition_read_only_execution_enabled": 0,
        "real_read_only_approval_transition_real_execution_enabled": 0,
        "real_read_only_approval_transition_subprocess_enabled": 0,
        "real_read_only_approval_transition_subprocess_invoked": 0,
        "real_read_only_approval_transition_execution_performed": 0,
        "real_read_only_approval_transition_rendered_command_executed": 0,
        "real_read_only_approval_transition_dry_run_command_executed": 0,
        "real_read_only_readiness_gate_observed": True,
        "real_read_only_readiness_gate_records": 1,
        "real_read_only_readiness_gate_linkage_complete": True,
        "real_read_only_readiness_gate_orphans": 0,
        "real_read_only_readiness_gate_satisfied": 1,
        "real_read_only_readiness_gate_ready": 1,
        "real_read_only_readiness_gate_read_only_execution_enabled": 0,
        "real_read_only_readiness_gate_real_execution_enabled": 0,
        "real_read_only_readiness_gate_subprocess_enabled": 0,
        "real_read_only_readiness_gate_subprocess_invoked": 0,
        "real_read_only_readiness_gate_execution_performed": 0,
        "real_read_only_readiness_gate_rendered_command_executed": 0,
        "real_read_only_readiness_gate_dry_run_command_executed": 0,
        "real_read_only_execution_result_observed": True,
        "real_read_only_execution_result_records": 1,
        "real_read_only_execution_result_failed": 1,
        "real_read_only_execution_result_executed": 0,
        "real_read_only_execution_result_rejected": 0,
        "real_read_only_execution_result_exit_code_1": 1,
        "real_read_only_execution_result_linkage_complete": True,
        "real_read_only_execution_result_orphans": 0,
        "real_read_only_execution_result_validation_reasons_empty": 1,
        "real_read_only_execution_result_operator_authorized": 1,
        "real_read_only_execution_result_allow_guarded": 1,
        "real_read_only_execution_result_read_only_execution_enabled": 1,
        "real_read_only_execution_result_real_execution_enabled": 0,
        "real_read_only_execution_result_subprocess_invoked": 1,
        "real_read_only_execution_result_execution_performed": 1,
        "real_read_only_execution_result_read_only_command_executed": 1,
        "real_read_only_execution_result_rendered_command_executed": 1,
        "real_read_only_execution_result_dry_run_command_executed": 1,
        "real_read_only_feedback_observed": True,
        "real_read_only_feedback_records": 1,
        "real_read_only_feedback_linkage_complete": True,
        "real_read_only_feedback_orphans": 0,
        "real_read_only_feedback_actionable": 1,
        "real_read_only_feedback_source_failed": 1,
        "real_read_only_feedback_source_exit_code_1": 1,
        "real_read_only_feedback_next_action_investigate": 1,
        "real_read_only_feedback_execution_observed": 1,
        "real_read_only_feedback_failed": 1,
        "real_read_only_feedback_real_execution_enabled": 0,
        "real_read_only_feedback_feedback_execution_performed": 0,
        "real_read_only_feedback_feedback_subprocess_invoked": 0,
        "real_read_only_feedback_execution_performed": 0,
        "real_read_only_feedback_subprocess_invoked": 0,
        "real_read_only_repair_plan_observed": True,
        "real_read_only_repair_plan_records": 1,
        "real_read_only_repair_plan_linkage_complete": True,
        "real_read_only_repair_plan_orphans": 0,
        "real_read_only_repair_plan_planned": 1,
        "real_read_only_repair_plan_source_actionable": 1,
        "real_read_only_repair_plan_source_failed": 1,
        "real_read_only_repair_plan_source_exit_code_1": 1,
        "real_read_only_repair_plan_next_action_review": 1,
        "real_read_only_repair_plan_requires_operator_review": 1,
        "real_read_only_repair_plan_repair_execution_enabled": 0,
        "real_read_only_repair_plan_real_execution_enabled": 0,
        "real_read_only_repair_plan_subprocess_enabled": 0,
        "real_read_only_repair_plan_repair_execution_performed": 0,
        "real_read_only_repair_plan_repair_subprocess_invoked": 0,
        "real_read_only_repair_plan_execution_performed": 0,
        "real_read_only_repair_plan_subprocess_invoked": 0,
        "real_read_only_repair_action_bundle_observed": True,
        "real_read_only_repair_action_bundle_records": 1,
        "real_read_only_repair_action_bundle_linkage_complete": True,
        "real_read_only_repair_action_bundle_orphans": 0,
        "real_read_only_repair_action_bundle_assembled": 1,
        "real_read_only_repair_action_bundle_source_planned": 1,
        "real_read_only_repair_action_bundle_source_actionable": 1,
        "real_read_only_repair_action_bundle_source_failed": 1,
        "real_read_only_repair_action_bundle_source_exit_code_1": 1,
        "real_read_only_repair_action_bundle_next_action_review": 1,
        "real_read_only_repair_action_bundle_requires_operator_review": 1,
        "real_read_only_repair_action_bundle_reviewed": 0,
        "real_read_only_repair_action_bundle_bundle_execution_enabled": 0,
        "real_read_only_repair_action_bundle_repair_execution_enabled": 0,
        "real_read_only_repair_action_bundle_real_execution_enabled": 0,
        "real_read_only_repair_action_bundle_subprocess_enabled": 0,
        "real_read_only_repair_action_bundle_bundle_execution_performed": 0,
        "real_read_only_repair_action_bundle_bundle_subprocess_invoked": 0,
        "real_read_only_repair_action_bundle_execution_performed": 0,
        "real_read_only_repair_action_bundle_subprocess_invoked": 0,
        "real_read_only_repair_action_bundle_review_observed": True,
        "real_read_only_repair_action_bundle_review_records": 1,
        "real_read_only_repair_action_bundle_review_linkage_complete": True,
        "real_read_only_repair_action_bundle_review_orphans": 0,
        "real_read_only_repair_action_bundle_review_approved_status": 1,
        "real_read_only_repair_action_bundle_review_source_assembled": 1,
        "real_read_only_repair_action_bundle_review_source_planned": 1,
        "real_read_only_repair_action_bundle_review_source_actionable": 1,
        "real_read_only_repair_action_bundle_review_source_failed": 1,
        "real_read_only_repair_action_bundle_review_source_exit_code_1": 1,
        "real_read_only_repair_action_bundle_review_source_item_count_9": 1,
        "real_read_only_repair_action_bundle_review_next_action_prepare": 1,
        "real_read_only_repair_action_bundle_review_operator_authorized": 1,
        "real_read_only_repair_action_bundle_review_reviewed": 1,
        "real_read_only_repair_action_bundle_review_approved": 1,
        "real_read_only_repair_action_bundle_review_bundle_execution_enabled": 0,
        "real_read_only_repair_action_bundle_review_repair_execution_enabled": 0,
        "real_read_only_repair_action_bundle_review_real_execution_enabled": 0,
        "real_read_only_repair_action_bundle_review_subprocess_enabled": 0,
        "real_read_only_repair_action_bundle_review_bundle_execution_performed": 0,
        "real_read_only_repair_action_bundle_review_bundle_subprocess_invoked": 0,
        "real_read_only_repair_action_bundle_review_execution_performed": 0,
        "real_read_only_repair_action_bundle_review_subprocess_invoked": 0,
        "real_repair_approval_observed": True,
        "real_repair_approval_records": 1,
        "real_repair_approval_linkage_complete": True,
        "real_repair_approval_orphans": 0,
        "real_repair_approval_pending": 1,
        "real_repair_approval_source_review_approved": 1,
        "real_repair_approval_next_action_await": 1,
        "real_repair_approval_operator_authorized": 1,
        "real_repair_approval_required": 1,
        "real_repair_approval_approved": 0,
        "real_repair_approval_repair_execution_enabled": 0,
        "real_repair_approval_real_execution_enabled": 0,
        "real_repair_approval_subprocess_enabled": 0,
        "real_repair_approval_repair_execution_performed": 0,
        "real_repair_approval_repair_subprocess_invoked": 0,
        "real_repair_approval_execution_performed": 0,
        "real_repair_approval_subprocess_invoked": 0,
        "real_repair_approval_transition_observed": True,
        "real_repair_approval_transition_records": 1,
        "real_repair_approval_transition_linkage_complete": True,
        "real_repair_approval_transition_orphans": 0,
        "real_repair_approval_transition_from_pending": 1,
        "real_repair_approval_transition_to_approved": 1,
        "real_repair_approval_transition_source_approval_pending": 1,
        "real_repair_approval_transition_next_action_final_gate": 1,
        "real_repair_approval_transition_operator_authorized": 1,
        "real_repair_approval_transition_required": 1,
        "real_repair_approval_transition_approved": 1,
        "real_repair_approval_transition_repair_execution_enabled": 0,
        "real_repair_approval_transition_real_execution_enabled": 0,
        "real_repair_approval_transition_subprocess_enabled": 0,
        "real_repair_approval_transition_repair_execution_performed": 0,
        "real_repair_approval_transition_repair_subprocess_invoked": 0,
        "real_repair_approval_transition_execution_performed": 0,
        "real_repair_approval_transition_subprocess_invoked": 0,
        "real_repair_final_gate_observed": True,
        "real_repair_final_gate_records": 1,
        "real_repair_final_gate_linkage_complete": True,
        "real_repair_final_gate_orphans": 0,
        "real_repair_final_gate_ready_blocked": 1,
        "real_repair_final_gate_preconditions_satisfied": 1,
        "real_repair_final_gate_ready": 0,
        "real_repair_final_gate_would_execute": 0,
        "real_repair_final_gate_next_action_dry_run_envelope": 1,
        "real_repair_final_gate_operator_authorized": 1,
        "real_repair_final_gate_transition_approved": 1,
        "real_repair_final_gate_repair_execution_enabled": 0,
        "real_repair_final_gate_real_execution_enabled": 0,
        "real_repair_final_gate_subprocess_enabled": 0,
        "real_repair_final_gate_repair_execution_performed": 0,
        "real_repair_final_gate_repair_subprocess_invoked": 0,
        "real_repair_final_gate_execution_performed": 0,
        "real_repair_final_gate_subprocess_invoked": 0,
        "checks": [],
        "exit_codes": {
            "trail": 0,
            "retry_observability": 0,
            "controlled_observability": 0,
            "real_execution": 1,
        },
    }

    result = validate_controlled_execution_readiness_report_schema(report)

    assert result == {
        "type": "controlled_execution_readiness_schema_validation",
        "valid": True,
        "schema_version": READINESS_SCHEMA_VERSION,
        "schema_kind": "controlled_execution_readiness",
        "reasons": [],
    }


def test_controlled_execution_readiness_observes_rejected_real_execution_request() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            controlled_execution_result_reasons={
                "real_execution_not_supported": 1,
            },
            controlled_real_execution_requested={
                "true": 1,
            },
            controlled_real_execution_performed={
                "false": 1,
            },
            controlled_real_execution_supported={
                "false": 1,
            },
            controlled_subprocess_invoked={
                "false": 1,
            },
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_execution_request_rejected_if_observed" not in failed
    assert "real_execution_request_did_not_execute" not in failed
    assert "real_execution_request_did_not_enable_support" not in failed
    assert "real_execution_request_did_not_invoke_subprocess" not in failed


def test_controlled_execution_readiness_fails_if_real_request_performed() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            controlled_execution_result_reasons={
                "real_execution_not_supported": 1,
            },
            controlled_real_execution_requested={
                "true": 1,
            },
            controlled_real_execution_performed={
                "true": 1,
            },
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_execution_request_did_not_execute" in failed


def test_controlled_execution_readiness_fails_if_real_preflight_executes() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_preflight_execution_performed={"true": 1},
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_preflight_does_not_execute" in failed


def test_controlled_execution_readiness_fails_if_real_approval_enables_execution() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_approval_enabled={"true": 1},
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_approval_does_not_enable_real_execution" in failed


def test_controlled_execution_readiness_fails_for_real_approval_orphan() -> None:
    trail_summary = _trail_summary(real_approval_orphans=1)
    trail_summary["counts"]["real_execution_approvals"] = 1

    checks = _build_checks(
        trail_summary=trail_summary,
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_approval_links_to_preflight" in failed


def test_controlled_execution_readiness_fails_for_real_preflight_orphan() -> None:
    trail_summary = _trail_summary(real_preflight_orphans=1)
    trail_summary["counts"]["real_execution_preflights"] = 1

    checks = _build_checks(
        trail_summary=trail_summary,
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_preflight_links_to_controlled_result" in failed


def test_controlled_execution_readiness_fails_for_real_dry_run_envelope_orphan() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_dry_run_envelope_orphans=1,
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_dry_run_envelope_links_to_final_gate" in failed


def test_controlled_execution_readiness_fails_for_real_noop_result_orphan() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_noop_result_orphans=1,
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_noop_result_links_to_dry_run_envelope" in failed


def test_controlled_execution_readiness_fails_without_real_noop_stdout_marker() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_noop_result_stdout_marker_observed={"false": 1},
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_noop_result_stdout_marker_observed" in failed


def test_controlled_execution_readiness_fails_for_read_only_promotion_orphan() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_read_only_promotion_orphans=1,
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_read_only_promotion_links_to_noop_result" in failed


def test_controlled_execution_readiness_fails_when_read_only_promotion_invokes_subprocess() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_read_only_promotion_subprocess_invoked={"true": 1},
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_read_only_promotion_does_not_invoke_subprocess" in failed


def test_controlled_execution_readiness_fails_for_read_only_final_gate_orphan() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_read_only_final_gate_orphans=1,
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_read_only_final_gate_links_to_promotion" in failed


def test_controlled_execution_readiness_fails_when_read_only_final_gate_invokes_subprocess() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_read_only_final_gate_subprocess_invoked={"true": 1},
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_read_only_final_gate_does_not_invoke_subprocess" in failed


def test_controlled_execution_readiness_fails_for_read_only_approval_orphan() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_read_only_approval_orphans=1,
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_read_only_approval_links_to_final_gate" in failed


def test_controlled_execution_readiness_fails_when_read_only_approval_invokes_subprocess() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_read_only_approval_subprocess_invoked={"true": 1},
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_read_only_approval_does_not_invoke_subprocess" in failed


def test_controlled_execution_readiness_fails_for_read_only_approval_transition_orphan() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_read_only_approval_transition_orphans=1,
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_read_only_approval_transition_links_to_approval" in failed


def test_controlled_execution_readiness_fails_when_read_only_approval_transition_invokes_subprocess() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_read_only_approval_transition_subprocess_invoked={"true": 1},
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_read_only_approval_transition_does_not_invoke_subprocess" in failed


def test_controlled_execution_readiness_fails_for_read_only_readiness_gate_orphan() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_read_only_readiness_gate_orphans=1,
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_read_only_readiness_gate_links_to_transition" in failed


def test_controlled_execution_readiness_fails_when_read_only_readiness_gate_invokes_subprocess() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_read_only_readiness_gate_subprocess_invoked={"true": 1},
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_read_only_readiness_gate_does_not_invoke_subprocess" in failed


def test_controlled_execution_readiness_fails_for_read_only_execution_result_orphan() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_read_only_execution_result_orphans=1,
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_read_only_execution_result_links_to_readiness_gate" in failed


def test_controlled_execution_readiness_fails_when_read_only_execution_result_enables_real_execution() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_read_only_execution_result_real_execution_enabled={"true": 1},
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_read_only_execution_result_did_not_enable_real_execution" in failed


def test_controlled_execution_readiness_fails_for_read_only_feedback_orphan() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_read_only_feedback_orphans=1,
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_read_only_feedback_links_to_execution_result" in failed


def test_controlled_execution_readiness_fails_when_read_only_feedback_executes() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_read_only_feedback_execution_performed={"true": 1},
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_read_only_feedback_did_not_execute" in failed


def test_controlled_execution_readiness_fails_for_read_only_repair_plan_orphan() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_read_only_repair_plan_orphans=1,
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_read_only_repair_plan_links_to_feedback" in failed


def test_controlled_execution_readiness_fails_when_read_only_repair_plan_executes() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_read_only_repair_plan_execution_performed={"true": 1},
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_read_only_repair_plan_did_not_execute" in failed


def test_controlled_execution_readiness_fails_for_read_only_repair_action_bundle_orphan() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_read_only_repair_action_bundle_orphans=1,
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_read_only_repair_action_bundle_links_to_repair_plan" in failed


def test_controlled_execution_readiness_fails_when_read_only_repair_action_bundle_executes() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_read_only_repair_action_bundle_execution_performed={"true": 1},
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_read_only_repair_action_bundle_did_not_execute" in failed


def test_controlled_execution_readiness_fails_for_read_only_repair_action_bundle_review_orphan() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_read_only_repair_action_bundle_review_orphans=1,
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_read_only_repair_action_bundle_review_links_to_bundle" in failed


def test_controlled_execution_readiness_fails_when_read_only_repair_action_bundle_review_executes() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_read_only_repair_action_bundle_review_execution_performed={
                "true": 1
            },
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_read_only_repair_action_bundle_review_did_not_execute" in failed


def test_controlled_execution_readiness_fails_for_real_repair_approval_orphan() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_repair_approval_orphans=1,
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_repair_approval_links_to_bundle_review" in failed


def test_controlled_execution_readiness_fails_when_real_repair_approval_enables_repair_execution() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_repair_approval_repair_execution_enabled={"true": 1},
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_repair_approval_did_not_enable_repair_execution" in failed


def test_controlled_execution_readiness_fails_for_real_repair_approval_transition_orphan() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_repair_approval_transition_orphans=1,
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_repair_approval_transition_links_to_repair_approval" in failed


def test_controlled_execution_readiness_fails_when_real_repair_approval_transition_enables_repair_execution() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_repair_approval_transition_repair_execution_enabled={"true": 1},
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert (
        "real_repair_approval_transition_did_not_enable_repair_execution"
        in failed
    )


def test_controlled_execution_readiness_fails_for_real_repair_final_gate_orphan() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_repair_final_gate_orphans=1,
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_repair_final_gate_links_to_transition" in failed


def test_controlled_execution_readiness_fails_when_real_repair_final_gate_enables_repair_execution() -> None:
    checks = _build_checks(
        trail_summary=_trail_summary(
            real_repair_final_gate_repair_execution_enabled={"true": 1},
        ),
        retry_observability=_retry_observability(),
        controlled_observability=_controlled_observability(),
        require_operator_authorized=True,
    )

    failed = [item["name"] for item in checks if item["status"] != "passed"]

    assert "real_repair_final_gate_did_not_enable_repair_execution" in failed