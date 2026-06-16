from src.security.directive_validation import (
    validate_evidence_record,
    validate_runtime_evidence_memory_record,
    validate_runtime_record,
    validate_swarm_directive,
    validate_swarm_directive_result,
)

from src.swarms.security.runtime_validation import (
    validate_replay_evidence_lifecycle_result,
    build_security_validation_heartbeat_metrics,
    validate_replay_lifecycle_retry_proposal,
    validate_replay_lifecycle_retry_approval,
    validate_replay_lifecycle_retry_execution_plan,
    validate_replay_lifecycle_retry_execution_result,
    validate_replay_lifecycle_retry_rendered_command,
    validate_replay_lifecycle_retry_rendered_command_result,
    validate_replay_lifecycle_retry_execution_eligibility,
    validate_replay_lifecycle_retry_controlled_execution_result,
    validate_replay_lifecycle_retry_mock_execution_summary,
    validate_replay_lifecycle_retry_real_execution_preflight,
    validate_replay_lifecycle_retry_real_execution_approval,
    validate_replay_lifecycle_retry_real_execution_approval_transition,
    validate_replay_lifecycle_retry_real_execution_final_gate,
    validate_replay_lifecycle_retry_real_execution_dry_run_envelope,
    validate_replay_lifecycle_retry_real_execution_noop_result,
    validate_replay_lifecycle_retry_real_execution_read_only_promotion,
    validate_replay_lifecycle_retry_real_execution_read_only_final_gate,
    validate_replay_lifecycle_retry_real_execution_read_only_approval,
    validate_replay_lifecycle_retry_real_execution_read_only_approval_transition,
    validate_replay_lifecycle_retry_real_execution_read_only_readiness_gate,
    validate_replay_lifecycle_retry_real_execution_read_only_execution_result,
    validate_replay_lifecycle_retry_real_execution_read_only_feedback,
    validate_replay_lifecycle_retry_real_execution_read_only_repair_plan,
    validate_replay_lifecycle_retry_real_execution_read_only_repair_action_bundle,
    validate_replay_lifecycle_retry_real_execution_read_only_repair_action_bundle_review,
    validate_replay_lifecycle_retry_real_execution_repair_approval,
    validate_replay_lifecycle_retry_real_execution_repair_approval_transition,
    validate_replay_lifecycle_retry_real_execution_repair_dry_run_envelope,
    validate_replay_lifecycle_retry_real_execution_repair_noop_result,
    validate_replay_lifecycle_retry_real_execution_repair_noop_feedback,
    validate_replay_lifecycle_retry_real_execution_repair_readiness_gate,
    validate_replay_lifecycle_retry_real_execution_sandbox_adapter_scaffold,
    validate_replay_lifecycle_retry_real_execution_sandbox_adapter_request_preflight,
)


def test_validate_safe_swarm_directive() -> None:
    result = validate_swarm_directive(
        {
            "type": "swarm_directive",
            "directive_id": "dir-1",
            "action": "REDUCE_RISK",
            "source": "overseer",
            "target_type": "swarm",
            "target": "trade",
            "payload": {
                "dry_run": True,
                "execution_enabled": False,
            },
        }
    )

    assert result.valid is True
    assert result.severity == "info"
    assert result.reasons == []


def test_validate_swarm_directive_rejects_live_execution_enable() -> None:
    result = validate_swarm_directive(
        {
            "type": "swarm_directive",
            "directive_id": "dir-unsafe",
            "action": "SET_DRY_RUN",
            "source": "overseer",
            "target_type": "swarm",
            "target": "trade",
            "payload": {
                "dry_run": False,
                "execution_enabled": True,
            },
        }
    )

    assert result.valid is False
    assert result.severity == "critical"
    assert "execution_enabled_not_allowed" in result.reasons


def test_validate_swarm_directive_rejects_unknown_action() -> None:
    result = validate_swarm_directive(
        {
            "type": "swarm_directive",
            "directive_id": "dir-bad",
            "action": "ENABLE_LIVE_TRADING",
            "source": "overseer",
            "target_type": "swarm",
            "target": "trade",
            "payload": {},
        }
    )

    assert result.valid is False
    assert "unsafe_or_unknown_action" in result.reasons


def test_validate_swarm_directive_result() -> None:
    result = validate_swarm_directive_result(
        {
            "type": "swarm_directive_result",
            "directive_id": "dir-1",
            "status": "applied",
            "source": "trade-1",
            "swarm": "trade",
        }
    )

    assert result.valid is True


def test_validate_evidence_record() -> None:
    result = validate_evidence_record(
        {
            "type": "evidence_record",
            "evidence_id": "ev-1",
            "subject": "runtime_directive_seed_check",
            "status": "passed",
            "checks": [
                {"name": "directive_seeded", "status": "passed"},
                {"name": "directive_applied", "status": "passed"},
            ],
        }
    )

    assert result.valid is True


def test_validate_runtime_evidence_memory_record() -> None:
    result = validate_runtime_evidence_memory_record(
        {
            "type": "memory_record",
            "memory_id": "mem-1",
            "kind": "runtime_evidence",
            "status": "passed",
            "payload": {
                "evidence_id": "ev-1",
                "directive_id": "dir-1",
                "checks": [
                    {"name": "directive_seeded", "status": "passed"},
                ],
            },
        }
    )

    assert result.valid is True


def test_validate_runtime_record_dispatches_by_type() -> None:
    result = validate_runtime_record(
        {
            "type": "evidence_record",
            "evidence_id": "ev-1",
            "subject": "runtime_directive_seed_check",
            "status": "passed",
            "checks": [],
        }
    )

    assert result.valid is True
    assert result.record_type == "evidence_record"


def test_validate_runtime_record_rejects_unsupported_type() -> None:
    result = validate_runtime_record({"type": "unknown"})

    assert result.valid is False
    assert result.severity == "warning"
    assert "unsupported_record_type" in result.reasons


def test_validate_run_replay_directive_requires_simulation_dry_run_and_scenario_id() -> None:
    result = validate_swarm_directive(
        {
            "type": "swarm_directive",
            "directive_id": "run-replay-1",
            "action": "RUN_REPLAY",
            "source": "overseer",
            "target_type": "swarm",
            "target": "simulation",
            "payload": {
                "scenario_id": "replay-runtime-reduce-risk-1",
                "dry_run": True,
            },
        }
    )

    assert result.valid is True


def test_validate_run_replay_directive_rejects_non_dry_run() -> None:
    result = validate_swarm_directive(
        {
            "type": "swarm_directive",
            "directive_id": "run-replay-unsafe",
            "action": "RUN_REPLAY",
            "source": "overseer",
            "target_type": "swarm",
            "target": "simulation",
            "payload": {
                "scenario_id": "replay-runtime-reduce-risk-1",
                "dry_run": False,
            },
        }
    )

    assert result.valid is False
    assert "run_replay_requires_dry_run" in result.reasons


def test_validate_run_replay_directive_rejects_wrong_target() -> None:
    result = validate_swarm_directive(
        {
            "type": "swarm_directive",
            "directive_id": "run-replay-wrong-target",
            "action": "RUN_REPLAY",
            "source": "overseer",
            "target_type": "swarm",
            "target": "trade",
            "payload": {
                "scenario_id": "replay-runtime-reduce-risk-1",
                "dry_run": True,
            },
        }
    )

    assert result.valid is False
    assert "run_replay_requires_simulation_target" in result.reasons


def test_validate_replay_evidence_lifecycle_result_accepts_passed_result() -> None:
    result = validate_replay_evidence_lifecycle_result(
        {
            "type": "replay_evidence_lifecycle_result",
            "status": "passed",
            "scenario_id": "replay-runtime-reduce-risk-1",
            "directive_id": "runtime-run-replay-e2e-result-1",
            "checks": [
                {"name": "scenario_seeded", "status": "passed", "value": True},
                {"name": "memory_record_published", "status": "passed", "value": 1},
            ],
        }
    )

    assert result["valid"] is True
    assert result["record_type"] == "replay_evidence_lifecycle_result"
    assert result["severity"] == "info"


def test_validate_replay_evidence_lifecycle_result_rejects_passed_result_with_failed_check() -> None:
    result = validate_replay_evidence_lifecycle_result(
        {
            "type": "replay_evidence_lifecycle_result",
            "status": "passed",
            "scenario_id": "replay-runtime-reduce-risk-1",
            "directive_id": "runtime-run-replay-e2e-result-1",
            "checks": [
                {"name": "execution_published", "status": "failed", "value": None},
            ],
        }
    )

    assert result["valid"] is False
    assert result["severity"] == "critical"
    assert "passed_result_contains_failed_checks" in result["reasons"]


def test_validate_replay_evidence_lifecycle_result_accepts_failed_result_with_failed_check() -> None:
    result = validate_replay_evidence_lifecycle_result(
        {
            "type": "replay_evidence_lifecycle_result",
            "status": "failed",
            "scenario_id": "replay-runtime-reduce-risk-1",
            "directive_id": "runtime-run-replay-e2e-result-1",
            "checks": [
                {"name": "execution_published", "status": "failed", "value": None},
            ],
        }
    )

    assert result["valid"] is True
    assert result["severity"] == "info"


def test_validate_replay_evidence_lifecycle_result_marks_timeout_failure_as_warning() -> None:
    result = validate_replay_evidence_lifecycle_result(
        {
            "type": "replay_evidence_lifecycle_result",
            "status": "failed",
            "scenario_id": "replay-runtime-reduce-risk-timeout-1",
            "directive_id": "runtime-run-replay-timeout-1",
            "checks": [
                {
                    "name": "execution_published",
                    "status": "failed",
                    "value": None,
                },
            ],
            "payload": {
                "failure_reason": "execution_not_observed_before_timeout",
            },
        }
    )

    assert result["valid"] is True
    assert result["severity"] == "warning"
    assert "execution_not_observed_before_timeout" in result["reasons"]


def test_validate_replay_evidence_lifecycle_result_rejects_passed_result_with_failure_reason() -> None:
    result = validate_replay_evidence_lifecycle_result(
        {
            "type": "replay_evidence_lifecycle_result",
            "status": "passed",
            "scenario_id": "replay-runtime-reduce-risk-1",
            "directive_id": "runtime-run-replay-ok-1",
            "checks": [
                {
                    "name": "execution_published",
                    "status": "passed",
                    "value": "completed",
                },
            ],
            "payload": {
                "failure_reason": "execution_not_observed_before_timeout",
            },
        }
    )

    assert result["valid"] is False
    assert result["severity"] == "critical"
    assert "passed_result_contains_failure_reason" in result["reasons"]


def test_security_validation_metrics_reports_warning_reasons_for_lifecycle_timeout() -> None:
    metrics = build_security_validation_heartbeat_metrics(
        [
            {
                "type": "replay_evidence_lifecycle_result",
                "status": "failed",
                "scenario_id": "replay-runtime-reduce-risk-timeout-2",
                "directive_id": "runtime-run-replay-timeout-2",
                "checks": [
                    {
                        "name": "execution_published",
                        "status": "failed",
                        "value": None,
                    },
                ],
                "payload": {
                    "failure_reason": "execution_not_observed_before_timeout",
                },
            }
        ]
    )

    assert metrics["security_validation_records"] == 1
    assert metrics["security_validation_valid_records"] == 1
    assert metrics["security_validation_invalid_records"] == 0
    assert metrics["security_validation_severity_counts"]["warning"] == 1
    assert (
        metrics["security_validation_warning_reasons"][
            "execution_not_observed_before_timeout"
        ]
        == 1
    )


def _retry_proposal(**overrides):
    proposal = {
        "type": "replay_lifecycle_retry_proposal",
        "proposal_id": "replay-retry-test",
        "status": "pending",
        "source": "overseer-test",
        "recommendation": "retry_replay_lifecycle_check",
        "reason": "execution_not_observed_before_timeout",
        "timeout_profile": "standard",
        "command_template": (
            "python -m src.testing.run_replay_evidence_check "
            "--scenario-id <scenario_id> "
            "--action REDUCE_RISK "
            "--directive-id <new_directive_id> "
            "--timeout-profile standard "
            "--db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db"
        ),
        "payload": {
            "recommendation": "retry_replay_lifecycle_check",
            "reason": "execution_not_observed_before_timeout",
            "timeout_profile": "standard",
            "suggested_wait_seconds": 15.0,
            "suggested_poll_interval": 0.5,
        },
    }
    proposal.update(overrides)
    return proposal


def test_validate_replay_lifecycle_retry_proposal_accepts_pending_standard_retry() -> None:
    result = validate_replay_lifecycle_retry_proposal(_retry_proposal())

    assert result["valid"] is True
    assert result["severity"] == "info"
    assert result["record_type"] == "replay_lifecycle_retry_proposal"


def test_validate_replay_lifecycle_retry_proposal_rejects_non_pending_status() -> None:
    result = validate_replay_lifecycle_retry_proposal(
        _retry_proposal(status="approved")
    )

    assert result["valid"] is False
    assert result["severity"] == "critical"
    assert "non_pending_retry_proposal" in result["reasons"]


def test_validate_replay_lifecycle_retry_proposal_rejects_fast_profile() -> None:
    result = validate_replay_lifecycle_retry_proposal(
        _retry_proposal(timeout_profile="fast")
    )

    assert result["valid"] is False
    assert "invalid_timeout_profile" in result["reasons"]


def test_validate_replay_lifecycle_retry_proposal_rejects_missing_command_template() -> None:
    result = validate_replay_lifecycle_retry_proposal(
        _retry_proposal(command_template="")
    )

    assert result["valid"] is False
    assert "missing_command_template" in result["reasons"]

def test_security_validation_metrics_counts_retry_proposals() -> None:
    metrics = build_security_validation_heartbeat_metrics([_retry_proposal()])

    assert metrics["security_validation_records"] == 1
    assert metrics["security_validation_valid_records"] == 1
    assert metrics["security_validation_record_type_counts"]["replay_lifecycle_retry_proposal"] == 1


def _retry_approval(**overrides):
    approval = {
        "type": "replay_lifecycle_retry_approval",
        "approval_id": "replay-retry-approval-test",
        "proposal_id": "replay-retry-test",
        "status": "approved",
        "approved_by": "operator",
        "decision_mode": "manual",
        "source": "overseer-test",
        "reason": "retry_with_standard_timeout",
        "execution_enabled": False,
        "payload": {
            "proposal_id": "replay-retry-test",
            "timeout_profile": "standard",
            "decision_mode": "manual",
            "command_template": (
                "python -m src.testing.run_replay_evidence_check "
                "--scenario-id <scenario_id> "
                "--action REDUCE_RISK "
                "--directive-id <new_directive_id> "
                "--timeout-profile standard "
                "--db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db"
            ),
        },
    }
    approval.update(overrides)
    return approval


def test_validate_replay_lifecycle_retry_approval_accepts_safe_approval() -> None:
    result = validate_replay_lifecycle_retry_approval(_retry_approval())

    assert result["valid"] is True
    assert result["severity"] == "info"
    assert result["record_type"] == "replay_lifecycle_retry_approval"
    assert result["decision_mode"] == "manual"


def test_validate_replay_lifecycle_retry_approval_rejects_execution_enabled() -> None:
    result = validate_replay_lifecycle_retry_approval(
        _retry_approval(execution_enabled=True)
    )

    assert result["valid"] is False
    assert result["severity"] == "critical"
    assert "approval_execution_enabled_before_runner" in result["reasons"]


def test_validate_replay_lifecycle_retry_approval_rejects_missing_approved_by() -> None:
    result = validate_replay_lifecycle_retry_approval(
        _retry_approval(approved_by="")
    )

    assert result["valid"] is False
    assert "missing_approved_by" in result["reasons"]


def test_validate_replay_lifecycle_retry_approval_rejects_invalid_timeout_profile() -> None:
    approval = _retry_approval()
    approval["payload"]["timeout_profile"] = "fast"

    result = validate_replay_lifecycle_retry_approval(approval)

    assert result["valid"] is False
    assert "invalid_approval_timeout_profile" in result["reasons"]


def test_security_validation_metrics_counts_retry_approvals() -> None:
    metrics = build_security_validation_heartbeat_metrics([_retry_approval()])

    assert metrics["security_validation_records"] == 1
    assert metrics["security_validation_valid_records"] == 1
    assert (
        metrics["security_validation_record_type_counts"][
            "replay_lifecycle_retry_approval"
        ]
        == 1
    )


def test_validate_replay_lifecycle_retry_approval_accepts_policy_decision_mode() -> None:
    approval = _retry_approval(decision_mode="policy")
    approval["payload"]["decision_mode"] = "policy"

    result = validate_replay_lifecycle_retry_approval(approval)

    assert result["valid"] is True


def test_validate_replay_lifecycle_retry_approval_rejects_autonomous_decision_mode() -> None:
    approval = _retry_approval(decision_mode="autonomous")
    approval["payload"]["decision_mode"] = "autonomous"

    result = validate_replay_lifecycle_retry_approval(approval)

    assert result["valid"] is False
    assert "invalid_approval_decision_mode" in result["reasons"]


def test_validate_replay_lifecycle_retry_approval_rejects_payload_decision_mode_mismatch() -> None:
    approval = _retry_approval(decision_mode="manual")
    approval["payload"]["decision_mode"] = "policy"

    result = validate_replay_lifecycle_retry_approval(approval)

    assert result["valid"] is False
    assert "payload_decision_mode_mismatch" in result["reasons"]


def test_security_validation_metrics_reports_retry_approval_decision_modes() -> None:
    manual = _retry_approval(decision_mode="manual")
    manual["payload"]["decision_mode"] = "manual"

    policy = _retry_approval(
        approval_id="replay-retry-approval-policy",
        decision_mode="policy",
        approved_by="policy-engine",
    )
    policy["payload"]["decision_mode"] = "policy"

    metrics = build_security_validation_heartbeat_metrics([manual, policy])

    assert metrics["security_validation_retry_approval_decision_modes"]["manual"] == 1
    assert metrics["security_validation_retry_approval_decision_modes"]["policy"] == 1


def _retry_execution_plan(**overrides):
    plan = {
        "type": "replay_lifecycle_retry_execution_plan",
        "plan_id": "replay-retry-plan-test",
        "proposal_id": "replay-retry-test",
        "approval_id": "replay-retry-approval-test",
        "status": "planned",
        "source": "overseer-test",
        "execution_enabled": False,
        "timeout_profile": "standard",
        "decision_mode": "manual",
        "command_template": (
            "python -m src.testing.run_replay_evidence_check "
            "--scenario-id <scenario_id> "
            "--action REDUCE_RISK "
            "--directive-id <new_directive_id> "
            "--timeout-profile standard "
            "--db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db"
        ),
        "payload": {
            "proposal_id": "replay-retry-test",
            "approval_id": "replay-retry-approval-test",
            "timeout_profile": "standard",
            "decision_mode": "manual",
            "command_template": (
                "python -m src.testing.run_replay_evidence_check "
                "--scenario-id <scenario_id> "
                "--action REDUCE_RISK "
                "--directive-id <new_directive_id> "
                "--timeout-profile standard "
                "--db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db"
            ),
        },
    }
    plan.update(overrides)
    return plan


