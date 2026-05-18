"""
Сервис получения рыночных данных для роя.
"""
import logging
import random
from typing import Dict, Optional, Any # Added 'Any' for flexible type hinting
import aiohttp
from swarm_config import config

logger = logging.getLogger(__name__)


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
                            It is expected to have an async `fetch_all_tickers` method.
            market_mode: The operating mode for the market (e.g., "live", "web3", "futures").
        """
        self.adapter = market_adapter
        self.mode = market_mode
        # Determine the primary trading symbol from config or default to WETH/USDC
        self.primary_symbol: str = config.trading_symbols.split(",")[0].strip() if config.trading_symbols else "WETH/USDC"

    async def get_snapshot(self, session: Optional[aiohttp.ClientSession] = None) -> Dict[str, dict]:
        """
        Возвращает словарь {symbol: tick_dict} с ценами.
        При отсутствии данных подставляет симуляцию.

        Attempts to fetch real-time market data using the configured adapter.
        If successful, it returns a dictionary of ticker information.
        If fetching fails or no data is returned, it falls back to a simulated price.

        Args:
            session: An optional aiohttp client session to use for requests.
                     (Currently not directly used by `self.adapter.fetch_all_tickers`
                     in this snippet, but kept for signature compatibility).

        Returns:
            A dictionary where keys are trading symbols and values are dictionaries
            containing ticker information (e.g., {'price': X, 'symbol': Y}).
        """
        if self.mode in ("live", "web3", "futures") and self.adapter:
            try:
                all_tickers = await self.adapter.fetch_all_tickers()
                if all_tickers:
                    return all_tickers
            except Exception as e:
                # Log the specific error when the adapter fails
                logger.warning(f"Failed to fetch all tickers from adapter in mode '{self.mode}': {e}")

        # fallback – симуляция
        symbol: str = self.primary_symbol
        return {symbol: {"price": random.uniform(90, 110), "symbol": symbol}}