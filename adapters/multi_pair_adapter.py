# adapters/multi_pair_adapter.py
import os
import logging
from typing import Dict, List, Optional
from adapters.live_market import BinanceTestnetAdapter
from adapters.futures_adapter import FuturesAdapter
from adapters.web3_testnet import Web3TestnetAdapter

logger = logging.getLogger(__name__)

PRICE_SCALE = float(os.environ.get("PRICE_SCALE", 10000))

class MultiPairAdapter:
    def __init__(self, symbols: List[str], market_mode: str = "sim"):
        self.symbols = symbols
        self.market_mode = market_mode
        self.hedge_enabled = os.environ.get("HEDGE_ENABLED", "false").lower() == "true"
        self.adapters: Dict[str, any] = {}

        for sym in symbols:
            if market_mode == "live":
                self.adapters[f"{sym}_spot"] = BinanceTestnetAdapter(symbol=sym)
            elif market_mode == "futures":
                self.adapters[f"{sym}_futures"] = FuturesAdapter(symbol=sym)
                if self.hedge_enabled:
                    self.adapters[f"{sym}_spot"] = BinanceTestnetAdapter(symbol=sym)
            elif market_mode == "web3":
                self.adapters[f"{sym}_spot"] = Web3TestnetAdapter(symbol=sym)
            else:  # sim
                self.adapters[f"{sym}_spot"] = BinanceTestnetAdapter(symbol=sym)

    def get_adapter(self, symbol: str, account: str = "spot") -> Optional[any]:
        """Получить адаптер по символу и типу счёта ('spot' или 'futures')."""
        key = f"{symbol}_{account}"
        return self.adapters.get(key)

    async def fetch_all_tickers(self):
        """Асинхронно получает тикеры для всех адаптеров и нормализует цену."""
        results = {}
        for key, adapter in self.adapters.items():
            sym = key.split("_")[0]  # извлекаем символ из ключа
            try:
                ticker = await adapter.get_ticker()
                if ticker:
                    # Нормализация цены для всех режимов, кроме sim
                    if self.market_mode != "sim":
                        raw_price = ticker.get("price", ticker.get("ask", 50000))
                        ticker["price"] = raw_price / PRICE_SCALE
                    results[sym] = ticker
            except Exception as e:
                logger.error(f"Failed to fetch ticker for {key}: {e}")
        return results