# src/intelligence/onchain_analyzer.py
"""
On-Chain Analyzer – provides extended blockchain data analysis via Etherscan API.
Offers ETH balance, transaction history, gas prices, and wallet activity.
"""
import asyncio
import logging
from typing import Optional, Dict, Any, List, Union
import aiohttp

logger = logging.getLogger(__name__)

class OnChainAnalyzer:
    """
    Class for analyzing Ethereum blockchain data using the Etherscan API.
    Provides methods to retrieve ETH balance, transaction count, gas prices,
    and a comprehensive report for a given address.

    Utilizes aiohttp.ClientSession for asynchronous requests and supports
    usage as an asynchronous context manager (`async with`).
    """
    BASE_URL: str = "https://api.etherscan.io/api"
    DEFAULT_TIMEOUT: float = 10.0 # seconds for API requests

    def __init__(self, api_key: str = ""):
        """
        Initializes the OnChainAnalyzer.

        Args:
            api_key (str): The Etherscan API key. Leave empty to use without a key
                           (subject to stricter rate limits).
        """
        self.api_key: str = api_key
        self.session: Optional[aiohttp.ClientSession] = None
        if not self.api_key:
            logger.warning("Etherscan API key is not provided. Requests may be heavily rate-limited or fail.")


    async def _ensure_session(self) -> None:
        """
        Ensures that an aiohttp.ClientSession is active.
        If a session does not exist or is closed, a new one is created.
        """
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
            logger.debug("aiohttp ClientSession created for OnChainAnalyzer.")

    async def __aenter__(self) -> "OnChainAnalyzer":
        """
        Initializes the asynchronous context manager.
        Creates an aiohttp.ClientSession.
        """
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type: Optional[type], exc_val: Optional[BaseException], exc_tb: Optional[Any]) -> None:
        """
        Exits the asynchronous context manager.
        Closes the aiohttp.ClientSession.
        """
        await self.close()

    async def close(self) -> None:
        """
        Closes the current aiohttp.ClientSession if it is active and not already closed.
        This should be called to release network resources.
        """
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
            logger.debug("aiohttp session closed for OnChainAnalyzer.")

    async def _make_etherscan_request(self, params: Dict[str, Union[str, int]]) -> Optional[Dict[str, Any]]:
        """
        Private method to execute requests to the Etherscan API.
        Handles common network and API errors.

        Args:
            params (Dict[str, Union[str, int]]): A dictionary of query parameters for the Etherscan API.

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing the API response result, or None in case of an error
                                      or if the API returns an error status.
        """
        await self._ensure_session()
        
        # Add the API key if provided
        request_params = params.copy()
        if self.api_key:
            request_params["apikey"] = self.api_key

        try:
            async with self.session.get(
                self.BASE_URL,
                params=request_params,
                timeout=aiohttp.ClientTimeout(total=self.DEFAULT_TIMEOUT)
            ) as resp:
                resp.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
                data: Dict[str, Any] = await resp.json()

                if data.get("status") == "1":
                    return data
                else:
                    message: str = data.get("message", "No message provided")
                    error_result: str = str(data.get("result", "No result info")) # Convert result to string for logging
                    logger.warning(
                        f"Etherscan API returned an error for parameters {request_params}: "
                        f"Message: {message}, Result: {error_result}"
                        f" (Full response: {data})"
                    )
                    return None
        except aiohttp.ClientError as e:
            logger.error(f"Network or client error during Etherscan request for {request_params}: {e}")
        except ValueError as e:  # Catch JSON decoding errors
            logger.error(f"JSON decoding error during Etherscan request for {request_params}: {e}", exc_info=True)
        except Exception as e:
            logger.exception(f"An unexpected error occurred during Etherscan request for {request_params}: {e}")
        return None

    async def get_eth_balance(self, address: str) -> Optional[float]:
        """
        Retrieves the ETH balance for the specified Ethereum address.

        Args:
            address (str): The Ethereum address (e.g., "0x...").

        Returns:
            Optional[float]: The ETH balance as a float, or None in case of an error
                             or if the address is invalid.
        """
        params: Dict[str, Union[str, int]] = {
            "module": "account",
            "action": "balance",
            "address": address,
            "tag": "latest"
        }
        data: Optional[Dict[str, Any]] = await self._make_etherscan_request(params)
        if data and "result" in data:
            try:
                # Etherscan returns balance in Wei as a string
                return int(data["result"]) / 1e18
            except (ValueError, TypeError) as e:
                logger.error(f"Failed to parse balance for address {address}: '{data['result']}' - {e}", exc_info=True)
        return None

    async def get_transaction_count(self, address: str, limit: int = 100) -> Optional[int]:
        """
        Retrieves a count of recent normal transactions for an Ethereum address.
        Note: Etherscan's public API does not provide a direct total transaction count
        without pagination. This method fetches up to `limit` (default 100) recent transactions
        and returns their count as an indicator of activity.

        Args:
            address (str): The Ethereum address (e.g., "0x...").
            limit (int): The maximum number of recent transactions to fetch to determine activity.
                         The Etherscan API typically has an upper limit for `offset` (e.g., 1000).

        Returns:
            Optional[int]: The number of recent transactions fetched (up to `limit`),
                           or None in case of an error.
        """
        params: Dict[str, Union[str, int]] = {
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": 0,
            "endblock": 99999999, # Max block number
            "page": 1,
            "offset": limit, # Fetch up to 'limit' transactions
            "sort": "desc"
        }
        data: Optional[Dict[str, Any]] = await self._make_etherscan_request(params)
        if data and "result" in data:
            # Etherscan returns a list of transactions. Its length indicates activity.
            if isinstance(data["result"], list):
                return len(data["result"])
            else:
                logger.warning(f"Etherscan txlist API returned non-list result for {address}: {data['result']}")
        return None

    async def get_gas_oracle(self) -> Optional[Dict[str, float]]:
        """
        Retrieves current Ethereum gas prices (Safe, Propose, Fast) in Gwei.
        These typically correspond to Low, Medium, and High priority gas prices.

        Returns:
            Optional[Dict[str, float]]: A dictionary with 'low', 'medium', 'high' gas prices in Gwei,
                                        e.g., `{"low": 20.0, "medium": 25.0, "high": 30.0}`,
                                        or None in case of an error.
        """
        params: Dict[str, Union[str, int]] = {
            "module": "gastracker",
            "action": "gasoracle"
        }
        data: Optional[Dict[str, Any]] = await self._make_etherscan_request(params)
        if data and "result" in data:
            result = data["result"]
            try:
                # Etherscan provides these as strings; convert to float
                return {
                    "low": float(result.get("SafeGasPrice", 0.0)),
                    "medium": float(result.get("ProposeGasPrice", 0.0)),
                    "high": float(result.get("FastGasPrice", 0.0)),
                }
            except (ValueError, TypeError) as e:
                logger.error(f"Failed to parse gas oracle data: {result} - {e}", exc_info=True)
        return None

    async def get_full_report(self, address: str, tx_limit: int = 100) -> Dict[str, Any]:
        """
        Generates a summary report for the specified Ethereum address,
        including ETH balance, recent transaction count, and current gas prices.

        Args:
            address (str): The Ethereum address (e.g., "0x...").
            tx_limit (int): The maximum number of recent transactions to consider for the count.

        Returns:
            Dict[str, Any]: A dictionary containing `balance_eth` (Optional[float]),
                            `transaction_count` (Optional[int]), and `gas_prices` (Optional[Dict[str, float]]).
                            Defaults to None for values that could not be fetched.
        """
        # Execute requests in parallel for efficiency
        balance, tx_count, gas = await asyncio.gather(
            self.get_eth_balance(address),
            self.get_transaction_count(address, tx_limit),
            self.get_gas_oracle()
        )
        return {
            "balance_eth": balance,
            "transaction_count": tx_count,
            "gas_prices": gas,
        }
