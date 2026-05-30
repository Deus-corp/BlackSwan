"""Trade node main-loop helper functions."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import aiohttp

from src.swarms.trade.market.snapshot import MarketSnapshot


async def collect_market_snapshot(node: Any, session: aiohttp.ClientSession) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    """Collect current market snapshot through the node's market collector."""
    return await node.market_collector.collect(session)


async def evaluate_survival_and_trade(
    node: Any,
    market: Dict[str, Any],
    symbol: str,
    snapshot: Any = None,
) -> Optional[Dict[str, Any]]:
    """Evaluate survival constraints and execute trade flow."""
    trade_flow = getattr(node, "trade_flow", None)
    if trade_flow is None:
        return None

    process = getattr(trade_flow, "process", None)
    if callable(process) and snapshot is not None:
        result = process(snapshot)
        if hasattr(result, "__await__"):
            return await result
        return result

    evaluate_and_execute = getattr(trade_flow, "evaluate_and_execute", None)
    if callable(evaluate_and_execute):
        result = evaluate_and_execute(market=market, symbol=symbol)
        if hasattr(result, "__await__"):
            return await result
        return result

    return None

async def tick_evolution(node: Any) -> None:
    """Run one evolution tick without re-entering the evolution cycle wrapper."""
    engine = getattr(node, "evolution_engine", None) or getattr(node, "engine", None)
    if engine is None:
        return

    step = getattr(engine, "step", None)
    if callable(step):
        result = step()
        if hasattr(result, "__await__"):
            await result
        return

    safe_step = getattr(engine, "_safe_genetic_step", None)
    if callable(safe_step):
        result = safe_step()
        if hasattr(result, "__await__"):
            await result

async def sync_swarm(node: Any) -> None:
    """Run one swarm synchronization tick without re-entering the sync cycle wrapper."""
    swarm_sync = getattr(node, "swarm_sync", None)
    if swarm_sync is None:
        return

    reconcile = getattr(swarm_sync, "reconcile", None)
    if callable(reconcile):
        result = reconcile()
        if hasattr(result, "__await__"):
            await result
        return

    sync = getattr(swarm_sync, "sync", None)
    if callable(sync):
        result = sync()
        if hasattr(result, "__await__"):
            await result
        return

    run = getattr(swarm_sync, "run", None)
    if callable(run):
        result = run()
        if hasattr(result, "__await__"):
            await result

async def periodic_tasks(node: Any, snapshot: MarketSnapshot) -> None:
    """Run periodic trade-node tasks after a market snapshot."""
    node.sync_context()

    heartbeat_publisher = getattr(node, "heartbeat_publisher", None)
    if heartbeat_publisher is not None:
        publish = getattr(heartbeat_publisher, "publish", None)
        if callable(publish):
            result = publish(snapshot)
            if hasattr(result, "__await__"):
                await result

    maintenance = (
        getattr(node, "maintenance", None)
        or getattr(node, "maintenance_service", None)
        or getattr(node, "maintenance_runner", None)
    )
    if maintenance is not None:
        run = getattr(maintenance, "run", None)
        if callable(run):
            result = run(snapshot)
            if hasattr(result, "__await__"):
                await result


__all__ = [
    "collect_market_snapshot",
    "evaluate_survival_and_trade",
    "periodic_tasks",
    "sync_swarm",
    "tick_evolution",
]