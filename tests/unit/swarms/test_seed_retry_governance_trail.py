import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.inspect_retry_governance_trail import (
    inspect_retry_governance_trail_from_records,
)
from src.testing.seed_retry_governance_trail import _record_id, seed_retry_governance_trail


@pytest.mark.asyncio
async def test_seed_retry_governance_trail_builds_seed_chain(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")

    records = await seed_retry_governance_trail(
        argparse.Namespace(
            db_path=db_path,
            source="retry-governance-seed-test",
            proposal_id="proposal-test",
            approval_id="approval-test",
            plan_id="plan-test",
            rendered_command_id="rendered-command-test",
            result_id="result-test",
            timeout_profile="standard",
            decision_mode="manual",
        )
    )

    rendered = next(
        record
        for record in records
        if record["type"] == "replay_lifecycle_retry_rendered_command"
    )
    result = next(
        record
        for record in records
        if record["type"] == "replay_lifecycle_retry_execution_result"
    )

    assert rendered["rendered_command_id"] == "rendered-command-test"
    assert rendered["payload"]["rendered_command_id"] == "rendered-command-test"
    assert result["rendered_command_id"] == "rendered-command-test"
    assert result["payload"]["rendered_command_id"] == "rendered-command-test"

    assert [record["type"] for record in records] == [
        "replay_lifecycle_retry_proposal",
        "replay_lifecycle_retry_approval",
        "replay_lifecycle_retry_execution_plan",
        "replay_lifecycle_retry_rendered_command",
        "replay_lifecycle_retry_execution_result",
    ]

    summary = inspect_retry_governance_trail_from_records(records)

    assert summary["chain_complete"] is False
    assert summary["missing_stages"] == [
        "rendered_command_result",
        "execution_eligibility",
    ]
    assert summary["counts"]["proposals"] == 1
    assert summary["counts"]["approvals"] == 1
    assert summary["counts"]["plans"] == 1
    assert summary["counts"]["rendered_commands"] == 1
    assert summary["counts"]["results"] == 1
    assert summary["counts"]["rendered_command_results"] == 0
    assert summary["counts"]["eligibilities"] == 0

    assert summary["rendered_command_statuses"]["rendered"] == 1
    assert summary["rendered_command_profiles"]["standard"] == 1
    assert summary["result_statuses"]["skipped"] == 1
    assert summary["result_reasons"]["execution_disabled"] == 1

    assert summary["chain_ids"]["proposal_ids"] == ["proposal-test"]
    assert summary["chain_ids"]["approval_ids"] == ["approval-test"]
    assert summary["chain_ids"]["plan_ids"] == ["plan-test"]
    assert summary["chain_ids"]["rendered_command_ids"] == ["rendered-command-test"]
    assert summary["chain_ids"]["result_ids"] == ["result-test"]


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
            rendered_command_id="rendered-command-test",
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
            "replay_lifecycle_retry_rendered_command",
            "replay_lifecycle_retry_execution_result",
        }
    ]

    summary = inspect_retry_governance_trail_from_records(records)

    assert summary["chain_complete"] is False
    assert summary["missing_stages"] == [
        "rendered_command_result",
        "execution_eligibility",
    ]
    assert summary["counts"]["rendered_command_results"] == 0
    assert summary["counts"]["eligibilities"] == 0
    assert summary["decision_modes"]["policy"] == 3
    assert summary["rendered_command_profiles"]["patient"] == 1
    assert summary["chain_ids"]["proposal_ids"] == ["proposal-test"]
    assert summary["chain_ids"]["approval_ids"] == ["approval-test"]
    assert summary["chain_ids"]["plan_ids"] == ["plan-test"]
    assert summary["chain_ids"]["rendered_command_ids"] == ["rendered-command-test"]
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
                rendered_command_id="rendered-command-test",
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
                rendered_command_id="rendered-command-test",
                result_id="result-test",
                timeout_profile="standard",
                decision_mode="autonomous",
            )
        )


def test_seed_retry_governance_trail_record_id_is_type_aware() -> None:
    assert _record_id(
        {
            "type": "replay_lifecycle_retry_proposal",
            "proposal_id": "proposal-test",
        }
    ) == "proposal-test"

    assert _record_id(
        {
            "type": "replay_lifecycle_retry_approval",
            "proposal_id": "proposal-test",
            "approval_id": "approval-test",
        }
    ) == "approval-test"

    assert _record_id(
        {
            "type": "replay_lifecycle_retry_execution_plan",
            "proposal_id": "proposal-test",
            "approval_id": "approval-test",
            "plan_id": "plan-test",
        }
    ) == "plan-test"

    assert _record_id(
        {
            "type": "replay_lifecycle_retry_rendered_command",
            "proposal_id": "proposal-test",
            "approval_id": "approval-test",
            "plan_id": "plan-test",
            "rendered_command_id": "rendered-command-test",
        }
    ) == "rendered-command-test"

    assert _record_id(
        {
            "type": "replay_lifecycle_retry_execution_result",
            "proposal_id": "proposal-test",
            "approval_id": "approval-test",
            "plan_id": "plan-test",
            "rendered_command_id": "rendered-command-test",
            "result_id": "result-test",
        }
    ) == "result-test"


@pytest.mark.asyncio
async def test_seed_retry_governance_trail_skips_existing_records(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")

    args = argparse.Namespace(
        db_path=db_path,
        source="retry-governance-seed-test",
        proposal_id="proposal-test",
        approval_id="approval-test",
        plan_id="plan-test",
        rendered_command_id="rendered-command-test",
        result_id="result-test",
        timeout_profile="standard",
        decision_mode="manual",
    )

    first = await seed_retry_governance_trail(args)
    second = await seed_retry_governance_trail(args)

    assert len(first) == 5
    assert len(second) == 0

    reader = CRDTAdapter(node_id="reader", db_path=db_path)
    state = getattr(reader, "state", {}) or {}

    governance_records = [
        item
        for item in state.values()
        if isinstance(item, dict)
        and item.get("type")
        in {
            "replay_lifecycle_retry_proposal",
            "replay_lifecycle_retry_approval",
            "replay_lifecycle_retry_execution_plan",
            "replay_lifecycle_retry_rendered_command",
            "replay_lifecycle_retry_execution_result",
        }
    ]

    assert len(governance_records) == 5
    assert sorted(_record_id(item) for item in governance_records) == sorted(
        [
            "proposal-test",
            "approval-test",
            "plan-test",
            "rendered-command-test",
            "result-test",
        ]
    )