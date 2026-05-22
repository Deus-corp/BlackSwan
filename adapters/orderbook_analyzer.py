# adapters/orderbook_analyzer.py
"""
Order Book Analyzer – calculates liquidity imbalance (pressure of buys/sells).
"""
import logging
from typing import Dict, Optional, Any, List, Tuple, Protocol

logger = logging.getLogger(__name__)

# Define a Protocol for the expected adapter structure
class ExchangeAdapter(Protocol):
    """
    Protocol for an adapter that exposes an 'exchange' object with an
    asynchronous 'fetch_order_book' method.
    
    Implementing classes should have a 'symbol' attribute (optional)
    and an 'exchange' attribute which itself conforms to the nested 'Exchange' Protocol.
    """
    symbol: Optional[str] # Adapters might have a default symbol
    
    class Exchange(Protocol):
        """
        Protocol for the exchange object within an ExchangeAdapter.
        It must provide an asynchronous method to fetch the order book.
        """
        async def fetch_order_book(self, symbol: str, limit: int) -> Dict[str, List[Tuple[float, float]]]:
            """
            Fetches the order book for a given symbol and limit.
            
            Args:
                symbol (str): The trading pair symbol.
                limit (int): The number of bids/asks to retrieve.
            
            Returns:
                Dict[str, List[Tuple[float, float]]]: A dictionary containing 'bids' and 'asks' lists.
                                                      Each bid/ask is a tuple of (price, volume).
            """
            ... # Ellipsis indicates an abstract method

    exchange: Exchange # The exchange attribute must conform to the nested Exchange Protocol

class OrderBookAnalyzer:
    """
    Order Book Analyzer – calculates liquidity imbalance (pressure of buys/sells).
    This class fetches order book data through the provided adapter
    and calculates liquidity metrics such as imbalance and delta volume.
    """
    def __init__(self, adapter: ExchangeAdapter) -> None:
        """
        Initializes the order book analyzer with the given adapter.
        
        Args:
            adapter (ExchangeAdapter): Object that must conform to the ExchangeAdapter protocol,
                                       i.e., have an 'exchange' attribute with an asynchronous
                                       'fetch_order_book(symbol, limit=depth)' method.
                                       For example, FuturesAdapter or BinanceTestnetAdapter.
        """
        self.adapter: ExchangeAdapter = adapter
        self.last_imbalance: Optional[float] = None
        self.last_delta_volume: Optional[float] = None

    async def update(self, symbol: Optional[str] = None, depth: int = 20) -> Optional[Dict[str, float]]:
        """
        Fetches the order book for the specified symbol and depth,
        then calculates and returns a dictionary with liquidity metrics.
        Updates internal states `last_imbalance` and `last_delta_volume`.

        Args:
            symbol (Optional[str]): Trading symbol (e.g., 'BTC/USDT'). If None, uses
                                    the symbol from the adapter (`self.adapter.symbol`).
            depth (int): Depth of the order book to fetch (number of bids and asks).
        
        Returns:
            Optional[Dict[str, float]]: Dictionary with metrics ("imbalance", "delta_volume",
                                        "total_bid_volume", "total_ask_volume")
                                        or None in case of error, missing symbol, or empty data.
        """
        # Determine the actual symbol to use. Prioritize provided symbol, then adapter's default.
        actual_symbol: Optional[str] = symbol or getattr(self.adapter, 'symbol', None)
        if actual_symbol is None:
            logger.error("Symbol not provided for OrderBookAnalyzer.update and adapter does not have a default 'symbol' attribute.")
            return None

        try:
            # Fetch the order book asynchronously using the adapter's exchange object.
            book: Dict[str, List[Tuple[float, float]]] = await self.adapter.exchange.fetch_order_book(actual_symbol, limit=depth)
            
            # Using .get() with a default empty list to prevent KeyError if 'bids' or 'asks' are missing
            bids: List[Tuple[float, float]] = book.get('bids', [])
            asks: List[Tuple[float, float]] = book.get('asks', [])

            # Calculate total volumes
            total_bid_volume: float = sum(b[1] for b in bids)
            total_ask_volume: float = sum(a[1] for a in asks)
            total_volume: float = total_bid_volume + total_ask_volume

            # Calculate imbalance and delta volume
            if total_volume > 0:
                imbalance: float = (total_bid_volume - total_ask_volume) / total_volume
            else:
                # If total_volume is 0, there's no liquidity, so imbalance is effectively neutral.
                imbalance = 0.0

            delta_volume: float = total_bid_volume - total_ask_volume

            # Store the latest metrics
            self.last_imbalance = imbalance
            self.last_delta_volume = delta_volume

            return {
                "imbalance": imbalance,
                "delta_volume": delta_volume,
                "total_bid_volume": total_bid_volume,
                "total_ask_volume": total_ask_volume,
            }
        except Exception as e:
            logger.error(f"OrderBook analysis for symbol {actual_symbol} failed: {e}", exc_info=True)
            return None

    def get_context_string(self) -> str:
        """
        Returns a formatted string describing the last calculated order book imbalance.
        This string can be used for LLM prompt substitution or logging.

        Returns:
            str: String with information about the imbalance and delta volume, or an empty string,
                 if the imbalance data has not been calculated yet or `last_delta_volume` is missing.
        """
        if self.last_imbalance is None or self.last_delta_volume is None:
            return ""
        
        # Determine the direction of pressure based on imbalance
        direction: str
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