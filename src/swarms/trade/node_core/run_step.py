"""Trade node single-step runtime orchestration."""

from __future__ import annotations

from typing import Any

import aiohttp

from swarm_config import config


async def run_one_step(node: Any, session: aiohttp.ClientSession) -> bool:
    """Run one trade node step and return whether the main loop should continue."""
    if await node._maybe_trigger_failure_shutdown():
        return False

    if not node._apply_capital_burn_and_check_alive():
        return False

    best_symbol, best_market, all_markets = await node._collect_market_snapshot(session)

    snapshot = node.market_collector.to_snapshot(
        best_symbol=best_symbol,
        best_market=best_market,
        all_markets=all_markets,
    )

    if not node._paused:
        await node._handle_market_mode_logic(best_symbol, best_market)
        await node._evaluate_survival_and_trade(best_market, best_symbol)

    await node._tick_evolution()
    await node._sync_swarm()

    node.pull_context()
    node._last_market = best_market

    await node._periodic_tasks(snapshot)

    node.telemetry.update_impact(node.capital)
    alert_threshold: float = float(config.capital_alert_threshold)
    if node.capital < alert_threshold:
        await node.telemetry.low_capital_alert(node.capital, alert_threshold)

    return True


__all__ = ["run_one_step"]