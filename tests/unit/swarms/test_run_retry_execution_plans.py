import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.run_retry_execution_plans import (
    build_retry_execution_result,
    run_retry_execution_plans,
)


def _plan(**overrides):
    plan = {
        "type": "replay_lifecycle_retry_execution_plan",
        "plan_id": "replay-retry-plan-test",
        "proposal_id": "replay-retry-proposal-test",
        "approval_id": "replay-retry-approval-test",
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
    }
    plan.update(overrides)
    return plan


def test_build_retry_execution_result_skips_disabled_plan() -> None:
    result = build_retry_execution_result(_plan())

    assert result["type"] == "replay_lifecycle_retry_execution_result"
    assert result["status"] == "skipped"
    assert result["reason"] == "execution_disabled"
    assert result["execution_enabled"] is False
    assert result["payload"]["executed"] is False


def test_build_retry_execution_result_rejects_enabled_plan_until_runner_supported() -> None:
    result = build_retry_execution_result(_plan(execution_enabled=True))

    assert result["status"] == "rejected"
    assert result["reason"] == "execution_not_supported"
    assert result["execution_enabled"] is True
    assert result["payload"]["executed"] is False


@pytest.mark.asyncio
async def test_run_retry_execution_plans_publishes_skipped_result(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_plan())

    results = await run_retry_execution_plans(
        argparse.Namespace(
            db_path=db_path,
            source="retry-plan-runner-test",
            plan_id="",
        )
    )

    assert len(results) == 1
    assert results[0]["status"] == "skipped"
    assert results[0]["reason"] == "execution_disabled"

    reader = CRDTAdapter(node_id="reader", db_path=db_path)
    state = getattr(reader, "state", {}) or {}
    stored = [
        item
        for item in state.values()
        if isinstance(item, dict)
        and item.get("type") == "replay_lifecycle_retry_execution_result"
    ]

    assert len(stored) == 1
    assert stored[0]["plan_id"] == "replay-retry-plan-test"


@pytest.mark.asyncio
async def test_run_retry_execution_plans_skips_duplicate_results(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")
    crdt = CRDTAdapter(node_id="seed", db_path=db_path)
    await crdt.add_genome(_plan())

    args = argparse.Namespace(
        db_path=db_path,
        source="retry-plan-runner-test",
        plan_id="",
    )

    first = await run_retry_execution_plans(args)
    second = await run_retry_execution_plans(args)

    assert len(first) == 1
    assert second == []