import asyncio

from src.swarms.common.base.meta_agent import (
    BaseMetaAgentConfig,
    BaseSwarmMetaAgent,
)
from src.swarms.common.base.node import BaseNodeConfig, BaseSwarmNode
from src.swarms.common.contracts import SwarmCapability, SwarmPolicy
from src.swarms.common.protocols.heartbeats import normalize_heartbeat
from src.swarms.common.protocols.topology import (
    NETWORK_READ,
    PRODUCTION_FINANCIAL_WRITE,
    SAFE_LOCAL_EXECUTION,
    SYSTEM_DANGEROUS_STUB,
    TESTNET_EXTERNAL_WRITE,
    command_is_dangerous,
    command_requires_explicit_gate,
    command_risk_tier,
)


class _FakeCRDT:
    def __init__(self) -> None:
        self.state = {}
        self.records = []

    async def add_genome(self, record):
        self.records.append(record)
        return record

    def close(self) -> None:
        return None


class _TickNode(BaseSwarmNode):
    def __init__(self) -> None:
        super().__init__(
            node_config=BaseNodeConfig(
                swarm_type="explorer",
                node_id="explorer-node-test",
                tick_interval_seconds=0.01,
                enable_heartbeat_loop=False,
                enable_command_loop=False,
                enable_reconcile_loop=False,
                enable_health_loop=False,
                enable_maintenance_loop=False,
            ),
            crdt=_FakeCRDT(),
        )
        self.ticks = 0

    async def process_tick(self) -> None:
        self.ticks += 1


async def _run_paused_node_once() -> _TickNode:
    node = _TickNode()
    node._set_runtime_paused(True)

    async def stop_soon() -> None:
        await asyncio.sleep(0.03)
        node.shutdown_event.set()

    await asyncio.gather(node.main_loop(), stop_soon())
    return node


def test_base_node_pause_skips_process_tick() -> None:
    node = asyncio.run(_run_paused_node_once())

    assert node.ticks == 0
    assert node.health.paused is True
    assert node.health.status == "paused"
    assert node.health_snapshot()["paused"] is True


def test_base_meta_agent_pause_is_exposed_in_health_snapshot() -> None:
    agent = BaseSwarmMetaAgent(
        meta_config=BaseMetaAgentConfig(
            swarm_type="explorer",
            agent_id="explorer-meta-test",
            enable_heartbeat_loop=False,
            enable_command_gc_loop=False,
            enable_reconcile_loop=False,
            enable_health_loop=False,
            enable_maintenance_loop=False,
        ),
        crdt=_FakeCRDT(),
    )

    agent._set_runtime_paused(True)

    assert agent.is_paused() is True
    assert agent.health.paused is True
    assert agent.health_snapshot()["paused"] is True


def test_topology_command_risk_tiers_are_execution_aware() -> None:
    assert command_risk_tier("explorer", "EXPLORE_URLS") == NETWORK_READ
    assert command_risk_tier("trade", "ADJUST_SWARM") == TESTNET_EXTERNAL_WRITE
    assert command_risk_tier("overseer", "RELOAD_POLICY") == SAFE_LOCAL_EXECUTION
    assert command_risk_tier("security", "UNBLOCK_ALL") == SYSTEM_DANGEROUS_STUB
    assert command_risk_tier("unknown", "DO_ANYTHING") == SYSTEM_DANGEROUS_STUB


def test_topology_explicit_gate_preserves_advisory_semantics() -> None:
    assert command_requires_explicit_gate("explorer", "node", "EXPLORE_URLS") is False
    assert command_requires_explicit_gate("trade", "node", "ADJUST_SWARM") is False
    assert command_requires_explicit_gate("security", "node", "UNBLOCK_ALL") is False
    assert command_requires_explicit_gate("memory", "meta_agent", "REINDEX") is True
    assert command_requires_explicit_gate("unknown", "node", "DO_ANYTHING") is False


def test_topology_dangerous_commands_are_classified_separately_from_explicit_gate() -> None:
    assert command_is_dangerous("security", "UNBLOCK_ALL") is True
    assert command_is_dangerous("security", "RESTART_NODE") is True
    assert command_is_dangerous("explorer", "EXPLORE_URLS") is False
    assert command_is_dangerous("trade", "ADJUST_SWARM") is False
    assert command_is_dangerous("unknown", "DO_ANYTHING") is True


def test_legacy_memory_and_simulation_heartbeats_normalize_to_known_swarms() -> None:
    memory = normalize_heartbeat(
        {
            "type": "memory_heartbeat",
            "node_id": "memory-node-1",
            "status": "ok",
        }
    )
    simulation = normalize_heartbeat(
        {
            "type": "simulation_heartbeat",
            "node_id": "simulation-node-1",
            "status": "ok",
        }
    )
    improver = normalize_heartbeat(
        {
            "type": "improver_heartbeat",
            "node_id": "improver-node-1",
            "status": "ok",
        }
    )

    assert memory["swarm"] == "memory"
    assert simulation["swarm"] == "simulation"
    assert improver["swarm"] == "improver"


def test_swarm_policy_supports_execution_risk_tiers() -> None:
    safe_policy = SwarmPolicy()
    network_policy = SwarmPolicy(
        allow_network_read=True,
        allowed_risk_tiers=("safe_local_execution", "network_read"),
    )
    testnet_policy = SwarmPolicy(
        allow_testnet_external_write=True,
        allowed_risk_tiers=("safe_local_execution", "testnet_external_write"),
    )
    production_policy = SwarmPolicy(
        allow_production_financial_write=False,
        allowed_risk_tiers=("production_financial_write",),
        max_risk_level=5,
    )

    assert safe_policy.allows(
        SwarmCapability(
            name="local_compile",
            risk_tier="safe_local_execution",
        )
    )
    assert not safe_policy.allows(
        SwarmCapability(
            name="explore_url",
            risk_tier="network_read",
        )
    )
    assert network_policy.allows(
        SwarmCapability(
            name="explore_url",
            risk_tier="network_read",
        )
    )
    assert testnet_policy.allows(
        SwarmCapability(
            name="sepolia_swap",
            risk_tier="testnet_external_write",
        )
    )
    assert not production_policy.allows(
        SwarmCapability(
            name="mainnet_swap",
            risk_level=5,
            risk_tier=PRODUCTION_FINANCIAL_WRITE,
        )
    )