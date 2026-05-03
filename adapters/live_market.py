# adapters/live_market.py
"""
Binance Testnet adapter for BlackSwan swarm.
Provides live price feed (bid/ask), market hours filtering, and multi-symbol support.
"""
import os
import logging
from typing import Dict, Optional
from datetime import datetime, time
import ccxt

logger = logging.getLogger(__name__)

class BinanceTestnetAdapter:
    """Подключение к Binance Testnet с использованием bid/ask."""

    def __init__(self, symbol: str = "BTC/USDT"):
        self.symbol = symbol
        self.api_key = os.environ.get("BINANCE_TESTNET_API_KEY", "")
        self.api_secret = os.environ.get("BINANCE_TESTNET_API_SECRET", "")

        # Настройка рыночных часов (UTC)
        self.market_open = os.environ.get("MARKET_OPEN", "00:00")  # по умолчанию круглосуточно
        self.market_close = os.environ.get("MARKET_CLOSE", "23:59")

        self.exchange = ccxt.binance({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
            },
            'testnet': True,
        })
        # Проверка соединения
        try:
            self.exchange.load_markets()
            logger.info(f"Binance Testnet connected. Symbol: {symbol}")
        except Exception as e:
            logger.warning(f"Could not load markets (testnet may be unavailable): {e}")

    def _is_market_open(self) -> bool:
        """Проверяет, находится ли текущее время в торговом окне."""
        now = datetime.utcnow().time()
        open_time = datetime.strptime(self.market_open, "%H:%M").time()
        close_time = datetime.strptime(self.market_close, "%H:%M").time()
        if open_time <= close_time:
            return open_time <= now <= close_time
        else:  # окно переходит через полночь
            return now >= open_time or now <= close_time

    async def get_ticker(self) -> Optional[Dict[str, float]]:
        """Возвращает тикер с bid/ask, если рынок открыт."""
        if not self._is_market_open():
            logger.debug("Market is closed, skipping live tick")
            return None

        try:
            ticker = self.exchange.fetch_ticker(self.symbol)
            return {
                "price": ticker['last'],    # для совместимости
                "bid": ticker['bid'],
                "ask": ticker['ask'],
                "symbol": self.symbol,
                "timestamp": ticker['timestamp'],
            }
        except Exception as e:
            logger.error(f"Failed to fetch ticker: {e}")
            # Fallback: симулированная цена
            import random
            return {"price": random.uniform(40000, 50000), "symbol": self.symbol, "timestamp": None}

    def place_order(self, side: str, amount: float, price: Optional[float] = None) -> Dict:
        """
        Выставляет лимитный или рыночный ордер.
        side: 'buy' или 'sell'
        amount: количество базовой валюты
        """
        try:
            if price:
                order = self.exchange.create_limit_order(self.symbol, side, amount, price)
            else:
                order = self.exchange.create_market_order(self.symbol, side, amount)
            logger.info(f"Order placed: {side} {amount} {self.symbol} @ {price}")
            return order
        except Exception as e:
            logger.error(f"Order failed: {e}")
            return {"error": str(e)}

    def fetch_balance(self) -> Dict[str, float]:
        """Возвращает баланс тестового аккаунта."""
        try:
            balance = self.exchange.fetch_balance()
            return balance.get('free', {})
        except Exception as e:
            logger.error(f"Failed to fetch balance: {e}")
            return {}

    def switch_symbol(self, new_symbol: str):
        """Смена торговой пары без пересоздания адаптера."""
        self.symbol = new_symbol
        logger.info(f"Switched symbol to {new_symbol}")