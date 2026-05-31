import asyncio

import pytest

from src.swarms.common.protocols.directives import build_directive
from src.swarms.simulation.node import SimulationSwarmNode


class DummyCRDT:
    def __init__(self, directive: dict) -> None:
        self.state = {"directive": directive}
        self.published = []

    def refresh_from_storage(self) -> int:
        return 1

    async def add_genome(self, payload: dict) -> None:
        self.published.append(payload)


def make_node(directive: dict) -> SimulationSwarmNode:
    try:
        node = SimulationSwarmNode(node_id="simulation-test")
    except TypeError:
        node = SimulationSwarmNode()
        node.node_id = "simulation-test"

    node.crdt = DummyCRDT(directive)
    if not hasattr(node, "shutdown_event"):
        node.shutdown_event = asyncio.Event()
    if not hasattr(node, "_processed_directive_ids"):
        node._processed_directive_ids = set()
    return node


@pytest.mark.asyncio
async def test_command_loop_once_consumes_run_replay_and_publishes_rejection() -> None:
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

    node = make_node(directive)

    processed = await node._command_loop_once()

    assert processed == 1
    assert node.crdt.published[0]["type"] == "swarm_directive_result"
    assert node.crdt.published[0]["directive_id"] == "run-replay-1"
    assert node.crdt.published[0]["status"] == "rejected"
    assert node.crdt.published[0]["payload"]["reason"] == "run_replay_execution_not_implemented"


@pytest.mark.asyncio
async def test_command_loop_once_skips_already_processed_directive() -> None:
    directive = build_directive(
        directive_id="run-replay-processed",
        action="RUN_REPLAY",
        source="overseer",
        target_type="swarm",
        target="simulation",
        payload={
            "scenario_id": "replay-runtime-reduce-risk-1",
            "dry_run": True,
        },
    ).to_dict()

    node = make_node(directive)
    node._processed_directive_ids.add("run-replay-processed")

    processed = await node._command_loop_once()

    assert processed == 0
    assert node.crdt.published == []