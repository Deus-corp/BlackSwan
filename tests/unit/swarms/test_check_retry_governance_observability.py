import argparse
import asyncio

from src.testing.check_retry_governance_observability import (
    _exit_code_for_result,
    check_retry_governance_observability,
    check_retry_governance_observability_from_records,
)
from src.testing.seed_retry_governance_trail import seed_retry_governance_trail


def _proposal(**overrides):
    item = {
        "type": "replay_lifecycle_retry_proposal",
        "proposal_id": "proposal-1",
        "status": "pending",
        "recommendation": "retry_replay_lifecycle_check",
        "reason": "execution_not_observed_before_timeout",
        "timeout_profile": "standard",
        "command_template": (
            "python -m src.testing.run_replay_evidence_check "
            "--scenario-id <scenario_id> "
            "--directive-id <new_directive_id> "
            "--timeout-profile standard"
        ),
        "payload": {
            "recommendation": "retry_replay_lifecycle_check",
            "reason": "execution_not_observed_before_timeout",
            "timeout_profile": "standard",
        },
    }
    item.update(overrides)
    return item


def _approval(**overrides):
    item = {
        "type": "replay_lifecycle_retry_approval",
        "approval_id": "approval-1",
        "proposal_id": "proposal-1",
        "status": "approved",
        "approved_by": "operator",
        "decision_mode": "manual",
        "reason": "manual_runtime_validation",
        "execution_enabled": False,
        "payload": {
            "proposal_id": "proposal-1",
            "timeout_profile": "standard",
            "decision_mode": "manual",
            "command_template": (
                "python -m src.testing.run_replay_evidence_check "
                "--scenario-id <scenario_id> "
                "--directive-id <new_directive_id> "
                "--timeout-profile standard"
            ),
        },
    }
    item.update(overrides)
    return item


def _plan(**overrides):
    item = {
        "type": "replay_lifecycle_retry_execution_plan",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "status": "planned",
        "execution_enabled": False,
        "timeout_profile": "standard",
        "decision_mode": "manual",
        "command_template": (
            "python -m src.testing.run_replay_evidence_check "
            "--scenario-id <scenario_id> "
            "--directive-id <new_directive_id> "
            "--timeout-profile standard"
        ),
        "payload": {
            "proposal_id": "proposal-1",
            "approval_id": "approval-1",
            "timeout_profile": "standard",
            "decision_mode": "manual",
            "command_template": (
                "python -m src.testing.run_replay_evidence_check "
                "--scenario-id <scenario_id> "
                "--directive-id <new_directive_id> "
                "--timeout-profile standard"
            ),
        },
    }
    item.update(overrides)
    return item


