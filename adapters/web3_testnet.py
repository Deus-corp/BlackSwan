"""
Web3 Testnet Adapter (Ethereum Sepolia) – полностью асинхронный Uniswap V3 адаптер.
Использует AsyncWeb3, NonceManager и новый конфиг.
"""
import asyncio
from typing import Dict, Optional, Any, List, Tuple
from web3 import AsyncWeb3
from web3.providers import AsyncHTTPProvider
from web3.middleware import ExtraDataToPOAMiddleware
from web3.types import TxReceipt, Wei
from web3.contract import Contract # Added specific web3 type for contracts
from loguru import logger

from swarm_config import config
from adapters.nonce_manager import NonceManager

# ---------- Константы Uniswap V3 Sepolia ----------
QUOTER_ADDRESS = "0xd64686fa7549534ecb1b5cdd772d60c3cf02af3c"
ROUTER_ADDRESS = "0x3bFA4769FB09eefC5a80d6E87c3B9C650f7Ae48E"
WETH_ADDRESS = "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14"
USDC_ADDRESS = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"
MULTICALL_ADDRESS = "0xcA11bde05977b3631167028862bE2a173976CA11" # Multicall3 contract address for Sepolia

QUOTER_ABI: List[Dict[str, Any]] = [
    {"inputs": [{"internalType": "bytes","name": "path","type": "bytes"},
                {"internalType": "uint256","name": "amountIn","type": "uint256"}],
     "name": "quoteExactInput","outputs": [{"internalType": "uint256","name": "amountOut","type": "uint256"}],
     "stateMutability": "nonpayable","type": "function"}
]

ROUTER_ABI: List[Dict[str, Any]] = [
    {"inputs": [{"components": [
        {"internalType": "address","name": "tokenIn","type": "address"},
        {"internalType": "address","name": "tokenOut","type": "address"},
        {"internalType": "uint24","name": "fee","type": "uint24"},
        {"internalType": "address","name": "recipient","type": "address"},
        {"internalType": "uint256","name": "amountIn","type": "uint256"},
        {"internalType": "uint256","name": "amountOutMinimum","type": "uint256"},
        {"internalType": "uint160","name": "sqrtPriceLimitX96","type": "uint160"}
    ],"internalType": "struct ISwapRouter.ExactInputSingleParams","name": "params","type": "tuple"}],
     "name": "exactInputSingle","outputs": [{"internalType": "uint256","name": "amountOut","type":"uint256"}],
     "stateMutability": "payable","type":"function"}
]

