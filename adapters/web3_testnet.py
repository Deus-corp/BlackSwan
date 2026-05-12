"""
Web3 Testnet Adapter (Ethereum Sepolia) – полностью асинхронный Uniswap V3 адаптер.
Использует AsyncWeb3, NonceManager и новый конфиг.
"""
import asyncio
import logging
from typing import Dict, Optional
from web3 import AsyncWeb3
from web3.providers import AsyncHTTPProvider
from web3.middleware import ExtraDataToPOAMiddleware
from loguru import logger

from swarm_config import config
from adapters.nonce_manager import NonceManager

# ---------- Константы Uniswap V3 Sepolia ----------
QUOTER_ADDRESS = "0xd64686fa7549534ecb1b5cdd772d60c3cf02af3c"
ROUTER_ADDRESS = "0x3bFA4769FB09eefC5a80d6E87c3B9C650f7Ae48E"
WETH_ADDRESS = "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14"
USDC_ADDRESS = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"

QUOTER_ABI = [
    {"inputs": [{"internalType": "bytes","name": "path","type": "bytes"},
                {"internalType": "uint256","name": "amountIn","type": "uint256"}],
     "name": "quoteExactInput","outputs": [{"internalType": "uint256","name": "amountOut","type": "uint256"}],
     "stateMutability": "nonpayable","type": "function"}
]

ROUTER_ABI = [
    {"inputs": [{"components": [
        {"internalType": "address","name": "tokenIn","type": "address"},
        {"internalType": "address","name": "tokenOut","type": "address"},
        {"internalType": "uint24","name": "fee","type": "uint24"},
        {"internalType": "address","name": "recipient","type": "address"},
        {"internalType": "uint256","name": "amountIn","type": "uint256"},
        {"internalType": "uint256","name": "amountOutMinimum","type": "uint256"},
        {"internalType": "uint160","name": "sqrtPriceLimitX96","type": "uint160"}
    ],"internalType": "struct ISwapRouter.ExactInputSingleParams","name": "params","type": "tuple"}],
     "name": "exactInputSingle","outputs": [{"internalType": "uint256","name": "amountOut","type": "uint256"}],
     "stateMutability": "payable","type": "function"}
]

