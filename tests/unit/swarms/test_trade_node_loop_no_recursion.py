import pytest

from src.swarms.trade.node_core.loop import sync_swarm, tick_evolution


class DummyEvolutionEngine:
    def __init__(self) -> None:
        self.calls = 0

    async def step(self) -> None:
        self.calls += 1


class DummySwarmSync:
    def __init__(self) -> None:
        self.calls = 0

    async def sync(self) -> None:
        self.calls += 1


class DummyNode:
    def __init__(self) -> None:
        self.evolution_engine = DummyEvolutionEngine()
        self.swarm_sync = DummySwarmSync()

    async def _evolution_cycle(self) -> None:
        raise AssertionError("tick_evolution must not call _evolution_cycle")

    async def _sync_cycle(self) -> None:
        raise AssertionError("sync_swarm must not call _sync_cycle")


@pytest.mark.asyncio
async def test_tick_evolution_calls_engine_without_cycle_recursion() -> None:
    node = DummyNode()

    await tick_evolution(node)

    assert node.evolution_engine.calls == 1


@pytest.mark.asyncio
async def test_sync_swarm_calls_swarm_sync_without_cycle_recursion() -> None:
    node = DummyNode()

    await sync_swarm(node)

    assert node.swarm_sync.calls == 1