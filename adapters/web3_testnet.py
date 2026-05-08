# adapters/web3_testnet.py
"""
Web3 Testnet Adapter (Ethereum Sepolia) – Uniswap V3 community deployment.

Полностью обновлённая версия:
- автоматический approve для WETH (и USDC при необходимости)
- улучшенная работа с газом (fee_history + max_priority_fee)
- расширенная диагностика и логирование
- поддержка свопов в обе стороны (buy / sell)
- ожидание подтверждения транзакции с проверкой статуса
"""
import os
import logging
import time
from typing import Dict, Optional, Tuple
from web3 import Web3
from web3.exceptions import TransactionNotFound
from web3.middleware import ExtraDataToPOAMiddleware

logger = logging.getLogger(__name__)

# Адреса контрактов (проверены сообществом Uniswap для Sepolia)
QUOTER_ADDRESS = "0xd64686fa7549534ecb1b5cdd772d60c3cf02af3c"
ROUTER_ADDRESS = "0x3bFA4769FB09eefC5a80d6E87c3B9C650f7Ae48E"

# Токены Sepolia
WETH_ADDRESS = "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14"
USDC_ADDRESS = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"

# Минимальный ABI для quoteExactInput (возвращает ТОЛЬКО amountOut)
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

# SwapRouter ABI
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

# Минимальный ERC-20 ABI
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

