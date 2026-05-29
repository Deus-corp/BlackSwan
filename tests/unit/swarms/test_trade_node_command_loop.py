import pytest

from src.swarms.trade.node_core.command_loop import run_command_loop


class DummyNode:
    def __init__(self) -> None:
        self.ran = False

    async def _command_loop_impl(self) -> None:
        self.ran = True


@pytest.mark.asyncio
async def test_run_command_loop_delegates_to_impl() -> None:
    node = DummyNode()

    await run_command_loop(node)

    assert node.ran is True