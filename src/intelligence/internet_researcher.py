# src/intelligence/internet_researcher.py
"""
Internet Researcher – собирает внешние данные (новости, ончейн) и сохраняет в память роя.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import aiohttp

logger = logging.getLogger(__name__)

class InternetResearcher:
    """Асинхронный сборщик внешних данных для контекста LLM."""

    def __init__(self, memory_api=None):
        self.memory_api = memory_api
        self.session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def fetch_crypto_news(self, limit: int = 5) -> list[Dict[str, Any]]:
        """Бесплатный RSS крипто‑новостей (CoinDesk). Возвращает список заголовков."""
        await self._ensure_session()
        url = "https://www.coindesk.com/arc/outboundfeeds/v2/headlines/?outputType=json&numHeadlines=5"
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    logger.warning(f"News fetch returned {resp.status}")
                    return []
                data = await resp.json()
                headlines = data.get("headlines", [])[:limit]
                return [
                    {
                        "title": h.get("title", ""),
                        "url": h.get("url", ""),
                        "published": h.get("published", ""),
                        "source": "CoinDesk",
                    }
                    for h in headlines
                ]
        except Exception as e:
            logger.error(f"News fetch failed: {e}")
            return []

    async def fetch_onchain_balance(self, address: str, api_key: str = "") -> Optional[float]:
        """
        Запрашивает баланс ETH через Etherscan API (бесплатно до 5 запросов/сек).
        api_key нужен только для Mainnet; для тестов можно оставить пустым.
        """
        await self._ensure_session()
        url = (
            f"https://api.etherscan.io/api"
            f"?module=account&action=balance&address={address}&tag=latest"
        )
        if api_key:
            url += f"&apikey={api_key}"
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                if data.get("status") == "1":
                    # баланс в wei, переводим в ETH
                    return int(data["result"]) / 1e18
        except Exception as e:
            logger.error(f"Onchain balance fetch failed: {e}")
        return None

    async def gather_context(self, eth_address: Optional[str] = None) -> str:
        """
        Основной метод: собирает все доступные внешние данные и возвращает строку
        для подстановки в промпт LLM.
        """
        parts = []
        # Новости
        news = await self.fetch_crypto_news(limit=3)
        if news:
            headlines = "\n".join(f"- {n['title']} ({n['url']})" for n in news)
            parts.append(f"Latest crypto news headlines:\n{headlines}")

        # Ончейн
        if eth_address:
            balance = await self.fetch_onchain_balance(eth_address)
            if balance is not None:
                parts.append(f"ETH balance of {eth_address}: {balance:.4f} ETH")

        context = "\n\n".join(parts)

        # Сохраняем в память, если доступна
        if self.memory_api:
            from src.memory.local_memory import MemoryRecord
            record = MemoryRecord(
                id="",
                kind="fact",
                scope="local",
                payload={
                    "source": "internet_researcher",
                    "context": context,
                    "news_count": len(news),
                    "balance": balance if eth_address else None,
                },
                confidence=0.8,
                priority=10,
            )
            await self.memory_api.remember(record)

        return context if context else "No external data available."