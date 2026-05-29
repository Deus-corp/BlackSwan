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


class DummyNode:
    def __init__(self) -> None:
        self.market_collector = DummyMarketCollector()
        self.trade_flow = DummyTradeFlow()
        self.heartbeat_publisher = DummyHeartbeatPublisher()
        self.maintenance = DummyMaintenance()
        self.synced = False
        self.evolved = False
        self.context_synced = False

    def sync_context(self) -> None:
        self.context_synced = True

    async def _evolution_cycle(self) -> None:
        self.evolved = True

    async def _sync_cycle(self) -> None:
        self.synced = True


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
async def test_tick_evolution_and_sync_swarm_delegate() -> None:
    node = DummyNode()

    await tick_evolution(node)
    await sync_swarm(node)

    assert node.evolved is True
    assert node.synced is True


@pytest.mark.asyncio
async def test_periodic_tasks_runs_context_heartbeat_and_maintenance() -> None:
    node = DummyNode()
    snapshot = object()

    await periodic_tasks(node, snapshot)

    assert node.context_synced is True
    assert node.heartbeat_publisher.snapshots == [snapshot]
    assert node.maintenance.snapshots == [snapshot]