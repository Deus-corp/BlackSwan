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
    """
    Класс для анализа данных блокчейна Ethereum с использованием Etherscan API.
    Предоставляет методы для получения баланса ETH, количества транзакций,
    цен на газ и полного отчета по адресу.
    """
    def __init__(self, api_key: str = ""):
        self.api_key: str = api_key
        self.session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self) -> None:
        """
        Гарантирует, что сессия aiohttp.ClientSession активна.
        Если сессия не существует, она будет создана.
        """
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def close(self) -> None:
        """
        Закрывает текущую сессию aiohttp.ClientSession, если она активна.
        """
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
                resp.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
                data = await resp.json()
                if data.get("status") == "1":
                    return int(data["result"]) / 1e18
                else:
                    logger.warning(f"Etherscan API error for balance {address}: {data.get('message', 'No message')}")
        except aiohttp.ClientError as e:
            logger.error(f"Network or client error fetching balance for {address}: {e}")
        except ValueError as e: # Catch JSON decoding errors
            logger.error(f"JSON decoding error fetching balance for {address}: {e}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred while fetching balance for {address}: {e}")
        return None

    async def get_transaction_count(self, address: str) -> Optional[int]:
        """
        Количество транзакций (для оценки активности).
        Примечание: Etherscan API txlist с offset=1 возвращает только 1 транзакцию (если есть).
        Для получения общего количества транзакций требуется более сложная пагинация.
        Текущая логика возвращает 1, если есть хотя бы одна транзакция, или 0.
        """
        await self._ensure_session()
        url = (
            f"https://api.etherscan.io/api"
            f"?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&page=1&offset=1&sort=desc"
        )
        if self.api_key:
            url += f"&apikey={self.api_key}"
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                resp.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
                data = await resp.json()
                if data.get("status") == "1":
                    return len(data["result"])
                else:
                    logger.warning(f"Etherscan API error for transaction count {address}: {data.get('message', 'No message')}")
        except aiohttp.ClientError as e:
            logger.error(f"Network or client error fetching transaction count for {address}: {e}")
        except ValueError as e: # Catch JSON decoding errors
            logger.error(f"JSON decoding error fetching transaction count for {address}: {e}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred while fetching transaction count for {address}: {e}")
        return None

    async def get_gas_oracle(self) -> Optional[Dict[str, float]]:
        """Текущие цены газа (Low/Medium/High) в Gwei."""
        await self._ensure_session()
        url = (
            f"https://api.etherscan.io/api"
            f"?module=gastracker&action=gasoracle"
        )
        if self.api_key:
            url += f"&apikey={self.api_key}"
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                resp.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
                data = await resp.json()
                if data.get("status") == "1":
                    result = data["result"]
                    return {
                        "low": float(result.get("SafeGasPrice", 0.0)),
                        "medium": float(result.get("ProposeGasPrice", 0.0)),
                        "high": float(result.get("FastGasPrice", 0.0)),
                    }
                else:
                    logger.warning(f"Etherscan API error for gas oracle: {data.get('message', 'No message')}")
        except aiohttp.ClientError as e:
            logger.error(f"Network or client error fetching gas oracle: {e}")
        except ValueError as e: # Catch JSON decoding errors
            logger.error(f"JSON decoding error fetching gas oracle: {e}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred while fetching gas oracle: {e}")
        return None

    async def get_full_report(self, address: str) -> Dict[str, Any]:
        """
        Формирует сводный отчет по указанному Ethereum-адресу,
        включающий баланс ETH, количество транзакций и текущие цены на газ.
        """
        balance = await self.get_eth_balance(address)
        tx_count = await self.get_transaction_count(address)
        gas = await self.get_gas_oracle()
        return {
            "balance_eth": balance,
            "transaction_count": tx_count,
            "gas_prices": gas,
        }