def test_validate_replay_lifecycle_retry_execution_plan_accepts_safe_plan() -> None:
    result = validate_replay_lifecycle_retry_execution_plan(_retry_execution_plan())

    assert result["valid"] is True
    assert result["severity"] == "info"
    assert result["record_type"] == "replay_lifecycle_retry_execution_plan"
    assert result["decision_mode"] == "manual"


def test_validate_replay_lifecycle_retry_execution_plan_rejects_execution_enabled() -> None:
    result = validate_replay_lifecycle_retry_execution_plan(
        _retry_execution_plan(execution_enabled=True)
    )

    assert result["valid"] is False
    assert "retry_plan_execution_enabled_before_runner" in result["reasons"]


def test_validate_replay_lifecycle_retry_execution_plan_rejects_fast_profile() -> None:
    result = validate_replay_lifecycle_retry_execution_plan(
        _retry_execution_plan(timeout_profile="fast")
    )

    assert result["valid"] is False
    assert "invalid_retry_plan_timeout_profile" in result["reasons"]


def test_validate_replay_lifecycle_retry_execution_plan_rejects_autonomous_decision_mode() -> None:
    result = validate_replay_lifecycle_retry_execution_plan(
        _retry_execution_plan(decision_mode="autonomous")
    )

    assert result["valid"] is False
    assert "invalid_retry_plan_decision_mode" in result["reasons"]


def test_validate_replay_lifecycle_retry_execution_plan_rejects_payload_mismatch() -> None:
    plan = _retry_execution_plan()
    plan["payload"]["approval_id"] = "other-approval"

    result = validate_replay_lifecycle_retry_execution_plan(plan)

    assert result["valid"] is False
    assert "payload_approval_id_mismatch" in result["reasons"]


def test_security_validation_metrics_counts_retry_execution_plans() -> None:
    metrics = build_security_validation_heartbeat_metrics([_retry_execution_plan()])

    assert metrics["security_validation_records"] == 1
    assert metrics["security_validation_valid_records"] == 1
    assert (
        metrics["security_validation_record_type_counts"][
            "replay_lifecycle_retry_execution_plan"
        ]
        == 1
    )


def _retry_execution_result(**overrides):
    result = {
        "type": "replay_lifecycle_retry_execution_result",
        "result_id": "replay-retry-result-test",
        "plan_id": "replay-retry-plan-test",
        "proposal_id": "replay-retry-proposal-test",
        "approval_id": "replay-retry-approval-test",
        "status": "skipped",
        "reason": "execution_disabled",
        "source": "retry-plan-runner-test",
        "execution_enabled": False,
        "payload": {
            "plan_id": "replay-retry-plan-test",
            "proposal_id": "replay-retry-proposal-test",
            "approval_id": "replay-retry-approval-test",
            "timeout_profile": "standard",
            "decision_mode": "manual",
            "execution_enabled": False,
            "executed": False,
        },
    }
    result.update(overrides)
    return result


def test_validate_replay_lifecycle_retry_execution_result_accepts_skipped_disabled() -> None:
    result = validate_replay_lifecycle_retry_execution_result(_retry_execution_result())

    assert result["valid"] is True
    assert result["severity"] == "info"
    assert result["record_type"] == "replay_lifecycle_retry_execution_result"


def test_validate_replay_lifecycle_retry_execution_result_accepts_rejected_enabled() -> None:
    result = validate_replay_lifecycle_retry_execution_result(
        _retry_execution_result(
            status="rejected",
            reason="execution_not_supported",
            execution_enabled=True,
            payload={
                "plan_id": "replay-retry-plan-test",
                "execution_enabled": True,
                "executed": False,
            },
        )
    )

    assert result["valid"] is True


def test_validate_replay_lifecycle_retry_execution_result_rejects_executed_true() -> None:
    record = _retry_execution_result()
    record["payload"]["executed"] = True

    result = validate_replay_lifecycle_retry_execution_result(record)

    assert result["valid"] is False
    assert "retry_execution_result_executed_before_runner_support" in result["reasons"]


def test_validate_replay_lifecycle_retry_execution_result_rejects_completed_status() -> None:
    result = validate_replay_lifecycle_retry_execution_result(
        _retry_execution_result(status="completed", reason="executed")
    )

    assert result["valid"] is False
    assert "invalid_retry_execution_result_status" in result["reasons"]


def test_validate_replay_lifecycle_retry_execution_result_rejects_payload_plan_mismatch() -> None:
    record = _retry_execution_result()
    record["payload"]["plan_id"] = "other-plan"

    result = validate_replay_lifecycle_retry_execution_result(record)

    assert result["valid"] is False
    assert "payload_plan_id_mismatch" in result["reasons"]


def test_security_validation_metrics_counts_retry_execution_results() -> None:
    metrics = build_security_validation_heartbeat_metrics([_retry_execution_result()])

    assert metrics["security_validation_records"] == 1
    assert metrics["security_validation_valid_records"] == 1
    assert (
        metrics["security_validation_record_type_counts"][
            "replay_lifecycle_retry_execution_result"
        ]
        == 1
    )


def test_security_validation_metrics_reports_retry_execution_result_statuses_and_reasons() -> None:
    skipped = _retry_execution_result(
        result_id="replay-retry-result-skipped",
        status="skipped",
        reason="execution_disabled",
    )
    rejected = _retry_execution_result(
        result_id="replay-retry-result-rejected",
        status="rejected",
        reason="execution_not_supported",
        execution_enabled=True,
        payload={
            "plan_id": "replay-retry-plan-test",
            "execution_enabled": True,
            "executed": False,
        },
    )

    metrics = build_security_validation_heartbeat_metrics([skipped, rejected])

    assert metrics["security_validation_retry_execution_result_statuses"]["skipped"] == 1
    assert metrics["security_validation_retry_execution_result_statuses"]["rejected"] == 1
    assert metrics["security_validation_retry_execution_result_reasons"]["execution_disabled"] == 1
    assert metrics["security_validation_retry_execution_result_reasons"]["execution_not_supported"] == 1


def _retry_rendered_command(**overrides):
    command = (
        "python -m src.testing.run_replay_evidence_check "
        "--scenario-id replay-render-test "
        "--action REDUCE_RISK "
        "--directive-id runtime-run-replay-render-test "
        "--timeout-profile standard "
        "--db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db"
    )
    record = {
        "type": "replay_lifecycle_retry_rendered_command",
        "rendered_command_id": "replay-retry-rendered-test",
        "plan_id": "replay-retry-plan-test",
        "proposal_id": "replay-retry-proposal-test",
        "approval_id": "replay-retry-approval-test",
        "status": "rendered",
        "source": "overseer-test",
        "execution_enabled": False,
        "scenario_id": "replay-render-test",
        "new_directive_id": "runtime-run-replay-render-test",
        "timeout_profile": "standard",
        "decision_mode": "manual",
        "command": command,
        "payload": {
            "plan_id": "replay-retry-plan-test",
            "proposal_id": "replay-retry-proposal-test",
            "approval_id": "replay-retry-approval-test",
            "scenario_id": "replay-render-test",
            "new_directive_id": "runtime-run-replay-render-test",
            "timeout_profile": "standard",
            "decision_mode": "manual",
            "command": command,
            "execution_enabled": False,
            "executed": False,
        },
    }
    record.update(overrides)
    return record


def test_validate_replay_lifecycle_retry_rendered_command_accepts_safe_command() -> None:
    result = validate_replay_lifecycle_retry_rendered_command(_retry_rendered_command())

    assert result["valid"] is True
    assert result["severity"] == "info"
    assert result["record_type"] == "replay_lifecycle_retry_rendered_command"
    assert result["timeout_profile"] == "standard"
    assert result["decision_mode"] == "manual"


def test_validate_replay_lifecycle_retry_rendered_command_rejects_execution_enabled() -> None:
    result = validate_replay_lifecycle_retry_rendered_command(
        _retry_rendered_command(execution_enabled=True)
    )

    assert result["valid"] is False
    assert "rendered_command_execution_enabled_before_runner" in result["reasons"]


def test_validate_replay_lifecycle_retry_rendered_command_rejects_payload_executed() -> None:
    record = _retry_rendered_command()
    record["payload"]["executed"] = True

    result = validate_replay_lifecycle_retry_rendered_command(record)

    assert result["valid"] is False
    assert "rendered_command_executed_before_runner" in result["reasons"]


def test_validate_replay_lifecycle_retry_rendered_command_rejects_unsafe_shell_syntax() -> None:
    result = validate_replay_lifecycle_retry_rendered_command(
        _retry_rendered_command(
            command=(
                "python -m src.testing.run_replay_evidence_check "
                "--scenario-id replay-render-test "
                "--directive-id runtime-run-replay-render-test "
                "--timeout-profile standard && echo bad"
            )
        )
    )

    assert result["valid"] is False
    assert "rendered_command_contains_unsafe_shell_syntax" in result["reasons"]


def test_validate_replay_lifecycle_retry_rendered_command_rejects_wrong_module() -> None:
    result = validate_replay_lifecycle_retry_rendered_command(
        _retry_rendered_command(
            command=(
                "python -m src.testing.other_helper "
                "--scenario-id replay-render-test "
                "--directive-id runtime-run-replay-render-test "
                "--timeout-profile standard"
            )
        )
    )

    assert result["valid"] is False
    assert "invalid_rendered_command_module" in result["reasons"]


def test_validate_replay_lifecycle_retry_rendered_command_rejects_missing_directive_id() -> None:
    result = validate_replay_lifecycle_retry_rendered_command(
        _retry_rendered_command(
            command=(
                "python -m src.testing.run_replay_evidence_check "
                "--scenario-id replay-render-test "
                "--timeout-profile standard"
            )
        )
    )

    assert result["valid"] is False
    assert "missing_rendered_command_directive_id" in result["reasons"]


def test_validate_replay_lifecycle_retry_rendered_command_rejects_timeout_profile_mismatch() -> None:
    result = validate_replay_lifecycle_retry_rendered_command(
        _retry_rendered_command(
            timeout_profile="patient",
            command=(
                "python -m src.testing.run_replay_evidence_check "
                "--scenario-id replay-render-test "
                "--directive-id runtime-run-replay-render-test "
                "--timeout-profile standard"
            ),
        )
    )

    assert result["valid"] is False
    assert "rendered_command_timeout_profile_mismatch" in result["reasons"]


def test_security_validation_metrics_counts_retry_rendered_commands() -> None:
    metrics = build_security_validation_heartbeat_metrics([_retry_rendered_command()])

    assert metrics["security_validation_records"] == 1
    assert metrics["security_validation_valid_records"] == 1
    assert (
        metrics["security_validation_record_type_counts"][
            "replay_lifecycle_retry_rendered_command"
        ]
        == 1
    )


def test_security_validation_metrics_reports_retry_rendered_command_profiles_and_modes() -> None:
    standard = _retry_rendered_command(
        rendered_command_id="rendered-standard",
        timeout_profile="standard",
        decision_mode="manual",
    )
    patient_command = standard["command"].replace(
        "--timeout-profile standard",
        "--timeout-profile patient",
    )
    patient = _retry_rendered_command(
        rendered_command_id="rendered-patient",
        timeout_profile="patient",
        decision_mode="policy",
        command=patient_command,
        payload={
            "plan_id": "replay-retry-plan-test",
            "timeout_profile": "patient",
            "decision_mode": "policy",
            "command": patient_command,
            "execution_enabled": False,
            "executed": False,
        },
    )

    metrics = build_security_validation_heartbeat_metrics([standard, patient])

    assert metrics["security_validation_retry_rendered_command_profiles"]["standard"] == 1
    assert metrics["security_validation_retry_rendered_command_profiles"]["patient"] == 1
    assert metrics["security_validation_retry_rendered_command_decision_modes"]["manual"] == 1
    assert metrics["security_validation_retry_rendered_command_decision_modes"]["policy"] == 1


def _retry_rendered_command_result(**overrides):
    command = (
        "python -m src.testing.run_replay_evidence_check "
        "--scenario-id replay-render-test "
        "--directive-id runtime-run-replay-render-test "
        "--timeout-profile standard"
    )
    record = {
        "type": "replay_lifecycle_retry_rendered_command_result",
        "rendered_command_result_id": "rendered-result-1",
        "rendered_command_id": "rendered-command-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "status": "skipped",
        "reason": "execution_disabled",
        "source": "runner-test",
        "execution_enabled": False,
        "timeout_profile": "standard",
        "decision_mode": "manual",
        "command": command,
        "payload": {
            "rendered_command_id": "rendered-command-1",
            "plan_id": "plan-1",
            "proposal_id": "proposal-1",
            "approval_id": "approval-1",
            "timeout_profile": "standard",
            "decision_mode": "manual",
            "command": command,
            "execution_enabled": False,
            "executed": False,
        },
    }
    record.update(overrides)
    return record

def test_validate_replay_lifecycle_retry_rendered_command_result_accepts_skipped_disabled() -> None:
    result = validate_replay_lifecycle_retry_rendered_command_result(
        _retry_rendered_command_result()
    )

    assert result["valid"] is True
    assert result["severity"] == "info"
    assert result["status"] == "skipped"
    assert result["reason"] == "execution_disabled"


def test_validate_replay_lifecycle_retry_rendered_command_result_accepts_rejected_enabled() -> None:
    record = _retry_rendered_command_result(
        status="rejected",
        reason="execution_not_supported",
        execution_enabled=True,
    )
    record["payload"]["execution_enabled"] = True

    result = validate_replay_lifecycle_retry_rendered_command_result(record)

    assert result["valid"] is True
    assert result["status"] == "rejected"
    assert result["reason"] == "execution_not_supported"


def test_validate_replay_lifecycle_retry_rendered_command_result_rejects_executed_payload() -> None:
    record = _retry_rendered_command_result()
    record["payload"]["executed"] = True

    result = validate_replay_lifecycle_retry_rendered_command_result(record)

    assert result["valid"] is False
    assert "rendered_command_result_executed_before_runner" in result["reasons"]


def test_validate_replay_lifecycle_retry_rendered_command_result_rejects_completed_status() -> None:
    result = validate_replay_lifecycle_retry_rendered_command_result(
        _retry_rendered_command_result(status="completed", reason="completed")
    )

    assert result["valid"] is False
    assert "invalid_rendered_command_result_status" in result["reasons"]


def test_validate_replay_lifecycle_retry_rendered_command_result_rejects_payload_command_mismatch() -> None:
    record = _retry_rendered_command_result()
    record["payload"]["command"] = "python -m other"

    result = validate_replay_lifecycle_retry_rendered_command_result(record)

    assert result["valid"] is False
    assert "payload_command_mismatch" in result["reasons"]


def test_security_validation_metrics_counts_retry_rendered_command_results() -> None:
    metrics = build_security_validation_heartbeat_metrics(
        [_retry_rendered_command_result()]
    )

    assert (
        metrics["security_validation_record_type_counts"][
            "replay_lifecycle_retry_rendered_command_result"
        ]
        == 1
    )
    assert metrics["security_validation_retry_rendered_command_result_statuses"]["skipped"] == 1
    assert (
        metrics["security_validation_retry_rendered_command_result_reasons"][
            "execution_disabled"
        ]
        == 1
    )


def _retry_execution_eligibility(**overrides):
    command = (
        "python -m src.testing.run_replay_evidence_check "
        "--scenario-id replay-render-test "
        "--directive-id runtime-run-replay-render-test "
        "--timeout-profile standard"
    )
    record = {
        "type": "replay_lifecycle_retry_execution_eligibility",
        "eligibility_id": "eligibility-1",
        "rendered_command_id": "rendered-command-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "status": "blocked",
        "reason": "execution_disabled",
        "source": "eligibility-test",
        "execution_supported": False,
        "execution_enabled": False,
        "timeout_profile": "standard",
        "decision_mode": "manual",
        "command": command,
        "payload": {
            "rendered_command_id": "rendered-command-1",
            "plan_id": "plan-1",
            "proposal_id": "proposal-1",
            "approval_id": "approval-1",
            "status": "blocked",
            "reason": "execution_disabled",
            "execution_supported": False,
            "execution_enabled": False,
            "executed": False,
            "timeout_profile": "standard",
            "decision_mode": "manual",
            "command": command,
        },
    }
    record.update(overrides)
    return record

def test_validate_replay_lifecycle_retry_execution_eligibility_accepts_blocked_disabled() -> None:
    result = validate_replay_lifecycle_retry_execution_eligibility(
        _retry_execution_eligibility()
    )

    assert result["valid"] is True
    assert result["severity"] == "info"
    assert result["status"] == "blocked"
    assert result["reason"] == "execution_disabled"


def test_validate_replay_lifecycle_retry_execution_eligibility_accepts_execution_not_supported() -> None:
    record = _retry_execution_eligibility(reason="execution_not_supported")
    record["payload"]["reason"] = "execution_not_supported"

    result = validate_replay_lifecycle_retry_execution_eligibility(record)

    assert result["valid"] is True
    assert result["reason"] == "execution_not_supported"


def test_validate_replay_lifecycle_retry_execution_eligibility_rejects_supported_execution() -> None:
    record = _retry_execution_eligibility(execution_supported=True)
    record["payload"]["execution_supported"] = True

    result = validate_replay_lifecycle_retry_execution_eligibility(record)

    assert result["valid"] is False
    assert "execution_supported_before_runner" in result["reasons"]
    assert "payload_execution_supported_before_runner" in result["reasons"]


def test_validate_replay_lifecycle_retry_execution_eligibility_rejects_execution_enabled() -> None:
    record = _retry_execution_eligibility(execution_enabled=True)
    record["payload"]["execution_enabled"] = True

    result = validate_replay_lifecycle_retry_execution_eligibility(record)

    assert result["valid"] is False
    assert "execution_enabled_before_runner" in result["reasons"]
    assert "payload_execution_enabled_before_runner" in result["reasons"]


def test_validate_replay_lifecycle_retry_execution_eligibility_rejects_executed_payload() -> None:
    record = _retry_execution_eligibility()
    record["payload"]["executed"] = True

    result = validate_replay_lifecycle_retry_execution_eligibility(record)

    assert result["valid"] is False
    assert "execution_eligibility_executed_before_runner" in result["reasons"]


def test_validate_replay_lifecycle_retry_execution_eligibility_rejects_unknown_reason() -> None:
    record = _retry_execution_eligibility(reason="ready")
    record["payload"]["reason"] = "ready"

    result = validate_replay_lifecycle_retry_execution_eligibility(record)

    assert result["valid"] is False
    assert "invalid_execution_eligibility_reason" in result["reasons"]


def test_validate_replay_lifecycle_retry_execution_eligibility_rejects_eligible_status() -> None:
    record = _retry_execution_eligibility(status="eligible")
    record["payload"]["status"] = "eligible"

    result = validate_replay_lifecycle_retry_execution_eligibility(record)

    assert result["valid"] is False
    assert "invalid_execution_eligibility_status" in result["reasons"]


