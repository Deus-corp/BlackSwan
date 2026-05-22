"""
Service responsible for providing market data snapshots to the swarm.

This module provides a mechanism to fetch live ticker data via an adapter
or fallback to a simulated price feed if the source is unavailable or the
system is not in a live execution mode.
"""
import logging
import random
from typing import Dict, Optional, Any, Protocol, Final, List

import aiohttp
from swarm_config import config

logger: Final = logging.getLogger(__name__)

DEFAULT_SYMBOL: Final[str] = "WETH/USDC"
LIVE_MODES: Final = {"live", "web3", "futures"}


class MarketAdapterProtocol(Protocol):
    """
    Defines the contract for market data providers.
    """
    async def fetch_all_tickers(self) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        Fetches mapping of symbols to ticker data. 
        Expected dict keys: 'price' (float), 'symbol' (str).
        """
        ...


class MarketSnapshotService:
    """
    Coordinates between real-time data adapters and simulation fallback.
    """
    __slots__ = ('_adapter', '_mode', '_primary_symbol')

    def __init__(self, market_adapter: MarketAdapterProtocol, market_mode: str) -> None:
        if not isinstance(market_mode, str):
            raise ValueError("market_mode must be a string.")
        if not hasattr(market_adapter, 'fetch_all_tickers'):
            raise ValueError("market_adapter must implement 'fetch_all_tickers'.")

        self._adapter: MarketAdapterProtocol = market_adapter
        self._mode: str = market_mode
        
        symbols: List[str] = [
            s.strip() for s in str(getattr(config, 'trading_symbols', '')).split(",") 
            if s.strip()
        ]
        self._primary_symbol: str = symbols[0] if symbols else DEFAULT_SYMBOL
        
        logger.debug("Initialized with mode: %s, primary_symbol: %s", self._mode, self._primary_symbol)

    async def get_snapshot(self, session: Optional[aiohttp.ClientSession] = None) -> Dict[str, Dict[str, Any]]:
        """
        Retrieves the current market snapshot.

        Attempts to use the adapter if in a live mode. Falls back to 
        simulated market data on failure or non-live settings.
        """
        if self._mode in LIVE_MODES:
            try:
                data = await self._adapter.fetch_all_tickers()
                if data:
                    self._sanitize_tickers(data)
                    logger.debug("Fetched %d tickers from adapter.", len(data))
                    return data
            except Exception as e:
                logger.warning("Adapter fetch failed in mode %s: %s", self._mode, e)

        return self._get_simulated_snapshot()

    def _sanitize_tickers(self, tickers: Dict[str, Dict[str, Any]]) -> None:
        """
        Ensures each ticker dict has a 'symbol' key mapping to its dict key.
        """
        for symbol, data in tickers.items():
            if isinstance(data, dict) and "symbol" not in data:
                data["symbol"] = symbol

    def _get_simulated_snapshot(self) -> Dict[str, Dict[str, Any]]:
        """
        Generates a fallback market snapshot with randomized pricing.
        """
        simulated_price = random.uniform(90.0, 110.0)
        logger.info("Simulating market snapshot for %s: price=%.2f", self._primary_symbol, simulated_price)
        return {
            self._primary_symbol: {
                "price": simulated_price,
                "symbol": self._primary_symbol
            }
        }