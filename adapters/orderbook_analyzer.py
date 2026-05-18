# adapters/orderbook_analyzer.py
"""
Анализатор Order Book – вычисляет имбаланс ликвидности (давление покупок/продаж).
"""
import logging
from typing import Dict, Optional, Any # Added Any for adapter type hint

logger = logging.getLogger(__name__)

class OrderBookAnalyzer:
    """
    Анализатор Order Book – вычисляет имбаланс ликвидности (давление покупок/продаж).
    Этот класс запрашивает данные стакана через предоставленный адаптер
    и рассчитывает метрики ликвидности.
    """
    def __init__(self, adapter: Any):
        """
        Инициализирует анализатор стакана с заданным адаптером.
        :param adapter: Объект, который должен иметь атрибут 'exchange' с методом
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
                 или None в случае ошибки.
        """
        # The original logic assumes self.adapter.symbol exists if symbol is None.
        # This preserves the existing functionality and logic.
        sym: str = symbol or getattr(self.adapter, 'symbol', None)
        if sym is None:
            logger.error("Symbol not provided and adapter does not have a default 'symbol' attribute.")
            return None

        try:
            # Assuming fetch_order_book is an async operation because the 'update' method is async.
            book = await self.adapter.exchange.fetch_order_book(sym, limit=depth) # Added await
            bids = book['bids']
            asks = book['asks']

            total_bid_volume = sum(b[1] for b in bids)
            total_ask_volume = sum(a[1] for a in asks)
            total_volume = total_bid_volume + total_ask_volume

            if total_volume > 0:
                imbalance = (total_bid_volume - total_ask_volume) / total_volume
            else:
                imbalance = 0.0

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
            logger.error(f"OrderBook analysis for symbol {sym} failed: {e}")
            return None

    def get_context_string(self) -> str:
        """
        Возвращает форматированную строку, описывающую последний рассчитанный имбаланс стакана.
        Эта строка может быть использована для подстановки в промпт LLM.

        :return: Строка с информацией об имбалансе и дельте объема, или пустая строка,
                 если данные об имбалансе еще не были получены.
        """
        if self.last_imbalance is None:
            return ""
        direction = "buy pressure" if self.last_imbalance > 0.1 else (
            "sell pressure" if self.last_imbalance < -0.1 else "balanced"
        )
        return (
            f"Order book imbalance: {self.last_imbalance:.4f} ({direction}), "
            f"delta volume: {self.last_delta_volume:.2f}"
        )