def test_validate_replay_lifecycle_retry_execution_eligibility_accepts_missing_rendered_command_reason() -> None:
    record = _retry_execution_eligibility(
        reason="missing_rendered_command",
        rendered_command_id="",
        plan_id="",
        proposal_id="",
        approval_id="",
        timeout_profile="unknown",
        decision_mode="unknown",
        command="",
    )
    record["payload"]["reason"] = "missing_rendered_command"
    record["payload"]["rendered_command_id"] = ""
    record["payload"]["plan_id"] = ""
    record["payload"]["proposal_id"] = ""
    record["payload"]["approval_id"] = ""
    record["payload"]["timeout_profile"] = "unknown"
    record["payload"]["decision_mode"] = "unknown"
    record["payload"]["command"] = ""

    result = validate_replay_lifecycle_retry_execution_eligibility(record)

    assert result["valid"] is True
    assert result["reason"] == "missing_rendered_command"


def test_security_validation_metrics_counts_retry_execution_eligibility() -> None:
    metrics = build_security_validation_heartbeat_metrics(
        [_retry_execution_eligibility()]
    )

    assert (
        metrics["security_validation_record_type_counts"][
            "replay_lifecycle_retry_execution_eligibility"
        ]
        == 1
    )
    assert metrics["security_validation_retry_execution_eligibility_statuses"]["blocked"] == 1
    assert (
        metrics["security_validation_retry_execution_eligibility_reasons"][
            "execution_disabled"
        ]
        == 1
    )


def _retry_controlled_execution_result(**overrides):
    command = (
        "python -m src.testing.run_replay_evidence_check "
        "--scenario-id replay-controlled-test "
        "--directive-id runtime-run-replay-controlled-test "
        "--timeout-profile standard"
    )

    command_parse = {
        "type": "controlled_retry_command_parse_result",
        "valid": True,
        "allowlist_matched": True,
        "reasons": [],
        "argv": [
            "python",
            "-m",
            "src.testing.run_replay_evidence_check",
            "--scenario-id",
            "replay-controlled-test",
            "--directive-id",
            "runtime-run-replay-controlled-test",
            "--timeout-profile",
            "standard",
        ],
        "module": "src.testing.run_replay_evidence_check",
        "args": {
            "scenario_id": "replay-controlled-test",
            "directive_id": "runtime-run-replay-controlled-test",
            "timeout_profile": "standard",
        },
        "execution_performed": False,
    }

    gate_evaluation = {
        "type": "controlled_retry_execution_gate_evaluation",
        "gate_status": "blocked",
        "would_execute": False,
        "would_execute_if_enabled": False,
        "reasons": [
            "controlled_execution_not_enabled",
            "controlled_execution_implementation_not_enabled",
        ],
        "controlled_execution_enabled": False,
        "implementation_enabled": False,
        "operator_authorized": False,
        "allowlist_matched": True,
        "command_parse_valid": True,
        "command_parse_allowlist_matched": True,
        "command_parse_execution_performed": False,
        "payload_executed": False,
        "execution_enabled": False,
        "readiness_score": 0,
        "min_readiness_score": 100,
        "execution_performed": False,
    }

    mock_execution = {
        "type": "controlled_retry_mock_execution",
        "status": "blocked",
        "reason": "mock_execution_blocked",
        "mock_execution_enabled": False,
        "real_execution_enabled": False,
        "mock_execution": {
            "adapter_result": {
                "type": "controlled_retry_execution_adapter_result",
                "adapter": "mock",
                "mode": "mock",
                "status": "mock_executed",
                "reason": "mock_execution_completed",
                "controlled_execution_result_id": "controlled-result-1",
                "rendered_command_id": "rendered-command-1",
                "timeout_profile": "standard",
                "subprocess_invoked": False,
                "real_execution_enabled": False,
                "exit_code": 0,
                "stdout": "mock controlled retry execution",
                "stderr": "",
                "payload": {
                    "executed": False,
                    "mock_executed": True,
                    "subprocess_invoked": False,
                    "real_execution_enabled": False,
                    "adapter": "mock",
                    "mode": "mock",
                    "timeout_profile": "standard",
                },
            },
            "performed": False,
            "adapter": "mock",
            "subprocess_invoked": False,
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "reasons": ["mock_execution_not_enabled"],
        },
        "payload": {
            "executed": False,
            "mock_executed": False,
            "subprocess_invoked": False,
        },
    }

    item = {
        "type": "replay_lifecycle_retry_controlled_execution_result",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-command-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "status": "rejected",
        "reason": "controlled_execution_not_implemented",
        "execution_enabled": False,
        "operator_authorized": False,
        "allowlist_matched": True,
        "readiness_score": 0,
        "timeout_profile": "standard",
        "decision_mode": "manual",
        "command": command,
        "command_parse": dict(command_parse),
        "gate_evaluation": dict(gate_evaluation),
        "mock_execution": dict(mock_execution),
        "real_execution_requested": False,
        "real_execution_performed": False,
        "real_execution_supported": False,
        "subprocess_invoked": False,
        "payload": {
            "rendered_command_id": "rendered-command-1",
            "plan_id": "plan-1",
            "proposal_id": "proposal-1",
            "approval_id": "approval-1",
            "status": "rejected",
            "reason": "controlled_execution_not_implemented",
            "execution_enabled": False,
            "operator_authorized": False,
            "allowlist_matched": True,
            "readiness_score": 0,
            "timeout_profile": "standard",
            "decision_mode": "manual",
            "command": command,
            "executed": False,
            "command_parse": dict(command_parse),
            "gate_evaluation": dict(gate_evaluation),
            "mock_execution": dict(mock_execution),
            "real_execution_requested": False,
            "real_execution_performed": False,
            "real_execution_supported": False,
            "subprocess_invoked": False,
        },
    }
    item.update(overrides)
    return item

def test_validate_retry_controlled_execution_result_accepts_reject_only_skeleton() -> None:
    result = validate_replay_lifecycle_retry_controlled_execution_result(
        _retry_controlled_execution_result()
    )

    assert result["valid"] is True
    assert result["severity"] == "info"
    assert result["record_type"] == "replay_lifecycle_retry_controlled_execution_result"
    assert result["status"] == "rejected"
    assert result["reason"] == "controlled_execution_not_implemented"
    assert result["operator_authorized"] is False
    assert result["allowlist_matched"] is True
    assert result["payload_executed"] is False
    assert result["command_parse_valid"] is True
    assert result["command_parse_allowlist_matched"] is True
    assert result["command_parse_execution_performed"] is False
    assert result["gate_status"] == "blocked"
    assert result["gate_would_execute"] is False
    assert result["gate_would_execute_if_enabled"] is False
    assert result["gate_execution_performed"] is False
    assert "controlled_execution_not_enabled" in result["gate_reasons"]
    assert result["mock_execution_status"] == "blocked"
    assert result["mock_execution_performed"] is False
    assert result["mock_subprocess_invoked"] is False
    assert result["real_execution_requested"] is False
    assert result["real_execution_performed"] is False
    assert result["real_execution_supported"] is False
    assert result["subprocess_invoked"] is False
    assert result["reasons"] == []


def test_validate_retry_controlled_execution_result_rejects_executed_payload() -> None:
    record = _retry_controlled_execution_result(
        payload={
            "executed": True,
        }
    )

    result = validate_replay_lifecycle_retry_controlled_execution_result(record)

    assert result["valid"] is False
    assert result["severity"] == "critical"
    assert "not_implemented_result_must_not_execute" in result["reasons"]


def test_validate_retry_controlled_execution_result_rejects_executed_status() -> None:
    result = validate_replay_lifecycle_retry_controlled_execution_result(
        _retry_controlled_execution_result(
            status="executed",
            reason="controlled_execution_not_implemented",
        )
    )

    assert result["valid"] is False
    assert "controlled_execution_not_allowed_yet" in result["reasons"]
    assert "not_implemented_result_must_be_rejected" in result["reasons"]


def test_validate_retry_controlled_execution_result_accepts_operator_authorization_intent_without_execution() -> None:
    result = validate_replay_lifecycle_retry_controlled_execution_result(
        _retry_controlled_execution_result(operator_authorized=True)
    )

    assert result["valid"] is True
    assert result["operator_authorized"] is True
    assert result["payload_executed"] is False
    assert result["status"] == "rejected"
    assert result["reason"] == "controlled_execution_not_implemented"


def test_security_validation_metrics_counts_retry_controlled_execution_results() -> None:
    metrics = build_security_validation_heartbeat_metrics(
        [_retry_controlled_execution_result()]
    )

    assert (
        metrics["security_validation_record_type_counts"][
            "replay_lifecycle_retry_controlled_execution_result"
        ]
        == 1
    )
    assert metrics["security_validation_controlled_execution_result_statuses"][
        "rejected"
    ] == 1
    assert metrics["security_validation_controlled_execution_result_reasons"][
        "controlled_execution_not_implemented"
    ] == 1
    assert metrics["security_validation_controlled_execution_operator_authorized"][
        "false"
    ] == 1
    assert metrics["security_validation_controlled_execution_allowlist_matched"][
        "true"
    ] == 1
    assert metrics["security_validation_controlled_execution_command_parse_valid"][
        "true"
    ] == 1
    assert metrics[
        "security_validation_controlled_execution_command_parse_allowlist_matched"
    ]["true"] == 1
    assert metrics[
        "security_validation_controlled_execution_command_parse_execution_performed"
    ]["false"] == 1
    assert metrics["security_validation_controlled_execution_gate_statuses"][
        "blocked"
    ] == 1
    assert metrics["security_validation_controlled_execution_gate_would_execute"][
        "false"
    ] == 1
    assert metrics[
        "security_validation_controlled_execution_gate_would_execute_if_enabled"
    ]["false"] == 1
    assert metrics[
        "security_validation_controlled_execution_gate_execution_performed"
    ]["false"] == 1
    assert metrics["security_validation_controlled_execution_gate_reasons"][
        "controlled_execution_not_enabled"
    ] == 1
    assert metrics["security_validation_controlled_execution_mock_statuses"][
        "blocked"
    ] == 1
    assert metrics["security_validation_controlled_execution_mock_performed"][
        "false"
    ] == 1
    assert metrics[
        "security_validation_controlled_execution_mock_subprocess_invoked"
    ]["false"] == 1

    assert metrics["security_validation_controlled_execution_mock_adapter"][
        "mock"
    ] == 1
    assert metrics["security_validation_controlled_execution_mock_adapter_mode"][
        "mock"
    ] == 1
    assert metrics[
        "security_validation_controlled_execution_mock_adapter_result_statuses"
    ]["mock_executed"] == 1
    assert metrics[
        "security_validation_controlled_execution_mock_adapter_subprocess_invoked"
    ]["false"] == 1
    assert metrics[
        "security_validation_controlled_execution_mock_adapter_real_execution_enabled"
    ]["false"] == 1
    assert metrics[
        "security_validation_controlled_execution_mock_adapter_payload_executed"
    ]["false"] == 1
    assert metrics["security_validation_controlled_execution_real_requested"][
        "false"
    ] == 1
    assert metrics["security_validation_controlled_execution_real_performed"][
        "false"
    ] == 1
    assert metrics["security_validation_controlled_execution_real_supported"][
        "false"
    ] == 1
    assert metrics["security_validation_controlled_execution_subprocess_invoked"][
        "false"
    ] == 1


def test_validate_retry_controlled_execution_result_accepts_allowlist_match_without_execution() -> None:
    result = validate_replay_lifecycle_retry_controlled_execution_result(
        _retry_controlled_execution_result(allowlist_matched=True)
    )

    assert result["valid"] is True
    assert result["allowlist_matched"] is True
    assert result["payload_executed"] is False


def test_validate_retry_controlled_execution_result_rejects_missing_command_parse() -> None:
    record = _retry_controlled_execution_result()
    record.pop("command_parse", None)
    record["payload"].pop("command_parse", None)

    result = validate_replay_lifecycle_retry_controlled_execution_result(record)

    assert result["valid"] is False
    assert "missing_command_parse" in result["reasons"]


def test_validate_retry_controlled_execution_result_rejects_parse_execution_performed() -> None:
    record = _retry_controlled_execution_result()
    record["command_parse"]["execution_performed"] = True
    record["payload"]["command_parse"]["execution_performed"] = True

    result = validate_replay_lifecycle_retry_controlled_execution_result(record)

    assert result["valid"] is False
    assert "command_parse_must_not_execute" in result["reasons"]


def test_validate_retry_controlled_execution_result_rejects_authorized_execution_payload() -> None:
    record = _retry_controlled_execution_result(operator_authorized=True)
    record["payload"]["executed"] = True

    result = validate_replay_lifecycle_retry_controlled_execution_result(record)

    assert result["valid"] is False
    assert "operator_authorized_result_must_not_execute_yet" in result["reasons"]
    assert "not_implemented_result_must_not_execute" in result["reasons"]


def test_security_validation_metrics_counts_operator_authorized_controlled_execution_intent() -> None:
    metrics = build_security_validation_heartbeat_metrics(
        [_retry_controlled_execution_result(operator_authorized=True)]
    )

    assert metrics["security_validation_controlled_execution_operator_authorized"][
        "true"
    ] == 1
    assert metrics["security_validation_controlled_execution_result_statuses"][
        "rejected"
    ] == 1


def test_validate_retry_controlled_execution_result_rejects_missing_gate_evaluation() -> None:
    record = _retry_controlled_execution_result()
    record.pop("gate_evaluation", None)
    record["payload"].pop("gate_evaluation", None)

    result = validate_replay_lifecycle_retry_controlled_execution_result(record)

    assert result["valid"] is False
    assert "missing_gate_evaluation" in result["reasons"]


def test_validate_retry_controlled_execution_result_rejects_gate_would_execute() -> None:
    record = _retry_controlled_execution_result()
    record["gate_evaluation"]["would_execute"] = True
    record["payload"]["gate_evaluation"]["would_execute"] = True

    result = validate_replay_lifecycle_retry_controlled_execution_result(record)

    assert result["valid"] is False
    assert "gate_would_execute_must_remain_false" in result["reasons"]


def test_validate_retry_controlled_execution_result_rejects_gate_execution_performed() -> None:
    record = _retry_controlled_execution_result()
    record["gate_evaluation"]["execution_performed"] = True
    record["payload"]["gate_evaluation"]["execution_performed"] = True

    result = validate_replay_lifecycle_retry_controlled_execution_result(record)

    assert result["valid"] is False
    assert "gate_must_not_perform_execution" in result["reasons"]


def test_validate_retry_controlled_execution_result_rejects_mock_subprocess_invoked() -> None:
    record = _retry_controlled_execution_result()
    record["mock_execution"]["mock_execution"]["subprocess_invoked"] = True

    result = validate_replay_lifecycle_retry_controlled_execution_result(record)

    assert result["valid"] is False
    assert "mock_execution_must_not_invoke_subprocess" in result["reasons"]


def test_validate_retry_controlled_execution_result_rejects_mock_payload_executed() -> None:
    record = _retry_controlled_execution_result()
    record["mock_execution"]["mock_execution"]["performed"] = True
    record["payload"]["executed"] = True

    result = validate_replay_lifecycle_retry_controlled_execution_result(record)

    assert result["valid"] is False
    assert "mock_execution_must_not_set_payload_executed" in result["reasons"]


def _retry_mock_execution_summary(**overrides):
    item = {
        "type": "replay_lifecycle_retry_mock_execution_summary",
        "mock_execution_summary_id": "mock-summary-1",
        "controlled_execution_result_id": "controlled-result-1",
        "source_controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-command-1",
        "proposal_id": "proposal-1",
        "plan_id": "plan-1",
        "approval_id": "approval-1",
        "status": "mock_executed",
        "reason": "mock_execution_completed",
        "mock_status": "mock_executed",
        "mock_reason": "mock_execution_completed",
        "mock_performed": True,
        "subprocess_invoked": False,
        "real_execution_enabled": False,
        "mock_execution_enabled": True,
        "payload_executed": False,
        "derived": True,
        "payload": {
            "mock_execution_summary_id": "mock-summary-1",
            "controlled_execution_result_id": "controlled-result-1",
            "source_controlled_execution_result_id": "controlled-result-1",
            "rendered_command_id": "rendered-command-1",
            "proposal_id": "proposal-1",
            "plan_id": "plan-1",
            "approval_id": "approval-1",
            "status": "mock_executed",
            "reason": "mock_execution_completed",
            "mock_performed": True,
            "subprocess_invoked": False,
            "real_execution_enabled": False,
            "mock_execution_enabled": True,
            "payload_executed": False,
            "executed": False,
            "derived": True,
        },
    }
    item.update(overrides)
    return item


def _real_execution_preflight(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_preflight",
        "real_execution_preflight_id": "real-preflight-1",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-command-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "status": "blocked",
        "reason": "real_execution_not_supported",
        "reasons": [
            "real_execution_not_supported",
            "subprocess_not_supported",
            "real_adapter_not_runnable",
            "real_adapter_requires_explicit_pr",
        ],
        "real_execution_requested": True,
        "operator_authorized": True,
        "allowlist_matched": True,
        "command_parse_valid": True,
        "command_parse_allowlist_matched": True,
        "would_execute": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "real_execution_supported": False,
        "subprocess_supported": False,
        "real_adapter_runnable": False,
        "real_adapter_requires_explicit_pr": True,
        "payload": {
            "would_execute": False,
            "execution_performed": False,
            "subprocess_invoked": False,
        },
    }
    item.update(overrides)
    return item


def _real_execution_approval(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_approval",
        "real_execution_approval_id": "real-approval-1",
        "real_execution_preflight_id": "real-preflight-1",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-command-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "approval_status": "pending",
        "reason": "real_execution_explicit_approval_required",
        "operator_authorized": True,
        "real_execution_requested": True,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "payload": {
            "real_execution_enabled": False,
            "subprocess_enabled": False,
            "execution_performed": False,
            "subprocess_invoked": False,
            "operator_authorized": True,
        },
    }
    item.update(overrides)
    return item


def _real_execution_approval_transition(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_approval_transition",
        "real_execution_approval_transition_id": "real-transition-1",
        "real_execution_approval_id": "real-approval-1",
        "real_execution_preflight_id": "real-preflight-1",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-command-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "from_status": "pending",
        "to_status": "approved",
        "reason": "real_execution_approval_transition_recorded",
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "payload": {
            "real_execution_enabled": False,
            "subprocess_enabled": False,
            "execution_performed": False,
            "subprocess_invoked": False,
        },
    }
    item.update(overrides)
    return item


def test_validate_retry_mock_execution_summary_accepts_safe_summary() -> None:
    result = validate_replay_lifecycle_retry_mock_execution_summary(
        _retry_mock_execution_summary()
    )

    assert result["valid"] is True
    assert result["status"] == "mock_executed"
    assert result["mock_performed"] is True
    assert result["subprocess_invoked"] is False
    assert result["real_execution_enabled"] is False
    assert result["payload_executed"] is False
    assert result["derived"] is True


def test_validate_retry_mock_execution_summary_rejects_subprocess_invoked() -> None:
    result = validate_replay_lifecycle_retry_mock_execution_summary(
        _retry_mock_execution_summary(subprocess_invoked=True)
    )

    assert result["valid"] is False
    assert "mock_summary_must_not_invoke_subprocess" in result["reasons"]


