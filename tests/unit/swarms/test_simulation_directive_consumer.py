import pytest

from src.swarms.common.protocols.directives import build_directive
from src.swarms.simulation.directive_consumer import (
    apply_simulation_directive,
    directive_applies_to_simulation,
)

class DummyNode:
    node_id = "simulation-test"


class DummyCRDT:
    state = {
        "scenario": {
            "type": "simulation_replay_scenario",
            "scenario_id": "replay-runtime-reduce-risk-1",
            "status": "pending",
            "replay_kind": "runtime_evidence",
            "action": "REDUCE_RISK",
            "expected_result_status": "applied",
            "payload": {},
        }
    }


class DummyNodeWithScenario:
    node_id = "simulation-test"
    crdt = DummyCRDT()


def test_directive_applies_to_simulation_swarm_target() -> None:
    directive = build_directive(
        directive_id="observe-sim",
        action="OBSERVE",
        source="overseer",
        target_type="swarm",
        target="simulation",
    ).to_dict()

    assert directive_applies_to_simulation(directive) is True


def test_directive_does_not_apply_to_trade_target() -> None:
    directive = build_directive(
        directive_id="observe-trade",
        action="OBSERVE",
        source="overseer",
        target_type="swarm",
        target="trade",
    ).to_dict()

    assert directive_applies_to_simulation(directive) is False


@pytest.mark.asyncio
async def test_apply_simulation_observe_directive_acknowledges() -> None:
    directive = build_directive(
        directive_id="observe-sim",
        action="OBSERVE",
        source="overseer",
        target_type="swarm",
        target="simulation",
    ).to_dict()

    result = await apply_simulation_directive(DummyNode(), directive)

    assert result["type"] == "swarm_directive_result"
    assert result["directive_id"] == "observe-sim"
    assert result["status"] == "applied"
    assert result["swarm"] == "simulation"
    assert result["source"] == "simulation-test"
    assert result["payload"]["reason"] == "observe_acknowledged"


@pytest.mark.asyncio
async def test_apply_simulation_run_replay_rejects_when_scenario_missing() -> None:
    directive = build_directive(
        directive_id="run-replay-1",
        action="RUN_REPLAY",
        source="overseer",
        target_type="swarm",
        target="simulation",
        payload={
            "scenario_id": "replay-runtime-reduce-risk-1",
            "dry_run": True,
        },
    ).to_dict()

    result = await apply_simulation_directive(DummyNode(), directive)

    assert result["status"] == "rejected"
    assert result["payload"]["reason"] == "run_replay_dry_run_failed"
    assert result["payload"]["scenario_id"] == "replay-runtime-reduce-risk-1"


@pytest.mark.asyncio
async def test_apply_simulation_run_replay_rejects_missing_scenario_id() -> None:
    directive = build_directive(
        directive_id="run-replay-missing",
        action="RUN_REPLAY",
        source="overseer",
        target_type="swarm",
        target="simulation",
        payload={"dry_run": True},
    ).to_dict()

    result = await apply_simulation_directive(DummyNode(), directive)

    assert result["status"] == "rejected"
    assert result["payload"]["reason"] == "run_replay_missing_scenario_id"


@pytest.mark.asyncio
async def test_apply_simulation_run_replay_rejects_non_dry_run() -> None:
    directive = build_directive(
        directive_id="run-replay-live",
        action="RUN_REPLAY",
        source="overseer",
        target_type="swarm",
        target="simulation",
        payload={
            "scenario_id": "replay-runtime-reduce-risk-1",
            "dry_run": False,
        },
    ).to_dict()

    result = await apply_simulation_directive(DummyNode(), directive)

    assert result["status"] == "rejected"
    assert result["payload"]["reason"] == "run_replay_requires_dry_run"


@pytest.mark.asyncio
async def test_apply_simulation_unsupported_directive_is_ignored() -> None:
    directive = build_directive(
        directive_id="unsupported",
        action="SET_DRY_RUN",
        source="overseer",
        target_type="swarm",
        target="simulation",
        payload={},
    ).to_dict()

    result = await apply_simulation_directive(DummyNode(), directive)

    assert result["status"] == "ignored"
    assert result["payload"]["reason"] == "unsupported_simulation_directive"

@pytest.mark.asyncio
async def test_apply_simulation_run_replay_dry_run_completes_when_scenario_exists() -> None:
    directive = build_directive(
        directive_id="run-replay-1",
        action="RUN_REPLAY",
        source="overseer",
        target_type="swarm",
        target="simulation",
        payload={
            "scenario_id": "replay-runtime-reduce-risk-1",
            "dry_run": True,
        },
    ).to_dict()

    result = await apply_simulation_directive(DummyNodeWithScenario(), directive)

    assert result["status"] == "applied"
    assert result["payload"]["reason"] == "run_replay_dry_run_completed"
    assert result["payload"]["execution"]["type"] == "simulation_replay_execution"
    assert result["payload"]["execution"]["status"] == "completed"