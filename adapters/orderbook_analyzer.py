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
    """
    symbol: Optional[str] # Adapters might have a default symbol
    
    class Exchange(Protocol):
        async def fetch_order_book(self, symbol: str, limit: int) -> Dict[str, List[Tuple[float, float]]]:
            ...
    
    exchange: Exchange

class OrderBookAnalyzer:
    """
    Анализатор Order Book – вычисляет имбаланс ликвидности (давление покупок/продаж).
    Этот класс запрашивает данные стакана через предоставленный адаптер
    и рассчитывает метрики ликвидности.
    """
    def __init__(self, adapter: ExchangeAdapter):
        """
        Инициализирует анализатор стакана с заданным адаптером.
        
        :param adapter: Объект, который должен соответствовать протоколу ExchangeAdapter,
                        т.е. иметь атрибут 'exchange' с асинхронным методом
                        'fetch_order_book(symbol, limit=depth)'.
                        Например, FuturesAdapter или BinanceTestnetAdapter.
        """
        self.adapter = adapter
        self.last_imbalance: Optional[float] = None
        self.last_delta_volume: Optional[float] = None

    async def update(self, symbol: Optional[str] = None, depth: int = 20) -> Optional[Dict[str, float]]:
        """
        Запрашивает стакан (order book) для указанного символа и глубины,
        затем вычисляет и возвращает словарь с метриками ликвидности.
        Обновляет внутренние состояния `last_imbalance` и `last_delta_volume`.

        :param symbol: Торговый символ (например, 'BTC/USDT'). Если None, используется
                       символ из адаптера (`self.adapter.symbol`).
        :param depth: Глубина стакана для запроса (количество бидов и асков).
        :return: Словарь с метриками ("imbalance", "delta_volume", "total_bid_volume", "total_ask_volume")
                 или None в случае ошибки или отсутствия символа.
        """
        # The original logic assumes self.adapter.symbol exists if symbol is None.
        # This preserves the existing functionality and logic.
        actual_symbol: str = symbol or getattr(self.adapter, 'symbol', None)
        if actual_symbol is None:
            logger.error("Symbol not provided and adapter does not have a default 'symbol' attribute.")
            return None

        try:
            # Assuming fetch_order_book is an async operation because the 'update' method is async.
            book: Dict[str, List[Tuple[float, float]]] = await self.adapter.exchange.fetch_order_book(actual_symbol, limit=depth)
            
            # Using .get() with a default empty list to prevent KeyError if 'bids' or 'asks' are missing
            bids: List[Tuple[float, float]] = book.get('bids', [])
            asks: List[Tuple[float, float]] = book.get('asks', [])

            total_bid_volume: float = sum(b[1] for b in bids)
            total_ask_volume: float = sum(a[1] for a in asks)
            total_volume: float = total_bid_volume + total_ask_volume

            if total_volume > 0:
                imbalance: float = (total_bid_volume - total_ask_volume) / total_volume
            else:
                imbalance = 0.0

            delta_volume: float = total_bid_volume - total_ask_volume

            self.last_imbalance = imbalance
            self.last_delta_volume = delta_volume

            return {
                "imbalance": imbalance,
                "delta_volume": delta_volume,
                "total_bid_volume": total_bid_volume,
                "total_ask_volume": total_ask_volume,
            }
        except Exception as e:
            logger.error(f"OrderBook analysis for symbol {actual_symbol} failed: {e}")
            return None

    def get_context_string(self) -> str:
        """
        Возвращает форматированную строку, описывающую последний рассчитанный имбаланс стакана.
        Эта строка может быть использована для подстановки в промпт LLM.

        :return: Строка с информацией об имбалансе и дельте объема, или пустая строка,
                 если данные об имбалансе еще не были получены или `last_delta_volume` отсутствует.
        """
        if self.last_imbalance is None or self.last_delta_volume is None:
            return ""
        direction: str = "buy pressure" if self.last_imbalance > 0.1 else (
            "sell pressure" if self.last_imbalance < -0.1 else "balanced"
        )
        return (
            f"Order book imbalance: {self.last_imbalance:.4f} ({direction}), "
            f"delta volume: {self.last_delta_volume:.2f}"
        )