ERC20_ABI: List[Dict[str, Any]] = [
    {"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"},
    {"constant":True,"inputs":[{"name":"_owner","type":"address"},{"name":"_spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"type":"function"},
    {"constant":False,"inputs":[{"name":"_spender","type":"address"},{"name":"_value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"type":"function"},
]

WETH9_ABI: List[Dict[str, Any]] = [
    {"constant":False,"inputs":[],"name":"deposit","outputs":[],"type":"function"},
    {"constant":False,"inputs":[{"name":"wad","type":"uint256"}],"name":"withdraw","outputs":[],"type":"function"},
]

MULTICALL_ABI: List[Dict[str, Any]] = [
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


class Web3TestnetAdapter:
    """
    Адаптер для взаимодействия с Uniswap V3 на тестовой сети Ethereum Sepolia.
    Поддерживает получение котировок, проверку балансов, оборачивание/разворачивание ETH/WETH
    и выполнение свопов (покупка/продажа WETH/USDC).

    Основные возможности:
    - Асинхронное подключение к Sepolia RPC.
    - Управление аккаунтом и nonce для безопасных транзакций.
    - Получение текущих цен WETH/USDC.
    - Проверка и управление балансами ETH, WETH, USDC.
    - Оборачивание ETH в WETH и разворачивание WETH в ETH.
    - Выполнение одиночных свопов WETH/USDC через Uniswap V3 Router.
    - Выполнение пакетных свопов WETH/USDC через Multicall3.
    """
    def __init__(self, symbol: str = "WETH/USDC", crdt_adapter: Any = None):
        """
        Инициализирует Web3TestnetAdapter.
        :param symbol: Торговая пара, например "WETH/USDC". Используется для идентификации,
                       но не меняет логику работы с WETH/USDC адресами по умолчанию.
        :param crdt_adapter: Опциональный адаптер CRDT. Не используется в этом классе,
                             но предусмотрен для совместимости.
        """
        self.crdt = crdt_adapter
        self.symbol: str = symbol
        self.rpc_url: str = config.web3_rpc_url
        self.private_key: Optional[str] = (
            config.security.web3_private_key.get_secret_value()
            if config.security.web3_private_key
            else None
        )
        self.token_in_env: str = WETH_ADDRESS # Default 'token in' for quote and sell
        self.token_out_env: str = USDC_ADDRESS # Default 'token out' for quote and sell

        if not self.private_key:
            logger.warning("WEB3_PRIVATE_KEY not set. Web3 adapter will run in read-only mode (no transactions).")

        self.w3 = AsyncWeb3(AsyncHTTPProvider(self.rpc_url, request_kwargs={"timeout": 60}))
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        self.account: Optional[Any] = None # Stores w3.eth.account.LocalAccount object
        self.nonce_manager: Optional[NonceManager] = None
        self.quoter: Optional[Contract] = None # Web3 contract instance for Quoter
        self.router: Optional[Contract] = None # Web3 contract instance for Router
        self.weth_contract: Optional[Contract] = None # Web3 contract instance for WETH
        self.usdc_contract: Optional[Contract] = None # Web3 contract instance for USDC
        self.multicall_contract: Optional[Contract] = None # Web3 contract instance for Multicall3

    async def initialize(self) -> None:
        """
        Асинхронная инициализация адаптера.
        Подключается к блокчейну, инициализирует аккаунт (если private_key предоставлен)
        и контракты Uniswap V3 (Quoter, Router, WETH, USDC) и Multicall3.
        Должен быть вызван при старте ноды.
        """
        for attempt in range(3):
            try:
                chain_id: int = await self.w3.eth.chain_id
                break
            except Exception as e:
                if attempt < 2:
                    logger.warning(f"RPC chain_id failed, retrying ({attempt+1}/3): {e}")
                    await asyncio.sleep(1)
                else:
                    logger.error(f"Failed to connect to chain after multiple retries: {e}")
                    raise

        logger.info(f"Connected to chain ID {chain_id}")

        if self.private_key:
            self.account = self.w3.eth.account.from_key(self.private_key)
            self.nonce_manager = NonceManager(self.account.address)
            self.w3.eth.default_account = self.account.address
            logger.info(f"Wallet: {self.account.address[:8]}...")
        else:
            logger.info("Private key not provided, adapter initialized in read-only mode (no transactions).")

        # Инициализируем контракты (адреса с checksum)
        checksum_quoter: str = self.w3.to_checksum_address(QUOTER_ADDRESS)
        checksum_router: str = self.w3.to_checksum_address(ROUTER_ADDRESS)
        checksum_weth: str = self.w3.to_checksum_address(WETH_ADDRESS)
        checksum_usdc: str = self.w3.to_checksum_address(USDC_ADDRESS)
        checksum_multicall: str = self.w3.to_checksum_address(MULTICALL_ADDRESS)

        self.quoter = self.w3.eth.contract(address=checksum_quoter, abi=QUOTER_ABI)
        self.router = self.w3.eth.contract(address=checksum_router, abi=ROUTER_ABI)
        self.weth_contract = self.w3.eth.contract(address=checksum_weth, abi=ERC20_ABI)
        self.usdc_contract = self.w3.eth.contract(address=checksum_usdc, abi=ERC20_ABI)
        self.multicall_contract = self.w3.eth.contract(address=checksum_multicall, abi=MULTICALL_ABI)

        logger.success("Web3TestnetAdapter initialized (async)")

    # ---------- Помощники ----------
    async def _get_gas_params(self) -> Dict[str, Wei]:
        """
        Получает параметры газа (maxFeePerGas, maxPriorityFeePerGas)
        на основе истории комиссий EIP-1559.
        В случае неудачи возвращает традиционный gasPrice (удвоенный).
        :return: Словарь с параметрами газа (maxFeePerGas, maxPriorityFeePerGas или gasPrice).
        """
        try:
            # max_priority_fee directly fetches the recommended priority fee
            max_priority_fee_per_gas: Wei = await self.w3.eth.max_priority_fee
            
            # Fetch base fee from the latest block's fee history
            fee_history = await self.w3.eth.fee_history(1, "latest", reward_percentiles=[50])
            base_fee_per_gas: Wei = fee_history["baseFeePerGas"][0]

            # maxFeePerGas should be at least (baseFeePerGas + maxPriorityFeePerGas)
            # A common strategy is to set it to 2 * baseFeePerGas + maxPriorityFeePerGas
            max_fee_per_gas: Wei = base_fee_per_gas * 2 + max_priority_fee_per_gas

            return {
                "maxFeePerGas": max_fee_per_gas,
                "maxPriorityFeePerGas": max_priority_fee_per_gas,
            }
        except Exception as e:
            # Fallback to legacy gasPrice if EIP-1559 parameters cannot be fetched
            gas_price: Wei = await self.w3.eth.gas_price
            logger.warning(f"Failed to fetch EIP-1559 gas params ({e}), falling back to legacy gas price.")
            # Double the current gas price for a slightly more competitive legacy transaction
            return {"gasPrice": int(gas_price * 2.0)}

    async def _send_transaction_and_wait(self, tx: Dict[str, Any], description: str, timeout: int = 180) -> Optional[TxReceipt]:
        """
        Хелпер для отправки подписанной транзакции и ожидания квитанции с ретраями.
        
        :param tx: Подготовленная транзакция.
        :param description: Описание транзакции для логгирования.
        :param timeout: Максимальное время ожидания квитанции.
        :return: Объект TxReceipt, если транзакция успешна, иначе None.
        """
        if not self.account or not self.private_key or not self.nonce_manager:
            logger.error("Account, private key, or NonceManager not initialized for transaction.")
            return None

        try:
            signed = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
            logger.info(f"{description} tx sent: {tx_hash.hex()}")

            receipt: Optional[TxReceipt] = None
            for attempt in range(3):
                try:
                    receipt = await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout, poll_latency=1.0)
                    break
                except Exception as e:
                    if attempt < 2:
                        logger.warning(
                            f"RPC wait_for_transaction_receipt failed for {tx_hash.hex()}, retrying ({attempt+1}/3): {e}"
                        )
                        await asyncio.sleep(2 ** attempt)
                    else:
                        logger.error(f"Failed to get transaction receipt for {tx_hash.hex()} after multiple retries: {e}")
                        raise # Re-raise after final failure to ensure exception handling below catches it

            if receipt and receipt.status == 1:
                logger.success(f"✅ {description} successful. Tx: {tx_hash.hex()}")
                await self.nonce_manager.update_nonce_async(receipt)
                return receipt
            else:
                status_text: str = "reverted" if receipt else "timeout"
                logger.error(f"❌ {description} {status_text}. Tx: {tx_hash.hex()}")
                # Sync nonce after a failed transaction to ensure consistency for future transactions
                await self._sync_nonce_after_failure()
                return None

        except Exception as e:
            logger.error(f"{description} error: {e}")
            await self._sync_nonce_after_failure()
            return None
    
    async def _sync_nonce_after_failure(self) -> None:
        """
        Синхронизирует nonce с блокчейном после неудачной транзакции или исключения.
        """
        if self.nonce_manager and self.account:
            for attempt in range(3):
                try:
                    pending_nonce: int = await self.w3.eth.get_transaction_count(
                        self.account.address, "pending"
                    )
                    await self.nonce_manager.sync_with_chain_async(pending_nonce)
                    logger.info(f"Nonce synced to {pending_nonce} after transaction failure.")
                    break
                except Exception as e2:
                    if attempt < 2:
                        logger.warning(
                            f"RPC get_transaction_count failed during nonce sync, retrying ({attempt+1}/3): {e2}"
                        )
                        await asyncio.sleep(1)
                    else:
                        logger.error(f"Failed to sync nonce after transaction failure: {e2}")

    async def _ensure_allowance(self, token_address: str, spender: str, amount: int) -> bool:
        """
        Проверяет текущий allowance для токена и, если он недостаточен,
        отправляет транзакцию на утверждение максимального allowance (2^256 - 1).
        
        :param token_address: Адрес токена ERC-20.
        :param spender: Адрес контракта, которому дается разрешение (например, Uniswap Router).
        :param amount: Необходимая сумма allowance в Wei (или наименьших единицах токена).
                       Используется для проверки, но при утверждении устанавливается max allowance.
        :return: True, если allowance достаточно или успешно утвержден, иначе False.
        """
        if not self.account or not self.private_key or not self.nonce_manager:
            logger.error("Account, private key, or NonceManager not initialized for _ensure_allowance.")
            return False

        token: Contract = self.w3.eth.contract(address=self.w3.to_checksum_address(token_address), abi=ERC20_ABI)
        current_allowance: int = await token.functions.allowance(self.account.address, spender).call()

        if current_allowance >= amount:
            return True

        logger.info(f"Approving {spender[:8]}... for max allowance (needed: {amount}, current: {current_allowance})...")
        nonce_n: int = await self.nonce_manager.reserve_nonce(self.w3)
        gas_params: Dict[str, Wei] = await self._get_gas_params()

        approve_tx = await token.functions.approve(spender, 2**256 - 1).build_transaction({
            "from": self.account.address,
            "gas": 100000, # A standard gas limit for ERC-20 approve
            "nonce": nonce_n,
            **gas_params,
        })
        
        receipt: Optional[TxReceipt] = await self._send_transaction_and_wait(approve_tx, "Approve", timeout=180)
        return receipt is not None

    # ---------- Получение данных ----------
    async def get_ticker(self) -> Optional[Dict[str, float]]:
        """
        Получает текущую цену WETH/USDC, используя Quoter контракт Uniswap V3.
        Запрашивает котировку для 1 WETH.
        
        :return: Словарь с ценой и символом, или None в случае ошибки.
        """
        async def _fetch_quote_once() -> Optional[Dict[str, float]]:
            if not self.quoter:
                logger.error("Quoter contract not initialized.")
                return None
            try:
                amount_in: Wei = self.w3.to_wei(1, "ether") # Quote 1 WETH
                fee: int = config.trading.web3_pool_fee # Pool fee, e.g., 500 for 0.05%
                
                # Constructing the path for the swap (WETH -> USDC)
                # This path format is for 'quoteExactInput', which takes a byte path
                path: bytes = (
                    self.w3.to_bytes(hexstr=WETH_ADDRESS).rjust(20, b"\0")
                    + fee.to_bytes(3, "big")
                    + self.w3.to_bytes(hexstr=USDC_ADDRESS).rjust(20, b"\0")
                )
                amount_out: int = await self.quoter.functions.quoteExactInput(path, amount_in).call()
                # USDC has 6 decimals
                price: float = amount_out / (10**6)
                return {"price": price, "symbol": self.symbol}
            except Exception as e:
                logger.error(f"Failed to fetch quote: {e}")
                return None

        # Retry logic for fetching quotes
        for attempt in range(3):
            result = await _fetch_quote_once()
            if result:
                return result
            if attempt < 2:
                logger.warning(f"get_ticker failed, retrying ({attempt+1}/3) in 5s...")
                await asyncio.sleep(5)
            else:
                logger.error("get_ticker failed after multiple retries.")
                return None

    async def _get_token_balance(self, token_address: str) -> float:
        """
        Возвращает баланс указанного ERC-20 токена для текущего аккаунта.
        
        :param token_address: Адрес токена.
        :return: Баланс токена в обычных единицах (не Wei). Возвращает 0.0, если аккаунт не инициализирован.
        """
        if not self.account:
            return 0.0 # No account, no balance

        # Use direct contract references if available, otherwise construct on-the-fly
        contract: Contract
        if token_address.lower() == WETH_ADDRESS.lower() and self.weth_contract:
            contract = self.weth_contract
        elif token_address.lower() == USDC_ADDRESS.lower() and self.usdc_contract:
            contract = self.usdc_contract
        else:
            # Fallback for other ERC20s or if direct references are None (though they should be init)
            contract = self.w3.eth.contract(address=self.w3.to_checksum_address(token_address), abi=ERC20_ABI)
        
        balance_wei: int = await contract.functions.balanceOf(self.account.address).call()
        # Determine decimals: WETH (ETH equivalent) has 18, USDC has 6
        decimals: int = 18 if token_address.lower() == WETH_ADDRESS.lower() else 6
        return balance_wei / (10**decimals)

    async def fetch_balance(self) -> Dict[str, float]:
        """
        Получает балансы ETH, WETH и USDC для текущего аккаунта.
        
        :return: Словарь с балансами ("ETH", "WETH", "USDC"). Возвращает пустой словарь, если аккаунт не инициализирован.
        """
        if not self.account:
            logger.warning("Account not initialized, cannot fetch balances.")
            return {}
        
        eth_balance: float = self.w3.from_wei(await self.w3.eth.get_balance(self.account.address), "ether")
        weth_balance: float = await self._get_token_balance(WETH_ADDRESS)
        usdc_balance: float = await self._get_token_balance(USDC_ADDRESS)
        return {"ETH": eth_balance, "WETH": weth_balance, "USDC": usdc_balance}

    # ---------- Wrap / Unwrap ----------
    async def wrap_eth(self, amount_eth: float) -> Optional[str]:
        """
        Оборачивает нативный ETH в WETH (Wrapped Ether).
        
        :param amount_eth: Количество ETH для оборачивания.
        :return: Хэш транзакции, если успешно, иначе None.
        """
        if not self.account or not self.private_key or not self.nonce_manager or not self.weth_contract:
            logger.error("Adapter not fully initialized (account/private_key/nonce_manager/weth_contract missing) for wrap_eth.")
            return None
        try:
            value: Wei = self.w3.to_wei(amount_eth, 'ether')
            nonce: int = await self.nonce_manager.reserve_nonce(self.w3)
            gas_params: Dict[str, Wei] = await self._get_gas_params()
            
            tx = await self.weth_contract.functions.deposit().build_transaction({
                'from': self.account.address,
                'value': value,
                'gas': 50000, # Standard gas limit for WETH deposit
                'nonce': nonce,
                **gas_params,
            })
            receipt = await self._send_transaction_and_wait(tx, f"Wrap {amount_eth} ETH → WETH", timeout=120)
            return receipt.transactionHash.hex() if receipt else None
        except Exception as e:
            logger.error(f"Wrap error for {amount_eth} ETH: {e}")
            return None

    async def unwrap_weth(self, amount_weth: float) -> Optional[str]:
        """
        Разворачивает WETH (Wrapped Ether) обратно в нативный ETH.
        
        :param amount_weth: Количество WETH для разворачивания.
        :return: Хэш транзакции, если успешно, иначе None.
        """
        if not self.account or not self.private_key or not self.nonce_manager or not self.weth_contract:
            logger.error("Adapter not fully initialized (account/private_key/nonce_manager/weth_contract missing) for unwrap_weth.")
            return None
        try:
            value: Wei = self.w3.to_wei(amount_weth, 'ether')
            nonce: int = await self.nonce_manager.reserve_nonce(self.w3)
            gas_params: Dict[str, Wei] = await self._get_gas_params()
            
            tx = await self.weth_contract.functions.withdraw(value).build_transaction({
                'from': self.account.address,
                'gas': 50000, # Standard gas limit for WETH withdraw
                'nonce': nonce,
                **gas_params,
            })
            receipt = await self._send_transaction_and_wait(tx, f"Unwrap {amount_weth} WETH → ETH", timeout=120)
            return receipt.transactionHash.hex() if receipt else None
        except Exception as e:
            logger.error(f"Unwrap error for {amount_weth} WETH: {e}")
            return None

    # ---------- Основной своп ----------
    async def place_order(self, side: str, amount: float, price: Optional[float] = None) -> Dict[str, str]:
        """
        Размещает ордер на своп WETH/USDC через Uniswap V3 Router (exactInputSingle).
        
        :param side: Сторона ордера ("buy" для покупки WETH за USDC, "sell" для продажи WETH за USDC).
                     "Buy" подразумевает ввод USDC для получения WETH.
                     "Sell" подразумевает ввод WETH для получения USDC.
        :param amount: Количество WETH для покупки/продажи (в ETH единицах, т.е. 18 десятичных знаков).
                       Для "buy" это целевое количество WETH, которое будет куплено,
                       на основе которого будет рассчитано необходимое количество USDC.
        :param price: Опциональная целевая цена. Не используется для прямого ограничения slippage,
                      но используется для оценки количества USDC при покупке WETH.
        :return: Словарь с информацией о транзакции (tx_hash, status) или ошибкой.
        """
        if not self.account or not self.nonce_manager or not self.private_key or not self.router:
            return {"error": "WEB3_PRIVATE_KEY not set or adapter not fully initialized for transactions"}

        try:
            fee: int = config.trading.web3_pool_fee
            token_in_addr: str
            token_out_addr: str
            amount_in_exact_units: int # Amount to input in smallest token units (e.g., wei for WETH, 10^6 for USDC)
            amount_out_minimum: int = 0 # NOTE: Setting to 0 allows for maximum slippage. In production,
                                        # calculate a realistic min_amount_out based on acceptable slippage.

            if side.lower() == "sell": # Sell WETH, get USDC
                token_in_addr = WETH_ADDRESS
                token_out_addr = USDC_ADDRESS
                amount_in_exact_units = self.w3.to_wei(amount, "ether") # WETH has 18 decimals
            elif side.lower() == "buy": # Buy WETH, pay with USDC
                token_in_addr = USDC_ADDRESS
                token_out_addr = WETH_ADDRESS
                # Fetch current price to estimate USDC needed to buy 'amount' of WETH
                ticker = await self.get_ticker()
                estimated_price: float = ticker["price"] if ticker else 2000.0 # Fallback price
                
                # Calculate USDC needed to buy 'amount' (of WETH)
                usdc_needed_float: float = amount * estimated_price
                amount_in_exact_units = int(usdc_needed_float * (10**6)) # USDC has 6 decimals
                
                # If buying WETH, need to estimate amount_out_minimum for WETH.
                # For simplicity and to match original "max slippage" behavior, setting to 0.
                # In a real system, calculate:
                # amount_out_minimum = int(amount * (1 - slippage_tolerance) * (10**18))
            else:
                return {"error": f"Unsupported trade side: {side}. Must be 'buy' or 'sell'."}

            # Проверка баланса
            current_balance_float: float = await self._get_token_balance(token_in_addr)
            # For comparison with 'amount_in_exact_units', convert back to float with correct decimals
            token_in_decimals: int = 18 if token_in_addr.lower() == WETH_ADDRESS.lower() else 6
            amount_in_float_for_balance_check: float = amount_in_exact_units / (10**token_in_decimals)

            if current_balance_float < amount_in_float_for_balance_check:
                logger.warning(
                    f"Insufficient {token_in_addr} balance ({current_balance_float:.6f} "
                    f"available, {amount_in_float_for_balance_check:.6f} needed for {side} {amount} WETH)"
                )
                return {"error": "Insufficient balance"}

            # Allowance check and approval if needed
            if not await self._ensure_allowance(token_in_addr, ROUTER_ADDRESS, amount_in_exact_units):
                return {"error": "Failed to ensure sufficient allowance for router."}

            safe_nonce: int = await self.nonce_manager.reserve_nonce(self.w3)
            gas_params: Dict[str, Wei] = await self._get_gas_params()

            # Construct the swap parameters tuple for exactInputSingle
            swap_tuple: Tuple[str, str, int, str, int, int, int] = (
                self.w3.to_checksum_address(token_in_addr),
                self.w3.to_checksum_address(token_out_addr),
                fee,
                self.account.address,
                amount_in_exact_units,
                amount_out_minimum, # Allows for max slippage. In production, calculate a min_amount_out.
                0 # sqrtPriceLimitX96 (0 means no limit on price)
            )

            tx = await self.router.functions.exactInputSingle(swap_tuple).build_transaction({
                "from": self.account.address,
                "gas": 300000, # A generous gas limit for swaps
                "nonce": safe_nonce,
                **gas_params,
            })

            receipt: Optional[TxReceipt] = await self._send_transaction_and_wait(tx, f"Swap (side: {side}, amount: {amount})", timeout=180)
            
            if receipt:
                return {"tx_hash": receipt.transactionHash.hex(), "status": "success"}
            else:
                return {"status": "failed", "error": "Transaction failed or timed out."}

        except Exception as e:
            logger.error(f"Swap exception for side {side}, amount {amount}: {e}")
            await self._sync_nonce_after_failure() # Ensure nonce is synced even if error before tx sent
            return {"error": str(e)}
        
    async def batch_swap(self, swaps: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Выполняет пакетные свопы через контракт Multicall3, агрегируя несколько вызовов `exactInputSingle`.
        
        ВАЖНО: Этот метод не выполняет проверку балансов или allowance внутри себя.
        Предполагается, что allowance был заранее одобрен для каждого `token_in`
        к `ROUTER_ADDRESS` для всех сумм в пакете.
        Также ожидается, что у аккаунта есть достаточный ETH для оплаты газа за всю пакетную транзакцию.

        :param swaps: Список словарей, каждый из которых описывает параметры одного свопа.
                      Каждый словарь должен содержать:
                      - "token_in": адрес токена входа (str)
                      - "token_out": адрес токена выхода (str)
                      - "fee": комиссия пула Uniswap V3 (int)
                      - "amount_in_wei": количество токена входа в наименьших единицах (int)
                      - "amount_out_min": минимальное ожидаемое количество токена выхода (int, 0 для максимального проскальзывания)
        :return: Словарь с информацией о пакетной транзакции (tx_hash, status) или ошибкой.
        """
        if not self.account or not self.nonce_manager or not self.private_key or not self.router or not self.multicall_contract:
            return {"error": "Adapter not fully initialized for batch swap"}

        calls: List[Tuple[str, bytes]] = []
        for i, s in enumerate(swaps):
            required_keys = ["token_in", "token_out", "fee", "amount_in_wei", "amount_out_min"]
            if not all(key in s for key in required_keys):
                logger.error(f"Swap at index {i} is missing required keys. Required: {required_keys}, Got: {s.keys()}")
                return {"error": f"Invalid swap parameters at index {i}"}

            # Construct the swap parameters tuple for exactInputSingle for each swap in the batch
            swap_params: Tuple[str, str, int, str, int, int, int] = (
                self.w3.to_checksum_address(s["token_in"]),
                self.w3.to_checksum_address(s["token_out"]),
                s["fee"],
                self.account.address,
                s["amount_in_wei"],
                s["amount_out_min"], # Allows for max slippage. In production, calculate a min_amount_out.
                0 # sqrtPriceLimitX96 (0 means no limit on price)
            )
            # Encode the call data for exactInputSingle function
            call_data: bytes = self.router.encode_abi('exactInputSingle', args=[swap_params])
            calls.append((self.router.address, call_data))

        if not calls:
            return {"error": "No swaps provided for batch_swap."}

        safe_nonce: int = await self.nonce_manager.reserve_nonce(self.w3)
        gas_params: Dict[str, Wei] = await self._get_gas_params()

        try:
            # Call tryAggregate with requireSuccess=False so that if one swap fails, others might still succeed.
            # Multicall3 contract address is used for the transaction target.
            tx = await self.multicall_contract.functions.tryAggregate(False, calls).build_transaction({
                "from": self.account.address,
                "gas": 500000 * len(swaps), # Dynamic gas limit based on number of swaps, very generous
                "nonce": safe_nonce,
                **gas_params,
            })
            
            receipt: Optional[TxReceipt] = await self._send_transaction_and_wait(tx, f"Batch Swap ({len(swaps)} swaps)", timeout=300)
            
            if receipt:
                return {"tx_hash": receipt.transactionHash.hex(), "status": "success"}
            else:
                return {"status": "failed", "error": "Batch transaction failed or timed out."}
        
        except Exception as e:
            logger.error(f"Batch swap exception: {e}")
            await self._sync_nonce_after_failure()
            return {"error": str(e)}