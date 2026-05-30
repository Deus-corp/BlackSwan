from typing import Any

import pytest

from src.swarms.trade.node_core.loop import (
    collect_market_snapshot,
    evaluate_survival_and_trade,
    periodic_tasks,
    sync_swarm,
    tick_evolution,
)


class DummyMarketCollector:
    async def collect(self, session: Any):
        return "BTC/USDT", {"price": 100.0}, {"BTC/USDT": {"price": 100.0}}


class DummyTradeFlow:
    async def evaluate_and_execute(self, *, market, symbol):
        return {"symbol": symbol, "market": market, "executed": False}


class DummyHeartbeatPublisher:
    def __init__(self) -> None:
        self.snapshots = []

    async def publish(self, snapshot):
        self.snapshots.append(snapshot)


class DummyMaintenance:
    def __init__(self) -> None:
        self.snapshots = []

    async def run(self, snapshot):
        self.snapshots.append(snapshot)


class DummyEvolutionEngine:
    def __init__(self) -> None:
        self.calls = 0

    async def _safe_genetic_step(self) -> None:
        self.calls += 1


class DummySwarmSync:
    def __init__(self) -> None:
        self.calls = 0

    async def reconcile(self) -> dict[str, Any]:
        self.calls += 1
        return {"pushed": False, "imported": 0}


class DummyNode:
    def __init__(self) -> None:
        self.market_collector = DummyMarketCollector()
        self.trade_flow = DummyTradeFlow()
        self.heartbeat_publisher = DummyHeartbeatPublisher()
        self.maintenance = DummyMaintenance()
        self.evolution_engine = DummyEvolutionEngine()
        self.swarm_sync = DummySwarmSync()
        self.context_synced = False

    def sync_context(self) -> None:
        self.context_synced = True

    async def _evolution_cycle(self) -> None:
        raise AssertionError("tick_evolution must not call _evolution_cycle")

    async def _sync_cycle(self) -> None:
        raise AssertionError("sync_swarm must not call _sync_cycle")

class DummyTradeFlowProcess:
    async def process(self, snapshot):
        return {"snapshot": snapshot, "executed": False, "via": "process"}
    

@pytest.mark.asyncio
async def test_collect_market_snapshot_delegates_to_collector() -> None:
    node = DummyNode()

    symbol, market, all_markets = await collect_market_snapshot(node, session=None)

    assert symbol == "BTC/USDT"
    assert market["price"] == 100.0
    assert "BTC/USDT" in all_markets


@pytest.mark.asyncio
async def test_evaluate_survival_and_trade_delegates_to_trade_flow() -> None:
    node = DummyNode()

    result = await evaluate_survival_and_trade(node, {"price": 100.0}, "BTC/USDT")

    assert result == {
        "symbol": "BTC/USDT",
        "market": {"price": 100.0},
        "executed": False,
    }


@pytest.mark.asyncio
async def test_tick_evolution_and_sync_swarm_delegate_without_cycle_recursion() -> None:
    node = DummyNode()

    await tick_evolution(node)
    await sync_swarm(node)

    assert node.evolution_engine.calls == 1
    assert node.swarm_sync.calls == 1


@pytest.mark.asyncio
async def test_periodic_tasks_runs_context_heartbeat_and_maintenance() -> None:
    node = DummyNode()
    snapshot = object()

    await periodic_tasks(node, snapshot)

    assert node.context_synced is True
    assert node.heartbeat_publisher.snapshots == [snapshot]
    assert node.maintenance.snapshots == [snapshot]

@pytest.mark.asyncio
async def test_evaluate_survival_and_trade_uses_process_when_snapshot_available() -> None:
    node = DummyNode()
    node.trade_flow = DummyTradeFlowProcess()
    snapshot = object()

    result = await evaluate_survival_and_trade(node, {"price": 100.0}, "BTC/USDT", snapshot=snapshot)

    assert result == {"snapshot": snapshot, "executed": False, "via": "process"}

@pytest.mark.asyncio
async def test_periodic_tasks_tolerates_missing_maintenance() -> None:
    node = DummyNode()
    delattr(node, "maintenance")
    snapshot = object()

    await periodic_tasks(node, snapshot)

    assert node.context_synced is True
    assert node.heartbeat_publisher.snapshots == [snapshot]