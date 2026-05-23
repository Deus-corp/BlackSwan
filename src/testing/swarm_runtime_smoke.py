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
import uuid
import os

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
from src.swarms.overseer.node import OverseerNode
from src.swarms.overseer.overseer_core.collector import StateCollector


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
    reason = f"smoke-explorer-dedup-{uuid.uuid4().hex}"

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
        payload={"reason": reason},
        provenance={"test": True},
    )

    legacy = {
        "type": "explorer_command",
        "gid": f"legacy-exp-smoke-pause-{uuid.uuid4().hex}",
        "timestamp": 9999999999,
        "expires_at": 9999999999,
        "data": {"action": "PAUSE", "reason": reason},
        "provenance": {"test": True},
    }

    await node.process_command(canonical)
    await node.process_command(legacy)

    events = [
        item
        for item in node.crdt.state.values()
        if isinstance(item, dict)
        and item.get("type") == "swarm_event"
        and item.get("event_type") in {"command_applied", "lifecycle_command_applied"}
        and item.get("source_swarm") == "explorer"
        and item.get("source_node") == node.node_id
        and isinstance(item.get("payload"), dict)
        and item["payload"].get("reason") == reason
    ]

    assert_true(node.is_paused() is True, "explorer pause not applied")
    assert_true(len(events) == 1, f"explorer dedup failed, command events={len(events)}")


async def check_improver_dry_cycle() -> None:
    reason = f"smoke-improver-dry-{uuid.uuid4().hex}"
    
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
        payload={"reason": reason},
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

async def check_overseer_topology_summary() -> None:
    class Dummy:
        state = {
            "security-node": {
                "type": "swarm_heartbeat",
                "node_id": "sec-smoke-1",
                "swarm": "security",
                "role": "node",
                "timestamp": 9999999999,
                "metrics": {"blocked_ips": 3},
            },
            "explorer-node": {
                "type": "swarm_heartbeat",
                "node_id": "exp-smoke-1",
                "swarm": "explorer",
                "role": "node",
                "timestamp": 9999999999,
                "metrics": {},
            },
            "explorer-meta": {
                "type": "swarm_heartbeat",
                "node_id": "exp-meta-smoke-1",
                "swarm": "explorer",
                "role": "meta_agent",
                "timestamp": 9999999999,
                "metrics": {},
            },
            "improver": {
                "type": "swarm_heartbeat",
                "node_id": "improver-smoke-1",
                "swarm": "improver",
                "role": "maintenance_agent",
                "timestamp": 9999999999,
                "metrics": {},
            },
            "security-command": {
                "type": "swarm_command",
                "command_type": "UNBLOCK_ALL",
                "target_swarm": "security",
                "timestamp": 9999999999,
            },
        }

    collector = StateCollector(Dummy())
    health = collector.collect_topology_health()

    node = OverseerNode(node_id="overseer-smoke-topology")
    summary = node.summarize_topology_health(health)

    assert_true(summary["type"] == "topology_health", "topology summary type mismatch")
    assert_true(summary["swarms"]["security"]["status"] == "ok", "security topology status mismatch")
    assert_true(summary["swarms"]["security"]["commands"] == 1, "security command count mismatch")
    assert_true(summary["swarms"]["explorer"]["node_count"] == 2, "explorer node_count mismatch")
    assert_true(
        summary["swarms"]["explorer"]["role_counts"]["meta_agent"] == 1,
        "explorer meta_agent role_count mismatch",
    )
    assert_true(
        summary["swarms"]["improver"]["advisory_only"] is True,
        "improver advisory_only mismatch",
    )

async def check_overseer_topology_healthcheck() -> None:
    node = OverseerNode(node_id="overseer-smoke-healthcheck")

    node._last_topology_health = {
        "swarms": {
            "security": {
                "managed_by_overseer": True,
                "advisory_only": False,
                "node_count": 1,
                "status": "ok",
            },
            "explorer": {
                "managed_by_overseer": True,
                "advisory_only": False,
                "node_count": 0,
                "status": "absent",
            },
            "improver": {
                "managed_by_overseer": True,
                "advisory_only": True,
                "node_count": 1,
                "status": "ok",
            },
        }
    }

    await node.healthcheck()

    assert_true(node.health.status == "ok", f"expected ok health, got {node.health.status}")
    assert_true(node.health.last_error == "", f"expected empty health error, got {node.health.last_error!r}")

    node._last_topology_health = {
        "swarms": {
            "security": {
                "managed_by_overseer": True,
                "advisory_only": False,
                "node_count": 1,
                "status": "stale",
            },
            "explorer": {
                "managed_by_overseer": True,
                "advisory_only": False,
                "node_count": 1,
                "status": "ok",
            },
            "improver": {
                "managed_by_overseer": True,
                "advisory_only": True,
                "node_count": 1,
                "status": "ok",
            },
        }
    }

    await node.healthcheck()

    assert_true(node.health.status == "degraded", f"expected degraded health, got {node.health.status}")
    assert_true(
        "security" in node.health.last_error,
        f"expected security in health error, got {node.health.last_error!r}",
    )

