"""
Исполнение на live/web3 (Sepolia через Uniswap V3).
"""
import logging
from typing import Dict, Any, Callable # Added Callable
from .backend import ExecutionBackend

logger = logging.getLogger(__name__)

WETH_ADDRESS = "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14"
USDC_ADDRESS = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"


class LiveExecutionBackend(ExecutionBackend):
    """
    Backend for executing orders on a live Web3 environment (e.g., Sepolia via Uniswap V3).
    It interacts with an adapter to place orders, check balances, and verify leadership status.
    """
    def __init__(self, node_id: str, adapter: Any, is_leader_func: Callable[[int], bool]) -> None:
        """
        Initializes the LiveExecutionBackend.

        Args:
            node_id: Identifier for the current node.
            adapter: An object capable of interacting with the blockchain (e.g., placing orders,
                     getting balances, accessing web3 instance). It's expected to have
                     `_get_token_balance`, `w3.eth.block_number`, and `place_order` methods.
            is_leader_func: A callable that takes a block number (int) and returns a boolean,
                            indicating if the current node is the leader for that block.
        """
        self.node_id = node_id
        self.adapter = adapter
        self.is_leader_func = is_leader_func   # callable (block_number) -> bool

    async def execute_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        capital: float,
    ) -> Dict[str, Any]:
        """
        Executes a trading order on the live blockchain environment.

        Performs checks for adapter availability, balance sufficiency, and leader status
        before attempting to place an order via the adapter.

        Args:
            symbol: The trading pair symbol (e.g., "WETH/USDC"). Note: This parameter
                    is not directly used in the current implementation logic.
            side: The order side ("buy" or "sell").
            amount: The amount of the base asset to trade.
            price: The desired price for the trade.
            capital: The current capital available.

        Returns:
            A dictionary containing the result of the order execution, including success status,
            new capital, transaction hash, execution status, and any error message.
        """
        if not self.adapter or not hasattr(self.adapter, "place_order"):
            logger.error("LiveExecutionBackend requires an adapter with a 'place_order' method.")
            return {
                "success": False,
                "new_capital": capital,
                "tx_hash": None,
                "status": "error",
                "error": "No adapter or adapter missing 'place_order' method",
            }

        # Проверка баланса (как в main_loop)
        if side == "sell":
            try:
                weth_bal: float = await self.adapter._get_token_balance(WETH_ADDRESS)
                amount = min(amount, weth_bal)
            except Exception as e:
                logger.warning(f"Balance check skipped for selling WETH: {e}")

        if amount <= 0:
            return {
                "success": False,
                "new_capital": capital,
                "tx_hash": None,
                "status": "error",
                "error": "Insufficient balance or adjusted amount is zero/negative",
            }

        # Проверка лидера
        try:
            block_number: int = await self.adapter.w3.eth.block_number
            if not self.is_leader_func(block_number):
                logger.info(f"Skipping order execution as node is not leader for block {block_number}.")
                return {
                    "success": False,
                    "new_capital": capital,
                    "tx_hash": None,
                    "status": "skipped",
                    "error": "Not leader for current block",
                }
        except Exception as e:
            logger.warning(f"Leader check failed for block number: {e}")
            # If leader check itself fails, current logic proceeds to attempt swap.

        # Исполнение свопа
        try:
            result: Dict[str, Any] = await self.adapter.place_order(side, amount, price=price)
            if result.get("status") == "success":
                # Очень грубое обновление капитала — здесь можно улучшить, взяв точное изменение баланса
                new_capital = capital  # реальный капитал обновится позже через RPC (если нужно)
                return {
                    "success": True,
                    "new_capital": new_capital,
                    "tx_hash": result.get("tx_hash"),
                    "status": "success",
                    "error": None,
                }
            else:
                logger.error(f"Live swap failed: {result.get('error', 'Unknown error during swap')}. Result: {result}")
                return {
                    "success": False,
                    "new_capital": capital,
                    "tx_hash": result.get("tx_hash"),
                    "status": "failed",
                    "error": result.get("error", "Unknown swap error"),
                }
        except Exception as e:
            logger.error(f"Live swap execution failed unexpectedly: {e}", exc_info=True)
            return {
                "success": False,
                "new_capital": capital,
                "tx_hash": None,
                "status": "error",
                "error": str(e),
            }