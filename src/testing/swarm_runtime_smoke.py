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
import os
import time
import uuid
import argparse
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from src.swarms.common import (
    BaseSwarmMetaAgent,
    BaseSwarmNode,
    BaseSwarmOverseer,
    COMMAND_EVENT_SKIPPED,
    COMMAND_STATUS_SKIPPED,
    LIFECYCLE_EVENT_APPLIED,
    LIFECYCLE_STATUS_APPLIED,
    command_action,
    command_event_action,
    command_event_payload,
    command_event_reason,
    command_event_status,
    command_requires_explicit_gate,
    is_command_event,
    is_lifecycle_event,
    known_swarms,
    lifecycle_event_action,
    lifecycle_event_payload,
    lifecycle_event_reason,
    lifecycle_event_status,
    make_swarm_command,
    normalize_command,
    normalize_commands,
    command_fingerprint,
)

from src.swarms.explorer.meta_agent import ExplorerMetaAgent
from src.swarms.explorer.node import ExplorerNode
from src.swarms.overseer.node import OverseerNode
from src.swarms.overseer.overseer_core.collector import (
    COMMAND_EVENT_WINDOW_SECONDS,
    StateCollector,
)
from src.swarms.overseer.overseer_core.executor import ActionExecutor
from src.swarms.overseer.overseer_core.models import OverseerDecision, SwarmSnapshot
from src.swarms.security.meta_agent import SecurityMetaAgent
from src.swarms.security.node import SecurityNode
from src.swarms.common.protocols.commands import command_targets
from src.testing.retry_governance_smoke import run_retry_governance_smoke

from src.swarms.overseer.overseer_core.policy import (
    PolicyEngine,
    command_event_thresholds,
)

try:
    from src.swarms.improver.improver_agent import ImproverAgent
except ModuleNotFoundError as exc:
    if exc.name not in {"src.swarms.improver", "src.swarms.improver.improver_agent"}:
        raise
    ImproverAgent = None  # type: ignore[assignment]

SMOKE_DATA_DIR = Path(os.getenv("SWARM_SMOKE_DATA_DIR", "./data/smoke_test"))
SMOKE_DATA_DIR.mkdir(parents=True, exist_ok=True)


