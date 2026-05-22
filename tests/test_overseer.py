"""Test templates for the overseer subsystem.

These are intentionally lightweight starting points. They can be expanded into a full
pytest suite with fixtures and integration tests once the module layout is wired in.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any, Dict

import pytest

from src.swarms.overseer.overseer_core.collector import StateCollector
from src.swarms.overseer.overseer_core.executor import ActionExecutor
from src.swarms.overseer.overseer_core.models import OverseerDecision, SwarmSnapshot
from src.swarms.overseer.overseer_core.policy import PolicyEngine


class FakeStateSource:
    def __init__(self, state: Dict[str, Any]) -> None:
        self._state = state

    @property
    def state(self) -> Dict[str, Any]:
        return self._state


class FakeSink:
    def __init__(self) -> None:
        self.genomes = []

    async def add_genome(self, genome: Dict[str, Any]) -> None:
        self.genomes.append(genome)


@pytest.fixture
def sample_state() -> Dict[str, Any]:
    now = 1_000_000.0
    return {
        "trade_a": {"type": "trade_heartbeat", "node_id": "trade-a", "timestamp": now, "capital": 1500, "dq": 0.31, "fitness": 0.4},
        "security_a": {"type": "security_heartbeat", "node_id": "sec-a", "timestamp": now, "blocked_ips": 60},
        "explorer_a": {"type": "explorer_heartbeat", "node_id": "exp-a", "timestamp": now, "status": "ok"},
        "finding_1": {"type": "explorer_finding", "timestamp": now},
        "vuln_1": {"type": "vulnerability_alert", "timestamp": now},
    }


@pytest.mark.asyncio
async def test_collector_builds_snapshot(sample_state: Dict[str, Any]) -> None:
    collector = StateCollector(FakeStateSource(sample_state))
    snapshot = collector.collect()

    assert snapshot.trade_nodes == 1
    assert snapshot.security_nodes == 1
    assert snapshot.explorer_nodes == 1
    assert snapshot.trade_capital == 1500
    assert snapshot.blocked_ips == 60


def test_policy_hard_rules_trigger_on_risk() -> None:
    policy = PolicyEngine()
    snapshot = SwarmSnapshot(
        trade_nodes=1,
        trade_capital=1500,
        trade_dq=0.31,
        trade_fitness=0.4,
        security_nodes=1,
        blocked_ips=60,
        explorer_nodes=1,
        recent_findings=0,
        recent_vulnerability_alerts=1,
        resources="CPU: 10%",
        stale_trade_nodes=[],
        stale_security_nodes=[],
        stale_explorer_nodes=[],
    )

    hard = policy.evaluate_hard_rules(snapshot)
    assert hard.reduce_risk is True
    assert hard.unblock_ips is True


def test_policy_merge_keeps_safety_over_llm() -> None:
    policy = PolicyEngine()
    hard = OverseerDecision(reduce_risk=True, continue_explorer=False)
    llm = {"reduce_risk": False, "continue_explorer": True, "increase_exploration": True}

    merged = policy.merge(hard, llm)
    assert merged.reduce_risk is True
    assert merged.continue_explorer is False
    assert merged.increase_exploration is True


@pytest.mark.asyncio
async def test_executor_deduplicates_identical_commands() -> None:
    sink = FakeSink()
    executor = ActionExecutor(sink)
    snapshot = SwarmSnapshot(
        trade_nodes=1,
        trade_capital=1000,
        trade_dq=0.5,
        trade_fitness=0.2,
        security_nodes=1,
        blocked_ips=0,
        explorer_nodes=1,
        recent_findings=0,
        recent_vulnerability_alerts=0,
        resources="CPU: 10%",
        stale_trade_nodes=[],
        stale_security_nodes=[],
        stale_explorer_nodes=[],
    )
    decision = OverseerDecision(reduce_risk=True)

    await executor.apply(snapshot, decision, now=1_000.0)
    await executor.apply(snapshot, decision, now=1_001.0)

    assert len(sink.genomes) == 1
