"""Async Web3 Sepolia adapter for WETH/USDC swaps through Uniswap V3."""

from __future__ import annotations

import asyncio
import logging
import math
import os
import time
from typing import Any, Optional

from web3 import AsyncWeb3
from web3.contract import Contract
from web3.middleware import ExtraDataToPOAMiddleware
from web3.providers import AsyncHTTPProvider
from web3.types import TxReceipt, Wei

from adapters.nonce_manager import NonceManager
from swarm_config import config

logger = logging.getLogger(__name__)

QUOTER_ADDRESS = "0xd64686fa7549534ecb1b5cdd772d60c3cf02af3c"
ROUTER_ADDRESS = "0x3bFA4769FB09eefC5a80d6E87c3B9C650f7Ae48E"
WETH_ADDRESS = "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14"
USDC_ADDRESS = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"
MULTICALL_ADDRESS = "0xcA11bde05977b3631167028862bE2a173976CA11"

SEPOLIA_CHAIN_ID = 11155111
DEFAULT_SYMBOL = "WETH/USDC"
DEFAULT_POOL_FEE = 500
DEFAULT_SLIPPAGE_BPS = 100
DEFAULT_TX_TIMEOUT_SECONDS = 180

QUOTER_ABI: list[dict[str, Any]] = [
    {
        "inputs": [
            {"internalType": "bytes", "name": "path", "type": "bytes"},
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
        ],
        "name": "quoteExactInput",
        "outputs": [{"internalType": "uint256", "name": "amountOut", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]

ROUTER_ABI: list[dict[str, Any]] = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "address", "name": "tokenIn", "type": "address"},
                    {"internalType": "address", "name": "tokenOut", "type": "address"},
                    {"internalType": "uint24", "name": "fee", "type": "uint24"},
                    {"internalType": "address", "name": "recipient", "type": "address"},
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "uint256", "name": "amountOutMinimum", "type": "uint256"},
                    {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"},
                ],
                "internalType": "struct ISwapRouter.ExactInputSingleParams",
                "name": "params",
                "type": "tuple",
            }
        ],
        "name": "exactInputSingle",
        "outputs": [{"internalType": "uint256", "name": "amountOut", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function",
    }
]

ERC20_ABI: list[dict[str, Any]] = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}, {"name": "_spender", "type": "address"}],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [{"name": "_spender", "type": "address"}, {"name": "_value", "type": "uint256"}],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
]

WETH9_ABI: list[dict[str, Any]] = [
    {"constant": False, "inputs": [], "name": "deposit", "outputs": [], "type": "function"},
    {"constant": False, "inputs": [{"name": "wad", "type": "uint256"}], "name": "withdraw", "outputs": [], "type": "function"},
]

MULTICALL_ABI: list[dict[str, Any]] = [
    {
        "inputs": [
            {"internalType": "bool", "name": "requireSuccess", "type": "bool"},
            {
                "components": [
                    {"internalType": "address", "name": "target", "type": "address"},
                    {"internalType": "bytes", "name": "callData", "type": "bytes"},
                ],
                "internalType": "struct Multicall3.Call[]",
                "name": "calls",
                "type": "tuple[]",
            },
        ],
        "name": "tryAggregate",
        "outputs": [
            {
                "components": [
                    {"internalType": "bool", "name": "success", "type": "bool"},
                    {"internalType": "bytes", "name": "returnData", "type": "bytes"},
                ],
                "internalType": "struct Multicall3.Result[]",
                "name": "returnData",
                "type": "tuple[]",
            }
        ],
        "stateMutability": "payable",
        "type": "function",
    }
]


