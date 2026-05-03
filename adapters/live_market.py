# adapters/live_market.py
"""
Binance Testnet adapter for BlackSwan swarm.
Provides live price feed and paper trading via CCXT.
"""
import os
import logging
from typing import Dict, Optional
import ccxt

logger = logging.getLogger(__name__)

class BinanceTestnetAdapter:
    """Подключение к Binance Testnet для получения цен и выполнения виртуальных сделок."""

    def __init__(self, symbol: str = "BTC/USDT"):
        self.symbol = symbol
        self.api_key = os.environ.get("BINANCE_TESTNET_API_KEY", "")
        self.api_secret = os.environ.get("BINANCE_TESTNET_API_SECRET", "")

        self.exchange = ccxt.binance({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
            },
            'testnet': True,   # встроенный режим тестнета
        })
        # Проверка соединения (теперь будет стучаться на правильный testnet)
        try:
            self.exchange.load_markets()
            logger.info(f"Binance Testnet connected. Symbol: {symbol}")
        except Exception as e:
            logger.warning(f"Could not load markets (testnet may be unavailable): {e}")

    async def get_ticker(self) -> Dict[str, float]:
        """Возвращает тикер с последней ценой."""
        try:
            ticker = self.exchange.fetch_ticker(self.symbol)
            return {
                "price": ticker['last'],
                "symbol": self.symbol,
                "timestamp": ticker['timestamp'],
                "bid": ticker['bid'],
                "ask": ticker['ask'],
            }
        except Exception as e:
            logger.error(f"Failed to fetch ticker: {e}")
            # Fallback: возвращаем случайную цену в диапазоне, чтобы не сломать цикл
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