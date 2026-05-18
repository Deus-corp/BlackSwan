# adapters/multi_pair_adapter.py
import os
import logging
from typing import Dict, List, Optional, Any, Union
from adapters.live_market import BinanceTestnetAdapter
from adapters.futures_adapter import FuturesAdapter
from adapters.web3_testnet import Web3TestnetAdapter

logger = logging.getLogger(__name__)

# Price scaling factor, typically used for normalization in specific strategies
PRICE_SCALE: float = float(os.environ.get("PRICE_SCALE", 10000.0))

class MultiPairAdapter:
    """
    Manages multiple market adapters for various trading pairs and market modes
    (live spot, futures, web3, or simulation).
    Provides a unified interface to fetch tickers and retrieve specific adapters.
    """

    def __init__(self, symbols: List[str], market_mode: str = "sim", crdt_adapter: Optional[Any] = None):
        """
        Initializes the MultiPairAdapter with a list of symbols and a market mode.

        Args:
            symbols (List[str]): A list of trading pair symbols (e.g., ["BTC/USDT", "ETH/USDT"]).
            market_mode (str): The operating mode. Can be "live", "futures", "web3", or "sim".
            crdt_adapter (Optional[Any]): An optional CRDT adapter instance, specifically for "web3" mode.
        """
        self.symbols: List[str] = symbols
        self.market_mode: str = market_mode
        self.hedge_enabled: bool = os.environ.get("HEDGE_ENABLED", "false").lower() == "true"
        self.adapters: Dict[str, Union[BinanceTestnetAdapter, FuturesAdapter, Web3TestnetAdapter]] = {}

        for sym in symbols:
            if market_mode == "live":
                self.adapters[f"{sym}_spot"] = BinanceTestnetAdapter(symbol=sym)
            elif market_mode == "futures":
                self.adapters[f"{sym}_futures"] = FuturesAdapter(symbol=sym)
                if self.hedge_enabled:
                    # If hedging is enabled for futures, a spot adapter might also be needed
                    self.adapters[f"{sym}_spot"] = BinanceTestnetAdapter(symbol=sym)
            elif market_mode == "web3":
                # For web3 mode, the Web3TestnetAdapter requires the CRDT adapter
                self.adapters[f"{sym}_spot"] = Web3TestnetAdapter(symbol=sym, crdt_adapter=crdt_adapter)
            else:  # "sim" mode as default
                # In simulation mode, often a BinanceTestnetAdapter is used for price feeds
                self.adapters[f"{sym}_spot"] = BinanceTestnetAdapter(symbol=sym)

    def get_adapter(self, symbol: str, account: str = "spot") -> Optional[Union[BinanceTestnetAdapter, FuturesAdapter, Web3TestnetAdapter]]:
        """
        Retrieves a specific market adapter by symbol and account type.

        Args:
            symbol (str): The trading pair symbol.
            account (str): The type of account ('spot' or 'futures').

        Returns:
            Optional[Union[BinanceTestnetAdapter, FuturesAdapter, Web3TestnetAdapter]]:
            The requested adapter instance, or None if not found.
        """
        key: str = f"{symbol}_{account}"
        return self.adapters.get(key)

    async def fetch_all_tickers(self) -> Dict[str, Dict[str, Union[float, str, int]]]:
        """
        Asynchronously fetches ticker information for all managed adapters and normalizes prices.

        Returns:
            Dict[str, Dict[str, Union[float, str, int]]]: A dictionary where keys are symbols
            and values are their normalized ticker information (price, bid, ask, symbol, timestamp).
            Prices are normalized by PRICE_SCALE for non-simulation modes.
        """
        results: Dict[str, Dict[str, Union[float, str, int]]] = {}
        for key, adapter in self.adapters.items():
            sym: str = key.split("_")[0]  # Extract symbol from the adapter key
            try:
                ticker: Optional[Dict[str, Union[float, str, int]]] = await adapter.get_ticker()
                if ticker:
                    # Normalize price for all modes except "sim"
                    if self.market_mode != "sim":
                        # Ensure 'price' exists, fallback to 'ask' or a default if necessary
                        raw_price: float = float(ticker.get("price", ticker.get("ask", 50000.0)))
                        ticker["price"] = raw_price / PRICE_SCALE
                        # It's good practice to normalize bid/ask too if 'price' is normalized
                        if "bid" in ticker:
                            ticker["bid"] = float(ticker["bid"]) / PRICE_SCALE
                        if "ask" in ticker:
                            ticker["ask"] = float(ticker["ask"]) / PRICE_SCALE
                    results[sym] = ticker
            except Exception as e:
                logger.exception(f"Failed to fetch ticker for adapter '{key}'. Error: {e}")
        return results
