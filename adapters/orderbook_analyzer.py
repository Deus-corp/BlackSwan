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
    Analyzes order book depth to calculate liquidity imbalance metrics.
    
    Attributes:
        adapter: The exchange adapter instance providing access to order book data.
        last_imbalance: The most recently calculated imbalance ratio.
        last_delta_volume: The most recently calculated net volume delta.
    """
    def __init__(self, adapter: ExchangeAdapter) -> None:
        self.adapter = adapter
        self.last_imbalance: Optional[float] = None
        self.last_delta_volume: Optional[float] = None

    async def update(self, symbol: Optional[str] = None, depth: int = 20) -> Optional[OrderBookMetrics]:
        """
        Fetches order book data for the symbol and calculates liquidity metrics.

        Args:
            symbol: The ticker symbol to analyze. Defaults to the adapter's symbol.
            depth: Number of levels to include from the order book.

        Returns:
            OrderBookMetrics dictionary if analysis is successful, otherwise None.
        """
        target_symbol = symbol or getattr(self.adapter, 'symbol', None)
        if not target_symbol:
            logger.error("Symbol not provided and adapter lacks default symbol.")
            return None

        try:
            book = await self.adapter.exchange.fetch_order_book(target_symbol, limit=depth)
            
            bids: List[Tuple[float, float]] = book.get('bids', [])
            asks: List[Tuple[float, float]] = book.get('asks', [])

            total_bid_volume = sum(level[1] for level in bids)
            total_ask_volume = sum(level[1] for level in asks)
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
        Returns a descriptive string for the last calculated order book imbalance.

        Returns:
            A formatted summary string or an empty string if no data is available.
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