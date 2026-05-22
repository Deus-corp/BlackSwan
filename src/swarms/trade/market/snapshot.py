"""Market snapshot types and collection helpers for the trade swarm."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple, cast

import aiohttp

from ..context import RuntimeContext


@dataclass(slots=True)
class MarketSnapshot:
    """Normalized market view used by trading, evolution, and telemetry layers."""

    best_symbol: str
    best_market: Dict[str, Any]
    markets: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def price_for(self, symbol: Optional[str] = None) -> float:
        """Retrieve the price for a specific symbol or the best available symbol."""
        key = symbol or self.best_symbol
        market = self.markets.get(key, self.best_market if key == self.best_symbol else {})
        try:
            return float(market.get("price", 0.0))
        except (ValueError, TypeError):
            return 0.0


class MarketCollector:
    """Collects and normalizes market data for all configured symbols."""

    def __init__(self, ctx: RuntimeContext) -> None:
        self._ctx = ctx

    async def collect(self, session: aiohttp.ClientSession) -> MarketSnapshot:
        """Fetch and normalize market data from the service."""
        raw_snapshot = cast(Dict[str, Any], await self._ctx.market_service.get_snapshot(session))
        best_symbol, best_market = self._select_best_market(raw_snapshot)

        normalized = self._normalize_snapshot(raw_snapshot)
        if best_symbol not in normalized and best_market:
            normalized[best_symbol] = best_market

        return MarketSnapshot(
            best_symbol=best_symbol,
            best_market=best_market,
            markets=normalized,
        )

    @staticmethod
    def _select_best_market(snapshot: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Select the best market with a robust fallback mechanism."""
        try:
            from src.trading.market import select_best_market

            return select_best_market(snapshot)
        except (ImportError, Exception):
            # Deterministic fallback: choose the first non-empty market entry.
            for symbol, market in snapshot.items():
                if isinstance(market, dict) and market:
                    return str(symbol), market
            return "BTC/USDT", {"price": 0.0, "symbol": "BTC/USDT"}

    @staticmethod
    def _normalize_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Sanitize raw input to ensure a dict of dict structure."""
        return {
            str(symbol): dict(market)
            for symbol, market in snapshot.items()
            if isinstance(market, dict)
        }