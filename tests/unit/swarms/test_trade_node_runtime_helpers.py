import asyncio

import pytest

from src.swarms.trade.node_core.runtime import graceful_shutdown, run_main_loop, shutdown_watcher


class DummyMemoryAPI:
    def __init__(self) -> None:
        self.loaded = False

    async def load_from_db(self) -> None:
        self.loaded = True


class DummyNode:
    def __init__(self) -> None:
        self.node_id = "trade-1"
        self.memory_api_enabled = True
        self.memory_api = DummyMemoryAPI()
        self.shutdown_event = asyncio.Event()
        self.steps = 0
        self.shutdown_called = False

    async def _run_one_step(self, session) -> bool:
        self.steps += 1
        self.shutdown_event.set()
        return True

    async def _graceful_shutdown(self) -> None:
        self.shutdown_called = True


@pytest.mark.asyncio
async def test_run_main_loop_loads_memory_and_runs_step() -> None:
    node = DummyNode()

    await run_main_loop(node)

    assert node.memory_api.loaded is True
    assert node.steps == 1


@pytest.mark.asyncio
async def test_shutdown_watcher_waits_and_runs_graceful_shutdown() -> None:
    node = DummyNode()
    node.shutdown_event.set()

    await shutdown_watcher(node)

    assert node.shutdown_called is True

@pytest.mark.asyncio
async def test_graceful_shutdown_delegates_to_impl() -> None:
    node = DummyNode()

    async def impl() -> None:
        node.shutdown_called = True

    node._graceful_shutdown_impl = impl

    await graceful_shutdown(node)

    assert node.shutdown_called is True