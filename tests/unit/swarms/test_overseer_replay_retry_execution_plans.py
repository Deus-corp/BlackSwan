import pytest

from src.swarms.overseer.overseer_core.replay_retry_execution_plans import (
    build_replay_lifecycle_retry_execution_plan,
)


def _proposal(**overrides):
    proposal = {
        "type": "replay_lifecycle_retry_proposal",
        "proposal_id": "replay-retry-test",
        "status": "pending",
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
    }
    proposal.update(overrides)
    return proposal


def _approval(**overrides):
    approval = {
        "type": "replay_lifecycle_retry_approval",
        "approval_id": "replay-retry-approval-test",
        "proposal_id": "replay-retry-test",
        "status": "approved",
        "approved_by": "operator",
        "decision_mode": "manual",
        "reason": "manual_runtime_validation",
        "execution_enabled": False,
    }
    approval.update(overrides)
    return approval


def test_build_replay_lifecycle_retry_execution_plan() -> None:
    plan = build_replay_lifecycle_retry_execution_plan(
        _proposal(),
        _approval(),
        source="overseer-test",
    )

    assert plan["type"] == "replay_lifecycle_retry_execution_plan"
    assert plan["status"] == "planned"
    assert plan["source"] == "overseer-test"
    assert plan["proposal_id"] == "replay-retry-test"
    assert plan["approval_id"] == "replay-retry-approval-test"
    assert plan["execution_enabled"] is False
    assert plan["timeout_profile"] == "standard"
    assert plan["decision_mode"] == "manual"
    assert "--timeout-profile standard" in plan["command_template"]


def test_build_replay_lifecycle_retry_execution_plan_rejects_mismatched_approval() -> None:
    with pytest.raises(ValueError, match="proposal_id"):
        build_replay_lifecycle_retry_execution_plan(
            _proposal(),
            _approval(proposal_id="other"),
        )


def test_build_replay_lifecycle_retry_execution_plan_rejects_rejected_approval() -> None:
    with pytest.raises(ValueError, match="approval status"):
        build_replay_lifecycle_retry_execution_plan(
            _proposal(),
            _approval(status="rejected"),
        )


def test_build_replay_lifecycle_retry_execution_plan_rejects_execution_enabled_approval() -> None:
    with pytest.raises(ValueError, match="execution_enabled"):
        build_replay_lifecycle_retry_execution_plan(
            _proposal(),
            _approval(execution_enabled=True),
        )


def test_build_replay_lifecycle_retry_execution_plan_rejects_fast_profile() -> None:
    with pytest.raises(ValueError, match="timeout_profile"):
        build_replay_lifecycle_retry_execution_plan(
            _proposal(timeout_profile="fast"),
            _approval(),
        )


def test_build_replay_lifecycle_retry_execution_plan_rejects_autonomous_decision_mode() -> None:
    with pytest.raises(ValueError, match="decision_mode"):
        build_replay_lifecycle_retry_execution_plan(
            _proposal(),
            _approval(decision_mode="autonomous"),
        )