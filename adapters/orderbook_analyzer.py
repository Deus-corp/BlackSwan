"""Order book analyzer for liquidity imbalance and spread/depth context."""

from __future__ import annotations

import logging
import math
import time
from typing import Any, Optional, Protocol, TypedDict

logger = logging.getLogger(__name__)


class OrderBookMetrics(TypedDict):
    """Structured order book analysis metrics."""

    imbalance: float
    delta_volume: float
    total_bid_volume: float
    total_ask_volume: float
    best_bid: float
    best_ask: float
    mid_price: float
    spread: float
    spread_bps: float
    depth: int
    symbol: str
    timestamp: float


class ExchangeProtocol(Protocol):
    """Exchange object exposing async order book fetch."""

    async def fetch_order_book(self, symbol: str, limit: int) -> dict[str, list[list[float] | tuple[float, float]]]:
        ...


class ExchangeAdapter(Protocol):
    """Adapter exposing an exchange and optional default symbol."""

    symbol: Optional[str]
    exchange: ExchangeProtocol


class OrderBookAnalyzer:
    """Analyze order book depth and calculate liquidity pressure metrics."""

    def __init__(self, adapter: ExchangeAdapter) -> None:
        self.adapter = adapter
        self.last_imbalance: Optional[float] = None
        self.last_delta_volume: Optional[float] = None
        self.last_metrics: Optional[OrderBookMetrics] = None

    async def update(self, symbol: Optional[str] = None, depth: int = 20) -> Optional[OrderBookMetrics]:
        """Fetch order book and update last liquidity metrics."""
        target_symbol = str(symbol or getattr(self.adapter, "symbol", "") or "").strip()
        if not target_symbol:
            logger.error("Symbol not provided and adapter has no default symbol.")
            return None

        safe_depth = max(1, int(depth))

        try:
            exchange = getattr(self.adapter, "exchange", None)
            fetch_order_book = getattr(exchange, "fetch_order_book", None)
            if not callable(fetch_order_book):
                logger.error("Adapter exchange does not expose fetch_order_book().")
                return None

            book = await fetch_order_book(target_symbol, limit=safe_depth)
            metrics = self.analyze_book(book, symbol=target_symbol, depth=safe_depth)

            self.last_imbalance = metrics["imbalance"]
            self.last_delta_volume = metrics["delta_volume"]
            self.last_metrics = metrics

            return metrics

        except Exception:
            logger.exception("Order book analysis failed for %s.", target_symbol)
            return None

    def get_context_string(self) -> str:
        """Return compact natural-language context for latest order book metrics."""
        if self.last_metrics is None:
            return ""

        imbalance = self.last_metrics["imbalance"]
        delta_volume = self.last_metrics["delta_volume"]
        spread_bps = self.last_metrics["spread_bps"]

        if imbalance > 0.1:
            direction = "buy pressure"
        elif imbalance < -0.1:
            direction = "sell pressure"
        else:
            direction = "balanced"

        return (
            f"Order book imbalance: {imbalance:.4f} ({direction}), "
            f"delta volume: {delta_volume:.2f}, spread: {spread_bps:.2f} bps"
        )

    @classmethod
    def analyze_book(cls, book: dict[str, Any], *, symbol: str, depth: int = 20) -> OrderBookMetrics:
        """Analyze a raw order book dict without fetching."""
        if not isinstance(book, dict):
            raise TypeError("book must be a dictionary")

        bids = cls._normalize_levels(book.get("bids", []), limit=depth)
        asks = cls._normalize_levels(book.get("asks", []), limit=depth)

        total_bid_volume = sum(size for _, size in bids)
        total_ask_volume = sum(size for _, size in asks)
        total_volume = total_bid_volume + total_ask_volume

        imbalance = (total_bid_volume - total_ask_volume) / total_volume if total_volume > 0 else 0.0
        delta_volume = total_bid_volume - total_ask_volume

        best_bid = bids[0][0] if bids else 0.0
        best_ask = asks[0][0] if asks else 0.0
        mid_price = (best_bid + best_ask) / 2.0 if best_bid > 0 and best_ask > 0 else max(best_bid, best_ask)
        spread = max(0.0, best_ask - best_bid) if best_bid > 0 and best_ask > 0 else 0.0
        spread_bps = (spread / mid_price * 10_000.0) if mid_price > 0 else 0.0

        return {
            "imbalance": imbalance,
            "delta_volume": delta_volume,
            "total_bid_volume": total_bid_volume,
            "total_ask_volume": total_ask_volume,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "mid_price": mid_price,
            "spread": spread,
            "spread_bps": spread_bps,
            "depth": min(depth, max(len(bids), len(asks))),
            "symbol": str(symbol or "").strip(),
            "timestamp": time.time(),
        }

    @staticmethod
    def _normalize_levels(levels: Any, *, limit: int) -> list[tuple[float, float]]:
        if not isinstance(levels, list):
            return []

        normalized: list[tuple[float, float]] = []

        for level in levels[: max(1, limit)]:
            if not isinstance(level, (list, tuple)) or len(level) < 2:
                continue

            price = OrderBookAnalyzer._safe_float(level[0], 0.0)
            size = OrderBookAnalyzer._safe_float(level[1], 0.0)

            if price > 0 and size > 0:
                normalized.append((price, size))

        return normalized

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return number if math.isfinite(number) else default