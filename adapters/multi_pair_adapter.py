# adapters/multi_pair_adapter.py
"""
MULTI‑PAIR ADAPTER – оборачивает несколько BinanceTestnetAdapter или Web3TestnetAdapter.
Позволяет одному узлу торговать на нескольких парах одновременно.
"""
import os
import logging
from typing import Dict, List, Optional

from adapters.live_market import BinanceTestnetAdapter
from adapters.futures_adapter import FuturesAdapter

logger = logging.getLogger(__name__)


class MultiPairAdapter:
    def __init__(self, symbols: List[str], market_mode: str = "sim"):
        self.symbols = symbols
        self.market_mode = market_mode
        self.adapters: Dict[str, BinanceTestnetAdapter] = {}

        for sym in symbols:
            if market_mode == "live":
                self.adapters[sym] = BinanceTestnetAdapter(symbol=sym)
            elif market_mode == "futures":
                self.adapters[sym] = FuturesAdapter(symbol=sym)
            elif market_mode == "web3":
                # заглушка
                self.adapters[sym] = BinanceTestnetAdapter(symbol=sym)
            else:  # sim
                self.adapters[sym] = BinanceTestnetAdapter(symbol=sym)

    async def fetch_all_tickers(self) -> Dict[str, dict]:
        """Возвращает словарь {symbol: ticker} для всех пар."""
        results = {}
        for sym, adapter in self.adapters.items():
            try:
                ticker = await adapter.get_ticker()
                results[sym] = ticker if ticker else {"price": 0.0}
            except Exception as e:
                logger.error(f"Failed to fetch ticker for {sym}: {e}")
                results[sym] = {"price": 0.0}
        return results

    def get_adapter(self, symbol: str) -> Optional[BinanceTestnetAdapter]:
        return self.adapters.get(symbol)

    def place_order(self, symbol: str, side: str, amount: float, price: Optional[float] = None) -> Dict:
        adapter = self.adapters.get(symbol)
        if not adapter:
            logger.warning(f"No adapter for {symbol}")
            return {"error": f"No adapter for {symbol}"}
        return adapter.place_order(side, amount, price)