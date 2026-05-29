from typing import Any

import pytest

from src.swarms.trade.node_core.run_step import run_one_step


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


class DummyNode:
    def __init__(self) -> None:
        self._paused = False
        self.capital = 10_000.0
        self.market_collector = DummyMarketCollector()
        self.telemetry = DummyTelemetry()
        self._last_market = None
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

    async def _evaluate_survival_and_trade(self, market, symbol):
        self.calls.append(("trade", symbol, market))

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
    assert ("trade", "BTC/USDT", {"price": 100.0}) in node.calls
    assert "evolution" in node.calls
    assert "sync" in node.calls
    assert "pull_context" in node.calls
    assert node._last_market == {"price": 100.0}
    assert node.telemetry.impact_values == [10_000.0]


@pytest.mark.asyncio
async def test_run_one_step_skips_trade_when_paused() -> None:
    node = DummyNode()
    node._paused = True

    assert await run_one_step(node, session=None) is True

    assert not any(isinstance(call, tuple) and call[0] == "market_mode" for call in node.calls)
    assert not any(isinstance(call, tuple) and call[0] == "trade" for call in node.calls)


@pytest.mark.asyncio
async def test_run_one_step_stops_on_failure_shutdown() -> None:
    node = DummyNode()

    async def fail():
        return True

    node._maybe_trigger_failure_shutdown = fail

    assert await run_one_step(node, session=None) is False