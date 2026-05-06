# adapters/web3_testnet.py
"""
Web3 Testnet Adapter (Arbitrum Sepolia) — реальная работа с Uniswap V3.
Подключается через web3.py, запрашивает цену через Quoter, выполняет свопы.
"""
import os
import logging
from typing import Dict, Optional
from web3 import Web3
from web3.middleware import geth_poa_middleware

logger = logging.getLogger(__name__)

# Адреса контрактов Uniswap V3 в Arbitrum Sepolia
UNISWAP_QUOTER_ADDRESS = "0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6"
UNISWAP_SWAP_ROUTER_ADDRESS = "0xE592427A0AEce92De3Edee1F18E0157C05861564"

# ABI для Quoter V2
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

# ABI для SwapRouter02 (упрощённый)
ROUTER_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "address", "name": "tokenIn", "type": "address"},
                    {"internalType": "address", "name": "tokenOut", "type": "address"},
                    {"internalType": "uint24", "name": "fee", "type": "uint24"},
                    {"internalType": "address", "name": "recipient", "type": "address"},
                    {"internalType": "uint256", "name": "deadline", "type": "uint256"},
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

class Web3TestnetAdapter:
    """Адаптер для Uniswap V3 на Arbitrum Sepolia."""

    def __init__(self, symbol: str = "WETH/USDC"):
        self.symbol = symbol
        self.rpc_url = os.environ.get("WEB3_RPC_URL", "https://sepolia-rollup.arbitrum.io/rpc")
        self.private_key = os.environ.get("WEB3_PRIVATE_KEY")
        self.token_in = os.environ.get("WEB3_TOKEN_IN", "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1")  # WETH
        self.token_out = os.environ.get("WEB3_TOKEN_OUT", "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8")  # USDC

        if not self.private_key:
            logger.warning("WEB3_PRIVATE_KEY not set. Web3 adapter will run in read-only mode.")

        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        # Arbitrum требует PoA middleware
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        if self.private_key:
            self.account = self.w3.eth.account.from_key(self.private_key)
            self.w3.eth.default_account = self.account.address
        else:
            self.account = None

        # Контракты
        self.quoter = self.w3.eth.contract(
            address=self.w3.to_checksum_address(UNISWAP_QUOTER_ADDRESS),
            abi=QUOTER_ABI,
        )
        self.router = self.w3.eth.contract(
            address=self.w3.to_checksum_address(UNISWAP_SWAP_ROUTER_ADDRESS),
            abi=ROUTER_ABI,
        )

    async def get_ticker(self) -> Optional[Dict[str, float]]:
        """Возвращает цену через Uniswap Quoter (симулируем обмен 1 WETH на USDC)."""
        try:
            # 1 WETH = 10**18 wei
            amount_in = self.w3.to_wei(1, "ether")
            # Кодируем путь: token_in (20 байт) + fee (3 байта) + token_out (20 байт)
            path = (
                self.w3.to_bytes(hexstr=self.token_in).rjust(20, b'\0')
                + (3000).to_bytes(3, 'big')  # fee = 0.3%
                + self.w3.to_bytes(hexstr=self.token_out).rjust(20, b'\0')
            )
            amount_out = self.quoter.functions.quoteExactInput(path, amount_in).call()
            price = amount_out / 10**6  # USDC имеет 6 десятичных знаков
            return {
                "price": price,
                "symbol": self.symbol,
                "timestamp": None,
            }
        except Exception as e:
            logger.error(f"Web3 get_ticker failed: {e}")
            return None

    def place_order(self, side: str, amount: float, price: Optional[float] = None) -> Dict:
        """Выполняет своп через Uniswap SwapRouter."""
        if not self.account:
            return {"error": "WEB3_PRIVATE_KEY not set"}

        try:
            amount_in = self.w3.to_wei(amount, "ether") if side == "buy" else self.w3.to_wei(amount * (price or 1), "ether")
            # amount_out_minimum – в реальности должно рассчитываться с учётом slippage
            amount_out_minimum = 0
            deadline = self.w3.eth.get_block('latest')['timestamp'] + 600  # 10 минут

            txn = self.router.functions.exactInputSingle(
                (
                    self.token_in,
                    self.token_out,
                    3000,
                    self.account.address,
                    deadline,
                    amount_in,
                    amount_out_minimum,
                    0,
                )
            ).build_transaction({
                'from': self.account.address,
                'gas': 300000,
                'maxFeePerGas': self.w3.eth.gas_price,
                'maxPriorityFeePerGas': self.w3.eth.max_priority_fee,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
            })

            signed_txn = self.w3.eth.account.sign_transaction(txn, private_key=self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            return {"tx_hash": self.w3.to_hex(tx_hash)}
        except Exception as e:
            logger.error(f"Web3 swap failed: {e}")
            return {"error": str(e)}

    def fetch_balance(self) -> Dict[str, float]:
        """Возвращает баланс ETH."""
        if not self.account:
            return {}
        try:
            balance_wei = self.w3.eth.get_balance(self.account.address)
            return {"ETH": self.w3.from_wei(balance_wei, "ether")}
        except Exception as e:
            logger.error(f"Web3 balance fetch failed: {e}")
            return {}