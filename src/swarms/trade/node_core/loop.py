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
) -> Optional[Dict[str, Any]]:
    """Evaluate survival constraints and execute trade flow."""
    return await node.trade_flow.evaluate_and_execute(market=market, symbol=symbol)


async def tick_evolution(node: Any) -> None:
    """Run one evolution tick."""
    await node._evolution_cycle()


async def sync_swarm(node: Any) -> None:
    """Run one swarm synchronization tick."""
    await node._sync_cycle()


async def periodic_tasks(node: Any, snapshot: MarketSnapshot) -> None:
    """Run periodic trade-node tasks after a market snapshot."""
    node.sync_context()
    await node.heartbeat_publisher.publish(snapshot)
    await node.maintenance.run(snapshot)


__all__ = [
    "collect_market_snapshot",
    "evaluate_survival_and_trade",
    "periodic_tasks",
    "sync_swarm",
    "tick_evolution",
]