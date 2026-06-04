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