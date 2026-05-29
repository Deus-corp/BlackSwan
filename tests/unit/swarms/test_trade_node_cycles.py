import pytest

from src.swarms.trade.node_core.cycles import (
    apply_meta_commands,
    evolution_cycle,
    sync_cycle,
)


class DummyNode:
    def __init__(self) -> None:
        self.calls = []

    async def _apply_meta_commands_impl(self) -> None:
        self.calls.append("meta")

    async def _evolution_cycle_impl(self) -> None:
        self.calls.append("evolution")

    async def _sync_cycle_impl(self) -> None:
        self.calls.append("sync")


@pytest.mark.asyncio
async def test_cycles_delegate_to_impl_methods() -> None:
    node = DummyNode()

    await apply_meta_commands(node)
    await evolution_cycle(node)
    await sync_cycle(node)

    assert node.calls == ["meta", "evolution", "sync"]