import pytest

from src.swarms.trade.node_core.market_mode import handle_market_mode_logic


class DummyEth:
    @property
    async def block_number(self):
        return 10


class DummyW3:
    def __init__(self) -> None:
        self.eth = DummyEth()


class DummyWeb3Adapter:
    def __init__(self) -> None:
        self.w3 = DummyW3()


class DummyTradingController:
    def __init__(self) -> None:
        self.calls = []

    async def check_and_rebalance(self, adapter):
        self.calls.append(adapter)


class DummyMarketAdapter:
    def __init__(self, adapter=None) -> None:
        self.adapter = adapter
        self.hedge_enabled = False

    def get_adapter(self, symbol, mode=None):
        return self.adapter


class DummyWeb3Node:
    def __init__(self) -> None:
        self.node_id = "trade-1"
        self.market_mode = "web3"
        self.web3_adapter = DummyWeb3Adapter()
        self.market_adapter = DummyMarketAdapter(self.web3_adapter)
        self.trading_controller = DummyTradingController()

    def is_leader(self, block_number: int) -> bool:
        return True


@pytest.mark.asyncio
async def test_handle_market_mode_logic_runs_web3_rebalance_for_leader() -> None:
    node = DummyWeb3Node()

    await handle_market_mode_logic(node, "ETH/USDC", {"price": 100.0})

    assert node.trading_controller.calls == [node.web3_adapter]


@pytest.mark.asyncio
async def test_handle_market_mode_logic_ignores_missing_web3_adapter() -> None:
    node = DummyWeb3Node()
    node.market_adapter = DummyMarketAdapter(None)

    await handle_market_mode_logic(node, "ETH/USDC", {"price": 100.0})

    assert node.trading_controller.calls == []