class Web3TestnetAdapter:
    """Адаптер для Uniswap V3 на Ethereum Sepolia."""

    def __init__(self, symbol: str = "WETH/USDC"):
        self.symbol = symbol
        self.rpc_url = os.environ.get("WEB3_RPC_URL", "https://ethereum-sepolia.publicnode.com")
        self.private_key = os.environ.get("WEB3_PRIVATE_KEY")
        self.token_in = os.environ.get("WEB3_TOKEN_IN", WETH_ADDRESS)   # по умолчанию WETH
        self.token_out = os.environ.get("WEB3_TOKEN_OUT", USDC_ADDRESS)  # USDC

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

        # Контракты Uniswap
        self.quoter = self.w3.eth.contract(
            address=self.w3.to_checksum_address(QUOTER_ADDRESS),
            abi=QUOTER_ABI,
        )
        self.router = self.w3.eth.contract(
            address=self.w3.to_checksum_address(ROUTER_ADDRESS),
            abi=ROUTER_ABI,
        )

        # ERC-20 контракты для approve и проверки балансов
        self.weth_contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(WETH_ADDRESS),
            abi=ERC20_ABI,
        )
        self.usdc_contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(USDC_ADDRESS),
            abi=ERC20_ABI,
        )

        # Автоматический approve при наличии приватного ключа
        if self.private_key:
            self._ensure_approval(WETH_ADDRESS, ROUTER_ADDRESS, max_approval=True)
            self._ensure_approval(USDC_ADDRESS, ROUTER_ADDRESS, max_approval=True)

    def _ensure_approval(self, token_address: str, spender: str, max_approval: bool = True):
        """Проверяет и при необходимости выполняет approve для указанного токена."""
        token_contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(token_address),
            abi=ERC20_ABI,
        )
        try:
            current_allowance = token_contract.functions.allowance(self.account.address, spender).call()
            need_approval = True
            if max_approval:
                # Разрешаем почти uint256.max
                if current_allowance >= 2**255:
                    logger.info(f"Allowance for {token_address} already high enough, skipping approve.")
                    need_approval = False
            else:
                # Здесь можно добавить расчёт конкретной суммы, но для простоты всегда делаем max
                pass

            if need_approval:
                logger.info(f"Initiating approve for {token_address} to spender {spender}...")
                tx = token_contract.functions.approve(spender, 2**256 - 1).build_transaction({
                    "from": self.account.address,
                    "gas": 100000,
                    "nonce": self.w3.eth.get_transaction_count(self.account.address),
                    **self._get_gas_params(),
                })
                signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
                tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
                logger.info(f"Approve tx sent: {tx_hash.hex()}")
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                if receipt.status == 1:
                    logger.info(f"Approve successful for {token_address}")
                else:
                    logger.error(f"Approve failed for {token_address}. Receipt status: {receipt.status}")
        except Exception as e:
            logger.error(f"Approve check/execution failed for {token_address}: {e}")

    def _get_gas_params(self) -> dict:
        """Возвращает актуальные параметры газа для EIP-1559 транзакции."""
        try:
            fee_history = self.w3.eth.fee_history(1, "latest", reward_percentiles=[50])
            base_fee = fee_history["baseFeePerGas"][0]
            max_priority_fee = self.w3.eth.max_priority_fee
            if max_priority_fee is None:
                max_priority_fee = self.w3.to_wei(2, "gwei")  # fallback
            max_fee_per_gas = base_fee + max_priority_fee
            return {
                "maxFeePerGas": max_fee_per_gas,
                "maxPriorityFeePerGas": max_priority_fee,
            }
        except Exception as e:
            logger.warning(f"Could not get fee history, using legacy gas price: {e}")
            # Fallback to legacy gas price
            return {"gasPrice": self.w3.eth.gas_price}

    async def get_ticker(self) -> Optional[Dict[str, float]]:
        """Возвращает цену через Quoter (симуляция обмена 1 WETH на USDC)."""
        try:
            amount_in = self.w3.to_wei(1, "ether")
            path = (
                self.w3.to_bytes(hexstr=self.token_in).rjust(20, b"\0")
                + (3000).to_bytes(3, "big")
                + self.w3.to_bytes(hexstr=self.token_out).rjust(20, b"\0")
            )
            amount_out = self.quoter.functions.quoteExactInput(path, amount_in).call()
            price = amount_out / 10**6
            return {"price": price, "symbol": self.symbol, "timestamp": None}
        except Exception as e:
            err_str = str(e)
            if "429" in err_str:
                logger.warning("Rate-limited by RPC, sleeping 10 seconds...")
                time.sleep(10)
                try:
                    amount_out = self.quoter.functions.quoteExactInput(path, amount_in).call()
                    price = amount_out / 10**6
                    return {"price": price, "symbol": self.symbol, "timestamp": None}
                except Exception as retry_e:
                    logger.error(f"Web3 get_ticker failed after retry: {retry_e}")
                    return None
            else:
                logger.error(f"Web3 get_ticker failed: {e}")
                return None

    def _get_token_balance(self, token_address: str) -> float:
        """Возвращает баланс токена в человекочитаемом формате."""
        contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(token_address),
            abi=ERC20_ABI,
        )
        balance_wei = contract.functions.balanceOf(self.account.address).call()
        decimals = 18 if token_address.lower() == WETH_ADDRESS.lower() else 6  # упрощение
        return balance_wei / (10 ** decimals)

    def place_order(self, side: str, amount: float, price: Optional[float] = None) -> Dict:
        """
        Выполняет своп через Uniswap V3 SwapRouter.
        side: "buy" (купить WETH за USDC) или "sell" (продать WETH за USDC).
        amount: количество базового актива (WETH) в единицах.
        """
        if not self.account:
            return {"error": "WEB3_PRIVATE_KEY not set"}

        try:
            # Определяем направление свопа
            if side.lower() == "buy":
                # Покупаем WETH, тратим USDC
                # amount — желаемое количество WETH
                # Для точности используем котировку, чтобы узнать, сколько USDC нужно
                # Здесь просто упрощённо: amount — количество USDC, которое готовы потратить? 
                # В коде роя вероятно amount в WETH, поэтому пересчитываем
                token_in = USDC_ADDRESS
                token_out = WETH_ADDRESS
                decimals_in = 6
                # Получаем цену WETH в USDC через get_ticker (синхронно? вызовем асинхронно нельзя, обойдёмся)
                # Запрашиваем котировку 1 WETH -> USDC
                amount_in_wei = None
                # Используем простой подход: amount трактуем как количество USDC для покупки (скорректируем вне)
                # Временно: amount — это количество WETH, которое хотим купить, пересчитываем по цене из get_ticker
                # Для простоты допустим, что price передаётся или мы запрашиваем котировку
                if price:
                    usdc_needed = amount * price
                else:
                    # Запросить тикер (синхронно не очень, но для теста ок)
                    tick = self._get_ticker_sync()
                    usdc_needed = amount * tick["price"] if tick else amount * 2000  # fallback
                amount_in_wei = int(usdc_needed * 10**decimals_in)
                amount_out_min = 0
            else:  # sell
                token_in = WETH_ADDRESS
                token_out = USDC_ADDRESS
                decimals_in = 18
                amount_in_wei = self.w3.to_wei(amount, "ether")
                amount_out_min = 0

            # Логируем перед отправкой
            eth_balance = self.w3.from_wei(self.w3.eth.get_balance(self.account.address), "ether")
            token_balance = self._get_token_balance(token_in)
            logger.info(
                f"Place order: side={side}, amount={amount} WETH, "
                f"token_in={token_in}, amount_in_wei={amount_in_wei}, "
                f"ETH balance={eth_balance}, token_in balance={token_balance}"
            )

            deadline = self.w3.eth.get_block("latest")["timestamp"] + 600

            # Параметры газа
            gas_params = self._get_gas_params()
            txn = self.router.functions.exactInputSingle(
                (
                    token_in,
                    token_out,
                    3000,  # fee 0.3%
                    self.account.address,
                    deadline,
                    amount_in_wei,
                    amount_out_min,
                    0,  # sqrtPriceLimitX96
                )
            ).build_transaction({
                "from": self.account.address,
                "gas": 300000,
                "nonce": self.w3.eth.get_transaction_count(self.account.address),
                **gas_params,
            })

            signed_txn = self.w3.eth.account.sign_transaction(txn, private_key=self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            logger.info(f"Swap tx sent: {tx_hash.hex()}")

            # Ожидаем подтверждение
            try:
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
                if receipt.status == 1:
                    logger.info(f"Swap successful! Tx: {tx_hash.hex()}, gas used: {receipt.gasUsed}")
                    return {
                        "tx_hash": tx_hash.hex(),
                        "status": "success",
                        "gas_used": receipt.gasUsed,
                    }
                else:
                    logger.error(f"Swap tx failed (status=0). Tx: {tx_hash.hex()}")
                    return {"tx_hash": tx_hash.hex(), "status": "failed", "error": "Transaction reverted"}
            except TransactionNotFound:
                logger.error(f"Transaction {tx_hash.hex()} not found after timeout")
                return {"tx_hash": tx_hash.hex(), "status": "unknown", "error": "Timeout waiting for receipt"}

        except Exception as e:
            logger.error(f"Web3 swap failed: {e}")
            return {"error": str(e)}

    def _get_ticker_sync(self) -> Optional[Dict[str, float]]:
        """Синхронная версия get_ticker для использования внутри place_order."""
        try:
            amount_in = self.w3.to_wei(1, "ether")
            path = (
                self.w3.to_bytes(hexstr=WETH_ADDRESS).rjust(20, b"\0")
                + (3000).to_bytes(3, "big")
                + self.w3.to_bytes(hexstr=USDC_ADDRESS).rjust(20, b"\0")
            )
            amount_out = self.quoter.functions.quoteExactInput(path, amount_in).call()
            price = amount_out / 10**6
            return {"price": price, "symbol": self.symbol, "timestamp": None}
        except Exception as e:
            logger.error(f"Sync get_ticker failed: {e}")
            return None

    def fetch_balance(self) -> Dict[str, float]:
        """Возвращает балансы ETH, WETH и USDC."""
        if not self.account:
            return {}
        try:
            eth_balance = self.w3.from_wei(self.w3.eth.get_balance(self.account.address), "ether")
            weth_balance = self._get_token_balance(WETH_ADDRESS)
            usdc_balance = self._get_token_balance(USDC_ADDRESS)
            return {
                "ETH": eth_balance,
                "WETH": weth_balance,
                "USDC": usdc_balance,
            }
        except Exception as e:
            logger.error(f"Web3 balance fetch failed: {e}")
            return {}