def smoke_data_path(*parts: str) -> Path:
    path = SMOKE_DATA_DIR.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


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
        memory_db=smoke_data_path("test_smoke_security_dedup.sqlite3"),
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
        memory_db=smoke_data_path("test_smoke_explorer_dedup.sqlite3"),
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

    if ImproverAgent is None:
        print("⚠️ improver module unavailable; skipping improver dry-cycle smoke")
        return
    
    agent = ImproverAgent(
        node_id="improver-smoke-dry",
        single_pass=False,
        proposals=False,
        enable_validation=False,
        enable_critique=False,
        scan_dirs=[],
        memory_db=smoke_data_path("test_smoke_improver.sqlite3"),
        output_dir=smoke_data_path("test_smoke_improver_output"),
        failed_dir=smoke_data_path("test_smoke_improver_failed"),
        proposals_dir=smoke_data_path("test_smoke_improver_proposals"),
        staging_dir=smoke_data_path("test_smoke_improver_staging"),
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
        memory_db=smoke_data_path("test_smoke_security_lifecycle.sqlite3"),
    )

    explorer = ExplorerNode(
        node_id="exp-smoke-lifecycle",
        memory_db=smoke_data_path("test_smoke_explorer_lifecycle.sqlite3"),
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

async def check_improver_lifecycle_pause_resume() -> None:
    reason = f"smoke-improver-lifecycle-{uuid.uuid4().hex}"

    if ImproverAgent is None:
        print("⚠️ improver module unavailable; skipping improver dry-cycle smoke")
        return

    agent = ImproverAgent(
        node_id="improver-smoke-lifecycle",
        single_pass=False,
        proposals=False,
        enable_validation=False,
        enable_critique=False,
        scan_dirs=[],
        memory_db=smoke_data_path("test_smoke_improver_lifecycle.sqlite3"),
        output_dir=smoke_data_path("test_smoke_improver_lifecycle_output"),
        failed_dir=smoke_data_path("test_smoke_improver_lifecycle_failed"),
        proposals_dir=smoke_data_path("test_smoke_improver_lifecycle_proposals"),
        staging_dir=smoke_data_path("test_smoke_improver_lifecycle_staging"),
    )

    await agent.on_startup()

    pause = make_swarm_command(
        command_type="PAUSE",
        source_agent="smoke",
        source_swarm="overseer",
        target_swarm="improver",
        target_role="maintenance_agent",
        target_node=agent.node_id,
        ttl_seconds=300,
        payload={"reason": reason},
    )

    resume = make_swarm_command(
        command_type="RESUME",
        source_agent="smoke",
        source_swarm="overseer",
        target_swarm="improver",
        target_role="maintenance_agent",
        target_node=agent.node_id,
        ttl_seconds=300,
        payload={"reason": reason},
    )

    await agent.process_command(pause)
    assert_true(agent.is_paused() is True, "improver PAUSE did not pause agent")

    await agent.process_command(resume)
    assert_true(agent.is_paused() is False, "improver RESUME did not resume agent")

    events = [
        item for item in agent.crdt.state.values()
        if isinstance(item, dict)
        and item.get("type") == "swarm_event"
        and item.get("event_type") == "lifecycle_command_applied"
        and item.get("source_node") == agent.node_id
        and isinstance(item.get("payload"), dict)
        and item["payload"].get("reason") == reason
    ]

    assert_true(len(events) == 2, f"expected 2 improver lifecycle events, got {len(events)}")

    await agent.on_shutdown()

async def check_improver_run_once_blocked_without_approval() -> None:
    reason = f"smoke-improver-runonce-blocked-{uuid.uuid4().hex}"

    if ImproverAgent is None:
        print("⚠️ improver module unavailable; skipping improver dry-cycle smoke")
        return

    agent = ImproverAgent(
        node_id="improver-smoke-runonce-blocked",
        single_pass=False,
        proposals=False,
        enable_validation=False,
        enable_critique=False,
        scan_dirs=[],
        memory_db=smoke_data_path("test_smoke_improver_runonce_blocked.sqlite3"),
        output_dir=smoke_data_path("test_smoke_improver_runonce_blocked_output"),
        failed_dir=smoke_data_path("test_smoke_improver_runonce_blocked_failed"),
        proposals_dir=smoke_data_path("test_smoke_improver_runonce_blocked_proposals"),
        staging_dir=smoke_data_path("test_smoke_improver_runonce_blocked_staging"),
    )

    await agent.on_startup()

    run_once = make_swarm_command(
        command_type="RUN_ONCE",
        source_agent="smoke",
        source_swarm="overseer",
        target_swarm="improver",
        target_role="maintenance_agent",
        target_node=agent.node_id,
        ttl_seconds=300,
        payload={"reason": reason},
    )

    await agent.process_command(run_once)

    events = [
        item for item in agent.crdt.state.values()
        if isinstance(item, dict)
        and item.get("type") == "swarm_event"
        and item.get("event_type") == "lifecycle_command_applied"
        and item.get("source_node") == agent.node_id
        and isinstance(item.get("payload"), dict)
        and item["payload"].get("reason") == reason
    ]

    assert_true(len(events) == 1, f"expected 1 RUN_ONCE blocked event, got {len(events)}")
    assert_true(events[0]["payload"]["status"] == "blocked", "RUN_ONCE should be blocked without approval")

    await agent.on_shutdown()

async def check_improver_run_once_approved_dry_cycle() -> None:
    reason = f"smoke-improver-runonce-approved-{uuid.uuid4().hex}"

    if ImproverAgent is None:
        print("⚠️ improver module unavailable; skipping improver dry-cycle smoke")
        return

    agent = ImproverAgent(
        node_id="improver-smoke-runonce-approved",
        single_pass=False,
        proposals=False,
        enable_validation=False,
        enable_critique=False,
        scan_dirs=[],
        memory_db=smoke_data_path("test_smoke_improver_runonce_approved.sqlite3"),
        output_dir=smoke_data_path("test_smoke_improver_runonce_approved_output"),
        failed_dir=smoke_data_path("test_smoke_improver_runonce_approved_failed"),
        proposals_dir=smoke_data_path("test_smoke_improver_runonce_approved_proposals"),
        staging_dir=smoke_data_path("test_smoke_improver_runonce_approved_staging"),
    )

    await agent.on_startup()

    run_once = make_swarm_command(
        command_type="RUN_ONCE",
        source_agent="smoke",
        source_swarm="overseer",
        target_swarm="improver",
        target_role="maintenance_agent",
        target_node=agent.node_id,
        ttl_seconds=300,
        payload={
            "reason": reason,
            "explicit_approval": True,
            "safety_gate": "approved",
        },
    )

    await agent.process_command(run_once)

    events = [
        item for item in agent.crdt.state.values()
        if isinstance(item, dict)
        and item.get("type") == "swarm_event"
        and item.get("event_type") == "lifecycle_command_applied"
        and item.get("source_node") == agent.node_id
        and isinstance(item.get("payload"), dict)
        and item["payload"].get("reason") == reason
    ]

    assert_true(len(events) == 1, f"expected 1 RUN_ONCE applied event, got {len(events)}")
    assert_true(events[0]["payload"]["status"] == "applied", "RUN_ONCE should be applied with approval")
    assert_true(agent._last_cycle_processed == 0, "dry RUN_ONCE should process 0 files")
    assert_true(agent._last_cycle_improved == 0, "dry RUN_ONCE should improve 0 files")

    await agent.on_shutdown()

async def check_explorer_pause_guard() -> None:
    class DummyClient:
        async def get(self, url):
            raise AssertionError("Explorer fetch should not be called while paused")

    reason = f"smoke-explorer-pause-guard-{uuid.uuid4().hex}"

    node = ExplorerNode(
        node_id="exp-smoke-pause-guard",
        memory_db=smoke_data_path("test_smoke_explorer_pause_guard.sqlite3"),
    )

    pause = make_swarm_command(
        command_type="PAUSE",
        source_agent="smoke",
        source_swarm="overseer",
        target_swarm="explorer",
        target_role="node",
        target_node=node.node_id,
        ttl_seconds=300,
        payload={"reason": reason},
    )

    await node.process_command(pause)

    did_work = await node._consume_targets_and_explore(DummyClient())
    await node._fetch_and_emit(DummyClient(), "https://example.com/should-not-fetch")

    assert_true(node.is_paused() is True, "explorer should be paused")
    assert_true(did_work is False, "explorer should not work while paused")

async def check_security_pause_guard() -> None:
    reason = f"smoke-security-pause-guard-{uuid.uuid4().hex}"

    node = SecurityNode(
        node_id="sec-smoke-pause-guard",
        memory_db=smoke_data_path("test_smoke_security_pause_guard.sqlite3"),
    )

    calls = {"count": 0}

    async def fake_unblock_all(scope="managed_chain", parent_command=None):
        calls["count"] += 1
        raise AssertionError("UNBLOCK_ALL should not execute while paused")

    node._unblock_all = fake_unblock_all

    pause = make_swarm_command(
        command_type="PAUSE",
        source_agent="smoke",
        source_swarm="overseer",
        target_swarm="security",
        target_role="node",
        target_node=node.node_id,
        ttl_seconds=300,
        payload={"reason": reason},
    )

    unblock = make_swarm_command(
        command_type="UNBLOCK_ALL",
        source_agent="smoke",
        source_swarm="overseer",
        target_swarm="security",
        target_role="node",
        target_node=node.node_id,
        ttl_seconds=300,
        payload={"reason": reason},
    )

    resume = make_swarm_command(
        command_type="RESUME",
        source_agent="smoke",
        source_swarm="overseer",
        target_swarm="security",
        target_role="node",
        target_node=node.node_id,
        ttl_seconds=300,
        payload={"reason": reason},
    )

    await node.process_command(pause)
    assert_true(node.is_paused() is True, "security should be paused")

    await node.process_command(unblock)
    assert_true(calls["count"] == 0, "UNBLOCK_ALL should be skipped while paused")

    await node.process_command(resume)
    assert_true(node.is_paused() is False, "security should resume")

async def check_improver_pause_guard() -> None:
    reason = f"smoke-improver-pause-guard-{uuid.uuid4().hex}"

    if ImproverAgent is None:
        print("⚠️ improver module unavailable; skipping improver dry-cycle smoke")
        return

    agent = ImproverAgent(
        node_id="improver-smoke-pause-guard",
        single_pass=False,
        proposals=False,
        enable_validation=False,
        enable_critique=False,
        scan_dirs=[],
        memory_db=smoke_data_path("test_smoke_improver_pause_guard.sqlite3"),
        output_dir=smoke_data_path("test_smoke_improver_pause_guard_output"),
        failed_dir=smoke_data_path("test_smoke_improver_pause_guard_failed"),
        proposals_dir=smoke_data_path("test_smoke_improver_pause_guard_proposals"),
        staging_dir=smoke_data_path("test_smoke_improver_pause_guard_staging"),
    )

    await agent.on_startup()

    pause = make_swarm_command(
        command_type="PAUSE",
        source_agent="smoke",
        source_swarm="overseer",
        target_swarm="improver",
        target_role="maintenance_agent",
        target_node=agent.node_id,
        ttl_seconds=300,
        payload={"reason": reason},
    )

    run_once = make_swarm_command(
        command_type="RUN_ONCE",
        source_agent="smoke",
        source_swarm="overseer",
        target_swarm="improver",
        target_role="maintenance_agent",
        target_node=agent.node_id,
        ttl_seconds=300,
        payload={
            "reason": reason,
            "explicit_approval": True,
            "safety_gate": "approved",
        },
    )

    await agent.process_command(pause)
    assert_true(agent.is_paused() is True, "improver should be paused")

    await agent.process_command(run_once)

    events = [
        item for item in agent.crdt.state.values()
        if isinstance(item, dict)
        and item.get("type") == "swarm_event"
        and item.get("event_type") == "lifecycle_command_applied"
        and item.get("source_node") == agent.node_id
        and isinstance(item.get("payload"), dict)
        and item["payload"].get("reason") == reason
        and item["payload"].get("action") == "RUN_ONCE"
    ]

    assert_true(len(events) == 1, f"expected 1 improver RUN_ONCE event, got {len(events)}")
    assert_true(events[0]["payload"]["status"] == "blocked", "RUN_ONCE should be blocked while paused")

    await agent.on_shutdown()

async def check_common_lifecycle_meta_agents() -> None:
    import inspect

    def make_agent(cls, value: str):
        sig = inspect.signature(cls)
        if "agent_id" in sig.parameters:
            return cls(agent_id=value)
        if "node_id" in sig.parameters:
            return cls(node_id=value)
        return cls()

    def agent_identity(agent):
        return str(getattr(agent, "agent_id", "") or getattr(agent, "node_id", ""))

    reason = f"smoke-meta-lifecycle-{uuid.uuid4().hex}"

    security = make_agent(SecurityMetaAgent, f"sec-meta-smoke-{uuid.uuid4().hex[:8]}")
    explorer = make_agent(ExplorerMetaAgent, f"exp-meta-smoke-{uuid.uuid4().hex[:8]}")

    security_id = agent_identity(security)
    explorer_id = agent_identity(explorer)

    sec_pause = make_swarm_command(
        command_type="PAUSE",
        source_agent="smoke",
        source_swarm="overseer",
        target_swarm="security",
        target_role="meta_agent",
        target_node=security_id,
        ttl_seconds=300,
        payload={"reason": reason},
    )

    exp_pause = make_swarm_command(
        command_type="PAUSE",
        source_agent="smoke",
        source_swarm="overseer",
        target_swarm="explorer",
        target_role="meta_agent",
        target_node=explorer_id,
        ttl_seconds=300,
        payload={"reason": reason},
    )

    exp_resume = make_swarm_command(
        command_type="RESUME",
        source_agent="smoke",
        source_swarm="overseer",
        target_swarm="explorer",
        target_role="meta_agent",
        target_node=explorer_id,
        ttl_seconds=300,
        payload={"reason": reason},
    )

    await security.crdt.add_genome(sec_pause)
    await explorer.crdt.add_genome(exp_pause)
    await explorer.crdt.add_genome(exp_resume)

    await security.poll_lifecycle_commands()
    await explorer.poll_lifecycle_commands()

    assert_true(security.is_paused() is True, "security meta-agent should be paused")
    assert_true(explorer.is_paused() is False, "explorer meta-agent should be resumed")

    sec_events = [
        item for item in security.crdt.state.values()
        if isinstance(item, dict)
        and item.get("type") == "swarm_event"
        and item.get("event_type") == "lifecycle_command_applied"
        and item.get("source_node") == security_id
        and isinstance(item.get("payload"), dict)
        and item["payload"].get("reason") == reason
    ]

    exp_events = [
        item for item in explorer.crdt.state.values()
        if isinstance(item, dict)
        and item.get("type") == "swarm_event"
        and item.get("event_type") == "lifecycle_command_applied"
        and item.get("source_node") == explorer_id
        and isinstance(item.get("payload"), dict)
        and item["payload"].get("reason") == reason
    ]

    assert_true(len(sec_events) == 1, f"expected 1 security meta lifecycle event, got {len(sec_events)}")
    assert_true(len(exp_events) == 2, f"expected 2 explorer meta lifecycle events, got {len(exp_events)}")

async def check_meta_agent_pause_guard() -> None:
    import inspect

    def make_agent(cls, value: str):
        sig = inspect.signature(cls)
        if "agent_id" in sig.parameters:
            return cls(agent_id=value)
        if "node_id" in sig.parameters:
            return cls(node_id=value)
        return cls()

    reason = f"smoke-meta-pause-guard-{uuid.uuid4().hex}"

    security = make_agent(SecurityMetaAgent, f"sec-meta-pause-guard-{uuid.uuid4().hex[:8]}")
    explorer = make_agent(ExplorerMetaAgent, f"exp-meta-pause-guard-{uuid.uuid4().hex[:8]}")

    security_id = str(getattr(security, "agent_id", "") or getattr(security, "node_id", ""))
    explorer_id = str(getattr(explorer, "agent_id", "") or getattr(explorer, "node_id", ""))

    async def fail_collect_security():
        raise AssertionError("SecurityMetaAgent collect should not run while paused")

    async def fail_collect_explorer():
        raise AssertionError("ExplorerMetaAgent collect should not run while paused")

    security.collect = fail_collect_security
    explorer.collect = fail_collect_explorer

    sec_pause = make_swarm_command(
        command_type="PAUSE",
        source_agent="smoke",
        source_swarm="overseer",
        target_swarm="security",
        target_role="meta_agent",
        target_node=security_id,
        ttl_seconds=300,
        payload={"reason": reason},
    )

    exp_pause = make_swarm_command(
        command_type="PAUSE",
        source_agent="smoke",
        source_swarm="overseer",
        target_swarm="explorer",
        target_role="meta_agent",
        target_node=explorer_id,
        ttl_seconds=300,
        payload={"reason": reason},
    )

    await security.crdt.add_genome(sec_pause)
    await explorer.crdt.add_genome(exp_pause)

    await security.reflect()
    await explorer.reflect()

    assert_true(security.is_paused() is True, "security meta-agent should be paused")
    assert_true(explorer.is_paused() is True, "explorer meta-agent should be paused")
    assert_true(security.health.status == "paused", f"security meta health should be paused, got {security.health.status}")
    assert_true(explorer.health.status == "paused", f"explorer meta health should be paused, got {explorer.health.status}")

async def check_lifecycle_observability_helpers() -> None:
    cmd = make_swarm_command(
        command_type="PAUSE",
        source_agent="smoke",
        source_swarm="overseer",
        target_swarm="explorer",
        target_role="node",
        target_node="exp-smoke-observability",
        ttl_seconds=300,
        payload={"reason": "smoke observability"},
    )

    payload = lifecycle_event_payload(
        cmd,
        status=LIFECYCLE_STATUS_APPLIED,
    )

    event = {
        "type": "swarm_event",
        "event_type": LIFECYCLE_EVENT_APPLIED,
        "payload": payload,
    }

    assert_true(payload["action"] == "PAUSE", "lifecycle payload action mismatch")
    assert_true(payload["status"] == "applied", "lifecycle payload status mismatch")
    assert_true(payload["reason"] == "smoke observability", "lifecycle payload reason mismatch")
    assert_true(is_lifecycle_event(event) is True, "event should be lifecycle event")
    assert_true(lifecycle_event_status(event) == "applied", "lifecycle event status mismatch")
    assert_true(lifecycle_event_action(event) == "PAUSE", "lifecycle event action mismatch")
    assert_true(lifecycle_event_reason(event) == "smoke observability", "lifecycle event reason mismatch")

async def check_command_observability_helpers() -> None:
    cmd = make_swarm_command(
        command_type="UNBLOCK_ALL",
        source_agent="smoke",
        source_swarm="overseer",
        target_swarm="security",
        target_role="node",
        target_node="sec-smoke-observability",
        ttl_seconds=300,
        payload={"reason": "smoke command observability"},
    )

    payload = command_event_payload(
        cmd,
        status=COMMAND_STATUS_SKIPPED,
    )

    event = {
        "type": "swarm_event",
        "event_type": COMMAND_EVENT_SKIPPED,
        "payload": payload,
    }

    assert_true(payload["action"] == "UNBLOCK_ALL", "command payload action mismatch")
    assert_true(payload["status"] == "skipped", "command payload status mismatch")
    assert_true(payload["reason"] == "smoke command observability", "command payload reason mismatch")
    assert_true(is_command_event(event) is True, "event should be command event")
    assert_true(command_event_status(event) == "skipped", "command event status mismatch")
    assert_true(command_event_action(event) == "UNBLOCK_ALL", "command event action mismatch")
    assert_true(command_event_reason(event) == "smoke command observability", "command event reason mismatch")

async def check_overseer_collector_command_events_visibility() -> None:
    class Dummy:
        def __init__(self):
            cmd_pause = make_swarm_command(
                command_type="PAUSE",
                source_agent="smoke",
                source_swarm="overseer",
                target_swarm="explorer",
                target_role="node",
                target_node="exp-smoke-command-events",
                ttl_seconds=300,
                payload={"reason": "smoke collector command events"},
            )

            cmd_unblock = make_swarm_command(
                command_type="UNBLOCK_ALL",
                source_agent="smoke",
                source_swarm="overseer",
                target_swarm="security",
                target_role="node",
                target_node="sec-smoke-command-events",
                ttl_seconds=300,
                payload={"reason": "paused"},
            )

            self.state = {
                "hb_exp": {
                    "type": "swarm_heartbeat",
                    "source_swarm": "explorer",
                    "source_node": "exp-smoke-command-events",
                    "role": "node",
                    "timestamp": 9999999999,
                    "metrics": {},
                },
                "hb_sec": {
                    "type": "swarm_heartbeat",
                    "source_swarm": "security",
                    "source_node": "sec-smoke-command-events",
                    "role": "node",
                    "timestamp": 9999999999,
                    "metrics": {},
                },
                "evt_exp": {
                    "type": "swarm_event",
                    "event_type": LIFECYCLE_EVENT_APPLIED,
                    "source_swarm": "explorer",
                    "source_node": "exp-smoke-command-events",
                    "timestamp": 9999999999,
                    "payload": lifecycle_event_payload(
                        cmd_pause,
                        status=LIFECYCLE_STATUS_APPLIED,
                    ),
                },
                "evt_sec": {
                    "type": "swarm_event",
                    "event_type": COMMAND_EVENT_SKIPPED,
                    "source_swarm": "security",
                    "source_node": "sec-smoke-command-events",
                    "timestamp": 9999999999,
                    "payload": command_event_payload(
                        cmd_unblock,
                        status=COMMAND_STATUS_SKIPPED,
                    ),
                },
            }

    collector = StateCollector(Dummy())
    health = collector.collect_topology_health()

    assert_true(
        health["command_events"]["applied"] == 1,
        "ecosystem command_events.applied should be 1",
    )
    assert_true(
        health["command_events"]["skipped"] == 1,
        "ecosystem command_events.skipped should be 1",
    )
    assert_true(
        health["swarms"]["explorer"]["command_events"]["applied"] == 1,
        "explorer command_events.applied should be 1",
    )
    assert_true(
        health["swarms"]["security"]["command_events"]["skipped"] == 1,
        "security command_events.skipped should be 1",
    )

async def check_overseer_topology_command_events_summary() -> None:
    topology_health = {
        "type": "ecosystem",
        "topology_version": "v1",
        "swarm_count": 2,
        "total_nodes": 2,
        "total_stale_nodes": 0,
        "command_event_window_seconds": COMMAND_EVENT_WINDOW_SECONDS,
        "command_events": {
            "applied": 1,
            "skipped": 3,
            "blocked": 0,
            "unsupported": 0,
            "received": 0,
            "unknown": 0,
        },
        "swarms": {
            "explorer": {
                "status": "ok",
                "node_count": 1,
                "role_counts": {"node": 1},
                "advisory_only": False,
                "managed_by_overseer": True,
                "stale_nodes": [],
                "commands": 0,
                "events": 1,
                "command_events": {
                    "applied": 1,
                    "skipped": 0,
                    "blocked": 0,
                    "unsupported": 0,
                    "received": 0,
                    "unknown": 0,
                },
                "latest_ts": 9999999999.0,
            },
            "security": {
                "status": "ok",
                "node_count": 1,
                "role_counts": {"node": 1},
                "advisory_only": False,
                "managed_by_overseer": True,
                "stale_nodes": [],
                "commands": 0,
                "events": 1,
                "command_event_window_seconds": COMMAND_EVENT_WINDOW_SECONDS,
                "command_events": {
                    "applied": 0,
                    "skipped": 3,
                    "blocked": 0,
                    "unsupported": 0,
                    "received": 0,
                    "unknown": 0,
                },
                "latest_ts": 9999999999.0,
            },
        },
    }

    summary = OverseerNode.summarize_topology_health(topology_health)

    assert_true(summary["command_events"]["applied"] == 1, "summary command_events.applied mismatch")
    assert_true(summary["command_events"]["skipped"] == 3, "summary command_events.skipped mismatch")
    assert_true(
        summary["swarms"]["explorer"]["command_events"]["applied"] == 1,
        "explorer summary command_events.applied mismatch",
    )
    assert_true(
        summary["swarms"]["security"]["command_events"]["skipped"] == 3,
        "security summary command_events.skipped mismatch",
    )
    assert_true(
        summary["command_event_window_seconds"] == COMMAND_EVENT_WINDOW_SECONDS,
        "summary command_event_window_seconds mismatch",
    )
    assert_true(
        summary["swarms"]["security"]["command_event_window_seconds"] == COMMAND_EVENT_WINDOW_SECONDS,
        "security summary command_event_window_seconds mismatch",
    )

async def check_overseer_topology_command_warnings() -> None:
    class DummyStrategist:
        async def suggest(self, snapshot):
            return {}

    node = OverseerNode(node_id="overseer-smoke-command-warnings")
    node.strategist = DummyStrategist()

    node._last_topology_health = {
        "swarms": {
            "security": {
                "managed_by_overseer": True,
                "advisory_only": False,
                "node_count": 1,
                "status": "ok",
                "stale_nodes": [],
                "command_event_window_seconds": COMMAND_EVENT_WINDOW_SECONDS,
                "command_events": {
                    "applied": 2,
                    "skipped": 3,
                    "blocked": 0,
                    "unsupported": 0,
                    "received": 0,
                    "unknown": 0,
                },
            },
            "explorer": {
                "managed_by_overseer": True,
                "advisory_only": False,
                "node_count": 1,
                "status": "ok",
                "stale_nodes": [],
                "command_event_window_seconds": COMMAND_EVENT_WINDOW_SECONDS,
                "command_events": {
                    "applied": 1,
                    "skipped": 0,
                    "blocked": 1,
                    "unsupported": 1,
                    "received": 0,
                    "unknown": 0,
                },
            },
        }
    }

    snapshot = node.collector.collect()
    decision = await node.global_decide(snapshot)

    warnings = decision.payload.get("topology_command_warnings", [])

    assert_true(len(warnings) == 2, f"expected 2 topology command warnings, got {len(warnings)}")
    assert_true(
        any(w.get("swarm") == "security" and w.get("skipped") == 3 for w in warnings),
        "expected security skipped command warning",
    )
    assert_true(
        any(
            w.get("swarm") == "explorer"
            and w.get("blocked") == 1
            and w.get("unsupported") == 1
            for w in warnings
        ),
        "expected explorer blocked/unsupported command warning",
    )
    assert_true(
        any(
            w.get("swarm") == "security"
            and w.get("skipped") == 3
            and w.get("window_seconds") == COMMAND_EVENT_WINDOW_SECONDS
            for w in warnings
        ),
        "expected security skipped command warning with window metadata",
    )
    assert_true(
        any(
            w.get("swarm") == "explorer"
            and w.get("blocked") == 1
            and w.get("unsupported") == 1
            and w.get("window_seconds") == COMMAND_EVENT_WINDOW_SECONDS
            for w in warnings
        ),
        "expected explorer blocked/unsupported command warning with window metadata",
    )

async def check_overseer_persisted_topology_command_warnings() -> None:
    class DummyStrategist:
        async def suggest(self, snapshot):
            return {}

    node = OverseerNode(node_id="overseer-smoke-command-warning-persist")
    node.strategist = DummyStrategist()

    node._last_topology_health = {
        "swarms": {
            "security": {
                "managed_by_overseer": True,
                "advisory_only": False,
                "node_count": 1,
                "status": "ok",
                "stale_nodes": [],
                "command_event_window_seconds": COMMAND_EVENT_WINDOW_SECONDS,
                "command_events": {
                    "applied": 2,
                    "skipped": 3,
                    "blocked": 0,
                    "unsupported": 0,
                    "received": 0,
                    "unknown": 0,
                },
            }
        }
    }

    snapshot = node.collector.collect()
    decision = await node.global_decide(snapshot)

    directives = []
    await node.persist_global_decision(decision, snapshot, directives)

    events = [
        item for item in node.crdt.state.values()
        if isinstance(item, dict)
        and item.get("type") == "swarm_event"
        and item.get("event_type") == "overseer_cycle_completed"
        and item.get("source_node") == node.overseer_id
    ]

    assert_true(events, "overseer_cycle_completed event missing")

    payload = events[-1].get("payload", {})
    warnings = payload.get("topology_command_warnings", [])

    assert_true(warnings, "topology_command_warnings missing from persisted decision")
    assert_true(
        any(
            item.get("swarm") == "security"
            and item.get("skipped") == 3
            and item.get("window_seconds") == COMMAND_EVENT_WINDOW_SECONDS
            for item in warnings
        ),
        "expected persisted security skipped command warning with window metadata",
    )

    assert_true(
        payload.get("command_event_thresholds") == command_event_thresholds(),
        "persisted command_event_thresholds mismatch",
    )

    decision_payload = payload.get("decision_payload", {})
    nested_warnings = (
        decision_payload.get("topology_command_warnings", [])
        if isinstance(decision_payload, dict)
        else []
    )

    assert_true(
        nested_warnings,
        "decision_payload.topology_command_warnings missing",
    )

    assert_true(
        any(
            item.get("swarm") == "security"
            and item.get("window_seconds") == COMMAND_EVENT_WINDOW_SECONDS
            for item in nested_warnings
        ),
        "expected nested persisted command warning window metadata",
    )

    assert_true(
        isinstance(decision_payload, dict)
        and decision_payload.get("command_event_thresholds") == command_event_thresholds(),
        "decision_payload command_event_thresholds mismatch",
    )

async def check_overseer_command_friction_advisory_directives() -> None:
    class DummyStrategist:
        async def suggest(self, snapshot):
            return {}

    node = OverseerNode(node_id="overseer-smoke-command-friction-directives")
    node.strategist = DummyStrategist()

    node._last_topology_health = {
        "swarms": {
            "command_event_window_seconds": COMMAND_EVENT_WINDOW_SECONDS,
            "security": {
                "managed_by_overseer": True,
                "advisory_only": False,
                "node_count": 1,
                "status": "ok",
                "stale_nodes": [],
                "command_event_window_seconds": COMMAND_EVENT_WINDOW_SECONDS,
                "command_events": {
                    "applied": 2,
                    "skipped": 3,
                    "blocked": 0,
                    "unsupported": 0,
                    "received": 0,
                    "unknown": 0,
                },
            },
            "explorer": {
                "managed_by_overseer": True,
                "advisory_only": False,
                "node_count": 1,
                "status": "ok",
                "stale_nodes": [],
                "command_event_window_seconds": COMMAND_EVENT_WINDOW_SECONDS,
                "command_events": {
                    "applied": 1,
                    "skipped": 0,
                    "blocked": 1,
                    "unsupported": 1,
                    "received": 0,
                    "unknown": 0,
                },
            },
        }
    }

    snapshot = node.collector.collect()
    decision = await node.global_decide(snapshot)
    directives = await node.route_directives(decision, snapshot)

    friction = [
        item for item in directives
        if item.get("source") == "topology_command_warnings"
    ]

    assert_true(len(friction) == 2, f"expected 2 command friction advisory directives, got {len(friction)}")

    assert_true(
        any(
            item.get("target_swarm") == "security"
            and item.get("action") == "INVESTIGATE_COMMAND_FRICTION"
            and item.get("skipped") == 3
            and item.get("window_seconds") == COMMAND_EVENT_WINDOW_SECONDS
            and item.get("advisory_only") is True
            and item.get("execution_enabled") is False
            for item in friction
        ),
        "expected security command friction advisory",
    )

    assert_true(
        any(
            item.get("target_swarm") == "explorer"
            and item.get("blocked") == 1
            and item.get("unsupported") == 1
            and item.get("window_seconds") == COMMAND_EVENT_WINDOW_SECONDS
            and item.get("advisory_only") is True
            and item.get("execution_enabled") is False
            for item in friction
        ),
        "expected explorer command friction advisory",
    )

    emitted_commands = [
        item for item in node.crdt.state.values()
        if isinstance(item, dict)
        and item.get("source_node") == node.overseer_id
        and item.get("type") in {
            "swarm_command",
            "sec_command",
            "explorer_command",
            "meta_command_json",
            "trade_command",
        }
        and item.get("command_type") == "INVESTIGATE_COMMAND_FRICTION"
    ]

    assert_true(not emitted_commands, "friction advisory must not emit commands")

async def check_policy_command_skipped_threshold() -> None:
    policy = PolicyEngine()

    topology = {
        "swarms": {
            "security": {
                "managed_by_overseer": True,
                "advisory_only": False,
                "node_count": 1,
                "status": "ok",
                "stale_nodes": [],
                "command_events": {
                    "applied": 2,
                    "skipped": 1,
                    "blocked": 0,
                    "unsupported": 0,
                    "received": 0,
                    "unknown": 0,
                },
            }
        }
    }

    result = policy.evaluate_topology_rules(topology)

    assert_true(
        result["has_command_event_warnings"] is False,
        "skipped below threshold should not create command event warning",
    )
    assert_true(
        result["command_event_warnings"] == [],
        "skipped below threshold should not produce warning records",
    )

async def check_overseer_collector_command_event_windowing() -> None:
    class Dummy:
        def __init__(self):
            now = time.time()

            cmd_old = make_swarm_command(
                command_type="UNBLOCK_ALL",
                source_agent="smoke",
                source_swarm="overseer",
                target_swarm="security",
                target_role="node",
                target_node="sec-smoke-old",
                ttl_seconds=300,
                payload={"reason": "old paused"},
            )

            cmd_recent = make_swarm_command(
                command_type="UNBLOCK_ALL",
                source_agent="smoke",
                source_swarm="overseer",
                target_swarm="security",
                target_role="node",
                target_node="sec-smoke-recent",
                ttl_seconds=300,
                payload={"reason": "recent paused"},
            )

            self.state = {
                "hb_sec": {
                    "type": "swarm_heartbeat",
                    "source_swarm": "security",
                    "source_node": "sec-smoke-recent",
                    "role": "node",
                    "timestamp": now,
                    "metrics": {},
                },
                "old_evt": {
                    "type": "swarm_event",
                    "event_type": COMMAND_EVENT_SKIPPED,
                    "source_swarm": "security",
                    "source_node": "sec-smoke-old",
                    "timestamp": now - COMMAND_EVENT_WINDOW_SECONDS - 60,
                    "payload": command_event_payload(
                        cmd_old,
                        status=COMMAND_STATUS_SKIPPED,
                    ),
                },
                "recent_evt": {
                    "type": "swarm_event",
                    "event_type": COMMAND_EVENT_SKIPPED,
                    "source_swarm": "security",
                    "source_node": "sec-smoke-recent",
                    "timestamp": now - 10,
                    "payload": command_event_payload(
                        cmd_recent,
                        status=COMMAND_STATUS_SKIPPED,
                    ),
                },
            }

    collector = StateCollector(Dummy())
    health = collector.collect_topology_health()

    assert_true(
        health["command_event_window_seconds"] == COMMAND_EVENT_WINDOW_SECONDS,
        "top-level command event window mismatch",
    )
    assert_true(
        health["swarms"]["security"]["command_event_window_seconds"] == COMMAND_EVENT_WINDOW_SECONDS,
        "security command event window mismatch",
    )
    assert_true(
        health["command_events"]["skipped"] == 1,
        "old command event should be ignored by ecosystem window count",
    )
    assert_true(
        health["swarms"]["security"]["command_events"]["skipped"] == 1,
        "old command event should be ignored by security window count",
    )

async def check_policy_command_friction_window_ignores_old_events() -> None:
    class Dummy:
        def __init__(self):
            now = time.time()
            self.state = {
                "hb_sec": {
                    "type": "swarm_heartbeat",
                    "source_swarm": "security",
                    "source_node": "sec-smoke-window-policy",
                    "role": "node",
                    "timestamp": now,
                    "metrics": {},
                }
            }

            for idx in range(3):
                cmd = make_swarm_command(
                    command_type="UNBLOCK_ALL",
                    source_agent="smoke",
                    source_swarm="overseer",
                    target_swarm="security",
                    target_role="node",
                    target_node=f"sec-smoke-old-{idx}",
                    ttl_seconds=300,
                    payload={"reason": "old paused"},
                )

                self.state[f"old_evt_{idx}"] = {
                    "type": "swarm_event",
                    "event_type": COMMAND_EVENT_SKIPPED,
                    "source_swarm": "security",
                    "source_node": f"sec-smoke-old-{idx}",
                    "timestamp": now - COMMAND_EVENT_WINDOW_SECONDS - 60 - idx,
                    "payload": command_event_payload(
                        cmd,
                        status=COMMAND_STATUS_SKIPPED,
                    ),
                }

    collector = StateCollector(Dummy())
    health = collector.collect_topology_health()
    result = PolicyEngine().evaluate_topology_rules(health)

    assert_true(
        health["swarms"]["security"]["command_events"]["skipped"] == 0,
        "old skipped events should not count in command event window",
    )
    assert_true(
        result["has_command_event_warnings"] is False,
        "old skipped events should not create command friction warning",
    )
    assert_true(
        result["command_event_warnings"] == [],
        "old skipped events should not produce command friction warning records",
    )

async def check_command_friction_default_config() -> None:
    from src.swarms.overseer.overseer_core.policy import (
        COMMAND_BLOCKED_WARNING_THRESHOLD,
        COMMAND_SKIPPED_WARNING_THRESHOLD,
        COMMAND_UNSUPPORTED_WARNING_THRESHOLD,
    )

    assert_true(
        COMMAND_EVENT_WINDOW_SECONDS == 900,
        "default command event window should be 900 seconds",
    )
    assert_true(
        COMMAND_SKIPPED_WARNING_THRESHOLD == 3,
        "default skipped threshold should be 3",
    )
    assert_true(
        COMMAND_BLOCKED_WARNING_THRESHOLD == 1,
        "default blocked threshold should be 1",
    )
    assert_true(
        COMMAND_UNSUPPORTED_WARNING_THRESHOLD == 1,
        "default unsupported threshold should be 1",
    )

async def check_overseer_collector_legacy_command_visibility() -> None:
    class Dummy:
        def __init__(self):
            self.state = {
                "hb_sec": {
                    "type": "swarm_heartbeat",
                    "source_swarm": "security",
                    "source_node": "sec-smoke-legacy",
                    "role": "node",
                    "timestamp": 9999999999,
                    "metrics": {},
                },
                "hb_exp": {
                    "type": "swarm_heartbeat",
                    "source_swarm": "explorer",
                    "source_node": "exp-smoke-legacy",
                    "role": "node",
                    "timestamp": 9999999999,
                    "metrics": {},
                },
                "legacy_sec": {
                    "type": "sec_command",
                    "gid": "legacy-sec-smoke-1",
                    "data": {"action": "UNBLOCK_ALL"},
                    "timestamp": 9999999999,
                },
                "legacy_exp": {
                    "type": "explorer_command",
                    "gid": "legacy-exp-smoke-1",
                    "data": {"action": "PAUSE"},
                    "timestamp": 9999999999,
                },
                "canonical": {
                    "type": "swarm_command",
                    "gid": "canonical-smoke-1",
                    "command_type": "PAUSE",
                    "target_swarm": "explorer",
                    "timestamp": 9999999999,
                },
            }

    collector = StateCollector(Dummy())
    health = collector.collect_topology_health()

    assert_true(
        health["legacy_commands"]["sec_command"] == 1,
        "top-level sec_command legacy count mismatch",
    )
    assert_true(
        health["legacy_commands"]["explorer_command"] == 1,
        "top-level explorer_command legacy count mismatch",
    )
    assert_true(
        health["legacy_commands"]["meta_command_json"] == 0,
        "top-level meta_command_json legacy count mismatch",
    )
    assert_true(
        health["legacy_commands"]["trade_command"] == 0,
        "top-level trade_command legacy count mismatch",
    )
    assert_true(
        health["swarms"]["security"]["legacy_commands"]["sec_command"] == 1,
        "security sec_command legacy count mismatch",
    )
    assert_true(
        health["swarms"]["explorer"]["legacy_commands"]["explorer_command"] == 1,
        "explorer explorer_command legacy count mismatch",
    )

async def check_overseer_topology_legacy_command_summary() -> None:
    summary = OverseerNode.summarize_topology_health({
        "type": "ecosystem",
        "topology_version": "v1",
        "swarm_count": 2,
        "total_nodes": 2,
        "total_stale_nodes": 0,
        "legacy_command_window_seconds": COMMAND_EVENT_WINDOW_SECONDS,
        "legacy_commands": {
            "sec_command": 1,
            "explorer_command": 1,
            "meta_command_json": 0,
            "trade_command": 0,
        },
        "swarms": {
            "security": {
                "status": "ok",
                "node_count": 1,
                "role_counts": {"node": 1},
                "advisory_only": False,
                "managed_by_overseer": True,
                "stale_nodes": [],
                "commands": 1,
                "events": 0,
                "legacy_command_window_seconds": COMMAND_EVENT_WINDOW_SECONDS,
                "legacy_commands": {
                    "sec_command": 1,
                    "explorer_command": 0,
                    "meta_command_json": 0,
                    "trade_command": 0,
                },
                "latest_ts": 9999999999.0,
            },
            "explorer": {
                "status": "ok",
                "node_count": 1,
                "role_counts": {"node": 1},
                "advisory_only": False,
                "managed_by_overseer": True,
                "stale_nodes": [],
                "commands": 2,
                "events": 0,
                "legacy_command_window_seconds": COMMAND_EVENT_WINDOW_SECONDS,
                "legacy_commands": {
                    "sec_command": 0,
                    "explorer_command": 1,
                    "meta_command_json": 0,
                    "trade_command": 0,
                },
                "latest_ts": 9999999999.0,
            },
        },
    })

    assert_true(
        summary["legacy_commands"]["sec_command"] == 1,
        "summary legacy sec_command count mismatch",
    )
    assert_true(
        summary["legacy_commands"]["explorer_command"] == 1,
        "summary legacy explorer_command count mismatch",
    )
    assert_true(
        summary["swarms"]["security"]["legacy_commands"]["sec_command"] == 1,
        "security summary legacy sec_command count mismatch",
    )
    assert_true(
        summary["swarms"]["explorer"]["legacy_commands"]["explorer_command"] == 1,
        "explorer summary legacy explorer_command count mismatch",
    )
    assert_true(
        summary["legacy_command_window_seconds"] == COMMAND_EVENT_WINDOW_SECONDS,
        "summary legacy_command_window_seconds mismatch",
    )
    assert_true(
        summary["swarms"]["security"]["legacy_command_window_seconds"] == COMMAND_EVENT_WINDOW_SECONDS,
        "security summary legacy_command_window_seconds mismatch",
    )

async def check_overseer_legacy_command_warnings_payload() -> None:
    class DummyStrategist:
        async def suggest(self, snapshot):
            return {}

    node = OverseerNode(node_id="overseer-smoke-legacy-warning-payload")
    node.strategist = DummyStrategist()

    node._last_topology_health = {
        "swarms": {
            "security": {
                "managed_by_overseer": True,
                "advisory_only": False,
                "node_count": 1,
                "status": "ok",
                "stale_nodes": [],
                "legacy_commands": {
                    "sec_command": 2,
                    "explorer_command": 0,
                    "meta_command_json": 0,
                    "trade_command": 0,
                },
                "command_events": {
                    "applied": 0,
                    "skipped": 0,
                    "blocked": 0,
                    "unsupported": 0,
                    "received": 0,
                    "unknown": 0,
                },
            },
            "explorer": {
                "managed_by_overseer": True,
                "advisory_only": False,
                "node_count": 1,
                "status": "ok",
                "stale_nodes": [],
                "legacy_commands": {
                    "sec_command": 0,
                    "explorer_command": 1,
                    "meta_command_json": 0,
                    "trade_command": 0,
                },
                "command_events": {
                    "applied": 0,
                    "skipped": 0,
                    "blocked": 0,
                    "unsupported": 0,
                    "received": 0,
                    "unknown": 0,
                },
            },
        }
    }

    snapshot = node.collector.collect()
    decision = await node.global_decide(snapshot)

    warnings = decision.payload.get("topology_legacy_command_warnings", [])

    assert_true(len(warnings) == 2, f"expected 2 legacy command warnings, got {len(warnings)}")
    assert_true(
        any(
            item.get("swarm") == "security"
            and item.get("legacy_commands", {}).get("sec_command") == 2
            and item.get("total") == 2
            for item in warnings
        ),
        "expected security legacy command warning",
    )
    assert_true(
        any(
            item.get("swarm") == "explorer"
            and item.get("legacy_commands", {}).get("explorer_command") == 1
            and item.get("total") == 1
            for item in warnings
        ),
        "expected explorer legacy command warning",
    )

async def check_overseer_persisted_legacy_command_warnings() -> None:
    class DummyStrategist:
        async def suggest(self, snapshot):
            return {}

    node = OverseerNode(node_id="overseer-smoke-legacy-warning-persist")
    node.strategist = DummyStrategist()

    node._last_topology_health = {
        "swarms": {
            "security": {
                "managed_by_overseer": True,
                "advisory_only": False,
                "node_count": 1,
                "status": "ok",
                "stale_nodes": [],
                "legacy_commands": {
                    "sec_command": 2,
                    "explorer_command": 0,
                    "meta_command_json": 0,
                    "trade_command": 0,
                },
                "command_events": {
                    "applied": 0,
                    "skipped": 0,
                    "blocked": 0,
                    "unsupported": 0,
                    "received": 0,
                    "unknown": 0,
                },
            }
        }
    }

    snapshot = node.collector.collect()
    decision = await node.global_decide(snapshot)
    await node.persist_global_decision(decision, snapshot, [])

    events = [
        item for item in node.crdt.state.values()
        if isinstance(item, dict)
        and item.get("type") == "swarm_event"
        and item.get("event_type") == "overseer_cycle_completed"
        and item.get("source_node") == node.overseer_id
    ]

    assert_true(events, "overseer_cycle_completed event missing")

    payload = events[-1].get("payload", {})
    warnings = payload.get("topology_legacy_command_warnings", [])

    assert_true(warnings, "topology_legacy_command_warnings missing from persisted decision")
    assert_true(
        any(
            item.get("swarm") == "security"
            and item.get("legacy_commands", {}).get("sec_command") == 2
            and item.get("total") == 2
            for item in warnings
        ),
        "expected persisted security legacy command warning",
    )

    decision_payload = payload.get("decision_payload", {})
    nested_warnings = (
        decision_payload.get("topology_legacy_command_warnings", [])
        if isinstance(decision_payload, dict)
        else []
    )

    assert_true(nested_warnings, "decision_payload.topology_legacy_command_warnings missing")
    assert_true(
        any(
            item.get("swarm") == "security"
            and item.get("legacy_commands", {}).get("sec_command") == 2
            for item in nested_warnings
        ),
        "expected nested persisted security legacy command warning",
    )

async def check_overseer_legacy_command_migration_advisory_directives() -> None:
    class DummyStrategist:
        async def suggest(self, snapshot):
            return {}

    node = OverseerNode(node_id="overseer-smoke-legacy-migration-directives")
    node.strategist = DummyStrategist()

    node._last_topology_health = {
        "swarms": {
            "security": {
                "managed_by_overseer": True,
                "advisory_only": False,
                "node_count": 1,
                "status": "ok",
                "stale_nodes": [],
                "legacy_commands": {
                    "sec_command": 2,
                    "explorer_command": 0,
                    "meta_command_json": 0,
                    "trade_command": 0,
                },
                "command_events": {
                    "applied": 0,
                    "skipped": 0,
                    "blocked": 0,
                    "unsupported": 0,
                    "received": 0,
                    "unknown": 0,
                },
            },
            "explorer": {
                "managed_by_overseer": True,
                "advisory_only": False,
                "node_count": 1,
                "status": "ok",
                "stale_nodes": [],
                "legacy_commands": {
                    "sec_command": 0,
                    "explorer_command": 1,
                    "meta_command_json": 0,
                    "trade_command": 0,
                },
                "command_events": {
                    "applied": 0,
                    "skipped": 0,
                    "blocked": 0,
                    "unsupported": 0,
                    "received": 0,
                    "unknown": 0,
                },
            },
        }
    }

    snapshot = node.collector.collect()
    decision = await node.global_decide(snapshot)
    directives = await node.route_directives(decision, snapshot)

    migration = [
        item for item in directives
        if item.get("source") == "legacy_command_warnings"
    ]

    assert_true(len(migration) == 2, f"expected 2 legacy migration advisory directives, got {len(migration)}")

    assert_true(
        any(
            item.get("target_swarm") == "security"
            and item.get("action") == "MIGRATE_LEGACY_COMMANDS"
            and item.get("legacy_commands", {}).get("sec_command") == 2
            and item.get("total") == 2
            and item.get("advisory_only") is True
            and item.get("execution_enabled") is False
            for item in migration
        ),
        "expected security legacy migration advisory",
    )

    assert_true(
        any(
            item.get("target_swarm") == "explorer"
            and item.get("legacy_commands", {}).get("explorer_command") == 1
            and item.get("total") == 1
            and item.get("advisory_only") is True
            and item.get("execution_enabled") is False
            for item in migration
        ),
        "expected explorer legacy migration advisory",
    )

    emitted_commands = [
        item for item in node.crdt.state.values()
        if isinstance(item, dict)
        and item.get("source_node") == node.overseer_id
        and item.get("type") in {
            "swarm_command",
            "sec_command",
            "explorer_command",
            "meta_command_json",
            "trade_command",
        }
        and item.get("command_type") == "MIGRATE_LEGACY_COMMANDS"
    ]

    assert_true(not emitted_commands, "legacy migration advisory must not emit commands")

async def check_overseer_collector_legacy_command_windowing() -> None:
    class Dummy:
        def __init__(self):
            now = time.time()
            self.state = {
                "hb_sec": {
                    "type": "swarm_heartbeat",
                    "source_swarm": "security",
                    "source_node": "sec-smoke-legacy-window",
                    "role": "node",
                    "timestamp": now,
                    "metrics": {},
                },
                "old_legacy_sec": {
                    "type": "sec_command",
                    "gid": "legacy-sec-smoke-old",
                    "data": {"action": "UNBLOCK_ALL"},
                    "timestamp": now - COMMAND_EVENT_WINDOW_SECONDS - 60,
                },
                "recent_legacy_sec": {
                    "type": "sec_command",
                    "gid": "legacy-sec-smoke-recent",
                    "data": {"action": "UNBLOCK_ALL"},
                    "timestamp": now - 10,
                },
            }

    collector = StateCollector(Dummy())
    health = collector.collect_topology_health()

    assert_true(
        health["legacy_command_window_seconds"] == COMMAND_EVENT_WINDOW_SECONDS,
        "top-level legacy command window mismatch",
    )
    assert_true(
        health["legacy_commands"]["sec_command"] == 1,
        "old legacy command should be ignored by top-level window count",
    )
    assert_true(
        health["swarms"]["security"]["legacy_commands"]["sec_command"] == 1,
        "old legacy command should be ignored by security window count",
    )
    assert_true(
        health["swarms"]["security"]["legacy_command_window_seconds"] == COMMAND_EVENT_WINDOW_SECONDS,
        "security legacy command window mismatch",
    )

async def check_policy_legacy_command_window_ignores_old_commands() -> None:
    class Dummy:
        def __init__(self):
            now = time.time()
            self.state = {
                "hb_sec": {
                    "type": "swarm_heartbeat",
                    "source_swarm": "security",
                    "source_node": "sec-smoke-legacy-window-policy",
                    "role": "node",
                    "timestamp": now,
                    "metrics": {},
                },
                "old_legacy_sec": {
                    "type": "sec_command",
                    "gid": "legacy-sec-smoke-old-policy",
                    "data": {"action": "UNBLOCK_ALL"},
                    "timestamp": now - COMMAND_EVENT_WINDOW_SECONDS - 60,
                },
            }

    collector = StateCollector(Dummy())
    health = collector.collect_topology_health()
    result = PolicyEngine().evaluate_topology_rules(health)

    assert_true(
        health["legacy_commands"]["sec_command"] == 0,
        "old legacy command should not count in top-level legacy window",
    )
    assert_true(
        health["swarms"]["security"]["legacy_commands"]["sec_command"] == 0,
        "old legacy command should not count in security legacy window",
    )
    assert_true(
        result["has_legacy_command_warnings"] is False,
        "old legacy command should not create legacy warning",
    )
    assert_true(
        result["legacy_command_warnings"] == [],
        "old legacy command should not produce warning records",
    )

async def check_overseer_observability_config_metadata() -> None:
    class DummyStrategist:
        async def suggest(self, snapshot):
            return {}

    node = OverseerNode(node_id="overseer-smoke-observability-config")
    node.strategist = DummyStrategist()

    node._last_topology_health = {
        "command_event_window_seconds": COMMAND_EVENT_WINDOW_SECONDS,
        "legacy_command_window_seconds": COMMAND_EVENT_WINDOW_SECONDS,
        "swarms": {
            "security": {
                "managed_by_overseer": True,
                "advisory_only": False,
                "node_count": 1,
                "status": "ok",
                "stale_nodes": [],
                "command_events": {
                    "applied": 0,
                    "skipped": 3,
                    "blocked": 0,
                    "unsupported": 0,
                    "received": 0,
                    "unknown": 0,
                },
                "legacy_commands": {
                    "sec_command": 1,
                    "explorer_command": 0,
                    "meta_command_json": 0,
                    "trade_command": 0,
                },
            }
        }
    }

    snapshot = node.collector.collect()
    decision = await node.global_decide(snapshot)

    config = decision.payload.get("observability_config", {})

    assert_true(
        config.get("command_event_window_seconds") == COMMAND_EVENT_WINDOW_SECONDS,
        "observability_config command_event_window_seconds mismatch",
    )
    assert_true(
        config.get("legacy_command_window_seconds") == COMMAND_EVENT_WINDOW_SECONDS,
        "observability_config legacy_command_window_seconds mismatch",
    )
    assert_true(
        config.get("command_event_thresholds") == command_event_thresholds(),
        "observability_config command_event_thresholds mismatch",
    )

    await node.persist_global_decision(decision, snapshot, [])

    events = [
        item for item in node.crdt.state.values()
        if isinstance(item, dict)
        and item.get("type") == "swarm_event"
        and item.get("event_type") == "overseer_cycle_completed"
        and item.get("source_node") == node.overseer_id
    ]

    assert_true(events, "overseer_cycle_completed event missing")

    payload = events[-1].get("payload", {})
    assert_true(
        payload.get("observability_config") == config,
        "persisted observability_config mismatch",
    )

async def check_legacy_command_normalization_audit() -> None:
    records = [
        {
            "type": "sec_command",
            "gid": "legacy-sec-smoke",
            "data": {"action": "UNBLOCK_ALL"},
        },
        {
            "type": "explorer_command",
            "gid": "legacy-exp-smoke",
            "data": {"action": "PAUSE"},
        },
        {
            "type": "meta_command_json",
            "gid": "legacy-meta-smoke",
            "data": {
                "action": "PAUSE",
                "target_swarm": "explorer",
                "target_role": "meta_agent",
            },
        },
        {
            "type": "trade_command",
            "gid": "legacy-trade-smoke",
            "data": {"action": "REDUCE_RISK"},
        },
    ]

    items = normalize_commands(records)

    assert_true(len(items) == 4, f"expected 4 normalized legacy commands, got {len(items)}")

    by_legacy = {item.get("legacy_type"): item for item in items}

    assert_true(
        by_legacy["sec_command"]["type"] == "swarm_command",
        "sec_command should normalize to swarm_command",
    )
    assert_true(
        by_legacy["sec_command"]["command_type"] == "UNBLOCK_ALL",
        "sec_command action mismatch",
    )
    assert_true(
        by_legacy["sec_command"]["target_swarm"] == "security",
        "sec_command target_swarm mismatch",
    )

    assert_true(
        by_legacy["explorer_command"]["command_type"] == "PAUSE",
        "explorer_command action mismatch",
    )
    assert_true(
        by_legacy["explorer_command"]["target_swarm"] == "explorer",
        "explorer_command target_swarm mismatch",
    )

    assert_true(
        by_legacy["meta_command_json"]["command_type"] == "PAUSE",
        "meta_command_json action mismatch",
    )
    assert_true(
        by_legacy["meta_command_json"]["target_swarm"] == "explorer",
        "meta_command_json explicit target_swarm should be preserved",
    )
    assert_true(
        by_legacy["meta_command_json"]["target_role"] == "meta_agent",
        "meta_command_json explicit target_role should be preserved",
    )

    assert_true(
        by_legacy["trade_command"]["command_type"] == "REDUCE_RISK",
        "trade_command action mismatch",
    )
    assert_true(
        by_legacy["trade_command"]["target_swarm"] == "trade",
        "trade_command target_swarm mismatch",
    )

async def check_canonical_command_normalization_enrichment() -> None:
    records = [
        {
            "type": "swarm_command",
            "gid": "canonical-direct-smoke",
            "command_type": "pause",
            "target_swarm": "explorer",
            "target_role": "node",
            "target_node": "exp-1",
        },
        {
            "type": "swarm_command",
            "gid": "canonical-payload-smoke",
            "payload": {
                "action": "resume",
                "target_swarm": "security",
                "target_role": "meta_agent",
                "target_node": "sec-meta-1",
            },
        },
        {
            "type": "swarm_command",
            "gid": "canonical-data-smoke",
            "data": {
                "action": "run_once",
                "target_swarm": "improver",
                "target_role": "maintenance_agent",
                "node_id": "improver-1",
            },
        },
    ]

    items = normalize_commands(records)
    assert_true(len(items) == 3, f"expected 3 canonical normalized commands, got {len(items)}")

    by_gid = {item["gid"]: item for item in items}

    assert_true(by_gid["canonical-direct-smoke"]["command_type"] == "PAUSE", "direct canonical action mismatch")
    assert_true(by_gid["canonical-direct-smoke"]["target_swarm"] == "explorer", "direct canonical target_swarm mismatch")
    assert_true(by_gid["canonical-direct-smoke"]["target_role"] == "node", "direct canonical target_role mismatch")
    assert_true(by_gid["canonical-direct-smoke"]["target_node"] == "exp-1", "direct canonical target_node mismatch")
    assert_true(by_gid["canonical-direct-smoke"]["payload"] == {}, "direct canonical payload should be normalized to dict")
    assert_true(by_gid["canonical-direct-smoke"]["data"] == {}, "direct canonical data should be normalized to dict")

    assert_true(by_gid["canonical-payload-smoke"]["command_type"] == "RESUME", "payload canonical action mismatch")
    assert_true(by_gid["canonical-payload-smoke"]["target_swarm"] == "security", "payload canonical target_swarm mismatch")
    assert_true(by_gid["canonical-payload-smoke"]["target_role"] == "meta_agent", "payload canonical target_role mismatch")
    assert_true(by_gid["canonical-payload-smoke"]["target_node"] == "sec-meta-1", "payload canonical target_node mismatch")

    assert_true(by_gid["canonical-data-smoke"]["command_type"] == "RUN_ONCE", "data canonical action mismatch")
    assert_true(by_gid["canonical-data-smoke"]["target_swarm"] == "improver", "data canonical target_swarm mismatch")
    assert_true(by_gid["canonical-data-smoke"]["target_role"] == "maintenance_agent", "data canonical target_role mismatch")
    assert_true(by_gid["canonical-data-smoke"]["target_node"] == "improver-1", "data canonical target_node mismatch")

async def check_command_fingerprint_canonical_legacy_parity() -> None:
    canonical = normalize_commands([
        {
            "type": "swarm_command",
            "gid": "canonical-fp-1",
            "command_type": "UNBLOCK_ALL",
            "target_swarm": "security",
            "target_role": "node",
            "target_node": "",
            "payload": {},
            "data": {"action": "UNBLOCK_ALL"},
        }
    ])[0]

    legacy = normalize_commands([
        {
            "type": "sec_command",
            "gid": "legacy-fp-1",
            "data": {"action": "UNBLOCK_ALL"},
        }
    ])[0]

    assert_true(
        command_fingerprint(canonical) == command_fingerprint(legacy),
        "canonical UNBLOCK_ALL and legacy sec_command should fingerprint equally",
    )

    canonical_pause = normalize_commands([
        {
            "type": "swarm_command",
            "gid": "canonical-fp-2",
            "command_type": "PAUSE",
            "target_swarm": "explorer",
            "target_role": "node",
            "target_node": "exp-1",
            "payload": {"reason": "test"},
        }
    ])[0]

    legacy_pause = normalize_commands([
        {
            "type": "explorer_command",
            "gid": "legacy-fp-2",
            "data": {
                "action": "PAUSE",
                "node_id": "exp-1",
                "reason": "test",
            },
        }
    ])[0]

    assert_true(
        command_fingerprint(canonical_pause) == command_fingerprint(legacy_pause),
        "canonical PAUSE and legacy explorer_command should fingerprint equally",
    )

    canonical_other_reason = normalize_commands([
        {
            "type": "swarm_command",
            "gid": "canonical-fp-3",
            "command_type": "PAUSE",
            "target_swarm": "explorer",
            "target_role": "node",
            "target_node": "exp-1",
            "payload": {"reason": "different"},
        }
    ])[0]

    assert_true(
        command_fingerprint(canonical_pause) != command_fingerprint(canonical_other_reason),
        "semantic payload changes should change command fingerprint",
    )

async def check_command_normalization_idempotency() -> None:
    records = [
        {
            "type": "swarm_command",
            "gid": "canonical-idempotent-direct",
            "command_type": "pause",
            "target_swarm": "explorer",
            "target_role": "node",
            "target_node": "exp-1",
        },
        {
            "type": "swarm_command",
            "gid": "canonical-idempotent-payload",
            "payload": {
                "action": "resume",
                "target_swarm": "security",
                "target_role": "meta_agent",
                "target_node": "sec-meta-1",
            },
        },
        {
            "type": "sec_command",
            "gid": "legacy-idempotent-sec",
            "data": {"action": "UNBLOCK_ALL"},
        },
        {
            "type": "meta_command_json",
            "gid": "legacy-idempotent-meta",
            "data": {
                "action": "PAUSE",
                "target_swarm": "explorer",
                "target_role": "meta_agent",
            },
        },
    ]

    for record in records:
        once = normalize_command(record)
        twice = normalize_command(once)

        assert_true(
            once == twice,
            f"normalize_command should be idempotent for {record.get('gid')}",
        )

async def check_normalize_commands_ordering_and_skip() -> None:
    records = [
        {"type": "not_command", "gid": "skip-1"},
        {"type": "sec_command", "gid": "a", "data": {"action": "UNBLOCK_ALL"}},
        {"type": "explorer_command", "gid": "b", "data": {"action": "PAUSE"}},
        {"type": "explorer_command", "gid": "b", "data": {"action": "PAUSE"}},
        {"type": "swarm_command", "gid": "c", "command_type": "RESUME", "target_swarm": "explorer"},
        {"type": "swarm_command", "gid": "bad-no-action"},
        None,
        "bad",
    ]

    items = normalize_commands(records)

    assert_true(
        [item["gid"] for item in items] == ["a", "b", "b", "c"],
        "normalize_commands should skip invalid records and preserve valid order/duplicates",
    )
    assert_true(items[0]["legacy_type"] == "sec_command", "first valid command should be sec_command")
    assert_true(items[1]["legacy_type"] == "explorer_command", "second valid command should be explorer_command")
    assert_true(items[2]["legacy_type"] == "explorer_command", "duplicate valid command should be preserved")
    assert_true(items[3]["command_type"] == "RESUME", "canonical command action mismatch")
    assert_true(items[3]["target_swarm"] == "explorer", "canonical command target_swarm mismatch")

async def check_command_action_targets_helpers() -> None:
    canonical = normalize_command(
        {
            "type": "swarm_command",
            "gid": "canonical-helper-smoke",
            "command_type": "PAUSE",
            "target_swarm": "explorer",
            "target_role": "node",
            "target_node": "exp-1",
        }
    )

    legacy = normalize_command(
        {
            "type": "explorer_command",
            "gid": "legacy-helper-smoke",
            "data": {
                "action": "PAUSE",
                "node_id": "exp-1",
            },
        }
    )

    meta = normalize_command(
        {
            "type": "meta_command_json",
            "gid": "meta-helper-smoke",
            "data": {
                "action": "PAUSE",
                "target_swarm": "explorer",
                "target_role": "meta_agent",
                "node_id": "exp-meta-1",
            },
        }
    )

    assert_true(command_action(canonical) == "PAUSE", "canonical command_action mismatch")
    assert_true(command_action(legacy) == "PAUSE", "legacy command_action mismatch")
    assert_true(command_action(meta) == "PAUSE", "meta command_action mismatch")

    assert_true(command_targets(canonical, swarm="explorer") is True, "canonical should target explorer")
    assert_true(command_targets(canonical, swarm="security") is False, "canonical should not target security")

    assert_true(command_targets(legacy, swarm="explorer") is True, "legacy should target explorer")
    assert_true(command_targets(legacy, swarm="security") is False, "legacy should not target security")

    assert_true(command_targets(meta, swarm="explorer") is True, "meta should target explorer")
    assert_true(command_targets(meta, swarm="security") is False, "meta should not target security")

    assert_true(
        command_fingerprint(canonical) == command_fingerprint(legacy),
        "canonical and legacy helper commands should fingerprint equally",
    )

    assert_true(meta["target_swarm"] == "explorer", "meta explicit target_swarm mismatch")
    assert_true(meta["target_role"] == "meta_agent", "meta explicit target_role mismatch")
    assert_true(meta["target_node"] == "exp-meta-1", "meta explicit target_node mismatch")

async def check_executor_semantic_fingerprint() -> None:
    canonical = {
        "type": "swarm_command",
        "gid": "canonical-exec-fp-smoke",
        "command_type": "PAUSE",
        "target_swarm": "explorer",
        "target_role": "node",
        "target_node": "exp-1",
        "payload": {"reason": "test"},
    }

    legacy = {
        "type": "explorer_command",
        "gid": "legacy-exec-fp-smoke",
        "data": {
            "action": "PAUSE",
            "node_id": "exp-1",
            "reason": "test",
        },
    }

    other = {
        "type": "swarm_command",
        "gid": "canonical-exec-fp-other-smoke",
        "command_type": "PAUSE",
        "target_swarm": "explorer",
        "target_role": "node",
        "target_node": "exp-1",
        "payload": {"reason": "different"},
    }

    fp1 = ActionExecutor._generate_fingerprint(canonical)
    fp2 = ActionExecutor._generate_fingerprint(legacy)
    fp3 = ActionExecutor._generate_fingerprint(other)

    assert_true(fp1 == fp2, "executor canonical/legacy fingerprints should match")
    assert_true(fp1 != fp3, "executor semantic payload changes should change fingerprint")

async def check_executor_rate_limit_fingerprint_behavior() -> None:
    class DummySink:
        def __init__(self):
            self.items = []

        async def add_genome(self, item):
            self.items.append(dict(item))

    sink = DummySink()
    executor = ActionExecutor(sink=sink)

    now = time.time()

    canonical = {
        "type": "swarm_command",
        "gid": "canonical-rate-smoke",
        "command_type": "PAUSE",
        "target_swarm": "explorer",
        "target_role": "node",
        "target_node": "exp-1",
        "payload": {"reason": "same"},
    }

    legacy = {
        "type": "explorer_command",
        "gid": "legacy-rate-smoke",
        "data": {
            "action": "PAUSE",
            "node_id": "exp-1",
            "reason": "same",
        },
    }

    different = {
        "type": "explorer_command",
        "gid": "legacy-rate-smoke-different",
        "data": {
            "action": "PAUSE",
            "node_id": "exp-1",
            "reason": "different",
        },
    }

    assert_true(
        executor._generate_fingerprint(canonical) == executor._generate_fingerprint(legacy),
        "executor canonical/legacy equivalent fingerprints should match",
    )
    assert_true(
        executor._generate_fingerprint(canonical) != executor._generate_fingerprint(different),
        "executor semantic difference should change fingerprint",
    )

    await executor._emit_command(
        key="pause_exp_1",
        command=canonical,
        now=now,
    )

    await executor._emit_command(
        key="pause_exp_1",
        command=legacy,
        now=now + 1,
    )

    assert_true(
        len(sink.items) == 1,
        "legacy-equivalent command should be blocked within cooldown",
    )

    await executor._emit_command(
        key="pause_exp_1",
        command=different,
        now=now + 3600,
    )

    assert_true(
        len(sink.items) == 2,
        "semantic difference should emit after cooldown window",
    )

async def check_explorer_command_semantic_key_normalized() -> None:
    helper = ExplorerNode._explorer_command_semantic_key

    canonical = {
        "type": "swarm_command",
        "gid": "canonical-exp-semantic-smoke",
        "command_type": "PAUSE",
        "target_swarm": "explorer",
        "target_role": "node",
        "target_node": "",
        "payload": {"urls": ["https://b.example", "https://a.example"]},
    }

    legacy = {
        "type": "explorer_command",
        "gid": "legacy-exp-semantic-smoke",
        "data": {
            "action": "PAUSE",
            "urls": ["https://a.example", "https://b.example"],
        },
    }

    canonical_key = helper(canonical)
    legacy_key = helper(legacy)

    assert_true(
        canonical_key == legacy_key,
        "canonical and legacy explorer command semantic keys should match",
    )

    node_specific = {
        "type": "swarm_command",
        "gid": "canonical-exp-semantic-node-smoke",
        "command_type": "PAUSE",
        "target_swarm": "explorer",
        "target_role": "node",
        "target_node": "exp-1",
        "payload": {"urls": ["https://a.example"]},
    }

    assert_true(
        helper(node_specific) != helper(legacy),
        "node-specific explorer command should have distinct semantic key",
    )

async def check_security_command_semantic_key_normalized() -> None:
    helper = SecurityNode._security_command_semantic_key

    canonical = {
        "type": "swarm_command",
        "gid": "canonical-sec-semantic-smoke",
        "command_type": "UNBLOCK_ALL",
        "target_swarm": "security",
        "target_role": "node",
        "target_node": "",
        "payload": {"ips": ["10.0.0.2", "10.0.0.1"]},
    }

    legacy = {
        "type": "sec_command",
        "gid": "legacy-sec-semantic-smoke",
        "data": {
            "action": "UNBLOCK_ALL",
            "ips": ["10.0.0.1", "10.0.0.2"],
        },
    }

    canonical_key = helper(canonical)
    legacy_key = helper(legacy)

    assert_true(
        canonical_key == legacy_key,
        "canonical and legacy security command semantic keys should match",
    )

    node_specific = {
        "type": "swarm_command",
        "gid": "canonical-sec-semantic-node-smoke",
        "command_type": "UNBLOCK_ALL",
        "target_swarm": "security",
        "target_role": "node",
        "target_node": "sec-1",
        "payload": {"ips": ["10.0.0.1"]},
    }

    assert_true(
        helper(node_specific) != helper(legacy),
        "node-specific security command should have distinct semantic key",
    )

async def check_improver_command_normalization_target_action_parity() -> None:
    canonical = normalize_command(
        {
            "type": "swarm_command",
            "gid": "canonical-improver-target-smoke",
            "command_type": "RUN_ONCE",
            "target_swarm": "improver",
            "target_role": "maintenance_agent",
            "target_node": "improver-1",
            "payload": {
                "explicit_approval": True,
                "safety_gate": "approved",
                "reason": "test",
            },
        }
    )

    legacy_like = normalize_command(
        {
            "type": "meta_command_json",
            "gid": "legacy-improver-target-smoke",
            "data": {
                "action": "RUN_ONCE",
                "target_swarm": "improver",
                "target_role": "maintenance_agent",
                "node_id": "improver-1",
                "explicit_approval": True,
                "safety_gate": "approved",
                "reason": "test",
            },
        }
    )

    assert_true(command_action(canonical) == "RUN_ONCE", "canonical improver action mismatch")
    assert_true(command_action(legacy_like) == "RUN_ONCE", "legacy improver action mismatch")

    assert_true(canonical["target_swarm"] == "improver", "canonical improver target_swarm mismatch")
    assert_true(legacy_like["target_swarm"] == "improver", "legacy improver target_swarm mismatch")

    assert_true(
        canonical["target_role"] == "maintenance_agent",
        "canonical improver target_role mismatch",
    )
    assert_true(
        legacy_like["target_role"] == "maintenance_agent",
        "legacy improver target_role mismatch",
    )

    assert_true(canonical["target_node"] == "improver-1", "canonical improver target_node mismatch")
    assert_true(legacy_like["target_node"] == "improver-1", "legacy improver target_node mismatch")

    assert_true(
        canonical["payload"]["explicit_approval"] is True,
        "canonical improver explicit approval missing",
    )
    assert_true(
        legacy_like["data"]["explicit_approval"] is True,
        "legacy improver explicit approval missing",
    )

async def check_base_node_command_intake_guard() -> None:
    node = ExplorerNode(node_id="exp-smoke-command-intake-guard")

    now = time.time()
    node._command_consumer_started_at = now
    node._command_history_grace_seconds = 5

    old_command = {
        "type": "swarm_command",
        "gid": "old-command-smoke",
        "command_type": "PAUSE",
        "target_swarm": "explorer",
        "timestamp": now - 60,
    }

    recent_command = {
        "type": "swarm_command",
        "gid": "recent-command-smoke",
        "command_type": "PAUSE",
        "target_swarm": "explorer",
        "timestamp": now,
    }

    expired_command = {
        "type": "swarm_command",
        "gid": "expired-command-smoke",
        "command_type": "PAUSE",
        "target_swarm": "explorer",
        "timestamp": now,
        "expires_at": now - 1,
    }

    assert_true(
        node._should_skip_command_record(old_command) is True,
        "old command should be skipped by runtime intake guard",
    )

    assert_true(
        node._should_skip_command_record(recent_command) is False,
        "fresh command should pass runtime intake guard first time",
    )

    assert_true(
        node._should_skip_command_record(recent_command) is True,
        "same command gid should be skipped after first intake",
    )

    assert_true(
        node._should_skip_command_record(expired_command) is True,
        "expired command should be skipped by runtime intake guard",
    )

async def _test_trade_runtime_command_loop() -> None:
    from src.swarms.trade.node import SwarmNode

    class FakeCRDT:
        def __init__(self) -> None:
            self.state = {}
            self.events = []
            self.closed = False

        async def add_genome(self, item):
            self.events.append(item)

        async def close(self):
            self.closed = True

    node = SwarmNode()
    node.crdt = FakeCRDT()
    node.ctx.crdt = node.crdt

    # Keep the probe fully dry-run and isolated.
    node.tradingview_enabled = False
    node.tradingview_webhook = None
    node.market_adapter = None
    node.telegram_notifier = None

    node.crdt.state["trade-pause-smoke"] = {
        "type": "swarm_command",
        "gid": "trade-pause-smoke",
        "command_type": "PAUSE",
        "target_swarm": "trade",
        "target_node": node.node_id,
    }

    task = asyncio.create_task(node._command_loop(), name="trade_command_loop_smoke")

    for _ in range(30):
        if node._paused:
            break
        await asyncio.sleep(0.1)

    assert_true(node._paused is True, "trade command loop did not apply PAUSE")

    node.crdt.state["trade-enable-blocked-smoke"] = {
        "type": "swarm_command",
        "gid": "trade-enable-blocked-smoke",
        "command_type": "SET_EXECUTION_ENABLED",
        "target_swarm": "trade",
        "target_node": node.node_id,
        "payload": {"enabled": True},
    }

    for _ in range(30):
        if any(
            event.get("event_type") == "command_blocked"
            and event.get("payload", {}).get("action") == "SET_EXECUTION_ENABLED"
            for event in node.crdt.events
        ):
            break
        await asyncio.sleep(0.1)

    assert_true(
        node.trade_config.execution_enabled is False,
        "trade execution_enabled changed without approval",
    )
    assert_true(
        node.trade_config.dry_run is True,
        "trade dry_run changed after blocked execution command",
    )

    node.shutdown_event.set()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    event_types = [event.get("event_type") for event in node.crdt.events]
    assert_true("command_applied" in event_types, "trade PAUSE command_applied event missing")
    assert_true("command_blocked" in event_types, "trade blocked command event missing")


async def _check_retry_governance_smoke() -> dict[str, object]:
    """Run retry governance smoke on an isolated temporary CRDT database."""
    with tempfile.TemporaryDirectory(prefix="retry-governance-smoke-") as tmpdir:
        db_path = str(Path(tmpdir) / "crdt.db")

        result = await run_retry_governance_smoke(
            argparse.Namespace(
                db_path=db_path,
                source="retry-governance-smoke-runtime",
                proposal_id="replay-retry-runtime-smoke-proposal-1",
                approval_id="replay-retry-runtime-smoke-approval-1",
                plan_id="replay-retry-runtime-smoke-plan-1",
                result_id="replay-retry-runtime-smoke-result-1",
                timeout_profile="standard",
                decision_mode="manual",
                json=False,
            )
        )

    return {
        "name": "retry_governance_smoke",
        "status": result.get("status"),
        "passed": result.get("status") == "passed",
        "records_seeded": result.get("records_seeded"),
        "chain_complete": (
            result.get("trail_summary", {}).get("chain_complete")
            if isinstance(result.get("trail_summary"), dict)
            else False
        ),
        "observability": (
            result.get("observability", {}).get("status")
            if isinstance(result.get("observability"), dict)
            else "unknown"
        ),
    }

async def main() -> None:
    checks = [
        ("common runtime", check_common_runtime),
        ("base node command intake guard", check_base_node_command_intake_guard),
        ("command normalization", check_command_normalization),
        ("command action targets helpers", check_command_action_targets_helpers),
        ("normalize commands ordering and skip", check_normalize_commands_ordering_and_skip),
        ("command normalization idempotency", check_command_normalization_idempotency),
        ("command fingerprint canonical legacy parity", check_command_fingerprint_canonical_legacy_parity),
        ("canonical command normalization enrichment", check_canonical_command_normalization_enrichment),
        ("legacy command normalization audit", check_legacy_command_normalization_audit),
        ("lifecycle observability helpers", check_lifecycle_observability_helpers),
        ("command observability helpers", check_command_observability_helpers),
        ("overseer observability config metadata", check_overseer_observability_config_metadata),
        ("security dedup", check_security_dedup),
        ("security command semantic key normalized", check_security_command_semantic_key_normalized),
        ("explorer dedup", check_explorer_dedup),
        ("explorer command semantic key normalized", check_explorer_command_semantic_key_normalized),
        ("common lifecycle security/explorer", check_common_lifecycle_security_explorer),
        ("common lifecycle meta-agents", check_common_lifecycle_meta_agents),
        ("meta-agent pause guard", check_meta_agent_pause_guard),
        ("explorer pause guard", check_explorer_pause_guard),
        ("security pause guard", check_security_pause_guard),
        ("improver dry cycle", check_improver_dry_cycle),
        ("improver lifecycle pause/resume", check_improver_lifecycle_pause_resume),
        ("improver run once blocked without approval", check_improver_run_once_blocked_without_approval),
        ("improver run once approved dry cycle", check_improver_run_once_approved_dry_cycle),
        ("improver pause guard", check_improver_pause_guard),
        ("improver command normalization target action parity", check_improver_command_normalization_target_action_parity),
        ("overseer topology summary", check_overseer_topology_summary),
        ("overseer topology legacy command summary", check_overseer_topology_legacy_command_summary),
        ("overseer topology command events summary", check_overseer_topology_command_events_summary),
        ("overseer topology healthcheck", check_overseer_topology_healthcheck),
        ("overseer legacy command warnings payload", check_overseer_legacy_command_warnings_payload),
        ("overseer persisted legacy command warnings", check_overseer_persisted_legacy_command_warnings),
        ("overseer collector command events visibility", check_overseer_collector_command_events_visibility),
        ("overseer collector legacy command visibility", check_overseer_collector_legacy_command_visibility),
        ("overseer collector legacy command windowing", check_overseer_collector_legacy_command_windowing),
        ("policy legacy command window ignores old commands", check_policy_legacy_command_window_ignores_old_commands),
        ("overseer topology rules payload", check_overseer_topology_rules_payload),
        ("overseer topology warnings", check_overseer_topology_warnings),
        ("overseer topology command warnings", check_overseer_topology_command_warnings),
        ("policy command skipped threshold", check_policy_command_skipped_threshold),
        ("executor semantic fingerprint", check_executor_semantic_fingerprint),
        ("executor rate limit fingerprint behavior", check_executor_rate_limit_fingerprint_behavior),
        ("overseer collector command event windowing", check_overseer_collector_command_event_windowing),
        ("policy command friction window ignores old events", check_policy_command_friction_window_ignores_old_events),
        ("command friction default config", check_command_friction_default_config),
        ("overseer command friction advisory directives", check_overseer_command_friction_advisory_directives),
        ("overseer persisted topology command warnings", check_overseer_persisted_topology_command_warnings),
        ("overseer legacy command migration advisory directives", check_overseer_legacy_command_migration_advisory_directives),
        ("overseer topology restart candidates", check_overseer_topology_restart_candidates),
        ("overseer topology restarts default disabled", check_overseer_topology_restarts_default_disabled),
        ("overseer topology restarts enabled canonical only", check_overseer_topology_restarts_enabled_canonical_only),
        ("overseer executor gates", check_overseer_executor_gates),
        ("trade runtime command loop", _test_trade_runtime_command_loop),
        ("retry governance smoke", _check_retry_governance_smoke),
    ]

    for name, check in checks:
        await check()
        print(f"✅ {name}")

    print("✅ swarm runtime smoke OK")


if __name__ == "__main__":
    asyncio.run(main())