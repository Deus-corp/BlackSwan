from dataclasses import dataclass
from typing import Any

import pytest

from src.swarms.trade.node_core.run_step import (
    normalize_market_snapshot_result,
    run_one_step,
)


class DummyMarketCollector:
    def __init__(self) -> None:
        self.snapshots = []

    def to_snapshot(self, *, best_symbol, best_market, all_markets):
        snapshot = {
            "best_symbol": best_symbol,
            "best_market": best_market,
            "all_markets": all_markets,
        }
        self.snapshots.append(snapshot)
        return snapshot


class DummyTelemetry:
    def __init__(self) -> None:
        self.impact_values = []
        self.alerts = []

    def update_impact(self, capital):
        self.impact_values.append(capital)

    async def low_capital_alert(self, capital, threshold):
        self.alerts.append((capital, threshold))


class DummyConfig:
    capital_alert_threshold = 100.0


class DummyNode:
    def __init__(self) -> None:
        self._paused = False
        self.capital = 10_000.0
        self.config = DummyConfig()
        self.market_collector = DummyMarketCollector()
        self.telemetry = DummyTelemetry()
        self._last_market = None
        self.last_decision = None
        self.calls = []

    async def _maybe_trigger_failure_shutdown(self) -> bool:
        self.calls.append("failure_check")
        return False

    def _apply_capital_burn_and_check_alive(self) -> bool:
        self.calls.append("capital_check")
        return True

    async def _collect_market_snapshot(self, session: Any):
        self.calls.append("collect")
        return "BTC/USDT", {"price": 100.0}, {"BTC/USDT": {"price": 100.0}}

    async def _handle_market_mode_logic(self, best_symbol, best_market):
        self.calls.append(("market_mode", best_symbol, best_market))

    async def _evaluate_survival_and_trade(self, market, symbol, snapshot=None):
        self.calls.append(("trade", symbol, market, snapshot))
        return {"action": "HOLD"}

    async def _tick_evolution(self):
        self.calls.append("evolution")

    async def _sync_swarm(self):
        self.calls.append("sync")

    def pull_context(self):
        self.calls.append("pull_context")

    async def _periodic_tasks(self, snapshot):
        self.calls.append(("periodic", snapshot))


@pytest.mark.asyncio
async def test_run_one_step_executes_full_active_step() -> None:
    node = DummyNode()

    assert await run_one_step(node, session=None) is True

    assert "failure_check" in node.calls
    assert "capital_check" in node.calls
    assert "collect" in node.calls
    assert ("market_mode", "BTC/USDT", {"price": 100.0}) in node.calls
    assert any(
        isinstance(call, tuple)
        and call[0] == "trade"
        and call[1] == "BTC/USDT"
        and call[2] == {"price": 100.0}
        for call in node.calls
    )
    assert "evolution" in node.calls
    assert "sync" in node.calls
    assert "pull_context" in node.calls
    assert node._last_market == {"price": 100.0}
    assert node.last_decision == {"action": "HOLD"}
    assert node.telemetry.impact_values == [10_000.0]
    assert node.telemetry.alerts == []


@pytest.mark.asyncio
async def test_run_one_step_sends_low_capital_alert() -> None:
    node = DummyNode()
    node.capital = 50.0

    assert await run_one_step(node, session=None) is True

    assert node.telemetry.impact_values == [50.0]
    assert node.telemetry.alerts == [(50.0, 100.0)]


@pytest.mark.asyncio
async def test_run_one_step_skips_trade_when_paused() -> None:
    node = DummyNode()
    node._paused = True

    assert await run_one_step(node, session=None) is True

    assert "collect" in node.calls
    assert "failure_check" in node.calls
    assert "capital_check" in node.calls
    assert not any(isinstance(call, tuple) and call[0] == "market_mode" for call in node.calls)
    assert not any(isinstance(call, tuple) and call[0] == "trade" for call in node.calls)
    assert "evolution" in node.calls
    assert "sync" in node.calls
    assert "pull_context" in node.calls


@pytest.mark.asyncio
async def test_run_one_step_stops_on_failure_shutdown() -> None:
    node = DummyNode()

    async def fail():
        return True

    node._maybe_trigger_failure_shutdown = fail

    assert await run_one_step(node, session=None) is False


@dataclass
class DummyMarketSnapshot:
    best_symbol: str
    best_market: dict
    all_markets: dict


def test_normalize_market_snapshot_result_accepts_object() -> None:
    snapshot = DummyMarketSnapshot(
        best_symbol="ETH/USDC",
        best_market={"price": 2500.0},
        all_markets={"ETH/USDC": {"price": 2500.0}},
    )

    symbol, market, all_markets, original = normalize_market_snapshot_result(snapshot)

    assert symbol == "ETH/USDC"
    assert market == {"price": 2500.0}
    assert all_markets == {"ETH/USDC": {"price": 2500.0}}
    assert original is snapshot


def test_normalize_market_snapshot_result_accepts_legacy_tuple() -> None:
    result = (
        "BTC/USDT",
        {"price": 100.0},
        {"BTC/USDT": {"price": 100.0}},
    )

    symbol, market, all_markets, original = normalize_market_snapshot_result(result)

    assert symbol == "BTC/USDT"
    assert market == {"price": 100.0}
    assert all_markets == {"BTC/USDT": {"price": 100.0}}
    assert original is result