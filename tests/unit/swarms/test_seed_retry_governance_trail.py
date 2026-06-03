import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.inspect_retry_governance_trail import (
    inspect_retry_governance_trail_from_records,
)
from src.testing.seed_retry_governance_trail import seed_retry_governance_trail


@pytest.mark.asyncio
async def test_seed_retry_governance_trail_builds_complete_chain(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")

    records = await seed_retry_governance_trail(
        argparse.Namespace(
            db_path=db_path,
            source="retry-governance-seed-test",
            proposal_id="proposal-test",
            approval_id="approval-test",
            plan_id="plan-test",
            result_id="result-test",
            timeout_profile="standard",
            decision_mode="manual",
        )
    )

    assert [record["type"] for record in records] == [
        "replay_lifecycle_retry_proposal",
        "replay_lifecycle_retry_approval",
        "replay_lifecycle_retry_execution_plan",
        "replay_lifecycle_retry_execution_result",
    ]

    summary = inspect_retry_governance_trail_from_records(records)

    assert summary["chain_complete"] is True
    assert summary["missing_stages"] == []
    assert summary["counts"]["proposals"] == 1
    assert summary["counts"]["approvals"] == 1
    assert summary["counts"]["plans"] == 1
    assert summary["counts"]["results"] == 1
    assert summary["result_statuses"]["skipped"] == 1
    assert summary["result_reasons"]["execution_disabled"] == 1


@pytest.mark.asyncio
async def test_seed_retry_governance_trail_publishes_to_crdt(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")

    await seed_retry_governance_trail(
        argparse.Namespace(
            db_path=db_path,
            source="retry-governance-seed-test",
            proposal_id="proposal-test",
            approval_id="approval-test",
            plan_id="plan-test",
            result_id="result-test",
            timeout_profile="patient",
            decision_mode="policy",
        )
    )

    reader = CRDTAdapter(node_id="reader", db_path=db_path)
    state = getattr(reader, "state", {}) or {}

    records = [
        item
        for item in state.values()
        if isinstance(item, dict)
        and item.get("type")
        in {
            "replay_lifecycle_retry_proposal",
            "replay_lifecycle_retry_approval",
            "replay_lifecycle_retry_execution_plan",
            "replay_lifecycle_retry_execution_result",
        }
    ]

    summary = inspect_retry_governance_trail_from_records(records)

    assert summary["chain_complete"] is True
    assert summary["decision_modes"]["policy"] == 2
    assert summary["chain_ids"]["proposal_ids"] == ["proposal-test"]
    assert summary["chain_ids"]["approval_ids"] == ["approval-test"]
    assert summary["chain_ids"]["plan_ids"] == ["plan-test"]
    assert summary["chain_ids"]["result_ids"] == ["result-test"]


@pytest.mark.asyncio
async def test_seed_retry_governance_trail_rejects_fast_profile(tmp_path) -> None:
    with pytest.raises(ValueError, match="timeout_profile"):
        await seed_retry_governance_trail(
            argparse.Namespace(
                db_path=str(tmp_path / "crdt.db"),
                source="retry-governance-seed-test",
                proposal_id="proposal-test",
                approval_id="approval-test",
                plan_id="plan-test",
                result_id="result-test",
                timeout_profile="fast",
                decision_mode="manual",
            )
        )


@pytest.mark.asyncio
async def test_seed_retry_governance_trail_rejects_autonomous_decision_mode(tmp_path) -> None:
    with pytest.raises(ValueError, match="decision_mode"):
        await seed_retry_governance_trail(
            argparse.Namespace(
                db_path=str(tmp_path / "crdt.db"),
                source="retry-governance-seed-test",
                proposal_id="proposal-test",
                approval_id="approval-test",
                plan_id="plan-test",
                result_id="result-test",
                timeout_profile="standard",
                decision_mode="autonomous",
            )
        )