def test_validate_retry_mock_execution_summary_rejects_real_execution_enabled() -> None:
    result = validate_replay_lifecycle_retry_mock_execution_summary(
        _retry_mock_execution_summary(real_execution_enabled=True)
    )

    assert result["valid"] is False
    assert "mock_summary_must_not_enable_real_execution" in result["reasons"]


def test_security_validation_metrics_counts_retry_mock_execution_summary() -> None:
    metrics = build_security_validation_heartbeat_metrics(
        [_retry_mock_execution_summary()]
    )

    assert metrics["security_validation_record_type_counts"][
        "replay_lifecycle_retry_mock_execution_summary"
    ] == 1
    assert metrics["security_validation_mock_summary_statuses"]["mock_executed"] == 1
    assert metrics["security_validation_mock_summary_reasons"][
        "mock_execution_completed"
    ] == 1
    assert metrics["security_validation_mock_summary_performed"]["true"] == 1
    assert metrics["security_validation_mock_summary_subprocess_invoked"]["false"] == 1


def test_validate_retry_controlled_execution_result_rejects_mock_adapter_subprocess_invoked() -> None:
    record = _retry_controlled_execution_result()
    record["mock_execution"]["mock_execution"]["adapter_result"][
        "subprocess_invoked"
    ] = True

    result = validate_replay_lifecycle_retry_controlled_execution_result(record)

    assert result["valid"] is False
    assert "mock_adapter_result_must_not_invoke_subprocess" in result["reasons"]


def test_validate_retry_controlled_execution_result_rejects_mock_adapter_real_execution_enabled() -> None:
    record = _retry_controlled_execution_result()
    record["mock_execution"]["mock_execution"]["adapter_result"][
        "real_execution_enabled"
    ] = True

    result = validate_replay_lifecycle_retry_controlled_execution_result(record)

    assert result["valid"] is False
    assert "mock_adapter_result_must_not_enable_real_execution" in result["reasons"]


def test_validate_retry_controlled_execution_result_rejects_mock_adapter_payload_executed() -> None:
    record = _retry_controlled_execution_result()
    record["mock_execution"]["mock_execution"]["adapter_result"]["payload"][
        "executed"
    ] = True

    result = validate_replay_lifecycle_retry_controlled_execution_result(record)

    assert result["valid"] is False
    assert "mock_adapter_result_payload_must_not_execute" in result["reasons"]


def test_validate_retry_controlled_execution_result_rejects_non_mock_adapter() -> None:
    record = _retry_controlled_execution_result()
    record["mock_execution"]["mock_execution"]["adapter_result"]["adapter"] = "real"

    result = validate_replay_lifecycle_retry_controlled_execution_result(record)

    assert result["valid"] is False
    assert "mock_adapter_result_must_use_mock_adapter" in result["reasons"]


def test_validate_retry_controlled_execution_result_rejects_non_mock_adapter_mode() -> None:
    record = _retry_controlled_execution_result()
    record["mock_execution"]["mock_execution"]["adapter_result"]["mode"] = "real"

    result = validate_replay_lifecycle_retry_controlled_execution_result(record)

    assert result["valid"] is False
    assert "mock_adapter_result_must_use_mock_mode" in result["reasons"]


def test_validate_retry_controlled_execution_result_accepts_rejected_real_execution_request() -> None:
    record = _retry_controlled_execution_result(
        reason="real_execution_not_supported",
        real_execution_requested=True,
    )
    record["payload"]["reason"] = "real_execution_not_supported"
    record["payload"]["real_execution_requested"] = True

    result = validate_replay_lifecycle_retry_controlled_execution_result(record)

    assert result["valid"] is True
    assert result["real_execution_requested"] is True
    assert result["real_execution_performed"] is False
    assert result["subprocess_invoked"] is False


def test_validate_retry_controlled_execution_result_rejects_real_execution_performed() -> None:
    record = _retry_controlled_execution_result(real_execution_performed=True)
    record["payload"]["real_execution_performed"] = True

    result = validate_replay_lifecycle_retry_controlled_execution_result(record)

    assert result["valid"] is False
    assert "real_execution_must_not_be_performed" in result["reasons"]


def test_validate_retry_controlled_execution_result_rejects_subprocess_invoked() -> None:
    record = _retry_controlled_execution_result(subprocess_invoked=True)
    record["payload"]["subprocess_invoked"] = True

    result = validate_replay_lifecycle_retry_controlled_execution_result(record)

    assert result["valid"] is False
    assert "controlled_execution_must_not_invoke_subprocess" in result["reasons"]


def test_validate_retry_controlled_execution_result_rejects_real_request_with_wrong_reason() -> None:
    record = _retry_controlled_execution_result(real_execution_requested=True)
    record["payload"]["real_execution_requested"] = True

    result = validate_replay_lifecycle_retry_controlled_execution_result(record)

    assert result["valid"] is False
    assert "real_execution_request_must_be_rejected_as_not_supported" in result["reasons"]


def test_validate_retry_real_execution_preflight_accepts_blocked_preflight() -> None:
    result = validate_replay_lifecycle_retry_real_execution_preflight(
        _real_execution_preflight()
    )

    assert result["valid"] is True
    assert result["status"] == "blocked"
    assert result["would_execute"] is False
    assert result["execution_performed"] is False
    assert result["subprocess_invoked"] is False
    assert result["real_adapter_requires_explicit_pr"] is True


def test_validate_retry_real_execution_preflight_rejects_would_execute() -> None:
    result = validate_replay_lifecycle_retry_real_execution_preflight(
        _real_execution_preflight(would_execute=True)
    )

    assert result["valid"] is False
    assert "real_preflight_must_not_would_execute" in result["reasons"]


def test_validate_retry_real_execution_preflight_rejects_subprocess_invoked() -> None:
    result = validate_replay_lifecycle_retry_real_execution_preflight(
        _real_execution_preflight(subprocess_invoked=True)
    )

    assert result["valid"] is False
    assert "real_preflight_must_not_invoke_subprocess" in result["reasons"]


def test_validate_retry_real_execution_approval_accepts_pending_disabled() -> None:
    result = validate_replay_lifecycle_retry_real_execution_approval(
        _real_execution_approval()
    )

    assert result["valid"] is True
    assert result["approval_status"] == "pending"
    assert result["real_execution_enabled"] is False
    assert result["subprocess_enabled"] is False
    assert result["execution_performed"] is False
    assert result["subprocess_invoked"] is False


def test_validate_retry_real_execution_approval_accepts_approved_but_disabled() -> None:
    result = validate_replay_lifecycle_retry_real_execution_approval(
        _real_execution_approval(approval_status="approved")
    )

    assert result["valid"] is True
    assert result["approval_status"] == "approved"
    assert result["real_execution_enabled"] is False
    assert result["subprocess_enabled"] is False


def test_validate_retry_real_execution_approval_rejects_real_execution_enabled() -> None:
    record = _real_execution_approval(real_execution_enabled=True)
    record["payload"]["real_execution_enabled"] = True

    result = validate_replay_lifecycle_retry_real_execution_approval(record)

    assert result["valid"] is False
    assert (
        "real_execution_approval_must_not_enable_real_execution"
        in result["reasons"]
    )


def test_validate_retry_real_execution_approval_rejects_subprocess_enabled() -> None:
    record = _real_execution_approval(subprocess_enabled=True)
    record["payload"]["subprocess_enabled"] = True

    result = validate_replay_lifecycle_retry_real_execution_approval(record)

    assert result["valid"] is False
    assert "real_execution_approval_must_not_enable_subprocess" in result["reasons"]


def test_validate_retry_real_execution_approval_transition_accepts_approved_disabled() -> None:
    result = validate_replay_lifecycle_retry_real_execution_approval_transition(
        _real_execution_approval_transition()
    )

    assert result["valid"] is True
    assert result["from_status"] == "pending"
    assert result["to_status"] == "approved"
    assert result["real_execution_enabled"] is False
    assert result["subprocess_enabled"] is False
    assert result["execution_performed"] is False
    assert result["subprocess_invoked"] is False


def test_validate_retry_real_execution_approval_transition_rejects_real_execution_enabled() -> None:
    record = _real_execution_approval_transition(real_execution_enabled=True)
    record["payload"]["real_execution_enabled"] = True

    result = validate_replay_lifecycle_retry_real_execution_approval_transition(
        record
    )

    assert result["valid"] is False
    assert (
        "real_approval_transition_must_not_enable_real_execution"
        in result["reasons"]
    )


def test_validate_retry_real_execution_approval_transition_rejects_subprocess_enabled() -> None:
    record = _real_execution_approval_transition(subprocess_enabled=True)
    record["payload"]["subprocess_enabled"] = True

    result = validate_replay_lifecycle_retry_real_execution_approval_transition(
        record
    )

    assert result["valid"] is False
    assert "real_approval_transition_must_not_enable_subprocess" in result["reasons"]


def test_validate_retry_real_execution_approval_transition_rejects_non_pending_from_status() -> None:
    result = validate_replay_lifecycle_retry_real_execution_approval_transition(
        _real_execution_approval_transition(from_status="approved", to_status="rejected")
    )

    assert result["valid"] is False
    assert "real_approval_transition_must_start_from_pending" in result["reasons"]


def _real_execution_final_gate(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_final_gate",
        "real_execution_final_gate_id": "real-final-gate-1",
        "real_execution_approval_transition_id": "real-transition-1",
        "real_execution_approval_id": "real-approval-1",
        "real_execution_preflight_id": "real-preflight-1",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-command-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "from_status": "pending",
        "to_status": "approved",
        "gate_status": "blocked",
        "would_execute": False,
        "ready_for_real_execution": False,
        "real_adapter_supported": False,
        "real_adapter_runnable": False,
        "subprocess_supported": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "reasons": [
            "real_adapter_not_supported",
            "subprocess_not_supported",
            "explicit_execution_pr_required",
        ],
        "payload": {
            "would_execute": False,
            "ready_for_real_execution": False,
            "real_execution_enabled": False,
            "subprocess_enabled": False,
            "execution_performed": False,
            "subprocess_invoked": False,
        },
    }
    item.update(overrides)
    return item


def test_validate_retry_real_execution_final_gate_accepts_blocked_disabled() -> None:
    result = validate_replay_lifecycle_retry_real_execution_final_gate(
        _real_execution_final_gate()
    )

    assert result["valid"] is True
    assert result["gate_status"] == "blocked"
    assert result["would_execute"] is False
    assert result["ready_for_real_execution"] is False
    assert result["real_execution_enabled"] is False
    assert result["subprocess_enabled"] is False


def test_validate_retry_real_execution_final_gate_rejects_ready() -> None:
    record = _real_execution_final_gate(ready_for_real_execution=True)
    record["payload"]["ready_for_real_execution"] = True

    result = validate_replay_lifecycle_retry_real_execution_final_gate(record)

    assert result["valid"] is False
    assert "real_final_gate_must_not_be_ready" in result["reasons"]


def test_validate_retry_real_execution_final_gate_rejects_would_execute() -> None:
    record = _real_execution_final_gate(would_execute=True)
    record["payload"]["would_execute"] = True

    result = validate_replay_lifecycle_retry_real_execution_final_gate(record)

    assert result["valid"] is False
    assert "real_final_gate_would_execute_must_remain_false" in result["reasons"]


def test_validate_retry_real_execution_final_gate_rejects_subprocess_invoked() -> None:
    record = _real_execution_final_gate(subprocess_invoked=True)
    record["payload"]["subprocess_invoked"] = True

    result = validate_replay_lifecycle_retry_real_execution_final_gate(record)

    assert result["valid"] is False
    assert "real_final_gate_must_not_invoke_subprocess" in result["reasons"]


def _real_execution_dry_run_envelope(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_dry_run_envelope",
        "real_execution_dry_run_envelope_id": "real-dry-run-envelope-1",
        "real_execution_final_gate_id": "real-final-gate-1",
        "real_execution_approval_transition_id": "real-transition-1",
        "real_execution_approval_id": "real-approval-1",
        "real_execution_preflight_id": "real-preflight-1",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-command-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "command": "python -m src.testing.run_replay_evidence_check --scenario-id s --directive-id d --timeout-profile standard",
        "argv": [
            "python",
            "-m",
            "src.testing.run_replay_evidence_check",
            "--scenario-id",
            "s",
            "--directive-id",
            "d",
            "--timeout-profile",
            "standard",
        ],
        "cwd": "/workspaces/BlackSwan",
        "env_keys": ["PATH", "PYTHONPATH", "PWD"],
        "timeout_profile": "standard",
        "decision_mode": "manual",
        "dry_run_only": True,
        "would_execute": False,
        "ready_for_real_execution": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "reason": "real_execution_dry_run_envelope_recorded",
        "payload": {
            "dry_run_only": True,
            "would_execute": False,
            "ready_for_real_execution": False,
            "real_execution_enabled": False,
            "subprocess_enabled": False,
            "execution_performed": False,
            "subprocess_invoked": False,
        },
    }
    item.update(overrides)
    return item


def test_validate_retry_real_execution_dry_run_envelope_accepts_safe_envelope() -> None:
    result = validate_replay_lifecycle_retry_real_execution_dry_run_envelope(
        _real_execution_dry_run_envelope()
    )

    assert result["valid"] is True
    assert result["dry_run_only"] is True
    assert result["would_execute"] is False
    assert result["ready_for_real_execution"] is False
    assert result["subprocess_invoked"] is False
    assert result["argv_len"] > 0
    assert result["env_key_count"] > 0


def test_validate_retry_real_execution_dry_run_envelope_rejects_would_execute() -> None:
    record = _real_execution_dry_run_envelope(would_execute=True)
    record["payload"]["would_execute"] = True

    result = validate_replay_lifecycle_retry_real_execution_dry_run_envelope(record)

    assert result["valid"] is False
    assert "dry_run_envelope_would_execute_must_remain_false" in result["reasons"]


def test_validate_retry_real_execution_dry_run_envelope_rejects_subprocess_invoked() -> None:
    record = _real_execution_dry_run_envelope(subprocess_invoked=True)
    record["payload"]["subprocess_invoked"] = True

    result = validate_replay_lifecycle_retry_real_execution_dry_run_envelope(record)

    assert result["valid"] is False
    assert "dry_run_envelope_must_not_invoke_subprocess" in result["reasons"]


def test_validate_retry_real_execution_dry_run_envelope_rejects_secret_env_keys() -> None:
    record = _real_execution_dry_run_envelope(env_keys=["PATH", "API_TOKEN"])

    result = validate_replay_lifecycle_retry_real_execution_dry_run_envelope(record)

    assert result["valid"] is False
    assert "dry_run_envelope_env_keys_must_not_include_secrets" in result["reasons"]


def _real_execution_noop_result(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_noop_result",
        "real_execution_noop_result_id": "real-noop-result-1",
        "real_execution_dry_run_envelope_id": "real-dry-run-envelope-1",
        "real_execution_final_gate_id": "real-final-gate-1",
        "real_execution_approval_transition_id": "real-transition-1",
        "real_execution_approval_id": "real-approval-1",
        "real_execution_preflight_id": "real-preflight-1",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-command-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "noop_argv": ["python", "-c", "print('controlled-noop-ok')"],
        "noop_only": True,
        "rendered_command_executed": False,
        "dry_run_envelope_command_executed": False,
        "real_execution_enabled": False,
        "subprocess_invoked": True,
        "execution_performed": True,
        "exit_code": 0,
        "stdout": "controlled-noop-ok\n",
        "stderr": "",
        "duration_seconds": 0.01,
        "reason": "real_execution_noop_harness_completed",
        "payload": {
            "noop_only": True,
            "rendered_command_executed": False,
            "dry_run_envelope_command_executed": False,
            "real_execution_enabled": False,
            "subprocess_invoked": True,
            "execution_performed": True,
        },
    }
    item.update(overrides)
    return item


def test_validate_retry_real_execution_noop_result_accepts_safe_noop() -> None:
    result = validate_replay_lifecycle_retry_real_execution_noop_result(
        _real_execution_noop_result()
    )

    assert result["valid"] is True
    assert result["noop_only"] is True
    assert result["rendered_command_executed"] is False
    assert result["dry_run_envelope_command_executed"] is False
    assert result["real_execution_enabled"] is False
    assert result["subprocess_invoked"] is True
    assert result["execution_performed"] is True
    assert result["exit_code"] == 0
    assert result["stdout_marker_observed"] is True


def test_validate_retry_real_execution_noop_result_rejects_rendered_command_execution() -> None:
    record = _real_execution_noop_result(rendered_command_executed=True)
    record["payload"]["rendered_command_executed"] = True

    result = validate_replay_lifecycle_retry_real_execution_noop_result(record)

    assert result["valid"] is False
    assert "noop_result_must_not_execute_rendered_command" in result["reasons"]


def test_validate_retry_real_execution_noop_result_rejects_dry_run_command_execution() -> None:
    record = _real_execution_noop_result(dry_run_envelope_command_executed=True)
    record["payload"]["dry_run_envelope_command_executed"] = True

    result = validate_replay_lifecycle_retry_real_execution_noop_result(record)

    assert result["valid"] is False
    assert "noop_result_must_not_execute_dry_run_envelope_command" in result["reasons"]


def test_validate_retry_real_execution_noop_result_rejects_missing_stdout_marker() -> None:
    result = validate_replay_lifecycle_retry_real_execution_noop_result(
        _real_execution_noop_result(stdout="")
    )

    assert result["valid"] is False
    assert "noop_result_stdout_must_contain_marker" in result["reasons"]


def test_validate_retry_real_execution_noop_result_rejects_non_zero_exit_code() -> None:
    result = validate_replay_lifecycle_retry_real_execution_noop_result(
        _real_execution_noop_result(exit_code=1)
    )

    assert result["valid"] is False
    assert "noop_result_exit_code_must_be_zero" in result["reasons"]


def _real_execution_read_only_promotion(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_read_only_promotion",
        "real_execution_read_only_promotion_id": "real-read-only-promotion-1",
        "real_execution_noop_result_id": "real-noop-result-1",
        "real_execution_dry_run_envelope_id": "real-dry-run-envelope-1",
        "real_execution_final_gate_id": "real-final-gate-1",
        "real_execution_approval_transition_id": "real-transition-1",
        "real_execution_approval_id": "real-approval-1",
        "real_execution_preflight_id": "real-preflight-1",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-command-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "promotion_status": "promoted",
        "read_only_candidate": True,
        "read_only_module": "src.testing.run_replay_evidence_check",
        "read_only_command": (
            "python -m src.testing.run_replay_evidence_check "
            "--scenario-id s --action REDUCE_RISK --directive-id d "
            "--timeout-profile standard"
        ),
        "read_only_argv": [
            "python",
            "-m",
            "src.testing.run_replay_evidence_check",
            "--scenario-id",
            "s",
            "--action",
            "REDUCE_RISK",
            "--directive-id",
            "d",
            "--timeout-profile",
            "standard",
        ],
        "command_parse_valid": True,
        "stdout_marker_observed": True,
        "noop_exit_code": 0,
        "noop_only": True,
        "rendered_command_executed": False,
        "dry_run_envelope_command_executed": False,
        "real_execution_enabled": False,
        "subprocess_invoked": False,
        "execution_performed": False,
        "reason": "real_execution_read_only_promotion_recorded",
        "payload": {
            "promotion_status": "promoted",
            "read_only_candidate": True,
            "command_parse_valid": True,
            "stdout_marker_observed": True,
            "noop_exit_code": 0,
            "noop_only": True,
            "rendered_command_executed": False,
            "dry_run_envelope_command_executed": False,
            "real_execution_enabled": False,
            "subprocess_invoked": False,
            "execution_performed": False,
        },
    }
    item.update(overrides)
    return item


