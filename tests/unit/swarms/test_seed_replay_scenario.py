import argparse

import pytest

from src.core.crdt_adapter import CRDTAdapter
from src.testing.seed_replay_scenario import SAFE_REPLAY_ACTIONS, seed_replay_scenario


@pytest.mark.asyncio
async def test_seed_replay_scenario_writes_scenario_to_crdt(tmp_path) -> None:
    db_path = str(tmp_path / "crdt.db")

    args = argparse.Namespace(
        scenario_id="replay-test-1",
        action="REDUCE_RISK",
        expected_result_status="applied",
        source="scenario-seed-test",
        directive_id="runtime-reduce-risk-1",
        db_path=db_path,
    )

    scenario = await seed_replay_scenario(args)

    assert scenario["type"] == "simulation_replay_scenario"
    assert scenario["scenario_id"] == "replay-test-1"
    assert scenario["status"] == "pending"
    assert scenario["action"] == "REDUCE_RISK"
    assert scenario["expected_result_status"] == "applied"
    assert scenario["payload"]["seeded"] is True
    assert scenario["payload"]["runtime_check"] is True

    reader = CRDTAdapter(node_id="reader", db_path=db_path)
    state = getattr(reader, "state", {}) or {}
    scenarios = [
        item
        for item in state.values()
        if isinstance(item, dict)
        and item.get("type") == "simulation_replay_scenario"
        and item.get("scenario_id") == "replay-test-1"
    ]

    assert len(scenarios) == 1
    assert scenarios[0]["source"] == "scenario-seed-test"


@pytest.mark.asyncio
async def test_seed_replay_scenario_rejects_unsafe_action(tmp_path) -> None:
    args = argparse.Namespace(
        scenario_id="replay-test-unsafe",
        action="LIVE_TRADE",
        expected_result_status="applied",
        source="scenario-seed-test",
        directive_id="runtime-live-trade-1",
        db_path=str(tmp_path / "crdt.db"),
    )

    with pytest.raises(ValueError, match="Unsafe replay action"):
        await seed_replay_scenario(args)


def test_safe_replay_actions_include_reduce_risk() -> None:
    assert "REDUCE_RISK" in SAFE_REPLAY_ACTIONS