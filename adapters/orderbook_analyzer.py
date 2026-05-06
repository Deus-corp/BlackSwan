# adapters/orderbook_analyzer.py
"""
Анализатор Order Book – вычисляет имбаланс ликвидности (давление покупок/продаж).
"""
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class OrderBookAnalyzer:
    def __init__(self, adapter):
        """
        adapter – объект с методом exchange.fetch_order_book(symbol).
        Например, FuturesAdapter или BinanceTestnetAdapter.
        """
        self.adapter = adapter
        self.last_imbalance: Optional[float] = None
        self.last_delta_volume: Optional[float] = None

    async def update(self, symbol: str = None, depth: int = 20) -> Optional[Dict[str, float]]:
        """
        Запрашивает стакан и возвращает словарь с метриками.
        """
        sym = symbol or self.adapter.symbol
        try:
            book = self.adapter.exchange.fetch_order_book(sym, limit=depth)
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
            logger.error(f"OrderBook analysis failed: {e}")
            return None

    def get_context_string(self) -> str:
        """Возвращает строку для подстановки в промпт LLM."""
        if self.last_imbalance is None:
            return ""
        direction = "buy pressure" if self.last_imbalance > 0.1 else (
            "sell pressure" if self.last_imbalance < -0.1 else "balanced"
        )
        return (
            f"Order book imbalance: {self.last_imbalance:.4f} ({direction}), "
            f"delta volume: {self.last_delta_volume:.2f}"
        )