# adapters/live_market.py
"""
Binance Testnet adapter for BlackSwan swarm.
Provides live price feed (bid/ask), market hours filtering, and multi-symbol support.
"""
import os
import logging
from typing import Dict, Optional, Any, Union
from datetime import datetime, time
import ccxt

logger = logging.getLogger(__name__)

class BinanceTestnetAdapter:
    """
    Adapter for connecting to Binance Testnet, providing bid/ask price feeds.
    Includes functionality for market hours filtering and order placement.
    """

    def __init__(self, symbol: str = "BTC/USDT"):
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
        self.market_open_time: time = datetime.strptime(market_open_str, "%H:%M").time()
        self.market_close_time: time = datetime.strptime(market_close_str, "%H:%M").time()

        self.exchange = ccxt.binance({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
            },
            'testnet': True,
        })
        # Verify connection by loading markets
        try:
            self.exchange.load_markets()
            logger.info(f"Binance Testnet connected. Symbol: {symbol}")
        except Exception as e:
            logger.warning(f"Could not load markets for Binance Testnet (testnet may be unavailable): {e}")

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

    async def get_ticker(self) -> Optional[Dict[str, Union[float, str, int]]]:
        """
        Fetches the ticker information (last price, bid, ask) for the configured symbol,
        but only if the market is currently open.

        Returns:
            Optional[Dict[str, Union[float, str, int]]]: A dictionary containing
            'price', 'bid', 'ask', 'symbol', and 'timestamp' if successful and market open.
            Returns None if the market is closed.
            In case of an error, it returns a simulated price with None timestamp.
        """
        if not self._is_market_open():
            logger.debug(f"Market for {self.symbol} is closed, skipping live tick")
            return None

        try:
            ticker: Dict[str, Any] = self.exchange.fetch_ticker(self.symbol)
            return {
                "price": float(ticker['last']),
                "bid": float(ticker['bid']),
                "ask": float(ticker['ask']),
                "symbol": self.symbol,
                "timestamp": int(ticker['timestamp']),  # Timestamp in milliseconds
            }
        except Exception as e:
            logger.exception(f"Failed to fetch ticker for {self.symbol}. Falling back to simulated price.")
            # Fallback: simulated price with a consistent structure
            import random
            return {
                "price": random.uniform(40000.0, 50000.0),
                "bid": random.uniform(39900.0, 49900.0),
                "ask": random.uniform(40100.0, 50100.0),
                "symbol": self.symbol,
                "timestamp": None, # Indicate no real timestamp for simulated data
            }

    def place_order(self, side: str, amount: float, price: Optional[float] = None) -> Dict[str, Any]:
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
                order = self.exchange.create_limit_order(self.symbol, side, amount, price)
            else:
                order = self.exchange.create_market_order(self.symbol, side, amount)
            logger.info(f"Order placed: {side.upper()} {amount} {self.symbol} @ {price if price else 'MARKET'}. Order ID: {order.get('id')}")
            return order
        except Exception as e:
            logger.exception(f"Failed to place order for {side} {amount} {self.symbol} @ {price}.")
            return {"error": str(e), "status": "failed"}

    def fetch_balance(self) -> Dict[str, float]:
        """
        Fetches the free balance of the testnet account.

        Returns:
            Dict[str, float]: A dictionary where keys are currency symbols (e.g., 'USDT', 'BTC')
            and values are their free balances. Returns an empty dict on failure.
        """
        try:
            balance: Dict[str, Any] = self.exchange.fetch_balance()
            # ccxt balance structure has 'free', 'used', 'total' keys for each currency
            # and a top-level 'free' dict for all currencies.
            return balance.get('free', {})
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