class Web3TestnetAdapter:
    """Async Uniswap V3 Sepolia adapter for WETH/USDC quotes and testnet swaps."""

    def __init__(self, symbol: str = DEFAULT_SYMBOL, crdt_adapter: Any = None) -> None:
        self.crdt = crdt_adapter
        self.symbol = str(symbol or DEFAULT_SYMBOL).strip().upper() or DEFAULT_SYMBOL

        self.rpc_url = str(getattr(config, "web3_rpc_url", "") or "").strip()
        if not self.rpc_url:
            self.rpc_url = os.environ.get("WEB3_RPC_URL", "").strip()

        self.private_key: Optional[str] = (
            config.security.web3_private_key.get_secret_value()
            if getattr(config, "security", None) is not None and getattr(config.security, "web3_private_key", None)
            else os.environ.get("WEB3_PRIVATE_KEY")
        )

        if not self.rpc_url:
            logger.warning("WEB3_RPC_URL is not configured. Web3 adapter may fail to initialize.")
        if not self.private_key:
            logger.warning("WEB3_PRIVATE_KEY is not set. Web3 adapter runs in read-only mode.")

        self.w3 = AsyncWeb3(AsyncHTTPProvider(self.rpc_url, request_kwargs={"timeout": 60}))
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        self.account: Optional[Any] = None
        self.nonce_manager: Optional[NonceManager] = None

        self.quoter: Optional[Contract] = None
        self.router: Optional[Contract] = None
        self.weth_contract: Optional[Contract] = None
        self.usdc_contract: Optional[Contract] = None
        self.multicall_contract: Optional[Contract] = None

        self._initialized = False

    async def initialize(self) -> None:
        """Initialize chain connection, wallet, nonce manager, and contracts."""
        chain_id = await self._retry_rpc(lambda: self.w3.eth.chain_id, description="chain_id", attempts=3)
        logger.info("Connected to chain_id=%s", chain_id)

        if int(chain_id) != SEPOLIA_CHAIN_ID:
            logger.warning("Expected Sepolia chain_id=%s but connected to chain_id=%s.", SEPOLIA_CHAIN_ID, chain_id)

        if self.private_key:
            self.account = self.w3.eth.account.from_key(self.private_key)
            self.nonce_manager = NonceManager(self.account.address)
            self.w3.eth.default_account = self.account.address
            logger.info("Web3 wallet initialized: %s...", self.account.address[:8])
        else:
            logger.info("Web3 adapter initialized in read-only mode.")

        self.quoter = self.w3.eth.contract(address=self._checksum(QUOTER_ADDRESS), abi=QUOTER_ABI)
        self.router = self.w3.eth.contract(address=self._checksum(ROUTER_ADDRESS), abi=ROUTER_ABI)
        self.weth_contract = self.w3.eth.contract(address=self._checksum(WETH_ADDRESS), abi=ERC20_ABI)
        self.usdc_contract = self.w3.eth.contract(address=self._checksum(USDC_ADDRESS), abi=ERC20_ABI)
        self.multicall_contract = self.w3.eth.contract(address=self._checksum(MULTICALL_ADDRESS), abi=MULTICALL_ABI)

        self._initialized = True
        logger.info("Web3TestnetAdapter initialized for %s.", self.symbol)

    async def ainit(self) -> None:
        """Compatibility alias used by MultiPairAdapter."""
        await self.initialize()

    async def close(self) -> None:
        """Close AsyncWeb3 provider resources when supported."""
        provider = getattr(getattr(self, "w3", None), "provider", None)
        if provider is None:
            return

        closed_any = False

        for method_name in ("disconnect", "close", "disconnect_all"):
            method = getattr(provider, method_name, None)
            if not callable(method):
                continue

            try:
                result = method()
                if hasattr(result, "__await__"):
                    await result
                closed_any = True
                logger.info("Web3 provider closed via %s().", method_name)
            except Exception as exc:
                logger.debug("Provider %s() failed during close: %s", method_name, exc)

        session_manager = getattr(provider, "_request_session_manager", None)
        if session_manager is not None:
            for method_name in ("close", "disconnect", "clear"):
                method = getattr(session_manager, method_name, None)
                if not callable(method):
                    continue

                try:
                    result = method()
                    if hasattr(result, "__await__"):
                        await result
                    closed_any = True
                    logger.debug("Web3 session manager closed via %s().", method_name)
                except Exception as exc:
                    logger.debug("Session manager %s() failed: %s", method_name, exc)

        if not closed_any:
            logger.debug("Web3 adapter close completed without closeable resources.")

    async def fetch_all_tickers(self) -> dict[str, dict[str, Any]]:
        """Fetch ticker snapshot in market-service shape."""
        ticker = await self.get_ticker()
        return {self.symbol: ticker} if ticker else {}

    async def get_ticker(self) -> Optional[dict[str, Any]]:
        """Quote 1 WETH in USDC through Uniswap V3 Quoter."""
        await self._ensure_initialized_readonly()

        if not self.quoter:
            logger.error("Quoter contract is not initialized.")
            return None

        async def _fetch_quote_once() -> Optional[dict[str, Any]]:
            try:
                amount_in = self.w3.to_wei(1, "ether")
                amount_out = await self._quote_exact_input(WETH_ADDRESS, USDC_ADDRESS, amount_in)
                price = amount_out / 10**6

                if price <= 0:
                    return None

                return {
                    "price": float(price),
                    "symbol": self.symbol,
                    "timestamp": time.time(),
                }
            except Exception as exc:
                logger.warning("Failed to fetch WETH/USDC quote: %s", exc)
                return None

        for attempt in range(3):
            result = await _fetch_quote_once()
            if result:
                return result

            if attempt < 2:
                await asyncio.sleep(2 ** attempt)

        logger.error("get_ticker failed after retries.")
        return None

    async def fetch_balance(self) -> dict[str, float]:
        """Fetch ETH, WETH, and USDC balances for initialized account."""
        await self._ensure_initialized_readonly()

        if not self.account:
            logger.warning("Account not initialized; cannot fetch balances.")
            return {}

        try:
            eth_balance = float(self.w3.from_wei(await self.w3.eth.get_balance(self.account.address), "ether"))
            weth_balance = await self._get_token_balance(WETH_ADDRESS)
            usdc_balance = await self._get_token_balance(USDC_ADDRESS)
            return {"ETH": eth_balance, "WETH": weth_balance, "USDC": usdc_balance}
        except Exception as exc:
            logger.error("Web3 balance fetch failed: %s", exc)
            return {}

    async def _get_token_balance(self, token_address: str) -> float:
        """Return ERC-20 balance for current account in human units."""
        await self._ensure_initialized_readonly()

        if not self.account:
            return 0.0

        contract = self._token_contract(token_address)
        decimals = self._token_decimals(token_address)

        try:
            raw_balance = await contract.functions.balanceOf(self.account.address).call()
            return float(raw_balance) / float(10**decimals)
        except Exception as exc:
            logger.warning("Failed to fetch token balance token=%s: %s", token_address, exc)
            return 0.0

    async def wrap_eth(self, amount_eth: float) -> Optional[str]:
        """Wrap ETH into WETH."""
        if not self._ready_for_transactions() or not self.weth_contract:
            logger.error("Web3 adapter is not initialized for wrap_eth transactions.")
            return None

        amount = self._positive_float(amount_eth)
        if amount is None:
            logger.error("Invalid wrap amount: %r", amount_eth)
            return None

        try:
            value = self.w3.to_wei(amount, "ether")
            nonce = await self.nonce_manager.reserve_nonce(self.w3)  # type: ignore[union-attr]
            gas_params = await self._get_gas_params()

            tx = await self.weth_contract.functions.deposit().build_transaction(
                {
                    "from": self.account.address,  # type: ignore[union-attr]
                    "value": value,
                    "gas": 50_000,
                    "nonce": nonce,
                    **gas_params,
                }
            )

            receipt = await self._send_transaction_and_wait(tx, f"Wrap {amount} ETH -> WETH", timeout=120)
            return receipt.transactionHash.hex() if receipt else None

        except Exception as exc:
            logger.error("Wrap ETH failed amount=%s: %s", amount_eth, exc)
            await self._sync_nonce_after_failure()
            return None

    async def unwrap_weth(self, amount_weth: float) -> Optional[str]:
        """Unwrap WETH into ETH."""
        if not self._ready_for_transactions() or not self.weth_contract:
            logger.error("Web3 adapter is not initialized for unwrap_weth transactions.")
            return None

        amount = self._positive_float(amount_weth)
        if amount is None:
            logger.error("Invalid unwrap amount: %r", amount_weth)
            return None

        try:
            value = self.w3.to_wei(amount, "ether")
            nonce = await self.nonce_manager.reserve_nonce(self.w3)  # type: ignore[union-attr]
            gas_params = await self._get_gas_params()

            tx = await self.weth_contract.functions.withdraw(value).build_transaction(
                {
                    "from": self.account.address,  # type: ignore[union-attr]
                    "gas": 50_000,
                    "nonce": nonce,
                    **gas_params,
                }
            )

            receipt = await self._send_transaction_and_wait(tx, f"Unwrap {amount} WETH -> ETH", timeout=120)
            return receipt.transactionHash.hex() if receipt else None

        except Exception as exc:
            logger.error("Unwrap WETH failed amount=%s: %s", amount_weth, exc)
            await self._sync_nonce_after_failure()
            return None

    async def place_order(self, side: str, amount: float, price: Optional[float] = None) -> dict[str, Any]:
        """Execute WETH/USDC swap through Uniswap V3 exactInputSingle."""
        if not self._ready_for_transactions() or not self.router:
            return self._error("web3_adapter_not_initialized_for_transactions")

        clean_side = str(side or "").strip().lower()
        if clean_side not in {"buy", "sell"}:
            return self._error(f"unsupported_trade_side:{side}")

        amount_weth = self._positive_float(amount)
        if amount_weth is None:
            return self._error("amount_must_be_positive")

        try:
            fee = self._pool_fee()
            slippage_bps = self._slippage_bps()

            token_in: str
            token_out: str
            amount_in: int
            amount_out_minimum: int

            if clean_side == "sell":
                token_in = WETH_ADDRESS
                token_out = USDC_ADDRESS
                amount_in = self.w3.to_wei(amount_weth, "ether")

                quoted_out = await self._quote_exact_input(token_in, token_out, amount_in)
                amount_out_minimum = self._apply_slippage(quoted_out, slippage_bps)

            else:
                token_in = USDC_ADDRESS
                token_out = WETH_ADDRESS

                estimated_price = self._positive_float(price)
                if estimated_price is None:
                    ticker = await self.get_ticker()
                    estimated_price = self._positive_float((ticker or {}).get("price")) or 2_000.0

                usdc_in = amount_weth * estimated_price
                amount_in = int(usdc_in * 10**6)

                quoted_out = await self._quote_exact_input(token_in, token_out, amount_in)
                amount_out_minimum = self._apply_slippage(quoted_out, slippage_bps)

            if amount_in <= 0:
                return self._error("amount_in_is_zero")

            balance = await self._get_token_balance(token_in)
            token_in_decimals = self._token_decimals(token_in)
            required_balance = amount_in / 10**token_in_decimals

            if balance < required_balance:
                logger.warning(
                    "Insufficient balance for %s: available=%.8f required=%.8f token=%s",
                    clean_side,
                    balance,
                    required_balance,
                    token_in,
                )
                return self._error("insufficient_balance")

            if not await self._ensure_allowance(token_in, ROUTER_ADDRESS, amount_in):
                return self._error("allowance_approval_failed")

            nonce = await self.nonce_manager.reserve_nonce(self.w3)  # type: ignore[union-attr]
            gas_params = await self._get_gas_params()

            swap_tuple = (
                self._checksum(token_in),
                self._checksum(token_out),
                fee,
                self.account.address,  # type: ignore[union-attr]
                amount_in,
                amount_out_minimum,
                0,
            )

            tx = await self.router.functions.exactInputSingle(swap_tuple).build_transaction(
                {
                    "from": self.account.address,  # type: ignore[union-attr]
                    "gas": 300_000,
                    "nonce": nonce,
                    **gas_params,
                }
            )

            receipt = await self._send_transaction_and_wait(
                tx,
                f"Swap side={clean_side} amount_weth={amount_weth}",
                timeout=DEFAULT_TX_TIMEOUT_SECONDS,
            )

            if receipt:
                return {
                    "success": True,
                    "status": "success",
                    "tx_hash": receipt.transactionHash.hex(),
                    "error": None,
                }

            return self._error("transaction_failed_or_timed_out", status="failed")

        except Exception as exc:
            logger.error("Swap exception side=%s amount=%s: %s", clean_side, amount, exc)
            await self._sync_nonce_after_failure()
            return self._error(str(exc))

    async def batch_swap(self, swaps: list[dict[str, Any]]) -> dict[str, Any]:
        """Execute multiple prepared exactInputSingle swaps through Multicall3."""
        if not self._ready_for_transactions() or not self.router or not self.multicall_contract:
            return self._error("web3_adapter_not_initialized_for_batch_swap")

        if not isinstance(swaps, list) or not swaps:
            return self._error("no_swaps_provided")

        calls: list[tuple[str, bytes]] = []

        for index, swap in enumerate(swaps):
            prepared = self._validate_batch_swap(swap, index)
            if isinstance(prepared, dict):
                return prepared

            token_in, token_out, fee, amount_in_wei, amount_out_min = prepared

            swap_params = (
                self._checksum(token_in),
                self._checksum(token_out),
                fee,
                self.account.address,  # type: ignore[union-attr]
                amount_in_wei,
                amount_out_min,
                0,
            )

            call_data = self.router.encode_abi("exactInputSingle", args=[swap_params])
            calls.append((self.router.address, call_data))

        try:
            nonce = await self.nonce_manager.reserve_nonce(self.w3)  # type: ignore[union-attr]
            gas_params = await self._get_gas_params()

            tx = await self.multicall_contract.functions.tryAggregate(False, calls).build_transaction(
                {
                    "from": self.account.address,  # type: ignore[union-attr]
                    "gas": 500_000 * len(calls),
                    "nonce": nonce,
                    **gas_params,
                }
            )

            receipt = await self._send_transaction_and_wait(tx, f"Batch Swap ({len(calls)} swaps)", timeout=300)

            if receipt:
                return {
                    "success": True,
                    "status": "success",
                    "tx_hash": receipt.transactionHash.hex(),
                    "error": None,
                }

            return self._error("batch_transaction_failed_or_timed_out", status="failed")

        except Exception as exc:
            logger.error("Batch swap exception: %s", exc)
            await self._sync_nonce_after_failure()
            return self._error(str(exc))

    async def _get_gas_params(self) -> dict[str, Any]:
        """Return EIP-1559 gas params or legacy gasPrice fallback."""
        try:
            max_priority_fee = await self.w3.eth.max_priority_fee
            fee_history = await self.w3.eth.fee_history(1, "latest", reward_percentiles=[50])
            base_fee = int(fee_history["baseFeePerGas"][-1])
            return {
                "maxFeePerGas": Wei(base_fee * 2 + int(max_priority_fee)),
                "maxPriorityFeePerGas": Wei(max_priority_fee),
            }
        except Exception as exc:
            gas_price = await self.w3.eth.gas_price
            logger.warning("Failed to fetch EIP-1559 gas params (%s); using gasPrice fallback.", exc)
            return {"gasPrice": Wei(int(gas_price * 2))}

    async def _send_transaction_and_wait(
        self,
        tx: dict[str, Any],
        description: str,
        timeout: int = DEFAULT_TX_TIMEOUT_SECONDS,
    ) -> Optional[TxReceipt]:
        """Sign, send, and wait for a transaction receipt."""
        if not self._ready_for_transactions():
            logger.error("Account/private key/nonce manager not initialized for transaction.")
            return None

        try:
            signed = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
            tx_hash_hex = tx_hash.hex()

            logger.info("%s tx sent: %s", description, tx_hash_hex)

            receipt = await self._retry_rpc(
                lambda: self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout, poll_latency=1.0),
                description=f"wait_for_receipt:{tx_hash_hex}",
                attempts=3,
                retry_delay=2.0,
            )

            if receipt and int(receipt.status) == 1:
                logger.info("%s successful. tx=%s", description, tx_hash_hex)
                await self.nonce_manager.update_nonce_async(receipt)  # type: ignore[union-attr]
                return receipt

            logger.error("%s failed/reverted. tx=%s receipt=%s", description, tx_hash_hex, receipt)
            await self._sync_nonce_after_failure()
            return None

        except Exception as exc:
            logger.error("%s transaction error: %s", description, exc)
            await self._sync_nonce_after_failure()
            return None

    async def _sync_nonce_after_failure(self) -> None:
        """Synchronize nonce from chain after a failed transaction path."""
        if not self.nonce_manager or not self.account:
            return

        for attempt in range(3):
            try:
                pending_nonce = await self.w3.eth.get_transaction_count(self.account.address, "pending")
                await self.nonce_manager.sync_with_chain_async(int(pending_nonce))
                logger.info("Nonce synced to %s after transaction failure.", pending_nonce)
                return
            except Exception as exc:
                if attempt < 2:
                    logger.warning("Nonce sync failed, retrying (%d/3): %s", attempt + 1, exc)
                    await asyncio.sleep(2**attempt)
                else:
                    logger.error("Failed to sync nonce after transaction failure: %s", exc)

    async def _ensure_allowance(self, token_address: str, spender: str, amount: int) -> bool:
        """Ensure router has enough ERC-20 allowance."""
        if not self._ready_for_transactions():
            logger.error("Adapter not initialized for allowance transaction.")
            return False

        token = self._token_contract(token_address)
        spender_checksum = self._checksum(spender)

        try:
            current_allowance = await token.functions.allowance(self.account.address, spender_checksum).call()  # type: ignore[union-attr]
            if int(current_allowance) >= int(amount):
                return True

            logger.info(
                "Approving spender=%s... token=%s amount=%s current_allowance=%s",
                spender_checksum[:10],
                token_address,
                amount,
                current_allowance,
            )

            nonce = await self.nonce_manager.reserve_nonce(self.w3)  # type: ignore[union-attr]
            gas_params = await self._get_gas_params()

            approve_tx = await token.functions.approve(spender_checksum, 2**256 - 1).build_transaction(
                {
                    "from": self.account.address,  # type: ignore[union-attr]
                    "gas": 100_000,
                    "nonce": nonce,
                    **gas_params,
                }
            )

            receipt = await self._send_transaction_and_wait(approve_tx, "Approve router allowance", timeout=180)
            return receipt is not None

        except Exception as exc:
            logger.error("Allowance check/approval failed: %s", exc)
            await self._sync_nonce_after_failure()
            return False

    async def _quote_exact_input(self, token_in: str, token_out: str, amount_in: int) -> int:
        if not self.quoter:
            raise RuntimeError("quoter_not_initialized")

        path = self._encode_v3_path(token_in, token_out, self._pool_fee())
        amount_out = await self.quoter.functions.quoteExactInput(path, int(amount_in)).call()
        return int(amount_out)

    def _encode_v3_path(self, token_in: str, token_out: str, fee: int) -> bytes:
        return (
            self.w3.to_bytes(hexstr=self._checksum(token_in)).rjust(20, b"\0")
            + int(fee).to_bytes(3, "big")
            + self.w3.to_bytes(hexstr=self._checksum(token_out)).rjust(20, b"\0")
        )

    def _token_contract(self, token_address: str) -> Contract:
        if token_address.lower() == WETH_ADDRESS.lower() and self.weth_contract:
            return self.weth_contract
        if token_address.lower() == USDC_ADDRESS.lower() and self.usdc_contract:
            return self.usdc_contract
        return self.w3.eth.contract(address=self._checksum(token_address), abi=ERC20_ABI)

    @staticmethod
    def _token_decimals(token_address: str) -> int:
        return 18 if token_address.lower() == WETH_ADDRESS.lower() else 6

    def _checksum(self, address: str) -> str:
        return self.w3.to_checksum_address(address)

    def _ready_for_transactions(self) -> bool:
        return bool(self.account and self.private_key and self.nonce_manager)

    async def _ensure_initialized_readonly(self) -> None:
        if not self._initialized:
            await self.initialize()

    @staticmethod
    def _apply_slippage(amount_out: int, slippage_bps: int) -> int:
        safe_bps = max(0, min(10_000, int(slippage_bps)))
        return max(0, int(int(amount_out) * (10_000 - safe_bps) / 10_000))

    @staticmethod
    def _positive_float(value: Any) -> Optional[float]:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(number) or number <= 0:
            return None
        return number

    @staticmethod
    def _error(error: str, *, status: str = "error") -> dict[str, Any]:
        return {
            "success": False,
            "status": status,
            "error": str(error),
        }

    @staticmethod
    async def _retry_rpc(call: Any, *, description: str, attempts: int = 3, retry_delay: float = 1.0) -> Any:
        last_error: Exception | None = None

        for attempt in range(max(1, attempts)):
            try:
                result = call()
                if hasattr(result, "__await__"):
                    return await result
                return result
            except Exception as exc:
                last_error = exc
                if attempt < attempts - 1:
                    logger.warning("RPC %s failed, retrying (%d/%d): %s", description, attempt + 1, attempts, exc)
                    await asyncio.sleep(retry_delay * (2**attempt))

        raise RuntimeError(f"RPC {description} failed after {attempts} attempt(s)") from last_error

    @staticmethod
    def _validate_batch_swap(
        swap: dict[str, Any],
        index: int,
    ) -> tuple[str, str, int, int, int] | dict[str, Any]:
        required = ("token_in", "token_out", "fee", "amount_in_wei", "amount_out_min")
        if not isinstance(swap, dict) or not all(key in swap for key in required):
            return Web3TestnetAdapter._error(f"invalid_swap_parameters_at_index:{index}")

        try:
            token_in = str(swap["token_in"])
            token_out = str(swap["token_out"])
            fee = int(swap["fee"])
            amount_in_wei = int(swap["amount_in_wei"])
            amount_out_min = int(swap["amount_out_min"])
        except (TypeError, ValueError):
            return Web3TestnetAdapter._error(f"invalid_swap_types_at_index:{index}")

        if amount_in_wei <= 0 or amount_out_min < 0 or fee <= 0:
            return Web3TestnetAdapter._error(f"invalid_swap_values_at_index:{index}")

        return token_in, token_out, fee, amount_in_wei, amount_out_min

    @staticmethod
    def _pool_fee() -> int:
        try:
            return int(getattr(config.trading, "web3_pool_fee", DEFAULT_POOL_FEE))
        except Exception:
            return DEFAULT_POOL_FEE

    @staticmethod
    def _slippage_bps() -> int:
        raw = (
            getattr(getattr(config, "trading", None), "web3_slippage_bps", None)
            or os.environ.get("WEB3_SLIPPAGE_BPS")
            or DEFAULT_SLIPPAGE_BPS
        )
        try:
            return max(0, min(10_000, int(raw)))
        except (TypeError, ValueError):
            return DEFAULT_SLIPPAGE_BPS