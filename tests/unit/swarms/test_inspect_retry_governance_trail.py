import argparse

from src.core.crdt_adapter import CRDTAdapter
from src.testing.inspect_retry_governance_trail import (
    _exit_code_for_summary,
    inspect_retry_governance_trail,
    inspect_retry_governance_trail_from_records,
)


def _proposal(**overrides):
    item = {
        "type": "replay_lifecycle_retry_proposal",
        "proposal_id": "proposal-1",
        "status": "pending",
        "timeout_profile": "standard",
    }
    item.update(overrides)
    return item


def _approval(**overrides):
    item = {
        "type": "replay_lifecycle_retry_approval",
        "approval_id": "approval-1",
        "proposal_id": "proposal-1",
        "status": "approved",
        "decision_mode": "manual",
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
        "decision_mode": "manual",
        "execution_enabled": False,
    }
    item.update(overrides)
    return item


def _rendered_command(**overrides):
    item = {
        "type": "replay_lifecycle_retry_rendered_command",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "status": "rendered",
        "timeout_profile": "standard",
        "decision_mode": "manual",
    }
    item.update(overrides)
    return item


def _rendered_command_result(**overrides):
    item = {
        "type": "replay_lifecycle_retry_rendered_command_result",
        "rendered_command_result_id": "rendered-result-1",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "status": "skipped",
        "reason": "execution_disabled",
        "execution_enabled": False,
        "payload": {"executed": False},
    }
    item.update(overrides)
    return item

def _eligibility(**overrides):
    item = {
        "type": "replay_lifecycle_retry_execution_eligibility",
        "eligibility_id": "eligibility-1",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "status": "blocked",
        "reason": "execution_disabled",
        "execution_supported": False,
        "execution_enabled": False,
        "payload": {
            "status": "blocked",
            "reason": "execution_disabled",
            "execution_supported": False,
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
            "rendered_command_id": "rendered-1",
            "executed": False,
        },
    }
    item.update(overrides)
    return item


def test_inspect_retry_governance_trail_from_records_counts_chain() -> None:
    summary = inspect_retry_governance_trail_from_records(
        [
            _proposal(),
            _approval(),
            _plan(),
            _rendered_command(),
            _rendered_command_result(),
            _eligibility(),
            _result(),
            {"type": "swarm_heartbeat"},
        ]
    )

    assert summary["total_records"] == 7
    assert summary["counts"]["proposals"] == 1
    assert summary["counts"]["approvals"] == 1
    assert summary["counts"]["plans"] == 1
    assert summary["counts"]["rendered_commands"] == 1
    assert summary["counts"]["rendered_command_results"] == 1
    assert summary["counts"]["results"] == 1
    assert summary["counts"]["eligibilities"] == 1

    assert summary["approval_statuses"]["approved"] == 1
    assert summary["plan_statuses"]["planned"] == 1
    assert summary["rendered_command_statuses"]["rendered"] == 1
    assert summary["rendered_command_profiles"]["standard"] == 1
    assert summary["rendered_command_result_statuses"]["skipped"] == 1
    assert summary["rendered_command_result_reasons"]["execution_disabled"] == 1
    assert summary["result_statuses"]["skipped"] == 1
    assert summary["result_reasons"]["execution_disabled"] == 1
    assert summary["eligibility_statuses"]["blocked"] == 1
    assert summary["eligibility_reasons"]["execution_disabled"] == 1

    assert summary["decision_modes"]["manual"] == 3

    assert summary["chain_ids"]["proposal_ids"] == ["proposal-1"]
    assert summary["chain_ids"]["approval_ids"] == ["approval-1"]
    assert summary["chain_ids"]["plan_ids"] == ["plan-1"]
    assert summary["chain_ids"]["rendered_command_ids"] == ["rendered-1"]
    assert summary["chain_ids"]["rendered_command_result_ids"] == ["rendered-result-1"]
    assert summary["chain_ids"]["result_ids"] == ["result-1"]
    assert summary["chain_ids"]["eligibility_ids"] == ["eligibility-1"]

    assert summary["chain_complete"] is True
    assert summary["missing_stages"] == []


def test_inspect_retry_governance_trail_from_records_filters_by_plan_id() -> None:
    summary = inspect_retry_governance_trail_from_records(
        [
            _proposal(proposal_id="proposal-1"),
            _plan(plan_id="plan-1", proposal_id="proposal-1"),
            _rendered_command(
                rendered_command_id="rendered-1",
                plan_id="plan-1",
                proposal_id="proposal-1",
            ),
            _rendered_command_result(
                rendered_command_result_id="rendered-result-1",
                rendered_command_id="rendered-1",
                plan_id="plan-1",
                proposal_id="proposal-1",
            ),
            _result(
                result_id="result-1",
                plan_id="plan-1",
                proposal_id="proposal-1",
                rendered_command_id="rendered-1",
            ),
            _eligibility(
                eligibility_id="eligibility-1",
                rendered_command_id="rendered-1",
                plan_id="plan-1",
                proposal_id="proposal-1",
            ),
            _plan(plan_id="plan-2", proposal_id="proposal-2"),
            _rendered_command(
                rendered_command_id="rendered-2",
                plan_id="plan-2",
                proposal_id="proposal-2",
            ),
            _rendered_command_result(
                rendered_command_result_id="rendered-result-2",
                rendered_command_id="rendered-2",
                plan_id="plan-2",
                proposal_id="proposal-2",
            ),
            _result(
                result_id="result-2",
                plan_id="plan-2",
                proposal_id="proposal-2",
                rendered_command_id="rendered-2",
            ),
            _eligibility(
                eligibility_id="eligibility-2",
                rendered_command_id="rendered-2",
                plan_id="plan-2",
                proposal_id="proposal-2",
            ),
        ],
        plan_id="plan-1",
    )

    assert summary["counts"]["plans"] == 1
    assert summary["counts"]["rendered_commands"] == 1
    assert summary["counts"]["rendered_command_results"] == 1
    assert summary["counts"]["results"] == 1
    assert summary["counts"]["eligibilities"] == 1
    assert summary["chain_ids"]["plan_ids"] == ["plan-1"]
    assert summary["chain_ids"]["rendered_command_ids"] == ["rendered-1"]
    assert summary["chain_ids"]["rendered_command_result_ids"] == ["rendered-result-1"]
    assert summary["chain_ids"]["eligibility_ids"] == ["eligibility-1"]


