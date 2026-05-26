"""On-Chain Analyzer – async Ethereum data analysis via Etherscan API."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any, Optional

import aiohttp

logger = logging.getLogger(__name__)


class OnChainAnalyzer:
    """Analyze Ethereum wallet data using the Etherscan API."""

    BASE_URL = "https://api.etherscan.io/api"
    DEFAULT_TIMEOUT = 10.0
    DEFAULT_TX_LIMIT = 100
    MAX_TX_LIMIT = 1_000

    ETH_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")

    def __init__(self, api_key: str = "") -> None:
        if not isinstance(api_key, str):
            raise TypeError("api_key must be a string")

        self.api_key = api_key.strip() or str(os.getenv("ETHERSCAN_API_KEY", "") or "").strip()
        self.session: Optional[aiohttp.ClientSession] = None

        if not self.api_key:
            logger.warning(
                "Etherscan API key is not provided. Requests may be rate-limited or fail."
            )

    def __repr__(self) -> str:
        return f"OnChainAnalyzer(api_key={'<configured>' if self.api_key else '<none>'})"

    async def __aenter__(self) -> OnChainAnalyzer:
        await self._ensure_session()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        await self.close()

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Return an active aiohttp session."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.DEFAULT_TIMEOUT)
            self.session = aiohttp.ClientSession(timeout=timeout)
            logger.debug("aiohttp ClientSession created for OnChainAnalyzer.")
        return self.session

    async def close(self) -> None:
        """Close the internal aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.debug("aiohttp session closed for OnChainAnalyzer.")
        self.session = None

    async def _make_etherscan_request(
        self,
        params: dict[str, str | int],
        *,
        allow_empty_result: bool = False,
    ) -> Optional[dict[str, Any]]:
        """Execute an Etherscan API request and return decoded JSON on success."""
        if not isinstance(params, dict):
            raise TypeError("params must be a dictionary")

        session = await self._ensure_session()

        request_params: dict[str, str | int] = dict(params)
        if self.api_key:
            request_params["apikey"] = self.api_key

        try:
            async with session.get(self.BASE_URL, params=request_params) as response:
                response.raise_for_status()
                data = await response.json(content_type=None)

            if not isinstance(data, dict):
                logger.warning("Etherscan returned non-object JSON: %r", type(data))
                return None

            status = str(data.get("status", ""))
            message = str(data.get("message", ""))
            result = data.get("result")

            if status == "1":
                return data

            if allow_empty_result and status == "0" and message.lower() == "no transactions found":
                return data

            logger.warning(
                "Etherscan API error: params=%s status=%s message=%s result=%s",
                self._safe_log_params(request_params),
                status,
                message,
                str(result)[:300],
            )
            return None

        except aiohttp.ClientError as exc:
            logger.warning(
                "Network/client error during Etherscan request params=%s: %s",
                self._safe_log_params(request_params),
                exc,
            )
        except (ValueError, TypeError) as exc:
            logger.warning(
                "JSON/response parsing error during Etherscan request params=%s: %s",
                self._safe_log_params(request_params),
                exc,
            )
        except Exception as exc:
            logger.exception(
                "Unexpected Etherscan request error params=%s: %s",
                self._safe_log_params(request_params),
                exc,
            )

        return None

    async def get_eth_balance(self, address: str) -> Optional[float]:
        """Return ETH balance for an Ethereum address, or None on failure."""
        clean_address = self._clean_eth_address(address)
        if clean_address is None:
            logger.warning("Invalid Ethereum address for balance lookup: %r", address)
            return None

        data = await self._make_etherscan_request(
            {
                "module": "account",
                "action": "balance",
                "address": clean_address,
                "tag": "latest",
            }
        )

        if not data or "result" not in data:
            return None

        try:
            return int(str(data["result"])) / 1e18
        except (ValueError, TypeError) as exc:
            logger.warning(
                "Failed to parse ETH balance for address=%s result=%r: %s",
                clean_address,
                data.get("result"),
                exc,
            )
            return None

    async def get_transaction_count(self, address: str, limit: int = DEFAULT_TX_LIMIT) -> Optional[int]:
        """Return count of recent normal transactions fetched from Etherscan."""
        clean_address = self._clean_eth_address(address)
        if clean_address is None:
            logger.warning("Invalid Ethereum address for transaction count: %r", address)
            return None

        safe_limit = self._normalize_limit(limit)

        data = await self._make_etherscan_request(
            {
                "module": "account",
                "action": "txlist",
                "address": clean_address,
                "startblock": 0,
                "endblock": 99999999,
                "page": 1,
                "offset": safe_limit,
                "sort": "desc",
            },
            allow_empty_result=True,
        )

        if not data:
            return None

        result = data.get("result")

        if data.get("status") == "0" and str(data.get("message", "")).lower() == "no transactions found":
            return 0

        if isinstance(result, list):
            return len(result)

        logger.warning("Etherscan txlist returned non-list result for %s: %r", clean_address, result)
        return None

    async def get_gas_oracle(self) -> Optional[dict[str, float]]:
        """Return current gas prices in Gwei as low/medium/high."""
        data = await self._make_etherscan_request(
            {
                "module": "gastracker",
                "action": "gasoracle",
            }
        )

        if not data or not isinstance(data.get("result"), dict):
            return None

        result = data["result"]

        try:
            return {
                "low": self._safe_float(result.get("SafeGasPrice"), 0.0),
                "medium": self._safe_float(result.get("ProposeGasPrice"), 0.0),
                "high": self._safe_float(result.get("FastGasPrice"), 0.0),
            }
        except Exception as exc:
            logger.warning("Failed to parse gas oracle data %r: %s", result, exc)
            return None

    async def get_full_report(self, address: str, tx_limit: int = DEFAULT_TX_LIMIT) -> dict[str, Any]:
        """Return balance, recent transaction count, and gas prices for an address."""
        clean_address = self._clean_eth_address(address)
        if clean_address is None:
            logger.warning("Invalid Ethereum address for full report: %r", address)
            return {
                "address": address,
                "valid_address": False,
                "balance_eth": None,
                "transaction_count": None,
                "gas_prices": None,
            }

        safe_limit = self._normalize_limit(tx_limit)

        balance, tx_count, gas = await asyncio.gather(
            self.get_eth_balance(clean_address),
            self.get_transaction_count(clean_address, safe_limit),
            self.get_gas_oracle(),
            return_exceptions=True,
        )

        return {
            "address": clean_address,
            "valid_address": True,
            "balance_eth": None if isinstance(balance, Exception) else balance,
            "transaction_count": None if isinstance(tx_count, Exception) else tx_count,
            "gas_prices": None if isinstance(gas, Exception) else gas,
        }

    @classmethod
    def _clean_eth_address(cls, address: str) -> Optional[str]:
        if not isinstance(address, str):
            return None

        clean_address = address.strip()
        if not cls.ETH_ADDRESS_RE.match(clean_address):
            return None

        return clean_address

    @classmethod
    def _normalize_limit(cls, limit: int) -> int:
        try:
            safe_limit = int(limit)
        except (TypeError, ValueError):
            safe_limit = cls.DEFAULT_TX_LIMIT

        return max(1, min(safe_limit, cls.MAX_TX_LIMIT))

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_log_params(params: dict[str, str | int]) -> dict[str, str | int]:
        safe_params = dict(params)
        if "apikey" in safe_params:
            safe_params["apikey"] = "<redacted>"
        return safe_params