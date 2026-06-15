from src.testing.run_controlled_retry_guarded_repair_golden_path import (
    GOLDEN_PATH_SCHEMA_VERSION,
    build_controlled_retry_guarded_repair_golden_path_report,
)


def _summary(**overrides):
    required_types = {
        "replay_lifecycle_retry_proposal": 1,
        "replay_lifecycle_retry_approval": 1,
        "replay_lifecycle_retry_execution_plan": 1,
        "replay_lifecycle_retry_rendered_command": 1,
        "replay_lifecycle_retry_rendered_command_result": 1,
        "replay_lifecycle_retry_execution_eligibility": 1,
        "replay_lifecycle_retry_execution_result": 1,
        "replay_lifecycle_retry_controlled_execution_result": 1,
        "replay_lifecycle_retry_real_execution_preflight": 1,
        "replay_lifecycle_retry_real_execution_approval": 1,
        "replay_lifecycle_retry_real_execution_approval_transition": 1,
        "replay_lifecycle_retry_real_execution_final_gate": 1,
        "replay_lifecycle_retry_real_execution_dry_run_envelope": 1,
        "replay_lifecycle_retry_real_execution_noop_result": 1,
        "replay_lifecycle_retry_real_execution_read_only_promotion": 1,
        "replay_lifecycle_retry_real_execution_read_only_final_gate": 1,
        "replay_lifecycle_retry_real_execution_read_only_approval": 1,
        "replay_lifecycle_retry_real_execution_read_only_approval_transition": 1,
        "replay_lifecycle_retry_real_execution_read_only_readiness_gate": 1,
        "replay_lifecycle_retry_real_execution_read_only_execution_result": 1,
        "replay_lifecycle_retry_real_execution_read_only_feedback": 1,
        "replay_lifecycle_retry_real_execution_read_only_repair_plan": 1,
        "replay_lifecycle_retry_real_execution_read_only_repair_action_bundle": 1,
        "replay_lifecycle_retry_real_execution_read_only_repair_action_bundle_review": 1,
        "replay_lifecycle_retry_real_execution_repair_approval": 1,
        "replay_lifecycle_retry_real_execution_repair_approval_transition": 1,
        "replay_lifecycle_retry_real_execution_repair_final_gate": 1,
        "replay_lifecycle_retry_real_execution_repair_dry_run_envelope": 1,
        "replay_lifecycle_retry_real_execution_repair_noop_result": 1,
        "replay_lifecycle_retry_real_execution_repair_noop_feedback": 1,
        "replay_lifecycle_retry_real_execution_repair_readiness_gate": 1,
        "replay_lifecycle_retry_guarded_repair_execution_result": 1,
        "replay_lifecycle_retry_post_repair_evidence_check": 1,
    }
    item = {
        "type": "retry_governance_trail_summary",
        "total_records": 33,
        "by_type": required_types,
        "counts": {},
        "chain_complete": True,
        "missing_stages": [],
        "real_linkage_complete": True,
        "real_dry_run_linkage_complete": True,
        "real_noop_linkage_complete": True,
        "real_read_only_promotion_linkage_complete": True,
        "real_read_only_final_gate_linkage_complete": True,
        "real_read_only_approval_linkage_complete": True,
        "real_read_only_approval_transition_linkage_complete": True,
        "real_read_only_readiness_gate_linkage_complete": True,
        "real_read_only_execution_result_linkage_complete": True,
        "real_read_only_feedback_linkage_complete": True,
        "real_read_only_repair_plan_linkage_complete": True,
        "real_read_only_repair_action_bundle_linkage_complete": True,
        "real_read_only_repair_action_bundle_review_linkage_complete": True,
        "real_repair_approval_linkage_complete": True,
        "real_repair_approval_transition_linkage_complete": True,
        "real_repair_final_gate_linkage_complete": True,
        "real_repair_dry_run_envelope_linkage_complete": True,
        "real_repair_noop_result_linkage_complete": True,
        "real_repair_noop_feedback_linkage_complete": True,
        "real_repair_readiness_gate_linkage_complete": True,
        "guarded_repair_execution_linkage_complete": True,
        "post_repair_evidence_linkage_complete": True,
        "post_repair_evidence_orphans": 0,
        "guarded_repair_execution_statuses": {"succeeded": 1},
        "guarded_repair_execution_allowed": {"true": 1},
        "guarded_repair_execution_marker_observed": {"true": 1},
        "guarded_repair_execution_exit_codes": {"0": 1},
        "guarded_repair_execution_target_counts": {"9": 1},
        "guarded_repair_execution_next_actions": {
            "run_post_repair_evidence_check": 1
        },
        "guarded_repair_execution_repair_actions_executed": {"true": 1},
        "guarded_repair_execution_repair_execution_enabled": {"true": 1},
        "guarded_repair_execution_real_execution_enabled": {"false": 1},
        "guarded_repair_execution_rendered_command_executed": {"false": 1},
        "guarded_repair_execution_dry_run_command_executed": {"false": 1},
        "post_repair_evidence_statuses": {"passed": 1},
        "post_repair_evidence_allowed": {"true": 1},
        "post_repair_evidence_enabled": {"true": 1},
        "post_repair_evidence_marker_observed": {"true": 1},
        "post_repair_evidence_exit_codes": {"0": 1},
        "post_repair_evidence_outcome_verified": {"true": 1},
        "post_repair_evidence_expected_counts": {"9": 1},
        "post_repair_evidence_verified_counts": {"9": 1},
        "post_repair_evidence_missing_counts": {"0": 1},
        "post_repair_evidence_unexpected_counts": {"0": 1},
        "post_repair_evidence_next_actions": {"close_repair_loop": 1},
        "post_repair_evidence_source_statuses": {"succeeded": 1},
        "post_repair_evidence_source_repair_execution_enabled": {"true": 1},
        "post_repair_evidence_source_real_execution_enabled": {"false": 1},
        "post_repair_evidence_repair_execution_enabled": {"false": 1},
        "post_repair_evidence_real_execution_enabled": {"false": 1},
        "post_repair_evidence_repair_execution_performed": {"false": 1},
        "post_repair_evidence_repair_subprocess_invoked": {"false": 1},
    }
    item.update(overrides)
    return item


