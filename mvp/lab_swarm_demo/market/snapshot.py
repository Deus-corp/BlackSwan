"""
Сервис получения рыночных данных для роя.
This service is responsible for fetching current market data (snapshots)
for all configured trading symbols using a provided market adapter.
It includes a fallback mechanism to simulate market prices if real data
cannot be obtained.
"""
import logging
import random
from typing import Dict, Optional, Any, Union
import aiohttp
from swarm_config import config

logger = logging.getLogger(__name__)

# A simple protocol could define the expected adapter interface
# For now, we'll use Any for flexibility with different adapter implementations.
# from typing import Protocol
# class MarketAdapterProtocol(Protocol):
#     async def fetch_all_tickers(self) -> Dict[str, Dict[str, Union[float, str]]]: ...


class MarketSnapshotService:
    """
    Собирает тики для всех торговых пар через адаптер.

    This service is responsible for fetching current market data (snapshots)
    for all configured trading symbols using a provided market adapter.
    It includes a fallback mechanism to simulate market prices if real data
    cannot be obtained.
    """

    def __init__(self, market_adapter: Any, market_mode: str) -> None:
        """
        Initializes the MarketSnapshotService.

        Args:
            market_adapter: An object responsible for fetching market data.
                            It is expected to have an async `fetch_all_tickers` method
                            that returns `Dict[str, Dict[str, Any]]`.
            market_mode: The operating mode for the market (e.g., "live", "web3", "futures").
        """
        self.adapter: Any = market_adapter
        self.mode: str = market_mode
        # Determine the primary trading symbol from config or default to WETH/USDC
        self.primary_symbol: str = (
            config.trading_symbols.split(",")[0].strip() if config.trading_symbols else "WETH/USDC"
        )

    async def get_snapshot(self, session: Optional[aiohttp.ClientSession] = None) -> Dict[str, Dict[str, Any]]:
        """
        Возвращает словарь {symbol: tick_dict} с ценами.
        При отсутствии данных подставляет симуляцию.

        Attempts to fetch real-time market data using the configured adapter.
        If successful, it returns a dictionary of ticker information.
        If fetching fails or no data is returned, it falls back to a simulated price.
        The returned `tick_dict` is guaranteed to contain at least "price" (float)
        and "symbol" (str) keys.

        Args:
            session: An optional aiohttp client session to use for requests.
                     This parameter is passed for compatibility but its direct
                     usage depends on the `market_adapter` implementation.

        Returns:
            A dictionary where keys are trading symbols (str) and values are
            dictionaries containing ticker information (e.g., {'price': X, 'symbol': Y}).
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
                    return all_tickers
            except Exception as e:
                # Log the specific error when the adapter fails to fetch data.
                # A broad Exception is caught here to ensure the fallback mechanism is always triggered.
                logger.warning(
                    f"Failed to fetch all tickers from adapter in mode '{self.mode}': {e}",
                    exc_info=False # Set to True for full traceback, but might be too verbose for warnings.
                )

        # Fallback mechanism: if the adapter failed, returned no data, or mode is not live/web3/futures.
        # Generate a simulated market snapshot for the primary trading symbol.
        symbol: str = self.primary_symbol
        # Ensure the simulated tick has "price" (float) and "symbol" (str) for consistency.
        simulated_tick: Dict[str, Any] = {
            "price": random.uniform(90.0, 110.0), # Generate a random float price
            "symbol": symbol
        }
        return {symbol: simulated_tick}
