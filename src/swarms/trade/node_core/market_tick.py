"""Trade node market tick helper."""

from __future__ import annotations

from typing import Any, Dict

import aiohttp


async def get_market_tick(node: Any, session: aiohttp.ClientSession, symbol: str = "BTC/USDT") -> Dict[str, Any]:
    """Get one market tick for a symbol."""
    return await node._get_market_tick_impl(session, symbol)


__all__ = ["get_market_tick"]