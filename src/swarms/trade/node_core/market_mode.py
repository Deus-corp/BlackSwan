"""Trade node market-mode side effects."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger("SwarmNode")


async def handle_market_mode_logic(node: Any, best_symbol: str, best_market: Dict[str, Any]) -> None:
    """Run market-mode-specific side effects for the selected market."""
    if node.market_mode == "web3":
        await _handle_web3_market_mode(node, best_symbol)
        return

    if node.market_mode == "futures":
        await _handle_futures_market_mode(node, best_symbol, best_market)
        return


async def _handle_web3_market_mode(node: Any, best_symbol: str) -> None:
    adapter = node.market_adapter.get_adapter(best_symbol)
    if not adapter or not hasattr(adapter, "w3"):
        return

    try:
        block_number: int = await adapter.w3.eth.block_number
        if node.is_leader(block_number):
            await node.trading_controller.check_and_rebalance(adapter)
    except Exception as exc:
        logger.warning("Web3 rebalance check failed for %s: %s", best_symbol, exc, exc_info=True)


async def _handle_futures_market_mode(node: Any, best_symbol: str, best_market: Dict[str, Any]) -> None:
    adapter = node.market_adapter.get_adapter(best_symbol, "futures")
    if not adapter or not hasattr(adapter, "exchange") or not hasattr(adapter, "check_stop_loss"):
        return

    try:
        positions: List[Dict[str, Any]] = await adapter.exchange.fetch_positions([best_symbol])
        if not positions:
            return

        pos: Dict[str, Any] = positions[0]
        contracts_str: Any = pos.get("contracts", "0.0")
        contracts: float = float(contracts_str)

        if contracts == 0.0:
            return

        entry_price: float = float(pos.get("entryPrice", 0.0))
        current_price: float = float(best_market["price"])
        side: str = "long" if contracts > 0 else "short"

        if not adapter.check_stop_loss(entry_price, current_price, side):
            return

        logger.info("Stop-loss triggered for %s", best_symbol)
        await adapter.close_position(best_symbol)
        await node.telegram_notifier.send(
            f"🛑 <b>Stop-loss triggered</b>\n"
            f"Node: {node.node_id}\n"
            f"Symbol: {best_symbol}\n"
            f"Capital: {node.capital:.2f}"
        )

        if node.market_adapter.hedge_enabled:
            await _close_hedge_position(node, best_symbol)

    except Exception as exc:
        logger.warning("Futures stop-loss check failed for %s: %s", best_symbol, exc, exc_info=True)


async def _close_hedge_position(node: Any, best_symbol: str) -> None:
    spot_adapter = node.market_adapter.get_adapter(best_symbol, "spot")
    if not spot_adapter:
        return

    try:
        await spot_adapter.close_position(best_symbol)
        logger.info("Hedge position for %s closed.", best_symbol)
    except Exception as exc:
        logger.warning("Hedge position close failed for %s: %s", best_symbol, exc)


__all__ = ["handle_market_mode_logic"]