def _rendered_command(**overrides):
    command = (
        "python -m src.testing.run_replay_evidence_check "
        "--scenario-id replay-render-test "
        "--directive-id runtime-run-replay-render-test "
        "--timeout-profile standard"
    )
    item = {
        "type": "replay_lifecycle_retry_rendered_command",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "status": "rendered",
        "execution_enabled": False,
        "timeout_profile": "standard",
        "decision_mode": "manual",
        "command": command,
        "payload": {
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
    item.update(overrides)
    return item


def _result(**overrides):
    item = {
        "type": "replay_lifecycle_retry_execution_result",
        "result_id": "result-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "rendered_command_id": "rendered-1",
        "status": "skipped",
        "reason": "execution_disabled",
        "execution_enabled": False,
        "payload": {
            "plan_id": "plan-1",
            "proposal_id": "proposal-1",
            "approval_id": "approval-1",
            "rendered_command_id": "rendered-1",
            "execution_enabled": False,
            "executed": False,
        },
    }
    item.update(overrides)
    return item


def test_check_retry_governance_observability_passes_for_full_trail() -> None:
    result = check_retry_governance_observability_from_records(
        [_proposal(), _approval(), _plan(), _rendered_command(), _result()]
    )

    assert result["status"] == "passed"
    assert _exit_code_for_result(result) == 0
    assert all(item["status"] == "passed" for item in result["checks"])
    assert result["brief_key_metrics"]["security_retry_proposals"] == 1
    assert result["brief_key_metrics"]["security_retry_approvals"] == 1
    assert result["brief_key_metrics"]["security_retry_execution_plans"] == 1
    assert result["brief_key_metrics"]["security_retry_rendered_commands"] == 1
    assert result["brief_key_metrics"]["security_retry_execution_results"] == 1
    assert result["brief_key_metrics"]["security_retry_execution_skipped"] == 1
    assert result["brief_key_metrics"]["security_retry_rendered_command_profiles"]["standard"] == 1


def test_check_retry_governance_observability_fails_for_missing_result() -> None:
    result = check_retry_governance_observability_from_records(
        [_proposal(), _approval(), _plan(), _rendered_command()]
    )

    assert result["status"] == "failed"
    assert _exit_code_for_result(result) == 1
    assert any(
        item["name"] == "security_observes_replay_lifecycle_retry_execution_result"
        and item["status"] == "failed"
        for item in result["checks"]
    )


def test_check_retry_governance_observability_filters_by_proposal_id() -> None:
    result = check_retry_governance_observability_from_records(
        [
            _proposal(proposal_id="proposal-1"),
            _approval(proposal_id="proposal-1"),
            _plan(proposal_id="proposal-1"),
            _rendered_command(proposal_id="proposal-1"),
            _result(proposal_id="proposal-1"),
            _proposal(proposal_id="proposal-2"),
        ],
        proposal_id="proposal-1",
    )

    assert result["status"] == "passed"
    assert result["brief_key_metrics"]["security_retry_proposals"] == 1
    assert result["brief_key_metrics"]["security_retry_rendered_commands"] == 1


def test_check_retry_governance_observability_reads_crdt(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")

    asyncio.run(
        seed_retry_governance_trail(
            argparse.Namespace(
                db_path=db_path,
                source="retry-governance-seed-test",
                proposal_id="proposal-1",
                approval_id="approval-1",
                plan_id="plan-1",
                rendered_command_id="rendered-1",
                result_id="result-1",
                timeout_profile="standard",
                decision_mode="manual",
            )
        )
    )

    result = check_retry_governance_observability(
        argparse.Namespace(
            db_path=db_path,
            proposal_id="proposal-1",
            json=False,
        )
    )

    assert result["status"] == "passed"
    assert result["brief_key_metrics"]["security_retry_rendered_commands"] == 1
    assert result["brief_key_metrics"]["security_retry_execution_skipped"] == 1


def test_check_retry_governance_observability_accepts_patient_rendered_profile() -> None:
    command = (
        "python -m src.testing.run_replay_evidence_check "
        "--scenario-id replay-render-test "
        "--directive-id runtime-run-replay-render-test "
        "--timeout-profile patient"
    )

    result = check_retry_governance_observability_from_records(
        [
            _proposal(timeout_profile="patient"),
            _approval(decision_mode="policy"),
            _plan(
                timeout_profile="patient",
                decision_mode="policy",
                command_template=(
                    "python -m src.testing.run_replay_evidence_check "
                    "--scenario-id <scenario_id> "
                    "--directive-id <new_directive_id> "
                    "--timeout-profile patient"
                ),
            ),
            _rendered_command(
                timeout_profile="patient",
                decision_mode="policy",
                command=command,
                payload={
                    "plan_id": "plan-1",
                    "proposal_id": "proposal-1",
                    "approval_id": "approval-1",
                    "timeout_profile": "patient",
                    "decision_mode": "policy",
                    "command": command,
                    "execution_enabled": False,
                    "executed": False,
                },
            ),
            _result(),
        ]
    )

    assert result["status"] == "passed"
    assert result["brief_key_metrics"]["security_retry_rendered_command_profiles"]["patient"] == 1