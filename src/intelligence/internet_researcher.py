"""Internet Researcher – async external market/on-chain context collector."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from typing import Any, Optional

import aiohttp

from swarm_config import config

logger = logging.getLogger(__name__)


class InternetResearcher:
    """Collect crypto news and optional Ethereum on-chain context for LLM prompts."""

    DEFAULT_API_TIMEOUT: float = 10.0
    DEFAULT_NEWS_LIMIT: int = 3
    MAX_NEWS_LIMIT: int = 10

    COINDESK_HEADLINES_URL: str = (
        "https://www.coindesk.com/arc/outboundfeeds/v2/headlines/"
    )
    ETHERSCAN_API_URL: str = "https://api.etherscan.io/api"

    POSITIVE_WORDS: frozenset[str] = frozenset(
        {
            "bullish",
            "surge",
            "rally",
            "upgrade",
            "adoption",
            "partnership",
            "growth",
            "profit",
            "breakthrough",
            "green",
            "higher",
            "gain",
            "support",
            "approve",
            "approval",
            "launch",
            "milestone",
            "innovation",
            "expansion",
            "strong",
            "positive",
            "success",
            "optimistic",
            "recovery",
            "boom",
        }
    )
    NEGATIVE_WORDS: frozenset[str] = frozenset(
        {
            "crash",
            "hack",
            "ban",
            "lawsuit",
            "sell-off",
            "decline",
            "bearish",
            "downturn",
            "loss",
            "fud",
            "warning",
            "investigation",
            "delay",
            "shutdown",
            "volatility",
            "drop",
            "fall",
            "liquidation",
            "scam",
            "exploit",
            "negative",
            "failure",
            "pessimistic",
            "recession",
            "slump",
        }
    )

    ETH_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")

    def __init__(self, memory_api: Optional[Any] = None) -> None:
        self.memory_api = memory_api
        self.session: Optional[aiohttp.ClientSession] = None
        self.etherscan_api_key = self._read_etherscan_key()

        if not self.etherscan_api_key:
            logger.warning(
                "Etherscan API key is not configured; on-chain calls may be rate-limited."
            )

    async def __aenter__(self) -> InternetResearcher:
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Return an active aiohttp session."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.DEFAULT_API_TIMEOUT)
            self.session = aiohttp.ClientSession(timeout=timeout)
            logger.debug("InternetResearcher aiohttp ClientSession created.")
        return self.session

    async def close(self) -> None:
        """Close the internal aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.debug("InternetResearcher aiohttp ClientSession closed.")
        self.session = None

    @classmethod
    def _simple_sentiment(cls, text: str) -> float:
        """Return primitive keyword sentiment from -1.0 to +1.0."""
        words = re.findall(r"[a-zA-Z][a-zA-Z-]*", str(text or "").lower())
        if not words:
            return 0.0

        word_set = set(words)
        pos_score = sum(1 for word in cls.POSITIVE_WORDS if word in word_set)
        neg_score = sum(1 for word in cls.NEGATIVE_WORDS if word in word_set)
        total = pos_score + neg_score

        return 0.0 if total == 0 else (pos_score - neg_score) / total

    async def fetch_crypto_news(self, limit: int = DEFAULT_NEWS_LIMIT) -> list[dict[str, Any]]:
        """Fetch recent crypto news headlines."""
        safe_limit = max(0, min(int(limit), self.MAX_NEWS_LIMIT))
        if safe_limit == 0:
            return []

        params = {
            "outputType": "json",
            "numHeadlines": str(min(max(safe_limit, 5), self.MAX_NEWS_LIMIT)),
        }

        try:
            data = await self._get_json(self.COINDESK_HEADLINES_URL, params=params)
        except Exception as exc:
            logger.warning("News fetch failed: %s", exc)
            return []

        headlines_raw = data.get("headlines", []) if isinstance(data, dict) else []
        if not isinstance(headlines_raw, list):
            return []

        enriched: list[dict[str, Any]] = []
        for item in headlines_raw[:safe_limit]:
            if not isinstance(item, dict):
                continue

            title = str(item.get("title", "") or "").strip()
            if not title:
                continue

            enriched.append(
                {
                    "title": title,
                    "url": str(item.get("url", "") or ""),
                    "published": str(item.get("published", "") or item.get("date", "") or ""),
                    "source": "CoinDesk",
                    "sentiment": self._simple_sentiment(title),
                }
            )

        return enriched

    async def fetch_onchain_balance(self, address: str) -> Optional[float]:
        """Fetch ETH balance for an Ethereum address using Etherscan."""
        clean_address = self._clean_eth_address(address)
        if clean_address is None:
            logger.warning("Invalid Ethereum address for balance lookup: %r", address)
            return None

        params = {
            "module": "account",
            "action": "balance",
            "address": clean_address,
            "tag": "latest",
        }
        self._add_etherscan_key(params)

        try:
            data = await self._get_json(self.ETHERSCAN_API_URL, params=params)
            if data.get("status") == "1" and "result" in data:
                return int(str(data["result"])) / 1e18

            logger.warning(
                "Etherscan balance API returned status=%s message=%s address=%s",
                data.get("status"),
                data.get("message"),
                clean_address,
            )
        except Exception as exc:
            logger.warning("On-chain balance fetch failed for %s: %s", clean_address, exc)

        return None

    async def fetch_transaction_count(self, address: str) -> Optional[int]:
        """Fetch count of recent normal transactions for an Ethereum address."""
        clean_address = self._clean_eth_address(address)
        if clean_address is None:
            logger.warning("Invalid Ethereum address for tx count lookup: %r", address)
            return None

        params = {
            "module": "account",
            "action": "txlist",
            "address": clean_address,
            "startblock": "0",
            "endblock": "99999999",
            "page": "1",
            "offset": "100",
            "sort": "desc",
        }
        self._add_etherscan_key(params)

        try:
            data = await self._get_json(self.ETHERSCAN_API_URL, params=params)
            result = data.get("result")

            if data.get("status") == "1" and isinstance(result, list):
                return len(result)

            if data.get("status") == "0" and str(data.get("message", "")).lower() == "no transactions found":
                return 0

            logger.warning(
                "Etherscan txlist API returned status=%s message=%s address=%s",
                data.get("status"),
                data.get("message"),
                clean_address,
            )
        except Exception as exc:
            logger.warning("Transaction count fetch failed for %s: %s", clean_address, exc)

        return None

    async def fetch_gas_oracle(self) -> Optional[dict[str, float]]:
        """Fetch Ethereum gas prices in Gwei from Etherscan."""
        params = {
            "module": "gastracker",
            "action": "gasoracle",
        }
        self._add_etherscan_key(params)

        try:
            data = await self._get_json(self.ETHERSCAN_API_URL, params=params)
            result = data.get("result")

            if data.get("status") == "1" and isinstance(result, dict):
                return {
                    "low": self._safe_float(result.get("SafeGasPrice"), 0.0),
                    "medium": self._safe_float(result.get("ProposeGasPrice"), 0.0),
                    "high": self._safe_float(result.get("FastGasPrice"), 0.0),
                }

            logger.warning(
                "Etherscan gas oracle API returned status=%s message=%s",
                data.get("status"),
                data.get("message"),
            )
        except Exception as exc:
            logger.warning("Gas oracle fetch failed: %s", exc)

        return None

    async def gather_context(self, eth_address: Optional[str] = None) -> str:
        """Gather external news and optional on-chain data as an LLM-ready string."""
        news_task = asyncio.create_task(self.fetch_crypto_news(limit=self.DEFAULT_NEWS_LIMIT))

        clean_address = self._clean_eth_address(eth_address) if eth_address else None
        balance_task: Optional[asyncio.Task[Optional[float]]] = None
        tx_count_task: Optional[asyncio.Task[Optional[int]]] = None
        gas_task: Optional[asyncio.Task[Optional[dict[str, float]]]] = None

        if clean_address:
            balance_task = asyncio.create_task(self.fetch_onchain_balance(clean_address))
            tx_count_task = asyncio.create_task(self.fetch_transaction_count(clean_address))
            gas_task = asyncio.create_task(self.fetch_gas_oracle())

        news = await news_task
        balance = await balance_task if balance_task is not None else None
        tx_count = await tx_count_task if tx_count_task is not None else None
        gas_prices = await gas_task if gas_task is not None else None

        context = self._format_context(
            news=news,
            eth_address=eth_address,
            clean_address=clean_address,
            balance=balance,
            tx_count=tx_count,
            gas_prices=gas_prices,
        )

        await self._remember_context(
            context=context,
            news=news,
            eth_address=clean_address or eth_address,
            balance=balance,
            tx_count=tx_count,
            gas_prices=gas_prices,
        )

        return context

    def _format_context(
        self,
        *,
        news: list[dict[str, Any]],
        eth_address: Optional[str],
        clean_address: Optional[str],
        balance: Optional[float],
        tx_count: Optional[int],
        gas_prices: Optional[dict[str, float]],
    ) -> str:
        parts: list[str] = []

        if news:
            lines: list[str] = []
            for item in news:
                sentiment = self._sentiment_label(self._safe_float(item.get("sentiment"), 0.0))
                lines.append(
                    f"- {sentiment}: {item.get('title', '')} "
                    f"(Source: {item.get('source', 'unknown')}, Published: {item.get('published', '')})"
                )
            parts.append("Latest crypto news headlines:\n" + "\n".join(lines))
        else:
            parts.append("Latest crypto news headlines: Not available.")

        if eth_address and clean_address is None:
            parts.append(f"\nOn-chain data for address: {eth_address} (invalid format, skipped).")
        elif clean_address:
            lines = [f"\nOn-chain data for address: {clean_address}"]
            lines.append(
                f"  ETH balance: {balance:.4f} ETH"
                if balance is not None
                else "  ETH balance: Not available"
            )
            lines.append(
                f"  Recent transaction count (up to 100): {tx_count}"
                if tx_count is not None
                else "  Transaction count: Not available"
            )

            if gas_prices:
                lines.append(
                    "  Current gas prices (Low/Med/High): "
                    f"{gas_prices.get('low', 0.0):.2f}/"
                    f"{gas_prices.get('medium', 0.0):.2f}/"
                    f"{gas_prices.get('high', 0.0):.2f} Gwei"
                )
            else:
                lines.append("  Gas prices: Not available")

            parts.append("\n".join(lines))
        else:
            parts.append("\nOn-chain data: No Ethereum address provided.")

        return "\n\n".join(parts) if parts else "No external data available."

    async def _remember_context(
        self,
        *,
        context: str,
        news: list[dict[str, Any]],
        eth_address: Optional[str],
        balance: Optional[float],
        tx_count: Optional[int],
        gas_prices: Optional[dict[str, float]],
    ) -> None:
        if self.memory_api is None:
            return

        remember = getattr(self.memory_api, "remember", None)
        if not callable(remember):
            return

        try:
            from src.memory.local_memory import MemoryRecord
        except ImportError as exc:
            logger.warning("MemoryRecord import failed; skipping memory write: %s", exc)
            return

        record = MemoryRecord(
            id=f"internet-researcher-{time.time():.6f}-{os.urandom(4).hex()}",
            kind="fact",
            scope="external_intelligence",
            payload={
                "source": "internet_researcher",
                "context_string": context,
                "news_data": news,
                "news_count": len(news),
                "eth_address": eth_address,
                "balance": balance,
                "transaction_count": tx_count,
                "gas_prices": gas_prices,
            },
            confidence=0.7,
            priority=10,
        )

        try:
            result = remember(record)
            if asyncio.iscoroutine(result):
                await result
            logger.debug("Stored internet research record in memory: %s", record.id)
        except Exception as exc:
            logger.warning("Failed to store internet research record in memory: %s", exc)

    async def _get_json(self, url: str, *, params: Optional[dict[str, str]] = None) -> dict[str, Any]:
        session = await self._ensure_session()

        async with session.get(url, params=params) as response:
            response.raise_for_status()
            data = await response.json(content_type=None)

        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object from {url}, got {type(data).__name__}")

        return data

    def _add_etherscan_key(self, params: dict[str, str]) -> None:
        if self.etherscan_api_key:
            params["apikey"] = self.etherscan_api_key

    @classmethod
    def _clean_eth_address(cls, address: Optional[str]) -> Optional[str]:
        if not isinstance(address, str):
            return None

        clean_address = address.strip()
        if not cls.ETH_ADDRESS_RE.match(clean_address):
            return None

        return clean_address

    @staticmethod
    def _sentiment_label(score: float) -> str:
        if score > 0:
            return "Positive"
        if score < 0:
            return "Negative"
        return "Neutral"

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _read_etherscan_key() -> str:
        try:
            key = getattr(getattr(config, "security", None), "etherscan_api_key", None)
            if key and hasattr(key, "get_secret_value"):
                return str(key.get_secret_value() or "").strip()
            if key:
                return str(key).strip()
        except Exception:
            pass

        return str(os.environ.get("ETHERSCAN_API_KEY", "") or "").strip()