def test_inspect_retry_governance_trail_from_crdt(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)

    import asyncio

    async def seed():
        await crdt.add_genome(_proposal())
        await crdt.add_genome(_approval())
        await crdt.add_genome(_plan())
        await crdt.add_genome(_rendered_command())
        await crdt.add_genome(_rendered_command_result())
        await crdt.add_genome(_eligibility())
        await crdt.add_genome(_result())

    asyncio.run(seed())

    summary = inspect_retry_governance_trail(
        argparse.Namespace(
            db_path=db_path,
            proposal_id="",
            approval_id="",
            plan_id="",
        )
    )

    assert summary["counts"]["proposals"] == 1
    assert summary["counts"]["approvals"] == 1
    assert summary["counts"]["plans"] == 1
    assert summary["counts"]["rendered_commands"] == 1
    assert summary["counts"]["rendered_command_results"] == 1
    assert summary["counts"]["results"] == 1
    assert summary["counts"]["eligibilities"] == 1
    assert summary["chain_complete"] is True


def test_inspect_retry_governance_trail_reports_missing_stages() -> None:
    summary = inspect_retry_governance_trail_from_records([_proposal()])

    assert summary["chain_complete"] is False
    assert summary["missing_stages"] == [
        "approval",
        "plan",
        "rendered_command",
        "rendered_command_result",
        "execution_eligibility",
        "result",
    ]


def test_retry_governance_trail_exit_code_is_zero_by_default_when_incomplete() -> None:
    summary = inspect_retry_governance_trail_from_records([_proposal()])

    assert summary["chain_complete"] is False
    assert _exit_code_for_summary(summary, require_complete=False) == 0


def test_retry_governance_trail_exit_code_is_one_when_require_complete_and_incomplete() -> None:
    summary = inspect_retry_governance_trail_from_records([_proposal()])

    assert summary["chain_complete"] is False
    assert _exit_code_for_summary(summary, require_complete=True) == 1


def test_retry_governance_trail_exit_code_is_zero_when_require_complete_and_complete() -> None:
    summary = inspect_retry_governance_trail_from_records(
        [
            _proposal(),
            _approval(),
            _plan(),
            _rendered_command(),
            _rendered_command_result(),
            _eligibility(),
            _result(),
        ]
    )

    assert summary["chain_complete"] is True
    assert _exit_code_for_summary(summary, require_complete=True) == 0


def _controlled_execution_result(**overrides):
    item = {
        "type": "replay_lifecycle_retry_controlled_execution_result",
        "controlled_execution_result_id": "controlled-result-1",
        "rendered_command_id": "rendered-1",
        "plan_id": "plan-1",
        "proposal_id": "proposal-1",
        "approval_id": "approval-1",
        "status": "rejected",
        "reason": "controlled_execution_not_implemented",
        "execution_enabled": False,
        "operator_authorized": False,
        "allowlist_matched": False,
        "payload": {"executed": False},
    }
    item.update(overrides)
    return item


def test_inspect_retry_governance_trail_counts_controlled_execution_extension() -> None:
    summary = inspect_retry_governance_trail_from_records(
        [
            _proposal(),
            _approval(),
            _plan(),
            _rendered_command(),
            _rendered_command_result(),
            _eligibility(),
            _result(),
            _controlled_execution_result(),
        ]
    )

    assert summary["chain_complete"] is True
    assert summary["missing_stages"] == []
    assert summary["total_records"] == 8
    assert summary["counts"]["controlled_execution_results"] == 1
    assert summary["extended_controlled_execution_observed"] is True
    assert summary["controlled_execution_result_statuses"]["rejected"] == 1
    assert (
        summary["controlled_execution_result_reasons"][
            "controlled_execution_not_implemented"
        ]
        == 1
    )
    assert summary["chain_ids"]["controlled_execution_result_ids"] == [
        "controlled-result-1"
    ]


def test_inspect_retry_governance_trail_does_not_require_controlled_execution_result() -> None:
    summary = inspect_retry_governance_trail_from_records(
        [
            _proposal(),
            _approval(),
            _plan(),
            _rendered_command(),
            _rendered_command_result(),
            _eligibility(),
            _result(),
        ]
    )

    assert summary["chain_complete"] is True
    assert summary["missing_stages"] == []
    assert summary["counts"]["controlled_execution_results"] == 0
    assert summary["extended_controlled_execution_observed"] is False
    assert summary["chain_ids"]["controlled_execution_result_ids"] == []