async def check_overseer_topology_rules_payload() -> None:
    class DummyStrategist:
        async def suggest(self, snapshot):
            return {}

    node = OverseerNode(node_id="overseer-smoke-topology-rules")
    node.strategist = DummyStrategist()

    node._last_topology_health = {
        "swarms": {
            "security": {
                "managed_by_overseer": True,
                "advisory_only": False,
                "node_count": 1,
                "status": "ok",
            },
            "explorer": {
                "managed_by_overseer": True,
                "advisory_only": False,
                "node_count": 1,
                "status": "stale",
            },
            "trade": {
                "managed_by_overseer": True,
                "advisory_only": False,
                "node_count": 0,
                "status": "absent",
            },
            "improver": {
                "managed_by_overseer": True,
                "advisory_only": True,
                "node_count": 1,
                "status": "ok",
            },
        }
    }

    snapshot = node.collector.collect()
    decision = await node.global_decide(snapshot)
    rules = decision.payload.get("topology_rules", {})

    assert_true(
        rules.get("has_degraded_managed_swarms") is True,
        "expected degraded managed swarms in topology rules",
    )
    assert_true(
        rules.get("degraded_managed_swarms", {}).get("explorer") == "stale",
        "expected explorer stale in degraded topology rules",
    )
    assert_true(
        "trade" in rules.get("absent_managed_swarms", []),
        "expected trade in absent managed swarms",
    )
    assert_true(
        "improver" in rules.get("advisory_swarms", []),
        "expected improver in advisory swarms",
    )

async def check_overseer_topology_warnings() -> None:
    class DummyStrategist:
        async def suggest(self, snapshot):
            return {}

    node = OverseerNode(node_id="overseer-smoke-topology-warnings")
    node.strategist = DummyStrategist()

    node._last_topology_health = {
        "swarms": {
            "security": {
                "managed_by_overseer": True,
                "advisory_only": False,
                "node_count": 1,
                "status": "ok",
            },
            "explorer": {
                "managed_by_overseer": True,
                "advisory_only": False,
                "node_count": 1,
                "status": "stale",
            },
            "trade": {
                "managed_by_overseer": True,
                "advisory_only": False,
                "node_count": 0,
                "status": "absent",
            },
            "improver": {
                "managed_by_overseer": True,
                "advisory_only": True,
                "node_count": 1,
                "status": "ok",
            },
        }
    }

    snapshot = node.collector.collect()
    decision = await node.global_decide(snapshot)
    warnings = decision.payload.get("topology_warnings", [])

    assert_true(
        any(w.get("swarm") == "explorer" and w.get("status") == "stale" for w in warnings),
        "expected explorer stale topology warning",
    )
    assert_true(
        any(w.get("swarm") == "trade" and w.get("status") == "absent" for w in warnings),
        "expected trade absent topology warning",
    )

async def check_overseer_topology_restart_candidates() -> None:
    class DummyStrategist:
        async def suggest(self, snapshot):
            return {}

    node = OverseerNode(node_id="overseer-smoke-topology-restart-candidates")
    node.strategist = DummyStrategist()

    node._last_topology_health = {
        "swarms": {
            "security": {
                "managed_by_overseer": True,
                "advisory_only": False,
                "node_count": 2,
                "status": "degraded",
                "stale_nodes": ["sec-smoke-stale-1"],
            },
            "explorer": {
                "managed_by_overseer": True,
                "advisory_only": False,
                "node_count": 1,
                "status": "stale",
                "stale_nodes": ["exp-smoke-stale-1"],
            },
            "trade": {
                "managed_by_overseer": True,
                "advisory_only": False,
                "node_count": 0,
                "status": "absent",
                "stale_nodes": [],
            },
            "improver": {
                "managed_by_overseer": True,
                "advisory_only": True,
                "node_count": 1,
                "status": "ok",
                "stale_nodes": [],
            },
        }
    }

    snapshot = node.collector.collect()
    decision = await node.global_decide(snapshot)
    directives = await node.route_directives(decision, snapshot)

    topology_directives = [
        item for item in directives
        if item.get("source") == "topology_rules"
    ]

    assert_true(
        any(item.get("target_node") == "sec-smoke-stale-1" for item in topology_directives),
        "expected topology restart candidate for stale security node",
    )
    assert_true(
        any(item.get("target_node") == "exp-smoke-stale-1" for item in topology_directives),
        "expected topology restart candidate for stale explorer node",
    )
    assert_true(
        all(item.get("execution_enabled") is False for item in topology_directives),
        "topology restart candidates must not execute in phase A",
    )
    assert_true(
        all(item.get("advisory_only") is True for item in topology_directives),
        "topology restart candidates must be advisory-only in phase A",
    )

