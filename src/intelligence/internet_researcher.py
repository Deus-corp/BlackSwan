# src/intelligence/internet_researcher.py
"""
Internet Researcher – собирает внешние данные (новости, ончейн) и сохраняет в память роя.
Включает простой анализ тональности и ончейн-отчёты через Etherscan API.
"""
import asyncio
import logging
import os
from typing import Optional, Dict, Any, List
import aiohttp
from swarm_config import config

logger = logging.getLogger(__name__)


class InternetResearcher:
    """
    Асинхронный сборщик внешних данных для контекста LLM.
    Collects external data such as news and on-chain information asynchronously
    and prepares it for LLM context.
    """

    def __init__(self, memory_api: Optional[Any] = None) -> None:
        """
        Initializes the InternetResearcher.

        Args:
            memory_api (Optional[Any]): An optional API for storing memory records.
                                         Expected to have a 'remember' method.
        """
        self.memory_api = memory_api
        self.session: Optional[aiohttp.ClientSession] = None
        # Etherscan API key (бесплатный, получается на etherscan.io)
        self.etherscan_api_key: str = config.security.etherscan_api_key.get_secret_value() if config.security.etherscan_api_key else ""

    async def _ensure_session(self) -> None:
        """
        Ensures that an aiohttp client session is active.
        If no session exists, a new one is created.
        """
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def close(self) -> None:
        """
        Closes the aiohttp client session if it's active.
        """
        if self.session:
            await self.session.close()
            self.session = None

    @staticmethod
    def _simple_sentiment(text: str) -> float:
        """Примитивный анализ тональности: от -1 (негатив) до +1 (позитив)."""
        positive_words = [
            "bullish", "surge", "rally", "upgrade", "adoption", "partnership",
            "growth", "profit", "breakthrough", "green", "higher", "gain",
            "support", "approve", "launch", "milestone"
        ]
        negative_words = [
            "crash", "hack", "ban", "lawsuit", "sell-off", "decline", "bearish",
            "downturn", "loss", "fud", "warning", "investigation", "delay",
            "shutdown", "volatility", "drop", "fall", "liquidation"
        ]
        text_lower = text.lower()
        pos_score = sum(1 for w in positive_words if w in text_lower)
        neg_score = sum(1 for w in negative_words if w in text_lower)
        total = pos_score + neg_score
        return 0.0 if total == 0 else (pos_score - neg_score) / total

    async def fetch_crypto_news(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Бесплатный RSS крипто‑новостей (CoinDesk). Возвращает список заголовков с тональностью.
        Note: The CoinDesk API URL currently hardcodes numHeadlines=5, so the 'limit' parameter
        will not fetch more than 5 headlines, even if a higher limit is requested.

        Args:
            limit (int): The maximum number of news headlines to fetch.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing a news headline
                                  with title, URL, publication date, source, and sentiment.
        """
        await self._ensure_session()
        url = "https://www.coindesk.com/arc/outboundfeeds/v2/headlines/?outputType=json&numHeadlines=5"
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    logger.warning(f"News fetch returned {resp.status} for URL: {url}")
                    return []
                data = await resp.json()
                headlines = data.get("headlines", [])[:limit] # Slicing ensures 'limit' is respected locally
                enriched = []
                for h in headlines:
                    title = h.get("title", "")
                    enriched.append({
                        "title": title,
                        "url": h.get("url", ""),
                        "published": h.get("published", ""),
                        "source": "CoinDesk",
                        "sentiment": self._simple_sentiment(title),
                    })
                return enriched
        except Exception as e:
            logger.error(f"News fetch failed: {e}")
            return []

    # ---------- Ончейн-методы ----------

    async def fetch_onchain_balance(self, address: str) -> Optional[float]:
        """
        Запрашивает баланс ETH через Etherscan API.

        Args:
            address (str): The Ethereum address to query.

        Returns:
            Optional[float]: The ETH balance in Ether, or None if the fetch fails.
        """
        await self._ensure_session()
        url = (
            f"https://api.etherscan.io/api"
            f"?module=account&action=balance&address={address}&tag=latest"
        )
        if self.etherscan_api_key:
            url += f"&apikey={self.etherscan_api_key}"
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                if data.get("status") == "1":
                    return int(data["result"]) / 1e18 # Convert wei to ETH
        except Exception as e:
            logger.error(f"Onchain balance fetch failed for address {address}: {e}")
        return None

    async def fetch_transaction_count(self, address: str) -> Optional[int]:
        """
        Количество транзакций (для оценки активности).

        Args:
            address (str): The Ethereum address to query.

        Returns:
            Optional[int]: The number of transactions, or None if the fetch fails.
        """
        await self._ensure_session()
        url = (
            f"https://api.etherscan.io/api"
            f"?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&page=1&offset=1&sort=desc"
        )
        if self.etherscan_api_key:
            url += f"&apikey={self.etherscan_api_key}"
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                if data.get("status") == "1":
                    # The API returns a list of transactions, its length is the count
                    return len(data["result"])
        except Exception as e:
            logger.error(f"Transaction count fetch failed for address {address}: {e}")
        return None

    async def fetch_gas_oracle(self) -> Optional[Dict[str, float]]:
        """
        Текущие цены газа (Low/Medium/High).

        Returns:
            Optional[Dict[str, float]]: A dictionary with 'low', 'medium', 'high' gas prices in Gwei,
                                        or None if the fetch fails.
        """
        await self._ensure_session()
        url = (
            f"https://api.etherscan.io/api"
            f"?module=gastracker&action=gasoracle"
        )
        if self.etherscan_api_key:
            url += f"&apikey={self.etherscan_api_key}"
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

    # ---------- Основной метод ----------

    async def gather_context(self, eth_address: Optional[str] = None) -> str:
        """
        Собирает все доступные внешние данные (новости, ончейн) и возвращает строку
        для подстановки в промпт LLM. Также сохраняет собранные данные в память, если memory_api доступен.

        Args:
            eth_address (Optional[str]): An optional Ethereum address for on-chain data collection.

        Returns:
            str: A formatted string containing all gathered external context.
        """
        parts: List[str] = []
        news_count: int = 0
        balance: Optional[float] = None
        tx_count: Optional[int] = None
        gas_prices: Optional[Dict[str, float]] = None

        # Новости с тональностью
        news = await self.fetch_crypto_news(limit=3)
        if news:
            news_count = len(news)
            lines = []
            for n in news:
                sentiment_str = "😊" if n['sentiment'] > 0 else "😞" if n['sentiment'] < 0 else "😐"
                lines.append(f"- {sentiment_str} {n['title']} ({n['url']})")
            parts.append("Latest crypto news headlines:\n" + "\n".join(lines))

        # Ончейн-анализ
        if eth_address:
            balance = await self.fetch_onchain_balance(eth_address)
            if balance is not None:
                parts.append(f"ETH balance of {eth_address}: {balance:.4f} ETH")

            tx_count = await self.fetch_transaction_count(eth_address)
            if tx_count is not None:
                parts.append(f"Transaction count: {tx_count}")

            gas_prices = await self.fetch_gas_oracle()
            if gas_prices:
                parts.append(
                    f"Gas prices (Low/Med/High): "
                    f"{gas_prices['low']}/{gas_prices['medium']}/{gas_prices['high']} Gwei"
                )

        context = "\n\n".join(parts) if parts else "No external data available."

        # Сохраняем в память, если доступна
        if self.memory_api:
            from src.memory.local_memory import MemoryRecord # Deferred import
            record = MemoryRecord(
                id="", # ID will likely be generated by the memory API
                kind="fact",
                scope="local",
                payload={
                    "source": "internet_researcher",
                    "context_string": context, # Storing the full context string for debugging/LLM input
                    "news_count": news_count,
                    "balance": balance,
                    "transaction_count": tx_count,
                    "gas_prices": gas_prices,
                },
                confidence=0.8,
                priority=10,
            )
            await self.memory_api.remember(record)

        return context