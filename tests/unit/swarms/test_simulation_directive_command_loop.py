import asyncio

import pytest

from src.swarms.common.protocols.directives import build_directive
from src.swarms.simulation.node import SimulationSwarmNode


def replay_scenario() -> dict:
    return {
        "type": "simulation_replay_scenario",
        "scenario_id": "replay-runtime-reduce-risk-1",
        "status": "pending",
        "replay_kind": "runtime_evidence",
        "directive_id": "runtime-reduce-risk-1",
        "action": "REDUCE_RISK",
        "expected_result_status": "applied",
        "payload": {},
    }


class DummyCRDT:
    def __init__(self, directive: dict, *, include_scenario: bool = True) -> None:
        self.state = {"directive": directive}
        if include_scenario:
            self.state["scenario"] = replay_scenario()
        self.published = []

    def refresh_from_storage(self) -> int:
        return 1

    async def add_genome(self, payload: dict) -> None:
        self.published.append(payload)


def make_node(
    directive: dict,
    *,
    include_scenario: bool = True,
) -> SimulationSwarmNode:
    try:
        node = SimulationSwarmNode(node_id="simulation-test")
    except TypeError:
        node = SimulationSwarmNode()
        node.node_id = "simulation-test"

    node.crdt = DummyCRDT(directive, include_scenario=include_scenario)
    if not hasattr(node, "shutdown_event"):
        node.shutdown_event = asyncio.Event()
    if not hasattr(node, "_processed_directive_ids"):
        node._processed_directive_ids = set()
    return node


def run_replay_directive(directive_id: str = "run-replay-1") -> dict:
    return build_directive(
        directive_id=directive_id,
        action="RUN_REPLAY",
        source="overseer",
        target_type="swarm",
        target="simulation",
        payload={
            "scenario_id": "replay-runtime-reduce-risk-1",
            "dry_run": True,
        },
    ).to_dict()


@pytest.mark.asyncio
async def test_command_loop_once_consumes_run_replay_and_publishes_dry_run_records() -> None:
    node = make_node(run_replay_directive())

    processed = await node._command_loop_once()

    assert processed == 1
    assert len(node.crdt.published) == 2

    execution = node.crdt.published[0]
    result = node.crdt.published[1]

    assert execution["type"] == "simulation_replay_execution"
    assert execution["scenario_id"] == "replay-runtime-reduce-risk-1"
    assert execution["directive_id"] == "run-replay-1"
    assert execution["status"] == "completed"
    assert execution["source"] == "simulation-test"

    assert result["type"] == "swarm_directive_result"
    assert result["directive_id"] == "run-replay-1"
    assert result["status"] == "applied"
    assert result["payload"]["reason"] == "run_replay_dry_run_completed"
    assert result["payload"]["scenario_id"] == "replay-runtime-reduce-risk-1"
    assert result["payload"]["dry_run"] is True
    assert result["payload"]["execution"]["type"] == "simulation_replay_execution"
    assert result["payload"]["execution"]["status"] == "completed"


@pytest.mark.asyncio
async def test_command_loop_once_rejects_run_replay_when_scenario_missing() -> None:
    node = make_node(run_replay_directive(), include_scenario=False)

    processed = await node._command_loop_once()

    assert processed == 1
    assert len(node.crdt.published) == 1

    result = node.crdt.published[0]

    assert result["type"] == "swarm_directive_result"
    assert result["directive_id"] == "run-replay-1"
    assert result["status"] == "rejected"
    assert result["payload"]["reason"] == "run_replay_dry_run_failed"
    assert result["payload"]["scenario_id"] == "replay-runtime-reduce-risk-1"
    assert "not found" in result["payload"]["error"]


@pytest.mark.asyncio
async def test_command_loop_once_skips_already_processed_directive() -> None:
    directive = run_replay_directive("run-replay-processed")
    node = make_node(directive)
    node._processed_directive_ids.add("run-replay-processed")

    processed = await node._command_loop_once()

    assert processed == 0
    assert node.crdt.published == []