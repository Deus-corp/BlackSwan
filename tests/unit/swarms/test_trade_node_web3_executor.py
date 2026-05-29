import pytest

from src.swarms.trade.node_core.web3_executor import initialize_web3_executor


class DummyNode:
    def __init__(self) -> None:
        self.initialized = False

    async def _initialize_web3_executor_impl(self) -> None:
        self.initialized = True


@pytest.mark.asyncio
async def test_initialize_web3_executor_delegates_to_impl() -> None:
    node = DummyNode()

    await initialize_web3_executor(node)

    assert node.initialized is True