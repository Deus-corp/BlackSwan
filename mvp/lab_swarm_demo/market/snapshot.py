"""
Сервис получения рыночных данных для роя.
"""
import logging
import random
from typing import Dict, Optional
import aiohttp
from swarm_config import config

logger = logging.getLogger(__name__)


class MarketSnapshotService:
    """Собирает тики для всех торговых пар через адаптер."""

    def __init__(self, market_adapter, market_mode: str):
        self.adapter = market_adapter
        self.mode = market_mode
        self.primary_symbol = config.trading_symbols.split(",")[0].strip() if config.trading_symbols else "WETH/USDC"

    async def get_snapshot(self, session: Optional[aiohttp.ClientSession] = None) -> Dict[str, dict]:
        """
        Возвращает словарь {symbol: tick_dict} с ценами.
        При отсутствии данных подставляет симуляцию.
        """
        if self.mode in ("live", "web3", "futures") and self.adapter:
            try:
                all_tickers = await self.adapter.fetch_all_tickers()
                if all_tickers:
                    return all_tickers
            except Exception as e:
                logger.warning(f"fetch_all_tickers failed: {e}")

        # fallback – симуляция
        symbol = self.primary_symbol
        return {symbol: {"price": random.uniform(90, 110), "symbol": symbol}}