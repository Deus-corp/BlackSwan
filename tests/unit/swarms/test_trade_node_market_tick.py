import pytest

from src.swarms.trade.node_core.market_tick import get_market_tick


class DummyNode:
    def __init__(self) -> None:
        self.calls = []

    async def _get_market_tick_impl(self, session, symbol: str = "BTC/USDT"):
        self.calls.append((session, symbol))
        return {"symbol": symbol, "price": 100.0}


@pytest.mark.asyncio
async def test_get_market_tick_delegates_to_impl() -> None:
    node = DummyNode()
    session = object()

    tick = await get_market_tick(node, session, "ETH/USDC")

    assert tick == {"symbol": "ETH/USDC", "price": 100.0}
    assert node.calls == [(session, "ETH/USDC")]