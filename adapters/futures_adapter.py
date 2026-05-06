# adapters/futures_adapter.py
import os
import logging
from typing import Dict, Optional
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

    async def get_ticker(self) -> Optional[Dict[str, float]]:
        """Возвращает тикер с последней ценой."""
        try:
            ticker = self.exchange.fetch_ticker(self.symbol)
            return {
                "price": ticker['last'],
                "bid": ticker['bid'],
                "ask": ticker['ask'],
                "symbol": self.symbol,
                "timestamp": ticker['timestamp'],
            }
        except Exception as e:
            logger.error(f"Futures ticker fetch failed: {e}")
            return None

    def place_order(self, side: str, amount: float, price: Optional[float] = None) -> Dict:
        """
        Выставляет лимитный или рыночный ордер.
        side: 'buy' (long) или 'sell' (short)
        amount: количество контрактов (в монетах)
        """
        try:
            if price:
                order = self.exchange.create_limit_order(self.symbol, side, amount, price)
            else:
                order = self.exchange.create_market_order(self.symbol, side, amount)
            logger.info(f"Futures order placed: {side} {amount} {self.symbol} @ {price}")
            return order
        except Exception as e:
            logger.error(f"Futures order failed: {e}")
            return {"error": str(e)}

    def close_position(self, symbol: Optional[str] = None) -> Dict:
        """Закрывает текущую позицию по рынку."""
        sym = symbol or self.symbol
        try:
            pos = self.exchange.fetch_positions([sym])
            if pos and len(pos) > 0:
                amt = abs(float(pos[0]['contracts']))
                if amt > 0:
                    side = 'sell' if pos[0]['side'] == 'long' else 'buy'
                    return self.place_order(side, amt)
            return {"error": "No open position"}
        except Exception as e:
            logger.error(f"Close position failed: {e}")
            return {"error": str(e)}

    def fetch_balance(self) -> Dict[str, float]:
        """Возвращает баланс тестового аккаунта."""
        try:
            balance = self.exchange.fetch_balance()
            return balance.get('free', {})
        except Exception as e:
            logger.error(f"Balance fetch failed: {e}")
            return {}

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