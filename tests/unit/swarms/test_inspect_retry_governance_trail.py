import argparse

from src.core.crdt_adapter import CRDTAdapter
from src.testing.inspect_retry_governance_trail import (
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


def _result(**overrides):
    item = {
        "type": "replay_lifecycle_retry_execution_result",
        "result_id": "result-1",
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


def test_inspect_retry_governance_trail_from_records_counts_chain() -> None:
    summary = inspect_retry_governance_trail_from_records(
        [
            _proposal(),
            _approval(),
            _plan(),
            _result(),
            {"type": "swarm_heartbeat"},
        ]
    )

    assert summary["total_records"] == 4
    assert summary["counts"]["proposals"] == 1
    assert summary["counts"]["approvals"] == 1
    assert summary["counts"]["plans"] == 1
    assert summary["counts"]["results"] == 1
    assert summary["approval_statuses"]["approved"] == 1
    assert summary["plan_statuses"]["planned"] == 1
    assert summary["result_statuses"]["skipped"] == 1
    assert summary["result_reasons"]["execution_disabled"] == 1
    assert summary["decision_modes"]["manual"] == 2
    assert summary["chain_ids"]["proposal_ids"] == ["proposal-1"]
    assert summary["chain_ids"]["approval_ids"] == ["approval-1"]
    assert summary["chain_ids"]["plan_ids"] == ["plan-1"]
    assert summary["chain_ids"]["result_ids"] == ["result-1"]
    assert summary["chain_complete"] is True
    assert summary["missing_stages"] == []


def test_inspect_retry_governance_trail_from_records_filters_by_plan_id() -> None:
    summary = inspect_retry_governance_trail_from_records(
        [
            _proposal(proposal_id="proposal-1"),
            _plan(plan_id="plan-1", proposal_id="proposal-1"),
            _result(result_id="result-1", plan_id="plan-1", proposal_id="proposal-1"),
            _plan(plan_id="plan-2", proposal_id="proposal-2"),
            _result(result_id="result-2", plan_id="plan-2", proposal_id="proposal-2"),
        ],
        plan_id="plan-1",
    )

    assert summary["counts"]["plans"] == 1
    assert summary["counts"]["results"] == 1
    assert summary["chain_ids"]["plan_ids"] == ["plan-1"]


def test_inspect_retry_governance_trail_from_crdt(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)

    import asyncio

    async def seed():
        await crdt.add_genome(_proposal())
        await crdt.add_genome(_approval())
        await crdt.add_genome(_plan())
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
    assert summary["counts"]["results"] == 1


def test_inspect_retry_governance_trail_reports_missing_stages() -> None:
    summary = inspect_retry_governance_trail_from_records([_proposal()])

    assert summary["chain_complete"] is False
    assert summary["missing_stages"] == ["approval", "plan", "result"]