def test_validate_retry_real_execution_read_only_promotion_accepts_safe_promotion() -> None:
    result = validate_replay_lifecycle_retry_real_execution_read_only_promotion(
        _real_execution_read_only_promotion()
    )

    assert result["valid"] is True
    assert result["promotion_status"] == "promoted"
    assert result["read_only_candidate"] is True
    assert result["command_parse_valid"] is True
    assert result["stdout_marker_observed"] is True
    assert result["noop_exit_code"] == 0
    assert result["subprocess_invoked"] is False
    assert result["execution_performed"] is False


def test_validate_retry_real_execution_read_only_promotion_rejects_blocked_status() -> None:
    result = validate_replay_lifecycle_retry_real_execution_read_only_promotion(
        _real_execution_read_only_promotion(promotion_status="blocked")
    )

    assert result["valid"] is False
    assert "read_only_promotion_must_be_promoted" in result["reasons"]


def test_validate_retry_real_execution_read_only_promotion_rejects_subprocess_invoked() -> None:
    record = _real_execution_read_only_promotion(subprocess_invoked=True)
    record["payload"]["subprocess_invoked"] = True

    result = validate_replay_lifecycle_retry_real_execution_read_only_promotion(record)

    assert result["valid"] is False
    assert "read_only_promotion_must_not_invoke_subprocess" in result["reasons"]


def test_validate_retry_real_execution_read_only_promotion_rejects_rendered_command_execution() -> None:
    record = _real_execution_read_only_promotion(rendered_command_executed=True)
    record["payload"]["rendered_command_executed"] = True

    result = validate_replay_lifecycle_retry_real_execution_read_only_promotion(record)

    assert result["valid"] is False
    assert (
        "read_only_promotion_must_not_execute_rendered_command"
        in result["reasons"]
    )


def test_validate_retry_real_execution_read_only_promotion_rejects_bad_module() -> None:
    result = validate_replay_lifecycle_retry_real_execution_read_only_promotion(
        _real_execution_read_only_promotion(read_only_module="os")
    )

    assert result["valid"] is False
    assert "read_only_promotion_module_must_be_allowlisted" in result["reasons"]


def _real_execution_read_only_final_gate(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_read_only_final_gate",
        "real_execution_read_only_final_gate_id": "real-read-only-final-gate-1",
        "real_execution_read_only_promotion_id": "real-read-only-promotion-1",
        "real_execution_noop_result_id": "real-noop-result-1",
        "real_execution_dry_run_envelope_id": "real-dry-run-envelope-1",
        "real_execution_final_gate_id": "real-final-gate-1",
        "real_execution_approval_transition_id": "real-transition-1",
        "real_execution_approval_id": "real-approval-1",
        "real_execution_preflight_id": "real-preflight-1",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-command-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "promotion_status": "promoted",
        "promotion_preconditions_satisfied": True,
        "precondition_failures": [],
        "gate_status": "blocked",
        "ready_for_read_only_execution": False,
        "would_execute": False,
        "read_only_execution_enabled": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "subprocess_invoked": False,
        "execution_performed": False,
        "rendered_command_executed": False,
        "dry_run_envelope_command_executed": False,
        "read_only_module": "src.testing.run_replay_evidence_check",
        "read_only_argv": [
            "python",
            "-m",
            "src.testing.run_replay_evidence_check",
        ],
        "reason": "read_only_execution_requires_separate_pr",
        "blocking_reasons": ["read_only_execution_requires_separate_pr"],
        "payload": {
            "promotion_preconditions_satisfied": True,
            "gate_status": "blocked",
            "ready_for_read_only_execution": False,
            "would_execute": False,
            "read_only_execution_enabled": False,
            "real_execution_enabled": False,
            "subprocess_enabled": False,
            "subprocess_invoked": False,
            "execution_performed": False,
            "rendered_command_executed": False,
            "dry_run_envelope_command_executed": False,
        },
    }
    item.update(overrides)
    return item


def test_validate_retry_real_execution_read_only_final_gate_accepts_blocked_gate() -> None:
    result = validate_replay_lifecycle_retry_real_execution_read_only_final_gate(
        _real_execution_read_only_final_gate()
    )

    assert result["valid"] is True
    assert result["gate_status"] == "blocked"
    assert result["promotion_preconditions_satisfied"] is True
    assert result["ready_for_read_only_execution"] is False
    assert result["subprocess_invoked"] is False
    assert result["execution_performed"] is False


def test_validate_retry_real_execution_read_only_final_gate_rejects_ready_gate() -> None:
    record = _real_execution_read_only_final_gate(
        ready_for_read_only_execution=True
    )
    record["payload"]["ready_for_read_only_execution"] = True

    result = validate_replay_lifecycle_retry_real_execution_read_only_final_gate(record)

    assert result["valid"] is False
    assert "read_only_final_gate_must_not_be_ready" in result["reasons"]


def test_validate_retry_real_execution_read_only_final_gate_rejects_subprocess_invoked() -> None:
    record = _real_execution_read_only_final_gate(subprocess_invoked=True)
    record["payload"]["subprocess_invoked"] = True

    result = validate_replay_lifecycle_retry_real_execution_read_only_final_gate(record)

    assert result["valid"] is False
    assert "read_only_final_gate_must_not_invoke_subprocess" in result["reasons"]


def test_validate_retry_real_execution_read_only_final_gate_rejects_missing_separate_pr_reason() -> None:
    result = validate_replay_lifecycle_retry_real_execution_read_only_final_gate(
        _real_execution_read_only_final_gate(blocking_reasons=[])
    )

    assert result["valid"] is False
    assert "read_only_final_gate_must_require_separate_pr" in result["reasons"]


def _real_execution_read_only_approval(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_read_only_approval",
        "real_execution_read_only_approval_id": "read-only-approval-1",
        "real_execution_read_only_final_gate_id": "read-only-final-gate-1",
        "real_execution_read_only_promotion_id": "read-only-promotion-1",
        "real_execution_noop_result_id": "noop-result-1",
        "real_execution_dry_run_envelope_id": "dry-run-envelope-1",
        "real_execution_final_gate_id": "real-final-gate-1",
        "real_execution_approval_transition_id": "real-transition-1",
        "real_execution_approval_id": "real-approval-1",
        "real_execution_preflight_id": "real-preflight-1",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-command-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "approval_status": "pending",
        "read_only_module": "src.testing.run_replay_evidence_check",
        "read_only_argv": ["python", "-m", "src.testing.run_replay_evidence_check"],
        "read_only_execution_enabled": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "subprocess_invoked": False,
        "execution_performed": False,
        "rendered_command_executed": False,
        "dry_run_envelope_command_executed": False,
        "reason": "read_only_execution_explicit_approval_required",
        "payload": {
            "read_only_execution_enabled": False,
            "real_execution_enabled": False,
            "subprocess_enabled": False,
            "subprocess_invoked": False,
            "execution_performed": False,
            "rendered_command_executed": False,
            "dry_run_envelope_command_executed": False,
        },
    }
    item.update(overrides)
    return item


def test_validate_retry_real_execution_read_only_approval_accepts_pending_disabled() -> None:
    result = validate_replay_lifecycle_retry_real_execution_read_only_approval(
        _real_execution_read_only_approval()
    )

    assert result["valid"] is True
    assert result["approval_status"] == "pending"
    assert result["read_only_execution_enabled"] is False
    assert result["subprocess_invoked"] is False
    assert result["execution_performed"] is False


def test_validate_retry_real_execution_read_only_approval_accepts_approved_disabled() -> None:
    result = validate_replay_lifecycle_retry_real_execution_read_only_approval(
        _real_execution_read_only_approval(approval_status="approved")
    )

    assert result["valid"] is True
    assert result["approval_status"] == "approved"
    assert result["read_only_execution_enabled"] is False


def test_validate_retry_real_execution_read_only_approval_rejects_read_only_execution_enabled() -> None:
    record = _real_execution_read_only_approval(read_only_execution_enabled=True)
    record["payload"]["read_only_execution_enabled"] = True

    result = validate_replay_lifecycle_retry_real_execution_read_only_approval(record)

    assert result["valid"] is False
    assert (
        "read_only_approval_must_not_enable_read_only_execution"
        in result["reasons"]
    )


def test_validate_retry_real_execution_read_only_approval_rejects_subprocess_invoked() -> None:
    record = _real_execution_read_only_approval(subprocess_invoked=True)
    record["payload"]["subprocess_invoked"] = True

    result = validate_replay_lifecycle_retry_real_execution_read_only_approval(record)

    assert result["valid"] is False
    assert "read_only_approval_must_not_invoke_subprocess" in result["reasons"]


def _real_execution_read_only_approval_transition(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_read_only_approval_transition",
        "real_execution_read_only_approval_transition_id": "read-only-transition-1",
        "real_execution_read_only_approval_id": "read-only-approval-1",
        "real_execution_read_only_final_gate_id": "read-only-final-gate-1",
        "real_execution_read_only_promotion_id": "read-only-promotion-1",
        "real_execution_noop_result_id": "noop-result-1",
        "real_execution_dry_run_envelope_id": "dry-run-envelope-1",
        "real_execution_final_gate_id": "real-final-gate-1",
        "real_execution_approval_transition_id": "real-transition-1",
        "real_execution_approval_id": "real-approval-1",
        "real_execution_preflight_id": "real-preflight-1",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-command-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "from_status": "pending",
        "to_status": "approved",
        "read_only_module": "src.testing.run_replay_evidence_check",
        "read_only_argv": ["python", "-m", "src.testing.run_replay_evidence_check"],
        "read_only_execution_enabled": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "subprocess_invoked": False,
        "execution_performed": False,
        "rendered_command_executed": False,
        "dry_run_envelope_command_executed": False,
        "reason": "read_only_execution_approval_transition_recorded",
        "payload": {
            "read_only_execution_enabled": False,
            "real_execution_enabled": False,
            "subprocess_enabled": False,
            "subprocess_invoked": False,
            "execution_performed": False,
            "rendered_command_executed": False,
            "dry_run_envelope_command_executed": False,
        },
    }
    item.update(overrides)
    return item


def test_validate_retry_real_execution_read_only_approval_transition_accepts_approved_disabled() -> None:
    result = (
        validate_replay_lifecycle_retry_real_execution_read_only_approval_transition(
            _real_execution_read_only_approval_transition()
        )
    )

    assert result["valid"] is True
    assert result["from_status"] == "pending"
    assert result["to_status"] == "approved"
    assert result["read_only_execution_enabled"] is False
    assert result["subprocess_invoked"] is False
    assert result["execution_performed"] is False


def test_validate_retry_real_execution_read_only_approval_transition_accepts_rejected_disabled() -> None:
    result = (
        validate_replay_lifecycle_retry_real_execution_read_only_approval_transition(
            _real_execution_read_only_approval_transition(to_status="rejected")
        )
    )

    assert result["valid"] is True
    assert result["to_status"] == "rejected"
    assert result["read_only_execution_enabled"] is False


def test_validate_retry_real_execution_read_only_approval_transition_rejects_non_pending_from_status() -> None:
    result = (
        validate_replay_lifecycle_retry_real_execution_read_only_approval_transition(
            _real_execution_read_only_approval_transition(from_status="approved")
        )
    )

    assert result["valid"] is False
    assert (
        "read_only_approval_transition_from_status_must_be_pending"
        in result["reasons"]
    )


def test_validate_retry_real_execution_read_only_approval_transition_rejects_subprocess_invoked() -> None:
    record = _real_execution_read_only_approval_transition(subprocess_invoked=True)
    record["payload"]["subprocess_invoked"] = True

    result = (
        validate_replay_lifecycle_retry_real_execution_read_only_approval_transition(
            record
        )
    )

    assert result["valid"] is False
    assert (
        "read_only_approval_transition_must_not_invoke_subprocess"
        in result["reasons"]
    )


def test_validate_retry_real_execution_read_only_approval_transition_rejects_read_only_execution_enabled() -> None:
    record = _real_execution_read_only_approval_transition(
        read_only_execution_enabled=True
    )
    record["payload"]["read_only_execution_enabled"] = True

    result = (
        validate_replay_lifecycle_retry_real_execution_read_only_approval_transition(
            record
        )
    )

    assert result["valid"] is False
    assert (
        "read_only_approval_transition_must_not_enable_read_only_execution"
        in result["reasons"]
    )


def _real_execution_read_only_readiness_gate(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_read_only_readiness_gate",
        "real_execution_read_only_readiness_gate_id": "readiness-gate-1",
        "real_execution_read_only_approval_transition_id": "read-only-transition-1",
        "real_execution_read_only_approval_id": "read-only-approval-1",
        "real_execution_read_only_final_gate_id": "read-only-final-gate-1",
        "real_execution_read_only_promotion_id": "read-only-promotion-1",
        "real_execution_noop_result_id": "noop-result-1",
        "real_execution_dry_run_envelope_id": "dry-run-envelope-1",
        "rendered_command_id": "rendered-command-1",
        "read_only_approval_from_status": "pending",
        "read_only_approval_latest_status": "approved",
        "read_only_readiness_satisfied": True,
        "ready_for_guarded_read_only_execution": True,
        "gate_status": "ready_blocked",
        "precondition_failures": [],
        "blocking_reasons": ["guarded_read_only_execution_requires_separate_pr"],
        "read_only_module": "src.testing.run_replay_evidence_check",
        "read_only_argv": ["python", "-m", "src.testing.run_replay_evidence_check"],
        "read_only_execution_enabled": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "subprocess_invoked": False,
        "execution_performed": False,
        "rendered_command_executed": False,
        "dry_run_envelope_command_executed": False,
        "reason": "guarded_read_only_execution_requires_separate_pr",
        "payload": {
            "read_only_readiness_satisfied": True,
            "ready_for_guarded_read_only_execution": True,
            "read_only_execution_enabled": False,
            "real_execution_enabled": False,
            "subprocess_enabled": False,
            "subprocess_invoked": False,
            "execution_performed": False,
            "rendered_command_executed": False,
            "dry_run_envelope_command_executed": False,
        },
    }
    item.update(overrides)
    return item


def test_validate_retry_real_execution_read_only_readiness_gate_accepts_ready_blocked() -> None:
    result = validate_replay_lifecycle_retry_real_execution_read_only_readiness_gate(
        _real_execution_read_only_readiness_gate()
    )

    assert result["valid"] is True
    assert result["gate_status"] == "ready_blocked"
    assert result["read_only_readiness_satisfied"] is True
    assert result["ready_for_guarded_read_only_execution"] is True
    assert result["read_only_execution_enabled"] is False
    assert result["subprocess_invoked"] is False
    assert result["execution_performed"] is False


def test_validate_retry_real_execution_read_only_readiness_gate_rejects_execution_enabled() -> None:
    record = _real_execution_read_only_readiness_gate(
        read_only_execution_enabled=True
    )
    record["payload"]["read_only_execution_enabled"] = True

    result = validate_replay_lifecycle_retry_real_execution_read_only_readiness_gate(
        record
    )

    assert result["valid"] is False
    assert (
        "read_only_readiness_gate_must_not_enable_read_only_execution"
        in result["reasons"]
    )


def test_validate_retry_real_execution_read_only_readiness_gate_rejects_subprocess_invoked() -> None:
    record = _real_execution_read_only_readiness_gate(subprocess_invoked=True)
    record["payload"]["subprocess_invoked"] = True

    result = validate_replay_lifecycle_retry_real_execution_read_only_readiness_gate(
        record
    )

    assert result["valid"] is False
    assert "read_only_readiness_gate_must_not_invoke_subprocess" in result["reasons"]


def test_validate_retry_real_execution_read_only_readiness_gate_rejects_not_approved() -> None:
    result = validate_replay_lifecycle_retry_real_execution_read_only_readiness_gate(
        _real_execution_read_only_readiness_gate(
            read_only_approval_latest_status="rejected"
        )
    )

    assert result["valid"] is False
    assert "read_only_readiness_gate_latest_status_must_be_approved" in result["reasons"]


def _real_execution_read_only_execution_result(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_read_only_execution_result",
        "real_execution_read_only_execution_result_id": "read-only-result-1",
        "real_execution_read_only_readiness_gate_id": "readiness-gate-1",
        "real_execution_read_only_approval_transition_id": "read-only-transition-1",
        "real_execution_read_only_approval_id": "read-only-approval-1",
        "real_execution_read_only_final_gate_id": "read-only-final-gate-1",
        "real_execution_read_only_promotion_id": "read-only-promotion-1",
        "real_execution_noop_result_id": "noop-result-1",
        "real_execution_dry_run_envelope_id": "dry-run-envelope-1",
        "rendered_command_id": "rendered-command-1",
        "status": "failed",
        "reason": "guarded_read_only_execution_failed",
        "operator_authorized": True,
        "allow_guarded_read_only_execution": True,
        "read_only_module": "src.testing.run_replay_evidence_check",
        "read_only_argv": ["python", "-m", "src.testing.run_replay_evidence_check"],
        "read_only_execution_enabled": True,
        "real_execution_enabled": False,
        "subprocess_enabled": True,
        "subprocess_invoked": True,
        "execution_performed": True,
        "read_only_command_executed": True,
        "rendered_command_executed": True,
        "dry_run_envelope_command_executed": True,
        "exit_code": 1,
        "stdout": "",
        "stderr": "failed checks",
        "validation_reasons": [],
        "payload": {
            "real_execution_enabled": False,
        },
    }
    item.update(overrides)
    return item


def test_validate_retry_real_execution_read_only_execution_result_accepts_failed_execution() -> None:
    result = validate_replay_lifecycle_retry_real_execution_read_only_execution_result(
        _real_execution_read_only_execution_result()
    )

    assert result["valid"] is True
    assert result["status"] == "failed"
    assert result["exit_code"] == 1
    assert result["subprocess_invoked"] is True
    assert result["execution_performed"] is True


def test_validate_retry_real_execution_read_only_execution_result_accepts_successful_execution() -> None:
    result = validate_replay_lifecycle_retry_real_execution_read_only_execution_result(
        _real_execution_read_only_execution_result(
            status="executed",
            reason="guarded_read_only_execution_completed",
            exit_code=0,
            stdout="ok",
            stderr="",
        )
    )

    assert result["valid"] is True
    assert result["status"] == "executed"
    assert result["exit_code"] == 0


