"""Trade node single-step runtime helper."""

from __future__ import annotations

from typing import Any, Dict, Tuple

import aiohttp


def normalize_market_snapshot_result(result: Any) -> Tuple[str, Dict[str, Any], Dict[str, Any], Any]:
    """Normalize market snapshot result.

    Supports both legacy tuple format:
        (best_symbol, best_market, all_markets)

    and MarketSnapshot-like objects with attributes.
    """
    if isinstance(result, tuple) and len(result) == 3:
        best_symbol, best_market, all_markets = result
        return str(best_symbol), dict(best_market or {}), dict(all_markets or {}), result

    best_symbol = (
        getattr(result, "best_symbol", None)
        or getattr(result, "symbol", None)
        or getattr(result, "selected_symbol", None)
        or "BTC/USDT"
    )

    best_market = (
        getattr(result, "best_market", None)
        or getattr(result, "market", None)
        or getattr(result, "selected_market", None)
        or {}
    )

    all_markets = (
        getattr(result, "all_markets", None)
        or getattr(result, "markets", None)
        or getattr(result, "market_data", None)
        or {}
    )

    if not isinstance(best_market, dict):
        to_dict = getattr(best_market, "to_dict", None)
        best_market = to_dict() if callable(to_dict) else {}

    if not isinstance(all_markets, dict):
        to_dict = getattr(all_markets, "to_dict", None)
        all_markets = to_dict() if callable(to_dict) else {}

    return str(best_symbol), dict(best_market), dict(all_markets), result


async def run_one_step(node: Any, session: aiohttp.ClientSession) -> bool:
    """Run one trade node main-loop step."""
    snapshot_result = await node._collect_market_snapshot(session)
    best_symbol, best_market, all_markets, snapshot = normalize_market_snapshot_result(snapshot_result)

    if bool(getattr(node, "_paused", False)):
        if await node._maybe_trigger_failure_shutdown():
            return False

        if not node._apply_capital_burn_and_check_alive():
            return False

        await node._tick_evolution()
        await node._sync_swarm()

        node.pull_context()
        node._last_market = best_market

        await node._periodic_tasks(snapshot)

        node.telemetry.update_impact(node.capital)
        alert_threshold = float(getattr(getattr(node, "config", None), "capital_alert_threshold", 0.0) or 0.0)
        if alert_threshold > 0 and node.capital < alert_threshold:
            await node.telemetry.low_capital_alert(node.capital, alert_threshold)

        return True

    await node._handle_market_mode_logic(best_symbol, best_market)

    if await node._maybe_trigger_failure_shutdown():
        return False

    if not node._apply_capital_burn_and_check_alive():
        return False

    decision = await node._evaluate_survival_and_trade(best_market, best_symbol, snapshot=snapshot)
    if decision is not None:
        node.last_decision = decision

    await node._tick_evolution()
    await node._sync_swarm()

    node.pull_context()
    node._last_market = best_market

    await node._periodic_tasks(snapshot)

    node.telemetry.update_impact(node.capital)
    alert_threshold = float(getattr(getattr(node, "config", None), "capital_alert_threshold", 0.0) or 0.0)
    if alert_threshold > 0 and node.capital < alert_threshold:
        await node.telemetry.low_capital_alert(node.capital, alert_threshold)

    return True


__all__ = ["normalize_market_snapshot_result", "run_one_step"]