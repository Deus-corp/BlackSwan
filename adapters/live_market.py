# adapters/live_market.py
"""
Binance Testnet adapter for BlackSwan swarm.
Provides live price feed (bid/ask), market hours filtering, and multi-symbol support.
"""
import os
import logging
from typing import Dict, Optional, Any, Union, Literal
from datetime import datetime, time
import ccxt.async_support as ccxt # Import async_support for awaitable methods

logger = logging.getLogger(__name__)

class BinanceTestnetAdapter:
    """
    Adapter for connecting to Binance Testnet, providing bid/ask price feeds.
    Includes functionality for market hours filtering and order placement.
    """

    def __init__(self, symbol: str = "BTC/USDT") -> None:
        """
        Initializes the BinanceTestnetAdapter.

        Args:
            symbol (str): The trading pair symbol, e.g., "BTC/USDT".
        """
        self.symbol: str = symbol
        self.api_key: str = os.environ.get("BINANCE_TESTNET_API_KEY", "")
        self.api_secret: str = os.environ.get("BINANCE_TESTNET_API_SECRET", "")

        # Market hours configuration (UTC)
        market_open_str: str = os.environ.get("MARKET_OPEN", "00:00")
        market_close_str: str = os.environ.get("MARKET_CLOSE", "23:59")
        
        try:
            self.market_open_time: time = datetime.strptime(market_open_str, "%H:%M").time()
            self.market_close_time: time = datetime.strptime(market_close_str, "%H:%M").time()
        except ValueError as e:
            logger.error(f"Invalid MARKET_OPEN or MARKET_CLOSE format: {e}. Using default 00:00-23:59.")
            self.market_open_time = time(0, 0)
            self.market_close_time = time(23, 59)

        self.exchange: ccxt.binance = ccxt.binance({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
            },
            'testnet': True,
        })
    
    async def ainit(self) -> None:
        """
        Asynchronous initialization of the adapter. Should be called after __init__.
        Loads markets to verify connection.
        """
        # Verify connection by loading markets
        try:
            await self.exchange.load_markets()
            logger.info(f"Binance Testnet connected. Symbol: {self.symbol}")
        except Exception as e:
            logger.warning(f"Could not load markets for Binance Testnet (testnet may be unavailable): {e}")

    async def close(self) -> None:
        """
        Closes the connection to the exchange. Recommended to call upon termination.
        """
        if self.exchange:
            await self.exchange.close()
            logger.info("Binance Testnet adapter CCXT exchange session closed.")

    def _is_market_open(self) -> bool:
        """
        Checks if the current UTC time falls within the defined market open and close times.

        Returns:
            bool: True if the market is open, False otherwise.
        """
        now: time = datetime.utcnow().time()
        if self.market_open_time <= self.market_close_time:
            # Market hours do not cross midnight
            return self.market_open_time <= now <= self.market_close_time
        else:
            # Market hours cross midnight (e.g., 22:00 to 04:00)
            return now >= self.market_open_time or now <= self.market_close_time

    async def get_ticker(self) -> Optional[Dict[Literal["price", "bid", "ask"], float]]:
        """
        Fetches the ticker information (last price, bid, ask) for the configured symbol,
        but only if the market is currently open.

        Returns:
            Optional[Dict[Literal["price", "bid", "ask"], float]]: A dictionary containing
            'price', 'bid', 'ask', 'symbol', and 'timestamp' if successful and market open.
            Returns None if the market is closed or in case of an error.
            Note: For simplicity, the simulated price fallback is removed as it would make
            the return type more complex and usually real-time adapters should fail if
            live data cannot be obtained.
        """
        if not self._is_market_open():
            logger.debug(f"Market for {self.symbol} is closed, skipping live tick")
            return None

        try:
            ticker: Dict[str, Any] = await self.exchange.fetch_ticker(self.symbol)
            return {
                "price": float(ticker['last']),
                "bid": float(ticker['bid']),
                "ask": float(ticker['ask']),
                # "symbol": self.symbol, # Removed from return dict to match Dict[Literal["..."], float]
                # "timestamp": int(ticker['timestamp']), # Removed from return dict for simplicity, if needed, adjust return type
            }
        except Exception as e:
            logger.exception(f"Failed to fetch ticker for {self.symbol}.")
            return None

    async def place_order(self, side: str, amount: float, price: Optional[float] = None) -> Dict[str, Any]:
        """
        Places a limit or market order on Binance Testnet.

        Args:
            side (str): The order side ('buy' or 'sell').
            amount (float): The quantity of the base currency to trade.
            price (Optional[float]): The price for a limit order. If None, a market order is placed.

        Returns:
            Dict[str, Any]: A dictionary representing the placed order, or an error message.
        """
        try:
            order: Dict[str, Any]
            if price is not None:
                order = await self.exchange.create_limit_order(self.symbol, side, amount, price)
            else:
                order = await self.exchange.create_market_order(self.symbol, side, amount)
            logger.info(f"Order placed: {side.upper()} {amount} {self.symbol} @ {price if price else 'MARKET'}. Order ID: {order.get('id')}")
            return order
        except Exception as e:
            logger.exception(f"Failed to place order for {side} {amount} {self.symbol} @ {price}.")
            return {"error": str(e), "status": "failed"}

    async def fetch_balance(self) -> Dict[str, float]:
        """
        Fetches the free balance of the testnet account.

        Returns:
            Dict[str, float]: A dictionary where keys are currency symbols (e.g., 'USDT', 'BTC')
            and values are their free balances. Returns an empty dict on failure.
        """
        try:
            balance: Dict[str, Any] = await self.exchange.fetch_balance()
            # ccxt balance structure has 'free', 'used', 'total' keys for each currency
            # and a top-level 'free' dict for all currencies.
            return {k: float(v) for k, v in balance.get('free', {}).items()} # Ensure float values
        except Exception as e:
            logger.exception("Failed to fetch balance from Binance Testnet.")
            return {}

    def switch_symbol(self, new_symbol: str) -> None:
        """
        Changes the trading pair symbol for the adapter without reinitializing.

        Args:
            new_symbol (str): The new trading pair symbol, e.g., "ETH/USDT".
        """
        self.symbol = new_symbol
        logger.info(f"Switched symbol to {new_symbol}")