def test_validate_retry_real_execution_read_only_execution_result_rejects_real_execution_enabled() -> None:
    record = _real_execution_read_only_execution_result(real_execution_enabled=True)
    record["payload"]["real_execution_enabled"] = True

    result = validate_replay_lifecycle_retry_real_execution_read_only_execution_result(
        record
    )

    assert result["valid"] is False
    assert "read_only_execution_result_must_not_enable_real_execution" in result["reasons"]


def test_validate_retry_real_execution_read_only_execution_result_rejects_missing_guarded_flag() -> None:
    result = validate_replay_lifecycle_retry_real_execution_read_only_execution_result(
        _real_execution_read_only_execution_result(
            allow_guarded_read_only_execution=False
        )
    )

    assert result["valid"] is False
    assert "read_only_execution_result_requires_guarded_flag" in result["reasons"]


def test_validate_retry_real_execution_read_only_execution_result_accepts_rejected_without_subprocess() -> None:
    result = validate_replay_lifecycle_retry_real_execution_read_only_execution_result(
        _real_execution_read_only_execution_result(
            status="rejected",
            reason="guarded_read_only_execution_rejected",
            read_only_execution_enabled=False,
            subprocess_enabled=False,
            subprocess_invoked=False,
            execution_performed=False,
            read_only_command_executed=False,
            rendered_command_executed=False,
            dry_run_envelope_command_executed=False,
            exit_code=None,
            validation_reasons=["guarded_read_only_execution_flag_required"],
        )
    )

    assert result["valid"] is True
    assert result["status"] == "rejected"


def _real_execution_read_only_feedback(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_read_only_feedback",
        "real_execution_read_only_feedback_id": "feedback-1",
        "real_execution_read_only_execution_result_id": "read-only-result-1",
        "real_execution_read_only_readiness_gate_id": "readiness-gate-1",
        "rendered_command_id": "rendered-command-1",
        "source_status": "failed",
        "source_reason": "guarded_read_only_execution_failed",
        "source_exit_code": 1,
        "feedback_status": "actionable",
        "recommended_next_action": "investigate_failed_read_only_evidence_check",
        "failure_hints": ["source_status:failed", "source_exit_code:1"],
        "read_only_execution_was_observed": True,
        "read_only_execution_failed": True,
        "read_only_execution_succeeded": False,
        "read_only_execution_rejected": False,
        "operator_authorized": True,
        "allow_guarded_read_only_execution": True,
        "read_only_execution_enabled": True,
        "real_execution_enabled": False,
        "source_subprocess_invoked": True,
        "source_execution_performed": True,
        "source_read_only_command_executed": True,
        "source_rendered_command_executed": True,
        "source_dry_run_command_executed": True,
        "feedback_execution_performed": False,
        "feedback_subprocess_invoked": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "reason": "read_only_execution_feedback_recorded",
        "payload": {
            "real_execution_enabled": False,
            "feedback_execution_performed": False,
            "feedback_subprocess_invoked": False,
            "execution_performed": False,
            "subprocess_invoked": False,
        },
    }
    item.update(overrides)
    return item


def test_validate_retry_real_execution_read_only_feedback_accepts_failed_actionable() -> None:
    result = validate_replay_lifecycle_retry_real_execution_read_only_feedback(
        _real_execution_read_only_feedback()
    )

    assert result["valid"] is True
    assert result["feedback_status"] == "actionable"
    assert result["source_status"] == "failed"
    assert result["source_exit_code"] == 1
    assert result["feedback_execution_performed"] is False
    assert result["feedback_subprocess_invoked"] is False


def test_validate_retry_real_execution_read_only_feedback_accepts_successful() -> None:
    result = validate_replay_lifecycle_retry_real_execution_read_only_feedback(
        _real_execution_read_only_feedback(
            source_status="executed",
            source_reason="guarded_read_only_execution_completed",
            source_exit_code=0,
            feedback_status="successful",
            recommended_next_action="promote_successful_read_only_execution_evidence",
            read_only_execution_failed=False,
            read_only_execution_succeeded=True,
        )
    )

    assert result["valid"] is True
    assert result["feedback_status"] == "successful"


def test_validate_retry_real_execution_read_only_feedback_rejects_feedback_execution() -> None:
    record = _real_execution_read_only_feedback(feedback_execution_performed=True)
    record["payload"]["feedback_execution_performed"] = True

    result = validate_replay_lifecycle_retry_real_execution_read_only_feedback(record)

    assert result["valid"] is False
    assert "read_only_feedback_must_not_perform_feedback_execution" in result["reasons"]


def test_validate_retry_real_execution_read_only_feedback_rejects_real_execution_enabled() -> None:
    record = _real_execution_read_only_feedback(real_execution_enabled=True)
    record["payload"]["real_execution_enabled"] = True

    result = validate_replay_lifecycle_retry_real_execution_read_only_feedback(record)

    assert result["valid"] is False
    assert "read_only_feedback_must_not_enable_real_execution" in result["reasons"]


def _real_execution_read_only_repair_plan(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_read_only_repair_plan",
        "real_execution_read_only_repair_plan_id": "repair-plan-1",
        "real_execution_read_only_feedback_id": "feedback-1",
        "real_execution_read_only_execution_result_id": "read-only-result-1",
        "real_execution_read_only_readiness_gate_id": "readiness-gate-1",
        "rendered_command_id": "rendered-command-1",
        "source_feedback_status": "actionable",
        "source_status": "failed",
        "source_exit_code": 1,
        "repair_plan_status": "planned",
        "repair_items": [
            {
                "target": "execution_published",
                "recommended_action": "publish_or_verify_execution_record",
                "priority": "high",
                "execution_required": False,
                "subprocess_required": False,
            }
        ],
        "repair_item_count": 1,
        "repair_targets": ["execution_published"],
        "recommended_next_action": "review_replay_evidence_repair_plan",
        "requires_operator_review": True,
        "repair_execution_enabled": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "repair_execution_performed": False,
        "repair_subprocess_invoked": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "reason": "read_only_execution_repair_plan_recorded",
        "payload": {
            "repair_execution_enabled": False,
            "real_execution_enabled": False,
            "subprocess_enabled": False,
            "repair_execution_performed": False,
            "repair_subprocess_invoked": False,
            "execution_performed": False,
            "subprocess_invoked": False,
        },
    }
    item.update(overrides)
    return item


def test_validate_retry_real_execution_read_only_repair_plan_accepts_planned() -> None:
    result = validate_replay_lifecycle_retry_real_execution_read_only_repair_plan(
        _real_execution_read_only_repair_plan()
    )

    assert result["valid"] is True
    assert result["repair_plan_status"] == "planned"
    assert result["source_feedback_status"] == "actionable"
    assert result["source_status"] == "failed"
    assert result["repair_item_count"] == 1
    assert result["repair_execution_performed"] is False
    assert result["subprocess_invoked"] is False


def test_validate_retry_real_execution_read_only_repair_plan_rejects_execution() -> None:
    record = _real_execution_read_only_repair_plan(execution_performed=True)
    record["payload"]["execution_performed"] = True

    result = validate_replay_lifecycle_retry_real_execution_read_only_repair_plan(
        record
    )

    assert result["valid"] is False
    assert "read_only_repair_plan_must_not_execute" in result["reasons"]


def test_validate_retry_real_execution_read_only_repair_plan_rejects_real_execution_enabled() -> None:
    record = _real_execution_read_only_repair_plan(real_execution_enabled=True)
    record["payload"]["real_execution_enabled"] = True

    result = validate_replay_lifecycle_retry_real_execution_read_only_repair_plan(
        record
    )

    assert result["valid"] is False
    assert "read_only_repair_plan_must_not_enable_real_execution" in result["reasons"]


def test_validate_retry_real_execution_read_only_repair_plan_rejects_item_count_mismatch() -> None:
    result = validate_replay_lifecycle_retry_real_execution_read_only_repair_plan(
        _real_execution_read_only_repair_plan(repair_item_count=2)
    )

    assert result["valid"] is False
    assert "read_only_repair_plan_item_count_mismatch" in result["reasons"]


def _real_execution_read_only_repair_action_bundle(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_read_only_repair_action_bundle",
        "real_execution_read_only_repair_action_bundle_id": "bundle-1",
        "real_execution_read_only_repair_plan_id": "repair-plan-1",
        "real_execution_read_only_feedback_id": "feedback-1",
        "real_execution_read_only_execution_result_id": "read-only-result-1",
        "rendered_command_id": "rendered-command-1",
        "source_repair_plan_status": "planned",
        "source_feedback_status": "actionable",
        "source_status": "failed",
        "source_exit_code": 1,
        "source_repair_item_count": 2,
        "bundle_status": "assembled",
        "bundle_items": [
            {
                "action_id": "action-1",
                "target": "execution_published",
                "recommended_action": "publish_or_verify_execution_record",
                "review_required": True,
                "execution_allowed": False,
                "subprocess_allowed": False,
                "real_execution_allowed": False,
                "execution_performed": False,
                "subprocess_invoked": False,
            },
            {
                "action_id": "action-2",
                "target": "evidence_published",
                "recommended_action": "publish_or_verify_replay_evidence",
                "review_required": True,
                "execution_allowed": False,
                "subprocess_allowed": False,
                "real_execution_allowed": False,
                "execution_performed": False,
                "subprocess_invoked": False,
            },
        ],
        "bundle_item_count": 2,
        "bundle_targets": ["execution_published", "evidence_published"],
        "recommended_next_action": "review_repair_action_bundle",
        "requires_operator_review": True,
        "bundle_reviewed": False,
        "bundle_execution_enabled": False,
        "repair_execution_enabled": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "bundle_execution_performed": False,
        "bundle_subprocess_invoked": False,
        "repair_execution_performed": False,
        "repair_subprocess_invoked": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "reason": "read_only_repair_action_bundle_recorded",
        "payload": {
            "bundle_execution_enabled": False,
            "repair_execution_enabled": False,
            "real_execution_enabled": False,
            "subprocess_enabled": False,
            "bundle_execution_performed": False,
            "bundle_subprocess_invoked": False,
            "repair_execution_performed": False,
            "repair_subprocess_invoked": False,
            "execution_performed": False,
            "subprocess_invoked": False,
        },
    }
    item.update(overrides)
    return item


def test_validate_retry_real_execution_read_only_repair_action_bundle_accepts_assembled() -> None:
    result = validate_replay_lifecycle_retry_real_execution_read_only_repair_action_bundle(
        _real_execution_read_only_repair_action_bundle()
    )

    assert result["valid"] is True
    assert result["bundle_status"] == "assembled"
    assert result["source_repair_plan_status"] == "planned"
    assert result["bundle_item_count"] == 2
    assert result["bundle_execution_performed"] is False
    assert result["subprocess_invoked"] is False


def test_validate_retry_real_execution_read_only_repair_action_bundle_rejects_execution() -> None:
    record = _real_execution_read_only_repair_action_bundle(execution_performed=True)
    record["payload"]["execution_performed"] = True

    result = validate_replay_lifecycle_retry_real_execution_read_only_repair_action_bundle(
        record
    )

    assert result["valid"] is False
    assert "read_only_repair_action_bundle_must_not_execute" in result["reasons"]


def test_validate_retry_real_execution_read_only_repair_action_bundle_rejects_real_execution_enabled() -> None:
    record = _real_execution_read_only_repair_action_bundle(real_execution_enabled=True)
    record["payload"]["real_execution_enabled"] = True

    result = validate_replay_lifecycle_retry_real_execution_read_only_repair_action_bundle(
        record
    )

    assert result["valid"] is False
    assert "read_only_repair_action_bundle_must_not_enable_real_execution" in result["reasons"]


def test_validate_retry_real_execution_read_only_repair_action_bundle_rejects_item_execution_allowed() -> None:
    record = _real_execution_read_only_repair_action_bundle()
    record["bundle_items"][0]["execution_allowed"] = True

    result = validate_replay_lifecycle_retry_real_execution_read_only_repair_action_bundle(
        record
    )

    assert result["valid"] is False
    assert "read_only_repair_action_bundle_item_must_not_allow_execution" in result["reasons"]


def test_validate_retry_real_execution_read_only_repair_action_bundle_rejects_item_count_mismatch() -> None:
    result = validate_replay_lifecycle_retry_real_execution_read_only_repair_action_bundle(
        _real_execution_read_only_repair_action_bundle(bundle_item_count=3)
    )

    assert result["valid"] is False
    assert "read_only_repair_action_bundle_item_count_mismatch" in result["reasons"]


def _real_execution_read_only_repair_action_bundle_review(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_read_only_repair_action_bundle_review",
        "real_execution_read_only_repair_action_bundle_review_id": "bundle-review-1",
        "real_execution_read_only_repair_action_bundle_id": "bundle-1",
        "real_execution_read_only_repair_plan_id": "repair-plan-1",
        "real_execution_read_only_feedback_id": "feedback-1",
        "real_execution_read_only_execution_result_id": "read-only-result-1",
        "rendered_command_id": "rendered-command-1",
        "source_bundle_status": "assembled",
        "source_repair_plan_status": "planned",
        "source_feedback_status": "actionable",
        "source_status": "failed",
        "source_exit_code": 1,
        "source_bundle_item_count": 9,
        "review_status": "approved",
        "operator_authorized": True,
        "requires_operator_review": True,
        "reviewed": True,
        "review_approved": True,
        "review_rejected": False,
        "recommended_next_action": "prepare_repair_execution_approval_scaffold",
        "bundle_execution_enabled": False,
        "repair_execution_enabled": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "bundle_execution_performed": False,
        "bundle_subprocess_invoked": False,
        "repair_execution_performed": False,
        "repair_subprocess_invoked": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "reason": "read_only_repair_action_bundle_review_recorded",
        "payload": {
            "bundle_execution_enabled": False,
            "repair_execution_enabled": False,
            "real_execution_enabled": False,
            "subprocess_enabled": False,
            "bundle_execution_performed": False,
            "bundle_subprocess_invoked": False,
            "repair_execution_performed": False,
            "repair_subprocess_invoked": False,
            "execution_performed": False,
            "subprocess_invoked": False,
        },
    }
    item.update(overrides)
    return item


def test_validate_retry_real_execution_read_only_repair_action_bundle_review_accepts_approved() -> None:
    result = validate_replay_lifecycle_retry_real_execution_read_only_repair_action_bundle_review(
        _real_execution_read_only_repair_action_bundle_review()
    )

    assert result["valid"] is True
    assert result["review_status"] == "approved"
    assert result["reviewed"] is True
    assert result["review_approved"] is True
    assert result["recommended_next_action"] == (
        "prepare_repair_execution_approval_scaffold"
    )
    assert result["repair_execution_enabled"] is False
    assert result["execution_performed"] is False
    assert result["subprocess_invoked"] is False


def test_validate_retry_real_execution_read_only_repair_action_bundle_review_accepts_pending() -> None:
    result = validate_replay_lifecycle_retry_real_execution_read_only_repair_action_bundle_review(
        _real_execution_read_only_repair_action_bundle_review(
            review_status="pending",
            reviewed=False,
            review_approved=False,
            review_rejected=False,
            recommended_next_action="await_repair_action_bundle_review",
        )
    )

    assert result["valid"] is True
    assert result["review_status"] == "pending"
    assert result["reviewed"] is False


def test_validate_retry_real_execution_read_only_repair_action_bundle_review_rejects_real_execution_enabled() -> None:
    record = _real_execution_read_only_repair_action_bundle_review(
        real_execution_enabled=True
    )
    record["payload"]["real_execution_enabled"] = True

    result = validate_replay_lifecycle_retry_real_execution_read_only_repair_action_bundle_review(
        record
    )

    assert result["valid"] is False
    assert (
        "read_only_repair_action_bundle_review_must_not_enable_real_execution"
        in result["reasons"]
    )


def test_validate_retry_real_execution_read_only_repair_action_bundle_review_rejects_execution() -> None:
    record = _real_execution_read_only_repair_action_bundle_review(
        execution_performed=True
    )
    record["payload"]["execution_performed"] = True

    result = validate_replay_lifecycle_retry_real_execution_read_only_repair_action_bundle_review(
        record
    )

    assert result["valid"] is False
    assert "read_only_repair_action_bundle_review_must_not_execute" in result["reasons"]


def test_validate_retry_real_execution_read_only_repair_action_bundle_review_rejects_bad_approved_flags() -> None:
    result = validate_replay_lifecycle_retry_real_execution_read_only_repair_action_bundle_review(
        _real_execution_read_only_repair_action_bundle_review(
            review_status="approved",
            reviewed=False,
            review_approved=False,
        )
    )

    assert result["valid"] is False
    assert (
        "approved_read_only_repair_action_bundle_review_must_be_reviewed"
        in result["reasons"]
    )
    assert (
        "approved_read_only_repair_action_bundle_review_must_be_approved"
        in result["reasons"]
    )


def _real_execution_repair_approval(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_repair_approval",
        "real_execution_repair_approval_id": "repair-approval-1",
        "real_execution_read_only_repair_action_bundle_review_id": "bundle-review-1",
        "real_execution_read_only_repair_action_bundle_id": "bundle-1",
        "real_execution_read_only_repair_plan_id": "repair-plan-1",
        "real_execution_read_only_feedback_id": "feedback-1",
        "real_execution_read_only_execution_result_id": "read-only-result-1",
        "rendered_command_id": "rendered-command-1",
        "approval_status": "pending",
        "source_review_status": "approved",
        "source_reviewed": True,
        "source_review_approved": True,
        "source_bundle_status": "assembled",
        "source_repair_plan_status": "planned",
        "source_feedback_status": "actionable",
        "source_status": "failed",
        "source_exit_code": 1,
        "source_bundle_item_count": 9,
        "recommended_next_action": "await_repair_execution_approval",
        "operator_authorized": True,
        "requires_operator_review": True,
        "repair_execution_approval_required": True,
        "repair_execution_approved": False,
        "repair_execution_rejected": False,
        "bundle_execution_enabled": False,
        "repair_execution_enabled": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "bundle_execution_performed": False,
        "bundle_subprocess_invoked": False,
        "repair_execution_performed": False,
        "repair_subprocess_invoked": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "reason": "repair_execution_explicit_approval_required",
        "payload": {
            "bundle_execution_enabled": False,
            "repair_execution_enabled": False,
            "real_execution_enabled": False,
            "subprocess_enabled": False,
            "bundle_execution_performed": False,
            "bundle_subprocess_invoked": False,
            "repair_execution_performed": False,
            "repair_subprocess_invoked": False,
            "execution_performed": False,
            "subprocess_invoked": False,
        },
    }
    item.update(overrides)
    return item


def test_validate_retry_real_execution_repair_approval_accepts_pending_disabled() -> None:
    result = validate_replay_lifecycle_retry_real_execution_repair_approval(
        _real_execution_repair_approval()
    )

    assert result["valid"] is True
    assert result["approval_status"] == "pending"
    assert result["repair_execution_enabled"] is False
    assert result["execution_performed"] is False
    assert result["subprocess_invoked"] is False


