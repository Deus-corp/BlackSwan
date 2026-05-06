# adapters/futures_adapter.py
import os
import logging
from typing import Dict, Optional, Tuple
import ccxt
import time

logger = logging.getLogger(__name__)

class FuturesAdapter:
    def __init__(self, symbol: str = "BTC/USDT"):
        self.symbol = symbol
        self.api_key = os.environ.get("BINANCE_TESTNET_API_KEY", "")
        self.api_secret = os.environ.get("BINANCE_TESTNET_API_SECRET", "")
        self.leverage = int(os.environ.get("FUTURES_LEVERAGE", 2))
        self.stop_loss_percent = float(os.environ.get("STOP_LOSS_PERCENT", 2.0))
        self.max_leverage = int(os.environ.get("MAX_LEVERAGE", 5))
        self.min_leverage = int(os.environ.get("MIN_LEVERAGE", 1))
        self._last_leverage_adjust = 0

        self.exchange = ccxt.binance({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
            'options': {'defaultType': 'future'},
            'testnet': True,
        })

        try:
            self.exchange.set_leverage(self.leverage, self.symbol)
            logger.info(f"Futures adapter ready: {symbol}, leverage={self.leverage}x")
        except Exception as e:
            logger.warning(f"Could not set leverage: {e}")

    # ... остальные методы ...

    def check_stop_loss(self, entry_price: float, current_price: float, side: str) -> bool:
        """
        Возвращает True, если сработал стоп‑лосс.
        side: 'long' или 'short'
        """
        if side == 'long':
            loss_percent = (entry_price - current_price) / entry_price * 100
        else:  # short
            loss_percent = (current_price - entry_price) / entry_price * 100
        return loss_percent >= self.stop_loss_percent

    async def adjust_leverage(self, volatility: float) -> None:
        """
        Увеличивает плечо при низкой волатильности, уменьшает при высокой.
        volatility – нормализованное значение (например, ATR/price).
        """
        # Простая эвристика: если волатильность < 1%, повышаем плечо, если > 5% – понижаем.
        if volatility < 0.01:
            target = min(self.max_leverage, self.leverage + 1)
        elif volatility > 0.05:
            target = max(self.min_leverage, self.leverage - 1)
        else:
            return

        if target != self.leverage:
            try:
                self.exchange.set_leverage(target, self.symbol)
                self.leverage = target
                logger.info(f"Leverage adjusted to {self.leverage}x (volatility={volatility:.4f})")
            except Exception as e:
                logger.warning(f"Leverage adjustment failed: {e}")