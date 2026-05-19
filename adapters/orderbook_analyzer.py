# adapters/orderbook_analyzer.py
"""
Анализатор Order Book – вычисляет имбаланс ликвидности (давление покупок/продаж).
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
    Анализатор Order Book – вычисляет имбаланс ликвидности (давление покупок/продаж).
    Этот класс запрашивает данные стакана через предоставленный адаптер
    и рассчитывает метрики ликвидности, такие как имбаланс и дельта объема.
    """
    def __init__(self, adapter: ExchangeAdapter) -> None:
        """
        Инициализирует анализатор стакана с заданным адаптером.
        
        Args:
            adapter (ExchangeAdapter): Объект, который должен соответствовать протоколу ExchangeAdapter,
                                       т.е. иметь атрибут 'exchange' с асинхронным методом
                                       'fetch_order_book(symbol, limit=depth)'.
                                       Например, FuturesAdapter или BinanceTestnetAdapter.
        """
        self.adapter: ExchangeAdapter = adapter
        self.last_imbalance: Optional[float] = None
        self.last_delta_volume: Optional[float] = None

    async def update(self, symbol: Optional[str] = None, depth: int = 20) -> Optional[Dict[str, float]]:
        """
        Запрашивает стакан (order book) для указанного символа и глубины,
        затем вычисляет и возвращает словарь с метриками ликвидности.
        Обновляет внутренние состояния `last_imbalance` и `last_delta_volume`.

        Args:
            symbol (Optional[str]): Торговый символ (например, 'BTC/USDT'). Если None, используется
                                    символ из адаптера (`self.adapter.symbol`).
            depth (int): Глубина стакана для запроса (количество бидов и асков).
        
        Returns:
            Optional[Dict[str, float]]: Словарь с метриками ("imbalance", "delta_volume",
                                        "total_bid_volume", "total_ask_volume")
                                        или None в случае ошибки, отсутствия символа или пустых данных.
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
        Возвращает форматированную строку, описывающую последний рассчитанный имбаланс стакана.
        Эта строка может быть использована для подстановки в промпт LLM или для логирования.

        Returns:
            str: Строка с информацией об имбалансе и дельте объема, или пустая строка,
                 если данные об имбалансе еще не были получены или `last_delta_volume` отсутствует.
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