def test_validate_retry_real_execution_repair_approval_accepts_approved_but_disabled() -> None:
    result = validate_replay_lifecycle_retry_real_execution_repair_approval(
        _real_execution_repair_approval(
            approval_status="approved",
            repair_execution_approved=True,
            recommended_next_action="await_repair_execution_approval_transition",
        )
    )

    assert result["valid"] is True
    assert result["approval_status"] == "approved"
    assert result["repair_execution_approved"] is True
    assert result["repair_execution_enabled"] is False


def test_validate_retry_real_execution_repair_approval_rejects_repair_execution_enabled() -> None:
    record = _real_execution_repair_approval(repair_execution_enabled=True)
    record["payload"]["repair_execution_enabled"] = True

    result = validate_replay_lifecycle_retry_real_execution_repair_approval(record)

    assert result["valid"] is False
    assert "repair_execution_approval_must_not_enable_repair_execution" in result["reasons"]


def test_validate_retry_real_execution_repair_approval_rejects_subprocess_enabled() -> None:
    record = _real_execution_repair_approval(subprocess_enabled=True)
    record["payload"]["subprocess_enabled"] = True

    result = validate_replay_lifecycle_retry_real_execution_repair_approval(record)

    assert result["valid"] is False
    assert "repair_execution_approval_must_not_enable_subprocess" in result["reasons"]


def test_validate_retry_real_execution_repair_approval_rejects_unapproved_source_review() -> None:
    result = validate_replay_lifecycle_retry_real_execution_repair_approval(
        _real_execution_repair_approval(
            source_review_status="pending",
            source_reviewed=False,
            source_review_approved=False,
        )
    )

    assert result["valid"] is False
    assert "repair_execution_approval_source_review_must_be_approved" in result["reasons"]
    assert "repair_execution_approval_source_must_be_reviewed" in result["reasons"]
    assert "repair_execution_approval_source_must_be_review_approved" in result["reasons"]


def _real_execution_repair_approval_transition(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_repair_approval_transition",
        "real_execution_repair_approval_transition_id": "repair-transition-1",
        "real_execution_repair_approval_id": "repair-approval-1",
        "real_execution_read_only_repair_action_bundle_review_id": "bundle-review-1",
        "real_execution_read_only_repair_action_bundle_id": "bundle-1",
        "real_execution_read_only_repair_plan_id": "repair-plan-1",
        "real_execution_read_only_feedback_id": "feedback-1",
        "real_execution_read_only_execution_result_id": "read-only-result-1",
        "rendered_command_id": "rendered-command-1",
        "from_status": "pending",
        "to_status": "approved",
        "source_approval_status": "pending",
        "source_review_status": "approved",
        "source_reviewed": True,
        "source_review_approved": True,
        "source_bundle_status": "assembled",
        "source_repair_plan_status": "planned",
        "source_feedback_status": "actionable",
        "source_status": "failed",
        "source_exit_code": 1,
        "source_bundle_item_count": 9,
        "recommended_next_action": "prepare_repair_execution_final_gate",
        "operator_authorized": True,
        "requires_operator_review": True,
        "repair_execution_approval_required": True,
        "repair_execution_transition_approved": True,
        "repair_execution_transition_rejected": False,
        "bundle_execution_enabled": False,
        "repair_execution_enabled": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "bundle_execution_performed": False,
        "bundle_subprocess_invoked": False,
        "repair_execution_performed": False,
        "repair_subprocess_invoked": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "reason": "repair_execution_approval_transition_recorded",
        "payload": {
            "bundle_execution_enabled": False,
            "repair_execution_enabled": False,
            "real_execution_enabled": False,
            "subprocess_enabled": False,
            "bundle_execution_performed": False,
            "bundle_subprocess_invoked": False,
            "repair_execution_performed": False,
            "repair_subprocess_invoked": False,
            "execution_performed": False,
            "subprocess_invoked": False,
        },
    }
    item.update(overrides)
    return item


def test_validate_retry_real_execution_repair_approval_transition_accepts_approved_disabled() -> None:
    result = validate_replay_lifecycle_retry_real_execution_repair_approval_transition(
        _real_execution_repair_approval_transition()
    )

    assert result["valid"] is True
    assert result["from_status"] == "pending"
    assert result["to_status"] == "approved"
    assert result["repair_execution_transition_approved"] is True
    assert result["repair_execution_enabled"] is False
    assert result["execution_performed"] is False
    assert result["subprocess_invoked"] is False


def test_validate_retry_real_execution_repair_approval_transition_accepts_rejected_disabled() -> None:
    result = validate_replay_lifecycle_retry_real_execution_repair_approval_transition(
        _real_execution_repair_approval_transition(
            to_status="rejected",
            repair_execution_transition_approved=False,
            repair_execution_transition_rejected=True,
            recommended_next_action="revise_repair_execution_approval",
        )
    )

    assert result["valid"] is True
    assert result["to_status"] == "rejected"
    assert result["repair_execution_transition_rejected"] is True
    assert result["repair_execution_enabled"] is False


def test_validate_retry_real_execution_repair_approval_transition_rejects_repair_execution_enabled() -> None:
    record = _real_execution_repair_approval_transition(repair_execution_enabled=True)
    record["payload"]["repair_execution_enabled"] = True

    result = validate_replay_lifecycle_retry_real_execution_repair_approval_transition(
        record
    )

    assert result["valid"] is False
    assert (
        "repair_execution_approval_transition_must_not_enable_repair_execution"
        in result["reasons"]
    )


def test_validate_retry_real_execution_repair_approval_transition_rejects_subprocess_enabled() -> None:
    record = _real_execution_repair_approval_transition(subprocess_enabled=True)
    record["payload"]["subprocess_enabled"] = True

    result = validate_replay_lifecycle_retry_real_execution_repair_approval_transition(
        record
    )

    assert result["valid"] is False
    assert (
        "repair_execution_approval_transition_must_not_enable_subprocess"
        in result["reasons"]
    )


def test_validate_retry_real_execution_repair_approval_transition_rejects_non_pending_from_status() -> None:
    result = validate_replay_lifecycle_retry_real_execution_repair_approval_transition(
        _real_execution_repair_approval_transition(
            from_status="approved",
            source_approval_status="approved",
        )
    )

    assert result["valid"] is False
    assert (
        "repair_execution_approval_transition_from_status_must_be_pending"
        in result["reasons"]
    )
    assert (
        "repair_execution_approval_transition_source_approval_must_be_pending"
        in result["reasons"]
    )


def _real_execution_repair_dry_run_envelope(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_repair_dry_run_envelope",
        "real_execution_repair_dry_run_envelope_id": "repair-envelope-1",
        "real_execution_repair_final_gate_id": "repair-final-gate-1",
        "real_execution_repair_approval_transition_id": "repair-transition-1",
        "real_execution_repair_approval_id": "repair-approval-1",
        "real_execution_read_only_repair_action_bundle_id": "bundle-1",
        "real_execution_read_only_repair_plan_id": "repair-plan-1",
        "rendered_command_id": "rendered-command-1",
        "repair_dry_run_status": "prepared",
        "dry_run_only": True,
        "repair_dry_run_mode": "repair_action_bundle_validation",
        "repair_dry_run_targets": ["target-a", "target-b"],
        "repair_dry_run_target_count": 2,
        "repair_dry_run_report": {
            "mode": "repair_action_bundle_validation",
            "target_count": 2,
            "targets": ["target-a", "target-b"],
            "applies_changes": False,
            "invokes_subprocess": False,
            "executes_bundle": False,
        },
        "source_gate_status": "ready_blocked",
        "source_final_gate_ready_blocked": True,
        "source_final_gate_preconditions_satisfied": True,
        "source_transition_approved": True,
        "operator_authorized": True,
        "ready_for_repair_execution": False,
        "would_execute": False,
        "recommended_next_action": "prepare_repair_execution_noop_harness",
        "bundle_execution_enabled": False,
        "repair_execution_enabled": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "bundle_execution_performed": False,
        "bundle_subprocess_invoked": False,
        "repair_execution_performed": False,
        "repair_subprocess_invoked": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "reason": "repair_execution_dry_run_envelope_recorded",
        "payload": {
            "bundle_execution_enabled": False,
            "repair_execution_enabled": False,
            "real_execution_enabled": False,
            "subprocess_enabled": False,
            "bundle_execution_performed": False,
            "bundle_subprocess_invoked": False,
            "repair_execution_performed": False,
            "repair_subprocess_invoked": False,
            "execution_performed": False,
            "subprocess_invoked": False,
        },
    }
    item.update(overrides)
    return item

def test_validate_retry_real_execution_repair_dry_run_envelope_accepts_prepared_disabled() -> None:
    result = validate_replay_lifecycle_retry_real_execution_repair_dry_run_envelope(
        _real_execution_repair_dry_run_envelope()
    )

    assert result["valid"] is True
    assert result["repair_dry_run_status"] == "prepared"
    assert result["dry_run_only"] is True
    assert result["repair_execution_enabled"] is False
    assert result["execution_performed"] is False
    assert result["subprocess_invoked"] is False


def test_validate_retry_real_execution_repair_dry_run_envelope_rejects_repair_execution_enabled() -> None:
    record = _real_execution_repair_dry_run_envelope(repair_execution_enabled=True)
    record["payload"]["repair_execution_enabled"] = True

    result = validate_replay_lifecycle_retry_real_execution_repair_dry_run_envelope(
        record
    )

    assert result["valid"] is False
    assert (
        "repair_dry_run_envelope_must_not_enable_repair_execution"
        in result["reasons"]
    )


def test_validate_retry_real_execution_repair_dry_run_envelope_rejects_subprocess_enabled() -> None:
    record = _real_execution_repair_dry_run_envelope(subprocess_enabled=True)
    record["payload"]["subprocess_enabled"] = True

    result = validate_replay_lifecycle_retry_real_execution_repair_dry_run_envelope(
        record
    )

    assert result["valid"] is False
    assert "repair_dry_run_envelope_must_not_enable_subprocess" in result["reasons"]


def test_validate_retry_real_execution_repair_dry_run_envelope_rejects_report_that_applies_changes() -> None:
    record = _real_execution_repair_dry_run_envelope()
    record["repair_dry_run_report"]["applies_changes"] = True

    result = validate_replay_lifecycle_retry_real_execution_repair_dry_run_envelope(
        record
    )

    assert result["valid"] is False
    assert "repair_dry_run_report_must_not_apply_changes" in result["reasons"]


def test_validate_retry_real_execution_repair_dry_run_envelope_rejects_target_count_mismatch() -> None:
    result = validate_replay_lifecycle_retry_real_execution_repair_dry_run_envelope(
        _real_execution_repair_dry_run_envelope(
            repair_dry_run_target_count=3,
        )
    )

    assert result["valid"] is False
    assert "repair_dry_run_envelope_target_count_mismatch" in result["reasons"]


def _real_execution_repair_noop_result(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_repair_noop_result",
        "real_execution_repair_noop_result_id": "repair-noop-1",
        "real_execution_repair_dry_run_envelope_id": "repair-envelope-1",
        "real_execution_repair_final_gate_id": "repair-final-gate-1",
        "real_execution_repair_approval_transition_id": "repair-transition-1",
        "real_execution_repair_approval_id": "repair-approval-1",
        "real_execution_read_only_repair_action_bundle_id": "bundle-1",
        "real_execution_read_only_repair_plan_id": "repair-plan-1",
        "rendered_command_id": "rendered-command-1",
        "repair_noop_status": "completed",
        "noop_only": True,
        "noop_marker": "controlled-repair-noop-ok",
        "noop_stdout_marker_observed": True,
        "exit_code": 0,
        "stdout": "controlled-repair-noop-ok\n",
        "stderr": "",
        "source_envelope_status": "prepared",
        "source_dry_run_only": True,
        "source_repair_dry_run_mode": "repair_action_bundle_validation",
        "source_repair_dry_run_target_count": 9,
        "source_final_gate_ready_blocked": True,
        "source_transition_approved": True,
        "operator_authorized": True,
        "dry_run_envelope_executed": False,
        "repair_dry_run_envelope_executed": False,
        "repair_actions_executed": False,
        "repair_bundle_executed": False,
        "repair_command_executed": False,
        "rendered_command_executed": False,
        "dry_run_command_executed": False,
        "bundle_execution_enabled": False,
        "repair_execution_enabled": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "bundle_execution_performed": False,
        "bundle_subprocess_invoked": False,
        "repair_execution_performed": False,
        "repair_subprocess_invoked": False,
        "execution_performed": True,
        "subprocess_invoked": True,
        "recommended_next_action": "inspect_repair_noop_result",
        "reason": "repair_execution_noop_harness_completed",
        "payload": {
            "repair_actions_executed": False,
            "repair_bundle_executed": False,
            "repair_command_executed": False,
            "rendered_command_executed": False,
            "dry_run_command_executed": False,
            "bundle_execution_enabled": False,
            "repair_execution_enabled": False,
            "real_execution_enabled": False,
            "subprocess_enabled": False,
            "bundle_execution_performed": False,
            "bundle_subprocess_invoked": False,
            "repair_execution_performed": False,
            "repair_subprocess_invoked": False,
            "execution_performed": True,
            "subprocess_invoked": True,
        },
    }
    item.update(overrides)
    return item


def test_validate_retry_real_execution_repair_noop_result_accepts_completed_noop() -> None:
    result = validate_replay_lifecycle_retry_real_execution_repair_noop_result(
        _real_execution_repair_noop_result()
    )

    assert result["valid"] is True
    assert result["repair_noop_status"] == "completed"
    assert result["noop_only"] is True
    assert result["exit_code"] == 0
    assert result["execution_performed"] is True
    assert result["subprocess_invoked"] is True
    assert result["repair_execution_performed"] is False
    assert result["repair_subprocess_invoked"] is False


def test_validate_retry_real_execution_repair_noop_result_rejects_repair_actions_executed() -> None:
    record = _real_execution_repair_noop_result(repair_actions_executed=True)
    record["payload"]["repair_actions_executed"] = True

    result = validate_replay_lifecycle_retry_real_execution_repair_noop_result(record)

    assert result["valid"] is False
    assert "repair_noop_must_not_execute_repair_actions" in result["reasons"]


def test_validate_retry_real_execution_repair_noop_result_rejects_repair_execution_enabled() -> None:
    record = _real_execution_repair_noop_result(repair_execution_enabled=True)
    record["payload"]["repair_execution_enabled"] = True

    result = validate_replay_lifecycle_retry_real_execution_repair_noop_result(record)

    assert result["valid"] is False
    assert "repair_noop_must_not_enable_repair_execution" in result["reasons"]


def test_validate_retry_real_execution_repair_noop_result_rejects_repair_subprocess_invoked() -> None:
    record = _real_execution_repair_noop_result(repair_subprocess_invoked=True)
    record["payload"]["repair_subprocess_invoked"] = True

    result = validate_replay_lifecycle_retry_real_execution_repair_noop_result(record)

    assert result["valid"] is False
    assert "repair_noop_must_not_invoke_repair_subprocess" in result["reasons"]


def test_validate_retry_real_execution_repair_noop_result_rejects_completed_without_marker() -> None:
    result = validate_replay_lifecycle_retry_real_execution_repair_noop_result(
        _real_execution_repair_noop_result(
            stdout="",
            noop_stdout_marker_observed=False,
        )
    )

    assert result["valid"] is False
    assert "repair_noop_marker_missing_from_stdout" in result["reasons"]
    assert "completed_repair_noop_result_requires_stdout_marker" in result["reasons"]


def _real_execution_repair_noop_feedback(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_repair_noop_feedback",
        "real_execution_repair_noop_feedback_id": "repair-feedback-1",
        "real_execution_repair_noop_result_id": "repair-noop-1",
        "real_execution_repair_dry_run_envelope_id": "repair-envelope-1",
        "real_execution_repair_final_gate_id": "repair-final-gate-1",
        "real_execution_repair_approval_transition_id": "repair-transition-1",
        "real_execution_repair_approval_id": "repair-approval-1",
        "real_execution_read_only_repair_action_bundle_id": "bundle-1",
        "real_execution_read_only_repair_plan_id": "repair-plan-1",
        "rendered_command_id": "rendered-command-1",
        "feedback_status": "actionable",
        "repair_noop_verified": True,
        "repair_path_can_proceed": True,
        "repair_path_next_gate_allowed": True,
        "recommended_next_action": "prepare_repair_execution_readiness_gate",
        "source_noop_status": "completed",
        "source_noop_exit_code": 0,
        "source_noop_only": True,
        "source_noop_stdout_marker_observed": True,
        "source_execution_performed": True,
        "source_subprocess_invoked": True,
        "source_envelope_status": "prepared",
        "source_dry_run_only": True,
        "source_repair_dry_run_mode": "repair_action_bundle_validation",
        "source_repair_dry_run_target_count": 9,
        "source_final_gate_ready_blocked": True,
        "source_transition_approved": True,
        "operator_authorized": True,
        "source_repair_actions_executed": False,
        "source_repair_bundle_executed": False,
        "source_repair_command_executed": False,
        "source_repair_execution_enabled": False,
        "source_repair_execution_performed": False,
        "source_repair_subprocess_invoked": False,
        "feedback_execution_performed": False,
        "feedback_subprocess_invoked": False,
        "ready_for_repair_execution": False,
        "would_execute": False,
        "bundle_execution_enabled": False,
        "repair_execution_enabled": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "bundle_execution_performed": False,
        "bundle_subprocess_invoked": False,
        "repair_execution_performed": False,
        "repair_subprocess_invoked": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "reason": "repair_execution_noop_feedback_recorded",
        "payload": {
            "feedback_execution_performed": False,
            "feedback_subprocess_invoked": False,
            "bundle_execution_enabled": False,
            "repair_execution_enabled": False,
            "real_execution_enabled": False,
            "subprocess_enabled": False,
            "bundle_execution_performed": False,
            "bundle_subprocess_invoked": False,
            "repair_execution_performed": False,
            "repair_subprocess_invoked": False,
            "execution_performed": False,
            "subprocess_invoked": False,
        },
    }
    item.update(overrides)
    return item


def test_validate_retry_real_execution_repair_noop_feedback_accepts_actionable_disabled() -> None:
    result = validate_replay_lifecycle_retry_real_execution_repair_noop_feedback(
        _real_execution_repair_noop_feedback()
    )

    assert result["valid"] is True
    assert result["feedback_status"] == "actionable"
    assert result["repair_noop_verified"] is True
    assert result["repair_path_can_proceed"] is True
    assert result["repair_path_next_gate_allowed"] is True
    assert result["repair_execution_enabled"] is False
    assert result["execution_performed"] is False
    assert result["subprocess_invoked"] is False


def test_validate_retry_real_execution_repair_noop_feedback_rejects_repair_execution_enabled() -> None:
    record = _real_execution_repair_noop_feedback(repair_execution_enabled=True)
    record["payload"]["repair_execution_enabled"] = True

    result = validate_replay_lifecycle_retry_real_execution_repair_noop_feedback(record)

    assert result["valid"] is False
    assert "repair_noop_feedback_must_not_enable_repair_execution" in result["reasons"]


