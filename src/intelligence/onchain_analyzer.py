# src/intelligence/onchain_analyzer.py
"""
On-Chain Analyzer – расширенный анализ блокчейн-данных через Etherscan API.
Предоставляет: баланс ETH, историю транзакций, газ, активность кошелька.
"""
import asyncio
import logging
from typing import Optional, Dict, Any, List
import aiohttp

logger = logging.getLogger(__name__)

class OnChainAnalyzer:
    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def get_eth_balance(self, address: str) -> Optional[float]:
        """Баланс ETH."""
        await self._ensure_session()
        url = (
            f"https://api.etherscan.io/api"
            f"?module=account&action=balance&address={address}&tag=latest"
        )
        if self.api_key:
            url += f"&apikey={self.api_key}"
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                if data.get("status") == "1":
                    return int(data["result"]) / 1e18
        except Exception as e:
            logger.error(f"Balance fetch failed: {e}")
        return None

    async def get_transaction_count(self, address: str) -> Optional[int]:
        """Количество транзакций (для оценки активности)."""
        await self._ensure_session()
        url = (
            f"https://api.etherscan.io/api"
            f"?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&page=1&offset=1&sort=desc"
        )
        if self.api_key:
            url += f"&apikey={self.api_key}"
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                if data.get("status") == "1":
                    return len(data["result"])
        except Exception as e:
            logger.error(f"Transaction count fetch failed: {e}")
        return None

    async def get_gas_oracle(self) -> Optional[Dict[str, float]]:
        """Текущие цены газа (Low/Medium/High)."""
        await self._ensure_session()
        url = (
            f"https://api.etherscan.io/api"
            f"?module=gastracker&action=gasoracle"
        )
        if self.api_key:
            url += f"&apikey={self.api_key}"
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                if data.get("status") == "1":
                    return {
                        "low": float(data["result"]["SafeGasPrice"]),
                        "medium": float(data["result"]["ProposeGasPrice"]),
                        "high": float(data["result"]["FastGasPrice"]),
                    }
        except Exception as e:
            logger.error(f"Gas fetch failed: {e}")
        return None

    async def get_full_report(self, address: str) -> dict:
        """Сводка по адресу."""
        balance = await self.get_eth_balance(address)
        tx_count = await self.get_transaction_count(address)
        gas = await self.get_gas_oracle()
        return {
            "balance_eth": balance,
            "transaction_count": tx_count,
            "gas_prices": gas,
        }