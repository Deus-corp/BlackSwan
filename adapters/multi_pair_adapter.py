# adapters/multi_pair_adapter.py
import os
import logging
from typing import Dict, List, Optional, Any, Union

# Assuming these adapters exist and their types are as named
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

    Provides a unified interface to fetch tickers and retrieve specific adapters
    based on symbol and account type. It supports dynamic adapter creation based
    on the configured market mode and hedging preference.
    """

    # Define a type alias for the union of possible adapter types for clarity
    AdapterType = Union[BinanceTestnetAdapter, FuturesAdapter, Web3TestnetAdapter]

    def __init__(self, symbols: List[str], market_mode: str = "sim", crdt_adapter: Optional[Any] = None) -> None:
        """
        Initializes the MultiPairAdapter with a list of symbols and a market mode.

        Args:
            symbols (List[str]): A list of trading pair symbols (e.g., ["BTC/USDT", "ETH/USDT"]).
            market_mode (str): The operating mode. Can be "live", "futures", "web3", or "sim".
            crdt_adapter (Optional[Any]): An optional CRDT adapter instance, specifically for "web3" mode.
                                          Its type is Any because it's an external dependency not defined here.
        """
        self.symbols: List[str] = symbols
        self.market_mode: str = market_mode
        self.hedge_enabled: bool = os.environ.get("HEDGE_ENABLED", "false").lower() == "true"
        self.adapters: Dict[str, MultiPairAdapter.AdapterType] = {}

        for sym in symbols:
            if market_mode == "live":
                # In "live" mode, typically a spot adapter is used
                self.adapters[f"{sym}_spot"] = BinanceTestnetAdapter(symbol=sym)
            elif market_mode == "futures":
                # In "futures" mode, a futures adapter is primary
                self.adapters[f"{sym}_futures"] = FuturesAdapter(symbol=sym)
                if self.hedge_enabled:
                    # If hedging is enabled for futures, a corresponding spot adapter might also be needed
                    self.adapters[f"{sym}_spot"] = BinanceTestnetAdapter(symbol=sym)
            elif market_mode == "web3":
                # For "web3" mode, the Web3TestnetAdapter requires the CRDT adapter
                if crdt_adapter is None:
                    logger.warning("crdt_adapter is None, but required for 'web3' market_mode.")
                    # Depending on strictness, one might raise an error here.
                    # For now, we proceed, assuming the Web3TestnetAdapter handles a None crdt_adapter gracefully
                    # or that a default is provided internally if it's truly optional.
                self.adapters[f"{sym}_spot"] = Web3TestnetAdapter(symbol=sym, crdt_adapter=crdt_adapter)
            else:  # "sim" mode as default
                # In simulation mode, often a BinanceTestnetAdapter is used for price feeds or simulation base
                self.adapters[f"{sym}_spot"] = BinanceTestnetAdapter(symbol=sym)

        if not self.adapters:
            logger.warning(f"No adapters initialized for symbols: {symbols} with market mode: {market_mode}")

    def get_adapter(self, symbol: str, account: str = "spot") -> Optional["MultiPairAdapter.AdapterType"]:
        """
        Retrieves a specific market adapter by symbol and account type.

        Args:
            symbol (str): The trading pair symbol (e.g., "BTC/USDT").
            account (str): The type of account ('spot' or 'futures').

        Returns:
            Optional[MultiPairAdapter.AdapterType]:
            The requested adapter instance, or None if not found.
        """
        key: str = f"{symbol}_{account}"
        return self.adapters.get(key)

    async def fetch_all_tickers(self) -> Dict[str, Dict[str, Union[float, str, int]]]:
        """
        Asynchronously fetches ticker information for all managed adapters and normalizes prices.

        Iterates through all initialized adapters, attempts to fetch their latest ticker data,
        and applies a global price scaling factor if the `market_mode` is not "sim".
        Errors during fetching for individual adapters are logged but do not stop the process.

        Returns:
            Dict[str, Dict[str, Union[float, str, int]]]: A dictionary where keys are symbols
            and values are their normalized ticker information (price, bid, ask, symbol, timestamp).
            Prices are normalized by PRICE_SCALE for non-simulation modes.
            Returns an empty dictionary if no tickers could be fetched.
        """
        results: Dict[str, Dict[str, Union[float, str, int]]] = {}
        for key, adapter in self.adapters.items():
            # Extract symbol from the adapter key (e.g., "BTC/USDT_spot" -> "BTC/USDT")
            sym: str = key.split("_")[0]
            try:
                ticker: Optional[Dict[str, Union[float, str, int]]] = await adapter.get_ticker()
                if ticker:
                    # Normalize price for all modes except "sim"
                    if self.market_mode != "sim":
                        # Ensure 'price' exists, fallback to 'ask' or a default if necessary
                        # The fallback of 50000.0 is an arbitrary safety default.
                        raw_price_val: Union[float, str, int] = ticker.get("price", ticker.get("ask", 50000.0))
                        raw_price: float = float(raw_price_val)
                        ticker["price"] = raw_price / PRICE_SCALE

                        # It's good practice to normalize bid/ask too if 'price' is normalized
                        if "bid" in ticker and isinstance(ticker["bid"], (int, float)):
                            ticker["bid"] = float(ticker["bid"]) / PRICE_SCALE
                        if "ask" in ticker and isinstance(ticker["ask"], (int, float)):
                            ticker["ask"] = float(ticker["ask"]) / PRICE_SCALE
                    results[sym] = ticker
                else:
                    logger.debug(f"No ticker data returned for adapter '{key}'.")
            except Exception as e:
                logger.exception(f"Failed to fetch ticker for adapter '{key}'. Error: {e}")
        return results
