import asyncio

import pytest

from src.swarms.trade.node_core.runtime import (
    graceful_shutdown,
    run_main_loop,
    run_node_start,
    shutdown_watcher,
    register_signal_handlers,
)

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
        self.started = False
        self.registered_loop = None

    async def _run_one_step(self, session) -> bool:
        self.steps += 1
        self.shutdown_event.set()
        return True

    async def _graceful_shutdown(self) -> None:
        self.shutdown_called = True

    async def _start_impl(self) -> None:
        self.started = True

    def _register_signal_handlers_impl(self, loop) -> None:
        self.registered_loop = loop


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

@pytest.mark.asyncio
async def test_run_node_start_delegates_to_impl() -> None:
    node = DummyNode()

    await run_node_start(node)

    assert node.started is True

def test_register_signal_handlers_delegates_to_impl() -> None:
    node = DummyNode()
    loop = object()

    register_signal_handlers(node, loop)

    assert node.registered_loop is loop