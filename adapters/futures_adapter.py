# adapters/futures_adapter.py
import os
import logging
import time
from typing import Dict, Optional, Any, List, Union
import ccxt.async_support as ccxt  # Import async_support for awaitable methods

logger = logging.getLogger(__name__)

class FuturesAdapter:
    """
    Adapter for interacting with a futures exchange using the CCXT library.

    Supports fetching tickers, placing orders, closing positions, retrieving balances,
    and dynamically adjusting leverage.
    """

    # Cooldown period for leverage adjustments (in seconds)
    LEVERAGE_ADJUST_COOLDOWN: int = 300  # 5 minutes

    def __init__(self, symbol: str = "BTC/USDT") -> None:
        """
        Initializes the futures adapter.

        Args:
            symbol (str): Default trading pair (e.g., "BTC/USDT").
        """
        self.symbol: str = symbol
        self.api_key: str = os.environ.get("BINANCE_TESTNET_API_KEY", "")
        self.api_secret: str = os.environ.get("BINANCE_TESTNET_API_SECRET", "")

        # Ensure leverage parameters are integers/floats
        self.leverage: int = int(os.environ.get("FUTURES_LEVERAGE", "2"))
        self.stop_loss_percent: float = float(os.environ.get("STOP_LOSS_PERCENT", "2.0"))
        self.max_leverage: int = int(os.environ.get("MAX_LEVERAGE", "5"))
        self.min_leverage: int = int(os.environ.get("MIN_LEVERAGE", "1"))
        self._last_leverage_adjust_timestamp: float = 0.0  # Renamed for clarity and usage

        if not self.api_key or not self.api_secret:
            logger.error("API key or secret not found. Futures adapter might not function correctly.")

        # Initialize CCXT async exchange client
        self.exchange: ccxt.binance = ccxt.binance({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,  # Enable built-in rate limiting
            'options': {'defaultType': 'future'},
            'testnet': True,
        })

    async def ainit(self) -> None:
        """
        Asynchronous initialization of the adapter. Should be called after __init__.
        Performs operations requiring await, such as setting leverage.
        """
        try:
            # Set initial leverage for the symbol
            await self.exchange.set_leverage(self.leverage, self.symbol)
            logger.info(f"Futures adapter ready: {self.symbol}, initial leverage={self.leverage}x")
        except ccxt.NetworkError as e:
            logger.error(f"Network error while setting initial leverage: {e}")
            # Potentially re-raise or handle if essential
        except ccxt.ExchangeError as e:
            logger.warning(f"Exchange error while setting initial leverage (e.g., invalid leverage): {e}")
        except Exception as e:
            logger.warning(f"Could not set initial leverage for {self.symbol}: {e}")

    async def close(self) -> None:
        """
        Closes the connection to the exchange. Recommended to call upon termination.
        """
        if self.exchange:
            await self.exchange.close()
            logger.info("Futures adapter CCXT exchange session closed.")

    async def get_ticker(self) -> Optional[Dict[str, Union[float, str, int]]]:
        """
        Returns the ticker with the last price for the set symbol.

        Returns:
            Optional[Dict[str, Union[float, str, int]]]: Dictionary with ticker information
            ('price', 'bid', 'ask', 'symbol', 'timestamp' (ms)) or None in case of error.
        """
        try:
            ticker: Dict[str, Any] = await self.exchange.fetch_ticker(self.symbol)
            return {
                "price": float(ticker['last']),
                "bid": float(ticker['bid']),
                "ask": float(ticker['ask']),
                "symbol": self.symbol,
                "timestamp": int(ticker['timestamp']),  # CCXT timestamps are usually milliseconds
            }
        except (ccxt.NetworkError, ccxt.ExchangeError) as e:
            logger.error(f"Futures ticker fetch failed for {self.symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred during ticker fetch: {e}")
            return None

    async def place_order(self, side: str, amount: float, price: Optional[float] = None) -> Dict[str, Any]:
        """
        Places a limit or market order.

        Args:
            side (str): 'buy' (long) or 'sell' (short).
            amount (float): Quantity of contracts (in coins).
            price (Optional[float]): Price for limit order. If None,
                                     a market order is placed.

        Returns:
            Dict[str, Any]: Dictionary with information about the placed order or
                            an error message.
        """
        if side not in ['buy', 'sell']:
            logger.error(f"Invalid order side: {side}. Must be 'buy' or 'sell'.")
            return {"error": "Invalid order side"}

        try:
            if price is not None:
                order: Dict[str, Any] = await self.exchange.create_limit_order(self.symbol, side, amount, price)
                logger.info(f"Futures LIMIT order placed: {side.upper()} {amount} {self.symbol} @ {price}")
            else:
                order: Dict[str, Any] = await self.exchange.create_market_order(self.symbol, side, amount)
                logger.info(f"Futures MARKET order placed: {side.upper()} {amount} {self.symbol}")
            return order
        except (ccxt.NetworkError, ccxt.ExchangeError) as e:
            logger.error(f"Futures order failed for {self.symbol}, side={side}, amount={amount}, price={price}: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"An unexpected error occurred during order placement: {e}")
            return {"error": str(e)}

    async def close_position(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Closes the current position in the market for the given symbol.

        Args:
            symbol (Optional[str]): Trading symbol for which to close the position.
                                    If None, uses self.symbol.

        Returns:
            Dict[str, Any]: Dictionary with information about the closing order or
                            an error message.
        """
        sym: str = symbol or self.symbol
        try:
            # fetch_positions takes an optional list of symbols or None for all
            positions: List[Dict[str, Any]] = await self.exchange.fetch_positions([sym])

            # Filter for the relevant position (assuming one position per symbol in futures)
            open_positions = [p for p in positions if float(p.get('contracts', 0)) != 0]

            if open_positions:
                pos: Dict[str, Any] = open_positions[0]  # Assuming only one open position for the symbol
                amount: float = abs(float(pos.get('contracts', 0)))  # Use .get() for safety

                if amount > 0:
                    # Determine the side to close the position
                    side: str = 'sell' if pos.get('side') == 'long' else 'buy'
                    logger.info(f"Attempting to close {pos.get('side')} position of {amount} {sym}")
                    # Place a market order to close the position
                    return await self.place_order(side, amount)
                else:
                    logger.info(f"No open position to close for {sym} (amount is zero).")
                    return {"info": "No open position"}
            else:
                logger.info(f"No open position found for {sym}.")
                return {"info": "No open position"}
        except (ccxt.NetworkError, ccxt.ExchangeError) as e:
            logger.error(f"Close position failed for {sym}: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"An unexpected error occurred during position closure: {e}")
            return {"error": str(e)}

    async def fetch_balance(self) -> Dict[str, float]:
        """
        Returns the balance of the test account, focusing on available funds.

        Returns:
            Dict[str, float]: Dictionary where the key is the currency code and the value is
                              the amount of available funds (available balance).
        """
        try:
            balance: Dict[str, Any] = await self.exchange.fetch_balance()
            # The 'free' key usually contains a dictionary of available assets
            return {k: float(v) for k, v in balance.get('free', {}).items()}  # Ensure float values
        except (ccxt.NetworkError, ccxt.ExchangeError) as e:
            logger.error(f"Balance fetch failed: {e}")
            return {}
        except Exception as e:
            logger.error(f"An unexpected error occurred during balance fetch: {e}")
            return {}

    def check_stop_loss(self, entry_price: float, current_price: float, side: str) -> bool:
        """
        Checks if the stop-loss has been triggered based on the set percentage.

        Args:
            entry_price (float): Price at which the position was entered.
            current_price (float): Current market price.
            side (str): Type of position ('long' or 'short').

        Returns:
            bool: True if the loss percentage exceeds `self.stop_loss_percent`,
                  otherwise False.
        """
        if side not in ['long', 'short']:
            logger.error(f"Invalid position side for stop-loss check: {side}. Must be 'long' or 'short'.")
            return False

        loss_percent: float
        if side == 'long':
            # For long position, loss occurs when current_price < entry_price
            if entry_price <= 0:  # Avoid division by zero
                logger.warning("Entry price for long position is zero or negative, cannot check stop loss.")
                return False
            loss_percent = (entry_price - current_price) / entry_price * 100
        else:  # 'short'
            # For short position, loss occurs when current_price > entry_price
            if entry_price <= 0:  # Avoid division by zero
                logger.warning("Entry price for short position is zero or negative, cannot check stop loss.")
                return False
            loss_percent = (current_price - entry_price) / entry_price * 100

        return loss_percent >= self.stop_loss_percent

    async def adjust_leverage(self, volatility: float) -> None:
        """
        Dynamically adjusts leverage based on volatility.
        Increases leverage for low volatility, decreases for high volatility.
        Includes a built-in timeout to prevent too frequent changes.

        Args:
            volatility (float): Normalized volatility value
                                (e.g., ATR / price).
        """
        current_time: float = time.monotonic()
        if current_time - self._last_leverage_adjust_timestamp < self.LEVERAGE_ADJUST_COOLDOWN:
            logger.debug(f"Leverage adjustment on cooldown. Next adjustment in {self.LEVERAGE_ADJUST_COOLDOWN - (current_time - self._last_leverage_adjust_timestamp):.1f}s")
            return

        target_leverage: Optional[int] = None

        # Adjust leverage based on volatility thresholds
        if volatility < 0.01:  # Low volatility -> increase leverage
            target_leverage = min(self.max_leverage, self.leverage + 1)
        elif volatility > 0.05:  # High volatility -> decrease leverage
            target_leverage = max(self.min_leverage, self.leverage - 1)

        if target_leverage is not None and target_leverage != self.leverage:
            try:
                await self.exchange.set_leverage(target_leverage, self.symbol)
                self.leverage = target_leverage
                self._last_leverage_adjust_timestamp = current_time
                logger.info(f"Leverage adjusted to {target_leverage}x for {self.symbol}")
            except (ccxt.NetworkError, ccxt.ExchangeError) as e:
                logger.error(f"Failed to adjust leverage for {self.symbol}: {e}")
            except Exception as e:
                logger.error(f"An unexpected error occurred during leverage adjustment: {e}")