ERC20_ABI = [
    {"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"},
    {"constant":True,"inputs":[{"name":"_owner","type":"address"},{"name":"_spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"type":"function"},
    {"constant":False,"inputs":[{"name":"_spender","type":"address"},{"name":"_value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"type":"function"},
]

WETH9_ABI = [
    {"constant":False,"inputs":[],"name":"deposit","outputs":[],"type":"function"},
    {"constant":False,"inputs":[{"name":"wad","type":"uint256"}],"name":"withdraw","outputs":[],"type":"function"},
]


class Web3TestnetAdapter:
    def __init__(self, symbol: str = "WETH/USDC", crdt_adapter=None):
        self.crdt = crdt_adapter
        self.symbol = symbol
        self.rpc_url = config.web3_rpc_url
        self.private_key = config.security.web3_private_key.get_secret_value() if config.security.web3_private_key else None
        self.token_in_env = WETH_ADDRESS
        self.token_out_env = USDC_ADDRESS

        if not self.private_key:
            logger.warning("WEB3_PRIVATE_KEY not set. Web3 adapter will run in read-only mode.")

        # Async Web3
        self.w3 = AsyncWeb3(AsyncHTTPProvider(self.rpc_url, request_kwargs={"timeout": 60}))
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        self.account = None
        self.nonce_manager = None
        self.quoter = None
        self.router = None
        self.weth_contract = None
        self.usdc_contract = None

    async def initialize(self):
        """Асинхронная инициализация (вызывать при старте ноды)."""
        chain_id = await self.w3.eth.chain_id
        logger.info(f"Connected to chain ID {chain_id}")

        if self.private_key:
            self.account = self.w3.eth.account.from_key(self.private_key)
            self.nonce_manager = NonceManager(self.account.address)
            self.w3.eth.default_account = self.account.address
            logger.info(f"Wallet: {self.account.address[:8]}...")

        # Инициализируем контракты (адреса с checksum)
        checksum_quoter = self.w3.to_checksum_address(QUOTER_ADDRESS)
        checksum_router = self.w3.to_checksum_address(ROUTER_ADDRESS)
        checksum_weth = self.w3.to_checksum_address(WETH_ADDRESS)
        checksum_usdc = self.w3.to_checksum_address(USDC_ADDRESS)

        self.quoter = self.w3.eth.contract(address=checksum_quoter, abi=QUOTER_ABI)
        self.router = self.w3.eth.contract(address=checksum_router, abi=ROUTER_ABI)
        self.weth_contract = self.w3.eth.contract(address=checksum_weth, abi=ERC20_ABI)
        self.usdc_contract = self.w3.eth.contract(address=checksum_usdc, abi=ERC20_ABI)

        logger.success("Web3TestnetAdapter initialized (async)")

    # ---------- Помощники ----------
    async def _get_gas_params(self) -> dict:
        try:
            fee_history = await self.w3.eth.fee_history(1, "latest", reward_percentiles=[50])
            base_fee = fee_history["baseFeePerGas"][0]
            max_priority_fee = await self.w3.eth.max_priority_fee
            if max_priority_fee is None:
                max_priority_fee = self.w3.to_wei(2, "gwei")
            return {
                "maxFeePerGas": base_fee * 2 + max_priority_fee,
                "maxPriorityFeePerGas": max_priority_fee,
            }
        except Exception:
            gas_price = await self.w3.eth.gas_price
            return {"gasPrice": int(gas_price * 2.0)}

    async def _ensure_allowance(self, token_address: str, spender: str, amount: int) -> bool:
        token = self.w3.eth.contract(address=self.w3.to_checksum_address(token_address), abi=ERC20_ABI)
        current = await token.functions.allowance(self.account.address, spender).call()
        if current >= amount:
            return True
        logger.info(f"Approving {spender} for max allowance...")
        nonce_n = await self.nonce_manager.reserve_nonce(self.w3)
        gas_params = await self._get_gas_params()
        tx = await token.functions.approve(spender, 2**256 - 1).build_transaction({
            "from": self.account.address,
            "gas": 100000,
            "nonce": nonce_n,
            **gas_params,
        })
        signed = self.w3.eth.account.sign_transaction(tx, self.private_key)
        tx_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
        logger.info(f"Approve tx: {tx_hash.hex()}")
        receipt = await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180, poll_latency=1.0)
        if receipt.status == 1:
            logger.info("Approve successful")
            return True
        else:
            logger.error("Approve failed")
            return False

    # ---------- Получение данных ----------
    async def get_ticker(self) -> Optional[Dict[str, float]]:
        try:
            amount_in = self.w3.to_wei(1, "ether")
            fee = config.trading.web3_pool_fee
            path = (
                self.w3.to_bytes(hexstr=WETH_ADDRESS).rjust(20, b"\0")
                + fee.to_bytes(3, "big")
                + self.w3.to_bytes(hexstr=USDC_ADDRESS).rjust(20, b"\0")
            )
            amount_out = await self.quoter.functions.quoteExactInput(path, amount_in).call()
            price = amount_out / 10**6
            return {"price": price, "symbol": self.symbol}
        except Exception as e:
            if "429" in str(e):
                await asyncio.sleep(10)
                try:
                    amount_out = await self.quoter.functions.quoteExactInput(path, amount_in).call()
                    price = amount_out / 10**6
                    return {"price": price, "symbol": self.symbol}
                except Exception as retry_e:
                    logger.error(f"get_ticker retry failed: {retry_e}")
                    return None
            logger.error(f"get_ticker failed: {e}")
            return None

    async def _get_token_balance(self, token_address: str) -> float:
        contract = self.w3.eth.contract(address=self.w3.to_checksum_address(token_address), abi=ERC20_ABI)
        balance_wei = await contract.functions.balanceOf(self.account.address).call()
        decimals = 18 if token_address.lower() == WETH_ADDRESS.lower() else 6
        return balance_wei / (10**decimals)

    async def fetch_balance(self) -> Dict[str, float]:
        if not self.account:
            return {}
        eth_balance = self.w3.from_wei(await self.w3.eth.get_balance(self.account.address), "ether")
        weth_balance = await self._get_token_balance(WETH_ADDRESS)
        usdc_balance = await self._get_token_balance(USDC_ADDRESS)
        return {"ETH": eth_balance, "WETH": weth_balance, "USDC": usdc_balance}

    # ---------- Wrap / Unwrap ----------
    async def wrap_eth(self, amount_eth: float) -> Optional[str]:
        try:
            weth = self.w3.eth.contract(address=self.w3.to_checksum_address(WETH_ADDRESS), abi=WETH9_ABI)
            value = self.w3.to_wei(amount_eth, 'ether')
            nonce = await self.nonce_manager.reserve_nonce(self.w3)
            gas_params = await self._get_gas_params()
            tx = await weth.functions.deposit().build_transaction({
                'from': self.account.address,
                'value': value,
                'gas': 50000,
                'nonce': nonce,
                **gas_params,
            })
            signed = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
            logger.info(f"Wrap {amount_eth} ETH → WETH, tx: {tx_hash.hex()}")
            receipt = await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            if receipt.status == 1:
                logger.success("✅ Wrap successful")
                return tx_hash.hex()
            else:
                logger.error("❌ Wrap reverted")
                return None
        except Exception as e:
            logger.error(f"Wrap error: {e}")
            return None

    async def unwrap_weth(self, amount_weth: float) -> Optional[str]:
        try:
            weth = self.w3.eth.contract(address=self.w3.to_checksum_address(WETH_ADDRESS), abi=WETH9_ABI)
            value = self.w3.to_wei(amount_weth, 'ether')
            nonce = await self.nonce_manager.reserve_nonce(self.w3)
            gas_params = await self._get_gas_params()
            tx = await weth.functions.withdraw(value).build_transaction({
                'from': self.account.address,
                'gas': 50000,
                'nonce': nonce,
                **gas_params,
            })
            signed = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
            logger.info(f"Unwrap {amount_weth} WETH → ETH, tx: {tx_hash.hex()}")
            receipt = await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            if receipt.status == 1:
                logger.success("✅ Unwrap successful")
                return tx_hash.hex()
            else:
                logger.error("❌ Unwrap reverted")
                return None
        except Exception as e:
            logger.error(f"Unwrap error: {e}")
            return None

    # ---------- Основной своп ----------
    async def place_order(self, side: str, amount: float, price: Optional[float] = None) -> Dict:
        if not self.account or not self.nonce_manager:
            return {"error": "WEB3_PRIVATE_KEY not set or not initialized"}

        try:
            fee = config.trading.web3_pool_fee

            if side.lower() == "sell":
                token_in = WETH_ADDRESS
                token_out = USDC_ADDRESS
                amount_in_wei = self.w3.to_wei(amount, "ether")
                amount_out_min = 0
            else:  # buy
                token_in = USDC_ADDRESS
                token_out = WETH_ADDRESS
                # Используем асинхронный get_ticker для получения цены
                tick = await self.get_ticker()
                usdc_needed = amount * (tick["price"] if tick else 2000)
                amount_in_wei = int(usdc_needed * 10**6)
                amount_out_min = 0

            # Проверка баланса (асинхронно)
            balance = await self._get_token_balance(token_in)
            if balance < amount:
                logger.warning(f"Insufficient {token_in} balance ({balance} < {amount})")
                return {"error": "Insufficient balance"}

            # Allowance
            if not await self._ensure_allowance(token_in, ROUTER_ADDRESS, amount_in_wei):
                return {"error": "Insufficient allowance"}

            # Безопасный nonce
            safe_nonce = await self.nonce_manager.reserve_nonce(self.w3)

            # Параметры ExactInputSingle
            swap_tuple = (
                self.w3.to_checksum_address(token_in),
                self.w3.to_checksum_address(token_out),
                fee,
                self.account.address,
                amount_in_wei,
                amount_out_min,
                0
            )

            gas_params = await self._get_gas_params()
            tx = await self.router.functions.exactInputSingle(swap_tuple).build_transaction({
                "from": self.account.address,
                "gas": 300000,
                "nonce": safe_nonce,
                **gas_params,
            })

            signed = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
            logger.info(f"Swap tx sent: {tx_hash.hex()}")

            receipt = await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180, poll_latency=1.0)

            if receipt.status == 1:
                logger.success(f"✅ Swap successful! Tx: {tx_hash.hex()}")
                # Обновим nonce
                await self.nonce_manager.update_nonce_async(receipt)
                return {"tx_hash": tx_hash.hex(), "status": "success"}
            else:
                logger.error(f"❌ Swap reverted. Tx: {tx_hash.hex()}")
                await self.nonce_manager.sync_with_chain_async(await self.w3.eth.get_transaction_count(self.account.address, "pending"))
                return {"tx_hash": tx_hash.hex(), "status": "failed"}
        except Exception as e:
            logger.error(f"Swap exception: {e}")
            # Синхронизируем nonce после ошибки
            if self.nonce_manager:
                await self.nonce_manager.sync_with_chain_async(
                    await self.w3.eth.get_transaction_count(self.account.address, "pending")
                )
            return {"error": str(e)}
        
    async def batch_swap(self, swaps: list) -> dict:
        """
        Выполняет несколько свопов через Multicall (tryAggregate).
        swaps: [{"token_in": str, "token_out": str, "fee": int, "amount_in_wei": int, "amount_out_min": int}, ...]
        """
        if not self.account or not self.nonce_manager:
            return {"error": "Not initialized"}

        # Адрес Multicall3 на Sepolia
        MULTICALL_ADDRESS = self.w3.to_checksum_address("0xcA11bde05977b3631167028862bE2a173976CA11")
        MULTICALL_ABI = [
            {
                "inputs": [
                    {"internalType": "bool", "name": "requireSuccess", "type": "bool"},
                    {"components": [
                        {"internalType": "address", "name": "target", "type": "address"},
                        {"internalType": "bytes", "name": "callData", "type": "bytes"}
                    ], "internalType": "struct Multicall3.Call[]", "name": "calls", "type": "tuple[]"}
                ],
                "name": "tryAggregate",
                "outputs": [
                    {"components": [
                        {"internalType": "bool", "name": "success", "type": "bool"},
                        {"internalType": "bytes", "name": "returnData", "type": "bytes"}
                    ], "internalType": "struct Multicall3.Result[]", "name": "returnData", "type": "tuple[]"}
                ],
                "stateMutability": "payable",
                "type": "function"
            }
        ]
        multicall = self.w3.eth.contract(address=MULTICALL_ADDRESS, abi=MULTICALL_ABI)

        calls = []
        for s in swaps:
            swap_params = (
                self.w3.to_checksum_address(s["token_in"]),
                self.w3.to_checksum_address(s["token_out"]),
                s["fee"],
                self.account.address,
                s["amount_in_wei"],
                s["amount_out_min"],
                0
            )
            call_data = self.router.encode_abi('exactInputSingle', args=[swap_params])
            calls.append((self.router.address, call_data))

        safe_nonce = await self.nonce_manager.reserve_nonce(self.w3)
        gas_params = await self._get_gas_params()
        tx = await multicall.functions.tryAggregate(False, calls).build_transaction({
            "from": self.account.address,
            "gas": 500000 * len(swaps),
            "nonce": safe_nonce,
            **gas_params,
        })
        signed = self.w3.eth.account.sign_transaction(tx, self.private_key)
        tx_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
        logger.info(f"Batch swap tx sent: {tx_hash.hex()} with {len(swaps)} swaps")

        receipt = await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        if receipt.status == 1:
            logger.success(f"✅ Batch swap successful! Tx: {tx_hash.hex()}")
            await self.nonce_manager.update_nonce_async(receipt)
            return {"tx_hash": tx_hash.hex(), "status": "success"}
        else:
            logger.error(f"❌ Batch swap reverted. Tx: {tx_hash.hex()}")
            await self.nonce_manager.sync_with_chain_async(
                await self.w3.eth.get_transaction_count(self.account.address, "pending")
            )
            return {"tx_hash": tx_hash.hex(), "status": "failed"}