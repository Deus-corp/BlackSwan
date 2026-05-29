import asyncio

import pytest

from src.swarms.trade.node_core.step import (
    apply_capital_burn_and_check_alive,
    maybe_trigger_failure_shutdown,
)


class DummyCapitalManager:
    def __init__(self, capital: float) -> None:
        self.capital = capital

    def burn(self, amount: float = 1.0) -> None:
        self.capital = max(0.0, self.capital - amount)

    def is_alive(self) -> bool:
        return self.capital > 0.0


class DummyNode:
    def __init__(self) -> None:
        self.node_id = "trade-1"
        self.failure_prob = 0.0
        self.shutdown_event = asyncio.Event()
        self.burn_rate = 1.0
        self.capital = 10.0
        self.capital_mgr = DummyCapitalManager(10.0)


@pytest.mark.asyncio
async def test_maybe_trigger_failure_shutdown_ignores_zero_probability() -> None:
    node = DummyNode()

    assert await maybe_trigger_failure_shutdown(node) is False
    assert node.shutdown_event.is_set() is False


def test_apply_capital_burn_and_check_alive_keeps_alive() -> None:
    node = DummyNode()

    assert apply_capital_burn_and_check_alive(node) is True
    assert node.capital == 9.0
    assert node.shutdown_event.is_set() is False


def test_apply_capital_burn_and_check_alive_shutdown_when_depleted() -> None:
    node = DummyNode()
    node.capital_mgr = DummyCapitalManager(0.5)
    node.capital = 0.5
    node.burn_rate = 1.0

    assert apply_capital_burn_and_check_alive(node) is False
    assert node.capital == 0.0
    assert node.shutdown_event.is_set() is True