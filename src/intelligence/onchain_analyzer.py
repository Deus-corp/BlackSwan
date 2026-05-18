# src/intelligence/onchain_analyzer.py
"""
On-Chain Analyzer – расширенный анализ блокчейн-данных через Etherscan API.
Предоставляет: баланс ETH, историю транзакций, газ, активность кошелька.
"""
import asyncio
import logging
from typing import Optional, Dict, Any, List, Union
import aiohttp

logger = logging.getLogger(__name__)

class OnChainAnalyzer:
    """
    Класс для анализа данных блокчейна Ethereum с использованием Etherscan API.
    Предоставляет методы для получения баланса ETH, количества транзакций,
    цен на газ и полного отчета по адресу.

    Использует aiohttp.ClientSession для асинхронных запросов и поддерживает
    работу как контекстный менеджер (async with).
    """
    BASE_URL: str = "https://api.etherscan.io/api"
    DEFAULT_TIMEOUT: float = 10.0 # seconds

    def __init__(self, api_key: str = ""):
        """
        Инициализирует анализатор блокчейна.

        Args:
            api_key: Ключ API Etherscan. Оставьте пустым для использования без ключа (ограниченные лимиты).
        """
        self.api_key: str = api_key
        self.session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self) -> None:
        """
        Гарантирует, что сессия aiohttp.ClientSession активна.
        Если сессия не существует, она будет создана.
        """
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def __aenter__(self) -> "OnChainAnalyzer":
        """
        Инициализирует асинхронный контекстный менеджер.
        Создает сессию aiohttp.ClientSession.
        """
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Выходит из асинхронного контекстного менеджера.
        Закрывает сессию aiohttp.ClientSession.
        """
        await self.close()

    async def close(self) -> None:
        """
        Закрывает текущую сессию aiohttp.ClientSession, если она активна.
        """
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
            logger.debug("aiohttp session closed.")

    async def _make_etherscan_request(self, params: Dict[str, Union[str, int]]) -> Optional[Dict[str, Any]]:
        """
        Приватный метод для выполнения запросов к Etherscan API.
        Обрабатывает общие ошибки сети и API.

        Args:
            params: Словарь параметров запроса для Etherscan API.

        Returns:
            Словарь с результатом API или None в случае ошибки.
        """
        await self._ensure_session()
        
        # Добавляем ключ API, если он предоставлен
        if self.api_key:
            params["apikey"] = self.api_key

        try:
            async with self.session.get(
                self.BASE_URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=self.DEFAULT_TIMEOUT)
            ) as resp:
                resp.raise_for_status()  # Вызывает исключение для HTTP-ошибок (4xx или 5xx)
                data = await resp.json()

                if data.get("status") == "1":
                    return data
                else:
                    message: str = data.get("message", "No message provided")
                    error_result: str = data.get("result", "No result info")
                    logger.warning(
                        f"Etherscan API returned an error for parameters {params}: "
                        f"Message: {message}, Result: {error_result}"
                    )
                    return None
        except aiohttp.ClientError as e:
            logger.error(f"Network or client error during Etherscan request for {params}: {e}")
        except ValueError as e:  # Catch JSON decoding errors
            logger.error(f"JSON decoding error during Etherscan request for {params}: {e}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred during Etherscan request for {params}: {e}")
        return None

    async def get_eth_balance(self, address: str) -> Optional[float]:
        """
        Получает баланс ETH для указанного адреса.

        Args:
            address: Ethereum-адрес.

        Returns:
            Баланс ETH в виде float или None в случае ошибки.
        """
        params: Dict[str, Union[str, int]] = {
            "module": "account",
            "action": "balance",
            "address": address,
            "tag": "latest"
        }
        data = await self._make_etherscan_request(params)
        if data and "result" in data:
            try:
                # Etherscan возвращает баланс в Wei в виде строки
                return int(data["result"]) / 1e18
            except (ValueError, TypeError) as e:
                logger.error(f"Failed to parse balance for {address}: {data['result']} - {e}")
        return None

    async def get_transaction_count(self, address: str) -> Optional[int]:
        """
        Получает количество транзакций для оценки активности кошелька.
        Примечание: Etherscan API txlist с offset=1 возвращает только 1 транзакцию (если есть).
        Текущая логика возвращает 1, если есть хотя бы одна транзакция, или 0.

        Args:
            address: Ethereum-адрес.

        Returns:
            Количество транзакций (0 или 1) в виде int или None в случае ошибки.
        """
        params: Dict[str, Union[str, int]] = {
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": 0,
            "endblock": 99999999,
            "page": 1,
            "offset": 1, # Fetch only one transaction to check for activity
            "sort": "desc"
        }
        data = await self._make_etherscan_request(params)
        if data and "result" in data:
            # Etherscan возвращает список транзакций. Если список не пуст, значит, транзакции есть.
            return len(data["result"])
        return None

    async def get_gas_oracle(self) -> Optional[Dict[str, float]]:
        """
        Получает текущие цены газа (Safe, Propose, Fast) в Gwei.

        Returns:
            Словарь с ценами газа {"low": ..., "medium": ..., "high": ...}
            или None в случае ошибки.
        """
        params: Dict[str, Union[str, int]] = {
            "module": "gastracker",
            "action": "gasoracle"
        }
        data = await self._make_etherscan_request(params)
        if data and "result" in data:
            result = data["result"]
            try:
                return {
                    "low": float(result.get("SafeGasPrice", 0.0)),
                    "medium": float(result.get("ProposeGasPrice", 0.0)),
                    "high": float(result.get("FastGasPrice", 0.0)),
                }
            except (ValueError, TypeError) as e:
                logger.error(f"Failed to parse gas oracle data: {result} - {e}")
        return None

    async def get_full_report(self, address: str) -> Dict[str, Any]:
        """
        Формирует сводный отчет по указанному Ethereum-адресу,
        включающий баланс ETH, количество транзакций и текущие цены на газ.

        Args:
            address: Ethereum-адрес.

        Returns:
            Словарь, содержащий balance_eth (Optional[float]),
            transaction_count (Optional[int]) и gas_prices (Optional[Dict[str, float]]).
        """
        # Выполняем запросы параллельно для повышения эффективности
        balance, tx_count, gas = await asyncio.gather(
            self.get_eth_balance(address),
            self.get_transaction_count(address),
            self.get_gas_oracle()
        )
        return {
            "balance_eth": balance,
            "transaction_count": tx_count,
            "gas_prices": gas,
        }