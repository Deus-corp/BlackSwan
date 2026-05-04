# adapters/web3_testnet.py
"""
Web3 Testnet Adapter (Arbitrum Sepolia) — заглушка.
В будущем заменит вызовы к Binance Testnet на On-Chain взаимодействие.
"""
import os
import logging
from typing import Dict, Optional
# import web3  # раскомментировать после установки web3.py

logger = logging.getLogger(__name__)

class Web3TestnetAdapter:
    """Заглушка для Web3-торговли. Пока возвращает симулированные данные."""

    def __init__(self, symbol: str = "WETH/USDC"):
        self.symbol = symbol
        # В будущем здесь будут настройки RPC и приватного ключа
        logger.info(f"Web3 Testnet Adapter initialized for {symbol} (stub)")

    async def get_ticker(self) -> Optional[Dict[str, float]]:
        """Возвращает симулированный тикер. В будущем будет запрашивать Uniswap Quoter."""
        import random
        return {
            "price": random.uniform(2000, 3000),
            "symbol": self.symbol,
            "timestamp": None,
            "bid": random.uniform(1999, 2999),
            "ask": random.uniform(2001, 3001),
        }

    def place_order(self, side: str, amount: float, price: Optional[float] = None) -> Dict:
        """Заглушка для размещения ордера. В будущем будет вызывать SwapRouter."""
        logger.info(f"Stub order: {side} {amount} {self.symbol} @ {price}")
        return {"status": "stub", "tx_hash": "0x0"}

    def fetch_balance(self) -> Dict[str, float]:
        """Возвращает нулевой баланс (заглушка)."""
        return {}