import asyncio
from types import SimpleNamespace

import pytest

from src.swarms.trade.execution.live_backend import LiveExecutionBackend
from src.swarms.trade.trading.flow import TradeFlowService


class FakeEth:
    @property
    async def block_number(self):
        return 123


class FakeW3:
    eth = FakeEth()


class FakeAdapter:
    w3 = FakeW3()

    def __init__(self):
        self.called = False

    async def place_order(self, **kwargs):
        self.called = True
        return {"status": "success", "tx_hash": "0xabc"}


class BrokenEth:
    @property
    async def block_number(self):
        raise RuntimeError("rpc down")


class BrokenW3:
    eth = BrokenEth()


class BrokenAdapter(FakeAdapter):
    w3 = BrokenW3()


@pytest.mark.asyncio
async def test_live_backend_does_not_execute_when_not_leader():
    adapter = FakeAdapter()
    backend = LiveExecutionBackend("node-a", adapter, lambda block: False)

    result = await backend.execute_order(
        symbol="WETH/USDC",
        side="buy",
        amount=0.001,
        price=2000.0,
        capital=1000.0,
    )

    assert result["success"] is False
    assert result["error"] == "not_leader"
    assert adapter.called is False


@pytest.mark.asyncio
async def test_live_backend_does_not_execute_when_leader_check_fails():
    adapter = BrokenAdapter()
    backend = LiveExecutionBackend("node-a", adapter, lambda block: True)

    result = await backend.execute_order(
        symbol="WETH/USDC",
        side="buy",
        amount=0.001,
        price=2000.0,
        capital=1000.0,
    )

    assert result["success"] is False
    assert result["error"] == "leader_check_failed"
    assert adapter.called is False


class FakePolicy:
    def __init__(self, ctx):
        pass

    def evaluate(self, snapshot):
        return SimpleNamespace(
            should_trade=True,
            reason="test",
            symbol="WETH/USDC",
            side="buy",
            price=2000.0,
        )


class FakeSizer:
    def __init__(self, ctx):
        pass

    def size(self, intent, snapshot):
        return 0.001


class FakeExecutor:
    def __init__(self):
        self.called = False

    async def execute_order(self, **kwargs):
        self.called = True
        return {"success": True, "status": "filled", "tx_hash": "0xabc", "new_capital": 1000.0}


class FakeTelemetry:
    def update_impact(self, capital):
        pass

    async def trade(self, **kwargs):
        pass


class FakeCapitalManager:
    def __init__(self):
        self.capital = 1000.0

    def apply_dq_delta(self, value):
        pass


@pytest.mark.asyncio
async def test_trade_flow_dry_run_does_not_call_executor(monkeypatch):
    import src.swarms.trade.trading.flow as flow_mod

    monkeypatch.setattr(flow_mod, "TradePolicy", FakePolicy)
    monkeypatch.setattr(flow_mod, "PositionSizer", FakeSizer)

    executor = FakeExecutor()
    ctx = SimpleNamespace(
        config=SimpleNamespace(
            execution_enabled=False,
            dry_run=True,
            market_mode="sim",
            hedge_ratio=0.0,
        ),
        executor=executor,
        capital=1000.0,
        capital_manager=FakeCapitalManager(),
        telemetry=FakeTelemetry(),
        step_count=1,
        trace_id="test-trace",
        market_adapter=None,
    )

    service = TradeFlowService(ctx)
    result = await service.process(snapshot={})

    assert result["status"] == "dry_run"
    assert result["dry_run"] is True
    assert executor.called is False
