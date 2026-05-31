import asyncio
from collections.abc import Mapping

import pytest

from src.swarms.common.protocols.directives import (
    DirectiveStatus,
    build_directive,
)


class DummyCRDT:
    def __init__(self, directive: dict) -> None:
        self.state = {"directive": directive}
        self.published = []

    async def add_genome(self, payload):
        self.published.append(payload)


class DummyNode:
    def __init__(self, directive: dict) -> None:
        self.node_id = "trade-1"
        self.shutdown_event = asyncio.Event()
        self._processed_directive_ids = set()
        self.crdt = DummyCRDT(directive)

    async def process_command(self, command: Mapping) -> None:
        raise AssertionError("process_command should not be called for directives")

    async def process_directive(self, directive: Mapping) -> dict:
        self._processed_directive_ids.add(str(directive["directive_id"]))
        self.shutdown_event.set()
        return {
            "type": "swarm_directive_result",
            "directive_id": directive["directive_id"],
            "status": DirectiveStatus.APPLIED.value,
            "source": self.node_id,
            "swarm": "trade",
        }


@pytest.mark.asyncio
async def test_command_loop_consumes_swarm_directive_and_publishes_result() -> None:
    from src.swarms.trade.node_core.service import SwarmNode

    directive = build_directive(
        directive_id="dir-loop-1",
        action="REDUCE_RISK",
        source="overseer",
        target_type="swarm",
        target="trade",
    ).to_dict()

    node = DummyNode(directive)

    # Call the unbound implementation method against a lightweight dummy.
    await SwarmNode._command_loop_impl(node)

    assert node.crdt.published
    assert node.crdt.published[0]["type"] == "swarm_directive_result"
    assert node.crdt.published[0]["directive_id"] == "dir-loop-1"
    assert node.crdt.published[0]["status"] == DirectiveStatus.APPLIED.value


@pytest.mark.asyncio
async def test_command_loop_skips_already_processed_directive(monkeypatch) -> None:
    from src.swarms.trade.node_core.service import SwarmNode

    directive = build_directive(
        directive_id="dir-loop-processed",
        action="REDUCE_RISK",
        source="overseer",
        target_type="swarm",
        target="trade",
    ).to_dict()

    node = DummyNode(directive)
    node._processed_directive_ids.add("dir-loop-processed")

    async def fake_sleep(_seconds: float) -> None:
        node.shutdown_event.set()

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    await SwarmNode._command_loop_impl(node)

    assert node.crdt.published == []


@pytest.mark.asyncio
async def test_command_loop_skips_directive_targeted_to_other_swarm(monkeypatch) -> None:
    from src.swarms.trade.node_core.service import SwarmNode

    directive = build_directive(
        directive_id="dir-simulation-only",
        action="RUN_REPLAY",
        source="overseer",
        target_type="swarm",
        target="simulation",
        payload={
            "scenario_id": "replay-runtime-reduce-risk-1",
            "dry_run": True,
        },
    ).to_dict()

    node = DummyNode(directive)

    async def fake_sleep(_seconds: float) -> None:
        node.shutdown_event.set()

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    await SwarmNode._command_loop_impl(node)

    assert node.crdt.published == []
    assert "dir-simulation-only" not in node._processed_directive_ids