async def check_overseer_topology_restarts_default_disabled() -> None:
    class DummyStrategist:
        async def suggest(self, snapshot):
            return {}

    previous = os.environ.pop("OVERSEER_ENABLE_TOPOLOGY_RESTARTS", None)

    try:
        node = OverseerNode(node_id="overseer-smoke-topology-restarts-default")
        node.strategist = DummyStrategist()

        node._last_topology_health = {
            "swarms": {
                "security": {
                    "managed_by_overseer": True,
                    "advisory_only": False,
                    "node_count": 1,
                    "status": "stale",
                    "stale_nodes": ["sec-smoke-topology-default-1"],
                }
            }
        }

        snapshot = node.collector.collect()
        decision = await node.global_decide(snapshot)
        directives = await node.route_directives(decision, snapshot)

        topology_directives = [
            item for item in directives
            if item.get("source") == "topology_rules"
            and item.get("target_node") == "sec-smoke-topology-default-1"
        ]

        assert_true(node.enable_topology_restarts is False, "topology restarts should be default-disabled")
        assert_true(topology_directives, "expected advisory topology restart directive")
        assert_true(
            all(item.get("execution_enabled") is False for item in topology_directives),
            "default-disabled topology directives must not execute",
        )

        commands = [
            item for item in node.crdt.state.values()
            if isinstance(item, dict)
            and item.get("type") == "swarm_command"
            and item.get("source_node") == node.overseer_id
            and item.get("target_node") == "sec-smoke-topology-default-1"
            and item.get("command_type") == "RESTART_NODE"
        ]

        assert_true(not commands, "topology restart command should not emit when flag is false")

    finally:
        if previous is not None:
            os.environ["OVERSEER_ENABLE_TOPOLOGY_RESTARTS"] = previous
        else:
            os.environ.pop("OVERSEER_ENABLE_TOPOLOGY_RESTARTS", None)

async def check_overseer_topology_restarts_enabled_canonical_only() -> None:
    class DummyStrategist:
        async def suggest(self, snapshot):
            return {}

    previous = os.environ.get("OVERSEER_ENABLE_TOPOLOGY_RESTARTS")
    os.environ["OVERSEER_ENABLE_TOPOLOGY_RESTARTS"] = "true"

    try:
        node = OverseerNode(node_id="overseer-smoke-topology-restarts-enabled")
        node.strategist = DummyStrategist()

        node._last_topology_health = {
            "swarms": {
                "security": {
                    "managed_by_overseer": True,
                    "advisory_only": False,
                    "node_count": 1,
                    "status": "stale",
                    "stale_nodes": ["sec-smoke-topology-enabled-1"],
                }
            }
        }

        snapshot = node.collector.collect()
        decision = await node.global_decide(snapshot)
        directives = await node.route_directives(decision, snapshot)

        assert_true(node.enable_topology_restarts is True, "topology restarts should be enabled by env flag")

        commands = [
            item for item in node.crdt.state.values()
            if isinstance(item, dict)
            and item.get("type") == "swarm_command"
            and item.get("source_node") == node.overseer_id
            and item.get("target_node") == "sec-smoke-topology-enabled-1"
            and item.get("command_type") == "RESTART_NODE"
        ]

        legacy = [
            item for item in node.crdt.state.values()
            if isinstance(item, dict)
            and item.get("source_node") == node.overseer_id
            and item.get("target_node") == "sec-smoke-topology-enabled-1"
            and item.get("type") in {"sec_command", "explorer_command", "meta_command_json"}
        ]

        assert_true(commands, "canonical topology restart command missing")
        assert_true(not legacy, "topology restart path must not emit legacy commands")

        topology_directives = [
            item for item in directives
            if item.get("source") == "topology_rules"
            and item.get("target_node") == "sec-smoke-topology-enabled-1"
        ]

        assert_true(
            any(item.get("execution_enabled") is True for item in topology_directives),
            "enabled topology restart directive should be execution_enabled=True",
        )
        assert_true(
            any(item.get("legacy_emitted") is False for item in topology_directives),
            "enabled topology restart directive should report legacy_emitted=False",
        )

    finally:
        if previous is not None:
            os.environ["OVERSEER_ENABLE_TOPOLOGY_RESTARTS"] = previous
        else:
            os.environ.pop("OVERSEER_ENABLE_TOPOLOGY_RESTARTS", None)