def test_golden_path_report_passes_verified_summary() -> None:
    report = build_controlled_retry_guarded_repair_golden_path_report(
        _summary(),
        proposal_id="replay-retry-real-observe-smoke-1",
    )

    assert report["type"] == "controlled_retry_guarded_repair_golden_path_report"
    assert report["schema_version"] == GOLDEN_PATH_SCHEMA_VERSION
    assert report["status"] == "passed"
    assert report["golden_path_status"] == "passed"
    assert report["proposal_id"] == "replay-retry-real-observe-smoke-1"
    assert report["post_repair_status"] == "passed"
    assert report["repair_outcome_verified"] is True
    assert report["recommended_next_action"] == "close_repair_loop"
    assert report["ready_for_real_execution"] is False
    assert report["real_execution_enabled"] is False
    assert report["failed_check_count"] == 0


def test_golden_path_report_fails_missing_required_type() -> None:
    summary = _summary()
    summary["by_type"] = dict(summary["by_type"])
    summary["by_type"].pop("replay_lifecycle_retry_post_repair_evidence_check")

    report = build_controlled_retry_guarded_repair_golden_path_report(summary)

    assert report["status"] == "failed"
    failed_names = [item["name"] for item in report["failed_checks"]]
    assert "required_record_type_present:post-repair evidence check" in failed_names


def test_golden_path_report_fails_broken_post_repair_linkage() -> None:
    report = build_controlled_retry_guarded_repair_golden_path_report(
        _summary(
            post_repair_evidence_linkage_complete=False,
            post_repair_evidence_orphans=1,
        )
    )

    assert report["status"] == "failed"
    failed_names = [item["name"] for item in report["failed_checks"]]
    assert "post_repair_evidence_linkage_complete" in failed_names


def test_golden_path_report_fails_when_repair_outcome_not_verified() -> None:
    report = build_controlled_retry_guarded_repair_golden_path_report(
        _summary(post_repair_evidence_outcome_verified={"false": 1})
    )

    assert report["status"] == "failed"
    failed_names = [item["name"] for item in report["failed_checks"]]
    assert "post_repair_evidence_outcome_verified" in failed_names
    assert report["repair_outcome_verified"] is False


def test_golden_path_report_fails_when_post_repair_missing_targets() -> None:
    report = build_controlled_retry_guarded_repair_golden_path_report(
        _summary(post_repair_evidence_missing_counts={"1": 1})
    )

    assert report["status"] == "failed"
    failed_names = [item["name"] for item in report["failed_checks"]]
    assert "post_repair_evidence_no_missing_targets" in failed_names


def test_golden_path_report_fails_when_real_execution_enabled() -> None:
    report = build_controlled_retry_guarded_repair_golden_path_report(
        _summary(post_repair_evidence_real_execution_enabled={"true": 1})
    )

    assert report["status"] == "failed"
    failed_names = [item["name"] for item in report["failed_checks"]]
    assert "post_repair_evidence_did_not_enable_real_execution" in failed_names