"""
Order Book Analyzer – calculates liquidity imbalance (pressure of buys/sells).
"""
import logging
from typing import Dict, Optional, List, Tuple, Protocol, TypedDict

logger = logging.getLogger(__name__)

class OrderBookMetrics(TypedDict):
    """Structured return for order book analysis metrics."""
    imbalance: float
    delta_volume: float
    total_bid_volume: float
    total_ask_volume: float

class ExchangeProtocol(Protocol):
    """
    Protocol for the exchange object within an ExchangeAdapter.
    """
    async def fetch_order_book(self, symbol: str, limit: int) -> Dict[str, List[Tuple[float, float]]]:
        ...

class ExchangeAdapter(Protocol):
    """
    Protocol for an adapter that exposes an 'exchange' object with an
    asynchronous 'fetch_order_book' method.
    """
    symbol: Optional[str]
    exchange: ExchangeProtocol

class OrderBookAnalyzer:
    """
    Order Book Analyzer – calculates liquidity imbalance (pressure of buys/sells).
    This class fetches order book data and calculates liquidity metrics.
    """
    def __init__(self, adapter: ExchangeAdapter) -> None:
        self.adapter = adapter
        self.last_imbalance: Optional[float] = None
        self.last_delta_volume: Optional[float] = None

    async def update(self, symbol: Optional[str] = None, depth: int = 20) -> Optional[OrderBookMetrics]:
        """
        Fetches the order book for the specified symbol and depth,
        then calculates liquidity metrics.
        """
        target_symbol = symbol or getattr(self.adapter, 'symbol', None)
        if not target_symbol:
            logger.error("Symbol not provided and adapter lacks default symbol.")
            return None

        try:
            book = await self.adapter.exchange.fetch_order_book(target_symbol, limit=depth)
            
            bids = book.get('bids', [])
            asks = book.get('asks', [])

            total_bid_volume = sum(b[1] for b in bids)
            total_ask_volume = sum(a[1] for a in asks)
            total_volume = total_bid_volume + total_ask_volume

            imbalance = (total_bid_volume - total_ask_volume) / total_volume if total_volume > 0 else 0.0
            delta_volume = total_bid_volume - total_ask_volume

            self.last_imbalance = imbalance
            self.last_delta_volume = delta_volume

            return {
                "imbalance": imbalance,
                "delta_volume": delta_volume,
                "total_bid_volume": total_bid_volume,
                "total_ask_volume": total_ask_volume,
            }
        except Exception as e:
            logger.error(f"OrderBook analysis for {target_symbol} failed: {e}", exc_info=True)
            return None

    def get_context_string(self) -> str:
        """
        Returns a formatted string describing the last calculated order book imbalance.
        """
        if self.last_imbalance is None or self.last_delta_volume is None:
            return ""
        
        if self.last_imbalance > 0.1:
            direction = "buy pressure"
        elif self.last_imbalance < -0.1:
            direction = "sell pressure"
        else:
            direction = "balanced"
            
        return (
            f"Order book imbalance: {self.last_imbalance:.4f} ({direction}), "
            f"delta volume: {self.last_delta_volume:.2f}"
        )