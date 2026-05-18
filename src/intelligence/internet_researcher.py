# src/intelligence/internet_researcher.py
"""
Internet Researcher – collects external data (news, on-chain) and stores it in the swarm's memory.
Includes simple sentiment analysis and on-chain reports via Etherscan API.
"""
import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional

import aiohttp
from swarm_config import config

logger = logging.getLogger(__name__)


class InternetResearcher:
    """
    Asynchronous external data collector for LLM context.
    Collects external data such as news and on-chain information asynchronously
    and prepares it for LLM context.
    """

    def __init__(self, memory_api: Optional[Any] = None) -> None:
        """
        Initializes the InternetResearcher.

        Args:
            memory_api (Optional[Any]): An optional API for storing memory records.
                                         Expected to have an async 'remember' method, e.g.,
                                         an instance of LocalMemory or similar, that accepts a MemoryRecord.
        """
        self.memory_api: Optional[Any] = memory_api
        self.session: Optional[aiohttp.ClientSession] = None
        # Etherscan API key (free, obtained from etherscan.io)
        # Using get_secret_value() for Pydantic SecretStr handling, ensuring safe access.
        self.etherscan_api_key: str = config.security.etherscan_api_key.get_secret_value() \
            if config.security.etherscan_api_key else ""

    async def _ensure_session(self) -> None:
        """
        Ensures that an aiohttp client session is active and not closed.
        If no session exists or if it's closed, a new one is created.
        """
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def close(self) -> None:
        """
        Closes the aiohttp client session if it's active and not already closed.
        """
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    @staticmethod
    def _simple_sentiment(text: str) -> float:
        """
        Performs a primitive sentiment analysis on a given text: returns a score from -1 (negative) to +1 (positive).
        It counts occurrences of predefined positive and negative keywords (case-insensitive) in the text.

        Args:
            text (str): The input text to analyze.

        Returns:
            float: A sentiment score between -1.0 and 1.0. Returns 0.0 if no relevant words are found.
        """
        positive_words: List[str] = [
            "bullish", "surge", "rally", "upgrade", "adoption", "partnership",
            "growth", "profit", "breakthrough", "green", "higher", "gain",
            "support", "approve", "launch", "milestone", "innovation", "expansion",
            "strong", "up", "positive", "success"
        ]
        negative_words: List[str] = [
            "crash", "hack", "ban", "lawsuit", "sell-off", "decline", "bearish",
            "downturn", "loss", "fud", "warning", "investigation", "delay",
            "shutdown", "volatility", "drop", "fall", "liquidation", "scam",
            "exploit", "down", "negative", "failure"
        ]
        text_lower: str = text.lower()
        pos_score: int = sum(1 for w in positive_words if w in text_lower)
        neg_score: int = sum(1 for w in negative_words if w in text_lower)
        total: int = pos_score + neg_score
        return 0.0 if total == 0 else (pos_score - neg_score) / total

    async def fetch_crypto_news(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Fetches free crypto news headlines from CoinDesk RSS feed.

        Note: The CoinDesk API URL currently hardcodes numHeadlines=5, so the 'limit' parameter
        will not fetch more than 5 headlines from the source, even if a higher limit is requested.
        The `limit` parameter is still applied locally to the fetched headlines.

        Args:
            limit (int): The maximum number of news headlines to fetch.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing a news headline
                                  with title, URL, publication date, source, and sentiment.
                                  Returns an empty list on failure or if no news is found.
        """
        await self._ensure_session()
        # CoinDesk API currently hardcodes numHeadlines=5
        url: str = "https://www.coindesk.com/arc/outboundfeeds/v2/headlines/?outputType=json&numHeadlines=5" 
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                resp.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
                data: Dict[str, Any] = await resp.json()
                # Apply local slicing to respect the `limit` parameter, even if CoinDesk returned more.
                headlines: List[Dict[str, Any]] = data.get("headlines", [])[:limit]
                enriched: List[Dict[str, Any]] = []
                for h in headlines:
                    title: str = h.get("title", "")
                    enriched.append({
                        "title": title,
                        "url": h.get("url", ""),
                        "published": h.get("published", ""),
                        "source": "CoinDesk",
                        "sentiment": self._simple_sentiment(title),
                    })
                return enriched
        except aiohttp.ClientError as e:
            logger.error(f"News fetch failed due to client error: {e}")
            return []
        except Exception as e:
            logger.error(f"News fetch failed due to unexpected error: {e}")
            return []

    # ---------- On-chain methods ----------

    async def fetch_onchain_balance(self, address: str) -> Optional[float]:
        """
        Queries the ETH balance for a given Ethereum address via Etherscan API.

        Args:
            address (str): The Ethereum address to query.

        Returns:
            Optional[float]: The ETH balance in Ether, or None if the fetch fails or address is invalid.
        """
        await self._ensure_session()
        url: str = (
            f"https://api.etherscan.io/api"
            f"?module=account&action=balance&address={address}&tag=latest"
        )
        if self.etherscan_api_key:
            url += f"&apikey={self.etherscan_api_key}"
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                resp.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
                data: Dict[str, Any] = await resp.json()
                if data.get("status") == "1" and "result" in data:
                    return int(data["result"]) / 1e18 # Convert wei to ETH
                else:
                    logger.warning(
                        f"Etherscan balance API returned status {data.get('status')} "
                        f"or missing result for address {address}: {data.get('message', 'No message')}"
                    )
        except aiohttp.ClientError as e:
            logger.error(f"Onchain balance fetch failed for address {address} due to client error: {e}")
        except (ValueError, TypeError):
            logger.error(
                f"Could not convert Etherscan balance result to int/float for address {address}. "
                f"Result: {data.get('result') if 'data' in locals() else 'N/A'}"
            )
        except Exception as e:
            logger.error(f"Onchain balance fetch failed for address {address} due to unexpected error: {e}")
        return None

    async def fetch_transaction_count(self, address: str) -> Optional[int]:
        """
        Fetches a count of recent normal transactions for an Ethereum address via Etherscan API.
        Note: Etherscan's public API does not provide a direct total transaction count.
        This method fetches up to 100 recent transactions and returns their count
        as an indicator of activity. To get a precise total count, multiple API calls would be needed.

        Args:
            address (str): The Ethereum address to query.

        Returns:
            Optional[int]: The number of transactions fetched (up to 100), or None if the fetch fails.
        """
        await self._ensure_session()
        # Etherscan's txlist API: 'offset' defines items per page, 'page' is page number.
        # Setting offset to 100 to retrieve up to 100 recent transactions for activity assessment.
        url: str = (
            f"https://api.etherscan.io/api"
            f"?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&page=1&offset=100&sort=desc"
        )
        if self.etherscan_api_key:
            url += f"&apikey={self.etherscan_api_key}"
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                resp.raise_for_status()
                data: Dict[str, Any] = await resp.json()
                if data.get("status") == "1" and isinstance(data.get("result"), list):
                    return len(data["result"])
                else:
                    logger.warning(
                        f"Etherscan transaction count API returned status {data.get('status')} "
                        f"or unexpected result type for address {address}: {data.get('message', 'No message')}"
                    )
        except aiohttp.ClientError as e:
            logger.error(f"Transaction count fetch failed for address {address} due to client error: {e}")
        except Exception as e:
            logger.error(f"Transaction count fetch failed for address {address} due to unexpected error: {e}")
        return None

    async def fetch_gas_oracle(self) -> Optional[Dict[str, float]]:
        """
        Fetches current Ethereum gas prices (Safe, Propose, Fast) via Etherscan API.
        These are typically mapped to Low, Medium, High.

        Returns:
            Optional[Dict[str, float]]: A dictionary with 'low', 'medium', 'high' gas prices in Gwei,
                                        or None if the fetch fails.
        """
        await self._ensure_session()
        url: str = (
            f"https://api.etherscan.io/api"
            f"?module=gastracker&action=gasoracle"
        )
        if self.etherscan_api_key:
            url += f"&apikey={self.etherscan_api_key}"
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                resp.raise_for_status()
                data: Dict[str, Any] = await resp.json()
                if data.get("status") == "1" and "result" in data:
                    result = data["result"]
                    return {
                        "low": float(result.get("SafeGasPrice", 0.0)),
                        "medium": float(result.get("ProposeGasPrice", 0.0)),
                        "high": float(result.get("FastGasPrice", 0.0)),
                    }
                else:
                    logger.warning(
                        f"Etherscan gas oracle API returned status {data.get('status')} "
                        f"or missing result: {data.get('message', 'No message')}"
                    )
        except aiohttp.ClientError as e:
            logger.error(f"Gas fetch failed due to client error: {e}")
        except (ValueError, TypeError):
            logger.error(
                f"Could not convert Etherscan gas result to float. "
                f"Result: {data.get('result') if 'data' in locals() else 'N/A'}"
            )
        except Exception as e:
            logger.error(f"Gas fetch failed due to unexpected error: {e}")
        return None

    # ---------- Main context gathering method ----------

    async def gather_context(self, eth_address: Optional[str] = None) -> str:
        """
        Gathers all available external data (news, on-chain) and returns a formatted string
        suitable for insertion into an LLM prompt. Also stores the gathered data in memory
        if `memory_api` is available.

        Args:
            eth_address (Optional[str]): An optional Ethereum address for on-chain data collection.

        Returns:
            str: A formatted string containing all gathered external context. Returns "No external data available."
                 if no data could be fetched.
        """
        parts: List[str] = []
        news_count: int = 0
        balance: Optional[float] = None
        tx_count: Optional[int] = None
        gas_prices: Optional[Dict[str, float]] = None

        # Fetch and format news with sentiment
        news: List[Dict[str, Any]] = await self.fetch_crypto_news(limit=3)
        if news:
            news_count = len(news)
            lines: List[str] = []
            for n in news:
                sentiment_str: str = "😊 Positive" if n['sentiment'] > 0 else "😞 Negative" if n['sentiment'] < 0 else "😐 Neutral"
                lines.append(f"- {sentiment_str}: {n['title']} (Source: {n['source']}, Published: {n['published']})")
            parts.append("Latest crypto news headlines:\n" + "\n".join(lines))
        else:
            parts.append("Latest crypto news headlines: Not available.")

        # Fetch and format on-chain analysis if an Ethereum address is provided
        if eth_address:
            parts.append(f"\nOn-chain data for address: {eth_address}")

            balance = await self.fetch_onchain_balance(eth_address)
            if balance is not None:
                parts.append(f"  ETH balance: {balance:.4f} ETH")
            else:
                parts.append("  ETH balance: Not available")

            tx_count = await self.fetch_transaction_count(eth_address)
            if tx_count is not None:
                parts.append(f"  Recent transaction count (up to 100): {tx_count}")
            else:
                parts.append("  Transaction count: Not available")

            gas_prices = await self.fetch_gas_oracle()
            if gas_prices:
                parts.append(
                    f"  Current Gas prices (Low/Med/High): "
                    f"{gas_prices['low']:.2f}/{gas_prices['medium']:.2f}/{gas_prices['high']:.2f} Gwei"
                )
            else:
                parts.append("  Gas prices: Not available")
        else:
            parts.append("\nOn-chain data: No Ethereum address provided.")

        context: str = "\n\n".join(parts) if parts else "No external data available."

        # Save gathered data to memory if `memory_api` is provided
        if self.memory_api:
            # Deferred import to avoid potential circular dependencies and only if needed
            from src.memory.local_memory import MemoryRecord # Assuming MemoryRecord is defined here

            record: MemoryRecord = MemoryRecord(
                id=f"internet-researcher-{time.time()}", # Generate a unique ID for the memory record
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
                confidence=0.8, # Placeholder confidence
                priority=10,    # Placeholder priority
            )
            try:
                await self.memory_api.remember(record)
            except Exception as e:
                logger.error(f"Failed to store internet research record in memory: {e}")

        return context
