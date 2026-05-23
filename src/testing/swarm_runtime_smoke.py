#!/usr/bin/env python3
"""Smoke tests for shared swarm runtime integration.

Run from repository root:

    python -m src.testing.swarm_runtime_smoke

This is intentionally lightweight and does not require pytest.
It verifies that the ongoing swarm refactor still preserves:
- common runtime imports
- topology gates
- command normalization
- security command dedup
- explorer command dedup
- improver dry-cycle behavior
- overseer executor advisory gates
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List

from src.swarms.common import (
    BaseSwarmMetaAgent,
    BaseSwarmNode,
    BaseSwarmOverseer,
    command_requires_explicit_gate,
    known_swarms,
    make_swarm_command,
    normalize_commands,
)
from src.swarms.explorer.node import ExplorerNode
from src.swarms.improver.improver_agent import ImproverAgent
from src.swarms.overseer.overseer_core.executor import ActionExecutor
from src.swarms.overseer.overseer_core.models import OverseerDecision, SwarmSnapshot
from src.swarms.security.node import SecurityNode


class MemorySink:
    """Simple async command sink for executor tests."""

    def __init__(self) -> None:
        self.items: List[Dict[str, Any]] = []

    async def add_genome(self, genome: Dict[str, Any]) -> None:
        self.items.append(genome)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def check_common_runtime() -> None:
    assert_true(BaseSwarmNode is not None, "BaseSwarmNode import failed")
    assert_true(BaseSwarmMetaAgent is not None, "BaseSwarmMetaAgent import failed")
    assert_true(BaseSwarmOverseer is not None, "BaseSwarmOverseer import failed")

    swarms = known_swarms()
    assert_true("security" in swarms, "security missing from topology")
    assert_true("explorer" in swarms, "explorer missing from topology")
    assert_true("improver" in swarms, "improver missing from topology")
    assert_true("overseer" in swarms, "overseer missing from topology")
    assert_true("trade" in swarms, "trade missing from topology")

    assert_true(
        command_requires_explicit_gate("improver", "maintenance_agent", "RUN_ONCE") is True,
        "improver RUN_ONCE must require explicit gate",
    )
    assert_true(
        command_requires_explicit_gate("security", "node", "UNBLOCK_ALL") is False,
        "security UNBLOCK_ALL should not require explicit gate",
    )


async def check_command_normalization() -> None:
    items = normalize_commands(
        [
            {
                "type": "sec_command",
                "gid": "legacy-sec-1",
                "data": {"action": "UNBLOCK_ALL"},
            },
            {"type": "not_command"},
            {
                "type": "swarm_command",
                "gid": "canonical-1",
                "command_type": "PAUSE",
                "target_swarm": "explorer",
            },
        ]
    )

    assert_true(len(items) == 2, f"expected 2 normalized commands, got {len(items)}")
    assert_true(items[0].get("command_type") == "UNBLOCK_ALL", "legacy sec command not normalized")
    assert_true(items[0].get("target_swarm") == "security", "legacy sec target_swarm not inferred")
    assert_true(items[1].get("command_type") == "PAUSE", "canonical command not normalized")


async def check_security_dedup() -> None:
    node = SecurityNode(
        node_id="sec-smoke-dedup",
        memory_db=Path("./data/test_smoke_security_dedup.sqlite3"),
    )

    calls = {"count": 0}

    async def fake_unblock_all(scope: str = "managed_chain", parent_command: str | None = None) -> None:
        calls["count"] += 1

    node._unblock_all = fake_unblock_all  # type: ignore[method-assign]

    canonical = make_swarm_command(
        command_type="UNBLOCK_ALL",
        source_agent="smoke",
        source_swarm="test",
        target_swarm="security",
        target_role="node",
        ttl_seconds=300,
        payload={"reason": "smoke"},
        provenance={"test": True},
    )

    legacy = {
        "type": "sec_command",
        "gid": "legacy-sec-smoke-unblock",
        "timestamp": 9999999999,
        "expires_at": 9999999999,
        "data": {"action": "UNBLOCK_ALL", "reason": "smoke"},
        "provenance": {"test": True},
    }

    await node.process_command(canonical)
    await node.process_command(legacy)

    assert_true(calls["count"] == 1, f"security dedup failed, calls={calls['count']}")


async def check_explorer_dedup() -> None:
    node = ExplorerNode(
        node_id="exp-smoke-dedup",
        memory_db=Path("./data/test_smoke_explorer_dedup.sqlite3"),
    )

    canonical = make_swarm_command(
        command_type="PAUSE",
        source_agent="smoke",
        source_swarm="test",
        target_swarm="explorer",
        target_role="node",
        ttl_seconds=300,
        payload={"reason": "smoke"},
        provenance={"test": True},
    )

    legacy = {
        "type": "explorer_command",
        "gid": "legacy-exp-smoke-pause",
        "timestamp": 9999999999,
        "expires_at": 9999999999,
        "data": {"action": "PAUSE", "reason": "smoke"},
        "provenance": {"test": True},
    }

    await node.process_command(canonical)
    await node.process_command(legacy)

    events = [
        item
        for item in node.crdt.state.values()
        if isinstance(item, dict)
        and item.get("type") == "swarm_event"
        and item.get("event_type") == "command_applied"
        and item.get("source_swarm") == "explorer"
        and item.get("source_node") == node.node_id
    ]

    assert_true(node.build_heartbeat()["metrics"]["paused"] is True, "explorer pause not applied")
    assert_true(len(events) == 1, f"explorer dedup failed, command events={len(events)}")


async def check_improver_dry_cycle() -> None:
    agent = ImproverAgent(
        node_id="improver-smoke-dry",
        single_pass=False,
        proposals=False,
        enable_validation=False,
        enable_critique=False,
        scan_dirs=[],
        memory_db=Path("./data/test_smoke_improver.sqlite3"),
        output_dir=Path("./data/test_smoke_improver_output"),
        failed_dir=Path("./data/test_smoke_improver_failed"),
        proposals_dir=Path("./data/test_smoke_improver_proposals"),
        staging_dir=Path("./data/test_smoke_improver_staging"),
    )

    await agent.on_startup()

    run_once = make_swarm_command(
        command_type="RUN_ONCE",
        source_agent="smoke",
        source_swarm="test",
        target_swarm="improver",
        target_role="maintenance_agent",
        target_node=agent.node_id,
        ttl_seconds=300,
        payload={"reason": "smoke"},
        provenance={"test": True},
    )

    await agent.process_command(run_once)

    assert_true(agent.scan_dirs == [], "improver dry scan_dirs changed")
    assert_true(agent._last_cycle_processed == 0, "improver dry cycle processed files")
    assert_true(agent._last_cycle_improved == 0, "improver dry cycle improved files")
    assert_true(agent._last_cycle_quarantined == 0, "improver dry cycle quarantined files")
    assert_true(agent._last_cycle_failed == 0, "improver dry cycle failed files")

    await agent.on_shutdown()


async def check_overseer_executor_gates() -> None:
    sink = MemorySink()
    executor = ActionExecutor(sink)

    snapshot = SwarmSnapshot(
        trade_nodes=1,
        trade_capital=3000,
        trade_dq=0.0,
        trade_fitness=0.1,
        security_nodes=0,
        blocked_ips=0,
        explorer_nodes=0,
        recent_findings=0,
        recent_vulnerability_alerts=0,
        improver_nodes=1,
        improver_files_processed=0,
        improver_files_improved=0,
        improver_files_quarantined=0,
        improver_files_failed=0,
        improver_last_cycle_duration_seconds=0.0,
        improver_last_error_count=0,
        resources="smoke",
    )

    decision = OverseerDecision(
        run_improver_once=True,
        pause_improver=True,
        reason="smoke advisory",
        confidence=0.9,
    )

    await executor.apply(snapshot, decision, 1234567890.0)

    assert_true(len(sink.items) == 0, "improver advisory should not emit commands")

    security_sink = MemorySink()
    security_executor = ActionExecutor(security_sink)

    security_snapshot = SwarmSnapshot(
        trade_nodes=1,
        trade_capital=3000,
        trade_dq=0.0,
        trade_fitness=0.1,
        security_nodes=1,
        blocked_ips=99,
        explorer_nodes=0,
        recent_findings=0,
        recent_vulnerability_alerts=0,
        resources="smoke",
    )

    security_decision = OverseerDecision(
        unblock_ips=True,
        reason="smoke security",
        confidence=1.0,
    )

    await security_executor.apply(security_snapshot, security_decision, 1234567890.0)

    types = {item.get("type") for item in security_sink.items}
    assert_true("swarm_command" in types, "security canonical command missing")
    assert_true("sec_command" in types, "security legacy command missing")


async def main() -> None:
    checks = [
        ("common runtime", check_common_runtime),
        ("command normalization", check_command_normalization),
        ("security dedup", check_security_dedup),
        ("explorer dedup", check_explorer_dedup),
        ("improver dry cycle", check_improver_dry_cycle),
        ("overseer executor gates", check_overseer_executor_gates),
    ]

    for name, check in checks:
        await check()
        print(f"✅ {name}")

    print("✅ swarm runtime smoke OK")


if __name__ == "__main__":
    asyncio.run(main())