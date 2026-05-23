"""
Binance Testnet adapter for BlackSwan swarm.
Provides live price feed (bid/ask), market hours filtering, and multi-symbol support.
"""
import os
import logging
from typing import Dict, Optional, Any, Literal
from datetime import datetime, time, timezone
import ccxt.async_support as ccxt

logger = logging.getLogger(__name__)

class BinanceTestnetAdapter:
    """
    Adapter for connecting to Binance Testnet, providing bid/ask price feeds.
    Includes functionality for market hours filtering and order placement.
    """

    def __init__(self, symbol: str = "BTC/USDT") -> None:
        """
        Initializes the BinanceTestnetAdapter with environment-based config.

        Args:
            symbol (str): The trading pair symbol, e.g., "BTC/USDT".
        """
        self.symbol = symbol
        self.api_key = os.environ.get("BINANCE_TESTNET_API_KEY", "")
        self.api_secret = os.environ.get("BINANCE_TESTNET_API_SECRET", "")

        market_open_str = os.environ.get("MARKET_OPEN", "00:00")
        market_close_str = os.environ.get("MARKET_CLOSE", "23:59")
        
        try:
            self.market_open_time = datetime.strptime(market_open_str, "%H:%M").time()
            self.market_close_time = datetime.strptime(market_close_str, "%H:%M").time()
        except ValueError:
            logger.error("Invalid MARKET_OPEN/CLOSE format. Defaulting to 00:00-23:59.")
            self.market_open_time = time(0, 0)
            self.market_close_time = time(23, 59)

        self.exchange = ccxt.binance({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'},
            'testnet': True,
        })
    
    async def ainit(self) -> None:
        """
        Asynchronous initialization to verify connection by loading markets.
        """
        try:
            await self.exchange.load_markets()
            logger.info(f"Binance Testnet connected. Symbol: {self.symbol}")
        except Exception as e:
            logger.error(f"Connection failed for Binance Testnet: {e}")

    async def close(self) -> None:
        """
        Closes the CCXT exchange session.
        """
        await self.exchange.close()
        logger.info("Binance Testnet adapter closed.")

    def _is_market_open(self) -> bool:
        """
        Checks if current UTC time falls within the defined market hours.

        Returns:
            bool: True if open, False otherwise.
        """
        now = datetime.now(timezone.utc).time()
        if self.market_open_time <= self.market_close_time:
            return self.market_open_time <= now <= self.market_close_time
        return now >= self.market_open_time or now <= self.market_close_time

    async def get_ticker(self) -> Optional[Dict[Literal["price", "bid", "ask"], float]]:
        """
        Fetches ticker data if the market is open.

        Returns:
            Optional dict with price, bid, and ask.
        """
        if not self._is_market_open():
            return None

        try:
            ticker = await self.exchange.fetch_ticker(self.symbol)
            return {
                "price": float(ticker['last']),
                "bid": float(ticker['bid']),
                "ask": float(ticker['ask']),
            }
        except Exception as e:
            logger.error(f"Failed to fetch ticker for {self.symbol}: {e}")
            return None

    async def place_order(self, side: str, amount: float, price: Optional[float] = None) -> Dict[str, Any]:
        """
        Places an order on Binance Testnet.

        Args:
            side: 'buy' or 'sell'.
            amount: Asset quantity.
            price: Limit price (market order if None).

        Returns:
            Order response dict or failure status dict.
        """
        try:
            if price is not None:
                order = await self.exchange.create_limit_order(self.symbol, side, amount, price)
            else:
                order = await self.exchange.create_market_order(self.symbol, side, amount)
            logger.info(f"Placed {side} order for {amount} {self.symbol}. ID: {order.get('id')}")
            return order
        except Exception as e:
            logger.error(f"Order placement failed for {side} {self.symbol}: {e}")
            return {"error": str(e), "status": "failed"}

    async def fetch_balance(self) -> Dict[str, float]:
        """
        Fetches free account balances.

        Returns:
            Mapping of currency code to free balance.
        """
        try:
            balance = await self.exchange.fetch_balance()
            return {k: float(v) for k, v in balance.get('free', {}).items()}
        except Exception as e:
            logger.error(f"Balance fetch failed: {e}")
            return {}

    def switch_symbol(self, new_symbol: str) -> None:
        """
        Updates the active trading pair.
        """
        self.symbol = new_symbol
        logger.info(f"Switched symbol to {new_symbol}")