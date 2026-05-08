# adapters/web3_testnet.py
"""
Web3 Testnet Adapter (Ethereum Sepolia) – Uniswap V3 community deployment.

Полностью автономный: автоматический approve, диагностика, выбор fee.
"""
import os
import logging
import time
from typing import Dict, Optional
from web3 import Web3
from web3.exceptions import TransactionNotFound
from web3.middleware import ExtraDataToPOAMiddleware

logger = logging.getLogger(__name__)

QUOTER_ADDRESS = "0xd64686fa7549534ecb1b5cdd772d60c3cf02af3c"
ROUTER_ADDRESS = "0x3bFA4769FB09eefC5a80d6E87c3B9C650f7Ae48E"
WETH_ADDRESS = "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14"
USDC_ADDRESS = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"

QUOTER_ABI = [
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

ROUTER_ABI = [
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

ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
]

class Web3TestnetAdapter:
    def __init__(self, symbol: str = "WETH/USDC"):
        self.symbol = symbol
        self.rpc_url = os.environ.get("WEB3_RPC_URL", "https://ethereum-sepolia.publicnode.com")
        self.private_key = os.environ.get("WEB3_PRIVATE_KEY")
        self.token_in_env = os.environ.get("WEB3_TOKEN_IN", WETH_ADDRESS)
        self.token_out_env = os.environ.get("WEB3_TOKEN_OUT", USDC_ADDRESS)

        if not self.private_key:
            logger.warning("WEB3_PRIVATE_KEY not set. Web3 adapter will run in read-only mode.")

        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        if self.private_key:
            self.account = self.w3.eth.account.from_key(self.private_key)
            logger.info(f"Web3 adapter initialized for address: {self.account.address}")
            self.w3.eth.default_account = self.account.address
        else:
            self.account = None

        self.quoter = self.w3.eth.contract(
            address=self.w3.to_checksum_address(QUOTER_ADDRESS),
            abi=QUOTER_ABI,
        )
        self.router = self.w3.eth.contract(
            address=self.w3.to_checksum_address(ROUTER_ADDRESS),
            abi=ROUTER_ABI,
        )
        self.weth_contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(WETH_ADDRESS),
            abi=ERC20_ABI,
        )
        self.usdc_contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(USDC_ADDRESS),
            abi=ERC20_ABI,
        )

    def _ensure_allowance(self, token_address: str, spender: str, amount: int) -> bool:
        """Проверяет и при необходимости выполняет approve."""
        token_contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(token_address),
            abi=ERC20_ABI,
        )
        try:
            current = token_contract.functions.allowance(self.account.address, spender).call()
            if current >= amount:
                return True
            logger.info(f"Allowance too low ({current} < {amount}), approving max...")
            tx = token_contract.functions.approve(spender, 2**256 - 1).build_transaction({
                "from": self.account.address,
                "gas": 100000,
                "nonce": self.w3.eth.get_transaction_count(self.account.address),
                **self._get_gas_params(),
            })
            signed = self.w3.eth.account.sign_transaction(tx, private_key=self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            logger.info(f"Approve tx sent: {tx_hash.hex()}")
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            if receipt.status == 1:
                logger.info("Approve successful")
                return True
            else:
                logger.error("Approve failed")
                return False
        except Exception as e:
            logger.error(f"Approve exception: {e}")
            return False

    def _get_gas_params(self) -> dict:
        try:
            fee_history = self.w3.eth.fee_history(1, "latest", reward_percentiles=[50])
            base_fee = fee_history["baseFeePerGas"][0]
            max_priority_fee = self.w3.eth.max_priority_fee or self.w3.to_wei(2, "gwei")
            return {
                "maxFeePerGas": base_fee + max_priority_fee,
                "maxPriorityFeePerGas": max_priority_fee,
            }
        except Exception:
            return {"gasPrice": self.w3.eth.gas_price}

    async def get_ticker(self) -> Optional[Dict[str, float]]:
        try:
            amount_in = self.w3.to_wei(1, "ether")
            fee = int(os.environ.get("WEB3_POOL_FEE", 500))
            path = (
                self.w3.to_bytes(hexstr=WETH_ADDRESS).rjust(20, b"\0")
                + fee.to_bytes(3, "big")
                + self.w3.to_bytes(hexstr=USDC_ADDRESS).rjust(20, b"\0")
            )
            amount_out = self.quoter.functions.quoteExactInput(path, amount_in).call()
            price = amount_out / 10**6
            return {"price": price, "symbol": self.symbol, "timestamp": None}
        except Exception as e:
            if "429" in str(e):
                time.sleep(10)
                try:
                    amount_out = self.quoter.functions.quoteExactInput(path, amount_in).call()
                    price = amount_out / 10**6
                    return {"price": price, "symbol": self.symbol, "timestamp": None}
                except Exception as retry_e:
                    logger.error(f"Web3 get_ticker failed after retry: {retry_e}")
                    return None
            logger.error(f"Web3 get_ticker failed: {e}")
            return None

    def _get_token_balance(self, token_address: str) -> float:
        contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(token_address),
            abi=ERC20_ABI,
        )
        balance_wei = contract.functions.balanceOf(self.account.address).call()
        decimals = 18 if token_address.lower() == WETH_ADDRESS.lower() else 6
        return balance_wei / (10**decimals)

    def _get_ticker_sync(self) -> Optional[Dict[str, float]]:
        try:
            fee = int(os.environ.get("WEB3_POOL_FEE", 500))
            amount_in = self.w3.to_wei(1, "ether")
            path = (
                self.w3.to_bytes(hexstr=WETH_ADDRESS).rjust(20, b"\0")
                + fee.to_bytes(3, "big")
                + self.w3.to_bytes(hexstr=USDC_ADDRESS).rjust(20, b"\0")
            )
            amount_out = self.quoter.functions.quoteExactInput(path, amount_in).call()
            price = amount_out / 10**6
            return {"price": price, "symbol": self.symbol, "timestamp": None}
        except Exception as e:
            logger.error(f"Sync get_ticker failed: {e}")
            return None

    def place_order(self, side: str, amount: float, price: Optional[float] = None) -> Dict:
        if not self.account:
            return {"error": "WEB3_PRIVATE_KEY not set"}

        try:
            fee = int(os.environ.get("WEB3_POOL_FEE", 3000))

            # Для теста всегда продаём WETH
            token_in = self.w3.to_checksum_address(WETH_ADDRESS)
            token_out = self.w3.to_checksum_address(USDC_ADDRESS)
            amount_in_wei = self.w3.to_wei(amount, "ether")
            amount_out_min = 0
            deadline = self.w3.eth.get_block("latest")["timestamp"] + 600

            # Проверка allowance
            weth = self.w3.eth.contract(address=token_in, abi=ERC20_ABI)
            if weth.functions.allowance(self.account.address, ROUTER_ADDRESS).call() < amount_in_wei:
                return {"error": "Insufficient allowance"}

            # Порядок полей в кортеже согласно ABI (из Etherscan):
            # tokenIn, tokenOut, fee, recipient, deadline, amountIn, amountOutMinimum, sqrtPriceLimitX96
            swap_tuple = (
                token_in,
                token_out,
                fee,
                self.account.address,
                amount_in_wei,
                amount_out_min,
                0,                     # sqrtPriceLimitX96
            )

            nonce = self.w3.eth.get_transaction_count(self.account.address, "pending")
            tx = self.router.functions.exactInputSingle(swap_tuple).build_transaction({
                "from": self.account.address,
                "gas": 300000,
                "gasPrice": self.w3.eth.gas_price,
                "nonce": nonce,
            })

            signed = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            logger.info(f"Swap tx sent: {tx_hash.hex()}")

            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
            if receipt.status == 1:
                logger.info(f"✅ Swap successful! Tx: {tx_hash.hex()}")
                return {"tx_hash": tx_hash.hex(), "status": "success"}
            else:
                logger.error(f"❌ Swap reverted. Tx: {tx_hash.hex()}")
                return {"tx_hash": tx_hash.hex(), "status": "failed"}
        except Exception as e:
            logger.error(f"Swap exception: {e}")
            return {"error": str(e)}

    def fetch_balance(self) -> Dict[str, float]:
        if not self.account:
            return {}
        try:
            eth_balance = self.w3.from_wei(self.w3.eth.get_balance(self.account.address), "ether")
            weth_balance = self._get_token_balance(WETH_ADDRESS)
            usdc_balance = self._get_token_balance(USDC_ADDRESS)
            return {"ETH": eth_balance, "WETH": weth_balance, "USDC": usdc_balance}
        except Exception as e:
            logger.error(f"Web3 balance fetch failed: {e}")
            return {}