"""
Сервис получения рыночных данных для роя.
This service is responsible for fetching current market data (snapshots)
for all configured trading symbols using a provided market adapter.
It includes a fallback mechanism to simulate market prices if real data
cannot be obtained.
"""
import logging
import random
from typing import Dict, Optional, Any, Union, Protocol, List
import aiohttp
from swarm_config import config

logger = logging.getLogger(__name__)


class MarketAdapterProtocol(Protocol):
    """
    Protocol defining the expected interface for a market data adapter.
    Adapters should implement an async method to fetch ticker data.
    """
    async def fetch_all_tickers(self) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        Asynchronously fetches ticker data for all configured symbols.

        Returns:
            An optional dictionary where keys are trading symbols (str) and values
            are dictionaries containing ticker information. Each ticker dictionary
            is expected to have at least 'price' (float) and 'symbol' (str).
            Returns None if no data can be fetched or an error occurs.
        """
        ... # Ellipsis indicates an abstract method


class MarketSnapshotService:
    """
    Service responsible for fetching current market data (snapshots) for
    all configured trading symbols using a provided market adapter.

    It includes a fallback mechanism to simulate market prices if real data
    cannot be obtained or if the service operates in a non-live mode.
    """

    adapter: MarketAdapterProtocol
    mode: str
    primary_symbol: str

    def __init__(self, market_adapter: MarketAdapterProtocol, market_mode: str) -> None:
        """
        Initializes the MarketSnapshotService.

        Args:
            market_adapter: An object adhering to the MarketAdapterProtocol,
                            responsible for fetching market data. It is expected
                            to have an async `fetch_all_tickers` method.
            market_mode: The operating mode for the market (e.g., "live", "web3", "futures", "simulate").
        """
        self.adapter = market_adapter
        self.mode = market_mode
        # Determine the primary trading symbol from config or default to WETH/USDC
        # config.trading_symbols can be None or an empty string, handle both
        symbols_list: List[str] = [s.strip() for s in config.trading_symbols.split(",") if s.strip()] \
            if config.trading_symbols else []
        self.primary_symbol = symbols_list[0] if symbols_list else "WETH/USDC"
        logger.debug(f"MarketSnapshotService initialized with mode: {self.mode}, primary_symbol: {self.primary_symbol}")


    async def get_snapshot(self, session: Optional[aiohttp.ClientSession] = None) -> Dict[str, Dict[str, Any]]:
        """
        Retrieves a market snapshot, attempting to fetch real-time data first,
        then falling back to simulation if necessary.

        The returned dictionary maps trading symbols to their ticker information.
        Each ticker dictionary is guaranteed to contain at least "price" (float)
        and "symbol" (str) keys.

        Args:
            session: An optional aiohttp client session to use for HTTP requests.
                     This parameter is passed for compatibility; its direct usage
                     depends on the `market_adapter` implementation.

        Returns:
            A dictionary where keys are trading symbols (str) and values are
            dictionaries containing ticker information (e.g., {'price': X.XX, 'symbol': 'SYM'}).
        """
        if self.mode in ("live", "web3", "futures") and self.adapter:
            try:
                # The adapter is expected to handle its own session or utilize the passed one.
                # Assuming fetch_all_tickers does not currently use the session parameter directly.
                all_tickers: Optional[Dict[str, Dict[str, Any]]] = await self.adapter.fetch_all_tickers()
                if all_tickers:
                    # Ensure all tickers returned by the adapter also contain the 'symbol' key
                    # for consistency, though the adapter should ideally provide it.
                    for symbol, tick_data in all_tickers.items():
                        if "symbol" not in tick_data:
                            tick_data["symbol"] = symbol
                    logger.debug(f"Fetched {len(all_tickers)} tickers from adapter in mode '{self.mode}'.")
                    return all_tickers
            except Exception as e:
                # Log the specific error when the adapter fails to fetch data.
                # A broad Exception is caught here to ensure the fallback mechanism is always triggered.
                logger.warning(
                    f"Failed to fetch all tickers from adapter in mode '{self.mode}': {type(e).__name__}: {e}",
                    exc_info=False # Set to True for full traceback, but might be too verbose for warnings.
                )
        else:
            if not self.adapter:
                logger.debug(f"No market adapter configured for mode '{self.mode}', falling back to simulation.")
            elif self.mode not in ("live", "web3", "futures"):
                logger.debug(f"Market mode '{self.mode}' is not live, falling back to simulation.")

        # Fallback mechanism: if the adapter failed, returned no data, or mode is not live/web3/futures.
        # Generate a simulated market snapshot for the primary trading symbol.
        symbol: str = self.primary_symbol
        # Ensure the simulated tick has "price" (float) and "symbol" (str) for consistency.
        simulated_price: float = random.uniform(90.0, 110.0)
        simulated_tick: Dict[str, Union[float, str]] = {
            "price": simulated_price,
            "symbol": symbol
        }
        logger.info(f"Simulating market snapshot for {symbol}: price={simulated_price:.2f}")
        return {symbol: simulated_tick}
