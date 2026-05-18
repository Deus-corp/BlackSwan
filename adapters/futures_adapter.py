# adapters/futures_adapter.py
import os
import logging
import time
from typing import Dict, Optional, Any
import ccxt

logger = logging.getLogger(__name__)

class FuturesAdapter:
    """
    Адаптер для взаимодействия с фьючерсной биржей через библиотеку CCXT.

    Поддерживает получение тикеров, размещение ордеров, закрытие позиций,
    получение баланса и динамическую регулировку кредитного плеча.
    """

    # Cooldown period for leverage adjustments (in seconds)
    LEVERAGE_ADJUST_COOLDOWN: int = 300  # 5 minutes

    def __init__(self, symbol: str = "BTC/USDT"):
        """
        Инициализирует адаптер фьючерсов.

        Args:
            symbol (str): Торговая пара по умолчанию (например, "BTC/USDT").
        """
        self.symbol: str = symbol
        self.api_key: str = os.environ.get("BINANCE_TESTNET_API_KEY", "")
        self.api_secret: str = os.environ.get("BINANCE_TESTNET_API_SECRET", "")
        
        # Ensure leverage parameters are integers/floats
        self.leverage: int = int(os.environ.get("FUTURES_LEVERAGE", "2"))
        self.stop_loss_percent: float = float(os.environ.get("STOP_LOSS_PERCENT", "2.0"))
        self.max_leverage: int = int(os.environ.get("MAX_LEVERAGE", "5"))
        self.min_leverage: int = int(os.environ.get("MIN_LEVERAGE", "1"))
        self._last_leverage_adjust_timestamp: float = 0.0 # Renamed for clarity and usage

        if not self.api_key or not self.api_secret:
            logger.error("API key or secret not found. Futures adapter might not function correctly.")

        # Initialize CCXT exchange client
        self.exchange: ccxt.Exchange = ccxt.binance({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,  # Enable built-in rate limiting
            'options': {'defaultType': 'future'},
            'testnet': True,
        })

        try:
            # Set initial leverage for the symbol
            self.exchange.set_leverage(self.leverage, self.symbol)
            logger.info(f"Futures adapter ready: {self.symbol}, initial leverage={self.leverage}x")
        except ccxt.NetworkError as e:
            logger.error(f"Network error while setting initial leverage: {e}")
            # Potentially re-raise or handle if essential
        except ccxt.ExchangeError as e:
            logger.warning(f"Exchange error while setting initial leverage (e.g., invalid leverage): {e}")
        except Exception as e:
            logger.warning(f"Could not set initial leverage for {self.symbol}: {e}")

    async def get_ticker(self) -> Optional[Dict[str, float]]:
        """
        Возвращает тикер с последней ценой для установленного символа.

        Returns:
            Optional[Dict[str, float]]: Словарь с информацией о тикере
            (price, bid, ask, symbol, timestamp) или None в случае ошибки.
        """
        try:
            # Note: ccxt methods are synchronous by default unless using ccxt.async_support
            ticker: Dict[str, Any] = self.exchange.fetch_ticker(self.symbol)
            return {
                "price": float(ticker['last']),
                "bid": float(ticker['bid']),
                "ask": float(ticker['ask']),
                "symbol": self.symbol,
                "timestamp": float(ticker['timestamp']),
            }
        except (ccxt.NetworkError, ccxt.ExchangeError) as e:
            logger.error(f"Futures ticker fetch failed for {self.symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred during ticker fetch: {e}")
            return None

    def place_order(self, side: str, amount: float, price: Optional[float] = None) -> Dict[str, Any]:
        """
        Выставляет лимитный или рыночный ордер.

        Args:
            side (str): 'buy' (long) или 'sell' (short).
            amount (float): Количество контрактов (в монетах).
            price (Optional[float]): Цена для лимитного ордера. Если None,
                                     выставляется рыночный ордер.

        Returns:
            Dict[str, Any]: Словарь с информацией о размещенном ордере или
                            сообщение об ошибке.
        """
        if side not in ['buy', 'sell']:
            logger.error(f"Invalid order side: {side}. Must be 'buy' or 'sell'.")
            return {"error": "Invalid order side"}

        try:
            if price is not None:
                order: Dict[str, Any] = self.exchange.create_limit_order(self.symbol, side, amount, price)
                logger.info(f"Futures LIMIT order placed: {side.upper()} {amount} {self.symbol} @ {price}")
            else:
                order: Dict[str, Any] = self.exchange.create_market_order(self.symbol, side, amount)
                logger.info(f"Futures MARKET order placed: {side.upper()} {amount} {self.symbol}")
            return order
        except (ccxt.NetworkError, ccxt.ExchangeError) as e:
            logger.error(f"Futures order failed for {self.symbol}, side={side}, amount={amount}, price={price}: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"An unexpected error occurred during order placement: {e}")
            return {"error": str(e)}

    def close_position(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Закрывает текущую позицию по рынку для заданного символа.

        Args:
            symbol (Optional[str]): Торговый символ, позицию по которому нужно закрыть.
                                    Если None, используется self.symbol.

        Returns:
            Dict[str, Any]: Словарь с информацией о закрывающем ордере или
                            сообщение об ошибке.
        """
        sym: str = symbol or self.symbol
        try:
            positions: list[Dict[str, Any]] = self.exchange.fetch_positions([sym])
            
            # Filter for the relevant position (assuming one position per symbol in futures)
            open_positions = [p for p in positions if float(p.get('contracts', 0)) != 0]

            if open_positions:
                pos: Dict[str, Any] = open_positions[0] # Assuming only one open position for the symbol
                amount: float = abs(float(pos.get('contracts', 0))) # Use .get() for safety
                
                if amount > 0:
                    # Determine the side to close the position
                    side: str = 'sell' if pos.get('side') == 'long' else 'buy'
                    logger.info(f"Attempting to close {pos.get('side')} position of {amount} {sym}")
                    # Place a market order to close the position
                    return self.place_order(side, amount)
                else:
                    logger.info(f"No open position to close for {sym}.")
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

    def fetch_balance(self) -> Dict[str, float]:
        """
        Возвращает баланс тестового аккаунта, фокусируясь на доступных средствах.

        Returns:
            Dict[str, float]: Словарь, где ключ - это код валюты, а значение -
                              количество свободных средств (available balance).
        """
        try:
            balance: Dict[str, Any] = self.exchange.fetch_balance()
            # The 'free' key usually contains a dictionary of available assets
            return balance.get('free', {}) # This matches Dict[str, float]
        except (ccxt.NetworkError, ccxt.ExchangeError) as e:
            logger.error(f"Balance fetch failed: {e}")
            return {}
        except Exception as e:
            logger.error(f"An unexpected error occurred during balance fetch: {e}")
            return {}

    def check_stop_loss(self, entry_price: float, current_price: float, side: str) -> bool:
        """
        Проверяет, сработал ли стоп-лосс на основе заданного процента.

        Args:
            entry_price (float): Цена входа в позицию.
            current_price (float): Текущая рыночная цена.
            side (str): Тип позиции ('long' или 'short').

        Returns:
            bool: True, если процент потерь превысил `self.stop_loss_percent`,
                  иначе False.
        """
        if side not in ['long', 'short']:
            logger.error(f"Invalid position side for stop-loss check: {side}. Must be 'long' or 'short'.")
            return False

        loss_percent: float
        if side == 'long':
            # For long position, loss occurs when current_price < entry_price
            loss_percent = (entry_price - current_price) / entry_price * 100
        else:  # 'short'
            # For short position, loss occurs when current_price > entry_price
            loss_percent = (current_price - entry_price) / entry_price * 100
        
        return loss_percent >= self.stop_loss_percent

    async def adjust_leverage(self, volatility: float) -> None:
        """
        Динамически регулирует кредитное плечо в зависимости от волатильности.
        Увеличивает плечо при низкой волатильности, уменьшает при высокой.
        Имеет встроенный таймаут для предотвращения слишком частых изменений.

        Args:
            volatility (float): Нормализованное значение волатильности
                                (например, ATR / price).
        """
        current_time = time.monotonic()
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
                # Note: ccxt methods are synchronous by default unless using ccxt.async_support
                self.exchange.set_leverage(target_leverage, self.symbol)
                self.leverage = target_leverage
                self._last_leverage_adjust_timestamp = current_time # Update timestamp on successful adjustment
                logger.info(f"Leverage adjusted to {self.leverage}x for {self.symbol} (volatility={volatility:.4f})")
            except (ccxt.NetworkError, ccxt.ExchangeError) as e:
                logger.warning(f"Leverage adjustment failed for {self.symbol} to {target_leverage}x: {e}")
            except Exception as e:
                logger.warning(f"An unexpected error occurred during leverage adjustment: {e}")
        else:
            logger.debug(f"No leverage adjustment needed for {self.symbol} (current={self.leverage}x, volatility={volatility:.4f})")