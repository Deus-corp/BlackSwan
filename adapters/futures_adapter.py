# adapters/futures_adapter.py
"""
Binance Testnet Futures adapter – открывает лонг/шорт, управляет плечом.
"""
import os
import logging
from typing import Dict, Optional
import ccxt

logger = logging.getLogger(__name__)

class FuturesAdapter:
    def __init__(self, symbol: str = "BTC/USDT"):
        self.symbol = symbol
        self.api_key = os.environ.get("BINANCE_TESTNET_API_KEY", "")
        self.api_secret = os.environ.get("BINANCE_TESTNET_API_SECRET", "")
        self.leverage = int(os.environ.get("FUTURES_LEVERAGE", 2))

        self.exchange = ccxt.binance({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',   # ключевой параметр
            },
            'testnet': True,
        })

        # Устанавливаем плечо
        try:
            self.exchange.set_leverage(self.leverage, self.symbol)
            logger.info(f"Futures adapter ready: {symbol}, leverage={self.leverage}x")
        except Exception as e:
            logger.warning(f"Could not set leverage: {e}")

    async def get_ticker(self) -> Optional[Dict[str, float]]:
        try:
            ticker = self.exchange.fetch_ticker(self.symbol)
            return {
                "price": ticker['last'],
                "bid": ticker['bid'],
                "ask": ticker['ask'],
                "symbol": self.symbol,
            }
        except Exception as e:
            logger.error(f"Futures ticker fetch failed: {e}")
            return None

    def place_order(self, side: str, amount: float, price: Optional[float] = None) -> Dict:
        """
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
        try:
            balance = self.exchange.fetch_balance()
            return balance.get('free', {})
        except Exception as e:
            logger.error(f"Balance fetch failed: {e}")
            return {}