async def check_common_lifecycle_security_explorer() -> None:
    reason = f"smoke-lifecycle-{uuid.uuid4().hex}"

    security = SecurityNode(
        node_id="sec-smoke-lifecycle",
        memory_db=Path("./data/test_smoke_security_lifecycle.sqlite3"),
    )

    explorer = ExplorerNode(
        node_id="exp-smoke-lifecycle",
        memory_db=Path("./data/test_smoke_explorer_lifecycle.sqlite3"),
    )

    sec_pause = make_swarm_command(
        command_type="PAUSE",
        source_agent="smoke",
        source_swarm="overseer",
        target_swarm="security",
        target_role="node",
        target_node=security.node_id,
        ttl_seconds=300,
        payload={"reason": reason},
    )

    exp_pause = make_swarm_command(
        command_type="PAUSE",
        source_agent="smoke",
        source_swarm="overseer",
        target_swarm="explorer",
        target_role="node",
        target_node=explorer.node_id,
        ttl_seconds=300,
        payload={"reason": reason},
    )

    exp_resume = make_swarm_command(
        command_type="RESUME",
        source_agent="smoke",
        source_swarm="overseer",
        target_swarm="explorer",
        target_role="node",
        target_node=explorer.node_id,
        ttl_seconds=300,
        payload={"reason": reason},
    )

    await security.process_command(sec_pause)
    await explorer.process_command(exp_pause)
    await explorer.process_command(exp_resume)

    assert_true(
        getattr(security, "paused", False) is True,
        "security PAUSE lifecycle command did not pause node",
    )
    assert_true(
        getattr(explorer, "paused", False) is False,
        "explorer RESUME lifecycle command did not resume node",
    )

    sec_events = [
        item for item in security.crdt.state.values()
        if isinstance(item, dict)
        and item.get("type") == "swarm_event"
        and item.get("event_type") == "lifecycle_command_applied"
        and item.get("source_node") == security.node_id
        and isinstance(item.get("payload"), dict)
        and item["payload"].get("reason") == reason
    ]

    exp_events = [
        item for item in explorer.crdt.state.values()
        if isinstance(item, dict)
        and item.get("type") == "swarm_event"
        and item.get("event_type") == "lifecycle_command_applied"
        and item.get("source_node") == explorer.node_id
        and isinstance(item.get("payload"), dict)
        and item["payload"].get("reason") == reason
    ]

    assert_true(len(sec_events) == 1, f"expected 1 security lifecycle event, got {len(sec_events)}")
    assert_true(len(exp_events) == 2, f"expected 2 explorer lifecycle events, got {len(exp_events)}")

async def main() -> None:
    checks = [
        ("common runtime", check_common_runtime),
        ("command normalization", check_command_normalization),
        ("security dedup", check_security_dedup),
        ("explorer dedup", check_explorer_dedup),
        ("common lifecycle security/explorer", check_common_lifecycle_security_explorer),
        ("improver dry cycle", check_improver_dry_cycle),
        ("overseer topology summary", check_overseer_topology_summary),
        ("overseer topology healthcheck", check_overseer_topology_healthcheck),
        ("overseer topology rules payload", check_overseer_topology_rules_payload),
        ("overseer topology warnings", check_overseer_topology_warnings),
        ("overseer topology restart candidates", check_overseer_topology_restart_candidates),
        ("overseer topology restarts default disabled", check_overseer_topology_restarts_default_disabled),
        ("overseer topology restarts enabled canonical only", check_overseer_topology_restarts_enabled_canonical_only),
        ("overseer executor gates", check_overseer_executor_gates),
    ]

    for name, check in checks:
        await check()
        print(f"✅ {name}")

    print("✅ swarm runtime smoke OK")


if __name__ == "__main__":
    asyncio.run(main())