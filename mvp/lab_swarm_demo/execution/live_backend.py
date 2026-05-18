"""
Исполнение на live/web3 (Sepolia через Uniswap V3).
"""
import logging
from typing import Dict, Any, Callable, Optional

from .backend import ExecutionBackend

logger = logging.getLogger(__name__)

# Constants for token addresses on Sepolia for demonstration purposes.
# In a production system, these might be loaded from a configuration or a network-specific registry.
WETH_ADDRESS: str = "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14"  # Example WETH address on Sepolia
USDC_ADDRESS: str = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"  # Example USDC address on Sepolia


class LiveExecutionBackend(ExecutionBackend):
    """
    Backend for executing orders on a live Web3 environment (e.g., Sepolia via Uniswap V3).
    It interacts with an adapter to place orders, check balances, and verify leadership status.

    Assumes the 'adapter' object provides specific methods for Web3 interaction,
    as detailed in the `__init__` method's docstring.
    """
    node_id: str
    adapter: Any  # Type `Any` because the specific adapter implementation is not defined here.
                  # A Protocol could be used for stronger typing if the adapter interface is stable.
    is_leader_func: Callable[[int], bool]

    def __init__(self, node_id: str, adapter: Any, is_leader_func: Callable[[int], bool]) -> None:
        """
        Initializes the LiveExecutionBackend.

        Args:
            node_id (str): Identifier for the current node. Used for logging.
            adapter (Any): An object capable of interacting with the blockchain (e.g., placing orders,
                           getting balances, accessing web3 instance). It's expected to have at least
                           the following callable attributes:
                           - `_get_token_balance(token_address: str) -> float`: To get token balances asynchronously.
                           - `w3.eth.block_number` (awaitable property/attribute): To get the current block number.
                           - `place_order(side: str, amount: float, price: float) -> Dict[str, Any]`:
                             To submit a trade order asynchronously.
            is_leader_func (Callable[[int], bool]): A callable that takes an integer (block number)
                                                     and returns a boolean, indicating if the current node
                                                     is the leader for that specific block.
        """
        self.node_id = node_id
        self.adapter = adapter
        self.is_leader_func = is_leader_func

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

        Performs checks for adapter availability, balance sufficiency (for sell orders),
        and leader status before attempting to place an order via the adapter.

        Note: The 'symbol' parameter is not currently utilized in the internal logic
        for determining which specific tokens to trade (e.g., WETH/USDC). The current
        implementation implicitly assumes WETH for selling and relies on available
        'capital' (which is assumed to be in USDC) for buying. For a more generic
        backend, the symbol should drive token address selection.

        Args:
            symbol (str): The trading pair symbol (e.g., "WETH/USDC").
                          Currently, this parameter is not directly used to determine
                          which token addresses to use for the swap.
            side (str): The order side ("buy" or "sell"). Expected to be "buy" to
                        exchange USDC for WETH, or "sell" to exchange WETH for USDC.
            amount (float): The amount of the base asset (e.g., WETH) to trade.
            price (float): The desired price for the trade (e.g., WETH price in USDC).
            capital (float): The current capital available, assumed to be in the quote
                             currency (e.g., USDC) for buy orders.

        Returns:
            Dict[str, Any]: A dictionary containing the result of the order execution,
            including success status, new capital (may be a placeholder), transaction hash,
            execution status, and any error message.
        """
        # Ensure the adapter is properly configured before proceeding
        if not self.adapter or not (hasattr(self.adapter, "place_order") and callable(self.adapter.place_order)):
            logger.error(f"[{self.node_id}] LiveExecutionBackend requires an adapter with a callable 'place_order' method.")
            return {
                "success": False,
                "new_capital": capital,
                "tx_hash": None,
                "status": "error",
                "error": "No adapter or adapter missing 'place_order' method",
            }

        adjusted_amount: float = amount

        # Perform balance check if selling. Currently hardcoded for WETH.
        if side.lower() == "sell":
            try:
                # Assuming _get_token_balance is an async method of the adapter
                weth_bal: float = await self.adapter._get_token_balance(WETH_ADDRESS)
                # Ensure we don't try to sell more WETH than available
                adjusted_amount = min(amount, weth_bal)
                logger.debug(
                    f"[{self.node_id}] Current WETH balance: {weth_bal:.4f}, "
                    f"requested sell amount: {amount:.4f}, adjusted to: {adjusted_amount:.4f}"
                )
            except Exception as e:
                logger.warning(
                    f"[{self.node_id}] Balance check skipped for selling WETH due to an error: {e}",
                    exc_info=False  # No stack trace by default for warnings
                )
                # If balance check fails, the current logic proceeds with the original 'amount'.
                # This might lead to a transaction revert later if the amount is too high.
                # Preserving original functionality.

        # Check if the adjusted amount is valid for a trade
        if adjusted_amount <= 0:
            error_message = "Insufficient balance or adjusted amount is zero/negative for trade."
            logger.info(f"[{self.node_id}] Skipping order: {error_message}")
            return {
                "success": False,
                "new_capital": capital,
                "tx_hash": None,
                "status": "rejected",  # Changed from 'error' to 'rejected' for clarity
                "error": error_message,
            }

        # Perform leader check
        block_number: Optional[int] = None
        try:
            # Assuming self.adapter.w3.eth.block_number is an awaitable property or method
            # `type: ignore [misc]` is used because `self.adapter` is `Any`, and mypy can't verify its attributes.
            block_number = await self.adapter.w3.eth.block_number  # type: ignore [misc]
            if not self.is_leader_func(block_number):
                logger.info(f"[{self.node_id}] Skipping order execution: Not leader for block {block_number}.")
                return {
                    "success": False,
                    "new_capital": capital,
                    "tx_hash": None,
                    "status": "skipped",
                    "error": "Not leader for current block",
                }
        except AttributeError:
            logger.error(
                f"[{self.node_id}] Adapter missing 'w3.eth.block_number' attribute required for leader check. "
                "Please ensure the adapter provides a web3 instance."
            )
            # If adapter structure is wrong, treat as an error preventing execution
            return {
                "success": False,
                "new_capital": capital,
                "tx_hash": None,
                "status": "error",
                "error": "Adapter misconfigured for leader check (missing w3.eth.block_number)",
            }
        except Exception as e:
            logger.warning(
                f"[{self.node_id}] Leader check failed for block number: {e}. Attempting swap anyway.",
                exc_info=False  # No stack trace by default for warnings
            )
            # As per original comment, if leader check fails, current logic proceeds to attempt swap.

        # Execute the swap via the adapter
        try:
            # The `place_order` method on the adapter is expected to handle the actual blockchain interaction.
            # It's assumed to return a dict with 'status' and optionally 'tx_hash', 'error'.
            result: Dict[str, Any] = await self.adapter.place_order(side=side, amount=adjusted_amount, price=price)

            if result.get("status") == "success":
                # Important: The 'new_capital' here is a placeholder.
                # In a real live system, the actual updated capital would need to be
                # fetched from an RPC call (e.g., getting balance of USDC after a buy)
                # or calculated from executed trade details (executed amount, fees).
                # The current design defers actual balance reconciliation to another process,
                # hence returning the initial 'capital'.
                new_capital_after_trade: float = capital
                logger.info(f"[{self.node_id}] Live swap successful. Tx_hash: {result.get('tx_hash')}")
                return {
                    "success": True,
                    "new_capital": new_capital_after_trade,
                    "tx_hash": result.get("tx_hash"),
                    "status": "filled",  # Changed from 'success' to 'filled' for clarity
                    "error": None,
                }
            else:
                error_msg: str = result.get("error", "Unknown error during swap")
                logger.error(
                    f"[{self.node_id}] Live swap failed: {error_msg}. Result: {result}",
                    exc_info=False  # Don't log stack trace unless truly unexpected
                )
                return {
                    "success": False,
                    "new_capital": capital,
                    "tx_hash": result.get("tx_hash"),
                    "status": "failed",
                    "error": error_msg,
                }
        except Exception as e:
            # Catch any unexpected exceptions during the adapter's place_order call
            logger.error(f"[{self.node_id}] Live swap execution failed unexpectedly: {e}", exc_info=True)
            return {
                "success": False,
                "new_capital": capital,
                "tx_hash": None,
                "status": "error",
                "error": str(e),
            }