def test_validate_retry_real_execution_repair_noop_feedback_rejects_feedback_subprocess() -> None:
    record = _real_execution_repair_noop_feedback(feedback_subprocess_invoked=True)
    record["payload"]["feedback_subprocess_invoked"] = True

    result = validate_replay_lifecycle_retry_real_execution_repair_noop_feedback(record)

    assert result["valid"] is False
    assert "repair_noop_feedback_must_not_invoke_feedback_subprocess" in result["reasons"]


def test_validate_retry_real_execution_repair_noop_feedback_rejects_source_repair_actions() -> None:
    result = validate_replay_lifecycle_retry_real_execution_repair_noop_feedback(
        _real_execution_repair_noop_feedback(source_repair_actions_executed=True)
    )

    assert result["valid"] is False
    assert (
        "repair_noop_feedback_source_must_not_execute_repair_actions"
        in result["reasons"]
    )


def test_validate_retry_real_execution_repair_noop_feedback_rejects_actionable_without_next_gate_allowed() -> None:
    result = validate_replay_lifecycle_retry_real_execution_repair_noop_feedback(
        _real_execution_repair_noop_feedback(
            repair_path_next_gate_allowed=False,
        )
    )

    assert result["valid"] is False
    assert (
        "actionable_repair_noop_feedback_requires_next_gate_allowed"
        in result["reasons"]
    )


def _real_execution_repair_readiness_gate(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_repair_readiness_gate",
        "real_execution_repair_readiness_gate_id": "repair-readiness-gate-1",
        "real_execution_repair_noop_feedback_id": "repair-feedback-1",
        "real_execution_repair_noop_result_id": "repair-noop-1",
        "real_execution_repair_dry_run_envelope_id": "repair-envelope-1",
        "real_execution_repair_final_gate_id": "repair-final-gate-1",
        "real_execution_repair_approval_transition_id": "repair-transition-1",
        "real_execution_repair_approval_id": "repair-approval-1",
        "rendered_command_id": "rendered-command-1",
        "gate_status": "ready_blocked",
        "repair_readiness_satisfied": True,
        "ready_for_guarded_repair_execution": True,
        "ready_for_repair_execution": False,
        "would_execute": False,
        "blocking_reasons": ["guarded_repair_execution_requires_separate_pr"],
        "recommended_next_action": "prepare_guarded_repair_execution_harness",
        "source_feedback_status": "actionable",
        "source_repair_noop_verified": True,
        "source_repair_path_can_proceed": True,
        "source_repair_path_next_gate_allowed": True,
        "source_noop_status": "completed",
        "source_noop_exit_code": 0,
        "source_noop_only": True,
        "source_noop_stdout_marker_observed": True,
        "source_execution_performed": True,
        "source_subprocess_invoked": True,
        "source_envelope_status": "prepared",
        "source_dry_run_only": True,
        "source_repair_dry_run_mode": "repair_action_bundle_validation",
        "source_repair_dry_run_target_count": 9,
        "source_final_gate_ready_blocked": True,
        "source_transition_approved": True,
        "operator_authorized": True,
        "source_repair_actions_executed": False,
        "source_repair_bundle_executed": False,
        "source_repair_command_executed": False,
        "source_repair_execution_enabled": False,
        "source_repair_execution_performed": False,
        "source_repair_subprocess_invoked": False,
        "bundle_execution_enabled": False,
        "repair_execution_enabled": False,
        "real_execution_enabled": False,
        "subprocess_enabled": False,
        "bundle_execution_performed": False,
        "bundle_subprocess_invoked": False,
        "repair_execution_performed": False,
        "repair_subprocess_invoked": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "reason": "repair_execution_readiness_gate_recorded",
        "payload": {
            "bundle_execution_enabled": False,
            "repair_execution_enabled": False,
            "real_execution_enabled": False,
            "subprocess_enabled": False,
            "bundle_execution_performed": False,
            "bundle_subprocess_invoked": False,
            "repair_execution_performed": False,
            "repair_subprocess_invoked": False,
            "execution_performed": False,
            "subprocess_invoked": False,
        },
    }
    item.update(overrides)
    return item


def test_validate_retry_real_execution_repair_readiness_gate_accepts_ready_blocked() -> None:
    result = validate_replay_lifecycle_retry_real_execution_repair_readiness_gate(
        _real_execution_repair_readiness_gate()
    )

    assert result["valid"] is True
    assert result["gate_status"] == "ready_blocked"
    assert result["repair_readiness_satisfied"] is True
    assert result["ready_for_guarded_repair_execution"] is True
    assert result["ready_for_repair_execution"] is False
    assert result["repair_execution_enabled"] is False
    assert result["execution_performed"] is False
    assert result["subprocess_invoked"] is False


def test_validate_retry_real_execution_repair_readiness_gate_rejects_repair_execution_enabled() -> None:
    record = _real_execution_repair_readiness_gate(repair_execution_enabled=True)
    record["payload"]["repair_execution_enabled"] = True

    result = validate_replay_lifecycle_retry_real_execution_repair_readiness_gate(record)

    assert result["valid"] is False
    assert "repair_readiness_gate_must_not_enable_repair_execution" in result["reasons"]


def test_validate_retry_real_execution_repair_readiness_gate_rejects_execution_performed() -> None:
    record = _real_execution_repair_readiness_gate(execution_performed=True)
    record["payload"]["execution_performed"] = True

    result = validate_replay_lifecycle_retry_real_execution_repair_readiness_gate(record)

    assert result["valid"] is False
    assert "repair_readiness_gate_must_not_execute" in result["reasons"]


def test_validate_retry_real_execution_repair_readiness_gate_rejects_source_repair_actions() -> None:
    result = validate_replay_lifecycle_retry_real_execution_repair_readiness_gate(
        _real_execution_repair_readiness_gate(source_repair_actions_executed=True)
    )

    assert result["valid"] is False
    assert (
        "repair_readiness_gate_source_must_not_execute_repair_actions"
        in result["reasons"]
    )


def test_validate_retry_real_execution_repair_readiness_gate_rejects_missing_separate_pr_blocker() -> None:
    result = validate_replay_lifecycle_retry_real_execution_repair_readiness_gate(
        _real_execution_repair_readiness_gate(blocking_reasons=[])
    )

    assert result["valid"] is False
    assert "repair_readiness_gate_requires_separate_pr_blocker" in result["reasons"]


def _sandbox_adapter_scaffold_record(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_sandbox_adapter_scaffold",
        "real_execution_sandbox_adapter_scaffold_id": "sandbox-scaffold-1",
        "real_execution_capability_policy_matrix_id": "matrix-1",
        "real_execution_adapter_request_schema_id": "request-schema-1",
        "real_execution_adapter_contract_id": "contract-1",
        "proposal_id": "proposal-1",
        "rendered_command_id": "rendered-1",
        "schema_version": "real-execution-sandbox-adapter-scaffold/v1",
        "sandbox_adapter_contract_version": "real-execution-sandbox-adapter/v1",
        "sandbox_adapter_scaffold_status": "defined",
        "sandbox_adapter_scaffold_kind": "fail_closed_sandbox_adapter_scaffold",
        "sandbox_workspace_strategy": "ephemeral_temp_workspace",
        "sandbox_input_strategy": "explicit_allowlist_only",
        "sandbox_output_strategy": "explicit_allowlist_only",
        "sandbox_rollback_strategy": "workspace_destruction",
        "sandbox_evidence_strategy": "post_execution_evidence_required",
        "sandbox_network_policy": "deny",
        "sandbox_secret_policy": "deny",
        "sandbox_filesystem_policy": "no_production_writes",
        "sandbox_production_write_policy": "deny",
        "sandbox_external_side_effect_policy": "deny",
        "sandbox_adapter_scaffold_exists": True,
        "sandbox_adapter_contract_exists": True,
        "sandbox_adapter_fail_closed": True,
        "sandbox_adapter_deny_by_default": True,
        "sandbox_adapter_requires_policy_matrix": True,
        "sandbox_adapter_requires_known_capability": True,
        "sandbox_adapter_requires_known_policy": True,
        "sandbox_adapter_requires_operator_authorization": True,
        "sandbox_adapter_requires_approval_lineage": True,
        "sandbox_adapter_requires_final_gate": True,
        "sandbox_adapter_requires_dry_run_envelope": True,
        "sandbox_adapter_requires_rollback_plan": True,
        "sandbox_adapter_requires_post_execution_evidence": True,
        "sandbox_adapter_rejects_unknown_capability": True,
        "sandbox_adapter_rejects_unknown_policy": True,
        "sandbox_adapter_rejects_orphans": True,
        "sandbox_adapter_rejects_stale_records": True,
        "source_capability_registry_exists": True,
        "source_policy_matrix_exists": True,
        "source_unknown_capability_rejected": True,
        "source_unknown_policy_rejected": True,
        "source_deny_by_default": True,
        "source_fail_closed_default": True,
        "source_sandbox_real_blocked": True,
        "source_policy_gated_real_blocked": True,
        "source_repair_outcome_verified": True,
        "source_capability_count": 7,
        "source_enabled_capability_count": 5,
        "source_blocked_capability_count": 2,
        "source_policy_rule_count": 7,
        "source_approved_policy_count": 5,
        "source_blocked_policy_count": 2,
        "sandbox_adapter_implementation_enabled": False,
        "sandbox_workspace_creation_enabled": False,
        "sandbox_input_materialization_enabled": False,
        "sandbox_command_rendering_enabled": False,
        "sandbox_execution_enabled": False,
        "sandbox_result_generation_enabled": False,
        "adapter_request_generation_enabled": False,
        "adapter_request_execution_enabled": False,
        "adapter_result_generation_enabled": False,
        "capability_execution_enabled": False,
        "policy_execution_enabled": False,
        "policy_gated_real_execution_enabled": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "real_execution_enabled": False,
        "external_side_effects_performed": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
        "source_capability_execution_enabled": False,
        "source_policy_execution_enabled": False,
        "source_adapter_request_generation_enabled": False,
        "source_sandbox_execution_enabled": False,
        "source_policy_gated_real_execution_enabled": False,
        "source_execution_performed": False,
        "source_subprocess_invoked": False,
        "source_real_execution_enabled": False,
        "source_external_side_effects_performed": False,
        "recommended_next_action": "surface_sandbox_adapter_scaffold_observability",
        "reason": "real_execution_sandbox_adapter_scaffold_defined_not_runnable",
    }
    item["payload"] = dict(item)
    item.update(overrides)
    return item


def test_validate_real_execution_sandbox_adapter_scaffold() -> None:
    result = validate_replay_lifecycle_retry_real_execution_sandbox_adapter_scaffold(
        _sandbox_adapter_scaffold_record()
    )

    assert result["valid"] is True
    assert result["severity"] == "info"
    assert result["reasons"] == []


def test_validate_real_execution_sandbox_adapter_scaffold_rejects_execution_enabled() -> None:
    result = validate_replay_lifecycle_retry_real_execution_sandbox_adapter_scaffold(
        _sandbox_adapter_scaffold_record(sandbox_execution_enabled=True)
    )

    assert result["valid"] is False
    assert result["severity"] == "critical"
    assert "sandbox_execution_enabled_must_be_false" in result["reasons"]


def _real_execution_sandbox_adapter_request_preflight(**overrides):
    item = {
        "type": "replay_lifecycle_retry_real_execution_sandbox_adapter_request_preflight",
        "real_execution_sandbox_adapter_request_preflight_id": "sandbox-preflight-1",
        "real_execution_sandbox_adapter_scaffold_id": "sandbox-scaffold-1",
        "real_execution_capability_policy_matrix_id": "matrix-1",
        "real_execution_adapter_request_schema_id": "request-schema-1",
        "real_execution_adapter_contract_id": "contract-1",
        "proposal_id": "proposal-1",
        "rendered_command_id": "rendered-1",
        "schema_version": "real-execution-sandbox-adapter-request-preflight/v1",
        "source_scaffold_schema_version": "real-execution-sandbox-adapter-scaffold/v1",
        "source_sandbox_adapter_contract_version": "real-execution-sandbox-adapter/v1",
        "source_scaffold_status": "defined",
        "sandbox_adapter_request_preflight_status": "blocked",
        "sandbox_adapter_request_preflight_kind": (
            "fail_closed_sandbox_adapter_request_preflight"
        ),
        "sandbox_adapter_request_preflight_exists": True,
        "sandbox_adapter_request_preflight_fail_closed": True,
        "sandbox_adapter_request_preflight_deny_by_default": True,
        "sandbox_adapter_request_preflight_requires_policy_matrix": True,
        "sandbox_adapter_request_preflight_requires_known_capability": True,
        "sandbox_adapter_request_preflight_requires_known_policy": True,
        "sandbox_adapter_request_preflight_requires_operator_authorization": True,
        "sandbox_adapter_request_preflight_requires_approval_lineage": True,
        "sandbox_adapter_request_preflight_requires_final_gate": True,
        "sandbox_adapter_request_preflight_requires_dry_run_envelope": True,
        "sandbox_adapter_request_preflight_requires_rollback_plan": True,
        "sandbox_adapter_request_preflight_requires_post_execution_evidence": True,
        "sandbox_adapter_request_preflight_rejects_unknown_capability": True,
        "sandbox_adapter_request_preflight_rejects_unknown_policy": True,
        "sandbox_adapter_request_preflight_rejects_orphans": True,
        "sandbox_adapter_request_preflight_rejects_stale_records": True,
        "source_scaffold_exists": True,
        "source_scaffold_fail_closed": True,
        "source_scaffold_deny_by_default": True,
        "sandbox_workspace_strategy": "ephemeral_temp_workspace",
        "sandbox_input_strategy": "explicit_allowlist_only",
        "sandbox_output_strategy": "explicit_allowlist_only",
        "sandbox_rollback_strategy": "workspace_destruction",
        "sandbox_evidence_strategy": "post_execution_evidence_required",
        "sandbox_network_policy": "deny",
        "sandbox_secret_policy": "deny",
        "sandbox_filesystem_policy": "no_production_writes",
        "sandbox_production_write_policy": "deny",
        "sandbox_external_side_effect_policy": "deny",
        "sandbox_adapter_request_generation_allowed": False,
        "sandbox_adapter_request_generation_enabled": False,
        "sandbox_workspace_creation_allowed": False,
        "sandbox_workspace_creation_enabled": False,
        "sandbox_input_materialization_allowed": False,
        "sandbox_input_materialization_enabled": False,
        "sandbox_command_rendering_allowed": False,
        "sandbox_command_rendering_enabled": False,
        "sandbox_execution_allowed": False,
        "sandbox_execution_enabled": False,
        "sandbox_result_generation_allowed": False,
        "sandbox_result_generation_enabled": False,
        "adapter_request_generation_enabled": False,
        "adapter_request_execution_enabled": False,
        "adapter_result_generation_enabled": False,
        "capability_execution_enabled": False,
        "policy_execution_enabled": False,
        "policy_gated_real_execution_enabled": False,
        "execution_performed": False,
        "subprocess_invoked": False,
        "real_execution_enabled": False,
        "external_side_effects_performed": False,
        "production_paths_mutated": False,
        "production_secrets_accessed": False,
        "source_scaffold_sandbox_execution_enabled": False,
        "source_scaffold_execution_performed": False,
        "source_scaffold_subprocess_invoked": False,
        "source_scaffold_real_execution_enabled": False,
        "source_scaffold_external_side_effects_performed": False,
        "source_scaffold_production_paths_mutated": False,
        "source_scaffold_production_secrets_accessed": False,
        "recommended_next_action": (
            "surface_sandbox_adapter_request_preflight_observability"
        ),
        "reason": "sandbox_adapter_request_preflight_defined_blocked_not_runnable",
    }
    item["payload"] = dict(item)
    item.update(overrides)
    return item


def test_validate_retry_real_execution_sandbox_adapter_request_preflight_accepts_blocked_fail_closed() -> None:
    result = (
        validate_replay_lifecycle_retry_real_execution_sandbox_adapter_request_preflight(
            _real_execution_sandbox_adapter_request_preflight()
        )
    )

    assert result["valid"] is True
    assert result["severity"] == "info"
    assert result["reasons"] == []
    assert result["sandbox_adapter_request_preflight_status"] == "blocked"
    assert result["sandbox_adapter_request_preflight_fail_closed"] is True
    assert result["sandbox_adapter_request_preflight_deny_by_default"] is True
    assert result["sandbox_execution_enabled"] is False
    assert result["execution_performed"] is False
    assert result["subprocess_invoked"] is False
    assert result["real_execution_enabled"] is False


def test_validate_retry_real_execution_sandbox_adapter_request_preflight_rejects_request_generation_enabled() -> None:
    record = _real_execution_sandbox_adapter_request_preflight(
        sandbox_adapter_request_generation_enabled=True
    )
    record["payload"]["sandbox_adapter_request_generation_enabled"] = True

    result = (
        validate_replay_lifecycle_retry_real_execution_sandbox_adapter_request_preflight(
            record
        )
    )

    assert result["valid"] is False
    assert result["severity"] == "critical"
    assert (
        "sandbox_adapter_request_generation_enabled_must_be_false"
        in result["reasons"]
    )
    assert (
        "payload_sandbox_adapter_request_generation_enabled_must_be_false"
        in result["reasons"]
    )


def test_validate_retry_real_execution_sandbox_adapter_request_preflight_rejects_workspace_creation_enabled() -> None:
    record = _real_execution_sandbox_adapter_request_preflight(
        sandbox_workspace_creation_enabled=True
    )
    record["payload"]["sandbox_workspace_creation_enabled"] = True

    result = (
        validate_replay_lifecycle_retry_real_execution_sandbox_adapter_request_preflight(
            record
        )
    )

    assert result["valid"] is False
    assert result["severity"] == "critical"
    assert "sandbox_workspace_creation_enabled_must_be_false" in result["reasons"]
    assert (
        "payload_sandbox_workspace_creation_enabled_must_be_false"
        in result["reasons"]
    )


def test_validate_retry_real_execution_sandbox_adapter_request_preflight_rejects_sandbox_execution_enabled() -> None:
    record = _real_execution_sandbox_adapter_request_preflight(
        sandbox_execution_enabled=True
    )
    record["payload"]["sandbox_execution_enabled"] = True

    result = (
        validate_replay_lifecycle_retry_real_execution_sandbox_adapter_request_preflight(
            record
        )
    )

    assert result["valid"] is False
    assert result["severity"] == "critical"
    assert "sandbox_execution_enabled_must_be_false" in result["reasons"]
    assert "payload_sandbox_execution_enabled_must_be_false" in result["reasons"]


def test_validate_retry_real_execution_sandbox_adapter_request_preflight_rejects_real_execution_enabled() -> None:
    record = _real_execution_sandbox_adapter_request_preflight(
        real_execution_enabled=True
    )
    record["payload"]["real_execution_enabled"] = True

    result = (
        validate_replay_lifecycle_retry_real_execution_sandbox_adapter_request_preflight(
            record
        )
    )

    assert result["valid"] is False
    assert result["severity"] == "critical"
    assert "real_execution_enabled_must_be_false" in result["reasons"]
    assert "payload_real_execution_enabled_must_be_false" in result["reasons"]