import pytest

from src.swarms.overseer.overseer_core.replay_retry_approvals import (
    build_replay_lifecycle_retry_approval,
)


def _proposal(**overrides):
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
    }
    proposal.update(overrides)
    return proposal


def test_build_replay_lifecycle_retry_approval() -> None:
    approval = build_replay_lifecycle_retry_approval(
        _proposal(),
        approved_by="operator",
        reason="retry_with_standard_timeout",
    )

    assert approval["type"] == "replay_lifecycle_retry_approval"
    assert approval["status"] == "approved"
    assert approval["proposal_id"] == "replay-retry-test"
    assert approval["approved_by"] == "operator"
    assert approval["execution_enabled"] is False
    assert approval["payload"]["timeout_profile"] == "standard"
    assert "--timeout-profile standard" in approval["payload"]["command_template"]


def test_build_replay_lifecycle_retry_rejection() -> None:
    approval = build_replay_lifecycle_retry_approval(
        _proposal(),
        approved_by="operator",
        status="rejected",
        reason="runtime_busy",
    )

    assert approval["status"] == "rejected"
    assert approval["reason"] == "runtime_busy"
    assert approval["execution_enabled"] is False


def test_build_replay_lifecycle_retry_approval_rejects_missing_proposal_id() -> None:
    with pytest.raises(ValueError, match="proposal_id"):
        build_replay_lifecycle_retry_approval(
            _proposal(proposal_id=""),
            approved_by="operator",
        )


def test_build_replay_lifecycle_retry_approval_rejects_invalid_status() -> None:
    with pytest.raises(ValueError, match="status"):
        build_replay_lifecycle_retry_approval(
            _proposal(),
            approved_by="operator",
            status="executing",
        )


def test_build_replay_lifecycle_retry_approval_requires_approved_by() -> None:
    with pytest.raises(ValueError, match="approved_by"):
        build_replay_lifecycle_retry_approval(
            _proposal(),
            approved_by="",
        )