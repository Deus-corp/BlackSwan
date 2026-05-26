from __future__ import annotations

import asyncio
from typing import Any, Dict, List

import pytest

from src.swarms.trade.node import SwarmNode


class FakeCRDT:
    def __init__(self) -> None:
        self.state: Dict[str, Dict[str, Any]] = {}
        self.events: List[Dict[str, Any]] = []

    async def add_genome(self, item: Dict[str, Any]) -> None:
        self.events.append(item)

    async def close(self) -> None:
        pass


def make_node() -> SwarmNode:
    node = SwarmNode()
    node.crdt = FakeCRDT()
    node.ctx.crdt = node.crdt

    # Keep tests isolated from any real runtime resources.
    node.tradingview_enabled = False
    node.tradingview_webhook = None
    node.market_adapter = None
    node.telegram_notifier = None

    return node


@pytest.mark.asyncio
async def test_trade_pause_resume_commands_toggle_paused_state():
    node = make_node()

    assert node._paused is False

    await node.process_command(
        {
            "type": "swarm_command",
            "gid": "cmd-pause",
            "command_type": "PAUSE",
            "target_swarm": "trade",
            "target_node": node.node_id,
        }
    )

    assert node._paused is True

    await node.process_command(
        {
            "type": "swarm_command",
            "gid": "cmd-resume",
            "command_type": "RESUME",
            "target_swarm": "trade",
            "target_node": node.node_id,
        }
    )

    assert node._paused is False

    event_types = [event.get("event_type") for event in node.crdt.events]
    assert event_types == ["command_applied", "command_applied"]


@pytest.mark.asyncio
async def test_trade_set_dry_run_forces_execution_disabled():
    node = make_node()

    node.trade_config = node.trade_config.__class__(
        **{
            field: getattr(node.trade_config, field)
            for field in node.trade_config.__dataclass_fields__
        }
    )
    node.trade_config = node.trade_config.__class__(
        **{
            **{
                field: getattr(node.trade_config, field)
                for field in node.trade_config.__dataclass_fields__
            },
            "execution_enabled": True,
            "dry_run": False,
        }
    )
    node.ctx.config = node.trade_config

    await node.process_command(
        {
            "type": "swarm_command",
            "gid": "cmd-dry-run",
            "command_type": "SET_DRY_RUN",
            "target_swarm": "trade",
            "target_node": node.node_id,
            "payload": {"enabled": True},
        }
    )

    assert node.trade_config.dry_run is True
    assert node.trade_config.execution_enabled is False
    assert node.ctx.config is node.trade_config

    event = node.crdt.events[-1]
    assert event["event_type"] == "command_applied"
    assert event["payload"]["dry_run"] is True
    assert event["payload"]["execution_enabled"] is False


@pytest.mark.asyncio
async def test_trade_set_execution_enabled_without_approval_is_blocked():
    node = make_node()

    assert node.trade_config.execution_enabled is False
    assert node.trade_config.dry_run is True

    await node.process_command(
        {
            "type": "swarm_command",
            "gid": "cmd-enable-blocked",
            "command_type": "SET_EXECUTION_ENABLED",
            "target_swarm": "trade",
            "target_node": node.node_id,
            "payload": {"enabled": True},
        }
    )

    assert node.trade_config.execution_enabled is False
    assert node.trade_config.dry_run is True

    event = node.crdt.events[-1]
    assert event["event_type"] == "command_blocked"
    assert event["payload"]["reason"] == "explicit_approval_required"


@pytest.mark.asyncio
async def test_trade_set_execution_enabled_with_approval_is_applied():
    node = make_node()

    await node.process_command(
        {
            "type": "swarm_command",
            "gid": "cmd-enable-approved",
            "command_type": "SET_EXECUTION_ENABLED",
            "target_swarm": "trade",
            "target_node": node.node_id,
            "payload": {
                "enabled": True,
                "explicit_approval": True,
                "safety_gate": "approved",
            },
        }
    )

    assert node.trade_config.execution_enabled is True
    assert node.trade_config.dry_run is False
    assert node.ctx.config is node.trade_config

    event = node.crdt.events[-1]
    assert event["event_type"] == "command_applied"
    assert event["payload"]["execution_enabled"] is True
    assert event["payload"]["dry_run"] is False


@pytest.mark.asyncio
async def test_trade_set_execution_disabled_returns_to_dry_run():
    node = make_node()

    await node.process_command(
        {
            "type": "swarm_command",
            "gid": "cmd-enable-approved-first",
            "command_type": "SET_EXECUTION_ENABLED",
            "target_swarm": "trade",
            "target_node": node.node_id,
            "payload": {
                "enabled": True,
                "explicit_approval": True,
                "safety_gate": "approved",
            },
        }
    )

    assert node.trade_config.execution_enabled is True
    assert node.trade_config.dry_run is False

    await node.process_command(
        {
            "type": "swarm_command",
            "gid": "cmd-disable",
            "command_type": "SET_EXECUTION_ENABLED",
            "target_swarm": "trade",
            "target_node": node.node_id,
            "payload": {"enabled": False},
        }
    )

    assert node.trade_config.execution_enabled is False
    assert node.trade_config.dry_run is True

    event = node.crdt.events[-1]
    assert event["event_type"] == "command_applied"
    assert event["payload"]["execution_enabled"] is False
    assert event["payload"]["dry_run"] is True


@pytest.mark.asyncio
async def test_trade_restart_command_requests_shutdown():
    node = make_node()

    assert node.shutdown_event.is_set() is False

    await node.process_command(
        {
            "type": "trade_command",
            "gid": "cmd-restart",
            "command_type": "RESTART_NODE",
            "target_swarm": "trade",
            "target_node": node.node_id,
        }
    )

    assert node.shutdown_event.is_set() is True
    assert node.crdt.events[-1]["event_type"] == "command_applied"
    assert node.crdt.events[-1]["payload"]["status"] == "shutdown_requested"


@pytest.mark.asyncio
async def test_trade_command_loop_processes_crdt_commands():
    node = make_node()

    node.crdt.state["cmd-pause-loop"] = {
        "type": "swarm_command",
        "gid": "cmd-pause-loop",
        "command_type": "PAUSE",
        "target_swarm": "trade",
        "target_node": node.node_id,
    }

    task = asyncio.create_task(node._command_loop())

    for _ in range(20):
        if node._paused:
            break
        await asyncio.sleep(0.1)

    node.shutdown_event.set()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert node._paused is True
    assert node.crdt.events[-1]["event_type"] == "command_applied"
